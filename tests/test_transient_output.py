"""A passing test's ``tmp_path`` is emptied and a passing session's base directory removed,
the ``tmp_path`` of a test that failed or errored stays, no test is handed a path an
earlier one had, a killed session's directory is pruned like any other, and none of it
can hide a run's report (``tests/transient_output.py``).

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
from collections.abc import Generator
from pathlib import Path

import pytest

from tests import chrome_starts
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
# A lock no session wrote: too large for os.kill, which raises OverflowError for it.
TOO_LARGE_PID = "99999999999"
# What the large probe writes: a tree of the shape the suite's heaviest tests leave, in
# miniature, so its removal is seen without the cost of one.
LARGE_FILE_BYTES = 1 << 20
SMALL_FILES = 50


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
    # Named as a session is, but a link: its lock is the one it points at.
    (root / "pytest-7").symlink_to(not_a_session)
    too_large = _session(root, "pytest-8", TOO_LARGE_PID)

    assert sorted(release_dead_locks(root)) == [garbage, dead]

    for directory in (dead, garbage):
        assert not (directory / LOCK_NAME).exists()
    for directory in (live, being_written, unreadable, not_a_session, too_large):
        assert (directory / LOCK_NAME).exists(), directory
    assert not (unlocked / LOCK_NAME).exists()
    # Releasing removes nothing but the lock; the pruning is pytest's.
    for directory in (dead, garbage, live, being_written, unreadable, unlocked, not_a_session):
        assert (directory / "output.bin").exists(), directory


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    reason="a directory's mode stops its owner removing a file in it on POSIX, not root",
)
def test_a_lock_that_cannot_be_removed_is_left(tmp_path: Path) -> None:
    root = tmp_path / "pytest-of-someone"
    stuck = _session(root, "pytest-1", str(NO_SUCH_PID))
    stuck.chmod(0o500)
    try:
        assert release_dead_locks(root) == []
    finally:
        stuck.chmod(0o700)
    assert (stuck / LOCK_NAME).exists()


def test_a_root_that_is_not_a_directory_releases_nothing(tmp_path: Path) -> None:
    assert release_dead_locks(tmp_path / "pytest-of-nobody") == []
    (tmp_path / "pytest-of-a-file").write_text("", encoding="utf-8")
    assert release_dead_locks(tmp_path / "pytest-of-a-file") == []


# ── Nested sessions ────────────────────────────────────────────────────────────
# Collected only by the nested runs below, which name ``probe_*`` as their tests.


def _record(name: str, tmp_path: Path) -> None:
    with open(os.environ[RECORD_ENV], "a", encoding="utf-8") as out:
        out.write(f"{name}\t{tmp_path}\n")


def _evidence(name: str, tmp_path: Path) -> None:
    (tmp_path / "evidence.txt").write_text(f"what went wrong in {name}\n", encoding="utf-8")
    _record(name, tmp_path)


def probe_a_passing_test_with_a_large_tree(tmp_path: Path) -> None:
    (tmp_path / "large.bin").write_bytes(os.urandom(LARGE_FILE_BYTES))
    for index in range(SMALL_FILES):
        (tmp_path / "small" / str(index)).mkdir(parents=True)
        (tmp_path / "small" / str(index) / "file.txt").write_text("small\n", encoding="utf-8")
    _record("large", tmp_path)


@pytest.mark.parametrize("case", ["first", "second"])
def probe_a_parametrized_test_whose_cases_share_a_prefix(tmp_path: Path, case: str) -> None:
    """pytest names a test's directory by the first 30 characters of the test's name, the
    same for both cases here, and numbers it one past the highest of that name there is."""

    (tmp_path / "case.txt").write_text(case, encoding="utf-8")
    _record(case, tmp_path)


def probe_a_test_that_calls_gh() -> None:
    subprocess.run(["gh", "auth", "status"], capture_output=True, check=False, timeout=10)


def probe_a_test_that_runs_gh_with_undecodable_arguments() -> None:
    # The stand-in gh logs its arguments as given: here a byte that is not UTF-8.
    undecodable = os.fsdecode(b"\xff")
    subprocess.run(["gh", undecodable], capture_output=True, check=False, timeout=10)


def probe_a_test_that_garbles_the_chrome_starts_log(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    log = chrome_starts.log_path(tmp_path_factory.getbasetemp())
    with log.open("ab") as out:
        out.write(b'\xff{"test": "cut sh\n')


def probe_a_failing_test(tmp_path: Path) -> None:
    _evidence("call", tmp_path)
    raise AssertionError("this probe fails, so its tmp_path stays")


@pytest.fixture
def errs_in_setup(tmp_path: Path) -> None:
    _evidence("setup", tmp_path)
    raise RuntimeError("this fixture errs in setup, so the test's tmp_path stays")


@pytest.mark.usefixtures("errs_in_setup")
def probe_a_test_whose_setup_errors() -> None:
    raise AssertionError("not reached: the setup erred")


@pytest.fixture
def fails_in_teardown() -> Generator[None]:
    yield
    raise RuntimeError("this fixture fails in teardown, so the test's tmp_path stays")


@pytest.mark.usefixtures("fails_in_teardown")
def probe_a_test_whose_teardown_fails(tmp_path: Path) -> None:
    # The call passes, so pytest's "failed" policy would remove this directory in its own
    # teardown, before the fixture's teardown fails.
    _evidence("teardown", tmp_path)


def _nested(
    tmp_path: Path, temproot: Path, workers: list[str], probes: str
) -> tuple[subprocess.CompletedProcess[str], dict[str, Path]]:
    # pytest makes ``pytest-of-<user>`` in the root, not the root itself.
    temproot.mkdir(exist_ok=True)
    record = tmp_path / f"record-{len(list(tmp_path.glob('record-*')))}.tsv"
    record.touch()
    session = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "no:sugar"]
    # Observe the repository's retention policy, including setup and teardown errors.
    env = {**os.environ, "PYTEST_DEBUG_TEMPROOT": str(temproot), RECORD_ENV: str(record)}
    env.pop("PYTEST_ADDOPTS", None)
    completed = subprocess.run(
        [*session, "-o", "python_functions=probe_*", "-k", probes, *workers, str(THIS)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=NESTED_BOUND_S,
        check=False,
    )
    lines = record.read_text(encoding="utf-8").splitlines()
    return completed, {name: Path(path) for name, path in (line.split("\t") for line in lines)}


def _numbered_after(first: Path, second: Path) -> bool:
    """Whether *second* is the directory pytest numbers next after *first*, the first of
    its name: so not *first*'s path again, as it is when *first* was removed."""

    stem = first.name.removesuffix("0")
    return first.name == stem + "0" and (second.parent, second.name) == (first.parent, stem + "1")


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
    assert _numbered_after(recorded["first"], recorded["second"]), recorded
    assert not (root / "pytest-6").exists()
    assert not killed.exists()
    assert (running / LOCK_NAME).exists()
    assert newest.exists()


@WORKERS
def test_a_failing_session_keeps_only_what_failed_and_still_reports(
    tmp_path: Path, workers: list[str]
) -> None:
    """The ``tmp_path`` of a test that failed in its call, erred in its setup, or failed in
    its teardown stays, and the rest are emptied. A lock no session wrote and logs that are
    not UTF-8 leave the report whole: its failures, the gh call and the Chrome log."""

    temproot = tmp_path / "temproot"
    root = temproot / f"pytest-of-{getpass.getuser()}"
    too_large = _session(root, "pytest-0", TOO_LARGE_PID)

    completed, recorded = _nested(
        tmp_path,
        temproot,
        workers,
        "large_tree or parametrized or failing_test or setup_errors or teardown_fails"
        " or undecodable or garbles",
    )

    out = completed.stdout
    report = out + completed.stderr
    assert completed.returncode == 1, report
    assert "INTERNALERROR" not in report, report
    assert f"FAILED {THIS}::probe_a_failing_test" in out, report
    assert f"ERROR {THIS}::probe_a_test_whose_setup_errors" in out, report
    assert f"ERROR {THIS}::probe_a_test_whose_teardown_fails" in out, report
    assert "1 failed" in out.splitlines()[-1], report
    assert (
        "gh guard: 1 gh call(s) reached the failing stand-in, from 1 test(s): "
        f"{THIS}::probe_a_test_that_runs_gh_with_undecodable_arguments"
    ) in out, report
    assert "chrome starts: 0, 0 failed; 1 unreadable line(s)" in out, report
    assert (too_large / LOCK_NAME).read_text(encoding="ascii") == TOO_LARGE_PID
    # A passing test's directory is kept empty, so that no later test is handed its path.
    for passed in ("large", "first", "second"):
        assert list(recorded[passed].iterdir()) == [], passed
    assert _numbered_after(recorded["first"], recorded["second"]), recorded
    phases = ("call", "setup", "teardown")
    evidence = [recorded[phase] / "evidence.txt" for phase in phases]
    assert [path.read_text(encoding="utf-8") if path.exists() else None for path in evidence] == [
        f"what went wrong in {phase}\n" for phase in phases
    ]
