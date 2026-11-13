// A repaint never blanks an avatar whose address did not change (docs/design-system.md,
// "A Repaint Keeps Its Images").
//
// The production pull page mounts on the recorded record of pull request 7, its author
// and commenters given avatars, and goes through what repaints its header and its
// conversation: each tab and back, and a poll that finds a refresh of the same record
// running. Every image the page creates is recorded as it is created.
//
// The page builds its actors again when it repaints, so an avatar can be a new image. A
// lazy image waits for layout before it asks for its bytes, and in WebKit it then asked
// the network again, which painted the header's avatar blank for that round trip on every
// tab switch; an eager one is the cached image at once. Paint is the engine's, so this pins
// what decides it: every avatar the page creates is eager, decodes asynchronously, keeps
// its 18 px slot, and hides itself rather than its slot when it fails to load.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");

const AVATAR = "https://avatars.githubusercontent.com/u/1242887?s=40";

/** The recorded record, its pull request's author and every commenter with an avatar. */
function withAvatars(body) {
  const copy = structuredClone(body);
  const record = copy.record;
  record.pull.author_avatar_url = AVATAR;
  for (const item of [...record.issue_comments, ...record.reviews, ...record.review_comments]) {
    item.author_avatar_url = AVATAR;
  }
  return copy;
}

/** What an avatar's attributes decide about when and how it paints. */
function avatarFacts(image) {
  return {
    loading: image.getAttribute("loading"),
    decoding: image.getAttribute("decoding"),
    fetchpriority: image.getAttribute("fetchpriority"),
    width: image.getAttribute("width"),
    height: image.getAttribute("height"),
    alt: image.getAttribute("alt"),
    crossorigin: image.getAttribute("crossorigin"),
    referrerpolicy: image.getAttribute("referrerpolicy"),
    src: image.getAttribute("src"),
  };
}

const EXPECTED = {
  loading: "eager",
  decoding: "async",
  fetchpriority: "low",
  width: "18",
  height: "18",
  alt: "",
  crossorigin: "anonymous",
  referrerpolicy: "no-referrer",
  src: AVATAR,
};

async function run() {
  /** @type {Element[]} */
  const images = [];
  const timers = new Map();
  globalThis.document = {
    visibilityState: "visible",
    addEventListener() {},
    removeEventListener() {},
    createElement: (tag) => {
      const node = new Element(tag);
      node.style = {};
      if (tag === "img") {
        images.push(node);
      }
      return node;
    },
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
    requestAnimationFrame: () => 0,
    cancelAnimationFrame() {},
  };
  globalThis.DOMParser = class {
    parseFromString() {
      return { body: { firstElementChild: new Element("svg") } };
    }
  };
  const body = withAvatars(recorded.current.body);
  let answer = body;
  let pulls = 0;
  globalThis.fetch = async (route) => {
    if (String(route).startsWith("/api/plugin/github/pull?")) {
      pulls += 1;
      return { status: 200, headers: { get: () => null }, json: async () => answer };
    }
    return { status: 304, headers: { get: () => null } };
  };
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  // authorLabel itself, which the Pulls list's rows share, is pinned in
  // github-pull-stack-mount-behavior.js; this is what the page's repaints create with it.
  const container = new Element("main");
  const handle = page.mountPullPage(
    container,
    { number: 7, tab: "", reader: { initial: { etag: null, body }, fetchAfterMs: 60_000 } },
    {
      perf,
      ensureAsset: async () => {},
      ensureKindAssets: async () => {},
      getRegisteredView: () => ({
        render: async (host) => {
          host.textContent = "Mounted comparison";
          return {
            currentFile: () => null,
            onCurrentFile: () => () => {},
            dispose() {},
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

  const headerAvatar = () =>
    container.querySelector(".github-pull-header")?.querySelector(".github-pull-avatar") ?? null;
  const steps = [];
  let previous = null;
  let seen = 0;
  /** @param {string} name */
  const step = (name) => {
    const header = headerAvatar();
    assert.ok(header, `${name}: the header shows the author's avatar`);
    assert.ok(header.parentNode.classes.has("github-pull-identity"), `${name}: in its identity`);
    const created = images.slice(seen);
    seen = images.length;
    for (const image of created) {
      assert.deepEqual(avatarFacts(image), EXPECTED, `${name}: every avatar created is eager`);
    }
    steps.push({
      step: name,
      header: previous === null ? "first" : header === previous ? "kept" : "new",
      avatarsCreated: created.length,
      avatarsShown: container.querySelectorAll(".github-pull-avatar").length,
    });
    previous = header;
  };
  step("Conversation");
  for (const tab of ["files", "checks", ""]) {
    window.location.pathname = `/pull/7${tab ? `/${tab}` : ""}`;
    handle.setTab(tab);
    await settle();
    step({ files: "Changes", checks: "Checks", "": "Conversation again" }[tab]);
  }
  // The page's timers come due, its poll among them, which finds a refresh of the same
  // record running: the header repaints for it, and its author is as it was.
  answer = { ...body, refreshing: true };
  const asked = pulls;
  const due = [...timers.values()];
  timers.clear();
  for (const timer of due) {
    timer.callback();
  }
  await settle();
  assert.equal(pulls, asked + 1, "the poll asked for the pull request");
  step("a poll finds a refresh running");

  // A broken image keeps its slot: it hides, and its box and the name stay.
  const broken = headerAvatar();
  broken.events.get("error")();
  assert.equal(broken.style.visibility, "hidden");
  assert.equal(broken.getAttribute("width"), "18");
  assert.equal(broken.parentNode.textContent, "forker");
  handle.dispose();
  return {
    steps,
    everyAvatarEager: images.every((image) => image.getAttribute("loading") === "eager"),
  };
}

if (require.main === module) {
  run()
    .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
    .catch((error) => {
      process.stderr.write(`${error.stack}\n`);
      process.exitCode = 1;
    });
}
