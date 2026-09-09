# Research: Aligning fdu and Metabrowser Behind a Pluggable Inventory Engine

**Date:** 2026-08-23

**Author:** Metabrowser maintainers with OpenAI Codex research assistance

**Status:** Complete

## Implementation Update

[Metabrowser pull request 74](https://github.com/jlevy/metabrowser/pull/74) implements
the Phase 1 contract described here.
The maintained design now lives in the
[inventory-provider architecture](../architecture/arch-inventory-provider.md), and the
remaining fdu adoption work lives in the
[implementation plan](../specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md).

The reviewed implementation names the reference module `python_inventory.py`, treats
`max_files` as a regular-file scope budget, applies the same hidden-name allowlist to
walking and watching, and rejects unsupported scope policies explicitly.
Complete tree and snapshot consumers follow bounded continuations at one engine version
and host overlay boundary.
Initial stream attachment suppresses changes already represented by that snapshot, and
an incompletely delivered watcher batch becomes a typed stale gap.
These details replace the pre-refactor `InventoryIndex` descriptions below where the
research records the original baseline.

## Overview

Metabrowser should integrate fdu behind a Metabrowser-owned **inventory engine**
interface. The interface should cover the retained index, coherent queries, progressive
initial discovery, refresh, and live changes.
A walker-only interface is too low: it would replace directory enumeration while leaving
the Python entry heap, per-entry ancestor updates, repeated whole-index queries, and
lack of persistence on the hot path.

The target has two providers:

- a Python reference backend extracted from the current `InventoryIndex` implementation;
- an fdu backend that owns its native index, maintained rollups, cache, reconciliation,
  and watcher.

The Starlette routes, Server-Sent Events (SSE), browser wire models, plugin SDK, and
[File Rollup Format](../architecture/file-rollup-format/file-rollup-format.md) remain
above the interface.
The providers return application-neutral typed values rather than JSON, `FsEntry`, or
fdu CLI reports. Metabrowser converts those values into its internal wire envelopes.

This design preserves a simple Python oracle, lets either backend run from the same
configuration, and gives the performance framework one explicit comparison axis.
It also requires a stronger correctness contract than either implementation exposes now:
every query must return one coherent version, and every data or trust transition must be
resumable from the same event cursor.

Pull request [fdu#44](https://github.com/jlevy/fdu/pull/44) has the right broad
direction. Its shared reads, partitioned rollups, runtime taxonomy, progressive session,
and embedder-watch work are necessary.
Before implementation, the plan should be tightened around the engine boundary, bounded
batch queries, File Rollup conformance, subtree provenance, versioned reads, lossless
path identity, and the exact handoff from initial discovery to watching.

## Questions to Answer

1. Where should Metabrowser place the boundary between its server and either inventory
   implementation?
2. Which filesystem, classification, rollup, lifecycle, and failure semantics must both
   providers implement?
3. Which parts of fdu pull request 44 are ready, which need refinement, and which
   integration requirements are missing?
4. How can queries stay coherent, bounded, and cheap across Python and Rust without
   coupling fdu to Metabrowser’s HTTP wire?
5. How should initial discovery, cache revalidation, watching, cursor resume, and
   backpressure compose without gaps?
6. Which project owns the file-type registry and how does the other consume it without
   duplicating classification?
7. How should the Python and fdu implementations be proven semantically equivalent?
8. Which measurements show an end-to-end improvement and its distance from the
   filesystem’s physical limits?
9. In what order can the change land while keeping every intermediate state testable?

## Scope

This research covers the filesystem metadata inventory that serves navigation, directory
totals, file-type rollups, recent files, the Quick File catalog, initial inventory
events, and live updates.
It includes the provider boundary, shared semantics, configuration, cache and watcher
lifecycle, differential testing, rollout, and performance measurement.

It does not move file contents, Git history, rendering, plugin routes, or browser state
into fdu. It does not define a public third-party backend SDK. The server, built-in
plugins, and both providers ship together, so this is an internal interface that may
change atomically when its consumers change.

The measurements recorded in fdu pull request 44 and fdu’s physical-floor report are
orientation evidence.
This research did not rerun those benchmarks and does not turn their host-specific
results into a Metabrowser performance claim.

## Findings

### Metabrowser Has the Right Product Architecture but the Wrong Replacement Seam

The current design has several strong properties worth preserving:

- one authoritative inventory is built once and updated incrementally;
- strict breadth-first discovery makes shallow navigation useful early;
- directory placeholders and finalization make partial state explicit;
- symlinks are visible leaves and are not followed;
- all-file and unignored totals are maintained separately;
- the File Rollup Format defines classification, populations, bounds, conservation, and
  registry identity independently of the application;
- query bodies are bounded, retained, single-flight, and validated;
- initial snapshots and later changes share the SSE delivery path.

The performance limitations arise below those decisions.
`InventoryIndex` combines the walker, watcher, authoritative records, derived indexes,
rollup cache, navigation tallies, query methods, event subscriptions, and lifecycle in
one Python class. Its hot paths include:

- one Python dataclass per retained entry;
- one `os.scandir` worker call per directory and one Python yield per discovered or
  finalized record;
- ancestor-chain updates on each file mutation;
- full entry-list copies and whole-index passes for filtered trees, recent files,
  catalogs, and navigation tallies;
- rollups built against live Python maps, with memoized aggregates added after the pass;
- no persisted inventory, so every process starts from an empty index;
- safety caps that turn large or deep trees into partial inventories.

The load-time performance work has already identified the corresponding architectural
floor: an amnesiac index, a sequential interpreted walk, and repeated work proportional
to the complete tree.
Replacing only `walk_tree()` would make directory enumeration faster while retaining
nearly all of that floor.
It would also serialize millions of native observations into Python only to rebuild
state fdu already maintains.

The present rollup cache also exposes why the new boundary needs a coherent-read rule.
`/api/rollup` reads an inventory revision for its ETag before dispatching the query, but
`InventoryIndex._rollup_view()` intentionally returns live maps that can observe later
writes while the worker builds the body.
The eviction epoch prevents a stale aggregate from entering the memo; it does not prove
that the returned body belongs to the earlier ETag revision.
The target interface must make the payload and its version one atomic result rather than
asking the route to sample a counter before a query.

### fdu Supplies the Missing Engine, Not a Drop-In Walker

The fdu engine already has the structural pieces Metabrowser needs:

- a retained parent-pointer index with native filename identity;
- precomputed per-directory counts, apparent bytes, allocated bytes, newest file mtime,
  and extension tallies;
- typed, conditionally applied deltas with a logical clock;
- generation-safe entry identities and stale-observation arbitration;
- snapshots, cache policy, full revalidation, and scoped reconciliation machinery;
- coherent Rust reads through `IndexHandle`;
- native watch sessions and a bounded `since(clock)` journal;
- breadth-first, region-scheduled parallel traversal;
- provenance axes for source, observation time, coverage, and freshness;
- CLI, Rust, and Python surfaces checked for parity.

Pull request 44 reports a 5.764-second Metabrowser walk and a 0.201-second fdu cold
index build on one generated 120,001-entry corpus, about a 29-fold orientation result.
It also reports sub-millisecond retained-index queries and lower resident memory for fdu
on that corpus. Those figures show enough headroom to justify integration work, but they
are not yet an end-to-end claim: the corpus is generated, the fdu call blocks until
complete, and the comparison excludes Metabrowser’s adapter, HTTP, SSE, and browser
work.

The fdu physical-floor report gives a better optimization frame.
On its measured Linux subjects, the aggregate-only tier approaches the parallel
metadata-call floor while the full retained index remains materially above it.
The report attributes most of the remaining cost to representation and per-entry
consumer work rather than to a missing filesystem trick.
That supports an engine interface broad enough to preserve fdu’s future index-layout
improvements instead of forcing its output back through a Python record stream.

### Pull Request 44 Is Necessary but Not Yet a Complete Integration Contract

The pull request correctly identifies several blockers.
Source review also found requirements that need to move from implicit assumptions into
the plan.

| Area | Current state at the pull request commit | Required target |
| --- | --- | --- |
| Python concurrency | Concurrent readers work, but a read during `refresh()` can raise `Already mutably borrowed` | Python holds a shared engine handle; reads wait or observe a complete prior/new version and never tear |
| Initial discovery | `open()` and `scan()` block | Immediate session return, progressive status and bounded data access, cancellation, and priority hints |
| Populations | One maintained rollup plane | Configured `all` and `unignored` populations updated by the same delta |
| Taxonomy | Compiled fdu registry | Runtime File Rollup registry supplied by Metabrowser and fingerprinted into session/cache identity |
| Logical extension | fdu folds `.tar.*` specially and otherwise takes the final suffix | The File Rollup algorithm: up to two eligible trailing components for every basename |
| Directory listing | `children()` clones all children and each directory’s complete extension map | Bounded or paged rows containing scalar totals only; no unrequested extension-map copy |
| Detailed rollup | One unbounded `by_extension` map | File Rollup breakdown with exact bounded fallbacks and remainder accounting |
| Provenance | A directory reports its own source, not the weakest descendant source | Rollup/subtree-composed provenance on every aggregate |
| Trust transitions | Cached-to-revalidated transitions are poll-only and do not advance the change clock | Data and trust transitions share a cursor and can wake a subscribed client |
| Change feed | Effective entry operations and a resumable clock | Enriched entries, dirty aggregate paths, state/progress changes, explicit gap, and one query-comparable version |
| Watch integration | Blocking, native-only iterator; whole-root Python refresh | Async adapter, native and poll policies, scoped refresh, and a proved no-gap boot-to-watch handoff |
| Entry kinds | File, directory, symlink, and other exist in fdu | The shared contract carries the three browser-representable kinds; each provider excludes special objects rather than reclassifying them as regular files |
| Empty directories | Rollup counts cannot distinguish a subtree containing only symlinks from an empty subtree | A maintained non-directory leaf count or equivalent exact `empty` fact |
| Query consistency | Individual Rust reads are coherent, but no Metabrowser result/version contract exists | One atomic result containing its state version, registry identity, coverage, and payload |
| Paths | Rust and PyO3 preserve native identity; rendered strings can be lossy unless raw identity accompanies them | Native identity through the provider and one documented lossless encoding at the host wire boundary |
| Instrumentation | CLI-oriented counters and summaries | Typed per-session and per-query work counters available to the serving benchmark |

The logical-extension difference is a concrete parity failure, not registry policy.
For example, the File Rollup Format classifies `release.v2.zip` as `.v2.zip` and
`bundle.umd.min.js` as `.min.js`; fdu currently derives `.zip` and `.js`. A runtime
registry cannot repair facts already derived differently.
fdu must run the existing File Rollup conformance corpus before it can produce
Metabrowser’s rollups.

The provenance limitations are similarly important for a warm interactive open.
fdu’s current `Index::provenance(path)` documents that a complete, revalidated directory
can still contain cached descendants.
It also documents that a cached-to-revalidated transition with no data change is absent
from `since()`. A browser would either clear an approximation marker too early or never
learn to clear it. Subtree provenance and clocked trust transitions are integration
prerequisites, not later polish.

### The Correct Boundary Is a Stateful Inventory Engine

Three boundaries are plausible:

| Boundary | Advantage | Structural problem | Verdict |
| --- | --- | --- | --- |
| Walker yields entry records | Small initial diff | Rebuilds the native index in Python, duplicates rollups, crosses the FFI boundary per entry or batch, and cannot use lazy snapshots | Reject |
| Routes call fdu objects directly | Fast prototype | Couples HTTP handlers to fdu’s current API, leaves the Python implementation without a peer contract, and spreads backend branches through the server | Reject |
| Metabrowser-owned inventory engine | One lifecycle and query contract, two testable providers, and native state stays native | Requires an explicit extraction before adoption | Adopt |

The interface belongs in Metabrowser because it states what the application needs.
fdu should remain application-independent and expose generic interactive-index
primitives. The fdu adapter maps those primitives into the Metabrowser contract.
No third shared package is needed: the application-independent interchange already
exists as File Rollup Format, and all other values are internal host-domain records.

The provider choice is fixed for one served-root session.
A route cannot switch providers per request, and a coordinator cannot merge records from
both. Running two live walkers against a changing tree would produce incomparable
observation moments and distort the performance being measured.
Differential checks should use immutable fixtures or one recorded observation stream
replayed into both providers.

## Shared Semantic Contract

The two providers should agree on semantics before they agree on method names.
The cleanest target is the intended product behavior, not every incidental behavior of
the current Python implementation.

| Subject | Required contract |
| --- | --- |
| Root and path identity | Paths are relative to one canonical served root. Native components remain lossless and distinct inside the engine. The HTTP layer owns a reversible machine encoding and a separate display-safe string. |
| Hidden names | Hidden components are outside the scan scope, except for a configured exact-name allowlist. They are pruned rather than tagged because the product does not offer a hidden-path toggle. |
| Gitignore | Visible entries are retained and tagged. Matching follows full gitignore negation and directory semantics. `all` includes them and `unignored` excludes them. |
| Traversal order | Breadth-first is the interactive scheduling default. Order affects progressive usefulness, not final state or cache validity. It is an operational policy, not a semantic fingerprint. |
| Symlinks | Retained as leaves, never followed by the interactive profile, and excluded from regular-file totals. |
| Special objects | Retained as `other` leaves when safely observable and excluded from file totals and content reads. They are never labeled as regular files. |
| Hard links | Each directory entry counts independently. Inode identity supports change detection; it does not deduplicate apparent bytes. |
| Depth and entry budgets | The normal profile has no implicit correctness cap. An explicit resource budget may stop a session, but every affected result reports partial coverage and its cause. Query output bounds are independent of inventory coverage. |
| Measures | Regular files contribute count, apparent bytes, optional allocated bytes, and mtime. Directory inode blocks do not contribute. Arithmetic is checked; overflow becomes an explicit failure rather than wrapping. |
| Newest time | The maximum mtime among descendant regular files. Directory and symlink mtimes do not contribute. |
| Empty | A complete subtree is empty when it contains no regular-file or symlink leaves. A partial subtree cannot claim emptiness. |
| File classification | Basename, logical extension, matching precedence, registry validation, registry fingerprint, grouping, populations, bounds, and conservation follow File Rollup Format and its conformance corpus. |
| Registry lifetime | The registry is immutable during a session. A new registry starts a new session/cache identity rather than retagging live values under the same version. |
| Populations | The interactive profile maintains `all` and `unignored`. `all` means all entries inside the scan scope, not hidden paths. Arbitrary selections are query predicates, not permanent rollup planes. |
| Filesystem failures | Permission, disappearance, malformed metadata, mount, and watcher failures are typed issues. A skipped subtree is partial, never silently complete or empty. |
| Snapshot consistency | Every response is derived from one engine version. Detailed rollup partitions conserve against totals from that same version. |
| Cache honesty | Cached values may be served immediately only with source, observation time, freshness, and coverage. Verification never silently upgrades a subtree whose descendants remain unverified. |

Two changes deliberately differ from pull request 44. Hidden state is a scope rule
rather than a second maintained tag plane, avoiding I/O and memory for paths Metabrowser
never shows. The maintained population set is named by the application profile rather
than exposed as a general complement algebra.
These choices keep fdu’s default CLI index small and make the interactive cost explicit.

## Proposed Metabrowser Interface

### A Small, Sealed Provider Surface

The interface should be an internal typed protocol with a fixed provider factory, not
entry-point discovery or a versioned external plugin ABI. It has two levels:

```python
class InventoryBackend(Protocol):
    async def open(
        self,
        root: Path,
        config: InventoryConfig,
    ) -> InventorySession: ...


class InventorySession(Protocol):
    @property
    def capabilities(self) -> InventoryCapabilities: ...

    async def read(self, request: ReadRequest) -> ReadResult: ...

    def events(
        self,
        *,
        after: EventCursor | None,
        interests: EventInterests,
    ) -> AsyncIterator[EventBatch]: ...

    async def refresh(self, request: RefreshRequest) -> RefreshReceipt: ...

    async def close(self) -> None: ...
```

This is illustrative, not a commitment to these exact Python names.
The important properties are:

- `open()` returns promptly with a session even when a cold scan continues;
- the backend owns every authoritative record and derived index for that session;
- `read()` is the only query boundary and returns the version it actually read;
- `events()` is pull-based, batched, bounded, resumable, and cancellable;
- `refresh()` accepts verified hints but all mutations still pass through the backend’s
  one delta path;
- `close()` cancels scan, reconciliation, watch, and adapter workers before releasing
  resources.

The Python provider owns the existing Python walker, inventory, and watcher behind this
surface. The fdu provider owns the native equivalents.
The coordinator above them owns root selection, provider construction, route-to-query
mapping, SSE projection, and wire serialization; it never stores a second authoritative
entry map. External activity or application observations may call `refresh()`, but they
do not run a second watcher.

### One Closed Query Algebra, Not a Generic Report Escape Hatch

`ReadRequest` should contain one or more typed projections.
Bundling lets `/api/tree` request rows, filtered totals, and navigation tallies from the
same version in one backend call and one FFI crossing.

| Projection | Domain result | Bound and intended cost shape |
| --- | --- | --- |
| `EntryQuery` | One entry’s facts and scalar directory totals | One path lookup; no filesystem stat |
| `DirectoryQuery` | A page or bounded-depth tree of child rows | Explicit row/node bound and remainder; scalar totals only |
| `FilteredTreeQuery` | Bounded tree plus whole-subtree selected totals | Explicit output bound; native/indexed predicate evaluation |
| `RollupQuery` | Directory tree totals and File Rollup breakdown | Explicit depth, child, fallback, and node bounds; exact remainder |
| `NavigationQuery` | Root populations, registry identity, extension/family/preset and recency tallies | Bounded rows from maintained or indexed state |
| `RecentQuery` | Newest matching regular files and ignored ancestor facts | Explicit row bound and exact pre-bound match count |
| `CatalogQuery` | File identities and logical extensions, optionally filtered by terminal extension, exact ancestor name, size, and ignore state | Paged or streamed with a stable version; predicates run before binding transfer; never an accidental unbounded tuple |

This is domain-shaped rather than route-shaped.
A future route may compose the same projections, and no projection contains HTTP status
codes, JSON dictionaries, ETags, or browser labels.

The query boundary should make expensive work visible.
Each result reports work counters such as entries visited, directories visited, output
records, bytes copied across the binding, lock wait, and query time.
The interface does not freeze an algorithm, but it prevents an implementation from
hiding an O(index) pass behind a property that appears cheap.

The fdu implementation needs new query forms rather than adapting its current
`children()` literally.
A directory row needs scalar rollups for the requested populations, classification
identity, leaf count, provenance, and tags.
It does not need the child’s complete `by_extension` map.
A separate bounded rollup query asks for that detail only when the folder overview needs
it. This distinction keeps work proportional to visible output and avoids both unbounded
cloning and one FFI call per child.

### Every Read Returns Its Version and State

`ReadResult` contains:

- an opaque `StateVersion` with a session identity, logical clock, scope fingerprint,
  and registry fingerprint;
- `IndexState`, separating lifecycle phase, structural coverage, freshness, source,
  progress, and typed issues;
- the requested typed projections;
- execution telemetry that is not part of the semantic payload.

The version is minted or captured inside the same read boundary as the projections.
The route builds its ETag from the returned version, query parameters, and application
build identity. It never samples a revision before dispatching work.
A retained body is cached only under the version that produced it.

An implementation may satisfy coherent reads with a shared lock, an immutable snapshot,
or version-check-and-retry.
The choice is internal, but two rules constrain it:

1. the payload cannot mix generations;
2. a frequent or unbounded read cannot hold the writer indefinitely.

The initial fdu implementation can use its shared index lock for bounded projections.
Any projection that still visits the full index should operate on an immutable read
image or purpose-built secondary index, then be measured under concurrent writes.
The Python provider must atomically capture the fields needed by the query and its
version; its current live rollup view is not sufficient.

### Lifecycle and Events Share One State Machine

Lifecycle is not one overloaded status string.
A session reports independent facts:

- **phase:** opening cache, discovering, reconciling, ready, watching, stopped, or
  failed;
- **coverage:** complete or partial, with a reason such as building, budget, cancelled,
  inaccessible, or failed;
- **freshness:** fresh, reconciling, stale, or partial;
- **source:** scanned, revalidated, journal-scoped, or cached;
- **progress:** entries and directories observed, with no invented total when unknown.

An `EventBatch` contains one cursor and resulting state version, plus any of:

- entry upserts and removals carrying the complete host-domain record needed by an
  interested consumer;
- directories whose aggregates or projections changed;
- lifecycle, coverage, freshness, provenance, or issue transitions;
- progress and execution counters;
- a reset marker when a retained cursor or bounded queue has a gap.

Provenance-only changes advance this stream even when file values did not change.
A client that reconnects with `after=cursor` either receives every later effective batch
or a reset marker; it never receives an apparently continuous suffix with missing state.

Event interests keep the native-to-Python path bounded.
A client can ask for shallow rows, expanded prefixes, recent-set effects, catalog
effects, or status only.
The engine may always maintain the complete index, but it should not serialize every
cold-scan entry into Python when no consumer needs it.
Slow consumers cause a gap and re-read; they do not block the native walker.

### Initial Discovery and Watching Need a Proved No-Gap Handoff

“The scan clock becomes the watch clock” is a desired outcome, not a complete algorithm.
The backend should implement and test this sequence:

1. Canonicalize the root, load any compatible snapshot, and establish the session and
   initial cursor.
2. Start capturing watch events before or atomically with discovery of the baseline.
3. Discover or verify the tree while watch events accumulate in a bounded native log.
4. Reconcile every captured event against observation expectations; on overflow or an
   unreliable backend, invalidate the affected scope and verify it.
5. Publish complete/fresh only after that reconciliation reaches a known cursor.
6. Continue the same event stream in resident watch mode.

The source of a filesystem notification is always a hint.
A stat or scoped rescan verifies it before mutation.
Native event loss, queue overflow, and unsupported mounts move freshness backward and
trigger reconciliation.
A polling fallback that claims exactness must inspect each entry’s metadata often enough
to catch in-place edits; directory mtime alone cannot prove an unchanged subtree.

## Ownership Across the Two Repositories

### Metabrowser Owns

- the `InventoryBackend` and `InventorySession` protocols and host-domain values;
- provider selection and lifecycle coordination;
- the interactive scope profile, including hidden allowlist and maintained populations;
- the File Rollup registry artifact it ships and passes to the selected provider;
- mapping engine results to `/api/tree`, `/api/rollup`, `/api/recent`, catalog, and SSE
  envelopes;
- ETag, retained-body, single-flight, connection, and browser scheduling policy;
- the Python reference provider and cross-provider conformance harness;
- end-to-end performance experiments and user-visible budgets.

### fdu Owns

- filesystem enumeration, metadata observation, native path identity, and optional
  platform acceleration;
- the retained native index, reducers, snapshots, cache validation, and change journal;
- runtime parsing, validation, indexing, and fingerprinting of a supplied File Rollup
  registry;
- configured entry tags and maintained populations;
- coherent batch queries and bounded typed results;
- progressive sessions, cancellation, priority hints, reconciliation, and watch
  backends;
- per-entry and subtree provenance, logical clocks, cursor retention, and gap signaling;
- Rust-to-Python batching, GIL release, shared-handle concurrency, and typed telemetry;
- its CLI and generic library contracts independent of Metabrowser.

### The Adapter Owns Translation, Not State

`FduInventoryBackend` converts fdu values into Metabrowser domain values once per
bounded batch. It does not retain a mirror tree, reclassify names, recompute aggregates,
run a second watcher, or parse rendered fdu reports.
`PythonInventoryBackend` implements the same contract directly and serves as the
readable reference.

This division resolves the registry release-cadence question in pull request 44. fdu
keeps its compiled default for its CLI. Metabrowser supplies its own registry at session
open. fdu’s parser supports the File Rollup schema version and indexes that immutable
registry for the session.
A Metabrowser registry edit therefore requires a Metabrowser release and cache refresh,
not an fdu release.

## Required fdu Work

The fdu plan should be revised into these integration capabilities, in dependency order:

1. **Shared Python handle.** Store and borrow `IndexHandle`, release the GIL around
   native work, and prove reads concurrent with refresh never raise or tear.
2. **File Rollup conformance.** Accept the runtime registry, implement the full logical
   extension and matching rules, expose classification and registry identity, and run
   the existing conformance corpus unchanged.
3. **Interactive scope profile.** Accept hidden-path admission rules, correct gitignore
   tagging, and configured maintained populations.
   Fingerprint semantic inputs while leaving scan order and worker settings out of cache
   identity.
4. **Complete directory facts.** Maintain the scalar fields the application needs,
   including non-directory leaf count and subtree-composed provenance.
5. **Coherent batch queries.** Add the bounded projection forms above.
   Return one state version and avoid cloning extension maps into ordinary child rows.
6. **Clocked trust state.** Put provenance and freshness transitions on committed
   batches so `since()` and polling cannot disagree about the visible state.
7. **Progressive session.** Return immediately, expose bounded read-anytime state and
   progress, accept priority hints, cancel promptly, and use a bounded pull queue across
   PyO3.
8. **Embedder change lifecycle.** Add dirty directories, async consumption, scoped
   refresh, explicit native and poll policies, cursor-gap handling, and the tested
   discovery-to-watch handoff.
9. **Typed telemetry.** Expose scan, cache, query, lock, journal, and binding-copy work
   beside results without adding execution facts to semantic report schemas.
10. **Interactive reference example.** Exercise boot, coherent queries, dual
    populations, resumable changes, cancellation, and resync without containing
    Metabrowser-specific wire models.

This list changes two readiness judgments in pull request 44. `children()` is not ready
for the application until it has a scalar, bounded form, and `since(clock)` is not ready
for SSE resume until trust transitions participate in the same clock.
The watcher’s verified entry operations remain a strong base for both.

## Required Metabrowser Work

1. Define the protocol, semantic records, state model, query algebra, errors, and
   provider factory in a focused inventory package.
2. Extract `PythonInventoryBackend` from `InventoryIndex` without changing wire output.
   Keep its storage and mutation internals private to the provider.
3. Make Python reads coherent.
   In particular, pair rollup payloads with the version they actually observe and make
   full-index snapshots plus revisions atomic.
4. Move tree-path existence checks from direct `Path.is_dir()` calls to the selected
   inventory session after lexical safe-path validation.
5. Change routes, recent-file collection, catalog, event routing, and diagnostics to
   depend only on the coordinator and typed query results.
6. Load the File Rollup registry once per session and pass the same normalized packet to
   either provider. Remove duplicate classification from the fdu path.
7. Add `python`, `fdu`, and later `auto` provider selection.
   An explicit unavailable `fdu` selection fails clearly; only `auto` may choose Python,
   and diagnostics report the choice and reason.
8. Add cross-provider fixtures, mutation replay, wire goldens, cursor tests, race tests,
   and error/partial-state tests.
9. Extend the serving and browser performance loops with a forced provider axis and the
   measurements below.
10. Enable fdu as an explicit experimental provider, validate it, and change the default
    only after the acceptance gates pass.

No compatibility layer is needed around the current singleton or `FsEntry`. They are
internal contracts and can change with all built-in consumers.
Keeping aliases or parallel write paths would make the migration harder to reason about
without protecting an independently released consumer.

## Consistency and Reliability Validation

### Three Complementary Oracles

The integration needs more than matching root byte totals.

1. **Shared format corpus.** Both providers run the existing File Rollup registry,
   classification, projection, and conservation cases.
2. **Recorded observation replay.** A normalized sequence of upserts, removals,
   invalidations, trust transitions, and failures is applied to both indexes.
   Every query projection is compared after each barrier without filesystem timing as a
   variable.
3. **Filesystem scenarios.** Both providers scan and then observe the same immutable or
   stepwise-mutated fixture tree.
   This validates enumeration, stat, ignore, path, watch, and reconciliation behavior
   that observation replay bypasses.

The filesystem scenarios should include:

- wide and deep trees, empty directories, compound extensions, and extensionless names;
- hidden paths and the allowed hidden names;
- gitignore directory rules, negations, and `.gitignore` edits;
- regular files, sparse files where supported, hard links, symlinks, broken symlinks,
  and special-object exclusion;
- non-Unicode native names on supported platforms;
- permission denial, disappearance during discovery, file-to-directory replacement, root
  removal, and mount-boundary behavior;
- same-size edits, restored mtimes, rename bursts, subtree deletion, and rapid create
  and remove;
- cancellation, queue overflow, retained-cursor overflow, watcher failure, and poll
  escalation;
- cached open, partially verified open, full revalidation, and an incompatible registry
  or scope fingerprint.

Parallel discovery need not emit records in the same order as Python.
The event oracle checks stronger semantic properties instead: cursors are monotonic,
applying an unbroken feed to its matching baseline yields the queried state, every gap
forces a reset, coverage never claims missing work, and a complete final snapshot is
identical.

### Acceptance Gates

| Gate | Required evidence |
| --- | --- |
| Static parity | Normalized entries, scalar rollups, classifications, populations, bounds, and host wire goldens agree |
| Mutation parity | Every scripted mutation converges to the same queries and normalized effective changes |
| Snapshot honesty | Cached, revalidated, journal-scoped, partial, and failed states carry correct subtree provenance |
| Concurrency | Reads during discovery, refresh, watch commit, cancellation, and close never tear, deadlock, or raise a borrow error |
| Cursor safety | Resume is lossless inside retention; overflow and slow consumption produce an explicit reset |
| Conservation | Every population and File Rollup partition sums exactly at every published complete version |
| Failure visibility | Skipped or uncertain subtrees are partial with typed issues; none appear as complete empty directories |
| Resource bounds | Every query and queue enforces its declared record or byte bound and reports exact remainder or reset state |

Wall-clock timing should not be a shared-CI gate.
Semantic, race, bound, and deterministic work-counter assertions should be.

## Performance Framework Alignment

### Measure the Backend at Three Layers

The comparison needs three nested views:

1. **Engine:** scan, index, snapshot, revalidation, query, and change-application costs,
   including distance from the platform metadata floor.
2. **Server:** provider open through HTTP/SSE response, including PyO3 conversion,
   serialization, cache, single-flight, event-loop delay, and concurrent clients.
3. **Browser:** first useful and final visible state, interaction latency, repaint and
   movement, and convergence after changes.

An engine-only win is necessary but not sufficient.
A design that saves scan time and then copies the full index or every extension map into
Python has moved rather than removed the cost.

### Extend the Standing Serving Benchmark

`devtools/bench_serving.py` should accept a forced provider and record it in every
result. Its current cold-unattached, cold-attached, settled, retained-body, validator,
tree-size, rollup, and multi-client phases remain useful.
Add or connect phases for:

- cache-only first useful response and background verification completion;
- unchanged warm revalidation;
- bounded directory, rollup, navigation, recent, filtered-tree, and catalog queries;
- reads while discovery and write batches are active;
- a sustained mutation stream and a large burst;
- watch overflow, cursor reset, scoped recovery, and polling fallback;
- cancellation, root replacement, and repeated open/close;
- settled and peak resident memory, cache file size, and bytes copied through PyO3.

Each result records enough context to reproduce the claim:

- Metabrowser and provider build identities;
- selected backend and fdu engine version;
- scope, registry, and corpus fingerprints;
- real or generated corpus provenance and structural shape;
- operating system, filesystem, mount characteristics, CPU, worker policy, and scan
  schedule;
- cache state, attachment state, trial order, and warmup policy;
- wall, user CPU, system CPU, peak and settled RSS, entries, bytes, errors, gaps, and
  backend work counters.

The existing load-time budgets remain the user-facing acceptance frame.
The provider comparison adds the architectural regimes the performance review calls out:
warm reopen, interaction during scan, churn, and resident memory at large scale.

### Use Paired Evidence and a Physical Denominator

For each backend comparison:

1. Build both candidates before trials and prove their semantic result digests match.
2. Use the same immutable real corpus and controlled cache state.
3. Interleave and randomize Python/fdu pairs so host drift affects both arms.
4. Run an A/A calibration to measure harness noise.
5. Report paired medians and a confidence interval, not only min/max overlap.
6. Measure attached and unattached scans because client polling perturbs the writer.
7. Repeat on generated shapes only to isolate a mechanism, never as the sole product
   claim.

Where fdu’s platform floor probe supports the host, record ratios as well as time:

- cold discovery and index wall divided by the parallel exact-metadata floor;
- warm exact verification divided by the one-metadata-call-per-entry floor;
- full engine plus adapter CPU divided by the aggregate-only tier;
- bytes of settled index memory per retained entry and relative to the compact reference
  layout.

The ratio distinguishes filesystem limits from representation overhead and remains
useful when absolute times change across machines.
Metabrowser should keep its absolute human-perception budgets at the browser layer; the
floor ratio guides engine work.

### Compare All Dimensions That Can Regress

| Dimension | Primary measurements |
| --- | --- |
| Cold usefulness | Server ready, first coherent shallow result, first useful rows, and first final visible viewport |
| Cold completion | Discovery wall, CPU, filesystem calls, throughput, errors, and complete/fresh transition |
| Warm usefulness | Cache header/top-level read through first useful paint, with source and age visible |
| Warm trust | Time and work until displayed subtrees and then the full index are verified |
| Queries | p50, p95, and p99 wall/CPU, lock wait, entries visited, output rows, and copied bytes during scan and settled state |
| Live changes | Filesystem event to verified index, SSE delivery, and painted convergence; coalescing and dirty-path cardinality |
| Churn and recovery | Sustained throughput, burst convergence, queue high-water marks, cursor gaps, stale duration, and rescan scope |
| Concurrency | Writer duty cycle, reader wait, event-loop lag, multi-client throughput, and cancellation latency |
| Memory and persistence | Peak and settled RSS, bytes per entry, snapshot size, first-block read, and lazy-load growth |
| Correctness | Mismatches, conservation failures, partial/error counts, stale-label duration, and resets |

The fdu provider is ready to become the default only when it wins the intended
end-to-end regimes on real trees, stays within every correctness and resource gate, and
does not trade a faster complete scan for a slower first useful viewport or live
interaction. A result that improves one layer and regresses another remains a hypothesis
result, not an adoption result.

## Migration Plan

### Phase 0: Freeze the Contract and Oracles

- Write the semantic records and lifecycle state machine as an architecture document.
- Add the provider-neutral observation and filesystem fixture corpus.
- Make fdu run the File Rollup conformance packet and resolve every mismatch.
- Add a versioned query/ETag test that changes the index while a rollup is built.

**Exit:** the two backends have one executable definition of “same result,” including
partial and trust state.

### Phase 1: Extract the Python Provider

- Introduce the coordinator, provider factory, session, query, event, and result types.
- Move current inventory behavior behind `PythonInventoryBackend`.
- Replace direct singleton and filesystem-existence reads in inventory-serving routes.
- Make snapshot plus version capture atomic and make rollup ETags describe their bodies.
- Keep browser wire goldens unchanged except for deliberately corrected semantics.

**Exit:** the full application runs on the Python provider through the new interface; no
route imports Python inventory internals.

### Phase 2: Complete the fdu Interactive Surface

- Land shared-handle concurrency and File Rollup runtime-registry support first.
- Add configured populations, complete directory facts, coherent bounded query bundles,
  and subtree provenance.
- Add the progressive session and clocked event state.
- Add async watch, scoped reconciliation, polling, and no-gap handoff.
- Expose typed telemetry and exercise the generic embedder example.

**Exit:** fdu passes its own surface parity plus the shared provider conformance suite.

### Phase 3: Add an Explicit fdu Provider

- Package fdu as a first-party dependency on supported platforms.
- Implement translation without a mirror index or second watcher.
- Add `--inventory-backend=python|fdu` and equivalent internal settings.
- Fail fast when explicit fdu selection is unavailable or incompatible.

**Exit:** both providers pass the same Metabrowser tests and can be forced in local and
serving benchmarks.

### Phase 4: Validate Correctness Under Change

- Run static and mutation differential suites on every supported platform.
- Exercise cache, partial failure, watcher overflow, polling, reconnect, cancellation,
  and concurrent read/write scenarios.
- Inspect every wire difference and either eliminate it or record an intentional product
  decision in the architecture and changelog.

**Exit:** no unexplained semantic or lifecycle differences remain.

### Phase 5: Run the Performance Campaign

- Add the provider axis and new regimes to the standing benchmark.
- Select representative real trees through the existing performance workflow.
- Run paired A/B trials with browser-attached and engine-only variants.
- Compare cold, warm, query, change, memory, and physical-floor results.
- Optimize only measured bottlenecks, one hypothesis per experiment.

**Exit:** a review states where the improvement comes from, where it does not transfer,
which regimes regress, and how far each engine tier remains from the measured floor.

### Phase 6: Change the Default and Simplify

- Introduce `auto` only after explicit fdu has passed the gates.
- Select fdu on supported builds and report a specific startup reason when `auto` uses
  Python.
- Keep the Python provider as the small semantic oracle and supported fallback, not as a
  parallel state layer in fdu sessions.
- Remove obsolete walker/rollup coordination from the server and update the architecture
  map and changelog for observable changes.

**Exit:** one provider owns one session at runtime, both providers remain conformant,
and diagnostics and benchmarks always identify the selected engine.

## Options Considered

### Adopt the Stateful Inventory Engine Boundary

**Description:** Extract one internal Metabrowser session/query/event protocol and adapt
the current Python engine and fdu to it.

**Advantages:**

- preserves fdu’s native index, cache, and watcher advantages;
- isolates provider choice from routes and browser wire;
- makes semantic and performance comparison executable;
- retains a simple reference implementation;
- avoids a new package and a public compatibility promise.

**Costs:**

- requires an extraction before the fdu adapter;
- requires both implementations to pass every future contract change;
- makes existing coherence and failure-semantics gaps visible and therefore necessary to
  fix.

### Eliminated: Swap Only the Walker

This leaves the main Python representation and query costs in place, duplicates fdu’s
maintained state, prevents lazy snapshot use, and creates a high-volume FFI stream.
It cannot reach the intended physical limit.

### Eliminated: Invoke the fdu CLI or Parse Its Reports

A subprocess adds startup, serialization, cancellation, and error-mapping costs; CLI
reports answer one-shot questions rather than a live coherent session.
This would throw away the in-process index and make parity depend on a presentation
schema.

### Eliminated: Let Routes Branch on fdu Directly

This minimizes a prototype but distributes backend knowledge through every query and
event path. It also provides no precise contract for the Python implementation and makes
one-version multi-projection reads difficult.

### Eliminated: Maintain Both Engines Live in Production

Dual walking doubles filesystem pressure, changes observation timing, and can disagree
legitimately on a changing tree.
Replay and immutable fixtures provide a better oracle without perturbing the system
under measurement.

## Recommendations

1. Treat the retained inventory engine, not the walker, as the replacement unit.
2. Extract and correct the Python provider before integrating fdu, so the interface is
   proven against the existing application rather than designed around one candidate.
3. Require atomic versioned query results and one cursor for data and trust changes.
4. Make all hot reads bounded and batch multiple projections into one coherent backend
   call. Do not adapt fdu’s current unbounded `children()` directly.
5. Use File Rollup Format and its corpus as the shared classification and rollup
   authority. Metabrowser supplies its registry at runtime; fdu supplies the engine.
6. Prune hidden paths as scope, tag gitignored paths, and maintain only the named
   populations the interactive profile needs.
7. Make cache, partial coverage, filesystem errors, watcher gaps, and provenance visible
   in the same state model.
8. Prove the discovery-to-watch handoff and bounded backpressure behavior before calling
   the event stream resumable.
9. Keep the Python provider as an executable oracle and fallback, not a mirror alongside
   fdu.
10. Evaluate adoption with paired, real-corpus, end-to-end measurements plus
    platform-floor ratios across cold, warm, query, live-change, memory, and correctness
    dimensions.

## Next Steps

- [ ] Convert the shared semantic contract and protocol into a Metabrowser architecture
  document with registered interfaces and invariants.
- [ ] Add a focused correctness task for atomic rollup version/ETag capture in the
  Python provider extraction.
- [ ] Extend the File Rollup conformance corpus with direct fdu execution and close the
  logical-extension differences.
- [ ] Revise fdu pull request 44 around the inventory-engine boundary and the required
  fdu work listed above.
- [ ] Build the provider-neutral observation replay and filesystem scenario harness.
- [ ] Extract `PythonInventoryBackend` and move all inventory-serving routes onto it.
- [ ] Implement the fdu interactive surface and explicit Metabrowser provider.
- [ ] Extend the serving benchmark result schema and run the cross-provider campaign.
- [ ] Record the adoption decision in a performance review after correctness and
  measurement gates pass.

## Methodology

The research read Metabrowser’s development and supply-chain guidance, architecture map,
state-and-delivery design, File Rollup Format and corpus, current load-time plan and
review, performance-loop harness, serving benchmark, walker, inventory, rollup builder,
events, recent-file query, and relevant server routes.

The fdu repository was checked out at pull request 44 commit `64398b7` in a detached,
ignored research clone.
The review covered the pull request plan, engine and surface principles,
progressive-results and interactive-browser research, metadata-walk floor report, Python
API and models, PyO3 binding, engine contract, retained index, public queries,
provenance, snapshot, watch, and logical-extension implementation.

The review compared source-level behavior and recorded measurements.
It did not build or benchmark fdu, validate unimplemented pull request work, or make new
macOS or Windows physical-floor claims.
Open performance decisions therefore remain measurement tasks, while the consistency and
interface findings follow from current code and documented contracts.

## References

- [State and delivery](../architecture/arch-state-and-delivery.md)
- [File Rollup Format](../architecture/file-rollup-format/file-rollup-format.md)
- [Views, models, and routes](../architecture/arch-views-models-routes.md)
- [End-to-end load-time plan](../specs/active/plan-2026-08-21-load-time-performance.md)
- [Load-time performance review](../reviews/review-2026-08-22-load-time-performance.md)
- [Metabrowser performance loop](../../../explorations/performance-loop/README.md)
- [Earlier high-performance rollup research](research-2026-08-06-file-rollup-engine.md)
- [fdu pull request 44](https://github.com/jlevy/fdu/pull/44)
- [fdu interactive-client integration plan](https://github.com/jlevy/fdu/blob/64398b7/docs/project/specs/active/plan-2026-08-23-fdu-interactive-client-integration.md)
- [fdu design principles](https://github.com/jlevy/fdu/blob/64398b7/docs/project/architecture/fdu-design-principles.md)
- [fdu progressive-results plan](https://github.com/jlevy/fdu/blob/64398b7/docs/project/specs/active/plan-2026-08-11-fdu-progressive-results.md)
- [fdu interactive-browser research](https://github.com/jlevy/fdu/blob/64398b7/docs/project/research/research-2026-08-11-interactive-browser-use-case.md)
- [fdu metadata-walk floor report](https://github.com/jlevy/fdu/blob/64398b7/docs/project/reports/report-2026-08-23-metadata-walk-floor.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
