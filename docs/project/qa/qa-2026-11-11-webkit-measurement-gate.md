# QA: WebKit Measurement Gate, 2026-11-11

**Date:** 2026-11-11

**Status:** A dated record of one run of `make macos-webkit-gate`, which failed.
The source view’s largest cost has since had a core fix (#367, `mb-551q`); after it the
Load more row still measured 2.25 to 2.46 times Chrome and the first-click probe 2.45 to
2.51 times. The rerun is `mb-76nv`, and what follows from the failure is the owner’s
decision (`mb-gvtw`). An addendum records the treemap case’s runs on 2026-11-23
(`mb-72rg`): the first failed the family hover, and the rerun with palette keys kept a
layout passed every metric.
[Native macOS App Architecture](../architecture/arch-macos-app.md#webkit-differences)
describes what the app does differently in WebKit; the
[app’s README](../../../apps/macos/README.md) says how to run the gate.

## Method and Results

The [packaging brief](../research/research-2026-11-08-macos-app-packaging.md) keeps the
`WKWebView` shell only if WebKit holds the large-content bounds that
[rendering large content](../../large-content-rendering.md) sets in Chrome, within 1.3
times Chrome in every back-to-back pair on one machine.
`make macos-webkit-gate` runs `apps/macos/webkit-gate/run.mjs`, whose header lists its
cases: it serves both engines the same generated corpora and committed diff benchmark
pages from one `metab`, runs the in-page `probe.js` in the app’s own web view class and
in Chrome over the DevTools protocol at the same viewport and device pixel ratio, each
sample a fresh browser with an empty cache, and runs a warm-up pair and then five pairs
per case, alternating which engine goes first.
A metric passes when every pair does; a pair under 5 ms in both is reported, not judged,
since WebKit rounds `performance.now()` to 1 ms (`webkit-gate/summary.mjs`).

The run of 2026-11-11 was on an Apple M1 Pro MacBook Pro with 32 GB, macOS 26.5.2,
WebKit 21624.2.5.11.8 (Safari 26.5.2), Chrome 152.0.7977.83, `metab` 0.12.1.dev214 from
`8b0603f7`, and the harness at `1c028e84`, with a load average of 9 to 15, Low Power
Mode on, and the screen locked.
Times are medians of five pairs; a ratio is WebKit’s value over Chrome’s in one pair.

| Bound | Case and metric | Chrome | WebKit | Pair ratios | Verdict |
| --- | --- | ---: | ---: | --- | --- |
| `TEXT_PREVIEW_CHUNK_BYTES` | Source, 16 MiB file: open, response end to laid out | 337 ms | 564 ms | 1.58–1.72 | **fail** |
|  | Open, navigation to next frame | 952 ms | 1,362 ms | 1.31–1.45 | **fail** |
| `TEXT_PREVIEW_MAX_CHUNK_BYTES` | Load more to 4 MiB, response end to laid out | 419 ms | 2,383 ms | 5.63–5.83 | **fail** |
|  | Load more to 8 MiB | 803 ms | 4,004 ms | 4.84–5.06 | **fail** |
|  | Load more to 16 MiB (an 8 MiB click) | 1,664 ms | 7,848 ms | 4.50–4.88 | **fail** |
|  | The same click, to next frame | 2,662 ms | 8,256 ms | 3.05–3.20 | **fail** |
|  | Scrolling 16 MiB, frame work | 85–164 ms | 0–3 ms | 0.00–0.07 | pass |
| One 2 MiB line | Open, response end to laid out | 193 ms | 270 ms | 1.37–1.42 | **fail** |
|  | Open, navigation to next frame | 561 ms | 1,054 ms | 1.84–2.04 | **fail** |
| `SYNTAX_HIGHLIGHT_MAX_BYTES` | YAML, 512 KiB, 27,854 spans | 285 ms | 347 ms | 1.13–1.24 | pass |
|  | Markdown, 4,603 spans | 114 ms | 162 ms | 1.37–1.48 | **fail** |
|  | JSON, 20,307 spans | 212 ms | 251 ms | 1.15–1.22 | pass |
|  | Dense JSON, 307,591 spans | 1,371 ms | 1,699 ms | 1.19–1.25 | pass |
|  | TypeScript, 22,494 spans | 336 ms | 471 ms | 1.27–1.45 | **fail** |
| `BINARY_PREVIEW_CHUNK_BYTES` | Binary, 32 MiB file: open, response end to laid out | 220 ms | 424 ms | 1.86–1.99 | **fail** |
| `BINARY_PREVIEW_MAX_BYTES` | Six Load more clicks to 32 MiB, each response end to laid out | 100–419 ms | 159–960 ms | 1.39–2.46 | **fail** |
|  | Last click (8 MiB), to next frame | 775 ms | 1,335 ms | 1.66–1.77 | **fail** |
|  | Scrolling 32 MiB, frame work | 5.5–6.3 ms | 12–13 ms | 1.76–2.91 | **fail** |
|  | Renderer footprint, without graphics | 1,029 MiB | 238 MiB | 0.23–0.26 | pass |
| `LINES_PER_BLOCK` | Binary, 8 MiB loaded: scroll to the middle, frame work | 2.1 ms | 4.0 ms | 1.25–4.76 | **fail** |
| `DEFAULT_ACCENT_RUN_BUDGET` | Accented binary, 8 MiB, 247,322 elements: open | 88 ms | 197 ms | 2.15–2.36 | **fail** |
|  | Load more clicks, response end to laid out | 77–338 ms | 168–820 ms | 2.13–2.70 | **fail** |
| `LAYOUT_PROJECTION_BATCH_FILES` | Diff layout benchmark, 1,000 files: mount | 59 ms | 26 ms | 0.42–1.08 | pass |
|  | Median blocking layout switch | 22 ms | 31 ms | 1.38–1.47 | **fail** |
|  | Slowest blocking layout switch | 68 ms | 89 ms | 1.21–1.32 | **fail** |
| Intraline work budget | Unrelated long lines, over budget | 36 ms | 21 ms | 0.56–0.58 | pass |
|  | 8 MiB similar line, refined | 24 ms | 26 ms | 1.07–1.11 | pass |
|  | 8 MiB unrelated lines, over budget | 37 ms | 20 ms | 0.51–0.57 | pass |
| Element height | Height laid out for a 100,000,000 px element | 16,777,214 px | 33,554,428 px |  | reported |

Not measured: the server-side bounds, which are the same whichever engine asks, the diff
fold and first-screen mount, which have no committed fixture, and the Pulls panel, which
needs a signed-in `gh`.

- **Layout is where WebKit falls behind.** The request, JSON parsing, and DOM building
  took about as long in both engines; the forced style and layout after them took the
  difference. JavaScriptCore was faster on pure computation, as the intraline cases show.
- **The source view’s Load more appended one text node per chunk,** which WebKit lays
  out three to five times slower than Chrome; on a bare page, text nodes of at most
  65,536 characters laid out in 0.53 to 0.56 of Chrome’s time.
  #367 made the source view split appended text that way (`TEXT_NODE_MAX_LENGTH` in
  `static/source-append.js`), with the result the status line gives.
- **WebKit does not defer new `content-visibility` blocks as Chrome does,** so the
  binary view ran 1.4 to 2.7 times Chrome; highlighting and the diff switch, 1.1 to 1.5
  times, show the general cost of style and layout under these conditions.
- **Memory and scrolling favor WebKit,** and WebKit drew at 30 frames a second in Low
  Power Mode against Chrome’s 120, which adds up to 33 ms to every metric that waits for
  a frame.

The brief’s answer to a failed bound is to make the bound engine-specific, make a core
change that also helps Safari, or ship its Electron fallback; the choice is the owner’s
and is open.

## `window.print()` and Drag and Drop

`run.mjs --checks` scripts both in the app’s web view class and configuration, with the
app’s navigation policy and `PagePrintRequests` installed as the app installs them, and
drags delivered to the web view’s drop methods as AppKit delivers a drag from Finder.
On the machine above, the Print button sent one request from the main frame of the
server’s own page and File > Print’s path printed the document alone, and a dropped file
and a dropped folder both reached `onFileDrop` before WebKit saw them.

## Addendum, 2026-11-23: The Treemap Case

`run.mjs --cases treemap-100k` measures the Treemap’s bounds, `PAINT_MAX_CELLS`
(`builtin_plugins/folder/treemap-map.js`) and `ROLLUP_MAX_NODES` (`settings.py`), on a
generated folder of 100,003 files in 10,023 folders, 18,309 of them gitignored
(`writeTreemapCorpus`), which a second `metab` serves once its index has finished.
In each engine the probe opens the folder, waits for its Overview, chooses the Treemap
tab, switches the metric three times each way, enters and leaves the legend entry of the
largest family (TypeScript, 29.7% of the files) five times, and then lays the view’s own
rollup out at six cell caps with the map’s own modules, best of five.

The run was on the machine above with macOS 26.5.2, Chrome 152.0.7977.83, WebKit
21624.2.5.11.8, and `metab` and the harness at `9a852e48` with the case uncommitted: 9
pairs after a warm-up pair, Low Power Mode on (WebKit drew at 30 frames a second and
Chrome at 120), and the screen locked.
The host was under heavy load: a 1-minute load average of 84 to 165 on 10 CPUs across
the judged samples, so absolute times are inflated and the pair ratios are the figures
to read.
Times are medians of the 9 pairs, and a ratio is WebKit’s value over Chrome’s in
one pair.

| Case and metric | Chrome | WebKit | Pair ratios | Verdict |
| --- | ---: | ---: | --- | --- |
| Open: rollup response end to labels mounted | 143 ms | 134 ms | 0.89–1.04 | pass |
| Open: rollup response end to next frame | 263 ms | 259 ms | 0.96–1.04 | pass |
| Open: tab click to next frame | 285 ms | 267 ms | 0.89–1.09 | pass |
| Metric to Bytes: click handler | 79 ms | 97 ms | 1.16–1.25 | pass |
| Metric to Bytes: frame work | 84 ms | 109 ms | 1.21–1.38 | **fail** |
| Metric to Files: frame work | 85 ms | 102 ms | 1.14–1.26 | pass |
| Legend hover enter, largest family: handler | 7.4 ms | 19 ms | 1.78–2.60 | **fail** |
| Legend hover enter: frame work | 10.5 ms | 22 ms | 1.38–2.19 | **fail** |
| Legend hover leave: frame work | 2.3 ms | 2 ms | 0.83–1.36 | under 5 ms |
| Layout, paint list, paint, and hit grid, 5,000 cells | 9.3 ms | 11 ms | 0.92–1.29 | pass |
| The same, 10,000 cells | 19.8 ms | 24 ms | 1.04–1.28 | pass |
| The same, 15,000 cells | 34.5 ms | 37 ms | 1.01–1.12 | pass |
| The same, 20,000 cells | 48.9 ms | 55 ms | 1.03–1.17 | pass |
| The same, 25,000 cells | 65.1 ms | 70 ms | 0.97–1.16 | pass |
| The same, every node: 33,030 and 33,028 cells | 85.5 ms | 93 ms | 1.02–1.14 | pass |
| Family hover marks, 25,000 cells | 8 ms | 14 ms | 1.23–1.92 | **fail** |
| Renderer footprint, without graphics | 422 MiB | 199 MiB | 0.39–0.53 | pass |

Both engines laid out 25,000 cells, painted 24,828 and 24,792 of them, and labelled 45.
The hover marked 6,732 and 6,741 cells with 4,470 and 4,472 mark ops.
The rollup was 32,000 nodes and 3.89 MB, sent uncompressed, as a local server sends
every body to its own machine (`gzip_wanted` in `delivery.py`).

- **The layout holds in WebKit.** At every cap it took 0.92 to 1.29 times Chrome’s time,
  near linear in cells in both engines, so WebKit asks for no lower `PAINT_MAX_CELLS`.
  The measurement is beside the constant.
  Whether 25,000 cells keeps a relayout within two frames is not settled by this run:
  Chrome took 65 ms at this load, on a tree that costs more a cell than the one the
  constant was first measured on.
- **The family hover is where WebKit falls behind,** and not for the cell count.
  A second run of 3 pairs that day, at a load of 126 to 150, split the hover’s marks at
  25,000 cells: the palette key `drawCellHover` looks up for every cell on every hover
  took 8 to 13 ms in WebKit and 4.2 to 4.3 ms in Chrome, building the mark ops 1 to 2 ms
  in both, and drawing them 0 to 1 ms in WebKit and 2.5 to 2.6 ms in Chrome.
  The keys change only with a layout, so a hover could read keys kept from the layout
  instead; the rerun below makes that change and measures it.
- **The first paint lays the map out twice in both engines.** The viewport was 415 or
  416 px tall when its labels mounted and 392 or 393 px a frame later: something above
  the map grew by 23 px, and the view’s `ResizeObserver` laid all 25,000 cells out again
  (`treemap.js`), which is most of the 110 ms between the labels’ layout and the next
  frame. Which row grows was not established.
- **The metric switch is 1.1 to 1.4 times Chrome,** more than the layout alone; the rest
  of a switch, the labels, the tally bars, and the legend, was not split.

### The Rerun With Palette Keys Kept

The map then looked each extension’s palette key up once a layout and kept it for the
layout’s hovers (`cellPaletteKey` and `paletteKeys` in `treemap-map.js`), and the
probe’s sweep did the same.
A first try kept every cell’s key but looked each up again in the paint list, which
moved the cost from the hover into every relayout: the hover passed and the metric
switch failed at 1.21 to 1.50 times Chrome.
Keeping one key an extension, 5 pairs at `9a852e48` with both changes uncommitted, at a
1-minute load average of 70 to 150 and otherwise as above, passed every metric:

| Case and metric | Chrome | WebKit | Pair ratios | Verdict |
| --- | ---: | ---: | --- | --- |
| Open: rollup response end to next frame | 252 ms | 230 ms | 0.89–0.99 | pass |
| Metric to Bytes: frame work | 79 ms | 92 ms | 1.11–1.21 | pass |
| Metric to Files: frame work | 77 ms | 86 ms | 1.08–1.12 | pass |
| Legend hover enter, largest family: handler | 2.9 ms | 3 ms | 1.00–1.03 | under 5 ms |
| Legend hover enter: frame work | 6 ms | 5 ms | 0.81–0.85 | pass |
| Layout, paint list, paint, and hit grid, 25,000 cells | 61 ms | 56 ms | 0.88–0.94 | pass |
| Family hover marks, 25,000 cells | 3.6 ms | 1 ms | 0.27–0.56 | under 5 ms |
| Renderer footprint, without graphics | 437 MiB | 204 MiB | 0.43–0.49 | pass |

The first paint still lays the map out twice (`mb-zcs0`).

Not measured: the canvas’s rasterization, which both engines run off the main thread,
the Treemap with Show ignored off, and any of it on an idle host.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
