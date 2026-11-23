# Plan for Treemap Granularity: Canvas Cells and a Denser Rollup

**Date:** 2026-11-22 (last updated 2026-11-22)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft, revised after design review.
Bead `mb-iirq` tracks it, under the treemap epic `mb-bjsy`. It is the fourth and fifth
layers of the treemap stack, on top of
[#722](https://github.com/jlevy/metabrowser/pull/722) (heaviest-first rollup),
[#723](https://github.com/jlevy/metabrowser/pull/723) (deep nesting, containment), and
[#724](https://github.com/jlevy/metabrowser/pull/724) (compact map on the Overview), so
those can land first on their own.
[Design Review](#design-review) records what an independent review changed.

## Overview

The owner asked, on 2026-11-22:

> “I still don’t see the level of granularity I would expect … There are large items
> that have hundreds of subcomponents.
> Why can’t we draw them?
> … Surely there’s an efficient way to draw these.”

The Treemap draws every cell as an absolutely positioned `<div>`. That caps it in two
ways at once: a cell must be at least `minCellPx` (4 px) on each side to be worth a DOM
node, and the map stops at `maxCells` (1,600) because writing markup is most of a
render’s cost. Behind both sits the server’s node budget, `ROLLUP_MAX_NODES` (4,000), so
a folder the budget did not reach arrives with no children and draws as one solid
rectangle however large it is.

This plan fixes the renderer and the data, in that order:

1. **Canvas cells** (layer 4): one `<canvas>` paints every cell down to about one device
   pixel; DOM keeps only labels, a focus proxy, and the cell under the pointer; the
   map’s own geometry answers the pointer.
2. **A denser rollup** (layer 5): the Treemap asks for a larger node budget in a compact
   encoding, and a map that hides ignored files spends none of it on them.

## Goals

- Draw every file whose share of the map is at least about one device pixel, as
  WinDirStat does (see [Prior Art](#prior-art)), and keep neighbours of one type
  distinct.

- Cut the share of the map drawn as unexpanded solid folders, measured on this
  repository: 44.9% today (Files, Show ignored on, see [Design Review](#design-review)).

- Every cell answers the pointer as cells do today, however small: the tooltip names it,
  a click opens it, the shared hover marks it.

- Keyboard reach stays what it is today: every folder and file cell drawn is reachable
  by the arrow keys, named, and opened with Enter; Backspace goes to the parent.

- Relayout and repaint stay within the frame budgets measured for them, in Chrome and in
  WebKit, and the DOM the map keeps shrinks from up to 1,600 cells to its labels.

## Non-Goals

- WebGL. Canvas 2D paints 50k cells in about 20 ms in WKWebView (see
  [Prior Art](#prior-art)); WebGL adds a context the app may lose and a second paint
  path for nothing measured.

- Zooming or panning inside the map.
  Drill-down stays navigation: a click opens the folder in the Treemap view at that
  path, as today.

- Client-side subtree fetching (grafts).
  The review’s simulation found 16 grafts still leave 29.7% of the map solid at 17
  requests and 1.44 MB, against 0% for one whole-tree response (see
  [Design Review](#design-review)). If the denser rollup’s budget still binds on large
  trees, grafts become a follow-up with the lifecycle the review set out.

- Cushion shading, as a style; but see [Separators](#separators).

- A worker thread or `OffscreenCanvas`. Both work in the WKWebView, and neither is
  needed at the measured costs; the layout stays plain JavaScript, testable without a
  browser.

- Changing what the Files tally, legend, or Overview bars count, or the Overview’s one
  request.

## Background

### Measurements That Motivate It

Measured on this repository, full Treemap at 1223×587, Files metric, Show ignored on,
stack head `658657751`:

| Quantity | Value |
| --- | --- |
| Nodes the server sent | 4,000 (the budget) |
| Cells drawn | 584 |
| Folders drawn solid because the budget did not expand them | 464 |
| Examples | `node_modules/zod` 840 files, `node_modules/@highlightjs` 892 files, each drawn solid at about 120×130 px |
| Files of `tests/` folded into a remainder by `top=200` | 351 |
| Files ÷ area | 35,790 files over 718k px², about 20 px² a file |
| Same with Show ignored off | 2,599 files, about 276 px² a file; 1,293 files sent, 88 unignored folders unexpanded |

So the DOM floor (4 px a side, 16 px²) is near the average file’s whole share with
ignored files shown, and most files are far below the average.
No DOM tuning reaches them; a pixel-level renderer does.

### What Exists Today

- `treemap-layout.js`: squarified layout (Bruls, Huizing, van Wijk 2000), breadth-first
  by area across folders, with a per-folder remainder cell for what does not fit.
  Bounds in `LAYOUT_DEFAULTS`: `minCellPx`, `maxCells`, `padPx`, `frameNestMinPx`,
  `nestMinH`, `minNestShare`. Cells are emitted parent first.

- `treemap-map.js`: the reusable map component (`createTreemapMap`), with `full` and
  `compact` presets. It writes one `innerHTML` string, routes pointer events by
  `closest("[data-tm-cell]")`, keeps a roving tabindex over actionable cells, and marks
  hover with `data-hovered` (a CSS `filter` lift, plus a shimmer on the cell under the
  pointer).

- `treemap.js` (the view) and `treemap-compact.js` (the Overview’s map) fetch through
  `mb.watchRollup` with `depth=max&top=max`, which the route resolves to
  `ROLLUP_MAX_DEPTH` and `ROLLUP_MAX_TOP`.

- `/api/rollup?path=` already serves any subtree, under the same node budget.

## Prior Art

[Drawing dense, deep treemaps in the browser](../../research/research-2026-11-22-dense-treemap-rendering.md)
surveys the tools and measures the costs; what this plan takes from it:

| Source | What it does | Taken here |
| --- | --- | --- |
| WinDirStat | paints every item into one bitmap down to 1 px; frames only where the short side is 5 px; 16 px bucket grid for hit tests; hover over the cached bitmap | all four |
| QDirStat | cuts rows under 3 px and leaves the folder’s corner grey | the remainder, at a 1 px floor instead of 3 |
| SequoiaView, cushion paper | regenerates the image only when the tree changes; selection is an overlay | the hover canvas |
| FoamTree | canvas; a group’s children drawn all or none; redraws only what a hover changes; loads children when a group opens | not the lazy loading (see Non-Goals) |
| webtreemap, Plotly | one DOM or SVG node per cell; coarse by design, sluggish above about 10k | the reason not to grow the DOM |
| ncdu, duc | cumulative size and count per directory, so an unexpanded folder still lays out; compact on-disk encodings | the compact encoding |
| Accessible canvas apps | focusable DOM elements over the canvas, focus ring drawn separately | the focus proxy |

Measurements that decide the design (Apple M1 Pro, 1223×587 at `devicePixelRatio` 2):

- **Canvas paint is cheap but not free**: `fillRect` per rectangle with `fillStyle`
  grouped, 5 to 9 ms for 10k rectangles and 16 to 23 ms for 50k in WKWebView; 8 ms and
  38 ms in Chrome, so 50k is already past two frames in Chrome.
- **DOM teardown in WebKit grows faster than linearly**: 59 ms to remove 1k `<div>`s,
  201 ms for 4k, 1,000 ms for 10k, 4,700 ms for 20k, however they are removed.
- **Geometric hit testing is free**: a 16 px bucket grid answers in under 2 µs and
  builds in about 2 ms for 100k rectangles; pixel readback is a synchronous round trip
  to WebKit’s GPU process.
- **`ctx.filter` does not exist in the WKWebView**; a CSS `filter` on an element does.

## Design: Canvas Cells (Layer 4)

### Layers

| Layer, bottom to top | Contents | Pointer events |
| --- | --- | --- |
| Paint canvas | every cell’s fill and edge | none |
| Hover canvas | copies of the marked cells’ pixels, under CSS `filter: var(--viz-data-mark-hover-filter)` | none |
| Label layer | one text element per labelled cell: icon, name, value | none |
| Hover anchor | one transparent `.tm-cell` element over the cell under the pointer, carrying today’s shimmer | none |
| Focus proxy | one `role="button"` element over the focused cell, with its name and focus ring | focusable |

The viewport owns all pointer events and routes them through the hit test.
Painting every fill on one canvas avoids the stacking problem a DOM and canvas mix has,
since a DOM folder’s fill covers any canvas cell inside it, and matches WinDirStat: a
bitmap first, then text where it fits.
Labels stay DOM, so they are crisp, use the app’s fonts, and stay findable with the
browser’s find-in-page, which a canvas defeats.
They are no longer selectable, since the viewport takes the pointer.

The label layer reconciles by `(kind, path)`, since a remainder cell shares its folder’s
path: a layout moves and retexts the labels that remain, adds new ones, and removes the
rest. The review counted 73 to 107 labelled cells in every scenario, so the layer needs
no cap of its own; the paint canvas carries everything else.

### Layout

`layoutTree` keeps its breadth-first, area-ordered nesting and changes in three ways:

- `minCellPx` becomes `paintMinPx`, one device pixel (`1 / devicePixelRatio`) by
  default. Cells below it fold into the parent’s remainder, as today.
  `packLevel` still emits a rectangle that is tiny after its final pass, so its area
  stays true; a cell whose edges snap to zero device pixels paints nothing and is not
  hit, and a test counts them.
- `maxCells` becomes `maxPaintCells`.
- A folder too small for a header nests inside a frame whose width shrinks with depth,
  after the squarified paper (`⌈w·f^(l−1)⌉`), drawn only where the folder’s short side
  is at least 5 px, WinDirStat’s threshold; below it, the folder’s children tile it edge
  to edge. This replaces `frameNestMinPx` and the fixed `padPx` for unlabelled folders.

Speed work waits for a profile in the browser.
The review found the cost follows children visited (6,917 at 1,600 cells, 111,333 at
10,000), because `emitLevel` builds and sorts every child of a folder even when its
share is a handful of cells, and the pending scan is at most 6.4% of the time at 50k. So
the first candidate is selecting only the children a folder’s share can hold; a heap and
typed arrays only if the profile then asks for them.

The layout’s outputs are pure data the goldens pin: the **paint list** (rectangle in
device pixels, color key, depth, edge or not), the **label set**, the **focus order**,
and the **hit grid**.

### Separators

Today every cell has a 1 px inset edge in a stronger tone (`--tm-edge`, `styles.css`),
so two files of one type side by side stay two cells, and a folder and its files of the
folder’s dominant type stay apart.
A gap alone would show the parent’s fill, usually the same color, and
`node_modules/zod/src`’s 332 `.ts` files would still read as one block.

- A nesting folder paints its interior in its edge tone, then its children over it.
- A cell at least `separatorMinDevicePx` (3 to start) on each side draws one device
  pixel short on its right and bottom edges, so the edge tone shows between neighbours.
- A smaller cell draws edge to edge.
  At that scale a run of same-type files reads as texture, as it does in WinDirStat’s
  flat preset; whether a light cushion term should separate them is the
  [open question](#open-questions), measured on this case.

### Painting

- The backing store is the viewport’s padding box times `devicePixelRatio`, with
  `setTransform(dpr, …)`, capped at `maxBackingPixels`, set below WebKit’s canvas area
  limit. A `matchMedia` resolution listener repaints when the pixel ratio changes.
- **Colors come from the stylesheet.** For each distinct
  `(palette key, ignored, pending, rest)` combination, a hidden probe element takes a
  cell’s classes and inline style, and the map reads its `background-color`, `--tm-edge`
  color, and `opacity`. Probes are reread when the color scheme or theme changes.
- Rectangles are drawn depth by depth, so parents stay under their children, and within
  a depth grouped by `fillStyle`, one `fillRect` each: the measured pattern.
- A pending cell draws at the reduced-motion opacity; the pulse is not animated.
- The paint canvas repaints on layout, a color change, or a pixel-ratio change, never on
  hover. During a resize the bitmap stretches with the viewport, and the map lays out
  again when the size settles, since `treemap.js` lays out on every resize callback.

### Hover

The shared hover (`DistributionHover`) keeps its contract with the bars and legend,
which key on anchor identity (`distribution-hover.js`, `sameTarget`), as the tooltip
does (`app.js`, `showTooltip`).

- **Marks are pixel copies.** For the marked set, the map walks the paint list in order
  and emits an op only where marking changes: *copy* a marked cell whose parent is not
  marked, *clear* an unmarked cell whose parent is.
  Each op copies or clears that rectangle of the paint canvas onto the hover canvas,
  whose element carries the CSS lift filter.
  So a marked folder lifts without its unmarked children, translucent ignored cells are
  not composited twice, and the lift is whatever the theme’s filter is, darkening or
  brightening. A family that marks every cell is one copy.
  The op list is pure and golden-pinned.
- **The cell under the pointer** gets a new hover anchor element for each cell it
  enters: a transparent `.tm-cell` over the cell’s rectangle with `data-hovered="self"`,
  so today’s CSS shimmer, its reduced-motion rule, and its compositor animation apply
  unchanged, and the tooltip and shared hover see a new anchor for every cell.
  On a nesting folder the anchor would shimmer over its children, so a folder gets the
  lift and not the shimmer; `docs/design-system.md` says so.
- **After every layout** the map hit-tests the last pointer position again and moves the
  anchor, tooltip, and mark if the cell under the pointer changed, since a canvas raises
  no `mouseover` when its content changes under a still pointer.

### Hit Testing

After each layout the map builds a 16 px bucket grid over cell indexes, deepest last.
A point maps to the deepest cell in its bucket that contains it.
`mousemove`, at most one lookup a frame, sets the anchor, tooltip, mark, and cursor;
`click` activates the cell under the pointer.
The grid and lookup are a pure module: every interior point maps to the deepest cell
containing it, and a point in a frame or gap maps to the folder.

### Keyboard and Accessibility

Today every folder and file cell drawn is a named button in one roving order
(`treemap-map.js`), and the full view has no outer box.
One **focus proxy** keeps that: a single `role="button"` element the arrow keys move
through every actionable cell in layout order, positioned over the focused cell, with
its accessible name and the focus ring.
Enter opens the cell; Backspace goes to the parent; the proxy exists whenever any
actionable cell does, so Backspace works on a map of tiny cells.
A folder’s name gains its remainder (“…, 351 more files in the remainder”), since
remainder cells lose their own `role="group"` elements.
The canvases are `aria-hidden`.

## Design: A Denser Rollup (Layer 5)

### Where the Area Goes

The review replayed the production `build_rollup` on this worktree (19,917 files, 21,005
nodes) and laid each tree out with the production layout at 1223×587, Files, Show
ignored on:

| Plan | Requests | JSON | Map area in unexpanded folders | In remainders |
| --- | --- | --- | --- | --- |
| Today: 4,000 nodes, `top` 200 | 1 | 0.76 MB | 44.9% | 18.0% |
| 16 client grafts | 17 | 1.44 MB | 29.7% | 18.9% |
| `top` raised to the budget | 1 | 0.71 MB | 65.3% | 2.8% |
| 8,000 nodes | 1 | 1.47 MB | 26.6% | 19.0% |
| The whole tree | 1 | 3.69 MB | 0% | 0% |

The canvas alone leaves 43.6% to 44.9% unexpanded.
Raising `top` alone makes the first paint worse, because
`emit_limit = min(top, remaining)` (`inventory_rollup.py`) lets one flat folder take the
budget.
The bytes, not the node count, are the cost, and most bytes are per-file keys and
repeated paths.

The same replay on this repository’s main checkout, on 2026-11-22 (38,819 entries,
`attic/treemap-budget/run.sh`, recorded in the
[research document](../../research/research-2026-11-22-dense-treemap-rendering.md#rollup-budget-on-this-repository)),
Files metric, gzip at level 6:

| Scope | Nodes | `top` | JSON | gzip | Compact | Server ms | Unexpanded | In remainders |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Show ignored on | 4,000 | 200 | 0.75 MB | 0.09 MB | 0.29 MB | 14.5 | 53.8% | 9.3% |
|  | 16,000 | 200 | 3.17 MB | 0.35 MB | 1.11 MB | 38 | 21.3% | 10.2% |
|  | 16,000 | 16,000 | 3.03 MB | 0.33 MB | 1.01 MB | 25 | 32.3% | 0.2% |
|  | 32,000 | 32,000 | 6.19 MB | 0.66 MB | 1.99 MB | 50 | 6.9% | 0.0% |
|  | the whole tree |  | 7.49 MB | 0.79 MB | 2.39 MB | 67 | 0.1% | 0.0% |
| Ignored files left out | 4,000 | 200 | 0.43 MB | — | 0.14 MB | 4 | 0.0% | 14.8% |
|  | 2,740, the whole tree | 4,000 | 0.49 MB | 0.07 MB | 0.17 MB | 4 | 0.0% | 0.0% |

Two answers follow. **Without ignored files, the whole tree fits today’s budget**: 2,740
nodes, so leaving ignored files out of the budget and letting `top` reach it draws every
file in 0.5 MB, with no new encoding.
**With ignored files shown**, the budget binds hard: `node_modules` and the virtual
environment hold 93% of the entries, the whole tree is 7.5 MB of JSON to parse (0.8 MB
on the wire), and the compact encoding cuts the parse to 2.4 MB.

### Changes

- **A budget that skips what the map hides**, first, because it alone completes the
  default view. `ignored=exclude` emits no gitignored children, so with Show ignored off
  the budget goes to the files the map draws, and `top` rises to the budget for that
  scope, since the whole unignored tree is under it.
  The Show ignored toggle then refetches, where today it is client-only.
- **A compact encoding.** `/api/rollup?encoding=compact` writes each folder’s file
  children as positional arrays (name, size, mtime, extension, ignored) without `path`,
  which the client derives from the folder’s path.
  Measured on the main checkout, it is a third of the JSON: 2.39 MB for the whole tree
  against 7.49 MB. Only the Treemap view asks for it, and the folder plugin decodes it,
  not `plugin-sdk.js`, which is eager and at its startup byte budget.
- **A node budget the request names.** `nodes=` bounded by a raised `ROLLUP_MAX_NODES`,
  set from the measurement; the default stays 4,000, so the Overview and other callers
  are unchanged and the Overview keeps one request of today’s size.
- **`top` set together with the budget**, so a flat folder cannot take it.
- **The body cache** (`ROLLUP_BODY_CACHE_ENTRIES`) gets a byte bound beside its entry
  bound, since denser bodies raise its ceiling.

Grafts stay out: with ignored files left out the tree is complete, and with them shown a
budget near 32,000 compact nodes leaves under 7% unexpanded; the browser measurement of
parse and layout at that size decides the budget.

## Components

| File | Layer | Change |
| --- | --- | --- |
| `treemap-layout.js` | 4 | `paintMinPx`, `maxPaintCells`, depth-thinned frames, the paint list, the label set, the focus order |
| `treemap-hit.js` (new, pure) | 4 | the bucket grid and point lookup |
| `treemap-paint.js` (new) | 4 | backing store, probe colors, depth-ordered grouped fills, edges, mark ops |
| `treemap-map.js` | 4 | the five layers, label reconciliation, pointer routing, the hover anchor, the focus proxy, disposal |
| `styles.css`, `docs/design-system.md` | 4 | the layers’ styles; the hover lift on the hover canvas; folders lift without the shimmer |
| `inventory_rollup.py`, `server.py`, `settings.py` | 5 | `encoding=compact`, `nodes=`, `ignored=exclude`, the budget, `top`, the body cache bound |
| `treemap.js` | 5 | asks for the dense, compact rollup and decodes it |

The new modules load with the folder plugin’s other treemap modules, not in the shell’s
eager path.

## Bounds to Measure

Per [rendering large content](../../../large-content-rendering.md), each bound is set
from a measurement in a real browser and recorded beside its constant, in Chrome and in
the macOS app’s WKWebView through the WebKit measurement gate
(`apps/macos/webkit-gate/run.mjs`), on this repository’s main checkout and on a
synthetic tree of 100k files.
The gate judges WebKit against Chrome and leaves times under 5 ms unjudged, so each
bound also gets an absolute budget of its own.

| Bound | Layer | Measures | Starting point |
| --- | --- | --- | --- |
| `maxPaintCells` | 4 | layout and paint ms at 5k, 10k, 25k, 50k cells | the largest count within two frames in both engines; Chrome’s 38 ms at 50k suggests about 25k |
| `paintMinPx` | 4 | visible distinction of 1, 2, and 3 device px cells | one device pixel |
| `separatorMinDevicePx` | 4 | same-type neighbours legible on `node_modules/zod/src` | 3 |
| `maxBackingPixels` | 4 | WebKit’s canvas area limit | below it |
| mark ops | 4 | ms to apply the ops for a family marking every cell, and the worst alternating case | under one frame |
| `ROLLUP_MAX_NODES`, `top` | 5 | compact JSON bytes, server ms, unexpanded and remainder share, at 4k, 8k, 16k, 32k nodes and the whole tree | the knee of the unexpanded-share curve |
| body cache byte bound | 5 | resident bytes at the chosen budget | the ceiling `settings.py` documents |

A first reading of the layout alone, in Node on 2026-11-22, on a synthetic tree of 120k
files at 1223×587, best of 15 runs on a host at a load average near 300: 1.8 ms at 1,600
cells, 18 ms at 5,000, 150 ms at 10,000 and 25,000, 200 ms at 50,000, 800 ms at 100,000.
The load makes the absolute numbers unreliable; the growth is the reason the layout is
profiled before `maxPaintCells` is set.

## Implementation Plan

Two stack layers. The canvas comes first because it is visible on its own (the review
counted 1,483 to 3,875 cells drawn where today draws 584) and because denser data has
nowhere to go without it.
The budget measurement runs first of all, since it decides layer 5’s shape and whether
grafts are needed at all.

### Phase 1: Canvas Cells (layer 4, `claude/treemap-canvas`)

- [x] Measure the budget curve on the main checkout with the review’s replay (it reuses
  the production `build_rollup`), and record it in the research document.
- [x] Layout: `paintMinPx`, `maxPaintCells`, depth-thinned frames, the paint list, the
  label set, the focus order, with vm tests: every cell inside its parent, labelled
  cells are the largest, bounds respected, zero-size cells counted.
- [x] `treemap-hit.js` with its invariants.
- [x] `treemap-paint.js`: backing store, probes, fills, edges, mark ops.
- [x] `treemap-map.js`: layers, label reconciliation, routing, the hover anchor, the
  focus proxy, re-hit-testing after layout; disposal of canvases (zeroed), listeners,
  probes, the theme and resolution listeners, and pending frames; placeholders that
  leave the layers in place.
- [x] Set the layer’s bounds in Chrome: `PAINT_MAX_CELLS` in `treemap-map.js`, with its
  measurement. The WebKit gate’s treemap case moves to Phase 2 (mb-72rg): the rollup’s
  4,000-node budget keeps this layer’s map near 4k cells, which Chrome paints in 7 ms
  and WebKit fills at well under a frame (the research benchmark: 5 to 9 ms for 10k
  rectangles), so `PAINT_MAX_CELLS` first binds once Phase 2 raises the budget.
- [x] Extend the containment Chrome test to every cell, sampling pixels at cell centers
  against the probe colors; keyboard reach over every actionable cell.
- [x] Sessions and goldens (`cli-ui-treemap-compact`, `cli-ui-treemap-legend`,
  `cli-ui-treemap-not-indexed`), driven by pointer coordinates at a pinned pixel ratio;
  parity rows; `docs/design-system.md` “Folder Treemap”; a changelog fragment.

### Phase 2: A Denser Rollup (layer 5, `claude/treemap-dense-rollup`)

- [x] `encoding=compact`, `nodes=`, `ignored=exclude` in the rollup and route, with
  tests and a golden through `metab --api` (`cli-api-rollup-dense.tryscript.md`).
- [x] The Treemap view asks for them and decodes in the folder plugin
  (`treemap-rollup-decode.js`); the route’s two encodings decode to one tree
  (`tests/test_treemap_rollup_decode.py`), and the layout orders equal values by path,
  so the map does not depend on the encoding’s child order.
- [x] Set `ROLLUP_MAX_NODES`, `top`, and the body cache bound from the measurement
  (`settings.py`, beside each constant).
- [ ] A treemap case in the WebKit gate at the raised budget; profile the layout; set
  `PAINT_MAX_CELLS` from both engines (mb-72rg).
- [x] Parity rows, docs, a changelog fragment.
  The measurement asks for no grafts: at `ROLLUP_MAX_NODES` the unexpanded share of the
  map is under 1%, and with Show ignored off the visible tree fits the default budget
  whole.

## Testing Strategy

- **Browserless** (the parity rules in `AGENTS.md`): the paint list, label set, focus
  order, hit lookup, mark ops, and the compact decoding are pure outputs of production
  modules, each with focused invariants and a golden session.
  Which cells a hover marks stays session-owned, as the parity registry has it today.
- **Chrome**: containment of every cell; probe colors at sampled cell centers; a pointer
  over an unlabelled cell shows its tooltip, a click opens it, and a layout under a
  still pointer moves the tooltip.
- **WebKit**: the gate’s treemap case, against the absolute budgets as well as Chrome.
- **Parity exemption**: rasterization only, the step from the pinned paint list and mark
  ops to pixels, with the Chrome pixel samples and the gate as its evidence.

## Rollout Plan

Ships with the treemap stack as one artifact: server, browser shell, and the folder
plugin change together, so no compatibility layer is owed.
A changelog fragment per layer: the map draws every file down to a pixel; the Treemap
view receives the whole tree, or far more of it, in one request.

## Design Review

An independent review on 2026-11-22 read the first draft against the code, replayed the
rollup at other budgets, and found:

| Finding | Change |
| --- | --- |
| Same-type neighbours would paint as one block: the separator was a gap showing the parent’s same color | [Separators](#separators): interiors in the edge tone |
| One moving tooltip proxy keeps the first cell’s text: the tooltip and shared hover key on anchor identity | a new hover anchor per cell |
| Client grafts leave 29.7% unexpanded at 17 requests; raising `top` alone makes it worse | grafts dropped; layer 5 is a compact, denser rollup |
| A canvas raises no events when its content changes under a still pointer | re-hit-test after every layout |
| Keyboard reach shrank: the full view has no outer box, and a folder of small files had no tab stop | one focus proxy over every actionable cell |
| The hover canvas covered unmarked children, double-composited translucent cells, assumed the lift lightens, and animated an infinite shimmer in script | marks as pixel copies under the CSS filter; the shimmer stays CSS on the anchor |
| The benchmark measured `fillRect` grouped by color, not one path per color; grouping by color breaks parent-first order | depth by depth, grouped within a depth |
| Layout cost follows children visited, not the pending scan; `maxLabelCells` was never binding | profile first; select only what a share holds; no label cap |
| “The canvas itself” was a blanket parity exemption | rasterization only; paint list and mark ops pinned |

## Open Questions

- Below `separatorMinDevicePx`, same-type files read as texture.
  Is a light cushion term (van Wijk and van de Wetering) worth it to separate them,
  given it is a second visual language beside the bars’ flat fills?
- A folder under the pointer lifts without shimmering, since its anchor would cover its
  children. Acceptable, or should the shimmer clip to the folder’s header and frame?
- With `ignored=exclude`, the Show ignored toggle refetches instead of relaying out.
  Acceptable for the budget it frees?

## References

- [Drawing dense, deep treemaps in the browser](../../research/research-2026-11-22-dense-treemap-rendering.md)
- [Rendering large content](../../../large-content-rendering.md)
- [Parity Registry](../../architecture/arch-parity-registry.md)
- `docs/design-system.md`, “Folder Treemap”
- Beads: `mb-iirq` (this plan), under the epic `mb-bjsy`; `mb-3m31`, `mb-9xaz`,
  `mb-qb2x` (layers 1 to 3)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
