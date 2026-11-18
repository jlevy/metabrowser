"""The time each test file took, printed at the end of a run for ``devtools/suite_report.py``.

A run's output used to say where its time went by the gaps between pytest's progress
lines, one line per file. Under pytest-xdist the workers' results arrive interleaved and
the progress lines name no file, so that reading has nothing to go on. Each test's report
carries its own duration and reaches the process that prints the summary, under xdist
too, so the time of a file is summed from its tests' setup, call, and teardown here.

``--file-durations=N`` prints the ``N`` slowest files, and ``0`` prints every one, as
``--durations`` does for tests:

    ==== slowest 2 of 380 test files, 901.42 s of test time ====
    55.90s tests/test_github_pulls.py
    42.61s tests/test_checkout_overlay.py

Under ``--dist loadfile`` a file runs on one worker, its tests one after another, so its
sum is the time it held that worker. A session-scoped fixture is counted in the file of
the first test that asked for it.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Final

import pytest

OPTION: Final = "file_durations"
# The section rule's title, as ``devtools/suite_report.py`` reads it.
TITLE: Final = "{shown} of {files} test files, {seconds:.2f} s of test time"


class FileTimes:
    """Seconds per test file, from every report the session receives."""

    def __init__(self) -> None:
        self.seconds: defaultdict[str, float] = defaultdict(float)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self.seconds[report.nodeid.split("::", 1)[0]] += report.duration

    def pytest_terminal_summary(
        self, terminalreporter: pytest.TerminalReporter, config: pytest.Config
    ) -> None:
        wanted: int | None = config.getoption(OPTION)
        if wanted is None or not self.seconds or hasattr(config, "workerinput"):
            return
        ranked = sorted(self.seconds.items(), key=lambda item: (-item[1], item[0]))
        shown = ranked if wanted <= 0 else ranked[:wanted]
        title = TITLE.format(
            shown=f"slowest {len(shown)}" if wanted > 0 else "all",
            files=len(ranked),
            seconds=sum(self.seconds.values()),
        )
        terminalreporter.write_sep("=", title)
        for path, seconds in shown:
            terminalreporter.write_line(f"{seconds:.2f}s {path}")


def add_option(parser: pytest.Parser) -> None:
    parser.addoption(
        "--file-durations",
        dest=OPTION,
        type=int,
        default=None,
        metavar="N",
        help="list the N slowest test files at the end, or every one for 0 (tests/suite_timing.py)",
    )
