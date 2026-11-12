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
    # The registry's leading chevrons (tree rows, tally tree, diff bars);
    # icons.js quotes attributes with double quotes.
    assert icons.count(f'd="{CHEVRON_PATH}"') >= 2, "registry chevron glyphs changed shape"
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
    header = "File and folder header"  # the file view header and renderFolderHeader
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
        (
            header,
            ".file-header",
            el(
                "file-header",
                text("file-header-path folder-breadcrumb", el("folder-crumb folder-crumb-current")),
                box("file-header-badge badge-live"),
                text("size file-header-size"),
                box("icon-btn file-header-icon file-header-print"),
            ),
        ),
        (
            header,
            ".file-header",
            el("file-header", text("file-header-path"), box("size tally-pending file-header-size")),
        ),
        (
            header,
            ".file-header",
            el(
                "file-header folder-header",
                box("btn parent-nav-btn parent-nav-btn-icon-only folder-up"),
                text("file-header-path folder-breadcrumb"),
                text(
                    "folder-header-summary",
                    el("size file-header-size"),
                    el("count folder-header-count"),
                    el("folder-header-age", el("age-min")),
                ),
            ),
        ),
        (
            header,
            ".file-header",
            el(
                "file-header folder-header",
                box("btn parent-nav-btn folder-up"),
                text("file-header-path"),
                box(
                    "folder-header-summary",
                    el("size tally-pending file-header-size"),
                    el("count tally-pending folder-header-count"),
                    el("folder-header-age", el("tally-pending tally-pending-narrow")),
                ),
            ),
        ),
    ]
    # Diff file bar: renderFileBar in the diff plugin, inside its host.
    toggle = el(
        "diff-file-toggle expanded",
        box("diff-file-chevron"),
        text("diff-file-kind diff-file-kind-modified"),
        text("diff-file-path"),
        text("diff-file-stats", el("diff-stat-add"), el("diff-stat-del")),
        text("diff-file-note"),
    )
    bar = el(
        "diff-file-bar",
        toggle,
        # View file controls: boxes at the path's size, which centering puts on its baseline.
        box("diff-file-view diff-file-view-base"),
        box("diff-file-view diff-file-view-head"),
        box("icon-btn icon-btn-reveal diff-file-copy"),
    )
    el("content-body metabrowser-diff-host", el("diff-file", bar))
    rows.append(("Diff file bar", f"{diff_host} .diff-file-toggle", toggle))
    rows.append(("Diff file bar", f"{diff_host} .diff-file-bar", bar))
    # Pull request row: buildRow in the GitHub plugin's pulls-panel.js. The muted line under
    # the title is alone on its line, so it neither shares a baseline nor is a box.
    rows.append(
        (
            "Pull request row",
            ".github-pulls-row",
            el(
                "github-pulls-row",
                box("github-pull-state-icon"),
                text("github-pulls-title"),
                text("github-pulls-age age-min"),
                el("github-pulls-meta"),
            ),
        )
    )
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
    # The header's path fills the header's content box, so the baseline
    # group lands where centering put it at any header height.
    assert "min-height: 100%;" in _rule(styles, ".file-header > .file-header-path"), (
        "the header path no longer fills the header, so its text rides to the top"
    )
    # The diff bar's View file controls are centered boxes beside the toggle, so they
    # land on the path's baseline only at the path's own size.
    for selector in (".diff-file-path", ".diff-file-view"):
        assert "font-size: var(--nav-font-size);" in _rule(
            diff_css, f".metabrowser-diff-host {selector}"
        ), f"{selector} left the diff bar's one text size"


def test_disclosure_motion_is_one_recipe_everywhere() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    diff_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/styles.css").read_text(
        encoding="utf-8"
    )
    overview_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/folder/overview.css").read_text(
        encoding="utf-8"
    )
    for css, selector in (
        (styles, ".tree-children"),
        (diff_css, ".metabrowser-diff-host .diff-file-body"),
        (diff_css, ".metabrowser-diff-host .diff-fold-group"),
        (overview_css, ".folder-overview-panel-body"),
    ):
        rule = _rule(css, selector)
        assert "height var(--transition-fast)" in rule, f"{selector} lost the travel"
        assert "interpolate-size: allow-keywords" in rule, f"{selector} lost keyword sizing"
    for css, selector in (
        (styles, ".tree-children-collapsed"),
        (diff_css, ".metabrowser-diff-host .diff-file-body-collapsed"),
        (diff_css, ".metabrowser-diff-host .diff-fold-collapsed"),
        (overview_css, ".folder-overview-panel-body-collapsed"),
    ):
        rule = _rule(css, selector)
        assert "height: 0" in rule and "visibility: hidden" in rule, f"{selector} state drifted"
    # Class-driven collapse: the tree never toggles inline display.
    for name in ("app.js", "tree-expansion.js"):
        source = (STATIC / name).read_text(encoding="utf-8")
        assert "tree-children-collapsed" in source, f"{name} lost the collapse class"


def test_inline_change_stats_are_bold() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    diff_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/styles.css").read_text(
        encoding="utf-8"
    )
    for css, selector in (
        (diff_css, ".metabrowser-diff-host .diff-stat-add"),
        (diff_css, ".metabrowser-diff-host .diff-stat-del"),
        (styles, ".git-stat-add"),
        (styles, ".git-stat-del"),
    ):
        assert "font-weight: var(--weight-bold)" in _rule(css, selector), f"{selector} not bold"


def test_branch_chips_are_bold_and_square() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    rule = _rule(styles, ".git-ref")
    assert "font-weight: var(--weight-bold)" in rule
    assert "border-radius: var(--radius-tag)" in rule
    assert "--radius-tag:" in styles


def test_row_targets_share_the_hover_token() -> None:
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    diff_css = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/styles.css").read_text(
        encoding="utf-8"
    )
    assert "background: var(--hover-bg);" in _rule(styles, ".tree-item:hover")
    assert "background: var(--hover-bg);" in _rule(
        diff_css, ".metabrowser-diff-host .diff-file-bar:hover"
    )


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

    assert "### Navigational Row Collections" in design
    assert "test_nav_like_row_sets_share_the_vertical_keyboard_contract" in design
    for source, movement_helper in (
        (tree, "focusAndOpen"),
        (git, "moveCommitRowFocus"),
        (pulls, "nav.move("),
        (pull_files, "nav.moveFile("),
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
    sdk = (STATIC / "plugin-sdk.js").read_text(encoding="utf-8")
    git = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    diff = (REPO_ROOT / "src/metabrowser/builtin_plugins/diff/diff-view.js").read_text(
        encoding="utf-8"
    )

    assert "### Copyable Identifiers Use One Delegate" in design
    assert "test_copyable_identifiers_share_the_copy_contract" in design
    assert 'target.closest("[data-mb-copy]")' in sdk
    assert 'mode === "text"' in sdk and 'mode === "wrap"' in sdk
    assert 'data-mb-copy="text"' in app
    assert 'setAttribute("data-mb-copy", "text")' in diff
    assert 'data-mb-copy="text"' in git and "commit.id" in git
    assert "git-commit-revision-copy" in git
    for source in (app, diff, git):
        assert "data-copy-path" not in source, "a local path-copy contract reappeared"


def test_age_is_one_primitive_everywhere() -> None:
    """An age is an age: one formatter, one styling rule, and call sites
    that add positioning only."""
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    formatters = (STATIC / "formatters.js").read_text(encoding="utf-8")
    assert "function age(epochSeconds, options = {})" in formatters, (
        "the shared age primitive moved"
    )
    for name in ("git-panel.js", "app.js"):
        consumer = (STATIC / name).read_text(encoding="utf-8")
        assert "MetabrowserFormatters" in consumer and "age(" in consumer, (
            f"{name} must take its ages from the shared primitive"
        )
    tiers = _rule(
        styles, ":is(.age-live, .age-sec, .age-min, .age-hr, .age-day, .age-wk, .age-old)"
    )
    for declaration in ("color:", "font-weight:", "font-size:", "font-variant-numeric:"):
        assert declaration in tiers, f"the age primitive lost {declaration}"
    # A call site that restates color or weight has forked the vocabulary.
    graph_age = _rule(styles, ".git-graph-age")
    assert "color:" not in graph_age and "font-weight:" not in graph_age, (
        ".git-graph-age must carry positioning only"
    )


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
        for notation in (r"hsla?\(", r"rgba?\(", r"#[0-9a-fA-F]{3,8}\b"):
            found = re.findall(notation, text)
            assert not found, (
                f"{sheet.name} declares colors as {found[0]!r}; every color is written in oklch"
            )


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
    # The kind classes must reach the markup from the wire, not be guessed
    # in the browser.
    panel = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    views = (STATIC / "plugin-sdk-views.js").read_text(encoding="utf-8")
    assert "ref.is_trunk" in panel and "git-ref-trunk" in views


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
    assert "renderCommitSummary(detail, { compact: true })" in panel
    for component_part in (
        'const subjectClass = compact ? "git-commit-subject"',
        'class="git-commit-meta"',
        'class="git-commit-identity"',
        'class="git-commit-file-statuses"',
        'class="git-commit-change-stats"',
        'class="git-commit-refs"',
        'class="git-commit-body page-card"',
    ):
        assert panel.count(component_part) == 1, f"summary part drifted: {component_part}"
    change_stats = _rule(styles, ".git-commit-change-stats")
    stats_rows = _rule(styles, ".git-commit-file-statuses,\n.git-commit-line-stats")
    compact = _rule(styles, ".git-commit-summary-compact")
    meta = _rule(styles, ".git-commit-meta")
    summary_sha = _rule(styles, ".git-commit-sha")
    compact_subject = _rule(styles, ".git-commit-summary-compact .git-commit-subject")
    compact_meta = _rule(styles, ".git-commit-summary-compact .git-commit-meta")
    summary_age = _rule(styles, ".git-commit-summary .git-commit-age")
    summary_body = _rule(styles, ".git-commit-body")
    summary_refs = _rule(styles, ".git-commit-summary .git-ref")
    summary_lines = _rule(styles, ".git-commit-summary :is(.git-stat-add, .git-stat-del)")
    assert "max-width:" in compact
    assert "line-clamp:" in compact_subject
    assert "display: grid" in change_stats
    assert "white-space: nowrap" in change_stats
    assert "display: inline-flex" in stats_rows
    assert "font-family: var(--prose-sans-font)" in summary_body
    assert "font-size: var(--document-body-font-size)" in summary_body
    assert "white-space: pre-wrap" in summary_body
    for rule in (
        meta,
        compact_subject,
        compact_meta,
        summary_age,
        summary_lines,
    ):
        assert "font-size: var(--body-font-size)" in rule
        assert "font-size: var(--ui-small-font-size)" not in rule
        assert "font-size: var(--tooltip-detail-font-size)" not in rule
    assert "font-size: var(--ui-small-font-size)" in summary_refs
    # The revision is the documented exception: monospace at body size
    # renders optically larger than the sans beside it, so the sha sits
    # one step down the ramp. See "Git Commit Summary" in the design
    # system.
    assert "font-family: var(--font-mono)" in summary_sha
    assert "font-size: var(--nav-font-size)" in summary_sha
    assert "noninteractive copy glyph" in doc


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
    assert 'document.addEventListener("focusin", hideTooltip)' in app
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
    assert 'includeToc: "off"' in readme
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "Overview renders the README at the same measure" in doc


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

    return [STATIC / "styles.css", *sorted((REPO_ROOT / BUILTIN_PLUGINS).glob("*/*.css"))]


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
    assert "outline: 2px solid var(--link)" in _rule(styles, ".tab-btn:focus-visible")
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
    # One step below the structured view's mono, in em so it follows that view's size.
    ("structured/styles.css", ".tok-meta"): "relative to the row it annotates",
}
_TYPE_SCALE_VALUE = re.compile(r"var\(--[a-z0-9-]+\)")


def _sheet_name(sheet: Path) -> str:
    if sheet.parent == STATIC:
        return sheet.name
    return f"{sheet.parent.name}/{sheet.name}"


def test_font_sizes_come_from_the_type_scale() -> None:
    """No literal font size at a use site, as "Type Scale" says, or a reason named above.

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
    "agent_log/index.js": "marks a chip of its groupHtml in place",
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
    wrapped_rest = styles.index('.chip-group[data-layout="wrap"] > .chip {')
    assert styles.index(".chip-group > .chip:hover {") > max(chip_rest, wrapped_rest)
    # One focus ring. A fill cannot be the signal, since a checked segment's would hide it.
    ring = "outline: 2px solid var(--link)"
    for selector in (".chip:focus-visible", ".menu-seg:focus-visible"):
        rule = _rule(styles, selector)
        assert ring in rule, f"{selector} lost the focus ring"
        assert "outline-offset: -2px" in rule, f"{selector} moved the focus ring"
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
    diff = (plugins / "diff/diff-view.js").read_text(encoding="utf-8")
    assert '"fold-expander diff-fold-control"' in diff
    page = (plugins / "github/pull-page.js").read_text(encoding="utf-8")
    headings = re.findall(r'h\("h2", \{([^}]+)\}', page)
    assert headings and len(headings) == page.count('h("h2",')
    assert all('class: "section-heading"' in attributes for attributes in headings)
    assert 'h("summary", { class: "fold-expander" }' in page
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


def _oklch_channels(value: str) -> tuple[float, float, float]:
    """Lightness (0 to 1), chroma, and hue of one `oklch(L% C H)` declaration."""

    found = re.fullmatch(r"oklch\(([\d.]+)% ([\d.]+) ([\d.]+)\)", value.strip())
    assert found is not None, value
    return float(found[1]) / 100, float(found[2]), float(found[3])


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
    """Each state is one color seen against two backgrounds, legible on both.

    `test_themed_colors_keep_their_hue` reads the shell's stylesheet; these tokens are the
    plugin's, as a domain's tokens are (docs/design-system.md, "Token Layers"). A state's
    badge sets its name in this color, so it is held to the 4.5:1 of text, on the surface the
    page's header sits on and on the panel's.
    """

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    light_block, dark_block = _theme_blocks()
    # The plugin's own theme rules, parsed: a comment or another rule's brace cannot move them.
    rules = _rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css")
    plugin_light = next(body for selector, body in rules if selector == ":root")
    plugin_dark = next(body for selector, body in rules if selector == '[data-theme="dark"]')
    assert "--sidebar-bg" in styles
    for name in ("open", "draft", "merged", "closed"):
        token = f"--github-pull-{name}"
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
    # One Chevron, One Row Contract: the row height, the hover, and a row's own focus ring.
    row = github[".github-pulls-row"]
    assert row["min-height"] == "var(--ui-row-height)"
    assert github[".github-pulls-row:hover"]["background"] == "var(--hover-bg)"
    assert github[".github-pulls-row.selected"]["background"] == "var(--highlight-bg)"
    assert github[".github-pulls-row:focus-visible"]["outline"] == "2px solid var(--link)"
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
    # A row and its page match: one state's icon, from one module.
    assert "pullStateIcon(" in panel and "pullStateIcon(" in page
    assert 'aria-label", PULL_STATES[state].label' in state
    # Ages, filters, buttons, and the spinner are the shell's.
    assert "mb.formatAge(" in panel
    assert "controls.groupHtml(" in panel
    assert 'class: "github-pulls-connection"' in panel
    assert 'class: "btn github-pulls-reload"' in panel
    assert '"mb-delayed-loading"' in panel
    assert 'class: "spinner spinner-sm"' in panel
    assert 'class: "btn github-pulls-more"' in panel
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
    assert 'class: "github-pull-file-name mb-refreshing-text"' in files
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
    assert 'h("span", { class: "github-pulls-title" }, [row.title])' in panel
    assert 'h("span", { class: "github-pull-stack-member-title" })' in page
    titles = (".github-pulls-title", ".github-pull-stack-member-title")
    for title in titles:
        assert github[title]["color"] == "var(--text)", title
        assert github[title]["font-weight"] == "var(--weight-bold)", title
    for selector, declarations in _rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"):
        if selector not in titles and any(title in selector for title in titles):
            assert not {"color", "font-weight"} & declarations.keys(), selector
    # The page's heading and a search result's label already are; the number beside a
    # title keeps its regular weight.
    assert 'class: "page-heading github-pull-title' in page
    shell = dict(_rules_of(STATIC / "styles.css"))
    assert shell[".page-heading"]["font-weight"] == "var(--weight-bold)"
    label = shell[".search-palette-label"]
    assert (label["color"], label["font-weight"]) == ("var(--text)", "var(--weight-bold)")
    assert github[".github-pull-number"]["font-weight"] == "var(--weight-normal)"
    for number in (".github-pulls-number", ".github-pull-stack-member-number"):
        assert "font-weight" not in github[number], number


def test_the_pull_request_page_carries_the_shells_primitives() -> None:
    """What "The Pull Request Page" says it reuses is what its markup says."""

    page = (REPO_ROOT / BUILTIN_PLUGINS / "github/pull-page.js").read_text(encoding="utf-8")
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "## The Pull Request Page" in doc
    assert "test_the_pull_request_page_carries_the_shells_primitives" in doc
    # Branch names and file paths are chrome: no `<code>` for either.
    assert 'h("code"' not in page
    assert "mb.refChip(" in page and 'kind: "remote"' in page
    # One age, not a timestamp at each call site.
    assert "mb.formatAge(" in page
    assert page.count("mb.formatTimestamp(") == 1, "the exact time belongs in the age's tooltip"
    assert "`file-header-badge github-pull-badge github-pull-${kind}`" in page
    assert 'class: "notice github-pull-notice"' in page
    github = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"))
    # The heading scales the shared glyph to its own type and wraps text in its own track.
    assert 'class: "page-heading github-pull-title' in page
    assert github[".github-pull-title-with-state"]["grid-template-columns"] == "auto minmax(0, 1fr)"
    title_icon = github[".github-pull-title > .github-pull-state-icon"]
    assert (title_icon["width"], title_icon["height"]) == ("1em", "1lh")
    title_glyph = github[".github-pull-title > .github-pull-state-icon svg"]
    assert (title_glyph["width"], title_glyph["height"]) == ("1em", "1em")
    # Links take the link token rather than the browser's blue.
    assert github[".github-pull-header a"]["color"] == "var(--link)"
    # A GitHub action (View on GitHub, a check's action on GitHub, a conversation commit
    # hash) is quiet: muted at rest, the link token on hover and focus, at its row's size.
    for place in (".github-pull-header", ".github-pull-checks", ".github-pull-commit"):
        action = f"{place} .github-pull-external-action"
        assert github[action] == {"color": "var(--muted)"}, action
        for state in (":hover", ":focus-visible"):
            assert github[action + state]["color"] == "var(--link)", action + state
    assert page.count('"github-pull-external-action"') == 2, "the header's and a check's"
    assert '"github-pull-commit-id git-commit-sha github-pull-external-action"' in page
    # A check's own site is an ordinary link, so it never reads as the description after it.
    assert github[".github-pull-checks a"]["color"] == "var(--link)"
    # A hash matches its 12 px row; the ramp's next step below is the 10 px micro size.
    assert github[".github-pull-commit"]["font-size"] == "var(--ui-small-font-size)"
    assert github[".github-pull-commit .git-commit-sha"]["font-size"] == (
        "var(--ui-small-font-size)"
    )
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
    assert 'freshnessLine.classList.toggle("mb-refreshing", busy);' in page
    assert 'freshnessLine.setAttribute("aria-busy", "true");' in page
    assert 'status.setAttribute("aria-busy"' not in page, "the status line's controls stay usable"
    assert '"recent-loading github-pull-loading github-pull-section-loading"' in page
    assert github[".github-pull-section-loading"] == {"height": "calc(var(--ui-row-height) * 3)"}
    # The author, action, and relative age share one prose size and baseline.
    assert github[".github-pull-card-head"]["font-size"] == "var(--body-font-size)"
    age = github[".github-pull-card-head .github-pull-age"]
    assert (age["font-size"], age["line-height"]) == ("var(--body-font-size)", "inherit")
    assert ".github-pull-card-head .github-pull-author" not in github
    identity = github[".github-pull-identity"]
    assert (identity["align-items"], identity["vertical-align"]) == ("baseline", "baseline")
    assert github[".github-pull-avatar"]["align-self"] == "center"
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


# A serif face, named directly or through the token KPress reads it from.
_SERIF = re.compile(r"--kpress-(?:host-)?font-prose\b|--app-serif-system\b|(?<!sans-)\bserif\b")


def test_serif_is_only_for_documents() -> None:
    """Chrome and messages are sans; serif is a committed document's, as "Serif Is for Documents" says.

    A pull request's description and comments read in the serif of a Markdown file, so a
    conversation about the content looked like part of it.
    """

    styles = STATIC / "styles.css"
    for path in sorted([*STATIC.glob("*.css"), *(REPO_ROOT / BUILTIN_PLUGINS).glob("*/*.css")]):
        for selector, declarations in _rules_of(path):
            family = declarations.get("font-family", "")
            assert _SERIF.search(family) is None, f"{path.name} {selector} sets a serif: {family}"
            for name, value in declarations.items():
                if path == styles and selector.startswith(("html[data-", ":root")):
                    continue  # the reading font and the font sets, which only documents read
                if name == "--kpress-host-font-prose":
                    assert value == "var(--prose-sans-font)", (
                        f"{path.name} {selector} points the prose face at {value}"
                    )
    assert dict(_rules_of(styles))['html[data-prose-font="sans"]']["--doc-char-advance"] == (
        "var(--sans-char-advance)"
    )
    # The pull request page uses the sans prose face.
    page = dict(_rules_of(REPO_ROOT / BUILTIN_PLUGINS / "github/styles.css"))[".github-pull"]
    assert page["--kpress-host-font-prose"] == "var(--prose-sans-font)"
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "### Serif Is for Documents" in doc
    assert "test_serif_is_only_for_documents" in doc


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
            color = _declared(block, f"--git-status-{role}")
            if role == "renamed":
                color = _declared(block, "--git-ref-local")
                parts = color.removeprefix("oklch(").removesuffix(")").split()
                color = f"oklch({float(parts[0]) * 100}% {parts[1]} {parts[2]})"
            for ground in ("--bg", "--sidebar-bg", "--hover-bg"):
                assert _contrast(color, _declared(block, ground)) >= 4.5
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


def test_branch_copy_plate_has_readable_interactive_ink() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "color: var(--text)" in _rule(css, ".git-ref-copy:is(:hover, :focus-visible)")
    rules = dict(_rules_of(STATIC / "styles.css"))
    assert rules[".git-ref-copy-layer > .git-ref-copy"]["color"] == "var(--git-ref-copy-ink)"


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
    # The anchors layer 3 declares: the file header, the folder header, the commit heading.
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert app.count('class="file-header" data-kbd-badge-anchor') == 1
    assert app.count('class="file-header folder-header" data-kbd-badge-anchor') == 1
    git_panel = (STATIC / "git-panel.js").read_text(encoding="utf-8")
    assert '<div class="git-commit-header" data-kbd-badge-anchor>' in git_panel


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


def test_hover_revealed_targets_show_while_keys_are_revealed() -> None:
    """A target that appears only on hover appears for the reveal, so its badge is not alone.

    Both copy buttons are `.icon-btn-reveal`, transparent until hover or focus; a badge inside
    one would inherit that, and a badge beside one would point at nothing. A target carries
    `aria-keyshortcuts` while attached, which no other reveal-on-hover button does, and the
    reveal restores `pointer-events` with the opacity, as every reveal trigger must
    ("Reveal on Hover Keeps Keyboard Reach").
    """

    revealed = _first_rules()["[data-key-reveal] .icon-btn-reveal[aria-keyshortcuts]"]
    assert revealed == {"opacity": "1", "pointer-events": "auto"}
    writes = re.compile(r"""setAttribute\(\s*"aria-keyshortcuts"|aria-keyshortcuts=""")
    writers = {
        source.name for source in _browser_sources() if writes.search(source.read_text("utf-8"))
    }
    # The registry for targets; Help for the strip's buttons; the overlay for a close button.
    assert writers == {"keyboard-shortcuts.js", "keyboard-help.js", "overlay-layer.js"}, writers
    for name in writers - {"keyboard-shortcuts.js"}:
        assert "icon-btn-reveal" not in (STATIC / name).read_text(encoding="utf-8"), name


def test_key_reveal_fades_in_hides_at_once_and_respects_reduced_motion() -> None:
    """The badges and the strip fade in over the short interval, appear at once under reduced
    motion, and go at once: they leave the document when the reveal ends, so nothing animates
    them out."""

    styles = (STATIC / "styles.css").read_text(encoding="utf-8")
    rules = _first_rules()
    for selector in (".kbd-badge", ".nav-shortcut-reveal"):
        assert rules[selector]["animation"] == "key-reveal-in var(--transition-fast)", selector
    keyframes = re.search(r"@keyframes key-reveal-in \{(.*?)\n\}", styles, re.DOTALL)
    assert keyframes is not None
    assert set(re.findall(r"([a-z-]+):", keyframes[1])) == {"opacity"}, "opacity only"
    assert re.search(r"\bfrom \{\s*opacity: 0;\s*\}", keyframes[1]), "from transparent, to rest"
    reduced = _at_rule_rules("@media (prefers-reduced-motion: reduce)")
    for selector in (".kbd-badge", ".nav-shortcut-reveal"):
        assert (selector, {"animation": "none"}) in reduced, f"reduced motion keeps {selector}"
    assert (
        "[data-key-reveal] .icon-btn-reveal[aria-keyshortcuts]",
        {"transition": "none"},
    ) in reduced
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
