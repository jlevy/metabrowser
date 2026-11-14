// Each avatar's loading policy, by where the page places it (docs/design-system.md,
// "A Repaint Keeps Its Images"), and which of the header's nodes each repaint keeps.
//
// The production pull page mounts on the recorded record of pull request 7, its author
// and commenters given avatars, and goes through what repaints its header and its
// conversation: each tab and back, a poll that finds a refresh of the same record running,
// and the next, which changes only the status line's age. Then polls whose record changes
// one input of the header each: its labels, its head branch, its author's avatar, and its
// state, merged by another actor. Every image the page creates is recorded as it is created.
//
// The header keeps a part while what it shows is unchanged and builds only a part whose
// inputs changed, so a repaint does not replace the node under a reader's pointer or
// focus. Each step names the parts it found new and counts every header element it had
// not seen in the step before; a repaint that changes nothing builds none. The header's
// avatar is eager: it is above the fold, and it is a new image whenever its actor or
// avatar changes. The conversation keeps its sections, avatars and all, across tabs and
// polls, so its avatars stay lazy, and one far down a long conversation is not asked for
// until the reader nears it. This is a check of attributes and of which nodes a repaint
// keeps or builds, not of paint, which is the engine's: every avatar created has its
// placement's loading, decodes asynchronously, keeps its 18 px slot, and hides itself
// rather than its slot when it fails to load.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");

const AVATAR = "https://avatars.githubusercontent.com/u/1242887?s=40";
const OTHER_AVATAR = "https://avatars.githubusercontent.com/u/9919?s=40";

/** An element whose `className` is its class attribute, as the SDK's chips set it. */
class Node extends Element {
  get className() {
    return this.getAttribute("class") ?? "";
  }
  set className(value) {
    this.setAttribute("class", value);
  }
}

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

/** The header's parts, each by the class that names it. */
const PARTS = {
  title: "github-pull-title",
  "state icon": "github-pull-state-icon",
  badge: "github-pull-state",
  "badge sizers": "github-pull-badge-sizer",
  identity: "github-pull-identity",
  action: "github-pull-action",
  branches: "merge-refs",
  "copy buttons": "git-ref-copy",
  "opened row": "github-pull-quiet",
  "GitHub link": "github-pull-external-action",
  labels: "github-pull-label",
  Refresh: "github-pull-refresh",
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
      const node = new Node(tag);
      node.style = {};
      if (tag === "img") {
        images.push(node);
      }
      return node;
    },
    importNode: () => new Node("svg"),
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
      return { body: { firstElementChild: new Node("svg") } };
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
  const container = new Node("main");
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

  const header = () => container.querySelector(".github-pull-header");
  const headerAvatar = () => header()?.querySelector(".github-pull-avatar") ?? null;
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
  /** The header's elements as the step before left them. @type {Set<Element> | null} */
  let before = null;
  let seen = 0;
  /** @param {string} name @param {string} [expected] the avatar's src */
  const step = (name, expected = AVATAR) => {
    const avatar = headerAvatar();
    assert.ok(avatar, `${name}: the header shows the actor's avatar`);
    assert.ok(avatar.parentNode.classes.has("github-pull-identity"), `${name}: in its identity`);
    const created = { header: 0, conversation: 0 };
    for (const image of images.slice(seen)) {
      const where = placement(image);
      assert.ok(where in POLICY, `${name}: every avatar created is shown in a placement`);
      assert.equal(image.getAttribute("loading"), POLICY[where], `${name}: ${where} loading`);
      const facts = avatarFacts(image);
      assert.deepEqual(
        facts,
        { ...EXPECTED, src: facts.src === AVATAR ? AVATAR : expected },
        `${name}: ${where} avatar`,
      );
      created[where] += 1;
    }
    seen = images.length;
    const now = new Set(header().descendants());
    // A part is new where any node of it was not in the header the step before.
    const rebuilt =
      before === null
        ? "first"
        : Object.entries(PARTS)
            .filter(([, name]) =>
              header()
                .querySelectorAll(`.${name}`)
                .some((node) => !before.has(node)),
            )
            .map(([part]) => part);
    steps.push({
      step: name,
      header: previous === null ? "first" : avatar === previous ? "kept" : "new",
      rebuilt,
      built: before === null ? now.size : [...now].filter((node) => !before.has(node)).length,
      created,
      shown: container.querySelectorAll(".github-pull-avatar").length,
    });
    previous = avatar;
    before = now;
  };
  /** Let the page's timers come due, its poll among them, which reads *next*. */
  const poll = async (next) => {
    answer = next;
    const asked = pulls;
    const due = [...timers.values()];
    timers.clear();
    for (const timer of due) {
      timer.callback();
    }
    await settle();
    assert.equal(pulls, asked + 1, "the poll asked for the pull request");
  };
  /** The record shown, with *change* made to its pull request. */
  const changed = (change) => {
    const next = structuredClone(answer);
    change(next.record.pull);
    return next;
  };
  step("Conversation");
  for (const tab of ["files", "checks", ""]) {
    window.location.pathname = `/pull/7${tab ? `/${tab}` : ""}`;
    handle.setTab(tab);
    await settle();
    step({ files: "Changes", checks: "Checks", "": "Conversation again" }[tab]);
  }
  // A poll finds a refresh of the same record running, and the next finds the repository's
  // list has checked it since: the header repaints for each, its status line's age changing
  // in the second, and the record is as it was.
  await poll({ ...body, refreshing: true });
  step("a poll finds a refresh running");
  await poll({
    ...body,
    refreshing: true,
    verified_by: "catalog",
    verified_at: "2026-09-17T12:01:00Z",
  });
  step("the next poll finds it checked");
  // Each of these changes one of the header's inputs; only its part is built again.
  await poll(
    changed((pull) => {
      pull.labels = [...pull.labels, "bug"];
    }),
  );
  step("a label is added");
  await poll(
    changed((pull) => {
      pull.head = { ...pull.head, ref: "count-to-three" };
    }),
  );
  step("the head branch is renamed");
  await poll(
    changed((pull) => {
      pull.author_avatar_url = OTHER_AVATAR;
    }),
  );
  step("the author's avatar changes", OTHER_AVATAR);
  await poll(
    changed((pull) => {
      Object.assign(pull, {
        state: "closed",
        merged: true,
        merged_by: "octo",
        merged_by_avatar_url: OTHER_AVATAR,
        merged_at: "2026-09-17T12:20:00Z",
        closed_at: "2026-09-17T12:20:00Z",
      });
    }),
  );
  step("another actor merges it", OTHER_AVATAR);

  // A broken image keeps its slot: it hides, and its box and the name stay.
  const broken = headerAvatar();
  broken.events.get("error")();
  assert.equal(broken.style.visibility, "hidden");
  assert.equal(broken.getAttribute("width"), "18");
  assert.equal(broken.parentNode.textContent, "octo");
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
