"""Chrome whose box is decided at first paint and does not depend on later data.

Geometry is the browser's, so these pin the rules that decide it: the slot a region
keeps while its content is absent, in line units where text sets the height, so the
same rule holds in WebKit, whose font metrics differ from Chrome's. Each region named
here moved the content beside or below it when it appeared or disappeared; the
measurements are in explorations/performance-loop/design-rule-measurements.md and the
rules' comments.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from tests.required_tools import require_node

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC = REPO_ROOT / "src" / "metabrowser" / "static"


def _css() -> str:
    return (STATIC / "styles.css").read_text(encoding="utf-8")


def _rule(css: str, selector: str) -> str:
    match = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match is not None, f"selector not found: {selector}"
    return match.group(1)


def _function(source: str, name: str) -> str:
    """A function declared at any depth, up to the closing brace at its own indent."""

    match = re.search(rf"(?m)^( *)(?:async )?function {name}\(", source)
    assert match is not None, name
    end = source.index(f"\n{match.group(1)}}}\n", match.start())
    return source[match.start() : end]


def test_both_panes_keep_their_scrollbar_gutter() -> None:
    """Scrollbars are classic, so a pane that starts overflowing narrowed by 11 px."""

    css = _css()
    assert "*::-webkit-scrollbar {" in css, "scrollbars are no longer classic; revisit this"
    for selector in (".tree-content", ".preview-pane"):
        assert "scrollbar-gutter: stable;" in _rule(css, selector), selector


def test_every_tab_fills_one_toolbar_slot_at_one_height() -> None:
    """The top of the navigation is one toolbar slot, filled by the tab in front.

    The Files filters, the Commits tally, and the Pulls filters stand in one another's
    place at one height while each is one line, in line units, so what is under the slot
    starts at one y on every tab. The filter bar alone hid on Commits and Pulls and moved
    the panel 37 px. In a pane too narrow for a toolbar's line, it wraps rather than being
    cut or scrolled, and the slot grows by the lines it adds (`.nav-toolbar-row`); Chrome
    measures that at every pane width (tests/dom/nav-toolbar-wrap.mjs).
    """

    css = _css()
    assert "--nav-toolbar-line-height: var(--chip-height);" in css
    assert "--nav-toolbar-gap: 6px;" in css
    assert (
        "--nav-toolbar-height: calc(var(--nav-toolbar-line-height) + 2 * "
        "var(--nav-toolbar-gap) + 1px);"
    ) in css
    assert "1.5 *" in css[css.index("--chip-height: calc(") :][:120], "chips are in line units"
    toolbar = _rule(css, ".nav-toolbar")
    # One line's height at least, its lines' when it wraps; never a line it scrolls along.
    assert "min-height: var(--nav-toolbar-height);" in toolbar
    assert "white-space" not in toolbar and "overflow" not in toolbar
    assert ".nav-toolbar::-webkit-scrollbar" not in css
    assert "min-height: var(--nav-toolbar-height);" in _rule(css, ".nav-filter-bar")
    assert "display: none;" in _rule(css, ".nav-filter-bar[hidden],\n.nav-toolbar[hidden]")
    assert ".nav-filter-bar[inert]" not in css
    # The rows of controls wrap between them, a line and a gap at a time, every control one
    # line tall; in the slot a row keeps the gap above and below its lines.
    row = _rule(css, ".nav-toolbar-row")
    assert "flex-wrap: wrap;" in row and "gap: var(--nav-toolbar-gap);" in row
    assert "min-width: 0;" in row
    assert "min-block-size: var(--nav-toolbar-line-height);" in _rule(css, ".nav-toolbar-row > *")
    assert "max-block-size: var(--nav-toolbar-line-height);" in _rule(
        css, ".nav-toolbar-row > :not(.chip-group)"
    )
    in_slot = _rule(css, ".nav-toolbar > .nav-toolbar-row")
    assert "padding-block: var(--nav-toolbar-gap);" in in_slot and "flex: 1 1 auto;" in in_slot
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert '<div class="nav-filter-bar-main nav-toolbar-row">' in app
    panel = (GITHUB / "pulls-panel.js").read_text(encoding="utf-8")
    assert 'filters.classList.add("nav-toolbar-row");' in panel
    # The Commits tally is a metadata line, and one line of that is the slot's height, so in
    # the slot it keeps its own padding above and below and gives up only its inset and rule;
    # it wraps as the line does.
    tally = _rule(css, ".nav-toolbar > .nav-metadata")
    assert "padding-inline: 0;" in tally and "border-bottom: none;" in tally
    assert "padding-block" not in tally and "min-height" not in tally
    assert "flex-wrap" not in tally
    pulls = _rule(_github_css(), ".github-pulls-filters:where(.nav-toolbar > *)")
    assert "position: static;" in pulls and "padding-inline: 0;" in pulls
    assert "flex:" not in pulls and "padding-block" not in pulls
    tabs = (STATIC / "main-tabs.js").read_text(encoding="utf-8")
    activate = _function(tabs, "activateNavPanel")
    assert 'document.querySelectorAll("[data-nav-toolbar]")' in activate
    assert ".dataset.navToolbar !== panelId" in activate


def test_the_files_tree_holds_its_first_paint_until_its_toolbar_is_filled() -> None:
    """The shell ships the Files toolbar one line tall around the pending placeholder, and
    app.js fills it. In a pane too narrow for its row the filled bar wraps, and the tree
    under it, which the shell paints before any script runs, moved 30 px at the narrowest
    pane, its rows with it when they were shown first (mb-a5pa, mb-kiqm). So the tree is
    hidden while the bar holds the placeholder, unless an alert was written into it or the
    bar is behind another tab's toolbar, and app.js fills the bar just before it draws the
    tree's first rows, so no row waits. The hold ends at a bound, so a bar that is never
    filled does not hide the tree for good; its measurement is beside the rule.
    tests/test_files_totals_stable_chrome.py measures that no load shifts and that the
    tree shows at the bound when filter-controls.js fails.
    """

    css = _css()
    hold = _rule(
        css,
        ".nav-filter-bar:not([hidden]):has(.tally-pending) ~ .tree-content:not(:has(> "
        '[role="alert"]))',
    )
    assert "visibility: hidden;" in hold
    # The bound: the quiet period's own keyframes show the tree a second in.
    assert "animation: mb-delayed-loading-reveal 0s linear 1s forwards;" in hold
    reveal = re.search(r"@keyframes mb-delayed-loading-reveal \{\s*to \{([^}]*)\}", css)
    assert reveal is not None and "visibility: visible;" in reveal.group(1)
    # The placeholder the hold waits on is the one the server puts in the bar, and the bar
    # app.js draws replaces it.
    server = (REPO_ROOT / "src" / "metabrowser" / "server.py").read_text(encoding="utf-8")
    assert "pending_tally = '<span class=\"count tally-pending\"></span>'" in server
    assert 'data-nav-toolbar="files"{filter_bar_behind}>{filter_bar_content}</div>' in server
    # A page with the branch and tag chooser ships the row, the chooser leading it and the
    # placeholder after it, which the hold finds at any depth; the filled bar has none.
    assert (
        "f'<div class=\"nav-filter-bar-main nav-toolbar-row\">{source_ref_selector}'\n"
        '        f"{pending_tally}</div>"'
    ) in server
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "bar.innerHTML = main + drawer;" in _function(app, "renderNavFilterBar")
    # Filled in the task that draws the first rows, before them, so the rows are never
    # held and a landed row is scrolled to under the settled bar.
    assert "\nrenderNavFilterBar();\nrenderInitialTreeRows();\n" in app


def test_the_shortcut_strip_keeps_one_row_until_it_is_filled() -> None:
    """The strip always holds Help once filled, so before then it holds a row's height."""

    rule = _rule(_css(), ".nav-shortcut-hints[hidden]")
    assert "visibility: hidden;" in rule
    assert "display: none" not in rule
    # A keycap is 1.5 lines of the strip's own type, so the reservation is in line units.
    assert re.search(r"min-height: calc\([^;]*1\.5em\)", rule), rule
    keycap = _rule(_css(), ".kbd")
    assert "line-height: 1.5;" in keycap
    assert "font-size: var(--kbd-font-size);" in keycap
    assert "--kbd-font-size: var(--ui-small-font-size);" in _css()
    assert "font-size: var(--kbd-font-size);" in _rule(_css(), ".nav-shortcut-hints")


def _render_file() -> str:
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    render = app[app.index("async function renderFile(") :]
    return render[: render.index('"renderFile:mount"')]


def test_every_file_has_a_view_tab_bar() -> None:
    """A kind with one view, or none, starts its content where a kind with two does."""

    render = _render_file()
    # Only the view keys wait for a second view; the bar itself does not. The one test of
    # the length past "any views" is the key gate, and the gate decides only the key.
    lengths = re.findall(r"views\.length\s*(?:[<>]=?|[!=]==)\s*\d+", render)
    assert lengths == ["views.length > 0", "views.length > 1"], lengths
    assert "var keyedBar = views.length > 1;" in render
    assert re.findall(r"[^\n]*\bkeyedBar\b[^\n]*", render) == [
        "          var keyedBar = views.length > 1;",
        '              (keyedBar ? viewKey : "") +',
    ], "keyedBar gates something besides the key"
    assert 'html += \'<div class="tab-bar" role="tablist">\';' in render
    assert '<span class="tab-btn tab-slot">&nbsp;</span>' in render
    slot = _rule(_css(), ".tab-slot")
    # It takes a tab's padding and type from .tab-btn, and a button's line-height.
    assert "visibility: hidden;" in slot
    assert "line-height: normal;" in slot


def test_only_a_bar_of_two_views_carries_their_keys(tmp_path: Path) -> None:
    """A lone view's tab has no other view to switch to, so it publishes no key.

    The server already strips such a key (``keymap.live_view_keys``), so no page it serves
    can show the gate; this runs renderFile's own lines for the bar, verbatim, on a list of
    one view and a list of two, each declaring a key.
    """

    render = _render_file()
    start = render.index("          var keyedBar = views.length > 1;")
    end = render.index('          html += "</div>";\n', start) + len('          html += "</div>";')
    script = tmp_path / "view-tab-bar.js"
    script.write_text(
        "const esc = (text) => String(text);\n"
        "const viewMetaAttrs = () => '';\n"
        "const lists = [\n"
        "  [{ id: 'source', label: 'Source', key: 's' }],\n"
        "  [{ id: 'rendered', label: 'Document', key: 'd' }, { id: 'source', label: 'Source', key: 's' }],\n"
        "];\n"
        "for (const views of lists) {\n"
        "  const initialActiveView = views[0];\n"
        "  let html = '';\n"
        f"{render[start:end]}\n"
        "  console.log(html);\n"
        "}\n",
        encoding="utf-8",
    )
    one, two = subprocess.run(
        [require_node(), str(script)], capture_output=True, text=True, timeout=30, check=True
    ).stdout.splitlines()
    assert one.startswith('<div class="tab-bar" role="tablist"><button class="tab-btn active"')
    assert 'role="tab" aria-selected="true" data-tab="source"' in one
    assert "data-view-key" not in one
    assert re.findall(r'data-view-key="(\w)"', two) == ["d", "s"]


def test_print_takes_no_slot_in_the_header_or_the_document() -> None:
    """The print button left the header, and in the document's card it reserves nothing.

    In the header it came and went with the view, so it kept a hidden slot: toggling
    `hidden` alone had moved the size label 32 px on a view switch. It is now in the
    rendered document's card (mb-07a1), absolute in the card's padding, so it has no slot
    to keep; tests/dom/document-print-chrome.mjs measures that nothing moves.
    """

    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "file-header-print" not in app
    assert "updatePrintButton" not in app
    assert ".file-header-print" not in _css()
    markdown = (STATIC.parent / "builtin_plugins" / "markdown" / "markdown.css").read_text(
        encoding="utf-8"
    )
    rule = _rule(markdown, "  .metabrowser-markdown-document .metabrowser-print-indicator")
    assert "position: absolute;" in rule


def test_a_runs_status_badge_is_as_wide_as_its_widest_label() -> None:
    """Live becomes Run ended in place; the badge's slot is the widest label's from the start.

    A sizer of every label the badge can show sits beside it in a one-column grid, at no
    height. As a pseudo-element of the inline-block badge the sizer was laid beside the
    label, and Run ended arriving widened the badge and moved the header. The header Chrome
    session checks that nothing moves (tests/dom/github-pull-header-chrome.mjs).
    """

    css = _css()
    # The view header draws the badge (view-header.js); the live tail in app.js relabels it.
    header = (STATIC / "view-header.js").read_text(encoding="utf-8")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    labels = set(re.findall(r'badge-(?:running|live|completed|failed)">([^<]+)<', header))
    labels |= set(re.findall(r'badge\.textContent = "([^"]+)"', app))
    assert labels == {"Running", "Live", "Done", "Failed", "Run ended"}, labels
    sizers = re.search(r"const RUN_STATUS_SIZERS = \[([^\]]*)\]", header)
    assert sizers is not None
    assert set(re.findall(r'"([^"]+)"', sizers.group(1))) == labels
    render = _function(header, "renderBadges")
    assert (
        '<span class="file-header-badge-slot">${statusBadge}${RUN_STATUS_SIZERS}</span>' in render
    )
    slot = _rule(css, ".file-header-badge-slot")
    assert "display: inline-grid;" in slot and "flex-shrink: 0;" in slot
    assert "justify-self: stretch;" in _rule(css, ".file-header-badge-slot > .file-header-badge")
    sizer = _rule(css, ".file-header-badge-slot > .file-header-badge-sizer")
    assert "block-size: 0;" in sizer and "visibility: hidden;" in sizer
    assert "::after" not in css.split(".badge-completed {")[0].split("/* A run's status badge")[-1]


GITHUB = REPO_ROOT / "src" / "metabrowser" / "builtin_plugins" / "github"


def _github_css() -> str:
    return (GITHUB / "styles.css").read_text(encoding="utf-8")


def test_a_title_holds_two_lines_and_never_more() -> None:
    """A pull request's title was 1 to 3 lines, 30 px each, under the tab bar's feet.

    It is cut short at two lines. Only the title while the record is on its way holds two,
    the most a record's title takes, so a record lands moving the tab bar up a line, if at
    all, never down. A record's title is its own one or two lines, and the author's line is
    `--page-title-gap` under it: a held second line stood between a one-line title and its
    author, 36.5 px of space where a two-line title had 6 (mb-wcbc). The commit view's
    subject is the same heading, and holds no line either.
    """

    css = _github_css()
    assert not re.search(r"(?m)^\.github-pull-title\s*\{", css)
    assert "min-height" not in _rule(css, ".github-pull-title-with-state")
    clamp = _rule(css, ".github-pull-title-text")
    assert "-webkit-line-clamp: 2;" in clamp and "line-clamp: 2;" in clamp
    assert "overflow: hidden;" in clamp
    cold = _rule(css, ".github-pull-title:not(.github-pull-title-with-state)")
    assert "min-height: 2lh;" in cold
    assert "-webkit-line-clamp: 2;" in cold and "line-clamp: 2;" in cold
    assert not re.search(r"(?m)^\.git-commit-subject\.page-heading\s*\{", _css())


def test_the_state_row_is_one_line_held_by_a_strut() -> None:
    """The author and the sentence share one line at a chip's height; the branches, the next."""

    css = _github_css()
    meta = _rule(css, ".github-pull-meta")
    assert "flex-wrap: nowrap;" in meta and "white-space: nowrap;" in meta
    details = _rule(css, ".github-pull-meta-details")
    assert "min-width: 0;" in details and "overflow: hidden;" in details
    # The branches are on a line of their own under the sentence (mb-fon5), a line tall
    # while no record is shown too.
    branches = _rule(css, ".github-pull-branches")
    assert "flex-wrap: nowrap;" in branches and "white-space: nowrap;" in branches
    assert "min-width: 0;" in branches and "overflow: hidden;" in branches
    assert "min-height: 1lh;" in branches
    # A chip is a grid item of the merge group, whose floor keeps the names legible; a
    # width of the chip's own would overflow the group's track rather than hold it. The
    # header sets nothing on its chips at all: `.git-ref` alone sizes a chip
    # (test_branch_chips_have_one_size in test_design_vocabulary.py).
    assert ".github-pull-meta .git-ref" not in css
    assert ".github-pull-branches .git-ref" not in css
    # The sentence gives way first.
    action = _rule(css, ".github-pull-meta-details > .github-pull-action")
    assert "flex: 0 1000 auto;" in action and "min-width: 0;" in action
    # The author gives way next, down to its avatar's box and a little of the name (review E2
    # on #370). The box is there for every author in the header, the person glyph in it where
    # there is no avatar (mb-nunw), so the floor always counts it.
    author = _rule(css, ".github-pull-meta-details > .github-pull-identity")
    assert "flex: 0 100 auto;" in author and "overflow: hidden;" in author
    floor = "min-width: calc(var(--actor-avatar-size) + var(--actor-identity-gap) + 1.75em);"
    assert floor in author
    assert ":has(.github-pull-avatar)" not in css
    name = _rule(css, ".github-pull-meta-details .github-pull-author")
    assert "min-width: 0;" in name and "text-overflow: ellipsis;" in name
    strut = _rule(css, ".github-pull-stack-strut")
    assert "width: 0;" in strut and "visibility: hidden;" in strut
    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    assert "btn github-pull-stack-trigger github-pull-stack-strut" in page
    # The author's row ends in the stack's slot, which holds a strut until a chip arrives
    # (mb-cf0l): the sentence keeps its start, and is only cut short at its end. On the row
    # that also held the merge, a late chip took its width from the sentence and the merge
    # (review E3 on #370). The freshness note sits between them, after the sentence, the two
    # the row's lead (mb-ne91).
    assert "[\n    stateLead,\n    stackColumn,\n  ]);" in page
    assert 'h("span", { class: "github-pull-meta-lead" }, [stateDetails, freshnessNote]);' in page
    # The state badge leads the row of ages (mb-4ydo), one line in every state.
    opened = _rule(css, ".github-pull-opened")
    assert "flex-wrap: nowrap;" in opened and "white-space: nowrap;" in opened
    ages = _rule(css, ".github-pull-opened > .github-pull-quiet")
    assert "height: 1lh;" in ages and "display: flex;" in ages
    # Its ages give way before its links (B4 of review B on #506); a flex row cuts no text,
    # so the ellipsis is the ages' own.
    assert "text-overflow" not in ages
    assert "text-overflow: ellipsis;" in _rule(css, ".github-pull-quiet > .github-pull-ages")
    assert "flex: none;" in _rule(css, ".github-pull-quiet > .github-pull-ages-links")
    # Refresh ends it, after Browse code (A1 of review A on #506).
    assert "placeChildren(openedRow, [stateBadge, opened.row, refresh]);" in page
    assert "margin-inline-start: auto;" in _rule(css, ".github-pull-opened > .github-pull-refresh")
    assert 'h("div", { class: "github-pull-branches page-header-line" })' in page


def test_the_state_badge_is_as_wide_as_the_widest_state() -> None:
    """Its slot is a grid whose column is the widest state's label (review F2 on #370)."""

    css = _github_css()
    states = (GITHUB / "pull-state.js").read_text(encoding="utf-8")
    labels = re.findall(r'label: "([A-Z][a-z]+)"', states)
    assert set(labels) == {"Open", "Draft", "Merged", "Closed"}, labels
    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    assert 'const stateBadge = h("span", { class: "github-pull-state-slot" });' in page
    # A sizer of every state's label, drawn beside the badge in its slot, built once.
    assert "const badgeSizers = Object.values(PULL_STATES).map(({ label }) =>" in page
    assert "...badgeSizers," in page
    assert '"file-header-badge github-pull-badge github-pull-badge-sizer"' in page
    slot = _rule(css, ".github-pull-state-slot")
    assert "display: inline-grid;" in slot and "flex: none;" in slot
    assert "justify-self: stretch;" in _rule(css, ".github-pull-state-slot > .github-pull-badge")
    sizer = _rule(css, ".github-pull-state-slot > .github-pull-badge-sizer")
    assert "block-size: 0;" in sizer and "visibility: hidden;" in sizer
    # Pseudo-element sizers of the inline-block badge were laid beside the label, and made
    # the badge all three labels wide.
    assert ".github-pull-badge::before" not in css and ".github-pull-badge::after" not in css


def test_labels_have_a_row_while_unknown_or_present() -> None:
    """A label's height, held while the record is on its way; none for no labels (mb-2u08).

    The stack's chip is on the author's row. A record's labels come with it, so whether the
    row is there is decided with the record's first paint; a label's color arriving later
    changes no chip's box (tests/dom/github-pull-header-chrome.mjs measures both).
    """

    css = _github_css()
    rule = _rule(css, ".github-pull-labels")
    assert "min-height: calc(1lh + 2px);" in rule
    assert "flex-wrap: nowrap;" in rule
    assert "overflow" not in rule
    labels = _rule(css, ".github-pull-label-list")
    assert "min-width: 0;" in labels and "overflow: hidden;" in labels
    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    assert 'h("div", { class: "github-pull-labels" }, [labelList])' in page
    # A pull request with no labels has no labels row, and no gap for it.
    assert "if (pull.labels.length > 0) {" in page
    # While the record is on its way the row is held, empty, with the rows it may have.
    assert "children.push(stateRow, branchesRow, openedRow, labelsRow);" in page


def test_the_stack_chip_ends_the_authors_row() -> None:
    """A late chip lands in the row's empty end, at the header's content edge (mb-cf0l)."""

    css = _github_css()
    stacks = _rule(css, ".github-pull-stacks")
    assert "margin-inline-start: auto;" in stacks and "flex: none;" in stacks
    assert ".github-pull-stacks[hidden]" not in css, "the slot is never hidden"
    # The author's row positions the stack's menu, which hangs from the chip's end.
    assert "position: relative;" in _rule(css, ".github-pull-meta")
    menu = _rule(css, ".github-pull-stack-menu")
    assert "inset-inline-end: 0;" in menu and "inset-inline-start" not in menu
    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    assert 'h("div", { class: "github-pull-meta page-header-line" }, [\n    stateLead,' in page


def test_the_freshness_note_ends_the_authors_row_in_a_slot_of_its_widest_age() -> None:
    """One time, on the author's row, whole or gone, and the age ticking moves nothing (mb-ne91).

    The note's slot is one grid cell holding the note and a hidden copy at its widest age, so
    its width is the same from "just now" to "59 min ago". The row's lead wraps, so a note
    that cannot be whole beside the sentence leaves the line, dot and all, and the sentence
    keeps its width; github-pull-header-chrome.mjs measures both (A2 of review A on #506).
    """
    css = _github_css()
    note = _rule(css, ".github-pull-note")
    assert "color: var(--muted);" in note and "flex: 0 1 auto;" in note
    assert "min-width: 0;" in note
    lead = _rule(css, ".github-pull-meta-lead")
    for declaration in ("flex-wrap: wrap;", "height: 1lh;", "overflow: hidden;", "min-width: 0;"):
        assert declaration in lead, declaration
    assert "display: none;" in _rule(css, ".github-pull-meta-details[hidden]")
    assert "display: none;" in _rule(css, ".github-pull-note[hidden]")
    slot = _rule(css, ".github-pull-freshness-slot")
    assert "display: inline-grid;" in slot and "minmax(0, max-content)" in slot
    sizer = _rule(css, ".github-pull-freshness-sizer")
    assert "grid-area: 1 / 1;" in sizer and "visibility: hidden;" in sizer
    assert "font-variant-numeric: var(--tabular-numerals);" in sizer
    assert "grid-area: 1 / 1;" in _rule(css, ".github-pull-freshness-slot > .github-pull-freshness")
    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    assert 'h("span", { class: "github-pull-note" }, [freshnessSep, freshnessSlot]);' in page, (
        "Refresh is not in the note, which can leave the line"
    )
    # A note cut short, alone on the row before a record, carries its text as a tooltip.
    assert "const freshnessLine = tipWhenCut(" in page
    # One time, never two: no "Checked … · fetched …".
    assert "Checked ${" not in page


def test_the_status_row_is_one_line_there_while_it_has_something_to_say() -> None:
    css = _github_css()
    status = _rule(css, ".github-pull-status")
    assert "flex-wrap: nowrap;" in status
    assert "display: none;" in _rule(css, ".github-pull-status[hidden]")
    assert "font-variant-numeric: var(--tabular-numerals);" in _rule(css, ".github-pull-freshness")
    # The offers end the row, so a message's width moves none of them.
    end = _rule(css, ".github-pull-status-end")
    assert "margin-inline-start: auto;" in end and "flex: 0 1 auto;" in end
    # An offer's sentence gives way before its control; what that lays out to, at every
    # pane width, is checked in Chrome (tests/test_github_pull_header_chrome.py).
    assert "text-overflow: ellipsis;" in _rule(css, ".github-pull-offer-text")
    assert "flex: none;" in _rule(css, ".github-pull-offer > :is(button, a)")
    assert "margin-inline-start" not in _rule(css, ".github-pull-refresh")
    held = _rule(css, ".github-pull-refresh[hidden]")
    assert "visibility: hidden;" in held and "display: inline-block;" in held
    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    # The row is a metadata line, a line of the page header's body size tall (mb-2u08,
    # mb-kisi), which its class sets (`.page-header-line`): its controls are text actions, a
    # line tall, never bordered .btn boxes, which made it 26 px against 18.
    assert "font-size" not in status
    assert 'h("div", { class: "github-pull-status page-header-line" })' in page
    # Whether it shows is read from what the paint put on it, not from the DOM (A4 of review A
    # on #506); the browserless sessions hold it (github-pull-page-mount-behavior.js).
    assert "status.hidden = agesRow && statusText.length === 0 && ending.length === 0;" in page
    assert 'class: "github-pull-text-action github-pull-refresh"' in page
    assert 'class: "github-pull-text-action github-pull-switch"' in page
    assert "btn github-pull-refresh" not in page and "btn github-pull-switch" not in page
    # Shown while offered, and while a refresh it offered waits, disabled, keeping its number
    # (B2 of review B on #506).
    assert "refresh.hidden = !(model.canRefresh || waiting);" in page
    assert 'refresh.setAttribute("aria-disabled", "true");' in page
    waits = _rule(css, '.github-pull-text-action[aria-disabled="true"]')
    assert "color: var(--muted);" in waits and "cursor: default;" in waits
    assert "if (model.canRefresh) {" not in page
    # With no row of ages, Refresh is the end's last child, after any offers.
    assert 'h("span", { class: "github-pull-status-end" })' in page
    assert "placeChildren(end, agesRow ? ending : [...ending, refresh]);" in page
    assert 'status.append(h("span", { class: "github-pull-offer" }' not in page
    # A failure carries its remedy, so it is the one text the row lets wrap.
    failed = _rule(css, ".github-pull-status.github-pull-status-failed")
    assert "flex-wrap: wrap;" in failed and "white-space: normal;" in failed
    # A rate limit's hold asks nothing of the reader and lifts by itself: it is said in the
    # note's place, so it adds no line (A3 of review A on #506).
    assert "model.failure !== null && model.failureHold !== true" in page
    assert "model.failureHold = true;" in page
    assert "? (hold ?? model.freshness)" in page


def test_the_pulls_status_lines_are_always_there_at_a_line_each() -> None:
    """Each is a metadata line, which reserves its own line box (`.nav-metadata`)."""

    line = _rule(_css(), ".nav-metadata")
    assert "min-height: 1lh;" in line and "box-sizing: content-box;" in line
    css = _github_css()
    # The count's one item is cut short; the line itself is the component's
    # (tests/test_nav_metadata_line.py), and Chrome measures it one line in a narrow pane.
    assert ".github-pulls-status {" not in css
    total = _rule(css, ".github-pulls-total-line")
    assert "white-space: nowrap;" in total and "text-overflow: ellipsis;" in total
    assert ".github-pulls-connection:not([hidden])" not in css
    panel = (GITHUB / "pulls-panel.js").read_text(encoding="utf-8")
    assert "status.hidden" not in panel and "connection.hidden" not in panel
    assert 'h("p", { class: "github-pulls-status nav-metadata" })' in panel
    assert (
        'h("div", { class: "github-pulls-connection nav-metadata nav-metadata-note" }, [' in panel
    )


def test_the_pulls_rows_age_column_and_filter_counts_keep_their_widths() -> None:
    css = _github_css()
    columns = re.search(r"grid-template-columns:\s*([^;]*);", _rule(css, ".github-pulls-row"))
    assert columns is not None
    # The title runs to the row's end on the first line, and the number's line and the age
    # share the second (mb-lkkt; the title first since 2026-11-17).
    # The state icon is the tree's one icon slot (mb-hmv7), on the row's inset, with no empty
    # slot before it (mb-3vil); a stack's row has two, its chevron's and its Layers icon's.
    assert " ".join(columns.group(1).split()) == "var(--tree-icon-slot) minmax(0, 1fr) 5ch"
    stack_columns = re.search(
        r"grid-template-columns:\s*([^;]*);",
        _rule(css, ".github-pulls-row.github-pulls-stack-row"),
    )
    assert stack_columns is not None
    assert (
        " ".join(stack_columns.group(1).split())
        == "var(--tree-icon-slot) var(--tree-icon-slot) minmax(0, 1fr) 5ch"
    )
    # The rows' one gap and the text column's offset, which every indent sums (A8 of review A
    # on #506). The change line's inset is the row's, so its chevron is under the state icon.
    change = _rule(css, ".github-pulls-change")
    assert "padding: 0 12px 2px calc(10px + var(--github-pulls-indent, 0px));" in change
    assert "grid-template-columns: var(--tree-icon-slot) minmax(0, 1fr);" in change
    assert "column-gap: var(--github-pull-row-gap);" in change
    assert "column-gap: var(--github-pull-row-gap);" in _rule(css, ".github-pulls-row")
    assert "  --github-pull-row-gap: 6px;\n" in css
    column = (
        "--github-pull-row-text-column: calc(var(--tree-icon-slot) + var(--github-pull-row-gap));"
    )
    assert column in css
    assert "var(--tree-icon-slot) + 6px" not in css
    count = _rule(css, ".github-pulls-filters .count")
    assert "min-width: 3ch;" in count
    assert "font-variant-numeric: var(--tabular-numerals);" in count
    # Pending, the count is as wide as it will be once it lands.
    assert "width: 3ch;" in _rule(css, ".github-pulls-filters .count.tally-pending")


def test_a_stack_members_place_is_on_its_numbers_line() -> None:
    """A stack member's place in its stack is on the muted line, before its number: "1/6 ·
    #455 · author" (mb-dzsi). Its column on the title line, between the title and the age
    (review E1 on #370), took the title's room; the place now arrives with the row's move
    under its stack's row, so it moves nothing that had not moved. The title's line is the
    title, which since mb-lkkt has a line of its own under the number's.
    github-pulls-stacks-chrome.mjs measures the title's room, and
    github-pulls-panel-session.js pins the built row's order."""

    panel = (GITHUB / "pulls-panel.js").read_text(encoding="utf-8")
    assert "[icon, title, updated, meta]," in panel
    meta = panel[panel.index("function rowMeta(") :]
    meta = meta[: meta.index("\n  }\n")]
    assert meta.index("place,") < meta.index('"github-pulls-number"'), "the place leads the line"
    css = _github_css()
    # The place and the number are one part of the wrapping line, which never breaks;
    # alone on a line too short for it, the place ends in an ellipsis and the number shows
    # whole (github-pull-header-chrome.mjs measures it at 180 to 420 px).
    part = _rule(css, ".github-pulls-id")
    assert "white-space: nowrap;" in part and "min-width: 0;" in part
    assert "flex: none;" in _rule(css, ".github-pulls-number")
    assert "text-overflow: ellipsis;" in _rule(
        css, ".github-pulls-place > .github-pull-stack-position"
    )
    assert ".github-pulls-row > .github-pulls-stack" not in css
    assert "grid-column: 3;" in _rule(css, ".github-pulls-row > .github-pulls-age")


def test_a_pulls_rows_title_comes_first_and_runs_to_the_end() -> None:
    """A pull request's row is three lines (mb-lkkt, mb-d0a3). Its link is two: the state
    icon in its slot, then the title alone, from the text column to the row's end; then the
    number's line, "1/4 · #113 · jlevy", with the age at the row's end. The number's line
    came first, the icon leading it, from mb-3cbf until 2026-11-17, when the owner asked for
    the title first; the chevron moved to the row's third line, its change line, which is
    not part of the link, in mb-h0ml. The number's line is one line, so the link is always
    two: the author leaves it whole onto a clipped second line rather than growing the row.
    The DOM keeps the title the link's first text, so its accessible name gives the state
    icon's label and then the title, before the number's line.
    github-pulls-stacks-chrome.mjs, github-pull-header-chrome.mjs, and
    github-pulls-row-lines-chrome.mjs measure it."""

    panel = (GITHUB / "pulls-panel.js").read_text(encoding="utf-8")
    assert "[icon, title, updated, meta]," in panel, "the title leads the name"
    css = _github_css()
    meta = _rule(css, ".github-pulls-meta")
    for declaration in ("grid-row: 2;", "grid-column: 2;", "height: 1lh;", "overflow: clip;"):
        assert declaration in meta, declaration
    age = _rule(css, ".github-pulls-row > .github-pulls-age")
    assert "grid-row: 2;" in age and "grid-column: 3;" in age and "justify-self: end;" in age
    title = _rule(css, ".github-pulls-row > .github-pulls-title")
    assert "grid-row: 1;" in title and "grid-column: 2 / -1;" in title
    # The icon leads the first line in the one slot, on the row's inset (mb-3vil), before the
    # title. A stack's row keeps its chevron in the first slot of its one line.
    for part, column in (("github-pulls-toggle", 1), ("github-pull-state-icon", 1)):
        rule = _rule(css, f".github-pulls-row > .{part}")
        assert "grid-row: 1;" in rule and f"grid-column: {column};" in rule, part
    # A pull request's chevron is on its change line, in the row's one slot under the state
    # icon, and the line's values in the text column under the title (mb-3vil).
    assert "grid-column: 1;" in _rule(css, ".github-pulls-change > .github-pulls-toggle")
    assert "grid-column: 2;" in _rule(css, ".github-pulls-change-line")
    second = re.findall(r"(?m)^(\.github-pulls[^{\n]*)\{[^}]*grid-row: 2;", css)
    assert sorted(selector.strip() for selector in second) == [
        ".github-pulls-meta",
        ".github-pulls-row > .github-pulls-age",
    ]
    # The number's line and the age share a baseline.
    assert (
        ".github-pulls-row > :is(.github-pulls-meta, .github-pulls-title, .github-pulls-age)"
        in (css)
    )
