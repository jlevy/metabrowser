"""The oklch conversion, and the band a family is painted inside.

The conversion is the same one a browser's dev tools perform, so the values
below are checkable by hand: paste the hex into dev tools and read the oklch
back. That is the whole point of using the standard matrices rather than an
approximation — a maintainer can verify a color without running this suite.
"""

from __future__ import annotations

import pytest

from metabrowser.color_oklch import (
    ACHROMATIC_CHROMA,
    BAND_CENTER,
    DARK_THEME,
    LIGHT_THEME,
    Oklch,
    ToneBand,
    TonePosition,
    band_positions,
    delta_e,
    hex_to_oklch,
    hue_distance,
    in_srgb_gamut,
    max_chroma,
    oklab,
    widest_hue_gap,
)

# hex, lightness, chroma, hue — as Chrome dev tools reports them.
DEV_TOOLS_VALUES = [
    ("#3572a5", 0.5354, 0.1022, 246.50),  # Python
    ("#f1e05a", 0.8961, 0.1527, 102.08),  # JavaScript
    ("#663399", 0.4403, 0.1603, 303.37),  # CSS
    ("#00add8", 0.6945, 0.1303, 223.85),  # Go
]

BANDS = (LIGHT_THEME, DARK_THEME)


# The ends of any band: a position is a place, so the edges do not depend on
# which band is being placed in.
DARK_EDGE = TonePosition(lightness_rank=0.0, chroma_ratio=0.0)
LIGHT_EDGE = TonePosition(lightness_rank=1.0, chroma_ratio=1.0)


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


def test_a_band_holds_every_family_within_its_stated_spread() -> None:
    """The bound the stacked bar is owed. Lightness varies now, which it did
    not before, so what protects a segment from reading heavier than its size
    is that the variation is bounded and small — the whole set lands inside
    ``lightness +- spread`` and nothing reaches past it."""

    for band in BANDS:
        low, high = band.lightness - band.spread, band.lightness + band.spread
        for hue in range(0, 360, 7):
            for rank in (0.0, 0.25, 0.5, 0.75, 1.0):
                painted = band.at(hue, TonePosition(rank, 0.5))
                assert low - 1e-9 <= painted.lightness <= high + 1e-9
        assert band.at(0.0, DARK_EDGE).lightness == pytest.approx(low)
        assert band.at(0.0, LIGHT_EDGE).lightness == pytest.approx(high)


def test_the_band_centre_is_where_a_family_without_a_colour_sits() -> None:
    """A family GitHub names no color for has a hue chosen to clear everything
    else, so it needs nothing from the other two axes."""

    assert TonePosition(lightness_rank=0.5, chroma_ratio=0.5) == BAND_CENTER
    for band in BANDS:
        assert band.at(210.0, BAND_CENTER).lightness == pytest.approx(band.lightness)
        assert band.at(210.0).lightness == pytest.approx(band.lightness)


def test_a_band_never_exceeds_its_chroma_reach_and_stays_inside_srgb() -> None:
    """Chroma is a ceiling in both directions: no hue is painted more saturated
    than its place in the band allows, and none is painted outside sRGB."""

    for band in BANDS:
        reach = band.chroma * (1 + band.chroma_spread)
        for hue in range(0, 360, 3):
            for ratio in (0.0, 0.5, 1.0):
                painted = band.at(hue, TonePosition(0.5, ratio))
                assert painted.chroma <= reach + 1e-9
                assert in_srgb_gamut(painted)


def test_the_shipped_bands_are_set_above_the_srgb_floor() -> None:
    """Deliberately, and the reason the palette does not look washed out. A
    target low enough for every hue to reach exactly exists and produces an
    even, muted set; these sit above it, so most hues reach the target and the
    cyan band comes in under."""

    for band in BANDS:
        floor = min(max_chroma(band.lightness, hue / 10) for hue in range(3600))
        assert band.chroma > floor
        assert any(band.at(hue).chroma == pytest.approx(band.chroma) for hue in range(0, 360, 3))


def test_a_band_pulls_chroma_back_rather_than_moving_lightness_or_hue() -> None:
    """Why the pullback lives here and not in a stylesheet: a browser handed an
    out-of-gamut oklch() clips it, which moves both. Chroma is the only thing
    that may give."""

    vivid = ToneBand(lightness=0.62, spread=0.0, chroma=0.4, chroma_spread=0.0)
    painted = vivid.at(206.0)
    assert painted.chroma < vivid.chroma
    assert painted.lightness == vivid.lightness
    assert painted.hue == pytest.approx(206.0)
    assert in_srgb_gamut(painted)


def test_a_band_keeps_the_hue_it_is_given() -> None:
    for band in BANDS:
        for hue in (0.0, 102.08, 246.5, 359.9):
            assert band.at(hue).hue == pytest.approx(hue)
    assert LIGHT_THEME.at(370.0).hue == pytest.approx(10.0)


def test_chroma_ceiling_depends_on_hue() -> None:
    """The fact that makes chroma a target rather than a promise: at one
    lightness sRGB gives red roughly twice the chroma it gives cyan, so a
    reach the reds can use is one the cyans come in under."""

    red, cyan = max_chroma(0.62, 27.0), max_chroma(0.62, 206.0)
    assert red > cyan * 1.8


def test_positions_rank_by_upstream_lightness_and_keep_githubs_order() -> None:
    """Rank, not a linear map. Upstream lightness piles up in the middle —
    half the families inside 0.492-0.687 of a 0.271-0.896 range — so a linear
    map would re-crowd the palette exactly where it is already tightest.
    Ranking spreads them evenly and still keeps the order GitHub chose."""

    # Lua's navy, Python's blue, Svelte's orange, JavaScript's yellow.
    colors = ["#000080", "#3572a5", "#ff3e00", "#f1e05a"]
    positions = band_positions(colors)

    ranks = [position.lightness_rank for position in positions]
    assert ranks[0] == 0.0  # darkest upstream
    assert ranks[-1] == 1.0  # lightest upstream
    assert ranks == sorted(ranks)  # upstream order survives
    assert ranks == [0.0, pytest.approx(1 / 3), pytest.approx(2 / 3), 1.0]  # evenly spread


def test_a_family_without_an_upstream_colour_sits_at_the_centre() -> None:
    positions = band_positions(["#3572a5", None, "#f1e05a"])
    assert positions[1] == BAND_CENTER
    assert band_positions([None, None]) == (BAND_CENTER, BAND_CENTER)
    assert band_positions([]) == ()


def test_chroma_is_normalised_rather_than_ranked() -> None:
    """Ranking chroma would assert a visible difference between two nearly
    equal saturations that is not there; normalising reports the difference
    that is."""

    # Python's blue is the least saturated of the three, Svelte's orange the
    # most, and Ruby's dark red sits between them but much nearer the blue.
    muted, between, vivid = "#3572a5", "#701516", "#ff3e00"
    ratios = [position.chroma_ratio for position in band_positions([muted, between, vivid])]
    assert ratios[0] == pytest.approx(0.0)
    assert ratios[-1] == pytest.approx(1.0)
    # Ranked, the middle would land on exactly 0.5. Normalised, it reports how
    # much closer to the muted end it actually is.
    assert ratios[1] == pytest.approx(0.17, abs=0.01)


def test_delta_e_measures_what_a_hue_angle_cannot() -> None:
    """Two hues a degree apart are the same color at one tone and plainly
    different at two, which is why the palette is checked in delta-E."""

    html, svelte = 34.85, 34.20
    flat = ToneBand(lightness=0.62, spread=0.0, chroma=0.18, chroma_spread=0.0)
    assert delta_e(flat.at(html), flat.at(svelte)) < 0.005

    apart = LIGHT_THEME.at(html, TonePosition(0.4, 0.5))
    lighter = LIGHT_THEME.at(svelte, TonePosition(0.9, 0.9))
    assert delta_e(apart, lighter) > 0.02

    same = Oklch(0.62, 0.18, 34.85)
    assert delta_e(same, same) == 0.0
    assert delta_e(apart, lighter) == pytest.approx(delta_e(lighter, apart))


def test_oklab_is_the_rectangular_form_of_the_same_colour() -> None:
    lightness, a, b = oklab(Oklch(0.62, 0.18, 0.0))
    assert (lightness, a, b) == pytest.approx((0.62, 0.18, 0.0), abs=1e-9)
    _, a90, b90 = oklab(Oklch(0.62, 0.18, 90.0))
    assert (a90, b90) == pytest.approx((0.0, 0.18), abs=1e-9)


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
