"""Data hooks for the built-in diff plugin.

``GET /api/plugin/diff/document?path=<rel>`` parses the patch file into
File Diff Format and returns the hydrated document — the same shape
``metab --diff`` emits and the conformance corpus validates, so the
browser model never sees a plugin-specific envelope. A virtual path
``<patch>/<inner>`` (the container contract) returns the same document
narrowed to that one file change.

``GET /api/plugin/diff/children?path=<rel>`` lists the change entries as
nav-tree child rows for the container affordance.

Synchronous on purpose: the data-hook dispatcher runs sync sidekicks in
the thread pool, and the parser is a bounded pure function.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.responses import JSONResponse

from metabrowser.diff.adapters.patch_file import MAX_PATCH_BYTES, parse_unified_patch
from metabrowser.diff.format import ChangeSetDocument, FileChange, Totals, dump_document
from metabrowser.plugin_api import resolve_path

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.requests import Request

# The container contract exposes one virtual level: a change entry's
# path. Deeper requests are malformed, and the ancestor walk on a
# request path must stay bounded.
_MAX_VIRTUAL_PARTS = 16

_PATCH_EXTS = (".patch", ".diff")


def _error(kind: str, message: str, status: int, *, path: str) -> JSONResponse:
    return JSONResponse({"error": kind, "message": message, "path": path}, status_code=status)


def _resolve_patch(subpath: str) -> tuple[Path, str] | None:
    """Resolve a real or virtual path to (patch file, inner path).

    Mirrors the server's nearest-file-ancestor rule, scoped to this
    plugin's extensions: the walk is bounded, every prefix passes the
    same served-root gate, and a real directory ancestor means the
    request was an ordinary missing file, not a container child.
    """
    direct = resolve_path(subpath)
    if direct is not None and direct.is_file():
        return direct, ""
    parts = subpath.split("/")
    if len(parts) < 2 or len(parts) > _MAX_VIRTUAL_PARTS:
        return None
    for cut in range(len(parts) - 1, 0, -1):
        prefix = "/".join(parts[:cut])
        target = resolve_path(prefix)
        if target is None:
            continue
        if target.is_dir():
            return None
        if not target.is_file():
            # Nothing at this depth; keep walking toward the root.
            continue
        if not prefix.lower().endswith(_PATCH_EXTS):
            return None
        return target, "/".join(parts[cut:])
    return None


def _parse(target: Path) -> ChangeSetDocument:
    # One byte past the cap keeps the parser's own truncation reporting
    # authoritative: it sees that the input exceeded the bound and says
    # so in the manifest, rather than this handler inventing a second rule.
    data = target.read_bytes()[: MAX_PATCH_BYTES + 1]
    return parse_unified_patch(data)


def _change_display_path(change: FileChange) -> str:
    side = change.new if change.new is not None else change.old
    return side.path if side is not None else ""


def _narrow_to_path(document: ChangeSetDocument, inner: str) -> ChangeSetDocument | None:
    """The same document, filtered to every change at path *inner*.

    Usually one change. A patch file records a type change as a delete
    plus an add at the same path — what git reports as one ``T`` entry —
    so a path can name more than one change, and the reader asking about
    that path wants both halves, not an arbitrary one.
    """
    matches = [c for c in document.manifest.files if _change_display_path(c) == inner]
    if not matches:
        return None
    patches = {c.id: document.patches[c.id] for c in matches if c.id in document.patches}
    counted = [c for c in matches if c.additions is not None]
    manifest = document.manifest.model_copy(
        update={
            "files": tuple(matches),
            "totals": Totals.model_construct(
                files=len(matches),
                additions=sum(c.additions or 0 for c in counted) if counted else None,
                deletions=sum(c.deletions or 0 for c in counted) if counted else None,
                exact=len(counted) == len(matches),
            ),
            "truncated": False,
            "cursor": None,
        }
    )
    return document.model_copy(update={"manifest": manifest, "patches": patches})


def document_handler(request: Request) -> JSONResponse:
    """One patch file — or one change inside it — as a ChangeSetDocument."""
    subpath = request.query_params.get("path", "")
    resolved = _resolve_patch(subpath)
    if resolved is None:
        return _error("diff_document", "This file is not available.", 404, path=subpath)
    target, inner = resolved
    document = _parse(target)
    if inner:
        narrowed = _narrow_to_path(document, inner)
        if narrowed is None:
            return _error(
                "diff_document",
                "This change set has no entry for that path.",
                404,
                path=subpath,
            )
        document = narrowed
    return JSONResponse(dump_document(document))


def children_handler(request: Request) -> JSONResponse:
    """The change entries of one patch file, as nav-tree child rows."""
    subpath = request.query_params.get("path", "")
    target = resolve_path(subpath)
    if target is None or not target.is_file():
        return _error("diff_children", "This file is not available.", 404, path=subpath)
    document = _parse(target)
    # One row per path, not per change: a patch file spells a type change
    # as delete-plus-add at the same path, and two rows sharing a virtual
    # path would be two rows that open the same thing.
    order: list[str] = []
    grouped: dict[str, list[FileChange]] = {}
    for change in document.manifest.files:
        display = _change_display_path(change)
        if not display:
            continue
        if display not in grouped:
            grouped[display] = []
            order.append(display)
        grouped[display].append(change)
    children: list[dict[str, Any]] = []
    for display in order:
        changes = grouped[display]
        entry: dict[str, Any] = {
            "name": display,
            "path": f"{subpath}/{display}",
            "badge": "T" if len(changes) > 1 else changes[0].kind.value[:1].upper(),
        }
        if all(c.availability.value != "ready" for c in changes):
            entry["muted"] = True
        children.append(entry)
    return JSONResponse({"children": children, "truncated": document.manifest.truncated})
