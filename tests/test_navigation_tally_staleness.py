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
import time

from metabrowser.inventory import InventoryIndex
from metabrowser.walker import FsEntry

PRESETS: list[tuple[str, list[str]]] = [("code", ["py", "js"])]
WINDOWS: list[tuple[str, float]] = [("24h", 86_400.0)]
LIMIT = 200


def _index_with(files: int) -> InventoryIndex:
    index = InventoryIndex()
    index.apply_walker_entries(
        [
            FsEntry.for_observed_file(
                path=f"f{i}.py", parent="", name=f"f{i}.py", size=1, mtime_ns=1
            )
            for i in range(files)
        ]
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

    index.apply_walker_entries(
        [FsEntry.for_observed_file(path="new.py", parent="", name="new.py", size=1, mtime_ns=1)]
    )
    assert index.rollup_revision() != before, "a write must move the revision"

    fresh = index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=60.0)
    assert fresh is not None, "a recent pass must be reused across a revision bump"


def test_an_old_pass_is_not_reused_once_the_revision_has_moved() -> None:
    """The bound is a bound -- but only for a revision that is moving."""
    index = _index_with(4)
    index.navigation_tallies_snapshotting(PRESETS, WINDOWS, LIMIT)
    index.apply_walker_entries(
        [FsEntry.for_observed_file(path="new.py", parent="", name="new.py", size=1, mtime_ns=1)]
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
