"""The navigation tallies are recomputed on a bound, not on every request.

They cost one visit per entry in the index, and the memo they used to rely on
keys on ``rollup_revision()``, which advances on every index write -- roughly
ninety times a second at the walker's emit batch size. So while a walk ran, no
request could ever hit the memo and every root ``/api/tree`` repeated the pass:
measured at a median of 638 ms per request on a 300,000-file tree against 12 ms
once settled. See explorations/performance-loop/experiments/exp-003.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from itertools import pairwise
from types import FrameType
from typing import overload

import pytest

from metabrowser.events import FsEntry
from metabrowser.inventory_engine.providers.python_inventory import (
    _PythonInventoryStore as PythonInventoryStore,
)

PRESETS: list[tuple[str, list[str]]] = [("code", ["py", "js"])]
WINDOWS: list[tuple[str, float]] = [("24h", 86_400.0)]
LIMIT = 200


def _index_with(files: int) -> PythonInventoryStore:
    index = PythonInventoryStore()
    for i in range(files):
        index.apply_live_entry(
            FsEntry.for_observed_file(
                path=f"f{i}.py", parent="", name=f"f{i}.py", size=1, mtime_ns=1
            )
        )
    return index


def test_a_cold_memo_reports_no_fresh_answer() -> None:
    """Nothing computed yet is a miss, not a stale hit of an empty result."""
    index = _index_with(4)
    assert index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=60.0) is None


def test_a_recent_pass_is_reused_though_the_revision_moved_on() -> None:
    """The point of the bound: a walk advances the revision constantly, and a
    revision test would miss every time."""
    index = _index_with(4)
    index.navigation_tallies_snapshotting(PRESETS, WINDOWS, LIMIT)
    before = index.rollup_revision()

    index.apply_live_entry(
        FsEntry.for_observed_file(path="new.py", parent="", name="new.py", size=1, mtime_ns=1)
    )
    assert index.rollup_revision() != before, "a write must move the revision"

    fresh = index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=60.0)
    assert fresh is not None, "a recent pass must be reused across a revision bump"


def test_an_old_pass_is_not_reused_once_the_revision_has_moved() -> None:
    """The bound is a bound -- but only for a revision that is moving."""
    index = _index_with(4)
    index.navigation_tallies_snapshotting(PRESETS, WINDOWS, LIMIT)
    index.apply_live_entry(
        FsEntry.for_observed_file(path="new.py", parent="", name="new.py", size=1, mtime_ns=1)
    )
    time.sleep(0.01)
    assert index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=0.0) is None


def test_a_settled_index_serves_the_memo_however_old_it_is() -> None:
    """An unchanged revision proves the memo current, so age has nothing to add.

    Gating on age here killed the fast path exactly where it should always hit.
    The timestamp is written only when the pass runs, so once a walk finished
    and the revision stopped moving, the memo aged past the bound and every
    later poll missed forever -- each paying a full index copy before
    discovering the revision had not moved.
    """
    index = _index_with(4)
    index.navigation_tallies_snapshotting(PRESETS, WINDOWS, LIMIT)
    # Older than any bound the route would ever ask for, revision untouched.
    index._navigation_tally_at = time.monotonic() - 3600.0  # pyright: ignore[reportPrivateUsage]
    assert (
        index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=0.0) is not None
    ), "a settled index must serve its memo rather than recomputing forever"


def test_the_bound_is_at_least_what_the_pass_cost() -> None:
    """A constant right at ten thousand files starves the loop at a million, so
    the bound is derived from the measured cost and the constant is its floor."""
    index = _index_with(4)
    index.navigation_tallies_snapshotting(PRESETS, WINDOWS, LIMIT)
    # Stand in for a tree big enough that the pass is expensive.
    index._navigation_tally_cost_s = 30.0  # pyright: ignore[reportPrivateUsage]
    time.sleep(0.01)
    assert (
        index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=0.0) is not None
    ), "a pass that cost 30 s must not be repeated 10 ms later"


def test_a_different_preset_shape_is_a_miss_not_a_wrong_answer() -> None:
    """The memo key carries the caller's bounds, so a second caller with a
    different shape gets its own pass rather than the first one's answer."""
    index = _index_with(4)
    index.navigation_tallies_snapshotting(PRESETS, WINDOWS, LIMIT)
    other = [("prose", ["md"])]
    assert index.navigation_tallies_fresh_within(other, WINDOWS, LIMIT, min_stale_s=60.0) is None


def test_a_freshness_probe_never_waits_for_an_in_flight_tally_pass() -> None:
    """A cache lookup on the request loop must not wait for worker-owned work."""
    index = _index_with(4)
    lock_acquired = threading.Event()

    def hold_tally_lock() -> None:
        with index._navigation_tally_lock:  # pyright: ignore[reportPrivateUsage]
            lock_acquired.set()
            time.sleep(0.35)

    holder = threading.Thread(target=hold_tally_lock)
    holder.start()
    assert lock_acquired.wait(1.0), "tally worker did not acquire its lock"

    async def scenario() -> tuple[float, float]:
        async def heartbeat() -> float:
            started = time.perf_counter()
            await asyncio.sleep(0.001)
            return (time.perf_counter() - started) * 1000.0

        heartbeat_task = asyncio.create_task(heartbeat())
        await asyncio.sleep(0)
        started = time.perf_counter()
        result = index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=60.0)
        call_ms = (time.perf_counter() - started) * 1000.0
        assert result is None
        return call_ms, await heartbeat_task

    try:
        call_ms, heartbeat_ms = asyncio.run(scenario())
    finally:
        holder.join(timeout=1.0)

    assert call_ms < 50.0
    assert heartbeat_ms < 50.0


class _TakenEntries(Sequence[FsEntry]):
    """A snapshot that knows how many entries a pass has taken from it so far."""

    def __init__(self, entries: list[FsEntry]) -> None:
        self._entries = entries
        self.taken = 0

    def __len__(self) -> int:
        return len(self._entries)

    @overload
    def __getitem__(self, index: int) -> FsEntry: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[FsEntry]: ...

    def __getitem__(self, index: int | slice) -> FsEntry | Sequence[FsEntry]:
        return self._entries[index]

    def __iter__(self) -> Iterator[FsEntry]:
        for entry in self._entries:
            self.taken += 1
            yield entry


# The most tally work a request on the loop can queue behind before the worker
# releases the GIL. It restates `_NAVIGATION_TALLY_COOPERATIVE_YIELD_BATCH`, where
# the measurement behind it is recorded, so raising that constant fails here
# until someone re-measures rather than passing silently.
MAX_ENTRIES_BETWEEN_YIELDS = 1_024


def test_worker_tally_pass_cooperatively_yields_to_the_event_loop() -> None:
    """Worker CPU must not depend on the interpreter's ordinary switch interval.

    The pass releases the GIL itself, with a timer-backed ``time.sleep``, every
    bounded number of entries. That cadence is the guarantee, so the test counts
    it: a profile hook on the thread running the pass notes how many entries had
    been taken at each sleep.

    An earlier version timed a 1 ms heartbeat on the loop during the pass and
    required it back within 50 ms. That measured how soon the OS scheduled the
    loop thread, which a busy host decides: it failed at 102 ms in a full-suite
    run and passed in isolation, and the batch was once halved to keep that
    heartbeat under budget on a contended CI runner. How many entries pass
    between yields does not depend on the host.

    The bound is entries, not time, so it assumes the per-entry work the
    constant was measured with. If the pass starts doing several times more per
    entry, this test still passes while the time between yields grows:
    re-measure `_NAVIGATION_TALLY_COOPERATIVE_YIELD_BATCH` rather than trusting
    it.
    """
    index = PythonInventoryStore()
    entry = FsEntry.for_observed_file(path="same.py", parent="", name="same.py", size=1, mtime_ns=1)
    snapshot = _TakenEntries([entry] * 5_000)
    yields_after: list[int] = []

    def profile(_frame: FrameType, event: str, arg: object) -> None:
        if event == "c_call" and arg is time.sleep:
            # The entry being taken when the pass yields is not yet processed.
            yields_after.append(snapshot.taken - 1)

    previous_profile: Callable[..., object] | None = sys.getprofile()
    sys.setprofile(profile)
    try:
        index.navigation_tallies(PRESETS, WINDOWS, LIMIT, entries=snapshot)
    finally:
        sys.setprofile(previous_profile)

    assert snapshot.taken == len(snapshot), "the pass must visit the whole snapshot"
    if len(yields_after) > 1 and yields_after[0] == len(snapshot) - 1:
        pytest.fail(
            "the tally pass took the whole snapshot before its first yield, so it "
            "materialized a copy before processing it; counting entries taken can no "
            "longer observe its progress between yields, so update this test to count "
            "per-entry work instead"
        )
    boundaries = [0, *yields_after, len(snapshot)]
    longest_run = max(later - earlier for earlier, later in pairwise(boundaries))
    assert longest_run <= MAX_ENTRIES_BETWEEN_YIELDS, (
        f"the tally pass processed {longest_run} entries without releasing the GIL "
        f"(limit {MAX_ENTRIES_BETWEEN_YIELDS}; it yielded {len(yields_after)} times over "
        f"{len(snapshot)} entries), so a request on the event loop waits on the "
        "interpreter's switch interval instead of on the pass"
    )


def test_the_snapshot_and_its_revision_are_read_together() -> None:
    """A memo keyed to a revision newer than its contents never gets evicted.

    ``navigation_tallies_snapshotting`` is the first call site that reads the
    index from a worker thread. Taking the snapshot and then the revision let
    the walker write in between, so the memo could be keyed to a revision newer
    than what it summarized -- and if that landed on the walk's final writes,
    the settled tree would serve under-counted tallies forever, because the
    revision never advances again to evict them.
    """
    index = _index_with(4)
    source = inspect.getsource(index.navigation_tallies_snapshotting)
    body = source.split('"""')[-1]
    lock_at = body.index("self._rollup_cache_lock")
    entries_at = body.index("self._entries.values()")
    revision_at = body.index("self._rollup_generation")
    assert lock_at < entries_at < revision_at, (
        "the snapshot and the revision must be read inside one lock acquisition"
    )
    # And the writers hold the same lock, which is what makes that meaningful.
    for writer in ("_replace_index_entry", "_pop_index_entry"):
        writer_source = inspect.getsource(getattr(index, writer))
        assert "self._rollup_cache_lock" in writer_source, f"{writer} no longer takes the lock"
