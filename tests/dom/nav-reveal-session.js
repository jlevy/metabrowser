// Browserless session: navigating to an item reveals it in the navigation pane, on the
// production code (docs/design-system.md, "Navigation Reveals the Item").
//
// `rule` is static/main-tabs.js's one rule, through its exports and the real address
// parser in static/navigation.js: which tab holds what each address names, and for each
// route, from another tab, whether the tab switches, whether its panel reveals, and
// whether the reveal scrolls. `landing` is how the shell names the route of a file's
// landing from the navigation controller's source and the landing a tab switch or a
// history step began.
//
// `tabs` loads static/main-tabs.js and static/pulls-nav.js whole over the stand-in DOM of
// tests/dom/key-reveal-dom.js and plays each route as app.js calls it: an open in the page
// (Quick Search, a link, a key), the page's own address, Back, a tab's button, a row's skim,
// and a step within the file shown. Each step prints the tab in front and what each panel
// was asked: the Files tree's reveal (app.js, `revealFileRow`), recorded, and the Pulls
// tab's view, a stand-in handle recording what the host told it. No step moves focus.
//
// `files tree` lifts app.js's tree reveal verbatim (`revealFileRow`, `revealInTree`,
// `revealWithin`, `mountTreePageHolding`, `setSelectedPath`, and the outside-filter note)
// over a stand-in tree: closed folders open, the page of a long folder that holds a row is
// mounted, a reveal that cannot show its row still takes the selection from the row that
// had it, and the note names a file only when the filter is what hides it. The page's
// mount and the folder's lazy load stand in for the renderer's.
//
// `pulls list` runs builtin_plugins/github/pulls-panel.js's controller over the recorded
// lists and stack snapshot that tests/test_github_pulls_panel_session.py records: an
// address that names a pull request in a closed stack opens the stack, the same pull
// request named again with `reveal` reveals it again, and one the list does not hold is
// named under the band.
//
// `invariants` are relations every step holds.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");
const { FakeDocument, FakeElement, element } = require("./key-reveal-dom.js");

const root = path.resolve(__dirname, "../..");
const staticDir = path.join(root, "src/metabrowser/static");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf8");

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/** A top-level function of app.js, verbatim, async or not, up to its closing brace. */
function appFunction(name) {
  const match = new RegExp(`\\n(async )?function ${name}\\(`).exec(appSource);
  if (!match) {
    throw new Error(`app.js ${name} is not extractable`);
  }
  const start = match.index + 1;
  const end = appSource.indexOf("\n}\n", start);
  return appSource.slice(start, end + 2);
}

/** A browser-like context over a stand-in document, with the named static modules loaded. */
function createContext(document, address, modules) {
  const location = new URL(address, "http://x");
  const listeners = [];
  const context = {
    Array,
    Boolean,
    Error,
    JSON,
    Map,
    Number,
    Object,
    Promise,
    Set,
    String,
    TypeError,
    URL,
    URLSearchParams,
    console,
    document,
    queueMicrotask,
    setTimeout: () => 0,
    clearTimeout() {},
    location: {
      get pathname() {
        return location.pathname;
      },
      get search() {
        return location.search;
      },
      get hash() {
        return location.hash;
      },
    },
    history: {
      state: null,
      pushState(state, _title, href) {
        context.history.state = state;
        const next = new URL(href, "http://x");
        location.pathname = next.pathname;
        location.search = next.search;
        location.hash = next.hash;
      },
      replaceState(state, title, href) {
        context.history.pushState(state, title, href);
      },
    },
    addEventListener: (type, listener) => listeners.push({ type, listener }),
    removeEventListener() {},
    go(href) {
      context.history.pushState(null, "", href);
    },
  };
  context.window = context;
  context.globalThis = context;
  vm.createContext(context);
  for (const name of modules) {
    vm.runInContext(fs.readFileSync(path.join(staticDir, name), "utf8"), context, {
      filename: path.join(staticDir, name),
    });
  }
  return context;
}

// ── The rule ──────────────────────────────────────────────────────

function ruleStory() {
  const document = new FakeDocument();
  const context = createContext(document, "/view/", ["navigation.js", "main-tabs.js"]);
  const tabs = context.MetabrowserMainTabs;
  const routes = context.MetabrowserNavigationRoute;
  const isPullAddress = (pathname) => pathname.startsWith("/pull/") || pathname === "/pulls";
  const describe = (plan) =>
    plan.tab === null
      ? "nothing"
      : [
          plan.switches ? `switch to ${plan.tab}` : `stay on ${plan.tab}`,
          plan.reveal ? `reveal, scroll ${plan.scroll}` : "no reveal",
        ].join(", ");
  const rule = {};
  for (const [address, gitLanding] of [
    ["/view/docs/deep/leaf.md", false],
    ["/view/docs/", false],
    ["/view/", false],
    ["/pull/7", false],
    ["/pull/7/files/src/app.txt", false],
    ["/pulls?state=closed", false],
    [`/commit/${"a".repeat(40)}`, false],
    ["/view/ (the neutral Commits entry)", true],
    ["/raw/notes.md", false],
  ]) {
    const url = new URL(address.split(" ")[0], "http://x");
    const tab = tabs.tabAtAddress(
      { pathname: url.pathname, search: url.search, hash: url.hash },
      { routes, isPullAddress, gitLanding },
    );
    const other = tab === "pulls" ? "files" : "pulls";
    const plans = { tab };
    for (const route of tabs.REVEAL_ROUTES) {
      plans[`${route}, from ${other}`] = describe(tabs.revealPlan(tab, route, other));
    }
    if (tab !== null) {
      plans[`open, from ${tab}`] = describe(tabs.revealPlan(tab, "open", tab));
    }
    rule[address] = plans;
  }
  let refused = null;
  try {
    tabs.revealPlan("files", "focus", "files");
  } catch (error) {
    refused = error.message;
  }
  const landing = {};
  for (const source of ["startup", "user", "popstate"]) {
    for (const pending of [null, "tab", "history", "open"]) {
      const article = pending === "open" ? "an" : "a";
      landing[`${source}${pending === null ? "" : `, after ${article} ${pending} landing`}`] =
        tabs.landingRoute(source, pending);
    }
  }
  // No route moves focus or keeps a tab's scroll but the tab's own; only a step reveals nothing.
  for (const route of tabs.REVEAL_ROUTES) {
    const plan = tabs.revealPlan("files", route, "pulls");
    assert.equal(plan.scroll === "keep", route === "tab" || route === "step", route);
    assert.equal(plan.reveal, route !== "step", route);
    assert.equal(plan.switches, true, route);
  }
  return { rule, "an unknown route": refused, landing };
}

// ── The tabs ──────────────────────────────────────────────────────

async function tabsStory() {
  const document = new FakeDocument();
  const context = createContext(document, "/view/README.md", [
    "navigation.js",
    "pull-route.js",
    "main-tabs.js",
    "pulls-nav.js",
  ]);
  const navBar = element(document, "div", { class: "nav-tab-bar", role: "tablist" });
  for (const [id, label] of [
    ["files", "Files"],
    ["pulls", "Pulls"],
    ["git", "Commits"],
  ]) {
    navBar.append(
      element(
        document,
        "button",
        {
          class: id === "files" ? "tab-btn active" : "tab-btn",
          "data-tab": id,
          role: "tab",
          type: "button",
        },
        label,
      ),
    );
  }
  const treeContent = element(
    document,
    "div",
    { id: "tree-content" },
    element(document, "div", { id: "tab-files", "data-tab-content": "files" }),
    element(document, "div", { id: "tab-pulls", "data-tab-content": "pulls" }),
  );
  const reading = element(document, "div", { id: "preview-pane", tabindex: "-1" });
  document.body.append(element(document, "nav", { class: "tree-pane" }, navBar, treeContent));
  document.body.append(reading);
  reading.focus();

  const told = [];
  let restores = 0;
  const mainTabs = context.MetabrowserMainTabs.create({
    cancelPreview: () => told.push("the pane given up"),
    filesShown() {},
    filesHidden() {},
    flushPull() {},
    focusFilesRow: () => false,
    isGitHistoryLanding: () => false,
    isPullAddress: (pathname) => pathname.startsWith("/pull/") || pathname === "/pulls",
    openRoot: () => Promise.resolve(),
    restore() {
      restores += 1;
      return Promise.resolve();
    },
    async revealFile(how) {
      told.push(`Files: reveal ${context.location.pathname}, scroll ${how.scroll}`);
    },
    scrollShadow() {},
  });
  context.mainTabs = mainTabs;
  const nav = context.MetabrowserPullsNav.createPullsNav({
    routes: context.MetabrowserPullRoute,
    location: () => ({ pathname: context.location.pathname, search: context.location.search }),
    pushHref: (href) => context.go(href),
    activeTab: () => mainTabs.active(),
    registerPanel: (panel) => mainTabs.register(panel),
    activate: (id) => mainTabs.activate(id),
    async loadView() {
      return {
        render(_container, ctx) {
          const host = ctx.pullsNav;
          told.push(`Pulls view mounted at current ${host.current}`);
          return {
            setShown() {},
            setCurrent(number, file, options = {}) {
              const how = [
                options.reveal ? "reveal" : null,
                options.preserveScroll ? "keep scroll" : null,
              ].filter(Boolean);
              told.push(
                `Pulls: current ${number}${file ? `, file ${file}` : ""}${how.length > 0 ? ` (${how.join(", ")})` : ""}`,
              );
            },
            setFilter() {},
            dispose() {},
          };
        },
      };
    },
    container: () => document.getElementById("tab-pulls"),
    scrollRoot: () => treeContent,
    pageFor: () => null,
    openPull: () => Promise.resolve({ status: "opened" }),
    schedulePrefetch: () => "prefetch",
    cancelPrefetch() {},
    showFailure() {},
  });
  context.MetabrowserPullsNav = Object.freeze({
    ...context.MetabrowserPullsNav,
    routeChanged: nav.routeChanged,
  });
  nav.start();
  // The Commits panel, which reveals a commit from its own landing (git-panel.js).
  mainTabs.register({ id: "git", label: "Commits", onFirstShow: null });
  await settle();
  told.length = 0;

  const steps = [];
  const step = async (what, act) => {
    await act();
    await settle();
    steps.push({
      step: what,
      address: context.location.pathname + context.location.search,
      tab: mainTabs.active(),
      told: told.splice(0),
    });
    assert.equal(document.activeElement, reading, `${what}: focus stays where the reader reads`);
  };
  // As app.js's routes call it: pullPageHostDeps' pushHref and replaceHref, Quick Search,
  // and applyNavigationTarget with the route main-tabs.js names for its source.
  const fileLanding = async (source, pathname, { step: within = false } = {}) => {
    if (source !== "popstate") {
      context.go(pathname);
    }
    const route = mainTabs.landingRoute(source);
    await mainTabs.reveal("step");
    if (!within) {
      await mainTabs.reveal(route);
    }
  };
  await step("Quick Search or a link opens a file from Files", () =>
    fileLanding("user", "/view/docs/deep/leaf.md"),
  );
  await step("a pull request opens by a link or Quick Search: Pulls comes to the front", () => {
    context.go("/pull/7");
    return mainTabs.reveal("open");
  });
  await step("Quick Search for the pull request shown: no new address, revealed again", () =>
    mainTabs.reveal("open"),
  );
  await step("a key skims the Pulls tab's rows: the next is revealed", () => {
    context.go("/pull/8");
    return mainTabs.reveal("nav");
  });
  await step("a changed file of #8 opens from its diff: #8 and the file are revealed", () => {
    context.go("/pull/8/files/src/app.txt");
    return mainTabs.reveal("open");
  });
  await step("a link on the page opens a file: Files comes to the front", () =>
    fileLanding("user", "/view/src/app.txt"),
  );
  await step("a fragment on the file shown is a step: nothing is revealed", () =>
    fileLanding("user", "/view/src/app.txt", { step: true }),
  );
  await step("the Pulls tab's button: its destination, with the list as it was", () =>
    mainTabs.open("pulls"),
  );
  await step("the Files tab's button: its destination, with the tree as it was", async () => {
    mainTabs.open("files");
    await fileLanding("popstate", context.location.pathname);
  });
  await step("Back to a pull request: Pulls comes to the front and reveals it", () => {
    context.go("/pull/8");
    mainTabs.onHistory();
    nav.routeChanged();
  });
  await step("Back to a file: Files comes to the front and reveals it", async () => {
    context.go("/view/src/app.txt");
    mainTabs.onHistory();
    await fileLanding("popstate", "/view/src/app.txt");
  });
  await step("a commit's address: Commits comes to the front; its panel reveals the row", () => {
    context.go(`/commit/${"b".repeat(40)}`);
    return mainTabs.reveal("address");
  });
  return { steps, "tab switches restored the address": restores };
}

// ── The Files tree ────────────────────────────────────────────────

async function filesStory() {
  const document = new FakeDocument();
  // What the lifted functions call on an element that the stand-in DOM leaves out.
  FakeElement.prototype.insertAdjacentElement ??= function insertAdjacentElement(where, node) {
    if (where === "afterbegin") {
      this.insertBefore(node, this.childNodes[0] ?? null);
    } else {
      this.parentNode.insertBefore(node, this.nextElementSibling);
    }
    return node;
  };
  const scrolled = [];
  FakeElement.prototype.scrollIntoView = function scrollIntoView() {
    scrolled.push(this.dataset.path);
  };
  const context = createContext(document, "/view/", ["tree-expansion.js"]);
  const filter = { state: { recency: "all", types: null, size: "all", showIgnored: true } };
  Object.assign(context, {
    filterState: { get: () => filter.state },
    treeKeyboard: null,
    currentPath: "",
    pendingTreePages: new Map(),
    filesPanelUsesGroupedSource: () => false,
    synchronizeTreeNow() {},
    scheduleSubtreePrefetch() {},
    loadSubtree: async () => {},
    // A page of a long folder, drawn as rows before its "more" row, which goes.
    mountNextTreePage(sentinel) {
      const page = context.pendingTreePages.get(sentinel.dataset.pageId);
      context.pendingTreePages.delete(sentinel.dataset.pageId);
      for (const node of page.nodes) {
        sentinel.parentNode.insertBefore(fileRow(node.path), sentinel);
      }
      sentinel.remove();
      return sentinel;
    },
  });
  vm.runInContext(
    [
      "escapePathForSelector",
      "queryHtml",
      "queryHtmlAll",
      "filterHasConstraints",
      "setSelectedPath",
      "renderSelectionOutsideFilterNote",
      "treeOmitsPath",
      "treePageHolds",
      "mountTreePageHolding",
      "setFolderExpanded",
      "revealWithin",
      "revealInTree",
      "revealFileRow",
    ]
      .map(appFunction)
      .join("\n"),
    context,
    { filename: "app.js (the tree's reveal)" },
  );

  const fileRow = (filePath) =>
    element(document, "div", {
      class: "tree-item tree-file",
      "data-path": filePath,
      role: "treeitem",
    });
  const folder = (folderPath, children, { open = false } = {}) => [
    element(document, "div", {
      class: `tree-item tree-folder ${open ? "expanded" : "collapsed"}`,
      "data-path": folderPath,
      "aria-expanded": String(open),
      role: "treeitem",
    }),
    element(
      document,
      "div",
      { class: `tree-children${open ? "" : " tree-children-collapsed"}`, role: "group" },
      ...children,
    ),
  ];
  const panel = element(document, "div", { id: "tab-files", "data-tab-content": "files" });
  document.body.append(panel);
  /** The tree as the filter left it. With .md files only, src and long have no rows. */
  function draw({ filtered = false } = {}) {
    context.pendingTreePages.clear();
    const long = [];
    if (!filtered) {
      for (let index = 0; index < 3; index += 1) {
        long.push(fileRow(`long/f${index}.txt`));
      }
      long.push(
        element(document, "div", {
          class: "tree-item tree-page-more",
          "data-page-id": "long-more",
          "data-action": "page-more",
        }),
      );
      context.pendingTreePages.set("long-more", {
        nodes: [{ path: "long/f3.txt" }, { path: "long/f250.txt" }],
      });
    }
    panel.replaceChildren(
      element(document, "div", { class: "tree-summary" }),
      ...folder("docs", [
        ...folder("docs/deep", [
          ...folder("docs/deep/deeper", [fileRow("docs/deep/deeper/leaf.md")]),
        ]),
        fileRow("docs/guide.md"),
      ]),
      ...(filtered ? [] : folder("long", long)),
      ...(filtered ? [] : folder("src", [fileRow("src/app.txt")])),
      fileRow("README.md"),
    );
  }
  const view = () => {
    const open = [...panel.querySelectorAll(".tree-folder")]
      .filter((row) => row.getAttribute("aria-expanded") === "true")
      .map((row) => row.dataset.path);
    return {
      open,
      selected: [...panel.querySelectorAll(".tree-item.selected")].map((row) => row.dataset.path),
      scrolled: scrolled.splice(0),
      note: panel.querySelector(".tree-selection-note")?.textContent ?? null,
    };
  };
  const steps = [];
  const reveal = async (what, filePath, scroll = "nearest") => {
    context.currentPath = filePath;
    const shown = await context.revealFileRow(filePath, { scroll, isCurrent: () => true });
    steps.push({ step: what, path: filePath, shown, ...view() });
  };
  draw();
  await reveal("a file three folders down: its folders open", "docs/deep/deeper/leaf.md");
  await reveal(
    "a tab's landing keeps the tree's place: selected, not scrolled",
    "README.md",
    "keep",
  );
  await reveal(
    "a file past a long folder's first page: the page holding it is drawn",
    "long/f250.txt",
  );
  await reveal("a path the tree does not hold, with no filter: no row stays selected", "gone.txt");
  await reveal("back to a listed file", "docs/guide.md");
  filter.state = { ...filter.state, types: [".md"] };
  draw({ filtered: true });
  await reveal(
    "a filter hides its folder: no row stays selected, and the tree says why",
    "src/app.txt",
  );
  await reveal("a file the filter keeps", "docs/deep/deeper/leaf.md");
  // The filter's own repaint closes the folders, and the selection is in one of them: the
  // tree cannot tell from its rows that the file is outside the filter, so it says nothing.
  draw({ filtered: true });
  context.renderSelectionOutsideFilterNote();
  steps.push({
    step: "a repaint closes the selection's folders: no claim it is outside the filter",
    path: context.currentPath,
    ...view(),
  });
  return steps;
}

// ── The Pulls list ────────────────────────────────────────────────

async function pullsStory() {
  const panel = await import(pathToFileURL(path.join(GITHUB, "pulls-panel.js")).href);
  const { createStackIndex } = await import(
    pathToFileURL(path.join(GITHUB, "pull-stacks.js")).href
  );
  const lists = JSON.parse(
    fs.readFileSync(path.join(root, "tests/fixtures/github-pulls-panel-responses.json"), "utf8"),
  );
  const stacks = require("../fixtures/github-stacks-responses.json");
  const rowsOf = (rows) =>
    Array.isArray(rows)
      ? rows.map((row) => JSON.parse(row))
      : [rows.same_as].flat().flatMap((holder) => rowsOf(lists[holder].body.rows));
  // The recording holds each distinct window of rows once; `same_as` names the answer that has it.
  const windows = Object.values(lists).filter((answer) => answer.body?.rows !== undefined);
  const resolved = windows.map((answer) => rowsOf(answer.body.rows));
  for (const [at, answer] of windows.entries()) {
    answer.body.rows = resolved[at];
  }
  const told = [];
  let model = null;
  const controller = panel.createPullsController(
    {
      request(method, route) {
        if (method === "GET" && route.startsWith("/api/plugin/github/pulls?")) {
          const state = new URL(route, "http://x").searchParams.get("state");
          const name = route.includes("&after=")
            ? "more_window"
            : state === "open"
              ? "open_current"
              : state === "closed"
                ? "closed_current"
                : "current";
          const answer = lists[name];
          return Promise.resolve({ status: answer.status, etag: answer.etag, body: answer.body });
        }
        return Promise.resolve({ status: 404, etag: null, body: null });
      },
      schedule: () => 0,
      cancel() {},
      now: () => Date.parse("2026-09-17T12:00:30Z"),
      isVisible: () => true,
      formatTime: (iso) => iso,
      render(next) {
        model = next;
      },
      markCurrent() {},
      markAnchor() {},
      reveal: (number) => told.push(`revealed #${number}`),
      markOutside: (text) => told.push(text === null ? "note gone" : `note: ${text}`),
      open() {},
      filterChanged() {},
    },
    { filter: "all", current: null },
  );
  await controller.start({ shown: true });
  await settle();
  controller.setStacks(createStackIndex(stacks.current.body));
  await settle();
  const stackRow = () => model.stacks.rows?.find((row) => row.kind === "stack");
  const steps = [];
  const step = async (what, act) => {
    act();
    await settle();
    steps.push({
      step: what,
      stack: stackRow() ? `${stackRow().label} ${stackRow().expanded ? "open" : "closed"}` : null,
      told: told.splice(0),
    });
  };
  told.length = 0;
  await step("the reader closes Stack #286", () => controller.setStackOpen(286, false));
  await step("an address names #7, in it: the stack opens, and #7 is revealed", () =>
    controller.setCurrent(7),
  );
  await step("the reader closes the stack again", () => controller.setStackOpen(286, false));
  await step("#7 named again, as a history step that changes nothing: nothing moves", () =>
    controller.setCurrent(7),
  );
  await step("#7 opened again, by Quick Search: the stack opens, and #7 is revealed", () =>
    controller.setCurrent(7, { reveal: true }),
  );
  await step("a tab's landing at #8 keeps the list's place: marked, not revealed", () =>
    controller.setCurrent(8, { preserveScroll: true }),
  );
  await step("under Open, the list does not hold closed #8, and says so", () =>
    controller.setFilter("open"),
  );
  await step("#10 named: listed, so revealed, and the note goes", () => controller.setCurrent(10));
  await step("#4000 named under Open: not listed", () => controller.setCurrent(4000));
  await step("under All, #4000 is still not listed, and the note names All", () =>
    controller.setFilter("all"),
  );
  await step("#6 named under All, past the rows read: the list reads on, and reveals it", () =>
    controller.setCurrent(6),
  );
  controller.dispose();
  return {
    steps,
    notes: {
      "Open, read past #8": panel.outsideText(8, "open", true),
      "Closed, read past #8": panel.outsideText(8, "closed", true),
      "All, read past #8": panel.outsideText(8, "all", true),
      "any list, not read as far as #8": panel.outsideText(8, "open", false),
    },
  };
}

(async () => {
  const transcript = {
    ...ruleStory(),
    tabs: await tabsStory(),
    "files tree": await filesStory(),
    "pulls list": await pullsStory(),
  };
  // Every Files step leaves at most one row selected, and only the path it revealed.
  for (const step of transcript["files tree"]) {
    assert.ok(step.selected.length <= 1, step.step);
    assert.ok(
      step.selected.every((selected) => selected === step.path),
      step.step,
    );
  }
  transcript.invariants = {
    "no route moves focus": true,
    "a reveal never leaves another row selected": true,
  };
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
