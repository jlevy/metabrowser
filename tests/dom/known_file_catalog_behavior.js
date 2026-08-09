const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const sandbox = {};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/known_file_catalog.js"),
  "utf-8",
);
vm.runInContext(source, sandbox, { filename: "known_file_catalog.js" });

const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

function equal(label, actual, expected) {
  check(label, JSON.stringify(actual) === JSON.stringify(expected), `${JSON.stringify(actual)}`);
}

const catalog = sandbox.MetabrowserKnownFileCatalog.create();
let snapshot = catalog.snapshot();
equal("new catalog is empty", snapshot.files, []);
check("catalog coverage is explicitly incomplete", snapshot.complete === false);
check("snapshot is frozen", Object.isFrozen(snapshot));

catalog.observeInitialTree([
  {
    name: "src",
    path: "src",
    type: "dir",
    children: [
      {
        name: "app.js",
        path: "src/app.js",
        type: "file",
        logical_ext: ".js",
      },
      {
        name: "lazy",
        path: "src/lazy",
        type: "dir",
        children: null,
      },
    ],
  },
  { name: "README.md", path: "README.md", type: "file" },
]);

snapshot = catalog.snapshot();
equal(
  "tree traversal records only file leaves",
  snapshot.files.map((file) => file.path),
  ["README.md", "src/app.js"],
);
equal("source summary counts latest observations", snapshot.sourceSummary, {
  "initial-tree": 2,
});
check(
  "file records are frozen",
  snapshot.files.every((file) => Object.isFrozen(file)),
);
check("file list is frozen", Object.isFrozen(snapshot.files));

const stableRevision = snapshot.revision;
catalog.observeInitialTree([{ name: "README.md", path: "README.md", type: "file" }]);
check("identical observations are idempotent", catalog.snapshot().revision === stableRevision);

catalog.observeLazyTree([{ name: "mounted.py", path: "src/lazy/mounted.py", type: "file" }]);

catalog.observeRecent([
  { name: "deep.jsonl.gz", path: "runs/deep.jsonl.gz", type: "file", logical_ext: ".jsonl" },
]);
catalog.observeEventSnapshot([
  { name: "live.log", path: "logs/live.log", type: "file" },
  { name: "logs", path: "logs", type: "dir" },
]);
catalog.observeNavigation("direct/unmounted.md", ".md");
catalog.applyEventChange([
  { op: "upsert", entry: { name: "new.txt", path: "tmp/new.txt", type: "file" } },
  { op: "upsert", entry: { name: "tmp", path: "tmp", type: "dir" } },
]);

snapshot = catalog.snapshot();
equal(
  "every observation adapter shares one catalog",
  snapshot.files.map((file) => file.path),
  [
    "README.md",
    "direct/unmounted.md",
    "logs/live.log",
    "runs/deep.jsonl.gz",
    "src/app.js",
    "src/lazy/mounted.py",
    "tmp/new.txt",
  ],
);
equal("logical extensions survive ingestion", snapshot.files[3].logicalExtension, ".jsonl");

catalog.applyEventChange([{ op: "remove", path: "runs" }]);
check(
  "scoped removal deletes descendants",
  !catalog.snapshot().files.some((file) => file.path.startsWith("runs/")),
);

catalog.clear();
snapshot = catalog.snapshot();
equal("resync clearing removes every observation source", snapshot.files, []);
equal("clearing resets source counts", snapshot.sourceSummary, {});
check("cleared catalog remains incomplete", snapshot.complete === false);

// ── Bulk feed and catalog.change ───────────────────────────────

const memoBefore = catalog.snapshot();
check("snapshot is memoized by revision", catalog.snapshot() === memoBefore);

catalog.observeNavigation("visited/ignored.log", ".log");
catalog.applyBulkSnapshot(
  [
    { p: "README.md", e: ".md" },
    { p: "docs/deep/nested/leaf.txt", e: ".txt" },
  ],
  true,
);
snapshot = catalog.snapshot();
check("bulk apply invalidates the memoized snapshot", snapshot !== memoBefore);
check("complete bulk apply marks the catalog complete", snapshot.complete === true);
check(
  "bulk apply merges instead of replacing observed paths",
  snapshot.files.some((file) => file.path === "visited/ignored.log"),
);
equal(
  "bulk entries carry path and logical extension",
  snapshot.files.find((file) => file.path === "docs/deep/nested/leaf.txt")?.logicalExtension,
  ".txt",
);
equal("bulk entries record their source", snapshot.sourceSummary["catalog-feed"], 2);

catalog.applyCatalogChange({
  upserts: [{ p: "src/new_module.py", e: ".py" }],
  removes: ["README.md"],
});
snapshot = catalog.snapshot();
check(
  "catalog.change upserts land",
  snapshot.files.some((file) => file.path === "src/new_module.py"),
);
check("catalog.change removes land", !snapshot.files.some((file) => file.path === "README.md"));

const incompleteCatalog = sandbox.MetabrowserKnownFileCatalog.create();
incompleteCatalog.applyBulkSnapshot([{ p: "a.txt", e: ".txt" }], false);
check("incomplete bulk apply stays incomplete", incompleteCatalog.snapshot().complete === false);
incompleteCatalog.markComplete();
check(
  "markComplete flips completeness without data",
  incompleteCatalog.snapshot().complete === true,
);
incompleteCatalog.clear();
check("clear resets completeness", incompleteCatalog.snapshot().complete === false);

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("OK known file catalog\n");
