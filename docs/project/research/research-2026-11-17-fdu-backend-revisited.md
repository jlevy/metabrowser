# Research: fdu as the Inventory Backend, Revisited on fdu 0.6

**Date:** 2026-11-17

**Author:** Metabrowser maintainers with Claude Code research assistance

**Status:** In Progress

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
| Close | Idempotent, shared outcome, joins workers | Native |
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
| `NavigationQuery` | none (maintained tallies exist but are keyed by raw extension and unread) | Missing |
| `RollupQuery` | `RollUp` scalars only | Missing |
| `FilteredTreeQuery` | none | Missing |
| `GroupedTreeQuery` | none | Missing |
| `DiagnosticsQuery` | `Diagnostics` plus root `RollUp` | Adapter-composable |

fdu already maintains, on every commit, the serving indexes that Phase 3C approved:
recency order, per-directory type tallies, and exact-name tallies
(`crates/fdu-core/src/index.rs`, `ServingIndexes`). Only tests read them.
Every commit pays their cost and no projection benefits yet, so the cheapest next fdu
work is to expose bounded projections over structures that already exist.

### Two Open-Time Blockers Arrived After the Last Spike

- **Registry schema.** Metabrowser’s packaged registry is File Rollup schema 5, which
  added a presentation field, `chroma_ratio`. fdu’s parser accepts schemas 3 and 4 and
  rejects unknown fields (`crates/fdu-core/src/classify/file_rollup_manifest.rs`,
  `SCHEMA_VERSIONS`), so `OpenedOptions(type_rules=...)` fails before discovery starts.
  The failure is correct fail-closed behavior; the coupling is the problem.
  A presentation-only change in Metabrowser should not require an fdu release.
- **Path identity.** Metabrowser’s canonical name escapes a POSIX backslash as `%5C`
  (`contract.py`, `canonical_inventory_name`); fdu’s portable path escapes only `%` and
  undecodable bytes (`crates/fdu-core/src/opened/read.rs`, `push_text`). A name
  containing
  `\` therefore has different identity and different row order in the two providers. `contract.py`
  says the escaping mirrors fdu; it no longer does.

### The Contract Still Encodes the Python Implementation

Checkpoint 2B corrected the vocabulary, but the conformance registry
(`tests/test_inventory_provider_contract.py`, 21 registered cases) still pins Python
choices that are not product semantics:

| Assertion | What it pins | Product requirement |
| --- | --- | --- |
| Semantic digest expects provider `python` | Provider identity | The digest of filesystem facts |
| Budget stop expects watch state `off`, reason `resource_budget` | Python’s free-form watch strings | A typed watch state |
| Replay with `change_queue_size=1` expects one non-reset batch | Python’s one-commit-per-refresh granularity | Exact replay or an explicit reset |
| Work-limit cases pin exact `rows_visited` | Python’s index-size charge for scanning queries | A bound on visited work |
| Checkpoint expects phase `watching` | Python’s watcher being available | Any settled phase |

One parametrized case,
`test_group_filters_cut_age_bands_at_their_edges_and_keep_symlinks`, is not registered,
and the registration check only verifies that registered names exist, so it cannot catch
an unregistered case.

Several rules that product tests rely on are not stated in the contract at all:

- `dirty_paths` includes every ancestor whose aggregates changed;
  `tests/test_e2e_filesystem_to_sse.py` depends on it.
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
On Linux the [spike](#linux-spike-on-fdu-060) measured the current opened route at 3.5
to 5.4 times faster than the Python store to settle, so the route’s overheads cost less
there than fdu’s older experiments suggested.

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

fdu adds its own conversion cost: the binding builds dictionaries under the GIL and
`opened.py` rebuilds dataclasses, about ten Python objects per row (fdu bead
`fdu-1yxw`). A browser-attached A/B run without host changes will mostly measure the
host, not the engine.

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

### Correctness

- **Conformance:** fdu passes 17 of the 22 factory-parametrized cases unchanged; Python
  passes all 22. One failure only asserts the provider name `python`; with it masked,
  every fact, order, aggregate, filter, rollup, navigation, recent, and catalog value
  matches. Two are fdu’s soft tree work budget (D6). Two pin Python behavior the contract
  does not require: which files a two-file budget admits within one directory, and a
  replay gap at capacity one, which fdu’s 64 KiB journal floor does not produce (D8).
- **Classification:** 153 of 153 File Rollup metadata cases agree with fdu’s native
  classifier on logical extension, canonical extension, kind, family, group, and content
  family, and no logical extension differed across 20,399 converted rows.
  The registry handshake (F1), not classification semantics, is what blocks parity; the
  spike opened fdu through a labeled shim that strips `chroma_ratio` and declares schema
  4\.
- **Routes and SSE:** 161 of 168 inventory route tests pass with fdu injected (Python
  168). Five monkeypatch `python_inventory.walk_tree` to hold discovery, one asserts the
  factory rejects unknown names (bypassed by the injection), one uses
  `watch_mode="poll"` (no fdu polling observer), and one exposes a host race:
  `refresh()` returns the receipt’s version before the host relay has published it, and
  fdu’s refresh is three commits where Python’s is one.
- **A flaky Python test:** the recursive-removal test that the 2A spike recorded as an
  fdu failure is intermittent for both providers: 5 of 32 runs failed with Python and 9
  of 32 with fdu, because the live observer and the test’s own refresh can land one
  removal in one batch or two.
  The rule it asserts (exactly one envelope) is not true of the Python provider either.
- **Lifecycle:** open through the coordinator, `watching`, a live creation delivered in
  about 50 ms and coherent on reread, refresh, root replacement, iterator-only
  cancellation joined in about 200 ms, and a concurrent double close with no surviving
  poll thread.

### Performance

Four rotated arms per trial (Python A, fdu A, Python B, fdu B); an effect is reported
only when every paired ratio falls outside both providers’ A/A bands.
A/A noise was about ±33% on the synthetic series and ±11% on the real-tree series.
Linux VM, root, warm cache; the spike’s README has every distribution.

| Layer | Measurement | Python | fdu |
| --- | --- | ---: | ---: |
| Engine | Open to settled, checkout copy (10,475 entries) | 0.50 s | 0.14 s |
| Engine | Open to settled, synthetic 100k (101,105 entries) | 3.94 s | 0.72 s |
| Engine | Open to settled, `project-10` (148,441 entries) | 7.49 s | 1.42 s |
| Engine | fdu observed, `project-10`: `open()` returns, discovered, watching |  | 1.45, 2.94, 4.43 s |
| Server | Cold discovery, nothing attached, synthetic 100k | 4,108 ms | 1,040 ms |
| Server | Cold discovery, `project-10` | 10,683 ms | 2,958 ms |
| Server | Scan with a client attached, to done, synthetic 100k | 9.85 s | 4.60 s |
| Server | First nonzero folder count on the wire, synthetic 100k | 0.92 s | 4.58 s |
| Server | Start to settled, `project-10` | 12.8 s | 8.71 s |
| Server | Mutation to SSE, p50 | 74–79 ms | 54 ms |
| Server | Rollup at a fresh version, synthetic 100k (fallback) | 21 ms | 2,748 ms |
| Server | Navigation, `project-10` (fallback) | 444 ms | 4,381 ms |
| Server | Catalog, `project-10` (native) | 219 ms | 1,503 ms |
| Server | `/api/tree` largest subfolder at depth 2, `project-10` (native) | 20.0 ms | 43.4 ms |
| Server | Settled RSS, synthetic 100k | 175 MB | 376 MB |

Three results explain the table:

1. **The engine is 3.5 to 5.4 times faster to settle**, and the server’s cold discovery
   is 3.6 to 4 times faster, at about equal engine memory (161 MB Python, 159 MB fdu on
   `project-10`).
2. **Every native row costs 10 to 14 µs to cross the binding**, plus 5 µs of adapter
   conversion, so even natively answered directory and catalog reads are slower than the
   Python store, which already holds its rows as Python objects.
3. **Fallbacks cannot answer during discovery.** Any fallback image larger than one
   native page needs several reads pinned to one version, fdu retains only the current
   version, and discovery commits once per directory.
   On the synthetic tree, fallback reads raised `VersionUnavailableError` 206 times
   (rollup) after 626 internal retries, so the first folder count reached the browser 5
   times later than with Python, even though fdu finished discovery 4 times sooner.
   The fallback image also explains the 2.1 times settled RSS and 5.4 times settled CPU.

## Key Insights

- **The engine case is proven; the delivery case is not.** fdu’s engine and its live
  observation are faster on every Linux corpus measured.
  What loses today is everything between the engine and the browser: missing
  projections, per-row binding cost, and host per-row costs.
  Adoption therefore depends on native projections and a cheap row path, not on more
  engine speed.
- **Bounded native projections also fix interaction during discovery.** A rollup
  overview, a navigation tally, or a recent page is small and answers in one read, so it
  needs no retained version.
  Version retention (F22) matters only for complete multi-page assemblies, such as the
  Quick File catalog, while versions are moving.
- **Classification parity already holds.** With the registry handshake fixed, the File
  Rollup corpus and real trees agree exactly, so the shared-taxonomy work of August paid
  off.
- **The contract is nearly neutral.** Seventeen of twenty-two cases pass unchanged, and
  every remaining failure is either a test pinning Python or one of two named semantic
  decisions (D6, the polling observer).
- **Some “Python behavior” is not even true of Python.** The one-envelope removal rule
  is flaky under Python too, and the provider-level observation and permission behavior
  are untested where they matter.
  Making the contract neutral will fix Python bugs, not just admit fdu.
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
   change must not require an fdu release.
5. **A semantic difference is decided once and implemented in both providers.** Where
   the Python provider is wrong or silent (unreadable directories, watch scope, live
   ignore edits), the decision changes Python in the same change that states it.
6. **Bounds are shared constants, not negotiated capabilities.** Page rows, projections
   per read, lookup batch size, and prioritize paths are fixed in the contract at values
   both providers meet, and the host assembles larger responses from bounded pages.

### Decisions Needed Before Parity Runs

| # | Question | Recommendation | Changes |
| --- | --- | --- | --- |
| D1 | How are unreadable or vanished directories reported? | Honest partial coverage with `inaccessible` and a bounded `permission` or `disappeared` issue. The host gets one status helper that distinguishes “complete with issues” from “still discovering”; lookups under a known hole answer `absent` for the hole’s subtree only after subtree completeness exists (F6) | Python walker, host status helpers, fdu F6 |
| D2 | Which `.gitignore` files apply when serving a repository subdirectory? | Keep Python’s rule (from the enclosing repository root down), which matches Git, and add it to fdu as an explicit control base (F21). Decide `.git/info/exclude` separately; neither reads it today | fdu F21, provider-level Git oracle |
| D3 | Are `.gitignore` edits observed live? | Yes, in both providers; an edit reclassifies its subtree as one verified change | Python watcher and refresh |
| D4 | What does the watcher observe? | Exactly the admitted scope. Remove `DefaultFilter`’s blind spots, turn overflow into scoped reconciliation, and retry or degrade explicitly | Python watcher (`mb-pn95`, `mb-dwo6`) |
| D5 | What state follows an observer failure? | `ready` plus `stale` plus `observation_gap`: the data is complete as of its version, only freshness is lost. Inotify watch-limit failure at open degrades the same way instead of failing open | fdu F3 |
| D6 | Is the per-page work budget hard or soft? | A bound with a progress guarantee: a page may visit `max_work` plus the one position it must name to make progress; a query that cannot produce its first row returns the typed limit. Conformance asserts the bound, not an exact count | Contract text, conformance, fdu `fdu-pokc` |
| D7 | Do filtered and grouped trees page? | Yes; Metabrowser needs paging for large filtered trees. fdu’s plan bullet that removes paging is stale | fdu plan |
| D8 | What is replay capacity measured in, and how fine is a batch? | Capacity is a provider budget; a cursor inside it replays exactly, outside it resets. A batch is one coherent provider version. Recursive removal must not expose a half-removed subtree at any version, but the number of envelopes is not pinned | Contract text, conformance, `tests/test_e2e_filesystem_to_sse.py` |
| D9 | How does the engine receive the registry? | Metabrowser derives an engine-facing classification document from its registry and passes that; providers derive semantic identity from it; the host stamps the browser’s registry fingerprint. fdu still reads schema 5 for direct users (F1) | Registry export, both providers, rollup and navigation routes |
| D10 | Which canonical path grammar wins? | Metabrowser’s total grammar, including `%5C`; it is the more portable one | fdu F2 |
| D11 | What are the shared bounds? | 4,096 rows per page for every paged query, including catalog; a batched lookup of up to 1,024 paths; at most 16 projections per read. The host assembles complete catalog and tree responses from pages | Contract constants, page assembly, catalog and pending-tally routes, fdu F5 |
| D12 | May an experimental fdu provider ship before every projection is native? | Yes, as an explicit, non-default selection whose fallbacks are named in diagnostics, bounded by `max_work`, and deleted as native projections land. The adoption gate requires zero fallbacks | Factory, adapter, diagnostics |

D12 is the one deliberate departure from the August plan, which called the materializing
adapter unacceptable.
It remains unacceptable as the adopted provider: the spike measured fallbacks at 8 to
over 100 times the Python provider’s latency, unable to answer during discovery, and
responsible for doubling settled memory.
As an explicit experimental selection it still earns its place, because it lets the
discovery, live-change, and macOS measurements start before every fdu projection exists,
and its fallbacks reuse the Python projection code, so their answers are equal by
construction until the native replacements prove themselves against the same conformance
cases. Anyone selecting it should expect worse first folder counts than Python until F10
and F12 land.

### Required fdu Changes

Grouped by what each group unblocks, in the order the spike’s measurements support.
Sizes: S is a small pull request, M several days, L a week or more.
Names stay generic; no Metabrowser vocabulary enters fdu.

**Open, identity, and bounds** (unblock an experimental provider without shims):

| # | Change | Size | Evidence |
| --- | --- | --- | --- |
| F1 | Read File Rollup registry schema 5; accept presentation fields such as `chroma_ratio` outside the fingerprint; expose detection source and confidence on `NameClassification` | S | Open fails on Metabrowser’s registry; the spike needed a schema-4 shim. The corpus asserts source and confidence, which fdu lacks |
| F2 | Escape a POSIX backslash as `%5C` in portable paths; update ordering keys and goldens | S | The spike confirmed order differs for such names |
| F3 | Observation degrades instead of failing: a watcher setup error at open (including inotify `ENOSPC`) and an observer failure after discovery both yield `ready`, `stale`, and an issue; no transient `ready` before the pre-watch reconcile | S | D5; the adapter had to remap a transient `ready` to `reconciling` |
| F4 | Prioritize accepts 1,024 paths and an optional depth, and is inert once stopped | S | The adapter chunks at 64 and swallows the stopped error |
| F5 | Batched lookups: one projection carries up to 1,024 paths | S | A 17-path SSE reread exceeded the 16-projection bound until the adapter chunked it |
| F6 | Directory facts: non-directory leaf count (for `empty`) and subtree completeness on directory rows | S | The adapter probes for symlinks to derive `empty` and withholds aggregates until coverage is complete |
| F19 | Vendor and run the File Rollup conformance packet | S | `fdu-ekga`; the spike’s run is the template |

**What the user sees first** (removes the fallbacks that delay first folder counts):

| # | Change | Size | Evidence |
| --- | --- | --- | --- |
| F10 | Classification tallies keyed by exact name or logical extension (not raw extension), with a bounded `Tally` projection for logical extension, canonical extension, kind, family, group, and name | M | Navigation and rollup breakdowns; navigation fallback 4,381 ms against Python’s 444 ms on `project-10` |
| F12 | Ranked children: bounded directory nodes by bytes or files with remainder aggregates | M | Rollup fallback 2,748 ms against 21 ms; first folder count 4.58 s against 0.92 s |
| F14 | A cheap row path: an identity row shape built directly as tuples or columns, without intermediate dictionaries and dataclasses | M | 10 to 14 µs per row in the binding makes native directory and catalog reads 2 to 7 times slower than the Python store (`fdu-1yxw`) |
| F15 | Prompt open: register non-recursive inotify watches from discovery for admitted directories only, drop `IN_OPEN`, and scope the final reconciliation pass | M | `open()` blocked 1.45 s on `project-10`; the pre-watch pass added up to 1.5 s (`fdu-eru0`) |

**Complete the algebra:**

| # | Change | Size | Evidence |
| --- | --- | --- | --- |
| F7 | Bounded change polls: impact-only detail, a commit bound per poll, exact changed paths separate from ancestors, and file-to-non-file kind transitions | S | A poll clones every retained commit, up to 8 MiB, under the GIL |
| F8 | Selection predicates: kind, family, and group IDs; an `under` prefix with a range seek; nanosecond time windows | S | Type filters, recent prefix, and catalog scans without a full pass |
| F9 | Ranked recency page over the maintained recency index, with ignored entries demoted and an exact-or-capped total | M | Recent fallback 4,945 ms against 114 ms in process on `project-10` |
| F11 | Exact recency-window counts plus oldest and newest times | M | `NavigationQuery.recency_windows` |
| F13 | Selected tree: a level-order page with selected totals, for one selection or up to eight groups, paged | L | Filtered and grouped tree fallbacks, about 20 to 30 times Python in process |

**Cost, observation, and test support:**

| # | Change | Size | Evidence |
| --- | --- | --- | --- |
| F16 | Opened discovery throughput: batched commits and more than one producer; `getattrlistbulk` on macOS | M–L | One commit per directory moves the version constantly during discovery; exp-126 on macOS |
| F17 | Price the serving indexes’ memory and commit cost | S | Maintained on every commit and unread (`fdu-hb2t`) |
| F18 | Public deterministic test seams in `fdu-py`: a scripted observation source and a discovery gate | M | Six route tests hold discovery by patching the Python walker |
| F20 | Polling observation backend, or a recorded decision that fdu rejects `poll` | M | The one `watch_mode="poll"` route test |
| F21 | Ignore-rule control base above the opened root | M | D2 |
| F22 | Retained versions for continuations | L | Only for complete multi-page assemblies while versions move; decide after F16 and native projections |
| F23 | A deterministic SBOM in the wheel, so a rebuild is byte-identical | S | Two builds differed only in maturin’s embedded CycloneDX serial and timestamp |

The first group lets an experimental provider open without shims.
The second removes the fallbacks that make it lose first folder counts, and with the
first group it is the minimum for an adoption measurement.
The third finishes the query algebra, and the fourth is ordered by the paired
measurements.

### Required Metabrowser Refactors

Grouped by purpose; the first group lands with only the Python provider.

**Make the contract provider-neutral.**

- **R1:** Rewrite the conformance assertions listed above as semantics and bounds,
  register the missing grouped-tree case, and make the registration check two-way.
  Replace the one-envelope recursive-removal assertion, which is flaky under Python
  today, with an invariant that no published version exposes a half-removed subtree
  (D8).
- **R2:** State the implicit rules (ancestor dirtiness, recursive removal, directory
  mtime, undiscovered folders, the budget edge, root counting) in the contract and pin
  each with a case.
- **R3:** Replace `RollupResult` and `NavigationTallies` in the contract with
  contract-owned aggregate types; move wire shaping and the registry fingerprint to the
  host; add `metabrowser.wire_models` to the neutrality denylist (`mb-gwlw`, `mb-nqgs`).
- **R4:** Replace the free-form watch strings in `ProviderDiagnostics` with a typed
  vocabulary, updating `/api/capabilities` and its goldens in the same change.
- **R5:** Apply D6 and D11: shared bounds, a batched lookup query, page assembly for
  catalog and trees, and route work limits scaled to the index instead of the fixed
  1,000,000 default that makes broad queries fail on very large trees.
- **R6:** Apply D1 in the Python walker and merge the three host status helpers.
- **R7:** Apply D3 and D4 in the Python watcher; delete the unused
  `INVENTORY_REFRESH_TTL_S`.
- **R8:** Lift the `git check-ignore` oracle and the File Rollup conformance packet to
  provider-parametrized cases.
- **R9:** Apply D9: an engine-facing classification document and host-owned registry
  identity.
- **R27:** Make `refresh()` read-your-writes at the host: the coordinator returns a
  receipt only after its relay has published the receipt’s version, so a route read
  after a refresh never sees an older host version.
  The rollup validator test fails with fdu because its refresh is three commits.

**Make providers selectable and testable.**

- **R10:** Add `fdu` to the sealed factory with a lazy import and a typed startup
  failure when the package is missing or the wrong version; no silent fallback.
- **R11:** Add `metab --inventory-provider`, keeping the environment variable, and
  report the selected provider in diagnostics and `/api/capabilities`.
- **R12:** Make `tests/inventory_harness.py` and the conformance registry select the
  provider from the environment, and replace monkeypatches of Python internals
  (`walk_tree`, `MAX_ASSEMBLED_ROWS`, `build_rollup`) with provider-owned seams: a
  discovery gate and neutral work counters.
- **R13:** Make goldens provider-neutral by eliding provider identity, and replace the
  Python-shaped `walker_task` field.
- **R14:** Package fdu as a `metabrowser[fdu]` extra with an exact pin, an
  `exclude-newer-package` entry, a first-party row in `SUPPLY-CHAIN-SECURITY.md` with
  every wheel digest, and installed-wheel smoke tests with and without the extra.
  On interpreters without an fdu wheel (free-threaded 3.14t), selecting fdu is a typed
  startup failure and CI skips the fdu job.
- **R15:** Let the macOS app select a provider: pass `METABROWSER_INVENTORY_PROVIDER`
  through `ChildEnvironment.swift`, or use the new flag and raise
  `MetabRequirement.minimumRelease`; install with the extra.

**Measure honestly.**

- **R16:** Replace the Python log-line regular expression that the serving benchmark and
  the performance loop use to detect discovery completion with a provider-neutral
  diagnostics field.
- **R17:** Register fdu in `INVENTORY_PROVIDERS`, attest the fdu wheel beside the
  Metabrowser wheel, and add a semantic-equality precheck that compares `--api` digests
  across providers on the corpus before timing.
- **R18:** Keep an engine-only layer (open to settled, read latencies, no server) as a
  maintained harness, from the spike’s runner.

**Remove host costs that would mask the engine.**

- **R19:** Carry bounded entry facts on change batches and stop marking diagnostics
  dirty on every change (`mb-l2eh`).
- **R20:** Construct provider-built rows without per-row path revalidation, and consider
  columnar catalog and recent pages.
- **R21:** Feed the activity tracker incrementally instead of a whole-index catalog
  every five seconds.
- **R22:** Re-measure Python-motivated host tuning (`grouped_tree_admission`, the
  cold-start wait loop, page sizes) per provider.
- **R28:** Stop bundling navigation tallies into every `/api/tree` page read; request
  them only where the response uses them.

**Close the bypasses.**

- **R23:** Route `metab --walk` text and stream modes through the runtime (`mb-iyu7`).
- **R24:** Delete the dead `tree._dir_tree` family and its re-exports; use the
  configured scope in `_folder_not_indexed`; document the README scan as a host
  exemption.
- **R25:** Move the Python walker, watcher, and ignore builder under the Python provider
  package with a reverse ownership test (`mb-ed9h`).
- **R26:** Give the change relay a recovery policy so a provider failure does not end
  live updates until restart (`mb-6o0l`).

### The Production Adapter

`inventory_engine.providers.fdu_inventory` holds one `fdu.opened.OpenedIndex` per handle
and implements `InventoryHandle` by translation:

- open: map `InventoryConfig` to `OpenedOptions`, including the classification document
  and `TimeBasis.MODIFIED`; derive scope and semantic identities from fdu’s `EntryScope`
  and `SemanticIdentity`;
- read: map each query to one or more fdu projections in a single pinned native read,
  translate rows and counts, and map refusals and limits to contract results;
- changes: one dedicated poll worker per handle bridging fdu’s blocking
  `changes(after, timeout)` to the async iterator, enforcing the single active iterator
  and translating impact into `ChangeBatch`;
- refresh and prioritize: pass paths through and translate receipts;
- close: stop the bridge, then close the native root, joining both.

All blocking native calls run off the event loop, and the binding releases the GIL
during native work. The adapter’s only state is the native handle, the bridge, and
per-read scratch.

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
3. Calibrate with an A/A pair per provider to measure harness noise.
4. Run at least five interleaved, order-randomized Python and fdu pairs per corpus, and
   report paired medians with their range and the ratio.
5. Record CPU (user and system), peak and settled RSS, event-loop lag during discovery,
   and the work counters alongside wall time.
6. Measure fdu’s one-shot index and a plain metadata traversal on the same tree as
   floors, so each result also reads as a distance from the filesystem.

The corpora are the generated 100,000- and 300,000-file trees that `make benchmark`
builds, a real checkout with its dependency trees installed, one larger real tree, and a
churn scenario (a sustained create, modify, and remove stream plus one large burst).
The performance loop’s method, accept rule, and durable-storage rules apply
(`explorations/performance-loop/README.md`); wall-clock thresholds never gate shared CI.

## macOS Validation

The Linux spike cannot answer these; each needs a run on an Apple silicon Mac against
the same fdu revision.
The [spike’s README](../../../explorations/fdu-provider-spike/README.md) has the exact
commands.

- **Build and install:** build the wheel at the same fdu revision for arm64, or install
  the published wheel with the matching digest, and confirm Metabrowser imports it.
- **Conformance and routes:** the same provider cases and route and SSE tests as Linux.
- **FSEvents behavior:** live create, modify, rename, and remove delivery; appends from
  a process that keeps the file open (`fdu-vhrb`); a rename burst; a
  must-scan-subdirectories event becoming scoped reconciliation.
- **Time to `watching`:** FSEvents needs no per-directory registration walk, so the
  remaining cost is the final reconciliation pass.
- **Discovery cost on APFS:** opened discovery wall time and memory against the one-shot
  index (the exp-126 comparison) and against the Python provider.
- **Case and normalization:** APFS is case-insensitive by default and Git sets
  `core.ignorecase` there; compare both providers’ ignored sets and path identity for
  names differing only in case and for decomposed Unicode names.
- **Paired benchmark:** the 100,000- and 300,000-file `make benchmark` rows on the M1
  Pro that recorded the Python baseline.
- **The app:** once R15 lands, open a folder in the macOS app with each provider and
  check progressive open, live changes, and memory.

## Options Considered

### Adopt: Neutral Contract, Then Native Projections Behind a Thin Adapter

**Description:** Make the contract provider-neutral with only Python behind it, register
fdu as an explicit experimental provider once fdu’s open-time changes release, and
replace its fallbacks with native projections until none remain.

**Advantages:**

- keeps the August boundary, which both codebases now fit;
- fixes Python bugs the neutral contract exposes, independent of fdu;
- starts the paired measurements and macOS validation early through the experimental
  selection;
- every step is testable with the same conformance registry.

**Costs:**

- a sizable fdu work list (F1 to F23) and a Metabrowser refactor list (R1 to R28);
- an experimental provider that is slower than Python for first folder counts until F10,
  F12, and F14 land.

### Eliminated: Ship the Fallback Adapter as the Backend

The spike measured it: fallbacks are 8 to over 100 times slower, cannot answer during
discovery, and double settled memory.
The engine gain is consumed by the image rebuild on every version.

### Eliminated: Retained Versions Instead of Native Projections

Retaining old versions in fdu would let fallback images assemble during discovery, but
it leaves every fallback paying an index-sized binding crossing per version, which the
spike measured at 2.1 s of binding plus 0.74 s of conversion on `project-10` before any
projection work. Bounded native projections need neither.

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

1. Keep the provider boundary and the fdu direction: on Linux the engine settles 3.5 to
   5.4 times faster and delivers live changes 20 to 25 ms sooner.
2. Land the provider-neutral contract (R1 to R9, R27) first, with only Python, because
   it fixes real Python defects and is the prerequisite for every parity claim.
3. Ask fdu for the open-time group (F1 to F6, F19) next; it is all small work and lets
   the provider open without shims.
4. Register fdu as an explicit experimental provider (D12, R10 to R18) so the U3 reading
   and macOS validation can start, and label its fallbacks in diagnostics.
5. Prioritize fdu’s rollup, navigation, row-cost, and prompt-open work (F10, F12, F14,
   F15) over the rest of the algebra, because those decide first folder counts.
6. Measure before and after with one build and an interleaved provider axis at the
   engine, unattached server, and browser layers, and land host-cost refactors (R19 to
   R22, R28) before reading the attached layer as a provider result.
7. Decide adoption only with zero fallbacks, passing conformance on Linux and macOS, and
   paired results on both platforms; any default change stays a separate, reversible
   decision.

## Next Steps

- [ ] Validate this spike on macOS using its README (tracked as a bead; the pull request
  carrying this research leaves the checklist open).
- [ ] Record decisions D1 to D12 in the inventory-provider architecture document.
- [ ] Open the Metabrowser beads for R1 to R28 under `mb-hej8`, linking the existing
  beads each one absorbs.
- [ ] Propose the fdu changes to the fdu project, starting with F1 to F6 and F19, and
  correct the stale bullets in fdu’s opened-root plan (removing ignored-last ranking and
  filtered-tree paging, and the “map recent and navigation onto `Report`” strategy).
- [ ] Implement the experimental provider after the open-time group releases.

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
- [Performance campaigns](../specs/active/plan-2026-11-14-performance-campaigns.md)
- [Performance architecture review](research-2026-11-14-performance-architecture-review.md)
- [Checkpoint 2A spike](../../../explorations/fdu-inventory-adapter/README.md)
- [fdu opened-root plan](https://github.com/jlevy/fdu/blob/4450be7/docs/project/specs/active/plan-2026-08-25-fdu-opened-root-inventory-engine.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
