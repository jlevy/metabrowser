const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const sandbox = {};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/known-file-catalog.js"),
  "utf-8",
);
vm.runInContext(source, sandbox, { filename: "known-file-catalog.js" });

const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

function equal(label, actual, expected) {
  check(label, JSON.stringify(actual) === JSON.stringify(expected), `${JSON.stringify(actual)}`);
}

function applyBulkSnapshot(catalog, files, coverage, authoritative = false) {
  const application = catalog.beginBulkSnapshot(files, coverage, authoritative);
  let result;
  do {
    result = application.step(4_096);
  } while (!result.done);
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

const gitCatalog = sandbox.MetabrowserKnownFileCatalog.create();
gitCatalog.observeInitialTree([
  {
    name: "README.md",
    path: "g1-UkVBRE1FLm1k",
    type: "file",
    logical_ext: ".md",
  },
]);
const gitSnapshot = gitCatalog.snapshot();
equal("GitPath tree name is the catalog basename", gitSnapshot.files[0].basename, "README.md");
equal("GitPath catalog path stays the wire", gitSnapshot.files[0].path, "g1-UkVBRE1FLm1k");
equal("GitPath catalog keeps the display extension", gitSnapshot.files[0].logicalExtension, ".md");

const unsafePaths = [
  "",
  "/absolute.md",
  "../escape.md",
  "a/../escape.md",
  "a/./file.md",
  "a//double.md",
  "trailing/",
  "back\\slash.md",
  "nul\0byte.md",
  `high-${String.fromCharCode(0xd800)}.md`,
  `low-${String.fromCharCode(0xdc00)}.md`,
];
const unsafeCatalog = sandbox.MetabrowserKnownFileCatalog.create();
const unsafeEntries = unsafePaths.map((path) => ({ path, type: "file" }));
unsafeCatalog.observeInitialTree(unsafeEntries);
unsafeCatalog.observeLazyTree(unsafeEntries);
unsafeCatalog.observeRecent(unsafeEntries);
unsafeCatalog.observeEventSnapshot(unsafeEntries);
for (const path of unsafePaths) {
  unsafeCatalog.observeNavigation(path, ".md");
}
unsafeCatalog.applyCatalogChange({
  upserts: unsafePaths.map((path) => ({ e: ".md", p: path })),
});
unsafeCatalog.applyEventChange(unsafeEntries.map((entry) => ({ entry, op: "upsert" })));
applyBulkSnapshot(
  unsafeCatalog,
  unsafePaths.map((path) => ({ e: ".md", p: path })),
  "complete",
  true,
);
check(
  "every catalog ingestion seam rejects non-canonical file paths",
  unsafeCatalog.snapshot().observedCount === 0,
  unsafeCatalog
    .snapshot()
    .files.map((file) => file.path)
    .join(","),
);

unsafeCatalog.observeNavigation("safe/kept.md", ".md");
unsafeCatalog.applyCatalogChange({
  non_file_paths: unsafePaths,
  remove_files: unsafePaths,
  removes: unsafePaths,
});
unsafeCatalog.applyEventChange(unsafePaths.map((path) => ({ op: "remove", path })));
for (const path of unsafePaths) {
  unsafeCatalog.removePath(path);
}
equal(
  "every catalog removal seam ignores non-canonical paths",
  unsafeCatalog.snapshot().files.map((file) => file.path),
  ["safe/kept.md"],
);

const unicodeCatalog = sandbox.MetabrowserKnownFileCatalog.create();
applyBulkSnapshot(
  unicodeCatalog,
  [
    { e: ".md", p: "unicode/\ue000.md" },
    { e: ".md", p: "unicode/\u{1f600}.md" },
  ],
  "complete",
  true,
);
equal(
  "bulk fast path preserves valid astral paths and UTF-16 code-unit order",
  unicodeCatalog.snapshot().files.map((file) => file.path),
  ["unicode/\u{1f600}.md", "unicode/\ue000.md"],
);

const multiRunUnicodeCatalog = sandbox.MetabrowserKnownFileCatalog.create();
applyBulkSnapshot(
  multiRunUnicodeCatalog,
  [
    { e: ".md", p: "a/\ue000.md" },
    { e: ".md", p: "a/\u{1f600}.md" },
    { e: ".md", p: "b/\ue000.md" },
    { e: ".md", p: "b/\u{1f600}.md" },
    { e: ".md", p: "c/\ue000.md" },
    { e: ".md", p: "c/\u{1f600}.md" },
  ],
  "complete",
  true,
);
equal(
  "bulk merge combines every provider-ordered Unicode run",
  multiRunUnicodeCatalog.snapshot().files.map((file) => file.path),
  [
    "a/\u{1f600}.md",
    "a/\ue000.md",
    "b/\u{1f600}.md",
    "b/\ue000.md",
    "c/\u{1f600}.md",
    "c/\ue000.md",
  ],
);

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

const lexicalRemovalCatalog = sandbox.MetabrowserKnownFileCatalog.create();
lexicalRemovalCatalog.observeEventSnapshot([
  { name: "docs", path: "docs", type: "file" },
  { name: "nested.txt", path: "docs/nested.txt", type: "file" },
  { name: "docs-old", path: "docs-old", type: "file" },
  { name: "docs.md", path: "docs.md", type: "file" },
  { name: "docs0", path: "docs0", type: "file" },
]);
lexicalRemovalCatalog.applyEventChange([{ op: "remove", path: "docs" }]);
equal(
  "subtree removal keeps adjacent lexical siblings",
  lexicalRemovalCatalog.snapshot().files.map((file) => file.path),
  ["docs-old", "docs.md", "docs0"],
);

const mutationSliceCatalog = sandbox.MetabrowserKnownFileCatalog.create();
mutationSliceCatalog.observeNavigation("middle.txt", ".txt");
const mutationSliceApplication = mutationSliceCatalog.beginCatalogChange(
  {
    upserts: Array.from({ length: 257 }, (_, index) => ({
      e: ".txt",
      p: `ahead-${String(index).padStart(3, "0")}.txt`,
    })),
  },
  4_096,
);
check("257 point changes select staged application", mutationSliceApplication !== null);
const firstMutationSlice = mutationSliceApplication?.step(4_096);
check(
  "staged point mutations retain the measured 256-item task cap",
  firstMutationSlice?.done === false && firstMutationSlice.workItems === 257,
  JSON.stringify(firstMutationSlice),
);
const finalMutationSlice = mutationSliceApplication?.step(4_096);
check(
  "the staged point mutation remainder commits on the next task",
  finalMutationSlice?.done === true && finalMutationSlice.workItems === 1,
  JSON.stringify(finalMutationSlice),
);

const replacementSliceCatalog = sandbox.MetabrowserKnownFileCatalog.create();
applyBulkSnapshot(
  replacementSliceCatalog,
  Array.from({ length: 257 }, (_, index) => ({
    e: ".txt",
    p: `replace-${String(index).padStart(3, "0")}.txt`,
  })),
  "complete",
  true,
);
const replacementSliceApplication = replacementSliceCatalog.beginCatalogChange(
  {
    upserts: Array.from({ length: 257 }, (_, index) => ({
      e: ".md",
      p: `replace-${String(index).padStart(3, "0")}.txt`,
    })),
  },
  4_096,
);
const firstReplacementSlice = replacementSliceApplication?.step(4_096);
check(
  "ordered replacements reject the new-tail fast path",
  firstReplacementSlice?.done === false && firstReplacementSlice.workItems === 513,
  JSON.stringify(firstReplacementSlice),
);
const finalReplacementSlice = replacementSliceApplication?.step(4_096);
check(
  "the bounded replacement remainder commits on the next task",
  finalReplacementSlice?.done === true && finalReplacementSlice.workItems === 1,
  JSON.stringify(finalReplacementSlice),
);

catalog.clear();
snapshot = catalog.snapshot();
equal("resync clearing removes every observation source", snapshot.files, []);
equal("clearing resets source counts", snapshot.sourceSummary, {});
check("cleared catalog remains incomplete", snapshot.complete === false);

// ── Bulk feed and catalog.change ───────────────────────────────

const memoBefore = catalog.snapshot();
check("snapshot is memoized by revision", catalog.snapshot() === memoBefore);

const cowCatalog = sandbox.MetabrowserKnownFileCatalog.create();
applyBulkSnapshot(
  cowCatalog,
  [
    { e: ".txt", p: "middle/keep.txt" },
    { e: ".txt", p: "middle/remove.txt" },
    { e: ".txt", p: "middle/update.txt" },
  ],
  "complete",
  true,
);
const cowBefore = cowCatalog.snapshot();
const cowBeforeJson = JSON.stringify(cowBefore);
cowCatalog.applyCatalogChange({ upserts: [{ e: ".md", p: "ahead/insert.md" }] });
cowCatalog.applyCatalogChange({ upserts: [{ e: ".md", p: "middle/update.txt" }] });
cowCatalog.applyCatalogChange({ remove_files: ["middle/remove.txt"] });
check(
  "direct copy-on-write mutations preserve an older immutable snapshot",
  JSON.stringify(cowBefore) === cowBeforeJson,
  JSON.stringify(cowBefore),
);
equal(
  "the new snapshot reflects direct insertion update and removal",
  cowCatalog.snapshot().files.map((file) => [file.path, file.logicalExtension]),
  [
    ["ahead/insert.md", ".md"],
    ["middle/keep.txt", ".txt"],
    ["middle/update.txt", ".md"],
  ],
);

catalog.observeNavigation("visited/ignored.log", ".log");
applyBulkSnapshot(
  catalog,
  [
    { p: "README.md", e: ".md" },
    { p: "docs/deep/nested/leaf.txt", e: ".txt" },
  ],
  "complete",
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
applyBulkSnapshot(incompleteCatalog, [{ p: "a.txt", e: ".txt" }], "partial");
check("incomplete bulk apply stays incomplete", incompleteCatalog.snapshot().complete === false);
incompleteCatalog.markComplete();
check(
  "markComplete flips completeness without data",
  incompleteCatalog.snapshot().complete === true,
);
incompleteCatalog.markIncomplete();
check(
  "markIncomplete resets coverage without discarding membership",
  incompleteCatalog.snapshot().complete === false &&
    incompleteCatalog.snapshot().files.some((file) => file.path === "a.txt"),
);
incompleteCatalog.clear();
check("clear resets completeness", incompleteCatalog.snapshot().complete === false);

// A walk that stops at the file cap is terminal without covering the root.
// The snapshot states that explicitly, so a consumer can stop waiting for a
// final revision without treating a lookup miss as proof of absence.
check("a new catalog is not truncated", catalog.snapshot().truncated === false);
const truncatedCatalog = sandbox.MetabrowserKnownFileCatalog.create();
applyBulkSnapshot(truncatedCatalog, [{ p: "capped.txt", e: ".txt" }], "truncated", true);
equal(
  "a truncated bulk is terminal but not complete",
  [truncatedCatalog.snapshot().complete, truncatedCatalog.snapshot().truncated],
  [false, true],
);
const truncatedRevision = truncatedCatalog.snapshot().revision;
truncatedCatalog.markTruncated();
check(
  "a repeated truncated terminal signal publishes no revision",
  truncatedCatalog.snapshot().revision === truncatedRevision,
);
truncatedCatalog.markIncomplete();
equal(
  "markIncomplete clears truncated coverage",
  [truncatedCatalog.snapshot().complete, truncatedCatalog.snapshot().truncated],
  [false, false],
);
truncatedCatalog.markTruncated();
check("markTruncated marks a partial catalog", truncatedCatalog.snapshot().truncated === true);
truncatedCatalog.markComplete();
equal(
  "complete coverage replaces truncated coverage",
  [truncatedCatalog.snapshot().complete, truncatedCatalog.snapshot().truncated],
  [true, false],
);
truncatedCatalog.markTruncated();
applyBulkSnapshot(truncatedCatalog, [], "truncated", false);
equal(
  "a truncated signal or payload cannot downgrade complete coverage",
  [truncatedCatalog.snapshot().complete, truncatedCatalog.snapshot().truncated],
  [true, false],
);
truncatedCatalog.clear();
check("clear resets truncated coverage", truncatedCatalog.snapshot().truncated === false);
const stagedTruncation = sandbox.MetabrowserKnownFileCatalog.create();
const stagedTruncationApplication = stagedTruncation.beginBulkSnapshot(
  [{ p: "staged.txt", e: ".txt" }],
  "partial",
  false,
);
stagedTruncation.markTruncated();
check(
  "a truncated signal during a staged bulk stays invisible until commit",
  stagedTruncation.snapshot().truncated === false,
);
let stagedTruncationStep;
do {
  stagedTruncationStep = stagedTruncationApplication.step(4_096);
} while (!stagedTruncationStep.done);
check(
  "a truncated signal during a staged bulk commits with it",
  stagedTruncation.snapshot().truncated === true &&
    stagedTruncation.snapshot().files.some((file) => file.path === "staged.txt"),
);
let invalidCoverageError = null;
try {
  stagedTruncation.beginBulkSnapshot([], true, false);
} catch (error) {
  invalidCoverageError = error;
}
check(
  "a bulk snapshot requires an explicit coverage state",
  invalidCoverageError?.name === "TypeError",
);

// A bulk response built mid-walk can resolve after the one-shot
// walk-completion event already marked the catalog complete; the
// stale flag must not downgrade it (Bugbot R6).
const racedCatalog = sandbox.MetabrowserKnownFileCatalog.create();
racedCatalog.markComplete();
applyBulkSnapshot(racedCatalog, [{ p: "late.txt", e: ".txt" }], "partial");
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
applyBulkSnapshot(ignoredCatalog, [{ e: ".py", p: "app.py" }], "complete");
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
applyBulkSnapshot(
  reconcileCatalog,
  [
    { e: ".txt", p: "deleted-during-gap.txt" },
    { e: ".txt", p: "still-present.txt" },
  ],
  "complete",
  true,
);
applyBulkSnapshot(reconcileCatalog, [{ e: ".txt", p: "still-present.txt" }], "complete", true);
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
applyBulkSnapshot(partialCatalog, [{ e: ".txt", p: "first.txt" }], "partial", false);
applyBulkSnapshot(partialCatalog, [{ e: ".txt", p: "second.txt" }], "partial", false);
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
applyBulkSnapshot(navExceptionCatalog, [{ e: ".py", p: "app.py" }], "complete", true);
check(
  "authoritative reconciliation spares navigated paths",
  navExceptionCatalog.snapshot().files.some((file) => file.path === "__pycache__/opened.pyc"),
);

const trackedNavigationCatalog = sandbox.MetabrowserKnownFileCatalog.create();
trackedNavigationCatalog.observeNavigation("tracked-after-navigation.txt", ".txt");
applyBulkSnapshot(
  trackedNavigationCatalog,
  [{ e: ".txt", p: "tracked-after-navigation.txt" }],
  "complete",
  true,
);
equal(
  "authoritative membership takes ownership of a previously navigated path",
  trackedNavigationCatalog.snapshot().sourceSummary,
  { "catalog-feed": 1 },
);
applyBulkSnapshot(trackedNavigationCatalog, [], "complete", true);
check(
  "a later authoritative omission retires that feed-owned path",
  trackedNavigationCatalog.snapshot().observedCount === 0,
);

// A large bulk is a transaction even though its construction is sliced. A
// snapshot built for the first time mid-slice sees the live catalog, never the
// stage; later navigation/tree mutations remain live and replay after the
// authoritative membership before the one constant-time publication.
const atomicCatalog = sandbox.MetabrowserKnownFileCatalog.create();
atomicCatalog.observeInitialTree([{ path: "stale.txt", type: "file" }]);
const atomicApplication = atomicCatalog.beginBulkSnapshot(
  [
    { e: ".txt", p: "bulk/one.txt" },
    { e: ".txt", p: "bulk/two.txt" },
    { e: ".txt", p: "retired/child.txt" },
  ],
  "complete",
  true,
);
const firstAtomicStep = atomicApplication.step(1);
check("bounded bulk pauses before completion", firstAtomicStep.done === false);
equal(
  "a first snapshot mid-slice cannot observe staged files",
  atomicCatalog.snapshot().files.map((file) => file.path),
  ["stale.txt"],
);
atomicCatalog.observeNavigation("visited/during-apply.log", ".log");
atomicCatalog.observeLazyTree([{ path: "live/during-apply.md", type: "file" }]);
atomicCatalog.removePath("retired");
atomicCatalog.applyCatalogChange({ remove_files: ["bulk/two.txt"], upserts: [] });
equal(
  "concurrent mutations stay invisible with the staged bulk",
  atomicCatalog.snapshot().files.map((file) => file.path),
  ["stale.txt"],
);
let atomicStep = firstAtomicStep;
while (!atomicStep.done) {
  atomicStep = atomicApplication.step(1);
}
equal(
  "final swap applies bulk then concurrent mutations in order",
  atomicCatalog.snapshot().files.map((file) => file.path),
  ["bulk/one.txt", "live/during-apply.md", "visited/during-apply.log"],
);

// A navigation sighting during an authoritative stage must not overwrite the
// feed's ownership of the same path. Otherwise a later authoritative omission
// would preserve a file that the provider says no longer exists.
const stagedOwnershipCatalog = sandbox.MetabrowserKnownFileCatalog.create();
const stagedOwnershipApplication = stagedOwnershipCatalog.beginBulkSnapshot(
  [{ e: ".txt", p: "tracked-during-stage.txt" }],
  "complete",
  true,
);
stagedOwnershipApplication.step(1);
stagedOwnershipCatalog.observeNavigation("tracked-during-stage.txt", ".txt");
while (!stagedOwnershipApplication.step(1).done) {
  // Replay the concurrent navigation at the smallest production work unit.
}
equal(
  "concurrent navigation does not downgrade feed ownership",
  stagedOwnershipCatalog.snapshot().sourceSummary,
  { "catalog-feed": 1 },
);
applyBulkSnapshot(stagedOwnershipCatalog, [], "complete", true);
check(
  "a later omission retires the concurrently navigated feed path",
  stagedOwnershipCatalog.snapshot().observedCount === 0,
);

const canceledCatalog = sandbox.MetabrowserKnownFileCatalog.create();
canceledCatalog.observeInitialTree([{ path: "base.txt", type: "file" }]);
const canceledApplication = canceledCatalog.beginBulkSnapshot(
  [
    { e: ".txt", p: "partial/one.txt" },
    { e: ".txt", p: "partial/two.txt" },
  ],
  "complete",
  true,
);
canceledApplication.step(1);
canceledCatalog.observeNavigation("visited-before-cancel.txt", ".txt");
canceledApplication.cancel();
equal(
  "cancel discards the stage but keeps concurrent live mutations",
  canceledCatalog.snapshot().files.map((file) => file.path),
  ["base.txt", "visited-before-cancel.txt"],
);

const supersededCatalog = sandbox.MetabrowserKnownFileCatalog.create();
const supersededApplication = supersededCatalog.beginBulkSnapshot(
  [
    { e: ".txt", p: "superseded/one.txt" },
    { e: ".txt", p: "superseded/two.txt" },
  ],
  "complete",
  true,
);
supersededApplication.step(1);
const winningApplication = supersededCatalog.beginBulkSnapshot(
  [{ e: ".txt", p: "winner.txt" }],
  "complete",
  true,
);
const supersededStep = supersededApplication.step(1);
check(
  "a superseded stage reports cancellation and becomes inert",
  supersededStep.done === true && supersededStep.cancelled === true,
);
while (!winningApplication.step(1).done) {
  // Exercise the smallest valid budget so every phase boundary is covered.
}
equal(
  "a replacement bulk publishes no superseded paths",
  supersededCatalog.snapshot().files.map((file) => file.path),
  ["winner.txt"],
);

// Removals scan for directory-prefix descendants, so one pass per removed
// path made a burst O(n*m) against a now-complete catalog. Batching a run of
// removes into a single pass must not change what the ops mean: order is
// preserved, so a remove followed by an upsert beneath it keeps the child
// (mb-r8yg).
const batchCatalog = sandbox.MetabrowserKnownFileCatalog.create();
applyBulkSnapshot(
  batchCatalog,
  [
    { e: ".txt", p: "a/one.txt" },
    { e: ".txt", p: "a/two.txt" },
    { e: ".txt", p: "b/three.txt" },
    { e: ".txt", p: "keep/four.txt" },
  ],
  "complete",
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
applyBulkSnapshot(orderedCatalog, [{ e: ".txt", p: "dir/before.txt" }], "complete");
orderedCatalog.applyEventChange([
  { op: "remove", path: "dir" },
  { entry: { logical_ext: ".txt", path: "dir/after.txt", type: "file" }, op: "upsert" },
]);
equal(
  "an upsert after a remove in the same batch survives it",
  orderedCatalog.snapshot().files.map((file) => file.path),
  ["dir/after.txt"],
);

// The same order survives separate buffered envelopes in one stage. The
// point-tail optimization must stop at the removal boundary rather than
// appending first and sweeping the later upsert with its predecessor.
const stagedOrderCatalog = sandbox.MetabrowserKnownFileCatalog.create();
applyBulkSnapshot(stagedOrderCatalog, [{ e: ".txt", p: "dir/before.txt" }], "complete", true);
let stagedOrderNotifications = 0;
stagedOrderCatalog.subscribe(() => {
  stagedOrderNotifications += 1;
});
const stagedOrderBefore = stagedOrderCatalog.snapshot();
const stagedOrderApplication = stagedOrderCatalog.beginBulkSnapshot([], "partial", false);
stagedOrderApplication.enqueueEventChange([{ op: "remove", path: "dir" }]);
stagedOrderApplication.enqueueEventChange([
  { entry: { logical_ext: ".txt", path: "dir/after.txt", type: "file" }, op: "upsert" },
]);
while (!stagedOrderApplication.step(1).done) {
  check(
    "separate removal and upsert envelopes remain invisible mid-stage",
    stagedOrderCatalog.snapshot() === stagedOrderBefore && stagedOrderNotifications === 0,
  );
}
equal(
  "remove then upsert order survives separate staged envelopes",
  stagedOrderCatalog.snapshot().files.map((file) => file.path),
  ["dir/after.txt"],
);

// The same batching applies to the catalog.change wire path, where removes
// arrive as their own array.
const changeCatalog = sandbox.MetabrowserKnownFileCatalog.create();
applyBulkSnapshot(
  changeCatalog,
  [
    { e: ".txt", p: "x/one.txt" },
    { e: ".txt", p: "y/two.txt" },
    { e: ".txt", p: "z/three.txt" },
  ],
  "complete",
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
applyBulkSnapshot(subCatalog, [{ e: ".txt", p: "one.txt" }], "complete");
check("a bulk apply queues subscriber notification", seen.length === 0, String(seen.length));
subCatalog.applyCatalogChange({ removes: [], upserts: [{ e: ".txt", p: "two.txt" }] });
check(
  "a direct change coalesces and delivers the queued bulk notification",
  seen.length === 1,
  String(seen.length),
);
subCatalog.observeNavigation("three.txt", ".txt");
check("navigation notifies subscribers", seen.length === 2, String(seen.length));

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

// A passive ignored-file sighting can only evict that exact file leaf. It must
// not enter the directory-removal path, whose prefix semantics require a full
// catalog scan. Subtree prefetch can deliver several such sightings together,
// so one accidental scan per ignored leaf turns a background warm-up into a
// main-thread freeze on a complete catalog.
let catalogKeySweeps = 0;
class KeySweepCountingMap extends Map {
  keys() {
    catalogKeySweeps += 1;
    return super.keys();
  }
}
const sweepSandbox = { Map: KeySweepCountingMap };
sweepSandbox.window = sweepSandbox;
sweepSandbox.globalThis = sweepSandbox;
vm.createContext(sweepSandbox);
vm.runInContext(source, sweepSandbox, { filename: "known-file-catalog.js" });
const exactEvictionCatalog = sweepSandbox.MetabrowserKnownFileCatalog.create();
applyBulkSnapshot(
  exactEvictionCatalog,
  [
    { e: ".txt", p: "keep.txt" },
    { e: ".pyc", p: "cache/stale.pyc" },
  ],
  "complete",
);
catalogKeySweeps = 0;
exactEvictionCatalog.observeLazyTree([
  { gitignored: true, logical_ext: ".pyc", path: "cache/stale.pyc", type: "file" },
  { gitignored: true, logical_ext: ".pyc", path: "cache/absent.pyc", type: "file" },
]);
equal(
  "passive ignored sightings evict only their exact file leaves",
  exactEvictionCatalog.snapshot().files.map((file) => file.path),
  ["keep.txt"],
);
check(
  "passive ignored sightings do not scan catalog keys",
  catalogKeySweeps === 0,
  String(catalogKeySweeps),
);

exactEvictionCatalog.applyCatalogChange({
  remove_files: [],
  removes: [],
  upserts: [{ e: ".pyc", p: "cache/live.pyc" }],
});
catalogKeySweeps = 0;
exactEvictionCatalog.applyCatalogChange({
  remove_files: ["cache/live.pyc", "cache/missing.pyc"],
  removes: [],
  upserts: [],
});
check(
  "wire exact-file removals evict the named leaf",
  !exactEvictionCatalog.snapshot().files.some((file) => file.path === "cache/live.pyc"),
);
check(
  "wire exact-file removals do not scan catalog keys",
  catalogKeySweeps === 0,
  String(catalogKeySweeps),
);
exactEvictionCatalog.applyCatalogChange({
  remove_files: [],
  removes: [],
  upserts: [{ e: ".txt", p: "cache/child.txt" }],
});
exactEvictionCatalog.observeNavigation("cache/replaced-link", ".md");
catalogKeySweeps = 0;
exactEvictionCatalog.applyCatalogChange({
  non_file_paths: ["cache", "cache/replaced-link"],
  remove_files: [],
  removes: [],
  upserts: [],
});
equal(
  "non-file invalidations retire navigated files but preserve directory descendants",
  exactEvictionCatalog.snapshot().files.map((file) => file.path),
  ["cache/child.txt", "keep.txt"],
);
check(
  "non-file exact invalidations do not scan catalog keys",
  catalogKeySweeps === 0,
  String(catalogKeySweeps),
);

exactEvictionCatalog.observeNavigation("cache/opened.pyc", ".pyc");
exactEvictionCatalog.applyCatalogChange({
  remove_files: ["cache/opened.pyc"],
  removes: [],
  upserts: [],
});
check(
  "wire exact-file removals preserve explicit navigation",
  exactEvictionCatalog.snapshot().files.some((file) => file.path === "cache/opened.pyc"),
);

// Subtree removal against a reference model. Lexical order interleaves a
// directory's exact entry and its descendants with siblings whose next code
// unit sorts below `/` (`src/parser.rs` sits between `src/parser` and
// `src/parser/a.rs`), so every removal path must be checked against the plain
// definition: drop each path equal to, or under, any removed path. The direct,
// staged steady-state, and bulk-replay paths each maintain their own ranges.
{
  let seed = 0x5eed1234;
  function random() {
    seed = (seed + 0x6d2b79f5) >>> 0;
    let value = seed;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4_294_967_296;
  }
  function pick(values) {
    return values[Math.floor(random() * values.length)];
  }
  // Names whose next code unit falls on both sides of `/` (0x2f).
  const names = ["a", "a b", "a!", "a+", "a-b", "a.rs", "a0", "b"];

  function randomCatalogPaths() {
    const paths = new Set();
    const count = 1 + Math.floor(random() * 24);
    while (paths.size < count) {
      const depth = 1 + Math.floor(random() * 3);
      paths.add(Array.from({ length: depth }, () => pick(names)).join("/"));
    }
    // A path cannot be both a file and a directory in one catalog.
    return [...paths].filter(
      (candidate) => ![...paths].some((other) => other.startsWith(`${candidate}/`)),
    );
  }

  function randomRemovals(paths) {
    const removals = new Set();
    const count = 1 + Math.floor(random() * 4);
    while (removals.size < count) {
      const segments = pick(paths).split("/");
      const prefixLength = 1 + Math.floor(random() * segments.length);
      removals.add(
        random() < 0.15 ? `${pick(names)}/missing` : segments.slice(0, prefixLength).join("/"),
      );
    }
    return [...removals];
  }

  function expectedAfterRemoval(paths, removals) {
    return paths
      .filter(
        (candidate) =>
          !removals.some((removed) => candidate === removed || candidate.startsWith(`${removed}/`)),
      )
      .sort((left, right) => (left < right ? -1 : left > right ? 1 : 0));
  }

  function seeded(paths) {
    const seededCatalog = sandbox.MetabrowserKnownFileCatalog.create();
    applyBulkSnapshot(
      seededCatalog,
      paths.map((candidate) => ({ e: ".txt", p: candidate })),
      "complete",
      true,
    );
    return seededCatalog;
  }

  function pathsOf(target) {
    return target.snapshot().files.map((file) => file.path);
  }

  const mismatches = [];
  for (let trial = 0; trial < 400 && mismatches.length < 3; trial += 1) {
    const paths = randomCatalogPaths();
    const removals = randomRemovals(paths);
    const expected = expectedAfterRemoval(paths, removals);

    const direct = seeded(paths);
    direct.applyCatalogChange({ removes: removals, upserts: [] });

    const staged = seeded(paths);
    const stagedApplication = staged.beginCatalogChange({ removes: removals, upserts: [] }, 1);
    if (stagedApplication) {
      let result;
      do {
        result = stagedApplication.step(1 + Math.floor(random() * 5));
      } while (!result.done);
    } else if (expected.length !== paths.length) {
      mismatches.push({ path: "staged", removals, reason: "a matching removal was not staged" });
    }

    const replay = sandbox.MetabrowserKnownFileCatalog.create();
    const replayApplication = replay.beginBulkSnapshot(
      paths.map((candidate) => ({ e: ".txt", p: candidate })),
      "complete",
      true,
    );
    replayApplication.enqueueCatalogChange({ removes: removals, upserts: [] });
    let replayResult;
    do {
      replayResult = replayApplication.step(1 + Math.floor(random() * 7));
    } while (!replayResult.done);

    const events = seeded(paths);
    events.applyEventChange(removals.map((removed) => ({ op: "remove", path: removed })));

    for (const [name, target] of [
      ["direct", direct],
      ["staged", staged],
      ["bulk replay", replay],
      ["event change", events],
    ]) {
      const actual = pathsOf(target);
      if (JSON.stringify(actual) !== JSON.stringify(expected)) {
        mismatches.push({ actual, expected, path: name, paths, removals });
      }
    }
  }
  check(
    "subtree removal matches the reference model on every path",
    mismatches.length === 0,
    JSON.stringify(mismatches[0]),
  );

  const siblingCatalog = seeded([
    "src/parser.rs",
    "src/parser/a.rs",
    "src/parser/b.rs",
    "zeta.txt",
  ]);
  siblingCatalog.applyCatalogChange({ removes: ["src/parser", "src/parser.rs"], upserts: [] });
  equal(
    "removing a directory and its same-prefix sibling keeps unrelated files",
    pathsOf(siblingCatalog),
    ["zeta.txt"],
  );
}

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("OK known file catalog\n");
