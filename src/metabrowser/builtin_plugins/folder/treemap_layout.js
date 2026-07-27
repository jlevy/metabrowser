// Folder plugin — pure treemap geometry (no DOM, no fetch).
//
// Classic script loaded via manifest extra_scripts BEFORE index.js; it
// exposes one global, `MetabrowserTreemapLayout`, that index.js and the
// Node vm tests consume. Squarified layout per Bruls, Huizing & van
// Wijk ("Squarified Treemaps", 2000): rows packed along the shorter
// side of the free rectangle, accepting an item into the current row
// only while it improves the row's worst aspect ratio.
//
// `layoutTree` first assigns every available rollup node a stable
// rectangle in a recursive "world", then projects an arbitrary folder
// camera into the viewport. The projection traverses breadth-first,
// clips outside the camera (plus overscan), and stops at the requested
// visible depth or DOM-cell budget. A zoom therefore changes only the
// camera: shared nodes retain the same world geometry at every
// intermediate scale, while deeper detail can fill in after motion.

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
    /** Visible recursive levels (1 = direct children only). */
    nestDepth: 6,
    /** Projected directory cells narrower/shorter than this stay at the current LOD. */
    nestMinW: 64,
    nestMinH: 44,
    /** Stable world-space fractions reserved for a directory label and border. */
    headerRatio: 0.03,
    padRatio: 0.005,
    /** Retained scenes may hold two bounded server-rollup envelopes;
     * repeat that combined bound here so supplied trees cannot flood geometry. */
    maxWorldCells: 2400,
    /** Defensive recursion bound above the server's supported depth. */
    maxWorldDepth: 64,
    /** Keep near-edge cells mounted during camera motion. */
    overscanPx: 24,
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
   *   remainder: {x: number, y: number, w: number, h: number, value: number, count: number} | null}}
   */
  function packLevel(items, rect, capacity, minPx) {
    /** @type {{item: WeightedItem, x: number, y: number, w: number, h: number}[]} */
    const none = [];
    if (capacity <= 0 || items.length === 0 || rect.w <= 0 || rect.h <= 0) {
      return { placed: none, remainder: null };
    }
    let remainderValue = 0;
    let remainderCount = 0;
    /** @type {WeightedItem[]} */
    let survivors = [];
    for (const it of items) {
      if (it.rest) {
        remainderValue += it.value;
        remainderCount += Number(it.count) || 0;
      } else if (it.value > 0) {
        survivors.push(it);
      }
    }

    /** @param {WeightedItem[]} kept @param {WeightedItem[]} cut */
    const foldCut = (kept, cut) => {
      for (const it of cut) {
        remainderValue += it.value;
        remainderCount += Number(it.count) || 0;
      }
      survivors = kept;
    };

    // Capacity pass: reserve one slot for the remainder when anything
    // must fold into it.
    const needsRemainderSlot = () => remainderValue > 0 || false;
    let limit = capacity - (needsRemainderSlot() ? 1 : 0);
    if (survivors.length > limit) {
      limit = Math.max(0, capacity - 1);
      foldCut(survivors.slice(0, limit), survivors.slice(limit));
    }

    /** @returns {{item: WeightedItem, x: number, y: number, w: number, h: number}[]} */
    const layoutOnce = () => {
      /** @type {WeightedItem[]} */
      const withRemainder = survivors.slice();
      if (remainderValue > 0) {
        withRemainder.push({ value: remainderValue, rest: true });
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

    /** @type {{x: number, y: number, w: number, h: number, value: number, count: number} | null} */
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
        };
      } else {
        emitted.push(p);
      }
    }
    return { placed: emitted, remainder };
  }

  /**
   * Uniform affine transform that covers the viewport with a world
   * rectangle and clips the excess on its longer axis. Preserving
   * aspect ratio keeps the treemap geometry stable at every camera
   * position. The compositor uses the same numbers as the settled
   * layout projection, avoiding a visual snap at route handoff.
   *
   * @param {Rect} focus
   * @param {{w: number, h: number}} viewport
   * @returns {{scaleX: number, scaleY: number, translateX: number, translateY: number}}
   */
  function focusTransform(focus, viewport) {
    const scale =
      focus.w > 0 && focus.h > 0 ? Math.max(viewport.w / focus.w, viewport.h / focus.h) : 1;
    return {
      scaleX: scale,
      scaleY: scale,
      translateX: (viewport.w - focus.w * scale) / 2 - focus.x * scale,
      translateY: (viewport.h - focus.h * scale) / 2 - focus.y * scale,
    };
  }

  /**
   * Project one world rectangle through a camera transform.
   * @param {Rect} rect
   * @param {{scaleX: number, scaleY: number, translateX: number, translateY: number}} transform
   * @returns {Rect}
   */
  function projectRect(rect, transform) {
    return {
      x: rect.x * transform.scaleX + transform.translateX,
      y: rect.y * transform.scaleY + transform.translateY,
      w: rect.w * transform.scaleX,
      h: rect.h * transform.scaleY,
    };
  }

  /**
   * Child coordinate space inside a directory. Header and padding
   * shrink proportionally for tiny world cells, so recursion never
   * collapses merely because an ancestor is small before zoom.
   * @param {Rect} rect
   * @param {Record<string, any>} opts
   * @returns {Rect}
   */
  function childRect(rect, opts) {
    const padX = rect.w * opts.padRatio;
    const padY = rect.h * opts.padRatio;
    const header = rect.h * opts.headerRatio;
    return {
      x: rect.x + padX,
      y: rect.y + header,
      w: Math.max(0, rect.w - 2 * padX),
      h: Math.max(0, rect.h - header - padY),
    };
  }

  /** @param {string} path @returns {string} */
  function normalizePath(path) {
    return String(path || "").replace(/^\/+|\/+$/g, "");
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
          count: hidden ? row[3] : row[1],
          // The server's remainder tally row (ext "") seeds the rest cell.
          rest: row[0] === "",
          ext: row[0],
          files: hidden ? row[3] : row[1],
          bytes: hidden ? row[4] : row[2],
        }))
        .filter((it) => it.value > 0)
        .sort((a, b) => b.value - a.value);
      const packedTypes = packLevel(
        items,
        { x: 0, y: 0, w: viewport.w, h: viewport.h },
        opts.maxCells,
        opts.minCellPx,
      );
      for (const p of packedTypes.placed) {
        cells.push({
          kind: "ext",
          name: p.item.ext,
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
      if (packedTypes.remainder) {
        cells.push({
          kind: "rest",
          name: "other",
          ext: "",
          path: "",
          x: packedTypes.remainder.x,
          y: packedTypes.remainder.y,
          w: packedTypes.remainder.w,
          h: packedTypes.remainder.h,
          depth: 0,
          value: packedTypes.remainder.value,
          files: packedTypes.remainder.count,
          bytes: packedTypes.remainder.value,
        });
      }
      return cells;
    }

    /**
     * Geometry record retained in world coordinates.
     * @typedef {{
     *   cell: Rect & Record<string, any>,
     *   node: Record<string, any> | null,
     *   inner: Rect | null,
     *   children: WorldCell[]
     * }} WorldCell
     */

    let worldCellCount = 0;
    /** @type {Map<string, {node: Record<string, any>, rect: Rect, children: WorldCell[]}>} */
    const directories = new Map();
    const requestedFocus = normalizePath(opts.focusPath);

    /**
     * Assign stable recursive world rectangles. Only the scene root
     * applies pixel sliver culling: deeper nodes must keep geometry so
     * they can become visible after a camera zoom.
     *
     * @param {Record<string, any>} dirNode
     * @param {Rect} rect
     * @param {number} worldDepth
     * @param {boolean} sceneRoot
     * @returns {WorldCell[]}
     */
    function buildWorld(dirNode, rect, worldDepth, sceneRoot) {
      const children = Array.isArray(dirNode.children) ? dirNode.children : [];
      /** @type {WeightedItem[]} */
      const items = [];
      const hidden = opts.ignored === "hidden";
      for (const child of children) {
        const value = nodeValue(child, opts);
        if (value > 0) {
          items.push({
            value,
            count: child.type === "dir" ? (hidden ? child.unignored_files : child.total_files) : 1,
            node: child,
          });
        }
      }
      const restVal = dirNode.rest ? restValue(dirNode.rest, opts) : 0;
      if (restVal > 0) {
        items.push({
          value: restVal,
          count: hidden ? dirNode.rest.unignored_files : dirNode.rest.files,
          rest: true,
        });
      }
      items.sort((a, b) => b.value - a.value);

      const capacity = sceneRoot ? opts.maxCells : Math.max(0, opts.maxWorldCells - worldCellCount);
      const packed = packLevel(items, rect, capacity, sceneRoot ? opts.minCellPx : 0);
      /** @type {WorldCell[]} */
      const worldCells = [];
      for (const p of packed.placed) {
        const node = p.item.node;
        const cell = {
          kind: node.type,
          name: node.name,
          path: node.path,
          x: p.x,
          y: p.y,
          w: p.w,
          h: p.h,
          depth: worldDepth,
          value: p.item.value,
          // Real magnitudes regardless of the active metric, so labels
          // can always show true bytes/counts.
          bytes: node.type === "dir" ? (hidden ? node.unignored_size : node.total_size) : node.size,
          files: p.item.count,
          mtime: node.mtime,
          ext: node.type === "dir" ? node.dominant_ext : node.ext,
          gitignored: !!node.gitignored,
          state: node.state,
        };
        worldCellCount += 1;
        const inner = node.type === "dir" ? childRect(cell, opts) : null;
        /** @type {WorldCell} */
        const worldCell = { cell, node, inner, children: [] };
        worldCells.push(worldCell);
      }
      if (packed.remainder) {
        worldCellCount += 1;
        worldCells.push({
          cell: {
            kind: "rest",
            name: "…",
            path: dirNode.path,
            x: packed.remainder.x,
            y: packed.remainder.y,
            w: packed.remainder.w,
            h: packed.remainder.h,
            depth: worldDepth,
            value: packed.remainder.value,
            files: packed.remainder.count,
          },
          node: null,
          inner: null,
          children: [],
        });
      }
      const nestable = worldCells
        .filter(
          (record) =>
            record.node?.type === "dir" &&
            Array.isArray(record.node.children) &&
            record.inner &&
            record.inner.w > 0 &&
            record.inner.h > 0,
        )
        .sort((a, b) => {
          const aPath = normalizePath(a.node?.path);
          const bPath = normalizePath(b.node?.path);
          const aFocus = requestedFocus === aPath || requestedFocus.startsWith(`${aPath}/`);
          const bFocus = requestedFocus === bPath || requestedFocus.startsWith(`${bPath}/`);
          return Number(bFocus) - Number(aFocus);
        });
      for (const record of nestable) {
        if (
          worldDepth + 1 < opts.maxWorldDepth &&
          worldCellCount < opts.maxWorldCells &&
          record.node &&
          record.inner
        ) {
          record.children = buildWorld(record.node, record.inner, worldDepth + 1, false);
        }
        if (record.node && record.inner) {
          directories.set(normalizePath(record.node.path), {
            node: record.node,
            rect: record.inner,
            children: record.children,
          });
        }
      }
      return worldCells;
    }

    const worldRoot = { x: 0, y: 0, w: viewport.w, h: viewport.h };
    const worldChildren = buildWorld(rootNode, worldRoot, 0, true);
    const rootPath = normalizePath(rootNode.path);
    directories.set(rootPath, { node: rootNode, rect: worldRoot, children: worldChildren });

    const focus = directories.get(requestedFocus) || directories.get(rootPath);
    if (!focus) {
      return cells;
    }
    const camera = focus.rect;
    const transform = focusTransform(camera, viewport);
    const overscan = Math.max(0, Number(opts.overscanPx) || 0);

    /** @param {Rect} rect @returns {boolean} */
    function intersectsViewport(rect) {
      return (
        rect.x + rect.w >= -overscan &&
        rect.y + rect.h >= -overscan &&
        rect.x <= viewport.w + overscan &&
        rect.y <= viewport.h + overscan
      );
    }

    /**
     * Materialize a projected LOD level. All candidates at one depth
     * compete by projected area before any deeper branch is visited,
     * preventing a single early subtree from consuming the DOM budget.
     *
     * @param {WorldCell[]} candidates
     * @param {number} visibleDepth
     * @returns {WorldCell[]} directory records eligible for the next level
     */
    function emitVisibleLevel(candidates, visibleDepth) {
      const projected = candidates
        .map((record) => ({
          record,
          rect: projectRect(record.cell, transform),
          inner: record.inner ? projectRect(record.inner, transform) : null,
        }))
        .filter((entry) => intersectsViewport(entry.rect))
        .sort((a, b) => b.rect.w * b.rect.h - a.rect.w * a.rect.h);
      /** @type {WorldCell[]} */
      const next = [];
      for (const entry of projected) {
        if (cells.length >= opts.maxCells) {
          break;
        }
        const cell = Object.assign({}, entry.record.cell, entry.rect, {
          depth: visibleDepth,
        });
        if (entry.inner) {
          cell.inner = entry.inner;
        }
        cells.push(cell);
        entry.record.cell.projectedCell = cell;
        if (
          entry.record.children.length > 0 &&
          visibleDepth + 1 < opts.nestDepth &&
          entry.rect.w >= opts.nestMinW &&
          entry.rect.h >= opts.nestMinH
        ) {
          next.push(entry.record);
        }
      }
      return next;
    }

    let depth = 0;
    let frontier = emitVisibleLevel(focus.children, depth);
    while (frontier.length > 0 && cells.length < opts.maxCells && depth + 1 < opts.nestDepth) {
      const candidates = frontier.flatMap((record) => record.children);
      depth += 1;
      const next = emitVisibleLevel(candidates, depth);
      for (const record of frontier) {
        const parentCell = record.cell.projectedCell;
        if (
          parentCell &&
          record.children.some((child) => child.cell.projectedCell?.depth === depth)
        ) {
          parentCell.nested = true;
        }
      }
      frontier = next;
    }
    // Projection bookkeeping is transient and must not leak into the
    // next layout call if a caller reuses a node tree.
    for (const record of directories.values()) {
      for (const child of record.children) {
        delete child.cell.projectedCell;
      }
    }
    return cells;
  }

  const api = {
    LAYOUT_DEFAULTS,
    squarify,
    packLevel,
    focusTransform,
    projectRect,
    layoutTree,
    worstAspect,
  };
  /** @type {any} */ (globalThis).MetabrowserTreemapLayout = api;
})();
