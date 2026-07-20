// Folder plugin — pure treemap geometry (no DOM, no fetch).
//
// Classic script loaded via manifest extra_scripts BEFORE index.js; it
// exposes one global, `MetabrowserTreemapLayout`, that index.js and the
// Node vm tests consume. Squarified layout per Bruls, Huizing & van
// Wijk ("Squarified Treemaps", 2000): rows packed along the shorter
// side of the free rectangle, accepting an item into the current row
// only while it improves the row's worst aspect ratio.
//
// `layoutTree` walks a /api/rollup node tree (or the envelope
// ext_tallies in type-grouping mode) and returns a flat array of
// positioned cells. Bounds: cells below `minCellPx` in either
// dimension merge into their parent's rest cell, and nesting stops
// once `maxCells` cells exist, so pathological trees cannot flood the
// DOM.

(() => {
  /**
   * Layout bounds and nesting thresholds. The renderer can override any
   * of these via the `opts` argument; tests pin them explicitly.
   */
  const LAYOUT_DEFAULTS = {
    /** Cells smaller than this (either dimension, px) merge into the rest cell. */
    minCellPx: 4,
    /** Hard cap on emitted cells across all nesting levels. */
    maxCells: 800,
    /** Nested levels drawn inside directory cells (1 = flat). */
    nestDepth: 2,
    /** Directory cells narrower/shorter than this never nest children. */
    nestMinW: 72,
    nestMinH: 48,
    /** Reserved label strip at the top of a nested directory cell (px). */
    headerPx: 16,
    /** Inner padding between a directory cell border and its children (px). */
    padPx: 2,
  };

  /**
   * @typedef {{x: number, y: number, w: number, h: number}} Rect
   * @typedef {{value: number} & Record<string, any>} WeightedItem
   */

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
    const hidden = opts.ignored === "hidden";
    if (node.type === "dir") {
      if (opts.metric === "files") {
        return hidden ? node.unignored_files : node.total_files;
      }
      return hidden ? node.unignored_size : node.total_size;
    }
    if (hidden && node.gitignored) {
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
    const hidden = opts.ignored === "hidden";
    if (opts.metric === "files") {
      return hidden ? rest.unignored_files : rest.files;
    }
    return hidden ? rest.unignored_size : rest.size;
  }

  /**
   * Flatten a rollup tree (or ext tallies) into positioned cells.
   *
   * @param {Record<string, any>} rootNode  /api/rollup `node`
   * @param {{w: number, h: number}} viewport
   * @param {Record<string, any>} options   layout + view options:
   *   metric "size"|"files", grouping "folder"|"type",
   *   ignored "shown"|"dimmed"|"hidden", extTallies (type grouping),
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

    if (opts.grouping === "type") {
      const tallies = Array.isArray(opts.extTallies) ? opts.extTallies : [];
      const hidden = opts.ignored === "hidden";
      const items = tallies
        .map((row) => ({
          value: opts.metric === "files" ? (hidden ? row[3] : row[1]) : hidden ? row[4] : row[2],
          ext: row[0],
          files: hidden ? row[3] : row[1],
          bytes: hidden ? row[4] : row[2],
        }))
        .filter((it) => it.value > 0)
        .sort((a, b) => b.value - a.value);
      for (const p of squarify(items, { x: 0, y: 0, w: viewport.w, h: viewport.h })) {
        if (p.w < opts.minCellPx || p.h < opts.minCellPx) {
          continue;
        }
        cells.push({
          kind: "ext",
          name: p.item.ext === "" ? "other" : p.item.ext,
          ext: p.item.ext,
          path: "",
          x: p.x,
          y: p.y,
          w: p.w,
          h: p.h,
          depth: 0,
          value: p.item.value,
          files: p.item.files,
          bytes: p.item.bytes,
        });
      }
      return cells;
    }

    /**
     * Emit one directory's children into `rect`; recurse into large
     * directory cells while depth and cell budget allow.
     * @param {Record<string, any>} dirNode
     * @param {Rect} rect
     * @param {number} depth
     */
    function emitLevel(dirNode, rect, depth) {
      const children = Array.isArray(dirNode.children) ? dirNode.children : [];
      /** @type {WeightedItem[]} */
      const items = [];
      const restVal = dirNode.rest ? restValue(dirNode.rest, opts) : 0;
      const restCount = dirNode.rest
        ? opts.ignored === "hidden"
          ? dirNode.rest.unignored_files
          : dirNode.rest.files
        : 0;
      for (const child of children) {
        const value = nodeValue(child, opts);
        if (value > 0) {
          items.push({ value, node: child });
        }
      }
      items.sort((a, b) => b.value - a.value);
      if (restVal > 0) {
        items.push({ value: restVal, node: null, rest: true });
      }

      const placed = squarify(items, rect);
      /** @type {{cell: Record<string, any>, node: Record<string, any>}[]} */
      const nestable = [];
      let culledValue = 0;
      let culledCount = 0;
      /** @type {Record<string, any> | null} */
      let restCell = null;

      for (const p of placed) {
        if (cells.length >= opts.maxCells) {
          break;
        }
        const tooSmall = p.w < opts.minCellPx || p.h < opts.minCellPx;
        if (p.item.rest || tooSmall) {
          if (tooSmall) {
            culledValue += p.item.value;
            culledCount += 1;
            continue;
          }
          restCell = {
            kind: "rest",
            name: "…",
            path: dirNode.path,
            x: p.x,
            y: p.y,
            w: p.w,
            h: p.h,
            depth,
            value: p.item.value,
            files: restCount,
          };
          cells.push(restCell);
          continue;
        }
        const node = p.item.node;
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
          mtime: node.mtime,
          ext: node.type === "dir" ? node.dominant_ext : node.ext,
          gitignored: !!node.gitignored,
          state: node.state,
        };
        cells.push(cell);
        if (
          node.type === "dir" &&
          Array.isArray(node.children) &&
          depth + 1 < opts.nestDepth &&
          p.w >= opts.nestMinW &&
          p.h >= opts.nestMinH &&
          cells.length < opts.maxCells
        ) {
          nestable.push({ cell, node });
        }
      }

      // Fold culled slivers into the rest cell so their share of the
      // area is not silently missing from the picture.
      if (culledValue > 0 && restCell) {
        restCell.value += culledValue;
        restCell.files = (restCell.files || 0) + culledCount;
      }

      for (const entry of nestable) {
        const inner = {
          x: entry.cell.x + opts.padPx,
          y: entry.cell.y + opts.headerPx,
          w: entry.cell.w - 2 * opts.padPx,
          h: entry.cell.h - opts.headerPx - opts.padPx,
        };
        if (inner.w >= opts.minCellPx && inner.h >= opts.minCellPx) {
          entry.cell.nested = true;
          emitLevel(entry.node, inner, depth + 1);
        }
      }
    }

    emitLevel(rootNode, { x: 0, y: 0, w: viewport.w, h: viewport.h }, 0);
    return cells;
  }

  const api = { LAYOUT_DEFAULTS, squarify, layoutTree, worstAspect };
  /** @type {any} */ (globalThis).MetabrowserTreemapLayout = api;
})();
