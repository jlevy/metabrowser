# pyright: reportPrivateUsage=false, reportUnusedFunction=false
"""TEMPORARY (mb-onzb review): report tests that leave process-global state changed.

Loaded from tests/conftest.py for one CI run and removed by the next commit. Before each
test is set up and after it is torn down, fixtures included, this takes a snapshot of
the process globals the review named and prints, at the end of the run, which tests
left each one different from how they found it.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from collections.abc import Generator
from typing import Any

import pytest

_LEFT_CHANGED: dict[str, list[tuple[str, str]]] = defaultdict(list)
_before: dict[str, Any] = {}


def _loggers() -> dict[str, tuple[int, tuple[str, ...], bool]]:
    found: dict[str, tuple[int, tuple[str, ...], bool]] = {}
    names = ["metabrowser", *sorted(logging.root.manager.loggerDict)]
    for name in names:
        if name != "metabrowser" and not name.startswith("metabrowser."):
            continue
        logger = logging.getLogger(name)
        # pytest attaches its own capture handlers for the length of each phase.
        handlers = tuple(
            type(handler).__name__
            for handler in logger.handlers
            if not type(handler).__module__.startswith("_pytest")
        )
        found[name] = (logger.level, handlers, logger.propagate)
    return found


def _snapshot() -> dict[str, Any]:
    from metabrowser import dotenv, events_route, home, paths_safe, server, tree
    from metabrowser.cache import probe
    from metabrowser.git import history, tree_source
    from metabrowser.logutil import parsing

    loggers = _loggers()
    return {
        "logger metabrowser": loggers.get("metabrowser"),
        "loggers metabrowser.*": {
            name: state
            for name, state in loggers.items()
            if name != "metabrowser" and (state[0] or state[1])
        },
        "server._EXTRA_ALLOWED_HOSTS": frozenset(server._EXTRA_ALLOWED_HOSTS),
        "server._PLUGIN_KIND_RULES": tuple(id(rule) for rule in server._PLUGIN_KIND_RULES),
        "cache.probe._RESULTS": len(probe._RESULTS),
        "dotenv._reported": len(dotenv._reported),
        "tree._IGNORE_CACHE": len(tree._IGNORE_CACHE),
        "tree._FOLDER_MARKERS": frozenset(tree._FOLDER_MARKERS),
        "git.tree_source._POOLS": frozenset(str(key) for key in tree_source._POOLS),
        "home._SUBJECTS": tuple(sorted(str(key) for key in home._SUBJECTS)),
        "git.history.HISTORY_SESSIONS": history.HISTORY_SESSIONS.session_count,
        "events_route._CATALOG_BODY_CACHE": len(events_route._CATALOG_BODY_CACHE),
        "events_route._CATALOG_ETAG_BY_CHECKPOINT": len(events_route._CATALOG_ETAG_BY_CHECKPOINT),
        "events_route._CATALOG_REVISION": (
            repr(events_route._CATALOG_REVISION.get("identity"))[:60],
            events_route._CATALOG_REVISION.get("value"),
        ),
        "logutil.parsing._PLUGIN_ADAPTERS": tuple(sorted(parsing._PLUGIN_ADAPTERS)),
        "paths_safe.ROOT_DIR": str(paths_safe.ROOT_DIR),
        "os.getcwd": os.getcwd(),
        "os.environ": tuple(
            sorted((k, v) for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST")
        ),
    }


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> Generator[None, None, None]:
    _before.clear()
    _before.update(_snapshot())
    yield


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_teardown(item: pytest.Item) -> Generator[None, None, None]:
    yield
    after = _snapshot()
    for name, value in after.items():
        if name in _before and _before[name] != value:
            _LEFT_CHANGED[name].append((item.nodeid, f"{_before[name]!r:.160} -> {value!r:.160}"))


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    terminalreporter.write_line("state probe: process-global state left changed, by global")
    names = sorted(_snapshot())
    for name in names:
        changed = _LEFT_CHANGED.get(name, [])
        modules = sorted({nodeid.split("::", 1)[0] for nodeid, _delta in changed})
        terminalreporter.write_line(
            f"state probe: {name}: {len(changed)} test(s) in {len(modules)} module(s)"
        )
        for module in modules[:40]:
            count = sum(1 for nodeid, _delta in changed if nodeid.startswith(module + "::"))
            terminalreporter.write_line(f"state probe:     {module}: {count}")
        for nodeid, delta in changed[:3]:
            terminalreporter.write_line(f"state probe:   e.g. {nodeid}: {delta}")
