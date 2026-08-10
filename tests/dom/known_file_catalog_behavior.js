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

// Removals scan for directory-prefix descendants, so one pass per removed
// path made a burst O(n*m) against a now-complete catalog. Batching a run of
// removes into a single pass must not change what the ops mean: order is
// preserved, so a remove followed by an upsert beneath it keeps the child
// (mb-r8yg).
const batchCatalog = sandbox.MetabrowserKnownFileCatalog.create();
batchCatalog.applyBulkSnapshot(
  [
    { e: ".txt", p: "a/one.txt" },
    { e: ".txt", p: "a/two.txt" },
    { e: ".txt", p: "b/three.txt" },
    { e: ".txt", p: "keep/four.txt" },
  ],
  true,
);
batchCatalog.applyEventChange([
  { op: "remove", path: "a" },
  { op: "remove", path: "b" },
]);
equal(
  "a batched run of removes deletes every subtree",
  batchCatalog.snapshot().files.map((file) => file.path),
  ["keep/four.txt"],
);

// Ordering within a batch survives batching: the child added after its
// parent was removed stays, and the child added before is still swept.
const orderedCatalog = sandbox.MetabrowserKnownFileCatalog.create();
orderedCatalog.applyBulkSnapshot([{ e: ".txt", p: "dir/before.txt" }], true);
orderedCatalog.applyEventChange([
  { op: "remove", path: "dir" },
  { entry: { logical_ext: ".txt", path: "dir/after.txt", type: "file" }, op: "upsert" },
]);
equal(
  "an upsert after a remove in the same batch survives it",
  orderedCatalog.snapshot().files.map((file) => file.path),
  ["dir/after.txt"],
);

// The same batching applies to the catalog.change wire path, where removes
// arrive as their own array.
const changeCatalog = sandbox.MetabrowserKnownFileCatalog.create();
changeCatalog.applyBulkSnapshot(
  [
    { e: ".txt", p: "x/one.txt" },
    { e: ".txt", p: "y/two.txt" },
    { e: ".txt", p: "z/three.txt" },
  ],
  true,
);
changeCatalog.applyCatalogChange({ removes: ["x", "y"], upserts: [] });
equal(
  "catalog.change removes batch too",
  changeCatalog.snapshot().files.map((file) => file.path),
  ["z/three.txt"],
);

// Derived views need to know when coverage moves; every mutation routes
// through one bump so a consumer subscribes once instead of hooking each
// ingestion seam (mb-lzvb).
const subCatalog = sandbox.MetabrowserKnownFileCatalog.create();
const seen = [];
/** @type {unknown[]} */
let lastArgs = null;
const unsubscribe = subCatalog.subscribe((...args) => {
  lastArgs = args;
  seen.push(subCatalog.snapshot().revision);
});
subCatalog.applyBulkSnapshot([{ e: ".txt", p: "one.txt" }], true);
check("a bulk apply notifies subscribers", seen.length === 1, String(seen.length));
subCatalog.applyCatalogChange({ removes: [], upserts: [{ e: ".txt", p: "two.txt" }] });
check("a catalog.change notifies subscribers", seen.length === 2, String(seen.length));
subCatalog.observeNavigation("three.txt", ".txt");
check("navigation notifies subscribers", seen.length === 3, String(seen.length));

// A no-op ingestion must not wake derived views.
const quiet = seen.length;
subCatalog.applyCatalogChange({ removes: [], upserts: [{ e: ".txt", p: "two.txt" }] });
check("an unchanged apply does not notify", seen.length === quiet, String(seen.length));

// Notification is invalidation only. Handing listeners a snapshot would sort
// the whole catalog on every mutation, and the palette's listener lives for
// the application lifetime, so that cost would land even with the palette
// closed (senior review R1).
check("notification carries no projection", lastArgs !== null && lastArgs.length === 0);

// A listener that asks for state gets the state that caused the notification.
let observedCount = -1;
const unsubscribeCount = subCatalog.subscribe(() => {
  observedCount = subCatalog.snapshot().observedCount;
});
subCatalog.applyCatalogChange({ removes: [], upserts: [{ e: ".txt", p: "four.txt" }] });
check(
  "a listener reading snapshot() sees the change",
  observedCount === subCatalog.snapshot().observedCount,
  `${observedCount} vs ${subCatalog.snapshot().observedCount}`,
);
unsubscribeCount();

unsubscribe();
const afterUnsubscribe = seen.length;
subCatalog.applyCatalogChange({ removes: [], upserts: [{ e: ".txt", p: "five.txt" }] });
check("unsubscribe stops delivery", seen.length === afterUnsubscribe);

// A subscriber that writes back must not recurse forever.
const reentrant = sandbox.MetabrowserKnownFileCatalog.create();
let reentrantCalls = 0;
reentrant.subscribe(() => {
  reentrantCalls += 1;
  if (reentrantCalls < 5) {
    reentrant.observeNavigation(`loop-${reentrantCalls}.txt`, ".txt");
  }
});
reentrant.observeNavigation("start.txt", ".txt");
check("re-entrant notification is suppressed", reentrantCalls === 1, String(reentrantCalls));
check(
  "the nested write still landed",
  reentrant.snapshot().files.some((file) => file.path === "loop-1.txt"),
);

// A listener running after one that wrote back must not see pre-write state.
// The eager-snapshot design could not honor this: the payload was computed
// once, before any listener ran (senior review R2).
const reentrantOrder = sandbox.MetabrowserKnownFileCatalog.create();
let writerRan = false;
let secondSawCount = -1;
reentrantOrder.subscribe(() => {
  if (writerRan) {
    return;
  }
  writerRan = true;
  reentrantOrder.observeNavigation("written-by-listener.txt", ".txt");
});
reentrantOrder.subscribe(() => {
  secondSawCount = reentrantOrder.snapshot().observedCount;
});
reentrantOrder.observeNavigation("first.txt", ".txt");
check(
  "a later listener sees a re-entrant write, not stale state",
  secondSawCount === reentrantOrder.snapshot().observedCount && secondSawCount === 2,
  `${secondSawCount} vs ${reentrantOrder.snapshot().observedCount}`,
);

// A throwing subscriber must not break the ingestion path or its siblings.
const resilient = sandbox.MetabrowserKnownFileCatalog.create();
let goodCalls = 0;
resilient.subscribe(() => {
  throw new Error("subscriber blew up");
});
resilient.subscribe(() => {
  goodCalls += 1;
});
resilient.observeNavigation("safe.txt", ".txt");
check("a throwing subscriber does not stop the others", goodCalls === 1);
check(
  "a throwing subscriber does not lose the write",
  resilient.snapshot().files.some((file) => file.path === "safe.txt"),
);

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("OK known file catalog\n");
