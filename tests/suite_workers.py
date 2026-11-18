"""What running beside other pytest-xdist workers needs from the suite.

A worker sends each test's report to the controlling process through execnet, which
carries only text that encodes as UTF-8. Python holds a file name that is not UTF-8 as a
lone surrogate (``os.fsdecode``), and the product logs such names: the Git diff adapter
logs the arguments of a command it reran, and ``tests/test_diff_one_run.py`` gives it a
name with the byte 0xE9. pytest keeps that log line in the report's captured sections, so
sending the report raised ``DumpError`` and stopped the whole run with an internal error.

Here every string of a report that is to be sent is made encodable, its lone surrogates
written as backslash escapes, as Python's own ``sys.stderr`` writes them. Nothing else in
a report changes, and a report that never leaves its process is not touched.

A test that runs out of time ends its worker, not the run: pytest-timeout's thread method
prints every stack and exits the process, and on a worker that output is the worker's
own, which nothing shows. A worker of CI run 44033895259 ended so, as "node down: Not
properly terminated", with no trace of its test. So ``StackDumps`` has faulthandler
write every thread's stack to the stderr the run started with, which reaches the log
from a worker too, ``DUMP_LEAD_S`` before the test's own budget, read as pytest-timeout
reads it: the test's ``timeout`` marker, then ``--timeout``, then ``PYTEST_TIMEOUT``, then
the suite's ``timeout``. A test that keeps to its budget prints nothing.
"""

from __future__ import annotations

import faulthandler
import os
import sys
from collections.abc import Generator
from typing import Final, cast

import pytest

# How long before a test's budget ends its stacks are written: time for faulthandler's
# own thread to write every stack before the timeout's thread exits the process.
DUMP_LEAD_S: Final = 5.0
# pytest-timeout's own variable for the budget, between ``--timeout`` and the ini file.
TIMEOUT_ENV: Final = "PYTEST_TIMEOUT"


def encodable(value: object) -> object:
    """*value* with every string in it, at any depth, encodable as UTF-8."""

    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return value.encode("utf-8", "backslashreplace").decode("utf-8")
        return value
    if isinstance(value, dict):
        items = cast("dict[object, object]", value).items()
        return {encodable(key): encodable(item) for key, item in items}
    if isinstance(value, list | tuple):
        items = [encodable(item) for item in cast("list[object] | tuple[object, ...]", value)]
        return items if isinstance(value, list) else tuple(items)
    return value


@pytest.hookimpl(wrapper=True)
def pytest_report_to_serializable() -> Generator[
    None, dict[str, object] | None, dict[str, object] | None
]:
    serialized = yield
    if serialized is None:
        return None
    return cast("dict[str, object]", encodable(serialized))


def budget_of(item: pytest.Item) -> float:
    """The seconds pytest-timeout gives *item*, found in the order it looks: the closest
    marker, then the command line, then ``PYTEST_TIMEOUT``, then the configuration."""

    marker = item.get_closest_marker("timeout")
    if marker is not None:
        given = marker.args[0] if marker.args else marker.kwargs.get("timeout")
        if given is not None:
            return float(given)
    for given in (
        item.config.getoption("timeout", None),
        os.environ.get(TIMEOUT_ENV) or None,
        item.config.getini("timeout"),
    ):
        if given is not None and given != "":
            return float(given)
    return 0.0


class StackDumps:
    """Every thread's stack, to the run's own stderr, shortly before a test's budget ends."""

    def __init__(self) -> None:
        self.stderr: int | None = None

    def pytest_configure(self, config: pytest.Config) -> None:
        # Capture is suspended while plugins are configured, so this is the real stderr.
        stream = sys.__stderr__
        assert stream is not None, "the interpreter has no stderr"
        self.stderr = os.dup(stream.fileno())

    def pytest_unconfigure(self, config: pytest.Config) -> None:
        if self.stderr is not None:
            os.close(self.stderr)
            self.stderr = None

    @pytest.hookimpl(wrapper=True, trylast=True)
    def pytest_runtest_protocol(self, item: pytest.Item) -> Generator[None, object, object]:
        budget = budget_of(item)
        if self.stderr is None or budget <= DUMP_LEAD_S:
            return (yield)
        faulthandler.dump_traceback_later(budget - DUMP_LEAD_S, file=self.stderr)
        try:
            return (yield)
        finally:
            faulthandler.cancel_dump_traceback_later()
