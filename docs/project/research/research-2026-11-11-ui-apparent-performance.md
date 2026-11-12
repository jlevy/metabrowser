# Research: Apparent UI Performance for the Native App

**Date:** 2026-11-11

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Complete

## Overview

Metabrowser’s browser UI is moving into a native macOS app: an AppKit shell around a
`WKWebView` that talks to a warm per-root server (see
[native app server topology](research-2026-11-10-native-app-server-topology.md)). The
product requirement is design principle 6 in the
[design system](../../design-system.md): everything is effortlessly fast.
For the app, that means every transition paints its destination at once, with no blank
or loading frame, no visible delay, and no content that moves after it appears.

The app changes the cost model in two ways that matter here.
We know the exact engine (WebKit in `WKWebView`), so we can tailor to it instead of to
every browser. And we can pay up front: preload code at launch, prefetch data while the
user reads, and keep rendered results in memory or on disk.

This research inventories how the UI performs today, finds where transitions do work at
click time that could have been done earlier or kept, and ranks the improvements by
effort and by payoff in apparent speed.

## Questions to Answer

1. Which transitions do visible work at click time today, and what kind: network,
   render, or teardown and rebuild?
2. Which surfaces can be kept alive or rendered ahead so a switch is only a visibility
   change?
3. What should be prefetched, at what priority, and when, so that prefetch never delays
   the request the user is waiting on?
4. Where does content shift during transitions, and how is each shift removed?
5. What does delivery cost (HTTP caching, request counts, parse and evaluate), and what
   changes when the shell runs inside `WKWebView` instead of Chrome?
6. Which measurements should become budgets so the gains stay?

## Scope

**In scope:** the browser shell and built-in plugins on `main` at `7a02fed4`; every
user-visible transition (file selection, view tabs, the Files, Commits, and Pulls main
tabs, pull request page tabs, history, folder expansion); prefetch and caching on both
sides of the wire; startup loading; layout shift; WebKit and `WKWebView` platform
behavior.

**Out of scope:** server indexing throughput (covered by the
[engine performance model](../../engine-performance-model.md)), the native shell’s own
window and process management except where it affects web view warmth, and visual design
changes.

## Findings

### Baseline: What Transitions Cost Today

Measured in headless Chrome over the DevTools Protocol against a server for this
repository (about 9,000 indexed files) with trusted pointer input, two runs per
transition, on a machine at load average 18–21. “Painted ready” is two animation frames
after the destination is complete, so about 30 ms is the instrument’s floor.
Counts were identical in both runs; times are noisy and shown as the pair.

| Transition | Painted ready (ms) | Requests | Preview replaced | Pane meanwhile | Layout shift |
| --- | --- | --- | --- | --- | --- |
| View tab, first visit (Rendered to Source) | 43, 43 | 0 | no | unchanged | none |
| View tab, revisit | 32–33 | 0 | no | unchanged | none |
| Files to Commits | 315 (first), 32 (later) | 3 | yes | empty prompt | tree pane 37 px |
| Commits to Files (restores the open file) | 66–81 | 3 | yes | empty for 1–2 frames | tree pane 37 px |
| File to file, cold Markdown (72 KB render) | 296, 529 | 13–18 | yes | old file kept | tree rows 44–89 px (folder disclosure) |
| File to file, cached revisit | 80–148 | 1–3 | yes | old file kept | none |
| History back to a cached file | 62–63 | 1–2 | yes | old file kept | none |
| File to file after a 400 ms hover | 81–114 | 1 | yes | old file kept | none |
| Cold landing on `README.md` | FCP 120–132, ready ~450 | 62–72 scripts, 750–826 KB | — | — | 0.003 (body moves 21 px at ~445 ms) |

While the old file is kept, a loading placeholder is mounted but stays invisible: it
appears only after the 50 ms `--loading-state-delay`, and no visible spinner was seen in
any file transition.

Four facts explain most of the table:

- **A view tab switch is a visibility toggle.** The shell creates one container per
  view, mounts the default, and mounts the rest on first selection (`initTabs` and
  `_metabrowserMount` in `static/app.js`). Revisits do no work, which is why they sit on
  the instrument floor.
- **A main tab switch rebuilds the preview.** `openMainTab` in `static/main-tabs.js`
  calls `cancelPreview()`, pushes the remembered route, and runs
  `navigationController.restore()`. The pane is emptied and the restored file is
  rendered again, including a new `/api/kpress/render` request and new requests for the
  Markdown worker scripts.
- **Only the file envelope is cached.** `fileCache` holds `/api/file` JSON. Rendered
  Markdown needs a second, serial request to `/api/kpress/render`, which nothing caches,
  so every revisit downloads the full body again and rebuilds the DOM. Hover prefetch
  warms only the envelope, so a hovered file still waits for the render.
- **Chrome that toggles moves content.** Hiding `#nav-filter-bar` on a switch away from
  Files moves the tree 37 px, and showing it moves the tree back.

### Transitions Rebuild Instead of Retaining

A wider inventory of 130 transitions (two passes, each journey in a fresh profile)
confirms the baseline and sharpens it.

**File to file never shows a blank frame.** All 84 file, keyboard, and history rows
showed zero blank frames and zero visible spinners.
The staged render works: the new file mounts into a transparent stage while the old one
stays visible, and the stage’s nodes replace the pane in one step.

**But nothing is ever reused.** Every transition, including a revisit of a file shown
seconds earlier, rebuilds the pane: 3 to 5 top-level nodes replaced and at least one
data request.
Revisit painted-ready was 39 to 61 ms for small Markdown, 125 to 159 ms for
a 156 KB document, and about 300 ms to highlighted for a 313 KB source file.

**Main tabs destroy the preview.** `openMainTab` cancels the preview
(`main-tabs.js:216`), and a tab with nothing selected replaces the pane with a prompt
(`showNavigationLanding`, `app.js:7657`). Returning to Files shows that prompt for 2 to
5 frames, takes 59 to 104 ms, and issues 3 requests.
When both tabs have a selection, the old surface stays until the new one is ready, so
there is no blank frame, but the switch still re-fetches and rebuilds: 71 to 327 ms.
The first Commits show waits on three serial requests (`git/repo`, `git/refs`,
`git/log`): 320 to 1,093 ms, with a loading element in the panel for over 300 ms.

**Heavy view tabs pay full layout on every visit.** View tabs hide with `display: none`
(`app.js:6194-6196`), which discards layout.
Ordinary files switch in one or two frames, but on a 4.3 MB JSONL log, Log to Raw
blocked the main thread for 1,317 ms on first visit and 678 ms on the revisit (n=1). The
folder Treemap is torn down when hidden and rebuilt when shown.

**Commits and Pulls repeat work they could keep.** Commit detail is cached
(`detailCache`, `git-panel.js:113`), but the diff comparison is fetched on every
selection (`beginDiffPreparation`, `git-panel.js:838-856`): 88 to 141 ms per revisit for
a result named by an immutable commit ID. A pull request click reads `pull?number=N` two
to four times, because the click does not join the read the mousedown peek started 1 to
60 ms earlier (`pulls-panel.js:3588-3597`). A pull request revisit still issues 10 to 11
requests. Holding an arrow key in the Files tree renders every intermediate file: six
keypresses cost 14 requests and 28 node replacements, where the Pulls panel already
coalesces (`WALK_SETTLE_MS`, `pulls-panel.js:78`).

### Retaining Layout Is What Makes a Switch Instant

The cost of showing a surface again was measured directly, n=5 per cell (median ms).
“Detached” moves the surface’s nodes out of the document and back; “laid out, hidden”
keeps them in place under `content-visibility: hidden`.

| Surface | Elements | Today’s revisit | Detached, re-attached | `display: none`, shown | Laid out, hidden, shown |
| --- | ---: | ---: | ---: | ---: | ---: |
| README.md | 486 | 31–55 | 5.6 | 5.0 | 0.8 |
| design-system.md | 2,728 | 102–154 | 36.7 | 34.4 | 1.2 |
| app.js, highlighted | 12,962 | 177–182 | 106.1 | 106.6 | 29.3 |
| Commit view | 2,178 | 128–223 | 11.2 | 10.6 | 4.0 |
| PR Changes | 2,304 | not isolated | 15.3 | 14.0 | 6.1 |

Layout is most of the memory, measured as heap after forced collection over 20 clones:

| Surface | Detached, per surface | Laid out and hidden, per surface |
| --- | ---: | ---: |
| README.md | 148 KB | 1.1 MB |
| design-system.md | 644 KB | 7.7 MB |
| app.js, highlighted | 3.1 MB | 29.0 MB |

So there are two tiers.
A detached surface is cheap to keep (thirty design-system-sized ones are about 19 MB)
and makes ordinary revisits one frame.
A laid-out hidden surface is instant at any size but costs about ten times the memory,
so it suits a small, fixed set: the current surface of each main tab and the recent
views of the open file.
A client cache of render *payloads* alone saved only 7 to 16 ms per revisit; caching
data without the DOM does not make a switch instant.

### The Markdown Render Chain

Rendered Markdown is a strictly serial chain:

1. `GET /api/file` returns the envelope with an ETag.
2. The kind’s plugin modules load, once per kind per page.
3. A worker runs `prepare-primary` over the source.
4. `POST /api/kpress/render` uploads the prepared source and returns rendered JSON.
5. KPress runtime scripts named by the response load.
6. The client parses, enhances links, builds the table of contents, lays out, and swaps.

Step 4 is a POST for nearly every document.
Preparation inserts an anchor before every heading (`wiki-parser.js:95-117`), so
`changed` is true even without wiki links, and `fetchKpressRender` then posts the whole
source (`rendered.js:176-181`, `plugin-sdk.js:1250-1262`). A headless check confirmed
it: 19 KB uploaded for README.md, 190 KB for design-system.md, and 43 KB for
architecture.md. The response cannot be cached by HTTP, and the render cannot be
requested before the source and the worker have run.
Hover prefetch (`app.js:2758-2823`) warms only step 1, and keyboard focus prefetches
nothing. A server-cold render costs 124 to 292 ms for large documents, and that cost
lands on the click.

### Layout Is the Main-Thread Cost

Quiet traces (no probe) of revisits put the time in layout, not script or style:

| Revisit | Ready (ms) | Script | Style | Layout | Paint |
| --- | ---: | ---: | ---: | ---: | ---: |
| README.md | 42.6 | 5.9 | 2.5 | 10.4 | 14.4 |
| design-system.md | 130.8 | 8.7 | 3.6 | 67.9 | 18.3 |
| app.js | 181.8 | 103.0 | 1.2 | 114.2 | 12.6 |

- **Markdown is laid out twice.** KPress’s table-of-contents wiring reads `scrollTop`
  while the document is still in the stage (`rendered.js:231`), forcing a 33 ms layout
  on design-system.md.
  Then `preview.replaceChildren(...)` (`app.js:6066`) re-parents the nodes, which
  discards that layout, and the next frame lays it out again for another 33 ms.
- **Large source is laid out twice and highlighted in one task.** For app.js: 47 ms of
  layout for plain text, a 103 ms `highlightCode` task (`app.js:397-459`), then 72 ms of
  layout. Color arrives about 300 ms after the click.
- **Style is cheap.** Recalculation took 10.6 ms for 5,587 elements; the 220 KB
  stylesheet does not need attention for transition speed.
- **Prefetch can collide with a swap.** The subtree sweep reads `getBoundingClientRect`
  (`app.js:2283`, `2328`) in an idle callback that can land between the swap and the
  frame, forcing a 13 ms layout.

### Layout Shift

Most movement comes from chrome that appears and disappears, not from content.

| Shift | Size | Cause | Fix |
| --- | --- | --- | --- |
| Tree pane on every main-tab switch | 37 px | `#nav-filter-bar` hidden on Commits and Pulls (`main-tabs.js:265`) | Keep the bar’s slot on every tab, or give each tab its own row in it |
| Content start between files | 30 px | The view tab bar renders only when a kind has more than one view (`app.js:5928`) | Always render the bar, or reserve its height |
| Pane width | 11 px | Classic scrollbars (`styles.css:1270`) on an `overflow-y: auto` pane with no gutter | `scrollbar-gutter: stable` on the preview and tree panes |
| Header label on a view switch | 32 px | The print button toggles `hidden` (`app.js:5675`, `5912`) | Hide it with `visibility` so its slot stays |
| PR tab bar on every PR tab switch | 8 px | The status row is 18 px on two tabs and 26 px on Changes | Give the row a fixed minimum height |
| First document after a cold load | 21–23 px, CLS 0.003 | PT Serif loads late; only Source Sans is preloaded (`server.py:1776-1789`) | Preload the prose faces, or await `document.fonts.load` before the swap |
| Tree rows during disclosure | 43–131 px per frame | `.tree-children` animates height with `interpolate-size` (`styles.css:2717-2724`), also on programmatic reveals | Never animate a reveal the user did not click |
| Pulls list after selecting a PR | 86 px, 0.12 without input | The old PR’s file list collapses about 2 s after the new row expands | Collapse and expand in the same frame |
| PR Changes first paint | up to 548 px, 0.47 | Diff sections grow as rendered diffs arrive after first paint | Hold first paint for in-flight diffs, or reserve heights |
| Palette results | rows replaced at about 110 ms | Pull request results interleave with file results when they arrive | Give the PR group a fixed position |
| Main tab bar on load | 78 px | The Commits button is inserted after Git discovery (`main-tabs.js:101`) | Render it in the shell when the root is a repository |

### Background Work Competes With Transitions

Every page load starts a walk through the pull request list: 90 requests to
`/api/plugin/github/` over 47 s (`pulls?state=all&limit=8&after=N` and
`pull-cores-prepare`, about 115 per minute) with no input.
It causes no long tasks, but it interleaves with every transition’s requests and
restarts on each load.

### The Cold Landing Is a Deep Chain of Round Trips

A cold landing on a Markdown file is about 23 dependent request levels, and the request
for the content itself is level 13. Each level waits on the one before it:

| Level | What starts | Why it waits |
| --- | --- | --- |
| 1 | Shell HTML |  |
| 2 | 20 scripts, 2 stylesheets, 1 font | Tags in the shell (`server.py:1791-1953`) |
| 3 | `/api/tree` | After `DOMContentLoaded` |
| 4 | `/api/file` and the view compositor | Navigation starts after `await loadTree()` (`app.js:8374-8378`), deliberately, so a folder renderer cannot delay the first tree rows |
| 5–9 | The Markdown plugin’s 15 modules | Only the entry module is preloaded (`plugin-sdk.js:299`); imports are discovered level by level |
| 10–12 | The Markdown worker and its imports | The view creates its worker client on mount |
| 13 | `POST /api/kpress/render` | The content |
| 14–23 | KPress CSS, then KPress scripts | Loaded one at a time with `await` in a loop (`plugin-sdk.js:1133-1158`) |
| late | PT Serif faces | Found only after the CSS applies |

Separately, the 14 `shell-tools` scripts (search, keyboard shortcuts, the Commits tab)
load strictly one after another because `ensureAsset` chains them with promises
(`asset-loader.js:168-183`), although `async = false` already orders execution.

Parse and evaluate are not the problem.
All 40 classic scripts (1.23 MB) parse in about 9 ms in both JavaScriptCore and V8, and
a cold landing has no task over 50 ms.
What costs time is the depth of the chain.
Concatenating the startup scripts, preloading the kind’s module graph, KPress styles,
and fonts after the startup scripts, and long `max-age` headers, applied together
through a rewriting proxy, made the cold landing 1.60x faster (357 to 223 ms median, n=8
interleaved pairs, every pair at least 1.37x) and reload 1.67x faster in Chrome.
No single ingredient cleared the 1.3x tolerance alone, and preload hints placed *before*
the startup scripts made first paint slower (92 to 120 ms) by competing for the six
connections.

### Every Load Revalidates Its Assets

| Route class | Cache-Control | Effect |
| --- | --- | --- |
| `/static/*?v=` (content-stamped) | none | Fresh only by the Last-Modified heuristic, 10% of the file’s age |
| `/plugin-static/*` | `no-cache` | Revalidated on every use; URLs carry no content stamp |
| `/kpress-static/*` CSS and JS | `no-cache` | Revalidated; URL keyed by KPress version, not content |
| `/kpress-static/*` fonts | `immutable`, one year | Already right |
| `/api/kpress/render` | `no-cache`, no validator | A POST in practice, so HTTP caching does not apply |
| `/raw` | none | Conditional requests get a full 200 (`FileResponse`, `server.py:3779`) |

In `WKWebView`, a relaunch on the same port made 59 requests while the heuristic held
and 100 requests (84 of them conditional) fourteen minutes later.
With `max-age` on the same URLs it made 17. Headers alone are worth only about 1.2x on a
reload over loopback, inside tolerance; their larger value is that anything preloaded or
prefetched stays warm across reloads and relaunches.

`WKWebView`’s disk cache is keyed by host and port.
The same warm data store made 17 requests on its own port and 103 (a full cold load) on
another port, or on `localhost` instead of `127.0.0.1`. In the app, a stable origin per
root is a performance requirement.

### Server Costs on the Click Path

Warm data routes are fast: `/api/file` 1.1 ms, `/api/tree` 4–11 ms, catalog and rollup
under 2 ms (server p50, n=10). The slow ones are the ones a click waits on:

- **Git routes are recomputed every time.** `/api/git/log?limit=250` takes 177 ms and
  `/api/git/summary` 186 ms for a 67-byte answer, because each spawns several git
  processes at 14–23 ms apiece and nothing is memoized.
- **Cold KPress renders** take 50 ms at the median and over a second at the worst (a 320
  KB report), about 1.4 ms per source KB. Warm renders are 4–10 ms.
  The server cache holds 64 entries in memory and is lost on restart.
- **Compression runs on the event loop for a loopback client.** gzip level 6 runs at
  about 33 MB/s, so a cold landing’s 3.1 MB costs about 93 ms of event-loop time that
  `Server-Timing` does not report, because it is taken at response start
  (`server.py:1069-1083`).
- **Background work has no lane.** With five background connections busy, a 1.7 ms
  foreground request took 23 to 46 ms at the median (13 to 26x). An uncapped prefetcher
  would produce exactly this.

### WebKit and the Native Shell

Measured in a real `WKWebView` on macOS 26.5.2 through a small Swift harness:

| Capability | In the app’s WebKit | Consequence |
| --- | --- | --- |
| `requestIdleCallback` | absent | Five idle prefetch sites fall back to fixed 200 ms timers; the comment at `server.py:1337` says it exists from Safari 18.2 |
| `scheduler.postTask`, `scheduler.yield` | absent | Yielding needs a `MessageChannel` or timer shim |
| `longtask`, `long-animation-frame`, `layout-shift` observers | absent | The budget file’s required `longtask` observer cannot pass; layout shift must be measured by region movement, not the Layout Instability API |
| `event`, `largest-contentful-paint`, `paint`, `resource` | present | Interaction and paint timing work |
| `rel=modulepreload`, `rel=preload`, `fetchpriority` | supported | Available to collapse the chain |
| `rel=prefetch` | no request sent | Do not rely on it |
| `content-visibility`, same-document View Transitions | present | Retained-surface techniques work |
| `Priority` request header | sent on every request (`u=5` for `fetch(…, {priority: "low"})`) | A server-side priority lane needs no new protocol |
| Protocol and encodings | HTTP/1.1, six connections, `gzip, deflate` only | `/api/events` permanently holds one of the six |

Native-shell experiments:

- **Prewarming the WebContent process** with a blank load at launch saved about 160 ms
  of the first real load (n=4 pairs, 1.42–1.63x). The first `WKWebView` construction
  takes 80–91 ms and its first load 164–177 ms.
- **Loading the shell in a hidden web view** fetched everything and mounted the first
  view, and showing it then reached ready in 56–68 ms (n=3). But while hidden the
  preview never leaves `preview-navigation-pending`, because hidden web views get about
  one animation frame per second and readiness waits on frames.
- **A `WKURLSchemeHandler` forwarder** to the loopback server works but gains nothing:
  it loses the disk cache, `document.cookie` (the theme, font, and width preferences),
  and Resource Timing.
- **The spike reveals the page on commit**, not on ready, so the reader watches the
  landing chain.

## Key Insights

- **The data is fast; the rebuilding is slow.** Warm data routes answer in 1 to 5 ms.
  What the reader waits for is serial chains and DOM rebuilt from scratch.
  A render-payload cache alone saved 7 to 16 ms, while keeping a laid-out surface made a
  revisit about 1 ms. Instant switching comes from keeping layout, not only data.
- **The staged render already prevents blank frames between files.** Every blank frame
  measured came from the main tabs’ cancel-and-restore design, which discards the
  surface the reader just left.
- **Most layout shift is self-inflicted chrome.** Filter bar, view tab bar, scrollbar
  gutter, print button, status rows, and a late tab button account for most movement,
  and each fix is a CSS or markup change.
- **The app’s engine cannot see some of what the gates measure.** WebKit has no
  `requestIdleCallback`, Long Tasks, Long Animation Frames, or Layout Instability API.
  Prefetch timing falls back to clocks, the current budget file cannot run in the app,
  and shift has to be measured as region movement, which works in both engines.
- **In the app, the origin is part of the cache key.** A port that changes between
  launches turns every relaunch into a cold load.
- **Prefetching needs admission control before it needs more prefetch.** Background
  requests already inflate foreground latency 13 to 26x when uncapped.
  A cap of one or two background requests and a low-priority lane come first.
- **Memory decides how much to retain laid out.** A laid-out hidden surface costs about
  ten times a detached one (7.7 MB against 0.64 MB for design-system.md), and each web
  view already costs 155 to 210 MB. Keep a few surfaces laid out and many detached,
  budgeted by DOM nodes, not by count.

## Options Considered

### Retention Strategies

| Option | What it keeps | Revisit cost | Memory | Contract change |
| --- | --- | --- | --- | --- |
| Rebuild (today) | Envelope JSON | 39–159 ms, 1–3 requests | Lowest | None |
| Payload cache | Envelope and render JSON | 7–16 ms less, 0 requests | About 7 MB for 30 renders | None |
| Detached LRU | DOM nodes, not layout | 6–37 ms (106 ms for 313 KB source) | About 19 MB for 30 large documents | Views must suspend and resume |
| Laid out, hidden | DOM and layout | 0.8–29 ms | About 10x detached | Views must tolerate being hidden |

The recommendation combines them: laid-out hidden surfaces for each main tab’s current
subject and the recent views of the open file, a detached LRU for recently viewed files,
and a payload cache underneath as the prefetch target.

### Eliminated Options

- **View Transitions as a fix:** file-to-file already has zero blank frames, and the
  main-tab blanks come from destroying the surface, which a transition would only
  animate. It may be worth a short cross-fade after retention lands.
- **A `WKURLSchemeHandler` for assets:** measured no faster as a forwarder, and it loses
  the disk cache, cookies, and Resource Timing.
  Serving from the app bundle would also split the one-artifact contract between server
  and shell.
- **Bytecode caching or splitting `styles.css`:** parse is 9 ms for all scripts and 2.5
  ms for the stylesheet; style recalculation is 10.6 ms for 5,587 elements.
- **`rel=prefetch`:** WebKit sends no request for it.
- **Pointer-trajectory prediction:** hover intent plus pointer-down already covers the
  last few hundred milliseconds, and mis-predictions would spend a one-request budget.

## Recommendations

Ranked by payoff per unit of effort.
Effort: **S** is a contained change of about a day, **M** touches a contract or several
modules, **L** changes an ownership model.
Payoff is apparent speed or stability, tied to the measurement behind it.

### Ranked Improvements

| # | Improvement | Effort | Payoff | Evidence | Depends on |
| --- | --- | --- | --- | --- | --- |
| 1 | **Reserve space for chrome that toggles:** keep the filter bar’s slot on every main tab, always render the view tab bar, `scrollbar-gutter: stable`, hide the print button with `visibility`, a fixed-height PR status row, the Commits button in the shell | S | High (stability) | Removes 37, 30, 11, 32, 8, and 78 px moves seen on most transitions | None |
| 2 | **Stable origin in the app:** sticky port per root, one host spelling, persistent data store | S | High on relaunch | 103 requests to 17 | Native shell |
| 3 | **Caching headers:** `immutable` for stamped `/static`, a content-keyed path prefix for plugin and KPress assets, stamped `/raw` | S–M | Medium alone; needed by 2, 11, 12 | 33–84 revalidations per load to 0–1 | None |
| 4 | **Git: cache comparisons by commit ID in the browser, memoize git routes on a refs fingerprint** | S | High in Commits | Commit revisit 125–222 ms toward about 11 ms; `log` and `summary` 177 and 186 ms to about 1 ms on repeat | None |
| 5 | **Parallelize the serial loaders:** `shell-tools` fetches and KPress CSS and scripts | S | Medium | 14 serial round trips to one level; part of the 1.6x landing result | None |
| 6 | **Render payload cache keyed by path, ETag, and options, and one long-lived Markdown worker** | S | Medium; enables 8 | Revisits become request-free, ending 19–190 KB uploads per view | None |
| 7 | **Small shift and smoothness fixes:** preload the prose fonts, never animate programmatic tree reveals, coalesce held arrow keys, fixed palette group order | S | Medium | CLS 0.003 on first document; 0.046 without input on a deep reveal; 14 requests for a 6-key skim | None |
| 8 | **One prepare unit per subject, fed by prediction:** envelope, render, and assets warmed on keyboard focus and the next row, pointer-down, and hover; Commits and Pulls data warmed after first view | M | High | Cold neighbor 41–84 ms toward revisit cost; takes 124–292 ms cold renders and 439–666 ms first Commits off the click | 6, 10; an addressable render GET for hover prefetch |
| 9 | **Per-main-tab retained surfaces:** each of Files, Commits, and Pulls keeps its own laid-out surface; a switch suspends instead of claiming the pane | L | High | Main-tab switch from 28–327 ms with up to 5 blank frames to one frame, 0 requests | 1 |
| 10 | **Admission control:** at most two background requests, `priority: "low"`, server holds low-priority work while foreground is in flight | M | Enabling | Uncapped background inflates foreground 13–26x | None |
| 11 | **Collapse the landing chain:** concatenate startup scripts in the server, preload the kind’s module graph after the startup scripts, request content early; re-measure the tree-first order | M | High | 1.60–1.71x cold, 1.61–1.67x reload | 3, 5 |
| 12 | **App launch:** prewarm a web view at launch, load the shell hidden, reveal on ready, keep one spare; make first-view readiness independent of visibility | S–M | High at launch and window open | 160 ms from prewarm; show-to-ready 56–68 ms | 2, 11 |
| 13 | **Pull request page:** join the click to the mousedown peek, collapse and expand list rows in one frame, hold Changes’ first paint for diffs in flight | S–M | High on PR pages (stability) | Removes the two largest shifts measured (0.47 and 0.12) and 1–3 duplicate reads per click | None |
| 14 | **Detached LRU of file surfaces** with a suspend and resume view contract, budgeted by DOM nodes | L | High | Revisits, Back, and backtracking from 39–159 ms to 6–37 ms, 0 requests | 6, view contract |
| 15 | **Keep hidden view tabs laid out** (`content-visibility: hidden`, bounded) and chunk long source with `content-visibility: auto` | M | High for heavy files | Heavy view revisit from 232–877 ms to a few ms; the chunking half is inferred | None |
| 16 | **One layout per Markdown mount:** defer the table of contents’ scroll read until after the swap, or commit without re-parenting | S–M | Medium | 23–33 ms of 131–150 ms on a 156 KB document | Composes with 9 and 14 |
| 17 | **Highlight in a worker** | M | Medium | Removes a 24–103 ms task per large source file | None |
| 18 | **Persistent render cache:** disk cache keyed by source digest, KPress version, and options; retained encoded bodies | M | Medium | Cold 50–1,108 ms to 4–10 ms after a restart | None |
| 19 | **No compression for the app’s own loopback client** | S | Low–medium | About 93 ms of event-loop time per cold landing | None |
| 20 | **Pulls walk in bulk** when its steps are cache reads | S | Low–medium | 90 requests over 47 s after every load | None |
| 21 | **Pre-mount non-default view tabs at idle** | S–M | Low alone | First visits are already 18–46 ms for ordinary files | 15 |
| 22 | **Persisted first-rows snapshot, then index**, for restored windows | L | Not measured |  | Native topology phases |

### Measurement Work That Gates the Rest

These do not make anything faster, but every row above needs them to be measured in the
app’s engine and kept:

- **A WebKit-aware recorder:** an idle shim that waits for the first view and pauses on
  input, a frame-gap detector in place of Long Tasks, and region-movement shift
  measurement, so `perf.js` and the budgets run in `WKWebView` (the
  [native app plan](../specs/active/plan-2026-11-10-native-macos-app.md)’s WebKit
  measurement gate). Correct the comment at `server.py:1337`.

- **`Server-Timing` through the end of the body,** with named spans (`git`, `render`,
  `read`, `encode`).

- **New budgets** in `explorations/performance-loop/performance-budgets.toml`, all per
  transition with trusted input:

| Metric | Target | Today |
| --- | --- | --- |
| Blank preview frames, file to file | 0 (gate) | 0 in 84 of 84 |
| Blank preview frames, main-tab switch | 0 | 1–5; 19–65 on first Commits |
| Reserved-region movement | 0 px | 37, 30, 11, 32, 8 px |
| Shift without input | 0 | 0.003–0.12 |
| Requests on a revisit of an unchanged subject | 0 | 1–4 |
| Duplicate requests for the selected subject | 0 | 1–3 per PR click |
| Revisit and main-tab switch, painted ready | 50 ms | 39–327 ms |
| Revalidations on a reload | 1 | 33–84 |
| Content request level on a cold landing | 3 | 13 |
| Background requests in flight | 2 (gate) | uncapped |
| Background requests per minute after settle | 6 | about 115 |

### Suggested Order

1. **Quick wins (items 1–7):** independent and small; together they remove most visible
   movement, every revalidation, and the slowest Commits waits.
2. **The instant core (items 8–12):** retained main-tab surfaces, full-chain prefetch
   behind admission control, the collapsed landing chain, and app prewarming.
   This is where tab switches become one frame.
3. **Deeper retention (items 13–18):** the detached LRU and its view contract,
   heavy-view retention, and render and highlight costs.

Land the WebKit-aware recorder and the first budgets alongside the quick wins, so each
later change is measured in `WKWebView` as well as Chrome.

## Next Steps

- [x] Review the ranking and the suggested order
- [x] File beads for the accepted items, grouped by the three phases: epic `mb-mpo0`,
  planned in
  [instant transitions and stable layout](../specs/active/plan-2026-11-11-ui-apparent-performance.md),
  with hypotheses H86–H105 in
  [the load-time plan](../specs/active/plan-2026-08-21-load-time-performance.md#apparent-speed-and-layout-stability)
- [ ] Add a stateful-navigation scenario to `explorations/performance-loop` that records
  the counts above (blank frames, region movement, revisit requests) in Chrome and in a
  `WKWebView` harness (`mb-4z4u`)

## Methodology

- **Corpus and build:** this repository (about 9,170 indexed files, 265 Markdown files,
  a GitHub checkout with 340 pull requests) served by `main` at `7a02fed4`.
- **Chrome:** headless Chrome 152 over the DevTools Protocol, 1440×900, a fresh profile
  per journey, trusted pointer and keyboard input.
  Painted ready is the frame after the first frame showing the requested subject with
  useful content. An early version of the probe forced layout inside
  `requestAnimationFrame` and inflated times by 30 to 50 ms; all tables use the
  corrected probe.
- **WebKit:** a real `WKWebView` on macOS 26.5.2 driven by a Swift harness, with request
  counts taken from a logging reverse proxy that also applied the experimental header
  and markup rewrites, so no product code was changed.
  The display slept partway through, so visible-window `WKWebView` timings are n=2–3;
  later runs report request counts and a visibility-independent mounted milestone.
- **Load and tolerance:** the machine ran at load average 7 to 39. Counts are
  deterministic and were identical across passes; time comparisons use interleaved pairs
  judged against the 1.3x rough-cut tolerance.
- **Not measured:** WebKit timing of most transitions, memory in `WKWebView`, the
  back-forward cache, large patch files, agent-log charts, images, and any corpus other
  than this repository.
  The `content-visibility: auto` chunking, worker highlighting, and View Transitions
  recommendations are reasoned from measured costs, not prototyped.
- The probe scripts are ad hoc and not committed; the scenario in Next Steps replaces
  them.

## References

- [Design system](../../design-system.md), principle 6 and Motion
- [Web performance framework](../../web-performance-framework.md), stateful navigation
- [Rendering large content](../../large-content-rendering.md)
- [Asset loading tiers](../../development.md#asset-loading-tiers)
- [State and delivery](../architecture/arch-state-and-delivery.md)
- [Native app server topology](research-2026-11-10-native-app-server-topology.md)
- [macOS app packaging](research-2026-11-08-macos-app-packaging.md)
- [Native macOS app plan](../specs/active/plan-2026-11-10-native-macos-app.md)

Platform facts cited rather than measured:

- [WebKit features in Safari 26.2](https://webkit.org/blog/17640/webkit-features-for-safari-26-2/)
  (official): Event Timing and Largest Contentful Paint
- [WebKit bug 285049](https://bugs.webkit.org/show_bug.cgi?id=285049) (issue tracker):
  `requestIdleCallback` enabled and backed out
- [WebKit bug 194047](https://bugs.webkit.org/show_bug.cgi?id=194047) (issue tracker):
  no on-disk bytecode cache for web content
- [`WKProcessPool`](https://developer.apple.com/documentation/webkit/wkprocesspool)
  (official): deprecated, process sharing is automatic
- [Enabling inspection of web content in apps](https://webkit.org/blog/13936/enabling-the-inspection-of-web-content-in-apps/)
  (official): `isInspectable`

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
