# Inventory Provider Contract

**Status:** The provider contract is implemented; the Python provider and application
ownership migration are in progress.

Metabrowser owns a sealed interface between application behavior and the engine that
walks, retains, aggregates, and watches one served root.
The interface lets the Python reference implementation and the fdu-backed implementation
answer the same requests without exposing either engine’s retained-index types or
concurrency model.

The provider is authoritative for filesystem facts and aggregate indexes.
The application coordinator owns root selection, host-only decorations, response
caching, browser event projection, and serialization.
Routes depend on the coordinator and cannot select or inspect a provider.

```text
routes and browser event projection
                |
      InventoryCoordinator + overlay
                |
          InventoryHandle
          /             \
 PythonInventoryHandle  FduInventoryHandle
```

`tests/test_inventory_provider_contract.py` checks the registered query types, explicit
bounds, lifecycle invariants, and provider-neutral imports described here.

## One Opened Root

`InventoryBackend.open(root, config)` returns one `InventoryHandle`. Opening does not
wait for a cold scan: the handle reports partial coverage while breadth-first discovery
runs. Its five operations are:

- `read(request)`, which returns one coherent version, cursor, state, typed projections,
  and work record
- `changes(after=cursor)`, a bounded invalidation stream
- `refresh(request)`, for verified filesystem or reconciliation hints
- `prioritize(request)`, which changes discovery order without changing semantics
- `close()`, which cancels and joins provider work before it returns

The application constructs the backend in its lifespan composition root.
A root change closes the old handle, invalidates host caches and cursors, opens the
replacement, and then makes the new coordinator state visible.
Tasks belonging to a closed session cannot publish into the replacement session.

## Configuration and Identity

Configuration separates state identity from execution policy:

| Class | Fields | Effect |
| --- | --- | --- |
| Semantic scope | entry and depth budgets, hidden-name allowlist, symlink and filesystem-boundary policy | Included in the scope fingerprint; a budget stop reports partial coverage |
| Classification | File Rollup registry fingerprint | Included in the registry fingerprint; changing it opens a new session |
| Execution | breadth-first traversal and change-queue size | Reported as provider facts; does not change a complete result’s meaning |
| Persistence and observation | cache mode and watch mode | Reported through source, freshness, and diagnostics |

The current product scope never follows symlinks.
The contract rejects a configuration that asks a provider to do so instead of letting
providers disagree.

An `EngineVersion` consists of a session identity, monotonic sequence, scope
fingerprint, and registry fingerprint.
A `ChangeCursor` contains the same session and sequence at the read boundary.
A provider may implement coherent reads with a lock, an immutable image, or
version-check-and-retry, provided that:

1. a projection cannot mix generations;
2. the returned version and cursor describe the projection’s observation boundary; and
3. a frequent or unbounded read cannot hold a writer indefinitely.

A version-pinned request either returns that version or raises
`VersionUnavailableError`. It never continues on a newer version.
This rule lets the coordinator assemble a complete paged catalog without joining pages
from different generations.

## Closed Query Algebra

`ReadRequest.queries` accepts only the registered records below.
Each record has a request-local `query_id`, and identifiers must be unique within a
bundled read. Output bounds are mandatory at the provider boundary even when an HTTP
route later assembles a complete response from version-pinned pages.

| Kind | Query | Required bound | Result |
| --- | --- | --- | --- |
| `entry` | `EntryQuery` | One relative path | Present, absent, or unknown lookup plus filesystem facts |
| `directory` | `DirectoryQuery` | Positive depth and row count | Name-ordered rows, continuation, and exact known remainder |
| `filtered_tree` | `FilteredTreeQuery` | Positive depth and row count | Matching tree rows and selected scalar totals |
| `rollup` | `RollupQuery` | Positive depth, node, ranking, extension, remainder, and filename counts | File Rollup Format payload for one directory |
| `navigation` | `NavigationQuery` | Positive tally-row count | Population, extension, family, preset, and recency tallies |
| `recent` | `RecentQuery` | Positive row count and explicit observation time | Newest matching files, pre-bound match count, and truncation |
| `catalog` | `CatalogQuery` | Positive page size | Nonignored file identities and logical extensions from one pinned version |
| `metadata` | `MetadataQuery` | Constant-size session record | Provider, contract, root, and identity facts |
| `diagnostics` | `DiagnosticsQuery` | Constant-size counter record | Provider state, progress, cache, watch, and queue diagnostics |

Recency filters carry `as_of_ns`; an unchanged engine version does not freeze a
time-dependent answer.
Providers may return `valid_until_ns` when the answer has a known expiry.
The coordinator includes that time boundary in request fingerprints, validators, and
retained-body keys.

The algebra has no generic report name, provider command, HTTP status, response header,
or provider-specific options map.
Adding a query requires adding its record and result to `REGISTERED_QUERY_TYPES`,
documenting its cost and bound in this table, extending the contract harness, and
implementing it in every production provider.

## Filesystem Records and Host Decorations

`InventoryEntry` contains served-root-relative filesystem facts: lossless path identity,
object type, logical extension, size, modification time, ignore state, and optional
directory aggregates.
A lookup distinguishes:

- `present`: the entry is known and returned
- `absent`: complete coverage proves it is not present
- `unknown`: current coverage cannot prove either state

Symlinks and special objects are visible leaves but do not contribute to regular-file
totals. Hidden components outside the exact-name allowlist are pruned from scope.
Gitignored visible entries remain in the `all` population and are excluded from the
`unignored` population.
File Rollup classification and conservation follow the
[File Rollup Format](file-rollup-format/file-rollup-format.md).

Active state, process labels, preview selections, and plugin labels belong to a sparse
application overlay keyed by the same path identity.
They do not cross the provider contract, advance an engine version, or contribute to
filesystem totals. The coordinator combines the engine version and overlay revision into
the host version used for browser events and caches.

## State and Failures

State reports independent lifecycle, coverage, freshness, source, progress, and issue
facts. The lifecycle transitions are:

```text
opening_cache -> discovering -> reconciling -> watching
      |              |              |             |
      +--------------+--------------+-----------> stopped
      |              |              |             |
      +--------------+--------------+-----------> failed -> stopped

watching -> reconciling -> watching
```

The implementation also permits cache opening to enter reconciliation directly and
discovery to enter watching when no reconciliation is needed.
`stopped` is terminal; `failed` may only transition to `stopped`.

Coverage is either complete with no reason or partial with one of `building`, `budget`,
`cancelled`, `inaccessible`, `watcher_gap`, or `failed`. Freshness is `fresh`,
`reconciling`, `stale`, or `partial`. Typed issues distinguish permission failures,
disappearance, invalid metadata, filesystem-boundary skips, watcher gaps, resource
stops, and provider failures.
Providers preserve the original path and cause when the current layer can handle them.

## Change Delivery

`changes()` yields `ChangeBatch`, not entry replicas or browser events.
Each batch has a resulting version and cursor, state, work counters, and one of:

- bounded dirty paths or query kinds
- `all_dirty` when individual dirtiness exceeds its bound
- `reset` when the requested cursor or consumer queue has a gap
- a state-only transition

The coordinator rereads the affected visible projections, resumes from the read’s
cursor, and projects results into browser events.
A slow consumer causes a reset and coherent reread; it cannot block discovery or receive
a suffix presented as complete.

Refresh requests contain 1 to 1,024 unique paths and a typed reason.
Priority requests contain the same maximum number of paths and a positive depth.
A notification remains a hint: a provider verifies filesystem state before applying a
mutation.

## Work and Performance Evidence

Every read and change reports nonnegative counts for entries visited, directories
visited, rows returned, bytes copied across the binding, lock wait, CPU time, and wall
time. Diagnostics identify the selected provider and contract.
The serving benchmark records the same identities so Python-before, Python-after, and
fdu runs differ by a declared provider axis rather than by separate harnesses.

The common performance gate measures cold discovery, shallow usefulness, settled and
concurrent rollups, tree reads, catalogs, retained bodies, validators, live convergence,
event-loop delay, memory, CPU, I/O, and binding-copy cost.
See the
[end-to-end load-time plan](../specs/active/plan-2026-08-21-load-time-performance.md)
and
[inventory provider plan](../specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md).

## Consumer Mapping

| Consumer | Queries |
| --- | --- |
| `/api/tree` | `DirectoryQuery` or `FilteredTreeQuery`, bundled with `NavigationQuery` for root tallies |
| `/api/rollup` and folder hooks | `RollupQuery` |
| `/api/recent` | `RecentQuery` |
| Quick File catalog | Version-pinned `CatalogQuery` pages |
| `/api/file` folder facts | `EntryQuery` |
| Initial browser stream | Bounded directory and catalog reads followed from their returned cursor |
| Live browser stream | `changes()` plus coherent rereads |
| Activity discovery | Scoped catalog reads; results update the host overlay |
| Index metadata and capabilities | `MetadataQuery` and `DiagnosticsQuery` |

Safe-path validation and file-content reads remain above the engine.
No inventory-serving route performs a second filesystem walk or reads a concrete
provider directly.

## References

- [State and delivery](arch-state-and-delivery.md)
- [Pluggable inventory engine](../specs/active/plan-2026-08-23-pluggable-inventory-engine.md)
- [fdu and Metabrowser inventory-engine alignment](../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
