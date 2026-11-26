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
    assert 'data-nav-toolbar="files"{filter_bar_behind}>{pending_tally}</div>' in server
    assert server.index("{source_ref_row}") < server.index('id="nav-filter-bar"')
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
    # A keycap is 1.5 lines of the strip's own type, so the reservation is in line units:
    # the row's height token, which the chevron is placed on too (mb-yw18), plus the rule.
    assert "min-height: calc(1px + var(--nav-shortcut-row-height));" in rule, rule
    assert re.search(
        r"--nav-shortcut-row-height: calc\([^;]*1\.5 \* var\(--kbd-font-size\)\);", _css()
    )
    keycap = _rule(_css(), ".kbd")
    assert "line-height: 1.5;" in keycap
    assert "font-size: var(--kbd-font-size);" in keycap
    assert "--kbd-font-size: var(--ui-small-font-size);" in _css()
    assert "font-size: var(--kbd-font-size);" in _rule(_css(), ".nav-shortcut-hints")


def _view_tab_markup() -> str:
    composition = (STATIC / "view-composition.js").read_text(encoding="utf-8")
    return _function(composition, "renderTabs")


def test_every_file_has_a_view_tab_bar() -> None:
    """A kind with one view, or none, starts its content where a kind with two does."""

    render = _view_tab_markup()
    # Only the view keys wait for a second view; the bar itself does not. The one test of
    # the length past "any views" is the key gate, and the gate decides only the key.
    lengths = re.findall(r"views\.length\s*(?:[<>]=?|[!=]==)\s*\d+", render)
    assert lengths == ["views.length === 0", "views.length > 1"], lengths
    assert [line.strip() for line in render.splitlines() if "keyedBar" in line] == [
        "const keyedBar = views.length > 1;",
        '(keyedBar ? viewKey : "") +',
    ], "keyedBar gates something besides the key"
    assert '<div class="tab-bar" role="tablist">' in render
    assert '<span class="tab-btn tab-slot">&nbsp;</span>' in render
    slot = _rule(_css(), ".tab-slot")
    # It takes a tab's padding and type from .tab-btn, and a button's line-height.
    assert "visibility: hidden;" in slot
    assert "line-height: normal;" in slot


def test_only_a_bar_of_two_views_carries_their_keys(tmp_path: Path) -> None:
    """A lone view's tab has no other view to switch to, so it publishes no key.

    The server already strips such a key (``keymap.live_view_keys``), so no page it serves
    can show the gate. Render the compositor's markup on a list of one view and a list
    of two, each declaring a key.
    """

    script = tmp_path / "view-tab-bar.js"
    script.write_text(
        "const fs = require('node:fs');\n"
        "const vm = require('node:vm');\n"
        "const window = {};\n"
        "vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), {window});\n"
        "const lists = [\n"
        "  [{ id: 'source', label: 'Source', key: 's' }],\n"
        "  [{ id: 'rendered', label: 'Document', key: 'd' }, { id: 'source', label: 'Source', key: 's' }],\n"
        "];\n"
        "for (const views of lists) {\n"
        "  const prepared = views.map((view) => ({view, renderer: null}));\n"
        "  console.log(window.MetabrowserViewComposition.renderTabs(prepared, views[0].id, String));\n"
        "}\n",
        encoding="utf-8",
    )
    one, two = subprocess.run(
        [require_node(), str(script), str(STATIC / "view-composition.js")],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
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

    It is cut short at two lines. A record's title is its own one or two lines, and the
    author's line is `--page-title-gap` under it: a held second line stood between a one-line
    title and its author, 36.5 px of space where a two-line title had 6 (mb-wcbc). The commit
    view's subject is the same heading, and holds no line either. The title while the record
    is on its way, where the Pulls tab has no row to title it with, holds two, the most a
    record's title takes, and a record seen landing on it keeps them
    (`.github-pull-title-held`, set by pull-page.js), so the record lands moving nothing
    (review A on #608).
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
    assert "min-height: 2lh;" in _rule(css, ".github-pull-title-held > .github-pull-title")
    assert not re.search(r"(?m)^\.git-commit-subject\.page-heading\s*\{", _css())


def test_the_state_row_is_one_line_held_by_a_strut() -> None:
    """The author and the sentence share one line; the branches, the next (mb-646g).

    The row of ages above them ends in the stack's slot, whose strut holds that row at a
    chip's height until a chip arrives.
    """

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
    # The author's row is its lead alone, the sentence and then the freshness note (mb-ne91):
    # the stack's slot is on the row of ages (mb-646g). On the author's row (mb-cf0l) the chip
    # stood a row below the state and ages it belongs with, and on the row that also held the
    # merge a late chip took its width from the sentence and the merge (review E3 on #370).
    # Its parts are the header's builder's (`pageHeaderParts`), which a stack's page shares.
    assert 'row: h("div", { class: "github-pull-meta page-header-line" }, [lead]),' in page
    assert 'const lead = h("span", { class: "github-pull-meta-lead" }, [details, note]);' in page
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
    # The stack's slot ends the row (mb-646g, mb-dwha), on a record's row and on the one held
    # before a record, with nothing after it: the page has no Refresh of its own (mb-ablv).
    assert "placeChildren(openedRow, [stateSlot, opened.row, stackColumn]);" in page
    assert "          ),\n          stackColumn,\n        ]);" in page
    assert "github-pull-refresh" not in page and "github-pull-refresh" not in css
    assert 'h("div", { class: "github-pull-branches page-header-line" })' in page


def test_the_state_badge_is_as_wide_as_the_widest_state() -> None:
    """Its slot is a grid whose column is the widest state's label (review F2 on #370)."""

    css = _github_css()
    states = (GITHUB / "pull-state.js").read_text(encoding="utf-8")
    labels = re.findall(r'label: "([A-Z][a-z]+)"', states)
    assert set(labels) == {"Open", "Draft", "Merged", "Closed"}, labels
    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    assert 'const stateSlot = h("span", { class: "github-pull-state-slot" });' in page
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

    The stack's chip is on the row of ages. A record's labels come with it, so whether the
    row is there is decided with the record's first paint; a label's color arriving later
    changes no chip's box (tests/dom/github-pull-header-chrome.mjs measures both).
    """

    css = _github_css()
    rule = _rule(css, ".github-pull-labels")
    assert "min-height: var(--compact-chip-height);" in rule
    assert "flex-wrap: nowrap;" in rule
    assert "overflow" not in rule
    labels = _rule(css, ".github-pull-label-list")
    assert "min-width: 0;" in labels and "overflow: hidden;" in labels
    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    # The row is the header's builder's (`pageHeaderParts`), which a stack's page shares.
    assert 'labels: { row: h("div", { class: "github-pull-labels" }, [list]), list },' in page
    # A pull request with no labels has no labels row, and no gap for it.
    assert "if (pull.labels.length > 0) {" in page
    # While the record is on its way the row is held, empty, with the rows it may have.
    assert "children.push(openedRow, stateRow, branchesRow, labelsRow);" in page


def test_the_stack_chip_ends_the_row_of_ages_under_the_number() -> None:
    """A late chip lands in the row's empty end, under the number (mb-646g, mb-dwha, mb-ablv).

    The slot takes the row's spare width, so the chip ends the row at the content edge,
    under the end of the title's number where the title leaves the corner's button no room;
    nothing follows it, since the page has no Refresh of its own, whose held slot there kept
    the chip a Refresh's width short of the number. The ages take only the width the chips
    leave, so they give
    way before a chip does, and a chip's position is cut short only once they have none
    left. tests/dom/github-pull-header-chrome.mjs measures it.
    """

    css = _github_css()
    stacks = _rule(css, ".github-pull-stacks")
    assert "margin-inline-start: auto;" in stacks and "flex: 0 1 auto;" in stacks
    assert "min-width: 0;" in stacks
    assert ".github-pull-stacks[hidden]" not in css, "the slot is never hidden"
    # One auto margin on the row, the slot's, so the chip ends the row.
    assert "margin-inline-start" not in _rule(css, ".github-pull-opened > .github-pull-quiet")
    # The row ends at the content edge: the room the title leaves the corner's button is the
    # title's alone, since taking it from the row too cut the ages and Browse code short in a
    # narrow pane.
    room = ".github-pull-header:has(> .view-header-end[data-counterpart])"
    assert "padding-inline-end: max(" in _rule(css, f"{room} > .github-pull-title")
    assert f"{room} > .github-pull-opened" not in css
    # The ages' basis is nothing, and they grow to their own width at most.
    ages = _rule(css, ".github-pull-opened > .github-pull-quiet")
    assert "flex: 1 1 0;" in ages and "max-width: max-content;" in ages
    position = _rule(css, ".github-pull-stack-trigger > .github-pull-stack-position")
    assert "min-width: 0;" in position and "text-overflow: ellipsis;" in position
    # The row of ages positions the stack's menu, which hangs from the row's end.
    assert "position: relative;" in _rule(css, ".github-pull-opened")
    assert "position: relative;" not in _rule(css, ".github-pull-meta")
    menu = _rule(css, ".github-pull-stack-menu")
    assert "inset-inline-end: 0;" in menu and "inset-inline-start" not in menu


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
    note = 'const note = h("span", { class: "github-pull-note" }, [\n    sep,\n'
    assert note in page, "Refresh is not in the note, which can leave the line"
    # A note cut short, alone on the row before a record, carries its text as a tooltip.
    assert "const line = tipWhenCut(" in page
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
    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    # The row is a metadata line, a line of the page header's body size tall (mb-2u08,
    # mb-kisi), which its class sets (`.page-header-line`): its controls are text actions, a
    # line tall, never bordered .btn boxes, which made it 26 px against 18.
    assert "font-size" not in status
    assert 'h("div", { class: "github-pull-status page-header-line" })' in page
    # Whether it shows is read from what the paint put on it, not from the DOM (A4 of review A
    # on #506); the browserless sessions hold it (github-pull-page-mount-behavior.js).
    assert "status.hidden = agesRow && statusText.length === 0 && ending.length === 0;" in page
    # The page has no Refresh of its own (mb-ablv): the status row's remedy, Retry or Fetch,
    # is a text action first among the offers at its end, never cut short.
    assert 'class: "github-pull-text-action github-pull-remedy"' in page
    assert "btn github-pull-remedy" not in page
    assert "flex: none;" in _rule(css, ".github-pull-status-end > .github-pull-remedy")
    # Shown while the row says what it is for, and while a refresh it asked for has not yet
    # started, disabled, keeping its number (B2 of review B on #506).
    assert "const remedyShown = asks && (model.canRefresh || waiting);" in page
    assert 'remedy.setAttribute("aria-disabled", "true");' in page
    waits = _rule(css, '.github-pull-text-action[aria-disabled="true"]')
    assert "color: var(--muted);" in waits and "cursor: default;" in waits
    assert "if (model.canRefresh) {" not in page
    assert 'h("span", { class: "github-pull-status-end" })' in page
    assert "placeChildren(end, ending);" in page
    assert 'status.append(h("span", { class: "github-pull-offer" }' not in page
    # A failure carries its remedy, so it is the one text the row lets wrap.
    failed = _rule(css, ".github-pull-status.github-pull-status-failed")
    assert "flex-wrap: wrap;" in failed and "white-space: normal;" in failed
    # A rate limit's hold asks nothing of the reader and lifts by itself: it is said in the
    # note's place, so it adds no line (A3 of review A on #506).
    assert "model.failure !== null && model.failureHold !== true" in page
    assert "model.failureHold = true;" in page
    assert "? (hold ?? model.freshness)" in page


def test_the_pulls_metadata_uses_the_shared_line_boxes() -> None:
    """Each is a metadata line, which reserves its own line box (`.nav-metadata`)."""

    line = _rule(_css(), ".nav-metadata")
    assert "min-height: 1lh;" in line and "box-sizing: content-box;" in line
    css = _github_css()
    # The repository total gives way on the shared line, keeping the state tally visible.
    assert ".github-pulls-status {" not in css
    total = _rule(css, ".github-pulls-total-line")
    assert "white-space: nowrap;" in total
    assert "text-overflow: ellipsis;" in _rule(css, ".github-pulls-total-lead")
    assert "flex: none;" in _rule(css, ".github-pulls-total-scope")
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
    # A pull request's link is one column, its run and its last line, across the row from the
    # state icon in the slot to the row's end (mb-85op, mb-pw8t); a stack's row is one line,
    # its chevron's slot, its heading, and the age's column a pull request's last line has
    # (mb-tvhs).
    # The state icon is the tree's one icon slot (mb-hmv7), on the row's inset, with no empty
    # slot before it (mb-3vil); a stack's row has one too, its chevron's.
    assert " ".join(columns.group(1).split()) == "minmax(0, 1fr)"
    stack_columns = re.search(
        r"grid-template-columns:\s*([^;]*);",
        _rule(css, ".github-pulls-row.github-pulls-stack-row"),
    )
    assert stack_columns is not None
    # Both rows' age columns read the one width, declared once on the row, so no grid keeps
    # a copy of it.
    age_column = "var(--github-pulls-age-column)"
    assert css.count("--github-pulls-age-column:") == 1
    assert "--github-pulls-age-column:" in _rule(css, ".github-pulls-row")
    assert stack_columns.group(1).split()[-1] == age_column
    tail_columns = re.search(
        r"grid-template-columns:\s*([^;]*);", _rule(css, ".github-pulls-row > .github-pulls-tail")
    )
    assert tail_columns is not None
    assert tail_columns.group(1).split()[-1] == age_column
    # The rows' one gap and the text column's offset, which every indent sums (A8 of review A
    # on #506).
    assert "column-gap: var(--github-pull-row-gap);" in _rule(css, ".github-pulls-row")
    assert "  --github-pull-row-gap: var(--tree-icon-gap);\n" in css
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


def test_a_pulls_rows_title_comes_first_and_runs_to_the_end() -> None:
    """A pull request's row is a run and a last line, all of it the row's link (mb-lkkt,
    mb-d0a3, mb-85op, mb-lqkb, mb-pw8t, mb-rb3n). The run is one flow of the state icon, then
    the title, a stack member's place, the number, and the author, "title · 5/12 · #N · jlevy",
    every line of it in the text column, past the icon, as a tree's title wraps; the last line
    is the lines with the chevron after them, "+12 −3 ›", and the age at the row's end. The
    lines and the chevron are the toggle of its changed files, and the rest of the row opens
    it. Before, the lines and the chevron ended the run, and the author and the age were the
    last line (mb-pw8t); before that, the title alone held two lines, cut short at the second,
    and a third line held the number, the author, and the lines. The DOM keeps the title the link's first
    text, so its accessible name gives the state icon's label, the title, and the place, before
    the number, the author, and the age in words (`rowSaid`). github-pulls-stacks-chrome.mjs,
    github-pull-header-chrome.mjs, and github-pulls-row-lines-chrome.mjs measure it."""

    panel = (GITHUB / "pulls-panel.js").read_text(encoding="utf-8")
    assert "[heading, tail, said]," in panel, "the title leads the name"
    build = _function(panel, "buildRow")
    # The run's order is the one every row of a pull request's fields has, the builder's
    # (stack-member-row.js); the last line is the toggle, whose lines come before its chevron,
    # and the age.
    assert 'h("span", { class: "github-pulls-tail" }, [change, updated])' in build
    toggle = build[build.index('{ class: "github-pulls-change disclosure-toggle collapsed"') :]
    assert toggle.index("changeLine,") < toggle.index('"github-pulls-toggle"'), (
        "the chevron comes after the lines it expands"
    )
    css = _github_css()
    heading = _rule(css, ".github-pulls-row > .github-pulls-heading")
    for declaration in (
        "position: relative;",
        "display: block;",
        "padding-inline-start: var(--github-pull-row-text-column);",
    ):
        assert declaration in heading, declaration
    # Every line of the run starts in the text column: its start padding, not the first line's
    # indent, which WebKit drops on a -webkit-box, where in the app's WKWebView the place or the
    # title was drawn over the state icon (mb-ma3f). The run is no -webkit-box and is never cut
    # short, so it always ends with its chevron; no rule of the sheet indents a line.
    assert "-webkit-box" not in heading and "line-clamp" not in heading
    assert not re.search(r"(?<![-\w])(?:min-|max-)?height\s*:", heading), heading
    assert ".github-pulls-row > .github-pulls-heading::before" not in css
    assert not re.search(r"(?m)^\s*text-indent\s*:", css)
    # Only the title breaks anywhere; the number never breaks, and the author is one box,
    # its name cut short only where it is wider than a line.
    assert "overflow-wrap" not in heading
    assert "overflow-wrap: anywhere;" in _rule(css, ".github-pulls-title")
    assert "white-space: nowrap;" in _rule(css, ".github-pulls-number")
    assert "max-width: 100%;" in _rule(css, ".github-pulls-by > .github-pull-identity")
    assert "--github-pulls-age-room" not in css
    # The icon is out of the text's flow, in the run's start padding, one line of the row's
    # type tall: inline, it was a break, and a title of one long word left the first line the
    # icon alone.
    icon = _rule(css, ".github-pulls-heading > .github-pull-state-icon")
    for declaration in (
        "position: absolute;",
        "inset-block-start: 0;",
        "inset-inline-start: 0;",
        "height: 1lh;",
    ):
        assert declaration in icon, declaration
    assert ".github-pulls-heading > .github-pulls-tail" not in css
    assert "--github-pulls-lines-room: 5.6em;" in _rule(css, ".github-pulls-row")
    assert "width: var(--github-pulls-lines-room);" in _rule(css, ".github-pulls-change-pending")
    assert "margin-inline-start: 0.25em;" in _rule(
        css, ".github-pulls-change > .github-pulls-toggle"
    )
    # Where the line has no room for the lines, they give way whole to an ellipsis, never
    # broken onto a second line, and the chevron and the age stay.
    line = _rule(css, ".github-pulls-change > .github-pulls-change-line")
    assert "overflow: hidden;" in line and "text-overflow: ellipsis;" in line
    assert "flex-wrap: nowrap;" in _rule(
        css, ".github-pulls-change > .github-pulls-change-line > .change-line"
    )
    assert "flex: none;" in _rule(css, ".github-pulls-toggle")
    assert ".github-pulls-byline" not in css and ".github-pulls-when" not in css
    # Nothing of the row's old change line is left: no grid of its own, no line that gives way.
    for gone in (".github-pulls-meta", ".github-pulls-line", ".github-pulls-change > :is("):
        assert gone not in css, gone
    assert re.findall(r"(?m)^(\.github-pulls[^{\n]*)\{[^}]*grid-row: 2;", css) == []
