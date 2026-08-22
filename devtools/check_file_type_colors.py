"""Hold the two rules the file-type palette rests on.

**A hue is GitHub's, or it is clear of everything else.** A family that names a
linguist language takes that language's hue exactly, including where two of
GitHub's own colors are close together, because a reader who knows Ruby is red
is better served by red than by a hue moved to win a distance metric. A family
GitHub names no color for takes a hue that clears every other declared hue by
:data:`MINIMUM_HOUSE_SEPARATION`.

**Every family is painted at one tone.** Lightness and chroma come from the
theme, not the family — so a segment never looks heavier than its size — and
the only permitted variation is sRGB itself, which holds less chroma at some
hues than at others. The check reports which hues come in under the target and
fails only if one lands outside sRGB, which would mean the pullback broke.

Run ``--suggest`` when adding a family GitHub has no color for: it prints the
hue furthest from everything already declared, which is the hue to write down.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from metabrowser.color_oklch import (
    ACHROMATIC_CHROMA,
    DARK_THEME,
    LIGHT_THEME,
    hex_to_oklch,
    hue_distance,
    in_srgb_gamut,
    max_chroma,
    widest_hue_gap,
)
from metabrowser.file_type_registry import FileTypeFamily, load_file_type_registry

MINIMUM_HOUSE_SEPARATION = 5.0
"""Degrees a hue we chose must clear every other declared hue by.

Low on purpose. It is a floor against collision, not a spacing target: 56
families cannot be spread evenly around a circle whose crowded regions are
GitHub's and not ours to redistribute. The families placed so far clear it with
room to spare, and --suggest keeps that true by handing out the widest gap
rather than the first hue that passes."""

HUE_TOLERANCE = 0.02
"""Degrees a declared hue may differ from its upstream conversion — rounding in
the two decimal places the registry writes, and nothing more."""


@dataclass(frozen=True, slots=True)
class Problem:
    family_id: str
    detail: str


def _upstream_problems(family: FileTypeFamily) -> list[Problem]:
    if family.linguist is None or family.linguist_color is None:
        return []
    upstream = hex_to_oklch(family.linguist_color)
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


def _separation_problems(families: tuple[FileTypeFamily, ...]) -> list[Problem]:
    problems: list[Problem] = []
    for family in families:
        if family.linguist is not None:
            continue  # Upstream hues are taken as they are, collisions included.
        crowding = [
            (hue_distance(family.hue, other.hue), other)
            for other in families
            if other.id != family.id
        ]
        gap, nearest = min(crowding, key=lambda pair: pair[0])
        if gap < MINIMUM_HOUSE_SEPARATION:
            suggestion = widest_hue_gap(
                tuple(other.hue for other in families if other.id != family.id)
            )
            problems.append(
                Problem(
                    family.id,
                    f"hue {family.hue:.2f} is {gap:.2f} degrees from {nearest.id} "
                    f"({nearest.hue:.2f}), under the {MINIMUM_HOUSE_SEPARATION:.0f} "
                    f"degree floor for a hue we chose; {suggestion:.2f} is free",
                )
            )
    return problems


def _tone_problems(families: tuple[FileTypeFamily, ...]) -> list[Problem]:
    problems: list[Problem] = []
    for name, tone in (("light", LIGHT_THEME), ("dark", DARK_THEME)):
        for family in families:
            painted = tone.at(family.hue)
            if painted.lightness != tone.lightness or painted.hue != family.hue % 360:
                problems.append(
                    Problem(
                        family.id,
                        f"the {name} tone moved something other than chroma at hue "
                        f"{family.hue:.2f}: {painted.css()}",
                    )
                )
            elif not in_srgb_gamut(painted):
                problems.append(
                    Problem(
                        family.id,
                        f"the {name} tone lands outside sRGB at hue {family.hue:.2f}: "
                        f"{painted.css()}; the chroma pullback failed",
                    )
                )
    return problems


def _report(families: tuple[FileTypeFamily, ...]) -> None:
    """Print what the rules permit but a maintainer still wants to see."""

    upstream = [family for family in families if family.linguist is not None]
    house = [family for family in families if family.linguist is None]
    print(
        f"{len(families)} families: {len(upstream)} carry GitHub's hue, "
        f"{len(house)} were placed in free gaps"
    )
    if house:
        floor = min(
            min(hue_distance(family.hue, other.hue) for other in families if other is not family)
            for family in house
        )
        print(f"tightest placed hue clears everything else by {floor:.1f} degrees")
    for name, tone in (("light", LIGHT_THEME), ("dark", DARK_THEME)):
        under = [
            family for family in families if max_chroma(tone.lightness, family.hue) < tone.chroma
        ]
        print(
            f"{name} tone: {len(under)} of {len(families)} hues come in under chroma "
            f"{tone.chroma}, because sRGB holds less there"
        )
    close = sorted(
        (hue_distance(a.hue, b.hue), a.id, b.id)
        for index, a in enumerate(upstream)
        for b in upstream[index + 1 :]
    )[:5]
    print("closest upstream pairs, which are GitHub's own and are kept:")
    for gap, left, right in close:
        print(f"  {gap:5.2f} degrees  {left} / {right}")


def _suggest(families: tuple[FileTypeFamily, ...]) -> None:
    taken = tuple(family.hue for family in families)
    hue = widest_hue_gap(taken)
    gap = min(hue_distance(hue, other) for other in taken)
    print(f"hue = {hue:.2f}   # {gap:.1f} degrees clear of every declared hue")
    for tone_name, tone in (("light", LIGHT_THEME), ("dark", DARK_THEME)):
        print(f"  {tone_name}: {tone.at(hue).css()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suggest",
        action="store_true",
        help="print a free hue for a new family instead of checking",
    )
    parser.add_argument("--quiet", action="store_true", help="report nothing when clean")
    arguments = parser.parse_args()

    families = load_file_type_registry().families
    if arguments.suggest:
        _suggest(families)
        return 0

    problems: list[Problem] = []
    for family in families:
        problems.extend(_upstream_problems(family))
    problems.extend(_separation_problems(families))
    problems.extend(_tone_problems(families))

    if problems:
        print("file-type colors: rules broken", file=sys.stderr)
        for problem in problems:
            print(f"  {problem.family_id}: {problem.detail}", file=sys.stderr)
        return 1
    if not arguments.quiet:
        _report(families)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
