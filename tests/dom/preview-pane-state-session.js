// Exact browserless session for the production preview-pane state machine.
//
// The module scenarios call the pane lifecycle and failure classifiers in
// navigation.js directly. The `shell` scenarios run the app.js functions that
// compose them (selectFile, applyNavigationTarget, navigateToPath,
// activateNavPanel, the inventory stream's onopen, and the startup settle),
// extracted verbatim and executed with the real navigation module and
// controller, so that wiring cannot regress behind a source-string assertion.
// Only the DOM, the network, the renderer, and unrelated shell services are
// doubles. Nothing here restates a decision the production code makes.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const navigationPath = path.join(repoRoot, "src/metabrowser/static/navigation.js");
const navigationSource = fs.readFileSync(navigationPath, "utf8");
const appPath = path.join(repoRoot, "src/metabrowser/static/app.js");
const appSource = fs.readFileSync(appPath, "utf8");

// Shared with every sandbox so `instanceof` agrees across the realm boundary.
const BUILTINS = {
  AbortController,
  Array,
  Error,
  Map,
  Number,
  Object,
  Promise,
  Set,
  String,
  SyntaxError,
  TypeError,
  URIError,
};

/** Load navigation.js into a fresh global, as the shell's script tag does. */
function loadNavigation(globals) {
  const sandbox = { ...BUILTINS, ...globals };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(navigationSource, sandbox, { filename: navigationPath });
  return sandbox;
}

const navigation = loadNavigation({}).MetabrowserNavigationRoute;

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

// ── Module scenarios ──────────────────────────────────────────

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

function supersededByAnotherOwner() {
  // A different producer claiming the pane is what supersedes a selection.
  const pane = navigation.createPreviewPaneLifecycle();
  const fileClaim = pane.claim("file", { folder: false, path: "slow.md" });
  const gitClaim = pane.claim("git");
  return {
    fileClaimCurrent: pane.isCurrent(fileClaim),
    gitClaimCurrent: pane.isCurrent(gitClaim),
    lateFilePlaceholder: plain(pane.placeholder(fileClaim)),
    lateFileSettled: pane.settle(fileClaim, "content"),
    reconnectRetry: plain(pane.reconnected()),
    snapshot: plain(pane.snapshot()),
  };
}

function holdsSelection() {
  // Re-opening a path only delivers its fragment while the pane holds it.
  const pane = navigation.createPreviewPaneLifecycle();
  const beforeAnyClaim = pane.holds("notes.md");
  const loading = pane.claim("file", { folder: false, path: "notes.md" });
  const whileLoading = pane.holds("notes.md");
  const otherPathWhileLoading = pane.holds("other.md");
  pane.settle(loading, "content");
  const withContent = pane.holds("notes.md");
  const failed = pane.claim("file", { folder: false, path: "notes.md" });
  pane.settle(failed, "error");
  const afterFileError = pane.holds("notes.md");
  const lost = pane.claim("file", { folder: false, path: "notes.md" });
  pane.settle(lost, "unreachable");
  const afterUnreachable = pane.holds("notes.md");
  const shown = pane.claim("file", { folder: false, path: "notes.md" });
  pane.settle(shown, "content");
  pane.claim("git");
  return {
    afterFileError,
    afterGitClaim: pane.holds("notes.md"),
    afterUnreachable,
    beforeAnyClaim,
    otherPathWhileLoading,
    whileLoading,
    withContent,
  };
}

function landingWithoutSelection() {
  // A location that selects nothing: no claim is loading, so the prompt is
  // the one honest thing to show.
  const pane = navigation.createPreviewPaneLifecycle();
  const loading = pane.claim("file", { folder: false, path: "abandoned.md" });
  const landing = pane.claim("none");
  const idle = plain(pane.placeholder(landing));

  // Startup that no producer claimed settles to the same state.
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

  // A renderer bug can throw a TypeError too. Only a rejected fetch or body
  // read is marked, so it is still reported as a failure to open the file.
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

  const malformed = new SyntaxError("Unexpected token < in JSON at position 0");
  const interrupted = navigation.responseBodyFailure(new TypeError("terminated"));
  return {
    abortPassesThrough: navigation.requestFailure(abort) === abort,
    aborted: { ...aborted, snapshot: plain(abortPane.snapshot()) },
    bodyRead: {
      abortPassesThrough: navigation.responseBodyFailure(abort) === abort,
      interruptedName: interrupted.name,
      interruptedPreservesCause: interrupted.cause?.message ?? null,
      malformedJsonPassesThrough: navigation.responseBodyFailure(malformed) === malformed,
      markedOnce: navigation.responseBodyFailure(refused) === refused,
    },
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

// ── Shell scenarios: the real app.js wiring ───────────────────

/** One app.js declaration, bounded by its closing line at column zero. */
function appDeclaration(pattern, label) {
  const match = appSource.match(pattern);
  if (!match) {
    throw new Error(`app.js ${label} is not extractable`);
  }
  return match[0];
}

const SHELL_FUNCTIONS = [
  "esc",
  "previewErrorHtml",
  "responseErrorDetail",
  "responseErrorSummary",
  "boundMapSize",
  "cancelPendingFilePreviewStage",
  "clearPreviewNavigationState",
  "disposePullRequestPage",
  "claimPreview",
  "isPreviewClaimCurrent",
  "previewPlaceholderHtml",
  "beginPreviewNavigation",
  "endPreviewNavigation",
  "activateNavPanel",
  "fileSelectionFailureOutcome",
  "beginViewCompositionLoad",
  "selectFile",
  "openedFileOutcome",
  "_createInventoryEventSource",
  "showNavigationLanding",
  "settleUnclaimedPreview",
  "settleCommitRoutePreview",
  "retryUnreachablePreview",
  "deliverNavigationFragment",
  "applyNavigationTarget",
  "navigateToPath",
];

const shellSource = [
  appDeclaration(/^var previewPane = [^\n]*;$/m, "preview pane"),
  appDeclaration(/^var pullRequestPage = null;$/m, "pull-request page"),
  appDeclaration(/^var navigationController = [\s\S]*?^\}\);$/m, "navigation controller"),
  ...SHELL_FUNCTIONS.map((name) =>
    appDeclaration(
      new RegExp(`^(?:async )?function ${name}\\([^)]*\\) \\{[\\s\\S]*?^\\}`, "m"),
      `function ${name}`,
    ),
  ),
].join("\n\n");

function fakeElement(fields = {}) {
  const attributes = new Map();
  const classes = new Set();
  return {
    classList: {
      add: (name) => classes.add(name),
      contains: (name) => classes.has(name),
      remove: (name) => classes.delete(name),
      toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)),
    },
    dataset: {},
    get firstElementChild() {
      const match = /^<[a-z]+(?: class="([^"]*)")?/.exec(this.innerHTML);
      if (!match) {
        return null;
      }
      const names = new Set((match[1] || "").split(/\s+/).filter(Boolean));
      return { classList: { contains: (name) => names.has(name) } };
    },
    getAttribute: (name) => (attributes.has(name) ? attributes.get(name) : null),
    hasAttribute: (name) => attributes.has(name),
    innerHTML: "",
    removeAttribute: (name) => attributes.delete(name),
    setAttribute: (name, value) => attributes.set(name, String(value)),
    style: {},
    ...fields,
  };
}

function jsonResponse(data) {
  return {
    headers: { get: () => null },
    json: async () => data,
    ok: true,
    status: 200,
    text: async () => JSON.stringify(data),
  };
}

function deferred() {
  let resolve;
  const promise = new Promise((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

/** Let every pending promise chain in the shell run to completion. */
async function settle() {
  for (let round = 0; round < 10; round += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/**
 * A shell booted at one pathname. `network(path)` answers each `/api/file`
 * request; the renderer double paints a view only for a current claim.
 */
function createShell(pathname, network) {
  const preview = fakeElement();
  const elements = new Map([
    ["preview-pane", preview],
    ["nav-filter-bar", fakeElement()],
  ]);
  const navBar = fakeElement();
  const tabButtons = ["files", "git"].map((tab) => fakeElement({ dataset: { tab } }));
  const tabPanels = ["files", "git"].map((tab) => fakeElement({ dataset: { tabContent: tab } }));
  const fetched = [];
  const panelShows = [];
  const timers = [];
  const sources = [];
  const counters = { catalogFeedStarts: 0, fragments: 0, paletteReconnects: 0 };
  const location = { hash: "", pathname, search: "" };
  const moveTo = (_state, _title, href) => {
    const url = new URL(href, "http://metabrowser.test");
    location.pathname = url.pathname;
    location.search = url.search;
    location.hash = url.hash;
  };

  const sandbox = loadNavigation({
    CustomEvent: class {
      constructor(type, init) {
        this.type = type;
        this.detail = init?.detail;
      }
    },
    addEventListener() {},
    dispatchEvent(event) {
      if (event.type === "metabrowser:navigation-fragment") {
        counters.fragments += 1;
      }
      return true;
    },
    document: { getElementById: (id) => elements.get(id) ?? null },
    history: { pushState: moveTo, replaceState: moveTo },
    location,
    removeEventListener() {},
    // The navigation bar activateNavPanel toggles.
    navPanels: [
      { id: "files", onFirstShow: null },
      {
        id: "git",
        onFirstShow: () => panelShows.push("git first show"),
        onShow: () => panelShows.push("git show"),
      },
    ],
    navPanelsShown: new Set(["files"]),
    navScrollShadowUpdate: null,
    queryHtml: (selector) => (selector === ".nav-tab-bar" ? navBar : null),
    queryHtmlAll: (selector) =>
      selector === ".tab-btn" ? tabButtons : selector === "[data-tab-content]" ? tabPanels : [],
    treePane: fakeElement(),
    // Selection state and caches selectFile reads.
    CACHE_MAX: 30,
    ETAG_REVALIDATE_MAX: 512,
    LOADING_INDICATOR_DELAY_MS: 120,
    activeFiles: new Set(),
    currentPath: null,
    fileCache: new Map(),
    fileETags: new Map(),
    filePreviewClaim: 0,
    knownFileCatalog: null,
    loadingIndicatorTimer: null,
    pendingFilePreviewStageCleanup: null,
    selectFileAbortController: null,
    // The delayed spinner runs only when a scenario says that much time passed.
    clearTimeout: (id) => {
      if (id) {
        timers[id - 1] = null;
      }
    },
    setTimeout: (callback) => timers.push(callback),
    // Services outside the pane's decisions.
    _perf: { measureAsync: (_label, run) => run() },
    cachePut: (map, key, value) => map.set(key, value),
    closeLiveStream() {},
    disposeActivePluginViews() {},
    evictFileCacheMetadata() {},
    fetch: (url) => {
      const requested = decodeURIComponent(String(url).replace("/api/file?path=", ""));
      fetched.push(requested);
      return network(requested);
    },
    loadViewComposition: async () => null,
    maybeOpenLiveStream() {},
    renderFile: async (data, _viewId, claim) => {
      if (!sandbox.isPreviewClaimCurrent(claim)) {
        return false;
      }
      preview.innerHTML = `<article class="rendered-view">${data.kind} ${data.path}</article>`;
      return true;
    },
    resetTextChunkGrowth() {},
    responsePerfMeta: () => ({}),
    revealInTree: async () => false,
    setSelectedPath() {},
    settleHoverPrefetchForSelection: async () => {},
    stopFolderHeaderSubscription() {},
    // The inventory stream and the services its open restarts.
    EventSource: class {
      constructor(url) {
        this.url = url;
        sources.push(this);
      }
      addEventListener() {}
      close() {}
    },
    _cancelEsStableReset() {},
    _scheduleEsStableReset() {},
    _scheduleInventoryReconnect() {},
    catalogFeedCanStart: false,
    inventoryEventSource: null,
    quickFileCatalogFeed: {
      start: () => {
        counters.catalogFeedStarts += 1;
      },
    },
    quickFilePalette: {
      reconnected: () => {
        counters.paletteReconnects += 1;
      },
    },
  });
  sandbox.fileNeedsRevalidate =
    sandbox.MetabrowserNavigationRoute.createFileRevalidationTracker(512);
  vm.runInContext(shellSource, sandbox, { filename: "app.js (preview pane functions)" });
  // What server.py ships in the pane before any script runs.
  preview.innerHTML = sandbox.previewPlaceholderHtml(sandbox.previewPane.placeholder(0));

  /** The pane's lifecycle state and what it paints, as one reader-level line. */
  function pane() {
    const html = preview.innerHTML;
    const classes = /^<[a-z]+(?: class="([^"]*)")?/.exec(html)?.[1] ?? "";
    const text = html
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    return { ...plain(sandbox.previewPane.snapshot()), shows: `${classes}: ${text}` };
  }

  /** An open outcome without its DOM focus target. */
  function outcome(result) {
    const { focusTarget, ...rest } = result;
    return { ...plain(rest), focusesPreview: focusTarget === preview };
  }

  return {
    /** The Git panel claims the pane and paints a commit, as git-panel.js does. */
    claimGit(revision) {
      const claim = sandbox.claimPreview("git");
      preview.innerHTML = `<article class="git-commit">${revision}</article>`;
      return claim;
    },
    counters,
    /** Let the loading-indicator delay elapse. */
    elapseLoadingDelay() {
      for (const [index, callback] of timers.entries()) {
        timers[index] = null;
        callback?.();
      }
    },
    fetches: (requested) => fetched.filter((entry) => entry === requested).length,
    outcome,
    pane,
    panelShows,
    sandbox,
    sources,
    tabs: () => tabPanels.map((panel) => `${panel.dataset.tabContent}:${panel.style.display}`),
  };
}

const refusedFetch = () => Promise.reject(new TypeError("Failed to fetch"));

async function tabSwitchDuringLoad() {
  // A navigation tab switch changes which list is visible, not what is
  // selected, so the folder still loading underneath keeps the pane and lands.
  const response = deferred();
  const shell = createShell("/view/big/", () => response.promise);
  const started = shell.sandbox.navigationController.start();
  await settle();
  const loading = shell.pane();
  shell.sandbox.activateNavPanel("git");
  const onGitTab = { pane: shell.pane(), tabs: shell.tabs() };
  shell.sandbox.activateNavPanel("files");
  const backOnFilesTab = { pane: shell.pane(), tabs: shell.tabs() };
  response.resolve(jsonResponse({ kind: "folder", path: "big" }));
  await started;
  await settle();
  return {
    backOnFilesTab,
    landed: shell.pane(),
    loading,
    onGitTab,
    panelShows: shell.panelShows,
  };
}

async function reselectAfterFailure() {
  // Opening the path a failed selection named again is how a reader retries,
  // from the tree or from Quick File: it loads again. Re-opening a path the
  // pane already shows only delivers the fragment.
  const answers = new Map([
    ["", [() => Promise.resolve(jsonResponse({ kind: "folder", path: "" }))]],
    [
      "notes.md",
      [refusedFetch, () => Promise.resolve(jsonResponse({ kind: "text", path: "notes.md" }))],
    ],
    [
      "broken.md",
      [
        () =>
          Promise.resolve({
            headers: { get: () => null },
            ok: false,
            status: 500,
            text: async () => "",
          }),
        () => Promise.resolve(jsonResponse({ kind: "text", path: "broken.md" })),
      ],
    ],
  ]);
  const shell = createShell("/view/", (requested) => answers.get(requested).shift()());
  await shell.sandbox.navigationController.start();
  await settle();

  async function open(requested) {
    const result = await shell.sandbox.navigateToPath(requested);
    await settle();
    return {
      fetches: shell.fetches(requested),
      fragments: shell.counters.fragments,
      outcome: shell.outcome(result),
      pane: shell.pane(),
    };
  }

  const unreachable = await open("notes.md");
  const retriedUnreachable = await open("notes.md");
  const reopenedContent = await open("notes.md");
  const fileError = await open("broken.md");
  const retriedFileError = await open("broken.md");
  await open("notes.md");
  // A Git commit replaced the file in the pane; opening the file shows it
  // again, from the payload the earlier open cached.
  shell.claimGit("abc123");
  const afterGitClaim = await open("notes.md");
  return {
    afterGitClaim,
    fileError,
    reopenedContent,
    retriedFileError,
    retriedUnreachable,
    unreachable,
  };
}

async function bodyReadFailure() {
  // `fetch` resolves at the headers. A server that stops while the body is
  // still streaming rejects the read: that is the same lost connection. A body
  // that arrives but is not JSON is still a response problem.
  const answers = new Map([
    ["", () => Promise.resolve(jsonResponse({ kind: "folder", path: "" }))],
    [
      "big.log",
      () =>
        Promise.resolve({
          ...jsonResponse({}),
          json: () => Promise.reject(new TypeError("terminated")),
        }),
    ],
    [
      "failing.md",
      () =>
        Promise.resolve({
          headers: { get: () => null },
          ok: false,
          status: 500,
          text: () => Promise.reject(new TypeError("terminated")),
        }),
    ],
    [
      "garbled.json",
      () =>
        Promise.resolve({
          ...jsonResponse({}),
          json: () => Promise.reject(new SyntaxError("Unexpected token < in JSON at position 0")),
        }),
    ],
  ]);
  const shell = createShell("/view/", (requested) => answers.get(requested)());
  await shell.sandbox.navigationController.start();
  await settle();
  const results = {};
  for (const [key, requested] of [
    ["interruptedJsonBody", "big.log"],
    ["interruptedErrorBody", "failing.md"],
    ["malformedJson", "garbled.json"],
  ]) {
    const result = await shell.sandbox.navigateToPath(requested);
    await settle();
    results[key] = {
      outcome: shell.outcome(result),
      pane: shell.pane(),
      reconnectRetry: plain(shell.sandbox.previewPane.reconnected()),
    };
  }
  return results;
}

async function reconnectRetry() {
  // The inventory stream's real onopen retries only a selection that failed
  // because the server could not be reached.
  let serverUp = false;
  const retried = deferred();
  const shell = createShell("/view/empty/", () => (serverUp ? retried.promise : refusedFetch()));
  await shell.sandbox.navigationController.start();
  await settle();
  const failed = shell.pane();
  shell.sandbox._createInventoryEventSource();
  const stream = shell.sources[0];
  serverUp = true;
  // selectFile claims before its first await, so the pane is loading again
  // before onopen returns and a duplicate open finds nothing to retry.
  stream.onopen();
  const claimedByOpen = shell.pane();
  stream.onopen();
  await settle();
  shell.elapseLoadingDelay();
  const whileRetrying = shell.pane();
  retried.resolve(jsonResponse({ kind: "folder", path: "empty" }));
  await settle();
  const recovered = shell.pane();

  // A Git commit claimed the pane after the failure: nothing to retry.
  let gitServerUp = false;
  const gitShell = createShell("/view/notes.md", (requested) =>
    gitServerUp ? Promise.resolve(jsonResponse({ kind: "text", path: requested })) : refusedFetch(),
  );
  await gitShell.sandbox.navigationController.start();
  await settle();
  gitShell.claimGit("abc123");
  gitShell.sandbox._createInventoryEventSource();
  gitServerUp = true;
  gitShell.sources[0].onopen();
  await settle();

  return {
    afterGitClaim: { fetches: gitShell.fetches("notes.md"), pane: gitShell.pane() },
    catalogFeedStarts: shell.counters.catalogFeedStarts,
    claimedByOpen,
    failed,
    fetchesForFailedFolder: shell.fetches("empty"),
    paletteReconnects: shell.counters.paletteReconnects,
    recovered,
    streamUrl: stream.url,
    whileRetrying,
  };
}

async function startupSettle() {
  // The startup settle runs once the shell tools, and with them the Git panel,
  // have settled. Only a /commit/ route waits on that panel to select something.
  const noOwner = createShell("/commit/abc123", refusedFetch);
  await noOwner.sandbox.navigationController.start();
  noOwner.sandbox.settleCommitRoutePreview();

  const gitOwner = createShell("/commit/abc123", refusedFetch);
  await gitOwner.sandbox.navigationController.start();
  gitOwner.claimGit("abc123");
  gitOwner.sandbox.settleCommitRoutePreview();

  // A /view/ route whose selection has not claimed the pane yet keeps the
  // shipped loading state, then its own selection settles it.
  const viewRoute = createShell("/view/docs/guide.md", (requested) =>
    Promise.resolve(jsonResponse({ kind: "text", path: requested })),
  );
  viewRoute.sandbox.settleCommitRoutePreview();
  const viewBeforeSelection = viewRoute.pane();
  await viewRoute.sandbox.navigationController.start();
  await settle();

  // A location that selects nothing lands on the prompt.
  const nowhere = createShell("/elsewhere", refusedFetch);
  await nowhere.sandbox.navigationController.start();

  return {
    commitRouteWithGitOwner: gitOwner.pane(),
    commitRouteWithoutOwner: noOwner.pane(),
    locationWithoutSelection: nowhere.pane(),
    viewRoute: { afterSelection: viewRoute.pane(), beforeSelection: viewBeforeSelection },
  };
}

async function shell() {
  const shipped = createShell("/view/", refusedFetch);
  return {
    shippedPlaceholderHtml: shipped.sandbox.previewPlaceholderHtml(
      shipped.sandbox.previewPane.placeholder(0),
    ),
    tabSwitchDuringLoad: await tabSwitchDuringLoad(),
    reselectAfterFailure: await reselectAfterFailure(),
    bodyReadFailure: await bodyReadFailure(),
    reconnectRetry: await reconnectRetry(),
    startupSettle: await startupSettle(),
  };
}

async function main() {
  const report = {
    rootLanding: rootLanding(),
    loadingToContent: loadingToContent(),
    loadingToEmptyFolder: loadingToEmptyFolder(),
    supersededByAnotherOwner: supersededByAnotherOwner(),
    holdsSelection: holdsSelection(),
    landingWithoutSelection: landingWithoutSelection(),
    failures: failures(),
    shell: await shell(),
  };
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error?.stack || error}\n`);
  process.exitCode = 1;
});
