# Feature: Inventory Provider Refactor and fdu Adoption

**Date:** 2026-08-23 (last updated 2026-08-23)

**Author:** Metabrowser maintainers with OpenAI Codex planning assistance

**Status:** Draft

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
Semantic inputs carry fingerprints.
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
  elapsed CPU and wall time, and bytes copied across the binding.

Metabrowser derives a host version from the returned engine version and overlay
revision.
Routes derive validators and retained-body keys from that host version plus the
canonical request fingerprint and build identity.
A route never samples a revision, dispatches work, and assigns the earlier revision to
the later payload.

Large results are bounded or paged at the provider seam.
When an existing HTTP response is intentionally complete, such as the Quick File
catalog, the coordinator assembles pages from one version-pinned read sequence off the
event loop. A provider may return an explicit restart if it no longer retains that
version; it may not mix pages from two versions.

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
The coordinator joins decorations only onto returned rows and combines overlay changes
with provider invalidations in host event order.

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
- `inventory_engine.providers.python`: the existing Python walker, retained state,
  reducers, refresh, and watcher behavior behind `InventoryHandle`;
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
- [ ] Capture normalized goldens for every row in the preservation table, plus a
  provider-neutral semantic digest for representative complete, progressive, partial,
  ignored, symlinked, and failing trees.
- [ ] Record a back-to-back Python baseline in the existing engine, server, and browser
  performance harness before moving code.
- [ ] Define the sealed factory, protocols, immutable semantic records, and a contract
  test harness. Use a small deterministic test provider only where it proves coordinator
  behavior; do not add a runtime fdu placeholder.

#### Extract Ownership Without a Compatibility Facade

- [ ] Move current retained entries, child indexes, reducers, walker, refresh mutation
  path, and watcher lifecycle into `PythonInventoryHandle` while preserving its
  algorithms and observation semantics.
- [ ] Give every Python read atomic payload/version/cursor capture.
  Fix the existing rollup payload/ETag race and equivalent catalog or snapshot races in
  the same slice.
- [ ] Add `InventoryCoordinator` as the sole application owner, serialize root changes,
  await close, centralize response-cache invalidation, and replace process-wide mutable
  access with explicit dependency access from the application lifespan.
- [ ] Move active state and labels into the sparse overlay while preserving current
  browser event and `/api/activity` behavior.
- [ ] Convert Python mutations into bounded `ChangeBatch` invalidations and implement
  coordinator read-on-dirty, cursor resume, coalescing, all-dirty, reset, and host event
  ordering.

#### Migrate Every Consumer and Remove the Old Seam

- [ ] Move `/api/tree`, `/api/rollup`, `/api/recent`, `/api/catalog`, `/api/index/*`,
  `/api/capabilities`, folder facts in `/api/file`, and folder plugin hooks onto bundled
  coordinator reads.
- [ ] Move tree helpers, recent collection, activity candidate discovery, event routing,
  watcher refresh, diagnostics, tests, and root-reset logic off concrete
  `InventoryIndex` imports.
- [ ] Remove route-level filesystem fallback branches or contain the proven necessary
  behavior in the Python provider with honest source and coverage.
- [ ] Delete the public singleton accessor, old event subscription surface, obsolete
  response revision reads, duplicate walker/index paths, and tests of removed internals.
  Do not retain aliases for in-repository consumers.
- [ ] Add `provider=python` to benchmark inputs and result records, with provider and
  contract identities in diagnostics, even though Python is the only Phase 1 provider.
- [ ] Run the normalized wire, browser, lifecycle, race, bound, work-counter, and
  performance comparisons after each vertical migration slice.

**Phase 1 exit:** Metabrowser ships with only the Python provider and no fdu dependency.
Every inventory consumer crosses the provider-neutral coordinator, one handle owns all
authoritative filesystem state for the root, current product behavior passes the
preservation suite, coherent reads fix torn validators, and the paired performance run
shows no unexplained regression outside harness noise.
Adding a provider requires a factory entry and an `InventoryHandle` implementation, not
a route or browser change.

### Phase 2: Implement and Adopt the fdu Provider

#### Prove the Real Rust Boundary First

- [ ] Refine the linked Metabrowser architecture and fdu integration design until their
  values, bounds, state transitions, registry handoff, and failure semantics match.
- [ ] Build the smallest actual PyO3 spike that opens an fdu shared handle, performs one
  bundled directory-plus-rollup read, returns one version/cursor/state/work record, and
  converges after one live mutation without a Python mirror index.
- [ ] Run that slice through the same provider contract tests and File Rollup packet.
  If translation requires provider-specific branches or lossy values, revise both
  designs and the Python provider before expanding the Rust implementation.

#### Complete the fdu Handle and Thin Adapter

- [ ] Implement the capabilities in
  [Required fdu work](../../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md#required-fdu-work):
  runtime registry and scope inputs, shared retained index, coherent bounded
  projections, complete reducers, progressive open, snapshot and revalidation state,
  resumable changes, verified refresh, watcher handoff, cancellation, and typed
  telemetry.
- [ ] Implement `FduInventoryHandle` as bounded value translation and async/GIL
  management only. Retain no entries, rollups, navigation indexes, cursors, or watcher
  state in the adapter.
- [ ] Add forced `python` and `fdu` selection through the composition root and benchmark
  CLI. An explicit unavailable or incompatible fdu selection fails with provider,
  platform, build, and contract details; it never falls back silently.
- [ ] Run the shared format corpus, normalized observation replay, filesystem scenarios,
  wire goldens, cursor and recovery tests, and forced concurrency interleavings against
  both providers.

#### Measure and Decide the Default

- [ ] Run interleaved Python/fdu comparisons on the same immutable real corpora and
  cache states at the engine, server, and browser layers, with A/A calibration,
  semantic-digest equality, work counters, memory, binding copies, and filesystem-floor
  ratios.
- [ ] Resolve every correctness, resource, interaction, recovery, packaging, or
  supported-platform regression before fdu is considered for automatic selection.
- [ ] Publish the paired performance review and add `auto` only after every adoption
  gate in the broader plan passes.
  Diagnostics record the chosen provider and the exact reason for a Python fallback.
- [ ] Keep Python as the readable semantic oracle and rollback provider.
  Remove any spike-only adapter code or temporary cross-repository shims before Phase 2
  closes.

**Phase 2 exit:** both providers pass the same contract and product suites; the fdu
adapter retains no mirror state; explicit fdu operation is reliable on supported
platforms; and a recorded end-to-end comparison justifies whether `auto` selects fdu.
Routes, browser code, plugins, and wire serializers are unchanged by provider choice.

## Testing Strategy

Phase 1 establishes every provider-independent test and runs it against Python.
Phase 2 adds fdu to the same parametrized harness rather than creating an fdu-only
suite.

- **Contract tests:** query bounds, coherent version and cursor capture, lifecycle,
  typed errors, refresh, change resume, overflow/reset, prompt close, and work records.
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

## Rollout Plan

Phase 1 lands in vertical slices but never leaves two production ownership paths.
Within a slice, producers, consumers, tests, and documentation move together.
The Python provider remains the only selection and current route and plugin behavior
remains available.

Phase 2 first exposes `fdu` as an explicit development and benchmark selection.
Its snapshot identity includes the provider contract, semantic scope, registry, and
native engine identity, so incompatible caches fail closed.
`auto` is added only after the recorded adoption review.
Selecting `python` is the rollback and does not require a second live index or an older
server API.

The repository’s standing compatibility answers apply.
Internal server, route, browser, and built-in plugin consumers update together, so the
refactor keeps no speculative facade around `InventoryIndex` or old event shapes.
A plugin-SDK change, if one becomes necessary, bumps the SDK gate and every built-in
manifest in the same change.

## Open Questions

No unresolved question blocks Phase 1. The contract spike must settle the exact stable
paging token for complete catalog assembly before that consumer migrates.

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
- [fdu contract reconciliation](https://github.com/jlevy/fdu/blob/bd1dcf8/docs/project/research/research-2026-08-23-interactive-contract-reconciliation.md)
- [fdu interactive-client integration plan](https://github.com/jlevy/fdu/blob/bd1dcf8/docs/project/specs/active/plan-2026-08-23-fdu-interactive-client-integration.md)
- [fdu metadata-walk floor report](https://github.com/jlevy/fdu/blob/bd1dcf8/docs/project/reports/report-2026-08-23-metadata-walk-floor.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
