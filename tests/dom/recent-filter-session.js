// Composed, browserless navigation-filter session.
//
// This loads the production filter predicate, tree model, and Quick File
// catalog. The transcript is deliberately richer than "OK": it records the
// request the browser makes and the tree it will hand to the bounded renderer.
// Three collapsed root folders whose descendants remain in the model were the
// shape that disappeared in the browser after a later DOM-only filtering pass.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const sandbox = {
  Array,
  Date,
  Map,
  Math,
  Object,
  Set,
  String,
  encodeURIComponent,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.METABROWSER_SETTINGS = {
  RECENT_WINDOW_SECONDS: { all: null, live: 90, "1h": 3600 },
};
sandbox.metabrowser = {
  prefs: { remove() {} },
};
sandbox.dispatchEvent = () => {};
sandbox.CustomEvent = function CustomEvent() {};
vm.createContext(sandbox);

for (const relative of [
  "filter-state.js",
  "tree-filter-model.js",
  "tree-expansion.js",
  "known-file-catalog.js",
]) {
  const filename = path.join(repoRoot, "src/metabrowser/static", relative);
  vm.runInContext(fs.readFileSync(filename, "utf-8"), sandbox, { filename });
}

const filter = sandbox.metabrowser.filterState;
const model = sandbox.MetabrowserTreeFilterModel;
const expansion = sandbox.MetabrowserTreeExpansion;
const knownFileCatalog = sandbox.MetabrowserKnownFileCatalog;
const nowSec = 2_000_000_000;
const state = {
  recency: "1h",
  types: [".md"],
  size: "all",
  showIgnored: true,
};
const entries = [
  { path: "alpha/a.md", type: "file", ext: ".md", size: 11, mtime: nowSec - 10 },
  { path: "alpha/b.md", type: "file", ext: ".md", size: 12, mtime: nowSec - 10.4 },
  { path: "bravo/a.md", type: "file", ext: ".md", size: 13, mtime: nowSec - 20 },
  { path: "bravo/b.md", type: "file", ext: ".md", size: 14, mtime: nowSec - 20.5 },
  { path: "charlie/a.md", type: "file", ext: ".md", size: 15, mtime: nowSec - 30 },
  { path: "charlie/b.md", type: "file", ext: ".md", size: 16, mtime: nowSec - 30.5 },
  { path: "noise/skip.txt", type: "file", ext: ".txt", size: 99, mtime: nowSec - 5 },
];

const treeCursor = model.recentFilterCursor(
  { ...state, recency: "all" },
  5000,
  filter.SIZE_MIN_BYTES,
);
const recentCursor = model.recentFilterCursor(state, 5000, filter.SIZE_MIN_BYTES);
const changedRecentCursor = model.recentFilterCursor(
  { ...state, types: [".py"] },
  5000,
  filter.SIZE_MIN_BYTES,
);
const controlTransitions = {
  enterRecent: model.recentFilterTransition(treeCursor, recentCursor).action,
  sameSelection: model.recentFilterTransition(recentCursor, recentCursor).action,
  sameWindowFilterChange: model.recentFilterTransition(recentCursor, changedRecentCursor).action,
  returnToTree: model.recentFilterTransition(changedRecentCursor, treeCursor).action,
};

let view = null;
model.renderRecentView(
  entries,
  {
    filterState: filter,
    ignoredDirectoryPaths: new Set(),
    limit: 5000,
    nowSec,
    clusterPct: 0.05,
    state,
  },
  (projection) => {
    view = projection;
  },
);

// Continuity is a browser-owned state machine even though its repair data
// comes from /api/recent. Exercise its production decisions here so the CLI
// transcript pins the same invalidation behavior the mounted panel uses.
const cappedEntries = new Map([
  ["tracked/old.md", { path: "tracked/old.md", type: "file", mtime: nowSec - 30 }],
  ["tracked/new.md", { path: "tracked/new.md", type: "file", mtime: nowSec - 10 }],
  [
    "ignored/newest.md",
    { path: "ignored/newest.md", type: "file", mtime: nowSec - 5, gitignored: true },
  ],
]);
const cappedOverflow = model.trimRecentEntriesToLimit(cappedEntries, 2);

const retainedPage = [
  { path: "page/new.md", type: "file", ext: ".md", size: 2, mtime: nowSec - 10 },
  { path: "page/old.md", type: "file", ext: ".md", size: 1, mtime: nowSec - 20 },
];

function fsEntry(pathname, type, mtime) {
  return {
    path: pathname,
    name: pathname.split("/").pop(),
    type,
    size: 1,
    mtime_ns: mtime * 1e9,
    ext: type === "file" ? ".md" : "",
  };
}

function applyLiveBatch({
  initial = retainedPage,
  limit = 2,
  operations,
  previous = [],
  truncated = true,
}) {
  const overlay = new Map(initial.map((entry) => [entry.path, entry]));
  const effect = model.applyRecentChangeBatch(overlay, operations, {
    filterState: filter,
    limit,
    nowSec,
    previousEntries: new Map(previous),
    state,
    truncated,
  });
  return {
    ...effect,
    retainedPaths: Array.from(overlay.keys()),
  };
}

// This matrix is deliberately expressed in the real fs.change wire shapes.
// Its capped cases are the ones where absence from the retained page cannot
// answer whether a previous provider match was added, removed, or replaced.
const liveBatchMatrix = {
  eligibleUnseenFileUpsert: applyLiveBatch({
    operations: [{ op: "upsert", entry: fsEntry("unseen/fresh.md", "file", nowSec - 5) }],
  }),
  ineligibleUnseenFileUpsert: applyLiveBatch({
    operations: [{ op: "upsert", entry: fsEntry("unseen/aged-out.md", "file", nowSec - 7200) }],
  }),
  unknownRemove: applyLiveBatch({
    operations: [{ op: "remove", path: "unseen/below-page.md" }],
  }),
  unseenFileToDirectory: applyLiveBatch({
    operations: [{ op: "upsert", entry: fsEntry("unseen/changed.md", "dir", nowSec - 5) }],
    previous: [["unseen/changed.md", { type: "file" }]],
  }),
  subtreeRemove: applyLiveBatch({
    initial: [
      { path: "keep/visible.md", type: "file", ext: ".md", mtime: nowSec - 10 },
      { path: "runs/day/a.md", type: "file", ext: ".md", mtime: nowSec - 20 },
      { path: "runs/day/b.md", type: "file", ext: ".md", mtime: nowSec - 30 },
    ],
    limit: 3,
    operations: [{ op: "remove", path: "runs" }],
  }),
  ordinaryDirectoryAggregate: applyLiveBatch({
    operations: [{ op: "upsert", entry: fsEntry("page", "dir", nowSec - 5) }],
    previous: [["page", { type: "dir" }]],
  }),
  ordinaryKnownWrite: applyLiveBatch({
    operations: [{ op: "upsert", entry: fsEntry("page/old.md", "file", nowSec - 5) }],
    previous: [["page/old.md", { type: "file" }]],
  }),
  knownRankRegression: applyLiveBatch({
    operations: [{ op: "upsert", entry: fsEntry("page/new.md", "file", nowSec - 30) }],
    previous: [["page/new.md", { type: "file" }]],
  }),
  uncappedEligibleUpsert: applyLiveBatch({
    initial: retainedPage.slice(0, 1),
    operations: [{ op: "upsert", entry: fsEntry("unseen/fresh.md", "file", nowSec - 5) }],
    truncated: false,
  }),
  knownRemoval: applyLiveBatch({
    operations: [{ op: "remove", path: "page/old.md" }],
    previous: [["page/old.md", { type: "file" }]],
  }),
  knownExpiry: applyLiveBatch({
    operations: [{ op: "upsert", entry: fsEntry("page/old.md", "file", nowSec - 7200) }],
    previous: [["page/old.md", { type: "file" }]],
  }),
};

const expectedLiveBatchMatrix = {
  eligibleUnseenFileUpsert: {
    changed: true,
    needsAuthoritativeRepair: true,
    overflowed: true,
    removedDescendants: 0,
    retainedLowerBound: 2,
    truncated: true,
    retainedPaths: ["unseen/fresh.md", "page/new.md"],
  },
  ineligibleUnseenFileUpsert: {
    changed: false,
    needsAuthoritativeRepair: true,
    overflowed: false,
    removedDescendants: 0,
    retainedLowerBound: 2,
    truncated: true,
    retainedPaths: ["page/new.md", "page/old.md"],
  },
  unknownRemove: {
    changed: false,
    needsAuthoritativeRepair: true,
    overflowed: false,
    removedDescendants: 0,
    retainedLowerBound: 2,
    truncated: true,
    retainedPaths: ["page/new.md", "page/old.md"],
  },
  unseenFileToDirectory: {
    changed: false,
    needsAuthoritativeRepair: true,
    overflowed: false,
    removedDescendants: 0,
    retainedLowerBound: 2,
    truncated: true,
    retainedPaths: ["page/new.md", "page/old.md"],
  },
  subtreeRemove: {
    changed: true,
    needsAuthoritativeRepair: true,
    overflowed: false,
    removedDescendants: 2,
    retainedLowerBound: 1,
    truncated: true,
    retainedPaths: ["keep/visible.md"],
  },
  ordinaryDirectoryAggregate: {
    changed: false,
    needsAuthoritativeRepair: false,
    overflowed: false,
    removedDescendants: 0,
    retainedLowerBound: null,
    truncated: true,
    retainedPaths: ["page/new.md", "page/old.md"],
  },
  ordinaryKnownWrite: {
    changed: true,
    needsAuthoritativeRepair: false,
    overflowed: false,
    removedDescendants: 0,
    retainedLowerBound: null,
    truncated: true,
    retainedPaths: ["page/new.md", "page/old.md"],
  },
  knownRankRegression: {
    changed: true,
    needsAuthoritativeRepair: true,
    overflowed: false,
    removedDescendants: 0,
    retainedLowerBound: 2,
    truncated: true,
    retainedPaths: ["page/new.md", "page/old.md"],
  },
  uncappedEligibleUpsert: {
    changed: true,
    needsAuthoritativeRepair: false,
    overflowed: false,
    removedDescendants: 0,
    retainedLowerBound: null,
    truncated: false,
    retainedPaths: ["page/new.md", "unseen/fresh.md"],
  },
  knownRemoval: {
    changed: true,
    needsAuthoritativeRepair: true,
    overflowed: false,
    removedDescendants: 0,
    retainedLowerBound: 1,
    truncated: true,
    retainedPaths: ["page/new.md"],
  },
  knownExpiry: {
    changed: true,
    needsAuthoritativeRepair: true,
    overflowed: false,
    removedDescendants: 0,
    retainedLowerBound: 1,
    truncated: true,
    retainedPaths: ["page/new.md"],
  },
};

if (JSON.stringify(liveBatchMatrix) !== JSON.stringify(expectedLiveBatchMatrix)) {
  throw new Error(`unexpected Recent live-batch matrix: ${JSON.stringify(liveBatchMatrix)}`);
}

const repairDescriptor = {
  windowKey: "1h",
  requestKey: "/api/recent?window=1h&limit=5000&types=.md",
  preserveRows: true,
};

function createContinuityHarness(maxRetries = 2) {
  const timers = [];
  const repairs = [];
  const statuses = [];
  const continuity = model.createRecentContinuity({
    delayMs: 100,
    retryBaseMs: 500,
    maxRetryDelayMs: 2000,
    maxRetries,
    onRepair: (request) => repairs.push(request),
    onStatus: (status) => statuses.push(status),
    clock: {
      clearTimeout(handle) {
        const index = timers.indexOf(handle);
        if (index >= 0) {
          timers.splice(index, 1);
        }
      },
      setTimeout(callback, delayMs) {
        const handle = { callback, delayMs };
        timers.push(handle);
        return handle;
      },
    },
  });
  return {
    continuity,
    repairs,
    statuses,
    timers,
    flush() {
      const timer = timers.shift();
      timer.callback();
      return timer.delayMs;
    },
  };
}

const settledBeforeBaseline = createContinuityHarness();
const settledRequest = settledBeforeBaseline.continuity.startRequest(repairDescriptor.requestKey);
const settledDisposition = settledBeforeBaseline.continuity.settleRequest(settledRequest);
const settledBaseline = model.observeRecentSentinel(settledBeforeBaseline.continuity, {
  recentActive: true,
  filterRefetchPending: false,
  repair: repairDescriptor,
});
const settledReconnect = model.observeRecentSentinel(settledBeforeBaseline.continuity, {
  recentActive: true,
  filterRefetchPending: false,
  repair: repairDescriptor,
});

const requestAfterBaseline = createContinuityHarness();
const inactiveBaseline = model.observeRecentSentinel(requestAfterBaseline.continuity, {
  recentActive: false,
  filterRefetchPending: false,
  repair: repairDescriptor,
});
requestAfterBaseline.continuity.startRequest(repairDescriptor.requestKey);

const activeAtBaseline = createContinuityHarness();
const preBaselineRequest = activeAtBaseline.continuity.startRequest(repairDescriptor.requestKey);
const activeBaseline = model.observeRecentSentinel(activeAtBaseline.continuity, {
  recentActive: true,
  filterRefetchPending: false,
  repair: repairDescriptor,
});
const preBaselineDisposition = activeAtBaseline.continuity.settleRequest(preBaselineRequest);

const expiryDuringCommit = createContinuityHarness();
const expiringLoad = model.beginRecentRequest(expiryDuringCommit.continuity, recentCursor, false);
const commitTrace = [];
let cleanRenderedPaths = [];
let activeDuringCommit = true;
let activeDuringRender = true;
let expiryAction = null;
const expiringDisposition = model.settleRecentSuccess(
  expiryDuringCommit.continuity,
  expiringLoad.request,
  expiringLoad.repair,
  {
    current: true,
    commit() {
      activeDuringCommit = expiryDuringCommit.continuity.hasActiveRequest();
      commitTrace.push("commit");
    },
    render() {
      model.renderRecentView(
        entries,
        {
          filterState: filter,
          ignoredDirectoryPaths: new Set(),
          limit: 5000,
          nowSec,
          clusterPct: 0.05,
          state,
        },
        (projection) => {
          activeDuringRender = expiryDuringCommit.continuity.hasActiveRequest();
          commitTrace.push("render");
          cleanRenderedPaths = projection.entries.map((entry) => entry.path);
          expiryAction = model.invalidateRecent(expiryDuringCommit.continuity, {
            recentActive: true,
            filterRefetchPending: false,
            repair: expiringLoad.repair,
          });
        },
      );
    },
  },
);

const dirtySuccess = createContinuityHarness();
const dirtySuccessRequest = dirtySuccess.continuity.startRequest(repairDescriptor.requestKey);
dirtySuccess.continuity.dirtyActiveRequest();
let dirtyCommitCalled = false;
const dirtySuccessDisposition = model.settleRecentSuccess(
  dirtySuccess.continuity,
  dirtySuccessRequest,
  repairDescriptor,
  {
    current: true,
    commit() {
      dirtyCommitCalled = true;
    },
    render() {
      throw new Error("dirty response rendered before its authoritative repair");
    },
  },
);

const staleSelection = createContinuityHarness();
const staleSelectionLoad = model.beginRecentRequest(staleSelection.continuity, recentCursor, false);
let staleSelectionCommitCalled = false;
const staleSelectionDisposition = model.settleRecentSuccess(
  staleSelection.continuity,
  staleSelectionLoad.request,
  staleSelectionLoad.repair,
  {
    current: changedRecentCursor.recentRequestKey === staleSelectionLoad.url,
    commit() {
      staleSelectionCommitCalled = true;
    },
    render() {
      throw new Error("a response for a stale filter selection rendered");
    },
  },
);

const failedRepairComposition = createContinuityHarness();
failedRepairComposition.continuity.scheduleRepair(repairDescriptor);
failedRepairComposition.flush();
let failedRepairRequest = null;
const failedRepairRunDisposition = model.runRecentRepair(
  failedRepairComposition.continuity,
  failedRepairComposition.repairs[0],
  {
    current: true,
    filterRefetchPending: false,
    recentLoaded: true,
    viewCommitted: true,
    fetch() {
      failedRepairRequest = failedRepairComposition.continuity.startRequest(
        repairDescriptor.requestKey,
      );
    },
  },
);
let initialErrorShown = false;
const failedRepairDisposition = model.settleRecentFailure(
  failedRepairComposition.continuity,
  failedRepairRequest,
  repairDescriptor,
  new Error("offline"),
  {
    current: true,
    classify: () => ({ retryable: true }),
    showInitialError() {
      initialErrorShown = true;
    },
  },
);

const initialFailureComposition = createContinuityHarness();
const initialFailureRequest = initialFailureComposition.continuity.startRequest(
  repairDescriptor.requestKey,
);
let initialFailureShown = false;
const initialFailureDisposition = model.settleRecentFailure(
  initialFailureComposition.continuity,
  initialFailureRequest,
  { ...repairDescriptor, preserveRows: false },
  new Error("denied"),
  {
    current: true,
    classify: () => ({ retryable: false }),
    showInitialError() {
      initialFailureShown = true;
    },
  },
);

const repairComposition = createContinuityHarness();
const repairFetches = [];
const repairRunDisposition = model.runRecentRepair(repairComposition.continuity, repairDescriptor, {
  current: true,
  filterRefetchPending: false,
  recentLoaded: true,
  viewCommitted: true,
  fetch: (windowKey, preserveRows) => repairFetches.push({ windowKey, preserveRows }),
});
const staleRepairDisposition = model.runRecentRepair(
  repairComposition.continuity,
  repairDescriptor,
  {
    current: false,
    filterRefetchPending: false,
    recentLoaded: true,
    viewCommitted: true,
    fetch() {
      throw new Error("a stale repair reached the transport");
    },
  },
);

const fixedWindow = createContinuityHarness();
fixedWindow.continuity.scheduleRepair({ ...repairDescriptor, preserveRows: false });
const fixedWindowSecondAction = fixedWindow.continuity.scheduleRepair(repairDescriptor);
const fixedWindowTimerCount = fixedWindow.timers.length;
fixedWindow.flush();
const timerRaceRequest = fixedWindow.continuity.startRequest(repairDescriptor.requestKey);
const timerRaceAction = fixedWindow.continuity.repairReady(true, false);
const timerRaceDisposition = fixedWindow.continuity.settleRequest(timerRaceRequest);

const retryLifecycle = createContinuityHarness();
retryLifecycle.continuity.scheduleRepair(repairDescriptor);
const initialRepairDelay = retryLifecycle.flush();
const firstFailure = retryLifecycle.continuity.repairFailed(repairDescriptor, true);
const firstRetryDelay = retryLifecycle.timers[0].delayMs;
const coalescedRetry = retryLifecycle.continuity.scheduleRepair(repairDescriptor);
const timersAfterCoalescing = retryLifecycle.timers.length;
retryLifecycle.flush();
retryLifecycle.continuity.repairFailed(repairDescriptor, true);
const secondRetryDelay = retryLifecycle.flush();
const terminalFailure = retryLifecycle.continuity.repairFailed(repairDescriptor, true);
const statusBeforeRecoverySignal = retryLifecycle.continuity.status();
const pendingBeforeRecoverySignal = retryLifecycle.continuity.pending();
const recoverySignal = retryLifecycle.continuity.invalidate(true, false, repairDescriptor);
const recoverySignalDelay = retryLifecycle.timers[0].delayMs;
const statusAfterRecoverySignal = retryLifecycle.continuity.status();
retryLifecycle.flush();
const recoveryFailure = retryLifecycle.continuity.repairFailed(repairDescriptor, true);
const recoveryRetryDelay = retryLifecycle.timers[0].delayMs;

const cancellation = createContinuityHarness();
cancellation.continuity.scheduleRepair(repairDescriptor);
cancellation.flush();
cancellation.continuity.repairFailed(repairDescriptor, true);
cancellation.continuity.cancelRepairs();
const lateCancelledFailure = cancellation.continuity.repairFailed(repairDescriptor, true);

const successReset = createContinuityHarness();
successReset.continuity.scheduleRepair(repairDescriptor);
successReset.flush();
successReset.continuity.repairFailed(repairDescriptor, true);
const delayBeforeSuccess = successReset.timers[0].delayMs;
successReset.continuity.repairSucceeded(repairDescriptor);
const statusAfterSuccess = successReset.continuity.status();
successReset.continuity.scheduleRepair(repairDescriptor);
successReset.flush();
successReset.continuity.repairFailed(repairDescriptor, true);
const delayAfterSuccess = successReset.timers[0].delayMs;

const integration = {
  controlTransitions,
  cleanResponse: {
    disposition: expiringDisposition,
    activeDuringCommit,
    activeDuringRender,
    renderedPaths: cleanRenderedPaths,
    request: expiringLoad.url,
    trace: commitTrace,
  },
  dirtyResponse: {
    commitCalled: dirtyCommitCalled,
    disposition: dirtySuccessDisposition,
    repairPending: dirtySuccess.continuity.pending(),
  },
  staleSelectionResponse: {
    commitCalled: staleSelectionCommitCalled,
    disposition: staleSelectionDisposition,
  },
  failedBackgroundRepair: {
    disposition: failedRepairDisposition,
    initialErrorShown,
    repairDisposition: failedRepairRunDisposition,
    retryPending: failedRepairComposition.continuity.pending(),
    status: failedRepairComposition.continuity.status(),
  },
  failedInitialLoad: {
    disposition: initialFailureDisposition,
    initialErrorShown: initialFailureShown,
    retryPending: initialFailureComposition.continuity.pending(),
  },
  repairCallback: {
    disposition: repairRunDisposition,
    fetches: repairFetches,
    staleDisposition: staleRepairDisposition,
  },
};

const deepNonFileChange = {
  upserts: [],
  removes: [],
  remove_files: [],
  non_file_paths: ["runs/day/job/replaced-dir", "runs/day/job/replaced-link"],
};
function recentCatalogEffect(change, entries = new Map()) {
  return model.applyRecentCatalogChange(entries, change, {
    filterState: filter,
    nowSec,
    state,
    visibleDepth: 2,
  });
}
const replacementCatalog = knownFileCatalog.create();
replacementCatalog.applyBulkSnapshot(
  [
    { p: "runs/day/job/replaced-dir", e: ".md" },
    { p: "runs/day/job/replaced-dir/child.md", e: ".md" },
  ],
  true,
);
replacementCatalog.observeNavigation("runs/day/job/replaced-link", ".md");
replacementCatalog.applyCatalogChange(deepNonFileChange);
const replacementRecentEntries = new Map(
  [
    "runs/day/job/replaced-dir",
    "runs/day/job/replaced-dir/child.md",
    "runs/day/job/replaced-link",
  ].map((pathname) => [
    pathname,
    { path: pathname, type: "file", ext: ".md", size: 1, mtime: nowSec - 1 },
  ]),
);
const nonFileReplacementEffect = recentCatalogEffect(deepNonFileChange, replacementRecentEntries);
const nonFileReplacement = {
  event: deepNonFileChange,
  recentEffect: nonFileReplacementEffect,
  recentPaths: Array.from(replacementRecentEntries.keys()),
  quickFilePaths: replacementCatalog.snapshot().files.map((entry) => entry.path),
};

const deepUpsertChange = {
  upserts: [{ p: "runs/day/job/changed.md", e: ".md" }],
  removes: [],
  remove_files: [],
};
const deepUpsertEntries = new Map(
  ["runs/day/job/changed.md", "keep.md"].map((pathname) => [
    pathname,
    { path: pathname, type: "file", ext: ".md", size: 1, mtime: nowSec - 1 },
  ]),
);
const deepUpsertEffect = recentCatalogEffect(deepUpsertChange, deepUpsertEntries);
const untruncatedDeepUpsert = {
  event: deepUpsertChange,
  recentEffect: deepUpsertEffect,
  recentPaths: Array.from(deepUpsertEntries.keys()),
  tally: model.recentFilteredTallyText(deepUpsertEffect.retainedLowerBound ?? 0, {
    totalMatching: deepUpsertEffect.retainedLowerBound ?? 0,
    totalMatchingExact: false,
    truncated: false,
  }),
};

const lateRecomputeCallbacks = new Map();
const cancelledRecomputeTimers = [];
const recomputeRenders = [];
let nextRecomputeTimerId = 1;
let currentRecomputeCursor = recentCursor;
const recomputeScheduler = model.createRecentRecomputeScheduler(
  100,
  (request) => recomputeRenders.push(request),
  (request) =>
    currentRecomputeCursor.source === "recent" &&
    currentRecomputeCursor.windowKey === request.windowKey &&
    currentRecomputeCursor.recentRequestKey === request.requestKey,
  {
    setTimeout(callback) {
      const timerId = nextRecomputeTimerId;
      nextRecomputeTimerId += 1;
      lateRecomputeCallbacks.set(timerId, callback);
      return timerId;
    },
    clearTimeout(timerId) {
      // Keep callbacks callable to model a browser task already queued when
      // the application cancels its timer during a transition.
      cancelledRecomputeTimers.push(timerId);
    },
  },
);
function recomputeRequest(cursor) {
  return { windowKey: cursor.windowKey, requestKey: cursor.recentRequestKey };
}

const sourceRecomputeSchedule = recomputeScheduler.schedule(recomputeRequest(recentCursor));
recomputeScheduler.cancel();
currentRecomputeCursor = treeCursor;
lateRecomputeCallbacks.get(1)();
const rendersAfterSourceTransition = recomputeRenders.length;

currentRecomputeCursor = recentCursor;
const windowRecomputeSchedule = recomputeScheduler.schedule(recomputeRequest(recentCursor));
const changedWindowCursor = model.recentFilterCursor(
  { ...state, recency: "24h" },
  5000,
  filter.SIZE_MIN_BYTES,
);
currentRecomputeCursor = changedWindowCursor;
lateRecomputeCallbacks.get(2)();
const rendersAfterWindowTransition = recomputeRenders.length;

currentRecomputeCursor = recentCursor;
const filterRecomputeSchedule = recomputeScheduler.schedule(recomputeRequest(recentCursor));
recomputeScheduler.cancel();
currentRecomputeCursor = changedRecentCursor;
lateRecomputeCallbacks.get(3)();
const rendersAfterFilterTransition = recomputeRenders.length;
const currentRecomputeSchedule = recomputeScheduler.schedule(recomputeRequest(changedRecentCursor));
lateRecomputeCallbacks.get(4)();
const recomputeTransitions = {
  source: {
    schedule: sourceRecomputeSchedule,
    cancelled: cancelledRecomputeTimers.includes(1),
    rendersAfterLateTimer: rendersAfterSourceTransition,
  },
  window: {
    schedule: windowRecomputeSchedule,
    rendersAfterLateTimer: rendersAfterWindowTransition,
  },
  filter: {
    schedule: filterRecomputeSchedule,
    cancelled: cancelledRecomputeTimers.includes(3),
    rendersAfterLateTimer: rendersAfterFilterTransition,
  },
  current: {
    schedule: currentRecomputeSchedule,
    renders: recomputeRenders,
    pending: recomputeScheduler.pending(),
  },
};

const activeResync = createContinuityHarness();
const activeResyncRequest = activeResync.continuity.startRequest(repairDescriptor.requestKey);
const activeResyncAction = model.invalidateRecent(activeResync.continuity, {
  recentActive: true,
  filterRefetchPending: false,
  repair: repairDescriptor,
});
let activeResyncCommitCalled = false;
const activeResyncSettle = model.settleRecentSuccess(
  activeResync.continuity,
  activeResyncRequest,
  repairDescriptor,
  {
    current: true,
    commit() {
      activeResyncCommitCalled = true;
    },
    render() {
      throw new Error("a pre-resync Recent request rendered");
    },
  },
);

const settledResync = createContinuityHarness();
const settledResyncRequest = settledResync.continuity.startRequest(repairDescriptor.requestKey);
const settledResyncRequestDisposition =
  settledResync.continuity.settleRequest(settledResyncRequest);
const settledResyncAction = model.invalidateRecent(settledResync.continuity, {
  recentActive: true,
  filterRefetchPending: false,
  repair: repairDescriptor,
});
const settledResyncTimerCount = settledResync.timers.length;
const settledResyncDelay = settledResync.flush();
const settledResyncFetches = [];
const settledResyncRun = model.runRecentRepair(settledResync.continuity, settledResync.repairs[0], {
  current: true,
  filterRefetchPending: false,
  recentLoaded: true,
  viewCommitted: true,
  fetch: (windowKey, preserveRows) => settledResyncFetches.push({ windowKey, preserveRows }),
});
const resync = {
  activeRequest: {
    invalidation: activeResyncAction,
    settle: activeResyncSettle,
    commitCalled: activeResyncCommitCalled,
    repairPending: activeResync.continuity.pending(),
  },
  settledView: {
    requestDisposition: settledResyncRequestDisposition,
    invalidation: settledResyncAction,
    timerCount: settledResyncTimerCount,
    delayMs: settledResyncDelay,
    run: settledResyncRun,
    fetches: settledResyncFetches,
  },
};

if (
  integration.controlTransitions.enterRecent !== "load-recent" ||
  integration.controlTransitions.sameSelection !== "apply" ||
  integration.controlTransitions.sameWindowFilterChange !== "refetch-recent" ||
  integration.controlTransitions.returnToTree !== "load-tree" ||
  integration.cleanResponse.disposition !== "committed" ||
  integration.cleanResponse.activeDuringCommit ||
  integration.cleanResponse.activeDuringRender ||
  JSON.stringify(integration.cleanResponse.trace) !== JSON.stringify(["commit", "render"]) ||
  integration.dirtyResponse.disposition !== "repair-scheduled" ||
  integration.dirtyResponse.commitCalled ||
  !integration.dirtyResponse.repairPending ||
  integration.staleSelectionResponse.disposition !== "ignored" ||
  integration.staleSelectionResponse.commitCalled ||
  integration.failedBackgroundRepair.repairDisposition !== "repair" ||
  integration.failedBackgroundRepair.disposition !== "repair-failed" ||
  integration.failedBackgroundRepair.initialErrorShown ||
  !integration.failedBackgroundRepair.retryPending ||
  integration.failedBackgroundRepair.status !== "retrying" ||
  integration.failedInitialLoad.disposition !== "initial-failed" ||
  !integration.failedInitialLoad.initialErrorShown ||
  integration.failedInitialLoad.retryPending ||
  integration.repairCallback.disposition !== "repair" ||
  integration.repairCallback.fetches.length !== 1 ||
  integration.repairCallback.staleDisposition !== "cancelled"
) {
  throw new Error(`unexpected Recent production composition: ${JSON.stringify(integration)}`);
}

const report = {
  request: expiringLoad.url,
  matchingFiles: view.entries.map((entry) => entry.path),
  defaultExpanded: Array.from(expansion.chooseDefaultExpandedPaths(view.tree, 20, 200)).sort(),
  selectedCount: view.entries.length,
  rootNodeCount: view.tree.length,
  rootNodes: view.tree.map((node) => ({
    path: node.path,
    files: node.total_files,
    expanded: node.expanded,
    childrenInModel: node.children.length,
  })),
  continuity: {
    recomputeTransitions,
    resync,
    untruncatedDeepUpsert,
    nonFileReplacement,
    deepCatalogChangeNeedsRepair: recentCatalogEffect({
      upserts: [{ p: "runs/day/job/live.md" }],
      removes: [],
      remove_files: [],
    }).needsAuthoritativeRepair,
    deepDirectoryReplacementNeedsRepair: recentCatalogEffect({
      upserts: [],
      removes: [],
      remove_files: [],
      non_file_paths: ["runs/day/job/replaced-dir"],
    }).needsAuthoritativeRepair,
    deepSymlinkReplacementNeedsRepair: recentCatalogEffect({
      upserts: [],
      removes: [],
      remove_files: [],
      non_file_paths: ["runs/day/job/replaced-link"],
    }).needsAuthoritativeRepair,
    shallowNonFileReplacementNeedsRepair: recentCatalogEffect({
      upserts: [],
      removes: [],
      remove_files: [],
      non_file_paths: ["docs"],
    }).needsAuthoritativeRepair,
    shallowSubtreeRemovalNeedsRepair: recentCatalogEffect({
      upserts: [],
      removes: ["runs"],
      remove_files: [],
    }).needsAuthoritativeRepair,
    firstSentinelAfterSettledRequest: {
      requestDisposition: settledDisposition,
      sentinel: settledBaseline,
      reconnect: settledReconnect,
      repairPending: settledBeforeBaseline.continuity.pending(),
    },
    firstSentinelDuringRequest: {
      sentinel: activeBaseline,
      requestDisposition: preBaselineDisposition,
    },
    requestAfterFirstSentinel: {
      sentinel: inactiveBaseline,
      redundantRepairPending: requestAfterBaseline.continuity.pending(),
    },
    expiryDuringCommit: {
      requestDisposition: expiringDisposition,
      activeBeforeRender: activeDuringRender,
      expiryAction,
      repairPending: expiryDuringCommit.continuity.pending(),
    },
    cappedOverflow,
    retainedAfterOverflow: Array.from(cappedEntries.keys()),
    liveBatches: liveBatchMatrix,
    fixedWindowCoalescing: {
      secondAction: fixedWindowSecondAction,
      timerCount: fixedWindowTimerCount,
      repairs: fixedWindow.repairs,
      newerRequestAction: timerRaceAction,
      newerRequestDisposition: timerRaceDisposition,
    },
    failedRepairLifecycle: {
      initialRepairDelay,
      firstFailure,
      firstRetryDelay,
      coalescedRetry,
      timersAfterCoalescing,
      secondRetryDelay,
      terminalFailure,
      statusBeforeRecoverySignal,
      pendingBeforeRecoverySignal,
      recoverySignal,
      recoverySignalDelay,
      statusAfterRecoverySignal,
      recoveryFailure,
      recoveryRetryDelay,
      statuses: retryLifecycle.statuses,
    },
    cancellation: {
      pending: cancellation.continuity.pending(),
      status: cancellation.continuity.status(),
      lateFailure: lateCancelledFailure,
      statuses: cancellation.statuses,
    },
    successReset: {
      delayBeforeSuccess,
      statusAfterSuccess,
      delayAfterSuccess,
      status: successReset.continuity.status(),
      statuses: successReset.statuses,
    },
    integration,
  },
};

console.log(JSON.stringify(report, null, 2));
