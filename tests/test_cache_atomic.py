"""Atomic record I/O and lock-verified publication in a temporary application home.

Interrupted writes and publications are real: a child interpreter is killed with SIGKILL
at the rename that would have committed, and the parent checks what a later process
finds on disk.
"""

from __future__ import annotations

import ctypes
import errno
import logging
import os
import stat
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from metabrowser import home as home_module
from metabrowser.cache.atomic import (
    MAX_READ_OPENS,
    MAX_RECORD_BYTES,
    RecordError,
    publish_entry,
    read_bytes_bounded,
    read_record,
    serialize_record,
    write_record_atomic,
)
from metabrowser.cache.locks import LockOrderError, repository_store_lock, staging_entry_lock
from metabrowser.cache.records import (
    CACHE_LAYOUT_CONTRACT_ID,
    REPOSITORY_SOURCE_STATE_CONTRACT_ID,
    REPOSITORY_STORE_STATE_CONTRACT_ID,
    CacheLayout,
    RepositorySourceState,
)
from metabrowser.home import (
    PrivateStorageError,
    PrivateStorageViolation,
    ensure_home,
    ensure_private_directory,
    rename_without_replacing,
    write_private_file_atomic,
)

pytestmark = pytest.mark.skipif(os.name != "posix", reason="owner-only storage is POSIX-only")
fcntl = pytest.importorskip("fcntl")

STORE_KEY = "c" * 64
CHILD_TIMEOUT = 50


@pytest.fixture
def home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    ensure_home(home)
    return home


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.lstat(path).st_mode)


def _temporaries(directory: Path) -> list[str]:
    return sorted(name for name in os.listdir(directory) if name.endswith(".tmp"))


def _run_killed_at_rename(home: Path, body: str) -> subprocess.CompletedProcess[str]:
    """Run *body* in a child whose first rename that commits kills the child."""

    script = textwrap.dedent(
        """
        import os, signal, sys
        from pathlib import Path
        from metabrowser import home as home_module
        home = Path(sys.argv[1])

        def die(*_args, **_kwargs):
            os.kill(os.getpid(), signal.SIGKILL)

        os.replace = die
        os.rename = die
        home_module.rename_without_replacing = die
        """
    ) + textwrap.dedent(body)
    return subprocess.run(
        [sys.executable, "-c", script, str(home)],
        capture_output=True,
        text=True,
        timeout=CHILD_TIMEOUT,
        check=False,
    )


# ── Atomic files ───────────────────────────────────────────────────


def test_an_atomic_write_replaces_the_whole_file_with_a_private_one(home: Path) -> None:
    write_private_file_atomic(home, "example.yml", b"first\n")
    first_inode = os.lstat(home / "example.yml").st_ino
    write_private_file_atomic(home, "example.yml", b"second\n")

    assert (home / "example.yml").read_bytes() == b"second\n"
    assert os.lstat(home / "example.yml").st_ino != first_inode
    assert _mode(home / "example.yml") == 0o600
    assert _temporaries(home) == []


def test_a_no_replace_write_refuses_an_existing_file_and_leaves_no_temporary(home: Path) -> None:
    write_private_file_atomic(home, "example.yml", b"first\n", replace=False)

    with pytest.raises(FileExistsError):
        write_private_file_atomic(home, "example.yml", b"second\n", replace=False)

    assert (home / "example.yml").read_bytes() == b"first\n"
    assert _temporaries(home) == []


def test_an_atomic_write_needs_an_existing_private_parent(home: Path) -> None:
    with pytest.raises(FileNotFoundError):
        write_private_file_atomic(home, "missing/example.yml", b"x")
    assert not (home / "missing").exists()


def test_a_write_killed_before_its_rename_leaves_the_previous_record(home: Path) -> None:
    write_private_file_atomic(home, "example.yml", b"old\n")

    result = _run_killed_at_rename(
        home,
        """
        home_module.write_private_file_atomic(home, "example.yml", b"new\\n")
        print("rename did not run")
        """,
    )

    assert result.returncode == -9, result.stderr
    assert (home / "example.yml").read_bytes() == b"old\n"
    (leftover,) = _temporaries(home)
    assert leftover.startswith(".example.yml.")
    assert (home / leftover).read_bytes() == b"new\n"

    write_private_file_atomic(home, "example.yml", b"newer\n")

    assert (home / "example.yml").read_bytes() == b"newer\n"
    assert _temporaries(home) == []


def test_a_live_writers_temporary_is_never_removed(home: Path) -> None:
    live = home / ".example.yml.0123456789abcdef.tmp"
    fd = home_module.open_private_file(
        home, ".example.yml.0123456789abcdef.tmp", os.O_WRONLY | os.O_CREAT | os.O_EXCL
    )
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        write_private_file_atomic(home, "example.yml", b"content\n")
        assert live.exists()
    finally:
        os.close(fd)
    write_private_file_atomic(home, "example.yml", b"content\n")
    assert not live.exists()


# ── Concurrent writers of one target ───────────────────────────────


def _leftover(home: Path, token: str = "f" * 16) -> Path:
    """Leave a temporary of ``example.yml`` as a writer that crashed before its lock does."""

    path = home / f".example.yml.{token}.tmp"
    os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
    return path


def _counted_draws(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Count the temporary names writers draw: one per write unless a write lost its file."""

    real = home_module.secrets.token_hex
    draws: list[int] = []
    guard = threading.Lock()

    def token_hex(length: int) -> str:
        with guard:
            draws.append(1)
        return real(length)

    monkeypatch.setattr(home_module, "secrets", SimpleNamespace(token_hex=token_hex))
    return draws


def _second_write_while_creating(
    monkeypatch: pytest.MonkeyPatch, home: Path, step: str, during: Callable[[], None]
) -> list[str]:
    """Run *during* while the first write's new temporary exists but is not yet locked.

    *step* ``"create"`` runs it as soon as the exclusive ``open`` that creates that
    temporary returns, before the open's own checks of the new file; ``"lock"`` runs it
    once the file is checked, just before the writer takes its ``flock``. The list names
    every temporary a writer creates, in order.
    """

    created: list[str] = []
    real_open = os.open
    real_hold = home_module._hold_temporary  # pyright: ignore[reportPrivateUsage]

    def opening(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        fd = real_open(path, flags, *args, **kwargs)
        ours = isinstance(path, str) and path.startswith(".example.yml.")
        if ours and flags & os.O_EXCL and kwargs.get("dir_fd") is not None:
            created.append(path)
            if step == "create" and len(created) == 1:
                during()
        return fd

    def holding(fd: int, path: Path) -> bool:
        if step == "lock" and len(created) == 1:
            during()
        return real_hold(fd, path)

    monkeypatch.setattr(os, "open", opening)
    monkeypatch.setattr(home_module, "_hold_temporary", holding)
    return created


@pytest.mark.parametrize("step", ["create", "lock"], ids=["after-create", "before-lock"])
def test_another_writers_sweep_never_takes_a_temporary_before_it_is_locked(
    home: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, step: str
) -> None:
    """A second writer of the target sweeps while the first's temporary is not yet held.

    The exclusive create and the ``flock`` are two system calls, and a sweep between them
    found the file unlocked and unlinked it as a crashed writer's (mb-532r). After the
    create the first write was refused as replaced, in CI three times; before the lock it
    drew another name. Mutation check: create and lock the temporary outside the
    directory's shared lock, and ``after-create`` raises while ``before-lock`` creates a
    third temporary and logs a removal.
    """

    def second_write() -> None:
        write_private_file_atomic(home, "example.yml", b"second\n")
        assert (home / "example.yml").read_bytes() == b"second\n"

    created = _second_write_while_creating(monkeypatch, home, step, second_write)
    with caplog.at_level(logging.INFO, logger="metabrowser.home"):
        write_private_file_atomic(home, "example.yml", b"first\n")

    assert (home / "example.yml").read_bytes() == b"first\n"
    assert len(created) == 2, created
    assert "Removed a temporary file" not in caplog.text
    assert _temporaries(home) == []


def test_a_crashed_writers_leftover_waits_out_a_writer_that_is_creating(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sweep that meets a writer between create and lock leaves even real leftovers.

    It cannot tell that writer's file from a crashed one's then, so it keeps both, and
    the next sweep that finds no writer creating removes the leftover.
    """

    leftover = _leftover(home)

    def second_write() -> None:
        write_private_file_atomic(home, "example.yml", b"second\n")
        assert leftover.exists()

    created = _second_write_while_creating(monkeypatch, home, "create", second_write)
    write_private_file_atomic(home, "example.yml", b"first\n")

    assert len(created) == 2
    assert not leftover.exists()
    assert _temporaries(home) == []


def test_a_writer_killed_between_create_and_lock_leaves_a_removable_leftover(
    home: Path,
) -> None:
    """The directory's shared lock goes with the killed process, so its file is swept."""

    result = _run_killed_at_rename(
        home,
        """
        home_module._hold_temporary = die
        home_module.write_private_file_atomic(home, "example.yml", b"new\\n")
        print("the temporary was locked")
        """,
    )

    assert result.returncode == -9, result.stderr
    (leftover,) = _temporaries(home)
    assert leftover.startswith(".example.yml.")

    write_private_file_atomic(home, "example.yml", b"newer\n")

    assert (home / "example.yml").read_bytes() == b"newer\n"
    assert _temporaries(home) == []


def test_a_copy_of_a_directory_lock_descriptor_does_not_keep_the_lock(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A child forked while a writer holds the directory's lock inherits the descriptor.

    ``flock`` belongs to the open file description, which the child's copy keeps open,
    so closing the parent's descriptor would leave the lock held for as long as the child
    lives and every sweep would be skipped. Each directory lock is released explicitly.
    Here every directory descriptor the writer opens is duplicated and kept, as a child
    would keep it. Mutation check: close the directory lock without ``LOCK_UN`` and the
    leftover is never removed.
    """

    real_open = os.open
    copies: list[int] = []

    def opening(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        fd = real_open(path, flags, *args, **kwargs)
        if path == "." and flags & os.O_DIRECTORY and kwargs.get("dir_fd") is not None:
            copies.append(os.dup(fd))
        return fd

    monkeypatch.setattr(os, "open", opening)
    try:
        write_private_file_atomic(home, "example.yml", b"first\n")
        leftover = _leftover(home)
        write_private_file_atomic(home, "example.yml", b"second\n")

        assert copies
        assert not leftover.exists()
    finally:
        for fd in copies:
            os.close(fd)


def test_where_a_directory_cannot_be_locked_writers_go_ahead_and_sweeps_skip(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file system that locks files but not directories still takes writes.

    No sweep there can take the exclusive lock either, so none can remove a temporary
    whose writer has not locked it yet; leftovers stay until the lock is available.
    """

    real_flock = fcntl.flock

    def flock(fd: int, operation: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(errno.ENOTSUP, os.strerror(errno.ENOTSUP))
        real_flock(fd, operation)

    leftover = _leftover(home)
    monkeypatch.setattr(home_module, "fcntl", SimpleNamespace(**{**vars(fcntl), "flock": flock}))
    write_private_file_atomic(home, "example.yml", b"first\n")

    assert (home / "example.yml").read_bytes() == b"first\n"
    assert leftover.exists()

    monkeypatch.undo()
    write_private_file_atomic(home, "example.yml", b"second\n")
    assert _temporaries(home) == []


def test_an_unexpected_directory_lock_failure_refuses_the_write(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the errors that mean no lock exists are let through; others are raised."""

    real_flock = fcntl.flock

    def flock(fd: int, operation: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(errno.EIO, os.strerror(errno.EIO))
        real_flock(fd, operation)

    monkeypatch.setattr(home_module, "fcntl", SimpleNamespace(**{**vars(fcntl), "flock": flock}))
    with pytest.raises(OSError) as refused:
        write_private_file_atomic(home, "example.yml", b"first\n")

    assert refused.value.errno == errno.EIO
    assert str(home) not in str(refused.value)
    assert not (home / "example.yml").exists()
    assert _temporaries(home) == []


# Measured 2026-11-17 on a 10-CPU Mac at load average 10 to 18, without mb-532r's fix:
# eight processes of 100 writes each were refused in 5 of 10 runs, and eight threads of
# 60 in 1 of 20, as the GIL rarely lets another thread in between create and lock. With
# it, none of 20 and 10. Each run takes about a second, far inside the suite's budget.
STRESS_THREADS = 8
STRESS_THREAD_WRITES = 60
STRESS_PROCESSES = 8
STRESS_PROCESS_WRITES = 100
# Each writer leaves a crashed writer's leftover this often, so the sweeps have real work.
STRESS_LEFTOVER_EVERY = 10


def test_concurrent_writers_and_sweeps_in_threads_never_lose_a_temporary(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every write sweeps; none of them may take another writer's file, or refuse."""

    draws = _counted_draws(monkeypatch)
    start = threading.Barrier(STRESS_THREADS)
    failures: list[BaseException] = []

    def run(index: int) -> None:
        try:
            start.wait(timeout=CHILD_TIMEOUT)
            for count in range(STRESS_THREAD_WRITES):
                write_private_file_atomic(home, "example.yml", f"{index}:{count}\n".encode())
                if count % STRESS_LEFTOVER_EVERY == 0:
                    _leftover(home, f"{index:08x}{count:08x}")
        except BaseException as failure:
            failures.append(failure)

    threads = [threading.Thread(target=run, args=(index,)) for index in range(STRESS_THREADS)]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + CHILD_TIMEOUT
    for thread in threads:
        thread.join(timeout=max(0.0, deadline - time.monotonic()))
    assert not any(thread.is_alive() for thread in threads)

    assert failures == []
    assert len(draws) == STRESS_THREADS * STRESS_THREAD_WRITES
    write_private_file_atomic(home, "example.yml", b"last\n")
    assert _temporaries(home) == []


_STRESS_CHILD = """
import os, secrets, sys
from pathlib import Path
from types import SimpleNamespace
from metabrowser import home as home_module

home, index, writes, every = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
draws = []

def token_hex(length):
    draws.append(1)
    return secrets.token_hex(length)

home_module.secrets = SimpleNamespace(token_hex=token_hex)
sys.stdin.readline()
for count in range(writes):
    home_module.write_private_file_atomic(home, "example.yml", f"{index}:{count}\\n".encode())
    if count % every == 0:
        name = f".example.yml.{index:08x}{count:08x}.tmp"
        os.close(os.open(home / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
print(len(draws))
"""


def test_concurrent_writers_and_sweeps_in_processes_never_lose_a_temporary(
    home: Path,
) -> None:
    """The same contest between interpreters, where only the file locks order them."""

    children = [
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                _STRESS_CHILD,
                str(home),
                str(index),
                str(STRESS_PROCESS_WRITES),
                str(STRESS_LEFTOVER_EVERY),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in range(STRESS_PROCESSES)
    ]
    deadline = time.monotonic() + CHILD_TIMEOUT
    results: list[tuple[int, str, str]] = []
    try:
        for child in children:
            assert child.stdin is not None
            child.stdin.write("go\n")
            child.stdin.flush()
        for child in children:
            out, err = child.communicate(timeout=max(0.0, deadline - time.monotonic()))
            results.append((child.returncode, out.strip(), err))
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait()

    assert results == [(0, str(STRESS_PROCESS_WRITES), "")] * STRESS_PROCESSES
    write_private_file_atomic(home, "example.yml", b"last\n")
    assert _temporaries(home) == []


def test_the_no_replace_rename_refuses_an_empty_directory_os_rename_would_replace(
    tmp_path: Path,
) -> None:
    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "payload").write_text("staged")
    (tmp_path / "target").mkdir()

    with pytest.raises(FileExistsError):
        rename_without_replacing(tmp_path / "source", tmp_path / "target")

    assert (tmp_path / "source" / "payload").read_text() == "staged"
    assert list((tmp_path / "target").iterdir()) == []


def test_without_a_platform_no_replace_rename_the_absence_check_still_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(home_module, "_no_replace_rename", lambda: (None, 0, False))
    (tmp_path / "source").mkdir()
    (tmp_path / "target").mkdir()

    with pytest.raises(FileExistsError):
        rename_without_replacing(tmp_path / "source", tmp_path / "target")
    assert rename_without_replacing(tmp_path / "source", tmp_path / "published") is False
    assert (tmp_path / "published").is_dir()


def test_a_file_system_that_ignores_the_no_replace_flag_falls_back_to_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unsupported(*_arguments: object) -> int:

        ctypes.set_errno(errno.EINVAL)
        return -1

    monkeypatch.setattr(home_module, "_no_replace_rename", lambda: (unsupported, 1, False))
    (tmp_path / "source").mkdir()
    (tmp_path / "target").mkdir()

    with pytest.raises(FileExistsError):
        rename_without_replacing(tmp_path / "source", tmp_path / "target")
    assert rename_without_replacing(tmp_path / "source", tmp_path / "published") is False


# ── Publication ────────────────────────────────────────────────────


def test_publication_moves_a_staged_entry_under_its_owning_lock(home: Path) -> None:
    ensure_private_directory(home, "staging/acquire-1/store")
    (home / "staging/acquire-1/store/marker").write_text("complete")

    with staging_entry_lock(home, "acquire-1"), repository_store_lock(home, STORE_KEY) as owner:
        publish_entry(
            home,
            "staging/acquire-1/store",
            f"repository-stores/{STORE_KEY}",
            owner=owner,
        )

    assert (home / f"repository-stores/{STORE_KEY}/marker").read_text() == "complete"
    assert not (home / "staging/acquire-1/store").exists()


def test_publication_refuses_an_existing_target_even_an_empty_one(home: Path) -> None:
    ensure_private_directory(home, "staging/acquire-1/store")
    ensure_private_directory(home, f"repository-stores/{STORE_KEY}")

    with repository_store_lock(home, STORE_KEY) as owner, pytest.raises(FileExistsError):
        publish_entry(
            home,
            "staging/acquire-1/store",
            f"repository-stores/{STORE_KEY}",
            owner=owner,
        )

    assert (home / "staging/acquire-1/store").is_dir()


def test_publication_requires_its_owning_lock_to_be_held(home: Path) -> None:
    ensure_private_directory(home, "staging/acquire-1/store")
    owner = repository_store_lock(home, STORE_KEY)
    owner.release()

    with pytest.raises(LockOrderError, match="owning lock"):
        publish_entry(
            home,
            "staging/acquire-1/store",
            f"repository-stores/{STORE_KEY}",
            owner=owner,
        )


def test_a_publication_killed_at_its_rename_leaves_only_reclaimable_staging(home: Path) -> None:
    ensure_private_directory(home, "staging/acquire-1/store")

    result = _run_killed_at_rename(
        home,
        f"""
        from metabrowser.cache import atomic, locks
        atomic.rename_without_replacing = die
        staging = locks.staging_entry_lock(home, "acquire-1")
        owner = locks.repository_store_lock(home, {STORE_KEY!r})
        atomic.publish_entry(
            home, "staging/acquire-1/store", "repository-stores/{STORE_KEY}", owner=owner
        )
        print("rename did not run")
        """,
    )

    assert result.returncode == -9, result.stderr
    assert not (home / f"repository-stores/{STORE_KEY}").exists()
    assert (home / "staging/acquire-1/store").is_dir()
    # The operating system released the killed owner's locks.
    staging_entry_lock(home, "acquire-1").release()
    repository_store_lock(home, STORE_KEY, blocking=False).release()


# ── Records ────────────────────────────────────────────────────────


def test_records_round_trip_without_a_schema_path(home: Path) -> None:
    layout = CacheLayout(format="f01", created_by="0.11.0")

    write_record_atomic(home, "layout.yml", layout, CACHE_LAYOUT_CONTRACT_ID)

    assert read_record(home, "layout.yml", CACHE_LAYOUT_CONTRACT_ID) == layout
    text = (home / "layout.yml").read_text()
    assert text.startswith("layout:\n") or text.startswith("softschema:\n")
    assert "\n  schema:" not in text
    assert serialize_record(layout, CACHE_LAYOUT_CONTRACT_ID) == (home / "layout.yml").read_bytes()


def test_a_record_read_in_the_wrong_slot_is_refused_without_naming_its_path(home: Path) -> None:
    write_record_atomic(
        home,
        "layout.yml",
        CacheLayout(format="f01", created_by="0.11.0"),
        CACHE_LAYOUT_CONTRACT_ID,
    )

    with pytest.raises(RecordError) as refused:
        read_record(home, "layout.yml", REPOSITORY_STORE_STATE_CONTRACT_ID)

    assert str(home) not in str(refused.value)
    assert refused.value.path == home / "layout.yml"

    # A source's state and a store's share the envelope `state`, so this pair is refused
    # by its contract alone.
    write_record_atomic(
        home,
        "state.yml",
        RepositorySourceState(last_opened_at="2026-09-17T12:00:00Z"),
        REPOSITORY_SOURCE_STATE_CONTRACT_ID,
    )
    with pytest.raises(RecordError, match="does not match its expected contract"):
        read_record(home, "state.yml", REPOSITORY_STORE_STATE_CONTRACT_ID)


def test_an_oversized_record_is_refused_before_it_is_parsed(home: Path) -> None:
    write_private_file_atomic(home, "layout.yml", b"#" * (MAX_RECORD_BYTES + 1))

    with pytest.raises(RecordError, match="larger"):
        read_bytes_bounded(home, "layout.yml")


@pytest.mark.parametrize(
    "payload",
    [
        b"softschema: [unclosed\n",
        b"!!python/object:os.system {}\n",
        b"softschema:\n  contract: metabrowser.cache:CacheLayout/v1\n"
        b"  envelope: layout\n  status: enforced\nlayout: &a\n  format: f01\n"
        b"  created_by: 0.11.0\nother: *a\n",
    ],
    ids=["malformed", "custom-tag", "extra-top-level-key"],
)
def test_malformed_records_are_refused(home: Path, payload: bytes) -> None:
    write_private_file_atomic(home, "layout.yml", payload)

    with pytest.raises(RecordError):
        read_record(home, "layout.yml", CACHE_LAYOUT_CONTRACT_ID)


# ── Reads that meet a republication ────────────────────────────────


def _republished_during(
    monkeypatch: pytest.MonkeyPatch,
    step: str,
    publish: Callable[[], None],
    *,
    times: int = 1,
) -> list[int]:
    """Run *publish* right after a read inspects ``layout.yml`` (*step* ``"stat"``) or
    opens it (``"open"``), the first *times* times; the list it returns counts them.

    The inspection is the no-follow ``stat`` through the parent's descriptor and the open
    is the ``open`` through it, which only the read makes: a writer opens its temporary.
    """

    real = os.stat if step == "stat" else os.open
    published: list[int] = []

    def racing(path: Any, *args: Any, **kwargs: Any) -> Any:
        result = real(path, *args, **kwargs)
        ours = path == "layout.yml" and kwargs.get("dir_fd") is not None
        inspected = step == "open" or kwargs.get("follow_symlinks") is False
        if ours and inspected and len(published) < times:
            published.append(1)
            publish()
        return result

    monkeypatch.setattr(os, step, racing)
    return published


@pytest.mark.parametrize("step", ["stat", "open"], ids=["after-inspection", "after-open"])
def test_a_read_that_meets_a_republication_reads_the_new_record(
    home: Path, monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    """Records are republished by atomic rename, so a read sees the old one or the new.

    The new one is renamed into place between the read's inspection of the entry and its
    open, or between the open and the check of the descriptor, which then names a file
    no longer linked. The pull-files route read no refresh stamp in that window (mb-kq72).
    Mutation check: open once, as ``read_bytes_bounded`` did, and the read is refused.
    """

    write_private_file_atomic(home, "layout.yml", b"old\n")
    _republished_during(
        monkeypatch, step, lambda: write_private_file_atomic(home, "layout.yml", b"new\n")
    )

    assert read_bytes_bounded(home, "layout.yml") == b"new\n"


def test_a_replacement_that_is_not_private_is_refused_when_read_again(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second open judges the replacement in full: a hard link is still refused."""

    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside data that must survive\n")
    outside.chmod(0o600)
    write_private_file_atomic(home, "layout.yml", b"ours\n")

    def link_outside() -> None:
        (home / "layout.yml").unlink()
        os.link(outside, home / "layout.yml")

    _republished_during(monkeypatch, "stat", link_outside)
    with pytest.raises(PrivateStorageError) as refused:
        read_bytes_bounded(home, "layout.yml")

    assert refused.value.violation is PrivateStorageViolation.HARD_LINK
    assert outside.read_bytes() == b"outside data that must survive\n"


def test_an_entry_replaced_at_every_open_is_refused_after_the_bound(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A writer that never stops cannot keep a read opening without end."""

    write_private_file_atomic(home, "layout.yml", b"0\n")
    published = _republished_during(
        monkeypatch,
        "stat",
        lambda: write_private_file_atomic(home, "layout.yml", b"again\n"),
        times=MAX_READ_OPENS + 1,
    )
    with pytest.raises(PrivateStorageError) as refused:
        read_bytes_bounded(home, "layout.yml")

    assert refused.value.replaced
    assert refused.value.violation is PrivateStorageViolation.UNVERIFIABLE
    assert len(published) == MAX_READ_OPENS


def test_a_write_that_runs_out_of_temporary_names_is_not_a_replacement(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``replaced`` is the raising site's, not its message's, which this refusal shares.

    Every temporary name the write draws is taken, so it checks no entry at the path and
    nothing there was replaced: a read must not take this refusal as one to open again.
    """

    monkeypatch.setattr(home_module, "secrets", SimpleNamespace(token_hex=lambda _n: "0" * 16))
    (home / f".layout.yml.{'0' * 16}.tmp").write_bytes(b"")
    with pytest.raises(PrivateStorageError) as refused:
        write_private_file_atomic(home, "layout.yml", b"new\n")

    assert refused.value.violation is PrivateStorageViolation.UNVERIFIABLE
    assert not refused.value.replaced
    assert not (home / "layout.yml").exists()


def _fsync_targets(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Record the device and inode of everything ``os.fsync`` is called on."""

    synced: list[tuple[int, int]] = []
    real_fsync = os.fsync

    def counting_fsync(fd: int) -> None:
        status = os.fstat(fd)
        synced.append((status.st_dev, status.st_ino))
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", counting_fsync)
    return synced


def _identity(path: Path) -> tuple[int, int]:
    status = os.lstat(path)
    return (status.st_dev, status.st_ino)


def test_an_atomic_write_syncs_the_new_file_and_its_directory(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rename is durable only once the bytes and the directory entry are on disk."""

    synced = _fsync_targets(monkeypatch)

    write_private_file_atomic(home, "example.yml", b"content\n")

    assert _identity(home / "example.yml") in synced
    assert _identity(home) in synced


def test_publication_syncs_both_directories_it_changed(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_private_directory(home, "staging/acquire-1/store")
    synced = _fsync_targets(monkeypatch)

    with repository_store_lock(home, STORE_KEY) as owner:
        publish_entry(
            home,
            "staging/acquire-1/store",
            f"repository-stores/{STORE_KEY}",
            owner=owner,
        )

    assert _identity(home / "repository-stores") in synced
    assert _identity(home / "staging/acquire-1") in synced
