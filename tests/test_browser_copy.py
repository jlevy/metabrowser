"""Browser-facing status copy describes user impact, not implementation details."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.test_reader_messages import extract, shipped_scripts

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "metabrowser" / "static"
BUILTINS = ROOT / "src" / "metabrowser" / "builtin_plugins"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_shell_messages_explain_state_and_recovery() -> None:
    app = _read(STATIC / "app.js")
    composition = _read(STATIC / "view-composition.js")
    styles = _read(STATIC / "styles.css")

    assert "Could not load files. Reload the page to try again." in app
    assert "File list incomplete." in app
    assert "some files and folders are not shown." in app
    assert "Could not load this folder. Collapse and reopen it to try again." in app
    assert "Could not load more content.</strong> Select Load more to try again." in app
    assert "No files were modified in the past" in app
    assert "No preview is available for this binary file" in app
    assert "function responseErrorDetail(body)" in app
    assert "new Error(responseErrorDetail(text))" in app
    assert "Could not display this view. Reload the page to try again." in composition
    assert "function previewErrorHtml(summary, detail)" in app
    assert 'class="preview-error-title"' in app
    assert 'class="preview-error-detail"' in app
    assert ".preview-error {" in styles
    assert "flex-direction: column;" in styles
    assert "max-width: var(--preview-message-max-width);" in styles

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
    markdown = _read(BUILTINS / "markdown" / "index.js") + _read(
        BUILTINS / "markdown" / "rendered.js"
    )
    agent_log = _read(BUILTINS / "agents" / "agent-log.js")
    charts = _read(STATIC / "charts.js")

    assert "mb.renderSourceView(container, raw)" in structured
    assert "The source view is unavailable" not in structured
    assert "Reload the page to try again." not in structured
    assert "Empty or unparseable file." not in structured
    assert "Could not render this document." in markdown
    assert "Raw content truncated. Showing at most" in agent_log
    assert "Loading charts…" in agent_log
    assert "Charts are unavailable. Reload the page to try again." in charts
    assert "Chart.js not loaded" not in charts


def test_search_copy_explains_incomplete_indexing() -> None:
    palette = _read(STATIC / "search-palette.js")
    controller = _read(STATIC / "search-controller.js")
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
    controls = _read(STATIC / "filter-controls.js")

    assert "Files modified in the past ${_RECENT_WINDOW_SECONDS.live} seconds" in app
    assert 'const tip = opt.tip ? ` data-tip-text="${esc(opt.tip)}"` : "";' in controls


# -- Refresh, Retry, and Reload page -------------------------------------------------------

# "Refresh" asks again in place; the page's own reload is "Reload the page". The page itself,
# not a page's part: "Refresh this page's checks" names what it refreshes.
_REFRESH_THE_PAGE = re.compile(r"(?<![\w-])[Rr]efresh(es|ed|ing)? (the|this) page\b(?!['’])")
# A sentence names a Refresh on screen by its label, capitalized. A lowercase "refresh to …"
# names no control, so it is the browser's reload, as the Files tab's "Change the filter or
# refresh to try again." was where the tab has no Refresh.
_BARE_REFRESH_REMEDY = re.compile(r"(?<![\w-])refresh to\b")
# "Reload" is always the whole page, and names it: "Reload page", "Reload the page",
# "Reloads the page". A bare "Reload" was the Pulls tab's Refresh, beside the PR page's.
_RELOAD = re.compile(r"(?<![\w-])[Rr]eload(s|ed|ing)?(?![\w-])(?! (the |this )?page\b)")
# A key, a kind, or an event name ("reload" as an offer's kind), which no reader sees.
_IDENTIFIER = re.compile(r"[a-z0-9_.:-]+")
# Control labels the inventory found, or their usual synonyms, each with the word it is now:
# a label is the verb alone, and the sentence beside it says what the verb acts on.
_RETIRED_LABELS = {
    "Reload": "Refresh, or Reload page for the page itself",
    "Reload history": "Refresh",
    "Retry loading history": "Retry",
    "Retry changes": "Retry",
    "Fetch changes": "Fetch",
    "Try again": "Retry",
    "Refetch": "Refresh",
    "Re-fetch": "Refresh",
    "Rescan": "Refresh",
    "Update now": "Refresh",
    "Check again": "Refresh",
}


def _browser_literals() -> list[tuple[str, int, str]]:
    """(file, line, text) for each string and template a reader could see.

    The reader-message check's extractor reads the shipped scripts with the TypeScript
    parser, so a template across lines is one text, and a console argument, a built-in
    error's argument, a property key, or a comparison operand, which no reader sees, is
    left out.
    """
    return [
        (str(Path(record["file"]).relative_to(ROOT)), record["line"], record["text"])
        for record in extract(shipped_scripts())
        if record["kind"] in ("string", "template") and record["context"] == "text"
    ]


def _asking_again_problems(text: str) -> list[str]:
    """What is wrong with *text* as a label, tooltip, or sentence that asks again."""
    if _IDENTIFIER.fullmatch(text):
        return []
    problems: list[str] = []
    if _REFRESH_THE_PAGE.search(text):
        problems.append("refreshes the page; say Reload the page")
    if _BARE_REFRESH_REMEDY.search(text):
        problems.append("offers a refresh no control makes; say Reload the page")
    if _RELOAD.search(text):
        problems.append("reloads something other than the page")
    if text in _RETIRED_LABELS:
        problems.append(f"is now {_RETIRED_LABELS[text]}")
    return problems


@pytest.mark.parametrize(
    ("text", "wrong"),
    [
        ("Refresh the page to try again.", True),
        ("Reload to try again.", True),
        ("Change the filter or refresh to try again.", True),
        ("Reload", True),
        ("Retry changes", True),
        ("Reload the page to try again.", False),
        ("Reload page", False),
        ("Refresh this page's checks", False),
        ("Changes took too long to prepare. Refresh to try again.", False),
        ("Could not refresh this folder.", False),
        ("reload", False),
    ],
)
def test_the_asking_again_rules_tell_right_from_wrong(text: str, wrong: bool) -> None:
    assert bool(_asking_again_problems(text)) is wrong


def test_asking_again_has_one_word_for_each_meaning() -> None:
    """Refresh asks again in place, Retry repeats what failed, and Reload is the page.

    docs/design-system.md, "Refresh, Retry, and Reload Page", says what each word means and
    why there are three. The owner found a Reload in the navigation column and a Refresh on
    a pull request's page that did the same thing (2026-11-24); this holds the words apart
    in every shipped label, tooltip, and sentence.
    """

    literals = _browser_literals()
    texts = {text for _, _, text in literals}
    # Positive controls: the scan reads the words it guards, so a pattern that stopped
    # matching cannot pass by finding nothing.
    for present in ("Refresh", "Retry", "Fetch", "Reload page"):
        assert present in texts, f"the scan no longer finds the {present!r} label"
    assert any("Reload the page to try again." in text for text in texts)

    problems = [
        f"{where}:{line}: {text!r} {problem}"
        for where, line, text in literals
        for problem in _asking_again_problems(text)
    ]
    assert not problems, "\n".join(problems)
