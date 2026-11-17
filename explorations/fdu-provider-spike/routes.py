"""Run selected route, lifecycle, and SSE tests with the fdu spike injected.

The injection replaces the runtime composition root's backend constructor for the
duration of one pytest session, so every `InventoryRuntime` the tests build gets an fdu
handle. Nothing in `src/` changes. A test that never builds a runtime (one that
constructs the Python provider or a coordinator directly) runs Python even under the
injection, so each result records how many fdu backends that test built; only a test
that built at least one says anything about fdu.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast

import pytest
from adapter import FduInventoryBackend
from probe import AdapterProbe

REPO_ROOT = Path(__file__).resolve().parents[2]

# The 2A spike's selection, then the Phase 1 preservation table's inventory route suites.
SELECTED_2A = (
    "tests/test_browser_inventory_api.py",
    "tests/test_browser_lifespan_e2e.py::test_full_lifespan_stack_serves_all_endpoints",
    "tests/test_browser_lifespan_e2e.py::test_recent_filter_includes_logs_state_files",
    "tests/test_e2e_filesystem_to_sse.py",
)
SELECTED_NEWER = (
    "tests/test_startup_nonblocking.py",
    "tests/test_browser_lifespan_e2e.py",
    "tests/test_browser_walk.py",
    "tests/test_tree_filter.py",
    "tests/test_api_folder_envelope.py",
    "tests/test_rollup_route.py",
    "tests/test_browser_rollup.py",
    "tests/test_browser_recent.py",
    "tests/test_catalog_feed_server.py",
    "tests/test_browser_events_route.py",
    "tests/test_browser_active_tracker.py",
    "tests/test_browser_watch_backends.py",
    "tests/test_inventory_coordinator.py",
)


class _InjectFdu:
    def __init__(self, probe: AdapterProbe, *, inject: bool) -> None:
        self.probe = probe
        self.inject = inject
        self.results: list[dict[str, object]] = []
        self.backends_built = 0
        self.per_test: dict[str, int] = {}
        self.phase_failures: list[dict[str, object]] = []

    def pytest_configure(self) -> None:
        if not self.inject:
            return
        runtime = importlib.import_module("metabrowser.inventory_engine.runtime")

        def build(_provider: object) -> FduInventoryBackend:
            self.backends_built += 1
            return FduInventoryBackend(probe=self.probe)

        setattr(runtime, "create_inventory_backend", build)  # noqa: B010

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item: Any, nextitem: Any) -> Generator[None]:
        del nextitem
        before = self.backends_built
        yield
        self.per_test[item.nodeid] = self.backends_built - before

    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.when != "call" and report.outcome == "failed":
            self.phase_failures.append(
                {"test": report.nodeid, "phase": report.when, "detail": str(report.longrepr)[-900:]}
            )
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            self.results.append(
                {
                    "test": report.nodeid,
                    "phase": report.when,
                    "outcome": report.outcome,
                    "detail": str(report.longrepr)[-1500:] if report.failed else "",
                }
            )


def run_selection(
    selection: tuple[str, ...], probe: AdapterProbe, *, inject: bool
) -> dict[str, object]:
    plugin = _InjectFdu(probe, inject=inject)
    exit_code = pytest.main(["-q", "--tb=short", "-p", "no:cacheprovider", *selection], plugins=[plugin])
    for row in plugin.results:
        row["fdu_backends_built"] = plugin.per_test.get(cast("str", row["test"]), 0)
    return {
        "injected": inject,
        "exit_code": int(exit_code),
        "selected": list(selection),
        "fdu_backends_built": plugin.backends_built,
        "setup_or_teardown_failures": plugin.phase_failures,
        "results": plugin.results,
    }


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "2a"
    selection = SELECTED_2A if which == "2a" else SELECTED_NEWER
    outcome = run_selection(selection, AdapterProbe(), inject=sys.argv[2:3] != ["python"])
    results = cast("list[dict[str, object]]", outcome["results"])
    for row in results:
        print(row["outcome"], row["fdu_backends_built"], row["test"])
    print("backends", outcome["fdu_backends_built"], "exit", outcome["exit_code"])
