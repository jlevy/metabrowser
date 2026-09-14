"""``active_tracker._tick`` keeps its filesystem probes off the event loop.

The active tracker runs every ``ACTIVE_TRACKER_INTERVAL_S`` (5 s) on the
same event loop that serves ``/api/file`` and every other request. If
``_tick`` does sync filesystem I/O on the loop, every request that lands
inside a tick stalls for the duration of the tick — the user sees
``server=4ms transit=3000ms`` on the perf console even though the request
handler itself is fast.

The guarantee is about *where* the probes run, so that is what this test
observes. A profile hook on the loop thread records every call to the
filesystem primitives the tick's probes reduce to, and the test asserts the
loop thread made none of them while the ticks still did their probing.

An earlier version timed the stall instead, and each refinement of that
measurement still measured the machine. A 50 ms budget failed at 52-74 ms under
full-suite and CI load and at 199.8 ms on a cold first run; the best of three
attempts failed again on CI at 61 ms; and the share-of-tick gate that followed
assumed the loop thread and its workers slow down together. Timing was also
blind to the cheaper half of the regression: moving only the ``stat`` pass
back onto the loop stalled it 4.6 ms and passed. Where a call runs does not
depend on how fast anything is. Run as:

    uv --config-file uv.toml run --frozen pytest tests/test_active_tracker_event_loop_stall.py -v
"""

from __future__ import annotations

import asyncio
import io
import os
import sys
from collections import Counter
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import FrameType

from metabrowser.active_tracker import (
    _ACTIVITY_LABEL,
    _pid_label,
    _read_candidates,
    _tick,
    _TrackerState,
)
from metabrowser.activity import FileActivityTracker
from metabrowser.inventory_engine.runtime import default_inventory_config
from tests.inventory_harness import inventory_harness

# 200 matches a busy session with several active dispatch runs.
N_TRACKABLE = 200

# The C functions the tick's probes reduce to: ``Path.stat`` and
# ``Path.exists`` call ``os.stat``, ``Path.glob`` calls ``os.scandir``,
# ``Path.read_text`` calls ``io.open``, and a liveness check calls ``os.kill``.
# They are matched by identity, so an alias bound at import time -- the glob
# module keeps its own reference to ``os.scandir`` -- is still the same call.
_FILESYSTEM_PRIMITIVES: dict[int, str] = {
    id(function): name
    for name, function in (
        ("os.stat", os.stat),
        ("os.lstat", os.lstat),
        ("os.scandir", os.scandir),
        ("os.listdir", os.listdir),
        ("os.open", os.open),
        ("io.open", io.open),
        ("os.kill", os.kill),
    )
}


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


@contextmanager
def _filesystem_calls_on_this_thread() -> Generator[Counter[str]]:
    """Count filesystem primitive calls made by the current thread.

    ``sys.setprofile`` installs the hook for the calling thread only, so work
    handed to ``asyncio.to_thread`` is invisible to it by construction. Installed
    on the event-loop thread, every count is a call that blocked the loop.
    """

    calls: Counter[str] = Counter()

    def profile(_frame: FrameType, event: str, arg: object) -> None:
        if event == "c_call":
            name = _FILESYSTEM_PRIMITIVES.get(id(arg))
            if name is not None:
                calls[name] += 1

    previous: Callable[..., object] | None = sys.getprofile()
    sys.setprofile(profile)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def test_the_probe_detector_sees_every_tick_probe(tmp_path: Path) -> None:
    """The detector below would see the tick's probes if they ran on its thread.

    Without this, a probe rewritten onto a primitive the detector does not know
    would pass the real test vacuously.
    """
    _make_workload(tmp_path)
    tracker = FileActivityTracker()
    jsonl = tmp_path / "runs" / "x" / ".logs" / "foo_0.jsonl"

    with _filesystem_calls_on_this_thread() as calls:
        tracker.poll_observations([jsonl])
        label = _pid_label(jsonl, tracker)

    assert label == "1"
    assert {"os.stat", "os.scandir", "io.open", "os.kill"} <= calls.keys(), calls


def test_tick_does_not_block_event_loop(tmp_path: Path) -> None:
    """``_tick`` must make no filesystem call on the event-loop thread.

    Failure means user-visible ``/api/file`` latency will spike for the
    duration of the probes on every tick.
    """
    _make_workload(tmp_path)
    # The watcher is off so the tick is the only work on the loop while it is
    # observed; the files are fabricated before the harness opens.
    config = replace(default_inventory_config(), watch_mode="off")

    async def _run() -> tuple[Counter[str], dict[str, str | None]]:
        async with inventory_harness(tmp_path, config=config) as harness:
            coordinator = harness.runtime.coordinator
            runtime_config = harness.runtime.config
            state = _TrackerState()
            tracker = FileActivityTracker()
            with _filesystem_calls_on_this_thread() as loop_calls:
                # Two ticks: the first seeds the fingerprint table; the
                # second is the steady-state cost the user pays every 5 s.
                await _tick(coordinator, tmp_path, runtime_config, state, tracker)
                await _tick(coordinator, tmp_path, runtime_config, state, tracker)
            records, decorations = await _read_candidates(
                coordinator,
                config=runtime_config,
                root=tmp_path,
            )
            labels = {
                record.path: dict(decorations[record.path].labels).get(_ACTIVITY_LABEL)
                if record.path in decorations
                else None
                for record in records
                if record.path.endswith(".jsonl")
            }
            return loop_calls, labels

    loop_calls, labels = asyncio.run(_run())

    # The probes did run -- somewhere. Every JSONL log carries the pid label
    # only a glob, a read, and a liveness check can produce.
    assert len(labels) == N_TRACKABLE
    assert set(labels.values()) == {"1"}, labels
    assert not loop_calls, (
        f"_tick made {sum(loop_calls.values())} filesystem call(s) on the event-loop "
        f"thread ({dict(loop_calls)}). The per-entry stat, glob() and "
        "check_pid_alive() probes block the loop; run them through asyncio.to_thread."
    )
