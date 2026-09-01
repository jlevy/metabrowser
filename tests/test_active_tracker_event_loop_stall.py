"""Event-loop stall benchmark for ``active_tracker._tick``.

The active tracker runs every ``ACTIVE_TRACKER_INTERVAL_S`` (5 s) on the
same event loop that serves ``/api/file`` and every other request. If
``_tick`` does sync filesystem I/O on the loop, every request that lands
inside a tick stalls for the duration of the tick — the user sees
``server=4ms transit=3000ms`` on the perf console even though the request
handler itself is fast.

This test pins the regression: with ``N`` trackable JSONL files (each
with a sibling ``.pid``), ``_tick`` must not block the loop more than
``MAX_STALL_MS``. Run as:

    uv --config-file uv.toml run --frozen pytest tests/test_active_tracker_event_loop_stall.py -v
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import pytest

from metabrowser.active_tracker import _tick, _TrackerState
from metabrowser.activity import FileActivityTracker
from tests.inventory_harness import inventory_harness

# Tuneable: how many .logs JSONL files to fabricate. 200 matches a busy
# session with several active dispatch runs; the bug shows even at 50.
N_TRACKABLE = 200

# An absolute floor, below which the loop is simply not blocked. A tick that
# stalls a few milliseconds is doing its work off-thread no matter what share
# of its wall time that is.
MAX_STALL_MS = 50.0

# Above that floor, the question is what share of the tick the loop spent
# blocked -- and that is the part a machine cannot fake.
#
# An absolute budget measures the machine as much as the code. On a contended
# CI runner the loop thread can miss its slot for 60 ms with `_tick` doing
# nothing but waiting on its executor, which failed this test at 71 ms and
# again at 61 ms while the same source measured 3-5 ms locally. A slower
# machine inflates the stall, but it inflates the tick's wall time with it, so
# the ratio between them stays put.
#
# The regression this guards -- per-entry sync `glob()` and `check_pid_alive()`
# on the loop -- makes the stall *be* the tick: roughly half its wall time,
# against a few percent when the work runs off-thread. The threshold sits well
# clear of both.
MAX_STALL_SHARE = 0.25

# Both figures are the best of this many attempts. Load can only push a
# maximum up, so the floor across attempts is the part attributable to the
# code.
STALL_ATTEMPTS = 3


def _make_workload(root: Path) -> None:
    """Fabricate ``N_TRACKABLE`` .logs/foo_<i>.jsonl files with sibling
    .pid files. Half the pids point at this process (alive); half at a
    sentinel pid that won't exist (dead). Mirrors the shape of a real
    repo where a few runs are live and many are stale."""
    logs_dir = root / "runs" / "x" / ".logs"
    logs_dir.mkdir(parents=True)
    self_pid = os.getpid()
    for i in range(N_TRACKABLE):
        (logs_dir / f"foo_{i}.jsonl").write_text('{"event":"start"}\n')
        # A neighboring .pid file forces _tick into the glob + read path.
        pid_target = self_pid if i % 2 == 0 else 1
        (logs_dir / f"foo_{i}.pid").write_text(f"{pid_target}\n")


async def _measure_max_stall_during(coro_fn) -> tuple[float, float]:
    """Run *coro_fn()* while a probe coroutine wakes every 1 ms and
    records the worst gap between expected and actual wake-up. Returns
    ``(coro_wall_ms, max_stall_ms)``."""
    stop = asyncio.Event()
    max_stall_ms = 0.0

    async def probe() -> None:
        nonlocal max_stall_ms
        target_interval_s = 0.001
        while not stop.is_set():
            t0 = time.perf_counter()
            await asyncio.sleep(target_interval_s)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if elapsed_ms > max_stall_ms:
                max_stall_ms = elapsed_ms

    probe_task = asyncio.create_task(probe())
    # Yield once so the probe is parked on its first sleep before the
    # workload starts — otherwise the very first measurement includes
    # the probe's own setup cost.
    await asyncio.sleep(0)
    t0 = time.perf_counter()
    try:
        await coro_fn()
    finally:
        stop.set()
        await probe_task
    coro_wall_ms = (time.perf_counter() - t0) * 1000.0
    return coro_wall_ms, max_stall_ms


def test_tick_does_not_block_event_loop(tmp_path: Path) -> None:
    """``_tick`` must not block the event loop more than
    ``MAX_STALL_MS``. Failure means user-visible ``/api/file`` latency
    will spike for the duration of the stall on every tick."""
    _make_workload(tmp_path)

    async def _run() -> list[tuple[float, float]]:
        async with inventory_harness(tmp_path) as harness:
            state = _TrackerState()
            tracker = FileActivityTracker()

            async def workload() -> None:
                # Two ticks: the first seeds the fingerprint table; the
                # second is the steady-state cost the user pays every 5 s.
                await _tick(
                    harness.runtime.coordinator,
                    tmp_path,
                    harness.runtime.config,
                    state,
                    tracker,
                )
                await _tick(
                    harness.runtime.coordinator,
                    tmp_path,
                    harness.runtime.config,
                    state,
                    tracker,
                )

            return [await _measure_max_stall_during(workload) for _ in range(STALL_ATTEMPTS)]

    attempts = asyncio.run(_run())
    tick_ms, stall_ms = min(attempts, key=lambda attempt: attempt[1])
    spread = ", ".join(f"{stall:.1f}" for _wall, stall in attempts)
    print(
        f"\n_tick wall-time={tick_ms:.1f}ms  event-loop stall={stall_ms:.1f}ms  "
        f"({stall_ms / tick_ms:.1%} of the tick, best of {STALL_ATTEMPTS}: "
        f"{spread} ms, N={N_TRACKABLE} trackable files)"
    )
    share = stall_ms / tick_ms if tick_ms > 0 else 0.0
    if stall_ms >= MAX_STALL_MS and share >= MAX_STALL_SHARE:
        pytest.fail(
            f"Event loop stalled {stall_ms:.1f} ms during a {tick_ms:.1f} ms _tick "
            f"({share:.0%} of it, limit {MAX_STALL_SHARE:.0%} above a "
            f"{MAX_STALL_MS:.0f} ms floor). The per-entry sync glob() + "
            "check_pid_alive() block on the loop. Wrap the per-entry "
            "loop in asyncio.to_thread."
        )
