// Run the production snapshot boundary with recording presentation collaborators.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.resolve(__dirname, "../..");
const navigationFile = path.join(root, "src/metabrowser/static/navigation.js");
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
    isGitRevisionSource: () => false,
    document: { getElementById: () => null },
    applyCellPatch: (entry) => calls.push(["patch", entry.path]),
    _mirrorActiveFromFsEntry() {},
    _removeDeferredTreePageEntries() {},
    _removeRenderedRowsImmediately: (name) => calls.push(["retire", name]),
    loadTree: (options) => calls.push(["filtered-tree", options.reconcileMountedRoot]),
    loadSubtree() {
      throw new Error("a snapshot with no mounted panel must not retry a subtree");
    },
    notifyFileStoreSubscribers() {},
    knownFileCatalog: null,
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(navigationFile, "utf8"), sandbox, { filename: navigationFile });
  vm.runInContext(snapshot, sandbox);
  vm.runInContext(
    app.match(/^function retryFailedExpandedSubtrees\([^)]*\) \{[\s\S]*?^\}/m)[0],
    sandbox,
  );
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
vm.runInContext(fs.readFileSync(navigationFile, "utf8"), sandbox, { filename: navigationFile });
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

// A reconnect snapshot is authoritative, but does not itself replace an expanded
// folder's failed lazy body. Exercise the production loaders, not an onopen spy.
function recoverySession(filtered = false) {
  const requests = [];
  const calls = [];
  let parses = 0;
  let snapshots = 0;
  const classes = new Set(["tree-folder", "expanded"]);
  const row = { dataset: { path: "docs" }, classList: { contains: (name) => classes.has(name) } };
  let html = "";
  let present = true;
  let revision = false;
  const children = {
    parentNode: {},
    previousElementSibling: row,
    classList: { contains: (name) => name === "tree-children" },
    get innerHTML() {
      return html;
    },
    set innerHTML(value) {
      html = value;
    },
  };
  const failed = { parentElement: children };
  const panel = {
    querySelectorAll: () => (html.includes("tree-lazy-error") ? [failed] : []),
    contains: (node) => node === children && children.parentNode !== null,
  };
  const context = {
    console: { warn() {} },
    Map,
    Set,
    JSON: {
      parse: (text) => {
        parses++;
        return JSON.parse(text);
      },
    },
    EventSource: class {
      handlers = new Map();
      addEventListener(name, handler) {
        this.handlers.set(name, handler);
      }
    },
    pageConnections: { suspended: () => false },
    inventoryEventSource: null,
    lastInventorySnapshot: null,
    recentEverLoaded: false,
    quickFileCatalogFeed: { onSentinelSnapshot() {} },
    treeFilterModel: { observeRecentSentinel() {} },
    recentFilterRefetch: { pending: () => false },
    recentRepairDescriptor: () => ({}),
    _scheduleRecentRecompute() {},
    fileStore: new Map([["docs", { path: "docs", type: "dir" }]]),
    fileCache: new Map(),
    fileNeedsRevalidate: new Set(),
    activeFiles: new Map(),
    subtreeCache: new Map(),
    subtreeRequests: new Map(),
    treeKeyboard: null,
    TREE_SUBTREE_FETCH_DEPTH: 2,
    treeFilterKey: () => (filtered ? "markdown" : ""),
    treeUrl: (folder) => folder,
    fetch: (folder) => new Promise((resolve, reject) => requests.push({ folder, resolve, reject })),
    _perf: { measure: (_name, fn) => fn(), measureAsync: (_name, fn) => fn() },
    responsePerfMeta: () => ({}),
    knownFileCatalog: {
      observeEventSnapshot() {
        snapshots++;
      },
      observeInitialTree() {},
      observeLazyTree() {},
    },
    recentContinuity: { dirtyActiveRequest() {} },
    filterState: { get: () => ({ types: filtered ? [".md"] : null }) },
    filterHasConstraints: (state) => !!state.types,
    filesPanelUsesRecentSource: () => false,
    isGitRevisionSource: () => revision,
    document: { getElementById: (id) => (id === "tab-files" && present ? panel : null) },
    applyCellPatch() {},
    _mirrorActiveFromFsEntry() {},
    _removeDeferredTreePageEntries() {},
    _removeRenderedRowsImmediately() {},
    notifyFileStoreSubscribers() {},
    clearSubtreeRetry() {},
    treeRenderOptionsForElement: () => ({}),
    treeLazyLoadingHtml: () => '<div class="tree-lazy-placeholder">Loading</div>',
    treeLazyFailureHtml: () => '<div class="tree-lazy-placeholder tree-lazy-error">Offline</div>',
    renderTreeNodes: (nodes) => nodes.map((node) => `<div>${node.path}</div>`).join(""),
    treeLevelForContainer: () => 2,
    escapePathForSelector: (value) => value,
    markFolderKnownEmpty() {},
    applyTreeFilters() {},
    reconcilePendingTallyDiagnostics() {},
    synchronizeTreeNow() {},
    scheduleSubtreePrefetch() {},
    renderInitialTreeRows() {},
    queryHtml: () => null,
    renderServedRootHeading() {},
    rootTallyFromTopLevel: () => ({ files: 1, size: 10, newestMtime: 1 }),
    treeSummaryHtml: () => "",
    updateFilterTallies: () => false,
    _rootTreeRequestsInFlight: 0,
    _inlineTreeBaseline: null,
    reconcileMountedTree: () => calls.push("authoritative root reconciled"),
  };
  context.window = context;
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(navigationFile, "utf8"), context, { filename: navigationFile });
  for (const name of [
    "fileStoreApplySnapshotInner",
    "fileStoreApplySnapshot",
    "_createInventoryEventSource",
    "loadTree",
    "loadSubtree",
    "fetchSubtree",
    "subtreeCacheKey",
    "subtreeIsExpanded",
    "retryFailedExpandedSubtrees",
    "reconcileTreeContainer",
    "treeNodeAsEntry",
  ]) {
    const declaration = app.match(
      new RegExp(`^(?:async )?function ${name}\\([^)]*\\) \\{[\\s\\S]*?^\\}`, "m"),
    );
    assert.ok(declaration, name);
    vm.runInContext(declaration[0], context);
  }
  const snapshot = () =>
    context.fileStoreApplySnapshotInner("root-depth-2", [{ path: "docs", type: "dir" }]);
  return {
    context,
    requests,
    calls,
    children,
    classes,
    snapshot,
    dispose: () => {
      present = false;
    },
    pin: () => {
      revision = true;
    },
    sentinelCounts: () => ({ parses, snapshots }),
  };
}

async function checkExpandedFolderRecovery() {
  const recovered = [];
  for (const filtered of [false, true]) {
    const s = recoverySession(filtered);
    s.context._createInventoryEventSource();
    const listener = s.context.inventoryEventSource.handlers.get("fs.snapshot");
    const sentinel = {
      data: JSON.stringify({
        scope: "root-depth-2",
        complete: true,
        entries: [{ path: "docs", type: "dir" }],
      }),
    };
    const rootReply = {
      ok: true,
      json: async () => ({
        tree: [{ path: "docs", type: "dir" }],
        summary: {},
        tally_cache_status: "done",
      }),
    };
    listener(sentinel);
    if (filtered) {
      s.requests.at(-1).resolve(rootReply);
      await new Promise(setImmediate);
    }
    const healthyCount = s.requests.length;
    listener(sentinel);
    assert.equal(s.requests.length, healthyCount, "healthy identical sentinel does not refetch");
    const initial = s.context.loadSubtree("docs", s.children);
    s.requests.at(-1).reject(new Error("offline"));
    await initial;
    assert.match(s.children.innerHTML, /tree-lazy-error/);
    const ahead = s.context.fetchSubtree("docs");
    const stale = s.requests.at(-1);
    const key = s.context.subtreeCacheKey("docs");
    s.context.subtreeCache.set(key, [{ path: "stale-cache.md", type: "file" }]);
    s.context.subtreeCache.set("healthy", ["retained"]);
    const healthyRequest = Promise.resolve("retained");
    s.context.subtreeRequests.set("healthy", healthyRequest);
    const before = s.requests.length;
    listener(sentinel);
    assert.equal(
      s.requests.length,
      before + 1,
      "identical sentinel recovers a failed expanded folder",
    );
    if (filtered) {
      const root = s.requests.at(-1);
      assert.equal(root.folder, "", "filtered recovery waits for its root answer");
      listener(sentinel);
      assert.equal(s.requests.at(-1), root, "identical sentinels share an in-flight root answer");
      root.resolve(rootReply);
    }
    await new Promise(setImmediate);
    const retry = s.requests.at(-1);
    assert.equal(retry.folder, "docs");
    assert.notEqual(retry, stale);
    stale.resolve({
      ok: true,
      json: async () => ({ tree: [{ path: "stale-request.md", type: "file" }] }),
    });
    await new Promise(setImmediate);
    assert.equal(s.requests.at(-1), retry, "stale read joins the revalidated failed-path request");
    assert.doesNotMatch(s.children.innerHTML, /stale-/);
    retry.resolve({
      ok: true,
      json: async () => ({ tree: [{ path: "docs/guide.md", type: "file" }] }),
    });
    await ahead;
    await new Promise(setImmediate);
    assert.match(s.children.innerHTML, /docs\/guide\.md/);
    assert.doesNotMatch(s.children.innerHTML, /tree-lazy-error/);
    assert.deepEqual(s.context.subtreeCache.get("healthy"), ["retained"]);
    assert.equal(s.context.subtreeRequests.get("healthy"), healthyRequest);
    assert.deepEqual(s.sentinelCounts(), { parses: 1, snapshots: 1 });
    recovered.push({
      filtered,
      folder: "docs",
      restored: "docs/guide.md",
      ...s.sentinelCounts(),
      healthyCacheRetained: true,
      staleReadRejected: true,
    });
  }
  return recovered;
}

async function failedSession() {
  const s = recoverySession();
  const initial = s.context.loadSubtree("docs", s.children);
  s.requests[0].reject(new Error("offline"));
  await initial;
  assert.match(s.children.innerHTML, /tree-lazy-error/);
  return s;
}

async function checkRecoveryBoundaries() {
  const kept = [];
  for (const mode of ["successful", "collapsed", "pinned", "Recent", "detached", "disposed"]) {
    const s = await failedSession();
    if (mode === "successful") {
      s.children.innerHTML = "already loaded guide.md";
    }
    if (mode === "collapsed") {
      s.classes.delete("expanded");
    }
    if (mode === "pinned") {
      s.pin();
    }
    if (mode === "Recent") {
      s.context.filesPanelUsesRecentSource = () => true;
    }
    if (mode === "detached") {
      s.children.parentNode = null;
    }
    if (mode === "disposed") {
      s.dispose();
    }
    const before = s.children.innerHTML;
    s.snapshot();
    await new Promise(setImmediate);
    assert.equal(s.requests.length, 1, `${mode} body must not be retried`);
    assert.equal(s.children.innerHTML, before, `${mode} body must not be replaced`);
    kept.push(mode);
  }

  const loading = await failedSession();
  loading.snapshot();
  const pending = loading.requests[1];
  loading.snapshot();
  assert.equal(loading.requests.length, 2, "an in-flight body is not restarted by recovery");
  pending.resolve({ ok: true, json: async () => ({ tree: [{ path: "stale.md", type: "file" }] }) });
  await new Promise(setImmediate);
  assert.equal(loading.requests.length, 3, "fetchSubtree revalidates the invalidated answer");
  assert.doesNotMatch(loading.children.innerHTML, /stale.md/);
  loading.requests[2].resolve({
    ok: true,
    json: async () => ({ tree: [{ path: "docs/guide.md", type: "file" }] }),
  });
  await new Promise(setImmediate);
  assert.match(loading.children.innerHTML, /docs\/guide.md/);

  const prefetched = recoverySession(true);
  const failedRead = prefetched.context.loadSubtree("docs", prefetched.children);
  prefetched.requests[0].reject(new Error("offline"));
  await failedRead;
  prefetched.snapshot();
  const ahead = prefetched.context.fetchSubtree("docs");
  prefetched.requests[1].resolve({
    ok: true,
    json: async () => ({
      tree: [{ path: "docs", type: "dir" }],
      summary: {},
      tally_cache_status: "done",
    }),
  });
  await new Promise(setImmediate);
  assert.equal(prefetched.requests.length, 3, "recovery joins the existing prefetch");
  prefetched.requests[2].resolve({
    ok: true,
    json: async () => ({ tree: [{ path: "docs/guide.md", type: "file" }] }),
  });
  await ahead;
  await new Promise(setImmediate);
  assert.ok(prefetched.children.innerHTML.includes("docs/guide.md"));

  const failedAgain = await failedSession();
  failedAgain.snapshot();
  failedAgain.requests[1].reject(new Error("still offline"));
  await new Promise(setImmediate);
  assert.equal(failedAgain.requests.length, 2, "a failed retry does not start a retry loop");
  assert.match(failedAgain.children.innerHTML, /tree-lazy-error/);

  // Collapsing an ancestor preserves a child's own disclosure. Reopening the
  // ancestor only loads its direct stub, so the expanded child still needs repair.
  const nested = await failedSession();
  nested.children.parentNode = {
    classList: { contains: (name) => name === "tree-children-collapsed" },
  };
  nested.snapshot();
  assert.equal(
    nested.requests.length,
    2,
    "a logically expanded child still recovers under a collapsed ancestor",
  );
  nested.requests[1].resolve({
    ok: true,
    json: async () => ({ tree: [{ path: "docs/guide.md", type: "file" }] }),
  });
  await new Promise(setImmediate);
  assert.ok(nested.children.innerHTML.includes("docs/guide.md"));

  const supplied = await failedSession();
  supplied.children.querySelectorAll = () => [];
  supplied.children.querySelector = (selector) =>
    selector === ":scope > .tree-lazy-error"
      ? {
          remove: () => {
            supplied.children.innerHTML = "";
          },
        }
      : { classList: { remove() {} }, dataset: {} };
  supplied.context.TREE_PAGE_SIZE = 100;
  supplied.context.removeDeferredPageForContainer = () => {};
  supplied.context.applyCellPatch = (entry) => {
    supplied.children.innerHTML += entry.path;
  };
  supplied.context.reconcileTreeContainer(
    supplied.children,
    [{ path: "docs/guide.md", type: "file" }],
    { work_items: 0 },
  );
  supplied.context.retryFailedExpandedSubtrees();
  assert.equal(supplied.requests.length, 1, "supplied authoritative children need no new request");
  assert.match(supplied.children.innerHTML, /docs\/guide.md/);
  assert.doesNotMatch(supplied.children.innerHTML, /tree-lazy-error/);
  return {
    kept,
    inFlight: "joined; invalidated answer revalidated",
    failedRetry: "waits for authoritative recovery",
    collapsedAncestor: "expanded child repaired; own-collapsed body retained",
    suppliedChildren: "stale failure removed without fetching",
  };
}

Promise.all([checkExpandedFolderRecovery(), checkRecoveryBoundaries()])
  .then(([recovery, boundaries]) =>
    console.log(JSON.stringify({ observations, resumed, recovery, boundaries }, null, 2)),
  )
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
