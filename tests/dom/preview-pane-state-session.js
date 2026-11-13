// Exact browserless session for the production preview-pane state machine.
//
// The module scenarios call the pane lifecycle and failure classifiers in
// navigation.js directly. The `shell` scenarios run the app.js functions that
// compose them (selectFile, applyNavigationTarget, navigateToPath, openTreeRow,
// activateNavPanel, the inventory stream's onopen, and the startup settle),
// extracted verbatim and executed with the real navigation module and
// controller, so that wiring cannot regress behind a source-string assertion.
// The asset loader and the plugin SDK are the production scripts too, and what
// they fetch on demand -- the view compositor, the SDK's view helpers with the
// line anchors, the pull-request routes -- is the production file, delivered a
// turn after it is asked for or refused, as a scenario says.
// Only the DOM, the network, the renderer, and unrelated shell services are
// doubles. Nothing here restates a decision the production code makes.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const navigationPath = path.join(staticDir, "navigation.js");
const navigationSource = fs.readFileSync(navigationPath, "utf8");
const appPath = path.join(staticDir, "app.js");
const appSource = fs.readFileSync(appPath, "utf8");
// The startup scripts the on-demand loads below run through, in the shell's order
// around navigation.js, which loadNavigation runs first.
const STARTUP_SCRIPTS = [
  "asset-loader.js",
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "plugin-sdk.js",
];
// What the shell publishes as on-demand bundles and these scenarios reach: the view
// compositor, the SDK's view helpers with the line anchors applyNavigationTarget
// reads an address with, and the pull-request page's routes and host.
const ASSET_BUNDLES = {
  mustache: [{ src: "/static/vendor/mustache.min.js", provides: "Mustache" }],
  "view-composition": [{ src: "/static/view-composition.js" }],
  "sdk-views": [{ src: "/static/plugin-sdk-views.js", provides: "MetabrowserSourceLineAnchors" }],
  "pull-route": [{ src: "/static/pull-route.js", provides: "MetabrowserPullRoute" }],
  "main-tabs": [{ src: "/static/main-tabs.js", provides: "MetabrowserMainTabs" }],
  "shell-tools": [{ src: "/static/main-tabs.js", provides: "MetabrowserMainTabs" }],
};

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
  "claimPreview",
  "isPreviewClaimCurrent",
  "previewPlaceholderHtml",
  "beginPreviewNavigation",
  "endPreviewNavigation",
  "finishRetainedPullPage",
  "stagePreviewNode",
  "createFilePreviewStage",
  "isGitHistoryLanding",
  "cancelMainTabPreview",
  "attachMainTabs",
  "initNavTabs",
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
  "showPreviewTab",
  "renderPreviewHtml",
  "loadViewComposition",
  "isPullAddress",
  "loadPullPageHost",
  "openQuickSearchPull",
  "showPullPageLoadFailure",
  "pullPageHostDeps",
  "applyPullHistoryLanding",
  "addressedView",
  "applyNavigationTarget",
  "navigateToPath",
  "openTreeRow",
];

const shellSource = [
  appDeclaration(/^var previewPane = [^\n]*;$/m, "preview pane"),
  appDeclaration(/^var PULL_ROUTE_PREFIX = [^\n]*;$/m, "pull-request route prefix"),
  appDeclaration(/^var PULLS_ROUTE = [^\n]*;$/m, "pull-request list route"),
  // The host is created on demand, when an address under /pull/ is opened; none of
  // these states opens one, so the pane's claim finds no page to dispose.
  appDeclaration(/^var pullPageHost = null;$/m, "pull-request page host"),
  appDeclaration(/^var retainedPullPageDispose = null;$/m, "retained pull-request finalizer"),
  appDeclaration(/^var pluginViewLifecycle = null;$/m, "plugin view lifecycle"),
  appDeclaration(/^var navigationController = [\s\S]*?^\}\);$/m, "navigation controller"),
  ...SHELL_FUNCTIONS.map((name) =>
    appDeclaration(
      new RegExp(`^(?:async )?function ${name}\\([^)]*\\) \\{[\\s\\S]*?^\\}`, "m"),
      `function ${name}`,
    ),
  ),
].join("\n\n");

// What makes a stand-in element a live shortcut target to the registry.
const LIVE_TARGET = Object.freeze({
  checkVisibility: () => true,
  isConnected: true,
  parentElement: null,
});

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
      const match = /^<[a-z]+(?: class="([^"]*)")?[^>]*>/.exec(this.innerHTML);
      if (!match) {
        return null;
      }
      const names = new Set((match[1] || "").split(/\s+/).filter(Boolean));
      return {
        classList: { contains: (name) => names.has(name) },
        hasAttribute: (name) => match[0].includes(` ${name}=`),
      };
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
 *
 * `options.startupScripts` names what the server adds to this address's shell, as
 * pull-route.js on a pull-request address. `options.refused` is the set of script
 * names the network refuses; a scenario empties it when the server answers again.
 * `options.revealInTree` stands in for revealing the opened row, which takes tree
 * requests of its own.
 */
function createShell(pathname, network, options = {}) {
  /** @type {Set<string>} */
  const refused = options.refused ?? new Set();
  /** @type {string[]} */
  const renderedViews = [];
  // The shown file's Source tab, in its bar; selecting it is the tab's own path,
  // selectPreviewTab, which a click and a key share.
  /** @type {string[]} */
  const tabClicks = [];
  const tabBar = fakeElement();
  const sourceTab = fakeElement({ parentElement: tabBar });
  const preview = fakeElement();
  const elements = new Map([
    ["preview-pane", preview],
    ["nav-filter-bar", fakeElement()],
  ]);
  const scroller = options.scroller ?? fakeElement({ scrollTop: 0 });
  const panelIds = ["files"];
  // `gitDrawn` is the Commits tab the server draws at a repository's root, which
  // discovery has not registered.
  if (!options.withoutGit || options.gitDrawn) {
    panelIds.push("git");
  }
  if (options.pulls) {
    panelIds.push("pulls");
  }
  // A tab button is its digit's target, which the registry reads as live: connected,
  // outside any inert subtree, and visible.
  const tabButtons = panelIds.map((tab) =>
    fakeElement({
      dataset: { tab },
      focus() {},
      remove() {
        tabButtons.splice(tabButtons.indexOf(this), 1);
      },
      ...LIVE_TARGET,
    }),
  );
  // The tab the server draws in front: Pulls at its addresses, Commits at a commit's.
  const initialPanel =
    options.pulls && pathname.startsWith("/pull")
      ? "pulls"
      : pathname.startsWith("/commit/") && panelIds.includes("git")
        ? "git"
        : "files";
  const tabPanels = panelIds.map((tab) =>
    fakeElement({
      dataset: { tabContent: tab },
      style: { display: tab === initialPanel ? "" : "none" },
    }),
  );
  // The navigation's toolbar slot: one toolbar per tab the server draws, the one in front shown.
  const toolbars = panelIds.map((tab) =>
    fakeElement({ dataset: { navToolbar: tab }, hidden: tab !== initialPanel }),
  );
  /** @param {any} toolbar The Files bar has its own id; every other toolbar is `nav-toolbar-<tab>`. */
  const slotToolbar = (toolbar) => {
    toolbar.querySelector ??= () => null;
    const id = toolbar.id || `nav-toolbar-${toolbar.dataset.navToolbar}`;
    if (toolbar.dataset.navToolbar !== "files") {
      elements.set(id, toolbar);
    }
    toolbar.remove = () => {
      toolbars.splice(toolbars.indexOf(toolbar), 1);
      elements.delete(id);
    };
  };
  for (const toolbar of toolbars) {
    slotToolbar(toolbar);
  }
  scroller.querySelector = () => ({ remove() {} });
  // A toolbar main-tabs.js adds for a tab the server did not draw goes into the slot.
  scroller.before = (toolbar) => {
    toolbars.push(toolbar);
    slotToolbar(toolbar);
  };
  scroller.querySelectorAll = () => tabPanels;
  elements.set("tree-content", scroller);
  const previewTab = fakeElement({ dataset: { tabContent: "source" }, style: { display: "" } });
  for (const button of tabButtons) {
    button.setAttribute("data-tab", button.dataset.tab);
    button.classList.toggle("active", button.dataset.tab === initialPanel);
    button.closest = () => button;
  }
  let tabClick;
  const navBar = fakeElement({
    insertBefore(button, next) {
      tabButtons.splice(next ? tabButtons.indexOf(next) : tabButtons.length, 0, button);
    },
    addEventListener(_type, listener) {
      tabClick = listener;
    },
    querySelectorAll: () => tabButtons,
    querySelector: (selector) =>
      tabButtons.find((btn) =>
        selector === ".tab-btn.active"
          ? btn.classList.contains("active")
          : selector === `.tab-btn[data-tab="${btn.dataset.tab}"]`,
      ) ?? null,
  });
  const fetched = [];
  const panelShows = [];
  const timers = [];
  const sources = [];
  const counters = { catalogFeedStarts: 0, fragments: 0, paletteReconnects: 0 };
  // Every script the page asks for after it started, in order.
  /** @type {string[]} */
  const scriptRequests = [];
  const location = {
    hash: options.hash ?? "",
    origin: "http://metabrowser.test",
    pathname,
    search: "",
  };

  function runScript(name) {
    const filepath = path.join(staticDir, name);
    vm.runInContext(fs.readFileSync(filepath, "utf8"), sandbox, { filename: filepath });
  }

  /** A <script> the page appended: the production file a turn later, or a refusal. */
  function requestScript(script) {
    const name = String(script.src).replace("/static/", "");
    scriptRequests.push(name);
    function respond() {
      if (refused.has(name)) {
        script.onerror?.();
        return;
      }
      runScript(name);
      script.onload?.();
    }
    const gate = options.scriptGates?.get(name);
    if (gate) {
      void gate.then(respond);
    } else {
      setImmediate(respond);
    }
  }
  const writes = [];
  const listeners = new Set();
  let keydown;
  const history = {
    state: null,
    pushState(state, _title, href) {
      writes.push(href);
      moveTo(state, href);
    },
    replaceState(state, _title, href) {
      moveTo(state, href);
    },
  };
  function moveTo(state, href) {
    const url = new URL(href, "http://metabrowser.test");
    history.state = state;
    location.pathname = url.pathname;
    location.search = url.search;
    location.hash = url.hash;
  }

  const sandbox = loadNavigation({
    CustomEvent: class {
      constructor(type, init) {
        this.type = type;
        this.detail = init?.detail;
      }
    },
    addEventListener(type, listener) {
      if (type === "popstate") {
        listeners.add(listener);
      }
    },
    dispatchEvent(event) {
      if (event.type === "metabrowser:navigation-fragment") {
        counters.fragments += 1;
      }
      return true;
    },
    document: {
      addEventListener(type, listener) {
        if (type === "keydown") {
          keydown = listener;
        }
      },
      body: { append() {} },
      cookie: "",
      createElement: (tag) =>
        fakeElement({ focus() {}, remove() {}, ...(tag === "button" ? LIVE_TARGET : {}) }),
      documentElement: { getAttribute: () => null },
      getElementById: (id) => elements.get(id) ?? null,
      querySelector: (selector) =>
        selector === ".nav-tab-bar"
          ? navBar
          : (toolbars.find(
              (toolbar) => selector === `[data-nav-toolbar="${toolbar.dataset.navToolbar}"]`,
            ) ?? null),
      querySelectorAll: (selector) =>
        selector === "[data-nav-toolbar]" ? toolbars : [...tabPanels, previewTab],
      head: { append() {}, appendChild: requestScript },
    },
    DOMException,
    Element: {
      [Symbol.hasInstance](value) {
        return typeof value?.closest === "function";
      },
    },
    METABROWSER_ASSET_BUNDLES: ASSET_BUNDLES,
    METABROWSER_SETTINGS: {
      SYNTAX_HIGHLIGHT_MAX_BYTES: 512 * 1024,
      SYNTAX_LANGUAGE_BY_BASENAME: {},
      SYNTAX_LANGUAGE_BY_EXTENSION: {},
    },
    TextEncoder,
    URL,
    URLSearchParams,
    history,
    location,
    removeEventListener(type, listener) {
      if (type === "popstate") {
        listeners.delete(listener);
      }
    },
    mainTabs: null,
    mainTabIntent: 0,
    // The shell keymap is created with the registry; these scenarios have neither.
    shellKeymap: null,
    pullHistoryGeneration: 0,
    navScrollShadowUpdate: null,
    queryHtml: (selector) =>
      selector === ".nav-tab-bar"
        ? navBar
        : selector === '#preview-pane > .tab-bar > .tab-btn[data-tab="source"]'
          ? sourceTab
          : null,
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
    maybeOpenLiveStream() {},
    renderFile: async (data, viewId, claim, renderOptions) => {
      // The renderer mounts through the compositor selectFile began loading, so a
      // compositor that did not arrive is this render's failure.
      const composition = await renderOptions.viewComposition;
      if (composition.status === "error") {
        throw composition.error;
      }
      if (!sandbox.isPreviewClaimCurrent(claim)) {
        return false;
      }
      renderedViews.push(`${data.path}: ${viewId ?? "default view"}`);
      preview.dataset.renderedPath = data.path;
      sourceTab.classList.toggle("active", viewId === "source");
      preview.innerHTML = `<article class="rendered-view">${data.kind} ${data.path}</article>`;
      return true;
    },
    resetTextChunkGrowth() {},
    responsePerfMeta: () => ({}),
    selectPreviewTab(bar, tabId) {
      if (bar === tabBar) {
        tabClicks.push(`${preview.dataset.renderedPath}: ${tabId}`);
        sourceTab.classList.add("active");
      }
      return bar === tabBar;
    },
    revealInTree: options.revealInTree ?? (async () => false),
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
    pageConnections: { suspended: () => false },
    // The Files tree's keyboard layer, which only the held-key and main-tab digit
    // scenarios install.
    treeKeyboard: null,
    lastInventorySnapshot: null,
    quickFileCatalogFeed: {
      release() {},
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
  // No plugin registers a pull-request view here, so a pull-request page that loaded
  // is the shell's own message that nothing renders it.
  for (const name of [...STARTUP_SCRIPTS, ...(options.startupScripts ?? [])]) {
    runScript(name);
  }
  vm.runInContext(shellSource, sandbox, { filename: "app.js (preview pane functions)" });
  if (!options.deferTabs) {
    runScript("main-tabs.js");
    if (!options.withoutGit) {
      sandbox.attachMainTabs().register({
        id: "git",
        label: "Commits",
        onFirstShow: () => panelShows.push("git first show"),
        onShow: () => panelShows.push("git show"),
        onHide: options.onGitHide,
      });
    } else {
      sandbox.attachMainTabs();
    }
  }
  sandbox.initNavTabs();
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
    tabButtons,
    pressTabShortcut(key, options) {
      let consumed = false;
      keydown({
        key,
        ...options,
        preventDefault: () => {
          consumed = true;
        },
      });
      return consumed;
    },
    clickTab: (panel) => tabClick({ target: tabButtons.find((btn) => btn.dataset.tab === panel) }),
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
    previewTab,
    pop(href, state = null) {
      moveTo(state, href);
      for (const listener of listeners) {
        listener();
      }
    },
    writes,
    refused,
    renderedViews,
    scriptRequests,
    tabClicks,
    sandbox,
    sources,
    tabs: () => tabPanels.map((panel) => `${panel.dataset.tabContent}:${panel.style.display}`),
    /** The toolbars in the navigation's slot, shown or not. */
    toolbarsPresent: () => toolbars.map((toolbar) => toolbar.dataset.navToolbar),
    /** @param {string} name One toolbar in the slot. */
    toolbar: (name) => toolbars.find((toolbar) => toolbar.dataset.navToolbar === name),
    /** The toolbars shown in the navigation's slot: exactly the active tab's. */
    toolbarsShown: () =>
      toolbars.filter((toolbar) => !toolbar.hidden).map((toolbar) => toolbar.dataset.navToolbar),
  };
}

const refusedFetch = () => Promise.reject(new TypeError("Failed to fetch"));

async function tabSwitchDuringLoad() {
  // Marking the tab for a route leaves the existing preview producer in charge.
  const response = deferred();
  const shell = createShell("/view/big/", () => response.promise);
  const started = shell.sandbox.navigationController.start();
  await settle();
  const loading = shell.pane();
  shell.sandbox.mainTabs.activate("git");
  assert.equal(shell.previewTab.style.display, "", "main tabs leave preview tabs alone");
  const onGitTab = { pane: shell.pane(), tabs: shell.tabs() };
  shell.sandbox.mainTabs.activate("files");
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

function navPanelsKeepTheirPlace() {
  // The navigation panels share one scroller. A switch keeps the offset of the panel it
  // leaves and puts back the offset of the one it shows, the top for a panel never shown,
  // and tells the panel that leaves, so one that polls can stop; choosing the panel already
  // in front moves nothing and tells nobody. Before this, Files' offset carried into Git.
  const scroller = fakeElement({ scrollTop: 0 });
  const told = [];
  const shell = createShell("/view/", refusedFetch, {
    scroller,
    onGitHide: () => told.push("git hidden"),
  });
  const switches = [];
  for (const [scrolled, panel] of [
    [400, "git"],
    [250, "files"],
    [400, "git"],
    [250, "git"],
  ]) {
    scroller.scrollTop = scrolled;
    shell.sandbox.mainTabs.activate(panel);
    switches.push(`scrolled to ${scrolled}, ${panel} chosen: shows ${scroller.scrollTop}`);
  }
  return { switches, told };
}

async function mainTabShortcuts() {
  // The server supplies Files and Pulls. Git can arrive after the keyboard registry.
  const shell = createShell(
    "/view/",
    (path) => Promise.resolve(jsonResponse({ kind: "text", path })),
    {
      pulls: true,
      withoutGit: true,
      startupScripts: ["keyboard-shortcuts.js"],
    },
  );
  const { sandbox, tabButtons } = shell;
  const shortcuts = sandbox.MetabrowserKeyboardShortcuts.create({ document: sandbox.document });
  sandbox.mainTabs.bindShortcuts(shortcuts);
  const press = (key, options) => shell.pressTabShortcut(key, options);
  assert.equal(press("2", {}), false, "absent Git leaves 2 alone");
  assert.equal(press("3", { code: "Digit3", metaKey: true }), false, "Command-3 is the browser's");
  assert.equal(press("3", { code: "Digit3", ctrlKey: true }), false, "Ctrl-3 is the browser's");
  assert.equal(press("3", { code: "Digit3" }), true, "Pulls keeps 3 while Git is absent");
  assert.equal(sandbox.mainTabs.active(), "pulls");
  assert.equal(press("3", { code: "Digit3", shiftKey: true }), true, "Shift does not change 3");
  await settle();

  sandbox.mainTabs.register({ id: "git", label: "Commits", onFirstShow: null });
  assert.deepEqual(
    tabButtons.map((button) => button.dataset.tab),
    ["files", "git", "pulls"],
  );
  assert.equal(press("2", { code: "Digit2", target: { tagName: "INPUT" } }), false);
  assert.equal(press("2", { code: "Digit2", metaKey: true }), false, "Command-2 is the browser's");
  const closeModal = shortcuts.activateScope("help", { exclusive: true });
  assert.equal(press("2", { code: "Digit2" }), false, "modal scopes own their keys");
  closeModal();
  // US Shift+2 types @ and Shift+1 types !: the digit row still names the tab.
  assert.equal(press("@", { code: "Digit2", shiftKey: true }), true, "Shift+2 opens Commits");
  assert.equal(sandbox.mainTabs.active(), "git");
  await settle();
  // The digit hands focus to the panel's roving row, the tree's for Files.
  const focusedRows = [];
  sandbox.treeKeyboard = {
    focusCurrent() {
      focusedRows.push("files");
      return true;
    },
  };
  assert.equal(press("!", { code: "Digit1", shiftKey: true }), true, "Shift+1 opens Files");
  assert.equal(sandbox.mainTabs.active(), "files");
  assert.deepEqual(focusedRows, ["files"], "the Files digit focuses the tree's roving row");
  sandbox.treeKeyboard = null;
  await settle();

  const help = shortcuts.snapshot("help").find((group) => group.id === "main-tabs");
  assert.equal(help.context, "Available outside text fields.");
  assert.deepEqual(plain(help.commands.map((command) => command.bindings.spoken)), ["1", "2", "3"]);
  return {
    tabOrder: tabButtons.map((button) => button.dataset.tab),
    ariaKeys: tabButtons.map((button) => button.getAttribute("aria-keyshortcuts")),
    keyboardRoutes: shell.writes,
  };
}

async function quickSearchPullRoute() {
  const read = async (path) => jsonResponse({ kind: "text", path });
  const selectedFile = "/view/notes.md?plain=1#L2";
  const shell = createShell("/view/notes.md", read, { pulls: true });
  const { sandbox } = shell;
  sandbox.history.replaceState(null, "", selectedFile);
  sandbox.addEventListener("popstate", sandbox.applyPullHistoryLanding);
  await sandbox.navigationController.start();
  const opened = await sandbox.openQuickSearchPull(307);
  assert.equal(opened.status, "opened");
  assert.equal(opened.focusTarget, sandbox.document.getElementById("preview-pane"));
  assert.equal(sandbox.mainTabs.active(), "pulls");
  assert.equal(shell.pane().owner, "pull-request");
  assert.deepEqual(shell.writes, ["/pull/307"], "opening makes a single history step");
  shell.pop(selectedFile);
  await settle();
  assert.equal(sandbox.mainTabs.active(), "files");
  assert.equal(shell.pane().owner, "file");

  const gate = deferred();
  const pending = createShell("/view/notes.md", read, {
    pulls: true,
    scriptGates: new Map([["pull-route.js", gate.promise]]),
  });
  await pending.sandbox.navigationController.start();
  const earlier = pending.sandbox.openQuickSearchPull(307);
  await pending.sandbox.navigateToPath("newer.md");
  gate.resolve();
  const superseded = await earlier;
  assert.equal(superseded.status, "cancelled");
  assert.equal(pending.sandbox.location.pathname, "/view/newer.md");

  return {
    opened: shell.writes,
    backTo: sandbox.location.pathname + sandbox.location.search + sandbox.location.hash,
    superseded: superseded.status,
  };
}

async function independentMainTabs() {
  const read = (path) => Promise.resolve(jsonResponse({ kind: "text", path }));
  const pendingFile = deferred();
  const scroller = fakeElement({ scrollTop: 0 });
  const shell = createShell(
    "/view/notes.md",
    (path) => (path === "notes.md" ? pendingFile.promise : read(path)),
    {
      scroller,
      pulls: true,
      async revealInTree(_path, { scroll }) {
        if (scroll) {
          scroller.scrollTop = 999;
        }
      },
    },
  );
  const { sandbox } = shell;
  const selectedFile = "/view/notes.md?plain=1#L2";
  const selectedPull = "/pull/7/files/src/a.py";
  const older = "b".repeat(40);
  const commit = `/commit/${older}/src/a.py#diff-2`;
  const place = { pullPlace: { top: 35 } };
  const selections = [];
  sandbox.addEventListener("popstate", sandbox.applyPullHistoryLanding);
  sandbox.MetabrowserPullsNav = {
    routeChanged() {
      if (sandbox.location.pathname === selectedPull) {
        // The mounted Pulls panel can reveal an offscreen selected row.
        scroller.scrollTop = 999;
      }
    },
  };
  const commitLandings = [];
  sandbox.MetabrowserGitPanel = {
    cancelPending() {},
    async restoreCommitLanding() {
      const parsed = sandbox.MetabrowserNavigationRoute.parseCommit(sandbox.location.pathname);
      commitLandings.push(parsed.revision);
      shell.claimGit(parsed.revision);
    },
  };
  sandbox.history.replaceState(null, "", selectedFile);
  const initial = sandbox.navigationController.start();
  await settle();

  function snapshot() {
    const { pathname, search, hash } = sandbox.location;
    return {
      address: pathname + search + hash,
      panel: sandbox.mainTabs.active(),
      owner: shell.pane().owner,
      scroll: scroller.scrollTop,
    };
  }
  async function open(panel) {
    shell.clickTab(panel);
    await settle();
    selections.push(snapshot());
  }
  scroller.scrollTop = 240;
  const outgoing = shell.pane().claim;
  await open("pulls");
  assert.equal(selections.at(-1).address, "/pulls");
  assert.equal(selections.at(-1).owner, "pull-request");
  assert.equal(
    sandbox.isPreviewClaimCurrent(outgoing),
    false,
    "a held Files response lost ownership",
  );
  pendingFile.resolve(jsonResponse({ kind: "text", path: "notes.md" }));
  await initial;
  await settle();
  assert.equal(shell.pane().owner, "pull-request", "late Files cannot replace Pulls");

  // A filtered list and a changed file are ordinary browser entries.
  shell.pop("/pulls?state=closed");
  await settle();
  scroller.scrollTop = 80;
  await open("git");
  assert.equal(selections.at(-1).address, "/view/");
  assert.equal(sandbox.history.state.gitLanding, true);
  assert.match(shell.pane().shows, /Select a commit to preview/);
  assert.deepEqual(commitLandings, [], "a first Git visit does not open commit detail");
  sandbox.history.replaceState(null, "", commit);
  sandbox.mainTabs.remember();
  scroller.scrollTop = 120;
  await open("pulls");
  assert.equal(selections.at(-1).address, "/pulls?state=closed");
  assert.equal(scroller.scrollTop, 80);
  shell.pop(selectedPull, place);
  await settle();
  await open("files");
  assert.equal(selections.at(-1).address, selectedFile);
  assert.equal(scroller.scrollTop, 240);
  await open("pulls");
  assert.equal(selections.at(-1).address, selectedPull);
  assert.equal(scroller.scrollTop, 80, "revealing the PR must not replace the saved offset");
  assert.deepEqual(sandbox.history.state, place);
  await open("git");
  assert.equal(selections.at(-1).address, commit);
  assert.equal(sandbox.history.state.cachedCommit, true);
  assert.deepEqual(commitLandings, [older]);
  assert.equal(scroller.scrollTop, 120);
  const still = shell.pane().claim;
  const pushed = shell.writes.length;
  shell.clickTab("git");
  assert.equal(shell.writes.length, pushed, "the active tab pushes no history");
  assert.equal(shell.pane().claim, still, "the active tab makes no preview claim");

  shell.pop(selectedFile);
  await settle();
  assert.equal(sandbox.mainTabs.active(), "files", "Back activates the address owner");
  assert.equal(shell.pane().owner, "file");
  shell.pop(selectedPull, place);
  await settle();
  assert.equal(sandbox.mainTabs.active(), "pulls", "Forward activates the address owner");
  assert.equal(shell.pane().owner, "pull-request");
  assert.equal(shell.writes.length, pushed, "Back and Forward never write another entry");

  const pullStartup = createShell(selectedPull, read, { pulls: true });
  await pullStartup.sandbox.navigationController.start();
  pullStartup.clickTab("files");
  await settle();
  assert.equal(
    pullStartup.sandbox.location.pathname,
    "/view/",
    "the first Files visit opens its root",
  );
  const activeAfterHistory = sandbox.mainTabs.active();
  shell.pop("/view/", { gitLanding: true });
  await settle();
  assert.equal(sandbox.mainTabs.active(), "git");
  assert.match(shell.pane().shows, /Select a commit to preview/);
  shell.pop("/view/");
  await settle();
  assert.equal(sandbox.mainTabs.active(), "files", "Files and neutral Git can share a pathname");
  assert.equal(shell.pane().owner, "file");

  const reloaded = createShell("/view/", read);
  reloaded.sandbox.history.replaceState({ gitLanding: true, other: 1 }, "", "/view/");
  await reloaded.sandbox.navigationController.start();
  assert.match(reloaded.pane().shows, /Select a commit to preview/);
  await reloaded.sandbox.mainTabs.finishGitDiscovery();
  assert.equal(reloaded.sandbox.mainTabs.active(), "git", "deferred registration restores Git");
  const unavailable = createShell("/view/", read, { withoutGit: true });
  unavailable.sandbox.history.replaceState({ gitLanding: true, other: 1 }, "", "/view/");
  await unavailable.sandbox.navigationController.start();
  await unavailable.sandbox.mainTabs.finishGitDiscovery();
  assert.equal(unavailable.pane().owner, "file", "failed discovery falls back to Files root");
  assert.deepEqual(plain(unavailable.sandbox.history.state), { other: 1 });
  assert.deepEqual(unavailable.writes, [], "failed discovery repairs the same history entry");
  const missingGit = createShell("/view/", read, { withoutGit: true });
  missingGit.sandbox.addEventListener("popstate", missingGit.sandbox.applyPullHistoryLanding);
  await missingGit.sandbox.navigationController.start();
  await missingGit.sandbox.mainTabs.finishGitDiscovery();
  missingGit.pop("/view/", { gitLanding: true, other: 2 });
  await settle();
  assert.equal(missingGit.sandbox.mainTabs.active(), "files");
  assert.doesNotMatch(missingGit.pane().shows, /Select a commit to preview/);
  assert.deepEqual(plain(missingGit.sandbox.history.state), { other: 2 });
  assert.deepEqual(missingGit.writes, [], "Back repairs the same history entry");

  const pendingGit = createShell("/view/", read, { withoutGit: true });
  pendingGit.sandbox.addEventListener("popstate", pendingGit.sandbox.applyPullHistoryLanding);
  await pendingGit.sandbox.navigationController.start();
  pendingGit.pop("/view/", { gitLanding: true });
  await settle();
  assert.equal(pendingGit.sandbox.history.state.gitLanding, true, "Back waits for Git discovery");
  pendingGit.sandbox.mainTabs.register({ id: "git", label: "Commits", onFirstShow: null });
  await pendingGit.sandbox.mainTabs.finishGitDiscovery();
  assert.equal(pendingGit.sandbox.mainTabs.active(), "git");
  assert.match(pendingGit.pane().shows, /Select a commit to preview/);

  // The server draws Commits at a repository's root, before Git discovery registers it,
  // so Pulls beside it never moves. A press before registration waits for it and opens
  // Commits once it is registered; discovery that registers it keeps it, and discovery
  // that does not removes it, with its toolbar, and forgets the press.
  const drawnGit = createShell("/view/", read, { gitDrawn: true, withoutGit: true });
  await drawnGit.sandbox.navigationController.start();
  drawnGit.clickTab("git");
  await settle();
  assert.equal(drawnGit.sandbox.mainTabs.active(), "files", "an unregistered Commits tab waits");
  assert.equal(drawnGit.sandbox.location.pathname, "/view/");
  await drawnGit.sandbox.mainTabs.finishGitDiscovery();
  assert.deepEqual(
    drawnGit.tabButtons.map((button) => button.dataset.tab),
    ["files"],
    "discovery that finds no repository removes the drawn tab",
  );
  assert.deepEqual(
    drawnGit.toolbarsPresent(),
    ["files"],
    "a removed tab takes its toolbar with it, so the slot keeps no stale tally",
  );
  assert.equal(drawnGit.sandbox.mainTabs.active(), "files", "a forgotten press opens nothing");
  const drawnLate = createShell("/view/", read, { gitDrawn: true, withoutGit: true });
  await drawnLate.sandbox.navigationController.start();
  drawnLate.clickTab("git");
  await settle();
  assert.equal(drawnLate.sandbox.mainTabs.active(), "files", "Commits waits for registration");
  drawnLate.sandbox.mainTabs.register({ id: "git", label: "Commits", onFirstShow: null });
  await settle();
  assert.equal(
    drawnLate.sandbox.mainTabs.active(),
    "git",
    "a press before registration opens Commits once it is registered",
  );
  const drawnReplaced = createShell("/view/", read, { gitDrawn: true, withoutGit: true });
  await drawnReplaced.sandbox.navigationController.start();
  drawnReplaced.clickTab("git");
  drawnReplaced.clickTab("files");
  await settle();
  drawnReplaced.sandbox.mainTabs.register({ id: "git", label: "Commits", onFirstShow: null });
  await settle();
  assert.equal(
    drawnReplaced.sandbox.mainTabs.active(),
    "files",
    "a press on another tab replaces a pending Commits press",
  );
  assert.deepEqual(
    reloaded.tabButtons.map((button) => button.dataset.tab),
    ["files", "git"],
    "discovery that registers Commits keeps the drawn tab",
  );

  // The navigation's toolbar slot shows exactly the tab in front's toolbar, so the slot
  // is never empty and what is under it starts at one y on every tab.
  const slotted = createShell("/view/", read, { pulls: true });
  await slotted.sandbox.navigationController.start();
  const slots = { landing: slotted.toolbarsShown() };
  for (const panel of ["git", "pulls", "files"]) {
    slotted.sandbox.mainTabs.activate(panel);
    slots[panel] = slotted.toolbarsShown();
  }
  assert.deepEqual(
    slots,
    { landing: ["files"], git: ["git"], pulls: ["pulls"], files: ["files"] },
    "each tab shows its own toolbar, and only it",
  );
  // A toolbar a narrow pane scrolled comes back at its start.
  slotted.toolbar("pulls").scrollLeft = 97;
  slotted.sandbox.mainTabs.activate("pulls");
  assert.equal(
    slotted.toolbar("pulls").scrollLeft,
    0,
    "a scrolled toolbar comes back at its start",
  );
  const pullsLanding = createShell("/pulls", read, { pulls: true });
  assert.deepEqual(
    pullsLanding.toolbarsShown(),
    ["pulls"],
    "the server draws the landing's toolbar",
  );
  assert.deepEqual(
    pendingGit.toolbarsShown(),
    ["git"],
    "a toolbar added for a late panel shows with it",
  );

  // A commit's address is drawn with Commits in front, and the page keeps it in front from
  // its first script on: the Files toolbar and tree are never shown and then swapped.
  const commitLanding = createShell(`/commit/${"c".repeat(40)}`, read);
  const landed = {
    active: commitLanding.sandbox.mainTabs.active(),
    toolbars: commitLanding.toolbarsShown(),
    panels: commitLanding.tabs(),
  };
  await commitLanding.sandbox.navigationController.start();
  await settle();
  assert.deepEqual(
    landed,
    { active: "git", toolbars: ["git"], panels: ["files:none", "git:"] },
    "a commit landing starts on Commits",
  );
  assert.deepEqual(
    [commitLanding.sandbox.mainTabs.active(), commitLanding.toolbarsShown()],
    ["git", ["git"]],
    "and stays there once the address is applied",
  );

  const early = createShell("/view/", read, { pulls: true, deferTabs: true });
  assert.equal(early.sandbox.mainTabs, null, "plain startup does not fetch main tabs");
  early.clickTab("pulls");
  await early.sandbox.MetabrowserAssets.ensureAsset("shell-tools");
  await settle();
  assert.equal(early.sandbox.location.pathname, "/pulls");
  assert.equal(early.sandbox.mainTabs.active(), "pulls");
  assert.deepEqual(
    early.scriptRequests.filter((name) => name === "main-tabs.js"),
    ["main-tabs.js"],
  );
  const superseded = createShell("/view/", read, { pulls: true, deferTabs: true });
  superseded.clickTab("pulls");
  superseded.clickTab("files");
  await settle();
  assert.deepEqual(superseded.writes, [], "a later active-tab click cancels an early switch");
  assert.equal(superseded.sandbox.pullHistoryGeneration, 0, "clicks did not affect pull history");
  const earlyFiles = createShell(selectedPull, read, { pulls: true, deferTabs: true });
  earlyFiles.clickTab("files");
  const booting = earlyFiles.sandbox.navigationController.start();
  await booting;
  await settle();
  assert.equal(
    earlyFiles.sandbox.location.pathname,
    "/view/",
    "startup does not override an early Files click",
  );
  for (const replace of [false, true]) {
    const mainTabsScript = deferred();
    const newerPull = createShell("/pull/7", read, {
      pulls: true,
      deferTabs: true,
      scriptGates: new Map([["main-tabs.js", mainTabsScript.promise]]),
    });
    await newerPull.sandbox.navigationController.start();
    const host = await newerPull.sandbox.loadPullPageHost();
    newerPull.clickTab("files");
    await settle();
    assert(newerPull.scriptRequests.includes("main-tabs.js"), "the Files click requested tabs");
    assert.equal(newerPull.sandbox.mainTabs, null, "the tab module is still held");
    await host.open({ number: 7, tab: "files", file: "src/a.py", replace });
    assert.equal(newerPull.sandbox.location.pathname, selectedPull);
    mainTabsScript.resolve();
    await settle();
    assert.equal(newerPull.sandbox.location.pathname, selectedPull, "the newer PR route wins");
    assert.equal(newerPull.sandbox.mainTabs.active(), "pulls");
    assert.deepEqual(newerPull.writes, replace ? [] : [selectedPull]);
  }
  return {
    selections,
    historyPushes: shell.writes.length,
    activeAfterHistory,
    neutralGitDetailOpens: commitLandings.length - 1,
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

async function anchoredAddressesOpenSource() {
  // An address with a line anchor or GitHub's `plain=1` opens the file in its Source
  // view; any other fragment or query leaves the file's default view. A line anchor
  // added to the file already shown selects its Source tab without loading it again.
  // A view that plugin navigation names outright wins over the address's.
  const shell = createShell("/view/", (requested) =>
    Promise.resolve(jsonResponse({ kind: requested ? "markdown" : "folder", path: requested })),
  );
  await shell.sandbox.navigationController.start();
  await settle();
  for (const target of [
    { path: "README.md", fragment: "L3-L4" },
    { path: "guide.md", query: "plain=1" },
    { path: "notes.md", fragment: "install" },
    { path: "notes.md", fragment: "L2" },
    { path: "notes.md", fragment: "L5" },
    { path: "other.md", query: "plain=10" },
  ]) {
    await shell.sandbox.navigationController.open(target);
    await settle();
  }
  await shell.sandbox.navigationController.open(
    { path: "chosen.md", fragment: "L7" },
    { viewId: "rendered" },
  );
  await settle();
  const files = shell.renderedViews.filter((entry) => !entry.startsWith(": "));
  return {
    renderedViews: files,
    tabClicks: shell.tabClicks,
    fragments: shell.counters.fragments,
  };
}

async function coldAnchoredAddress() {
  // A page that loads at a line-anchored address opens the file in its Source view.
  // The module that reads the anchor is not a startup script: it arrives with the view
  // compositor, and the address waits for it before it chooses a view.
  const shell = createShell(
    "/view/a.py",
    (requested) => Promise.resolve(jsonResponse({ kind: "text", path: requested })),
    { hash: "#L10" },
  );
  const lineAnchorsAtStartup = typeof shell.sandbox.MetabrowserSourceLineAnchors;
  await shell.sandbox.navigationController.start();
  await settle();

  // The module's fetch starts when the address is applied, so it overlaps revealing
  // the row and does not follow it. An address with no fragment or query cannot name
  // a view, and goes on to the file without asking for anything first.
  async function whileRevealing(hash) {
    const row = deferred();
    const revealing = createShell(
      "/view/a.py",
      (requested) => Promise.resolve(jsonResponse({ kind: "text", path: requested })),
      { hash, revealInTree: () => row.promise },
    );
    const started = revealing.sandbox.navigationController.start();
    await settle();
    const requestedMeanwhile = [...revealing.scriptRequests];
    row.resolve(false);
    await started;
    await settle();
    return { requestedMeanwhile, renderedViews: revealing.renderedViews };
  }

  return {
    lineAnchorsAtStartup,
    scriptRequests: shell.scriptRequests,
    renderedViews: shell.renderedViews,
    pane: shell.pane(),
    whileTheRowIsRevealed: {
      anchoredAddress: await whileRevealing("#L10"),
      plainAddress: await whileRevealing(""),
    },
  };
}

async function pullRouteLoadsOnDemand() {
  // The pull-request page's routes are no startup script of a folder's page, whose
  // addresses never ask for them. The server adds them to the shell of a pull-request
  // address, so a page that loads there asks for nothing before it shows the page; one
  // that reaches such an address through history, with no host yet, fetches them and
  // then mounts the page; and an address under /pull/ that is no page lands nowhere.
  // The page's plugin is loaded with no compositor, so its load fetches the SDK's
  // view helpers and the template library.
  const folder = createShell("/view/", (requested) =>
    Promise.resolve(jsonResponse({ kind: requested ? "text" : "folder", path: requested })),
  );
  await folder.sandbox.navigationController.start();
  await folder.sandbox.navigationController.open({ path: "notes.txt" });
  await settle();
  folder.sandbox.location.pathname = "/view/notes.txt";
  folder.sandbox.applyPullHistoryLanding();
  await settle();

  const page = createShell("/pull/7", refusedFetch, { startupScripts: ["pull-route.js"] });
  await page.sandbox.navigationController.start();
  await settle();
  const first = { scriptRequests: [...page.scriptRequests], pane: page.pane() };
  page.sandbox.location.pathname = "/pull/7/files";
  page.sandbox.applyPullHistoryLanding();
  await settle();

  const notAPage = createShell("/pull/x", refusedFetch);
  await notAPage.sandbox.navigationController.start();
  await settle();

  // A commit address is the Git panel's, so the controller holds no target there and
  // nothing has asked for the pull-request routes. Back onto a page's entry is then
  // the host's to apply, once it has loaded.
  const back = createShell(`/commit/${"a".repeat(40)}`, refusedFetch);
  await back.sandbox.navigationController.start();
  await settle();
  const backBefore = {
    scriptRequests: [...back.scriptRequests],
    hostCreated: back.sandbox.pullPageHost !== null,
  };
  back.sandbox.location.pathname = "/pull/8";
  back.sandbox.applyPullHistoryLanding();
  await settle();

  return {
    folderAddresses: {
      scriptRequests: folder.scriptRequests,
      hostCreated: folder.sandbox.pullPageHost !== null,
    },
    pullAddress: { ...first, afterTabLanding: { scriptRequests: page.scriptRequests } },
    notAPullAddress: { scriptRequests: notAPage.scriptRequests, pane: notAPage.pane() },
    historyLandingWithoutHost: {
      before: backBefore,
      scriptRequests: back.scriptRequests,
      pane: back.pane(),
    },
  };
}

async function onDemandCodeRefused() {
  // Each on-demand script a page needs can fail to arrive. The pane then says that,
  // not that nothing is selected or that no plugin renders the page, and what is asked
  // for again once the server answers is only what failed.
  const text = (requested) => Promise.resolve(jsonResponse({ kind: "text", path: requested }));

  // Opening a file: the SDK's view helpers arrive beside the compositor, or not.
  const fileRefused = new Set(["plugin-sdk-views.js"]);
  const file = createShell("/view/notes.md", text, { refused: fileRefused });
  await file.sandbox.navigationController.start();
  await settle();
  const fileFailed = { pane: file.pane(), scriptRequests: [...file.scriptRequests] };
  fileRefused.clear();
  const reopened = await file.sandbox.navigateToPath("notes.md");
  await settle();

  // A pull-request address whose routes did not arrive: the shell's own script failed,
  // or history landed there from another page.
  const routes = createShell("/pull/7", refusedFetch, { refused: new Set(["pull-route.js"]) });
  await routes.sandbox.navigationController.start();
  await settle();

  const landing = createShell(`/commit/${"a".repeat(40)}`, refusedFetch, {
    refused: new Set(["pull-route.js"]),
  });
  await landing.sandbox.navigationController.start();
  landing.claimGit("abc123");
  landing.sandbox.location.pathname = "/pull/8";
  landing.sandbox.applyPullHistoryLanding();
  await settle();

  // The page's plugin is loaded with no compositor, so its load fetches the helpers.
  const helpersRefused = new Set(["plugin-sdk-views.js"]);
  const helpers = createShell("/pull/7", refusedFetch, {
    refused: helpersRefused,
    startupScripts: ["pull-route.js"],
  });
  await helpers.sandbox.navigationController.start();
  await settle();
  const helpersFailed = { pane: helpers.pane(), scriptRequests: [...helpers.scriptRequests] };
  helpersRefused.clear();
  helpers.sandbox.location.pathname = "/pull/7/files";
  helpers.sandbox.applyPullHistoryLanding();
  await settle();

  // The template prerequisite can also fail after the other helpers are ready.
  // A later route retries only that library before reporting an absent plugin.
  const templatesRefused = new Set(["vendor/mustache.min.js"]);
  const templates = createShell("/pull/7", refusedFetch, {
    refused: templatesRefused,
    startupScripts: ["pull-route.js"],
  });
  await templates.sandbox.navigationController.start();
  await settle();
  const templatesFailed = { pane: templates.pane(), scriptRequests: [...templates.scriptRequests] };
  templatesRefused.clear();
  templates.sandbox.location.pathname = "/pull/7/files";
  templates.sandbox.applyPullHistoryLanding();
  await settle();

  return {
    viewHelpersOpeningAFile: {
      failed: fileFailed,
      reopened: {
        outcome: file.outcome(reopened),
        pane: file.pane(),
        scriptRequests: file.scriptRequests.slice(fileFailed.scriptRequests.length),
      },
    },
    pullRoutesAtAPullAddress: { pane: routes.pane(), scriptRequests: routes.scriptRequests },
    pullRoutesOnAHistoryLanding: { pane: landing.pane(), scriptRequests: landing.scriptRequests },
    templatesOnThePullPage: {
      failed: templatesFailed,
      nextRoute: {
        pane: templates.pane(),
        scriptRequests: templates.scriptRequests.slice(templatesFailed.scriptRequests.length),
      },
    },
    viewHelpersOnThePullPage: {
      failed: helpersFailed,
      nextRoute: {
        pane: helpers.pane(),
        scriptRequests: helpers.scriptRequests.slice(helpersFailed.scriptRequests.length),
      },
    },
  };
}

async function heldKeyWalk() {
  // A held arrow key moves the selection and replaces the address on every
  // repeat, and the file the walk stops on is the only one read and rendered:
  // when the repeats stop, or at once when the key is let go. A single press
  // opens at once. The walk is tree-keyboard-navigation.js's, and each key does
  // what its focusAndOpen does: step the walk, then open the row.
  const shell = createShell("/view/", (requested) =>
    Promise.resolve(jsonResponse({ kind: "text", path: requested })),
  );
  await shell.sandbox.navigationController.start();
  await settle();
  const scriptPath = path.join(staticDir, "tree-keyboard-navigation.js");
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), shell.sandbox, { filename: scriptPath });
  const walk = shell.sandbox.MetabrowserTreeKeyboardNavigation.createWalk();
  shell.sandbox.treeKeyboard = { walking: walk.walking };

  async function key(pathName, repeat) {
    walk.step(pathName, repeat);
    shell.sandbox.openTreeRow({ dataset: { path: pathName } });
    await settle();
    return `${repeat ? "repeat" : "press"} ${pathName}: address ${shell.sandbox.location.pathname}`;
  }
  const renderedBefore = shell.renderedViews.length;
  const keys = [await key("a.md", false)];
  const afterPress = shell.renderedViews.slice(renderedBefore);
  for (const name of ["b.md", "c.md", "d.md", "e.md", "f.md"]) {
    keys.push(await key(name, true));
  }
  const whileHeld = shell.renderedViews.slice(renderedBefore);
  // The quiet period after the last repeat elapses.
  shell.elapseLoadingDelay();
  await settle();
  const afterSettle = shell.renderedViews.slice(renderedBefore);
  // The key is let go and held again: a hold that outlasted the quiet period with the key
  // still down is a slow repeat, whose rows open as single presses do.
  walk.end();
  const releaseKeys = [await key("g.md", true), await key("h.md", true)];
  const beforeRelease = shell.renderedViews.slice(renderedBefore);
  // Letting the key go is what the tree's keyup does.
  walk.end();
  await settle();
  return {
    afterPress,
    afterRelease: shell.renderedViews.slice(renderedBefore),
    afterSettle,
    beforeRelease,
    fetches: Object.fromEntries(
      ["a.md", "b.md", "c.md", "d.md", "e.md", "f.md", "g.md", "h.md"].map((name) => [
        name,
        shell.fetches(name),
      ]),
    ),
    keys,
    releaseKeys,
    whileHeld,
  };
}

async function shell() {
  const pulls = createShell("/pulls", refusedFetch);
  const preview = pulls.sandbox.document.getElementById("preview-pane");
  preview.innerHTML =
    '<div class="content-body pull-request-list-host" data-preview-empty="">' +
    '<div class="preview-empty">Select a pull request.</div></div>';
  const claim = pulls.sandbox.claimPreview("pull-request", "294");
  assert.equal(
    pulls.sandbox.beginPreviewNavigation(claim),
    false,
    "the neutral list host cannot hide initial PR loading blocks",
  );
  assert.equal(preview.getAttribute("aria-busy"), null);
  preview.innerHTML = '<article class="github-pull">A useful previous pull request</article>';
  assert.equal(pulls.sandbox.beginPreviewNavigation(claim), true);
  assert.equal(preview.getAttribute("aria-busy"), "true");

  const shipped = createShell("/view/", refusedFetch);
  return {
    shippedPlaceholderHtml: shipped.sandbox.previewPlaceholderHtml(
      shipped.sandbox.previewPane.placeholder(0),
    ),
    tabSwitchDuringLoad: await tabSwitchDuringLoad(),
    navPanelsKeepTheirPlace: navPanelsKeepTheirPlace(),
    independentMainTabs: await independentMainTabs(),
    mainTabShortcuts: await mainTabShortcuts(),
    quickSearchPullRoute: await quickSearchPullRoute(),
    reselectAfterFailure: await reselectAfterFailure(),
    bodyReadFailure: await bodyReadFailure(),
    reconnectRetry: await reconnectRetry(),
    startupSettle: await startupSettle(),
    anchoredAddressesOpenSource: await anchoredAddressesOpenSource(),
    coldAnchoredAddress: await coldAnchoredAddress(),
    pullRouteLoadsOnDemand: await pullRouteLoadsOnDemand(),
    onDemandCodeRefused: await onDemandCodeRefused(),
    heldKeyWalk: await heldKeyWalk(),
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
