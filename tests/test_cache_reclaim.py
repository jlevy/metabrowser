"""Reclamation of staging, trash, quarantine, and unreferenced stores.

Each production operation reports its transitions and the locks it holds at each one.
:class:`MachineReplay` walks those reports through the machine frozen in
``tests/fixtures/repository-cache/state-machines.json``: every event must be the one
transition the machine allows from the current state, and the lock kinds held must be
exactly the ones that transition declares. The fixture's scenarios are then realized
against real temporary homes, with other holders and crashes in real child processes.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import signal
import subprocess
import sys
import textwrap
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any, cast

import pytest

from metabrowser.cache import reclaim as reclaim_module
from metabrowser.cache.atomic import publish_entry, write_record_atomic
from metabrowser.cache.layout import open_cache
from metabrowser.cache.locks import (
    held_locks,
    staging_entry_lock,
)
from metabrowser.cache.paths import source_record
from metabrowser.cache.reclaim import (
    MachineEvent,
    StoreReclamation,
    purge_quarantined,
    quarantine_entries,
    reclaim_staging,
    reclaim_store,
    reclaim_trash,
    store_is_referenced,
    sweep_staging_and_trash,
)
from metabrowser.cache.records import (
    REPOSITORY_STORE_ALIAS_CONTRACT_ID,
    RepositoryStoreAlias,
)
from metabrowser.home import ensure_home, ensure_private_directory, write_private_file_atomic

pytestmark = pytest.mark.skipif(os.name != "posix", reason="cache locks are BSD flock locks")
fcntl = pytest.importorskip("fcntl")

FIXTURES = Path(__file__).parent / "fixtures" / "repository-cache"
SLUG = "github-com--pallets--flask--e7b7fe0ffe8a"
SOURCE_ID = "sha256:e7b7fe0ffe8a446772b8a863f51222c90d256e511e1a4da3daec599735962fa9"
STORE_KEY = "4c2d8559cb0179baca3afa2f633e1cfd7271b82e4fb7f0c451dfa9354aa70aff"
CHILD_TIMEOUT = 60.0


def _document() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((FIXTURES / "state-machines.json").read_text()))


class MachineReplay:
    """Check observed transitions against one frozen machine."""

    def __init__(self, name: str, *, lock_aliases: dict[str, str] | None = None) -> None:
        document = _document()
        self.machine = next(m for m in document["machines"] if m["name"] == name)
        self.recoveries: dict[str, Any] = document["crash_recovery"]
        self.states = {state["name"]: state for state in self.machine["states"]}
        self.state: str = self.machine["initial"]
        self.events: list[str] = []
        self._aliases = lock_aliases or {}
        self._visible: bool | None = None

    def __call__(self, observed: MachineEvent) -> None:
        assert observed.machine == self.machine["name"]
        candidates = [
            transition
            for transition in self.machine["transitions"]
            if transition["from"] == self.state and transition["event"] == observed.event
        ]
        assert len(candidates) == 1, (self.state, observed.event)
        holds = frozenset(self._aliases.get(kind, kind) for kind in observed.holds)
        assert holds == frozenset(candidates[0]["holds"]), (observed.event, sorted(holds))
        self.state = candidates[0]["to"]
        self.events.append(observed.event)

    def advance(self, events: list[str]) -> None:
        """Apply events a killed child performed, whose held locks this process cannot see."""

        for event in events:
            (transition,) = [
                t
                for t in self.machine["transitions"]
                if t["from"] == self.state and t["event"] == event
            ]
            self.state = transition["to"]
            self.events.append(event)

    def crash(self) -> str:
        """Apply the frozen crash recovery of the current state and return it."""

        recovery = cast(str, self.states[self.state]["on_crash"])
        after = self.recoveries[recovery]["visible_after"]
        self._visible = self.visible if after == "unchanged" else cast(bool, after)
        self.state = recovery
        return recovery

    @property
    def visible(self) -> bool:
        if self.state in self.recoveries:
            assert self._visible is not None
            return self._visible
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


def _run_until_killed(home: Path, body: str) -> subprocess.CompletedProcess[str]:
    script = textwrap.dedent(
        """
        import os, signal, sys
        from pathlib import Path
        from metabrowser.cache import reclaim
        home = Path(sys.argv[1])

        def die(*_args, **_kwargs):
            os.kill(os.getpid(), signal.SIGKILL)
        """
    ) + textwrap.dedent(body)
    return subprocess.run(
        [sys.executable, "-c", script, str(home)],
        capture_output=True,
        text=True,
        timeout=CHILD_TIMEOUT,
        check=False,
    )


def _make_store(home: Path) -> None:
    ensure_private_directory(home, f"cache/repository-stores/{STORE_KEY}/repository.git/objects")
    (home / f"cache/repository-stores/{STORE_KEY}/repository.git/objects/pack").write_bytes(b"x")


def _make_source_with_alias(home: Path) -> None:
    ensure_private_directory(home, f"cache/sources/{SLUG}")
    write_record_atomic(
        home,
        source_record(SLUG, "store-alias.yml"),
        RepositoryStoreAlias(
            source_id=SOURCE_ID,
            store_id=f"sha256:{STORE_KEY}",
            generation=1,
            updated_at="2026-09-17T12:00:00Z",
        ),
        REPOSITORY_STORE_ALIAS_CONTRACT_ID,
    )


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
        report = reclaim_staging(home, observer=replay)
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


def test_the_trash_sweep_follows_the_same_machine_with_trash_locks(home: Path) -> None:
    ensure_private_directory(home, "cache/trash/a-live/sources")
    ensure_private_directory(home, "cache/trash/b-dead/repository-stores")
    owner = _Child(home, 'lock = locks.trash_entry_lock(home, "a-live")')
    replay = MachineReplay("startup_sweep", lock_aliases={"trash_entry": "staging_entry"})
    try:
        report = reclaim_trash(home, observer=replay)
    finally:
        owner.finish()

    assert replay.events == _scenario("sweep-skips-live-staging")["events"]
    assert replay.state == "done"
    assert report.removed == ("cache/trash/b-dead",)
    assert report.live == ("cache/trash/a-live",)


def test_the_sweep_removes_free_orphan_lock_files_and_reports_unknown_names(home: Path) -> None:
    ensure_private_directory(home, "cache/staging/Not An Entry")
    staging_entry_lock(home, "orphan").release()
    owner = _Child(home, 'lock = locks.staging_entry_lock(home, "claimed-before-mkdir")')
    try:
        report = reclaim_staging(home)
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
        report = reclaim_staging(home)
    finally:
        os.close(foreign)

    assert report.failed == ("cache/staging/a-shared",)
    assert report.removed == ("cache/staging/b-dead",)
    assert (home / "cache/staging/a-shared/objects").is_dir()


def test_the_sweep_never_touches_quarantine(home: Path) -> None:
    ensure_private_directory(home, "cache/quarantine/quarantine-1/sources")

    report = sweep_staging_and_trash(home)

    assert report.removed == ()
    assert (home / "cache/quarantine/quarantine-1/sources").is_dir()


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

    report = reclaim_staging(home)

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

    report = reclaim_staging(home)

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


# ── Store reclamation ──────────────────────────────────────────────


def test_an_unreferenced_store_is_moved_to_trash_and_deleted(home: Path) -> None:
    _make_store(home)
    replay = MachineReplay("store_reclamation")

    outcome = reclaim_store(home, STORE_KEY, observer=replay)

    assert outcome is StoreReclamation.RECLAIMED
    assert replay.events == ["try_exclusive", "move_to_trash", "delete_completed"]
    assert replay.state == "reclaimed"
    assert not (home / f"cache/repository-stores/{STORE_KEY}").exists()
    assert list((home / "cache/trash").iterdir()) == []
    assert list((home / "cache/locks/trash").iterdir()) == []


def test_reclamation_skips_a_store_with_a_live_lease(home: Path) -> None:
    scenario = _scenario("reclaim-skips-leased-store")
    _make_store(home)
    subject = _Child(home, f"lease = locks.store_lease(home, {STORE_KEY!r})")
    replay = MachineReplay("store_reclamation")
    try:
        outcome = reclaim_store(home, STORE_KEY, observer=replay)
    finally:
        subject.finish()

    assert outcome is StoreReclamation.BUSY
    assert replay.events == scenario["events"]
    assert replay.state == scenario["expected_final"]
    assert (home / f"cache/repository-stores/{STORE_KEY}").is_dir()


def test_reclamation_skips_a_referenced_or_absent_store(home: Path) -> None:
    absent = MachineReplay("store_reclamation")
    assert reclaim_store(home, STORE_KEY, observer=absent) is StoreReclamation.ABSENT
    assert absent.events == ["try_exclusive", "store_absent"]

    _make_store(home)
    _make_source_with_alias(home)
    referenced = MachineReplay("store_reclamation")
    assert reclaim_store(home, STORE_KEY, observer=referenced) is StoreReclamation.REFERENCED
    assert referenced.events == ["try_exclusive", "still_referenced"]
    assert referenced.state == "skipped"
    assert (home / f"cache/repository-stores/{STORE_KEY}").is_dir()


@pytest.mark.parametrize(
    "setup",
    [
        lambda home: ensure_private_directory(home, "cache/provider-bindings"),
        lambda home: (
            ensure_private_directory(home, "cache/provider-bindings"),
            write_private_file_atomic(home, "cache/provider-bindings/source.yml", b"x"),
        ),
        lambda home: (
            ensure_private_directory(home, f"cache/sources/{SLUG}"),
            write_private_file_atomic(home, source_record(SLUG, "store-alias.yml"), b"alias: ["),
        ),
        lambda home: ensure_private_directory(home, "cache/sources/Unknown Entry"),
    ],
    ids=["empty-provider-directory", "provider-binding", "unreadable-alias", "unknown-source"],
)
def test_reference_checks_fail_safe(home: Path, setup: Callable[[Path], object]) -> None:
    setup(home)
    unreferenced = not any((home / "cache/provider-bindings").glob("*")) and not any(
        (home / "cache/sources").glob("*")
    )

    assert store_is_referenced(home, STORE_KEY) is not unreferenced


def test_a_reclamation_killed_while_deleting_trash_is_finished_by_the_sweep(home: Path) -> None:
    scenario = _scenario("reclaim-crash-in-trash")
    _make_store(home)

    result = _run_until_killed(
        home,
        f"""
        reclaim._remove_tree = die
        reclaim.reclaim_store(home, {STORE_KEY!r})
        """,
    )

    assert result.returncode == -signal.SIGKILL, result.stderr
    replay = MachineReplay("store_reclamation")
    replay.advance([event for event in scenario["events"] if event != "crash"])
    assert replay.crash() == scenario["expected_final"] == "trash_swept"
    assert not (home / f"cache/repository-stores/{STORE_KEY}").exists()
    (left,) = list((home / "cache/trash").iterdir())

    report = reclaim_trash(home)

    assert report.removed == (f"cache/trash/{left.name}",)
    assert list((home / "cache/trash").iterdir()) == []
    assert replay.visible is scenario["expected_visible"]


# ── Quarantine ─────────────────────────────────────────────────────


def _recording_publish(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    moves: list[str] = []

    def recording_publish(home: Path, staged: str, target: str, **kwargs: Any) -> bool:
        moves.append(staged)
        return publish_entry(home, staged, target, **kwargs)

    monkeypatch.setattr(reclaim_module, "publish_entry", recording_publish)
    return moves


def test_quarantine_moves_the_alias_then_the_store(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_store(home)
    _make_source_with_alias(home)
    moves = _recording_publish(monkeypatch)
    replay = MachineReplay("quarantine")

    outcome = quarantine_entries(
        home,
        source_slugs=[SLUG],
        store_keys=[STORE_KEY],
        revalidate=lambda: False,
        observer=replay,
    )

    assert outcome.state == "quarantined" and outcome.entry is not None
    assert replay.events == [
        "try_exclusive",
        "move_alias_to_quarantine",
        "move_store_to_quarantine",
    ]
    assert moves == [f"cache/sources/{SLUG}", f"cache/repository-stores/{STORE_KEY}"]
    assert outcome.retained == (
        f"cache/quarantine/{outcome.entry}/sources/{SLUG}",
        f"cache/quarantine/{outcome.entry}/repository-stores/{STORE_KEY}",
    )
    assert all((home / path).is_dir() for path in outcome.retained)
    assert replay.state == "quarantined" and replay.visible is False

    sweep_staging_and_trash(home)
    assert all((home / path).is_dir() for path in outcome.retained)


def test_a_quarantined_store_is_deleted_only_by_explicit_purge(home: Path) -> None:
    scenario = _scenario("quarantine-explicit-purge")
    _make_store(home)
    replay = MachineReplay("quarantine")

    # The source the store was resolved through is locked, but its alias entry is already
    # gone, so only the store moves.
    outcome = quarantine_entries(
        home,
        source_slugs=[SLUG],
        store_keys=[STORE_KEY],
        revalidate=lambda: False,
        observer=replay,
    )
    assert outcome.entry is not None
    assert reclaim_store(home, STORE_KEY) is StoreReclamation.ABSENT
    assert purge_quarantined(home, outcome.entry, observer=replay) is True

    assert replay.events == scenario["events"]
    assert replay.state == scenario["expected_final"]
    assert replay.visible is scenario["expected_visible"]
    assert list((home / "cache/quarantine").iterdir()) == []
    assert list((home / "cache/trash").iterdir()) == []


def test_quarantine_leaves_a_healthy_entry_in_place(home: Path) -> None:
    _make_store(home)
    _make_source_with_alias(home)
    replay = MachineReplay("quarantine")

    outcome = quarantine_entries(
        home, source_slugs=[SLUG], store_keys=[STORE_KEY], revalidate=lambda: True, observer=replay
    )

    assert outcome.state == "healthy"
    assert replay.events == ["try_exclusive", "revalidated_ok"]
    assert (home / f"cache/sources/{SLUG}").is_dir()
    assert list((home / "cache/quarantine").iterdir()) == []


def test_quarantine_of_an_absent_store_moves_nothing(home: Path) -> None:
    _make_source_with_alias(home)
    replay = MachineReplay("quarantine")

    outcome = quarantine_entries(
        home,
        source_slugs=[SLUG],
        store_keys=[STORE_KEY],
        revalidate=lambda: pytest.fail("revalidated a store that is absent"),
        observer=replay,
    )

    assert outcome.state == "nothing_to_quarantine"
    assert replay.events == ["try_exclusive", "store_absent"]
    assert replay.state == "nothing_to_quarantine"
    assert (home / f"cache/sources/{SLUG}").is_dir()
    with pytest.raises(ValueError, match="at least one repository store"):
        quarantine_entries(home, source_slugs=[SLUG], store_keys=[], revalidate=lambda: False)


@pytest.mark.parametrize("source_slugs", [[SLUG], []], ids=["alias-first", "store-only"])
def test_quarantine_defers_while_a_lease_is_held(home: Path, source_slugs: list[str]) -> None:
    _make_store(home)
    subject = _Child(home, f"lease = locks.store_lease(home, {STORE_KEY!r})")
    replay = MachineReplay("quarantine")
    try:
        outcome = quarantine_entries(
            home,
            source_slugs=source_slugs,
            store_keys=[STORE_KEY],
            revalidate=lambda: pytest.fail("revalidated without the maintenance lock"),
            observer=replay,
        )
    finally:
        subject.finish()

    assert outcome.state == "deferred"
    assert replay.events == ["exclusive_busy"]
    assert replay.state == "deferred"


def test_a_quarantine_survives_a_crash_and_every_later_sweep(home: Path) -> None:
    scenario = _scenario("quarantine-survives-crash")
    _make_store(home)
    _make_source_with_alias(home)

    result = _run_until_killed(
        home,
        f"""
        reclaim.quarantine_entries(
            home, source_slugs=[{SLUG!r}], store_keys=[{STORE_KEY!r}], revalidate=lambda: False
        )
        die()
        """,
    )

    assert result.returncode == -signal.SIGKILL, result.stderr
    replay = MachineReplay("quarantine")
    replay.advance([event for event in scenario["events"] if event != "crash"])
    assert replay.crash() == scenario["expected_final"] == "quarantine_retained"
    assert replay.visible is scenario["expected_visible"]
    sweep_staging_and_trash(home)
    (entry,) = list((home / "cache/quarantine").iterdir())
    assert (entry / "sources" / SLUG / "store-alias.yml").is_file()
    assert (entry / "repository-stores" / STORE_KEY).is_dir()


def test_a_crash_between_alias_and_store_leaves_an_ordinary_unreferenced_store(
    home: Path,
) -> None:
    scenario = _scenario("quarantine-crash-between-moves")
    _make_store(home)
    _make_source_with_alias(home)

    result = _run_until_killed(
        home,
        """
        real_publish = reclaim.publish_entry
        calls = []
        def publish_once_then_die(*args, **kwargs):
            calls.append(args)
            if len(calls) > 1:
                die()
            return real_publish(*args, **kwargs)
        reclaim.publish_entry = publish_once_then_die
        """
        + f"""
        reclaim.quarantine_entries(
            home, source_slugs=[{SLUG!r}], store_keys=[{STORE_KEY!r}], revalidate=lambda: False
        )
        """,
    )

    assert result.returncode == -signal.SIGKILL, result.stderr
    replay = MachineReplay("quarantine")
    replay.advance([event for event in scenario["events"] if event != "crash"])
    assert replay.crash() == scenario["expected_final"] == "alias_quarantined_store_reclaimable"
    assert replay.visible is scenario["expected_visible"]
    (entry,) = list((home / "cache/quarantine").iterdir())
    assert (entry / "sources" / SLUG / "store-alias.yml").is_file()
    assert not (home / f"cache/sources/{SLUG}").exists()
    assert (home / f"cache/repository-stores/{STORE_KEY}").is_dir()
    assert not store_is_referenced(home, STORE_KEY)
    assert reclaim_store(home, STORE_KEY) is StoreReclamation.RECLAIMED


# ── Store-only quarantine ──────────────────────────────────────────


def test_a_store_no_alias_names_is_quarantined_under_its_store_lock_alone(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _scenario("quarantine-unreferenced-store")
    _make_store(home)
    moves = _recording_publish(monkeypatch)
    replay = MachineReplay("quarantine")

    outcome = quarantine_entries(
        home, source_slugs=[], store_keys=[STORE_KEY], revalidate=lambda: False, observer=replay
    )

    assert replay.events == scenario["events"]
    assert replay.state == scenario["expected_final"]
    assert replay.visible is scenario["expected_visible"]
    assert outcome.state == "quarantined" and outcome.entry is not None
    assert moves == [f"cache/repository-stores/{STORE_KEY}"]
    assert outcome.retained == (f"cache/quarantine/{outcome.entry}/repository-stores/{STORE_KEY}",)
    assert list((home / "cache/locks/sources").iterdir()) == []


def test_store_only_quarantine_falls_back_when_an_alias_now_names_the_store(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenario = _scenario("quarantine-unreferenced-store-now-aliased")
    _make_store(home)
    _make_source_with_alias(home)
    moves = _recording_publish(monkeypatch)
    replay = MachineReplay("quarantine")

    outcome = quarantine_entries(
        home, source_slugs=[], store_keys=[STORE_KEY], revalidate=lambda: False, observer=replay
    )

    assert replay.events == scenario["events"]
    assert replay.state == scenario["expected_final"]
    assert outcome.state == "quarantined" and outcome.entry is not None
    assert moves == [f"cache/sources/{SLUG}", f"cache/repository-stores/{STORE_KEY}"]
    assert not (home / f"cache/sources/{SLUG}").exists()


def test_store_only_quarantine_treats_an_unreadable_alias_as_naming_the_store(
    home: Path,
) -> None:
    _make_store(home)
    ensure_private_directory(home, f"cache/sources/{SLUG}")
    write_private_file_atomic(home, source_record(SLUG, "store-alias.yml"), b"alias: [")
    replay = MachineReplay("quarantine")

    outcome = quarantine_entries(
        home, source_slugs=[], store_keys=[STORE_KEY], revalidate=lambda: False, observer=replay
    )

    assert replay.events[:2] == ["try_exclusive", "alias_now_names_store"]
    assert outcome.entry is not None
    assert (home / f"cache/quarantine/{outcome.entry}/sources/{SLUG}/store-alias.yml").is_file()


@pytest.mark.parametrize(
    ("make_store", "revalidates", "expected"),
    [
        (False, False, ["try_exclusive", "unreferenced_store_absent"]),
        (True, True, ["try_exclusive", "unreferenced_store_revalidated_ok"]),
    ],
    ids=["absent", "repaired"],
)
def test_store_only_quarantine_moves_nothing_it_need_not(
    home: Path, make_store: bool, revalidates: bool, expected: list[str]
) -> None:
    if make_store:
        _make_store(home)
    replay = MachineReplay("quarantine")

    outcome = quarantine_entries(
        home,
        source_slugs=[],
        store_keys=[STORE_KEY],
        revalidate=lambda: revalidates,
        observer=replay,
    )

    assert replay.events == expected
    assert outcome.state == replay.state
    assert list((home / "cache/quarantine").iterdir()) == []
    assert (home / f"cache/repository-stores/{STORE_KEY}").is_dir() is make_store


@pytest.mark.parametrize("operation", ["reclaim", "purge"], ids=["reclamation", "quarantine-purge"])
def test_a_failed_trash_deletion_still_releases_its_entry_lock(
    home: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    """A leaked descriptor would make the sweep read the entry as live for this process."""

    _make_store(home)
    entry: str | None = None
    if operation == "purge":
        outcome = quarantine_entries(
            home, source_slugs=[], store_keys=[STORE_KEY], revalidate=lambda: False
        )
        entry = outcome.entry
        assert entry is not None

    def unreadable(_path: Path) -> bool:
        raise OSError(errno.EIO, "input/output error")

    monkeypatch.setattr(reclaim_module, "_remove_tree", unreadable)
    with pytest.raises(OSError, match="input/output error"):
        if entry is None:
            reclaim_store(home, STORE_KEY)
        else:
            purge_quarantined(home, entry)

    monkeypatch.undo()
    (left,) = list((home / "cache/trash").iterdir())

    report = reclaim_trash(home)

    assert report.removed == (f"cache/trash/{left.name}",)
    assert report.live == ()
    assert list((home / "cache/trash").iterdir()) == []
    assert list((home / "cache/locks/trash").iterdir()) == []


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

    report = reclaim_staging(home)

    assert report.failed == ("cache/staging/dead-1",)
    assert report.removed == ()
