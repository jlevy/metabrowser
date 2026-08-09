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

// A bulk response built mid-walk can resolve after the one-shot
// walk-completion event already marked the catalog complete; the
// stale flag must not downgrade it (Bugbot R6).
const racedCatalog = sandbox.MetabrowserKnownFileCatalog.create();
racedCatalog.markComplete();
racedCatalog.applyBulkSnapshot([{ p: "late.txt", e: ".txt" }], false);
check(
  "stale incomplete bulk cannot downgrade completeness",
  racedCatalog.snapshot().complete === true,
);
check(
  "the downgrade-refused bulk still merges its files",
  racedCatalog.snapshot().files.some((file) => file.path === "late.txt"),
);

// The bulk feed excludes gitignored files, but the tree and inventory
// payloads carry them (the tree dims ignored rows rather than hiding them).
// A catalog that reports itself complete and non-gitignored must not offer
// files the feed deliberately dropped (senior review R8).
const ignoredCatalog = sandbox.MetabrowserKnownFileCatalog.create();
ignoredCatalog.observeInitialTree([
  { logical_ext: ".py", path: "app.py", type: "file" },
  { gitignored: true, logical_ext: ".pyc", path: "__pycache__/ignored.pyc", type: "file" },
  {
    children: [
      { gitignored: true, logical_ext: ".js", path: "node_modules/dep/index.js", type: "file" },
    ],
    gitignored: true,
    path: "node_modules",
    type: "dir",
  },
]);
ignoredCatalog.applyBulkSnapshot([{ e: ".py", p: "app.py" }], true);
const ignoredPaths = ignoredCatalog.snapshot().files.map((file) => file.path);
check(
  "a shallow-tree ignored file never enters a complete catalog",
  !ignoredPaths.includes("__pycache__/ignored.pyc"),
  ignoredPaths.join(","),
);
check(
  "an ignored file nested in an ignored dir stays out too",
  !ignoredPaths.includes("node_modules/dep/index.js"),
  ignoredPaths.join(","),
);
check("the non-ignored file is still searchable", ignoredPaths.includes("app.py"));

// Explicit navigation is the one provenance that may seat an ignored path:
// the user opened it on purpose, so it stays findable.
ignoredCatalog.observeNavigation("__pycache__/ignored.pyc", ".pyc");
check(
  "navigating to an ignored file keeps it findable",
  ignoredCatalog.snapshot().files.some((file) => file.path === "__pycache__/ignored.pyc"),
);

// A later passive sighting must not evict what navigation seated.
ignoredCatalog.applyEventChange([
  {
    entry: { gitignored: true, logical_ext: ".pyc", path: "__pycache__/ignored.pyc", type: "file" },
    op: "upsert",
  },
]);
check(
  "a passive re-sighting does not evict a navigated ignored file",
  ignoredCatalog.snapshot().files.some((file) => file.path === "__pycache__/ignored.pyc"),
);

// A refetch happens because deltas may have been dropped, so the payload has
// to be able to say what is GONE. The reviewer's repro: a file present in the
// first bulk, deleted while the stream was down, and absent from the
// authoritative refetch must stop being searchable (senior review R7).
const reconcileCatalog = sandbox.MetabrowserKnownFileCatalog.create();
reconcileCatalog.applyBulkSnapshot(
  [
    { e: ".txt", p: "deleted-during-gap.txt" },
    { e: ".txt", p: "still-present.txt" },
  ],
  true,
  true,
);
reconcileCatalog.applyBulkSnapshot([{ e: ".txt", p: "still-present.txt" }], true, true);
const reconciled = reconcileCatalog.snapshot().files.map((file) => file.path);
check(
  "an authoritative refetch retires a path it no longer lists",
  !reconciled.includes("deleted-during-gap.txt"),
  reconciled.join(","),
);
check("the surviving path stays", reconciled.includes("still-present.txt"));

// A mid-walk payload is a prefix, not a membership statement: merging is
// correct there, and retiring absent paths would empty the catalog.
const partialCatalog = sandbox.MetabrowserKnownFileCatalog.create();
partialCatalog.applyBulkSnapshot([{ e: ".txt", p: "first.txt" }], false, false);
partialCatalog.applyBulkSnapshot([{ e: ".txt", p: "second.txt" }], false, false);
const partialPaths = partialCatalog.snapshot().files.map((file) => file.path);
check(
  "a non-authoritative payload merges instead of retiring",
  partialPaths.includes("first.txt") && partialPaths.includes("second.txt"),
  partialPaths.join(","),
);

// Explicit navigation is the documented exception to feed membership: a
// gitignored file the user opened is absent from the feed by design.
const navExceptionCatalog = sandbox.MetabrowserKnownFileCatalog.create();
navExceptionCatalog.observeNavigation("__pycache__/opened.pyc", ".pyc");
navExceptionCatalog.applyBulkSnapshot([{ e: ".py", p: "app.py" }], true, true);
check(
  "authoritative reconciliation spares navigated paths",
  navExceptionCatalog.snapshot().files.some((file) => file.path === "__pycache__/opened.pyc"),
);

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("OK known file catalog\n");
