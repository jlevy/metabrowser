# fdu as Metabrowser's inventory backend: the current seam on Metabrowser's side

Read-only research at `db08e3b8` on branch `claude/cool-edison-avg57h`. Nothing was edited, committed or pushed.

**Caveat on history.** This clone is shallow: `git rev-parse --is-shallow-repository` is true and history starts on 2026-11-12. For September to November, the "what changed" findings come from `CHANGELOG.md`, the docs and the beads rather than `git log`.

**External fact, checked on PyPI because packaging depends on it.** `fdu` 0.6.0 was published 2026-11-12.
- It ships `cp312-abi3` wheels for macOS arm64 and x86_64, manylinux2014 x86_64 and aarch64, win_amd64, plus an sdist.
- Its description says free-threaded CPython (3.14t) is not supported.
- It exposes a synchronous progressive API, `fdu.opened.OpenedIndex.open(...)`, with `read`, `changes(cursor, timeout=)` and similar methods.

## Executive summary

- **What fdu must implement.** The seam is real and narrow: five async handle methods (`contract.py:1742-1757`), nine query kinds with typed results, and a bounded invalidation stream. Today an fdu provider must reproduce several things exactly:
  - Python's browser wire payloads for rollup and navigation (`RollupResult`, `NavigationTallies`), including the registry fingerprint the browser compares.
  - Python's work-charging model, which the conformance tests pin by exact counts.
  - Python's batch granularity in one replay test.
  - Python-specific free-form watcher strings.
- **What bypasses the seam.** A handful of places, mostly legitimate (file contents, safe-path resolution, Git). The real bypasses are:
  - `metab --walk` text and stream modes, which call the Python walker directly (`mb-iyu7`).
  - A host-side scandir for README discovery.
  - The activity tracker's own stat poller (it feeds verified refresh hints, so this is by design).
  - Git pins, which have a separate, complete-at-once index outside the provider.
  - About 400 lines of dead `tree._dir_tree` filesystem walker still re-exported by `server.py`.
- **The biggest semantic risk.** Python treats permission-denied directories as empty and complete, and never reports `inaccessible` or `permission`. The host reads only `phase`, `coverage.complete` and the `resource_budget` issue. A native provider that honestly reports partial coverage would make every status read "scanning" forever and make lookups answer `unknown`.
- **The biggest performance risk.** About 93% of the detached walk is Python above the filesystem, so fdu should collapse the walk itself. But with a browser attached, delivery costs about 14 µs per entry, and that cost sits in the host: one `EntryQuery` per dirty path, Python dataclass construction and validation per row, the wire record, SSE. Catalog pages are 500,000 rows, a size chosen for the Python provider. An end-to-end A/B will understate fdu unless `mb-l2eh` (facts in change batches) and a cheaper record path land too.
- **The stale spike.** The Checkpoint 2A spike is stale against the current contract. Its adapter uses `IssueCode.PERMISSION_DENIED`, `IssueCode.WATCHER_GAP` and `entry.portable_path`, none of which exist now, and `GroupedTreeQuery` was added on 2026-11-14/15. The 2A failure on journal capacity is still encoded in the conformance test, even though the plan marks 2B done.

---

## 1. Contract surface today

### 1a. Protocols and methods

| Item | Definition | Semantics | Native difficulty |
|---|---|---|---|
| `InventoryBackend.open(root, config)` | `contract.py:1755-1757` | Returns a handle at once, without waiting for discovery. The coordinator immediately issues `ReadRequest()` as a checkpoint (`coordinator.py:595-600`). | Medium. fdu must parse the File Rollup registry TOML text itself (`InventoryConfig.registry_document`) and derive both fingerprints. |
| `InventoryHandle.read(request)` | `:1744` | One coherent version, cursor, state, typed projections and work for the whole bundle. | Hard. Nine projections, bundling, continuations, work charging. |
| `changes(after=cursor)` | `:1746` | An async iterator of `ChangeBatch`. Only one iterator may be active at a time, otherwise `ChangeStreamBusyError` (`:1727`). | Medium. Needs an async bridge over fdu's synchronous `changes(cursor, timeout)` poll. 2A measured a 239 ms cancel join with a 250 ms poll. |
| `refresh(request)` | `:1748` | Verifies hints against the filesystem. The receipt must account for every path (`coordinator.py:421-425`) and carry the terminal `EngineVersion`. | Medium. Has Python-specific reject rules (see §4). |
| `prioritize(request)` | `:1750` | Bounded discovery-order hint. Inert after a budget stop. | Easy to medium. |
| `close()` | `:1752` | Cancels and joins all work. Idempotent; concurrent callers join the same shutdown. | Medium. Must join native workers and the poll worker. |

### 1b. `InventoryConfig` (`contract.py:479-528`)

| Field | Class | v1 constraint | Notes |
|---|---|---|---|
| `registry_document` | Classification (semantic fingerprint) | Must parse (`:499-503`) | The Python provider uses `registry.fingerprint` as `semantic_fingerprint` (`python_inventory.py:1382`). |
| `hidden_allowlist` | Semantic scope (scope fingerprint) | Exact `.name` components, unique (`:506-516`) | The app passes `(".logs", ".state")` (`runtime.py:35-43`). |
| `include_hidden`, `follow_symlinks`, `one_filesystem` | Semantic scope | Must be False, False, False (`:517-522`) | Fingerprinted by `inventory_scope_fingerprint` (`:531-562`), a portable canonical-JSON SHA-256. |
| `admitted_object_kinds` | Semantic scope | Exactly file, directory, symlink (`:523-528`) | |
| `budget: DiscoveryBudget(max_files)` | Execution | Positive int (`:469-476`) | Counts regular files only. The app sets `INVENTORY_MAX_FILES = 500_000` (`settings.py:110`). |
| `change_queue_size` | Execution | Positive | The app sets `SSE_BUS_INVENTORY_QUEUE_SIZE = 4_096` (`settings.py:147`). It sizes provider replay history, the coordinator's relay queue and the host history. |
| `watch_mode` | Observation | `auto`, `native`, `poll` or `off` (`:491`, `:504`) | Not fingerprinted. |

Docs and code disagree here. `plan-2026-08-23-pluggable-inventory-engine.md` §"Shared Classification Packet" says the provider receives the packet plus an expected identity and fails the open on disagreement. Code passes the document only; that design changed in Checkpoint 2B.

### 1c. Queries and results

All query records are frozen, slotted dataclasses whose `__post_init__` validates every path. The algebra is closed (`REGISTERED_QUERY_TYPES` at `:1257`). `MAX_QUERIES_PER_READ` is 1,024 (`:102`), and `query_id` values must be unique within a request.

| Query (def) | Bounds / fields | Result (def) | Semantics | Native difficulty |
|---|---|---|---|---|
| `EntryQuery` (`:949`) | path | `EntryProjection` (`:1316`): `present`, `absent` or `unknown` | `absent` only when coverage is complete, else `unknown` (`python_inventory.py:2287-2290`) | Trivial |
| `DirectoryQuery` (`:960`) | `max_depth` (default 2), `max_rows` (10k), `max_work`, `after`, `include_ignored` | `DirectoryProjection` (`:1328`) | Breadth-first level order; directories first; canonical UTF-8 byte order (`:15-25`). `include_ignored=False` prunes ignored subtrees. A folder the walk has not reached yet answers as an empty page with no continuation (`server.py:1784-1788` relies on this). | Medium |
| `FilteredTreeQuery` (`:1014`) plus `InventoryFilter` (`:979`) | extensions, filenames, type_families, recency, age band, `type_group`, `minimum_size`, `include_ignored`, `as_of_ns` | `FilteredTreeProjection` (`:1342`): rows plus `matching_leaves`, `matching_files`, `matching_bytes` | Ancestor folders within depth listed; ASCII-only case folding; symlink rules (§4) | Hard |
| `GroupedTreeQuery` (`:1064`) plus `TreeGroupFilter` (`:1033`) | 1 to `MAX_TREE_GROUPS` (8, `:110`) groups; one shared filter | `GroupedTreeProjection` (`:1388`) of `TreeGroupProjection` (`:1362`) | Each group equals `group_query(...)` (`:1106-1123`), and each group's continuation is a filtered-tree continuation. New on 2026-11-14/15. | Hard |
| `RollupQuery` (`:1126`) | depth, `max_nodes`, top, `extension_top`, `remaining_top`, `filename_top`, `rank`, `max_work` | `RollupProjection.payload: RollupResult` (`:1406-1412`), a browser wire TypedDict | Python builds it with `inventory_rollup.build_rollup` (744 lines) | Hard. A native provider must emit the browser's wire model (`mb-gwlw`). |
| `NavigationQuery` (`:1149`) | presets, `recency_windows`, `max_rows`, `max_work`, `as_of_ns` | `NavigationProjection.payload: NavigationTallies` (`:1415`), with untyped `list[list[object]]` rows | Ranking and preset semantics are in `_compute_navigation_tallies` (`python_inventory.py:3175-3322`) | Medium to hard (row shape is unpinned, `mb-nqgs`) |
| `RecentQuery` (`:1171`) | `max_rows`, `as_of_ns`, `max_work`, `count_cap`, `prefix`, filter (defaults to `include_ignored=False`) | `RecentProjection` (`:1462`): `RecentRecord`s, a `CountResult`, `gitignored_directories`, `valid_until_ns` | Two total orders (`:29-46`). No continuation. | Medium |
| `CatalogQuery` (`:1194`) | `max_rows`, `max_work`, `count_cap`, `after`, `include_ignored` (default False), `terminal_extensions`, `ancestor_names`, `size_less_than` | `CatalogProjection` (`:1502`): `CatalogRecord`s (path, logical extension, size, mtime) | Regular files only; ordered by the canonical path's UTF-8 bytes | Medium |
| `DiagnosticsQuery` (`:1236`) | none | `DiagnosticsProjection(ProviderDiagnostics)` (`:1519`) | | Easy, except the watch-string vocabulary (§1f) |

### 1d. Bounds, work limits, counts, continuations, version pins

- **Constants** (`contract.py:98-126`): `MAX_CHANGE_PATHS` 1,024; `MAX_COMMAND_PATHS` 1,024; `MAX_ASSEMBLED_PAGES` 4,096; `MAX_ASSEMBLED_ROWS` 1,000,000; `MAX_INVENTORY_ISSUES` 1,024; `MAX_ISSUE_DETAIL_BYTES` 4,096; `DEFAULT_QUERY_MAX_WORK` 1,000,000; `DEFAULT_COUNT_CAP` 10,000; `MAX_COUNT_CAP` 1,000,000.
- **Typed limits.** A query that cannot finish within `max_work` returns `QueryLimitProjection(query_id, query_kind, max_work, rows_visited)` (`:1528`), never a partial answer. Routes map that to HTTP 503 `inventory_query_limit` (`server.py:4960-4980`). Counts are exact or a proven lower bound (`CountResult`, `:1432`).
- **How Python charges work** (`python_inventory.py:1502-1528`):
  - A scanning query (filtered tree, grouped tree, rollup, navigation, recent, catalog) is charged the whole index size. When `len(entries) > max_work` it returns the limit result.
  - A directory query is charged the child-bucket entries it visits within its depth.
  - An entry query is charged 1.
  - A continuation page is charged the rows it returns (`:1744-1753`).
  - The conformance tests pin these exact numbers (e.g. `rows_visited == 12` for six queries at `max_work=2`). The difficulty is medium: either fdu copies an index-size charge, or the contract has to stop pinning the counts.
- **Routes never set `max_work`.** Every route uses the 1,000,000 default. An index above 1,000,000 entries (500,000 files plus directories plus symlinks can exceed it) makes broad queries return 503, and the activity tracker's catalog tick fails. This is pre-existing.
- **Continuations.** Only directory, filtered-tree and catalog queries take `after`, and `after` requires `at_version` (`:1302-1307`). Tokens are opaque and one-shot. A typed limit result does not consume the token.
  - Python keeps the whole computed projection in `_page_memos` (capacity 64, and every retained continuation together stays within `MAX_ASSEMBLED_ROWS`, `python_inventory.py:193`, `:1769-1795`). It names evictions (`:1797-1806`).
  - Continuations are validated against the original query parameters (`:1645-1714`).
- **Version pins.** Python retains only the current version. A pinned read without `after` at any other version raises `VersionUnavailableError` (`:1497-1500`). In practice "pinning" means "the continuation memo".
- **The checkpoint read.** `ReadRequest()` with no queries must cost constant work: `entries_visited` and `directories_read` stay 0.

### 1e. State vocabularies (`contract.py:610-756`)

| Vocabulary | Values | Python emits | Host reads |
|---|---|---|---|
| `LifecyclePhase` and `ALLOWED_PHASE_TRANSITIONS` (`:610-665`) | opening, discovering, reconciling, ready, watching, stopped, failed | discovering, reconciling, ready, watching, stopped, failed. `opening` is host-owned. Mapping is in `_state_for`, `:1401-1465`. | Yes. `can_transition_to` (`:752`) is never called anywhere. |
| `Coverage` / `CoverageReason` | building, budget, cancelled, inaccessible, failed | Never `inaccessible` | Only `.complete` |
| `Freshness` | fresh, reconciling, stale, partial | All of them | Never |
| `SourceKind` | scanned, revalidated, journal_scoped, cached | `scanned` only | Never |
| `IssueCode` | permission, disappeared, invalid_metadata, resource_budget, observation_gap, provider_failure | Only resource_budget, provider_failure, observation_gap (`:1426`, `:1436`, `:1448`) | Only `"resource_budget"`, by string comparison, at about 11 sites: `server.py:2530,2643,2853,2981`, `events_route.py:492,854,932,1102,1216`, `walk.py:497` |
| `IndexProgress` | entries_observed, directories_observed, estimated_entries | `estimated_entries` is never set | |

Native difficulty is trivial for the values themselves. The hard part is behaviour: the host collapses state into three status functions that disagree with each other (`server.py:2360`, `events_route.py:825`, `walk.py:496-507`), so partial coverage for any reason other than the budget reads as "scanning".

### 1f. Diagnostics, work and metrics

- **`ProviderDiagnostics`** (`:801-820`): provider, contract, files_indexed, directories_indexed, watch_mode, watch_state, watch_reason, read_requests, cumulative_work, cumulative_metrics.
  - The three `watch_*` fields are free-form strings. Python's values:
    - mode: off, auto, native, polling
    - state: off, starting, running, failed
    - reason: disabled, selecting, override, `fs=<type>`, fs-type-unknown, `fs=<t>-unrecognized`, watch-failed, resource_budget
  - These strings are interpreted by `/api/capabilities` (`events_route.py:1432-1452`, which also emits the literal reason `"inventory-done+watchfiles-native"`), and the budget conformance test pins `"off"` and `"resource_budget"` (`tests/test_inventory_provider_contract.py:1308-1309`).
  - `contract` is `"inventory-provider-v1"` (`python_inventory.py:198`). The benchmark checks it (`devtools/bench_serving.py:88`).
- **`WorkCounters`** (`:758-778`) is documented as "shared with the native fdu engine". Python fills only `rows_visited`, `rows_returned` and `maintained_index_work`. Walk counters (`directories_read`, `entries_visited`, `files_visited`, `bytes_visited`, `observations`, …) are always 0, so comparing work across providers is not like for like. `/_debug/inventory` exposes all of them (`server.py:4777-4823`).
- **`BoundaryMetrics`** (`:781-798`): `bytes_copied`, `lock_wait_ns`, `cpu_time_ns` (None when unavailable), `wall_time_ns`.

### 1g. `ChangeBatch` (`:1592-1629`)

- Fields: `cursor`, `version`, `state`, `dirty_paths` (at most 1,024), `non_file_paths` (a subset of `dirty_paths`; paths that changed from a file to a directory or symlink), `dirty_queries`, `all_dirty`, `reset`, `work`.
- `reset` excludes every other field. `all_dirty` excludes the path lists.
- Replay and reset in Python (`python_inventory.py:1186-1217`, `:4473-4515`):
  - History is bounded by `change_queue_size`, counted in provider batches. A cursor from another session, a cursor ahead of the tip, or a cursor below the replay floor gets a reset.
  - A full subscriber queue becomes a reset.
- **Implicit rules that are pinned by tests but not stated in the contract:**
  1. `dirty_paths` includes every ancestor whose aggregates changed. Python adds ancestor upserts (`remove()` at `:3856-3867`). The SSE stream rereads only the dirty paths, so without this, folder totals in the browser go stale. `tests/test_e2e_filesystem_to_sse.py:177,219` pin it.
  2. Every `FsChange` marks all nine query kinds dirty, including `DIAGNOSTICS` (`:4456-4468`). That is the double crossing `mb-l2eh` describes.
  3. Removing a directory is one batch (`:3788-3867`). `tests/test_e2e_filesystem_to_sse.py:256` asserts exactly one envelope. 2A found fdu produced two.
- Native difficulty: medium. The granularity and coalescing expectations are the hard part.

### 1h. Refresh and priority (`:1632-1712`)

- `RefreshReason` has five values. Only `ACTIVITY_OBSERVATION` (`active_tracker.py:203`) and the default `FILESYSTEM_HINT` are ever sent. `GITIGNORE_CHANGE`, `RECONCILIATION` and `USER_REQUEST` are unused, and Python ignores the reason entirely.
- `ObservationKind` labels are hints only.
- `RefreshReceipt` carries the version plus accepted and rejected paths.
- `PriorityRequest` carries paths plus `max_depth`.

### 1i. Errors (`:1715-1739`)

`InventoryContractError`, `InventoryClosedError`, `VersionUnavailableError`, `ChangeStreamBusyError`, `QueryWorkLimitError`. The coordinator adds `InventoryNotOpenError` and `InventoryConsistencyError` (`coordinator.py:70-75`).

### 1j. Path identity helpers that are part of the contract

Native difficulty is medium: fdu must byte-match these.
- `canonical_inventory_name` (`:255-306`) is a total, injective escape. `%` becomes `%25`; on POSIX, `\` becomes `%5C`; an undecodable byte becomes `%XX` in uppercase hex; on Windows, each byte of a lone surrogate is escaped big-endian.
- `native_inventory_name` (`:325-394`) is its inverse.
- `parse_inventory_path` (`:213-252`) reads inbound spellings.
- `ascii_casefold` (`:414-429`) folds ASCII only.
- `catalog_terminal_suffix` (`:432-444`).
- `derive_ext` (`fs_paths.py:70-99`) gives at most two components, each ASCII alphanumeric and at most 12 characters. It is derived from the escaped canonical name.

---

## 2. Conformance registry and other tests that exercise inventory

### 2a. Provider-parametrized registry

- **How a provider plugs in.** `tests/test_inventory_provider_contract.py:114` defines `PROVIDER_FACTORIES = (pytest.param(PythonInventoryBackend, id="python"),)`. Each case takes `provider_factory` (a zero-argument backend constructor) and `tmp_path`. `_open_settled_provider` (`:143-161`) polls checkpoints until the phase is ready, watching, stopped or failed.
- **The registry** (`PROVIDER_CONFORMANCE_TESTS`, `:116-140`) has 21 cases and matches the table in `arch-inventory-provider.md:440-462`:
  - checkpoint envelope; paged time-dependent reads reuse one `as_of`
  - semantic digest (`:1054`)
  - registry identity from supplied content; supplied registry used for classification
  - budget stop (`:1257`)
  - directory pages lossless when directories outnumber the file budget
  - filtered tree and recent share filter semantics
  - grouped tree answers each group as its filtered tree (`:2153`)
  - catalog predicate semantics; catalog pages lossless
  - work bounds on continuation pages; typed query limits
  - exact-or-lower-bound counts
  - canonical row order
  - version pins fail instead of moving
  - changes resume and gaps become reset (`:1815`)
  - one active iterator; refresh verifies the filesystem; close joins; lifecycle is monotonic
- **One parametrized case is not registered:** `test_group_filters_cut_age_bands_at_their_edges_and_keep_symlinks` (`:2018`). There are 22 parametrized cases against 21 registered. The registration check (`:192-201`) only verifies that registered names exist, so it cannot catch an unregistered one.
- **Assertions that encode Python rather than the contract:**
  - The semantic digest expects `("python", "inventory-provider-v1")` (`:1251`). 2A failed here only on the provider name.
  - The budget case expects watch_state `"off"` and watch_reason `"resource_budget"` (`:1308-1309`).
  - The replay case uses `change_queue_size=1` and expects one refresh of one file to replay as one non-reset batch (`:1815-1866`). This is exactly 2A's journal-capacity failure, still unresolved.
  - The work-limit cases pin exact `rows_visited` (around `:1549-1700`).
  - The checkpoint case asserts phase `WATCHING` (`:986`).
- **Contract-only tests** (not parametrized) cover vocabularies (`:317-353`), bounds, the canonical path rules (`:693-800`), and provider neutrality (`:945-966`). The neutrality denylist omits `metabrowser.wire_models` on purpose, because adding it fails today (`mb-gwlw`).
- **Gitignore oracle.** `tests/test_gitignore_hierarchical.py:166-215` compares against `git check-ignore --no-index` with global config disabled. It is Python-only: it exercises `HierarchicalGitIgnore` directly, not through a provider.
- **File Rollup corpus.** `src/metabrowser/data/file-rollup-format/file-rollup-conformance.json` holds 153 metadata cases, 2 aggregate cases and 21 invalid-registry cases. `tests/test_file_type_contract.py` and `tests/test_file_type_taxonomy_js.py` run it against the Python registry and the JS taxonomy, not through a provider.

### 2b. Product suites

- `tests/inventory_harness.py:53` builds `InventoryRuntime(config=...)` with the default provider, which is always Python, and ignores the environment. **24 test modules use it**, including `test_e2e_filesystem_to_sse.py`, `test_browser_events_route.py`, `test_catalog_feed_server.py`, `test_rollup_route.py`, `test_initial_tree_inline.py`, `test_browser_recent.py`, `test_inventory_coordinator.py`, `test_browser_active_tracker.py`, `test_browser_watch_backends.py`, `test_inventory_walk_work.py` and `test_perf_instrumentation.py`. The plan's preservation table is at `plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md:519-529`.
- **Tests that reach into Python provider internals** (each needs a provider-owned seam before it can run against fdu):
  - Pausing or scripting discovery by monkeypatching `python_inventory.walk_tree`: `test_api_folder_envelope.py:87`; `test_browser_events_route.py:592-601` (this is 2A's "pauses the private walker" test, `test_api_index_progress_does_not_304_while_active`); `test_browser_inventory_api.py:446` (injects a scripted partial walk); `test_catalog_feed_server.py:123-135,405-416`.
  - Bounding retained continuations: `test_browser_inventory_api.py:379-387` patches `python_inventory.MAX_ASSEMBLED_ROWS`.
  - Counting or gating rollup passes: `test_rollup_route.py:152,360,396,433` patch `python_inventory.build_rollup`.
  - Python-only by nature, so these can stay: `test_python_inventory_provider.py`, `test_browser_inventory.py`, `test_browser_rollup.py`, `test_inventory_root_summary.py`, `test_navigation_tally_staleness.py`, `test_inventory_walk_work.py`, `test_startup_nonblocking.py`, and the parts of `test_browser_walk.py` that use `_PythonInventoryStore` directly.
- **Structural tests.** `tests/test_inventory_provider_ownership.py:32,45,113` check that only the factory imports the concrete provider and only the coordinator opens handles.

### 2c. Goldens and the parity registry

- `arch-parity-registry.md:25-34` marks these as covered through `--api` (and `/api/tree` also through `--walk`): `/api/tree`, `/api/rollup`, `/api/recent`, `/api/catalog`, `/api/diagnostics/pending-tallies`, `/api/capabilities`, `/api/index/progress`, `/api/index/meta`. `/api/events` is exempt as streaming (`:79`), and `/_debug/inventory` is exempt (`:82`).
- `devtools/check_parity.py` only checks that goldens run the routes. `--walk` is deliberately not credited as an indirect mode (`:44-54`), and `--check-api` is credited for `/api/tree`, `/api/recent` and `/api/index/progress`.
- `--api` runs the real app lifespan in-process (`cli/asgi_client.py`, `cli/api_cli.py:51-80`). The goldens therefore exercise whichever provider `METABROWSER_INVENTORY_PROVIDER` names, which is good for cross-provider runs.
- But `tests/golden/cli-api-shell.tryscript.md` pins `"provider": "python"` at lines 91, 296, 332, 878 and 886, and pins `"walker_task":"done"`, a Python-shaped field derived from phase at `events_route.py:1111-1121`.
- Interaction rows are browser-only JS sessions; inventory ones are `transport-exempt:/api/events`.
- The SSE stream (snapshot, live changes, coalescing) has no golden, only pytest coverage. 2A recommended a scripted-observation golden session (`explorations/fdu-inventory-adapter/README.md` §"Golden Session Direction").

---

## 3. What the coordinator assumes about a provider (`inventory_engine/coordinator.py`)

| Assumption | Where | Detail |
|---|---|---|
| One handle per root; one change iterator per handle, opened once | `:587-625`, `:649-671` | `_run_change_relay` calls `handle.changes(after=initial.cursor)` once. If the stream ends, that is an error (`:697-698`); a relay failure publishes one host reset and nothing restarts (`:669-671`). `open()` on the same root returns the cached version (`:315-316`), and `close()` is terminal. This is `mb-6o0l`: no recovery path. |
| Provider replay capacity | `:681-687` | The coordinator never resubscribes, so provider replay is used only for the window between the initial checkpoint and the first iteration. Consumer replay is host-side: `_history`, `maxlen=change_queue_size` (`:299`, `:835-844`). A full relay queue drops everything and enqueues a provider reset (`:682-685`). |
| Coalescing boundary | `:700-732`, `:780-813` | Opportunistic: after `sleep(0)`, everything already queued is merged. A merge above 1,024 paths becomes `all_dirty`; any reset wins. Sequences must strictly increase (`:724-729`), and session and fingerprints must never change (`:78-90`). There is no explicit rule for recursive removal, although the 2B checklist marks "host coalescing boundary" done (plan `:396-397`). |
| Read-on-dirty | `events_route.py:417-478` | For each host change: if no browser is connected, nothing happens (`:424-426`). Otherwise one `EntryQuery` per dirty path (`:443-446`). Any `unknown` answer forces a full resync (`:457-462`). `DIAGNOSTICS` dirtiness triggers an extra diagnostics read (`:480-519`). |
| Page assembly | `tree_page_assembly.py:49-158`, `:170-285` | One read session; the first page unpinned, then pinned. At most 3 attempts (`:36`). Cursors must advance and must not repeat; filtered totals must stay constant across pages; every returned entry must have a decoration join (`:124-128`). Catalog assembly is in the route (`events_route.py:1259-1326`) with page size `budget.max_files`, which is 500,000 (`:1269`, chosen so the Python provider does one scan). |
| Overlay | `overlay.py`; `coordinator.py:911-957` | Decorations join only onto entry-bearing projections; catalog decorations are opt-in. The overlay revision is part of `HostVersion`. Overlay paths are validated on write (`overlay.py:146-147`). |
| Per-connection version floor | `events_route.py:362-373`, `:521-528` | A queued change is suppressed when it has the same engine session, `engine.sequence <= floor.sequence` and `overlay_revision <= floor`. This requires sequences to be comparable and monotonic within a session. |
| Root replacement | `coordinator.py:307-326`, `:587-625` | Stop the relay, close the old handle, clear the overlay, open the new one, read a checkpoint, start a new host session, publish a reset. **Production never replaces a root**: only `events_route.py:202` and `walk.py:412` call `open`. The macOS app runs one server per folder. H117, a resident server that adopts a root, would make it a real path; the load-time plan notes Python's `replace_root` returned only about 61% of the memory. |
| Close and join | `:555-585`, `:257-273` | Close is a shielded task that waits for active operations. A cancelled caller still drains the provider operation (`_drain_provider_operation_on_cancel`). |
| Host invalidation | `runtime.py:80-103` | Dirty paths are converted back to native spelling to invalidate host content caches (`projections.py`). |
| Host-side Python tuning | `runtime.py:75`; `server.py:284`, `:2393-2425` | `grouped_tree_admission` lock (justified by the GIL); a 0.10 s cold-start wait loop with `prioritize`, retried every 5 ms (`mb-vknc` (c)). |
| Git pin | `coordinator.py:333-363` | `open_subject` returns a fabricated `EngineVersion` with no handle at all; Git routes own that index. |

---

## 4. Python provider semantics fdu must match

- **Walker order.** Strict FIFO breadth-first search (`walker.py:214-506`). One `os.scandir` per directory runs in a thread (`:397-405`); children are sorted directories first, then by Python string order of the raw name (`:207`). That order is for discovery only: reads re-sort by canonical UTF-8 bytes (`python_inventory.py:732-748`). Post-order finalize (`walker.py:316-365`).
  - A directory's `mtime_ns` and `newest_mtime_ns` are the newest descendant regular-file mtime; symlinks and the directory's own mtime are excluded (`:339-347`, `:493-494`; live path `python_inventory.py:4262-4411`).
  - A placeholder directory has `total_*` set to None, `empty` None and mtime 0.
  - **The semantic digest's `_entry_semantics` leaves out mtimes and symlink sizes** (`tests/test_inventory_provider_contract.py:164-176`), so none of these rules is pinned.
- **Cooperative yields.**
  - The walker sleeps 1 µs every 64 entries (`python_inventory.py:183-184`, `:3921-3924`).
  - The navigation tally pass yields every 256 entries (`:167`).
  - The catalog pass yields every 1,024 entries (`:175`).
  - Changes are emitted in batches of `WALKER_EMIT_BATCH` = 256 (`settings.py:126`).
  - All of this is Python-only; it matters for whether the event loop stays responsive with fdu threads.
- **Watcher before walk.** `PythonInventoryBackend.open` installs the watcher and waits for it before starting the walk (`:4521-4536`).
- **Hidden names.** Names starting with `.` are pruned unless they are exact allowlist names (`fs_paths.py:41-67`). This applies to the walker, the watcher (`watch_backends.py:261`) and refresh validation (`python_inventory.py:2786-2795`).
  - Elsewhere the host repeats this rule with the default allowlist instead of the configured one: `server.py:3112-3124` `_folder_not_indexed`.
  - `ignore_filter.ALLOWLIST_DIRS` is used only in the `default` mode, while the provider uses the strict `gitignore` mode, so `.logs` and `.state` can still be gitignored.
- **Gitignore engine.**
  - `tree.build_gitignore_check` (`tree.py:157-198`) finds a git root by looking for any `.git` marker on the parents (`:137-145`).
  - `HierarchicalGitIgnore` (`ignore_filter.py:86-194`) reads only `.gitignore` files on the ancestor chain, lazily, including files above the served root inside the repository. A deeper file overrides a shallower one, negation is handled by `pathspec.GitIgnoreSpec`, and nothing inside an ignored directory can be re-included.
  - **Not supported:** `.git/info/exclude`, `core.excludesFile` or other global excludes, `.ignore` files.
  - Children inherit their parent's ignored flag without re-matching (`walker.py:270`, `:428-436`).
  - A refresh uses a checker cached with a 300 s TTL (`tree.py:65`).
  - **`.gitignore` edits are never observed live**: the file is a hidden name, so the watcher drops it. Entries already indexed are never re-flagged.
  - `RefreshReason.GITIGNORE_CHANGE` is unused.
  - fdu's ignore engine (ripgrep's `ignore` crate) reads info/exclude and global excludes by default, so its answers would diverge.
- **Symlinks.** Never followed. Stored as leaves with their own lstat size and mtime and `ext=""` (`walker.py:461-470`). Matched against gitignore as files. Counted as leaves for `empty`, excluded from file totals.
  - Refresh rejects a hint whose parent path goes through a symlink (`python_inventory.py:2797-2808`).
  - Group by places symlinks in the Other type group and in age bands by the link's own mtime. The extension, filename, type-family, recency and minimum-size filters drop them (`:2583-2627`, `:2663-2669`).
- **Special files.** Sockets, FIFOs and devices are excluded by the walker (`walker.py:180-184`) and removed on refresh (`python_inventory.py:2893-2896`). The research doc's "retained as `other` leaves" is stale; fdu has `EntryKind.OTHER`, which the 2A adapter dropped.
- **Permission and errors.** A `PermissionError` or a vanished directory in scandir is logged at debug level and **treated as an empty directory, with coverage still complete** (`walker.py:195-204`). No permission issue is ever emitted.
- **File Rollup classification.**
  - The registry is packaged at `src/metabrowser/data/file-rollup-format/recommended-file-types.toml`, loaded by `load_file_type_registry_document` (`file_type_registry.py:21`, `:489`), passed as text, and parsed per provider (`python_inventory.py:1020`).
  - Its fingerprint is computed by `_registry_fingerprint` (`file_type_registry.py:970`) and appears in the navigation payload (`python_inventory.py:3309-3313`) and in the rollup payload (`inventory_rollup.py:676`).
  - The browser compares that fingerprint with its own taxonomy (`builtin_plugins/folder/folder-totals.js:203`, `file-type-summary-model.js:503`), so **fdu must emit a byte-identical fingerprint** unless the host stamps it.
  - The logical extension comes from `derive_ext` on the canonical name.
  - Group IDs come from `registry.name_group_id` or `classify` (`:2680-2695`); semantic suffix matching from `_compile_inventory_filter` (`:2629-2670`).
- **Populations.** Entries carry `total_*` (all) and `unignored_*`. Filtered tree and recent prune by effective ignored ancestors (`:2697-2706`). Navigation splits every row into `[key, tracked, ignored]`.
- **Recent** (`:2708-2768`). Select by (ignored, −mtime, path), cut at `max_rows`, re-sort by (−mtime, path). `gitignored_directories` lists the ignored ancestors of returned rows. Count via `_bounded_count` (`:853-858`). Regular files only.
- **Catalog** (`:861-896`, `:2334-2373`). Regular files only; optionally excludes ignored files; size bound exclusive; terminal suffix by `catalog_terminal_suffix` with both sides ASCII-folded; ancestor names match any ancestor component, case-sensitively; sorted by `path.encode("utf-8")`.
- **Navigation tallies** (`:3175-3322`).
  - Extensions and canonical extensions are ranked by (−total, key) and cut at `limit`; families are ranked by (−total, key) with no cut; presets keep request order.
  - A preset matches when its ID equals the file's semantic group, or the extension is in the preset, or the name is.
  - Recency rows come from sorted mtimes. `oldest_mtime_ns` and `newest_mtime_ns` are included.
  - A bounded-staleness memo is allowed (`arch-inventory-provider.md:133-137`; `:3067-3134`).
- **Budgets.** Only regular files count.
  - The walker stops at `files_indexed >= max_files` (`walker.py:414-416`). The provider then declares truncation when `self._files_indexed >= self._max_files` (`python_inventory.py:3936`). **A tree with exactly `max_files` files reads as truncated.**
  - On truncation: stop the watcher with reason `resource_budget` (`:1105-1114`); phase stopped, coverage partial with reason budget, issue `resource_budget`; skip the end-of-walk aggregate repair.
  - After that, refresh rejects unknown paths and directories (`:1244-1246`), and priority hints are inert (`:1279-1280`).
  - `directories_indexed` includes the root (`:3558-3570`); the golden pins `indexed_dirs: 1`.
- **Work counters.** See §1d and §1f.
- **Watcher** (`watch_backends.py`).
  - `watchfiles.awatch` with the library's default debounce and step **and `DefaultFilter`**. That filter drops `node_modules`, `__pycache__`, `.venv` and similar directories, which the walker does index, so changes under them are not seen live.
  - Native or polling is chosen by filesystem type (`:71-103`, `:188-207`); polling every 2,000 ms (`:345`).
  - Paths are normalized, deduplicated, canonicalized and chunked into refreshes (`:244-311`). A receipt that does not accept every path ends the watch (`:305-308`). A failure sets status failed, freshness stale and an `observation_gap` issue; there is no retry (`mb-dwo6`).
  - **Overflow and rescan events are dropped** inside watchfiles (`mb-pn95`).
  - `mb-pn95`'s note says "the inventory already has a periodic refresh TTL". **That is false**: `INVENTORY_REFRESH_TTL_S` (`settings.py:118`) is only re-exported (`walker.py:44`, `:57`) and never used.
- **Refreshing a directory rewalks its whole subtree** (`python_inventory.py:2873-2881`, `rewalk_subtree` at `:3632`). Removing a directory scans every key in the index and emits one batch (`:3788-3867`).

---

## 5. Bypass audit

| Location | What it reads | Class | Proposed fix |
|---|---|---|---|
| `walk.py:110-180` (`walk_collect`, text `--walk`) and `:556-578` (`stream_entries`, `--walk --stream`) | Calls `walker.walk_tree` directly, with no `hidden_allowlist`; re-stats every path with `abs_path.is_symlink()` (`:150`) | **(b)** The CLI describes the Python walker whichever provider is running (`mb-iyu7`) | Route through `InventoryRuntime` as JSON already does (`walk.py:384-525`), or label the output as the Python walker with the provider name; drop the re-stat in favour of `entry.type`. |
| `tree.py:204-541` (`_dir_tree`, `_subtree_summary`, `_has_any_leaf`, sentinel scans); re-exported by `server.py:229-243`, `:503-531`; cleared at `server.py:728-731` | os.scandir walks of the served tree | **(b, dead)** No production caller; tests use them (`test_proc_browser_tree.py`, `test_browser_wire_shape.py`, `test_tree_folder_markers.py`) | Delete them. Note that the folder-marker badge (`marker_basename`, set up at `server.py:4492`) is emitted only by `_dir_tree`, so that feature is already silently dead. |
| `folder_discovery.py:29-61`, called from `server.py:3159-3163` | Bounded scandir of direct children to find a README; uses Unicode `casefold` | **(b-minor)** A second structural read; it must still work for folders outside the index (hidden or reached through a symlink) | Keep it as an explicit host exemption for folders outside the index, or answer indexed folders with a depth-1 `DirectoryQuery`; document either way. |
| `server.py:3112-3124` `_folder_not_indexed` | Re-applies the hidden and symlink scope rules with the default allowlist | **(b-minor)** Duplicates scope rules | Use `runtime.config.hidden_allowlist`, or ask the provider. |
| `source.py:123-139`, `:367` (`ContentHandle.from_path` exists/is_dir/is_file) and `paths_safe.py:70-121`, used by `/api/tree` and `/api/rollup` (`server.py:2705`, `:2797`) | realpath plus up to three stats per request | **(a)** Safe-path containment, which the arch doc says stays above the engine. It is not lexical, though; the research doc's item 4 asked for a lexical check plus the provider. | Optional: a lexical containment check plus `EntryQuery`. Low priority. |
| `server.py:3271-3330` and on (`/api/file` file branch), `raw_file` (`:4308` and on), `sse.py:300-330` (`/api/stream`), KPress, `charts.py:67`, `gz_io.py:358-416`, `projections.py` MtimeCache | File contents and stats | **(a)** Content | None. |
| `active_tracker.py:75-107` and `:109-119`; `activity.py:40-80` | A `CatalogQuery` every 5 s (`ACTIVE_TRACKER_INTERVAL_S`), then a host `stat` of each candidate plus a `*.pid` glob of its parent | **(a, by design)** A second observer that feeds verified refreshes (`RefreshReason.ACTIVITY_OBSERVATION`). It also re-checks the provider's predicates with a *different* suffix rule (`PurePosixPath.suffix.lower()`, `:64-72`) and raises `TypeError` on a mismatch (`:103-104`). | Re-check with `catalog_terminal_suffix`. The 5 s whole-index catalog tick is a cost that must be measured per provider. |
| `server.py:1611-1613` (`.git` exists, to decide the Commits tab); `repository_context.py:66-90`; `git/repo.py` | Git markers | **(a)** Git | None. Note there are two git-root finders with different rules: `tree._find_git_root` (any `.git` marker, used for gitignore) and git discovery. |
| `git/content_routes.py` (Git pin tree, rollup, catalog, tallies; reuses `inventory_rollup.build_rollup`, `:118`, `:916`) | `git ls-tree` and `cat-file` | **(a)** A separate subject with no provider (`coordinator.py:333-363`). It is a parallel implementation of the projection semantics. | Out of fdu's scope. With `mb-gwlw`, it would share the host-side rollup shaping. |
| `cache/*`, `home.py`, `builtin_plugins/github/*`, `asset_stamps.py:140`, `http_caching.py:99`, `plugin_loader/*`, `logutil/parsing.py:1507-1525` | Repository cache, home and state, package assets, plugin directories, JSONL discovery for `metab tail` | **(a)** Not the served tree | None. |
| `builtin_plugins/diff/sidekick.py:522-557` (container children) | Patch-file contents | **(a)** | None. |
| macOS app (`apps/macos/Sources`) | Stats only the `metab` executable (`Setup/FileWatch.swift`); never enumerates the served tree | **(a)** | None. |
| `--show`, `--api`, `--check-api` | Go through the in-process app and coordinator | Not a bypass | Provider-selectable through the environment already. |

`arch-inventory-provider.md:429-431` says "Nothing above this contract changes, with one exception: `metab --walk`". That understates it: add the README scan, the duplicated scope rule, the activity stats, the dead tree walker, and Git pins.

---

## 6. Selection and packaging

- **Factory.** `inventory_engine/factory.py:12-30` is sealed and has only `PYTHON`. An unknown name raises `ValueError`. `runtime.py:46-49` reads `METABROWSER_INVENTORY_PROVIDER`; `events_route.py:186-189` and `walk.py:411` use it.
- **No `metab` flag** selects the provider. The variable is deliberately not read from dotenv (`dotenv.py:97-99`, `:66-74`).
- **The macOS app cannot select fdu today.** It runs a user-installed `metab`, found from the saved path, `METABROWSER_METAB`, `~/.local/bin`, uv's tool bin directory or Homebrew (`Runtime/RuntimeDiscovery.swift:151-160`). It launches `metab ROOT --no-open --exit-on-eof --host --port` (`Supervision/ServerLaunch.swift:59,68`). Its child environment is an allowlist (`Runtime/ChildEnvironment.swift:14-33`) that **drops `METABROWSER_INVENTORY_PROVIDER`**.
  - To A/B or ship fdu in the app, pick one: add the variable to `passedThrough` (an app change only); add a `metab --inventory-provider` flag (then raise `MetabRequirement.minimumRelease`, currently `[0,12,1]` at `Setup/MetabVersion.swift:54`); or flip the default.
  - The app does not bundle Python, so the fdu wheel must come through the uv tool install, i.e. as a dependency or extra of `metabrowser`. The publishing plan notes that a bundled, hardened Python would need `disable-library-validation` (`plan-2026-11-16-macos-app-publishing.md:194-196`).
- **Python range.** `requires-python = ">=3.12,<4.0"` (`pyproject.toml:20`). fdu's `abi3-py312` wheels fit, except on 3.14t.
- **Dependencies today.** `pathspec>=1.1.1` and `watchfiles>=1.2.0` (`pyproject.toml:48,61`). There are no optional-dependency extras yet.
- **Supply chain** (`SUPPLY-CHAIN-SECURITY.md`):
  - First-party packages skip the cool-off, but the review is still required: a row in the first-party table (`:38-60`) recording the lock delta, the runtime-dependency delta and every published artifact's SHA-256 against `uv.lock`.
  - "an unexpected … binary artifact … [is] a blocker until it is explained and reviewed" (`:298-299`).
  - Precedent for the override: `uv.toml` already has `exclude-newer-package` entries for kpress, softschema and flowmark-rs. fdu 0.6.0 (2026-11-12) is within the 14-day window, so it needs one.
  - `make verify` runs installed-wheel smoke tests and distribution inspection; both need a with-extra and a without-extra variant.
- **CI.**
  - `ci.yml:49-51`: test matrix Python 3.12, 3.13, 3.14 and **3.14t** on `ubuntu-latest`. There is no fdu wheel for 3.14t: the build falls back to the sdist (needs Rust) or fails with `--no-build`. Decide skip versus require.
  - `macos-app.yml:44-56`: macos-26 arm64 runs `make install` and the live app tests against `.venv/bin/metab`.
  - `publish.yml` runs `make verify` on 3.13. There are no Windows or macOS Python test jobs.
  - The plan requires building the exact fdu revision as a wheel on every supported Python and platform job (plan `:451-453`).

---

## 7. Performance harness, latest measurements, and what a clean A/B needs

### 7a. Harnesses

- **`devtools/bench_serving.py`.**
  - `INVENTORY_PROVIDERS = ("python",)` (`:87`); `--provider` choices (`:1511`), passed to the server through the environment (`:571`).
  - Three phases: `cold_scan` (`:961`), `scan_with_client` (`:984`, which polls the Overview rollup and records `first_count_s`, `wall_s` and rollup latencies) and `settled` (`:1031`: aggregated, retained and 304 rollups, navigation first and memoized, catalog body and 304, process resources).
  - JSON results are diffable through `--baseline`. `_record_inventory_identity` (`:1270-1302`) requires the provider and contract reported by `/_debug/inventory` to be consistent across phases.
  - **Completion is detected by regex on a Python log line**: `inventory walker complete: provider=… contract=… status=… files=… entries=… elapsed=…ms` (`:117-121`, emitted at `python_inventory.py:3973-3982`). The same regex is in `explorations/performance-loop/run.py:700-708`.
  - `explorations/performance-loop/scan_bench.py:104-107` drives `tests.inventory_harness`, so it is Python-only.
  - `WheelAttestation` attests only the metabrowser wheel.
- **The performance loop** (`explorations/performance-loop/README.md`).
  - Method: hypothesis, then measure the unchanged build three or more times, change, measure again, decide, record (`:36-49`).
  - Durable storage (`:188-239`): protocols committed as `exp-NNN-protocol.txt` before timing; samples committed; raw output in `.bench/`; the series lock at `$(git rev-parse --git-common-dir)/metabrowser-series.lock`.
  - Accept rule (`:2476-2540`): medians move in the predicted direction; ranges do not overlap at n≥3; at least two back-to-back pairs beyond tolerance (1.3x through `judge()`); nothing else regresses unexplained; a judgment that the complexity is worth it. For effects under 2x, use five or more interleaved pairs from clean, content-identified builds.

### 7b. Where time goes (latest recorded)

- **Scale benchmark, Python, 2026-11-15, M1 Pro** (`docs/scale-benchmark.md:56-66`):

  | Files | First folder counts | Scan with a client attached | Peak RSS |
  |---:|---:|---:|---:|
  | 100,000 | 1.19 s | 5.5 s | 174 MiB |
  | 300,000 | 1.38 s | 19.3 s | 331 MiB |

- **Walk.** 300,000 files took 12,871 ms warm, about 43 µs per file (load-time plan H18, `:751`). On the flat 300k corpus, a bare filesystem traversal takes 0.87 s against a 12.9-15.5 s detached walk: **about 93% of the walk is Python above the filesystem** (`plan-2026-09-15-flat-tree-delivery-cost.md`, "Background").
- **Attached delivery.** About 13.86 µs per entry for the entry query, contract entry, projection, decoration, wire record and catalog upsert, with three validations of each path. On the flat corpus, the attached walk took 31.3 s against v0.9.1's 18.7 s, and the settled `/api/catalog` took 2,575 ms against 663 ms (same plan).
- **2A materializing adapter.** One eight-query read cost 852 ms and about 13 MB, materializing 8,830 entries (spike README).
- **Projections.**
  - Navigation tally pass: about 2 s at 400,000 entries (`python_inventory.py:3043-3047`).
  - Grouped tree: 92-96 ms for six groups on 100,000 files, against 0.62-0.69 s when each group is read separately (`:2489-2494`).
  - `MAX_TREE_GROUPS` measurements: 0.27-0.33 s for the six groups on 260,000 files (`contract.py:103-110`).
- **Review conclusions.** The architecture review says walker costs are CPython's and demotes the Python-walker hypotheses until U3 (`mb-wb7e`) measures fdu against Python. H21 (persisted index, `mb-omhf`) and H46 wait on U3 (`research-2026-11-14-performance-architecture-review.md:182-185`, `:229-262`; `plan-2026-11-14-performance-campaigns.md:133-151`). The largest app-visible gains are H117 (server start) and H112, not inventory.

### 7c. What a clean Python-versus-fdu A/B needs

1. Register fdu in the factory and in `INVENTORY_PROVIDERS`; run **one build** with an interleaved provider axis, which isolates the provider better than comparing two builds.
2. A provider-neutral completion signal in place of the Python log regex, for example a coordinator-emitted line on the first non-discovering phase, or discovery elapsed time in `ProviderDiagnostics`.
3. Attest the fdu wheel too: exact version and digest per platform.
4. Check semantic equality on the corpus before timing: diff `metab --walk --format json` output and selected `--api` digests per provider. The plan requires it; no tool exists.
5. Same immutable corpora (synthetic, `build_project_corpus` with real `node_modules` and `.venv`, and corpus v2), A/A calibration, a committed protocol, the series lock.
6. Report all three layers. Interpret work counters with care: Python leaves walk counters at 0. Expect the attached-browser layer to be dominated by host per-entry costs unless `mb-l2eh` lands (§9).

---

## 8. What changed since the August plan

- **Contract additions after 2A and 2B.**
  - `GroupedTreeQuery`, `TreeGroupFilter`, `MAX_TREE_GROUPS` and the Group by fields on `InventoryFilter` (`band_within_seconds`, `older_than_seconds`, `type_group`), with symlink placement rules. Commits `d94c119f`, `d483cd18`, `6ac888a9`, `311c0db5`, `f69c0d20`, `3916d43e` (2026-11-14/15); `plan-2026-11-15-files-grouping-…:561`.
  - `InventoryRuntime.grouped_tree_admission` and evicted-cursor naming.
- **Path identity is now total.** Escaping covers `%25`, `%5C` (0.12, `CHANGELOG.md:2543-2549`), `native_inventory_path` and `parse_inventory_path`. The "portable-path completeness and bounded issue examples" that the 2B checklist still lists (plan `:390-391`) was **removed** in favour of total escaping (`contract.py:61-69`).
- **Total orders.** ASCII-only case folding, `catalog_terminal_suffix`, the recent demotion "in every branch", directory-first UTF-8 order.
- **Resource budget means stopped.** Watcher reason `resource_budget`; `/api/*` report `truncated` (`CHANGELOG.md:2662-2670`).
- **Repository subjects and Git pins** (`source.py`, `coordinator.open_subject`; `CHANGELOG.md:2220-2334`): a second, provider-less index.
- **Root-summary bounded staleness, cooperative-yield retuning, the close-race watcher fix** (`20a00fd3`), and the read-session lease (PR #101 final review).
- **Object data model plan** (#453, `plan-2026-11-14-object-data-model-and-views.md`):
  - Folder and file objects take `updated_at` from mtime and newest mtime (`:471-472`); a folder's `totals.complete`.
  - **Recent Changes needs "a cursor below a time"** for changed files (`:769-775`), i.e. a `RecentQuery` continuation. That is a contract change both providers would need in one commit (Phase 2).
  - It leaves `/api/tree` and `/api/recent` encodings unchanged (`:868`, `:990-999`).
- **macOS app plans.** One server per folder; `MetabRequirement`; the child-environment allowlist; `mb-omhf` (persisted index) now under the macOS epic (`plan-2026-11-10-native-macos-app.md:484`); H117 resident server (load-time plan `:967`), which would make root adoption and replacement real.
- **Performance campaigns** (2026-11-14). U3 gates Loop 2. H40 is superseded by `mb-hej8`, and `mb-nbvk` was closed as a duplicate.
- **Beads.**
  - `mb-hej8` is blocked by `mb-6o0l` (restart), `mb-iyu7` (`--walk`), `mb-l2eh` (invalidation-only batches) and `mb-lsgg` (closed).
  - Open siblings: `mb-gwlw`, `mb-nqgs`, `mb-ed9h`, `mb-vknc`, `mb-pn95`, `mb-dwo6`.
  - `mb-wb7e` (U3) blocks `mb-omhf` and `mb-19em`.
- **The 2A spike no longer runs against main.** Its adapter (`adapter.py:223,227,294-296`) uses names that no longer exist; `evidence.json` lists renamed tests; it covered 12 cases where there are now 21 (plus one unregistered).

---

## 9. Refactor list

"Spike" means it blocks a 2C prototype or the U3 A/B against main. "Prod" means it blocks only production adoption.

| # | What | Why | Files | Size | Blocks |
|---|---|---|---|---|---|
| 1 | Add `InventoryProvider.FDU` with a lazy optional import, a typed startup failure, and no silent fallback | Selection by name, for the benchmark and the CLI | `inventory_engine/factory.py`, `runtime.py`, `devtools/bench_serving.py:87`, `docs/command-line.md:529` | S | Spike |
| 2 | A provider-neutral discovery-complete signal | The benchmark and the loop parse a Python log line | `bench_serving.py:117-121,619-643`; `performance-loop/run.py:700-708`; coordinator or runtime | S | Spike (U3) |
| 3 | Provider-selectable test harnesses | 24 modules hard-wire Python | `tests/inventory_harness.py:53`, `test_inventory_provider_contract.py:114`, `scan_bench.py:104` | S | Spike |
| 4 | Remove Python assumptions from the conformance cases: provider name, watch strings, capacity-1 replay in provider-batch terms, the exact `rows_visited` charging; register the case at `:2018` and make the registration check two-way | They currently encode Python's implementation (2A failures still present) | `tests/test_inventory_provider_contract.py:192-201,1251,1308,1815-1866,1549-1700,2018`; `arch-inventory-provider.md:440-462` | S-M | Spike |
| 5 | A provider-owned discovery gate or scripted-discovery seam, plus provider-neutral rollup-pass and eviction counters | Route tests monkeypatch `python_inventory.walk_tree`, `MAX_ASSEMBLED_ROWS` and `build_rollup` | `test_api_folder_envelope.py:87`, `test_browser_events_route.py:601`, `test_browser_inventory_api.py:379-387,446`, `test_catalog_feed_server.py:135,416`, `test_rollup_route.py:152-444`; a backend-constructor hook in both providers (not in `InventoryConfig`) | M | Spike (product suites) |
| 6 | State the implicit rules in the contract and pin each with a case: ancestors in `dirty_paths`; directory mtime and newest mtime; placeholder facts; empty page for an undiscovered folder; root counted in `directories_indexed`; the budget `>=` rule; symlink size; recursive-removal coalescing (for example, one refresh receipt equals one host change) | fdu cannot match unwritten rules; the semantic digest omits mtimes | `contract.py` docstring, `arch-inventory-provider.md`, new conformance cases, possibly `coordinator.py:700-732` | M | Spike |
| 7 | **Decide permission and inaccessible semantics** and teach the host a "complete with issues" status | Python claims completeness; an honest native provider would read as "scanning" forever and answer `unknown` | `walker.py:195-204`; `server.py:2360`, `events_route.py:825`, `walk.py:496-507` (merge into one status helper) | M | Spike (parity) |
| 8 | Lift gitignore conformance to the provider level; decide on info/exclude, global excludes and live `.gitignore` edits (`GITIGNORE_CHANGE`) | The Python engine is narrower than git and the ignore crate; edits are never observed | `tests/test_gitignore_hierarchical.py` to provider cases; `ignore_filter.py`, `tree.py:157-198`, `watch_backends.py:261` | M | Spike (parity) |
| 9 | Decide the observation scope: `DefaultFilter` blind spots, overflow/rescan to reconciliation (`mb-pn95`), retry (`mb-dwo6`); remove the dead `INVENTORY_REFRESH_TTL_S` | fdu's watch semantics will differ; the SSE suites would diverge | `watch_backends.py:354-360`, `settings.py:118`, `walker.py:44,57` | M | Prod |
| 10 | `mb-gwlw`: contract-owned aggregate types; move `build_rollup` and navigation row shaping to the host; the host stamps registry identity; type the navigation rows (`mb-nqgs`) | Otherwise fdu must emit browser wire models and a byte-identical registry fingerprint | `contract.py:95,1406-1424`; `inventory_rollup.py` (744 lines); `wire_models.py:228-265`; `server.py` rollup and tree routes; `git/content_routes.py:916` | L | Prod (a spike can materialize, as 2A did) |
| 11 | `mb-l2eh`: optional bounded facts on `ChangeBatch`; stop dirtying `DIAGNOSTICS` on every `FsChange` | The attached-walk host cost (~14 µs per entry) would hide fdu's gain | `contract.py:1592`, `coordinator.py:734-813`, `events_route.py:417-478`, `python_inventory.py:4456-4468` | M | Prod (and U3 interpretation) |
| 12 | `mb-6o0l`: a supervise-or-reopen policy, or adapter-owned recovery under one session | A native crash ends live updates until restart | `coordinator.py:315-316,649-671,697-698` | M | Prod |
| 13 | `mb-iyu7`: `--walk` text and stream modes through the coordinator, or explicitly labelled | CLI parity | `walk.py:110-180,556-578`, `cli/walk_cli.py` | S-M | Prod |
| 14 | `mb-ed9h`: move `walker.py`, `watch_backends.py` and the gitignore builder under `providers/python/`; delete the dead `tree._dir_tree` family and its `server.py` re-exports; add a reverse ownership test | Prevents new bypasses; removes a second walker | `tree.py:204-541`, `server.py:229-243,503-531,728-731`, `test_inventory_provider_ownership.py` | M | Hygiene |
| 15 | Typed watch vocabulary (mode, state, reason enums plus detail); update `/api/capabilities` and the goldens in the same commit | Free-form strings are interpreted by the host | `contract.py:801-820`, `events_route.py:1432-1452`, goldens | S | Prod |
| 16 | A cheaper record crossing: trusted construction for provider-built records, or columnar catalog and recent pages; per-provider catalog page size | Python `__post_init__` validation runs for every row from any provider (about 1-4 µs each); catalog pages are 500k rows | `contract.py:829-866,1443-1500`, `events_route.py:1269`, `active_tracker.py:87-95` | M-L | Prod perf |
| 17 | Specify the work-charging model, and set route `max_work` relative to the index size | Exact charges are pinned; the 1M default makes huge trees answer 503 | `contract.py:122`, `python_inventory.py:1517-1528`, routes | S-M | Spike (conformance) |
| 18 | Goldens: elide or parametrize provider identity; a CI job running the goldens and route suites with fdu | `cli-api-shell.tryscript.md:91,296,332,878,886` | goldens, `ci.yml` | S | Prod |
| 19 | Packaging: a `metabrowser[fdu]` extra with an exact pin; `exclude-newer-package`; the SUPPLY-CHAIN row with every wheel SHA; smoke tests with and without the extra; a 3.14t decision; the macOS app's selection path (allowlist or flag, plus `minimumRelease`) | Shipping and the app A/B | `pyproject.toml`, `uv.toml`, `uv.lock`, `SUPPLY-CHAIN-SECURITY.md`, `devtools/check_distribution.py`, `ci.yml`, `macos-app.yml`, `ChildEnvironment.swift:14-20`, `MetabVersion.swift:54` | M | Prod |
| 20 | Benchmark additions: fdu wheel attestation, a semantic-equality pre-check, the engine-only layer (refresh the 2A `run.py` against the current contract) | A clean U3 | `bench_serving.py`, `explorations/fdu-inventory-adapter/` | M | Spike (U3) |
| 21 | Revisit Python-motivated host tuning: `grouped_tree_admission`, the cold-start wait, the 4,096-row tree pages, the catalog page size | They may penalize or mis-measure fdu | `runtime.py:75`, `server.py:284`, `settings.py:115` | S | Prod |
| 22 | Fix doc drift (§10) | Docs and code disagree | `arch-inventory-provider.md`, both plans, the research doc, bead notes | S | Neither |
| 23 | Future: a `RecentQuery` time cursor (data model, Phase 2); a persisted index using `SourceKind.cached/revalidated` (`mb-omhf`, after U3) | Later contract changes; land them in both providers at once | `contract.py:1171` | M / L | Later |

**Smallest set that unblocks the U3 reading through `bench_serving`:** items 1, 2, 20, plus a refreshed adapter.

**For a meaningful conformance spike, add:** 3, 4, 6, 7, 8, 17.

---

## 10. Top risks and surprises

1. **Permission-denied directories read as complete.** Python silently treats them as empty with complete coverage, never emitting `inaccessible` or `permission`, and the host reads only phase, `complete` and `resource_budget`. An honest native provider changes visible status everywhere, and `unknown` lookups trigger cold-start waits and SSE resyncs. Decide before any parity run.
2. **Host-side per-row costs remain after a swap.** They include record validation, read-back per dirty path, wire records, 500k-row catalog pages and the 5 s activity catalog tick. A faster walk may barely move the attached-browser numbers unless items 11 and 16 land.
3. **Conformance encodes Python.** Batch granularity (capacity-1 replay), exact work charges, `"python"`, and the `"off"`/`"resource_budget"` strings. The 2B checkbox says the capacity rule was settled; the test says otherwise.
4. **Wire coupling.** Rollup and navigation payloads are browser wire models, and the browser compares the registry fingerprint, which fdu would have to reproduce byte for byte.
5. **Gitignore is narrower than git.** No info/exclude, no global excludes; `.gitignore` edits are never observed live because the file is hidden. fdu's ignore crate would diverge. The only git oracle is Python-only.
6. **The watcher is blind under `node_modules`, `.venv` and `__pycache__`** (watchfiles `DefaultFilter`), drops overflow, never retries, and has no periodic reconciliation, despite `mb-pn95`'s note citing `INVENTORY_REFRESH_TTL_S`, which is dead. A correct native watcher changes SSE volume and behaviour.
7. **The macOS app cannot select a provider.** The child-environment allowlist drops `METABROWSER_INVENTORY_PROVIDER`.
8. **Packaging gaps.** No fdu wheel for CI's 3.14t job; fdu 0.6.0 is inside the 14-day window, so it needs the first-party override and review.
9. **The 2A spike is stale** against the current contract (vocabulary renames, removed `portable_path`, grouped tree), so re-measurement needs adapter work first.
10. **Documented but unimplemented or wrong:**
    - `valid_until_ns` is said to feed fingerprints (`arch-inventory-provider.md:213-217`); nothing produces or consumes it.
    - "Only `--walk` bypasses" (`:429-431`).
    - The pluggable plan's "expected registry identity … fails the open" (§"Shared Classification Packet").
    - The 2B item "portable-path completeness".
    - The research doc's "special objects retained as `other`".
    - The plan's "host coalescing boundary" done; it is opportunistic only.
    - `can_transition_to` is never enforced.
11. **Dead features.** The folder-marker tree badge only exists in the legacy `_dir_tree`. `IndexProgress.estimated_entries`, three of the five `RefreshReason` values, and three of the four `SourceKind` values are never produced.
12. **Smaller semantic edges.**
    - A tree with exactly `max_files` files reports truncated (`python_inventory.py:3936`).
    - The default `max_work` of 1,000,000 makes trees above 1M entries answer 503 for broad queries.
    - The all-known SSE snapshot is capped at depth 20 (`events_route.py:336`, `INVENTORY_MAX_DEPTH`).
    - Three divergent status-mapping functions.
13. **Root replacement is test-only in production today.** That simplifies fdu, but H117 (resident server) would make adoption and replacement real; Python returned only about 61% of memory on `replace_root`.
14. **History.** The shallow clone hides September and October commit detail; §8 is reconstructed from `CHANGELOG.md`, docs and beads, so verify specific commit claims against GitHub if they matter.