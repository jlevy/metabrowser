# Feature: End-to-End Load Time, from the CLI to First Paint

**Date:** 2026-08-21

**Author:** Metabrowser maintainers

**Status:** Partly delivered; broader load-time, flat-tree, and visual-stability goals
remain open.

On-demand asset bundles, progressive inventory delivery, cooperative provider work, and
an enforced startup-script budget are implemented.
They do not complete the remaining whole-tree, warm-reopen, navigation-window, and
visual-stability work below.
The opening measurements and experiment narratives are historical baselines, not
measurements of the current build.

## Overview

Metabrowser should be the fastest way to browse a lot of files, and it should feel
instant at any size a filesystem can produce.
It is not there yet, and the gap is not where it looks.

Measured cold, on a synthetic 100,000-file tree, the shell paints in 92 ms and the first
row of the file tree appears **4,525 ms** later.
On a million-file tree the shell paints in 176 ms and the first row appears at **22,328
ms**. The browser has usable tree data at 319 ms in both cases.
It is not waiting on bytes.
It is waiting for the scan to finish before it draws anything.

That is the headline, and it reframes the work.
The front-end payload is worth fixing — 432,092 bytes of vendored JavaScript load on
every page and the Chart.js stack alone costs about 374 ms of every document’s `load` —
but it is the smaller half.
The larger half is that the tree, the catalog, and the scan are all gated on completion
when they could be progressive.

This plan is one performance pass across the whole path: the assets the browser loads,
the time until the tree is usable, and the server and CLI work underneath.
Each phase reports through the same harness, so each change is a comparison rather than
an impression.

## Goals

- First usable tree rows in well under a second at any corpus size, on the same hardware
  where that is 4.5 s at 100,000 files and 22 s at a million today
- Rendered row count bounded by the viewport rather than by the corpus
- CLI start to serving bounded by the code, not by the tree
- No silent truncation: a million-file folder is browsed, not cut off at 500,000
- Every asset and bulk payload on an explicit loading tier, justified by measurement
- One harness that measures all of it, records it as JSON, and diffs two runs, extending
  `devtools/bench_serving.py` rather than sitting beside it
- One visual state, not a sequence: what the reader can see settles in a single paint,
  and nothing above it ever moves afterwards

### What We Are Optimizing For

Added after exp-010, because the first nine rounds optimized something narrower than
what this product is for, and the measurements say so.

`first_row_ms` rewards painting *something* early and is indifferent to everything after
it.
Across the campaign it went **1,473 ms to 276** while `tree_region_repaints` went **1
to 2**: time to first paint was bought, and paid for in visual states.
That trade is the mechanism of flicker — paint a placeholder, replace it — and it is
what a reader experiences as the page assembling itself.

So the objective, stated so a round can fail against it:

> **What the reader can see reaches its final state in a single paint.
> Everything below the fold may arrive later, provided it moves nothing above it.**

Off-screen filling is free; on-screen replacement is not.
A 246,000-file tree obviously cannot be complete at first paint, and does not need to be
— the viewport does.

Four distinct failures hide behind the words *flicker* and *jank*, and conflating them
is why exp-009 fixed one and read as finished:

| What the reader sees | Cause | Where it stands |
| --- | --- | --- |
| Content jumps down | A box above it changed size | Mostly fixed (exp-009). 23 px left, H54 |
| Content blinks and redraws | The DOM was destroyed and rebuilt | Fixed for the initial tree handoff: one whole-region build, H11 and H53 |
| Blank, then content | Nothing painted there yet | The frame is placeholders, H52 |
| Right, then corrected | An optimistic paint was reconciled | Not yet a problem; H42 would create it |

The comparison that matters is a desktop application, which wins on three structural
properties rather than on speed: it is already resident, so opening a folder does not
reload the program; it keeps state, so reopening shows the last known view and
reconciles behind it; and it mutates in place, so a new file inserts a row rather than
rebuilding the list.
A page reloading gives up all three by default, and getting them back is deliberate
work: H57, H42, and H11 respectively.

### Proposed Budgets

Targets to validate and adjust in Phase 1, not settled numbers.
They exist so a later change has something to fail against.

The budgets the loop enforces are in
`explorations/performance-loop/performance-budgets.toml`, and its comments name the
experiment behind each ceiling.
First row is a 350 ms gate, calibrated on the repository-shaped project-10 corpus in
exp-035. Startup scripts are gated at 25 requests, from exp-014 on a 111,590-file
corpus, and at 220 KB, from exp-084 on a 468-file folder page.
First contentful paint is a 200 ms target.
`performance-budgets-flat-stress.toml` holds the flat shape.
The table below is the August proposal; no 10k, 100k, or 1M baseline has replaced it row
by row.

| Measure | Budget | Today, 100k | Today, 1M |
| --- | --- | --- | --- |
| First contentful paint | ≤ 200 ms | 92 ms | 176 ms |
| First usable tree rows | ≤ 500 ms | 4,525 ms | 22,328 ms |
| Rendered rows | viewport-bounded | 2,550 | 25,122 |
| DOM nodes at rest | ≤ 20,000 | 28,711 | 276,789 |
| CLI start to serving | ≤ 300 ms | 944 ms | 2,748 ms |
| Eager third-party JS | ≤ 150,000 B | 432,092 B | 432,092 B |
| Visual states in the viewport | 1 | 3+ | 3+ |
| Movement after first paint | 0 px | 23 px | not measured |
| Shell boot, navigation to first row, minus server time | ≤ 50 ms | ~270 ms | not measured |

The last three come from [What We Are Optimizing For](#what-we-are-optimizing-for) and
are the ones this plan was missing.
Their “today” column is the fixed 246,282-file corpus at 1280×900, not the 100k/1M
synthetic runs the rows above it use, because that is where they were measured; see
[exp-009](../../../../explorations/performance-loop/experiments/exp-009-the-skeleton-stops-growing-under-the-reader.md)
and
[exp-010](../../../../explorations/performance-loop/experiments/exp-010-every-checkpoint-on-one-corpus.md).

## Non-Goals

- Changing what Metabrowser shows.
  This is a plan about when things arrive, not about detail: the detail is the point of
  the product and none of it is traded away for speed.
- A build step or bundler
- Server-side rendering of the file tree
- Persisting an index across runs.
  Worth its own investigation once the progressive path exists; a cache that hides a
  slow path is not a fix for it.
  H21 (`mb-omhf`) reopens it now that the progressive path exists, and the
  [native macOS app plan](plan-2026-11-10-native-macos-app.md) carries it as a measured
  follow-up.

## Background

> **Superseded — read the [hypothesis registry](#hypotheses) and
> [the ledger](../../../../explorations/performance-loop/report.md) first.** Every
> number in this section was taken by hand against a corpus that was not `build_corpus`
> and no longer exists, before the exploration loop existed.
> Two of them did not survive re-measurement: the headline 4,525 ms first row (H6, not
> reproduced — the same measure is 854 ms on `build_corpus` at the same file count) and
> the 4.5 MB `/api/catalog` (H4, 62 bytes here, because the catalog fills from
> recognized file kinds and this corpus has none).
> The section is kept because its *shape* — that the browser has data long before it
> shows rows — is what motivated the work, and because a superseded measurement deleted
> is a measurement someone takes again.

All numbers below were taken on this machine against synthetic corpora of a realistic
shape (nested package directories, mixed extensions, small file bodies), Chromium 141
via Playwright build 1194, medians of repeated cold runs.
Absolute values move with hardware and page cache.
The shape is what carries.

### The Browser

Cold load of `/view/`, first row measured by waiting for a `[role="treeitem"]` element:

| Corpus | FCP | DOMContentLoaded | First tree row | Rows | DOM nodes | Transferred |
| --- | --- | --- | --- | --- | --- | --- |
| 100,000 files | 92 ms | 217 ms | 4,525 ms | 2,550 | 28,711 | 937,756 B |
| 998,560 files | 176 ms | 557 ms | 22,328 ms | 25,122 | 276,789 | 2,507,258 B |

The shell is fast. What follows it is not, and the request waterfall says why.
On the 100,000-file tree:

| Time | Request | Duration | Bytes |
| --- | --- | --- | --- |
| t+319 ms | `/api/tree` | 38 ms | 387,778 |
| t+366 ms | `/api/rollup?path=&depth=0…` | 674 ms | 3,473 |
| t+1,063 ms | `/api/events?scope=root-depth-2` | 3,669 ms | — |
| t+4,733 ms | `/api/catalog` | 98 ms | 4,580,060 |
| t+4,936 ms | *first row painted* |  |  |

Three separate problems sit in that table.

**The tree waits for the scan.** Tree data is in the browser at 319 ms.
The event stream then blocks for 3,669 ms, which is the walker converging, and rows
appear only after it does.
The server is already built for the opposite: the first `/api/tree` answers in 3 to 9 ms
with partial data at every corpus size, because the walker publishes as it goes.
The client does not use that.

**The catalog is on the critical path and is not small.** `/api/catalog` is the Quick
File finder’s index — every path in the tree, 4,580,060 bytes at 100,000 files.
Nothing needs it until the finder opens.

**The tree renders every row it knows about.** 25,122 rows and 276,789 DOM nodes at a
million files, with no windowing.
[Rendering large content](../../../large-content-rendering.md) already establishes that
element count and memory are the real ceiling, and this is well past where that document
puts it.

After the first row, the tree hydrates each visible folder with its own request: of 42
API calls on that load, most are `/api/tree?path=…&depth=2` at about 5,230 bytes each,
fired in a burst.

### The Assets

Six vendored files, 432,092 bytes, load on every page through a serial chain in
`server.py` that appends one `<script>` at a time and chains each on the previous one’s
`onload`. Blocking the Chart.js stack moves the `load` event from 853 ms to 479 ms;
blocking all vendored JavaScript moves it to 330 ms.
First contentful paint does not move in either case, because the chain starts after it.

| Library | Bytes | Read by |
| --- | --- | --- |
| Chart.js and its two plugins | 297,531 | The agent-log `charts` view only |
| highlight.js and the TOML grammar | 122,771 | Client-side highlighting of source views |
| Mustache | 11,790 | `metabrowser.render` in the plugin SDK |

Each already tolerates absence: `charts.js` guards `typeof Chart === "undefined"`,
`app.js` returns early without `hljs`, and `plugin-sdk.js` throws a named error without
`Mustache`. Each guard becomes an await rather than a bail-out.

### The Server and the CLI

From process start to the first served response, then to walk completion:

| Corpus | Start to serving | First `/api/tree` | Walk | Warm `/api/tree` |
| --- | --- | --- | --- | --- |
| 9,000 files | 771 ms | 3.1 ms, 32,117 B | 472 ms | 77 ms, 37,359 B |
| 100,000 files | 944 ms | 7.7 ms, 91,732 B | 4,908 ms | 866 ms, 387,783 B |
| 998,560 files | 2,748 ms | 9.4 ms, 43,686 B | 27,426 ms | 4,990 ms, 3,676,480 B |

Four things follow.

Startup is not constant.
It nearly triples between 100,000 and a million files, so something in the path to
binding the port scales with the tree.
Of the fixed part, `import metabrowser.cli` measures 113 ms and `uv run python -c pass`
about 56 ms, which leaves most of the fixed cost unattributed and worth attributing
before it is optimized.

The walk is linear at roughly 50 µs per file, and single-threaded.

The warm `/api/tree` is linear and expensive: 4,990 ms and 3.68 MB for one request at a
million files. It is the same route that answers in 9 ms while scanning, so the cost is
in serving the whole known tree at once rather than in the route itself.

The million-file run reports `status=truncated files=500000`. `INVENTORY_MAX_FILES` is
500,000, so half that corpus is silently absent.

### What Already Exists

This plan extends existing machinery rather than introducing a parallel one.

`devtools/bench_serving.py` measures scan and serve, writes JSON, and diffs a labelled
run against a baseline.
[Its documentation](../../../development.md#benchmarking-scan-and-serve) is explicit
that only a back-to-back comparison carries, which is the discipline this plan adopts
throughout. `devtools/bench-browser-probe.js` measures request coalescing from inside an
open page by reading the `Server-Timing` header every route emits.

Neither measures cold page load, first paint, or time to first row, and the browser
probe is pasted into a console by hand.
That is the gap Phase 1 closes first.

## Design

### Approach

Three phases, front to back, each ending in a recorded comparison.

Phase 1 takes the front-end payload, because it is self-contained and it forces the
harness to grow the page-load half it is missing.
Phase 2 takes the time between paint and a usable tree, which is where the seconds are.
Phase 3 takes the server and the CLI, once the client stops asking for everything at
once and the real server cost is visible rather than masked by client waiting.

The ordering is deliberate.
Phase 3’s numbers are not trustworthy until Phase 2 stops the client from gating on
completion, because a client that waits for the scan makes every server cost look like
scan cost.

### Components

**`devtools/bench_serving.py`.** Gains a page-load phase driving headless Chromium
against the same corpus it already builds, reporting first contentful paint,
DOMContentLoaded, time to first tree row, rendered row count, DOM node count, and
transferred bytes into the same result JSON, so one `--baseline` comparison covers
serving and page load together.
Superseded: this phase was not added, and `explorations/performance-loop/run.py`
measures page load instead (`mb-pwnw`, Phase 1).

**`static/asset-loader.js` (new).** One loader with `ensureAsset(name)` and
`prefetchAssets()`, generalizing the loaded-set and in-flight-promise semantics that
`plugin-sdk.js` already implements privately for KPress modules.
A new module, so it sits under the fully strict `tsconfig.json` gate.

**`server.py`.** The eager core list is unchanged.
`optional_script_assets` becomes a tiered descriptor published to the client rather than
expanded into an inline chain.

**The nav tree client.** Renders from partial index state as it arrives instead of
gating on scan completion, and windows its rows so the rendered count follows the
viewport.

**`/api/catalog` and its client.** Moves to the on-demand tier, fetched when the finder
is first opened rather than on load.

**The walker and `/api/tree`.** Phase 3’s subjects: the startup path that scales with
the tree, walk throughput, whole-tree response cost, and the 500,000-file cap.

### API Changes

`METABROWSER_SETTINGS` gains the asset descriptor the loader reads.
`window.metabrowser` gains the asset loader surface.
Both are additive; server, shell, and built-in plugins ship as one artifact and change
together in one commit.

`PLUGIN_SDK_VERSION` moves from 0.4 to 0.5 before v0.7.0. Version 0.6.0 loaded every
admitted plugin’s styles, classic scripts, and index module with the page.
Loading those assets only when the browser selects one of the plugin’s kinds changes
when global CSS and module side effects exist, so it is a released contract break even
though the callable SDK surface is additive.
The exact-match gate must reject 0.4 manifests rather than silently admitting them under
the new lifecycle; every built-in manifest and the plugin documentation move with the
host.

Any change to `/api/tree`’s progressive contract or to `INVENTORY_MAX_FILES` is
observable, so it lands in `CHANGELOG.md` and in
[state and delivery](../../architecture/arch-live-delivery.md#pulled-aggregates).

## Implementation Plan

### Ordering: What to Work Next

The current order of work is in
[the campaign plan](plan-2026-11-14-performance-campaigns.md), which sorts the open rows
of this registry into lanes and loops and gives the
[order to work them in](plan-2026-11-14-performance-campaigns.md#order-of-work).
The [hypothesis registry](#hypotheses) is the live source for status.

The table below is **the order as of exp-010, kept for history**. It was reordered after
exp-010 put every checkpoint on one corpus and priced the campaign as a whole, so it
predates exp-014 and every row from H58 on.

Two findings moved this table.
The server is no longer the bottleneck — it answers the first tree request in 6 ms while
the reader waits 276 ms for a row — so the top of the list is now client-side.
And the campaign bought its speed partly with visual states, taking the tree region from
one paint per load to three, which is the flicker
[the objective](#what-we-are-optimizing-for) is about.

Rows 1–6 are the reader-facing block and are new to the top.
Rows 7–19 are the scan and walker work, unchanged in relative order.

The v0.7.0 stabilization gate preempted that backlog and is complete; see Phase 4. It
began with H59’s failing installed-build comparison, then made the navigation-tally
freshness lookup nonblocking, versioned the deferred plugin lifecycle as SDK 0.5,
preserved manifest order when several plugins own one kind, and re-ran both backend and
visible-browser comparisons before the changelog was finalized.
The release comparison is the source of the release numbers; an intermediate regression
introduced and corrected within this cycle is part of the final behavior, not a shipped
fix.

| # | Next | Why here |
| --- | --- | --- |
| 1 | **H51** — establish the visible LCP and CLS baseline (`mb-qf2p`) | **Complete in exp-014.** Four admissible harness-14 runs per installed build stayed visible at 1600×900 and captured non-null LCP and CLS. The candidate median LCP is 146 ms against 212 ms; CLS is 0 in every candidate run. Direct frame and summary measurements retain the visual debts that CLS alone does not express |
| 2 | **H11** — patch the panel instead of replacing it (`mb-izxl`) | **Complete in exp-014.** The fetched snapshot reconciles into keyed visible containers instead of replacing the inline tree, and `tree_region_repaints` is 1 per load. exp-010 had found it a regression this campaign introduced: 1 paint before the performance work, 2 after |
| 3 | **H52** — ship a skeleton, not placeholders (`mb-rxst`) | At first paint the files panel is a spinner at 80 px where 612 px of rows belong. exp-009 stopped the frame moving; this is what makes the frame exist. The obstacle is duplication: the chip and row markup lives only in JavaScript, so a server-side counterpart needs a shared source or it drifts |
| 4 | **H57** — attribute the shell’s own boot (`mb-emhr`) | **Attributed in exp-014; optimization remains open.** Startup rows split into response wait, Server-Timing work, and download. 6 ms of server against 276 ms to first row was the gap; H9, H10 and H17 are the candidate fixes, H44 (which absorbed H26) owns whether server-side concatenation earns its complexity remotely, and H96 is that concatenation |
| 5 | **H54** — the tally row’s remaining 23 px (`mb-w3va`) | Small and nearly free. The exp-009 audit found the better fix: the row is already wrapped at 14,826 files mid-scan, so the server has a usable partial count long before the walk ends and could inline it with the rows it already inlines |
| 6 | **H42** — client-side tree replica (`mb-6rdn`) | Promoted from 12. The only row that makes a *revisit* instant, which is half of what “like a desktop app” means, and it is independent of every walker row so it can run in parallel with them |
| 7 | **H56** — replace the loop’s primary metric (`mb-unt6`) | No longer blocked on a visible driver, and H51’s baseline is recorded (exp-014); it still needs an instrument for distinct visible states rather than the current repaint proxy. This is what stops the loop steering itself wrong again |
| 8 | **H31 remainder** — re-measure the loop (`mb-jalf`) | exp-007 took the attached walk from 70.2 s to 50.0 s. Unattached it is 21 s, so amplification is now roughly 2.4x rather than 12x. Measure with a real browser, which is heavier than the probe, before deciding whether serving needs an explicit CPU bound during a scan |
| 9 | **H39** — price the gitignore matcher (`mb-8yqt`) | One run, and it redirects the three largest rows below it. H21, H40, and H35 all attack the same 50 s from different sides; knowing whether matching or traversal dominates says which is the bigger bite |
| 10 | **H49** — measure the four unrecorded regimes (`mb-609b`) | Scaffolding, ordered here because H21 cannot be scored without the warm-reopen distinction, and because interaction latency is where a reader actually spends their time |
| 11 | **H32** — inline without a warm index (`mb-vih2`) | **Resolved by H30.** With no pre-walk the root is indexed within one `scandir` of the walk starting, so the inline carries rows on a first open |
| 12 | **H21** — persist the index (`mb-omhf`) | A 44 s cold open repeated every session is exactly the case persistence exists for. Larger than everything above it and worth doing once they are done |
| 13 | **H28** — build the tree from the SSE stream (`mb-ap6p`) | The streamed-delivery centerpiece. Still right, but on a real tree the reader’s problem is that rows do not *exist* yet, not that they are delivered in snapshots |
| 14 | **H18 → H22** — profile the walk, then batch it (`mb-nbc6`, `mb-tip8`) | Demoted by measurement: the clean walk is 21 s at 104 µs per directory. Worth attributing, but it is not what makes this tree slow |
| 15 | **H26 + H29** — one remote round (`mb-f591`, `mb-pk2l`) | Unchanged: costs localhost hides. Measure the stake before choosing a fix |
| 16 | **H47** — right-size the executor (`mb-squq`) | Cheap, and it is the other half of H31’s remaining question about serving under a scan |
| 17 | **H41** — columnar index (`mb-od5n`) | With H34 this deletes the tally apparatus rather than tuning it. Ordered after the measurement rows so the pass cost is attributed before it is engineered away |
| 18 | **H40** — native parallel walker (`mb-nbvk`) | Blocked on H39. The largest scan win available if matching is what costs, and it retires the negation bug rather than guarding it |
| 19 | **H44** — the remote-link regime (`mb-ycf2`) | Measurement first. If batching wins at 120 ms RTT the way it should, it reorders much of this table |

Three orderings are load-bearing.
The measurement row comes first (1) because the objective it serves was invisible until
it ran; attribution comes before the walker change (14), because a structural rewrite
without a profile is a guess; and the walk attribution comes before the file cap (H15),
because a cap is a claim about cost and there is no measurement of that cost yet.

### Considered and Deliberately Not Registered

A registry that only ever grows is a backlog, not a map.
These were examined during the exp-004 review and left out on purpose, so the next
reader spends their attention elsewhere rather than re-deriving them:

- **Streaming file and document previews.** The text path is already a bounded envelope
  with an explicit continuation (`fetchCompleteText`, `renderTextLoadMoreFooter`,
  `source-append.js`). The waiting-for-complete problem this plan is about does not
  appear there.
- **Chunked-encoding the `/api/tree` body as NDJSON.** It attacks the same wait H27
  removes, for a protocol change, a streaming JSON parser on the client, and an
  interaction with the gzip middleware.
  If H27 lands and a wait remains, revisit; reaching for it first would be solving the
  harder half of the same problem.
- **HTTP/2 or connection-count work for the eager asset chain.** H44, which absorbed
  H26, has to price the stake first.
  On localhost the startup scripts cost little: 20 of them at `27ea216c`
  ([exp-084](../../../../explorations/performance-loop/experiments/exp-084-eager-startup-script-cost.md)),
  gated at 25 requests and 220 KB in `performance-budgets.toml`. A fix chosen before the
  measurement is a fix chosen for a number nobody has.
  The
  [architecture review](../../research/research-2026-11-14-performance-architecture-review.md)
  then deferred it behind U2 (`mb-cejc`). Browsers speak HTTP/2 only over TLS, and the
  wait may be server work rather than connections; but H57 recorded an 81 ms local
  HTTP/1.1 queue before one `app.js` response, so U2’s reading decides it rather than a
  ruling.

Two options the architecture review refuted:

- **A shared multi-root process.** The server is built around one root per process (the
  review counted 42 uses of single-root accessors in 10 files), and a resident server
  that adopts one root (H117) gets the same saving without rewriting them.
- **A server-rendered or stored first-screen DOM.** It needs a second renderer, and H118
  shortens the landing chain without one.

Three rows were registered and then retired on 2026-11-14. H12 and H19 describe paths
the code no longer has; H42 cannot do what it claims.
Each keeps its number in the registry, so no id means two things:

- **H12, `/api/recent` on the load path.** Nothing puts a recency filter on a load.
  Filter state starts at its defaults on every page (`load()` in `filter-state.js`), and
  nothing restores a recency from a URL or a preference.
  So `/api/recent` is requested only after the reader picks a recency
  (`filesPanelUsesRecentSource()` in `app.js`). Revisit if a filter is ever restored on
  load.
- **H19, `/api/events` before the first row.** The stream opens last in `app.js`’s
  startup, after `await loadTree()` and the navigation start
  (`startInventoryEventStream()`), and the first rows are inline in the shell (H20), so
  it cannot hold the first row.
  The 3,669 ms stall was never re-observed, and it was taken in the same degenerate
  hidden pane as H6.
- **H42, a client-side tree replica painted before the server answers.** The shell
  document comes from the same server process a relaunch waits for, so a replica held by
  that document cannot paint before the server answers.
  A restored window’s snapshot is native work (the architecture review).

### Phase 1: The Harness and the Front-End Payload

- [ ] Add a page-load phase to `devtools/bench_serving.py`: headless Chromium against
  the corpus it already builds, reporting FCP, DOMContentLoaded, time to first tree row,
  rendered rows, DOM nodes, and transferred bytes into the existing result JSON and
  `--baseline` diff. Superseded by `explorations/performance-loop/run.py`, whose
  `capture` and `capture-browser.js` measure first row and paint in a real browser
  against `performance-budgets.toml` (`mb-pwnw`)
- [ ] Record a baseline at 10,000, 100,000, and 1,000,000 files and check the numbers
  into this document, replacing the proposed budgets with validated ones.
  Not done as written: after H16 the loop gates project-10 through
  `performance-budgets.toml`, plus `build_corpus` shape 2 at 300,000 files through
  `performance-budgets-flat-stress.toml`, rather than these three sizes; see
  [Proposed Budgets](#proposed-budgets) (`mb-o2hk`)
- [x] Add `static/asset-loader.js` for the on-demand tier, under the strict
  `tsconfig.json` gate.
  Planned with eager, prefetched, and on-demand tiers, it owns only the on-demand tier,
  through `ensureAsset`; the prefetched tier is the idle chain below (`mb-sn1i`)
- [x] Publish a tiered asset descriptor from `server.py` in place of the inline chain,
  keeping the `metabrowser:optional-asset*` re-enhance events firing.
  `server.py` publishes the on-demand bundles as `window.METABROWSER_ASSET_BUNDLES`
  beside the prefetched `optional_script_assets` chain (`mb-nytk`)
- [x] Move the Chart.js stack to on demand.
  `static/asset-loader.js` owns the loading, `plugin-sdk.js` publishes it as
  `ensureAsset`, and the agent-log charts view awaits it.
  Measured on this repository, median of five cold loads of `/view/README.md`: `load`
  853 ms to 411 ms, transferred 823,391 B to 732,836 B, vendored files on load 6 to 3.
  First contentful paint did not move, which is the expected result: the chain never
  blocked paint, it competed with the tree render behind it.
- [x] Move highlight.js, the TOML grammar, and Mustache to prefetch-on-idle.
  The chain now starts on the first idle callback after `DOMContentLoaded`, with a 2,000
  ms floor so a busy main thread cannot defer highlighting forever.
  Measured on the 100,000-file bench corpus, median of three cold loads of `/view/`
  each, a fresh port and a fresh server per run so both the browser cache and the index
  start cold: `load` 3,883 ms to 750 ms.
  Time to first tree row did not measurably change — 854 ms against 999 ms, on ranges of
  678-1,591 ms and 690-1,106 ms that overlap almost completely.
  Accepted on the tier policy and the `load` result, not on a first-row win
- [x] Re-measure and record the comparison: H55 in exp-010, and H51 and H9 in exp-014
  (`mb-3jt8`)

### Phase 2: Time to First Row

- [ ] Render nav rows from partial index state as it arrives, instead of gating on scan
  completion; the first `/api/tree` already answers in under 10 ms at every corpus size.
  Not needed as stated: H6 did not reproduce, because `renderFilesFromTree` runs as soon
  as `/api/tree` resolves, and H20 inlines the first rows (`mb-op70`)
- [x] Inline the root’s depth-1 rows into the shell so the first paint does not wait for
  a fetch: 1,604 ms to 242 ms at 300,000 files —
  [exp-004](../../../../explorations/performance-loop/experiments/exp-004-the-shell-carries-the-first-rows.md)
- [x] Show scan progress in place rather than as an empty tree, so an incomplete tree
  reads as incomplete — [degrade visibly](../../../large-content-rendering.md).
  `#index-progress` and `renderIndexProgress` show a scan count in place of an empty
  tree (`mb-s8yx`)
- [ ] Window the rendered rows so the count follows the viewport, keeping find-in-page
  and selection working or recording what is traded (`mb-z7zb`)
- [ ] Move `/api/catalog` to the on-demand tier, fetched when the finder first opens
  (`mb-296z`). `catalog-feed.js` already holds the fetch on a pull-request page until
  its palette or a file releases it
- [x] Collapse the per-folder `/api/tree?path=…&depth=2` burst into what the viewport
  needs. Candidates are now the lazy stubs whose folder row is on screen plus one screen
  of lookahead, and the sweep re-arms on scroll and on folder expansion.
  Measured at 300,000 files, 1280x900, median of three cold loads: 32 subtree requests
  and 1,566 KB to 0 and 517 KB. Time to first row did not measurably change —
  [exp-002](../../../../explorations/performance-loop/experiments/exp-002-subtree-prefetch-bounded-to-the-viewport.md)
- [ ] Re-measure at all three corpus sizes and record the comparison

### Phase 3: The Server and the CLI

- [ ] Attribute start-to-serving: find what scales with the tree before binding, and
  what the fixed cost is beyond the 113 ms module import and 56 ms interpreter start
  (`mb-kp6c`)
- [ ] Reduce the whole-tree `/api/tree` cost, which is 4,990 ms and 3.68 MB at a million
  files on the route that answers in 9 ms while scanning (`mb-r4bm`)
- [ ] Measure walk throughput per file and find where the roughly 50 µs goes (`mb-migx`)
- [ ] Decide what replaces `INVENTORY_MAX_FILES = 500_000`: a higher measured cap, or a
  progressive index with no cap and a visible frontier.
  Silent truncation is not an option either way (`mb-s5p6`).
- [ ] Re-measure and record the comparison

### Phase 4: v0.7.0 Release Stabilization

- [x] Extend `devtools/compare_builds.py` before changing production code.
  While one root tally is computing and another depth-0 tally request overlaps it, probe
  `/api/index/progress` and record `tally_overlap_progress_max_ms` and the sample count.
  Pair it with a deterministic test that holds the tally lock for 350 ms while a 1 ms
  asyncio heartbeat runs.
  The deterministic cache-probe budget is less than 50 ms.
  The installed-server budget is less than 200 ms, matching the browser responsiveness
  boundary. The final five exact pairs record 389.1–439.4 ms on `c123ae6` and 50.4–135.4
  ms on the candidate over the unchanged 123,658-file corpus.
- [x] Make `navigation_tallies_fresh_within` a nonblocking cache probe.
  Contention may miss the memo and move work to the existing worker path, but it must
  never wait for the O(index) pass on the request event loop.
- [x] Bound the worker pass’s GIL residency with measured cooperative yield points.
  The first exact v0.6.0 comparison found one 291.7 ms progress outlier while that
  candidate tally pass stretched to 928.9 ms; the other four runs were 73.4–116.8 ms.
  Preserve the 200 ms release gate and add a deterministic heartbeat test that extends
  the interpreter switch interval, so a cold CPU tail cannot starve unrelated requests.
- [x] Bump the plugin SDK to 0.5, update every built-in manifest, and document the
  selected-kind lifecycle for `styles.css`, `extra_styles`, `extra_scripts`, and
  `index.js`. Keep the installed-browser startup gates at no more than 25 scripts and
  175 KB.
- [x] Load same-kind plugin descriptors sequentially in server discovery order.
  Add a behavioral test with two delayed modules that proves the later manifest
  deterministically owns a duplicate view while preserving per-plugin asset order,
  deduplication, and retry.
- [x] Treat the initial inventory as the navigation baseline before enabling live-change
  highlighting. Snapshot rows and walker upserts must stay neutral until the first
  inventory reports completion; only later inserts may use the yellow change flash.
  Gate the transition with a browser regression test and include the result in the final
  visible comparison.
- [x] Reject rendered preview errors and uncaught page exceptions as hard browser-gate
  failures. Rebuild the v0.6.0 measurement adapter from the exact tag, preserve its
  pre-SDK `metabrowserPerf` handoff, isolate external builds from the candidate
  checkout, and stop only the exact server process the harness started.
- [x] Build and install the exact candidate.
  Compare it first with the pre-fix `c123ae6` control and then with v0.6.0 using at
  least five interleaved backend pairs and four visible headed-browser pairs on one
  fingerprinted project corpus.
  Require identical ordered rows and tallies, less than 200 ms tally-overlap progress
  latency, every browser hard gate, and the existing startup asset gates.
  Retain full ranges for process start, FCP, LCP, and first row so cold-tail variance
  cannot disappear into a median.
- [x] Write the v0.7.0 changelog from the exact-candidate experiment.
  Describe the aggregate v0.6.0-to-v0.7.0 behavior and omit bugs that existed only
  between refactor commits in this unreleased cycle.

## Hypotheses

The loop that resolves these lives in
[explorations/performance-loop/](../../../../explorations/performance-loop/README.md):
its README is the runbook, `explorations/performance-loop/run.py report` regenerates
[the ledger](../../../../explorations/performance-loop/report.md), and every resolved
row below links the artifact that resolved it.

Each round of
[the exploration loop](../../../../explorations/performance-loop/README.md) tests one of
these, and each is stated so it can be wrong, with the metric that would show it.
Status is updated as experiments resolve them; the write-ups are in
[explorations/performance-loop/experiments/](../../../../explorations/performance-loop/experiments/).

Numbering is shared across this plan; a new hypothesis takes the next free number so no
id ever means two things.

One theme runs through the highest-leverage open rows and deserves naming: **nothing
should wait for “complete” when it can paint from “so far.”** exp-004 proved the shape —
rows inlined at page-render time made first paint independent of the slowest request —
and H27, H28, and H21 are the same move applied to the tally payload, the scan stream,
and process restarts respectively.

Three of these are standing design decisions rather than tuning targets, and they are
the rows most likely to move whole columns of the measurement tables: the walker applies
every entry, one at a time, on the same event loop that serves requests (H22, with H23
as its cheapest consequence); nothing survives a restart, so every open of a large tree
pays the full walk again (H21); and the first paint waits for a fetch whose payload the
server could have inlined (H20).

### What Each Hypothesis Is For

A registry this large is a list, not a map.
Every registered hypothesis appears exactly once below, grouped by which part of
[the objective](#what-we-are-optimizing-for) it serves, so an agent picking up this loop
can find the rows that bear on the question they care about instead of reading all of
them. **✓** marks a resolved row, **✗** one that did not reproduce as stated or was
rejected, and **→ Hn** one merged into Hn; a row retired, closed, or superseded says so.
The marks are a convenience and not every resolved row carries one.
Status and evidence stay in the registry tables; this is only the grouping.

**What the reader sees** — stability, and one paint instead of several.
The objective’s first two failure modes.

- H50 ✓ reserve the heights that grow · H54 the tally row’s remaining 23 px
- H11 patch the panel instead of replacing it · H53 repaints as a standing metric
- H52 ship a skeleton, not placeholders · H10 render-blocking stylesheets
- H51 measure LCP and CLS in a visible window · H56 the primary metric is mis-aimed
- H62 ✓ treat the first inventory as baseline before highlighting changes
- H63 ✓ reject rendered failures and isolate release measurement adapters
- H64 ✓ keep the prior Git revision visible through an atomic handoff

**How fast the first correct frame arrives** — everything on the critical path between
navigation and a usable viewport.

- H20 ✓ inline the first rows · H32 inline without a warm index · H1 ✓ prefetch on idle
- H74 cold navigation waterfalls · H75 → H94 natural intent timing · H76 prepared render
  cost
- H77 first-selection detail availability behind a ready catalog
- H78 redundant hover preparation after a selected Git revision renders
- H79 detached Git staging and the first-screen render budget
- H80 selected core viewer attribution and provider process cost
- H81 visible PR description preparation · H82 publication-to-paint delay · H83 catalog
  updates during preparation
- H73 ✓ a prepared PR manifest and visible prefix · H84 ✓ progressive PR metadata
  warming
- H57 attribute the shell’s own boot · H9 the eager JavaScript count · H17 import cost
- H107 a startup-script byte ceiling set at a measured size
- H14 start-to-serving scales with the tree
- H19 (retired) `/api/events` on the critical path · H29 the first byte waits on a
  filesystem walk
- H5 the root tree route under a scan · H8 ✓/H23 ✓ the tally pass per request
- H59 the event loop waits on the tally memo lock · H61 the worker pass can starve it
- H25 re-serializing an unchanged answer · H45 serialization cost · H37 path
  normalization
- H12 (retired) `/api/recent` on the critical path · H24 two progress channels at once
- H6 ✗ rows gated on scan completion · H4 ✗ the catalog payload

**How big the page gets** — the tree grows; the DOM and the wire should not.

- H7 window the rendered rows · H15 no silent truncation at 500,000
- H26 → H44 the eager request count priced at localhost · H44 the remote-link regime
- H41 a columnar index
- H58 main-thread work during load bounded by a budget, not the data

**Whether a revisit costs anything** — the desktop-app property this plan does not have.

- H21 persist the index · H42 (retired) a client-side replica painted before the server
  answers
- H46 bulk-attribute syscalls for the verification sweep

**How fast the tree becomes complete** — the scan behind the viewport.

- H30 ✓ remove the gitignore pre-walk · H27 ✓ rows without the tally pass · H2 ✓ bound
  the warming sweep
- H31 scan and serve contend · H33 tracked files before ignored ones · H43 the
  viewport’s subtree first
- H39 price the matcher · H40 (superseded) a native parallel walker · H35 (superseded)
  `git ls-files` on a git tree
- H34 incremental tallies · H36 → H34 the tally thread under the GIL · H47 executor size
  · H48 free-threaded
- H18 profile the walk · H22 batch it · H13 → H18 walk attribution · H28 build from the
  SSE stream
- H65 ✓ positional write-token copies · H66 ✗ netted ancestor deltas · H67 ✓ a
  delta-free add path · H68 ✗ memoized ancestor chains
- H69 ✗ path checks without `split` · H70 ✗ `derive_ext` without splitting · H71 ✓ a
  module-level import and positional construction · H72 the walker builds the provider’s
  record

**The loop’s own instruments** — rows that decide how every other row is judged.

- H16 ✓ measure a real corpus · H55 ✓ one corpus for every checkpoint · H49 the four
  unrecorded regimes
- H38 what counts as acting a row into view · H3 ✗ the sweep’s request rate
- H85 (closed) a release candidate against every hard gate

**How a transition looks** — the November 11 campaign: a switch that paints at once and
nothing that moves after it.

- H86 reserve every region’s box at first paint · H87 immutable asset headers
- H88 keep Git comparisons and memoize git routes · H89 parallel serial loaders
- H90 (superseded) a render cache and a kept Markdown worker · H91 four small shift
  fixes
- H92 one read per PR selection, file trees that open once, a held Changes paint
- H93 admission control for background work · H94 one prepare unit per subject
- H95 → H112 retained main-tab surfaces · H96 → H118 a shorter landing chain · H97 first
  view without visibility
- H98 → H112 a detached surface LRU · H99 laid-out view tabs (a → H112) and chunked
  source · H100 → H112 one layout per Markdown mount
- H101 highlighting in a worker · H102 a persistent render cache · H103 → H115 no
  loopback compression
- H104 a bulk Pulls walk · H105 → H112 pre-mounted view tabs · H106 a PR body final at
  first paint
- H108 (re-scoped) a Changes screen prepared before the click · H109 capped preloads ·
  H110 low-priority preloads · H111 a frame before diff enhancement

**What every transition or window open pays** — the structural costs the architecture
review found.

- H112 one surface store · H113 Markdown render by `GET` · H114 a pull request’s first
  screen in one answer
- H115 encode once, or not at all · H116 one Git process per comparison
- H117 a resident server and shell · H118 landing data starts with the document

| # | Hypothesis | Metric that would show it | Status |
| --- | --- | --- | --- |
| H1 | The prefetched libraries start on `DOMContentLoaded`, which is the same window as the first `/api/tree` fetch and the tree render, so they compete with the tree and hold the `load` event open behind them. Starting them on the first idle callback removes both. | `load_ms` down; `first_row_ms` down | **Half confirmed** (exp-001). `load_ms` 3,883 ms to 750 ms on ranges that do not overlap. `first_row_ms` did not move: 854 ms against 999 ms on ranges that overlap almost completely. Accepted on the tier policy and `load`, not on the row |
| H2 | The idle sweep that warms collapsed folders is not viewport-bounded and re-arms on every index refresh, so on a wide tree it requests folders the reader cannot see, for as long as the scan runs. Bounding it to the viewport ends the tail. | `last_resource_ms` and `subtree_requests` down sharply; `first_row_ms` unchanged or down | **Confirmed** (exp-002). 32 requests and 1,566 KB to 0 and 517 KB per cold load at 300,000 files, on ranges that do not overlap. Expanding a folder still warms exactly its newly visible children, and the click after that costs no fetch and paints in 93 ms. Time to first row did not measurably change and is not claimed |
| H3 | That sweep issues one request per ~800 ms, which does not follow from `SUBTREE_PREFETCH_MAX_CONCURRENT = 3` over a 32-path sweep. Something serializes it, and the policy should not be changed before that is known. | A counted sweep: paths per sweep and sweeps per second | **Unresolved** (exp-002), and the bound landed without it because H2 does not depend on it. Instrumented, the sweep does what it says: one sweep, 32 paths, all issued inside 545-690 ms — against a settled index, against a scan with 12.9 s left, and on both sides of the prefetch-tier change. The trickle was recorded when the corpus had not been served for a while and its walk took ~29 s against 2.7 s warm, so reproducing it needs a cold page cache, which needs root on macOS |
| H4 | `/api/catalog` is 4.5 MB at 100,000 files and nothing reads it until the finder opens, so it competes for connections and main thread during the first seconds. Moving it to the on-demand tier frees that window. | `first_row_ms` down; `transferred_kb` down | **Untestable as stated** on this corpus. `/api/catalog` is 62 bytes at 300,000 `build_corpus` files, not 4.5 MB — the catalog fills from recognized file kinds, and a synthetic tree of stub `.py`/`.ts`/`.png` files produces almost none. A real repository corpus has to reproduce the size before the tier change can be measured at all; exp-034 later measured a 15.9 MB body at 300,000 rows on the flat shape-2 corpus (`mb-qtgj`), which can. The buffering policy a deferred first fetch needs exists: `hold()` in `catalog-feed.js` journals nothing while held and `release()` starts an authoritative fetch. It is applied on a pull-request page; applying it to the finder is `mb-296z` |
| H5 | The root `/api/tree` costs more server time while the walk runs than when it is idle, and the cost is contention with the walker, not response size. Registered at 620-721 ms during a walk, before H23 and H27 took the tally pass off the row request; restated on 2026-11-14 onto `mb-3s45`’s measurement: on project-10, exp-034 recorded 1 (1-3) ms on v0.9.1 against 39 (9-44) ms on the v0.10.0 candidate, `main` at `03fd7997`, every pair past 1.3x. | `tree_fetch_srv_ms` on the root `/api/tree` during a walk, sampled across the scan by `run.py probe-server`, down, with server-side attribution | **Open** (`mb-3s45`). H2, which it once waited behind, was confirmed in exp-002. The mechanism `mb-3s45` names is the provider read: eight loop iterations and a worker hop through the coordinator, each a wait on the walker’s GIL slices. First blocker: re-measure on current `main` with `run.py probe-server`, since exp-034 measured the v0.10.0 candidate |
| H6 | Nav rows are gated on scan completion, so the first row waits seconds for data the browser already has. | `first_row_ms` down several-fold | **Not reproduced** as stated. On `build_corpus` at 100,000 files the first row lands at a median of 854 ms, not the 4,525 ms this plan’s Background reports from a different corpus. `renderFilesFromTree` runs as soon as `/api/tree` resolves, so the gate is that request rather than scan completion. `mb-op70` closed on 2026-11-01 on this result and H20’s inline; the root route’s cost under a walk is H5’s (`mb-3s45`) |
| H7 | The tree renders every row it knows about, so DOM node count follows the corpus rather than the viewport. | `dom_nodes` bounded as corpus grows | **Open** (`mb-z7zb`). **The fix is a windowed renderer** over a flattened visible-rows array, capping the DOM at about three screens permanently; `TREE_PAGE_SIZE` caps only the *initial* mount, so a reader who expands and pages still accumulates unbounded nodes. `content-visibility: auto` on subtree containers is the cheap intermediate. Pairing either with a Web Worker that owns JSON parsing and the tree merge moves the remaining main-thread blocking off the interaction path. 3,735 nodes at 100,000 files on `build_corpus`, well under the ceiling — the shape that produced 276,789 nodes needs a wider corpus to reproduce, and that corpus is the first blocker |

### The Backlog

Nine more, from measuring the first two rounds rather than from reading the code.
Ordered by the evidence behind them, not by where they sit in the stack.

| # | Hypothesis | Metric that would show it | Status |
| --- | --- | --- | --- |
| H8 | During a scan, every root `/api/tree` pays a full navigation-tally pass. Measured: 1,567 ms scanning against 15 ms settled for the same 7,537-byte answer, and `?depth=1` (987 bytes) costs the same — so it is not payload, depth, or aggregation. The mechanism is in the code: `navigation_tallies` memoizes on the index revision (`inventory.py`), the walker moves that revision with every write, so while scanning the memo can never hit and each root request redoes the O(index) pass (~486 ms/100k per its own comment, plus an `entries()` snapshot copy per request). Serving slightly stale tallies during a scan — recompute at most every N ms, or only when files-indexed has moved by a threshold — removes ~85% of time to first row in that regime. | `load_tree_ms` and `tree_reprobe_ms` while `index_status_at_probe` is `scanning`; floor 15 ms | **Partly resolved** (exp-003). H23 was the mechanism and it landed: root `/api/tree` fell from 650 ms to 394 ms scanning and 12 ms to 6 ms settled. What the split never described, and what exp-003 makes explicit, is the *first* request of a page load — its memo is cold by construction, so `load_tree_ms` did not move. That is H20’s job, not this one. What is left for H8 itself is the GIL share taken by per-entry stores (H22) |
| H9 | The shell fetches **74 separate JavaScript files** on every load — 33 from `static/`, 41 from built-in plugins — over HTTP/1.1, so they queue six at a time, and `app.js` cannot ask for the tree until its own chain has run. | Shell boot, as `first_row_ms` minus `load_tree_ms`; about 180 ms today | **Fixed and gated** (exp-014). Manifest-owned plugin assets load for the selected kind; search, keyboard Help, and Git tools load after the first usable tree. The directory scenario fell from 74 startup scripts / 337 KB to 33 / 214 KB and then 22 / 154 KB. Hard ceilings of 25 / 220 (raised from 175 in exp-084) prevent either eager tier from returning, `shell_tools_missing = 0` proves the deferred controls initialized, and `file_catalog_incomplete = 0` proves their delayed feed converged after any stream-ordering race. No bundler was added |
| H10 | Twelve render-blocking stylesheets, eight of them per-plugin, sit between the HTML and first paint. | First contentful paint | **The asset mechanism is fixed; the literal FCP comparison remains open** (exp-014). Plugin styles load with their selected kind, reducing stylesheet transfer from 80 KB to 73 KB. The final candidate FCP is nevertheless 146 ms (124–172), against 114 ms (96–116) for the installed release. H57 now attributes the remaining cold-start queue instead of calling the asset count a complete FCP result |
| H11 | The tree re-render replaces the whole `#tab-files` panel with `innerHTML` rather than patching it, so every refresh rebuilds every row. | A long-task measure around `renderTreeNodes:root`; 52 ms at 334 rows today | **Fixed and gated** (exp-014, `mb-izxl`). The first fetched snapshot reconciles through keyed visible containers instead of replacing the inline tree. Collapsed descendants stay in `subtreeCache` rather than hidden DOM. A 250-entry root reconciled its maximum mounted page in 9 ms; the project-shaped 111,590-file corpus recorded one root build and a 1–2 ms reconciliation |
| H12 | `/api/recent` is 68,748 bytes and 86 ms settled, and a recency filter puts it on the load path. | `first_row_ms` with a recency filter active | **Retired** (2026-11-14): no load has a recency filter, so the path does not exist; the evidence is in [Considered and Deliberately Not Registered](#considered-and-deliberately-not-registered) |
| H13 | The walk runs at about **43 µs per file** — 300,000 files in 12,871 ms — and nobody has attributed that number. | Walk elapsed per file, by layer | **Merged into H18** (`mb-migx`), whose profile is the same attribution |
| H14 | Start-to-serving scales with the tree rather than with the code. | CLI start to first served request, across corpus sizes | Open (`mb-kp6c`, `mb-lv46`). It was ordered after H8, because a client that waits 1.5 s on a lock makes every server cost look like scan cost; H23 removed that wait (exp-003). One mechanism that scales with the tree is named: serving waits for watcher registration, so the socket opens late on a deep tree (`mb-lv46`). First blocker: a deep-against-shallow start pair with `startup_pairs.py` |
| H15 | `INVENTORY_MAX_FILES = 500_000` truncates a larger tree and says so only in a banner. | Correctness, not speed | Open (`mb-s5p6`). Needs H18’s attribution first (H13 merged into it, `mb-migx`): replacing a cap means knowing what the cap was buying. It also needs a corpus above 500,000 files |
| H16 | Time to first row on a real repository does not behave like time to first row on `build_corpus`, whose 972 directories are uniformly wide and whose files are stubs. | Every metric, against a checked-out repository of comparable size | **Confirmed, and worse than stated** (exp-005). A real tree has 2.4 files per directory against `build_corpus`’s 309 — a 128× difference in how often every per-directory cost is paid, invisible to every measurement before it. It surfaced H30, H31, and H32, and it showed exp-004’s headline result to be conditional on a warm index |
| H17 | Importing `metabrowser.server` costs 390-770 ms before any walk — `python -X importtime`: kpress ~74 ms, `plugin_loader.manifest` + pydantic model construction ~60 ms, `plugin_api` ~45 ms, `classify` ~57 ms, `inventory` ~38 ms, `activity` ~30 ms — and `discover_plugins` runs at module scope (`server.py`), so manifest validation is paid at import. Deferring plugin discovery and the kpress import off the serving path cuts CLI start-to-serving by most of its fixed half. | `importtime` totals, and `bench_serving.py` start-to-serving | Open (`mb-kp6c` carries the attribution). The plan’s earlier “113 ms module import” undercounts on this machine by 3-6x. The 390-770 ms records no bytecode state, and the runbook now measures every build in one ([Start-Up Work, in Pairs](../../../../explorations/performance-loop/README.md#start-up-work-in-pairs)), so it is not a baseline. exp-037 deferred the Git imports a plain folder does not use; `discover_plugins` still runs at module scope (`_DISCOVERY` in `server.py`). **Attribution only** since the [architecture review](../../research/research-2026-11-14-performance-architecture-review.md): its probe imported 592 modules in 0.41-0.45 s with bytecode and 0.92 s without, the largest self time about 20 ms, so no single import is worth cutting, and H117 takes the cost off the click. First blocker: a re-baseline with `startup_pairs.py` in its `cached` bytecode state |
| H18 | The walk costs ~43 µs/file (300,000 files in 12,871 ms warm), and the structure says where: one `to_thread` per directory is cheap (972 hops), but every entry is yielded one at a time through an async generator onto the event loop, and each write updates the index and moves the rollup revision. Batching emission per directory — one loop hop per directory instead of per file — cuts walk elapsed materially, and also slows the revision churn that H8 depends on. | `inventory walker complete: elapsed=` in the server log, same corpus warm | **Demoted** (2026-11-14), with the scan-and-walker loop: the [architecture review](../../research/research-2026-11-14-performance-architecture-review.md) found its costs are CPython’s, which the [Python inventory engine](../../architecture/arch-inventory-engine-python.md) document measures on CPython alone, so U3 (`mb-wb7e`, fdu against the Python provider) decides first whether to spend on it. Open (`mb-nbc6`, with H13’s attribution, `mb-migx`). Attribution first (profile one walk), then the batch change as its own experiment. The [flat-tree plan](plan-2026-09-15-flat-tree-delivery-cost.md) has since bounded it: bare traversal is 0.87 s warm against a 12.9-15.5 s detached walk on the 300k flat corpus, so about 93% of the walk is Python above the filesystem, and delivery decomposes to 13.86 µs per entry. The structure, re-read on 2026-11-14: one async-generator yield per entry, one `_store_walker_entry` per entry on the serving event loop with an O(depth) ancestor-aggregate update per file, emits batched at 256 (`INVENTORY_WALKER_EMIT_BATCH`), one `to_thread` hop per directory, and `dataclasses.replace` only in the walker’s per-directory finalize, since H65 (exp-024) made the per-entry write-token copy positional. First blocker: the per-layer profile of the current build’s detached walk at the cap size (`scan_bench.py inproc --profile`). H22 is the batch-everything experiment this predicts |
| H19 | `/api/events` blocked 3,669 ms in the original waterfall before any row appeared. Never re-observed under the fixed harness, and the original was taken in the same degenerate pane as H6, so it may be an artifact. | The events stream’s time-to-first-message during a scan, from the resource timing of the EventSource | **Retired** (2026-11-14; `mb-fhfh`): the stream opens after the first tree request and the inline rows, so it cannot gate the first row; the evidence is in [Considered and Deliberately Not Registered](#considered-and-deliberately-not-registered) |
| H20 | The first tree paint waits for a round trip it does not need. `first_row_ms` is `DOMContentLoaded` (~180 ms) plus `loadTree` (850–1,500+ ms during a scan), yet the index handler could embed the root’s depth-1 entries as inline JSON — from the warm index, or from one synchronous `scandir` of the root, which is single-digit milliseconds — and let the client render rows at DCL and reconcile when `/api/tree` lands. The shell already server-renders the Files panel chrome for exactly this reason; the first data should ride the same vehicle. | `first_row_ms` ≈ FCP + render at every corpus size and in both scan regimes | **Confirmed** (exp-004). 1,604 ms to 242 ms at 300,000 files, non-overlapping, and `first_row_ms` now tracks `dcl_ms` almost exactly — the tree is usable at DOMContentLoaded rather than one slow round trip later. Main-thread blocking fell with it, 268 ms to 65 ms. Cost: 34 KB, being the inline payload plus the thirteen now-visible folders exp-002’s sweep correctly warms. Inline only the unfiltered default view, so filter state cannot diverge |
| H21 | The “no persisted index” non-goal is priced wrong for a *browsing* tool, whose common case is reopening the same tree. Persist the index at walk end and load it on start, serving stale-labeled data instantly while a revalidation walk runs — the UX contract for staleness already exists (`tally_cache_status=scanning`), and fdu proved the snapshot-plus-revalidate pattern on the same machine. The plan deferred this “until the progressive path exists”; it now exists. | Start-to-usable-tree on a revisit of a 1M-file tree: seconds to sub-second. Cold first visit unchanged | **Waits on U3** (`mb-wb7e`, fdu against the Python provider), as the [architecture review](../../research/research-2026-11-14-performance-architecture-review.md) orders it. Open, large (`mb-omhf`). The biggest single lever at large N. **The invalidation story is a bounded revalidation**: a directory’s mtime moves when its direct children change, so the sweep `stat`s only directories and rescans only the subtrees that moved — git’s untracked-cache mechanism, and what separates a revalidation from a second full walk. H46 accelerates that sweep per platform; H49 supplies the warm-reopen metric it would be scored against. Three predictions worth scoring it on: loading 300,000 entries costs around 100 ms, a warm reopen reaches first row within twice the shell’s own paint time, and the sweep finds under 1% of directories changed on a typical revisit — if the last is false the approach is worth much less, and one measurement says so. Needs an invalidation story (mtime-revalidate per directory, walk in background) and a format decision measured for load cost. First blocker: H49’s warm-reopen adapter (`mb-609b`), which supplies the metric it is scored on |
| H22 | The walk’s ~43 µs/file is mostly per-entry Python by construction, not filesystem cost: every entry crosses an async-generator boundary one at a time, is stored by a per-entry call on the serving event loop, and updates ancestor aggregates O(depth) per *file* — while the walker already computes per-directory aggregates at finalize, so the per-file propagation is double bookkeeping. Batching the pipeline per directory (yield lists, store lists, one ancestor update per directory) removes ~300,000 loop iterations and most per-entry overhead per scan. | Walk elapsed down 2×+ at 300k; event-loop availability during scan up (measured as during-scan `/api/tree` latency with H23 already in place) | **Demoted** (2026-11-14), with the scan-and-walker loop, for the reason H18 gives: U3 (`mb-wb7e`) decides first. Open (`mb-tip8`, blocked by H18’s `mb-nbc6`). Do H18’s profile first so the before is attributed, then land as one structural experiment |
| H23 | During a scan, every root `/api/tree` recomputes navigation tallies over the whole index because the memo keys on `rollup_revision()`, which advances on every write — at 256-entry batches and ~23k entries/s that is ~90 revisions/s, so the memo cannot hit until the walk ends. The docstring itself prices the pass at ~2 s at 400k entries. Serve tallies at bounded staleness during a scan: recompute at most once per window, single-flight, reuse between. The payload already labels them provisional. | Root `/api/tree` during a scan: 837–1,567 ms → near-settled (~15–50 ms); `first_row_ms` during scan drops by most of a second | **Confirmed** (exp-003), and it found a second O(N) cost the hypothesis missed: the route copied every index entry on the *event loop* before the pass it fed even started. Bound is `max(0.5 s, last pass cost)` — derived rather than constant, because the pass visits every entry and a constant right at 10,000 files starves the loop at a million. A fixed 0.5 s reached only 518 ms (the nav polls at 1 s, so a shorter bound can never be hit by a poller); request-triggered background warming was measured and rejected |
| H24 | The client runs two progress channels at once through the scan — the 1 s `/api/index/progress` poll *and* the SSE stream that already pushes completion — and each poll can trigger a depth-0 tree refetch and a full re-render (H11), all landing in the window where the server is busiest. Consolidate progress onto the stream it already holds, keep the poll as a fallback only. | Requests issued during a 13 s scan; `renderTreeNodes:root` span count during scan | Open (`mb-n352`). Pairs with H11, which exp-014 resolved: a fetched snapshot now reconciles keyed rows instead of re-rendering the panel, so what remains here is the requests themselves, the 1 s poll beside the stream. H28 would absorb it. First blocker: a requests-during-scan metric |
| H25 | `/api/tree` re-serializes and re-gzips an unchanged answer for every poller and every tab; `/api/rollup` already keeps an encoded-body cache keyed by ETag for exactly this. Give the tree route the same (revision, params)-keyed body cache and validator. | Settled root `/api/tree`: ~15 ms → ~1 ms; multi-tab during scan shares one encode | Open, small and mechanical (`mb-43v7`) — worth batching with H45, which replaces the encoder whose output this would cache, and see H44 for `zstd` and for keying the cache per revision. H23 landed in exp-003, so there is no longer a tally change to batch it with. The campaign plan runs it in the remote-link loop, after H44 and H29 |
| H26 | The eager request count is priced at localhost, where ~110 requests over six HTTP/1.1 connections cost little; `metab --remote` tunnels the same page over SSH, where ~19 serial connection-rounds × RTT land before the first API call — at 50 ms RTT, roughly a second of shell alone. One measured `--remote` (or throttled) load would set the real stake for H9/H10, and a server-side concat of the eager `static/*.js` in tag order — no bundler, tier policy intact — is the count fix if it matters. | Shell-ready time over a ≥50 ms RTT link, before vs after count reduction | **Merged into H44** (`mb-f591`, closed as a duplicate of `mb-ycf2`); the server-side concatenation it names is H96 (`mb-a1nu`), whose remote value is judged in H44’s regime |
| H27 | Even with the staleness bound, the *first* root request during a scan pays the cold tally pass — `load_tree_ms` stayed near a second in exp-003/004 while the repeat-request cost fell to 394 ms — because the response couples cheap rows to an O(index) computation in one JSON body. Decouple them: the tree responds with rows immediately and the tallies arrive separately (a second cheap request, or the stream). `updateFilterTallies` already guards every field, so a payload without tallies is tolerated today. | `load_tree_ms` during a scan → tens of ms; filter counts fill in behind it | **Confirmed** (exp-007). A row request now serves tallies only from a fresh memo; `depth=0` is the channel that computes them, fetched behind the render by the `scheduleRootSummaryRefresh` that already existed. 311 ms to 2 ms on the official corpus, 777 ms to 6 ms and 67 ms to 1 ms on the two real trees, all non-overlapping. Nothing was made faster — the expensive work was moved off the path that did not need it |
| H28 | The tree is delivered as snapshots the client re-fetches on a poll, then re-renders wholesale — while the walker already publishes `fs.change` ops on the SSE stream the page holds open, scoped to `root-depth-2`, which is exactly the rows the nav renders. Build the tree progressively from the stream: insert rows as they are discovered, and drop the poll-triggered refetch loop. Absorbs the H11 (patch-not-replace) and H24 (two progress channels) directions into the change that makes both moot. | `renderTreeNodes:root` span count during a scan → per-batch bounded inserts; snapshot refetches during a scan → 0; on a large tree the nav visibly fills in live | Open, large (`mb-ap6p`). **The tallies belong on that same stream**: the nav polls `depth=0` about once a second per tab and the whole staleness apparatus exists to survive that poll, so pushing tally updates alongside the `fs.change` ops — throttled to a couple per second during a scan — retires the poll, the per-tab request rate, and the GIL contention exp-005 found. A client fetch becomes subscribe, then backfill since revision R; H36 (now merged into H34) is the cheap version of the same observation. The full streamed-delivery design revisit. H27 proved the decoupling on the simpler payload (exp-007), and part of the stream half exists: each `fs.change` op patches its rendered row, and inserts one under a rendered, expanded parent (`app.js`). First blocker: re-scoping the row to what remains, the snapshot refetch and the tally poll, absorbing H24 |
| H29 | The shell blocks its first byte on `discover_repository_context` (a filesystem walk up plus config parse, off-thread but serial) and then ships as one buffered response — so the browser cannot start fetching CSS or JS until Python has finished building the whole page. Flush the head early and move repository context out of the pre-first-byte path. | Time from request to first stylesheet fetch; shell-ready over a ≥50 ms RTT link | Open (`mb-pk2l`). Pair with H44’s remote measurement (H26 merged into it) — on localhost the whole shell is ~200 ms and the win may be invisible. The link exists: `tier-probe.mjs --network` emulates one under every load. First blocker: H44’s measurement. The local half, the shell’s own server time with repository context memoized, is now part of H118 |
| H30 | `build_gitignore_check` costs 19.4-23.3 s on a real 241,000-file tree, before the walk starts and therefore before any row can exist — larger than the 21.0 s walk it precedes. Nothing in this plan accounted for it, and no browser metric shows it: the page loads fine with nothing to put in it. | Time from process start to the first entry existing | **Resolved** (`mb-mnj1`). exp-006 pruned the pre-walk, but on a real repository it still visited 40,832 directories to find 25 `.gitignore` files and held back the first rows for 9-34 s. The pre-walk is gone: each directory’s `.gitignore` is read the first time a path inside it is checked, so the breadth-first walk starts at once. First root rows on that repository fell from 7.1-13.2 s to 1.0-1.8 s after process start, interleaved under load, and verdicts match `git check-ignore` |
| H31 | Watching a scan makes it twelve times slower. Measured warm on a real tree: 21.0 s unattached against 258.3 s with one client polling every 2 s. Each nav request costs a tally pass that grows with the index (0.75 s at 120,000 entries, 1.5 s at 241,000), that work competes with the walker for the GIL, the walk slows, the window lengthens, and more polls land inside it — each more expensive than the last. A real browser is a heavier client than the probe. | `walk_elapsed_ms` attached against unattached | **Partly resolved** (exp-007), from the other end than expected. Removing the per-request tally cost cut the attached walk on the real tree from 70.2 s to 50.0 s without touching the walker: the requests were not only slow, they were taking CPU the walk wanted. With exp-006 the attached walk is 258 s to 50 s. What remains (`mb-jalf`) is whether a real browser — heavier than the probe — still amplifies; exp-034 measured the attached walk on the 300k flat corpus at 1.62-1.78x v0.9.1, against 1.13-1.30x for the backend’s own index completion (`mb-qvw4`) |
| H32 | exp-004’s inline fires only when `inventory_has_data()`, and on a first open of a real tree the index is empty at page-render time — behind H30’s twenty seconds. The probe recorded `inline_rows: null`. So a result measured as 1,604 ms to 242 ms is conditional on a warm index: it helps a second load and not a first open, which is the case it was built for. | `inline_rows` non-null, and `first_row_ms`, on a *first* open of a real tree | **Resolved** by H30 (`mb-mnj1`). With no pre-walk, the root’s children are indexed within one `scandir` of the walk starting, so the inline carries rows on a first open (0.1-0.3 s after the server answers) |
| H33 | Ignored subtrees are usually the bulk of a real tree and the least interesting: one keeps 232,190 files under two `target` directories. Crawling everything but ordering the frontier so tracked entries are discovered and published first would give a reader a usable tree in a fraction of the total scan. Flags still control what is revealed; only the order changes. | Time until all *tracked* entries are indexed, against total walk; `first_row_ms` unchanged or better | **Demoted** (2026-11-14), with the scan-and-walker loop, for the reason H18 gives: U3 (`mb-wb7e`) decides first. Open, **P0** (`mb-6yh2`). Sized after exp-006: 48% of files and 59% of directory yields are ignored, and the last *tracked* file is seen at 29.94 s of a 30.06 s walk — level order interleaves the two completely, so the tracked tree is never ready early. BFS already yields a directory placeholder before enqueueing it, so the nav’s *shape* is complete long before its contents; only the descent needs reordering, into a secondary queue drained after the tracked frontier. First blocker: a “tracked entries indexed at” metric, which neither `run.py` nor `scan_bench.py` records |
| H34 | The tallies are sums over per-entry attributes, and every mutation already funnels through `_replace_index_entry` / `_pop_index_entry` under one lock. Maintaining them incrementally there makes the pass O(1) amortized and retires the whole staleness apparatus: no memo, no bound, no derived-cost heuristic, no residual GIL contention with the walker. | `srv_scanning_ms` at its floor with the memo deleted entirely | **Demoted** (2026-11-14), with the scan-and-walker loop, for the reason H18 gives: U3 (`mb-wb7e`) decides first. Open, **P1** (`mb-0cmt`). exp-003 and exp-007 both work around this cost; this is the fix the bound is standing in for. H36, its cheap half, is merged into it as its fallback. #413 made one pass about 4x cheaper in the meantime (`mb-0cmt`’s notes) |
| H35 | On a git working tree, `git ls-files -co --exclude-standard -z` returns the visible set directly, in C, with git’s exact semantics — including the negation cases the current `rel_dir` prefixing gets wrong. | Time from process start to the first entry existing; and the negation cases the prefixing mis-answers | **Superseded** by H30 (`mb-mnj1`; `mb-9ge2` is closed). The first-rows half is resolved by H30 without git; hierarchical matching also fixed the negation and nested-pattern mismatches. What remains is walk speed, which H39 (`mb-8yqt`) should price first and the fdu provider (`mb-hej8`, which supersedes H40) would change |
| H36 | The tally pass still runs in a thread that is GIL-bound Python competing with the walker, just less often. Serving the last memo regardless of age while the status reports scanning — recomputing once on completion — removes the rest, and the client is already told those numbers are provisional. | `walk_elapsed_ms` attached against unattached | **Merged into H34** (`mb-26ey`), as its cheap fallback |
| H37 | `os.path.relpath(str(here / name), str(root))` builds two `Path` objects and normalizes a path for every directory the prune considers. `os.walk` is top-down, so the parent’s relative path is in hand and the child’s is a string concat. | `gitignore_build_ms` on a tree with hundreds of thousands of directories | **Obsolete** (`mb-n3is`). The prune loop was removed with the pre-walk (H30) |
| H38 | Scroll and expand cover the two ways a reader *acts* a row into view. A window resize or a pane-splitter drag also reveals rows and re-arms nothing, so enlarging the window leaves the newly revealed folders cold until the reader scrolls. | `subtree_requests` after a resize that reveals rows | Open (`mb-r391`). First blocker: a resize scenario |
| H39 | What remains of the walk may be pattern *matching* rather than traversal: the ignore check runs per entry, and nobody has measured what the matcher costs. Price it before replacing the walker. | `walk_elapsed_ms` with and without `gitignore_check` | **Demoted** (2026-11-14), with the scan-and-walker loop, for the reason H18 gives: U3 (`mb-wb7e`) decides first. Open, **P0** (`mb-8yqt`). Attribution, and it gates H40: replacing a traversal that is not the bottleneck would be the expensive way to learn this. Registered when exp-006 had cut a compiled pattern set from 10,668 to 327; H30 then removed that set, and the matcher is now `HierarchicalGitIgnore` (`ignore_filter.py`), which applies each `.gitignore` on an entry’s ancestor chain, read lazily and under one lock. First blocker: a toggle in `scan_bench.py`; the walker already accepts `gitignore_check=None` |
| H40 | A native parallel walker over ripgrep’s ignore crate would collapse the scan by an order of magnitude, because the walk is per-entry Python competing with itself under one GIL. | `walk_elapsed_ms` on the real tree | **Superseded by fdu provider adoption** (`mb-hej8`; `mb-nbvk` was this row’s bead). A second native walker would duplicate the provider the [fdu adoption plan](plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md) builds, whose Checkpoints 2C and 2D are unstarted. The adoption takes no number here: that plan carries it, and U3 (`mb-wb7e`) measures fdu against the Python provider first |
| H41 | A columnar index makes the tally pass vectorized rather than a per-entry Python loop, cheap enough to delete the memo, the bound, and the derived-cost heuristic outright. | Tally pass duration at 300,000 and 1,000,000 entries | Open (`mb-od5n`). The heavier alternative to H34, so it waits on H34’s result |
| H42 | A client-side tree replica painted before the server answers makes a revisit cost no network on the critical path. | `first_row_ms` on a revisit, offline | **Retired** (2026-11-14; `mb-6rdn` closed as canceled), on the architecture review’s reason in [Considered and Deliberately Not Registered](#considered-and-deliberately-not-registered) |
| H43 | Walking the viewport’s subtree first makes the visible tree correct long before the scan ends — the reader’s question is answered by a fraction of the work. | Time until the on-screen subtree stops changing | **Demoted** (2026-11-14), with the scan-and-walker loop, for the reason H18 gives: U3 (`mb-wb7e`) decides first. Open (`mb-w2f3`). Composes with H33, which orders tracked before ignored; this orders visible before the rest. A bounded side refresh of requested paths the index does not yet hold exists (`prioritize()` in `python_inventory.py`); the walk’s own order does not change. After H33 |
| H44 | Under realistic latency, batching the subtree prefetch into one request beats every server-side win so far, because ~110 requests over six HTTP/1.1 connections is priced at localhost and paid in RTTs. | `first_row_ms` and total prefetch time at 0 ms and 120 ms RTT | Open, **P0** (`mb-ycf2`). Supersedes the framing of H26, now merged into it, by adding the engineering, not just the measurement. The ~110 requests is the count at registration; the startup scripts were 20 at `27ea216c`, gated at 25 (exp-084). The RTT knob exists, `tier-probe.mjs --network`, and exp-084 read a folder page’s first row at 514.1 ms over an 80 ms link against 92.4 ms on loopback, for its startup-script series rather than for prefetch. First blocker: a prefetch-total metric and a batched `/api/trees` prototype. Three changes follow if it holds: one `/api/trees?paths=...` request in place of up to 32; offering `zstd`, which current Chrome and Firefox accept and which beats gzip-6 for less CPU; and extending H25’s encoded-body cache per revision so a settled index serves bytes it compressed once |
| H45 | Serialization is a measurable share of large tree and rollup responses, and `orjson` would show it. | Server time on `/api/tree` and `/api/rollup` at 300,000 entries | Open (`mb-0l4a`). The server still encodes with the standard library’s `json`. First blocker: `orjson` is a new third-party dependency, so it needs the supply-chain review first |
| H46 | Bulk-attribute syscalls cut the verification sweep that H21’s persisted index would depend on: `getattrlistbulk` on macOS returns attributes for many directory entries in one call, `io_uring` batches `statx` on Linux, and on Windows the USN journal replaces the sweep with a change feed. | Verify-sweep duration on an unchanged 241,000-file tree | **Waits on U3** (`mb-wb7e`), as H21 does. Open (`mb-19em`). Only matters once H21 exists |
| H47 | A 64-worker executor sized for I/O waiters hurts the CPU-bound work now routed through it: under one GIL, more workers is more contention, not more throughput. | Tally and encode latency, and walk time, against pool size | **Demoted** (2026-11-14), with the scan-and-walker loop, for the reason H18 gives: U3 (`mb-wb7e`) decides first. Open (`mb-squq`). The pool is still `DEFAULT_EXECUTOR_WORKERS = 64` (`settings.py`). First blocker: a pool-size knob for the measurement |
| H48 | A free-threaded build makes the existing thread offloads actually parallel — and would surface every shared-state assumption the GIL is currently hiding, including the one the F2 finding exposed. | Attached `walk_elapsed_ms` and tally latency on 3.14t against 3.14 | **Shared state audited; speed unmeasured** (`mb-ltm2`). The release-readiness audit exercised shared inventory, rollup, watcher, catalog, HTTP teardown, and task ownership paths on CPython 3.14.7t. The 3.14t-against-3.14 timing comparison has not been run |
| H49 | The four unmeasured regimes hide regressions the cold-load metric cannot see: interaction latency, churn recovery, resident size, and warm reopen. | Interaction latency, churn recovery, resident size, warm reopen | Open, **P0** (`mb-609b`). Harness 4 now records Event Timing, bounded retention, optional JS heap, and names progressive, steady-interaction, endurance, and warm-reopen loops in the reusable framework. The scenario runs and churn/reopen adapters remain; having fields is not the same as collecting their baselines |
| H50 | Two regions are rendered before they have content and grow when it arrives: the filter bar, shipped empty for `filter-controls.js` to fill, and the tally row, which paints with the inlined rows and gets its numbers from a later request. The page moves under the reader on every load. | `reserved_region_shift_px`, measured directly as populated height minus empty height | **Confirmed** (exp-009). 67 px together, now 23. Both reserve a line box of the type they hold rather than a measured constant, because the shell offers a choice of font sets. The filter bar is settled at zero; the tally row keeps 23 px because its settled height depends on its own content, which is H54 |
| H51 | The two metrics a browser would actually report — largest-contentful-paint and cumulative layout shift — were unmeasured because the old pane was hidden and collapsed to 0×0 on navigation. | `lcp_ms` and `cls`, non-null, from a visible window | **Confirmed and complete** (exp-014, `mb-qf2p`). Four admissible harness-14 runs per installed build stayed visible at 1600×900. Candidate LCP is 146 ms (124–172) against 212 ms (208–216); candidate CLS is 0 in every run. The direct frame and summary targets remain open because a good CLS is not proof of one final visual state |
| H52 | The shell ships placeholders, not a skeleton: the filter bar is empty, the files panel is “Loading files…”, the preview pane is one line of text. First paint is chrome plus three placeholders, each later replaced wholesale. Server-rendering resting-state chips and placeholder rows would make the structure look complete at first paint. | `frame_missing_px`, target 0. Baseline **532 px** on the fixed corpus at 1280×900, n=3 and identical across all three, all of it the files panel: 612 px settled against the 80 px the shell ships | Open, **P1** (`mb-rxst`). exp-009 stopped the page *moving*; this is what would stop it *assembling*. The obstacle is duplication — the chip markup lives only in `filter-controls.js`, so a server-side counterpart needs a shared source or it drifts. Two metrics have been retired from this row for being unfalsifiable. `skeleton_complete` asked whether each region was non-empty *at probe time*, which is after settle, and returned true on all ten runs ever recorded. `regions_non_empty` replaced it and repeated the mistake in subtler form: it read `textContent`, and the files panel ships a spinner and an `.sr-only` label, so the gap passed a floor check written to catch it. What remains is a distance rather than a predicate. The 532 px baseline, and the 615 px `mb-rxst` records from the reworked probe, were both taken on the 246,282-file project-10 build of exp-009, which a rebuild at a later commit does not reproduce, so the first blocker is a fresh baseline on the current corpus; the campaign plan runs it after H56 and H54 |
| H53 | The tree region is painted twice per load — inlined rows, then fetched rows — each a wholesale replacement of the whole panel. | Whole-region builds per load, target 1 | **Fixed for the tree region** (exp-014, `mb-t5x3`). The fetched answer now patches the standing keyed tree; `tree_region_repaints` remains 1 on both the project-shaped corpus and a 250-entry wide root. The metric deliberately counts whole-region builds, not ordinary cell updates, and is in `run.py compare` and `performance-budgets.toml`. Extending visual-state coverage to the preview pane and filter bar is H56’s viewport-wide `visual_states` |
| H54 | The tally row’s settled height depends on its own text: `.tree-summary-split` reports tracked and ignored files separately and wraps to a second line in a 300 px navigation pane, so no fixed reservation fits both states. A one-line floor leaves the wrap uncovered; a two-line floor leaves dead space whenever the row does not wrap. | `summary_shift_px` at 300 px and at a pane wide enough not to wrap, both zero, with no idle gap in either | Open, **P2** (`mb-w3va`). The remainder of exp-009: 23 px of the original 67. The fix is to make the pending row the same shape as the settled one — same classes, same cell count, placeholder glyphs sized like digits — so it wraps identically, rather than to raise the floor. Its instrument exists (`summary_shift_px` in `probe.js` and `run.py`); first blocker: a reserved experiment id, and the campaign plan runs it after H56 |
| H55 | The campaign’s numbers span seven corpora and none of them compare, so nothing says what all of it bought. Each round measured its own control against its own candidate, which is sound per round and is why the verdicts stand, but it leaves the campaign itself unmeasured. | Every checkpoint’s standing metrics against one corpus with one harness, in one table | **Confirmed** (exp-010, `mb-3a3h`). Answered by holding the corpus and the harness fixed and moving only `src/metabrowser`: first row 1,473 ms to 276, server share of the first tree fetch 1,099 ms to 6, tail 28.9 s to 12.3. It also surfaced two regressions no round could see from inside itself — repaints 1 to 2, and shift 42 px to 67 on main before this branch took it to 23 |
| H56 | `first_row_ms` rewards painting *something* early and says nothing about how many states follow it. The campaign drove it from 1,473 ms to 276 while repaints went 1 to 2, so the loop’s own primary metric is what steered it into placeholder-then-replace. The objective is one visual state in the viewport, and nothing measures that. | `visual_states`, the count of distinct painted viewport layouts between navigation and settle, target 1; `time_to_final_state` beside it | Open, **P1** (`mb-unt6`). The visible driver removes the environment blocker, and H51’s baseline is recorded (exp-014). It still needs an instrument for distinct visible states; `tree_region_repaints` is today’s partial proxy and covers one region. Most of that instrument now exists: the transition recorder reads every frame after layout and records blank, placeholder, and frames-to-ready counts, settle time, and region movement per transition (`transitions-recorder.mjs`, `transitions-stats.mjs`). First blocker: a `visual_states` count of distinct painted viewport layouts on the landing |
| H57 | The server is no longer the bottleneck and the shell’s own boot is, but nothing has attributed it. On the fixed corpus this branch answers the first tree request in 6 ms and paints no row until 276 ms; the ~270 ms in between is 126 requests and 742 KB of shell, unexamined. | Navigation to first row broken into connect, HTML, blocking CSS, JS parse, JS execute, and the inline render | **Attributed; optimization remains open** (exp-014, `mb-emhr`). The directory shell is now 22 startup scripts / 154 KB and the first-row ranges overlap the release, but FCP does not. A representative slow `app.js` fetch spends 130 ms to response start: 48.5 ms server work and roughly 81 ms local HTTP/1.1 queue, followed by 9 ms download. Bounded startup rows now retain this split. H44 (which absorbed H26) owns measuring whether server-side concatenation earns its complexity remotely; the local FCP delta keeps the same mechanism relevant here. `mb-emhr` closed on the attribution; the optimization half runs as H115 (`mb-9uyq`, which widened H103), since the same scripts sent uncompressed reached the first row 32 ms sooner on loopback (exp-084, `performance-budgets.toml`), then as H96’s concatenated startup scripts (`mb-a1nu`), after U2 |
| H58 | Main-thread work during load is bounded by the data, not by a budget. The UI thread should never be blocked by backend work: responsiveness independent of server latency, bandwidth, and tree size, tuned for a local server but not *depending* on one, so `--remote` over a tunnel shows content later rather than freezing. The invariant is constant-bounded synchronous slices however much data arrives — preserve exact operations across boundaries, coalesce events into one render of the latest state per frame, deadline-slice any inventory-sized loop, aggregate in a worker, and let speculation yield to interaction. | `long_task_max_ms` and `interaction_max_ms` between navigation and settle, from instrumentation attached at navigation, **measured visible**; target no task over 200 ms | **Confirmed, fixed, and gated** (exp-012, exp-014, and exp-016, `mb-y2ft`). The first record was void because `ever_hidden` was true. A visible run then named two versions of the same O(N) mistake: passive ignored-file sightings and live ignored-file updates were routed through directory-prefix removal, scanning the complete Quick File catalog once per exact leaf. The wire had combined exact ignored-file eviction with filesystem subtree removal, so the client could not choose correctly. `catalog.change.remove_files` now preserves exact semantics and both paths use `Map.delete`; only removals that may name a directory scan prefixes. Harness 15 continuously drives exact-count trusted input through client settle, freezes the product window before diagnostics, and separately gates readiness, final catalog authority, rendered errors, and page exceptions. Across four final installed-candidate profiles, inventory delivery totals 28–29 ms, its longest callback is 1–2 ms, its window share is 0.1%–0.5%, and every hard gate passes |
| H59 | `navigation_tallies_fresh_within` waits on the same lock an off-thread O(index) tally pass holds, so an overlapping tally request can stop the server event loop even though the expensive pass itself was offloaded. | `tally_overlap_progress_max_ms` while two depth-0 tally requests overlap, target less than 200 ms; plus a 1 ms in-process heartbeat under a controlled 350 ms lock hold, target less than 50 ms | **Confirmed and fixed** (exp-016, `mb-09xv`, `mb-gicx`). The controlled lookup took 352 ms. Across ten exact installed pairs on the unchanged 123,658-file fingerprinted project corpus, `c123ae6` takes 363.8–547.3 ms and the final candidate takes 52.4–156.0 ms, with identical ordered rows and tallies |
| H61 | Removing the memo-lock wait does not bound the worker’s GIL residency. If a cold tally pass stretches under host contention, its Python loop can still starve unrelated request work past the responsiveness budget. | `tally_overlap_progress_max_ms`, target less than 200 ms in every exact candidate run; deterministic 1 ms heartbeat while the interpreter switch interval is lengthened, target less than 50 ms | **Confirmed, fixed, and gated** (exp-016 and exp-019, `mb-1sa3`). Candidate `5a8f3ed` recorded four runs at 73.4–116.8 ms and one at 291.7 ms while its tally pass stretched to 928.9 ms. The original fix yielded every 2,048 entries; Linux CI later measured its deterministic heartbeat at 52.1 ms, so the release candidate tightened the cadence to every 1,024 entries without weakening the guard. Exact v0.8.0 comparison records 81.9–124.6 ms across five candidate runs, with identical ordered rows and tallies. The pass now yields every 256 entries (`_NAVIGATION_TALLY_COOPERATIVE_YIELD_BATCH` in `python_inventory.py`): exp-033 found a provider read pays the GIL wait once per loop iteration, eight times a request, and recorded 213–254 ms against the 200 ms budget at 1,024 |
| H62 | Initial walker upserts use the same yellow row flash as live filesystem changes, so rows painted while the navigation baseline is still forming look like newly created files. Keep highlighting disarmed through the initial snapshot and crawl, then arm it on the first terminal inventory signal. | A browser behavior test proves snapshot and pre-completion upserts stay neutral while the first post-completion insert flashes; the final visible comparison continues to pass every hard responsiveness and visual-stability gate | **Confirmed, fixed, and verified** (exp-016, `mb-ppvj`). Snapshot application explicitly suppresses the flash, walker changes read a completion-gated state, and both an already-complete snapshot and the ordered terminal capability event arm later live changes. All four exact candidate profiles pass every hard browser gate |
| H63 | A browser profile can be mechanically valid while the main panel is an error state or plugin scripts are throwing. A release measurement adapter can also change an internal namespace contract before the SDK loads, invalidating the control it is meant to observe. | `rendered_preview_errors` and `page_exceptions`, both required and zero; exact-tag asset provenance; external server isolation | **Confirmed, fixed, and gated** (exp-016, `mb-jtg8`). Harness 15 counts rendered preview errors and CDP `Runtime.exceptionThrown` events from navigation through export. The broken adapter now fails with one rendered error and eight exceptions. The rebuilt exact-tag v0.6.0 adapter preserves the release’s `metabrowserPerf` handoff, and all four admissible control and candidate profiles record zero for both fields. External builds run from the served root, and PID-plus-command verification replaces a broad process-name kill |
| H64 | Git revision navigation discards useful content before the next comparison is ready, and serial request and mount work makes the gap longer. Keep the prior revision visible through an atomic handoff, overlap independent work, and prepare one pointer-intended revision. | Blank frames, exact selection-to-painted-ready time, server/client phase spans, mounted diff count, and retained heap in a trusted-input Git scenario | **Confirmed and fixed** ([exp-018](../../../../explorations/performance-loop/experiments/exp-018-git-revisions-swap-without-blanking.md), `mb-fgcg`). Candidate scenarios record zero blank frames instead of 4–5 and pointer-prepared transitions fall from 209.7 ms (205.8–245.0) to 104.4 ms (99.6–109.2). Cold ranges overlap and support no speed claim. All runs finish on the exact revision with one mounted diff, unchanged retained heap, and no page exception |
| H65 | The walker stamps a write token on every entry with `dataclasses.replace`, which reads all twenty `FsEntry` fields back through string-keyed `getattr` and reruns the generated `__init__` over them. Building the copy positionally is the same constructor without the reflection. | `walk_to_settled_ms` on a 60,000-file corpus, measured in process | **Confirmed and fixed** ([exp-024](../../../../explorations/performance-loop/experiments/exp-024-the-walker-builds-each-entry-once.md)). 3.5 us to 1.3 us per copy; 1,847 ms to 1,653 on disjoint ranges |
| H66 | Leaf, file, and tracked-file aggregates hang off the same ancestor chain and the ordinary walker event moves all three by the same parent, so adjusting them separately climbs that chain three times. Netting the deltas per parent and climbing once removes two traversals in three. | `walk_to_settled_ms`, same corpus | **Rejected** (exp-024). 1,645 ms against 1,653 on overlapping ranges. The traversals it saved were paid back by the dict and closure allocated per entry to net them in. Right about the redundancy, wrong about where the time was |
| H67 | The walker’s add path — no existing entry, which is every entry of a first walk — has exactly one parent, so it needs no delta map at all. | `walk_to_settled_ms`, same corpus | **Confirmed and fixed** (exp-024). 1,645 ms to 1,277 on disjoint ranges, which is H66’s idea with the allocation removed from the path that never needed it |
| H68 | Every file in a directory climbs the same ancestor chain, so a 60,000-file tree re-derives a few thousand distinct chains once per file. Memoizing them removes roughly 240,000 `rsplit` calls. | `walk_to_settled_ms`, same corpus | **Rejected** ([exp-025](../../../../explorations/performance-loop/experiments/exp-025-the-instrument-was-measuring-the-order-it-ran-in.md)). 1,247 ms against 1,203, nominally slower on overlapping ranges. Shape 2 is four components deep, so `str.rsplit` at C speed costs about what a dict lookup and tuple iteration cost. Reverted |
| H69 | `require_canonical_inventory_path` runs 248,826 times per walk and its `split("/")` allocates a list each time; substring scans decide the same thing without allocating. | Per-call cost, then `walk_to_settled_ms` | **Refused before implementation** (exp-025). 1.05x on a deep path and 0.72x on a short one, because a short path costs less to split than to scan six times |
| H70 | `derive_ext` normalizes separators and splits a path out of what the walker passes as a bare filename, allocating twice per call before it starts. | Per-call cost, then `walk_to_settled_ms` | **Rejected** (exp-025). 1.11x, about 3 ms over 60,000 calls |
| H71 | `for_observed_file` imports `derive_ext` inside the function on every call and `_internal_entry` binds twenty keywords; a module-level import and positional construction remove both. | Per-call cost, then `walk_to_settled_ms` | **Confirmed in isolation, not separable at walk scale** (exp-025). 34 ms over 62,210 entries, against a spread of roughly 50 ms. Kept: one half deletes a function-level import |
| H72 | Every entry is built as a contract `InventoryEntry`, converted to the provider’s `FsEntry`, and converted back on read, so the walk constructs each entry twice and validates its path four times. Having the walker build the provider’s record directly removes one construction and two validations per entry. | `walk_to_settled_ms`, and the interleaved build comparison against `main` | **Demoted** (2026-11-14), with the scan-and-walker loop, for the reason H18 gives: U3 (`mb-wb7e`) decides first. **Walk half accepted** ([exp-026](../../../../explorations/performance-loop/experiments/exp-026-the-refactor-added-a-rule-that-forced-a-second-build.md)); open for the rest (`mb-kicj`, **P1**). The walker now builds the provider’s `FsEntry` directly and `_internal_entry` passes it through: zero `InventoryEntry` builds on the walk where the stack had done 62,210 for 61,105 entries, and the interleaved medians moved 429 ms against a modelled 382 ms. Registered at about 190 ms by microbenchmark; it is a contract change rather than a local one, and is the same duplication the design review names as F1. What remains: the change pipeline’s 2.04 path validations per entry, which exp-026 left as their own item, and the read side, which still converts every returned row to a contract `InventoryEntry` (`_semantic_entry`). First blocker: the [flat-tree plan](plan-2026-09-15-flat-tree-delivery-cost.md)’s Tier 2 prototype |
| H73 | A fetched PR can prepare its immutable manifest before Files is opened and hydrate only an initial visible prefix, avoiding manifest recomputation and invisible patch work on the first request. | Cold first text, completed initial viewport, all mounted bars, load tasks, and trusted navigation | **Measured and accepted with limits** ([exp-041](../../../../explorations/performance-loop/experiments/exp-041-pr-files-use-a-prepared-manifest-and-visible-prefix.md), `mb-fkd9`). The 1,627-file first-text median is 519 ms against 1,350; the 500 ms goal remains open. All bars remain mounted, load tasks stay below 200 ms, and jump drift is zero. Actual resting text regresses about 13 ms in the larger case while remaining below 150 ms |
| H107 | A transferred kilobyte of startup script costs a cold first row in proportion to its bytes, so a ceiling can be set at a measured size: growth from 174 KB to 220 KB, all of it comment, costs under the careful 1.1x on every path. | Paired first row, a comment-padded 220 KB build against `main`, on loopback and emulated 10 ms and 80 ms links | **Supported as a rough cut; the careful 1.1x is open** ([exp-084](../../../../explorations/performance-loop/experiments/exp-084-eager-startup-script-cost.md)). 1.07x (1.03–1.14) on loopback, 0.99x (0.95–1.11) on the 10 ms link, and 1.04x (1.03–1.04) on the 80 ms link, on a loaded host with one series per path and no A/A series. It sets `startup_script_transfer_kb = 220`; the careful 1.1x waits on a quiet-host re-measure (`mb-djo1`) |

### PR and Git Navigation

The November 4, 2026 iteration (`mb-4ifm`) measures the unchanged product before
selecting an implementation.
Register each mechanism separately; retained data, in-flight preparation, HTTP-cache
responses, and cold-origin assets are different conditions.
The target is useful, exact content painted within 100 ms for prepared or cached
navigation, with immediate selection feedback and the framework’s existing correctness
and responsiveness gates.
This is an investigation target, not a newly measured baseline or a reason to relax a
gate.

| # | Hypothesis | Metric that would show it | Status |
| --- | --- | --- | --- |
| H74 | Cold PR and Git navigation spends avoidable time awaiting on-demand assets and serial independent route work before useful content can render. Preparing only the existing asset bundles outside the input window separates asset wait from backend and render cost. | Trusted input to exact painted PR Conversation or first Git history rows; request start/order, server time, decode, mount, and paint phases on the same cached subjects | **Open for first-tab controls** (`mb-5rm1`, reserved exp-042). Selected Git assets finished before comparison data on the measured path; no eager bundle change. First-tab and empty-pane controls still need separate evidence. |
| H75 | Intent preparation starts too late for natural clicks, or a selected request fails to join matching preparation. Long scripted hover can therefore overstate the benefit a reader receives. | Preparation hit rate and exact selected-subject request count, alongside painted readiness at 0, 100, 200 and 450 ms dwell and keyboard selection | **Merged into H94** (`mb-97ex`): H92 (a) measured its join clause for the Pulls selection (exp-065), and H94 runs its dwell and keyboard sweep. Its reserved exp-043 stays unused. |
| H76 | Once data is genuinely held, decoding, validation, mounting or paint remains the limiting cost. Additional network prefetch cannot remove that render floor. | Correct painted readiness and client phase spans with held data, matching in-flight data and HTTP-cache data; transferred/decoded bytes, Long Tasks, DOM and retained heap | **Diagnosed for these paths** (`mb-i73o`, [exp-045](../../../../explorations/performance-loop/experiments/exp-045-publish-selected-pr-description-before-full-conversation.md), [exp-047](../../../../explorations/performance-loop/experiments/exp-047-connect-the-git-stage-before-rendering.md)). Held PR descriptions already paint in 42–53 ms. The identical held Git payload exposed avoidable render work, corrected under H79. No extra data fetch is justified for the measured held paths. |
| H77 | A lightweight catalog can be ready while a first-selected PR has no detailed record. Cache-only hover reads cannot prepare that missing record, so selection waits for full provider hydration and publication. Bounded preparation or honest progressive core availability may remove this wait. | Same-PR absent versus held record: trusted click to exact header and useful description, core versus final publication, provider request/byte costs and background concurrency | **Accepted for early description and continuity** (`mb-tgn3`, [exp-045](../../../../explorations/performance-loop/experiments/exp-045-publish-selected-pr-description-before-full-conversation.md)). Three integrated pairs reached the exact description in 1.27–1.56 s against 3.06–4.09 s. Three transitions retained real prior PR content without a blank frame. Full Conversation has no speed claim; the original outlier and prescribed rerun are retained. [exp-048](../../../../explorations/performance-loop/experiments/exp-048-measure-provider-cost-of-preparing-visible-pr-core.md) and `mb-oywk` track preparation before selection. |
| H78 | Once a Git revision has rendered, clearing its preparation slot allows a later hover to fetch the same comparison again. Tooltip preparation should reuse selected detail without another comparison while that revision still owns the preview. | Matching comparison request count and decoded bytes after selected-row reentry; painted readiness, cancellation, ownership, Long Tasks and memory alongside them | **Accepted** (`mb-wpyg`, [exp-046](../../../../explorations/performance-loop/experiments/exp-046-reuse-the-rendered-git-revision-on-hover.md)). All five final pairs removed the extra comparison request when hovering the already rendered selected row. Another owner still invalidates that selection. |
| H79 | A detached Git comparison has no viewport geometry, so its initial screen budget is infinite and its first width report projects every initially hydrated file. A connected stage may preserve atomic handoff while limiting initial work to the visible prefix. | Same held comparison payload and assets: first correct painted text and viewport, model and projection counts, Long Tasks, DOM, heap and requests; then complete trusted Git navigation | **Accepted** (`mb-envd`, [exp-047](../../../../explorations/performance-loop/experiments/exp-047-connect-the-git-stage-before-rendering.md)). The same held payload projected four file models instead of 50. Five final pairs painted in 236–247 ms against 358–387 ms, with no Long Tasks. Separate generic startup gates passed. |
| H80 | A selected REST core needs another account check before its early preview can be exposed. A GraphQL response can bind the same validated payload to its actual viewer, keeping initial and final account checks while removing a sixth concurrent `gh` process. | Identical core fields and account failures; provider bytes, selected description and full Conversation paint, process concurrency, and sampled RSS | **Accepted for resource cost** (`mb-npyj`, [exp-049](../../../../explorations/performance-loop/experiments/exp-049-bind-the-missing-selected-pr-core-to-the-graphql-viewer.md)). Five pairs reduced sampled peak concurrent `gh` from six to five and median sampled server-family RSS from 353 to 313 MiB. Full Conversation ranges overlap; the cached conditional REST path is preserved. |
| H81 | A small batch after the visible Pulls window paints can prepare descriptions before a reader selects a row. | Exact trusted click to prepared description, alongside immediate and full-Conversation guards, cohort changes and competing work | **Trial rejected** (`mb-oywk`, [exp-050](../../../../explorations/performance-loop/experiments/exp-050-prepare-visible-pr-descriptions-after-summary-paint.md)). Two ready clicks painted in 34–37 ms, but both immediate pairs exceeded the full-Conversation guard. The actual publication delay and the following poll wait are reported separately. **Follow-up accepted** ([exp-052](../../../../explorations/performance-loop/experiments/exp-052-confirm-visible-pr-descriptions-after-settlement.md)). With H82 in both arms, five ready clicks painted in 37–40 ms versus 1,054–1,225 ms. Immediate and running clicks fell back to selection. The local guard and unchanged directory gate passed; the experiment does not establish a faster full Conversation. |
| H82 | A selected refresh can publish just after a one-second poll, delaying the complete Conversation even though the record is ready. A bounded cache read can wake on the existing refresh. | Atomic full-record publication to exact full paint, with provider and Git latency measured separately | **Accepted** (`mb-dmby`, [exp-051](../../../../explorations/performance-loop/experiments/exp-051-wake-selected-pr-cache-read-on-settlement.md)). Three final pairs reduced the post-publication interval from 73–852 ms to 26–29 ms. Both exact variants passed the unchanged directory gate. Total provider and Git time still varies. |
| H83 | After a visible batch is admitted, an unrelated catalog member can change while the selected row stays exact. Validate the selected row independently. | Held update before and after batch publication, then exact prepared read under a live sibling update | **Accepted** (`mb-1r6v`, [exp-054](../../../../explorations/performance-loop/experiments/exp-054-keep-prepared-descriptions-through-a-catalog-update.md)). [Exp-053](../../../../explorations/performance-loop/experiments/exp-053-reject-whole-window-catalog-validation.md) retained three whole-window misses. The per-row proof kept four exact ready reads through the live sibling update, and all five ready trial descriptions painted in 34–46 ms. |
| H84 | Background PR metadata starts after idle startup in both repository modes, covers the measured viewport, and continues through cached catalog rows. Durable cores remain useful after another batch, a minute, and server restart. | Startup and prepared-click latency, provider work and bytes, complete viewport/catalog coverage, prolonged busy admission, reconnect cursor ownership, and stale/cache-only reads | **Accepted for observed metadata readiness** ([exp-055](../../../../explorations/performance-loop/experiments/exp-055-progressive-pr-metadata-warming.md)). Six alternating browser pairs observed descriptions in 71–80 ms versus 1,123–3,357 ms beyond the first eight rows. Startup and full-record ranges overlap; no paint, INP, or universal speed claim. A new managed process read a 143.5-second-old unselected core with zero GitHub CLI calls. Production sessions cover viewport/catalog traversal, prolonged contention, reconnect and identity replacement. A later three-pair review-fix guard retained prepared-description readiness (77 versus 76 ms medians, overlapping ranges); exp-055 records its separate pins and recovery checks. |
| H85 | A release candidate preserves ordered navigation/tallies except documented changes, passes every committed browser hard gate, and has no repeatable wrong-way paired release-metric ratio above the declared 1.3 rough tolerance. | Five alternating browser pairs and five backend pairs on one frozen project-10 shape-2 corpus; ordered results, tally answers, per-run hard gates and paired release metrics | **Closed: v0.12.0 shipped without exp-057.** The release was tagged at `87b8ec81` on 2026-11-08, and no exp-057 record exists; its preflights deferred without a pair. [exp-056](../../../../explorations/performance-loop/experiments/exp-056-previous-release-rehearsal.md) stays as recorded, a valid hard-gate failure: pair 1 observed control 130 ms and candidate 114 ms; pair 2’s candidate measured 444 ms against the 350 ms first-row gate. Its matching control and all backend pairs were not run. No full-series statistics, speedup or release acceptance. |

Take at least three admissible runs per condition and five or more interleaved pairs for
expected effects below 2x. Freeze product and browsed corpus independently, record
provider/cache state and request concurrency, and preserve cancellation and exact
source/account/record ownership.
A range that overlaps supports no speed claim.
Record rejected explanations with the same provenance as accepted ones.

### Apparent Speed and Layout Stability

The November 11, 2026 campaign (epic `mb-mpo0`) implements the ranking in
[apparent UI performance for the native app](../../research/research-2026-11-11-ui-apparent-performance.md).
Its work order is the phase order of
[the implementation plan](plan-2026-11-11-ui-apparent-performance.md).

It follows the [November 4 iteration](#pr-and-git-navigation) and the provider prefetch
lane that landed with #355
([PR freshness and prefetch](../done/plan-2026-11-11-pr-freshness-and-prefetch.md)), and
five of its rows revisit their results: H88 generalizes H78; H92 measures H75’s join
clause for the Pulls selection; H94 covers file navigation, which H74 to H76 did not;
H104 revises H84’s walk; and H106 revisits the description readiness of H77, H81, and
H84. Each of these rows carries the metrics its predecessors were accepted on as guards,
because the accept rule’s third clause sees only the metrics in a round’s own table.
A row that bundles mechanisms keeps one identifier and records a lettered verdict for
each mechanism, each decided by its own named metric.

Each round’s control is the build immediately before that item’s commits, run
interleaved with its candidate on the corpus checkout frozen at `7a02fed4`, under
[the accept rule](../../../../explorations/performance-loop/README.md#the-accept-rule).
exp-058 is the campaign’s reference, not a round’s control: it measured the product at
`main` 09903292 on that corpus.
[exp-079](../../../../explorations/performance-loop/experiments/exp-079-every-accepted-change-at-final-main.md)
closed Phase 1 only: it measured every landed Phase 1 item together at final `main`
against that reference, in Chrome, and its
[Final Performance Update](../../../../explorations/performance-loop/experiments/exp-079-every-accepted-change-at-final-main.md#final-performance-update)
gives each one’s outcome.
Phases 2 and 3 need their own closing round, in Chrome and `WKWebView` (`mb-vmb4`), and
[the campaign plan](plan-2026-11-14-performance-campaigns.md#lanes-of-the-ui-campaign)
orders the rows that remain into lanes.
A commit does not pin pull request data, so each condition reads GitHub records from its
own cache directory, filled by an unrecorded warm-up pass; subjects are named by number,
and each row records the catalog totals it saw.
Reserved experiment IDs are identifiers, not an order: H106 holds exp-080 although the
Phase 1 closing round is exp-079.

| # | Hypothesis | Metric that would show it | Status |
| --- | --- | --- | --- |
| H86 | Chrome that toggles (filter bar, view tab bar, scrollbar, print button, status rows, a late tab button) and header sections that fill in late move content during transitions. Reserving each region’s box at first paint removes the movement without slowing the transition. | Two verdicts, each on region movement per transition in its own regions: (a) shell chrome (tree content top, content start, pane width, header label, main tab bar); (b) the PR page header (title, state row, status row, tab bar). Layout-shift value as a second reading; painted-ready as a guard on both | **Accepted**, (a) and (b) ([exp-059](../../../../explorations/performance-loop/experiments/exp-059-every-region-box-at-first-paint.md); `mb-4z69`). At final main, [exp-079](../../../../explorations/performance-loop/experiments/exp-079-every-accepted-change-at-final-main.md): (a) accepted (region movement 11–37 px to 0 on 23 transitions); (b) is unresolved, 13 wrong-way results on its guards over nine pull request transitions, the first-paint holds. `mb-0t7d` attributes them to the lane merges |
| H87 | Stamped assets carry no `Cache-Control`, and plugin and KPress assets are `no-cache`, so every reload and relaunch revalidates them. Immutable headers on content-keyed URLs remove those requests. | Conditional requests per reload in Chrome decide the row, with reload ready time as a guard. Requests per relaunch in `WKWebView` are a secondary reading, which the probe committed in #378 (`mb-fevz`, `wkprobe.mjs`) takes on one fixed proxy origin; the app’s own relaunch also needs `metab` host mode’s sticky port (`mb-qzny`). That reading has a limit, which #378’s probe found: over three or more runs, the only regime a control can hold, judged by age, is “fresh”, in which stamped `/static/` assets come from cache at a relaunch. So in WebKit, H87’s saving on stamped assets reads 0 against 0 by construction, and only the families that were `no-cache` can show a difference; #378’s `--stale-assets` flag gives a diagnostic stale control | **Accepted** ([exp-083](../../../../explorations/performance-loop/experiments/exp-083-immutable-stamped-assets-without-h89.md), with its third clause met by [exp-087](../../../../explorations/performance-loop/experiments/exp-087-frame-quantization-confirms-h87.md); earlier [exp-060](../../../../explorations/performance-loop/experiments/exp-060-immutable-stamped-assets-on-reload.md); `mb-3m3l`). Conditional requests per Chrome reload fell from 43 to 1, and reload painted-ready improved from 158.1 to 124.7 ms. exp-083’s one-frame-later cold views did not recur in rate: in 9 judged pairs (Low Power Mode on, AC power), the later frame came 1/9 against 0/9 for the cold JSON and image views and 0/9 against 0/9 for the large Markdown revisit (Fisher p=1.0 each). At final main, [exp-079](../../../../explorations/performance-loop/experiments/exp-079-every-accepted-change-at-final-main.md): unresolved, its deciding metric met (43 to 1) and 17 wrong-way results on landing and files transitions unaccounted. `mb-0t7d` attributes them; the WebKit reading at final `main` is `mb-o3hr` |
| H88 | A commit revisit re-fetches its comparison, and git routes recompute on every call. (a) A browser comparison cache by commit ID makes a revisit request-free; it generalizes H78, accepted in exp-046, from the hovered selected row to every revisit. (b) A server memo keyed by a refs fingerprint read from ref storage without running Git makes repeated routes cheap; the existing scope fingerprint spawns Git (`git/history.py:303-393`), so it cannot be the key. | (a) Comparison requests and painted-ready on a commit revisit, with H78’s guards (cancellation, ownership, Long Tasks, memory) and H79’s first painted text from exp-047 not regressing. (b) Server time of repeated `log`, `summary`, and `refs`, and Git processes spawned per repeat | **Accepted**, (a) and (b) ([exp-086](../../../../explorations/performance-loop/experiments/exp-086-comparison-cache-route-memo-and-markdown-render-cache-confirmation.md), on scenario revision 5; earlier [exp-061](../../../../explorations/performance-loop/experiments/exp-061-commit-comparison-cache-and-git-route-memo.md) left both unresolved and [exp-081](../../../../explorations/performance-loop/experiments/exp-081-commit-comparison-cache-and-git-route-memo-confirmation.md) rejected (a); `mb-8a8g`). At final main, [exp-079](../../../../explorations/performance-loop/experiments/exp-079-every-accepted-change-at-final-main.md): (a) is unresolved, its deciding metrics met (revisit painted ready 122.5 to 30.4 and 164.4 to 31.1 ms) and 12 guard results unaccounted, which `mb-0t7d` attributes; (b) not measured |
| H89 | Shell tools and KPress assets load one round trip at a time. Fetching them in parallel, in the same execution order, shortens the chain to tools ready and to a styled Markdown view. | Dependent request levels; time to shell tools ready; cold Markdown painted-ready | **Rejected** ([exp-062](../../../../explorations/performance-loop/experiments/exp-062-parallel-shell-tools-and-kpress-loading.md); `mb-pdul`). #372 reverted it before merging; its code is kept at `14150b84`, not on main. Its follow-up is H109 and H110 (`mb-mjc0`) |
| H90 | A Markdown revisit uploads its source and downloads its render again, and leaving Markdown discards the worker. A render cache keyed by content identity and a kept worker make revisits request-free. | Requests and uploaded bytes on a revisit; painted-ready | **Unresolved** ([exp-086](../../../../explorations/performance-loop/experiments/exp-086-comparison-cache-route-memo-and-markdown-render-cache-confirmation.md), after [exp-063](../../../../explorations/performance-loop/experiments/exp-063-markdown-render-cache-and-kept-worker.md) and [exp-082](../../../../explorations/performance-loop/experiments/exp-082-markdown-render-cache-and-kept-worker-confirmation.md); `mb-mbd3`). #368 took it out before merging (`bd971661`); its code is kept at `6b876c54`, not on main. **Not re-tested** (2026-11-14; `mb-mbd3` closed as canceled): its deciding metrics were met and it failed only on one-frame guard flags, and the [architecture review](../../research/research-2026-11-14-performance-architecture-review.md) supersedes it with H112, which keeps the revisited surface, and H113, which makes the render request-free. Its code at `6b876c54` is H113’s fallback |
| H91 | Four small mechanisms, each with its own prediction: (a) prose faces loaded before the first document’s swap remove its 21–23 px reflow; (b) programmatic tree reveals that do not animate remove the no-input shift of a deep reveal; (c) coalescing a held arrow key renders only the row it stops on; (d) a fixed position for pull request results in Quick Search replaces no row after the first results paint. | (a) Shift without input on a first document, 0.003 to 0, with first contentful paint and first-document painted-ready as guards; (b) shift without input on a deep reveal, 0.046 to 0; (c) requests per six-key skim, 14 to those of one file, with painted-ready of the row it stops on as a guard; (d) result rows replaced after first paint, three to none | **Accepted**, (a), (b) and (d) ([exp-064](../../../../explorations/performance-loop/experiments/exp-064-four-movements-nobody-asked-for.md)) and (c) ([exp-085](../../../../explorations/performance-loop/experiments/exp-085-held-key-guard-confirmed.md); `mb-n3r5`). At final main, [exp-079](../../../../explorations/performance-loop/experiments/exp-079-every-accepted-change-at-final-main.md): (a), (b) and (d) accepted; (c) rejected by exp-085’s guard rule, ready after the last input 46.2 to 65.0 ms with ranges apart. `mb-f8g9` finds what lengthened the skim’s last row and re-judges (c) on `main` |
| H92 | A PR click reads the selected record two to four times. The click does join the mousedown peek; the extra reads are the page’s own first read after `OPEN_WAIT_MS`, the hover timer re-reading the clicked row, and a click on the row already shown. Separately, a selected row’s file tree grows seconds after the click, and Changes paints before its rendered diffs. (a) An answer the selection read less than one fast poll earlier counts as the page’s first read; (b) a row’s file tree opens once at its full height; (c) Changes holds first paint for diffs in flight. Mechanism (a) is H75’s join clause measured for the Pulls selection; H75’s intent timing is now H94’s sweep, since H75 merged into H94. | (a) Reads of the selected record per click, settlement polls while a refresh runs excluded, with two guards: the page never treats a record older than one fast poll as its first read, and prepared-click description readiness keeps H81’s and H84’s results (37–40 ms in exp-052, 71–80 ms in exp-055). (b) No-input layout shift in the Pulls list after a selection. (c) Layout shift on Changes first paint, with trusted input to first painted diff as a guard | **Accepted**, all three parts ([exp-065](../../../../explorations/performance-loop/experiments/exp-065-one-read-per-click-trees-that-open-once-and-a-held-changes-paint.md); `mb-6chh`). At final main, [exp-079](../../../../explorations/performance-loop/experiments/exp-079-every-accepted-change-at-final-main.md): (a) and (c) accepted, with exp-065’s account of the first-paint hold; (b) not measured. (c) is the campaign’s costliest accepted trade (Changes ready 79–102 ms against 43–45 ms); H112 (d) (`mb-wki1`), with what remains of H108, would win that time back |
| H93 | Saturated background work inflates a cheap foreground request 3.3–26x. (a) A client cap on background requests in flight, paused while input is pending, keeps a cheap foreground route near its quiet latency. (b) A low-priority server lane does what (a) cannot. The cap starts at two, a value the research did not measure; this round sets it. | (a) Foreground route p50 and p95 under background warm-up; (b) the same, run only if (a) leaves foreground p95 above 1.3x its quiet latency; guards: background completion time, the prepared hit rate, and the provider lane’s outcomes | **Open** (`mb-16d7`, reserved exp-066), **split** on 2026-11-14 as the [architecture review](../../research/research-2026-11-14-performance-architecture-review.md) proposed. H115 and H116 cheapen two of the inflators the research measured, warm renders and Git routes, so (a) may be enough. First blocker: its instrument. The research’s saturation probe is not committed, and Server-Timing has no wait phase to separate thread-pool wait from work (`server_timing.py` names `read`, `render`, `git` and `encode`), which `mb-16d7`’s notes ask for before the lane is designed. It caps the requests H94 and H104 add, so it runs before them |
| H94 | A file click waits for the envelope, the worker, and the render in series. One prepare unit per subject, driven by keyboard, pointer-down, and hover, makes a predicted transition as fast as a revisit. H74 and H75 measured PR and Git navigation, and H76 found that a held PR description paints in 42–53 ms, a render floor more prefetch cannot remove. What is new is the file chain (envelope, worker preparation, render, kind assets) and keyboard prediction; H75’s dwell sweep becomes this row’s sweep for files. | Cold-neighbor and hovered painted-ready at 0, 100, 200, and 450 ms dwell and on keyboard selection; selected-subject requests (one cold, none prepared); cost: wasted prepare requests and bytes per transition | **Open** (`mb-fejb`, reserved exp-067). **Runs after H112** (`mb-fejb` is blocked on `mb-wki1`): a prediction fills H112’s kept hosts, and H113’s render `GET`, where it once filled H90’s payload cache, which will not land. It also waits on H93 (a) (`mb-16d7`). The dwell sweep needs a journey: hover-clicks dwell a fixed 400 ms (`hoverClick` in `transitions-journeys.mjs`), which recorder revision 6 adds (`mb-tpol`). H75 is merged into this row, so the sweep also covers the PR and Git rows H75 named (`mb-97ex`). At final `main` cold keyboard neighbors already read like revisits (exp-079: 42.9–54.6 against 41.7–54.3 ms); the headroom is on heavier files, such as cold large Markdown at 180.8 ms against its revisit at 145.8 ms |
| H95 | Main tabs destroy the preview on every switch. Retaining each tab’s surface makes a switch one frame with no request and no blank frame. | Main-tab switch painted-ready, blank frames, requests; retained memory and DOM nodes as guards | **Merged into H112** (2026-11-14; `mb-88mp` closed as a duplicate of `mb-wki1`): a kept host per subject covers each main tab’s surface. Its reserved exp-068 stays unused |
| H96 | The cold landing is about 23 dependent request levels deep. Concatenated startup scripts, preloads after them, and an early content request shorten it. The early content request depends on the render `GET`, served from the server’s render cache (the plan’s API Changes). | Request levels; cold and reload ready; guards: first contentful paint and first tree rows, which the tree-first order (`await loadTree()` before `navigationController.start()`, `app.js:8629-8633`) protects and which preloads ahead of the startup scripts slowed | **Partly amended into H118** (2026-11-14). The early content request moved to H118 (`mb-gdmt`), which starts the content with the document and takes the render `GET` from H113. Concatenated startup scripts stay open here (`mb-a1nu`, reopened with that scope; reserved exp-069). **After U2** (`mb-cejc`): on loopback the wait may be server work rather than connections, so U2 decides whether the local half is worth a round. Its remote value, the about 19 serial connection rounds H26 priced over `metab --remote`, is judged in H44’s regime (`tier-probe.mjs --network`). Guards to add before the round: the startup-script budgets, `startup_script_requests` ≤ 25 and `startup_script_transfer_kb` ≤ 220; `region_movement_px` 0 on the landing (H86 (a)); `shift_sum_no_input.landing.cold_markdown` 0 (H91 (a)); revalidated requests per reload at most 1 (H87) |
| H97 | A hidden page never finishes its first view, because readiness waits on animation frames. Readiness that does not depend on visibility lets a prewarmed web view show ready content at once. | Show-to-ready and hidden first-view completion in `WKWebView` | **Blocked** on its code and on the user present at an unlocked screen (`mb-touu`, reserved exp-070; Lane W). The `WKWebView` probe it waited on (`mb-fevz`) landed in #378, and its `hidden-then-show` scenario reads hidden first-view completion and show-to-ready (`wkprobe.mjs`). Not to be read in Chrome instead. The row also needs its predicted direction and its guards before the round |
| H98 | A file revisit rebuilds the pane. A detached LRU of surfaces with suspend and resume makes revisits a re-attach. | Revisit and history painted-ready; requests; retained memory | **Merged into H112** (2026-11-14; `mb-d1uo` closed as a duplicate of `mb-wki1`): its detached tier is H112’s beyond the node budget. Its reserved exp-071 stays unused |
| H99 | View tabs hidden with `display: none` lose their layout, so a heavy view costs a full layout on every return. (a) Keeping shown views laid out under `content-visibility: hidden` removes that layout. (b) Chunking long source with `content-visibility: auto` cuts its first layout; this half is inferred from measured costs, not prototyped. | (a) Heavy view-tab revisit painted-ready and longest task, with retained memory and DOM nodes as guards. (b) First layout time and longest task on a large source view, with find-in-page and anchor scrolling checked | (a) **Merged into H112** (2026-11-14): a shown view stays laid out in its kept host. (b) **Open**, one row with H101 after U6 (`mb-1bh1`, now H99 (b) only and blocked on `mb-xws3`; reserved exp-072). (b) needs a first-layout-time reading, and it cuts the same longest task as H101 |
| H100 | A Markdown mount is laid out twice: once forced in the stage and again after re-parenting. One layout per mount saves the second pass. | Layout passes over 10 ms per mount; painted-ready | **Merged into H112** (2026-11-14; `mb-jak8` closed as a duplicate of `mb-wki1`): a mount in its own host is laid out once, which is H112 (a). Its reserved exp-073 stays unused |
| H101 | Highlighting a large source file is one main-thread task of up to 103 ms. A worker moves its lexing share off the main thread; the token spans it returns must still be parsed, styled, and laid out there ([rendering large content](../../../large-content-rendering.md#syntax-highlighting-spends-elements-and-main-thread-time)), so the gain is less than the whole task. | Longest task on large source files; time to highlighted | **Open** (`mb-y04k`, reserved exp-074), **one row with H99 (b) after U6** (`mb-xws3`): if highlight.js can continue a lexer state, highlighting the visible lines first and the rest at idle replaces the worker. First blocker: U6, then a time-to-highlighted milestone, which recorder revision 6 adds (`mb-tpol`), and named guards |
| H102 | Renders are cached in memory only, so a restart pays cold renders again. A disk cache keyed by source digest returns them at warm cost. | Render route time after restart | **Open** (`mb-4ufj`, reserved exp-075). First blocker: named guards and a restart script; `run.py probe-server --path` samples one route but does not restart the server. The bead also covers retained encoded bodies, which this row does not. It runs after H113, keyed by source digest, and its disk cache would serve H113’s render `GET` after a restart |
| H103 | Compressing for a loopback client costs event-loop time the client does not need. An opt-in uncompressed mode removes it. | Event-loop compression time per cold landing; cold ready | **Widened into H115** (2026-11-14; `mb-e500` closed as a duplicate of `mb-9uyq`): H115 (b) is this row, and (a) adds stamped assets compressed once. Its reserved exp-076 stays unused |
| H104 | The Pulls walk issues about two requests a second for most of a minute after every load, even when steps only read the cache. Bulk preparation removes that traffic. The walk is H84’s, accepted in exp-055, so this row revises an accepted result. | Background requests per minute after settle; H84’s guards: viewport and catalog coverage, prepared-click description readiness beyond the first eight rows (71–80 ms in exp-055), provider calls and bytes, prolonged busy admission, and foreground latency while the walk runs | **Open** (`mb-b7ru`, reserved exp-077). First blocker: a count of background requests per minute after settle; the recorder’s `requests_background` is per transition and shown, not judged. After H93, which caps the requests it governs |
| H105 | A first view-tab visit mounts the view at click time. Mounting at idle after the default view settles makes the first visit a toggle. The headroom is small: when registered, a first visit took 43 ms against 32–33 ms for a revisit, about 1.3x at best, which is the rough tolerance. | First view-tab visit painted-ready; main-thread busy time and longest task while idle as guards | **Merged into H112** (2026-11-14; `mb-yyja` closed as a duplicate of `mb-wki1`): mounting at idle is H112 (d). Its premise held at final `main` only for the folder view (exp-079: 46.9 ms first against 30.9 revisited). Its reserved exp-078 stays unused |
| H106 | The PR description paints as plain text and is then replaced by Markdown, and the full record and commit rows rebuild or insert into the painted Conversation. Caching Markdown by record revision, patching in place, and delivering commits with the record make the body final at first paint. This revisits H77, accepted in exp-045 (description in 1.27–1.56 s against 3.06–4.09 s), and the prepared descriptions of H81 and H84; a hold for Markdown in flight could give those gains back. | Body and section movement after first paint; no-input layout shift on PR landings and switches. Guards: trusted click to exact description, cold, core-only, and prepared, against exp-045, exp-052, and exp-055; full-Conversation paint | **Accepted** ([exp-080](../../../../explorations/performance-loop/experiments/exp-080-pull-request-conversation-final-at-first-paint.md); `mb-gsa0`). At final main, [exp-079](../../../../explorations/performance-loop/experiments/exp-079-every-accepted-change-at-final-main.md): unresolved, its deciding metric met (plain-first Conversation transitions 6 to 1 per run) and `main_subject.commits_to_pulls` painted ready unaccounted (the analysis as amendment 3 hashed it accepts H106, on a broader reading of its accounts). `mb-0t7d` attributes that result; H114 (`mb-3zvb`) would win back the hold’s cost on pull request clicks |
| H108 | H92 (c) and H106 hold first paint until the content is final, and at final `main` the holds cost Changes 79–102 ms against 43–45 ms and a pull request click 44–112 ms against 28–62 ms (exp-079). Preparing a pull request’s first Changes screen and its description on selection or pointer intent lets both holds resolve at once, winning back the time without bringing back movement. This revisits H92 (c), accepted in exp-065, and H106, accepted in exp-080. | As registered, deciding: painted ready, lower, on `pulls.tab.changes_first`, `pulls.tab.changes_first_2`, `pulls.tab.changes_revisit_2` and `pulls.pr_changes_to_pr` (final `main` 95.1–111.5 ms medians against 42.5–62.2 ms at the control, exp-079). For what remains after the re-scope, deciding: painted ready, lower, on a Changes tab clicked before H112 (d)’s idle mount has run. Guards: the Changes body shift after ready stays 0 (H92 (c)’s deciding metric); `subject_duplicates` stays 0 (H92 (a), 8 → 0 per run); `region_movement_px` stays 0 on the pull request transitions (H86 (b)’s header, 8 → 0); plain-first Conversation transitions stay at their final-`main` 1 per run (H106’s); wasted prepare requests and bytes per transition, a count of prepare requests for subjects never shown, which no recorder metric takes and must be built; the hold spans; painted ready on exp-079’s other pull request transitions; prepared-click description readiness (37–40 ms in exp-052, 71–80 ms in exp-055); foreground latency. Instrument: the `pulls` journey of `explorations/performance-loop/transitions.mjs`, with `experiments/exp-065-instruments/derive-h92-h106.mjs` and `experiments/exp-065-instruments/probe-holds-corpus.mjs` | **Re-scoped** (2026-11-14), as the [architecture review](../../research/research-2026-11-14-performance-architecture-review.md) proposed: H114 takes the description half, which a `pull` answer carrying its rendered texts removes, and H112 (d) the Changes half, by mounting Changes at idle. This row keeps only a Changes tab clicked before that idle mount has run, prepared on pointer intent over the tab. Open (`mb-nitp`, reserved exp-088). It runs after H112 and H114. First blocker: a `pulls` journey step that clicks Changes before the idle mount, which the scenario does not have, and the wasted-prepare count |
| H109 | H89’s parallel loading cut dependent request levels to the last shell-tools script from 21 to 5 (exp-062). exp-062 also recorded cold Markdown painted ready at 311.0 ms against 362.3, 1.17x with ranges apart and 0 of 4 pairs beyond 1.3x, which it judged “higher, ranges apart, not a result”; its blank frames went 13 to 16.5, wrong-way with 2 of 4 pairs beyond. Keeping at most a few of a bundle’s preloads in flight keeps the shallower chain without holding the first view’s KPress stylesheets behind it. The cap is set from the waterfall before the round and registered with it. | Deciding: `shell_tools_ready_ms` on the cold Markdown landing and dependent levels to the last shell-tools script, both lower. Guards: cold Markdown painted ready and `styled_markdown_ms`, which exp-062 recorded later; blank and placeholder frames, which exp-062 raised; `shift_sum_no_input.landing.cold_markdown` stays 0 (H91 (a), 0.0033 → 0); `region_movement_px` stays 0 on the landing (H86 (a)); `startup_script_requests` ≤ 25 and `startup_script_transfer_kb` ≤ 220 (`performance-budgets.toml`). Instrument: `explorations/performance-loop/experiments/exp-062-levels-probe.mjs` and the `landing` journey of `transitions.mjs` | **Open** (`mb-mjc0`, reserved exp-089), **behind U2** (`mb-mjc0` is blocked on `mb-cejc`): exp-062 fits a serial server queue, the shell tools 61 ms sooner and KPress 40 ms later with the total unchanged, so if the server’s one thread bounds the cold landing by over half, this row and H110 retire and H115 (a) goes first. Then the first blocker is one network waterfall of a cold landing per build, which separates exp-062’s two candidate mechanisms (the 14 parallel fetches holding connections, or KPress loading starting later from the `sdk-views` tier) and so picks between this row and H110. The code to start from is H89’s, at commit `14150b84`. It competes with H113, H115 and H118 for the cold landing |
| H110 | Starting the same parallel preloads at `fetchpriority="low"`, rather than capping them, lets the first view’s KPress stylesheets go first and keeps exp-062’s shallower chain. | H109’s deciding metrics and guards, `shift_sum_no_input.landing.cold_markdown` among them (H91 (a)), and the same cold landing in `WKWebView`, where the native app runs. Instrument: H109’s, plus the `cold` scenario of `explorations/performance-loop/wkprobe.mjs` | **Open** (`mb-mjc0`, reserved exp-090), **behind U2** (`mb-cejc`), as H109 is. First blocker after U2: H109’s waterfall. The `WKWebView` reading needs the user present at an unlocked screen (Lane W) |
| H111 | After a diff mounts, `yieldForEnhancement` (`diff-view.js`) chains through `setTimeout(0)` into a 56–61 ms intraline task (`myersDiff`, `diff-intraline.js`). When the mount task ends before the next vsync, that task runs first and holds the diff’s first paint 60–75 ms, so `commits.cold.1` is bimodal on both builds, about 114 ms against 165–190 ms. Yielding to a frame first, then to a task, paints the diff before its enhancement. | Deciding: `commits.cold.1` painted ready and its share of runs in the late mode, both lower (exp-079: 122.9 (114.2–180.3) ms at the control, 163.5 (112.6–164.8) at final `main`). Guards: time to the enhanced diff; `long_task_max_ms`; painted ready on the commit revisits (30.4 and 31.1 ms at final `main`, H88 (a)) and on `files.cold.diff`; `region_movement_px` stays 0 on `files.cold.diff` (H86 (a), 30 px → 0); H116’s deciding metric, `git;dur` per comparison, since both rows move `commits.cold.*`. Instrument: the `commits` and `files` journeys of `explorations/performance-loop/transitions.mjs`; time to the enhanced diff needs a recorder milestone that is not in revision 6’s scope (`mb-tpol`) and must be built | **Open** (`mb-i9vb`, reserved exp-091). First blocker: Lane A’s test of the mechanism against `commits.cold.1` on scenario revision 5, then the enhanced-diff milestone |

**The readings and instrument work that gate these rows and the next table** are
measurements, not hypotheses, so they take no H number; each still needs its own
experiment id and committed protocol before it runs:

- `mb-0t7d` attributes exp-079’s unaccounted wrong-way results (H86 (b), H87, H88 (a),
  H106) to the lane merges that cause them, and `mb-f8g9` finds what lengthened the
  held-key skim’s last row, then re-judges H91 (c) under its own row.
- `mb-o3hr` reads exp-079’s WebKit half, request counts per reload and relaunch at final
  `main` in `WKWebView`, and judges nothing.
- `mb-32en` measures an idle Markdown worker’s memory, which any change that keeps the
  worker needs first, H113’s fallback to H90’s code among them.
- `mb-86b9`, `mb-5xzz` and `mb-s0e4` fix the transition recorder, and land together in
  revision 6 (`mb-tpol`) with the memory, dwell, and time-to-highlighted readings that
  H94, H99 (b), H101 and H112 need.
- The
  [architecture review](../../research/research-2026-11-14-performance-architecture-review.md#readings-first)’s
  six readings come before the rows they reorder:
  - U1 (`mb-r303`): what a kept surface costs in `WKWebView`, a toggle against a
    re-attach on three surfaces and the footprint per surface; it sets H112’s tiers.
    Its instrument must be built: `wkprobe.mjs` has no toggle-against-re-attach
    scenario, and `wkprobe-steps.mjs` only attributes requests to steps.
  - U2 (`mb-cejc`): whether the server’s one thread bounds the cold landing,
    Server-Timing summed to the end of each body over one landing per build; it decides
    H109, H110, and H115 (a)’s place.
  - U3 (`mb-wb7e`): the fdu provider against the Python provider, walk to settled,
    footprint, and foreground latency during the walk; it decides the scan-and-walker
    rows, H21 and H46.
  - U4 (`mb-7nm6`): how k pages on one origin share six connections when each holds one
    for `/api/events` (`explorations/page-connections/measure.mjs`), before native tabs.
  - U5 (`mb-ttfq`): the app’s frame rate, since WebKit drew 30 frames a second in Low
    Power Mode; it restates the 50 ms goal in frames.
    Its instrument must be built: a frame-gap reading in `wkprobe.mjs`, which takes none
    today.
  - U6 (`mb-xws3`): whether highlight.js can continue a lexer state; it decides H101 and
    H99 (b).

### Structural Costs

The
[architecture review](../../research/research-2026-11-14-performance-architecture-review.md)
of 2026-11-14 found four divisions of work that charge a fixed cost to every transition
or window open, whatever is tuned around them: the preview pane has one owner and
rebuilds on every show; text is rendered by a second request the client drives; the
server repeats identical work per request; and a folder is a process and an origin.
A fifth cost follows from them: the landing starts after the first tree request.
These rows remove those costs.
Their regime, unless a row says otherwise, is the campaign’s: headless Chrome 152,
corpus v2 at `7a02fed4`, a warm server, and paced interleaved pairs under
[the accept rule](../../../../explorations/performance-loop/README.md#the-accept-rule),
with `WKWebView` readings in the campaign plan’s Lane W. Instrument paths are under
`explorations/performance-loop/`. Every predicted size beyond a cited record or probe is
an inference, and a probe reading is an untimed order of magnitude from a loaded host.

| # | Hypothesis | Metric that would show it | Status |
| --- | --- | --- | --- |
| H112 | The preview pane commits a render by moving the stage into it (`preview.replaceChildren(...)` in `app.js`), a main-tab switch cancels the preview (`deps.cancelPreview()` in `main-tabs.js`), and the pull request page replaces its body for each tab (`pull-page.js`), so nothing rendered is kept. If each render stays in the host it was staged in, shown in place and kept afterwards (laid out and hidden within a node budget, detached beyond it), then (a) a mount is laid out once; (b) a return to an unchanged subject makes no request before paint; (c) it shows in the next frame; and (d) with Changes and each main tab’s landing mounted at idle, their first show is a toggle too. It absorbs H95, H98, H99 (a), H100 and H105, and H108’s Changes half. | Four verdicts, each on its own metric: (a) layout passes over 10 ms per mount, 2 → 1 (the UI research: 33 ms each on a 156 KB document); (b) requests before ready → 0 on the scenario’s file, history, keyboard, main-tab, view-tab (`views.*.revisit`, `views.*.revisit_2`), pull request and Changes revisits (up to 13 data requests today on `main_subject.commits_to_pulls`, exp-079); (c) painted ready on those, up to 145.8 ms (`files.revisit.markdown_large`) → ≤ 47 ms, ≤ 63 ms for the 13,000-element source view; (d) `pulls.tab.changes_first` and `pulls.tab.changes_first_2` 102.2 and 95.1 → ≤ 47 ms, `commits.first_show` 197.9 → ≤ 47 ms, and the view-tab first visits at their revisit time, where `views.folder.first`, H105’s one live premise, is 46.9 ms against 30.9 revisited (exp-079). Guards: the longest task on a heavy view-tab revisit not longer (H99 (a)’s guard), with `long_task_max_ms` on every transition it changes; H91 (c)’s skim, `file_envelope_requests` at 2 or fewer (6 → 2) and `ready_after_last_input_ms` not later; retained heap and DOM nodes against a budget set before the round; the cold transitions not later; `blank_frames` 0; `region_movement_px` 0 on every transition it changes (H86 (a), and H86 (b)’s pull request header); `shift_sum_no_input` 0 where H91 (a) and (b) set it; H88 (a)’s commit revisits, `requests_data` 0 and painted ready near 30 ms; `subject_duplicates` 0 (H92 (a)); the Changes body shift after ready 0 (H92 (c)); plain-first Conversation transitions at most 1 per run (H106); a surface flagged by a change event revalidates before it shows; one disposal per view. Instrument: `transitions.mjs` at revision 6 with its memory reading (`mb-tpol`); a layout-pass count, which must be built | **Open** (`mb-wki1`, reserved exp-092). Before the first run: recorder revision 6 (`mb-tpol`); the host and store in `app.js`; additive `suspend()` and `resume()` view hooks; the Git panel and the pull request page on the store; and id scoping, since two kept documents can share heading ids. U1 (`mb-r303`) sets its `WKWebView` tiers. H94 (`mb-fejb`) runs after it and fills its hosts |
| H113 | A Markdown view runs the worker’s wiki preparation, then uploads the prepared source with its render request (`rendered.js`), and preparation changes nearly every document: its trigger (`hasPreprocessingTrigger` in `wiki-parser.js`) fires on any `[`, `#`, `^`, `=` or `-`, and the heading pass adds an anchor to each heading. Deriving the anchors from the rendered headings lets a document with no wiki syntax skip the worker and the upload: the page asks `/api/file` and `GET /api/kpress/render` (already served, `api_kpress_render` in `server.py`) together, and a validator from the source digest lets the HTTP cache answer revisits, reloads and relaunches. If the anchors cannot move, the claim is false. It supersedes H90. | Deciding: `post_body_bytes` 19,168–191,142 → 0 (exp-063); worker module requests 3 → 0 (exp-063); the content’s request level 13 → ≤ 9 (the UI research’s chain); `files.cold.markdown_mid` one frame earlier, 64.4 → ≤ 47 ms, by exp-087’s later-frame test. Inferred: Markdown revisits as H90 measured them, `files.revisit.markdown_small` 63.8 → 30.9 ms (exp-086). Guards: wiki links, block references, transclusion and heading fragments unchanged, in browserless sessions; a document with wiki syntax keeps today’s path byte for byte; `shift_sum_no_input.landing.cold_markdown` 0 and `styled_markdown_ms` not later (H91 (a)); `region_movement_px` 0 on the Markdown transitions (H86 (a)); revalidated requests per reload at most 1 (H87); the startup-script budgets. Instrument: `transitions.mjs` (`landing`, `files`); `experiments/exp-062-levels-probe.mjs`; `experiments/exp-087-analyze.mjs` | **Open** (`mb-mbf4`, reserved exp-093). No dependency. First blocker: the code: anchors after render, a tighter trigger than `hasPreprocessingTrigger`, and an entity tag on the render `GET`, which answers `cache-control: no-cache` with no validator today. A document with wiki syntax keeps today’s path, the worker, the upload, and the three worker modules fetched again after a view of another kind (exp-063); that remainder is what H90’s code at `6b876c54`, the fallback, would still address. H102 runs after it, and it runs with H118 as one round |
| H114 | A pull request page asks for each text’s render separately, at most two at a time (`MARKDOWN_ROUTE` and `MARKDOWN_CONCURRENCY` in `pull-page.js`), and its first-paint hold waited in all 12 opens exp-065 recorded, 25–151 ms, median 41.5. If the `pull` answer carries the rendered HTML of the texts its first screen shows, rendered once per record revision, the page holds for nothing, on cold clicks too. It takes H108’s description half. | Deciding: first-paint holds that waited, 12 of 12 → 0 (`githubPull:firstPaintHold`); `pulls.pr_to_pr.cold` 61.4 → ≤ 47 ms, `pulls.pr_to_pr.hover_click` 96.4 → ≤ 47, `pulls.list_to_pr.cold` 90.5 → ≤ 63 (exp-079); plain-first Conversation transitions 1 → 0 per run. Guards: the Changes body shift after ready 0 (H92 (c)); `subject_duplicates` 0 (H92 (a)); `region_movement_px` 0 on the pull request transitions (H86 (b)); cold, core-only and prepared description readiness against exp-045, exp-052 (37–40 ms) and exp-055 (71–80 ms), as H106 carries them; the `pull` route’s server time within 1.3x, from Server-Timing, since no paired instrument exists for it yet; `304` polls unchanged; both sanitizing passes kept. Instrument: `transitions.mjs` (`pulls`); `experiments/exp-065-instruments/derive-h92-h106.mjs` and `probe-holds-corpus.mjs` | **Open** (`mb-3zvb`, reserved exp-094). No dependency, since it adds no request. First blocker: the code: the route calling `render_part` (`pull_markdown.py`), keyed by record revision, and `inert-html` and the KPress styles loaded when Pulls first shows |
| H115 | Every compressible answer is gzipped at level 6 on the event loop (`TimedGZipMiddleware` in `server.py`), toward a loopback client that does not need it. (a) Stamped assets served from memory, compressed once, and (b) no gzip toward a loopback client unless `--remote` started the server, return that time to the event loop. It widens H103 into (b). | Two verdicts: (a) the startup assets’ server time, summed from Server-Timing to the end of each body over one landing (U2’s reading), lower, by a size registered from U2’s reading of the control before the round. Context only: `static_probe.py`’s client-side sum of timed round trips over the shell’s scripts and stylesheets plus its on-demand bundles, 41 requests, was 98–106 ms with gzip and 44–66 without (probed); (b) a warm `GET` of a 211 KB document’s render, 14.8 ms gzipped → about its uncompressed 3.8 ms, and `/api/file` on the same document 14.6 → ≤ 4 ms (probed). Outcome, by exp-087’s later-frame test: `files.cold.markdown_large` and `landing.cold_markdown` not later, and one of them earlier. Guards: bytes and first row over an emulated 80 ms link unchanged (exp-084’s 514.1 ms); `startup_script_transfer_kb` restated, since it is read on loopback; `startup_script_requests` ≤ 25; revalidated requests per reload at most 1 with the immutable headers kept (H87); the 350 ms first-row gate; `region_movement_px` and `shift_sum_no_input.landing.cold_markdown` 0 on the landing (H86 (a), H91 (a)). Instrument: (a) Server-Timing summed to the end of each body over one landing, U2’s instrument, which must be built; (b) `architecture-probes/render_probe.py`; `architecture-probes/static_probe.py` as context; `tier-probe.mjs --network` | **Open** (`mb-9uyq`, reserved exp-095). Runs on scenario revision 5. First blocker: U2’s instrument and U2’s reading of the control, which sets (a)’s size. (a) goes before H118. **Lands ahead of its round** with #455, so (a) is backed out unless exp-095 accepts it: the revert criterion, the corrected reading of #455’s untimed table, and the arms are in [The exp-095 Protocol for H115](#the-exp-095-protocol-for-h115) |
| H116 | A commit comparison’s time is process starts, not diffing: `GitDiffSource` (`diff/adapters/git.py`) runs four Git processes in sequence, two `rev-parse` runs, a listing, and the patch, and a folder keeps no comparison (`comparison_cache.py`). One `git diff --patch-with-raw --numstat` answers it. | Deciding: `git;dur` on `/api/plugin/diff/comparison`, 82–118 → ≤ 45 ms (probed); processes per comparison, 4 → ≤ 2; `commits.cold.2` and `commits.cold.3` painted ready, 159.5 and 145.8 → ≤ 112 ms (exp-079). Guards: answers byte-identical (goldens); root-commit and shallow-boundary refusals; H79’s first painted text; H111’s deciding metric, `commits.cold.1` and its late-mode share, since both rows move `commits.cold.*`; H88 (a)’s commit revisits and H88 (b)’s Git processes per repeat; H78’s hover reuse; `region_movement_px` 0 on the Commits transitions (H86 (a)); `long_task_max_ms`. Instrument: `git-route-pairs.mjs` extended to the comparison route with a count of processes, which must be built; `architecture-probes/git_spawn_probe.py` and `architecture-probes/commit_probe.py`; `transitions.mjs` (`commits`) | **Open** (`mb-83zg`, reserved exp-096). Runs on scenario revision 5. First blocker: the extension to `git-route-pairs.mjs` |
| H117 | Opening a folder spawns a server that imports the program before it binds (0.41–0.45 s with bytecode, 0.92 s without, probed), and the shell is a new document. A `metab` started with no root, imported and bound, that adopts a root on a control message, answers the folder’s first rows within 100 ms, and a shell loaded from it attaches without a document load. | Deciding: open to the first `/api/tree` rows, 0.5–0.8 s → ≤ 100 ms (exp-037’s addendum: 503–513 ms from spawn to the first `/api`; the topology research: 0.77 s to the first page); in `WKWebView`, open to painted ready with no document load (a first load is 164–177 ms today, the UI research). Guards: identity, tab and origin checks as a spawned server gives them; exit on stdin EOF; the spare’s footprint, about 65 MB a server (topology research); one adoption per process, since `replace_root` returned only about 61% of a large root’s memory; the 350 ms first-row gate; on the landing, `region_movement_px` 0 (H86 (a)), `shift_sum_no_input.landing.cold_markdown` 0 (H91 (a)) and `shift_sum_no_input.reveal.deep_landing` 0 (H91 (b)), and revalidated requests per reload at most 1 with reload painted ready not later (H87). Instrument: `startup_pairs.py` with an adopt arm, in its `cached` bytecode state, and `wkprobe.mjs` with an attach scenario, both to be built | **Open** (`mb-obgj`, reserved exp-097). The core half of `mb-bbod` and `mb-25nv`. Before the first run: host mode’s control channel (`mb-qzny`) and H97 (`mb-touu`); a rootless start and the adopt message in `metab`; a shell that boots without a root. H17 stays attribution only, since this row takes the import off the click |
| H118 | Navigation starts after `DOMContentLoaded` and the first tree request (the tree-first order: `await loadTree()` before `navigationController.start()` in `app.js`), though the server already knows the path it renders (`index()` in `server.py` takes it as `view_path`). An inline head script that starts `/api/file` and, with H113, the render, plus module preloads after the startup scripts, puts the content at request level ≤ 2. It amends H96. | Deciding: the content’s request level, 13 → ≤ 2; `landing.cold_markdown` 290.2 → ≤ 220 ms and `landing.reload` 106.7 → ≤ 80 ms (exp-079; a rewriting proxy took the cold landing 357 → 223 ms in the UI research); the shell’s `srv` 16 → ≤ 5 ms with repository context memoized, H29’s local half (probed). Guards: first contentful paint, and the first tree rows the tree-first order protects, under the 350 ms first-row gate; `startup_script_requests` ≤ 25 and `startup_script_transfer_kb` ≤ 220; exp-062’s blank and placeholder frames; `shift_sum_no_input.landing.cold_markdown` 0 and `styled_markdown_ms` (H91 (a)); `shift_sum_no_input.reveal.deep_landing` 0 (H91 (b)), since the server inlines a deep landing’s folders; `region_movement_px` 0 on the landing (H86 (a)); revalidated requests per reload at most 1 and reload painted ready (H87). Instrument: `experiments/exp-062-levels-probe.mjs`; `transitions.mjs` (`landing`, `reveal`); `wkprobe.mjs` (`cold`, `relaunch`) | **Open** (`mb-gdmt`, reserved exp-098). Before the first run: H113 and H115 (a), and each kind’s module list read from its manifest. It runs with H113 as one round |
| H119 | The pull request view is slower on `main` (#513) than on v0.12.0, as the owner reported, and one merge holds the step. A page opened from a cache that holds the record is where a first-paint hold would show, since the cold-record path waits on GitHub either way. | Deciding: time to the record’s title on `pr-warm` (`/pull/487` from a warm cache, a fresh server), pair ratio main/v0.12.0 beyond 1.3x in two of three back-to-back pairs, then the same across the bisected merge. Context: description final, complete, and the warm reload on the same page; `pr-fresh`, `pr-store`, and the Pulls rows cold, warm, and reloaded. Instrument: `explorations/performance-loop/pr-view.mjs` with `pr-view-pairs.sh` and `pr-view-stats.mjs` | **Accepted** (exp-099, `mb-g5wf`): the pr-warm title went from 683 to 961 ms (1.33 / 1.58 / 1.38), and the bisect places the step at #369’s conversation first-paint hold (`holdFirstPaint`, `DESCRIPTION_HOLD_MS`, `pull-page.js`) by a context metric and the mechanism: across #369 a warm reload’s title went 112 → 204 ms (3 of 3 beyond), while the deciding pr-warm title was later in every pair but under the rough cut (1.14 / 1.27 / 1.18). The protocol was committed after the series, so the round is exploratory. The cold-record path and the Pulls rows’ milestones did not move; the `GET pull` route’s server time grew from v0.12.0 (already by 2026-11-12) and is open. Fixes follow under `mb-g5wf` |
| H120 | A held first paint asks for its first screen’s texts `MARKDOWN_CONCURRENCY` (two) at a time (`pull-page.js`), so a first screen of four texts waits two Markdown round trips (exp-099: requests 7, 30, 73 and 102 ms after the record on #487). Asking for the held texts at once, past the concurrency, saves one round trip, 50 to 80 ms on a fresh server. | Deciding: `pr-warm` `title_after_pull` (the title’s first frame minus the first GET pull’s response end) on #487, pair ratio under 1/1.3 in 3 of 5 pairs. Guards: title, description final and complete on every `pr` step within 1.3x. Instrument: `explorations/performance-loop/pr-view.mjs` with `pr-view-pairs.sh` and `pr-view-stats.mjs` | **Rejected** (exp-100, `mb-g5wf`): 233 → 230 ms (0.99 / 1.08 / 0.99 / 1.13 / 0.95). The requests started at the same times: only two texts are on the first screen when the hold first looks, and those two were already in flight together. The hold ended 41 to 117 ms after the last answer, so the wait is in the browser after the answers; by inference, KPress’s stylesheet load before insertion |
| H121 | A first paint held over the loading page keeps the loading heading too (`cf117163a`), so a cached pull request’s title waits with the body for the Markdown of every text on the first screen (exp-099: 212 to 258 ms after the record, against 24 to 30 ms on v0.12.0). Painting the header from the record at once and holding only the body brings the title back to the record’s arrival, and the body shows no later. The owner decided for the header first over D1’s change-once. | Deciding: `pr-warm` `title_after_pull` on #487, pair ratio under 1/1.3 in 3 of 5 pairs. Guards: description final and complete on `pr-warm` and the reload, and title and description final on `pr-fresh` and `pr-store`, within 1.3x; layout from `tests/dom/github-pull-header-chrome.mjs` (`cold-landing`). Instrument: `explorations/performance-loop/pr-view.mjs` with `pr-view-pairs.sh` and `pr-view-stats.mjs` | **Accepted** (exp-101, `mb-g5wf`): 232 → 33 ms after the record (0.12 / 0.14 / 0.15 / 0.16 / 0.13), the title from navigation 887 → 677 ms; no guard moved |

#### The exp-095 Protocol for H115

H115 lands with #455, ahead of the round that decides it, so each half stays in only
while this round says it earns its place.
Reviews A and B of #455 set what follows, and exp-095 is registered against it before it
measures.

**Revert criterion for (a), stated before the round.** (a) is backed out unless, on the
cold regime below, the asset families’ `busy` and their `read` plus `encode` are lower
than the control’s beyond the accept rule’s tolerance.
If the no-store arm matches (a) on that regime, the store’s code and memory are paid for
by the warm, shared-server case alone; the store is then backed out, and the no-store
arm is kept in its place only if it is accepted.
Either way the default is removal, not retention.

**What #455’s untimed reading shows, corrected** (review B, B1). It is one cold-server
landing per build, at a load average of about 2.5, so nothing in it is judged:

- By family, (a)’s own families fell: the assets’ `busy` from 171.0 to 152.6 ms, and
  their summed latency from 502.0 to 417.5 ms.
- The whole rise of the total, 464 to 516 ms, lay in `data`, which (a) does not touch.
  One `/api/kpress/render`, rendered in a worker thread, ended at 343.4 ms against 262
  (render 328.0 against 246.7), and the asset and `data` spans overlapped by at most
  15.1 ms.
- The control, recorder revision 6 at `9242c5cf4`, predates #449, whose Git changes the
  candidate `d7c282e82` carries: `data`’s `git` phase moved from 96.3 to 118.9 ms.
- The two asset `encode` figures time different things: the control’s ran on the event
  loop, (a)’s in up to six worker threads at once.

**Arms:**

- **Control:** this layer’s base, the tip of #449, not recorder revision 6.
- **(a):** the candidate started `--no-open`.
- **No store** (review B, B12): stamped assets compressed in a thread on every request,
  with nothing held. It separates moving compression off the event loop, which every cold
  landing gets, from the store’s warm hits.
- **(b):** the candidate in its two starts, `--no-open` against `-- --exit-on-eof`.

**Regimes** (review B, B3):

- **Cold, which decides (a):** `run.py serve`, which starts a fresh server on an unused
  port for each sample, and `server-time.mjs --warmup 0`.
- **Warm, reported as the shared-server case and not judged as the app’s:**
  `transitions.mjs`, whose measured pass follows an unrecorded one on the same server,
  `server-time.mjs --warmup 1` or more, and its serial pass.

**Readings:**

- **Primary for (a):** the asset families’ `busy`, and their `read` plus `encode`, which
  since #455 are timed one way in every route (`metabrowser.server_timing`).
- **A/A guard:** `data`’s `busy`, with `/api/kpress/render` reported apart, since that
  one request swings it by 80 ms.
- **CPU and memory:** the server’s CPU time over each window, and its resident memory
  before and after the landings (`server-time/3`; B4, B9). Moving compression off the
  loop is (a)’s cold-path effect, and one landing left about 2.6 MB held on the
  compressed path and 1.85 MB on the app’s start.
- **Gates that read `srv`:** stylesheets and `/static` scripts over 64 KB are compared
  across H115 by end of body (`end_ms`, or Resource Timing’s `responseEnd`), since their
  `srv` now includes the read and compression (B5). The 80 ms-link arm keeps
  `startup_script_last_response_ms`, where a cold far server loses the overlap of
  compression with transfer (B8).
- **Delivery:** each start’s, which `server-time/3` reports and labels (review A, A3).
  `wkprobe.mjs` and the WebKit gate start builds as the app does, so a pair of theirs
  across H115 compares compressed with uncompressed delivery; read its bytes by decoded
  size (A2).

**Waiting on the verdict:** what the store keeps on the app’s start, identity bytes the
window asks for about once per server (`mb-tbpn`, B2), and keeping only the gzip
encoding with the identity length beside it (`mb-0i10`, A11).

## Debt Carried into v0.10.0

v0.10.0 shipped with a measured regression on one corpus shape, knowingly and with the
reasoning recorded. This section states what was carried so a later reader does not have
to reconstruct it from the experiment ledger.

The release trades bulk indexing throughput for time to first content.
It streams rows to subscribers during the walk instead of completing the walk and then
serving, at roughly 14 µs per entry on the delivery path — an entry query, a contract
entry, a projection, a decoration and a wire record for each discovered entry.

On repository-shaped trees that trade is strongly positive, and is the point of the
release: first rows 1,238 ms → 230 ms, walk completion 39.2 s → 15.5 s, backend index
39.2 s → 9.3 s, measured as five back-to-back quiet-host pairs in exp-034.

On a flat mega-tree — `build_corpus` shape 2, hundreds of files per directory — the
per-entry cost dominates and no reader benefit weighs against it, because nobody reads
300,000 files. There the release is slower than v0.9.1:

| What | v0.9.1 | v0.10.0 | Tracked as |
| --- | --- | --- | --- |
| Walk with a browser attached | 18.7 s | 31.3 s (1.62-1.78x) | `mb-qvw4` |
| `/api/catalog` on a settled index | 663 ms | 2,575 ms (3.9x) | `mb-qtgj` |
| Long Tasks | none | 98 ms and 75 ms in two of five runs | `mb-zc3p` |

Three things follow, and they are the standing answers to questions this debt invites:

- **The gate is corpus-scoped, and that is not the same as weakened.** exp-035 performed
  the quiet-machine recalibration `performance-budgets.toml` asked for and it landed on
  the value already there: worst project-10 first row 317 ms, careful 1.1x tolerance
  348.7 ms, gate 350 ms.
  The release gate did not move.
  What changed is that the flat shape stopped being judged by a number calibrated from a
  different shape, and got `performance-budgets-flat-stress.toml` instead.
- **The flat-shape budget is a ratchet, not a target.** Its 450 ms is the careful
  tolerance on the candidate’s own worst run, so it cannot fail the build that produced
  it. It exists to stop the shape getting worse, and it is lowered as the debt is paid.
- **This is structural work, not constants.** The constants were measured in exp-035 and
  do not add up to a fix, and they do not share a denominator either: the walker emit
  batch is about 4% of the flat-shape walk it shortens, and the catalog content hash is
  about 0.8% of the catalog read it shortens.
  Quoting one combined percentage would mean adding savings taken from different totals,
  and an earlier draft of this section did exactly that.
  The catalog content hash was taken (1.51x on that step, byte-identical digest); the
  catalog sort key was measured and rejected, because removing the per-row encode is a
  corpus-dependent cliff rather than a saving (`mb-wpqq` carries the arithmetic); the
  walker emit batch is a real 1.2 s but delays the first emit, and was deliberately not
  taken on a release branch against the metric nearest its gate (`mb-nuhb`).

Paying this down means not building a per-entry contract object for entries the store
already admitted — the same structural change the inventory-provider work is aimed at,
tracked under `mb-kicj`.

## Reproducing the Measurements

Every number in [Background](#background) was taken by hand, outside the repository,
before the [performance loop](../../../../explorations/performance-loop/README.md)
existed; the loop’s own rounds are reproduced from their experiment write-ups.
That is a limitation of the evidence, not of the conclusions: the gaps are large enough
that corpus shape moves them by percentages, not by orders.
Still, a reader reproducing them needs to know exactly what was done, and a reader
building the harness needs the definitions to carry over unchanged.

### The corpus these numbers came from

A generator outside the repository, not `build_corpus`. It made
`pkgNNN/modNNN/fileNNNN.ext` three levels deep, 40 files per leaf directory, ten
extensions cycling, bodies from empty to a few hundred bytes.

`build_corpus` in `devtools/bench_serving.py` makes a different shape: 972 directories,
wide at the top and deep in one branch, with file bodies from 64 B to 16 KiB. **The
harness should use `build_corpus`, and its first run becomes the recorded baseline.**
Expect its absolute numbers to differ from the ones above.
What should survive the change of shape is the relation: usable tree data reaching the
browser in hundreds of milliseconds while the first row waits seconds for the scan.

### The definitions to carry over

Navigate to `/view/` for tree measurements and `/view/README.md` for document ones.
Take a median of at least five cold loads, each in a fresh browser context so no module
or HTTP cache carries over.

| Measure | How |
| --- | --- |
| First contentful paint | `performance.getEntriesByType("paint")`, the `first-contentful-paint` entry’s `startTime` |
| DOMContentLoaded | the navigation entry’s `domContentLoadedEventEnd` |
| `load` | the navigation entry’s `loadEventEnd` |
| Time to first tree row | wall clock from navigation commit until a `[role="treeitem"]` element exists |
| Rendered rows | `document.querySelectorAll('[role="treeitem"]').length` |
| DOM nodes | `document.querySelectorAll("*").length` |
| Transferred | the sum of `transferSize` across resource entries, which is compressed, so it moves far less than uncompressed size does |

Time to first row is the one that matters most and the one a naive harness gets wrong.
Waiting for `load` reports a page that painted its shell; waiting for a network idle
reports a scan that finished.
Neither is when the reader can use the tree.

### What the environment needs

Three things cost time to discover and are worth stating once.

- `uv.toml` sets `exclude-newer = "14 days"`, a relative form that needs uv 0.11.26 or
  newer. An older uv fails to parse it and `make install` stops there.
- `package.json` requires Node 24; `npm ci` refuses on Node 22.
- `metab` binds another port when the requested one is busy and prints the one it
  settled on, so the banner is more reliable than the requested port.
  `Server` in `bench_serving.py` already parses it.

## Testing Strategy

Every phase reports through `devtools/bench_serving.py` with `--label` and `--baseline`,
taken back to back on one machine, as
[the existing guidance](../../../development.md#benchmarking-scan-and-serve) requires.
Page load is the exception: its planned `bench_serving.py` phase was superseded by
`explorations/performance-loop/run.py` (`mb-pwnw`), which records and compares page-load
runs itself. A uniform shift across every row is machine noise; a real change moves the
rows its mechanism touches.

Beyond the harness:

- Budget assertions in `tests/dom` for the loader: eager core still precedes tiered
  assets, an on-demand asset is absent until its consumer runs, concurrent `ensureAsset`
  callers share one load, and a resolved asset is not refetched
- A regression test that source-view highlighting still appears when highlight.js
  arrives on the prefetch tier rather than the eager chain
- A test that the nav tree renders rows while the index reports `scanning`, which is the
  behavior Phase 2 adds and the one most likely to regress quietly
- A server-availability comparison and deterministic event-loop heartbeat test for an
  overlapping navigation-tally pass; browser Long Tasks cannot observe a blocked Python
  event loop, so the backend needs its own responsiveness gate
- A manifest-gate test for the 0.4-to-0.5 plugin SDK break and a delayed two-plugin
  behavioral test for deterministic same-kind registration order
- A test that a corpus above the current cap is browsable and reports its state honestly

## Rollout Plan

Server, shell, and built-in plugins ship as one artifact, so every phase lands as
ordinary commits with no flag.
Each performance phase is independently shippable and independently valuable: Phase 1
cuts payload, Phase 2 cuts the wait, and Phase 3 raises the ceiling.
Phase 4 is a release gate and ships as one coordinated host-plus-built-ins change: SDK
0.5 rejects an older manifest rather than trying to emulate its eager lifecycle.

The recorded baseline is the rollback signal.
A phase that does not move the rows its mechanism touches has not done its job, and the
comparison says so before the change ships.

## Open Questions

- What is the honest budget for first usable rows?
  500 ms was proposed from the shape of the waterfall, not from a measurement of the
  progressive path. exp-035 answered it for repository-shaped trees: a 350 ms gate on
  project-10 in `performance-budgets.toml`, with a 450 ms ratchet for the flat shape in
  `performance-budgets-flat-stress.toml`.
- Does row windowing cost find-in-page and select-all across the whole tree?
  [Rendering large content](../../../large-content-rendering.md) measures that trade for
  document content; the tree is a different surface and needs its own measurement.
- Should the index persist between runs?
  It would make a second open instant, and it would also hide a slow first open.
  Worth investigating after Phase 3, when the un-cached path is fast enough that a cache
  is an optimization rather than a cover.
- Is the walk parallelizable under the GIL, or does it need a different structure?
  Phase 3 measures where the 50 µs per file goes before answering.

## References

- [Rendering large content](../../../large-content-rendering.md) — the cost model this
  follows
- [Benchmarking scan and serve](../../../development.md#benchmarking-scan-and-serve) —
  the existing harness and its discipline
- [Asset loading tiers](../../architecture/arch-browser-shell.md#asset-loading-tiers) —
  the policy Phase 1 implements
- [State and delivery](../../architecture/arch-live-delivery.md) — what the inventory
  holds and how it reaches the browser
- [Mermaid diagrams](plan-2026-08-21-mermaid-diagram-rendering.md) — the first on-demand
  consumer, which depends on Phase 1

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
