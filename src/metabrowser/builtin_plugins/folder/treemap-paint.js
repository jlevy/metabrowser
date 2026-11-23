// Folder plugin — what the treemap canvas paints, and painting it.
//
// The map paints every cell on one canvas (treemap-map.js). This module turns
// a layout into a paint list, the rectangles in device pixels and the style
// each takes, and the hover's marked cells into mark ops, the rectangles the
// hover canvas copies from the paint canvas or clears. Both are pure, so the
// sessions pin them browserlessly; only `paintCells` and `applyMarkOps` touch a
// canvas, and rasterizing is the one step that needs a browser
// (docs/project/architecture/arch-parity-registry.md).
//
// A cell's edge: every cell drawn on a page of cells has had a 1 px edge in a
// stronger tone than its fill (styles.css, .tm-cell and .tm-type-fill), which
// keeps two files of one type side by side two cells. Here a nesting folder
// paints its children's region in its edge tone, and each child large enough
// draws one device pixel short on its right and bottom, so the edge tone shows
// between neighbours; a smaller child draws edge to edge. The interior reaches
// one device pixel past the children on the top and left (interiorRect), so the
// first row and column have an edge against the folder's header and frame.

/**
 * A cell at least this many device pixels on each side draws one device pixel
 * short of its rectangle, so its edge shows. Below it a pixel of edge is a
 * third or more of the cell, and the cell draws edge to edge: at that size a run
 * of same-type files reads as texture, as it does in WinDirStat's flat preset.
 */
export const SEPARATOR_MIN_DEVICE_PX = 3;

/**
 * @typedef {{x: number, y: number, w: number, h: number}} DeviceRect
 * @typedef {DeviceRect & {cell: number, style: string, tone: "fill" | "edge", depth: number}} PaintRect
 * @typedef {{fill: string, edge: string, alpha: number}} PaintStyle
 * @typedef {{op: "copy" | "clear", cell: number} & DeviceRect} MarkOp
 */

/**
 * A rectangle in CSS pixels, snapped to the device pixel grid. Edges round to
 * the nearest device pixel, so neighbours share an edge and leave no hairline.
 * @param {Readonly<Record<string, any>>} rect  x, y, w, and h in CSS pixels
 * @param {number} dpr
 * @returns {DeviceRect}
 */
export function snapRect(rect, dpr) {
  const x0 = Math.round(rect.x * dpr);
  const y0 = Math.round(rect.y * dpr);
  const x1 = Math.round((rect.x + rect.w) * dpr);
  const y1 = Math.round((rect.y + rect.h) * dpr);
  return { x: x0, y: y0, w: Math.max(0, x1 - x0), h: Math.max(0, y1 - y0) };
}

/**
 * The rectangle a cell's fill covers, in device pixels: its snapped rectangle,
 * one device pixel short on the right and bottom when it is at least
 * `separatorMinDevicePx` on each side, so its edge shows; null when it snaps
 * to nothing. Every pixel of the paint canvas shows the deepest cell whose fill
 * covers it, or the surface, so the hover's lift (markOps) and the pointer
 * (treemap-hit.js) take each pixel from this rectangle too.
 * @param {Readonly<Record<string, any>>} cell  x, y, w, and h in CSS pixels
 * @param {number} dpr
 * @param {number} [separatorMinDevicePx]
 * @returns {DeviceRect | null}
 */
export function fillRect(cell, dpr, separatorMinDevicePx = SEPARATOR_MIN_DEVICE_PX) {
  const snapped = snapRect(cell, dpr);
  if (snapped.w === 0 || snapped.h === 0) {
    return null;
  }
  const separated = snapped.w >= separatorMinDevicePx && snapped.h >= separatorMinDevicePx;
  return separated ? { ...snapped, w: snapped.w - 1, h: snapped.h - 1 } : snapped;
}

/**
 * The part of `a` inside `b`, or null.
 * @param {DeviceRect} a
 * @param {DeviceRect} b
 * @returns {DeviceRect | null}
 */
function intersect(a, b) {
  const x = Math.max(a.x, b.x);
  const y = Math.max(a.y, b.y);
  const w = Math.min(a.x + a.w, b.x + b.w) - x;
  const h = Math.min(a.y + a.h, b.y + b.h) - y;
  return w > 0 && h > 0 ? { x, y, w, h } : null;
}

/**
 * A nesting folder's interior: its children's region, one device pixel more on
 * the top and on the left wherever the folder's header or frame keeps at least
 * one of its own pixels there. Children draw short only on their right and
 * bottom, so without that pixel the first row met the header, and the first
 * column the frame, with no edge between (mb-39p0).
 * @param {DeviceRect} inner  the children's region, snapped
 * @param {DeviceRect} fill  the folder's own fill
 * @returns {DeviceRect}
 */
function interiorRect(inner, fill) {
  const top = inner.y - fill.y >= 2 ? 1 : 0;
  const left = inner.x - fill.x >= 2 ? 1 : 0;
  return { x: inner.x - left, y: inner.y - top, w: inner.w + left, h: inner.h + top };
}

/**
 * The paint list for `cells`, parent first: each cell's fill, and before a
 * nesting folder's children its interior in the folder's edge tone, inside its
 * fill, so a folder drawn edge to edge keeps its own separator. A cell whose
 * snapped rectangle is empty paints nothing.
 * @param {ReadonlyArray<Record<string, any>>} cells  layoutTree's output
 * @param {(cell: Record<string, any>) => string} styleOf  the cell's style key
 * @param {number} dpr
 * @param {number} [separatorMinDevicePx]
 * @returns {{rects: PaintRect[], empty: number}}
 */
export function paintList(cells, styleOf, dpr, separatorMinDevicePx = SEPARATOR_MIN_DEVICE_PX) {
  /** @type {PaintRect[]} */
  const rects = [];
  let empty = 0;
  for (let i = 0; i < cells.length; i += 1) {
    const cell = cells[i];
    const fill = fillRect(cell, dpr, separatorMinDevicePx);
    if (!fill) {
      empty += 1;
      continue;
    }
    const style = styleOf(cell);
    rects.push({ ...fill, cell: i, style, tone: "fill", depth: cell.depth });
    if (cell.nested && cell.inner) {
      const inner = intersect(interiorRect(snapRect(cell.inner, dpr), fill), fill);
      if (inner) {
        rects.push({ ...inner, cell: i, style, tone: "edge", depth: cell.depth });
      }
    }
  }
  return { rects, empty };
}

/**
 * Paint `rects` on `ctx`, whose transform is the identity (device pixels):
 * depth by depth, so a folder lies under its children, and within a depth one
 * `fillStyle` at a time, which halves WebKit's cost at 50k rectangles against a
 * style change per rectangle (research-2026-11-22-dense-treemap-rendering.md).
 * A folder's interior comes after the folder's own fill and before its
 * children, which are one depth deeper.
 * @param {CanvasRenderingContext2D} ctx
 * @param {ReadonlyArray<PaintRect>} rects
 * @param {(style: string) => PaintStyle} resolve
 */
export function paintCells(ctx, rects, resolve) {
  /** @type {Map<number, Map<string, PaintRect[]>>} */
  const byDepth = new Map();
  for (const rect of rects) {
    // An interior paints after every fill of its depth, so a sibling's fill
    // never covers it; it is one rank above its folder's depth.
    const rank = rect.depth * 2 + (rect.tone === "edge" ? 1 : 0);
    let groups = byDepth.get(rank);
    if (!groups) {
      groups = new Map();
      byDepth.set(rank, groups);
    }
    const key = `${rect.style}\u0000${rect.tone}`;
    const group = groups.get(key);
    if (group) {
      group.push(rect);
    } else {
      groups.set(key, [rect]);
    }
  }
  for (const rank of [...byDepth.keys()].sort((a, b) => a - b)) {
    for (const group of /** @type {Map<string, PaintRect[]>} */ (byDepth.get(rank)).values()) {
      const style = resolve(group[0].style);
      ctx.globalAlpha = style.alpha;
      ctx.fillStyle = group[0].tone === "edge" ? style.edge : style.fill;
      for (const rect of group) {
        ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
      }
    }
  }
  ctx.globalAlpha = 1;
}

/**
 * The ops that put the marked cells on the hover canvas: walking the cells
 * parent first, copy a marked cell's fill whose parent is not marked, and clear
 * an unmarked cell's fill whose parent is. A copy brings the cell's descendants
 * with it, so the clears take back those that are not marked, and a marked
 * folder lifts without its unmarked children but with the edges between them,
 * which are its own pixels. A family that marks every cell is one copy per
 * top-level cell.
 * @param {ReadonlyArray<Record<string, any>>} cells
 * @param {(index: number) => boolean} marked
 * @param {number} dpr
 * @returns {MarkOp[]}
 */
export function markOps(cells, marked, dpr) {
  /** @type {MarkOp[]} */
  const ops = [];
  /** @type {boolean[]} */
  const state = new Array(cells.length);
  for (let i = 0; i < cells.length; i += 1) {
    const parent = cells[i].parent;
    const parentMarked = parent >= 0 ? state[parent] : false;
    const own = marked(i);
    state[i] = own;
    if (own !== parentMarked) {
      const rect = fillRect(cells[i], dpr);
      if (rect) {
        ops.push({ op: own ? "copy" : "clear", cell: i, ...rect });
      }
    }
  }
  return ops;
}

/**
 * Apply mark ops to the hover canvas's context from the paint canvas.
 * @param {CanvasRenderingContext2D} ctx
 * @param {CanvasImageSource} source
 * @param {ReadonlyArray<MarkOp>} ops
 */
export function applyMarkOps(ctx, source, ops) {
  for (const op of ops) {
    if (op.op === "copy") {
      ctx.clearRect(op.x, op.y, op.w, op.h);
      ctx.drawImage(source, op.x, op.y, op.w, op.h, op.x, op.y, op.w, op.h);
    } else {
      ctx.clearRect(op.x, op.y, op.w, op.h);
    }
  }
}
