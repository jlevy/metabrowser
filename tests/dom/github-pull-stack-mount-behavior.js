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
  // The shell's person glyph, Lucide's `circle-user-round`.
  const PERSON_GLYPH =
    /^<svg [^>]+><path d="M17\.925 20\.056a6 6 0 0 0-11\.851\.001"\/><circle cx="12" cy="11" r="4"\/><circle cx="12" cy="12" r="10"\/><\/svg>$/;
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
  // An author is the shell's identity (docs/design-system.md, "Actor Identity"): the avatar's
  // box, holding GitHub's avatar, then the bold name.
  const sdk = require("./sdk-ref-fixture.js").refHelpers(document);
  const identity = page.authorLabel(sdk, "octo", avatar);
  assert.deepEqual([...identity.classes], ["actor-identity", "github-pull-identity"]);
  const box = identity.children[0];
  assert.ok(box.classes.has("actor-avatar") && box.getAttribute("aria-hidden") === "true");
  const image = box.children[0];
  assert.ok(image.classes.has("actor-avatar-image"));
  assert.equal(identity.children[1].tag, "strong");
  assert.deepEqual([...identity.children[1].classes], ["actor-name", "github-pull-author"]);
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
  // A failed image gives its box to the person glyph: the box stays, so nothing moves.
  image.events.get("error")();
  assert.equal(box.children.length, 0, "the failed image leaves its box");
  assert.match(box.innerHTML, PERSON_GLYPH, "the glyph takes the box");
  assert.equal(identity.children.length, 2, "failed image retains its fixed box");
  // An avatar that is not GitHub's is never asked for: the box holds the glyph instead.
  const ghost = page.authorLabel(sdk, "ghost", "https://evil.example/track");
  assert.equal(ghost.children.length, 2, "an author with no avatar keeps the box");
  assert.equal(ghost.children[0].children.length, 0, "no image is made");
  assert.match(ghost.children[0].innerHTML, PERSON_GLYPH);
  // A Pulls row asks for no box for an author with no avatar; its row carries the avatar.
  const row = page.authorLabel(sdk, "ghost", null, "github-pulls-author", {
    placeholder: false,
  });
  assert.equal(row.children.length, 1, "a Pulls row's avatarless author has no box");
  assert.deepEqual(
    [...row.children[0].classes],
    ["actor-name", "github-pull-author", "github-pulls-author"],
  );
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
    whenIdle: require("./sdk-idle-fixture.js").whenIdle,
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
  assert.match(
    refreshing.querySelector(".github-pull-freshness").textContent,
    /^Fetched .+ via GitHub CLI$/,
  );
  // Refresh keeps its slot at the row's end, held hidden while a refresh runs.
  assert.equal(refreshing.children.at(-1).children.at(-1).hidden, true);
  assert.equal(refreshing.querySelector(".spinner"), null, "nothing spins over the cached page");
  const age = refreshing.querySelector(".github-pull-freshness");
  assert(
    age.classes.has("mb-refreshing") &&
      age.getAttribute("aria-busy") === "true" &&
      refreshing.getAttribute("aria-busy") === null,
    "the cached page's age breathes, and is the one thing busy, while it refreshes",
  );
  resolveStacks({
    status: optionalStacks.current.status,
    headers: { get: () => optionalStacks.current.etag },
    json: async () => optionalStacks.current.body,
  });
  await settle();
  assert(warm.textContent.includes("2/3"));
  const trigger = warm
    .querySelector(".github-pull-stacks")
    .querySelector(".github-pull-stack-trigger");
  assert.equal(trigger.getAttribute("aria-label"), "Navigate Stack #286, position 2 of 3");
  assert.equal(trigger.getAttribute("aria-haspopup"), "menu");
  assert(
    warm.querySelector(".github-pull-meta").children.at(-1).contains(trigger),
    "stack control ends the author's row (mb-cf0l)",
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
  // A menu of one group is named once, by the heading over its members: the host's group
  // heading, in the stack's label class (docs/design-system.md, "Stacks").
  const heading = [...members.descendants()].find(
    (element) => element.getAttribute("class") === "group-heading github-pull-stack-label",
  );
  assert.equal(heading?.textContent, "Stack #286");
  assert.equal(members.getAttribute("aria-labelledby"), heading.getAttribute("id"));
  assert.equal(members.getAttribute("aria-label"), null, "the menu has no second name");
  assert.equal(heading.parentElement?.getAttribute("role") ?? null, null, "no group role");
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
  assert.deepEqual(
    warm.querySelector(".github-pull-stacks").children.map((node) => node.getAttribute("class")),
    ["btn github-pull-stack-trigger github-pull-stack-strut"],
    "identical visible data under another source hides old badges, and keeps their slot",
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
    titleNodes: api.titleNodes,
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
  // A key held with Command, Control, or Option is the browser's: Command-R reloads,
  // Command-Left goes back, and Command-Down scrolls to the end. The menu opens and moves
  // only on unmodified keys.
  const swallowed = [];
  for (const name of ["r", "ArrowDown", "ArrowUp", "Home", "End", "Enter", " ", "Escape"]) {
    for (const modifier of ["metaKey", "ctrlKey", "altKey"]) {
      let prevented = false;
      standalone.element.events.get("keydown")({
        key: name,
        [modifier]: true,
        target: standalone.element.children[0],
        preventDefault() {
          prevented = true;
        },
        stopPropagation() {
          prevented = true;
        },
      });
      if (prevented || standalone.element.open) {
        swallowed.push(`${modifier} ${name}`);
      }
    }
  }
  assert.deepEqual(swallowed, [], "the stack menu takes no key held with a modifier");
  // On the trigger, Home and End are left alone, as on a filter's trigger; the menu stays
  // closed (docs/design-system.md, "Keys in a Menu").
  for (const name of ["Home", "End"]) {
    let prevented = false;
    standalone.element.events.get("keydown")({
      key: name,
      target: standalone.element.children[0],
      preventDefault() {
        prevented = true;
      },
      stopPropagation() {},
    });
    assert.equal(prevented || Boolean(standalone.element.open), false, `${name} opens nothing`);
  }
  // Every way the menu opens puts focus on the current member, #7, the row checked, whose
  // place in the top-first list is second (mb-xlla).
  key("ArrowDown");
  const menuLinks = standalone.element.querySelectorAll("a[href]");
  const currentMember = () =>
    standalone.element
      .querySelectorAll("a[href]")
      .find((link) => link.getAttribute("aria-current") === "page");
  assert.equal(currentMember(), menuLinks[1]);
  assert.equal(document.activeElement, menuLinks[1], "Down opens at the current member");
  key("ArrowDown");
  assert.equal(document.activeElement, menuLinks[2], "Down then moves within the menu");
  key("ArrowUp");
  assert.equal(document.activeElement, menuLinks[1]);
  key("ArrowUp");
  assert.equal(document.activeElement, menuLinks[0]);
  // With the menu open, Escape held with a modifier reaches the document's listeners, the
  // one that closes the open menu among them, and none takes it or closes the menu.
  const documentKeydowns = [...(documentEvents.get("keydown") ?? [])];
  assert(documentKeydowns.length > 0, "the open menu listens for Escape on the document");
  const escapes = [];
  for (const modifier of ["metaKey", "ctrlKey", "altKey"]) {
    for (const listener of documentKeydowns) {
      let prevented = false;
      listener({
        key: "Escape",
        [modifier]: true,
        target: menuLinks[0],
        preventDefault() {
          prevented = true;
        },
        stopPropagation() {},
      });
      if (prevented || !standalone.element.open) {
        escapes.push(modifier);
      }
    }
  }
  assert.deepEqual(escapes, [], "a modified Escape leaves the open stack menu open");
  assert.equal(document.activeElement, menuLinks[0], "a modified Escape moves no focus");
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
  assert.equal(document.activeElement, currentMember(), "Enter opens on the current member");
  key("Escape");
  assert.equal(document.activeElement, standalone.element.children[0], "and Escape gives it back");
  key(" ", standalone.element.children[0]);
  assert.equal(document.activeElement, currentMember(), "Space opens on the current member");
  key("Escape");
  key("ArrowUp");
  assert.equal(document.activeElement, currentMember(), "Up opens on the current member");
  key("Escape");
  // A press: the details opens itself, with focus on the trigger, and its toggle event
  // moves focus to the current member.
  standalone.element.children[0].focus();
  standalone.element.open = true;
  standalone.element.events.get("toggle")();
  assert.equal(document.activeElement, currentMember(), "a press opens on the current member");
  // The toggle event a key's open sends after it leaves focus where the key put it.
  key("ArrowDown");
  const moved = document.activeElement;
  standalone.element.events.get("toggle")();
  assert.equal(document.activeElement, moved, "a later toggle event takes no focus back");
  key("Escape");
  assert.equal(document.activeElement, standalone.element.children[0], "Escape returns to trigger");
  // A pull request in two stacks: each trigger names its stack before its position, as a
  // Pulls row's place names another stack (mb-xlla); in one, the position is bare.
  assert.equal(standalone.element.children[0].textContent, "3/4");
  standalone.update(
    { ...menuStack, pulls: [5, 6, 7, 8], titles: ["New base", "Base", "Current", "Top"] },
    "Current",
    true,
  );
  assert.equal(standalone.element.children[0].textContent, "90 3/4");
  standalone.update(
    { ...menuStack, pulls: [5, 6, 7, 8], titles: ["New base", "Base", "Current", "Top"] },
    "Current",
    false,
  );
  assert.equal(standalone.element.children[0].textContent, "3/4");
  const named = page.createStackMenu(menuStack, 7, {
    link: (target) => page.h("a", { href: `/pull/${target}` }),
    icon: null,
    currentTitle: "Current",
    titleNodes: api.titleNodes,
    named: true,
    onOpen() {},
  });
  assert.equal(named.element.children[0].textContent, "90 2/3");
  assert.equal(
    named.element.children[0].getAttribute("aria-label"),
    "Navigate Stack #90, position 2 of 3",
  );
  named.dispose();
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
