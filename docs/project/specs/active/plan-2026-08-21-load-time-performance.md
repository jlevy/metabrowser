# Feature: End-to-End Load Time, from the CLI to First Paint

**Date:** 2026-08-21

**Author:** Metabrowser maintainers

**Status:** Draft

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

### Proposed Budgets

Targets to validate and adjust in Phase 1, not settled numbers.
They exist so a later change has something to fail against.

| Measure | Budget | Today, 100k | Today, 1M |
| --- | --- | --- | --- |
| First contentful paint | ≤ 200 ms | 92 ms | 176 ms |
| First usable tree rows | ≤ 500 ms | 4,525 ms | 22,328 ms |
| Rendered rows | viewport-bounded | 2,550 | 25,122 |
| DOM nodes at rest | ≤ 20,000 | 28,711 | 276,789 |
| CLI start to serving | ≤ 300 ms | 944 ms | 2,748 ms |
| Eager third-party JS | ≤ 150,000 B | 432,092 B | 432,092 B |

## Non-Goals

- Changing what Metabrowser shows.
  This is a plan about when things arrive, not about detail: the detail is the point of
  the product and none of it is traded away for speed.
- A build step or bundler
- Server-side rendering of the file tree
- Persisting an index across runs.
  Worth its own investigation once the progressive path exists; a cache that hides a
  slow path is not a fix for it.

## Background

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
`app.js` returns early without `hljs`, and `plugin_sdk.js` throws a named error without
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
throughout. `devtools/bench_browser_probe.js` measures request coalescing from inside an
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

**`static/asset_loader.js` (new).** One loader with `ensureAsset(name)` and
`prefetchAssets()`, generalizing the loaded-set and in-flight-promise semantics that
`plugin_sdk.js` already implements privately for KPress modules.
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

`PLUGIN_SDK_VERSION` does not move.
The gate is an exact-match test, so a bump would force an edit to every built-in
manifest and buy nothing; per the repository’s rule, it belongs to a break, and these
are additions.

Any change to `/api/tree`’s progressive contract or to `INVENTORY_MAX_FILES` is
observable, so it lands in `CHANGELOG.md` and in
[state and delivery](../../architecture/arch-state-and-delivery.md).

## Implementation Plan

### Ordering: Cost, Effort, and What Blocks What

The phases below are grouped by layer because that is how the code is organized.
The order to *work* them is by measured cost over effort, and the two are not the same.
Read this table first.

| Item | Wins | Effort | Order |
| --- | --- | --- | --- |
| Chart.js to on demand | 297,531 B and ~374 ms of `load`, every document | Small: one consumer, an existing `typeof Chart` guard, no protocol | **done** |
| Rows from partial index state | 4.2 s at 100k, 22 s at 1M | Medium: the data already arrives at 319 ms; the gate is in the client | **2** |
| `/api/catalog` to on demand | 4,580,060 B off the critical path at 100k | Medium, not small: `pendingChanges` in `catalog_feed.js` is unbounded, so a deferred first fetch needs a buffering policy, not a moved call | **3** |
| Row windowing | 276,789 DOM nodes at 1M | Medium: a rendering change with a find-in-page trade to measure | 4 |
| highlight.js and Mustache to prefetch | ~135,000 B off the eager chain | Small, but the win is small too | 5 |
| Whole-tree `/api/tree` cost | 4,990 ms and 3.68 MB at 1M | Large: a response-shape question | 6 |
| Startup that scales with the tree | 1.8 s at 1M | Unknown until attributed | 7 |
| `INVENTORY_MAX_FILES` | Correctness, not speed | Large: needs the walk work first | 8 |

The page-load harness is not on that list because it is not a win.
It is what makes every row of it checkable, so it comes before all of them.

Two orderings are load-bearing and should not be rearranged for convenience.
Rows-from-partial-state comes before any server work, because a client that waits for
the scan makes every server cost look like scan cost.
And the walk attribution comes before the file cap, because a cap is a claim about cost
and there is no measurement of that cost yet.

### Phase 1: The Harness and the Front-End Payload

- [ ] Add a page-load phase to `devtools/bench_serving.py`: headless Chromium against
  the corpus it already builds, reporting FCP, DOMContentLoaded, time to first tree row,
  rendered rows, DOM nodes, and transferred bytes into the existing result JSON and
  `--baseline` diff
- [ ] Record a baseline at 10,000, 100,000, and 1,000,000 files and check the numbers
  into this document, replacing the proposed budgets with validated ones
- [ ] Add `static/asset_loader.js` with eager, prefetched, and on-demand tiers, under
  the strict `tsconfig.json` gate
- [ ] Publish a tiered asset descriptor from `server.py` in place of the inline chain,
  keeping the `metabrowser:optional-asset*` re-enhance events firing
- [x] Move the Chart.js stack to on demand.
  `static/asset_loader.js` owns the loading, `plugin_sdk.js` publishes it as
  `ensureAsset`, and the agent-log charts view awaits it.
  Measured on this repository, median of five cold loads of `/view/README.md`: `load`
  853 ms to 411 ms, transferred 823,391 B to 732,836 B, vendored files on load 6 to 3.
  First contentful paint did not move, which is the expected result: the chain never
  blocked paint, it competed with the tree render behind it.
- [ ] Move highlight.js, the TOML grammar, and Mustache to prefetch-on-idle
- [ ] Re-measure and record the comparison

### Phase 2: Time to First Row

- [ ] Render nav rows from partial index state as it arrives, instead of gating on scan
  completion; the first `/api/tree` already answers in under 10 ms at every corpus size
- [ ] Show scan progress in place rather than as an empty tree, so an incomplete tree
  reads as incomplete — [degrade visibly](../../../large-content-rendering.md)
- [ ] Window the rendered rows so the count follows the viewport, keeping find-in-page
  and selection working or recording what is traded
- [ ] Move `/api/catalog` to the on-demand tier, fetched when the finder first opens
- [ ] Collapse the per-folder `/api/tree?path=…&depth=2` burst into what the viewport
  needs
- [ ] Re-measure at all three corpus sizes and record the comparison

### Phase 3: The Server and the CLI

- [ ] Attribute start-to-serving: find what scales with the tree before binding, and
  what the fixed cost is beyond the 113 ms module import and 56 ms interpreter start
- [ ] Reduce the whole-tree `/api/tree` cost, which is 4,990 ms and 3.68 MB at a million
  files on the route that answers in 9 ms while scanning
- [ ] Measure walk throughput per file and find where the roughly 50 µs goes
- [ ] Decide what replaces `INVENTORY_MAX_FILES = 500_000`: a higher measured cap, or a
  progressive index with no cap and a visible frontier.
  Silent truncation is not an option either way.
- [ ] Re-measure and record the comparison

## Reproducing the Measurements

Every number in this document was taken by hand, outside the repository, because the
page-load phase this plan asks for does not exist yet.
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
A uniform shift across every row is machine noise; a real change moves the rows its
mechanism touches.

Beyond the harness:

- Budget assertions in `tests/dom` for the loader: eager core still precedes tiered
  assets, an on-demand asset is absent until its consumer runs, concurrent `ensureAsset`
  callers share one load, and a resolved asset is not refetched
- A regression test that source-view highlighting still appears when highlight.js
  arrives on the prefetch tier rather than the eager chain
- A test that the nav tree renders rows while the index reports `scanning`, which is the
  behavior Phase 2 adds and the one most likely to regress quietly
- A test that a corpus above the current cap is browsable and reports its state honestly

## Rollout Plan

Server, shell, and built-in plugins ship as one artifact, so every phase lands as
ordinary commits with no flag.
Each phase is independently shippable and independently valuable: Phase 1 cuts payload,
Phase 2 cuts the wait, Phase 3 raises the ceiling.

The recorded baseline is the rollback signal.
A phase that does not move the rows its mechanism touches has not done its job, and the
comparison says so before the change ships.

## Open Questions

- What is the honest budget for first usable rows?
  500 ms is proposed from the shape of the waterfall, not from a measurement of the
  progressive path, which does not exist yet.
  Phase 1’s baseline settles it.
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
- [Asset loading tiers](../../../development.md#asset-loading-tiers) — the policy Phase
  1 implements
- [State and delivery](../../architecture/arch-state-and-delivery.md) — what the
  inventory holds and how it reaches the browser
- [Mermaid diagrams](plan-2026-08-21-mermaid-diagram-rendering.md) — the first on-demand
  consumer, which depends on Phase 1

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
