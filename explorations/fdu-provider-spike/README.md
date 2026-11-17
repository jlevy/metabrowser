# fdu Provider Spike Against the Current Contract

**Status:** Measured on Linux (2026-11-17). macOS validation is pending; its commands
and empty result slots are in [macOS Validation](#macos-validation).

This experiment asks whether fdu 0.6.0 (`4450be7`) can back Metabrowser’s complete
inventory-provider contract as it stands after Checkpoint 2B, and what Python versus fdu
costs through the real server path.
It is the successor to the [Checkpoint 2A spike](../fdu-inventory-adapter/README.md),
which measured fdu `0583a1a` against the contract before 2B and is a frozen record.

The adapter here is spike code, not the production provider.
It answers every contract item fdu has a native projection for in one coherent native
read, and answers the rest with the Python reference oracle over a temporary flat image,
counting every such fallback under the fdu addition that would remove it.
It never walks the filesystem in Python, shells out to the fdu command, keeps an image
across native versions, or fabricates a value; a semantic fdu cannot express is a typed
`InventoryContractError`.

## Answer

fdu can back the contract’s lifecycle, identity, coherent reads, version pins, paging,
change delivery, refresh, and close today: 17 of the 22 provider-parametrized cases pass
unchanged against the installed wheel, an eighteenth passes once the hardcoded provider
name is masked, and the remaining four are fdu’s soft tree work budget (two cases) and
two tests that assume Python’s behavior (which files a budget admits, and replay
capacity as a maximum).
It cannot yet back five of the nine query kinds natively (filtered tree, grouped tree,
rollup, navigation, recent), and its Python binding costs 10 to 14 µs per returned row,
which makes even the natively answered catalog and directory pages slower than the
Python provider’s retained store.

Performance splits the same way.
fdu’s engine settles 3.5 to 5.4 times faster than the Python store, the server’s cold
discovery is 2.3 to 4 times faster, and mutation to SSE is 20 to 25 ms sooner.
Everything that crosses a temporary fallback is slower, by 8 times for navigation up to
over 100 times for a rollup at a fresh version, costs 1.4 to 2.1 times the RSS, and
cannot answer while discovery is moving the version, so a browser sees its first folder
counts later on every corpus measured even though fdu finishes discovery first.
The numbers are in [Performance](#performance), the fdu work they justify in
[Required fdu Changes](#required-fdu-changes), and the Metabrowser seams in
[Required Metabrowser Refactors](#required-metabrowser-refactors).

## Reproduce

Revisions measured:

- Metabrowser: `db08e3b8` plus this directory (the working tree was later checkpointed
  as `9637b122`; `evidence/correctness.json` records the head and dirty paths it ran on)
- fdu: `4450be7`, version 0.6.0
- Wheel: `fdu-0.6.0-cp312-abi3-manylinux_2_34_x86_64.whl`, SHA-256
  `d4b9071b377be9201ad95dedaebc19328e0a255cd76dc072fe5fa0cc91fdac1f`
- Toolchain: rustc and cargo 1.97.1 (from fdu’s `rust-toolchain.toml`), maturin 1.14.1
  (fdu’s locked dev group), uv 0.11.32, CPython 3.13.18

The wheel is build output that rerunning one command recreates, so it lives outside both
repositories. Build it with fdu’s locked maturin path, the one its Makefile and CI use:

```shell
cd <fdu-checkout>/crates/fdu-py          # checked out at 4450be7
uv run --frozen --only-group dev maturin build --locked --release --out <artifact-dir>
```

fdu’s Makefile asks for uv 0.12.1 (`UV_MIN_VERSION`); the build above ran with uv
0.11.32 directly, outside the Make preflight, and parsed fdu’s relative `exclude-newer`
without complaint. The manylinux tag is `2_34` because the wheel was built against this
host’s glibc, not in fdu’s release container.
A rebuild of the same revision produced a different digest: every member, the native
extension included, is byte-identical except maturin’s embedded CycloneDX SBOM (a random
serial number and a timestamp) and the `RECORD` that hashes it.
The digest above therefore identifies this artifact, not the revision; compare members,
not the archive, when reproducing it.

From the Metabrowser checkout:

```shell
WHEEL=<artifact-dir>/fdu-0.6.0-cp312-abi3-manylinux_2_34_x86_64.whl
export PYTHONPATH=src:tests:explorations/fdu-provider-spike
UV="uv --config-file uv.toml run --frozen --with $WHEEL python"

# Correctness: conformance, File Rollup corpus, routes, lifecycle -> evidence/correctness.json
$UV explorations/fdu-provider-spike/run.py --wheel "$WHEEL"

# Timed series (about 25 minutes on 4 vCPU) -> .bench/fdu-spike/, then the summary
WHEEL=$WHEEL explorations/fdu-provider-spike/series.sh
$UV explorations/fdu-provider-spike/summarize.py

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
`.bench/corpus-checkout` as a copy of this checkout made with
`tar --exclude=./.bench -cf - . | tar -xf - -C .bench/corpus-checkout`, so live-change
markers never touch the real working tree.

Following [Durable Storage](../performance-loop/README.md#durable-storage), the
normalized evidence and every script it cites are in this directory, and raw bench
output and corpora are in `.bench/`, which rerunning recreates.

## Files

| File | Role |
| --- | --- |
| `adapter.py` | `FduInventoryBackend` and `FduInventoryHandle`, the spike provider |
| `probe.py` | Fallback and native counters; `FALLBACK_REMEDIES` names the fdu addition behind each fallback |
| `conformance.py` | Runs every provider-parametrized contract case against Python and fdu |
| `rollup_corpus.py` | The File Rollup conformance corpus through fdu’s native classifier |
| `routes.py` | Route, lifecycle, and SSE suites with fdu injected at the runtime composition root |
| `run.py` | Correctness harness, root-cause classification, normalized `evidence/correctness.json` |
| `launcher.py` | Spike-only `metab` entry point; `METABROWSER_INVENTORY_PROVIDER=fdu` selects the spike |
| `bench.py` | Paired serving runs: `synthetic` (unchanged `bench_serving`), `tree`, and `floor` |
| `projections.py` | Per-projection read latency at fresh versions, and fdu’s per-row binding cost |
| `discovery.py` | Open to first answer per projection kind while discovery runs |
| `series.sh` | The timed series; it ran as `STAGES=synthetic`, then `tree floor projections discovery` after a harness fix to tree-response parsing, then `floor` again after a fix to the observed-phase wait |
| `summarize.py` | Paired medians, A/A bands, and verdicts into `evidence/performance.json` |
| `evidence/` | Normalized correctness and performance evidence |

The seam research the lead gathered for this spike is in
[research-inputs/metabrowser-seam.md](research-inputs/metabrowser-seam.md) and
[research-inputs/fdu-api-and-gaps.md](research-inputs/fdu-api-and-gaps.md); its findings
were checked against code before they are repeated here.

## Adapter Design

Selection is a spike-only seam: `launcher.py` and `routes.py` replace the runtime
composition root’s `create_inventory_backend` reference in one process.
Nothing under `src/` changes, and the shipping sealed factory still rejects `fdu`.

### Native

| Contract item | fdu mapping |
| --- | --- |
| Checkpoint read | `OpenedIndex.state()`; a `Diagnostics()` follow-up at the same version only when the state carries issues |
| `EntryQuery` | `Lookup`, with `Knowledge` present, absent, or unknown mapped one to one |
| `DirectoryQuery` | `Tree(depth, include_ignored, Page)` and `Continue`; fdu’s level order, directory-first canonical byte order, and opaque single-use continuations already match the contract |
| `CatalogQuery` | `Flat` with an `EntrySelection` (file kind, `exclude_ignored`, terminal suffixes, ancestor names, `max_size = size_less_than - 1`) plus `Aggregate` for the capped count |
| `DiagnosticsQuery` | `Diagnostics` and a root `Lookup` for directory counts |
| Version pins | `read(expected=...)`; a moved version raises `VersionUnavailableError` |
| State vocabulary | fdu’s phase, coverage reason, freshness, source, and issue kinds carry Metabrowser’s exact value spellings |
| Work counters | fdu’s `Work` has the same thirteen fields as `WorkCounters` |
| `changes()` | `changes(cursor, timeout=0.25)` on one dedicated poll thread; reset, all-dirty, and dirty paths from the native impact |
| `refresh()` and `prioritize()` | Native, with the receipt’s terminal version |
| `close()` | Native close on the poll thread, then the thread joins |
| Registry identity | fdu parses the registry text and derives `type_rules_fingerprint` from what it parsed |

### Translated

Each translation is exact unless marked; the counted ones appear in the probe.

- **Identity:** session `fdu:<hex>`; scope fingerprint from Metabrowser’s
  `inventory_scope_fingerprint`; semantic fingerprint is the canonical-pair SHA-256 of
  fdu’s three native semantic identities, checked unchanged on every response.
- **Directory facts:** directory `mtime_ns` and `newest_mtime_ns` are the newest
  descendant file’s modification time, or 0, as the Python store sets them; aggregates
  are reported only at complete coverage (fdu exposes no per-subtree completeness, so
  the adapter reports `None` rather than partial counts as final).
- **`empty`:** fdu’s rollup counts files only, so a directory with no files is probed
  for symlink leaves with a bounded `Tree` read at the same version
  (`directory_empty_probe`).
- **Extensions:** fdu’s `NameClassification.logical_extension`; checked against
  `derive_ext` on every converted row in the correctness run (0 mismatches in 20,399).
- **Backslash identity** (`backslash_identity`): fdu’s portable path escapes `%` and
  undecodable bytes exactly as Metabrowser does but keeps a POSIX backslash, which
  Metabrowser escapes as `%5C`; identity translates exactly, order does not (finding
  F2).
- **Page bound** (`page_chaining`): fdu refuses pages above 4,096 rows; Metabrowser asks
  for up to `budget.max_files` rows per catalog page, so larger pages are chained at one
  pinned version.
- **Read bound** (`projection_chunking`): fdu refuses more than 16 projections per read;
  the coordinator bundles one `EntryQuery` per dirty path, so larger bundles are chunked
  at one pinned version.
  Before this fix a 17-path reread failed (an adapter bug).
- **Priority bound** (`priority_chunking`): fdu refuses more than 64 priority paths.
- **Catalog continuation count** (`catalog_offset_ledger`): a continued page reuses the
  first page’s count from a handle-local ledger and raises the lower bound by rows
  already emitted, as the Python oracle does from its memo; recounting would rescan the
  whole selection under the page’s work bound.
- **Continuation identity:** the same bounded ledger refuses a continuation resubmitted
  with a different path, depth, or filter, which fdu’s `Continue` cannot check.
- **Journal capacity:** fdu budgets bytes with a 64 KiB floor; the adapter maps
  `change_queue_size` to `max(64 KiB, 4 KiB × batches)`, which has no exact meaning.
- **Issues:** paths made root-relative and canonical; fdu retains at most 64 issues, and
  an omitted count is summarized in the last retained record.
- **Watch facts:** `watch_mode`, `watch_state`, and `watch_reason` derived from phase
  and coverage, including `off`/`resource_budget` after a budget stop.
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
version reuses the image, mirroring the Python provider’s per-revision memos; any
version change discards it.
Work over the limit is a typed `QueryLimitProjection` before anything is materialized.

On the live checkout (read only, so its counts move with the working tree), one bundled
read of all nine kinds materialized 10,482 rows and 490,521 path bytes once, then reused
the image for the other four fallbacks; it rebuilt 520 child buckets for the rollup and
made one full-result sort each for the filtered tree and recent.
The per-fallback counters are in `evidence/correctness.json` under
`representative_read.probe`.

### Not Possible Without fdu Changes

- A hard `max_work` limit on directory pages (fdu’s tree budget is deliberately soft).
- Replay capacity expressed in batches (fdu budgets bytes).
- A polling observer (`watch_mode="poll"`).
- Canonical row order for names containing a backslash.
- A schema-5 registry without the down-level shim.
- Progressive directory aggregates for completed subtrees during discovery.

## Correctness

### Provider Conformance

Every factory-parametrized case in `tests/test_inventory_provider_contract.py`, the 21
registered cases plus the unregistered age-band case.
Python passes all 22.

| Test | Python | fdu | Class | Root cause |
| --- | --- | --- | --- | --- |
| `test_provider_semantic_digest` | pass | fail | d | Asserts `diagnostics.provider == "python"`; with that masked every fact, order, aggregate, filter, rollup, navigation, recent, and catalog value matches |
| `test_provider_applies_work_bounds_to_continuation_pages` | pass | fail | b | Directory half: fdu’s soft tree budget returns rows, not a typed limit, and consumes the single-use continuation; catalog and filtered-tree halves match Python’s exact work |
| `test_provider_returns_typed_query_limits_without_partial_answers` | pass | fail | b | Same soft budget for the directory query; the other five kinds limit at `rows_visited=2` |
| `test_provider_budget_stop_is_explicit_and_absence_remains_unknown` | pass | fail | c | Assumes the two-file budget admits `a.txt` and `b.txt` (Python’s sorted admission); the contract does not order admission within a directory, and fdu’s admitted pair differs; stop, coverage, issue, and watch facts all match |
| `test_provider_changes_resume_and_report_history_gaps_as_reset` | pass | fail | c | Requires a gap at capacity one; fdu’s 64 KiB journal floor keeps both commits replayable |
| The other 17 cases | pass | pass |  |  |

The File Rollup conformance corpus through fdu’s native classifier: 153 of 153 metadata
cases agree on logical extension, canonical extension, kind, family, group, and content
family (fdu does not expose `confidence` or `detection_source`); 20 of 21 invalid
registries are refused, the exception being the schema-4 case, which fdu reads by
design. The two aggregate cases need a breakdown projection fdu lacks.

### Routes, Lifecycle, and SSE

With fdu injected, the 2A selection passes 16 of 17 and the inventory route suites from
the
[provider plan](../../docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md)
pass 161 of 168; without injection Python passes all 168. The recursive-removal
coalescing test 2A recorded as a failure passes in the recorded run but is intermittent
for both providers: with observation on, the live observer and the test’s explicit
refresh both verify one removal, and whether that lands in one provider batch or two is
timing, against an assertion of exactly one envelope.
Repeated on this host it failed 5 of 32 runs with Python and 9 of 32 with fdu (class c);
that difference is not resolved at this count.

| Test | fdu | Class | Root cause |
| --- | --- | --- | --- |
| `test_api_tree_uses_pending_inventory_without_filesystem_fallback` | fail | d | Monkeypatches `python_inventory.walk_tree` to hold discovery |
| `test_root_directory_envelope_and_pending_state` | fail | d | Same |
| `test_api_catalog_is_incomplete_while_discovery_is_blocked` | fail | d | Same |
| `test_walker_completion_projects_capability_update` | fail | d | Same |
| `test_api_index_progress_does_not_304_while_active` | fail | d | Same |
| `test_tree_dump_honors_inventory_provider_selection` | fail | d | Asserts the sealed factory rejects an unknown name, which the spike’s injection bypasses |
| `test_watcher_detects_new_file_after_walker_completes` | fail | b | `watch_mode="poll"`; fdu has no polling observer, refused as a typed error |
| `test_rollup_payload_and_etag_share_one_version` | fail | c | A refresh is three native commits (freshness to reconciling, insert, verified to fresh); the receipt names the last, but the host relay can still be publishing an earlier one when `refresh()` returns |

The lifecycle probe opened through `InventoryCoordinator`, reached `watching`, delivered
a live file creation in about 50 ms with the file coherent on reread, refreshed,
replaced the root, joined an iterator-only cancellation in about 200 ms (the 250 ms
poll), left the handle usable, and closed concurrently twice with no surviving poll
thread.

## Performance

All timings are from one Linux VM: kernel 6.18.44, x86_64, 4 vCPU, 15.7 GiB RAM, CPython
3.13.18, running as root with a warm page cache; the 1-minute load was 0.3 to 1.0 when
each series started.
They are evidence about this regime only.
Every server run is a fresh `metab` process started through the same launcher shim and
interpreter for both providers.
Each trial runs four arms in rotated order (python A, fdu A, python B, fdu B). The A/A
band is the B/A ratio of one provider within a trial; the paired ratio is fdu over
Python for the same arm letter.
An effect is called only when every paired ratio falls outside both providers’ A/A
bands, the [accept rule](../performance-loop/README.md#the-accept-rule)’s range test.
Every table row below cleared it unless it says “noise”.
Medians are over n samples per provider; the full distributions, bands, and verdicts are
in `evidence/performance.json`.

The provider sources were frozen before timing (adapter SHA-256 `c19ea02d…`). The final
adapter differs only by two state translations that no timed path reaches (transient
`ready` with observation on, and observer failure) plus formatting, and it reproduces
every correctness result above.

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

Each engine alone in a fresh process, four samples, observation off unless stated.

| Corpus | Python store, open to settled | fdu, open to settled | fdu observed: `open()` returns | discovered | watching |
| --- | ---: | ---: | ---: | ---: | ---: |
| Checkout copy | 0.50 s | 0.14 s | 0.19 s | 0.28 s | 0.32 s |
| Synthetic 100k | 3.94 s | 0.72 s | 0.29 s | 0.97 s | 1.32 s |
| `project-10` | 7.49 s | 1.42 s | 1.45 s | 2.94 s | 4.43 s |

fdu’s engine is 3.5 to 5.4 times faster to settle.
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

### Real Trees

Two trials, n = 4 per provider; route latencies are p50 at a fresh version, eight rounds
on the checkout and five on `project-10`. Each round writes a marker file, waits for its
SSE record, then requests each route.

| Metric | Checkout: Python | fdu | `project-10`: Python | fdu |
| --- | ---: | ---: | ---: | ---: |
| Discovery (walker’s own record) | 616 ms | 262 ms | 10,683 ms | 2,958 ms |
| Server start to first useful `/api/tree` | 0.82 s | 1.28 s | 2.06 s | 8.61 s (noise) |
| Server start to settled | 1.39 s | 1.28 s | 12.8 s | 8.71 s |
| Mutation to SSE, p50 and p95 | 79, 100 ms | 54, 55 ms | 74, 84 ms | 54, 55 ms (p95 noise) |
| Navigation | 34 ms | 279 ms | 444 ms | 4,381 ms |
| `/api/tree` root depth 1, depth 2 | 2.3, 6.8 ms | 3.0, 13.1 ms | 2.0, 3.0 ms | 2.9, 5.1 ms |
| `/api/tree` largest subfolder depth 2 | 9.5 ms | 17.7 ms | 20.0 ms | 43.4 ms |
| Filtered tree (`.md`, depth 3) | 24 ms | 25 ms (noise) | 304 ms | 338 ms (noise) |
| Grouped tree (type, depth 2) | 20 ms | 23 ms (noise) | 187 ms | 241 ms |
| Rollup overview, treemap | 3.6, 7.7 ms | 21.6, 11.9 ms | 4.1, 17.6 ms | 458, 90 ms |
| Recent | 30 ms | 34 ms (noise) | 221 ms | 286 ms (noise) |
| Catalog | 9.8 ms | 50 ms | 219 ms | 1,503 ms |
| Settled RSS, sampled peak | 82, 92 MB | 119, 131 MB | 246, 287 MB | 377, 480 MB |
| Process CPU over the whole run | 3 s | 6 s | 23.5 s | 56 s |

Navigation is the first route each round, so with the per-version image memo it pays the
fallback image for the routes after it; the filtered, grouped, recent, and treemap
numbers are the oracle alone over a reused image.
One of four fdu runs on `project-10` answered `/api/tree` during discovery at 2.19 s;
the other three waited for settle, which is why that row’s band is wide.

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

Every fallback costs about the same at a given size because each pays the full image:
fdu’s Python binding converts native rows at 10.8 to 14.2 µs per row (`FULL` shape) and
9.8 to 13.2 µs (`COMPACT`), and the adapter’s conversion into the oracle’s record adds
5.0 µs. On `project-10` that is 2.1 s of binding and 0.74 s of conversion before any
projection work. Python’s rollup is nearly free because its subtree aggregates survive a
one-file change; the oracle over a fresh image rebuilds them.
The natively answered kinds are slower than Python only by the binding’s per-row cost.

### During Discovery

`discovery.py` opens a fresh handle per sample and reads one kind in a loop from the
moment `open` returns.
Native kinds (entry, directory) answer in about 8 ms for fdu and 6 ms for Python.
For the fallbacks, any image larger than one native page needs several reads pinned to
one version, and fdu retains only the current version while discovery commits move it.
On the synthetic tree, three trials raised `VersionUnavailableError` 206 times for the
rollup and 98 for navigation after 626 and 298 internal retries; the rollup’s median
first answer was 2,335 ms against Python’s 5.5 ms.
A read can only succeed early by racing ahead of discovery while the tree is still one
page, which is what happened on `project-10`’s in-process samples, and is not what a
browser attached to the server sees (8.6 s above).

## Required fdu Changes

Ordered by what they unblock, each with the evidence above.

1. **Native projections for the five fallback kinds.** Filtered tree, grouped tree, the
   File Rollup breakdown, navigation, and ranked recent are 8 to 2,800 times slower
   through the temporary fallback, cost 1.4 to 2.1 times the settled RSS and 2 to 5.4
   times the CPU, and cannot answer during discovery.
   The maintained structures already exist in fdu’s serving indexes (semantic type
   tallies, exact-name tallies, global recency order); the readers do not.
   Recent and age filters must read modification time (`TimeBasis.MODIFIED`), since
   fdu’s default clock is change time.
2. **A cheaper binding row path.** At 10 to 14 µs per row, conversion in `fdu.opened` (a
   dataclass tree and a `Path` per row) makes a 10,000-row catalog page 8 times Python’s
   on the checkout and a 100k catalog body 4.8 times; it is also what every fallback
   image pays. A lean row shape (portable path, kind, size, mtime, ignored,
   classification ids, and directory totals as plain tuples or columns) would remove
   most of it.
3. **Registry schema 5 (F1).** fdu 0.6.0 refuses Metabrowser’s registry at open
   (`unknown family field "chroma_ratio"`). The only addition is presentation, which
   fdu’s fingerprint already excludes; the spike’s down-level shim proves nothing else
   differs (153 of 153 classification cases agree).
4. **One escape rule for a POSIX backslash (F2).** fdu keeps the backslash byte in a
   portable path, where Metabrowser escapes it as `%5C`. Identity translates exactly,
   but fdu’s directory and catalog order then differs from the contract’s canonical byte
   order (`identity_and_bounds` in the evidence).
5. **Version retention across a bounded multi-page read, or larger bounds.** fdu holds
   only the current version, 4,096 rows per page, and 16 projections per read; a catalog
   page of `budget.max_files` rows, a fallback image, or a coordinator reread of 17
   dirty paths needs several reads at one version, and during discovery or churn the
   version moves between them (the discovery counts above).
   Either retain a short window of recent versions for `expected`, or raise the bounds
   to Metabrowser’s (`MAX_QUERIES_PER_READ` and `MAX_COMMAND_PATHS` are 1,024; priority
   is capped at 64).
6. **A hard work limit on tree pages, or a decision that the contract’s is soft.** fdu’s
   tree budget is soft by design, so the two work-limit conformance cases fail and a
   limited continuation is consumed rather than kept for retry.
7. **Leaf counts and subtree completeness in directory rows.** The rollup counts files
   only, so `empty` for a file-less directory needs a probe; and with only
   `children_complete`, the adapter cannot report progressive totals for finished
   subtrees during discovery.
8. **Lifecycle shape with observation on.** fdu passes through a transient `ready`
   before its pre-watch reconcile, and reports observer failure as terminal `failed`;
   the adapter translates both exactly, but the native vocabulary should say what the
   contract means.
9. **A polling observer, or an explicit decision not to have one.** `watch_mode="poll"`
   is refused.
10. **A reproducible wheel.** Two builds of the same revision differ only in maturin’s
    embedded CycloneDX SBOM (random serial number and timestamp) and the `RECORD` that
    hashes it, so a pinned wheel digest cannot be re-derived by rebuilding.

## Required Metabrowser Refactors

Each is evidence that the current seam pins Python behavior rather than the contract.

1. **A provider-owned discovery barrier for tests.** Six route tests (and the 2A one
   still) monkeypatch `python_inventory.walk_tree` or the sealed factory, so they cannot
   run against any other provider.
   A scripted discovery or observation source owned by the provider would make them
   provider-neutral, as 2A also recommended.
2. **Conformance cases that pin Python specifics.** The semantic digest asserts the
   provider name; the budget case asserts which files a sorted walker admits; the replay
   case treats capacity as a maximum to forget beyond.
   State capacity as a minimum a provider retains, assert budget invariants rather than
   names, and compare digests modulo provider identity.
3. **`refresh()` should return after the host relay has published the receipt’s
   version,** or the contract should say sub-batches are visible.
   A native refresh is three commits, and
   `test_rollup_payload_and_etag_share_one_version` observes an intermediate one.
4. **Page sizes chosen for an in-memory Python store.** Catalog pages of
   `budget.max_files` rows and one `EntryQuery` per dirty path both assume a provider
   with no per-row binding cost or request bounds.
   A provider page-size hint honored by host assembly, and facts carried in change
   batches (the seam research’s `mb-l2eh`), would remove the chaining and chunking
   translations.
5. **Root-summary bundling in `/api/tree`.** The tree route reads navigation tallies
   with every page, so a provider that answers directory pages natively still cannot
   show the first rows until its navigation projection answers.
6. **Factory registration and packaging** as Checkpoint 2C lists: an explicit `fdu`
   choice, an optional exact wheel, a typed startup failure, and `bench_serving`’s
   provider list and synthetic-only tree paths generalized; this spike reached all of
   them through a launcher instead.
7. **Permission-denied semantics, to verify as a non-root user.** The seam research
   found the Python provider reports an unreadable directory as empty and complete; fdu
   reports `inaccessible` partial coverage, which the host may treat as never settling.
   Root cannot exercise this; it is a [macOS validation](#macos-validation) slot.

## macOS Validation

Everything above is Linux evidence: inotify, ext4-style readdir order, and a process
running as root, which reads mode-000 files and so cannot exercise permission failures.
The pull request is validated on macOS (arm64) separately.
Rebuild the wheel there and rerun the same harnesses; the wheel’s name and digest will
differ, so pass both to `run.py`, which still refuses any other wheel.

```shell
# fdu, detached at 4450be7, with the toolchain from rust-toolchain.toml
cd <fdu-checkout>/crates/fdu-py
uv run --frozen --only-group dev maturin build --locked --release --out <artifact-dir>
shasum -a 256 <artifact-dir>/fdu-0.6.0-cp312-abi3-macosx_11_0_arm64.whl

# Metabrowser checkout
WHEEL=<artifact-dir>/fdu-0.6.0-cp312-abi3-macosx_11_0_arm64.whl
export PYTHONPATH=src:tests:explorations/fdu-provider-spike
UV="uv --config-file uv.toml run --frozen --with $WHEEL python"
$UV explorations/fdu-provider-spike/run.py --wheel "$WHEEL" \
  --expect-wheel-name "$(basename "$WHEEL")" --expect-wheel-sha256 <digest-from-shasum> \
  --output explorations/fdu-provider-spike/evidence/correctness-macos.json
WHEEL=$WHEEL explorations/fdu-provider-spike/series.sh
$UV explorations/fdu-provider-spike/discovery.py --corpus .bench/corpus-synthetic-100000 \
  --label synthetic-100000
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
| Rename within the root (paired) and out of the root (unpaired) | `EffectiveChange` kinds and `InvalidateReason.UNPAIRED_RENAME` | Not measured |  |
| Case-only rename on case-insensitive APFS (`a.txt` to `A.txt`) | identity, order, and one removal plus one insertion | Not applicable on ext4 |  |
| Unicode-normalization pair (NFC and NFD names) | canonical paths and order agree with Python | Not measured |  |
| Event-stream overflow (`kFSEventStreamEventFlagMustScanSubDirs`) | a reset or a scoped invalidation, never silent loss | Not measured |  |
| Observer failure mapping (`Failed` with complete coverage to `ready` and stale) | revoke access to a watched directory mid-session | Unexercised |  |
| Permission-denied directory, as a non-root user | Python reports it empty and complete; fdu reports `inaccessible` partial coverage, which the host may show as scanning forever | Not testable as root |  |
| Served root through a symlink (`/tmp` to `/private/tmp`) | issue and dirty paths stay root-relative | Not applicable |  |
| `watch_mode="poll"` | typed refusal at open | Typed refusal |  |

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
