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
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    labels = set(re.findall(r'badge-(?:running|live|completed|failed)">([^<]+)<', app))
    labels |= set(re.findall(r'badge\.textContent = "([^"]+)"', app))
    assert labels == {"Running", "Live", "Done", "Failed", "Run ended"}, labels
    sizers = re.search(r"const RUN_STATUS_SIZERS = \[([^\]]*)\]", app)
    assert sizers is not None
    assert set(re.findall(r'"([^"]+)"', sizers.group(1))) == labels
    render = _function(app, "renderBadges")
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
    """A pull request's title was 1 to 3 lines, 30 px each, under the tab bar's feet."""

    css = _github_css()
    assert "min-height: 2lh;" in _rule(css, ".github-pull-title")
    clamp = _rule(css, ".github-pull-title-text")
    assert "-webkit-line-clamp: 2;" in clamp and "line-clamp: 2;" in clamp
    assert "overflow: hidden;" in clamp
    # The commit view's subject is the same heading, and holds the same two lines.
    assert "min-height: 2lh;" in _rule(_css(), ".git-commit-subject.page-heading")


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
    # (review E3 on #370).
    assert "[\n    stateDetails,\n    stackColumn,\n  ]);" in page
    # The state badge leads the row of ages (mb-4ydo), one line in every state.
    opened = _rule(css, ".github-pull-opened")
    assert "flex-wrap: nowrap;" in opened and "white-space: nowrap;" in opened
    ages = _rule(css, ".github-pull-opened > .github-pull-quiet")
    assert "height: 1lh;" in ages and "text-overflow: ellipsis;" in ages
    assert "placeChildren(openedRow, [stateBadge, opened.row]);" in page
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
    assert 'h("div", { class: "github-pull-meta page-header-line" }, [\n    stateDetails,' in page


def test_the_status_row_is_one_line_ending_in_refreshs_slot() -> None:
    css = _github_css()
    status = _rule(css, ".github-pull-status")
    assert "flex-wrap: nowrap;" in status
    assert "font-variant-numeric: var(--tabular-numerals);" in _rule(css, ".github-pull-freshness")
    # The offers end the row with Refresh, so the freshness text's width moves none of them.
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
    assert 'h("div", { class: "github-pull-status page-header-line" }, [freshnessLine])' in page
    assert 'class: "github-pull-text-action github-pull-refresh"' in page
    assert 'class: "github-pull-text-action github-pull-switch"' in page
    assert "btn github-pull-refresh" not in page and "btn github-pull-switch" not in page
    assert "refresh.hidden = !model.canRefresh;" in page
    assert "if (model.canRefresh) {" not in page
    # Refresh is always the end's last child, after any offers.
    assert 'h("span", { class: "github-pull-status-end" })' in page
    assert "placeChildren(end, [...ending, refresh]);" in page
    assert 'status.append(h("span", { class: "github-pull-offer" }' not in page
    # A failure carries its remedy, so it is the one text the row lets wrap.
    failed = _rule(css, ".github-pull-status.github-pull-status-failed")
    assert "flex-wrap: wrap;" in failed and "white-space: normal;" in failed
    # A rate limit's hold asks nothing of the reader and lifts by itself: it stays on the line.
    assert "model.failure !== null && model.failureHold !== true" in page
    assert "model.failureHold = true;" in page


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
    # The chevron and the icon are each the tree's one icon slot (mb-hmv7).
    assert (
        " ".join(columns.group(1).split())
        == "var(--tree-icon-slot) var(--tree-icon-slot) minmax(0, 1fr) 5ch"
    )
    assert "column-gap: 6px;" in _rule(css, ".github-pulls-row")
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
    assert "grid-column: 4;" in _rule(css, ".github-pulls-row > .github-pulls-age")


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
    for declaration in ("grid-row: 2;", "grid-column: 3;", "height: 1lh;", "overflow: clip;"):
        assert declaration in meta, declaration
    age = _rule(css, ".github-pulls-row > .github-pulls-age")
    assert "grid-row: 2;" in age and "grid-column: 4;" in age and "justify-self: end;" in age
    title = _rule(css, ".github-pulls-row > .github-pulls-title")
    assert "grid-row: 1;" in title and "grid-column: 3 / -1;" in title
    # The icon leads the first line in the second slot, before the title.
    # A stack's row keeps its chevron in the first slot of its one line.
    for part, column in (("github-pulls-toggle", 1), ("github-pull-state-icon", 2)):
        rule = _rule(css, f".github-pulls-row > .{part}")
        assert "grid-row: 1;" in rule and f"grid-column: {column};" in rule, part
    # A pull request's chevron is on its change line, in the first slot, and the line in the
    # text column.
    assert "grid-column: 1;" in _rule(css, ".github-pulls-change > .github-pulls-toggle")
    assert "grid-column: 3;" in _rule(css, ".github-pulls-change-line")
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
