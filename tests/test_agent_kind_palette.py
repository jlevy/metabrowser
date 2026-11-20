"""One color per event kind and per tool family, in both themes (the operational views plan,
"One Color System").

The ``agents`` plugin's stylesheet declares ``--agent-kind-<kind>-{bg,text,fill}`` for every
event kind and ``--agent-tool-<family>-{bg,text,fill}`` for every tool family. Kinds and
families form one palette, since the Records and Tools page shows both, so the check here
pins what a reader needs of it: every token exists in both themes; each ``-text`` reads on
its ``-bg``; a token keeps its hue between themes; and no two ``-fill`` colors in one theme
sit closer than ``MIN_FILL_DISTANCE``. The Log, the Charts view, and the Session view each
draw a kind from these tokens, and the adapters' own kind names map onto them in one table
that ``charts.py`` and ``agents/index.js`` both state.
"""

from __future__ import annotations

import itertools
import math
import re
from pathlib import Path

from metabrowser.builtin_plugins.agents.kinds import KINDS, TOOL_FAMILIES
from tests.test_agent_log_theme import (
    MINIMUM_TEXT_CONTRAST,
    OKLCH_RE,
    PLUGIN_CSS,
    _contrast_ratio,  # pyright: ignore[reportPrivateUsage]
    _css_block,  # pyright: ignore[reportPrivateUsage]
    _tokens,  # pyright: ignore[reportPrivateUsage]
)

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_JS = PLUGIN_CSS.with_name("index.js")
CHARTS_PY = ROOT / "src" / "metabrowser" / "charts.py"

# The least Euclidean distance in OKLab between two fills of one theme. Measured on the
# palette as shipped: the closest pair is 0.095 in the dark theme and 0.105 in the light one
# (tool-call and tool-edit; tool-result and unknown). The bound sits just below, so a
# change that crowds two kinds fails and one that keeps them apart does not.
MIN_FILL_DISTANCE = 0.09

# Below this chroma a color is a near-neutral and its hue is not perceptible.
NEUTRAL_CHROMA = 0.02

PARTS = ("bg", "text", "fill")


def _names() -> list[str]:
    return [f"kind-{kind}" for kind in KINDS] + [f"tool-{family}" for family in TOOL_FAMILIES]


def _themes() -> dict[str, dict[str, str]]:
    css = PLUGIN_CSS.read_text(encoding="utf-8")
    light = _tokens(_css_block(css, ":root {"))
    dark = _tokens(_css_block(css, '[data-theme="dark"] {'))
    return {"light": light, "dark": {**light, **dark}}


def _lch(value: str) -> tuple[float, float, float]:
    match = OKLCH_RE.fullmatch(value.strip())
    assert match is not None, f"expected an oklch() color, got {value!r}"
    return float(match["lightness"]) / 100, float(match["chroma"]), float(match["hue"])


def _lab(value: str) -> tuple[float, float, float]:
    lightness, chroma, hue = _lch(value)
    return lightness, chroma * math.cos(math.radians(hue)), chroma * math.sin(math.radians(hue))


def test_every_kind_and_family_has_all_three_tokens_in_both_themes() -> None:
    css = PLUGIN_CSS.read_text(encoding="utf-8")
    light = _tokens(_css_block(css, ":root {"))
    dark = _tokens(_css_block(css, '[data-theme="dark"] {'))
    for name in _names():
        for part in PARTS:
            token = f"--agent-{name}-{part}"
            assert token in light, f"the light theme is missing {token}"
            assert token in dark, f"the dark theme is missing {token}"


def test_each_ink_reads_on_its_ground_in_both_themes() -> None:
    for theme, tokens in _themes().items():
        for name in _names():
            ratio = _contrast_ratio(tokens[f"--agent-{name}-text"], tokens[f"--agent-{name}-bg"])
            assert ratio >= MINIMUM_TEXT_CONTRAST, f"{theme} {name}: {ratio:.2f}:1"


def test_a_token_keeps_its_hue_between_themes() -> None:
    themes = _themes()
    for name in _names():
        for part in PARTS:
            token = f"--agent-{name}-{part}"
            light, dark = _lch(themes["light"][token]), _lch(themes["dark"][token])
            if min(light[1], dark[1]) < NEUTRAL_CHROMA:
                continue
            assert light[2] == dark[2], f"{token} changes hue: {light[2]} then {dark[2]}"


def test_no_two_fills_in_one_theme_are_closer_than_the_bound() -> None:
    for theme, tokens in _themes().items():
        fills = {name: _lab(tokens[f"--agent-{name}-fill"]) for name in _names()}
        for first, second in itertools.combinations(fills, 2):
            distance = math.dist(fills[first], fills[second])
            assert distance >= MIN_FILL_DISTANCE, (
                f"{theme}: {first} and {second} are {distance:.3f} apart"
            )


def test_the_old_private_kind_tokens_are_gone() -> None:
    for path in (PLUGIN_CSS, PLUGIN_JS, CHARTS_PY):
        assert "--agent-log-kind-" not in path.read_text(encoding="utf-8"), path.name


def _chart_table() -> dict[str, str]:
    source = CHARTS_PY.read_text(encoding="utf-8")
    block = re.search(r"kind_colors = \{(.*?)\}", source, re.DOTALL)
    assert block is not None
    return dict(re.findall(r'"(\w+)":\s*"var\(--agent-kind-([\w-]+)-fill\)"', block.group(1)))


def _script_table() -> dict[str, str]:
    source = PLUGIN_JS.read_text(encoding="utf-8")
    block = re.search(r"EVENT_KIND_OF_ADAPTER_KIND = \{(.*?)\};", source, re.DOTALL)
    assert block is not None
    return dict(re.findall(r'(\w+):\s*"([\w-]+)"', block.group(1)))


def test_the_chart_and_the_log_color_an_adapter_kind_alike() -> None:
    chart, script = _chart_table(), _script_table()
    assert chart == script
    assert set(chart.values()) <= set(KINDS)
