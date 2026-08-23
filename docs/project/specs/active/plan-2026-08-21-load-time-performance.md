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

### Ordering: What to Work Next

This order is derived from what the loop has measured, and it changes as rounds land.
The [hypothesis registry](#hypotheses) is the live source for status; this is the
reading of it, **reordered after exp-005 measured a real tree and did not confirm the
previous order**.

On a 241,000-file working tree the reader waits about twenty seconds before any row can
exist, then four minutes for a tree that takes twenty-one seconds to walk unattended.
None of that is first paint, asset payload, or render cost — the three things the first
four rounds worked on.

| # | Next | Why here |
| --- | --- | --- |
| ~~1~~ | ~~**H30** — the gitignore build~~ | **Done** (exp-006): 21.4 s to 2.5 s on the real tree, no verdict changed. What remains of the pre-walk is a second traversal that still visits every tracked directory; folding it into the indexing walk is a larger change nobody has needed yet |
| ~~2~~ | ~~**H27** — rows respond without the tally pass~~ | **Done** (exp-007): 311 ms to 2 ms, and the attached walk fell 29% as a side effect |
| 1 | **H31 remainder** — re-measure the loop (`mb-jalf`) | exp-007 took the attached walk from 70.2 s to 50.0 s. Unattached it is 21 s, so amplification is now roughly 2.4x rather than 12x. Measure with a real browser, which is heavier than the probe, before deciding whether serving needs an explicit CPU bound during a scan |
| 2 | **H39** — price the gitignore matcher (`mb-8yqt`) | One run, and it redirects the three largest rows below it. H21, H40, and H35 all attack the same 50 s from different sides; knowing whether matching or traversal dominates says which is the bigger bite |
| 3 | **H49** — measure the four unrecorded regimes (`mb-609b`) | Scaffolding, ordered here because H21 cannot be scored without the warm-reopen distinction, and because interaction latency is where a reader actually spends their time |
| 4 | **H32** — inline without a warm index (`mb-vih2`) | Cheap, and it makes exp-004’s win unconditional. Ordered after H30, which may remove the empty-index window that causes it |
| 5 | **H21** — persist the index (`mb-omhf`) | A 44 s cold open repeated every session is exactly the case persistence exists for. Larger than everything above it and worth doing once they are done |
| 6 | **H28** — build the tree from the SSE stream (`mb-ap6p`) | The streamed-delivery centerpiece. Still right, but on a real tree the reader’s problem is that rows do not *exist* yet, not that they are delivered in snapshots |
| 7 | **H18 → H22** — profile the walk, then batch it (`mb-nbc6`, `mb-tip8`) | Demoted by measurement: the clean walk is 21 s at 104 µs per directory. Worth attributing, but it is not what makes this tree slow |
| 8 | **H26 + H29** — one remote round (`mb-f591`, `mb-pk2l`) | Unchanged: costs localhost hides. Measure the stake before choosing a fix |
| 9 | **H47** — right-size the executor (`mb-squq`) | Cheap, and it is the other half of H31’s remaining question about serving under a scan |
| 10 | **H41** — columnar index (`mb-od5n`) | With H34 this deletes the tally apparatus rather than tuning it. Ordered after the measurement rows so the pass cost is attributed before it is engineered away |
| 11 | **H40** — native parallel walker (`mb-nbvk`) | Blocked on H39. The largest scan win available if matching is what costs, and it retires the negation bug rather than guarding it |
| 12 | **H42** — client-side tree replica (`mb-6rdn`) | The frontend path to a revisit with nothing on the network critical path. Independent of every walker row, so it can run in parallel |
| 13 | **H44** — the remote-link regime (`mb-ycf2`) | Measurement first. If batching wins at 120 ms RTT the way it should, it reorders much of this table |

Two orderings are load-bearing.
Attribution comes before the walker change (7), because a structural rewrite without a
profile is a guess; and the walk attribution comes before the file cap (H15), because a
cap is a claim about cost and there is no measurement of that cost yet.

### Considered and Deliberately Not Registered

A registry that only ever grows is a backlog, not a map.
These were examined during the exp-004 review and left out on purpose, so the next
reader spends their attention elsewhere rather than re-deriving them:

- **Streaming file and document previews.** The text path is already a bounded envelope
  with an explicit continuation (`fetchCompleteText`, `renderTextLoadMoreFooter`,
  `source_append.js`). The waiting-for-complete problem this plan is about does not
  appear there.
- **Chunked-encoding the `/api/tree` body as NDJSON.** It attacks the same wait H27
  removes, for a protocol change, a streaming JSON parser on the client, and an
  interaction with the gzip middleware.
  If H27 lands and a wait remains, revisit; reaching for it first would be solving the
  harder half of the same problem.
- **HTTP/2 or connection-count work for the eager asset chain.** H26 has to price the
  stake first. On localhost the ~110 requests cost little, and a fix chosen before the
  measurement is a fix chosen for a number nobody has.

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
- [x] Move highlight.js, the TOML grammar, and Mustache to prefetch-on-idle.
  The chain now starts on the first idle callback after `DOMContentLoaded`, with a 2,000
  ms floor so a busy main thread cannot defer highlighting forever.
  Measured on the 100,000-file bench corpus, median of three cold loads of `/view/`
  each, a fresh port and a fresh server per run so both the browser cache and the index
  start cold: `load` 3,883 ms to 750 ms.
  Time to first tree row did not measurably change — 854 ms against 999 ms, on ranges of
  678-1,591 ms and 690-1,106 ms that overlap almost completely.
  Accepted on the tier policy and the `load` result, not on a first-row win
- [ ] Re-measure and record the comparison

### Phase 2: Time to First Row

- [ ] Render nav rows from partial index state as it arrives, instead of gating on scan
  completion; the first `/api/tree` already answers in under 10 ms at every corpus size
- [x] Inline the root’s depth-1 rows into the shell so the first paint does not wait for
  a fetch: 1,604 ms to 242 ms at 300,000 files —
  [exp-004](../../../../explorations/performance-loop/experiments/exp-004-the-shell-carries-the-first-rows.md)
- [ ] Show scan progress in place rather than as an empty tree, so an incomplete tree
  reads as incomplete — [degrade visibly](../../../large-content-rendering.md)
- [ ] Window the rendered rows so the count follows the viewport, keeping find-in-page
  and selection working or recording what is traded
- [ ] Move `/api/catalog` to the on-demand tier, fetched when the finder first opens
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
- [ ] Reduce the whole-tree `/api/tree` cost, which is 4,990 ms and 3.68 MB at a million
  files on the route that answers in 9 ms while scanning
- [ ] Measure walk throughput per file and find where the roughly 50 µs goes
- [ ] Decide what replaces `INVENTORY_MAX_FILES = 500_000`: a higher measured cap, or a
  progressive index with no cap and a visible frontier.
  Silent truncation is not an option either way.
- [ ] Re-measure and record the comparison

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

| # | Hypothesis | Metric that would show it | Status |
| --- | --- | --- | --- |
| H1 | The prefetched libraries start on `DOMContentLoaded`, which is the same window as the first `/api/tree` fetch and the tree render, so they compete with the tree and hold the `load` event open behind them. Starting them on the first idle callback removes both. | `load_ms` down; `first_row_ms` down | **Half confirmed** (exp-001). `load_ms` 3,883 ms to 750 ms on ranges that do not overlap. `first_row_ms` did not move: 854 ms against 999 ms on ranges that overlap almost completely. Accepted on the tier policy and `load`, not on the row |
| H2 | The idle sweep that warms collapsed folders is not viewport-bounded and re-arms on every index refresh, so on a wide tree it requests folders the reader cannot see, for as long as the scan runs. Bounding it to the viewport ends the tail. | `last_resource_ms` and `subtree_requests` down sharply; `first_row_ms` unchanged or down | **Confirmed** (exp-002). 32 requests and 1,566 KB to 0 and 517 KB per cold load at 300,000 files, on ranges that do not overlap. Expanding a folder still warms exactly its newly visible children, and the click after that costs no fetch and paints in 93 ms. Time to first row did not measurably change and is not claimed |
| H3 | That sweep issues one request per ~800 ms, which does not follow from `SUBTREE_PREFETCH_MAX_CONCURRENT = 3` over a 32-path sweep. Something serializes it, and the policy should not be changed before that is known. | A counted sweep: paths per sweep and sweeps per second | **Unresolved** (exp-002), and the bound landed without it because H2 does not depend on it. Instrumented, the sweep does what it says: one sweep, 32 paths, all issued inside 545-690 ms — against a settled index, against a scan with 12.9 s left, and on both sides of the prefetch-tier change. The trickle was recorded when the corpus had not been served for a while and its walk took ~29 s against 2.7 s warm, so reproducing it needs a cold page cache, which needs root on macOS |
| H4 | `/api/catalog` is 4.5 MB at 100,000 files and nothing reads it until the finder opens, so it competes for connections and main thread during the first seconds. Moving it to the on-demand tier frees that window. | `first_row_ms` down; `transferred_kb` down | **Untestable as stated** on this corpus. `/api/catalog` is 62 bytes at 300,000 `build_corpus` files, not 4.5 MB — the catalog fills from recognized file kinds, and a synthetic tree of stub `.py`/`.ts`/`.png` files produces almost none. A real repository corpus has to reproduce the size before the tier change can be measured at all. The known trap stands: `pendingChanges` in `catalog_feed.js` is unbounded, so a deferred first fetch needs a buffering policy (`mb-296z`) |
| H5 | The root `/api/tree` answers in single-digit milliseconds when idle but took 620-721 ms while the walk was running, and it is the largest single component of time to first row. The cost is contention with the walker, not response size. | `load_tree_ms` down with server-side attribution | **Open**. Phase 3, and blocked behind H2 for the reason the ordering table gives |
| H6 | Nav rows are gated on scan completion, so the first row waits seconds for data the browser already has. | `first_row_ms` down several-fold | **Not reproduced** as stated. On `build_corpus` at 100,000 files the first row lands at a median of 854 ms, not the 4,525 ms this plan’s Background reports from a different corpus. `renderFilesFromTree` runs as soon as `/api/tree` resolves, so the gate is that request rather than scan completion. `mb-op70` should be re-scoped to H5 unless a corpus reproduces the original number |
| H7 | The tree renders every row it knows about, so DOM node count follows the corpus rather than the viewport. | `dom_nodes` bounded as corpus grows | **Open** (`mb-z7zb`). **The fix is a windowed renderer** over a flattened visible-rows array, capping the DOM at about three screens permanently; `TREE_PAGE_SIZE` caps only the *initial* mount, so a reader who expands and pages still accumulates unbounded nodes. `content-visibility: auto` on subtree containers is the cheap intermediate. Pairing either with a Web Worker that owns JSON parsing and the tree merge moves the remaining main-thread blocking off the interaction path. 3,735 nodes at 100,000 files on `build_corpus`, well under the ceiling — the shape that produced 276,789 nodes needs a wider corpus to reproduce |

### The Backlog

Nine more, from measuring the first two rounds rather than from reading the code.
Ordered by the evidence behind them, not by where they sit in the stack.

| # | Hypothesis | Metric that would show it | Status |
| --- | --- | --- | --- |
| H8 | During a scan, every root `/api/tree` pays a full navigation-tally pass. Measured: 1,567 ms scanning against 15 ms settled for the same 7,537-byte answer, and `?depth=1` (987 bytes) costs the same — so it is not payload, depth, or aggregation. The mechanism is in the code: `navigation_tallies` memoizes on the index revision (`inventory.py`), the walker moves that revision with every write, so while scanning the memo can never hit and each root request redoes the O(index) pass (~486 ms/100k per its own comment, plus an `entries()` snapshot copy per request). Serving slightly stale tallies during a scan — recompute at most every N ms, or only when files-indexed has moved by a threshold — removes ~85% of time to first row in that regime. | `load_tree_ms` and `tree_reprobe_ms` while `index_status_at_probe` is `scanning`; floor 15 ms | **Partly resolved** (exp-003). H23 was the mechanism and it landed: root `/api/tree` fell from 650 ms to 394 ms scanning and 12 ms to 6 ms settled. What the split never described, and what exp-003 makes explicit, is the *first* request of a page load — its memo is cold by construction, so `load_tree_ms` did not move. That is H20’s job, not this one. What is left for H8 itself is the GIL share taken by per-entry stores (H22) |
| H9 | The shell fetches **74 separate JavaScript files** on every load — 33 from `static/`, 41 from built-in plugins — over HTTP/1.1, so they queue six at a time, and `app.js` cannot ask for the tree until its own chain has run. | Shell boot, as `first_row_ms` minus `load_tree_ms`; about 180 ms today | Open. Small next to H8, and it is the part a bundler would fix, which this project has decided against — so the question is whether the count can drop instead. H26 reframes the stake: localhost hides a per-request cost that `--remote` pays in RTTs |
| H10 | Twelve render-blocking stylesheets, eight of them per-plugin, sit between the HTML and first paint. | First contentful paint | **Open.** Was blocked — paint entries return `[]` in a pane created hidden — but a recreated, fronted pane reports them, and the probe now records `fcp_ms` (null where unsupported, never 0). Needs runs where the pane is visible from the first navigation |
| H11 | The tree re-render replaces the whole `#tab-files` panel with `innerHTML` rather than patching it, so every refresh rebuilds every row. | A long-task measure around `renderTreeNodes:root`; 52 ms at 334 rows today | Open. Cheap at this corpus, and it is the same code row windowing (H7) has to change anyway |
| H12 | `/api/recent` is 68,748 bytes and 86 ms settled, and a recency filter puts it on the load path. | `first_row_ms` with a recency filter active | Open, low. Nothing measures the filtered load path yet |
| H13 | The walk runs at about **43 µs per file** — 300,000 files in 12,871 ms — and nobody has attributed that number. | Walk elapsed per file, by layer | Open (`mb-kp6c`). Attribution before any change: a cap is a claim about cost |
| H14 | Start-to-serving scales with the tree rather than with the code. | CLI start to first served request, across corpus sizes | Open (`mb-kp6c`). Ordered after H8, because a client that waits 1.5 s on a lock makes every server cost look like scan cost |
| H15 | `INVENTORY_MAX_FILES = 500_000` truncates a larger tree and says so only in a banner. | Correctness, not speed | Open (`mb-s5p6`). Needs H13 first: replacing a cap means knowing what the cap was buying |
| H16 | Time to first row on a real repository does not behave like time to first row on `build_corpus`, whose 972 directories are uniformly wide and whose files are stubs. | Every metric, against a checked-out repository of comparable size | **Confirmed, and worse than stated** (exp-005). A real tree has 2.4 files per directory against `build_corpus`’s 309 — a 128× difference in how often every per-directory cost is paid, invisible to every measurement before it. It surfaced H30, H31, and H32, and it showed exp-004’s headline result to be conditional on a warm index |
| H17 | Importing `metabrowser.server` costs 390-770 ms before any walk — `python -X importtime`: kpress ~74 ms, `plugin_loader.manifest` + pydantic model construction ~60 ms, `plugin_api` ~45 ms, `classify` ~57 ms, `inventory` ~38 ms, `activity` ~30 ms — and `discover_plugins` runs at module scope (`server.py`), so manifest validation is paid at import. Deferring plugin discovery and the kpress import off the serving path cuts CLI start-to-serving by most of its fixed half. | `importtime` totals, and `bench_serving.py` start-to-serving | Open (`mb-kp6c` carries the attribution). The plan’s earlier “113 ms module import” undercounts on this machine by 3-6x |
| H18 | The walk costs ~43 µs/file (300,000 files in 12,871 ms warm), and the structure says where: one `to_thread` per directory is cheap (972 hops), but every entry is yielded one at a time through an async generator onto the event loop, and each write updates the index and moves the rollup revision. Batching emission per directory — one loop hop per directory instead of per file — cuts walk elapsed materially, and also slows the revision churn that H8 depends on. | `inventory walker complete: elapsed=` in the server log, same corpus warm | Open (`mb-nbc6`). Attribution first (profile one walk), then the batch change as its own experiment. The structure, from reading walker.py and inventory.py: one async-generator yield per entry (300,000 loop iterations per scan), one `_store_walker_entry` per entry on the serving event loop with an O(depth) ancestor-aggregate update per file, `dataclasses.replace` copies at finalize, and one `to_thread` hop per directory. H22 is the batch-everything experiment this predicts |
| H19 | `/api/events` blocked 3,669 ms in the original waterfall before any row appeared. Never re-observed under the fixed harness, and the original was taken in the same degenerate pane as H6, so it may be an artifact. | The events stream’s time-to-first-message during a scan, from the resource timing of the EventSource | Open (`mb-fhfh`), needs reproduction before any change |
| H20 | The first tree paint waits for a round trip it does not need. `first_row_ms` is `DOMContentLoaded` (~180 ms) plus `loadTree` (850–1,500+ ms during a scan), yet the index handler could embed the root’s depth-1 entries as inline JSON — from the warm index, or from one synchronous `scandir` of the root, which is single-digit milliseconds — and let the client render rows at DCL and reconcile when `/api/tree` lands. The shell already server-renders the Files panel chrome for exactly this reason; the first data should ride the same vehicle. | `first_row_ms` ≈ FCP + render at every corpus size and in both scan regimes | **Confirmed** (exp-004). 1,604 ms to 242 ms at 300,000 files, non-overlapping, and `first_row_ms` now tracks `dcl_ms` almost exactly — the tree is usable at DOMContentLoaded rather than one slow round trip later. Main-thread blocking fell with it, 268 ms to 65 ms. Cost: 34 KB, being the inline payload plus the thirteen now-visible folders exp-002’s sweep correctly warms. Inline only the unfiltered default view, so filter state cannot diverge |
| H21 | The “no persisted index” non-goal is priced wrong for a *browsing* tool, whose common case is reopening the same tree. Persist the index at walk end and load it on start, serving stale-labeled data instantly while a revalidation walk runs — the UX contract for staleness already exists (`tally_cache_status=scanning`), and fdu proved the snapshot-plus-revalidate pattern on the same machine. The plan deferred this “until the progressive path exists”; it now exists. | Start-to-usable-tree on a revisit of a 1M-file tree: seconds to sub-second. Cold first visit unchanged | Open, large (`mb-omhf`). The biggest single lever at large N. **The invalidation story is a bounded revalidation**: a directory’s mtime moves when its direct children change, so the sweep `stat`s only directories and rescans only the subtrees that moved — git’s untracked-cache mechanism, and what separates a revalidation from a second full walk. H46 accelerates that sweep per platform; H49 supplies the warm-reopen metric it would be scored against. Three predictions worth scoring it on: loading 300,000 entries costs around 100 ms, a warm reopen reaches first row within twice the shell’s own paint time, and the sweep finds under 1% of directories changed on a typical revisit — if the last is false the approach is worth much less, and one measurement says so. Needs an invalidation story (mtime-revalidate per directory, walk in background) and a format decision measured for load cost |
| H22 | The walk’s ~43 µs/file is mostly per-entry Python by construction, not filesystem cost: every entry crosses an async-generator boundary one at a time, is stored by a per-entry call on the serving event loop, and updates ancestor aggregates O(depth) per *file* — while the walker already computes per-directory aggregates at finalize, so the per-file propagation is double bookkeeping. Batching the pipeline per directory (yield lists, store lists, one ancestor update per directory) removes ~300,000 loop iterations and most per-entry overhead per scan. | Walk elapsed down 2×+ at 300k; event-loop availability during scan up (measured as during-scan `/api/tree` latency with H23 already in place) | Open (`mb-tip8`). Do H18’s profile first so the before is attributed, then land as one structural experiment |
| H23 | During a scan, every root `/api/tree` recomputes navigation tallies over the whole index because the memo keys on `rollup_revision()`, which advances on every write — at 256-entry batches and ~23k entries/s that is ~90 revisions/s, so the memo cannot hit until the walk ends. The docstring itself prices the pass at ~2 s at 400k entries. Serve tallies at bounded staleness during a scan: recompute at most once per window, single-flight, reuse between. The payload already labels them provisional. | Root `/api/tree` during a scan: 837–1,567 ms → near-settled (~15–50 ms); `first_row_ms` during scan drops by most of a second | **Confirmed** (exp-003), and it found a second O(N) cost the hypothesis missed: the route copied every index entry on the *event loop* before the pass it fed even started. Bound is `max(0.5 s, last pass cost)` — derived rather than constant, because the pass visits every entry and a constant right at 10,000 files starves the loop at a million. A fixed 0.5 s reached only 518 ms (the nav polls at 1 s, so a shorter bound can never be hit by a poller); request-triggered background warming was measured and rejected |
| H24 | The client runs two progress channels at once through the scan — the 1 s `/api/index/progress` poll *and* the SSE stream that already pushes completion — and each poll can trigger a depth-0 tree refetch and a full re-render (H11), all landing in the window where the server is busiest. Consolidate progress onto the stream it already holds, keep the poll as a fallback only. | Requests issued during a 13 s scan; `renderTreeNodes:root` span count during scan | Open (`mb-n352`). Pairs with H11; the two together decide how often the tree redraws while scanning |
| H25 | `/api/tree` re-serializes and re-gzips an unchanged answer for every poller and every tab; `/api/rollup` already keeps an encoded-body cache keyed by ETag for exactly this. Give the tree route the same (revision, params)-keyed body cache and validator. | Settled root `/api/tree`: ~15 ms → ~1 ms; multi-tab during scan shares one encode | Open, small and mechanical (`mb-43v7`) — worth batching with H45, which replaces the encoder whose output this would cache, and see H44 for `zstd` and for keying the cache per revision. Worth batching with H23 since both touch the same handler |
| H26 | The eager request count is priced at localhost, where ~110 requests over six HTTP/1.1 connections cost little; `metab --remote` tunnels the same page over SSH, where ~19 serial connection-rounds × RTT land before the first API call — at 50 ms RTT, roughly a second of shell alone. One measured `--remote` (or throttled) load would set the real stake for H9/H10, and a server-side concat of the eager `static/*.js` in tag order — no bundler, tier policy intact — is the count fix if it matters. | Shell-ready time over a ≥50 ms RTT link, before vs after count reduction | Open (`mb-f591`). H44 now owns the general version of this, adding an RTT knob so request count is priced where it actually costs. Measure the stake first; the fix is only worth its complexity if the remote number says so |
| H27 | Even with the staleness bound, the *first* root request during a scan pays the cold tally pass — `load_tree_ms` stayed near a second in exp-003/004 while the repeat-request cost fell to 394 ms — because the response couples cheap rows to an O(index) computation in one JSON body. Decouple them: the tree responds with rows immediately and the tallies arrive separately (a second cheap request, or the stream). `updateFilterTallies` already guards every field, so a payload without tallies is tolerated today. | `load_tree_ms` during a scan → tens of ms; filter counts fill in behind it | **Confirmed** (exp-007). A row request now serves tallies only from a fresh memo; `depth=0` is the channel that computes them, fetched behind the render by the `scheduleRootSummaryRefresh` that already existed. 311 ms to 2 ms on the official corpus, 777 ms to 6 ms and 67 ms to 1 ms on the two real trees, all non-overlapping. Nothing was made faster — the expensive work was moved off the path that did not need it |
| H28 | The tree is delivered as snapshots the client re-fetches on a poll, then re-renders wholesale — while the walker already publishes `fs.change` ops on the SSE stream the page holds open, scoped to `root-depth-2`, which is exactly the rows the nav renders. Build the tree progressively from the stream: insert rows as they are discovered, and drop the poll-triggered refetch loop. Absorbs the H11 (patch-not-replace) and H24 (two progress channels) directions into the change that makes both moot. | `renderTreeNodes:root` span count during a scan → per-batch bounded inserts; snapshot refetches during a scan → 0; on a large tree the nav visibly fills in live | Open, large (`mb-ap6p`). **The tallies belong on that same stream**: the nav polls `depth=0` about once a second per tab and the whole staleness apparatus exists to survive that poll, so pushing tally updates alongside the `fs.change` ops — throttled to a couple per second during a scan — retires the poll, the per-tab request rate, and the GIL contention exp-005 found. A client fetch becomes subscribe, then backfill since revision R; H36 is the cheap version of the same observation. The full streamed-delivery design revisit; do after H27 proves the decoupling on the simpler payload |
| H29 | The shell blocks its first byte on `discover_repository_context` (a filesystem walk up plus config parse, off-thread but serial) and then ships as one buffered response — so the browser cannot start fetching CSS or JS until Python has finished building the whole page. Flush the head early and move repository context out of the pre-first-byte path. | Time from request to first stylesheet fetch; shell-ready over a ≥50 ms RTT link | Open (`mb-pk2l`). Pair with H26’s remote measurement — on localhost the whole shell is ~200 ms and the win may be invisible |
| H30 | `build_gitignore_check` costs 19.4-23.3 s on a real 241,000-file tree, before the walk starts and therefore before any row can exist — larger than the 21.0 s walk it precedes. Nothing in this plan accounted for it, and no browser metric shows it: the page loads fine with nothing to put in it. | Time from process start to the first entry existing | **Confirmed** (exp-006). `load_gitignore` did a second full `os.walk` of the tree before the indexing one, pruning nothing. Pruning ignored subtrees and hidden directories -- both semantics, not shortcuts, since git does not read a `.gitignore` inside an ignored directory either -- took it from 21.4 s to 2.5 s on the tree that motivated it and 0.75 s to zero on the second, with compiled patterns 10,668 to 327. No verdict changed on 341,872 visible paths |
| H31 | Watching a scan makes it twelve times slower. Measured warm on a real tree: 21.0 s unattached against 258.3 s with one client polling every 2 s. Each nav request costs a tally pass that grows with the index (0.75 s at 120,000 entries, 1.5 s at 241,000), that work competes with the walker for the GIL, the walk slows, the window lengthens, and more polls land inside it — each more expensive than the last. A real browser is a heavier client than the probe. | `walk_elapsed_ms` attached against unattached | **Partly resolved** (exp-007), from the other end than expected. Removing the per-request tally cost cut the attached walk on the real tree from 70.2 s to 50.0 s without touching the walker: the requests were not only slow, they were taking CPU the walk wanted. With exp-006 the attached walk is 258 s to 50 s. What remains is whether a real browser — heavier than the probe — still amplifies |
| H32 | exp-004’s inline fires only when `inventory_has_data()`, and on a first open of a real tree the index is empty at page-render time — behind H30’s twenty seconds. The probe recorded `inline_rows: null`. So a result measured as 1,604 ms to 242 ms is conditional on a warm index: it helps a second load and not a first open, which is the case it was built for. | `inline_rows` non-null, and `first_row_ms`, on a *first* open of a real tree | Open (`mb-vih2`). One synchronous `scandir` of the root is ~37 µs measured, so the fallback is cheap; the question is whether it is correct while the index is still empty |
| H33 | Ignored subtrees are usually the bulk of a real tree and the least interesting: one keeps 232,190 files under two `target` directories. Crawling everything but ordering the frontier so tracked entries are discovered and published first would give a reader a usable tree in a fraction of the total scan. Flags still control what is revealed; only the order changes. | Time until all *tracked* entries are indexed, against total walk; `first_row_ms` unchanged or better | Open, **P0** (`mb-6yh2`). Sized after exp-006: 48% of files and 59% of directory yields are ignored, and the last *tracked* file is seen at 29.94 s of a 30.06 s walk — level order interleaves the two completely, so the tracked tree is never ready early. BFS already yields a directory placeholder before enqueueing it, so the nav’s *shape* is complete long before its contents; only the descent needs reordering, into a secondary queue drained after the tracked frontier |
| H34 | The tallies are sums over per-entry attributes, and every mutation already funnels through `_replace_index_entry` / `_pop_index_entry` under one lock. Maintaining them incrementally there makes the pass O(1) amortized and retires the whole staleness apparatus: no memo, no bound, no derived-cost heuristic, no residual GIL contention with the walker. | `srv_scanning_ms` at its floor with the memo deleted entirely | Open, **P1** (`mb-0cmt`). exp-003 and exp-007 both work around this cost; this is the fix the bound is standing in for |
| H35 | On a git working tree, `git ls-files -co --exclude-standard -z` returns the visible set directly, in C, with git’s exact semantics — including the negation cases the current `rel_dir` prefixing gets wrong. | Time from process start to the first entry existing; and the negation cases the prefixing mis-answers | Open, **P1** (`mb-9ge2`). Could take exp-006’s remaining 2.2 s to near zero *and* fix a correctness bug, with the existing walk as the non-git fallback |
| H36 | The tally pass still runs in a thread that is GIL-bound Python competing with the walker, just less often. Serving the last memo regardless of age while the status reports scanning — recomputing once on completion — removes the rest, and the client is already told those numbers are provisional. | `walk_elapsed_ms` attached against unattached | Open (`mb-26ey`). The cheap half of H34 |
| H37 | `os.path.relpath(str(here / name), str(root))` builds two `Path` objects and normalizes a path for every directory the prune considers. `os.walk` is top-down, so the parent’s relative path is in hand and the child’s is a string concat. | `gitignore_build_ms` on a tree with hundreds of thousands of directories | Open (`mb-n3is`) |
| H38 | Scroll and expand cover the two ways a reader *acts* a row into view. A window resize or a pane-splitter drag also reveals rows and re-arms nothing, so enlarging the window leaves the newly revealed folders cold until the reader scrolls. | `subtree_requests` after a resize that reveals rows | Open (`mb-r391`) |
| H39 | What remains of the walk may be pattern *matching* rather than traversal: the ignore check runs per entry, and exp-006 cut the compiled pattern set 10,668 to 327 without anyone measuring what the matcher still costs. Price it before replacing the walker. | `walk_elapsed_ms` with and without `gitignore_check` | Open, **P0** (`mb-8yqt`). Attribution, and it gates H40: replacing a traversal that is not the bottleneck would be the expensive way to learn this |
| H40 | A native parallel walker over ripgrep’s ignore crate would collapse the scan by an order of magnitude, because the walk is per-entry Python competing with itself under one GIL. | `walk_elapsed_ms` on the real tree | Open (`mb-nbvk`). Large, and blocked behind H39 |
| H41 | A columnar index makes the tally pass vectorized rather than a per-entry Python loop, cheap enough to delete the memo, the bound, and the derived-cost heuristic outright. | Tally pass duration at 300,000 and 1,000,000 entries | Open (`mb-od5n`). The heavier alternative to H34 |
| H42 | A client-side tree replica painted before the server answers makes a revisit cost no network on the critical path. | `first_row_ms` on a revisit, offline | Open (`mb-6rdn`). The browser-side counterpart to H21 |
| H43 | Walking the viewport’s subtree first makes the visible tree correct long before the scan ends — the reader’s question is answered by a fraction of the work. | Time until the on-screen subtree stops changing | Open (`mb-w2f3`). Composes with H33, which orders tracked before ignored; this orders visible before the rest |
| H44 | Under realistic latency, batching the subtree prefetch into one request beats every server-side win so far, because ~110 requests over six HTTP/1.1 connections is priced at localhost and paid in RTTs. | `first_row_ms` and total prefetch time at 0 ms and 120 ms RTT | Open, **P0** (`mb-ycf2`). Supersedes the framing of H26 by adding the engineering, not just the measurement. Three changes follow if it holds: one `/api/trees?paths=...` request in place of up to 32; offering `zstd`, which current Chrome and Firefox accept and which beats gzip-6 for less CPU; and extending H25’s encoded-body cache per revision so a settled index serves bytes it compressed once |
| H45 | Serialization is a measurable share of large tree and rollup responses, and `orjson` would show it. | Server time on `/api/tree` and `/api/rollup` at 300,000 entries | Open (`mb-0l4a`) |
| H46 | Bulk-attribute syscalls cut the verification sweep that H21’s persisted index would depend on: `getattrlistbulk` on macOS returns attributes for many directory entries in one call, `io_uring` batches `statx` on Linux, and on Windows the USN journal replaces the sweep with a change feed. | Verify-sweep duration on an unchanged 241,000-file tree | Open (`mb-19em`). Only matters once H21 exists |
| H47 | A 64-worker executor sized for I/O waiters hurts the CPU-bound work now routed through it: under one GIL, more workers is more contention, not more throughput. | Tally and encode latency, and walk time, against pool size | Open (`mb-squq`) |
| H48 | A free-threaded build makes the existing thread offloads actually parallel — and would surface every shared-state assumption the GIL is currently hiding, including the one the F2 finding exposed. | Attached `walk_elapsed_ms` and tally latency on 3.14t against 3.14 | Open (`mb-ltm2`) |
| H49 | The four unmeasured regimes hide regressions the cold-load metric cannot see: interaction latency, churn recovery, resident size, and warm reopen. | Interaction latency, churn recovery, resident size, warm reopen | Open, **P0** (`mb-609b`). Every number in this plan describes one cold load of a settling tree; nothing describes using the thing |
| H50 | Two regions are rendered before they have content and grow when it arrives: the filter bar, shipped empty for `filter_controls.js` to fill, and the tally row, which paints with the inlined rows and gets its numbers from a later request. The page moves under the reader on every load. | `total_downward_shift_px`, measured directly as populated height minus empty height | **Confirmed** (exp-009). 67 px together, now 23. Both reserve a line box of the type they hold rather than a measured constant, because the shell offers a choice of font sets. The filter bar is settled at zero; the tally row keeps 23 px because its settled height depends on its own content, which is H54 |
| H51 | The two metrics a browser would actually report — largest-contentful-paint and cumulative layout shift — are unmeasured, and unmeasurable here: Chromium does not compute LCP for a page that has never been visible, and this pane is permanently hidden and collapses to 0×0 on navigation. | `lcp_ms` and `cls`, non-null, from a visible window | Open, **P1** (`mb-qf2p`). The probe records both plus `page_visible` and `page_laid_out`, so an absent number reads as an environment limit rather than a good result. Needs a headed run |
| H52 | The shell ships placeholders, not a skeleton: the filter bar is empty, the files panel is “Loading files…”, the preview pane is one line of text. First paint is chrome plus three placeholders, each later replaced wholesale. Server-rendering resting-state chips and placeholder rows would make the structure look complete at first paint. | `skeleton_complete` at first paint; region repaint count | Open, **P1** (`mb-rxst`). exp-009 stopped the page *moving*; this is what would stop it *assembling*. The obstacle is duplication — the chip markup lives only in `filter_controls.js`, so a server-side counterpart needs a shared source or it drifts |
| H53 | The tree region is painted three times per load — inlined rows, fetched rows, refresh — each a wholesale replacement of the whole panel. | Repaints per region per load, target 1 | Open (`mb-t5x3`). exp-009 added the metric; exp-010 confirmed it is a regression rather than a standing cost, measuring 1 paint before the campaign against 3 after. H11 is the fix. Should extend past the tree region to the preview pane and the filter bar |
| H54 | The tally row’s settled height depends on its own text: `.tree-summary-split` reports tracked and ignored files separately and wraps to a second line in a 300 px navigation pane, so no fixed reservation fits both states. A one-line floor leaves the wrap uncovered; a two-line floor leaves dead space whenever the row does not wrap. | `summary_shift_px` at 300 px and at a pane wide enough not to wrap, both zero, with no idle gap in either | Open, **P2** (`mb-w3va`). The remainder of exp-009: 23 px of the original 67. The fix is to make the pending row the same shape as the settled one — same classes, same cell count, placeholder glyphs sized like digits — so it wraps identically, rather than to raise the floor |
| H55 | The campaign’s numbers span seven corpora and none of them compare, so nothing says what all of it bought. Each round measured its own control against its own candidate, which is sound per round and is why the verdicts stand, but it leaves the campaign itself unmeasured. | Every checkpoint’s standing metrics against one corpus with one harness, in one table | **Confirmed** (exp-010, `mb-3a3h`). Answered by holding the corpus and the harness fixed and moving only `src/metabrowser`: first row 1,473 ms to 276, server share of the first tree fetch 1,099 ms to 6, tail 28.9 s to 12.3. It also surfaced two regressions no round could see from inside itself — repaints 1 to 3, and shift 42 px to 67 on main before this branch took it to 23 |

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
