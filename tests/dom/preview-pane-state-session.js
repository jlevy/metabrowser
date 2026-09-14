// Exact browserless session for the production preview-pane state machine.
//
// Every transition below calls the functions app.js calls at the same moment:
// the pane lifecycle for claims and placeholders, the fresh-response commit for
// a folder envelope, the fetch-rejection boundary, and the shared selection
// failure settlement. Nothing here restates their decisions.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const navigationPath = path.join(repoRoot, "src/metabrowser/static/navigation.js");
const sandbox = { Array, Error, Map, Number, Object, Promise, String, TypeError, URIError };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(navigationPath, "utf8"), sandbox, {
  filename: navigationPath,
});

const navigation = sandbox.MetabrowserNavigationRoute;

/** A plain-data view of one directive or snapshot, stable across realms. */
function plain(value) {
  return JSON.parse(JSON.stringify(value));
}

/** The same failure boundary app.js runs for an owned file selection. */
function settleFailure(pane, claim, pathName, error, options = {}) {
  const shown = [];
  const revalidated = [];
  const outcome = navigation.settleFileSelectionFailure({
    cached: options.cached === true,
    claim,
    error,
    isCurrent: () => options.current !== false,
    markForRevalidation: () => revalidated.push(pathName),
    pane,
    path: pathName,
    showError: (failure) => shown.push(plain(failure)),
  });
  return { outcome: plain(outcome), revalidated, shown };
}

function commitFolder(data) {
  const cache = new Map([[data.path, { kind: "text" }]]);
  const validators = new Map([[data.path, '"old"']]);
  const commit = navigation.commitFreshFileResponse({
    cacheFile: (fresh) => cache.set(data.path, fresh),
    cacheValidator: (etag) => validators.set(data.path, etag),
    data,
    etag: null,
    evictFile: () => cache.delete(data.path),
    evictValidator: () => validators.delete(data.path),
    isCurrent: () => true,
  });
  return { cacheRetained: cache.has(data.path), commit };
}

function httpError(detail, fields) {
  return Object.assign(new Error(detail), fields);
}

function rootLanding() {
  // `/` redirects to `/view/`, which parses to the served root: the landing
  // always selects a folder, so the shell ships a loading state, not a prompt.
  const pane = navigation.createPreviewPaneLifecycle();
  const shipped = plain(pane.placeholder(0));
  const target = plain(navigation.parse("/view/"));
  const claim = pane.claim("file", { folder: true, path: target.path });
  const whileLoading = plain(pane.placeholder(claim));
  const settled = pane.settle(claim, "content");
  return {
    afterSettle: plain(pane.placeholder(claim)),
    settled,
    shipped,
    snapshot: plain(pane.snapshot()),
    target,
    whileLoading,
  };
}

function loadingToContent() {
  const pane = navigation.createPreviewPaneLifecycle();
  const claim = pane.claim("file", { folder: false, path: "docs/guide.md" });
  const whileLoading = plain(pane.placeholder(claim));
  const settled = pane.settle(claim, "content");
  return {
    afterSettle: plain(pane.placeholder(claim)),
    settled,
    snapshot: plain(pane.snapshot()),
    whileLoading,
  };
}

function loadingToEmptyFolder() {
  // The complete envelope the server returns for a folder with no files.
  const envelope = {
    dir: { state: "complete", total_files: 0, total_size: 0 },
    kind: "folder",
    path: "empty",
    readme_path: "",
  };
  const pane = navigation.createPreviewPaneLifecycle();
  const claim = pane.claim("file", { folder: true, path: "empty" });
  const whileLoading = plain(pane.placeholder(claim));
  const response = commitFolder(envelope);
  const settled = pane.settle(claim, "content");
  return {
    afterSettle: plain(pane.placeholder(claim)),
    response,
    settled,
    snapshot: plain(pane.snapshot()),
    whileLoading,
  };
}

function panelSwitchDuringLoad() {
  // A navigation tab switch changes which list is visible, not what is
  // selected. It makes no claim, so the in-flight selection keeps the pane:
  // its loading state stays up and its response still lands.
  const pane = navigation.createPreviewPaneLifecycle();
  const claim = pane.claim("file", { folder: true, path: "big" });
  const beforeSwitch = plain(pane.placeholder(claim));
  const claimCurrentAfterSwitch = pane.isCurrent(claim);
  const afterSwitch = plain(pane.placeholder(claim));
  const settled = pane.settle(claim, "content");
  const afterSettle = plain(pane.snapshot());

  // A different producer claiming the pane is what supersedes a selection.
  const superseded = navigation.createPreviewPaneLifecycle();
  const fileClaim = superseded.claim("file", { folder: false, path: "slow.md" });
  const gitClaim = superseded.claim("git");
  return {
    afterSettle,
    afterSwitch,
    beforeSwitch,
    claimCurrentAfterSwitch,
    settled,
    supersededByAnotherOwner: {
      fileClaimCurrent: superseded.isCurrent(fileClaim),
      gitClaimCurrent: superseded.isCurrent(gitClaim),
      lateFilePlaceholder: plain(superseded.placeholder(fileClaim)),
      lateFileSettled: superseded.settle(fileClaim, "content"),
      reconnectRetry: plain(superseded.reconnected()),
      snapshot: plain(superseded.snapshot()),
    },
  };
}

function landingWithoutSelection() {
  // A location that selects nothing: no claim is loading, so the prompt is
  // the one honest thing to show.
  const pane = navigation.createPreviewPaneLifecycle();
  const loading = pane.claim("file", { folder: false, path: "abandoned.md" });
  const landing = pane.claim("none");
  const idle = plain(pane.placeholder(landing));

  // A /commit/ route whose Git panel never claims the pane (not a repository,
  // or its restore failed before selecting) settles to the same state.
  const commitRoute = navigation.createPreviewPaneLifecycle();
  const unclaimed = plain(commitRoute.settleUnclaimed());
  const afterUnclaimed = plain(commitRoute.snapshot());

  // Once anything has claimed the pane, that owner decides what it shows.
  const restored = navigation.createPreviewPaneLifecycle();
  restored.claim("git");
  const unclaimedAfterOwner = plain(restored.settleUnclaimed());
  return {
    abandonedLoadCurrent: pane.isCurrent(loading),
    abandonedLoadSettled: pane.settle(loading, "content"),
    commitRouteWithoutOwner: { snapshot: afterUnclaimed, unclaimed },
    commitRouteWithOwner: { snapshot: plain(restored.snapshot()), unclaimed: unclaimedAfterOwner },
    idle,
    snapshot: plain(pane.snapshot()),
  };
}

function failures() {
  const abort = Object.assign(new Error("superseded"), { name: "AbortError" });
  const refused = navigation.requestFailure(new TypeError("Failed to fetch"));

  const unreachablePane = navigation.createPreviewPaneLifecycle();
  const unreachableClaim = unreachablePane.claim("file", { folder: true, path: "empty" });
  const unreachable = settleFailure(unreachablePane, unreachableClaim, "empty", refused, {
    cached: true,
  });

  const notFoundPane = navigation.createPreviewPaneLifecycle();
  const notFoundClaim = notFoundPane.claim("file", { folder: false, path: "gone.md" });
  const notFound = settleFailure(
    notFoundPane,
    notFoundClaim,
    "gone.md",
    httpError("This file is no longer available.", {
      notFound: true,
      summary: "Could not open this file.",
    }),
  );

  const serverErrorPane = navigation.createPreviewPaneLifecycle();
  const serverErrorClaim = serverErrorPane.claim("file", { folder: false, path: "broken.md" });
  const serverError = settleFailure(
    serverErrorPane,
    serverErrorClaim,
    "broken.md",
    httpError("The request failed (HTTP 500).", { summary: "Could not open this file." }),
  );

  // A renderer bug can throw a TypeError too. Only a rejected fetch is marked,
  // so it is still reported as a failure to open the file.
  const rendererPane = navigation.createPreviewPaneLifecycle();
  const rendererClaim = rendererPane.claim("file", { folder: false, path: "odd.md" });
  const renderer = settleFailure(
    rendererPane,
    rendererClaim,
    "odd.md",
    new TypeError("Cannot read properties of undefined (reading 'views')"),
  );

  const abortPane = navigation.createPreviewPaneLifecycle();
  const abortClaim = abortPane.claim("file", { folder: false, path: "left.md" });
  const aborted = settleFailure(abortPane, abortClaim, "left.md", navigation.requestFailure(abort));

  return {
    abortPassesThrough: navigation.requestFailure(abort) === abort,
    aborted: { ...aborted, snapshot: plain(abortPane.snapshot()) },
    fetchRejectionName: refused.name,
    fetchRejectionPreservesCause: refused.cause?.message ?? null,
    httpNotFound: {
      ...notFound,
      reconnectRetry: plain(notFoundPane.reconnected()),
      snapshot: plain(notFoundPane.snapshot()),
    },
    httpServerError: { ...serverError, snapshot: plain(serverErrorPane.snapshot()) },
    markedOnce: navigation.requestFailure(refused) === refused,
    quickFile: {
      opaqueThrow: plain(navigation.openFailureOutcome(new Error("unexpected"))),
      unreachableThrow: plain(navigation.openFailureOutcome(refused)),
    },
    rendererTypeError: { ...renderer, snapshot: plain(rendererPane.snapshot()) },
    serverUnreachable: { ...unreachable, snapshot: plain(unreachablePane.snapshot()) },
  };
}

function recoveryOnReconnect() {
  const pane = navigation.createPreviewPaneLifecycle();
  const beforeFailure = plain(pane.reconnected());
  const failed = pane.claim("file", { folder: true, path: "empty", viewId: "overview" });
  settleFailure(pane, failed, "empty", navigation.requestFailure(new TypeError("Failed to fetch")));
  const retry = plain(pane.reconnected());

  // The shell re-runs the selection it was told to retry, which claims again.
  const retried = pane.claim("file", retry);
  const duplicateOpen = plain(pane.reconnected());
  const whileRetrying = plain(pane.placeholder(retried));
  const settled = pane.settle(retried, "content");

  // A failure the reader has since navigated away from is not retried.
  const movedOn = navigation.createPreviewPaneLifecycle();
  const lost = movedOn.claim("file", { folder: false, path: "notes.md" });
  settleFailure(movedOn, lost, "notes.md", navigation.requestFailure(new TypeError("offline")));
  movedOn.claim("none");
  return {
    afterRecovery: plain(pane.reconnected()),
    beforeFailure,
    duplicateOpen,
    failedLoadCurrent: pane.isCurrent(failed),
    movedOnRetry: plain(movedOn.reconnected()),
    retry,
    settled,
    snapshot: plain(pane.snapshot()),
    whileRetrying,
  };
}

process.stdout.write(
  `${JSON.stringify(
    {
      rootLanding: rootLanding(),
      loadingToContent: loadingToContent(),
      loadingToEmptyFolder: loadingToEmptyFolder(),
      panelSwitchDuringLoad: panelSwitchDuringLoad(),
      landingWithoutSelection: landingWithoutSelection(),
      failures: failures(),
      recoveryOnReconnect: recoveryOnReconnect(),
    },
    null,
    2,
  )}\n`,
);
