// Behavioural checks for static/tree-filter-model.js: what a filter selection
// asks the server for, and which clustered rows a filter leaves standing.
//
// No DOM. That is the point of the module: these were the two decisions buried
// in a document walk, and the navigation panel's filtering bugs were in them.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const sandbox = { encodeURIComponent, Map, Set, Object, Array, String };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/tree-filter-model.js"), "utf-8"),
  sandbox,
  { filename: "tree-filter-model.js" },
);

const model = sandbox.MetabrowserTreeFilterModel;
const failures = [];

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    failures.push(`${label}: expected ${JSON.stringify(expected)} got ${JSON.stringify(actual)}`);
  }
}

const SIZE_FLOORS = { all: 0, "100k": 102400, "1m": 1048576, "10m": 10485760 };

function snapshot(patch) {
  return Object.assign({ recency: "all", types: null, size: "all", showIgnored: true }, patch);
}

// ── The request ──────────────────────────────────────────────────

assertEqual(
  "a default selection asks for nothing",
  model.requestParams(snapshot({}), SIZE_FLOORS),
  [],
);
assertEqual("no state at all is also no constraint", model.requestParams(null, SIZE_FLOORS), []);
assertEqual(
  "types travel as one comma-separated parameter",
  model.requestParams(snapshot({ types: [".md", ".py"] }), SIZE_FLOORS),
  ["types=.md%2C.py"],
);
// The bucket name is the browser's label; only a byte count crosses the wire,
// so the server needs no second copy of the table.
assertEqual(
  "a size bucket travels as its floor in bytes",
  model.requestParams(snapshot({ size: "1m" }), SIZE_FLOORS),
  ["min_size=1048576"],
);
assertEqual(
  "the unbounded bucket is no constraint",
  model.requestParams(snapshot({ size: "all" }), SIZE_FLOORS),
  [],
);
assertEqual(
  "hiding gitignored entries is a request parameter, not a class",
  model.requestParams(snapshot({ showIgnored: false }), SIZE_FLOORS),
  ["include_ignored=0"],
);
// Recency belongs to /api/recent, which owns the panel while a window is set.
assertEqual(
  "a recency window is not a tree parameter",
  model.requestParams(snapshot({ recency: "24h" }), SIZE_FLOORS),
  [],
);

assertEqual(
  "an unfiltered tree request carries no query at all",
  model.treeUrl("", snapshot({}), SIZE_FLOORS),
  "/api/tree",
);
assertEqual(
  "a subtree request leads with its path and keeps the filter",
  model.treeUrl("a/b c", snapshot({ types: [".md"] }), SIZE_FLOORS, ["depth=2"]),
  "/api/tree?path=a%2Fb%20c&types=.md&depth=2",
);

// Two selections that ask for the same thing share a cache entry; two that do
// not must never, or narrowing the filter would expand folders out of a cache
// filled while it was wider.
assertEqual(
  "the cache key follows the selection",
  model.requestKey(snapshot({ types: [".md"] }), SIZE_FLOORS) ===
    model.requestKey(snapshot({ types: [".md"], recency: "24h" }), SIZE_FLOORS),
  true,
);
assertEqual(
  "a narrower selection is a different key",
  model.requestKey(snapshot({ types: [".md"] }), SIZE_FLOORS) ===
    model.requestKey(snapshot({ types: [".md"], showIgnored: false }), SIZE_FLOORS),
  false,
);

// ── Cluster verdicts ─────────────────────────────────────────────

/** Rows in document order: [id, parentId, isDir, matched]. */
function rows(...tuples) {
  return tuples.map(([id, parentId, isDir, matched]) => ({ id, parentId, isDir, matched }));
}

function hidden(...tuples) {
  return Array.from(model.clusterHiddenIds(rows(...tuples))).sort();
}

assertEqual(
  "a folder survives on a surviving child",
  hidden(["dir", null, true, true], ["kid", "dir", false, true]),
  [],
);
assertEqual(
  "a folder whose every child was filtered out goes with them",
  hidden(["dir", null, true, true], ["kid", "dir", false, false]),
  ["dir", "kid"],
);
// The clustered source builds a folder out of the matching files themselves,
// so a folder with no children listed has none — unlike the tree source, where
// that meant "never sent" and keeping it was the bug this replaced.
assertEqual("a childless folder is empty, not unknown", hidden(["dir", null, true, true]), ["dir"]);
assertEqual(
  "a pruned folder takes its descendants with it, however deep",
  hidden(
    ["a", null, true, true],
    ["b", "a", true, true],
    ["c", "b", false, false],
    ["d", "b", true, true],
    ["e", "d", false, false],
  ),
  ["a", "b", "c", "d", "e"],
);
assertEqual(
  "one surviving leaf keeps its whole ancestry",
  hidden(
    ["a", null, true, true],
    ["b", "a", true, true],
    ["c", "b", false, true],
    ["d", "a", true, true],
    ["e", "d", false, false],
  ),
  ["d", "e"],
);
// A row that fails the predicate itself is hidden even when its siblings pass,
// and its parent still survives on them.
assertEqual(
  "siblings are judged independently",
  hidden(["dir", null, true, true], ["yes", "dir", false, true], ["no", "dir", false, false]),
  ["no"],
);
assertEqual("an empty list decides nothing", hidden(), []);

if (failures.length > 0) {
  console.error(`FAIL tree filter model\n${failures.join("\n")}`);
  process.exit(1);
}
console.log("OK tree filter model");
