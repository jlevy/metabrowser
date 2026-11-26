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


@pytest.mark.timeout(0)
def probe_a_first_test_that_warms_the_process() -> None:
    """Runs first in each nested run, with no budget, so the probes timed after it are warm.

    pytest-timeout and ``StackDumps`` time a test from the start of its setup to the end
    of its teardown, and the first test of a process pays the deferred imports of the
    suite's autouse fixtures in both (``tests/conftest.py``). On 2026-11-18 at load
    average 270, five nested runs gave their first test 0.7 to 3.5 s of setup and 1.9 to
    5.5 s of teardown, and each test after it 0.03 s or less of each. A timed probe that
    ran first had its dump fire in setup, where its stack does not name it, or its
    budget end in teardown, which ended the process. With no budget this one is neither
    dumped nor ended; the nested run's own ``MAX_INNER_BOUND_S`` bounds it.
    """


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
    # Each case supplies its own budget or exercises the repository default.
    env = os.environ.copy()
    env.pop("PYTEST_ADDOPTS", None)
    env.pop(TIMEOUT_ENV, None)
    env.update(environ or {})
    completed = subprocess.run(
        [*session, "-o", "python_functions=probe_*", f"--basetemp={tmp_path}", *arguments, THIS],
        cwd=ROOT,
        env=env,
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
    # budget leaves the two tests after it alone, and the first has none.
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
    log = _run(tmp_path, "-k", "warms_the_process or run_budget", *arguments, environ=environ)

    assert log.count(f"Timeout (0:00:{RUN_BUDGET_S - DUMP_LEAD_S:02g})!") == 1, log
    assert "in probe_a_test_that_nears_a_run_budget" in log
