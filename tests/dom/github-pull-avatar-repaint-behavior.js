// Each avatar's loading policy, by where the page places it (docs/design-system.md,
// "A Repaint Keeps Its Images").
//
// The production pull page mounts on the recorded record of pull request 7, its author
// and commenters given avatars, and goes through what repaints its header and its
// conversation: each tab and back, and a poll that finds a refresh of the same record
// running. Every image the page creates is recorded as it is created.
//
// The header's avatar is built again on each repaint, and in WebKit a new lazy image waits
// for layout and asks the network again, so the header's is eager. The conversation keeps
// its sections, avatars and all, across tabs and polls, so its avatars stay lazy, and one
// far down a long conversation is not asked for until the reader nears it. This is a check
// of attributes and of which nodes a repaint keeps or builds, not of paint, which is the
// engine's: every avatar created has its placement's loading, decodes asynchronously,
// keeps its 18 px slot, and hides itself rather than its slot when it fails to load.
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

/** Each placement's loading. */
const POLICY = { header: "eager", conversation: "lazy" };

const EXPECTED = {
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
      whenIdle: require("./sdk-idle-fixture.js").whenIdle,
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
  /** Where an avatar sits: the header or the conversation under it. */
  const placement = (image) => {
    for (let node = image.parentNode; node; node = node.parentNode) {
      if (node.classes?.has("github-pull-header")) {
        return "header";
      }
      if (node.classes?.has("github-pull-body")) {
        return "conversation";
      }
    }
    return "unplaced";
  };
  let previous = null;
  let seen = 0;
  /** @param {string} name */
  const step = (name) => {
    const header = headerAvatar();
    assert.ok(header, `${name}: the header shows the author's avatar`);
    assert.ok(header.parentNode.classes.has("github-pull-identity"), `${name}: in its identity`);
    const created = { header: 0, conversation: 0 };
    for (const image of images.slice(seen)) {
      const where = placement(image);
      assert.ok(where in POLICY, `${name}: every avatar created is shown in a placement`);
      assert.equal(image.getAttribute("loading"), POLICY[where], `${name}: ${where} loading`);
      assert.deepEqual(avatarFacts(image), EXPECTED, `${name}: ${where} avatar`);
      created[where] += 1;
    }
    seen = images.length;
    steps.push({
      step: name,
      header: previous === null ? "first" : header === previous ? "kept" : "new",
      created,
      shown: container.querySelectorAll(".github-pull-avatar").length,
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
    loading: Object.fromEntries(
      Object.keys(POLICY).map((where) => [
        where,
        [
          ...new Set(
            images
              .filter((image) => placement(image) === where)
              .map((image) => image.getAttribute("loading")),
          ),
        ],
      ]),
    ),
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
