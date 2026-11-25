"""A passing test's ``tmp_path`` is emptied and a passing session's base directory removed,
a failing test's stays, no test is handed a path an earlier one had, and a killed
session's directory is pruned like any other (``tests/transient_output.py``).

Nested pytest sessions of this module's ``probe_*`` functions run under a temporary root
of their own (``PYTEST_DEBUG_TEMPROOT``), so that what they leave, and what they prune, is
this test's alone: in one process, and under pytest-xdist, which runs every module of the
parallel tier.
"""

from __future__ import annotations

import getpass
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.transient_output import LOCK_NAME, release_dead_locks

ROOT = Path(__file__).resolve().parents[1]
THIS = Path(__file__).relative_to(ROOT)
RECORD_ENV = "METABROWSER_TEST_TRANSIENT_RECORD"
# One nested session: pytest's start, the suite's conftest, and the first probe's deferred
# imports in its setup and teardown. On CI the whole module took 6 to 7 s. On a 10-core
# Mac at a load average of 330 on 2026-11-24 a passing session took 22.7 s alone; in
# one run of this module two were cut off at the suite's 50 s inner bound, and in the
# next the four took 15 to 30 s.
NESTED_BOUND_S = 150
pytestmark = pytest.mark.timeout(NESTED_BOUND_S + 30)
# A process id no process can hold: above Linux's PID_MAX_LIMIT (2**22) and macOS's
# highest, 99998. A session that was killed holds one that is no longer running.
NO_SUCH_PID = 2**22 + 1
# What the large probe writes: a tree of the shape the suite's heaviest tests leave, in
# miniature, so its removal is seen without the cost of one.
LARGE_FILE_BYTES = 1 << 20
SMALL_FILES = 50


def test_the_suite_keeps_only_a_failing_tests_tmp_path(pytestconfig: pytest.Config) -> None:
    assert pytestconfig.getini("tmp_path_retention_policy") == "failed"


# ── release_dead_locks ─────────────────────────────────────────────────────────


def _session(root: Path, name: str, owner: str | None) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "output.bin").write_bytes(b"x")
    if owner is not None:
        (directory / LOCK_NAME).write_text(owner, encoding="ascii")
    return directory


@pytest.mark.skipif(os.name != "posix", reason="a process is looked for with signal 0")
def test_only_a_lock_whose_process_has_gone_is_released(tmp_path: Path) -> None:
    root = tmp_path / "pytest-of-someone"
    dead = _session(root, "pytest-1", str(NO_SUCH_PID))
    garbage = _session(root, "garbage-3f2c", str(NO_SUCH_PID))
    live = _session(root, "pytest-2", str(os.getpid()))
    being_written = _session(root, "pytest-3", "")
    unreadable = _session(root, "pytest-4", "not a process")
    unlocked = _session(root, "pytest-5", None)
    not_a_session = _session(root, "elsewhere-6", str(NO_SUCH_PID))
    (root / "pytest-current").symlink_to(dead)

    assert sorted(release_dead_locks(root)) == [garbage, dead]

    for directory in (dead, garbage):
        assert not (directory / LOCK_NAME).exists()
    for directory in (live, being_written, unreadable, not_a_session):
        assert (directory / LOCK_NAME).exists(), directory
    assert not (unlocked / LOCK_NAME).exists()
    # Releasing removes nothing but the lock; the pruning is pytest's.
    for directory in (dead, garbage, live, being_written, unreadable, unlocked, not_a_session):
        assert (directory / "output.bin").exists(), directory


def test_a_root_that_is_not_there_releases_nothing(tmp_path: Path) -> None:
    assert release_dead_locks(tmp_path / "pytest-of-nobody") == []


# ── Nested sessions ────────────────────────────────────────────────────────────
# Collected only by the nested runs below, which name ``probe_*`` as their tests.


def _record(name: str, tmp_path: Path) -> None:
    with open(os.environ[RECORD_ENV], "a", encoding="utf-8") as out:
        out.write(f"{name}\t{tmp_path}\n")


def probe_a_passing_test_with_a_large_tree(tmp_path: Path) -> None:
    (tmp_path / "large.bin").write_bytes(os.urandom(LARGE_FILE_BYTES))
    for index in range(SMALL_FILES):
        (tmp_path / "small" / str(index)).mkdir(parents=True)
        (tmp_path / "small" / str(index) / "file.txt").write_text("small\n", encoding="utf-8")
    _record("large", tmp_path)


@pytest.mark.parametrize("case", ["first", "second"])
def probe_a_parametrized_test(tmp_path: Path, case: str) -> None:
    """Its cases' names start the same, as pytest names their directories."""

    (tmp_path / "case.txt").write_text(case, encoding="utf-8")
    _record(case, tmp_path)


def probe_a_test_that_calls_gh() -> None:
    subprocess.run(["gh", "auth", "status"], capture_output=True, check=False, timeout=10)


def probe_a_failing_test(tmp_path: Path) -> None:
    (tmp_path / "evidence.txt").write_text("what went wrong\n", encoding="utf-8")
    _record("failing", tmp_path)
    raise AssertionError("this probe fails, so its tmp_path stays")


def _nested(
    tmp_path: Path, temproot: Path, workers: list[str], probes: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, Path]]:
    # pytest makes ``pytest-of-<user>`` in the root, not the root itself.
    temproot.mkdir(exist_ok=True)
    record = tmp_path / f"record-{len(list(tmp_path.glob('record-*')))}.tsv"
    record.touch()
    session = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "no:sugar"]
    completed = subprocess.run(
        [*session, "-o", "python_functions=probe_*", "-k", probes, *workers, str(THIS)],
        cwd=ROOT,
        env={**os.environ, "PYTEST_DEBUG_TEMPROOT": str(temproot), RECORD_ENV: str(record)},
        capture_output=True,
        text=True,
        timeout=NESTED_BOUND_S,
        check=False,
    )
    lines = record.read_text(encoding="utf-8").splitlines()
    return completed, {name: Path(path) for name, path in (line.split("\t") for line in lines)}


WORKERS = pytest.mark.parametrize(
    "workers", [["-p", "no:xdist"], ["-n", "1"]], ids=["one process", "a worker"]
)


@WORKERS
def test_a_passing_session_leaves_nothing_and_prunes_a_killed_one(
    tmp_path: Path, workers: list[str]
) -> None:
    """Its base directory goes, a killed session's older one is pruned, and its summary,
    written after the removal, still names the gh call a test made."""

    temproot = tmp_path / "temproot"
    root = temproot / f"pytest-of-{getpass.getuser()}"
    killed = _session(root, "pytest-0", str(NO_SUCH_PID))
    # This process is running, so its session is not pruned.
    running = _session(root, "pytest-1", str(os.getpid()))
    # Among the newest kept: the nested session's own is pytest-6.
    newest = _session(root, "pytest-5", None)

    completed, recorded = _nested(
        tmp_path, temproot, workers, "large_tree or calls_gh or parametrized"
    )

    report = completed.stdout + completed.stderr
    assert completed.returncode == 0, report
    assert "gh guard: 1 gh call(s) reached the failing stand-in" in completed.stdout, report
    assert not recorded["large"].exists()
    assert recorded["first"] != recorded["second"]
    assert not (root / "pytest-6").exists()
    assert not killed.exists()
    assert (running / LOCK_NAME).exists()
    assert newest.exists()


@WORKERS
def test_a_failing_session_keeps_only_the_failing_tests_tmp_path(
    tmp_path: Path, workers: list[str]
) -> None:
    temproot = tmp_path / "temproot"
    completed, recorded = _nested(
        tmp_path, temproot, workers, "large_tree or failing_test or parametrized"
    )

    assert completed.returncode == 1, completed.stdout + completed.stderr
    # A passing test's directory is kept empty, so that no later test is handed its path
    # (pytest_runtest_teardown in tests/conftest.py).
    for passed in ("large", "first", "second"):
        assert list(recorded[passed].iterdir()) == [], passed
    assert recorded["first"] != recorded["second"]
    assert (recorded["failing"] / "evidence.txt").read_text(encoding="utf-8") == (
        "what went wrong\n"
    )
