const assert = require("node:assert/strict");
const optionalStacks = require("../fixtures/github-stacks-responses.json");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");
(async () => {
  const timers = new Map();
  globalThis.document = {
    visibilityState: "visible",
    addEventListener() {},
    removeEventListener() {},
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
  assert.match(refreshing.textContent, /^Refreshing… · fetched .+ by /);
  assert(refreshing.querySelector(".spinner"), "cached refreshing status includes a spinner");
  resolveStacks({
    status: optionalStacks.current.status,
    headers: { get: () => optionalStacks.current.etag },
    json: async () => optionalStacks.current.body,
  });
  await settle();
  assert(warm.textContent.includes("Stack #286"));
  assert(warm.textContent.includes("2 of 3"));
  assert(warm.querySelector(".github-pull-author"), "page actor uses semantic username treatment");
  const disclosure = warm.querySelector(".github-pull-stack-disclosure");
  assert.equal(warm.querySelector(".github-pull-stack-members"), null, "member list is lazy");
  disclosure.open = true;
  disclosure.events.get("toggle")();
  const members = warm.querySelector(".github-pull-stack-members");
  assert.deepEqual(
    [...members.descendants()].filter((item) => item.tag === "a").map((item) => item.textContent),
    ["#6", "#7", "#8"],
  );
  const anchors = [...warm.descendants()].filter((element) => element.tag === "a");
  const previous = anchors.find((element) => element.textContent === "Previous PR");
  const following = anchors.find((element) => element.textContent === "Next PR");
  assert.equal(previous.attributes.get("href"), "/pull/6/files");
  assert.equal(following.attributes.get("href"), "/pull/8/files");
  following.events.get("click")({ preventDefault() {} });
  assert.deepEqual(opened.at(-1), {
    number: 8,
    tab: "files",
    reader: { fetchAfterMs: 0, initial: null },
  });
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
  assert.equal(opened.length, 1, "disposed stack links cannot navigate");
  // Optional ownership must repaint even when all visible PR data is byte-identical.
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
