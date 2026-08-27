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
 _PythonInventoryStore  fdu-backed store (planned)
```

`InventoryHandle` is a structural protocol, not a wrapper class.
The private Python store implements its five operations directly and also owns walking,
watching, retained indexes, and projection execution.
Those implementation helpers remain private without a forwarding object that duplicates
the provider API.

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
The provider session, scope fingerprint, and semantic fingerprint are immutable for the
life of a handle. A read or refresh carrying different identity raises
`InventoryConsistencyError`; the change relay treats the same violation as provider
failure and publishes a host reset so stream consumers recover coherently.
Every concurrent `close()` caller joins the same shutdown before returning.

`METABROWSER_INVENTORY_PROVIDER` selects the sealed in-tree factory entry.
Phase 1 accepts only `python`; an unknown value fails explicitly.
The performance harnesses use the same selection axis, so adding `fdu` does not require
a second benchmark path.

## Configuration and Identity

Configuration separates state identity from execution policy:

| Class | Fields | Effect |
| --- | --- | --- |
| Semantic filesystem scope | hidden admission and exact allowlist, symlink following, filesystem boundary, and admitted object kinds | Included in the versioned scope fingerprint |
| Classification | Immutable File Rollup registry document | Parsed by each provider; its provider-derived identity contributes to the semantic fingerprint |
| Execution | discovery budget and change-queue size | A budget stop reports partial coverage but does not redefine semantic scope |
| Observation | watch mode | Reported through source, freshness, and diagnostics |
| Selection | depth, row, and work bounds carried by each query | Changes one answer without changing the opened root’s identity |

`DiscoveryBudget.max_files` limits regular files, not directory rows.
Query `max_rows` bounds each returned page independently, and complete directory-style
consumers follow every continuation.
Metabrowser route and initial-stream tree assembly use `INVENTORY_TREE_PAGE_ROWS` rather
than reusing the `INVENTORY_MAX_FILES` discovery budget.
One `ReadRequest` contains at most `MAX_QUERIES_PER_READ` queries, which also bounds a
dirty-path projection batch.
The opened provider discovers without a depth limit.
The walker and watcher both apply `hidden_allowlist`; a name that changes scope cannot
be fingerprinted without also changing observation behavior.

Traversal is breadth-first.
The v1 contract names and validates one observation-compatible scope: hidden components
are excluded except for the allowlist, symlinks are visible leaves and never followed,
filesystem boundaries are crossed, and files, directories, and symlinks are admitted.
An unsupported scope fails at config construction; providers cannot silently ignore
inert options.

The scope fingerprint is SHA-256 over the UTF-8 compact JSON array of sorted
`[name, value]` string pairs.
The payload includes the `inventory-scope-v2` schema identity.
Structured values are compact canonical JSON strings within that outer array.
Discovery budget, query depth, registry content, queue capacity, and observation mode
are intentionally absent.
Every provider adapter uses the application helper that defines this encoding; it does
not hash a language-specific object representation.

An `EngineVersion` consists of a session identity, monotonic sequence, scope
fingerprint, and semantic fingerprint.
The semantic fingerprint changes when any non-scope rule or reducer that can change a
complete answer changes.
A provider with one native fingerprint returns it directly.
A provider with several computes SHA-256 over the UTF-8 canonical JSON array of
`[name, value]` string pairs sorted by name, with no insignificant whitespace.
The Python provider’s current semantic component is the parsed File Rollup registry,
while fdu also includes its reducer behavior.
A caller never supplies a fingerprint as proof of different registry content.
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
Each record has a request-local `query_id`, identifiers must be unique within a bundled
read, and the bundle itself has the `MAX_QUERIES_PER_READ` bound.
Output bounds are mandatory at the provider boundary even when an HTTP route later
assembles a complete response from version-pinned pages.

`ReadRequest()` with no projections is the constant-work checkpoint form.
It returns only the coherent version, cursor, lifecycle state, and work envelope.
Routes use it to validate retained bodies before paying for a projection; an empty read
must not traverse inventory entries or manufacture a diagnostics dependency.

| Kind | Query | Required bound | Result |
| --- | --- | --- | --- |
| `entry` | `EntryQuery` | One relative path | Present, absent, or unknown lookup plus filesystem facts |
| `directory` | `DirectoryQuery` | Positive depth and row count | Name-ordered rows, continuation, and exact known remainder |
| `filtered_tree` | `FilteredTreeQuery` | Positive depth and row count | Matching tree rows and selected scalar totals |
| `rollup` | `RollupQuery` | Nonnegative depth and ranking bounds; positive node bound | Typed File Rollup Format record for one directory |
| `navigation` | `NavigationQuery` | Positive tally-row count | Typed population, extension, family, preset, and recency record |
| `recent` | `RecentQuery` | Positive row count and explicit observation time | Newest matching files and pre-bound match count; truncation is derived |
| `catalog` | `CatalogQuery` | Positive page size; optional terminal-extension, ancestor-name, and size predicates | Matching file identities, logical extensions, continuation, and exact known remainder from one pinned version |
| `diagnostics` | `DiagnosticsQuery` | Fixed `ProviderDiagnostics` record | Provider identity, indexed counts, watch state, request count, and cumulative work |

Recency filters carry `as_of_ns`; an unchanged engine version does not freeze a
time-dependent answer.
Providers may return `valid_until_ns` when the answer has a known expiry.
The coordinator includes that time boundary in request fingerprints, validators, and
retained-body keys. A caller assembling a time-dependent result from several
version-pinned pages chooses one `as_of_ns` before the first page and reuses it for
every page in that assembly.

Catalog terminal extensions use the lowercase substring beginning at the final dot when
that dot is neither the first nor final character.
Thus `archive.tar.gz` has `.gz`, `..foo` has `.foo`, and `.gitignore` and `notes.` have
no terminal suffix. This explicit rule keeps every provider independent of path-library
versions. Predicate lists contain unique values.
Ancestor names are nonempty, case-sensitive path components other than `.` and `..` and
contain neither separator; `size_less_than` is an exclusive byte bound.
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

Symlinks are visible leaves but do not contribute to regular-file totals.
The contract does not expose special filesystem objects because the current browser wire
cannot represent them; every provider must exclude them rather than reclassifying them
as regular files. Hidden components outside the exact-name allowlist are pruned from
scope. Gitignored visible entries remain in the `all` population and are excluded from
the `unignored` population.
File Rollup classification and conservation follow the
[File Rollup Format](file-rollup-format/file-rollup-format.md).

Active state, process labels, preview selections, and plugin labels belong to a sparse
application overlay keyed by the same path identity.
They do not cross the provider contract, advance an engine version, or contribute to
filesystem totals. The coordinator combines the engine version and overlay revision into
the host version used for browser events and caches.
Entry-bearing projections receive decorations automatically.
Provider-returned paths have already passed contract construction, so sparse-overlay
reads perform only deduplication and dictionary lookups.
Canonical validation occurs on overlay writes, where untrusted host paths first enter
that store. Catalog projections return identities rather than entries, so a coordinator
caller must opt in to catalog decorations.
The activity tracker opts in; bulk Quick File delivery does not traverse the overlay.

## State and Failures

State reports independent lifecycle, coverage, freshness, source, progress, and issue
facts. A same-phase observation is always valid; cross-phase transitions are:

| Current phase | Legal next phases |
| --- | --- |
| `opening_cache` | `discovering`, `reconciling`, `ready`, `stopped`, `failed` |
| `discovering` | `reconciling`, `ready`, `watching`, `stopped`, `failed` |
| `reconciling` | `ready`, `watching`, `stopped`, `failed` |
| `ready` | `reconciling`, `watching`, `stopped`, `failed` |
| `watching` | `reconciling`, `ready`, `stopped`, `failed` |
| `stopped` | none |
| `failed` | `stopped` |

`ready` means the handle is open and answering without discovery, reconciliation, or a
live filesystem observer.
`watching` requires a live observer; a provider configured with observation off, or one
whose observer has failed while the retained index remains readable, reports `ready`.
Resource-budget refusal remains readable but shuts down observation and reports
`stopped`; it must not claim to watch a scope it can no longer expand.
Refresh may still verify a retained file or symlink, including its removal, but rejects
unknown paths and retained directories because either could expand the stopped scope.
Priority hints are inert after this stop.
`stopped` is terminal; `failed` may only transition to `stopped`.

Coverage is either complete with no reason or partial with one of `building`, `budget`,
`cancelled`, `inaccessible`, or `failed`. Freshness is `fresh`, `reconciling`, `stale`,
or `partial`. A watcher gap makes freshness stale and adds a typed watcher-gap issue;
coverage changes only if reconciliation discovers or cannot resolve an enumeration hole.
Typed issues also distinguish permission failures, disappearance, invalid metadata,
filesystem-boundary skips, resource stops, and provider failures.
Providers preserve the original path and cause when the current layer can handle them.
`IndexState` contains at most `MAX_INVENTORY_ISSUES` records, and each issue detail is
at most `MAX_ISSUE_DETAIL_BYTES` UTF-8 bytes.
A provider coalesces or summarizes larger failure sets before constructing the state
record.

The Phase 2 fdu adapter uses the following total mappings; it does not infer them from
strings at individual call sites:

| Metabrowser fact | fdu fact |
| --- | --- |
| `LifecyclePhase.READY` | `Ready` |
| `SourceKind.SCANNED` | `cold_scan` |
| `SourceKind.REVALIDATED` | `warm_revalidate` |
| `SourceKind.CACHED` | `cache_only` |
| `IssueCode.PERMISSION_DENIED` | `Permission` |
| `IssueCode.WATCHER_GAP` | `ObservationGap` |
| `IssueCode.RESOURCE_BUDGET` | `ResourceStop` |

`SourceKind.JOURNAL_SCOPED` has no fdu mapping because replaying a journal does not
manufacture a new answer-shaping state.
Other issue spellings are identical.
Zero progress is honest for a settled provider that did not expose progressive state; an
adapter never invents progress, and fdu must expose real mid-discovery progress before
it can satisfy the progressive-open adoption gate.

## Change Delivery

`changes()` yields `ChangeBatch`, not entry replicas or browser events.
Each batch has a resulting version and cursor, state, work counters, and one of:

- bounded dirty paths or query kinds
- `all_dirty` when individual dirtiness exceeds its bound
- `reset` when the requested cursor or consumer queue has a gap
- a state-only transition

Batches from one handle retain the opened scope and semantic fingerprints and have
strictly increasing sequences.
The coordinator rejects a mixed-identity or nonmonotonic group before it coalesces any
dirtiness or work.

The coordinator rereads the affected visible projections, resumes from the read’s
cursor, and projects results into browser events.
A slow consumer causes a reset and coherent reread; it cannot block discovery or receive
a suffix presented as complete.
That consumer-side reset does not describe a provider observation gap.
A provider watch gap makes answers stale while the provider reconciles the affected
scope when recovery is available; an unrecoverable observer failure remains stale with
its typed issue. The coordinator may continue coherent reads and must not treat either
state as a failed reset recovery.

Refresh and priority requests contain at most `MAX_COMMAND_PATHS` unique canonical paths
and cannot be empty.
Refresh adds a typed reason; priority adds a positive depth.
A notification remains a hint: a provider verifies filesystem state before applying a
mutation. A completed refresh accounts for every requested path as accepted or rejected
and returns the terminal `EngineVersion` after every accepted observation has passed
through the provider’s mutation path.
A provider may publish coherent sub-batches while it works; the receipt is a completion
boundary, not a claim that the whole request was one transaction.
An adapter cannot return before it can name that terminal version or fan a bounded
request into untracked background work.
The primary native-or-polling watcher belongs to the opened provider so baseline
discovery, observation capture, reconciliation, and freshness share one lifecycle.
`refresh()` also accepts bounded external hints from activity probes or application
writes; it is not a second watcher.
If a watch batch cannot be submitted completely, the observer stops and reports a
watcher gap. It never drops one failed chunk and continues while claiming freshness.

## Work and Performance Evidence

Every read and change reports nonnegative counts for entries visited, directories
visited, rows returned, bytes copied across the binding, lock wait, and wall time.
CPU time is an exact nonnegative measurement when present and is unavailable otherwise;
a provider never substitutes zero or infers CPU from wall time.
Diagnostics use the fixed `ProviderDiagnostics` record rather than a provider-defined
mapping. They identify the selected provider and contract, indexed counts, watch state,
read count, and cumulative work.
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
| Quick File catalog | Empty checkpoint read followed, on a cache miss, by version-pinned `CatalogQuery` pages; the default Python execution budget fits in one page bounded by `InventoryConfig.budget.max_files` |
| `/api/file` folder facts | `EntryQuery` |
| Initial browser stream | A lossless version-pinned snapshot assembled before atomic queue attachment; covered older changes are suppressed per connection |
| Live browser stream | `changes()` plus coherent rereads |
| Activity discovery | Provider-filtered catalog reads by terminal extension, ancestor name, and size; results update the host overlay |
| Index metadata and capabilities | `NavigationQuery`, lifecycle state, engine identity, and `DiagnosticsQuery` |

Safe-path validation and file-content reads remain above the engine.
No inventory-serving route performs a second filesystem walk or reads a concrete
provider directly.
Every provider implements flat filtered-tree and catalog continuations
natively with the requested version, mandatory row bound, and exact remainder.
An adapter cannot materialize an unbounded result, retain a mirror solely to page it, or
claim a truncated first page is terminal.
The Python reference provider may retain one coherent tree projection when it returns a
continuation, then discard or replace that memo when another projection wins the slot.
This avoids repeating a full Python subtree pass for every page without creating a
coordinator cache or an fdu adapter index.
The fdu provider uses its native cursor and indexes instead.

## Provider Conformance Registry

This is the adoption gate shared by every provider factory.
The named check `test_architecture_document_registers_every_provider_conformance_case`
verifies that every row resolves to a provider-parametrized test in
`tests/test_inventory_provider_contract.py`.

| Test |
| --- |
| `test_checkpoint_read_returns_only_a_coherent_constant_work_envelope` |
| `test_paged_time_dependent_reads_reuse_one_as_of` |
| `test_provider_semantic_digest` |
| `test_provider_derives_registry_identity_from_supplied_content` |
| `test_provider_uses_supplied_registry_content_for_classification` |
| `test_provider_budget_stop_is_explicit_and_absence_remains_unknown` |
| `test_directory_pages_are_lossless_when_directories_outnumber_file_budget` |
| `test_catalog_predicate_semantics_are_runtime_independent_and_exact` |
| `test_catalog_pages_report_exact_lossless_remainders` |
| `test_provider_version_pins_fail_instead_of_moving` |
| `test_provider_changes_resume_and_report_history_gaps_as_reset` |
| `test_provider_refresh_verifies_the_filesystem_instead_of_trusting_the_hint` |
| `test_provider_close_joins_change_delivery_and_is_idempotent` |
| `test_provider_lifecycle_is_monotonic_and_one_handle_keeps_one_session` |

## References

- [State and delivery](arch-state-and-delivery.md)
- [Pluggable inventory engine](../specs/active/plan-2026-08-23-pluggable-inventory-engine.md)
- [fdu and Metabrowser inventory-engine alignment](../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
