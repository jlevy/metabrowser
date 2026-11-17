# fdu Provider Spike Against the Current Contract

**Status:** Measured on Linux (2026-11-17) and revised after an independent review; see
[Corrections After Review](#corrections-after-review).
macOS validation is pending; its commands and empty result slots are in
[macOS Validation](#macos-validation).

This experiment asks whether fdu 0.6.0 (`4450be7`) can back Metabrowser’s complete
inventory-provider contract as it stands after Checkpoint 2B, and what Python versus fdu
costs through the real server path.
It is the successor to the [Checkpoint 2A spike](../fdu-inventory-adapter/README.md),
which measured fdu `0583a1a` against the contract before 2B and is a frozen record.

The adapter here is spike code, not the production provider.
It answers every contract item fdu has a native projection for with native reads at one
pinned version, and answers the rest with the Python reference oracle over a temporary
flat image, counting every such fallback under the fdu addition that would remove it.
It never walks the filesystem in Python, shells out to the fdu command, keeps an image
across native versions, or fabricates a value; a semantic fdu cannot express is a typed
`InventoryContractError`.

## Answer

fdu can back the contract’s lifecycle, identity, coherent reads, version pins, paging,
change delivery, refresh, and close today.
Seventeen of the 22 provider-parametrized conformance cases pass unchanged against the
installed wheel, an eighteenth passes once its hardcoded provider name is masked, and
the remaining four are fdu’s soft tree work budget (two cases) and two tests that assume
Python’s behavior (which files a budget admits, and replay capacity as a maximum).
fdu cannot yet answer five of the nine query kinds natively (filtered tree, grouped
tree, rollup, navigation, recent).
Its Python binding costs about 9 to 14 µs per returned row, most of it rebuilding wire
dictionaries as dataclasses, so even its natively answered directory pages are slower
than the Python provider’s retained store.

Measured on this Linux VM, warm cache, as root:

- With observation off, fdu’s engine settles 3.5 to 5.4 times faster than the Python
  store. There is no Python engine-alone floor with observation on to compare with fdu’s
  observed floor.
- Through the server with observation on, discovery is 2.3 to 4 times faster, but
  “settled” (the first rollup that reports `done`) is only 1.1 times sooner on the
  checkout and 1.47 times on `project-10` (provisional at four runs per side), because
  the first fallback answer after discovery pays a full image.
- fdu’s native folder tree answers as soon as the server listens, like Python’s; the
  root tallies and the folder Overview, both fallbacks, wait for discovery to stop
  moving the version: 7.5 to 7.7 s against Python’s 1.6 s on `project-10`.
- Routes served by a fallback are slower where a full image is built for them (6 to 130
  times at fresh versions in the server runs), and roughly equal where a reused image
  answers (filtered tree, recent).
  Settled RSS is 1.4 to 2.1 times Python’s with the per-version image memo on; there is
  no memo-off or native-only server arm.

The numbers are in [Performance](#performance), the fdu work they justify in
[Required fdu Changes](#required-fdu-changes), and the Metabrowser seams in
[Required Metabrowser Refactors](#required-metabrowser-refactors).

## Reproduce

Revisions measured:

- Metabrowser: `db08e3b8` plus this directory; `evidence/correctness.json` records the
  head and dirty paths each correctness run used
- fdu: `4450be7`, version 0.6.0
- Wheel: `fdu-0.6.0-cp312-abi3-manylinux_2_34_x86_64.whl`, SHA-256
  `d4b9071b377be9201ad95dedaebc19328e0a255cd76dc072fe5fa0cc91fdac1f`
- Toolchain: rustc and cargo 1.97.1 (from fdu’s `rust-toolchain.toml`), maturin 1.14.1
  (fdu’s locked dev group), uv 0.11.32, CPython 3.13.18

The wheel is build output, so it lives outside both repositories.
Build it with fdu’s locked maturin path, the one its Makefile and CI use:

```shell
cd <fdu-checkout>/crates/fdu-py          # checked out at 4450be7
uv run --frozen --only-group dev maturin build --locked --release --out <artifact-dir>
WHEEL=$(ls <artifact-dir>/fdu-0.6.0-*.whl)
```

fdu’s Makefile asks for uv 0.12.1 (`UV_MIN_VERSION`); the build above ran with uv
0.11.32 directly, outside the Make preflight.
The manylinux tag is `2_34` because the wheel was built against this host’s glibc, not
in fdu’s release container.
A rebuild of the same revision produced a different digest: every member, the native
extension included, is byte-identical except maturin’s embedded CycloneDX SBOM (a random
serial number and a timestamp) and the `RECORD` that hashes it, so the digest identifies
this artifact, not the revision.

From the Metabrowser checkout:

```shell
export PYTHONPATH=src:tests:explorations/fdu-provider-spike
UV="uv --config-file uv.toml run --frozen --with $WHEEL python"

# Correctness -> evidence/correctness.json (about 6 minutes)
$UV explorations/fdu-provider-spike/run.py --wheel "$WHEEL"
# The two timing-sensitive SSE tests, 32 fresh processes per provider -> evidence/flake.json
$UV explorations/fdu-provider-spike/flake.py --runs 32

# Timed series -> .bench/fdu-spike/ (about 25 minutes); requires committed scripts
WHEEL=$WHEEL explorations/fdu-provider-spike/series.sh
# Targeted measurements added in review
$UV explorations/fdu-provider-spike/firstread.py --corpus .bench/project-10 --label project-10
$UV explorations/fdu-provider-spike/binding.py --corpus .bench/project-10 --label project-10
$UV explorations/fdu-provider-spike/summarize.py      # -> evidence/performance.json

# Strict type check against the installed wheel
uv --config-file uv.toml run --frozen --with "$WHEEL" bash -c \
  'basedpyright --project explorations/fdu-provider-spike/pyrightconfig.json \
  --pythonpath "$(command -v python)"'
```

`run.py` refuses a wheel whose name or digest differs and refuses an `fdu` imported from
anywhere but an installed wheel’s `site-packages`, so a source-tree import cannot make
integration pass. The corpora are built under the gitignored `.bench/`: the 100,000-file
synthetic tree by `devtools/bench_serving.py` itself, `project-10` by
[Building the corpus](../performance-loop/README.md#building-the-corpus), and
`.bench/corpus-checkout` as a frozen copy of this checkout
(`tar --exclude=./.bench -cf - . | tar -xf - -C .bench/corpus-checkout`), so markers
never touch the working tree and counts do not move between runs.

`series.sh` now refuses to time anything until every script it runs is committed
unmodified, writes the commit and each script’s digest to
`.bench/fdu-spike/frozen-digests.txt`, and takes the performance loop’s series lock.
The recorded series ran before it did: `timed_sources_note` in
`evidence/performance.json` names the version each stage ran and which of them no commit
holds. Following [Durable Storage](../performance-loop/README.md#durable-storage),
normalized evidence and every script it cites are in this directory, and raw output and
corpora are in `.bench/`, which rerunning recreates.

## Files

| File | Role |
| --- | --- |
| `adapter.py` | `FduInventoryBackend` and `FduInventoryHandle`, the spike provider |
| `probe.py` | Fallback and native counters; `FALLBACK_REMEDIES` names the fdu addition behind each fallback |
| `conformance.py` | Runs every provider-parametrized contract case against Python and fdu |
| `rollup_corpus.py` | The File Rollup conformance corpus through fdu’s native classifier |
| `routes.py` | Route, lifecycle, and SSE suites with fdu injected at the runtime composition root, counting fdu backends per test |
| `run.py` | Correctness harness, root-cause classification by failing assertion, `evidence/correctness.json` |
| `flake.py` | Two timing-sensitive SSE tests repeated in fresh processes, `evidence/flake.json` |
| `launcher.py` | Spike-only `metab` entry point; `METABROWSER_INVENTORY_PROVIDER=fdu` selects the spike |
| `bench.py` | Paired serving runs: `synthetic` (unchanged `bench_serving`), `tree`, and `floor` |
| `projections.py` | Per-projection read latency at fresh versions, in process |
| `discovery.py` | Open to first answer per projection kind while discovery runs, in process |
| `firstread.py` | Server start to each route’s first answer, with a socket-only readiness check |
| `binding.py` | fdu’s per-row cost split into native read, Python rebuild, and adapter conversion |
| `series.sh` | The timed series, its source check, digest record, and lock |
| `summarize.py` | Paired medians, A/A bands, verdicts, and the review measurements into `evidence/performance.json` |
| `evidence/` | Normalized correctness, flake, and performance evidence |

The seam research the lead gathered for this spike is in
[research-inputs/metabrowser-seam.md](research-inputs/metabrowser-seam.md) and
[research-inputs/fdu-api-and-gaps.md](research-inputs/fdu-api-and-gaps.md); its findings
were checked against code before they are repeated here.

## Adapter Design

Selection is a spike-only seam: `launcher.py` and `routes.py` replace the runtime
composition root’s `create_inventory_backend` reference in one process (and `routes.py`
restores it when its pytest session ends).
Nothing under `src/` changes, and the shipping sealed factory still rejects `fdu`.

### Native

| Contract item | fdu mapping |
| --- | --- |
| Checkpoint read | `OpenedIndex.state()`; a `Diagnostics()` follow-up at the same version only when the state carries issues |
| `EntryQuery` | `Lookup`, with `Knowledge` present, absent, or unknown mapped one to one |
| `DirectoryQuery` | `Tree(depth, include_ignored, Page)` and `Continue`; fdu’s level order, directory-first canonical byte order, and opaque single-use continuations already match the contract |
| `CatalogQuery` | `Flat` with an `EntrySelection` (file kind, `exclude_ignored`, terminal suffixes, ancestor names, `max_size = size_less_than - 1`) and `Aggregate` for the capped count, read together at the bundle’s version under one work budget |
| `DiagnosticsQuery` | `Diagnostics` and a root `Lookup` for directory counts |
| Version pins | `read(expected=...)`; a moved version raises `VersionUnavailableError` |
| State vocabulary | fdu’s phase, coverage reason, freshness, source, and issue kinds carry Metabrowser’s exact value spellings |
| Work counters | fdu’s `Work` has the same thirteen fields as `WorkCounters` |
| `changes()` | `changes(cursor, timeout=0.25)` on one dedicated poll thread; reset, all-dirty, and dirty paths from the native impact |
| `refresh()` and `prioritize()` | Native, with the receipt’s terminal version |
| `close()` | Joins in-flight reads (a dedicated read pool), closes natively on the poll thread, then joins it |
| Registry identity | fdu parses the registry text and derives `type_rules_fingerprint` from what it parsed |

### Translated

Each translation is exact unless marked; the counted ones appear in the probe.

- **Identity:** session `fdu:<hex>`; scope fingerprint from Metabrowser’s
  `inventory_scope_fingerprint`; semantic fingerprint is the canonical-pair SHA-256 of
  fdu’s three native semantic identities, checked unchanged on every response.
- **Progress and diagnostics:** `IndexProgress.entries_observed` carries fdu’s retained
  file count (fdu reports no entry count in its state), and
  `ProviderDiagnostics.directories_indexed` is the root rollup’s directory count from
  the most recent read that fetched it.
- **Directory facts:** directory `mtime_ns` and `newest_mtime_ns` are the newest
  descendant file’s modification time, or 0, as the Python store sets them; aggregates
  are reported only at complete coverage (fdu exposes no per-subtree completeness, so
  the adapter reports `None` rather than partial counts as final).
- **`empty`:** fdu’s rollup counts files only, so a directory with no files is probed
  for symlink leaves with a bounded `Tree` read at the read’s version
  (`directory_empty_probe`).
- **Extensions:** fdu’s `NameClassification.logical_extension`; checked against
  `derive_ext` on every converted row in the correctness run (no mismatch;
  `representative_read.probe.extension_checks`).
- **Backslash identity** (`backslash_identity`): fdu’s portable path escapes `%` and
  undecodable bytes exactly as Metabrowser does but keeps a POSIX backslash, which
  Metabrowser escapes as `%5C`; identity translates exactly, order does not (finding
  F2).
- **Page bound** (`page_chaining`): fdu refuses pages above 4,096 rows; Metabrowser asks
  for up to `budget.max_files` rows per catalog page.
  A larger page is read as a chain of native pages at the pinned version, each its own
  read, with the query’s `max_work` carried as one remaining budget across the chain.
  A catalog chain that runs out returns the typed limit charged at the bound; a tree
  chain stops with rows and a continuation, as fdu’s soft tree budget does.
- **Read bound** (`projection_chunking`): fdu refuses more than 16 projections per read;
  the coordinator bundles one `EntryQuery` per dirty path, so larger bundles are chunked
  at one pinned version.
- **Priority bound** (`priority_chunking`): fdu refuses more than 64 priority paths.
- **Helper reads:** a fallback needs the root record and entry count, and a diagnostics
  query the directory count; those are read separately at the same version and not
  charged to the request’s work (`helper_reads`).
- **Catalog continuation count** (`catalog_offset_ledger`): a continued page reuses the
  first page’s count from a handle-local ledger and raises the lower bound by rows
  already emitted, as the Python oracle does from its memo.
- **Continuation identity** (`continuation_identity_ledger`): the same bounded ledger
  refuses a continuation resubmitted with a different path, depth, or filter, which
  fdu’s `Continue` cannot check.
- **Unpinned reads:** a moved version during an unpinned read’s follow-up native reads
  is retried with back-off (5 ms doubling to 200 ms, 120 s deadline, then a typed
  contract error), never raised as `VersionUnavailableError`, which the contract
  reserves for pinned reads.
- **Change batches:** dirty paths come only from commits with a data domain; a
  state-only commit (a refresh entering reconciliation) still names paths, and taking
  those as dirty made the host publish a removal before the commit that performed it.
  A batch whose issues fdu no longer retains at its version becomes a reset at a version
  whose issues can be read.
- **Journal capacity:** fdu budgets bytes with a 64 KiB floor; the adapter maps
  `change_queue_size` to `max(64 KiB, 4 KiB × batches)`, which has no exact meaning.
- **Issues:** paths made root-relative and canonical; fdu retains at most 64 issues, and
  an omitted count is summarized in the last retained record.
- **Watch facts:** `watch_mode`, `watch_state`, and `watch_reason` derived from phase
  and coverage, including `off`/`resource_budget` after a budget stop.
- **Errors:** fdu’s `InvalidArgumentError` and `FilesystemError` become
  `InventoryContractError`.
- **Registry schema** (`registry_downlevel`, finding F1): fdu reads schema 3 and 4 and
  refuses unknown fields; schema 5 adds only the presentation field `chroma_ratio`, so
  the shim strips it and declares schema 4. Any other difference still fails at open.
  This is a labeled input deviation, not a native capability.
- **Lifecycle with observation on:** fdu passes through a transient `ready` between
  discovery and its pre-watch reconcile; because fdu reports observer failure as
  `failed`, never `ready`, the adapter reports that `ready` as `reconciling`. An
  observer failure (`ObservationTransition::Failed`: phase `failed`, coverage untouched,
  where a discovery failure sets coverage `Partial(Failed)`) maps to `ready`, stale, and
  an `observation_gap` issue.
  This host cannot induce an inotify failure, so that mapping is unexercised.

### Fallbacks

`FilteredTreeQuery`, `GroupedTreeQuery`, `RollupQuery`, `NavigationQuery`, and
`RecentQuery` have no native projection.
The adapter materializes one native `Flat(FULL)` image of the read’s exact version,
loads it into a private instance of the Python reference store, and projects there.
With `FDU_SPIKE_IMAGE_MEMO=1` (the default) a second fallback read at the same exact
version reuses the image, mirroring the Python provider’s per-revision memos; a version
change discards it and the oracle’s continuations for older versions.
Work over the limit is a typed `QueryLimitProjection` before anything is materialized.

On the frozen checkout copy, one bundled read of all nine kinds materialized 10,475 rows
and 490,179 path bytes once, then reused the image for the other four fallbacks; it
rebuilt 520 child buckets for the rollup and made one full-result sort each for the
filtered tree and recent (`representative_read.probe` in the correctness evidence).

### Not Possible Without fdu Changes

- A hard `max_work` limit on directory pages (fdu’s tree budget is deliberately soft).
- Replay capacity expressed in batches (fdu budgets bytes).
- A polling observer (`watch_mode="poll"`).
- Canonical row order for names containing a backslash.
- A schema-5 registry without the down-level shim.
- Progressive directory aggregates for completed subtrees during discovery.
- A fallback answer while discovery moves the version every few milliseconds, since a
  multi-page image needs several reads at one version and fdu retains only the current
  one.

## Correctness

Every failure below is classified by the assertion it stopped at; a failure that moves
elsewhere is reported unclassified.
Classes: (a) adapter bug, (b) fdu gap, (c) Metabrowser contract or test
over-specification, (d) test reaches into Python-provider internals or is defeated by
the spike’s own injection.

### Provider Conformance

Every factory-parametrized case in `tests/test_inventory_provider_contract.py`, the 21
registered cases plus the unregistered age-band case.
Python passes all 22; fdu passes 17.

| Test | fdu stops at | Class | Root cause |
| --- | --- | --- | --- |
| `test_provider_semantic_digest` | `:1253` provider name | d | Asserts `diagnostics.provider == "python"`; with that masked, every fact, order, aggregate, filter, rollup, navigation, recent, and catalog value matches |
| `test_provider_applies_work_bounds_to_continuation_pages` | `:1627` directory half | b | fdu’s soft tree budget returns rows instead of a typed limit and consumes the single-use continuation; the case never reaches its other halves (below) |
| `test_provider_returns_typed_query_limits_without_partial_answers` | `:1674` directory query | b | The same soft budget; the other five kinds limit at `rows_visited=2` (below) |
| `test_provider_budget_stop_is_explicit_and_absence_remains_unknown` | `:1302` | c | Assumes the two-file budget admits `a.txt` and `b.txt` (Python’s sorted admission); fdu admits in readdir order (`b.txt` and `z.txt` here), which the contract does not order. Stop, coverage, issue, and watch facts all match. Whether admission should be deterministic is also an fdu design question |
| `test_provider_changes_resume_and_report_history_gaps_as_reset` | `:1859` | c | Requires a gap at capacity one; fdu’s 64 KiB journal floor keeps both commits replayable |

Each half of the work-bound cases, run on its own against both providers
(`work_bounds_by_half`):

| Case | Python | fdu |
| --- | --- | --- |
| Directory continuation, `max_work=1`, then 4 | limit (1 visited, 0 returned), then 4/4 | rows (3 visited, 2 returned), then continuation unavailable |
| Filtered-tree continuation, `max_work=1`, then 4 | limit (1/0), then 4/4 | limit (1/0), then 4/4 |
| Catalog continuation, `max_work=1`, then 4 | limit (1/0), then 4/4 | limit (1/0), then 4/4 |
| Six kinds at `max_work=2` in one read | six limits; bundle 12 visited, 0 returned | five limits and directory rows; bundle 13 visited, 2 returned |

Only the directory query differs, and only because of the soft tree budget.

The File Rollup conformance corpus through fdu’s native classifier: 153 of 153 metadata
cases agree on logical extension, canonical extension, kind, family, group, and content
family (fdu exposes no `confidence` or `detection_source`). Each of the 21 invalid
registries is down-leveled through the adapter’s shim first, so none is refused merely
for being schema 5, then fdu’s refusal is compared with the defect the case names: 18
are refused for that defect, `invalid-toml` is refused for a structural rather than
TOML-syntax reason, `previous-schema-version` is accepted because fdu reads schema 4 by
design, and `undeclared-chroma-deviation` is accepted because the shim strips the field
the case is about. The two aggregate cases need a breakdown projection fdu lacks.

### Routes, Lifecycle, and SSE

A route test says something about fdu only if it builds a runtime, so each result
records how many fdu backends it built.
Without injection Python passes all 168 inventory suite tests and all 17 of the 2A
selection, run in the same harness.

| Selection | Tests | Pass with fdu injected | Of those, built an fdu backend | Fail |
| --- | ---: | ---: | ---: | ---: |
| 2A route and SSE selection | 17 | 16 | 16 | 1 |
| Inventory route suites from the [provider plan](../../docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md) | 168 | 161 | 85 | 7 |

Every 2A test built an fdu backend, and its one recorded failure is the
pending-inventory test below.
So 85 passes exercise fdu in the inventory suites; the rest (all of
`test_browser_rollup.py`, most of `test_inventory_coordinator.py` and
`test_browser_watch_backends.py`) construct their provider directly and ran Python.

| Test | fdu stops at | Class | Root cause |
| --- | --- | --- | --- |
| `test_api_tree_uses_pending_inventory_without_filesystem_fallback` | `test_browser_inventory_api.py:480` | d | Monkeypatches `python_inventory.walk_tree` to hold discovery |
| `test_root_directory_envelope_and_pending_state` | `test_api_folder_envelope.py:97` | d | Same |
| `test_api_catalog_is_incomplete_while_discovery_is_blocked` | `test_catalog_feed_server.py:139` | d | Same |
| `test_walker_completion_projects_capability_update` | `test_catalog_feed_server.py:424` | d | Same |
| `test_api_index_progress_does_not_304_while_active` | `test_browser_events_route.py:615` | d | Same |
| `test_tree_dump_honors_inventory_provider_selection` | `test_browser_walk.py:420` | d | Asserts the sealed factory rejects an unknown name, which the spike’s injection bypasses |
| `test_watcher_detects_new_file_after_walker_completes` | open | b | `watch_mode="poll"`; fdu has no polling observer, refused as a typed error |
| `test_rollup_payload_and_etag_share_one_version` | `test_rollup_route.py:464` (4 of 6 isolated runs) or `:474` (2 of 6) | c, d | See below |
| `test_touch_existing_file_emits_one_upsert_path` | `test_e2e_filesystem_to_sse.py:174`, intermittent: passed in the recorded run, fails 20 of 32 fresh-process runs | c | A native refresh begins with a state-only commit (freshness to reconciling); when a poll returns it alone, the host projects it as `capability.update`, which the test forbids. The contract allows state-only batches |

The rollup and ETag case has two failure modes.
At `:464` (“the version must hold”), a native refresh is three commits (freshness to
reconciling, insert, verified to fresh); the receipt names the last, but the host relay
can still be publishing an earlier one when `refresh()` returns (class c). At `:474`
(the first body has one file, not two), the test gates `python_inventory.build_rollup`,
which engages only because the spike’s rollup is the Python oracle; the gated build
answers from the immutable image of the version the read began at, a coherent older
boundary with its own tag, while Python’s mutable store detects the move and rereads
(class d, with the reread policy pinned as c). Python passes the isolated case 6 of 6
(`rollup_etag_modes`).

`evidence/flake.json` repeats the two timing-sensitive SSE tests in 32 fresh processes
per provider, alternating.
The recursive-removal coalescing test passes 32 of 32 with fdu and 32 of 32 with Python.
The touch test passes 32 of 32 with Python and 12 of 32 with fdu; all 20 fdu failures
stop at `:174` for the `capability.update` above.
Before the change-batch fix the touch test was masked: the state-only first commit’s
impact paths were taken as dirty, so that batch carried the touched path and the host
projected it as `fs.change`. An adapter could hide a reconciling-to-fresh round trip by
holding a state-only batch until the next poll, at the cost of change latency and of
reporting a state the engine was not in; the spike does not, and the test’s assertion is
refactor 2 below. Before the change-batch fix the removal test failed 28 of 32 with
adapter `c03c8851` and 9 of 12 with the timed one: a refresh’s state-only first commit
named `sub1`, the host reread it after the removal commit had landed, and published a
partial removal, then a second envelope.
That was an adapter bug (class a), not a shared flake.

The lifecycle probe opened through `InventoryCoordinator`, reached `watching`, delivered
a live file creation coherent on reread, refreshed, replaced the root, joined an
iterator-only cancellation within the 250 ms poll, left the handle usable, and closed
concurrently twice with no surviving spike thread.

## Performance

All timings are from one Linux VM: kernel 6.18.44, x86_64, 4 vCPU, 15.7 GiB RAM, CPython
3.13.18, running as root with a warm page cache; the 1-minute load was 0.3 to 1.0 when
each series started.
They are evidence about this regime only.
Every server run is a fresh `metab` process started through the same launcher shim and
interpreter for both providers.
Each trial runs four arms in rotated order (python A, fdu A, python B, fdu B), so
same-letter arms share a trial but can be three runs apart.
The A/A band is the B/A ratio of one provider within a trial; the paired ratio is fdu
over Python for the same arm letter.
An effect is called only when every paired ratio falls outside both providers’ A/A
bands, the [accept rule](../performance-loop/README.md#the-accept-rule)’s range test.
Rows below cleared it unless marked “noise”; “provisional” marks an effect under 2×
called at fewer than the accept rule’s five runs per side.
The full distributions, bands, and verdicts are in `evidence/performance.json`.

What the timed series ran is not quite the adapter in this directory.
It ran adapter `c19ea02d`, which took dirty paths from state-only commits (extra host
rereads, and an upsert that could publish from a state commit’s reread) and raised
`VersionUnavailableError` for an unpinned read after four moved-version retries (see
[Unhandled Server Exceptions](#unhandled-server-exceptions)). The review fixes change no
native work on a timed path except those, and the series was not rerun.
`firstread.py` and `binding.py` ran adapter `c03c8851` (held by commit `b6129b1c`),
which has every review fix except the change-batch dirty-path fix.

### Corpora

| Corpus | On disk | Retained by both providers |
| --- | --- | --- |
| Synthetic (`bench_serving` 100k) | 100,000 files, 972 directories | 100,000 files, 101,105 entries |
| Checkout copy | 27,167 files, 3,051 directories | 9,954 files, 10,475 entries |
| `project-10` | 272,542 files, 31,901 directories | 141,070 files, 148,441 entries |

The hidden-component rule prunes `.git` and every `.venv` from both providers’ scope;
`node_modules` is retained as ignored content.
No real tree on this host is larger than 79k files, so `project-10`, which copies real
locked installs, stands in for the larger real tree.

### Engine Floor

Each engine alone in a fresh process, four samples.
The Python store and the first fdu column run with observation off; the last three
columns are fdu with observation on, for which there is no Python counterpart.
Both poll for settle (every 2 ms), Python through its async handle and fdu through
`state()`.

| Corpus | Python store, open to settled | fdu, open to settled | fdu observed: `open()` returns | discovered | watching |
| --- | ---: | ---: | ---: | ---: | ---: |
| Checkout copy | 0.50 s | 0.14 s | 0.19 s | 0.28 s | 0.32 s |
| Synthetic 100k | 3.94 s | 0.72 s | 0.29 s | 0.97 s | 1.32 s |
| `project-10` | 7.49 s | 1.42 s | 1.45 s | 2.94 s | 4.43 s |

With observation on, `open()` blocks while notify registers recursive inotify watches
(1.45 s on `project-10`), and the full-root reconcile pass fdu runs before `watching`
adds 0.04 to 1.5 s. Process maximum RSS is about equal at the engine layer (161 MB
Python, 159 MB fdu on `project-10`; 185 MB with observation).

### Synthetic 100k Through `bench_serving`

Three trials, n = 6 per provider.

| Metric | Python | fdu | fdu / Python |
| --- | ---: | ---: | ---: |
| Cold scan, nothing attached (walker’s own record) | 4,108 ms | 1,040 ms | 0.25 |
| Scan with a client attached, to `done` | 9.85 s | 4.60 s | 0.47 |
| First nonzero folder count on the wire | 0.92 s | 4.58 s | 5.1 |
| Settled rollup at a fresh version | 21 ms | 2,748 ms | 130 |
| Settled rollup, retained body and 304 | 2.2 ms, 1.7 ms | 2.5 ms, 1.9 ms | noise |
| Navigation, first and reused | 282 ms, 1.7 ms | 335 ms, 3.9 ms | noise, 2.3 |
| Catalog, first body (5 MB) | 462 ms | 2,172 ms | 4.8 |
| `/api/tree` root depth 2, `top00/mid00` depth 2 | 3.8 ms, 10.0 ms | 6.9 ms, 19.0 ms | 1.8, 2.1 |
| Settled RSS | 175 MB | 376 MB | 2.1 |
| Settled-phase process CPU | 6 s | 32.5 s | 5.4 |

fdu’s attached-phase rollup latency is not comparable and is not shown: it answered no
rollup during discovery, so bench_serving’s startup probe absorbed the wait and its one
timed rollup came after settle.
First count on the wire is the honest metric for that phase.
CPU comes from `ps`, at one-second resolution.
RSS and CPU describe fdu with the per-version image memo on.

### Real Trees

Two trials, n = 4 per provider; route latencies are p50 at a fresh version, eight rounds
on the checkout and five on `project-10`. Each round writes a marker file, waits for its
SSE record, then requests each route.

| Metric | Checkout: Python | fdu | `project-10`: Python | fdu |
| --- | ---: | ---: | ---: | ---: |
| Discovery (walker’s own record) | 616 ms | 262 ms | 10,683 ms | 2,958 ms |
| Server start to settled (first rollup reporting `done`) | 1.39 s | 1.28 s (provisional) | 12.8 s | 8.71 s (provisional) |
| Mutation to SSE, p50 and p95 | 79, 100 ms | 54, 55 ms (provisional) | 74, 84 ms | 54, 55 ms (provisional; p95 noise) |
| Navigation | 34 ms | 279 ms | 444 ms | 4,381 ms |
| `/api/tree` root depth 1, depth 2 | 2.3, 6.8 ms | 3.0, 13.1 ms (provisional) | 2.0, 3.0 ms | 2.9, 5.1 ms (provisional) |
| `/api/tree` largest subfolder depth 2 | 9.5 ms | 17.7 ms (provisional) | 20.0 ms | 43.4 ms |
| Filtered tree (`.md`, depth 3) | 24 ms | 25 ms (noise) | 304 ms | 338 ms (noise) |
| Grouped tree (type, depth 2) | 20 ms | 23 ms (noise) | 187 ms | 241 ms (provisional) |
| Rollup overview, treemap | 3.6, 7.7 ms | 21.6, 11.9 ms (treemap provisional) | 4.1, 17.6 ms | 458, 90 ms |
| Recent | 30 ms | 34 ms (noise) | 221 ms | 286 ms (noise) |
| Catalog | 9.8 ms | 50 ms | 219 ms | 1,503 ms |
| Settled RSS, sampled peak | 82, 92 MB | 119, 131 MB (provisional) | 246, 287 MB | 377, 480 MB (provisional) |
| Process CPU over the whole run | 3 s | 6 s | 23.5 s | 56 s |

Navigation is the first route each round, so with the per-version image memo it pays the
fallback image for the routes after it; the filtered, grouped, recent, and treemap
numbers are the oracle alone over a reused image.
Mutation to SSE is not an engine-speed measure: both providers batch observations on the
same 50 ms step (fdu’s `WatchConfig.settle` copies watchfiles’ 50 ms step and 1.6 s
ceiling), so fdu’s 54 ms is its settle floor plus about 4 ms, and the 20 to 25 ms gap is
post-batch work and loop timing.

### First Answers With a Socket-Only Readiness Check

`bench_serving.Server` waits for `/api/rollup` to return 200 before it hands the server
over, so anything timed after it inherits the rollup’s readiness.
`firstread.py` counts the server as listening once its socket accepts a connection, then
polls three routes independently from process start; three runs per provider, adapter
`c03c8851`.

| Route | Checkout: Python | fdu | `project-10`: Python | fdu |
| --- | ---: | ---: | ---: | ---: |
| Socket accepts | 0.61 s | 0.64 s | 1.62 s | 1.67 s |
| `/api/tree` depth 1 (native directory page, no tallies) | 0.62 s | 0.65 s | 1.63 s | 1.68 s |
| `/api/tree` depth 0 (root summary with navigation tallies, a fallback) | 0.62 s | 1.13 s | 1.63 s | 7.46 s |
| `/api/rollup` Overview (a fallback) | 0.62 s | 1.14 s | 1.63 s | 7.68 s |

Every first answer was a 200; the depth-1 tree answered while the index was still
scanning, and only the depth-0 summary carries tallies, as the route bundles navigation
only for the root at depth 0. One fdu run on `project-10` answered the root summary at
1.75 s, before the tree grew past one native page.
With no client polling throughout, Python’s `project-10` discovery took 5.5 s here
against 10.7 s in the tree runs; fdu’s took 2.6 s.

### Per Projection, In Process

`projections.py` refreshes a marker file before every sample, so both providers are at a
new version and neither answers from a per-version memo; p50 ms, fdu against Python.
It runs both providers in one process with no A/A arm, so read it for orders of
magnitude; a ratio near one, such as the synthetic catalog page, is not resolved.

| Kind | Checkout (n = 7) | Synthetic 100k (n = 5) | `project-10` (n = 3) |
| --- | ---: | ---: | ---: |
| Entry (root) | 0.45 vs 0.28 | 0.53 vs 0.28 | 0.50 vs 0.25 |
| Directory, depth 2 | 7.3 vs 2.0 | 4.3 vs 1.2 | 3.1 vs 0.9 |
| Catalog, 10,000-row page | 45 vs 5.5 | 183 vs 178 | 214 vs 156 |
| Filtered tree | 212 vs 20 | 2,895 vs 164 | 4,681 vs 252 |
| Grouped tree | 224 vs 15 | 3,099 vs 102 | 4,868 vs 167 |
| Navigation | 215 vs 27 | 3,083 vs 228 | 5,499 vs 386 |
| Recent | 186 vs 4.4 | 3,023 vs 99 | 4,945 vs 114 |
| Rollup overview | 210 vs 1.4 | 3,059 vs 1.1 | 5,116 vs 1.9 |
| Diagnostics | 0.66 vs 0.45 | 0.64 vs 0.46 | 0.79 vs 0.30 |

Every fallback costs about the same at a given size because each pays a full image.
Python’s rollup is nearly free because its subtree aggregates survive a one-file change;
the oracle over a fresh image rebuilds them.

### Where fdu’s Per-Row Cost Goes

`binding.py` times every page of a full-index `Flat` read in three parts, five
repetitions per corpus, medians in µs per row.

| Corpus | Rows | `_native.read` (engine and PyO3 wire objects) | `fdu.opened` dataclass rebuild | Adapter conversion |
| --- | ---: | ---: | ---: | ---: |
| Checkout copy | 10,474 | 3.5 | 5.6 | 3.5 |
| Synthetic 100k | 101,104 | 3.6 | 7.8 | 3.8 |
| `project-10` | 148,440 | 4.2 | 9.6 | 3.9 |

The `COMPACT` shape is 0.3 µs cheaper per row in each part.
The rebuild in `fdu.opened` (a `Path` and a nested dataclass tree per row) is the
largest share and grows with the tree.
The catalog page is a different cost: on the checkout copy the native read of the
catalog selection alone takes 11.9 ms for its 1,816 matching rows (a scan of all 10,474
entries), and fdu scans twice, once for the page and once for the capped count, so its
whole answer is 36.5 ms against Python’s 5.1 ms; on the synthetic tree, where every file
matches, the two whole answers are equal (164 and 169 ms).

### During Discovery

`discovery.py` opens a fresh handle per sample and reads one kind in a loop from the
moment `open` returns; it ran on the timed adapter.
Native kinds (entry, directory) answer in about 8 ms for fdu and 6 ms for Python.
For the fallbacks, any image larger than one native page needs several reads pinned to
one version, and fdu retains only the current version while discovery commits move it.
On the synthetic tree, three trials raised `VersionUnavailableError` 206 times for the
rollup and 98 for navigation after 626 and 298 internal retries; the rollup’s median
first answer was 2,335 ms against Python’s 5.5 ms.
The reviewed adapter retries such a read with back-off instead of raising, so the read
waits rather than fails.

### Unhandled Server Exceptions

The recorded fdu tree runs logged unhandled `Exception in ASGI application` tracebacks,
every one an unpinned `/api/rollup` read during discovery that the timed adapter
answered with `VersionUnavailableError`: 0, 0, 1, and 0 on the checkout and 4, 3, 6, and
5 on `project-10`; every Python run logged none (`asgi_exceptions` in the performance
evidence). Adapter `c03c8851` logged none in `firstread.py`’s six fdu runs.

## Required fdu Changes

Ordered by what they unblock, each with the evidence above.

1. **Native projections for the five fallback kinds.** Filtered tree, grouped tree, the
   File Rollup breakdown, navigation, and ranked recent pay a full flat image whenever
   one is not already built for the version (8 to 2,800 times Python in process, no A/A
   arm; 6 to 130 times through the server at a fresh version), and cannot answer while
   discovery moves the version.
   The maintained structures already exist in fdu’s serving indexes (semantic type
   tallies, exact-name tallies, global recency order); the readers do not.
   Recent and age filters must read modification time (`TimeBasis.MODIFIED`), since
   fdu’s default clock is change time.
2. **A cheaper Python row path.** Of 12 to 18 µs per row on a full-index read, 5 to 10
   µs is `fdu.opened` rebuilding wire dictionaries as a `Path` and nested dataclasses
   per row, and 3.3 to 4.2 µs is the native read and PyO3 wire objects.
   A lean row shape (portable path, kind, size, mtime, ignored, classification ids, and
   directory totals as plain tuples or columns) would remove most of the first.
3. **A catalog page and its count from one scan.** The checkout catalog is bound by the
   selection scan, run twice (page and `Aggregate`), not by conversion; a page that
   reports its capped count, or a count from a maintained index, halves it.
4. **Registry schema 5 (F1).** fdu 0.6.0 refuses Metabrowser’s registry at open
   (`unknown family field "chroma_ratio"`). The only addition is presentation, which
   fdu’s fingerprint already excludes (153 of 153 classification cases agree through the
   shim).
5. **One escape rule for a POSIX backslash (F2).** fdu keeps the backslash byte in a
   portable path, where Metabrowser escapes it as `%5C`. Identity translates exactly,
   but fdu’s directory and catalog order then differs from the contract’s canonical byte
   order (`identity_and_bounds` in the evidence).
6. **Version retention across a bounded multi-page read, or larger bounds.** fdu holds
   only the current version, 4,096 rows per page, and 16 projections per read; a catalog
   page of `budget.max_files` rows, a fallback image, or a coordinator reread of 17
   dirty paths needs several reads at one version, and during discovery or churn the
   version moves between them.
   Either retain a short window of recent versions for `expected`, or raise the bounds
   to Metabrowser’s (`MAX_QUERIES_PER_READ` and `MAX_COMMAND_PATHS` are 1,024; priority
   is capped at 64).
7. **A hard work limit on tree pages, or a decision that the contract’s is soft.** fdu’s
   tree budget is soft by design, so the two work-limit cases fail on their directory
   query alone and a limited continuation is consumed rather than kept for retry.
8. **Leaf counts and subtree completeness in directory rows.** The rollup counts files
   only, so `empty` for a file-less directory needs a probe; and with only
   `children_complete`, the adapter cannot report progressive totals for finished
   subtrees during discovery.
9. **Lifecycle and impact shape with observation on.** fdu passes through a transient
   `ready` before its pre-watch reconcile, reports observer failure as terminal
   `failed`, and names paths in the impact of state-only commits; the adapter now
   translates all three, but the native values should say what the contract means.
10. **A polling observer, or an explicit decision not to have one.** `watch_mode="poll"`
    is refused.
11. **Deterministic admission under a budget,** if the contract is to promise which
    files a stopped root retains; fdu admits in readdir order.
12. **A reproducible wheel.** Two builds of the same revision differ only in maturin’s
    embedded SBOM and the `RECORD` that hashes it, so a pinned digest cannot be
    re-derived by rebuilding.

## Required Metabrowser Refactors

Each is evidence that the current seam pins Python behavior rather than the contract.

1. **A provider-owned discovery barrier for tests.** Six route tests (and the 2A one
   still) monkeypatch `python_inventory.walk_tree` or the sealed factory, so they cannot
   run against any other provider.
   A scripted discovery or observation source owned by the provider would make them
   provider-neutral, as 2A also recommended.
2. **Tests that pin Python specifics.** The semantic digest asserts the provider name;
   the budget case asserts which files a sorted walker admits; the replay case treats
   capacity as a maximum; the touch test asserts a verified refresh causes no state
   transition. State capacity as a minimum a provider retains, assert budget invariants
   rather than names, compare digests modulo provider identity, and allow state-only
   batches.
3. **`refresh()` should return after the host relay has published the receipt’s
   version,** or the contract should say sub-batches are visible.
   A native refresh is three commits, and
   `test_rollup_payload_and_etag_share_one_version` observes an intermediate one.
4. **Route handling for a provider error on an unpinned read.** `/api/rollup` let
   `VersionUnavailableError` escape as an unhandled ASGI exception (3 to 6 per
   `project-10` run). The contract reserves that error for pinned reads, so the timed
   adapter was wrong to raise it, but the route should still answer a provider failure
   with a typed retryable response rather than a traceback.
5. **Page sizes chosen for an in-memory Python store.** Catalog pages of
   `budget.max_files` rows and one `EntryQuery` per dirty path both assume a provider
   with no per-row binding cost or request bounds.
   A provider page-size hint honored by host assembly, and facts carried in change
   batches (the seam research’s `mb-l2eh`), would remove the chaining and chunking
   translations.
6. **Factory registration and packaging** as Checkpoint 2C lists: an explicit `fdu`
   choice, an optional exact wheel, a typed startup failure, and `bench_serving`’s
   provider list and synthetic-only tree paths generalized, along with a readiness check
   that does not depend on the rollup; this spike reached all of them through a launcher
   instead.
7. **Permission-denied semantics, to verify as a non-root user.** The seam research
   found the Python provider reports an unreadable directory as empty and complete; fdu
   reports `inaccessible` partial coverage, which the host may treat as never settling.
   Root cannot exercise this; it is a [macOS validation](#macos-validation) slot.

## Corrections After Review

An independent review recomputed every table and found claims the evidence did not
support. These are withdrawn or corrected above:

- **“Server start to first useful `/api/tree`”** timed the server’s rollup readiness
  gate, not the tree, and the refactor it motivated (“`/api/tree` stops bundling
  navigation tallies with every page”) was wrong: the route bundles tallies only for the
  root at depth 0. The socket-only measurement replaces it.
- **Work numbers.** Pages above 4,096 rows gave every native page the full `max_work`,
  so a large catalog ignored its hard limit, and helper projections were charged to the
  request. Both were adapter bugs and are fixed; the per-half table replaces the claim
  that the catalog and filtered-tree halves matched before.
- **Route counts.** “161 of 168 pass with fdu” counted tests that never built an fdu
  backend; only 85 did.
  The earlier “Python passes all 168” baseline is now recorded.
- **The recursive-removal test** was reported as an intermittent failure for both
  providers. The Python failures came from runs where the injection leaked into later
  pytest sessions in one process; in fresh processes Python never failed, and the fdu
  failures were an adapter bug, now fixed.
- **The touch test** was reported as failing 4 of 6 isolated runs, a sample too small
  for a rate; 32 fresh-process runs give 20 of 32 for fdu and 0 for Python.
- **Invalid registries.** “20 of 21 refused” counted refusals for being schema 5; with
  the shim applied first, 18 are refused for their own defect.
- **Binding cost.** “10 to 14 µs per row in the binding” was one sampled loop; the split
  above attributes it.
- **Scope.** Speed-ups are stated for the regime and observation mode they were measured
  in, effects under 2× at four runs per side are marked provisional, and the in-process
  ratios are stated as having no A/A arm.

## macOS Validation

Everything above is Linux evidence: inotify, ext4-style readdir order, and a process
running as root, which reads mode-000 files and so cannot exercise permission failures.
The pull request is validated on macOS (arm64) separately.
Rebuild the wheel there and rerun the same harnesses.
`run.py` and `summarize.py` default to `-darwin` output names off Linux, so the Linux
evidence is not overwritten, and `series.sh` refuses to time uncommitted scripts and
takes the performance loop’s series lock.

```shell
# fdu, checked out at 4450be7, with the toolchain from rust-toolchain.toml
cd <fdu-checkout>/crates/fdu-py
uv run --frozen --only-group dev maturin build --locked --release --out <artifact-dir>
WHEEL=$(ls <artifact-dir>/fdu-0.6.0-*macosx*.whl)
shasum -a 256 "$WHEEL"

# Metabrowser checkout
export PYTHONPATH=src:tests:explorations/fdu-provider-spike
UV="uv --config-file uv.toml run --frozen --with $WHEEL python"
$UV explorations/fdu-provider-spike/run.py --wheel "$WHEEL" \
  --expect-wheel-name "$(basename "$WHEEL")" --expect-wheel-sha256 <digest-from-shasum>
$UV explorations/fdu-provider-spike/flake.py --runs 32
WHEEL=$WHEEL explorations/fdu-provider-spike/series.sh
for corpus in corpus-checkout project-10; do
  $UV explorations/fdu-provider-spike/firstread.py --corpus .bench/$corpus --label $corpus
  $UV explorations/fdu-provider-spike/binding.py --corpus .bench/$corpus --label $corpus
done
$UV explorations/fdu-provider-spike/summarize.py
```

Run as an ordinary user, not root, so the permission cases mean something.
Record the host as the performance loop asks: model, memory, macOS version, power state,
and whether Spotlight is indexing the corpus volume.

FSEvents-specific checks, to fill in:

| Check | How | Linux result | macOS result |
| --- | --- | --- | --- |
| `open()` return time with `observe=True` | `bench.py floor`, `fdu-observed.open_returned_s` | See [Engine Floor](#engine-floor) |  |
| Open to `watching`, including fdu’s full pre-watch reconcile pass | `fdu-observed.watching_s` | See [Engine Floor](#engine-floor) |  |
| Mutation to SSE latency | `bench.py tree`, `live_change_*_ms` | See [Real Trees](#real-trees) |  |
| Burst coalescing: 1,000 files created in one directory | count `ChangeBatch` and SSE envelopes per burst | Not measured |  |
| Recursive removal in one envelope | `flake.py` | See [Routes, Lifecycle, and SSE](#routes-lifecycle-and-sse) |  |
| Rename within the root (paired) and out of the root (unpaired) | `EffectiveChange` kinds and `InvalidateReason.UNPAIRED_RENAME` | Not measured |  |
| Case-only rename on case-insensitive APFS (`a.txt` to `A.txt`) | identity, order, and one removal plus one insertion | Not applicable on ext4 |  |
| Unicode-normalization pair (NFC and NFD names) | canonical paths and order agree with Python | Not measured |  |
| Event-stream overflow (`kFSEventStreamEventFlagMustScanSubDirs`) | a reset or a scoped invalidation, never silent loss | Not measured |  |
| Observer failure mapping (`Failed` with complete coverage to `ready` and stale) | revoke access to a watched directory mid-session | Unexercised |  |
| Permission-denied directory, as a non-root user | Python reports it empty and complete; fdu reports `inaccessible` partial coverage, which the host may show as scanning forever | Not testable as root |  |
| Served root through a symlink (`/tmp` to `/private/tmp`) | issue and dirty paths stay root-relative | Not applicable |  |
| Budget admission order | `test_provider_budget_stop_is_explicit_and_absence_remains_unknown` | readdir order |  |
| `watch_mode="poll"` | typed refusal at open | Typed refusal |  |

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
