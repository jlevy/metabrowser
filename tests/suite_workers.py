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
"""

from __future__ import annotations

from collections.abc import Generator
from typing import cast

import pytest


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
