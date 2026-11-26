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
// tests/dom/key-reveal-dom.js, with app.js's pull-request routes lifted verbatim (the page
// host's address writes, `revealPullAddress`, and Quick Search's `openQuickSearchPull`),
// and plays each route as app.js calls it: an open in the page (Quick Search, a link, a
// key), the page's own address, Back, a tab's button, a row's skim, and a step within the
// item shown, a fragment of a file or another tab or changed file of a pull request. Each
// step prints the tab in front and what each panel was asked: the Files tree's reveal
// (app.js, `revealFileRow`), recorded, and what the host told the Pulls tab's view, whose
// own controller (builtin_plugins/github/pulls-panel.js) says when it reveals a row. A
// step within the pull request shown reveals no row, and an open of it again does. No
// step moves focus.
//
// `files tree` lifts app.js's tree reveal and page mounting verbatim (`revealFileRow`,
// `revealInTree`, `revealWithin` and its scroll, `mountTreePageHolding`, `mountTreePageAt`,
// `mountNextTreePage`, `setSelectedPath`, and the outside-filter note), and its insert of
// a file that arrives while the page is open (`_insertRowSorted` and the "more" rows'
// totals), over a stand-in tree: closed folders open; in a folder of 1,400 files only the
// page that holds the row is drawn, with the pages before and after it behind "more" rows
// of their own, which draw in order where they are; one above the reader's row grows up,
// and one below grows down, with focus on its first row, after a second reveal too; an
// arrival counts in every "more" row, and one that sorts last goes last; a reveal that
// cannot show its row still takes the selection from the row that had it; the note
// names a file only when the filter is what hides it; and a landing whose folder is still
// opening scrolls its row once the folder's travel ends, not before, and only while the
// address names it and the folder is open, to the row drawn in its place if it was drawn
// again, while an endless animation holds no scroll. The renderer stands in for
// renderTreeNodes, deferredTreePageHtml and _buildRowHtml, paging as they do
// (TREE_PAGE_SIZE rows, then a "more" row), as the folder's lazy load stands in for the
// server's.
//
// `pulls list` runs builtin_plugins/github/pulls-panel.js's controller over the recorded
// lists and stack snapshot that tests/test_github_pulls_panel_session.py records: an
// address that names a pull request in a closed stack opens the stack, the same pull
// request named again moves nothing unless `again` says it was opened again, `again` ends
// a tab landing's kept place, one the filter leaves out moves the list to a filter that
// draws it, a filter the reader picks says nothing of the pull request it leaves out, and
// only one the list still cannot show is named under the band. `beyond the rows read`, the
// part `pulls-depth` prints, serves lists longer than the panel draws, with the pages a
// reader scrolls in, a catalog still being read from GitHub, a pull request opened since
// its last read, failing reads, a number the route refuses, and slow answers that come
// after a newer navigation, a filter the reader picks, or the panel was hidden, over the
// route's windows and the catalog's one-row lookups; a row the list moved for takes focus
// only while focus is where the move left it.
//
// `a link's address`, the part `links` prints, opens by a plain click on a link in a text
// an address Pulls or Commits holds, through the SDK's `navigation.openRoute` and
// static/main-tabs.js's `openRoute` over the same tabs: a commit, another commit, a pull
// request, another tab of the one shown, another pull request, the list, and a stack's
// page, each pushing one entry and landing as a tab's destination lands, and the addresses
// it leaves to the browser, which move, write, and tell nothing.
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
      get href() {
        return location.href;
      },
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

/**
 * The shell's navigation pane over *document*: its three tabs with Files in front, the
 * scroller that holds their panels, and the reading pane, which has focus.
 */
function navigationPane(document) {
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
  return { treeContent, reading };
}

/**
 * static/pulls-nav.js's tab under *mainTabs*, whose view is the Pulls panel's own
 * controller over the recorded lists: it decides whether a row is revealed, and what the
 * host tells the view is *told* as it is told.
 */
function pullsTab(context, document, mainTabs, treeContent, told) {
  const nav = context.MetabrowserPullsNav.createPullsNav({
    routes: context.MetabrowserPullRoute,
    location: () => ({ pathname: context.location.pathname, search: context.location.search }),
    pushHref: (href) => context.go(href),
    activeTab: () => mainTabs.active(),
    registerPanel: (panel) => mainTabs.register(panel),
    activate: (id) => mainTabs.activate(id),
    // The Pulls tab's view: the panel's own controller over the recorded lists, which decides
    // whether a row is revealed; what the host tells the view is printed as it is told.
    async loadView() {
      return {
        async render(_container, ctx) {
          const host = ctx.pullsNav;
          told.push(`Pulls view mounted at current ${host.current}`);
          const controller = await recordedPullsController(
            { reveal: (number) => told.push(`Pulls: #${number} revealed`) },
            { current: host.current },
          );
          void controller.start({ shown: host.shown });
          return {
            setShown: (shown) => controller.setShown(shown),
            setCurrent(number, file, options = {}) {
              const how = Object.entries(options)
                .filter(([, value]) => value === true)
                .map(([name]) => (name === "preserveScroll" ? "keep scroll" : name));
              told.push(
                `Pulls: current ${number}${file ? `, file ${file}` : ""}${how.length > 0 ? ` (${how.join(", ")})` : ""}`,
              );
              controller.setCurrent(number, options);
            },
            setFilter() {},
            dispose: () => controller.dispose(),
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
  return nav;
}

async function tabsStory() {
  const document = new FakeDocument();
  const context = createContext(document, "/view/README.md", [
    "navigation.js",
    "pull-route.js",
    "main-tabs.js",
    "pulls-nav.js",
  ]);
  const { treeContent, reading } = navigationPane(document);

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
    openHome: () => Promise.resolve(),
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
  const nav = pullsTab(context, document, mainTabs, treeContent, told);
  // The Commits panel, which reveals a commit from its own landing (git-panel.js).
  mainTabs.register({ id: "git", label: "Commits", onFirstShow: null });
  await settle();
  told.length = 0;

  // app.js's pull-request routes, lifted verbatim: the page host's address writes
  // (pullPageHostDeps, revealPullAddress) and Quick Search's open (openQuickSearchPull),
  // over stand-ins for the pane they claim.
  vm.runInContext(
    [
      "var mainTabIntent = 0;",
      "var previewPane = { snapshot: () => ({ claim: 1 }) };",
      "function isPreviewClaimCurrent() { return true; }",
      "function renderPreviewHtml() {}",
      "function beginPreviewNavigation() {}",
      "function endPreviewNavigation() {}",
      "function stagePreviewNode() {}",
      "function showPullPageLoadFailure() {}",
      ...["pullPageHostDeps", "revealPullAddress", "openQuickSearchPull"].map(appFunction),
    ].join("\n"),
    context,
    { filename: "app.js (the pull-request routes)" },
  );
  const routes = context.MetabrowserPullRoute;
  const hostDeps = context.pullPageHostDeps(routes);
  // pull-route.js's host `open`: the address is written when it moves, pushed, or replaced
  // for a key's skim, through the deps app.js gives the host.
  const host = {
    async open(route) {
      const href = routes.pullHref(route.number, route.tab, route.file ?? "");
      if (hostDeps.pathname() !== href) {
        if (route.replace === true) {
          hostDeps.replaceHref(href);
        } else {
          hostDeps.pushHref(href);
        }
      }
      return { status: "opened" };
    },
  };
  context.loadPullPageHost = async () => host;

  const steps = [];
  /** *reveals*: whether the Pulls tab's row is revealed, for a step that names a pull request. */
  const step = async (what, act, { reveals = null } = {}) => {
    await act();
    await settle();
    const said = told.splice(0);
    steps.push({
      step: what,
      address: context.location.pathname + context.location.search,
      tab: mainTabs.active(),
      told: said,
    });
    assert.equal(document.activeElement, reading, `${what}: focus stays where the reader reads`);
    if (reveals !== null) {
      assert.equal(
        said.some((line) => line.endsWith(" revealed")),
        reveals,
        `${what}: ${reveals ? "the row is revealed" : "no row is revealed"} (${said.join("; ")})`,
      );
    }
  };
  // As app.js's routes call it: the page host's writes and Quick Search, lifted above, and
  // applyNavigationTarget with the route main-tabs.js names for its source.
  const fileLanding = async (source, pathname, { step: within = false } = {}) => {
    if (source !== "popstate") {
      context.go(pathname);
    }
    const route = mainTabs.landingRoute(source);
    const switching = mainTabs.reveal("step");
    // The list is told of every file's address: it names no pull request.
    context.MetabrowserPullsNav.routeChanged();
    await switching;
    if (!within) {
      await mainTabs.reveal(route);
    }
  };
  await step("Quick Search or a link opens a file from Files", () =>
    fileLanding("user", "/view/docs/deep/leaf.md"),
  );
  await step(
    "a link opens a pull request: Pulls comes to the front and reveals it",
    () => host.open({ number: 7, tab: "" }),
    { reveals: true },
  );
  await step(
    "Quick Search for the pull request shown: no new address, revealed again",
    () => context.openQuickSearchPull(7),
    { reveals: true },
  );
  await step(
    "a key skims the Pulls tab's rows: the next is revealed",
    () => host.open({ number: 8, tab: "", replace: true }),
    { reveals: true },
  );
  await step(
    "another tab of #8's page: a step within it, nothing is revealed",
    () => host.open({ number: 8, tab: "files" }),
    { reveals: false },
  );
  await step(
    "a changed file of #8 opens from its diff: the list is told, nothing is revealed",
    () => host.open({ number: 8, tab: "files", file: "src/app.txt" }),
    { reveals: false },
  );
  await step(
    "J walks #8's changed files: the next replaces it, nothing is revealed",
    () => host.open({ number: 8, tab: "files", file: "src/b.txt", replace: true }),
    { reveals: false },
  );
  await step(
    "Quick Search for #8 from one of its files: its page opens, and #8 is revealed again",
    () => context.openQuickSearchPull(8),
    { reveals: true },
  );
  await step("a link on the page opens a file: Files comes to the front", () =>
    fileLanding("user", "/view/src/app.txt"),
  );
  await step("a fragment on the file shown is a step: nothing is revealed", () =>
    fileLanding("user", "/view/src/app.txt", { step: true }),
  );
  await step(
    "the Pulls tab's button: its destination, with the list as it was",
    () => mainTabs.open("pulls"),
    { reveals: false },
  );
  await step(
    "Quick Search for the pull request shown after the tab's button: revealed again",
    () => context.openQuickSearchPull(8),
    { reveals: true },
  );
  await step("the Files tab's button: its destination, with the tree as it was", async () => {
    mainTabs.open("files");
    await fileLanding("popstate", context.location.pathname);
  });
  await step(
    "Back to a pull request: Pulls comes to the front and reveals it",
    () => {
      context.go("/pull/8");
      mainTabs.onHistory();
      nav.routeChanged();
    },
    { reveals: true },
  );
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

// ── A link's address ──────────────────────────────────────────────

/**
 * A link in a text opens an address Pulls or Commits holds in place, through the SDK's
 * `navigation.openRoute` (static/navigation.js) and the tab controller's `openRoute`
 * (static/main-tabs.js), loaded whole with static/pull-route.js and static/pulls-nav.js, as
 * a plain click on such a link asks it (static/repository-links.js, `enhance`, and the
 * Markdown plugin's link-enhancer.js). Each step prints its answer, the address and the tab
 * in front after it, how many history entries it pushed, and what the shell's parts were
 * asked: a pull request's page writing its place into its entry, the pane given up on a
 * switch of tab, the pane applying the address (app.js's `applyNavigationTarget`, which the
 * controller's `restore` runs), the Commits panel's landing (git-panel.js's
 * `restoreCommitLanding`, the one Back runs), and what the Pulls tab's view was told.
 */
async function linksStory() {
  const document = new FakeDocument();
  const context = createContext(document, "/view/README.md", [
    "navigation.js",
    "pull-route.js",
    "main-tabs.js",
    "pulls-nav.js",
  ]);
  const { treeContent, reading } = navigationPane(document);
  const navigation = context.MetabrowserNavigationRoute.navigation;
  const routes = context.MetabrowserPullRoute;
  const told = [];
  let pushed = 0;
  const write = context.history.pushState;
  context.history.pushState = (state, title, href) => {
    pushed += 1;
    write(state, title, href);
  };
  context.history.replaceState = write;
  // The Commits panel's landing on a commit's address, as Back and a tab's switch run it.
  context.MetabrowserGitPanel = {
    async restoreCommitLanding() {
      const commit = context.MetabrowserNavigationRoute.parseCommit(context.location.pathname);
      if (commit !== null) {
        told.push(`Commits: selects ${commit.revision.slice(0, 7)} and reveals its row`);
      }
    },
  };
  const address = () => `${context.location.pathname}${context.location.search}`;
  /** @type {ReturnType<typeof context.MetabrowserMainTabs.create> | null} */
  let mainTabs = null;

  const steps = [];
  const refused = [];
  /** A plain click on a link to *href*: *reveals*, for one that names a pull request. */
  const click = async (what, href, { reveals = null } = {}) => {
    const before = {
      address: address(),
      hash: context.location.hash,
      tab: mainTabs?.active() ?? "files",
      pushed,
    };
    const opened = navigation.openRoute(href);
    await settle();
    // The Pulls view tells the reveal its own read of the list makes and the current row
    // the host gives it, which nothing orders against each other (its controller starts
    // unawaited, as pulls-panel.js mounts it), so its lines are kept together, sorted,
    // after the shell's, which keep their order.
    const said = told.splice(0);
    const view = said.filter((line) => line.startsWith("Pulls: ")).sort();
    said.splice(0, said.length, ...said.filter((line) => !line.startsWith("Pulls: ")), ...view);
    const after = { address: address(), tab: mainTabs?.active() ?? "files" };
    assert.equal(document.activeElement, reading, `${what}: focus stays where the reader reads`);
    if (!opened) {
      // The browser follows the link: nothing here moved, wrote, or was told.
      assert.deepEqual(after, { address: before.address, tab: before.tab }, what);
      assert.equal(pushed, before.pushed, what);
      assert.deepEqual(said, [], what);
      refused.push({ link: what, href });
      return;
    }
    // One entry, the link's own address, as a click on any link pushes; a link to the
    // address shown opens it again where it is, and pushes none, as `navigation.open` and
    // a pull request's page push none for the address shown.
    const again = `${before.address}${before.hash}` === href;
    assert.equal(pushed - before.pushed, again ? 0 : 1, what);
    assert.equal(`${after.address}${context.location.hash}`, href, what);
    if (reveals !== null) {
      assert.equal(
        said.some((line) => line.endsWith(" revealed")),
        reveals,
        `${what}: ${reveals ? "the row is revealed" : "no row is revealed"} (${said.join("; ")})`,
      );
    }
    steps.push({ step: what, href, address: after.address, tab: after.tab, told: said });
  };

  await click("the list, before the shell tools have loaded: no controller opens it", "/pulls");
  mainTabs = context.MetabrowserMainTabs.create({
    cancelPreview: () => told.push("the pane given up"),
    filesShown() {},
    filesHidden() {},
    // app.js's flushPull: only a pull request's page holding the pane has a place to write.
    flushPull() {
      const page = routes.parsePull(context.location.pathname);
      if (page !== null) {
        told.push(`#${page.number}'s page writes its place into its entry`);
      }
    },
    focusFilesRow: () => false,
    isGitHistoryLanding: () => false,
    isPullAddress: (pathname) => /^\/(pull|stack)\//.test(pathname) || pathname === "/pulls",
    openHome: () => Promise.resolve(),
    restore() {
      told.push(`the pane shows ${address()}`);
      return Promise.resolve();
    },
    async revealFile(how) {
      told.push(`Files: reveal ${context.location.pathname}, scroll ${how.scroll}`);
    },
    scrollShadow() {},
  });
  pullsTab(context, document, mainTabs, treeContent, told);
  await settle();
  told.length = 0;
  await click(
    "a commit, before Git discovery has registered the Commits tab",
    `/commit/${"b".repeat(40)}`,
  );
  mainTabs.register({ id: "git", label: "Commits", onFirstShow: null });
  await settle();
  told.length = 0;

  await click(
    "a Markdown file links a commit: Commits comes to the front and its panel selects it",
    `/commit/${"b".repeat(40)}`,
  );
  await click(
    "the commit's message links another commit: Commits stays, and its panel claims the pane",
    `/commit/${"c".repeat(40)}`,
  );
  await click(
    "the message links a pull request: Pulls comes to the front and reveals it",
    "/pull/8",
    { reveals: true },
  );
  await click(
    "a document drawn in #8's Changes links #8's Changes: a step within it, nothing revealed",
    "/pull/8/files",
    { reveals: false },
  );
  await click("the same document links #7: its row is revealed", "/pull/7", { reveals: true });
  await click(
    "#7's description links a commit: its page writes its place, and Commits comes to the front",
    `/commit/${"b".repeat(40)}#diff`,
  );
  await click(
    "the commit's message links the list: Pulls comes to the front, and the pane shows it",
    "/pulls",
    { reveals: false },
  );
  await click("a link opens a stack's page", "/stack/3", { reveals: false });
  // A link to the address shown, as a document in a page's own Changes links that page.
  await click("a link to the stack's page shown opens it again, pushing nothing", "/stack/3");
  await click("a link opens the list", "/pulls", { reveals: false });
  await click("a link to the list shown opens it again, pushing nothing", "/pulls");
  await click("a link opens a changed file of #8", "/pull/8/files/docs/a%20b.md");
  await click(
    "a link to the changed file shown opens it again, pushing nothing",
    "/pull/8/files/docs/a%20b.md",
  );

  // Each leaves the browser to follow the link.
  for (const [what, href] of [
    ["a file's address, which navigation.open opens", "/view/docs/guide.md"],
    ["the served root's", "/view/"],
    ["an address on another origin", "https://example.com/pulls"],
    ["a protocol-relative address, on another origin", "//example.com/pull/8"],
    ["a backslash the URL parser reads as a second slash", "/\\example.com/pulls"],
    ["GitHub's page that opens a pull request, which the routes do not read", "/pull/new/topic"],
    ["a pull request numbered 0", "/pull/0"],
    ["a tab a stack's page does not have", "/stack/3/checks"],
    ["a commit's address with no revision", "/commit/"],
    ["an address no tab holds", "/raw/notes.md"],
    ["no URL at all", "http://["],
  ]) {
    await click(what, href);
  }
  return { opened: steps, "the browser follows": refused };
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
    scrolled.push(
      this.isConnected ? this.dataset.path : `${this.dataset.path}, a row gone from the tree`,
    );
  };
  // The stand-in tree lays nothing out, so it has no disclosure travel, and a reveal
  // scrolls at once (folderTravelAbove), until the story gives one folder body the
  // animations of a travel whose end it says (`travelling`). A real travel is
  // tests/dom/nav-reveal-chrome.mjs's.
  let travelling = null;
  FakeElement.prototype.getAnimations = function getAnimations() {
    return travelling?.body === this ? travelling.animations : [];
  };
  const context = createContext(document, "/view/", ["tree-expansion.js"]);
  const filter = { state: { recency: "all", types: null, size: "all", showIgnored: true } };
  const TREE_PAGE_SIZE = Number(/\nconst TREE_PAGE_SIZE = (\d+);/.exec(appSource)[1]);
  // A file's row, with the name a live insert sorts by and the total it was drawn with.
  const rowHtml = (filePath, setSize) =>
    `<div class="tree-item tree-file" data-path="${filePath}" data-tree-set-size="${setSize}"` +
    ` role="treeitem"><span class="tree-item-name">${filePath.split("/").pop()}</span></div>`;
  let pageIds = 0;
  Object.assign(context, {
    TREE_PAGE_SIZE,
    filterState: { get: () => filter.state },
    treeKeyboard: null,
    currentPath: "",
    pendingTreePages: new Map(),
    filesPanelUsesGroupedSource: () => false,
    synchronizeTreeNow() {},
    scheduleSubtreePrefetch() {},
    loadSubtree: async () => {},
    // The renderer, paging as production's renderTreeNodes does: a folder's first
    // TREE_PAGE_SIZE rows, then a "more" row that holds back the rest.
    renderTreeNodes(nodes, _isRoot, options) {
      const offset = options.positionOffset || 0;
      return (
        nodes
          .slice(0, TREE_PAGE_SIZE)
          .map((node) => rowHtml(node.path, options.setSize))
          .join("") +
        context.deferredTreePageHtml(nodes.slice(TREE_PAGE_SIZE), {
          ...options,
          positionOffset: offset + TREE_PAGE_SIZE,
        })
      );
    },
    deferredTreePageHtml(nodes, options) {
      if (nodes.length === 0) {
        return "";
      }
      const pageId = `page-${++pageIds}`;
      context.pendingTreePages.set(pageId, { nodes, options });
      return (
        `<div class="tree-item tree-page-more" data-page-id="${pageId}" data-action="page-more"` +
        ` role="treeitem" aria-labelledby="${pageId}-label"><span id="${pageId}-label">` +
        `Show ${nodes.length} more (${options.setSize} total)</span></div>`
      );
    },
    withTreeIdScope: (_scope, build) => build(),
    applyTreeFilters() {},
    reconcilePendingTallyDiagnostics() {},
    // A row that arrives while the page is open, drawn as the renderer draws one.
    _buildRowHtml: (entry, options) => rowHtml(entry.path, options.setSize),
    scheduleTreeSynchronize() {},
  });
  vm.runInContext(
    [
      "escapePathForSelector",
      "queryHtml",
      "queryHtmlAll",
      "filterHasConstraints",
      "setSelectedPath",
      "renderSelectionOutsideFilterNote",
      "addFilesRemark",
      "filesMetadataBand",
      "treeOmitsPath",
      "treePageHolds",
      "selectedTreeRowFollows",
      "mountNextTreePage",
      "_labelDeferredTreePage",
      "mountTreePageAt",
      "mountTreePageHolding",
      "setFolderExpanded",
      "revealWithin",
      "folderTravelAbove",
      "revealInTree",
      "revealFileRow",
      // A file that arrives while the page is open (the live inventory's insert).
      "treeLevelForContainer",
      "_treeSortKey",
      "_treeKeyCmp",
      "_deferredTreePageForContainer",
      "_updateDeferredTreePageEntry",
      "_synchronizeDeferredTreePage",
      "_insertRowSorted",
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
  // A folder longer than the tree draws at once: 1,400 files, f0000 to f1399.
  const LONG_FILES = 1400;
  const longName = (index) => `long/f${String(index).padStart(4, "0")}.txt`;
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
  // The totals stand in their band over the panel, as the shell draws it (server.py), and the
  // outside-filter note joins them there.
  const band = element(document, "div", { id: "nav-metadata-files" });
  const panel = element(document, "div", { id: "tab-files", "data-tab-content": "files" });
  document.body.append(band, panel);
  /** The tree as the filter left it. With .md files only, src and long have no rows. */
  function draw({ filtered = false } = {}) {
    context.pendingTreePages.clear();
    const long = [];
    if (!filtered) {
      const holder = element(document, "div");
      holder.innerHTML = context.renderTreeNodes(
        Array.from({ length: LONG_FILES }, (_unused, index) => ({ path: longName(index) })),
        false,
        { level: 2, setSize: LONG_FILES },
      );
      long.push(...holder.childNodes);
    }
    band.replaceChildren(element(document, "div", { class: "tree-summary" }));
    panel.replaceChildren(
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
  /**
   * The long folder as drawn, in order: each run of consecutive rows, and each "more" row
   * with what it says. A row out of order starts a run of its own.
   */
  const longFolder = () => {
    const children = panel.querySelector('.tree-folder[data-path="long"]')?.nextElementSibling;
    if (!children) {
      return null;
    }
    const parts = [];
    let run = null;
    for (const item of children.children) {
      if (item.classList.contains("tree-page-more")) {
        run = null;
        parts.push(item.textContent);
        continue;
      }
      const name = item.dataset.path.slice("long/".length, -".txt".length);
      const number = Number(name.slice(1));
      if (run !== null && number === run.last + 1) {
        run.last = number;
        parts[parts.length - 1] = `${run.first}–${name}`;
      } else {
        run = { first: name, last: number };
        parts.push(name);
      }
    }
    return parts;
  };
  const view = () => {
    const open = [...panel.querySelectorAll(".tree-folder")]
      .filter((row) => row.getAttribute("aria-expanded") === "true")
      .map((row) => row.dataset.path);
    const drawn = longFolder();
    // A remark on the totals is a line of their band, never a row of the panel under it.
    assert.equal(panel.querySelector(".tree-selection-note"), null);
    return {
      open,
      selected: [...panel.querySelectorAll(".tree-item.selected")].map((row) => row.dataset.path),
      scrolled: scrolled.splice(0),
      note: band.querySelector(".tree-selection-note")?.textContent ?? null,
      ...(drawn === null ? {} : { "long folder": drawn }),
    };
  };
  const steps = [];
  const reveal = async (what, filePath, scroll = "nearest") => {
    context.currentPath = filePath;
    const shown = await context.revealFileRow(filePath, { scroll, isCurrent: () => true });
    steps.push({ step: what, path: filePath, shown, ...view() });
  };
  /** The reader presses the *nth* "more" row of the long folder, as its click does. */
  const pressMore = (what, nth) => {
    const more = panel
      .querySelector('.tree-folder[data-path="long"]')
      .nextElementSibling.children.filter((item) => item.classList.contains("tree-page-more"))[nth];
    const focus = context.mountNextTreePage(more);
    steps.push({
      step: what,
      path: context.currentPath,
      ...view(),
      "focus goes to": focus?.dataset.path ?? focus?.textContent ?? null,
    });
  };
  draw();
  await reveal("a file three folders down: its folders open", "docs/deep/deeper/leaf.md");
  await reveal(
    "a tab's landing keeps the tree's place: selected, not scrolled",
    "README.md",
    "keep",
  );
  await reveal(
    "a file in a long folder's second page: that page is drawn, the rest stays behind its row",
    longName(250),
  );
  await reveal(
    "a file in its fifth page: only that page is drawn, between rows for the pages around it",
    longName(905),
  );
  const fifth = steps.at(-1);
  assert.ok(fifth.shown, "a file in a long folder's fifth page is not drawn");
  assert.deepEqual(
    fifth["long folder"],
    ["f0000–f0399", "Show 400 more (1400 total)", "f0800–f0999", "Show 400 more (1400 total)"],
    "a reveal drew more than the page that holds its row",
  );
  pressMore(
    "the row above the revealed page draws the page before it there, and keeps focus nearby",
    0,
  );
  pressMore("again: the folder reads in order up to the revealed page", 0);
  pressMore("the row that ends the folder draws down from there, as before", 0);
  assert.deepEqual(
    steps.at(-1)["long folder"],
    ["f0000–f1199", "Show 200 more (1400 total)"],
    "the rows the reveal left behind did not draw in order",
  );
  await reveal("a path the tree does not hold, with no filter: no row stays selected", "gone.txt");
  await reveal("back to a listed file", "docs/guide.md");

  // Two reveals in one long folder, the second above the first: its page lies between the
  // "more" row above it and one of its own, which sits above the first's page.
  draw();
  await reveal("a long folder again, a file in its fifth page", longName(905));
  await reveal("then one in its third: only its page is drawn, above the first's", longName(405));
  assert.deepEqual(
    steps.at(-1)["long folder"],
    [
      "f0000–f0199",
      "Show 200 more (1400 total)",
      "f0400–f0599",
      "Show 200 more (1400 total)",
      "f0800–f0999",
      "Show 400 more (1400 total)",
    ],
    "a second reveal drew more than the page that holds its row",
  );
  pressMore(
    "the row below the reader's, pressed: its page grows down, and focus goes to its first row",
    1,
  );
  assert.equal(
    steps.at(-1)["focus goes to"],
    longName(600),
    "a 'more' row below the reader's row sent focus past the page it drew",
  );
  // Files that arrive while the page is open, as the live inventory inserts them.
  const longRows = () =>
    panel
      .querySelector('.tree-folder[data-path="long"]')
      .nextElementSibling.children.filter((item) => !item.classList.contains("tree-page-more"));
  const arrive = (what, filePath) => {
    context._insertRowSorted(
      panel.querySelector('.tree-folder[data-path="long"]').nextElementSibling,
      { path: filePath, name: filePath.split("/").pop(), type: "file" },
      {},
      false,
    );
    steps.push({ step: what, path: context.currentPath, ...view() });
  };
  arrive("a file arrives within a drawn page: each 'more' row counts it", "long/f0650a.txt");
  pressMore(
    "the row above the reader's, pressed: the rows it draws count the arrival, and focus goes to the row nearest the reader's",
    0,
  );
  steps.at(-1)["totals the rows give"] = [
    ...new Set(longRows().map((row) => row.dataset.treeSetSize)),
  ];
  assert.deepEqual(
    steps.at(-1)["totals the rows give"],
    ["1401"],
    "rows a 'more' row drew give the total from before an arrival",
  );
  await reveal("a file in the folder's last page", longName(1350));
  arrive("a file that sorts last arrives: it goes last, after the page drawn", "long/zzz.txt");
  assert.equal(
    steps.at(-1)["long folder"].at(-1),
    "zzz",
    "a file that sorts last went above rows a reveal drew",
  );

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

  // A landing whose folders travel as they open (revealInTree with `instant: false`, as the
  // end of app.js's DOMContentLoaded calls it) scrolls its row once their travel ends, and
  // then only if the address still names it, its folder is still open, and the tree holds
  // a row for it, the one revealed or one drawn in its place (revealWithin). The
  // long folder's body travels, with one animation whose `finished` the story resolves
  // after *during*.
  filter.state = { ...filter.state, types: null };
  const landWhileOpening = async (what, filePath, during = async () => {}) => {
    draw();
    let end = () => {};
    const finished = new Promise((resolve) => {
      end = resolve;
    });
    travelling = {
      body: panel.querySelector('.tree-folder[data-path="long"]').nextElementSibling,
      animations: [{ finished, effect: { getComputedTiming: () => ({ endTime: 150 }) } }],
    };
    context.currentPath = filePath;
    const shown = await context.revealInTree(filePath, {
      instant: false,
      isCurrent: () => context.currentPath === filePath,
    });
    steps.push({ step: what, path: filePath, shown, ...view() });
    assert.deepEqual(
      steps.at(-1).scrolled,
      [],
      "a reveal scrolled before its folder's travel ended",
    );
    await during();
    end();
    await settle();
    travelling = null;
  };
  /** The step at the end of a landing's travel. */
  const travelEnds = (what) => steps.push({ step: what, path: context.currentPath, ...view() });
  await landWhileOpening(
    "a landing in the long folder's fifth page, while the folder opens: selected, not yet scrolled",
    longName(905),
  );
  travelEnds("its travel ends: the row is scrolled into view");
  await landWhileOpening(
    "a landing, then another file revealed during its travel: not yet scrolled",
    longName(905),
    () => reveal("the other file's reveal scrolls at once", "README.md"),
  );
  travelEnds("the travel ends: the landing no longer stands, so its row is not scrolled");
  await landWhileOpening(
    "a landing, then its folder closed during the travel: not yet scrolled",
    longName(905),
    async () => {
      context.setFolderExpanded(panel.querySelector('.tree-folder[data-path="long"]'), false);
    },
  );
  travelEnds("the travel ends: the folder is closed, so its row is not scrolled");
  await landWhileOpening(
    "a landing, then its row drawn again during the travel: not yet scrolled",
    longName(905),
    async () => {
      const revealed = panel.querySelector(`.tree-item[data-path="${longName(905)}"]`);
      const redrawn = fileRow(longName(905));
      redrawn.className = revealed.className;
      revealed.parentNode.insertBefore(redrawn, revealed);
      revealed.remove();
    },
  );
  travelEnds("the travel ends: the row drawn in its place is scrolled into view");
  // Only a finite animation is waited on: an endless one on a folder's body would hold the
  // scroll for good.
  draw();
  travelling = {
    body: panel.querySelector('.tree-folder[data-path="long"]').nextElementSibling,
    animations: [
      {
        finished: new Promise(() => {}),
        effect: { getComputedTiming: () => ({ endTime: Infinity }) },
      },
    ],
  };
  context.currentPath = longName(905);
  await context.revealInTree(longName(905), { isCurrent: () => true });
  steps.push({
    step: "an endless animation on the folder's body: the reveal scrolls at once",
    path: context.currentPath,
    ...view(),
  });
  travelling = null;
  return steps;
}

// ── The Pulls list ────────────────────────────────────────────────

/** The recorded lists tests/test_github_pulls_panel_session.py records, each window resolved. */
function recordedLists() {
  const lists = JSON.parse(
    fs.readFileSync(path.join(root, "tests/fixtures/github-pulls-panel-responses.json"), "utf8"),
  );
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
  return lists;
}

/**
 * builtin_plugins/github/pulls-panel.js's controller over the recorded lists, under All,
 * with *deps* for what it tells the view: `reveal`, and `render` and `markOutside` when a
 * story reads them.
 */
async function recordedPullsController(deps, options) {
  const panel = await import(pathToFileURL(path.join(GITHUB, "pulls-panel.js")).href);
  const lists = recordedLists();
  return panel.createPullsController(
    {
      request(method, route) {
        if (method === "GET" && route.startsWith("/api/plugin/github/pulls?")) {
          const query = new URL(route, "http://x").searchParams;
          const state = query.get("state");
          if (query.get("limit") === "1") {
            // The catalog's indexed read, newest first from just above `after`, as
            // pull_catalog.py's `catalog_window` answers it, over the recorded All list.
            const all = [...lists.current.body.rows, ...lists.more_window.body.rows];
            const after = query.has("after") ? Number(query.get("after")) : null;
            const rows = all.filter((row) => after === null || row.number < after).slice(0, 1);
            const body = { ...lists.current.body, rows, next_after: null };
            return Promise.resolve({ status: 200, etag: null, body });
          }
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
      formatCount: (count) => count.toLocaleString("en-US"),
      render() {},
      markCurrent() {},
      markAnchor() {},
      open() {},
      filterChanged() {},
      ...deps,
    },
    { filter: "all", ...options },
  );
}

async function pullsStory() {
  const panel = await import(pathToFileURL(path.join(GITHUB, "pulls-panel.js")).href);
  const { createStackIndex } = await import(
    pathToFileURL(path.join(GITHUB, "pull-stacks.js")).href
  );
  const stacks = require("../fixtures/github-stacks-responses.json");
  const told = [];
  let model = null;
  const controller = await recordedPullsController(
    {
      render(next) {
        model = next;
      },
      reveal: (number) => told.push(`revealed #${number}`),
      markOutside: (text) => told.push(text === null ? "note gone" : `note: ${text}`),
      filterChanged: (name) => told.push(`filter ${name}`),
    },
    { current: null },
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
  await step(
    "#7 named again, by another tab of its page, one of its files, or a history step: nothing moves",
    () => controller.setCurrent(7),
  );
  await step("#7 opened again, by Quick Search: the stack opens, and #7 is revealed", () =>
    controller.setCurrent(7, { again: true }),
  );
  await step("a tab's landing at #8 keeps the list's place: marked, not revealed", () =>
    controller.setCurrent(8, { preserveScroll: true }),
  );
  await step("Quick Search for #8 after that landing: revealed, which ends the kept place", () =>
    controller.setCurrent(8, { again: true }),
  );
  await step("the reader picks Open, which leaves out closed #8: the list says nothing of it", () =>
    controller.setFilter("open"),
  );
  await step(
    "Quick Search for #8 again: Open leaves it out, so the list goes to All and reveals it",
    () => controller.setCurrent(8, { again: true }),
  );
  await step("the reader picks Open", () => controller.setFilter("open"));
  await step("#10 named: listed, so revealed", () => controller.setCurrent(10));
  await step(
    "the reader picks Closed while open #10 is shown: Closed leaves it out, and the list says nothing of it",
    () => controller.setFilter("closed"),
  );
  await step("#8 named under Closed: listed, so revealed", () => controller.setCurrent(8));
  await step("open #10 named under Closed, by Back: the list goes to All and reveals it", () =>
    controller.setCurrent(10),
  );
  await step("the reader picks Open", () => controller.setFilter("open"));
  await step(
    "#4000 named under Open: the catalog, read in full, lacks it, so the list stays and says so",
    () => controller.setCurrent(4000),
  );
  await step("the reader picks All: the filter is theirs, and the note goes", () =>
    controller.setFilter("all"),
  );
  await step("#6 named under All, past the rows read: the list reads on, and reveals it", () =>
    controller.setCurrent(6),
  );
  controller.dispose();
  return {
    steps,
    notes: {
      "in the catalog, further down than the list draws": panel.outsideText(8, true),
      "not in the catalog, which has been read in full": panel.outsideText(8, false),
    },
  };
}

/** The largest number the pulls route takes for `after` (cache/paths.py). */
const MAX_PULL_REQUEST_NUMBER = 9_999_999_999;

/**
 * A repository whose lists run past what the panel draws (pulls-panel.js `DISPLAY_ROWS`),
 * served in windows as the route serves them: Open is #3000 to #2901 and an old #1000,
 * Closed is #2900 down to #1001, and All is both. *catalog* is what the server's catalog
 * holds: how many of All's rows, newest first, as a catalog being read from GitHub holds
 * them, the newest number it has read (`newest`, for pull requests opened since, which
 * `publish` reads in), its `epoch`, whether it is complete, which reads fail (a list's
 * name, or `lookup` for the one-row indexed reads), and which are slow (`held`, the same
 * names, or `newest` for the read of the newest row alone): those wait for `release`, and
 * answer then, from the catalog as it stands, even when the panel has let them go, as an
 * answer already on its way does. A read the panel lets go before it answers is listed as
 * `let go`. Each list's generation moves as pull_catalog.py's `_commit` moves it: a pull
 * request read in newer than a list's oldest moves All's and its own state's, and older
 * rows a crawl reads in move none. `focus` is where focus is, as the view's `focusPlace`
 * reports it, and a row the controller focuses is told. Each story's steps name pull
 * requests as a link or Back does, and "time passes" runs what the panel scheduled, its
 * next poll among them.
 */
async function pullsDepthController(catalog, filter) {
  const panel = await import(pathToFileURL(path.join(GITHUB, "pulls-panel.js")).href);
  const template = recordedLists().open_current.body;
  const range = (high, low) => Array.from({ length: high - low + 1 }, (_, at) => high - at);
  const every = [...range(3000, 1000)];
  const state = (number) => (number > 2900 || number === 1000 ? "open" : "closed");
  const row = (number) => ({
    ...template.rows[0],
    number,
    title: `Pull request ${number}`,
    state: state(number),
    merged: false,
    merged_at: null,
  });
  /** Each list's generation, as `_commit` counts them. */
  const generations = { all: 0, open: 0, closed: 0 };
  const reads = [];
  const told = [];
  const letGo = [];
  const pending = new Set();
  /** @type {{kind: string, answer: () => void}[]} */
  const waiting = [];
  const controller = panel.createPullsController(
    {
      request(method, route, options) {
        if (method !== "GET" || !route.startsWith("/api/plugin/github/pulls?")) {
          return Promise.resolve({ status: 404, etag: null, body: null });
        }
        const query = new URL(route, "http://x").searchParams;
        const name = query.get("state");
        const limit = Number(query.get("limit"));
        const after = query.has("after") ? Number(query.get("after")) : null;
        const lookup = limit === 1;
        const kind = lookup ? "lookup" : name;
        const read = lookup
          ? after === null
            ? "lookup: the newest"
            : `lookup: #${after - 1} or the next older`
          : `${name}${after === null ? "" : ` after #${after}`}`;
        reads.push(read);
        let answered = false;
        options?.signal?.addEventListener("abort", () => answered || letGo.push(read), {
          once: true,
        });
        const answer = () => {
          answered = true;
          return answerOf(name, limit, after, kind);
        };
        const slow = catalog.held?.has(kind)
          ? kind
          : lookup && after === null && catalog.held?.has("newest")
            ? "newest"
            : null;
        if (slow !== null) {
          return new Promise((resolve) =>
            waiting.push({ kind: slow, answer: () => resolve(answer()) }),
          );
        }
        return Promise.resolve(answer());
      },
      schedule(callback) {
        const handle = { callback };
        pending.add(handle);
        return handle;
      },
      cancel: (handle) => pending.delete(handle),
      now: () => Date.parse("2026-09-17T12:00:30Z"),
      isVisible: () => true,
      formatTime: (iso) => iso,
      formatCount: (count) => count.toLocaleString("en-US"),
      render() {},
      markCurrent() {},
      markAnchor(_previous, number, focus) {
        if (focus) {
          told.push(`focused #${number}`);
        }
      },
      focusPlace: () => catalog.focus ?? "body",
      open() {},
      reveal: (number) => told.push(`revealed #${number}`),
      markOutside: (text) => told.push(text === null ? "note gone" : `note: ${text}`),
      filterChanged: (name) => told.push(`filter ${name}`),
    },
    { filter, current: null },
  );
  /** The route's answer, from the catalog as it stands when it answers. */
  function answerOf(name, limit, after, kind) {
    if (catalog.down.has(kind)) {
      return { status: 500, etag: null, body: null };
    }
    if (after !== null && after > MAX_PULL_REQUEST_NUMBER) {
      // pull_list_route.py refuses an `after` past the largest pull request number.
      return { status: 400, etag: null, body: { code: "invalid_request" } };
    }
    const cached = every
      .filter((number) => number <= (catalog.newest ?? Number.POSITIVE_INFINITY))
      .slice(0, catalog.cached);
    const all = cached.filter((number) => name === "all" || state(number) === name);
    const from = after === null ? 0 : all.findIndex((number) => number < after);
    const rows = from < 0 ? [] : all.slice(from, from + limit);
    const last = from >= 0 && from + limit < all.length ? rows[rows.length - 1] : null;
    const body = {
      ...template,
      list: name,
      total: every.filter((number) => name === "all" || state(number) === name).length,
      fetched: all.length,
      catalog_fetched: cached.length,
      complete: catalog.complete,
      generation: `${catalog.epoch ?? template.generation.split(":")[0]}:${generations[name]}`,
      filter_totals: { all: every.length, open: 101, closed: 1900 },
      rows: rows.map(row),
      next_after: last,
    };
    return { status: 200, etag: `"${name}:${cached.length}"`, body };
  }
  await controller.start({ shown: true });
  await settle();
  const steps = [];
  const step = async (what, act) => {
    reads.length = 0;
    told.length = 0;
    letGo.length = 0;
    await act();
    await settle();
    steps.push({
      step: what,
      read: [...new Set(reads)],
      told: [...told],
      ...(letGo.length > 0 ? { "let go": [...new Set(letGo)] } : {}),
    });
  };
  const timePasses = () => {
    const due = [...pending];
    pending.clear();
    for (const handle of due) {
      handle.callback();
    }
  };
  /** The slow reads of *kind* answer, and reads of it are no longer slow. */
  const release = (kind) => {
    catalog.held?.delete(kind);
    const due = waiting.filter((held) => held.kind === kind);
    waiting.splice(0, waiting.length, ...waiting.filter((held) => held.kind !== kind));
    for (const held of due) {
      held.answer();
    }
  };
  /** The catalog reads in the pull requests opened since its last read. */
  const publish = () => {
    for (const number of every) {
      if (number > (catalog.newest ?? Number.POSITIVE_INFINITY)) {
        generations.all += 1;
        generations[state(number)] += 1;
      }
    }
    catalog.newest = undefined;
  };
  /** The catalog starts again, as for a new reader, having read *cached* rows so far. */
  const restart = (epoch, cached) => {
    catalog.epoch = epoch;
    catalog.cached = cached;
    catalog.complete = false;
    generations.all = 0;
    generations.open = 0;
    generations.closed = 0;
  };
  return { controller, steps, step, timePasses, release, publish, restart };
}

async function pullsDepthStory() {
  const full = { cached: 2001, complete: true, down: new Set() };
  const deep = await pullsDepthController(full, "open");
  const { controller, step } = deep;
  await step(
    "the reader picks Closed, and a link names closed #2700 before its rows arrive: Closed holds it past its first window, so the list stays, reads on, and reveals it",
    () => {
      controller.setFilter("closed");
      controller.setCurrent(2700);
    },
  );
  await step(
    "open #2950 named under Closed: the catalog says it is open and among All's first 500, so the list goes to All and reveals it",
    () => controller.setCurrent(2950),
  );
  await step("the reader picks Closed", () => controller.setFilter("closed"));
  await step(
    "open #1000 named under Closed: All's 500 rows do not reach it, so the list goes to Open, which draws it, and reveals it",
    () => controller.setCurrent(1000),
  );
  await step("the reader picks Closed", () => controller.setFilter("closed"));
  await step(
    "closed #1500 named under Closed: it is further down than Closed draws, so the list stays and says so",
    () => controller.setCurrent(1500),
  );
  await step("the reader picks Open: the filter is theirs, and the note goes", () =>
    controller.setFilter("open"),
  );
  await step(
    "the reader picks Closed, and a link names open #2950: the list goes to All and reveals it",
    () => {
      controller.setFilter("closed");
      controller.setCurrent(2950);
    },
  );
  await step(
    "a link from #2950 names open #1000: All's 500 rows do not reach it, so the list goes on to Open, which draws it, and reveals it",
    () => controller.setCurrent(1000),
  );
  await step("the reader picks All", () => controller.setFilter("all"));
  await step(
    "closed #1500 named under All: All's rows do not reach it, so the list goes to Closed, which reaches furthest, and says it is further down than Closed draws too",
    () => controller.setCurrent(1500),
  );
  await step(
    "the reader scrolls to the list's end: Closed reads a page of 100 more, and the note stays as it was",
    () => controller.reachedEnd(),
  );
  await step(
    "the reader scrolls on, nine pages more: the note stays until the page that brings #1500, which reveals it, and then goes",
    async () => {
      for (let page = 0; page < 9; page += 1) {
        await controller.reachedEnd();
        await settle();
      }
    },
  );
  controller.dispose();

  const crawling = { cached: 200, complete: false, down: new Set() };
  const crawl = await pullsDepthController(crawling, "closed");
  await crawl.step(
    "a link names closed #2700 while the catalog has read 200 of 2,001 from GitHub: where it is is not known yet, so the list stays and says nothing",
    () => crawl.controller.setCurrent(2700),
  );
  await crawl.step(
    "the catalog reads to its end, and time passes: the next poll finds #2700 closed, so the list stays, reads on, and reveals it",
    () => {
      crawling.cached = 2001;
      crawling.complete = true;
      crawl.timePasses();
    },
  );
  crawl.controller.dispose();

  const behind = { cached: 2001, complete: true, down: new Set(), newest: 2990 };
  const newer = await pullsDepthController(behind, "open");
  await newer.step(
    "a link names open #2995, opened since the catalog's last read: the catalog, read to its end, lacks it, so the list says so",
    () => newer.controller.setCurrent(2995),
  );
  await newer.step(
    "the catalog reads it, and time passes: the next poll brings its row, so the note goes and the row is revealed",
    () => {
      newer.publish();
      newer.timePasses();
    },
  );
  newer.controller.dispose();

  const elsewhere = { cached: 2001, complete: true, down: new Set(), newest: 2990 };
  const across = await pullsDepthController(elsewhere, "closed");
  await across.step(
    "a link names open #2995 under Closed, opened since the catalog's last read: the catalog, read to its end, lacks it, so the list stays and says so",
    () => across.controller.setCurrent(2995),
  );
  await across.step(
    "time passes, and the catalog has read nothing new: the next poll does not ask again",
    () => across.timePasses(),
  );
  await across.step(
    "the catalog reads #2995, and time passes: Closed's next poll says the catalog has read more, so the list asks again, goes to All, and reveals it",
    () => {
      across.publish();
      across.timePasses();
    },
  );
  across.controller.dispose();

  const racing = {
    cached: 2001,
    complete: true,
    down: new Set(),
    newest: 2990,
    held: new Set(["newest"]),
  };
  const race = await pullsDepthController(racing, "closed");
  await race.step(
    "a link names open #2995 under Closed as the catalog reads it in: the lookup of #2995 answers before, and that of the newest row after, so the catalog as the first saw it lacks #2995, and the list says so",
    async () => {
      race.controller.setCurrent(2995);
      await settle();
      race.publish();
      race.release("newest");
    },
  );
  await race.step(
    "time passes: Closed's next poll says the catalog has read more than the lookup of #2995 saw, so the list asks again, goes to All, and reveals it",
    () => race.timePasses(),
  );
  race.controller.dispose();

  const restarting = { cached: 2001, complete: true, down: new Set() };
  const again = await pullsDepthController(restarting, "closed");
  await again.step(
    "a link names #4000 under Closed: the catalog, read to its end, lacks it, so the list says so",
    () => again.controller.setCurrent(4000),
  );
  await again.step(
    "the catalog starts again, as for a new reader, and has read 200 so far; time passes: what the old catalog lacked is not known of the new one yet, so the note goes and the list says nothing",
    () => {
      again.restart("restarted", 200);
      again.timePasses();
    },
  );
  await again.step(
    "the catalog reads to its end, and time passes: it lacks #4000 too, so the list says so again",
    () => {
      restarting.cached = 2001;
      restarting.complete = true;
      again.timePasses();
    },
  );
  again.controller.dispose();

  const failing = { cached: 2001, complete: true, down: new Set(["closed"]) };
  const failed = await pullsDepthController(failing, "closed");
  await failed.step(
    "the Closed list answers HTTP 500, and a link names open #2950: the catalog still says where it is, so the list goes to All and reveals it",
    () => failed.controller.setCurrent(2950),
  );
  await failed.step("the reader picks Closed, which answers again", () => {
    failing.down.clear();
    failed.controller.setFilter("closed");
  });
  await failed.step(
    "the catalog's lookups fail as a link names open #2940: where it is is not known, so the list stays and says nothing",
    () => {
      failing.down.add("lookup");
      failed.controller.setCurrent(2940);
    },
  );
  await failed.step(
    "the lookups answer again, and time passes: the next poll asks again, so the list goes to All and reveals #2940",
    () => {
      failing.down.clear();
      failed.timePasses();
    },
  );
  failed.controller.dispose();

  const failingThere = { cached: 2001, complete: true, down: new Set(["all"]) };
  const moved = await pullsDepthController(failingThere, "closed");
  await moved.step(
    "open #2950 named under Closed while All answers HTTP 500: the list goes to All, whose first read fails, so nothing is revealed and nothing noted",
    () => moved.controller.setCurrent(2950),
  );
  await moved.step(
    "All answers again, and time passes: the next poll brings #2950's row, and reveals it",
    () => {
      failingThere.down.clear();
      moved.timePasses();
    },
  );
  await moved.step("time passes again: #2950 is revealed once, not at every poll", () =>
    moved.timePasses(),
  );
  moved.controller.dispose();

  const slow = { cached: 2001, complete: true, down: new Set(), held: new Set(["lookup"]) };
  const late = await pullsDepthController(slow, "closed");
  await late.step(
    "a link names open #1000 under Closed while the catalog is slow to answer: the list waits and says nothing",
    () => late.controller.setCurrent(1000),
  );
  await late.step(
    "a second link names open #2950 before that answer: the first lookup is let go, and the second waits",
    () => late.controller.setCurrent(2950),
  );
  await late.step(
    "both answers come: the one for #1000 is ignored, and #2950 is among All's first 500, so the list goes to All and reveals it",
    () => late.release("lookup"),
  );
  await late.step(
    "the reader picks Closed, and a link names open #1000 while the catalog is slow again",
    () => {
      slow.held.add("lookup");
      late.controller.setFilter("closed");
      late.controller.setCurrent(1000);
    },
  );
  await late.step(
    "the reader picks All before the answer: the lookup is let go, and the filter is theirs",
    () => late.controller.setFilter("all"),
  );
  await late.step(
    "the answer comes: it is ignored, so the list stays under All and says nothing",
    () => late.release("lookup"),
  );
  await late.step(
    "the reader picks Closed, and a link names open #2950 while the catalog is slow",
    () => {
      slow.held.add("lookup");
      late.controller.setFilter("closed");
      late.controller.setCurrent(2950);
    },
  );
  await late.step(
    "the panel is hidden before the answer: its reads end, the lookups among them",
    () => late.controller.setShown(false),
  );
  await late.step("the answer comes while the panel is hidden: it is ignored", () =>
    late.release("lookup"),
  );
  await late.step(
    "the panel is shown again: its next poll asks again, so the list goes to All and reveals #2950",
    () => late.controller.setShown(true),
  );
  late.controller.dispose();

  const focusing = { cached: 2001, complete: true, down: new Set(), held: new Set(["all"]) };
  const focus = await pullsDepthController(focusing, "closed");
  await focus.step(
    "with focus on a row, open #2950 named under Closed, as Control-N names it: the list goes to All, whose rows are slow",
    () => {
      focusing.focus = "list";
      focus.controller.setCurrent(2950);
    },
  );
  await focus.step(
    "the reader moves focus out of the list, and All's rows come: #2950 is revealed, and focus stays where the reader put it",
    () => {
      focusing.focus = "elsewhere";
      focus.release("all");
    },
  );
  await focus.step("the reader picks Closed, and puts focus on a row", () => {
    focusing.focus = "list";
    focus.controller.setFilter("closed");
  });
  await focus.step(
    "open #2940 named, as Control-N names it: the list goes to All, whose rows are slow again",
    () => {
      focusing.held.add("all");
      focus.controller.setCurrent(2940);
    },
  );
  await focus.step(
    "All's rows come with focus where the move left it, on no element: #2940 is revealed, and takes focus",
    () => {
      focusing.focus = "body";
      focus.release("all");
    },
  );
  focus.controller.dispose();

  const refused = await pullsDepthController(
    { cached: 2001, complete: true, down: new Set() },
    "closed",
  );
  await refused.step(
    "a link names #9999999999, the largest number a pull request may have: the route refuses a read from above it, and the newest pull request is older, so the catalog lacks it and the list says so",
    () => refused.controller.setCurrent(MAX_PULL_REQUEST_NUMBER),
  );
  await refused.step("time passes: the next poll does not ask again", () => refused.timePasses());
  refused.controller.dispose();
  return {
    "past what the list draws": deep.steps,
    crawling: [...crawl.steps, ...newer.steps, ...across.steps, ...race.steps, ...again.steps],
    failing: [...failed.steps, ...moved.steps],
    "answers that come late": late.steps,
    focus: focus.steps,
    "a number the route refuses": refused.steps,
  };
}

/** The parts the command line names; with none, every part but `pulls-depth`. */
async function main(part = process.argv[2] ?? null) {
  if (part === "pulls-depth") {
    const transcript = { "beyond the rows read": await pullsDepthStory() };
    process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
    return;
  }
  if (part === "links") {
    const transcript = {
      "a link's address": await linksStory(),
      invariants: {
        "an open pushes one entry, the link's own address, and none for the address shown": true,
        "an address the shell cannot open in place moves, writes, and tells nothing": true,
        "no link moves focus": true,
      },
    };
    process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
    return;
  }
  if (part !== null) {
    throw new Error(`Unknown part ${part}; the parts to name are pulls-depth and links`);
  }
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
    "a step within the pull request shown reveals no row, and Quick Search for it does": true,
  };
  // `links` runs here too, after the rest, and prints only when named: the parity registry
  // runs a session with no part, and its row for the shell's opener reads this run.
  await linksStory();
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
