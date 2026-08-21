---
type: is
id: is-01m0hfnfd7vrpcq6d760ntd34c
title: Eviction-epoch guard has no test; invariant 5 is unenforced
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies: []
parent_id: is-01m0gfpa3nt74hvrnqbyqhn0ya
created_at: 2026-08-21T06:20:53.021Z
updated_at: 2026-08-21T18:31:15.643Z
closed_at: 2026-08-21T06:52:23.484Z
close_reason: null
---
arch-state-and-delivery.md lists ten invariants and says each has a test that fails when
it does not hold. Invariant 5 is: "An aggregate computed against data the walker has
moved past is discarded, not published."

Nothing tests it. The whole mechanism can be deleted and the suite stays green.

Verified by mutation on PR #59 at 40df198. Replacing the guarded merge in
InventoryIndex._merge_subtree_aggregates with an unconditional one:

    for directory_path, aggregate in memo.items():
        self._subtree_aggregates[directory_path] = aggregate

leaves 1164 passed, 1 skipped. The eviction-epoch machinery it guards
(_aggregate_epoch, _aggregate_evicted_at, the snapshot_epoch argument) is
therefore unenforced by the suite.

The mechanism is real, not redundant. Driving the documented race directly -- a rollup
pass that has already read a directory's children, with walker writes landing before the
pass merges -- produces a permanently wrong tally with the guard removed, and a correct
one with it:

    files written mid-rollup=1     folder reports 0    truth 1     STALE
    files written mid-rollup=5     folder reports 0    truth 5     STALE
    files written mid-rollup=50    folder reports 0    truth 50    STALE

It does not self-correct. Nothing evicts the directory again, so the folder keeps
reporting the stale total until something else happens to write beneath it.

A regression test should drive that shape: let a rollup pass read a directory's
children, land walker writes for that directory before the pass merges, then assert the
settled rollup equals a cold rollup derived from the same entries. Placing the interleave
matters -- gating before the read instead of after it does not reproduce the bug, because
_rollup_view hands out live views and the pass simply sees the newer data.

A working reproduction was written during review and can be adapted.
