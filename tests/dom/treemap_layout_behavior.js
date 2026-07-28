// Geometry checks for the folder plugin's treemap layout module.
//
// Pure-function tests: squarified area conservation, bounds
// containment, aspect quality, arbitrary bounded recursion, spatial
// focus transforms, culling + rest synthesis, type-grouping mode, and
// a timed 800-cell layout against the spec budget (16 ms, asserted
// with slack for CI jitter; the measured value is printed for the
// budget record).

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

const sandbox = { console, Math, performance };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/treemap_layout.js"),
  "utf8",
);
vm.runInContext(source, sandbox, { filename: "treemap_layout.js" });

const layout = sandbox.MetabrowserTreemapLayout;
if (!layout) {
  console.error("MetabrowserTreemapLayout global missing");
  process.exit(1);
}

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
        children: [
          fileNode("inner.py", "sub/inner.py", 1000),
          dirNode("nested", "sub/nested", {
            total_size: 1000,
            children: [
              dirNode("deeper", "sub/nested/deeper", {
                total_size: 1000,
                children: [fileNode("leaf.py", "sub/nested/deeper/leaf.py", 1000)],
              }),
            ],
          }),
        ],
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
  const leaf = cells.find((c) => c.path === "sub/nested/deeper/leaf.py");
  check(
    "default scene recurses through available depth",
    !!leaf && leaf.depth === 3 && Math.max(...cells.map((cell) => cell.depth)) >= 3,
    JSON.stringify(cells.map((cell) => [cell.path, cell.depth])),
  );
  const twoLevels = layout.layoutTree(root, { w: 400, h: 300 }, { metric: "size", nestDepth: 2 });
  check(
    "explicit depth two stops at the requested intermediate level",
    twoLevels.every((cell) => cell.depth <= 1) &&
      !twoLevels.some((cell) => cell.path === "sub/nested/deeper"),
    JSON.stringify(twoLevels.map((cell) => [cell.path, cell.depth])),
  );
  const threeLevels = layout.layoutTree(root, { w: 400, h: 300 }, { metric: "size", nestDepth: 3 });
  check(
    "explicit depth three renders the next intermediate level",
    threeLevels.some((cell) => cell.path === "sub/nested/deeper" && cell.depth === 2) &&
      !threeLevels.some((cell) => cell.path === "sub/nested/deeper/leaf.py"),
    JSON.stringify(threeLevels.map((cell) => [cell.path, cell.depth])),
  );
  check(
    "nested cell exposes its child coordinate rect",
    !!sub &&
      !!sub.inner &&
      sub.inner.x > sub.x &&
      sub.inner.y > sub.y &&
      sub.inner.x + sub.inner.w < sub.x + sub.w + 0.01 &&
      sub.inner.y + sub.inner.h < sub.y + sub.h + 0.01,
    JSON.stringify(sub),
  );
  if (inner && sub) {
    check(
      "nested child inside parent",
      inner.x >= sub.x && inner.y >= sub.y && inner.x + inner.w <= sub.x + sub.w + 0.01,
      "child escapes parent rect",
    );
  }
  const focused = layout.layoutTree(
    root,
    { w: 400, h: 300 },
    { metric: "size", focusPath: "sub", nestDepth: 3 },
  );
  check(
    "focused camera trims siblings outside its subtree",
    !focused.some((cell) => cell.path === "a.py" || cell.path === "b.md"),
    JSON.stringify(focused.map((cell) => cell.path)),
  );
  const focusedInner = focused.find((cell) => cell.path === "sub/inner.py");
  check(
    "focused camera makes direct children the visible root level",
    !!focusedInner &&
      focusedInner.depth === 0 &&
      focusedInner.x < 400 &&
      focusedInner.y < 300 &&
      focusedInner.x + focusedInner.w > 0 &&
      focusedInner.y + focusedInner.h > 0,
    JSON.stringify(focusedInner),
  );
  if (sub?.inner && inner && focusedInner) {
    const expectedFocusedInner = layout.projectRect(
      inner,
      layout.focusTransform(sub.inner, { w: 400, h: 300 }),
    );
    check(
      "settled focus geometry exactly matches the compositor transform",
      Math.abs(expectedFocusedInner.x - focusedInner.x) < 0.01 &&
        Math.abs(expectedFocusedInner.y - focusedInner.y) < 0.01 &&
        Math.abs(expectedFocusedInner.w - focusedInner.w) < 0.01 &&
        Math.abs(expectedFocusedInner.h - focusedInner.h) < 0.01,
      `${JSON.stringify(expectedFocusedInner)} vs ${JSON.stringify(focusedInner)}`,
    );
  }
  check(
    "focused camera preserves arbitrary recursive detail",
    focused.some((cell) => cell.path === "sub/nested/deeper/leaf.py" && cell.depth === 2),
    JSON.stringify(focused.map((cell) => [cell.path, cell.depth])),
  );
  const transitionDetail = layout.layoutTree(
    root,
    { w: 400, h: 300 },
    {
      metric: "size",
      focusPath: "",
      detailPath: "sub/nested/deeper",
      nestDepth: 4,
      nestMinW: 1000,
      nestMinH: 1000,
    },
  );
  check(
    "transition detail pre-renders the camera corridor below settled LOD thresholds",
    transitionDetail.some((cell) => cell.path === "sub/nested/deeper/leaf.py" && cell.depth === 3),
    JSON.stringify(transitionDetail.map((cell) => [cell.path, cell.depth])),
  );
  const budgetFocusRoot = dirNode("root", "", {
    children: [
      dirNode("huge", "huge", {
        total_size: 9000,
        children: Array.from({ length: 20 }, (_, i) =>
          dirNode(`branch-${i}`, `huge/branch-${i}`, {
            total_size: 400 - i,
            children: [fileNode("deep.py", `huge/branch-${i}/deep.py`, 400 - i)],
          }),
        ),
      }),
      dirNode("target", "target", {
        total_size: 1000,
        children: [fileNode("wanted.py", "target/wanted.py", 1000)],
      }),
    ],
  });
  const budgetFocused = layout.layoutTree(
    budgetFocusRoot,
    { w: 400, h: 300 },
    {
      metric: "size",
      focusPath: "target",
      minCellPx: 0,
      maxCells: 20,
      maxWorldCells: 8,
    },
  );
  check(
    "world budget prioritizes the active camera corridor",
    budgetFocused.some((cell) => cell.path === "target/wanted.py" && cell.depth === 0) &&
      !budgetFocused.some((cell) => cell.path.startsWith("huge/")),
    JSON.stringify(budgetFocused.map((cell) => [cell.path, cell.depth])),
  );
  // hidden mode uses unignored values: gitignored file drops out.
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
    { metric: "size", ignored: "hidden" },
  );
  check(
    "hidden drops gitignored",
    !hiddenCells.some((c) => c.path === "ignored.log"),
    JSON.stringify(hiddenCells.map((c) => c.path)),
  );
}

// ── layoutTree: type grouping from ext tallies ──────────────────
{
  const root = dirNode("root", "");
  const cells = layout.layoutTree(
    root,
    { w: 300, h: 200 },
    {
      grouping: "type",
      metric: "size",
      extTallies: [
        [".py", 10, 6000, 10, 6000],
        [".md", 5, 3000, 5, 3000],
        ["", 2, 1000, 2, 1000],
      ],
    },
  );
  check("type cells", cells.length === 3, `${cells.length}`);
  check(
    "type kinds",
    cells.filter((c) => c.kind === "ext").length === 2 &&
      cells.filter((c) => c.kind === "rest").length === 1,
    cells.map((c) => c.kind).join(","),
  );
  const other = cells.find((c) => c.kind === "rest");
  check("rest ext labeled", !!other && other.name === "other", JSON.stringify(other));
  const typeTotal = cells.reduce((s, c) => s + c.value, 0);
  check("type value conservation", typeTotal === 6000 + 3000 + 1000, `${typeTotal}`);
  // files metric with hidden variant reads columns 3.
  const filesCells = layout.layoutTree(
    root,
    { w: 300, h: 200 },
    {
      grouping: "type",
      metric: "files",
      ignored: "hidden",
      extTallies: [[".py", 10, 6000, 4, 2000]],
    },
  );
  check(
    "type files metric",
    filesCells[0] && filesCells[0].value === 4,
    JSON.stringify(filesCells),
  );
}

// ── spatial focus transform uniformly covers and clips viewport ──
{
  const focus = { x: 100, y: 50, w: 200, h: 100 };
  const transform = layout.focusTransform(focus, { w: 400, h: 300 });
  check(
    "focus transform preserves world aspect ratio",
    transform.scaleX === 3 && transform.scaleY === 3,
    JSON.stringify(transform),
  );
  const projected = layout.projectRect(focus, transform);
  check(
    "focus transform covers the viewport",
    projected.x <= 0 &&
      projected.y <= 0 &&
      projected.x + projected.w >= 400 &&
      projected.y + projected.h >= 300,
    JSON.stringify(projected),
  );
  check(
    "focus transform centers clipped excess",
    projected.x === (400 - projected.w) / 2 && projected.y === (300 - projected.h) / 2,
    JSON.stringify(projected),
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
}

// ── budget timing ───────────────────────────────────────────────
{
  // Budget: lay out a recursive tree that emits ~800 cells.
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
