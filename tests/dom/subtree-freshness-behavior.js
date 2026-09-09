const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
  process.argv[2] || path.resolve(__dirname, "../../src/metabrowser/static/app.js"),
  "utf8",
);
const functionNames = [
  "subtreeCacheKey",
  "invalidateSubtreeCaches",
  "invalidateFilePreviews",
  "fetchSubtree",
  "fileStoreApplyChangeInner",
  "_findChildContainerFor",
];
const functions = functionNames
  .map((name) => source.match(new RegExp(`^function ${name}\\([\\s\\S]*?^}`, "m"))?.[0] || "")
  .join("\n");
const requests = [];
const observed = [];
const context = vm.createContext({
  subtreeCache: new Map(),
  subtreeRequests: new Map(),
  fileStore: new Map(),
  fileCache: new Map(),
  fileNeedsRevalidate: new Set(),
  currentPath: "",
  hoverPrefetchPath: "",
  activeFiles: new Map(),
  inventoryChangeHighlightingActive: false,
  TREE_SUBTREE_FETCH_DEPTH: 2,
  treeFilterKey: () => "",
  treeUrl: (folder) => folder,
  fetch: (folder) =>
    new Promise((resolve) => {
      requests.push({
        folder,
        resolve: (tree) => resolve({ ok: true, json: async () => ({ tree }) }),
      });
    }),
  _perf: { measure: (_name, fn) => fn(), measureAsync: (_name, fn) => fn() },
  responsePerfMeta: () => ({}),
  knownFileCatalog: { applyEventChange() {}, observeLazyTree: (tree) => observed.push(tree) },
  applyCellPatch() {},
  _mirrorActiveFromFsEntry() {},
  _removeDeferredTreePageEntries() {},
  _removeRenderedRows() {},
  recentBaseApplyOp() {},
  notifyFileStoreSubscribers() {},
  escapePathForSelector: (value) => value,
  window: {},
});
vm.runInContext(functions, context);

async function main() {
  // A collapsed folder can have cached children for several filter states.
  context.subtreeCache.set("d%251", [{ path: "d%251/old.txt" }]);
  context.subtreeCache.set("d%251\u0000filtered", []);
  context.subtreeCache.set("other", [{ path: "other/keep.txt" }]);
  context.fileStoreApplyChangeInner([
    { op: "upsert", entry: { path: "d%251/new.txt", type: "file" } },
  ]);
  assert.equal(context.subtreeCache.has("d%251"), false, "prefetched children became stale");
  assert.equal(context.subtreeCache.has("d%251\u0000filtered"), false);
  assert.equal(context.subtreeCache.has("other"), true, "unrelated folders remain warm");

  // An earlier request cannot overwrite a newer filesystem event on completion.
  const pending = context.fetchSubtree("d%251");
  context.fileStoreApplyChangeInner([
    { op: "upsert", entry: { path: "d%251/newer.txt", type: "file" } },
  ]);
  requests[0].resolve([{ path: "d%251/old.txt" }]);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(requests.length, 2, "invalidated in-flight reads refresh before mounting");
  assert.equal(observed.length, 0, "stale reads must not populate the catalog");
  const fresh = [{ path: "d%251/new.txt" }, { path: "d%251/newer.txt" }];
  requests[1].resolve(fresh);
  assert.deepEqual((await pending).tree, fresh);
  assert.deepEqual(context.subtreeCache.get("d%251"), fresh);
  context.subtreeCache.set("d%251/nested", []);
  context.fileStoreApplyChangeInner([{ op: "remove", path: "d%251" }]);
  assert.equal(context.subtreeCache.has("d%251/nested"), false);

  // Editing an inactive cached file must revalidate on its next selection.
  const before = { path: "notes/readme.md", type: "file", size: 20, mtime_ns: 100 };
  context.fileStore.set(before.path, before);
  context.fileCache.set(before.path, { content: "old preview" });
  context.fileStoreApplyChangeInner([{ op: "upsert", entry: { ...before, active: false } }]);
  assert.equal(context.fileNeedsRevalidate.has(before.path), false, "unchanged facts stay hot");
  context.fileStoreApplyChangeInner([
    { op: "upsert", entry: { ...before, size: 30, mtime_ns: 200 } },
  ]);
  assert.equal(context.fileNeedsRevalidate.has(before.path), true, "edited file revalidates");
  context.fileNeedsRevalidate.clear();
  context.fileCache.set("notes/deep/unsubscribed.md", { content: "deep preview" });
  context.fileStoreApplyChangeInner([{ op: "upsert", entry: { path: "notes", type: "dir" } }]);
  assert.equal(context.fileNeedsRevalidate.has("notes/deep/unsubscribed.md"), true);

  // Already-mounted hidden rows update without forcing unvisited folders to mount.
  let lazy = false;
  const children = {
    classList: { contains: (name) => name === "tree-children" },
    querySelector: () => (lazy ? {} : null),
  };
  const panel = {
    querySelector: () => ({ classList: { contains: () => false }, nextElementSibling: children }),
  };
  assert.equal(context._findChildContainerFor("d%251", panel), children);
  lazy = true;
  assert.equal(context._findChildContainerFor("d%251", panel), null);
  process.stdout.write("subtree freshness OK\n");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
