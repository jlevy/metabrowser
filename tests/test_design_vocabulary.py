"""Design-vocabulary agreements the stylesheet cannot state for itself.

Each check pins one cross-file agreement from ``docs/design-system.md``:
the disclosure chevron is one glyph everywhere it appears, row-like
activation targets share one height token, and their hover is the one
hover token. A failure here means a surface forked the vocabulary.
"""

from __future__ import annotations

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
    bar = el("diff-file-bar", toggle, box("icon-btn icon-btn-reveal diff-file-copy"))
    el("content-body metabrowser-diff-host", el("diff-file", bar))
    rows.append(("Diff file bar", f"{diff_host} .diff-file-toggle", toggle))
    rows.append(("Diff file bar", f"{diff_host} .diff-file-bar", bar))
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
    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "### Row Text Shares a Baseline" in doc, "the row baseline rule lost its documentation"
    section = doc.split("### Row Text Shares a Baseline", 1)[1].split("\n### ", 1)[0]
    rules = _baseline_rules()
    for label, row_rule, row in _baseline_rows():
        assert f"| {label}" in section, f"{label} is missing from the design-system table"
        css = diff_css if row_rule.startswith(".metabrowser-diff-host") else styles
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

    assert "### Navigational Row Collections" in design
    assert "test_nav_like_row_sets_share_the_vertical_keyboard_contract" in design
    for source, movement_helper in (
        (tree, "focusAndOpen"),
        (git, "moveCommitRowFocus"),
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
    assert "function age(epochSeconds)" in formatters, "the shared age primitive moved"
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
    assert "ref.is_trunk" in panel and "git-ref-trunk" in panel


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
        'class="git-commit-subject"',
        'class="git-commit-meta"',
        'class="git-commit-identity"',
        'class="git-commit-file-statuses"',
        'class="git-commit-change-stats"',
        'class="git-commit-refs"',
        'class="git-commit-body"',
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
    assert "font-family: var(--font-sans)" in summary_body
    assert "font-size: var(--body-font-size)" in summary_body
    assert "white-space: pre-wrap" in summary_body
    for rule in (
        meta,
        compact_subject,
        compact_meta,
        summary_age,
        summary_refs,
        summary_lines,
    ):
        assert "font-size: var(--body-font-size)" in rule
        assert "font-size: var(--ui-small-font-size)" not in rule
        assert "font-size: var(--tooltip-detail-font-size)" not in rule
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
    """A README reads at the same measure in Overview as on its own.

    The two surfaces render the same file through the same renderer, so the
    reader compares them directly and any difference reads as a bug. Three
    things have to agree for that to hold, and each one broke it on its own:

    * the band boundaries, which must be the *same* container. Overview used
      to query its own host, which is the preview pane minus its padding, so
      the two crossed 75rem about 25px apart and there was a band of window
      widths where the README's text jumped while every other panel stayed.
    * the wide column, which is KPress's content track (the measure plus its
      2.5rem insets), not the measure alone. Sized to the measure, the column
      is right and the text inside it is 5rem short, because KPress still pads
      the prose for a track it is no longer in.
    * the narrow inset, which must equal the article padding Overview zeroes,
      or the text runs short by twice the difference.
    """

    css = (REPO_ROOT / "src/metabrowser/builtin_plugins/folder/overview.css").read_text(
        encoding="utf-8"
    )
    # One container names the bands for both surfaces.
    assert "@container kpress-doc (min-width: 75rem)" in css
    assert "@container kpress-doc (max-width: 47.99rem)" in css
    assert "@container (min-width:" not in css, "an unnamed band drifts from KPress's"
    assert "@container (max-width:" not in css, "an unnamed band drifts from KPress's"

    # The wide column is the track, not the measure.
    assert "--folder-overview-wide-card-width: calc(" in css
    wide = css[css.index("--folder-overview-wide-card-width:") :][:200]
    assert "var(--doc-measure)" in wide and "--folder-overview-wide-toc-inset" in wide
    # Both of KPress's measure caps are lifted, never one: lifting the outer
    # alone leaves the inner centred at the measure, which reads as a wide left
    # margin with the content spilling past its right edge.
    assert ".folder-overview-panel-document > .folder-overview-panel-body > .kpress," in css
    assert ".folder-overview-panel-document .kpress-doc-layout {" in css

    # The narrow inset replaces the article padding Overview drops.
    assert "--folder-overview-narrow-document-gutter: 0.5rem" in css
    assert "padding-inline: 0" in css

    doc = (REPO_ROOT / "docs/design-system.md").read_text(encoding="utf-8")
    assert "Overview renders the README at the same measure" in doc, (
        "the rule belongs in the design system, not only in the stylesheet"
    )
