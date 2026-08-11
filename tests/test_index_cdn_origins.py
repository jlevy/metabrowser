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
    """The page must be loadable fully offline: no external src/href."""
    html = _index_html()
    external = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
    assert external == [], f"external asset references remain: {external}"
    assert "cdn.jsdelivr.net" not in html
    assert "cdnjs.cloudflare.com" not in html


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


def test_local_core_scripts_load_before_optional_assets() -> None:
    """The shell must not wait on optional libraries before registering its app."""
    html = _index_html()
    app_pos = html.index("/static/app.js")
    optional_pos = html.index("vendor/highlight.min.js")
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
