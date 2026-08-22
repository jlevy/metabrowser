"""The navigation tallies are recomputed on a bound, not on every request.

They cost one visit per entry in the index, and the memo they used to rely on
keys on ``rollup_revision()``, which advances on every index write -- roughly
ninety times a second at the walker's emit batch size. So while a walk ran, no
request could ever hit the memo and every root ``/api/tree`` repeated the pass:
measured at a median of 638 ms per request on a 300,000-file tree against 12 ms
once settled. See explorations/performance-loop/experiments/exp-003.
"""

from __future__ import annotations

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


def test_an_old_pass_is_not_reused() -> None:
    """The bound is a bound. Zero staleness allowed means always recompute."""
    index = _index_with(4)
    index.navigation_tallies_snapshotting(PRESETS, WINDOWS, LIMIT)
    time.sleep(0.01)
    assert index.navigation_tallies_fresh_within(PRESETS, WINDOWS, LIMIT, min_stale_s=0.0) is None


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
