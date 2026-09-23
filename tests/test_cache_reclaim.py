"""The startup sweep of abandoned staging entries.

Each production operation reports its transitions and the locks it holds at each one.
:class:`MachineReplay` walks those reports through the machine frozen in
``tests/fixtures/repository-cache/state-machines.json``: every event must be the one
transition the machine allows from the current state, and the lock kinds held must be
exactly the ones that transition declares. The fixture's scenario is then realized
against a real temporary home, with another holder in a real child process.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import subprocess
import sys
import textwrap
from collections.abc import Generator
from pathlib import Path
from typing import Any, cast

import pytest

from metabrowser.cache import reclaim as reclaim_module
from metabrowser.cache.layout import open_cache
from metabrowser.cache.locks import (
    held_locks,
    staging_entry_lock,
)
from metabrowser.cache.reclaim import MachineEvent, sweep_staging
from metabrowser.home import ensure_home, ensure_private_directory

pytestmark = pytest.mark.skipif(os.name != "posix", reason="cache locks are BSD flock locks")
fcntl = pytest.importorskip("fcntl")

FIXTURES = Path(__file__).parent / "fixtures" / "repository-cache"
CHILD_TIMEOUT = 60.0


def _document() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURES / "state-machines.json").read_text()))


class MachineReplay:
    """Check observed transitions against one frozen machine."""

    def __init__(self, name: str) -> None:
        document = _document()
        self.machine = next(m for m in document["machines"] if m["name"] == name)
        self.states = {state["name"]: state for state in self.machine["states"]}
        self.state: str = self.machine["initial"]
        self.events: list[str] = []

    def __call__(self, observed: MachineEvent) -> None:
        assert observed.machine == self.machine["name"]
        candidates = [
            transition
            for transition in self.machine["transitions"]
            if transition["from"] == self.state and transition["event"] == observed.event
        ]
        assert len(candidates) == 1, (self.state, observed.event)
        assert observed.holds == frozenset(candidates[0]["holds"]), (
            observed.event,
            sorted(observed.holds),
        )
        self.state = candidates[0]["to"]
        self.events.append(observed.event)

    @property
    def visible(self) -> bool:
        return cast(bool, self.states[self.state]["visible"])


def _scenario(scenario_id: str) -> dict[str, Any]:
    return next(s for s in _document()["scenarios"] if s["id"] == scenario_id)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    ensure_home(home)
    return home


@pytest.fixture(autouse=True)
def no_leaked_locks() -> Generator[None]:
    yield
    assert held_locks() == ()


class _Child:
    """A child interpreter that runs *setup*, reports, and waits to be released or killed."""

    def __init__(self, home: Path, setup: str) -> None:
        script = (
            textwrap.dedent(
                """
            import sys
            from pathlib import Path
            from metabrowser.cache import locks
            home = Path(sys.argv[1])
            """
            )
            + textwrap.dedent(setup)
            + textwrap.dedent(
                """
            print("ready", flush=True)
            sys.stdin.readline()
            """
            )
        )
        self.process = subprocess.Popen(
            [sys.executable, "-c", script, str(home)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert self.process.stdout is not None
        line = self.process.stdout.readline().strip()
        if line != "ready":
            _, errors = self.process.communicate(timeout=CHILD_TIMEOUT)
            pytest.fail(f"child did not start: {line!r} {errors}")

    def finish(self) -> None:
        if self.process.poll() is None:
            self.process.communicate("\n", timeout=CHILD_TIMEOUT)


# ── Startup sweep ──────────────────────────────────────────────────


def test_the_sweep_skips_a_live_staging_entry_and_removes_a_dead_one(home: Path) -> None:
    scenario = _scenario("sweep-skips-live-staging")
    ensure_private_directory(home, "cache/staging/a-live/objects")
    ensure_private_directory(home, "cache/staging/b-dead/objects/pack")
    dead_file = home / "cache/staging/b-dead/objects/pack/tmp_pack_1"
    dead_file.write_bytes(b"partial")
    dead_file.chmod(0o400)
    owner = _Child(home, 'lock = locks.staging_entry_lock(home, "a-live")')
    replay = MachineReplay("startup_sweep")
    try:
        report = sweep_staging(home, observer=replay)
    finally:
        owner.finish()

    assert replay.events == scenario["events"]
    assert replay.state == scenario["expected_final"]
    assert replay.visible is scenario["expected_visible"]
    assert report.removed == ("cache/staging/b-dead",)
    assert report.live == ("cache/staging/a-live",)
    assert (home / "cache/staging/a-live").is_dir()
    assert not (home / "cache/staging/b-dead").exists()
    assert not (home / "cache/locks/staging/b-dead.lock").exists()


def test_the_sweep_removes_free_orphan_lock_files_and_reports_unknown_names(home: Path) -> None:
    ensure_private_directory(home, "cache/staging/Not An Entry")
    staging_entry_lock(home, "orphan").release()
    owner = _Child(home, 'lock = locks.staging_entry_lock(home, "claimed-before-mkdir")')
    try:
        report = sweep_staging(home)
    finally:
        owner.finish()

    assert report.unrecognized == ("cache/staging/Not An Entry",)
    assert report.removed_lock_files == ("cache/locks/staging/orphan.lock",)
    assert (home / "cache/staging/Not An Entry").is_dir()
    assert (home / "cache/locks/staging/claimed-before-mkdir.lock").exists()


def test_an_entry_with_an_unusable_lock_file_is_kept_and_the_sweep_continues(home: Path) -> None:
    ensure_private_directory(home, "cache/staging/a-shared/objects")
    ensure_private_directory(home, "cache/staging/b-dead/objects")
    staging_entry_lock(home, "a-shared").release()
    shared = home / "cache/locks/staging/a-shared.lock"
    shared.chmod(0o644)
    # Stands in for another principal holding the lock file it opened while shared.
    foreign = os.open(shared, os.O_RDONLY)
    try:
        fcntl.flock(foreign, fcntl.LOCK_EX)
        report = sweep_staging(home)
    finally:
        os.close(foreign)

    assert report.failed == ("cache/staging/a-shared",)
    assert report.removed == ("cache/staging/b-dead",)
    assert (home / "cache/staging/a-shared/objects").is_dir()


@pytest.fixture
def searchable_again(home: Path) -> Generator[None]:
    """Restore owner access below the home, so the temporary directory can be deleted."""

    yield
    for path, directories, _files in os.walk(home, topdown=False):
        for name in directories:
            with contextlib.suppress(OSError):
                os.chmod(os.path.join(path, name), 0o700)


@pytest.mark.usefixtures("searchable_again")
def test_the_sweep_deletes_an_entry_holding_a_directory_its_owner_cannot_search(
    home: Path,
) -> None:
    """A crashed clone can leave one; failing here would fail every later open_cache."""

    ensure_private_directory(home, "cache/staging/dead-1/repository.git/objects/ab")
    (home / "cache/staging/dead-1/repository.git/objects/ab/loose").write_bytes(b"x")
    (home / "cache/staging/dead-1/repository.git/objects/ab").chmod(0o000)

    report = sweep_staging(home)

    assert report.removed == ("cache/staging/dead-1",)
    assert report.failed == ()
    assert not (home / "cache/staging/dead-1").exists()


@pytest.mark.usefixtures("searchable_again")
def test_an_entry_that_stays_behind_is_reported_and_left_for_the_next_sweep(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_remove_tree`` promises ``False`` on failure, so nothing may escape it."""

    ensure_private_directory(home, "cache/staging/dead-1/objects/ab")
    (home / "cache/staging/dead-1/objects/ab/loose").write_bytes(b"x")
    (home / "cache/staging/dead-1/objects/ab").chmod(0o000)
    monkeypatch.setattr(reclaim_module, "_grant_owner_access", lambda _directory: False)

    report = sweep_staging(home)

    assert report.removed == ()
    assert report.failed == ("cache/staging/dead-1",)
    assert (home / "cache/staging/dead-1/objects/ab").is_dir()


@pytest.mark.usefixtures("searchable_again")
def test_opening_the_cache_survives_an_entry_it_cannot_search(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ensure_home(home)
    ensure_private_directory(home, "cache/staging/acquire-0123456789abcdef/objects/ab")
    (home / "cache/staging/acquire-0123456789abcdef/objects/ab").chmod(0o000)

    opened = open_cache(home, version="0.11.0")

    assert opened.sweep.removed == ("cache/staging/acquire-0123456789abcdef",)
    assert list((home / "cache/staging").iterdir()) == []


def test_an_entry_that_cannot_be_inspected_is_reported_rather_than_raised(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_private_directory(home, "cache/staging/dead-1")
    real_lstat = os.lstat

    def refusing_lstat(path: Any, **kwargs: Any) -> os.stat_result:
        if str(path).endswith("cache/staging/dead-1"):
            raise OSError(errno.EIO, "input/output error")
        return real_lstat(path, **kwargs)

    monkeypatch.setattr(reclaim_module.os, "lstat", refusing_lstat)

    report = sweep_staging(home)

    assert report.failed == ("cache/staging/dead-1",)
    assert report.removed == ()
