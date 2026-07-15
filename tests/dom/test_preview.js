// Pure-function tests for structured/preview.js.
//
// Runs in a Node vm sandbox (same approach as load_plugins.js) — no
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
  path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/structured/preview.js"),
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
  assertTrue("$.a expanded", exp.has("$.a"));
  assertTrue("$.c expanded", exp.has("$.c"));
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
  assertEq("oversized child NOT expanded", exp.has("$.big"), false);
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
  path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/structured/tree.js"),
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
  const nestedRow = rows.find((r) => r.path === "$.a");
  assertTrue("nested row present", !!nestedRow);
  assertEq("nested row expanded", nestedRow.expanded, false);

  // Deep: expanding root + child container produces grandchild row.
  rows = tree.materializeRows({ a: { nested: 1 } }, new Set(["$", "$.a"]));
  // root open + a open + nested kv = 3 rows
  assertEq("deep full-expand row count", rows.length, 3);
  const deepest = rows[2];
  assertEq("deepest kv key", deepest.key, "nested");
  assertEq("deepest kv level", deepest.level, 2);
  assertEq("deepest path", deepest.path, "$.a.nested");

  // Array-of-objects: each child gets its own indexed path.
  rows = tree.materializeRows(
    { items: [{ q: 1 }, { q: 2 }] },
    new Set(["$", "$.items", "$.items[0]"]),
  );
  // root open + items open + items[0] open + q=1 kv + items[1] open(collapsed) = 5
  assertEq("array-of-objects row count", rows.length, 5);
  assertEq("first item path", rows[2].path, "$.items[0]");
  assertEq("first item.q path", rows[3].path, "$.items[0].q");
})();

if (failures.length) {
  for (const f of failures) {
    console.error(`FAIL: ${f}`);
  }
  process.exit(1);
}
console.log("OK " + "all preview.js + tree.js assertions");
