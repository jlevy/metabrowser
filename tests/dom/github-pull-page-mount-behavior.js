// Mount the production pull page with failed assets and renderers. Layout is irrelevant:
// this exercises the asynchronous mount, its recovery control, and replacement ownership.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const root = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/github-pull-page-responses.json"), "utf8"),
);
for (const answer of Object.values(recorded)) {
  for (const envelope of [answer.body, answer.body?.pull]) {
    const holder = envelope?.record?.same_as;
    if (holder !== undefined) {
      envelope.record = recorded[holder].body.record;
    }
  }
}
class Element {
  constructor(tag) {
    this.tag = tag;
    this.tagName = tag.toUpperCase();
    this.parentNode = null;
    this.children = [];
    this.attributes = new Map();
    this.dataset = {};
    this.events = new Map();
    this.classes = new Set();
    this.classList = {
      add: (...names) =>
        names.forEach((name) => {
          this.classes.add(name);
        }),
      remove: (...names) =>
        names.forEach((name) => {
          this.classes.delete(name);
        }),
      toggle: (name, on) => (on ? this.classes.add(name) : this.classes.delete(name)),
    };
  }
  get ownerDocument() {
    return globalThis.document;
  }
  get childNodes() {
    return this.children;
  }
  get firstChild() {
    return this.children[0] ?? null;
  }
  get lastChild() {
    return this.children.at(-1) ?? null;
  }
  get nextSibling() {
    const peers = this.parentNode?.children ?? [];
    return peers[peers.indexOf(this) + 1] ?? null;
  }
  insertBefore(node, before) {
    if (node === before) {
      return node;
    }
    node.remove();
    const at = before === null ? this.children.length : this.children.indexOf(before);
    assert(at >= 0, "insertBefore reference belongs to its parent");
    node.parentNode = this;
    this.children.splice(at, 0, node);
    return node;
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
    if (name === "class") {
      this.classes = new Set(value.split(" "));
    }
  }
  append(...children) {
    for (const child of children) {
      if (typeof child !== "string") {
        child.remove();
        child.parentNode = this;
      }
      this.children.push(child);
    }
  }
  prepend(...children) {
    this.children.unshift(...children);
  }
  replaceChildren(...children) {
    for (const child of this.children) {
      if (typeof child !== "string" && child.parentNode === this) {
        child.parentNode = null;
      }
    }
    this.children = [];
    this.append(...children);
  }
  get textContent() {
    return this.children
      .map((child) => (typeof child === "string" ? child : child.textContent))
      .join("");
  }
  set textContent(value) {
    this.children = [value];
  }
  *descendants() {
    for (const child of this.children) {
      if (typeof child !== "string") {
        yield child;
        yield* child.descendants();
      }
    }
  }
  querySelectorAll(selector) {
    const direct = selector.startsWith(":scope > ");
    const wanted = direct ? selector.slice(9) : selector;
    const nodes = direct
      ? this.children.filter((node) => typeof node !== "string")
      : [...this.descendants()];
    return nodes.filter((node) =>
      wanted === "a[href]"
        ? node.tag === "a" && node.attributes.has("href")
        : wanted.startsWith(".") && node.classes.has(wanted.slice(1)),
    );
  }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
  replaceWith(...nodes) {
    const parent = this.parentNode;
    if (!parent) {
      return;
    }
    const at = parent.children.indexOf(this);
    if (at < 0) {
      return;
    }
    parent.children.splice(at, 1, ...nodes);
    for (const node of nodes) {
      if (typeof node !== "string") {
        node.parentNode = parent;
      }
    }
    this.parentNode = null;
  }
  closest() {
    return null;
  }
  after(...nodes) {
    const parent = this.parentNode;
    if (!parent) {
      return;
    }
    for (const node of nodes) {
      if (typeof node !== "string") {
        node.remove();
        node.parentNode = parent;
      }
    }
    parent.children.splice(parent.children.indexOf(this) + 1, 0, ...nodes);
  }
  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((node) => node !== this);
    }
    this.parentNode = null;
  }
  addEventListener(name, callback) {
    this.events.set(name, callback);
  }
}
const perfEntries = [];
const perf = {
  measure(label, work) {
    try {
      return work();
    } finally {
      perfEntries.push(label);
    }
  },
  async measureAsync(label, work) {
    try {
      return await work();
    } finally {
      perfEntries.push(label);
    }
  },
};
async function settle() {
  for (let turn = 0; turn < 10; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}
async function releasedFilesMounts(page, initial, diffView, errors) {
  const results = {};
  for (const phase of ["assets", "renderer", "comparison"]) {
    let finish;
    let fail;
    const held = new Promise((resolve, reject) => {
      finish = resolve;
      fail = reject;
    });
    let started = 0;
    let disposed = 0;
    let requested = 0;
    let requestSignal;
    if (phase === "comparison") {
      window.metabrowser.fetchPluginData = (_plugin, hook, _params, options) => {
        assert.equal(hook, "pull-comparison");
        requested += 1;
        requestSignal = options?.signal;
        requestSignal?.addEventListener("abort", () => fail(requestSignal.reason), { once: true });
        return held;
      };
    }
    const readiness = () => perfEntries.filter((label) => label === "githubPull:filesReady").length;
    const readyBefore = readiness();
    const errorsBefore = errors.length;
    const container = new Element("main");
    const handle = page.mountPullPage(
      container,
      { number: 7, tab: "files", reader: { initial, fetchAfterMs: 0 } },
      {
        perf,
        ensureAsset: async () => {},
        ensureKindAssets: async () => {
          if (phase === "assets") {
            await held;
          }
        },
        getRegisteredView: () =>
          phase === "comparison"
            ? diffView
            : {
                async render() {
                  started += 1;
                  if (phase === "renderer") {
                    await held;
                  }
                  return {
                    currentFile: () => ({ kind: "file", path: "old.txt", fileId: "old" }),
                    dispose() {
                      disposed += 1;
                    },
                  };
                },
              },
        ...require("./sdk-ref-fixture.js").refHelpers(document),
        formatAge: () => ({ label: "now", className: "age" }),
        formatTimestamp: () => "now",
        navigation: { href: () => "/view/" },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
      },
    );
    await settle();
    await handle.ready;
    assert.equal(
      started,
      phase === "renderer" ? 1 : 0,
      `${phase} is held at its intended boundary`,
    );
    assert.equal(requested, phase === "comparison" ? 1 : 0);
    const host = container.querySelector(".github-pull-diff");
    assert.ok(host);
    const text = container.textContent;
    handle.cancelPending();
    const comparisonAborted = phase === "comparison" ? requestSignal?.aborted === true : null;
    if (phase === "comparison") {
      // Also settle the old unbound request on the RED side so the session can inspect it.
      fail(new DOMException("Released Files page", "AbortError"));
    } else {
      finish();
    }
    await handle.whenFilesReady();
    results[phase] = {
      started,
      disposed,
      comparisonAborted,
      preserved:
        container.querySelector(".github-pull-diff") === host && container.textContent === text,
      ownsFile: handle.currentFile() !== null,
      filesReady: readiness() - readyBefore,
      errors: errors.length - errorsBefore,
    };
    handle.dispose();
  }
  assert.deepEqual(
    results,
    {
      assets: {
        started: 0,
        disposed: 0,
        comparisonAborted: null,
        preserved: true,
        ownsFile: false,
        filesReady: 0,
        errors: 0,
      },
      renderer: {
        started: 1,
        disposed: 1,
        comparisonAborted: null,
        preserved: true,
        ownsFile: false,
        filesReady: 0,
        errors: 0,
      },
      comparison: {
        started: 0,
        disposed: 0,
        comparisonAborted: true,
        preserved: true,
        ownsFile: false,
        filesReady: 0,
        errors: 0,
      },
    },
    "released Files work cannot change the retained surface or publish a late renderer",
  );
}

async function markdownOwnership() {
  for (const delayed of ["inert", "styles"]) {
    for (const transition of ["response", "replace", "metadata", "tab", "dispose"]) {
      // Kept renders and loaded styles belong to the module, so each story has its own.
      const page = await import(
        `${pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href}?${delayed}-${transition}`
      );
      const timers = new Map();
      globalThis.document = {
        visibilityState: "visible",
        addEventListener() {},
        removeEventListener() {},
        createElement: (tag) => new Element(tag),
        importNode: () => new Element("svg"),
      };
      globalThis.window = {
        location: { pathname: "/pull/7" },
        setTimeout(callback, delay) {
          const id = Symbol();
          timers.set(id, { callback, delay });
          return id;
        },
        clearTimeout: (id) => timers.delete(id),
      };
      let release;
      const waiting = new Promise((resolve) => {
        release = resolve;
      });
      // The sanitizer is a dependency boundary here: exact HTML transfer/ownership,
      // not sanitizer policy, is exercised by this mounted controller session.
      const inert = {
        sanitizeHtml: (html) => html,
        kpressProse(html) {
          const node = document.createElement("p");
          node.textContent = html;
          return node;
        },
      };
      const first = structuredClone(recorded.current);
      first.body.record_revision = "a".repeat(64);
      first.body.record.pull.body = "plain A";
      first.body.record.issue_comments = [];
      first.body.record.reviews = [];
      first.body.record.review_comments = [];
      first.body.record.comparison = null;
      first.body.record.unavailable.comparison = "no_store";
      let current = first;
      let releaseResponse;
      let markdownReads = 0;
      let assets = 0;
      globalThis.fetch = async (route) => {
        const response = (body) => ({
          status: 200,
          headers: { get: () => null },
          json: async () => body,
        });
        if (route.startsWith("/api/plugin/github/pull-markdown")) {
          markdownReads += 1;
          const reply = response({
            fetched_at: current.body.fetched_at,
            record_revision: current.body.record_revision,
            html: current.body.record.pull.body === "plain A" ? "rendered A" : "rendered B",
            assets: {},
          });
          if (transition === "response" && markdownReads === 1) {
            return new Promise((resolve) => {
              releaseResponse = () => resolve(reply);
            });
          }
          return reply;
        }
        return route.startsWith("/api/plugin/github/pull?")
          ? response(current.body)
          : { status: 304, headers: { get: () => null } };
      };
      const container = new Element("main");
      const handle = page.mountPullPage(
        container,
        { number: 7, tab: "", reader: { initial: first, fetchAfterMs: 0 } },
        {
          perf,
          ensureAsset: async () => {
            if (delayed === "inert") {
              await waiting;
            }
            window.MetabrowserInertHtml = inert;
          },
          loadKpressAssets: () => {
            assets += 1;
            return delayed === "styles" ? waiting : Promise.resolve();
          },
          ...require("./sdk-ref-fixture.js").refHelpers(document),
          formatAge: () => ({ label: "now", className: "age" }),
          formatTimestamp: () => "now",
          navigation: { href: () => "/view/" },
          sourceKind: () => "git_revision",
          icons: { toggle: "" },
        },
      );
      const body = () =>
        [...container.descendants()].find((node) => node.getAttribute("data-part") === "body");
      const poll = async () => {
        const ready = [...timers.values()];
        timers.clear();
        for (const timer of ready) {
          timer.callback();
        }
        await settle();
      };
      await settle();
      const holding = () =>
        [...container.descendants()]
          .find((node) => node.classes.has("github-pull-body"))
          ?.classes.has("github-pull-body-holding");
      assert.equal(
        holding(),
        true,
        `${delayed}/${transition}: the first paint waits, out of sight, for the description's Markdown`,
      );
      // The wait is bounded: past it the description paints plain.
      const [hold] = [...timers].filter(([, timer]) => timer.delay === page.DESCRIPTION_HOLD_MS);
      assert.ok(hold, `${delayed}/${transition}: the first paint's wait has its bound`);
      timers.delete(hold[0]);
      hold[1].callback();
      await settle();
      assert.equal(holding(), false, `${delayed}/${transition}: past the bound it shows`);
      const old = body();
      assert.equal(
        old.textContent,
        "plain A",
        `${delayed}/${transition}: delayed positive control`,
      );
      if (["response", "replace", "metadata"].includes(transition)) {
        current = structuredClone(first);
        current.body.refreshing = true; // A harmless header paint must not strand the body.
        if (transition === "metadata") {
          current.body.fetched_at = "2026-09-17T12:00:01Z";
          current.body.record.fetched_at = current.body.fetched_at;
        } else {
          current.body.record_revision = "b".repeat(64);
          current.body.record.pull.body = "plain B"; // Deliberately the SAME fetched_at.
        }
        await poll();
        assert.equal(body().textContent, transition === "metadata" ? "plain A" : "plain B");
        if (transition === "metadata") {
          assert.equal(body(), old, "same content retains its actual element across a new model");
          assert.equal(markdownReads, 1, "timestamp-only refresh reuses the client Markdown cache");
        } else {
          assert.notEqual(body(), old, "changed text owns a new element");
          assert.equal(markdownReads, 2, "same-second new revision asks for its own Markdown");
        }
        if (releaseResponse) {
          releaseResponse();
          await settle();
        }
      } else if (transition === "tab") {
        handle.land({ tab: "files" });
        handle.land({ tab: "" });
        await settle();
        assert.equal(body(), old, "Conversation again keeps the text element it painted");
      } else {
        handle.dispose();
      }
      release();
      await settle();
      assert.equal(assets, 1, "all admitted parts share the same stylesheet readiness promise");
      const expected =
        transition === "dispose"
          ? "plain A"
          : ["replace", "response"].includes(transition)
            ? "rendered B"
            : "rendered A";
      assert.equal(
        body().textContent,
        expected,
        `${delayed}/${transition}: only current owned HTML appears`,
      );
      handle.dispose();
    }
  }
}

// Mount the page on a recorded answer, read nothing more from the server, and return what
// it painted. `ageLabel` plays the age primitive's label for a time, so a test chooses
// which ages read the same.
async function mountOn(page, body, tab, ageLabel) {
  globalThis.document = {
    visibilityState: "visible",
    addEventListener() {},
    removeEventListener() {},
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  globalThis.window = {
    location: { pathname: `/pull/${body.number}${tab ? `/${tab}` : ""}` },
    setTimeout: () => Symbol(),
    clearTimeout() {},
  };
  globalThis.fetch = async () => ({ status: 304, headers: { get: () => null } });
  const container = new Element("main");
  const handle = page.mountPullPage(
    container,
    { number: body.number, tab, reader: { initial: { etag: null, body }, fetchAfterMs: 60_000 } },
    {
      perf,
      ensureAsset: async () => {},
      ensureKindAssets: async () => {},
      ...require("./sdk-ref-fixture.js").refHelpers(document),
      formatAge: (seconds) => ({ label: ageLabel(seconds), className: "age" }),
      formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
      navigation: { href: () => "/view/" },
      sourceKind: () => "filesystem",
      icons: { toggle: "" },
    },
  );
  await settle();
  return { container, handle };
}

// The page's tabs answer to C, G, and H through the SDK's shortcut surface. The production
// shortcut registry and plugin shortcut facade (static/keyboard-shortcuts.js and
// static/plugin-shortcuts.js) load whole into a realm of their own, as `shell-tools` loads
// them, and the page's `mb.shortcuts.attach` is the facade's, as the SDK's is once it has
// loaded. Each key runs the page handle's setTab: a tab the address does not show goes
// through the route, as a click on its link does. The header keeps its tab column unless
// its first read fails (headerShape): while the record is on its way, and for an absent
// record nothing is fetching, such as a server with no GitHub repository. So the keys are
// live from first paint, as the links are. They wait while the column is out of the page,
// after a first read that failed, and return when paintHeader puts it back, badged at once
// while Shift is held; the inert stage of a retained navigation holds them; and disposal
// ends them.
async function tabKeys(page) {
  const vm = require("node:vm");
  // What the registry reads of a target: connected, enabled, not inert, and visible.
  class LiveElement extends Element {
    get isConnected() {
      let node = this;
      while (node.parentNode) {
        node = node.parentNode;
      }
      return node.connected === true;
    }
    get parentElement() {
      return this.parentNode;
    }
    get inert() {
      return this.attributes.has("inert");
    }
    hasAttribute(name) {
      return this.attributes.has(name);
    }
    checkVisibility() {
      for (let node = this; node; node = node.parentNode) {
        if (node.attributes.has("hidden")) {
          return false;
        }
      }
      return true;
    }
  }
  const listeners = [];
  const body = new LiveElement("body");
  body.connected = true;
  globalThis.document = {
    visibilityState: "visible",
    addEventListener: (type, listener) => listeners.push({ type, listener }),
    removeEventListener(type, listener) {
      const at = listeners.findIndex((entry) => entry.type === type && entry.listener === listener);
      if (at >= 0) {
        listeners.splice(at, 1);
      }
    },
    createElement: (tag) => new LiveElement(tag),
    importNode: () => new LiveElement("svg"),
    body,
  };
  const timers = new Map();
  globalThis.window = {
    location: { pathname: "/pull/7" },
    setTimeout(callback) {
      const id = Symbol();
      timers.set(id, callback);
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
  };
  let answer = recorded.pending.body;
  // A read of the record fails while this is set, as a server that cannot answer does.
  let failing = false;
  globalThis.fetch = async (route) =>
    !route.startsWith("/api/plugin/github/pull?")
      ? { status: 304, headers: { get: () => null } }
      : failing
        ? { status: 503, headers: { get: () => null } }
        : { status: 200, headers: { get: () => null }, json: async () => answer };
  const shell = {
    console,
    document: globalThis.document,
    HTMLElement: LiveElement,
    // `serialize_reserved_shell_keys()` in src/metabrowser/keymap.py, as the shell serves it.
    METABROWSER_SETTINGS: {
      RESERVED_SHELL_KEYS: {
        ...Object.fromEntries([..."tjkuwxya0123456789"].map((key) => [key, null])),
        n: ["pull-request"],
        p: ["pull-request"],
      },
    },
  };
  shell.window = shell;
  vm.createContext(shell);
  for (const name of ["keyboard-shortcuts.js", "plugin-shortcuts.js"]) {
    const file = path.join(root, "src/metabrowser/static", name);
    vm.runInContext(fs.readFileSync(file, "utf8"), shell, { filename: file });
  }
  const facade = shell.MetabrowserPluginShortcuts;
  const registry = shell.MetabrowserKeyboardShortcuts.create({ document: globalThis.document });
  const detachRegistry = facade.attachShortcutRegistry(registry);
  const opened = [];
  /** Mount #7 into a new container in the page; `reader` is the Pulls tab's, if any. */
  const mountPage = (reader) => {
    const target = new LiveElement("main");
    body.append(target);
    const mounted = page.mountPullPage(
      target,
      {
        number: 7,
        tab: "",
        open(route) {
          opened.push(route.tab);
        },
        reader,
      },
      {
        perf,
        ensureAsset: async () => {},
        ensureKindAssets: async () => {},
        ...require("./sdk-ref-fixture.js").refHelpers(globalThis.document),
        formatAge: () => ({ label: "now", className: "age" }),
        formatTimestamp: () => "now",
        navigation: { href: () => "/view/" },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
        shortcuts: { attach: facade.attachShortcut },
      },
    );
    return { container: target, handle: mounted };
  };
  /** Let every timer the page set run, as the time they wait for passing does. */
  const elapse = async () => {
    for (const callback of [...timers.values()]) {
      callback();
    }
    timers.clear();
    await settle();
  };
  let { container, handle } = mountPage({
    initial: { etag: null, body: answer },
    fetchAfterMs: 0,
  });
  await settle();
  const press = (key, init = {}) => {
    const event = {
      type: "keydown",
      key,
      code: "",
      altKey: false,
      ctrlKey: false,
      metaKey: false,
      shiftKey: false,
      repeat: false,
      isComposing: false,
      target: body,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...init,
    };
    for (const entry of listeners.filter((candidate) => candidate.type === "keydown")) {
      entry.listener(event);
    }
    return event.defaultPrevented;
  };
  const shown = () =>
    container
      .querySelectorAll(".tab-btn")
      .find((tab) => tab.getAttribute("aria-selected") === "true")?.textContent ?? "none";
  const keyed = () =>
    container
      .querySelectorAll(".tab-btn")
      .map((tab) => `${tab.textContent} ${tab.getAttribute("aria-keyshortcuts") ?? "none"}`);
  /** Each tab that carries a Shift badge now, as its label and its badge's key. */
  const badged = () =>
    container.querySelectorAll(".tab-btn").flatMap((tab) => {
      const badge = tab.children.find((node) => String(node.className).includes("kbd-badge"));
      const label = tab.children.filter((node) => node !== badge).join("");
      return badge ? [`${label} ${badge.textContent}`] : [];
    });
  const attached = () =>
    registry
      .snapshot("help", { includeInactive: true })
      .flatMap((group) => group.commands)
      .map((command) => command.bindings.visible.join(""))
      .join(" ");
  const live = () =>
    ["conversation", "files", "checks"].filter((id) =>
      registry.isLive(`plugin.github.pull.tab.${id}`),
    );
  /** Press `key`, and say what the page did: the route it opened, or the tab now shown. */
  const result = (key, init = {}) => {
    opened.length = 0;
    const handled = press(key, init);
    const name = `${init.ctrlKey ? "Ctrl+" : ""}${init.shiftKey ? "Shift+" : ""}${key.toUpperCase()}`;
    if (!handled) {
      return `${name}: not handled`;
    }
    return opened.length > 0
      ? `${name}: opened the ${opened[0] || "conversation"} route`
      : `${name}: showed ${shown()}`;
  };
  /** The route answers an opened tab as pull-route.js does: the address moves, and setTab. */
  const arrive = (tab) => {
    window.location.pathname = tab ? `/pull/7/${tab}` : "/pull/7";
    handle.setTab(tab);
  };

  const steps = [];
  assert.ok(container.querySelector(".tab-bar"), "the tab column is in from first paint");
  steps.push(
    `before the record, the tab column in the page: ${keyed().join(", ")}; ` +
      `live ${live().join(" ") || "none"}`,
  );
  steps.push(result("c"));
  steps.push(result("g"));
  // A click on Changes asks for the same route G does. The host shows the page there once
  // it is ready (static/pull-route.js), for the click and the key alike.
  opened.length = 0;
  globalThis.MouseEvent = class MouseEvent {};
  container
    .querySelectorAll(".tab-btn")
    .find((tab) => tab.textContent === "Changes")
    .events.get("click")({ preventDefault() {} });
  delete globalThis.MouseEvent;
  assert.deepEqual(opened, ["files"], "a click on Changes asks for the route G asks for");
  answer = recorded.current.body;
  await elapse();
  assert.ok(container.querySelector(".tab-bar"), "the record kept the tab column in");
  steps.push(`the record arrives and paintHeader keeps the column: ${keyed().join(", ")}`);
  steps.push(`live: ${live().join(" ")}`);
  steps.push(result("c"));
  steps.push(result("g"));
  arrive("files");
  steps.push(`the route arrives: ${shown()}`);
  steps.push(result("h", { shiftKey: true }));
  arrive("checks");
  steps.push(result("C", { shiftKey: true }));
  arrive("");
  steps.push(result("g", { ctrlKey: true }));
  const stage = new LiveElement("div");
  stage.setAttribute("inert", "");
  body.append(stage);
  stage.append(container);
  steps.push(`staged inert: ${result("g")}`);
  body.append(container);
  stage.remove();
  steps.push(`committed: ${result("g")}`);
  handle.dispose();
  steps.push(`disposed: ${keyed().join(", ")}; keys ${attached() || "none"}; ${result("g")}`);
  container.remove();
  // A page whose first read fails has nothing to show, and takes the column out; the read
  // that answers puts the same links back, keys and all. The reader has gone to Changes
  // meanwhile, so the record lands with no held first paint, and paintHeader's own retarget
  // of the returning links is what badges them at once while Shift is held. A conversation's
  // held header wakes its column instead (github-pull-first-paint-behavior.js).
  failing = true;
  ({ container, handle } = mountPage(undefined));
  await settle();
  assert.equal(container.querySelector(".tab-bar"), null, "a failed read, no tab column");
  steps.push(`a failed first read takes the column out: live ${live().join(" ") || "none"}`);
  steps.push(result("g"));
  arrive("files");
  registry.setRevealed(true);
  steps.push(`on Changes, Shift held while it is out: badges ${badged().join(", ") || "none"}`);
  failing = false;
  await elapse();
  assert.ok(container.querySelector(".tab-bar"), "the record put the tab column back");
  steps.push(`the next read answers, and the returning tabs are badged: ${badged().join(", ")}`);
  registry.setRevealed(false);
  steps.push(`the next read answers and paintHeader puts the column back: ${keyed().join(", ")}`);
  steps.push(`live: ${live().join(" ")}`);
  steps.push(result("g"));
  handle.dispose();
  steps.push(`disposed: keys ${attached() || "none"}`);
  assert.equal(
    registry.snapshot("help", { includeInactive: true }).flatMap((group) => group.commands).length,
    0,
    "disposal leaves no plugin key in Help",
  );
  detachRegistry();
  registry.dispose();
  return steps;
}

// A check row is its badge, its plain name, its action, and its description: the action
// says where it opens, is the quiet GitHub action with a leading mark only for a GitHub
// destination, names its check for a list of links, and is absent for an address a page
// may not follow. Only an Actions link stands in for the "GitHub Actions" app.
async function checkRows(page) {
  const body = structuredClone(recorded.current.body);
  body.record.check_runs.push(
    {
      id: 1,
      name: "coverage",
      status: "completed",
      conclusion: "success",
      details_url: "https://github.com/octo/demo/runs/123",
      app: "Codecov",
    },
    {
      id: 2,
      name: "lint",
      status: "completed",
      conclusion: "success",
      details_url: "https://ci.example/runs/2",
      app: "GitHub Actions",
    },
    {
      id: 3,
      name: "gist",
      status: "completed",
      conclusion: "success",
      details_url: "https://gist.github.com/octo/abc",
      app: "Gist bot",
    },
    {
      id: 4,
      name: "proxied",
      status: "completed",
      conclusion: "success",
      details_url: "https://github.com:8443/octo/demo/actions/runs/9",
      app: "Proxy",
    },
    {
      id: 5,
      name: "credentialed",
      status: "completed",
      conclusion: "success",
      details_url: "https://bot@github.com/octo/demo/runs/5",
      app: "Bot",
    },
  );
  body.record.status.statuses.push({
    context: "legacy-ci",
    state: "success",
    description: "Passed",
    target_url: "ftp://ci.example/7",
  });
  const { container, handle } = await mountOn(page, body, "checks", () => "now");
  const list = container.querySelector(".github-pull-checks");
  assert.ok(list, "the Checks tab lists its checks");
  const rows = list.children.map((row) => {
    const [badge, space, name, ...rest] = row.children;
    assert.ok(badge.classes.has("file-header-badge"), "a row leads with its status badge");
    assert.equal(space, " ");
    assert.equal(name.tag, "span");
    assert.equal(name.getAttribute("class"), null, "the name is plain text, not a link");
    const link = rest.find((node) => node.tag === "a") ?? null;
    const detail = rest.find((node) => node.classes.has("github-pull-quiet")) ?? null;
    assert.equal(rest.length, Number(link !== null) + Number(detail !== null));
    if (link !== null && detail !== null) {
      assert.equal(rest.indexOf(link), 0, "the action comes before the description");
    }
    const mark = link?.children.find(
      (node) => typeof node !== "string" && node.getAttribute("data-external-kind") !== null,
    );
    return {
      name: name.textContent,
      action:
        link === null
          ? null
          : {
              text: link.textContent,
              href: link.getAttribute("href"),
              accessibleName: link.getAttribute("aria-label"),
              quiet: link.classes.has("github-pull-external-action"),
              mark:
                mark === undefined
                  ? null
                  : `${mark.getAttribute("data-external-kind")} ${link.children.indexOf(mark) === 0 ? "before" : "after"}`,
            },
      detail: detail?.textContent ?? null,
    };
  });
  const actions = (kind, href) => ({
    text: { actions: "View action on GitHub", github: "View on GitHub", external: "View details" }[
      kind
    ],
    href,
    quiet: kind !== "external",
    mark: kind === "external" ? null : "github before",
  });
  const job = "https://github.com/octo/demo/actions/runs/18062895276/job/";
  assert.deepEqual(rows, [
    {
      name: "tests (3.13)",
      action: {
        ...actions("actions", `${job}51401654787`),
        accessibleName: "View action on GitHub: tests (3.13)",
      },
      detail: null,
    },
    {
      name: "docs",
      action: {
        ...actions("actions", `${job}51401654788`),
        accessibleName: "View action on GitHub: docs",
      },
      detail: null,
    },
    {
      name: "coverage",
      action: {
        ...actions("github", "https://github.com/octo/demo/runs/123"),
        accessibleName: "View on GitHub: coverage",
      },
      detail: "Codecov",
    },
    {
      name: "lint",
      action: {
        ...actions("external", "https://ci.example/runs/2"),
        accessibleName: "View details: lint",
      },
      detail: "GitHub Actions",
    },
    {
      name: "gist",
      action: {
        ...actions("github", "https://gist.github.com/octo/abc"),
        accessibleName: "View on GitHub: gist",
      },
      detail: "Gist bot",
    },
    {
      name: "proxied",
      action: {
        ...actions("external", "https://github.com:8443/octo/demo/actions/runs/9"),
        accessibleName: "View details: proxied",
      },
      detail: "Proxy",
    },
    {
      name: "credentialed",
      action: {
        ...actions("external", "https://bot@github.com/octo/demo/runs/5"),
        accessibleName: "View details: credentialed",
      },
      detail: "Bot",
    },
    {
      name: "docs/readthedocs.org:demo",
      action: {
        ...actions("external", "https://demo--7.org.readthedocs.build/en/7/"),
        accessibleName: "View details: docs/readthedocs.org:demo",
      },
      detail: "Read the Docs build succeeded!",
    },
    { name: "legacy-ci", action: null, detail: "Passed" },
  ]);
  const names = rows.flatMap((row) => (row.action === null ? [] : [row.action.accessibleName]));
  assert.equal(new Set(names).size, names.length, "every action has its own accessible name");
  handle.dispose();
}

// The header leaves out an updated age that reads the same as the merged or closed age
// beside it, or else the opened age, and keeps its exact time in that age's tooltip.
async function headerAges(page) {
  const said = async (name, ageLabel) => {
    const { container, handle } = await mountOn(page, recorded[name].body, "", ageLabel);
    const line = container
      .querySelector(".github-pull-header")
      .children.find((node) => node.classes?.has("github-pull-quiet"));
    const ages = line.children.filter((node) => node.classes?.has("github-pull-age"));
    const link = line.children.find((node) => node.tag === "a");
    assert.ok(link.classes.has("github-pull-external-action"), "View on GitHub is quiet");
    assert.equal(link.children[0].getAttribute("data-external-kind"), "github");
    handle.dispose();
    return {
      text: line.textContent.split(" · View on GitHub")[0],
      tips: ages.map((node) => node.getAttribute("data-tip-text")),
    };
  };
  const at = (iso) => Date.parse(iso) / 1000;
  const hour = (seconds) => new Date(seconds * 1000).toISOString().slice(0, 13);
  const day = (seconds) => new Date(seconds * 1000).toISOString().slice(0, 10);
  // Opened 10:57, updated 17:39; merged 18:00; closed 19:00, all on 2026-09-16.
  assert.deepEqual(await said("current", hour), {
    text: "Opened 2026-09-16T10 · updated 2026-09-16T17",
    tips: ["2026-09-16T10:57:23.000Z", "2026-09-16T17:39:01.000Z"],
  });
  assert.deepEqual(await said("current", day), {
    text: "Opened 2026-09-16",
    tips: ["2026-09-16T10:57:23.000Z · updated 2026-09-16T17:39:01.000Z"],
  });
  const late = (seconds) => (seconds >= at("2026-09-16T17:00:00Z") ? "late" : "early");
  assert.deepEqual(await said("merged", late), {
    text: "Opened early · merged late",
    tips: [
      "2026-09-16T10:57:23.000Z",
      "2026-09-16T18:00:00.000Z · updated 2026-09-16T17:39:01.000Z",
    ],
  });
  assert.deepEqual(await said("merged", day), {
    text: "Opened 2026-09-16 · merged 2026-09-16",
    tips: [
      "2026-09-16T10:57:23.000Z",
      "2026-09-16T18:00:00.000Z · updated 2026-09-16T17:39:01.000Z",
    ],
  });
  assert.deepEqual(await said("closed", hour), {
    text: "Opened 2026-09-16T10 · updated 2026-09-16T17 · closed 2026-09-16T19",
    tips: ["2026-09-16T10:57:23.000Z", "2026-09-16T17:39:01.000Z", "2026-09-16T19:00:00.000Z"],
  });
}

// The header's box is decided at first paint: the same rows, in the same order, whatever
// the pull request carries and whichever tab shows, and while its record is on its way.
// Each row's height is its stylesheet's (tests/test_reserved_chrome.py); here, that every
// row is there. A stack's chip has its slot at the labels row's end, held by a strut until
// one arrives; the state row holds a strut of its own; and Refresh has its slot at the
// status row's end on every tab. tests/dom/github-pull-header-chrome.mjs measures that a
// late chip moves nothing.
async function headerShape(page) {
  const rows = (container) =>
    container
      .querySelector(".github-pull-header")
      .children.map((node) =>
        node.tag === "h1"
          ? "title"
          : [...node.classes].find((name) => name.startsWith("github-pull-")).slice(12),
      );
  const age = () => "now";
  const shapes = {};
  const variants = {
    "one label": recorded.current.body,
    "no labels, a title of three lines": (() => {
      const body = structuredClone(recorded.current.body);
      body.record.pull.labels = [];
      body.record.pull.title = "A title long enough to need three lines ".repeat(6).trim();
      return body;
    })(),
    "three labels": (() => {
      const body = structuredClone(recorded.current.body);
      body.record.pull.labels = ["bug", "enhancement", "needs review"];
      return body;
    })(),
    merged: recorded.merged.body,
    stale: recorded.stale.body,
    "on its way": recorded.absent.body,
  };
  for (const [name, body] of Object.entries(variants)) {
    for (const tab of ["", "files", "checks"]) {
      const { container, handle } = await mountOn(page, body, tab, age);
      const header = container.querySelector(".github-pull-header");
      const meta = container.querySelector(".github-pull-meta");
      const labels = container.querySelector(".github-pull-labels");
      const stacks = container.querySelector(".github-pull-stacks");
      const status = container.querySelector(".github-pull-status");
      const end = status.children.at(-1);
      const refresh = end.children.at(-1);
      assert.ok(end.classes.has("github-pull-status-end"), `${name} ${tab}: offers end the row`);
      assert.equal(
        labels.children.at(-1),
        stacks,
        `${name} ${tab}: the stack slot ends the labels`,
      );
      assert.ok(
        meta.children.at(-1).classes.has("github-pull-stack-strut"),
        `${name} ${tab}: a strut holds the state row at a chip's height`,
      );
      assert.ok(
        stacks.children.length > 0 && !stacks.hidden,
        `${name} ${tab}: the stack slot is held while no stack is known`,
      );
      assert.ok(
        refresh.classes.has("github-pull-refresh"),
        `${name} ${tab}: Refresh's slot ends the status row`,
      );
      assert.ok(
        container.querySelector(".tab-bar"),
        `${name} ${tab}: the tab bar is under the header from first paint`,
      );
      assert.equal(header.parentNode.children.indexOf(header), 0);
      shapes[`${name} ${tab || "conversation"}`] = rows(container).join(" ");
      handle.dispose();
    }
  }
  assert.deepEqual(
    new Set(Object.values(shapes)),
    new Set(["title meta quiet labels status"]),
    JSON.stringify(shapes, null, 2),
  );
  // A title cut short at two lines carries the whole of it in its tooltip, and only then.
  const { container, handle } = await mountOn(page, variants["three labels"], "", age);
  const title = container.querySelector(".github-pull-title");
  const text = title.children[1];
  text.scrollHeight = 60;
  text.clientHeight = 40;
  title.events.get("pointerenter")();
  assert.equal(title.dataset.tipText, "Count to two in the app #7");
  text.scrollHeight = 40;
  title.events.get("pointerenter")();
  assert.equal(title.dataset.tipText, undefined);
  // Two lines that fit overhang their box by a descender's pixels, and are not cut short.
  text.scrollHeight = 62;
  text.clientHeight = 60;
  title.events.get("pointerenter")();
  assert.equal(title.dataset.tipText, undefined, "a whole two-line title has no tooltip");
  handle.dispose();
}

async function run() {
  const timers = new Map();
  const frames = new Map();
  const paintFrame = () => {
    const ready = [...frames.values()];
    frames.clear();
    for (const callback of ready) {
      callback();
    }
  };
  globalThis.document = {
    visibilityState: "visible",
    addEventListener() {},
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  globalThis.window = {
    location: { pathname: "/pull/7/files" },
    setTimeout: (callback) => {
      const id = Symbol();
      timers.set(id, callback);
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
    requestAnimationFrame: (callback) => {
      const id = frames.size + 1;
      frames.set(id, callback);
      return id;
    },
    cancelAnimationFrame: (id) => frames.delete(id),
  };
  globalThis.DOMParser = class {
    parseFromString() {
      return { body: { firstElementChild: new Element("svg") } };
    }
  };
  globalThis.fetch = async () => ({ status: 304, headers: { get: () => null } });
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const initial = recorded.current;
  for (const failure of ["assets", "render"]) {
    const readyBefore = perfEntries.filter((label) => label === "githubPull:filesReady").length;
    globalThis.fetch = async () => ({
      status: initial.status,
      headers: { get: () => null },
      json: async () => initial.body,
    });
    const container = new Element("main");
    let fail = true;
    let mounted = 0;
    let disposed = 0;
    let unsubscriptions = 0;
    let reportFile = null;
    let currentFile = {
      kind: "file",
      path: "src/one.py",
      fileId: "one",
      changeKind: "modified",
      availability: "ready",
    };
    const handle = page.mountPullPage(
      container,
      {
        number: 7,
        tab: "files",
        reader: { initial, fetchAfterMs: 0 },
      },
      {
        perf,
        ensureAsset: async () => {},
        ensureKindAssets: async () => {
          if (fail && failure === "assets") {
            throw Error("asset failed");
          }
        },
        getRegisteredView: () => ({
          render: async (host) => {
            if (fail && failure === "render") {
              throw Error("render failed");
            }
            mounted += 1;
            host.textContent = "Mounted comparison";
            return {
              currentFile: () => currentFile,
              onCurrentFile(listener) {
                reportFile = listener;
                listener(currentFile);
                return () => {
                  unsubscriptions += 1;
                  reportFile = null;
                };
              },
              dispose: () => {
                disposed += 1;
              },
            };
          },
        }),
        ...require("./sdk-ref-fixture.js").refHelpers(document),
        formatAge: () => ({ label: "now", className: "age" }),
        formatTimestamp: () => "now",
        navigation: { href: () => "/view/" },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
      },
    );
    await settle();
    await handle.whenFilesReady();
    const title = container.querySelector(".github-pull-title-with-state");
    assert.equal(title.tag, "h1");
    assert.ok(title.classes.has("page-heading"));
    assert.ok(title.parentNode.classes.has("page-reading-column"));
    assert.ok(container.querySelector(".tab-bar").parentNode.classes.has("page-reading-column"));
    assert.ok(!container.querySelector(".github-pull-body").classes.has("page-reading-column"));
    const [icon, titleText, , number] = title.children;
    assert.equal(icon.className, "github-pull-state-icon");
    assert.equal(icon.dataset.state, "open");
    assert.equal(icon.children[0].tag, "svg");
    assert.equal(icon.getAttribute("aria-hidden"), "true");
    assert.equal(icon.getAttribute("aria-label"), null);
    // The number is outside the text a long title is clamped in, so it is never cut off.
    assert.equal(titleText.textContent, "Count to two in the app");
    assert.ok(number.classes.has("github-pull-number"));
    assert.equal(title.textContent.endsWith("Count to two in the app #7"), true);
    const meta = container.querySelector(".github-pull-meta");
    assert.equal(
      title.parentNode.children.indexOf(meta),
      title.parentNode.children.indexOf(title) + 1,
    );
    // The state row is the badge, the details, and a strut; the stack's slot is not on it,
    // so a late chip takes no room from the sentence or the merge.
    const [stateBadgeSlot, details, stateStrut] = meta.children;
    const stateBadge = stateBadgeSlot.children[0];
    assert.ok(details.classes.has("github-pull-meta-details"));
    assert.ok(stateStrut.classes.has("github-pull-stack-strut"));
    assert.equal(meta.children.length, 3);
    assert.equal(
      container.querySelector(".github-pull-labels").children.at(-1),
      container.querySelector(".github-pull-stacks"),
    );
    assert.equal(stateBadge.getAttribute("data-state"), "open");
    assert.deepEqual(stateBadge.children, ["Open"]);
    // Merge Direction: the header names the branches head → base, through the shared group,
    // after the action the row cuts short first.
    assert.ok(details.children.at(-2).classes.has("github-pull-action"));
    assert.equal(
      details.textContent,
      "forker wants to merge 2 commits: forker:count-to-two → octo:topic",
    );
    const merge = details.children.find((node) => node.className === "merge-refs");
    assert.equal(merge.getAttribute("dir"), "ltr");
    const [source, arrow, target] = merge.children;
    assert.equal(source.dataset.tipText, "forker:count-to-two");
    assert.equal(target.dataset.tipText, "octo:topic");
    assert.equal(arrow.getAttribute("aria-label"), "merges into");
    const githubAction = [...container.descendants()].find(
      (node) => node.tag === "a" && node.textContent === "View on GitHub",
    );
    assert(githubAction);
    assert.equal(githubAction.firstChild.getAttribute("data-external-kind"), "github");
    assert.equal(githubAction.lastChild, "View on GitHub");

    assert.equal(stateBadge.getAttribute("aria-hidden"), null);
    assert.deepEqual(
      container
        .querySelectorAll(".tab-btn")
        .filter((tab) => tab.getAttribute("role") === "tab")
        .map((tab) => [tab.textContent, tab.getAttribute("href")]),
      [
        ["Conversation", "/pull/7"],
        ["Changes", "/pull/7/files"],
        ["Checks", "/pull/7/checks"],
      ],
    );
    assert.match(container.textContent, /Changes could not load/);
    assert.equal(
      perfEntries.filter((label) => label === "githubPull:filesReady").length,
      readyBefore,
      "failed assets and renderer rejection are not useful Files readiness",
    );
    const retry = [...container.descendants()].find(
      (element) => element.tag === "button" && element.textContent === "Retry",
    );
    assert.ok(retry, "a failed mount offers recovery");
    assert.equal(handle.currentFile(), null);
    const files = [];
    const unwatchFile = handle.onCurrentFile((file) => files.push(file?.path ?? null));
    fail = false;
    retry.events.get("click")();
    await settle();
    await handle.whenFilesReady();
    assert.match(container.textContent, /Mounted comparison/);
    assert.equal(mounted, 1);
    assert.equal(
      perfEntries.filter((label) => label === "githubPull:filesReady").length,
      readyBefore + 1,
      "the current successful renderer reports useful DOM readiness",
    );
    assert.equal(handle.currentFile().path, "src/one.py");
    assert.equal(reportFile, null, "readiness settles without subscribing in the mount task");
    const immediate = [];
    handle.onCurrentFile((file) => immediate.push(file?.path ?? null))();
    assert.deepEqual(immediate, ["src/one.py"], "explicit subscribers get an immediate snapshot");
    paintFrame();
    assert.equal(reportFile, null, "the first frame may paint before the bridge reads layout");
    currentFile = { ...currentFile, path: "src/two.py", fileId: "two" };
    paintFrame();
    assert.equal(files.at(-1), "src/two.py", "the bridge reads the latest selection after paint");
    currentFile = { ...currentFile, path: "src/three.py", fileId: "three" };
    reportFile(currentFile);
    assert.equal(files.at(-1), "src/three.py", "the page forwards a hand-scrolled file");
    handle.land({ tab: "" });
    assert.equal(unsubscriptions, 1, "replacement releases the diff subscription");
    handle.setTab("files");
    await settle();
    await handle.whenFilesReady();
    paintFrame();
    const abandoned = [...frames.values()][0];
    assert.ok(abandoned, "the replacement owns a pending second frame");
    handle.land({ tab: "" });
    assert.equal(frames.size, 0, "replacement cancels the pending frame");
    handle.setTab("files");
    await settle();
    await handle.whenFilesReady();
    const disposedFrame = [...frames.values()][0];
    abandoned();
    assert.equal(reportFile, null, "an already queued old frame cannot observe its replacement");
    unwatchFile();
    handle.dispose();
    disposedFrame();
    assert.equal(reportFile, null, "disposal makes queued bridge work inert");
    assert.equal(frames.size, 0, "disposal cancels owned frames");
    handle.onCurrentFile(() => {
      throw Error("a disposed page must not retain subscriptions");
    });
    assert.equal(disposed, 3);
    retry.events.get("click")();
    await settle();
    assert.equal(mounted, 3, "a stale Retry cannot remount a disposed page");
  }
  for (const outcome of ["same", "moved", "failed"]) {
    let current = structuredClone(initial.body);
    let reply;
    const requests = [];
    const mounted = [];
    let disposed = 0;
    globalThis.fetch = async (_route, options = {}) => {
      if (options.method === "POST") {
        requests.push(JSON.parse(options.body));
        return new Promise((resolve) => {
          reply = resolve;
        });
      }
      return { status: 200, headers: { get: () => null }, json: async () => current };
    };
    const container = new Element("main");
    const handle = page.mountPullPage(
      container,
      {
        number: 7,
        tab: "files",
        reader: { initial, fetchAfterMs: 0 },
      },
      {
        perf,
        ensureAsset: async () => {},
        ensureKindAssets: async () => {},
        getRegisteredView: () => ({
          render: async (host, options) => {
            mounted.push(options.comparison);
            host.textContent = "Displayed changes";
            return {
              dispose: () => {
                disposed += 1;
              },
            };
          },
        }),
        ...require("./sdk-ref-fixture.js").refHelpers(document),
        formatAge: () => ({ label: "now", className: "age" }),
        formatTimestamp: () => "now",
        navigation: { href: () => "/view/" },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
      },
    );
    const tick = async () => {
      const [id, callback] = timers.entries().next().value;
      timers.delete(id);
      callback();
      await settle();
    };
    await settle();
    await handle.whenFilesReady();
    assert.equal(mounted.length, 1);
    const displayed = { base: mounted[0].left, head: mounted[0].right };
    if (outcome === "moved") {
      current = structuredClone(current);
      current.record.comparison.head = "e".repeat(40);
      current.record.pull.head.sha = "e".repeat(40);
      await tick();
      assert.equal(mounted.length, 1, "a metadata-only head advance retains displayed changes");
    }
    const refresh = [...container.descendants()].find(
      (element) => element.tag === "button" && element.textContent === "Refresh",
    );
    assert.ok(refresh, "fresh Files offers explicit repair");
    refresh.events.get("click")();
    await settle();
    refresh.events.get("click")();
    await settle();
    assert.deepEqual(requests, [{ number: 7, retry: true, recovery: displayed }]);
    assert.equal(mounted.length, 1, "a pending POST cannot remount");
    current = { ...current, refreshing: true };
    reply({ status: 202, headers: { get: () => null }, json: async () => ({ pull: current }) });
    await settle();
    await tick();
    assert.equal(mounted.length, 1, "waiting for a job cannot remount");
    current = {
      ...current,
      refreshing: false,
      last_refresh: {
        outcome: outcome === "failed" ? "network_error" : "succeeded",
        message: outcome === "failed" ? "offline" : null,
        reset_at: null,
        at: current.fetched_at,
      },
    };
    await tick();
    await handle.whenFilesReady();
    assert.equal(mounted.length, outcome === "failed" ? 1 : 2);
    assert.equal(disposed, outcome === "failed" ? 0 : 1);
    assert.deepEqual(mounted.at(-1), mounted[0], "repair never selects a newer head");
    if (outcome === "moved") {
      assert.match(container.textContent, /Show the newer changes/);
    }
    await tick();
    assert.equal(mounted.length, outcome === "failed" ? 1 : 2, "only one remount per repair");
    handle.dispose();
    refresh.events.get("click")();
    await settle();
    assert.equal(requests.length, 1, "disposed Refresh is inert");
  }
  const checkout = JSON.parse(
    fs.readFileSync(
      path.join(root, "tests/fixtures/github-checkout-comparison-responses.json"),
      "utf8",
    ),
  );
  const posts = [];
  const comparisonAsk = { number: 10, retry: true, comparison: true };
  let resolveComparison;
  globalThis.fetch = async (_route, options = {}) => {
    if (options.method === "POST") {
      posts.push(JSON.parse(options.body));
      if (posts.length === 1) {
        return new Promise((resolve) => {
          resolveComparison = resolve;
        });
      }
    }
    const answer = options.method === "POST" ? checkout.started : checkout.before;
    return { status: answer.status, headers: { get: () => null }, json: async () => answer.body };
  };
  window.location.pathname = "/pull/10";
  const checkoutContainer = new Element("main");
  const checkoutHandle = page.mountPullPage(
    checkoutContainer,
    {
      number: 10,
      tab: "files",
      reader: { initial: checkout.before, fetchAfterMs: 0 },
    },
    {
      perf,
      ensureAsset: async () => {},
      ensureKindAssets: async () => {},
      getRegisteredView: () => {
        throw new Error("no comparison exists before acquisition");
      },
      ...require("./sdk-ref-fixture.js").refHelpers(document),
      formatAge: () => ({ label: "now", className: "age" }),
      formatTimestamp: () => "now",
      navigation: { href: () => "/view/" },
      sourceKind: () => "filesystem",
      icons: { toggle: "" },
    },
  );
  await settle();
  assert.deepEqual(posts, [], "a staged Changes mount cannot fetch after the route moved away");
  const stagedBody = checkoutContainer.querySelector(".github-pull-body");
  assert.match(stagedBody.textContent, /Changes have not been fetched/);
  assert.equal(stagedBody.querySelector(".spinner"), null, "nothing is on its way to spin for");
  assert.equal(
    stagedBody.querySelector(".github-pull-fetch-changes")?.textContent,
    "Fetch changes",
    "the reader can still fetch what the address does not ask for",
  );
  window.location.pathname = "/pull/10/files/src/app.txt";
  checkoutHandle.land({ tab: "files", file: "src/app.txt" });
  await settle();
  const checkoutBody = checkoutContainer.querySelector(".github-pull-body");
  assert.deepEqual(posts, [comparisonAsk]);
  const acquiring = checkoutBody.querySelector(".github-pull-changes-pending");
  assert.match(acquiring?.getAttribute("aria-label") ?? "", /Fetching changes/);
  assert.ok(acquiring.classes.has("mb-delayed-loading"), "after the quiet period");
  assert.ok(checkoutBody.querySelector(".spinner"));
  assert.equal(checkoutBody.querySelector(".github-pull-retry-changes"), null);
  resolveComparison({
    status: 429,
    headers: { get: () => null },
    json: async () => ({ error: "server busy" }),
  });
  await settle();
  const [checkoutPollId, checkoutPoll] = timers.entries().next().value;
  timers.delete(checkoutPollId);
  checkoutPoll();
  await settle();
  assert.deepEqual(posts, [comparisonAsk], "polling does not retry a refused acquisition");
  assert.match(checkoutBody.textContent, /Changes could not be fetched/);
  assert.match(
    checkoutContainer.querySelector(".github-pull-message")?.textContent ?? "",
    /server busy/,
    "the refusal's reason outlasts the read that cleared its error",
  );
  assert.equal(checkoutBody.querySelector(".spinner"), null);
  const retryChanges = checkoutBody.querySelector(".github-pull-retry-changes");
  assert.equal(retryChanges?.textContent, "Retry changes");
  retryChanges.events.get("click")();
  retryChanges.events.get("click")();
  await settle();
  assert.deepEqual(posts, [comparisonAsk, comparisonAsk], "only one explicit retry is admitted");
  assert.equal(checkoutBody.querySelector(".github-pull-retry-changes"), null);
  checkoutHandle.dispose();
  retryChanges.events.get("click")();
  await settle();
  assert.equal(posts.length, 2, "a disposed Retry button starts nothing");
  window.location.pathname = "/pull/7/files";
  globalThis.fetch = async () => ({
    status: initial.status,
    headers: { get: () => null },
    json: async () => initial.body,
  });
  // A comparison request failure is handled inside the production diff renderer: it
  // resolves with a disposable error notice, rather than rejecting the mount.
  let diffView;
  let failureStatus;
  const errors = [];
  window.metabrowser = {
    registerView: (_kind, _name, view) => {
      diffView = view;
    },
    fetchPluginData: async () => {
      throw Object.assign(new Error("comparison failed"), { status: failureStatus });
    },
  };
  const logError = console.error;
  console.error = (...args) => errors.push(args);
  try {
    await import(pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/diff/index.js")));
    for (failureStatus of [404, 409]) {
      const readyBefore = perfEntries.filter((label) => label === "githubPull:filesReady").length;
      const container = new Element("main");
      const handle = page.mountPullPage(
        container,
        { number: 7, tab: "files", reader: { initial, fetchAfterMs: 0 } },
        {
          perf,
          ensureAsset: async () => {},
          ensureKindAssets: async () => {},
          getRegisteredView: () => diffView,
          ...require("./sdk-ref-fixture.js").refHelpers(document),
          formatAge: () => ({ label: "now", className: "age" }),
          formatTimestamp: () => "now",
          navigation: { href: () => "/view/" },
          sourceKind: () => "git_revision",
          icons: { toggle: "" },
        },
      );
      await settle();
      await handle.whenFilesReady();
      assert.match(container.textContent, /Could not load this diff/);
      assert.equal(
        perfEntries.filter((label) => label === "githubPull:filesReady").length,
        readyBefore,
        "a resolved production 404/409 notice is not useful Files readiness",
      );
      const absent = { kind: "no_diff", path: "src/app.txt" };
      assert.deepEqual(handle.fileForPath(absent.path), absent);
      assert.deepEqual(handle.scrollToFile(absent.path), absent);
      handle.dispose();
      assert.deepEqual(handle.scrollToFile(absent.path), absent);
    }
    assert.deepEqual(
      errors.map((entry) => entry[1].status),
      [404, 409],
    );
    await releasedFilesMounts(page, initial, diffView, errors);
  } finally {
    console.error = logError;
  }
  delete window.requestAnimationFrame;
  delete window.cancelAnimationFrame;
  document.visibilityState = "hidden";
  const fallbackTasks = new Map();
  window.setTimeout = (callback, delay) => {
    const id = Symbol();
    fallbackTasks.set(id, { callback, delay });
    return id;
  };
  window.clearTimeout = (id) => fallbackTasks.delete(id);
  let hiddenSubscriptions = 0;
  let hiddenUnsubscriptions = 0;
  const hiddenOptions = { number: 7, tab: "files", reader: { initial, fetchAfterMs: 0 } };
  const hiddenApi = {
    perf,
    ensureAsset: async () => {},
    ensureKindAssets: async () => {},
    getRegisteredView: () => ({
      render: async () => ({
        currentFile: () => ({ kind: "file", path: "src/now.py", fileId: "now" }),
        onCurrentFile(listener) {
          hiddenSubscriptions += 1;
          listener({ kind: "file", path: "src/now.py", fileId: "now" });
          return () => {
            hiddenUnsubscriptions += 1;
          };
        },
        dispose() {},
      }),
    }),
    ...require("./sdk-ref-fixture.js").refHelpers(document),
    formatAge: () => ({ label: "now", className: "age" }),
    formatTimestamp: () => "now",
    navigation: { href: () => "/view/" },
    sourceKind: () => "git_revision",
    icons: { toggle: "" },
  };
  const hidden = page.mountPullPage(new Element("main"), hiddenOptions, hiddenApi);
  await settle();
  await hidden.whenFilesReady();
  assert.equal(hiddenSubscriptions, 0, "hidden/no-frame readiness does not wait for the bridge");
  const fallback = [...fallbackTasks.values()].find((task) => task.delay === 0);
  assert.ok(fallback, "a nonvisual host owns a later bridge task");
  hidden.dispose();
  fallback.callback();
  assert.equal(hiddenSubscriptions, 0, "disposal invalidates even a queued fallback task");
  assert.equal(fallbackTasks.size, 0);
  const reentrant = page.mountPullPage(new Element("main"), hiddenOptions, hiddenApi);
  await settle();
  await reentrant.whenFilesReady();
  let armed = false;
  reentrant.onCurrentFile(() => {
    if (armed) {
      reentrant.dispose();
    }
  });
  armed = true;
  const reentrantTask = [...fallbackTasks.values()].find((task) => task.delay === 0);
  assert.ok(reentrantTask);
  reentrantTask.callback();
  assert.equal(hiddenSubscriptions, 1);
  assert.equal(
    hiddenUnsubscriptions,
    1,
    "reentrant disposal releases the just-created subscription",
  );
  await markdownOwnership();
  await checkRows(page);
  await headerAges(page);
  await headerShape(page);
  const tabKeySteps = await tabKeys(page);
  for (const label of [
    "githubPull:decode",
    "githubPull:render",
    "githubPull:filesRender",
    "githubPull:conversationReady",
  ]) {
    assert(perfEntries.includes(label), `the existing profiler receives ${label}`);
  }
  return {
    titleStateAndTextBadge: true,
    failedAssetsRecover: true,
    failedRenderRecovers: true,
    staleRetryIsInert: true,
    checkoutFetchIsAutomatic: true,
    displayedComparisonRepair: true,
    bridgeAfterPaint: true,
    bridgeFramesOwned: true,
    hiddenReadiness: true,
    markdownOwnership: true,
    checkRows: true,
    headerAges: true,
    headerShape: true,
    tabKeys: tabKeySteps,
  };
}
module.exports = { Element, recorded, root, settle, perf };
if (require.main === module) {
  run()
    .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
    .catch((error) => {
      process.stderr.write(`${error.stack}\n`);
      process.exitCode = 1;
    });
}
