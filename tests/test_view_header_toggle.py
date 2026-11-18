"""The GitHub toggle draws the app's own marks, not look-alikes.

The owner asked for "a gray version of the metabrowser icon and the github icon" (mb-zp7y).
The stylesheet draws both as masks (``.view-header-toggle-mark`` in ``static/styles.css``),
so each is a copy: the Metabrowser mark of the app icon's glyph group, which
``apps/macos/AppIcon/make-glyphs.swift`` writes into ``AppIconMarkGeometry.swift``, and the
GitHub mark of the one ``static/plugin-sdk-views.js`` draws beside a View on GitHub link.
This holds each copy to its source, path for path and frame for frame, so neither drifts.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
STYLES = ROOT / "src" / "metabrowser" / "static" / "styles.css"
GEOMETRY = ROOT / "apps" / "macos" / "Sources" / "ShellCore" / "App" / "AppIconMarkGeometry.swift"
VIEWS = ROOT / "src" / "metabrowser" / "static" / "plugin-sdk-views.js"


def _mask(selector: str) -> str:
    css = STYLES.read_text(encoding="utf-8")
    start = css.index(f"{selector} {{")
    body = css[start : css.index("}", start)]
    found = re.search(r'url\("data:image/svg\+xml,([^"]+)"\)', body)
    assert found is not None, f"{selector} draws no mask"
    return unquote(found.group(1))


def test_the_metabrowser_mark_is_the_app_icons_glyphs() -> None:
    svg = _mask(".view-header-toggle-metabrowser > .view-header-toggle-mark")
    swift = GEOMETRY.read_text(encoding="utf-8")
    paths = re.findall(r'path: "([^"]+)"', swift)
    ink = re.search(r"x: ([\d.]+), y: ([\d.]+), width: ([\d.]+), height: ([\d.]+)", swift)
    assert ink is not None and len(paths) == 2
    assert re.findall(r"<path d='([^']+)'/>", svg) == paths
    assert f"viewBox='{' '.join(ink.groups())}'" in svg


def test_the_github_mark_is_the_one_view_on_github_draws() -> None:
    svg = _mask(".view-header-toggle-mark")
    views = VIEWS.read_text(encoding="utf-8")
    source = re.search(
        r'github:\n\s+\'<svg viewBox="0 0 16 16" fill="currentColor"><path d="([^"]+)"/></svg>\'',
        views,
    )
    assert source is not None
    assert re.findall(r"<path d='([^']+)'/>", svg) == [source.group(1)]
    assert "viewBox='0 0 16 16'" in svg
