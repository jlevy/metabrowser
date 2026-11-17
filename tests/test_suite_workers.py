"""``tests/suite_workers.py``: a test near its budget leaves every stack in the run's log,
from a pytest-xdist worker too."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.suite_workers import DUMP_LEAD_S, TIMEOUT_ENV
from tests.test_suite_gates import MAX_INNER_BOUND_S

ROOT = Path(__file__).resolve().parents[1]
THIS = Path(__file__).relative_to(ROOT)
# A run's budget two seconds past the lead, so its dump comes two seconds into a test.
RUN_BUDGET_S = DUMP_LEAD_S + 2


# Collected only by the nested runs below, which name ``probe_*`` as their tests.


@pytest.mark.timeout(DUMP_LEAD_S + 1)
def probe_a_test_that_nears_its_budget() -> None:
    time.sleep(2.5)


def probe_a_test_that_nears_a_run_budget() -> None:
    """Within the suite's budget, and near one a run gives with ``--timeout``."""

    time.sleep(2.5)


def probe_a_test_well_within_its_budget() -> None:
    pass


def _run(tmp_path: Path, *arguments: str, environ: dict[str, str] | None = None) -> str:
    session = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "no:sugar"]
    completed = subprocess.run(
        [*session, "-o", "python_functions=probe_*", f"--basetemp={tmp_path}", *arguments, THIS],
        cwd=ROOT,
        env={**os.environ, **(environ or {})},
        capture_output=True,
        text=True,
        timeout=MAX_INNER_BOUND_S,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed.stdout + completed.stderr


@pytest.mark.parametrize("workers", [[], ["-n", "1"]], ids=["one process", "a worker"])
def test_a_test_near_its_budget_leaves_every_stack_in_the_log(
    tmp_path: Path, workers: list[str]
) -> None:
    log = _run(tmp_path, *workers)

    # One second into a six-second budget, the five before it ends; the suite's own
    # budget leaves the other two tests alone.
    assert log.count("Timeout (0:00:01)!") == 1, log
    assert "Timeout (0:00:02)!" not in log, log
    assert "in probe_a_test_that_nears_its_budget" in log
    assert "probe_a_test_well_within_its_budget" not in log.split("Timeout", 1)[1]


@pytest.mark.parametrize(
    ("arguments", "environ"),
    [([f"--timeout={RUN_BUDGET_S:g}"], {}), ([], {TIMEOUT_ENV: f"{RUN_BUDGET_S:g}"})],
    ids=["--timeout", TIMEOUT_ENV],
)
def test_a_budget_the_run_gives_is_read_as_pytest_timeout_reads_it(
    tmp_path: Path, arguments: list[str], environ: dict[str, str]
) -> None:
    log = _run(tmp_path, "-k", "run_budget", *arguments, environ=environ)

    assert log.count(f"Timeout (0:00:{RUN_BUDGET_S - DUMP_LEAD_S:02g})!") == 1, log
    assert "in probe_a_test_that_nears_a_run_budget" in log
