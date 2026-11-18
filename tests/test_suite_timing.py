"""``tests/suite_timing.py``: each test file's time, summed from its tests' reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import pytest

from tests.suite_timing import OPTION, TITLE, FileTimes


@dataclass
class _Report:
    nodeid: str
    duration: float


@dataclass
class _Config:
    wanted: int | None
    worker: bool = False

    def getoption(self, name: str) -> int | None:
        assert name == OPTION
        return self.wanted

    def __getattr__(self, name: str) -> object:
        if name == "workerinput" and self.worker:
            return {}
        raise AttributeError(name)


@dataclass
class _Terminal:
    written: list[str] = field(default_factory=lambda: list[str]())

    def write_sep(self, sep: str, title: str) -> None:
        self.written.append(f"{sep} {title}")

    def write_line(self, line: str) -> None:
        self.written.append(line)


def _summary(times: FileTimes, config: _Config) -> list[str]:
    terminal = _Terminal()
    times.pytest_terminal_summary(
        cast("pytest.TerminalReporter", terminal), cast("pytest.Config", config)
    )
    return terminal.written


@pytest.fixture
def times() -> FileTimes:
    """Two files: one test's three phases in the first, two tests in the second."""

    times = FileTimes()
    for nodeid, duration in [
        ("tests/test_a.py::test_one", 0.25),
        ("tests/test_a.py::test_one", 2.0),
        ("tests/test_a.py::test_one", 0.25),
        ("tests/test_b.py::test_two[x]", 1.0),
        ("tests/test_b.py::TestGroup::test_three", 0.5),
    ]:
        times.pytest_runtest_logreport(cast("pytest.TestReport", _Report(nodeid, duration)))
    return times


def test_a_file_s_time_is_the_sum_of_its_tests_phases(times: FileTimes) -> None:
    assert dict(times.seconds) == {"tests/test_a.py": 2.5, "tests/test_b.py": 1.5}


def test_the_slowest_files_are_listed_under_the_count_of_all(times: FileTimes) -> None:
    title = TITLE.format(shown="slowest 1", files=2, seconds=4.0)
    assert _summary(times, _Config(1)) == [f"= {title}", "2.50s tests/test_a.py"]
    every = TITLE.format(shown="all", files=2, seconds=4.0)
    assert _summary(times, _Config(0)) == [
        f"= {every}",
        "2.50s tests/test_a.py",
        "1.50s tests/test_b.py",
    ]


def test_nothing_is_listed_unless_asked_or_on_a_worker(times: FileTimes) -> None:
    assert _summary(times, _Config(None)) == []
    assert _summary(times, _Config(0, worker=True)) == []
    assert _summary(FileTimes(), _Config(0)) == []
