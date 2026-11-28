// Pure-function tests for static/structured-preview.js.
//
// Runs in a Node vm sandbox (same approach as load-plugins.js) — no
// jsdom dependency. Exits 0 on success, 1 on first failed assertion;
// the Python harness in test_structured_plugin_js.py inspects stdout.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const sandbox = {
  console,
  Set,
  Map,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const previewSrc = fs.readFileSync(
  path.resolve(__dirname, "../../src/metabrowser/static/structured-preview.js"),
  "utf-8",
);
vm.runInContext(previewSrc, sandbox, { filename: "preview.js" });

const pv = sandbox.__structuredPreview;
const failures = [];

function assertEq(label, actual, expected) {
  if (actual !== expected) {
    failures.push(`${label}: expected ${JSON.stringify(expected)} got ${JSON.stringify(actual)}`);
  }
}

function assertTrue(label, cond) {
  if (!cond) {
    failures.push(`${label}: expected truthy`);
  }
}

// formatValue — primitive coverage
(() => {
  let r = pv.formatValue("hello");
  assertEq("formatValue string text", r.text, '"hello"');
  assertEq("formatValue string class", r.colorClass, "tok-string");

  r = pv.formatValue(42);
  assertEq("formatValue number text", r.text, "42");
  assertEq("formatValue number class", r.colorClass, "tok-number");

  r = pv.formatValue(true);
  assertEq("formatValue bool true text", r.text, "true");
  assertEq("formatValue bool class", r.colorClass, "tok-bool");

  r = pv.formatValue(null);
  assertEq("formatValue null text", r.text, "null");
  assertEq("formatValue null class", r.colorClass, "tok-null");

  r = pv.formatValue(NaN);
  assertEq("formatValue NaN text", r.text, "NaN");

  r = pv.formatValue(Infinity);
  assertEq("formatValue +Inf text", r.text, "Infinity");
})();

// calculateIndentStyle scales with level
(() => {
  const s0 = pv.calculateIndentStyle(0, 2);
  const s2 = pv.calculateIndentStyle(2, 2);
  assertEq("indent level 0", s0.paddingLeft, "0em");
  assertEq("indent level 2", s2.paddingLeft, "2em");
})();

// generateStructuredPreview — collapsed-object summary
(() => {
  const small = { a: 1, b: "x", c: true };
  const pr = pv.generateStructuredPreview(small, { maxWidth: 80 });
  assertTrue("preview has parts", pr.parts.length > 0);
  assertEq("preview not truncated for small obj", pr.hasMore, false);
  // First/last parts should be the curly braces.
  assertEq("opens with {", pr.parts[0].text, "{");
  assertEq("ends with }", pr.parts[pr.parts.length - 1].text, "}");
})();

// generateStructuredPreview — triggers "more" marker on overflow
(() => {
  const big = {};
  for (let i = 0; i < 50; i++) {
    big[`k${i}`] = `v${i}`;
  }
  const pr = pv.generateStructuredPreview(big, { maxWidth: 30 });
  assertEq("preview marks hasMore on overflow", pr.hasMore, true);
  // Some "more" part should be present.
  const moreParts = pr.parts.filter((p) => p.kind === "more");
  assertTrue("preview emits a more part", moreParts.length > 0);
})();

// generateStructuredPreview — empty array
(() => {
  const pr = pv.generateStructuredPreview([], { maxWidth: 80 });
  assertEq("empty array opens [", pr.parts[0].text, "[");
  assertEq("empty array closes ]", pr.parts[pr.parts.length - 1].text, "]");
})();

// calculateOptimalExpansion — always expands root, bounded by maxLines
(() => {
  const data = { a: { b: 1 }, c: [1, 2, 3] };
  const exp = pv.calculateOptimalExpansion(data, {
    maxLines: 60,
    maxExpandThreshold: 80,
  });
  assertTrue("root expanded", exp.has("$"));
  // Paths are positional: "$/0" is the root's first entry ("a"), "$/1" its second.
  assertTrue("$/0 (a) expanded", exp.has("$/0"));
  assertTrue("$/1 (c) expanded", exp.has("$/1"));
  assertEq(
    "no key-text paths",
    [...exp].some((p) => p.includes(".")),
    false,
  );
})();

// calculateOptimalExpansion — refuses huge containers
(() => {
  const huge = { big: {} };
  for (let i = 0; i < 200; i++) {
    huge.big[`k${i}`] = i;
  }
  const exp = pv.calculateOptimalExpansion(huge, {
    maxLines: 60,
    maxExpandThreshold: 80,
  });
  assertTrue("root expanded", exp.has("$"));
  assertEq("oversized child NOT expanded", exp.has("$/0"), false);
})();

// ── tree.js — materializeRows ─────────────────────────────────────
//
// Load tree.js into the same sandbox so we can probe materializeRows
// directly. preview.js is already loaded above and exposed as pv.
// Stub document so renderInlineTree's createElement calls would
// resolve, though we only call materializeRows here.
sandbox.document = {
  createElement: () => ({
    appendChild: () => {},
    addEventListener: () => {},
    classList: { add: () => {}, contains: () => false },
    style: {},
  }),
};
const treeSrc = fs.readFileSync(
  path.resolve(__dirname, "../../src/metabrowser/static/structured-tree.js"),
  "utf-8",
);
vm.runInContext(treeSrc, sandbox, { filename: "tree.js" });
const tree = sandbox.__structuredTree;

(() => {
  assertTrue("tree module loaded", !!tree && !!tree.materializeRows);

  // Empty object → one empty row.
  let rows = tree.materializeRows({}, new Set());
  assertEq("empty obj row count", rows.length, 1);
  assertEq("empty obj row kind", rows[0].kind, "empty");

  // Empty array → one empty row.
  rows = tree.materializeRows([], new Set());
  assertEq("empty arr row count", rows.length, 1);
  assertEq("empty arr row kind", rows[0].kind, "empty");
  assertEq("empty arr isArray", rows[0].isArray, true);

  // Primitive root → single kv row.
  rows = tree.materializeRows(42, new Set());
  assertEq("primitive root row count", rows.length, 1);
  assertEq("primitive root kind", rows[0].kind, "kv");

  // Collapsed object → just one open row (children hidden).
  rows = tree.materializeRows({ a: 1, b: 2 }, new Set()); // no paths expanded
  assertEq("collapsed obj row count", rows.length, 1);
  assertEq("collapsed obj kind", rows[0].kind, "open");
  assertEq("collapsed obj expanded", rows[0].expanded, false);

  // Expanded object → open row + 2 child kv rows.
  rows = tree.materializeRows({ a: 1, b: 2 }, new Set(["$"]));
  assertEq("expanded obj row count", rows.length, 3);
  assertEq("expanded obj open kind", rows[0].kind, "open");
  assertEq("expanded obj first child kind", rows[1].kind, "kv");
  assertEq("expanded obj first child key", rows[1].key, "a");
  assertEq("expanded obj second child key", rows[2].key, "b");

  // Expanded array → item rows with isArrayIndex true.
  rows = tree.materializeRows(["x", "y"], new Set(["$"]));
  assertEq("expanded arr row count", rows.length, 3);
  assertEq("expanded arr item kind", rows[1].kind, "item");
  assertEq("expanded arr item isArrayIndex", rows[1].isArrayIndex, true);

  // Deep: expanding only the root keeps grandchildren hidden.
  rows = tree.materializeRows({ a: { nested: 1 }, b: 2 }, new Set(["$"]));
  // root open + a open (collapsed) + b kv = 3 rows
  assertEq("deep partial-expand row count", rows.length, 3);
  // The nested container row should be open (kind=open) but not expanded.
  const nestedRow = rows.find((r) => r.path === "$/0");
  assertTrue("nested row present", !!nestedRow);
  assertEq("nested row expanded", nestedRow.expanded, false);

  // Deep: expanding root + child container produces grandchild row.
  rows = tree.materializeRows({ a: { nested: 1 } }, new Set(["$", "$/0"]));
  // root open + a open + nested kv = 3 rows
  assertEq("deep full-expand row count", rows.length, 3);
  const deepest = rows[2];
  assertEq("deepest kv key", deepest.key, "nested");
  assertEq("deepest kv level", deepest.level, 2);
  assertEq("deepest path", deepest.path, "$/0/0");

  // Array-of-objects: each child gets its own indexed path.
  rows = tree.materializeRows({ items: [{ q: 1 }, { q: 2 }] }, new Set(["$", "$/0", "$/0/0"]));
  // root open + items open + items[0] open + q=1 kv + items[1] open(collapsed) = 5
  assertEq("array-of-objects row count", rows.length, 5);
  assertEq("first item path", rows[2].path, "$/0/0");
  assertEq("first item.q path", rows[3].path, "$/0/0/0");
  assertEq("second item path", rows[4].path, "$/0/1");

  // A key's text never enters a path: a long key and a key with the scheme's own
  // characters both get their position, so two keys never share a path (mb-8274 A14).
  const long = "k".repeat(10_000);
  rows = tree.materializeRows({ [long]: { x: 1 }, "a/0": 1, a: [1] }, new Set(["$", "$/0", "$/2"]));
  assertEq("positional paths", rows.map((r) => r.path).join(" "), "$ $/0 $/0/0 $/1 $/2 $/2/0");
  assertEq("long key's path is short", rows[2].path.length, 5);
  assertEq("long key kept as the row's key", rows[1].key, long);

  // opts place the value inside a larger tree: its root row takes the path, level and key.
  rows = tree.materializeRows({ a: 1 }, new Set(["$~2/4"]), {
    path: "$~2/4",
    level: 2,
    key: "svc",
  });
  assertEq("placed root path", rows[0].path, "$~2/4");
  assertEq("placed root level", rows[0].level, 2);
  assertEq("placed root key", rows[0].key, "svc");
  assertEq("placed child path", rows[1].path, "$~2/4/0");
  assertEq("placed child level", rows[1].level, 3);
  rows = tree.materializeRows(7, new Set(), { path: "$/1", level: 1, isArrayIndex: true });
  assertEq("placed scalar item kind", rows[0].kind, "item");
  assertEq("placed scalar item key", rows[0].key, null);

  // limit draws that many children of an open container and one "more" row for the
  // rest; shown overrides the limit per container.
  const items = Array.from({ length: 7 }, (_, i) => i);
  rows = tree.materializeRows(items, new Set(["$"]), { limit: 3 });
  assertEq("limited row count", rows.length, 5);
  assertEq("more row kind", rows[4].kind, "more");
  assertEq("more row path", rows[4].path, "$/+");
  assertEq("more row hidden", rows[4].hidden, 4);
  assertEq("more row level", rows[4].level, 1);
  rows = tree.materializeRows(items, new Set(["$"]), { limit: 3, shown: new Map([["$", 6]]) });
  assertEq("shown row count", rows.length, 8);
  assertEq("shown more hidden", rows[7].hidden, 1);
  rows = tree.materializeRows(items, new Set(["$"]), { limit: 3, shown: new Map([["$", 9]]) });
  assertEq("all shown, no more row", rows.at(-1).kind, "item");

  // renderRowHtml draws the "more" row as chrome and a number's JSON text in place of
  // its value.
  let html = tree.renderRowHtml(
    { path: "$/+", level: 1, kind: "more", key: null, isArrayIndex: false, hidden: 4 },
    2,
  );
  assertTrue("more row class", html.includes('class="srow srow-more"'));
  assertTrue("more row label", html.includes('<span class="tok-meta">… 4 more</span>'));
  html = tree.renderRowHtml(
    {
      path: "$/0",
      level: 1,
      kind: "kv",
      key: "n",
      value: 1e16,
      text: "1e+16",
      isArrayIndex: false,
    },
    2,
  );
  assertTrue("number text drawn", html.includes('<span class="tok-number">1e+16</span>'));
  html = tree.renderRowHtml(
    {
      path: "$/0",
      level: 1,
      kind: "item",
      key: null,
      value: 2 ** 64,
      text: "18446744073709551616",
      isArrayIndex: true,
    },
    2,
  );
  assertTrue("big integer text drawn", html.includes(">18446744073709551616<"));

  assertEq("expansion maxLines", tree.expansion.maxLines, 500);
  assertEq("expansion frozen", Object.isFrozen(tree.expansion), true);
})();

if (failures.length) {
  for (const f of failures) {
    console.error(`FAIL: ${f}`);
  }
  process.exit(1);
}
console.log("OK " + "all preview.js + tree.js assertions");
