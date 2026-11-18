# fdu `main` (`4450be7`, 0.6.0) as Metabrowser’s inventory backend: API map, gap matrix, and proposed fdu changes

Research input to the
[revisited fdu backend research](../../../docs/project/research/research-2026-11-17-fdu-backend-revisited.md),
recorded on 2026-11-17 by a read-only investigation of fdu `4450be7` (0.6.0) and
Metabrowser `db08e3b8`. Paths prefixed `fdu:` are in the fdu repository; others are in
Metabrowser. Line references describe those revisions.
The `0583a1a` baseline was read through the GitHub API, and PyPI metadata from one
public JSON read.

## 0. Bottom line

- **The lifecycle core is native-ready.** That covers open, coherent read, the journal,
  refresh, close, version pins, opaque one-shot continuations, typed limits,
  exact-or-at-least counts, and lifecycle/coverage/freshness/source/issue values that
  are nearly 1:1 with `contract.py`.
- **Of Metabrowser’s 9 query kinds, only 3 map natively today:** entry, directory and
  catalog. Filtered tree, grouped tree, rollup, navigation and recent have no bounded
  native projection. Diagnostics can be assembled by the adapter from small projections.
- **fdu has built the indexes Phase 3C approved but nothing reads them.**
  `ServingIndexes` maintains recency order, per-directory type tallies and exact-name
  tallies on every commit (`fdu:crates/fdu-core/src/index.rs:834-846`, writes at
  `:4315-4390`). Only tests read them (`index.rs:7563+`). This costs memory and commit
  time with no benefit yet.
- **Hard blocker 1: fdu 0.6.0 refuses Metabrowser’s current registry document.**
  Metabrowser’s registry is `schema_version = 5` with a new `chroma_ratio` field
  (`src/metabrowser/data/file-rollup-format/recommended-file-types.toml:28,95`). fdu
  reads only schemas 3 and 4 and rejects unknown fields
  (`fdu:crates/fdu-core/src/classify/file_rollup_manifest.rs:31,128-171,198-201`). So
  `OpenedOptions(type_rules=...)` raises at open.
- **Hard blocker 2: canonical path encoding diverges.** Metabrowser escapes a POSIX
  backslash as `%5C` (`src/metabrowser/inventory_engine/contract.py:51-56,263-267`). fdu
  escapes only `%` and undecodable bytes
  (`fdu:crates/fdu-core/src/opened/read.rs:1104-1117`). That changes both the path
  identity and the row order for such names.
- **Contract conflicts that need a joint decision, not adapter code:**
  - Tree work budget: fdu’s is soft (a page always returns at least one row).
    Metabrowser’s conformance test expects a hard `QueryLimitProjection` and exact
    `rows_visited` (`tests/test_inventory_provider_contract.py:1550-1640`).
  - Observer failure: fdu reports `Failed` + `Partial`. Metabrowser expects `ready` +
    `stale`.
  - Filtered-tree paging: fdu’s plan wants complete-or-limit.
    Metabrowser’s contract keeps `after` and per-group continuations.
  - Bundle and page sizes: fdu allows 16 projections per read and 4,096 rows per page.
    Metabrowser sends up to 1,024 queries per read and catalog pages of `max_files` rows
    (500,000).
- **Version retention is tip-only.** Any commit invalidates `expected` pins and every
  continuation. Paged assembly on a churning tree restarts, so the “prove page completion
  under churn” gate (`contract.py:1286-1291`) is an open performance risk.
- **The performance record for the opened route is thin.** On macOS, opened discovery
  measured 6.5× the one-shot wall time and 5.5× its peak memory (exp-126, September).
  Linux was 2.75× (exp-145, before the 0.3.0 getdents64 reader).
  Discovery runs as one single-threaded producer.
  On Linux, `open()` with observation first walks the whole tree to register inotify
  watches. Before entering `watching`, fdu re-walks the whole root once more.
- **Packaging is ready.** fdu 0.6.0 has been on PyPI since 2026-11-12: cp312-abi3 wheels
  for manylinux2014 x86_64 and aarch64, macOS 11 arm64 and x86_64, Windows amd64, plus
  an sdist. It has no Python dependencies.
  Pin it exactly as an optional extra; the 0.x opened-root API breaks across minor
  releases.

* * *

## 1. The opened-root API today (Rust and Python)

### 1.1 Surface

| Operation | Rust (`fdu:crates/fdu-core/src/opened.rs`) | Python (`fdu:crates/fdu-py/python/fdu/opened.py`) | Metabrowser `InventoryHandle` |
| --- | --- | --- | --- |
| open | `OpenedIndex::open(&Plan, OpenOptions)` `:247-263`. A plan comes from `OpenOptions::plan` `:151-164` and must use `CachePolicy::Off` (`fdu:crates/fdu-core/src/execution.rs:478-487`). | `OpenedIndex.open(root, OpenedOptions)` `:1456-1481` | `InventoryBackend.open` (`contract.py:1755-1757`) |
| read | `read(ReadRequest{projections, expected})` `:356-359` → `read.rs:23-216` | `read(*projections, expected=)` `:1483-1503`; `state()` `:1505-1508` | `read(ReadRequest)` |
| changes | `changes(ChangeRequest{after, timeout})` `:371-374` → `journal.rs` | `changes(after, timeout=)` `:1510-1520` | `changes(after=)` async iterator (adapter owns the bridge) |
| refresh | `refresh(&[PathBuf])` `:382-477`, at most 1,024 paths (`:39`) | `refresh(paths)` `:1522-1527` | `refresh(RefreshRequest)`, at most 1,024 paths |
| prioritize | `prioritize(&[PathBuf])` `:317-336`, **at most 64 paths** (`:37`); raises `OpenedIndexStopped` once stopped (`:325-327`) | `prioritize(paths)` `:1529-1534` | `prioritize(PriorityRequest)`, at most 1,024 paths plus `max_depth` |
| close | `close()` `:308-310`: idempotent; concurrent callers share one stored outcome (`:195-199`) | `close()` `:1536-1539`, context manager | `close()` |

### 1.2 Open options vs `InventoryConfig`

| fdu option | Where | Metabrowser item | Status |
| --- | --- | --- | --- |
| `prune_hidden` + `hidden_allow` (exact component names, any depth; prune, not tag) | `opened.rs:102`; `fdu:crates/fdu-core/src/admission.rs:19-52`; Python `:291-292,346-347` | `include_hidden=False`, `hidden_allowlist` (`contract.py:485-486,506-516`) | native-ready |
| `follow_symlinks` (setting `true` is refused) | `opened.rs:98`; CHANGELOG 0.1.0 Known limitations | `follow_symlinks=False` | native-ready |
| `one_filesystem` | `opened.rs:100` | `one_filesystem=False` | native-ready |
| `exclude_special` (drops `EntryKind::Other`) | `opened.rs:104` | `admitted_object_kinds = {file, dir, symlink}` | native-ready |
| `max_files` (`DiscoveryBudget`: retained regular files; execution policy, not scope) | `opened.rs:76-85` | `DiscoveryBudget.max_files` (`contract.py:469-476`) | native-ready |
| `type_rules` (registry document text, schema 3/4, or a `[[kind]]` manifest) | Python `:310-317`; binding `opened_binding.rs:1218-1227` | `registry_document` (`contract.py:483`) | **missing: schema 5 is refused** (F1) |
| `journal_capacity_bytes` (default 8 MiB, minimum 64 KiB) | `opened.rs:116-121`; `engine_contract.rs:1807` | `change_queue_size=1_024` items (`contract.py:490`) | adapter-translatable; Metabrowser should restate it (M2) |
| `observe: bool` (native backend with default `WatchConfig`; no backend choice from Python) | binding `opened_binding.rs:1214`; `watch.rs:91-104` | `watch_mode` auto/native/poll/off (`contract.py:491`) | auto/native/off translatable; **poll missing** (F18) |
| `control_budget` / `control_line_limit` (`.gitignore` bounds; defaults 4 MiB and 16 KiB) | Python `:318-327`; `fdu:crates/fdu-core/src/control.rs:51,59` | none (the Python provider reads every `.gitignore` unbounded) | Metabrowser decides (M7) |
| `batch_size` | `opened.rs:96` | none | n/a |
| Always on, not options: `.gitignore` observed, populations `all`/`unignored`, one breadth-first producer (`threads: Some(1)`) | `opened.rs:166-192`, esp. `:179-186` | n/a | see §10 risk |

### 1.3 Read projections

`ReadProjection` (`fdu:crates/fdu-core/src/engine_contract.rs:941-999`) and its Python
mirrors (`opened.py:512-650`). Bounds: at most 16 projections per read
(`engine_contract.rs:769`), 4,096 rows per page (`:771`), work at most 1,000,000
(`:773`), `count_cap` at most 1,000,000 (`:779`).

| Projection | Semantics | Metabrowser use |
| --- | --- | --- |
| `Lookup{path}` | `Knowledge<EntryValue>`: present / absent / unknown{reason} (`read.rs:55-71`) | `EntryQuery`: native |
| `RollUp{path}` | `PartitionRollUpSummary` (all/unignored: files, dirs, bytes, allocated, newest_mtime_ns, newest_changed_ns); `Refused(NotADirectory)` for a file (`read.rs:72-98`) | aggregates and diagnostics counts |
| `Tree{path, depth, include_ignored, page}` | Breadth-first level order, directories first, canonical byte order. `include_ignored=false` prunes the whole subtree. Rows are full entries with rollups (`read.rs:549-739`). | `DirectoryQuery`: native order |
| `Flat{selection: EntrySelection, shape, page}` | Canonical-path order over `portable_entries`. A full scan per page, with no prefix seek (`read.rs:741-820`). | `CatalogQuery`: native |
| `Aggregate{selection, count_cap, max_work}` | O(1) exact only when unfiltered, and then it counts all entries including directories; otherwise a scan with cap and limit (`read.rs:822-865`) | catalog totals (the adapter can use root `RollUp` files instead) |
| `Report(ReportRequest)` | The one-shot report machinery. Rows carry **native paths only** (`fdu-v9uf`). `report_work` charges full passes (`read.rs:369-431`). | the fdu plan’s intended route for recent and navigation; unsuitable today (see §11) |
| `Continue{continuation, page}` | Resumes a tree or flat page (`read.rs:115-181`) | `after` |
| `Diagnostics` | root, scope, entry count, at most 64 issues, control observation (`read.rs:204-212`) | diagnostics and issues |

`EntrySelection` (`fdu:crates/fdu-core/src/query/query_selection.rs:415-444`; Python
`opened.py:549-605`) wraps `Selection`: include/exclude globs, `min_size`, `kinds`, a
time window with `time` basis (**default is change time since 0.6.0**), and `ignored`.
It adds `max_size` (inclusive), `exclude_ignored`, `logical_extensions`, `exact_names`,
`terminal_extensions` and `ancestor_names`. All predicates match the portable path.
**It has no kind, family or group predicate and no subtree prefix.** `depth`, `limit`,
`sort` and `reverse` are refused (`read.rs:484-494`).

### 1.4 Continuations and version pinning

- **Pins:** `expected` must equal the current version exactly, or the whole read raises
  `VersionUnavailable` (`read.rs:42-48`). There is no historical retention; the plan
  says so explicitly
  (`fdu:docs/project/specs/active/plan-2026-08-25-fdu-opened-root-inventory-engine.md:745-764`,
  “no historical index image is retained”).
- **Continuation table:** 128 records
  (`fdu:crates/fdu-core/src/opened/continuation.rs:9`), each at most 64 KiB
  (`engine_contract.rs:784`). IDs are single-use.
- **Limits and refusals:** a `Limit` or `Refused` result restores the record so the same
  continuation can be retried (`read.rs:166-180`). A record from an older version raises
  `ContinuationStale`, which Python maps to `ContinuationUnavailableError`
  (`read.rs:132-137`; `fdu:crates/fdu-py/src/opened_binding.rs:49-50`). A consumed or
  evicted ID returns `RefusedResult(CONTINUATION_UNAVAILABLE)`
  (`engine_contract.rs:1143-1151`).
- **vs Metabrowser:** opaque, one-shot, version-pinned and preserved by limits, as
  `docs/project/architecture/arch-inventory-provider.md:404-411` requires.
  Retention is the tip only.

### 1.5 Work limits, typed limits, refusals

- `LimitResult{projection: tree|flat|report|aggregate, max_work, rows_visited}`
  (`engine_contract.rs:1076-1098`) maps to `QueryLimitProjection`.
- **The tree budget is soft.** A page always emits at least one row and may overrun to
  the next position it can name (`read.rs:549-739`; plan `:819-866`; open beads
  `fdu-pokc` and `fdu-3v0d`). Flat and aggregate budgets are hard.
- `ProjectionRefusal`: `NotADirectory`, `ContinuationRecordLimit`,
  `ContinuationUnavailable` (`engine_contract.rs:1117-1152`). Metabrowser’s contract has
  **no refusal type** (`contract.py:1545-1556`). The adapter maps `NotADirectory` to an
  empty projection, which is what the Python reference does
  (`src/metabrowser/inventory_engine/providers/python_inventory.py:2379-2413`), and maps
  unavailable to `VersionUnavailableError`.

### 1.6 State vocabularies

| Concept | fdu (`engine_contract.rs`) | Metabrowser (`contract.py`) | Status |
| --- | --- | --- | --- |
| Phase | discovering, reconciling, ready, watching, stopped, failed (`:543-556`) | the same plus host-owned `opening` (`:610-617`) | native-ready |
| Coverage | complete / partial(building, budget, cancelled, inaccessible, failed) (`:560-580`) | the same (`:668-685`) | native-ready |
| Freshness | fresh, reconciling, stale, partial (`:527-536`) | the same (`:688-692`) | native-ready |
| Source | scanned, revalidated, journal_scoped, cached (`:392-415`); always `scanned` for an opened root (cold only) | the same (`:695-699`) | native-ready |
| Issues | permission, disappeared, invalid_metadata, resource_budget, observation_gap, provider_failure. At most 64 retained, message at most 512 B (`:583-604`). Only a summary is in the state; details need a `Diagnostics` projection, with native relative paths. | the same codes; at most 1,024 issues, detail at most 4,096 B (`:115-117,715-737`) | adapter-translatable |
| Progress | `files_retained`, `directories_complete` (`:741-749`) | `entries_observed`, `directories_observed`, `estimated_entries` (`:702-712`) | adapter-translatable via `Diagnostics.entries` or root `RollUp`; F23 or M8 |
| Observer failure | `Failed` + freshness `Partial` (`fdu:crates/fdu-core/src/index.rs:3257-3263`) | `ready` + `stale` + typed issue (`arch-inventory-provider.md:290-296`) | **conflict** (F5) |
| Budget stop | `Stopped` + partial(budget) + `ResourceBudget` issue; no observation; refresh refuses expansion (`opened.rs:392-404`) | the same (2B) | native-ready |

### 1.7 Changes and journal

- A poll returns `Changes{commits, impact}`, `Idle`, or
  `Reset{impact: all domains, all_dirty}` (`engine_contract.rs:1204-1236`;
  `fdu:crates/fdu-core/src/opened/journal.rs:68-182`).
- **A poll returns every retained commit after the cursor, cloned.** There is no
  per-poll bound (`journal.rs:111-118`), and the journal holds up to 8 MiB.
- `Impact{domains, dirty_paths (changed paths plus ancestors), all_dirty}`. The path set
  is capped at 256 per commit and 256 for a poll’s union
  (`engine_contract.rs:1696-1707`; `journal.rs:209-235`). Metabrowser’s batches carry up
  to 1,024 changed paths, without ancestors (`contract.py:98`;
  `python_inventory.py:4448-4452`).
- Impact domains: topology, metadata, classification, aggregates, content, state
  (`engine_contract.rs:1677-1690`).
- **Trust and state transitions are clocked commits:** freshness, verified, directory
  complete/incomplete, index state (`:1711-1743`). Metabrowser’s August “clocked trust
  state” requirement is met.
- Cursor errors: a foreign, future or mismatched cursor raises `ChangeCursorUnavailable`
  (`journal.rs:126-139`). fdu allows any number of pollers; the single-iterator rule
  stays in the adapter.

### 1.8 Refresh, prioritize, close

- **Refresh:** inputs are deduplicated and normalized.
  `accepted` lists every unique path; `rejected` gives a typed reason (outside_root,
  beyond_depth, not_admitted, unsafe_ancestry, resource_budget)
  (`fdu:crates/fdu-core/src/scan.rs:5862-5921`; `engine_contract.rs:1244-1305`). The
  receipt is the `(after, version]` interval plus impact, issues and work
  (`opened.rs:406-476`). A directory path re-walks its subtree.
- **vs Metabrowser:** full accounting and a terminal version are native-ready.
  The refresh reason and observation kind are dropped (harmless).
- **Prioritize:** at most 64 paths, no depth argument, and an error once stopped.
- **Close:** joins all workers, clears continuations, wakes pollers.

### 1.9 Concurrency, GIL, errors

- **Concurrency:** `OpenedIndex` is an `Arc` authority (`opened.rs:200-203`). Reads
  share a `std::sync::RwLock` (`index.rs:1486-1549`), so long reads delay discovery and
  observer commits.
- **GIL:** the Python handle is a `frozen` pyclass.
  Every native call runs under `py.detach` (`opened_binding.rs:1157-1290`). **Conversion
  holds the GIL:** Rust builds `PyDict` trees, then `opened.py` rebuilds dataclasses
  (`:979-997`), roughly 10 Python objects per row.
  Bead `fdu-1yxw` is open.
- **Errors:** `OpenedIndexError` (a `RuntimeError` subclass) has subclasses Closed,
  Stopped, VersionUnavailable, ContinuationUnavailable, ChangeCursorUnavailable and
  Limit (`opened.py:130-160`; mapping `:1402-1431`; `opened_binding.rs:34-78`). A panic
  surfaces as `pyo3_runtime.PanicException` (a `BaseException`) and poisons the root
  (`opened.py:1442-1448`).

| fdu error | Adapter maps it to |
| --- | --- |
| `OpenedIndexClosedError` | `InventoryClosedError` |
| `VersionUnavailableError`, `ContinuationUnavailableError`, `RefusedResult(CONTINUATION_UNAVAILABLE)` | `VersionUnavailableError` |
| `ChangeCursorUnavailableError` | provider failure / host reset |
| `OpenedIndexLimitError` | adapter bug (bounds) |
| `OpenedIndexStoppedError` on prioritize | ignore (inert) |

* * *

## 2. What changed since `0583a1a` (2026-08-27, a pre-release “0.1.0” development build)

These come from diffing `opened.py` at `0583a1a` against `main`, plus CHANGELOG
0.1.0–0.6.0.

- **`OpenedOptions`:**
  - `journal_capacity` (items) became `journal_capacity_bytes`, with a 64 KiB minimum.
    The 2A adapter’s `journal_capacity=config.change_queue_size`
    (`explorations/fdu-inventory-adapter/adapter.py:751-760`) now fails at open.
  - Added `type_rules`, `control_budget` and `control_line_limit`.
- **Identity:** `ScopeIdentity` became `EntryScope`, gaining `population` and
  `control_fingerprint`. `ScanScope` gained `population`. `ReadDiagnostics` gained
  `controls`.
- **Total portable paths:** `PortablePathEncoding`, `PortablePathExample` and
  `PortablePathIssue` were removed.
  `Entry.portable_path` is now always `str` (it was `str | None`).
  `TreePage.native_complete`, `portable_complete` and `portable_issue` collapsed into
  `complete`. `FlatPage.portable_issue` was removed.
- **Rows:** added `Entry.classification: NameClassification` (logical and canonical
  extension, kind, family and group IDs, content family).
- **Tree:** gained `depth` (int or `Bound.ALL`, default 1) and `include_ignored`.
  Breadth-first level order is now stated.
- **Selection:** `Flat` and `Aggregate` now take `EntrySelection` instead of
  `Selection`, and match portable paths.
- **Refusals:** added `RefusalReason` and `RefusedResult`. A consumed or evicted
  continuation no longer raises.
- **Change records:** added `EffectiveChangeKind.CONTROL_REFUSAL_UPDATED`, the
  `previous_refusal`/`current_refusal` fields,
  `InvalidateReason.CONTROL_POPULATION_CHANGED` and
  `StateTransitionKind.DIRECTORY_INCOMPLETE`.
- **0.6.0:** `RollUpSummary` added `newest_changed_ns` (constructor break).
  `Selection` time windows default to **change time**, so the adapter must pass
  `time=TimeBasis.MODIFIED`. `read()` raises `TypeError` for a non-projection.
  `OverflowError` and `RuntimeError` now map to fdu errors.
- **Rust:** `ReadProjection::Tree{depth, include_ignored}`, `ProjectionResult::Refused`,
  `OpenOptions.types` and `control_limits`, `MAX_CONTINUATION_RECORD_BYTES`, and the
  internal `ServingIndexes`.
- **Still absent** (same as `0583a1a`): a polling backend,
  recent/navigation/filtered-tree/rollup projections, and warm reopen.

* * *

## 3. Classification

- **Runtime registry:**
  - **Supported:** the File Rollup registry document, schemas **3 and 4 only**, via a
    dependency-free parser
    (`fdu:crates/fdu-core/src/classify/file_rollup_manifest.rs:1-31`), or the compact
    `[[kind]]` dialect (`fdu:crates/fdu-core/src/classify.rs:398-541`).
  - **Fails today on two counts:** Metabrowser’s schema 5 and the new family field
    `chroma_ratio` (`file_rollup_manifest.rs:146-171,198-201`).
  - **Behaviour:** it is fail-closed by design.
- **Fingerprinting:** `TypeRegistry::fingerprint()` is a length-prefixed FNV-1a hash
  over classification fields.
  Presentation fields and `schema_version` stay out (`file_rollup_manifest.rs:455-512`).
  The result is reported as `SemanticIdentity.type_rules_fingerprint` (u64), alongside
  `ignore_rules_fingerprint` and `reducers_fingerprint`. The adapter must combine the
  three into Metabrowser’s `semantic_fingerprint` string (adapter-translatable).
  - The wire `FileTypeRegistryIdentity.fingerprint`
    (`src/metabrowser/wire_models.py:280-285`) is Metabrowser’s own recipe.
    The host should own it (M4).
- **Logical extension:** `classify::logical_ext` keeps up to 2 trailing components, each
  ASCII alphanumeric and at most 12 bytes, with a leading dot belonging to the basename
  (`classify.rs:898-919,1104-1146`). So `release.v2.zip` → `.v2.zip` and
  `bundle.umd.min.js` → `.min.js`, matching Metabrowser’s `derive_ext`
  (`src/metabrowser/fs_paths.py:70-99`).
  - One edge case diverges on Metabrowser’s side: `part.lower()` lowercases Unicode
    before the ASCII check, so a Kelvin sign `K` (U+212A) becomes `.k` in Metabrowser
    and gets no extension in fdu (M1).
- **Three extension levels:** raw, logical and canonical (`classify.rs:9-38`). **fdu’s
  maintained per-directory `by_ext` tallies use the raw level** (`index.rs:196,249`),
  which is the wrong level for Metabrowser’s navigation and rollup tallies (`.zip` vs
  `.v2.zip`).
- **Conformance corpus:** fdu does **not** run Metabrowser’s corpus
  (`src/metabrowser/data/file-rollup-format/file-rollup-conformance.json`: 153 metadata,
  21 invalid-registry and 2 aggregate cases).
  Bead `fdu-ekga` (P2) is open.
  - `NameClassification` (`classify.rs:307-347`) also lacks the detection source and
    confidence that the metadata cases assert.

## 4. Scope semantics

- **Populations:** the fixed partitions `all` and `unignored` are always observed by an
  opened root (`opened.rs:184-186`; `OpenedIndex::basis` `:234-240`).
  `include_ignored=false` on a tree prunes the subtree.
- **`.gitignore` engine:** an in-tree matcher with no regex or glob crate
  (`fdu:crates/fdu-core/src/control/gitignore.rs:1-27`). It handles nested files with
  deeper precedence, negation, anchors, `**`, and bracket classes pinned to
  `git check-ignore`. Matching is case-sensitive.
  - **Not read:** `.git/info/exclude`, `core.excludesFile`, global excludes, and
    **`.gitignore` files above the opened root**. A nested repository is not a boundary
    (`control.rs:9-19`; `fdu:docs/usage.md:676`).
  - Files inside ignored directories are read and charged against the budget.
    Refused files degrade gracefully (`ReadDiagnostics.controls`), and no issue is
    raised.
  - **Divergence:** Metabrowser’s walker applies rules from the enclosing git root down,
    including above the served root (`src/metabrowser/walker.py:93-110` →
    `src/metabrowser/tree.py`, `build_gitignore_check`/`_find_git_root`). This diverges
    whenever Metabrowser serves a subdirectory of a repository (F19 / M9).
- **Hidden:** pruned (not tagged) with an exact-name allowlist (`admission.rs:19-52`).
  Every producer applies admission before observing; the `.gitignore` control is still
  read without becoming a row (`admission.rs:1-6`).
- **Symlinks:** listed leaves, never followed, contributing nothing to totals
  (`index.rs:3273-3283`).
- **Special objects:** `EntryKind::Other`, excluded by `exclude_special`.
- **Hard links:** counted once per path.
  0.6.0 notes that change time on other links of the same file goes stale under
  observation (`opened.py:295-298`).
- **Mounts:** `one_filesystem` is supported.
  Linux automount handling was fixed in 0.6.0 (CHANGELOG `:286-301`).

## 5. Directory facts

- **`RollUpSummary`** (`index.rs:210-233`; Python `opened.py:431-447`): files, dirs,
  bytes (apparent), allocated, `newest_mtime_ns` and `newest_changed_ns` (regular files
  only), for both `all` and `unignored`. These map directly to `total_files`,
  `total_size`, `unignored_files`, `unignored_size` and `newest_mtime_ns`.
- **Not exposed:** raw-level `by_ext` tallies; per-directory newest *activity* across
  all kinds (`index.rs:260-279`); the `ServingIndexes` semantic and exact-name tallies.
- **Missing:**
  - A **non-directory leaf count**, so `InventoryEntry.empty` (`contract.py:846`;
    Python’s `_descendant_leaf_counts`, `python_inventory.py:4018`) cannot be derived
    (F4).
  - **Subtree completeness.** `children_complete` covers direct children only (F20).
- **Provenance:** subtree composition exists for the detached index
  (`engine_contract.rs:502-517`). It is moot for opened roots, which are cold-only with
  `source=scanned`.
- **Trust transitions do advance the change clock** (§1.7).

## 6. Watch

- **Backends:** `notify` 8.2 `RecommendedWatcher` with `RecursiveMode::Recursive` on the
  root (`fdu:crates/fdu-core/src/watch.rs:46,251-265`). That is inotify on Linux (no
  fanotify), FSEvents on macOS, ReadDirectoryChangesW on Windows and kqueue on BSD.
  **There is no polling fallback** (CHANGELOG 0.1.0 Known limitations; `fdu-lka2` open).
- **Events are hints:** each named path is verified by stat; rescan or overflow becomes
  `InvalidateSubtree` and then reconciliation (`watch.rs:1-35`). The raw queue holds
  4,096 events and collapses to a root invalidation when it overflows
  (`watch.rs:91-103,748-757`).
  - **Risk:** notify’s inotify mask includes `IN_OPEN`. Fdu filters Access events only
    after they enter that queue (`watch.rs:923`), so heavy file reads consume queue
    capacity.
- **Linux setup cost and failure:** `Watcher::new` runs synchronously inside `open()`
  (`opened.rs:711-713,754`). notify then walks the entire tree with WalkDir to add one
  inotify watch per directory, including pruned hidden and ignored directories (notify
  `inotify.rs:400-415`). `ENOSPC` (`MaxFilesWatch`) **fails open entirely**; there is no
  degrade to `ready`.
- **Handoff:** the observer is captured before discovery.
  After discovery, fdu reconciles the buffered intents and then runs a **final
  whole-root reconcile pass** (`opened.rs:1591-1599`) before entering `watching`. The
  serial re-verification cost is the same shape as `fdu-eru0` (37 s after a 7 s cold
  scan on a 476k-entry tree; that measurement came from the CLI watch route).
- **macOS:** FSEvents misses writes from processes holding a file open until the last
  close (`fdu-vhrb`, P1; CHANGELOG 0.2.0 `:609-615`).
- **Scoped reconciliation:** each rename side is verified as its own path (0.2.0).
  Overflow reconciles the named subtree, or the root.

## 7. Persistence

None on the opened route.
It is cold-only: the plan refuses any cache and `plan.load() == None`
(`execution.rs:478-487,1990-1993`; plan `:974-989`). Snapshots exist for one-shot and
retained-index routes (`fdu:crates/fdu-core/src/snapshot.rs`, format 7), keyed by engine
and scope fingerprints.
Warm opened serving is epic `fdu-wpa0` (P2, open).
Metabrowser’s Python provider is also cold-only, so this is parity, not a regression.

## 8. Telemetry

- **`Work` matches `WorkCounters` field for field, in the same order**
  (`engine_contract.rs:1758-1787` vs `contract.py:758-778`):
  - reads fill rows_visited, rows_returned and maintained_index_work;
  - polls fill commits_visited and commits_returned (`journal.rs:155-160`);
  - refresh fills observations, unchanged, stale, resource_refused and the
    directories/entries/files/bytes counters (`opened.rs:455-465`).
- **Charging rules differ, though:** a tree charges the path walk (components + 1), and
  its budget is soft. Metabrowser’s conformance test asserts an exact `rows_visited == 4`
  (`tests/test_inventory_provider_contract.py:1622-1640`). Decision M6 is needed.
- **`BoundaryMetrics`:** fdu supplies none, so the adapter measures wall and CPU time.
  `lock_wait_ns` is unavailable and should become optional (M3).
- **Process counters:** `FDU_COUNTERS` (`fdu:crates/fdu-core/src/counters.rs`) is
  process-global instrumentation and is not part of the opened API.

## 9. Packaging

- **PyPI:** `fdu` releases 0.1.0 (2026-09-26) through **0.6.0 (2026-11-12)**. Files:
  `cp312-abi3` manylinux2014 x86_64 and aarch64, `macosx_11_0` arm64 and x86_64,
  `win_amd64`, and an sdist.
  `requires_dist` is empty.
- **Build:** `requires-python >=3.12` (`fdu:crates/fdu-py/pyproject.toml:7`),
  `abi3-py312` (`fdu:crates/fdu-py/Cargo.toml:34`), maturin 1.14.1. The release matrix
  is at `fdu:.github/workflows/release.yml:236-262`, with trusted publishing at
  `:381-545`.
- **Caveats:**
  - Linux aarch64 wheels are cross-built and inspected, never executed.
  - There are no musl or Windows arm64 wheels, and free-threaded CPython is unsupported.
  - Source builds need Rust 1.85 or newer (MSRV in `fdu:Cargo.toml:7`; the dev toolchain
    is 1.97.1).
  - The wheel installs an `fdu` console script (`pyproject.toml:31-32`).
- **How Metabrowser pins it:** an optional extra such as `fdu = ["fdu==0.X.Y"]` with an
  exact pin. Metabrowser’s Python range (`>=3.12,<4.0`) is compatible.
  fdu is first-party, so it needs a row in `SUPPLY-CHAIN-SECURITY.md:52-59` and an
  `exclude-newer-package` entry in `uv.toml` (0.6.0 is 5 days old).
  - The opened types are explicitly unstable across 0.x minor releases (CHANGELOG
    `:1421-1429,1495-1498`; 0.6.0 broke the `RollUpSummary` constructor).
    Pin exactly.

## 10. Performance record

| Measurement | Result | Source |
| --- | --- | --- |
| Linux one-shot default tree, 1M-entry generated tree | 0.951 s, 920k files/s, 3.1 GB/s, 57 MiB peak (folded tree, not a retained index) | `fdu:docs/performance-measurements.md:41-47,105-127` (exp-202, 0.3.0) |
| Linux physical floor (4 workers) | index tier 1.35–1.40× the parallel-stat floor; tree tier 1.21–1.26× | `fdu:docs/project/reports/scoreboard-2026-10-10-linux-tree-floor.md` |
| Retained full index memory | about 285 MiB on 1,000,001 entries; growth 190–520 B per entry | CHANGELOG 0.1.0 Known limitations; bead `fdu-6o5o` notes |
| macOS one-shot (pre-0.2.0) | 6.4 s on 1M entries, 137k files/s. **No macOS run on the current engine.** | `performance-measurements.md:197-218` |
| **macOS opened discovery** (146k-entry Metabrowser clone, M1 Pro, uncontrolled) | wall 3.77 s / component 2.76 s / **212 MiB**, vs cold index scan 0.58 s / 0.31 s / 39 MiB: **6.5× wall, 8.8× component, 5.5× RSS**. Uses read_dir + fstatat instead of getattrlistbulk. One commit per directory (11,524), 241k dirty paths, 1.12M rollup merges. | `fdu:docs/project/experiments/exp-126-first-pass-walk-versus-opened-discovery-i-o-on-metabrowser.md:330-412` |
| **Linux opened discovery** (linux-v6.12, 92k entries) | component 1.18 s vs scan-index 0.43 s (**2.75×**), wall 1.50 s, 107 MiB. Measured before 0.3.0’s getdents64 reader, which opened discovery now uses (`scan.rs` `list_directory`); not re-measured since. | `exp-145-linux-opened-discovery-leftover-is-still-journal-clones-plus.md:198-246` |
| Second report over an opened root (macOS, 77k entries) | 0.13–0.15 ms | exp-211 |
| Commit-cost probe (10,101-entry batch) | detached 51.2 ms vs opened 62.8 ms (1.225×) | plan `:1626-1634` |
| Memory vs dust (macOS home trees, single runs) | fdu at 1.5–1.6× dust’s peak | bead `fdu-syyl` |
| For comparison: Metabrowser Python provider (M1 Pro) | 100k files: 5.5 s / 174 MiB; 300k files: 19.3 s / 331 MiB | `docs/scale-benchmark.md:58-63` |

Read together, these are not paired and not claim-grade.
They suggest that fdu’s opened discovery on macOS is only about **2× faster than the
Python provider, at similar memory per entry**. fdu’s 10× headline belongs to the
one-shot walker, not the opened route.
The performance index assigns the opened root 5% weight
(`plan-2026-10-05-fdu-performance-index.md:171`); Linux cells are `fdu-iwmq`. Python
conversion cost is unmeasured (`fdu-1yxw`).

* * *

## 11. Gap matrix

The status column uses the four categories you asked for; “conflict” means native
behaviour exists but disagrees with Metabrowser’s contract.

| # | Metabrowser item | fdu today | Status | Fix |
| --- | --- | --- | --- | --- |
| 1 | `registry_document` | `type_rules`, schemas 3/4 | **missing** | F1 |
| 2 | budget, hidden, symlink, filesystem, object kinds | options in §1.2 | native-ready | — |
| 3 | scope fingerprint | adapter calls Metabrowser’s `inventory_scope_fingerprint` | adapter-translatable | — |
| 4 | semantic fingerprint | `SemanticIdentity` (3×u64) combined by the adapter | adapter-translatable | — |
| 5 | `change_queue_size` (items) | bytes, minimum 64 KiB | adapter-translatable / Metabrowser should change | M2 |
| 6 | `watch_mode` | native or off; setup failure fails open | auto: missing degrade; poll: **missing** | F5a, F18 |
| 7 | ignore rules above the served root | not read | **missing**, or Metabrowser should change | F19 / M9 |
| 8 | lifecycle, coverage, freshness, source | 1:1 (§1.6) | native-ready | — |
| 9 | observer-failure state | `Failed`/`Partial` | conflict | F5b |
| 10 | `IndexProgress` | files_retained, directories_complete | adapter-translatable | F23 / M8 |
| 11 | issues in state | summary only; details via `Diagnostics`; native paths | adapter-translatable | — |
| 12 | refused `.gitignore` → issue | `ReadDiagnostics.controls` only | Metabrowser should change | M7 |
| 13 | empty checkpoint read | `state()` | native-ready | — |
| 14 | 1,024 queries per read | 16 projections | **missing** | F3 |
| 15 | `EntryQuery` | `Lookup` | native-ready except `empty` | F4 |
| 16 | canonical path encoding | no `%5C` escape for backslash | **missing** | F2 |
| 17 | `DirectoryQuery` order and pruning | `Tree` | native-ready | — |
| 17a | `DirectoryQuery` `max_rows` up to 500k | pages of at most 4,096 rows | adapter-translatable by looping (fragile under churn) | M5 / F21 |
| 17b | hard work limit on pages | soft tree budget | conflict | M6 / `fdu-pokc` |
| 18 | `FilteredTreeQuery` | none | **missing** | F13 + F8 |
| 19 | `GroupedTreeQuery` (≤8 groups, one pass) | none | **missing** | F13 |
| 20 | `RollupQuery` (File Rollup payload: node tree, dominant extension, breakdown) | `RollUp` scalars only; raw-level tallies | **missing** | F10, F12 |
| 21 | `NavigationQuery` (logical, canonical, family, preset, recency tallies) | none; serving tallies unexposed and keyed by kind | **missing** | F10, F11 |
| 22 | `RecentQuery` (ignored last, mtime, prefix, count cap) | `Report` recent sorts everything, no demotion, native paths | **missing** | F9, F8 |
| 23 | `CatalogQuery` predicates and order | `Flat` + `EntrySelection` | native-ready | F14 (lean rows) |
| 23a | catalog totals | root `RollUp` (unfiltered) or `Aggregate` | adapter-translatable | — |
| 24 | `DiagnosticsQuery` | `Diagnostics` + root `RollUp` + adapter counters | adapter-translatable | — |
| 25 | `QueryLimitProjection`, `CountResult` | `LimitResult`, `CountResult` | native-ready (tree excepted, see 17b) | — |
| 26 | version pins and continuations | exact and one-shot; tip-only retention | native-ready; churn risk | F21 (defer) |
| 27 | `valid_until_ns` | none | adapter-translatable from `as_of` and windows | — |
| 28 | change stream, reset, state-only batches, monotonic versions | journal | native-ready | — |
| 29 | `dirty_paths` (changed, ≤1,024) and `non_file_paths` | impact paths include ancestors, capped at 256; full commits | adapter-translatable from commits (costly) | F7 |
| 30 | `dirty_queries` | from impact domains | adapter-translatable | — |
| 31 | refresh accounting and terminal version | `RefreshResult` | native-ready | — |
| 32 | prioritize (1,024 paths, depth, inert when stopped) | 64 paths, raises when stopped | adapter-translatable (truncate and swallow) | F6 |
| 33 | close and join semantics | yes | native-ready | — |
| 34 | `WorkCounters` | identical names; charging differs | native-ready / M6 | — |
| 35 | `BoundaryMetrics.lock_wait_ns` | not available | Metabrowser should change | M3 |
| 36 | scripted observation and discovery barrier for goldens | test-only (`opened.rs:112-115`) | **missing** | F17 |
| 37 | File Rollup conformance | not run in fdu | **missing** | F22 (`fdu-ekga`) |
| 38 | time to `watching`, discovery speed and memory | §6, §10 | risk | F15, F16 |
| 39 | Python row conversion cost | dicts, then dataclasses | risk | F14 |

### Proposed fdu changes

All are named generically; none carries Metabrowser vocabulary into fdu.
Sizes: S is a small PR, M is several days, L is a week or more.

- **F1 (S) Read File Rollup registry schema 5.**
  - Where: add 5 to `SCHEMA_VERSIONS` (`file_rollup_manifest.rs:31`); accept
    `chroma_ratio` in the family block (`:146-171`) as a shape-checked presentation
    field outside the fingerprint (`:455-512`).
  - Also: expose detection source and confidence on `NameClassification`
    (`classify.rs:307-347`; Python `opened.py:450-471`) for the metadata cases.
  - Justification: Metabrowser registry `:28,95`, commit `210827b5`. Otherwise
    `type_rules` raises at open.
  - Process note: schema bumps currently force releases of both repositories in
    lockstep; make that a named co-release rule.
- **F2 (S) Escape POSIX `\` as `%5C` in portable paths.**
  - Where: `push_text` (`read.rs:1104-1117`). This changes the ordering keys for
    `portable_entries` and child maps, and the goldens.
  - Generic rationale: a Windows-portable grammar.
  - Justification: `contract.py:51-56,263-267`; Metabrowser CHANGELOG `:2544-2553`. The
    alternative is that Metabrowser reverts.
- **F3 (S) Batched lookups.**
  - API: `ReadProjection::Lookups{paths: Vec<PathBuf>}` with at most `MAX_PAGE_ROWS`
    paths, returning `Vec<Knowledge<EntryValue>>`. Alternatively, count O(1) projections
    separately against `MAX_READ_PROJECTIONS`.
  - Where: `engine_contract.rs:941-999`, `read.rs:55-71`, binding `parse_projections`,
    `opened.py`.
  - Justification: `src/metabrowser/events_route.py:443-447` rereads up to 1,024 paths
    in one read, and the pending tallies at `:1050-1063` use 1 + 2N queries.
    With 16 projections per read, a batch splits into 64 or more pinned reads that fail
    together under churn.
- **F4 (S) Non-directory leaf count.**
  - API: `RollUpSummary.leaves` (files + symlinks + other), maintained in
    `InternedRollUp` (`index.rs:242-250`) and in `subtree_scalars` (`:3273-3283`).
  - Justification: `InventoryEntry.empty`; the August research row “Empty directories”.
- **F5 (S) Observation degrades instead of failing.**
  - (a) A `Watcher::new` error at open (`opened.rs:711-713,754`) should yield `Ready`
    plus an issue, not an open failure.
  - (b) Observer failure after discovery should report `Ready` + `Stale` + issue
    (`index.rs:3257-3263`), keeping `Failed` for discovery or provider failure.
  - Justification: `arch-inventory-provider.md:290-296`. This is a joint decision.
- **F6 (S) Prioritize.** Raise `MAX_PRIORITY_PATHS` to 1,024 (`opened.rs:37`), accept an
  optional depth hint, and make it a no-op once stopped (`:325-327`).
- **F7 (S) Change-poll detail and bounds.**
  - API: `ChangeRequest{after, timeout, detail: Commits | ImpactOnly, max_commits}`,
    plus `Impact.changed_paths` (exact effective paths without ancestors) with its own
    bound, and kind transitions (file to non-file).
  - Where: `engine_contract.rs:1195-1236,1696-1707`; `journal.rs:209-235`; binding
    `change_poll_dict`.
  - Justification: Metabrowser’s dirty-path granularity and 1,024 bound; exp-126 counted
    11,524 commits and 241k dirty paths in one discovery.
    Today an 8 MiB journal can be cloned and converted under the GIL on each poll.
- **F8 (S) Selection predicates.**
  - API: on `EntrySelection`, add `kind_ids`, `family_ids`, `group_ids` and
    `unclassified` (matched through `NameClassification`); add
    `under: Option<portable prefix>` with a range seek in `flat_projection`
    (`read.rs:741-779`); accept nanosecond integers for the Python
    `Selection.since`/`before` (today they take `datetime`, which truncates to
    microseconds).
  - Where: `query_selection.rs:415-444`, `portable_candidate` (`read.rs:496-516`).
  - Justification: `InventoryFilter.type_families`/`type_group` (`contract.py:983-992`)
    and `RecentQuery.prefix` (`:1178`).
- **F9 (M) Ranked-recency page.**
  - API: `ReadProjection::Recent{selection, demote_ignored, limit, count_cap, max_work}`
    returning `{rows, total: CountResult}`.
  - Where: read `ServingIndexes.recent_files` (`index.rs:837,855-875`, keyed by mtime)
    in two passes (unignored, then ignored) under `max_work`; return rows ordered by
    mtime descending, then portable path ascending.
  - Justification: `contract.py:29-46`, the plan’s row-order section, and 2A item 3. It
    replaces the `Report`-based plan, which sorts everything
    (`fdu:crates/fdu-core/src/query/query_report.rs:4016-4110`) and is charged a full
    pass (`read.rs:369-431`).
- **F10 (M) Classification tallies.**
  - Where: re-key the serving per-directory tally from kind to “exact-name ID, else
    logical extension” (`index.rs:4315-4356`). Then kind, family, group and canonical
    extension all derive from the registry at read time, bounded by the number of
    distinct keys.
  - API:
    `ReadProjection::Tally{path, dimension: LogicalExt|CanonicalExt|Kind|Family|Group|ExactName, top, max_work}`
    returning rows for `all` and `unignored`.
  - Justification: `NavigationTallies` and rollup `ext_tallies`/`dominant_ext`
    (`wire_models.py:228-267,367-373`; Python `python_inventory.py:3230-3320`); 2A items
    2 and 4. The existing raw-level `by_ext` gives the wrong buckets.
- **F11 (M) Exact recency-window counts.**
  - API: `ReadProjection::TimeCounts{cutoffs, basis: Modified, partitions}`, plus oldest
    and newest times.
  - Where: an order-statistic structure in `ServingIndexes`. Counting a `BTreeSet` range
    is O(window).
  - Justification: `NavigationQuery.recency_windows` (`contract.py:1150-1168`).
- **F12 (M) Ranked children tree.**
  - API: `ReadProjection::Children{path, depth, rank: Bytes|Files|Dual, top, max_nodes}`
    returning directory nodes with summaries plus “rest” aggregates.
  - Effect: with F10 tallies, the adapter can assemble the File Rollup payload with no
    entry loop. Extensionless-basename top-N needs a bounded subtree pass that returns a
    typed limit.
  - Justification: `RollupQuery` (`contract.py:1126-1146`);
    `RollupDirNode`/`RollupRest`.
- **F13 (L) Selected (filtered) tree, including groups.**
  - API:
    `ReadProjection::SelectedTree{path, depth, include_ignored, selection, groups: Vec<EntrySelection> (≤8), page}`
    returning one level-order page per group, with selected totals on directory rows and
    matching_leaves/files/bytes.
  - Where: reuse the tree traversal (`read.rs:549-739`) and the subtree measurement in
    `query_subtrees.rs`.
  - Joint decision: complete-or-limit (fdu plan `:1667-1675`) or paged (Metabrowser
    `contract.py:1014-1123`).
  - Justification: Group by measurements (`contract.py:103-110`); 2A item 4.
- **F14 (M) Leaner rows and cheaper conversion.**
  - API: `RowShape::Identity` (portable path, kind, size, mtime, logical extension,
    ignored), with tuple or pyclass rows that skip the intermediate dicts; columnar
    export optional.
  - Where: `engine_contract.rs:1033-1039`; `opened_binding.rs:1078`; `opened.py:979`.
  - Justification: catalog pages of 500k rows (`events_route.py:1060`,
    `src/metabrowser/active_tracker.py:89`); the 2A measurement of 412,836 path bytes
    and 13 MB for one read; boundary review A1; beads `fdu-1yxw`, `fdu-g20s`.
- **F15 (M) Time to `watching`.**
  - (a) Scope the final handoff pass (`opened.rs:1591-1599`): skip it for FSEvents’ root
    stream, and on inotify re-verify only directories whose time moved.
  - (b) On Linux, register non-recursive inotify watches from discovery, only for
    admitted directories, instead of notify’s recursive WalkDir inside `open()`
    (`watch.rs:265`). Drop `IN_OPEN` interest (`:99,923`).
  - Justification: “Opening does not wait for a cold scan”
    (`arch-inventory-provider.md:38-40`); bead `fdu-eru0`.
- **F16 (M) macOS opened discovery on getattrlistbulk.**
  - Where: the existing `scan/macos_bulk.rs` in `list_directory` (`scan.rs` around
    `:1671-1710`). Consider more than one producer; the single-producer constraint is at
    `opened.rs:174-180`.
  - Justification: exp-126.
- **F17 (M) Public deterministic test seams.** A build feature exposing the scripted
  observation source (`opened.rs:112-115`) and a discovery gate through `fdu-py`.
  Justification: the 2A README’s golden-session direction and the discovery-barrier
  route test.
- **F18 (M) Polling backend.** `WatchConfig.backend: Native|Poll{interval}` using
  notify’s `PollWatcher`; or Metabrowser rejects `poll` for fdu.
  Bead `fdu-lka2`.
- **F19 (M, optional) Ancestor ignore rules.**
  `OpenOptions.control_base: Option<PathBuf>`, reading `.gitignore` files from the base
  down to the root. Justification: Metabrowser’s git-root rules.
- **F20 (S) Subtree completeness on directory rows.** A maintained count of incomplete
  descendant directories.
  Justification: rollup node `state: pending`
  (`src/metabrowser/inventory_rollup.py:291`).
- **F21 (L, defer) Retained versions for continuations.** Only if churn measurement
  shows assembly restarts dominate.
- **F22 (S) Vendor and run the File Rollup conformance packet** (`fdu-ekga`).
- **F23 (S, optional) `DiscoveryProgress.entries_retained`.**

### Changes Metabrowser should make instead

- **M1:** ASCII-fold in `derive_ext` (`fs_paths.py:92`).
- **M2:** state `change_queue_size` as a provider byte budget, or let the provider
  choose it.
- **M3:** make `lock_wait_ns` optional.
- **M4:** the host owns the wire registry identity.
- **M5:** catalog and pending pages of at most 4,096 rows, or tolerate multi-read pages.
- **M6:** decide hard vs soft tree budget, and stop asserting exact cross-provider
  `rows_visited`.
- **M7:** add a vocabulary for “ignore classification incomplete” (refused controls), or
  pass `control_budget=Bound.ALL` for parity.
- **M8:** align `IndexProgress` with fdu’s committed counters.
- **M9:** decide the ignore-rule scope above the served root.

## 12. fdu beads and plans relevant to embedding

- **Phase 3C epic `fdu-hgnj` (P1).** Child `fdu-a0cf` (P1) has a corrected scope saying
  **“no new projection variant”**: recent and navigation are to come from `Report` sped
  up by maintained indexes.
  I recommend revisiting this.
  `Report` rows are native-path only (`fdu-v9uf`), its recent view does no demotion and
  sorts lossy names, it has no continuations, and its extension view uses the raw level.
  Generic projections (F9–F13) keep the application-independence rule.
- **Adapter work:** `fdu-2xfp`, `fdu-jy8p`, `fdu-o5ne`, `fdu-9dg9`, `fdu-zop7`;
  conformance `fdu-xu27`, `fdu-ekga`, `fdu-e76r`; composed proof `fdu-bldb`, `fdu-lr6r`,
  `fdu-cuwr`, `fdu-4w03` (all P2–P3, open).
- **Bounds:** `fdu-pokc` (strict tree level-advance) and `fdu-3v0d` (Metabrowser
  assembly work budget).
- **Memory and timing:** `fdu-6o5o`, `fdu-syyl`, `fdu-pro1`/`fdu-lj4h`, and `fdu-hb2t`
  (opened allocation slope; it should also price `ServingIndexes`).
- **Watch:** `fdu-vhrb` (P1, FSEvents misses open writers), `fdu-lka2`, `fdu-eru0`,
  `fdu-ek21` (Windows overflow not signalled).
- **Warm opened serving:** `fdu-wpa0`.
- **Later plans:** the performance index (`plan-2026-10-05`) and explicit core models
  (`plan-2026-09-17`, session rules `fdu-fjh1` P0) do not change the opened-root
  picture. The 0.6.0 recent-growth plan changed the default clock to change time, which
  matters for windows.

## 13. Doc and code disagreements

1. The plan’s status line says “3C idle since 08-28”, while its table says “3C in
   progress” and calls the serving-index set complete.
   Those indexes are maintained but never read in production (`index.rs:4315-4390` vs
   `:7563+`).
2. The plan says “the recent projection pays through the maintained timestamp-ordered
   set” (`:900-905`). No projection reads that set; the `Report` recent view sorts every
   row.
3. The plan’s “Required MetaBrowser changes” asks Metabrowser to **delete** ignored-last
   ranking (`:1046-1050`). The plan’s own row-order section (`:868-887`) and
   `contract.py:29-46` require it.
   The bullet is stale.
4. The plan asks Metabrowser to add per-projection refusals (`:1060-1066`); Metabrowser
   has none (`contract.py:1545-1556`).
5. The plan says filtered-tree paging “must be removed” (`:1667-1675`); Metabrowser
   keeps it.
6. The plan’s Decision Summary still says tree pages are “parent-first” (`:81`), the
   term its row-order section calls ambiguous.
7. The plan says “a backend can provide native events, polling hints” (`:630`); no
   polling backend exists.
8. `OpenedIndex.open` “returns while discovery continues” (CHANGELOG `:1333-1334`). On
   Linux with `observe=True` it first runs notify’s recursive WalkDir (`watch.rs:265`).
9. Metabrowser says canonical escaping “mirrors fdu” (`contract.py:269`). fdu does not
   escape a backslash.
10. The `type_rules` docstring calls the input “what MetaBrowser calls the registry”
    (`opened.py:310-312`), yet fdu refuses that registry today.
    Metabrowser vocabulary also appears in fdu’s public docs (`opened.py:560-561`;
    `control/gitignore.rs:3-4`).
11. `watch.rs:24-26` describes Metabrowser as running watchfiles, which is stale.

## 14. Top risks and surprises

1. **Two hard open-time blockers** (F1, F2) that the 2A spike never hit, because they
   arrived later on Metabrowser’s side.
2. **Maintained but unused serving indexes.** Every commit pays for recency, semantic
   and exact-name indexes.
   The portable path string is stored about 3 times per file (`portable_entries`,
   `RecentKey`, child maps) and each file walks its ancestors twice.
   None of this is read in production, and the memory cost is unmeasured.
3. **The opened route is much slower than fdu’s headlines,** especially on macOS (6.5×
   wall, 5.5× memory vs one-shot).
   It is single-producer, uses a slower macOS reader, makes one journal clone per
   directory commit, adds a Linux inotify registration walk, and ends with a full
   re-verification walk.
   On this evidence fdu may beat the Python provider by only about 2× on macOS time to
   first useful state.
4. **Tip-only versions plus small bounds (16 projections, 4,096 rows) plus Metabrowser’s
   large bundles and pages** mean frequent `VersionUnavailable` restarts on busy trees,
   which is when change batches arrive.
5. **The soft tree budget conflicts with Metabrowser’s hard-limit conformance test.**
   Exact work counts will not match across providers.
6. **GIL-held conversion** of about 10 Python objects per row, plus whole-journal commit
   conversion per poll, will compete with the asyncio loop.
7. **Linux watch fragility:** `ENOSPC` fails open; watches cover pruned and ignored
   trees; `IN_OPEN` traffic shares the 4,096-event queue, and overflow means a root
   reconcile.
8. **macOS FSEvents misses open-writer appends** (`fdu-vhrb`), so freshness claims on
   macOS need care.
9. **Ignore semantics differ** when serving a repository subdirectory (ancestor rules),
   and fdu’s `.gitignore` budget can refuse rules that the Python provider applies.
10. **The fdu plan’s “map onto Report” strategy for recent and navigation is unworkable
    as written.** This needs the lead’s decision.

## 15. Recommended fdu change list, in dependency order

0. **Joint decisions, no code:** tree budget (M6 / `fdu-pokc`); filtered-tree paging vs
   complete-or-limit; observer-failure state (F5b); refusal mapping; ancestor ignore
   scope (M9); page and bundle sizes (M5); correct the stale plan bullets in §13.
1. **Open and identity unblockers (S):** F1 schema 5 (plus detection source and
   confidence), F2 backslash escape, F5 degrade instead of failing open, F6 prioritize.
2. **Read-shape fixes (S):** F3 batched lookups, F4 leaf count, F20 subtree
   completeness, F23 optional.
3. **Change delivery (S):** F7 impact-only polls, changed paths, poll bound.
4. **Predicates (S):** F8 kind/family/group, prefix seek, nanosecond windows.
5. **Recent (M):** F9 over `recent_files`. This also stops paying for an unused index.
6. **Classification tallies and navigation (M):** F10 re-keyed tallies with the `Tally`
   projection, then F11 time counts.
   This retires the kind-keyed tally.
7. **Rollup (M):** F12 ranked children; the adapter assembles the File Rollup payload
   from F10 tallies.
8. **Filtered and grouped tree (L):** F13.
9. **In parallel from step 1:**
   - F22 conformance packet;
   - F14 lean rows and conversion, measured first under `fdu-1yxw`;
   - `fdu-hb2t` memory pricing of the serving indexes.
10. **Performance before the 2D gate (M):** F15 handoff and inotify registration; F16
    macOS getattrlistbulk and possibly parallel discovery.
    Re-run exp-126/145-style opened-discovery cells on 0.6.0 or later, plus
    Metabrowser’s `make benchmark BENCHMARK_PROVIDER=fdu`.
11. **Test seams for the 2D golden session (M):** F17.
12. **Optional, by decision:** F18 polling backend, F19 ancestor rules.
13. **Deferred until churn data demands it:** F21 version retention; warm reopen
    (`fdu-wpa0`).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
