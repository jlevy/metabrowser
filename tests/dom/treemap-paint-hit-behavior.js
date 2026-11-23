// Invariants of the treemap's paint list, paint order, mark ops, and hit grid.
//
// The map paints its cells on a canvas and answers the pointer from the layout's
// geometry (treemap-map.js), so what it paints, which pixels a hover lifts, and
// which cell a point is on are pure functions of the layout. These checks run
// the production modules (treemap-layout.js, treemap-paint.js, treemap-hit.js)
// on a seeded tree and compare each against a brute-force reading of the same
// geometry. Prints one summary line; exits 1 on a failed invariant.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    return;
  }
  emitWarning.call(process, warning, ...rest);
};

const repoRoot = path.resolve(process.argv[2] || ".");
const folder = path.join(repoRoot, "src/metabrowser/builtin_plugins/folder");
const failures = [];

function check(name, cond, detail) {
  if (!cond) {
    failures.push(`${name}: ${detail || "failed"}`);
  }
}

/** A seeded tree: folders of files of several types, five levels deep. */
function seededTree(fileBudget) {
  let seed = 11;
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
  };
  const exts = ["js", "ts", "py", "md", "json"];
  const budget = { n: fileBudget };
  function dir(dirPath, depth) {
    const children = [];
    let files = 0;
    let bytes = 0;
    const fileCount = Math.floor(rnd() * 40) + 3;
    const dirCount = depth < 4 ? Math.floor(rnd() * 4) + 1 : 0;
    for (let i = 0; i < fileCount && budget.n > 0; i += 1, budget.n -= 1) {
      const size = Math.floor(Math.exp(rnd() * 12)) + 1;
      const ext = exts[Math.floor(rnd() * exts.length)];
      children.push({
        type: "file",
        name: `f${i}.${ext}`,
        path: `${dirPath}/f${i}.${ext}`,
        size,
        ext,
      });
      files += 1;
      bytes += size;
    }
    for (let i = 0; i < dirCount && budget.n > 0; i += 1) {
      const child = dir(`${dirPath}/d${i}`, depth + 1);
      children.push(child);
      files += child.total_files;
      bytes += child.total_size;
    }
    return {
      type: "dir",
      name: dirPath.split("/").pop(),
      path: dirPath,
      children,
      rest: null,
      total_files: files,
      total_size: bytes,
      unignored_files: files,
      unignored_size: bytes,
      dominant_ext: "js",
    };
  }
  return dir("root", 0);
}

async function main() {
  const { layoutTree } = await import(pathToFileURL(path.join(folder, "treemap-layout.js")).href);
  const paint = await import(pathToFileURL(path.join(folder, "treemap-paint.js")).href);
  const { buildHitGrid } = await import(pathToFileURL(path.join(folder, "treemap-hit.js")).href);

  const box = { w: 480, h: 300 };
  const dpr = 2;
  const tree = seededTree(3000);
  const cells = layoutTree(tree, box, {
    metric: "files",
    includeIgnored: true,
    minCellPx: 1 / dpr,
    maxCells: 5000,
  });
  check("the seeded layout is dense", cells.length > 1000, `${cells.length} cells`);

  // ── Hit grid: the deepest cell containing a point, as a scan finds it ──────
  const grid = buildHitGrid(cells, box);
  /** @param {number} x @param {number} y */
  const scan = (x, y) => {
    let found = -1;
    for (let i = 0; i < cells.length; i += 1) {
      const c = cells[i];
      if (x >= c.x && x < c.x + c.w && y >= c.y && y < c.y + c.h) {
        found = i;
      }
    }
    return found;
  };
  let seed = 3;
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
  };
  let mismatches = 0;
  for (let k = 0; k < 4000; k += 1) {
    const x = rnd() * box.w;
    const y = rnd() * box.h;
    if (grid.lookup(x, y) !== scan(x, y)) {
      mismatches += 1;
    }
  }
  check("the grid finds the deepest cell a scan finds", mismatches === 0, `${mismatches} of 4000`);
  check(
    "a point outside the box hits nothing",
    grid.lookup(-1, 5) === -1 && grid.lookup(5, box.h) === -1,
  );
  const framed = cells.findIndex((c) => c.framed && c.inner && c.inner.x - c.x >= 1);
  if (framed >= 0) {
    const c = cells[framed];
    check(
      "a point in a folder's frame hits the folder",
      grid.lookup(c.x + 0.25, c.y + c.h / 2) === framed,
      JSON.stringify({ framed, hit: grid.lookup(c.x + 0.25, c.y + c.h / 2) }),
    );
  }
  check("one parent-first cell list is what the grid indexes", grid.entries >= cells.length);

  // ── Paint list: snapped, inside each cell, separated when large enough ──────
  const { rects, empty } = paint.paintList(cells, (c) => c.ext || c.kind, dpr);
  const snapped = cells.map((c) => paint.snapRect(c, dpr));
  check(
    "a cell whose snapped rectangle is empty paints nothing, and is counted",
    empty === snapped.filter((r) => r.w === 0 || r.h === 0).length,
    `${empty}`,
  );
  let outside = 0;
  let unseparated = 0;
  for (const r of rects) {
    const s = snapped[r.cell];
    if (r.x < s.x || r.y < s.y || r.x + r.w > s.x + s.w || r.y + r.h > s.y + s.h) {
      outside += 1;
    }
    if (
      r.tone === "fill" &&
      s.w >= paint.SEPARATOR_MIN_DEVICE_PX &&
      s.h >= paint.SEPARATOR_MIN_DEVICE_PX &&
      (r.w !== s.w - 1 || r.h !== s.h - 1)
    ) {
      unseparated += 1;
    }
  }
  check("every painted rectangle lies inside its cell", outside === 0, `${outside}`);
  check("a cell large enough draws one device pixel short, so its edge shows", unseparated === 0);
  check(
    "every nesting folder paints its interior in its edge tone",
    cells.every((c, i) => !c.nested || rects.some((r) => r.cell === i && r.tone === "edge")),
  );

  // ── Paint order: a folder, then its interior, then its children ──────────────
  const order = [];
  const ctx = {
    globalAlpha: 1,
    fillStyle: "",
    fillRect() {
      order.push(this.fillStyle);
    },
  };
  const tagged = rects.map((r, k) => ({ ...r, style: String(k) }));
  paint.paintCells(ctx, tagged, (style) => ({ fill: `f${style}`, edge: `e${style}`, alpha: 1 }));
  const position = new Map(order.map((style, k) => [style, k]));
  let misordered = 0;
  for (const r of tagged) {
    const own = position.get(`${r.tone === "edge" ? "e" : "f"}${r.style}`);
    const parent = cells[r.cell].parent;
    if (r.tone === "fill" && parent >= 0) {
      const interior = tagged.find((t) => t.cell === parent && t.tone === "edge");
      if (interior && position.get(`e${interior.style}`) > own) {
        misordered += 1;
      }
    }
    if (r.tone === "edge") {
      const fill = tagged.find((t) => t.cell === r.cell && t.tone === "fill");
      if (fill && position.get(`f${fill.style}`) > own) {
        misordered += 1;
      }
    }
  }
  check(
    "each folder paints under its interior, and its interior under its children",
    misordered === 0,
    `${misordered}`,
  );
  check("every rectangle is painted once", order.length === tagged.length);

  // ── Mark ops: the lifted pixels are exactly the marked cells' own pixels ──────
  // Each device pixel shows the deepest cell whose snapped rectangle holds it;
  // after the ops, a pixel is lifted exactly when that cell is marked.
  const W = Math.round(box.w * dpr);
  const H = Math.round(box.h * dpr);
  const owner = new Int32Array(W * H).fill(-1);
  snapped.forEach((r, i) => {
    for (let y = r.y; y < r.y + r.h; y += 1) {
      owner.fill(i, y * W + r.x, y * W + r.x + r.w);
    }
  });
  const families = ["js", "py", "md"];
  for (const family of families) {
    const marked = (i) => cells[i].ext === family;
    const ops = paint.markOps(cells, marked, dpr);
    const lifted = new Uint8Array(W * H);
    for (const op of ops) {
      for (let y = op.y; y < op.y + op.h; y += 1) {
        lifted.fill(op.op === "copy" ? 1 : 0, y * W + op.x, y * W + op.x + op.w);
      }
    }
    let wrong = 0;
    for (let p = 0; p < W * H; p += 1) {
      const expected = owner[p] >= 0 && marked(owner[p]) ? 1 : 0;
      if (lifted[p] !== expected) {
        wrong += 1;
      }
    }
    check(
      `a ${family} family's ops lift exactly its cells' own pixels`,
      wrong === 0,
      `${wrong} pixels`,
    );
  }
  const everything = paint.markOps(cells, () => true, dpr);
  check(
    "a hover that marks every cell is one copy per top-level cell",
    everything.every((op) => op.op === "copy" && cells[op.cell].parent === -1),
    `${everything.length} ops`,
  );
  check(
    "a hover that marks nothing has no ops",
    paint.markOps(cells, () => false, dpr).length === 0,
  );

  if (failures.length > 0) {
    console.error(`treemap paint and hit FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log(`treemap paint and hit OK: ${cells.length} cells, ${rects.length} rectangles`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
