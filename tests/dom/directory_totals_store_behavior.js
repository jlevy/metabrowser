const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/directory_totals_store.js"),
  "utf8",
);
const sandbox = { window: {} };
sandbox.window.window = sandbox.window;
vm.runInNewContext(source, sandbox, { filename: "directory_totals_store.js" });

const store = sandbox.window.metabrowserDirectoryTotalsStore;
const seen = [];
const unsubscribe = store.subscribe("src", (value) => seen.push(value));

store.applySnapshot([
  {
    path: "src",
    type: "dir",
    total_files: 8,
    total_size: 80,
    unignored_files: 5,
    unignored_size: 50,
  },
  { path: "src/a.py", type: "file", size: 10 },
]);
const first = store.get("src");
if (
  first?.totalFiles !== 8 ||
  first?.totalBytes !== 80 ||
  first?.unignoredFiles !== 5 ||
  first?.unignoredBytes !== 50 ||
  first?.state !== "complete"
) {
  throw new Error(`snapshot totals were not normalized: ${JSON.stringify(first)}`);
}

store.applyChange([
  {
    op: "upsert",
    entry: {
      path: "src",
      type: "dir",
      total_files: 9,
      total_size: 100,
      unignored_files: 6,
      unignored_size: 70,
    },
  },
]);
if (store.get("src")?.totalFiles !== 9 || seen.at(-1)?.totalBytes !== 100) {
  throw new Error("directory upsert did not publish an atomic replacement");
}

store.applyChange([{ op: "remove", path: "src" }]);
if (store.get("src") !== null || seen.at(-1) !== null) {
  throw new Error("directory removal did not clear subscribers");
}
unsubscribe();
console.log(JSON.stringify({ ok: true, notifications: seen.length }));
