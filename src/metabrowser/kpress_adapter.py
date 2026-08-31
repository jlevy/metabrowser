"""Thin boundary between Metabrowser and the KPress runtime package.

KPress is imported on first use rather than at module load, which is a
deliberate exception to this package's ordinary import style and is confined to
this module.

The reason is measured. Importing `metabrowser.server` costs about 345 ms, of
which KPress and its rendering stack are the single largest contributor, and
every `metab` invocation pays it -- `--help`, `--walk`, and every `--api` route
included. Only four surfaces actually need KPress: the browser shell's HTML
(for its font URLs), `/api/kpress/render`, `/api/kpress/export`, and
`/kpress-static/*`. No data route touches it, so the whole CLI was paying for a
renderer it does not use.

The exception is narrow on purpose. Deferring an import trades a startup cost
for a first-call cost and hides an unavailable dependency until run time, so it
earns its place only where the saving is measured and the dependency is heavy
and genuinely optional to most callers. Do not copy this pattern without those
three things; see `docs/development.md`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    # Annotations only. `from __future__ import annotations` makes these
    # strings at run time, so naming them costs nothing.
    from kpress.models import KPressAsset, KPressExportRequest


# Resolved on first use and cached here. This stays a module attribute rather
# than a local inside `_runtime` because it is the seam the KPress tests
# substitute: `monkeypatch.setattr(kpress_adapter, "_kpress_runtime", fake)`
# works exactly as it did when the import was at module level.
_kpress_runtime: Any = None


def _runtime() -> Any:
    """The KPress runtime, imported on first call. See the module docstring."""

    global _kpress_runtime
    if _kpress_runtime is None:
        from kpress import runtime

        _kpress_runtime = runtime
    return _kpress_runtime


# Keep the top-level section spine visible while scroll-follow opens the active branch.
_TOC_COLLAPSE_DEPTH = 1


class KPressRenderError(RuntimeError):
    """Raised when KPress is present but cannot render the requested input."""


class KPressInvalidRequestError(ValueError):
    """Raised when a KPress request is malformed (e.g. unknown print profile)."""


class KPressAssetNotFoundError(FileNotFoundError):
    """Raised when a KPress package asset path is missing or unsafe."""


__all__ = [
    "KPressAssetNotFoundError",
    "KPressInvalidRequestError",
    "KPressRenderError",
    "build_export_request",
    "clear_render_cache",
    "export_kpress_document",
    "get_kpress_static_asset",
    "kpress_static_url",
    "render_kpress_view",
    "set_kpress_static_root_for_tests",
]


def kpress_static_url(rel_path: str) -> str:
    """Version-keyed URL for a KPress static asset (e.g. a vendored font).

    Matches the URL embedded documents request, so chrome that preloads or links
    the same asset shares one download and cache entry instead of fetching a
    second copy.
    """

    return _runtime().static_asset_url(rel_path)


def clear_render_cache() -> None:
    """Clear KPress' in-process render cache."""

    _runtime().clear_render_cache()


def set_kpress_static_root_for_tests(path: Path | None) -> None:
    """Override KPress static asset root for route tests."""

    _runtime().set_static_root_for_tests(path)


def render_kpress_view(
    *,
    source_text: str,
    source_path: str,
    kind: str,
    view: str,
    ext: str,
    mtime_hash: str,
    size: int,
    frontmatter: dict[str, Any] | None = None,
    frontmatter_error: str | None = None,
    profile: str | None = None,
    include_toc: Literal["auto", "on", "off"] = "auto",
) -> dict[str, Any]:
    """Render a Metabrowser file through KPress.

    ``include_toc="off"`` suppresses the table of contents for a document
    embedded inside Metabrowser's own navigation; see the README panel in the
    folder Overview.
    """

    runtime = _runtime()
    # KPress defaults to font_mode="custom", which uses vendored PT Serif /
    # Source Sans reader faces. Host fonts apply only when font_mode="host".
    request = runtime.KPressRenderRequest(
        source_text=source_text,
        source_path=source_path,
        kind=kind,
        view=view,
        ext=ext,
        mtime_hash=mtime_hash,
        size=size,
        frontmatter=frontmatter or {},
        frontmatter_error=frontmatter_error,
        profile=profile,
        include_theme_resolver=False,
        host="metabrowser",
        asset_url_prefix="/kpress-static/",
        # metabrowser shows the file path in its own file-header, so suppress
        # KPress's rendered <h1> doc header rather than hiding it with host CSS.
        show_doc_header=False,
        include_toc=include_toc,
        toc_collapse_depth=_TOC_COLLAPSE_DEPTH,
        # A browser shows one document after another, so the reading column has
        # to land in the same place every time. KPress's wide band gives a
        # document with a TOC a left-aligned sidebar grid and a document under
        # `toc_min_headings` a centred, measure-capped column — different
        # position AND a narrower measure. Reserving holds the rail open on the
        # documents that earn no TOC, so only the rail's contents change between
        # files, never the layout. See KPress's "Reserved TOC Rail".
        toc_rail="reserved",
    )
    try:
        return runtime.render_view(request)
    except runtime.KPressInvalidRequestError as exc:
        raise KPressInvalidRequestError(str(exc)) from exc
    except runtime.KPressRenderError as exc:
        raise KPressRenderError(str(exc)) from exc


def get_kpress_static_asset(rel_path: str) -> KPressAsset:
    """Read a safe KPress package static asset."""

    runtime = _runtime()
    try:
        return runtime.get_static_asset(rel_path)
    except runtime.KPressAssetNotFoundError as exc:
        raise KPressAssetNotFoundError(str(exc)) from exc


def build_export_request(**kwargs: Any) -> KPressExportRequest:
    """Construct a KPress static-export request.

    The model is imported here rather than named at module scope because it is
    constructed, not merely annotated -- the distinction the deferred import in
    this module has to respect.
    """

    from kpress.models import KPressExportRequest as _KPressExportRequest

    return _KPressExportRequest(**kwargs)


def export_kpress_document(request: KPressExportRequest) -> dict[str, object]:
    """Delegate static export requests to KPress publisher APIs.

    The publish pipeline raises ``KPressPublishError`` (and subclasses like the
    optimizer/missing-dependency errors), which is a sibling of
    ``KPressRenderError`` rather than a subclass — so it is translated explicitly
    here to the adapter's render-error type, which the export route maps to a 502
    rather than letting it surface as an unstructured 500.
    """

    runtime = _runtime()
    try:
        return cast("dict[str, object]", runtime.export_document(request))
    except runtime.KPressInvalidRequestError as exc:
        raise KPressInvalidRequestError(str(exc)) from exc
    except (runtime.KPressPublishError, runtime.KPressRenderError) as exc:
        raise KPressRenderError(str(exc)) from exc
