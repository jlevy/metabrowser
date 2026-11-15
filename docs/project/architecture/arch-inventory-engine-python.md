# Python Inventory Engine

**Status:** Built. The only provider this build registers (`InventoryProvider.PYTHON`),
in `inventory_engine/providers/python_inventory.py`, `walker.py`, and
`watch_backends.py`. The unit costs below were measured on CPython; a native provider
documents its own in a sibling document.

This is the only engine-specific architecture document.
What every provider guarantees is in the
[Inventory Provider Contract](arch-inventory-provider.md), and nothing above that
contract depends on what is written here.
When another provider ships, its engine document joins this one and the contract’s
status line names it.

`PythonInventoryBackend.open` returns a `_PythonInventoryStore`, which implements
`InventoryHandle` directly.
The store is private: it owns walking, watching, the retained index, aggregate caches,
and read projection for one root.

## Discovery

`walk_tree` in `walker.py` discovers the tree:

- **Strict level order.** The queue is FIFO, so every directory at depth N is scanned
  before any at depth N+1, and the shallow layers the navigation tree shows are complete
  early
  (`tests/test_browser_inventory.py::test_walk_tree_discovers_strictly_in_level_order`).
- **One `os.scandir` per directory and one stat per file.** `_scandir_visible` is the
  walker’s only filesystem access.
  Symlinks are not followed; sockets, FIFOs, and devices are excluded; and names that
  start with `.` are pruned unless they are in the configured `hidden_allowlist`.
- **Ignore state.** `build_gitignore_check` (`tree.py`) builds one checker per root and
  caches it, and a child of an ignored directory inherits the flag without matching
  again. So editing a `.gitignore` does not re-flag entries already indexed until they
  are rewritten.
- **Post-order finalize.** A directory’s totals are written only after every descendant
  has been walked, so a large root has no totals of its own until the walk ends; until
  then it is a placeholder with null aggregates.
- **The budget.** Discovery stops at `max_files` (`INVENTORY_MAX_FILES`). The store then
  stops its watcher, reports `stopped` with a `resource_budget` issue, and leaves
  unscanned directories pending: the end-of-walk repair is skipped, because descendant
  counts are incomplete and a repaired total would be wrong.
- **Delivery.** `_run_walker` groups stored entries into changes of `WALKER_EMIT_BATCH`
  ops, so the first walk produces a bounded number of change batches rather than one per
  file.

How long a walk takes depends on the tree and the filesystem, slower on network mounts;
measured scan times are in [Scale Benchmark](../../scale-benchmark.md).

## The Watcher

`run_watcher` in `watch_backends.py` is the store’s observer.
`PythonInventoryBackend.open` starts it and waits until it is installed or has failed
before the walk begins, so no path is scanned before the watch boundary exists.

- **Backend selection.** `select_watch_mode` reads the root’s filesystem type, from
  `/proc/self/mountinfo` on Linux and `mount(8)` on macOS. Types in `_NATIVE_FS_TYPES`
  get `watchfiles`’ native driver (inotify, FSEvents, or kqueue); types in
  `_POLLING_FS_TYPES`, network and FUSE mounts where native watches miss remote writes,
  get polling. A type it cannot detect polls too, and an unrecognized one polls with a
  warning naming it, so the failure mode is late rather than never.
- **Batching.** `watchfiles.awatch` groups changes and yields a batch once no new change
  arrives within its `step`, or after at most its `debounce`; Metabrowser uses the
  library defaults. Polling adds the poll delay `run_watcher` sets.
- **The default filter.** `awatch` applies `watchfiles.DefaultFilter`, which drops
  changes under directories such as `node_modules`, `__pycache__`, `.git`, and `.venv`,
  and editor and bytecode files such as `*.pyc`, `*.swp`, and `*~`. The walker indexes
  `node_modules` and `__pycache__`, so changes there are not seen live; they appear when
  a rewalk of an enclosing directory reaches them, or on the next open.
- **Normalization.** `_observations_for_batch` maps each path into the root, drops the
  root itself and anything under a hidden segment, keeps one observation per path, and
  escapes the path to its canonical identity.
  `_emit_batch` submits observations in chunks of at most `MAX_COMMAND_PATHS` through
  `refresh()`, which stats each path before applying it.
- **Failure.** A backend error, an exhausted inotify watch limit among them, or a
  receipt that does not accept every observation ends observation.
  The watcher reports `failed`; the store marks freshness stale with an
  `observation_gap` issue.
  Nothing retries it.
- **Stopping.** Cancellation sets a cooperative stop event and joins the consumer until
  it has left `awatch`, rather than abandoning the Rust-backed iterator, which could
  race event-loop teardown on free-threaded Python.

A refreshed path that is a directory, a newly created one included, is ingested by
`rewalk_subtree`, which walks that directory’s subtree.
`prioritize()` schedules a bounded rewalk of unknown paths in a background task and is
inert after the budget stop.

## Concurrency and the Interpreter Lock

**One writer.** The walker, watcher refreshes, and subtree rewalks write on the asyncio
event loop and yield only at explicit `await` points.
The activity tracker writes the coordinator’s overlay, never provider entries.

**Reads run off the loop.** `read()` runs `_read_sync` through `asyncio.to_thread`.
`_capture_image` takes an immutable image of the entries, version, and state under
`_rollup_cache_lock`, and the projection runs on that image, so a projection cannot mix
generations. Any read from a worker thread takes that lock.
Under the GIL a `list(dict.values())` does not tear, but the version has to be read with
the snapshot it describes, and a free-threaded build would make the lock necessary for
the read itself. `navigation_tallies_snapshotting` reads entries and revision in one
acquisition for both reasons
(`tests/test_navigation_tally_staleness.py::test_the_snapshot_and_its_revision_are_read_together`).

**Threads buy queueing, not parallelism.** The application sizes the default executor
with `DEFAULT_EXECUTOR_WORKERS`. Under the GIL a rollup on a worker competes with the
walker on the loop rather than running beside it, so the way to keep requests responsive
is to make each one cheap, not to move it to a thread.

**Cooperative yields.** The walker, the navigation tally pass, and the catalog pass each
sleep briefly after a bounded number of entries.
A pass that never releases the GIL is served by the interpreter’s forced switch instead,
so every loop iteration would wait up to the switch interval while it runs, and a
provider read through the coordinator takes several loop iterations.
The batch sizes are the `_*_COOPERATIVE_YIELD_BATCH` constants in `python_inventory.py`,
each with the measurement that set it, and `tests/test_navigation_tally_staleness.py`
and `tests/test_inventory_walk_work.py` count entries between yields.

**Two synchronization points.**

- `_rollup_cache_lock` guards `_entries` and every structure derived from it.
  It is held for dictionary operations only, never across an `await` or a rollup
  reduction.
- An **eviction epoch** covers the one concurrent case.
  A rollup runs on a worker while the walker keeps writing, so an aggregate computed
  from what the worker read can finish after a write has invalidated it.
  Each pass computes into a private map and merges under the lock, keeping only
  directories nothing evicted since the pass began
  (`tests/test_browser_rollup.py::test_aggregate_computed_against_moved_data_is_never_published`).

`_navigation_tally_lock` is held across the whole tally pass, so simultaneous askers
share one pass instead of running the same aggregation once each.

## Retained State

`_entries` maps each canonical path to its retained `FsEntry` (`fs_record.py`), and
everything else in the store is derived from it and rebuildable from it
(`tests/test_browser_rollup.py::test_derived_index_state_survives_writes_and_removals`).
Every write goes through `_replace_index_entry` or `_pop_index_entry`, which keep the
derived structures in step and advance the version; a scan of the source fails the build
on any other write
(`tests/test_browser_rollup.py::test_every_index_write_goes_through_the_two_write_methods`),
and test fixtures use `conftest.SyntheticIndexWriter` for the same reason.

| Structure | Holds | Invalidated by |
| --- | --- | --- |
| `_children_index` | parent path to children | The write itself, in place |
| `_subtree_aggregates` | directory to subtree aggregate | Eviction of the changed path’s ancestor chain |
| `_aggregate_evicted_at` | directory to eviction epoch | Released once no rollup pass is in flight |
| `_descendant_file_counts` and siblings | running per-directory totals | Adjusted per write |
| `_pending_dirs` | directories awaiting finalize | Post-order finalize, or the end-of-walk repair |
| `_navigation_tally_memo` | the index-wide tallies and sorted modification times | A moving revision older than the refresh bound |
| `_navigation_read_memo` | one coherent root-entry and navigation read boundary | The same bound; root replacement clears it |
| `_page_memos` | complete projections with another page to serve | Consumption, or eviction past `_PAGE_MEMO_CAPACITY` |
| `_change_history` | recent change batches for resumption | Bounded by the configured change-queue size |

- **The children index is maintained**, so a rollup or tree expansion reads only the
  buckets on its own path.
- **Subtree aggregates are evicted, not rebuilt.** A write drops the changed path and
  its ancestors; sibling subtrees stay valid, so a rollup recomputes only what moved.
  Eviction walks the whole ancestor chain, recording an epoch even for a directory that
  holds no aggregate, because a pass in flight may be about to publish one.
  The epoch map is released when no pass is in flight, so it does not grow with every
  directory path seen in a long session over a churning tree.
- **The root summary is retained as a coherent boundary.** While the revision moves, a
  repeated root-summary read may reuse the memo until the greater of
  `_NAVIGATION_TALLY_REFRESH_FLOOR_S` and the last pass’s cost has elapsed, returning
  the memo’s own version and state.
  On a settled revision the memo is reused however old it is.
  Recency rows are answered from the memo’s sorted modification times by binary search
  at the request’s observation time, so the memo has no clock term.
- **Versions** come from one process-wide sequence, `_ROLLUP_REVISIONS`, with a session
  identity per store, so a tag never repeats for different content across roots or
  handles.
- **Continuations** are retained in `_page_memos`, bounded by `_PAGE_MEMO_CAPACITY` and
  `MAX_ASSEMBLED_ROWS`. A page consumes its single-use cursor, and eviction raises
  `VersionUnavailableError`.
- **Change history** is bounded by the change-queue size; a cursor older than the
  history, or from another session, gets a reset.

## Unit Costs

Measured in isolation on Darwin 25.5.0 with CPython 3.14 by
`explorations/performance-loop/scan_bench.py`, as recorded in
[exp-026](../../../explorations/performance-loop/experiments/exp-026-the-refactor-added-a-rule-that-forced-a-second-build.md).
The right-hand column is the cost of putting the operation on the per-entry path for one
300,000-entry tree:

| Operation | Cost | Once per entry, 300,000 entries |
| --- | --- | --- |
| `require_canonical_inventory_path` | 1.05 us | 315 ms |
| `InventoryEntry.for_observed_file`, including its two validations | 4.28 us | 1,284 ms |
| `_internal_entry`, contract entry to retained record | 1.85 us | 555 ms |
| `_semantic_entry`, retained record to contract entry | 4.67 us | 1,401 ms |
| `canonical_inventory_name`, nothing to escape | 0.16 us | 48 ms |
| `native_inventory_path`, nothing to unescape | 0.14 us | 42 ms |

Two design constraints follow from the
[per-entry rule](arch-inventory-provider.md#the-per-entry-rule):

- **The walker yields the retained record.** A contract entry per discovered entry would
  add a construction and two validations per entry.
  `FsEntry` and `WriteToken` live in `metabrowser.fs_record`, which belongs to neither
  the scanner nor the browser layer, so the walker can build the retained record
  directly while
  `tests/test_python_inventory_provider.py::test_scanner_and_reducer_do_not_depend_on_browser_events`
  keeps the scanner independent of `metabrowser.events`.
- **Escaping happens once, on the way in.** The store is keyed by the canonical
  identity, which reduces `_semantic_entry` to a field copy instead of three escapes on
  every row of every read.

`tests/test_inventory_walk_work.py` holds the walk to counts rather than times.
With no reader attached, a discovered entry costs one retained record, no conversion to
a contract entry, and one path validation, in the provider’s change batch
(`test_discovery_validates_each_path_once_and_converts_nothing`). With a browser
attached, each entry is reread through the contract and validated three times: the
change batch, the entry query, and the contract entry
(`test_attached_walk_projects_each_entry_with_one_validation_per_record`). The
coordinator passes a batch that arrives alone through unchanged rather than revalidating
it.

## What Is Still on the Path

- **Change batches during discovery.** `_record_provider_change` builds a validated
  change batch for every entry discovered, to publish invalidations for entries no
  reader has seen. A browser attached during a walk pays more: the event bus rereads
  every dirty path through the contract, once per discovered entry.
  Suppressing publication during discovery would change the delivery contract, because a
  consumer attaching mid-walk has to be told what it missed.
- **The root tally’s first pass.** The navigation tallies behind the root request are a
  full pass over the index the first time each revision is asked for; it is memoized,
  but during a walk the revision moves on every write.
  Maintaining the counts per write, as the children index is, would remove it.
- **Unyielding whole-index steps.** The sort that follows the catalog read’s filter and
  the Recent pass do not yet yield to the event loop.
- **No admission control.** Under sustained back-to-back requests with no think time,
  the walker can be starved.
  Yielding the loop per batch was measured and made both the walk and expansion slower,
  so a fix here needs measurement first.
- **A failed watch is announced but not repaired.** A bounded retry with backoff is not
  built.

## References

- [Inventory Provider Contract](arch-inventory-provider.md): what this engine implements
- [Live Delivery](arch-live-delivery.md): what consumes its changes
- [Engine Performance Model](../../engine-performance-model.md): how these costs are
  measured
- [Scale Benchmark](../../scale-benchmark.md): end-to-end scan and serving figures

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
