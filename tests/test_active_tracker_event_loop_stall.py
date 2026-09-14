"""``active_tracker._tick`` keeps its filesystem probes off the event loop.

The active tracker runs every ``ACTIVE_TRACKER_INTERVAL_S`` (5 s) on the
same event loop that serves ``/api/file`` and every other request. If
``_tick`` does sync filesystem I/O on the loop, every request that lands
inside a tick stalls for the duration of the tick — the user sees
``server=4ms transit=3000ms`` on the perf console even though the request
handler itself is fast.

The guarantee has two halves, and this test observes each without timing it.

- **The probes run elsewhere.** A profile hook on the loop thread records every
  call to the blocking primitives the tick's probes reduce to, and the ticks
  must make none of them there.
- **The loop stays free while they do.** The tick's off-loop work asks the loop
  to run a callback and waits for the answer. Only a loop that is not blocked,
  for example waiting on that same worker, can answer.

An earlier version timed the stall instead, and each refinement of that
measurement still measured the machine. A 50 ms budget failed at 52-74 ms under
full-suite and CI load and at 199.8 ms on a cold first run; the best of three
attempts failed again on CI at 61 ms; and the share-of-tick gate that followed
assumed the loop thread and its workers slow down together. Timing was also
blind to the cheaper half of the regression: moving only the ``stat`` pass
back onto the loop stalled it 4.6 ms and passed. Where a call runs, and
whether the loop can answer, do not depend on how fast anything is. Run as:

    uv --config-file uv.toml run --frozen pytest tests/test_active_tracker_event_loop_stall.py -v
"""

from __future__ import annotations

import asyncio
import functools
import io
import os
import sys
import threading
import time
import types
from collections import Counter
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import FrameType
from typing import Any

import pytest

import metabrowser.active_tracker as active_tracker
from metabrowser.active_tracker import _ACTIVITY_LABEL, _read_candidates, _tick, _TrackerState
from metabrowser.activity import ActivityPoll, FileActivityTracker
from metabrowser.inventory_engine.overlay import InventoryDecorationPatch
from metabrowser.inventory_engine.runtime import default_inventory_config
from tests.inventory_harness import inventory_harness

# 200 matches a busy session with several active dispatch runs.
N_TRACKABLE = 200

# The watcher is off so the tick is the only work on the loop while it is
# observed; the files are fabricated before the harness opens.
_WATCH_OFF = replace(default_inventory_config(), watch_mode="off")

# How long off-loop tick work waits for the loop to run one callback. It breaks
# the deadlock a blocked loop would otherwise cause and is not a latency budget:
# a free loop answers as soon as the OS schedules it.
LOOP_ANSWER_DEADLINE_S = 5.0

# The C functions blocking work reduces to: ``Path.stat`` and ``Path.exists``
# call ``os.stat``, ``Path.glob`` calls ``os.scandir``, ``Path.read_text`` calls
# ``io.open``, a liveness check calls ``os.kill``, and waiting on a child calls
# ``os.waitpid``. They are matched by identity, so an alias bound at import time
# -- the glob module keeps its own reference to ``os.scandir`` -- is still the
# same call.
_BLOCKING_PRIMITIVES: dict[int, str] = {
    id(function): name
    for name, function in (
        ("os.stat", os.stat),
        ("os.lstat", os.lstat),
        ("os.scandir", os.scandir),
        ("os.listdir", os.listdir),
        ("os.access", os.access),
        ("os.readlink", os.readlink),
        ("os.open", os.open),
        ("io.open", io.open),
        ("os.kill", os.kill),
        ("os.waitpid", os.waitpid),
        ("time.sleep", time.sleep),
    )
}

# (primitive, calling function, file:line)
type _CallSite = tuple[str, str, str]


def _make_workload(root: Path) -> None:
    """Fabricate ``N_TRACKABLE`` .logs/foo_<i>.jsonl files with sibling .pid files.

    Even-numbered pid files name this process and odd-numbered ones name pid 1,
    which an unprivileged process cannot signal, so both liveness answers are on
    disk. Which pid file labels a given log is the tracker's choice, so the tests
    assert only that every log got a label.
    """
    logs_dir = root / "runs" / "x" / ".logs"
    logs_dir.mkdir(parents=True)
    self_pid = os.getpid()
    for i in range(N_TRACKABLE):
        (logs_dir / f"foo_{i}.jsonl").write_text('{"event":"start"}\n')
        # A neighboring .pid file forces _tick into the glob + read path.
        pid_target = self_pid if i % 2 == 0 else 1
        (logs_dir / f"foo_{i}.pid").write_text(f"{pid_target}\n")


@contextmanager
def _blocking_calls_on_this_thread() -> Generator[Counter[_CallSite]]:
    """Count blocking primitive calls made by the current thread, by call site.

    ``sys.setprofile`` installs the hook for the calling thread only, so work
    handed to ``asyncio.to_thread`` is invisible to it by construction. Installed
    on the event-loop thread, every count is a call that blocked the loop.
    """

    calls: Counter[_CallSite] = Counter()

    def profile(frame: FrameType, event: str, arg: object) -> None:
        if event == "c_call":
            name = _BLOCKING_PRIMITIVES.get(id(arg))
            if name is not None:
                code = frame.f_code
                site = f"{os.path.basename(code.co_filename)}:{frame.f_lineno}"
                calls[(name, code.co_qualname, site)] += 1

    previous: Callable[..., object] | None = sys.getprofile()
    sys.setprofile(profile)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def _describe(calls: Counter[_CallSite]) -> str:
    return "; ".join(
        f"{count}x {primitive} in {function} ({site})"
        for (primitive, function, site), count in calls.most_common(8)
    )


class _LoopRendezvous:
    """Off-loop work proves the event loop is free by having it run a callback."""

    def __init__(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._loop_thread = threading.get_ident()
        self.answered: list[str] = []
        self.unanswered: list[str] = []

    def check(self, work: str) -> None:
        if threading.get_ident() == self._loop_thread:
            self.unanswered.append(f"{work} ran on the event-loop thread")
            return
        if self.unanswered:
            # Already failing; do not wait out another deadline.
            return
        answered = threading.Event()
        self._loop.call_soon_threadsafe(answered.set)
        if answered.wait(LOOP_ANSWER_DEADLINE_S):
            self.answered.append(work)
        else:
            self.unanswered.append(
                f"the loop ran no callback for {LOOP_ANSWER_DEADLINE_S:.0f} s while {work} "
                "ran off it, so it was blocked waiting"
            )


class _RendezvousTracker(FileActivityTracker):
    def __init__(self, rendezvous: _LoopRendezvous) -> None:
        super().__init__()
        self._rendezvous = rendezvous

    def poll_observations(self, paths: list[Path]) -> ActivityPoll:
        poll = super().poll_observations(paths)
        self._rendezvous.check("poll_observations")
        return poll


def test_the_probe_detector_sees_every_tick_probe(tmp_path: Path) -> None:
    """The detector would see the tick's probes if they ran on its thread.

    The tick runs here with its thread hops made inline, so whatever probes it
    really makes, through whichever helpers, land on the hooked thread. Each hop
    must show at least one detected call per log. Without this, a probe
    rewritten onto a primitive the detector does not know would pass the real
    test vacuously.
    """
    _make_workload(tmp_path)
    hop_calls: Counter[str] = Counter()

    async def run() -> Counter[_CallSite]:
        async with inventory_harness(tmp_path, config=_WATCH_OFF) as harness:
            with _blocking_calls_on_this_thread() as calls:

                async def inline[T](
                    function: Callable[..., T], /, *args: object, **kwargs: object
                ) -> T:
                    before = calls.total()
                    try:
                        return function(*args, **kwargs)
                    finally:
                        hop = getattr(function, "__name__", repr(function))
                        hop_calls[hop] += calls.total() - before

                inline_asyncio = types.ModuleType("asyncio")
                vars(inline_asyncio).update(vars(asyncio))
                inline_asyncio.to_thread = inline  # pyright: ignore[reportAttributeAccessIssue]
                with pytest.MonkeyPatch.context() as patch:
                    patch.setattr(active_tracker, "asyncio", inline_asyncio)
                    await _tick(
                        harness.runtime.coordinator,
                        tmp_path,
                        harness.runtime.config,
                        _TrackerState(),
                        FileActivityTracker(),
                    )
            return calls

    calls = asyncio.run(run())
    assert hop_calls, "the tick handed no work off the loop"
    for hop, count in hop_calls.items():
        assert count >= N_TRACKABLE, (
            f"the detector saw {count} blocking call(s) while {hop} probed {N_TRACKABLE} "
            f"logs, so a probe uses a primitive it does not know: {_describe(calls)}"
        )


def test_tick_does_not_block_event_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``_tick`` must neither block the event loop nor make it wait on its probes.

    Failure means user-visible ``/api/file`` latency will spike for the
    duration of the probes on every tick.
    """
    _make_workload(tmp_path)

    async def _run() -> tuple[Counter[_CallSite], _LoopRendezvous, dict[str, str | None]]:
        rendezvous = _LoopRendezvous()
        real_compute_updates = active_tracker._compute_updates

        @functools.wraps(real_compute_updates)
        def compute_updates(**kwargs: Any) -> dict[str, InventoryDecorationPatch]:
            patches = real_compute_updates(**kwargs)
            rendezvous.check("_compute_updates")
            return patches

        monkeypatch.setattr(active_tracker, "_compute_updates", compute_updates)
        async with inventory_harness(tmp_path, config=_WATCH_OFF) as harness:
            coordinator = harness.runtime.coordinator
            runtime_config = harness.runtime.config
            state = _TrackerState()
            tracker = _RendezvousTracker(rendezvous)
            with _blocking_calls_on_this_thread() as loop_calls:
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
            return loop_calls, rendezvous, labels

    loop_calls, rendezvous, labels = asyncio.run(_run())

    # The probes did run -- somewhere. Every JSONL log carries a pid label only
    # a glob, a read, and a liveness check can produce.
    assert len(labels) == N_TRACKABLE
    assert None not in labels.values(), labels
    assert set(labels.values()) <= {"0", "1"}, labels
    assert not loop_calls, (
        f"_tick made {sum(loop_calls.values())} blocking call(s) on the event-loop thread: "
        f"{_describe(loop_calls)}. Run them through asyncio.to_thread."
    )
    assert not rendezvous.unanswered, "; ".join(rendezvous.unanswered)
    assert set(rendezvous.answered) == {"poll_observations", "_compute_updates"}, (
        rendezvous.answered
    )
