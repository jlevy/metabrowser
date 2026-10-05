// Run the production snapshot boundary with recording presentation collaborators.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.resolve(__dirname, "../..");
const app = fs.readFileSync(path.join(root, "src/metabrowser/static/app.js"), "utf8");
const snapshot = app.match(/^function fileStoreApplySnapshotInner\([^)]*\) \{[\s\S]*?^\}/m)[0];
const observations = [];
for (const filtered of [false, true]) {
  const calls = [];
  const sandbox = {
    console,
    Map,
    Set,
    fileStore: new Map([["gone.md", { path: "gone.md", type: "file" }]]),
    fileCache: new Map(),
    fileNeedsRevalidate: new Set(),
    activeFiles: new Map(),
    subtreeCache: new Map(),
    subtreeRequests: new Map(),
    recentContinuity: { dirtyActiveRequest() {} },
    filterState: { get: () => ({ types: filtered ? [".md"] : null }) },
    filterHasConstraints: (state) => !!state.types,
    filesPanelUsesRecentSource: () => false,
    applyCellPatch: (entry) => calls.push(["patch", entry.path]),
    _mirrorActiveFromFsEntry() {},
    _removeDeferredTreePageEntries() {},
    _removeRenderedRowsImmediately: (name) => calls.push(["retire", name]),
    loadTree: (options) => calls.push(["filtered-tree", options.reconcileMountedRoot]),
    notifyFileStoreSubscribers() {},
    knownFileCatalog: null,
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(
    fs.readFileSync(path.join(root, "src/metabrowser/static/navigation.js"), "utf8"),
    sandbox,
  );
  vm.runInContext(snapshot, sandbox);
  sandbox.fileStoreApplySnapshotInner("root-depth-2", [
    { path: "excluded", type: "dir", total_files: 90 },
  ]);
  assert.deepEqual(
    calls,
    filtered
      ? [
          ["retire", "gone.md"],
          ["filtered-tree", true],
        ]
      : [
          ["retire", "gone.md"],
          ["patch", "excluded"],
        ],
  );
  assert.equal(sandbox.fileStore.has("excluded"), true);
  observations.push({ filtered, calls });
}
// A broken connection must not prevent other parked connections from resuming.
const sandbox = { console: { warn() {} } };
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(
  fs.readFileSync(path.join(root, "src/metabrowser/static/navigation.js"), "utf8"),
  sandbox,
);
let resumed = 0;
const owner = sandbox.MetabrowserNavigationRoute.createPageConnections({
  connections: [
    () => () => {
      throw new Error("broken resume");
    },
    () => () => resumed++,
  ],
  rebuild() {
    throw new Error("kept controls must not be rebuilt");
  },
  teardown() {},
});
owner.hidden(true);
owner.hidden(true);
owner.shown(true);
owner.shown(true);
assert.equal(resumed, 1);
assert.equal(owner.parked(), 0);
assert.equal(owner.suspended(), false);
console.log(JSON.stringify({ observations, resumed }));
