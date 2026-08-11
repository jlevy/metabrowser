"""Browser-facing status copy describes user impact, not implementation details."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "metabrowser" / "static"
BUILTINS = ROOT / "src" / "metabrowser" / "builtin_plugins"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_shell_messages_explain_state_and_recovery() -> None:
    app = _read(STATIC / "app.js")

    assert "Could not load files. Refresh the page to try again." in app
    assert "File list incomplete." in app
    assert "some files and folders are not shown." in app
    assert "Could not load this folder. Collapse and reopen it to try again." in app
    assert "Could not load more content.</strong> Select Load more to try again." in app
    assert "No files were modified in the past" in app
    assert "No preview is available for this binary file" in app
    assert "This JSONL file is too large to preview." in app
    assert "function responseErrorDetail(body, status)" in app
    assert "new Error(responseErrorDetail(text, resp.status))" in app
    assert "Could not display this view. Refresh the page to try again." in app

    for internal_wording in (
        "Failed to load tree",
        "Tree partial:",
        "Unable to load folder",
        "Plugin render error:",
        "Unknown view:",
        "Log file too large for browser parsing",
        "tail -f ",
    ):
        assert internal_wording not in app


def test_plugin_messages_use_product_language() -> None:
    structured = _read(BUILTINS / "structured" / "index.js")
    markdown = _read(BUILTINS / "markdown" / "index.js")
    agent_log = _read(BUILTINS / "agent_log" / "index.js")
    charts = _read(STATIC / "charts.js")

    assert "The source view is unavailable. Refresh the page to try again." in structured
    assert "Could not load structured data. Refresh the page to try again." in structured
    assert "Empty or unparseable file." not in structured
    assert "Could not render this document." in markdown
    assert "Raw content truncated. Showing at most" in agent_log
    assert "Loading charts…" in agent_log
    assert "Charts are unavailable. Refresh the page to try again." in charts
    assert "Chart.js not loaded" not in charts


def test_search_copy_explains_incomplete_indexing() -> None:
    palette = _read(STATIC / "search_palette.js")
    controller = _read(STATIC / "search_controller.js")
    copy = palette + controller

    assert "Search includes ${scope}." in palette
    assert "No matches in ${searchScope}." in controller
    assert "Scanning continues." in copy
    assert "Showing the top matches." in copy
    assert "Type a filename to search" not in copy
    assert "No files match your search." not in copy
    assert "files are searchable" not in copy
    assert "More files may appear as scanning continues." not in copy
    assert "stale result" not in palette
    assert "Local coverage is incomplete." not in copy
    assert "observed files" not in copy


def test_live_filter_exposes_its_exact_cutoff() -> None:
    app = _read(STATIC / "app.js")
    controls = _read(STATIC / "filter_controls.js")

    assert "Files modified in the past ${_RECENT_WINDOW_SECONDS.live} seconds" in app
    assert 'const title = opt.title ? ` title="${esc(opt.title)}"` : "";' in controls
