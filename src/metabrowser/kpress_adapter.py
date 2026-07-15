"""Thin boundary between MetaBrowser and the KPress runtime package."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

from kpress import runtime as _kpress_runtime
from kpress.models import KPressAsset, KPressExportRequest, ThemeMode


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

    return _kpress_runtime.static_asset_url(rel_path)


def clear_render_cache() -> None:
    """Clear KPress' in-process render cache."""

    _kpress_runtime.clear_render_cache()


def set_kpress_static_root_for_tests(path: Path | None) -> None:
    """Override KPress static asset root for route tests."""

    _kpress_runtime.set_static_root_for_tests(path)


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
    theme_mode: str = "system",
    resolved_theme: str = "light",
) -> dict[str, Any]:
    """Render a MetaBrowser file through KPress."""

    runtime = _kpress_runtime
    if theme_mode not in {"system", "light", "dark"}:
        raise KPressInvalidRequestError(f"Unsupported KPress theme mode {theme_mode!r}")
    if resolved_theme not in {"light", "dark"}:
        raise KPressInvalidRequestError(f"Unsupported resolved KPress theme {resolved_theme!r}")
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
        theme_mode=cast("ThemeMode", theme_mode),
        resolved_theme=cast('Literal["light", "dark"]', resolved_theme),
        host="metabrowser",
        asset_url_prefix="/kpress-static/",
        # metabrowser shows the file path in its own file-header, so suppress
        # KPress's rendered <h1> doc header rather than hiding it with host CSS.
        show_doc_header=False,
    )
    try:
        return runtime.render_view(request)
    except runtime.KPressInvalidRequestError as exc:
        raise KPressInvalidRequestError(str(exc)) from exc
    except runtime.KPressRenderError as exc:
        raise KPressRenderError(str(exc)) from exc


def get_kpress_static_asset(rel_path: str) -> KPressAsset:
    """Read a safe KPress package static asset."""

    runtime = _kpress_runtime
    try:
        return runtime.get_static_asset(rel_path)
    except runtime.KPressAssetNotFoundError as exc:
        raise KPressAssetNotFoundError(str(exc)) from exc


def build_export_request(**kwargs: Any) -> KPressExportRequest:
    """Construct a KPress static-export request."""

    return KPressExportRequest(**kwargs)


def export_kpress_document(request: KPressExportRequest) -> dict[str, object]:
    """Delegate static export requests to KPress publisher APIs.

    The publish pipeline raises ``KPressPublishError`` (and subclasses like the
    optimizer/missing-dependency errors), which is a sibling of
    ``KPressRenderError`` rather than a subclass — so it is translated explicitly
    here to the adapter's render-error type, which the export route maps to a 502
    rather than letting it surface as an unstructured 500.
    """

    runtime = _kpress_runtime
    try:
        return cast("dict[str, object]", runtime.export_document(request))
    except runtime.KPressInvalidRequestError as exc:
        raise KPressInvalidRequestError(str(exc)) from exc
    except (runtime.KPressPublishError, runtime.KPressRenderError) as exc:
        raise KPressRenderError(str(exc)) from exc
