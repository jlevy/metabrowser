"""The PDF plugin's routes: a PDF's first-page preview, and the preview's image.

- ``GET /api/plugin/pdf/preview?path=<identity>``: the preview of a served file, the
  path as the client holds it (an inventory path in a folder, a ``GitPath`` wire on a
  pin), as :func:`metabrowser.source.resolve_content` takes it.
- ``GET /api/plugin/pdf/preview?oid=<blob>``: the preview of a blob of the served
  repository, by its full object ID: a side of a change in a comparison, which a diff
  names by its blob and which the served tree need not hold. On a pin it is read from
  the pin's store, beside a folder from the folder's repository. A blob is a revision's
  content, so it is never trusted (:func:`metabrowser.capabilities.capabilities_for`).

  Either answers 200 with ``{"status": "ready", "key", "width", "height", "pages",
  "image", "rendered"}``, where ``image`` is the image route's address and ``rendered``
  says whether this request drew it, or with ``{"status": "unavailable", "reason",
  "message"}``, a reason of :data:`.preview.REASON_MESSAGES`: the card then shows no
  image and still opens the file. A request that names nothing to preview is 400, and a
  path or blob that is not there is 404. Answers are ``no-store``: the file can change.
- ``GET /api/plugin/pdf/preview-image?key=<64 hex>``: the PNG in the cache under that
  key, ``image/png``. The key names its bytes, so the answer is immutable and may be kept
  a year. It is an image and nothing else: ``nosniff``, a policy that runs nothing and
  frames nothing, no referrer, and readable only by this origin. A key not of the form
  is 400, and one the cache does not hold is 404.

Trust is decided once, from the subject the request resolved at its start, and used for
the whole request, as :func:`metabrowser.capabilities.capabilities_for` asks; the bytes
are read from that same subject.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
from typing import TYPE_CHECKING, Any, Final

from starlette.responses import JSONResponse, Response

from metabrowser.builtin_plugins.pdf.preview import (
    MAX_INPUT_BYTES,
    REASON_MESSAGES,
    Preview,
    PreviewRefusedError,
    PreviewSource,
    content_hashes,
    opened_store,
    preview_for,
)
from metabrowser.builtin_plugins.pdf.preview_store import KEY_PATTERN
from metabrowser.capabilities import capabilities_for
from metabrowser.content_errors import ContentReadError
from metabrowser.source import (
    ContentRef,
    SourceSession,
    as_git_revision_subject,
    get_source_session,
    read_content_window,
)

if TYPE_CHECKING:
    from starlette.requests import Request

_OID: Final = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
# A path parameter longer than this names no file a request should resolve; the same
# bound as the GitHub image route's (`pull_snapshot.py`).
_MAX_PATH_CHARS: Final = 8192
_NO_STORE: Final = {"Cache-Control": "no-store"}
# Every image answer, errors included, so no return path can leave one out.
IMAGE_HEADERS: Final = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
# A preview's image never changes under its key.
_IMMUTABLE: Final = "private, max-age=31536000, immutable"


def _answer(body: dict[str, Any], status: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers=_NO_STORE)


def _invalid(message: str) -> JSONResponse:
    return _answer({"code": "invalid_request", "message": message}, 400)


def _not_found(what: str) -> JSONResponse:
    return _answer({"code": "not_found", "message": f"No {what} is there."}, 404)


def _ready(preview: Preview) -> JSONResponse:
    return _answer(
        {
            "status": "ready",
            "key": preview.key,
            "width": preview.facts.width,
            "height": preview.facts.height,
            "pages": preview.facts.pages,
            "image": f"/api/plugin/pdf/preview-image?key={preview.key}",
            "rendered": preview.rendered,
        }
    )


def _unavailable(refused: PreviewRefusedError) -> JSONResponse:
    return _answer(
        {
            "status": "unavailable",
            "reason": refused.reason,
            "message": REASON_MESSAGES[refused.reason],
        }
    )


def _trusted(session: SourceSession) -> bool:
    pinned = as_git_revision_subject(session.subject) is not None
    return capabilities_for(pinned_revision=pinned).active_content


async def _bounded_bytes(ref: ContentRef) -> bytes:
    if ref.stored_size is not None and ref.stored_size > MAX_INPUT_BYTES:
        raise PreviewRefusedError("too_large")
    window = await read_content_window(ref, offset=0, max_bytes=MAX_INPUT_BYTES)
    if window.has_more:
        raise PreviewRefusedError("too_large")
    return window.data


def _file_identity(session: SourceSession, identity: str) -> tuple[int, int] | None:
    """A served file's device and inode, which a rename onto it changes."""

    handle = session.content.resolve(identity)
    if handle is None or handle.path is None:
        return None
    try:
        status = os.stat(handle.path)
    except OSError:
        return None
    return status.st_dev, status.st_ino


def _path_source(session: SourceSession, ref: ContentRef) -> PreviewSource:
    pin = as_git_revision_subject(session.subject)
    if pin is not None:
        oid = ref.fingerprint

        async def pinned_id() -> str:
            return f"git-blob:{oid}"

        return PreviewSource(
            trusted=_trusted(session),
            content_id=pinned_id,
            read=lambda: _bounded_bytes(ref),
        )

    held: list[bytes] = []
    keyed: list[str] = []

    async def folder_id() -> str:
        node = await asyncio.to_thread(_file_identity, session, ref.identity)
        fingerprint = (ref.identity, ref.fingerprint, ref.stored_size, node)
        known = content_hashes.get(fingerprint) if node is not None else None
        if known is None:
            data = await _bounded_bytes(ref)
            held.append(data)
            known = await asyncio.to_thread(lambda: hashlib.sha256(data).hexdigest())
            if node is not None:
                content_hashes.remember(fingerprint, known)
        keyed.append(known)
        return f"sha256:{known}"

    async def folder_bytes() -> bytes:
        if held:
            return held.pop()
        # Keyed by a remembered hash: the file is read now, and drawn under that key only
        # if it still has those bytes, since it may have changed in between.
        data = await _bounded_bytes(ref)
        digest = await asyncio.to_thread(lambda: hashlib.sha256(data).hexdigest())
        if keyed and digest != keyed[0]:
            raise PreviewRefusedError("failed")
        return data

    return PreviewSource(trusted=_trusted(session), content_id=folder_id, read=folder_bytes)


async def _blob_size(session: SourceSession, oid: str) -> int | None:
    """The size of blob *oid* in the served repository, or None when it holds no such blob."""

    from metabrowser.git.process import GitError, GitLocation, run_git_at

    pin = as_git_revision_subject(session.subject)
    try:
        if pin is not None:
            info = await pin.tree_source.object_info(oid)
            return info.size if info.kind == "blob" else None
        root = session.subject.filesystem_root
        if root is None:
            return None
        location = GitLocation.filesystem(root)
        kind = (await run_git_at(["cat-file", "-t", oid], location, max_bytes=64)).strip()
        if kind != b"blob":
            return None
        return int(await run_git_at(["cat-file", "-s", oid], location, max_bytes=64))
    except (GitError, ValueError):
        return None


async def _blob_bytes(session: SourceSession, oid: str) -> bytes:
    from metabrowser.git.process import GitLocation, GitOutputTooLargeError, run_git_at

    pin = as_git_revision_subject(session.subject)
    if pin is not None:
        data, size = await pin.tree_source.read_blob_window(
            oid, offset=0, max_bytes=MAX_INPUT_BYTES + 1
        )
        if size > MAX_INPUT_BYTES:
            raise PreviewRefusedError("too_large")
        return data
    root = session.subject.filesystem_root
    if root is None:  # pragma: no cover - `_blob_size` found it first
        raise PreviewRefusedError("failed")
    try:
        return await run_git_at(
            ["cat-file", "blob", oid], GitLocation.filesystem(root), max_bytes=MAX_INPUT_BYTES
        )
    except GitOutputTooLargeError as exc:
        raise PreviewRefusedError("too_large") from exc


async def preview_handler(request: Request) -> JSONResponse:
    """``GET /api/plugin/pdf/preview?path=<identity>`` or ``?oid=<blob>``."""

    params = request.query_params
    path = params.get("path", "")
    oid = params.get("oid", "")
    if bool(path) == bool(oid):
        return _invalid("Name a file with path, or a blob with oid.")
    if len(path) > _MAX_PATH_CHARS:
        return _invalid("This path is too long.")
    session = get_source_session()
    try:
        if oid:
            if not _OID.fullmatch(oid):
                return _invalid("oid is a full object ID.")
            size = await _blob_size(session, oid)
            if size is None:
                return _not_found("blob")
            if size > MAX_INPUT_BYTES:
                raise PreviewRefusedError("too_large")

            async def blob_id() -> str:
                return f"git-blob:{oid}"

            source = PreviewSource(
                trusted=False, content_id=blob_id, read=lambda: _blob_bytes(session, oid)
            )
        else:
            ref = await session.content.open_ref(path)
            if ref is None:
                return _not_found("file")
            source = _path_source(session, ref)
        return _ready(await preview_for(source))
    except PreviewRefusedError as refused:
        return _unavailable(refused)
    except ContentReadError:
        return _not_found("file")


async def preview_image_handler(request: Request) -> Response:
    """``GET /api/plugin/pdf/preview-image?key=<64 hex>``. Every answer carries the headers."""

    response = await _image(request.query_params.get("key", ""))
    response.headers.update(IMAGE_HEADERS)
    return response


async def _image(key: str) -> Response:
    if not KEY_PATTERN.fullmatch(key):
        return Response("This preview address is invalid.", 400, media_type="text/plain")
    store = await opened_store()
    data = None if store is None else await asyncio.to_thread(store.read, key)
    if data is None:
        return Response("No preview is kept under this key.", 404, media_type="text/plain")
    return Response(data, media_type="image/png", headers={"Cache-Control": _IMMUTABLE})


__all__ = ["IMAGE_HEADERS", "preview_handler", "preview_image_handler"]
