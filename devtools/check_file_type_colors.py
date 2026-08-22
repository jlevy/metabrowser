"""Hold the two rules the file-type palette rests on.

**A hue is GitHub's, or it is clear of everything else.** A family that names a
linguist language takes that language's hue exactly, including where two of
GitHub's own colors are close together, because a reader who knows Ruby is red
is better served by red than by a hue moved to win a distance metric. A family
GitHub names no color for takes a hue that leaves it :data:`MINIMUM_HOUSE_DELTA_E`
clear of every other family, as painted, in both themes.

**Every family is painted inside a band the theme owns.** Lightness and chroma
come from the theme, and where a family sits inside them comes from its rank
among the upstream colors — never from the upstream values themselves, whose
range is far wider than a usable palette. The check reports which hues come in
under the chroma target and fails only if one lands outside sRGB, which would
mean the pullback broke.

The separation floor is measured in Oklab delta-E rather than in degrees of
hue, because degrees stopped being the thing worth measuring once lightness and
chroma varied: two hues a degree apart are the same color at one tone and
plainly different at two. One perceptual rule replaces the two the palette used
to need.

Collisions between two upstream colors are reported and not failed. They are
GitHub's, we do not redistribute them, and the derivation already takes the
worst of them from a delta-E of 0.0020 to 0.0237. What survives is listed at the
end of the report.

Run ``--suggest`` when adding a family GitHub has no color for: it prints the
hue furthest from everything already declared, and the colors that hue is
painted as. Note that adding a family that *does* name a linguist color shifts
its neighbours by a rank step, because a position is relative to the whole set.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from metabrowser.color_oklch import (
    ACHROMATIC_CHROMA,
    DARK_THEME,
    LIGHT_THEME,
    Oklch,
    ToneBand,
    TonePosition,
    delta_e,
    hex_to_oklch,
    hue_distance,
    in_srgb_gamut,
    widest_hue_gap,
)
from metabrowser.file_type_registry import (
    FileTypeFamily,
    FileTypeRegistry,
    load_file_type_registry,
)

MINIMUM_HOUSE_DELTA_E = 0.015
"""Oklab delta-E a color we chose must clear every other family by, in both themes.

The perceptual equivalent of the five degrees of hue this replaces: an arc that
wide at the old flat tone measured 0.0157, so the floor is where it always was,
now stated in the units that survive a varying tone.

Low on purpose. It is a floor against collision, not a spacing target: 56
families cannot be spread evenly across a band whose crowded regions are
GitHub's and not ours to redistribute. The families placed so far clear it at
0.0164 in light and 0.0160 in dark, and --suggest keeps that true by handing
out the widest gap rather than the first hue that passes.
"""

HUE_TOLERANCE = 0.02
"""Degrees a declared hue may differ from its upstream conversion — rounding in
the two decimal places the registry writes, and nothing more."""

NOTICEABLE = 0.02
"""Roughly where an Oklab difference stops being visible side by side. Used for
reporting only: it is the bar the palette is measured against, not a rule."""


@dataclass(frozen=True, slots=True)
class Problem:
    family_id: str
    detail: str


def _painted(registry: FileTypeRegistry, band: ToneBand) -> dict[str, Oklch]:
    """Every family as this theme paints it."""

    return {
        family.id: band.at(family.hue, registry.tone_position(family.id))
        for family in registry.families
    }


def _themes() -> tuple[tuple[str, ToneBand], ...]:
    return (("light", LIGHT_THEME), ("dark", DARK_THEME))


def _upstream_problems(family: FileTypeFamily) -> list[Problem]:
    if family.linguist is None or family.linguist_color is None:
        return []
    upstream = hex_to_oklch(family.linguist_color)
    if family.deviation is not None:
        # A deviated family keeps its provenance and gives up the hue rule; it
        # is held to the separation floor instead, like a colour we chose.
        # What it may not do is claim a deviation it does not make, which is
        # how a reason goes stale without anyone noticing.
        moved_hue = hue_distance(family.hue, upstream.hue) > HUE_TOLERANCE
        if not moved_hue and family.lightness_rank is None:
            return [
                Problem(
                    family.id,
                    f"declares a deviation but paints where {family.linguist} "
                    f"{family.linguist_color} puts it; drop the deviation or make it",
                )
            ]
        return []
    if upstream.chroma < ACHROMATIC_CHROMA:
        return [
            Problem(
                family.id,
                f"{family.linguist} is {family.linguist_color}, which is grey "
                f"(chroma {upstream.chroma:.4f}) and carries no hue to take; "
                f"drop linguist and linguist_color and choose a free hue instead",
            )
        ]
    if hue_distance(family.hue, upstream.hue) > HUE_TOLERANCE:
        return [
            Problem(
                family.id,
                f"hue {family.hue:.2f} does not match {family.linguist} "
                f"{family.linguist_color}, which converts to {upstream.hue:.2f}; "
                f"GitHub's hues are taken unchanged",
            )
        ]
    return []


def _separation_problems(registry: FileTypeRegistry) -> list[Problem]:
    """A color we chose has to be clear of every other family, in both themes."""

    problems: list[Problem] = []
    families = registry.families
    for name, band in _themes():
        painted = _painted(registry, band)
        for family in families:
            if family.linguist is not None and family.deviation is None:
                continue  # Upstream colors are taken as they are, collisions included.
            gap, nearest = min(
                (
                    (delta_e(painted[family.id], painted[other.id]), other.id)
                    for other in families
                    if other.id != family.id
                ),
                key=lambda pair: pair[0],
            )
            if gap < MINIMUM_HOUSE_DELTA_E:
                suggestion = widest_hue_gap(
                    tuple(other.hue for other in families if other.id != family.id)
                )
                problems.append(
                    Problem(
                        family.id,
                        f"hue {family.hue:.2f} paints {gap:.4f} from {nearest} in the "
                        f"{name} theme, under the {MINIMUM_HOUSE_DELTA_E} floor for a "
                        f"color we chose; {suggestion:.2f} is the freest hue",
                    )
                )
    return problems


def _tone_problems(registry: FileTypeRegistry) -> list[Problem]:
    """The band may move chroma to reach sRGB, and nothing else."""

    problems: list[Problem] = []
    for name, band in _themes():
        for family in registry.families:
            position = registry.tone_position(family.id)
            painted = band.at(family.hue, position)
            expected = band.lightness + band.spread * (2 * position.lightness_rank - 1)
            if painted.lightness != expected or painted.hue != family.hue % 360:
                problems.append(
                    Problem(
                        family.id,
                        f"the {name} band moved something other than chroma at hue "
                        f"{family.hue:.2f}: {painted.css()}",
                    )
                )
            elif not in_srgb_gamut(painted):
                problems.append(
                    Problem(
                        family.id,
                        f"the {name} band lands outside sRGB at hue {family.hue:.2f}: "
                        f"{painted.css()}; the chroma pullback failed",
                    )
                )
    return problems


def _position_problems(registry: FileTypeRegistry) -> list[Problem]:
    """A position is a place in the band, so it has to be one — unless a family
    says in writing that it is leaving.

    Leaving the band is the one thing checked here whose cost is paid by
    something other than the palette: the band is what bounds how much a
    stacked-bar segment can read heavier than its size, so a family outside it
    is a segment that can. That is allowed, deliberately and in prose, and
    never by accident.
    """

    problems: list[Problem] = []
    for family in registry.families:
        position = registry.tone_position(family.id)
        if not 0.0 <= position.chroma_ratio <= 1.0:
            problems.append(
                Problem(
                    family.id,
                    f"chroma_ratio is {position.chroma_ratio:.4f}, outside the band",
                )
            )
        if not 0.0 <= position.lightness_rank <= 1.0 and family.deviation is None:
            problems.append(
                Problem(
                    family.id,
                    f"lightness_rank is {position.lightness_rank:.4f}, outside the "
                    f"band, with no deviation saying why",
                )
            )
    return problems


def _pairs(painted: dict[str, Oklch]) -> list[tuple[float, str, str]]:
    ids = sorted(painted)
    return sorted(
        (delta_e(painted[left], painted[right]), left, right)
        for index, left in enumerate(ids)
        for right in ids[index + 1 :]
    )


def _report(registry: FileTypeRegistry) -> None:
    """Print what the rules permit but a maintainer still wants to see."""

    families = registry.families
    upstream = [
        family for family in families if family.linguist is not None and family.deviation is None
    ]
    house = [family for family in families if family.linguist is None]
    deviated = [family for family in families if family.deviation is not None]
    print(
        f"{len(families)} families: {len(upstream)} carry GitHub's hue, "
        f"{len(house)} were placed in free gaps, {len(deviated)} deviate"
    )

    for family in deviated:
        reason = " ".join((family.deviation or "").split())
        head, _, _ = reason.partition(". ")
        outside = "" if family.lightness_rank is None else ", outside the band"
        print(f"  {family.id}: hue {family.hue:.2f}{outside} — {head or reason}.")

    from_github = {family.id for family in upstream}
    tightest: dict[tuple[str, str], float] = {}
    for name, band in _themes():
        painted = _painted(registry, band)
        pairs = _pairs(painted)
        floor, left, right = pairs[0]
        under = sum(1 for gap, _, _ in pairs if gap < NOTICEABLE)
        lightness = sorted(color.lightness for color in painted.values())
        chroma = sorted(color.chroma for color in painted.values())
        pulled = [
            family
            for family in families
            if painted[family.id].chroma
            < band.chroma
            * (
                1
                - band.chroma_spread
                + 2 * band.chroma_spread * registry.tone_position(family.id).chroma_ratio
            )
            - 1e-9
        ]
        print(f"{name} band:")
        print(f"  closest pair    {floor:.4f}  {left} / {right}")
        print(f"  under {NOTICEABLE}      {under} of {len(pairs)} pairs")
        print(f"  painted L       {lightness[0]:.3f}-{lightness[-1]:.3f}")
        print(f"  painted C       {chroma[0]:.3f}-{chroma[-1]:.3f}")
        print(
            f"  {len(pulled)} of {len(families)} hues come in under their target "
            f"chroma, because sRGB holds less there"
        )
        if house:
            house_floor = min(
                min(
                    delta_e(painted[family.id], painted[other.id])
                    for other in families
                    if other.id != family.id
                )
                for family in house
            )
            print(f"  placed hues clear everything else by {house_floor:.4f}")
        for gap, a, b in pairs:
            if gap >= NOTICEABLE or a not in from_github or b not in from_github:
                continue
            key = (a, b)
            tightest[key] = min(gap, tightest.get(key, gap))

    if tightest:
        print(
            f"pairs still under {NOTICEABLE} in a theme, both of them GitHub's own "
            f"and so kept (tighter theme shown):"
        )
        for (left, right), gap in sorted(tightest.items(), key=lambda item: item[1])[:8]:
            print(f"  {gap:.4f}  {left} / {right}")


def _suggest(registry: FileTypeRegistry) -> None:
    taken = tuple(family.hue for family in registry.families)
    hue = widest_hue_gap(taken)
    gap = min(hue_distance(hue, other) for other in taken)
    print(f"hue = {hue:.2f}   # {gap:.1f} degrees clear of every declared hue")
    print("# no linguist_color, so it sits at the centre of the band:")
    center = TonePosition(lightness_rank=0.5, chroma_ratio=0.5)
    for name, band in _themes():
        print(f"  {name}: {band.at(hue, center).css()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suggest",
        action="store_true",
        help="print a free hue for a new family instead of checking",
    )
    parser.add_argument("--quiet", action="store_true", help="report nothing when clean")
    arguments = parser.parse_args()

    registry = load_file_type_registry()
    if arguments.suggest:
        _suggest(registry)
        return 0

    problems: list[Problem] = []
    for family in registry.families:
        problems.extend(_upstream_problems(family))
    problems.extend(_position_problems(registry))
    problems.extend(_separation_problems(registry))
    problems.extend(_tone_problems(registry))

    if problems:
        print("file-type colors: rules broken", file=sys.stderr)
        for problem in problems:
            print(f"  {problem.family_id}: {problem.detail}", file=sys.stderr)
        return 1
    if not arguments.quiet:
        _report(registry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
