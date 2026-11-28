"""Run Markdown off the server's interpreter, in one long-lived child process.

The child does two jobs. It projects the diffs a changed file's Rendered view draws,
Markdown (:mod:`metabrowser.diff.markdown_projection`) and YAML or JSON
(:mod:`metabrowser.diff.structured_projection`, a request whose ``op`` is
``structured``), and it renders the Markdown documents an untrusted author wrote that a
page asks the server for: a pinned mirror's files, a folder served with ``--untrusted``,
and a pull request's texts (:meth:`ProjectionWorker.render_inert`). Parsing YAML and
JSONC is pure Python as well, so a structured projection holds the GIL as a Markdown
projection does, and takes the same path.

**Projections.** A projection is pure Python. In a thread it holds the GIL, and every
other request on the server waits up to the interpreter's switch interval at each of its
event-loop wake-ups. With the 48,719-byte ``docs/reviewing-pull-requests.md`` pair
projecting continuously (Python 3.14, development Mac, load average 4, three alternating
phases), a request of eight wake-ups took 1.41-1.44 ms idle (p50), 32-35 ms beside a
projection thread and 1.41-1.42 ms (p95 at most 1.83 ms) beside the same projections in
this child, at the same 35-37 projections in 1.5 s. The repository budgets 50 ms for an
unrelated request's delay (``inventory_engine/providers/python_inventory.py``), and a
request with more wake-ups pays the switch interval at each. A projection starts the
child at the second one an event loop asks for, or when :meth:`ProjectionWorker.start`
is called (a page's ``prefetch=1`` request), and until it has imported the renderer each
projection a reader waits for runs in a thread, so the first screen of a Changes tab
never waits for it. A prefetch has no reader waiting, so the route lets it wait for the
child (``pull_rendered_diff``): the first screen's projections then run under the
child's deadline rather than on the server's interpreter. A build without the GIL, or a
platform where the child cannot start, keeps the thread.

**Inert renders.** KPress's cost depends on what a document contains, not only on its
size, and a document's author can choose it: the review of mb-273l timed 23.1 s for
1,000 unpaired ``[`` before 239 KB of ``%``, 2.5 s for one 512 KiB line of ``a--b``, and
11.6 s for a highlighted 1,622-byte ``console`` fence. A thread cannot be stopped, so a
render of such a document held the interpreter until it finished, and each reload
started another. Here a render that runs past :data:`_RENDER_DEADLINE_S` is stopped with
its child and refused, and the refusal is kept by the document's identity, its blob ID
or a hash of its text, so a reload is refused at once. An inert render never runs in a
thread: until the child is ready it waits for it, at most :data:`_START_WAIT_S`, and is
refused when it is not. It renders fenced code plain (``plain_code`` in
:mod:`metabrowser.kpress_adapter`), since the inert page drops every class the
highlighting would add, and reduces the HTML to the inert allowlist
(:mod:`metabrowser.inert_html`) in the child too. A served pin, a served ``--untrusted``
folder, and a served pull request's page start the child before their first document
(:func:`start_for_pages`), so it does not wait for the start; a one-shot command does
not, since it would not use the child it paid for.

**One child for both jobs.** One hostile text must not stall every other render and
projection on the server, so the child is shared under these rules:

- One exchange runs at a time, under a lock that belongs to the worker on its event loop
  rather than to one child, so no stop or replacement lets two exchanges share a pipe.
  Projections go first: one that finds an inert render holding the child projects in a
  thread, and one that finds a projection there waits ahead of every queued render. So an
  untrusted document never holds a Changes tab for longer than one projection, and never
  ends a projection's exchange by its deadline.
- Identical requests in flight share one render. When the last request waiting for it
  goes, the render is cancelled, and a child rendering it is stopped with no verdict
  kept: an abandoned render never holds the queue. The routes stop waiting when their
  client disconnects (:mod:`metabrowser.client_disconnect`), as a page that navigates
  away or a transclusion past its own deadline does.
- At most :data:`_MAX_RENDERS` distinct renders are in flight, the one in the child among
  them. Past that a render is refused ``renderer_busy`` (``503``), which is not kept.
- The front matter is the bounded loader's value (:mod:`metabrowser.frontmatter_yaml`),
  and the event loop never walks it: neither a kept refusal nor a flight's key reads it,
  and only the frame, built on a worker thread, encodes it.
- A refusal is kept only for what the child did with the document: it ran past the
  deadline, counted from when the child had the whole request, with a last look at the
  pipe, and a longer one when the server's own loop ran the deadline late; or the child
  exited on it twice.
  A child already dead when the request reached it, or killed from outside, is not the
  document's doing: the render runs once more on a fresh child. A kept refusal lapses
  after :data:`_VERDICT_TTL_S`, so a moment of heavy load does not hide a document for
  the server's life.
- Three starts in a row that do not become ready stop the worker trying for
  :data:`_START_COOL_OFF_S`, after which it tries again. The first failure of each run of
  them is logged at warning, and so is each refusal a render makes.
- The child leads its own process group, so a terminal's suspend of the server's group
  does not stop it; on Python 3.14.7 and later on macOS, asyncio's child watcher reaps a
  child stopped in the server's group with a blocking wait on the event loop, which then
  never wakes. It still ends with the server: when its input closes, when the server it
  started from is gone (it looks every :data:`_PARENT_POLL_S`, mid-render too), or when
  the server stops at once on Ctrl-C (:func:`stop_children`, which signals only a child
  not yet reaped). The end of its standard error is kept, for the log line that says why
  a child ended.

The child costs memory while it runs: 56-66 MB resident once it is ready and 63-70 MB
after all 434 of this repository's real Markdown pairs (macOS ``ps`` RSS, two runs each
in two reviews of #349, under different loads). It stops after ten idle minutes, and
the next render or projection starts it again.

The child is this module run with ``python -m``, so it never imports the server's main
module, and it speaks length-prefixed JSON over its standard input and output: plain
data each way, nothing executable. A child that overruns or exits is stopped, and
another starts at once when a render killed it, or on demand otherwise.

This module is imported by the server, so the projection module, which imports KPress
and Pygments, is imported where a projection runs rather than here: the server's start
does not pay for a renderer, as :mod:`metabrowser.kpress_adapter` explains.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import json
import logging
import os
import signal
import sys
import threading
import time
from collections import OrderedDict, deque
from collections.abc import AsyncGenerator, Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Final, Literal, cast

from metabrowser import event_log, kpress_adapter
from metabrowser.diff.format import FilePatch

if TYPE_CHECKING:
    from metabrowser.diff.markdown_projection import MarkdownDiffProjection, PreparedMarkdownDiff
    from metabrowser.diff.structured_projection import Format, StructuredDiffProjection

LOG = logging.getLogger(__name__)

# A request frame larger than this is a protocol fault. A projection is at most 128 KiB
# of blobs and their patch (``STRUCTURED_DIFF_MAX_BYTES``, for strict JSON); a render is the route's text, at most
# ``settings.TEXT_PREVIEW_REQUEST_MAX_BYTES`` (16 MiB) of UTF-8, base64-encoded to a
# third more, beside its front matter: the loader's value, within
# ``FRONTMATTER_MAX_EXPANDED_SIZE`` (``frontmatter_yaml.py``), at most twelve bytes of
# ASCII JSON a unit of it (an astral character's two escapes; the largest accepted
# string of them aliased framed to 12.6 MB, 2026-11-18).
_MAX_REQUEST_FRAME: Final = 64 * 1024 * 1024
# An answer frame larger than this is a protocol fault. A projection answers at most a
# few hundred KiB of HTML. A render's answer is bounded by what the child writes before
# the deadline. KPress's record of the raw HTML it removed (``sanitizer_diagnostics``)
# was most of it, 41 times its source for 256 KiB of an unknown tag (10.8 MB, measured
# 2026-11-17 at a load average of 10 to 21), and an inert render no longer carries it;
# the largest of this repository's Markdown files answered 2.1 MB. The bound is several
# deadlines of the diagnostics.
_MAX_ANSWER_FRAME: Final = 256 * 1024 * 1024
# The child was ready 0.57 s after it started at load average 4 (review C of #349 saw
# about 2 s under heavier load); it is given far longer before it counts as failed.
_START_TIMEOUT_S = 30.0
# A projection answers within its budgets in well under a second: the slowest Markdown
# input measured inside every budget took 222-268 ms, front matter adds at most what
# ``markdown_projection._FRONTMATTER_MAX_NODES`` records, and the slowest structured
# shapes, recorded beside the budgets in ``structured_projection.py``, take about as long
# as the slowest Markdown input. A child that has not answered after this is stopped.
_PROJECTION_TIMEOUT_S = 10.0
# The longest one untrusted document's render may run in the child before the child is
# stopped and the document refused. Measured 2026-11-17 on an Apple M1 Pro
# (MacBookPro18,1), macOS 26.5.2, Python 3.14.7, KPress 0.3.8, at a load average of 9.9
# to 12.6, three renders of each with plain code and the inert hardening, as the child
# runs them: of the 30 largest Markdown files tracked in this repository, the slowest,
# `explorations/performance-loop/report.md` (325 KB), took 1.07 to 1.19 s to render and
# 0.19 s to harden, and the next, `docs/design-system.md` (340 KB), 0.22 to 0.23 s and
# 0.02 to 0.03 s; the other 28 took 0.04 to 0.23 s in all. Through the child, frames
# included, report.md answered in 1.26 to 1.75 s over five renders at a load average of
# 16 to 17. Five seconds is about three times that, room for a heavier load; a document
# over it is shown as source. What that refuses of honest documents (review C of #527,
# load average 10, deadline lifted): this repository's documents concatenated rendered
# 1 MiB in 0.83 s, 2 MiB in 1.88 s, and 4 MiB in 4.03 s, so ordinary prose reaches the
# deadline near 4 to 5 MiB, and text as table-heavy as report.md near 1.2 MB.
# METABROWSER_INERT_RENDER_DEADLINE_MS replaces it, as the other budgets in
# docs/command-line.md are replaced, and must be a positive number of milliseconds.
INERT_RENDER_DEADLINE_MS: Final = 5_000


def _deadline_from_environment() -> float:
    raw = os.environ.get("METABROWSER_INERT_RENDER_DEADLINE_MS", str(INERT_RENDER_DEADLINE_MS))
    milliseconds = int(raw)
    if milliseconds < 1:
        # Zero or less would refuse every document at once, and keep each refusal.
        raise ValueError(
            "METABROWSER_INERT_RENDER_DEADLINE_MS must be a positive number of milliseconds,"
            f" not {raw!r}"
        )
    return milliseconds / 1000


_RENDER_DEADLINE_S = _deadline_from_environment()
# How long an inert render waits for the child to start before it is refused as
# unavailable, a refusal that is not kept. A start is not a render: it costs the
# interpreter's start and the imports and warm-up of both jobs, the same for every
# document, and it grows with the machine's load, not with what an author wrote. So the
# wait is its own measured bound, and METABROWSER_INERT_RENDER_DEADLINE_MS does not move
# it in either direction: a deadline shortened to refuse a slow document must not refuse
# every document whose child starts cold (a one-shot `--api` command's always does), and
# one lengthened for a large document says nothing of starts.
#
# Measured on an Apple M1 Pro (MacBookPro18,1, 10 cores), macOS 26.5.2, Python 3.14.7,
# from `ProjectionWorker.start(renders=True)` to the ready frame, both jobs warmed:
#
# - 1.36 s at a load average of 16 (2026-11-17); the projection alone 0.23 to 0.57 s at
#   a load average of 4 (#349).
# - 2.71 to 6.81 s over twelve starts in a row at a load average of 356 to 372
#   (2026-11-22): median 3.9 s, two of the twelve past 5 s (6.70 and 6.81 s).
# - Under the same kind of load, at 300 to 400, renders were refused as unavailable 5.1
#   to 8.3 s after they were asked (mb-xmte), when this wait was the render deadline's
#   default of 5 s.
#
# Fifteen seconds is about twice the slowest start seen, and half of _START_TIMEOUT_S,
# after which a start counts as failed. A start that fails ends the wait at once, so
# only a child that is slow or hung costs a reader the whole of it, and the start goes
# on after a refusal: a reload finds the child ready or still starting.
_START_WAIT_S = 15.0
# Starts in a row that did not become ready before the worker stops trying for
# _START_COOL_OFF_S: projections stay in their thread, and inert renders are refused as
# unavailable, until the cool-off passes, a start succeeds, or a stop counts again.
_MAX_STARTS = 3
# How long the worker waits after the start limit before it tries again. A start that
# cannot spawn fails in under a millisecond, and one whose child dies importing costs its
# import (0.2 to 0.3 s), so a broken installation costs at most three of either per
# cool-off while reloads continue; what makes a start fail and then pass (a full process
# table, an interpreter replaced mid-upgrade) passes in seconds, so the notice's "Reload
# the page to try again" holds a few seconds later.
_START_COOL_OFF_S = 10.0
# Distinct inert renders in flight at once, the one in the child among them; past it a
# render is refused renderer_busy, not kept. A page reaches the server over at most six
# connections (HTTP/1.1, which the server speaks, and Chrome's and WebKit's six per
# host), one of them the events stream, so one page's renders are never more than five at
# once: a document's transclusions, which each ask at once, and a pull request page's two
# texts at a time (MARKDOWN_CONCURRENCY in pull-page.js) fit, with room for a second
# page's first renders. A document holds the child for one exchange and a restart, or,
# when its first child ends before answering, for a second exchange on a fresh child too
# (the retry in _render_flight): at most two deadlines and two starts. So a render
# admitted behind a full queue of hostile documents waits at most seven of those: about
# 90 s at the default with starts of 1.4 s (load average 16), about 165 s with the
# 6.8 s starts measured at a load average near 370, and about 37 s when they only run
# long. A start that hangs costs up to _START_WAIT_S instead. Past that the reader's
# reload is the better retry, as pull_rendered_diff's _Slot reasons for diffs.
_MAX_RENDERS: Final = 8
# When the deadline fires, an answer the loop has already read, or reads in its next turn,
# is taken, however late the deadline ran (review E of #527, E3). A deadline that fired
# more than _LATE_S late was held up by the server's own event loop (the repository
# budgets 50 ms for an unrelated request's delay), so the child's whole answer may still
# be in the pipe, unread: it gets one more look, of at most _ANSWER_GRACE_S, before the
# render counts as past its deadline. Reading a 21.6 MB answer from the pipe took 42 to
# 57 ms (review C of #527).
_LATE_S = 0.05
_ANSWER_GRACE_S = 0.25
# The last of a child's standard error kept, for the log line that says why it ended (a
# traceback's last frames and its error), and how long that line waits for the rest of
# it once the child has gone. The pipe is drained as the child writes, so a library that
# prints a great deal never blocks the child.
_STDERR_TAIL_BYTES: Final = 2048
_STDERR_TAIL_WAIT_S = 0.5
# A child no projection or render has used for this long is stopped; the next one starts
# it again. A start took 0.23-0.24 s to ready (review E of #349), against 56-63 MB kept
# resident for as long as the server runs.
_IDLE_S = 600.0
# While an exchange holds the child past the idle limit, the idle stop looks again this
# often rather than at every turn of the event loop.
_IDLE_RECHECK_S = 1.0
# How long a closing server waits for the children it stopped to exit, so none is reaped
# after its event loop has closed: asyncio then logs, on standard error, that the loop
# handling that pid is closed, which a one-shot `--api` command printed on Python 3.14
# (CI, 2026-11-17). A killed child exits in milliseconds.
_REAP_S = 2.0
# Refusals kept, by document. Each one cost a deadline of the child's time, so a server
# reaches this only after hours of refused renders; it bounds what a flood of distinct
# documents can make the server keep, at about 280 bytes a verdict (its key, its
# identity string, and its OrderedDict entry, measured with tracemalloc by review C of
# #527): 280 KiB at the bound, after which the least recently asked is forgotten.
_MAX_VERDICTS: Final = 1024
# How long a kept refusal stands. A hostile document then costs one deadline of the
# child's time each ten minutes (5 s in 600 s, under 1% of it), and a document refused at
# a moment of heavy load renders again ten minutes later, the child's own idle period.
_VERDICT_TTL_S = 600.0
# The same two bounds, for a route that keeps the refusal of a projection this worker
# stopped at its deadline (``pull_rendered_diff``): the worker keeps no verdict for a
# projection, whose identity is the route's.
STOPPED_TTL_S: Final = _VERDICT_TTL_S
MAX_STOPPED: Final = _MAX_VERDICTS
# How often the child looks whether the server that started it is still there, so it
# ends with the server even while it renders a document that would take minutes.
_PARENT_POLL_S = 1.0
# A warm child used 63–70 MB over 434 ordinary Markdown pairs. On macOS arm64,
# Python 3.14.7, four 10–92 KB project guides rendered twice peaked at 69.27 MiB;
# a 256 MiB ceiling leaves over 3.6 times that peak. Reading ru_maxrss took
# 0.61 µs and 50 ms samples ran 55 ms apart at the median, up to 65 ms.
# This is a sampled budget: scheduling or a native call holding the GIL can
# delay enforcement. Check again before giving the parent a completed answer.
_RSS_BYTES = 256 * 1024 * 1024
_RSS_POLL_S = 0.05
_RSS_EXIT = 86

type RefusalCode = Literal[
    "render_deadline", "renderer_exited", "renderer_unavailable", "renderer_busy"
]

_REFUSALS: Final[dict[RefusalCode, tuple[int, str]]] = {
    "render_deadline": (422, "Rendering took longer than {deadline}, so it was stopped"),
    "renderer_exited": (422, "The renderer stopped while rendering this document"),
    "renderer_unavailable": (503, "The document renderer is unavailable"),
    "renderer_busy": (503, "The document renderer is busy with other documents"),
}


class InertRenderRefused(Exception):
    """An untrusted document's render was refused, and *code* says why.

    *remembered* says the answer is a refusal kept from an earlier render, given without
    rendering the document again.
    """

    def __init__(self, code: RefusalCode, *, remembered: bool = False) -> None:
        super().__init__(code)
        self.code: RefusalCode = code
        self.remembered = remembered

    @property
    def http_status(self) -> int:
        """The status a route answers the refusal with."""

        return _REFUSALS[self.code][0]

    def payload(self) -> dict[str, Any]:
        """What a route answers: the code, a sentence for ``--api``, the deadline, and
        whether the refusal was kept from an earlier render."""

        seconds = _RENDER_DEADLINE_S
        deadline = f"{seconds:g} second" + ("" if seconds == 1 else "s")
        return {
            "code": self.code,
            "error": _REFUSALS[self.code][1].format(deadline=deadline),
            "deadline_ms": round(seconds * 1000),
            "remembered": self.remembered,
        }


def kpress_refusal_payload(refused: InertRenderRefused, path: str) -> dict[str, Any]:
    """The ``/api/kpress/render`` answer to a refused render, on a folder and a pin alike."""

    return {"type": "kpress_render_refused", **refused.payload(), "path": path}


@dataclass(frozen=True, slots=True)
class InertRender:
    """One untrusted document to render in the child.

    *identity* names the document's bytes: ``blob:<oid>`` for a Git blob, or
    :func:`text_identity` of the text. A refusal is kept by it with the kind, extension,
    and mode, so another request for the same bytes is refused without rendering.
    *link_base*, when given, makes the answer a pull request's text: only its HTML,
    reduced by :func:`metabrowser.inert_html.harden` with every reference made absolute
    against that page. Without it the answer is :func:`kpress_adapter.inert_render`'s.
    *display_path* only names the document in the log.

    *frontmatter* and *frontmatter_error* are what the bounded loader
    (:func:`metabrowser.frontmatter_yaml.load_frontmatter_yaml`) made of the document's
    front matter: a JSON-safe mapping with string keys, within its budget, or the reason
    it refused. The loader owns that form, so the mapping crosses to the child as it is.
    """

    source_text: str
    source_path: str
    identity: str
    kind: str
    view: str
    ext: str
    mtime_hash: str
    size: int
    frontmatter: dict[str, Any] | None = None
    frontmatter_error: str | None = None
    profile: str | None = None
    include_toc: Literal["auto", "on", "off"] = "auto"
    link_base: str | None = None
    mark_path_relative: bool = False
    # What the log names the document by, where *source_path* is a route's token rather
    # than a name a reader knows (a pin's wire path); *source_path* otherwise.
    display_path: str | None = None
    fence_origin: bytes | None = None

    @property
    def verdict_key(self) -> tuple[str, ...]:
        return (
            self.identity,
            self.kind,
            self.ext,
            "document" if self.link_base is None else "text",
        )

    @property
    def flight_key(self) -> tuple[object, ...]:
        """Everything that makes one render differ from another of the same bytes.

        The front matter is not in it, and the key never reads it: every route parses it
        from what the rest of the key names, a pin's blob or the text a page sent, which
        *identity* hashes, or a folder's file at *source_path* as of *mtime_hash* (its
        size and modification time in nanoseconds; a file rewritten between a request's
        reads of it can pair one version's text with another's front matter, and its
        *kind*, whatever the key holds). Encoding it was the key's one cost
        (review E of #527, E1): for the largest values the loader accepts, the
        near-budget shapes of ``devtools/frontmatter_bound_benchmark.py``, up to 65 ms of
        CPU (one-key mappings of an empty mapping, 4 KB of YAML), and the event loop's
        longest gap was the same 66 ms with the encoding on a worker thread, since C's
        JSON encoder holds the interpreter throughout (Apple M1 Pro, CPython 3.14.7 with
        the GIL, load average 4 to 6, 2026-11-18).
        """

        return (
            *self.verdict_key,
            self.source_path,
            self.view,
            self.mtime_hash,
            self.profile,
            self.include_toc,
            self.link_base,
            self.mark_path_relative,
            self.fence_origin,
        )


def text_identity(text: str) -> str:
    """The identity of a document with no blob: a hash of its text. Blocking for a large text."""

    return "sha256:" + hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def _gil_enabled() -> bool:
    probe = cast("Callable[[], bool] | None", getattr(sys, "_is_gil_enabled", None))
    return True if probe is None else probe()


def _frame(payload: object) -> bytes:
    data = json.dumps(payload, separators=(",", ":")).encode()
    return len(data).to_bytes(4, "big") + data


def _blob(data: bytes | None) -> str | None:
    return None if data is None else base64.b64encode(data).decode()


def _unblob(value: object) -> bytes | None:
    return None if value is None else base64.b64decode(str(value), validate=True)


def _encode(
    old: bytes | None, new: bytes | None, patch: FilePatch, namespace: str
) -> dict[str, Any]:
    return {
        "op": "project",
        "old": _blob(old),
        "new": _blob(new),
        "patch": patch.model_dump(mode="json"),
        "namespace": namespace,
    }


def _encode_structured(old: bytes | None, new: bytes | None, fmt: Format) -> dict[str, Any]:
    return {"op": "structured", "format": fmt, "old": _blob(old), "new": _blob(new)}


def _encode_render(request: InertRender, asset_url_prefix: str) -> dict[str, Any]:
    return {
        "op": "render",
        "source": base64.b64encode(request.source_text.encode("utf-8", "surrogatepass")).decode(),
        "source_path": request.source_path,
        "kind": request.kind,
        "view": request.view,
        "ext": request.ext,
        "mtime_hash": request.mtime_hash,
        "size": request.size,
        "frontmatter": request.frontmatter,
        "frontmatter_error": request.frontmatter_error,
        "profile": request.profile,
        "include_toc": request.include_toc,
        "asset_url_prefix": asset_url_prefix,
        "link_base": request.link_base,
        "mark_path_relative": request.mark_path_relative,
        "fence_origin": _blob(request.fence_origin),
    }


def _decode(answer: dict[str, Any]) -> PreparedMarkdownDiff:
    """A Markdown projection's answer."""

    from metabrowser.diff.markdown_projection import LocalReference, PreparedMarkdownDiff

    projection = cast("MarkdownDiffProjection", answer["projection"])
    references = tuple(
        LocalReference(str(href), bool(image), str(template), str(fallback))
        for href, image, template, fallback in answer["references"]
    )
    return PreparedMarkdownDiff(projection, references)


def _decode_structured(answer: dict[str, Any]) -> StructuredDiffProjection:
    """A YAML or JSON projection's answer."""

    return cast("StructuredDiffProjection", answer["structured"])


def _project(request: dict[str, Any]) -> dict[str, Any]:
    from metabrowser.diff.markdown_projection import prepare_markdown_diff

    # The server stops this child at its deadline, so the input budgets of a projection
    # nothing stops do not apply here.
    prepared = prepare_markdown_diff(
        old=_unblob(request["old"]),
        new=_unblob(request["new"]),
        patch=FilePatch.model_validate(request["patch"]),
        namespace=str(request["namespace"]),
        stoppable=True,
    )
    return {
        "projection": prepared.projection,
        "references": [
            [reference.href, reference.image, reference.template, reference.fallback]
            for reference in prepared.references
        ],
    }


def _render(request: dict[str, Any]) -> dict[str, Any]:
    """One inert render, as the child answers it: the render, or which KPress error."""

    from metabrowser.inert_html import harden

    source = base64.b64decode(str(request["source"]), validate=True)
    try:
        rendered = kpress_adapter.render_kpress_view(
            source_text=source.decode("utf-8", "surrogatepass"),
            source_path=str(request["source_path"]),
            kind=str(request["kind"]),
            view=str(request["view"]),
            ext=str(request["ext"]),
            mtime_hash=str(request["mtime_hash"]),
            size=int(request["size"]),
            frontmatter=cast("dict[str, Any] | None", request["frontmatter"]),
            frontmatter_error=cast("str | None", request["frontmatter_error"]),
            profile=cast("str | None", request["profile"]),
            include_toc=cast("Literal['auto', 'on', 'off']", request["include_toc"]),
            plain_code=True,
            fence_origin=_unblob(request.get("fence_origin")),
            asset_url_prefix=str(request["asset_url_prefix"]),
        )
    except kpress_adapter.KPressInvalidRequestError as exc:
        return {"error": "invalid", "message": str(exc)}
    except kpress_adapter.KPressRenderError as exc:
        return {"error": "render", "message": str(exc)}
    link_base = request["link_base"]
    if isinstance(link_base, str):
        html = harden(
            str(rendered["html"]), link_base, mark_path_relative=bool(request["mark_path_relative"])
        )
        return {"rendered": {"html": html}}
    inert = kpress_adapter.inert_render(rendered)
    # What KPress's sanitizer removed is for `--api` and debugging of a trusted render
    # (kpress_adapter._separate_sanitizer_diagnostics); no page reads it, and for raw HTML
    # it was most of the answer (see _MAX_ANSWER_FRAME), so it does not cross.
    inert.pop("sanitizer_diagnostics", None)
    return {"rendered": inert}


def _project_structured(request: dict[str, Any]) -> dict[str, Any]:
    from metabrowser.diff.structured_projection import project_structured_diff

    return {
        "structured": project_structured_diff(
            old=_unblob(request["old"]),
            new=_unblob(request["new"]),
            fmt=cast("Format", request["format"]),
        )
    }


def _answer(request: dict[str, Any]) -> dict[str, Any]:
    op = request.get("op")
    if op == "render":
        return _render(request)
    if op == "structured":
        return _project_structured(request)
    return _project(request)


def _warm() -> None:
    """Import and exercise both jobs once, as the child's first work."""

    from metabrowser.diff.markdown_projection import warm_markdown_projection
    from metabrowser.diff.structured_projection import warm_structured_projection

    warm_markdown_projection()
    # The YAML loader and json5 cost the first file that reads them 26-29 ms otherwise
    # (mb-8274 review C9).
    warm_structured_projection()
    _render(
        _encode_render(
            InertRender(
                source_text="# Warm\n\nA [link](a.md), `code`, and\n\n```console\n$ x\n```\n",
                source_path="warm.md",
                identity="warm",
                kind="markdown",
                view="document",
                ext=".md",
                mtime_hash="warm",
                size=0,
            ),
            "/kpress-static/",
        )
    )


def serve(source: BinaryIO, sink: BinaryIO, *, watching: threading.Event | None = None) -> None:
    """The child's loop: one answer for each request until its input closes."""

    if watching is not None:
        watching.set()
    _warm()
    if watching is not None:
        _check_rss()
        watching.clear()
    sink.write(_frame({"ready": True}))
    sink.flush()
    while len(header := source.read(4)) == 4:
        size = int.from_bytes(header, "big")
        if size > _MAX_REQUEST_FRAME:
            return
        if watching is not None:
            watching.set()
        body = source.read(size)
        if len(body) != size:
            return
        answer = _frame(_answer(json.loads(body)))
        if watching is not None:
            _check_rss()
            watching.clear()
        sink.write(answer)
        sink.flush()
        del answer, body


async def _read_body(stream: asyncio.StreamReader, limit: int) -> bytes:
    size = int.from_bytes(await stream.readexactly(4), "big")
    if size > limit:
        raise ConnectionError("oversized frame from the Markdown child")
    return await stream.readexactly(size)


async def _read(stream: asyncio.StreamReader) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(await _read_body(stream, _MAX_ANSWER_FRAME)))


# The Markdown children this process started and has not killed, by process ID, with the
# Process whose ``returncode`` asyncio sets once it reaps the child: from then on the ID
# may belong to another process.
_CHILDREN: dict[int, asyncio.subprocess.Process] = {}


def _unreaped(pid: int) -> bool:
    """Whether *pid* is, now, a child of this process not yet reaped, alive or not.

    Its ID stays its own until it is reaped, so a signal to it reaches no one else.
    ``WNOWAIT`` leaves it for asyncio to reap. Python before 3.13 has no ``waitid`` on
    macOS; there the Process's ``returncode`` is all there is.
    """

    waitid = getattr(os, "waitid", None)
    if waitid is None:
        return True
    try:
        waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except ChildProcessError:
        return False
    return True


def stop_children() -> None:
    """Kill every Markdown child this process started that is still its own, at once.

    For a command that ends without unwinding, such as a server stopped by Ctrl-C
    (``cli/serve.py``): a child leads its own process group, so the terminal's signal does
    not reach it. A child that died of anything else and was reaped is skipped, since its
    ID may name another process by now (review E of #527, E2). It needs nothing from the
    event loop, so a signal handler may call it.
    """

    for pid, process in list(_CHILDREN.items()):
        if process.returncode is None and _unreaped(pid):
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)
    _CHILDREN.clear()


def _forget_reaped() -> None:
    for pid, process in list(_CHILDREN.items()):
        if process.returncode is not None:
            del _CHILDREN[pid]


# A child also exits when its input closes with this process; this ends one mid-import.
_register = cast(
    "Callable[[Callable[[], None]], None] | None", getattr(threading, "_register_atexit", None)
)
if _register is not None:
    _register(stop_children)


@dataclass(slots=True)
class _Serving:
    pages: bool = False


# Whether this process serves pages, as ``metab`` serving a folder or a pin does, rather
# than answering one command: only a served page asks for documents soon enough after its
# first read to repay starting the child ahead of them (:func:`serve_pages`).
_SERVING: Final = _Serving()


def serve_pages() -> None:
    """Say this process serves pages: ``cli/serve.py`` calls it before the server starts."""

    _SERVING.pages = True


def start_for_pages() -> None:
    """Start the child ahead of the documents a page will ask for, on this event loop,
    when this process serves pages; a one-shot command never pays for it."""

    if _SERVING.pages:
        shared_worker().start(renders=True)


type _HolderKind = Literal["projection", "render"]


class _ChildLock:
    """The child's one exchange at a time, with waiting projections served before waiting
    renders. It belongs to the worker on one event loop, not to one child."""

    def __init__(self) -> None:
        self.holder: _HolderKind | None = None
        self._waiting: dict[_HolderKind, deque[asyncio.Future[None]]] = {
            "projection": deque(),
            "render": deque(),
        }

    def locked(self) -> bool:
        return self.holder is not None

    @property
    def rendering(self) -> bool:
        """Whether an inert render holds the child, which it may for its whole deadline."""

        return self.holder == "render"

    @contextlib.asynccontextmanager
    async def hold(self, kind: _HolderKind) -> AsyncGenerator[None]:
        await self._acquire(kind)
        try:
            yield
        finally:
            self._release()

    async def _acquire(self, kind: _HolderKind) -> None:
        if self.holder is None:
            self.holder = kind
            return
        future = asyncio.get_running_loop().create_future()
        queue = self._waiting[kind]
        queue.append(future)
        try:
            await future
        except asyncio.CancelledError:
            if future.done() and not future.cancelled():
                # Handed the child just as this was cancelled: hand it on.
                self._release()
            else:
                with contextlib.suppress(ValueError):
                    queue.remove(future)
            raise

    def _release(self) -> None:
        for kind in ("projection", "render"):
            queue = self._waiting[kind]
            while queue:
                future = queue.popleft()
                if not future.done():
                    self.holder = kind
                    future.set_result(None)
                    return
        self.holder = None


def _named(request: InertRender) -> str:
    """What a log line names *request*'s document by; logged with ``%r``, so a name in an
    untrusted tree cannot put a newline or a terminal escape in the operator's log."""

    return request.display_path or request.source_path


class _Tail:
    """The last :data:`_STDERR_TAIL_BYTES` a child wrote to its standard error."""

    def __init__(self) -> None:
        self._data = bytearray()
        self._task: asyncio.Task[None] | None = None

    @classmethod
    def follow(cls, process: asyncio.subprocess.Process) -> _Tail:
        tail = cls()
        if process.stderr is not None:
            tail._task = asyncio.get_running_loop().create_task(tail._drain(process.stderr))
        return tail

    async def _drain(self, stream: asyncio.StreamReader) -> None:
        while chunk := await stream.read(64 * 1024):
            self._data += chunk
            del self._data[:-_STDERR_TAIL_BYTES]

    def done(self) -> bool:
        return self._task is None or self._task.done()

    async def text(self) -> str:
        """What it holds once the pipe has closed, or after a short wait for that."""

        if self._task is not None and not self._task.done():
            await asyncio.wait({self._task}, timeout=_STDERR_TAIL_WAIT_S)
        return self._data.decode("utf-8", "replace").strip()


@dataclass(frozen=True, slots=True)
class _Failed:
    """How a render ended without HTML, as a flight returns it (nothing raises out of a
    flight, so a render no request waits for any more is never logged as unretrieved)."""

    kind: Literal["refused", "invalid", "render"]
    code: RefusalCode = "renderer_unavailable"
    remembered: bool = False
    message: str = ""

    def error(self) -> Exception:
        if self.kind == "invalid":
            return kpress_adapter.KPressInvalidRequestError(self.message)
        if self.kind == "render":
            return kpress_adapter.KPressRenderError(self.message)
        return InertRenderRefused(self.code, remembered=self.remembered)


type _Outcome = dict[str, Any] | _Failed


@dataclass(frozen=True, slots=True)
class _Answered[T]:
    """A projection's decoded answer from the child."""

    value: T


@dataclass(slots=True)
class _Flight:
    """One render and the requests waiting for it."""

    task: asyncio.Task[_Outcome]
    waiters: int = 0


class ProjectionWorker:
    """Prepare projections in the child once it is ready, and in a thread until then;
    render untrusted documents in the child only."""

    def __init__(self, *, processes: bool = True, command: Sequence[str] | None = None) -> None:
        # Whether projections may move to the child. Inert renders always use it.
        self._processes = processes and _gil_enabled()
        # Isolated mode: no working directory or script directory on the module path, and
        # no PYTHON* variable or user site-packages, so the child runs only installed code
        # wherever the server was started (a checkout of the reviewed pull request
        # included). It starts in the package's own directory, as cache/probe.py's does.
        self._command = tuple(command or (sys.executable, "-I", "-m", __name__))
        self._process: asyncio.subprocess.Process | None = None
        # The event loop this worker serves. Its child, lock, and flights belong to it.
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock: _ChildLock | None = None
        self._starting: asyncio.Task[None] | None = None
        self._ready = False
        self._starts = 0
        self._failed_at = -_START_COOL_OFF_S
        self._start_warned = False
        self._requests = 0
        # What each child this loop started last wrote to its standard error.
        self._tails: dict[asyncio.subprocess.Process, _Tail] = {}
        self._counted: asyncio.AbstractEventLoop | None = None
        self._used = 0.0
        self._idle_timer: asyncio.TimerHandle | None = None
        # Refusals kept, by document, with when each was kept (time.monotonic).
        self._verdicts: OrderedDict[tuple[str, ...], tuple[RefusalCode, float]] = OrderedDict()
        self._flights: dict[tuple[object, ...], _Flight] = {}
        # Children killed that may not have been reaped yet, with the loop each belongs
        # to, which alone can wait for it (:meth:`aclose`).
        self._dying: dict[asyncio.subprocess.Process, asyncio.AbstractEventLoop] = {}

    @property
    def ready(self) -> bool:
        """Whether the child is ready on this event loop."""

        return self._ready and self._loop is _running_loop()

    async def started(self) -> bool:
        """Wait for a start in progress; whether the child is now ready."""

        if self._starting is not None:
            await asyncio.shield(self._starting)
        return self.ready

    async def settle(self) -> bool:
        """Wait for a start in progress, at most as long as an inert render waits for one
        (:data:`_START_WAIT_S`); whether the child is now ready.

        A request no reader waits on, a page's prefetch, waits here, so its projection
        runs in the child under :data:`_PROJECTION_TIMEOUT_S` rather than in a thread that
        nothing stops (mb-8274 review C2: the first screen's four files were answered from
        threads by 150-207 ms, and the child was ready at 312-488 ms).
        """

        if self._starting is not None:
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(_START_WAIT_S):
                    await asyncio.shield(self._starting)
        return self.ready

    def _bind(self, loop: asyncio.AbstractEventLoop) -> _ChildLock:
        """This worker on *loop*: a child's pipes and its reaping belong to the loop that
        started it, so another loop stops it and begins again."""

        if self._loop is not loop or self._lock is None:
            if self._loop is not None:
                self.stop()
                self._dying = {}
                self._tails = {}
            self._loop, self._lock = loop, _ChildLock()
            self._flights = {}
        return self._lock

    def start(self, *, renders: bool = False) -> None:
        """Start the child on this event loop if it is not running; it does not wait.

        Projections start it only where they would use it; *renders* starts it on any
        build, since an inert render runs nowhere else.
        """

        loop = asyncio.get_running_loop()
        self._bind(loop)
        if (not self._processes and not renders) or self._starting is not None:
            return
        if self._starts >= _MAX_STARTS:
            if time.monotonic() - self._failed_at < _START_COOL_OFF_S:
                return
            self._starts = 0
        self._starts += 1
        # A job in the event log, so the time a page waited for a start is told apart from
        # the projection it then waited for (mb-1jp0).
        self._starting = loop.create_task(
            event_log.job(
                self._launch(), "markdown_projection_worker.start", attrs={"renders": renders}
            )
        )

    async def _launch(self) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path(__file__).resolve().parent,
                # Its own group: see "One child for both jobs" above.
                process_group=0,
            )
        except OSError as exc:
            # The next request may try again, up to the start limit.
            self._starting = None
            self._start_failed(f"it could not be spawned: {exc}")
            return
        self._process = process
        _forget_reaped()
        _CHILDREN[process.pid] = process
        self._tails = {
            each: tail
            for each, tail in self._tails.items()
            if each.returncode is None or not tail.done()
        }
        self._tails[process] = _Tail.follow(process)
        assert process.stdout is not None
        failure: str | None = None
        try:
            ready = await asyncio.wait_for(_read(process.stdout), _START_TIMEOUT_S)
        except TimeoutError:
            failure = f"it was not ready after {_START_TIMEOUT_S:g} s"
        except (ConnectionError, asyncio.IncompleteReadError, ValueError):
            failure = "it exited before it was ready"
        else:
            if ready.get("ready") is not True:
                failure = "its first answer was not the ready frame"
        if self._process is not process:
            # Stopped from here while it started: that start did not fail.
            return
        if failure is not None:
            self._kill(process)
            self._start_failed(failure + await self._said(process))
            return
        self._ready = True
        self._starts = 0
        self._start_warned = False
        # Counted from the start, not the first answer: a page's prefetch starts the
        # child, and its answers may all come from the thread or the route's cache.
        self._touch()

    def _start_failed(self, cause: str) -> None:
        self._failed_at = time.monotonic()
        limit = self._starts >= _MAX_STARTS
        if not self._start_warned:
            self._start_warned = True
            LOG.warning("The Markdown child did not start: %s", cause)
        else:
            LOG.debug("The Markdown child did not start again: %s", cause)
        if limit:
            LOG.warning(
                "The Markdown child failed %d starts in a row; it is tried again in %g s",
                _MAX_STARTS,
                _START_COOL_OFF_S,
            )

    def _touch(self) -> None:
        """Note a start or a request, and stop the child once _IDLE_S passes without one."""

        loop = asyncio.get_running_loop()
        self._used = loop.time()
        if self._idle_timer is None:
            self._idle_timer = loop.call_later(_IDLE_S, self._idle)

    def _idle(self) -> None:
        self._idle_timer = None
        loop = self._loop
        if loop is None or self._process is None:
            return
        waited = loop.time() - self._used
        if self._lock is not None and self._lock.locked():
            self._idle_timer = loop.call_later(max(_IDLE_S - waited, _IDLE_RECHECK_S), self._idle)
            return
        if waited < _IDLE_S:
            self._idle_timer = loop.call_later(_IDLE_S - waited, self._idle)
            return
        self.stop()

    def _kill(self, process: asyncio.subprocess.Process) -> None:
        if self._process is process:
            self._process, self._ready, self._starting = None, False, None
        if _CHILDREN.get(process.pid) is process:
            del _CHILDREN[process.pid]
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            self._dying = {each: at for each, at in self._dying.items() if each.returncode is None}
            # The loop it was started on, which alone can wait for it, whichever loop kills
            # it: a close on a later loop stops a child an earlier one started.
            if self._loop is not None:
                self._dying[process] = self._loop

    def _replace(self) -> None:
        """Start another child at once after a render killed one, so the next document does
        not wait for the start."""

        if self._loop is _running_loop():
            self.start(renders=True)

    def stop(self) -> None:
        """Stop the child; the next start begins a new one, with its starts counted anew.

        A start this cuts off did not fail, and a server's lifespan, or a command's, ends
        with one: so the next loop may start the child again, up to the start limit. The
        lock and the flights stay: a request waiting for the child gets the next one.
        """

        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None
        # Taken first: the kill forgets the start, which must still be cancelled.
        starting = self._starting
        if self._process is not None:
            self._kill(self._process)
        if starting is not None:
            starting.cancel()
        self._process, self._ready, self._starting = None, False, None
        self._starts = 0

    async def aclose(self) -> None:
        """End this loop's renders, stop the child, and wait at most :data:`_REAP_S` for
        every child this loop stopped to exit, so none is reaped after the loop closes and
        none starts after it. A server's lifespan ends with this, and so must any other loop
        that used the worker: a loop that ends without it leaves ``asyncio.run`` to cancel a
        start still spawning (a render's :meth:`_replace` begins one as it answers) together
        with the task connecting its pipes, and on CPython 3.12 and 3.13 that start then
        waits for ever for pipes that were never connected (mb-4g7f). Cancelled here, alone,
        it finishes."""

        loop = _running_loop()
        if self._loop is loop:
            flights = [flight.task for flight in self._flights.values()]
            self._flights = {}
            for task in flights:
                task.cancel()
            if flights:
                await asyncio.gather(*flights, return_exceptions=True)
        starting = self._starting if self._loop is loop else None
        self.stop()
        dying = [each for each, at in self._dying.items() if at is loop and each.returncode is None]
        self._dying = {}
        self._tails = {}
        if starting is not None or dying:
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(_REAP_S):
                    if starting is not None:
                        # asyncio may have spawned the child without returning its Process
                        # yet. Let the cancelled start finish reaping it on this loop.
                        await asyncio.wait((starting,))
                    if dying:
                        await asyncio.gather(*(each.wait() for each in dying))

    async def prepare(
        self, *, old: bytes | None, new: bytes | None, patch: FilePatch, namespace: str
    ) -> PreparedMarkdownDiff:
        """*patch*'s projection: in the child when it is ready and free of inert renders,
        and in a thread otherwise. A failure that is not this input's doing is answered
        from the thread, so no caller keeps it as the input's answer.

        A thread projects within the input budgets beside ``MARKDOWN_DIFF_MAX_BYTES``,
        since nothing stops it, and no raw HTML (``_Limits`` in ``markdown_projection.py``).
        A pair past them, or that holds raw HTML, is the child's alone, which this waits
        for, on every build: there :data:`_PROJECTION_TIMEOUT_S` is its bound, whatever
        its size. Only where no child can be had does the thread's refusal stand."""

        from metabrowser.diff.markdown_projection import (
            MARKDOWN_DIFF_MAX_BYTES,
            prepare_markdown_diff,
            unavailable_markdown_diff,
        )

        def past_a_thread(prepared: PreparedMarkdownDiff) -> bool:
            # A budget's refusal names no cause; nesting's does, and the child's is the same.
            projection = prepared.projection
            return projection["status"] == "too_large" and "reason" not in projection

        return await self._projection(
            lambda: _frame(_encode(old, new, patch, namespace)),
            _decode,
            unavailable_markdown_diff,
            lambda: prepare_markdown_diff(old=old, new=new, patch=patch, namespace=namespace),
            heavy=len(old or b"") + len(new or b"") > MARKDOWN_DIFF_MAX_BYTES,
            past_a_thread=past_a_thread,
        )

    async def project_structured(
        self, *, old: bytes | None, new: bytes | None, fmt: Format
    ) -> StructuredDiffProjection:
        """A YAML or JSON file's projection
        (:func:`~metabrowser.diff.structured_projection.project_structured_diff`), where
        and as :meth:`prepare` runs a Markdown one."""

        from metabrowser.diff.structured_projection import (
            project_structured_diff,
            unavailable_structured_diff,
        )

        return await self._projection(
            lambda: _frame(_encode_structured(old, new, fmt)),
            _decode_structured,
            unavailable_structured_diff,
            lambda: project_structured_diff(old=old, new=new, fmt=fmt),
        )

    async def _projection[T](
        self,
        frame: Callable[[], bytes],
        decode: Callable[[dict[str, Any]], T],
        refused: Callable[
            [Literal["unsupported", "too_large"], Literal["deadline", "memory"] | None], T
        ],
        local: Callable[[], T],
        *,
        heavy: bool = False,
        past_a_thread: Callable[[T], bool] | None = None,
    ) -> T:
        """One projection, in the child or in a thread (:meth:`prepare`).

        *heavy* says the request is past what the event loop may frame itself, so a thread
        frames it. *past_a_thread* says whether a thread's answer refuses the input only
        for being past a thread's budgets; such an input waits for the child.
        """

        loop = asyncio.get_running_loop()
        if self._counted is not loop:
            # Each event loop counts its own: a command that runs one request per loop
            # in a process never starts a child.
            self._counted, self._requests = loop, 0
        self._requests += 1
        if self._requests >= 2:
            # A one-request command never pays for a child it would not use.
            self.start()
        lock = self._lock if self._loop is loop else None
        request: bytes | None = None
        if self._processes and self.ready and lock is not None and not lock.rendering:
            request = await asyncio.to_thread(frame) if heavy else frame()
            answered = await self._ask_child(lock, request, decode, refused, wait=False)
            if answered is not None:
                return answered.value
        answer = await asyncio.to_thread(local)
        if past_a_thread is None or not past_a_thread(answer):
            return answer
        # Past what a thread may project, and no child answered it above: a child is
        # started on any build, as for an inert render, and waited for, behind a render
        # that holds it. No child, or one that is not this input's doing, leaves the
        # thread's refusal.
        if request is None:
            request = await asyncio.to_thread(frame)
        if len(request) - 4 > _MAX_REQUEST_FRAME:
            return answer
        answered = await self._ask_child(self._bind(loop), request, decode, refused, wait=True)
        return answer if answered is None else answered.value

    async def _ask_child[T](
        self,
        lock: _ChildLock,
        request: bytes,
        decode: Callable[[dict[str, Any]], T],
        refused: Callable[
            [Literal["unsupported", "too_large"], Literal["deadline", "memory"] | None], T
        ],
        *,
        wait: bool,
    ) -> _Answered[T] | None:
        """The child's answer to one projection, or its refusal of an input it ran past
        the deadline on or died of twice; ``None`` when no child answered and that is not
        the input's doing. *wait* starts a child and waits for it when none is ready."""

        async with lock.hold("projection"):
            for attempt in (1, 2):
                if attempt == 1 and not wait:
                    process = self._process
                    if not self.ready or process is None:
                        # Stopped or replaced while this waited: not this input's doing.
                        break
                    if process.returncode is not None:
                        # Gone while idle, also not this input's doing; the next
                        # request starts another child.
                        self._kill(process)
                        break
                else:
                    process = await self._ready_child()
                    if process is None:
                        break
                outcome = await self._exchange_projection(process, request, decode)
                if isinstance(outcome, _Answered):
                    return outcome
                if outcome == "timeout":
                    self._kill(process)
                    return _Answered(refused("too_large", "deadline"))
                if self._process is not process:
                    # Stopped from here, by a new loop or the server's end.
                    break
                memory = outcome == "died" and await _rss_exit(process)
                self._kill(process)
                if memory:
                    return _Answered(refused("too_large", "memory"))
                if outcome == "died" and attempt == 2:
                    # Twice on two children: the input may be what stops it, so it is
                    # not run in this process.
                    return _Answered(refused("unsupported", None))
                # Gone before the request reached it, or dead on arrival or killed from
                # outside as easily as by this input: once more, on a fresh child.
        return None

    async def _exchange_projection[T](
        self,
        process: asyncio.subprocess.Process,
        frame: bytes,
        decode: Callable[[dict[str, Any]], T],
    ) -> _Answered[T] | Literal["unreached", "died", "timeout"]:
        assert process.stdin is not None and process.stdout is not None
        self._touch()
        try:
            # A child that does not take the whole request within the deadline is not
            # reading it, whatever the pair holds, as for a render: a frame longer than
            # the pipe holds would wait on such a child for ever, with the child's lock.
            async with asyncio.timeout(_PROJECTION_TIMEOUT_S):
                process.stdin.write(frame)
                await process.stdin.drain()
        except (TimeoutError, ConnectionError):
            return "unreached"
        except BaseException:
            # A request cut off part-way leaves the child's input out of step.
            self._kill(process)
            raise
        try:
            # Counted from when the child has the request, as a render's deadline is.
            answer = decode(await asyncio.wait_for(_read(process.stdout), _PROJECTION_TIMEOUT_S))
        except TimeoutError:
            return "timeout"
        except (ConnectionError, asyncio.IncompleteReadError, ValueError, KeyError, TypeError):
            return "died"
        except BaseException:
            # A cancelled exchange leaves an answer in the pipe for the next request.
            self._kill(process)
            raise
        self._touch()
        return _Answered(answer)

    def refusal(self, request: InertRender) -> InertRenderRefused | None:
        """The kept refusal of *request*'s document, if an earlier render was refused
        within :data:`_VERDICT_TTL_S`."""

        key = request.verdict_key
        kept = self._verdicts.get(key)
        if kept is None:
            return None
        code, kept_at = kept
        if time.monotonic() - kept_at >= _VERDICT_TTL_S:
            del self._verdicts[key]
            return None
        self._verdicts.move_to_end(key)
        return InertRenderRefused(code, remembered=True)

    async def render_inert(self, request: InertRender) -> dict[str, Any]:
        """*request* rendered and hardened in the child, within the deadline.

        Raises :class:`InertRenderRefused` when the render ran past the deadline, the
        child stopped while rendering it, the child could not start, or too many other
        documents are being rendered, and :class:`kpress_adapter.KPressInvalidRequestError`
        or :class:`kpress_adapter.KPressRenderError` as an in-process render would. A
        request identical to one in flight waits for that render rather than queueing
        another, so reloads of a slow document do not stack; a render no request waits for
        any more is cancelled.
        """

        refused = self.refusal(request)
        if refused is not None:
            raise refused
        loop = asyncio.get_running_loop()
        self._bind(loop)
        # Ahead of the lock, so the start overlaps the frame's encoding.
        self.start(renders=True)
        key = request.flight_key
        flight = self._flights.get(key)
        if flight is None:
            if sum(not each.task.done() for each in self._flights.values()) >= _MAX_RENDERS:
                LOG.warning(
                    "Refused rendering %r: %d other documents are being rendered",
                    _named(request),
                    _MAX_RENDERS,
                )
                raise InertRenderRefused("renderer_busy")
            flight = _Flight(loop.create_task(self._render_flight(request)))
            flights = self._flights
            flights[key] = flight

            def landed(_task: asyncio.Task[_Outcome], flight: _Flight = flight) -> None:
                if flights.get(key) is flight:
                    del flights[key]

            flight.task.add_done_callback(landed)
        flight.waiters += 1
        try:
            outcome = await asyncio.shield(flight.task)
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if flight.task.cancelled() and (current is None or current.cancelling() == 0):
                # The render was ended from here, by the server's close, not this request.
                raise InertRenderRefused("renderer_unavailable") from None
            raise
        finally:
            flight.waiters -= 1
            if flight.waiters == 0 and not flight.task.done():
                # Nobody waits for this render any more: it must not hold the child.
                flight.task.cancel()
                if self._flights.get(key) is flight:
                    del self._flights[key]
        if isinstance(outcome, _Failed):
            raise outcome.error()
        return outcome

    async def _ready_child(self) -> asyncio.subprocess.Process | None:
        """The ready child on this loop, started and waited for when there is none."""

        process = self._process
        if self.ready and process is not None and process.returncode is None:
            return process
        if process is not None and process.returncode is not None:
            # Gone while idle; one still starting is waited for, not replaced.
            self._kill(process)
        self.start(renders=True)
        try:
            async with asyncio.timeout(_START_WAIT_S):
                ready = await self.started()
        except TimeoutError:
            ready = False
        return self._process if ready else None

    async def _render_flight(self, request: InertRender) -> _Outcome:
        # The server's asset prefix, so the child names the assets this server serves.
        # With the GIL the thread still holds the interpreter while it encodes the front
        # matter, as the loader did while it parsed it: up to 47 ms of CPU for the largest
        # front matter the loader accepts (one-key mappings of an empty mapping, 2.8 MB of
        # frame; 2026-11-18, machine as for `flight_key`). Parsing front matter in the
        # child instead (bead mb-2y6a) would spare both.
        frame = await asyncio.to_thread(
            lambda: _frame(_encode_render(request, kpress_adapter.kpress_asset_url_prefix()))
        )
        lock = self._bind(asyncio.get_running_loop())
        async with lock.hold("render"):
            # Another request may have refused the same document while this one waited.
            refused = self.refusal(request)
            if refused is not None:
                return _Failed("refused", refused.code, remembered=True)
            for attempt in (1, 2):
                process = await self._ready_child()
                if process is None:
                    return _Failed("refused", "renderer_unavailable")
                began = time.monotonic()
                outcome = await self._exchange_render(process, frame)
                if isinstance(outcome, bytes):
                    return await self._accept(process, request, outcome)
                if outcome == "deadline":
                    self._kill(process)
                    return self._refuse(request, "render_deadline", began)
                if self._process is not process:
                    # Stopped from here, by a new loop or the server's end: not the
                    # document's doing, so nothing is kept.
                    return _Failed("refused", "renderer_unavailable")
                memory = outcome == "exited" and await _rss_exit(process)
                self._kill(process)
                said = await self._said(process)
                if memory:
                    # Peak RSS includes allocations retained from earlier requests.
                    # A later request can try a fresh child, with no retry in this flight.
                    LOG.warning("Markdown child reached its memory budget on %r", _named(request))
                    self._replace()
                    return _Failed("refused", "renderer_unavailable")
                if attempt == 1:
                    # Dead before the request reached it, or killed from outside, as easily
                    # as by this document: once more, on a fresh child.
                    LOG.info(
                        "The Markdown child stopped on %r; rendering it on a new child%s",
                        _named(request),
                        said,
                    )
                    continue
                if outcome == "exited":
                    # Twice on two children: the input may be what stopped it, so it is
                    # not rendered again.
                    return self._refuse(request, "renderer_exited", began, said)
            return _Failed("refused", "renderer_unavailable")

    async def _exchange_render(
        self, process: asyncio.subprocess.Process, frame: bytes
    ) -> bytes | Literal["deadline", "exited", "unreached"]:
        """One render's exchange: the answer's bytes, or how it ended without them."""

        assert process.stdin is not None and process.stdout is not None
        loop = asyncio.get_running_loop()
        self._touch()
        try:
            # A child that does not take the whole request within a deadline is not
            # reading it, whatever the document holds.
            async with asyncio.timeout(_RENDER_DEADLINE_S):
                process.stdin.write(frame)
                await process.stdin.drain()
        except (TimeoutError, ConnectionError):
            return "unreached"
        except BaseException:
            # An exchange cut off part-way leaves the child's pipes out of step.
            self._kill(process)
            raise
        # The deadline counts from when the child has the request, so a server whose own
        # loop was slow to write it does not spend the document's time.
        due = loop.time() + _RENDER_DEADLINE_S
        reading = asyncio.ensure_future(_read_body(process.stdout, _MAX_ANSWER_FRAME))
        try:
            try:
                async with asyncio.timeout_at(due):
                    return await asyncio.shield(reading)
            except TimeoutError:
                late = loop.time() - due
                if not reading.done():
                    # One turn of the loop: an answer already read is finished by it.
                    await asyncio.sleep(0)
                if not reading.done() and late > _LATE_S:
                    # The loop ran the deadline late, and the answer may be in the pipe.
                    await asyncio.wait({reading}, timeout=_ANSWER_GRACE_S)
                if not reading.done():
                    return "deadline"
                return reading.result()
        except (ConnectionError, asyncio.IncompleteReadError):
            return "exited"
        except BaseException:
            self._kill(process)
            raise
        finally:
            if not reading.done():
                reading.cancel()

    async def _accept(
        self, process: asyncio.subprocess.Process, request: InertRender, body: bytes
    ) -> _Outcome:
        """The child's answer, checked before it reaches a page."""

        self._touch()
        try:
            answer: object = await asyncio.to_thread(json.loads, body)
        except ValueError:
            answer = None
        if isinstance(answer, dict):
            answer = cast("dict[str, Any]", answer)
            error = answer.get("error")
            if error == "invalid":
                return _Failed("invalid", message=str(answer.get("message")))
            if error is not None:
                return _Failed("render", message=str(answer.get("message")))
            rendered = answer.get("rendered")
            if isinstance(rendered, dict):
                rendered = cast("dict[str, Any]", rendered)
                if isinstance(rendered.get("html"), str) and (
                    request.link_base is not None or rendered.get("inert") is True
                ):
                    return rendered
        # An answer of the wrong shape: the child is not trusted with another document.
        self._kill(process)
        return self._refuse(request, "renderer_exited", time.monotonic())

    def _refuse(
        self, request: InertRender, code: RefusalCode, began: float, said: str = ""
    ) -> _Failed:
        """Keep and log a refusal the child earned, and start its replacement."""

        self._remember(request, code)
        LOG.warning(
            "Refused rendering %r (%s) after %.2f s: %s%s",
            _named(request),
            request.identity,
            time.monotonic() - began,
            code,
            said,
        )
        self._replace()
        return _Failed("refused", code)

    async def _said(self, process: asyncio.subprocess.Process) -> str:
        """The end of what a child that has ended wrote to its standard error, for a log
        line, or ""."""

        tail = self._tails.pop(process, None)
        if tail is None:
            return ""
        text = await tail.text()
        return f"; its standard error ended {text!r}" if text else ""

    def _remember(self, request: InertRender, code: RefusalCode) -> None:
        self._verdicts[request.verdict_key] = (code, time.monotonic())
        self._verdicts.move_to_end(request.verdict_key)
        while len(self._verdicts) > _MAX_VERDICTS:
            self._verdicts.popitem(last=False)


@cache
def shared_worker() -> ProjectionWorker:
    """This process's Markdown child, which every route that renders untrusted text shares."""

    return ProjectionWorker()


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


async def _rss_exit(process: asyncio.subprocess.Process) -> bool:
    """EOF may arrive just before asyncio records the child's exit status."""
    if process.returncode is None and process.stdout is not None and process.stdout.at_eof():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(process.wait(), _REAP_S)
    return process.returncode == _RSS_EXIT


def _check_rss() -> None:
    if sys.platform not in {"darwin", "linux"}:
        return
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    used = peak if sys.platform == "darwin" else peak * 1024
    if used > _RSS_BYTES:
        os._exit(_RSS_EXIT)


def _exit_with_parent(parent: int, watching: threading.Event) -> None:
    """End this child once the server that started it has gone, even mid-render."""

    while True:
        if watching.wait(_PARENT_POLL_S):
            _check_rss()
            time.sleep(_RSS_POLL_S)
        if os.getppid() != parent:
            os._exit(0)


def main() -> None:
    watching = threading.Event()
    threading.Thread(
        target=_exit_with_parent, args=(os.getppid(), watching), name="parent-watch", daemon=True
    ).start()
    # The protocol owns the original standard output; anything a library prints goes to
    # standard error instead of into a frame.
    sink = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    serve(sys.stdin.buffer, sink, watching=watching)


if __name__ == "__main__":
    main()
