"""Offline-first asset policy — every browser asset is vendored and same-origin.

Third-party browser libraries are vendored into the wheel from
lockfile-verified npm packages by ``devtools/vendor_assets.py`` and served
from ``/static/vendor/``. The rendered page must reference no external
origins at all, so Metabrowser works offline and the runtime trust model
collapses to the wheel itself.

These tests assert:
1. The rendered index references no external ``src``/``href`` origins.
2. The vendored files match ``static/vendor/manifest.json`` byte-for-byte
   and the manifest versions match the ``package.json`` pins.
3. Highlight.js layout and colors stay in the host stylesheet, with no vendor theme.
4. The vendored TOML grammar is the official highlight.js ``ini`` grammar.
5. Local core scripts load before the optional vendored libraries.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from unittest.mock import Mock

from devtools.vendor_assets import check as vendor_check
from metabrowser import server

VENDOR_DIR = Path(__file__).resolve().parent.parent / "src" / "metabrowser" / "static" / "vendor"
REPO_ROOT = VENDOR_DIR.parents[3]


def _index_html() -> str:
    return bytes(asyncio.run(server.index(Mock())).body).decode("utf-8")


def test_no_external_asset_origins_in_index() -> None:
    """The page must be loadable fully offline: no external asset is fetched.

    An asset is something the page needs in order to render — a script, an
    image, a stylesheet. A hyperlink is not: an ``<a href>`` to the project's
    own page costs nothing until someone clicks it, and the page renders
    identically with no network at all.

    Stated as "assets" rather than as "any absolute URL" because the two are
    not the same rule, and only the first one is about being loadable offline.
    """

    html = _index_html()
    fetched = re.findall(r'src="(https?://[^"]+)"', html)
    fetched += [
        match.group(1)
        for tag in re.findall(r"<link\b[^>]*>", html, re.IGNORECASE)
        for match in re.finditer(r'href="(https?://[^"]+)"', tag)
    ]
    assert fetched == [], f"external asset references remain: {fetched}"
    assert "cdn.jsdelivr.net" not in html
    assert "cdnjs.cloudflare.com" not in html


def test_outbound_links_are_anchors_to_the_project() -> None:
    """The page may link out, and only as a link the reader chooses to follow.

    This is the other half of the rule above: absolute URLs are permitted, but
    each one has to be an anchor, so a future asset cannot arrive by being
    spelled as an href.
    """

    html = _index_html()
    anchors = {
        match.group(1)
        for tag in re.findall(r"<a\b[^>]*>", html, re.IGNORECASE)
        for match in re.finditer(r'href="(https?://[^"]+)"', tag)
    }
    every_absolute = set(re.findall(r'(?:src|href)="(https?://[^"]+)"', html))
    assert every_absolute == anchors, (
        f"absolute URLs that are not anchors: {sorted(every_absolute - anchors)}"
    )
    assert anchors <= {"https://github.com/jlevy/metabrowser"}, (
        f"unexpected outbound link: {sorted(anchors)}"
    )


def test_vendored_assets_match_manifest() -> None:
    """Committed vendor files, manifest hashes, and npm pins agree."""
    problems = vendor_check()
    assert problems == [], "\n".join(problems)


def test_optional_libraries_are_served_from_local_vendor() -> None:
    html = _index_html()
    for name in (
        "vendor/mustache.min.js",
        "vendor/highlight.min.js",
        "vendor/highlight-toml.min.js",
        "vendor/chart.umd.min.js",
        "vendor/chartjs-plugin-annotation.min.js",
        "vendor/chartjs-adapter-date-fns.bundle.min.js",
    ):
        assert name in html, f"vendored asset missing from index template: {name}"
        assert (VENDOR_DIR / Path(name).name).is_file(), f"vendored file missing: {name}"


def test_highlight_theme_stylesheet_is_not_shipped() -> None:
    """The host palette must not compete with a separately loaded vendor theme."""
    html = _index_html()
    assert "highlight-github.min.css" not in html
    assert not (VENDOR_DIR / "highlight-github.min.css").exists()
    assert "styles/github.min.css" not in (REPO_ROOT / "devtools/vendor_assets.py").read_text(
        encoding="utf-8"
    )


def test_vendored_toml_is_the_official_hljs_ini_grammar() -> None:
    """Sanity check: the vendored file is the canonical highlight.js 11.9.0
    grammar (registers as 'ini' with toml as an alias)."""
    text = (VENDOR_DIR / "highlight-toml.min.js").read_text(encoding="utf-8")
    assert "Highlight.js 11.9.0" in text or "`ini` grammar compiled for Highlight.js 11.9.0" in text
    assert 'aliases:["toml"]' in text
    assert 'hljs.registerLanguage("ini"' in text


def test_chart_js_is_published_on_demand_rather_than_loaded_eagerly() -> None:
    """Chart.js is 297,531 bytes read by one view.

    Eager loading measured about 374 ms of every document's load event whether
    or not that view was ever opened, so the shell must publish it as a bundle
    for asset_loader.js and must not put it in the chain that runs on load.
    See docs/development.md "Asset Loading Tiers".
    """
    html = _index_html()
    bundles_start = html.index("window.METABROWSER_ASSET_BUNDLES=")
    bundles = html[bundles_start : html.index("</script>", bundles_start)]
    chain_start = html.index("var assets = ")
    chain = html[chain_start : html.index("</script>", chain_start)]

    for name in (
        "vendor/chart.umd.min.js",
        "vendor/chartjs-plugin-annotation.min.js",
        "vendor/chartjs-adapter-date-fns.bundle.min.js",
    ):
        assert name in bundles, f"on-demand asset missing from the bundle map: {name}"
        assert name not in chain, f"on-demand asset is still loaded on every page: {name}"

    # The prefetched tier still runs on load: a source view that highlights a
    # beat late is visible, and these are small.
    for name in ("vendor/highlight.min.js", "vendor/mustache.min.js"):
        assert name in chain, f"prefetched asset missing from the load chain: {name}"

    # The loader has to be present before anything can ask it for a bundle.
    assert "/static/asset_loader.js" in html


def test_prefetched_assets_wait_for_idle_rather_than_dom_content_loaded() -> None:
    """The prefetched tier must not run inside the DOMContentLoaded window.

    Starting the chain there puts it in the same window as the tree fetch and
    keeps the ``load`` event open until it finishes: measured on the 100,000-file
    bench corpus, median of three cold loads, ``load`` was 3,883 ms with the
    chain on DOMContentLoaded and 750 ms with it on the first idle callback.
    The timeout is the floor, so a busy main thread cannot defer highlighting
    forever. See docs/development.md "Asset Loading Tiers".
    """
    html = _index_html()
    chain_start = html.index("var assets = ")
    chain = html[chain_start : html.index("</script>", chain_start)]

    assert "requestIdleCallback" in chain, "the prefetched chain no longer waits for idle"
    assert f"timeout: {server.PREFETCH_IDLE_TIMEOUT_MS}" in chain
    assert f"setTimeout(start, {server.PREFETCH_FALLBACK_DELAY_MS})" in chain
    # DOMContentLoaded may still be the earliest point the chain is *scheduled*
    # from, but it must schedule rather than start.
    assert 'addEventListener("DOMContentLoaded", schedule' in chain
    assert 'addEventListener("DOMContentLoaded", start' not in chain


def test_local_core_scripts_load_before_optional_assets() -> None:
    """The shell must not wait on optional libraries before registering its app."""
    html = _index_html()
    app_pos = html.index("/static/app.js")
    optional_pos = html.index("vendor/highlight.min.js")
    assert app_pos < optional_pos
    assert "metabrowser:optional-assets-loaded" in html


def test_strict_sdk_dependencies_load_before_the_legacy_adapter() -> None:
    html = _index_html()
    sdk_position = html.index("/static/plugin_sdk.js")
    for name in (
        "request_error.js",
        "formatters.js",
        "inventory_scope.js",
        "contribution_registry.js",
        "resource_context.js",
        "view_state.js",
    ):
        assert html.index(f"/static/{name}") < sdk_position


def test_duplicate_markdown_assets_are_absent() -> None:
    html = _index_html()
    assert "dompurify" not in html.lower()
    assert "marked.min.js" not in html


def test_index_starts_at_root_overview_even_when_readme_exists(tmp_path: Path) -> None:
    """No-hash startup leaves README discovery to the root Overview."""
    previous_root = server._resolved_root_dir()
    try:
        (tmp_path / "README.md").write_text("# Fast first paint\n")
        server._set_root_dir(tmp_path)
        html = _index_html()
    finally:
        server._set_root_dir(previous_root)

    assert "METABROWSER_INITIAL_PATH" not in html
