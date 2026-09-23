// Browserless session: the served source kind drives the production browser code.
//
// The shell learns whether it is showing an attached folder or an immutable
// Git pin from one inline block the server writes into every page. The input
// here is that block and the SPA tree exactly as the in-process application
// served them for a folder and for a pin of the same names, recorded in
// tests/fixtures/source-kind-shell.json. tests/test_source_kind_session.py
// rebuilds both subjects and fails when the recording drifts, so this session
// never runs on a source kind a test assigned by hand.
//
// Per kind, a fresh context runs the served block verbatim, then loads the
// production modules whole, the way the shell links them: navigation.js,
// plugin-sdk.js, filter-state.js, and filter-controls.js. The shell's own
// source-kind gates live in app.js, which cannot load without a document, so
// they are lifted out of it and run against those modules, as
// tree-node-name-behavior.js does. Only their collaborators that do not branch
// on the source kind are stubbed, and the stubs record what the gates asked of
// them.
//
// What the transcript shows, per kind:
// - what `metabrowser.sourceKind()` reports to plugins;
// - each tree row's rendered name and displayed location, from the real
//   payload's `name` and `path`;
// - whether Recent answers the Files panel, index progress polls, and the live
//   event stream opens, or the one-shot catalog starts instead;
// - which nav filter controls render. A pin has no mtime and no ignore state;
// - the navigation heading as served and after the tree loads. A folder's
//   heading becomes the tree root's name; a pin keeps the ref and short commit
//   the server rendered, since its tree root is the empty GitPath;
// - the heading tooltip's file count and size from the top-level rows, which
//   must equal the server's own whole-tree summary. A top-level symlink is where
//   they differ: a pin counts it as a blob, and a folder does not follow it.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf8");
const served = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/source-kind-shell.json"), "utf8"),
);

const PRODUCTION_MODULES = [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "contribution-registry.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "plugin-sdk.js",
  "filter-state.js",
  "filter-controls.js",
];

// Gates and helpers lifted verbatim from app.js.
const LIFTED = [
  "esc",
  "pathBaseHtml",
  "isGitRevisionSource",
  "renderServedRootHeading",
  "rootTallyFromTopLevel",
  "treeNodeDisplayName",
  "filesPanelUsesRecentSource",
  "startIndexProgressPolling",
  "startInventoryEventStream",
  "renderNavFilterBar",
];

// Collaborators the gates call that do not themselves branch on the source
// kind. Each records into `__probe` so the transcript shows what was asked.
const COLLABORATORS = `
var INDEX_PROGRESS_POLL_MS = 1000;
var indexProgressTimer = null;
var catalogFeedCanStart = false;
var inventoryEventSource = null;
var filterDrawerOpen = false;
var filterOpenMenu = null;
var ICONS = { toggle: "" };
var FILTER_SIZE_OPTIONS = [{ value: "1m", label: ">1M" }];
var filterState = window.metabrowser.filterState;
var filterControls = window.metabrowser.filterControls;
var quickFileCatalogFeed = {
  start() {
    __probe.catalogFeedStarts += 1;
  },
};
function refreshIndexProgress(force) {
  __probe.progressRefreshes += 1;
}
function _createInventoryEventSource() {
  __probe.eventSourcesOpened += 1;
}
function filterRecencyOptions() {
  return [{ value: "24h", label: "Past day", count: 0 }];
}
function filterTypeOptions() {
  return [];
}
function filterTypePresetSections() {
  return [];
}
`;

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function lift(name) {
  const match = appSource.match(new RegExp(`\\nfunction ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n\\}`));
  assert(match, `${name} not found in app.js`);
  return match[0];
}

function createContext() {
  const probe = {
    catalogFeedStarts: 0,
    eventSourcesOpened: 0,
    intervals: [],
    progressRefreshes: 0,
  };
  const navFilterBar = { innerHTML: "" };
  const document = {
    addEventListener() {},
    createElement() {
      return { setAttribute() {}, appendChild() {} };
    },
    getElementById(id) {
      return id === "nav-filter-bar" ? navFilterBar : null;
    },
    querySelector() {
      return null;
    },
    querySelectorAll() {
      return [];
    },
    documentElement: {},
    head: { appendChild() {} },
  };
  const sandbox = {
    __probe: probe,
    Array,
    CustomEvent: class {
      constructor(type, init) {
        this.type = type;
        this.detail = init?.detail;
      }
    },
    // Present in both contexts, so only the source kind decides whether the
    // stream opens.
    EventSource: class {},
    JSON,
    Map,
    Math,
    Number,
    Object,
    Promise,
    Set,
    String,
    TextDecoder,
    URL,
    Uint8Array,
    atob,
    btoa,
    clearInterval() {},
    clearTimeout,
    console,
    dispatchEvent() {
      return true;
    },
    document,
    encodeURIComponent,
    fetch: () => Promise.reject(new Error("fetch is unavailable in the source-kind session")),
    location: { origin: "http://127.0.0.1:8411", pathname: "/" },
    setInterval(_callback, delay) {
      probe.intervals.push(delay);
      return probe.intervals.length;
    },
    setTimeout,
    // Not source-kind specific; filter-state reads recency windows from it.
    METABROWSER_SETTINGS: {
      RECENT_WINDOW_SECONDS: { live: 90, "1h": 3600, "24h": 86400, all: null },
    },
    METABROWSER_PATH_ENCODING: "bytes",
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  return { sandbox, probe, navFilterBar };
}

function flatten(nodes, parents = []) {
  const rows = [];
  for (const node of nodes) {
    rows.push({ node, parents });
    rows.push(...flatten(node.children || [], [...parents, node]));
  }
  return rows;
}

function chipKeys(html) {
  const keys = [];
  for (const match of html.matchAll(/data-chip-(?:key|check)="([^"]+)"/g)) {
    if (!keys.includes(match[1])) {
      keys.push(match[1]);
    }
  }
  return keys;
}

function observe(kind) {
  const { shell, heading: servedHeading, root, tree, summary } = served[kind];
  const { sandbox, probe, navFilterBar } = createContext();

  // The served block runs first, exactly as the page's inline scripts do.
  for (const script of shell) {
    vm.runInContext(script, sandbox, { filename: `served-shell-${kind}.js` });
  }
  for (const name of PRODUCTION_MODULES) {
    const absolute = path.join(staticDir, name);
    vm.runInContext(fs.readFileSync(absolute, "utf8"), sandbox, { filename: absolute });
  }
  vm.runInContext(COLLABORATORS, sandbox, { filename: "source-kind-collaborators.js" });
  vm.runInContext(LIFTED.map(lift).join("\n"), sandbox, {
    filename: "app-source-kind-gates.js",
  });

  const route = sandbox.MetabrowserNavigationRoute;
  const rows = flatten(tree).map(({ node, parents }) => ({
    path: node.path,
    name: node.name,
    row: sandbox.treeNodeDisplayName(node.name),
    location: route.displayPath(node.path),
    expected: [...parents, node].map((entry) => sandbox.treeNodeDisplayName(entry.name)).join("/"),
  }));

  const { files, size } = sandbox.rootTallyFromTopLevel(tree);
  const headingTally = { files, size };
  assert(
    files === summary.files && size === summary.size,
    `${kind}: the heading counts ${files} files, ${size} bytes; the server ${summary.files}, ${summary.size}`,
  );

  // The tree's first load settles the heading, as the shell does.
  const heading = { innerHTML: servedHeading };
  sandbox.renderServedRootHeading(heading, root);

  sandbox.renderNavFilterBar();
  const navFilterControls = chipKeys(navFilterBar.innerHTML);
  sandbox.filterState.set({ recency: "24h" });
  const filesPanelUsesRecentSource = sandbox.filesPanelUsesRecentSource();
  sandbox.startIndexProgressPolling();
  sandbox.startInventoryEventStream();

  for (const row of rows) {
    // A row's location is its ancestors' rendered names joined, whichever
    // spelling the server used for the identity.
    assert(
      row.location === row.expected,
      `${kind}: ${row.path} displays as ${row.location}, not ${row.expected}`,
    );
  }
  return {
    sourceKind: sandbox.metabrowser.sourceKind(),
    shell,
    rows: rows.map(({ expected: _expected, ...row }) => row),
    heading: { served: servedHeading, afterTreeLoad: heading.innerHTML },
    tally: { heading: headingTally, server: summary },
    gates: {
      filesPanelUsesRecentSource,
      indexProgress: { refreshes: probe.progressRefreshes, intervals: probe.intervals },
      inventoryEvents: {
        eventSourcesOpened: probe.eventSourcesOpened,
        catalogFeedStarts: probe.catalogFeedStarts,
        catalogFeedCanStart: sandbox.catalogFeedCanStart,
      },
      navFilterControls,
    },
  };
}

const folder = observe("filesystem");
const pin = observe("git_revision");

assert(folder.sourceKind === "filesystem", "a folder shell did not report filesystem");
assert(pin.sourceKind === "git_revision", "a pin shell did not report git_revision");
// The same names display identically whichever subject served them.
const locations = (observed) => observed.rows.map((row) => row.location).sort();
assert(
  JSON.stringify(locations(folder)) === JSON.stringify(locations(pin)),
  "a folder and a pin of the same names display different locations",
);
assert(
  folder.gates.filesPanelUsesRecentSource && !pin.gates.filesPanelUsesRecentSource,
  "Recent must answer a bounded window on a folder and never on a pin",
);
assert(
  folder.gates.indexProgress.refreshes === 1 && pin.gates.indexProgress.refreshes === 0,
  "index progress must poll a folder's walk and never a complete pin",
);
assert(
  folder.gates.inventoryEvents.eventSourcesOpened === 1 &&
    pin.gates.inventoryEvents.eventSourcesOpened === 0 &&
    pin.gates.inventoryEvents.catalogFeedStarts === 1,
  "a pin must start the one-shot catalog instead of the live stream",
);
assert(
  folder.heading.afterTreeLoad.includes(">folder<"),
  "a folder's heading must become the served root's name",
);
assert(
  pin.heading.afterTreeLoad === pin.heading.served &&
    pin.heading.served.includes("header-revision"),
  "a pin's heading must keep the ref and commit the server rendered",
);
for (const key of ["recency", "showIgnored"]) {
  assert(folder.gates.navFilterControls.includes(key), `a folder lost the ${key} control`);
  assert(!pin.gates.navFilterControls.includes(key), `a pin offered the ${key} control`);
}

console.log(JSON.stringify([folder, pin], null, 2));
