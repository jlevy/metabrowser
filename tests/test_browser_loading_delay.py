"""Structural checks for flicker-free transient loading states."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = REPO_ROOT / "src" / "metabrowser" / "static"
PLUGIN_ROOT = REPO_ROOT / "src" / "metabrowser" / "builtin_plugins"


def test_transient_loading_utility_has_a_short_quiet_period() -> None:
    css = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    assert "--loading-state-delay: 30ms;" in css
    start = css.index(".mb-delayed-loading {")
    block = css[start : start + 300]
    assert "visibility: hidden;" in block
    assert (
        "animation: mb-delayed-loading-reveal 0s linear var(--loading-state-delay) forwards;"
        in block
    )
    assert "@keyframes mb-delayed-loading-reveal" in css
    assert "visibility: visible;" in css[css.index("@keyframes mb-delayed-loading-reveal") :][:200]


def test_every_fast_renderer_uses_the_delayed_loading_utility() -> None:
    sources = {
        "shell": STATIC_ROOT / "app.js",
        "Markdown": PLUGIN_ROOT / "markdown" / "rendered.js",
        "folder Overview": PLUGIN_ROOT / "folder" / "overview.js",
        "Treemap": PLUGIN_ROOT / "folder" / "treemap.js",
        "agent-log charts": PLUGIN_ROOT / "agent_log" / "index.js",
    }

    for label, path in sources.items():
        source = path.read_text(encoding="utf-8")
        assert "mb-delayed-loading" in source, f"{label} exposes an immediate loading flash"


def test_shell_keeps_the_previous_preview_during_fast_fetches() -> None:
    app = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    select_file = app[
        app.index("async function selectFile(path, skipHistory, preferredViewId)") : app.index(
            "// ── File rendering"
        )
    ]

    assert "var LOADING_INDICATOR_DELAY_MS = 120;" in app
    assert select_file.index("loadingIndicatorTimer = setTimeout") < select_file.index(
        "preview.innerHTML"
    )
