"""The navigation tallies are recomputed on a bound, not on every request.

They cost one visit per entry in the index, and the memo they used to rely on
keys on ``rollup_revision()``, which advances on every index write -- roughly
ninety times a second at the walker's emit batch size. So while a walk ran, no
request could ever hit the memo and every root ``/api/tree`` repeated the pass:
measured at a median of 638 ms per request on a 300,000-file tree against 12 ms
once settled. See explorations/performance-loop/experiments/exp-003.
"""

from __future__ import annotations

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
# How long a thread waits for an event that only a hang would withhold. Not a budget:
# no assertion depends on how much of it elapsed.
_HANG_BREAKER_S = 10.0


def _aged(index: PythonInventoryStore, seconds: float) -> None:
    """Make the memoized pass *seconds* old, in place of sleeping until it is."""
    index._navigation_tally_at = time.monotonic() - seconds  # pyright: ignore[reportPrivateUsage]


def _move_revision(index: PythonInventoryStore) -> None:
    before = index.rollup_revision()
    index.apply_live_entry(
        FsEntry.for_observed_file(path="new.py", parent="", name="new.py", size=1, mtime_ns=1)
    )
    assert index.rollup_revision() != before, "a write must move the revision"


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
    _move_revision(index)

    fresh = index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=60.0)
    assert fresh is not None, "a recent pass must be reused across a revision bump"


def test_an_old_pass_is_not_reused_once_the_revision_has_moved() -> None:
    """The bound is a bound -- but only for a revision that is moving."""
    index = _index_with(4)
    index.navigation_tallies_snapshotting(PRESETS, WINDOWS, LIMIT)
    _move_revision(index)
    _aged(index, 3600.0)
    assert index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=60.0) is None


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
    _aged(index, 3600.0)
    assert (
        index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=0.0) is not None
    ), "a settled index must serve its memo rather than recomputing forever"


def test_the_bound_is_at_least_what_the_pass_cost() -> None:
    """A constant right at ten thousand files starves the loop at a million, so
    the bound is derived from the measured cost and the constant is its floor.

    The revision has to have moved: an unchanged one serves the memo whatever the
    bound, and this test would then pass with the cost left out of it.
    """
    index = _index_with(4)
    index.navigation_tallies_snapshotting(PRESETS, WINDOWS, LIMIT)
    _move_revision(index)
    # Stand in for a tree big enough that the pass is expensive.
    index._navigation_tally_cost_s = 30.0  # pyright: ignore[reportPrivateUsage]
    _aged(index, 10.0)
    assert (
        index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=0.0) is not None
    ), "a pass that cost 30 s must not be repeated 10 s later"
    _aged(index, 60.0)
    assert (
        index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=0.0) is None
    ), "past what the pass cost, a moved revision is a miss again"


def test_a_different_preset_shape_is_a_miss_not_a_wrong_answer() -> None:
    """The memo key carries the caller's bounds, so a second caller with a
    different shape gets its own pass rather than the first one's answer."""
    index = _index_with(4)
    index.navigation_tallies_snapshotting(PRESETS, WINDOWS, LIMIT)
    other = [("prose", ["md"])]
    assert index.navigation_tallies_fresh_within(other, WINDOWS, LIMIT, min_stale_s=60.0) is None


def test_a_freshness_probe_never_waits_for_an_in_flight_tally_pass() -> None:
    """A cache lookup on the request loop must not wait for worker-owned work.

    Ordered, not timed. The memo is warm, so the probe hits when the lock is free; a
    stand-in for the worker then holds the lock until the probe has returned. A probe
    that waited for the lock could only return after the stand-in gave up on it.
    """
    index = _index_with(4)
    index.navigation_tallies_snapshotting(PRESETS, WINDOWS, LIMIT)

    def probe() -> object:
        return index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=60.0)

    assert probe() is not None
    lock_acquired = threading.Event()
    probe_returned = threading.Event()
    released_after_probe: list[bool] = []

    def hold_tally_lock() -> None:
        with index._navigation_tally_lock:  # pyright: ignore[reportPrivateUsage]
            lock_acquired.set()
            released_after_probe.append(probe_returned.wait(_HANG_BREAKER_S))

    holder = threading.Thread(target=hold_tally_lock)
    holder.start()
    try:
        assert lock_acquired.wait(_HANG_BREAKER_S), "tally worker did not acquire its lock"
        during = probe()
    finally:
        probe_returned.set()
        holder.join(_HANG_BREAKER_S)

    assert not holder.is_alive()
    assert released_after_probe == [True], "the probe waited for the worker's lock"
    assert during is None, "a contended lock is a miss"
    assert probe() is not None


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
# until someone re-measures rather than passing silently. A provider read is
# several loop iterations, each of which can wait this long, so the batch stays
# inside the interpreter's 5 ms switch interval.
MAX_ENTRIES_BETWEEN_YIELDS = 256


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


class _CountingLock:
    """A lock that counts the threads waiting on it, so a test knows who has arrived."""

    def __init__(self) -> None:
        self._inner = threading.Lock()
        self._guard = threading.Lock()
        self.waiting = 0

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        if self._inner.acquire(blocking=False):
            return True
        if not blocking:
            return False
        with self._guard:
            self.waiting += 1
        try:
            return self._inner.acquire(True, timeout)
        finally:
            with self._guard:
                self.waiting -= 1

    def release(self) -> None:
        self._inner.release()

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, *_exc: object) -> None:
        self.release()


def _await(condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + _HANG_BREAKER_S
    while not condition():
        assert time.monotonic() < deadline, "a reader never arrived"
        time.sleep(0.001)


def test_readers_who_arrive_during_a_pass_share_the_next_one() -> None:
    """A burst of root-summary readers on a live tree costs two passes, not one each.

    After a walk, a moving revision makes the memo stale for every reader, so each one
    that found a pass running waited for it and then ran its own: the tree writes during
    every pass, so no two readers' images matched. On a 303,000-file tree with writes
    every 250 ms that put five identical root requests at about 3.2 s each
    (explorations/tree-summary-storm/README.md). Now readers that arrived during a pass
    share the one after it, whose image is newer than each of their arrivals, so every
    answer still counts every write made before its reader asked.
    """
    from metabrowser.inventory_engine.contract import (
        EntryQuery,
        NavigationProjection,
        NavigationQuery,
        ReadRequest,
    )

    index = _index_with(8)
    index._status = "done"  # pyright: ignore[reportPrivateUsage]
    lock = _CountingLock()
    index._navigation_tally_lock = lock  # pyright: ignore[reportPrivateUsage, reportAttributeAccessIssue]
    real_compute = index._compute_navigation_tallies  # pyright: ignore[reportPrivateUsage]
    passes: list[int] = []
    first_pass_running = threading.Event()
    release_first_pass = threading.Event()
    written = 0

    def write() -> None:
        nonlocal written
        written += 1
        index.apply_live_entry(
            FsEntry.for_observed_file(
                path=f"live{written}.py", parent="", name=f"live{written}.py", size=1, mtime_ns=1
            )
        )

    def live_pass(*args: object) -> object:
        passes.append(len(passes))
        # A live tree writes while every pass runs.
        write()
        if len(passes) == 1:
            first_pass_running.set()
            assert release_first_pass.wait(_HANG_BREAKER_S)
        return real_compute(*args)  # pyright: ignore[reportArgumentType]

    index._compute_navigation_tallies = live_pass  # type: ignore[method-assign]  # pyright: ignore[reportPrivateUsage]
    request = ReadRequest(
        queries=(EntryQuery(query_id="root", path=""), NavigationQuery(query_id="navigation"))
    )
    answers: dict[str, int] = {}

    def read(name: str, files_before: int) -> None:
        result = index._read_sync(request)  # pyright: ignore[reportPrivateUsage]
        navigation = result.projection("navigation")
        assert isinstance(navigation, NavigationProjection)
        summary = navigation.payload["summary"]
        assert isinstance(summary, dict)
        files = summary["files"]
        assert isinstance(files, int)
        assert files >= files_before, f"{name} was answered from before it asked"
        answers[name] = files

    first = threading.Thread(target=read, args=("first", 8))
    first.start()
    assert first_pass_running.wait(_HANG_BREAKER_S)
    readers = []
    for arrived, name in enumerate(("second", "third", "fourth"), start=1):
        # Each reader asks after another write, as root upserts arrive one by one.
        write()
        files_before = 8 + written
        thread = threading.Thread(target=read, args=(name, files_before))
        thread.start()
        _await(lambda arrived=arrived: lock.waiting == arrived)
        readers.append(thread)
    release_first_pass.set()
    for thread in (first, *readers):
        thread.join(_HANG_BREAKER_S)
        assert not thread.is_alive()

    assert sorted(answers) == ["first", "fourth", "second", "third"]
    assert len(passes) == 2, f"{len(passes)} passes for one burst of four readers"
