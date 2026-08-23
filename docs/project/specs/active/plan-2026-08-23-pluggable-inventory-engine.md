# Feature: Pluggable Inventory Engine

**Date:** 2026-08-23 (last updated 2026-08-23)

**Author:** Metabrowser maintainers with OpenAI Codex planning assistance

**Status:** In Review

## Overview

Metabrowser will put filesystem discovery, retained metadata, rollups, coherent queries,
and live reconciliation behind one sealed inventory-engine contract.
The current Python implementation becomes the reference backend.
fdu becomes the high-performance backend.
Exactly one backend owns the authoritative inventory for an opened root.

The contract is deliberately smaller than either implementation.
It exposes bounded, versioned reads and a resumable invalidation stream; it does not
expose walker records, HTTP models, fdu reports, or a generic plugin ABI. Metabrowser
owns browser-facing wire models and sparse application decorations.
fdu owns its native index, reducers, persistence, discovery, and watch lifecycle.

The design comes from the
[inventory-engine research](../../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md)
and the
[fdu-side reconciliation](https://github.com/jlevy/fdu/blob/bd1dcf8/docs/project/research/research-2026-08-23-interactive-contract-reconciliation.md).
Because both projects can change together, the repository boundary is for focused
context, not compatibility negotiation.
The implementation proceeds through executable cross-seam spikes.
A spike that disproves the contract changes both designs before more production code is
built.

## Goals

- Run the complete Metabrowser filesystem experience on either a Python or fdu backend
  without route or browser branches for the selected implementation.
- Preserve one coherent version across every projection used to build a response, and
  derive retained bodies and ETags from that returned version.
- Keep frequent reads, change delivery, queues, and binding copies explicitly bounded;
  expose work counters that reveal accidental whole-index work.
- Make File Rollup derivation, classification, populations, bounds, and conservation
  identical through one Metabrowser-authored, revision-pinned conformance packet.
- Preserve honest partial coverage, cache provenance, trust transitions, and a no-gap
  handoff from baseline discovery or revalidation to watching.
- Replace implicit file and depth correctness caps with explicit resource budgets whose
  results report partial coverage and its cause.
- Compare both backends through the standing performance framework at the engine,
  server, and browser layers, including ratios to measured filesystem floors.
- Keep the Python backend small enough to remain an understandable semantic oracle and a
  supported fallback.

## Non-Goals

- A public third-party backend SDK, entry-point discovery, or a stable provider ABI.
- A generic query language or report escape hatch.
- fdu-specific types in routes, SSE payloads, browser code, or plugin contracts.
- A Python mirror of the fdu index, a second watcher, or dual live engines in
  production.
- Per-entry cold-scan delivery across PyO3.
- Prefix entry deltas or lazy snapshot blocks before measurements show that the simpler
  read-on-dirty and bulk-load designs miss a product budget.
- Preserving internal `InventoryIndex`, `/api/*`, SSE, or browser-shell shapes when all
  consumers can change in the same release.

## Background

The current `InventoryIndex` combines traversal, retained records, aggregates, queries,
watching, and event delivery.
Replacing only its walker would still allocate and update the Python index, repeat
whole-tree queries, and serialize native observations that fdu already retains.
The replacement unit must therefore be the stateful engine.

fdu pull request [#44](https://github.com/jlevy/fdu/pull/44) already points at the same
boundary. Its follow-up review validates the shared-read, runtime-registry, maintained
rollup, progressive-open, and watch work, while narrowing three premature requirements:

- live delivery starts with bounded dirtiness and read-on-dirty, not prefix entry
  streams;
- bulk snapshot load and revalidation ship before on-demand snapshot blocks;
- the full maintained reducer union must be measured together.

Metabrowser already exports a self-contained File Rollup adoption packet as documented
under
[File Rollup Format maintenance](../../../development.md#file-rollup-format-maintenance).
The missing conformance fact is logical-extension derivation: current metadata cases
supply `logical_extension` to the classifier.
The first spike closes that gap before the packet becomes the cross-repository oracle.

## Design

### Boundary and Ownership

At runtime the flow is:

```text
routes and browser wire
        |
inventory coordinator + sparse overlay
        |
sealed typed contract
        |
Python backend  OR  fdu adapter -> native fdu engine
```

The coordinator selects and opens one backend, maps route needs to typed projections,
joins sparse Metabrowser-only decorations onto bounded rows, projects change
invalidations into SSE behavior, and serializes wire models.
It never stores a second filesystem inventory.

The backend owns path facts, classification, retained entries, directory reducers, query
indexes, snapshots, discovery, reconciliation, and watch state.
The fdu adapter translates one bounded batch at a time and retains no derived state.
File contents, preview selection, active state, plugin labels, and other application
decorations stay above the boundary.

Both providers implement the
[shared semantic contract](../../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md#shared-semantic-contract).
Contract paths are relative to one canonical root and retain lossless native component
identity; display strings and reversible HTTP encoding stay above the engine.

### Minimum Contract

Names may be refined in the contract spike, but the two-level shape is fixed:

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

`InventoryHandle` avoids adding another type called `Session` beside fdu’s progressive
scan and watch lifecycles.
Those fdu surfaces must also have distinct descriptive names before they enter the
Python binding.

This is an internal contract for two in-tree implementations.
It has no general capability negotiation.
A genuine platform gap, such as the absence of a native watch backend, appears in
lifecycle state and diagnostics and selects the documented polling policy.

`open()` returns an immediately readable handle while cold discovery or warm
revalidation continues.
`close()` owns cancellation and joins every backend worker.
`refresh()` submits a hint; the backend verifies filesystem state and applies changes
through its one mutation path.
`prioritize()` changes scheduling without changing scope or cache identity.

### Coherent Read Algebra

A `ReadRequest` bundles one or more closed projections.
The initial set is entry lookup, directory page or bounded tree, filtered tree, rollup,
navigation tallies, recent files, and catalog page.
The detailed semantics and route mapping remain in the
[research document](../../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md#one-closed-query-algebra-not-a-generic-report-escape-hatch).

Every `ReadResult` contains:

- one opaque engine version and a change cursor captured at the same read boundary;
- lifecycle, coverage, freshness, source, progress, and typed issues;
- the requested typed projections;
- scope and registry fingerprints;
- lock wait, entries and directories visited, rows returned, query CPU and wall time,
  and bytes copied across the binding.

The result is coherent as a whole.
A backend may use a shared guard, an immutable read image, or checked retry internally,
but no response may mix generations.
Frequent reads must be proportional to the requested output or a maintained index, not
an unreported full-tree pass.
Child rows carry scalar directory facts; extension breakdowns come from a separate
bounded rollup projection.

Metabrowser builds an HTTP cache key from the returned engine version, sparse-overlay
revision, canonical request fingerprint, and application build identity.
It never reads a revision before dispatch and associates that earlier value with a later
payload. Time-dependent projections carry an explicit `as_of_ns` or validity boundary.

### Change and Trust Contract

The first `ChangeBatch` is a bounded invalidation record containing:

- a cursor and resulting engine version;
- dirty directory prefixes or named projections;
- lifecycle, coverage, freshness, provenance, issue, and progress transitions;
- work and queue counters;
- an all-dirty marker when the dirty set exceeds its bound, or a reset marker when a
  retained cursor has a gap.

It does not carry entry rows.
On relevant dirtiness, the coordinator performs a coherent read and resumes from the
cursor returned by that read.
Dirty prefixes coalesce, and a shallower prefix may dominate its descendants when it
invalidates the same projection.
A gap is explicit and forces bounded re-reads; a slow consumer never stalls discovery.

Trust participates in the same clock as data.
fdu should aggregate revalidation state, for example with an unverified-descendant count
whose zero crossing dirties the subtree, instead of emitting millions of provenance-only
entry changes. Coverage is monotone only during additive discovery; every other
transition carries its phase and cause.

Prefix-scoped entry deltas and catalog deltas are optional optimizations.
They enter the contract only after a live-change A/B test shows lower end-to-end latency
and copy cost than invalidation plus bounded read.

### Shared Classification Packet

Metabrowser remains the source of truth for File Rollup Format and its recommended
registry. At open, either backend receives the same immutable registry packet and
expected identity. It validates the packet once and returns the identity it indexed;
disagreement fails the open.

The conformance packet is exported at a reviewed Metabrowser source revision and
committed into fdu. fdu CI verifies its manifest and hashes locally.
There is no network fetch, sibling checkout, package import, or third shared package.

Before the first export, the conformance schema gains direct logical extension cases
from basenames, while classification cases continue to test matching independently.
The packet must cover at least:

- bounded two-component derivation, eligibility, case folding, dotfiles, and long dotted
  names;
- `release.v2.zip` deriving `.v2.zip` and suffix-matching canonical `.zip`;
- `bundle.umd.min.js` deriving `.min.js` and suffix-matching canonical `.js`;
- preservation of unknown compound extensions in `remaining_types`.

Provider parity fixtures separately prove that navigation tallies, literal filters,
recent rows, and catalog rows retain the raw logical extension even when classification
uses a canonical suffix.

### Scope, Persistence, and Cost

The interactive profile prunes hidden paths except for an exact allowlist, retains and
tags visible gitignored paths with full negation and directory semantics, and maintains
`all` and `unignored` populations.
Hidden control files may be read without being retained.
Semantic scope and registry inputs are fingerprinted; traversal order, worker count,
batching, and priority are telemetry rather than cache identity.

Warm open first uses persisted reducers plus bulk snapshot load and background
revalidation with explicit source and freshness.
Lazy blocks become required only if this path misses the existing warm-usefulness budget
at a supported scale.

The maintained-state benchmark prices populations, groups, composed subtree provenance,
and non-directory leaf counts together on a dense real corpus.
The final representation must be chosen from that combined measurement, because all four
share the ancestor merge path.

### Performance Contract

The provider becomes a first-class axis of the existing
[load-time plan](plan-2026-08-21-load-time-performance.md) and
[performance loop](../../../../explorations/performance-loop/README.md).
Existing browser-perception budgets remain the product gates; this plan does not copy
values that the benchmark source already reports.

Every comparison has three paired layers:

1. engine-only discovery, persistence, query, change application, memory, and fdu floor
   ratio;
2. server startup, route latency, event-loop delay, serialization, and binding copies;
3. browser first usable rows, interaction during discovery, live convergence, and
   settled responsiveness.

Trials use the same immutable real corpus and cache state, interleave Python and fdu
pairs, include A/A calibration, and compare semantic digests before timing results are
accepted. Generated shapes isolate mechanisms but do not establish the product claim.
The loop continues against the largest measured source of non-filesystem cost until a
candidate improvement is inside harness noise or would regress a correctness or resource
gate.

## Components

- A focused `metabrowser.inventory_engine` package for semantic values, the sealed
  contract, coordinator, Python backend, fdu adapter, and sparse overlay.
- The existing File Rollup exporter, schemas, generated corpus, and packet verifier.
- fdu’s shared native index, runtime registry, coherent multi-projection read, reducers,
  progressive lifecycle, snapshot, watch, and PyO3 surfaces.
- Route and SSE adapters for tree, rollup, recent files, catalog, path lookup, and
  navigation tallies.
- Provider-neutral replay fixtures, filesystem scenarios, normalized wire goldens, and
  performance result schemas.

The implementation may choose a smaller module split after the spikes.
It must not put provider selection branches back into route modules or rebuild another
`inventory.py` monolith.

## API Changes

All changes are internal and land with their consumers:

- add explicit `python` and `fdu` provider selection for development and benchmarks;
- add `auto` only after the fdu adoption gates pass;
- replace direct `InventoryIndex` and filesystem-existence reads in inventory-serving
  routes with coordinator reads;
- update SSE and browser behavior to consume invalidations and perform bounded reads;
- report selected backend, fallback reason, lifecycle state, fingerprints, and work
  counters in diagnostics;
- fail an explicit `fdu` selection when its wheel, platform surface, or contract is
  unavailable or incompatible; only `auto` may choose Python and must report why.

Observable wire or plugin-SDK changes update every built-in consumer atomically and
follow the repository’s changelog and SDK-version rules.
No compatibility facade is kept around `InventoryIndex` or old event records without a
named external consumer.

## Implementation Plan

The
[inventory-provider refactor and fdu adoption plan](plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md)
is the implementation spec.
It has two independently shippable phases: extract and ship the Python reference
provider, then implement and evaluate the fdu provider against the same contract.

This document remains authoritative for the semantic contract, cross-provider test
oracles, performance method, and adoption gates.
A spike that changes those decisions updates this plan, the implementation spec, and the
linked fdu design before more code is built.

## Testing Strategy

The deterministic CI gates are:

- packet generation, schema validation, manifest verification, and execution by both
  classifiers and aggregate engines;
- normalized static parity for entries, classification, rollups, populations, bounds,
  states, issues, and route wire goldens;
- observation replay after every mutation barrier;
- filesystem scenarios for hidden and gitignored paths, path encodings, symlinks,
  special objects, permission failures, replacement races, overflow, cancellation, cache
  mismatch, and watch-to-poll transitions;
- forced interleavings proving coherent multi-projection reads, atomic ETags, cursor
  resume, no-gap baseline handoff, prompt close, and no GIL-held native work;
- conservation and declared-bound assertions at every complete published version;
- work-counter ceilings that catch full-index visits or unbounded binding copies on hot
  projections.

Wall-clock thresholds do not gate shared CI. Performance acceptance comes from the
standing paired benchmark on controlled real subjects.
Each recorded trial includes the provider, source revision, corpus identity, cache
state, lifecycle source and freshness, work counters, semantic digest, and all three
layer results.

## Adoption Gates

fdu may become the automatic default only when:

- all static, mutation, cache, failure, cursor, conservation, and wire differences are
  either eliminated or recorded as intentional product changes;
- every query and queue enforces its declared record or byte bound and reports exact
  remainder, all-dirty, or reset state;
- no implicit file or depth cap presents a partial inventory as complete;
- reads during discovery, reconciliation, watch commits, cancellation, and close do not
  tear, deadlock, starve the event loop, or expose a Python borrow failure;
- cold and warm usefulness meet the existing load-time budgets, and no server or browser
  layer hides a regression behind a faster engine result;
- live changes converge within the measured product budget under ordinary edits and
  recover correctly under bursts and gaps;
- peak and settled memory, snapshot size, CPU, and binding copies are acceptable on the
  largest supported corpus;
- the performance review reports paired results, uncertainty, regressions, and distance
  from the filesystem floor rather than only a headline speedup.

## Rollout Plan

The Python backend remains the default while the contract and live spikes run.
The fdu backend then ships as an explicit experimental choice in development and
benchmark surfaces. An explicit request never falls back silently.

After the adoption review, `auto` may select fdu on supported platforms and Python
elsewhere, with a concrete reason in diagnostics.
Selecting Python is the rollback; it does not require retaining parallel state or an old
route API. Cache and registry fingerprints make snapshots fail closed when either
implementation changes semantics.

## Open Questions

No unresolved semantic question blocks Phase 1. Two optimization questions stay open on
purpose and are answered by the Phase 2 A/B measurements:

- Do prefix or catalog entry deltas beat bounded invalidation plus coherent read for a
  real live browser workload?
- At what supported corpus, if any, does bulk snapshot load plus revalidation miss the
  warm-usefulness budget and require lazy blocks?

Whether fdu’s compiled CLI-default registry adopts the File Rollup derivation is an fdu
product decision. It does not affect a Metabrowser inventory handle, which supplies and
verifies its own registry packet.

## References

- [Inventory-engine research](../../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md)
- [File Rollup Format](../../architecture/file-rollup-format/file-rollup-format.md)
- [File Rollup maintenance and packet export](../../../development.md#file-rollup-format-maintenance)
- [State and delivery](../../architecture/arch-state-and-delivery.md)
- [End-to-end load-time plan](plan-2026-08-21-load-time-performance.md)
- [Load-time performance review](../../reviews/review-2026-08-22-load-time-performance.md)
- [Metabrowser performance loop](../../../../explorations/performance-loop/README.md)
- [fdu pull request 44](https://github.com/jlevy/fdu/pull/44)
- [fdu contract reconciliation](https://github.com/jlevy/fdu/blob/bd1dcf8/docs/project/research/research-2026-08-23-interactive-contract-reconciliation.md)
- [fdu interactive-client integration plan](https://github.com/jlevy/fdu/blob/bd1dcf8/docs/project/specs/active/plan-2026-08-23-fdu-interactive-client-integration.md)
- [fdu progressive-results plan](https://github.com/jlevy/fdu/blob/bd1dcf8/docs/project/specs/active/plan-2026-08-11-fdu-progressive-results.md)
- [fdu metadata-walk floor report](https://github.com/jlevy/fdu/blob/bd1dcf8/docs/project/reports/report-2026-08-23-metadata-walk-floor.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
