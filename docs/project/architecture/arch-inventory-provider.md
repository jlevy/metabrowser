# Inventory Provider Contract

**Status:** Implemented for the Python reference provider; the fdu provider is planned.

Metabrowser owns a sealed interface between application behavior and the engine that
walks, retains, aggregates, and watches one served root.
The interface lets the Python reference implementation and a future fdu-backed
implementation answer the same requests without exposing either engine’s retained-index
types or concurrency model.

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
 PythonInventoryHandle  FduInventoryHandle (planned)
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

`METABROWSER_INVENTORY_PROVIDER` selects the sealed in-tree factory entry.
Phase 1 accepts only `python`; an unknown value fails explicitly.
The performance harnesses use the same selection axis, so adding `fdu` does not require
a second benchmark path.

## Configuration and Identity

Configuration separates state identity from execution policy:

| Class | Fields | Effect |
| --- | --- | --- |
| Semantic scope | `max_files`, `max_depth`, exact hidden-name allowlist, symlink policy, filesystem-boundary policy, and traversal order | Included in the scope fingerprint; a file-budget stop reports partial coverage |
| Classification | File Rollup registry fingerprint | Contributes to the semantic fingerprint; changing it opens a new session |
| Execution | change-queue size | Reported as a provider fact; does not change a result’s meaning |
| Persistence and observation | cache mode and watch mode | Reported through source, freshness, and diagnostics |

`max_files` limits regular files, not directory rows.
Query `max_rows` bounds each returned page independently, and complete directory-style
consumers follow every continuation.
The walker and watcher both apply `hidden_allowlist`; a name that changes scope cannot
be fingerprinted without also changing observation behavior.

Traversal order is semantic while a file budget can truncate discovery, because it
determines which partial prefix is retained.
The current product scope requires breadth-first traversal and validates that
requirement at runtime.

The current product scope follows neither symlinks nor a one-filesystem policy.
The contract rejects `follow_symlinks=True` and `stay_on_filesystem=True` instead of
letting providers disagree or silently ignore an input.

The scope fingerprint is SHA-256 over the UTF-8 compact JSON array of sorted
`[name, value]` string pairs.
Structured values, currently `hidden_allowlist`, are compact canonical JSON strings
within that outer array.
Every provider adapter uses the application helper that defines this encoding; it does
not hash a language-specific object representation.

An `EngineVersion` consists of a session identity, monotonic sequence, scope
fingerprint, and semantic fingerprint.
The semantic fingerprint changes when any non-scope rule or reducer that can change a
complete answer changes.
A provider with one native fingerprint returns it directly.
A provider with several computes SHA-256 over the UTF-8 canonical JSON array of
`[name, value]` string pairs sorted by name, with no insignificant whitespace.
The Python provider’s sole component is the File Rollup registry, while fdu also
includes its tag rules and reducer registrations.
A `ChangeCursor` contains the same session and sequence at the read boundary.
A provider may implement coherent reads with a lock, an immutable image, or
version-check-and-retry, provided that:

1. a projection cannot mix generations;
2. the returned version and cursor describe the projection’s observation boundary; and
3. a frequent or unbounded read cannot hold a writer indefinitely.

A version-pinned request either returns that version or raises
`VersionUnavailableError`. It never continues on a newer version.
This rule lets the coordinator assemble complete paged catalogs and trees without
joining generations.
`InventoryReadSession` also holds the root and sparse-overlay boundary while those pages
assemble. If the native engine stops retaining the pinned version, the whole bounded
assembly restarts; cursors must advance and the final page must report zero remaining
rows. Exhausted retries fail the request with `VersionUnavailableError`; a complete
consumer never substitutes a partial first page.

The Python provider retains the last coherent root-entry and navigation bundle while its
revision is moving. A repeated root-summary read may return that earlier boundary until
the cost-aware refresh cadence expires.
Its version, cursor, state, and entry projection all remain from the retained boundary;
only recency rows are evaluated at the query’s explicit `as_of_ns`. A settled unchanged
revision reuses the exact memo without copying the index.
A provider with incrementally maintained tallies may always return a newer exact
boundary.

## Closed Query Algebra

`ReadRequest.queries` accepts only the registered records below.
Each record has a request-local `query_id`, and identifiers must be unique within a
bundled read. Output bounds are mandatory at the provider boundary even when an HTTP
route later assembles a complete response from version-pinned pages.

`ReadRequest()` with no projections is the constant-work checkpoint form.
It returns only the coherent version, cursor, lifecycle state, and work envelope.
Routes use it to validate retained bodies before paying for a projection; an empty read
must not traverse inventory entries or manufacture a diagnostics dependency.

| Kind | Query | Required bound | Result |
| --- | --- | --- | --- |
| `entry` | `EntryQuery` | One relative path | Present, absent, or unknown lookup plus filesystem facts |
| `directory` | `DirectoryQuery` | Positive depth and row count | Name-ordered rows, continuation, and exact known remainder |
| `filtered_tree` | `FilteredTreeQuery` | Positive depth and row count | Matching tree rows and selected scalar totals |
| `rollup` | `RollupQuery` | Nonnegative depth and ranking bounds; positive node bound | File Rollup Format payload for one directory |
| `navigation` | `NavigationQuery` | Positive tally-row count | Population, extension, family, preset, and recency tallies |
| `recent` | `RecentQuery` | Positive row count and explicit observation time | Newest matching files, pre-bound match count, and truncation |
| `catalog` | `CatalogQuery` | Positive page size; optional terminal-extension, ancestor-name, and size predicates | Matching file identities, logical extensions, continuation, and exact known remainder from one pinned version |
| `metadata` | `MetadataQuery` | Constant-size session record | Provider, contract, root, and identity facts |
| `diagnostics` | `DiagnosticsQuery` | Constant-size counter record | Provider state, progress, cache, watch, and queue diagnostics |

Recency filters carry `as_of_ns`; an unchanged engine version does not freeze a
time-dependent answer.
Providers may return `valid_until_ns` when the answer has a known expiry.
The coordinator includes that time boundary in request fingerprints, validators, and
retained-body keys. A caller assembling a time-dependent result from several
version-pinned pages chooses one `as_of_ns` before the first page and reuses it for
every page in that assembly.

Catalog terminal extensions use one lowercase terminal suffix including its leading dot;
matching is case-insensitive against the file name.
Ancestor names are exact, case-sensitive path components, and `size_less_than` is an
exclusive byte bound.
These rules are provider semantics, not Python implementation details.

The algebra has no generic report name, provider command, HTTP status, response header,
or provider-specific options map.
Adding a query requires adding its record and result to `REGISTERED_QUERY_TYPES`,
documenting its cost and bound in this table, extending the contract harness, and
implementing it in every production provider.

## Filesystem Records and Host Decorations

`InventoryEntry` contains served-root-relative filesystem facts: lossless path identity,
object type, logical extension, size, modification time, ignore state, and optional
directory aggregates.
Path-bearing contract records use one canonical POSIX-relative grammar: the root is
`""`, absolute paths, backslashes, nulls, `.` and `..` segments, duplicate separators,
and trailing separators are rejected at construction.
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
Entry-bearing projections receive decorations automatically.
Catalog projections return identities rather than entries, so a coordinator caller must
opt in to catalog decorations.
The activity tracker opts in; bulk Quick File delivery does not traverse the overlay.

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
`cancelled`, `inaccessible`, or `failed`. Freshness is `fresh`, `reconciling`, `stale`,
or `partial`. A watcher gap makes freshness stale and adds a typed watcher-gap issue;
coverage changes only if reconciliation discovers or cannot resolve an enumeration hole.
Typed issues also distinguish permission failures, disappearance, invalid metadata,
filesystem-boundary skips, resource stops, and provider failures.
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
That consumer-side reset does not describe a provider observation gap.
A provider watch gap makes answers stale while the provider reconciles the affected
scope when recovery is available; an unrecoverable observer failure remains stale with
its typed issue. The coordinator may continue coherent reads and must not treat either
state as a failed reset recovery.

Refresh and priority requests contain 1 to 1,024 unique canonical paths.
Refresh adds a typed reason; priority adds a positive depth.
A notification remains a hint: a provider verifies filesystem state before applying a
mutation. The primary native-or-polling watcher belongs to the opened provider so
baseline discovery, observation capture, reconciliation, and freshness share one
lifecycle. `refresh()` also accepts bounded external hints from activity probes or
application writes; it is not a second watcher.
If a watch batch cannot be submitted completely, the observer stops and reports a
watcher gap. It never drops one failed chunk and continues while claiming freshness.

## Work and Performance Evidence

Every read and change reports nonnegative counts for entries visited, directories
visited, rows returned, bytes copied across the binding, lock wait, and wall time.
CPU time is an exact nonnegative measurement when present and is unavailable otherwise;
a provider never substitutes zero or infers CPU from wall time.
Diagnostics identify the selected provider and contract.
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
| `/api/tree` | Version-pinned `DirectoryQuery` or `FilteredTreeQuery` pages, with `NavigationQuery` at the same host boundary for root tallies |
| `/api/rollup` and folder hooks | `RollupQuery` |
| `/api/recent` | `RecentQuery` |
| Quick File catalog | Empty checkpoint read followed, on a cache miss, by version-pinned `CatalogQuery` pages; the Python scope fits in one page bounded by `InventoryConfig.max_files` |
| `/api/file` folder facts | `EntryQuery` |
| Initial browser stream | A lossless version-pinned snapshot assembled before atomic queue attachment; covered older changes are suppressed per connection |
| Live browser stream | `changes()` plus coherent rereads |
| Activity discovery | Provider-filtered catalog reads by terminal extension, ancestor name, and size; results update the host overlay |
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
