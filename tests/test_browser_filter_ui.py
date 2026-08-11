"""Structural tests for the filter control family and the nav filter bar.

The chip family is a design-system commitment as much as a component:
single-select and multi-select must stay visually and semantically
distinguishable, and every filtering surface must draw from the same
rules. These tests pin the parts of that contract a refactor could
quietly break.

Behavioural checks for the selection semantics live in
tests/dom/filter_controls_behavior.js and
tests/dom/filter_state_behavior.js.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

from metabrowser import server as proc_browser


def _read(name: str) -> str:
    return proc_browser.STATIC_DIR.joinpath(name).read_text()


def _render_index_html() -> str:
    """Render the / route once and return the HTML body."""

    class _FakeQuery:
        def get(self, key: str, default: str = "") -> str:
            return default

    class _FakeReq:
        def __init__(self) -> None:
            self.query_params = _FakeQuery()
            self.headers: dict[str, str] = {}

    resp = asyncio.run(proc_browser.index(cast(Any, _FakeReq())))
    return resp.body.decode() if isinstance(resp.body, (bytes, bytearray)) else str(resp.body)


# ── The control family ─────────────────────────────────────────


def test_chip_family_is_defined_in_core_styles() -> None:
    """Promoted out of per-surface stylesheets so the treemap toolbar
    and the nav bar cannot drift apart."""

    css = _read("styles.css")
    for selector in (
        ".chip {",
        ".chip-group {",
        ".chip-toggle[aria-pressed=",
        ".chip-badge {",
        ".chip-clear {",
    ):
        assert selector in css, f"missing chip-family rule {selector!r}"


def test_single_and_multi_select_use_different_fills() -> None:
    """The fill split is the only cue that tells a user which kind of
    group they are looking at before clicking, so it is load-bearing:
    single-select takes the accent tint (the .menu-seg treatment),
    multi-select takes the neutral one."""

    css = _read("styles.css")
    one_start = css.index('.chip-group[data-select="one"] > .chip[aria-checked="true"]')
    one_block = css[one_start : one_start + 260]
    assert "var(--highlight-bg)" in one_block
    assert "var(--link)" in one_block

    many_start = css.index('.chip-group[data-select="many"] > .chip[aria-pressed="true"]')
    many_block = css[many_start : many_start + 260]
    assert "var(--hover-bg)" in many_block
    assert "var(--text)" in many_block


def test_chip_family_uses_tokens_not_color_literals() -> None:
    css = _read("styles.css")
    start = css.index("/* ── Filter controls ")
    block = css[start : css.index("/* ── Navigation filter bar ")]
    for literal in ("#", "rgb(", "hsl("):
        assert literal not in block, f"chip family must use design tokens, found {literal!r}"


def test_groups_carry_the_aria_their_variant_implies() -> None:
    """Single-select is a radiogroup with aria-checked; multi-select
    is a plain group of aria-pressed toggles. Styling keys off these
    attributes, so drifting ARIA silently breaks the visuals too."""

    js = _read("filter_controls.js")
    assert 'select === "one" ? "radiogroup" : "group"' in js
    assert 'role="radio" aria-checked=' in js
    assert "aria-pressed=" in js


def test_single_select_group_is_one_tab_stop_with_arrow_keys() -> None:
    """Roving tabindex plus arrow-key traversal is the ARIA
    radiogroup pattern; multi-select chips stay individually
    reachable because each is an independent control."""

    js = _read("filter_controls.js")
    assert 'tabindex="${on ? "0" : "-1"}"' in js
    assert '"ArrowLeft"' in js
    assert '"ArrowRight"' in js
    assert '.chip-group[data-select="one"]' in js


def test_filter_values_are_carried_by_buttons() -> None:
    """Anything that holds a filter *value* is a button with
    aria-pressed or aria-checked, so state is read one way."""

    js = _read("filter_controls.js")
    for fn in ("groupHtml", "menuGroupHtml"):
        start = js.index(f"function {fn}(spec)")
        block = js[start : js.index("\n  }", start)]
        assert "<input" not in block, f"{fn} must not use inputs"


def test_the_checkbox_exception_is_scoped_and_explained() -> None:
    """One control breaks the button rule: a boolean whose polarity has
    to be legible. "Show ignored" with a tick says which way it points;
    a pressed pill reading "Gitignored" does not."""

    js = _read("filter_controls.js")
    start = js.index("function checkHtml(spec)")
    block = js[start : start + 700]
    assert '<input type="checkbox"' in block
    assert "data-chip-check=" in block

    # Only the gitignored visibility toggle uses it.
    app = _read("app.js")
    assert app.count("fc.checkHtml(") == 1
    assert '"Show ignored"' in app


def test_extension_tallies_come_from_the_index_not_the_catalog() -> None:
    """catalog_files() drops gitignored entries by design, so a menu
    tallied from it undercounts every extension the tree still shows
    while gitignored rows are visible."""

    js = _read("app.js")
    start = js.index("function filterTypeOptions()")
    block = js[start : start + 1500]
    assert "_extensionTally" in block
    assert "knownFileCatalog" not in block
    # Tracked and ignored stay apart so the count follows the setting.
    assert "showIgnored ? row[1] + row[2] : row[1]" in block


def test_dropdown_rows_are_arrow_key_traversable() -> None:
    """A menu is a list, so it takes the vertical keys; the segmented
    groups take the horizontal ones."""

    js = _read("filter_controls.js")
    start = js.index("function onKeyDown(event)")
    block = js[start : start + 1200]
    assert '.closest(".chip-menu-panel")' in block
    assert '"ArrowDown"' in block
    assert '"ArrowUp"' in block
    assert ".chip-menu-item" in block


def test_all_three_dimensions_are_dropdowns() -> None:
    """Age, type, and size are dropdowns rather than segmented ramps:
    six joined segments each is a lot of pill for a 300px pane."""

    js = _read("app.js")
    fn_start = js.index("function renderNavFilterBar()")
    fn_block = js[fn_start : fn_start + 4200]
    assert fn_block.count("fc.menuGroupHtml(") == 3
    # Age and size pick one; type picks several.
    assert fn_block.count('select: "one"') == 2
    for label in ('"Any age"', '"Any type"', '"Any size"'):
        assert label in fn_block, f"missing any-label {label}"


def test_age_and_type_ride_the_always_visible_row() -> None:
    """Size and gitignored visibility sit behind the disclosure; the
    two dimensions people reach for do not."""

    js = _read("app.js")
    fn_start = js.index("function renderNavFilterBar()")
    fn_block = js[fn_start : fn_start + 4200]
    drawer_at = fn_block.index('class="filter-drawer"')
    assert fn_block.index('"Any age"') < drawer_at
    assert fn_block.index('"Any type"') < drawer_at
    assert fn_block.index('"Any size"') > drawer_at
    assert fn_block.index('"Show ignored"') > drawer_at


def test_option_lists_omit_the_any_value() -> None:
    """The menu's any-row *is* that value; listing it twice would
    offer the same choice under two names."""

    js = _read("app.js")
    for const in ("FILTER_RECENCY_OPTIONS", "FILTER_SIZE_OPTIONS"):
        start = js.index(f"var {const} = [")
        block = js[start : js.index("];", start)]
        assert 'value: "all"' not in block, f"{const} must not list the any value"


def test_single_select_dropdowns_close_on_pick() -> None:
    """The choice is made; a menu left hanging over the tree has
    nothing more to offer. Multi-select stays open by design."""

    js = _read("app.js")
    start = js.index("onMenuPick: (key, value) =>")
    block = js[start : start + 1200]
    assert 'if (key === "recency" || key === "size")' in block
    assert "filterOpenMenu = null;" in block


def test_only_one_dropdown_is_open_at_a_time() -> None:
    js = _read("app.js")
    start = js.index("onMenuToggle: (key, open) =>")
    block = js[start : start + 300]
    assert "filterOpenMenu = open ? key : null;" in block


def test_clear_is_only_rendered_when_something_is_set() -> None:
    js = _read("app.js")
    fn_start = js.index("function renderNavFilterBar()")
    fn_block = js[fn_start : fn_start + 3000]
    assert "count > 0" in fn_block


def test_drawer_toggle_is_an_icon_button_that_names_itself() -> None:
    """Every icon-only control in the app is the same control, so the
    drawer disclosure rides .icon-btn like the settings gear and the
    print button. A glyph has no accessible name of its own, so the
    aria-label describes the action and carries the count the badge
    shows visually."""

    js = _read("app.js")
    fn_start = js.index("function renderNavFilterBar()")
    fn_block = js[fn_start : fn_start + 3000]
    assert "icon: ICONS.toggle" in fn_block
    assert '"Hide more filters" : "Show more filters"' in fn_block
    assert "active)" in fn_block

    controls = _read("filter_controls.js")
    assert 'class="icon-btn' in controls

    css = _read("styles.css")
    # Only the rotation lives locally; geometry and hover come from the
    # primitive, which is what keeps it the same control.
    assert '.filter-drawer-toggle[aria-pressed="true"] svg' in css
    assert ".filter-drawer-toggle {" not in css


def test_menu_rows_use_type_icons_rather_than_tinted_labels() -> None:
    """The icon identifies the type everywhere else in the app; eight
    tinted row labels would compete with the check mark instead of
    helping anyone scan the list."""

    controls = _read("filter_controls.js")
    assert 'class="menu-item-icon ' in controls

    css = _read("styles.css")
    assert ".chip-menu-item .menu-item-icon {" in css
    # The dead per-chip tint rule is gone with the chip row it served.
    assert ".chip-ft" not in css
    assert "chip-ft" not in _read("app.js")


# ── Filter state ───────────────────────────────────────────────


def test_recency_is_one_dimension_including_live() -> None:
    """Live is the narrowest point on the recency axis, not a second
    boolean; "live but older than a week" is not a query."""

    js = _read("filter_state.js")
    assert 'const RECENCY_VALUES = ["all", "live", "1h", "24h", "7d", "30d"]' in js
    assert "current:" not in js
    assert "ageWindow" not in js


def test_defaults_leave_the_tree_unfiltered() -> None:
    """There is no dim/hide switch: filtering removes what does not
    match. The only display choice left is gitignored visibility, and
    it defaults to the tree's long-standing dimmed treatment."""

    js = _read("filter_state.js")
    start = js.index("const DEFAULTS = Object.freeze({")
    block = js[start : start + 600]
    assert 'recency: "all"' in block
    assert 'size: "all"' in block
    assert "showIgnored: true" in block
    assert "mode:" not in js
    assert "tree-item-filter-dim" not in _read("app.js")


def test_size_is_a_cumulative_floor() -> None:
    """ "What is over 10M in here" is the question people ask; bands
    make you guess which one a file landed in."""

    js = _read("filter_state.js")
    start = js.index("const SIZE_MIN_BYTES = {")
    block = js[start : start + 400]
    for step in ('"100k"', '"1m"', '"10m"', '"100m"', '"1g"'):
        assert step in block, f"missing size step {step}"
    match_start = js.index("function sizeMatches(bytes, bucket)")
    assert "bytes >= floor" in js[match_start : match_start + 500]


def test_missing_data_never_excludes_a_row() -> None:
    """A pending size or an absent mtime is incomplete information,
    not a non-match — rows must not flicker as filtered while data is
    still arriving. A missing extension is different: that is complete
    information, so it is a real non-match."""

    js = _read("filter_state.js")
    size_start = js.index("function sizeMatches(bytes, bucket)")
    size_block = js[size_start : size_start + 500]
    assert "return true; // pending size is unknown, not excluded" in size_block

    type_start = js.index("function typeMatches(pathLike, types, logicalExt)")
    type_block = js[type_start : type_start + 1200]
    assert "return false;" in type_block


def test_type_presets_name_broad_kinds_of_work() -> None:
    """Docs / Code / Data are shorthands for the full extension list
    beneath them, and a deliberately separate vocabulary from
    FILE_TYPES: that list answers "what icon and hue does this file
    get" (which is why .json sits with YAML there), these answer "which
    kind of work is this"."""

    js = _read("app.js")
    start = js.index("var FILTER_TYPE_PRESETS = [")
    block = js[start : js.index("\n];", start)]
    for label in ('"Docs"', '"Code"', '"Data"'):
        assert label in block

    # The convention: leading dot is an extension, anything else a
    # whole filename. Docs reaches README and LICENSE only because of it.
    assert '"readme"' in block
    assert '"license"' in block
    assert '".md"' in block

    state = _read("filter_state.js")
    tm_start = state.index("function typeMatches(pathLike, types, logicalExt)")
    tm_block = state[tm_start : tm_start + 1400]
    assert 'token.charAt(0) === "."' in tm_block
    assert "name === token" in tm_block


def test_the_drawer_always_opens_closed() -> None:
    """Its state is deliberately not persisted: it holds the secondary
    controls, so restoring it open spends vertical space asked for on
    a previous visit. The filters do persist, and the badge reports
    them either way."""

    js = _read("app.js")
    assert "filters.drawer" not in js
    start = js.index("function initFilterBar()")
    block = js[start : start + 600]
    assert "filterDrawerOpen = false;" in block


def test_the_tally_and_its_filtered_count_read_as_one_block() -> None:
    """The totals are what the filtered figure reads against, so the
    rule goes under the pair rather than between them."""

    css = _read("styles.css")
    start = css.index(".tree-summary:has(+ .tree-summary-filtered)")
    block = css[start : css.index("}", start)]
    assert "border-bottom: none;" in block
    assert "padding-bottom: 0;" in block


def test_a_closed_bar_is_vertically_symmetric() -> None:
    """The nav column is a stack of bands that all keep the same 6px.
    A standing row-gap broke that: it survived the drawer collapsing to
    zero height, so a closed bar sat 6px lower than it sat high. The gap
    belongs to the drawer being open, so it is gated on that."""

    css = _read("styles.css")
    start = css.index(".nav-filter-bar {")
    block = css[start : start + 700]
    assert "row-gap: 0;" in block
    assert "column-gap: 6px;" in block
    assert '.nav-filter-bar:has(.filter-drawer[data-open="true"])' in css


def test_nothing_inside_the_drawer_track_carries_its_own_spacing() -> None:
    """`overflow` clips a content box, not a padding or margin box, so
    either one on the grid item survives the 0fr track and leaves a
    sliver of drawer visible below a closed bar."""

    css = _read("styles.css")
    start = css.index(".filter-drawer > * {")
    block = css[start : css.index("}", start)]
    for prop in ("padding", "margin"):
        assert prop not in block, f".filter-drawer > * must not set {prop}"


def test_the_first_tree_row_clears_the_tally_rule() -> None:
    """A tree row's 2px is sized for the distance between rows, not for
    the distance from a rule, so the first one landed hard against the
    tally's border while every band above kept 6px."""

    css = _read("styles.css")
    start = css.index(".tree-summary + .tree-item,")
    block = css[start : css.index("}", start)]
    # Both leading cases: the tally, and rows alone under a recency window.
    assert ".tree-summary-filtered + .tree-item" in block
    assert ".tree-content > * > .tree-item:first-child" in block
    # Margin, so the hover fill and selected border stay row-height.
    assert "margin-top" in block
    assert "padding-top" not in block


def test_the_overlay_stops_when_the_recency_window_is_cleared() -> None:
    """Leaving the source sets the window to "", and an unknown key
    gives `undefined`, not `null`. The old `!== null` guard let that
    through, so the cutoff became NaN, every comparison against it was
    false, and the base map grew without bound behind the plain tree."""

    js = _read("app.js")
    start = js.index("function recentBaseApplyOp(op)")
    block = js[start : start + 1600]
    assert "if (!currentRecentWindow) {" in block
    assert 'typeof seconds === "number"' in block


def test_live_overlay_rows_carry_the_index_extension() -> None:
    """recentEntryFromFsEntry mirrors _file_entry_to_recent_dict; without
    the compound tail a file reaching the panel only through the overlay
    is matched on its last suffix while rendered rows are matched on the
    tail, so a compound pick hides it."""

    js = _read("app.js")
    start = js.index("function recentEntryFromFsEntry(entry)")
    block = js[start : start + 900]
    assert "ext: entry.ext" in block


def test_the_recency_tally_is_recomputed_not_cached() -> None:
    """Type and size changes run applyTreeFilters alone, so a count
    cached at render time kept its previous value while rows updated."""

    js = _read("app.js")
    assert "_recentFilteredCount" not in js
    start = js.index("function applyTreeFilters()")
    block = js[start : start + 4200]
    assert "countRecentMatches(" in block


def test_the_filtered_tally_shows_whenever_anything_is_filtered() -> None:
    """ "How many am I looking at" is the question a filter raises every
    time, not only when a response was capped."""

    js = _read("app.js")
    start = js.index("function _renderFilteredTally(panel, shownFiles, state, recencyCount)")
    block = js[start : start + 1600]
    assert "filterHasConstraints(state)" in block
    assert "Filtered to ${" in block
    # The "of N matching" half is the capped-response disclosure only.
    assert "recentTruncated" in block

    # Removing the last filter must clear the line, and that path is
    # the unconstrained early return.
    apply_start = js.index("function applyTreeFilters()")
    apply_block = js[apply_start : apply_start + 1400]
    assert "_renderFilteredTally(panel, 0, st, null);" in apply_block


def test_the_recency_tally_counts_entries_not_rendered_rows() -> None:
    """renderTreeNodes pages at TREE_PAGE_SIZE, so a DOM count reports
    how much has been paged in rather than how many files passed."""

    js = _read("app.js")
    assert "function countRecentMatches(entries, nowSec)" in js
    start = js.index("function _renderFilteredTally(panel, shownFiles, state, recencyCount)")
    block = js[start : start + 1600]
    assert "recencyCount !== null ? recencyCount : shownFiles" in block


def test_the_recency_cap_records_why_it_is_where_it_is() -> None:
    """The bound is the per-burst re-cluster, not first render, and the
    number should not drift without someone re-measuring."""

    settings = (proc_browser.STATIC_DIR.parent / "settings.py").read_text()
    start = settings.index("RECENT_DEFAULT_WINDOW")
    block = settings[start : start + 1400]
    assert "RECENT_RECLUSTER_DEBOUNCE_MS" in block
    assert "RECENT_DEFAULT_LIMIT = 5_000" in block
    assert "RECENT_MAX_LIMIT = 5_000" in block


def test_the_extension_list_is_hard_capped() -> None:
    """Appending selected-but-unranked tokens let one preset add dozens
    of rows — extensions the folder does not contain, and bare filename
    tokens like "makefile" listed as if they were suffixes."""

    js = _read("app.js")
    assert "var FILTER_TYPE_MENU_MAX = 20;" in js
    start = js.index("function filterTypeOptions()")
    block = js[start : start + 1800]
    assert "ranked.slice(0, FILTER_TYPE_MENU_MAX)" in block
    # Nothing is pushed back in past the cap.
    assert "kept.push(" not in block


def test_filters_reapply_when_new_rows_render() -> None:
    """Lazy subtrees and deferred pages arrive unfiltered; without a
    reapply, expanding a folder under an active filter shows all of
    its children."""

    js = _read("app.js")
    sub_start = js.index("async function loadSubtree(")
    assert "applyTreeFilters();" in js[sub_start : sub_start + 2500]
    page_start = js.index(".tree-page-more")
    assert "applyTreeFilters();" in js[page_start : page_start + 700]


def test_leaving_the_recency_source_abandons_its_fetch() -> None:
    """A late /api/recent response would otherwise repaint the panel
    with the old window's list under a trigger reading "Any age"."""

    js = _read("app.js")
    start = js.index("function onFilterStateChange(state)")
    block = js[start : start + 1800]
    assert "recentInflight.abort()" in block
    assert 'currentRecentWindow = ""' in block


def test_the_summary_poll_does_not_disturb_an_open_menu() -> None:
    """It runs repeatedly while the index warms up; rebuilding the bar
    would drop focus out of a dropdown being arrowed through."""

    js = _read("app.js")
    start = js.index("function scheduleRootSummaryRefresh()")
    block = js[start : start + 1800]
    assert "filterOpenMenu === null" in block
    # Both caches move together, or the tally reverts to first-paint
    # figures under a recency filter.
    assert "_lastTreeSummaryHtml = html;" in block


def test_index_wide_tallies_stay_off_the_event_loop() -> None:
    """Two O(index) passes per request, and the nav re-requests this
    route while the walk converges."""

    py = (proc_browser.STATIC_DIR.parent / "server.py").read_text()
    start = py.index("summary = None")
    block = py[start : start + 700]
    assert "asyncio.to_thread" in block
    assert "root_summary()" in block
    assert "extension_tally()" in block


def test_reapply_is_skipped_when_nothing_is_filtered() -> None:
    """fs bursts would otherwise walk the whole tree every 100ms in the
    default state."""

    js = _read("app.js")
    start = js.index("function scheduleFilterReapply()")
    block = js[start : start + 600]
    assert "filterHasConstraints(filterState.get())" in block


def test_compound_extensions_match_what_the_menu_counted() -> None:
    """The tally keys on the index's compound tail (".min.js"), so
    matching must too. Reducing to the last dotted suffix turned every
    compound row into ".js" and made a compound pick match nothing it
    was offered for."""

    js = _read("filter_state.js")
    start = js.index("function typeMatches(pathLike, types, logicalExt)")
    block = js[start : start + 1200]
    assert "logicalExt || extensionOf(pathLike)" in block

    # The row carries it, and both tree sources supply it.
    app = _read("app.js")
    assert "ext: row.dataset.ext" in app
    recent = (proc_browser.STATIC_DIR.parent / "recent.py").read_text()
    assert '"ext": entry.ext,' in recent


def test_filter_state_persists_through_prefs_and_emits_change() -> None:
    js = _read("filter_state.js")
    assert 'const PREF_KEY = "filters"' in js
    assert '"metabrowser:filter-change"' in js
    assert "mb?.prefs" in js


def test_sdk_exposes_prefs_and_filters() -> None:
    """Plugin views bind to the shared vocabulary through the
    documented SDK rather than reaching for the global."""

    js = _read("plugin_sdk.js")
    assert "prefs: prefs," in js
    assert "filters: filters," in js


# ── Applying filters to the tree ───────────────────────────────


def test_no_filters_leaves_the_rendered_dom_alone() -> None:
    """Filtering is a decoration layer, not a render fork: with
    nothing set, the pass removes its own classes and returns."""

    js = _read("app.js")
    fn_start = js.index("function applyTreeFilters()")
    fn_block = js[fn_start : fn_start + 1200]
    assert "if (!constrained) {" in fn_block
    assert 'rows[c].classList.remove("tree-item-filter-hidden")' in fn_block


def test_folders_with_no_loaded_children_are_kept_and_counted() -> None:
    """An unexpanded folder is unknown, not excluded. Hide mode says
    so instead of implying the pruned tree is the whole answer."""

    js = _read("app.js")
    fn_start = js.index("function applyTreeFilters()")
    fn_block = js[fn_start : fn_start + 3000]
    assert "unloadedFolders += 1" in fn_block
    note_start = js.index("function _renderFilterNote(panel, unloadedFolders, state)")
    note_block = js[note_start : note_start + 1600]
    assert "not expanded yet" in note_block
    assert 'note.setAttribute("role", "status")' in note_block


def test_hidden_folders_suppress_their_descendants() -> None:
    """Otherwise a matching row could survive inside a pruned subtree
    and float under the wrong parent."""

    js = _read("app.js")
    fn_start = js.index("function applyTreeFilters()")
    fn_block = js[fn_start : fn_start + 4200]
    assert "suppressed.add(kidContainer)" in fn_block
    assert "suppressed.has(el.parentElement)" in fn_block


def test_filters_reapply_after_live_row_inserts() -> None:
    """A file written while a filter is active must not appear just
    because it arrived over the event stream."""

    js = _read("app.js")
    assert "function scheduleFilterReapply()" in js
    # applyCellPatch owns both live paths: patching an existing row
    # (mtime and activity can flip its verdict) and inserting a new one.
    patch_start = js.index("function applyCellPatch(entry)")
    patch_block = js[patch_start : js.index("function _removeRenderedRows(path)")]
    assert patch_block.count("scheduleFilterReapply()") == 2


# ── Wiring ─────────────────────────────────────────────────────


def test_index_loads_filter_modules_before_app() -> None:
    """filter_state.js registers the global app.js reads at load, and
    filter_controls.js supplies the markup it renders."""

    html = _render_index_html()
    assert 'src="/static/filter_state.js?v=' in html
    assert 'src="/static/filter_controls.js?v=' in html
    assert html.index("/static/filter_state.js") < html.index("/static/app.js")
    assert html.index("/static/filter_controls.js") < html.index("/static/app.js")


def test_dom_content_loaded_initializes_the_filter_bar() -> None:
    js = _read("app.js")
    handler_start = js.rindex('addEventListener("DOMContentLoaded", async () =>')
    handler_block = js[handler_start : handler_start + 3000]
    assert "initFilterBar();" in handler_block


def test_nav_filter_bar_does_not_share_the_plugin_filter_bar_name() -> None:
    """The agent-log plugin already owned `.filter-bar`, and its
    `margin: 8px 0 12px` leaked into the navigation column — 20px of
    dead space above the tally that no nav rule asked for. Distinct
    names are what keep the two apart."""

    css = _read("styles.css")
    assert ".nav-filter-bar {" in css
    # The plugin's rule keeps the old name and its margin.
    plugin_start = css.index("/* ── Event filter bar ")
    plugin_block = css[plugin_start : plugin_start + 500]
    assert ".filter-bar {" in plugin_block
    assert "margin: 8px 0 12px 0;" in plugin_block

    # The nav bar sets no margin of its own, so nothing can leak back.
    nav_start = css.index(".nav-filter-bar {")
    nav_block = css[nav_start : css.index("}", nav_start)]
    assert "margin" not in nav_block

    assert 'id="nav-filter-bar"' in _render_index_html()


def test_the_navigation_column_shares_one_left_inset() -> None:
    """Brand, path, tab label, filter chips, tally, and tree rows all
    land on the same edge. A control with internal padding cancels it
    so its text sits on the inset; the tree row reaches the same 12px
    as padding plus its selection bar."""

    css = _read("styles.css")
    assert "--pane-header-padding-x: 12px;" in css

    # The tab bar subtracts the tab's own padding rather than adding to it.
    nav_tab_start = css.index(".tab-bar.nav-tab-bar {")
    nav_tab_block = css[nav_tab_start : css.index("}", nav_tab_start)]
    assert "calc(var(--pane-header-padding-x) - var(--file-tab-padding-x))" in nav_tab_block

    # Tree row: 10px padding + 2px selection bar = the same 12px.
    row_start = css.index(".tree-item {")
    row_block = css[row_start : css.index("}", row_start)]
    assert "padding: 2px 12px 2px 10px;" in row_block
    assert "border-left: 2px solid transparent;" in row_block


def test_recency_fetch_carries_the_gitignored_setting() -> None:
    """Gitignored visibility is a server-side parameter here, not just
    a row class: it decides what the response cap is spent on. A day
    window on a repository with node_modules returned 2,000 ignored
    entries and none of the user's own files."""

    js = _read("app.js")
    assert "&include_ignored=0" in js
    # Changing it has to refetch, not just re-decorate.
    start = js.index("function onFilterStateChange(state)")
    block = js[start : start + 1400]
    assert "_filterLastShowIgnored !== state.showIgnored" in block
    assert "ignoredChanged" in block


def test_live_survives_the_gap_between_tracker_polls() -> None:
    """The tracker polls every 5s but the watcher emits an upsert per
    append, carrying a stale `active: false` in between. Mirroring
    that straight into the filter made a file being written once a
    second flicker in and out of the tree."""

    js = _read("app.js")
    assert "const FILTER_LIVE_PERSIST_MS = 90_000;" in js
    # The filter reads a persisted set, not activeFiles directly.
    apply_start = js.index("function applyTreeFilters()")
    apply_block = js[apply_start : apply_start + 3000]
    assert "livePathsForFilter()" in apply_block
    assert "activeFiles.has(" not in apply_block
    # Writing stops, no more events arrive; something has to re-check.
    assert "function scheduleLiveExpiryRecheck()" in js


def test_age_menu_rows_reuse_the_tree_freshness_ramp() -> None:
    """Live is the under-a-minute red because a file being written now
    is that bucket; each window then takes the colour of the bucket it
    tops out at."""

    js = _read("app.js")
    start = js.index("var FILTER_RECENCY_OPTIONS = [")
    block = js[start : js.index("];", start)]
    for value, age in (
        ('"live"', "age-sec"),
        ('"1h"', "age-min"),
        ('"24h"', "age-hr"),
        ('"7d"', "age-day"),
        ('"30d"', "age-wk"),
    ):
        line = next(ln for ln in block.splitlines() if value in ln)
        assert f'ageClass: "{age}"' in line, f"{value} should wear {age}"

    # Scoped to the menu: the tree's ramp is contrast-audited.
    css = _read("styles.css")
    assert ".chip-menu-item.age-min {" in css


def test_clear_sits_with_the_dropdowns_it_undoes() -> None:
    """Not in the drawer: it can only appear when something is set, and
    opening the drawer to undo a filter set from the row above is a
    step too many. Short label so it shares the row."""

    js = _read("app.js")
    fn_start = js.index("function renderNavFilterBar()")
    fn_block = js[fn_start : fn_start + 4200]
    clear_at = fn_block.index("fc.clearHtml(")
    assert clear_at < fn_block.index('class="filter-drawer"')
    assert '{ label: "Clear" }' in fn_block


def test_a_constrained_dropdown_trigger_looks_set() -> None:
    """A collapsed control must not require reading its label to know
    whether it is filtering."""

    js = _read("filter_controls.js")
    assert 'data-active="${selected.length > 0}"' in js

    css = _read("styles.css")
    start = css.index('.chip-menu-trigger[data-active="true"]')
    block = css[start : css.index("}", start)]
    assert "var(--highlight-bg)" in block
    assert "var(--link)" in block


def test_the_drawer_animates_open_and_stays_out_of_reach_when_closed() -> None:
    """A display toggle cannot transition, so the drawer animates a
    grid track and uses `inert` for the closed state."""

    css = _read("styles.css")
    start = css.index(".filter-drawer {")
    block = css[start : css.index("}", start)]
    assert "grid-template-rows: 0fr;" in block
    assert "transition: grid-template-rows var(--transition-fast);" in block
    assert '.filter-drawer[data-open="true"]' in css
    # Reduced motion still changes state, just without the travel.
    reduced = css[css.index("@media (prefers-reduced-motion: reduce)") :]
    assert ".filter-drawer," in reduced

    js = _read("app.js")
    assert '" inert"' in js
    # The old `hidden` attribute would reintroduce display: none.
    assert '" hidden"' not in js
    # Re-rendering would replace the node and snap it open.
    assert "function applyDrawerOpenState()" in js


def test_the_nav_column_shares_one_vertical_rhythm() -> None:
    """The tally row and the filter bar are both one-line bordered
    bands of chrome, so they get the same padding; .tree-content adds
    nothing on top of it."""

    css = _read("styles.css")
    bar_start = css.index(".nav-filter-bar {")
    assert "padding: 6px var(--pane-header-padding-x);" in css[bar_start : bar_start + 900]

    sum_start = css.index(".tree-summary {")
    sum_block = css[sum_start : css.index("}", sum_start)]
    assert "padding: 6px 12px;" in sum_block
    assert "margin-bottom" not in sum_block

    content_start = css.index(".tree-content {")
    assert "padding: 0 0 8px;" in css[content_start : content_start + 300]


def test_scroll_shadow_rides_the_filter_bar() -> None:
    """The filter bar is the bottom-most chrome above the scroll
    owner, so a shadow on the tab bar would land on the bar instead
    of on the content."""

    js = _read("app.js")
    fn_start = js.index("function initNavScrollShadow()")
    fn_block = js[fn_start : fn_start + 900]
    assert 'document.getElementById("nav-filter-bar")' in fn_block
    css = _read("styles.css")
    assert ".nav-filter-bar.scrolled {" in css
