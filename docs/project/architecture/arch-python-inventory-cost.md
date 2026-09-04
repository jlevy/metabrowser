# Python Inventory Cost

**Status:** Implemented and measured for the Python reference provider.
These numbers describe CPython and do not carry to another engine; a native provider
states its own.

The rule this document serves — what may run once per entry, and how to measure it — is
[the engine performance model](../../engine-performance-model.md).
This is the reference engine’s half: what the operations on its per-entry path actually
cost, what the walk therefore spends, and what is still on it.

## Unit Costs

Measured in isolation on Darwin 25.5.0, CPython 3.14, reproduced by
`explorations/performance-loop/scan_bench.py`. The right-hand column is the cost of
putting the operation on the per-entry path for one 300,000-entry tree, which is the
number that decides arguments:

| Operation | Cost | Once per entry, 300,000 entries |
| --- | --- | --- |
| `require_canonical_inventory_path` | 1.05 us | 315 ms |
| `InventoryEntry.for_observed_file`, including its two validations | 4.28 us | 1,284 ms |
| `_internal_entry`, contract entry to retained record | 1.85 us | 555 ms |
| `_semantic_entry`, retained record to contract entry | 4.67 us | 1,401 ms |
| `canonical_inventory_name`, nothing to escape | 0.16 us | 48 ms |
| `native_inventory_path`, nothing to unescape | 0.14 us | 42 ms |

Two things follow, and both are design constraints rather than observations.

**A construction costs roughly thirty validations.** Anything building a second object
per entry is the largest single item on the path.
This is why the walker yields the record the inventory retains rather than yielding a
contract type and converting it.

**Escaping on the way in beats escaping per row on the way out.** The store is keyed by
the canonical identity for correctness — see
[the provider contract](arch-inventory-provider.md) — and that also reduces
`_semantic_entry` to a field copy instead of three escapes on every row of every read.
Escaping happens once per entry at discovery instead of once per row per read.

## What the Boundary Cost Once

The provider refactor added `test_scanner_and_reducer_do_not_depend_on_browser_events`,
forbidding `walker.py` from importing `metabrowser.events`. The rule is right: the
scanner should not depend on the browser-delivery layer.

But `FsEntry`, the record the inventory retains, lived in `events.py` — for history, not
because it is an event.
Satisfying the rule therefore meant the walker yielded the contract’s `InventoryEntry`,
which validates its path and its parent on construction, and the provider converted it
back to `FsEntry` anyway.
That is one extra construction and two extra validations for every entry in the tree,
about 6.25 us each, and every individual piece of it was correct, which is why it
survived review.

`FsEntry` and `WriteToken` now live in `metabrowser.fs_record`, which is neither the
scanner nor the browser layer, and `events.py` re-exports them so no importer changed.
The walker builds the retained record directly.
The test still passes and now means what it says.

The generalizable half of this is in
[the engine performance model](../../engine-performance-model.md#the-per-entry-rule);
the worked numbers are below.

## What the Walk Does Per Entry

Counted in process over a 61,105-entry corpus, `main` against this provider, before and
after the change above.
Counts rather than times, because the host was under heavy load throughout and counts do
not care:

|  | `main` | before | after |
| --- | --- | --- | --- |
| `os.scandir` | 2,210 | 2,210 | 2,210 |
| `os.lstat` | 1,111 | 1,139 | 1,139 |
| `FsEntry.__init__` | 125,525 | 125,525 | 125,525 |
| `InventoryEntry.__init__` | 0 | 62,210 | 0 |
| `_internal_entry` | 0 | 62,210 | 62,210 (pass-through) |
| `require_canonical_inventory_path` | 0 | 248,826 | 124,406 |

The filesystem work is identical in all three columns, which is the check that says the
difference is language work rather than I/O.

Attributing the validator calls to their callers splits them in half, and the halves
have different causes:

| Caller | Per entry |
| --- | --- |
| `InventoryEntry.for_observed_file` | 1.96 |
| `_record_provider_change` | 1.02 |
| `coordinator._merge_provider_batches` | 1.02 |

The first half is entry construction and is gone.
The second half is the change pipeline.

## What Is Still on the Path

`_record_provider_change` and `coordinator._merge_provider_batches` each construct a
validated contract object for every entry discovered, to publish invalidations for
entries no reader has seen — about 2.1 us per entry.
`main` had no equivalent during its boot walk, because it had no change pipeline to
feed.

Suppressing publication during discovery is a change to the delivery contract rather
than a local optimization: a consumer attaching mid-walk has to be told what it missed,
which is [state and delivery](arch-state-and-delivery.md)’s subject.
It is tracked as its own item rather than folded into a performance change.

## References

- [Engine performance model](../../engine-performance-model.md) — the rule and the
  measurement discipline, which outlive this engine
- [Inventory provider contract](arch-inventory-provider.md) — the boundary these types
  cross, and why the store is keyed by the canonical identity
- [State and delivery](arch-state-and-delivery.md) — what the change pipeline owes a
  consumer
- [exp-024](../../../explorations/performance-loop/experiments/exp-024-the-refactor-added-a-rule-that-forced-a-second-build.md)
  — the round these numbers come from

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
