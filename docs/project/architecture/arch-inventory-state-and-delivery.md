# Architecture: Inventory State and Delivery

**Author:** Metabrowser maintainers

**Status:** Approved

## Overview

Metabrowser holds one authoritative picture of the served tree and delivers it to
browsers that are watching it change.
This document is the engineering account of that picture: what state exists, who is
allowed to write it, how derived state is invalidated, and how each kind of state
reaches the client.

It exists because the same mistake was made independently in four places.
Each of `/api/rollup`, `/api/tree`, the folder Overview, and the File Breakdown rebuilt
or discarded whole-index state on every request, and each looked locally reasonable.
The cost only appeared at scale, where it compounded: a 100,000-file root took about
fifteen seconds to show a single number, and past roughly a quarter-million files the
browser’s own refresh interval was shorter than the response it was waiting for, so the
view stopped converging entirely.

The rule this architecture encodes is one sentence: **state that is proportional to the
tree is built once and maintained incrementally, never rebuilt per request.**

## Goals and Non-Goals

### Goals

- Keep one authoritative inventory with exactly one writer
- Make every derived structure’s invalidation rule explicit and testable
- Serve any request in time proportional to its answer, not to the index
- Let a reader see partial results immediately and refine them, rather than waiting
- Keep a placeholder distinguishable from a measurement at every layer it crosses

### Non-Goals

- Parallelism. The GIL means concurrent CPU work interleaves rather than overlaps; the
  aim is to do less work, not to do it on more cores.
- A general cache framework.
  Each derived structure states its own invalidation rule next to itself.
- Persisting the index across restarts.
  It is rebuilt by crawling.

## Concurrency Model

**One writer, many readers.** Every inventory mutation — the boot walker, the filesystem
watcher, the active-file tracker, and subtree rewalks — runs on the single asyncio event
loop and yields only at explicit `await` points.
That is what lets `InventoryIndex.remove` snapshot and mutate without a lock: no other
producer can interleave inside a region that contains no `await`.

Read paths offload CPU work to a 64-worker executor (`events_route.py`,
`loop.set_default_executor`). That buys queueing, not parallelism: under the GIL a
rollup running in a worker competes with the walker on the loop rather than running
beside it.
The practical consequence is that background scan work and foreground requests
take CPU from each other, so the way to protect responsiveness is to make each request
cheap, not to move it to a thread.

Two synchronization points matter:

- `InventoryIndex._rollup_cache_lock` guards `_entries` and every structure derived from
  it. It is held for dict operations only, never across an `await`.
- An **eviction epoch** covers the one genuinely concurrent case.
  A rollup runs in a worker thread while the walker keeps writing, so an aggregate
  computed from what the worker read can finish *after* a write has invalidated it.
  Publishing it would leave a tally that is wrong and never corrects itself.
  Each pass therefore computes into a private map and merges under the lock, keeping
  only directories that nothing evicted since the pass began.

## The Two State Layers

Metabrowser delivers two kinds of inventory state.
They have different shapes, different transports, and different invalidation rules, and
most of the historical bugs came from treating one like the other.

|  | **Entries** | **Aggregates** |
| --- | --- | --- |
| What | One record per file, directory, symlink | Per-directory totals, extension tallies, file-type breakdown |
| Server state | `_entries`, authoritative | `_subtree_aggregates`, derived and evictable |
| Size | One per filesystem object | One per directory |
| Changes | On its own file’s change | On any change anywhere beneath it |
| Transport | **Push** — `fs.change` over SSE | **Pull** — `/api/rollup`, `/api/tree` |
| Computed | Once, fanned out to every subscriber | Once per distinct (revision, path, bounds) |
| Repeat cost | None; deltas only | One `304`, or a retained body |
| Client state | Incremental stores patched by op | Envelope replaced wholesale |
| Scope | Filtered to `root-depth-2` | Any path, any depth |

The asymmetry in the last two rows is the remaining architectural debt, and it is
deliberate: because SSE only carries entries within `root-depth-2`, a change deep in the
tree never reaches the client, which is *why* aggregates are pulled at all.
See [What Is Not Solved](#what-is-not-solved).

### Why aggregates cannot simply be entries

A directory’s aggregate summarizes its whole subtree, so a single file write invalidates
every aggregate above it.
Entries do not work that way: a file write invalidates exactly one entry.
That difference is what makes aggregates expensive to keep current and cheap to keep
*approximately* current, and it is the reason the delivery model differs.

## Server State

### Authoritative

`InventoryIndex._entries` maps path to `FsEntry`. Everything else is derived from it and
must be able to be rebuilt from it.
`tests/test_browser_rollup.py::test_derived_index_state_survives_writes_and_removals`
asserts exactly that, by deriving from scratch and comparing.

Every write goes through `_replace_index_entry` or `_pop_index_entry`. This is
load-bearing: those two functions are where derived structures are kept in step, so a
write that bypasses them silently desynchronizes the index.
Test fixtures that assemble a synthetic index use `conftest.SyntheticIndexWriter` for
this reason rather than assigning into `_entries`.

### Derived

| Structure | Holds | Invalidated by |
| --- | --- | --- |
| `_children_index` | parent path → children | The write itself, in place |
| `_subtree_aggregates` | directory → subtree aggregate | Eviction of the changed path’s ancestor chain |
| `_aggregate_evicted_at` | directory → eviction epoch | Never; bounded by directory count |
| `_descendant_file_counts` and siblings | running per-directory totals | Adjusted per write, incrementally |
| `_pending_dirs` | directories awaiting finalize | Post-order finalize, or end-of-walk repair |

The two structures added to remove per-request O(N) work follow the same rule from
opposite directions:

- `_children_index` is **maintained**. A write updates one bucket.
  Every reader — the rollup’s subtree walk and `/api/tree`’s recursion — looks up only
  the buckets on its own path.
- `_subtree_aggregates` is **evicted**. A write drops the changed path and its
  ancestors; sibling subtrees stay valid and are reused.
  A rollup then recomputes only what moved.

Eviction walks the full ancestor chain rather than stopping early, because the epoch has
to be recorded even for a directory that holds no aggregate right now — a rollup already
in flight may be about to publish one, and the epoch is what tells the merge to refuse
it. Cost is one chain walk per write, bounded by `INVENTORY_MAX_DEPTH`. Only directories
are tracked, so the epoch map grows with the directory count rather than the entry
count.

### Response state

`/api/rollup` answers conditionally.
A rollup body is a pure function of the index revision, the path, and the bounds that
shape the response, so those three make an exact validator.
The bounds must be in the tag: two clients asking for different depths share a revision,
and a tag that ignored the difference would hand one of them the other’s shape.

Three layers sit behind that tag, each covering a case the one before it does not:

1. **ETag** — a client that already holds the answer gets a `304`.
2. **Retained body** (`_ROLLUP_BODY_CACHE`, bounded by `ROLLUP_BODY_CACHE_ENTRIES`) — a
   client arriving *without* the tag, such as a second tab or a reconnect, gets the
   encoded body instead of a second aggregation.
   Bodies from a superseded revision can never be requested again and age out by
   insertion order.
3. **Single flight** (`_ROLLUP_IN_FLIGHT`) — clients arriving *together*, before the
   first has finished, await its result.
   Nothing between the lookup and the registration awaits, so two requests cannot both
   decide they are the one computing, and a failure — including the cancellation of a
   client that disconnects mid-build — is handed to everyone waiting rather than
   stranding them.

During a scan the revision moves on every write, so none of the three reuses anything.
That is correct: the answer really is changing then.

## Client State

The browser keeps its own stores, patched by the same `fs.change` ops the server emits:
`fileStore`, `metabrowserDirectoryTotalsStore`, and the Quick File catalog.
Plugins read directory totals through `window.metabrowser.directoryTotals` rather than
reaching into shell internals.

Aggregates arrive differently.
`watchRollup` refetches the whole envelope when an inventory change touches the watched
subtree, coalescing bursts behind a debounce.
That debounce is bounded by one window: a crawl emits changes continuously, and a
debounce that restarted on every one would never fire until the stream paused, freezing
a folder’s numbers mid-scan and then jumping.

### Placeholders are not measurements

The rule that connects both layers, and the one most easily lost at a boundary: **a
value the producer knows is provisional must stay distinguishable from a real one all
the way to the pixel.**

The walker finalizes a directory’s aggregate only after every descendant is walked, so a
large root has no totals of its own until the crawl ends.
The directory totals store represents that by zero-filling the aggregate and marking the
entry `state: "pending"`. Downstream, `normalizeFolderTotals` re-derived completeness
from the numbers alone and read those zeros as a settled “0 files” — a placeholder
presented as a measurement.
An explicit pending state now wins over the numbers beside it.

The same rule holds where two provisional sources meet.
The folder Overview draws totals from the walker’s finalized aggregate when it exists
and from the rollup otherwise.
During a crawl both are lower bounds that only grow, and either can be the stale one, so
the panel takes whichever has counted more — whole, never mixing fields — and never
replaces numbers on screen with a spinner.

## Data Flow: Opening a Large Folder

1. The walker crawls in **strict level order**. Every directory at depth N is scanned
   before any at depth N+1, so the layers the nav tree shows are complete early: on a
   100,000-file tree, depths 1 and 2 are fully discovered 2 ms and 22 ms into a
   6.6-second walk.
2. Entries are stored through `_replace_index_entry`, which maintains `_children_index`
   and evicts the ancestor chain from `_subtree_aggregates`.
3. Batched `fs.change` events reach subscribers; client stores patch in place.
4. `/api/tree` answers an expand by reading only the buckets in the requested subtree.
5. `/api/rollup` answers with what has been counted so far.
   The Overview renders it labeled as in progress rather than withholding it, and
   refines as the crawl proceeds.
6. When the walk ends, pending directory aggregates are repaired, status flips to
   `done`, and the revision stops moving — so every subsequent identical request is a
   `304` or a retained body.

## Measured Behavior

A 100,000-file tree (17,542 directories), browser attached, on the reference machine.
These are the numbers the design is accountable to; re-measure rather than trusting them
after changing any of the paths above.

|  | Before | Now |
| --- | --- | --- |
| First numbers on screen | 14.6 s | 2.4 s |
| Rollup p50 / p95 during scan | 610 ms / 1693 ms | 83 ms / 145 ms |
| Full scan with a client attached | 52.1 s | 16.5 s |
| Nav expand, 6 KB response | 63 ms | 6–8 ms |
| Repeat rollup, settled index | 30.8 ms | 7.6 ms (`304`) |
| 8 clients, settled, staggered | 236 ms | 30 ms |
| 8 clients, settled, simultaneous | 166 ms | 72 ms |
| Levels 1 and 2 fully crawled | 3 ms / 38 ms | 2 ms / 22 ms |

Nav-expand latency now tracks response size rather than index size, and no longer
depends on whether a scan is running.

## What Is Not Solved

**Aggregates are still pulled, not pushed.** The steady state is effectively
compute-once: on a settled index, eight clients cost what one costs.
During a scan the revision moves constantly, so every poll is a real aggregation.
Measured with N tabs on one folder: 1 tab, 15.7 s walk; 4 tabs, 19.0 s; 8 tabs, 25.4 s.
Bounded, and transient — but it is the case a push model would remove.
Tracked as `mb-gqci` under epic `mb-48vd`, deferred with the measurements recorded,
because the fix breaks three internal contracts and the two cheap fixes captured the
steady-state win.

**No admission control between foreground and background.** At a realistic interaction
rate the crawl converges normally.
Under sustained saturation — requests issued back-to-back with no think time — the
walker can be starved indefinitely.
An attempt to fix this by yielding the event loop per batch made both worse (walk 17 s →
23 s, expand p90 166 ms → 211 ms) and was reverted; anything here needs measurement, not
reasoning.

**Truncated scans leave unscanned directories pending.** Past `INVENTORY_MAX_FILES` the
walker force-finalizes what it scanned and leaves the rest as placeholders.
The end-of-walk repair is deliberately skipped, because descendant counts are incomplete
and repairing would state a total that is wrong.

## Invariants

Changes to any path above should preserve these; each has a test that fails when it does
not.

1. Every derived structure equals a from-scratch derivation from `_entries`, after
   writes and after removals.
2. Every index write goes through `_replace_index_entry` or `_pop_index_entry`.
3. No request path does work proportional to the index.
   A rollup costs what changed; a tree request costs the subtree it returns.
4. The walker discovers in strict level order.
5. An aggregate computed against data the walker has moved past is discarded, not
   published.
6. A value marked provisional never renders as a settled measurement.

## Related Documentation

- [Core architecture](../../architecture.md)
- [Rendering large content](../../large-content-rendering.md)
- [File Rollup Format](file-rollup-format/file-rollup-format.md)
- [Development](../../development.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
