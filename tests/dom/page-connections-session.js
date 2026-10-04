// Browserless session: what a page's connections do across the back/forward cache.
//
// A browser keeps a page it may show again on Back, with its heap and its open
// requests. Each kept page's event stream then holds one of the six connections the
// browser opens to a host, and the sixth page loaded in one tab waits for one
// (explorations/page-connections/README.md). So a `pagehide` that says the page is
// kept parks the page's connections, and the `pageshow` that brings it back reopens
// them. The decision is createPageConnections in navigation.js, loaded here whole.
//
// What it decides about is app.js: the inventory event stream with its reconnect and
// stable-connection timers, the live tail of a log, and the `pagehide` and `pageshow`
// listeners themselves. Those declarations are extracted from app.js verbatim and run
// against the real navigation module, as preview-pane-state-session.js does, so the
// wiring cannot regress behind a source-string assertion. The catalog feed the stream
// starts when it opens is the production catalog-feed.js, so "reconciles once" is a
// count of the `/api/catalog` requests it really makes.
//
// Only the browser is a double: EventSource, the timers, `fetch`, and the shell
// services a stream event is handed to. Each records what it was asked. A step's
// `did` is that record, in order, and `after` is what the page then holds: its open
// streams, its pending timers, and how many connections are parked.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf8");

/** One app.js declaration, bounded by its closing line at column zero. */
function appDeclaration(pattern, label) {
  const match = appSource.match(pattern);
  if (!match) {
    throw new Error(`app.js ${label} is not extractable`);
  }
  return match[0];
}

const SHELL_VARIABLES = [
  "_esConsecutiveErrors",
  "_esBackoffMs",
  "_esReconnectTimer",
  "_esStableResetTimer",
  "_ES_MAX_CONSECUTIVE_ERRORS",
  "_ES_BACKOFF_CAP_MS",
  "_ES_STABLE_CONNECTION_MS",
  "inventoryEventSource",
  "lastInventorySnapshot",
  "catalogFeedCanStart",
];

const SHELL_FUNCTIONS = [
  "isGitRevisionSource",
  "closeLiveStream",
  "parkLiveStream",
  "maybeOpenLiveStream",
  "openLiveStream",
  "appendLiveEvents",
  "_resetEsCircuitBreaker",
  "_cancelEsStableReset",
  "_scheduleEsStableReset",
  "_scheduleInventoryReconnect",
  "parkInventoryEventStream",
  "_createInventoryEventSource",
  "startInventoryEventStream",
];

const shellSource = [
  appDeclaration(/^let currentPath = null;$/m, "current path"),
  appDeclaration(/^let currentLiveStream = null;$/m, "live stream"),
  appDeclaration(/^const activeFiles = new Map\(\);[^\n]*$/m, "active files"),
  appDeclaration(/^const fileCache = new Map\(\);$/m, "file cache"),
  ...SHELL_VARIABLES.map((name) =>
    appDeclaration(new RegExp(`^var ${name} = [^\\n]*;$`, "m"), `variable ${name}`),
  ),
  ...SHELL_FUNCTIONS.map((name) =>
    appDeclaration(
      new RegExp(`^function ${name}\\([^)]*\\) \\{[\\s\\S]*?^\\}`, "m"),
      `function ${name}`,
    ),
  ),
  appDeclaration(/^var pageConnections = [\s\S]*?^\}\);$/m, "page connections"),
  appDeclaration(
    /^window\.addEventListener\("pagehide", \(event\) => pageConnections[^\n]*;$/m,
    "pagehide listener",
  ),
  appDeclaration(
    /^window\.addEventListener\("pageshow", \(event\) => pageConnections[^\n]*;$/m,
    "pageshow listener",
  ),
].join("\n\n");

// The shell services a stream event is handed to, and the page's teardown and rebuild.
// None of them decides anything about a connection; each records that it was called.
const COLLABORATORS = `
var _perf = { measure: (_label, fn) => fn() };
var quickFileCatalogFeed = null;
var quickFilePalette = { reconnected() {} };
var knownFileCatalog = null;
var filterState = null;
var inventoryChangeHighlightingActive = false;
var recentEverLoaded = false;
var recentContinuity = { dirtyActiveRequest() {} };
var fileNeedsRevalidate = new Set();
var recentFilterRefetch = { pending: () => false };
var recentRecompute = { cancel() {} };
var treeFilterModel = { observeRecentSentinel() {} };
function queryHtml() {
  return null;
}
function recentRepairDescriptor() {
  return null;
}
function filesPanelUsesRecentSource() {
  return false;
}
function recentViewOwnsCurrentCursor() {
  return false;
}
function _scheduleRecentRecompute() {}
function scheduleRecentAuthoritativeRefetch() {}
function notifyFileStoreSubscribers() {}
function startIndexProgressPolling() {}
function retryUnreachablePreview() {}
function flagRunEndedBadge() {
  __did("live log: marked ended");
}
function fileStoreApplySnapshot(_scope, entries) {
  __did("tree: snapshot of " + entries.length + " entries applied");
}
function fileStoreApplyChange(ops) {
  __did("tree: " + ops.length + " change applied");
}
function initKeyboardInfrastructure() {
  __did("page: keyboard rebuilt if torn down");
}
function initQuickFileFinder() {
  __did("page: Quick File rebuilt if torn down");
}
function disposeKeyboardInfrastructure() {
  __did("page: keyboard and Quick File torn down");
}
`;

/** A catalog target that accepts whatever the feed delivers. */
function catalogTarget() {
  return {
    applyCatalogChange: () => ({ candidateVisits: 0, changed: true, workItems: 1 }),
    applyEventChange: (ops) => ({ candidateVisits: 0, changed: true, workItems: ops.length }),
    beginBulkSnapshot: (files) => ({
      cancel() {},
      enqueueCatalogChange() {},
      enqueueEventChange() {},
      step: () => ({ candidateVisits: 0, cancelled: false, done: true, workItems: files.length }),
    }),
    beginCatalogChange: () => null,
    beginEventChange: () => null,
    markComplete() {},
    markIncomplete() {},
    markTruncated() {},
  };
}

/** Let every promise chain that needs no further input run. */
async function turns() {
  for (let round = 0; round < 10; round += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/** One page: the production code in a fresh global, with a recording browser. */
function createPage(sourceKind) {
  /** @type {string[]} */
  let did = [];
  const streams = [];
  const timers = new Map();
  const listeners = new Map();
  let nextTimer = 0;
  let catalogRequests = 0;

  class RecordingEventSource {
    constructor(url) {
      this.url = String(url);
      this.id = streams.length + 1;
      this.readyState = 0;
      this.closed = false;
      this.handlers = new Map();
      streams.push(this);
      did.push(`stream ${this.id}: opened ${this.url}`);
    }
    addEventListener(type, handler) {
      this.handlers.set(type, [...(this.handlers.get(type) ?? []), handler]);
    }
    close() {
      if (!this.closed) {
        this.closed = true;
        this.readyState = 2;
        did.push(`stream ${this.id}: closed`);
      }
    }
  }

  const sandbox = {
    __did: (line) => did.push(line),
    Array,
    Date,
    EventSource: RecordingEventSource,
    JSON,
    Map,
    Math,
    Number,
    Object,
    Promise,
    Set,
    String,
    METABROWSER_SOURCE_KIND: sourceKind,
    addEventListener: (type, listener) =>
      listeners.set(type, [...(listeners.get(type) ?? []), listener]),
    clearTimeout(handle) {
      if (timers.delete(handle)) {
        did.push(`timer ${handle}: cancelled`);
      }
    },
    console,
    encodeURIComponent,
    setTimeout(callback, delayMs) {
      nextTimer += 1;
      timers.set(nextTimer, { callback, delayMs });
      did.push(`timer ${nextTimer}: set for ${delayMs} ms`);
      return nextTimer;
    },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  for (const name of ["navigation.js", "catalog-feed.js"]) {
    const absolute = path.join(staticDir, name);
    vm.runInContext(fs.readFileSync(absolute, "utf8"), sandbox, { filename: absolute });
  }
  vm.runInContext(COLLABORATORS, sandbox, { filename: "page-connections-collaborators.js" });
  vm.runInContext(shellSource, sandbox, { filename: "app-page-connections.js" });
  // The production feed, as initQuickFileFinder composes it. Its first answer is the
  // catalog and every later one says nothing changed, as the server answers a page
  // whose folder did not change.
  sandbox.quickFileCatalogFeed = sandbox.MetabrowserCatalogFeed.create({
    catalog: catalogTarget(),
    fetchImpl: async (endpoint, init) => {
      if (
        catalogRequests > 0 &&
        (init?.headers?.["If-None-Match"] !== '"catalog-1"' || init?.cache !== "no-store")
      ) {
        throw new Error("reconnect must explicitly revalidate the applied catalog");
      }
      catalogRequests += 1;
      did.push(`request: GET ${endpoint}`);
      return catalogRequests === 1
        ? {
            headers: { get: () => '"catalog-1"' },
            ok: true,
            status: 200,
            text: async () => JSON.stringify({ complete: true, files: [], truncated: false }),
          }
        : { headers: { get: () => '"catalog-1"' }, ok: false, status: 304 };
    },
    yieldControl: () => Promise.resolve(),
  });

  const run = (code) => vm.runInContext(code, sandbox);
  /** An open stream; a browser delivers nothing to one that is closed or was never opened. */
  const stream = (id) => {
    const found = streams[id - 1];
    if (found && !found.closed) {
      return found;
    }
    did.push(`stream ${id}: not open, so nothing reaches it`);
    return null;
  };
  /** @type {Array<{step: string, did: string[], after: object}>} */
  const steps = [];
  const page = {
    steps,
    /** Run one step and record what the page did and what it then holds. */
    async step(name, action) {
      did = [];
      action();
      await turns();
      steps.push({
        step: name,
        did,
        after: {
          streams: streams.filter((item) => !item.closed).map((item) => item.url),
          timers: [...timers.values()].map((timer) => `${timer.delayMs} ms`),
          parked: run("pageConnections.parked()"),
        },
      });
    },
    run,
    start: () => run("startInventoryEventStream()"),
    opens(id) {
      const target = stream(id);
      if (target) {
        target.readyState = 1;
        target.onopen?.();
      }
    },
    fails(id, permanently = false) {
      const target = stream(id);
      if (target && permanently) {
        target.readyState = 2;
      }
      target?.onerror?.();
    },
    delivers(id, type, data) {
      for (const handler of stream(id)?.handlers.get(type) ?? []) {
        handler({ data: JSON.stringify(data) });
      }
    },
    /** A page lifecycle event, to every listener the shell registered for it. */
    dispatch(type, persisted) {
      for (const listener of listeners.get(type) ?? []) {
        listener({ type, persisted });
      }
    },
  };
  return page;
}

const SNAPSHOT = {
  scope: "root-depth-2",
  complete: true,
  entries: [{ path: "a.md", type: "file" }],
};

async function folderRestored() {
  const page = createPage("filesystem");
  await page.step("the page starts", () => page.start());
  await page.step("stream 1 opens and sends its snapshot", () => {
    page.opens(1);
    page.delivers(1, "fs.snapshot", SNAPSHOT);
  });
  await page.step("pagehide, kept for Back", () => page.dispatch("pagehide", true));
  await page.step("a duplicate pagehide preserves the parked connections", () =>
    page.dispatch("pagehide", true),
  );
  await page.step("a late task cannot open an event stream while parked", () => page.start());
  await page.step("pageshow, restored", () => page.dispatch("pageshow", true));
  await page.step("stream 2 opens and sends its snapshot", () => {
    page.opens(2);
    page.delivers(2, "fs.snapshot", SNAPSHOT);
  });
  await page.step("a file changes", () => {
    page.delivers(2, "fs.change", { ops: [{ op: "upsert", entry: { path: "b.md" } }] });
  });
  await page.step("pageshow, restored, with no pagehide before it", () =>
    page.dispatch("pageshow", true),
  );
  await page.step("pagehide, kept for Back again", () => page.dispatch("pagehide", true));
  await page.step("pageshow, restored again", () => page.dispatch("pageshow", true));
  await page.step("stream 3 sends the original snapshot after a change was undone", () => {
    page.opens(3);
    page.delivers(3, "fs.snapshot", SNAPSHOT);
  });
  return { scenario: "a folder's page is kept for Back and restored", steps: page.steps };
}

async function keptWhileReconnecting() {
  const page = createPage("filesystem");
  await page.step("the page starts and stream 1 opens", () => {
    page.start();
    page.opens(1);
  });
  await page.step("stream 1 fails five times", () => {
    for (let failure = 0; failure < 5; failure += 1) {
      page.fails(1);
    }
  });
  await page.step("pagehide, kept for Back", () => page.dispatch("pagehide", true));
  await page.step("pageshow, restored", () => page.dispatch("pageshow", true));
  return {
    scenario: "a page is kept for Back while its stream waits to reconnect",
    steps: page.steps,
  };
}

async function liveLogRestored() {
  const page = createPage("filesystem");
  await page.step("the page starts and stream 1 opens", () => {
    page.start();
    page.opens(1);
  });
  await page.step("a live log is opened, read to byte 120", () => {
    page.run(`
      currentPath = "run.jsonl";
      activeFiles.set("run.jsonl", { pid_alive: true });
      fileCache.set("run.jsonl", { type: "jsonl", bytes_read: 120, events: [] });
      maybeOpenLiveStream("run.jsonl", fileCache.get("run.jsonl"));
    `);
  });
  await page.step("the log grows to byte 300", () => {
    page.delivers(2, "append", { events: [{ n: 1 }], cursor: 300 });
  });
  await page.step("pagehide, kept for Back", () => page.dispatch("pagehide", true));
  await page.step("pageshow, restored", () => page.dispatch("pageshow", true));
  await page.step("the restored log no longer exists", () => page.fails(4, true));
  return { scenario: "a page tailing a live log is kept for Back and restored", steps: page.steps };
}

async function pinRestored() {
  const page = createPage("git_revision");
  await page.step("the page starts", () => page.start());
  await page.step("pagehide, kept for Back", () => page.dispatch("pagehide", true));
  await page.step("pageshow, restored", () => page.dispatch("pageshow", true));
  return { scenario: "a pin's page is kept for Back and restored", steps: page.steps };
}

async function unloaded() {
  const page = createPage("filesystem");
  await page.step("pageshow, the first load", () => page.dispatch("pageshow", false));
  await page.step("the page starts and stream 1 opens", () => {
    page.start();
    page.opens(1);
  });
  await page.step("pagehide, not kept", () => page.dispatch("pagehide", false));
  await page.step("pageshow, restored all the same", () => page.dispatch("pageshow", true));
  return { scenario: "a page is unloaded", steps: page.steps };
}

async function connectingRestored() {
  const page = createPage("filesystem");
  await page.step("the page starts but the socket has not opened", () => page.start());
  await page.step("pagehide, kept for Back", () => page.dispatch("pagehide", true));
  await page.step("pageshow, restored", () => page.dispatch("pageshow", true));
  await page.step("the fresh stream survives four errors", () => {
    for (let i = 0; i < 4; i += 1) {
      page.fails(2);
    }
  });
  return { scenario: "a connecting stream is parked and restored", steps: page.steps };
}

async function delayedInitialStreams() {
  const page = createPage("filesystem");
  await page.step("pagehide before startup completes", () => page.dispatch("pagehide", true));
  await page.step("initial streams requested while parked", () => {
    page.start();
    page.start();
    page.run(`
      currentPath = "run.jsonl";
      activeFiles.set("run.jsonl", { pid_alive: true });
      fileCache.set("run.jsonl", { type: "jsonl", bytes_read: 120, events: [] });
      maybeOpenLiveStream("run.jsonl", fileCache.get("run.jsonl"));
    `);
  });
  await page.step("pageshow, restored", () => page.dispatch("pageshow", true));
  return { scenario: "initial streams become ready while the page is parked", steps: page.steps };
}

async function main() {
  const transcript = [
    await folderRestored(),
    await keptWhileReconnecting(),
    await liveLogRestored(),
    await pinRestored(),
    await unloaded(),
    await connectingRestored(),
    await delayedInitialStreams(),
  ];
  console.log(JSON.stringify(transcript, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
