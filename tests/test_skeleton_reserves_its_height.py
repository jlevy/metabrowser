"""The page's structure must not grow under the reader after it paints.

Two regions were rendered before they had content and grew when it arrived:
the filter bar, which the server ships empty for filter_controls.js to fill,
and the tree's tally row, which paints with the inlined rows and gets its
numbers from a later request. Measured at 1280x900 on the 246,282-file corpus:
24 px and 43 px of downward movement, on every load and every reload.

Each reservation holds one line box. That settles the filter bar outright and
takes the tally row from 43 px to 23, the remainder being a split row wrapping
to a second line in a narrow pane -- H54, which wants the pending row shaped
like the settled one rather than a taller floor. These tests assert the
reservations exist and stay derived; the pixels are in
explorations/performance-loop/experiments/exp-009.
"""

from __future__ import annotations

import re
from pathlib import Path

from metabrowser import server

STATIC = Path(server.__file__).resolve().parent / "static"


def _rule(css: str, selector: str) -> str:
    match = re.search(rf"^{re.escape(selector)} \{{(.*?)^\}}", css, re.MULTILINE | re.DOTALL)
    assert match is not None, f"{selector} rule not found"
    return match.group(1)


def test_the_filter_bar_reserves_a_chip_row_before_the_chips_arrive() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "min-height" in _rule(css, ".nav-filter-bar"), (
        "the filter bar grows when filter_controls.js fills it unless it reserves the height"
    )


def test_the_tally_row_reserves_its_settled_height() -> None:
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "min-height" in _rule(css, ".tree-summary"), (
        "the tally row grows when its counts arrive unless it reserves the height"
    )


def test_both_reservations_derive_from_the_type_they_hold() -> None:
    """A hardcoded pixel height drifts the first time the font set changes, and
    this shell offers the reader a choice of font sets."""
    css = (STATIC / "styles.css").read_text(encoding="utf-8")
    assert "--chip-height:" in css, "the chip height must be a token both users can share"
    for selector in (".nav-filter-bar", ".tree-summary"):
        rule = _rule(css, selector)
        reservation = next(line for line in rule.splitlines() if "min-height" in line)
        assert "var(--" in reservation, (
            f"{selector} reserves a fixed height rather than deriving it: {reservation.strip()}"
        )


def test_the_inline_render_emits_the_tally_row_rather_than_omitting_it() -> None:
    """Reserving the height in CSS only helps if the element is there to hold
    it. The inline path used to pass an empty chrome string."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    block = app[app.index("function renderInitialTreeRows()") :]
    block = block[: block.index("async function loadTree()")]
    assert "treeSummaryHtml(null, null, null)" in block
    assert 'chromeHtml: ""' not in block


def test_the_inline_span_is_recorded_only_when_it_paints() -> None:
    """Repaint count is a metric now, so a span for a call that declined to
    paint reports a repaint of a region nothing touched."""
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    load_tree = app[app.index("async function loadTree()") :][:1200]
    assert "if (_inlineTreeRows) {" in load_tree
