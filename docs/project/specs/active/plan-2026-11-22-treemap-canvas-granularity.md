# Plan for Treemap Granularity: Canvas Cells and On-Demand Folders

**Date:** 2026-11-22

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft, in design review.
Bead `mb-iirq` tracks it, under the treemap epic `mb-bjsy`. It is the fourth and fifth
layers of the treemap stack, on top of
[#722](https://github.com/jlevy/metabrowser/pull/722) (heaviest-first rollup),
[#723](https://github.com/jlevy/metabrowser/pull/723) (deep nesting, containment), and
[#724](https://github.com/jlevy/metabrowser/pull/724) (compact map on the Overview), so
those can land first on their own.

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

This plan paints every cell’s fill on one `<canvas>`, down to about one device pixel,
keeps DOM only for the labels, focus rings, and accessible names of the cells large
enough to label, hit-tests the map’s geometry for tooltips and clicks, and fetches the
children of large unexpanded folders on demand.

## Goals

- Draw every file whose share of the map is at least about one device pixel, as
  WinDirStat does (see [Prior Art](#prior-art)).

- A large folder the first rollup did not expand fills in, after the first paint, with
  its own children.

- Every cell answers the pointer as cells do today, however small: the tooltip names the
  cell under the pointer, a click opens it, and the shared hover marks it.

- Relayout and repaint stay within the frame budgets measured for them, in Chrome and in
  WebKit, and the DOM the map keeps shrinks from up to 1,600 elements to a few hundred.

- Keyboard and screen-reader access stay what they are today: every labelled cell is a
  focusable control with a name, and Enter on a folder opens it, where its own children
  are drawn large enough to label.

## Non-Goals

- WebGL. Canvas 2D paints 50k cells in about 20 ms in WKWebView (see
  [Prior Art](#prior-art)); WebGL adds a context the app may lose and a second paint
  path for nothing measured.

- Zooming or panning inside the map.
  Drill-down stays navigation: a click opens the folder in the Treemap view at that
  path, as today.

- Cushion shading. It is a style choice, not a granularity one; see
  [Open Questions](#open-questions).

- A worker thread or `OffscreenCanvas`. Both work in the WKWebView, and neither is
  needed at the measured costs; the layout stays plain JavaScript, testable without a
  browser.

- Changing what the Files tally, legend, or Overview bars count.

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
| SequoiaView, cushion paper | regenerates the image only when the tree changes; selection is an overlay | the overlay canvas |
| FoamTree | canvas; a group’s children drawn all or none; redraws only what a hover changes; loads children when a group opens | on-demand folders |
| ECharts | `childrenVisibleMin` hides children below an area | the expansion threshold |
| webtreemap, Plotly | one DOM or SVG node per cell; coarse by design, sluggish above about 10k | the reason not to grow the DOM |
| ncdu, duc | cumulative size and count per directory, so an unexpanded folder still lays out | already true of `/api/rollup` |

Four measurements decide the design (Apple M1 Pro, 1223×587 at `devicePixelRatio` 2):

- **Canvas paint is cheap**: grouped by color, 5 to 9 ms for 10k rectangles and 16 to 23
  ms for 50k in WKWebView; 8 ms and 38 ms in Chrome.
  A 36k-file map is about 25 ms in either engine.
- **DOM teardown in WebKit grows faster than linearly**: 250 ms to remove 5k `<div>`s,
  1,000 ms for 10k, 4,700 ms for 20k, however they are removed.
  Today’s 1,600-cell cap is already on that curve, so this plan *shrinks* the DOM.
- **Geometric hit testing is free**: a 16 px bucket grid answers in under 2 µs and
  builds in about 2 ms for 100k rectangles; pixel readback is a synchronous round trip
  to WebKit’s GPU process.
- **`ctx.filter` does not exist in the WKWebView**, so the hover lift cannot reuse
  `--viz-data-mark-hover-filter` on the canvas.

## Design

### Approach

Three changes, each with its own bound:

1. **One canvas paints every cell’s fill**, down to `paintMinPx`, under `maxPaintCells`.
2. **DOM keeps only labelled cells**, as transparent controls over the canvas, under
   `maxLabelCells`, reused across layouts.
3. **The map asks its host to expand large unexpanded folders**, grafts the answers into
   its tree, and lays out again.

### Layers

| Layer, bottom to top | Contents | Pointer events |
| --- | --- | --- |
| Paint canvas | every cell’s fill, frames, separators | none |
| Hover canvas | the lift on marked cells, the shimmer on the cell under the pointer | none |
| Label layer | one transparent element per labelled cell: icon, name, value, focus ring, accessible name | none; the viewport routes them |

Painting every fill on one canvas removes the stacking problem a DOM and canvas mix
would have, since a DOM folder’s fill would cover any canvas cell inside it.
It also matches WinDirStat: a bitmap first, then text where it fits.
Labels stay DOM, so they are crisp at any zoom, use the app’s fonts, and stay findable
with the browser’s find-in-page, which a canvas defeats.

The label layer is bounded by `maxLabelCells` and reconciled by path: a layout updates
the position and text of an element whose cell is still labelled, adds those that became
labelled, and removes the rest.
A relayout from a metric change, a resize, or a graft then touches few elements, which
is what WebKit’s teardown cost asks for.

### Layout

`layoutTree` keeps its breadth-first, area-ordered nesting and changes in four ways:

- `minCellPx` becomes `paintMinPx`: the smallest painted cell, in CSS pixels, one device
  pixel (`1 / devicePixelRatio`) by default.
  Cells below it fold into the parent’s remainder, as today.

- `maxCells` becomes `maxPaintCells`, the cap on all cells; `maxLabelCells` caps the
  labelled ones, largest first.

- A folder too small for a header nests inside a frame whose width shrinks with depth,
  after the squarified paper (`⌈w·f^(l−1)⌉`), drawn only where the folder’s short side
  is at least 5 px, WinDirStat’s threshold; below it, its children tile the folder edge
  to edge. This replaces `frameNestMinPx` and the fixed `padPx` for unlabelled folders.

- For speed at tens of thousands of cells (see [Bounds to Measure](#bounds-to-measure)):
  the pending-folder choice becomes a binary heap, `cellTypography` runs only for
  labelled cells, and geometry goes into typed arrays (`x`, `y`, `w`, `h`, `parent`,
  `depth`, `node`) with an object only for labelled cells.

The output stays parent first, so painting in order draws children over their parents.

### Painting

- The canvas backing store is the viewport’s padding box times `devicePixelRatio`, with
  `setTransform(dpr, …)`, and every edge snapped to device pixels, so neighbours neither
  overlap nor leave hairline gaps.

- **Colors come from the stylesheet, not a second palette.** For each distinct
  `(palette key, ignored, pending, rest)` combination, a hidden probe element takes the
  classes and inline style a cell would get, and the map reads its computed
  `background-color` and `opacity`. The probes are reread when the color scheme or theme
  changes, so the canvas and the bars and legend beside it cannot disagree.

- A cell at least 3 device pixels on a side draws one device pixel short of its
  rectangle, as cells do now (`w - 1`); a smaller one draws edge to edge.

- Fills are grouped by color into one path each and filled once, which halves WebKit’s
  cost at 50k cells. No strokes: a separator is the gap the short fill leaves.

- A pending cell draws at the reduced-motion opacity; the pulse is not animated.

- The paint canvas repaints only on layout or a color change, never on hover.

### Hover

The shared hover (`DistributionHover`) keeps its contract with the bars and legend.

- **Family marks** (a legend entry): the hover canvas fills each marked cell with a
  lightened copy of its color, computed once per probe color as the lift
  `--viz-data-mark-hover-filter` gives a DOM mark, since `ctx.filter` is absent in
  WebKit.
- **Self mark** (the cell under the pointer): the same lift on one cell, plus the
  shimmer, animated on the hover canvas in `requestAnimationFrame` for the shimmer’s
  duration and not at all under `prefers-reduced-motion`.
- `docs/design-system.md`, “Folder Treemap”, is rewritten to describe this, since the
  lift is no longer a CSS rule on the cell.

### Hit Testing

After each layout the map builds a 16 px bucket grid over cell indexes: each bucket
lists the cells overlapping it, deepest last.
A point maps to the deepest cell in its bucket that contains it.

- `mousemove`, throttled to one lookup a frame, gives the tooltip, the self mark, and
  the cursor; `click` activates; the viewport owns both.
- The tooltip anchors to one transparent proxy element the map moves over the cell’s
  rectangle, since `mb.tooltip.show` anchors to an element.
- The grid and lookup live in a pure module, so their invariants (every interior point
  maps to the deepest cell containing it; a point in a gap maps to the parent) run
  browserlessly against the production code.

### Keyboard and Accessibility

The label layer keeps today’s roving tabindex: each labelled folder or file is a
`role="button"` with its accessible name, and the arrow keys, Enter, and Backspace work
as now. The focus ring is the label element’s outline.

Unlabelled cells are not focusable and have no name of their own: thousands of anonymous
rectangles are not a structure a keyboard or screen reader can use, and no surveyed tool
offers one.
Every unlabelled cell lies inside a labelled ancestor, or the outer box, that
is focusable and named, and Enter opens it, where its children are drawn large enough to
label. A folder’s accessible name gains its file count, so a reader hears how much is
inside before opening it.
Both canvases are `aria-hidden`.

### On-Demand Folders

The map takes an optional `expand(path)` option returning a promise of a rollup `node`.
After each layout, it collects **expansion candidates**: drawn folders whose node has
`children: null` and whose rectangle could hold at least `expandMinCells` cells (its
area over `paintMinPx²`), largest first.

- At most `expandConcurrency` requests are in flight, and at most `expandMaxGrafts`
  folders are grafted per tree.
- Each answer replaces the folder’s `children` and `rest` in the map’s copy of the tree,
  and the map lays out again, coalescing answers that arrive in the same frame into one
  layout.
- The view supplies `expand` with `mb.rollup(path, {depth: "max", top: "max"})` and the
  current Show ignored, so a graft is bounded by the same node budget as the root.
- Grafts are keyed by path and by the folder’s `(total_files, total_size, mtime)`. When
  the watch delivers a new root, the map regrafts each cached subtree whose folder is
  unchanged and drops the rest, so a refresh does not refetch every graft.
- A folder in `state: "pending"` is not expanded while its scan runs; a changed measure
  or Show ignored drops every graft.
- A failed or aborted graft leaves the folder solid; it is not retried until the next
  root. Disposal aborts every request in flight.

The compact map on the Overview takes `expand` too, with a lower `expandMaxGrafts`, so
the Overview does not cost the server what the Treemap view does.

### `top` and Flat Folders

`top=200` folds 351 of `tests/`’s files into its remainder however much room the folder
has. The node budget already bounds the response, so `ROLLUP_MAX_TOP` mainly limits flat
folders. Raise it to the largest value whose response stays within the payload and
server-time bounds measured in #723 (see the table beside `ROLLUP_MAX_NODES`), or to
`ROLLUP_MAX_NODES`, whichever the measurement supports.

Both are needed: on-demand folders fill in what the node budget left solid, and a higher
`top` fills in what one folder’s child cap folded away.

### Components

| File | Change |
| --- | --- |
| `treemap-layout.js` | `paintMinPx`, `maxPaintCells`, `maxLabelCells`, depth-thinned frames, the heap, typed-array geometry |
| `treemap-hit.js` (new, pure) | the bucket grid and point lookup |
| `treemap-paint.js` (new) | canvas sizing, probe colors, grouped fills, the hover canvas and shimmer |
| `treemap-map.js` | the three layers, label reconciliation by path, viewport pointer routing, the tooltip proxy, `expand` scheduling and grafts |
| `styles.css`, `docs/design-system.md` | the label layer’s styles; the hover lift rule moves to the hover canvas |
| `treemap.js`, `treemap-compact.js` | supply `expand` |
| `settings.py` | `ROLLUP_MAX_TOP`, from the measurement |

`treemap-paint.js` and `treemap-hit.js` load on demand with the folder plugin’s other
treemap modules, not in the shell’s eager path.

### API Changes

None to `/api/rollup`: `path` already selects a subtree.
`ROLLUP_MAX_TOP` may rise.
The map component’s options gain `expand`; it is internal to the folder plugin.

## Bounds to Measure

Per [rendering large content](../../../large-content-rendering.md), each bound is set
from a measurement in a real browser and recorded beside its constant.
Measured in Chrome and in the macOS app’s WKWebView, through the WebKit measurement gate
(`apps/macos/webkit-gate/run.mjs`, `make macos-webkit-gate`) with a treemap case added,
on this repository and on a synthetic tree of 100k files:

| Bound | Measures | Starting point |
| --- | --- | --- |
| `maxPaintCells` | layout ms and paint ms at 5k, 10k, 25k, 50k, 100k cells | the largest count whose layout plus paint stays near two frames; paint alone allows about 50k (Prior Art) |
| `maxLabelCells` | label reconciliation ms in WebKit when every label changes, at 200, 400, 800 | a few hundred |
| `paintMinPx` | visible distinction of 1, 2, and 3 device px cells | one device pixel |
| hover repaint | ms to fill the hover canvas for a family that marks every cell | under one frame |
| `expandConcurrency`, `expandMaxGrafts` | server ms and bytes per graft, total relayout ms with all grafts | 4 and 16; the Overview 4 |
| `expandMinCells` | how many grafted folders change what is visible | 64 |
| `ROLLUP_MAX_TOP` | payload bytes and server ms for `tests/` and a 5k-file flat folder | as above |

A first, rough reading of the layout alone, in Node on 2026-11-22, on a synthetic tree
of 120k files at 1223×587 with `minCellPx: 1`, best of 15 runs on a host at a load
average near 300: 1.8 ms at 1,600 cells, 18 ms at 5,000, 150 ms at 10,000 and 25,000,
200 ms at 50,000, 800 ms at 100,000. The load makes the absolute numbers unreliable, but
the growth is faster than linear, and a profile at 50k cells puts the time in
`emitLevel`, `squarify`, `cellTypography`, garbage collection, and `layoutTree`’s own
loop. So the layout changes before the bound is set:

- The pending-folder choice scans every pending folder for the largest (quadratic in
  folders); it becomes a binary heap.
- `cellTypography` runs only for labelled cells.
- Geometry goes into typed arrays, with an object only for labelled cells, to cut
  allocation.

The bound is then measured in the browser, where the layout runs, not in Node.

## Implementation Plan

Two stack layers, so the renderer can be reviewed, and land, before the data change.

### Phase 1: Canvas Cells (layer 4, `claude/treemap-canvas`)

- [ ] Layout: the heap, typed-array geometry, `paintMinPx`, `maxPaintCells`,
  `maxLabelCells`, depth-thinned frames, with vm tests: every cell inside its parent,
  labelled cells are the largest, bounds respected.
- [ ] `treemap-hit.js` with focused invariants: every interior point maps to the deepest
  cell containing it; a point in a gap maps to the parent.
- [ ] `treemap-paint.js`: sizing, probe colors, grouped fills, the hover canvas and
  shimmer.
- [ ] `treemap-map.js`: the three layers, label reconciliation, viewport routing, the
  tooltip proxy, disposal (canvases, listeners, probes, the theme listener, the
  shimmer’s frame).
- [ ] A treemap case in the WebKit gate; measure and set `maxPaintCells`,
  `maxLabelCells`, `paintMinPx`, and the hover repaint.
- [ ] Extend the containment Chrome test to every cell (geometry from the layout, pixels
  sampled at cell centers against the probe colors).
- [ ] Sessions and goldens (`cli-ui-treemap`, `cli-ui-treemap-compact`), parity rows,
  `docs/design-system.md` “Folder Treemap”, a changelog fragment.

### Phase 2: On-Demand Folders (layer 5, `claude/treemap-expand`)

- [ ] `expand` scheduling, grafts, regrafting on refresh, abort on dispose, with a
  browserless session that pins requests made, coalescing, and caps.
- [ ] The view and compact map supply `expand`.
- [ ] Measure and set the expansion bounds and `ROLLUP_MAX_TOP`.
- [ ] A golden for `/api/rollup?path=<subtree>&depth=max&top=max`, parity rows, docs, a
  changelog fragment.

## Testing Strategy

- **Browserless** (the parity rules in `AGENTS.md`): the layout, label reconciliation,
  hit testing, and expansion scheduling are pure or vm-harnessed JavaScript, so each has
  focused invariants and a golden session run against the production modules.

- **Chrome**: containment of every cell; the canvas paints the fill the probe resolved
  at sampled cell centers; a pointer over an unlabelled cell shows its tooltip, and a
  click opens it.

- **WebKit**: the gate’s treemap case times layout and paint in the app’s WKWebView,
  where a pair passes when WebKit is under 1.3 times Chrome, the gate’s own rule.

- **Parity exemption**: canvas pixels are paint, so the canvas itself is a named
  paint-only exemption whose evidence is the Chrome and WebKit checks above; everything
  the canvas shows comes from the layout the goldens pin.

## Rollout Plan

Ships with the treemap stack as one artifact: server, browser shell, and the folder
plugin change together, so no compatibility layer is owed.
A changelog fragment per layer says the map now draws every file down to a pixel and
fills in large folders after the first paint.

## Open Questions

- Should unlabelled cells be reachable by keyboard, through a focus proxy that walks
  them in layout order, or is opening the enclosing folder enough?
  This plan says opening the folder is enough.

- Should the Overview’s compact map expand folders at all, or stay one request?

- Cushion shading (van Wijk and van de Wetering) makes deep nesting readable without
  frames, at the cost of a second visual language beside the bars’ flat fills.
  Worth a separate experiment?

## References

- [Rendering large content](../../../large-content-rendering.md)
- [Parity Registry](../../architecture/arch-parity-registry.md)
- `docs/design-system.md`, “Folder Treemap”
- Beads: `mb-iirq` (this plan), under the epic `mb-bjsy`; `mb-3m31`, `mb-9xaz`,
  `mb-qb2x` (layers 1 to 3)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
