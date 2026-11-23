// Folder plugin — which treemap cell is under a point (no DOM).
//
// The map paints its cells on a canvas, which says nothing about what the
// pointer is over, so the map answers from the layout's own geometry. After
// each layout it builds a uniform grid of buckets over the drawable box; each
// bucket lists the cells that overlap it. A cell is emitted after its parent
// (treemap-layout.js), so of the cells containing a point, which form one
// chain of ancestors, the deepest is the one with the highest index.
//
// WinDirStat hit-tests its treemap the same way, with 16 px buckets
// (docs/project/research/research-2026-11-22-dense-treemap-rendering.md):
// measured there over 100k rectangles, a lookup takes under 2 µs in WebKit and
// the grid builds in about 2 ms, where a linear scan takes 0.41 ms a lookup.

/** Bucket side, in CSS pixels: WinDirStat's, measured as above. */
export const HIT_BUCKET_PX = 16;

/**
 * @typedef {{lookup: (x: number, y: number) => number, buckets: number, entries: number}} HitGrid
 */

/**
 * Build the grid for `cells` laid out in a `box.w` by `box.h` box.
 * @param {ReadonlyArray<Readonly<Record<string, any>>>} cells  x, y, w, and h in CSS
 *   pixels, parent first, as layoutTree emits them
 * @param {{w: number, h: number}} box
 * @param {number} [bucketPx]
 * @returns {HitGrid}
 */
export function buildHitGrid(cells, box, bucketPx = HIT_BUCKET_PX) {
  const cols = Math.max(1, Math.ceil(box.w / bucketPx));
  const rows = Math.max(1, Math.ceil(box.h / bucketPx));
  /** @type {number[][]} */
  const buckets = Array.from({ length: cols * rows }, () => []);
  let entries = 0;
  for (let i = 0; i < cells.length; i += 1) {
    const cell = cells[i];
    if (!(cell.w > 0 && cell.h > 0)) {
      continue;
    }
    const c0 = Math.max(0, Math.floor(cell.x / bucketPx));
    const c1 = Math.min(cols - 1, Math.floor((cell.x + cell.w) / bucketPx));
    const r0 = Math.max(0, Math.floor(cell.y / bucketPx));
    const r1 = Math.min(rows - 1, Math.floor((cell.y + cell.h) / bucketPx));
    for (let r = r0; r <= r1; r += 1) {
      for (let c = c0; c <= c1; c += 1) {
        // Indexes go in ascending order, so a lookup can scan from the end.
        buckets[r * cols + c].push(i);
        entries += 1;
      }
    }
  }

  /**
   * The index of the deepest cell containing (x, y), or -1 for none. A cell
   * holds its left and top edges and not its right and bottom ones, so a point
   * on a shared edge belongs to exactly one of two neighbours.
   * @param {number} x
   * @param {number} y
   * @returns {number}
   */
  function lookup(x, y) {
    if (!(x >= 0 && y >= 0 && x < box.w && y < box.h)) {
      return -1;
    }
    const bucket = buckets[Math.floor(y / bucketPx) * cols + Math.floor(x / bucketPx)];
    if (!bucket) {
      return -1;
    }
    for (let k = bucket.length - 1; k >= 0; k -= 1) {
      const cell = cells[bucket[k]];
      if (x >= cell.x && x < cell.x + cell.w && y >= cell.y && y < cell.y + cell.h) {
        return bucket[k];
      }
    }
    return -1;
  }

  return Object.freeze({ lookup, buckets: buckets.length, entries });
}
