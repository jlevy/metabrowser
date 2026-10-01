"""Run the modules that rewrite goldens, and fail if any of their tests was skipped.

``make golden-update`` claims to regenerate every recording and every in-process
transcript. A recorder that skips, because Node is missing, the installed Git is below
the acquisition floor, or the run is root, regenerates nothing and still reports
success, so the claim would then depend on the host without saying so. This runs the
named test modules with ``GOLDEN_UPDATE=1`` and turns any skip into a failure that
names the test and its reason.

    python -m devtools.golden_update tests/test_one.py tests/test_two.py
"""

from __future__ import annotations

import os
import sys

import pytest

from devtools.check_goldens import UPDATE_ENV


class SkipCollector:
    """Remember every test and every module that was skipped, with the reason given."""

    def __init__(self) -> None:
        self.skipped: list[str] = []

    def _record(self, report: pytest.TestReport | pytest.CollectReport) -> None:
        # An expected failure is reported as a skip and is not one.
        if not report.skipped or hasattr(report, "wasxfail"):
            return
        detail = report.longrepr
        reason = str(detail[2]) if isinstance(detail, tuple) else str(detail)
        self.skipped.append(f"{report.nodeid}: {reason.removeprefix('Skipped: ')}")

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self._record(report)

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        self._record(report)


def main(modules: list[str] | None = None) -> int:
    modules = sys.argv[1:] if modules is None else modules
    if not modules:
        print("usage: python -m devtools.golden_update <test module>...", file=sys.stderr)
        return 2
    os.environ[UPDATE_ENV] = "1"
    collector = SkipCollector()
    status = int(pytest.main(["-rs", *modules], plugins=[collector]))
    if collector.skipped:
        print(
            f"\n{len(collector.skipped)} test(s) were skipped, so what they write was not "
            "regenerated on this machine:",
            file=sys.stderr,
        )
        for line in collector.skipped:
            print(f"- {line}", file=sys.stderr)
        return status or 1
    return status


if __name__ == "__main__":
    sys.exit(main())
