"""Oklch color math: the plain sRGB conversion, plus a legibility clamp.

A file-type family declares its color as an upstream sRGB hex — GitHub's, for
the families GitHub names — and this module converts it the same way a browser
does. ``hex_to_oklch("#3572a5")`` returns ``oklch(53.50% 0.1016 246.53)``,
which is what dev tools report for that color.

Conversion is the whole mapping. Hue and chroma are kept as converted, so the
palette is GitHub's palette rather than an interpretation of it.

The one adjustment is lightness, and only where a color is otherwise unusable.
Upstream lightness runs from 0.27 (Lua's navy) to 0.90 (JavaScript's yellow),
and the ends of that range disappear against one theme or the other. Each theme
therefore clamps lightness into a band it can show, and pulls chroma back to
whatever sRGB holds at the resulting lightness. Colors already inside the band —
most of them — pass through untouched.

No third-party color library: these are the standard Oklab matrices, and a
dependency for thirty lines of arithmetic would not survive
SUPPLY-CHAIN-SECURITY.md's cost test.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# ── Theme legibility bands ──────────────────────────────────────
#
# The range of lightness a theme can actually show. A color inside its band is
# used as converted; one outside moves to the nearest edge, which is the least
# change that makes it visible.
#
# Set wide on purpose. Upstream lightness across the 38 languages we map spans
# 0.19 to 0.90 with a median of 0.60, so a narrow band would collapse most of
# the set onto its edges and throw away the distinctions GitHub draws — an
# earlier pair at 0.45-0.75 and 0.60-0.88 clamped 11 and 21 of them. These
# clamp 8 and 7, which is about the count that is genuinely unusable: navies
# near 0.2 on either ground, and JavaScript's 0.90 yellow on the light one.
LIGHT_THEME_LIGHTNESS = (0.40, 0.78)
"""Usable lightness on a near-white ground: below reads as a smudge, above
washes out."""

DARK_THEME_LIGHTNESS = (0.45, 0.90)
"""Usable lightness on a dark ground. Both ends sit higher than the light
theme's, because the same color needs more lightness to read against dark."""

_SRGB_EPSILON = 1e-4


@dataclass(frozen=True, slots=True)
class Oklch:
    """A color as lightness (0-1), chroma, and hue in degrees."""

    lightness: float
    chroma: float
    hue: float

    def css(self) -> str:
        """The CSS ``oklch()`` form, rounded to what a stylesheet needs."""

        return f"oklch({self.lightness * 100:.2f}% {self.chroma:.4f} {self.hue:.2f})"


def hex_to_oklch(value: str) -> Oklch:
    """Convert an sRGB hex string, the way a browser's dev tools do."""

    text = value.strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"expected a six-digit hex color, got {value!r}")
    red, green, blue = (int(text[index : index + 2], 16) / 255 for index in (0, 2, 4))
    return _linear_srgb_to_oklch(
        (_srgb_to_linear(red), _srgb_to_linear(green), _srgb_to_linear(blue))
    )


def for_theme(color: Oklch, band: tuple[float, float]) -> Oklch:
    """The color as this theme can show it.

    Lightness is clamped into *band*; chroma follows only if that move takes it
    out of gamut, in which case it drops to what sRGB holds at the new
    lightness. Hue never changes, which is what keeps a family the same color on
    both themes.
    """

    low, high = band
    lightness = min(max(color.lightness, low), high)
    chroma = min(color.chroma, max_chroma(lightness, color.hue))
    return Oklch(lightness, chroma, color.hue % 360)


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
    "DARK_THEME_LIGHTNESS",
    "LIGHT_THEME_LIGHTNESS",
    "Oklch",
    "for_theme",
    "hex_to_oklch",
    "hue_distance",
    "in_srgb_gamut",
    "max_chroma",
    "oklch_to_srgb",
]
