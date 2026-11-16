# QA: WebKit Measurement Gate, 2026-11-11

**Date:** 2026-11-11

**Status:** A dated record of one run of `make macos-webkit-gate`, which failed.
The source view’s largest cost has since had a core fix (#367, `mb-551q`); after it the
Load more row still measured 2.25 to 2.46 times Chrome and the first-click probe 2.45 to
2.51 times. The rerun is `mb-76nv`, and what follows from the failure is the owner’s
decision (`mb-gvtw`).
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

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
