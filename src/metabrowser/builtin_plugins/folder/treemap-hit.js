// Folder plugin — which treemap cell is under a point (no DOM).
//
// The map paints its cells on a canvas, which says nothing about what the
// pointer is over, so the map answers from the layout's own geometry. A pixel
// of the canvas shows the deepest cell whose fill covers it (fillRect in
// treemap-paint.js, in device pixels), so a point is looked up as the device
// pixel it falls in, against the same rectangles: the cell the pointer names is
// the cell painted under it, however its edges round. After each layout the map
// builds a uniform grid of buckets over the drawable box; each bucket lists the
// cells whose fill overlaps it. A cell is emitted after its parent
// (treemap-layout.js), so of the cells covering a pixel, which form one chain of
// ancestors, the deepest is the one with the highest index.
//
// WinDirStat hit-tests its treemap the same way, with 16 px buckets
// (docs/project/research/research-2026-11-22-dense-treemap-rendering.md):
// measured there over 100k rectangles, a lookup takes under 2 µs in WebKit and
// the grid builds in about 2 ms, where a linear scan takes 0.41 ms a lookup.

import { fillRect } from "./treemap-paint.js";

/** Bucket side, in CSS pixels: WinDirStat's, measured as above. */
export const HIT_BUCKET_PX = 16;

/**
 * @typedef {{lookup: (x: number, y: number) => number, buckets: number, entries: number}} HitGrid
 */

/**
 * Build the grid for `cells` laid out in a `box.w` by `box.h` box and painted
 * at `dpr` device pixels a CSS pixel.
 * @param {ReadonlyArray<Readonly<Record<string, any>>>} cells  x, y, w, and h in CSS
 *   pixels, parent first, as layoutTree emits them
 * @param {{w: number, h: number}} box
 * @param {number} dpr
 * @param {number} [bucketPx]
 * @returns {HitGrid}
 */
export function buildHitGrid(cells, box, dpr, bucketPx = HIT_BUCKET_PX) {
  const bucket = Math.max(1, Math.round(bucketPx * dpr));
  const width = Math.round(box.w * dpr);
  const height = Math.round(box.h * dpr);
  const cols = Math.max(1, Math.ceil(width / bucket));
  const rows = Math.max(1, Math.ceil(height / bucket));
  /** @type {number[][]} */
  const buckets = Array.from({ length: cols * rows }, () => []);
  /** @type {Array<import("./treemap-paint.js").DeviceRect | null>} */
  const fills = cells.map((cell) => fillRect(cell, dpr));
  let entries = 0;
  for (let i = 0; i < cells.length; i += 1) {
    const rect = fills[i];
    if (!rect) {
      continue;
    }
    const c0 = Math.max(0, Math.floor(rect.x / bucket));
    const c1 = Math.min(cols - 1, Math.floor((rect.x + rect.w - 1) / bucket));
    const r0 = Math.max(0, Math.floor(rect.y / bucket));
    const r1 = Math.min(rows - 1, Math.floor((rect.y + rect.h - 1) / bucket));
    for (let r = r0; r <= r1; r += 1) {
      for (let c = c0; c <= c1; c += 1) {
        // Indexes go in ascending order, so a lookup can scan from the end.
        buckets[r * cols + c].push(i);
        entries += 1;
      }
    }
  }

  /**
   * The index of the deepest cell painted at (x, y), in CSS pixels, or -1 for
   * none: the cell whose fill covers the device pixel the point falls in.
   * @param {number} x
   * @param {number} y
   * @returns {number}
   */
  function lookup(x, y) {
    const px = Math.floor(x * dpr);
    const py = Math.floor(y * dpr);
    if (!(px >= 0 && py >= 0 && px < width && py < height)) {
      return -1;
    }
    const list = buckets[Math.floor(py / bucket) * cols + Math.floor(px / bucket)];
    if (!list) {
      return -1;
    }
    for (let k = list.length - 1; k >= 0; k -= 1) {
      const rect = /** @type {import("./treemap-paint.js").DeviceRect} */ (fills[list[k]]);
      if (px >= rect.x && px < rect.x + rect.w && py >= rect.y && py < rect.y + rect.h) {
        return list[k];
      }
    }
    return -1;
  }

  return Object.freeze({ lookup, buckets: buckets.length, entries });
}
