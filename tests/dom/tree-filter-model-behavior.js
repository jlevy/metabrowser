// Behavioural checks for static/tree-filter-model.js: what a filter selection
// asks each navigation route for.
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
assertEqual(
  "unordered type selections have one canonical request identity",
  model.requestParams(snapshot({ types: ["README", ".txt", ".md"] }), SIZE_FLOORS),
  ["types=.md%2C.txt%2CREADME"],
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
assertEqual(
  "a recent request carries every server-owned filter dimension",
  model.recentUrl(
    "1h",
    5000,
    snapshot({ recency: "1h", types: [".md", "README"], size: "1m", showIgnored: false }),
    SIZE_FLOORS,
  ),
  "/api/recent?window=1h&limit=5000&types=.md%2CREADME&min_size=1048576&include_ignored=0",
);
assertEqual(
  "the recent request identity includes every server-owned dimension",
  model.recentRequestKey(
    "1h",
    5000,
    snapshot({ recency: "1h", types: [".md"], size: "all", showIgnored: true }),
    SIZE_FLOORS,
  ) ===
    model.recentRequestKey(
      "1h",
      5000,
      snapshot({ recency: "1h", types: [".txt"], size: "all", showIgnored: true }),
      SIZE_FLOORS,
    ),
  false,
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

// ── Recent selection and request continuity ─────────────────────────────

const passAll = { rowMatches: () => true };
const recentOptions = {
  clusterPct: 0.05,
  filterState: passAll,
  ignoredDirectoryPaths: new Set(),
  limit: 10,
  nowSec: 2_000_000_000,
  state: snapshot({}),
};

function catalogEffect(change, entries = new Map()) {
  return model.applyRecentCatalogChange(entries, change, {
    filterState: passAll,
    nowSec: recentOptions.nowSec,
    state: recentOptions.state,
    visibleDepth: 2,
  });
}

assertEqual(
  "equal-mtime paths use canonical UTF-8 order instead of locale collation",
  model
    .recentView(
      [
        { path: "a.md", type: "file", mtime: 100 },
        { path: "Z.md", type: "file", mtime: 100 },
      ],
      recentOptions,
    )
    .entries.map((entry) => entry.path),
  ["Z.md", "a.md"],
);

assertEqual(
  "tracked files rank before newer ignored files when the page is capped",
  model
    .recentView(
      [
        { path: "ignored/newer.md", type: "file", mtime: 200, gitignored: true },
        { path: "tracked/older.md", type: "file", mtime: 100 },
      ],
      { ...recentOptions, limit: 1 },
    )
    .entries.map((entry) => entry.path),
  ["tracked/older.md"],
);

assertEqual(
  "path segments named like object internals remain ordinary directories",
  model
    .recentView(
      [
        { path: "__proto__/x.md", type: "file", mtime: 100 },
        { path: "constructor/y.md", type: "file", mtime: 100 },
      ],
      recentOptions,
    )
    .tree.map((entry) => entry.path),
  ["__proto__", "constructor"],
);

assertEqual(
  "the view reports matching leaves before its render cap",
  model.recentView(
    [
      { path: "one.md", type: "file", mtime: 200 },
      { path: "two.md", type: "file", mtime: 100 },
    ],
    { ...recentOptions, limit: 1 },
  ).matchingCount,
  2,
);

assertEqual(
  "an exact untruncated Recent tally names the visible count",
  model.recentFilteredTallyText(1, {
    totalMatching: 1,
    totalMatchingExact: true,
    truncated: false,
  }),
  "Filtered to 1 file.",
);
assertEqual(
  "a deep invalidation marks an originally untruncated Recent tally as a lower bound",
  model.recentFilteredTallyText(1, {
    totalMatching: 1,
    totalMatchingExact: false,
    truncated: false,
  }),
  "Filtered to 1+ files.",
);
assertEqual(
  "an empty non-exact Recent tally still discloses uncertainty",
  model.recentFilteredTallyText(0, {
    totalMatching: 0,
    totalMatchingExact: false,
    truncated: false,
  }),
  "Filtered to 0+ files.",
);
assertEqual(
  "a truncated exact Recent tally names its provider total",
  model.recentFilteredTallyText(5, {
    totalMatching: 12,
    totalMatchingExact: true,
    truncated: true,
  }),
  "Filtered to 5 files of 12 matching.",
);
assertEqual(
  "a truncated non-exact Recent tally marks the provider total as a lower bound",
  model.recentFilteredTallyText(5, {
    totalMatching: 12,
    totalMatchingExact: false,
    truncated: true,
  }),
  "Filtered to 5 files of 12+ matching.",
);

assertEqual(
  "a shallow catalog upsert is covered by root-depth-2 fs.change",
  catalogEffect({
    upserts: [{ p: "docs/live.md", e: ".md" }],
    removes: [],
    remove_files: [],
  }).needsAuthoritativeRepair,
  false,
);
assertEqual(
  "a deep catalog upsert invalidates the whole-root Recent snapshot",
  catalogEffect({
    upserts: [{ p: "runs/day/job/live.md", e: ".md" }],
    removes: [],
    remove_files: [],
  }).needsAuthoritativeRepair,
  true,
);
assertEqual(
  "a shallow subtree removal is ambiguous and invalidates Recent",
  catalogEffect({ upserts: [], removes: ["runs"], remove_files: [] }).needsAuthoritativeRepair,
  true,
);
assertEqual(
  "a deep ignored-file transition invalidates Recent",
  catalogEffect({ upserts: [], removes: [], remove_files: ["runs/day/job/ignored.md"] })
    .needsAuthoritativeRepair,
  true,
);
assertEqual(
  "a deep file-to-directory replacement invalidates Recent",
  catalogEffect({
    upserts: [],
    removes: [],
    remove_files: [],
    non_file_paths: ["runs/day/job/replaced-dir"],
  }).needsAuthoritativeRepair,
  true,
);
assertEqual(
  "a deep file-to-symlink replacement invalidates Recent",
  catalogEffect({
    upserts: [],
    removes: [],
    remove_files: [],
    non_file_paths: ["runs/day/job/replaced-link"],
  }).needsAuthoritativeRepair,
  true,
);
assertEqual(
  "a shallow file-to-directory replacement stays on the fs.change fast path",
  catalogEffect({ upserts: [], removes: [], remove_files: [], non_file_paths: ["docs"] })
    .needsAuthoritativeRepair,
  false,
);

const deepCatalogEntries = new Map(
  [
    "runs/day/job/replaced-dir",
    "runs/day/job/replaced-dir/child.md",
    "runs/day/job/replaced-link",
    "keep.md",
  ].map((path) => [path, { path, type: "file", mtime: recentOptions.nowSec - 1 }]),
);
const deepCatalogEffect = catalogEffect(
  {
    upserts: [],
    removes: [],
    remove_files: [],
    non_file_paths: ["runs/day/job/replaced-dir", "runs/day/job/replaced-link"],
  },
  deepCatalogEntries,
);
assertEqual(
  "deep exact invalidations prune only named Recent rows",
  {
    effect: deepCatalogEffect,
    paths: Array.from(deepCatalogEntries.keys()),
  },
  {
    effect: {
      changed: true,
      needsAuthoritativeRepair: true,
      removedEntries: 2,
      retainedLowerBound: 2,
    },
    paths: ["runs/day/job/replaced-dir/child.md", "keep.md"],
  },
);

function deepCatalogBatch(change) {
  const entries = new Map(
    ["runs/day/job/affected.md", "keep.md"].map((path) => [
      path,
      { path, type: "file", mtime: recentOptions.nowSec - 1 },
    ]),
  );
  return {
    effect: catalogEffect(change, entries),
    paths: Array.from(entries.keys()),
  };
}

for (const [label, change] of [
  [
    "deep catalog upsert",
    { upserts: [{ p: "runs/day/job/affected.md", e: ".md" }], removes: [], remove_files: [] },
  ],
  [
    "deep catalog removal",
    { upserts: [], removes: ["runs/day/job/affected.md"], remove_files: [] },
  ],
  [
    "deep ignored-file removal",
    { upserts: [], removes: [], remove_files: ["runs/day/job/affected.md"] },
  ],
  [
    "deep non-file replacement",
    {
      upserts: [],
      removes: [],
      remove_files: [],
      non_file_paths: ["runs/day/job/affected.md"],
    },
  ],
]) {
  assertEqual(
    `${label} immediately reports the retained matching lower bound`,
    deepCatalogBatch(change),
    {
      effect: {
        changed: true,
        needsAuthoritativeRepair: true,
        removedEntries: 1,
        retainedLowerBound: 1,
      },
      paths: ["keep.md"],
    },
  );
}

const oneHourFilter = {
  rowMatches(row, state, nowSec) {
    return state.recency !== "1h" || (row.mtime || 0) >= nowSec - 3600;
  },
};
const replacementOptions = {
  filterState: oneHourFilter,
  nowSec: 10_000,
  state: snapshot({ recency: "1h" }),
};
assertEqual(
  "a bounded Recent window rejects an epoch mtime like the provider",
  model.recentEntryMatches({ path: "epoch.md", type: "file", mtime: 0 }, replacementOptions),
  false,
);
assertEqual(
  "an unbounded Recent window may retain an epoch mtime",
  model.recentEntryMatches(
    { path: "epoch.md", type: "file", mtime: 0 },
    { ...replacementOptions, state: snapshot({ recency: "all" }) },
  ),
  true,
);
assertEqual(
  "only the batch and catalog transitions own live Recent composition",
  {
    batch: typeof model.applyRecentChangeBatch,
    catalog: typeof model.applyRecentCatalogChange,
    countHelper: typeof model.recentMatchingCount,
    prefixHelper: typeof model.removeRecentEntriesByPrefix,
    recompute: typeof model.createRecentRecomputeScheduler,
    replacementHelper: typeof model.recentReplacementNeedsBackfill,
    tally: typeof model.recentFilteredTallyText,
    unseenHelper: typeof model.recentUnseenBeforeMayMatch,
  },
  {
    batch: "function",
    catalog: "function",
    countHelper: "undefined",
    prefixHelper: "undefined",
    recompute: "function",
    replacementHelper: "undefined",
    tally: "function",
    unseenHelper: "undefined",
  },
);

function wireEntry(pathname, type, mtime) {
  return {
    path: pathname,
    name: pathname.split("/").pop(),
    type,
    size: 1,
    mtime_ns: mtime * 1e9,
    ext: type === "file" ? ".md" : "",
  };
}

function liveBatch(initial, operations, options = {}) {
  const entries = new Map(initial.map((entry) => [entry.path, entry]));
  const effect = model.applyRecentChangeBatch(entries, operations, {
    ...replacementOptions,
    limit: options.limit ?? initial.length,
    previousEntries: new Map(options.previous || []),
    truncated: options.truncated ?? true,
  });
  return { effect, paths: Array.from(entries.keys()) };
}

const duplicateNonFileEntries = new Map(
  [
    { path: "docs/changed.md", type: "file", ext: ".md", mtime: 9_500 },
    { path: "keep.md", type: "file", ext: ".md", mtime: 9_000 },
  ].map((entry) => [entry.path, entry]),
);
const duplicateNonFileFsEffect = model.applyRecentChangeBatch(
  duplicateNonFileEntries,
  [{ op: "upsert", entry: wireEntry("docs/changed.md", "dir", 9_750) }],
  {
    ...replacementOptions,
    limit: 2,
    previousEntries: new Map([["docs/changed.md", { type: "file" }]]),
    truncated: true,
  },
);
const duplicateNonFileCatalogEffect = catalogEffect(
  {
    upserts: [],
    removes: [],
    remove_files: [],
    non_file_paths: ["docs/changed.md"],
  },
  duplicateNonFileEntries,
);
assertEqual(
  "duplicate shallow fs and catalog non-file events do not subtract the retained tally twice",
  {
    catalog: duplicateNonFileCatalogEffect,
    fs: duplicateNonFileFsEffect,
    paths: Array.from(duplicateNonFileEntries.keys()),
  },
  {
    catalog: {
      changed: false,
      needsAuthoritativeRepair: false,
      removedEntries: 0,
      retainedLowerBound: null,
    },
    fs: {
      changed: true,
      needsAuthoritativeRepair: true,
      overflowed: false,
      removedDescendants: 0,
      retainedLowerBound: 1,
      truncated: true,
    },
    paths: ["keep.md"],
  },
);

const duplicateRemoveEntries = new Map(
  [
    { path: "docs/deep/changed.md", type: "file", ext: ".md", mtime: 9_500 },
    { path: "keep.md", type: "file", ext: ".md", mtime: 9_000 },
  ].map((entry) => [entry.path, entry]),
);
const duplicateRemoveFsEffect = model.applyRecentChangeBatch(
  duplicateRemoveEntries,
  [{ op: "remove", path: "docs" }],
  {
    ...replacementOptions,
    limit: 2,
    previousEntries: new Map(),
    truncated: true,
  },
);
const duplicateRemoveCatalogEffect = catalogEffect(
  { upserts: [], removes: ["docs"], remove_files: [] },
  duplicateRemoveEntries,
);
assertEqual(
  "duplicate shallow fs and catalog subtree removals keep one stable retained lower bound",
  {
    catalog: duplicateRemoveCatalogEffect,
    fs: duplicateRemoveFsEffect,
    paths: Array.from(duplicateRemoveEntries.keys()),
  },
  {
    catalog: {
      changed: false,
      needsAuthoritativeRepair: true,
      removedEntries: 0,
      retainedLowerBound: 1,
    },
    fs: {
      changed: true,
      needsAuthoritativeRepair: true,
      overflowed: false,
      removedDescendants: 1,
      retainedLowerBound: 1,
      truncated: true,
    },
    paths: ["keep.md"],
  },
);

const retained = [
  { path: "new.md", type: "file", ext: ".md", mtime: 9_500 },
  { path: "old.md", type: "file", ext: ".md", mtime: 9_000 },
];
const ordinaryWrite = liveBatch(
  retained,
  [{ op: "upsert", entry: wireEntry("old.md", "file", 9_750) }],
  { previous: [["old.md", { type: "file" }]] },
);
assertEqual(
  "a normal capped write stays on the local overlay fast path",
  ordinaryWrite.effect.needsAuthoritativeRepair,
  false,
);
assertEqual(
  "the normal write still updates the retained overlay",
  ordinaryWrite.effect.changed,
  true,
);

const rankRegression = liveBatch(
  retained,
  [{ op: "upsert", entry: wireEntry("new.md", "file", 8_500) }],
  { previous: [["new.md", { type: "file" }]] },
);
assertEqual(
  "a retained member that ranks later needs capped-page backfill",
  {
    lowerBound: rankRegression.effect.retainedLowerBound,
    repair: rankRegression.effect.needsAuthoritativeRepair,
  },
  { lowerBound: 2, repair: true },
);

const unseenIneligible = liveBatch(retained, [
  { op: "upsert", entry: wireEntry("unseen.md", "file", 6_000) },
]);
assertEqual(
  "an unseen ineligible file can have subtracted a capped match",
  {
    lowerBound: unseenIneligible.effect.retainedLowerBound,
    repair: unseenIneligible.effect.needsAuthoritativeRepair,
  },
  { lowerBound: 2, repair: true },
);

const unseenRemoval = liveBatch(retained, [{ op: "remove", path: "unseen.md" }]);
assertEqual(
  "an unseen remove cannot preserve an exact capped total",
  unseenRemoval.effect.needsAuthoritativeRepair,
  true,
);

const fileToDirectory = liveBatch(
  retained,
  [{ op: "upsert", entry: wireEntry("unseen.md", "dir", 9_750) }],
  { previous: [["unseen.md", { type: "file" }]] },
);
assertEqual(
  "an unseen file-to-directory replacement repairs capped membership",
  fileToDirectory.effect.needsAuthoritativeRepair,
  true,
);

const directoryAggregate = liveBatch(
  retained,
  [{ op: "upsert", entry: wireEntry("folder", "dir", 9_750) }],
  { previous: [["folder", { type: "dir" }]] },
);
assertEqual(
  "an ordinary directory aggregate does not trigger a provider scan",
  directoryAggregate.effect.needsAuthoritativeRepair,
  false,
);

const subtreeRemoval = liveBatch(
  [
    { path: "keep.md", type: "file", ext: ".md", mtime: 9_500 },
    { path: "runs/day/one.md", type: "file", ext: ".md", mtime: 9_000 },
    { path: "runs/day/two.md", type: "file", ext: ".md", mtime: 8_500 },
  ],
  [{ op: "remove", path: "runs" }],
);
assertEqual(
  "one subtree pass prunes descendants and returns their safe lower bound",
  {
    lowerBound: subtreeRemoval.effect.retainedLowerBound,
    paths: subtreeRemoval.paths,
    removed: subtreeRemoval.effect.removedDescendants,
  },
  { lowerBound: 1, paths: ["keep.md"], removed: 2 },
);

const uncappedUpsert = liveBatch(
  retained.slice(0, 1),
  [{ op: "upsert", entry: wireEntry("unseen.md", "file", 9_750) }],
  { limit: 2, truncated: false },
);
assertEqual(
  "a complete page resolves an unseen eligible upsert locally",
  {
    paths: uncappedUpsert.paths,
    repair: uncappedUpsert.effect.needsAuthoritativeRepair,
    truncated: uncappedUpsert.effect.truncated,
  },
  { paths: ["new.md", "unseen.md"], repair: false, truncated: false },
);

const boundedEntries = new Map([
  ["middle.md", { path: "middle.md", type: "file", mtime: 200 }],
  ["old.md", { path: "old.md", type: "file", mtime: 100 }],
  ["new.md", { path: "new.md", type: "file", mtime: 300 }],
]);
assertEqual(
  "one batch selection reports overflow",
  model.trimRecentEntriesToLimit(boundedEntries, 2),
  true,
);
assertEqual(
  "one batch selection retains the provider's top entries at the route cap",
  Array.from(boundedEntries.keys()).sort(),
  ["middle.md", "new.md"],
);
assertEqual(
  "an already bounded overlay does no more selection work",
  model.trimRecentEntriesToLimit(boundedEntries, 2),
  false,
);
assertEqual("the retained overlay stays bounded", boundedEntries.size, 2);

assertEqual(
  "a settled active Recent view is ready for repair",
  model.recentRepairDisposition(true, false, false),
  "repair",
);
assertEqual(
  "an active request is dirtied instead of duplicated",
  model.recentRepairDisposition(true, true, false),
  "dirty",
);
assertEqual(
  "a pending filter request already covers the invalidation",
  model.recentRepairDisposition(true, false, true),
  "covered",
);
assertEqual(
  "an inactive Recent view ignores repair signals",
  model.recentRepairDisposition(false, false, false),
  "ignore",
);

const firstRequest = model.createRecentRequest("/api/recent?window=1h");
const replacementRequest = model.createRecentRequest("/api/recent?window=1h");
assertEqual(
  "same-URL request replacement uses identity rather than its URL",
  model.recentRequestDisposition(replacementRequest, firstRequest),
  "superseded",
);
assertEqual(
  "an unchanged active request may commit",
  model.recentRequestDisposition(replacementRequest, replacementRequest),
  "commit",
);
model.dirtyRecentRequest(replacementRequest);
assertEqual(
  "a filesystem change forces a fresh snapshot instead of delta replay",
  model.recentRequestDisposition(replacementRequest, replacementRequest),
  "refetch",
);

const scheduledCallbacks = new Map();
const cancelledCallbacks = [];
let nextTimerId = 1;
const fakeClock = {
  setTimeout(callback) {
    const timerId = nextTimerId;
    nextTimerId += 1;
    scheduledCallbacks.set(timerId, callback);
    return timerId;
  },
  clearTimeout(timerId) {
    cancelledCallbacks.push(timerId);
    scheduledCallbacks.delete(timerId);
  },
};
const refetches = [];
const refetchScheduler = model.createRecentRefetchScheduler(
  100,
  (request) => refetches.push(request),
  fakeClock,
);
refetchScheduler.schedule({ windowKey: "1h", requestKey: "types=.md" });
refetchScheduler.schedule({ windowKey: "1h", requestKey: "types=.txt" });
assertEqual("rapid filter changes cancel obsolete timers", cancelledCallbacks, [1]);
assertEqual("rapid filter changes do not launch work early", refetches, []);
for (const callback of scheduledCallbacks.values()) {
  callback();
}
assertEqual("rapid filter changes launch only the final request", refetches, [
  { windowKey: "1h", requestKey: "types=.txt" },
]);

const lateRecomputeCallbacks = new Map();
const lateRecomputeCancellations = [];
let nextRecomputeTimerId = 1;
let currentRecomputeIdentity = { source: "recent", windowKey: "1h", requestKey: "types=.md" };
const recomputes = [];
const recomputeScheduler = model.createRecentRecomputeScheduler(
  100,
  (request) => recomputes.push(request),
  (request) =>
    currentRecomputeIdentity.source === "recent" &&
    currentRecomputeIdentity.windowKey === request.windowKey &&
    currentRecomputeIdentity.requestKey === request.requestKey,
  {
    setTimeout(callback) {
      const timerId = nextRecomputeTimerId;
      nextRecomputeTimerId += 1;
      lateRecomputeCallbacks.set(timerId, callback);
      return timerId;
    },
    clearTimeout(timerId) {
      // Retain the callback to model a timer that reached the task queue just
      // before cancellation. The scheduler's generation guard must still win.
      lateRecomputeCancellations.push(timerId);
    },
  },
);
assertEqual(
  "the first live change schedules one Recent recompute",
  recomputeScheduler.schedule({ windowKey: "1h", requestKey: "types=.md" }),
  "scheduled",
);
assertEqual(
  "a burst coalesces without moving the Recent recompute window",
  recomputeScheduler.schedule({ windowKey: "1h", requestKey: "types=.md" }),
  "coalesced",
);
recomputeScheduler.cancel();
currentRecomputeIdentity = { source: "tree", windowKey: "", requestKey: "" };
lateRecomputeCallbacks.get(1)();
assertEqual("a cancelled source-transition timer cannot repaint", recomputes, []);

currentRecomputeIdentity = { source: "recent", windowKey: "1h", requestKey: "types=.md" };
recomputeScheduler.schedule({ windowKey: "1h", requestKey: "types=.md" });
currentRecomputeIdentity = { source: "recent", windowKey: "24h", requestKey: "types=.md" };
lateRecomputeCallbacks.get(2)();
assertEqual("the callback identity guard rejects an obsolete window", recomputes, []);

currentRecomputeIdentity = { source: "recent", windowKey: "24h", requestKey: "types=.txt" };
recomputeScheduler.schedule({ windowKey: "24h", requestKey: "types=.txt" });
lateRecomputeCallbacks.get(3)();
assertEqual("the current Recent identity may repaint once", recomputes, [
  { windowKey: "24h", requestKey: "types=.txt" },
]);
assertEqual("source transitions cancel the queued timer", lateRecomputeCancellations, [1]);
assertEqual("a fired recompute clears pending state", recomputeScheduler.pending(), false);

scheduledCallbacks.clear();
cancelledCallbacks.length = 0;
const repairs = [];
const repairScheduler = model.createRecentRepairScheduler(
  100,
  (request) => repairs.push(request),
  fakeClock,
);
repairScheduler.schedule({ preserveRows: false, windowKey: "1h", requestKey: "first" });
repairScheduler.schedule({ preserveRows: true, windowKey: "1h", requestKey: "latest" });
assertEqual("a live burst retains only one repair timer", scheduledCallbacks.size, 1);
assertEqual("a live burst does not restart its convergence window", cancelledCallbacks, []);
assertEqual("a scheduled repair reports pending work", repairScheduler.pending(), true);
for (const callback of scheduledCallbacks.values()) {
  callback();
}
assertEqual("a live burst launches one repair for its latest request", repairs, [
  { preserveRows: true, windowKey: "1h", requestKey: "latest" },
]);
assertEqual("a completed repair clears pending state", repairScheduler.pending(), false);

function createContinuityHarness() {
  const timers = [];
  const repairCalls = [];
  const statuses = [];
  const continuity = model.createRecentContinuity({
    delayMs: 100,
    retryBaseMs: 500,
    maxRetryDelayMs: 2000,
    maxRetries: 3,
    onRepair: (request) => repairCalls.push(request),
    onStatus: (status) => statuses.push(status),
    clock: {
      setTimeout(callback, delayMs) {
        const handle = { callback, delayMs };
        timers.push(handle);
        return handle;
      },
      clearTimeout(handle) {
        const index = timers.indexOf(handle);
        if (index >= 0) {
          timers.splice(index, 1);
        }
      },
    },
  });
  return {
    continuity,
    repairCalls,
    statuses,
    timers,
    flush() {
      const timer = timers.shift();
      if (!timer) {
        failures.push("continuity harness: expected a pending timer");
        return null;
      }
      timer.callback();
      return timer.delayMs;
    },
  };
}

const continuityDescriptor = {
  preserveRows: true,
  windowKey: "1h",
  requestKey: "/api/recent?window=1h",
};

const settledBaseline = createContinuityHarness();
const settledBaselineRequest = settledBaseline.continuity.startRequest(
  continuityDescriptor.requestKey,
);
assertEqual(
  "a clean request settles before its render can invalidate",
  settledBaseline.continuity.settleRequest(settledBaselineRequest),
  "commit",
);
assertEqual(
  "the first sentinel repairs a page committed before the SSE baseline",
  settledBaseline.continuity.observeSentinel(true, false, continuityDescriptor),
  { phase: "baseline", disposition: "repair" },
);
assertEqual(
  "a later sentinel repairs a settled page after reconnect",
  settledBaseline.continuity.observeSentinel(true, false, continuityDescriptor),
  { phase: "reconnect", disposition: "repair" },
);
assertEqual("baseline and reconnect repair share one timer", settledBaseline.timers.length, 1);

const requestAfterBaseline = createContinuityHarness();
assertEqual(
  "a first sentinel with no Recent request records the baseline without deferred work",
  requestAfterBaseline.continuity.observeSentinel(false, false, continuityDescriptor),
  { phase: "baseline", disposition: "ignore" },
);
requestAfterBaseline.continuity.startRequest(continuityDescriptor.requestKey);
assertEqual(
  "a request started after the baseline has no redundant repair",
  requestAfterBaseline.continuity.pending(),
  false,
);

const activeBaseline = createContinuityHarness();
const activeBaselineRequest = activeBaseline.continuity.startRequest(
  continuityDescriptor.requestKey,
);
assertEqual(
  "the first sentinel dirties a request that began before the baseline",
  activeBaseline.continuity.observeSentinel(true, false, continuityDescriptor),
  { phase: "baseline", disposition: "dirty" },
);
assertEqual(
  "the pre-baseline request must refetch when it settles",
  activeBaseline.continuity.settleRequest(activeBaselineRequest),
  "refetch",
);

const expiryDuringCommit = createContinuityHarness();
const expiringRequest = expiryDuringCommit.continuity.startRequest(continuityDescriptor.requestKey);
expiryDuringCommit.continuity.settleRequest(expiringRequest);
assertEqual(
  "commit settlement clears active identity before synchronous expiry",
  expiryDuringCommit.continuity.hasActiveRequest(),
  false,
);
assertEqual(
  "expiry discovered during commit schedules repair rather than dirtying a settled request",
  expiryDuringCommit.continuity.invalidate(true, false, continuityDescriptor),
  "repair",
);

const retryingRepair = createContinuityHarness();
retryingRepair.continuity.scheduleRepair(continuityDescriptor);
assertEqual("an initial repair uses the fixed coalescing delay", retryingRepair.flush(), 100);
assertEqual(
  "the first background failure schedules bounded backoff",
  retryingRepair.continuity.repairFailed(continuityDescriptor, true),
  "retrying",
);
assertEqual(
  "another invalidation coalesces into the pending retry",
  retryingRepair.continuity.scheduleRepair(continuityDescriptor),
  "coalesced",
);
assertEqual("coalescing does not add a parallel retry", retryingRepair.timers.length, 1);
assertEqual("the first retry uses the base backoff", retryingRepair.flush(), 500);
retryingRepair.continuity.repairFailed(continuityDescriptor, true);
assertEqual("the second retry doubles its backoff", retryingRepair.flush(), 1000);
retryingRepair.continuity.repairFailed(continuityDescriptor, true);
assertEqual("the third retry reaches the configured cap", retryingRepair.flush(), 2000);
assertEqual(
  "the retry budget exposes stale state instead of looping forever",
  retryingRepair.continuity.repairFailed(continuityDescriptor, true),
  "stale",
);
assertEqual("exhausted retry state retains no timer", retryingRepair.timers.length, 0);
assertEqual("retry status changes are observable", retryingRepair.statuses, ["retrying", "stale"]);
assertEqual(
  "a later authoritative invalidation starts a new bounded recovery episode",
  retryingRepair.continuity.invalidate(true, false, continuityDescriptor),
  "repair",
);
assertEqual("the recovery episode has one timer", retryingRepair.timers.length, 1);
assertEqual(
  "the recovery episode returns to retrying state",
  retryingRepair.continuity.status(),
  "retrying",
);

const repairTimerRace = createContinuityHarness();
repairTimerRace.continuity.scheduleRepair(continuityDescriptor);
repairTimerRace.flush();
const newerRequest = repairTimerRace.continuity.startRequest(continuityDescriptor.requestKey);
assertEqual(
  "a repair timer dirties a newer active request instead of overlapping it",
  repairTimerRace.continuity.repairReady(true, false),
  "dirty",
);
assertEqual(
  "the newer request carries that timer invalidation to settlement",
  repairTimerRace.continuity.settleRequest(newerRequest),
  "refetch",
);

const cancelledRepair = createContinuityHarness();
cancelledRepair.continuity.scheduleRepair(continuityDescriptor);
cancelledRepair.flush();
cancelledRepair.continuity.repairFailed(continuityDescriptor, true);
cancelledRepair.continuity.cancelRepairs();
assertEqual("a filter or source change cancels retry work", cancelledRepair.timers.length, 0);
assertEqual("cancellation clears stale UI state", cancelledRepair.continuity.status(), "fresh");
assertEqual(
  "a late failure from the cancelled identity is ignored",
  cancelledRepair.continuity.repairFailed(continuityDescriptor, true),
  "ignored",
);

const successfulRepair = createContinuityHarness();
successfulRepair.continuity.scheduleRepair(continuityDescriptor);
successfulRepair.flush();
successfulRepair.continuity.repairFailed(continuityDescriptor, true);
successfulRepair.continuity.repairSucceeded(continuityDescriptor);
assertEqual("success cancels an obsolete retry", successfulRepair.timers.length, 0);
assertEqual("success clears retry status", successfulRepair.continuity.status(), "fresh");
successfulRepair.continuity.scheduleRepair(continuityDescriptor);
successfulRepair.flush();
successfulRepair.continuity.repairFailed(continuityDescriptor, true);
assertEqual("success resets backoff for the next episode", successfulRepair.timers[0].delayMs, 500);

if (failures.length > 0) {
  console.error(`FAIL tree filter model\n${failures.join("\n")}`);
  process.exit(1);
}
console.log("OK tree filter model");
