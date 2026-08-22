"""Oklch color math, and the tone system a file-type family is painted in.

A family declares one number: its hue. Everything else is the same for every
family, so the palette reads as one set rather than as fifty-six imported
colors.

**Hue is identity.** Where GitHub's linguist names a color for a language, the
family takes that color's hue, converted the way a browser's dev tools convert
it: ``hex_to_oklch("#3572a5").hue`` is 246.5, and Python is that hue. Families
GitHub has no color for take a hue from the widest remaining gap. That is the
whole hue rule — no adjustment of GitHub's hues, including where GitHub's own
are close together, because a reader who knows Ruby is red is better served by
red than by a hue we moved to win a distance metric.

**Lightness and chroma are the system.** Upstream lightness runs from Lua's
0.27 navy to JavaScript's 0.90 yellow, which is a palette assembled by hundreds
of people over a decade and looks like it. Rather than clamp that range into
something usable, each theme states one lightness and one chroma and every
family is painted at them: :data:`LIGHT_THEME` and :data:`DARK_THEME`. The only
per-family variation is the sRGB gamut itself — cyan holds about half the
chroma red does — so chroma drops to whatever the hue can hold.

No third-party color library: these are the standard Oklab matrices, and a
dependency for forty lines of arithmetic would not survive
SUPPLY-CHAIN-SECURITY.md's cost test.
"""

from __future__ import annotations

import math
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
class Tone:
    """The lightness and chroma one theme paints every family at."""

    lightness: float
    chroma: float

    def at(self, hue: float) -> Oklch:
        """This tone at *hue*, with chroma pulled back into sRGB if it must be.

        The pullback is the one place families differ in anything but hue, and
        it is not a choice: sRGB simply holds less chroma in the cyan-green
        band than it does in red, at any lightness.

        It has to happen here rather than in a stylesheet. A browser handed an
        out-of-gamut ``oklch()`` clips it, which moves lightness and hue —
        measured at up to nine degrees of hue, more than the separation the
        palette is built on. Reducing chroma keeps the hue exactly where the
        registry declared it.
        """

        hue %= 360
        return Oklch(self.lightness, min(self.chroma, max_chroma(self.lightness, hue)), hue)


# ── The two tones ───────────────────────────────────────────────
#
# Lightness comes from the hand-tuned twelve-slot ramp these replace, which
# centered on 0.60 light and 0.77 dark after many iterations by eye.
#
# Chroma is a target rather than a guarantee, and it is set high — near what
# sRGB holds at the roomiest hues, not at the tightest. A target low enough for
# every hue to reach exactly does exist (0.1055 light, 0.1275 dark, both set by
# the cyan-blue band, which holds roughly half what red does) and produces a
# perfectly even set that reads as washed out. Chroma this far up is worth the
# unevenness: most hues reach it and the cyans come in under, which is the same
# trade the old ramp made when it gave its teal slot 0.09 against 0.15
# elsewhere.
#
# What does not vary is lightness, and that is the half that matters for a
# stacked bar: a segment never looks heavier than its size because its neighbor
# is darker.

LIGHT_THEME = Tone(lightness=0.62, chroma=0.180)
"""Filled swatches on a near-white ground."""

DARK_THEME = Tone(lightness=0.75, chroma=0.150)
"""The same hues on a dark ground. Lighter, because a color needs more
lightness to carry against dark, and less saturated, because sRGB holds less
chroma up there — 0.75 is past the peak."""


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
    "DARK_THEME",
    "LIGHT_THEME",
    "Oklch",
    "Tone",
    "hex_to_oklch",
    "hue_distance",
    "in_srgb_gamut",
    "max_chroma",
    "oklch_to_srgb",
    "widest_hue_gap",
]
