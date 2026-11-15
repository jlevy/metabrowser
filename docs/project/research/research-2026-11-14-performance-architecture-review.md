# Research: An Architecture Review of the Performance Design

**Date:** 2026-11-14

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Complete

## Overview

[exp-079](../../../explorations/performance-loop/experiments/exp-079-every-accepted-change-at-final-main.md)
closed Phase 1 of the November 11 campaign.
Nothing it measured moves during a transition any more, warm data routes answer in about
a millisecond, and inventory delivery is progressive.
The rows still open in
[the load-time registry](../specs/active/plan-2026-08-21-load-time-performance.md#hypotheses)
were nearly all registered as tuning: a cap, a cache, a preload, a faster walk.

This review asked a different question: is the design built for the best performance it
can reach, or do some of its divisions charge a fixed cost to every transition or window
open, whatever is tuned around them?
It found four such divisions, and a fifth cost that follows from them:

1. **The preview pane has one owner and rebuilds on every show.** Nothing rendered is
   kept.
2. **Text is rendered by a second request the client drives** after the data arrives,
   and every hold and half the landing chain wait on it.
3. **The server repeats identical work per request:** gzip toward a loopback client,
   immutable assets re-read and re-compressed, four Git processes per comparison.
4. **A folder is a process and an origin,** so opening one pays the interpreter’s
   imports and a document load.
5. The landing starts late, after the first tree request, though the shell already knows
   its path.

Seven changes remove these costs, and they subsume, supersede, or demote about a dozen
registered rows. They are registered as H112 to H118 in
[Structural Costs](../specs/active/plan-2026-08-21-load-time-performance.md#structural-costs),
with six readings, U1 to U6, that come first because their answers reorder the work.
[The campaign plan](../specs/active/plan-2026-11-14-performance-campaigns.md) holds the
order.

## Questions to Answer

1. Which divisions of work between the shell, the server, and the client force a cost on
   every transition or window open, rather than on some?
2. What would remove each one, and which registered rows does that subsume?
3. Which uncertainties should be measured before anyone builds?
4. Which registered rows does the answer retire, merge, or demote?

## Scope

**In scope:** the browser shell, the built-in plugins, and the server on `main` at
`4fe109b9`, with the registry as of `d981c77f`; every committed experiment record and
research table; six untimed probes the reviewer ran (in [Methodology](#methodology)).
The code references below were re-checked against `main` at `4f79b47c`, and name
functions rather than line numbers, because `app.js` moves with nearly every merge.

**Out of scope:** any timed round, any reading in `WKWebView`, and any probe of a pull
request route. Nothing here is a verdict under
[the accept rule](../../../explorations/performance-loop/README.md#the-accept-rule).

## Findings

Each finding separates three kinds of evidence:

- **Recorded:** a committed experiment record or research table, cited by name.
- **Probed:** a reading the reviewer took on a loaded host, by a command in
  [Methodology](#methodology).
  A probe reading is an order of magnitude, not a result.
- **Inferred:** a reading of the source, or a prediction no instrument has taken.

### One Pane, Rebuilt on Every Show

The preview pane has one owner.
A render is staged off screen and committed by moving the stage’s nodes into the pane
(`preview.replaceChildren(...)` in `app.js`). A main-tab switch cancels the preview
(`deps.cancelPreview()` in `main-tabs.js`), and the pull request page replaces its body
for each tab (`body.replaceChildren(host, loading)` in `pull-page.js`). So a return to
anything rebuilds it.

- **Recorded.** At final `main`, a revisit costs about what a cold view does: large
  Markdown 145.8 ms on a revisit against 180.8 ms cold (exp-079). A return to a main tab
  is ready in 63 to 112 ms and makes up to 13 data requests
  (`main_subject.commits_to_pulls`, exp-079), and a Changes revisit 79 to 96 ms.
  The UI research measured the alternative: a laid-out surface of a few thousand
  elements shows again in 0.8 to 6 ms, and a Markdown mount is laid out twice, 33 ms
  each on a 156 KB document
  ([apparent UI performance](research-2026-11-11-ui-apparent-performance.md)).
- **Inferred.** If each subject rendered into its own host, shown in place and kept, a
  return would be a visibility change.
  That removes the re-parenting commit, the one-page handoff (`finishRetainedPullPage()`
  in `app.js`), and four separately reserved rounds (H95, H98, H99 (a), H105) plus
  H100’s second layout.
- **Registered as** H112, one surface store.

### Rendering Is a Second Request the Client Drives

A Markdown view runs the worker’s wiki preparation and then asks KPress for the render,
uploading the whole prepared source when preparation changed it (`rendered.js`, through
`mb.fetchKpressRender`). Preparation changes nearly every document: its trigger
(`hasPreprocessingTrigger` in `wiki-parser.js`) fires on any `[`, `#`, `^`, `=` or `-`,
and the heading pass adds an anchor to every heading.
A pull request page asks for each text’s render separately, at most two at a time
(`MARKDOWN_ROUTE` and `MARKDOWN_CONCURRENCY` in `pull-page.js`).

- **Recorded.**
  - A Markdown view uploads 19 to 191 KB of source and, after any other kind of view,
    fetches three worker modules again (exp-063).
  - The content request is level 13 of the landing’s 23 dependent request levels
    (apparent UI research).
  - The pull request holds wait 25 to 151 ms for the first paint and 31 to 74 ms for
    Changes (exp-065). At final `main` they cost a pull request click 16 to 58 ms
    (exp-079).
- **Inferred.** The answer that carries a text could carry its render.
  `GET /api/kpress/render` is already served (`api_kpress_render` in `server.py`), but
  it answers `cache-control: no-cache` with no validator, so the HTTP cache cannot
  answer a revisit.
- **Registered as** H113, Markdown render by GET, and H114, a pull request’s first
  screen in one answer.

### The Server Repeats Identical Work per Request

Every compressible answer is gzipped at level 6 on the event loop (`TimedGZipMiddleware`
in `server.py`), toward a loopback client that does not need it.
A commit comparison runs four Git processes in sequence (`GitDiffSource` in
`diff/adapters/git.py`: two `rev-parse` runs in `resolve`, a listing in `manifest`, and
the patch), and a folder keeps none of them (`comparison_cache.py` keeps answers “for a
store, and nothing for a folder”).

- **Recorded.** Five saturated background connections inflate a cheap foreground request
  3.3 to 26x; the worst, 13 to 26x, were Git routes, tree prefetches, and warm renders
  (apparent UI research).
- **Probed.**
  - gzip is 12.3 ms of the 14.8 ms a warm 311 KB render answer takes.
  - The landing’s 41 startup assets, requested one at a time, take 98 to 106 ms of
    server time with gzip and 44 to 66 ms without.
  - `git;dur` per comparison is 82 to 118 ms, the same on a repeat.
    One Git process costs 16.6 ms to start; the four take 80 to 98 ms, and one
    `git diff --patch-with-raw --numstat` takes 20 to 39 ms for the same answer.
- **Inferred.** Encode once or not at all, and answer a comparison with one process.
- **Registered as** H115, encode once or not at all (widening H103), and H116, one Git
  process per comparison.

### A Folder Is a Process and an Origin

Opening a folder spawns a server, which imports the program before it can bind, and the
shell is a new document on a new origin.

- **Recorded.** Spawn to the first answer is 503 to 513 ms (exp-037’s addendum) and 0.77
  s to the first `/view/` page
  ([native app server topology](research-2026-11-10-native-app-server-topology.md)). A
  first `WKWebView` load takes 164 to 177 ms, and a cold landing 273 to 290 ms at the
  control and at final `main` (apparent UI research, exp-079).
- **Probed.** `import metabrowser.server` is 0.41 to 0.45 s of that with bytecode and
  0.92 s without. It imports 592 modules, and the largest self time is about 20 ms
  (`metabrowser.inventory_engine.contract`), so no single import is worth cutting.
- **Inferred.** The program can be resident before the folder is chosen.
- **Registered as** H117, a resident server and shell.

### The Landing Starts Late

Navigation starts after `DOMContentLoaded` and the first tree request (the tree-first
order: `await loadTree()` before `navigationController.start()` in `app.js`), though the
server already knows the path it is rendering (`index(view_path=…)` in `server.py`).

- **Recorded.** A rewriting proxy that started content early made the cold landing on
  `README.md` 1.60x faster, 357 to 223 ms (apparent UI research).
- **Probed.** The shell answer is 16 ms of server time.
- **Registered as** H118, landing data starts with the document, amending H96.

## Key Insights

- **The design is sound where earlier rounds attacked it.** Delivery is progressive,
  warm routes are fast, and nothing moves.
  What remains is fixed costs at boundaries, which tuning cannot remove.
- **Most open rows tune around a boundary instead of removing it.** A render cache (H90)
  helps a revisit that a kept surface (H112) would not need; a preload cap (H109)
  shortens a chain that starting the content with the document (H118) removes.
- **The server is on the critical path more than the registry assumed.** Its one thread
  spends time on gzip and Git process starts that the client then waits for.
  U2 tests whether it bounds the cold landing.
- **Walker costs are CPython’s.** The
  [Python inventory cost](../architecture/arch-python-inventory-cost.md) numbers “do not
  carry to another engine”, so tuning the Python walk is worth less until U3 says
  whether the fdu provider replaces it.

## Options Considered

### The Seven Changes

| Review | Row | Change | What it subsumes |
| --- | --- | --- | --- |
| R1 | H112 | One surface store: each subject renders into its own kept host | H95, H98, H99 (a), H100, H105, and H108’s Changes half |
| R2 | H113 | Markdown render by `GET`, heading anchors from the rendered headings | H90’s cache; H90’s code at `6b876c54` is its fallback |
| R3 | H114 | A pull request’s first screen in one answer | H108’s description half |
| R4 | H115 | Encode once, or not at all | H103, widened |
| R5 | H116 | One Git process per comparison | Nothing; new |
| R6 | H117 | A resident server and shell | The core half of `mb-bbod` and `mb-25nv` |
| R7 | H118 | Landing data starts with the document | H96, amended |

Every predicted size in those rows, beyond a cited record or probe, is an inference.

### Eliminated Options

- **A shared multi-root process.** The server reads its one root through single-root
  accessors throughout; the review counted 42 uses in 10 files, a count not re-derived
  here. A resident server that adopts one root (H117) gets the saving without that
  rewrite.
- **HTTP/2.** Browsers speak it only over TLS, and the wait it would remove is server
  work, not connections.
- **A server-rendered or stored first-screen DOM.** It needs a second renderer, and H118
  shortens the chain without one.
- **A client-side tree replica (H42).** The shell document comes from the same process a
  relaunch waits for, so a replica cannot paint before it.
  A restored window’s snapshot is native work.

## Recommendations

### Readings First

These are measurements, not hypotheses, and take no H number:

| # | Question | Cheapest reading | What it reorders | Bead |
| --- | --- | --- | --- | --- |
| U1 | What a kept surface costs in WebKit, which lays out 1.1 to 5 times slower than Chrome ([rendering large content](../../large-content-rendering.md)) | `wkprobe-steps.mjs`: a toggle against a re-attach on three surfaces, and the footprint per surface | H112’s tiers, and whether a detached tier is worth having | `mb-r303` |
| U2 | Whether the server’s one thread bounds the cold landing | Server-Timing summed to the end of each body over one landing per build | If it does by over half, H109 and H110 retire and H115 (a) goes first | `mb-cejc` |
| U3 | The fdu provider against the Python provider | One paired run: walk to settled, footprint, foreground latency during the walk | The whole scan-and-walker loop, and H21 | `mb-wb7e` |
| U4 | How k pages on one origin share connections, when each holds one of six for `/api/events` (`startInventoryEventStream()` in `app.js`) | `explorations/page-connections/measure.mjs` with k live tabs, then k web views | A parked or shared stream before native tabs | `mb-7nm6` |
| U5 | The app’s frame rate: WebKit drew 30 frames a second in Low Power Mode (rendering large content) | `wkprobe.mjs` frame gaps | States the 50 ms goal in frames | `mb-ttfq` |
| U6 | Whether highlight.js can continue a lexer state | A twenty-line check | If it can, highlight the visible lines first and the rest at idle, in place of H101’s worker | `mb-xws3` |

### Retire, Merge, Demote

- **H90:** not re-tested a fourth time.
  Its deciding metrics were met and it failed only on one-frame flags (exp-086). H112
  takes its revisits and H113 its request-free render.
- **Merged:** H95, H98, H99 (a), H100 and H105 into H112; H103 into H115; H96 into H118.
  H108 is re-scoped: H114 takes its description half and H112 (d) its Changes half.
  H102 runs after H113, keyed by source digest.
- **Behind U2:** H109 and H110. exp-062’s numbers fit a serial server queue: shell tools
  61 ms sooner, KPress 40 ms later, the total unchanged.
- **Split:** H93 into (a) a client cap that pauses on input, and (b) a server lane only
  if (a) leaves foreground p95 above 1.3x its quiet latency.
  H115 and H116 cheapen the two inflators the research measured.
- **After H112:** H94, which fills its hosts.
- **After U6:** H101 and H99 (b), as one row.
- **Retired:** H42, for the reason under [Eliminated Options](#eliminated-options).
- **Waiting on U3:** H21 and H46. **Demoted:** H18, H22, H72, H33, H43, H34, H47 and
  H39, whose costs are CPython’s.
- **Attribution only:** H17. The probe finds no single import worth cutting, and H117
  takes the cost off the click.

### Suggested Order

The review proposed this order; the campaign plan holds the one in force.

1. Lane 0 and Lane A, with three changes: read Lane A’s counts from single untimed runs
   per merge, spend timed pairs only on the skim’s last row and
   `main_subject.commits_to_pulls`, and declare exp-087’s later-frame test in every
   revision-6 protocol.
   Add U2.
2. H115 and H116 beside Lane 0. Server-side instruments decide them, they run on
   revision 5, and they make every later background request cheaper.
3. Lane C as H112, ahead of Lane B. It moves the most rows per timed series, and
   prediction has nothing to win until a return is cheap.
4. H114, then Lane D as one round, H113 with H118.
5. Loop 1 as H117’s core half, then H56’s counter and H14’s pair.
   Compile bytecode in the app’s install flow: the import is 0.92 s without it against
   about 0.43 s with it.
6. Lane B: H93 (a), H94, H104.
7. Lane W whenever the user is present: U1 and U5 first, then H97 and the WebKit halves
   of H112, H117 and H118.
8. Lane E after U6, with H102. Loops 2 and 3: U3 and H49’s adapters only.
   Loop 4 last.

The largest gains a reader of the app would see, in order: H117, up to a second per
folder opened; H112, every return; then H114 and H116, on pull request and commit
clicks.

## Next Steps

- [x] Register H112 to H118 and U1 to U6 in the load-time registry, and update the rows
  the review retires, merges, or demotes
- [x] File their beads
- [ ] Run U2 and Lane A’s attribution before the first H112 to H118 round
- [ ] Read U1 and U5 in the next session with the user present

## Methodology

The review was read-only, in a worktree at `4fe109b9`. Every probe ran untimed against a
host whose one-minute load was 7.6 to 36, so each reading is an order of magnitude and
not a result: no probe was paired, interleaved, or judged.

The probes are committed in
[architecture-probes](../../../explorations/performance-loop/architecture-probes/). Each
file is the script the review ran, reformatted and typed to pass the repository’s lint
and type checks with the same requests and commands; the committed versions have not
been run again.

All from the checkout root, with
`UVR="uv --config-file $PWD/uv.toml run --frozen --no-sync"` and
`P=explorations/performance-loop/architecture-probes`:

1. `$UVR python -X importtime -c "import metabrowser.server"`. With
   `PYTHONDONTWRITEBYTECODE=1`: 820 to 855 ms cumulative (n=3, after a first run of
   2,474 ms) and a wall time of 0.92 to 0.94 s (n=3). With it unset and
   `PYTHONPYCACHEPREFIX` pointed at a scratch directory: a wall time of 0.41 to 0.45 s
   (n=5), 315 to 316 ms cumulative (n=3); `python -c pass` took 0.03 s.
2. `$UVR python $P/gzip_probe.py "$PWD"`: gzip level 6 in process over the shell’s
   scripts, `styles.css`, the startup bundles, and the Markdown plugin, 61 files, 1,716
   to 484 KB, in 54.9 ms.
3. `$UVR metab CORPUS --no-open --port 8977 --cache-dir SCRATCH/cache --config-dir SCRATCH/config`,
   where `CORPUS` holds copies of `README.md`, `docs/development.md` and
   `docs/design-system.md`, then
   `$UVR python $P/static_probe.py 127.0.0.1 8977 /view/README.md`: the shell in 24.0 ms
   (`srv` 16.0); the 41 assets on one connection, three sweeps each way, as cited above;
   `/api/identity` in 0.37 ms and `/api/file` in 1.08 ms (n=40).
4. The same server, `$UVR python $P/render_probe.py 127.0.0.1 8977 CORPUS` (n=7 per
   cell), for `design-system.md` (211 KB): first render 219 ms; a warm `GET` in 3.8 ms
   identity and 14.8 ms gzip; a `POST` in 15.5 ms; `/api/file` in 14.6 ms.
5. `$UVR metab "$PWD"` with the same flags, then
   `$UVR python $P/commit_probe.py 127.0.0.1 PORT SHA...` on four recent commits: a
   comparison in 93.9 to 130.9 ms first and 90.2 to 124.8 ms on a repeat; commit detail
   in 28 to 126 ms.
6. `$UVR python $P/git_spawn_probe.py "$PWD" SHA...` on the same four commits (n=9
   each): `git --version` 16.6 ms; the two `rev-parse` runs, the listing, and the patch,
   summed, 79.5 to 97.6 ms; one `diff --patch-with-raw --numstat` 20.0 to 38.6 ms.

The probes’ raw outputs and server logs are not committed: they hold local paths.
Nothing was measured in `WKWebView`, and no pull request route was probed.

## References

- [The load-time registry](../specs/active/plan-2026-08-21-load-time-performance.md#structural-costs),
  rows H112 to H118
- [The campaign plan](../specs/active/plan-2026-11-14-performance-campaigns.md)
- [Apparent UI performance for the native app](research-2026-11-11-ui-apparent-performance.md)
- [Native app server topology](research-2026-11-10-native-app-server-topology.md)
- [Rendering large content](../../large-content-rendering.md)
- [Python inventory cost](../architecture/arch-python-inventory-cost.md)
- [exp-079, the Phase 1 closing round](../../../explorations/performance-loop/experiments/exp-079-every-accepted-change-at-final-main.md)
- [The performance-loop runbook](../../../explorations/performance-loop/README.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
