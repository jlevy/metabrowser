"""Structural tests for the filter control family and the nav filter bar.

The chip family is a design-system commitment as much as a component:
single-select and multi-select must stay visually and semantically
distinguishable, and every filtering surface must draw from the same
rules. These tests pin the parts of that contract a refactor could
quietly break.

Behavioural checks for the selection semantics live in
tests/dom/filter-controls-behavior.js and
tests/dom/filter-state-behavior.js.
"""

from __future__ import annotations

import asyncio
import inspect
import re
from pathlib import Path
from typing import Any, cast

from metabrowser import server as proc_browser
from metabrowser.file_type_filters import FILTER_TYPE_PRESETS
from metabrowser.inventory_engine.tree_page_assembly import assemble_tree_pages


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


def test_treemap_uses_shared_controls_for_metric_and_scope() -> None:
    """One reusable owner renders the metric and scope controls.

    Files and Treemap mount the same stateful component, so neither view
    can fork its labels, accessibility semantics, defaults, or preference key.
    """

    folder_root = proc_browser.STATIC_DIR.parent / "builtin_plugins" / "folder"
    controls = (folder_root / "rollup-controls.js").read_text()
    treemap = (folder_root / "treemap.js").read_text()
    file_totals = (folder_root / "file-totals-panel.js").read_text()
    file_types = (folder_root / "file-type-summary.js").read_text()
    overview_panel = (folder_root / "file-overview-panel.js").read_text()
    plugin_css = (folder_root / "styles.css").read_text()

    assert "filterControls.groupHtml" in controls
    assert 'label: "Measure file rollups by"' in controls
    assert "filterControls.checkHtml" in controls
    assert 'label: "Show ignored"' in controls
    assert "includeIgnored: value.includeIgnored !== false" in controls

    # Both views mount one row carrying both halves, because the measure and
    # the gitignore switch are the same kind of choice about the same numbers
    # and splitting them meant each silently moved the other's. No parts
    # argument is what asks for both, so the absence of one is the assertion.
    assert "rollupControls.mount(controls)" in overview_panel
    assert "rollupControls.mount(rollupControlsHost)" in treemap
    assert "metric: true" not in treemap
    assert "ignored: true" not in treemap
    # And neither body owns a control row any more.
    for body in (file_totals, file_types):
        assert "rollupControls.mount(" not in body
    assert "segmentHtml" not in controls
    assert ".tm-seg" not in plugin_css


def test_folder_rollups_use_coordinated_totals_and_breakdown_sections() -> None:
    """Overview keeps one selected metric across totals and details.

    Files, Ignored, and type rows must switch together instead of retaining
    parallel Files and Size columns that compete with the chooser.
    """

    folder_root = proc_browser.STATIC_DIR.parent / "builtin_plugins" / "folder"
    index = (folder_root / "index.js").read_text()
    totals = (folder_root / "folder-totals.js").read_text()
    file_totals = (folder_root / "file-totals-panel.js").read_text()
    file_types = (folder_root / "file-type-summary.js").read_text()
    overview_panel = (folder_root / "file-overview-panel.js").read_text()
    distribution = (folder_root / "distribution-view.js").read_text()
    treemap = (folder_root / "treemap.js").read_text()

    assert 'label: "File Overview"' in overview_panel
    assert "defaultExpanded: true" in overview_panel
    assert '"folder.file-overview"' in index
    assert '<h2 class="tm-totals-heading">Files</h2>' in treemap
    assert "mountFolderTotalsView" in file_totals
    assert "mountFolderTotalsView" not in file_types
    # The bodies stay separate modules and the section composes them, so the
    # merge is a heading and a control row rather than an entanglement of two
    # different data lifecycles.
    assert "mountFileTotalsPanel" in overview_panel
    assert "mountFileTypeSummary" in overview_panel
    assert 'filesRow = totalsRow("Files")' in totals
    # Total was once left out because the two disjoint rows already sum to it.
    # It is back because the type distribution below counts against that sum
    # whenever Show ignored is on, so without it no percentage in the
    # distribution corresponds to any track a reader can see.
    assert 'allRow = totalsRow("Total")' in totals
    assert "body.append(filesRow.tr, ignoredRow.tr, allRow.tr)" in totals
    # And Show ignored cannot reach the totals rows at all: the builder does
    # not take it, so the invariant is structural rather than observed.
    assert "buildFolderTotalsComposition(envelope, fileTypes, metric)" in totals
    assert "includeIgnored" not in totals.split("export function buildFolderTotalsComposition")[1]
    assert 'head.className = "sr-only"' in totals
    assert 'for (const label of ["Population", "Files", "Size"])' not in totals
    assert 'for (const label of ["Type", "Files", "Size"])' not in distribution
    assert "metricHeader" in distribution
    # The totals table hides its header row with `sr-only`, which is defined in
    # the shared stylesheet rather than here. It used to be scoped to this
    # plugin's own ancestors, which silently left the same class inert
    # everywhere else; see test_browser_loading_delay.py.
    assert ".sr-only" in (proc_browser.STATIC_DIR / "styles.css").read_text()


def test_treemap_hover_never_promotes_a_container_over_nested_cells() -> None:
    """A nested folder and its descendants are flattened siblings.

    Hover may adjust the folder fill, but changing its stacking level would
    paint the folder over every descendant rectangle inside it.
    """

    folder_root = proc_browser.STATIC_DIR.parent / "builtin_plugins" / "folder"
    shared_css = (proc_browser.STATIC_DIR / "styles.css").read_text()
    plugin_css = (folder_root / "styles.css").read_text()
    hover_start = plugin_css.index(".tm-cell:hover {")
    hover_block = plugin_css[hover_start : plugin_css.index("}", hover_start)]

    assert "filter: var(--viz-data-mark-hover-filter);" in hover_block
    # The direction that gains contrast against the page flips between themes,
    # so the token is declared for the light palette and again for the dark one.
    # Pinning the declarations rather than their values leaves the filter free
    # to be adjusted without editing this test.
    dark_start = shared_css.index('[data-theme="dark"] {')
    assert "--viz-data-mark-hover-filter:" in shared_css[:dark_start]
    assert "--viz-data-mark-hover-filter:" in shared_css[dark_start:]
    assert "z-index" not in hover_block
    assert "display:" not in hover_block


def test_treemap_pointer_hit_testing_uses_the_full_actionable_cell() -> None:
    """Nested ARIA buttons stay on labels, but pointer activation uses
    the deepest visible cell rectangle rather than that label alone."""

    folder_root = proc_browser.STATIC_DIR.parent / "builtin_plugins" / "folder"
    treemap = (folder_root / "treemap.js").read_text()
    plugin_css = (folder_root / "styles.css").read_text()
    click_start = treemap.index('viewport.addEventListener("click"')
    click_block = treemap[click_start : treemap.index('viewport.addEventListener("mouseover"')]

    assert 'cls.push("tm-actionable")' in treemap
    assert "cellForElement" in click_block
    assert "cellIsActionable(cell)" in click_block
    assert "actionableCellForElement" not in click_block
    assert ".tm-actionable {" in plugin_css
    assert "cursor: pointer;" in plugin_css[plugin_css.index(".tm-actionable {") :]
    assert ".tm-nested {\n  cursor: default;" not in plugin_css


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


def test_symlinks_use_the_lucide_icon_in_the_standard_leading_slot() -> None:
    """A link replaces the ordinary file icon; it is not an extra badge."""

    icons = _read("icons.js")
    app = _read("app.js")
    css = _read("styles.css")

    assert "fileSymlink: // Lucide `file-symlink`" in icons
    assert "ICONS.fileSymlink" in app
    assert 'class="tree-item tree-symlink' in app
    assert 'data-tip-type="symlink"' in app
    assert ".tree-symlink .tree-item-icon" in css


def test_wrapped_groups_are_chip_clusters_not_segmented_controls() -> None:
    """Segmented controls stay on one line. A long additive set wraps as
    individually bounded chips without an enclosing pill, so every visible
    shape remains an interactive target."""

    css = _read("styles.css")
    joined_start = css.index(".chip-group {")
    joined_block = css[joined_start : css.index("}", joined_start)]
    assert "flex-wrap: nowrap;" in joined_block

    wrapped_start = css.index('.chip-group[data-layout="wrap"] {')
    wrapped_block = css[wrapped_start : css.index("}", wrapped_start)]
    assert "flex-wrap: wrap;" in wrapped_block
    assert "gap: var(--chip-cluster-gap);" in wrapped_block
    assert "border: 0;" in wrapped_block
    assert "background: transparent;" in wrapped_block

    chip_start = css.index('.chip-group[data-layout="wrap"] > .chip {')
    chip_block = css[chip_start : css.index("}", chip_start)]
    assert "border: 1px solid var(--viz-border);" in chip_block
    assert "border-radius: var(--radius-pill);" in chip_block

    hover_start = css.index('.chip-group[data-layout="wrap"] > .chip:hover')
    hover_block = css[hover_start : css.index("}", hover_start)]
    assert "background: var(--hover-bg);" in hover_block


def test_groups_carry_the_aria_their_variant_implies() -> None:
    """Single-select is a radiogroup with aria-checked; multi-select
    is a plain group of aria-pressed toggles. Styling keys off these
    attributes, so drifting ARIA silently breaks the visuals too."""

    js = _read("filter-controls.js")
    assert 'select === "one" ? "radiogroup" : "group"' in js
    assert 'role="radio" aria-checked=' in js
    assert "aria-pressed=" in js


def test_single_select_group_is_one_tab_stop_with_arrow_keys() -> None:
    """Roving tabindex plus arrow-key traversal is the ARIA
    radiogroup pattern; multi-select chips stay individually
    reachable because each is an independent control."""

    js = _read("filter-controls.js")
    assert 'tabindex="${on ? "0" : "-1"}"' in js
    assert '"ArrowLeft"' in js
    assert '"ArrowRight"' in js
    assert '.chip-group[data-select="one"]' in js


def test_filter_values_are_carried_by_buttons() -> None:
    """Anything that holds a filter *value* is a button with
    aria-pressed or aria-checked, so state is read one way."""

    js = _read("filter-controls.js")
    for fn in ("groupHtml", "menuGroupHtml"):
        start = js.index(f"function {fn}(spec)")
        block = js[start : js.index("\n  }", start)]
        assert "<input" not in block, f"{fn} must not use inputs"


def test_filter_control_types_expose_the_wrapping_chip_layout() -> None:
    """Plugins must be able to select the documented chip-cluster layout
    without escaping the public SDK type contract."""

    types = _read("types.d.ts")
    assert 'layout?: "joined" | "wrap";' in types


def test_the_checkbox_exception_is_scoped_and_explained() -> None:
    """One control breaks the button rule: a boolean whose polarity has
    to be legible. "Show ignored" with a tick says which way it points;
    a pressed pill reading "Gitignored" does not."""

    js = _read("filter-controls.js")
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

    js = _read("filter-controls.js")
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

    controls = _read("filter-controls.js")
    assert 'class="icon-btn' in controls

    css = _read("styles.css")
    # Only the rotation lives locally; geometry and hover come from the
    # primitive, which is what keeps it the same control.
    assert '.filter-drawer-toggle[aria-pressed="true"] svg' in css
    assert ".filter-drawer-toggle {" not in css


def test_dropdown_triggers_use_the_shared_disclosure_chevron() -> None:
    """Menu triggers and the adjacent drawer disclosure should use one
    Lucide shape at the standard chrome glyph size, with rotation alone
    distinguishing their direction."""

    controls = _read("filter-controls.js")
    assert "window.MetabrowserIcons?.toggle" in controls
    assert "⌄" not in controls

    css = _read("styles.css")
    start = css.index(".chip-menu-caret {")
    block = css[start : start + 700]
    assert "var(--icon-glyph)" in block
    assert "rotate(90deg)" in block


def test_every_icon_only_control_carries_the_icon_button_primitive() -> None:
    """Use-site classes may position a button but may not recreate its control style."""

    server = Path(proc_browser.__file__).read_text()
    app = _read("app.js")
    sdk = _read("plugin-sdk.js")
    controls = _read("filter-controls.js")

    assert 'class="icon-btn settings-btn"' in server
    assert 'class="icon-btn icon-btn-reveal file-header-copy"' in app
    assert 'class="icon-btn file-header-icon file-header-print"' in app
    assert 'class="icon-btn icon-btn-reveal icon-btn-overlay content-copy-btn"' in sdk
    assert 'class="icon-btn${cls}"' in controls

    css = _read("styles.css")
    primitive = css[css.index("/* ── Icon buttons") : css.index("/* ── Settings toggle")]
    assert "\n.icon-btn {" in primitive
    for private_class in (
        "settings-btn",
        "file-header-icon",
        "file-header-copy",
        "content-copy-btn",
    ):
        assert f"\n.{private_class}," not in primitive
        assert f"\n.{private_class} {{" not in primitive


def test_plain_text_actions_use_the_shared_button_primitive() -> None:
    app = _read("app.js")
    css = _read("styles.css")

    # The text view's Load more moved out of the file header and into the
    # shared partial-content notice, but it is still the `.btn` primitive.
    sdk = _read("plugin-sdk.js")
    assert 'class="btn metabrowser-load-more"' in sdk
    assert "file-header-action" not in app, (
        "the header no longer restates partial progress; the notice owns it"
    )
    assert 'class="btn parent-nav-btn parent-nav-btn-icon-only folder-up"' in app
    assert '<span class="parent-nav-arrow" aria-hidden="true">↑</span>' in app
    assert ".btn {" in css
    assert ".btn:focus-visible {" in css
    assert ".parent-nav-btn {" in css
    assert ".parent-nav-btn-icon-only {" in css
    parent_nav = css[css.index(".parent-nav-btn {") : css.index(".parent-nav-btn-icon-only {")]
    assert "height: var(--icon-btn-size);" in parent_nav
    assert "border-color: var(--viz-border-strong);" in parent_nav
    assert 'aria-label="Open parent folder ${esc(parentLabel)}"' in app


def test_every_core_button_declares_non_submit_behavior() -> None:
    html = _render_index_html()
    for tag in re.findall(r"<button\b[^>]*>", html):
        assert 'type="button"' in tag

    for name in ("app.js", "filter-controls.js", "plugin-sdk.js"):
        source = _read(name)
        for match in re.finditer(r"<button\b", source):
            nearby_markup = source[match.start() : match.start() + 320]
            assert 'type="button"' in nearby_markup, f"{name}: {nearby_markup!r}"


def test_filter_surfaces_have_no_private_button_family() -> None:
    """Filter values come from filter-controls.js, never private button markup."""

    builtin_root = proc_browser.STATIC_DIR.parent / "builtin_plugins"
    sources = [_read("app.js"), _read("styles.css")]
    sources.extend(path.read_text() for path in builtin_root.glob("*/index.js"))
    sources.extend(path.read_text() for path in builtin_root.glob("*/styles.css"))
    combined = "\n".join(sources)

    for legacy_token in ("filter-btn", "data-filter-kind", 'class="filter-bar"'):
        assert legacy_token not in combined

    design = (
        proc_browser.STATIC_DIR.parent.parent.parent / "docs" / "design-system.md"
    ).read_text()
    assert "`window.metabrowser.filterControls`" in design
    assert "Do not handwrite chip markup" in design


def test_menu_rows_use_type_icons_rather_than_tinted_labels() -> None:
    """The icon identifies the type everywhere else in the app; eight
    tinted row labels would compete with the check mark instead of
    helping anyone scan the list."""

    controls = _read("filter-controls.js")
    assert 'class="menu-item-icon ' in controls

    css = _read("styles.css")
    assert ".chip-menu-item .menu-item-icon {" in css
    # The dead per-chip tint rule is gone with the chip row it served.
    assert ".chip-ft" not in css
    assert "chip-ft" not in _read("app.js")


# ── Filter state ───────────────────────────────────────────────


def test_recency_is_one_dimension_including_live() -> None:
    """Live is the narrowest recency window, not a specialized
    tracker flag or a second boolean dimension."""

    js = _read("filter-state.js")
    assert "const RECENCY_VALUES = Object.keys(RECENCY_SECONDS);" in js
    assert 's.recency === "live"' not in js
    assert "current:" not in js
    assert "ageWindow" not in js


def test_defaults_leave_the_tree_unfiltered() -> None:
    """There is no dim/hide switch: filtering removes what does not
    match. The only display choice left is gitignored visibility, and
    it defaults to the tree's long-standing dimmed treatment."""

    js = _read("filter-state.js")
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

    js = _read("filter-state.js")
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

    js = _read("filter-state.js")
    size_start = js.index("function sizeMatches(bytes, bucket)")
    size_block = js[size_start : size_start + 500]
    assert "return true; // pending size is unknown, not excluded" in size_block

    type_start = js.index("function typeMatches(pathLike, types, logicalExt)")
    type_block = js[type_start : type_start + 1200]
    assert "return false;" in type_block


def test_type_presets_name_registry_display_groups() -> None:
    """Registry groups are shorthands for the full declared membership
    beneath them and a deliberately separate vocabulary from
    FILE_TYPES: that list answers "what icon and hue does this file
    get" (which is why .json sits with YAML there), these answer "which
    kind of work is this"."""

    labels = [preset["label"] for preset in FILTER_TYPE_PRESETS]
    assert labels == [
        "Code",
        "Documentation",
        "Data",
        "Archives",
        "Media",
    ]

    settings = (proc_browser.STATIC_DIR.parent / "settings.py").read_text()
    assert '"FILTER_TYPE_PRESETS": FILTER_TYPE_PRESETS' in settings

    js = _read("app.js")
    assert "var FILTER_TYPE_PRESETS = _METABROWSER_SETTINGS.FILTER_TYPE_PRESETS || [];" in js

    # The convention: leading dot is an extension, anything else a
    # whole filename. Docs reaches README and LICENSE only because of it.
    docs = next(preset for preset in FILTER_TYPE_PRESETS if preset["id"] == "docs")
    assert "readme" in docs["values"]
    assert "license" in docs["values"]
    assert ".md" in docs["values"]

    code = next(preset for preset in FILTER_TYPE_PRESETS if preset["id"] == "code")
    assert ".mts" in code["values"]
    assert ".cts" in code["values"]

    state = _read("filter-state.js")
    assert "mb.filterState = {" in state
    assert "MetabrowserFilterState" not in state
    tm_start = state.index("function typeMatches(pathLike, types, logicalExt)")
    tm_block = state[tm_start : tm_start + 1400]
    assert 'token.charAt(0) === "."' in tm_block
    assert "name === token" in tm_block


def test_the_drawer_always_opens_closed() -> None:
    """Its state is deliberately not persisted: it holds the secondary
    controls, so restoring it open spends vertical space asked for on
    a previous visit. Active filters are transient, and the badge
    reports them while the drawer is closed."""

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
    start = css.index(".tree-summary + .tree-root > .tree-item:first-child,")
    block = css[start : css.index("}", start)]
    # Both leading cases: the tally, and rows alone under a recency window.
    assert ".tree-summary-filtered + .tree-root > .tree-item:first-child" in block
    assert ".tree-content > * > .tree-root:first-child > .tree-item:first-child" in block
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


def _apply_tree_filters_body(js: str) -> str:
    start = js.index("function applyTreeFilters()")
    return js[start : js.index("function _applyTreeSourceFilters(panel, state)")]


def test_the_recency_tally_is_recomputed_not_cached() -> None:
    """Type and size changes run applyTreeFilters alone, so a count
    cached at render time kept its previous value while rows updated."""

    js = _read("app.js")
    assert "_recentFilteredCount" not in js
    assert "countRecentMatches(" in _apply_tree_filters_body(js)


def test_the_filtered_tally_shows_whenever_anything_is_filtered() -> None:
    """ "How many am I looking at" is the question a filter raises every
    time, not only when a response was capped."""

    js = _read("app.js")
    start = js.index("function _renderFilteredTally(panel, state, count)")
    block = js[start : start + 1800]
    assert "filterHasConstraints(state)" in block
    assert "Filtered to ${" in block
    # The "of N matching" half is the capped-response disclosure only.
    assert "recentTruncated" in block
    assert "recentTotalMatchingExact" in block

    # Removing the last filter must clear the line, and that path is
    # the unconstrained early return.
    assert "_renderFilteredTally(panel, st, null);" in _apply_tree_filters_body(js)


def test_the_filtered_tally_counts_a_subtree_not_rendered_rows() -> None:
    """renderTreeNodes pages at TREE_PAGE_SIZE and the tree is depth-capped,
    so a DOM count reports how much has been paged in rather than how many
    files matched. Each source hands the line a subtree total instead: the
    server's for the tree, the window's own entries for recency."""

    js = _read("app.js")
    assert "function countRecentMatches(entries, nowSec)" in js
    assert "countRecentMatches(" in _apply_tree_filters_body(js)
    leaf_start = js.index("function _applyTreeSourceFilters(panel, state)")
    assert (
        "_filteredTreeTotals ? _filteredTreeTotals.files : null"
        in js[leaf_start : js.index("function _renderFilteredTally(")]
    )
    assert "_filteredTreeTotals = data.filtered || null;" in js


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


def test_type_presets_use_index_wide_tracked_and_ignored_tallies() -> None:
    """The aggregate rows must answer the same question as selecting
    them, including extensionless filenames and Show ignored."""

    js = _read("app.js")
    assert "var _typePresetTally = [];" in js
    start = js.index("function filterTypePresets()")
    block = js[start : start + 1000]
    assert "showIgnored ? row[1] + row[2] : row[1]" in block
    assert "count:" in block
    tally_start = js.index("function updateFilterTallies(data)")
    tally_block = js[tally_start : tally_start + 1800]
    assert "registryMismatch" not in tally_block
    assert "file_type_registry" not in tally_block

    render_start = js.index("function renderNavFilterBar()")
    render_block = js[render_start : render_start + 2200]
    assert "presetSections: filterTypePresetSections()" in render_block
    assert "function filterTypeFamilies(groupId)" in js
    assert "window.MetabrowserFileTypeTaxonomy?.groups" in js
    assert "_typeFamilyTally" in js


def test_age_options_use_index_wide_tracked_and_ignored_tallies() -> None:
    """Every fixed age choice carries the same right-aligned count as a
    file-type row, and the count follows Show ignored."""

    js = _read("app.js")
    assert "var _recencyTally = [];" in js
    start = js.index("function filterRecencyOptions()")
    block = js[start : start + 1000]
    assert "showIgnored ? row[1] + row[2] : row[1]" in block
    assert "count:" in block

    render_start = js.index("function renderNavFilterBar()")
    render_block = js[render_start : render_start + 2200]
    assert "options: filterRecencyOptions()" in render_block


def test_opening_age_menu_refreshes_rolling_tallies() -> None:
    """Age membership changes as time passes even when no filesystem event fires."""

    js = _read("app.js")
    toggle_start = js.index("onMenuToggle: (key, open) =>")
    toggle_block = js[toggle_start : toggle_start + 500]
    assert 'key === "recency" && open' in toggle_block
    assert "scheduleRootSummaryRefresh();" in toggle_block

    refresh_start = js.index("function scheduleRootSummaryRefresh()")
    refresh_block = js[refresh_start : refresh_start + 2000]
    assert "patchOpenRecencyTallyCounts();" in refresh_block


def test_filters_reapply_when_new_rows_render() -> None:
    """Lazy subtrees and deferred pages arrive unfiltered; without a
    reapply, expanding a folder under an active filter shows all of
    its children."""

    js = _read("app.js")
    sub_start = js.index("async function loadSubtree(")
    assert "applyTreeFilters();" in js[sub_start : sub_start + 2500]
    page_start = js.index("function mountNextTreePage(row)")
    assert "applyTreeFilters();" in js[page_start : page_start + 1800]


def test_leaving_the_recency_source_abandons_its_fetch() -> None:
    """A late /api/recent response would otherwise repaint the panel
    with the old window's list under a trigger reading "Any age"."""

    js = _read("app.js")
    start = js.index("function onFilterStateChange(state)")
    block = js[start : start + 1800]
    assert "recentInflight.abort()" in block
    assert 'currentRecentWindow = ""' in block


def test_leaving_recency_refetches_the_authoritative_tree() -> None:
    """The cached first-paint tree can retain pending aggregates.

    Live events patch the visible DOM, not that old wire snapshot. Restoring it
    after a recency filter therefore reintroduced skeletons after the scan and
    its progress polling had completed.
    """

    js = _read("app.js")
    start = js.index("function onFilterStateChange(state)")
    block = js[start : start + 2200]
    assert "loadTree();" in block
    assert "renderFilesFromTree()" not in block


def test_the_summary_poll_does_not_disturb_an_open_menu() -> None:
    """It runs repeatedly while the index warms up; rebuilding the bar
    would drop focus out of a dropdown being arrowed through."""

    js = _read("app.js")
    start = js.index("function scheduleRootSummaryRefresh()")
    # Slice to the next top-level function rather than a fixed character
    # count: a comment added inside this one pushed the last assertion out
    # of an 1800-character window and failed a behavior that had not changed.
    block = js[start : js.index("\nfunction ", start + 1)]
    assert "filterOpenMenu === null" in block
    # Both caches move together, or the tally reverts to first-paint
    # figures under a recency filter.
    assert "_lastTreeSummaryHtml = html;" in block


def _provider_tree_source() -> str:
    py = (proc_browser.STATIC_DIR.parent / "server.py").read_text()
    start = py.index("async def _read_tree_from_provider(")
    return py[start : py.index("\nasync def ", start + 1)]


def test_index_wide_tallies_stay_off_the_event_loop() -> None:
    """The route delegates the O(index) tally to the provider query.

    Provider implementations own scheduling and report their work counters;
    the request path must not copy or traverse retained entries itself.
    """

    block = _provider_tree_source()
    assert "NavigationQuery(" in block
    assert "RECENT_WINDOW_SECONDS.items()" in block
    assert "await assemble_tree_pages(" in block
    assert "asyncio.to_thread" not in block
    assert ".entries(scope=" not in block


def test_one_index_snapshot_serves_every_pass_a_request_makes() -> None:
    """Tree pages, filters, and navigation share one pinned host boundary."""

    block = _provider_tree_source()
    assembly = inspect.getsource(assemble_tree_pages)
    assert "FilteredTreeQuery(" in block
    assert "NavigationQuery(" in block
    assert "companion_queries=tuple(companion_queries)" in block
    assert "async with coordinator.read_session()" in assembly
    assert "at_version=pinned" in assembly
    assert ".rollup_revision()" not in block
    assert ".entries(scope=" not in block


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

    js = _read("filter-state.js")
    start = js.index("function typeMatches(pathLike, types, logicalExt)")
    block = js[start : start + 1200]
    assert "logicalExt || extensionOf(pathLike)" in block

    # The row carries it, and both tree sources supply it.
    app = _read("app.js")
    assert "ext: row.dataset.ext" in app
    recent = (proc_browser.STATIC_DIR.parent / "recent.py").read_text()
    assert '"ext": entry.ext,' in recent


def test_filter_state_is_transient_and_emits_change() -> None:
    js = _read("filter-state.js")
    assert 'const LEGACY_PREF_KEY = "filters"' in js
    assert '"metabrowser:filter-change"' in js
    assert "p.remove(LEGACY_PREF_KEY)" in js
    assert "p.set(LEGACY_PREF_KEY" not in js


def test_sdk_exposes_prefs_and_filters() -> None:
    """Plugin views bind to the shared vocabulary through the
    documented SDK rather than reaching for the global."""

    js = _read("plugin-sdk.js")
    assert "remove: prefsRemove" in js
    assert "prefs: prefs," in js
    assert "filters: filters," in js


# ── Applying filters to the tree ───────────────────────────────


def test_no_filters_leaves_the_rendered_dom_alone() -> None:
    """Filtering is a decoration layer, not a render fork: with
    nothing set, the pass removes its own classes and returns."""

    js = _read("app.js")
    fn_block = _apply_tree_filters_body(js)
    assert "if (!constrained) {" in fn_block
    assert 'rows[c].classList.remove("tree-item-filter-hidden")' in fn_block


def test_the_tree_source_asks_the_server_rather_than_judging_mounted_rows() -> None:
    """Whether a folder survives a filter, and what it rolls up to, are
    questions about a whole subtree — including the part this client was
    never sent. Deciding them from mounted rows listed every folder whose
    children had not loaded, then deleted it once expanding proved it held
    nothing. The filter travels with the request instead."""

    js = _read("app.js")
    assert "unloadedFolders" not in js
    assert "_renderFilterNote" not in js
    assert "contain additional matches." not in js

    # The request itself is built in the model, where it is testable without a
    # document (tests/dom/tree-filter-model-behavior.js); app.js only supplies
    # the current snapshot.
    assert "treeFilterModel.treeUrl(" in js
    assert "treeFilterModel.requestKey(" in js

    # A subtree cached under a wider filter is not an answer for a narrower
    # one, so the cache key carries the selection.
    key_start = js.index("function subtreeCacheKey(path)")
    key = js[key_start : js.index("}", js.index("return filter", key_start))]
    assert "treeFilterKey()" in key

    # And the tree source never re-decides a folder: it judges leaves only,
    # which is all that rows arriving live can get wrong.
    fn_block = _apply_tree_filters_body(js)
    tree_source = fn_block[: fn_block.index("var rows =")]
    assert "if (!filesPanelUsesRecentSource()) {" in tree_source
    assert "_applyTreeSourceFilters(panel, st);" in tree_source

    leaf_start = js.index("function _applyTreeSourceFilters(panel, state)")
    leaf_block = js[leaf_start : js.index("function _renderFilteredTally(")]
    assert ".tree-item.tree-file, .tree-item.tree-symlink" in leaf_block
    assert "tree-folder" not in leaf_block

    # And a filesystem burst must not repaint the panel: that would collapse
    # the tree under a reader every time anything on disk changed.
    reapply = js[js.index("function scheduleFilterReapply()") :][:900]
    assert "loadTree()" not in reapply
    assert "applyTreeFilters();" in reapply


def test_a_filter_that_excludes_where_you_are_standing_says_so() -> None:
    """Open a folder from a breadcrumb or a URL while a filter is on and the
    tree legitimately has no row for it, so nothing is selected. Naming the
    folder answers the question that raises.

    Deliberately a line and not a pinned row: keeping the selection in the
    tree means refetching as the reader navigates, and a refetch repaints the
    panel and collapses every folder they had open."""

    js = _read("app.js")
    start = js.index("function renderSelectionOutsideFilterNote(selectedPath)")
    block = js[start : start + 1800]
    assert "filterHasConstraints(filterState.get())" in block
    assert "escapePathForSelector(path)" in block
    # Named from the path being selected, not from currentPath: this runs
    # before navigateToPath commits it, so the latter is the folder just left.
    assert "selectedPath === undefined ? currentPath : selectedPath" in block
    assert "renderSelectionOutsideFilterNote(path);" in js
    assert "is outside this filter." in block
    assert 'note.setAttribute("role", "status")' in block

    # Written on selection change and on every repaint, or it would survive a
    # filter change that brought the folder back.
    select_block = js[js.index("function setSelectedPath(path)") :][:1400]
    assert "renderSelectionOutsideFilterNote(path);" in select_block
    assert "renderSelectionOutsideFilterNote(null);" in select_block
    assert js.count("renderSelectionOutsideFilterNote();") >= 3

    css = _read("styles.css")
    note_start = css.index(".tree-selection-note {")
    assert "var(--muted)" in css[note_start : css.index("}", note_start)]


def test_hidden_folders_suppress_their_descendants() -> None:
    """Otherwise a matching row could survive inside a pruned subtree
    and float under the wrong parent.

    The rule itself lives in static/tree-filter-model.js and is exercised
    there; this pins that app.js still routes the clustered source through it
    rather than growing a second copy of the walk."""

    js = _read("app.js")
    assert "treeFilterModel.clusterHiddenIds(" in _apply_tree_filters_body(js)
    model = _read("tree-filter-model.js")
    assert "function clusterHiddenIds(rows)" in model
    assert "hidden.has(row.parentId)" in model


def test_filters_reapply_after_live_row_inserts() -> None:
    """A file written while a filter is active must not appear just
    because it arrived over the event stream."""

    js = _read("app.js")
    assert "function scheduleFilterReapply()" in js
    # applyCellPatch owns both live paths: patching an existing row
    # (mtime and activity can flip its verdict) and inserting a new one.
    patch_start = js.index("function applyCellPatch(entry, highlightChange)")
    patch_block = js[patch_start : js.index("function _removeRenderedRows(path)")]
    assert patch_block.count("scheduleFilterReapply()") == 2


# ── Wiring ─────────────────────────────────────────────────────


def test_index_loads_filter_modules_before_app() -> None:
    """filter-state.js registers the global app.js reads at load, and
    filter-controls.js supplies the markup it renders."""

    html = _render_index_html()
    assert 'src="/static/filter-state.js?v=' in html
    assert 'src="/static/filter-controls.js?v=' in html
    app_script = html.index('<script src="/static/app.js')
    assert html.index("/static/filter-state.js") < app_script
    assert html.index("/static/filter-controls.js") < app_script


def test_index_loads_pending_tally_watchdog_before_app() -> None:
    html = _render_index_html()
    assert 'src="/static/pending-tally-diagnostics.js?v=' in html
    assert html.index("/static/pending-tally-diagnostics.js") < html.index(
        '<script src="/static/app.js'
    )


def test_dom_content_loaded_initializes_the_filter_bar() -> None:
    js = _read("app.js")
    handler_start = js.rindex('addEventListener("DOMContentLoaded", async () =>')
    handler_block = js[handler_start : handler_start + 3000]
    assert "initFilterBar();" in handler_block


def test_agent_log_uses_the_shared_additive_chip_family() -> None:
    """Event kinds are additive values, including kinds discovered at run time.

    The shared chip contract makes every selected state visible through the same
    ``aria-pressed`` selector instead of relying on a fixed list of kind colors.
    """

    css = _read("styles.css")
    plugin_root = proc_browser.STATIC_DIR.parent / "builtin_plugins" / "agent_log"
    plugin = (plugin_root / "index.js").read_text()
    plugin_css = (plugin_root / "styles.css").read_text()

    assert ".nav-filter-bar {" in css
    assert "mb.filterControls" in plugin
    assert "fc.groupHtml" in plugin
    assert 'select: "many"' in plugin
    assert 'label: "Event types"' in plugin
    assert 'class="agent-log-filter-bar"' in plugin
    assert "filter-btn" not in plugin
    assert ".filter-bar" not in plugin
    assert ".filter-btn" not in css
    assert ".agent-log-filter-bar" in plugin_css
    assert "margin: 8px 0 12px;" in plugin_css

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

    # Tree row: 10px padding + 2px selection bar = the same 12px at the top
    # level, plus one --tree-indent per level of nesting. The depth is in the
    # padding, never in the box, so the row still spans the whole panel.
    row_start = css.index(".tree-item {")
    row_block = css[row_start : css.index("}", row_start)]
    assert "padding: 2px 12px 2px calc(10px + (var(--tree-depth, 1) - 1)" in row_block
    assert (
        "margin-left"
        not in css[css.index(".tree-children {") : css.index("}", css.index(".tree-children {"))]
    )
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


def test_live_uses_the_server_owned_ninety_second_window() -> None:
    """Every file uses one cutoff. Agent logs retain their active badge
    and tailing behavior, but the filter does not use that tracker."""

    settings = (proc_browser.STATIC_DIR.parent / "settings.py").read_text()
    assert "LIVE_FILE_WINDOW_S = 90.0" in settings
    assert '"live": LIVE_FILE_WINDOW_S' in settings
    assert '"RECENT_WINDOW_SECONDS": RECENT_WINDOW_SECONDS' in settings
    assert '"RECENT_WINDOWS"' not in settings

    js = _read("app.js")
    assert "_METABROWSER_SETTINGS.RECENT_WINDOW_SECONDS" in js
    assert "FILTER_LIVE_PERSIST_MS" not in js
    assert "livePathsForFilter" not in js


def test_age_menu_rows_reuse_the_tree_freshness_ramp() -> None:
    """Live uses the freshest color; each longer window takes the
    color of the age bucket it tops out at."""

    js = _read("app.js")
    start = js.index("var FILTER_RECENCY_OPTIONS = [")
    block = js[start : js.index("];", start)]
    for value, age in (
        ('"live"', "age-live"),
        ('"1h"', "age-min"),
        ('"24h"', "age-hr"),
        ('"7d"', "age-day"),
        ('"30d"', "age-wk"),
    ):
        value_start = block.index(f"value: {value}")
        option = block[value_start : value_start + 240]
        assert f'ageClass: "{age}"' in option, f"{value} should wear {age}"

    filter_controls = _read("filter-controls.js")
    assert "file-age-marker" not in filter_controls

    # The shared ramp is sufficient; no menu-only color correction may drift.
    css = _read("styles.css")
    assert ".chip-menu-item.age-min {" not in css
    assert ".file-age-marker" not in css


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

    js = _read("filter-controls.js")
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
