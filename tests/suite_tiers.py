"""The tiers the suite runs in, and the parts ``--shard`` deals a tier into.

Two markers name two properties, and the three pytest tiers are their combinations:

- ``chrome``: the test drives headless Chrome. Every test that uses the ``chrome_profile``
  fixture gets it here, and nothing else may set it: ``tests/suite_gates.py`` fails a
  test that is marked by hand, or that asks for Chrome without the marker. It is the one
  marker that lets a pull request check a test on one interpreter, so no test reaches
  that by being marked.
- ``serial``: the test measures wall-clock time and needs the machine to itself, so it
  never runs beside other workers. A module adds it by hand as
  ``pytest.mark.serial(reason=...)``, with the measurement that forced it as the reason,
  as a module raises its timeout; ``tests/suite_gates.py`` fails one without a reason.
  It says nothing about interpreters: the serial tier runs on every one.

``TIERS`` holds the three ``-m`` expressions. They cover each combination of the two
markers once, so every test is in exactly one tier whatever is marked.

``--shard=I/N`` keeps, of the tests left after ``-m`` and ``-k``, those whose index in
node-ID order is ``I`` modulo ``N``. The ``N`` parts are disjoint and together are the
tier by construction, need no record of durations, and deal one module's tests across
parts, so one slow module does not set a part's floor.

``--shard-by=file`` deals whole files instead: each file, largest first by its count of
selected tests, goes to the part with the fewest tests so far. A module then runs in one
part, its tests in order, as ``--dist loadfile`` runs it on one worker, so a
module-scoped fixture, and a test that relies on an earlier one, behave as they do in
one process. The parts are still disjoint and together the tier.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import pytest

CHROME_MARKER: Final = "chrome"
SERIAL_MARKER: Final = "serial"
# The fixture that owns a headless Chrome's profile; using it is what makes a test ``chrome``.
CHROME_FIXTURE: Final = "chrome_profile"
# What --shard deals into its parts: single tests, or whole files.
BY_TEST: Final = "test"
BY_FILE: Final = "file"
SHARD_UNITS: Final = (BY_TEST, BY_FILE)

# The ``-m`` expressions of the parallel, serial, and Chrome tiers, in that order.
PARALLEL_TIER: Final = f"not {SERIAL_MARKER} and not {CHROME_MARKER}"
SERIAL_TIER: Final = f"{SERIAL_MARKER} and not {CHROME_MARKER}"
CHROME_TIER: Final = CHROME_MARKER
TIERS: Final = (PARALLEL_TIER, SERIAL_TIER, CHROME_TIER)

MARKER_HELP: Final = {
    CHROME_MARKER: (
        "drives headless Chrome; given to every test that uses the chrome_profile fixture, "
        "and never set by hand (tests/suite_tiers.py)"
    ),
    f"{SERIAL_MARKER}(reason)": (
        "measures wall-clock time and needs the machine to itself; set by hand with the "
        "measurement that forced it as the reason (tests/suite_tiers.py)"
    ),
}

_SHARD: Final = re.compile(r"(?P<index>\d+)/(?P<count>\d+)")


@dataclass(frozen=True, slots=True)
class Shard:
    """The ``index``th of ``count`` parts, counted from 1."""

    index: int
    count: int

    def __str__(self) -> str:
        return f"{self.index}/{self.count}"


def parse_shard(value: str) -> Shard:
    """``I/N`` with ``1 <= I <= N``; anything else is refused with the form it takes."""

    match = _SHARD.fullmatch(value.strip())
    if match is None:
        raise argparse.ArgumentTypeError(f"--shard takes I/N, such as 2/4, not {value!r}")
    shard = Shard(int(match["index"]), int(match["count"]))
    if not 1 <= shard.index <= shard.count:
        raise argparse.ArgumentTypeError(
            f"--shard={value} names part {shard.index} of {shard.count}; "
            f"the parts are 1 through {shard.count}"
        )
    return shard


def _file(nodeid: str) -> str:
    return nodeid.split("::", 1)[0]


def _dealt_by_file(nodeids: Sequence[str], shard: Shard) -> list[bool]:
    sizes = Counter(_file(nodeid) for nodeid in nodeids)
    loads = [0] * shard.count
    part_of: dict[str, int] = {}
    for name in sorted(sizes, key=lambda name: (-sizes[name], name)):
        part = min(range(shard.count), key=lambda index: (loads[index], index))
        part_of[name] = part
        loads[part] += sizes[name]
    return [part_of[_file(nodeid)] == shard.index - 1 for nodeid in nodeids]


def dealt(nodeids: Sequence[str], shard: Shard, by: str = BY_TEST) -> list[bool]:
    """Whether each test, in the order given, is in *shard*.

    By test, the ``i``th test of node-ID order, counted from 1, is in the part whose index
    ``i`` is congruent to modulo ``count``, so every test is in exactly one part and the
    parts differ in size by one at most. By file, every test of a file is in its file's
    part, and the parts differ in size by at most the largest file's count.
    """

    if by == BY_FILE:
        return _dealt_by_file(nodeids, shard)
    ranked = sorted(range(len(nodeids)), key=lambda position: nodeids[position])
    kept = [False] * len(nodeids)
    for rank, position in enumerate(ranked):
        kept[position] = rank % shard.count == shard.index - 1
    return kept


def pytest_itemcollected(item: pytest.Item) -> None:
    """Mark every test that uses ``chrome_profile``, directly or through a fixture."""

    if CHROME_FIXTURE in getattr(item, "fixturenames", ()):
        item.add_marker(CHROME_MARKER)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Deal the tests ``-m`` and ``-k`` left into ``--shard``'s part; last, so it is after them."""

    shard: Shard | None = config.getoption("shard")
    if shard is None:
        return
    by: str = config.getoption("shard_by") or BY_TEST
    kept = dealt([item.nodeid for item in items], shard, by)
    dropped = [item for item, keep in zip(items, kept, strict=True) if not keep]
    if dropped:
        config.hook.pytest_deselected(items=dropped)
    items[:] = [item for item, keep in zip(items, kept, strict=True) if keep]
