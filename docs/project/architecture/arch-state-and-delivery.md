# Architecture: State and Delivery

**Author:** Metabrowser maintainers

**Status:** Approved

## Overview

Metabrowser holds one picture of the served tree, in a server that is watching it change
and a browser that is watching the server.
This document is the engineering account of that picture on both sides: what state
exists, who is allowed to write it, how derived state is invalidated, how it crosses the
wire, and what the browser does with it when it arrives.

It is one document rather than a server one and a client one because the interesting
failures live at the seam.
A placeholder that the server knows is provisional becomes a confident zero three layers
later; a structure the server rebuilds per request becomes a browser that never stops
polling. Neither is visible from one side alone.

The rule the whole design encodes is one sentence: **state proportional to the tree is
built once and maintained incrementally, never rebuilt per request** — and its corollary
on the client, **what is provisional stays visibly provisional.**

## Goals and Non-Goals

### Goals

- Keep one authoritative inventory with exactly one writer
- Make every derived structure’s invalidation rule explicit and testable
- Serve any request in time proportional to its answer, not to the index
- Let a reader see partial results immediately and refine them, rather than waiting
- Keep a placeholder distinguishable from a measurement at every layer it crosses
- Recover from a gap in the delta stream without a page reload

### Non-Goals

- Parallelism. The GIL means concurrent CPU work interleaves rather than overlaps; the
  aim is to do less work, not to do it on more cores.
- A general cache framework.
  Each derived structure states its own invalidation rule next to itself.
- Persisting the index across restarts.
  It is rebuilt by crawling.
- A client-side framework.
  The shell is plain modules over a small number of stores.

## First Principles

Two facts about the problem determine nearly everything below.

**The tree can be large.** A hundred thousand files is the design center and half a
million the cap.
No response can carry it, so every response is bounded — and bounding is
a ranking problem, not a truncation problem: what is omitted has to be the least useful
thing, and the response has to say that it omitted something.

**The tree changes while it is being read.** A crawl is filling in, and the filesystem
moves underneath. So no state can be fetched once and trusted; it has to converge.
Convergence needs three things the design supplies: a delta stream, an authoritative
snapshot to fall back to when the stream has a gap, and a way to say “this number is not
final yet.”

Everything that follows is those two facts applied to a specific layer.

## The Deployable Unit

The server, the browser shell, and the built-in plugins ship as one artifact.
The index route is served uncached, every script is stamped with a content-derived `?v=`
token, and the browser’s configuration is inlined into that same response.
An upgraded server therefore always serves the matching shell, settings, and plugins
together.

That is why `/api/*`, `window.metabrowser`, `METABROWSER_SETTINGS`, and the plugin
manifest are internal contracts rather than versioned peers: a change to any of them
lands in one commit across all three halves, and compatibility shims between them are
forbidden. See
[Compatibility and Legacy Code](../../development.md#compatibility-and-legacy-code).

## Server: Concurrency Model

**One provider writer, many readers.** The opened `InventoryHandle` owns filesystem
facts. In the Python provider, the boot walker, verified watcher refreshes, and subtree
rewalks write on the asyncio event loop and yield only at explicit `await` points.
The activity tracker writes the coordinator’s sparse host overlay instead of mutating
provider entries.

**A worker thread is such a producer, so it takes the lock.** The argument above holds
only for code on the loop.
`navigation_tallies_snapshotting` reads the index from the executor, so it acquires
`_rollup_cache_lock` — the same lock `_replace_index_entry` and `_pop_index_entry` hold
— and reads the entries and the revision they belong to inside one acquisition.
Reading them separately is the bug worth naming: the walker can write in between, which
keys a memo to a revision newer than the contents it summarizes, and on a settled tree
the revision never advances again to evict it.
Any future read from off the loop belongs under the same lock, and not because the GIL
makes the read unsafe today — it does not — but because that is the invariant a
free-threaded build will hold us to.

Read paths offload CPU work to a 64-worker executor (`events_route.py`,
`loop.set_default_executor`). That buys queueing, not parallelism: under the GIL a
rollup running in a worker competes with the walker on the loop rather than running
beside it.
The practical consequence is that background scan work and foreground requests
take CPU from each other, so the way to protect responsiveness is to make each request
cheap, not to move it to a thread.

Two synchronization points matter:

- `PythonInventoryHandle._rollup_cache_lock` guards `_entries` and every structure
  derived from it. It is held for dict operations only, never across an `await` or a
  bounded rollup reduction.
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

A directory’s aggregate summarizes its whole subtree, so a single file write invalidates
every aggregate above it.
Entries do not work that way: a file write invalidates exactly one entry.
That difference is what makes aggregates expensive to keep current and cheap to keep
*approximately* current, and it is why the delivery model differs.

The asymmetry in the last two rows is the remaining architectural debt, and it is
deliberate: because the event stream only carries entries within `root-depth-2`, a
change deep in the tree never reaches the client, which is *why* aggregates are pulled
at all. See [What Is Not Solved](#what-is-not-solved).

## Server: State

### Authoritative

`PythonInventoryHandle._entries` maps path to the Python provider’s retained filesystem
record. Everything else in that provider is derived from it and must be rebuildable from
it.
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
| `_aggregate_evicted_at` | directory → eviction epoch | Released once no rollup pass is in flight |
| `_descendant_file_counts` and siblings | running per-directory totals | Adjusted per write, incrementally |
| `_pending_dirs` | directories awaiting finalize | Post-order finalize, or end-of-walk repair |
| `_navigation_tally_memo` | the root request’s index-wide tallies | A new revision |

The two structures that exist to remove per-request O(N) work follow the same rule from
opposite directions:

- `_children_index` is **maintained**. A write updates one bucket.
  Every reader — the rollup’s subtree walk and `/api/tree`’s recursion — looks up only
  the buckets on its own path.
- `_subtree_aggregates` is **evicted**. A write drops the changed path and its
  ancestors; sibling subtrees stay valid and are reused.
  A rollup then recomputes only what moved.

An epoch exists only so a merge can refuse an aggregate the walker has moved past, so
once no pass is in flight there is no merge left to consult one and the whole map is
released. Retaining them instead would grow it with every directory path seen in the
process lifetime rather than with the current directory count, and a long session over a
churning tree — build outputs, dependency reinstalls, temp directories — would never
give any of it back.

Eviction walks the full ancestor chain rather than stopping early, because the epoch has
to be recorded even for a directory that holds no aggregate right now — a rollup already
in flight may be about to publish one, and the epoch is what tells the merge to refuse
it. Cost is one chain walk per write, bounded by `INVENTORY_MAX_DEPTH`. Only directories
are tracked, so the epoch map grows with the directory count rather than the entry
count.

Separately, `projections.py` memoizes per-file derived projections (JSONL views, charts)
in `MtimeCache` keyed by absolute path, with the entry’s mtime fingerprint checked on
every read, so editing a file invalidates its projection automatically.
Changing the served root clears these through `paths_safe.register_root_callback`.

### Response state

`/api/rollup` answers conditionally.
A rollup body is a pure function of the returned engine version, host overlay revision,
path, and bounds that shape the response, so those values make an exact validator.
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

## Delivery

### Validators

Every route that answers conditionally builds its validator in `http_caching.py`, and
`tests/test_http_caching.py` fails the build if one is constructed anywhere else.
That rule exists because the tag has to fold in the build’s identity, not just the
source: Metabrowser answers with a *rendering* of a file, so a validator derived from
the file alone will hand a browser back a stale rendering after an upgrade that changed
how that file renders.
Inventory-derived responses validate on the coherent host version returned with their
provider read instead of file metadata, because their bodies summarize many files rather
than reproducing one.

### Why a conditional response is safe

A validator is a claim, and the claim has to be checked.
`/api/rollup` answers `304 Not Modified` on an unchanged host version, so it is worth
stating exactly what that promises and what it rests on.

**The tag identifies the resource.** It carries the served root, because “the rollup of
this path” is a different resource under a different root, and a validator that left the
root out would reuse one root’s body for another wherever their revisions lined up.

**The tag covers the whole body.** The response carries the rollup node, extension
tallies, the file-type breakdown, `index_status`, `indexed_files`, `max_files`, and
`truncated`. Every one of those is a function of the index contents, the request’s
bounds, or a constant.
The bounds are in the tag directly.
The remaining fields come from the same bundled, versioned read as the rollup.
In the Python provider, `_entries` is mutated in exactly two places
(`_replace_index_entry`, `_pop_index_entry`), both of which advance the engine sequence,
and lifecycle transitions advance it as well.
There is no path that changes what the body would say without changing the tag.

**The revision only moves forward.** Python-provider revisions come from one
process-wide sequence rather than a per-handle counter, and the engine version also
carries a session identity.
A tag cannot be reused for different content across roots or handles.

**So a `304` means “the index has not changed”.** It does not, by itself, mean the
filesystem has not changed.
Those are the same statement only while the index is tracking the filesystem, which is
the watcher’s job:

```
filesystem change
  → provider-owned watcher (native inotify/FSEvents/kqueue, or 2s polling)
  → provider refresh hint
  → provider verifies and applies the observation
  → _replace_index_entry / _pop_index_entry
  → coordinator invalidates host projection caches
  → engine and host versions advance
  → new ETag, fs.change on the stream
```

Every link is checked except the first, and the first is where the honest limits are:

- **Polling latency.** On a filesystem where native watches are unreliable — NFS, CIFS,
  FUSE, or any type the selector does not recognize — the watcher polls every 2s, so a
  change can be up to that old.
  Unknown types default to polling rather than native, so the failure mode is *late*,
  never *never*.
- **A failed watch.** If the watch itself fails, live updates end.
  Exhausting the inotify watch limit on a large tree lands here.
  The provider marks coverage with `watcher_gap`, freshness as stale, and reports a
  typed issue and diagnostics; the coordinator projects that transition as a
  `capability.update` with `state: "failed"`. This is necessary because nothing
  downstream can distinguish a quiet filesystem from a dead watch.
- **Gitignore edits.** `FsEntry.gitignored` is stamped at write time from a checker
  cached per served root, so editing a `.gitignore` does not re-flag entries already in
  the index until they are rewalked.

None of these are introduced by the validator; a request that recomputed the body from
scratch every time would return exactly the same stale answer, because it would read the
same stale index. The validator inherits the index’s freshness and adds nothing to it.
What it changes is that a stale index is now *visible* — a client that keeps receiving
`304` while it believes the tree is changing is being told, precisely, that the server
has seen nothing.

### The event stream

`/api/events` is one Server-Sent Events connection per tab, carrying an ordered delta
stream. The provider publishes bounded `ChangeBatch` invalidations to the coordinator;
the application event bus performs one coherent reread and projects the result to each
connected browser. With no browser connected, it advances the cursor without building
wire records; a new connection always begins with a coherent snapshot.

| Event | Carries |
| --- | --- |
| `fs.snapshot` | Authoritative initial state at the connection’s scope |
| `fs.change` | Ordered upsert and remove ops |
| `catalog.change` | Quick File catalog upserts, exact file evictions, and subtree removals, emitted beside every `fs.change` |
| `fs.resync_required` | A gap marker: drop derived state and resubscribe |
| `capability.update` | Index completeness, watcher backends |
| `projection.invalidate` / `projection.update` | Plugin projection lifecycle |
| `file.append` / `truncate` / `rotate` / `closed` / `coalesced` | Live-file tailing |
| `heartbeat` | Liveness |

A subscriber whose queue fills cannot be sent a correct ordered stream any more, so the
event bus drains its backlog, replaces it with `fs.resync_required`, and detaches that
connection: bounded memory and an honest signal instead of a corrupted delta stream.

Bulk state deliberately does not ride the stream.
`/api/catalog` is a plain JSON response because the gzip middleware compresses it (SSE
frames are never compressed), its ETag makes refetch-after-reconnect a `304`, and
encoding runs off the event loop instead of as a synchronous dump inside the stream
handler.
Live catalog updates then arrive as `catalog.change`; the pair converges without
a shared transaction because ops are idempotent by path.

Removal semantics stay explicit on that event.
`remove_files` names files made ineligible by a gitignored upsert, so the browser
applies each with one exact `Map.delete`. `removes` names filesystem paths that
disappeared and may therefore name directories, so the browser performs the prefix sweep
needed to evict descendants.
Combining the two is a correctness-preserving but unbounded-cost mistake: the client has
to interpret every exact file as a possible directory and scan the complete catalog.
`tests/dom/known-file-catalog-behavior.js` installs a `Map` that counts key enumeration
and is the named check that exact removals never enter that path.

### Routes

| Route | Purpose |
| --- | --- |
| `/view/{path}` | The canonical, reloadable document URL |
| `/api/tree` | Nav subtree, bounded by depth |
| `/api/rollup` | Bounded subtree aggregation for Overview and treemap |
| `/api/file` | File envelope: kind, view descriptors, preview |
| `/api/recent` | Top-N by mtime within a window, clustered |
| `/api/catalog` | One-shot Quick File universe |
| `/api/events`, `/api/stream` | Delta streams |
| `/api/index/progress`, `/api/index/meta`, `/api/capabilities` | Index and backend status |
| `/api/activity` | Active-file polling |
| `/api/kpress/render`, `/api/kpress/export`, `/kpress-static/{path}` | Document rendering |
| `/raw` | Bounded byte passthrough for embedded resources |

#### `/api/tree` serves two different questions

The same route answers a request for *rows* and a request for *tallies*, and which one
it answers is decided by `depth` alone.
A client that does not know this will ask the wrong one and read the absence of a field
as a defect.

| Request | `depth` | Returns | Issued by |
| --- | --- | --- | --- |
| Rows | absent, or `>= 1` | `tree` populated; tally fields null unless a fresh memo exists | the nav tree, via `treeUrl` |
| Tallies | `0` | `tree` empty, always; `summary`, `extensions`, `canonical_extensions`, `file_type_registry`, `type_families`, `type_presets`, `recency_tallies` | `scheduleRootSummaryRefresh`, behind the render |

An absent `depth` is not unbounded: it resolves to `DEFAULT_TREE_DEPTH`, which is 2. So
the browser’s ordinary row request is a depth-2 request, and `depth=0` is a channel that
never carries rows at all -- time to first row cannot be measured on it.

**Only `depth=0` computes tallies.** The pass costs 0.37 s at 60,000 files indexed and
1.30 s at 220,000, and it competes with the walker for the GIL, so paying it on a row
request delays the rows and slows the scan that is producing them.
Every tally field is nullable and the client guards each one, which is what makes the
split safe. See
`explorations/performance-loop/experiments/exp-007-rows-stop-waiting-for-the-tally-pass.md`.

A client that wants both asks twice.
That is what the browser does, and it is why the split is invisible in the app and
visible at the API.

A URL fragment identifies a location *inside* the selected document and never the file
itself; query keys beginning with `_mb_` are reserved for presentation parameters and
every other key belongs to the document.
The full grammar is in [Browser URL Grammar](../../architecture.md#browser-url-grammar).

## Client: State

The shell is plain ES modules over a small number of stores.
`static/app.js` owns navigation, the tree, tabs, and view mounting;
`static/plugin-sdk.js` exposes `window.metabrowser`, the only surface plugins may use.
The other modules are single-purpose seams the shell and the SDK share.

Client state falls into three tiers that mirror the server’s.

### Tier 1: live stores, patched per op

These are the client’s half of the push layer.
Each is populated by `fs.snapshot` and then patched by `fs.change` ops; none is ever
refetched wholesale in normal operation.

| Store | Module | Holds |
| --- | --- | --- |
| `fileStore` | `app.js` | path → `FsEntry`, the source of truth for tree decoration |
| `metabrowserDirectoryTotalsStore` | `directory-totals-store.js` | Per-directory totals, the plugin-visible cache |
| Known-file catalog | `known-file-catalog.js`, `catalog-feed.js` | The Quick File universe |

Applying an op patches the store and the rendered row together, so a live update does
not require a re-render of the tree.

### Tier 2: envelopes, replaced wholesale

These are the client’s half of the pull layer: a response that is refetched when
something relevant changes, rather than patched.

- `resource-context.js` — a multiplexed live envelope store for path-scoped resources,
  so several views of one path share a single fetch.
- `inventory-scope.js` — the shared primitive underneath both: *is this inventory event
  relevant to my scope*, plus the debounced refresh lifecycle.
  Its debounce is bounded by one window, because a crawl emits changes continuously and
  a debounce that restarted on every one would never fire until the stream paused.
- `watchRollup` in the SDK — the folder Overview’s and treemap’s refresh loop, built on
  the above.

### Tier 3: view and shell state

State that belongs to what is on screen rather than to the tree.

`view-state.js` (active-view subscriptions, print metadata), `tree-expansion.js`
(disclosure state and the initial expansion plan), `filter-state.js` (the one filter
vocabulary behind the nav controls), `theme-state.js` (the resolved-theme boundary the
shell and canvas renderers share), `navigation.js` (canonical route construction),
`contribution-registry.js` (deterministic registration for views and commands).

Mounted plugin views are the disposable part of this tier.
Replacing the preview pane runs every registered disposer; switching tabs does not, so a
tab’s DOM and captured state survive until a different file replaces the pane.

### Recovery

The delta stream can develop a gap — a slow tab, a dropped connection, a server-side
queue overflow. The client treats that as a first-class state, not an error: on
`fs.resync_required` it clears the catalog, drops `fileStore`, notifies subscribers,
restarts progress polling, and replaces the connection so the server sends an
authoritative `fs.snapshot` before live updates resume.

`EventSource` reconnects on its own for transient errors.
On top of that the shell keeps a consecutive-error count and a circuit breaker: repeated
failures close and recreate the connection with exponential backoff, and a connection
that survives a stability interval resets it.
The interval matters — resetting on `onopen` alone would let an overflow-resync cycle
reconnect tightly forever.

### Placeholders are not measurements

The rule that connects both halves, and the one most easily lost at a boundary: **a
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

## The Plugin Boundary

Plugins are where domain knowledge lives; core stays consumer-agnostic.
A manifest declares which kinds a plugin claims and which views it contributes, and the
shell resolves each `(kind, view)` pair in the JavaScript registry.

Plugins reach state only through `window.metabrowser`. That surface includes read access
to the stores above (`directoryTotals`, `fileCatalog`, `folderContext`), bounded fetch
helpers (`fetchPluginData`, `fetchText`, `fetchJsonl`, `fetchRollup`, `watchRollup`),
navigation, and presentation utilities.
The `Metabrowser*` globals the modules publish are shell-internal seams that the SDK
proxies; a plugin that reaches into them is depending on something with no contract.

Any view that captures state must register a disposer.
See [Plugin authoring](../../plugins.md).

## Data Flow: Opening a Large Folder

1. The walker crawls in **strict level order**. Every directory at depth N is scanned
   before any at depth N+1, so the layers the nav tree shows are complete early: on a
   100,000-file tree, depths 1 and 2 are fully discovered 2 ms and 22 ms into a
   6.6-second walk.
2. Entries are stored through `_replace_index_entry`, which maintains `_children_index`
   and evicts the ancestor chain from `_subtree_aggregates`.
3. Batched `fs.change` events reach subscribers; tier-1 client stores patch in place and
   rendered rows update with them.
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

`devtools/bench_serving.py` reproduces every row below, and its `--browser-probe` half
covers the client behavior the server cannot see — whether validators are working and
what simultaneous clients actually cost.
See [Benchmarking Scan and Serve](../../development.md#benchmarking-scan-and-serve).
Absolute numbers move with the machine and the filesystem, so compare a before and an
after from one machine rather than against the table.

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

**The root request’s tally is still a full pass the first time.** `/api/tree` with an
empty path needs the index-wide navigation tallies — extension, family, preset, and
recency counts over every file entry.
That pass is proportional to the index and nothing else on the request path is: measured
at 486 ms for 100,000 entries and 2.7 s for 400,000, against a 3.8 KB response, while a
123 KB subtree response costs 6 ms.

It is memoized on the index revision, so the cost is paid once per change rather than
once per request or per tab: repeat root requests fall to 4 ms at 100,000 entries and 15
ms at 400,000, and clients arriving together share one pass.

The memo key carries no clock term, which matters more than it sounds.
Recency windows are the one clock-dependent part, and an earlier version keyed the memo
on a rounded second to cover them.
That fails exactly where the memo is needed: at 400,000 entries the pass takes longer
than the bucket, so every request landed in a later bucket than the one before it and
the memo never hit at all.
Recency is now answered from a sorted mtime array by binary search per window, so the
memoized half depends only on the entries.

What remains is the first request after any change — and during a crawl the revision
moves on every write, so a root refresh while scanning pays the pass again.
Removing that means maintaining the counts per write, the way `_children_index` is,
which is tracked as `mb-65mg`.

**No admission control between foreground and background.** At a realistic interaction
rate the crawl converges normally.
Under sustained saturation — requests issued back-to-back with no think time — the
walker can be starved indefinitely.
An attempt to fix this by yielding the event loop per batch made both worse (walk 17 s →
23 s, expand p90 166 ms → 211 ms) and was reverted; anything here needs measurement, not
reasoning.

**A failed watch is announced but not repaired.** The watcher publishes
`state: "failed"` and stops; nothing retries it, and no surface turns that into
something a reader sees.
The information is on the stream for a client that wants it, which is the floor, not the
finished behavior: a badge, and a bounded retry with backoff, are the obvious next
steps.

**Truncated scans leave unscanned directories pending.** Past `INVENTORY_MAX_FILES` the
walker force-finalizes what it scanned and leaves the rest as placeholders.
The end-of-walk repair is deliberately skipped, because descendant counts are incomplete
and repairing would state a total that is wrong.

## Invariants

Changes to any path above should preserve these.
Each has a test that fails when it does not; 2 and 7 are enforced by a scan over the
source rather than by exercising a behavior, so a new violation fails the build wherever
it is written.

1. Every Python-provider derived structure equals a from-scratch derivation from
   `_entries`, after writes and after removals.
2. Every Python-provider index write goes through `_replace_index_entry` or
   `_pop_index_entry`.
3. No request path *repeats* work proportional to the index.
   A rollup costs what changed; a tree expansion costs the subtree it returns; the root
   request’s index-wide tally is computed once per revision and reused.
   The weaker word is deliberate — the root tally is a full pass the first time it is
   asked for, and that is recorded in [What Is Not Solved](#what-is-not-solved) rather
   than claimed away.
4. The walker discovers in strict level order.
5. An aggregate computed against data the walker has moved past is discarded, not
   published.
6. A value marked provisional never renders as a settled measurement.
7. Every conditional response builds its validator in `http_caching.py`.
8. Nothing changes what a response body would say without changing its validator.
9. A watch that fails announces it rather than ending quietly.
10. A client disconnecting cancels only its own wait, never a shared computation.

## Related Documentation

- [Core architecture](../../architecture.md) — runtime shape, request flow, URL grammar
- [Plugin authoring](../../plugins.md) — the `window.metabrowser` contract
- [Rendering large content](../../large-content-rendering.md) — measuring before
  bounding
- [Design system](../../design-system.md) — tokens, and “everything is effortlessly
  fast”
- [File Rollup Format](file-rollup-format/file-rollup-format.md) — the aggregation
  contract
- [End-to-end testing](../../e2e-testing.md) — which layer each test covers
- [Real-time debugging](../../realtime-debugging.md) — observing the live path
- [Development](../../development.md) — workflow and dependency policy

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
