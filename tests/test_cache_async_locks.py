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
import subprocess
import sys
import textwrap
import threading
from collections.abc import Callable
from pathlib import Path

import pytest

from metabrowser.cache import acquire as acquire_module
from metabrowser.cache.acquire import acquire_source
from metabrowser.cache.identity import source_identity
from metabrowser.cache.locks import (
    CacheLock,
    LockBusyError,
    LockOrder,
    LockOrderError,
    application_cache_lock,
    held_locks,
    repository_store_lock,
    source_alias_lock,
    staging_entry_lock,
)
from metabrowser.cancellable_thread import run_acquiring_thread
from metabrowser.home import ensure_home
from tests.admitted_git import required_admitted_git
from tests.child_io import read_line
from tests.required_tools import needs_git
from tests.test_cache_acquire import _allow_installed_git, _file_source, _origin

pytestmark = pytest.mark.skipif(os.name != "posix", reason="cache locks are BSD flock locks")

STORE_A = "a" * 64
SLUG_A = "github-com--acme--alpha--0123456789ab"
CHILD_TIMEOUT = 30.0
HOLD_AT_MOST = 10.0
TICK_S = 0.01
TICKS = 20

requires_git = needs_git


class _BoundedHolder:
    """A child interpreter that holds one lock until told to release, or *hold_at_most*."""

    def __init__(self, home: Path, acquire: str, *, hold_at_most: float = HOLD_AT_MOST) -> None:
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
            [sys.executable, "-c", script, str(home), str(hold_at_most)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        line = read_line(self.process).strip()
        if line != "held":
            _, errors = self.process.communicate(timeout=CHILD_TIMEOUT)
            pytest.fail(f"lock holder did not start: {line!r} {errors}")

    def release(self) -> str:
        """Ask the child to release; return ``asked``, or ``gave up`` if it timed out first."""

        assert self.process.stdin is not None
        if self.process.poll() is None:
            try:
                self.process.stdin.write("\n")
                self.process.stdin.flush()
            except BrokenPipeError:
                pass
        how = read_line(self.process).strip()
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
    application_cache_lock,
    lambda home: source_alias_lock(home, SLUG_A),
    lambda home: repository_store_lock(home, STORE_A),
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
        with staging_entry_lock(home, "acquire-1"):
            pass

    asyncio.run(on_the_loop())
    assert held_locks() == ()


# ── Abandoned work ─────────────────────────────────────────────────


def test_work_a_cancelled_task_abandoned_is_released_when_it_finishes() -> None:
    """A thread cannot be interrupted; what it acquires after cancellation is released."""

    working = threading.Event()
    proceed = threading.Event()
    released: list[str] = []
    done = threading.Event()

    def work() -> str:
        working.set()
        proceed.wait(CHILD_TIMEOUT)
        return "acquired"

    def release(result: str) -> None:
        released.append(result)
        done.set()

    async def scenario() -> None:
        waiting = asyncio.create_task(run_acquiring_thread(work, release=release))
        # 20 s, so that with the 30 s wait below the two stay within 50 s.
        assert await asyncio.to_thread(working.wait, 20)
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
def test_cold_source_waiter_reuses_another_process_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    version = _allow_installed_git(monkeypatch)
    home = tmp_path / "home"
    source = _file_source(_origin(tmp_path))
    other = tmp_path / "other"
    other.mkdir()
    other_source = _file_source(_origin(other))
    source_id = source_identity(source.transport, source.normalized)
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import asyncio
                import ast
                import select
                import sys
                from pathlib import Path
                from metabrowser.cache import acquire
                from metabrowser.cache.urls import classify_root_argument

                if sys.argv[3]:
                    acquire.require_acquisition_git = lambda: ast.literal_eval(sys.argv[3])

                def phase(name):
                    if name == "reading the default branch":
                        print("staging", flush=True)
                        if not select.select([sys.stdin], [], [], 30)[0]:
                            raise TimeoutError("the waiting process did not resume acquisition")
                        if not sys.stdin.readline():
                            raise EOFError("the waiting process disappeared")

                answer = asyncio.run(
                    acquire.acquire_source(
                        classify_root_argument(sys.argv[1]), home=Path(sys.argv[2]), on_phase=phase
                    )
                )
                assert answer.fetched
                print(answer.store_key, flush=True)
                """
            ),
            source.normalized,
            str(home),
            repr(version) if required_admitted_git() is None else "",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert read_line(child).strip() == "staging"
        real_claim = acquire_module.source_acquisition_lock

        async def scenario() -> str:
            loop = asyncio.get_running_loop()
            busy = asyncio.Event()
            phases: list[str] = []
            notes: list[str] = []

            def observed_claim(
                home: Path, key: str, *, order: LockOrder | None = None
            ) -> CacheLock:
                try:
                    return real_claim(home, key, order=order)
                except LockBusyError:
                    if key == source_id:
                        loop.call_soon_threadsafe(busy.set)
                    raise

            monkeypatch.setattr(acquire_module, "source_acquisition_lock", observed_claim)
            cancelled = asyncio.create_task(acquire_source(source, home=home))
            await asyncio.wait_for(busy.wait(), CHILD_TIMEOUT)
            cancelled.cancel()
            with pytest.raises(asyncio.CancelledError):
                await cancelled

            busy.clear()
            waiting = asyncio.create_task(
                acquire_source(source, home=home, on_phase=phases.append, on_note=notes.append)
            )
            await asyncio.wait_for(busy.wait(), CHILD_TIMEOUT)
            independent = await asyncio.wait_for(
                acquire_source(other_source, home=home), CHILD_TIMEOUT
            )
            assert independent.fetched
            assert child.poll() is None
            assert not waiting.done()
            assert child.stdin is not None
            child.stdin.write("\n")
            child.stdin.flush()

            published = await asyncio.wait_for(waiting, CHILD_TIMEOUT)
            assert not published.fetched
            assert phases == []
            # PR #348 review A12: the wait is said once, not silent for up to its deadline.
            assert notes == [
                f"waiting for another Metabrowser process to finish acquiring {source.normalized}"
            ]
            assert independent.store_key != published.store_key
            return published.store_key

        store_key = asyncio.run(scenario())
        stdout, stderr = child.communicate(timeout=CHILD_TIMEOUT)
        assert child.returncode == 0, stderr
        assert stdout.strip() == store_key
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate(timeout=CHILD_TIMEOUT)
    assert list((home / "staging").iterdir()) == []
    assert held_locks() == ()


@requires_git
def test_acquisition_waits_for_the_home_lock_without_blocking_the_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A miss opens the cache under the home lock, then publishes, all off the loop."""

    _allow_installed_git(monkeypatch)
    home = tmp_path / "home"
    asyncio.run(acquire_source(_file_source(_origin(tmp_path)), home=home))
    other = tmp_path / "other"
    other.mkdir()
    other_source = _file_source(_origin(other))
    holder = _BoundedHolder(home, "locks.application_cache_lock(home)")
    try:

        async def scenario() -> str:
            waiting = asyncio.create_task(acquire_source(other_source, home=home))
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
    assert (home / "repository-stores" / store_key).is_dir()
    assert list((home / "staging").iterdir()) == []


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
    asyncio.run(acquire_source(_file_source(_origin(tmp_path)), home=home))
    other = tmp_path / "other"
    other.mkdir()
    other_source = _file_source(_origin(other))
    # Half the usual hold: the bound this test has always had on how long the
    # cancelled command may keep running, now kept by the child and not by a clock here.
    holder = _BoundedHolder(
        home, "locks.application_cache_lock(home)", hold_at_most=HOLD_AT_MOST / 2
    )
    try:

        async def scenario() -> None:
            waiting = asyncio.create_task(acquire_source(other_source, home=home))
            assert await _ticks_while_pending(waiting) == TICKS
            waiting.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiting

        asyncio.run(scenario())
        # ``asyncio.run`` has joined its executor and returned, and the child still
        # holds the lock: a wait that outlived the cancellation would have kept the
        # run from returning until the child gave up.
        assert holder.release() == "asked", "cancellation waited for the lock"
        assert held_locks() == ()
        # Python 3.14 logs an exception left in a shielded worker; an abandoned wait
        # must not leave one, or Ctrl-C prints a traceback.
        assert not [r for r in caplog.records if r.name == "asyncio"], caplog.text
    finally:
        holder.close()
    assert list((home / "staging").iterdir()) == []
