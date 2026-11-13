"""Chrome whose box is decided at first paint and does not depend on later data.

Geometry is the browser's, so these pin the rules that decide it: the slot a region
keeps while its content is absent, in line units where text sets the height, so the
same rule holds in WebKit, whose font metrics differ from Chrome's. Each region named
here moved the content beside or below it when it appeared or disappeared; the
measurements are in docs/design-system.md and the rules' comments.
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
    place at one height, in line units, so what is under the slot starts at one y on every
    tab. The filter bar alone hid on Commits and Pulls and moved the panel 37 px.
    """

    css = _css()
    assert "--nav-toolbar-height: calc(var(--chip-height) + 12px + 1px);" in css
    assert "1.5 *" in css[css.index("--chip-height: calc(") :][:120], "chips are in line units"
    toolbar = _rule(css, ".nav-toolbar")
    assert "height: var(--nav-toolbar-height);" in toolbar
    assert "white-space: nowrap;" in toolbar
    # A toolbar wider than a narrowed pane scrolls along its line; it is never cut.
    assert "overflow-x: auto;" in toolbar and "overflow-y: hidden;" in toolbar
    assert "min-width: 0;" not in _rule(
        _github_css(), ".github-pulls-filters:where(.nav-toolbar > *)"
    )
    assert "min-height: var(--nav-toolbar-height);" in _rule(css, ".nav-filter-bar")
    assert "display: none;" in _rule(css, ".nav-filter-bar[hidden],\n.nav-toolbar[hidden]")
    assert ".nav-filter-bar[inert]" not in css
    tally = _rule(css, ".nav-toolbar > .git-history-summary")
    assert "padding: 0;" in tally and "min-height: 0;" in tally
    pulls = _rule(_github_css(), ".github-pulls-filters:where(.nav-toolbar > *)")
    assert "position: static;" in pulls and "padding: 0;" in pulls
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
    assert "font-size: var(--ui-small-font-size);" in _rule(_css(), ".nav-shortcut-hints")


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


def test_the_print_button_keeps_its_slot() -> None:
    """Toggling `hidden` on it moved the header's size label 32 px on a view switch."""

    rule = _rule(_css(), ".file-header-print[hidden]")
    assert "visibility: hidden;" in rule
    assert "display: inline-flex;" in rule
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "btn.hidden = !printable;" in _function(app, "updatePrintButton")


def test_a_runs_status_badge_is_as_wide_as_its_widest_label() -> None:
    """Live becomes Run ended in place; the badge sizes to the widest label from the start."""

    css = _css()
    selector = ":is(.badge-running, .badge-live, .badge-completed, .badge-failed)"
    sizer = _rule(css, f"{selector}::after")
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    labels = set(re.findall(r'badge-(?:running|live|completed|failed)">([^<]+)<', app))
    labels |= set(re.findall(r'badge\.textContent = "([^"]+)"', app))
    assert labels == {"Running", "Live", "Done", "Failed", "Run ended"}, labels
    widest = max(labels, key=len)
    assert f'content: "{widest}" / "";' in sizer
    assert "height: 0;" in sizer and "visibility: hidden;" in sizer
    assert "flex-direction: column;" in _rule(css, selector)


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
    """The sentence, the author, and the merge share one line, at a chip's height."""

    css = _github_css()
    meta = _rule(css, ".github-pull-meta")
    assert "flex-wrap: nowrap;" in meta and "white-space: nowrap;" in meta
    details = _rule(css, ".github-pull-meta-details")
    assert "min-width: 0;" in details and "overflow: hidden;" in details
    # A chip is a grid item of the merge group, whose floor keeps the names legible; a
    # width of the chip's own would overflow the group's track rather than hold it.
    chip = _rule(css, ".github-pull-meta .git-ref")
    assert "min-width" not in chip and "flex-shrink" not in chip
    # The sentence gives way before the branches do.
    action = _rule(css, ".github-pull-meta-details > .github-pull-action")
    assert "flex: 0 1000 auto;" in action and "min-width: 0;" in action
    # The author gives way next, down to its avatar and a little of the name, and only
    # then the merge, down to the merge group's floor (review E2 on #370).
    author = _rule(css, ".github-pull-meta-details > .github-pull-identity")
    assert "flex: 0 100 auto;" in author and "min-width: 1.75em;" in author
    assert "overflow: hidden;" in author
    assert "min-width: calc(18px + 4px + 1.75em);" in _rule(
        css, ".github-pull-meta-details > .github-pull-identity:has(.github-pull-avatar)"
    )
    name = _rule(css, ".github-pull-meta-details .github-pull-author")
    assert "min-width: 0;" in name and "text-overflow: ellipsis;" in name
    strut = _rule(css, ".github-pull-stack-strut")
    assert "width: 0;" in strut and "visibility: hidden;" in strut
    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    assert "btn github-pull-stack-trigger github-pull-stack-strut" in page
    # The state row ends in a strut, not in the stack's slot: a late chip there took its
    # width from the sentence and the merge (review E3 on #370).
    assert "[stateBadge, stateDetails, strut()]" in page


def test_the_state_badge_is_as_wide_as_the_widest_state() -> None:
    css = _github_css()
    states = (GITHUB / "pull-state.js").read_text(encoding="utf-8")
    labels = re.findall(r'label: "([A-Z][a-z]+)"', states)
    assert set(labels) == {"Open", "Draft", "Merged", "Closed"}, labels
    longest = max(len(label) for label in labels)
    sized = set(
        re.findall(
            r'\.github-pull-meta \.github-pull-badge::(?:before|after) \{\s*content: "([A-Za-z]+)" / "";',
            css,
        )
    )
    assert sized == {label for label in labels if len(label) == longest}, sized
    assert "flex-direction: column;" in _rule(css, ".github-pull-meta .github-pull-badge")
    # The label stays the first flex item, whose baseline the badge takes; what the rows
    # lay out to is checked in Chrome (tests/test_github_pull_header_chrome.py).
    sizers = _rule(
        css,
        ".github-pull-meta .github-pull-badge::before,\n.github-pull-meta .github-pull-badge::after",
    )
    assert "order: 1;" in sizers


def test_labels_have_a_row_that_always_exists() -> None:
    """It ends in the stack's slot, so a late chip takes room only from cut-short labels."""

    css = _github_css()
    rule = _rule(css, ".github-pull-labels")
    assert "min-height: calc(1lh + 2px);" in rule
    assert "flex-wrap: nowrap;" in rule
    # It positions the stack's menu, so it clips nothing; its list of labels does.
    assert "position: relative;" in rule and "overflow" not in rule
    labels = _rule(css, ".github-pull-label-list")
    assert "min-width: 0;" in labels and "overflow: hidden;" in labels
    stacks = _rule(css, ".github-pull-stacks")
    assert "margin-inline-start: auto;" in stacks and "flex: none;" in stacks
    assert ".github-pull-stacks[hidden]" not in css, "the slot is never hidden"
    page = (GITHUB / "pull-page.js").read_text(encoding="utf-8")
    assert "if (pull.labels.length > 0)" not in page
    assert 'h("div", { class: "github-pull-labels" }, [labelList, stackColumn])' in page


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
    assert "refresh.hidden = !model.canRefresh;" in page
    assert "if (model.canRefresh) {" not in page
    assert 'h("span", { class: "github-pull-status-end" }, [refresh])' in page
    assert 'status.append(h("span", { class: "github-pull-offer" }' not in page
    # A failure carries its remedy, so it is the one text the row lets wrap.
    failed = _rule(css, ".github-pull-status.github-pull-status-failed")
    assert "flex-wrap: wrap;" in failed and "white-space: normal;" in failed
    # A rate limit's hold asks nothing of the reader and lifts by itself: it stays on the line.
    assert "model.failure !== null && model.failureHold !== true" in page
    assert "model.failureHold = true;" in page


def test_the_pulls_status_lines_are_always_there_at_a_line_each() -> None:
    css = _github_css()
    for selector in (".github-pulls-status,\n.github-pulls-connection",):
        assert "min-height: calc(1lh + 6px);" in _rule(css, selector)
    status = _rule(css, ".github-pulls-status")
    assert "white-space: nowrap;" in status and "text-overflow: ellipsis;" in status
    assert ".github-pulls-connection:not([hidden])" not in css
    panel = (GITHUB / "pulls-panel.js").read_text(encoding="utf-8")
    assert "status.hidden" not in panel and "connection.hidden" not in panel
    assert 'h("div", { class: "github-pulls-connection" }, [' in panel


def test_the_pulls_rows_age_column_and_filter_counts_keep_their_widths() -> None:
    css = _github_css()
    assert "grid-template-columns: 16px 16px minmax(0, 1fr) auto 5ch;" in _rule(
        css, ".github-pulls-row"
    )
    count = _rule(css, ".github-pulls-filters .count")
    assert "min-width: 3ch;" in count
    assert "font-variant-numeric: var(--tabular-numerals);" in count
    # Pending, the count is as wide as it will be once it lands.
    assert "width: 3ch;" in _rule(css, ".github-pulls-filters .count.tally-pending")


def test_a_pulls_rows_stack_position_has_a_column_on_the_title_line() -> None:
    """It arrives from its own answer. On the muted line, which wraps, it moved the merge
    or added a line to its row (review E1 on #370); in a column of its own before the age,
    it cuts the title shorter and moves nothing. github-pull-header-chrome.mjs measures it,
    and github-pulls-panel-session.js pins the built row's order."""

    panel = (GITHUB / "pulls-panel.js").read_text(encoding="utf-8")
    meta = panel[panel.index("function rowMeta(") :]
    meta = meta[: meta.index("\n  }\n")]
    assert "stack" not in meta
    assert "[toggle, icon, title, stack, updated, meta]," in panel
    css = _github_css()
    stack = _rule(css, ".github-pulls-row > .github-pulls-stack")
    assert "grid-row: 1;" in stack and "grid-column: 4;" in stack
    # On the title's baseline its taller box grew the row 3 px.
    assert "align-self: center;" in stack
    assert "grid-column: 5;" in _rule(css, ".github-pulls-row > .github-pulls-age")
