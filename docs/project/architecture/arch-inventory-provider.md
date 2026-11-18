# Inventory Provider Contract

**Status:** Built: the contract in `inventory_engine/contract.py`, the coordinator, and
one provider, the Python reference engine
([Python Inventory Engine](arch-inventory-engine-python.md)). Planned: a native fdu
provider behind this same contract
([provider plan](../specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md),
Phase 2). [Decisions for a Second Provider](#decisions-for-a-second-provider) records
which of that provider’s rules Metabrowser has decided and which are open pending fdu
(`mb-54tl`).

Metabrowser owns a sealed interface between application behavior and the engine that
walks, retains, aggregates, and watches one served root.
The interface lets any engine answer the same requests without exposing its
retained-index types or concurrency model.
This document states what every provider guarantees; everything that depends on one
engine’s implementation is in that engine’s document.

The provider is authoritative for filesystem facts and aggregate indexes.
The application coordinator (`inventory_engine/coordinator.py`) owns root selection,
host-only decorations, response caching, browser event projection, and serialization.
Routes depend on the coordinator and cannot select or inspect a provider.

```text
routes and browser event projection
                |
      InventoryCoordinator + overlay
                |
          InventoryHandle
                |
       one provider per engine
```

`InventoryHandle` is a structural protocol, not a wrapper class: a provider implements
its five operations directly, and its helpers stay private without a forwarding object
that duplicates the API.

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

The application constructs the backend in its lifespan composition root
(`inventory_engine/runtime.py`). A root change closes the old handle, invalidates host
caches and cursors, opens the replacement, and then makes the new coordinator state
visible.
Tasks belonging to a closed session cannot publish into the replacement session.
The provider session, scope fingerprint, and semantic fingerprint are immutable for the
life of a handle. A read or refresh carrying different identity raises
`InventoryConsistencyError`; the change relay treats the same violation as provider
failure and publishes a host reset so stream consumers recover coherently.
Every concurrent `close()` caller joins the same shutdown before returning.

`METABROWSER_INVENTORY_PROVIDER` selects an entry of the sealed factory
(`InventoryProvider` in `inventory_engine/factory.py`), which lists the providers this
build ships. An unknown value fails at startup instead of falling back.
The performance harnesses take the same selection as `--provider`, so a new provider
needs no second benchmark path.
The tests read the same variable: `tests/inventory_harness.py`, which the product suites
open inventory through, and `PROVIDER_FACTORIES` in
`tests/test_inventory_provider_contract.py` build the selected provider through the
factory, so setting it runs those suites against that provider.

## Configuration and Identity

Configuration separates state identity from execution policy:

| Class | Fields | Effect |
| --- | --- | --- |
| Semantic filesystem scope | hidden admission and exact allowlist, symlink following, filesystem boundary, and admitted object kinds | Included in the versioned scope fingerprint |
| Classification | Immutable File Rollup registry document | Parsed by each provider; its provider-derived identity contributes to the semantic fingerprint |
| Execution | discovery budget and change-queue size | A budget stop reports partial coverage but does not redefine semantic scope |
| Observation | watch mode | Reported through source, freshness, and diagnostics |
| Selection | depth, row, and work bounds carried by each query | Changes one answer without changing the opened root’s identity |

Query `max_rows` bounds each returned page independently, and complete directory-style
consumers follow every continuation.
Metabrowser route and initial-stream tree assembly use `INVENTORY_TREE_PAGE_ROWS` rather
than reusing the discovery budget.
One `ReadRequest` contains at most `MAX_QUERIES_PER_READ` queries, which also bounds a
dirty-path projection batch.
The opened provider discovers without a depth limit.
Discovery and observation both apply `hidden_allowlist`; a name that changes scope
cannot be fingerprinted without also changing observation behavior.

Traversal is breadth-first.
The contract names and validates one observation-compatible scope: hidden components are
excluded except for the allowlist, symlinks are visible leaves and never followed,
filesystem boundaries are crossed, and files, directories, and symlinks are admitted.
An unsupported scope fails at config construction; providers cannot silently ignore
inert options.

Every provider computes the scope fingerprint with the application helper
`inventory_scope_fingerprint`, whose docstring defines the portable encoding; none
hashes a language-specific object representation.
Discovery budget, query depth, registry content, queue capacity, and observation mode
are not part of it.

An `EngineVersion` consists of a session identity, monotonic sequence, scope
fingerprint, and semantic fingerprint.
The semantic fingerprint changes when any non-scope rule or reducer that can change a
complete answer changes: the parsed File Rollup registry, and any reducer behavior of
the provider’s own. A provider with several components hashes them in the same canonical
`[name, value]` form.
A caller never supplies a fingerprint as proof of different registry content.
A `ChangeCursor` contains the same session and sequence at the read boundary.
A provider may implement coherent reads with a lock, an immutable image, or
version-check-and-retry, provided that:

1. a projection cannot mix generations;
2. the returned version and cursor describe the projection’s observation boundary; and
3. a frequent or unbounded read cannot hold a writer indefinitely.

### Version Pins

A version-pinned request either returns that version or raises
`VersionUnavailableError`. It never continues on a newer version.
This rule lets the coordinator assemble complete paged catalogs and trees without
joining generations.
`InventoryReadSession` leases the root and retains an immutable sparse-overlay snapshot
while those pages assemble.
It does not hold the coordinator lock across provider I/O; root replacement and shutdown
wait on its operation lease.
If the provider stops retaining the pinned version, the whole bounded assembly restarts;
cursors must advance and the final page must omit its continuation.
Exhausted retries fail the request with `VersionUnavailableError`; a complete consumer
never substitutes a partial first page.
The protocol does not promise indefinite retention: a provider states its own eviction
policy, and an unrelated old version-pinned request may expire.

A provider may answer a repeated root-summary read from an earlier coherent boundary
while its version moves, provided the version, cursor, state, and entry projection all
come from that boundary and only recency rows are evaluated at the query’s `as_of_ns`. A
provider whose tallies are maintained incrementally may always return a newer exact
boundary.

## The Cap

`DiscoveryBudget.max_files` limits how many regular files a provider discovers;
directories and symlinks do not count against it.
The application sets it from `INVENTORY_MAX_FILES` in `settings.py`
(`default_inventory_config` in `inventory_engine/runtime.py`), and that comment is where
the value and its reason live.

When discovery reaches the budget, a provider guarantees:

- coverage is partial with reason `budget`, and the state carries a `resource_budget`
  issue, which routes report as index status `truncated`;
- what was discovered stays readable, and lookups outside it answer `unknown`, never
  `absent`;
- observation stops and the phase becomes `stopped`, because a provider must not claim
  to watch a scope it can no longer expand (see
  [State and Failures](#state-and-failures)).

Reaching the budget is the stop, so a tree holding exactly `max_files` regular files
reports a budget stop although discovery left nothing out;
`test_provider_budget_counts_regular_files_and_stops_when_they_reach_it` pins the rule
as it stands.
Which files a stop admits is unspecified, because it follows directory read
order (D17): `test_provider_budget_stop_is_explicit_and_absence_remains_unknown` asserts
the stop, coverage, issue, and counts, and reads the admitted files back rather than
naming them.

Browsing a tree larger than the cap, rather than stopping at it, is planned
([load-time plan](../specs/active/plan-2026-08-21-load-time-performance.md)).

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
| `directory` | `DirectoryQuery` | Positive depth, page-row, and work bounds | Directory-first, canonical UTF-8 name-ordered rows and an opaque continuation |
| `filtered_tree` | `FilteredTreeQuery` | Positive depth, page-row, and work bounds | Matching tree rows and selected scalar totals |
| `grouped_tree` | `GroupedTreeQuery` | Positive depth, page-row, and work bounds; one to `MAX_TREE_GROUPS` groups | Each group’s filtered tree from one pass: its first page, totals, and a filtered-tree continuation |
| `rollup` | `RollupQuery` | Nonnegative depth and ranking bounds; positive node and work bounds | Typed File Rollup Format record for one directory |
| `navigation` | `NavigationQuery` | Positive tally-row and work bounds | Typed population, extension, family, preset, and recency record |
| `recent` | `RecentQuery` | Positive row, count, and work bounds plus explicit observation time | Newest matching files and an exact-or-lower-bound product count; truncation is derived |
| `catalog` | `CatalogQuery` | Positive page-row, count, and work bounds; optional terminal-extension, ancestor-name, and size predicates | Canonical UTF-8 path-ordered file identities, logical extensions, opaque continuation, and an exact-or-lower-bound product count |
| `diagnostics` | `DiagnosticsQuery` | Fixed `ProviderDiagnostics` record | Provider identity, indexed counts, watch state, request count, and cumulative work |

`tests/test_inventory_provider_contract.py` checks that this table names every
registered query. The row orders above are total, and the module docstring of
`contract.py` states them.

A grouped tree is Group by’s read (`metabrowser/tree_groups.py`). It answers each group
exactly as the `FilteredTreeQuery` that `GroupedTreeQuery.group_query` names, from one
pass over the index: the shared filter is tested once per leaf, and each group adds only
its type group and age band.
A group whose rows outrun the page bound carries that filtered tree’s continuation at
the grouped read’s version, so a caller completes every group from one engine version.
A folder stands in every group that holds something under it, with that group’s totals,
so grouped rows take no host decoration join.
`/api/tree` admits one grouped assembly at a time per runtime
(`InventoryRuntime.grouped_tree_admission`), so overlapping grouped reads take turns;
the Python engine’s reason, its retained continuations, is in
[Retained State](arch-inventory-engine-python.md#retained-state).

Recency filters carry `as_of_ns`; an unchanged engine version does not freeze a
time-dependent answer.
Recent ranks ignored files last, then newest first, then by canonical path, and applies
its row bound after that ranking, so a dependency install that writes thousands of files
cannot crowd out the reader’s own work; the rows it keeps are then ordered newest first.
The ranking holds whatever the match count.
Recent returns `RecentRecord` rows containing path, extension, size, modification time,
and ignored state. The name derives from the canonical path; directory aggregates and
host preview and activity decorations are absent because the Recent response consumes
neither. `tests/test_browser_recent.py` checks the wire fields and the absence of a
coordinator decoration join, alongside filtering and ordering.
`RecentProjection` and `NavigationProjection` have an optional `valid_until_ns` for an
answer with a known expiry, but no provider sets it and nothing above the contract reads
it, so a time-dependent answer describes only the `as_of_ns` it was read at.
A caller assembling a time-dependent result from several version-pinned pages chooses
one `as_of_ns` before the first page and reuses it for every page in that assembly.

Catalog terminal extensions follow `catalog_terminal_suffix`, which spells the rule
rather than leaving it to a path library, so `archive.tar.gz` has `.gz` and `.gitignore`
has none. Predicate lists contain unique values.
Ancestor names are nonempty, case-sensitive path components other than `.` and `..` and
contain neither separator; `size_less_than` is an exclusive byte bound.

Every potentially broad query carries `max_work`. A provider that cannot produce the
complete bounded projection returns `QueryLimitProjection` with the query kind, bound,
and deterministic charged work; it never returns a partial value in the ordinary result
type. Rollup, navigation, recent, and catalog queries refuse at their bound.
Whether a directory or filtered-tree page’s bound is a ceiling or a budget the page may
finish spending is D6, open pending fdu, so
`test_provider_returns_typed_query_limits_without_partial_answers` and
`test_provider_applies_work_bounds_to_continuation_pages` accept either a typed limit or
a page that makes progress, and require that pages end, assemble the unpaged answer, and
report at least the rows they return.
A typed limit charges at most its bound.
Recent and catalog counts stop claiming exactness after `count_cap` and return a proven
`at_least` lower bound.
Consumers use continuations for completeness and counts for display; neither count kind
controls paging.
A directory page for a path discovery has not listed yet, a directory it
reached but has not enumerated or a path below one, is empty and has no continuation
(`test_provider_answers_an_unlisted_directory_with_an_empty_final_page`); `/api/tree`
relies on it while discovery runs.

The algebra has no generic report name, provider command, HTTP status, response header,
or provider-specific options map.
Adding a query requires adding its record and result to `REGISTERED_QUERY_TYPES`,
documenting its cost and bound in this table, extending the contract harness, and
implementing it in every production provider.

## Filesystem Records and Host Decorations

`InventoryEntry` contains served-root-relative filesystem facts: lossless path identity,
object type, logical extension (the bounded compound tail `fs_paths.derive_ext` defines,
so `archive.tar.gz` has `.tar.gz`), size, modification time, ignore state, and optional
directory aggregates.
Path-bearing contract records use one canonical POSIX-relative grammar: the root is
`""`, absolute paths, backslashes, nulls, `.` and `..` segments, duplicate separators,
and trailing separators are rejected at construction.
That grammar is **total**: every entry has a canonical path, because the form is derived
by escaping (`canonical_inventory_name`, which states the escapes) rather than by
requiring the platform name to already be representable, and the escaping is injective,
so two names never share a form.
Because every name has a canonical form, a directory has one population, and a lookup
distinguishes:

- `present`: the entry is known and returned
- `absent`: complete coverage proves it is not present
- `unknown`: current coverage cannot prove either state

Symlinks are visible leaves but do not contribute to regular-file totals.
A directory’s `mtime_ns` and `newest_mtime_ns` are the newest modification time of any
regular file below it, and 0 when it holds none: neither a symlink’s time nor the
directory’s own counts (`test_provider_directory_times_are_their_newest_regular_file`).
That case pins `mtime_ns` at discovery only, because the Python store keeps a
directory’s discovered `mtime_ns` through a live change while `newest_mtime_ns` moves;
an expected failure in `tests/test_python_inventory_provider.py` records the gap.
The contract does not expose special filesystem objects because the browser wire cannot
represent them; every provider excludes them rather than reclassifying them as regular
files. Hidden components outside the exact-name allowlist are pruned from scope.
Gitignored visible entries remain in the `all` population and are excluded from the
`unignored` population.
File Rollup classification and conservation follow the
[File Rollup Format](file-rollup-format/file-rollup-format.md).

Active state, process labels, preview selections, and plugin labels belong to a sparse
application overlay (`inventory_engine/overlay.py`) keyed by the same path identity.
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
facts. A same-phase observation is always valid; cross-phase transitions follow
`ALLOWED_PHASE_TRANSITIONS` in `contract.py`, which
`tests/test_inventory_provider_contract.py::test_lifecycle_transition_graph_is_explicit_and_terminal`
checks: every live phase may stop or fail, `stopped` is terminal, and `failed` may only
stop. The graph binds through conformance, not at run time:
`test_provider_lifecycle_is_monotonic_and_one_handle_keeps_one_session` applies
`IndexState.can_transition_to` to every transition a provider makes while it opens, and
the coordinator does not reject an illegal one.

`ready` means the handle is open and answering without discovery, reconciliation, or a
live filesystem observer.
`watching` requires a live observer; a provider configured with observation off, or one
whose observer has failed while the retained index remains readable, reports `ready`.
Resource-budget refusal remains readable but shuts down observation and reports
`stopped`. Refresh may still verify a retained file or symlink, including its removal,
but rejects unknown paths and retained directories because either could expand the
stopped scope. Priority hints are inert after this stop.

Coverage is either complete with no reason or partial with a `CoverageReason`, and
`Freshness` says whether answers are current.
An observation gap makes freshness stale and adds a typed `observation_gap` issue;
coverage changes only if reconciliation discovers or cannot resolve an enumeration hole.
`IssueCode` also distinguishes permission failures, disappearance, invalid metadata,
resource stops, and provider failures.
Providers preserve the original path and cause when the current layer can handle them.
A provider that can no longer serve its root, after a native panic, a poisoned root, or
a broken internal invariant, raises `ProviderFailureError` from the command or its
change stream; the coordinator replaces the handle rather than the provider recovering
in place (D14). `IndexState` contains at most `MAX_INVENTORY_ISSUES` records, and each
issue detail is at most `MAX_ISSUE_DETAIL_BYTES` UTF-8 bytes; a provider coalesces or
summarizes larger failure sets before constructing the state record.
Zero progress is honest for a provider that does not expose progressive state; a
provider never invents progress.

## Change Delivery

`changes()` yields `ChangeBatch`, not entry replicas or browser events.
Each batch has a resulting version and cursor, state, work counters, and one of:

- bounded dirty paths (at most `MAX_CHANGE_PATHS`) or query kinds
- `all_dirty` when individual dirtiness exceeds its bound
- `reset` when the requested cursor or consumer queue has a gap
- a state-only transition

Batches from one handle retain the opened scope and semantic fingerprints and have
strictly increasing sequences.
A batch may carry state alone, so how many batches one change takes is the provider’s
own. A cursor inside the provider’s replay capacity, which `change_queue_size` sizes in
the provider’s own units, replays every batch after it, and one outside it gets a reset
(D8, `test_provider_changes_resume_and_report_history_gaps_as_reset`). The dirty paths
of a change include every ancestor whose aggregates it moved, up to the root, so a
consumer that rereads only dirty paths sees current folder totals
(`test_provider_dirty_paths_name_every_ancestor_whose_aggregates_changed`); what else a
dirty path promises is D20. The coordinator rejects a mixed-identity or nonmonotonic
group before it coalesces any dirtiness or work.
A handle allows one active change iterator.

The coordinator rereads the affected visible projections, resumes from the read’s
cursor, and projects results into browser events; see
[Live Delivery](arch-live-delivery.md).
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
The change stream then delivers a batch at or past the receipt’s version, unless it
already has, because the coordinator returns a refresh only once its relay has published
that version (`test_provider_change_stream_reaches_every_refresh_receipt_version`).

The primary filesystem observer belongs to the opened provider, so baseline discovery,
observation capture, reconciliation, and freshness share one lifecycle.
A provider establishes its observation boundary before discovery scans a path, so a
change made during discovery is either observed or scanned, and `close()` stops and
joins the observer before releasing anything it uses.
`refresh()` also accepts bounded external hints from activity probes or application
writes; it is not a second watcher.
If a batch of observations cannot be applied completely, observation stops and reports a
gap. A provider never drops one failed chunk and continues while claiming freshness.

## The Per-Entry Rule

This contract is crossed by queries, which are few, not by every discovered entry, so an
engine follows the
[per-entry rule](../../engine-performance-model.md#the-per-entry-rule): nothing goes on
the per-entry path without a measured reason.
That is why the contract’s entry type is not what a walker yields, and why a provider
keys its store by the canonical identity rather than escaping on every row of every
read. Each engine states its unit costs against the rule in its own document.

## Work and Performance Evidence

Every read and change reports one semantic work vocabulary, `WorkCounters`:
deterministic charges, such as rows visited and filesystem entries read, with the same
meaning in every provider.
`BoundaryMetrics` separately records binding bytes, lock wait, wall time, and exact CPU
time when available; unavailable CPU time remains `None` rather than becoming zero.
Diagnostics use the fixed `ProviderDiagnostics` record rather than a provider-defined
mapping, and `/_debug/inventory` reports it when `METABROWSER_DEBUG` is set.
Its `directories_indexed` counts every retained directory, the served root included, and
`files_indexed` regular files only
(`test_provider_counts_the_root_among_indexed_directories`); its `watch_*` fields are
the provider’s own words.

The host also records when the served root’s first discovery ended,
`InventoryCoordinator.discovery()`: the first provider state outside `DISCOVERY_PHASES`
to reach it, through a read or a change batch, timed from the provider’s `open()`
returning, with the time `open()` took beside it.
`/_debug/inventory` reports it as `discovery`, so every provider’s discovery is timed by
one definition without any provider reporting it, and the serving benchmark and the
performance loop read it rather than a provider’s log line.

The serving benchmark records the same identities, so runs on two providers differ by a
declared provider axis rather than by separate harnesses;
[Scale Benchmark](../../scale-benchmark.md) says what it measures and how to run it.
The performance gate shared by every provider is in the
[load-time plan](../specs/active/plan-2026-08-21-load-time-performance.md) and the
[provider plan](../specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md).

## Consumer Mapping

| Consumer | Queries |
| --- | --- |
| `/api/tree` | Version-pinned `DirectoryQuery` or `FilteredTreeQuery` pages, with `NavigationQuery` at the same host boundary for root tallies; with `group_by`, one `GroupedTreeQuery` and its groups’ version-pinned continuations |
| `/api/rollup` and folder hooks | `RollupQuery` |
| `/api/recent` | `RecentQuery` |
| Quick File catalog | Empty checkpoint read followed, on a cache miss, by version-pinned `CatalogQuery` pages of `budget.max_files` rows, so a catalog that fits the budget is one page |
| `/api/file` folder facts | `EntryQuery` |
| Initial browser stream | A lossless version-pinned snapshot assembled before atomic queue attachment; covered older changes are suppressed per connection |
| Live browser stream | `changes()` plus coherent rereads |
| Activity discovery | Provider-filtered catalog reads by terminal extension, ancestor name, and size; results update the host overlay |
| Index metadata and capabilities | `NavigationQuery`, lifecycle state, engine identity, and `DiagnosticsQuery` |

Safe-path validation and file-content reads remain above the engine.
No inventory-serving route performs a second filesystem walk or reads a concrete
provider directly.
Every provider implements flat filtered-tree and catalog continuations
natively with the requested version and mandatory row bound.
An adapter cannot materialize an unbounded result, retain a mirror solely to page it, or
claim a truncated first page is terminal.
Continuations are opaque, one-shot, and version-pinned; a provider that no longer holds
one reports unavailability rather than reconstructing cursor authority from caller data.
A typed work-limit result does not consume a continuation, so a caller can retry the
same version and token with an adequate bound; a successfully returned page does.

## Test and Measurement Seams

A product test that needs a provider held at a known point asks the provider through the
contract rather than patching one provider’s internals, so the suites run unchanged
against any provider.
`ProviderSeams` (`inventory_engine/seams.py`) reaches a backend through its constructor,
by way of `create_inventory_backend(..., seams=)` and `InventoryRuntime(seams=)`, and
never through `InventoryConfig`, because a seam changes neither scope nor semantics.
The application lifespan passes none.

- **A discovery gate.** `DiscoveryGate(before=path)` holds opening discovery before it
  lists that directory until `release()`, and reports `reached` when it arrives there.
  `before=""` holds discovery before anything below the root is listed; a deeper path
  lets level order publish everything it reaches first, which scripts a partially
  discovered tree. A held provider answers reads, reports `discovering`, and closes
  promptly.
- **A retained-row bound.** `max_retained_rows` lowers the bound on rows retained for
  continuations below `MAX_ASSEMBLED_ROWS`, so a test reaches the eviction a large tree
  reaches.

`tests/test_inventory_seams.py` holds the selected provider to both.
Two more seams live only in the tests.
Route tests count and hold rollup passes as the coordinated reads that carry a
`RollupQuery`, which measures the host’s coalescing whichever provider aggregates.
`tests/perturbed_provider.py` wraps any backend and changes only its granularity and
identity, or injects a fault, to reproduce over the Python provider host behavior that a
provider with different commit granularity exposes; `InventoryRuntime(backend=)` accepts
such a wrapped backend.

## Adding a Provider

Only the sealed factory imports a concrete provider; routes, browser-event projection,
and activity tracking use the coordinator, and each provider owns its own observer.
A new provider:

1. adds its entry to `InventoryProvider` and its construction to
   `create_inventory_backend` (`inventory_engine/factory.py`);
2. passes the registry below with `METABROWSER_INVENTORY_PROVIDER` naming it, which is
   how `PROVIDER_FACTORIES` in `tests/test_inventory_provider_contract.py` selects it,
   and the product suites and goldens the same way;
3. implements the [test and measurement seams](#test-and-measurement-seams), which
   `tests/test_inventory_seams.py` and the product suites hold it to;
4. adds an engine document beside
   [Python Inventory Engine](arch-inventory-engine-python.md) with its walker,
   concurrency, observer, retained state, and unit costs; and
5. reruns the serving benchmark with `--provider` and records the result in
   [Scale Benchmark](../../scale-benchmark.md).

Nothing above this contract changes for a new provider, but a few host paths still read
the served tree without it.
Two would make a provider swap non-equivalent:

- `metab --walk` text and `--stream` modes (`walk.py`) call the Python walker’s
  `walk_tree` directly, so they show the Python walker whichever provider serves; its
  JSON, YAML, and filtered modes already read through the runtime.
- The `tree._dir_tree` family, which `server.py` re-exports, walks with `os.scandir`,
  though no production route calls it.

The rest are bounded host reads: the README scan in `folder_discovery.py`, which must
also answer for folders outside the index; `_folder_not_indexed` in `server.py`, which
re-applies the scope rules with the default hidden allowlist rather than the configured
one; and the activity tracker’s `stat` of catalog candidates, which feeds verified
refresh hints. The research’s
[bypass table](../research/research-2026-11-17-fdu-backend-revisited.md#a-few-code-paths-still-bypass-the-seam)
gives each one’s disposition.

## Decisions for a Second Provider

A second provider exposes rules the Python provider never had to state.
[The revisited fdu research](../research/research-2026-11-17-fdu-backend-revisited.md#decisions-needed-before-parity-runs)
names the decisions parity runs need and gives each one’s reasons, evidence, and the
changes it implies; this table records only the rule, its status, and what holds a
provider to it.

A **decided** rule is Metabrowser’s alone and binds every provider, including where the
Python provider does not meet it yet, which the last column says.
An **open, pending fdu** rule changes fdu’s behavior or contradicts a decision fdu has
recorded, so it is Metabrowser’s proposal in
[jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215) until fdu agrees, and the last
column says what, if anything, holds a provider to it meanwhile.
R numbers name the research’s
[refactors](../research/research-2026-11-17-fdu-backend-revisited.md#required-metabrowser-refactors),
whose bead table tracks each, and a layer is a step of the stack its
[recommendations](../research/research-2026-11-17-fdu-backend-revisited.md#recommendations)
order. `test_architecture_document_records_every_decision` checks that the table records
each decision the research names once, in its order, with one of these statuses, that
every open one links the fdu proposal, and that every test it names exists.

| # | Rule | Status | Held by |
| --- | --- | --- | --- |
| D1 | An unreadable or vanished directory makes coverage partial with reason `inaccessible` and adds a bounded `permission` or `disappeared` issue, rather than reading as empty; the host tells “complete with issues” from “still discovering” | Decided | Not yet: the Python walker treats such a directory as empty, with coverage complete. R6 (layer 4) |
| D2 | Serving a repository subdirectory applies every `.gitignore` from the enclosing repository root down, those above the served root included; `.git/info/exclude`, global excludes, and `core.ignorecase` are decided together with it | Open, pending fdu ([jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)) | The Python provider’s rule, which `tests/test_gitignore_hierarchical.py` checks against `git check-ignore` through the Python matcher rather than a provider. R8 (layer 4) |
| D3 | A `.gitignore` edit is observed live and reclassifies its subtree as one verified change | Decided | Not yet: the Python watcher drops the hidden name. R7 (layer 4) |
| D4 | The observer watches exactly the admitted scope, turns overflow into scoped reconciliation, and retries or degrades explicitly when it fails | Decided | Not yet: see [The Watcher](arch-inventory-engine-python.md#the-watcher). R7 (layer 4) |
| D5 | After an observer failure, including a watch-limit failure at open, a handle reports `ready`, freshness `stale`, and an `observation_gap` issue, because its data is complete as of its version | Open, pending fdu ([jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)) | [State and Failures](#state-and-failures) states it; the Python provider meets it (`test_python_provider_surfaces_observation_gap`), and no conformance case can fail an observer yet |
| D6 | A per-page tree work budget is soft: a page spends its budget, stops at a position its continuation can name, reports the work it spent, and returns at least one row or ends the traversal; conformance asserts progress, termination, and conservation, never a ceiling | Open, pending fdu ([jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)) | `test_provider_returns_typed_query_limits_without_partial_answers` and `test_provider_applies_work_bounds_to_continuation_pages` accept a typed limit or a page that makes progress; the Python provider’s hard limit is pinned in `tests/test_python_inventory_provider.py`, and R5 (layer 6) gives it the soft rule |
| D7 | A filtered or grouped tree is one complete-or-limit read at one version and does not page; a moved version restarts it | Open, pending fdu ([jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)) | Not yet: both page today. R5 (layer 6) |
| D8 | Replay capacity is a provider budget: a cursor inside it replays exactly and one outside it gets a reset. A batch is one coherent version and may carry state only; the host publishes a transient `reconciling` freshness and the batches after it as one change, and tests assert convergence rather than envelope counts | Decided | `test_provider_changes_resume_and_report_history_gaps_as_reset`, which also runs with split batches. The host rule is `_hold_reconciling_batches` in `coordinator.py`, bounded by `RECONCILING_HOLD_S` (`test_a_reconciling_batch_and_the_batches_after_it_publish_as_one_change`, `test_a_reconciling_hold_publishes_when_its_bound_expires`); `tests/test_e2e_filesystem_to_sse.py` runs each refresh case with split, delayed batches and asserts convergence and that no envelope half-removes a subtree |
| D9 | The engine receives classification, not presentation: a File Rollup classification profile names the fields an engine reads, providers derive semantic identity from what they parse, and the host stamps the browser’s registry fingerprint | Intent decided; profile open, pending fdu ([jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)) | Providers parse the whole registry document today (`test_provider_derives_registry_identity_from_supplied_content`, `test_provider_uses_supplied_registry_content_for_classification`). R9 (layer 5) |
| D10 | Metabrowser’s total canonical grammar is the identity, `%5C` for a POSIX backslash included | Open, pending fdu ([jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)) | `canonical_inventory_name` in `contract.py` (`test_the_canonical_path_is_total_and_injective`, `test_an_unescaped_posix_backslash_is_not_an_identity`); fdu’s grammar does not escape the backslash |
| D11 | Every bound both providers must meet is one contract constant, set from a measurement of both and recorded beside it, and the adapter asserts fdu’s exported bounds against those constants at open | Method decided; values pending measurement | The constants at the top of `contract.py`, set for the Python provider today (`test_configuration_and_command_bounds_are_enforced`). R5 (layer 6), after R20 |
| D12 | The fdu adapter in `src/` is thin from its first commit: a kind fdu cannot answer returns a typed unsupported result in its projection’s place, against a shrink-only expected list, fallbacks live in a harness outside `src/`, and the provider stays experimental with no goldens until every kind is native | Decided | With the adapter (R10, R11, R14, R29); the contract has no unsupported result yet |
| D13 | A complete assembly of path-keyed rows equals one version while the version moves: a continuation names a position in the total order, and the coordinator re-reads what its dirty ledger names until a pass finds nothing new | Open, pending fdu ([jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)) | Today a pin fails instead of moving ([Version Pins](#version-pins), `test_provider_version_pins_fail_instead_of_moving`). R5 (layer 6) |
| D14 | A native panic or poisoned root becomes a typed provider failure, and a coordinator supervisor, not the relay, closes the failed handle with a bounded wait, reopens it up to a cap, publishes a host reset, and past the cap leaves the root failed | Decided | `ProviderFailureError` in `contract.py` is the typed failure; the adapter translates a native panic into it (R10). The supervisor is `_recover` in `coordinator.py` ([Live Delivery](arch-live-delivery.md#from-provider-to-coordinator)), and `tests/test_inventory_recovery.py` drives it through the fault seams in `tests/perturbed_provider.py`: `test_a_failed_change_stream_reopens_the_root_and_keeps_live_updates` (an `Exception` and a `BaseException`), `test_a_read_that_reports_provider_failure_starts_recovery`, `test_past_the_reopen_cap_the_root_is_failed_until_it_opens_again`, and `test_a_close_that_hangs_is_abandoned_after_its_bound` |
| D15 | The seam has two latency bounds, measured separately and stated in the contract: the uninterruptible native hold and event-loop lag, which also counts preemptible conversion; page sizes follow from both, and `open`, `close`, and root replacement have bounds under the coordinator lock | Decided | Not yet: measured with the adapter, and stated with D11’s constants |
| D16 | A provider’s settled memory per retained entry has a byte budget, and the fdu process is no larger than Python’s on one corpus, measured at steady state after settle | Decided | Not yet: `devtools/bench_engine.py` (R18) records peak resident memory, not settled memory; R30 re-measures the Python baseline (layer 7) |
| D17 | Which files a budget stop admits is unspecified; conformance and goldens assert the stop, coverage, issue, and counts, never membership | Decided | `test_provider_budget_stop_is_explicit_and_absence_remains_unknown`; the files the Python provider admits are pinned in `tests/test_python_inventory_provider.py` |
| D18 | Only the byte-exact served name is identity: a lookup or refresh spelled differently only in letter case or Unicode normalization answers `absent` or is rejected, and a refresh verifies its spelling against the parent’s listing | Open, pending fdu ([jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)) | Not yet: macOS cases with the adapter |
| D19 | Metabrowser pins fdu exactly, changes the pin in one commit with the adapter and its conformance results, and uses only the public `fdu.opened` surface and fdu’s exported bounds | Decided | With the adapter’s packaging (R14) |
| D20 | A change batch names every path whose row may differ from the version before it, every ancestor whose aggregates changed included; a removed subtree is named by its root in a separate bounded field; what a batch cannot express this way is all-dirty | Open, pending fdu ([jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)) | The ancestor rule: `test_provider_dirty_paths_name_every_ancestor_whose_aggregates_changed`. The removed-subtrees field is R5 (layer 6) |
| D21 | Native events are never trusted on a remote or unknown filesystem: such a root reports D5’s `ready`, `stale`, and `observation_gap`, with refresh driven by the host until fdu can poll | Open, pending fdu ([jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)) | The Python provider polls those filesystems instead (`select_watch_mode` in `watch_backends.py`); fdu’s side comes with the adapter |
| D22 | Aggregates cross the seam as contract-owned values: classification tallies per dimension, ranked children with a remainder, exact-or-capped totals, and recency-window counts, from which the host builds `RollupResult` and navigation rows and stamps registry identity | Open, pending fdu ([jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)) | Not yet: `RollupProjection` and `NavigationProjection` carry browser wire models. R3 (layer 5) |

## Provider Conformance Registry

This is the adoption gate shared by every provider factory.
The named check `test_architecture_document_registers_every_provider_conformance_case`
verifies, in both directions, that the rows below are exactly the provider-parametrized
tests in `tests/test_inventory_provider_contract.py`.

A case asserts semantics and bounds: a filesystem fact, an order, a bound, or a state
transition, never a provider’s name, a free-form string, a batch granularity, or an
exact work charge. Each runs against the provider `METABROWSER_INVENTORY_PROVIDER`
selects and against it behind `tests/perturbed_provider.py`, once renamed and once also
with every data batch split into a state-only batch and the data at versions of their
own, so a case that fails only wrapped pins an identity or granularity the contract
leaves to a provider.
Where the contract leaves a choice open, such as which files a budget stop admits, the
unit of replay capacity, work charges, or watch strings, the Python provider’s choice is
pinned in `tests/test_python_inventory_provider.py`, each case there naming the
conformance case it complements.

| Test |
| --- |
| `test_checkpoint_read_returns_only_a_coherent_constant_work_envelope` |
| `test_paged_time_dependent_reads_reuse_one_as_of` |
| `test_provider_semantic_digest` |
| `test_provider_derives_registry_identity_from_supplied_content` |
| `test_provider_uses_supplied_registry_content_for_classification` |
| `test_provider_budget_stop_is_explicit_and_absence_remains_unknown` |
| `test_provider_budget_counts_regular_files_and_stops_when_they_reach_it` |
| `test_provider_counts_the_root_among_indexed_directories` |
| `test_directory_pages_are_lossless_when_directories_outnumber_file_budget` |
| `test_filtered_tree_and_recent_share_filter_semantics_before_caps` |
| `test_grouped_tree_answers_each_group_as_its_filtered_tree` |
| `test_group_filters_cut_age_bands_at_their_edges_and_keep_symlinks` |
| `test_catalog_predicate_semantics_are_runtime_independent_and_exact` |
| `test_catalog_pages_are_lossless_without_suffix_counts` |
| `test_provider_applies_work_bounds_to_continuation_pages` |
| `test_provider_returns_typed_query_limits_without_partial_answers` |
| `test_provider_counts_are_exact_or_proven_lower_bounds` |
| `test_provider_uses_canonical_portable_row_order` |
| `test_provider_version_pins_fail_instead_of_moving` |
| `test_provider_changes_resume_and_report_history_gaps_as_reset` |
| `test_provider_dirty_paths_name_every_ancestor_whose_aggregates_changed` |
| `test_provider_directory_times_are_their_newest_regular_file` |
| `test_provider_answers_an_unlisted_directory_with_an_empty_final_page` |
| `test_provider_allows_only_one_active_change_iterator` |
| `test_provider_refresh_verifies_the_filesystem_instead_of_trusting_the_hint` |
| `test_provider_change_stream_reaches_every_refresh_receipt_version` |
| `test_provider_close_joins_change_delivery_and_is_idempotent` |
| `test_provider_lifecycle_is_monotonic_and_one_handle_keeps_one_session` |

## References

- [Python Inventory Engine](arch-inventory-engine-python.md): the reference engine
- [Live Delivery](arch-live-delivery.md): what the application does with `changes()`
- [Engine Performance Model](../../engine-performance-model.md): measurement discipline
- [Pluggable inventory engine](../specs/active/plan-2026-08-23-pluggable-inventory-engine.md)
- [fdu and Metabrowser inventory-engine alignment](../research/research-2026-08-23-fdu-metabrowser-inventory-engine.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
