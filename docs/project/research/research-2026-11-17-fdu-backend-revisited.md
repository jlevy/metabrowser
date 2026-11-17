# Research: fdu as the Inventory Backend, Revisited on fdu 0.6

**Date:** 2026-11-17

**Author:** Metabrowser maintainers with Claude Code research assistance

**Status:** Complete for Linux; macOS validation is pending (`mb-6xfh`). Each decision
below is marked decided, when it is Metabrowser’s alone, or open pending fdu, when it
needs fdu’s agreement.

## Overview

Metabrowser plans to serve its filesystem inventory from fdu, the Rust disk-usage and
inventory engine, while keeping the Python implementation as an equivalent reference
provider. The two should be swappable by configuration so that every product suite, and
the standing performance harness, can run against either one.

The [August research](research-2026-08-23-fdu-metabrowser-inventory-engine.md) chose the
boundary: a Metabrowser-owned, stateful inventory engine, not a walker.
[Phase 1 and Checkpoint 2B](../specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md)
shipped that boundary with the Python provider behind it, and the Checkpoint 2A spike
measured a disposable fdu adapter against fdu `0583a1a`. Checkpoints 2C and 2D, the
native projections and the production adapter, never started.
Since then both projects moved: fdu released 0.1.0 through 0.6.0 with a public
opened-root API, and Metabrowser added grouped trees, total path escaping, registry
schema 5, repository subjects, the macOS app, and a performance campaign that gates its
walker hypotheses on a Python-versus-fdu reading (U3, `mb-wb7e`).

This research re-derives the integration against the code as it stands on both sides,
runs a new spike on Linux against fdu 0.6.0, and states the fdu changes and Metabrowser
refactors that a clean swap needs.
macOS validation is left as an explicit follow-up with its own procedure.

The short answer: the boundary is still right and fdu’s lifecycle core fits it nearly
one to one, but the swap is not yet clean on either side.
Metabrowser’s contract and conformance tests still encode Python implementation choices,
two of its projections return browser wire models, and the Python provider hides
semantic decisions (unreadable directories, ignore-rule scope, watch scope) that an
honest native provider exposes.
fdu answers three of the nine query kinds natively, refuses Metabrowser’s current
registry at open, escapes paths differently, and its opened route is materially slower
than its one-shot headline numbers.
None of these is a reason to change the boundary; each is a named, bounded change.
Several of them touch decisions fdu has recorded, so they are proposed to fdu as joint
decisions rather than as work items.

## Questions to Answer

1. Does the provider boundary from August still fit both codebases as they are today?
2. What exactly must an fdu-backed provider implement, and which of those items does fdu
   0.6.0 already provide?
3. Where does the current contract, its conformance registry, or its consumers encode
   the Python implementation rather than product semantics?
4. Which fdu changes are required, in what order, and what evidence justifies each?
5. Which Metabrowser refactors make the two providers cleanly swappable, including
   selection, packaging, the macOS app, tests, and the CLI?
6. How should performance be compared before and after, and what would hide a real
   engine gain?
7. What does a Linux spike against fdu 0.6.0 show, and what remains to validate on
   macOS?

## Scope

“The backend” here means the authority for filesystem structure and metadata: discovery,
the retained index, directory totals, File Rollup classification and breakdowns, recent
files, the Quick File catalog, navigation tallies, refresh, and live changes.
That authority sits behind `InventoryHandle`, so a Rust implementation of it is a
complete second backend for everything the browser learns about the served tree.

File contents, Git objects and history, pull-request data, plugin routes, HTTP, SSE, and
browser state stay in Python above the seam.
Git pins already have their own provider-less index (`coordinator.open_subject`) and are
outside fdu’s scope.

This document covers Linux measurements only.
macOS results, including FSEvents behavior, are a required follow-up described in
[macOS Validation](#macos-validation).

## Findings

### The Boundary Holds, and fdu’s Lifecycle Core Matches It

Metabrowser’s seam is narrow: a backend `open` and five async handle methods (`read`,
`changes`, `refresh`, `prioritize`, `close`; the protocols close `contract.py`), a
closed algebra of nine query kinds, and a bounded invalidation stream.
Every inventory consumer crosses `InventoryCoordinator`;
`tests/test_inventory_provider_ownership.py` enforces that only the factory imports the
concrete provider.

fdu 0.6.0’s opened root (`fdu.opened.OpenedIndex`, Rust `fdu_core::opened`) exposes the
same five operations, and its value vocabularies were aligned with Metabrowser’s in
Checkpoint 2B:

| Concern | fdu 0.6.0 | Fit |
| --- | --- | --- |
| Open | Returns while discovery continues; scope options for hidden allowlist, symlinks, filesystem boundary, special objects, and a regular-file budget | Native |
| Coherent read | One version per bundle; exact version pins; opaque one-shot continuations that survive typed limits | Native, with tip-only retention |
| Lifecycle | Same phase, coverage, freshness, source, and issue values | Native, except observer failure (below) |
| Changes | Clocked journal; trust and state transitions are commits; explicit reset | Native, with different granularity |
| Refresh | Full path accounting, typed rejections, terminal version | Native |
| Close | Idempotent, shared outcome, joins workers, wakes blocked change polls | Native |
| Work counters | Field-for-field the same `WorkCounters` names | Native names, different charging |

That alignment is the payoff of August’s decision to keep fdu application-independent
while letting the contract borrow fdu’s total vocabularies.
The remaining gaps are in projections, edge semantics, and cost, not in the shape of the
handle.

### Only Three of Nine Query Kinds Map Natively

| Metabrowser query | fdu 0.6.0 projection | Status |
| --- | --- | --- |
| `EntryQuery` | `Lookup` | Native, but no leaf count for `empty` |
| `DirectoryQuery` | `Tree{depth, include_ignored, page}` | Native order and pruning; pages capped at 4,096 rows; soft work budget |
| `CatalogQuery` | `Flat` with `EntrySelection` | Native predicates and order; full scan per page, no prefix seek |
| `RecentQuery` | none (`Report` sorts everything and returns native paths) | Missing |
| `NavigationQuery` | none (maintained tallies exist, keyed by file-type ID, and unread) | Missing |
| `RollupQuery` | `RollUp` scalars only | Missing |
| `FilteredTreeQuery` | none | Missing |
| `GroupedTreeQuery` | none | Missing |
| `DiagnosticsQuery` | `Diagnostics` plus root `RollUp` | Adapter-composable |

fdu already maintains, on every commit, the serving indexes that Phase 3C approved:
recency order, per-directory type tallies, and exact-name tallies
(`crates/fdu-core/src/index.rs`, `ServingIndexes`). Only tests read them.
Every commit pays their cost (1.225 times a detached commit in fdu’s own probe) and no
projection benefits yet, so the cheapest next fdu work is to serve bounded views over
structures that already exist.
fdu’s plan routes those views through its existing report and selected-tree machinery
rather than new projection variants (`fdu-a0cf`), and the proposal below follows it.

### Two Open-Time Blockers Arrived After the Last Spike

- **Registry schema.** Metabrowser’s packaged registry is File Rollup schema 5, which
  added a presentation field, `chroma_ratio`. fdu’s parser accepts schemas 3 and 4 and
  rejects unknown fields (`crates/fdu-core/src/classify/file_rollup_manifest.rs`,
  `SCHEMA_VERSIONS`), so `OpenedOptions(type_rules=...)` fails before discovery starts.
  Removing presentation does not help: the same parser requires presentation fields,
  `hue` on every family among them, so a document stripped of them is refused as surely.
  The failure is correct fail-closed behavior; the coupling is the problem.
  A presentation-only change in Metabrowser should not require an fdu release.
- **Path identity.** Metabrowser’s canonical name escapes a POSIX backslash as `%5C`
  (`contract.py`, `canonical_inventory_name`); fdu’s portable path escapes only `%` and
  undecodable bytes (`crates/fdu-core/src/opened/read.rs`, `push_text`). A name
  containing a backslash therefore has different identity and different row order in the
  two providers. The contract’s docstring says the escaping mirrors fdu; it no longer
  does.

### The Contract Still Encodes the Python Implementation

Checkpoint 2B corrected the vocabulary, but the conformance registry
(`tests/test_inventory_provider_contract.py`, 21 registered cases) still pins Python
choices that are not product semantics.
The first four rows below are the spike’s fdu failures that are not fdu gaps; the rest
pass with fdu today but encode Python all the same:

| Assertion | What it pins | Product requirement |
| --- | --- | --- |
| Semantic digest expects provider `python` | Provider identity | The digest of filesystem facts |
| Budget stop expects the two files a sorted walker admits | Python’s admission order within a directory | A decision on truncated membership (D17) |
| Replay at `change_queue_size=1` expects a gap reset | A capacity counted in Python’s batches | Exact replay inside capacity, reset outside it (D8) |
| Typed-limit and continuation-work cases expect a hard directory limit | Python’s hard per-page budget | Progress, termination, and conservation under a soft budget (D6) |
| Budget stop expects watch state `off`, reason `resource_budget` | Python’s free-form watch strings | A typed watch state |
| Work-limit cases pin exact `rows_visited` | Python’s index-size charge for scanning queries | A bound on visited work |
| Checkpoint expects phase `watching` | Python’s watcher being available | Any settled phase |

One parametrized case,
`test_group_filters_cut_age_bands_at_their_edges_and_keep_symlinks`, is not registered,
and the registration check only verifies that registered names exist, so it cannot catch
an unregistered case.

Several rules that product tests rely on are not stated in the contract at all:

- `dirty_paths` includes every ancestor whose aggregates changed;
  `tests/test_e2e_filesystem_to_sse.py` depends on it, and what else a dirty path
  promises is undefined (D20).
- Removing a directory produces one change batch; the same suite asserts one envelope,
  and the 2A spike’s fdu adapter produced two.
- A directory’s `mtime_ns` is its newest descendant regular-file mtime; the semantic
  digest omits mtimes, so nothing pins it.
- A directory the walk has not reached answers as an empty page with no continuation;
  `/api/tree` relies on it.
- A tree with exactly `max_files` regular files reports truncated.

fdu cannot match unwritten rules, and Python cannot be held to them either.

### Two Projections Return Browser Wire Models

`RollupProjection.payload` is the browser’s `RollupResult` and
`NavigationProjection.payload` is `NavigationTallies` with untyped rows (`contract.py`;
beads `mb-gwlw` and `mb-nqgs`). Both carry a registry fingerprint computed by
Metabrowser’s own recipe (`file_type_registry._registry_fingerprint`), which the browser
compares with its taxonomy (`folder-totals.js`, `file-type-summary-model.js`). As
written, a native provider must emit Metabrowser’s wire shapes and reproduce that
fingerprint byte for byte.
The provider-neutrality test omits `metabrowser.wire_models` from its denylist because
adding it fails today.

### The Python Provider Hides Semantic Decisions

An honest native provider exposes behavior the Python provider papers over.
Each needs a product decision before parity runs mean anything:

- **Unreadable directories.** The Python walker treats a `PermissionError` or a vanished
  directory as empty, with coverage still complete (`walker.py`, scandir error path).
  No `permission` issue or `inaccessible` coverage reason is ever produced.
  The host reads only phase, `coverage.complete`, and the `resource_budget` issue, and
  it collapses state in three status helpers that disagree (`server.py`,
  `events_route.py`, `walk.py`). fdu reports partial coverage, which the host would show
  as scanning forever, and lookups under the hole answer `unknown`, which forces SSE
  resyncs.
- **Ignore-rule scope.** Python reads every `.gitignore` from the enclosing repository
  root down, including files above the served root.
  fdu reads only files at or below the opened root.
  Serving a repository subdirectory therefore yields different ignored sets.
  Neither reads `.git/info/exclude` or global excludes, which `git check-ignore` does.
  The only Git oracle (`tests/test_gitignore_hierarchical.py`) exercises the Python
  matcher directly, not a provider.
- **Live ignore edits.** Python never observes a `.gitignore` edit, because the watcher
  drops hidden names; already indexed entries are never re-flagged.
  fdu treats `.gitignore` as an observed control and reclassifies.
- **Watch scope.** Python’s watcher uses `watchfiles.DefaultFilter`, which drops
  `node_modules`, `.venv`, `__pycache__`, and similar directories that the walker
  indexes, so changes there are never seen live.
  It also drops kernel overflow and rescan signals (`mb-pn95`), never retries
  (`mb-dwo6`), and has no periodic reconciliation; `INVENTORY_REFRESH_TTL_S` is defined
  but unused. fdu observes the whole admitted scope and turns overflow into
  reconciliation.
- **Observer failure.** Metabrowser documents ready plus stale plus an `observation_gap`
  issue; fdu reports `failed` with partial freshness.
- **Remote and unknown filesystems.** Python selects polling by filesystem type
  (`watch_backends.py`: NFS, SMB, FUSE, and any unrecognized type poll), because native
  events there miss remote writes.
  fdu’s observation consults no filesystem type and has no polling backend (D21).

### fdu’s Opened Route Is Not Its Headline Engine

fdu’s published speed comes from the one-shot walker (about 0.95 s for a generated
million-entry tree on Linux, `docs/performance-measurements.md` in fdu).
The opened route, which Metabrowser would use, is a different pipeline:

- one breadth-first producer thread, not the parallel scheduler;
- one journal commit per directory, each cloned for pollers;
- on Linux with observation, `notify` walks the whole tree inside `open()` to register
  one inotify watch per directory, including pruned hidden and ignored directories;
- after discovery, one more whole-root reconciliation pass before `watching`.

fdu’s own experiments measured opened discovery at 6.5 times the one-shot wall time and
5.5 times its memory on macOS (exp-126, a 146,000-entry Metabrowser checkout), and 2.75
times on Linux before 0.3.0’s `getdents64` reader (exp-145). Against Metabrowser’s
Python baseline on an M1 Pro (100,000 files: 5.5 s attached, 174 MiB;
`docs/scale-benchmark.md`), those unpaired figures suggest fdu’s opened discovery may be
only about twice as fast on macOS, at similar memory per entry.
That is a hypothesis for the macOS run, not a result.
On Linux the [spike](#linux-spike-on-fdu-060) measured server discovery with no client
polling at 2.1 times faster than Python on its larger real tree and 1.6 times on a
checkout copy. With observation on, `open()` blocked 1.45 s on that tree and the
pre-watch pass added up to 1.5 s more.
Those overheads are still large against fdu’s own floor: 0.72 s for about 101,000
entries opened, against fdu’s published 0.95 s for a million entries one-shot, and
engine memory equal to Python’s (159 MB against 161 MB on `project-10`). The spike did
not run fdu’s one-shot index on its own corpora, so that ratio is orientation only.

### Host Costs Bound the End-to-End Gain

About 93% of the detached Python walk is Python above the filesystem
(`plan-2026-09-15-flat-tree-delivery-cost.md`), so a native engine can remove most of
that cost. With a browser attached, however, delivery costs about 14 µs per entry in the
host, independent of the provider:

- one `EntryQuery` per dirty path to rebuild SSE records (`events_route.py`);
- every change batch marks all nine query kinds dirty, including diagnostics;
- every result row is a frozen, validated dataclass (`__post_init__` path checks);
- catalog pages are `max_files` rows, 500,000 by default, sized so the Python provider
  scans once;
- the activity tracker reads a whole-index catalog every five seconds.

fdu adds its own conversion cost: the binding builds dictionaries with the GIL held and
`opened.py` rebuilds dataclasses, about ten Python objects per row (fdu bead
`fdu-1yxw`). Only the first is an uninterruptible hold; the rebuild is ordinary Python
on a worker thread (D15). A browser-attached A/B run without host changes will mostly
measure the host, not the engine.

### Packaging Is Ready; Selection Is Not

fdu 0.6.0 has been on PyPI since 2026-11-12 with `cp312-abi3` wheels for manylinux2014
x86_64 and aarch64, macOS 11 arm64 and x86_64, and Windows amd64, plus an sdist, and no
Python dependencies.
Metabrowser supports Python 3.12 and later, which those wheels cover, except CI’s
free-threaded 3.14t job, for which fdu publishes no wheel.
fdu’s opened types change across 0.x minor releases (0.6.0 broke the `RollUpSummary`
constructor), so the pin must be exact.

Selection is the gap:

- the sealed factory knows only `python`;
- `METABROWSER_INVENTORY_PROVIDER` is read from the process environment but not from
  `.env`, and no `metab` flag selects a provider;
- `devtools/bench_serving.py` lists only `python` in `INVENTORY_PROVIDERS` and detects
  discovery completion with a regular expression on a Python log line;
- `tests/inventory_harness.py`, used by 24 test modules, always builds the default
  provider;
- the macOS app launches a user-installed `metab` with an allowlisted child environment
  that drops `METABROWSER_INVENTORY_PROVIDER` (`apps/macos`, `ChildEnvironment.swift`).

### A Few Code Paths Still Bypass the Seam

| Location | Reads | Disposition |
| --- | --- | --- |
| `walk.py` text and `--stream` modes | `walker.walk_tree` directly | Route through `InventoryRuntime` (`mb-iyu7`) |
| `tree.py` `_dir_tree` family, re-exported by `server.py` | scandir walks | Dead in production; delete |
| `folder_discovery.py` README scan | Bounded scandir of direct children | Keep as a documented host exemption for folders outside the index |
| `server.py` `_folder_not_indexed` | Re-applies scope rules with the default allowlist | Use the configured scope |
| `active_tracker.py` | Catalog every 5 s, then host `stat` of candidates | By design (verified refresh hints); use `catalog_terminal_suffix` for its recheck |
| Content, safe paths, Git, caches, plugins, macOS app | Contents and stats outside the tree model | Legitimately outside the engine |

`arch-inventory-provider.md` says only `metab --walk` bypasses the contract; the list is
longer, though only the first two rows would make a provider swap non-equivalent.

## Linux Spike on fdu 0.6.0

The [spike](../../../explorations/fdu-provider-spike/README.md) built an exact fdu wheel
at `4450be7`, implemented a spike provider against the current contract, injected it
into the runtime’s composition root without changing `src/`, and ran Metabrowser’s
conformance, route, SSE, and benchmark harnesses on a 4-vCPU Linux VM. The adapter
answers every query fdu can answer in one coherent native read.
The five missing kinds fall back to the Python reference projection over a temporary
flat image of the same native version, so their answers are equal by construction and
their cost is measured, not hidden.
Independent reviews of the spike found two adapter bugs, a harness leak, a biased engine
floor, and several overstated counts; the numbers below are the corrected ones, and the
spike’s README records each correction.

### Correctness

- **Conformance:** fdu passes 17 of the 22 factory-parametrized cases unchanged; Python
  passes all 22. One failure only asserts the provider name `python`; with it masked,
  every fact, order, aggregate, filter, rollup, navigation, recent, and catalog value
  matches. Two are fdu’s soft tree work budget (D6): run half by half, the filtered-tree
  and catalog work bounds match Python’s exactly and only the directory query differs.
  Two pin Python behavior the contract does not require: which files a two-file budget
  admits within one directory (fdu admits in directory-read order; D17), and a replay
  gap at capacity one, which fdu’s 64 KiB journal floor does not produce (D8).
- **Classification:** 153 of 153 File Rollup metadata cases agree with fdu’s native
  classifier on logical extension, canonical extension, kind, family, group, and content
  family, and no logical extension differed across the 20,385 rows the representative
  read converted. Of 21 invalid registries, converted through the same schema shim, fdu
  refuses 18 for the case’s own defect, refuses one for a different reason, and accepts
  two: a previous schema version, which it reads by design, and an undeclared
  `chroma_ratio` deviation, which the shim strips before fdu sees it.
  The registry handshake, not classification semantics, is what blocks parity (D9).
- **Routes and SSE:** of 168 inventory route tests, 85 actually build an fdu backend and
  pass with it, and 7 fail; the other 76 pass without exercising fdu.
  Four failures monkeypatch `python_inventory.walk_tree` to hold discovery (one test in
  the 2A selection does too), one asserts the factory rejects unknown names (bypassed by
  the injection), and one uses `watch_mode="poll"`, which fdu cannot serve (D21). The
  last, the rollup validator test, fails with fdu in two ways: `refresh()` returns the
  receipt’s version before the host relay has published it (R27), and the fallback can
  serve a body from before the refresh.
- **Granularity is visible to the host:** in 32 fresh runs per provider, a test that
  touches a file and waits for its change passed 32 times with Python and 12 times with
  fdu. fdu’s refresh is several commits, the first of which changes only state (fresh to
  reconciling), and the host publishes it as its own envelope before the data change
  (D8). The recursive-removal test passed 32 of 32 for both providers once an adapter
  bug that marked paths dirty from state-only commits was fixed (D8, R2).
- **Lifecycle:** open through the coordinator, `watching`, a live creation delivered in
  about 50 ms and coherent on reread, refresh, root replacement, iterator-only
  cancellation joined in about 200 ms (within the adapter’s own 250 ms poll timeout),
  and a concurrent double close with no surviving poll thread.

### Performance

Four rotated arms per trial (Python A, fdu A, Python B, fdu B). A metric’s A/A band is
the range of both providers’ B/A ratios within a trial, and an effect is reported only
when every paired ratio falls outside it.
The bands come from two or three trials and differ widely by metric, from 0.995–1.044
for `project-10`’s settle time to 0.26–1.04 for its first useful read, so each server
row states its own; the engine, first-answer, and per-row runs have no A/A arm and give
ranges. Effects under 2 times at four runs per side are provisional.
Linux VM, root, warm cache.
The timed series ran an adapter from before the review’s fixes, and the exact timed
versions of two scripts were not committed; the spike’s README gives the details and
every distribution.

| Layer | Measurement | Python | fdu | Spread |
| --- | --- | ---: | ---: | --- |
| Engine | Open to settled, observation off, checkout copy (10,475 entries); the Python arm polled its handle every 2 ms | 0.50 s | 0.14 s | 4 samples: 0.49–0.51, 0.14–0.18 s |
| Engine | The same, synthetic 100k (101,105 entries) | 3.94 s | 0.72 s | 3.84–4.08, 0.68–0.76 s |
| Engine | The same, `project-10` (148,441 entries) | 7.49 s | 1.42 s | 7.39–7.52, 1.36–1.50 s |
| Engine | fdu observed, `project-10`: `open()` returns, discovered, watching |  | 1.45, 2.94, 4.43 s | 1.34–1.48, 2.87–3.00, 4.41–4.68 s |
| Server | Discovery with no client polling, `project-10` | 5.51 s | 2.57 s | 3 runs: 5.50–5.77, 2.53–2.69 s |
| Server | Discovery with no client polling, checkout copy | 362 ms | 222 ms | 3 runs: 346–372, 217–242 ms |
| Server | Discovery with nothing attached after the readiness probe, synthetic 100k | 4,108 ms | 1,040 ms | A/A 0.87–1.24 |
| Server | Discovery with a client polling the rollup until settled, `project-10` | 10,683 ms | 2,958 ms | A/A 0.94–1.03 |
| Server | Start to the first rollup reporting done, `project-10` (fallback) | 12.8 s | 8.71 s | A/A 0.995–1.044, provisional |
| Server | First depth-1 `/api/tree` after the socket accepts, `project-10` (native) | 1.63 s | 1.68 s | 3 runs: 1.61–1.64, 1.67–1.83 s |
| Server | First root `/api/tree` with tallies, `project-10` (fallback) | 1.63 s | 7.46 s | 3 runs: 1.61–1.64, 1.75–7.64 s |
| Server | First rollup overview, `project-10` (fallback) | 1.63 s | 7.68 s | 3 runs: 1.61–1.64, 7.20–7.75 s |
| Server | First nonzero folder count on the wire, synthetic 100k (fallback) | 0.92 s | 4.58 s | A/A 0.78–1.12 |
| Server | Rollup at a fresh version, synthetic 100k (fallback) | 21 ms | 2,748 ms | A/A 0.94–1.18 |
| Server | Navigation, `project-10` (fallback) | 444 ms | 4,381 ms | A/A 0.93–1.01 |
| Server | Catalog, `project-10` (native) | 219 ms | 1,503 ms | A/A 0.75–1.03 |
| Server | Mutation to SSE, p50, checkout copy and `project-10` | 79, 74 ms | 54, 54 ms | A/A 1.00–1.03 and 0.90–1.01, provisional |
| Server | Peak RSS by settle, synthetic 100k (fallback image memo on) | 175 MB | 376 MB | A/A 0.83–1.01 |

Four results explain the table:

1. **Discovery is 1.6 to 4 times faster with no client polling, and the engine ratio is
   biased upward.** With no client polling, server discovery takes 5.51 s with Python
   and 2.57 s with fdu on `project-10` (2.1 times), 362 and 222 ms on the checkout copy
   (1.6 times), and 4,108 and 1,040 ms on the synthetic tree (4 times).
   Only fdu’s arms saw any request during discovery in these runs, a fallback request
   left waiting or the benchmark’s startup probe, because every Python route answered at
   once, so the ratios are if anything conservative.
   A client polling the rollup roughly doubles Python’s discovery (10.68 s on
   `project-10`) and adds about 15% to fdu’s (2.96 s), because request work competes
   with Python’s walker for the interpreter.
   The engine floor’s 3.5 to 5.4 times comes from a Python arm that read its handle
   every 2 ms while it discovered, so the same competition biases it upward
   (`explorations/fdu-provider-spike/bench.py`, the engine-floor script).
   With observation on, `open()` blocks 1.45 s on `project-10` while inotify watches
   register, and the pre-watch pass adds up to 1.5 s before `watching`: the cost F15
   targets. The server’s settled time (12.8 against 8.71 s) is the first rollup that
   reports done, a fallback that D12 removes from the product, so it does not describe
   the configuration that ships.
2. **Native rows cost about 13 to 18 µs each to reach the host, mostly in Python.**
   Repeated five times over full-index reads, the native read itself costs 3.5 to 4.2 µs
   per row, including the PyO3 object building that holds the GIL; `fdu.opened`’s
   dataclass rebuild costs 5.6 to 9.6 µs, and the adapter’s conversion into contract
   records 3.5 to 3.9 µs, both preemptible Python.
   Directory pages are slower than the Python store by that per-row cost.
   The catalog is also bound by its selection: fdu scans every entry for the page and
   again for the count, 36.5 ms against Python’s 5.1 ms on the checkout copy, though the
   two are equal (164 against 169 ms) on the synthetic tree.
3. **Native kinds answer as early as Python; fallbacks cannot answer during discovery.**
   The first depth-1 tree arrived with Python’s on both real trees.
   Any fallback image larger than one native page needs several reads pinned to one
   version, fdu retains only the current version, and discovery commits once per
   directory, so the first tallies, rollup, and folder counts arrived 1.8 to 5 times
   later than with Python.
   The timed adapter also raised `VersionUnavailableError` for unpinned reads, which the
   contract reserves for pinned ones, and `/api/rollup` logged it unhandled three to six
   times per `project-10` run; the fixed adapter logged none.
   An assembly can still exhaust its bounded attempts with any provider whose version
   moves, which R31 maps.
4. **Live delivery reflects debounce windows, not engines.** fdu’s 54 ms matches its 50
   ms settle window; Python’s 74 to 79 ms reflects `watchfiles` batching.
   Peak memory and settled CPU (5.4 times) describe the fallback image memo, which no
   native-only arm separated.

## Key Insights

- **The engine is faster, and the configuration that ships gains less, for fixable
  reasons.** With no client polling, server discovery is 1.6 to 2.1 times faster on the
  real trees and 4 times on the synthetic tree; a polling client doubles Python’s
  discovery and adds about 15% to fdu’s. With observation on, watch registration inside
  `open()` and the pre-watch pass add about 3 s on `project-10` before `watching` (F15).
  The rest of what loses sits between the engine and the browser: missing projections,
  per-row conversion in Python on both sides of the binding, and host per-row costs.
  Adoption therefore depends on prompt open, native projections, and a cheap row path,
  not on more discovery speed.
- **Bounded native projections also fix interaction during discovery.** A rollup
  overview, a navigation tally, or a recent page is small and answers in one read, so it
  needs no retained version; the native depth-1 tree already answers as early as
  Python’s. Complete assemblies of path-keyed rows under moving versions still need
  D13’s rule, because D11’s 4,096-row pages make the catalog and large trees multi-page,
  and that rule needs fdu to resume positions across versions (F26). Selected trees
  avoid the problem by never paging (D7).
- **Classification parity already holds.** With a classification profile fdu can parse
  (D9), the File Rollup corpus and real trees agree exactly, so the shared-taxonomy work
  of August paid off.
- **The contract is nearly neutral, but its host is not.** Seventeen of twenty-two cases
  pass unchanged; the five failures are the provider-name assertion, the soft tree
  budget twice (D6), budget admission order (D17), and replay capacity (D8). The host,
  however, publishes a transient state-only batch as its own envelope and reads results
  right after `refresh()`, which fdu’s finer commits expose (D8, R27).
- **Opening is not prompt on Linux with observation.** `notify` registers recursive
  inotify watches inside `open()`: 1.45 s on `project-10` before Metabrowser gets a
  handle, against the contract’s promise that opening never waits for discovery.

## Design for a Cleanly Swappable Backend

### Principles

1. **The contract states product semantics; conformance asserts semantics and bounds.**
   A conformance case may pin a filesystem fact, an order, a bound, or a state
   transition. It may not pin a provider name, a free-form string, a batch granularity,
   or an exact work charge.
2. **Adapter work is bounded by output size, never by index size.** The production fdu
   adapter translates values, owns the async bridge, and may compose bounded fdu
   results, for example a rollup from ranked children plus tallies.
   It never pages the whole index into Python, retains a mirror, reclassifies names, or
   walks the filesystem.
3. **Aggregates cross the seam as contract-owned types.** Providers return typed
   tallies, ranked children, and totals; the host builds the browser’s `RollupResult`
   and navigation rows and stamps the registry identity it derives itself.
4. **The engine receives classification, not presentation.** A display-only registry
   change must not require an fdu release; the File Rollup Format’s classification
   profile says which fields an engine reads (D9).
5. **A semantic difference is decided once and implemented in both providers.** Where
   the Python provider is wrong or silent (unreadable directories, watch scope, live
   ignore edits), the decision changes Python in the same change that states it.
6. **Bounds are shared constants, not negotiated capabilities.** Page rows, projections
   per read, lookup batch size, work per page, and prioritize paths are fixed in the
   contract at values both providers meet, each set from a measurement recorded beside
   its constant, and the adapter asserts fdu’s exported bounds against them at open.
   The host assembles larger responses from bounded pages.

### Decisions Needed Before Parity Runs

A decision marked **decided** is Metabrowser’s alone and can be recorded now.
One marked **open, pending fdu** changes fdu’s behavior or contradicts a decision fdu
has recorded, so its recommendation is Metabrowser’s proposal until fdu agrees.

| # | Question | Status | Recommendation | Changes |
| --- | --- | --- | --- | --- |
| D1 | How are unreadable or vanished directories reported? | Decided | Honest partial coverage with `inaccessible` and a bounded `permission` or `disappeared` issue. The host gets one status helper that distinguishes “complete with issues” from “still discovering”; lookups under a known hole answer `absent` for the hole’s subtree only after subtree completeness exists (F6) | Python walker, host status helpers, fdu F6 |
| D2 | Which ignore rules apply when serving a repository subdirectory? | Open, pending fdu | Keep Python’s rule (every `.gitignore` from the enclosing repository root down), which matches Git for in-tree files, and give fdu caller-supplied ancestor rules: the caller passes each `.gitignore` above the root, anchored at its base, and owns watching it (F21). Decide `.git/info/exclude`, global excludes, and `core.ignorecase` together in the same decision; neither provider reads the first two today, and fdu’s matcher deliberately reads neither and matches case-sensitively | fdu F21, provider-level Git oracle (R8) |
| D3 | Are `.gitignore` edits observed live? | Decided | Yes, in both providers; an edit reclassifies its subtree as one verified change | Python watcher and refresh |
| D4 | What does the watcher observe? | Decided | Exactly the admitted scope. Remove `DefaultFilter`’s blind spots, turn overflow into scoped reconciliation, and retry or degrade explicitly | Python watcher (`mb-pn95`, `mb-dwo6`) |
| D5 | What state follows an observer failure? | Open, pending fdu | `ready` plus `stale` plus `observation_gap`: the data is complete as of its version, only freshness is lost. Inotify watch-limit failure at open degrades the same way instead of failing open. This changes fdu’s lifecycle mapping, which reports `failed` | fdu F3, adapter |
| D6 | Is the per-page tree work budget hard or soft? | Open, pending fdu | Soft, as fdu records it: a page spends its budget, stops at the first position its continuation can name, reports the work it spent, and emits at least one row or ends the traversal. Conformance asserts progress, termination, and conservation (assembled pages equal the unpaged answer), never a ceiling, and the host records reported work as an observation (`fdu-3v0d`). Python’s directory query, which returns a typed limit with no rows today, adopts the same rule. A hard ceiling is the alternative, and needs fdu to finish `fdu-pokc` | Contract text, Python provider, conformance, page assembly |
| D7 | Do filtered and grouped trees page? | Open, pending fdu | No. A filtered or grouped tree is one complete-or-limit read at one version: the whole selected tree within its row and work bounds, or a typed limit. Version movement restarts it and never splices it. This is fdu’s recorded design, and Metabrowser’s routes already accumulate every page before responding, so paging never bounded their output. fdu answers up to the contract’s eight groups in one pass (F13) | Contract (selected trees stop paging), Python provider, tree assembly, fdu F13 |
| D8 | What is replay capacity measured in, and how fine is a batch? | Decided | Capacity is a provider budget; a cursor inside it replays exactly, outside it resets. A batch is one coherent provider version, and a provider may commit state-only batches. A transient freshness transition is not its own envelope: the coordinator holds a batch whose freshness is `reconciling`, with every batch after it, until freshness settles or a bounded hold expires, then publishes them as one host change at the latest version, whether a refresh or the provider’s own watcher caused them. No version may expose a half-removed subtree, and tests assert convergence rather than envelope counts. R27’s wait for the relay fails fast if the relay is dead or has reset | Contract text, coordinator, conformance, `tests/test_e2e_filesystem_to_sse.py` |
| D9 | How does the engine receive the registry? | Intent decided; profile open, pending fdu | The engine receives classification, not presentation, so a display-only change needs no engine release. Stripping presentation does not achieve that, because fdu’s parser requires presentation fields. The File Rollup Format defines a classification profile, the fields an engine reads, with presentation fields optional and skipped when present, decided jointly with fdu (F1). Metabrowser passes that profile, providers derive semantic identity from what they parse, and the host stamps the browser’s registry fingerprint | File Rollup Format, registry export (R9), both providers, rollup and navigation routes, fdu F1 |
| D10 | Which canonical path grammar wins? | Open, pending fdu | Metabrowser’s total grammar, including `%5C`; it is the more portable one | fdu F2, a breaking change to fdu’s public grammar and order |
| D11 | What are the shared bounds? | Method decided | Every paired bound named once in the contract: rows per page (fdu 4,096), lookups per batch (1,024, F5), projections per read (fdu 16), work per page (fdu refuses more than 1,000,000), dirty paths per batch (fdu 256, contract 1,024), issues and issue bytes (fdu 64 and 512, contract 1,024 and 4,096), retained continuations (fdu 128), and priority paths per request, which the contract lowers to fdu’s 64: its one caller passes one path, and fdu replaces the priority set on each call, so chunking a longer list keeps only the last chunk. Each value is set from a measurement of both providers, including the native hold (D15), not adopted from fdu, and page sizes stay provisional until measured after the row-cost work (R20, F14). Broad queries that would exceed the work bound are answered from maintained structures or resume through continuations; routes do not scale the limit past what a provider accepts | Contract constants, page assembly, catalog and pending-tally routes, fdu F5 and F24 |
| D12 | How may fdu be exercised before every projection is native? | Decided | The `src/` adapter is thin from its first commit. A query kind fdu cannot answer returns, in that projection’s position, a typed unsupported result naming the kind, so native companions in the same read still answer; a route that needs it answers a typed error. A checked-in expected-unsupported list names those kinds; it may only shrink, and CI fails on drift either way. `--inventory-provider fdu` is marked experimental in `CHANGELOG.md`, and no fdu goldens are recorded until every kind is native. Fallbacks over the Python oracle live outside `src/`, in a maintained measurement harness injected at the composition root as the spike does. The adoption gate requires every kind native | Contract result type, adapter, routes, harness, CI report, `CHANGELOG.md` |
| D13 | How does a complete assembly stay equal to one version while the version moves? | Open, pending fdu | For row sets keyed by path alone (directory pages and the catalog), a continuation names a position in the query’s total order, not a version (F26). The coordinator keeps a dirty ledger per read session, fed by its relay. Before an assembly finishes, it waits until the relay has published its last read’s version (R27’s mechanism, so paging depends on host consistency), re-reads every ledger path through batched lookups, applies D20’s rules, and repeats with any paths dirtied since, until a pass finds none; totals come from that last pass. A reset or all-dirty batch restarts the assembly, and after a bounded number of passes it answers R31’s outcome, 503 with a retry hint. An assembly that finishes at one version needs no re-read, as Python’s per-version page memo does, so both providers satisfy the rule. The answer is labeled provisional while the phase is `discovering` (coverage reason `building`), not whenever coverage is partial, so an unreadable directory or a budget stop never keeps it provisional. A property test pins it: an assembly under churn equals a single-version read, with the re-read path driven by the test-only wrapper provider (R12). Selected trees, whose totals depend on the selection and cannot be repaired by lookups, follow D7. Retained versions (F22) remain only a fallback, since they contradict fdu’s non-goal of retaining historical index images | Contract paging rule, coordinator ledger, page assembly, both providers, fdu F26 |
| D14 | What happens when the native engine panics or poisons its root? | Decided | The adapter translates `pyo3_runtime.PanicException` (a `BaseException`, which the relay’s `except Exception` misses) and poisoned-root errors into a typed provider failure. Recovery runs in a coordinator supervisor task, not in the relay, because reopening from inside the relay would cancel and await the relay itself. The supervisor closes the failed handle with a bounded wait (a poisoned root may never join), reopens the root up to a capped number of attempts, publishes a host reset, and past the cap leaves the root in a typed failed state. Fault seams in the test-only wrapper provider (R12) and in fdu (F18) exercise each step | Adapter, coordinator supervisor (R26, `mb-6o0l`), wrapper provider, fdu F18 |
| D15 | What concurrency and latency budget applies at the seam? | Decided | Two bounds, measured separately and stated in the contract. The uninterruptible native hold is the part of a native call that holds the GIL with no bytecode boundary, today PyO3 building wire objects inside the native read: at most the 3.5 to 4.2 µs per row that read costs in all, about 17 ms for a 4,096-row page. Event-loop lag also counts preemptible Python on worker threads, `fdu.opened`’s dataclass rebuild and the adapter’s conversion (about 9 to 13.5 µs per row). Page sizes follow from both. F14 must keep the native hold bounded as it moves conversion into native code, by building in chunks or capping the page. `open`, `close`, and root replacement have latency bounds under the coordinator lock, and an iterator cancellation does not wait out a poll interval | Contract bounds, fdu F7, F14, F15, F25 |
| D16 | What memory may a provider use? | Decided | A settled-memory budget in bytes per retained entry, with the fdu process no larger than Python’s on the same corpus, measured as steady state after settle rather than the high-water mark | Measurement harness, fdu F17 |
| D17 | Which files does a budget stop admit? | Decided | Unspecified: truncated membership depends on directory read order, which differs across filesystems, and fdu’s plan likewise declines to guarantee a retained prefix under a budget. Conformance and goldens assert the stop, coverage, issue, and counts, never which files were admitted | Conformance, goldens |
| D18 | What does a lookup or refresh spelled differently from a served name answer? | Open, pending fdu | Only the byte-exact served name is identity. A lookup or refresh whose path differs from a served name only in letter case or Unicode normalization answers `absent` or is rejected, the same in both providers. A refresh verifies each path’s spelling against its parent’s listing before admitting it, so on a case-insensitive volume a wrong-case refresh cannot create an alias entry. Ignore matching follows D2’s `core.ignorecase` decision | Contract text, both providers, fdu F27, macOS cases |
| D19 | How do fdu and Metabrowser evolve once released separately? | Decided | Metabrowser pins fdu exactly; every pin change lands in one commit with the adapter and the conformance results. The adapter uses only the public `fdu.opened` surface and fdu’s exported bounds | Packaging, adapter |
| D20 | What does a change batch’s dirty-path set promise? | Open, pending fdu | A batch names every path whose row may differ between the version before it and its own: each inserted, updated, removed, or reclassified entry, and every ancestor whose aggregates changed. Any row fact that can change (presence, kind, size, times, ignored state, classification, aggregates, completeness) dirties its row. Removal alone is named by its root, in a separate bounded removed-subtrees field, and a consumer drops what it holds under each removed root before re-reading the point paths. A change a batch cannot express this way (a subtree invalidated pending reconciliation, a set over the path bound) is all-dirty | Contract `ChangeBatch`, both providers, coordinator merge, SSE projection, conformance, fdu F7 |
| D21 | How is a root on a remote or unknown filesystem observed? | Open, pending fdu | Native events are never trusted there. Recommended: fdu detects such a root (F28), and the adapter reports it `ready` plus `stale` plus `observation_gap`, D5’s mapping, with refresh driven by the host until fdu has a polling backend (F20). The alternative makes F20 adoption-gating and polls, as Python does | fdu F28 and F20, adapter, host refresh |
| D22 | What shape do aggregate values take at the seam? | Open, pending fdu | Contract-owned values that fdu’s report views can produce without Metabrowser vocabulary: classification tallies (key, files, bytes, newest time) per dimension, ranked children with a remainder aggregate, exact-or-capped totals, and recency-window counts with oldest and newest times. The host builds `RollupResult` and navigation rows from them and stamps the registry identity (R3) | Contract types, both providers, host shaping, fdu F9 to F12 |

D7, D12, and D13 are the deliberate departures from the current plan.
D12 keeps August’s rule that the production adapter never materializes the index: the
spike measured fallbacks at 8 to over 100 times the Python provider’s latency, unable to
answer during discovery, and doubling peak memory.
It moves the fallbacks, which still earn their place for discovery, live-change, and
macOS measurements, into a harness outside the shipped package, where conformance cannot
mistake Python code answering through fdu for fdu’s answer.
D13 replaces the rule that an assembly may never mix pages from two versions, for row
sets keyed by path, with a rule that yields an answer equal to one version, because fdu
retains only its current version and commits once per directory during discovery.
D7 keeps the stricter rule for selected trees by never paging them, since their
directory totals cannot be repaired path by path.

D20 chooses a removed-subtrees field over treating a re-created directory as all-dirty.
Python names only a removed directory, fdu names every removed entry and goes all-dirty
past 256, and the host’s merge (`coordinator.py`, `_merge_provider_batches`) keeps each
path once, so a directory removed and re-created across merged batches looks merely
updated and its removed descendants survive.
With removals applied first and every re-read at the final version, a merge becomes a
plain union with no order to keep.
All-dirty would answer re-creation correctly, but re-creation is routine in development
trees (build outputs, dependency reinstalls, branch switches), and all-dirty there turns
each one into an assembly restart and an SSE resync at the sizes where both cost most.

### Required fdu Changes

Grouped by what each group unblocks, in the order the spike’s measurements support.
Sizes: S is a small pull request, M several days, L a week or more.
Names stay generic; no Metabrowser vocabulary enters fdu.
Where an item reverses a decision fdu has recorded, it says so and names the joint
decision behind it. fdu’s bead `fdu-a0cf` already plans recent, navigation, and
selected-tree readers over its report and tree machinery and rejects new projection
variants, so F9 through F13 ask for properties of those planned views, not new variants.

**Open-time** (lets the thin adapter open and answer its native kinds without shims):

| # | Change | Size | Evidence | fdu |
| --- | --- | --- | --- | --- |
| F1 | Accept a File Rollup classification profile: a registry document whose presentation fields are optional and skipped when present, at schema 3, 4, or 5, with the File Rollup Format naming the presentation fields (D9) | S–M | The parser requires `hue` on every family and refuses unknown fields such as schema 5’s `chroma_ratio`, so neither the packaged registry nor a document stripped of presentation opens; the spike needed a schema-4 shim |  |
| F3 | Observation degrades instead of failing: a watcher setup error at open (including inotify `ENOSPC`) and an observer failure after discovery both yield `ready`, `stale`, and an issue, with no transient `ready` before the pre-watch reconcile. Changes fdu’s lifecycle mapping (D5) | S–M | The adapter had to remap a transient `ready` to `reconciling` and `failed` to `ready` |  |
| F5 | Batched lookups: one projection carries up to 1,024 paths | S | A 17-path SSE reread exceeded the 16-projection bound until the adapter chunked it |  |
| F6 | Two maintained per-directory facts beside `RollUpSummary`: descendant leaves that are neither files nor directories, and descendant directories whose child set is not yet complete | M | Without the first, the adapter probes each file-less directory for symlinks; without the second, it withholds every aggregate until the whole root is complete |  |
| F19 | Vendor and run the File Rollup conformance packet, exposing detection source and confidence on `NameClassification` or agreeing that the packet treats them as optional | S | The spike’s run is the template; the packet asserts source and confidence, which fdu lacks | `fdu-ekga` |
| F24 | Export the opened-root bounds (page rows, projections, work, dirty paths, issues, continuations, priority paths) from `fdu.opened` | S | The spike hardcodes them; D11 asserts them at open |  |
| F26 | Resumable positions across versions: a continuation’s structural position resumes at the current version, or `Tree` and `Flat` accept an explicit start-after position, and the page reports the version it read; a position whose path has since been removed resumes at the next position in the total order. Reverses fdu’s stale-continuation rule (D13) | M | `opened/read.rs` returns `ContinuationStale` for any moved version, and discovery commits once per directory, so a 148,441-entry assembly at 4,096 rows per page, 37 reads, never sees one version |  |

**First answers** (remove the fallbacks that delay first folder counts):

| # | Change | Size | Evidence | fdu |
| --- | --- | --- | --- | --- |
| F10 | Classification breakdowns as properties of the type and extension report views once they read maintained tallies: output-bounded work, keyed by the classifier’s logical extension and exact name rather than the raw extension. A logical-extension key is a new maintained structure, which fdu’s plan admits only with new measurement and a plan amendment | M | Navigation fallback 4,381 ms against Python’s 444 ms on `project-10` | `fdu-a0cf` |
| F12 | Ranked children as a property of the per-directory roll-up view: bounded directory nodes by bytes or files with exact-or-capped remainder aggregates | M | Rollup fallback 2,748 ms against 21 ms at a fresh version; first folder count 4.58 s against 0.92 s | `fdu-a0cf` |
| F14 | A cheap row path: an identity row shape built directly as tuples or columns, without intermediate dictionaries and dataclasses, that keeps the uninterruptible GIL hold bounded by building in chunks or capping the page (D15) | M | `fdu.opened` rebuilds each row as dataclasses at 5.6 to 9.6 µs, on top of a 3.5 to 4.2 µs native read, so native directory pages are slower than the Python store; moving the rebuild into native code unchunked would lengthen the hold | `fdu-1yxw` |
| F15 | Prompt open, stated as an invariant: `open()` returns without waiting for watch registration, and `watching` follows the end of discovery by a bounded verification rather than a whole-root pass. One route is non-recursive watches registered by discovery for admitted directories only; it must still watch each directory before listing it, the ordering fdu’s observation-before-discovery handoff relies on | L, likely | `open()` blocked 1.45 s on `project-10` while notify registered recursive watches, including pruned directories, and the coordinator awaits `open` under its lock during root replacement; the pre-watch pass added up to 1.5 s | `fdu-eru0` |

**Complete the algebra:**

| # | Change | Size | Evidence | fdu |
| --- | --- | --- | --- | --- |
| F7 | Bounded change polls: impact-only detail, a commit bound per poll, exact changed paths separate from ancestors, file-to-non-file kind transitions, and a removed subtree reported by its root rather than one path per entry (D20) | S–M | A poll clones every retained commit, up to the 8 MiB default journal, and converts it with the GIL held; a removal of more than 256 entries is all-dirty |  |
| F8 | Selection predicates: kind, family, and group IDs; an `under` prefix with a range seek; nanosecond time windows | S | Type filters, recent prefix, and catalog pages without a full pass; today a catalog page scans every entry twice, for the page and its count (36.5 ms against Python’s 5.1 ms on the checkout copy) |  |
| F9 | Recent as a property of the recent report view once it reads the maintained recency order: output-bounded work, portable paths, ignored entries ranked last as fdu’s plan already specifies, and an exact-or-capped total | M | Recent fallback 4,945 ms against 114 ms in process on `project-10` | `fdu-a0cf` |
| F11 | Recency-window counts as a property of the age report view once it reads the maintained recency order: exact counts per window plus oldest and newest times | M | `NavigationQuery.recency_windows` | `fdu-a0cf` |
| F13 | Selected tree: one complete-or-limit read at one version with selected totals per directory, for one selection or several (up to eight) in one pass (D7) | L | Filtered and grouped tree fallbacks cost 11 to 30 times Python in process | `fdu-a0cf` |

**Cost, observation, and test support:**

| # | Change | Size | Evidence | fdu |
| --- | --- | --- | --- | --- |
| F4 | Prioritize accepts an optional depth | S | The contract’s priority request carries a depth that fdu cannot take |  |
| F16 | Opened discovery throughput: batched commits and more than one producer; `getattrlistbulk` on macOS | M–L | One commit per directory moves the version constantly during discovery; exp-126 on macOS |  |
| F17 | Price the serving indexes’ memory on large trees; their commit cost is already measured | S | Maintained on every commit and read by no projection yet; fdu’s plan records the commit cost at 1.225 times detached |  |
| F18 | Public deterministic test seams in `fdu-py`: a scripted observation source, a discovery gate, and an injected fault (a panic or poisoned root at a named operation) | M | Six route tests hold discovery by patching the Python walker, and D14’s recovery cannot be tested against fdu without a fault; fdu’s core has a scripted watch backend that `fdu-py` does not expose |  |
| F21 | Ignore rules above the opened root as caller-supplied rules: the caller passes each ancestor `.gitignore`’s text anchored at its base directory and owns watching it (D2) | M | Serving a repository subdirectory yields different ignored sets in the two providers |  |
| F22 | Retained versions for continuations: a fallback only if D13’s re-reads dominate under churn, and it contradicts fdu’s non-goal of retaining historical index images | — | Not proposed as work |  |
| F23 | Withdrawn from this list: a deterministic SBOM in the wheel is a packaging matter, filed with fdu separately | — | Two builds differed only in maturin’s embedded CycloneDX serial and timestamp |  |
| F25 | A cancellable change wait: an iterator cancels one blocked poll without closing the root, with a measured idle wakeup rate. Close already wakes every waiter | S | Iterator cancellation waited out the adapter’s own 250 ms poll timeout; the observation loop wakes every 100 ms |  |
| F27 | Case and normalization aliasing on refresh and lookup: on a case-insensitive or normalizing volume, a path spelled differently from its listed name never creates a second entry (D18) | S–M | A wrong-case refresh on such a volume can admit an alias entry, and no fdu test covers it |  |

**Adoption gates** (needed before fdu can be adopted, not before the thin adapter):

| # | Change | Size | Evidence | fdu |
| --- | --- | --- | --- | --- |
| F2 | Escape a POSIX backslash as `%5C` in portable paths; update ordering keys, goldens, and the Python parity corpus. A breaking change to fdu’s public portable-path grammar and order for every fdu user; check stored identity before proposing it (D10) | M, breaking | The spike confirmed order differs for such names |  |
| F20 | Polling observation backend, or a recorded decision that fdu rejects `poll` (D21) | M | The one `watch_mode="poll"` route test; Python polls remote and unknown filesystems |  |
| F28 | Detect a remote or unknown filesystem at open and report observation there as degraded (`ready`, stale, an issue) instead of trusting native events (D21) | S–M | Python’s `watch_backends.py` selects polling by filesystem type; fdu’s observation consults none, though its capacity code already reads the mount table |  |

The open-time group lets the thin adapter open and answer its native kinds without
shims; with the first-answers group it is the minimum for an adoption measurement.
The third finishes the query algebra.
The fourth is ordered by the paired measurements, except F17, which precedes F9 through
F12 because they build on the serving indexes.
The adoption gates decide whether fdu can become a default, not whether it can be
exercised.

### Required Metabrowser Refactors

Grouped by purpose; the first group lands with only the Python provider.

**Make the contract provider-neutral.**

- **R1:** Rewrite the conformance assertions listed above as semantics and bounds,
  register the missing grouped-tree case, and make the registration check two-way.
  Python-exact assertions move to provider-specific tests rather than being deleted.
  Replace envelope-count assertions, such as the recursive-removal and touch tests’,
  with convergence and with D8’s rule that no published version exposes a half-removed
  subtree.
- **R2:** State the implicit rules (ancestor dirtiness and the rest of D20, recursive
  removal, directory mtime, undiscovered folders, the budget edge, root counting) in the
  contract and pin each with a case, including D8’s host coalescing rule, which the
  coordinator applies opportunistically today with no stated bound.
- **R3:** Replace `RollupResult` and `NavigationTallies` in the contract with
  contract-owned aggregate types once fdu answers D22; move wire shaping and the
  registry fingerprint to the host; add `metabrowser.wire_models` to the neutrality
  denylist (`mb-gwlw`, `mb-nqgs`).
- **R4:** Replace the free-form watch strings in `ProviderDiagnostics` with a typed
  vocabulary, updating `/api/capabilities` and its goldens in the same change.
- **R5:** Apply D6, D7, D11, D13, and D20: shared bounds, a batched lookup query,
  complete-or-limit selected trees, page assembly for the catalog and directory pages
  under D13’s rule once fdu agrees, and broad queries that resume or read maintained
  structures instead of failing at the 1,000,000 work default on very large trees.
- **R6:** Apply D1 in the Python walker and merge the three host status helpers.
- **R7:** Apply D3 and D4 in the Python watcher; delete the unused
  `INVENTORY_REFRESH_TTL_S`.
- **R8:** Lift the `git check-ignore` oracle and the File Rollup conformance packet to
  provider-parametrized cases.
- **R9:** Apply D9 once its profile is agreed: export the engine-facing classification
  profile and keep registry identity in the host.
- **R27:** Make `refresh()` read-your-writes at the host: the coordinator returns a
  receipt only after its relay has published the receipt’s version, and the wait fails
  fast if the relay is dead or has reset.
  D8’s coalescing of transient freshness transitions lands with it, and D13’s dirty
  ledger waits on the same mechanism.
  The rollup validator test fails with fdu because its refresh is three commits.

**Make providers selectable and testable.** R12 and R13 land in the stack’s first layer,
before any fdu code; R10, R11, R14, and R29 land with the thin adapter in one change;
R15 waits for the composed-product checkpoint.

- **R10:** Add `fdu` to the sealed factory with a lazy import and a typed startup
  failure when the package is missing or the wrong version; no silent fallback.
- **R11:** Add `metab --inventory-provider`, keeping the environment variable, report
  the selected provider in diagnostics and `/api/capabilities`, and mark `fdu`
  experimental in `CHANGELOG.md` (D12).
- **R12:** Make `tests/inventory_harness.py` and the conformance registry select the
  provider from the environment, and replace monkeypatches of Python internals
  (`walk_tree`, `MAX_ASSEMBLED_ROWS`, `build_rollup`) with provider-owned seams: a
  discovery gate and neutral work counters.
  Add a test-only wrapper provider that perturbs any provider’s batch granularity (a
  state-only batch before its data), identity, replay capacity, relay timing, and
  faults, so the host defects fdu exposed (D8, D13, D14, R27) reproduce
  deterministically before fdu is in the build.
- **R13:** Run the golden suite per provider with one named placeholder for provider
  identity, plus one golden per provider that pins its name, and replace the
  Python-shaped `walker_task` field.
- **R14:** Package fdu as a `metabrowser[fdu]` extra with an exact pin and an
  environment marker that excludes interpreters without an fdu wheel (free-threaded
  3.14t), an `exclude-newer-package` entry, a first-party row in
  `SUPPLY-CHAIN-SECURITY.md` with every wheel digest, and installed-wheel smoke tests
  with and without the extra.
  Where fdu publishes no wheel (free-threaded CPython, musl, Windows arm64), selecting
  fdu is a typed startup failure.
- **R15:** Give the macOS app a provider preference mapped to `--inventory-provider` (an
  environment passthrough does nothing for a Finder launch), raise
  `MetabRequirement.minimumRelease` to the release with the flag, and install with the
  extra. Until then, macOS validation runs `metab` from a terminal.
- **R29:** Keep the fallback composite as a maintained measurement harness outside
  `src/` (D12), injected at the composition root, and have CI report per query kind
  whether fdu answered natively, against the expected-unsupported list.

Every R item that changes observable behavior or a wire field (R4, R6, R7, R11, R13 at
least) updates its parity registry row, the views-models-routes map, and `CHANGELOG.md`
in the same commit, and `devtools/check_parity.py` must pass.

**Measure honestly.**

- **R16:** Replace the Python log-line regular expression that the serving benchmark and
  the performance loop use to detect discovery completion with a provider-neutral
  diagnostics field.
- **R17:** Register fdu in `INVENTORY_PROVIDERS`, attest the fdu wheel beside the
  Metabrowser wheel, and add a semantic-equality precheck that compares `--api` digests
  across providers on the corpus before timing.
  A budget-stopped corpus admits different files by design (D17), so the precheck
  compares only its invariants.
- **R18:** Keep an engine-only layer (open to settled, read latencies, no server) as a
  maintained harness, from the spike’s runner, that does not poll the engine it times.
- **R30:** Re-measure the Python baseline after the neutral-contract slice, because
  watching the whole admitted scope (D4) and honest coverage (D1) change Python’s own
  cost; the “before” arm is the corrected Python provider.

**Remove host costs that would mask the engine.**

- **R19:** Carry bounded entry facts on change batches and stop marking diagnostics
  dirty on every change (`mb-l2eh`).
- **R20:** Construct provider-built rows without per-row path revalidation, and consider
  columnar catalog and recent pages; the spike adapter’s conversion into contract
  records alone cost 3.5 to 3.9 µs per row.
  Page-size constants are measured after it (D11).
- **R21:** Feed the activity tracker incrementally instead of a whole-index catalog
  every five seconds.
- **R22:** Re-measure Python-motivated host tuning (`grouped_tree_admission`, the
  cold-start wait loop, page sizes) per provider.
- **R28:** Withdrawn after measurement.
  The spike proposed unbundling navigation tallies from `/api/tree`, but its evidence
  was a harness artifact, the route bundles tallies only at root depth 0, and the native
  depth-1 tree answered as early as Python’s.
- **R31:** Give every multi-page assembly consumer one moved-version mapping: the tree,
  grouped-tree, and rollup routes (`server.py`), the catalog assembly and the SSE
  snapshot (`events_route.py`), and `metab --walk` (`walk.py`), with `--api` reaching
  the routes. An assembly that exhausts its bounded attempts, or a provider failure on an
  unpinned read, becomes one typed retryable outcome: 503 with a retry hint from a
  route, a resync on the SSE stream, and a typed error from the CLI, pinned by one
  golden. Today the tree, grouped-tree, and catalog assemblies raise
  `VersionUnavailableError` once their bounded attempts run out, and the rollup’s
  unpinned retry can raise it again.

**Close the bypasses.**

- **R23:** Route `metab --walk` text and stream modes through the runtime (`mb-iyu7`).
- **R24:** Delete the dead `tree._dir_tree` family and its re-exports; use the
  configured scope in `_folder_not_indexed`; document the README scan as a host
  exemption.
- **R25:** Move the Python walker, watcher, and ignore builder under the Python provider
  package with a reverse ownership test (`mb-ed9h`).
- **R26:** Give the change relay a recovery supervisor (D14) so a provider failure,
  including a native panic, does not end live updates until restart (`mb-6o0l`).

### The Production Adapter

`inventory_engine.providers.fdu_inventory` holds one `fdu.opened.OpenedIndex` per handle
and implements `InventoryHandle` by translation:

- open: map `InventoryConfig` to `OpenedOptions`, including the classification profile
  and `TimeBasis.MODIFIED`; derive scope and semantic identities from fdu’s `EntryScope`
  and `SemanticIdentity`;
- read: map each query to one or more fdu projections in a single pinned native read,
  translate rows and counts, and map refusals and limits to contract results;
- changes: one dedicated poll worker per handle bridging fdu’s blocking
  `changes(after, timeout)` to the async iterator, enforcing the single active iterator
  and translating impact into `ChangeBatch`, removed subtrees included (D20);
- refresh and prioritize: pass paths through and translate receipts;
- observation: on a remote or unknown filesystem, report observation as degraded (D21);
- close: stop the bridge, then close the native root, joining both;
- failure: translate a native panic or poisoned root into a typed provider failure for
  the coordinator’s supervisor (D14), and a query kind fdu cannot yet answer into that
  projection’s typed unsupported result (D12);
- bounds: assert fdu’s exported bounds (F24) against the contract’s at open (D11).

All blocking native calls run off the event loop.
The binding releases the GIL during native work and holds it, with no bytecode boundary,
while it builds wire objects: at most about 17 ms for a 4,096-row page at today’s
native-read cost. `fdu.opened`’s dataclass rebuild and the adapter’s conversion then run
as ordinary Python on the worker thread, preemptible but still competing with the event
loop for the interpreter.
Page size and F14 decide both bounds (D15). The adapter’s only state is the native
handle, the bridge, and per-read scratch; it uses only the public `fdu.opened` surface
(D19).

## Measuring Before and After

“Before” is the Python provider and “after” is fdu, both run from **one build** with the
provider as an interleaved axis.
Comparing two builds would mix the provider change with every other commit between them.

### Three Layers

| Layer | What it isolates | Harness |
| --- | --- | --- |
| Engine | Open to settled, read latency per projection, change application, memory; no server | The spike’s runner, maintained as R18 |
| Server | Cold scan unattached and attached, settled route latencies, retained bodies and validators, live change to SSE, process resources | `devtools/bench_serving.py --provider` |
| Browser | First folder counts and attached scan time as a user sees them | `make benchmark BENCHMARK_PROVIDER=<name>` and `docs/scale-benchmark.md` |

An engine win that does not appear at the server layer has been moved, not removed.
Until R19 and R20 land, expect the browser-attached layer to be dominated by host costs
that are the same for both providers; report it, but read the engine and unattached
server layers for the provider comparison.

### Procedure

1. Build once. Record the Metabrowser and fdu wheel identities and digests.
2. Run the semantic-equality precheck (R17) on each corpus; a mismatch stops the run.
   A budget-stopped corpus is compared on its invariants only (D17).
3. Run at least ten interleaved pairs per corpus with arm positions balanced, so neither
   provider always runs first, and report the paired median ratio with a bootstrap
   interval, as fdu’s `perf-compare` does.
   Use A/A pairs to measure order effects as well as noise: the spike’s A/A bands came
   from two or three trials, and several did not straddle 1.
4. Time each engine without polling it, or poll both identically and report the cadence:
   the spike’s Python engine floor read its handle every 2 ms, which competes with its
   walker.
5. Record CPU from `rusage` or `/proc` (not one-second `ps` samples), peak RSS and
   steady-state RSS after settle as separate values, event-loop lag p99, the native GIL
   hold per read and per change poll, host relay resets and SSE resyncs during
   discovery, idle CPU and wakeups after settle, thread and watch counts, and the work
   counters.
6. Detect discovery completion with the provider-neutral signal (R16), so both
   providers’ discovery times have one definition.
7. Read every route at a fresh version and in randomized order, so a fallback image or
   memo built for one route does not make the next one look free.
8. Measure fdu’s one-shot index and a plain metadata traversal on the same tree as
   floors, so each result also reads as a distance from the filesystem; the spike did
   not run this step.
9. Run as a non-root user, and include cold-cache runs, where discovery’s single
   producer thread matters most.

The corpora are the generated 100,000- and 300,000-file trees that `make benchmark`
builds, a real checkout with its dependency trees installed, one larger real tree, a
single very large directory, a deep tree, and a churn scenario (a sustained create,
modify, and remove stream plus one large burst).
Relay overflow deserves its own reading: the host relay queue holds 4,096 batches, a
tree like `project-10` has 31,901 directories, and fdu commits once per directory during
discovery, so an attached discovery may reset the host stream.
Measure the Python “before” arm again after the neutral-contract slice (R30). The
performance loop’s method, accept rule, and durable-storage rules apply
(`explorations/performance-loop/README.md`); wall-clock thresholds never gate shared CI.

## macOS Validation

The Linux spike cannot answer these; each needs a run on an Apple silicon Mac against
the same fdu revision, as a non-root user, with `metab` started from a terminal through
the spike’s launcher until R15 lands.
The [spike’s README](../../../explorations/fdu-provider-spike/README.md) has the exact
commands and the result slots.

- **Build and install:** build the wheel at the same fdu revision for arm64, or install
  the published wheel with the matching digest, and confirm Metabrowser imports it.
- **Conformance and routes:** the same provider cases and route and SSE tests as Linux.
- **Unreadable and protected directories:** permission-denied directories and
  privacy-protected folders under a home directory.
  The spike adapter withholds directory aggregates until coverage is complete, and under
  D1 one unreadable directory keeps coverage partial, so on such a tree totals never
  appear until fdu ships subtree completeness (F6). Treat F6 as a prerequisite for a
  meaningful macOS run of home-directory trees.
- **FSEvents behavior:** live create, modify, rename, and remove delivery; appends from
  a process that keeps the file open (`fdu-vhrb`); a rename burst and a large burst; a
  must-scan-subdirectories event becoming scoped reconciliation; a rename out of the
  root; and FSEvents latency against fdu’s 50 ms settle window.
- **Observer failure:** the `ready`, `stale`, and `observation_gap` mapping (D5), which
  the Linux host could not induce.
- **Roots and volumes:** a symlinked root, firmlinks and the data volume under the
  one-filesystem option, cloud placeholder files, and a network or FUSE mount (D21).
- **Time to `watching`:** FSEvents needs no per-directory registration walk, so the
  remaining cost is the final reconciliation pass; Linux’s watch-limit failure (D5) does
  not apply.
- **Discovery cost on APFS:** opened discovery wall time and memory against the one-shot
  index (the exp-126 comparison) and against the Python provider.
  There is no `getdents64` path on macOS, so the Linux discovery ratio may not transfer.
- **Case and normalization:** APFS is case-insensitive by default and Git sets
  `core.ignorecase` there; compare both providers’ ignored sets and path identity for
  names differing only in case and for decomposed Unicode names, and check that a
  wrong-case lookup answers `absent` and a wrong-case refresh creates no alias entry
  (D18, F27).
- **Budget admission:** which files a budget stop admits may differ from Linux (D17).
- **`poll` refusal:** `watch_mode="poll"` fails as a typed error, as on Linux.
- **Paired benchmark:** the 100,000- and 300,000-file `make benchmark` rows on the M1
  Pro that recorded the Python baseline, under the procedure above.
- **The app:** once R15 lands, open a folder in the macOS app with each provider and
  check progressive open, live changes, and memory.

## Options Considered

### Adopt: Neutral Contract, Then Native Projections Behind a Thin Adapter

**Description:** Make the contract provider-neutral with only Python behind it; land a
thin fdu adapter that answers natively or answers a typed unsupported result once fdu’s
open-time group releases; measure through a fallback harness outside `src/` meanwhile;
and add native projections until every kind is native.

**Advantages:**

- keeps the August boundary, which both codebases now fit;
- fixes Python bugs the neutral contract exposes, independent of fdu;
- starts the paired measurements and macOS validation early through the harness, without
  shipping index-sized work in the package;
- every step is testable with the same conformance registry, and CI shows which kinds
  are native.

**Costs:**

- a sizable fdu work list (F1 to F28), several items of which need fdu to revisit a
  recorded decision, and a Metabrowser refactor list (R1 to R31);
- measurements through the harness are slower than Python for first folder counts until
  F10, F12, and F14 land.

### Eliminated: Ship the Fallback Adapter as the Backend

The spike measured it: fallbacks are 8 to over 100 times slower, cannot answer during
discovery, and double settled memory.
The engine gain is consumed by the image rebuild on every version.

### Eliminated: Retained Versions Instead of Native Projections

Retaining old versions in fdu would let fallback images assemble during discovery, but
it leaves every fallback paying an index-sized crossing per version, about 2.6 s on
`project-10` (17.7 µs per row over 148,440 rows) before any projection work.
Bounded native projections need neither.
Retained versions remain only a fallback for complete multi-page assemblies under
version movement (F22), and they contradict fdu’s non-goal of retaining historical index
images.

### Eliminated: Host Projection Kernels Over Flat Pages

Moving all projection logic into a shared host layer over a few flat primitives would
guarantee equal answers, but it is the fallback design with better names: its cost is
proportional to the index, not the output.
The host keeps only output-bounded shaping (R3).

### Eliminated: Swap Only the Walker

Unchanged from August, and reinforced by the spike: per-row conversion into Python costs
as much as Python’s own per-entry work, so feeding fdu’s walk into the Python store
would keep both costs.

### Deferred: Native Serialization of Large Responses

Emitting a catalog page as wire bytes directly from Rust would skip both binding and
host row costs, but it puts Metabrowser’s wire format into fdu.
Revisit only if F14 and R20 together leave the catalog bound by conversion.

## Recommendations

1. Keep the provider boundary and the fdu direction.
   On Linux, server discovery with no client polling is 1.6 to 2.1 times faster on the
   real trees and 4 times on the synthetic tree, and a polling client widens the gap;
   with observation on, fdu’s `open()` blocks 1.45 s and its pre-watch pass adds up to
   1.5 s on `project-10` until F15. The engine’s 3.5 to 5.4 times with observation off
   is biased upward by its harness.
   These are Linux results from a small number of trials; macOS may differ.
2. Land the fdu-independent Metabrowser work as a stack in this order, each layer with
   only the Python provider:
   1. test and benchmark seams, with the wrapper provider and its fault seam (R12, R13,
      R16, R18), in three pull requests;
   2. the decisions record, with Metabrowser’s unilateral decisions decided and the rest
      open pending fdu, and conformance neutrality (R1, R2);
   3. host consistency: relay and refresh (R27, D8), the recovery supervisor (R26, D14),
      and one moved-version mapping for every assembly consumer (R31);
   4. honest Python semantics, which needs no fdu input and defines the baseline: R8’s
      oracles, then `--walk` through the runtime (R23), then unreadable directories with
      the status-helper merge (R6), then watch scope alone (R7);
   5. contract types: R4, then R3 once fdu answers D22, and R9 once D9’s profile is
      agreed;
   6. bounds and paging: R19 and R20 first, then R5’s bounds and batched lookup, and
      D13’s paging only after fdu agrees;
   7. R24 as its own pull request, the provider package move (R25), the remaining host
      costs (R21, R22), and then the Python re-baseline (R30).
3. Propose the fdu changes in one upstream issue: the joint decisions first (D2, D5 to
   D7, D9, D10, D13, D18, D20 to D22, and the test seams), then the open-time group (F1,
   F3, F5, F6, F19, F24, F26).
4. Land the thin adapter with its factory entry, flag, and extra in one change (D12,
   R10, R11, R14, R29) once the open-time group releases, marked experimental, and keep
   the fallback harness outside `src/` for the U3 reading and macOS validation.
5. Prioritize fdu’s rollup, navigation, row-cost, and prompt-open work (F10, F12, F14,
   F15) over the rest of the algebra, because those decide first folder counts and
   responsiveness.
6. Measure before and after with one build and an interleaved provider axis at the
   engine, unattached server, and browser layers, following the procedure above, and
   land host-cost refactors (R19 to R22) before reading the attached layer as a provider
   result.
7. Decide adoption only with every kind native, the adoption gates resolved (F2, and F20
   or F28 under D21), conformance passing on Linux and macOS, and paired results on both
   platforms; any default change stays a separate, reversible decision.

## Next Steps

- [ ] Validate this spike on macOS using its README (`mb-6xfh`; the pull request
  carrying this research leaves the checklist open).
- [ ] Record decisions D1 to D22 in the inventory-provider architecture document, each
  marked decided or open pending fdu (`mb-54tl`).
- [x] Track R1 to R31 as Metabrowser beads under `mb-hej8`, linking the existing beads
  each one absorbs; the table below maps them.
- [x] Propose the fdu changes to the fdu project in one issue: the joint decisions, F1
  to F28 in the five groups above, and the points in fdu’s opened-root plan that the
  evidence suggests revisiting, framed as questions
  ([jlevy/fdu#215](https://github.com/jlevy/fdu/issues/215)).
- [ ] Implement the thin adapter after the open-time group releases (`mb-urh5`).

| Items | Bead |
| --- | --- |
| D1 to D22 | `mb-54tl` |
| R1, R2 | `mb-7z9i` |
| R3 | `mb-gwlw`, `mb-nqgs` |
| R4 | `mb-mjfu` |
| R5 (D6, D7, D11, D13, D20) | `mb-rs6c` |
| R6 (D1) | `mb-kde1` |
| R7 (D3, D4) | `mb-s0v3`, with `mb-pn95` and `mb-dwo6` |
| R8 | `mb-8u6t` |
| R9 (D9) | `mb-qiv7` |
| R10, R11, R14 | `mb-urh5` |
| R12, R13 | `mb-x5lm` |
| R15 | `mb-e9uw` |
| R16, R18 | `mb-yp2j` |
| R17, R29 | `mb-b1v3` |
| R19 | `mb-l2eh` |
| R20 to R22 | `mb-jesj` |
| R23 | `mb-iyu7` |
| R24 | `mb-1rma` |
| R25 | `mb-ed9h` |
| R26 (D14) | `mb-quis`, with `mb-6o0l` |
| R27, with D8’s coalescing | `mb-not1`, with `mb-3p3x` |
| R30 | `mb-0658` |
| R31 | `mb-e19z` |
| F1, F3, F5, F6, F19, F24, F26 (open-time) | `mb-xd56` |
| F10, F12, F14, F15 (first answers) | `mb-sdqe` |
| F7 to F9, F11, F13 (complete the algebra) | `mb-bve2` |
| F4, F16 to F18, F21, F22, F25, F27 (cost, observation, test support) | `mb-77tq` |
| F2, F20, F28 (adoption gates) | `mb-pvc4` |

## Methodology

Three parallel investigations read the code on both sides at Metabrowser `db08e3b8` and
fdu `4450be7` (0.6.0): one of Metabrowser’s contract, coordinator, Python provider,
consumers, tests, packaging, and performance harness; one of fdu’s opened-root API in
Rust and Python, classification, watch, packaging, and performance record; and a
hands-on spike that built an exact fdu wheel and ran a spike provider through
Metabrowser’s conformance, route, and benchmark harnesses on Linux.
Their reports are kept with the spike in
`explorations/fdu-provider-spike/research-inputs/` as dated evidence; line references in
them describe those revisions.

Two rounds of independent technical review then checked this document’s claims against
both codebases, the spike’s code and evidence against its conclusions, and the fdu
proposal against decisions fdu has recorded; the
[review record](../reviews/review-2026-11-17-fdu-backend-design.md) lists every finding,
and its corrections are applied here and in the spike’s README.

Both clones were shallow, so history between September and November comes from
changelogs, plans, and beads rather than commit logs.
fdu’s unpaired performance figures come from its own experiment records and are cited as
orientation, not as Metabrowser claims.

## References

- [fdu and Metabrowser inventory-engine alignment](research-2026-08-23-fdu-metabrowser-inventory-engine.md)
- [Inventory provider refactor and fdu adoption](../specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md)
- [Pluggable inventory engine](../specs/active/plan-2026-08-23-pluggable-inventory-engine.md)
- [Inventory provider contract](../architecture/arch-inventory-provider.md)
- [Python inventory engine](../architecture/arch-inventory-engine-python.md)
- [File Rollup Format](../architecture/file-rollup-format/file-rollup-format.md)
- [Performance campaigns](../specs/active/plan-2026-11-14-performance-campaigns.md)
- [Performance architecture review](research-2026-11-14-performance-architecture-review.md)
- [fdu backend design review, two rounds](../reviews/review-2026-11-17-fdu-backend-design.md)
- [Checkpoint 2A spike](../../../explorations/fdu-inventory-adapter/README.md)
- [fdu opened-root plan](https://github.com/jlevy/fdu/blob/4450be7/docs/project/specs/active/plan-2026-08-25-fdu-opened-root-inventory-engine.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
