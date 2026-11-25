"""``GET github/pull-rendered-diff``: the Rendered view of one changed file of a comparison.

The envelope's ``rendered_route`` names the comparison; a page appends ``file``, the
manifest ID of the file. The pair passes the same admission check as the images its
Markdown shows (``GET github/pull-image``). A Markdown file answers ``markdown-diff-v1``
(:mod:`metabrowser.diff.markdown_projection`), and a YAML or JSON file
``structured-diff-v1`` (:mod:`metabrowser.diff.structured_projection`), the formats the
file view draws from data rather than as text. Anything else answers the Markdown
format's refusal, and the route itself refuses with its own code; a YAML or JSON file
the route refuses answers its own format's refusal. A refusal names its ``reason`` where
one says more than its status, and the page says it on the file's Rendered chip, which
it never hides. A page's request sent before the reader asks names ``prefetch=1``, which
also starts the projection process and waits for it, so the first screen of Changes is
computed in that process while the reader is still on Conversation.

A Markdown pair is read up to :data:`_MARKDOWN_PAIR_MAX_BYTES`, whatever a projection in
a thread may hold: past the thread's budgets the pair is the Markdown child's, whose
deadline bounds it (:meth:`ProjectionWorker.prepare`). A pair the child was stopped on is
refused for :data:`_STOPPED_TTL_S` and then asked again, and one no child could run is
not kept at all: neither is the pair's own answer, which the route keeps.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from functools import partial
from time import monotonic
from typing import TYPE_CHECKING, Any, Literal, cast

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from metabrowser.builtin_plugins.github.pull_route import PullRequestError, pull_host
from metabrowser.builtin_plugins.github.pull_snapshot import (
    Snapshot,
    admitted_snapshot,
    requested_snapshot,
)
from metabrowser.diff.adapters.base import DiffSourceError
from metabrowser.diff.adapters.git import GitDiffSource
from metabrowser.diff.format import (
    Availability,
    ChangeSetManifest,
    ContentRefKind,
    EntrySide,
    EntryType,
    FileChange,
    FilePatch,
)
from metabrowser.diff.markdown_projection import (
    MARKDOWN_DIFF_VERSION,
    MarkdownRefusal,
    bind_markdown_diff,
)
from metabrowser.diff.markdown_projection_worker import (
    MAX_STOPPED,
    STOPPED_TTL_S,
    ProjectionWorker,
    shared_worker,
)
from metabrowser.diff.structured_projection import (
    Format,
    structured_byte_budget,
    structured_format,
    unavailable_structured_diff,
)
from metabrowser.git.process import GitError, GitLocation, RepositoryStoreTarget
from metabrowser.git.tree_source import (
    GitBlobTooLargeError,
    GitPath,
    GitPathError,
    blob_logical_ext,
    held_store_readers,
    read_store_blob,
)
from metabrowser.git.wire import is_full_revision
from metabrowser.loading_cache import LoadingCache

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.diff.comparison_cache import ResolvedManifest
    from metabrowser.cache.acquire import PublishedSource

type Status = Literal["unsupported", "too_large"]
_NO_STORE = {"cache-control": "no-store"}
_MARKDOWN = frozenset({".md", ".markdown", ".mdown", ".mkd"})
# Both sides of a Markdown file together, which the route reads at most. It is not the
# projection's bound: past a thread's budgets (MARKDOWN_DIFF_MAX_BYTES and the bounds
# beside it) a pair is projected in the Markdown child, where a deadline stops it. It
# bounds what the server's own interpreter does with a pair, which nothing stops: framing
# the request, in a thread, and reading, binding and encoding the answer, on the event
# loop. Measured 2026-11-23 on an Apple M1 Pro (MacBookPro18,1), macOS 26.5.2, Python
# 3.14.7, KPress 0.3.9, as process CPU time, the least of two runs, at a load average of
# 355 to 450, where wall time measures the load: pairs made of this repository's tracked
# Markdown that projects, as one word changed in every 40th paragraph, as a new file,
# and as two different texts.
#
# | Pair, bytes         | Server, ms    | Of it framing, ms | Child, s     |
# | ---                 | ---           | ---               | ---          |
# | 266,809-275,731     | 3.3-10.2      | 1.2-6.5           | 0.34-0.36    |
# | 529,293-533,637     | 6.3-20.1      | 2.2-12.7          | 0.71-0.75    |
# | 1,063,137-1,080,454 | 12.0-43.9     | 4.2-28.3          | 1.32-1.53    |
# | 2,100,073-2,140,262 | 24.0-82.1     | 8.7-51.3          | 2.80-3.10    |
# | 4,200,274-4,412,112 | 51.6-165.9    | 21.4-106.8        | 5.80-7.26    |
#
# Both grow with the pair's bytes, and the server's with its patch lines too: a new file
# or a rewrite frames every line (19,294 lines at 1 MiB), an edit a few hundred. One MiB
# is the largest size measured that keeps the server's share inside the 50 ms the
# repository budgets for an unrelated request's delay
# (``inventory_engine/providers/python_inventory.py``), and leaves the child's deadline
# over six times its time. The largest Markdown pair in the pull request that showed the
# earlier 48 KiB bound for what it was, a 241,628-byte research document, is 483,256
# bytes (mb-rm40).
_MARKDOWN_PAIR_MAX_BYTES = 1024 * 1024
# Rendered blocks and front matter text the route sends at most. A pair at the read bound
# answered at most 1,333,821 bytes of HTML in the measurement above, a new file of
# 1,070,079 bytes, and the 434 real pairs of this repository's history at most 45,677.
# Bytes read do not bound it: each link into the snapshot is an address of about 400
# bytes, so 255 links made 110,840 bytes of a pair inside 48 KiB. Front matter counts
# too: a 30 KB `!!binary` value is 40 KB of base64 text (mb-8274 review B9). The page
# builds the blocks it draws, changed ones and the unchanged ones beside them, and a new
# file's are all changed: in headless Chrome a 1,426-node answer built in 1.6-1.7 ms
# with 4.3-4.6 ms of layout (review C of #349); what an answer at this cap costs a page
# has not been measured (mb-qq0c).
_MAX_HTML_BYTES = 2 * 1024 * 1024
# The encoded answers the route keeps, in bytes: four at _MAX_HTML_BYTES, and real ones
# are far smaller, since the 434 real pairs answer at most 120 KiB. A tree's answer was
# kept as Python objects, which a 120 KB list of 39,999 empty mappings made 2.9 MB
# (mb-8274 review B7); kept encoded, an answer weighs what is sent.
_MAX_KEPT_BYTES = 8 * 1024 * 1024
# How long the route refuses a pair the child was stopped on before it asks the child
# again, and how many such pairs it remembers: an inert render's own, for its reasons
# (``markdown_projection_worker.py``). A stopped pair cost the child its deadline, and one
# stopped at a moment of heavy load renders ten minutes later.
_STOPPED_TTL_S = STOPPED_TTL_S
_MAX_STOPPED = MAX_STOPPED
# The Markdown files one `git diff` hydrates when a reader reaches the first of them: the
# Source view's own run is a different request, so this route reads its patches itself.
# For this repository one file took 15.7 ± 1.9 ms and sixteen 20.0 ± 1.6 ms (hyperfine,
# 30 runs), so each later file of the batch answers without a subprocess.
_PATCH_BATCH = 16
# A later file joins the batch only when the manifest counts its changed lines and they
# are few enough for a pair the projection could answer: the 434 real pairs of at most
# 48 KiB change p50 14, p90 75 and at most 722 lines. Without this, fifteen 216 KB
# rewrites the route would refuse anyway were hydrated beside a 4-line file, which took
# 1.3 s instead of 18-55 ms and kept 102 MB (review E of #349).
_BATCH_FILE_LINES = 1_000
_BATCH_LINES = 2_000
# What the route keeps of hydrated patches, in patch lines: at most a few dozen pairs.
_KEPT_LINES = 20_000
# Loads that wait for the projection slot before more are refused (see _Slot).
_MAX_WAITING = 4


def _fallback(
    status: Status = "unsupported",
    rendered: Rendered = "markdown",
    reason: MarkdownRefusal | None = None,
) -> dict[str, Any]:
    """The route's refusal, in the format the file would have answered (review A10)."""

    if rendered != "markdown":
        return dict(unavailable_structured_diff(status))
    return {
        "version": MARKDOWN_DIFF_VERSION,
        "status": status,
        "blocks": [],
        "source_only": False,
        **({} if reason is None else {"reason": reason}),
    }


class _Unkept(Exception):
    """An answer the route gives and does not keep, since asking again may answer better:
    the Markdown child could not run a pair past a thread's budgets, or was stopped on it."""

    def __init__(self, body: bytes, *, stopped: bool) -> None:
        super().__init__("an answer that is not kept")
        self.body = body
        self.stopped = stopped


def _encoded(answer: dict[str, Any]) -> bytes:
    """*answer* as ``JSONResponse`` renders it, encoded once and kept so."""

    return json.dumps(
        answer, ensure_ascii=False, allow_nan=False, indent=None, separators=(",", ":")
    ).encode("utf-8")


class _Busy(Exception):
    """More loads wait for the projection slot than the route keeps waiting."""


class _Slot:
    """One load at a time per server; a few more wait their turn, and the rest are refused.

    Under the GIL a second projection thread doubled every other request's delay (35 to
    74-84 ms for eight wake-ups) and projected no more per second (37 in 1.5 s with one
    thread, 37-38 with two); the child process runs one projection at a time anyway. A
    page asks for one file at a time and keeps its request when the file scrolls away, so
    each open Changes tab holds at most one place; past four waiting, a load would wait
    four projections, and the page's own retry serves the reader better.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._waiting = 0

    async def run[T](self, load: Callable[[], Awaitable[T]]) -> T:
        if self._waiting >= _MAX_WAITING:
            raise _Busy
        self._waiting += 1
        try:
            await self._lock.acquire()
        finally:
            self._waiting -= 1
        try:
            return await load()
        finally:
            self._lock.release()


def projection_worker(state: Any) -> ProjectionWorker:
    """The server's Markdown child, which renders its untrusted documents too, or the
    worker a test put in its place before a request."""

    worker = getattr(state, "pull_rendered_diff_worker", None)
    return shared_worker() if worker is None else cast("ProjectionWorker", worker)


def _path(side: EntrySide) -> GitPath:
    raw = (
        base64.b64decode(side.path_b64, validate=True)
        if side.path_b64 is not None
        else side.path.encode()
    )
    return GitPath(tuple(raw.split(b"/")))


type Rendered = Literal["markdown"] | Format


def rendered_format(change: FileChange) -> Rendered | None:
    """The format both sides of a ready file render as, or ``None``.

    The guided-review route asks it too, of each file a step cites whole, so a step draws
    with the rendered layer exactly the files this route renders (``_step_references`` in
    ``guided_review.py``).
    """

    if change.availability is not Availability.ready or change.binary:
        return None
    sides = [side for side in (change.old, change.new) if side is not None]
    if not sides or not all(
        side.entry_type is EntryType.file and side.content.kind is ContentRefKind.git_object
        for side in sides
    ):
        return None
    formats = {
        "markdown" if ext in _MARKDOWN else structured_format(ext)
        for ext in (blob_logical_ext(_path(side)) for side in sides)
    }
    found = formats.pop() if len(formats) == 1 else None
    return cast("Rendered | None", found)


def _projectable(change: FileChange) -> bool:
    """A Markdown file the projection reads a patch for."""

    return rendered_format(change) == "markdown"


def _lines_of(patch: FilePatch) -> int:
    return sum(len(hunk.lines) for hunk in patch.hunks)


class _Patches:
    """Patches of projectable Markdown files, hydrated a few small ones per `git diff`."""

    def __init__(self) -> None:
        self._kept: OrderedDict[tuple[str, ...], FilePatch] = OrderedDict()
        self._lines = 0

    def _keep(self, key: tuple[str, ...], patch: FilePatch) -> None:
        if key in self._kept:
            return
        self._kept[key] = patch
        self._lines += _lines_of(patch)
        while self._lines > _KEPT_LINES and len(self._kept) > 1:
            _, dropped = self._kept.popitem(last=False)
            self._lines -= _lines_of(dropped)

    async def get(
        self,
        key: tuple[str, ...],
        source: GitDiffSource,
        comparison: Any,
        manifest: ChangeSetManifest,
        file_id: str,
    ) -> FilePatch | None:
        if (*key, file_id) in self._kept:
            self._kept.move_to_end((*key, file_id))
            return self._kept[(*key, file_id)]
        files = manifest.files
        at = next(index for index, change in enumerate(files) if change.id == file_id)
        # The small projectable files after this one in the manifest's order, as a reader
        # scrolls to them.
        batch, budget = [file_id], _BATCH_LINES
        for change in files[at + 1 :]:
            if len(batch) == _PATCH_BATCH:
                break
            changed = (
                None
                if change.additions is None or change.deletions is None
                else change.additions + change.deletions
            )
            if (
                changed is not None
                and changed <= min(_BATCH_FILE_LINES, budget)
                and _projectable(change)
                and (*key, change.id) not in self._kept
            ):
                batch.append(change.id)
                budget -= changed
        hydrated = await source.hydrate(comparison, batch, manifest=manifest)
        patches = dict(hydrated.patches)
        if file_id not in patches and len(batch) > 1:
            # Past one run's bound, a file that fits alone is asked for alone.
            alone = await source.hydrate(comparison, [file_id], manifest=manifest)
            patches.update(alone.patches)
        for each in batch:
            if each in patches:
                self._keep((*key, each), patches[each])
        return patches.get(file_id)


async def _project(
    published: PublishedSource,
    snapshot: Snapshot,
    file_id: str,
    namespace: str,
    state: Any,
    listed: Callable[[], Awaitable[ResolvedManifest]],
) -> dict[str, Any]:
    from metabrowser.kpress_adapter import document_stylesheets

    target = RepositoryStoreTarget(published.git_dir, published.object_format)
    source = GitDiffSource(GitLocation.revision(target, snapshot.head))
    comparison = await listed()
    resolved, manifest = comparison.resolved, comparison.manifest
    if resolved.left.id != snapshot.base or resolved.right.id != snapshot.head:
        return _fallback()
    change = next((entry for entry in manifest.files if entry.id == file_id), None)
    rendered = None if change is None else rendered_format(change)
    if change is None or rendered is None:
        return _fallback()

    async def blob(side: EntrySide | None, budget: int) -> bytes | None:
        if side is None:
            return None
        oid = side.content.oid
        assert oid is not None
        return await read_store_blob(target, oid, max_blob_bytes=budget)

    budget = (
        _MARKDOWN_PAIR_MAX_BYTES if rendered == "markdown" else structured_byte_budget(rendered)
    )
    try:
        # One cat-file process for both sides where nothing else holds the store's: with
        # none held, the two reads took p50 5.6-6.5 ms a file, most of a JSON file's
        # time, and 0.5-0.7 ms held (mb-8274 review C5).
        async with held_store_readers(target):
            old = await blob(change.old, budget)
            new = await blob(change.new, budget - len(old or b""))
    except GitBlobTooLargeError:
        return _fallback("too_large", rendered)
    if rendered != "markdown":
        # The tree compares parsed values, so it reads no patch, and shows no images.
        tree = dict(
            await projection_worker(state).project_structured(old=old, new=new, fmt=rendered)
        )
        if tree.get("reason") == "deadline":
            raise _Unkept(_encoded(tree), stopped=True)
        return tree
    patches = getattr(state, "pull_rendered_diff_patches", None)
    if patches is None:
        patches = state.pull_rendered_diff_patches = _Patches()
    patch = await cast("_Patches", patches).get(
        (published.store_id, snapshot.base, snapshot.head), source, resolved, manifest, file_id
    )
    if patch is None:
        return _fallback()
    if not patch.hunks:
        # A rename or a mode change: the content did not change, and the page says so.
        return _fallback(reason="no_changes")
    rewrite: Callable[[str, bool], str | None] | None = None
    if change.new is not None:
        path = _path(change.new)

        def head_reference(href: str, image: bool) -> str | None:
            return snapshot.reference(path, href, image)

        rewrite = head_reference

    prepared = await projection_worker(state).prepare(
        old=old, new=new, patch=patch, namespace=namespace
    )
    answered = prepared.projection
    if answered["status"] == "too_large" and answered.get("reason") in (None, "deadline"):
        # Not the pair's own answer: the child has no input budget, so this is a thread's
        # budget where no child could be had, or the child's deadline.
        raise _Unkept(_encoded(dict(answered)), stopped="reason" in answered)
    projection = bind_markdown_diff(prepared, rewrite)
    shown = sum(len(block["html"].encode()) for block in projection["blocks"])
    frontmatter = projection.get("frontmatter")
    if frontmatter is not None:
        shown += sum(
            len(entry["key"].encode()) + len(entry["text"].encode())
            for entry in frontmatter["entries"]
        )
    if shown > _MAX_HTML_BYTES:
        return _fallback("too_large")
    return {
        **projection,
        **(
            {"assets": await asyncio.to_thread(document_stylesheets)}
            if projection["status"] == "ready"
            else {}
        ),
    }


async def pull_rendered_diff_handler(request: Request) -> Response:
    from metabrowser.builtin_plugins.github.pull_list_route import served_repository
    from metabrowser.builtin_plugins.github.pull_manifest import shared_pull_manifest
    from metabrowser.builtin_plugins.github.pull_stack import combined, read_stack

    params = request.query_params
    try:
        number, scope = requested_snapshot(params)
    except PullRequestError:
        number, scope = None, "pull"
    base, head = params.get("left", ""), params.get("right", "")
    file_id = params.get("file", "")
    if (
        number is None
        or not is_full_revision(base)
        or not is_full_revision(head)
        or not file_id
        or len(file_id) > 128
    ):
        return JSONResponse({"code": "invalid_rendered_diff"}, status_code=400, headers=_NO_STORE)
    snapshot = Snapshot(number, base, head, params.get("store", ""), scope)
    published, admission = await admitted_snapshot(request, snapshot)
    if admission == "unknown":
        return JSONResponse({"code": "snapshot_unavailable"}, status_code=409, headers=_NO_STORE)
    if published is None:
        return JSONResponse({"code": "snapshot_expired"}, status_code=410, headers=_NO_STORE)

    state = request.app.state
    if params.get("prefetch") == "1":
        worker = projection_worker(state)
        worker.start()
        # No reader waits on a prefetch, so it waits for the child, where a projection
        # runs under its deadline (mb-8274 review C2); a reader's own request does not.
        await worker.settle()
    cache = getattr(state, "pull_rendered_diff_cache", None)
    if cache is None:
        cache = state.pull_rendered_diff_cache = LoadingCache[tuple[str, ...], bytes](
            max_values=32, max_weight=_MAX_KEPT_BYTES, weigh=len
        )
    cache = cast("LoadingCache[tuple[str, ...], bytes]", cache)
    slot = getattr(state, "pull_rendered_diff_slot", None)
    if slot is None:
        slot = state.pull_rendered_diff_slot = _Slot()
    slot = cast("_Slot", slot)
    listed: Callable[[], Awaitable[ResolvedManifest]] = partial(
        shared_pull_manifest, published, number, base, head
    )
    named = str(number)
    if scope == "stack":
        # The stack's own manifest, restricted to its layers' files, whose digest names it:
        # a pull request keeps the key, and so the rendered namespace, it had.
        host = pull_host(request.app)
        reader = host.pulls.observed_reader if host is not None else None
        pair = (await read_stack(served_repository(request.app), published, number, reader)).pair
        if pair is None or (pair.base, pair.head) != (base, head):
            return JSONResponse({"code": "snapshot_expired"}, status_code=410, headers=_NO_STORE)
        named = f"stack-{number}-{pair.digest}"

        async def restricted() -> ResolvedManifest:
            assert pair is not None
            return (await combined(published, pair)).manifest

        listed = restricted
    key = (published.store_id, snapshot.store, named, base, head, file_id)
    namespace = "diff-" + hashlib.sha256("\0".join(key).encode()).hexdigest()[:20]
    # The pairs the child was stopped on, each with when and with the refusal it answered.
    stopped = getattr(state, "pull_rendered_diff_stopped", None)
    if stopped is None:
        stopped = state.pull_rendered_diff_stopped = OrderedDict[
            tuple[str, ...], tuple[float, bytes]
        ]()
    stopped = cast("OrderedDict[tuple[str, ...], tuple[float, bytes]]", stopped)
    refused = stopped.get(key)
    if refused is not None:
        if monotonic() - refused[0] < _STOPPED_TTL_S:
            return Response(refused[1], media_type="application/json", headers=_NO_STORE)
        del stopped[key]

    async def load() -> bytes:
        return _encoded(await _project(published, snapshot, file_id, namespace, state, listed))

    try:
        body = await cache.get(key, lambda: slot.run(load))
    except _Unkept as answered:
        if answered.stopped:
            stopped[key] = (monotonic(), answered.body)
            stopped.move_to_end(key)
            while len(stopped) > _MAX_STOPPED:
                stopped.popitem(last=False)
        body = answered.body
    except _Busy:
        return JSONResponse({"code": "rendered_diff_busy"}, status_code=429, headers=_NO_STORE)
    except (DiffSourceError, GitError):
        return JSONResponse(
            {"code": "rendered_objects_unavailable"}, status_code=409, headers=_NO_STORE
        )
    except GitPathError:
        body = _encoded(_fallback())
    return Response(body, media_type="application/json", headers=_NO_STORE)
