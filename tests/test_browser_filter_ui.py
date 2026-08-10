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


def test_every_control_is_a_button_with_pressed_or_checked_state() -> None:
    """One state mechanism, not two: no hidden checkbox inputs whose
    state has to be read a different way."""

    js = _read("filter_controls.js")
    assert 'type="checkbox"' not in js
    assert "input:checked" not in js


def test_clear_is_only_rendered_when_something_is_set() -> None:
    js = _read("app.js")
    fn_start = js.index("function renderNavFilterBar()")
    fn_block = js[fn_start : fn_start + 3000]
    assert "count > 0" in fn_block


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

    type_start = js.index("function typeMatches(pathLike, types)")
    type_block = js[type_start : type_start + 800]
    assert "return false;" in type_block


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
    note_block = js[note_start : note_start + 900]
    assert "not expanded yet" in note_block
    assert 'note.setAttribute("role", "status")' in note_block


def test_hidden_folders_suppress_their_descendants() -> None:
    """Otherwise a matching row could survive inside a pruned subtree
    and float under the wrong parent."""

    js = _read("app.js")
    fn_start = js.index("function applyTreeFilters()")
    fn_block = js[fn_start : fn_start + 3500]
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


def test_scroll_shadow_rides_the_filter_bar() -> None:
    """The filter bar is the bottom-most chrome above the scroll
    owner, so a shadow on the tab bar would land on the bar instead
    of on the content."""

    js = _read("app.js")
    fn_start = js.index("function initNavScrollShadow()")
    fn_block = js[fn_start : fn_start + 900]
    assert 'document.getElementById("filter-bar")' in fn_block
    css = _read("styles.css")
    assert ".filter-bar.scrolled {" in css
