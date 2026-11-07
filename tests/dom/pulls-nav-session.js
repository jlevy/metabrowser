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
const assert = require("node:assert/strict");

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
function createShell(
  address,
  { active = "files", failLoads = 0, slowView = false, checkout = false } = {},
) {
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
    pageFor: (number) => shell.pages?.get(number) ?? null,
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
    ...(checkout ? { checkout: true } : {}),
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

  // A checkout uses the same post-startup metadata warmup as a managed repository.
  page = createShell("/view/README.md", { checkout: true });
  host = nav.createPullsNav(page.deps);
  log = story("a checkout's page at a file");
  host.start();
  log.push({
    "the shell starts it: idle warmup scheduled": page.take(),
    snapshot: host.snapshot(),
  });
  page.runPrefetch();
  await settle();
  log.push({ "the idle read mounts it, hidden": page.take() });
  page.deps.activate("pulls");
  await settle();
  log.push({
    "the tab opens: the warmed view is shown": page.take(),
    "what it is handed": {
      refreshAhead: page.shell.host.refreshAhead,
      checkout: page.shell.host.checkout,
    },
  });
  page.deps.activate("files");
  log.push({ "Files: it is told, and stops": page.take() });
  host.dispose();

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
  page.shell.address = new URL("/pulls?state=all", "http://x");
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
    "the two trees": await twoTreesStory(),
    "stack keys": await stackKeysStory(),
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

/** Stack commands use the active page capability and the real registry's global guards. */
async function stackKeysStory() {
  const { nav, shortcuts } = modules;
  const page = createShell("/pull/7/checks", { active: "pulls" });
  let known = true,
    endpoint = false;
  const moves = [];
  const renderer = {
    hasStack: () => known,
    moveStack(delta) {
      if (!known) {
        return false;
      }
      moves.push(endpoint ? "endpoint" : delta);
      return true;
    },
  };
  page.shell.pages = new Map([[7, renderer]]);
  const host = nav.createPullsNav(page.deps);
  host.start();
  await settle();
  page.take();
  let dispatch;
  const registry = shortcuts.create({
    document: {
      addEventListener: (_type, listener) => {
        dispatch = listener;
      },
      removeEventListener() {},
    },
  });
  const unregister = nav.registerKeys(host, registry);
  const press = (key, values = {}) => {
    const event = {
      key,
      shiftKey: true,
      repeat: false,
      altKey: false,
      ctrlKey: false,
      metaKey: false,
      isComposing: false,
      defaultPrevented: false,
      target: { tagName: "DIV" },
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...values,
    };
    dispatch(event);
    return event.defaultPrevented;
  };
  assert(press("J"));
  assert(press("K"));
  assert.deepEqual(moves, [-1, 1], "global direction reaches the active subtab without row focus");
  const rowScope = registry.activateScope("pull-rows");
  const plainJ = press("j", { shiftKey: false });
  assert(plainJ);
  assert.deepEqual(page.take(), ["view told: move 1"]);
  assert.equal(press("J", { repeat: true }), false);
  assert.equal(press("J", { target: { tagName: "INPUT" } }), false);
  assert.equal(press("J", { target: { tagName: "DIV", isContentEditable: true } }), false);
  const closeHelp = registry.activateScope("help", { exclusive: true });
  assert.equal(press("J"), false);
  closeHelp();
  const closeModal = registry.activateScope("dialog", { exclusive: true });
  assert.equal(press("K"), false);
  closeModal();
  assert.deepEqual(moves, [-1, 1], "repeat, editor, Help and modal never navigate");
  endpoint = true;
  assert(press("J"));
  assert.equal(moves.at(-1), "endpoint", "endpoint is consumed without a row fallback");
  assert.deepEqual(page.take(), []);
  endpoint = false;
  known = false;
  assert.equal(press("K"), false);
  known = true;
  assert(press("K"), "newly known membership becomes available without re-registration");
  page.shell.pages.set(7, {});
  assert.equal(press("J"), false, "custom PR pages may omit stack navigation");
  page.shell.pages.set(7, { hasStack: () => true });
  assert.equal(press("J"), false, "a partial capability cannot consume navigation");
  page.shell.pages.set(7, renderer);
  page.deps.activate("files");
  assert.equal(press("J"), false, "a hidden Pulls panel does not own a global command");
  page.deps.activate("pulls");
  page.shell.address = new URL("/pulls", "http://x");
  assert.equal(press("J"), false, "the list has no active PR stack");
  page.shell.address = new URL("/view/README.md", "http://x");
  assert.equal(press("K"), false, "another preview does not reuse an old PR capability");
  page.shell.address = new URL("/pull/7/checks", "http://x");
  const help = registry
    .snapshot("help", { includeInactive: true })
    .find((group) => group.id === "pull-stack");
  const copy = help.commands.map((command) => ({
    keys: command.bindings.spoken,
    action: command.copy.action,
  }));
  assert.deepEqual(
    Array.from(copy, (entry) => entry.keys),
    ["Shift plus J", "Shift plus K"],
  );
  const visible = registry.present("pulls.stack.base").bindings.visible[0].keys;
  assert.deepEqual(Array.from(visible), ["⇧", "J"]);
  host.dispose();
  assert.equal(press("J"), false, "disposed pages cannot navigate even before registry cleanup");
  rowScope();
  for (const remove of unregister) {
    remove();
  }
  assert.equal(registry.present("pulls.stack.base"), null);
  registry.dispose();
  return {
    directions: moves.slice(0, 2),
    endpointConsumed: true,
    plainJRemainsRowNavigation: plainJ,
    guards: [
      "repeat",
      "input",
      "contenteditable",
      "Help",
      "modal",
      "unknown membership",
      "custom renderer",
      "hidden tab",
      "list",
      "other preview",
      "disposed",
    ],
    help: copy,
    cleanup: true,
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
      rememberMainTabAddress() {},
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
    metabrowser: {
      ensureKindAssets: async () => {},
      getRegisteredView: () => view,
      sourceKind: () => "git_revision",
    },
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

// ── The two trees ───────────────────────────────────────────────
//
// The Files tab and the Pulls tab are both trees of `treeitem` rows in one navigation pane, and
// the Files tree's keyboard handler claims every `treeitem` in its container. What keeps them
// apart is app.js's: the handler is made on `#tab-files`, not on the pane, and the overlay's
// focus fallback hands back a Files row only for a row with a tree id. So this story runs the
// production `initKeyboardInfrastructure` and `resolveApplicationFocusFallback`, extracted from
// app.js verbatim, with the real keyboard-shortcuts.js, tree-keyboard-navigation.js, and this
// host, in a stand-in for the DOM whose focus events bubble as a browser's do. The Files tree's
// opening, the overlay, Help, and the Pulls view are played: the view only moves focus and asks
// the shell to open the row, which the panel session covers.

/** One app.js declaration, bounded by its closing line at column zero. */
function appDeclaration(source, pattern, label) {
  const match = source.match(pattern);
  if (!match) {
    throw new Error(`app.js ${label} is not extractable`);
  }
  return match[0];
}

/** Whether *element* matches one compound selector: a tag, classes, ids, and attributes. */
function matchesCompound(element, selector) {
  const parts = selector.match(/^[a-z]+|\.[\w-]+|#[\w-]+|\[[\w-]+(?:="[^"]*")?\]/g) ?? [];
  if (parts.join("") !== selector) {
    throw new Error(`the stand-in DOM does not read the selector ${selector}`);
  }
  return parts.every((part) => {
    if (part.startsWith(".")) {
      return element.classList.contains(part.slice(1));
    }
    if (part.startsWith("#")) {
      return element.id === part.slice(1);
    }
    if (part.startsWith("[")) {
      const [, name, value] = /^\[([\w-]+)(?:="([^"]*)")?\]$/.exec(part);
      return value === undefined
        ? element.hasAttribute(name)
        : element.getAttribute(name) === value;
    }
    return element.localName === part;
  });
}

function twoTreesPage() {
  const log = [];
  class FakeElement {
    constructor(tag, document) {
      this.localName = tag;
      this.tagName = tag.toUpperCase();
      this.ownerDocument = document;
      this.parentElement = null;
      this.children = [];
      this.attributes = new Map();
      this.listeners = [];
      this.dataset = {};
      this.hidden = false;
      this.isContentEditable = false;
      this.style = { display: "" };
      const classes = new Set();
      this.classList = {
        add(...names) {
          for (const name of names) {
            classes.add(name);
          }
        },
        remove(...names) {
          for (const name of names) {
            classes.delete(name);
          }
        },
        contains: (name) => classes.has(name),
        toggle(name, on) {
          const wanted = on ?? !classes.has(name);
          if (wanted) {
            classes.add(name);
          } else {
            classes.delete(name);
          }
          return wanted;
        },
      };
    }
    get id() {
      return this.getAttribute("id") ?? "";
    }
    get isConnected() {
      return this.ownerDocument.body.contains(this);
    }
    get nextElementSibling() {
      const siblings = this.parentElement?.children ?? [];
      return siblings[siblings.indexOf(this) + 1] ?? null;
    }
    get previousElementSibling() {
      const siblings = this.parentElement?.children ?? [];
      return siblings[siblings.indexOf(this) - 1] ?? null;
    }
    append(...children) {
      for (const child of children) {
        child.parentElement = this;
        this.children.push(child);
      }
    }
    contains(node) {
      for (let at = node; at; at = at.parentElement) {
        if (at === this) {
          return true;
        }
      }
      return false;
    }
    matches(selector) {
      return selector.split(",").some((part) => matchesCompound(this, part.trim()));
    }
    closest(selector) {
      for (let at = this; at; at = at.parentElement) {
        if (at.matches(selector)) {
          return at;
        }
      }
      return null;
    }
    querySelectorAll(selector) {
      const found = [];
      const visit = (node) => {
        for (const child of node.children) {
          if (child.matches(selector)) {
            found.push(child);
          }
          visit(child);
        }
      };
      visit(this);
      return found;
    }
    querySelector(selector) {
      return this.querySelectorAll(selector)[0] ?? null;
    }
    setAttribute(name, value) {
      this.attributes.set(name, String(value));
      if (name.startsWith("data-")) {
        this.dataset[name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] =
          String(value);
      }
    }
    getAttribute(name) {
      return this.attributes.get(name) ?? null;
    }
    hasAttribute(name) {
      return this.attributes.has(name);
    }
    removeAttribute(name) {
      this.attributes.delete(name);
    }
    addEventListener(type, listener, options) {
      const entry = { type, listener };
      this.listeners.push(entry);
      options?.signal?.addEventListener("abort", () => {
        this.listeners.splice(this.listeners.indexOf(entry), 1);
      });
    }
    removeEventListener(type, listener) {
      this.listeners = this.listeners.filter(
        (entry) => entry.type !== type || entry.listener !== listener,
      );
    }
    focus() {
      const previous = document.activeElement;
      if (previous === this) {
        return;
      }
      document.activeElement = this;
      if (previous !== document.body) {
        dispatch(previous, "focusout", { relatedTarget: this });
      }
      dispatch(this, "focusin", { relatedTarget: previous });
    }
  }

  const documentListeners = [];
  const document = {
    activeElement: null,
    addEventListener(type, listener, capture) {
      documentListeners.push({ type, listener, capture });
    },
    removeEventListener(type, listener) {
      const at = documentListeners.findIndex(
        (entry) => entry.type === type && entry.listener === listener,
      );
      if (at >= 0) {
        documentListeners.splice(at, 1);
      }
    },
    createElement: (tag) => new FakeElement(tag, document),
    getElementById: (id) => document.body.querySelector(`#${id}`),
    // The tab bar the host reads which tab is in front from.
    querySelector: (selector) => {
      if (selector !== ".nav-tab-bar .tab-btn.active") {
        throw new Error(`the stand-in DOM does not read the selector ${selector}`);
      }
      return { getAttribute: () => shell.active };
    },
  };
  document.body = new FakeElement("body", document);
  document.activeElement = document.body;

  /** An event from *target* up through its ancestors to the document, as focus events go. */
  function dispatch(target, type, fields = {}) {
    const event = {
      type,
      target,
      defaultPrevented: false,
      isComposing: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...fields,
    };
    // The registry listens on the document in the capture phase, before the target.
    for (const entry of documentListeners.filter((e) => e.type === type && e.capture)) {
      entry.listener(event);
    }
    for (let at = target; at; at = at.parentElement) {
      for (const entry of at.listeners.filter((e) => e.type === type)) {
        entry.listener({ ...event, currentTarget: at });
      }
    }
    for (const entry of documentListeners.filter((e) => e.type === type && !e.capture)) {
      entry.listener(event);
    }
    return event;
  }

  const make = (tag, attributes = {}, children = []) => {
    const element = new FakeElement(tag, document);
    for (const [name, value] of Object.entries(attributes)) {
      if (name === "class") {
        element.classList.add(...value.split(" "));
      } else {
        element.setAttribute(name, value);
      }
    }
    element.append(...children);
    return element;
  };
  // A mirror's Files tree, as the shell renders it, with README.md open.
  const fileRow = (path, selected) => {
    const row = make("div", {
      class: `tree-item tree-file${selected ? " selected" : ""}`,
      role: "treeitem",
      "data-tree-kind": "file",
      "data-tree-id": `file:${path}`,
      "data-path": path,
      "data-action": "select",
    });
    return row;
  };
  const files = [fileRow("README.md", true), fileRow("setup.py", false)];
  const filesTab = make("div", { id: "tab-files", "data-tab-content": "files" }, [
    make("div", { role: "tree", "aria-label": "Files" }, files),
  ]);
  // The Pulls tab's list, as the panel paints it: a tree of anchors in items of no role.
  const pullRow = (number) =>
    make("a", {
      class: "github-pulls-row",
      href: `/pull/${number}`,
      role: "treeitem",
      "aria-level": "1",
      tabindex: number === 3900 ? "0" : "-1",
      "data-number": String(number),
    });
  const pulls = [3900, 3899, 3898].map(pullRow);
  const pullsTab = make("div", { id: "tab-pulls", "data-tab-content": "pulls" }, [
    make(
      "ul",
      { class: "github-pulls-list", role: "tree" },
      pulls.map((row) => make("li", { role: "none" }, [row])),
    ),
  ]);
  document.body.append(
    make("div", { id: "tree-pane" }, [make("div", { id: "tree-content" }, [filesTab, pullsTab])]),
    make("div", { id: "preview-pane" }),
    make("div", { id: "nav-shortcut-hints" }),
  );

  const changedFiles = ["src/a.py", "src/b.py"].map((path, index) =>
    make("a", {
      class: "github-pull-file-row",
      role: "treeitem",
      tabindex: index === 0 ? "0" : "-1",
      href: `/pull/3900/files/${path}`,
      "data-file": path,
    }),
  );
  pulls[0].parentElement.append(make("div", { role: "group" }, changedFiles));
  const shell = { active: "files", panel: null, address: "/view/" };
  const tabs = { files: filesTab, pulls: pullsTab };
  const context = {
    console: { error() {}, warn: (message) => log.push(`warned: ${message}`) },
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
    queueMicrotask,
    Element: FakeElement,
    HTMLElement: FakeElement,
    document,
    location: { pathname: "/view/", search: "" },
    history: { pushState() {} },
    requestIdleCallback: () => 1,
    cancelIdleCallback() {},
    addEventListener() {},
    // The shell's services that are not what this story is about.
    MetabrowserOverlay: {},
    MetabrowserKeyboardHelp: { create: () => ({ dispose() {} }) },
    MetabrowserAssets: { ensureAsset: async () => {} },
    MetabrowserShell: {
      rememberMainTabAddress() {},
      registerNavPanel(panel) {
        shell.panel = panel;
      },
      activateNavPanel(id) {
        const leaving = shell.active;
        shell.active = id;
        for (const [name, tab] of Object.entries(tabs)) {
          tab.style.display = name === id ? "" : "none";
        }
        if (leaving === "pulls" && id !== "pulls") {
          shell.panel?.onHide();
        }
        if (id === "pulls") {
          shell.panel?.onShow();
        }
      },
      openPullRequest(route) {
        shell.address = `/pull/${route.number}${route.tab ? `/${route.tab}` : ""}${route.file ? `/${route.file}` : ""}`;
        log.push(`the shell opened ${shell.address}, ${route.replace ? "replacing" : "pushing"}`);
        return Promise.resolve({ status: "opened" });
      },
      shortcuts: () => context.shortcutRegistry,
      removeNavPanel() {},
    },
    metabrowser: {
      ensureKindAssets: async () => {},
      sourceKind: () => "git_revision",
      getRegisteredView: () => ({
        // The Pulls view, played: a key moves focus to the next row and opens it.
        render(container, ctx) {
          const rows = () => container.querySelectorAll("a.github-pulls-row");
          return {
            setShown() {},
            setCurrent() {},
            setFilter() {},
            released() {},
            move(delta) {
              const all = rows();
              const at = all.indexOf(document.activeElement);
              const next = all[Math.max(0, Math.min(all.length - 1, at + delta))];
              for (const row of all) {
                row.setAttribute("tabindex", row === next ? "0" : "-1");
              }
              next.focus();
              void ctx.pullsNav.open({
                number: Number(next.dataset.number),
                tab: "",
                replace: true,
              });
              return true;
            },
            expand() {
              changedFiles[0].focus();
              return true;
            },
            collapse() {
              return true;
            },
            moveFile(delta) {
              const at = changedFiles.indexOf(document.activeElement);
              const next = changedFiles[Math.max(0, Math.min(changedFiles.length - 1, at + delta))];
              for (const row of changedFiles) {
                row.setAttribute("tabindex", row === next ? "0" : "-1");
              }
              next.focus();
              void ctx.pullsNav.open({
                number: 3900,
                tab: "files",
                file: next.dataset.file,
                replace: true,
              });
              return true;
            },
            fileLeft() {
              pulls[0].focus();
              return true;
            },
            fileRight() {
              return true;
            },
            activateFile() {
              void ctx.pullsNav.open({
                number: 3900,
                tab: "files",
                file: document.activeElement.dataset.file,
              });
              return true;
            },
            activateAnchor() {
              const row = document.activeElement;
              void ctx.pullsNav.open({
                number: Number(row.dataset.number),
                tab: "",
                replace: false,
              });
              return true;
            },
            dispose() {},
          };
        },
      }),
    },
    // The Files tree's opening, played: what app.js would open for the row.
    openTreeRow(row) {
      if (!row.dataset.path) {
        log.push(`the Files tree took the key, and opens nothing for ${row.getAttribute("href")}`);
        return;
      }
      shell.address = `/view/${row.dataset.path}`;
      log.push(`the Files tree opened ${shell.address}`);
    },
    activateTreeRowFromKeyboard: (row) => row,
    setRowExpanded() {},
  };
  context.window = context;
  vm.createContext(context);
  for (const name of [
    "keyboard-shortcuts.js",
    "tree-keyboard-navigation.js",
    "pull-route.js",
    "pulls-nav.js",
  ]) {
    const file = path.join(staticDir, name);
    vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  }
  const appPath = path.join(staticDir, "app.js");
  const appSource = fs.readFileSync(appPath, "utf8");
  const shellSource = [
    ...[
      "shortcutRegistry",
      "mainTabs",
      "keyboardHelp",
      "treeKeyboard",
      "applicationFocusRegion",
      "applicationFocusListener",
    ].map((name) => appDeclaration(appSource, new RegExp(`^var ${name} = null;$`, "m"), name)),
    ...["resolveApplicationFocusFallback", "initKeyboardInfrastructure"].map((name) =>
      appDeclaration(
        appSource,
        new RegExp(`^function ${name}\\([^)]*\\) \\{[\\s\\S]*?^\\}`, "m"),
        name,
      ),
    ),
  ].join("\n\n");
  // app.js's own handle on the pane, which the shell's other listeners hang off.
  context.treePane = document.getElementById("tree-pane");
  vm.runInContext(shellSource, context, { filename: "app.js (keyboard infrastructure)" });

  const named = (element) =>
    element === null
      ? null
      : element === document.body
        ? "the page"
        : (element.dataset.treeId ?? `${element.getAttribute("href")}`);
  return {
    context,
    files,
    pulls,
    changedFiles,
    shell,
    take: () => log.splice(0),
    /** A key pressed where focus is, and its release. */
    press(key) {
      const target = document.activeElement;
      const event = dispatch(target, "keydown", {
        key,
        repeat: false,
        altKey: false,
        ctrlKey: false,
        metaKey: false,
        shiftKey: false,
      });
      dispatch(target, "keyup", { key });
      return {
        handled: event.defaultPrevented,
        did: log.splice(0),
        "focus on": named(document.activeElement),
        address: shell.address,
      };
    },
    /** Who holds each tree's one Tab stop. */
    tabStops: () => ({
      Files: files.filter((row) => row.getAttribute("tabindex") === "0").map(named),
      Pulls: pulls.filter((row) => row.getAttribute("tabindex") === "0").map(named),
    }),
    named,
  };
}

async function twoTreesStory() {
  const page = twoTreesPage();
  const { context } = page;
  const story = {};
  context.initKeyboardInfrastructure();
  await context.MetabrowserPullsNav.init();
  await settle();
  page.take();
  story["the shell starts at a file"] = page.tabStops();
  // Pulls chosen by hand, at a file's address.
  context.MetabrowserShell.activateNavPanel("pulls");
  await settle();
  page.pulls[0].focus();
  story["a Pulls row takes focus: each tree keeps its own Tab stop"] = page.tabStops();
  story["J on it is the list's"] = page.press("j");
  story["ArrowDown too"] = page.press("ArrowDown");
  story["Enter opens the row"] = page.press("Enter");
  story["Right enters changed files"] = page.press("ArrowRight");
  story["J in changed files has its own scope"] = page.press("j");
  story["Enter in changed files pushes that file"] = page.press("Enter");
  story["Left returns to the parent pull-request row"] = page.press("ArrowLeft");
  story["the overlay closes over a Pulls row: no Files row is handed back"] = page.named(
    context.resolveApplicationFocusFallback(context.document.activeElement),
  );
  context.MetabrowserShell.activateNavPanel("files");
  page.files[0].focus();
  story["back in Files: J walks the file tree"] = page.press("j");
  story["and the Pulls list keeps its Tab stop"] = page.tabStops();
  story["the overlay closes over a Files row: the Files tree's row is handed back"] = page.named(
    context.resolveApplicationFocusFallback(context.document.activeElement),
  );
  context.MetabrowserPullsNav.dispose();
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
