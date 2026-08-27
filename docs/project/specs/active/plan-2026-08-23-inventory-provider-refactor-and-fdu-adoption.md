# Feature: Inventory Provider Refactor and fdu Adoption

**Date:** 2026-08-23 (last updated 2026-08-26)

**Author:** Metabrowser maintainers with OpenAI Codex planning assistance

**Status:** Phase 1 implemented; Phase 2A measured; Phase 2B planned

## Overview

Metabrowser will deliver the pluggable inventory engine in two independently shippable
phases.

Phase 1 moves the existing Python inventory, walker, rollups, watcher integration, and
live delivery behind the final Metabrowser-owned provider contract.
It preserves the current product behavior and ships without an fdu dependency.
At its exit, Python is the only production provider, but routes and browser code no
longer know which provider is running.

Phase 2 implements the same contract with the fdu Rust library through a thin PyO3
adapter. Python remains the reference provider and rollback path.
fdu becomes selectable only after semantic parity, and becomes the automatic default
only after the standing correctness, resource, and end-to-end performance gates pass.

The [pluggable inventory-engine plan](plan-2026-08-23-pluggable-inventory-engine.md)
owns the semantic design and adoption gates.
This document owns implementation order, the Phase 1 preservation boundary, and the
definition of done for each provider.
When a spike exposes a bad seam, both project designs change before either side adds an
adapter workaround.

## Goals

- Make the current Python implementation a complete reference provider behind the same
  contract fdu will implement.
- Keep provider construction in one composition root and run exactly one authoritative
  provider for an opened root.
- Preserve current navigation, rollup, filtering, recency, catalog, activity, live
  update, failure, and partial-scan behavior through the Python refactor.
- Give every read one atomically captured version, cursor, state, and set of projections
  so payloads, retained bodies, and ETags cannot describe different generations.
- Keep filesystem facts inside the selected provider and Metabrowser-only decorations in
  a sparse overlay; do not build a second inventory in the coordinator or adapter.
- Let fdu implement the contract without changes to route handlers, browser code, plugin
  contracts, or wire serializers.
- Add the provider identity to the existing performance framework in Phase 1, then use
  the same measurements for the Python/fdu comparison in Phase 2.
- Delete the old singleton and direct-consumer seams as each migration slice lands.

## Non-Goals

- Requiring fdu, PyO3, Rust build tooling, or an fdu-shaped stub in Phase 1.
- A public third-party backend API, entry-point discovery, capability negotiation, or a
  stable external provider ABI.
- Calling the fdu CLI, parsing fdu reports, or rebuilding fdu’s native index in Python.
- Running Python and fdu against one changing root in production or merging their
  results.
- Preserving internal `InventoryIndex`, `FsEntry`, singleton, event, or route-helper
  APIs after all co-shipped consumers move in the same change.
- Claiming a Phase 1 speedup.
  The refactor should stay within measured harness noise or explain and correct any
  regression before it ships.
- Adding prefix entry deltas, lazy snapshot blocks, or other optional optimizations
  before the measurements in the broader plan require them.

## Design Constraints

### One Composition Root and One Runtime Owner

The application lifespan constructs an `InventoryCoordinator` for one canonical served
root.
The coordinator selects a provider from a sealed in-tree factory, opens one handle,
owns the sparse overlay and host event ordering, and closes the handle before a root
replacement or process shutdown completes.

```text
routes, serializers, and browser wire
                 |
      InventoryCoordinator + overlay
                 |
       InventoryHandle protocol
          /                 \
 PythonInventoryHandle    FduInventoryHandle
       Phase 1                 Phase 2
          |
 _PythonInventoryStore
```

Provider selection appears only in the factory and composition root.
Route modules, SSE projection, recent-file collection, activity discovery, and folder
hooks depend on the coordinator or provider-neutral values.
A source check should fail if those modules import a concrete provider.

A root transition is serialized as close-old, invalidate host caches and cursors,
open-new, then publish the new state.
`close()` cancels and joins discovery, refresh, watch, polling, and adapter work.
No task from the old root may publish after the new handle is visible.

### Sealed Provider Contract

The interface has one factory level and one opened-root level:

```python
class InventoryBackend(Protocol):
    async def open(
        self,
        root: Path,
        config: InventoryConfig,
    ) -> InventoryHandle: ...


class InventoryHandle(Protocol):
    async def read(self, request: ReadRequest) -> ReadResult: ...
    def changes(self, *, after: ChangeCursor | None) -> AsyncIterator[ChangeBatch]: ...
    async def refresh(self, request: RefreshRequest) -> RefreshReceipt: ...
    async def prioritize(self, request: PriorityRequest) -> None: ...
    async def close(self) -> None: ...
```

The protocol contains Metabrowser’s inventory needs, not one method for every current
`InventoryIndex` method and not an fdu report escape hatch.
Its concrete semantic values, bounds, state machine, and error types belong in a new
inventory-engine architecture document.
The
[shared semantic contract](../../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md#shared-semantic-contract)
is the starting point.

`InventoryConfig` separates semantic scope and classification inputs from execution,
cache, watch, and resource policy.
`max_files` is the regular-file discovery budget; directory rows use bounded query pages
and do not consume that budget.
The Python walker and watcher both apply the configured exact hidden-name allowlist.
Unsupported symlink-following and one-filesystem scopes fail at construction.
Semantic inputs use the portable canonical scope-fingerprint encoding defined by the
contract rather than a Python representation.
Execution facts remain telemetry.
An explicit resource stop reports partial coverage and its cause.

### Coherent Closed Reads

`ReadRequest` composes closed, typed projections for entry lookup, directory pages or
bounded trees, filtered trees, rollups, navigation tallies, recent entries, and catalog
pages. The route-to-projection map remains the one in the
[inventory-engine research](../../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md#one-closed-query-algebra-not-a-generic-report-escape-hatch).

Every `ReadResult` returns the following values from one read boundary:

- an opaque engine version and a resume cursor;
- lifecycle phase, coverage, freshness, source, progress, and typed issues;
- the requested typed projections;
- request work, including lock wait, visited entries and directories, returned rows,
  elapsed wall time, exact CPU time when measured, and bytes copied across the binding.
  CPU time is unavailable when the provider cannot measure it exactly; zero never means
  unavailable.

Lifecycle issue count and detail bytes are bounded before they cross the provider
boundary. `DiagnosticsQuery` returns the fixed `ProviderDiagnostics` record used by the
host and performance harness, not an extensible provider-defined mapping.

Metabrowser derives a host version from the returned engine version and overlay
revision.
Routes derive validators and retained-body keys from that host version plus the
canonical request fingerprint and build identity.
A route never samples a revision, dispatches work, and assigns the earlier revision to
the later payload.

Large results are bounded or paged at the provider seam.
When an existing HTTP response is intentionally complete, including Quick File, tree
responses, and the initial browser snapshot, the coordinator assembles pages from one
version-pinned sequence and one sparse-overlay boundary.
A provider may require a full restart if it no longer retains that version; it may not
mix pages from two versions.
If any page has time-dependent semantics, the coordinator chooses one `as_of_ns` before
the first page and reuses it for the complete assembly.

### Live Changes and Sparse Decorations

`changes()` yields bounded invalidations with a cursor, resulting version, dirty paths
or projections, state transitions, and queue/work counters.
It does not send a second copy of the inventory.
On relevant dirtiness, the coordinator performs one bundled coherent read, projects the
result into the current host event behavior, and resumes after the cursor returned by
that read. Overflow produces an all-dirty or reset marker, never a silently incomplete
suffix.

The Python provider may reuse its current batched mutation machinery internally, but
`StreamEvent` and browser wire records do not cross the provider contract.
This ensures Phase 1 proves the live seam that fdu will use instead of preserving a
Python-only event API until Phase 2.

Active state, PID labels, preview choices, and plugin labels live in a sparse overlay
keyed by the same lossless path identity.
The activity tracker reads bounded candidates, updates only the overlay, and submits a
refresh hint when it observes changed filesystem metadata.
Its catalog request carries terminal-extension, ancestor-name, and size predicates so a
native provider returns only candidates across the binding.
The coordinator joins decorations only onto returned rows and combines overlay changes
with provider invalidations in host event order.

The selected provider owns the one primary filesystem watcher.
The Python handle runs the existing native-or-polling observer; the fdu handle will run
its native equivalent.
Both feed verified observations through their own mutation path and expose watcher gaps
as stale freshness plus a typed issue.
They reconcile the affected scope when recovery is available; an unrecoverable observer
failure remains stale.
Coverage changes only if reconciliation discovers or cannot resolve an enumeration hole.
The coordinator invalidates host projection caches and emits browser invalidations from
provider changes, so neither watcher imports application wire types.
Reset and all-dirty changes clear every projection cache; bounded changes invalidate
only their canonical dirty paths.
A failed watcher batch is a watcher gap and stops the observer rather than losing a
suffix while freshness remains green.
A completed refresh accounts for every requested path and returns the provider version
after every accepted observation has passed through that provider’s mutation path.
Providers may publish coherent sub-batches while processing one request; callers use the
receipt as the terminal completion boundary and do not assume a cross-path transaction.

### Behavior Preserved by the Python Provider

Phase 1 treats current product behavior as a regression boundary, even though the
internal APIs can change together.
Preservation does not freeze a named correctness bug: the atomic ETag fix and any other
intentional semantic correction update their producers, consumers, goldens, and
documentation in one slice.

| Surface | Provider-neutral operation | Phase 1 preservation check |
| --- | --- | --- |
| Progressive root open | `open`, `DirectoryQuery`, state | Startup remains nonblocking; breadth-first discovery exposes shallow rows early; pending and partial states stay explicit |
| Files tree and filters | `DirectoryQuery`, `FilteredTreeQuery`, `NavigationQuery` | Tree shape, lazy boundaries, tracked/ignored totals, logical extensions, recency and type filters, and incomplete-state behavior match normalized wire goldens |
| Folder overview and treemap | `RollupQuery` | File Rollup Format, populations, bounds, conservation, ranking, remainder fields, and cache behavior match; payload and ETag use the same returned version |
| Recent files | `RecentQuery` | Window, prefix, extension, ignored-file cap policy, ancestor markers, ordering, totals, and truncation match |
| Quick File catalog | version-pinned `CatalogQuery` pages | The complete nonignored universe, logical extensions, gzip, validators, live convergence, and bounded provider reads match |
| File and folder facts | `EntryQuery` | Safe-path validation remains above the engine; presence is present, absent, or unknown; folder facts do not use a second filesystem truth path |
| Live browser state | `changes` plus coherent reread | Initial snapshot, incremental convergence, reconnect, queue overflow, resync, and per-tab isolation preserve current behavior |
| Activity badges | catalog query plus overlay | Active and PID labels render and age out with the existing cadence without changing filesystem totals or provider versions |
| Watch and refresh | `changes`, `refresh`, state | Native/poll selection, verified mutations, gitignore refresh, watcher failure, root replacement, cancellation, and stale/partial reporting stay visible |
| Diagnostics | state and work records | Existing progress, index metadata, capabilities, request timing, and pending-tally diagnostics remain available and gain the selected provider identity |

Remove current direct-filesystem fallbacks from inventory-serving routes once
progressive-read tests prove the provider covers their user-visible purpose.
If measurement shows one is still necessary, it must live inside the Python provider
with an explicit source and coverage state.
A route cannot retain a parallel path around the coordinator.

### Target Module Boundary

The implementation should converge on a focused package with these responsibilities:

- `inventory_engine.contract`: immutable semantic values, queries, results, state,
  cursors, typed failures, and the two protocols;
- `inventory_engine.coordinator`: root lifecycle, provider-neutral reads, host versions,
  cache invalidation, change-to-host projection, and diagnostics;
- `inventory_engine.overlay`: sparse application decorations and overlay revision;
- `inventory_engine.providers.python_inventory`: the existing Python walker, retained
  state, reducers, refresh, and watcher behavior behind `InventoryHandle`;
- `inventory_engine.providers.fdu`: a Phase 2 translation layer that owns no derived
  state;
- one sealed factory at the composition root.

The final file split may consolidate modules when that improves cohesion.
It may not put provider selection into routes or recreate the current monolith under a
new filename.

## Implementation Plan

### Phase 1: Extract and Ship the Python Reference Provider

#### Fix the Contract and Preservation Baseline

- [x] Add the inventory-engine architecture document with the exact values, query
  algebra, lifecycle transitions, errors, bounds, route mapping, and invariants; link it
  from the architecture map and name the check that keeps registered projections and
  consumers aligned.
- [x] Capture normalized goldens for every row in the preservation table, plus a
  provider-neutral semantic digest for representative complete, progressive, partial,
  ignored, symlinked, and failing trees.
- [x] Record a back-to-back Python baseline in the existing engine, server, and browser
  performance harness before moving code.
- [x] Define the sealed factory, protocols, immutable semantic records, and a contract
  test harness. Use a small deterministic test provider only where it proves coordinator
  behavior; do not add a runtime fdu placeholder.

#### Extract Ownership Without a Compatibility Facade

- [x] Move current retained entries, child indexes, reducers, walker, refresh mutation
  path, and watcher lifecycle behind the five-method `PythonInventoryHandle` façade in a
  private store while preserving algorithms and observation semantics.
- [x] Give every Python read atomic payload/version/cursor capture.
  Fix the existing rollup payload/ETag race and equivalent catalog or snapshot races in
  the same slice.
- [x] Add `InventoryCoordinator` as the sole application owner, serialize root changes,
  await close, centralize response-cache invalidation, and replace process-wide mutable
  access with explicit dependency access from the application lifespan.
- [x] Move active state and labels into the sparse overlay while preserving current
  browser event and `/api/activity` behavior.
- [x] Convert Python mutations into bounded `ChangeBatch` invalidations and implement
  coordinator read-on-dirty, cursor resume, coalescing, all-dirty, reset, and host event
  ordering.

#### Migrate Every Consumer and Remove the Old Seam

- [x] Move `/api/tree`, `/api/rollup`, `/api/recent`, `/api/catalog`, `/api/index/*`,
  `/api/capabilities`, folder facts in `/api/file`, and folder plugin hooks onto bundled
  coordinator reads.
- [x] Move tree helpers, recent collection, activity candidate discovery, event routing,
  watcher refresh, diagnostics, tests, and root-reset logic off concrete
  `InventoryIndex` imports.
- [x] Remove route-level filesystem fallback branches or contain the proven necessary
  behavior in the Python provider with honest source and coverage.
- [x] Delete the public singleton accessor, old event subscription surface, obsolete
  response revision reads, duplicate walker/index paths, and tests of removed internals.
  Do not retain aliases for in-repository consumers.
- [x] Add `provider=python` to benchmark inputs and result records, with provider and
  contract identities in diagnostics, even though Python is the only Phase 1 provider.
- [x] Run the normalized wire, browser, lifecycle, race, bound, work-counter, and
  performance comparisons after each vertical migration slice.
- [x] Reaudit the rebased implementation against the landed large-tree performance work.
  Preserve cooperative discovery yields, tree-first browser startup, bounded navigation
  refreshes, exact catalog invalidation, constant-work cache hits, off-loop bulk catalog
  materialization, and one Python catalog scan per complete response.
- [x] Make an empty projection bundle the explicit constant-work checkpoint read, so
  validators and retained-body caches can observe a coherent provider boundary without
  coupling either provider to a dummy metadata or diagnostics query.
- [x] Harden the reviewed seam: rename the Python provider module descriptively, enforce
  canonical paths and unique priority requests, apply semantic scope inputs, distinguish
  the file budget from page rows, assemble complete tree pages at one host boundary,
  attach snapshots without a stale-delta gap, fail closed on watcher-batch loss, and
  invalidate projection caches on broad changes, and define catalog predicate semantics
  independently of the host Python version.
- [x] Remove the superseded Python-only filtered-tree reducer and unused metadata query,
  replace open-ended diagnostics with a typed record, bound lifecycle issues, return a
  terminal version from refresh, and avoid repeating full Python tree projection work
  across continuation pages.

**Phase 1 exit:** Metabrowser ships with only the Python provider and no fdu dependency.
Every inventory consumer crosses the provider-neutral coordinator, one handle owns all
authoritative filesystem state for the root, current product behavior passes the
preservation suite, coherent reads fix torn validators, and the paired performance run
shows no unexplained regression outside harness noise.
Adding a provider requires a factory entry and an `InventoryHandle` implementation, not
a route or browser change.

### Phase 2: Implement and Adopt the fdu Provider

The reviewed fdu design and implementation are in
[fdu pull request 48](https://github.com/jlevy/fdu/pull/48). Its
`plan-2026-08-25-fdu-opened-root-inventory-engine.md` is the cross-repository execution
map.
Pull requests 44 and 47 remain research and implementation sources; neither owns the
current contract.

#### Checkpoint 2A: Measure the Unchanged Contract

- [x] Build and install an exact fdu wheel from revision `0583a1a`; reject a sibling
  source-tree import and record the wheel digest.
- [x] Inject a disposable fdu backend directly into `InventoryCoordinator` without
  changing the shipping factory or Python default.
- [x] Run the registered provider cases, selected route and SSE tests, one repository
  corpus, and a complete open-to-close application lifecycle.
- [x] Record every temporary full materialization, sort, aggregate pass, binding page,
  latency, and memory observation in
  [the exact-wheel spike](../../../../explorations/fdu-inventory-adapter/README.md).

The spike proves that the public Python handle has the required lifecycle shape.
It also shows why the unchanged contract cannot be the durable boundary: resource
refusal, journal capacity, discovery barriers, and recursive-removal coalescing need
explicit shared rules.
Complete materialization and Python projection work are measured duplication, not an
acceptable adapter implementation.

#### Checkpoint 2B: Revise the Contract and Python Oracle

- [ ] Pass immutable registry content at open instead of trusting a caller-supplied
  fingerprint. Derive both scope and semantic identities inside each provider.
- [ ] Make discovery budget execution policy with honest partial state, and move maximum
  depth to bounded read selection.
  Name hidden, symlink, filesystem-boundary, and object-kind scope explicitly.
- [ ] Align lifecycle, coverage, freshness, source, and issue values with fdu’s total
  vocabulary. Resource refusal is terminal for expansion and observation rather than a
  nominally watching state.
- [ ] Add request work limits and typed limit results.
  Replace exact suffix remainders with opaque continuations plus exact-or-capped totals,
  stable version pinning, and portable-path completeness.
- [ ] Specify one active change iterator, provider-batch replay capacity, iterator-only
  cancellation, reset semantics, and the host coalescing boundary for recursive changes.
- [ ] Update the Python provider, coordinator, page assembly, routes, and the closed
  conformance registry.
  The Python provider must pass before fdu is registered.

The resource-stop slice is complete: the Python reference provider remains readable,
reports partial budget coverage in terminal `stopped`, and joins its watcher with an
explicit `resource_budget` diagnostic.
It still verifies retained leaves, rejects refreshes that could expand the stopped
scope, and treats priority hints as inert.

#### Checkpoint 2C: Add Native Projections and the Thin Adapter

- [ ] Add only the maintained native structures justified by Checkpoint 2A: path order,
  timestamp and catalog order, registry dimensions, fixed partitions, and navigation
  presets. Each structure must name the measured pass or sort it removes.
- [ ] Add bounded version-pinned tree, flat, filtered-tree, rollup, navigation, recent,
  catalog, and diagnostics projections with opaque handle-local continuations.
- [ ] Implement `FduInventoryBackend` as total value translation and one application-
  owned async change bridge.
  It retains the native handle but no entry mirror, aggregate store, filesystem walker,
  fingerprint recipe, or MetaBrowser policy.
- [ ] Give each handle one dedicated bounded poll worker.
  Iterator cancellation joins only the bridge and preserves the handle; handle close
  joins the bridge and native opened root.
  A second active iterator fails explicitly.
- [ ] Add explicit `python` and `fdu` factory choices plus an optional exact fdu
  package. Missing or incompatible native artifacts are typed startup failures.
  Python remains the default, and an explicit fdu request never falls back silently.
- [ ] Delete the disposable materializing adapter and its temporary instrumentation.
  Retain the reproducible harness, normalized evidence, and report.

#### Checkpoint 2D: Prove the Composed Product

- [ ] Run the same provider conformance registry, File Rollup packet, route tests, and
  deterministic observation sessions against Python and fdu.
- [ ] Record a normalized golden session covering progressive open, bounded reads and
  paging, live mutation, refresh, replay loss, iterator cancellation, root replacement,
  and joined close. Normalize only generated identities, time, and platform metadata;
  preserve complete stable request, result, state, impact, work, route, and SSE
  payloads.
- [ ] Build the exact fdu revision as a wheel in a clean MetaBrowser environment on
  every supported Python and platform job.
  A source-tree import must not make integration pass.
- [ ] Run interleaved Python/fdu comparisons on immutable real corpora with A/A
  calibration, semantic equality, work counters, memory, binding copies, and
  filesystem-floor ratios.
- [ ] Resolve every correctness, resource, interaction, recovery, packaging, and
  supported-platform regression.
  Any default change is a separate reversible decision after these gates; this
  implementation phase does not add an `auto` fallback.

**Phase 2 exit:** both providers pass the same contract and product suites; the fdu
adapter retains no mirror state; explicit fdu operation is reliable on supported
platforms; and the recorded end-to-end comparison is sufficient for a separate default
decision. Routes, browser code, plugins, and wire serializers are unchanged by provider
choice.

## Testing Strategy

Phase 1 establishes every provider-independent test and runs it against Python.
Phase 2 adds fdu to the same parametrized harness rather than creating an fdu-only
suite.

- **Contract tests:** query bounds, coherent version and cursor capture, lifecycle,
  bounded typed issues and diagnostics, terminal refresh receipts, change resume,
  overflow/reset, prompt close, and work records.
- **Preservation tests:** normalized route and SSE goldens, existing DOM behavior,
  plugin hooks, root replacement, progress, partial and failure states, active overlays,
  and HTTP caching.
- **Semantic oracles:** the File Rollup packet, normalized observation replay after each
  mutation barrier, and static plus stepwise-mutated filesystem scenarios.
- **Concurrency tests:** reads during discovery and writes, mutation during a bundled
  read, subscriber overflow, cancellation, root replacement, read/close races, and PyO3
  work with the GIL released.
- **Structural tests:** no inventory consumer imports a concrete provider, no route
  reads provider revisions separately from results, and provider-specific values stop at
  the adapter.
- **Performance tests:** deterministic work-counter and bound assertions in CI; paired
  wall-clock, CPU, memory, event-loop, browser, and physical-floor measurements on the
  controlled performance host.

Shared CI does not use wall-clock thresholds.
A Phase 1 regression or Phase 2 adoption decision uses a same-host before/after run and
the standing performance-loop method.

### Phase 1 Preservation Evidence

The provider-parametrized registry in
`docs/project/architecture/arch-inventory-provider.md` is the Phase 2 parity entry
point. Its maintained tests cover coherent checkpoints, time-pinned paging, semantic
digests, explicit budget stops, lossless remainders, unavailable versions, change resume
and reset recovery, verified refresh, joined close, lifecycle, and session stability.
`tests/test_python_inventory_provider.py` adds implementation-specific progressive,
failure, refresh, paging, bound, and work-counter checks for the reference store without
expanding the public handle.

The existing product suites remain the wire and browser preservation oracle:

| Surface | Evidence |
| --- | --- |
| Progressive open and lifecycle | `tests/test_startup_nonblocking.py`, `tests/test_browser_lifespan_e2e.py` |
| Tree, filters, and folder facts | `tests/test_browser_walk.py`, `tests/test_tree_filter.py`, `tests/test_api_folder_envelope.py` |
| Rollups and validators | `tests/test_inventory_rollup.py`, `tests/test_rollup_route.py`, `tests/test_browser_rollup.py` |
| Recent files and catalog | `tests/test_browser_recent.py`, `tests/test_catalog_feed_server.py` |
| Live delivery and recovery | `tests/test_e2e_filesystem_to_sse.py`, `tests/test_browser_events_route.py` |
| Activity overlay | `tests/test_browser_active_tracker.py`, `tests/test_inventory_overlay.py` |
| Watch, refresh, and root replacement | `tests/test_browser_watch_backends.py`, `tests/test_inventory_coordinator.py` |
| Diagnostics and provider-neutral ownership | `tests/test_perf_instrumentation.py`, `tests/test_inventory_provider_ownership.py` |

The serving comparison uses the same 100,000-file corpus and the `--provider python`
axis shown in the performance-loop documentation.
The corrected harness waits for a visible filesystem mutation and a changed ETag before
timing fresh aggregation, rejects failed route responses, and samples process resources
only after discovery completes so the instrumentation does not perturb the cold walk.
It separately times first-pass and memoized navigation reads and the catalog’s first
body, retained body, and `304` paths.
The harness checks the navigation count against the settled walker and requires repeated
catalog bodies and validators to agree.

## Rollout Plan

Phase 1 lands in vertical slices but never leaves two production ownership paths.
Within a slice, producers, consumers, tests, and documentation move together.
The Python provider remains the only selection and current route and plugin behavior
remains available.

Phase 2 first exposes `fdu` as an explicit development and benchmark selection.
Its snapshot identity includes the provider contract, semantic scope, registry, and
native engine identity, so incompatible caches fail closed.
The engine version’s semantic fingerprint also covers every answer-affecting tag rule
and reducer registration, not only the File Rollup registry.
`auto` is added only after the recorded adoption review.
Selecting `python` is the rollback and does not require a second live index or an older
server API.

The repository’s standing compatibility answers apply.
Internal server, route, browser, and built-in plugin consumers update together, so the
refactor keeps no speculative facade around `InventoryIndex` or old event shapes.
A plugin-SDK change, if one becomes necessary, bumps the SDK gate and every built-in
manifest in the same change.

## Open Questions

Phase 1 has no unresolved contract question.
Complete catalog and tree assembly use bounded continuations, one version-pinned read
sequence, and one host-overlay boundary.
Initial stream attachment adds a per-connection version floor, so an older queued
invalidation cannot follow a newer snapshot.

Two Phase 2 optimizations remain measurement-gated:

- whether prefix or catalog entry deltas beat invalidation plus bounded coherent reads;
- whether bulk snapshot load and revalidation miss the warm-usefulness budget at a
  supported corpus and require lazy blocks.

## References

- [Pluggable inventory engine](plan-2026-08-23-pluggable-inventory-engine.md)
- [fdu and Metabrowser inventory-engine alignment](../../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md)
- [State and delivery](../../architecture/arch-state-and-delivery.md)
- [File Rollup Format](../../architecture/file-rollup-format/file-rollup-format.md)
- [End-to-end load time](plan-2026-08-21-load-time-performance.md)
- [Metabrowser performance loop](../../../../explorations/performance-loop/README.md)
- [fdu pull request 44](https://github.com/jlevy/fdu/pull/44)
- [fdu pull request 47](https://github.com/jlevy/fdu/pull/47)
- [fdu pull request 48](https://github.com/jlevy/fdu/pull/48)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
