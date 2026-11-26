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

``--shard=I/N`` keeps, of the tests left after ``-m`` and ``-k``, the ``I``th of ``N``
parts that ``devtools/shard_weights.py`` deals them into by the seconds CI measured for
each test: heaviest first, each to the part with the least so far. The parts are disjoint
and together are the tier, the same in every process that computes them, and about the
same length, which is what a part's time limit needs. One module's tests are dealt
across parts, so one slow module does not set a part's floor. Until run 45062416967 the
deal was by rank in node-ID order, which needs no record of durations and was even
while no test was long; by then one test took 94 s and one part of the Chrome tier's
four held 360 s of its 790 s.

``--shard-by=file`` deals whole files instead, by the seconds measured for each file. A
module then runs in one part, its tests in order, as ``--dist loadfile`` runs it on one
worker, so a module-scoped fixture, and a test that relies on an earlier one, behave as
they do in one process. The parts are still disjoint and together the tier.

No option leaves out a tier's slow tests. Until 2026-11-25 ``--skip-slow`` dropped the
tests measured at 20 s or more from a pull request's Chrome tier, and three pull
requests that week merged green and broke one of them on ``main`` (bead mb-593d). A run
of the Chrome tier is now every Chrome test, in more parts where it has to be shorter
(``devtools/ci_plan.sh``).

A tier or a shard may hold no test, as the serial tier will once its last module no
longer needs the machine, and a shard does when it is numbered past the tier's size, or,
dealt by file, past its number of files.
pytest exits 5 when nothing is left to run, which would fail ``make test`` with no test
failing. ``EmptyTiers`` turns that into success only where the emptiness is a tier's:
``-m`` is one of ``TIERS`` exactly, or ``--shard`` is given, and the selection itself
deselected the tests this process collected. A misspelt ``-m`` expression, or a run that
collected nothing at all, still exits 5. Under pytest-xdist the workers deselect and the
controlling process counts nothing, so an empty parallel tier still fails, which it can
only be by mistake.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

import pytest

from devtools import shard_weights

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


def _test(nodeid: str) -> str:
    return nodeid


def dealt(
    nodeids: Sequence[str],
    shard: Shard,
    by: str = BY_TEST,
    seconds: Mapping[str, float] | None = None,
) -> list[bool]:
    """Whether each test, in the order given, is in *shard*.

    By test, each test is a unit; by file, each file is, and every test of a file is in
    its file's part. The units are dealt by ``devtools.shard_weights.parts``, weighed by
    *seconds*, or else by the measured seconds of the tests or the files, so every test
    is in exactly one part, whatever the order, and the heaviest part holds at most the
    mean plus the heaviest unit.
    """

    unit, table = (_file, shard_weights.FILES) if by == BY_FILE else (_test, shard_weights.TESTS)
    measured = shard_weights.load(table) if seconds is None else seconds
    part_of = shard_weights.parts(map(unit, nodeids), shard.count, measured)
    return [part_of[unit(nodeid)] == shard.index - 1 for nodeid in nodeids]


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


def empty_by_selection(markexpr: str, sharded: bool, deselected: int) -> bool:
    """Whether a run that left no test to run is a tier or shard that holds none."""

    return deselected > 0 and (" ".join(markexpr.split()) in TIERS or sharded)


class EmptyTiers:
    """Success, not exit 5, for a tier or a shard that selected no test."""

    def __init__(self) -> None:
        self.deselected = 0
        self.excused = ""

    def pytest_deselected(self, items: Sequence[pytest.Item]) -> None:
        self.deselected += len(items)

    @pytest.hookimpl(trylast=True)
    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        if exitstatus != pytest.ExitCode.NO_TESTS_COLLECTED:
            return
        markexpr = str(session.config.getoption("markexpr") or "")
        shard: Shard | None = session.config.getoption("shard")
        if empty_by_selection(markexpr, shard is not None, self.deselected):
            session.exitstatus = pytest.ExitCode.OK
            chosen = " and ".join(
                part
                for part in (
                    f"-m {markexpr!r}" if markexpr else "",
                    f"--shard={shard}" if shard else "",
                )
                if part
            )
            self.excused = f"suite tiers: {chosen} selects no test here, which a tier may"

    def pytest_terminal_summary(self, terminalreporter: pytest.TerminalReporter) -> None:
        if self.excused:
            terminalreporter.write_line(self.excused)
