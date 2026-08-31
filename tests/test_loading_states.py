"""Loading states are shapes, not sentences.

`docs/design-system.md` ("Loading States Are Shapes, Not Sentences")
says a loading state takes the shape of the content rather than
announcing itself: a skeleton block where the geometry is known, a
neutral spinner where it is not. Screen-reader text is required and is
explicitly not a violation.

Prose alone does not hold — the Git panel drifted back to
"Loading history…" while that rule was already written for spinners. This
turns it into a gate, and the allowlist below is the record of what has
not been converted yet rather than a set of permanent exemptions.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BROWSER_DIRS = (
    REPO_ROOT / "src/metabrowser/static",
    REPO_ROOT / "src/metabrowser/builtin_plugins",
)

# Visible loading copy that predates the rule. Each entry is a debt, not
# a dispensation: converting one means deleting its line here. Keyed by
# repository-relative path so a moved file fails loudly. Empty because
# every known case is converted — a new entry needs a reason in review.
KNOWN_VISIBLE_LOADING_TEXT: dict[str, int] = {}

# "Loading…" inside an sr-only span or an aria-label is the accessible
# name the rule requires, so both are stripped before counting.
_SR_ONLY_SPAN = re.compile(r'<span class="sr-only">[^<]*</span>')
_ARIA_LABEL = re.compile(r'aria-label="[^"]*"')
_ARIA_LABEL_CALL = re.compile(r'setAttribute\(\s*"aria-label"\s*,\s*"[^"]*"\s*\)')
# The DOM-built form of the same accessible name:
#     node.className = "sr-only";
#     node.textContent = "Loading …";
_SR_ONLY_ASSIGNED = re.compile(
    r'(\w+)\.className\s*=\s*"sr-only";\s*\1\.textContent\s*=\s*"[^"]*";'
)
_LOADING_TEXT = re.compile(r'["\'>]\s*Loading\b[^"\'<]*')
# Comments discuss this rule by name, so they are stripped before the
# scan; otherwise documenting the policy trips the check that enforces it.
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"^\s*//.*$", re.MULTILINE)


def _browser_sources() -> list[Path]:
    files: list[Path] = []
    for directory in BROWSER_DIRS:
        files.extend(sorted(directory.rglob("*.js")))
    return files


def _visible_loading_hits(text: str) -> list[str]:
    stripped = _LINE_COMMENT.sub("", _BLOCK_COMMENT.sub("", text))
    stripped = _SR_ONLY_SPAN.sub("", stripped)
    stripped = _ARIA_LABEL.sub("", stripped)
    stripped = _ARIA_LABEL_CALL.sub("", stripped)
    stripped = _SR_ONLY_ASSIGNED.sub("", stripped)
    return _LOADING_TEXT.findall(stripped)


def test_no_new_visible_loading_text() -> None:
    """A new visible "Loading…" string fails the build."""
    actual: dict[str, int] = {}
    for path in _browser_sources():
        hits = _visible_loading_hits(path.read_text(encoding="utf-8"))
        if hits:
            actual[str(path.relative_to(REPO_ROOT))] = len(hits)

    unexpected = {
        path: count
        for path, count in actual.items()
        if count > KNOWN_VISIBLE_LOADING_TEXT.get(path, 0)
    }
    assert not unexpected, (
        "visible loading text added; use a skeleton block or a spinner with an "
        f"sr-only name instead (see docs/design-system.md): {unexpected}"
    )

    # A converted file must drop out of the allowlist, so the list cannot
    # outlive the debt it records.
    stale = {
        path: expected
        for path, expected in KNOWN_VISIBLE_LOADING_TEXT.items()
        if actual.get(path, 0) < expected
    }
    assert not stale, f"allowlist is stale, lower or remove these entries: {stale}"


def test_the_git_panel_is_free_of_visible_loading_text() -> None:
    """The panel this rule was written for stays converted."""
    panel = REPO_ROOT / "src/metabrowser/static/git-panel.js"
    assert not _visible_loading_hits(panel.read_text(encoding="utf-8"))
