"""The Treemap's label bounds restate CSS lengths; these checks pin each copy.

`labelPlan` in treemap-map.js decides whether a size fits from a cell's horizontal
padding (`padX` in `SIZE_PRESETS`) and the gap beside a nested folder's name
(`FOLDER_TITLE_GAP_PX`), which styles.css sets, and the legend session checks drawn
sizes against `VALUE_CHAR_EM`. A copy that drifted from its source would let a size
draw cut off, or hide one that fits, with no other test noticing.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FOLDER = REPO_ROOT / "src" / "metabrowser" / "builtin_plugins" / "folder"
MAP_JS = (FOLDER / "treemap-map.js").read_text(encoding="utf-8")
STYLES = (FOLDER / "styles.css").read_text(encoding="utf-8")
LEGEND_SESSION = (REPO_ROOT / "tests" / "dom" / "treemap-legend-session.js").read_text(
    encoding="utf-8"
)


def _rule(selector: str) -> str:
    match = re.search(rf"(?m)^{re.escape(selector)} \{{(?P<body>[^}}]*)\}}", STYLES)
    assert match, f"styles.css has no rule {selector}"
    return re.sub(r"/\*.*?\*/", "", match["body"], flags=re.DOTALL)


def _px(body: str, prop: str) -> list[int]:
    match = re.search(rf"(?m)^\s*{prop}:\s*(?P<value>[^;]+);", body)
    assert match, f"no {prop} in {body!r}"
    return [int(part.removesuffix("px")) for part in match["value"].split()]


def _preset_pad(name: str) -> int:
    match = re.search(rf"{name}: Object\.freeze\(\{{(?P<body>.*?)restLabels", MAP_JS, re.DOTALL)
    assert match, f"no {name} preset"
    pad = re.search(r"padX: (\d+),", match["body"])
    assert pad, f"no padX in the {name} preset"
    return int(pad[1])


def test_preset_padding_matches_the_cell_padding() -> None:
    assert _preset_pad("full") == _px(_rule(".tm-cell"), "padding")[1]
    assert _preset_pad("compact") == _px(_rule(".tm-compact .tm-cell:not(.tm-bare)"), "padding")[1]


def test_folder_title_gap_matches_the_title_gap() -> None:
    gap = re.search(r"const FOLDER_TITLE_GAP_PX = (\d+);", MAP_JS)
    assert gap
    assert [int(gap[1])] == _px(_rule(".tm-cell-title"), "gap")


def test_legend_session_checks_sizes_at_the_value_bound() -> None:
    bound = re.search(r"const VALUE_CHAR_EM = ([\d.]+);", MAP_JS)
    assert bound
    padding = 2 * _preset_pad("full")
    assert f"size.length * cell.valuePx * {bound[1]} <= cell.w - 1 - {padding}," in LEGEND_SESSION
