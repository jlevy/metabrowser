"""The oklch conversion, and the tone every family is painted at.

The conversion is the same one a browser's dev tools perform, so the values
below are checkable by hand: paste the hex into dev tools and read the oklch
back. That is the whole point of using the standard matrices rather than an
approximation — a maintainer can verify a color without running this suite.
"""

from __future__ import annotations

import pytest

from metabrowser.color_oklch import (
    ACHROMATIC_CHROMA,
    DARK_THEME,
    LIGHT_THEME,
    Oklch,
    Tone,
    hex_to_oklch,
    hue_distance,
    in_srgb_gamut,
    max_chroma,
    widest_hue_gap,
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


def test_grey_converts_below_the_achromatic_threshold() -> None:
    """Why a grey upstream color cannot be a family's identity: it has no hue
    to take. GitHub gives JSON #292929, and the hue that converts to is
    rounding noise."""

    for grey in ("#000000", "#292929", "#141414", "#ffffff"):
        assert hex_to_oklch(grey).chroma < ACHROMATIC_CHROMA


def test_a_bad_hex_is_refused() -> None:
    for bad in ("#fff", "3572a5f", "", "#zzzzzz"):
        with pytest.raises(ValueError):
            hex_to_oklch(bad)


def test_a_tone_gives_every_hue_the_same_lightness() -> None:
    """The half of the tone that never varies, and the half that matters for a
    stacked bar: no segment looks heavier than its size because its neighbor is
    darker. Chroma is a target rather than a constant — see below."""

    for tone in (LIGHT_THEME, DARK_THEME):
        assert {tone.at(hue).lightness for hue in range(0, 360, 7)} == {tone.lightness}


def test_a_tone_never_exceeds_its_chroma_and_stays_inside_srgb() -> None:
    """Chroma is a ceiling in both directions: no hue is painted more saturated
    than the target, and none is painted outside what sRGB can show."""

    for tone in (LIGHT_THEME, DARK_THEME):
        for hue in range(0, 360, 3):
            painted = tone.at(hue)
            assert painted.chroma <= tone.chroma
            assert in_srgb_gamut(painted)


def test_the_shipped_tones_are_set_above_the_srgb_floor() -> None:
    """Deliberately, and the reason the palette does not look washed out. A
    target low enough for every hue to reach exactly exists and produces an
    even, muted set; these sit above it, so most hues reach the target and the
    cyan band comes in under."""

    for tone in (LIGHT_THEME, DARK_THEME):
        floor = min(max_chroma(tone.lightness, hue / 10) for hue in range(3600))
        assert tone.chroma > floor
        assert any(tone.at(hue).chroma == tone.chroma for hue in range(0, 360, 3))


def test_a_tone_pulls_chroma_back_rather_than_moving_lightness_or_hue() -> None:
    """Why the pullback lives here and not in a stylesheet: a browser handed an
    out-of-gamut oklch() clips it, which moves both. Chroma is the only thing
    that may give."""

    vivid = Tone(lightness=0.62, chroma=0.4)
    painted = vivid.at(206.0)
    assert painted.chroma < vivid.chroma
    assert painted.lightness == vivid.lightness
    assert painted.hue == pytest.approx(206.0)
    assert in_srgb_gamut(painted)


def test_a_tone_keeps_the_hue_it_is_given() -> None:
    for tone in (LIGHT_THEME, DARK_THEME):
        for hue in (0.0, 102.08, 246.5, 359.9):
            assert tone.at(hue).hue == pytest.approx(hue)
    assert LIGHT_THEME.at(370.0).hue == pytest.approx(10.0)


def test_chroma_ceiling_depends_on_hue() -> None:
    """The fact that forces one chroma for the whole set: at one lightness sRGB
    gives red roughly twice the chroma it gives cyan, so a higher target would
    be reachable by some hues and not others."""

    red, cyan = max_chroma(0.62, 27.0), max_chroma(0.62, 206.0)
    assert red > cyan * 1.8


def test_hue_distance_wraps() -> None:
    assert hue_distance(10, 350) == pytest.approx(20)
    assert hue_distance(350, 10) == pytest.approx(20)
    assert hue_distance(0, 180) == pytest.approx(180)


def test_the_widest_gap_is_the_hue_furthest_from_what_is_taken() -> None:
    assert widest_hue_gap((0.0, 180.0)) in (90.0, 270.0)
    assert widest_hue_gap(()) == 0.0
    taken = (10.0, 20.0, 30.0, 200.0)
    gap = widest_hue_gap(taken)
    assert min(hue_distance(gap, hue) for hue in taken) == pytest.approx(85.0, abs=0.1)


def test_css_renders_the_form_a_stylesheet_wants() -> None:
    assert Oklch(0.6234, 0.1234, 246.5).css() == "oklch(62.34% 0.1234 246.50)"
