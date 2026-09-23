"""Cache locks on async paths: no blocking ``flock`` or sweep runs on the event loop.

A lock another process holds must delay only the coroutine that wants it. Each
responsiveness test holds the contended lock in a real child interpreter, starts the
async operation as a task, lets the loop run a number of ticks, and only then asks the
child to release. A child also releases on its own after :data:`HOLD_AT_MOST` and says
which happened: if the wait had blocked the loop, no tick could run and nothing could ask
until the child gave up, so the test fails on that report rather than on a timing.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from metabrowser.cache.acquire import acquire_file_source
from metabrowser.cache.locks import (
    CacheLock,
    HeldLock,
    LockKind,
    LockOrderError,
    acquire_store_lease,
    application_home_lock,
    held_locks,
    provider_resource_lock,
    repository_store_lock,
    source_alias_lock,
    store_lease,
    store_maintenance_lock,
)
from metabrowser.cache.repository_store import lease_revision
from metabrowser.cancellable_thread import run_acquiring_thread
from metabrowser.home import ensure_home
from tests.test_cache_acquire import _allow_installed_git, _file_source, _origin
from tests.test_git_revision_lease import _publish

pytestmark = pytest.mark.skipif(os.name != "posix", reason="cache locks are BSD flock locks")

STORE_A = "a" * 64
SLUG_A = "github-com--acme--alpha--0123456789ab"
CHILD_TIMEOUT = 30.0
HOLD_AT_MOST = 10.0
TICK_S = 0.01
TICKS = 20

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git executable is required")


class _BoundedHolder:
    """A child interpreter that holds one lock until told to release, or HOLD_AT_MOST."""

    def __init__(self, home: Path, acquire: str) -> None:
        script = textwrap.dedent(
            f"""
            import select
            import sys
            from pathlib import Path
            from metabrowser.cache import locks
            home = Path(sys.argv[1])
            lock = {acquire}
            print("held", flush=True)
            asked, _, _ = select.select([sys.stdin], [], [], float(sys.argv[2]))
            lock.release()
            print("asked" if asked else "gave up", flush=True)
            """
        )
        self.process = subprocess.Popen(
            [sys.executable, "-c", script, str(home), str(HOLD_AT_MOST)],
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

    def release(self) -> str:
        """Ask the child to release; return ``asked``, or ``gave up`` if it timed out first."""

        assert self.process.stdin is not None and self.process.stdout is not None
        if self.process.poll() is None:
            try:
                self.process.stdin.write("\n")
                self.process.stdin.flush()
            except BrokenPipeError:
                pass
        how = self.process.stdout.readline().strip()
        self.process.communicate(timeout=CHILD_TIMEOUT)
        return how

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.kill()
        self.process.communicate(timeout=CHILD_TIMEOUT)


async def _ticks_while_pending(task: asyncio.Task[object]) -> int:
    """Count loop ticks until TICKS have run or *task* finishes."""

    ticks = 0
    while ticks < TICKS and not task.done():
        await asyncio.sleep(TICK_S)
        ticks += 1
    return ticks


# ── The guard ──────────────────────────────────────────────────────


BLOCKING_LOCKS: list[Callable[[Path], CacheLock]] = [
    application_home_lock,
    lambda home: source_alias_lock(home, SLUG_A),
    lambda home: repository_store_lock(home, STORE_A),
    lambda home: provider_resource_lock(home, "p1"),
    lambda home: store_lease(home, STORE_A),
]


@pytest.mark.parametrize("take", BLOCKING_LOCKS)
def test_a_blocking_lock_is_refused_on_an_event_loop_thread(
    tmp_path: Path, take: Callable[[Path], CacheLock]
) -> None:
    home = tmp_path / "home"
    ensure_home(home)

    async def on_the_loop() -> None:
        take(home).release()

    with pytest.raises(LockOrderError, match="stall the event loop"):
        asyncio.run(on_the_loop())
    assert held_locks() == ()

    async def in_a_worker() -> None:
        (await asyncio.to_thread(take, home)).release()

    asyncio.run(in_a_worker())
    take(home).release()
    assert held_locks() == ()


def test_attempts_that_never_block_may_run_on_the_loop(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ensure_home(home)

    async def on_the_loop() -> None:
        with source_alias_lock(home, SLUG_A, blocking=False):
            pass
        with store_maintenance_lock(home, STORE_A):
            pass

    asyncio.run(on_the_loop())
    assert held_locks() == ()


# ── Lease ownership ────────────────────────────────────────────────


def test_an_async_lease_belongs_to_the_awaiting_thread_not_the_worker(tmp_path: Path) -> None:
    """The worker opens and locks; the loop thread holds, reports, and releases."""

    home = tmp_path / "home"
    ensure_home(home)

    async def scenario() -> tuple[tuple[HeldLock, ...], tuple[HeldLock, ...]]:
        # One worker thread, so the thread that made the attempt is the one asked.
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=1))
        lease = await acquire_store_lease(home, STORE_A)
        try:
            with pytest.raises(LockOrderError, match="other mode"):
                store_maintenance_lock(home, STORE_A)
            return held_locks(), await asyncio.to_thread(held_locks)
        finally:
            lease.release()

    on_loop, on_worker = asyncio.run(scenario())
    assert on_loop == (HeldLock(LockKind.MAINTENANCE_SHARED, STORE_A),)
    assert on_worker == ()
    assert held_locks() == ()


def test_an_async_lease_is_still_checked_as_a_blocking_wait(tmp_path: Path) -> None:
    home = tmp_path / "home"
    ensure_home(home)

    async def while_holding(take: Callable[[], CacheLock]) -> None:
        with take():
            await acquire_store_lease(home, STORE_A)

    with pytest.raises(LockOrderError, match="could deadlock"):
        asyncio.run(while_holding(lambda: source_alias_lock(home, SLUG_A, blocking=False)))
    with pytest.raises(LockOrderError, match="other mode"):
        asyncio.run(while_holding(lambda: store_maintenance_lock(home, STORE_A)))
    assert held_locks() == ()


@requires_git
def test_a_lease_waits_for_maintenance_in_another_process_without_blocking_the_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, _git_dir, _first, second = _publish(tmp_path, monkeypatch)
    holder = _BoundedHolder(home, f"locks.store_maintenance_lock(home, {store_key!r})")
    try:

        async def scenario() -> None:
            waiting = asyncio.create_task(
                lease_revision(home=home, store_key=store_key, commit_oid=second)
            )
            assert await _ticks_while_pending(waiting) == TICKS
            assert not waiting.done()
            assert held_locks() == ()
            assert holder.release() == "asked"
            lease = await asyncio.wait_for(waiting, CHILD_TIMEOUT)
            try:
                assert held_locks() == (HeldLock(LockKind.MAINTENANCE_SHARED, store_key),)
            finally:
                lease.release()

        asyncio.run(scenario())
    finally:
        holder.close()
    assert held_locks() == ()
    with store_maintenance_lock(home, store_key):
        pass


@requires_git
def test_a_cancelled_lease_wait_holds_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home, store_key, _git_dir, _first, second = _publish(tmp_path, monkeypatch)
    holder = _BoundedHolder(home, f"locks.store_maintenance_lock(home, {store_key!r})")
    try:

        async def scenario() -> None:
            waiting = asyncio.create_task(
                lease_revision(home=home, store_key=store_key, commit_oid=second)
            )
            await _ticks_while_pending(waiting)
            waiting.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiting

        asyncio.run(scenario())
        assert holder.release() == "asked"
    finally:
        holder.close()
    assert held_locks() == ()
    with store_maintenance_lock(home, store_key):
        pass


def test_work_a_cancelled_task_abandoned_is_released_when_it_finishes() -> None:
    """A thread cannot be interrupted; what it acquires after cancellation is released."""

    proceed = threading.Event()
    released: list[str] = []
    done = threading.Event()

    def work() -> str:
        proceed.wait(CHILD_TIMEOUT)
        return "acquired"

    def release(result: str) -> None:
        released.append(result)
        done.set()

    async def scenario() -> None:
        waiting = asyncio.create_task(run_acquiring_thread(work, release=release))
        await asyncio.sleep(TICK_S)
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        assert released == []
        proceed.set()
        await asyncio.to_thread(done.wait, CHILD_TIMEOUT)

    asyncio.run(scenario())
    assert released == ["acquired"]


# ── Acquisition ────────────────────────────────────────────────────


@requires_git
def test_acquisition_waits_for_the_home_lock_without_blocking_the_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A miss opens the cache under the home lock, then publishes, all off the loop."""

    _allow_installed_git(monkeypatch)
    home = tmp_path / "home"
    asyncio.run(acquire_file_source(_file_source(_origin(tmp_path, allow_filter=False)), home=home))
    other = tmp_path / "other"
    other.mkdir()
    other_source = _file_source(_origin(other, allow_filter=False))
    holder = _BoundedHolder(home, "locks.application_home_lock(home)")
    try:

        async def scenario() -> str:
            waiting = asyncio.create_task(acquire_file_source(other_source, home=home))
            assert await _ticks_while_pending(waiting) == TICKS
            assert not waiting.done()
            assert holder.release() == "asked"
            published = await asyncio.wait_for(waiting, CHILD_TIMEOUT)
            assert held_locks() == ()
            return published.store_key

        store_key = asyncio.run(scenario())
    finally:
        holder.close()
    assert held_locks() == ()
    assert (home / "cache" / "repository-stores" / store_key).is_dir()
    assert list((home / "cache" / "staging").iterdir()) == []


def test_a_cancelled_acquisition_behind_a_busy_home_stops_promptly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Ctrl-C cancels the CLI's task; the worker's lock wait must end with it.

    A thread blocked in ``flock`` cannot be interrupted, and ``asyncio.run`` joins its
    executor on the way out, so an uninterruptible wait kept the command running for
    as long as another process held the home lock.
    """

    _allow_installed_git(monkeypatch)
    home = tmp_path / "home"
    asyncio.run(acquire_file_source(_file_source(_origin(tmp_path, allow_filter=False)), home=home))
    other = tmp_path / "other"
    other.mkdir()
    other_source = _file_source(_origin(other, allow_filter=False))
    holder = _BoundedHolder(home, "locks.application_home_lock(home)")
    try:

        async def scenario() -> None:
            waiting = asyncio.create_task(acquire_file_source(other_source, home=home))
            assert await _ticks_while_pending(waiting) == TICKS
            waiting.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiting

        started = time.monotonic()
        asyncio.run(scenario())
        elapsed = time.monotonic() - started
        assert elapsed < HOLD_AT_MOST / 2, f"cancellation waited {elapsed:.1f}s for the lock"
        assert held_locks() == ()
        # Python 3.14 logs an exception left in a shielded worker; an abandoned wait
        # must not leave one, or Ctrl-C prints a traceback.
        assert not [r for r in caplog.records if r.name == "asyncio"], caplog.text
    finally:
        holder.close()
    assert list((home / "cache" / "staging").iterdir()) == []
