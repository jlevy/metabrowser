"""The cache lock hierarchy, side locks, and the application-home probe.

Every home is a temporary directory. Cross-process rules are exercised with real child
interpreters, because an in-process thread shares the process's lock ownership in ways a
second process does not.
"""

from __future__ import annotations

import os
import signal
import stat
import subprocess
import sys
import textwrap
import threading
import time
import types
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest

from metabrowser.cache import locks, probe
from metabrowser.cache.locks import (
    CacheLock,
    HeldLock,
    LockBusyError,
    LockKind,
    LockOrder,
    LockOrderError,
    application_home_lock,
    held_locks,
    job_entry_lock,
    provider_resource_lock,
    repository_store_lock,
    require_no_hierarchy_locks,
    source_alias_lock,
    staging_entry_lock,
    store_lease,
    store_maintenance_lock,
    trash_entry_lock,
)
from metabrowser.home import (
    PrivateStorageError,
    PrivateStorageViolation,
    ensure_home,
    open_private_file,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="cache locks are BSD flock locks")
fcntl = pytest.importorskip("fcntl")

STORE_A = "a" * 64
STORE_B = "b" * 64
SLUG_A = "github-com--acme--alpha--0123456789ab"
SLUG_B = "github-com--acme--beta--0123456789ab"
CHILD_TIMEOUT = 30.0


@pytest.fixture
def home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    ensure_home(home)
    return home


@pytest.fixture(autouse=True)
def no_leaked_locks() -> Generator[None]:
    yield
    assert held_locks() == ()


def _descriptor(lock: CacheLock) -> int:
    fd = lock._fd  # pyright: ignore[reportPrivateUsage]
    assert fd is not None
    return fd


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


class _Holder:
    """A child interpreter that takes one lock, reports it, and waits to be told or killed."""

    def __init__(self, home: Path, acquire: str) -> None:
        script = textwrap.dedent(
            f"""
            import sys
            from pathlib import Path
            from metabrowser.cache import locks
            home = Path(sys.argv[1])
            lock = {acquire}
            print("held", flush=True)
            sys.stdin.readline()
            lock.release()
            print("released", flush=True)
            """
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
        if line != "held":
            _, errors = self.process.communicate(timeout=CHILD_TIMEOUT)
            pytest.fail(f"lock holder did not start: {line!r} {errors}")

    def release(self) -> None:
        assert self.process.stdin is not None and self.process.stdout is not None
        self.process.stdin.write("\n")
        self.process.stdin.flush()
        assert self.process.stdout.readline().strip() == "released"
        self.process.communicate(timeout=CHILD_TIMEOUT)

    def kill(self) -> None:
        self.process.send_signal(signal.SIGKILL)
        self.process.communicate(timeout=CHILD_TIMEOUT)


def _eventually(predicate: Callable[[], bool], timeout: float = CHILD_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


# ── Order ──────────────────────────────────────────────────────────


def test_hierarchy_locks_are_taken_in_rank_then_key_order(home: Path) -> None:
    with (
        application_home_lock(home),
        source_alias_lock(home, SLUG_A),
        source_alias_lock(home, SLUG_B),
        repository_store_lock(home, STORE_A),
        repository_store_lock(home, STORE_B),
        provider_resource_lock(home, "forge-repo-1"),
    ):
        assert [lock.kind for lock in held_locks()] == [
            LockKind.HOME,
            LockKind.SOURCE_ALIAS,
            LockKind.SOURCE_ALIAS,
            LockKind.REPOSITORY_STORE,
            LockKind.REPOSITORY_STORE,
            LockKind.PROVIDER_RESOURCE,
        ]


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (
            lambda home: repository_store_lock(home, STORE_A),
            lambda home: source_alias_lock(home, SLUG_A),
        ),
        (lambda home: source_alias_lock(home, SLUG_A), lambda home: application_home_lock(home)),
        (lambda home: application_home_lock(home), lambda home: application_home_lock(home)),
        (
            lambda home: repository_store_lock(home, STORE_B),
            lambda home: repository_store_lock(home, STORE_A),
        ),
        (
            lambda home: repository_store_lock(home, STORE_A),
            lambda home: repository_store_lock(home, STORE_A),
        ),
        (
            lambda home: provider_resource_lock(home, "p1"),
            lambda home: repository_store_lock(home, STORE_A),
        ),
    ],
    ids=[
        "store-before-alias",
        "home-under-alias",
        "home-twice",
        "stores-descending",
        "store-reentry",
        "provider-before-store",
    ],
)
def test_out_of_order_acquisition_is_refused_before_any_lock_is_taken(
    home: Path,
    first: Callable[[Path], CacheLock],
    second: Callable[[Path], CacheLock],
) -> None:
    with first(home):
        before = held_locks()
        with pytest.raises(LockOrderError):
            second(home)
        assert held_locks() == before


def test_network_work_is_refused_while_a_hierarchy_lock_is_held(home: Path) -> None:
    require_no_hierarchy_locks("fetch")
    with staging_entry_lock(home, "acquire-1"):
        require_no_hierarchy_locks("fetch")
        with repository_store_lock(home, STORE_A), pytest.raises(LockOrderError, match="fetch"):
            require_no_hierarchy_locks("fetch")


def test_a_lease_blocks_only_while_no_hierarchy_lock_is_held(home: Path) -> None:
    with repository_store_lock(home, STORE_A):
        with pytest.raises(LockOrderError, match="deadlock"):
            store_lease(home, STORE_A)
        with store_lease(home, STORE_A, blocking=False):
            pass
    with store_lease(home, STORE_A):
        pass


def test_locks_can_be_released_out_of_order_and_retaken(home: Path) -> None:
    alias = source_alias_lock(home, SLUG_A)
    store = repository_store_lock(home, STORE_A)
    alias.release()
    assert held_locks() == (HeldLock(LockKind.REPOSITORY_STORE, STORE_A),)
    store.release()
    store.release()
    with repository_store_lock(home, STORE_A), repository_store_lock(home, STORE_B):
        pass


def test_the_order_is_per_thread(home: Path) -> None:
    ready = threading.Event()
    done = threading.Event()
    outcome: list[BaseException | None] = []

    def other_thread() -> None:
        try:
            with application_home_lock(home, blocking=False):
                ready.set()
                done.wait(CHILD_TIMEOUT)
            outcome.append(None)
        except BaseException as error:
            ready.set()
            outcome.append(error)

    with repository_store_lock(home, STORE_A):
        thread = threading.Thread(target=other_thread)
        thread.start()
        assert ready.wait(CHILD_TIMEOUT)
        done.set()
        thread.join(CHILD_TIMEOUT)
    assert outcome == [None]


@pytest.mark.parametrize(
    "call",
    [
        lambda home: source_alias_lock(home, "Not-A-Slug"),
        lambda home: repository_store_lock(home, "../" + "a" * 61),
        lambda home: staging_entry_lock(home, "../escape"),
        lambda home: provider_resource_lock(home, "a/b"),
    ],
)
def test_lock_keys_cannot_name_paths_outside_their_directory(
    home: Path, call: Callable[[Path], CacheLock]
) -> None:
    with pytest.raises(ValueError, match="invalid"):
        call(home)


# ── Descriptors, leases, and exclusion ─────────────────────────────


def test_each_acquisition_owns_its_own_descriptor(home: Path) -> None:
    first = store_lease(home, STORE_A)
    second = store_lease(home, STORE_A, blocking=False)
    try:
        assert _descriptor(first) != _descriptor(second)
        assert os.fstat(_descriptor(first)).st_ino == os.fstat(_descriptor(second)).st_ino
    finally:
        second.release()
        first.release()


def test_an_exclusive_attempt_is_refused_while_this_process_holds_a_shared_lease(
    home: Path,
) -> None:
    with store_lease(home, STORE_A):
        with pytest.raises(LockOrderError, match="other mode"):
            store_maintenance_lock(home, STORE_A)
        outcome: list[BaseException | None] = []

        def other_thread() -> None:
            try:
                store_maintenance_lock(home, STORE_A).release()
                outcome.append(None)
            except BaseException as error:
                outcome.append(error)

        thread = threading.Thread(target=other_thread)
        thread.start()
        thread.join(CHILD_TIMEOUT)
        assert len(outcome) == 1 and isinstance(outcome[0], LockBusyError)
    with store_maintenance_lock(home, STORE_A):
        pass


def test_a_second_process_cannot_take_a_held_lock_until_its_holder_dies(home: Path) -> None:
    holder = _Holder(home, f"locks.repository_store_lock(home, {STORE_A!r})")
    try:
        with pytest.raises(LockBusyError):
            repository_store_lock(home, STORE_A, blocking=False)
        holder.kill()
        lock = repository_store_lock(home, STORE_A)
        lock.release()
    finally:
        if holder.process.poll() is None:
            holder.kill()


def test_shared_leases_coexist_across_processes_and_defer_maintenance(home: Path) -> None:
    holder = _Holder(home, f"locks.store_lease(home, {STORE_A!r})")
    try:
        with store_lease(home, STORE_A, blocking=False):
            pass
        with pytest.raises(LockBusyError):
            store_maintenance_lock(home, STORE_A)
        holder.release()
        with store_maintenance_lock(home, STORE_A):
            pass
    finally:
        if holder.process.poll() is None:
            holder.kill()


def test_a_waiter_on_a_replaced_lock_file_retries_on_the_new_file(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = repository_store_lock(home, STORE_A)
    real_open = locks._open_lock_file  # pyright: ignore[reportPrivateUsage]
    opens: list[str] = []

    def counting_open(home: Path, relative_path: str) -> int:
        opens.append(threading.current_thread().name)
        return real_open(home, relative_path)

    monkeypatch.setattr(locks, "_open_lock_file", counting_open)
    acquired: list[CacheLock] = []

    def wait_for_lock() -> None:
        acquired.append(repository_store_lock(home, STORE_A))

    thread = threading.Thread(target=wait_for_lock, name="waiter")
    thread.start()
    assert _eventually(lambda: opens == ["waiter"])
    time.sleep(0.1)
    first.remove_lock_file()
    thread.join(CHILD_TIMEOUT)
    assert len(acquired) == 1
    second = acquired[0]
    try:
        assert opens == ["waiter", "waiter"]
        current = os.lstat(second.path).st_ino
        assert os.fstat(_descriptor(second)).st_ino == current
    finally:
        # Released from a different thread than the one that acquired it.
        second.release()


@pytest.mark.parametrize(
    "call",
    [
        lambda home: staging_entry_lock(home, "acquire-1"),
        lambda home: trash_entry_lock(home, "purge-1"),
        lambda home: job_entry_lock(home, "job-1"),
    ],
    ids=["staging", "trash", "job"],
)
def test_entry_liveness_locks_never_block(home: Path, call: Callable[[Path], CacheLock]) -> None:
    holder_lock = call(home)
    outcome: list[BaseException | None] = []

    def other_thread() -> None:
        try:
            call(home).release()
            outcome.append(None)
        except BaseException as error:
            outcome.append(error)

    thread = threading.Thread(target=other_thread)
    thread.start()
    thread.join(CHILD_TIMEOUT)
    holder_lock.release()
    assert len(outcome) == 1 and isinstance(outcome[0], LockBusyError)


def test_a_lock_file_that_was_shared_is_replaced_under_its_old_lock(home: Path) -> None:
    lock = repository_store_lock(home, STORE_A)
    path = lock.path
    lock.release()
    path.chmod(0o644)
    shared_inode = os.lstat(path).st_ino

    with repository_store_lock(home, STORE_A) as replaced:
        assert os.lstat(path).st_ino != shared_inode
        assert _mode(path) == 0o600
        assert os.fstat(_descriptor(replaced)).st_ino == os.lstat(path).st_ino


def test_a_shared_lock_file_held_by_another_process_is_refused_untouched(home: Path) -> None:
    lock = repository_store_lock(home, STORE_A)
    path = lock.path
    lock.release()
    path.chmod(0o644)
    shared_inode = os.lstat(path).st_ino
    # Stands in for another principal who opened the file while it was shared.
    foreign = os.open(path, os.O_RDONLY)
    try:
        fcntl.flock(foreign, fcntl.LOCK_EX)
        with pytest.raises(PrivateStorageError) as refused:
            repository_store_lock(home, STORE_A, blocking=False)
        assert refused.value.violation is PrivateStorageViolation.UNVERIFIABLE
        assert os.lstat(path).st_ino == shared_inode
        assert _mode(path) == 0o644
    finally:
        os.close(foreign)


def test_lock_files_live_only_under_cache_locks(home: Path) -> None:
    with (
        application_home_lock(home) as home_lock,
        source_alias_lock(home, SLUG_A) as alias,
        repository_store_lock(home, STORE_A) as store,
    ):
        paths = [home_lock.relative_path, alias.relative_path, store.relative_path]
    with store_lease(home, STORE_A) as lease, staging_entry_lock(home, "acquire-1") as staging:
        paths += [lease.relative_path, staging.relative_path]
    assert all(path.startswith("cache/locks/") for path in paths)
    assert all(_mode(home / path) == 0o600 for path in paths)


# ── Lock order state machine ───────────────────────────────────────


def test_lock_order_releases_the_named_lock() -> None:
    order = LockOrder()
    order.check(LockKind.SOURCE_ALIAS, SLUG_A, blocking=True)
    order.acquired(LockKind.SOURCE_ALIAS, SLUG_A)
    with pytest.raises(LockOrderError, match="not held"):
        order.released(LockKind.REPOSITORY_STORE, STORE_A)
    order.released(LockKind.SOURCE_ALIAS, SLUG_A)
    assert order.snapshot() == ()


# ── Probe ──────────────────────────────────────────────────────────


def test_a_local_home_passes_the_probe_once_per_process(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = probe.probe_application_home(home, force=True)

    # APFS was measured to honor renamex_np(RENAME_EXCL); a Linux file system may answer
    # renameat2(RENAME_NOREPLACE) with EINVAL, and publication then relies on its check.
    if sys.platform == "darwin":
        assert report.no_replace_rename is True
    assert list((home / "cache/staging").iterdir()) == []
    assert list((home / "cache/locks/staging").iterdir()) == []

    def must_not_rerun(_home: Path) -> probe.ProbeReport:
        raise AssertionError("the probe ran twice for one home")

    monkeypatch.setattr(probe, "_probe", must_not_rerun)
    assert probe.probe_application_home(home) == report


def _record_lock_shim() -> types.SimpleNamespace:
    """``flock`` implemented with POSIX record locks, as some network file systems do."""

    def flock(fd: int, operation: int) -> None:
        fcntl.lockf(fd, operation)

    return types.SimpleNamespace(
        flock=flock,
        LOCK_EX=fcntl.LOCK_EX,
        LOCK_SH=fcntl.LOCK_SH,
        LOCK_NB=fcntl.LOCK_NB,
        LOCK_UN=fcntl.LOCK_UN,
    )


_RECORD_LOCK_CHILD = probe._CHILD_SCRIPT.replace(  # pyright: ignore[reportPrivateUsage]
    "fcntl.flock(fd,", "fcntl.lockf(fd,"
).replace("os.O_RDONLY | os.O_NOFOLLOW", "os.O_RDWR | os.O_NOFOLLOW")


def test_a_home_whose_locks_vanish_when_a_descriptor_closes_is_refused(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(probe, "fcntl", _record_lock_shim())
    monkeypatch.setattr(probe, "_CHILD_SCRIPT", _RECORD_LOCK_CHILD)

    with pytest.raises(PrivateStorageError, match="unrelated descriptor") as refused:
        probe.probe_application_home(home, force=True)

    assert refused.value.violation is PrivateStorageViolation.UNVERIFIABLE


def test_record_locks_that_survive_every_close_are_still_refused_in_process(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no unrelated close, record locks pass the cross-process exclusion check.

    They are still refused, because a record lock never contends with another lock the
    same process holds, which the separate-descriptor check detects.
    """

    monkeypatch.setattr(probe, "fcntl", _record_lock_shim())
    monkeypatch.setattr(probe, "_CHILD_SCRIPT", _RECORD_LOCK_CHILD)
    real_open = open_private_file

    def open_without_an_unrelated_descriptor(
        home: Path, relative: str, flags: int, **kwargs: Any
    ) -> int:
        if flags == os.O_RDONLY:
            # Any close of a descriptor for the lock file would drop a record lock.
            return os.open(os.devnull, os.O_RDONLY)
        return real_open(home, relative, flags, **kwargs)

    monkeypatch.setattr(probe, "open_private_file", open_without_an_unrelated_descriptor)
    asked: list[str] = []
    real_ask = probe._Child.ask  # pyright: ignore[reportPrivateUsage]

    def recording_ask(child: Any, request: str) -> str:
        answer = real_ask(child, request)
        asked.append(f"{request}={answer}")
        return answer

    monkeypatch.setattr(probe._Child, "ask", recording_ask)  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(PrivateStorageError, match="separate descriptor"):
        probe.probe_application_home(home, force=True)

    assert asked == ["ex sh=busy busy"]


def test_a_home_whose_locks_do_not_exclude_another_process_is_refused(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shim = _record_lock_shim()
    shim.flock = lambda _fd, _operation: None
    monkeypatch.setattr(probe, "fcntl", shim)

    with pytest.raises(PrivateStorageError, match="second process took a lock"):
        probe.probe_application_home(home, force=True)


def test_a_home_whose_rename_replaces_an_existing_entry_is_refused(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def replacing_rename(source: Path, target: Path) -> bool:
        if target.is_dir():
            os.rmdir(target)
        os.replace(source, target)
        return True

    monkeypatch.setattr(probe, "rename_without_replacing", replacing_rename)

    with pytest.raises(PrivateStorageError, match="replaced an existing entry"):
        probe.probe_application_home(home, force=True)


def test_a_refused_home_is_probed_again_next_time(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(probe, "rename_without_replacing", lambda _s, _t: True)
        with pytest.raises(PrivateStorageError):
            probe.probe_application_home(home, force=True)
    assert probe.probe_application_home(home).no_replace_rename in {True, False}


def test_locks_module_exports_every_side_lock() -> None:
    assert {kind.value for kind in LockKind} == {
        "home",
        "source_alias",
        "repository_store",
        "provider_resource",
        "staging_entry",
        "trash_entry",
        "job_entry",
        "maintenance_shared",
        "maintenance_exclusive",
    }
    assert locks.HIERARCHY_RANKS == {
        LockKind.HOME: 1,
        LockKind.SOURCE_ALIAS: 2,
        LockKind.REPOSITORY_STORE: 3,
        LockKind.PROVIDER_RESOURCE: 4,
    }
