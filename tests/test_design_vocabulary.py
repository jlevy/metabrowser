"""Design-vocabulary agreements the stylesheet cannot state for itself.

Each check pins one cross-file agreement from ``docs/design-system.md``:
the disclosure chevron is one glyph everywhere it appears, row-like
activation targets share one height token, and their hover is the one
hover token. A failure here means a surface forked the vocabulary.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import get_args

from metabrowser.builtin_plugins.github.pull_readiness import Tone

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC = REPO_ROOT / "src" / "metabrowser" / "static"
BUILTIN_PLUGINS = "src/metabrowser/builtin_plugins"

CHEVRON_PATH = "m9 18 6-6-6-6"  # Lucide chevron-right


def _rule(css: str, selector: str) -> str:
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match is not None, f"selector not found: {selector}"
    return match.group(1)


def test_disclosure_chevron_is_one_glyph_everywhere() -> None:
    icons = (STATIC / "icons.js").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    # The registry's one leading chevron (tree rows, tally tree, diff bars, log events);
    # icons.js quotes attributes with double quotes.
    assert icons.count(f'd="{CHEVRON_PATH}"') == 1, "the registry's chevron forked or changed"
    # The section-disclosure mask draws the same path (single-quoted
    # inside the data URI).
    assert f"d='{CHEVRON_PATH}'" in styles, "section-disclosure mask forked the glyph"
    # Both color from the same token family.
    assert "--section-disclosure-chevron-color: var(--muted);" in styles
    assert "color: var(--muted);" in _rule(styles, ".toggle-chevron")


def test_diff_bar_uses_the_shared_chevron_and_registry() -> None:
    view = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/diff-view.js").read_text(
        encoding="utf-8"
    )
    assert 'shellIcon("toggle")' in view, "diff bar must lead with the registry's toggle glyph"


def test_row_targets_share_the_row_height_token() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    diff_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/styles.css").read_text(
        encoding="utf-8"
    )
    assert "--ui-row-height: 24px;" in styles, "the row-height token moved or changed"
    assert "min-height: var(--ui-row-height);" in _rule(styles, ".tree-item")
    assert "min-height: var(--ui-row-height);" in _rule(
        diff_css, ".metabrowser-diff-host .diff-file-bar"
    )


# ── Row text shares one baseline ───────────────────────────────────
#
# A two-size row centers its boxes and aligns its text on the baseline
# (docs/design-system.md, "Row Text Shares a Baseline"). The check below
# builds each registered row as a small element tree mirroring its
# renderer, then asks every stylesheet rule that sets baseline alignment
# which of those elements it could select. It is deliberately stricter
# than the cascade: a box must not be selected by any baseline rule at
# all, so a later override or a heavier selector cannot be what keeps it
# centered, and moving or deleting an exclusion fails here.


class _El:
    """An element in a row: its classes, its children, and, for a row's
    direct child, whether it is a text slot or a box."""

    def __init__(self, classes: str, *children: _El, role: str = "") -> None:
        self.classes = frozenset(classes.split())
        self.children = list(children)
        self.role = role
        self.parent: _El | None = None
        for child in children:
            child.parent = self

    def ancestors(self) -> list[_El]:
        found: list[_El] = []
        node = self.parent
        while node is not None:
            found.append(node)
            node = node.parent
        return found

    def descendants(self) -> list[_El]:
        found: list[_El] = []
        for child in self.children:
            found.append(child)
            found.extend(child.descendants())
        return found


def _split_top(text: str, separators: str) -> list[str]:
    """Split on separators that sit outside parentheses and brackets."""
    parts: list[str] = []
    depth = 0
    current = ""
    for char in text:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        if depth == 0 and char in separators:
            parts.append(current)
            current = ""
        else:
            current += char
    parts.append(current)
    return parts


def _style_rules(css: str) -> list[tuple[str, str]]:
    """Every style rule as (selector list, declarations), at-rules unwrapped."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    rules: list[tuple[str, str]] = []
    depth = 0
    prelude_start = 0
    body_start = 0
    prelude = ""
    quote = ""
    for index, char in enumerate(css):
        if quote:
            quote = "" if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char == "{":
            text = css[prelude_start:index].strip()
            if text.startswith("@"):
                prelude_start = index + 1
                continue
            if depth == 0:
                prelude, body_start = text, index + 1
            depth += 1
        elif char == "}":
            if depth == 0:
                prelude_start = index + 1
                continue
            depth -= 1
            if depth == 0:
                rules.append((prelude, css[body_start:index]))
                prelude_start = index + 1
        elif char == ";" and depth == 0:
            prelude_start = index + 1
    return rules


_SIMPLE = re.compile(
    r"\*|\.[\w-]+|#[\w-]+|\[[^\]]*\]|::?[\w-]+(?:\((?:[^()]|\([^()]*\))*\))?|[\w-]+"
)


def _matches_compound(compound: str, element: _El) -> bool:
    assert compound, "empty compound selector"
    consumed = "".join(_SIMPLE.findall(compound))
    assert consumed == compound, f"unsupported selector syntax: {compound!r}"
    for simple in _SIMPLE.findall(compound):
        if simple.startswith("::"):
            return False  # a pseudo-element is not the element
        if simple.startswith("."):
            if simple[1:] not in element.classes:
                return False
        elif simple.startswith((":is(", ":where(", ":not(", ":has(")):
            name, argument = simple[1:].split("(", 1)
            selectors = _split_top(argument[:-1], ",")
            if name == "has":
                hit = any(_matches_relative(s.strip(), element) for s in selectors)
            else:
                hit = any(_matches_complex(s.strip(), element) for s in selectors)
            if hit == (name == "not"):
                return False
        # Tags, ids, attributes, and state pseudo-classes may match: assume
        # they do, so the check errs toward flagging a box.
    return True


def _compounds(selector: str) -> list[str]:
    spaced = re.sub(r"\s*([>+~])\s*", r" \1 ", selector.strip())
    return [token for token in _split_top(spaced, " ") if token]


def _matches_complex(selector: str, element: _El) -> bool:
    tokens = _compounds(selector)
    if not _matches_compound(tokens[-1], element):
        return False
    rest = tokens[:-1]
    if not rest:
        return True
    combinator = rest[-1] if rest[-1] in ">+~" else " "
    left = " ".join(rest[:-1] if combinator != " " else rest)
    if combinator == ">":
        return element.parent is not None and _matches_complex(left, element.parent)
    if combinator == " ":
        return any(_matches_complex(left, ancestor) for ancestor in element.ancestors())
    siblings = element.parent.children if element.parent else [element]
    before = siblings[: siblings.index(element)]
    if combinator == "+":
        before = before[-1:]
    return any(_matches_complex(left, sibling) for sibling in before)


def _matches_relative(selector: str, element: _El) -> bool:
    tokens = _compounds(selector)
    if tokens[0] == ">":
        assert len(tokens) == 2, f"unsupported :has() argument: {selector!r}"
        return any(_matches_compound(tokens[1], child) for child in element.children)
    assert len(tokens) == 1, f"unsupported :has() argument: {selector!r}"
    return any(_matches_compound(tokens[0], node) for node in element.descendants())


_BASELINE_SELF = re.compile(r"align-self\s*:\s*(?:first\s+|last\s+)?baseline")
_BASELINE_ITEMS = re.compile(r"align-items\s*:\s*(?:first\s+|last\s+)?baseline")


def _baseline_rules() -> list[tuple[str, bool]]:
    """(complex selector, sets align-items) for every rule that aligns to a baseline."""
    sheets = [STATIC / "styles.css", *sorted((REPO_ROOT / BUILTIN_PLUGINS).glob("*/*.css"))]
    found: list[tuple[str, bool]] = []
    for sheet in sheets:
        for selectors, body in _style_rules(sheet.read_text(encoding="utf-8")):
            for is_items, pattern in ((False, _BASELINE_SELF), (True, _BASELINE_ITEMS)):
                if pattern.search(body):
                    found.extend((s.strip(), is_items) for s in _split_top(selectors, ","))
    return found


def _text(classes: str, *children: _El) -> _El:
    return _El(classes, *children, role="text")


def _box(classes: str, *children: _El) -> _El:
    return _El(classes, *children, role="box")


def _baseline_rows() -> list[tuple[str, str, _El]]:
    """(design-system table label, centering rule, row) per registered row.

    Each row mirrors its renderer's markup, once per state that turns a
    text slot into a box.
    """
    el, text, box = _El, _text, _box
    tree = "File tree row"  # renderTreeNodes, _buildRowHtml, renderContainerChildren
    diff_host = ".metabrowser-diff-host"
    rows = [
        (
            tree,
            ".tree-item",
            el(
                "tree-item tree-folder expanded",
                box("tree-toggle"),
                text("tree-item-name"),
                text("tree-item-age-inline", el("age-min")),
                text("size tree-item-size"),
            ),
        ),
        (
            tree,
            ".tree-item",
            el(
                "tree-item tree-file",
                box("tree-item-icon file-identity-icon"),
                text("tree-item-name"),
                text(
                    "tree-item-age-inline",
                    el("tree-item-age", el("age-min")),
                    el("tree-item-activity"),
                ),
                text("size tree-item-size"),
            ),
        ),
        (
            tree,
            ".tree-item",
            el(
                "tree-item tree-file file-active",
                box("tree-item-icon"),
                text("tree-item-name"),
                box("tree-item-age-inline", el("tree-item-age"), el("tree-item-activity")),
            ),
        ),
        (
            tree,
            ".tree-item",
            el(
                "tree-item tree-folder collapsed",
                box("tree-toggle"),
                text("tree-item-name"),
                box("tree-item-age-inline", el("tally-pending tally-pending-narrow")),
                box("size tally-pending tree-item-size"),
            ),
        ),
        (
            tree,
            ".tree-item",
            el(
                "tree-item tree-file tree-container collapsed",
                box("tree-toggle"),
                box("tree-item-icon file-identity-icon"),
                text("tree-item-name"),
            ),
        ),
        (
            tree,
            ".tree-item",
            el(
                "tree-item tree-file tree-container-child",
                text("tree-container-badge"),
                text("tree-item-name"),
            ),
        ),
        (
            tree,
            ".tree-item",
            el(
                "tree-item tree-file tree-container-child",
                box("tree-item-icon"),
                text("tree-item-name"),
            ),
        ),
        (
            "Git history row",  # renderRow in git-panel.js
            ".git-graph-body",
            el(
                "git-graph-body",
                box("git-graph-refs", el("git-ref git-ref-local")),
                text("git-graph-subject"),
                text("git-graph-meta", el("git-graph-age age-min")),
            ),
        ),
    ]
    # Diff file bar: renderFileBar in the diff plugin, inside its host.
    toggle = box(
        "diff-file-toggle expanded",
        box("diff-file-chevron"),
        text("diff-file-kind diff-file-kind-modified"),
        text("diff-file-path"),
    )
    # The change's stats and notes, after the copy control: a box at the path's size, which
    # centering puts on its baseline, with its own text on one baseline.
    facts = box(
        "diff-file-facts",
        text(
            "diff-file-stats",
            el("change-line", el("change-line-stats", el("diff-stat-add"), el("diff-stat-del"))),
        ),
        text("diff-file-note"),
    )
    # The bar is a centered row of boxes: the name's group, the toggle with the copy control
    # right after it and the change's stats; the View file or View on branch control, a box
    # at the path's size, which centering puts on its baseline; and the group at its end, a
    # file's Full | Concise | Source chooser behind its progress mark (`add` in diff-markdown.js).
    # Each group is a centered row of boxes too.
    lead = box(
        "diff-file-lead",
        toggle,
        box("icon-btn icon-btn-reveal diff-file-copy"),
        facts,
    )
    end = box(
        "diff-file-end",
        box("diff-markdown-progress"),
        box("diff-markdown-control"),
    )
    bar = el("diff-file-bar diff-file-bar-markdown", lead, box("diff-file-view"), end)
    el("content-body metabrowser-diff-host", el("diff-file", bar))
    rows.append(("Diff file bar", f"{diff_host} .diff-file-toggle", toggle))
    rows.append(("Diff file bar", f"{diff_host} .diff-file-facts", facts))
    rows.append(("Diff file bar", f"{diff_host} .diff-file-lead", lead))
    rows.append(("Diff file bar", f"{diff_host} .diff-file-end", end))
    rows.append(("Diff file bar", f"{diff_host} .diff-file-bar", bar))
    # A Pulls row is not one: its title is one run of inline text, and its change line sets
    # its text at one size on one line height and centers it (docs/design-system.md, "Row
    # Text Shares a Baseline"; mb-85op, mb-lqkb).
    return rows


def test_row_text_shares_one_baseline() -> None:
    """Row text of two sizes aligns on its baseline; boxes stay centered.

    Measured in Chromium before the rules, the smaller text sat above the
    larger by 0.75 px at device pixel ratio 2 and 0.25 px at 1 (tree rows,
    Git history rows, file and folder headers) and by 0.5 px at both (the
    diff bar's note); with them it is 0 px at both.
    """
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    diff_css = (REPO_ROOT / BUILTIN_PLUGINS / "diff/styles.css").read_text(encoding="utf-8")
    github_css = (REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css").read_text(encoding="utf-8")
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "### Row Text Shares a Baseline" in doc, "the row baseline rule lost its documentation"
    section = doc.split("### Row Text Shares a Baseline", 1)[1].split("\n### ", 1)[0]
    rules = _baseline_rules()
    for label, row_rule, row in _baseline_rows():
        assert f"| {label}" in section, f"{label} is missing from the design-system table"
        css = (
            diff_css
            if row_rule.startswith(".metabrowser-diff-host")
            else github_css
            if row_rule.startswith(".github-")
            else styles
        )
        # The row centers its children, so a box needs no rule of its own.
        assert "align-items: center;" in _rule(css, row_rule), f"{row_rule} stopped centering"
        for child in row.children:
            applying = [
                selector
                for selector, is_items in rules
                if _matches_complex(selector, row if is_items else child)
            ]
            name = " ".join(sorted(child.classes))
            if child.role == "text":
                assert applying, f"{label}: text slot .{name} does not opt in to the baseline"
            elif child.role == "box":
                assert not applying, f"{label}: box .{name} is baseline-aligned by {applying}"
    # A view header's eyebrow sets its text at one size and centers it, and its heading row
    # sets the title and the metadata line after it as one run of inline text, so the line
    # sits on the title's baseline as text does (docs/design-system.md, "View Headers"). No
    # flex baseline rule reaches either: an item holding only a pending skeleton, aligned
    # as a flex item, would sit the skeleton's bottom edge on the baseline.
    # The header's corner (`.view-header-end`) is neither row: a strut of the title's type
    # and the View on GitHub button, which opts in to the strut's baseline, the title's
    # first line's (mb-tatf), as a row's text does. tests/dom/view-header-chrome.mjs
    # measures the button's label and the title on one baseline.
    for selector, _is_items in rules:
        if selector.startswith(".view-header-end"):
            continue
        assert not re.search(r"\.(?:file-header|view-header)", selector), (
            f"{selector} aligns a view header's text to a baseline"
        )
    # The diff bar's stats and View file controls are centered boxes beside the toggle, so
    # they land on the path's baseline only at the path's own size: the toggle's, which its
    # path inherits, the stats', and the view's, all the main view's body size.
    for selector in (".diff-file-toggle", ".diff-file-facts", ".diff-file-view"):
        assert "font-size: var(--body-font-size);" in _rule(
            diff_css, f".metabrowser-diff-host {selector}"
        ), f"{selector} left the diff bar's one text size"
    assert "font-size" not in _rule(diff_css, ".metabrowser-diff-host .diff-file-path")
    # And at the toggle's line height, a button's `normal`: at the bar's 1.5, which a link
    # inherits, the link form sat 0.5 px above the path's baseline in Chrome and the button
    # form on it (Design Rule Measurements, "Row Baselines").
    for selector in (".diff-file-facts", ".diff-file-view"):
        assert "line-height: normal;" in _rule(diff_css, f".metabrowser-diff-host {selector}")
    assert "line-height" not in _rule(diff_css, ".metabrowser-diff-host .diff-file-toggle")


def test_disclosure_motion_is_one_recipe_everywhere() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    diff_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/styles.css").read_text(
        encoding="utf-8"
    )
    overview_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/folder/overview.css").read_text(
        encoding="utf-8"
    )
    github_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/github/styles.css").read_text(
        encoding="utf-8"
    )
    for css, selector in (
        (styles, ".tree-children"),
        (diff_css, ".metabrowser-diff-host .diff-file-body"),
        (diff_css, ".metabrowser-diff-host .diff-fold-group"),
        (overview_css, ".folder-overview-panel-body"),
        (github_css, ".github-pull-stack-members-body"),
    ):
        rule = _rule(css, selector)
        assert "height var(--transition-fast)" in rule, f"{selector} lost the travel"
        assert "interpolate-size: allow-keywords" in rule, f"{selector} lost keyword sizing"
    for css, selector in (
        (styles, ".tree-children-collapsed"),
        (diff_css, ".metabrowser-diff-host .diff-file-body-collapsed"),
        (diff_css, ".metabrowser-diff-host .diff-fold-collapsed"),
        (overview_css, ".folder-overview-panel-body-collapsed"),
        (github_css, ".github-pull-stack-members-body-collapsed"),
    ):
        rule = _rule(css, selector)
        assert "height: 0" in rule and "visibility: hidden" in rule, f"{selector} state drifted"
    # Class-driven collapse: the tree never toggles inline display.
    for name in ("app.js", "tree-expansion.js"):
        source = (STATIC / name).read_text(encoding="utf-8")
        assert "tree-children-collapsed" in source, f"{name} lost the collapse class"
    # A reveal the reader did not ask for lands in place. The rule must come
    # after the travel it cancels, which has the same specificity.
    instant = _rule(styles, ".tree-children-instant")
    assert "transition: none" in instant, "the instant disclosure travels"
    assert styles.index(".tree-children-instant {") > styles.index(".tree-children {")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    # revealInTree reveals within a scope (the panel, or a Group by section) through
    # revealWithin, which opens the folders.
    reveal = app[app.index("async function revealWithin(") :]
    reveal = reveal[: reveal.index("\n}\n")]
    assert "setFolderExpanded(folder, true, { instant })" in reveal, (
        "navigation's reveal of a path animates the folders it opens"
    )
    assert "instant = true }" in reveal[: reveal.index(") {")], "a reveal the reader caused travels"
    # A landing's reveal answers no input, and its folders travelling moved the tree less.
    landing = app[app.index("    revealInTree(initialPath, {") :]
    assert "instant: false" in landing[: landing.index("});")]
    toggle = app[app.index("async function toggleTreeFolder(") :]
    toggle = toggle[: toggle.index("\n}\n")]
    assert "instant" not in toggle, "a folder the reader clicked lands without travel"


def test_inline_change_stats_are_bold() -> None:
    # Every lines summary is the brief change line, a file's and a folder's too, so its one
    # rule inks and weighs every +N and −N (mb-ox6a).
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    for selector in (".change-line-stats > .diff-stat-add", ".change-line-stats > .diff-stat-del"):
        assert "font-weight: var(--weight-bold)" in _rule(styles, selector), f"{selector} not bold"


def test_branch_chips_are_bold_and_square() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    rule = _rule(styles, ".git-ref")
    assert "font-weight: var(--weight-bold)" in rule
    assert "border-radius: var(--radius-tag)" in rule
    assert "--radius-tag:" in styles


def test_badges_center_their_capitals_in_the_box_they_had() -> None:
    """A badge trims its line to the capitals and the baseline, and centers what is left.

    Centered by its line box, a 12px Source Sans 3 word sat 0.93px high in Chrome and in
    WebKit; trimmed and centered, 0.02-0.09px (the comment above `.file-header-badge`). The
    box keeps the height its line, pads, and borders gave it, so each badge states that
    sum against its own pads and borders.
    """
    base = dict(_rules_of(STATIC / "styles.css"))[".file-header-badge"]
    assert base["display"] == "inline-block", "text-box trims a block container's line"
    assert base["text-box"] == "trim-both cap alphabetic"
    assert base["align-content"] == "center"
    assert base["white-space"] == "nowrap", "a fixed-height badge holds one line"
    assert base["padding"] == "2px 8px" and "border" not in base
    assert base["block-size"] == "calc(1lh + 2 * 2px)"
    pull = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"))[".github-pull-badge"]
    assert pull["padding-block"] == "0" and pull["border"].startswith("1px ")
    assert pull["block-size"] == "calc(1lh + 2 * 1px)"


def test_row_targets_share_the_hover_token() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    diff_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/styles.css").read_text(
        encoding="utf-8"
    )
    assert "background: var(--hover-bg);" in _rule(styles, ".tree-item:hover")
    assert "background: var(--hover-bg);" in _rule(
        diff_css, ".metabrowser-diff-host .diff-file-bar:hover"
    )


def test_diff_file_bar_keeps_its_actions_by_the_name_and_its_chooser_at_its_end() -> None:
    """A diff's file bar: the name's group, then View file, then a chooser at its end.

    ``tests/dom/diff-view-behavior.js`` and ``tests/dom/diff-view-file-session.js`` hold what
    each part contains, in order. Where they sit is layout, and these declarations are what
    put them there (docs/design-system.md, "Diff File Bar"; mb-leg0, mb-ceap).
    ``tests/test_diff_file_bar_chrome.py`` lays the bars out in headless Chrome at widths
    from 1,063 to 159 px and holds that no part is cut off or covers another, that a bar
    with a chooser cuts its name only on a line of its own, and that at rest the stats read
    with the name. On a pull request's Docs and Changes and a commit's page, measured at
    those widths, the name kept at least the width it had with View on branch in the end
    group (review A of #759, A1; Design Rule Measurements, "Diff File Bar Widths").
    """

    diff_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/styles.css").read_text(
        encoding="utf-8"
    )
    host = ".metabrowser-diff-host"
    # Every bar wraps its parts in order where they do not fit one line, so nothing is cut
    # off past its end.
    assert "flex-wrap: wrap;" in _rule(diff_css, f"{host} .diff-file-bar")
    # The name's group gives way before anything else does, so Copy path and the stats sit
    # right after the name at any width and a long path is cut short with them still beside
    # it. Without a chooser the group is laid out at its basis, so a long name is cut on one
    # line beside View file down to that basis, and grows no wider than its content, so View
    # file follows the name; with one it is laid out whole, so View file and the chooser
    # take the next line before the name is cut at all.
    lead = _rule(diff_css, f"{host} .diff-file-lead")
    assert "flex: 1 1 var(--diff-file-lead-basis);" in lead
    assert "max-width: max-content;" in lead
    assert "min-width: 0;" in lead
    chooser_lead = _rule(diff_css, f"{host} .diff-file-bar-markdown .diff-file-lead")
    assert "flex: 0 1 auto;" in chooser_lead
    toggle = _rule(diff_css, f"{host} .diff-file-toggle")
    assert "flex: 0 1 auto;" in toggle and "min-width: 0;" in toggle
    for selector in (".diff-file-copy", ".diff-file-facts", ".diff-file-view"):
        assert "flex: none;" in _rule(diff_css, f"{host} {selector}"), f"{selector} gives way"
    # The space before View file is the first thing to give way, before the name.
    space = _rule(diff_css, f"{host} .diff-file-lead:has(+ .diff-file-view)::after")
    assert "width: var(--diff-file-actions-gap);" in space
    assert "flex: 0 1000000 auto;" in space and "min-width: 0;" in space
    # The end group keeps its width, and its start margin takes the bar's free space, which
    # holds it at the bar's end on a line of its own too; empty, it takes no line.
    end = _rule(diff_css, f"{host} .diff-file-end")
    assert "flex: none;" in end
    assert "margin-inline-start: auto;" in end
    assert "display: none;" in _rule(diff_css, f"{host} .diff-file-end:empty")
    # A chooser's group, where it alone is wider than the bar, wraps too, with each line at
    # the bar's end.
    wrapping_end = _rule(diff_css, f"{host} .diff-file-bar-markdown .diff-file-end")
    assert "flex: 0 1 auto;" in wrapping_end
    assert "flex-wrap: wrap;" in wrapping_end
    assert "justify-content: flex-end;" in wrapping_end
    # Copy path shows while the pointer is on the bar or the keyboard's focus is in it, the
    # reveal contract of every `.icon-btn-reveal` ("Copyable Identifiers Use One Delegate"),
    # and through its own "Copied", as a file header's does. The focus is `:focus-visible`:
    # in headless Chrome a mouse press on the name focused the disclosure, and under
    # `:focus-within` the control stayed at full opacity with the pointer off the bar.
    reveal = (
        f"{host} .diff-file-bar:hover .diff-file-copy,\n"
        f"{host} .diff-file-bar:has(:focus-visible) .diff-file-copy,\n"
        f"{host} .diff-file-copy.copied {{\n"
        "  opacity: 1;\n"
        "  pointer-events: auto;\n"
        "}"
    )
    assert reveal in diff_css, "the bar no longer reveals Copy path on hover and keyboard focus"
    assert ":focus-within .diff-file-copy" not in diff_css, (
        "a press on a bar's name would hold Copy path shown"
    )
    copied = f"{host} .diff-file-copy.copied {{\n  color: var(--status-success-text);\n}}"
    assert copied in diff_css, "a copied path no longer shows in the success ink"


def test_preview_navigation_arrival_motion_is_shared_and_reduced_motion_safe() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")

    assert "--preview-navigation-pending-overlay" not in styles
    assert "#preview-pane::after" not in styles
    arrival = app[app.index("function animatePreviewContentArrival") :][:1_500]
    assert "content.animate(" in arrival
    assert "preview.animate(" not in arrival
    assert "PREVIEW_ARRIVAL_START_OPACITY" in arrival
    assert "PREVIEW_ARRIVAL_DURATION_MS" in arrival
    assert "prefers-reduced-motion: reduce" in arrival


def test_nav_like_row_sets_share_the_vertical_keyboard_contract() -> None:
    """The maintained surface registry keeps row navigation from drifting."""
    design = (REPO_ROOT / "docs" / "design-system.md").read_text(encoding="utf-8")
    tree = (STATIC / "tree-keyboard-navigation.js").read_text(encoding="utf-8")
    git = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    # The host binds a row's keys in the registry, and the view moves the rows' tab stop.
    pulls = (STATIC / "pulls-nav.js").read_text(encoding="utf-8") + (
        REPO_ROOT / BUILTIN_PLUGINS / "github/pulls-panel.js"
    ).read_text(encoding="utf-8")

    pull_files = pulls + (REPO_ROOT / BUILTIN_PLUGINS / "github/pull-files-view.js").read_text(
        encoding="utf-8"
    )
    # The table view: its model says where a key moves, and the view moves the tab stop.
    table = "".join(
        (REPO_ROOT / BUILTIN_PLUGINS / f"table/{name}").read_text(encoding="utf-8")
        for name in ("table-model.js", "table-view.js")
    )

    assert "### Navigational Row Collections" in design
    assert "test_nav_like_row_sets_share_the_vertical_keyboard_contract" in design
    for source, movement_helper in (
        (tree, "focusAndOpen"),
        (git, "moveCommitRowFocus"),
        (pulls, "nav.move("),
        (pull_files, "nav.moveFile("),
        (table, "moveFocus("),
    ):
        assert movement_helper in source
        assert '"ArrowUp"' in source
        assert '"ArrowDown"' in source
        assert '"k"' in source
        assert '"j"' in source
        assert 'setAttribute("tabindex"' in source


def test_git_row_selection_avoids_full_collection_mutation() -> None:
    """Immediate Git feedback mutates only the old and new row."""
    git = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    anchor = git[
        git.index("function setCommitRowAnchor") : git.index("/** @param {HTMLElement} list */")
    ]
    selection = git[git.index("async function selectCommit") : git.index("function renderFileRow")]

    assert 'querySelector(".git-graph-row[data-roving-anchor]")' in anchor
    assert "commitRows(list)" not in anchor
    assert "options.rowElement" in selection
    assert 'mountedPanel.querySelector(".git-graph-row.selected")' in selection
    assert 'document.querySelector(".git-graph-row.selected")' not in selection
    assert 'querySelectorAll(".git-graph-row")' not in selection
    assert '"gitRevision:selectionFeedback"' in selection
    assert '"gitRevision:rowAnchor"' in selection
    assert selection.index('"gitRevision:selectionFeedback"') < selection.index(
        '"gitRevision:rowAnchor"'
    )
    render_row = git[git.index("function renderRow") : git.index("function renderRefBadges")]
    assert 'element.addEventListener("focus"' not in render_row
    enter_handler = git[git.index('if (event.key === "Enter"') :][:250]
    assert "{ rowElement: row }" in enter_handler
    assert "transition:" not in _rule(styles, ".git-graph-row")


def test_copyable_identifiers_share_the_copy_contract() -> None:
    """Paths and revisions use one explicit-value copy delegate."""
    design = (REPO_ROOT / "docs" / "design-system.md").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    # A file's view header writes its Copy path control (view-header.js).
    header = (STATIC / "view-header.js").read_text(encoding="utf-8")
    sdk = (STATIC / "plugin-sdk.js").read_text(encoding="utf-8")
    git = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    diff = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/diff-view.js").read_text(
        encoding="utf-8"
    )

    assert "### Copyable Identifiers Use One Delegate" in design
    assert "test_copyable_identifiers_share_the_copy_contract" in design
    assert 'target.closest("[data-mb-copy]")' in sdk
    assert 'mode === "text"' in sdk and 'mode === "wrap"' in sdk
    assert 'data-mb-copy="text"' in header
    assert 'setAttribute("data-mb-copy", "text")' in diff
    assert 'data-mb-copy="text"' in git and "commit.id" in git
    assert "git-commit-revision-copy" in git
    for source in (app, header, diff, git):
        assert "data-copy-path" not in source, "a local path-copy contract reappeared"


def test_branch_chips_have_their_own_ground() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "background: var(--git-ref-bg)" in _rule(styles, ".git-ref")
    assert "--git-ref-bg: var(--viz-surface-sunken)" not in styles, (
        "ref chips must not reuse the shared chip ground"
    )
    assert styles.count("--git-ref-bg:") >= 2, "both themes must define the ref-chip ground"


# ── Theming: one hue, two lightnesses ──────────────────────────────

_OKLCH_TOKEN = re.compile(r"^\s*(--[a-z0-9-]+):\s*oklch\(([^)]+)\)", re.MULTILINE)


def _oklch_tokens(block: str) -> dict[str, list[str]]:
    return {name: value.split() for name, value in _OKLCH_TOKEN.findall(block)}


def _theme_blocks() -> tuple[str, str]:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    dark_start = styles.index('[data-theme="dark"] {')
    return styles[:dark_start], styles[dark_start:]


# Below this chroma a color is a near-neutral and its hue is not
# perceptible, so requiring hue equality there would constrain a number
# nobody can see — and would force the dark theme's cool grays to take
# the light theme's warm ones.
_NEUTRAL_CHROMA = 0.02


def test_themed_colors_keep_their_hue() -> None:
    """The systematic rule for two themes.

    A token defined in both themes names one color seen against two
    backgrounds: its hue is the invariant, while lightness and chroma
    are tuned for the background it sits on (dark surfaces generally
    want less chroma, not more). Near-neutrals are exempt, since hue is
    imperceptible at their chroma.

    Stating colors in oklch is what makes this checkable at all — the
    notation separates the three components, which hex and hsl do not.
    """
    light_tokens = _oklch_tokens(_theme_blocks()[0])
    dark_tokens = _oklch_tokens(_theme_blocks()[1])
    compared = 0
    for name, dark_value in dark_tokens.items():
        light_value = light_tokens.get(name)
        if light_value is None or len(light_value) < 3 or len(dark_value) < 3:
            continue
        if float(light_value[1]) < _NEUTRAL_CHROMA or float(dark_value[1]) < _NEUTRAL_CHROMA:
            continue
        compared += 1
        assert light_value[2] == dark_value[2], (
            f"{name} changes hue between themes (light {light_value[2]}, "
            f"dark {dark_value[2]}); a themed color keeps its hue and moves in "
            "lightness and chroma"
        )
        assert light_value[0] != dark_value[0] or light_value[1] != dark_value[1], (
            f"{name} is identical in both themes; drop the override instead"
        )
    assert compared >= 30, "the theming check lost its coverage"


def test_colors_are_declared_in_oklch() -> None:
    """One notation, so lightness, chroma, and hue are comparable across
    every token — which is what let the drift above be found at all."""
    sheets = [
        STATIC / "styles.css",
        *(REPO_ROOT / "src/metabrowser/builtin_plugins").glob("*/styles.css"),
    ]
    for sheet in sheets:
        text = sheet.read_text(encoding="utf-8")
        if sheet.parent.name == "github":
            text = _without_label_formula(text)
        for notation in (r"hsla?\(", r"rgba?\(", r"#[0-9a-fA-F]{3,8}\b"):
            found = re.findall(notation, text)
            assert not found, (
                f"{sheet.name} declares colors as {found[0]!r}; every color is written in oklch"
            )


_LABEL_RULE = re.compile(
    r'\.github-pull-label\[data-color\](?::where\(\[data-theme="dark"\] \*\))? \{[^}]*\}'
)


def _without_label_formula(text: str) -> str:
    """The GitHub plugin's stylesheet without GitHub's label formula, the one exception.

    A label's color is GitHub's data, six hex digits of sRGB, and the formula is
    github.com's, written in ``rgb()`` and ``hsl()`` of the label's own custom properties
    (docs/design-system.md, "Label Colors"): in oklch it would not paint what github.com
    paints. Its two rules are taken out whole, so a color anywhere else in the sheet is
    still found; and each color they write is computed from a ``--github-label-`` property, never
    a literal.
    """

    rules = _LABEL_RULE.findall(text)
    assert len(rules) == 2, "the label formula is a light rule and a dark one"
    for rule in rules:
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", rule), rule
        calls = [_call_at(rule, found.start()) for found in re.finditer(r"(?:rgba?|hsla?)\(", rule)]
        assert calls and all("var(--github-label-" in call for call in calls), rule
    return _LABEL_RULE.sub("", text)


def _call_at(text: str, start: int) -> str:
    """The function call that starts at *start* in *text*, to its balancing parenthesis."""

    depth = 0
    for at in range(text.index("(", start), len(text)):
        depth += {"(": 1, ")": -1}.get(text[at], 0)
        if depth == 0:
            return text[start : at + 1]
    raise AssertionError(f"an unbalanced call: {text[start:]}")


def test_ref_colors_are_themed_and_distinguished_by_hue() -> None:
    """Three ref kinds, one lightness, three hues — each themed, since a
    single literal cannot be readable on both backgrounds."""
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    tokens = ("--git-ref-local", "--git-ref-remote", "--git-ref-tag")
    for token in tokens:
        assert styles.count(f"{token}:") >= 2, f"{token} must be defined for both themes"
    light, _dark = _theme_blocks()
    light_tokens = _oklch_tokens(light)
    hues = [light_tokens[token][2] for token in tokens if token in light_tokens]
    assert len(set(hues)) == 3, f"ref kinds must differ by hue, got {hues}"


def _hue_gap(first: float, second: float) -> float:
    gap = abs(first - second) % 360
    return min(gap, 360 - gap)


def test_branch_chips_are_blue_and_never_a_merged_pull_requests_purple() -> None:
    """A branch is blue, the other branch kind a blue-green, and each reads on its ground.

    Every branch a pull request shows is a remote chip, so remote is the branch blue, and
    `HEAD`'s lane takes it too. Neither branch ink may sit near the purple of a merged
    pull request: the remote ink once sat 5 degrees of hue from it. Each ink is text on
    `--git-ref-bg`, and the solid trunk form swaps the two, so one ratio covers both.
    """
    light, dark = _theme_blocks()
    rules = _rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css")
    plugin_light = next(body for selector, body in rules if selector == ":root")
    plugin_dark = next(body for selector, body in rules if selector == '[data-theme="dark"]')
    for theme, block, plugin in (("light", light, plugin_light), ("dark", dark, plugin_dark)):
        ground = _declared(block, "--git-ref-bg")
        for kind in ("remote", "local", "tag"):
            ink = _declared(block, f"--git-ref-{kind}")
            assert _contrast(ink, ground) >= 4.5, (
                f"--git-ref-{kind} reads at {_contrast(ink, ground):.2f}:1 in the {theme} theme"
            )
        merged = _oklch_channels(plugin["--github-pull-merged"])[2]
        remote = _oklch_channels(_declared(block, "--git-ref-remote"))[2]
        local = _oklch_channels(_declared(block, "--git-ref-local"))[2]
        assert 220 <= remote <= 270, f"the branch color is blue, not hue {remote}"
        for name, hue in (("remote", remote), ("local", local)):
            assert _hue_gap(hue, merged) >= 30, f"--git-ref-{name} is a merged pull request's hue"
        assert _hue_gap(remote, local) >= 30, "the two branch kinds must be clearly apart"
    graph = (STATIC / "git-graph.js").read_text(encoding="utf-8")
    history = (REPO_ROOT / "src/metabrowser/git/history.py").read_text(encoding="utf-8")
    assert 'const HEAD_LANE_COLOR = "var(--git-ref-remote)";' in graph
    assert '_HEAD_LANE_COLOR = "var(--git-ref-remote)"' in history
    # The pull request's page names its branches; a Pulls row names none.
    source = (REPO_ROOT / BUILTIN_PLUGINS / "github" / "pull-page.js").read_text(encoding="utf-8")
    assert 'kind: "remote"' in source, "pull-page.js's branches lost the remote chip"


def test_ref_chip_kinds_differ_in_form_not_only_hue() -> None:
    """A tag is a different kind of thing from a branch, and trunk is
    the branch worth finding: each carries a form, so the vocabulary
    survives a reader who does not separate the hues."""
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    tag = _rule(styles, ".git-ref-tag")
    assert "clip-path:" in tag, "a tag must differ in shape, not only in color"
    trunk = _rule(styles, ".git-ref-trunk")
    assert "background: var(--git-ref-ink)" in trunk, "trunk takes the solid form"
    head = _rule(styles, ".git-ref-head")
    assert "outline:" in head, "HEAD is a ring, orthogonal to the chip's kind"
    # The ring is the kind's color: in currentcolor it took a trunk chip's ground-colored
    # text and all but vanished. A history row clips its chips, so it keeps the ring's
    # 2px inside the clip and gives the room back.
    assert "outline: 1px solid var(--git-ref-ink);" in head
    refs = _rule(styles, ".git-graph-refs")
    assert "overflow: hidden;" in refs
    assert "padding: 2px;" in refs and "margin: -2px;" in refs, "the row clips the HEAD ring"
    # The kind classes must reach the markup from the wire, not be guessed
    # in the browser.
    panel = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    views = (STATIC / "plugin-sdk-views.js").read_text(encoding="utf-8")
    assert "ref.is_trunk" in panel and "git-ref-trunk" in views


# The classes the SDK writes on a chip and its label (`refChip`, `refChipHtml`, and
# `mergeRefs`'s two roles). A rule whose subject carries one of them styles a chip.
_CHIP_CLASSES = frozenset(
    {
        "git-ref",
        "git-ref-local",
        "git-ref-remote",
        "git-ref-tag",
        "git-ref-trunk",
        "git-ref-head",
        "git-ref-label",
        "merge-refs-source",
        "merge-refs-target",
    }
)
# What makes a chip one size and one box: its type, its line, its padding, its corner,
# and its width bound.
_CHIP_TYPE_AND_BOX = frozenset(
    {
        "font",
        "font-size",
        "font-weight",
        "font-family",
        "font-stretch",
        "line-height",
        "letter-spacing",
        "padding",
        "padding-left",
        "padding-right",
        "padding-top",
        "padding-bottom",
        "padding-inline",
        "padding-inline-start",
        "padding-inline-end",
        "padding-block",
        "border-radius",
        "max-width",
        "height",
        "min-height",
        "block-size",
        "zoom",
    }
)
# A form's own room, on the chip itself and never from a context: the tag's notch and
# the copyable chip's reserved control.
_CHIP_FORM_ROOM = {".git-ref-tag": {"padding-left"}}


def test_branch_chips_are_one_size_everywhere() -> None:
    """A ref chip is one size in every context ("Branch Chips", "One Size").

    As a ratio of the text around it, a chip's type ran 10.8px to 12.6px against a box
    that stayed one height, so a name sat level in a history row and low in a commit's
    header (mb-uokj). Now `.git-ref` alone sets a chip's type and box, from tokens that
    resolve to lengths with no part taken from the text the chip sits in, and no rule in
    any shipped stylesheet restyles a chip from where it sits. What size that is, and
    where the name then sits in the box, is the tokens' to say: it is measured in a
    browser, not pinned here.
    """
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    section = doc.split("#### One Size", 1)[1].split("\n#### ", 1)[0]
    assert "test_branch_chips_are_one_size_everywhere" in section
    # Only the core :root defines the tokens a chip's type and box are made of: a rule
    # anywhere else, a plugin's included, that set one would resize every chip inside it.
    chip_tokens = ("--git-ref-font-scale", "--git-ref-font-size", "--compact-chip-height")
    for token in chip_tokens:
        defined = [
            (_sheet_name(sheet), selector)
            for sheet in _stylesheets()
            for selector, declarations in _rules_of(sheet)
            if token in declarations
        ]
        assert defined == [("styles.css", ":root")], f"{token} is defined at {defined}"
    root = _root_rule(STATIC / "styles.css")
    # The size is the navigation column's chip size: a ratio of that column's fixed text
    # size, so it has no unit that resolves against the chip's surroundings.
    assert root["--git-ref-font-size"] == ("calc(var(--git-ref-font-scale) * var(--nav-font-size))")
    assert re.fullmatch(r"\d+(\.\d+)?", root["--git-ref-font-scale"])
    for token in ("--nav-font-size", "--compact-chip-height"):
        assert re.fullmatch(r"\d+(\.\d+)?px", root[token]), f"{token} is not a fixed length"
    shell = dict(_rules_of(STATIC / "styles.css"))
    chip = shell[".git-ref"]
    assert chip["font-size"] == "var(--git-ref-font-size)"
    assert chip["font-weight"] == "var(--weight-bold)"
    # The line is the box's height, so one token sets the height and centers the name. The
    # shared outer height leaves room for the HEAD ring in a history row.
    assert chip["line-height"] == "var(--compact-chip-height)"
    assert chip["align-items"] == "center"
    assert not {"height", "min-height", "block-size", "padding-top", "padding-bottom"} & set(chip)
    assert float(root["--compact-chip-height"].removesuffix("px")) + 4 <= 22
    assert chip["padding"] == "0 var(--compact-chip-padding-inline)"
    assert chip["border-radius"] == "var(--radius-tag)"
    assert chip["max-width"] == "22em", "the width bound is in the chip's own fixed size"
    github = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"))
    table = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "table/styles.css"))
    for bordered_chip in (
        shell[".source-ref-selector-badge"],
        github[".github-pull-label"],
        table[".table-ref"],
    ):
        assert (
            bordered_chip["line-height"]
            == "calc(var(--compact-chip-height) - 2 * var(--chip-border))"
        )
        assert bordered_chip["border"] == "var(--chip-border) solid var(--border)"
        assert bordered_chip["padding"] == chip["padding"]
        assert bordered_chip["border-radius"] == chip["border-radius"]
    assert table[".table-chip"]["min-block-size"] == "var(--chip-height)"
    restyled = []
    for sheet in _stylesheets():
        for selector, declarations in _rules_of(sheet):
            classes = set(re.findall(r"\.([\w-]+)", _compounds(selector)[-1]))
            if selector == ".git-ref" or not classes & _CHIP_CLASSES:
                continue
            touched = _CHIP_TYPE_AND_BOX & set(declarations)
            touched -= _CHIP_FORM_ROOM.get(selector, set())
            if touched:
                restyled.append(f"{sheet.parent.name}/{sheet.name}: {selector} {sorted(touched)}")
    assert not restyled, f"a context restyles a ref chip: {restyled}"


def test_each_context_assigns_its_chip_kind() -> None:
    """Each context's chips take the kind, trunk, and HEAD its row of the table names.

    "Which Kind Each Context Gets" in the design system: a history row, a commit's summary,
    and its tooltip draw the wire's kind with the server's trunk and HEAD; a merge's two
    branches are remote and never trunk or HEAD; the ref selector draws a mirror's branch
    as remote, a checkout's own as local and its remote-tracking branch as remote, and a
    tag as a tag, and never trunk or HEAD: the mirror's default is not the history's
    trunk, and it says "default" and "checked out" in words.
    `tests/test_git_api.py` holds that the detail and the refs listing carry the
    refs and trunk the history row does.
    """
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    section = doc.split("#### Which Kind Each Context Gets", 1)[1].split("\n#### ", 1)[0]
    assert "test_each_context_assigns_its_chip_kind" in section
    for context in (
        "A checkout’s history row",
        "A mirror’s history row",
        "A commit’s summary",
        "A commit’s tooltip",
        "A pull request’s header",
        "The Files revision row and chooser list",
    ):
        assert f"| {context} |" in section, f"the table lost {context!r}"
    # One mapping from a Git kind to a chip's: a tag, a remote branch, else a local branch.
    views = (STATIC / "plugin-sdk-views.js").read_text(encoding="utf-8")
    mapping = 'options.kind === "tag" ? "tag" : options.kind === "remote" ? "remote" : "local"'
    assert views.count(mapping) == 1, "refChip and refChipHtml share a kind mapping"
    # A history row, a commit's summary, and its tooltip draw the wire's refs, all three
    # marks included, through one function.
    panel = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    badges = re.search(
        r"function renderRefBadges\(refs, menu = \"sibling\"\) \{(.*?)\n  \}", panel, re.S
    )
    assert badges is not None
    for option in ("kind: ref.kind,", "trunk: ref.is_trunk,", "head: ref.is_head,"):
        assert option in badges[1], f"history chips lost {option!r}"
    assert panel.count("refChipHtml(") == 1, "git history draws chips only in renderRefBadges"
    assert "renderRefBadges(commit.refs || [])" in panel
    assert 'renderRefBadges(commit.refs, compact ? false : "inline")' in panel
    # A merge's two branches are the hosted repository's: remote, never trunk or HEAD. The
    # pull request's page draws them; a Pulls row names no branches.
    for name in ("pull-page.js",):
        source = (REPO_ROOT / BUILTIN_PLUGINS / "github" / name).read_text(encoding="utf-8")
        calls = re.findall(r"mb\.mergeRefs\((.*?)\n\s*\),?\n", source, re.S)
        assert len(calls) == 1, f"{name} draws one merge"
        options = calls[0].rsplit("{", 1)[1]
        assert 'kind: "remote"' in options, f"{name}'s branches are remote"
        assert not re.search(r"\b(?:trunk|head):", calls[0]), f"{name} marks trunk or HEAD"
    # The ref selector: a tag is a tag, and a branch is remote but for a checkout's own,
    # which is local, in the source row and the list. Neither is trunk or HEAD; the list
    # says "default", and "checked out" for a checkout's HEAD, in words.
    selector = (STATIC / "source-ref-selector.js").read_text(encoding="utf-8")
    chips = re.findall(r"metabrowser\.refChip\((.*?)\}\)", selector, re.S)
    assert len(chips) == 3, (
        "the selector draws a chip for the source, for the working tree's branch,"
        " and for each list row"
    )
    for chip in chips:
        assert re.search(r'kind: (?:model\.selectedRef\.kind|row\.chip|"local"),', chip)
        assert not re.search(r"\b(?:trunk|head):", chip), "the selector marks trunk or HEAD"
    squeezed = re.sub(r"\s+", " ", selector)
    # The chooser's rows by list kind and the source row by the currently viewed ref.
    assert (
        'state.kind === "tag" ? "tag" : state.kind === "branch" && checkout ? "local" : "remote";'
        in squeezed
    )
    assert (
        'label.kind === "Tag" ? "tag" : label.kind === "Branch" && checkout ? "local" : "remote",'
        in squeezed
    )
    assert 'badge.textContent = row.default ? "default" : "checked out";' in selector
    # Trunk has one definition, on the server, and every answer that names a ref uses it.
    log = (REPO_ROOT / "src/metabrowser/git/log.py").read_text(encoding="utf-8")
    assert log.count('is_trunk_ref(ref["name"], ref["kind"])') == 2, "decoration and refs"
    detail = (REPO_ROOT / "src/metabrowser/git/detail.py").read_text(encoding="utf-8")
    assert '"--decorate=full",' in detail, "a detail's refs parse as the history's do"


def test_git_history_vocabulary_is_documented() -> None:
    """The git panel's own elements are design-system material, not
    panel-local decisions."""
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    for heading in ("## Git History", "### Lane Colors", "### Commit Nodes", "### History Rows"):
        assert heading in doc, f"the design system lost {heading!r}"
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    # The lane set is the documented exception to the hue rule: identical
    # in both themes, so it must be defined exactly once.
    for lane in range(1, 6):
        assert styles.count(f"--git-lane-{lane}:") == 1, (
            f"--git-lane-{lane} is defined per theme; the lane set is one set"
        )


def test_git_commit_summary_is_one_component() -> None:
    """Commit identity and description have one maintained component boundary."""
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    panel = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")

    assert "### Git Commit Summary" in doc
    assert "test_git_commit_summary_is_one_component" in doc
    assert "function renderCommitSummary(detail, options = {})" in panel
    assert "function renderCommitTooltip(detail)" in panel
    assert "function renderCommitChangeStats(" in panel
    assert '"git-commit-summary git-commit-summary-compact"' in panel
    assert 'class="git-commit-change-stats"' in panel
    assert "html += renderCommitSummary(detail);" in panel
    assert "return renderCommitSummary(detail, {\n      compact: true," in panel
    # The commit page's change counts are its size line and its one Diff summary, which its
    # diff draws in the summary's place (mb-pb35): the size line, the page header's line
    # above it, says the file count and the size ("Change Size Line"), and the summary the
    # statuses and line totals. Only the compact summary, in a tooltip, draws its own, its
    # size line and one line in the Diff summary's words and paint (mb-khm6). Until the diff
    # draws it, and where it is not drawn, the place holds the commit's totals (A6 of review
    # A on #470).
    assert "html += renderCommitChangeStats(stats, options.size ?? null);" in panel
    assert (
        'html += `<div class="git-commit-size page-header-line page-header-size">'
        "${commitSizeLineHtml(stats, kept)}</div>`;"
    ) in panel
    assert (
        'html += `<div class="git-commit-diff-summary metabrowser-diff-host page-header-line">'
        "${renderCommitTotals(stats)}</div>`;"
    ) in panel
    assert (
        panel.count('class="git-commit-diff-summary metabrowser-diff-host page-header-line"') == 1
    )
    assert 'preview.querySelector(".git-commit-diff-summary")' in panel
    commit_place = _rule(styles, ".git-commit-diff-summary")
    assert "flex-direction: column" in commit_place
    assert "align-items: flex-start" in commit_place
    for component_part in (
        'const subjectClass = compact ? "git-commit-subject"',
        'class="git-commit-meta"',
        'class="git-commit-identity"',
        'class="git-commit-change-line"',
        'class="git-commit-change-stats"',
        'class="git-commit-refs"',
        'class="git-commit-body page-card chrome-prose"',
    ):
        assert panel.count(component_part) == 1, f"summary part drifted: {component_part}"
    change_stats = _rule(styles, ".git-commit-change-stats")
    change_line = _rule(styles, ".git-commit-change-line")
    line_stats = _rule(styles, ".change-line-stats")
    compact = _rule(styles, ".git-commit-summary-compact")
    meta = _rule(styles, ".git-commit-meta")
    summary_sha = _rule(styles, ".git-commit-sha")
    compact_subject = _rule(styles, ".git-commit-summary-compact .git-commit-subject")
    compact_meta = _rule(styles, ".git-commit-summary-compact .git-commit-meta")
    summary_body = _rule(styles, ".git-commit-body")
    assert "max-width:" in compact
    assert "line-clamp:" in compact_subject
    assert "display: flex" in change_line
    assert "flex-wrap: wrap" in change_line
    assert "display: inline-flex" in line_stats
    assert "white-space: nowrap" in line_stats
    # Its face is chrome prose's, which its markup carries (test_serif_is_only_for_documents).
    assert "font-family" not in summary_body
    assert "font-size: var(--document-body-font-size)" in summary_body
    # Its Markdown is set as a PR description's (placeCommitBody); the message as written,
    # until then and where it is not rendered, and its trailers keep their newlines.
    assert "white-space" not in summary_body
    written = _rule(styles, ".git-commit-body-plain,\n.git-commit-trailers")
    assert "white-space: pre-wrap" in written
    for rule in (
        change_stats,
        meta,
        compact_subject,
        compact_meta,
    ):
        assert "font-size: var(--body-font-size)" in rule
        assert "font-size: var(--ui-small-font-size)" not in rule
    # Its ref chips are the chip's one size, and no rule here sizes them:
    # test_branch_chips_are_one_size_everywhere.
    assert ".git-commit-summary .git-ref" not in styles
    # The revision is monospace, the documented exception, at the size of its line, with its
    # face's x-height the sans's: "Short Commit IDs" in the design system, and
    # test_the_commit_id_face_is_one_face_one_gray_and_its_lines_size.
    assert "font-family: var(--font-mono)" in summary_sha
    assert "font-size:" not in summary_sha
    assert "font-size-adjust: var(--font-sans-ex-height)" in summary_sha
    assert "noninteractive copy glyph" in doc


# The lines under a page header's title, by the class each page's line has: the commit page's
# author, revision, and age, and the pull request's state and ages, author, branches, and status.
_PAGE_HEADER_LINES = (
    "page-header-line",
    "git-commit-byline",
    "git-commit-revision-line",
    "git-commit-ages",
    "github-pull-meta",
    "github-pull-branches",
    "github-pull-opened",
    "github-pull-status",
)


def test_page_headers_set_every_line_under_the_title_at_the_body_size() -> None:
    """A commit's, a pull request's, and a stack's page have one header ("Page Headers").

    One since mb-26zj, and the stack's since mb-cm31.

    Each is a `.page-header`, with its first line `--page-title-gap` under the title and
    the common line gap beneath it. The pull request adds half a gap on each side of its
    size line. Every line under the title but the labels and a stack's members card is a
    `.page-header-line` at
    `--body-font-size`, including the ages and Diff summary, whose text the diff plugin sets at the
    same token: the owner found the summary and the pull request's
    rows of ages and status a step smaller than the lines above them (mb-kisi). No rule sets
    another size on a line or its text; a chip keeps its own (Branch Chips, Label Colors) and
    a revision the line's. `tests/dom/page-header-chrome.mjs` reads the computed sizes
    on both pages in Chrome.
    """

    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "### Page Headers" in doc
    assert "test_page_headers_set_every_line_under_the_title_at_the_body_size" in doc
    shell = dict(_rules_of(STATIC / "styles.css"))
    assert shell[".page-header"] == {
        "--page-header-line-gap": "6px",
        "--page-header-size-margin": "0px",
        "--page-header-end-padding": (
            "calc(var(--content-padding-y) - 2 * var(--page-header-size-margin))"
        ),
        "display": "flex",
        "flex-direction": "column",
        "gap": "var(--page-header-line-gap)",
    }
    # The first line is `--page-title-gap` under the title, the gap a view header leaves
    # between its title and the metadata line after it (mb-wcbc).
    assert shell[".page-header > .page-heading"] == {
        "margin": "0 0 calc(var(--page-title-gap) - var(--page-header-line-gap))"
    }
    assert shell[".view-header-title.page-heading"]["padding-inline-end"] == (
        "var(--page-title-gap)"
    )
    assert shell[".page-header-line"]["font-size"] == "var(--body-font-size)"
    assert shell[".page-header > .page-header-size"]["margin-block"] == (
        "var(--page-header-size-margin)"
    )
    # An age in a line takes the line's size because the age primitive sets none
    # (tests/test_age_single_source.py), so no rule restates it here.
    assert not any(":is(.age-live" in selector for selector in shell if ".page-header" in selector)
    diff = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "diff/styles.css"))
    assert diff[".metabrowser-diff-host .diff-summary"]["font-size"] == "var(--body-font-size)"
    github = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"))
    assert github[".github-pull-summary-pending"]["font-size"] == "var(--body-font-size)"
    # The rows of ages' quiet text is muted at its line's size, the body's, as quiet text is
    # everywhere on the page (mb-ctlu), so the row restates no size.
    assert github[".github-pull-quiet"]["font-size"] == "var(--body-font-size)"
    assert "font-size" not in github[".github-pull-opened > .github-pull-quiet"]
    line = re.compile(r"\.(" + "|".join(_PAGE_HEADER_LINES) + r")(?![\w-])")
    for sheet in _stylesheets():
        for selector, declarations in _rules_of(sheet):
            size = declarations.get("font-size")
            if size is not None and line.search(selector):
                assert size == "var(--body-font-size)", (sheet.name, selector, size)
    # Both pages write the classes on every line under the title but the labels, a row of
    # chips at a chip's size: the commit summary on its page, and the pull request's header,
    # the Diff summary's row included on both (A1 of review A on #487). Which order they
    # come in is held by tests/dom/git-panel-behavior.js for the commit page and by
    # tests/dom/page-header-chrome.mjs for both.
    panel = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    assert '`<div class="git-commit-header${compact ? "" : " page-header"}">`' in panel
    for written in (
        "'<div class=\"git-commit-byline page-header-line\">'",
        '`<div class="git-commit-revision-line page-header-line">${revisionGroup}</div>`',
        '`<div class="git-commit-ages page-header-line">Committed ${age}</div>`',
        '`<div class="git-commit-diff-summary metabrowser-diff-host page-header-line">',
    ):
        assert written in panel, written
    page = (REPO_ROOT / BUILTIN_PLUGINS / "github/pull-page.js").read_text(encoding="utf-8")
    assert 'class: "github-pull-header page-header page-reading-column"' in page
    for row in (
        "github-pull-meta",
        "github-pull-branches",
        "github-pull-opened",
        "github-pull-status",
        "github-pull-summary metabrowser-diff-host",
    ):
        assert f'class: "{row} page-header-line"' in page, row
    assert 'class: "github-pull-labels"' in page, "the labels row is a row of chips"
    # A native stack's page is a pull request's header for the whole stack ("The Stack
    # Page"): it builds its header and the lines it shares with a pull request's page with
    # the pull request page's builders (`pageHeaderParts` and its neighbours in
    # pull-page.js), and its members with the stack menu's (`stackMemberRow`), so nothing
    # here restates their classes.


def test_a_person_is_one_identity_on_every_page() -> None:
    """An author is the shell's identity wherever a page names one (mb-nunw, mb-s3g8).

    `actorIdentity` and `actorIdentityHtml` in `plugin-sdk-views.js` draw it: an avatar's
    box, then the bold name. The commit page draws its author through the markup form and the
    GitHub plugin's `authorLabel` through the nodes form, so the box is one size on both
    pages, and where there is no avatar it holds the shell's person glyph, Lucide's, drawn in
    the view bundle. Core reaches no plugin for it.
    """

    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "### Actor Identity" in doc
    assert "test_a_person_is_one_identity_on_every_page" in doc
    views = (STATIC / "plugin-sdk-views.js").read_text(encoding="utf-8")
    assert "function actorIdentity(name, options = {})" in views
    assert "function actorIdentityHtml(name, options = {})" in views
    assert "    actorIdentity,\n    actorIdentityHtml,\n" in views
    # The glyph is Lucide's, beside the one component that draws it, in the view bundle, not
    # in the eager icon registry every folder's first paint fetches.
    assert "const PERSON_GLYPH = // Lucide `circle-user-round`" in views
    icons = (STATIC / "icons.js").read_text(encoding="utf-8")
    assert "circle-user" not in icons and "person:" not in icons
    panel = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    assert 'window.metabrowser.actorIdentityHtml(author, { nameClass: "git-commit-author" })' in (
        " ".join(panel.split())
    )
    assert "github-pull-" not in panel and "authorLabel" not in panel, "core names no plugin's"
    page = (REPO_ROOT / BUILTIN_PLUGINS / "github/pull-page.js").read_text(encoding="utf-8")
    assert "return mb.actorIdentity(name, {" in page
    assert '"github-pull-avatar' not in page, "no avatar of the plugin's own"
    types = (STATIC / "types.d.ts").read_text(encoding="utf-8")
    assert (
        "actorIdentity(name: string, options?: MetabrowserActorIdentityOptions): HTMLElement;"
        in (types)
    )
    shell = dict(_rules_of(STATIC / "styles.css"))
    assert shell[".actor-avatar"]["width"] == "var(--actor-avatar-size)"
    assert shell[".actor-avatar"]["border-radius"] == "var(--radius-circle)"
    assert shell[".actor-avatar"]["color"] == "var(--muted)", "the glyph is muted"
    # The glyph takes the avatar's box, the second exception One Glyph Size names, at its
    # rule and in the section (A3 of review A on #487).
    fills = shell[".actor-avatar > :is(img, svg)"]
    assert (fills["width"], fills["height"]) == ("100%", "100%")
    glyph_size = doc[doc.index("### One Glyph Size") : doc.index("### Every Icon-Only Control")]
    assert "`.actor-avatar > :is(img, svg)`" in glyph_size
    # Lucide's license travels with the glyph, and NOTICE.md lists it with its release and
    # commit (A2 of review A on #487).
    assert "circle-user-round.svg, the person in an actor identity's box" in views
    notice = (REPO_ROOT / "NOTICE.md").read_text(encoding="utf-8")
    assert "`circle-user-round.svg`" in notice


def test_navigation_tooltips_are_pointer_only() -> None:
    """Navigation focus already exposes the selected item and must not add a tooltip."""
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    panel = (STATIC / "git-panel.js").read_text(encoding="utf-8")

    assert "Navigation tooltips are pointer-only" in doc
    assert 'document.addEventListener("mouseenter", showTipText, true)' in app
    assert 'document.addEventListener("mouseleave", hideTipText, true)' in app
    assert 'document.addEventListener("focusin", showTipText)' not in app
    assert 'document.addEventListener("focusout", hideTipText)' not in app
    # Moving focus dismisses a pointer tooltip. A rebuild can repair focus.
    assert 'document.addEventListener("focusin", hideTooltipOnFocus)' in app
    on_focus = app[app.index("function hideTooltipOnFocus(") :]
    on_focus = on_focus[: on_focus.index("\n}\n")]
    assert "if (previous && previous.isConnected === false) {" in on_focus
    assert on_focus.rstrip().endswith("hideTooltip();")
    assert 'element.addEventListener("focus", () =>' not in panel
    assert "dismissHoverTooltip();" in panel


def test_one_document_surface_has_one_set_of_breakpoints() -> None:
    """The README and standalone file share one Markdown column implementation."""

    folder = (REPO_ROOT / "src/metabrowser/builtin_plugins/folder/overview.css").read_text(
        encoding="utf-8"
    )
    markdown = (REPO_ROOT / "src/metabrowser/builtin_plugins/markdown/markdown.css").read_text(
        encoding="utf-8"
    )
    assert "@container kpress-doc (min-width: 48rem)" in folder
    for css in (folder, markdown):
        assert "@container kpress-doc (min-width: 75rem)" in css
        assert "@container (min-width:" not in css
    assert "--kpress-column-inset:" not in markdown
    assert "--kpress-prose-gutter:" not in markdown
    assert ".metabrowser-markdown-document > .kpress-doc" in markdown
    assert "var(--doc-measure)" in folder
    assert "padding-inline: var(--folder-overview-text-inset)" in folder
    readme = (REPO_ROOT / "src/metabrowser/builtin_plugins/folder/readme-panel.js").read_text(
        encoding="utf-8"
    )
    assert "includeToc" not in readme
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "Overview renders the README at the same measure" in doc
    # A README with a table of contents takes the column, as the opened file does.
    assert ".kpress-doc-layout > .kpress-toc) {\n    width: 100%;" in folder


# ── Tabs, type sizes, toggles, and reading width ───────────────────
#
# Each of these holds a rule in docs/design-system.md across every stylesheet and browser
# source the app ships, so a new surface cannot fork it. A primitive is carried in markup;
# a use site positions it. See "Control Families".


def _browser_sources() -> list[Path]:
    """Everything that writes the app's markup: browser sources, plugins, the shell."""

    static = [path for path in sorted(STATIC.glob("*.js")) if path.name != "types.d.ts"]
    plugins = sorted((REPO_ROOT / BUILTIN_PLUGINS).glob("*/*.js"))
    return [*static, *plugins, REPO_ROOT / "src/metabrowser/server.py"]


def _stylesheets() -> list[Path]:
    """Every stylesheet the app ships. Vendored ones are not ours to hold to this."""

    return [
        STATIC / "styles.css",
        STATIC / "structured-tree.css",
        *sorted((REPO_ROOT / BUILTIN_PLUGINS).glob("*/*.css")),
    ]


def _declarations(body: str) -> list[tuple[str, str]]:
    """(property, value) for each declaration of a rule's body."""

    found: list[tuple[str, str]] = []
    for declaration in body.split(";"):
        name, separator, value = declaration.partition(":")
        if separator:
            found.append((name.strip().lower(), value.strip()))
    return found


def _rules_of(path: Path) -> list[tuple[str, dict[str, str]]]:
    """(one selector, declarations) for each selector of each rule in *path*."""

    return [
        (selector.strip(), dict(_declarations(body)))
        for selectors, body in _style_rules(path.read_text(encoding="utf-8"))
        for selector in _split_top(selectors, ",")
    ]


def _root_rule(path: Path) -> dict[str, str]:
    """The sheet's first `:root` rule, its unconditional tokens. The window's steps after it
    in styles.css restate the main view's gutter in `:root` rules inside `@media`."""

    return next(declarations for selector, declarations in _rules_of(path) if selector == ":root")


_ROLE_TAB = re.compile(r"""role="tab"|"role",\s*"tab"|role:\s*"tab\"""")
_TAB_SELECTOR = re.compile(r"\.[\w-]*\btabs?\b[\w-]*")
# The classes the tab primitive and its one bar variant are made of, and names that merely
# contain the word: `.tree-tab` would not pass, but a number's tabular figures are no tab.
_TAB_PRIMITIVE = frozenset({".tab-btn", ".tab-bar", ".nav-tab-bar"})
_TAB_OWNED = frozenset(
    {
        "background",
        "border",
        "border-bottom",
        "border-bottom-color",
        "color",
        "font",
        "font-family",
        "font-size",
        "font-weight",
        "letter-spacing",
        "padding",
        "text-transform",
    }
)


def test_every_tab_is_the_tab_primitive() -> None:
    """A tab is `.tab-btn`, in the markup, and no stylesheet draws one of its own.

    The pull request page's Conversation and Files changed were lowercase links under
    `.github-pull-tab`, which recreated the primitive's border, color, and padding, beside
    uppercase OVERVIEW and DOCUMENT everywhere else.
    """

    for source in _browser_sources():
        text = source.read_text(encoding="utf-8")
        for match in _ROLE_TAB.finditer(text):
            nearby = text[max(0, match.start() - 300) : match.end() + 300]
            assert "tab-btn" in nearby, (
                f"{source.name} gives an element role=tab without the .tab-btn primitive"
            )
    for sheet in _stylesheets():
        for selector, declarations in _rules_of(sheet):
            for name in _TAB_SELECTOR.findall(selector):
                if name in _TAB_PRIMITIVE:
                    continue
                recreated = sorted(_TAB_OWNED & set(declarations))
                assert not recreated, (
                    f"{sheet.name}: {selector} recreates the tab primitive's {recreated}"
                )
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    tab = _rule(styles, ".tab-btn")
    for token in (
        "--label-font-size",
        "--label-font-weight",
        "--label-text-transform",
        "--label-letter-spacing",
    ):
        assert f"var({token})" in tab, f".tab-btn lost {token}"
    active = _rule(styles, ".tab-btn.active")
    assert "border-bottom-color: var(--tab-active-color)" in active
    # A tab that is an address renders as the same tab.
    link = _rule(styles, "a.tab-btn")
    assert "text-decoration: none" in link and "line-height: normal" in link
    assert "outline: var(--focus-ring-width) solid var(--focus-ring-color)" in _rule(
        styles, ".tab-btn:focus-visible"
    )
    # Only core styles the primitive; a use site adds positioning from its own class.
    for sheet in _stylesheets()[1:]:
        for selector, _declared in _rules_of(sheet):
            assert ".tab-btn" not in selector, f"{sheet.name} restyles .tab-btn: {selector}"
    page = (REPO_ROOT / BUILTIN_PLUGINS / "github/pull-page.js").read_text(encoding="utf-8")
    assert 'class: "tab-bar", role: "tablist"' in page
    assert '"tab-btn", [label])' in page
    assert 'link.classList.toggle("active", model.tab === id)' in page
    assert 'link.setAttribute("aria-selected", String(model.tab === id))' in page


# Every font-size that is not a type-scale token, and why. A literal anywhere else fails.
_FONT_SIZE_EXEMPT: dict[tuple[str, str], str] = {
    # A glyph, not text: documented beside the ramp.
    ("styles.css", ".compression-badge"): "a 7px mark, iconography rather than text",
    # Paper is sized in points, as --kpress-print-font-size is.
    ("styles.css", '.preview-pane[data-printable="false"]::before'): "a sentence for print",
    # The fallback prose path a third-party plugin gets without KPress: its headings step
    # from whatever size the plugin's container sets, so they are relative on purpose.
    ("styles.css", ".md-body:not(.metabrowser-kpress-host) h1"): "relative fallback heading",
    ("styles.css", ".md-body:not(.metabrowser-kpress-host) h2"): "relative fallback heading",
    ("styles.css", ".md-body:not(.metabrowser-kpress-host) h3"): "relative fallback heading",
    ("styles.css", ".md-body:not(.metabrowser-kpress-host) h4"): "relative fallback heading",
    ("styles.css", ".md-body:not(.metabrowser-kpress-host) .checkbox"): "relative to its text",
    # A treemap cell's label and value are sized from the cell's area, set on each cell inline
    # by treemap-map.js; the stylesheet's defaults are the small size.
    ("folder/styles.css", ".tm-cell-label"): "a cell's size, from its area",
    ("folder/styles.css", ".tm-cell-sub"): "a cell's size, from its area",
}
# The ramp's tokens, and the role tokens that name one of them ("Type Scale"). A font size is
# one of these, so a size is a decision about a role, not a variable a stylesheet invents.
_TYPE_SCALE_TOKENS = frozenset(
    {
        "--page-title-font-size",
        "--document-body-font-size",
        "--body-font-size",
        "--tooltip-font-size",
        "--nav-font-size",
        "--ui-small-font-size",
        "--kbd-font-size",
        "--label-font-size",
        "--mono-block-font-size",
        "--git-ref-font-size",
        "--micro-font-size",
    }
)
_TYPE_SCALE_VALUE = re.compile(
    r"var\((" + "|".join(sorted(_TYPE_SCALE_TOKENS, key=len, reverse=True)) + r")\)"
)


def _sheet_name(sheet: Path) -> str:
    if sheet.parent == STATIC:
        return sheet.name
    return f"{sheet.parent.name}/{sheet.name}"


def test_font_sizes_come_from_the_type_scale() -> None:
    """No literal font size at a use site, as "Type Scale" says, or a reason named above.

    And no size outside the ramp: a `var()` names one of its tokens, never a variable of its
    own that a stylesheet sets to whatever it likes.

    A plugin's stylesheet is held to it too: it consumes the host's tokens, so a change to
    the ramp reaches it. `font` shorthands count, since they set a size just the same.
    """

    offenders: list[str] = []
    for sheet in _stylesheets():
        name = _sheet_name(sheet)
        for selector, declarations in _rules_of(sheet):
            if (name, selector) in _FONT_SIZE_EXEMPT:
                continue
            size = declarations.get("font-size")
            if size is not None and _TYPE_SCALE_VALUE.fullmatch(size) is None:
                offenders.append(f"{name}: {selector} sets font-size: {size}")
            shorthand = declarations.get("font", "")
            if re.search(r"\d(?:px|em|rem|pt|%)", shorthand):
                offenders.append(f"{name}: {selector} sets font: {shorthand}")
    assert not offenders, "\n  ".join(["literal font sizes:", *offenders])


# Who may set the small size, and why ("Type Scale"; mb-ctlu). The small size is the controls':
# chips, badges, buttons, filters, and menus. Secondary metadata, an age, a size, a count, a
# fetch or update time, a row's second line, a note, has no size of its own: it reads at the
# size of the text it accompanies. It was the small size on a dozen surfaces, a step under the
# 13 px rows and 14 px lines beside it, and the owner found an update time at three sizes on
# one screen. A rule that reaches for the small size is a control named here, or it is
# metadata at the wrong size.
_SMALL_SIZE_ROLES: dict[tuple[str, str], str] = {
    ("styles.css", ".app-header"): "the navigation header's controls; its path sets its own",
    ("styles.css", ".btn"): "a button",
    ("styles.css", ".parent-nav-arrow"): "a button's glyph",
    ("styles.css", ".fold-expander"): "a control row (Fold Expanders)",
    ("styles.css", ".menu-item"): "a menu",
    ("styles.css", ".menu-link-url"): "the destination shown inside a menu",
    ("styles.css", ".menu-version"): "a menu's line",
    ("styles.css", ".menu-select"): "a menu's control",
    ("styles.css", ".menu-row"): "a menu's line",
    ("styles.css", ".menu-number"): "a menu's control",
    ("styles.css", ".source-ref-selector-panel"): "a chip's menu",
    ("styles.css", ".chip"): "a chip",
    ("styles.css", ".chip-menu-count"): "a chip menu's count",
    ("styles.css", ".counterpart-status"): "a split button's result, where its menu was",
    ("styles.css", ".filter-check"): "a filter",
    ("styles.css", ".chip-clear"): "a chip's control",
    ("styles.css", ".file-header-badge"): "a badge",
    (
        "styles.css",
        ".mb-image-fallback",
    ): "the stand-in for a badge: an image the page does not load",
    ("styles.css", ".tree-container-badge"): "a tree row's leading letter, its slot's glyph",
    ("agents/agent-log.css", ".log-event-kind"): "a badge",
    ("github/styles.css", ".github-pull-labels"): "a row of label chips",
    ("github/styles.css", ".github-pull-label"): "a label chip",
    ("github/styles.css", ".github-pull-stacks"): "the stack chip's slot",
    ("html/styles.css", ".metabrowser-html-host .file-html-preview-open"): "a control",
    ("table/styles.css", ".table-chip"): "a filter chip",
    ("table/styles.css", ".table-fit-note"): "a control: it opens the Columns menu",
    ("table/styles.css", ".table-stored-mark"): "a badge",
    ("table/styles.css", ".table-ref"): "a reference chip",
    ("table/styles.css", ".table-menu-note"): "a menu's line",
}
# Who may set the micro size, a step under the controls': a mark, never running text.
_MICRO_SIZE_ROLES: dict[tuple[str, str], str] = {
    ("styles.css", ".chip-badge"): "a chip's count badge, a filled mark inside the chip",
    ("github/styles.css", ".github-pull-stack-dot"): "the dot between a stack's badges",
}
# The role tokens that are the small size, each a role of its own.
_SMALL_SIZE_TOKENS = frozenset({"--kbd-font-size", "--label-font-size", "--mono-block-font-size"})
# Metadata whose container sets the size it reads at, so it sets none and inherits it, and the
# parts of a line whose box sets the line's size (a Pulls row's number and place). A size
# restated here is a second place to change when the text beside it moves: the file header
# took four edits to follow the body size where it now takes none. A rule left off this list
# is not checked. Index progress has its own shared size across navigation and content;
# the table Chrome session compares those two actual surfaces.
_INHERITED_METADATA: tuple[tuple[str, str], ...] = (
    ("styles.css", ".notice"),
    ("styles.css", ".tip-detail"),
    ("styles.css", ".tree-item-size"),
    ("styles.css", ".tree-item-age-inline"),
    ("styles.css", ".tree-item.tree-page-more"),
    ("styles.css", ".tree-lazy-placeholder"),
    ("styles.css", ".tree-empty-note"),
    ("styles.css", ".recent-empty"),
    ("styles.css", ".source-freshness"),
    ("styles.css", ".changed-file-stats"),
    ("styles.css", ".git-graph-meta"),
    ("styles.css", ".git-graph-more"),
    ("styles.css", ".git-history-page-placeholder"),
    ("styles.css", ".git-panel-empty"),
    ("styles.css", ".git-commit-files-summary"),
    ("styles.css", ".git-stat-binary"),
    ("styles.css", ".file-header-path"),
    ("styles.css", ".file-header-mirror"),
    ("styles.css", ".file-header-size"),
    ("styles.css", ".folder-header-count"),
    ("styles.css", ".view-header-age"),
    ("diff/styles.css", ".metabrowser-diff-host .diff-file-path"),
    ("diff/styles.css", ".metabrowser-diff-host .diff-file-note"),
    ("github/styles.css", ".github-pulls-by"),
    ("github/styles.css", ".github-pulls-number"),
    ("github/styles.css", ".github-pulls-place"),
    ("github/styles.css", ".github-pulls-empty"),
    ("github/styles.css", ".github-pulls-foot"),
    ("github/styles.css", ".github-pull-files-line"),
    ("github/styles.css", ".github-pull-files-offer-floating"),
    ("structured-tree.css", ".tok-meta"),
)


def test_secondary_metadata_reads_at_its_texts_size() -> None:
    """The small size is the controls', and metadata takes its text's size ("Type Scale").

    The navigation column sets the list size once, so a primitive it shares with the main view
    takes it there; metadata whose container sets its size sets none; the hint strips take the
    keycaps' token. `tests/dom/type-scale-chrome.mjs` reads the computed sizes in Chrome.
    """

    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "test_secondary_metadata_reads_at_its_texts_size" in doc
    offenders: list[str] = []
    rules: dict[tuple[str, str], list[dict[str, str]]] = {}
    for sheet in _stylesheets():
        name = _sheet_name(sheet)
        for selector, declarations in _rules_of(sheet):
            rules.setdefault((name, selector), []).append(declarations)
            size = declarations.get("font-size")
            if size == "var(--ui-small-font-size)" and (name, selector) not in _SMALL_SIZE_ROLES:
                offenders.append(f"{name}: {selector} sets the small size")
            if size == "var(--micro-font-size)" and (name, selector) not in _MICRO_SIZE_ROLES:
                offenders.append(f"{name}: {selector} sets the micro size")
    assert not offenders, "\n  ".join(["sizes outside their roles:", *offenders])
    for key in _INHERITED_METADATA:
        assert key in rules, f"{key} is gone; update _INHERITED_METADATA"
        assert all("font-size" not in rule for rule in rules[key]), f"{key} restates its size"
    for key in (*_SMALL_SIZE_ROLES, *_MICRO_SIZE_ROLES):
        assert key in rules, f"{key} is gone; update its role list"
    shell = _rules_of(STATIC / "styles.css")
    root = {
        name: value
        for selector, declarations in shell
        if selector == ":root"
        for name, value in declarations.items()
    }
    tokens = {
        name
        for name, value in root.items()
        if value == "var(--ui-small-font-size)" and name.endswith("-font-size")
    }
    assert tokens == _SMALL_SIZE_TOKENS, tokens
    assert "--tooltip-detail-font-size" not in root, "a tooltip's detail inherits its size"

    def sizes(selector: str) -> list[str | None]:
        return [rule.get("font-size") for named, rule in shell if named == selector]

    assert "var(--nav-font-size)" in sizes(".tree-pane"), "the column sets its size once"
    # A hint strip labels keys, so it reads at the keycaps' token and moves with them.
    for strip in (".nav-shortcut-hints", ".search-palette-hint"):
        assert "var(--kbd-font-size)" in sizes(strip), strip
    # A commit's files outside the served folder are path rows in the main view, so they
    # read at the body size, as a file's header and a diff file bar do; their summary line
    # and line counts inherit it (_INHERITED_METADATA). No Chrome fixture draws them.
    assert set(sizes(".git-commit-file")) - {None} == {"var(--body-font-size)"}


def test_a_pill_is_the_pill_token_and_means_a_filter() -> None:
    """A radius literal is a one-off, and a chip's pill reads as a filter wherever it is."""

    for sheet in _stylesheets():
        for selector, declarations in _rules_of(sheet):
            radius = declarations.get("border-radius", "")
            assert "999px" not in radius, f"{sheet.name}: {selector} spells the pill as a literal"
    github = _rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css")
    for selector, declarations in github:
        assert declarations.get("border-radius") != "var(--radius-pill)", (
            f"{selector} is not a filter, so it does not take a filter's shape"
        )


# The sources that may state a toggle's ARIA, and the primitive each one states it for. A new
# surface reaches for the renderer, so it never appears here.
_TOGGLE_SOURCES: dict[str, str] = {
    "filter-controls.js": "the chip family's renderer",
    "app.js": ".menu-seg's checked mark and the drawer's .icon-btn toggle",
    "server.py": ".menu-seg in the shell's menu",
    "source-ref-selector.js": "marks a chip of its groupHtml in place",
    "agents/agent-log.js": "marks a chip of its groupHtml in place",
    "folder/treemap.js": "marks a chip of its groupHtml in place",
    "github/pulls-panel.js": "marks a chip of its groupHtml in place",
    "shell-keymap.js": "reads a filter menu's checked row to focus it, and renders none",
}
_TOGGLE_ARIA = re.compile(
    r"""aria-pressed|aria-checked|radiogroup|menuitemradio|menuitemcheckbox"""
    r"""|role="radio"|"role",\s*"radio"|role:\s*"radio\""""
)
# What a stylesheet may hang on that ARIA: the family's members.
_TOGGLE_SELECTORS = (".chip", ".menu-seg", ".menu-item", ".filter-drawer-toggle")


def test_a_toggle_cannot_fork_the_family() -> None:
    """A choice among values is one of the family in "Choosing Among Values".

    `.source-ref-selector-kind` was an exclusive choice drawn from scratch: its own border,
    no hover, the browser's focus ring, `aria-pressed` where a radio belongs, and no arrow
    keys, one panel away from the chip group that has all of that.
    """

    for source in _browser_sources():
        text = source.read_text(encoding="utf-8")
        key = source.name if source.parent == STATIC else f"{source.parent.name}/{source.name}"
        if source.name == "server.py":
            key = "server.py"
        if _TOGGLE_ARIA.search(text):
            assert key in _TOGGLE_SOURCES, (
                f"{key} states a toggle's ARIA itself. Render it through "
                "metabrowser.filterControls, or register why it cannot."
            )
    for sheet in _stylesheets():
        for selector, _declared in _rules_of(sheet):
            if "[aria-pressed" not in selector and "[aria-checked" not in selector:
                continue
            assert any(member in selector for member in _TOGGLE_SELECTORS), (
                f"{sheet.name}: {selector} draws a toggle outside the family"
            )
    ref_selector = (STATIC / "source-ref-selector.js").read_text(encoding="utf-8")
    assert "chipControls().groupHtml" in ref_selector
    assert "aria-pressed" not in ref_selector, "an exclusive choice is a radio"
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "### Choosing Among Values" in doc
    assert "test_a_toggle_cannot_fork_the_family" in doc


def test_exclusive_choices_share_one_answer_to_each_state() -> None:
    """A joined chip and a menu segment differ in shape and agree on what a state looks like."""

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    selected = (
        _rule(styles, '.chip-group[data-select="one"] > .chip[aria-checked="true"]'),
        _rule(styles, '.menu-seg[aria-checked="true"]'),
    )
    for rule in selected:
        assert "background: var(--highlight-bg)" in rule
        assert "color: var(--link)" in rule
    hover_chip = _rule(styles, ".chip-group > .chip:hover")
    assert "background: var(--hover-bg)" in hover_chip
    assert "background: var(--hover-bg)" in _rule(styles, ".menu-seg:hover")
    # Later than the rest fill it ties with, or a joined chip answers the pointer with
    # nothing, and earlier than the selected fill, which outranks it either way.
    chip_rest = styles.index(".chip-group > .chip {")
    wrapped_rest = styles.index('.chip-group:is([data-layout="wrap"], [data-fit="wrap"]) > .chip {')
    assert styles.index(".chip-group > .chip:hover {") > max(chip_rest, wrapped_rest)
    # One focus ring. A fill cannot be the signal, since a checked segment's would hide it.
    ring = "outline: var(--focus-ring-width) solid var(--focus-ring-color)"
    for selector in (".chip:focus-visible", ".menu-seg:focus-visible"):
        rule = _rule(styles, selector)
        assert ring in rule, f"{selector} lost the focus ring"
        assert "outline-offset: var(--focus-ring-offset)" in rule, (
            f"{selector} moved the focus ring"
        )
    # A consumer repaints a group from its state, so focus has to survive that.
    controls = (STATIC / "filter-controls.js").read_text(encoding="utf-8")
    assert "chip.isConnected === false" in controls


def test_every_prose_surface_reads_the_measure() -> None:
    """Prose wraps at the reader's "Max text width", wherever it is, as "Reading Width" says.

    A pull request's description ran the width of a 1100px literal, about 170 characters
    where a file on the same server wraps at 102, and ignored the setting.
    """

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "--doc-measure: calc(" in styles
    assert "--kpress-measure: var(--doc-measure)" in _rule(
        styles, ".metabrowser-kpress-host .kpress"
    )
    fallback = [
        declarations["max-width"]
        for selector, declarations in _rules_of(STATIC / "styles.css")
        if selector == ".md-body:not(.metabrowser-kpress-host) p" and "max-width" in declarations
    ]
    assert fallback == ["var(--doc-measure)"]
    overview = (REPO_ROOT / BUILTIN_PLUGINS / "folder/overview.css").read_text(encoding="utf-8")
    assert "var(--doc-measure)" in overview
    # Commit and PR pages start at the pane gutter and share the README's measure.
    rules = _rules_of(STATIC / "styles.css")
    columns = [
        declarations for selector, declarations in rules if selector == ".page-reading-column"
    ]
    assert len(columns) == 1
    column = columns[0]
    assert "var(--doc-measure)" in column["max-width"]
    assert column["margin-inline-end"] == "auto"
    placeholder_columns = [
        declarations
        for selector, declarations in rules
        if selector == ".pull-request-placeholder" and "max-width" in declarations
    ]
    assert placeholder_columns == [column]
    assert dict(rules)[".page-heading"]["font-size"] == "var(--page-title-font-size)"
    github_css = REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"
    page = dict(_rules_of(github_css))[".github-pull"]
    assert "--doc-measure" not in page
    assert (
        page["--page-reading-gutter"]
        == dict(_rules_of(STATIC / "styles.css"))[".pull-request-placeholder"][
            "--page-reading-gutter"
        ]
    )
    for selector, declarations in _rules_of(github_css):
        width = declarations.get("max-width", "")
        assert re.search(r"\d(?:px|rem|em|ch)", width) is None, (
            f"{selector} caps prose at a literal: {width}"
        )
    # A surface that rebuilds untrusted Markdown sets it in KPress's prose, which is what the
    # bridge above reaches. Plain rebuilt nodes would read at whatever width they are given.
    for source in sorted((REPO_ROOT / BUILTIN_PLUGINS).glob("*/*.js")):
        text = source.read_text(encoding="utf-8")
        if ".sanitizeHtml(" in text:
            assert ".kpressProse(" in text, f"{source.name} rebuilds Markdown outside KPress prose"
    # A document's text is held to the measure by the column class a trusted render carries.
    inert = (REPO_ROOT / BUILTIN_PLUGINS / "markdown/inert-render.js").read_text(encoding="utf-8")
    assert 'prose.classList.add("kpress-long-text")' in inert
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "test_every_prose_surface_reads_the_measure" in doc


def test_section_headings_and_fold_expanders_are_primitives() -> None:
    """A section's title and a withheld run of content look the same on every page."""

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    heading = _rule(styles, ".section-heading")
    for token in (
        "--body-font-size",
        "--label-font-weight",
        "--label-letter-spacing",
        "--label-text-transform",
        "--section-heading-divider-gap",
    ):
        assert f"var({token})" in heading, f".section-heading lost {token}"
    fold = _rule(styles, ".fold-expander")
    for declaration in (
        "min-height: var(--ui-row-height)",
        "background: var(--highlight-bg)",
        "color: var(--muted)",
    ):
        assert declaration in fold, f".fold-expander lost {declaration}"
    assert "background: var(--hover-bg)" in _rule(styles, ".fold-expander:hover")
    plugins = REPO_ROOT / BUILTIN_PLUGINS
    overview = (plugins / "folder/overview.js").read_text(encoding="utf-8")
    assert '"section-heading folder-overview-panel-heading"' in overview
    # One fold bar for every fold of a diff: a code file's run of changed lines and a
    # rendered Markdown file's run of unchanged blocks (docs/design-system.md, "Fold
    # Expanders").
    fold_bar = (plugins / "diff/diff-fold.js").read_text(encoding="utf-8")
    assert '"fold-expander diff-fold-control disclosure-toggle"' in fold_bar
    for user in ("diff/diff-view.js", "diff/diff-markdown.js"):
        source = (plugins / user).read_text(encoding="utf-8")
        assert re.search(
            r'import \{[^}]*\bfoldExpander\b[^}]*\} from "\./diff-fold\.js";', source
        ), user
        assert "fold-expander" not in source, f"{user} builds a fold bar of its own"
    page = (plugins / "github/pull-page.js").read_text(encoding="utf-8")
    headings = re.findall(r'h\("h2", \{([^}]+)\}', page)
    assert headings and len(headings) == page.count('h("h2",')
    assert all('class: "section-heading"' in attributes for attributes in headings)
    assert 'h("summary", { class: "fold-expander disclosure-toggle" }' in page
    # A hunk's fold states its size and then the inverse, as a fold does.
    assert "earlier ${lines}" in page and "`Hide ${earlierLines} ${lines}`" in page
    assert "section-disclosure-trigger" not in page
    github = plugins / "github/styles.css"
    for selector, declarations in _rules_of(github):
        assert not re.search(r"(?:^|\s)h[1-6]\b", selector), (
            f"{selector} sizes a heading in the page's stylesheet"
        )
        assert "text-transform" not in declarations, f"{selector} recreates a label's caps"
    # The native form of the one motion recipe, and it collapses to nothing at rest. The
    # first rule for the selector: the print and reduced-motion ones only adjust it.
    details: dict[str, dict[str, str]] = {}
    for selector, declarations in _rules_of(github):
        details.setdefault(selector, declarations)
    travel = details[".github-pull-hunk-earlier::details-content"]
    assert "height var(--transition-fast)" in travel["transition"]
    assert travel["interpolate-size"] == "allow-keywords"
    assert travel["height"] == "0"
    assert details[".github-pull-hunk-earlier[open]::details-content"]["height"] == "auto"


# A fold expander's two glyphs, KPress's table-of-contents pair, each by a path only it has
# (docs/design-system.md, "Fold Expanders"): chevrons-up-down closed, chevrons-down-up open.
FOLD_CLOSED_PATH = "m7 15 5 5 5-5"
FOLD_OPEN_PATH = "m7 20 5-5 5 5"
# The browser sources that build a fold expander, each with the builder it uses: the diff's
# factory, and a review comment's earlier lines, on a native summary.
_FOLD_BUILDERS = {
    "diff/diff-fold.js": '"fold-expander diff-fold-control disclosure-toggle"',
    "github/pull-page.js": '{ class: "fold-expander disclosure-toggle" }',
}
# The classes a fold is built of: the primitive, the diff's bar, and the pull page's fold.
_FOLD_CLASSES = ("fold-expander", "diff-fold-control", "github-pull-hunk-earlier")


def test_a_fold_expander_draws_the_pair_not_the_chevron() -> None:
    """Every fold leads with the expand/contract pair its primitive draws, never a chevron.

    A fold sets withheld content back in place; a chevron turns for a row's children. The
    primitive draws the pair from the control's own state, so no fold's markup holds a
    glyph, and none can turn one.
    """

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    rules = _rules_of(STATIC / "styles.css")
    glyph = dict(_declarations(_rule(styles, ".fold-expander::before")))
    assert glyph["content"] == '""'
    assert glyph["width"] == glyph["height"] == "var(--toggle-chevron-size)"
    assert glyph["background-color"] == "currentcolor", "the glyph is the expander's muted ink"
    assert f"d='{FOLD_CLOSED_PATH}'" in glyph["mask"] and FOLD_OPEN_PATH not in glyph["mask"]
    # Open is the control's own state: a button's aria-expanded, a native summary's open.
    opened = [
        (selector, declarations)
        for selector, declarations in rules
        if f"d='{FOLD_OPEN_PATH}'" in declarations.get("mask-image", "")
    ]
    assert [selector for selector, _ in opened] == [
        '.fold-expander[aria-expanded="true"]::before',
        "details[open] > summary.fold-expander::before",
    ]
    # The text's ink under the pointer and the ring, and CanvasText in forced colors, which
    # force the glyph's background to Canvas (tests/test_icon_catalog.py holds every mask).
    assert {
        declarations["background-color"]
        for selector, declarations in rules
        if selector == ".fold-expander:is(:hover, :focus-visible)::before"
    } == {"var(--text)", "CanvasText"}, (
        "the glyph takes the text's ink under the pointer and the ring"
    )
    # Nothing styles a chevron in a fold or turns anything there, and the control itself
    # does not move: only the group it opens travels.
    for sheet in _stylesheets():
        for selector, declarations in _rules_of(sheet):
            if not any(re.search(rf"\.{name}(?![\w-])", selector) for name in _FOLD_CLASSES):
                continue
            where = f"{_sheet_name(sheet)}: {selector}"
            assert "toggle-chevron" not in selector and "svg" not in selector, where
            assert not any("rotate" in value for value in declarations.values()), where
            if re.search(r"\.(?:fold-expander|diff-fold-control)(?![\w-])", selector):
                assert "transform" not in declarations, where
                assert "transition" not in declarations, where
    plugins = REPO_ROOT / BUILTIN_PLUGINS
    for path in [*_browser_sources(), *_stylesheets()]:
        text = path.read_text(encoding="utf-8")
        for retired in ("diff-fold-chevron", "github-pull-fold-chevron"):
            assert retired not in text, f"{path.name} names the fold's old chevron, {retired}"
    # Only the registered builders make a fold, and neither puts a glyph in it.
    building = {
        _source_key(source)
        for source in _browser_sources()
        if re.search(r"(?<![\w-])fold-expander(?![\w-])", source.read_text(encoding="utf-8"))
    }
    assert building == set(_FOLD_BUILDERS), "a new fold expander is built outside its builders"
    for key, builder in _FOLD_BUILDERS.items():
        assert builder in (plugins / key).read_text(encoding="utf-8"), key
        for glyph_text, listed_builder in _TOGGLE_GLYPHS.get(key, ()):
            assert listed_builder != builder or "summary" in glyph_text, (
                f"{key} puts {glyph_text} in a fold expander, which draws its own glyph"
            )
    # The factory's body alone, to its top-level closing brace, so a glyph helper declared
    # after it in the file is not read as the factory's.
    fold = (plugins / "diff/diff-fold.js").read_text(encoding="utf-8")
    factory = fold.split("export function foldExpander", 1)[1].split("\n}\n", 1)[0]
    assert "return { control, group" in factory, "the slice is not foldExpander's body"
    assert "shellIcon(" not in factory, "foldExpander draws a glyph; .fold-expander draws it"
    page = (plugins / "github/pull-page.js").read_text(encoding="utf-8")
    assert re.search(
        r'h\("summary", \{ class: "fold-expander disclosure-toggle" \}, \[\s*'
        r'h\("span", \{ class: "github-pull-fold-closed" \}',
        page,
    ), "a review comment's fold summary holds its words alone"
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "test_a_fold_expander_draws_the_pair_not_the_chevron" in doc


# ── Disclosure toggles never select text ───────────────────────────
#
# docs/design-system.md, "Disclosure Toggles Never Select Text". Every browser source
# that builds a toggle's markers -- the registry chevron, a `summary`, `aria-expanded` --
# is registered: with the builders that carry `.disclosure-toggle`, each named by text
# unique to it, or with why what it builds is not a toggle. Every chevron and `summary`
# a source builds is listed, in order, with the builder whose element it goes into, so
# a new one fails until it is listed, even beside a marked toggle. What the check cannot
# see is which element a listed glyph lands in: it holds only that the builder it is
# listed with sits within a window of it, and review holds the rest.

_TOGGLE_MARKER = re.compile(
    r"aria-expanded|ariaExpanded|<summary|createElement\(\"summary\"\)|h\(\s*\"summary\""
    r"|ICONS\.toggle|icons\.toggle|MetabrowserIcons\?\.toggle|shellIcon\(\"toggle\"\)"
    r"|registryIcon\(\"toggle\"\)|host\.chevron\(\)|srow-chevron\""
)
# A chevron or summary going into markup, each of which `_TOGGLE_GLYPHS` lists.
_TOGGLE_GLYPH = re.compile(
    r"\$\{ICONS\.toggle\}|ICONS\.toggle \+|icon: ICONS\.toggle|ICONS\.toggle,|"
    r"\$\{menuChevron\}|MetabrowserIcons\?\.toggle \?\?|shellIcon\(\"toggle\"\)|"
    r"mb\.icons\.toggle \+|host\.chevron\(\)|\[chevron\(\)\]|^\s*chevron\(\),|srow-chevron\""
    r"|<summary|createElement\(\"summary\"\)|h\(\s*\"summary\"",
    re.MULTILINE,
)
# How close a glyph sits to the builder it is listed with, in characters: just past the
# farthest today, before it (a chip menu's caret) and after it (a Pulls row's chevron).
_TOGGLE_NEAR_BEFORE = 600
_TOGGLE_NEAR_AFTER = 320

_DISCLOSURE_TOGGLES: dict[str, tuple[str, ...]] = {
    "app.js": (
        'class="tree-item tree-folder disclosure-toggle ${stateClass}',
        '" tree-container disclosure-toggle collapsed"',
        "'<div class=\"tree-item tree-folder disclosure-toggle collapsed'",
        'className: "filter-drawer-toggle disclosure-toggle"',
        '"icon-btn nav-collapse-toggle disclosure-toggle"',
    ),
    "server.py": ('class="icon-btn root-details-trigger disclosure-toggle"',),
    "charts.js": ("'<div class=\"tally-node disclosure-toggle'",),
    "filter-controls.js": ('class="chip chip-menu-trigger disclosure-toggle"',),
    "source-ref-selector.js": ('"icon-btn source-ref-selector-toggle disclosure-toggle"',),
    # The View on GitHub button's chevron, which opens its menu.
    "plugin-sdk-views.js": (
        '"git-ref-action", "disclosure-toggle"',
        '"git-ref-menu-hit disclosure-toggle"',
        '"chip chip-menu-trigger counterpart-more disclosure-toggle"',
    ),
    "agents/agent-log.js": ('class="log-event-header disclosure-toggle"',),
    "event_log/event-log-views.js": ('"disclosure-toggle event-log-row-head"',),
    "structured-tree.js": ('" srow-container disclosure-toggle"',),
    "structured-node-table.js": ('"btn structured-branch-toggle disclosure-toggle"',),
    "markdown/inert-toc.js": ('"kpress-toc-toggle disclosure-toggle"',),
    "markdown/frontmatter-view.js": (
        'summary.className = "section-disclosure-trigger disclosure-toggle"',
    ),
    "markdown/fenced-views.js": (
        'summary.className = "section-disclosure-trigger disclosure-toggle"',
    ),
    "markdown/rendered.js": ('class="section-disclosure-trigger disclosure-toggle">Diagnostics',),
    "folder/distribution-view.js": (
        "file-type-summary-details-toggle disclosure-toggle",
        '"file-type-summary-disclosure section-disclosure-trigger disclosure-toggle"',
    ),
    "folder/overview.js": (
        '"folder-overview-panel-toggle section-disclosure-trigger disclosure-toggle"',
    ),
    "diff/diff-fold.js": ('"fold-expander diff-fold-control disclosure-toggle"',),
    "diff/diff-view.js": (
        '"diff-file-bar disclosure-toggle"',
        '"diff-summary diff-summary-toggle summary-toggle disclosure-toggle collapsed"',
    ),
    "diff/diff-summary.js": (
        '"changed-file-row diff-summary-row diff-summary-folder disclosure-toggle"',
    ),
    "diff/diff-markdown.js": ('heading.className = "disclosure-toggle"',),
    "github/pulls-panel.js": (
        '"github-pulls-change disclosure-toggle collapsed"',
        '"github-pulls-row github-pulls-stack-row disclosure-toggle"',
        '"github-pulls-change github-pulls-whole-change disclosure-toggle collapsed"',
    ),
    "github/pull-files-view.js": ('"changed-file-row github-pull-folder-row disclosure-toggle"',),
    "github/pull-page.js": (
        '"btn github-pull-stack-trigger disclosure-toggle"',
        '{ class: "fold-expander disclosure-toggle" }',
    ),
    "github/stack-page.js": (
        '"summary-toggle github-pull-stack-members-toggle disclosure-toggle collapsed"',
    ),
}
# Sources with a marker that build no toggle of their own, and why.
_NOT_TOGGLES: dict[str, str] = {
    "file-watches.js": "reads aria-expanded on the tree rows app.js builds",
    "tree-keyboard-navigation.js": "reflects aria-expanded on the tree rows app.js builds",
    "overlay-layer.js": "a dialog's trigger, an icon or labelled button, is not a disclosure",
    "search-palette.js": "the search field is a combobox, and its text stays editable",
    "shell-keymap.js": "reads which filter dropdown is open, for its rows' letters",
    "nav-collapse.js": "reflects aria-expanded on the chevron server.py writes and app.js draws",
    "table/table-view.js": "the Columns button and a header's menu button open dialogs, not disclosures",
}
# Each chevron and `summary` a source builds, in source order, with the builder whose
# element it goes into. Whitespace in a glyph is collapsed to one space.
_TOGGLE_GLYPHS: dict[str, tuple[tuple[str, str], ...]] = {
    "app.js": (
        ("${ICONS.toggle}", 'class="tree-item tree-folder disclosure-toggle ${stateClass}'),
        ("${ICONS.toggle}", '" tree-container disclosure-toggle collapsed"'),
        ("icon: ICONS.toggle", 'className: "filter-drawer-toggle disclosure-toggle"'),
        ("ICONS.toggle +", "'<div class=\"tree-item tree-folder disclosure-toggle collapsed'"),
        ("${ICONS.toggle}", '"icon-btn nav-collapse-toggle disclosure-toggle"'),
    ),
    "charts.js": (("ICONS.toggle +", "'<div class=\"tally-node disclosure-toggle'"),),
    "filter-controls.js": (("${menuChevron}", 'class="chip chip-menu-trigger disclosure-toggle"'),),
    "source-ref-selector.js": (
        (
            "MetabrowserIcons?.toggle ??",
            '"icon-btn source-ref-selector-toggle disclosure-toggle"',
        ),
    ),
    "plugin-sdk-views.js": (
        ("MetabrowserIcons?.toggle ??", '"git-ref-action", "disclosure-toggle"'),
        (
            "MetabrowserIcons?.toggle ??",
            '"chip chip-menu-trigger counterpart-more disclosure-toggle"',
        ),
    ),
    "agents/agent-log.js": (("mb.icons.toggle +", 'class="log-event-header disclosure-toggle"'),),
    "structured-tree.js": (('srow-chevron"', '" srow-container disclosure-toggle"'),),
    "structured-node-table.js": (
        ("MetabrowserIcons?.toggle ??", '"btn structured-branch-toggle disclosure-toggle"'),
    ),
    "markdown/frontmatter-view.js": (
        (
            'createElement("summary")',
            'summary.className = "section-disclosure-trigger disclosure-toggle"',
        ),
    ),
    "markdown/fenced-views.js": (
        (
            'createElement("summary")',
            'summary.className = "section-disclosure-trigger disclosure-toggle"',
        ),
    ),
    "markdown/rendered.js": (
        ("<summary", 'class="section-disclosure-trigger disclosure-toggle">Diagnostics'),
    ),
    "diff/diff-view.js": (
        ('shellIcon("toggle")', '"diff-file-bar disclosure-toggle"'),
        (
            'shellIcon("toggle")',
            '"diff-summary diff-summary-toggle summary-toggle disclosure-toggle collapsed"',
        ),
    ),
    "diff/diff-summary.js": (
        (
            "host.chevron()",
            '"changed-file-row diff-summary-row diff-summary-folder disclosure-toggle"',
        ),
    ),
    "diff/diff-markdown.js": (
        ('createElement("summary")', 'heading.className = "disclosure-toggle"'),
    ),
    "github/pulls-panel.js": (
        ("[chevron()]", '"github-pulls-change disclosure-toggle collapsed"'),
        ("[chevron()]", '"github-pulls-row github-pulls-stack-row disclosure-toggle"'),
        (
            "[chevron()]",
            '"github-pulls-change github-pulls-whole-change disclosure-toggle collapsed"',
        ),
    ),
    "github/pull-files-view.js": (
        ("host.chevron()", '"changed-file-row github-pull-folder-row disclosure-toggle"'),
    ),
    "github/pull-page.js": (
        ('h( "summary"', '"btn github-pull-stack-trigger disclosure-toggle"'),
        ('h("summary"', '{ class: "fold-expander disclosure-toggle" }'),
    ),
    "github/stack-page.js": (
        (
            "[chevron()]",
            '"summary-toggle github-pull-stack-members-toggle disclosure-toggle collapsed"',
        ),
    ),
}
# A glyph built far from its builder: a folder row's parts are made by one function and
# put in the row by another.
_GLYPH_FAR_FROM_BUILDER: frozenset[tuple[str, str]] = frozenset(
    {("github/pull-files-view.js", "host.chevron()"), ("diff/diff-summary.js", "host.chevron()")}
)
# The classes the registered toggles are made of. A stylesheet that gives one of them a
# selectable `user-select` reopens the toggle, whether or not its selector also names
# `.disclosure-toggle`.
_TOGGLE_CLASSES: frozenset[str] = frozenset(
    {
        "tree-item",
        "tree-folder",
        "tree-container",
        "filter-drawer-toggle",
        "tally-node",
        "chip",
        "chip-menu-trigger",
        "source-ref-selector-toggle",
        "log-event-header",
        "event-log-row-head",
        "srow-container",
        "kpress-toc-toggle",
        "section-disclosure-trigger",
        "file-type-summary-disclosure",
        "file-type-summary-details-toggle",
        "folder-overview-panel-toggle",
        "fold-expander",
        "diff-fold-control",
        "diff-file-bar",
        "diff-summary-toggle",
        "diff-summary-folder",
        "github-pulls-row",
        "github-pulls-stack-row",
        "github-pull-folder-row",
        "changed-file-row",
        "btn",
        "github-pull-stack-trigger",
        "github-pull-stack-members-toggle",
        "summary-toggle",
    }
)
# One compound selector that names a toggle: its marker class, a component class, or a
# summary.
_TOGGLE_COMPOUND = re.compile(
    r"\.(?:disclosure-toggle|"
    + "|".join(sorted(map(re.escape, _TOGGLE_CLASSES), key=len, reverse=True))
    + r")(?![\w-])|(?:^|[(,\s])summary(?![\w-])"
)


def _selects_in_a_toggle(selector: str) -> bool:
    """Whether a selector's subject is a toggle or inside one.

    A compound contains the subject when it is the subject or is followed by a
    descendant or child combinator: what it reaches is inside it, and so is any later
    sibling of that. A compound followed by `+` or `~` is a sibling, never around the
    subject, so content a toggle reveals beside it is not in the toggle.
    """

    tokens = _compounds(selector)
    for index, token in enumerate(tokens):
        if token in (">", "+", "~"):
            continue
        following = tokens[index + 1] if index + 1 < len(tokens) else ""
        if following in ("+", "~"):
            continue
        if _TOGGLE_COMPOUND.search(token):
            return True
    return False


def _source_key(source: Path) -> str:
    if source.name == "server.py" or source.parent == STATIC:
        return source.name
    return f"{source.parent.name}/{source.name}"


def _toggle_sheet_problems(name: str, css: str) -> list[str]:
    """Where one stylesheet lets a toggle select text, in WebKit or anywhere."""

    problems: list[str] = []
    for selectors, body in _style_rules(css):
        declarations = _declarations(body)
        names = [declared for declared, _value in declarations]
        values = dict(declarations)
        # WebKit applies only the prefixed half, so one without it is a no-op there.
        if "user-select" in names and values.get("-webkit-user-select") != values["user-select"]:
            problems.append(f"{name}: {selectors} sets user-select without -webkit-user-select")
        for selector in _split_top(selectors, ","):
            if not _selects_in_a_toggle(selector) or selector.strip() in (
                ".disclosure-toggle",
                "summary",
            ):
                continue
            for declared in ("user-select", "-webkit-user-select"):
                value = values.get(declared, "var(--toggle-user-select)")
                if value not in ("var(--toggle-user-select)", "none"):
                    problems.append(f"{name}: {selector} lets a toggle select text")
        if name != "styles.css" and any(
            selector.strip() == ".disclosure-toggle" for selector in _split_top(selectors, ",")
        ):
            problems.append(f"{name} redefines .disclosure-toggle")
    return problems


def _toggle_source_problems(key: str, text: str) -> list[str]:
    """Where one browser source builds a toggle the registry does not account for."""

    if not _TOGGLE_MARKER.search(text):
        if key in _DISCLOSURE_TOGGLES or key in _NOT_TOGGLES:
            return [f"{key} builds no toggle any more; drop it from the registry"]
        return []
    if key not in _DISCLOSURE_TOGGLES and key not in _NOT_TOGGLES:
        return [
            f"{key} builds a chevron, a summary, or aria-expanded. Give each toggle it "
            "builds the .disclosure-toggle class and register its builders, or register "
            "why it builds no toggle."
        ]
    problems: list[str] = []
    builders = _DISCLOSURE_TOGGLES.get(key, ())
    for builder in builders:
        if "disclosure-toggle" not in builder or builder not in text:
            problems.append(f"{key} no longer builds {builder!r}")
    listed = _TOGGLE_GLYPHS.get(key, ())
    matches = list(_TOGGLE_GLYPH.finditer(text))
    found = [re.sub(r"\s+", " ", match.group().strip()) for match in matches]
    if found != [glyph for glyph, _builder in listed]:
        problems.append(
            f"{key} builds the chevrons and summaries {found}, but the registry lists "
            f"{[glyph for glyph, _builder in listed]}. Give each new one's element the "
            ".disclosure-toggle class and list it with that element's builder."
        )
        return problems
    for match, (glyph, builder) in zip(matches, listed, strict=True):
        if builder not in builders:
            problems.append(f"{key}: {glyph} is listed with {builder!r}, not a builder")
            continue
        if (key, glyph) in _GLYPH_FAR_FROM_BUILDER:
            continue
        nearby = text[
            max(0, match.start() - _TOGGLE_NEAR_BEFORE) : match.end() + _TOGGLE_NEAR_AFTER
        ]
        if builder not in nearby:
            line = text.count("\n", 0, match.start()) + 1
            problems.append(f"{key}:{line} builds {glyph} away from {builder!r}")
    return problems


def test_disclosure_toggles_never_select_text() -> None:
    """A toggle carries one class, and its one rule keeps every engine from selecting text.

    A triple click on a rendered Markdown diff's unchanged-blocks fold selected its label
    and every paragraph it revealed, and in WebKit, the macOS app's engine, a double click
    on a folder row selected its name: WebKit reads only `-webkit-user-select`.
    """

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "--toggle-user-select: none;" in styles
    rule = dict(_rules_of(STATIC / "styles.css"))
    for selector in (".disclosure-toggle", "summary"):
        declared = rule[selector]
        assert declared["-webkit-user-select"] == "var(--toggle-user-select)", selector
        assert declared["user-select"] == "var(--toggle-user-select)", selector
    problems: list[str] = []
    for sheet in _stylesheets():
        problems += _toggle_sheet_problems(_sheet_name(sheet), sheet.read_text(encoding="utf-8"))
    for source in _browser_sources():
        problems += _toggle_source_problems(_source_key(source), source.read_text(encoding="utf-8"))
    assert not problems, "\n  ".join(["toggles that can select text:", *problems])
    every_builder = " ".join(b for listed in _DISCLOSURE_TOGGLES.values() for b in listed)
    for name in sorted(_TOGGLE_CLASSES):
        assert re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", every_builder), (
            f"{name} is no registered toggle's class"
        )
    assert set(_TOGGLE_GLYPHS) <= set(_DISCLOSURE_TOGGLES)

    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "### Disclosure Toggles Never Select Text" in doc
    assert "test_disclosure_toggles_never_select_text" in doc


def test_an_unmarked_chevron_beside_a_marked_toggle_fails() -> None:
    """A second chevron control built beside a marked one is a toggle the class misses.

    Review A of #394 traced it: the character window found the neighbour's class, so a
    new chevron button built just after a diff fold's passed.
    """

    key = "diff/diff-fold.js"
    text = (REPO_ROOT / BUILTIN_PLUGINS / key).read_text(encoding="utf-8")
    anchor = '  control.className = "fold-expander diff-fold-control disclosure-toggle";\n'
    assert anchor in text
    beside = anchor + (
        '  const more = document.createElement("button");\n'
        '  more.className = "diff-fold-more";\n'
        '  more.innerHTML = shellIcon("toggle");\n'
    )
    assert _toggle_source_problems(key, text) == []
    assert _toggle_source_problems(key, text.replace(anchor, beside))


def test_a_toggle_components_own_selection_override_fails() -> None:
    """`user-select: text` on a toggle, or on anything inside one, reopens it.

    What a selector selects is its subject, so a toggle class decides only when the
    subject is that element or inside it. Content a toggle reveals is its sibling, and a
    rule reached through `+` or `~` may make it selectable (review B of #394).
    """

    selectable = "{ -webkit-user-select: text; user-select: text; }"
    for reopens in (
        ".log-event-header",
        ".tree-folder .tree-item-name",
        ".tree-folder > .tree-item-name",
        ".tree-folder .tree-toggle + .tree-item-name",
        "details > summary",
    ):
        assert _toggle_sheet_problems("styles.css", f"{reopens} {selectable}"), reopens
    for revealed in (
        ".log-event-raw",
        ".log-event-header + .log-event-raw",
        ".log-event-header ~ .log-event-raw pre",
        "summary + p",
    ):
        assert not _toggle_sheet_problems("styles.css", f"{revealed} {selectable}"), revealed


def _oklch_channels(value: str) -> tuple[float, float, float]:
    """Lightness (0 to 1), chroma, and hue of one `oklch(L% C H)` or `oklch(L C H)`."""

    found = re.fullmatch(r"oklch\(([\d.]+)(%?) ([\d.]+) ([\d.]+)\)", value.strip())
    assert found is not None, value
    lightness = float(found[1]) / 100 if found[2] else float(found[1])
    return lightness, float(found[3]), float(found[4])


def _relative_luminance(lightness: float, chroma: float, hue: float) -> float:
    """WCAG relative luminance of an oklch color, from its linear sRGB channels."""

    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    long = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    medium = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    short = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    red = 4.0767416621 * long - 3.3077115913 * medium + 0.2309699292 * short
    green = -1.2684380046 * long + 2.6097574011 * medium - 0.3413193965 * short
    blue = -0.0041960863 * long - 0.7034186147 * medium + 1.7076147010 * short
    channels = [min(max(channel, 0.0), 1.0) for channel in (red, green, blue)]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (
            _relative_luminance(*_oklch_channels(foreground)),
            _relative_luminance(*_oklch_channels(background)),
        ),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_pull_state_colors_keep_their_hue_and_read_on_both_grounds() -> None:
    """Each of the plugin's colors is one color seen against two backgrounds, legible on both.

    `test_themed_colors_keep_their_hue` reads the shell's stylesheet; these tokens are the
    plugin's, as a domain's tokens are (docs/design-system.md, "Token Layers"): a pull
    request's four states, and the attention tone of its readiness. A state's badge sets its
    name in its color, and a readiness's badge its label, so each is held to the 4.5:1 of
    text, on the surface the page's header sits on and on the panel's. Every color the
    plugin's theme rules declare is held, so a new one cannot miss the check.
    """

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    light_block, dark_block = _theme_blocks()
    # The plugin's own theme rules, parsed and merged: its states' and its readiness's are
    # rules of their own, and a comment or another rule's brace cannot move them.
    plugin_light: dict[str, str] = {}
    plugin_dark: dict[str, str] = {}
    for selector, body in _rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"):
        if selector == ":root":
            plugin_light.update(body)
        elif selector == '[data-theme="dark"]':
            plugin_dark.update(body)
    colors = sorted(token for token, value in plugin_light.items() if value.startswith("oklch("))
    assert colors == sorted(plugin_dark), "each of the plugin's colors is themed, and only those"
    assert "--github-pull-attention" in colors, "a readiness's attention is the plugin's color"
    assert "--sidebar-bg" in styles
    for token in colors:
        light = plugin_light[token]
        dark = plugin_dark[token]
        assert _oklch_channels(light)[2] == _oklch_channels(dark)[2], f"{token} changes hue"
        for theme, block, color in (("light", light_block, light), ("dark", dark_block, dark)):
            for ground in ("--bg", "--sidebar-bg"):
                surface = _declared(block, ground)
                assert _contrast(color, surface) >= 4.5, (
                    f"{token} on {ground} in the {theme} theme reads at "
                    f"{_contrast(color, surface):.2f}:1"
                )


def test_a_readinesss_color_is_its_tones_alone_and_reads_where_it_is_drawn() -> None:
    """A readiness's glyph and badge take their tone's ink, never their verdict's.

    The server gives each verdict its tone (`Tone` in pull_readiness.py), and pull-readiness.js
    writes both on the mark; only the tone may color it, so a verdict cannot read in one color
    on one surface and another elsewhere (docs/design-system.md, "A Pull Request’s
    Readiness"). The glyph and the badge of a tone are one ink, each tone is its own, the
    section's table of each tone's ink is the stylesheet's, and each is held to the 4.5:1 of
    text in both themes on the page, where the header and the Checks tab draw it, and on the
    panel, where a Pulls row does. Attention is not the shell's warning ink, which is
    reserved for a degraded result: its hue is outside the family
    `test_status_text_inks_keep_their_fills_hue` allows one ink.
    """

    by_verdict = [
        f"{_sheet_name(sheet)} {selector}"
        for sheet in _stylesheets()
        for selector, _declarations in _rules_of(sheet)
        if "data-verdict" in selector
    ]
    assert by_verdict == [], "a readiness is colored by its tone, never its verdict"
    rules = _rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css")
    github = dict(rules)
    tones = get_args(Tone.__value__)
    inks: dict[str, str] = {}
    for tone in tones:
        icon = github[f'.github-pull-readiness-icon[data-tone="{tone}"]']["color"]
        badge = github[f'.github-pull-badge.github-pull-readiness[data-tone="{tone}"]']["color"]
        requirement = github[f'.github-pull-badge.github-pull-requirement[data-tone="{tone}"]'][
            "color"
        ]
        assert icon == badge == requirement, (
            f"the {tone} glyph, verdict's badge, and requirement's badge are one ink"
        )
        inks[tone] = icon
    assert len(set(inks.values())) == len(tones), "each tone is its own ink"
    # Waiting is one color across the plugin: a pending check is the attention tone's ink.
    assert github['.github-pull-badge[data-state="pending"]']["color"] == inks["attention"]
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    section = doc[doc.index("### A Pull Request’s Readiness") :]
    section = section[: section.index("\n### ")]
    table = dict(re.findall(r"^\| `(\w+)` \| `(--[\w-]+)`", section, flags=re.MULTILINE))
    assert {tone: f"var({token})" for tone, token in table.items()} == inks
    plugin = {
        theme: {
            name: value
            for selector, declarations in rules
            if selector == scope
            for name, value in declarations.items()
        }
        for theme, scope in (("light", ":root"), ("dark", '[data-theme="dark"]'))
    }
    shell = _theme_tokens()
    themes = {
        "light": {**shell["light"], **plugin["light"]},
        "dark": {**shell["dark"], **plugin["light"], **plugin["dark"]},
    }
    for theme, tokens in themes.items():
        colors: dict[str, str] = {}
        for tone, ink in inks.items():
            alias = re.fullmatch(r"var\((--[\w-]+)\)", ink)
            assert alias is not None, f"the {tone} ink is a token: {ink}"
            colors[tone] = _resolved(tokens, alias[1])
            ink_luminance = _srgb_luminance(_srgb(colors[tone]))
            for ground in ("--bg", "--sidebar-bg"):
                ratio = _ratio(ink_luminance, _srgb_luminance(_ground(tokens, ground)))
                assert ratio >= _AA_TEXT, (
                    f"the {tone} ink on {ground} in the {theme} theme reads at {ratio:.2f}:1"
                )
            # A Pulls row's glyph, a mark and not text, on the row under the pointer and as
            # the open one, the highlight's tint over the panel (mb-3n21).
            for ground in ("--hover-bg", "--highlight-bg"):
                ratio = _ratio(ink_luminance, _srgb_luminance(_ground(tokens, ground)))
                assert ratio >= _AA_GRAPHIC, (
                    f"the {tone} glyph on {ground} in the {theme} theme reads at {ratio:.2f}:1"
                )
        # The label after it is text, in an ink no tone sets, and reads at a text's contrast
        # on every ground a row has.
        label = next(
            declarations["color"]
            for selector, declarations in rules
            if selector == ".github-pulls-readiness-label" and "color" in declarations
        )
        assert label not in inks.values(), "a row's label takes no tone's ink"
        label_alias = re.fullmatch(r"var\((--[\w-]+)\)", label)
        assert label_alias is not None, f"the label's ink is a token: {label}"
        label_luminance = _srgb_luminance(_srgb(_resolved(tokens, label_alias[1])))
        for ground in ("--sidebar-bg", "--hover-bg", "--highlight-bg"):
            ratio = _ratio(label_luminance, _srgb_luminance(_ground(tokens, ground)))
            assert ratio >= _AA_TEXT, (
                f"a row's label on {ground} in the {theme} theme reads at {ratio:.2f}:1"
            )
        warning = _oklch_channels(_resolved(tokens, "--status-warning-text"))[2]
        assert _hue_gap(_oklch_channels(colors["attention"])[2], warning) > 15, (
            f"attention is the shell's warning ink in the {theme} theme"
        )


def _declared(block: str, token: str) -> str:
    found = re.search(rf"^\s*{re.escape(token)}:\s*([^;]+);", block, flags=re.MULTILINE)
    assert found is not None, token
    return found[1]


def test_the_pulls_tab_carries_the_shells_primitives() -> None:
    """What "The Pulls Tab" says it reuses is what its markup and stylesheet say."""

    panel = (REPO_ROOT / BUILTIN_PLUGINS / "github/pulls-panel.js").read_text(encoding="utf-8")
    state = (REPO_ROOT / BUILTIN_PLUGINS / "github/pull-state.js").read_text(encoding="utf-8")
    page = (REPO_ROOT / BUILTIN_PLUGINS / "github/pull-page.js").read_text(encoding="utf-8")
    icons = (STATIC / "icons.js").read_text(encoding="utf-8")
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "## The Pulls Tab" in doc
    assert "test_the_pulls_tab_carries_the_shells_primitives" in doc
    github = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"))
    # One Chevron, One Row Contract: the row height, the hover, and a row's own focus ring. A
    # pull request's run and last line are one item (mb-1z7j): its zone hovers, carries the
    # current mark, and takes the ring of the link inside it, as a Files row's `.tree-item` does.
    row = github[".github-pulls-row"]
    assert row["min-height"] == "var(--ui-row-height)"
    item = ".github-pulls-entry"
    assert github[f"{item}:hover"]["background"] == "var(--hover-bg)"
    assert github[".github-pulls-stack-row:hover"]["background"] == "var(--hover-bg)"
    assert (
        github[f"{item}:has(> .github-pulls-row.selected)"]["background"] == "var(--highlight-bg)"
    )
    assert github[".github-pulls-row.selected"]["border-left-color"] == "var(--highlight-bar)"
    ring = github[f"{item}:has(> .github-pulls-row:focus-visible)"]
    assert ring["outline"] == "var(--focus-ring-width) solid var(--focus-ring-color)"
    assert ring["outline-offset"] == "var(--focus-ring-offset)"
    assert (
        github[".github-pulls-stack-row:focus-visible"]["outline"]
        == "var(--focus-ring-width) solid var(--focus-ring-color)"
    )
    assert github[f"{item} > .github-pulls-row:focus-visible"]["outline"] == "none"
    # The toggle, the lines and the chevron, is the item's inner target: no ground of its own,
    # and only its chevron's plate answers the pointer, so its status inks keep the grounds
    # their contrast is held on.
    assert ".github-pulls-change:hover" not in github
    assert github[".github-pulls-change:hover > .github-pulls-toggle"]["background"] == (
        "var(--border)"
    )
    assert "transition" not in row, "a row crossed by a held key answers with no easing"
    # Icons: the app's glyph, in the state's color and never its own. The four shapes are the
    # plugin's, Lucide's, and drawn only on a GitHub repository's page, so no folder's startup
    # scripts carry them.
    assert github[".github-pull-state-icon svg"]["width"] == "var(--icon-glyph)"
    for name, lucide in (
        ("gitPullRequest", "git-pull-request"),
        ("gitPullRequestDraft", "git-pull-request-draft"),
        ("gitMerge", "git-merge"),
        ("gitPullRequestClosed", "git-pull-request-closed"),
    ):
        assert f"{name}: // Lucide `{lucide}`" in state
        assert f'"{name}"' in state
        assert name not in icons, f"{name} is back in the shell's eager icon registry"
    assert 'fill="none" stroke="currentColor"' in state, "a state's glyph takes its color"
    # A row and its page match: one state's icon, from one module; a Pulls row draws its
    # icon with its fields (stack-member-row.js).
    member_row = (REPO_ROOT / BUILTIN_PLUGINS / "github/stack-member-row.js").read_text(
        encoding="utf-8"
    )
    assert "pullStateIcon(" in member_row and "pullStateIcon(" in page
    assert 'aria-label", PULL_STATES[state].label' in state
    # Filters, buttons, and the spinner are the shell's.
    assert "controls.groupHtml(" in panel
    assert 'class: "github-pulls-connection nav-metadata nav-metadata-note"' in panel
    assert 'class: "github-pulls-status nav-metadata"' in panel
    assert '"mb-delayed-loading"' in panel
    assert 'class: "spinner spinner-sm"' in panel
    # No control or notice counts the rows held. Below them, pages still on their way show
    # the nav's own scan indicator, its spinner and text classes, after the quiet period.
    assert "github-pulls-more" not in panel and "Showing last" not in panel
    assert "Catalog paused" not in panel
    assert 'class: "github-pulls-progress mb-delayed-loading"' in panel
    assert 'h("span", { class: "index-progress-spinner", "aria-hidden": "true" })' in panel
    assert 'h("span", { class: "index-progress-text" })' in panel
    assert "pull requests fetched" in panel
    # Rows already shown are never covered by progress ("Refreshing Content"): the spinner and
    # "Fetching pull requests…" are only for a list with no rows. While rows are held, the
    # connection row keeps its age, muted and breathing, and a row whose data GitHub is read
    # for breathes its title, which is primary ink. Only the status text is marked busy: a row
    # and a tree group stay usable links, so the breathing there is paint alone.
    assert 'const connectionMessage = h("span", { class: "mb-refreshing-muted" });' in panel
    assert 'connectionMessage.classList.toggle("mb-refreshing", refreshing);' in panel
    assert 'connectionText.setAttribute("aria-busy", "true");' in panel
    assert "} else if ((working || page.more) && !holding) {" in panel
    assert 'entry.title.classList.toggle("mb-refreshing", on);' in panel
    assert 'entry.row.setAttribute("aria-busy"' not in panel, "a usable row is never busy"
    files = (REPO_ROOT / BUILTIN_PLUGINS / "github/pull-files-view.js").read_text(encoding="utf-8")
    assert 'class: "changed-file-name github-pull-file-name mb-refreshing-text"' in files
    assert 'group.classList.toggle("mb-refreshing-group", next.refreshing);' in files
    assert '"aria-busy"' not in files, "the usable tree group is never busy"
    assert "spinner.hidden = !next.loading;" in files
    # A file the comparison does not hold is muted ink, so its name breathes as a muted line.
    muted_name = github[
        ".github-pull-files.mb-refreshing-group .github-pull-file-muted > .github-pull-file-name"
    ]
    assert muted_name == {
        "--mb-refreshing-to": "var(--refreshing-muted-lift-opacity)",
        "color": "var(--text)",
        "opacity": "var(--refreshing-muted-rest-opacity)",
    }
    # A pull request's title is bold in normal text ink wherever it appears. A row and a
    # stack menu item are links, so the title sets both itself; in headless Chrome its
    # computed weight is 700 in the text ink for a normal, visited, hovered, focused and
    # selected row, and for a stack member at rest, hovered and current.
    assert "A pull request’s title is always bold in normal text ink" in doc
    # A Pulls row, the stack menu, a stack's page, and a guide's pull request row draw a pull
    # request's fields with one builder (stack-member-row.js), its title through the SDK's
    # titleNodes.
    assert "stackMemberRow(heading, mb.titleNodes, rowAuthor, PULLS_RUN)" in panel
    assert "stackMemberRow(link, deps.titleNodes, deps.identity)" in page
    titles = (".github-pulls-title", ".github-pull-stack-member-title")
    for title in titles:
        assert github[title]["color"] == "var(--text)", title
        assert github[title]["font-weight"] == "var(--weight-bold)", title
    for selector, declarations in _rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"):
        if selector not in titles and any(title in selector for title in titles):
            assert not {"color", "font-weight"} & declarations.keys(), selector
    # The page's heading and a search result's label already are.
    assert 'class: "page-heading github-pull-title' in page
    shell = dict(_rules_of(STATIC / "styles.css"))
    assert shell[".page-heading"]["font-weight"] == "var(--weight-bold)"
    label = shell[".search-palette-label"]
    assert (label["color"], label["font-weight"]) == ("var(--text)", "var(--weight-bold)")
    # A pull request's number is bold wherever it names the pull request, the weight of a
    # stack's position, through one token (mb-vrvs): one rule in the GitHub plugin for the
    # title's, a Pulls row's, and a stack menu member's (mb-1kzu), and the shell's Quick
    # Search result and ref selector; no other rule sets a number's weight. In headless
    # Chrome each computes to 700 (github-pulls-stacks-chrome.mjs,
    # github-pull-header-chrome.mjs).
    assert "### Pull Request Numbers" in doc
    shell_css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert shell_css.count("--pull-number-weight:") == 1
    assert "--pull-number-weight: var(--weight-bold);" in shell_css
    numbers = (".github-pull-number", ".github-pulls-number", ".github-pull-stack-member-number")
    weighted = [
        (selector, declarations["font-weight"])
        for selector, declarations in _rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css")
        if "font-weight" in declarations and any(number in selector for number in numbers)
    ]
    assert weighted == [(number, "var(--pull-number-weight)") for number in numbers], weighted
    for number in (".search-palette-pull-number", ".source-ref-selector-pull-number"):
        assert shell[number]["font-weight"] == "var(--pull-number-weight)", number


# A count's numeral and a pull request's number are both bold, each through a token of its
# own, so the two may part (docs/design-system.md, "Count Summaries Bold Their Numbers" and
# "Pull Request Numbers"): the selectors that take each. A status count, "21 A", takes the
# count's weight for its number and its letter alike (mb-8iwn).
_COUNT_NUMERALS = frozenset({".summary-number", ".heading-tally-figure", ".summary-status-count"})
_PULL_NUMBERS = frozenset(
    {
        ".github-pull-number",
        ".github-pulls-number",
        ".github-pull-stack-position",
        ".github-pull-stack-member-position",
        ".github-pull-stack-member-number",
        ".github-pull-guide-reference-pull",
        ".search-palette-pull-number",
        ".source-ref-selector-pull-number",
    }
)
# A class a source gives a count summary's number beside `.summary-number`.
_SUMMARY_NUMBER_CLASSES = re.compile(
    r"""class(?:Name)?\s*[:=]\s*["']([^"']*\bsummary-number\b[^"']*)["']"""
)


def _token_uses(token: str) -> set[tuple[str, str]]:
    """(selector, property) for every declaration in every stylesheet that reads *token*."""

    return {
        (selector, name)
        for sheet in _stylesheets()
        for selector, declarations in _rules_of(sheet)
        for name, value in declarations.items()
        if f"var({token})" in value
    }


def test_count_summaries_bold_their_numbers_through_one_token() -> None:
    """A count summary's numbers are bold, its words regular ("Count Summaries Bold Their
    Numbers"; mb-roa9).

    One token, `--count-numeral-weight`, sets a count's numeral's weight: every count
    numeral's rule reads it, and nothing else does; `--pull-number-weight` is read by the
    pull request numbers' rules alone. One shell class, `.summary-number`, takes the token
    and nothing else, so a number keeps its line's ink and size, and no stylesheet restyles
    it, by its own class or by a class a source gives it beside that one. Each surface that
    paints a count summary puts its counts in it: the browserless sessions named in the
    design system hold the markup, and tests/test_changed_file_rows_chrome.py and
    tests/test_nav_metadata_chrome.py read 700 for the numbers and 400 for the words in
    Chrome.
    """

    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "### Count Summaries Bold Their Numbers" in doc
    shell_css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert shell_css.count("--count-numeral-weight:") == 1
    assert "--count-numeral-weight: var(--weight-bold);" in shell_css
    assert _token_uses("--count-numeral-weight") == {
        (numeral, "font-weight") for numeral in _COUNT_NUMERALS
    }
    assert _token_uses("--pull-number-weight") == {
        (number, "font-weight") for number in _PULL_NUMBERS
    }
    shell = dict(_rules_of(STATIC / "styles.css"))
    assert shell[".summary-number"] == {"font-weight": "var(--count-numeral-weight)"}
    beside = {
        f".{name}"
        for source in _browser_sources()
        for found in _SUMMARY_NUMBER_CLASSES.finditer(source.read_text(encoding="utf-8"))
        for name in found.group(1).split()
        if name != "summary-number"
    }
    assert not beside, beside
    for sheet in _stylesheets():
        for selector, declarations in _rules_of(sheet):
            assert selector == ".summary-number" or "summary-number" not in selector, (
                sheet,
                selector,
            )
            # The Checks summary's numbers are spans in a quiet paragraph; nothing styles a
            # paragraph's descendants' weight there.
            if re.search(r"\.github-pull-quiet(?![\w-])\s*[\s>+~]\s*\S", selector):
                assert "font-weight" not in declarations, (sheet, selector)
    painters = {
        "static/formatters.js": "{ className: part.sizeStyle ?? SUMMARY_NUMBER_CLASS, text: part.number",
        "static/navigation.js": "window.MetabrowserFormatters.countPartsHtml(parts)",
        "static/app.js": "window.MetabrowserFormatters.countPartsNodes(document, parts)",
        "static/git-panel.js": "window.MetabrowserFormatters.countPartsNodes(document, [",
        "builtin_plugins/diff/diff-view.js": "words.append(...paint(parts));",
        "builtin_plugins/github/pulls-panel.js": "mb.countPartsNodes(summary.total)",
        "builtin_plugins/github/pull-page.js": "mb.countPartsNodes(counted)",
    }
    for path, painted in painters.items():
        source = (REPO_ROOT / "src/metabrowser" / path).read_text(encoding="utf-8")
        assert painted in source, path
    formatters = (STATIC / "formatters.js").read_text(encoding="utf-8")
    assert 'const SUMMARY_NUMBER_CLASS = "summary-number";' in formatters


# A count summary's one painter, and how each surface reaches it: the shell through
# formatters.js, a plugin through the SDK's `countPartsNodes` (A3 of review A on #479).
_PUNCTUATION_PAINTERS = {
    "static/formatters.js": (
        'const SUMMARY_PUNCTUATION_CLASS = "summary-punctuation";',
        'const SUMMARY_STATUS_COUNT_CLASS = "summary-status-count";',
        'const FILE_CHANGE_STATUS_CLASS = "file-change-status";',
        "className: `${SUMMARY_STATUS_COUNT_CLASS} ${FILE_CHANGE_STATUS_CLASS}`,",
        "children: [{ className: SUMMARY_NUMBER_CLASS, text: part.count }, ` ${part.letter}`],",
        'const VISUALLY_HIDDEN_CLASS = "visually-hidden";',
        'attributes: [["aria-hidden", "true"]],',
        '...(at === 0 ? [] : [{ punctuation: "," }, " "]),',
        "{ status: entry.status, letter: entry.letter, count: written(entry.count) },",
        'const CHANGE_LINE_CLASS = "change-line";',
        'const CHANGE_LINE_NONE_CLASS = "change-line-none";',
        "{ statuses: entries, additions: totals.additions, deletions: totals.deletions },",
    ),
    "static/plugin-sdk.js": (
        "return global.MetabrowserFormatters.countPartsNodes(global.document, parts);",
        "countPartsNodes: countPartsNodes,",
        "return global.MetabrowserFormatters.changeLineNodes(global.document, line, options);",
        "changeLine: changeLine,",
        "changeLineNodes: changeLineNodes,",
    ),
    # The size line is a view helper, drawn only by a commit's or a pull request's page
    # and a commit's hover card, so it is not in a startup script ("Change Size Line").
    "static/plugin-sdk-views.js": (
        "element.append(...mb.countPartsNodes(counts));",
        "sized.append(...mb.countPartsNodes(size));",
        "const paint = global.MetabrowserFormatters.countPartsHtml;",
        "changeSizeLineNodes,",
    ),
    "static/changed-files-tree.js": (
        "return formatters().changeSummary(totals, statusBreakdown(statuses), formatCount);",
        'letter: STATUS_BADGES[/** @type {keyof typeof STATUS_BADGES} */ (status)] ?? "?",',
    ),
    "static/git-panel.js": (
        "const said = formatters.changeSummary(",
        "formatters.changeLineHtml(said.line)",
        # The size line, the SDK's one component for it ("Change Size Line").
        "return mb.changeSizeLineHtml(",
    ),
    "builtin_plugins/diff/diff-view.js": (
        'const SUMMARY_SEPARATOR = Object.freeze({ separator: "·" });',
        'const LINE_SEPARATOR = Object.freeze({ separator: "·", spoken: ", " });',
        "const countPartsNodes = api?.countPartsNodes;",
        '...paint.changeLineNodes(said.line, named ? {} : { spoken: ", " }),',
        '...paint.changeLineNodes(paint.changeLine(said.change), { spoken: ", " }),',
    ),
    "builtin_plugins/github/pull-page.js": (
        'const CHECKS_SEPARATOR = Object.freeze({ separator: "·", spoken: ", " });',
        'h("p", { class: "github-pull-quiet" }, mb.countPartsNodes(counted))',
    ),
    # A stack's heading in the Pulls tab draws its change line through the SDK (mb-9ekj).
    "builtin_plugins/github/pulls-panel.js": (
        '...mb.countPartsNodes([{ separator: "·" }]),',
        "...mb.changeLineNodes(said),",
    ),
}
# A class only the one painter writes: no other source spells one as a class of its own.
_PAINTED_CLASSES = re.compile(
    r"""["'](summary-number|summary-punctuation|summary-status-count|file-change-status|change-line(?:-[a-z]+)?)["']"""
)


def test_count_summaries_mute_their_punctuation_and_ink_their_status_counts() -> None:
    """A count summary's separators and list punctuation are muted, and a status count, "21 A",
    is bold in its status's ink, number and letter alike ("Count Summaries Bold Their
    Numbers"; mb-vb51, mb-8iwn).

    One shell class, `.summary-punctuation`, sets the muted ink and nothing else, and no
    stylesheet restyles it. A status count in a count summary is one span, the shell's
    `.summary-status-count`, which sets the count's weight and nothing else, and the
    shell's status primitive, `.file-change-status`, whose inks
    `test_file_status_ink_is_shared_and_legible` holds; no stylesheet restyles the status
    count, so its number and letter take one ink. What a change set's summary says is one
    function, `changeSummary`, which the Diff summary's model and a commit's hover card both
    say it through, and its parts have one painter, formatters.js's, which a plugin reaches
    through the SDK's `countPartsNodes`: the Diff summary and the Checks summary paint none
    of those classes themselves.
    tests/dom/count-parts-session.js pins each kind's markup, tests/dom/diff-view-behavior.js
    the Diff summary's header and fallback line, tests/dom/git-panel-behavior.js the hover
    card, and tests/test_changed_file_rows_chrome.py and tests/dom/git-commit-summary-chrome.mjs
    read their inks, weights, and contrast in Chrome.
    """

    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "`.summary-punctuation`" in doc
    assert "test_count_summaries_mute_their_punctuation_and_ink_their_status_counts" in doc
    shell = dict(_rules_of(STATIC / "styles.css"))
    assert shell[".summary-punctuation"] == {"color": "var(--muted)"}
    assert shell[".summary-status-count"] == {"font-weight": "var(--count-numeral-weight)"}
    for sheet in _stylesheets():
        for selector, _ in _rules_of(sheet):
            assert selector == ".summary-punctuation" or "summary-punctuation" not in selector, (
                sheet,
                selector,
            )
            assert selector == ".summary-status-count" or "summary-status-count" not in selector, (
                sheet,
                selector,
            )
    for path, painted in _PUNCTUATION_PAINTERS.items():
        source = (REPO_ROOT / "src/metabrowser" / path).read_text(encoding="utf-8")
        for text in painted:
            assert text in source, (path, text)
    for path in (
        "builtin_plugins/diff/diff-view.js",
        "builtin_plugins/github/pull-page.js",
        "builtin_plugins/github/pulls-panel.js",
        "builtin_plugins/github/stack-lines.js",
        "builtin_plugins/github/row-lines.js",
        "builtin_plugins/github/change-lines.js",
    ):
        source = (REPO_ROOT / "src/metabrowser" / path).read_text(encoding="utf-8")
        assert _PAINTED_CLASSES.findall(source) == [], path
    # The Diff summary's breakdown is in its line's ink: only its marks, and the
    # "(estimated)" note that qualifies its totals, are muted. Each dot is one item with the
    # group before it, spaced by the line's one gap, on a toggle and on a line alike.
    diff_css = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "diff/styles.css"))
    assert ".metabrowser-diff-host .diff-summary-breakdown" not in diff_css
    assert diff_css[".metabrowser-diff-host .diff-summary-note"] == {"color": "var(--muted)"}
    assert diff_css[".metabrowser-diff-host .diff-summary-group"] == {
        "display": "inline-flex",
        "align-items": "baseline",
        "column-gap": "inherit",
    }
    assert diff_css[".metabrowser-diff-host .diff-summary"]["column-gap"] == "6px"
    assert "column-gap" not in diff_css[".metabrowser-diff-host .diff-summary-toggle"]
    # The hover card's change line is spaced as the Diff summary's is.
    assert shell[".git-commit-change-group"] == {
        "display": "inline-flex",
        "align-items": "baseline",
        "column-gap": "inherit",
    }
    assert shell[".git-commit-change-line"]["column-gap"] == "6px"
    # The brief change line is one shell component, spaced as the Diff summary is, its
    # statuses and their dot one item (mb-9ekj).
    assert shell[".change-line"] == {
        "display": "inline-flex",
        "flex-wrap": "wrap",
        "align-items": "baseline",
        "column-gap": "6px",
    }
    assert shell[".change-line-group"] == {
        "display": "inline-flex",
        "align-items": "baseline",
        "column-gap": "inherit",
    }
    # A line leaves out a total of zero and says "0 lines" for a change of none, muted at
    # its line's weight, wherever it stands (mb-efum, mb-ox6a).
    assert shell[".change-line-stats > .change-line-none"] == {"color": "var(--muted)"}


def test_merges_read_source_to_target_in_one_notation() -> None:
    """Every merge reads source → target, through `mergeRefs` ("Merge Direction")."""

    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "### Merge Direction" in doc
    assert "test_merges_read_source_to_target_in_one_notation" in doc
    # One writer: the arrow, its accessible name, and the left-to-right island are the SDK's.
    views = (STATIC / "plugin-sdk-views.js").read_text(encoding="utf-8")
    assert 'const MERGE_ARROW_NAME = "merges into";' in views
    assert 'arrow.setAttribute("role", "img");' in views
    assert 'arrow.setAttribute("aria-label", MERGE_ARROW_NAME);' in views
    assert 'arrow.textContent = " → ";' in views
    assert 'group.setAttribute("dir", "ltr");' in views
    assert re.search(
        r"group\.append\(\s*chip\(source, \"merge-refs-source\"\),\s*arrow,\s*"
        r"chip\(target, \"merge-refs-target\"\),?\s*\)",
        views,
    ), "the group is the source, the arrow, then the target"
    # The page draws its merge with it, head first, and draws no ref chip of its own, so it
    # cannot compose two around a connector, nor writes the left arrow; its session holds
    # the rendered order, the arrow, and the literal refs. A Pulls row names no branches.
    panel_source = (REPO_ROOT / BUILTIN_PLUGINS / "github" / "pulls-panel.js").read_text(
        encoding="utf-8"
    )
    assert "mergeRefs" not in panel_source, "a Pulls row names no branches"
    for name, side in (("pull-page.js", "pull"),):
        source = (REPO_ROOT / BUILTIN_PLUGINS / "github" / name).read_text(encoding="utf-8")
        assert re.search(
            rf"mb\.mergeRefs\(\s*\{{\s*name:\s*{side}\.headRef\b[^}}]*\}},\s*"
            rf"\{{\s*name:\s*{side}\.baseRef\b",
            source,
        ), f"{name} does not draw its merge head → base through mergeRefs"
        assert not re.search(r"\brefChip(?:Html)?\(", source), f"{name} draws a ref chip itself"
        assert "←" not in source, f"{name} writes a merge target ← source"
    # The arrow is a connector, in muted ink at the size of the sentence it sits in, which
    # the group inherits (each chip is its own one size); the names give way first,
    # and never past both chips' frames, an ellipsis in each, and the arrow.
    shell = dict(_rules_of(STATIC / "styles.css"))
    group = shell[".merge-refs"]
    assert group["display"] == "inline-grid"
    assert group["grid-template-columns"] == (
        "minmax(0, max-content) max-content minmax(0, max-content)"
    ), "each name may shrink and the arrow never shrinks"
    assert group["min-width"] == "calc(2 * var(--compact-chip-padding-inline) + 3em)", (
        "the merge's floor"
    )
    assert "font-size" not in group, "the arrow and chips take the text around the merge"
    assert ".merge-refs > .git-ref" not in shell, "a merge places its chips; it never sizes them"
    assert shell[".merge-refs-arrow"] == {"color": "var(--muted)", "white-space": "pre"}
    # A Pulls row names no branches (the pull request's page does) (mb-lkkt, mb-pw8t, mb-rb3n):
    # its run is the title, the place, the number, and the author, the number never breaking,
    # the author in the row's type and its name ending in an ellipsis only where it is wider
    # than a line; its last line is the lines, and the age at the row's end.
    github = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"))
    assert ".github-pulls-meta" not in github and ".github-pulls-line" not in github
    assert github[".github-pulls-number"]["white-space"] == "nowrap", "the number never breaks"
    assert ".github-pulls-byline" not in github, "the author is in the run"
    assert github[".github-pulls-row > .github-pulls-tail"]["height"] == (
        "var(--github-pulls-change-line)"
    )
    assert github[".github-pulls-tail > .github-pulls-age"]["justify-self"] == "end"
    # The author is the run's secondary metadata, at its size, which it inherits.
    assert "font-size" not in github[".github-pulls-by"]
    assert ".github-pulls-id" not in github, "the run names the number once"
    assert ".github-pulls-merge" not in github, "a Pulls row names no branches"
    assert github[".github-pulls-by"]["--actor-avatar-size"] == (
        "var(--github-pull-row-avatar-size)"
    ), "a list row's avatar"
    assert github[".github-pulls-by > .github-pull-identity"]["max-width"] == "100%"
    assert ".github-pulls-by:has(.actor-avatar)" not in github
    author = github[".github-pulls-by .github-pulls-author"]
    assert (author["min-width"], author["text-overflow"]) == ("0", "ellipsis")
    assert ".github-pulls-who" not in github
    # The header's details may be narrower than its merge, whose chips then ellipsize.
    assert github[".github-pull-meta-details"]["min-width"] == "0"


def test_the_pull_request_page_carries_the_shells_primitives() -> None:
    """What "The Pull Request Page" says it reuses is what its markup says."""

    page = (REPO_ROOT / BUILTIN_PLUGINS / "github/pull-page.js").read_text(encoding="utf-8")
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "## The Pull Request Page" in doc
    assert "test_the_pull_request_page_carries_the_shells_primitives" in doc
    # Branch names and file paths are chrome: no `<code>` for either.
    assert 'h("code"' not in page
    assert "mb.mergeRefs(" in page and 'kind: "remote"' in page
    # One exact time, in the age's tooltip, not a timestamp at each call site.
    assert page.count("mb.formatTimestamp(") == 1, "the exact time belongs in the age's tooltip"
    assert "`file-header-badge github-pull-badge github-pull-${kind}`" in page
    assert 'class: "notice github-pull-notice"' in page
    github = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"))
    # The heading scales the shared glyph to its own type and wraps text in its own track.
    assert 'class: "page-heading github-pull-title' in page
    assert (
        github[".github-pull-title-with-state"]["grid-template-columns"]
        == "auto minmax(0, 1fr) auto"
    ), "the number is a track of its own, after the title it is never clamped with"
    title_icon = github[".github-pull-title > .github-pull-state-icon"]
    assert (title_icon["width"], title_icon["height"]) == ("1em", "1lh")
    title_glyph = github[".github-pull-title > .github-pull-state-icon svg"]
    assert (title_glyph["width"], title_glyph["height"]) == ("1em", "1em")
    # Links take the link token rather than the browser's blue, all but the corner's View on
    # GitHub button, which is a chip and takes a chip's ink (mb-4wqh).
    assert github[".github-pull-header a:not(:where(.view-header-end *))"]["color"] == (
        "var(--link)"
    )
    # A check's action on GitHub is quiet: muted at rest, the link token on hover and
    # focus, at its row's size. View on GitHub is the header corner's button, a chip
    # (mb-4wqh), and not one of them.
    action = ".github-pull-checks .github-pull-external-action"
    assert github[action] == {"color": "var(--muted)"}, action
    for state in (":hover", ":focus-visible"):
        assert github[action + state]["color"] == "var(--link)", action + state
    assert page.count('"github-pull-external-action"') == 1, "a check's"
    # A conversation commit's hash links to it on GitHub and is a short commit ID, in the
    # commit-ID gray under the pointer too, which only underlines it (docs/design-system.md,
    # "Short Commit IDs"); tests/test_github_pull_timeline_chrome.py measures it.
    assert '"github-pull-commit-id git-commit-sha"' in page
    assert not any(
        "color" in declarations
        for selector, declarations in _rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css")
        if ".github-pull-commit-id" in selector
        or ".github-pull-commit .github-pull-external-action" in selector
    )
    assert github[".github-pull-commit-id:hover"]["text-decoration"] == "underline"
    # A check's own site is an ordinary link, so it never reads as the description after it.
    assert github[".github-pull-checks a"]["color"] == "var(--link)"
    # A conversation commit is said in a card head's type ("Conversation Timeline"): its
    # when is no quieter than a comment's, its age is the head's, and its hash is the size
    # of the text beside it, as a short commit ID is everywhere. The sizes and the line they
    # draw are measured in Chrome by tests/test_github_pull_timeline_chrome.py.
    commit = github[".github-pull-commit"]
    assert commit["font-size"] == github[".github-pull-card-head"]["font-size"]
    # Its box is its line, so its text is the rhythm from the events beside it (mb-w7rt).
    assert "min-height" not in commit and commit["padding"].startswith("0 ")
    # The rhythm is the Conversation's, and only its events carry it: the body keeps the
    # page's gap, as the Files and Checks tabs and a section or note below an event do, and
    # each event stands the rest of the rhythm below whatever is before it.
    assert github[".github-pull-body"]["gap"] == "var(--github-pull-gap)"
    assert github[".github-pull-body > * + .github-pull-event"] == {
        "margin-block-start": "calc(var(--github-pull-rhythm) - var(--github-pull-gap))"
    }
    # Under Review comments the rhythm is between its cards only: its heading sits at the
    # section's gap over the first, as every section's heading does (mb-xlla).
    assert ".github-pull-threads" not in github
    assert github[".github-pull-threads > .github-pull-card + .github-pull-card"] == {
        "margin-block-start": "calc(var(--github-pull-rhythm) - var(--github-pull-gap))"
    }
    assert ".github-pull-commit .git-commit-sha" not in github
    assert (
        github[".github-pull-commit .github-pull-age"]
        == (github[".github-pull-card-head .github-pull-age"])
    )
    # The row's when is a plain span in the row's type; the Chrome test holds its ink.
    assert 'h("span", {}, ["committed ", age(event.committed_at)])' in page
    # The events the line joins: the description, each comment and review, and each commit.
    assert page.count("github-pull-event") == 3, "the description, a card, and a commit"
    # Every author there is the shell's identity, whose avatar's box is there for an author
    # without one, the person glyph in it (mb-nunw); only a Pulls row, a stack menu member, and
    # a guide's pull request row (mb-x0z1) ask for none.
    assert page.count("authorLabel(mb, ") == 6, (
        "the header, the description, a card, a reply, a member, a guide's pull request row"
    )
    # Biome sets the guide's on lines of their own, so its braces are read past white space.
    assert len(re.findall(r"\{\s*placeholder: false,?\s*\}", page)) == 2, (
        "a stack menu member and a guide's pull request row"
    )
    assert "{ slot: true }" not in page and "github-pull-avatar-slot" not in github
    shell = dict(_rules_of(STATIC / "styles.css"))
    avatar = shell[".actor-avatar"]
    assert (avatar["width"], avatar["height"]) == ("var(--actor-avatar-size)",) * 2
    node = github[".github-pull-commit::after"]
    assert (node["border-radius"], node["background"]) == ("var(--radius-circle)", "var(--muted)")
    # A button that moves the pin looks as a link does: no primitive's border or fill.
    action = github[".github-pull-text-action"]
    assert (action["color"], action["border"], action["background"]) == (
        "var(--link)",
        "0",
        "transparent",
    )
    assert "github-pull-browse" not in page and '"Browse code"' in page
    assert page.count('class: "github-pull-text-action"') == 1
    assert '"github-pull-file github-pull-text-action"' in page
    # The status line's remedy, Retry or Fetch, is a text action too (mb-ablv): the line is
    # one of the header's metadata lines, and a bordered .btn made it 26 px where the row of
    # ages above it is 18 (mb-2u08). A switch to the head was one, until the server followed
    # the head itself (mb-6a6w). The page has no Refresh of its own.
    assert '"github-pull-text-action github-pull-remedy"' in page
    assert "github-pull-refresh" not in page
    assert "github-pull-switch" not in page
    # A <button> is an atomic inline box whatever its display, so the link and the plain
    # path are one too: a wrapped path then puts the badge after it on the next line in every
    # form, where the link alone let it follow the text. Measured in Chrome on a 685 px card
    # head: before, the link's head was 45 px and the button's 63 px; after, both 63 px.
    assert github[".github-pull-file"]["display"] == "inline-block"
    # Content already shown is never covered by progress ("Refreshing Content"): no spinner in
    # the header, a section, or the description card. The age line is one persistent element,
    # muted, that breathes while a refresh runs or is due, on a status line marked busy; a
    # section a description preview lacks shows the cold page's blocks after the quiet period.
    assert "github-pull-progress" not in page and "github-pull-progress" not in str(github)
    assert "github-pull-timeline-loading" not in page
    assert 'class: "spinner spinner-sm"' not in page
    spinners = page.count('h("span", { class: "spinner", "aria-hidden": "true" })')
    assert spinners == 2, "only the diff host and Changes with nothing cached spin"
    assert '"loading mb-delayed-loading github-pull-diff-loading"' in page
    assert '"loading mb-delayed-loading github-pull-changes-pending"' in page
    assert 'h("span", { class: "github-pull-freshness mb-refreshing-muted" })' in page
    assert 'meta.line.classList.toggle("mb-refreshing", busy);' in page
    assert 'meta.line.setAttribute("aria-busy", "true");' in page
    assert 'status.setAttribute("aria-busy"' not in page, "the status line's controls stay usable"
    assert '"recent-loading github-pull-loading github-pull-section-loading"' in page
    assert github[".github-pull-section-loading"] == {"height": "calc(var(--ui-row-height) * 3)"}
    # The author, action, and relative age share one prose size and baseline.
    assert github[".github-pull-card-head"]["font-size"] == "var(--body-font-size)"
    age = github[".github-pull-card-head .github-pull-age"]
    assert age == {"line-height": "inherit"}, "an age takes its line's size from the primitive"
    assert ".github-pull-card-head .github-pull-author" not in github
    identity = shell[".actor-identity"]
    assert (identity["align-items"], identity["vertical-align"]) == ("baseline", "baseline")
    assert shell[".actor-avatar"]["align-self"] == "center"
    # A hunk is the user's code, at the chrome-context mono size, in the app's mono face.
    assert github[".github-pull-hunk"]["font-family"] == "var(--font-mono)"
    assert github[".github-pull-hunk"]["font-size"] == "var(--mono-block-font-size)"


def test_no_pull_request_surface_says_it_may_be_out_of_date() -> None:
    """Stale data that can be refreshed is being refreshed ("Refreshing Content").

    A pull request's page, the Pulls tab, and a changed-files tree once said "may be out of
    date" beside data they were about to refresh, or never would. They show the plain age
    while a refresh runs, and name a problem only when no refresh can run.
    """

    plugin = REPO_ROOT / BUILTIN_PLUGINS / "github"
    sources = sorted(path for suffix in ("*.js", "*.css", "*.py") for path in plugin.glob(suffix))
    assert sources
    for source in sources:
        assert "may be out of date" not in source.read_text(encoding="utf-8").lower(), source.name


def _srgb(value: str) -> tuple[float, float, float]:
    """Gamma-encoded sRGB channels of an `oklch(L% C H)` color, the space opacity blends in."""

    lightness, chroma, hue = _oklch_channels(value)
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    long = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    medium = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    short = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    linear = (
        4.0767416621 * long - 3.3077115913 * medium + 0.2309699292 * short,
        -1.2684380046 * long + 2.6097574011 * medium - 0.3413193965 * short,
        -0.0041960863 * long - 0.7034186147 * medium + 1.7076147010 * short,
    )
    encoded = [
        12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        for c in (min(max(channel, 0.0), 1.0) for channel in linear)
    ]
    return encoded[0], encoded[1], encoded[2]


def _blended_luminance(ink: str, ground: str, opacity: float) -> float:
    """WCAG relative luminance of *ink* at *opacity* over *ground*."""

    channels = [
        opacity * front + (1 - opacity) * back
        for front, back in zip(_srgb(ink), _srgb(ground), strict=True)
    ]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _ratio(first: float, second: float) -> float:
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def test_refreshing_text_breathes_on_the_compositor_and_keeps_its_contrast() -> None:
    """The one refresh animation ("Refreshing Content"): opacity only, quiet first, and legible.

    Breathing changes opacity alone, so the compositor runs it with no style or paint work per
    frame (measured in headless Chrome beside the tokens). It starts after the loading quiet
    period and stops under reduced motion. Primary ink keeps 4.5:1 at its dimmest in both
    themes; muted ink cannot dim and keep it, so a muted line is drawn in primary ink at the
    opacity that reproduces muted, within 0.1:1, and lifts toward full ink instead.
    """

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    shell = _rules_of(STATIC / "styles.css")
    rules = dict(shell)
    # Each form is declared twice: the breath, and its reduced-motion override.
    for form in (".mb-refreshing", ".mb-refreshing-group .mb-refreshing-text"):
        declared = [body for selector, body in shell if selector == form]
        assert len(declared) == 2, form
        assert declared[1] == {"animation": "none"}, f"reduced motion stops {form}"
    breathe = next(body for selector, body in shell if selector == ".mb-refreshing")
    assert " ".join(breathe["animation"].split()) == (
        "mb-refreshing-text var(--refreshing-text-period) ease-in-out"
        " var(--loading-state-delay) infinite"
    ), "one period, eased, after the quiet period, looping while the refresh runs"
    keyframes = re.search(r"@keyframes mb-refreshing-text \{(.*?)\n\}", styles, re.DOTALL)
    assert keyframes is not None
    assert set(re.findall(r"([a-z-]+):", keyframes[1])) == {"opacity"}, "opacity only"
    muted = rules[".mb-refreshing.mb-refreshing-muted"]
    assert muted["color"] == "var(--text)"
    assert muted["opacity"] == "var(--refreshing-muted-rest-opacity)"
    assert "prefers-reduced-motion: reduce) {\n  /* The text stays as it is at rest" in styles
    light_block, dark_block = _theme_blocks()
    dim = float(_declared(light_block, "--refreshing-text-dim-opacity"))
    for theme, block in (("light", light_block), ("dark", dark_block)):
        ground = _declared(block, "--bg")
        text = _declared(block, "--text")
        muted_ink = _declared(block, "--muted")
        surface = _relative_luminance(*_oklch_channels(ground))
        dimmed = _ratio(_blended_luminance(text, ground, dim), surface)
        assert dimmed >= 4.5, f"primary ink dims to {dimmed:.2f}:1 in the {theme} theme"
        rest = float(_declared(block, "--refreshing-muted-rest-opacity"))
        lift = float(_declared(block, "--refreshing-muted-lift-opacity"))
        resting = _ratio(_blended_luminance(text, ground, rest), surface)
        assert abs(resting - _contrast(muted_ink, ground)) <= 0.1, (
            f"a muted line at rest reads {resting:.2f}:1, not muted's, in the {theme} theme"
        )
        assert rest < lift <= 1, "a muted line lifts toward primary ink, never below its rest"


def _oklab(value: str) -> tuple[float, float, float]:
    lightness, chroma, hue = _oklch_channels(value)
    return (
        lightness,
        chroma * math.cos(math.radians(hue)),
        chroma * math.sin(math.radians(hue)),
    )


def _oklab_luminance(lightness: float, a: float, b: float) -> float:
    """WCAG relative luminance of an OKLab color, clipped to sRGB as a browser paints it."""

    chroma = math.hypot(a, b)
    hue = math.degrees(math.atan2(b, a)) % 360
    return _relative_luminance(lightness, chroma, hue)


def test_a_hovered_legend_entrys_ink_reads_for_every_family() -> None:
    """A hovered family's legend name keeps 4.5:1 for every registered family, on both pages.

    While the hover marks a File Overview legend entry, its name is drawn in its family's
    ink: the family's color mixed in OKLab with `--text`, `--mb-distribution-ink-share` of it
    the family's ("Aggregate Distributions"). A family's own color can read 2.3:1 on the
    light page, so the share is what makes the name text. Every family the registry declares
    is checked, at the color the server resolves for each theme, on `--bg`, which the legend
    sits on. tests/test_overview_legend_hover_chrome.py reads one family's ink as Chrome
    computes it.
    """

    from metabrowser.file_type_filters import serialize_distribution_colors

    rules = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "folder/file_type_summary.css"))
    label = ".file-type-summary-legend-item[data-hovered] .file-type-summary-legend-label"
    assert " ".join(rules[label]["color"].split()) == (
        "color-mix( in oklab, var(--mb-distribution-color) var(--mb-distribution-ink-share),"
        " var(--text) )"
    )
    light_block, dark_block = _theme_blocks()
    share = float(_declared(light_block, "--mb-distribution-ink-share").removesuffix("%")) / 100
    colors = serialize_distribution_colors()
    assert colors
    for theme, block in (("light", light_block), ("dark", dark_block)):
        text = _oklab(_declared(block, "--text"))
        ground = _relative_luminance(*_oklch_channels(_declared(block, "--bg")))
        for family in colors:
            mixed = [
                share * own + (1 - share) * ink
                for own, ink in zip(_oklab(family[theme]), text, strict=True)
            ]
            ratio = _ratio(_oklab_luminance(*mixed), ground)
            assert ratio >= 4.5, f"{family['key']} reads {ratio:.2f}:1 on the {theme} page"


# How many times the separation floor Other's neutral must be from every family's color. The
# legend names up to nine families and Other (file_type_legend.py), and the family colors are
# held a floor apart from each other (devtools/check_file_type_colors.py), which nothing held
# for Other, drawn in --muted. Measured 2026-11-20, 56 families: 0.1111 in the light theme and
# 0.1074 in the dark, 7.4 and 7.2 times the floor, the nearest to Other plain text and asciidoc.
OTHER_CLEARANCE_FLOORS = 5


def test_other_is_clear_of_every_family_in_both_themes() -> None:
    """The legend's Other, drawn in `--muted`, is never taken for a family it sits beside.

    Every family's color is `MINIMUM_HOUSE_DELTA_E` or more from every other's in both themes,
    held by `devtools/check_file_type_colors.py`. Other is none of them and takes the page's
    muted ink (`--mb-distribution-other`), so this holds it the same distance in Oklab,
    several times over, from each family, as the server resolves them for each theme.
    """

    from devtools.check_file_type_colors import MINIMUM_HOUSE_DELTA_E
    from metabrowser.file_type_filters import serialize_distribution_colors

    light_block, dark_block = _theme_blocks()
    assert _declared(light_block, "--mb-distribution-other") == "var(--muted)"
    colors = serialize_distribution_colors()
    assert len(colors) > 9
    for theme, block in (("light", light_block), ("dark", dark_block)):
        other = _oklab(_declared(block, "--muted"))
        for family in colors:
            distance = math.dist(other, _oklab(family[theme]))
            assert distance >= OTHER_CLEARANCE_FLOORS * MINIMUM_HOUSE_DELTA_E, (
                f"{family['key']} is {distance:.4f} from Other on the {theme} page"
            )


def test_only_the_group_by_wait_dims_shown_content_and_never_twice() -> None:
    """The one wait that dims what is shown has its own token, and dims nothing twice.

    "Refreshing Content" says content already shown is never covered by progress, and names
    the one exception: a Group by choice's first sections, where the tree on screen is the
    arrangement the reader left ("Grouping the Files Tree", Waiting). It dims through
    `--loading-dim-opacity`, used nowhere else, and every tree row the dimmed content
    token already dims is held at that token under the wait rather than multiplied by it.
    tests/test_files_tab_chrome.py measures both in Chrome (mb-xlla).
    """

    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "`--loading-dim-opacity`" in doc
    sheets = [STATIC / "styles.css", *(REPO_ROOT / BUILTIN_PLUGINS).glob("*/*.css")]
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    uses = sum(
        sheet.read_text(encoding="utf-8").count("var(--loading-dim-opacity)") for sheet in sheets
    )
    assert uses == 2, "the dim's keyframe and the hold's are its only uses"
    dim = re.search(r"@keyframes tree-regrouping-dim \{(.*?)\n\}", styles, re.DOTALL)
    hold = re.search(r"@keyframes tree-regrouping-hold \{(.*?)\n\}", styles, re.DOTALL)
    assert dim is not None and "opacity: var(--loading-dim-opacity);" in dim[1]
    assert hold is not None and (
        "opacity: min(1, calc(var(--dimmed-content-opacity) / var(--loading-dim-opacity)));"
        in hold[1]
    )
    rules = _rules_of(STATIC / "styles.css")
    held = next(
        selector
        for selector, body in rules
        if body.get("animation", "").startswith("tree-regrouping-hold ")
    )
    assert held.startswith("#tab-files.tree-regrouping :is(") and held.endswith(")"), held
    holds = {
        name.strip()
        for name in held.removeprefix("#tab-files.tree-regrouping :is(")[:-1].split(",")
    }
    dimmed = {
        selector.removeprefix(".tree-item")
        for selector, body in rules
        if body.get("opacity") == "var(--dimmed-content-opacity)"
        and selector.startswith(".tree-item.")
    }
    assert dimmed and dimmed == holds, (dimmed, holds)


def test_tabular_figures_are_the_token_everywhere() -> None:
    """Every stylesheet sets tabular figures through `--tabular-numerals`, never the literal.

    The token is one place to change how figures align; a literal beside it is a second.
    """

    sheets = [STATIC / "styles.css", *(REPO_ROOT / BUILTIN_PLUGINS).glob("*/*.css")]
    for sheet in sheets:
        for selector, body in _rules_of(sheet):
            assert body.get("font-variant-numeric") != "tabular-nums", (sheet.name, selector)


def test_no_badge_rule_names_a_review_state_that_has_no_badge() -> None:
    """A review state whose verb says it all draws no chip, so no rule can style one.

    `REVIEW_STATES` in pull-page.js maps a plain review (COMMENTED) and a pending one to null
    (docs/design-system.md, "Conversation Timeline", Headings); a `.github-pull-badge` rule
    for either could never match and reads as a chip that exists.
    """

    page = (REPO_ROOT / BUILTIN_PLUGINS / "github/pull-page.js").read_text(encoding="utf-8")
    states = re.search(r"const REVIEW_STATES = Object\.freeze\(\{(.*?)\}\);", page, re.DOTALL)
    assert states is not None
    unbadged = re.findall(r"^\s*([A-Z_]+): null,", states[1], re.MULTILINE)
    assert set(unbadged) == {"COMMENTED", "PENDING"}, unbadged
    github = (REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css").read_text(encoding="utf-8")
    for state in unbadged:
        assert f'.github-pull-badge[data-state="{state}"]' not in github, state


def test_both_trees_of_changed_files_use_the_shells_rows() -> None:
    """The Pulls tab's changed files and the Diff summary draw the shell's one row set.

    The class set is `static/styles.css`'s `.changed-file-row` and its parts, beside the
    Files tree's rows; each plugin's stylesheet sets only its depth's indent, and no plugin
    restyles a row's box, hover, or ring, which is how the Diff summary's copy drifted to an
    8px inset and a rounded, outset ring (mb-xlla). `tests/test_changed_file_rows_chrome.py`
    measures the two trees row for row in Chrome.
    """

    shell = dict(_rules_of(STATIC / "styles.css"))
    row = shell[".changed-file-row"]
    assert row["padding"] == "2px 12px 2px calc(10px + var(--changed-file-indent, 0px))"
    assert row["border-left"] == "2px solid transparent"
    assert row["height"] == "var(--ui-row-height)"
    assert shell[".changed-file-row:hover"] == {"background": "var(--hover-bg)"}
    assert shell[".changed-file-row:focus-visible"]["outline-offset"] == "var(--focus-ring-offset)"
    assert shell[".changed-file-toggle"]["width"] == "var(--tree-icon-slot)"
    sources = ("diff/diff-summary.js", "github/pull-files-view.js")
    for source in sources:
        text = (REPO_ROOT / BUILTIN_PLUGINS / source).read_text(encoding="utf-8")
        for part in (
            "changed-file-row",
            "changed-file-toggle",
            "changed-file-name",
            "changed-file-stats",
        ):
            # A class string that holds the shared class as one of its names.
            assert re.search(rf'"(?:[\w-]+ )*{part}(?: [\w-]+)*"', text), (source, part)
    owned = {"--changed-file-indent", "scroll-margin-block-start", "color"}
    for sheet, classes in (
        ("diff/styles.css", ("diff-summary-row",)),
        ("github/styles.css", ("github-pull-file-row", "github-pull-folder-row")),
    ):
        for selector, body in _rules_of(REPO_ROOT / BUILTIN_PLUGINS / sheet):
            subject = selector.split()[-1]
            named = any(re.search(rf"\.{name}(?![\w-])", subject) for name in classes)
            if named and "::" not in subject:
                assert set(body) <= owned, (sheet, selector, body)
    # The Diff summary's header hovers and rings as its rows do: square, the ring inside. It
    # is the shell's summary toggle, which the stack page's members toggle is too, and no
    # plugin restates its box, hover, ring, or chevron slot (A5 of review A on #861). The
    # shell's own values are not repeated here: one rule holds them (B4 of review B).
    assert {".summary-toggle", ".summary-toggle:hover", ".summary-toggle-chevron"} <= set(shell)
    for sheet, source, classes in (
        ("diff/styles.css", "diff/diff-view.js", ("diff-summary-toggle", "diff-summary-chevron")),
        (
            "github/styles.css",
            "github/stack-page.js",
            ("github-pull-stack-members-toggle", "summary-toggle-chevron"),
        ),
    ):
        text = (REPO_ROOT / BUILTIN_PLUGINS / source).read_text(encoding="utf-8")
        assert re.search(r'"(?:[\w-]+ )*summary-toggle(?: [\w-]+)*"', text), source
        assert re.search(r'"(?:[\w-]+ )*summary-toggle-chevron(?: [\w-]+)*"', text), source
        for selector, body in _rules_of(REPO_ROOT / BUILTIN_PLUGINS / sheet):
            if any(re.search(rf"\.{name}(?![\w-])", selector) for name in classes):
                restated = {"padding", "margin", "border-radius", "outline", "cursor"} & set(body)
                assert not restated, (sheet, selector, restated)
    # A folder's tooltip gives what its sums leave out, the counts alone.
    for source in sources:
        text = (REPO_ROOT / BUILTIN_PLUGINS / source).read_text(encoding="utf-8")
        assert "element.dataset.tipText = missing;" in text, source
        assert "${row.name}, ${missing}" not in text, source


def test_tree_slots_and_avatar_geometry_derive_from_their_tokens() -> None:
    """A size two rules share is one token, and what is made of it is derived from it.

    The tree's icon slot is the glyph's width, `--tree-icon-slot: var(--icon-glyph)`, and the
    chevron centered in it is `--toggle-chevron-size`; a menu's, a palette's, and a file
    identity's icon box is `--icon-box`, and the tree's slot is that box's height. A person's
    avatar box and the gap after it are the shell's `--actor-avatar-size` and
    `--actor-identity-gap` (mb-nunw), and the Conversation timeline's commit row's start, the
    line's x, and the authors' floors are derived from them (mb-xlla).
    """

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "--tree-icon-slot: var(--icon-glyph);" in styles
    for token in ("--toggle-chevron-size", "--icon-box"):
        assert re.search(rf"^\s*{token}:", styles, re.MULTILINE), token
    shell = dict(_rules_of(STATIC / "styles.css"))
    chevron = shell[".toggle-chevron"]
    assert (chevron["width"], chevron["height"]) == ("var(--toggle-chevron-size)",) * 2
    centered = "calc((var(--tree-icon-slot) - var(--toggle-chevron-size)) / 2)"
    assert shell[".tree-folder > .tree-toggle"]["margin-inline"] == centered
    assert shell[".tree-container > .tree-toggle"]["margin"] == f"0 {centered}"
    for box in (".menu-item-icon", ".search-palette-icon", ".file-identity-icon"):
        assert (shell[box]["width"], shell[box]["height"]) == ("var(--icon-box)",) * 2, box
    # A tree row's slot is the glyph's width and the icon box's height.
    icon = shell[".tree-item-icon"]
    assert (icon["width"], icon["height"]) == ("var(--tree-icon-slot)", "var(--icon-box)")
    github = (REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css").read_text(encoding="utf-8")
    rules = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"))
    # A person's avatar box and the gap after it are the shell's, declared once on its root,
    # and every page that draws a person reads them: a commit's author and a pull request's
    # alike (mb-nunw). No plugin declares its own.
    root = _root_rule(STATIC / "styles.css")
    assert (root["--actor-avatar-size"], root["--actor-identity-gap"]) == ("18px", "4px")
    assert "--github-pull-avatar-size" not in github and "--github-pull-identity-gap" not in github
    assert (
        shell[".actor-avatar"]["width"]
        == shell[".actor-avatar"]["height"]
        == ("var(--actor-avatar-size)")
    )
    assert shell[".actor-identity"]["gap"] == "var(--actor-identity-gap)"
    assert rules[".github-pull-event"]["--github-pull-rail"] == (
        "calc(var(--github-pull-text-inset) + var(--actor-avatar-size) / 2)"
    )
    for selector in (
        ".github-pull-commit",
        ".github-pull-meta-details > .github-pull-identity",
    ):
        geometry = " ".join(
            rules[selector].get("padding", rules[selector].get("min-width", "")).split()
        )
        assert "var(--actor-avatar-size)" in geometry, selector
        assert "var(--actor-identity-gap)" in geometry, selector
    # No avatar size or gap is written as a pixel literal in a rule.
    assert "18px + 4px" not in github and "+ 9px" not in github


def test_boxed_prose_takes_one_inline_padding() -> None:
    """A bordered box that holds prose has one inline padding, `--boxed-prose-padding-inline`.

    The pane inset, `--pane-header-padding-x`, aligns the navigation column's rows, and put a
    description's h2 a few pixels inside its box's border (owner, 2026-11-20). The token is
    declared once, on the shell's `:root`; a pull request's cards read it through
    `--github-pull-text-inset`, which their head, text, hunk lines, and commit rows share, and
    a commit's message reads it directly. docs/design-system.md, "Boxed Prose", names what
    keeps its own padding and why. `tests/test_github_pull_text_chrome.py` measures the
    padding the boxes lay out.
    """

    shell_path = STATIC / "styles.css"
    github_path = REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"
    token = "--boxed-prose-padding-inline"
    shell_rules = _rules_of(shell_path)
    declared = [
        (selector, body[token])
        for selector, body in shell_rules + _rules_of(github_path)
        if token in body
    ]
    assert len(declared) == 1 and declared[0][0] == ":root", declared
    assert re.fullmatch(r"\d+px", declared[0][1]), "the token's value is a length of its own"
    github = dict(_rules_of(github_path))
    shell = dict(shell_rules)
    # A pull request's text is padded by the card's inset, which is the token and no pane inset.
    assert github[".github-pull"]["--github-pull-text-inset"] == f"var({token})"
    assert github[".github-pull-text"]["padding"] == (
        "var(--content-padding-y) var(--github-pull-text-inset)"
    )
    # A commit's message is the same kind of box, and reads the token itself.
    assert shell[".git-commit-body"]["padding"] == f"var(--pane-header-padding-y) var({token})"


# A serif face, named directly, as a family, or through the token KPress reads it from.
_SERIF = re.compile(
    r"--kpress-(?:host-)?font-prose\b|--app-serif-system\b|(?<!sans-)\bserif\b|\bgeorgia\b",
    re.IGNORECASE,
)
# A face token: KPress's resolved families and the hooks it reads them from.
_FACE_TOKEN = re.compile(r"--kpress-(?:host-)?font-")
# A rule on KPress's own elements, which would set a document's face around its hooks.
_KPRESS_CLASS = re.compile(r"\.kpress(?:-[\w-]+)?\b")
# The rules on <html> that hold the reading font and the font sets, and the face tokens
# each declares; every face rule outside them is refused.
_FACE_ROOTS = {
    ":root": {
        "--font-sans": "var(--app-sans-clean)",
        "--prose-sans-font": "var(--app-sans-clean)",
        "--kpress-host-font-mono": "var(--app-mono)",
        "--kpress-host-font-size-base": "var(--document-body-font-size)",
    },
    'html[data-app-font="system"]': {
        "--font-sans": "var(--app-sans-system)",
        "--prose-sans-font": "var(--app-sans-system)",
        "--kpress-host-font-sans": "var(--app-sans-system)",
        "--kpress-host-font-body": "var(--app-sans-system)",
        "--kpress-host-font-prose": "var(--app-serif-system)",
    },
    'html[data-prose-font="sans"]': {"--kpress-host-font-prose": "var(--prose-sans-font)"},
}
# The one rule that sets a face by context.
_CHROME_PROSE = {
    "font-family": "var(--prose-sans-font)",
    "--kpress-host-font-prose": "var(--prose-sans-font)",
}
# A plugin's Markdown view without KPress: its text, not the view, reads the reading font,
# through the prose hook first so that it follows chrome prose.
_DOCUMENT_FACES = {
    f".md-body:not(.metabrowser-kpress-host) {element}": (
        "var(--kpress-host-font-prose, var(--kpress-font-prose))"
    )
    for element in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "blockquote")
}
# Every element that holds chrome prose, by the file that builds it.
_CHROME_PROSE_BUILDERS = {
    "static/git-panel.js": 1,  # a commit's body
    "builtin_plugins/github/pull-page.js": 1,  # textBlock: a pull request's every text
    "builtin_plugins/github/guided-review.js": 1,  # proseHost: a guide step's title and note
}


def test_serif_is_only_for_documents() -> None:
    """Chrome prose is sans; serif is a document's, as "Serif Is for Documents" says.

    A pull request's description and comments read in the serif of a Markdown file, so a
    conversation about the content looked like part of it. Then a rule on the whole pull
    request page made them sans, and the Markdown files in its Changes with them. So one
    class says a text is chrome prose, the element that holds the text carries it, and no
    other rule sets a face by context: not through KPress's hooks or its resolved tokens,
    and not on KPress's own elements. The faces themselves are computed in Chrome by
    tests/test_prose_faces_chrome.py.
    """

    styles = STATIC / "styles.css"
    source = REPO_ROOT / "src" / "metabrowser"
    roots: dict[str, dict[str, str]] = {}
    documents: dict[str, str] = {}
    for path in sorted([*STATIC.glob("*.css"), *(REPO_ROOT / BUILTIN_PLUGINS).glob("*/*.css")]):
        for selector, declarations in _rules_of(path):
            family = declarations.get("font-family", "")
            faces = {name: value for name, value in declarations.items() if _FACE_TOKEN.match(name)}
            where = f"{path.relative_to(REPO_ROOT).as_posix()} {selector}"
            if path == styles and selector in _FACE_ROOTS:
                roots.setdefault(selector, {}).update(
                    {
                        name: value
                        for name, value in declarations.items()
                        if name in ("--font-sans", "--prose-sans-font") or _FACE_TOKEN.match(name)
                    }
                )
                assert not family, f"{where} sets a face"
                continue
            if path == styles and selector == ".chrome-prose":
                assert declarations == _CHROME_PROSE, where
                continue
            if path == styles and selector in _DOCUMENT_FACES:
                if family:
                    documents[selector] = family
            else:
                assert _SERIF.search(family) is None, f"{where} sets a serif: {family}"
                assert "--prose-sans-font" not in family, f"{where} sets chrome prose's face"
                assert not (family and _KPRESS_CLASS.search(selector)), (
                    f"{where} sets a face on KPress's own element: {family}"
                )
            # Only chrome prose sets a face by context, so no rule on a page reaches a
            # document it shows.
            assert not faces, f"{where} sets a face token: {sorted(faces)}"
    assert roots == _FACE_ROOTS
    assert documents == _DOCUMENT_FACES
    # An h2 is upright wherever the prose face is sans: the one rule that sets its style
    # keys on each selector that points the prose hook at sans, and on nothing else, so a
    # third such place cannot arrive without it.
    style_rules = _rules_of(styles)
    sans_hooks = {
        selector
        for selector, declarations in style_rules
        if declarations.get("--kpress-host-font-prose") == "var(--prose-sans-font)"
    }
    upright = [
        (selector, declarations)
        for selector, declarations in style_rules
        if selector.endswith(".kpress-prose h2") and "font-style" in declarations
    ]
    assert sans_hooks, "no rule points the prose hook at sans"
    assert {selector for selector, _ in upright} == {
        f"{hook} .kpress-prose h2" for hook in sans_hooks
    }
    for selector, declarations in upright:
        assert declarations == {"font-style": "normal"}, selector
    builders = {
        path.relative_to(source).as_posix(): path.read_text(encoding="utf-8").count("chrome-prose")
        for path in sorted([*STATIC.glob("*.js"), *(REPO_ROOT / BUILTIN_PLUGINS).glob("*/*.js")])
    }
    assert {name: count for name, count in builders.items() if count} == _CHROME_PROSE_BUILDERS
    assert dict(_rules_of(styles))['html[data-prose-font="sans"]']["--doc-char-advance"] == (
        "var(--sans-char-advance)"
    )
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "### Serif Is for Documents" in doc
    for name in ("test_serif_is_only_for_documents", "test_prose_faces_chrome.py", "chrome-prose"):
        assert name in doc
    # The plugin-facing contract names the class too.
    assert "`chrome-prose`" in (REPO_ROOT / "docs/plugins.md").read_text(encoding="utf-8")


def test_file_status_ink_is_shared_and_legible() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    light, dark = _theme_blocks()
    mapping = {
        "added": "added",
        "copied": "added",
        "deleted": "deleted",
        "removed": "deleted",
        "modified": "modified",
        "typechanged": "modified",
        "type_changed": "modified",
        "changed": "modified",
        "renamed": "renamed",
        "unmerged": "deleted",
    }
    rules = list(_rules_of(STATIC / "styles.css"))
    for status, role in mapping.items():
        assert any(
            f'[data-file-status="{status}"]' in selector
            and body.get("color") == f"var(--git-status-{role})"
            for selector, body in rules
        )
    assert "color: var(--muted)" in _rule(styles, ".file-change-status[data-file-status]")
    for block in (light, dark):
        for role in ("added", "deleted", "modified", "renamed"):
            # A literal, never a ref color: a ref kind's hue is chosen for the chips.
            color = _declared(block, f"--git-status-{role}")
            # A text's 4.5:1 on every ground a status is drawn on, a tooltip's among them, as
            # a commit's hover card draws its status counts, number and letter, in the ink
            # (mb-8iwn).
            for ground in ("--bg", "--sidebar-bg", "--hover-bg", "--viz-surface-raised"):
                assert _contrast(color, _declared(block, ground)) >= 4.5, (role, ground)
    # The current row's ground, a translucent tint, under a Pulls row's change line and its
    # file rows and the Files tree's current row: `--highlight-bg` over the ground it tints.
    # Over `--sidebar-bg` it is the modified ink's lowest in the light theme, 4.57:1 (A5 of
    # review A on #506).
    for theme, tokens in _theme_tokens().items():
        mix = _MIX_OVER_TRANSPARENT.fullmatch(_resolved(tokens, "--highlight-bg"))
        assert mix is not None, theme
        tint = _srgb(_resolved(tokens, mix["token"]))
        for role in ("added", "deleted", "modified", "renamed"):
            ink = _srgb_luminance(_srgb(_resolved(tokens, f"--git-status-{role}")))
            for under in ("--bg", "--sidebar-bg"):
                ground = _over(tint, _srgb(_resolved(tokens, under)), float(mix["percent"]) / 100)
                ratio = _ratio(ink, _srgb_luminance(ground))
                assert ratio >= 4.5, (theme, role, under, round(ratio, 2))
    for relative in (
        "static/git-panel.js",
        "builtin_plugins/diff/diff-view.js",
        "builtin_plugins/github/pull-files-view.js",
    ):
        source = (REPO_ROOT / "src/metabrowser" / relative).read_text(encoding="utf-8")
        assert "file-change-status" in source and (
            "data-file-status" in source or "fileStatus" in source
        )


def test_diff_text_and_reserved_geometry_use_the_dense_mono_token() -> None:
    css = (REPO_ROOT / BUILTIN_PLUGINS / "diff/styles.css").read_text(encoding="utf-8")
    view = (REPO_ROOT / BUILTIN_PLUGINS / "diff/diff-view.js").read_text(encoding="utf-8")
    assert "--code-font-size" not in css + view
    for selector in (
        ".metabrowser-diff-host .diff-line",
        ".metabrowser-diff-host .diff-split-side",
    ):
        assert "font-size: var(--mono-block-font-size)" in _rule(css, selector)
    metrics = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "diff/styles.css"))[
        ".metabrowser-diff-host"
    ]
    assert metrics["--diff-code-row-height"] == "calc(1.5 * var(--mono-block-font-size))"
    for kind in ("code", "header", "fold", "notice"):
        assert f"--diff-{kind}-row-height" in metrics
        assert f"var(--diff-{kind}-row-height)" in view


def test_ref_menu_chevron_uses_neutral_ink_without_reserving_space() -> None:
    rules = list(_rules_of(STATIC / "styles.css"))
    caret, reduced_motion = [
        declarations for selector, declarations in rules if selector == ".git-ref-menu-caret"
    ]
    assert caret["position"] == "absolute"
    assert caret["color"] == "var(--muted)"
    background = _MIX_OVER_TRANSPARENT.fullmatch(caret["background"])
    assert background is not None and background["token"] == "--viz-surface-raised"
    assert 0 < float(background["percent"]) < 100
    assert "opacity var(--transition-fast)" in caret["transition"]
    assert reduced_motion["transition"] == "none"
    assert dict(rules)[".git-ref-menu-caret > svg"]["transform"] == "rotate(90deg)"


# ── The Shift reveal's paint ────────────────────────────────────────
#
# Which badges mount and what the revealed strip lists are pinned browserlessly by the
# reveal session (`shell.key-reveal`). What they look like is paint, `shell.key-badge-paint`
# in the architecture map: these checks pin, by stylesheet text, the parts of it a
# stylesheet states, against the markup the registry, the reveal machine, and Help write.

_KEY_REVEAL_YELLOW_HUE = 98.1
# What a badge is drawn over, by target: the tab bars, the main-pane headers, and the
# filter bar are --sidebar-bg; the commit view's heading is --bg; a resting filter chip is
# --viz-surface; a hovered control or an open menu's trigger is --hover-bg; a trigger
# holding a value is --highlight-bg over the filter bar.
_BADGE_GROUNDS = ("--bg", "--sidebar-bg", "--viz-surface", "--hover-bg", "--highlight-bg")
_MIX_OVER_TRANSPARENT = re.compile(
    r"color-mix\(in srgb, var\((?P<token>--[\w-]+)\) (?P<percent>[\d.]+)%, transparent\)"
)


def _theme_tokens() -> dict[str, dict[str, str]]:
    """Every custom property each theme resolves: the light root, and the dark override on it."""

    rules = _rules_of(STATIC / "styles.css")
    light: dict[str, str] = {}
    dark: dict[str, str] = {}
    for selector, declarations in rules:
        if selector == ":root":
            light.update(declarations)
        elif selector == '[data-theme="dark"]':
            dark.update(declarations)
    return {"light": light, "dark": {**light, **dark}}


def _resolved(tokens: dict[str, str], token: str) -> str:
    """A token's value with `var()` aliases followed to the declaration that states a color."""

    value = tokens[token]
    seen = {token}
    while (alias := re.fullmatch(r"var\((--[\w-]+)\)", value)) is not None:
        assert alias[1] not in seen, f"{token} aliases itself"
        seen.add(alias[1])
        value = tokens[alias[1]]
    return value


def _translucent(value: str) -> tuple[str, float]:
    """An `oklch(L% C H / A)` color as its opaque `oklch(L% C H)` and its alpha."""

    found = re.fullmatch(r"oklch\(([\d.]+% [\d.]+ [\d.]+)(?: / ([\d.]+))?\)", value.strip())
    assert found is not None, value
    return f"oklch({found[1]})", float(found[2] or 1)


def _translucent_token(tokens: dict[str, str], token: str) -> tuple[str, float]:
    """A token's opaque `oklch()` color and its alpha, following `var()` aliases.

    A `color-mix(in srgb, var(--x) P%, transparent)` is `--x` at P% of its own alpha: a
    browser mixes with `transparent` premultiplied, so the color does not move toward black.
    """

    value = _resolved(tokens, token)
    mix = _MIX_OVER_TRANSPARENT.fullmatch(value)
    if mix is None:
        return _translucent(value)
    color, alpha = _translucent(_resolved(tokens, mix["token"]))
    return color, alpha * float(mix["percent"]) / 100


def _over(ink: tuple[float, ...], ground: tuple[float, ...], opacity: float) -> tuple[float, ...]:
    """*ink* at *opacity* over *ground*, blended in gamma-encoded sRGB as a browser does."""

    return tuple(
        opacity * front + (1 - opacity) * back for front, back in zip(ink, ground, strict=True)
    )


def _srgb_luminance(channels: tuple[float, ...]) -> float:
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _ground(tokens: dict[str, str], token: str) -> tuple[float, ...]:
    """The sRGB a surface token paints, a translucent mix composited over the filter bar."""

    value = _resolved(tokens, token)
    mix = _MIX_OVER_TRANSPARENT.fullmatch(value)
    if mix is not None:
        ink = _srgb(_resolved(tokens, mix["token"]))
        return _over(ink, _srgb(_resolved(tokens, "--sidebar-bg")), float(mix["percent"]) / 100)
    return _srgb(value)


def _key_reveal_contrast(tokens: dict[str, str]) -> dict[str, float]:
    """The ratios the reveal paints: its text on the strip's yellow, and a badge at its worst."""

    text = _srgb_luminance(_srgb(_resolved(tokens, "--kbd-badge-color")))
    strip = _srgb(_resolved(tokens, "--key-reveal-bg"))
    fill, alpha = _translucent_token(tokens, "--kbd-badge-bg")
    badge = min(
        _ratio(text, _srgb_luminance(_over(_srgb(fill), _ground(tokens, ground), alpha)))
        for ground in _BADGE_GROUNDS
    )
    # A keycap on the strip is a badge's fill over the strip's own yellow.
    keycap = _ratio(text, _srgb_luminance(_over(_srgb(fill), strip, alpha)))
    return {
        "badge": badge,
        "keycap": keycap,
        "muted": _ratio(
            _srgb_luminance(_srgb(_resolved(tokens, "--muted"))), _srgb_luminance(strip)
        ),
        "strip": _ratio(text, _srgb_luminance(strip)),
    }


def _first_rules() -> dict[str, dict[str, str]]:
    """Each selector of the shell stylesheet with its first rule: the one outside an at-rule
    override such as reduced motion or print, which follow it."""

    found: dict[str, dict[str, str]] = {}
    for selector, declarations in _rules_of(STATIC / "styles.css"):
        found.setdefault(selector, declarations)
    return found


def _at_rule_rules(prelude: str) -> list[tuple[str, dict[str, str]]]:
    """(one selector, declarations) for each rule inside every `prelude { … }` block."""

    css = re.sub(
        r"/\*.*?\*/", "", (STATIC / "styles.css").read_text(encoding="utf-8"), flags=re.DOTALL
    )
    found: list[tuple[str, dict[str, str]]] = []
    start = 0
    while (at := css.find(prelude, start)) >= 0:
        opening = css.index("{", at)
        depth = 0
        for index in range(opening, len(css)):
            depth += {"{": 1, "}": -1}.get(css[index], 0)
            if depth == 0:
                found.extend(
                    (selector.strip(), dict(_declarations(body)))
                    for selectors, body in _style_rules(css[opening + 1 : index])
                    for selector in _split_top(selectors, ",")
                )
                break
        start = opening + 1
    return found


def test_key_reveal_tokens_are_the_row_flash_yellow_in_both_themes() -> None:
    """The reveal is the live-row yellow (docs/design-system.md, "Badge Targets and the Shift Reveal").

    The strip's layer is `--row-flash-bg` itself; a badge is that color, partly transparent
    so the label under its leading edge shows through, and mixed from it rather than
    restating its numbers, so its dark value serves both; its border is a deeper tone of the
    same hue, with more chroma and a step toward the text, so a keycap keeps its edge on the
    yellow strip; and its text is the body text. The border is oklch at the yellow's hue in
    both themes, which is what `test_themed_colors_keep_their_hue` reads as one color.
    """

    themes = _theme_tokens()
    root = next(body for selector, body in _rules_of(STATIC / "styles.css") if selector == ":root")
    dark = next(
        body
        for selector, body in _rules_of(STATIC / "styles.css")
        if selector == '[data-theme="dark"]'
    )
    assert root["--key-reveal-bg"] == "var(--row-flash-bg)"
    assert root["--kbd-badge-color"] == "var(--text)"
    mix = _MIX_OVER_TRANSPARENT.fullmatch(root["--kbd-badge-bg"])
    assert mix is not None and mix["token"] == "--row-flash-bg", (
        "a badge's fill is --row-flash-bg mixed with transparent, not a copy of its numbers"
    )
    assert "--kbd-badge-bg" not in dark, "the badge's fill follows --row-flash-bg's dark value"
    assert "--kbd-badge-border" in root and "--kbd-badge-border" in dark, (
        "--kbd-badge-border must be defined in both themes"
    )
    for theme, tokens in themes.items():
        yellow = _oklch_channels(_resolved(tokens, "--key-reveal-bg"))
        assert yellow[2] == _KEY_REVEAL_YELLOW_HUE, f"the {theme} reveal left the row-flash hue"
        fill, alpha = _translucent_token(tokens, "--kbd-badge-bg")
        assert _oklch_channels(fill) == yellow, f"the {theme} badge is not the reveal's yellow"
        assert 0 < alpha < 1, f"the {theme} badge must be translucent, not {alpha}"
        border, border_alpha = _translucent(tokens["--kbd-badge-border"])
        lightness, chroma, hue = _oklch_channels(border)
        assert border_alpha == 1 and hue == _KEY_REVEAL_YELLOW_HUE
        assert chroma > yellow[1], f"the {theme} badge border is no deeper than its fill"
        ink = _oklch_channels(_resolved(tokens, "--text"))[0]
        assert abs(lightness - ink) < abs(yellow[0] - ink), (
            f"the {theme} badge border does not step from the fill toward the text"
        )


def test_key_reveal_text_meets_contrast_in_both_themes() -> None:
    """Everything the reveal paints keeps 4.5:1, and the ratios beside the tokens are these.

    A badge's keycap is measured as composited: its translucent fill over each surface a
    target sits on. The revealed strip's labels and keycaps are measured on its yellow, which
    is why they are `--text`: `--muted` does not reach 4.5:1 there.
    """

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    measured = {theme: _key_reveal_contrast(tokens) for theme, tokens in _theme_tokens().items()}
    for theme, ratios in measured.items():
        for surface in ("badge", "keycap", "strip"):
            assert ratios[surface] >= 4.5, f"the {theme} {surface} reads {ratios[surface]:.2f}:1"
        assert ratios["muted"] < 4.5, f"--muted reads on the {theme} yellow; the note is stale"
    recorded = re.findall(r"(light|dark)\s+strip\s+([\d.]+):1\s+badge\s+([\d.]+):1", styles)
    assert {theme for theme, _strip, _badge in recorded} == {"light", "dark"}
    for theme, strip, badge in recorded:
        assert (strip, badge) == (
            f"{measured[theme]['strip']:.2f}",
            f"{measured[theme]['badge']:.2f}",
        ), f"the {theme} ratios recorded beside the tokens have drifted"
    muted = re.search(
        r"--muted reads ([\d.]+):1\s+on\s+the\s+light\s+yellow\s+and\s+([\d.]+):1", styles
    )
    assert muted is not None
    assert (muted[1], muted[2]) == (
        f"{measured['light']['muted']:.2f}",
        f"{measured['dark']['muted']:.2f}",
    )


def test_key_badges_are_positioned_paint_over_layer_three_markup() -> None:
    """A badge is a `.kbd` that changes only its paint, ignores the pointer, and moves no box.

    The registry mounts `kbd.kbd.kbd-badge` with `data-kbd-placement`; `inline-end` makes the
    target `.kbd-badge-host`, and `beside` writes the target's inline end and vertical center,
    measured from the nearest `[data-kbd-badge-anchor]`, as two custom properties. The host
    and the anchor become containing blocks through zero-specificity rules, so an element
    that already declares a position keeps it.
    """

    registry = (STATIC / "keyboard-shortcuts.js").read_text(encoding="utf-8")
    for written in (
        'badge.className = "kbd kbd-badge";',
        "badge.dataset.kbdPlacement = record.placement;",
        'classList.add("kbd-badge-host")',
        '"--kbd-badge-inline"',
        '"--kbd-badge-block"',
        'const BADGE_ANCHOR_SELECTOR = "[data-kbd-badge-anchor]";',
    ):
        assert written in registry, f"the registry no longer writes {written}"
    assert 'const ROOT_ATTRIBUTE = "data-key-reveal";' in (STATIC / "key-reveal.js").read_text(
        encoding="utf-8"
    )
    selected = _first_rules()
    badge = selected[".kbd-badge"]
    assert badge["position"] == "absolute"
    assert badge["pointer-events"] == "none"
    assert badge["background"] == "var(--kbd-badge-bg)"
    assert badge["border-color"] == "var(--kbd-badge-border)"
    assert badge["color"] == "var(--kbd-badge-color)"
    assert badge["box-shadow"] == "var(--shadow-sm)"
    keycap = {"font", "font-family", "font-size", "font-weight", "letter-spacing", "line-height"}
    keycap |= {"text-transform", "border-radius", "border-width", "padding", "min-width"}
    assert not keycap & set(badge), f"a badge restyles the keycap: {sorted(keycap & set(badge))}"
    inline_end = selected['.kbd-badge[data-kbd-placement="inline-end"]']
    assert inline_end["inset-inline-end"] == "0"
    assert (inline_end["top"], inline_end["translate"]) == ("50%", "0 -50%")
    beside = selected['.kbd-badge[data-kbd-placement="beside"]']
    assert beside["inset-inline-end"] == "calc(100% - var(--kbd-badge-inline))"
    assert (beside["top"], beside["translate"]) == ("var(--kbd-badge-block)", "0 -50%")
    assert selected[":where(.kbd-badge-host)"] == {"position": "relative"}
    assert selected[":where([data-kbd-badge-anchor])"] == {"position": "relative"}
    # The anchor: the view header, a file's and a folder's alike, for Up's button. The
    # commit heading anchored Copy revision's badge, and copying has no key any more.
    header = (STATIC / "view-header.js").read_text(encoding="utf-8")
    assert header.count("data-kbd-badge-anchor") == 1
    assert '`<div class="file-header view-header${' in header
    assert "data-kbd-badge-anchor" not in (STATIC / "app.js").read_text(encoding="utf-8")
    git_panel = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    assert "data-kbd-badge-anchor" not in git_panel


def test_beside_badges_end_at_their_targets_inline_end() -> None:
    """A `beside` badge covers the end of its own control and no text outside it.

    The registry writes `--kbd-badge-inline` as the target's inline end, measured from the
    anchor's inline-start edge. The badge's inline end sits that far from the anchor's
    inline start, which is `100%` less it from the anchor's inline end, so the badge ends
    where its target ends, as an `inline-end` badge does. A badge that started there
    instead, just past its target, covered the first glyphs of whatever came next: the
    file name after Up's crumb, the mirror note after Copy path, the path after the
    folder's Up, and the author after Copy revision. `100%` is the anchor's padding box,
    which is the border box the registry measures from only while no anchor has an inline
    border.
    """

    registry = (STATIC / "keyboard-shortcuts.js").read_text(encoding="utf-8")
    measured = "const inline = rtl ? anchorBox.right - box.left : box.right - anchorBox.left;"
    assert measured in registry, "the registry measures the target's inline end differently"
    rules = _rules_of(STATIC / "styles.css")
    beside = [body for selector, body in rules if 'data-kbd-placement="beside"' in selector]
    assert len(beside) == 1, "a beside badge is placed by one rule"
    placement = beside[0]
    offsets = {name for name in placement if name.startswith(("inset", "left", "right", "margin"))}
    assert offsets == {"inset-inline-end"}, (
        f"a beside badge is placed by {sorted(offsets)}, not by its inline end alone"
    )
    assert placement["inset-inline-end"] == "calc(100% - var(--kbd-badge-inline))"
    assert placement["translate"].split()[0] == "0", "a beside badge is shifted off its target"
    anchor = re.compile(r"(\.(file-header|folder-header|git-commit-header))+")
    for selector, body in rules:
        if anchor.fullmatch(re.split(r"[\s>+~]+", selector)[-1]):
            borders = {
                name
                for name in body
                if re.fullmatch(r"border(-width|-style|-(left|right|inline)(-[\w-]+)?)?", name)
            }
            assert not borders, f"{selector} gives a badge anchor an inline border: {borders}"


def test_hover_revealed_controls_take_no_key() -> None:
    """A control that appears only on hover is ancillary, so it is never a key's target.

    Both copy buttons are `.icon-btn-reveal`, transparent until hover or focus, and copying
    has no key ("Keyboard Shortcuts" in docs/design-system.md), so the reveal never has to
    show a hidden control and the stylesheet keeps no override that would. Only the
    registry, Help's strip buttons, and the overlay's close button write
    `aria-keyshortcuts`, and none of them on a reveal-on-hover button.
    """

    selectors = [selector for selector, _ in _rules_of(STATIC / "styles.css")]
    assert not [s for s in selectors if "data-key-reveal" in s and "icon-btn-reveal" in s]
    writes = re.compile(r"""setAttribute\(\s*"aria-keyshortcuts"|aria-keyshortcuts=""")
    writers = {
        source.name for source in _browser_sources() if writes.search(source.read_text("utf-8"))
    }
    # The registry for targets; Help for the strip's buttons; the overlay for a close button.
    assert writers == {"keyboard-shortcuts.js", "keyboard-help.js", "overlay-layer.js"}, writers
    for name in writers - {"keyboard-shortcuts.js"}:
        assert "icon-btn-reveal" not in (STATIC / name).read_text(encoding="utf-8"), name


def test_key_reveal_fades_in_hides_at_once_and_respects_reduced_motion() -> None:
    """The badges and the strip ease in on the reveal motion token, appear at once under
    reduced motion, and go at once: they leave the document when the reveal ends, so nothing
    animates them out ("Reveals" in docs/design-system.md).

    `--motion-reveal` is the one duration and curve every reveal shares, shorter than the
    200 ms hold that starts the Shift reveal. A badge fades and grows, through the `scale`
    property, which composes with the `translate` that centers it; the strip only fades,
    since a pane-wide layer that grew would move. Both run on transform and opacity alone,
    so the compositor draws them, and none needs a `-webkit-` form in the macOS app's WebKit.
    """

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    token = re.search(r"--motion-reveal:\s*([^;]+);", styles)
    assert token is not None and token[1] == "180ms cubic-bezier(0.2, 0, 0, 1)", token
    milliseconds = re.match(r"(\d+)ms", token[1])
    assert milliseconds is not None, token[1]
    duration = int(milliseconds[1])
    hold = re.search(
        r"const REVEAL_HOLD_MS = (\d+);", (STATIC / "key-reveal.js").read_text(encoding="utf-8")
    )
    assert hold is not None and duration < int(hold[1]), "the fade fits inside the hold"
    rules = _first_rules()
    assert rules[".kbd-badge"]["animation"] == "key-reveal-in var(--motion-reveal)"
    assert rules[".nav-shortcut-reveal"]["animation"] == "key-reveal-fade-in var(--motion-reveal)"
    assert "--transition-fast" not in rules[".kbd-badge"]["animation"]
    for name, properties in (
        ("key-reveal-in", {"opacity", "scale"}),
        ("key-reveal-fade-in", {"opacity"}),
    ):
        keyframes = re.search(rf"@keyframes {name} \{{(.*?)\n\}}", styles, re.DOTALL)
        assert keyframes is not None, name
        assert set(re.findall(r"([a-z-]+):", keyframes[1])) == properties, name
        assert re.search(r"\bfrom \{\s*opacity: 0;", keyframes[1]), f"{name} starts transparent"
        assert "to {" not in keyframes[1], f"{name} ends at the element's own style"
    assert "-webkit-animation" not in styles and "@-webkit-keyframes" not in styles
    reduced = _at_rule_rules("@media (prefers-reduced-motion: reduce)")
    for selector in (".kbd-badge", ".nav-shortcut-reveal"):
        assert (selector, {"animation": "none"}) in reduced, f"reduced motion keeps {selector}"
    # The reveal machine removes the badges and the layer rather than hiding them.
    registry = (STATIC / "keyboard-shortcuts.js").read_text(encoding="utf-8")
    assert "record.badge.remove();" in registry
    assert "revealLayer.remove();" in (STATIC / "keyboard-help.js").read_text(encoding="utf-8")


def test_key_reveal_never_prints() -> None:
    printed = _at_rule_rules("@media print")
    for selector in (".kbd-badge", ".nav-shortcut-reveal", ".nav-shortcut-hints"):
        assert any(
            candidate == selector and body.get("display") == "none" for candidate, body in printed
        ), f"{selector} prints"


def test_revealed_strip_overlays_the_panel_without_reflowing_it() -> None:
    """The strip's host keeps its resting size; the reveal layer grows upward over the panel.

    Help appends the layer to `#nav-shortcut-hints` while revealed. Positioned against the
    host's bottom edge and out of flow, it covers the resting strip and as much of the tree,
    history, or pull list above as its items need, and the panel neither reflows nor
    scrolls. It declares no z-index, so the panel's pinned headers and open menus, which do,
    stay above it, and rows, which do not, stay under it.
    """

    help_source = (STATIC / "keyboard-help.js").read_text(encoding="utf-8")
    assert 'revealLayer.className = "nav-shortcut-reveal";' in help_source
    assert "options.hintHost.append(revealLayer);" in help_source
    rules = _first_rules()
    host = rules[".nav-shortcut-hints"]
    assert (host["position"], host["flex"]) == ("relative", "0 0 auto")
    layer = rules[".nav-shortcut-reveal"]
    assert layer["position"] == "absolute"
    assert (layer["inset-inline"], layer["bottom"]) == ("0", "0")
    assert "top" not in layer and "height" not in layer, "the layer grows with its items"
    assert layer["min-height"] == "calc(100% + 1px)", "it covers the host and its top border"
    assert (layer["background"], layer["color"]) == ("var(--key-reveal-bg)", "var(--text)")
    assert "z-index" not in layer
    assert rules[".nav-shortcut-reveal[hidden]"] == {"display": "none"}
    keycap = rules[".nav-shortcut-reveal .kbd"]
    assert keycap == {
        "background": "var(--kbd-badge-bg)",
        "border-color": "var(--kbd-badge-border)",
        "color": "var(--kbd-badge-color)",
    }
    assert rules[".nav-shortcut-reveal .shortcut-binding-separator"] == {"color": "var(--text)"}


# ── Heading tallies are one node sequence ──────────────────────────
#
# docs/design-system.md, "Heading Tallies". The tally keeps its white space
# (`white-space: pre`), so its markup is whitespace-sensitive, and it is built twice: as
# an HTML string in the shell and as `h()` nodes in the GitHub plugin. Every source that
# builds a `.heading-tally` is found, each build is held to the one node sequence (a
# space, the hidden dot, a space, the figure, and an optional unit, with no white space
# between the name and the tally), and the builders found are held to the design
# system's table of headings that carry one. A builder is the nearest `function` before
# the tally; review holds that it is the heading's builder.

_TALLY_CLASS = re.compile(r"""["']heading-tally["']""")
# The shell's HTML string, with its template literals joined: the tally, then its unit.
_TALLY_HTML = re.compile(
    r'<span class="heading-tally"> <span class="heading-tally-dot" aria-hidden="true">·</span>'
    r' <span class="heading-tally-figure">\$\{[^`]+?\}</span>(?: \$\{\w+\}| \w+)?</span>'
)
# A plugin's `h()` nodes.
_TALLY_NODES = re.compile(
    r'h\("span", \{ class: "heading-tally" \}, \[\s*" ",\s*'
    r'h\("span", \{ class: "heading-tally-dot", "aria-hidden": "true" \}, \["·"\]\),\s*" ",\s*'
    r'h\("span", \{ class: "heading-tally-figure" \}, \[[^\]]*\]\),\s*(?:"[^"]*",\s*)?\]\)'
)
_TALLY_ROW = re.compile(r"(?m)^\| [^|]+ \| `(?P<builder>\w+)` in `(?P<path>[^`]+)` \| [^|]+ \|$")


def _joined_templates(text: str) -> str:
    """*text* with each concatenation of two template literals joined into one."""

    return re.sub(r"`\s*\+\s*`", "", text)


def _heading_tally_problems(key: str, text: str) -> tuple[set[str], list[str]]:
    """The builders in *text* that build a `.heading-tally`, and what is wrong with each."""

    text = _joined_templates(text)
    builds = [*_TALLY_HTML.finditer(text), *_TALLY_NODES.finditer(text)]
    builders: set[str] = set()
    problems: list[str] = []
    for found in _TALLY_CLASS.finditer(text):
        at = found.start()
        build = next((build for build in builds if build.start() <= at < build.end()), None)
        line = text.count("\n", 0, at) + 1
        if build is None:
            problems.append(f"{key}:{line} builds a .heading-tally out of the one sequence")
            continue
        if build.start() != at - len("<span class=") and not build.group().startswith("h("):
            problems.append(f"{key}:{line} is not the tally's own element")
            continue
        before = text[: build.start()]
        # Nothing but the name before it: no white space in the same literal, and no
        # whitespace-only string node.
        if build.group().startswith("<span"):
            if not re.search(r"(?:>|\+\s*`)$", before):
                problems.append(f"{key}:{line} puts white space between the name and the tally")
        elif re.search(r'"\s*",\s*$', before):
            problems.append(f"{key}:{line} puts a white-space node between the name and the tally")
        names = re.findall(r"\bfunction\s+(\w+)\s*\(", before)
        if not names:
            problems.append(f"{key}:{line} builds a .heading-tally outside any function")
            continue
        builders.add(names[-1])
    return builders, problems


def test_every_heading_tally_is_the_one_node_sequence() -> None:
    """Each source that builds a heading's tally builds the same nodes, and is listed."""

    found: set[tuple[str, str]] = set()
    problems: list[str] = []
    for source in _browser_sources():
        key = source.relative_to(REPO_ROOT).as_posix()
        builders, wrong = _heading_tally_problems(key, source.read_text(encoding="utf-8"))
        found |= {(key, builder) for builder in builders}
        problems += wrong
    assert problems == []
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    section = doc.split("\n### Heading Tallies\n", 1)[1].split("\n### ", 1)[0]
    listed = {(row["path"], row["builder"]) for row in _TALLY_ROW.finditer(section)}
    assert listed, "the Heading Tallies table is missing"
    assert found == listed
    # The numeral's weight is a count's, through its own token, not a pull request number's.
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert styles.count("--count-numeral-weight:") == 1
    assert "--count-numeral-weight: var(--weight-bold);" in styles
    assert "font-weight: var(--count-numeral-weight);" in _rule(styles, ".heading-tally-figure")
    assert "white-space: pre;" in _rule(styles, ".heading-tally")


def test_a_heading_tally_out_of_sequence_fails() -> None:
    """White space before the tally, a missing dot, or a tally built elsewhere fails."""

    key = "static/app.js"
    text = (STATIC / "app.js").read_text(encoding="utf-8")
    builders, problems = _heading_tally_problems(key, text)
    assert (builders, problems) == ({"treeSectionHeadingHtml"}, [])
    tally = '`<span class="heading-tally"> '
    assert text.count(tally) == 1
    spaced = text.replace("label +\n    " + tally, "label +\n    ` " + tally[1:])
    assert spaced != text
    assert _heading_tally_problems(key, spaced)[1]
    undotted = text.replace('<span class="heading-tally-dot" aria-hidden="true">·</span> ', "")
    assert _heading_tally_problems(key, undotted)[1]
    page = (REPO_ROOT / BUILTIN_PLUGINS / "github/pull-page.js").read_text(encoding="utf-8")
    builders, problems = _heading_tally_problems("github/pull-page.js", page)
    assert (builders, problems) == ({"reviewThreads"}, [])
    named = '        "Review comments",\n'
    assert page.count(named) == 1
    padded = page.replace(named, named + '        " ",\n')
    assert _heading_tally_problems("github/pull-page.js", padded)[1]
    elsewhere = text + '\nconst stray = `<span class="heading-tally">3</span>`;\n'
    assert _heading_tally_problems(key, elsewhere)[1]


# ── Tokens: every one used is defined, and the system's inks read ────────────────────


def _shipped_css_text() -> dict[Path, str]:
    return {sheet: sheet.read_text(encoding="utf-8") for sheet in _stylesheets()}


# A custom property a stylesheet reads that no shipped stylesheet or script sets: the host
# page or an embedded document supplies these, so they are not ours to define. A prefix
# names a family the host owns.
_EXTERNAL_PROPERTIES: frozenset[str] = frozenset(
    {
        # Written per element by a script through a named constant, so no literal
        # `setProperty("--name")` call is there to find (folder/category-palette.js's
        # LIGHT_PROPERTY and DARK_PROPERTY; app.js's FILE_COLOR_*_PROPERTY).
        "--mb-distribution-color-light",
        "--mb-distribution-color-dark",
        "--mb-file-color-light",
        "--mb-file-color-dark",
        # The embedded kpress document's own properties, which its stylesheet defines.
        "--kpress-font-prose",
        "--kpress-line-height-normal",
        "--kpress-toc-toggle-clearance",
        "--kpress-column-inset",
    }
)
_VAR_WITHOUT_FALLBACK = re.compile(r"var\(\s*(--[\w-]+)\s*\)")
_PROPERTY_DECLARATION = re.compile(r"(--[a-zA-Z][\w-]*)\s*:")
_SET_PROPERTY = re.compile(r"setProperty\(\s*[\"'`](--[\w-]+)")


def _defined_custom_properties() -> set[str]:
    defined: set[str] = set()
    for css in _shipped_css_text().values():
        defined.update(_PROPERTY_DECLARATION.findall(re.sub(r"/\*.*?\*/", "", css, flags=re.S)))
    for source in _browser_sources():
        # A name in a comment is prose, not a definition.
        text = re.sub(r"/\*.*?\*/", "", source.read_text(encoding="utf-8"), flags=re.S)
        text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
        defined.update(_SET_PROPERTY.findall(text))
        # An inline `style="--x: …"` or a style object key written by a script.
        defined.update(_PROPERTY_DECLARATION.findall(text))
    return defined


def test_every_custom_property_a_stylesheet_reads_is_defined() -> None:
    """`var(--x)` with no fallback names a token, so the token must exist.

    A read of a name nothing defines falls through to the property's initial value, which
    is how `min-height: var(--button-height-compact)` sat in the shell doing nothing. A
    read with a fallback is an optional hook and is not checked.

    Limit: "defined" is a name set anywhere in a shipped stylesheet, or in a script outside
    a comment, at any selector; it does not check that the definition is in scope of the
    reader (a token set only under one component's selector but read elsewhere passes).
    """

    defined = _defined_custom_properties()
    undefined: dict[str, set[str]] = {}
    for sheet, css in _shipped_css_text().items():
        stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        for name in _VAR_WITHOUT_FALLBACK.findall(stripped):
            if name in defined or name in _EXTERNAL_PROPERTIES:
                continue
            undefined.setdefault(name, set()).add(_sheet_name(sheet))
    assert not undefined, f"custom properties read but never defined: {undefined}"


_FOCUS_OUTLINE = "var(--focus-ring-width) solid var(--focus-ring-color)"
_FOCUS_OFFSET = "var(--focus-ring-offset)"
_FOCUS_OFFSET_OUTSET = "var(--focus-ring-offset-outset)"
# The bare controls whose box is their text: a ring inside it would sit on the glyphs, so it
# stands outside (docs/design-system.md, "Focus Ring"). Nothing else takes the outset.
_FOCUS_RING_OUTSET = frozenset(
    {
        ".nav-shortcut-action:focus-visible",
        ".filter-check:has(input:focus-visible)",
        ".help-project a:focus-visible",
        ".event-log-details a:focus-visible",
        # A session's link in the agents views: a bare inline link, as the two above are.
        "a.agents-session-link:focus-visible",
    }
)


def test_every_focus_ring_is_the_one_ring() -> None:
    """Width, color, and offset come from the focus-ring tokens, never a literal."""

    problems: list[str] = []
    for sheet in _stylesheets():
        for selector, declarations in _rules_of(sheet):
            outline = declarations.get("outline")
            if "focus-visible" not in selector or outline is None or outline in {"none", "0"}:
                continue
            offset = declarations.get("outline-offset")
            want = _FOCUS_OFFSET_OUTSET if selector in _FOCUS_RING_OUTSET else _FOCUS_OFFSET
            if outline != _FOCUS_OUTLINE or offset != want:
                problems.append(f"{_sheet_name(sheet)} {selector}: {outline}; offset {offset}")
    assert not problems, "\n".join(problems)


def test_the_outset_focus_ring_is_only_for_the_documented_controls() -> None:
    """A control not in the allowlist cannot take the outset by naming the token."""

    outset = {
        selector
        for sheet in _stylesheets()
        for selector, declarations in _rules_of(sheet)
        if declarations.get("outline-offset") == _FOCUS_OFFSET_OUTSET
    }
    assert outset == set(_FOCUS_RING_OUTSET)
    root = _theme_tokens()["light"]
    assert root["--focus-ring-offset"].startswith("-")
    assert root["--focus-ring-offset-outset"][0].isdigit()


def test_a_link_no_rule_colors_is_the_link_color() -> None:
    """The shell sets the base anchor, so a new view's bare link is never the user agent's.

    The base is zero-specificity (`:where`), so every context's own color, hover, and ring
    still win; it covers a visited link too (`:any-link`); and it sets the color alone, so
    the contexts that keep the user agent's underline at rest are unchanged. The Chrome
    half, that a bare `<a href>` in a plugin view computes to `--link` and not the user
    agent's blue or visited purple, is in `tests/dom/agents-views-chrome.mjs`.
    """

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert dict(_declarations(_rule(styles, ":where(a:any-link)"))) == {"color": "var(--link)"}
    # The rules the base made redundant stay gone: a context that colors every anchor in it
    # with the link color is patching the user agent's fallback one context at a time.
    for selector in (
        ".help-project a",
        ".event-log-details a",
        ".md-body:not(.metabrowser-kpress-host) a",
    ):
        for sheet in _stylesheets():
            for rule, declarations in _rules_of(sheet):
                assert not (rule == selector and "color" in declarations), (
                    f"{selector} recolors a link the base already colors"
                )


def test_a_control_no_rule_rings_takes_the_one_ring() -> None:
    """A button or summary that no rule rings draws the one ring, not the user agent's.

    The base is zero-specificity, `:focus-visible` inside the `:where` too, so every family's
    own `:focus-visible` rule still wins; it states the ring from the four tokens and nothing
    else; and it rings the elements a control is built from, `button` and `summary`, and not
    links, whose ring is their context's (docs/design-system.md, "Focus Ring"). Because any
    rule wins, KPress's ring on a `summary` in `article.kpress` does too, so the rendered
    diff's fold states the ring itself; tests/test_diff_markdown_fold_chrome.py reads it.
    """

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    base = ":where(button:focus-visible, summary:focus-visible)"
    assert dict(_declarations(_rule(styles, base))) == {
        "outline": "var(--focus-ring-width) solid var(--focus-ring-color)",
        "outline-offset": "var(--focus-ring-offset)",
    }
    # One base, stated once: a second would be a fork of it.
    assert styles.count(base) == 1


def test_the_ref_selectors_current_row_shows_focus_by_the_ring() -> None:
    """A menu row shows focus by the hover tint, which the current row's highlight replaces.

    So the current row, the working tree's or a ref's, draws the one ring on focus instead,
    and keyboard focus on it is not invisible.
    """

    shell = dict(_rules_of(STATIC / "styles.css"))
    assert shell[".menu-item:focus-visible"] == {"background": "var(--hover-bg)", "outline": "none"}
    for row in (".source-ref-selector-row", ".source-ref-selector-working-tree"):
        current = f'{row}[aria-current="true"]'
        assert shell[current]["background"] == "var(--highlight-bg)", row
        assert shell[current + ":focus-visible"] == {
            "outline": _FOCUS_OUTLINE,
            "outline-offset": _FOCUS_OFFSET,
        }, row


_STATUS_TEXT_TOKENS = (
    "--status-success-text",
    "--status-warning-text",
    "--status-error-text",
    "--status-info-text",
    "--status-success-soft-text",
)
_BADGE_TONES = (
    "completed",
    "failed",
    "running",
    "pending",
    "adapter",
    "compressed",
)
_STATUS_FILL_TOKENS = (
    "--status-success",
    "--status-warning",
    "--status-warning-strong",
    "--status-error",
    "--status-error-strong",
    "--status-info",
)
_AA_TEXT = 4.5
# WCAG 2.2's 1.4.11 Non-text Contrast: a mark that says something, a glyph, against its ground.
_AA_GRAPHIC = 3.0


def test_status_and_badge_inks_read_in_both_themes() -> None:
    """A status ink is held to 4.5:1 on the page and the hover ground; a badge's on its own fill."""

    for theme, tokens in _theme_tokens().items():
        for ground_token in ("--bg", "--hover-bg"):
            ground = _resolved(tokens, ground_token)
            for token in _STATUS_TEXT_TOKENS:
                ink = _resolved(tokens, token)
                assert _contrast(ink, ground) >= _AA_TEXT, (
                    f"{token} in the {theme} theme reads at {_contrast(ink, ground):.2f}:1 "
                    f"on {ground_token}"
                )
        for tone in _BADGE_TONES:
            fill = _resolved(tokens, f"--badge-{tone}-bg")
            ink = _resolved(tokens, f"--badge-{tone}-text")
            assert _contrast(ink, fill) >= _AA_TEXT, (
                f"--badge-{tone} in the {theme} theme reads at {_contrast(ink, fill):.2f}:1"
            )


def test_status_text_inks_keep_their_fills_hue() -> None:
    """A text ink is its fill's color seen as text, so the two share a hue family."""

    light = _theme_tokens()["light"]
    for name in ("success", "warning", "error"):
        ink = _oklch_channels(_resolved(light, f"--status-{name}-text"))
        fill = _oklch_channels(_resolved(light, f"--status-{name}"))
        assert _hue_gap(ink[2], fill[2]) <= 15, name


def test_no_stylesheet_sets_text_in_a_status_fill() -> None:
    """A fill token is for dots, bars, tints, and borders; text takes the themed ink."""

    fills = {f"var({token})" for token in _STATUS_FILL_TOKENS}
    problems = [
        f"{_sheet_name(sheet)} {selector}: color {declarations['color']}"
        for sheet in _stylesheets()
        for selector, declarations in _rules_of(sheet)
        if declarations.get("color") in fills
    ]
    assert not problems, "\n".join(problems)


def test_a_failure_is_one_ink_and_a_stat_is_one_pair() -> None:
    """Additions and deletions read in one ink wherever drawn, and so does a failed load."""

    ink = {
        ".diff-stat-add": "--status-success-text",
        ".diff-stat-del": "--status-error-text",
    }
    seen: dict[str, set[str]] = {}
    for sheet in _stylesheets():
        for selector, declarations in _rules_of(sheet):
            for stat in ink:
                if selector.endswith(stat) and "color" in declarations:
                    seen.setdefault(stat, set()).add(declarations["color"])
    for stat, token in ink.items():
        assert seen.get(stat) == {f"var({token})"}, (stat, seen.get(stat))
    failure = {
        ".tree-lazy-error",
        ".git-graph-more-failed",
        ".nav-error",
        ".source-freshness-error",
        ".source-ref-selector-error",
    }
    found = {
        selector: declarations["color"]
        for selector, declarations in _rules_of(STATIC / "styles.css")
        if selector in failure and "color" in declarations
    }
    assert set(found) == failure
    assert set(found.values()) == {"var(--status-error-text)"}


def test_the_diff_row_tints_are_shell_tokens() -> None:
    """The plugins and the shell tint an added or removed line from one pair."""

    root = _theme_tokens()["light"]
    assert root["--diff-add-row-bg"] == "color-mix(in srgb, var(--status-success) 9%, transparent)"
    assert root["--diff-del-row-bg"] == "color-mix(in srgb, var(--status-error) 9%, transparent)"


_RADIUS_VALUE = r"(?:var\(--[\w-]*radius[\w-]*\)|0|inherit)"
_BORDER_RADIUS = re.compile(rf"{_RADIUS_VALUE}(?:\s+{_RADIUS_VALUE})*")
# A radius that is not a token, and why: a shape the token set cannot say.
_RADIUS_EXCEPTIONS: dict[tuple[str, str], str] = {}


def test_every_border_radius_is_a_radius_token() -> None:
    """The app's corners are `--radius-*` tokens; a literal forks the shape vocabulary."""

    problems = []
    for sheet in _stylesheets():
        for selector, declarations in _rules_of(sheet):
            value = declarations.get("border-radius")
            if value is None or _BORDER_RADIUS.fullmatch(value):
                continue
            if (_sheet_name(sheet), selector) in _RADIUS_EXCEPTIONS:
                continue
            problems.append(f"{_sheet_name(sheet)} {selector}: {value}")
    assert not problems, "\n".join(problems)


_FIELD_CONSUMERS = (".menu-select", ".menu-number", ".source-ref-selector-filter")
_FIELD_OWNED = ("border", "background", "outline", "outline-offset", "border-radius")


def test_text_fields_carry_the_field_primitive() -> None:
    """Border, fill, ring, and hover are stated once; a field sets only its own layout."""

    rules = _rules_of(STATIC / "styles.css")
    alone = [
        (selectors.strip(), dict(_declarations(body)))
        for selectors, body in _style_rules((STATIC / "styles.css").read_text(encoding="utf-8"))
    ]
    for selector in _FIELD_CONSUMERS:
        own = [declarations for selectors, declarations in alone if selectors == selector]
        assert own, selector
        for declarations in own:
            restated = [name for name in _FIELD_OWNED if name in declarations]
            assert not restated, f"{selector} restates {restated}"
    field = dict(next(d for rule, d in rules if rule == ".field"))
    assert {"border", "background", "border-radius", "padding"} <= set(field)
    assert any(rule == ".field:focus-visible" for rule, _ in rules)
    source = (STATIC / "source-ref-selector.js").read_text(encoding="utf-8")
    assert 'filter.className = "field source-ref-selector-filter";' in source
    server = (STATIC.parent / "server.py").read_text(encoding="utf-8")
    assert '<select class="field menu-select"' in server
    assert '<input class="field menu-number"' in server
