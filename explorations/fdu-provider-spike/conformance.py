"""Run every provider-parametrized conformance case against Python and the fdu spike."""

from __future__ import annotations

import importlib
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from adapter import FduInventoryBackend
from probe import AdapterProbe

from metabrowser.inventory_engine.providers.python_inventory import PythonInventoryBackend

REPO_ROOT = Path(__file__).resolve().parents[2]


def provider_cases() -> tuple[Any, list[str]]:
    """The conformance module and every case parametrized over `provider_factory`."""

    tests_path = str(REPO_ROOT / "tests")
    if tests_path not in sys.path:
        sys.path.insert(0, tests_path)
    suite = importlib.import_module("test_inventory_provider_contract")
    names: list[str] = []
    for name in dir(suite):
        if not name.startswith("test_"):
            continue
        function = getattr(suite, name)
        marks = getattr(function, "pytestmark", ())
        if any(
            mark.name == "parametrize" and mark.args and mark.args[0] == "provider_factory"
            for mark in marks
        ):
            names.append(name)
    return suite, sorted(names)


def run_case(suite: Any, name: str, factory: Callable[[], Any]) -> dict[str, object]:
    started = time.monotonic_ns()
    with tempfile.TemporaryDirectory(prefix="fdu-spike-contract-") as raw_root:
        try:
            getattr(suite, name)(factory, Path(raw_root))
        except pytest.skip.Exception as error:
            outcome, detail = "skipped", str(error)
        except BaseException as error:
            outcome = "failed"
            detail = "".join(
                traceback.format_exception(type(error), error, error.__traceback__, limit=6)
            )
        else:
            outcome, detail = "passed", ""
    return {
        "outcome": outcome,
        "detail": detail,
        "wall_time_ms": round((time.monotonic_ns() - started) / 1e6, 1),
    }


def run_conformance(probe: AdapterProbe, only: str | None = None) -> list[dict[str, object]]:
    suite, names = provider_cases()
    registered = set(suite.PROVIDER_CONFORMANCE_TESTS)
    rows: list[dict[str, object]] = []
    for name in names:
        if only and only not in name:
            continue
        python = run_case(suite, name, PythonInventoryBackend)
        fdu_result = run_case(suite, name, lambda: FduInventoryBackend(probe=probe))
        rows.append(
            {
                "test": name,
                "registered": name in registered,
                "python": python,
                "fdu": fdu_result,
            }
        )
    return rows


def main() -> int:
    probe = AdapterProbe()
    only = sys.argv[1] if len(sys.argv) > 1 else None
    rows = run_conformance(probe, only)
    failures = 0
    for row in rows:
        python = cast("dict[str, object]", row["python"])
        fdu_row = cast("dict[str, object]", row["fdu"])
        print(f"{python['outcome']!s:8} {fdu_row['outcome']!s:8} {row['test']}")
        if fdu_row["outcome"] == "failed":
            failures += 1
            print("    " + str(fdu_row["detail"]).replace("\n", "\n    ")[-900:])
    print(sorted(cast("dict[str, object]", probe.snapshot()["fallbacks"])))
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
