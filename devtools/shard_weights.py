"""The measured seconds each shard dealer weighs by, and how the dealers deal.

CI splits three things into parts that run on separate runners: a pytest tier by test or
by file (``tests/suite_tiers.py``, ``--shard``), and the goldens by file
(``devtools/run_goldens.py``, ``--shard``). A job's time limit holds only while its parts
are about the same length, and the length of a part is the time of its units, which
nothing but a run can say. Each stand-in tried for it stopped tracking it: a test's rank
in node-ID order put a 94-second test and 360 s of the Chrome tier's 790 s in one part of
four, a golden's size put 568 s of 844 s in one part of two, and a file's count of tests
left the unit tier's parts 123 s of test time apart (run 45062416967; bead mb-j5j2). So
the dealers weigh by the seconds CI measured, which ``WEIGHTS`` holds:

- ``tests``: seconds per test node ID, for a tier dealt by test (Chrome and serial);
- ``files``: seconds per test file of the parallel tier, which is dealt by file;
- ``goldens``: seconds per golden file;
- ``source``: the CI runs the seconds were read from, each with its commit.

**Dealing** (``parts``). Units go heaviest first, ties by name, each to the part that
holds the least so far, ties to the lowest part. The heaviest part then holds at most the
mean plus the heaviest unit, however the weights fall. The answer depends on the set of
names and on ``WEIGHTS`` alone, never on the order the names arrive in, so each runner
computes the same parts, and every unit is in exactly one.

**A unit with no measurement** weighs ``fallback``: see there.

**Refreshing.** ``make shard-weights`` rewrites ``WEIGHTS`` from a CI run's job logs;
``devtools/refresh_shard_weights.py`` says what it reads and when to run it. A stale
weight makes the parts less even, never wrong.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final, cast

ROOT: Final = Path(__file__).resolve().parents[1]
# The measured seconds, beside this module; ``make shard-weights`` writes it.
WEIGHTS: Final = Path(__file__).with_name("shard_weights.json")

# The tables of WEIGHTS, and the record of where their seconds came from.
TESTS: Final = "tests"
FILES: Final = "files"
GOLDENS: Final = "goldens"
TABLES: Final = (TESTS, FILES, GOLDENS)
SOURCE: Final = "source"

# What a unit weighs when no unit dealt with it has a measurement, as when WEIGHTS is
# missing: every unit the same, so the parts hold the same number of units.
UNMEASURED_S: Final = 1.0

type Json = dict[str, object]


class WeightsError(Exception):
    """The weights file cannot be read; the message says why."""


# ── Dealing ────────────────────────────────────────────────────────────────────


def load(table: str, path: Path = WEIGHTS) -> dict[str, float]:
    """The seconds of *table*; none when *path* does not exist, so every unit weighs the same."""

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        found = cast("Json", cast("Json", json.loads(text)).get(table) or {})
        return {str(name): float(cast("float", seconds)) for name, seconds in found.items()}
    except (ValueError, TypeError, AttributeError) as error:
        raise WeightsError(f"{path} does not hold a {table} table of seconds: {error}") from error


def fallback(names: Iterable[str], seconds: Mapping[str, float]) -> float:
    """What a unit of *names* with no measurement weighs: the median of those that have one.

    A unit is unlisted because it is new since the last refresh, or because pytest prints
    no phase shorter than 5 ms and all three of its phases were. Nothing says which, so it
    is taken to cost what a typical unit dealt beside it costs. That is honest for both
    where it matters: among the Chrome tests, the unit files, and the goldens nearly every
    unit is listed, so an unlisted one is new and most likely ordinary, and among the
    serial tests, where half are too fast to list, the median is itself a few
    hundredths of a second. The least measured weight would be near nothing, and units
    that weigh nothing all go to the one part that is lightest when they are dealt, so new
    tests would pile up there until the next refresh; the median spreads them.
    """

    measured = [seconds[name] for name in set(names) if name in seconds]
    return statistics.median(measured) if measured else UNMEASURED_S


def parts(names: Iterable[str], count: int, seconds: Mapping[str, float]) -> dict[str, int]:
    """The part, from 0, of each of *names*: heaviest first, each to the lightest part."""

    units = set(names)
    unlisted = fallback(units, seconds)
    weights = {name: seconds.get(name, unlisted) for name in units}
    loads = [0.0] * count
    part_of: dict[str, int] = {}
    for name in sorted(units, key=lambda name: (-weights[name], name)):
        part = min(range(count), key=lambda index: (loads[index], index))
        part_of[name] = part
        loads[part] += weights[name]
    return part_of
