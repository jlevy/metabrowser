// Guided Review on the production stack page (`mountStackPage` in stack-page.js), mounted with
// a stub SDK on the stack route's recorded answers (tests/fixtures/github-stack-responses.json):
// the front page mounts the stack's guide and reads its first step at the comparison it draws;
// a step's file opens in the stack's Changes and another pull request's file in that pull
// request's; a file the rendered route renders is drawn whole only at the comparison drawn; a
// note's links resolve against the member that carries the guide; a new revision of that
// member is read again while the drawn comparison is current, and a new comparison is offered,
// not swapped in, until the reader takes it; and leaving the tab disposes the view and aborts
// its read. The navigation itself is github-guided-review-session.js's, and the stack's own
// state machine github-stack-page-session.js's; this is the page's glue between them. Paint is
// Chrome's.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");
const { Element, root, settle } = require("./github-pull-page-mount-behavior.js");

const recorded = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/github-stack-responses.json"), "utf8"),
);
const GUIDE_ROUTE = "/api/plugin/github/guided-review";
const STACK_ROUTE = "/api/plugin/github/stack";
/** A record revision, 64 hexadecimal characters. */
const revision = (digit) => String(digit).repeat(64);

// The page module imports pull-page.js, which reads the shell's route and Git path codecs at
// import, as in the shell.
const routeContext = { atob, btoa, TextDecoder, TextEncoder, Uint8Array };
routeContext.window = routeContext;
for (const name of ["navigation.js", "git-path.js"]) {
  const file = path.join(root, "src/metabrowser/static", name);
  vm.runInNewContext(fs.readFileSync(file, "utf8"), routeContext, { filename: file });
}

const timers = new Map();
/** The base each note's HTML was sanitized against. */
const bases = [];
/** The address of each link the page marked as an outside link. */
const decorated = [];
globalThis.Node = Element;
globalThis.HTMLElement = Element;
globalThis.document = {
  visibilityState: "visible",
  addEventListener() {},
  removeEventListener() {},
  createElement: (tag) => new Element(tag),
  importNode: () => new Element("svg"),
};
globalThis.window = {
  MetabrowserGitPath: routeContext.MetabrowserGitPath,
  MetabrowserNavigationRoute: routeContext.MetabrowserNavigationRoute,
  location: { pathname: "/stack/70" },
  setTimeout(callback, delay) {
    const id = Symbol();
    timers.set(id, { callback, delay });
    return id;
  },
  clearTimeout: (id) => timers.delete(id),
  // The allowlist's stand-in: a note comes back as one link, so a test reads the base it
  // was resolved against and whether the page marked it. The rebuild itself is the
  // allowlist's, pinned by tests/dom/inert-html-session.js.
  MetabrowserInertHtml: {
    sanitizeHtml(_html, base) {
      bases.push(base);
      const link = new Element("a");
      link.setAttribute("href", "https://example.com/elsewhere");
      link.textContent = "elsewhere";
      return [link];
    },
    kpressProse(nodes) {
      const prose = new Element("div");
      prose.className = "kpress-prose";
      prose.append(...nodes);
      return prose;
    },
  },
};
globalThis.DOMParser = class {
  parseFromString() {
    return { body: { firstElementChild: null } };
  }
};

/** The stack route's answers in order, each with its validator. */
let stackAnswer = null;
/** Each read of the guide: what it asked, its signal, and whether it was answered. */
const reads = [];
const response = (body, status = 200, etag = null) => ({
  ok: status >= 200 && status < 300,
  status,
  headers: { get: (name) => (name === "etag" ? etag : null) },
  json: async () => body,
});
globalThis.fetch = async (route, init = {}) => {
  if (route.startsWith(`${STACK_ROUTE}?`)) {
    return response(stackAnswer, 200, `"${JSON.stringify(stackAnswer).length}"`);
  }
  if (route.startsWith(`${GUIDE_ROUTE}?`)) {
    const asked = new URL(route, "http://localhost").searchParams;
    return new Promise((resolve, reject) => {
      const read = { asked, signal: init.signal, answered: false };
      read.answer = (body) => {
        read.answered = true;
        resolve(response(body));
      };
      init.signal?.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
      reads.push(read);
    });
  }
  return response({}, 404);
};

/** The comparison a stack answer names, and one the stack moved to. */
const drawnFirst = recorded.current.comparison;
const movedTo = {
  ...drawnFirst,
  right: "<moved_head>",
  key: "f".repeat(32),
  route: drawnFirst.route.replace(drawnFirst.key, "f".repeat(32)),
};

/** The stack's answer: 70 current, its guide carried by 10 at *carried*, drawing *comparison*. */
function stack(carried, comparison = drawnFirst) {
  return {
    ...structuredClone(recorded.current),
    guide: { number: 10, revision: carried },
    comparison,
    // No probe: this session moves the stack itself.
    probe: null,
  };
}

/** A reference as the route answers it, every field present. */
const cited = (fields) => ({
  kind: "file",
  path: null,
  side: null,
  start_line: null,
  end_line: null,
  pull: null,
  commit: null,
  state: "ready",
  rendered: null,
  href: null,
  hunks: [],
  truncated: false,
  comparison: null,
  target: null,
  ...fields,
});
const HUNK = {
  old_start: 1,
  old_count: 1,
  new_start: 1,
  new_count: 2,
  heading: null,
  lines: [
    { op: "context", text: "one" },
    { op: "add", text: "two" },
  ],
};

/** Step *step* of 10's two-step guide, read at *pins*, for record revision *carried*: a file
 * of the stack drawn as a patch, one the rendered route renders, and a file of 9. 8, below
 * the top, carries the guide's page here, so its notes' links are made absolute there. */
function step(carried, at, pins) {
  return {
    stack: 70,
    carrier: 10,
    carrier_url: "https://github.com/octo/demo/pull/8",
    record_revision: carried,
    state: "ready",
    comparison: pins,
    step_count: 2,
    titles: ["The layers", "The draft"],
    outline: [
      { kind: "step", step: 1, title: "The layers" },
      { kind: "step", step: 2, title: "The draft" },
    ],
    step: at,
    group: null,
    title: at === 1 ? "The layers" : "The draft",
    note: "Read [elsewhere](https://example.com/elsewhere).",
    note_html: '<p><a href="https://example.com/elsewhere">elsewhere</a></p>',
    note_refusal: null,
    group_note_html: null,
    group_note_refusal: null,
    references: [
      cited({ path: "src/app.txt", href: "/stack/70/changes/src/app.txt", hunks: [HUNK] }),
      cited({
        path: "docs/draft.md",
        rendered: "markdown",
        href: "/stack/70/changes/docs/draft.md",
      }),
      cited({
        kind: "pull_file",
        pull: 9,
        path: "src/other.txt",
        href: "/pull/9/files/src/other.txt",
        hunks: [HUNK],
        comparison: {
          merge_base: "9".repeat(40),
          head: "a".repeat(40),
          route: "/api/plugin/github/pull-comparison?number=9",
          image_route: "/api/plugin/github/pull-image?number=9",
          rendered_route: "/api/plugin/github/pull-rendered-diff?number=9",
        },
      }),
    ],
    assets: {},
  };
}
const pinsOf = (comparison) => ({ merge_base: comparison.left, head: comparison.right });

async function run() {
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/stack-page.js")).href
  );
  /** The routes the page asked the shell to open. */
  const opened = [];
  /** Each document the diff plugin was asked to draw whole, by the comparison's head. */
  const documents = [];
  /** Each patch the diff plugin drew, and whether its view was disposed. */
  const patches = [];
  const diff = {
    mountFilePatch(_body, change, patch) {
      const drawn = { path: change.new.path, lines: patch.hunks[0].lines.length, disposed: false };
      patches.push(drawn);
      return {
        dispose() {
          drawn.disposed = true;
        },
      };
    },
    mountRenderedFile(_body, comparison, file) {
      const drawn = { path: file, right: comparison.right, disposed: false };
      documents.push(drawn);
      return {
        settled: Promise.resolve(true),
        dispose() {
          drawn.disposed = true;
        },
      };
    },
  };
  /** Files' view, which the reader leaves the guide for. */
  const files = { mounted: 0 };
  const filesView = {
    prefetch: async () => ({}),
    summary: async () => {
      files.mounted += 1;
      return { dispose() {} };
    },
    render: async () => ({ dispose() {} }),
  };
  const mb = {
    titleNodes: (title) => [title],
    formatAge: () => ({ label: "now", className: "age" }),
    formatTimestamp: () => "now",
    shortCommit: (sha) => sha.slice(0, 7),
    ensureAsset: async () => {},
    loadKpressAssets: async () => {},
    ensureKindAssets: async () => {},
    decorateExternalLink(anchor) {
      decorated.push(anchor.getAttribute("href"));
      return anchor;
    },
    plugins: {
      async load(name) {
        assert.equal(name, "diff", "the guide loads only the diff plugin");
        return diff;
      },
    },
    getRegisteredView: () => filesView,
  };
  async function poll() {
    const due = [...timers];
    timers.clear();
    for (const [, timer] of due) {
      timer.callback();
    }
    await settle();
  }
  const asks = (read) =>
    ["stack", "step", "left", "right", "key"].map((name) => read.asked.get(name)).join(" ");
  const press = (container, label) =>
    [...container.descendants()]
      .find((node) => node.tag === "button" && node.getAttribute("aria-label") === label)
      .events.get("click")();
  const plain = { button: 0, preventDefault() {} };
  const report = {};

  // The front page of 70, whose guide 10 carries, mounts the guide on its first step and
  // reads it at the comparison the page draws.
  stackAnswer = stack(revision(1));
  const container = new Element("main");
  const handle = page.mountStackPage(
    container,
    {
      number: 70,
      tab: "",
      open(route) {
        opened.push(route);
        return Promise.resolve();
      },
    },
    mb,
  );
  await settle();
  const active = () =>
    container
      .querySelectorAll(".tab-btn")
      .filter((tab) => tab.classes.has("active"))
      .map((tab) => tab.textContent)
      .join(",");
  assert.equal(active(), "Guided Review");
  assert.equal(reads.length, 1);
  report.front = { tab: active(), asks: asks(reads[0]) };
  assert.equal(
    asks(reads[0]),
    `70 1 ${drawnFirst.left} ${drawnFirst.right} ${drawnFirst.key}`,
    "the guide is read at the comparison drawn",
  );

  // The step draws its files: a patch, a document whole from the comparison drawn, and 9's
  // file from 9's own comparison. Its note is resolved against 8's page, the carrier's, and
  // its outside link is marked.
  reads[0].answer(step(revision(1), 1, pinsOf(drawnFirst)));
  await settle();
  assert.deepEqual(
    documents.map(({ path: file, right }) => `${file}@${right}`),
    [`docs/draft.md@${drawnFirst.right}`],
  );
  assert.deepEqual(bases, ["https://github.com/octo/demo/pull/8"]);
  assert.deepEqual(decorated, ["https://example.com/elsewhere"]);
  // Each file's Open full diff opens it where it is a change: the stack's Changes, or 9's.
  for (const full of container.querySelectorAll(".diff-file-view")) {
    full.events.get("click")(plain);
  }
  assert.deepEqual(opened, [
    { number: 70, tab: "changes", file: "src/app.txt", stack: true },
    { number: 9, tab: "files", file: "src/other.txt" },
  ]);
  report.step = {
    documents: documents.map(({ path: file, right }) => `${file}@${right}`),
    patches: patches.map(({ path: file }) => file),
    note_base: bases[0],
    marked: [...decorated],
    opened: opened.map((route) => JSON.stringify(route)),
  };

  // A new revision of 10's record while the drawn comparison is current: the step on screen
  // is read again, at that comparison.
  stackAnswer = stack(revision(2));
  await poll();
  assert.equal(reads.length, 2);
  assert.equal(reads[1].asked.get("step"), "1");
  reads[1].answer(step(revision(2), 1, pinsOf(drawnFirst)));
  await settle();
  report.edited = { reads: reads.length, asks: asks(reads[1]) };

  // Another member moves the stack: the new comparison is offered, not swapped in. The guide
  // keeps the comparison drawn: nothing is read again, and the next step is read there.
  stackAnswer = stack(revision(2), movedTo);
  await poll();
  const offer = container.querySelector(".github-pull-notice")?.textContent ?? "";
  assert.match(offer, /Show the new comparison$/);
  assert.equal(reads.length, 2, "an offered comparison reads nothing");
  press(container, "Next step");
  await settle();
  assert.equal(reads.length, 3);
  assert.equal(asks(reads[2]), `70 2 ${drawnFirst.left} ${drawnFirst.right} ${drawnFirst.key}`);
  // An answer read at another comparison than the one drawn draws no document whole.
  const drawnBefore = documents.length;
  reads[2].answer(step(revision(2), 2, pinsOf(movedTo)));
  await settle();
  assert.equal(documents.length, drawnBefore, "a document is drawn only at the comparison drawn");
  report.moved = {
    offer,
    reads_before_next: 2,
    asks: asks(reads[2]),
    documents_drawn_at_other_pins: documents.length - drawnBefore,
  };

  // The reader takes the new comparison: the guide is mounted again, its old view disposed,
  // and read at the comparison now drawn.
  container.querySelector(".github-pull-stack-page-take").events.get("click")();
  await settle();
  assert.ok(documents.every((drawn) => drawn.disposed) && patches.every((drawn) => drawn.disposed));
  assert.equal(reads.length, 4);
  assert.equal(asks(reads[3]), `70 1 ${movedTo.left} ${movedTo.right} ${movedTo.key}`);
  report.taken = { asks: asks(reads[3]), earlier_views_disposed: true };

  // Leaving the tab while that read is on its way disposes the view and aborts the read, and
  // its late answer draws nothing.
  handle.setTab("files");
  await settle();
  assert.equal(reads[3].signal.aborted, true);
  assert.equal(files.mounted, 1);
  assert.equal(container.querySelector(".github-pull-guided-review"), null);
  report.left = { tab: active(), read_aborted: reads[3].signal.aborted, files_mounted: 1 };
  handle.dispose?.();
  console.log(JSON.stringify(report, null, 2));
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
