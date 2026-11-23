// Invariants of the treemap's paint list, paint order, mark ops, and hit grid.
//
// The map paints its cells on a canvas and answers the pointer from the layout's
// geometry (treemap-map.js), so what it paints, which pixels a hover lifts, and
// which cell a point is on are pure functions of the layout. These checks run
// the production modules (treemap-layout.js, treemap-paint.js, treemap-hit.js)
// on a seeded tree. Which cell each device pixel shows is read by painting the
// paint list onto a buffer of cell indexes, in the order paintCells paints; the
// hit grid and the hover's lift are each held against that reading, at every
// device pixel and at points that fall between them, at several pixel ratios.
// Prints one summary line; exits 1 on a failed invariant.

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
  const tree = seededTree(3000);
  let seed = 3;
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
  };
  let summary = "";

  // Pixel ratios: a plain screen, a Retina screen, and fractional ones, where
  // CSS edges fall between device pixels.
  for (const dpr of [1, 2, 1.25, 2.2]) {
    const at = `at ${dpr}x`;
    const cells = layoutTree(tree, box, {
      metric: "files",
      includeIgnored: true,
      minCellPx: 1 / dpr,
      maxCells: 5000,
    });
    check(`the seeded layout is dense ${at}`, cells.length > 1000, `${cells.length} cells`);

    // ── Paint list: snapped, inside each cell, separated when large enough ──────
    const { rects, empty } = paint.paintList(cells, (c) => String(cells.indexOf(c)), dpr);
    const snapped = cells.map((c) => paint.snapRect(c, dpr));
    check(
      `a cell whose snapped rectangle is empty paints nothing, and is counted ${at}`,
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
    check(`every painted rectangle lies inside its cell ${at}`, outside === 0, `${outside}`);
    check(
      `a cell large enough draws one device pixel short, so its edge shows ${at}`,
      unseparated === 0,
    );
    check(
      `a folder's interior lies inside its own fill ${at}`,
      rects.every((r) => {
        if (r.tone !== "edge") {
          return true;
        }
        const fill = rects.find((f) => f.cell === r.cell && f.tone === "fill");
        return (
          fill &&
          r.x >= fill.x &&
          r.y >= fill.y &&
          r.x + r.w <= fill.x + fill.w &&
          r.y + r.h <= fill.y + fill.h
        );
      }),
    );
    check(
      `every nesting folder paints its interior in its edge tone ${at}`,
      cells.every(
        (c, i) =>
          !c.nested ||
          !c.inner ||
          paint.snapRect(c.inner, dpr).w < 2 ||
          rects.some((r) => r.cell === i && r.tone === "edge"),
      ),
    );
    // Children draw short only on their right and bottom, so the interior reaches a
    // device pixel above and left of them wherever the folder's header or frame keeps
    // a pixel of its own there: the first row and column then have an edge too.
    let edgeless = 0;
    let measured = 0;
    for (let i = 0; i < cells.length; i += 1) {
      const c = cells[i];
      const edge = rects.find((r) => r.cell === i && r.tone === "edge");
      const fill = rects.find((r) => r.cell === i && r.tone === "fill");
      if (!c.nested || !c.inner || !edge || !fill) {
        continue;
      }
      const inner = paint.snapRect(c.inner, dpr);
      for (const [gap, start, want] of [
        [inner.y - fill.y, edge.y, inner.y - 1],
        [inner.x - fill.x, edge.x, inner.x - 1],
      ]) {
        if (gap >= 2) {
          measured += 1;
          if (start !== want) {
            edgeless += 1;
          }
        }
      }
    }
    check(
      `a nesting folder's first row and column have an edge against its header and frame ${at}`,
      measured > 0 && edgeless === 0,
      `${edgeless} of ${measured} sides`,
    );

    // ── Paint order, and which cell each device pixel shows ──────────────────────
    // Each cell paints in a style of its own, so a fill names its cell; painting
    // the list into a buffer of indexes, in paintCells's order, gives each pixel's
    // owner, -1 for the surface.
    const W = Math.round(box.w * dpr);
    const H = Math.round(box.h * dpr);
    const owner = new Int32Array(W * H).fill(-1);
    // Whether each pixel shows its owner's edge tone: the separators between cells.
    const edgeTone = new Uint8Array(W * H);
    let painted = 0;
    const ctx = {
      globalAlpha: 1,
      fillStyle: "",
      fillRect(x, y, w, h) {
        painted += 1;
        const index = Number(this.fillStyle.slice(1));
        const edge = this.fillStyle[0] === "e" ? 1 : 0;
        for (let row = y; row < y + h; row += 1) {
          owner.fill(index, row * W + x, row * W + x + w);
          edgeTone.fill(edge, row * W + x, row * W + x + w);
        }
      },
    };
    paint.paintCells(ctx, rects, (style) => ({ fill: `f${style}`, edge: `e${style}`, alpha: 1 }));
    check(`every rectangle is painted once ${at}`, painted === rects.length);
    // A cell shows over its parent, or the paint order put the parent on top.
    let buried = 0;
    const shown = new Set(owner);
    for (const r of rects) {
      if (r.tone === "fill" && !shown.has(r.cell)) {
        buried += 1;
      }
    }
    check(`every painted cell shows at least one pixel ${at}`, buried === 0, `${buried}`);

    // ── Hit grid: the cell painted at a point ───────────────────────────────────
    const grid = buildHitGrid(cells, box, dpr);
    let missed = 0;
    let firstMiss = null;
    for (let py = 0; py < H; py += 1) {
      for (let px = 0; px < W; px += 1) {
        const hit = grid.lookup((px + 0.5) / dpr, (py + 0.5) / dpr);
        if (hit !== owner[py * W + px]) {
          missed += 1;
          firstMiss ??= { px, py, hit, owner: owner[py * W + px] };
        }
      }
    }
    check(
      `the grid names the cell painted at every device pixel ${at}`,
      missed === 0,
      `${missed} of ${W * H}: ${JSON.stringify(firstMiss)}`,
    );
    let offCentre = 0;
    for (let k = 0; k < 20000; k += 1) {
      const x = rnd() * box.w;
      const y = rnd() * box.h;
      const px = Math.min(W - 1, Math.floor(x * dpr));
      const py = Math.min(H - 1, Math.floor(y * dpr));
      if (grid.lookup(x, y) !== owner[py * W + px]) {
        offCentre += 1;
      }
    }
    check(
      `the grid names the painted cell between pixel centres ${at}`,
      offCentre === 0,
      `${offCentre}`,
    );
    check(
      `a point outside the box hits nothing ${at}`,
      grid.lookup(-1, 5) === -1 && grid.lookup(5, box.h) === -1 && grid.lookup(box.w, 5) === -1,
    );
    const unreachable = rects.filter((r) => r.tone === "fill" && !shown.has(r.cell)).length;
    check(`every painted cell can be pointed at ${at}`, unreachable === 0, `${unreachable}`);

    // ── Mark ops: the lifted pixels are exactly the marked cells' own fill pixels,
    // never a separator, which keeps its tone under any hover ─────────────────────
    for (const family of ["js", "py", "md"]) {
      const marked = (i) => cells[i].ext === family || cells[i].dominant_ext === family;
      const ops = paint.markOps(cells, marked, dpr);
      const lifted = new Uint8Array(W * H);
      for (const op of ops) {
        for (let row = op.y; row < op.y + op.h; row += 1) {
          lifted.fill(op.op === "copy" ? 1 : 0, row * W + op.x, row * W + op.x + op.w);
        }
      }
      let wrong = 0;
      for (let p = 0; p < W * H; p += 1) {
        const expected = owner[p] >= 0 && marked(owner[p]) && !edgeTone[p] ? 1 : 0;
        if (lifted[p] !== expected) {
          wrong += 1;
        }
      }
      check(
        `a ${family} family's ops lift exactly its cells' own fill pixels ${at}`,
        wrong === 0,
        `${wrong} pixels`,
      );
    }
    // Every cell marked, as a pointer on each in turn would: each lifts its fill and
    // header and frame, and no separator anywhere lifts.
    const everything = paint.markOps(cells, () => true, dpr);
    const all = new Uint8Array(W * H);
    for (const op of everything) {
      for (let row = op.y; row < op.y + op.h; row += 1) {
        all.fill(op.op === "copy" ? 1 : 0, row * W + op.x, row * W + op.x + op.w);
      }
    }
    let liftedSeparators = 0;
    let unliftedFills = 0;
    for (let p = 0; p < W * H; p += 1) {
      if (owner[p] < 0) {
        continue;
      }
      if (edgeTone[p] && all[p]) {
        liftedSeparators += 1;
      } else if (!edgeTone[p] && !all[p]) {
        unliftedFills += 1;
      }
    }
    check(
      `a hover that marks every cell lifts every fill and no separator ${at}`,
      liftedSeparators === 0 && unliftedFills === 0,
      `${liftedSeparators} separators lifted, ${unliftedFills} fills not`,
    );
    // A nesting folder's own hover: its header and frame lift, and nothing inside it.
    const folder = cells.findIndex((c) => c.nested && c.parent >= 0);
    if (folder >= 0) {
      const own = paint.markOps(cells, (i) => i === folder, dpr);
      check(
        `a folder's hover copies its fill and clears its interior ${at}`,
        own.length === 2 &&
          own[0].op === "copy" &&
          own[1].op === "clear" &&
          own.every((op) => op.cell === folder),
        JSON.stringify(own),
      );
    }
    check(
      `a hover that marks nothing has no ops ${at}`,
      paint.markOps(cells, () => false, dpr).length === 0,
    );
    // ── Icons alone: a square of the glyph's device size, inside its cell's fill ───
    const glyphOf = (i) => (cells[i].kind === "file" ? 2 + (i % 7) : 0);
    const icons = paint.iconList(cells, glyphOf, dpr);
    let iconsOutside = 0;
    let missized = 0;
    for (const icon of icons) {
      const fill = paint.fillRect(cells[icon.cell], dpr);
      if (
        icon.x < fill.x ||
        icon.y < fill.y ||
        icon.x + icon.w > fill.x + fill.w ||
        icon.y + icon.h > fill.y + fill.h
      ) {
        iconsOutside += 1;
      }
      const want = Math.min(Math.round(glyphOf(icon.cell) * dpr), fill.w, fill.h);
      if (icon.w !== icon.h || icon.w !== want) {
        missized += 1;
      }
    }
    check(`every icon lies inside its cell's fill ${at}`, iconsOutside === 0, `${iconsOutside}`);
    check(`every icon is a square of its glyph's size ${at}`, missized === 0, `${missized}`);
    check(
      `a cell with no glyph draws no icon ${at}`,
      icons.every((icon) => glyphOf(icon.cell) > 0) && icons.length > 0,
    );
    summary += ` ${at}: ${cells.length} cells, ${rects.length} rectangles;`;
  }

  if (failures.length > 0) {
    console.error(`treemap paint and hit FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log(`treemap paint and hit OK:${summary}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
