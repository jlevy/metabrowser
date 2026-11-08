const assert = require("node:assert/strict");
const optionalStacks = require("../fixtures/github-stacks-responses.json");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");
(async () => {
  const timers = new Map();
  const documentEvents = new Map();
  globalThis.Node = Element;
  globalThis.HTMLElement = Element;
  Object.defineProperty(Element.prototype, "isConnected", {
    get() {
      return this.tag === "main" || Boolean(this.parentNode?.isConnected);
    },
  });
  Element.prototype.focus = function () {
    document.activeElement = this;
  };
  Element.prototype.scrollIntoView = () => {};
  Element.prototype.contains = function (node) {
    return this === node || [...this.descendants()].includes(node);
  };
  // Real replacement detaches focused descendants even if the same nodes return.
  const replace = Element.prototype.replaceChildren;
  Element.prototype.replaceChildren = function (...nodes) {
    if (this !== document.activeElement && this.contains(document.activeElement)) {
      document.activeElement = null;
    }
    replace.call(this, ...nodes);
  };
  const captures = new WeakMap();
  const listen = Element.prototype.addEventListener;
  Element.prototype.addEventListener = function (name, listener, options) {
    listen.call(this, name, listener);
    if (options?.capture) {
      const events = captures.get(this) ?? new Map();
      events.set(name, listener);
      captures.set(this, events);
    }
  };
  globalThis.document = {
    visibilityState: "visible",
    addEventListener(name, listener, options) {
      const listeners = documentEvents.get(name) ?? new Set();
      listeners.add(listener);
      documentEvents.set(name, listeners);
      options?.signal?.addEventListener("abort", () => listeners.delete(listener), { once: true });
    },
    removeEventListener(name, listener) {
      documentEvents.get(name)?.delete(listener);
    },
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  globalThis.window = {
    location: { pathname: "/pull/7/files" },
    setTimeout(callback) {
      const id = Symbol();
      timers.set(id, callback);
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
  };
  globalThis.MouseEvent = class {};
  globalThis.DOMParser = class {
    parseFromString() {
      return { body: { firstElementChild: null } };
    }
  };
  let resolveCore;
  let resolveStacks;
  const calls = [];
  globalThis.fetch = (route, options = {}) => {
    calls.push([options.method ?? "GET", route]);
    if (route === "/api/plugin/github/stacks") {
      return new Promise((resolve) => {
        resolveStacks = resolve;
      });
    }
    if (route.startsWith("/api/plugin/github/pull?")) {
      return new Promise((resolve) => {
        resolveCore = resolve;
      });
    }
    return Promise.resolve({ status: 304, headers: { get: () => null } });
  };
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const avatar = "https://avatars.githubusercontent.com/u/123?s=40";
  for (const unsafe of [
    null,
    "",
    "https://evil.example/u/123?s=40",
    "http://avatars.githubusercontent.com/u/123?s=40",
    "https://avatars.githubusercontent.com:443/u/123?s=40",
    `${avatar}#x`,
    `${avatar}&x=1`,
    "https://avatars.githubusercontent.com/u/123456789012345678901?s=40",
    "https://avatars.githubusercontent.com/u/123?s=40\n",
  ]) {
    assert.equal(page.avatarUrl(unsafe), null, `unsafe avatar ${unsafe}`);
  }
  assert.equal(page.avatarUrl(avatar), avatar);
  assert.equal(
    page.avatarUrl("https://avatars.githubusercontent.com/in/42?s=40"),
    "https://avatars.githubusercontent.com/in/42?s=40",
  );
  const identity = page.authorLabel("octo", avatar);
  const image = identity.children[0];
  assert.equal(identity.textContent, "octo");
  for (const [name, value] of Object.entries({
    alt: "",
    width: "18",
    height: "18",
    loading: "lazy",
    decoding: "async",
    fetchpriority: "low",
    crossorigin: "anonymous",
    referrerpolicy: "no-referrer",
    src: avatar,
  })) {
    assert.equal(image.attributes.get(name), value);
  }
  assert.equal(
    [...image.attributes.keys()].at(-1),
    "src",
    "privacy/layout attributes precede the request",
  );
  image.style = {};
  image.events.get("error")();
  assert.equal(image.style.visibility, "hidden");
  assert.equal(identity.children.length, 2, "failed image retains its fixed slot");
  assert.equal(page.authorLabel("ghost", "https://evil.example/track").children.length, 1);
  const merged = structuredClone(recorded.current.body);
  merged.record.pull.merged = true;
  merged.record.pull.merged_by = "merger";
  merged.record.pull.author_avatar_url = avatar;
  merged.record.pull.merged_by_avatar_url = "https://avatars.githubusercontent.com/u/456?s=40";
  const mergedModel = page.describePull(merged, {
    number: 7,
    tab: "",
    nowMs: Date.parse(merged.fetched_at),
  });
  assert.equal(mergedModel.pull.actor, "merger");
  assert.equal(mergedModel.pull.actorAvatar, merged.record.pull.merged_by_avatar_url);
  const api = {
    ...require("./sdk-ref-fixture.js").refHelpers(document),
    perf,
    ensureAsset: async () => {},
    ensureKindAssets: async () => {},
    getRegisteredView: () => ({ render: async () => ({ dispose() {} }) }),
    formatAge: () => ({ label: "now", className: "age" }),
    formatTimestamp: () => "now",
    navigation: { href: () => "/view/" },
    sourceKind: () => "git_revision",
    icons: { toggle: "" },
  };
  const opened = [];
  const container = new Element("main");
  const handle = page.mountPullPage(
    container,
    { number: 7, tab: "files", open: (route) => opened.push(route) },
    api,
  );
  assert(container.querySelector(".recent-loading"), "cold page has shared skeleton shape");
  assert.equal(container.querySelector(".spinner"), null);
  const pending = structuredClone(recorded.current.body);
  pending.record = null;
  pending.record_revision = null;
  pending.state = "pending";
  pending.refreshing = true;
  resolveCore({ status: 200, headers: { get: () => "pending" }, json: async () => pending });
  await settle();
  assert(container.querySelector(".recent-loading"), "pending cold fetch retains skeleton");
  handle.dispose();
  assert.equal(timers.size, 0);
  // A late optional answer cannot paint its disposed page; the next owner reads afresh.
  resolveStacks({ status: 200, headers: { get: () => null }, json: async () => ({}) });
  await settle();
  const warm = new Element("main");
  const current = structuredClone(recorded.current);
  current.body.refreshing = true;
  const next = page.mountPullPage(
    warm,
    {
      number: 7,
      tab: "files",
      open: (route) => opened.push(route),
      reader: { initial: current, fetchAfterMs: 0 },
    },
    api,
  );
  await settle();
  assert.equal(
    warm.querySelector(".recent-loading"),
    null,
    "cached refreshing page remains readable",
  );
  assert(warm.textContent.includes(current.body.record.pull.title));
  const refreshing = warm.querySelector(".github-pull-status");
  assert.match(refreshing.textContent, /^Refreshing… · fetched .+ via GitHub CLI$/);
  assert(refreshing.querySelector(".spinner"), "cached refreshing status includes a spinner");
  resolveStacks({
    status: optionalStacks.current.status,
    headers: { get: () => optionalStacks.current.etag },
    json: async () => optionalStacks.current.body,
  });
  await settle();
  assert(warm.textContent.includes("2/3"));
  const trigger = warm.querySelector(".github-pull-stack-trigger");
  assert.equal(trigger.getAttribute("aria-label"), "Navigate Stack #286, position 2 of 3");
  assert.equal(trigger.getAttribute("aria-haspopup"), "menu");
  assert(
    warm.querySelector(".github-pull-meta").contains(trigger),
    "stack control shares the state row",
  );
  assert(warm.querySelector(".github-pull-author"), "page actor uses semantic username treatment");
  const disclosure = warm.querySelector(".github-pull-stack-disclosure");
  assert.equal(warm.querySelector(".github-pull-stack-menu"), null, "member list is lazy");
  disclosure.open = true;
  disclosure.events.get("toggle")();
  const members = warm.querySelector(".github-pull-stack-menu");
  assert.deepEqual(
    [...members.descendants()].filter((item) => item.tag === "a").map((item) => item.textContent),
    ["3/3 · Stack change 8 · #8", "✓2/3 · Stack change 7 · #7", "1/3 · Stack change 6 · #6"],
  );
  const anchors = [...members.descendants()].filter((element) => element.tag === "a");
  anchors[0].focus();
  next.setTab("files");
  await settle();
  assert.equal(disclosure.open, true, "same-page repaint retains the open disclosure");
  assert.equal(document.activeElement, anchors[0], "same-page repaint retains menu focus");

  const previous = anchors.find((element) => element.getAttribute("href") === "/pull/6/files");
  const following = anchors.find((element) => element.getAttribute("href") === "/pull/8/files");
  assert(previous);
  assert(following);
  assert.equal(anchors[1].getAttribute("aria-current"), "page");
  next.activate();
  assert.equal(next.hasStack(), true);
  assert.equal(next.moveStack(-1), true);
  assert.deepEqual(opened.at(-1), {
    number: 6,
    tab: "files",
    reader: { fetchAfterMs: 0, initial: null },
  });
  following.focus();
  const captureClick = captures.get(members)?.get("click");
  assert.equal(typeof captureClick, "function", "menu activation precedes link navigation");
  const activate = (modifiers = {}) => {
    const event = Object.assign(new MouseEvent(), {
      button: 0,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...modifiers,
    });
    captureClick(event);
    assert.equal(document.activeElement, trigger, "focus leaves the hidden menu before navigation");
    assert.equal(disclosure.open, false);
    following.events.get("click")(event);
    return event;
  };
  assert.equal(activate().defaultPrevented, true, "plain activation keeps local navigation");
  assert.deepEqual(opened.at(-1), {
    number: 8,
    tab: "files",
    reader: { fetchAfterMs: 0, initial: null },
  });
  for (const modifiers of [{ metaKey: true }, { ctrlKey: true }, { button: 1 }]) {
    disclosure.open = true;
    following.focus();
    const count = opened.length;
    assert.equal(activate(modifiers).defaultPrevented, false, "native link behavior is preserved");
    assert.equal(opened.length, count, "modified clicks do not open a local page");
    assert.equal(following.getAttribute("href"), "/pull/8/files");
  }
  const outsideFocus = new Element("button");
  document.activeElement = outsideFocus;
  disclosure.open = true;
  captureClick({});
  assert.equal(
    document.activeElement,
    outsideFocus,
    "pointer dismissal does not steal other focus",
  );
  assert.equal(
    calls.filter(([, route]) => route === "/api/plugin/github/stacks").length,
    2,
    "each mounted lifetime has one shared repository read, never one read per member",
  );
  const differentOwner = structuredClone(current.body);
  differentOwner.record.source = "https://github.com/octo/another";
  resolveCore({
    status: 200,
    headers: { get: () => "different-owner" },
    json: async () => differentOwner,
  });
  await settle();
  assert.equal(
    warm.querySelector(".github-pull-stacks").hidden,
    true,
    "identical visible data under another source hides old badges",
  );
  next.dispose();
  assert.equal(timers.size, 0);
  following.events.get("click")({ preventDefault() {} });
  assert.equal(opened.length, 2, "disposed stack links cannot navigate");
  assert.equal(next.hasStack(), false);
  assert.equal(next.moveStack(1), false);
  // Optional ownership must repaint even when all visible PR data is byte-identical.
  assert.equal(
    documentEvents.get("pointerdown").size,
    0,
    "disposed menus release outside listeners",
  );
  const menuStack = {
    number: 90,
    base_ref: "main",
    open: true,
    pulls: [6, 7, 8],
    titles: ["Base", "Current", "Top"],
  };
  const standalone = page.createStackMenu(menuStack, 7, {
    link: (target) => page.h("a", { href: `/pull/${target}/checks` }),
    icon: null,
    currentTitle: "Current",
    onOpen() {},
  });
  const menuHost = new Element("main");
  menuHost.append(standalone.element);
  const key = (name, target = null) =>
    standalone.element.events.get("keydown")({
      key: name,
      target,
      preventDefault() {},
      stopPropagation() {},
    });
  key("ArrowDown");
  const menuLinks = standalone.element.querySelectorAll("a[href]");
  assert.equal(document.activeElement, menuLinks[0], "Down opens at the top stack member");
  key("End");
  assert.equal(document.activeElement, menuLinks[2]);
  key("Home");
  assert.equal(document.activeElement, menuLinks[0]);
  standalone.update(
    { ...menuStack, titles: ["Base", "Current", "<script>updated title</script>"] },
    "Current",
  );
  assert.equal(document.activeElement, menuLinks[0], "title refresh preserves focused row");
  assert.equal(standalone.element.open, true, "title refresh keeps the menu open");
  assert(
    menuLinks[0].textContent.includes("<script>updated title</script>"),
    "title remains plain text",
  );
  standalone.update(
    {
      ...menuStack,
      pulls: [5, 6, 7, 8],
      titles: ["New base", "Base", "Current", "Top"],
    },
    "Current",
  );
  assert.equal(standalone.element.querySelectorAll("a[href]")[0], menuLinks[0]);
  assert.equal(
    document.activeElement,
    menuLinks[0],
    "membership update retains focused link identity",
  );
  assert.equal(standalone.element.open, true, "membership update preserves open disclosure");
  assert.equal(standalone.element.children[0].textContent, "3/4");
  key("Escape");
  assert.equal(standalone.element.open, false);
  assert.equal(document.activeElement, standalone.element.children[0], "Escape returns to trigger");
  key("Enter", standalone.element.children[0]);
  assert.equal(document.activeElement, menuLinks[0], "Enter opens and focuses the first menu row");
  key("Escape");
  key("ArrowUp");
  assert.equal(document.activeElement, standalone.element.querySelectorAll("a[href]").at(-1));
  for (const listener of documentEvents.get("pointerdown")) {
    listener({ target: new Element("button") });
  }
  assert.equal(standalone.element.open, false, "outside pointer dismisses the menu");
  standalone.dispose();
  assert.equal(documentEvents.get("pointerdown").size, 0);
  assert.equal(documentEvents.get("keydown").size, 0);
  const identities = [];
  const models = [];
  let answer = structuredClone(recorded.current.body);
  const identityController = page.createPullController(
    {
      request: async () => ({ status: 200, etag: null, body: answer }),
      now: () => Date.parse(recorded.current.body.fetched_at),
      schedule(callback) {
        const id = Symbol();
        timers.set(id, callback);
        return id;
      },
      cancel: (id) => timers.delete(id),
      isVisible: () => true,
      render(model, identity) {
        if (identity) {
          identities.push(identity);
          models.push(model);
        }
      },
      renderMarkdown() {},
      reload() {},
      navigate() {},
    },
    { number: 7, tab: "" },
  );
  await identityController.start();
  answer = structuredClone(answer);
  answer.record.source = "https://github.com/octo/another";
  await identityController.poll();
  assert.equal(identities.length, 2);
  assert.notEqual(identities[0].source, identities[1].source);
  assert.deepEqual(
    models[0],
    models[1],
    "identity-only response must invalidate enrichment independently",
  );
  identityController.dispose();
  assert.equal(timers.size, 0);
  console.log(
    JSON.stringify({
      coldSkeleton: true,
      pendingSkeleton: true,
      cachedRefreshRetained: true,
      authoritativeStack: true,
      orderedNeighbors: true,
      stackActivationFocus: true,
      tabPreserved: true,
      fileCleared: true,
      explicitReaderIntent: true,
      disposedWorkReleased: true,
    }),
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
