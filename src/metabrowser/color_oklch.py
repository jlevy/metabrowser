"""Oklch color math, and the tone system a file-type family is painted in.

A family declares one number: its hue. Where it also records the upstream color
that hue was taken from, the palette reads two more attributes off it — but as
positions inside a band each theme owns, never as the upstream values
themselves. The set still reads as one palette rather than as fifty-six
imported colors.

**Hue is identity.** Where GitHub's linguist names a color for a language, the
family takes that color's hue, converted the way a browser's dev tools convert
it: ``hex_to_oklch("#3572a5").hue`` is 246.5, and Python is that hue. Families
GitHub has no color for take a hue from the widest remaining gap. That is the
whole hue rule — no adjustment of GitHub's hues, including where GitHub's own
are close together, because a reader who knows Ruby is red is better served by
red than by a hue we moved to win a distance metric.

**Lightness and chroma are a band, not a constant.** One lightness and one
chroma for everything is what this palette did first, and it discarded the two
dimensions GitHub's own colors are mostly separated by. Html and svelte differ
by 0.65 degrees of hue but by 0.032 of lightness and 0.040 of chroma; ruby and
yaml by 1.13 degrees and 0.179 of lightness. Flattened onto one tone they came
out as the same color: html rendered ``#dd5230`` against svelte's ``#dd5232``.
Fifty-six families average 6.4 degrees of hue spacing, at or under the
just-noticeable difference at fixed lightness and chroma, so hue alone cannot
carry the set.

So each theme states a lightness centre with a spread and a chroma centre with
a spread, and every family sits somewhere inside both — see :data:`LIGHT_THEME`,
:data:`DARK_THEME`, and :func:`band_positions`. Upstream *order* is kept and
upstream *extremes* are not, which is the point: GitHub's lightness runs from
Lua's 0.27 navy to JavaScript's 0.90 yellow, a palette assembled by hundreds of
people over a decade that looks like it.

One property is given up deliberately. Lightness is no longer constant, so a
stacked-bar segment can read slightly heavier than a neighbour of the same
size, and guaranteeing it did not was why the flat tone was chosen. The band is
narrow to keep that small, and the measured alternative was worse: at one tone
the closest pair in the light theme sits at an Oklab delta-E of 0.0020, which
is not a difference anyone can see.

A family may leave the band, and only by saying so. Where the derivation cannot
separate a family that matters — or where GitHub's own placement puts it on top
of a better-known neighbour — the registry lets it declare a lightness rank of
its own alongside the reason. That is the whole escape hatch: prose, checked,
and visible in the palette report rather than buried in a diff.

No third-party color library: these are the standard Oklab matrices, and a
dependency for forty lines of arithmetic would not survive
SUPPLY-CHAIN-SECURITY.md's cost test.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

_SRGB_EPSILON = 1e-4

# Below this chroma a color has no usable hue: #292929 is grey, and the hue
# angle its conversion reports is rounding noise rather than a color anyone
# chose. Families whose upstream color is grey take a gap hue instead.
ACHROMATIC_CHROMA = 0.02


@dataclass(frozen=True, slots=True)
class Oklch:
    """A color as lightness (0-1), chroma, and hue in degrees."""

    lightness: float
    chroma: float
    hue: float

    def css(self) -> str:
        """The CSS ``oklch()`` form, rounded to what a stylesheet needs."""

        return f"oklch({self.lightness * 100:.2f}% {self.chroma:.4f} {self.hue:.2f})"


@dataclass(frozen=True, slots=True)
class TonePosition:
    """Where one family sits inside a theme's band, on each axis, normally in [0, 1].

    Both are relative places among the families, not upstream measurements:
    :func:`band_positions` derives them once for the whole set. A family with
    no upstream color of its own sits at :data:`BAND_CENTER`.

    ``lightness_rank`` may fall outside [0, 1], which places the family outside
    the band. That is the one way out, it is never derived, and the registry
    only accepts it from a family that records in prose why it is leaving —
    because the band is the bound on how much a stacked-bar segment can read
    heavier than its size, and a family outside it is a segment that can.
    """

    lightness_rank: float
    chroma_ratio: float


BAND_CENTER = TonePosition(lightness_rank=0.5, chroma_ratio=0.5)
"""The middle of the band, where a family GitHub names no color for sits.

It has a hue of its own, chosen to clear everything else, so it needs no help
from the other two axes — and it has no upstream color to take a place from."""


@dataclass(frozen=True, slots=True)
class ToneBand:
    """The lightness and chroma band one theme paints its families inside."""

    lightness: float
    """The centre of the band. A family at :data:`BAND_CENTER` is painted here."""
    spread: float
    """Half the band's height: the lightest family lands ``lightness + spread``."""
    chroma: float
    """The centre chroma, as a target rather than a guarantee — see :meth:`at`."""
    chroma_spread: float
    """The fraction of ``chroma`` the most and least saturated families differ
    from the centre by, so the reachable target runs over
    ``chroma * (1 - chroma_spread)`` to ``chroma * (1 + chroma_spread)``."""

    def at(self, hue: float, position: TonePosition = BAND_CENTER) -> Oklch:
        """This band at *hue* and *position*, pulled back into sRGB if it must be.

        The pullback is not a choice: sRGB simply holds less chroma in the
        cyan-green band than it does in red, at any lightness.

        It has to happen here rather than in a stylesheet. A browser handed an
        out-of-gamut ``oklch()`` clips it, which moves lightness and hue —
        measured at up to nine degrees of hue, more than the separation the
        palette is built on. Reducing chroma keeps the hue exactly where the
        registry declared it, and keeps lightness where the band put it.
        """

        hue %= 360
        lightness = self.lightness + self.spread * (2 * position.lightness_rank - 1)
        target = self.chroma * (
            1 - self.chroma_spread + 2 * self.chroma_spread * position.chroma_ratio
        )
        return Oklch(lightness, min(target, max_chroma(lightness, hue)), hue)


# ── The two bands ───────────────────────────────────────────────
#
# The centres come from the hand-tuned twelve-slot ramp these replace, which
# settled on 0.60 light and 0.77 dark after many iterations by eye.
#
# Chroma is a target rather than a guarantee, and its centre is set high — near
# what sRGB holds at the roomiest hues, not at the tightest. A target low enough
# for every hue to reach exactly does exist (0.1055 light, 0.1275 dark, both set
# by the cyan-blue band, which holds roughly half what red does) and produces a
# perfectly even set that reads as washed out. Chroma this far up is worth the
# unevenness: most hues reach it and the cyans come in under, which is the same
# trade the old ramp made when it gave its teal slot 0.09 against 0.15
# elsewhere.
#
# The spreads are measured, not guessed. Over all 56 families the closest
# Oklab delta-E pair moves from 0.0020 to 0.0156 in light and 0.0017 to 0.0073
# in dark, and pairs under 0.02 fall from 41 to 9 and from 48 to 8. Widening
# the lightness band to +-0.08 buys almost nothing — the light floor goes to
# 0.0164 — so the tighter band wins on consistency, since every 0.01 of spread
# is lightness a stacked-bar segment carries that its size did not earn.
# Letting the house families take lightness freedom too was measured and
# dropped: it moves the floor not at all, because the binding pair is
# GitHub's against GitHub's.
#
# Reproduce all of it with devtools/check_file_type_colors.py.

LIGHT_THEME = ToneBand(lightness=0.62, spread=0.06, chroma=0.180, chroma_spread=0.25)
"""Filled swatches on a near-white ground. Paints 0.560-0.680 lightness and
reaches 0.225 chroma where the gamut allows, against a flat 0.180 before."""

DARK_THEME = ToneBand(lightness=0.75, spread=0.06, chroma=0.150, chroma_spread=0.25)
"""The same hues on a dark ground. Lighter, because a color needs more
lightness to carry against dark, and less saturated, because sRGB holds less
chroma up there — 0.75 is past the peak. Paints 0.690-0.810."""


def hex_to_oklch(value: str) -> Oklch:
    """Convert an sRGB hex string, the way a browser's dev tools do."""

    text = value.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"expected a six-digit hex color, got {value!r}")
    try:
        red, green, blue = (int(text[index : index + 2], 16) / 255 for index in (0, 2, 4))
    except ValueError as error:
        raise ValueError(f"expected a six-digit hex color, got {value!r}") from error
    return _linear_srgb_to_oklch(
        (_srgb_to_linear(red), _srgb_to_linear(green), _srgb_to_linear(blue))
    )


def oklch_to_srgb(color: Oklch) -> tuple[float, float, float]:
    """Linear-light sRGB channels, unclamped, so gamut can be tested."""

    a = color.chroma * math.cos(math.radians(color.hue))
    b = color.chroma * math.sin(math.radians(color.hue))
    l_ = color.lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = color.lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = color.lightness - 0.0894841775 * a - 1.2914855480 * b
    long_, medium, short = l_**3, m_**3, s_**3
    return (
        4.0767416621 * long_ - 3.3077115913 * medium + 0.2309699292 * short,
        -1.2684380046 * long_ + 2.6097574011 * medium - 0.3413193965 * short,
        -0.0041960863 * long_ - 0.7034186147 * medium + 1.7076147010 * short,
    )


def in_srgb_gamut(color: Oklch) -> bool:
    """Whether every channel lands inside sRGB, within a rounding tolerance."""

    return all(-_SRGB_EPSILON <= c <= 1 + _SRGB_EPSILON for c in oklch_to_srgb(color))


def max_chroma(lightness: float, hue: float) -> float:
    """The most chroma sRGB holds at this lightness and hue.

    Bisection rather than an analytic solve: the gamut boundary in oklch has no
    closed form, and this runs at build time.
    """

    low, high = 0.0, 0.5
    for _ in range(40):
        middle = (low + high) / 2
        if in_srgb_gamut(Oklch(lightness, middle, hue)):
            low = middle
        else:
            high = middle
    return low


def oklab(color: Oklch) -> tuple[float, float, float]:
    """The same color as Oklab lightness and its two opponent axes.

    Oklch is what the registry and the stylesheets speak; Oklab is what a
    distance is taken in. They are one space in polar and rectangular form.
    """

    return (
        color.lightness,
        color.chroma * math.cos(math.radians(color.hue)),
        color.chroma * math.sin(math.radians(color.hue)),
    )


def delta_e(left: Oklch, right: Oklch) -> float:
    """How different two colors look: plain Euclidean distance in Oklab.

    Oklab is built so this distance tracks perceived difference, which a hue
    angle on its own does not — two hues a degree apart are the same color at
    one lightness and clearly different at two. It is the measure the palette
    is checked against for that reason.
    """

    return math.dist(oklab(left), oklab(right))


def band_positions(upstream_colors: Sequence[str | None]) -> tuple[TonePosition, ...]:
    """Place each family inside the band, from the color GitHub gave it.

    Returns one position per entry, in the order given. ``None`` — a family
    GitHub names no color for — lands at :data:`BAND_CENTER`.

    Lightness is a **rank** and chroma is a plain normalisation, and the
    asymmetry is the point. Upstream lightness runs 0.271 to 0.896 with half
    the families inside 0.492-0.687, so mapping it linearly would re-crowd the
    middle exactly where the set is already tightest. Ranking keeps GitHub's
    order — svelte stays lighter than html — while spreading the families
    evenly across the band the theme allows. Upstream chroma has no comparable
    pile-up, and ranking it would assert a visible difference between two
    nearly equal saturations that is not there.

    Positions are relative to the set, so adding a family can move its
    neighbours by a rank step. That is why they are derived here for the whole
    registry at once rather than recorded per family.
    """

    upstream = {
        index: hex_to_oklch(value)
        for index, value in enumerate(upstream_colors)
        if value is not None
    }
    if not upstream:
        return tuple(BAND_CENTER for _ in upstream_colors)

    # Ties break on registry order so the palette is a function of the file.
    ordered = sorted(upstream, key=lambda index: (upstream[index].lightness, index))
    span = max(len(ordered) - 1, 1)
    rank = {index: place / span for place, index in enumerate(ordered)}

    chromas = [color.chroma for color in upstream.values()]
    low, high = min(chromas), max(chromas)
    width = high - low

    return tuple(
        TonePosition(
            lightness_rank=rank[index],
            chroma_ratio=0.5 if width == 0 else (upstream[index].chroma - low) / width,
        )
        if index in upstream
        else BAND_CENTER
        for index in range(len(upstream_colors))
    )


def hue_distance(left: float, right: float) -> float:
    """Shortest angular distance between two hues, in degrees."""

    delta = abs(left - right) % 360
    return min(delta, 360 - delta)


def widest_hue_gap(taken: tuple[float, ...]) -> float:
    """The hue furthest from every hue in *taken*, to a tenth of a degree.

    How a family GitHub names no color for gets one. A sweep rather than
    midpoint arithmetic because the answer has to be the same one the check
    computes, and a sweep is obviously that.
    """

    if not taken:
        return 0.0
    best, best_gap = 0.0, -1.0
    for step in range(3600):
        hue = step / 10
        gap = min(hue_distance(hue, other) for other in taken)
        if gap > best_gap:
            best, best_gap = hue, gap
    return best


def _srgb_to_linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def _linear_srgb_to_oklch(rgb: tuple[float, float, float]) -> Oklch:
    red, green, blue = rgb
    long_ = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
    medium = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
    short = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue
    l_, m_, s_ = (math.copysign(abs(c) ** (1 / 3), c) for c in (long_, medium, short))
    lightness = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return Oklch(lightness, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360)


__all__ = [
    "ACHROMATIC_CHROMA",
    "BAND_CENTER",
    "DARK_THEME",
    "LIGHT_THEME",
    "Oklch",
    "ToneBand",
    "TonePosition",
    "band_positions",
    "delta_e",
    "hex_to_oklch",
    "hue_distance",
    "in_srgb_gamut",
    "max_chroma",
    "oklab",
    "oklch_to_srgb",
    "widest_hue_gap",
]
