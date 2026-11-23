// Geometry checks for the folder plugin's treemap layout module.
//
// Pure-function tests: squarified area conservation, bounds
// containment, aspect quality, culling + rest synthesis, fluid cell
// typography, and a timed 800-cell layout against the spec budget (16 ms,
// asserted with slack for CI jitter; the measured value is printed for
// the budget record).

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

const sandbox = { console, Math, performance };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
const source = fs
  .readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/treemap-layout.js"),
    "utf8",
  )
  .replace(/^export\s*\{[^}]*\};$/gm, "")
  .concat(
    "\nglobalThis.MetabrowserTreemapLayout = { LAYOUT_DEFAULTS, ICON_DEFAULTS, TYPOGRAPHY_DEFAULTS, cellTypography, iconOnlyPx, labelIconGapPx, labelIconPx, labelIconRoomPx, squarify, packLevel, layoutTree, worstAspect };",
  );
vm.runInContext(source, sandbox, { filename: "treemap-layout.js" });

const layout = sandbox.MetabrowserTreemapLayout;
if (!layout) {
  console.error("MetabrowserTreemapLayout global missing");
  process.exit(1);
}
check(
  "fluid header height is derived rather than a layout override",
  !("headerPx" in layout.LAYOUT_DEFAULTS),
);

function check(name, cond, detail) {
  if (!cond) {
    failures.push(`${name}: ${detail || "failed"}`);
  }
}

// ── squarify: area conservation + containment + order ───────────
{
  const items = [40, 25, 15, 10, 6, 4].map((v, i) => ({ value: v, id: i }));
  const rect = { x: 0, y: 0, w: 200, h: 100 };
  const placed = layout.squarify(items, rect);
  check("squarify count", placed.length === items.length, `${placed.length}`);
  const total = placed.reduce((s, p) => s + p.w * p.h, 0);
  check("area conservation", Math.abs(total - 200 * 100) < 1, `sum=${total}`);
  for (const p of placed) {
    check(
      "containment",
      p.x >= -0.01 && p.y >= -0.01 && p.x + p.w <= 200.01 && p.y + p.h <= 100.01,
      JSON.stringify(p),
    );
    const area = p.w * p.h;
    const expected = (p.item.value / 100) * 20000;
    check("proportional area", Math.abs(area - expected) < 1, `${area} vs ${expected}`);
  }
  // Squarified quality: no cell should be pathologically thin.
  for (const p of placed) {
    const aspect = Math.max(p.w / p.h, p.h / p.w);
    check("aspect quality", aspect < 8, `aspect=${aspect.toFixed(2)}`);
  }
  // Zero/negative values are skipped.
  const withZero = layout.squarify([{ value: 10 }, { value: 0 }, { value: -5 }], {
    x: 0,
    y: 0,
    w: 10,
    h: 10,
  });
  check("zero skipped", withZero.length === 1, `${withZero.length}`);
}

// ── layoutTree: folder grouping, rest bucket, nesting ───────────
function dirNode(name, pathStr, extras) {
  return Object.assign(
    {
      name,
      path: pathStr,
      type: "dir",
      state: "complete",
      total_files: 10,
      total_size: 1000,
      unignored_files: 10,
      unignored_size: 1000,
      mtime: 1700000000,
      gitignored: false,
      dominant_ext: ".py",
      children: [],
    },
    extras || {},
  );
}
function fileNode(name, pathStr, size, extras) {
  return Object.assign(
    {
      name,
      path: pathStr,
      type: "file",
      size,
      mtime: 1700000000,
      ext: ".py",
      gitignored: false,
    },
    extras || {},
  );
}

{
  const root = dirNode("root", "", {
    total_size: 3000,
    children: [
      dirNode("sub", "sub", {
        total_size: 2000,
        children: [fileNode("inner.py", "sub/inner.py", 2000)],
      }),
      fileNode("a.py", "a.py", 700),
      fileNode("b.md", "b.md", 300, { ext: ".md" }),
    ],
    rest: { dirs: 1, files: 5, size: 500, unignored_files: 5, unignored_size: 500 },
  });
  const cells = layout.layoutTree(root, { w: 400, h: 300 }, { metric: "size" });
  const kinds = cells.map((c) => c.kind).sort();
  check("has dir cell", kinds.includes("dir"), kinds.join(","));
  check("has file cells", kinds.filter((k) => k === "file").length >= 2, kinds.join(","));
  check("has rest cell", kinds.includes("rest"), kinds.join(","));
  const sub = cells.find((c) => c.kind === "dir" && c.path === "sub");
  check("dir nested flag", !!sub && sub.nested === true, JSON.stringify(sub));
  const inner = cells.find((c) => c.path === "sub/inner.py");
  check("nested child emitted", !!inner && inner.depth === 1, JSON.stringify(inner));
  if (inner && sub) {
    check(
      "nested child inside parent",
      inner.x >= sub.x && inner.y >= sub.y && inner.x + inner.w <= sub.x + sub.w + 0.01,
      "child escapes parent rect",
    );
  }
  // Excluding ignored files uses unignored values: the gitignored
  // leaf drops out and the remaining cell fills the map.
  const rootHidden = dirNode("root", "", {
    total_size: 1000,
    unignored_size: 400,
    children: [
      fileNode("kept.py", "kept.py", 400),
      fileNode("ignored.log", "ignored.log", 600, { gitignored: true, ext: ".log" }),
    ],
  });
  const hiddenCells = layout.layoutTree(
    rootHidden,
    { w: 200, h: 100 },
    { metric: "size", includeIgnored: false },
  );
  check(
    "unchecked ignored scope drops gitignored",
    !hiddenCells.some((c) => c.path === "ignored.log"),
    JSON.stringify(hiddenCells.map((c) => c.path)),
  );
}

// ── Fluid typography: continuous, bounded, and geometry-aware ───
{
  const tiny = layout.cellTypography({ w: 40, h: 20 });
  const medium = layout.cellTypography({ w: 180, h: 100 });
  const large = layout.cellTypography({ w: 900, h: 600 });
  check(
    "label size grows continuously with usable cell geometry",
    tiny.labelPx < medium.labelPx && medium.labelPx < large.labelPx,
    `${tiny.labelPx}/${medium.labelPx}/${large.labelPx}`,
  );
  check(
    "value size grows with the label",
    tiny.valuePx < medium.valuePx && medium.valuePx < large.valuePx,
    `${tiny.valuePx}/${medium.valuePx}/${large.valuePx}`,
  );
  check(
    "font sizes stay within the documented bounds",
    tiny.labelPx === 9 && large.labelPx === 24 && tiny.valuePx === 9 && large.valuePx === 18,
    JSON.stringify({ tiny, large }),
  );
  // A folder's name is a heading over its files: it stops at the navigation's sizes, and
  // its header strip with it, however large the folder.
  const largeFolder = layout.cellTypography({ w: 900, h: 600 }, "dir");
  const smallFolder = layout.cellTypography({ w: 40, h: 20 }, "dir");
  check(
    "a folder's label and value stop at the navigation's sizes",
    largeFolder.labelPx === 13 &&
      largeFolder.valuePx === 12 &&
      largeFolder.headerPx === 20 &&
      smallFolder.labelPx === tiny.labelPx,
    JSON.stringify({ largeFolder, smallFolder }),
  );
  check(
    "a narrow sliver cannot claim large type from area alone",
    layout.cellTypography({ w: 1000, h: 18 }).labelPx === tiny.labelPx,
  );
}

// ── Icons: sized to their cell, smaller with it, within the glyph bounds ───
{
  const { glyphMinPx, glyphMaxPx } = layout.ICON_DEFAULTS;
  check(
    "the glyph bounds stay under the navigation's 14 px glyph",
    glyphMinPx === 4 && glyphMaxPx === 12,
    JSON.stringify(layout.ICON_DEFAULTS),
  );
  // Beside a label, the glyph follows the label's size, never past the bounds.
  const besideLabel = [9, 12, 13, 14, 18, 24].map((px) => layout.labelIconPx(px));
  check(
    "a label's glyph grows with the label and stops at the cap",
    JSON.stringify(besideLabel) === JSON.stringify([8, 10, 11, 12, 12, 12]),
    JSON.stringify(besideLabel),
  );
  check(
    "a label's glyph is no taller than the smallest label",
    layout.labelIconPx(layout.TYPOGRAPHY_DEFAULTS.labelMinPx) <=
      layout.TYPOGRAPHY_DEFAULTS.labelMinPx,
  );
  check(
    "the gap and the room a glyph takes scale with the label",
    layout.labelIconGapPx(10) === 4 &&
      layout.labelIconRoomPx(10) === layout.labelIconPx(10) + 4 &&
      layout.labelIconRoomPx(9) < layout.labelIconRoomPx(20),
    `${layout.labelIconRoomPx(9)}/${layout.labelIconRoomPx(20)}`,
  );
  // Alone, the glyph is a share of the cell's short side: smaller cells, smaller glyphs,
  // down to the smallest; below it, none.
  const alone = [5, 6, 8, 9, 11, 12, 15, 30].map((side) => layout.iconOnlyPx({ w: side, h: side }));
  check(
    "an icon alone shrinks with its cell to the smallest glyph, then is not drawn",
    JSON.stringify(alone) === JSON.stringify([0, 4, 5, 6, 7, 8, 8, 8]),
    JSON.stringify(alone),
  );
  check(
    "an icon alone is never larger than the glyph beside its label",
    layout.iconOnlyPx({ w: 30, h: 30 }, 9) === layout.labelIconPx(9) &&
      layout.iconOnlyPx({ w: 30, h: 30 }, 14) === layout.labelIconPx(14),
  );
  let monotone = true;
  let fits = true;
  for (let side = 1; side <= 60; side += 0.5) {
    const glyph = layout.iconOnlyPx({ w: side, h: 400 }, 24);
    if (glyph > layout.iconOnlyPx({ w: side + 0.5, h: 400 }, 24)) {
      monotone = false;
    }
    if (glyph > 0 && (glyph < glyphMinPx || glyph > glyphMaxPx || glyph > side - 2)) {
      fits = false;
    }
  }
  check("an icon alone never shrinks as its cell grows", monotone);
  check("an icon alone stays within the bounds and inside its cell's edge", fits);
  check(
    "a sliver's icon is sized by its short side",
    layout.iconOnlyPx({ w: 300, h: 9 }) === 6 && layout.iconOnlyPx({ w: 6, h: 300 }) === 4,
  );

  const nestedRoot = dirNode("root", "", {
    total_size: 1000,
    children: [
      dirNode("large", "large", {
        total_size: 1000,
        children: [fileNode("inside.py", "large/inside.py", 1000)],
      }),
    ],
  });
  const nested = layout.layoutTree(nestedRoot, { w: 900, h: 600 }, { metric: "size" });
  const folder = nested.find((cell) => cell.path === "large");
  const child = nested.find((cell) => cell.path === "large/inside.py");
  check(
    "nested children start below the fluid folder header",
    folder && child && child.y >= folder.y + folder.headerPx,
    JSON.stringify({ folder, child }),
  );
}

// ── conservation under culling and the cap (R7 regression) ──────
{
  // Culling with NO server rest bucket: tiny slivers must fold into a
  // synthesized remainder, never vanish.
  const sliverRoot = dirNode("root", "", {
    total_size: 10230,
    children: [fileNode("big.py", "big.py", 10000)].concat(
      Array.from({ length: 230 }, (_, i) => fileNode(`s${i}.py`, `s${i}.py`, 1)),
    ),
  });
  const sliverCells = layout.layoutTree(sliverRoot, { w: 120, h: 60 }, { metric: "size" });
  const sliverTotal = sliverCells.reduce((s, c) => s + c.value, 0);
  check("cull conservation (value)", sliverTotal === 10230, `${sliverTotal}`);
  const sliverArea = sliverCells.filter((c) => c.depth === 0).reduce((s, c) => s + c.w * c.h, 0);
  check("cull conservation (area)", Math.abs(sliverArea - 120 * 60) < 1, `${sliverArea}`);
  check(
    "cull synthesizes remainder",
    sliverCells.some((c) => c.kind === "rest" && c.value > 0),
    JSON.stringify(sliverCells.map((c) => [c.kind, c.value]).slice(0, 5)),
  );

  // Cap exhaustion: the unemitted tail aggregates into the remainder
  // instead of silently disappearing.
  const wide = dirNode("root", "", {
    children: Array.from({ length: 3000 }, (_, i) => fileNode(`f${i}.py`, `f${i}.py`, 3000 - i)),
  });
  const wideTotal = wide.children.reduce((s, c) => s + c.size, 0);
  const capped = layout.layoutTree(wide, { w: 1200, h: 800 }, { metric: "size", maxCells: 100 });
  check("maxCells cap", capped.length <= 100, `${capped.length}`);
  const cappedTotal = capped.reduce((s, c) => s + c.value, 0);
  check("cap conservation (value)", cappedTotal === wideTotal, `${cappedTotal} vs ${wideTotal}`);
  check(
    "cap remainder present",
    capped.some((c) => c.kind === "rest" && c.value > 0),
    "no remainder after cap",
  );

  const fileMetricRoot = dirNode("root", "", {
    total_files: 12,
    total_size: 1200,
    children: [fileNode("kept.py", "kept.py", 200)],
    rest: { dirs: 0, files: 11, size: 1000, unignored_files: 11, unignored_size: 1000 },
  });
  const byFiles = layout.layoutTree(
    fileMetricRoot,
    { w: 300, h: 200 },
    { metric: "files", minCellPx: 0 },
  );
  const fileRemainder = byFiles.find((cell) => cell.kind === "rest");
  check(
    "file-metric remainder retains its true byte magnitude",
    fileRemainder && fileRemainder.bytes === 1000,
    JSON.stringify(fileRemainder),
  );
}

// ── containment, depth, framing, and budget spread ──────────────
{
  // Every cell lies inside its parent folder's cell and inside the viewport,
  // at every depth, including the right and bottom edges.
  /** A folder `depth` levels deep, `fanout` subfolders and `files` files per level. */
  function deepTree(prefix, depth, fanout, files) {
    const children = [];
    for (let i = 0; i < files; i += 1) {
      children.push(fileNode(`f${i}.py`, `${prefix}f${i}.py`, 100 + i * 37));
    }
    if (depth > 0) {
      for (let d = 0; d < fanout; d += 1) {
        children.push(deepTree(`${prefix}d${d}/`, depth - 1, fanout, files));
      }
    }
    const total = children.reduce((sum, c) => sum + (c.type === "dir" ? c.total_size : c.size), 0);
    const count = children.reduce((sum, c) => sum + (c.type === "dir" ? c.total_files : 1), 0);
    const name = prefix.split("/").filter(Boolean).at(-1) || "root";
    return dirNode(name, prefix.replace(/\/$/, ""), {
      total_size: total,
      unignored_size: total,
      total_files: count,
      unignored_files: count,
      children,
    });
  }
  const tree = deepTree("", 5, 3, 4);
  const view = { w: 1037, h: 611 };
  const cells = layout.layoutTree(tree, view, { metric: "size" });
  const byPath = new Map(cells.filter((c) => c.kind === "dir").map((c) => [c.path, c]));
  const eps = 1e-6;
  let escapesParent = 0;
  let escapesView = 0;
  for (const c of cells) {
    if (c.x < -eps || c.y < -eps || c.x + c.w > view.w + eps || c.y + c.h > view.h + eps) {
      escapesView += 1;
    }
    // A remainder cell carries its folder's own path.
    const parentPath = c.kind === "rest" ? c.path : c.path.split("/").slice(0, -1).join("/");
    const parent = parentPath ? byPath.get(parentPath) : null;
    if (
      parent &&
      (c.x < parent.x - eps ||
        c.y < parent.y - eps ||
        c.x + c.w > parent.x + parent.w + eps ||
        c.y + c.h > parent.y + parent.h + eps)
    ) {
      escapesParent += 1;
    }
  }
  check("no cell escapes the viewport", escapesView === 0, `${escapesView}`);
  check("no cell escapes its parent folder", escapesParent === 0, `${escapesParent}`);
  check(
    "nesting reaches past the old two-level limit",
    Math.max(...cells.map((c) => c.depth)) >= 3,
    `${Math.max(...cells.map((c) => c.depth))}`,
  );
  const parentsFirst = cells.every((c, i) => {
    const parentPath = c.kind === "rest" ? null : c.path.split("/").slice(0, -1).join("/");
    const parent = parentPath ? byPath.get(parentPath) : null;
    return !parent || cells.indexOf(parent) < i;
  });
  check("parents are emitted before their children", parentsFirst);

  // A folder too small for a header still nests, framed, with no header strip.
  const framed = cells.filter((c) => c.framed);
  check("small folders nest in a frame", framed.length > 0, `${framed.length}`);
  const framedChild = framed
    .map((f) => [f, cells.find((c) => c.path.startsWith(`${f.path}/`))])
    .find(([, child]) => child);
  check(
    "a framed folder's children start one pad inside it, not below a header",
    framedChild && Math.abs(framedChild[1].y - framedChild[0].y) < framedChild[0].headerPx,
    JSON.stringify(framedChild),
  );
  // The frame thins with depth, ceil(padPx * frameDecay^depth), and a folder
  // smaller than frameNestMinPx on a side has none: its children tile it.
  const { padPx, frameDecay, frameNestMinPx } = layout.LAYOUT_DEFAULTS;
  const offsets = framed.map((f) => {
    const inside = cells.filter(
      (c) => c.path.startsWith(`${f.path}/`) || (c.kind === "rest" && c.path === f.path),
    );
    const expected =
      Math.min(f.w, f.h) >= frameNestMinPx ? Math.ceil(padPx * frameDecay ** f.depth) : 0;
    return [
      Math.min(...inside.map((c) => c.x)) - f.x,
      Math.min(...inside.map((c) => c.y)) - f.y,
      expected,
    ];
  });
  check(
    "a framed folder's children start exactly one frame width inside it",
    offsets.every(([dx, dy, want]) => Math.abs(dx - want) < eps && Math.abs(dy - want) < eps),
    JSON.stringify(offsets.slice(0, 4)),
  );
  check(
    "frames thin with depth",
    framed.some((f) => f.depth >= 3 && Math.min(f.w, f.h) >= frameNestMinPx)
      ? offsets.every(([dx, , want], k) => framed[k].depth < 3 || dx <= 1 + eps || want === 0)
      : true,
    JSON.stringify(offsets.filter((_, k) => framed[k].depth >= 3).slice(0, 4)),
  );

  // Each cell names its parent's index, the folder whose interior holds it, which
  // hit testing and hover marks walk.
  const parentIndexes = cells.every((c, i) => {
    if (c.parent === -1) {
      return c.depth === 0;
    }
    const p = cells[c.parent];
    return (
      c.parent < i &&
      p.kind === "dir" &&
      p.depth === c.depth - 1 &&
      (c.kind === "rest" ? c.path === p.path : c.path.startsWith(`${p.path}/`))
    );
  });
  check("every cell names its parent's index", parentIndexes);
  const interiors = cells.every(
    (c) =>
      !c.nested ||
      (c.inner &&
        c.inner.x >= c.x - eps &&
        c.inner.y >= c.y - eps &&
        c.inner.x + c.inner.w <= c.x + c.w + eps &&
        c.inner.y + c.inner.h <= c.y + c.h + eps),
  );
  check("a nesting folder records the interior its children tile", interiors);
  // A folder the map would label is labelled, not framed: framing it hid the
  // names of folders that had room for them.
  const labelMin = { w: layout.LAYOUT_DEFAULTS.labelMinW, h: layout.LAYOUT_DEFAULTS.labelMinH };
  check(
    "only folders too small for a label are framed",
    framed.every((f) => f.w < labelMin.w || f.h < labelMin.h),
    JSON.stringify(framed.filter((f) => f.w >= labelMin.w && f.h >= labelMin.h).slice(0, 3)),
  );
  const headed = cells.filter((c) => c.nested && !c.framed);
  check(
    "a folder nests under its label only with room for the label and a row of children",
    headed.length > 0 && headed.every((c) => c.w >= labelMin.w && c.h >= 40),
    `${headed.length}`,
  );

  // A folder whose children all folded into its remainder at the rollup's node
  // budget has nothing to nest: it stays one solid cell, not a frame around a
  // single inert remainder.
  const restOnly = layout.layoutTree(
    dirNode("root", "", {
      total_size: 2000,
      children: [
        dirNode("capped", "capped", {
          total_size: 1500,
          children: [],
          rest: { dirs: 0, files: 9, size: 1500, unignored_files: 9, unignored_size: 1500 },
        }),
        fileNode("a.py", "a.py", 500),
      ],
    }),
    { w: 400, h: 300 },
    { metric: "size" },
  );
  const capped = restOnly.find((c) => c.path === "capped" && c.kind === "dir");
  check(
    "a folder holding only its remainder stays solid",
    !!capped && !capped.nested && !capped.framed && restOnly.every((c) => c.kind !== "rest"),
    JSON.stringify(restOnly.map((c) => [c.kind, c.path, c.nested])),
  );

  // The budget spreads across the map rather than draining into the first
  // folder: with a small cap, every large top-level folder still nests.
  const wideTree = dirNode("root", "", {
    total_size: 4 * 400 * 1000,
    children: Array.from({ length: 4 }, (_, d) =>
      dirNode(`d${d}`, `d${d}`, {
        total_size: 400 * 1000,
        total_files: 400,
        children: Array.from({ length: 400 }, (_, i) =>
          fileNode(`f${i}.py`, `d${d}/f${i}.py`, 1000),
        ),
      }),
    ),
  });
  const spread = layout.layoutTree(
    wideTree,
    { w: 1200, h: 800 },
    { metric: "size", maxCells: 200 },
  );
  const perFolder = [0, 1, 2, 3].map(
    (d) => spread.filter((c) => c.kind === "file" && c.path.startsWith(`d${d}/`)).length,
  );
  check(
    "the cell budget reaches every large folder",
    perFolder.every((n) => n >= 20),
    JSON.stringify(perFolder),
  );
  check("the cap still holds while spreading", spread.length <= 200, `${spread.length}`);
}

// ── chrome compensation: a file's area follows its value at any depth ──
{
  // Eight 1,000-byte files at each of seven levels, each level a folder inside
  // the last, so every level's files sit inside one more header or frame.
  const levels = 7;
  /** @param {number} level @param {string} prefix */
  function chain(level, prefix) {
    const files = Array.from({ length: 8 }, (_, i) =>
      fileNode(`f${i}.py`, `${prefix}f${i}.py`, 1000),
    );
    if (level === levels - 1) {
      return { files, size: 8000, count: 8 };
    }
    const sub = chain(level + 1, `${prefix}d${level + 1}/`);
    const dir = dirNode(`d${level + 1}`, `${prefix}d${level + 1}`, {
      total_size: sub.size,
      unignored_size: sub.size,
      total_files: sub.count,
      unignored_files: sub.count,
      children: sub.files,
    });
    return { files: [...files, dir], size: sub.size + 8000, count: sub.count + 8 };
  }
  const top = chain(0, "");
  const tree = dirNode("root", "", {
    total_size: top.size,
    unignored_size: top.size,
    total_files: top.count,
    unignored_files: top.count,
    children: top.files,
  });
  /** @param {Record<string, any>} options */
  function depthRatio(options) {
    const cells = layout.layoutTree(tree, { w: 1200, h: 800 }, { metric: "size", ...options });
    /** @param {number} depth */
    const perValue = (depth) => {
      const files = cells.filter((c) => c.kind === "file" && c.depth === depth);
      return files.reduce((s, c) => s + (c.w * c.h) / c.value, 0) / Math.max(1, files.length);
    };
    const deepest = Math.max(...cells.filter((c) => c.kind === "file").map((c) => c.depth));
    return { ratio: perValue(deepest) / perValue(0), deepest, cells };
  }
  const plain = depthRatio({ chromeRounds: 0, chromePasses: 0 });
  const estimated = depthRatio({ chromePasses: 0 });
  const corrected = depthRatio({});
  check(
    "uncompensated, the deepest files shrink by each folder's chrome",
    plain.deepest === levels - 1 && plain.ratio < 0.8,
    `${plain.ratio.toFixed(3)} at depth ${plain.deepest}`,
  );
  check(
    "the chrome estimate gives the deepest files near their share",
    estimated.ratio > 0.9 && estimated.ratio < 1.1,
    estimated.ratio.toFixed(3),
  );
  check(
    "the corrective pass gives the deepest files their share",
    corrected.deepest === levels - 1 && Math.abs(corrected.ratio - 1) < 0.02,
    corrected.ratio.toFixed(3),
  );
  check(
    "a compensated cell still carries its own value, not its weight",
    corrected.cells
      .filter((c) => c.kind === "dir")
      .every((c) => c.value === c.bytes && c.value === (levels - c.depth - 1) * 8000),
    JSON.stringify(corrected.cells.filter((c) => c.kind === "dir").map((c) => [c.depth, c.value])),
  );
  const capped = depthRatio({ chromePassMaxCells: 10 });
  check(
    "a map past chromePassMaxCells keeps the estimate alone",
    capped.ratio === estimated.ratio,
    `${capped.ratio} vs ${estimated.ratio}`,
  );
}

// ── budget timing ───────────────────────────────────────────────
{
  // Budget: lay out a two-level tree that emits ~800 cells.
  const subdirs = Array.from({ length: 40 }, (_, d) =>
    dirNode(`d${d}`, `d${d}`, {
      total_size: 100000 - d * 100,
      children: Array.from({ length: 30 }, (_, i) =>
        fileNode(`f${i}.py`, `d${d}/f${i}.py`, 3000 - i),
      ),
    }),
  );
  const big = dirNode("root", "", { total_size: 4000000, children: subdirs });
  const t0 = performance.now();
  const bigCells = layout.layoutTree(big, { w: 1600, h: 900 }, { metric: "size", maxCells: 800 });
  const elapsed = performance.now() - t0;
  console.log(
    `budget: layoutTree emitted ${bigCells.length} cells in ${elapsed.toFixed(2)}ms (spec budget 16ms)`,
  );
  check("budget cells", bigCells.length > 400 && bigCells.length <= 800, `${bigCells.length}`);
  // Hard gate is generous (4x) to absorb CI jitter; the printed value
  // is the budget record.
  check("layout budget", elapsed < 64, `${elapsed.toFixed(2)}ms`);
}

if (failures.length > 0) {
  console.error(`treemap layout FAILURES:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log("treemap layout OK");
