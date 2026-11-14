"""Thin boundary between Metabrowser and the KPress runtime package.

KPress is imported on first use rather than at module load, which is a
deliberate exception to this package's ordinary import style and is confined to
this module.

The reason is measured. Importing `metabrowser.server` costs about 345 ms, of
which KPress and its rendering stack are the single largest contributor, and
every `metab` invocation pays it -- `--help`, `--walk`, and every `--api` route
included. Only three surfaces need the runtime: `/api/kpress/render`,
`/api/kpress/export`, and `/kpress-static/*`. The browser shell needs two KPress
asset URLs, but their public shape -- a stamp of the package's files, then its
version -- can be built from the files and the distribution metadata without
importing the renderer. Serve resolves those unconditional
assets before Uvicorn starts; non-serve modes and data routes do not pay for a
renderer they never use.

The exception is narrow on purpose. Deferring an import trades a startup cost
for a first-call cost and hides an unavailable dependency until run time, so it
earns its place only where the saving is measured and the dependency is heavy
and genuinely optional to most callers. Do not copy this pattern without those
three things; see `docs/development.md`.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from contextvars import ContextVar
from functools import cache, lru_cache
from html import escape
from importlib.metadata import version as distribution_version
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.parse import quote

from metabrowser.asset_stamps import StampedTree
from metabrowser.http_caching import editable_install

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


# Whether KPress renders in this context highlight fenced code. Pygments' lexers can cost
# far more than their input's size: review G of #348 found 15 of 594 quadratic in a
# line's length (48 KB of `devicetree` took 79 s) and the shell session prompt pattern
# cubic (one 1.6 KB `console` line took 12 s), which no estimate over the text bounds. A
# render of Markdown an untrusted author wrote therefore asks for plain code: each fence
# escaped, as KPress shows one that names no language.
_PLAIN_CODE: ContextVar[bool] = ContextVar("kpress_plain_code", default=False)
_plain_code_installed = False
_plain_code_lock = threading.Lock()


def _install_plain_code() -> None:
    """Make KPress's fence highlighter answer :data:`_PLAIN_CODE`, once per process.

    KPress has no option for it, and its fences call
    ``kpress.format.markdown._highlight_code``, so that function is wrapped. A KPress
    without it raises :class:`KPressRenderError`, so a render that asked for plain code
    fails rather than highlighting.
    """
    global _plain_code_installed
    with _plain_code_lock:
        if _plain_code_installed:
            return
        from kpress.format import markdown as kpress_markdown

        highlight = getattr(kpress_markdown, "_highlight_code", None)
        if not callable(highlight):
            raise KPressRenderError("this KPress has no fence highlighter to turn off")

        def highlight_unless_plain(code: str, language: str) -> str:
            return escape(code) if _PLAIN_CODE.get() else str(highlight(code, language))

        kpress_markdown._highlight_code = highlight_unless_plain  # pyright: ignore[reportPrivateUsage]
        _plain_code_installed = True


# Keep the top-level section spine visible while scroll-follow opens the active branch.
_TOC_COLLAPSE_DEPTH = 1

# These two package assets are unconditional browser-shell dependencies. Serve
# resolves them before Uvicorn starts so their first requests do not pay the
# deferred KPress import while inventory startup is competing for the CPU.
_BROWSER_SHELL_ASSET_PATHS = (
    "fonts/source-sans-3-latin-wght-normal.woff2",
    "css/style-tokens.css",
)


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
    "document_stylesheets",
    "export_kpress_document",
    "get_kpress_static_asset",
    "inert_render",
    "kpress_asset_prefix_settled",
    "kpress_asset_url_prefix",
    "kpress_stamp_is_current",
    "kpress_static_url",
    "prepare_browser_assets",
    "render_kpress_view",
    "set_kpress_static_root_for_tests",
]


def kpress_static_url(rel_path: str, *, prefix: str | None = None) -> str:
    """Content-keyed URL for a KPress static asset (e.g. a vendored font).

    Matches the URL embedded documents request, so chrome that preloads or links
    the same asset shares one download and cache entry instead of fetching a
    second copy. KPress defines this public path as
    ``<asset_url_prefix>v<distribution-version>/<quoted-path>``, and the prefix
    Metabrowser gives it is :func:`kpress_asset_url_prefix`. Building that small
    contract here keeps the shell from importing the renderer; the host
    integration test compares it with KPress' own helper so an upstream change
    cannot drift silently. *prefix* is one :func:`kpress_asset_url_prefix` already
    returned, for a page that names several assets.
    """

    base = kpress_asset_url_prefix() if prefix is None else prefix
    return f"{base}{_kpress_version_segment()}/{quote(rel_path.lstrip('/'))}"


@cache
def _kpress_version_segment() -> str:
    """The version segment KPress puts after the prefix, without importing its runtime."""

    return f"v{distribution_version('kpress')}"


@cache
def _kpress_tree() -> StampedTree | None:
    """The KPress package's files, located without importing it.

    The stamp covers every non-Python file under the package, so it needs nothing of how
    KPress lays out its assets; an upgrade, or an edit in an editable KPress, moves it.
    """

    spec = find_spec("kpress")
    locations = list(spec.submodule_search_locations or []) if spec is not None else []
    if not locations:
        return None
    return StampedTree(Path(locations[0]), live=editable_install("kpress"))


def kpress_asset_url_prefix() -> str:
    """The ``asset_url_prefix`` KPress renders with: ``/kpress-static/@<digest>/``.

    The digest names the KPress tree's contents (:mod:`metabrowser.asset_stamps`), so
    its CSS and JS can be kept without revalidation, which the version alone did not
    allow: an editable KPress serves changed bytes under the same version. KPress puts
    its version segment after it, and its stylesheets and modules reach their fonts and
    imports by relative URL, so everything under it inherits the digest. A KPress that
    cannot be stamped keeps the plain prefix, whose answers are revalidated.
    """

    tree = _kpress_tree()
    stamp = tree.stamp() if tree is not None else None
    return "/kpress-static/" if stamp is None else f"/kpress-static/@{stamp.digest}/"


def kpress_asset_prefix_settled() -> bool:
    """Whether :func:`kpress_asset_url_prefix` would return without touching the disk."""

    tree = _kpress_tree()
    return tree is None or tree.settled


def kpress_stamp_is_current(digest: str | None, body: bytes) -> bool:
    """Whether *body*, requested under ``@<digest>``, is what that stamp names now.

    KPress resolves the file itself, so the check is on the bytes: they must be among the
    files the current stamp was taken from.
    """

    tree = _kpress_tree()
    stamp = tree.latest() if tree is not None and digest is not None else None
    return stamp is not None and stamp.digest == digest and stamp.holds_content(body)


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
    plain_code: bool = False,
    asset_url_prefix: str | None = None,
) -> dict[str, Any]:
    """Render a Metabrowser file through KPress.

    ``include_toc="off"`` suppresses the table of contents for a document
    embedded inside Metabrowser's own navigation; see the README panel in the
    folder Overview. ``plain_code`` shows fenced code escaped rather than
    highlighted (see :data:`_PLAIN_CODE`). ``asset_url_prefix`` defaults to
    :func:`kpress_asset_url_prefix`; KPress keeps renders by it, so a render made
    under an older stamp never answers for the current one.
    """

    runtime = _runtime()
    if plain_code:
        _install_plain_code()
        # KPress keeps renders by this hash among the rest, so a plain render never
        # answers a highlighted request, or the reverse.
        mtime_hash = f"{mtime_hash}:plain-code"
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
        asset_url_prefix=kpress_asset_url_prefix()
        if asset_url_prefix is None
        else asset_url_prefix,
        # metabrowser shows the file path in its own file-header, so suppress
        # KPress's rendered <h1> doc header rather than hiding it with host CSS.
        show_doc_header=False,
        include_toc=include_toc,
        toc_collapse_depth=_TOC_COLLAPSE_DEPTH,
    )
    plain = _PLAIN_CODE.set(plain_code)
    try:
        return cast("dict[str, Any]", runtime.render_view(request))
    except runtime.KPressInvalidRequestError as exc:
        raise KPressInvalidRequestError(str(exc)) from exc
    except runtime.KPressRenderError as exc:
        raise KPressRenderError(str(exc)) from exc
    finally:
        _PLAIN_CODE.reset(plain)


def get_kpress_static_asset(rel_path: str) -> KPressAsset:
    """Read a safe KPress package static asset."""

    runtime = _runtime()
    try:
        return runtime.get_static_asset(rel_path)
    except runtime.KPressAssetNotFoundError as exc:
        raise KPressAssetNotFoundError(str(exc)) from exc


def prepare_browser_assets() -> None:
    """Initialize KPress and resolve the browser shell's required assets.

    Serve calls this before Uvicorn starts. Other CLI modes keep the deferred
    runtime boundary and pay no KPress renderer import cost. The package's asset
    stamp is taken here too, so the first page does not wait for its files to be
    read.
    """

    for rel_path in _BROWSER_SHELL_ASSET_PATHS:
        get_kpress_static_asset(rel_path)
    kpress_asset_url_prefix()


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


# KPress's table of contents -- its toggle, backdrop, and nav -- sits in the layout ahead
# of the prose, where nothing the document wrote can be: titles in it are escaped.
_KPRESS_PROSE = '<div class="kpress-prose'
_KPRESS_TOC = re.compile(r"<button\b[^>]*\bdata-kpress-toc-toggle\b.*?</nav>", re.DOTALL)


def _without_kpress_toc(html: str) -> tuple[str, bool]:
    """*html* without KPress's table of contents, and whether it had one."""

    prose = html.find(_KPRESS_PROSE)
    if prose < 0:
        return html, False
    chrome, found = _KPRESS_TOC.subn("", html[:prose], count=1)
    return chrome + html[prose:], found > 0


def _anchored_headings(headings: object, anchors: dict[str, str]) -> list[dict[str, Any]]:
    """KPress's table-of-contents entries, each pointing at its heading's anchor; an entry
    whose heading has none is left out."""

    entries: list[dict[str, Any]] = []
    for entry in cast("list[object]", headings) if isinstance(headings, list) else []:
        if not isinstance(entry, dict):
            continue
        href = str(cast("dict[str, object]", entry).get("href") or "")
        anchor = anchors.get(href[1:]) if href.startswith("#") else None
        if anchor is not None:
            entries.append({**cast("dict[str, Any]", entry), "href": f"#{anchor}"})
    return entries


def _assets_loading(assets: dict[str, Any], loading: frozenset[str]) -> dict[str, Any]:
    """*assets*, a KPress asset manifest, keeping only entries loaded one of these ways."""

    kept = [
        asset
        for asset in cast("list[object]", assets.get("assets") or [])
        if isinstance(asset, dict) and asset.get("loading") in loading
    ]
    return {key: value for key, value in assets.items() if key not in {"assets", "import_map"}} | {
        "assets": kept
    }


def document_stylesheets() -> dict[str, Any]:
    """The manifest of KPress's stylesheets, for prose a page sets in a KPress article itself.

    What KPress lists for an empty document, so no text chooses what a page loads, and
    stylesheets alone: nothing in it runs. A page gives it to ``loadKpressAssets``. One
    render per asset stamp, so once per process in a release.
    """

    return _document_stylesheets(kpress_asset_url_prefix())


# A live KPress tree moves its stamp at each edit; the last few are enough to keep.
@lru_cache(maxsize=4)
def _document_stylesheets(asset_url_prefix: str) -> dict[str, Any]:
    rendered = render_kpress_view(
        source_text="",
        source_path="document-stylesheets.md",
        kind="markdown",
        view="document",
        ext=".md",
        mtime_hash="document-stylesheets",
        size=0,
        include_toc="off",
        asset_url_prefix=asset_url_prefix,
    )
    return _assets_loading(cast("dict[str, Any]", rendered["assets"]), frozenset({"stylesheet"}))


def inert_render(
    rendered: dict[str, Any], *, rewrite_local: Callable[[str, bool], str | None] | None = None
) -> dict[str, Any]:
    """*rendered* for a page that must not trust it: allowlisted HTML and no scripts.

    Under the untrusted profile (active content off) a document's author is not the
    reader's to trust: its HTML is reduced to :mod:`metabrowser.inert_html`'s allowlist,
    references inside the document kept for the page to resolve, and every KPress
    script leaves the asset list -- KPress adds entry points for what a document
    contains, such as a video popover, and the document must not choose what the page
    loads. Stylesheets stay, and so does KPress's reading type. ``inert`` tells the page
    to apply the same allowlist again before inserting the HTML.

    KPress's table of contents leaves the HTML too, since its script cannot run; ``toc``
    says whether KPress drew one, and the model's ``headings`` -- its entries -- point at
    the headings' ``user-content-`` anchors, for the page to draw its own from them.

    *rewrite_local* is passed to :func:`~metabrowser.inert_html.harden_document`: a page
    that shows a document from outside the served tree, such as a pull request's revision
    file, gives it to write each reference inside the document as an address there.
    """

    from metabrowser.inert_html import harden_document

    inert = dict(rendered)
    html, inert["toc"] = _without_kpress_toc(str(rendered.get("html", "")))
    inert["html"], anchors = harden_document(html, rewrite_local=rewrite_local)
    assets = rendered.get("assets")
    if isinstance(assets, dict):
        inert["assets"] = _assets_loading(
            cast("dict[str, Any]", assets), frozenset({"stylesheet", "resource"})
        )
    inert["widgets"] = {}
    model = rendered.get("model")
    if isinstance(model, dict):
        model = cast("dict[str, Any]", model)
        inert["model"] = {
            **model,
            "headings": _anchored_headings(model.get("headings"), anchors),
            "widgets": {},
        }
    inert["inert"] = True
    return inert
