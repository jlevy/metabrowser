"""The oklch conversion, and the clamp that makes a color usable on a theme.

The conversion is the same one a browser's dev tools perform, so the values
below are checkable by hand: paste the hex into dev tools and read the oklch
back. That is the whole point of using the standard matrices rather than an
approximation — a maintainer can verify a color without running this suite.
"""

from __future__ import annotations

import pytest

from metabrowser.color_oklch import (
    DARK_THEME_LIGHTNESS,
    LIGHT_THEME_LIGHTNESS,
    Oklch,
    for_theme,
    hex_to_oklch,
    hue_distance,
    in_srgb_gamut,
    max_chroma,
)

# hex, lightness, chroma, hue — as Chrome dev tools reports them.
DEV_TOOLS_VALUES = [
    ("#3572a5", 0.5354, 0.1022, 246.50),  # Python
    ("#f1e05a", 0.8961, 0.1527, 102.08),  # JavaScript
    ("#663399", 0.4403, 0.1603, 303.37),  # CSS
    ("#00add8", 0.6945, 0.1303, 223.85),  # Go
]


@pytest.mark.parametrize(("value", "lightness", "chroma", "hue"), DEV_TOOLS_VALUES)
def test_conversion_matches_what_dev_tools_report(
    value: str, lightness: float, chroma: float, hue: float
) -> None:
    color = hex_to_oklch(value)
    assert color.lightness == pytest.approx(lightness, abs=5e-4)
    assert color.chroma == pytest.approx(chroma, abs=5e-4)
    assert color.hue == pytest.approx(hue, abs=0.05)


def test_black_and_white_convert_without_a_hue() -> None:
    """Achromatic input has no hue to carry, which is what makes a grey
    upstream color unusable as an identity: there is nothing to preserve."""

    assert hex_to_oklch("#000000").chroma == pytest.approx(0.0, abs=1e-6)
    assert hex_to_oklch("#ffffff").lightness == pytest.approx(1.0, abs=1e-3)
    assert hex_to_oklch("#292929").chroma == pytest.approx(0.0, abs=1e-3)


def test_a_bad_hex_is_refused() -> None:
    for bad in ("#fff", "3572a5f", "", "#zzzzzz"):
        with pytest.raises(ValueError):
            hex_to_oklch(bad)


def test_a_color_inside_the_band_is_left_alone() -> None:
    """Most upstream colors pass through untouched; that is why the bands are
    wide. A clamp that moved everything would be a palette of its own."""

    python = hex_to_oklch("#3572a5")
    assert for_theme(python, LIGHT_THEME_LIGHTNESS) == python


def test_a_color_outside_the_band_moves_to_the_nearest_edge() -> None:
    javascript = hex_to_oklch("#f1e05a")  # lightness 0.896, above the light band
    adapted = for_theme(javascript, LIGHT_THEME_LIGHTNESS)
    assert adapted.lightness == pytest.approx(LIGHT_THEME_LIGHTNESS[1])
    assert adapted.hue == pytest.approx(javascript.hue)

    lua = hex_to_oklch("#000080")  # lightness 0.271, below both bands
    for band in (LIGHT_THEME_LIGHTNESS, DARK_THEME_LIGHTNESS):
        assert for_theme(lua, band).lightness == pytest.approx(band[0])


def test_hue_survives_the_clamp_on_both_themes() -> None:
    """A family is one color across themes, which is only true if the clamp
    never touches hue."""

    for value in ("#3572a5", "#f1e05a", "#663399", "#000080", "#cb171e"):
        color = hex_to_oklch(value)
        for band in (LIGHT_THEME_LIGHTNESS, DARK_THEME_LIGHTNESS):
            assert for_theme(color, band).hue == pytest.approx(color.hue)


def test_every_adapted_color_is_inside_srgb() -> None:
    """Moving lightness raises the chroma ceiling in some places and lowers it
    in others; the clamp has to follow it down or it emits an unpaintable
    color."""

    for value in ("#3572a5", "#f1e05a", "#663399", "#083fa1", "#000080", "#cb171e", "#00add8"):
        color = hex_to_oklch(value)
        for band in (LIGHT_THEME_LIGHTNESS, DARK_THEME_LIGHTNESS):
            assert in_srgb_gamut(for_theme(color, band))


def test_chroma_ceiling_depends_on_hue() -> None:
    """The fact that makes a categorical palette hard: at one lightness sRGB
    gives red roughly twice the chroma it gives cyan, so equal saturation
    across hues is not available."""

    red, cyan = max_chroma(0.62, 27.0), max_chroma(0.62, 206.0)
    assert red > cyan * 1.8


def test_hue_distance_wraps() -> None:
    assert hue_distance(10, 350) == pytest.approx(20)
    assert hue_distance(350, 10) == pytest.approx(20)
    assert hue_distance(0, 180) == pytest.approx(180)


def test_css_renders_the_form_a_stylesheet_wants() -> None:
    assert Oklch(0.6234, 0.1234, 246.5).css() == "oklch(62.34% 0.1234 246.50)"
