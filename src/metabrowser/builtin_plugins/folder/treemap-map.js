// Folder treemap map: the drawn cells of a rollup tree, at any size.
//
// One component behind both surfaces that draw a folder as a treemap: the
// Treemap view (treemap.js), which fills the pane, and the compact map under
// File Overview's type breakdown (treemap-compact.js). It owns the cells and
// everything a cell does — layout through treemap-layout.js, labels,
// tooltip, pointer and keyboard activation, and the hover the map shares
// with its tally bars and legend — and nothing about where the rollup comes
// from or what surrounds the map. Its host hands it a node and asks for a
// layout; the map measures its own drawable box.
//
// A compact map draws the same tree with smaller bounds: fewer cells, no
// value lines, and smaller label thresholds, since its cells are small and
// the tooltip carries every name.

import { buildHitGrid } from "./treemap-hit.js";
import {
  iconOnlyPx,
  labelIconGapPx,
  labelIconPx,
  labelIconRoomPx,
  layoutTree,
} from "./treemap-layout.js";
import { applyMarkOps, iconList, markOps, paintCells, paintList } from "./treemap-paint.js";

/** @typedef {{classFor: (key: string) => string, styleFor: (key: string) => string, paint: (element: HTMLElement, key: string) => void}} TreemapPalette */
/** @typedef {{metric: "size" | "files", includeIgnored: boolean}} TreemapState */
/** @typedef {import("./distribution-hover.js").DistributionHover} DistributionHover */
/** @typedef {import("./distribution-hover.js").DistributionHoverTarget} DistributionHoverTarget */

/**
 * Size presets. `layout` overrides LAYOUT_DEFAULTS (treemap-layout.js); the
 * label bounds are paint thresholds, since type size itself comes from cell
 * geometry.
 */
/**
 * The most cells a map lays out and paints. Measured in the app's browser pane
 * (Chrome) on 2026-11-23 with these modules on a synthetic tree of 120k files
 * at 1100 by 560 and a pixel ratio of 2, best of five, on a host at a load
 * average above 400: layout, paint list, paint, and hit grid together took
 * 11 ms at 5,000 cells, 19 ms at 10,000, 38 ms at 25,000, and 66 ms at 50,000,
 * the layout and the paint each about half. This repository's rollup, 4,000
 * nodes, lays out as 3,714 cells in 7 ms. 25,000 keeps a relayout near two
 * frames on a loaded host.
 *
 * In WebKit, by the WebKit gate's treemap case (apps/macos/webkit-gate/run.mjs,
 * treemap-100k) on 2026-11-23, 9 back-to-back pairs at load averages of 84 to
 * 165: the Treemap's own 32,000-node rollup of a 100,000-file folder, laid out
 * at 837 by 393 and a pixel ratio of 2, best of five, took 0.92 to 1.29 times
 * Chrome's time at every cap from 5,000 to 33,000 cells (medians 70 and 65 ms
 * at 25,000), so WebKit asks for no lower bound. That tree costs more a cell
 * than the one above, and the load leaves the two-frame budget unconfirmed in
 * either engine. A family hover's marks, then at most one op a cell, took 1.2 to
 * 2.0 times Chrome's (14 and 8 ms at 25,000); most of WebKit's was the palette
 * key drawCellHover looked up for every cell on every hover, not the cell count.
 * With each extension's key looked up once a layout (cellPaletteKey), a run of
 * 5 pairs that day at load averages of 70 to 150 passed every metric: the
 * hover's handler 3 ms in both engines, its frame work 0.81 to 0.85 times
 * Chrome's, the metric switch 1.01 to 1.21 times, and the layout at 25,000
 * cells 0.88 to 0.94 times (56 and 61 ms).
 * A marked nested folder now adds a second op, the clear of its interior
 * (markOps), so a hover makes at most a copy a cell and a clear a folder; that
 * count has not been measured again in either engine.
 */
export const PAINT_MAX_CELLS = 25_000;

/**
 * The most pixels one canvas holds: 4096 x 4096, the area WebKit allows a
 * canvas on iOS, its smallest; a viewport larger at its pixel ratio paints at
 * a lower ratio. A platform limit, not a cost: a full pane at twice its pixels
 * is near 8 million.
 */
const MAX_BACKING_PIXELS = 4096 * 4096;

/**
 * The widest a value's character draws, in ems: a cell shows its size only when the
 * whole of it fits, never cut off or wrapped. Measured in headless Chrome at 1400 by
 * 900 on 2026-11-23 with tabular numerals (.tm-cell-sub, styles.css) at 8 to 24 px,
 * sizes and counts such as "1023.9 MB" and "22,222 files" drew at most 0.472 em a
 * character in Source Sans 3, the app's face, and 0.61 em in system-ui, which the
 * System Fonts setting uses on macOS, at 8 px; the bound covers both.
 */
const VALUE_CHAR_EM = 0.62;

/** The gap before a nested folder's inline value (.tm-cell-title, styles.css). */
const FOLDER_TITLE_GAP_PX = 6;

// The label bounds hold the smallest label, at labelMinPx (treemap-layout.js), inside
// its cell. Measured in Chrome at 1400 by 900 on this repository (2026-11-23): a 9 px
// label's title box is 10.8 px tall. A cell's box is 1 px smaller than its cell
// (boxStyle), and its padding is 2px 5px in the full map, 1px 4px in the compact one
// (styles.css), so the title fits below 14 px and 13 px. At 40 px and 32 px wide, 29 px
// and 23 px of text show about five and four characters before the ellipsis.
const SIZE_PRESETS = Object.freeze({
  full: Object.freeze({
    layout: Object.freeze({ maxCells: PAINT_MAX_CELLS }),
    labelMinW: 40,
    labelMinH: 14,
    padX: 5,
    values: true,
    restLabels: true,
  }),
  // The same cell cap: the smaller box already culls by geometry, and a
  // lower cap only turned files that had room into remainder cells. The
  // compact cell's padding is smaller, so its label bounds are lower.
  compact: Object.freeze({
    layout: Object.freeze({ maxCells: PAINT_MAX_CELLS }),
    labelMinW: 32,
    labelMinH: 13,
    padX: 4,
    values: false,
    restLabels: false,
  }),
});

/** The Treemap view, which a map cell opens at its folder (treemap.js registers it). */
export const TREEMAP_VIEW_ID = "treemap";

/**
 * The palette key of a nested folder, whose header and frame are drawn neutral
 * (mb-lzmo). No legend entry or tally segment has it, since the taxonomy's keys
 * are a family's `family:` key, an extension, or the remainder's "", so a
 * family hover never marks a nested folder and hovering one marks no entry.
 */
const NESTED_FOLDER_KEY = "folder:nested";

/** What a map shows while its tree is on its way. */
export const TREEMAP_LOADING_HTML =
  '<div class="tm-loading mb-delayed-loading" aria-hidden="true"></div><span class="sr-only">Loading treemap…</span>';

/**
 * The rollup the Overview's compact map requests: the deepest tree the server
 * returns, with the most children per folder (the route resolves "max" to
 * ROLLUP_MAX_DEPTH and ROLLUP_MAX_TOP, settings.py), and the tallies a legend
 * reads. The route's default node budget, not these, bounds the response, and
 * the layout folds whatever has no room into remainder cells. A map of a few
 * hundred pixels draws no more than that budget holds.
 * @returns {{ext_rank: "dual", depth: "max", top: "max"}}
 */
export function treemapRollupQuery() {
  return { ext_rank: "dual", depth: "max", top: "max" };
}

/**
 * The rollup the Treemap view requests: the compact map's, at the route's
 * largest node budget (ROLLUP_MAX_NODES), in the compact encoding that carries a
 * file as one positional entry (treemap-rollup-decode.js), and with gitignored
 * nodes left out while Show ignored is off, so the budget goes to the nodes the
 * map draws. Leaving them out changes which nodes are emitted, never a total, a
 * tally, or a folder's dominant type.
 * @param {boolean} includeIgnored  Show ignored
 * @returns {{ext_rank: "dual", depth: "max", top: "max", nodes: "max", encoding: "compact", ignored: "include" | "exclude"}}
 */
export function treemapFullRollupQuery(includeIgnored) {
  return {
    ...treemapRollupQuery(),
    nodes: "max",
    encoding: "compact",
    ignored: includeIgnored ? "include" : "exclude",
  };
}

/**
 * The index has stopped, and has said all it will about this folder.
 * @param {Record<string, any> | null} snapshot
 * @returns {boolean}
 */
export function isCompleteSnapshot(snapshot) {
  return (
    (snapshot?.index_status === "done" || snapshot?.index_status === "truncated") &&
    snapshot.node?.state !== "pending"
  );
}

/**
 * What a map's host shows for a rollup snapshot: the map; its skeleton while
 * the tree is on its way; or nothing, since nothing is coming, when the index
 * failed, finished without this folder, or stopped at its cap before finishing
 * it, or the last request failed with no map to keep.
 * @param {Record<string, any> | null} snapshot
 * @param {boolean} failed  the last request failed
 * @returns {"map" | "loading" | "unavailable"}
 */
export function treemapAvailability(snapshot, failed) {
  const terminal = isCompleteSnapshot(snapshot);
  if (terminal && snapshot?.node) {
    return "map";
  }
  if (
    failed ||
    snapshot?.index_status === "failed" ||
    terminal ||
    (snapshot?.index_status === "truncated" && snapshot?.node?.state === "pending")
  ) {
    return "unavailable";
  }
  return "loading";
}

/** Keep a complete map visible while a new snapshot is still being assembled.
 * @param {Record<string, any> | null} previous
 * @param {Record<string, any> | null} next
 */
export function retainTreemap(previous, next) {
  return (
    treemapAvailability(previous, false) === "map" && treemapAvailability(next, false) === "loading"
  );
}

/**
 * The folder as a map's one top-level cell: an outer box, labelled with the
 * folder's name, around everything in it. The Treemap view and the Overview's
 * compact map both draw it, so the two maps of one folder match. On the compact
 * map a click on its frame opens the Treemap view at the folder (mb-olmt); the
 * view is already there, so it opens nothing (mb-85bh). Its totals are the
 * folder's, so every share inside is what it would be without the box.
 * @param {Record<string, any>} node
 * @returns {Record<string, any>}
 */
export function withOuterBox(node) {
  return { ...node, children: [node], rest: null };
}

/**
 * @typedef {object} TreemapMapOptions
 * @property {"full" | "compact"} [size]
 * @property {() => TreemapState} getState
 * @property {(cell: Record<string, any>) => void} onActivate  a folder or file cell was chosen
 * @property {DistributionHover} [hover]  the hover the map shares with its bars and legend
 * @property {() => void} [onParent]  Backspace asks for the enclosing folder
 * @property {(cell: Record<string, any>) => boolean} [opens]  whether activating a folder
 *   or file cell opens anything; a cell that does not is no button and shows no pointer
 */

/**
 * What a mounted map shows, for the browserless sessions, which have no canvas
 * to read: the layout, what is painted, labelled, focused, and marked.
 * @typedef {object} TreemapInspection
 * @property {ReadonlyArray<Record<string, any>>} cells
 * @property {ReadonlyArray<import("./treemap-paint.js").PaintRect>} paint
 * @property {number} empty  cells whose snapped rectangle is empty, painted nowhere
 * @property {ReadonlyArray<number>} labels  indexes of the labelled cells
 * @property {ReadonlyArray<{cell: number, px: number}>} icons  the cells that show their
 *   icon alone, painted on the icons canvas, and the glyph's size in CSS pixels
 * @property {ReadonlyArray<import("./treemap-paint.js").IconRect>} iconRects  where those
 *   icons are drawn, in device pixels (iconList)
 * @property {ReadonlyArray<{cell: number, px: number, alone: boolean}>} glyphs  every
 *   drawn icon's glyph size, over its name or alone
 * @property {ReadonlyArray<number>} focusOrder  indexes the focus proxy walks
 * @property {number} focused  index of the cell the focus proxy is on, or -1
 * @property {number} hovered  index of the cell under the pointer, or -1
 * @property {ReadonlyArray<number>} marked  indexes the hover marks
 * @property {ReadonlyArray<import("./treemap-paint.js").MarkOp>} markOps
 * @property {Readonly<Record<string, import("./treemap-paint.js").PaintStyle>>} styles  the
 *   colors each style key resolved to from its probe, as last painted
 * @property {number} dpr
 */

/** @type {WeakMap<HTMLElement, () => TreemapInspection>} */
const INSPECTORS = new WeakMap();

/**
 * What the map mounted on `viewport` shows, or null when none is. A read, for the
 * sessions; nothing in the app calls it.
 * @param {HTMLElement} viewport
 * @returns {TreemapInspection | null}
 */
export function inspectTreemap(viewport) {
  return INSPECTORS.get(viewport)?.() ?? null;
}

/**
 * Mount a treemap map on `viewport`, which the map fills with its layers.
 *
 * Layers, bottom to top (docs/design-system.md, "Folder Treemap"): the paint
 * canvas, every cell's fill and edge; two marks canvases, copies of the marked
 * cells' pixels under the lift filter, one fading in as the other fades out; the
 * icons canvas, the icons of the cells too small for their names; the hover anchor,
 * a transparent cell
 * over the cell under the pointer, which carries the shimmer and anchors the
 * tooltip; the labels, text only; and the focus proxy, the one focusable control,
 * which the arrow keys move over every folder and file cell. The viewport takes
 * every pointer event and asks the hit grid which cell is under it, since a
 * canvas says nothing about what is painted on it.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {TreemapPalette} palette
 * @param {HTMLElement} viewport
 * @param {TreemapMapOptions} options
 */
export function createTreemapMap(mb, palette, viewport, options) {
  const preset = SIZE_PRESETS[options.size ?? "full"];
  const hover = options.hover ?? null;
  const doc = viewport.ownerDocument ?? document;
  const win = doc.defaultView ?? (typeof window === "undefined" ? null : window);
  /** @type {Record<string, any>[]} */
  let cells = [];
  /**
   * Each cell's palette key, which changes only with a layout. A family hover reads
   * every cell's; looked up again on each hover, it was most of the hover's cost in
   * WebKit (PAINT_MAX_CELLS, beside the measurement).
   * @type {string[]}
   */
  let paletteKeys = [];
  /**
   * The palette key of each extension in the layout, looked up once a layout: a map
   * holds tens of extensions among its thousands of cells, and the lookup was most of
   * a family hover's cost in WebKit (PAINT_MAX_CELLS, beside the measurement). Cleared
   * at each layout, so a registry that changed is read again.
   * @type {Map<string, string>}
   */
  const extensionKeys = new Map();
  /** @type {import("./treemap-paint.js").PaintRect[]} */
  let paintRects = [];
  let emptyCells = 0;
  /** @type {number[]} */
  let actionableIndexes = [];
  /** @type {Map<number, string>} the remainder phrase a folder's name carries */
  let remainderNotes = new Map();
  let focusPos = 0;
  let disposed = false;
  /** @type {import("./treemap-hit.js").HitGrid | null} */
  let hitGrid = null;
  /** @type {{w: number, h: number}} */
  let laidOutBox = { w: 0, h: 0 };
  let dpr = devicePixelRatio();
  /** The last node and content drawn, which a pixel-ratio or theme change draws again. */
  /** @type {{node: Record<string, any> | null, content: {placeholderHtml?: string, emptyHtml?: string}} | null} */
  let lastRender = null;
  /**
   * The pointer's last client position while it is over the map. The viewport
   * can move under a still pointer (the legend's row wrapping above it), so a
   * lookup measures the viewport again rather than keeping a position in it.
   */
  /** @type {{clientX: number, clientY: number} | null} */
  let pointer = null;
  let pointerFrame = 0;
  let hoveredIndex = -1;
  /** @type {number[]} */
  let markedIndexes = [];
  /** @type {import("./treemap-paint.js").MarkOp[]} */
  let currentMarkOps = [];
  /** Where the icons drawn alone go (iconList), and what draws them (paintIcons). */
  /** @type {import("./treemap-paint.js").IconRect[]} */
  let iconRects = [];
  /**
   * Each icon rect's icon, looked up once a layout rather than on every paint.
   * @type {Array<{svg: string, className: string}>}
   */
  let iconOfRect = [];
  /**
   * Each icon rasterized once for each size and color it is drawn at, so a map of
   * thousands of icons draws a few dozen images; cleared with the theme.
   *
   * A sprite is drawn from a bitmap of its SVG image, not the image: Chrome renders an
   * SVG image again on every draw. Measured in headless Chrome on 2026-11-23 at a load
   * average near 240, five runs each, drawing 2,500 and 25,000 icons of 8 to 16 px on a
   * 2800 by 1800 canvas took 17.5 and 170 ms from the SVG images, 18 to 31 and 66 to 84
   * ms from canvases, and 4.4 and 39 ms from ImageBitmaps, about what the layout and
   * paint of 25,000 cells take together (PAINT_MAX_CELLS).
   * @type {Map<string, {image: HTMLImageElement, bitmap: CanvasImageSource | null}>}
   */
  const iconSprites = new Map();
  /** @type {Map<string, string>} each icon class's color, read from a probe */
  const iconColors = new Map();
  let iconFrame = 0;
  /** The marks canvas shown (layers.marks), and the cells it marks. */
  let shownMarks = 0;
  /** @type {number[]} */
  let shownMarked = [];
  /** The cells the canvas fading out marks, while it fades. */
  /** @type {number[]} */
  let fadingMarked = [];
  /** The hover the cell under the pointer entered, until the pointer leaves the cell. */
  /** @type {DistributionHoverTarget | null} */
  let cellHover = null;
  /** @type {Map<string, PaintStyle>} */
  const styleCache = new Map();
  /**
   * What each style key stands for. A key is a JSON array, so a family key may
   * hold any character, a `|` an extension keeps among them, and still read back.
   * @type {Map<string, {paletteKey: string, rest: boolean, ignored: boolean, pending: boolean}>}
   */
  const styleParts = new Map();

  /** @typedef {import("./treemap-paint.js").PaintStyle} PaintStyle */

  /** @returns {number} */
  function devicePixelRatio() {
    const ratio = Number(win?.devicePixelRatio);
    return Number.isFinite(ratio) && ratio > 0 ? ratio : 1;
  }

  // ---- Layers ----------------------------------------------------------------

  /** @type {Record<string, any> | null} */
  let layers = null;

  /** The layers, made once and put back whenever a placeholder replaced them. */
  function ensureLayers() {
    if (layers && viewport.contains(layers.paint)) {
      return layers;
    }
    viewport.innerHTML = "";
    const paint = doc.createElement("canvas");
    paint.className = "tm-paint";
    paint.setAttribute("aria-hidden", "true");
    // Two marks canvases, so a hover that moves from one cell to the next fades
    // the old lift out as the new one fades in (drawCellHover).
    const marks = [0, 1].map(() => {
      const canvas = doc.createElement("canvas");
      canvas.className = "tm-marks";
      canvas.setAttribute("aria-hidden", "true");
      return canvas;
    });
    // The icons the cells too small for their names show alone, drawn on a canvas, as
    // the cells are: a map can hold as many such icons as cells (paintIcons).
    const icons = doc.createElement("canvas");
    icons.className = "tm-icons";
    icons.setAttribute("aria-hidden", "true");
    const labels = doc.createElement("div");
    labels.className = "tm-labels";
    labels.setAttribute("aria-hidden", "true");
    const focus = doc.createElement("div");
    focus.className = "tm-focus";
    focus.setAttribute("role", "button");
    focus.setAttribute("tabindex", "0");
    focus.hidden = true;
    const probes = doc.createElement("div");
    probes.className = "tm-probes";
    probes.setAttribute("aria-hidden", "true");
    for (const element of [paint, ...marks, icons, labels, focus, probes]) {
      viewport.appendChild(element);
    }
    // New canvases show nothing, so the next hover draws on one and shows it.
    shownMarks = 0;
    shownMarked = [];
    layers = {
      paint,
      marks,
      icons,
      labels,
      focus,
      probes,
      /** @type {HTMLElement | null} */
      anchor: null,
      /** @type {Map<string, HTMLElement>} */
      labelElements: new Map(),
    };
    return layers;
  }

  /** Let go of the layers, as a placeholder takes the viewport. */
  function dropLayers() {
    if (layers) {
      zeroCanvas(layers.paint);
      zeroCanvas(layers.icons);
      for (const canvas of layers.marks) {
        zeroCanvas(canvas);
      }
    }
    layers = null;
  }

  /** @param {HTMLCanvasElement} canvas */
  function zeroCanvas(canvas) {
    canvas.width = 0;
    canvas.height = 0;
  }

  // ---- Cells -----------------------------------------------------------------

  /**
   * The distribution key for a cell: the family behind a file's extension, and
   * the neutral fallback for the remainder cell that stands for what did not
   * fit. A folder whose contents are drawn inside it takes NESTED_FOLDER_KEY:
   * its header and frame are chrome around many types, not one of them. A folder
   * drawn as one solid cell keeps its dominant type's.
   * @param {Record<string, any>} cell
   * @returns {string}
   */
  function cellPaletteKey(cell) {
    if (cell.kind === "rest") {
      return "";
    }
    if (cell.kind === "dir" && cell.nested) {
      return NESTED_FOLDER_KEY;
    }
    return extensionKey(cell.ext || "(none)");
  }

  /**
   * The palette key of an extension, the family that colors it, looked up once a layout.
   * @param {string} extension
   */
  function extensionKey(extension) {
    let key = extensionKeys.get(extension);
    if (key === undefined) {
      key = mb.fileTypes.distributionKeyForExtension(extension);
      extensionKeys.set(extension, key);
    }
    return key;
  }

  /**
   * A folder or file cell opens something, unless its host says it does not.
   * @param {Record<string, any>} cell
   * @returns {boolean}
   */
  function cellIsActionable(cell) {
    return (cell.kind === "dir" || cell.kind === "file") && (options.opens?.(cell) ?? true);
  }

  /**
   * The style a cell paints in: its family, and whether it is dimmed as
   * ignored, scanning, or the remainder. Cells that share one share a probe.
   * @param {Record<string, any>} cell
   * @returns {string}
   */
  function cellStyleKey(cell) {
    const state = options.getState();
    const parts = {
      paletteKey: cellPaletteKey(cell),
      rest: cell.kind === "rest",
      ignored: Boolean(cell.gitignored && state.includeIgnored),
      pending: cell.state === "pending",
    };
    const key = JSON.stringify([parts.paletteKey, parts.rest, parts.ignored, parts.pending]);
    if (!styleParts.has(key)) {
      styleParts.set(key, parts);
    }
    return key;
  }

  /**
   * The colors a style key paints in, read from a probe element styled as a
   * cell of that style would be, so the canvas follows the stylesheet and the
   * palette the bars and legend use, in either theme.
   * @param {string} key
   * @returns {PaintStyle}
   */
  function resolveStyle(key) {
    const cached = styleCache.get(key);
    if (cached) {
      return cached;
    }
    const { paletteKey, rest, ignored, pending } = styleParts.get(key) ?? {
      paletteKey: "",
      rest: true,
      ignored: false,
      pending: false,
    };
    const probe = doc.createElement("div");
    // A nested folder takes no palette class, so .tm-type-fill falls back to
    // the neutral border tone (styles.css, .tm-nested-folder).
    const nestedFolder = paletteKey === NESTED_FOLDER_KEY;
    probe.className = [
      "tm-cell",
      "tm-type-fill",
      rest ? "tm-rest" : nestedFolder ? "tm-nested-folder" : "tm-file",
      nestedFolder ? "" : palette.classFor(paletteKey),
      ignored ? "tm-ignored" : "",
      pending ? "tm-pending-still" : "",
    ]
      .filter(Boolean)
      .join(" ");
    const styleText = nestedFolder ? "" : palette.styleFor(paletteKey);
    if (styleText) {
      probe.setAttribute("style", styleText);
    }
    const edge = doc.createElement("div");
    edge.className = "tm-probe-edge";
    probe.appendChild(edge);
    const host = ensureLayers().probes;
    host.appendChild(probe);
    const computed = win?.getComputedStyle?.(probe);
    const edgeComputed = win?.getComputedStyle?.(edge);
    const alpha = Number.parseFloat(computed?.opacity ?? "1");
    const style = Object.freeze({
      fill: computed?.backgroundColor || "transparent",
      edge: edgeComputed?.backgroundColor || computed?.backgroundColor || "transparent",
      alpha: Number.isFinite(alpha) ? alpha : 1,
    });
    probe.remove();
    styleCache.set(key, style);
    return style;
  }

  /** The surface under every cell, the viewport's own: what shows between top-level cells. */
  function surfaceColor() {
    return win?.getComputedStyle?.(viewport)?.backgroundColor || "transparent";
  }

  /**
   * Value phrase for a cell: aggregate cells follow the active metric;
   * file leaves retain their more useful byte size in both modes.
   * @param {Record<string, any>} cell
   * @param {TreemapState} state
   * @returns {string}
   */
  function cellValueText(cell, state) {
    // One file is already obvious from a leaf rectangle. Its byte size
    // remains useful in either area mode; folders and remainder cells
    // report the active metric because their count is aggregate data.
    if (cell.kind === "file") {
      return mb.formatSize(cell.bytes ?? cell.value);
    }
    if (state.metric === "files") {
      return mb.formatFileCount(cell.files ?? cell.value);
    }
    return mb.formatSize(cell.bytes ?? cell.value);
  }

  /**
   * The focus proxy's name for a cell. A folder's names what its remainder
   * holds, since the remainder has no control of its own.
   * @param {number} index
   * @param {TreemapState} state
   * @returns {string}
   */
  function cellAriaLabel(index, state) {
    const cell = cells[index];
    const what = cell.kind === "dir" ? "folder" : "file";
    const note = remainderNotes.get(index);
    return `${cell.name} (${what}, ${cellValueText(cell, state)}${note ? `, ${note}` : ""})`;
  }

  /**
   * Whether a cell draws its label, and which lines: its name, a file's icon over it,
   * and its size where the whole of it fits.
   * @param {Record<string, any>} cell
   */
  function labelPlan(cell) {
    const labelLineHeight = cell.labelPx * 1.2;
    const valueLineHeight = cell.valuePx * 1.2;
    // A file's name sits under its icon, which with its gap is sized to the name
    // (labelIconRoomPx): a file shows both when its cell has room for the name's
    // smallest width and both lines, and its name ellipsizes in the width it has. A file
    // without that room shows its icon alone, so cells of one size draw alike.
    const icon = cell.kind === "file";
    const iconRoom = icon ? labelIconRoomPx(cell.labelPx) : 0;
    const titleHeight = Math.max(preset.labelMinH, labelLineHeight + 2) + iconRoom;
    // A framed folder's children cover its whole interior, so it has no
    // room for a label; the tooltip names it.
    const showLabel =
      !cell.framed &&
      (preset.restLabels || cell.kind !== "rest") &&
      cell.w >= preset.labelMinW &&
      cell.h >= titleHeight;
    // A size shows only whole: its line needs the height, and its text the width
    // (VALUE_CHAR_EM), past the cell's padding.
    const room = Math.max(0, cell.w - 1 - 2 * preset.padX);
    const valueWidth =
      preset.values && showLabel && cell.kind !== "rest"
        ? cellValueText(cell, options.getState()).length * cell.valuePx * VALUE_CHAR_EM
        : Infinity;
    // Nested parents suppress the sublabel: the reserved header strip
    // is one line tall, and a second line would overlap child cells.
    const stacked =
      preset.values &&
      showLabel &&
      cell.h >= titleHeight + valueLineHeight + 4 &&
      valueWidth <= room &&
      cell.kind !== "rest" &&
      !cell.nested;
    // Beside a nested folder's name, its size keeps its width and the name gives way,
    // keeping the smallest label's width (.tm-cell-sub-inline, styles.css).
    const inline =
      preset.values &&
      showLabel &&
      cell.nested &&
      cell.kind === "dir" &&
      valueWidth + FOLDER_TITLE_GAP_PX + preset.labelMinW - 2 * preset.padX <= room;
    // Too small for its name and icon, a file shows its icon alone, sized to its cell
    // (iconOnlyPx). A folder has no icon, as in the navigation, where its row leads with
    // its chevron (docs/design-system-icons.md).
    const iconOnlyGlyph =
      !showLabel && icon ? iconOnlyPx({ w: cell.w, h: cell.h }, cell.labelPx) : 0;
    return {
      showLabel,
      stacked,
      inline,
      icon: showLabel && icon,
      iconPx: showLabel && icon ? labelIconPx(cell.labelPx) : iconOnlyGlyph,
      iconOnly: iconOnlyGlyph > 0,
    };
  }

  /**
   * A file cell's icon as the navigation draws it, its file type's, at `glyphPx` when the
   * map sizes it to its cell, or at the navigation's own size. A folder has none, as its
   * row in the navigation has none.
   * @param {Record<string, any>} cell
   * @param {string} [extraClass]
   * @param {number} [glyphPx]
   */
  function cellIconHtml(cell, extraClass, glyphPx) {
    const icon = cellIcon(cell);
    if (!icon.svg) {
      return "";
    }
    const cls = ["file-identity-icon", extraClass || "", icon.className].filter(Boolean).join(" ");
    const size = glyphPx ? ` style="--icon-glyph:${glyphPx}px;--icon-box:${glyphPx}px"` : "";
    return `<span class="${mb.escapeHtml(cls)}"${size} aria-hidden="true">${icon.svg}</span>`;
  }

  /**
   * A labelled cell's text, the markup the DOM cells drew inside themselves.
   * @param {Record<string, any>} cell
   * @param {TreemapState} state
   * @param {{stacked: boolean, inline: boolean, icon: boolean, iconPx: number}} plan
   */
  function labelInnerHtml(cell, state, plan) {
    const sub = cellValueText(cell, state);
    const visibleName = cell.kind === "dir" ? `${cell.name}/` : cell.name;
    const fileIconHtml = plan.icon ? cellIconHtml(cell, "tm-cell-file-icon", plan.iconPx) : "";
    return `<span class="tm-cell-title">${fileIconHtml}<span class="tm-cell-label">${mb.escapeHtml(visibleName)}</span>${
      plan.inline ? `<span class="tm-cell-sub tm-cell-sub-inline">${mb.escapeHtml(sub)}</span>` : ""
    }</span>${plan.stacked ? `<span class="tm-cell-sub">${mb.escapeHtml(sub)}</span>` : ""}`;
  }

  /**
   * Classes a labelled cell's text element takes: the cell's own, so type and
   * color follow the rules the cells always had, without its fill.
   * @param {Record<string, any>} cell
   * @param {TreemapState} state
   */
  function labelClasses(cell, state) {
    const cls = ["tm-cell", "tm-label-cell", `tm-${cell.kind}`];
    if (cell.gitignored && state.includeIgnored) {
      cls.push("tm-ignored");
    }
    if (cell.nested) {
      cls.push("tm-nested");
    }
    return cls.join(" ");
  }

  /** @param {Readonly<Record<string, any>>} rect  x, y, w, and h in CSS pixels */
  function boxStyle(rect) {
    return (
      `left:${rect.x.toFixed(1)}px;top:${rect.y.toFixed(1)}px;` +
      `width:${Math.max(0, rect.w - 1).toFixed(1)}px;height:${Math.max(0, rect.h - 1).toFixed(1)}px;`
    );
  }

  /**
   * Bring the label layer to the layout: keep, move, and retext the labels of
   * cells still labelled, add the new ones, and remove the rest, keyed by kind
   * and path, since a remainder shares its folder's path. Removing many
   * elements at once is slow in WebKit (research-2026-11-22-dense-treemap-rendering.md),
   * so a relayout touches only what changed.
   * @param {TreemapState} state
   * @returns {number[]} indexes of the labelled cells
   */
  function reconcileLabels(state) {
    const { labels, labelElements } = ensureLayers();
    /** @type {number[]} */
    const labelled = [];
    const seen = new Set();
    for (let i = 0; i < cells.length; i += 1) {
      const cell = cells[i];
      const plan = labelPlan(cell);
      if (!plan.showLabel) {
        continue;
      }
      labelled.push(i);
      const key = `${cell.kind}\u0000${cell.path}`;
      seen.add(key);
      let element = labelElements.get(key);
      if (!element) {
        element = doc.createElement("div");
        labels.appendChild(element);
        labelElements.set(key, element);
      }
      const className = labelClasses(cell, state);
      if (element.className !== className) {
        element.className = className;
      }
      const style = `${boxStyle(cell)}--tm-label-size:${cell.labelPx}px;--tm-value-size:${cell.valuePx}px;--tm-title-gap:${labelIconGapPx(cell.labelPx)}px;`;
      if (element.getAttribute("style") !== style) {
        element.setAttribute("style", style);
      }
      const html = labelInnerHtml(cell, state, plan);
      if (element.dataset.tmHtml !== html) {
        element.innerHTML = html;
        element.dataset.tmHtml = html;
      }
      element.dataset.tmCell = String(i);
    }
    for (const [key, element] of labelElements) {
      if (!seen.has(key)) {
        element.remove();
        labelElements.delete(key);
      }
    }
    return labelled;
  }

  /**
   * The tooltip, in the navigation's terms (docs/design-system.md, "Folder Treemap"):
   * the cell's icon and path, then its size and file count as the navigation's columns
   * write them, in their hues, and its age with its freshness class.
   * @param {Record<string, any>} cell
   * @param {TreemapState} state
   * @returns {string}
   */
  function tooltipHtml(cell, state) {
    /** @param {number} n */
    const count = (n) =>
      `<span class="${`count ${mb.countClass(n)}`.trim()}">${mb.escapeHtml(mb.formatFileCount(n))}</span>`;
    /** @param {string} html */
    const detail = (html) => `<div class="tip-detail">${html}</div>`;
    if (cell.kind === "rest") {
      return (
        `<div class="tip-name">${count(cell.files || 0)} in the remainder</div>` +
        detail(state.metric === "files" ? count(cell.files || 0) : mb.sizeHtml(cell.bytes || 0))
      );
    }
    const pathLabel =
      window.MetabrowserNavigationRoute?.displayPath?.(cell.path || "", mb.sourceKind()) ||
      cell.path ||
      cell.name;
    const rows = [
      `<div class="tip-name tm-tip-name">${cellIconHtml(cell, "tm-tip-icon")}<span>${mb.escapeHtml(pathLabel)}</span></div>`,
      detail(
        cell.kind === "dir"
          ? `${count(cell.files || 0)} · ${mb.sizeHtml(cell.bytes || 0)}`
          : mb.sizeHtml(cell.bytes || 0),
      ),
    ];
    const age =
      typeof cell.mtime === "number" ? mb.ageLabelHtml(cell.mtime, { style: "relative" }) : "";
    if (age !== "") {
      rows.push(detail(`modified ${age}`));
    }
    if (cell.gitignored) {
      rows.push(detail("gitignored"));
    }
    if (cell.state === "pending") {
      rows.push(detail("still scanning"));
    }
    return rows.join("");
  }

  /**
   * The box cells are laid out in: the viewport's padding box, inside its
   * border, which is what absolutely positioned layers are placed against.
   * The border box is larger by the border, and laying out to it pushed
   * every right- and bottom-edge cell under the viewport's clipping edge.
   * A host without layout metrics (the vm harness) falls back to the
   * bounding rectangle, or to no box at all.
   * @returns {{w: number, h: number}}
   */
  function drawableBox() {
    if (typeof viewport.getBoundingClientRect !== "function") {
      return { w: 0, h: 0 };
    }
    const rect = viewport.getBoundingClientRect();
    const clientW = Number(viewport.clientWidth);
    const clientH = Number(viewport.clientHeight);
    return {
      w: Number.isFinite(clientW) && clientW > 0 ? clientW : rect.width,
      h: Number.isFinite(clientH) && clientH > 0 ? clientH : rect.height,
    };
  }

  // ---- Painting --------------------------------------------------------------

  /**
   * Size a canvas to the box in device pixels and return its 2D context, or
   * null where there is none (the vm harness).
   * @param {HTMLCanvasElement} canvas
   * @param {{w: number, h: number}} box
   * @returns {CanvasRenderingContext2D | null}
   */
  function sizeCanvas(canvas, box) {
    const width = Math.round(box.w * dpr);
    const height = Math.round(box.h * dpr);
    if (canvas.width !== width) {
      canvas.width = width;
    }
    if (canvas.height !== height) {
      canvas.height = height;
    }
    // The CSS size is the backing store's, so each backing pixel is one device
    // pixel at a fractional ratio too, and no edge is resampled.
    canvas.style.width = `${width / dpr}px`;
    canvas.style.height = `${height / dpr}px`;
    return typeof canvas.getContext === "function" ? canvas.getContext("2d") : null;
  }

  function paintMap() {
    const { paint } = ensureLayers();
    const ctx = sizeCanvas(paint, laidOutBox);
    if (!ctx) {
      return;
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    // An opaque surface first, so a translucent cell's pixels are what a mark copies.
    ctx.fillStyle = surfaceColor();
    ctx.fillRect(0, 0, paint.width, paint.height);
    paintCells(ctx, paintRects, resolveStyle);
  }

  // ---- Icons -----------------------------------------------------------------

  /**
   * The color an icon of `className` is drawn in, read from a probe styled as the
   * navigation's icon is, so the canvas follows the stylesheet in either theme.
   * @param {string} className
   */
  function iconColor(className) {
    const cached = iconColors.get(className);
    if (cached) {
      return cached;
    }
    const probe = doc.createElement("span");
    probe.className = ["file-identity-icon", className].filter(Boolean).join(" ");
    ensureLayers().probes.appendChild(probe);
    const color = win?.getComputedStyle?.(probe)?.color || "currentColor";
    probe.remove();
    iconColors.set(className, color);
    return color;
  }

  /**
   * A cell's icon: a file's is its type's, and a folder or remainder has none.
   * @param {Record<string, any>} cell
   * @returns {{svg: string, className: string}}
   */
  function cellIcon(cell) {
    return cell.kind === "file" ? mb.fileTypeIcon(cell.name) : { svg: "", className: "" };
  }

  /**
   * The image of an icon at `size` device pixels, made on first use; null where there
   * are no images (the vm harness) or there is no icon.
   * @param {{svg: string, className: string}} icon
   * @param {number} size
   */
  function iconSprite(icon, size) {
    if (!icon.svg || typeof win?.Image !== "function") {
      return null;
    }
    const color = iconColor(icon.className);
    const key = `${size}\u0000${color}\u0000${icon.svg}`;
    let sprite = iconSprites.get(key);
    if (!sprite) {
      const image = new win.Image();
      /** @type {{image: HTMLImageElement, bitmap: CanvasImageSource | null}} */
      const made = { image, bitmap: null };
      sprite = made;
      iconSprites.set(key, made);
      // The registry's glyph, given a size and a color: its strokes are currentColor, and
      // an image's SVG reads no stylesheet. Parsed as HTML it is an SVG element, which
      // serializes with its namespace, as an image needs.
      const holder = doc.createElement("div");
      holder.innerHTML = icon.svg;
      const glyph = holder.firstElementChild;
      if (!glyph || typeof win.XMLSerializer !== "function") {
        iconSprites.delete(key);
        return null;
      }
      glyph.setAttribute("width", String(size));
      glyph.setAttribute("height", String(size));
      glyph.setAttribute("style", `color:${color}`);
      const svg = new win.XMLSerializer().serializeToString(glyph);
      image.addEventListener("load", () => {
        const ready = (/** @type {CanvasImageSource} */ bitmap) => {
          // A sprite let go while it loaded (dropIconSprites) keeps nothing.
          if (iconSprites.get(key) !== made || disposed) {
            const loaded = /** @type {any} */ (bitmap);
            if (loaded !== image && typeof loaded.close === "function") {
              loaded.close();
            }
            return;
          }
          made.bitmap = bitmap;
          scheduleIconPaint();
        };
        if (typeof win.createImageBitmap === "function") {
          win.createImageBitmap(image).then(ready, () => ready(image));
        } else {
          ready(image);
        }
      });
      image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
    }
    return sprite;
  }

  /** Let go of every sprite, closing its bitmap. */
  function dropIconSprites() {
    for (const sprite of iconSprites.values()) {
      const bitmap = /** @type {any} */ (sprite.bitmap);
      if (bitmap && bitmap !== sprite.image && typeof bitmap.close === "function") {
        bitmap.close();
      }
    }
    iconSprites.clear();
  }

  /** Draw the icons again once the images still loading have loaded, a frame at most. */
  function scheduleIconPaint() {
    if (iconFrame || disposed) {
      return;
    }
    const run = () => {
      iconFrame = 0;
      if (!disposed) {
        paintIcons();
      }
    };
    iconFrame = win?.requestAnimationFrame ? win.requestAnimationFrame(run) : setTimeout(run, 16);
  }

  /**
   * Draw the icons the cells too small for their names show alone on the icons
   * canvas, each at its place (iconList), dimmed as its cell is.
   */
  function paintIcons() {
    if (!layers) {
      return;
    }
    const canvas = layers.icons;
    const ctx = sizeCanvas(canvas, laidOutBox);
    if (!ctx) {
      return;
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < iconRects.length; i += 1) {
      const rect = iconRects[i];
      const cell = cells[rect.cell];
      const bitmap = iconSprite(iconOfRect[i], rect.w)?.bitmap;
      if (!bitmap) {
        continue;
      }
      ctx.globalAlpha = resolveStyle(cellStyleKey(cell)).alpha;
      ctx.drawImage(bitmap, rect.x, rect.y, rect.w, rect.h);
    }
    ctx.globalAlpha = 1;
  }

  // ---- Hover -----------------------------------------------------------------

  /**
   * Whether two lists of cell indexes are the same, in the same order.
   * @param {ReadonlyArray<number>} a
   * @param {ReadonlyArray<number>} b
   */
  function sameIndexes(a, b) {
    return a.length === b.length && a.every((index, i) => index === b[i]);
  }

  /**
   * Draw the hover on the map's cells: a legend entry's hover marks every cell of its
   * family, the files of its types and the folders it is the dominant type of, the cells
   * it colors, as `family`; a cell's own hover marks that cell as `self`. The legend
   * marks its entry and the tally bars their segments (distribution-legend.js,
   * folder-totals.js). Every marked cell lifts, and none grows, since a cell's area is
   * its value; only the cell under the pointer shimmers, on its hover anchor
   * (styles.css, beside the rule; docs/design-system.md, "Folder Treemap").
   */
  function drawCellHover() {
    const target = hover?.current();
    /** @type {(index: number) => boolean} */
    let marked = () => false;
    if (target && cells.length > 0) {
      if (target.marks === "self") {
        const anchor = layers?.anchor ?? null;
        if (anchor && target.anchor === anchor && hoveredIndex >= 0) {
          const own = hoveredIndex;
          marked = (index) => index === own;
        }
      } else {
        const keys = paletteKeys;
        marked = (index) => keys[index] === target.key;
      }
    }
    markedIndexes = [];
    for (let i = 0; i < cells.length; i += 1) {
      if (marked(i)) {
        markedIndexes.push(i);
      }
    }
    currentMarkOps = markOps(cells, marked, dpr);
    // The same marks again, as a repaint or a relayout draws them, are drawn in place.
    // New marks go on the canvas not shown, which fades in as the shown one fades out;
    // no marks fade the shown one out where it is, so a pointer that leaves one cell
    // for the next, a leave and then an enter, fades the old lift out as the new one
    // fades in. The marks the fading canvas held, entered again at once, as a relayout
    // under a still pointer leaves its cell and enters it again, are shown again on
    // that canvas, so the lift does not dip.
    const changed = !sameIndexes(markedIndexes, shownMarked);
    const previous = shownMarked;
    shownMarked = markedIndexes;
    if (!layers) {
      return;
    }
    const front = layers.marks[shownMarks];
    if (markedIndexes.length === 0) {
      if (changed) {
        fadingMarked = previous;
        front.classList.remove("tm-marks-shown");
        fadeOut(front);
      }
      return;
    }
    if (!changed || sameIndexes(markedIndexes, fadingMarked)) {
      fadingMarked = [];
      drawMarks(front);
      front.classList.add("tm-marks-shown");
      return;
    }
    fadingMarked = [];
    const back = layers.marks[1 - shownMarks];
    drawMarks(back);
    back.classList.add("tm-marks-shown");
    front.classList.remove("tm-marks-shown");
    fadeOut(front);
    shownMarks = 1 - shownMarks;
  }

  /**
   * Draw the current mark ops on `canvas`.
   * @param {HTMLCanvasElement} canvas
   */
  function drawMarks(canvas) {
    if (!layers) {
      return;
    }
    const ctx = sizeCanvas(canvas, laidOutBox);
    if (ctx) {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      applyMarkOps(ctx, layers.paint, currentMarkOps);
    }
  }

  /**
   * Clear a marks canvas once it has faded out, so a hidden canvas holds no lift: at
   * once where it does not fade (reduced motion), or when its fade ends, unless it was
   * shown again first.
   * @param {HTMLCanvasElement} canvas
   */
  function fadeOut(canvas) {
    const clear = () => {
      if (canvas.classList.contains("tm-marks-shown")) {
        return;
      }
      const ctx = typeof canvas.getContext === "function" ? canvas.getContext("2d") : null;
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
    };
    const seconds = Number.parseFloat(win?.getComputedStyle?.(canvas).transitionDuration ?? "0");
    if (!(seconds > 0) || typeof canvas.addEventListener !== "function") {
      clear();
      return;
    }
    // Not transitioncancel: a fade reversed, as a pointer back within the fade shows the
    // canvas again, cancels the fade, and the canvas must keep its lift. The next fade
    // out ends, or the next draw replaces what the canvas holds.
    canvas.addEventListener("transitionend", clear, { once: true });
  }
  const unsubscribeCellHover = hover ? hover.subscribe(drawCellHover) : () => {};

  /**
   * Let go of the hover the cell under the pointer entered, as a layout replaces the
   * cell or the pointer leaves it.
   */
  function releaseCellHover() {
    if (cellHover && hover) {
      hover.leave(cellHover);
    }
    cellHover = null;
  }

  /** Take the hover anchor away, with the tooltip and the hover it carried. */
  function clearPointerCell() {
    if (hoveredIndex < 0 && !layers?.anchor) {
      return;
    }
    mb.tooltip.hide();
    releaseCellHover();
    hoveredIndex = -1;
    viewport.style.cursor = "";
    if (layers?.anchor) {
      layers.anchor.remove();
      layers.anchor = null;
    }
  }

  /**
   * Point at cell `index`: a new anchor element for it, so the tooltip and the
   * shared hover, which both key on the anchor, see a new cell; the tooltip; and
   * the cell's own hover.
   * @param {number} index
   */
  function pointAt(index) {
    if (index === hoveredIndex) {
      return;
    }
    clearPointerCell();
    if (index < 0) {
      return;
    }
    const cell = cells[index];
    const anchor = doc.createElement("div");
    // A nesting folder's anchor would shimmer over its children, so a folder
    // lifts without the shimmer.
    anchor.className = `tm-cell tm-hover-anchor tm-${cell.kind}`;
    anchor.setAttribute("style", boxStyle(cell));
    anchor.setAttribute("aria-hidden", "true");
    if (!cell.nested) {
      anchor.dataset.hovered = "self";
    }
    anchor.dataset.tmCell = String(index);
    const own = ensureLayers();
    // Under the labels, so its shimmer is too and a label keeps its contrast.
    viewport.insertBefore(anchor, own.labels);
    own.anchor = anchor;
    viewport.style.cursor = cellIsActionable(cell) ? "pointer" : "";
    hoveredIndex = index;
    const state = options.getState();
    mb.tooltip.show(tooltipHtml(cell, state), anchor);
    if (hover) {
      /** @type {DistributionHoverTarget} */
      const target = Object.freeze({
        population: state.includeIgnored ? "all" : "files",
        key: cellPaletteKey(cell),
        anchor,
        marks: /** @type {const} */ ("self"),
      });
      cellHover = target;
      hover.enter(target);
    }
  }

  /** Hit-test the pointer's last position and point at the cell under it. */
  function trackPointer() {
    pointerFrame = 0;
    if (disposed || !pointer || !hitGrid) {
      return;
    }
    pointAt(cellAtClient(pointer));
  }

  /**
   * The cell painted at a client position, or -1.
   * @param {{clientX: number, clientY: number}} client
   * @returns {number}
   */
  function cellAtClient(client) {
    const at = pointerPosition(client);
    return at && hitGrid ? hitGrid.lookup(at.x, at.y) : -1;
  }

  /**
   * A client position in the viewport's padding box.
   * @param {{clientX: number, clientY: number}} e
   * @returns {{x: number, y: number} | null}
   */
  function pointerPosition(e) {
    if (typeof viewport.getBoundingClientRect !== "function") {
      return null;
    }
    const rect = viewport.getBoundingClientRect();
    return {
      x: e.clientX - rect.left - (Number(viewport.clientLeft) || 0),
      y: e.clientY - rect.top - (Number(viewport.clientTop) || 0),
    };
  }

  /** @param {MouseEvent} e */
  function onMouseMove(e) {
    pointer = { clientX: e.clientX, clientY: e.clientY };
    // One lookup a frame: mousemove can fire several times between frames.
    if (!pointerFrame) {
      pointerFrame = win?.requestAnimationFrame ? win.requestAnimationFrame(trackPointer) : 0;
      if (!pointerFrame) {
        trackPointer();
      }
    }
  }

  function onMouseLeave() {
    pointer = null;
    clearPointerCell();
  }

  /** @param {MouseEvent} e */
  function onClick(e) {
    const index = cellAtClient(e);
    const cell = index >= 0 ? cells[index] : null;
    if (cell && cellIsActionable(cell)) {
      options.onActivate(cell);
    }
  }

  // ---- Keyboard ----------------------------------------------------------------

  /** Put the focus proxy over the focused cell, with its name. */
  function placeFocus() {
    if (!layers) {
      return;
    }
    const { focus } = layers;
    const index = actionableIndexes[focusPos];
    if (index === undefined) {
      focus.hidden = true;
      focus.removeAttribute("aria-label");
      return;
    }
    focus.hidden = false;
    focus.setAttribute("style", boxStyle(cells[index]));
    focus.setAttribute("aria-label", cellAriaLabel(index, options.getState()));
    focus.dataset.tmCell = String(index);
  }

  /** @param {number} nextPos position within actionableIndexes */
  function moveFocus(nextPos) {
    if (nextPos < 0 || nextPos >= actionableIndexes.length) {
      return;
    }
    focusPos = nextPos;
    placeFocus();
  }

  /** @param {KeyboardEvent} e */
  function onKeyDown(e) {
    // A key held with Command, Control, or Option is the browser's: Command-R
    // reloads, and Command-Left or Alt-Left goes back.
    if (e.altKey || e.ctrlKey || e.metaKey) {
      return;
    }
    const key = e.key;
    if (key === "Enter" || key === " ") {
      const cell = cells[actionableIndexes[focusPos]];
      if (cell) {
        options.onActivate(cell);
      }
      e.preventDefault();
    } else if (key === "ArrowRight" || key === "ArrowDown") {
      moveFocus(focusPos + 1);
      e.preventDefault();
    } else if (key === "ArrowLeft" || key === "ArrowUp") {
      moveFocus(focusPos - 1);
      e.preventDefault();
    } else if (key === "Backspace" && options.onParent) {
      options.onParent();
      e.preventDefault();
    }
  }

  viewport.addEventListener("mousemove", /** @type {EventListener} */ (onMouseMove));
  viewport.addEventListener("mouseleave", onMouseLeave);
  viewport.addEventListener("click", /** @type {EventListener} */ (onClick));
  viewport.addEventListener("keydown", /** @type {EventListener} */ (onKeyDown));

  // ---- Theme and pixel ratio -------------------------------------------------

  /** Colors and pixels changed under the same layout: paint it again. */
  function repaint() {
    styleCache.clear();
    iconColors.clear();
    dropIconSprites();
    if (lastRender && !disposed) {
      render(lastRender.node, lastRender.content);
    }
  }
  // The shell resolves its theme into data-theme on the root element (app.js).
  const themeObserver =
    typeof MutationObserver === "function" && doc.documentElement
      ? new MutationObserver(repaint)
      : null;
  themeObserver?.observe(doc.documentElement, {
    attributes: true,
    attributeFilter: ["data-theme"],
  });
  /** @type {MediaQueryList | null} */
  let resolutionQuery = null;
  function watchResolution() {
    resolutionQuery?.removeEventListener?.("change", onResolutionChange);
    resolutionQuery = win?.matchMedia?.(`(resolution: ${dpr}dppx)`) ?? null;
    resolutionQuery?.addEventListener?.("change", onResolutionChange);
  }
  function onResolutionChange() {
    dpr = devicePixelRatio();
    watchResolution();
    repaint();
  }
  watchResolution();

  // ---- Rendering ----------------------------------------------------------------

  /**
   * Replace the map's content with cells for `node`, or with
   * `placeholderHtml` when there is no tree to draw.
   * @param {Record<string, any> | null} node
   * @param {{placeholderHtml?: string, emptyHtml?: string}} [content]
   * @returns {number} cells drawn
   */
  function render(node, content) {
    if (disposed) {
      return 0;
    }
    lastRender = { node, content: content ?? {} };
    try {
      return renderCells(node, content ?? {});
    } finally {
      drawCellHover();
      // A canvas raises no mouseover when what is under a still pointer changes,
      // so the map asks itself which cell the pointer is on now.
      if (pointer && hitGrid) {
        pointAt(cellAtClient(pointer));
      }
    }
  }

  /**
   * @param {Record<string, any> | null} node
   * @param {{placeholderHtml?: string, emptyHtml?: string}} content
   */
  function renderCells(node, content) {
    const box = drawableBox();
    const state = options.getState();
    dpr = Math.min(devicePixelRatio(), Math.sqrt(MAX_BACKING_PIXELS / Math.max(1, box.w * box.h)));
    // Read the registry again for this layout, as its children's order (typeOf) and
    // their cells' colors (cellPaletteKey) both do.
    extensionKeys.clear();
    const laidOut =
      node && box.w >= 10 && box.h >= 10
        ? layoutTree(node, box, {
            typeOf: (/** @type {string} */ ext) => extensionKey(ext || "(none)"),
            ...preset.layout,
            minCellPx: 1 / dpr,
            labelMinW: preset.labelMinW,
            labelMinH: preset.labelMinH,
            metric: state.metric,
            includeIgnored: state.includeIgnored,
          })
        : [];
    // The cell the focus proxy is on, so a relayout keeps it there: a key
    // pressed after a refresh acts on the cell the user chose.
    const focusedCell = cells[actionableIndexes[focusPos]];
    const focusedKey = focusedCell ? `${focusedCell.kind}\u0000${focusedCell.path}` : null;
    clearPointerCell();
    if (laidOut.length === 0) {
      cells = [];
      paletteKeys = [];
      paintRects = [];
      iconRects = [];
      iconOfRect = [];
      emptyCells = 0;
      actionableIndexes = [];
      remainderNotes = new Map();
      hitGrid = null;
      dropLayers();
      viewport.innerHTML =
        node && box.w >= 10 && box.h >= 10
          ? (content.emptyHtml ?? "")
          : (content.placeholderHtml ?? "");
      return 0;
    }
    cells = laidOut;
    paletteKeys = cells.map(cellPaletteKey);
    laidOutBox = box;
    ensureLayers();
    const listed = paintList(cells, cellStyleKey, dpr);
    paintRects = listed.rects;
    emptyCells = listed.empty;
    hitGrid = buildHitGrid(cells, box, dpr);
    paintMap();
    // Both marks canvases take the map's size with its layout, so the one a hover draws
    // on first changes no box under it.
    for (const canvas of ensureLayers().marks) {
      sizeCanvas(canvas, box);
    }
    iconRects = iconList(
      cells,
      (i) => {
        const plan = labelPlan(cells[i]);
        return plan.iconOnly ? plan.iconPx : 0;
      },
      dpr,
    );
    iconOfRect = iconRects.map((rect) => cellIcon(cells[rect.cell]));
    paintIcons();
    reconcileLabels(state);
    // The focus proxy walks every folder and file cell in layout order;
    // remainder cells are named by their folder instead.
    actionableIndexes = [];
    remainderNotes = new Map();
    cells.forEach((cell, i) => {
      if (cellIsActionable(cell)) {
        actionableIndexes.push(i);
      } else if (cell.kind === "rest" && cell.parent >= 0) {
        remainderNotes.set(
          cell.parent,
          `${mb.formatFileCount(cell.files || 0)} more in the remainder`,
        );
      }
    });
    const kept = focusedKey
      ? actionableIndexes.findIndex((i) => `${cells[i].kind}\u0000${cells[i].path}` === focusedKey)
      : -1;
    focusPos = kept >= 0 ? kept : 0;
    placeFocus();
    return cells.length;
  }

  INSPECTORS.set(viewport, () =>
    Object.freeze({
      cells,
      paint: paintRects,
      empty: emptyCells,
      labels: cells.flatMap((cell, i) => (labelPlan(cell).showLabel ? [i] : [])),
      icons: cells.flatMap((cell, i) => {
        const plan = labelPlan(cell);
        return plan.iconOnly ? [{ cell: i, px: plan.iconPx }] : [];
      }),
      iconRects,
      // Each drawn icon's glyph size, over a label or alone (labelIconPx, iconOnlyPx).
      glyphs: cells.flatMap((cell, i) => {
        const plan = labelPlan(cell);
        return plan.icon || plan.iconOnly
          ? [{ cell: i, px: plan.iconPx, alone: plan.iconOnly }]
          : [];
      }),
      focusOrder: actionableIndexes,
      focused: actionableIndexes[focusPos] ?? -1,
      hovered: hoveredIndex,
      marked: markedIndexes,
      markOps: currentMarkOps,
      styles: Object.fromEntries(styleCache),
      dpr,
    }),
  );

  function dispose() {
    if (disposed) {
      return;
    }
    disposed = true;
    if (pointerFrame && win?.cancelAnimationFrame) {
      win.cancelAnimationFrame(pointerFrame);
    }
    if (iconFrame) {
      if (win?.cancelAnimationFrame) {
        win.cancelAnimationFrame(iconFrame);
      } else {
        clearTimeout(iconFrame);
      }
    }
    iconFrame = 0;
    dropIconSprites();
    pointerFrame = 0;
    pointer = null;
    releaseCellHover();
    unsubscribeCellHover();
    themeObserver?.disconnect();
    resolutionQuery?.removeEventListener?.("change", onResolutionChange);
    viewport.removeEventListener("mousemove", /** @type {EventListener} */ (onMouseMove));
    viewport.removeEventListener("mouseleave", onMouseLeave);
    viewport.removeEventListener("click", /** @type {EventListener} */ (onClick));
    viewport.removeEventListener("keydown", /** @type {EventListener} */ (onKeyDown));
    // Take back every element the map put in the viewport: a left anchor would
    // still be marked and shimmering, and a left focus proxy still focusable.
    if (layers) {
      for (const element of [
        layers.paint,
        ...layers.marks,
        layers.icons,
        layers.labels,
        layers.focus,
        layers.probes,
        layers.anchor,
      ]) {
        element?.remove();
      }
    }
    viewport.style.cursor = "";
    hoveredIndex = -1;
    dropLayers();
    INSPECTORS.delete(viewport);
    // The host puts away the tooltip, its own and the map's at once, since it
    // may own other tooltips around the map (mb-alff).
  }

  return Object.freeze({
    render,
    /** Let go of the cell hover, as the host's own disposal begins. */
    releaseHover: releaseCellHover,
    dispose,
  });
}
