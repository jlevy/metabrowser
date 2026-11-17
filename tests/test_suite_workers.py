"""``tests/suite_workers.py``: a test near its budget leaves every stack in the run's log,
from a pytest-xdist worker too."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.suite_workers import DUMP_LEAD_S
from tests.test_suite_gates import MAX_INNER_BOUND_S

ROOT = Path(__file__).resolve().parents[1]
THIS = Path(__file__).relative_to(ROOT)


# Collected only by the nested runs below, which name ``probe_*`` as their tests.


@pytest.mark.timeout(DUMP_LEAD_S + 1)
def probe_a_test_that_nears_its_budget() -> None:
    time.sleep(2.5)


def probe_a_test_well_within_its_budget() -> None:
    pass


@pytest.mark.parametrize("workers", [[], ["-n", "1"]], ids=["one process", "a worker"])
def test_a_test_near_its_budget_leaves_every_stack_in_the_log(
    tmp_path: Path, workers: list[str]
) -> None:
    session = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "no:sugar"]
    completed = subprocess.run(
        [*session, "-o", "python_functions=probe_*", f"--basetemp={tmp_path}", *workers, THIS],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=MAX_INNER_BOUND_S,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    log = completed.stdout + completed.stderr
    # One second into a six-second budget, the five before it ends.
    assert log.count("Timeout (0:00:01)!") == 1, log
    assert "in probe_a_test_that_nears_its_budget" in log
    assert "probe_a_test_well_within_its_budget" not in log.split("Timeout", 1)[1]
