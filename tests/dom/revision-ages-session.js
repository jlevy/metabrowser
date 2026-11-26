// Browserless session: a Git revision's page while the server reads its files' ages.
//
// The server dates a revision's files in the background and never makes a page wait for
// it, so a tree, a grouped tree, or a Recent list asked for early says `ages.state:
// "dating"` with every file undated. static/revision-ages.js watches for that state, asks
// /api/index/progress until it changes, and asks the shell to draw once more when it does
// (docs/project/architecture/arch-git.md, "File Ages"). It also says what the state is when it
// is not all dated, in the line that counts a filter's files.
//
// This runs the real module under fake timers and a scripted /api/index/progress, in
// three parts: the controller, which owns every decision, with the state each poll
// returns; `mount`, the browser glue, with a scripted `fetch` and the page's own settings;
// and the page itself, where the functions of app.js that the module meets (`observeFileAges`,
// the landing handler `rereadFiles`, and the menu's counts) are lifted out of it and
// run against the module the way the asset loader would load it. Every line below is what
// the code did: how many timers it holds, when it asked the shell to draw, and with what.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const file = path.join(repoRoot, "src/metabrowser/static/revision-ages.js");
const source = fs.readFileSync(file, "utf8");
const appSource = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/app.js"), "utf8");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

/** A page with the module loaded: fake timers that run when told to, and a clock. */
function page(extra = {}) {
  const timers = new Map();
  let nextId = 1;
  const context = vm.createContext({
    ...extra,
    setTimeout(run, ms) {
      const id = nextId++;
      timers.set(id, { run, ms });
      return id;
    },
    clearTimeout(id) {
      timers.delete(id);
    },
  });
  context.window = context;
  vm.runInContext(source, context, { filename: file });
  return {
    api: context.MetabrowserRevisionAges,
    /** Run the oldest timer, as the browser would when it fires; its poll settles after. */
    async fire() {
      const [id, timer] = timers.entries().next().value;
      timers.delete(id);
      timer.run();
      await new Promise((resolve) => setImmediate(resolve));
      return timer.ms;
    },
  };
}

const transcript = {};

async function scenario(name, answers, run, options = {}) {
  const p = page();
  let clock = 0;
  const timers = new Map();
  let nextId = 1;
  const lines = [];
  const asked = [];
  const c = p.api.createController({
    fetchState: async () => {
      asked.push("progress");
      const next = answers.shift();
      if (next instanceof Error) {
        throw next;
      }
      return next;
    },
    landed: (state) => lines.push(`landed ${JSON.stringify(state)}`),
    setTimer: (fn, ms) => {
      const id = nextId++;
      timers.set(id, { fn, ms });
      return id;
    },
    clearTimer: (id) => timers.delete(id),
    now: () => clock,
    pollMs: 500,
    ...options,
  });
  const state = () => ({
    watching: c.isWatching(),
    timers: timers.size,
    progressRequests: asked.length,
    landed: [...lines],
  });
  const env = {
    c,
    state,
    async fire() {
      const [id, timer] = timers.entries().next().value;
      timers.delete(id);
      timer.fn();
      await new Promise((resolve) => setImmediate(resolve));
    },
    advance(ms) {
      clock += ms;
    },
    delays: () => [...timers.values()].map((timer) => timer.ms),
  };
  transcript[name] = await run(env);
}

// ── The page's side: app.js's own functions, run against the real module ────────────────

function liftVar(name) {
  const match = appSource.match(new RegExp(`\\nvar ${name} = [^;]*;`));
  assert(match, `${name} not found in app.js`);
  return match[0];
}

function lift(name) {
  const match = appSource.match(new RegExp(`\\nfunction ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n\\}`));
  assert(match, `${name} not found in app.js`);
  return match[0];
}

function liftLine(text) {
  const at = appSource.indexOf(text);
  assert(at >= 0, `${text} not found in app.js`);
  return text;
}

/**
 * A page that has app.js's file-ages functions and an asset loader that runs the module when
 * asked for the `revision-ages` bundle. `events` is everything the page was asked to do.
 * *held* is what the main pane holds, as app.js's preview pane says it, and *activeView* the
 * view tab it shows.
 */
function appPage({
  held = { owner: "file", path: "docs/guide.md" },
  activeView = "rendered",
} = {}) {
  const events = [];
  const listeners = {};
  const timers = new Map();
  let nextId = 1;
  // The line that counts the files a filter keeps: there only while a filter is set.
  const line = {
    present: false,
    children: [],
    querySelector(selector) {
      return selector === ".file-ages-note" ? (line.children[0] ?? null) : null;
    },
    append(child) {
      line.children.push(child);
    },
    texts: () => line.children.map((child) => child.textContent),
  };
  const context = vm.createContext({
    __events: events,
    FILTER_RECENCY_OPTIONS: [
      { value: "24h", label: "Past day" },
      { value: "7d", label: "Past week" },
    ],
    filterState: { get: () => ({ showIgnored: true }) },
    __held: held,
    document: {
      getElementById: (id) => (id === "preview-pane" ? { dataset: { activeView } } : null),
      querySelector: (selector) =>
        selector === ".tree-summary-filtered" && line.present ? line : null,
      createElement: () => ({
        className: "",
        textContent: "",
        remove() {
          line.children = line.children.filter((child) => child !== this);
        },
      }),
    },
    CustomEvent: class {
      constructor(type, init) {
        this.type = type;
        this.detail = init?.detail;
      }
    },
    addEventListener(type, listener) {
      listeners[type] = listener;
    },
    dispatchEvent(event) {
      events.push(`event ${event.type} ${JSON.stringify(event.detail)}`);
      listeners[event.type]?.(event);
    },
    setTimeout(run, ms) {
      const id = nextId++;
      timers.set(id, { run, ms });
      return id;
    },
    clearTimeout(id) {
      timers.delete(id);
    },
    fetch: async (url) => {
      events.push(`fetch ${url}`);
      return { ok: true, json: async () => ({ ages: context.__progress }) };
    },
    METABROWSER_SETTINGS: { GIT_AGES_POLL_MS: 500 },
    __progress: { state: "dating" },
  });
  context.window = context;
  context.MetabrowserAssets = {
    ensureAsset(name) {
      events.push(`ensureAsset ${name}`);
      if (!context.MetabrowserRevisionAges) {
        vm.runInContext(source, context, { filename: file });
      }
      return Promise.resolve();
    },
  };
  vm.runInContext(
    `
var currentPath = "docs/guide.md";
var currentRecentWindow = "7d";
var _RECENT_WINDOW_SECONDS = { live: 90 };
var filterOpenMenu = null;
var _recencyTally = [];
var subtreeCache = { clear() { __events.push("subtreeCache.clear"); } };
var fileCache = { clear() { __events.push("fileCache.clear"); } };
function renderNavFilterBar() { __events.push("renderNavFilterBar"); }
function patchOpenRecencyTallyCounts() { __events.push("patchOpenRecencyTallyCounts"); }
function loadTree(options) { __events.push("loadTree " + JSON.stringify(options)); }
function loadRecent() { __events.push("loadRecent"); }
function filesPanelUsesRecentSource() { return true; }
function currentRecentFilterCursor() { return {}; }
function selectFile(path, viewId) { __events.push("selectFile " + path + " in " + viewId); return Promise.resolve(); }
var previewPane = { snapshot() { return __held; } };
${liftVar("fileAgesState")}
${[
  "refreshFilterTallies",
  "observeFileAges",
  "rereadFiles",
  "filterRecencyOptions",
  "renderRecentList",
]
  .map(lift)
  .join("\n")}
${liftLine('window.addEventListener("metabrowser:file-ages-landed", rereadFiles);')}
`,
    context,
  );
  return {
    context,
    events,
    line,
    counts: () => context.filterRecencyOptions().map((option) => option.count),
    drain: () => new Promise((resolve) => setImmediate(resolve)),
    async fire() {
      const [id, timer] = timers.entries().next().value;
      timers.delete(id);
      timer.run();
      await new Promise((resolve) => setImmediate(resolve));
      return timer.ms;
    },
    timers: () => timers.size,
    take() {
      return events.splice(0);
    },
  };
}

(async () => {
  await scenario("a response with no ages is not about file ages", [], async ({ c, state }) => {
    c.observe(undefined);
    c.observe({});
    return state();
  });

  await scenario("an answer that has landed starts no watch", [], async ({ c, state }) => {
    c.observe({ state: "ready" });
    c.observe({ state: "unavailable" });
    return state();
  });

  await scenario(
    "dating starts one watch that polls until the answer lands, then draws once",
    [{ state: "dating" }, { state: "dating" }, { state: "ready", dated: 7 }],
    async ({ c, state, fire, delays }) => {
      const steps = {};
      c.observe({ state: "dating" });
      steps.observed = { ...state(), delays: delays() };
      c.observe({ state: "dating" });
      steps.observedAgain = { ...state(), delays: delays() };
      await fire();
      steps.firstPoll = state();
      await fire();
      steps.secondPoll = state();
      await fire();
      steps.landed = state();
      return steps;
    },
  );

  await scenario(
    "a partial answer is an answer: it draws once and stops",
    [{ state: "partial", dated: 3, older_than: 1700000000 }],
    async ({ c, state, fire }) => {
      c.observe({ state: "dating" });
      await fire();
      return state();
    },
  );

  await scenario(
    "a failed read is an answer too: the page is told, and asks no more",
    [{ state: "failed", reason: "git_failed" }],
    async ({ c, state, fire }) => {
      c.observe({ state: "dating" });
      await fire();
      return state();
    },
  );

  await scenario(
    "a poll that fails is asked again, and the answer it then gets lands",
    [new Error("offline"), new Error("offline"), { state: "ready" }],
    async ({ c, state, fire }) => {
      const steps = {};
      c.observe({ state: "dating" });
      await fire();
      steps.firstFailure = state();
      await fire();
      steps.secondFailure = state();
      await fire();
      steps.landed = state();
      return steps;
    },
  );

  await scenario(
    "a poll that keeps failing ends the watch without drawing",
    [new Error("down"), new Error("down"), new Error("down"), new Error("down")],
    async ({ c, state, fire }) => {
      const steps = {};
      c.observe({ state: "dating" });
      for (const step of ["first", "second", "third"]) {
        await fire();
        steps[step] = state();
      }
      await fire();
      steps.gaveUp = state();
      return steps;
    },
  );

  await scenario(
    "a response that says the answer landed while the watch runs is the landing",
    [],
    async ({ c, state }) => {
      c.observe({ state: "dating" });
      c.observe({ state: "ready" });
      return state();
    },
  );

  await scenario(
    "a response that says it landed with no watch running draws nothing",
    [],
    async ({ c, state }) => {
      c.observe({ state: "ready" });
      c.observe({ state: "partial" });
      return state();
    },
  );

  await scenario(
    "a watch that outlasts the bound the settings give it gives up",
    [{ state: "dating" }, { state: "dating" }],
    async ({ c, state, fire, advance }) => {
      const steps = {};
      c.observe({ state: "dating" });
      advance(99_000);
      await fire();
      steps.insideTheBound = state();
      advance(2_000);
      await fire();
      steps.pastTheBound = state();
      return steps;
    },
    { giveUpMs: 100_000 },
  );

  // Part two: the glue the page runs, with its own fetch and settings.
  const asked = [];
  const answers = [{ ages: { state: "dating" } }, { ages: { state: "partial", dated: 2 } }];
  const landed = [];
  const glue = page({
    METABROWSER_SETTINGS: { GIT_AGES_POLL_MS: 250, GIT_AGES_WATCH_GIVE_UP_MS: 1_000 },
    async fetch(url, options) {
      asked.push({ url, options });
      return { ok: true, json: async () => answers.shift() };
    },
  });
  const mounted = glue.api.mount({ reload: (state) => landed.push(state) });
  mounted.observe({ state: "dating" });
  const delays = [];
  delays.push(await glue.fire());
  delays.push(await glue.fire());
  transcript["the page's glue asks the progress route at the settings' pace"] = {
    delays,
    asked,
    landed,
    watching: mounted.isWatching(),
  };

  // The words the line that counts a filter's files adds for each state.
  const notes = glue.api.noteText;
  transcript["what the filtered count says of each state"] = {
    absent: notes(undefined),
    ready: notes({ state: "ready" }),
    dating: notes({ state: "dating" }),
    failedGit: notes({ state: "failed", reason: "git_failed" }),
    failedTooMany: notes({ state: "failed", reason: "too_many_files" }),
    failedUnknown: notes({ state: "failed" }),
    partialShallow: notes({
      state: "partial",
      files: 40,
      dated: 3,
      older_than: 1700000000,
      stop: "boundary",
    }),
    partialCut: notes({
      state: "partial",
      files: 40,
      dated: 30,
      older_than: 1700000000,
      stop: "budget",
    }),
    partialOne: notes({ state: "partial", files: 4, dated: 3, stop: "boundary" }),
    partialFilteredList: notes({ state: "partial", files: 40, dated: 3, stop: "boundary" }, 7),
    partialNoneInTheList: notes({ state: "partial", files: 40, dated: 3, stop: "boundary" }, 0),
  };

  // Part three: the page's own functions with the module the asset loader brings.
  {
    const app = appPage();
    const steps = {};
    app.context.observeFileAges({ state: "ready" });
    steps.aWholeAnswerAsksForNothing = { events: app.take(), counts: app.counts() };

    app.context.observeFileAges(undefined);
    steps.aResponseWithNoAgesAsksForNothing = { events: app.take(), timers: app.timers() };

    // No filter is set, so there is no line to say anything in, and nothing is added to move
    // the tree.
    app.context.observeFileAges({ state: "dating", files: 6 });
    await app.drain();
    steps.theFirstResponseSaysDatingWithNoFilterSet = {
      events: app.take(),
      menuCounts: app.counts(),
      tallyLine: app.line.texts(),
      timers: app.timers(),
    };

    // A filter is set: the line the shell draws for it gets the clause, as one more item.
    app.line.present = true;
    app.context.MetabrowserRevisionAges.annotate();
    steps.theShellDrawsTheFilteredLine = { tallyLine: app.line.texts() };

    // The poll finds the answer: the shell redraws what was drawn without ages, once; the
    // tree it asks for says `ready`, which ends the watch's note and the menu's pending marks.
    app.context.__progress = { state: "ready", files: 6, dated: 6 };
    await app.fire();
    steps.theAnswerLands = { events: app.take() };
    app.context.observeFileAges({ state: "ready", files: 6, dated: 6 });
    app.context._recencyTally = [
      ["24h", 2, 0],
      ["7d", 5, 0],
    ];
    steps.theRedrawnTreeSaysReady = {
      events: app.take(),
      menuCounts: app.counts(),
      tallyLine: app.line.texts(),
      timers: app.timers(),
    };

    // A page opened after the read failed is told so, and keeps no watch.
    const failed = appPage();
    failed.line.present = true;
    failed.context.observeFileAges({ state: "failed", reason: "git_failed" });
    await failed.drain();
    steps.aFailedReadIsSaid = {
      events: failed.take(),
      tallyLine: failed.line.texts(),
      timers: failed.timers(),
    };

    // A Recent list of a shallow clone counts the files it could not date.
    const shallow = appPage();
    shallow.line.present = true;
    shallow.context.observeFileAges(
      { state: "partial", files: 40, dated: 3, older_than: 1700000000, stop: "boundary" },
      37,
    );
    await shallow.drain();
    steps.aShallowHistoryIsSaid = { tallyLine: shallow.line.texts(), timers: shallow.timers() };
    // The shell draws the line again, as it does for every response: one clause, not two.
    shallow.context.MetabrowserRevisionAges.annotate();
    shallow.context.MetabrowserRevisionAges.annotate();
    steps.theLineIsDrawnAgainWithOneClause = { tallyLine: shallow.line.texts() };

    // The Recent list with nothing in it says why, as the state of the ages has it.
    const lists = appPage();
    const emptyLine = () => lists.context.renderRecentList({ tree: [] });
    steps.theRecentListSaysWhyItIsEmpty = { whole: emptyLine() };
    lists.context.observeFileAges({ state: "dating" });
    steps.theRecentListSaysWhyItIsEmpty.dating = emptyLine();
    lists.context.observeFileAges({ state: "failed", reason: "git_failed" });
    steps.theRecentListSaysWhyItIsEmpty.failed = emptyLine();
    lists.context.observeFileAges({ state: "ready" });
    steps.theRecentListSaysWhyItIsEmpty.ready = emptyLine();

    // A menu open while the state changes keeps its focus: only its counts change.
    const open = appPage();
    open.context.filterOpenMenu = "recency";
    open.context.observeFileAges({ state: "dating" });
    await open.drain();
    steps.anOpenMenuOnlyHasItsCountsPatched = { events: open.take() };

    // The landing, or the navigation's Refresh (static/refresh-plan.js), reads again what the
    // pane holds, in the view it shows, so a file in Source stays in Source; a pane that
    // holds no file or folder, a pull request's page say, or nothing yet, is left as it is.
    const reread = async (held, activeView) => {
      const app = appPage({ held, activeView });
      await app.context.rereadFiles();
      return app.take();
    };
    steps.aRereadKeepsWhatThePaneShows = {
      aFileInSource: await reread({ owner: "file", path: "docs/guide.md" }, "source"),
      aFolderInTreemap: await reread({ owner: "file", path: "docs" }, "treemap"),
      aPullRequestPage: await reread({ owner: "pull-request", path: "7" }, "conversation"),
      nothingChosen: await reread({ owner: "file", path: null }, undefined),
    };
    const rereads = steps.aRereadKeepsWhatThePaneShows;
    assert(
      rereads.aFileInSource.includes("selectFile docs/guide.md in source"),
      "a reread keeps the view the pane shows",
    );
    assert(
      !rereads.aPullRequestPage
        .concat(rereads.nothingChosen)
        .some((e) => e.startsWith("selectFile")),
      "a reread opens no file in a pane that holds none",
    );
    transcript["the page's own functions meet the module"] = steps;
  }

  // Part four: the Recent list of a revision names its folders as a person reads them. A
  // row's path is a GitPath wire, whose segments are encoded, so the server sends the
  // folders' names beside it (`dir_names`); a folder's own rows have none and are named by
  // their path.
  {
    const sandbox = { Array, Date, Map, Math, Object, Set, String, encodeURIComponent };
    sandbox.window = sandbox;
    sandbox.globalThis = sandbox;
    sandbox.METABROWSER_SETTINGS = { RECENT_WINDOW_SECONDS: { all: null } };
    sandbox.metabrowser = { prefs: { remove() {} } };
    sandbox.dispatchEvent = () => {};
    sandbox.CustomEvent = function CustomEvent() {};
    vm.createContext(sandbox);
    for (const relative of ["filter-state.js", "tree-filter-model.js"]) {
      const filename = path.join(repoRoot, "src/metabrowser/static", relative);
      vm.runInContext(fs.readFileSync(filename, "utf8"), sandbox, { filename });
    }
    const nowSec = 2_000_000_000;
    const state = { recency: "all", types: [], size: "all", showIgnored: true };
    const named = (entries) => {
      let view = null;
      sandbox.MetabrowserTreeFilterModel.renderRecentView(
        entries,
        {
          filterState: sandbox.metabrowser.filterState,
          ignoredDirectoryPaths: new Set(),
          limit: 50,
          nowSec,
          clusterPct: 0.05,
          state,
        },
        (projection) => {
          view = projection;
        },
      );
      const folders = [];
      const walk = (nodes) => {
        for (const node of nodes) {
          if (node.type === "dir") {
            folders.push({ name: node.name, path: node.path });
            walk(node.children ?? []);
          }
        }
      };
      walk(view.tree);
      return folders;
    };
    transcript["a revision's Recent list names its folders by their names"] = {
      withDirNames: named([
        {
          path: "g1-ZG9j/g1-Z3VpZGUubWQ",
          name: "guide.md",
          type: "file",
          ext: ".md",
          size: 3,
          mtime: nowSec - 5,
          dir_names: ["doc"],
        },
      ]),
      aFoldersOwnRows: named([
        {
          path: "doc/guide.md",
          name: "guide.md",
          type: "file",
          ext: ".md",
          size: 3,
          mtime: nowSec - 5,
        },
      ]),
    };
  }

  console.log(JSON.stringify(transcript, null, 2));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
