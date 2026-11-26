// Folder plugin — pure treemap geometry (no DOM, no fetch).
//
// Classic script loaded via manifest extra_scripts BEFORE index.js; it
// exposes one global, `MetabrowserTreemapLayout`, that index.js and the
// Node vm tests consume. Squarified layout per Bruls, Huizing & van
// Wijk ("Squarified Treemaps", 2000): rows packed along the shorter
// side of the free rectangle, accepting an item into the current row
// only while it improves the row's worst aspect ratio.
//
// `layoutTree` walks a /api/rollup node tree and returns a flat array
// of positioned folder and file cells. Folders nest breadth-first by
// area: the largest pending folder is filled next, from a share of the
// remaining cell budget proportional to its area, so the budget spreads
// across the whole map instead of draining into the first folder drawn.
// Folders large enough for a label nest under a header strip; smaller
// ones nest with no label, inside a frame that thins with depth or, when
// too small for a frame, edge to edge, and the tooltip names them. Each
// cell records its parent's index, which hit testing and hover marks use.
// A folder is sized for its header and frame as well as its contents
// (`chromeRounds`, `chromePasses`), so a file's area follows its value
// however deep it sits, instead of shrinking by each folder's chrome
// around it. Bounds: cells below `minCellPx` in either dimension merge
// into their parent's rest cell, and nesting stops once `maxCells` cells
// exist, so pathological trees cannot flood the DOM.

/**
 * Layout bounds and nesting thresholds. The renderer can override any
 * of these via the `opts` argument; tests pin them explicitly.
 */
const LAYOUT_DEFAULTS = {
  /** Cells smaller than this (either dimension, px) merge into the rest cell. */
  minCellPx: 4,
  /**
   * Hard cap on emitted cells across all nesting levels. The layout is about
   * 1 ms of a render; writing the cells is the rest. Measured in the app's
   * browser pane on this repository, 2026-11-22, layout and markup together:
   * 11 to 14 ms at 800 cells, 22 to 23 ms at 1,600, 30 to 31 ms at 2,400.
   * 1,600 keeps a relayout near two frames while drawing twice the cells; the
   * rollup's node budget (ROLLUP_MAX_NODES, settings.py) is the other bound.
   */
  maxCells: 1600,
  /**
   * Levels drawn, the outermost included (1 = flat). Unbounded by default:
   * the rollup's own depth and the cells' room bound it.
   */
  nestDepth: Infinity,
  /**
   * A cell at least this wide and tall has room for its label. These are the
   * map's paint thresholds (treemap-map.js passes its preset's in), so a
   * folder the map would label is never framed instead, which hid the names
   * of folders that had room for them.
   */
  labelMinW: 40,
  labelMinH: 14,
  /**
   * A folder with room for its label nests its children under the label
   * strip when it is at least this tall: the strip, the padding, and a row of
   * children at least 20 px tall. A shorter one is a solid, labelled cell.
   */
  nestMinH: 40,
  /**
   * A folder too small for its label nests with no header: inside a frame
   * when it is at least this size on both sides, WinDirStat's threshold for
   * drawing a folder's frame, and edge to edge below it, so its files are
   * drawn however small it is and the tooltip names the folder. A frame on a
   * smaller folder draws mostly frame.
   */
  frameNestMinPx: 5,
  /**
   * A frame's width at depth `l` (the root's children are depth 0) is
   * ceil(padPx * frameDecay^l), the squarified paper's frames that thin with
   * depth (Bruls, Huizing & van Wijk 2000, section 4), so a deep tree spends
   * its pixels on files rather than on borders. 2 px at depths 0 to 2, 1 px
   * below.
   */
  frameDecay: 0.75,
  /** Inner padding between a labelled directory cell's border and its children (px). */
  padPx: 2,
  /**
   * Fewest cells a nesting folder is offered, however small its share of the
   * remaining area: enough for a few files and the remainder beside them.
   * Fewer left a small folder's children all folded into its remainder, a
   * nest with nothing to show; more drained the budget from large folders
   * into the many small ones that share a map.
   */
  minNestShare: 4,
  /**
   * Rounds of the chrome estimate (estimateChrome), which sizes each folder for
   * its header and frame as well as its contents, so a file's area follows its
   * value at every depth rather than shrinking with each folder around it. 0
   * sizes folders by value alone. Measured on this repository at 1100 by 560,
   * 2026-11-23, the 10th-percentile file's area over the median file's, by
   * value: 0.55 (bytes) and 0.51 (files) uncompensated; 0.72 and 0.68 after
   * one round, 0.93 and 0.92 after two, 0.94 and 0.89 after four, no better
   * after six. Each round is two walks of the rollup's nodes: four add about
   * 2 ms to a 31 ms layout of 23,000 cells.
   */
  chromeRounds: 4,
  /**
   * Layouts after the first that correct the estimate by the chrome the last
   * layout drew, folder by folder, while that layout has at most
   * `chromePassMaxCells` cells. The estimate takes every folder for a square,
   * and a squarified folder is longer than one and spends 2 to 4 points more
   * of its area on frame; nested eight deep, that leaves the deepest files at
   * 0.55 to 0.7 of their area. One pass brings this repository's 10th
   * percentile to 0.98 (bytes) and 0.97 (files), at the cost of a second
   * layout.
   */
  chromePasses: 1,
  /**
   * The most cells a layout may have and still be corrected by a second one.
   * A layout of 5,000 cells takes about 5 ms (PAINT_MAX_CELLS, treemap-map.js,
   * measures the layout as about half of 11 ms), a third of a frame; a larger
   * map keeps the estimate alone, which on this repository with its ignored
   * files (23,000 cells) holds depths 1 to 8 within 8% of their area and
   * leaves the deepest at 0.55 to 0.7, from 0.28 uncompensated.
   */
  chromePassMaxCells: 5000,
};

const TYPOGRAPHY_DEFAULTS = Object.freeze({
  /**
   * The smallest label and value a cell draws, so a small cell still names
   * itself; a cell too small even for these shows its icon (treemap-map.js).
   */
  labelMinPx: 9,
  labelMaxPx: 24,
  valueMinPx: 9,
  valueMaxPx: 18,
  /**
   * A folder's label and value stop growing at the navigation's sizes for a
   * name and its size (--nav-font-size and --ui-small-font-size,
   * static/styles.css): a folder's name is a heading over its files, and at
   * a file's 24 px it outweighed the map. Its header strip stops with it.
   */
  folderLabelMaxPx: 13,
  folderValueMaxPx: 12,
  /** Floor for the label strip derived by `cellTypography`; not a layout override. */
  headerMinPx: 16,
  basisMinPx: 24,
  basisMaxPx: 360,
});

/**
 * A cell's file-type icon, sized to its cell as its label is (treemap-map.js
 * draws it). Every size is the glyph's, in CSS pixels; the icon's box is the
 * glyph itself, since the cell or the title centers it.
 *
 * Over a label the glyph is `labelShare` of the label's size, so a 9 px
 * label has an 8 px glyph rather than the navigation's 14 px one, which stood
 * taller than its name. A cell too small for its name shows its icon alone at
 * `cellShare` of its short side, which keeps a margin on every side and names
 * a cell 6 px on its short side with a 4 px glyph, and never larger than the
 * glyph its label would have had, so a smaller cell never shows a larger icon
 * than a labelled one. No glyph is drawn larger
 * than `glyphMaxPx`, two pixels under the navigation's --icon-glyph
 * (static/styles.css), or smaller than `glyphMinPx`: below it, a glyph is a
 * dot of a few pixels, and the cell's color says what the glyph would.
 *
 * Measured in headless Chrome at 1400 by 900 on this repository at c7e2b5991
 * (2026-11-23, tests/dom/treemap-label-coverage-chrome.mjs). With a fixed
 * 14 px glyph, drawn alone only in a cell 16 px on each side, the Treemap view
 * named 51 of 2,532 cells by Files and 145 of 2,446 by Bytes. With the rule
 * before this one, an icon alone in a 16 px box down to an 8 px one and a
 * name only with room for its icon at the name's line (42c7dd9d9), it named
 * 51 and 376; the cells it left unnamed were 3 to 10 px on their short side by
 * Files (1,569 of 2,481 at 9 px) and 0 to 10 px by Bytes. With these sizes it
 * names 2,482 by Files and 1,211 by Bytes: what it leaves is under 6 px on its
 * short side. A 6 px minimum named 1,648 and 627; the smallest glyphs looked
 * of a piece with the rest, and leaving the cells between unnamed did not.
 */
const ICON_DEFAULTS = Object.freeze({
  glyphMinPx: 4,
  glyphMaxPx: 12,
  labelShare: 0.85,
  cellShare: 2 / 3,
  /** The gap between a glyph and its label, as a share of the label's size (.tm-cell-title). */
  gapShare: 0.4,
});

/**
 * The glyph over a label of `labelPx`.
 * @param {number} labelPx
 * @returns {number}
 */
function labelIconPx(labelPx) {
  return clamp(
    Math.round(labelPx * ICON_DEFAULTS.labelShare),
    ICON_DEFAULTS.glyphMinPx,
    ICON_DEFAULTS.glyphMaxPx,
  );
}

/**
 * The gap between a glyph and the label of `labelPx` under it (.tm-cell-title, styles.css).
 * @param {number} labelPx
 * @returns {number}
 */
function labelIconGapPx(labelPx) {
  return Number((labelPx * ICON_DEFAULTS.gapShare).toFixed(2));
}

/**
 * The height a glyph over a label of `labelPx` adds to a title: the glyph and its gap.
 * @param {number} labelPx
 * @returns {number}
 */
function labelIconRoomPx(labelPx) {
  return labelIconPx(labelPx) + labelIconGapPx(labelPx);
}

/**
 * The glyph a cell too small for its name shows alone, or 0 when the cell is too
 * small even for the smallest: a share of its short side, and no larger than
 * the glyph over the label it has no room for, of `labelPx`.
 * @param {{w: number, h: number}} rect
 * @param {number} [labelPx]  the cell's label size; the smallest label's by default
 * @returns {number}
 */
function iconOnlyPx(rect, labelPx = TYPOGRAPHY_DEFAULTS.labelMinPx) {
  const shortSide = Math.min(Math.max(0, Number(rect.w) || 0), Math.max(0, Number(rect.h) || 0));
  const glyph = Math.floor(shortSide * ICON_DEFAULTS.cellShare);
  return glyph < ICON_DEFAULTS.glyphMinPx ? 0 : Math.min(glyph, labelIconPx(labelPx));
}

/** The type sizes a cell too small for a label carries: the smallest, never drawn. */
const NO_LABEL = Object.freeze({
  labelPx: TYPOGRAPHY_DEFAULTS.labelMinPx,
  valuePx: TYPOGRAPHY_DEFAULTS.valueMinPx,
  headerPx: TYPOGRAPHY_DEFAULTS.headerMinPx,
});

/**
 * @typedef {{x: number, y: number, w: number, h: number}} Rect
 * @typedef {{value: number, actual?: number, bytes?: number, count?: number} & Record<string, any>} WeightedItem
 */

/**
 * A child's extension, case folded: a file's own, or a folder's dominant one, which
 * colors a solid folder's cell; "" for none.
 * @param {Record<string, any>} node
 */
function extensionOf(node) {
  const ext = node.type === "dir" ? node.dominant_ext : node.ext;
  return typeof ext === "string" ? ext.toLowerCase() : "";
}

/**
 * The type a child sorts by among children of equal value: the color family its
 * extension belongs to, as `typeOf` names it (the map passes the palette's lookup),
 * so a family of several extensions, as JavaScript's .js and .mjs, sits together;
 * without `typeOf`, its extension. "" for none.
 * @param {Record<string, any>} node
 * @param {((ext: string) => string) | undefined} [typeOf]
 */
function typeKey(node, typeOf) {
  const raw = node.type === "dir" ? node.dominant_ext : node.ext;
  if (typeOf) {
    return String(typeOf(typeof raw === "string" ? raw : ""));
  }
  return extensionOf(node);
}

/** Code-unit order, the same in every engine, as a locale's order is not. */
function compareText(/** @type {unknown} */ a, /** @type {unknown} */ b) {
  const x = String(a ?? "");
  const y = String(b ?? "");
  return x < y ? -1 : x > y ? 1 : 0;
}

/**
 * The order a folder's children are laid out in. Value comes first, largest first, as
 * the squarified layout needs, so the order changes no cell's size. Children of equal
 * value, as every file is by Files and same-sized files are by Bytes, break by type, so
 * cells of one color sit together: by type (typeKey), with none after every type,
 * then by extension within it, then by name case folded, then by path. The remainder
 * comes after every child of its value. The order is total, so the map draws the same
 * whichever order the rollup sent the children in, as the compact encoding sends a
 * folder's files after its folders (treemap-rollup-decode.js).
 * @param {WeightedItem} a
 * @param {WeightedItem} b
 */
function compareChildren(a, b) {
  if (b.value !== a.value) {
    return b.value - a.value;
  }
  if (Boolean(a.rest) !== Boolean(b.rest)) {
    return a.rest ? 1 : -1;
  }
  return (
    Number(a.sortType === "") - Number(b.sortType === "") ||
    compareText(a.sortType, b.sortType) ||
    compareText(a.sortExt, b.sortExt) ||
    compareText(a.sortName, b.sortName) ||
    compareText(a.node?.path, b.node?.path)
  );
}

/** @param {number} value @param {number} min @param {number} max */
function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

/**
 * Fluid type scale derived from the rectangle itself. The short side
 * prevents a wide sliver from receiving oversized text, while the
 * area term lets genuinely large cells grow smoothly. Values are
 * rounded only for stable inline CSS and remain continuous between
 * the documented bounds. A folder's sizes stop at the folder caps.
 *
 * @param {{w: number, h: number}} rect
 * @param {string} [kind]  the cell's kind; "dir" caps the sizes
 */
function cellTypography(rect, kind) {
  const width = Math.max(0, Number(rect.w) || 0);
  const height = Math.max(0, Number(rect.h) || 0);
  const shortSide = Math.min(width, height);
  const areaBasis = Math.sqrt(width * height) * 0.7;
  const basis = Math.min(shortSide, areaBasis);
  const span = TYPOGRAPHY_DEFAULTS.basisMaxPx - TYPOGRAPHY_DEFAULTS.basisMinPx;
  const progress = clamp((basis - TYPOGRAPHY_DEFAULTS.basisMinPx) / span, 0, 1);
  /** @param {number} min @param {number} max */
  const interpolate = (min, max) => Number((min + (max - min) * progress).toFixed(2));
  const folder = kind === "dir";
  const labelPx = Math.min(
    interpolate(TYPOGRAPHY_DEFAULTS.labelMinPx, TYPOGRAPHY_DEFAULTS.labelMaxPx),
    folder ? TYPOGRAPHY_DEFAULTS.folderLabelMaxPx : Infinity,
  );
  const valuePx = Math.min(
    interpolate(TYPOGRAPHY_DEFAULTS.valueMinPx, TYPOGRAPHY_DEFAULTS.valueMaxPx),
    folder ? TYPOGRAPHY_DEFAULTS.folderValueMaxPx : Infinity,
  );
  return Object.freeze({
    labelPx,
    valuePx,
    headerPx: Math.max(TYPOGRAPHY_DEFAULTS.headerMinPx, Math.ceil(labelPx * 1.2 + 4)),
  });
}

/**
 * Worst aspect ratio of a row of areas laid along `side`.
 * @param {number[]} areas
 * @param {number} side
 * @returns {number}
 */
function worstAspect(areas, side) {
  let sum = 0;
  let min = Infinity;
  let max = 0;
  for (const a of areas) {
    sum += a;
    if (a < min) {
      min = a;
    }
    if (a > max) {
      max = a;
    }
  }
  if (sum === 0 || side === 0) {
    return Infinity;
  }
  const sideSq = side * side;
  const sumSq = sum * sum;
  return Math.max((sideSq * max) / sumSq, sumSq / (sideSq * min));
}

/**
 * Squarified layout. Items must be sorted by descending value; zero
 * or negative values are skipped. Returns one placed rect per used
 * item, in item order.
 *
 * @param {WeightedItem[]} items
 * @param {Rect} rect
 * @returns {{item: WeightedItem, x: number, y: number, w: number, h: number}[]}
 */
function squarify(items, rect) {
  /** @type {{item: WeightedItem, x: number, y: number, w: number, h: number}[]} */
  const placed = [];
  const usable = items.filter((it) => it.value > 0);
  if (usable.length === 0 || rect.w <= 0 || rect.h <= 0) {
    return placed;
  }
  const totalValue = usable.reduce((s, it) => s + it.value, 0);
  const scale = (rect.w * rect.h) / totalValue;

  let free = { x: rect.x, y: rect.y, w: rect.w, h: rect.h };
  /** @type {WeightedItem[]} */
  let row = [];

  /** Lay the current row along the shorter side of the free rect. */
  function flushRow() {
    if (row.length === 0) {
      return;
    }
    const rowArea = row.reduce((s, it) => s + it.value * scale, 0);
    const horizontal = free.w >= free.h; // row occupies a vertical strip on the left
    const side = horizontal ? free.h : free.w;
    const thickness = side > 0 ? rowArea / side : 0;
    let offset = 0;
    for (const it of row) {
      const cellArea = it.value * scale;
      const along = thickness > 0 ? cellArea / thickness : 0;
      if (horizontal) {
        placed.push({ item: it, x: free.x, y: free.y + offset, w: thickness, h: along });
      } else {
        placed.push({ item: it, x: free.x + offset, y: free.y, w: along, h: thickness });
      }
      offset += along;
    }
    if (horizontal) {
      free = { x: free.x + thickness, y: free.y, w: free.w - thickness, h: free.h };
    } else {
      free = { x: free.x, y: free.y + thickness, w: free.w, h: free.h - thickness };
    }
    row = [];
  }

  for (const it of usable) {
    const side = Math.min(free.w, free.h);
    const rowAreas = row.map((r) => r.value * scale);
    const withAreas = rowAreas.concat([it.value * scale]);
    if (row.length === 0 || worstAspect(withAreas, side) <= worstAspect(rowAreas, side)) {
      row.push(it);
    } else {
      flushRow();
      row.push(it);
    }
  }
  flushRow();
  return placed;
}

/**
 * Metric value for a rollup child under the active options.
 * @param {Record<string, any>} node
 * @param {Record<string, any>} opts
 * @returns {number}
 */
function nodeValue(node, opts) {
  const excludeIgnored = opts.includeIgnored === false;
  if (node.type === "dir") {
    if (opts.metric === "files") {
      return excludeIgnored ? node.unignored_files : node.total_files;
    }
    return excludeIgnored ? node.unignored_size : node.total_size;
  }
  if (excludeIgnored && node.gitignored) {
    return 0;
  }
  return opts.metric === "files" ? 1 : node.size;
}

/**
 * Value carried by a rest bucket under the active options.
 * @param {Record<string, any>} rest
 * @param {Record<string, any>} opts
 * @returns {number}
 */
function restValue(rest, opts) {
  const excludeIgnored = opts.includeIgnored === false;
  if (opts.metric === "files") {
    return excludeIgnored ? rest.unignored_files : rest.files;
  }
  return excludeIgnored ? rest.unignored_size : rest.size;
}

/**
 * Pack weighted items into `rect` within a cell-count capacity while
 * conserving represented weight. Two passes: items cut by capacity
 * plus items whose first-pass rectangle falls under `minPx` merge
 * into one remainder item, then geometry is recomputed from the
 * final weights so every emitted rectangle's area matches the weight
 * it represents — nothing is dropped silently.
 *
 * @param {WeightedItem[]} items  sorted descending by value; at most
 *   one `{rest: true}` seed carrying server-side remainder weight. An item's
 *   `value` is the weight its area follows; `actual`, when present, is the
 *   metric it stands for, which the remainder reports.
 * @param {Rect} rect
 * @param {number} capacity  max rects to emit, including the remainder
 * @param {number} minPx
 * @returns {{placed: {item: WeightedItem, x: number, y: number, w: number, h: number}[],
 *   remainder: {x: number, y: number, w: number, h: number, value: number, count: number, bytes: number} | null}}
 */
function packLevel(items, rect, capacity, minPx) {
  /** @type {{item: WeightedItem, x: number, y: number, w: number, h: number}[]} */
  const none = [];
  if (capacity <= 0 || items.length === 0 || rect.w <= 0 || rect.h <= 0) {
    return { placed: none, remainder: null };
  }
  let remainderValue = 0;
  let remainderActual = 0;
  let remainderCount = 0;
  let remainderBytes = 0;
  /** @type {WeightedItem[]} */
  let survivors = [];
  for (const it of items) {
    if (it.rest) {
      remainderValue += it.value;
      remainderActual += it.actual ?? it.value;
      remainderCount += Number(it.count) || 0;
      remainderBytes += Number(it.bytes) || 0;
    } else if (it.value > 0) {
      survivors.push(it);
    }
  }

  /** @param {WeightedItem[]} kept @param {WeightedItem[]} cut */
  const foldCut = (kept, cut) => {
    for (const it of cut) {
      remainderValue += it.value;
      remainderActual += it.actual ?? it.value;
      remainderCount += Number(it.count) || 0;
      remainderBytes += Number(it.bytes) || 0;
    }
    survivors = kept;
  };

  // Capacity pass: reserve one slot for the remainder when anything
  // must fold into it.
  let limit = capacity - (remainderValue > 0 ? 1 : 0);
  if (survivors.length > limit) {
    limit = Math.max(0, capacity - 1);
    foldCut(survivors.slice(0, limit), survivors.slice(limit));
  }

  /** @returns {{item: WeightedItem, x: number, y: number, w: number, h: number}[]} */
  const layoutOnce = () => {
    /** @type {WeightedItem[]} */
    const withRemainder = survivors.slice();
    if (remainderValue > 0) {
      withRemainder.push({ value: remainderValue, bytes: remainderBytes, rest: true });
    }
    withRemainder.sort((a, b) => b.value - a.value);
    return squarify(withRemainder, rect);
  };

  let placed = layoutOnce();
  const tooSmall = placed.filter((p) => !p.item.rest && (p.w < minPx || p.h < minPx));
  if (tooSmall.length > 0) {
    const cutSet = new Set(tooSmall.map((p) => p.item));
    foldCut(
      survivors.filter((it) => !cutSet.has(it)),
      survivors.filter((it) => cutSet.has(it)),
    );
    // Final pass: geometry from the final weights. Any rect still
    // tiny after this is emitted anyway — its area stays true.
    placed = layoutOnce();
  }

  /** @type {{x: number, y: number, w: number, h: number, value: number, count: number, bytes: number} | null} */
  let remainder = null;
  /** @type {{item: WeightedItem, x: number, y: number, w: number, h: number}[]} */
  const emitted = [];
  for (const p of placed) {
    if (p.item.rest) {
      remainder = {
        x: p.x,
        y: p.y,
        w: p.w,
        h: p.h,
        value: remainderActual,
        count: remainderCount,
        bytes: remainderBytes,
      };
    } else {
      emitted.push(p);
    }
  }
  return { placed: emitted, remainder };
}

/**
 * Type sizes for a cell with room for its label; a smaller cell is never
 * labelled, and most cells of a dense map are smaller.
 * @param {{w: number, h: number}} rect
 * @param {Record<string, any>} opts
 * @param {string} [kind]
 */
function typographyFor(rect, opts, kind) {
  return rect.w >= opts.labelMinW && rect.h >= opts.labelMinH
    ? cellTypography(rect, kind)
    : NO_LABEL;
}

/**
 * Where a folder's children go when it nests: under its label strip when it is
 * large enough, otherwise inside a thin frame, or edge to edge. Null when it
 * stays a solid cell. The layout and the chrome estimate both decide by it.
 *
 * @param {Rect} cell
 * @param {number} depth  the folder's own depth
 * @param {Record<string, any>} node
 * @param {Record<string, any>} opts
 * @returns {{inner: Rect, framed: boolean} | null}
 */
function nestGeometry(cell, depth, node, opts) {
  // A folder whose children all fold into its remainder (the rollup's node
  // budget ran out at it) has nothing to show inside but one inert
  // remainder cell, so it stays a solid cell, named by its own tooltip.
  const hasChildren = Array.isArray(node.children) && node.children.length > 0;
  if (node.type !== "dir" || !hasChildren || depth + 1 >= opts.nestDepth) {
    return null;
  }
  const labelFits = cell.w >= opts.labelMinW && cell.h >= opts.labelMinH;
  const labelled = labelFits && cell.h >= opts.nestMinH;
  // A folder with room for its label but too short to nest under it stays a
  // solid, labelled cell; every other folder nests without a header.
  if (labelFits && !labelled) {
    return null;
  }
  const inset = labelled
    ? opts.padPx
    : Math.min(cell.w, cell.h) >= opts.frameNestMinPx
      ? Math.ceil(opts.padPx * opts.frameDecay ** depth)
      : 0;
  const top = labelled ? cellTypography(cell, "dir").headerPx : inset;
  const inner = {
    x: cell.x + inset,
    y: cell.y + top,
    w: cell.w - 2 * inset,
    h: cell.h - top - inset,
  };
  if (inner.w < opts.minCellPx || inner.h < opts.minCellPx) {
    return null;
  }
  return { inner, framed: !labelled };
}

/**
 * Flatten a rollup tree into positioned folder and file cells.
 *
 * Every cell lies inside its parent's rectangle: children are packed into
 * the parent's inner rectangle (inset by `padPx`, and by the header strip
 * when the parent is labelled), and cells are emitted parent first, so a
 * renderer painting them in order draws children over their parent.
 *
 * @param {Record<string, any>} rootNode  /api/rollup `node`
 * @param {{w: number, h: number}} viewport  the drawable box, inside any border
 * @param {Record<string, any>} options   layout + view options:
 *   metric "size"|"files", includeIgnored boolean,
 *   plus any LAYOUT_DEFAULTS override.
 * @returns {Record<string, any>[]} cells with x/y/w/h/kind/depth/…
 */
function layoutTree(rootNode, viewport, options) {
  const opts = Object.assign({}, LAYOUT_DEFAULTS, options);
  if (!rootNode || viewport.w <= 0 || viewport.h <= 0) {
    return [];
  }
  // A folder's chrome is what it draws around its children: its header strip
  // and frame. Weighting each folder by its value plus its subtree's chrome,
  // at the area per unit of value that leaves the whole map's chrome paid for,
  // gives every file the same area per unit of value at every depth.
  const estimate =
    opts.chromeRounds > 0 ? estimateChrome(rootNode, viewport, opts, opts.chromeRounds) : null;
  let cells =
    estimate && estimate.total > 0 && estimate.perValue > 0
      ? layoutPass(rootNode, viewport, opts, estimate.byPath, estimate.perValue)
      : layoutPass(rootNode, viewport, opts, null, 0);
  const area = viewport.w * viewport.h;
  for (
    let pass = 0;
    pass < opts.chromePasses && cells.length <= opts.chromePassMaxCells;
    pass += 1
  ) {
    const chrome = subtreeChrome(cells);
    const rootValue = cells.reduce((sum, c) => (c.parent === -1 ? sum + c.value : sum), 0);
    const perValue = (area - chrome.total) / Math.max(rootValue, Number.MIN_VALUE);
    // A map that is all chrome, a box too small for its folders, has no area
    // left to compensate from, so it keeps the layout it has.
    if (chrome.total <= 0 || !(perValue > 0)) {
      break;
    }
    cells = layoutPass(rootNode, viewport, opts, chrome.byPath, perValue);
  }
  return cells;
}

/**
 * Estimate each folder's subtree chrome without laying the tree out: every
 * folder is taken to be square (an only child fills its parent's interior
 * exactly), its area its share of its parent's interior by weight, and its
 * chrome what nestGeometry would leave around its children at that size.
 * Weights depend on the chrome and the chrome on the sizes, so the estimate
 * repeats `rounds` times from no chrome. Each round is two walks of the
 * nodes and no packing, a small part of one layout.
 *
 * @param {Record<string, any>} rootNode
 * @param {{w: number, h: number}} viewport
 * @param {Record<string, any>} opts
 * @param {number} rounds
 * @returns {{byPath: Map<string, number>, total: number, perValue: number}}
 */
function estimateChrome(rootNode, viewport, opts, rounds) {
  // The tree flattened breadth first: parents before children.
  /** @type {Record<string, any>[]} */
  const nodes = [rootNode];
  const parent = [-1];
  const depth = [-1];
  const value = [0];
  /** Each folder's total child value, rest included. */
  const childValue = [0];
  for (let i = 0; i < nodes.length; i += 1) {
    const node = nodes[i];
    const children = Array.isArray(node.children) ? node.children : [];
    let sum = node.rest ? restValue(node.rest, opts) || 0 : 0;
    for (const child of children) {
      const v = nodeValue(child, opts);
      if (!(v > 0)) {
        continue;
      }
      sum += v;
      if (child.type === "dir") {
        nodes.push(child);
        parent.push(i);
        depth.push(depth[i] + 1);
        value.push(v);
        childValue.push(0);
      }
    }
    childValue[i] = sum;
  }
  const n = nodes.length;
  const chrome = new Float64Array(n);
  const own = new Float64Array(n);
  const area = new Float64Array(n);
  const innerArea = new Float64Array(n);
  const innerW = new Float64Array(n);
  const innerH = new Float64Array(n);
  /** Sum of each folder's children's chrome, its interior's extra weight. */
  const childChrome = new Float64Array(n);
  const onlyChild = new Uint8Array(n);
  const siblings = new Int32Array(n);
  for (let i = 1; i < n; i += 1) {
    siblings[parent[i]] += 1;
  }
  const total = viewport.w * viewport.h;
  const rootValue = childValue[0];
  let perValue = total / Math.max(rootValue, Number.MIN_VALUE);
  for (let round = 0; round < rounds; round += 1) {
    perValue = (total - childChrome[0]) / Math.max(rootValue, Number.MIN_VALUE);
    if (!(perValue > 0)) {
      break;
    }
    innerW[0] = viewport.w;
    innerH[0] = viewport.h;
    innerArea[0] = total;
    for (let i = 1; i < n; i += 1) {
      const p = parent[i];
      const weightSum = perValue * childValue[p] + childChrome[p];
      const a = weightSum > 0 ? (innerArea[p] * (perValue * value[i] + chrome[i])) / weightSum : 0;
      area[i] = a;
      // An only child that is its parent's whole value fills the interior;
      // any other is taken to be square.
      const fills = siblings[p] === 1 && childValue[p] === value[i];
      onlyChild[i] = fills ? 1 : 0;
      const w = fills ? innerW[p] : Math.sqrt(a);
      const h = fills ? innerH[p] : Math.sqrt(a);
      const nest = a > 0 ? nestGeometry({ x: 0, y: 0, w, h }, depth[i], nodes[i], opts) : null;
      if (nest) {
        innerW[i] = nest.inner.w;
        innerH[i] = nest.inner.h;
        innerArea[i] = nest.inner.w * nest.inner.h;
        own[i] = Math.max(0, a - innerArea[i]);
      } else {
        innerW[i] = 0;
        innerH[i] = 0;
        innerArea[i] = 0;
        own[i] = 0;
      }
    }
    // Bottom up: a folder's chrome is its own plus its nested children's.
    childChrome.fill(0);
    for (let i = n - 1; i >= 1; i -= 1) {
      chrome[i] = innerArea[i] > 0 ? own[i] + childChrome[i] : 0;
      childChrome[parent[i]] += chrome[i];
    }
  }
  /** @type {Map<string, number>} */
  const byPath = new Map();
  for (let i = 1; i < n; i += 1) {
    if (chrome[i] > 0) {
      byPath.set(nodes[i].path, chrome[i]);
    }
  }
  return { byPath, total: childChrome[0], perValue };
}

/**
 * Each nested folder's chrome in a layout, by path: its header strip and
 * frame (the cell less the inner rectangle its children tile), plus the
 * chrome of every folder nested inside it. Cells are emitted parent first,
 * so one pass from the end sums every subtree.
 *
 * @param {Record<string, any>[]} cells
 * @returns {{byPath: Map<string, number>, total: number}}
 */
function subtreeChrome(cells) {
  const sums = new Float64Array(cells.length);
  /** @type {Map<string, number>} */
  const byPath = new Map();
  let total = 0;
  for (let i = cells.length - 1; i >= 0; i -= 1) {
    const cell = cells[i];
    if (cell.nested && cell.inner) {
      sums[i] += Math.max(0, cell.w * cell.h - cell.inner.w * cell.inner.h);
    }
    if (sums[i] > 0 && cell.kind === "dir") {
      byPath.set(cell.path, sums[i]);
    }
    if (cell.parent >= 0) {
      sums[cell.parent] += sums[i];
    } else {
      total += sums[i];
    }
  }
  return { byPath, total };
}

/**
 * One layout of the tree. With `chrome`, a folder weighs its value plus the
 * chrome its subtree drew in an earlier pass, expressed in value units at
 * `perValue` area per unit, so its files keep the area their values earn.
 *
 * @param {Record<string, any>} rootNode
 * @param {{w: number, h: number}} viewport
 * @param {Record<string, any>} opts
 * @param {Map<string, number> | null} chrome
 * @param {number} perValue
 * @returns {Record<string, any>[]}
 */
function layoutPass(rootNode, viewport, opts, chrome, perValue) {
  /** @type {Record<string, any>[]} */
  const cells = [];
  const excludeIgnored = opts.includeIgnored === false;

  /** @typedef {{cell: Record<string, any>, index: number, node: Record<string, any>, inner: Rect, framed: boolean, area: number}} PendingNest */
  /** @type {PendingNest[]} */
  const pending = [];
  let pendingArea = 0;

  /**
   * Queue a just-emitted directory cell for nesting when its geometry and
   * the remaining depth allow it: under a labelled header when it is large
   * enough, otherwise inside a thin frame.
   * @param {Record<string, any>} cell
   * @param {number} index  the cell's index in `cells`
   * @param {Record<string, any>} node
   */
  function considerNesting(cell, index, node) {
    const nest = nestGeometry(/** @type {Rect} */ (cell), cell.depth, node, opts);
    if (!nest) {
      return;
    }
    const area = nest.inner.w * nest.inner.h;
    pending.push({ cell, index, node, inner: nest.inner, framed: nest.framed, area });
    pendingArea += area;
  }

  /**
   * Emit one directory's children into `rect` within `capacity` cells.
   * @param {Record<string, any>} dirNode
   * @param {Rect} rect
   * @param {number} depth
   * @param {number} capacity
   * @param {number} parent  the index of the folder's own cell, or -1 for the root
   * @returns {number} cells emitted
   */
  function emitLevel(dirNode, rect, depth, capacity, parent) {
    const children = Array.isArray(dirNode.children) ? dirNode.children : [];
    /** @type {WeightedItem[]} */
    const items = [];
    for (const child of children) {
      const value = nodeValue(child, opts);
      if (value > 0) {
        const extra = chrome && child.type === "dir" ? (chrome.get(child.path) ?? 0) : 0;
        items.push({
          value: extra > 0 ? value + extra / perValue : value,
          actual: value,
          bytes:
            child.type === "dir"
              ? excludeIgnored
                ? child.unignored_size
                : child.total_size
              : child.size,
          count:
            child.type === "dir" ? (excludeIgnored ? child.unignored_files : child.total_files) : 1,
          node: child,
          sortType: typeKey(child, opts.typeOf),
          sortExt: extensionOf(child),
          sortName: String(child.name ?? "").toLowerCase(),
        });
      }
    }
    const restVal = dirNode.rest ? restValue(dirNode.rest, opts) : 0;
    if (restVal > 0) {
      items.push({
        value: restVal,
        bytes: excludeIgnored ? dirNode.rest.unignored_size : dirNode.rest.size,
        count: excludeIgnored ? dirNode.rest.unignored_files : dirNode.rest.files,
        rest: true,
      });
    }
    items.sort(compareChildren);

    const before = cells.length;
    const packed = packLevel(items, rect, capacity, opts.minCellPx);
    for (const p of packed.placed) {
      const node = p.item.node;
      const typography = typographyFor(p, opts, p.item.node.type);
      const cell = {
        kind: node.type,
        name: node.name,
        path: node.path,
        x: p.x,
        y: p.y,
        w: p.w,
        h: p.h,
        depth,
        value: p.item.actual ?? p.item.value,
        // Real magnitudes regardless of the active metric, so labels
        // can always show true bytes/counts.
        bytes:
          node.type === "dir"
            ? excludeIgnored
              ? node.unignored_size
              : node.total_size
            : node.size,
        files: p.item.count,
        mtime: node.mtime,
        ext: node.type === "dir" ? node.dominant_ext : node.ext,
        gitignored: !!node.gitignored,
        state: node.state,
        parent,
        ...typography,
      };
      cells.push(cell);
      considerNesting(cell, cells.length - 1, node);
    }
    if (packed.remainder) {
      const typography = typographyFor(packed.remainder, opts);
      cells.push({
        kind: "rest",
        name: "…",
        path: dirNode.path,
        x: packed.remainder.x,
        y: packed.remainder.y,
        w: packed.remainder.w,
        h: packed.remainder.h,
        depth,
        value: packed.remainder.value,
        files: packed.remainder.count,
        bytes: packed.remainder.bytes,
        parent,
        ...typography,
      });
    }
    return cells.length - before;
  }

  emitLevel(rootNode, { x: 0, y: 0, w: viewport.w, h: viewport.h }, 0, opts.maxCells, -1);

  // Largest pending folder first, so the budget reaches every large
  // region of the map before it is spent on small ones.
  while (pending.length > 0 && cells.length < opts.maxCells) {
    let best = 0;
    for (let i = 1; i < pending.length; i += 1) {
      if (pending[i].area > pending[best].area) {
        best = i;
      }
    }
    const entry = pending[best];
    pending[best] = pending[pending.length - 1];
    pending.pop();
    const remaining = opts.maxCells - cells.length;
    const share = Math.min(
      remaining,
      Math.max(opts.minNestShare, Math.ceil((remaining * entry.area) / Math.max(pendingArea, 1))),
    );
    pendingArea -= entry.area;
    if (emitLevel(entry.node, entry.inner, entry.cell.depth + 1, share, entry.index) > 0) {
      entry.cell.nested = true;
      // The rectangle the children tile, which the paint list fills in the
      // folder's edge tone before them (treemap-paint.js).
      entry.cell.inner = entry.inner;
      if (entry.framed) {
        entry.cell.framed = true;
      }
    }
  }
  return cells;
}

export {
  cellTypography,
  compareChildren,
  ICON_DEFAULTS,
  iconOnlyPx,
  LAYOUT_DEFAULTS,
  labelIconGapPx,
  labelIconPx,
  labelIconRoomPx,
  layoutTree,
  packLevel,
  squarify,
  TYPOGRAPHY_DEFAULTS,
  typeKey,
  worstAspect,
};
