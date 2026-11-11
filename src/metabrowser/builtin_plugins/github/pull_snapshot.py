"""Read one admitted PR revision without switching the served repository subject.

``GET github/pull-snapshot`` serves a file from the exact base or head of a pull
request's comparison, as a standalone page on the app's origin. The pull envelope's
``snapshot_route`` names the comparison (:func:`.pull_route.snapshot_route`); ``side`` and
``path`` name the file, ``mode`` how it is shown (``document``, ``source``, ``image``, or
``download``), and ``offset`` a Source window.

A pair opens when it is the record's current comparison, or one of the pairs retained for
this reader and this store (:mod:`.pull_snapshot_cache`). Nothing else is ever read: no
fetch starts, the served pin and checkout stay as they are. A Markdown document renders
inert, and its relative links and supported images stay in the same Git tree. Every
response carries :func:`_headers`: a policy under which only the page's own three
preference scripts run (:func:`_page_scripts`).

Outcomes, each with a stable ``code``, answered as JSON for ``mode=image`` or an
``Accept: application/json`` request and as a short page otherwise:

- ``400 invalid_snapshot``: the address is malformed;
- ``410 snapshot_expired``: the pair is not admitted, so the link is gone;
- ``409 snapshot_unavailable``: admission could not be decided now (the record or the
  history could not be read); reloading may succeed. Not a 5xx: the plugin loader answers
  a data hook's server error with its own degraded warning;
- ``404 file_not_found`` / ``404 not_a_file``: nothing, or a folder, a symbolic link, or a
  submodule, is at that path in that revision;
- ``409 snapshot_objects_unavailable``: the current pair's objects cannot be read now;
- ``410 snapshot_objects_expired``: a retained earlier pair's commit has left the store;
- ``413 download_too_large``, ``415 unsupported_image``, ``416 invalid_offset``.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import re
import threading
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import cache
from html import escape
from pathlib import Path, PurePosixPath
from typing import Final, Literal, cast
from urllib.parse import quote, unquote_to_bytes, urlencode, urlsplit
from weakref import WeakKeyDictionary

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from metabrowser import kpress_adapter
from metabrowser.builtin_plugins.github.pull_record import PullRecord, read_pull_record
from metabrowser.builtin_plugins.github.pull_route import (
    PullRequestError,
    pull_host,
    requested_number,
    snapshot_route,
)
from metabrowser.builtin_plugins.github.pull_snapshot_cache import read_snapshot_bindings
from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.paths import source_pull_record, source_pull_snapshots
from metabrowser.cache.repository_store import open_revision
from metabrowser.content_sniff import SNIFF_PREFIX_BYTES, ContentClass, classify_prefix
from metabrowser.file_extensions import BROWSER_TEXT_EXTS
from metabrowser.git.process import GitError, repository_store_target
from metabrowser.git.tree_source import (
    GitObjectUnavailableError,
    GitPath,
    GitTreeSource,
)
from metabrowser.git.wire import is_full_revision
from metabrowser.http_caching import store_tag
from metabrowser.inert_html import fragment_link, kpress_prose
from metabrowser.invisible_chars import display_segment
from metabrowser.loading_cache import LoadingCache
from metabrowser.settings import TEXT_PREVIEW_CHUNK_BYTES
from metabrowser.view_routes import format_pull_href

_MARKDOWN: Final = frozenset({".md", ".markdown", ".mdown", ".mkd"})
# What an `<img>` on this page shows. The formats the browser decodes as pictures only:
# an SVG is a document, so it is offered as a link to its own page instead.
_IMAGE_TYPES: Final = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
}
# The largest Markdown file rendered as a document; a larger one opens as Source. A pull
# request's author writes it, so _DOCUMENT_WORK_MS below bounds what its render costs;
# this cap bounds the document the estimate reads and the page it makes. Review B of #347
# measured 16.99 s for a run of `[` at the earlier 256 KiB cap. The in-app pinned
# viewer renders larger files: its Markdown is the served repository's.
_DOCUMENT_BYTES: Final = 64 * 1024
# The whole document's render work a page may spend, as an estimate in milliseconds; a
# document estimated above it opens as Source. Measured 2026-11-11 with `_render_markdown`
# on one thread, three adjacent runs per shape with the fastest kept, load average 1.9 to
# 4.7: ordinary prose costs 0.5 µs a byte (24 ms at 64 KiB), but what the renderer spends
# grows with constructs a pull request's author can repeat, linearly in all of them but
# task lists, and splitting the text into paragraphs does not lower it. So the estimate
# charges each construct the most it was measured to cost, over the whole document:
# - per `[` whose next bracket on its line is not a `]`, 280 µs (followed by inline
#   content: `[*a*a` took 1.8 s for 6,554, as much with one `]` at the end, and `[<a`
#   168 µs each);
# - per `[` its line closes before another opens, 60 µs (a bare run 60 µs each,
#   `[*a*a]` 44 µs, a line of prose with a link 0.1 ms);
# - per `$`, 90 µs (inline math, 2.7 s for 32,768);
# - per `|`, 40 µs (a table, 1.2 to 1.3 s for 32,768 at any width);
# - per line that starts a block (a heading, list item, quote, table row, setext rule, or
#   container), 55 µs (16,384 headings 0.73 s, list items 0.88 s);
# - per line, 26 µs more (64 KiB of one-character paragraphs took 0.75 s, of lines that
#   end in a backslash 0.55 s);
# - per other inline delimiter, 20 µs (`*a` runs 0.48 s, autolinks 0.29 s, code spans
#   0.35 s).
# Fenced code renders as escaped plain text (`_render_markdown`) and is charged as the
# text it is. Highlighting it cost what no estimate over the text bounds, for classes
# the inert page then dropped: review G found a 1.6 KB `console` line that took 12 s, and
# 48 KB of `devicetree` that took 79 s.
# Task-list items cost more than linearly (1,024 took 0.19 s, 2,048 0.55 s, 8,192 6.4 s),
# so at most _TASK_ITEMS are admitted, behind any container, each charged 190 µs.
# Re-measured the same day for review G at load average 12 to 20, where 64 KiB of prose
# took 28 to 30 ms, over about 200 shapes and mixes each grown to the bound: the worst
# admitted render is 417 ms (lines that end in a backslash), then 415 ms (the same mixed
# with inline math), 410 ms (a wide table), and 406 ms (inline math). Scaled to the quiet
# run's prose, the worst is about 335 to 350 ms. One fence of any language reviews F and
# G timed renders in 4 to 10 ms at the bound, and the most fences, short ones one after
# another, in 129 ms. Of this repository's 346 Markdown files up to 64 KiB, the 64
# under node_modules, and 441 from nine other repositories, none opens as Source. Before,
# 16,384 `[` admitted a 64 KiB task list that took 6.4 s, and before reviews F and G
# admitted documents took up to 1.2 s and highlighted fences 79 s. The estimate covers
# the constructs measured; it is not a deadline, which only a renderer that can be
# stopped could give.
_DOCUMENT_WORK_MS: Final = 400
_TASK_ITEMS: Final = 1024
_UNPAIRED_OPENER_US: Final = 280
_PAIRED_OPENER_US: Final = 60
_HEAVY_US: Final = ((b"$", 90), (b"|", 40))
_DELIMITERS: Final = b"*_`~<>!]&:^=+{}"
_DELIMITER_US: Final = 20
_BLOCK_LINE_US: Final = 55
_LINE_US: Final = 26
_TASK_ITEM_US: Final = 190
_BYTE_US: Final = 0.5
_BLOCK_LINE: Final = re.compile(rb"^[ \t]*(?:[#>|=+*:-]|[0-9]+[.)])", re.MULTILINE)
# A checkbox after any container prefix: quote markers, list markers, or neither, for a
# list item whose first line is blank. KPress renders a task in each; a checkbox that
# starts a line of a paragraph is counted too, which only overcounts.
_TASK_ITEM: Final = re.compile(
    rb"^(?:[ \t>]*+(?:[-*+]|[0-9]{1,9}[.)])[ \t]++)*+[ \t>]*+\[[ xX]\]", re.MULTILINE
)
# A `[` whose line holds a `]` before any other bracket. The lookahead stops at the next
# bracket, so each scan ends where the next begins, and the whole count is linear.
_PAIRED_OPENER: Final = re.compile(rb"\[(?=[^\[\]\n]*\])")
# Full-file renders at once in one server: each holds the interpreter for up to the bound
# above, so a second would only slow both and every other request. A request finds one
# running and waits for it, rather than opening as Source.
_DOCUMENT_RENDERS: Final = 1
# Rendered pages kept per event loop, so a reload or Back does not repeat the work. KPress
# keeps its own render by path and object ID, but the hardening after it ran again: 25 to
# 87 ms per reload of a document at the bound, measured 2026-11-11 with the shapes above
# (load average near 16). The largest admitted page measured 1.1 MB of HTML (links, each
# rewritten to this route), so eight are at most about 9 MB.
_DOCUMENT_PAGES: Final = 8
# The images one document keeps; the rest become links to their own pages. Each kept image
# is one request to this route, and a browser requests every unsized lazy image of a page
# at once (review B of #347 counted 18,216 of 18,216 in headless Chrome). Measured
# 2026-11-11 with the in-process client on a cached pull request, 40 requests, three
# adjacent rounds, load average 4.3 to 4.8: an image request took 18 to 20 ms with
# admission and the revision's tree remembered, against 41 to 42 ms with neither, when no
# other source holds the store's Git readers (a checkout's store: each request starts one),
# and 1.3 to 1.8 ms when one does (a mirror serving that store). 64 images are therefore
# about 1.2 s of one worker's time per page on a checkout, 0.1 s on a mirror.
_DOCUMENT_IMAGES: Final = 64
# A Source window, as the in-app Source view's first chunk, whose cost the shell measured
# (settings.TEXT_PREVIEW_CHUNK_BYTES); this page draws plain text, which costs less.
_SOURCE_BYTES: Final = TEXT_PREVIEW_CHUNK_BYTES
type ViewMode = Literal["document", "source", "image", "download"]
type Admission = Literal["current", "retained", "refused", "unknown"]


@cache
def _page_scripts() -> tuple[str, ...]:
    # The shell's own first-paint preference scripts and the width default they read, so
    # this page paints in the reader's theme, fonts, and reading width. Imported late: the
    # server imports every plugin.
    from metabrowser.server import page_preference_scripts

    return page_preference_scripts()


@cache
def _headers() -> dict[str, str]:
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"
        for script in _page_scripts()
    )
    return {
        "Cache-Control": "no-store",
        "Content-Security-Policy": (
            f"default-src 'none'; script-src {hashes}; style-src 'self'; font-src 'self'; "
            "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        ),
        "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff",
    }


@dataclass(frozen=True, slots=True)
class Snapshot:
    number: int
    base: str
    head: str
    store: str
    side: Literal["base", "head"]

    @property
    def commit(self) -> str:
        return self.base if self.side == "base" else self.head

    def href(self, path: GitPath, mode: ViewMode = "document", offset: int = 0) -> str:
        query = urlencode(
            {
                "side": self.side,
                "path": path.to_wire(),
                "mode": mode,
                **({"offset": str(offset)} if offset else {}),
            }
        )
        return f"{snapshot_route(self.number, self.base, self.head, store=self.store)}&{query}"

    def reference(self, source: GitPath, href: str, image: bool) -> str | None:
        """Rewrite an already sanitized, local reference into this immutable tree.

        ``None`` drops it: a reference that leaves the tree, a folder's (written with a
        trailing ``/``; this route shows files), or an image in a format
        :data:`_IMAGE_TYPES` does not name.
        """
        try:
            url = urlsplit(href)
        except ValueError:
            return None
        if url.scheme or url.netloc:
            return None
        if not url.path:
            if image:
                return None
            return "#" + url.fragment if url.fragment else self.href(source)
        if url.path.endswith("/"):
            return None
        segments = [] if url.path.startswith("/") else list(source.parent().segments)
        for spelling in url.path.split("/"):
            name = unquote_to_bytes(spelling)
            if name in {b"", b"."}:
                continue
            if name == b"..":
                if not segments:
                    return None
                segments.pop()
            elif b"/" in name or b"\x00" in name:
                return None
            else:
                segments.append(name)
        if not segments:
            return None
        path = GitPath(tuple(segments))
        if image and _extension(path) not in _IMAGE_TYPES:
            return None
        target = self.href(path, "image" if image else "document")
        if url.fragment and not image:
            target += fragment_link("#" + quote(url.fragment, safe="-%._~"))
        return target


def _extension(path: GitPath) -> str:
    return PurePosixPath(display_segment(path.segments[-1])).suffix.lower()


# ── Admission ───────────────────────────────────────────────────


def _file_stamp(path: Path) -> tuple[int, int, int] | None:
    try:
        status = os.lstat(path)
    except FileNotFoundError:
        return None
    return status.st_ino, status.st_mtime_ns, status.st_size


# Decisions for the files they were read from: both are replaced atomically, so an
# unchanged inode, time, and size is an unchanged file. A page's images each ask again,
# and this answers them from two `lstat` calls instead of a record read and validation.
_ADMITTED: OrderedDict[tuple[object, ...], Admission] = OrderedDict()
_ADMITTED_LOCK: Final = threading.Lock()
_MAX_ADMITTED: Final = 256


def _admission(
    published: PublishedSource, snapshot: Snapshot, observed_reader: str | None
) -> Admission:
    """Whether *snapshot*'s pair opens: the record's own, a retained one, or neither.

    ``unknown`` when the record or the history cannot be read now. Blocking.
    """
    home, slug, number = published.home, published.slug, snapshot.number
    try:
        stamps = (
            _file_stamp(home / source_pull_record(slug, number)),
            _file_stamp(home / source_pull_snapshots(slug, number)),
        )
    except OSError:
        stamps = None
    key = (
        str(home),
        slug,
        number,
        published.store_id,
        published.source.normalized,
        observed_reader,
        snapshot.base,
        snapshot.head,
        stamps,
    )
    if stamps is not None:
        with _ADMITTED_LOCK:
            known = _ADMITTED.get(key)
            if known is not None:
                _ADMITTED.move_to_end(key)
                return known
    verdict = _decide(published, snapshot, observed_reader)
    if stamps is not None and verdict != "unknown":
        with _ADMITTED_LOCK:
            _ADMITTED[key] = verdict
            while len(_ADMITTED) > _MAX_ADMITTED:
                _ADMITTED.popitem(last=False)
    return verdict


def _decide(
    published: PublishedSource, snapshot: Snapshot, observed_reader: str | None
) -> Admission:
    record = read_pull_record(published.home, published.slug, snapshot.number, shared="refuse")
    if record in ("unreadable", "schema_mismatch"):
        return "unknown"
    if (
        not isinstance(record, PullRecord)
        or record.source.casefold() != published.source.normalized.casefold()
    ):
        return "refused"
    if observed_reader is not None and observed_reader != record.reader:
        return "refused"
    pair = (snapshot.base, snapshot.head)
    comparison = record.comparison
    if comparison is not None and pair == (comparison.base, comparison.head):
        return "current"
    bindings = read_snapshot_bindings(published.home, published.slug, snapshot.number)
    if bindings is None:
        return "unknown"
    retained = any(
        binding.store == published.store_id
        and binding.reader == record.reader
        and pair == (binding.base, binding.head)
        for binding in bindings
    )
    return "retained" if retained else "refused"


async def admitted_snapshot(
    request: Request, snapshot: Snapshot
) -> tuple[PublishedSource | None, Admission]:
    """Find the current source and authorize this exact pair without starting a fetch."""
    from metabrowser.builtin_plugins.github.checkout import ensure_resolved

    await ensure_resolved(request.app)
    host = pull_host(request.app)
    published = host.pulls.published if host is not None else None
    if (
        host is None
        or not isinstance(published, PublishedSource)
        or snapshot.store != store_tag(published.git_dir)
    ):
        return None, "refused"
    reader = host.pulls.observed_reader
    allowed = await asyncio.to_thread(_admission, published, snapshot, reader)
    # The source and reader the decision was made for must still be the server's.
    if host.pulls.published is not published or host.pulls.observed_reader != reader:
        return None, "refused"
    if allowed in ("refused", "unknown"):
        return None, allowed
    return published, allowed


# ── Revisions ───────────────────────────────────────────────────

# The root tree of each commit opened here: a full commit ID names one tree forever, so a
# later request reads it without the two Git processes that resolving it costs. A commit
# that later leaves the store fails on its first read, as an unopened one would.
_TREES: OrderedDict[tuple[str, str], str] = OrderedDict()
_MAX_TREES: Final = 64


async def _open_tree(published: PublishedSource, commit: str) -> GitTreeSource:
    key = (str(published.git_dir), commit)
    tree = _TREES.get(key)
    if tree is not None:
        _TREES.move_to_end(key)
        return GitTreeSource(
            target=repository_store_target(git_dir=published.git_dir), root_tree_oid=tree
        )
    subject = await open_revision(
        home=published.home,
        store_key=published.store_key,
        commit_oid=commit,
        store_identity=published.store_id,
    )
    _TREES[key] = subject.tree_oid
    while len(_TREES) > _MAX_TREES:
        _TREES.popitem(last=False)
    return subject.tree_source


# ── Pages ───────────────────────────────────────────────────────


def _error(request: Request, code: str, message: str, status: int) -> Response:
    if request.query_params.get("mode") == "image" or "application/json" in request.headers.get(
        "accept", ""
    ):
        return JSONResponse({"code": code, "message": message}, status_code=status)
    return HTMLResponse(
        "<!doctype html><html lang=en><meta charset=utf-8><title>File unavailable</title>"
        f"<main><h1>File unavailable</h1><p>{escape(message)}</p></main></html>",
        status_code=status,
    )


def _render_markdown(body: bytes, path: GitPath, oid: str, snapshot: Snapshot) -> str:
    rendered = kpress_adapter.render_kpress_view(
        source_text=body.decode("utf-8", "replace"),
        source_path=path.to_wire(),
        kind="markdown",
        view="document",
        ext=".md",
        mtime_hash=oid,
        size=len(body),
        include_toc="off",
        # Its author is untrusted and highlighting unbounded (`kpress_adapter`), and the
        # inert page drops the highlighting's classes anyway.
        plain_code=True,
    )
    images = 0

    def rewrite(href: str, image: bool) -> str | None:
        nonlocal images
        if image and images >= _DOCUMENT_IMAGES:
            return None
        target = snapshot.reference(path, href, image)
        if image and target is not None:
            images += 1
        return target

    # The prose content the in-app inert render builds from the same HTML (kpressProse):
    # KPress's wrappers out, and its code and table classes back, by element.
    return kpress_prose(str(kpress_adapter.inert_render(rendered, rewrite_local=rewrite)["html"]))


def _document_work_ms(body: bytes) -> float:
    """The render work *body* may cost, at the most each construct was measured to cost.

    Infinite past :data:`_TASK_ITEMS` task-list items, whose cost grows faster than their
    count. Blocking and linear in *body*; run it off the event loop with the render.
    """
    # Every line ending is one, as the renderer reads it.
    body = body.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    tasks = len(_TASK_ITEM.findall(body))
    if tasks > _TASK_ITEMS:
        return float("inf")
    work = _BYTE_US * len(body) + _TASK_ITEM_US * tasks
    paired = len(_PAIRED_OPENER.findall(body))
    work += _PAIRED_OPENER_US * paired + _UNPAIRED_OPENER_US * (body.count(b"[") - paired)
    work += sum(cost * body.count(char) for char, cost in _HEAVY_US)
    work += _DELIMITER_US * sum(body.count(bytes((char,))) for char in _DELIMITERS)
    work += _BLOCK_LINE_US * len(_BLOCK_LINE.findall(body))
    work += _LINE_US * body.count(b"\n")
    return work / 1000


def _render_document(body: bytes, path: GitPath, oid: str, snapshot: Snapshot) -> str | None:
    """The inert document, or ``None`` when its work is over the bound or it cannot render."""
    if _document_work_ms(body) > _DOCUMENT_WORK_MS:
        return None
    try:
        return _render_markdown(body, path, oid, snapshot)
    except (kpress_adapter.KPressRenderError, kpress_adapter.KPressInvalidRequestError):
        return None


@dataclass(eq=False, slots=True)
class _Documents:
    """One event loop's document renders: one load per document, at most a few at once."""

    loads: LoadingCache[tuple[Snapshot, GitPath, str], str | None]
    renders: asyncio.Semaphore


# Per event loop, since a semaphore belongs to the loop that first waits on it.
_DOCUMENTS: WeakKeyDictionary[asyncio.AbstractEventLoop, _Documents] = WeakKeyDictionary()


async def _document(
    snapshot: Snapshot, path: GitPath, oid: str, read: Callable[[], Awaitable[bytes]]
) -> str | None:
    """The document at *oid*, rendered once however many requests ask, a free render waited for.

    The last :data:`_DOCUMENT_PAGES` pages are kept, the refusals among them, and a kept page
    is answered without reading the blob. Otherwise each request reads its own blob with
    *read* first: a load shared with another request must not use a tree that request
    closes when it ends.
    """
    loop = asyncio.get_running_loop()
    documents = _DOCUMENTS.get(loop)
    if documents is None:
        documents = _DOCUMENTS[loop] = _Documents(
            LoadingCache(max_values=_DOCUMENT_PAGES), asyncio.Semaphore(_DOCUMENT_RENDERS)
        )
    key = (snapshot, path, oid)
    kept = documents.loads.kept(key)
    if kept is not None:
        return kept[0]
    renders = documents.renders
    body = await read()

    async def load() -> str | None:
        async with renders:
            return await asyncio.to_thread(_render_document, body, path, oid, snapshot)

    return await documents.loads.get(key, load)


def _page(
    snapshot: Snapshot,
    path: GitPath,
    content: str,
    *,
    markdown: bool,
    document: bool,
    offset: int = 0,
    next_offset: int | None = None,
) -> HTMLResponse:
    name = "/".join(display_segment(part) for part in path.segments)
    links = [
        f'<a href="{escape(format_pull_href(snapshot.number, "files"))}">Pull request #{snapshot.number} Changes</a>'
    ]
    if markdown:
        for mode in ("document", "source"):
            active = (mode == "document") == document
            current = ' aria-current="page"' if active else ""
            href = snapshot.href(path, cast("ViewMode", mode))
            links.append(f'<a href="{escape(href)}"{current}>{mode.title()}</a>')
    if offset:
        previous = max(0, offset - _SOURCE_BYTES)
        links.append(
            f'<a href="{escape(snapshot.href(path, "source", previous))}">Previous bytes</a>'
        )
    if next_offset is not None:
        links.append(
            f'<a href="{escape(snapshot.href(path, "source", next_offset))}">Next bytes</a>'
        )
    styles = ""
    if document:
        # The frame the in-app inert render puts around the same prose
        # (builtin_plugins/markdown/inert-render.js), whose content `_render_markdown`
        # already built as its `kpressProse` does: the host class bridges the reader's width
        # (`--doc-measure`) into KPress's measure, and KPress's prose classes carry the
        # reading font (`--kpress-host-font-prose`). The page writes every class; the
        # document's own were removed with the rest of its attributes. The in-app render's
        # own table of contents and link enhancer are not here.
        content = (
            '<div class="metabrowser-kpress-host"><article class="kpress kpress-doc kpress-inert"'
            ' data-kpress-card="on"><div class="kpress-doc-layout">'
            f'<div class="kpress-prose kpress-long-text">{content}</div></div></article></div>'
        )
        for asset in kpress_adapter.document_stylesheets().get("assets", []):
            href = asset.get("public_url")
            if isinstance(href, str) and href.startswith("/kpress-static/"):
                styles += f'<link rel="stylesheet" href="{escape(href)}">'
    scripts = "".join(f"<script>{script}</script>" for script in _page_scripts())
    return HTMLResponse(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        f"<title>{escape(name)} at {snapshot.commit[:12]}</title>{scripts}"
        '<link rel="stylesheet" href="/static/styles.css">'
        '<link rel="stylesheet" href="/plugin-static/github/pull-snapshot.css">'
        f'{styles}<body class="pull-snapshot-page"><main class="pull-snapshot"><header><nav aria-label="Revision file">'
        f'{" ".join(links)}</nav><h1 class="page-heading">{escape(name)}</h1><code>{snapshot.commit}</code></header>'
        f'<article class="pull-snapshot-content">{content}</article></main></body></html>'
    )


def _attachment(path: GitPath) -> str:
    """A ``Content-Disposition`` that saves the file under its own name (RFC 6266)."""
    name = display_segment(path.segments[-1])
    fallback = "".join(
        character if " " <= character <= "~" and character not in '"\\' else "_"
        for character in name
    )
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


def _source_window(body: bytes, *, last: bool) -> bytes:
    """*body* cut to end on a line, or else a character, unless it is the file's end."""
    if last:
        return body
    newline = body.rfind(b"\n", len(body) // 2)
    if newline >= 0:
        return body[: newline + 1]
    # The last byte that starts a character, and whether its whole sequence fits.
    for start in range(len(body) - 1, max(-1, len(body) - 5), -1):
        byte = body[start]
        if byte & 0xC0 != 0x80:
            width = 1 if byte < 0x80 else 2 if byte < 0xE0 else 3 if byte < 0xF0 else 4
            return body if start + width <= len(body) or start == 0 else body[:start]
    return body


def _character_start(prefix: bytes) -> int:
    """How many trailing bytes of *prefix* belong to the character that starts the window."""
    back = 0
    while back < len(prefix) and back < 3 and prefix[len(prefix) - 1 - back] & 0xC0 == 0x80:
        back += 1
    if back < len(prefix) and prefix[len(prefix) - 1 - back] >= 0xC0:
        return back + 1
    return 0


async def _source(
    snapshot: Snapshot,
    path: GitPath,
    tree: GitTreeSource,
    oid: str,
    size: int,
    offset: int,
    *,
    markdown: bool,
) -> HTMLResponse:
    """One Source window, every window read from a character's first byte."""
    preview_size = min(size, tree.max_blob_bytes)
    reach = min(3, offset)
    body, _ = await tree.read_blob_window(
        oid, offset=offset - reach, max_bytes=min(_SOURCE_BYTES, preview_size - offset) + reach
    )
    back = _character_start(body[:reach]) if len(body) > reach and body[reach] & 0xC0 == 0x80 else 0
    start = offset - back
    window = body[reach - back :]
    window = _source_window(window, last=start + len(window) >= preview_size)
    end = start + len(window)
    notice = ""
    if end >= preview_size and preview_size < size:
        notice = (
            f"<p>This preview ends at {preview_size:,} of {size:,} bytes, the limit for a"
            " revision file.</p>"
        )
    return _page(
        snapshot,
        path,
        f"<pre><code>{escape(window.decode('utf-8', 'replace'))}</code></pre>{notice}",
        markdown=markdown,
        document=False,
        offset=start,
        next_offset=end if end < preview_size else None,
    )


async def pull_snapshot_handler(request: Request) -> Response:
    """Read a file or inert document asset only from the requested admitted side.

    Every response leaves through here, so each carries the page policy and no later
    return can forget it.
    """
    response = await _respond(request)
    response.headers.update(_headers())
    return response


async def _respond(request: Request) -> Response:
    params = request.query_params
    try:
        number = requested_number(params)
        base, head = params.get("left", ""), params.get("right", "")
        side = params.get("side", "")
        mode = params.get("mode", "document")
        raw_offset = params.get("offset", "0")
        if (
            not is_full_revision(base)
            or not is_full_revision(head)
            or side not in {"base", "head"}
            or mode not in {"document", "source", "image", "download"}
            or not raw_offset.isascii()
            or not raw_offset.isdecimal()
            or len(raw_offset) > 10
            or len(params.get("path", "")) > 8192
        ):
            raise ValueError
        path = GitPath.from_wire(params.get("path", ""))
        if not path.segments or any(part in {b".", b".."} for part in path.segments):
            raise ValueError
        offset = int(raw_offset)
    except (PullRequestError, ValueError):
        return _error(request, "invalid_snapshot", "This revision file address is invalid.", 400)
    snapshot = Snapshot(
        number, base, head, params.get("store", ""), cast('Literal["base", "head"]', side)
    )
    published, admission = await admitted_snapshot(request, snapshot)
    if admission == "unknown":
        return _error(
            request,
            "snapshot_unavailable",
            "This PR revision could not be checked just now. Reload the page to try again.",
            409,
        )
    if published is None:
        return _error(
            request,
            "snapshot_expired",
            "This PR revision is no longer available. Open Changes again for the current comparison.",
            410,
        )
    ext = _extension(path)
    try:
        tree = await _open_tree(published, snapshot.commit)
        try:
            return await _file(request, snapshot, path, tree, mode, ext, offset)
        finally:
            await tree.aclose()
    except GitObjectUnavailableError:
        if admission == "retained":
            return _error(
                request,
                "snapshot_objects_expired",
                "This earlier PR revision is no longer cached. Open Changes for the current comparison.",
                410,
            )
        return _error(
            request,
            "snapshot_objects_unavailable",
            "This revision’s Git objects are unavailable. Reopen Changes to retry.",
            409,
        )
    except GitError:
        return _error(
            request,
            "snapshot_objects_unavailable",
            "This revision’s Git objects are unavailable. Reopen Changes to retry.",
            409,
        )


async def _file(
    request: Request,
    snapshot: Snapshot,
    path: GitPath,
    tree: GitTreeSource,
    mode: str,
    ext: str,
    offset: int,
) -> Response:
    entry = await tree.resolve_path(path)
    if entry is None:
        return _error(request, "file_not_found", "This file is absent at this revision.", 404)
    if entry.mode not in {"100644", "100755"}:
        what = (
            "a folder"
            if entry.is_tree
            else "a symbolic link, which revision files do not follow"
            if entry.is_symlink
            else "a submodule"
        )
        return _error(request, "not_a_file", f"This path is {what} at this revision.", 404)
    size = entry.size if entry.size is not None else (await tree.object_info(entry.oid)).size
    if mode == "image":
        if ext not in _IMAGE_TYPES or size > tree.max_blob_bytes:
            return _error(request, "unsupported_image", "This image cannot be displayed.", 415)
        return Response(await tree.read_blob(path), media_type=_IMAGE_TYPES[ext])
    if mode == "download":
        if size > tree.max_blob_bytes:
            return _error(
                request, "download_too_large", "This file exceeds the download limit.", 413
            )
        return Response(
            await tree.read_blob(path),
            media_type="application/octet-stream",
            headers={"Content-Disposition": _attachment(path)},
        )
    if mode == "document" and ext in _IMAGE_TYPES and size <= tree.max_blob_bytes:
        src = escape(snapshot.href(path, "image"))
        name = escape(display_segment(path.segments[-1]))
        return _page(
            snapshot, path, f'<img src="{src}" alt="{name}">', markdown=False, document=False
        )
    markdown = ext in _MARKDOWN and size <= _DOCUMENT_BYTES
    if mode == "document" and markdown:
        document = await _document(snapshot, path, entry.oid, lambda: tree.read_blob(path))
        if document is not None:
            return _page(snapshot, path, document, markdown=True, document=True)
        # Its Source, with no Document link to come back to.
        markdown = False
    if offset and offset >= min(size, tree.max_blob_bytes):
        return _error(
            request, "invalid_offset", "This source window is outside the preview limit.", 416
        )
    # What a file is follows from its first bytes, whichever window is asked for.
    prefix, _ = await tree.read_blob_window(entry.oid, offset=0, max_bytes=SNIFF_PREFIX_BYTES)
    content = classify_prefix(prefix)
    if content is ContentClass.BINARY or (
        ext not in BROWSER_TEXT_EXTS and content is not ContentClass.TEXT and size
    ):
        download = escape(snapshot.href(path, "download"))
        link = f' <a href="{download}">Download file</a>' if size <= tree.max_blob_bytes else ""
        return _page(snapshot, path, f"<p>Binary file.{link}</p>", markdown=False, document=False)
    return await _source(snapshot, path, tree, entry.oid, size, offset, markdown=markdown)
