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
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/treemap_layout.js"),
    "utf8",
  )
  .replace(/^export\s*\{[^}]*\};$/gm, "")
  .concat(
    "\nglobalThis.MetabrowserTreemapLayout = { LAYOUT_DEFAULTS, cellTypography, squarify, packLevel, layoutTree, worstAspect };",
  );
vm.runInContext(source, sandbox, { filename: "treemap_layout.js" });

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
    tiny.labelPx === 11 && large.labelPx === 24 && tiny.valuePx === 10 && large.valuePx === 18,
    JSON.stringify({ tiny, large }),
  );
  check(
    "a narrow sliver cannot claim large type from area alone",
    layout.cellTypography({ w: 1000, h: 18 }).labelPx === tiny.labelPx,
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
