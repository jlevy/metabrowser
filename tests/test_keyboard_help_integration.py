"""Shell integration checks for keyboard Help and navigation hints."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from metabrowser import server as proc_browser


def _render_index_html() -> str:
    class _FakeQuery:
        def get(self, key: str, default: str = "") -> str:
            return default

    class _FakeReq:
        def __init__(self) -> None:
            self.query_params = _FakeQuery()
            self.headers: dict[str, str] = {}

    response = asyncio.run(proc_browser.index(cast(Any, _FakeReq())))
    return response.body.decode() if isinstance(response.body, bytes) else str(response.body)


def test_help_assets_and_navigation_hint_host_have_stable_shell_order() -> None:
    html = _render_index_html()
    hints = html.index('id="nav-shortcut-hints"')
    progress = html.index('id="index-progress"')
    assert hints < progress
    assert 'aria-live="' not in html[hints : html.index(">", hints)]

    assets = (
        "/static/keyboard_shortcuts.js",
        "/static/overlay_layer.js",
        "/static/keyboard_help.js",
        "/static/search_palette.js",
        "/static/app.js",
    )
    positions = []
    for asset in assets:
        assert f'src="{asset}?v=' in html
        positions.append(html.index(asset))
    assert positions == sorted(positions)


def test_application_composes_one_help_runtime_before_quick_file() -> None:
    js = proc_browser.STATIC_DIR.joinpath("app.js").read_text()
    infrastructure = js[
        js.index("function initKeyboardInfrastructure()") : js.index(
            "function initQuickFileFinder()"
        )
    ]
    assert "MetabrowserKeyboardShortcuts.create" in infrastructure
    assert "MetabrowserKeyboardHelp.create" in infrastructure
    assert 'getElementById("nav-shortcut-hints")' in infrastructure
    assert "resolveApplicationFocusFallback" in infrastructure

    loaded = js[js.rindex('addEventListener("DOMContentLoaded", async () =>') :]
    assert loaded.index("initKeyboardInfrastructure();") < loaded.index("initQuickFileFinder();")
    assert loaded.count("initKeyboardInfrastructure();") == 1
