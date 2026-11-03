// Browserless session: the Pulls tab's host, driven through the production browser code.
//
// static/pulls-nav.js loads whole, as the shell's `shell-tools` bundle loads it, with the real
// static/pull-route.js for the address grammar and the real static/keyboard-shortcuts.js for
// the keys. The shell and the view are played here: the session records what the host asks of
// the shell, and what it tells the view. No request is made by the host at all, so there is no
// recording to replay: which tab a page draws is the server's, and `tests/test_pulls_nav.py`
// holds that against real shells.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");

function loadModules() {
  const listeners = [];
  const context = {
    console: { error() {}, warn() {} },
    JSON,
    Object,
    Promise,
    Set,
    Map,
    Symbol,
    Array,
    String,
    Number,
    TypeError,
    URLSearchParams,
    Error,
    AbortController,
    Element: class {},
  };
  context.window = context;
  context.document = {
    addEventListener(type, listener, capture) {
      listeners.push({ type, listener, capture });
    },
    removeEventListener() {},
  };
  vm.createContext(context);
  for (const name of ["pull-route.js", "keyboard-shortcuts.js", "pulls-nav.js"]) {
    const file = path.join(staticDir, name);
    vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  }
  return {
    context,
    routes: context.MetabrowserPullRoute,
    shortcuts: context.MetabrowserKeyboardShortcuts,
    nav: context.MetabrowserPullsNav,
    dispatch(event) {
      for (const { type, listener } of listeners) {
        if (type === "keydown") {
          listener(event);
        }
      }
    },
  };
}

const modules = loadModules();

async function settle() {
  for (let turn = 0; turn < 10; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/** A shell, a view, and a log of what the host did to each. */
function createShell(address, { active = "files", failLoads = 0, slowView = false } = {}) {
  const log = [];
  const shell = { active, address: new URL(address, "http://x"), failLoads, panel: null };
  /** @type {(() => void) | null} */
  let releaseView = null;
  let prefetch = null;
  const view = {
    render(_container, ctx) {
      const host = ctx.pullsNav;
      log.push(
        `view rendered: filter ${host.filter}, current ${host.current}, shown ${host.shown}, kind ${ctx.kind}`,
      );
      shell.host = host;
      return {
        setShown: (shown) => log.push(`view told: ${shown ? "shown" : "hidden"}`),
        setCurrent: (number) => log.push(`view told: current ${number}`),
        setFilter: (state) => log.push(`view told: filter ${state}`),
        move: (delta, how) => {
          log.push(`view told: move ${delta}${how?.repeat ? " repeating" : ""}`);
          return true;
        },
        released: () => log.push("view told: released"),
        activateAnchor: () => {
          log.push("view told: open the row with focus");
          return true;
        },
        dispose: () => log.push("view disposed"),
      };
    },
  };
  const deps = {
    routes: modules.routes,
    location: () => ({ pathname: shell.address.pathname, search: shell.address.search }),
    pushHref(href) {
      log.push(`pushed ${href}`);
      shell.address = new URL(href, "http://x");
    },
    activeTab: () => shell.active,
    registerPanel(panel) {
      log.push(`registered ${panel.id} "${panel.label}"`);
      shell.panel = panel;
    },
    activate(panelId) {
      log.push(`activated ${panelId}`);
      const leaving = shell.active;
      shell.active = panelId;
      if (leaving === "pulls" && panelId !== "pulls") {
        shell.panel?.onHide();
      }
      if (panelId === "pulls") {
        shell.panel?.onShow();
      }
    },
    async loadView(kind) {
      log.push(`load view of ${kind}`);
      if (shell.failLoads > 0) {
        shell.failLoads -= 1;
        throw new Error("the plugin did not load");
      }
      if (slowView) {
        await new Promise((resolve) => {
          releaseView = resolve;
        });
      }
      return view;
    },
    container: () => ({}),
    scrollRoot: () => ({}),
    openPull(route) {
      log.push(`opened pull request ${route.number}`);
      return Promise.resolve({ status: "opened" });
    },
    schedulePrefetch(callback) {
      log.push("prefetch scheduled");
      prefetch = callback;
      return "prefetch";
    },
    cancelPrefetch() {
      log.push("prefetch cancelled");
      prefetch = null;
    },
    showFailure() {
      log.push("failure shown");
    },
  };
  return {
    shell,
    deps,
    runPrefetch() {
      const callback = prefetch;
      prefetch = null;
      callback?.();
    },
    release: () => releaseView?.(),
    take: () => log.splice(0),
  };
}

async function run() {
  const { nav, routes, shortcuts } = modules;
  const addresses = {};
  for (const [pathname, search] of [
    ["/pulls", ""],
    ["/pulls", "?state=closed"],
    ["/pulls", "?state=merged"],
    ["/pull/7", ""],
    ["/pull/7/files", ""],
    ["/view/README.md", ""],
    ["/commit/abc", ""],
  ]) {
    const address = `${pathname}${search}`;
    addresses[address] = {
      names: nav.pullAddress(routes, pathname, search),
      "from Files": nav.tabForAddress(routes, pathname, search, "files"),
      "from Pulls": nav.tabForAddress(routes, pathname, search, "pulls"),
      "from Git": nav.tabForAddress(routes, pathname, search, "git"),
    };
  }

  const stories = {};
  const story = (name) => {
    stories[name] = [];
    return stories[name];
  };

  // Elsewhere on a mirror: the tab is there, and the view is read ahead when the shell is idle.
  let page = createShell("/view/README.md");
  let host = nav.createPullsNav(page.deps);
  let log = story("a mirror's page at a file");
  host.start();
  log.push({ "the shell starts it": page.take(), snapshot: host.snapshot() });
  page.runPrefetch();
  await settle();
  log.push({ "the idle read mounts it, hidden": page.take(), snapshot: host.snapshot() });
  page.deps.activate("pulls");
  log.push({ "the tab opens: it is told, and loads nothing": page.take() });
  page.deps.activate("files");
  log.push({ "another tab: it is told": page.take() });
  host.dispose();
  log.push({ "the page goes: it is disposed": page.take(), snapshot: host.snapshot() });

  // At a pull request's address the server draws the tab in front, so the first show is the host's.
  page = createShell("/pull/7/files", { active: "pulls" });
  host = nav.createPullsNav(page.deps);
  log = story("the first page of a pull request's address");
  host.start();
  await settle();
  log.push({ "the tab shows, mounted at once": page.take(), snapshot: host.snapshot() });
  page.shell.address = new URL("/pull/8", "http://x");
  host.routeChanged();
  log.push({ "another pull request: the row follows": page.take() });
  page.shell.address = new URL("/pulls?state=open", "http://x");
  host.routeChanged();
  log.push({ "the list's address: its filter": page.take() });
  page.shell.host.filterChanged("closed");
  log.push({ "a filter chosen at the list's address is an address": page.take() });
  page.shell.address = new URL("/pull/8", "http://x");
  host.routeChanged();
  page.take();
  page.shell.host.filterChanged("open");
  log.push({ "a filter chosen on a pull request's page is the panel's": page.take() });
  void page.shell.host.open({ number: 9, tab: "" });
  log.push({ "a row's open is the shell's": page.take() });
  page.shell.address = new URL("/view/README.md", "http://x");
  host.routeChanged();
  log.push({ "a file opens: Files is in front": page.take() });
  page.deps.activate("pulls");
  page.take();
  host.routeChanged();
  log.push({ "chosen by hand at that file: a step on the same path keeps it": page.take() });
  page.shell.address = new URL("/commit/abc", "http://x");
  host.routeChanged();
  log.push({ "a commit is the Git panel's": page.take() });
  page.shell.active = "files";
  page.shell.address = new URL("/pull/7", "http://x");
  host.routeChanged();
  log.push({ "history lands on a pull request from Files": page.take() });
  host.dispose();

  // The list's filters are places of their own: Back from one to another shows the list, though
  // Files was chosen by hand at the first, and so does Back from a filter the panel chose.
  page = createShell("/pulls?state=open", { active: "pulls" });
  host = nav.createPullsNav(page.deps);
  log = story("Back between the list's filters");
  host.start();
  await settle();
  page.take();
  page.deps.activate("files");
  page.take();
  host.routeChanged();
  log.push({ "Files chosen by hand at Open: the same place keeps it": page.take() });
  page.shell.address = new URL("/pulls", "http://x");
  host.routeChanged();
  log.push({ "Back to All: the list is in front": page.take() });
  page.shell.host.filterChanged("closed");
  page.deps.activate("files");
  page.take();
  page.shell.address = new URL("/pulls", "http://x");
  host.routeChanged();
  log.push({ "Back from a filter the panel chose: the list again": page.take() });
  host.dispose();

  // Lazy mounting: a load that fails says so to a reader who is looking, and the next show retries.
  page = createShell("/view/README.md", { failLoads: 1 });
  host = nav.createPullsNav(page.deps);
  log = story("a view that could not load");
  host.start();
  page.take();
  page.deps.activate("pulls");
  await settle();
  log.push({ "the tab opens, and the load fails": page.take(), snapshot: host.snapshot() });
  page.deps.activate("files");
  page.deps.activate("pulls");
  await settle();
  log.push({ "the next show tries again": page.take(), snapshot: host.snapshot() });
  host.dispose();

  // A prefetch that fails is not the reader's business, until they look.
  page = createShell("/view/README.md", { failLoads: 1 });
  host = nav.createPullsNav(page.deps);
  log = story("a read ahead that could not load");
  host.start();
  page.take();
  page.runPrefetch();
  await settle();
  log.push({ "nothing is shown of it": page.take(), snapshot: host.snapshot() });
  host.dispose();

  // Replacement: the page goes while the view is loading, so that mount is nobody's.
  page = createShell("/pull/7", { active: "pulls", slowView: true });
  host = nav.createPullsNav(page.deps);
  log = story("the page goes while the view loads");
  host.start();
  page.take();
  host.dispose();
  page.release();
  await settle();
  log.push({ "the late mount is disposed": page.take(), snapshot: host.snapshot() });

  // The keys, through the real registry: what repeats, what Help says, and that a rebuilt
  // registry gets them back.
  page = createShell("/pull/7", { active: "pulls" });
  host = nav.createPullsNav(page.deps);
  host.start();
  await settle();
  page.take();
  const registry = shortcuts.create({
    document: { addEventListener() {}, removeEventListener() {} },
  });
  const unregister = nav.registerKeys(host, registry);
  const deactivate = registry.activateScope("pull-rows");
  const keys = {};
  for (const [name, commandId, event] of [
    ["ArrowDown", "pulls.next", { key: "ArrowDown", repeat: false }],
    ["held J", "pulls.next", { key: "j", repeat: true }],
    ["ArrowUp", "pulls.previous", { key: "ArrowUp", repeat: false }],
    ["held K", "pulls.previous", { key: "k", repeat: true }],
    ["Enter", "pulls.open", { key: "Enter", repeat: false }],
  ]) {
    const handled = registry.invoke(commandId, { event });
    keys[name] = { handled, did: page.take() };
  }
  const help = registry
    .snapshot("help", { includeInactive: true })
    .find((group) => group.id === "pull-requests");
  deactivate();
  const outsideRows = registry.invoke("pulls.next", { event: { key: "j" } });
  for (const remove of unregister) {
    remove();
  }
  const rebuilt = registry.snapshot("help", { includeInactive: true }).map((group) => group.id);
  host.dispose();

  return {
    "the page's host": await pageHostStory(),
    addresses,
    stories,
    keys,
    help: {
      label: help.label,
      context: help.context,
      commands: help.commands.map((command) => ({
        keys: command.bindings.spoken,
        action: command.copy.action,
        description: command.copy.description,
      })),
    },
    "keys when no row has focus": outsideRows,
    "groups once unregistered": rebuilt,
  };
}

/**
 * The module's own `init` and `dispose`, on a page the session plays: the listeners it puts on
 * the tab and the window, which a key's release ends a walk through, and a second `init` after
 * a `dispose`, as a page rebuilt after a real teardown takes.
 */
async function pageHostStory() {
  const { context, nav } = modules;
  /** Each listener the host added, live until its signal aborts, as the DOM keeps them. */
  const listeners = [];
  const target = (name) => ({
    addEventListener(type, listener, options) {
      if (options?.signal?.aborted) {
        return;
      }
      const entry = { name, type, listener, live: true };
      listeners.push(entry);
      options?.signal?.addEventListener("abort", () => {
        entry.live = false;
      });
    },
  });
  const told = [];
  const view = {
    render: () => ({
      setShown() {},
      setCurrent() {},
      setFilter() {},
      move: () => true,
      released: () => told.push("released"),
      activateAnchor: () => true,
      dispose: () => told.push("view disposed"),
    }),
  };
  let panel = null;
  const tab = target("the tab");
  Object.assign(context, {
    MetabrowserAssets: { ensureAsset: async () => {} },
    MetabrowserShell: {
      registerNavPanel(registered) {
        panel = registered;
      },
      activateNavPanel(id) {
        if (id === "pulls") {
          panel?.onShow();
        }
      },
      openPullRequest: async () => ({ status: "opened" }),
      shortcuts: () => null,
      removeNavPanel: () => told.push("tab removed"),
    },
    metabrowser: { ensureKindAssets: async () => {}, getRegisteredView: () => view },
    location: { pathname: "/pull/7", search: "" },
    history: { pushState() {} },
    requestIdleCallback: () => 1,
    cancelIdleCallback() {},
    addEventListener: target("the window").addEventListener,
  });
  context.document.getElementById = (id) => (id === "tab-pulls" ? tab : null);
  context.document.querySelector = () => null;
  const live = () => listeners.filter((entry) => entry.live).map((e) => `${e.name}: ${e.type}`);
  const keyUp = (key) => {
    for (const entry of listeners) {
      if (entry.live && entry.type === "keyup") {
        entry.listener({ key });
      }
    }
    return told.splice(0);
  };
  const story = {};
  await nav.init();
  await settle();
  told.splice(0);
  story["init listens"] = live();
  story["a modifier's release ends no walk"] = keyUp("Shift");
  story["J's release ends it"] = keyUp("j");
  nav.dispose();
  story["dispose ends them all"] = { listening: live(), told: told.splice(0) };
  await nav.init();
  await settle();
  story["init again listens again"] = live();
  story["and J's release ends a walk again"] = keyUp("j");
  nav.dispose();
  told.splice(0);
  return story;
}

// A step that awaits an answer nobody gives ends the process quietly, with nothing printed.
let finished = false;
process.on("beforeExit", () => {
  if (!finished) {
    process.stderr.write("the session stopped on something no step resolved\n");
    process.exitCode = 1;
  }
});

run()
  .then((transcript) => {
    finished = true;
    process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
  })
  .catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
