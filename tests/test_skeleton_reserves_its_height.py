"""The page's structure must not grow under the reader after it paints.

Two regions were rendered before they had content and grew when it arrived:
the filter bar, which the server ships empty for filter-controls.js to fill,
and the tree's tally row, which paints with the inlined rows and gets its
numbers from a later request. Measured at 1280x900 on the 246,282-file corpus:
24 px and 43 px of downward movement, on every load and every reload.

Each reservation holds one line box. That settles the filter bar outright and
takes the tally row from 43 px to 23, the remainder being a split row wrapping
to a second line in a narrow pane -- H54, which wants the pending row shaped
like the settled one rather than a taller floor. These tests assert the
reservations exist, stay derived, and stay off the one state whose box they
were not derived from; the pixels are in
explorations/performance-loop/experiments/exp-009.
"""

from __future__ import annotations

import re
from pathlib import Path

from metabrowser import server

STATIC = Path(server.__file__).resolve().parent / "static"

# The tally row's floor is derived from a box that carries this row's own
# bottom padding and border. The rule below drops both so the totals and the
# filtered count read as one band, and the floor must not reach that state.
TALLY_RESERVATION = (
    ".tree-summary:not(:has(+ .tree-summary-filtered)):not(:has(+ .tree-selection-note))"
)
TALLY_JOINED = ".tree-summary:has(+ .tree-selection-note)"


def _rule(css: str, selector: str) -> str:
    """The declarations of one rule, found by the last line of its selector."""
    match = re.search(rf"^{re.escape(selector)} \{{(.*?)^\}}", css, re.MULTILINE | re.DOTALL)
    assert match is not None, f"{selector} rule not found"
    return match.group(1)


def _declaration(rule: str, property_name: str) -> str:
    line = next((one for one in rule.splitlines() if f"{property_name}:" in one), None)
    assert line is not None, f"no {property_name} in rule"
    return line.strip()


def _function_source(js: str, signature: str) -> str:
    """One top-level function, bounded by the next one rather than by a count.

    A fixed-size window keeps passing while it measures source that no longer
    holds the code under test, which is the failure mode a source-level test
    can least afford.
    """
    start = js.find(signature)
    assert start >= 0, f"{signature} not found"
    rest = js[start + len(signature) :]
    ends = [at for at in (rest.find("\nfunction "), rest.find("\nasync function ")) if at >= 0]
    return signature + (rest[: min(ends)] if ends else rest)


def test_the_filter_bar_reserves_a_chip_row_before_the_chips_arrive() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "min-height" in _rule(css, ".nav-filter-bar"), (
        "the filter bar grows when filter-controls.js fills it unless it reserves the height"
    )


def test_the_tally_row_reserves_a_line_box_before_its_counts_arrive() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "min-height" in _rule(css, TALLY_RESERVATION), (
        "the tally row grows when its counts arrive unless it reserves the height"
    )


def test_the_tally_reservation_stays_off_the_state_it_was_not_derived_from() -> None:
    """The floor counts this row's bottom padding and border. Where the joined
    state removes them, the same floor holds that much empty space open between
    the totals and the filtered count -- the gap that rule exists to close."""
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    joined = _rule(css, TALLY_JOINED)
    assert "border-bottom: none" in joined and "padding-bottom: 0" in joined, (
        "this test guards the joined state against the reservation; the state has changed"
    )
    assert "min-height" not in _rule(css, ".tree-summary"), (
        "the reservation must be scoped, not on the base rule, or it reaches the joined state"
    )


def test_both_reservations_derive_from_the_type_they_hold() -> None:
    """A hardcoded pixel height drifts the first time the font set changes, and
    this shell offers the reader a choice of font sets."""
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    for selector in (".nav-filter-bar", TALLY_RESERVATION):
        reservation = _declaration(_rule(css, selector), "min-height")
        assert "var(--" in reservation, (
            f"{selector} reserves a fixed height rather than deriving it: {reservation}"
        )


def test_the_chip_box_has_one_source() -> None:
    """The filter bar reserves a chip's height before any chip exists, so the
    padding and border making up that height cannot live only in `.chip`. A
    reservation that restates them goes short the moment either changes, and
    nothing here would notice."""
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    at = css.index("--chip-height:")
    chip_height = css[at : css.index(";", at)]
    for token in ("--chip-padding-y", "--chip-border"):
        assert f"{token}:" in css, f"{token} must be defined for --chip-height to derive from it"
        assert f"var({token})" in chip_height, (
            f"--chip-height must be built from {token} rather than restating its value"
        )
    chip = _rule(css, ".chip")
    assert "var(--chip-padding-y)" in chip and "var(--chip-border)" in chip, (
        ".chip must read back the tokens --chip-height is built from, or the two can disagree"
    )


def test_the_inline_render_emits_the_tally_row_rather_than_omitting_it() -> None:
    """Reserving the height in CSS only helps if the element is there to hold
    it. The inline path used to pass an empty chrome string."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    block = _function_source(app, "function renderInitialTreeRows()")
    assert "treeSummaryHtml(null, null, null)" in block


def test_the_inline_span_is_recorded_around_the_paint_not_around_the_decision() -> None:
    """`renderInitialTreeRows` declines to paint four ways -- no inlined rows,
    something already on screen, a filter, a recency window. A span recorded
    around the call reports work on a region none of them touched."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    inline = _function_source(app, "function renderInitialTreeRows()")
    assert '_perf.measure("renderTreeNodes:inline", () => renderFilesFromTree())' in inline, (
        "the inline span must wrap the paint itself"
    )
    load_tree = _function_source(app, "async function loadTree()")
    assert "renderTreeNodes:inline" not in load_tree, (
        "wrapping the call records a span whether or not it painted"
    )
