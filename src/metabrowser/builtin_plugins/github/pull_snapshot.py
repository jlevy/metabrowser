"""Read one admitted PR revision without switching the served repository subject."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from html import escape
from pathlib import PurePosixPath
from typing import Final, Literal, cast
from urllib.parse import unquote_to_bytes, urlencode, urlsplit

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from metabrowser import kpress_adapter
from metabrowser.builtin_plugins.github.pull_record import PullRecord, read_pull_record
from metabrowser.builtin_plugins.github.pull_route import (
    PullRequestError,
    pull_host,
    requested_number,
)
from metabrowser.builtin_plugins.github.pull_snapshot_cache import read_snapshot_bindings
from metabrowser.cache.acquire import PublishedSource
from metabrowser.cache.repository_store import open_revision
from metabrowser.git.process import GitError
from metabrowser.git.tree_source import GitPath, display_segment
from metabrowser.git.wire import is_full_revision
from metabrowser.http_caching import store_tag
from metabrowser.view_routes import format_pull_href

_ROUTE: Final = "/api/plugin/github/pull-snapshot"
_HEADERS: Final = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'self'; font-src 'self'; img-src 'self'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
_MARKDOWN: Final = frozenset({".md", ".markdown", ".mdown", ".mkd"})
_IMAGE_TYPES: Final = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
}
# Keep the Source view windowed and cap renderer inputs before reading their bodies.
_DOCUMENT_BYTES: Final = 256 * 1024
_SOURCE_BYTES: Final = 64 * 1024
_IMAGE_BYTES: Final = 8 * 1024 * 1024
type ViewMode = Literal["document", "source", "image"]


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
                "number": self.number,
                "left": self.base,
                "right": self.head,
                "store": self.store,
                "side": self.side,
                "path": path.to_wire(),
                "mode": mode,
                **({"offset": str(offset)} if offset else {}),
            }
        )
        return f"{_ROUTE}?{query}"

    def reference(self, source: GitPath, href: str, image: bool) -> str | None:
        """Rewrite an already sanitized, local reference into this immutable tree."""
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
        target = self.href(path, "image" if image else "document")
        if url.fragment and not image:
            from urllib.parse import quote

            from metabrowser.inert_html import fragment_link

            target += fragment_link("#" + quote(url.fragment, safe="-%._~"))
        return target


def _allowed(published: PublishedSource, snapshot: Snapshot, observed_reader: str | None) -> bool:
    record = read_pull_record(published.home, published.slug, snapshot.number, shared="refuse")
    if (
        not isinstance(record, PullRecord)
        or record.source.casefold() != published.source.normalized.casefold()
    ):
        return False
    if observed_reader is not None and observed_reader != record.reader:
        return False
    pair = (snapshot.base, snapshot.head)
    comparison = record.comparison
    if comparison is not None and pair == (comparison.base, comparison.head):
        return True
    return any(
        binding.store == published.store_id
        and binding.reader == record.reader
        and pair == (binding.base, binding.head)
        for binding in read_snapshot_bindings(published.home, published.slug, snapshot.number)
    )


def _error(request: Request, code: str, message: str, status: int) -> Response:
    if request.query_params.get("mode") == "image" or "application/json" in request.headers.get(
        "accept", ""
    ):
        return JSONResponse(
            {"code": code, "message": message}, status_code=status, headers=_HEADERS
        )
    return HTMLResponse(
        "<!doctype html><html lang=en><meta charset=utf-8><title>File unavailable</title>"
        f"<main><h1>File unavailable</h1><p>{escape(message)}</p></main></html>",
        status_code=status,
        headers=_HEADERS,
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
    )
    return str(
        kpress_adapter.inert_render(
            rendered, rewrite_local=lambda href, image: snapshot.reference(path, href, image)
        )["html"]
    )


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
        f'<a href="{escape(format_pull_href(snapshot.number, "files"))}">PR #{snapshot.number} Changes</a>'
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
        for asset in kpress_adapter.document_stylesheets().get("assets", []):
            href = asset.get("public_url")
            if isinstance(href, str) and href.startswith("/kpress-static/"):
                styles += f'<link rel="stylesheet" href="{escape(href)}">'
    return HTMLResponse(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(name)} at {snapshot.commit[:12]}</title>"
        '<link rel="stylesheet" href="/static/styles.css">'
        '<link rel="stylesheet" href="/plugin-static/github/styles.css">'
        f'{styles}<body class="pull-snapshot-page"><main class="pull-snapshot"><header><nav aria-label="Revision file">'
        f"{' '.join(links)}</nav><h1>{escape(name)}</h1><code>{snapshot.commit}</code></header>"
        f'<article class="pull-snapshot-content">{content}</article></main></body></html>',
        headers=_HEADERS,
    )


async def admitted_snapshot(request: Request, snapshot: Snapshot) -> PublishedSource | None:
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
        return None
    reader = host.pulls.observed_reader
    allowed = await asyncio.to_thread(_allowed, published, snapshot, reader)
    if not allowed or host.pulls.published is not published or host.pulls.observed_reader != reader:
        return None
    return published


async def pull_snapshot_handler(request: Request) -> Response:
    """Read a file or inert document asset only from the requested admitted side."""
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
            or mode not in {"document", "source", "image"}
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
    published = await admitted_snapshot(request, snapshot)
    if published is None:
        return _error(
            request,
            "snapshot_expired",
            "This PR revision is no longer available. Open Changes again for the current comparison.",
            410,
        )
    ext = PurePosixPath(display_segment(path.segments[-1])).suffix.lower()
    try:
        subject = await open_revision(
            home=published.home,
            store_key=published.store_key,
            commit_oid=snapshot.commit,
            store_identity=published.store_id,
        )
        try:
            tree = subject.tree_source
            entry = await tree.resolve_path(path)
            if entry is None or entry.mode not in {"100644", "100755"}:
                return _error(
                    request, "file_not_found", "This file is absent at this revision.", 404
                )
            size = (
                entry.size if entry.size is not None else (await tree.object_info(entry.oid)).size
            )
            if mode == "image":
                if ext not in _IMAGE_TYPES or size > _IMAGE_BYTES:
                    return _error(
                        request, "unsupported_image", "This image cannot be displayed.", 415
                    )
                return Response(
                    await tree.read_blob(path), media_type=_IMAGE_TYPES[ext], headers=_HEADERS
                )
            markdown = ext in _MARKDOWN and size <= _DOCUMENT_BYTES
            if mode == "document" and markdown:
                try:
                    document = await asyncio.to_thread(
                        _render_markdown, await tree.read_blob(path), path, entry.oid, snapshot
                    )
                except (kpress_adapter.KPressRenderError, kpress_adapter.KPressInvalidRequestError):
                    pass
                else:
                    return _page(snapshot, path, document, markdown=True, document=True)
            if offset >= size and offset:
                return _error(
                    request, "invalid_offset", "This source window is outside the file.", 416
                )
            body, _ = await tree.read_blob_window(entry.oid, offset=offset, max_bytes=_SOURCE_BYTES)
        finally:
            await subject.aclose()
    except GitError:
        return _error(
            request,
            "snapshot_objects_unavailable",
            "This revision’s Git objects are unavailable. Reopen Changes to retry.",
            409,
        )
    source = escape(body.decode("utf-8", "replace"))
    next_offset = offset + len(body)
    return _page(
        snapshot,
        path,
        f"<pre><code>{source}</code></pre>",
        markdown=markdown,
        document=False,
        offset=offset,
        next_offset=next_offset if next_offset < size else None,
    )
