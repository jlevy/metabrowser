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
// ones nest inside a thin frame with no label, and the tooltip names
// them. Bounds: cells below `minCellPx` in either dimension merge into
// their parent's rest cell, and nesting stops once `maxCells` cells
// exist, so pathological trees cannot flood the DOM.

/**
 * Layout bounds and nesting thresholds. The renderer can override any
 * of these via the `opts` argument; tests pin them explicitly.
 */
const LAYOUT_DEFAULTS = {
  /** Cells smaller than this (either dimension, px) merge into the rest cell. */
  minCellPx: 4,
  /** Hard cap on emitted cells across all nesting levels. */
  maxCells: 800,
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
  labelMinW: 56,
  labelMinH: 16,
  /**
   * A folder with room for its label nests its children under the label
   * strip when it is at least this tall: the strip, the padding, and a row of
   * children at least 20 px tall. A shorter one is a solid, labelled cell.
   */
  nestMinH: 40,
  /**
   * A folder too small for its label nests, in a frame `padPx` wide with no
   * header, when it is at least this size on both sides: its files are drawn,
   * and the tooltip names the folder. Below it a folder is one solid cell.
   * 14 px leaves an interior of 10 px, room for a child of more than twice
   * minCellPx on each side; a smaller frame draws mostly frame.
   */
  frameNestMinPx: 14,
  /** Inner padding between a directory cell border and its children (px). */
  padPx: 2,
  /**
   * Fewest cells a nesting folder is offered, however small its share of the
   * remaining area: enough for a few files and the remainder beside them.
   * Fewer left a small folder's children all folded into its remainder, a
   * nest with nothing to show; more drained the budget from large folders
   * into the many small ones that share a map.
   */
  minNestShare: 4,
};

const TYPOGRAPHY_DEFAULTS = Object.freeze({
  labelMinPx: 11,
  labelMaxPx: 24,
  valueMinPx: 10,
  valueMaxPx: 18,
  /** Floor for the label strip derived by `cellTypography`; not a layout override. */
  headerMinPx: 16,
  basisMinPx: 24,
  basisMaxPx: 360,
});

/**
 * @typedef {{x: number, y: number, w: number, h: number}} Rect
 * @typedef {{value: number, bytes?: number, count?: number} & Record<string, any>} WeightedItem
 */

/** @param {number} value @param {number} min @param {number} max */
function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

/**
 * Fluid type scale derived from the rectangle itself. The short side
 * prevents a wide sliver from receiving oversized text, while the
 * area term lets genuinely large cells grow smoothly. Values are
 * rounded only for stable inline CSS and remain continuous between
 * the documented bounds.
 *
 * @param {{w: number, h: number}} rect
 */
function cellTypography(rect) {
  const width = Math.max(0, Number(rect.w) || 0);
  const height = Math.max(0, Number(rect.h) || 0);
  const shortSide = Math.min(width, height);
  const areaBasis = Math.sqrt(width * height) * 0.7;
  const basis = Math.min(shortSide, areaBasis);
  const span = TYPOGRAPHY_DEFAULTS.basisMaxPx - TYPOGRAPHY_DEFAULTS.basisMinPx;
  const progress = clamp((basis - TYPOGRAPHY_DEFAULTS.basisMinPx) / span, 0, 1);
  /** @param {number} min @param {number} max */
  const interpolate = (min, max) => Number((min + (max - min) * progress).toFixed(2));
  const labelPx = interpolate(TYPOGRAPHY_DEFAULTS.labelMinPx, TYPOGRAPHY_DEFAULTS.labelMaxPx);
  const valuePx = interpolate(TYPOGRAPHY_DEFAULTS.valueMinPx, TYPOGRAPHY_DEFAULTS.valueMaxPx);
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
 *   one `{rest: true}` seed carrying server-side remainder weight
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
  let remainderCount = 0;
  let remainderBytes = 0;
  /** @type {WeightedItem[]} */
  let survivors = [];
  for (const it of items) {
    if (it.rest) {
      remainderValue += it.value;
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
        value: remainderValue,
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
  /** @type {Record<string, any>[]} */
  const cells = [];
  if (!rootNode || viewport.w <= 0 || viewport.h <= 0) {
    return cells;
  }
  const excludeIgnored = opts.includeIgnored === false;

  /** @typedef {{cell: Record<string, any>, node: Record<string, any>, inner: Rect, framed: boolean, area: number}} PendingNest */
  /** @type {PendingNest[]} */
  const pending = [];
  let pendingArea = 0;

  /**
   * Queue a just-emitted directory cell for nesting when its geometry and
   * the remaining depth allow it: under a labelled header when it is large
   * enough, otherwise inside a thin frame.
   * @param {Record<string, any>} cell
   * @param {Record<string, any>} node
   */
  function considerNesting(cell, node) {
    // A folder whose children all fold into its remainder (the rollup's node
    // budget ran out at it) has nothing to show inside but one inert
    // remainder cell, so it stays a solid cell, named by its own tooltip.
    const hasChildren = Array.isArray(node.children) && node.children.length > 0;
    if (node.type !== "dir" || !hasChildren || cell.depth + 1 >= opts.nestDepth) {
      return;
    }
    const labelFits = cell.w >= opts.labelMinW && cell.h >= opts.labelMinH;
    const labelled = labelFits && cell.h >= opts.nestMinH;
    const framed = !labelFits && cell.w >= opts.frameNestMinPx && cell.h >= opts.frameNestMinPx;
    if (!labelled && !framed) {
      return;
    }
    const top = labelled ? cell.headerPx : opts.padPx;
    const inner = {
      x: cell.x + opts.padPx,
      y: cell.y + top,
      w: cell.w - 2 * opts.padPx,
      h: cell.h - top - opts.padPx,
    };
    if (inner.w < opts.minCellPx || inner.h < opts.minCellPx) {
      return;
    }
    const area = inner.w * inner.h;
    pending.push({ cell, node, inner, framed, area });
    pendingArea += area;
  }

  /**
   * Emit one directory's children into `rect` within `capacity` cells.
   * @param {Record<string, any>} dirNode
   * @param {Rect} rect
   * @param {number} depth
   * @param {number} capacity
   * @returns {number} cells emitted
   */
  function emitLevel(dirNode, rect, depth, capacity) {
    const children = Array.isArray(dirNode.children) ? dirNode.children : [];
    /** @type {WeightedItem[]} */
    const items = [];
    for (const child of children) {
      const value = nodeValue(child, opts);
      if (value > 0) {
        items.push({
          value,
          bytes:
            child.type === "dir"
              ? excludeIgnored
                ? child.unignored_size
                : child.total_size
              : child.size,
          count:
            child.type === "dir" ? (excludeIgnored ? child.unignored_files : child.total_files) : 1,
          node: child,
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
    items.sort((a, b) => b.value - a.value);

    const before = cells.length;
    const packed = packLevel(items, rect, capacity, opts.minCellPx);
    for (const p of packed.placed) {
      const node = p.item.node;
      const typography = cellTypography(p);
      const cell = {
        kind: node.type,
        name: node.name,
        path: node.path,
        x: p.x,
        y: p.y,
        w: p.w,
        h: p.h,
        depth,
        value: p.item.value,
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
        ...typography,
      };
      cells.push(cell);
      considerNesting(cell, node);
    }
    if (packed.remainder) {
      const typography = cellTypography(packed.remainder);
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
        ...typography,
      });
    }
    return cells.length - before;
  }

  emitLevel(rootNode, { x: 0, y: 0, w: viewport.w, h: viewport.h }, 0, opts.maxCells);

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
    if (emitLevel(entry.node, entry.inner, entry.cell.depth + 1, share) > 0) {
      entry.cell.nested = true;
      if (entry.framed) {
        entry.cell.framed = true;
      }
    }
  }
  return cells;
}

export {
  cellTypography,
  LAYOUT_DEFAULTS,
  layoutTree,
  packLevel,
  squarify,
  TYPOGRAPHY_DEFAULTS,
  worstAspect,
};
