# Research: Drawing Dense, Deep Treemaps in the Browser

**Date:** 2026-11-22

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Informs
[the treemap granularity plan](../specs/active/plan-2026-11-22-treemap-canvas-granularity.md)
(bead `mb-iirq`).

## Question

How do established tools draw a file system’s treemap down to single files, and what
does it cost in a browser, in Chrome and in the macOS app’s WKWebView, to draw tens of
thousands of cells?

## Method

A survey of the source code, documentation, and papers behind desktop disk-usage tools
and web treemap libraries, and a benchmark of canvas and DOM drawing on one machine.

The benchmark ran on 2026-11-22 on an Apple M1 Pro, macOS 26.5.2, in an embedded
WKWebView (the macOS app’s engine) and headless Chrome 152 over the DevTools protocol.
Each case drew strip-layout rectangles in 12 colors over 1223×587 CSS pixels at a
`devicePixelRatio` of 2, and forced the canvas to flush with a one-pixel `getImageData`.
Times are medians of 3 to 5 runs.
The page and drivers are not committed; the treemap plan repeats the measurements that
set its bounds through the repository’s WebKit measurement gate
(`apps/macos/webkit-gate/run.mjs`), which is.

Caveats: one machine; the WKWebView ran in a window that was not key, with a two-frame
floor near 66 ms; WebKit’s `performance.now()` has 1 ms granularity; Safari itself and
older Macs were not measured.
Claims marked *unverified* had no primary source.

## Findings

### Desktop Tools

| Tool | Rendering | Smallest cell | Hit testing and overlays |
| --- | --- | --- | --- |
| [WinDirStat](https://github.com/windirstat/windirstat/blob/master/windirstat/Controls/TreeMap.cpp) | per-pixel cushion shading into one bitmap, blitted at once | 1 px (2 px with the grid on); folder frames only where the short side is at least 5 px | a 16 px bucket grid, deepest item wins; hover and selection drawn over the cached bitmap |
| [QDirStat](https://github.com/shundhammer/qdirstat/blob/master/doc/Treemap.md) | one scene-graph tile per item, a small cushion image per leaf | rows thinner than 3 px are cut, leaving a grey area in the folder’s corner | wheel zooms one level; middle-click outlines ancestors |
| [SequoiaView](https://wstahw.win.tue.nl/papers/ctm.pdf) | cushion treemap, the technique’s origin | over 3,000 leaves in 640×480 | the image regenerates only when the tree changes; selection is an overlay |
| [GrandPerspective](https://grandperspectiv.sourceforge.net/) | drawing in a background thread | unverified | unverified |
| [DaisyDisk](https://daisydiskapp.com/guide/4/en/UnderstandingSunburst/) | sunburst | small siblings merge into “smaller objects”, listed in a sidebar | — |

WizTree’s release notes report a treemap that once seemed to hang on folders of millions
of files ([changelog](https://www.diskanalyzer.com/whats-new)); how it renders is
unverified, as is everything about SpaceSniffer, SpaceMonger, and Disk Inventory X.

### Web Libraries

- **webtreemap**
  ([source](https://raw.githubusercontent.com/evmar/webtreemap/master/src/treemap.ts)):
  one `<div>` per node, shown only when wider than 20 px and as tall as its 14 px
  header; children only inside 40×40 px.
  Deliberately coarse.
- **FoamTree** ([API](https://get.carrotsearch.com/foamtree/latest/api/)), behind
  webpack-bundle-analyzer: canvas.
  It caps levels drawn and labelled, draws a group’s children all or none by their
  average size (`groupMinDiameter`), redraws only the region a hover changes, draws a
  wireframe within a time budget during animation, and since 3.2 loads children when a
  group opens. It is advertised for 100k+ groups
  ([demo](https://get.carrotsearch.com/foamtree/latest/demos/large.html)). A canvas
  defeats find-in-page ([esbuild #2848](https://github.com/evanw/esbuild/issues/2848)).
- **ECharts**
  ([options](https://apache.googlesource.com/echarts-doc/+/refs/tags/4.8.0/en/option/series/treemap.md)):
  `visibleMin` (default 10 px² of area) hides small nodes; `childrenVisibleMin` hides a
  node’s children below an area until zoomed.
- **Plotly**: SVG, one rectangle and label per node, `maxdepth`; reported sluggish above
  about 10k nodes
  ([forum](https://community.plotly.com/t/max-rows-supported-by-treemap-before-seeing-extreme-low-rendering/70167)).
- **nivo TreeMapCanvas**
  ([source](https://github.com/plouc/nivo/blob/master/packages/treemap/src/TreeMapCanvas.tsx)):
  backing size times `pixelRatio`, one `fillRect` per node, a linear scan to hit-test,
  labels skipped below `labelSkipSize`.
- **d3-hierarchy** ([docs](https://d3js.org/d3-hierarchy/treemap)): layout only;
  squarify at the golden ratio, rounding, padding, and `treemapResquarify` for stable
  updates.
- No maintained WebGL treemap was found worth citing.

### Legibility at Depth

- Squarifying loses the alternating-direction cue, so hierarchy is “far less obvious”;
  the
  [squarified paper](https://classes.engineering.wustl.edu/cse557/readings/squarified-treemap.pdf)
  answers with frames that thin by depth, `⌈w·f^(l−1)⌉`.
- [Cushions](https://wstahw.win.tue.nl/papers/ctm.pdf) shade a parabolic ridge per level
  instead, arguing nested borders waste space and turn deep trees into mazes.
  WinDirStat ships flat and high-contrast presets with no cushion.
- Every tool aggregates what it cannot draw: DaisyDisk’s “smaller objects”, QDirStat’s
  grey area, FoamTree’s all-or-none children.

### Data Delivery

- [ncdu’s binary format](https://dev.yorhel.nl/ncdu/binfmt) stores each directory’s
  cumulative size and count, in indexed compressed blocks, so a tree can be browsed
  without loading it whole.
  [duc](https://github.com/zevv/duc/blob/master/doc/duc.md) keeps an indexed database of
  the same and draws four levels by default.
- FoamTree and ECharts both fetch or reveal children only when a group is large enough
  or opened.

### Canvas and DOM Cost

Paint time, in ms:

| Rectangles | WebKit, a fill per rect | WebKit, grouped by color | WebKit, `ImageData` | Chrome, per rect / grouped | Chrome, `ImageData` |
| --- | --- | --- | --- | --- | --- |
| 1k | 3 | 1–3 | 4–10 | 2 / 3 | 5–9 |
| 10k | 8 | 5–9 | 13–15 | 9–10 / 8 | 4–11 |
| 50k | 29–30 | 16–23 | 16–19 | 36–38 / 38–39 | 8–15 |
| 100k | 62–67 | 31–33 | 17–23 | 61–64 / 59–60 | 11–22 |

- Stroking every outline in one path doubles WebKit’s time at 100k (64 against 33 ms).
- **Removing DOM cells in WebKit grows faster than linearly**: about 250 ms for 5k
  `<div>`s, 1,000 ms for 10k, 4,700 ms for 20k, and minutes for 50k, whether by
  `innerHTML = ""`, `replaceChildren()`, or removing their parent.
  Chrome stayed at its frame floor.
  Building them to the second frame cost 105 ms at 10k in WebKit and 67 ms in Chrome.
- Hit testing 100k rectangles: a linear scan takes 0.41 ms a lookup in WebKit and 0.11
  ms in Chrome; a 16 px bucket grid takes about 1.5 µs and 0.5 µs, and builds in about 2
  ms. Reading pixels back costs a synchronous round trip to WebKit’s GPU process
  ([GPUProcess](https://trac.webkit.org/wiki/GPUProcess)).
- `ctx.filter` is absent in the WKWebView (`'filter' in ctx` is false), disabled by
  default through Safari 27
  ([caniuse](https://caniuse.com/mdn-api_canvasrenderingcontext2d_filter)).
- `OffscreenCanvas`, with a 2D context and `transferControlToOffscreen`, works in the
  WKWebView (Safari 17+, [caniuse](https://caniuse.com/offscreencanvas)).
- Canvas hit regions never shipped
  ([whatwg #7490](https://github.com/whatwg/html/issues/7490)); the accessible pattern
  is focusable DOM elements over or behind the canvas, with the focus ring drawn
  separately ([TPGI](https://www.tpgi.com/html5-canvas-sub-dom/)).

### Rollup Budget on This Repository

The production `build_rollup`, replayed on 2026-11-22 over a walk of this repository’s
main checkout (38,819 entries, 2,741 of them outside gitignored paths), at several node
budgets and `top` values, with each tree laid out by the production `layoutTree` at
1223×587 with a 0.5 px cell floor.
The replay and its outputs are in the worktree’s gitignored `attic/treemap-budget/`
(`run.sh` reruns them); the table is in the
[treemap granularity plan](../specs/active/plan-2026-11-22-treemap-canvas-granularity.md#where-the-area-goes).
In short: without ignored files the whole tree is 2,740 nodes and 0.49 MB of JSON, under
today’s 4,000-node budget; with them it is 38,402 nodes, 7.49 MB of JSON (0.79 MB
gzipped, 2.39 MB as positional arrays without paths), and today’s budget leaves 53.8% of
the map in unexpanded folders.

## Conclusions

1. One canvas paints every cell down to about a device pixel: about 25 ms for a 36k-cell
   map in either engine, 8 to 10 ms for 10k. Grouping fills by color halves WebKit’s
   cost at 50k and above.
2. DOM is kept for a bounded set of a few hundred labelled cells, reused across layouts,
   since WebKit’s teardown cost already reaches a quarter second at 5k.
3. Hover and selection go on an overlay, never a repaint of the map, and never through
   `ctx.filter`.
4. Hit testing is geometric, through a bucket grid built after layout.
5. The data, not the renderer, bounds the map when ignored files are shown: the budget
   must rise, in a compact encoding, and with ignored files hidden the budget must skip
   them, which alone completes the tree.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
