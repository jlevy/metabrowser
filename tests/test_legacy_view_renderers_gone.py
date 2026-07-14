"""Phase 3g — VIEW_RENDERERS / VIEW_CONTAINER_STYLES / renderXTab gone from app.js.

After Phase 3c–3f migrated each built-in plugin's renderers into its
own ``index.js``, Phase 3g deletes the legacy fallback dispatch and
the now-unused function definitions. Every (kind, viewId) pair must
go through the plugin registry; no shell-side function table.

Regression guards so the legacy machinery doesn't reappear on
future changes.
"""

from __future__ import annotations

from pathlib import Path

APP_JS = Path(__file__).resolve().parent.parent / "src" / "metabrowser" / "static" / "app.js"


def _src() -> str:
    return APP_JS.read_text(encoding="utf-8")


def test_view_renderers_dict_is_gone() -> None:
    src = _src()
    # The dict declaration line — historically `var VIEW_RENDERERS = {`.
    assert "VIEW_RENDERERS" not in src, "VIEW_RENDERERS dict must not return"


def test_view_container_styles_dict_is_gone() -> None:
    src = _src()
    assert "VIEW_CONTAINER_STYLES" not in src, "VIEW_CONTAINER_STYLES must not return"


def test_render_x_tab_function_definitions_gone_from_shell() -> None:
    src = _src()
    forbidden = [
        "function renderLogTab(",
        "function renderRawTab(",
        "function renderMarkdownTab(",
        "function renderSourceTab(",
        "function renderChartsTab(",
        "function renderStatsTab(",
        "function renderVisualTab(",
        "function renderResourceReportTab(",
        "function renderResourceTreemapTab(",
    ]
    for needle in forbidden:
        assert needle not in src, (
            f"app.js must not define legacy renderer {needle!r} — moved to plugin"
        )


def test_markdown_helpers_gone_from_shell() -> None:
    """splitFrontmatter + openLinksInNewTab + wrapMarkdownTables +
    renderFrontmatterBlock all moved into the markdown plugin."""
    src = _src()
    forbidden = [
        "function splitFrontmatter(",
        "function openLinksInNewTab(",
        "function wrapMarkdownTables(",
        "function renderFrontmatterBlock(",
    ]
    for needle in forbidden:
        assert needle not in src, (
            f"app.js must not define markdown helper {needle!r} — moved to plugin"
        )


def test_agent_log_helpers_gone_from_shell() -> None:
    """renderLogEvent + renderFilterBar + renderSummary + logStat +
    activeKindFilters + toggleKindFilter all moved into agent-log plugin."""
    src = _src()
    forbidden = [
        "function renderLogEvent(",
        "function renderFilterBar(",
        "function renderSummary(",
        "function logStat(",
        "function toggleKindFilter(",
    ]
    for needle in forbidden:
        assert needle not in src, (
            f"app.js must not define agent-log helper {needle!r} — moved to plugin"
        )


def test_render_file_uses_unknown_view_empty_state() -> None:
    """The fallback branch must paint 'Unknown view' rather than dispatching
    through a function table — proves the cut is real."""
    src = _src()
    assert "Unknown view:" in src, "Phase 3g empty-state must be present"
    # Negative: the fallback branch must NOT call into a function table.
    assert "VIEW_RENDERERS[v.id]" not in src


def test_no_legacy_for_now_comments_in_builtin_plugins() -> None:
    """Phase 3 deleted every 'renderers stay in app.js for now' comment
    from the built-in plugins. Regression guard."""
    builtin_root = APP_JS.parent.parent / "builtin_plugins"
    forbidden_phrases = [
        "stay in app.js",
        "lives in app.js",
        "live in app.js",
        "Reserve namespace",
        "renderers (renderLogTab",
        "renderers (renderMarkdownTab",
    ]
    for index_js in builtin_root.glob("*/index.js"):
        text = index_js.read_text(encoding="utf-8")
        for phrase in forbidden_phrases:
            assert phrase not in text, (
                f"{index_js.relative_to(builtin_root.parent)} contains legacy phrase {phrase!r}"
            )


def test_no_legacy_for_now_comments_in_builtin_manifests() -> None:
    builtin_root = APP_JS.parent.parent / "builtin_plugins"
    forbidden_phrases = [
        "for now",
        "preserves the convention",
        "no views in the legacy",
    ]
    for manifest in builtin_root.glob("*/manifest.toml"):
        text = manifest.read_text(encoding="utf-8")
        for phrase in forbidden_phrases:
            assert phrase not in text, (
                f"{manifest.relative_to(builtin_root.parent)} contains legacy phrase {phrase!r}"
            )


def test_container_class_drives_outer_div_style() -> None:
    """View-level container_class field on [[view]] replaced the
    VIEW_CONTAINER_STYLES dict; the manifest classifier surfaces it
    on the api/file response so the shell can pick it up at render
    time."""
    src = _src()
    assert "view.container_class" in src
