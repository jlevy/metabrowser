"""Admit one revision pair of a pull request, and serve the images its rendered Markdown shows.

A pair, a comparison's base and head, opens when it is the record's current comparison,
or one of the pairs retained for this reader and this store (:mod:`.pull_snapshot_cache`).
Nothing else is ever read: no fetch starts, the served pin and checkout stay as they are.
``GET github/pull-rendered-diff`` (:mod:`.pull_rendered_diff`) and the image route here
both admit their pair this way.

An address may name ``stack=<n>`` in place of ``number``: a native stack's page asks for
its combined comparison's rendered documents and their images so. It opens the stack's
current pair, computed as the ``stack`` route computes it (:mod:`.pull_stack`), from its
members' records and their ancestry, and an earlier pair that route answered while it is
kept (:mod:`.pull_stack_retained`), since a stack's page keeps the comparison it drew.

``GET github/pull-image`` serves one image at the head of an admitted pair, for the
rendered Markdown of Changes: the pull envelope's ``image_route`` names the pair
(:func:`.pull_route.image_route`), and the rendered diff adds ``path``. A document link in
that Markdown is not this route's: it names the file's ``/view/`` address on the head,
which the page keeps only while it shows that head (:meth:`Snapshot.reference`).

Outcomes, each a JSON answer with a stable ``code``:

- ``400 invalid_image``: the address is malformed;
- ``410 snapshot_expired``: the pair is not admitted, so the link is gone;
- ``409 snapshot_unavailable``: admission could not be decided now (the record or the
  history could not be read); reloading may succeed. Not a 5xx: the plugin loader answers
  a data hook's server error with its own degraded warning;
- ``404 file_not_found`` / ``404 not_a_file``: nothing, or a folder, a symbolic link, or a
  submodule, is at that path in that revision;
- ``409 snapshot_objects_unavailable``: the current pair's objects cannot be read now;
- ``410 snapshot_objects_expired``: a retained earlier pair's commit has left the store;
- ``415 unsupported_image``: the file is not an image this route serves, or is too large.
"""

from __future__ import annotations

import asyncio
import os
import threading
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final, Literal
from urllib.parse import quote, unquote_to_bytes, urlencode, urlsplit

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from metabrowser.builtin_plugins.github.pull_record import PullRecord, read_pull_record
from metabrowser.builtin_plugins.github.pull_route import (
    IMAGE_ROUTE,
    NUMBER_REQUIRED,
    PullRequestError,
    image_route,
    pull_host,
    requested_number,
)
from metabrowser.builtin_plugins.github.pull_snapshot_cache import read_snapshot_bindings
from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.paths import source_pull_record, source_pull_snapshots
from metabrowser.cache.repository_store import open_revision
from metabrowser.git.process import GitError, repository_store_target
from metabrowser.git.tree_source import (
    GitObjectUnavailableError,
    GitPath,
    GitTreeSource,
)
from metabrowser.git.wire import is_full_revision
from metabrowser.http_caching import store_tag
from metabrowser.inert_html import fragment_link
from metabrowser.invisible_chars import display_segment
from metabrowser.view_routes import VIEW_ROUTE_PREFIX

if TYPE_CHECKING:
    from metabrowser.builtin_plugins.github.pull_stack import StackPair

# What an `<img>` in rendered Markdown shows. The formats the browser decodes as pictures
# only: an SVG is a document, so a reference to one is dropped.
_IMAGE_TYPES: Final = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
}
# Every answer is an image or a refusal, kept by nobody: an earlier pair's link can expire.
_HEADERS: Final = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
type Admission = Literal["current", "retained", "refused", "unknown"]


@dataclass(frozen=True, slots=True)
class Snapshot:
    """One revision pair of a pull request, or of a native stack, as a store's token names it."""

    number: int
    base: str
    head: str
    store: str
    scope: Literal["pull", "stack"] = "pull"

    def image_href(self, path: GitPath) -> str:
        """The image route's address of *path* at the head."""

        query = urlencode({"path": path.to_wire()})
        if self.scope == "stack":
            names = {"stack": self.number, "left": self.base, "right": self.head}
            return f"{IMAGE_ROUTE}?{urlencode({**names, 'store': self.store})}&{query}"
        return f"{image_route(self.number, self.base, self.head, store=self.store)}&{query}"

    def reference(self, source: GitPath, href: str, image: bool) -> str | None:
        """Rewrite an already sanitized, local reference of *source* into the head's tree.

        An image becomes its address on the image route. A link becomes the file's
        ``/view/`` address on the head, which is the same for every page: the page keeps it
        only while it shows the head, where that address opens this file, and makes it
        plain text otherwise. ``None`` drops it: a reference that leaves the tree, a
        folder's (written with a trailing ``/``), or an image in a format
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
            return "#" + url.fragment if url.fragment else VIEW_ROUTE_PREFIX + source.to_wire()
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
        if image:
            return self.image_href(path) if _extension(path) in _IMAGE_TYPES else None
        target = VIEW_ROUTE_PREFIX + path.to_wire()
        if url.fragment:
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
# unchanged inode, time, and size is an unchanged file. A rendered file's images each ask
# again, and this answers them from two `lstat` calls instead of a record read and
# validation.
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


def requested_snapshot(params: Mapping[str, str]) -> tuple[int, Literal["pull", "stack"]]:
    """The pull request a ``GET`` names by ``number``, or the stack by ``stack``: exactly one
    of the two, or :class:`PullRequestError`."""

    if "stack" in params:
        if "number" in params:
            raise PullRequestError(NUMBER_REQUIRED)
        return requested_number({"number": params["stack"]}), "stack"
    return requested_number(params), "pull"


async def _stack_admission(
    request: Request, published: PublishedSource, snapshot: Snapshot, reader: str | None
) -> tuple[Admission, StackPair | None]:
    from metabrowser.builtin_plugins.github.pull_list_route import served_repository
    from metabrowser.builtin_plugins.github.pull_stack import read_stack
    from metabrowser.builtin_plugins.github.pull_stack_retained import retained_stack_pair

    read = await read_stack(served_repository(request.app), published, snapshot.number, reader)
    if read.reason == "commits_unavailable":
        return "unknown", None
    pair = read.pair
    if pair is not None and (pair.base, pair.head) == (snapshot.base, snapshot.head):
        return "current", pair
    # A pair the stack has moved from stays admitted while the stack route keeps it, so a
    # page keeps drawing the comparison it drew (pull_stack_retained.py).
    retained = await asyncio.to_thread(
        retained_stack_pair, published, snapshot.number, reader, snapshot.base, snapshot.head, None
    )
    if retained == "unknown":
        return "unknown", None
    return ("retained", retained) if retained is not None else ("refused", None)


async def admitted_snapshot(
    request: Request, snapshot: Snapshot
) -> tuple[PublishedSource | None, Admission]:
    """Find the current source and authorize this exact pair without starting a fetch."""

    published, admission, _ = await admitted_pair(request, snapshot)
    return published, admission


async def admitted_pair(
    request: Request, snapshot: Snapshot
) -> tuple[PublishedSource | None, Admission, StackPair | None]:
    """:func:`admitted_snapshot`, and for a stack's snapshot the pair that admitted it: the
    stack's current pair or the retained one, so a route that draws it reads the stack once
    (mb-3dkn). ``None`` for a pull request's snapshot or a refusal."""
    from metabrowser.builtin_plugins.github.checkout import ensure_resolved

    await ensure_resolved(request.app)
    host = pull_host(request.app)
    published = host.pulls.published if host is not None else None
    if (
        host is None
        or not isinstance(published, PublishedSource)
        or snapshot.store != store_tag(published.git_dir)
    ):
        return None, "refused", None
    reader = host.pulls.observed_reader
    pair = None
    if snapshot.scope == "stack":
        allowed, pair = await _stack_admission(request, published, snapshot, reader)
    else:
        allowed = await asyncio.to_thread(_admission, published, snapshot, reader)
    # The source and reader the decision was made for must still be the server's.
    if host.pulls.published is not published or host.pulls.observed_reader != reader:
        return None, "refused", None
    if allowed in ("refused", "unknown"):
        return None, allowed, None
    return published, allowed, pair


# ── Revisions ───────────────────────────────────────────────────

# The root tree of each head opened here: a full commit ID names one tree forever, so a
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


# ── The image route ─────────────────────────────────────────────


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"code": code, "message": message}, status_code=status)


async def pull_image_handler(request: Request) -> Response:
    """One image at the head of an admitted pair.

    Every response leaves through here, so each carries :data:`_HEADERS` and no later
    return can forget them.
    """
    response = await _respond(request)
    response.headers.update(_HEADERS)
    return response


async def _respond(request: Request) -> Response:
    params = request.query_params
    try:
        number, scope = requested_snapshot(params)
        base, head = params.get("left", ""), params.get("right", "")
        if (
            not is_full_revision(base)
            or not is_full_revision(head)
            or len(params.get("path", "")) > 8192
        ):
            raise ValueError
        path = GitPath.from_wire(params.get("path", ""))
        if not path.segments or any(part in {b".", b".."} for part in path.segments):
            raise ValueError
    except (PullRequestError, ValueError):
        return _error("invalid_image", "This image address is invalid.", 400)
    snapshot = Snapshot(number, base, head, params.get("store", ""), scope)
    published, admission = await admitted_snapshot(request, snapshot)
    if admission == "unknown":
        return _error(
            "snapshot_unavailable",
            "This PR revision could not be checked just now. Reload the page to try again.",
            409,
        )
    if published is None:
        return _error(
            "snapshot_expired",
            "This PR revision is no longer available. Open Changes again for the current comparison.",
            410,
        )
    try:
        tree = await _open_tree(published, snapshot.head)
        try:
            return await _image(tree, path)
        finally:
            await tree.aclose()
    except GitObjectUnavailableError:
        if admission == "retained":
            return _error(
                "snapshot_objects_expired",
                "This earlier revision of the pull request is no longer available. Open Changes for "
                "the current comparison.",
                410,
            )
        return _error(
            "snapshot_objects_unavailable",
            "This revision’s Git objects are unavailable. Reopen Changes to retry.",
            409,
        )
    except GitError:
        return _error(
            "snapshot_objects_unavailable",
            "This revision’s Git objects are unavailable. Reopen Changes to retry.",
            409,
        )


async def _image(tree: GitTreeSource, path: GitPath) -> Response:
    entry = await tree.resolve_path(path)
    if entry is None:
        return _error("file_not_found", "This file is absent at this revision.", 404)
    if entry.mode not in {"100644", "100755"}:
        what = (
            "a folder"
            if entry.is_tree
            else "a symbolic link, which images do not follow"
            if entry.is_symlink
            else "a submodule"
        )
        return _error("not_a_file", f"This path is {what} at this revision.", 404)
    ext = _extension(path)
    size = entry.size if entry.size is not None else (await tree.object_info(entry.oid)).size
    if ext not in _IMAGE_TYPES or size > tree.max_blob_bytes:
        return _error("unsupported_image", "This image cannot be displayed.", 415)
    return Response(await tree.read_blob(path), media_type=_IMAGE_TYPES[ext])
