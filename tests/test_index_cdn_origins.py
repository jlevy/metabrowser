"""CDN consolidation — single origin (jsdelivr) + locally-vendored TOML grammar.

Background: the index template used to mix two CDN origins (cdnjs +
jsdelivr) for third-party scripts, which defeats HTTP/2 connection
coalescing and forces a second TLS handshake. The TOML language module
for highlight.js 11.9.0 is community-maintained and not on jsdelivr,
so we vendor it locally under ``static/vendor/`` rather than keep
cdnjs around for one file.

These tests assert:
1. No cdnjs URL appears in the rendered <head> / <body>.
2. ``<link rel="preconnect" href="https://cdn.jsdelivr.net">`` is emitted.
3. The TOML language module is served from /static/vendor/.
4. Floating-version range tags (chart.js@4, etc.) are pinned to
   exact versions so jsdelivr's long-cache layer can keep responses
   immutable.
5. The vendored TOML file is the official ``ini`` grammar from
   ``@highlightjs/cdn-assets@11.9.0`` (which carries TOML via
   ``aliases:["toml"]``).
6. Local core assets load before optional CDN assets so first paint
   never waits on jsdelivr.
7. Every fetched CDN asset pins a Subresource Integrity hash so a
   tampered CDN response fails closed instead of executing.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import Mock

from metabrowser import server

VENDOR_TOML = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "metabrowser"
    / "static"
    / "vendor"
    / "highlight-toml.min.js"
)


def _index_html() -> str:
    return bytes(asyncio.run(server.index(Mock())).body).decode("utf-8")


def test_no_cdnjs_origin_in_index() -> None:
    """The cdnjs origin must not appear anywhere in the rendered page."""
    html = _index_html()
    assert "cdnjs.cloudflare.com" not in html, (
        "All third-party scripts/links should be on a single origin (jsdelivr)"
    )


def test_preconnect_to_jsdelivr_is_emitted() -> None:
    """A <link rel=preconnect> entry saves the TLS handshake on the first
    third-party fetch; without it, the browser delays connection setup
    until the first <script> tag is parsed."""
    html = _index_html()
    assert '<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>' in html, (
        "preconnect for jsdelivr must be in <head>"
    )


def test_highlight_stylesheet_is_not_render_blocking() -> None:
    """Syntax-highlight CSS is visual enhancement, not first-paint critical CSS."""
    html = _index_html()
    assert (
        'href="https://cdn.jsdelivr.net/npm/highlight.js@11.9.0/styles/github.min.css" '
        'integrity="sha384-'
    ) in html
    assert 'media="print" onload="this.media=\'all\'"' in html


def test_all_cdn_references_carry_subresource_integrity() -> None:
    """Every jsdelivr asset must pin an SRI hash alongside its exact version.

    Version pinning alone leaves the browser trusting whatever bytes the CDN
    serves; ``integrity`` makes substitution fail closed (the loader's onerror
    path degrades gracefully). The preconnect hint has no fetched body and is
    exempt. The vendored local grammar is same-origin and needs no SRI.
    """
    html = _index_html()

    # The stylesheet <link> tags (including the noscript fallback) carry
    # integrity + crossorigin.
    for fragment in html.split("<link "):
        if "cdn.jsdelivr.net" not in fragment or 'rel="preconnect"' in fragment:
            continue
        head = fragment.split(">", 1)[0]
        assert 'integrity="sha384-' in head, f"CDN <link> without SRI: {head[:120]}"
        assert 'crossorigin="anonymous"' in head, f"CDN <link> without crossorigin: {head[:120]}"

    # Every entry in the optional-asset loader list with a jsdelivr src
    # declares an integrity hash, and the loader applies it. The list is
    # embedded as a JSON literal: ``var assets = [...];``.
    assets_json = html.split("var assets = ", 1)[1].split(";", 1)[0]
    assets = json.loads(assets_json)
    assert assets, "optional-asset list unexpectedly empty"
    for asset in assets:
        if "cdn.jsdelivr.net" in asset["src"]:
            assert asset.get("integrity", "").startswith("sha384-"), (
                f"CDN script without SRI: {asset['src']}"
            )
    assert "script.integrity = asset.integrity" in html
    assert 'script.crossOrigin = "anonymous"' in html


def test_toml_language_is_served_from_local_vendor() -> None:
    """The TOML grammar is community-maintained and not on jsdelivr; we
    vendor the official ``@highlightjs/cdn-assets@11.9.0/languages/ini.min.js``
    (which carries TOML via the ``aliases:["toml"]`` field) under
    /static/vendor/."""
    html = _index_html()
    assert "/static/vendor/highlight-toml.min.js" in html
    # And the file must actually exist (so the wheel ships it).
    assert VENDOR_TOML.is_file(), f"vendored file missing: {VENDOR_TOML}"


def test_vendored_toml_is_the_official_hljs_ini_grammar() -> None:
    """Sanity check: the vendored file is the canonical highlight.js 11.9.0
    grammar (registers as 'ini' with toml as an alias)."""
    text = VENDOR_TOML.read_text(encoding="utf-8")
    assert "Highlight.js 11.9.0" in text or "`ini` grammar compiled for Highlight.js 11.9.0" in text
    assert 'aliases:["toml"]' in text
    assert 'hljs.registerLanguage("ini"' in text


def test_floating_range_tags_are_pinned() -> None:
    """jsdelivr's long-cache only kicks in for fully-pinned URLs; range
    tags (chart.js@4, etc.) force re-validation. Pin every
    URL to a complete semver so cache hits are immutable."""
    html = _index_html()

    # These exact-version substrings must be present (script src URLs).
    expected_pins = [
        "highlight.js@11.9.0/styles/github.min.css",
        "@highlightjs/cdn-assets@11.9.0/highlight.min.js",
        "chart.js@4.5.1/dist/chart.umd.min.js",
        "chartjs-plugin-annotation@3.1.0/",
        "chartjs-adapter-date-fns@3.0.0/",
        "elkjs@0.10.0/lib/elk.bundled.js",
        "mustache@4.2.0/mustache.min.js",
    ]
    for pin in expected_pins:
        assert pin in html, f"pin missing from index template: {pin}"

    # Negative: a bare @4 / @13 / @3 in a script src would be a regression.
    # We allow them inside comments (e.g. "range tags chart.js@4 …"), but not
    # in actual src= attributes — search for the exact src=" prefix.
    forbidden_floats = [
        'src="https://cdn.jsdelivr.net/npm/chart.js@4/',
        'src="https://cdn.jsdelivr.net/npm/chart.js@4"',
        'src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3/',
        'src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3/',
    ]
    for f in forbidden_floats:
        assert f not in html, f"floating range tag in src attribute: {f}"


def test_local_core_scripts_load_before_optional_assets() -> None:
    """The shell must not wait on CDN libraries before registering its app."""
    html = _index_html()
    app_pos = html.index("/static/app.js")
    optional_pos = html.index("@highlightjs/cdn-assets@11.9.0/highlight.min.js")
    assert app_pos < optional_pos
    assert "metabrowser:optional-assets-loaded" in html


def test_duplicate_markdown_assets_are_absent() -> None:
    html = _index_html()
    assert "dompurify" not in html.lower()
    assert "marked.min.js" not in html


def test_index_seeds_root_readme_for_immediate_preview(tmp_path: Path) -> None:
    """The root README preview is chosen without waiting for the tree index."""
    previous_root = server._resolved_root_dir()
    try:
        (tmp_path / "README.md").write_text("# Fast first paint\n")
        server._set_root_dir(tmp_path)
        html = _index_html()
    finally:
        server._set_root_dir(previous_root)

    assert 'window.METABROWSER_INITIAL_PATH="README.md"' in html
