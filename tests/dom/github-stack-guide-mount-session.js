// The production stack page (`mountStackPage` in stack-page.js), mounted with a stub SDK on the
// stack route's recorded answers (tests/fixtures/github-stack-responses.json). First its
// header: the rows its first paint draws from the stack the Pulls tab knows, before the stack's
// answer, are the rows the answer settles in, and what it passes the diff view draws the Diff
// summary collapsed and Docs and Changes as a pull request's page does.
// Then Guided Review:
// the front page mounts the stack's guide and reads its first step at the comparison it draws;
// a step's file opens in the stack's Changes and another pull request's file in that pull
// request's; a file the rendered route renders is drawn whole at the comparison drawn; a
// note's links resolve against the member that carries the guide; a new revision of that
// member is read again while the drawn comparison is current, and a new comparison is offered,
// not swapped in, until the reader takes it, whether a member below moved or the carrier
// moved with it and was pinned again, which no step is read as, and the route's own refusal
// of a step at a comparison it has moved past reads the stack at once; and leaving the tab
// disposes the view and aborts its read. Then Docs and Changes that could not load: each says so in a
// pull request's error notice with Retry, whose press disposes what the failed draw left and
// draws again, and a Retry left behind by a tab switch or the page's disposal draws nothing.
// Then two more stacks' headers from first paint to their answers: one whose members the
// Pulls tab knows carry no labels, which has no labels row from first paint, and one the
// Pulls tab does not know, whose members row is held from first paint. Last, the members'
// readiness (mb-3n21): the page reads the server's verdict on its open members when the
// browser is idle, and each member's line ends with its glyph's cell, empty for a merged one,
// though a member's record lags the head the server judged; a Pulls tab beside it shares its
// answer, so neither reads it again; and a member whose record moves is read again once.
// The navigation itself is github-guided-review-session.js's, and the stack's own
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
const STACKS_ROUTE = "/api/plugin/github/stacks";
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
// The clock, fixed five minutes after the members' records were fetched, so a fetch's age is
// said as a reader would see it, as the page's own session says it.
const NOW_MS = Date.parse("2026-09-17T12:05:00Z");
Date.now = () => NOW_MS;
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
/** The answers of the stacks other than 70, by number. */
const otherAnswers = new Map();
/** How many times the page has read the stack route. */
let stackReads = 0;
/** The repository's stacks, as the Pulls tab reads them: 70 of 8 and then 10, titled as the
 * stack route's recorded answer titles them. */
const stacksAnswer = {
  state: "current",
  reason: null,
  source: "https://github.com/octo/demo",
  reader: "gh:octo-reader",
  fetched_at: "2026-09-17T12:05:01Z",
  fresh_for_s: 90,
  refreshing: false,
  last_refresh: null,
  complete: true,
  stacks: [
    {
      number: 70,
      base_ref: recorded.current.base_ref,
      open: true,
      pulls: recorded.current.members.map((member) => member.number),
      titles: recorded.current.members.map((member) => member.title),
      // The stacks route read 10's author with its title and holds none for 8, so 10's
      // member row ends in its author and 8's in its number.
      authors: recorded.current.members.map((member) =>
        member.number === 10 ? "maintainer" : null,
      ),
      avatars: recorded.current.members.map(() => null),
      // And 10's labels, and none of 8's, so the labels row is held until the answer.
      labels: recorded.current.members.map((member) => (member.number === 10 ? ["bugfix"] : null)),
    },
    // 75, the same members, which the stacks route read with no labels: no labels row from
    // first paint. 76, which it does not know, is not here.
    {
      number: 75,
      base_ref: recorded.current.base_ref,
      open: true,
      pulls: recorded.current.members.map((member) => member.number),
      titles: recorded.current.members.map((member) => member.title),
      authors: recorded.current.members.map(() => "maintainer"),
      avatars: recorded.current.members.map(() => null),
      labels: recorded.current.members.map(() => []),
    },
  ],
};
/** Each read of the guide: what it asked, its signal, and whether it was answered. */
const reads = [];
const response = (body, status = 200, etag = null) => ({
  ok: status >= 200 && status < 300,
  status,
  headers: { get: (name) => (name === "etag" ? etag : null) },
  json: async () => body,
  // The guide reads its answer as text, whose length it keeps (guide-reads.js).
  text: async () => JSON.stringify(body),
});
globalThis.fetch = async (route, init = {}) => {
  if (route.startsWith(`${STACK_ROUTE}?`)) {
    stackReads += 1;
    const number = Number(new URL(route, "http://localhost").searchParams.get("number"));
    const answer = otherAnswers.get(number) ?? stackAnswer;
    return response(answer, 200, `"${number}-${JSON.stringify(answer).length}"`);
  }
  if (route === STACKS_ROUTE && (init.method ?? "GET") === "GET") {
    return response(stacksAnswer, 200, '"stacks-1"');
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

/** The comparison a stack answer names; the one it moves to when its bottom member's record
 * catches up, whose key changes while its two commits and its files stay; the one it moves to
 * when its bottom member moves, whose base and key change while the top's head and record
 * stay; and the one it moves to when the top member, which carries the guide, moves too. */
const drawnFirst = recorded.current.comparison;
const caughtUp = {
  ...drawnFirst,
  key: "d".repeat(32),
  route: drawnFirst.route.replace(drawnFirst.key, "d".repeat(32)),
};
const belowMoved = {
  ...drawnFirst,
  left: "<moved_base>",
  key: "e".repeat(32),
  route: drawnFirst.route.replace(drawnFirst.key, "e".repeat(32)),
};
const movedTo = {
  ...belowMoved,
  right: "<moved_head>",
  key: "f".repeat(32),
  route: drawnFirst.route.replace(drawnFirst.key, "f".repeat(32)),
};

/** The stack's answer: 70 current, its guide carried by 10 at *carried*, drawing *comparison*.
 * Its bottom member, 8, has a head the first comparison already shows in `caughtUp`, whose
 * record caught up, and two new commits in the moved comparisons, and 10, the top, one more
 * in `movedTo`, as the route's `moved` says asked `since` the first. */
function stack(carried, comparison = drawnFirst) {
  const answer = structuredClone(recorded.current);
  const moved = [];
  if (comparison === caughtUp) {
    answer.members[0].head = "<caught_up_8_head>";
    moved.push({ number: 8, commits: 0 });
  } else if (comparison !== drawnFirst) {
    answer.members[0].head = "<moved_8_head>";
    moved.push({ number: 8, commits: 2 });
  }
  if (comparison === movedTo) {
    answer.members[1].head = "<moved_head>";
    moved.push({ number: 10, commits: 1 });
  }
  return {
    ...answer,
    guide: { number: 10, revision: carried },
    comparison,
    // No probe: this session moves the stack itself.
    probe: null,
    moved: moved.length === 0 ? null : { since: drawnFirst.key, members: moved },
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

const TITLES = ["The layers", "The draft", "The plan"];
/** Step *step* of 10's three-step guide, read at *pins*, for record revision *carried*: a file
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
    step_count: TITLES.length,
    titles: TITLES,
    outline: TITLES.map((title, index) => ({ kind: "step", step: index + 1, title })),
    step: at,
    group: null,
    title: TITLES[at - 1],
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
  const { fileDisclosure } = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/diff/diff-view.js")).href
  );
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
    guidePatchDrawer() {
      // With the diff view's own bar and chevron, which fold the cards the guide draws.
      return Object.assign((body, change, patch) => this.mountFilePatch(body, change, patch), {
        disclose: (section, folded, changed) => fileDisclosure(section, folded, changed),
      });
    },
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
  /** The diff view: what the page passed it for the header's Diff summary and for each
   * diff it drew, and how many of each it drew. */
  const files = { summaries: 0, rendered: 0 };
  /** How the diff view's next draws fail, in order: `throw` fails the draw itself, and
   * `late` draws and then fails its first screen, after the page has adopted the view. */
  const failures = [];
  /** Each diff view drawn, and whether the page disposed it. */
  const views = [];
  /** @type {Array<Record<string, unknown>>} */
  const drawings = [];
  const shape = (ctx) =>
    Object.fromEntries(
      Object.entries(ctx)
        .filter(([name]) => !["comparison", "comparisonSignal", "raw"].includes(name))
        .map(([name, value]) => [name, typeof value === "function" ? "function" : value]),
    );
  const filesView = {
    prefetch: async () => ({ manifest: { totals: { files: 1 } } }),
    summary: async (_slot, ctx) => {
      files.summaries += 1;
      drawings.push({ summary: shape(ctx) });
      return { dispose() {} };
    },
    render: async (_host, ctx) => {
      files.rendered += 1;
      drawings.push({ render: shape(ctx) });
      const failure = failures.shift();
      if (failure === "throw") {
        throw new Error("the stub diff could not draw");
      }
      const view = {
        disposed: false,
        dispose() {
          view.disposed = true;
        },
      };
      if (failure === "late") {
        view.firstScreen = () => Promise.reject(new Error("the stub diff's first screen failed"));
      }
      views.push(view);
      return view;
    },
  };
  const mb = {
    titleNodes: (title) => [title],
    // The shell's actor identity, as its name alone.
    actorIdentity(name, { nameClass = "" } = {}) {
      const identity = new Element("span");
      identity.className = nameClass;
      identity.textContent = name;
      return identity;
    },
    ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
      label: "now",
      className: "age",
    })),
    formatTimestamp: () => "now",
    formatInteger: (value) => String(value),
    // A count summary's parts as its text: each number, word, and separator.
    countPartsNodes: (parts) =>
      parts.map((part) =>
        typeof part === "string" ? part : (part.number ?? part.separator ?? ""),
      ),
    shortCommit: (sha) => sha.slice(0, 7),
    ensureAsset: async () => {},
    loadKpressAssets: async () => {},
    ensureKindAssets: async () => {},
    // The page is never idle here, so the guide reads each step when the reader moves to it;
    // its reads ahead are pinned in github-guided-review-session.js.
    whenIdle: () => () => {},
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
    changeSizeLine: ({ files: count }) => ({
      text: `${count} file${count === 1 ? "" : "s"} changed`,
    }),
    changeSizeLineNodes: (line) => [line.text],
    mergeRefs(source, target) {
      const merge = new Element("span");
      merge.textContent = `${source.name} → ${target.name}`;
      return merge;
    },
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

  // The Pulls tab has read the repository's stacks, as it has when a stack button opens the
  // page.
  const stacks = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-stacks.js")).href
  );
  const pullsTab = stacks.watchStacks(() => {});
  await settle();

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
  // The header's rows as the reader sees them: each row, and what it holds.
  const header = container.querySelector(".github-pull-header");
  const rowName = (node) =>
    node.tag === "h1"
      ? "title"
      : node.classes.has("view-header-end")
        ? "corner"
        : node.classes.has("github-pull-stack-members-row")
          ? "members"
          : node.classes.has("github-pull-opened")
            ? "opened"
            : node.classes.has("github-pull-meta")
              ? "meta"
              : node.classes.has("github-pull-branches")
                ? "merge"
                : node.classes.has("github-pull-labels")
                  ? "labels"
                  : node.classes.has("github-pull-status")
                    ? "status"
                    : node.classes.has("github-pull-size")
                      ? "size"
                      : node.classes.has("github-pull-summary")
                        ? "summary"
                        : node.tag;
  const holds = (node) =>
    node.querySelector(".tally-pending") !== null ? "(pending)" : node.textContent;
  const rowsOf = (shown) =>
    shown.children
      .filter((node) => !node.hidden)
      .map((node) => {
        const name = rowName(node);
        if (name === "members") {
          const toggle = node.querySelector(".github-pull-stack-members-toggle");
          return {
            members: {
              toggle: toggle.textContent,
              held: toggle.classes.has("github-pull-stack-members-held"),
              expanded: toggle.getAttribute("aria-expanded"),
              rows: node
                .querySelectorAll(".github-pull-stack-member")
                .map((row) => row.textContent.replace(/\s+/g, " ").trim()),
            },
          };
        }
        if (name === "labels") {
          return {
            labels: node.querySelectorAll(".github-pull-label").map((chip) => chip.textContent),
          };
        }
        return name === "title" || name === "corner" ? name : { [name]: holds(node) };
      });
  const rows = () => rowsOf(header);
  const firstPaint = rows();
  const cold = header.classes.has("github-pull-cold");
  await settle();
  const settled = rows();
  const names = (list) => list.map((row) => (typeof row === "string" ? row : Object.keys(row)[0]));
  assert.deepEqual(names(firstPaint), names(settled), "the answer lands in the rows drawn");
  // Until the stack's answer the page is held out of sight for the quiet period, as a pull
  // request's page is until its record, and the answer shows it.
  assert.equal(cold, true, "the page is held until the stack's answer");
  assert.equal(header.classes.has("github-pull-cold"), false, "the answer shows the page");
  // The members' toggle, closed at first as the Diff summary is, opens and closes the card it
  // controls, and stays as the reader left it while the stack's answers are read again.
  const membersToggle = header.querySelector(".github-pull-stack-members-toggle");
  const membersBody = header.querySelector(".github-pull-stack-members-body");
  const disclosure = () => ({
    expanded: membersToggle.getAttribute("aria-expanded"),
    collapsed: membersBody.classes.has("github-pull-stack-members-body-collapsed"),
    controls: membersToggle.getAttribute("aria-controls") === membersBody.getAttribute("id"),
  });
  const toggled = { first: disclosure() };
  membersToggle.events.get("click")();
  toggled.opened = disclosure();
  await poll();
  toggled.after_a_poll = disclosure();
  membersToggle.events.get("click")();
  toggled.closed = disclosure();
  assert.deepEqual(toggled.first, { expanded: "false", collapsed: true, controls: true });
  assert.deepEqual(toggled.opened, { expanded: "true", collapsed: false, controls: true });
  assert.deepEqual(toggled.after_a_poll, toggled.opened, "an answer keeps the reader's choice");
  assert.deepEqual(toggled.closed, toggled.first);
  const summaryDrawn = drawings.find((drawing) => drawing.summary)?.summary;
  assert.deepEqual(Object.keys(summaryDrawn).sort(), ["openFile"], "where a file opens alone");
  report.header = {
    first_paint: firstPaint,
    settled,
    members_toggle: toggled,
    summary_drawing: summaryDrawn,
  };
  pullsTab.dispose();
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
  // Its step list has no overview, and no step is in a group, so each row starts on a group
  // heading's edge with its number, in a column one digit wide (mb-420k).
  const list = container.querySelector(".github-pull-guide-steps");
  const isElement = (node) => typeof node !== "string";
  report.list = {
    rows: list.children.filter(isElement).map((item) =>
      item.children
        .find(isElement)
        .children.filter(isElement)
        .map((part) => `${[...part.classes].join(".")}: ${part.textContent}`)
        .join(", "),
    ),
    style: list.getAttribute("style"),
  };
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

  // 8's record catches up, so the stack's key changes while its two commits and its files
  // stay, and 10's record has a new revision. Nothing the reader sees changes: the
  // comparison drawn stays, with no notice and the guide's view kept, and the step on screen
  // is read again, at that comparison.
  const view = container.querySelector(".github-pull-guided-review");
  stackAnswer = stack(revision(2), caughtUp);
  await poll();
  assert.equal(container.querySelector(".github-pull-stack-take"), null, "nothing is offered");
  assert.equal(container.querySelector(".github-pull-guided-review"), view, "nor drawn again");
  assert.equal(reads.length, 2);
  assert.equal(reads[1].asked.get("step"), "1");
  reads[1].answer(step(revision(2), 1, pinsOf(drawnFirst)));
  await settle();
  report.edited = { reads: reads.length, asks: asks(reads[1]) };

  // The reader has pressed on the page, as they did to open each file above, so from here a
  // comparison that looks different is offered, not drawn under them.
  container.events.get("pointerdown")();
  // The bottom member moves the stack: its base and key change, while 10, the top member that
  // carries the guide, keeps its head and its record. The new comparison is offered, not
  // swapped in, its notice naming 8, whose new commits came after the head its record
  // caught up to. The guide keeps the comparison drawn: nothing is read again, and the next
  // step is read there and draws its document there. The notice's words are the golden's.
  stackAnswer = stack(revision(2), belowMoved);
  await poll();
  const offer = container.querySelector(".github-pull-status")?.textContent ?? "";
  assert.ok(offer.includes("#8"), "the notice names 8");
  assert.notEqual(container.querySelector(".github-pull-stack-take"), null, "and offers it");
  assert.equal(reads.length, 2, "an offered comparison reads nothing");
  press(container, "Next step");
  await settle();
  assert.equal(reads.length, 3);
  assert.equal(asks(reads[2]), `70 2 ${drawnFirst.left} ${drawnFirst.right} ${drawnFirst.key}`);
  reads[2].answer(step(revision(2), 2, pinsOf(drawnFirst)));
  await settle();
  assert.equal(
    documents.at(-1).right,
    drawnFirst.right,
    "a document is drawn at the comparison drawn",
  );
  report.below_moved = {
    offer,
    reads_before_next: 2,
    asks: asks(reads[2]),
    document_at: documents.at(-1).right,
  };

  // Then 10 moves too, and its author pins the guide again, so the carrier's revision and the
  // comparison change together (B1 of review B on #838). Nothing is read; a step not read
  // yet, read at the comparison drawn, names the new revision, or the route answers
  // `stack_moved` for a guide pinned past it: either is that step's refusal in the stack's
  // words, under the steps the guide keeps, and Show the new comparison is how to read it.
  stackAnswer = stack(revision(3), movedTo);
  await poll();
  assert.equal(reads.length, 3, "a carrier that moves with the stack reads nothing");
  const guided = () => container.querySelector(".github-pull-guided-review");
  const said = () => guided().querySelector(".github-pull-quiet")?.textContent ?? "";
  const listed = () => guided().querySelectorAll(".github-pull-guide-steps-item").length;
  const MOVED =
    "This stack has moved since its comparison was drawn. Show the new comparison to read its guide.";
  press(container, "Next step");
  await settle();
  assert.equal(asks(reads[3]), `70 3 ${drawnFirst.left} ${drawnFirst.right} ${drawnFirst.key}`);
  reads[3].answer(step(revision(3), 3, pinsOf(drawnFirst)));
  await settle();
  assert.equal(said(), MOVED);
  assert.equal(listed(), 3, "the guide keeps its steps");
  press(container, "Previous step");
  await settle();
  assert.equal(reads.length, 4, "a step in hand is not read again");
  press(container, "Next step");
  await settle();
  assert.equal(asks(reads[4]), `70 3 ${drawnFirst.left} ${drawnFirst.right} ${drawnFirst.key}`);
  // The route's own `stack_moved` says the comparison drawn may be gone, so the page reads
  // the stack at once, not at its next poll, and keeps its offer.
  const readsBefore = stackReads;
  reads[4].answer({
    stack: 70,
    carrier: 10,
    carrier_url: "https://github.com/octo/demo/pull/8",
    record_revision: revision(3),
    state: "stack_moved",
  });
  await settle();
  assert.equal(said(), MOVED);
  assert.equal(listed(), 3);
  assert.equal(stackReads - readsBefore, 1, "the route's stack_moved reads the stack now");
  assert.notEqual(container.querySelector(".github-pull-stack-take"), null, "and offers it");
  const kept = listed();
  // Back on the tab before taking the new comparison: the guide is not the one read at the
  // comparison drawn, so nothing is read there, and the stack's words say why. The steps
  // went with the view the tab disposed, and the route has only the guide pinned again.
  handle.setTab("changes");
  await settle();
  handle.setTab("guided");
  await settle();
  assert.equal(reads.length, 5, "reopened, the guide reads nothing at the comparison drawn");
  assert.equal(said(), MOVED);
  report.carrier_moved = {
    asks: asks(reads[3]),
    step_refused: MOVED,
    steps_kept: kept,
    route_refused_step: reads[4].asked.get("step"),
    route_refused_reads_stack: stackReads - readsBefore,
    reopened_reads: reads.length - 5,
    reopened_steps: listed(),
  };

  // The reader takes the new comparison: the guide is mounted again, its old view disposed,
  // and read at the comparison now drawn.
  container.querySelector(".github-pull-stack-take").events.get("click")();
  await settle();
  assert.ok(documents.every((drawn) => drawn.disposed) && patches.every((drawn) => drawn.disposed));
  assert.equal(reads.length, 6);
  assert.equal(asks(reads[5]), `70 1 ${movedTo.left} ${movedTo.right} ${movedTo.key}`);
  report.taken = { asks: asks(reads[5]), earlier_views_disposed: true };

  // Leaving the tab while that read is on its way disposes the view; the read goes on for
  // the document's keep of the guide's answers (guide-reads.js), and its late answer draws
  // nothing.
  handle.setTab("changes");
  await settle();
  assert.equal(reads[5].signal.aborted, false);
  assert.equal(container.querySelector(".github-pull-guided-review"), null);
  reads[5].answer(step(revision(3), 1, pinsOf(movedTo)));
  await settle();
  assert.equal(container.querySelector(".github-pull-guided-review"), null);
  const changes = drawings.findLast((drawing) => drawing.render)?.render;
  assert.equal(changes.summary, false, "the header draws the Diff summary, the diff none");
  report.left = {
    tab: active(),
    read_aborted: reads[5].signal.aborted,
    // The header's Diff summary, once for each comparison drawn, and the diffs drawn.
    summaries_drawn: files.summaries,
    diffs_drawn: files.rendered,
    changes_drawing: changes,
  };

  // Docs and Changes that could not load: a pull request's error notice and its Retry
  // (`paintDiff` in stack-page.js, as `mountDiff` in pull-page.js). The page logs each
  // failure; the session keeps the messages out of its transcript.
  const logError = console.error;
  const logged = [];
  console.error = (...args) => logged.push(args.map(String)[0]);
  const body = container.querySelector(".github-pull-body");
  const notice = () => body.querySelector(".github-pull-notice");
  const retryButton = (node) => [...node.descendants()].find((each) => each.tag === "button");
  /** What the body shows: the notice's words and its button, or the diff's host. */
  const shows = () => {
    const shown = notice();
    if (shown === null) {
      return body.querySelector(".metabrowser-diff-host") === null ? "(nothing)" : "the diff";
    }
    return `${shown.getAttribute("data-severity")}: ${shown.textContent}`;
  };
  const failed = {};
  // Docs whose draw fails says so, and Retry draws it again.
  failures.push("throw");
  handle.setTab("docs");
  await settle();
  let renders = files.rendered;
  failed.docs = { notice: shows(), retry: retryButton(notice())?.textContent ?? null };
  assert.equal(failed.docs.notice, "error: Docs could not load. Retry");
  retryButton(notice()).events.get("click")();
  await settle();
  failed.docs.after_retry = { shows: shows(), draws: files.rendered - renders };
  assert.deepEqual(failed.docs.after_retry, { shows: "the diff", draws: 1 });
  // Changes that draws and then fails its first screen says so too, and Retry disposes the
  // view the failed draw left before it draws again.
  failures.push("late");
  handle.setTab("changes");
  await settle();
  const left = views.at(-1);
  renders = files.rendered;
  failed.changes = { notice: shows(), left_view_disposed: left.disposed };
  assert.equal(failed.changes.notice, "error: Changes could not load. Retry");
  retryButton(notice()).events.get("click")();
  await settle();
  failed.changes.after_retry = {
    shows: shows(),
    draws: files.rendered - renders,
    left_view_disposed: left.disposed,
  };
  assert.deepEqual(failed.changes.after_retry, {
    shows: "the diff",
    draws: 1,
    left_view_disposed: true,
  });
  // A Retry left behind by a tab switch draws nothing: the tab now shown keeps its diff.
  failures.push("throw");
  handle.setTab("docs");
  await settle();
  const behind = retryButton(notice());
  handle.setTab("changes");
  await settle();
  renders = files.rendered;
  behind.events.get("click")();
  await settle();
  failed.retry_after_tab_switch = { shows: shows(), draws: files.rendered - renders };
  assert.deepEqual(failed.retry_after_tab_switch, { shows: "the diff", draws: 0 });
  // And one pressed after the page is disposed draws nothing.
  failures.push("throw");
  handle.setTab("docs");
  await settle();
  const disposedRetry = retryButton(notice());
  handle.dispose?.();
  renders = files.rendered;
  disposedRetry.events.get("click")();
  await settle();
  failed.retry_after_dispose = { draws: files.rendered - renders };
  assert.deepEqual(failed.retry_after_dispose, { draws: 0 });
  console.error = logError;
  assert.equal(logged.length, 4, "each failure is logged once");
  failed.logged = logged;
  report.failed = failed;

  // Two more stacks' headers, from first paint to the answer, the Pulls tab having read the
  // repository's stacks again: 75, whose members the Pulls tab knows carry no labels, has no
  // labels row from first paint, and its answer, which says none, moves nothing; and 76,
  // which the Pulls tab does not know, holds its members row from first paint, its toggle out
  // of sight and empty, and its answer fills it.
  const pullsAgain = stacks.watchStacks(() => {});
  await settle();
  otherAnswers.set(75, { ...stack(revision(1)), number: 75, labels: [], guide: null });
  otherAnswers.set(76, { ...stack(revision(1)), number: 76, guide: null });
  const others = {};
  for (const number of [75, 76]) {
    const shown = new Element("main");
    const mounted = page.mountStackPage(
      shown,
      { number, tab: "changes", open: () => Promise.resolve() },
      mb,
    );
    const otherHeader = shown.querySelector(".github-pull-header");
    const first = rowsOf(otherHeader);
    await settle();
    const answered = rowsOf(otherHeader);
    assert.deepEqual(
      names(first),
      names(answered),
      `${number}: the answer lands in the rows drawn`,
    );
    others[number] = { first_paint: first, settled: answered };
    mounted.dispose?.();
  }
  pullsAgain.dispose();
  assert.ok(!names(others[75].first_paint).includes("labels"), "75 has no labels row");
  assert.ok(names(others[76].first_paint).includes("members"), "76 holds its members row");
  report.cold_without_labels = others[75];
  report.unknown_stack = others[76];
  report.note_links = await noteLinks(page, mb);

  // The members' readiness (mb-3n21): the page reads, for the members its card lists, the
  // server's verdict on each, from the statuses the server answered once the scan of every
  // open pull request's status had ended (tests/fixtures/github-pulls-readiness-responses.json),
  // when the browser is idle, and each member's line ends with its glyph's cell. #10, a draft,
  // conflicts; #8 is merged, so it is not asked and its cell stays empty. The stack's heads are
  // its members' records', placeholders here that lag the heads the statuses judged, as a
  // record lags the catalog after a push: a member draws the verdict on the head the server
  // judged all the same, as its Pulls row does.
  const readiness = JSON.parse(
    fs.readFileSync(
      path.join(root, "tests/fixtures/github-pulls-readiness-responses.json"),
      "utf8",
    ),
  ).scanned.body;
  const judged = new Map(
    readiness.rows.map((row) => JSON.parse(row)).map((row) => [row.number, row]),
  );
  const statusReads = [];
  const answered = globalThis.fetch;
  globalThis.fetch = async (route, init = {}) => {
    if (route.startsWith("/api/plugin/github/pull-statuses?")) {
      const numbers = new URL(route, "http://localhost").searchParams.get("numbers").split(",");
      statusReads.push(route);
      return response({
        ...readiness,
        rows: numbers.map((number) => judged.get(Number(number))).filter(Boolean),
      });
    }
    return answered(route, init);
  };
  const idle = [];
  const runIdle = async () => {
    while (idle.length > 0) {
      idle.shift()();
      await settle();
    }
  };
  const idleMb = {
    ...mb,
    whenIdle(callback) {
      idle.push(callback);
      return () => {};
    },
  };
  const members = stack(revision(1)).members;
  assert.ok(
    members.every((member) => member.head !== judged.get(member.number)?.head),
    "each member's record lags the head the statuses judged",
  );
  otherAnswers.set(77, { ...stack(revision(1)), number: 77, guide: null, members });
  const judgedPage = new Element("main");
  const judging = page.mountStackPage(
    judgedPage,
    { number: 77, tab: "changes", open: () => Promise.resolve() },
    idleMb,
  );
  await settle();
  const memberRows = () =>
    judgedPage.querySelectorAll(".github-pull-stack-member").map((row) => {
      const glyph = row.querySelector(".github-pull-readiness-icon");
      return {
        state: row.querySelector(".github-pull-state-icon")?.dataset.state ?? null,
        words: row.querySelector(".github-pull-readiness-said")?.textContent ?? null,
        glyph: glyph === null ? null : `${glyph.dataset.verdict} (${glyph.dataset.tone})`,
        cell_last: row.children.at(-1)?.classes.has("github-pull-stack-member-readiness") ?? false,
      };
    });
  const before = memberRows();
  await runIdle();
  report.members_readiness = {
    before_idle: before,
    asked: [...statusReads],
    after_idle: memberRows(),
  };
  assert.deepEqual(
    statusReads,
    ["/api/plugin/github/pull-statuses?numbers=10"],
    "the page asks for its open member alone, once",
  );
  assert.ok(
    report.members_readiness.after_idle.every((row) => row.cell_last),
    "every member's line ends with its readiness's cell",
  );
  assert.equal(report.members_readiness.after_idle[0].glyph, "conflicts (danger)");

  // A Pulls tab in the same document draws #10 by the catalog's head, the one the server
  // judged, beside the page that knows #10 by its record's lagging head: the document holds one
  // answer of #10 for both, so neither reads it again as the tab draws and the page polls, turn
  // after turn; and when #10's record moves to a new head in the stack's answer, #10 is read
  // again once, whichever of them reads it, and both draw what it says.
  const lanes = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/row-readiness.js")).href
  );
  const tabLane = lanes.createRowReadiness({
    async read(numbers) {
      const answer = await globalThis.fetch(`${lanes.PULL_STATUSES_ROUTE}?numbers=${numbers}`);
      return { status: answer.status, body: await answer.json() };
    },
    schedule(callback) {
      idle.push(callback);
      return callback;
    },
    cancel() {},
    isVisible: () => true,
    now: () => NOW_MS,
    changed() {},
  });
  const tabRow = { number: 10, head: judged.get(10).head, state: "draft" };
  const source = stacksAnswer.source;
  const beside = [];
  for (let turn = 0; turn < 3; turn += 1) {
    statusReads.length = 0;
    tabLane.want([tabRow], source);
    await poll();
    await runIdle();
    beside.push({
      turn: turn + 1,
      asked: [...statusReads],
      pulls_tab: tabLane.readiness(tabRow, source)?.label ?? null,
      page: memberRows()[0].glyph,
    });
  }
  statusReads.length = 0;
  otherAnswers.set(77, {
    ...stack(revision(1)),
    number: 77,
    guide: null,
    members: members.map((member) =>
      member.number === 10 ? { ...member, head: "<moved_head>" } : member,
    ),
  });
  await poll();
  await runIdle();
  tabLane.want([tabRow], source);
  await runIdle();
  report.members_readiness.beside_a_pulls_tab = beside;
  report.members_readiness.record_moved = {
    asked: [...statusReads],
    pulls_tab: tabLane.readiness(tabRow, source)?.label ?? null,
    page: memberRows()[0].glyph,
  };
  assert.ok(
    beside.every((turn) => turn.asked.length === 0),
    "a row two surfaces know by two heads is not read in turn",
  );
  assert.deepEqual(
    statusReads,
    ["/api/plugin/github/pull-statuses?numbers=10"],
    "a member whose record moves is read again once",
  );
  tabLane.dispose();
  judging.dispose?.();
  globalThis.fetch = answered;
  console.log(JSON.stringify(report, null, 2));
}

/**
 * What a note's links open, with static/repository-links.js run whole beside the GitPath
 * codec, as the `repository-links` bundle carries them and the SDK's loader answers them,
 * on a server whose tree is not the stack's head. The allowlist's stand-in makes each link of a note absolute against the carrier's
 * page, as static/inert-html.js does, so a path-relative reference arrives under `/pull/`.
 * The step's note is drawn before the comparison is read: its links open github.com at the
 * head of the comparison drawn, and once the read says what it changes, a changed file's
 * link opens it in the stack's Changes, in place, and an unchanged one stays on github.com.
 * A member's page opens in place through the page's own `open` too, and a commit's page and
 * the list through the shell's (`navigation.openRoute`), which is asked only for what the
 * page declined; a modified click on any of them is the browser's.
 *
 * @param {Record<string, any>} page
 * @param {Record<string, any>} mb The session's SDK, with what this story adds.
 */
async function noteLinks(page, mb) {
  const sandbox = { Object, URL, TextEncoder, TextDecoder, btoa, atob, console };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  for (const name of ["git-path.js", "repository-links.js"]) {
    const file = path.join(root, "src/metabrowser/static", name);
    vm.runInContext(fs.readFileSync(file, "utf8"), sandbox, { filename: file });
  }
  const allowlist = window.MetabrowserInertHtml;
  window.MetabrowserInertHtml = {
    sanitizeHtml(html, base, keepPathRelative) {
      return [
        ...html.matchAll(/<a href="([^"]*)"( data-metabrowser-path-relative="")?>([^<]*)<\/a>/g),
      ].map(([, href, relative, text]) => {
        const link = new Element("a");
        link.setAttribute("href", new URL(href, base).href);
        if (keepPathRelative && relative) {
          link.setAttribute("data-metabrowser-path-relative", "");
        }
        link.setAttribute("target", "_blank");
        link.setAttribute("rel", "noopener noreferrer");
        link.textContent = text;
        return link;
      });
    },
    kpressProse: allowlist.kpressProse,
  };
  // A comparison whose head is a full commit, which a path-relative reference names.
  const head = "5".repeat(40);
  const drawn = { ...drawnFirst, right: head, key: "1".repeat(32) };
  stackAnswer = { ...stack(revision(4)), comparison: drawn };
  /** The comparison's read, which answers when the session says. */
  let answerRead = () => {};
  const read = new Promise((resolve) => {
    answerRead = () =>
      resolve({
        manifest: {
          files: [
            {
              id: "1",
              kind: "modified",
              old: { path: "docs/draft.md" },
              new: { path: "docs/draft.md" },
            },
          ],
          totals: { files: 1, additions: 1, deletions: 0, exact: true },
          truncated: false,
        },
      });
  });
  const view = {
    prefetch: () => read,
    summary: async () => ({ dispose() {} }),
    render: async () => ({ dispose() {} }),
  };
  const opened = [];
  // What the shell was asked to open in place: a route the page's own `open` declined.
  const shell = [];
  const container = new Element("main");
  const handle = page.mountStackPage(
    container,
    {
      number: 70,
      tab: "",
      open(route) {
        opened.push(JSON.stringify(route));
        return Promise.resolve();
      },
    },
    {
      ...mb,
      // As static/plugin-sdk-views.js answers it on a repository's page: the resolver.
      loadRepositoryLinks: async () => sandbox.MetabrowserRepositoryLinks,
      getRegisteredView: () => view,
      repository: {
        host: "github.com",
        owner: "octo",
        name: "demo",
        branch: "main",
        revision: "a".repeat(40),
        served_prefix: "",
      },
      navigation: {
        href: (target) => `/view/${target.path}`,
        open: async () => {},
        openRoute(href) {
          shell.push(`the shell opens ${href}`);
          return true;
        },
      },
      sourceKind: () => "git_revision",
    },
  );
  await settle();
  reads.at(-1).answer({
    ...step(revision(4), 1, pinsOf(drawn)),
    note_html: [
      "<p>",
      '<a href="https://github.com/octo/demo/pull/docs/draft.md" data-metabrowser-path-relative="">the draft</a>',
      '<a href="https://github.com/octo/demo/pull/src/same.txt" data-metabrowser-path-relative="">an unchanged file</a>',
      `<a href="https://github.com/octo/demo/commit/${"e".repeat(40)}">a commit</a>`,
      '<a href="https://github.com/octo/demo/pulls">the pull requests</a>',
      '<a href="https://github.com/octo/demo/pull/72">a member</a>',
      "</p>",
    ].join(""),
  });
  await settle();
  const note = () => container.querySelector(".kpress-prose");
  const told = () =>
    note()
      .querySelectorAll("a[href]")
      .map((link) => `${link.textContent} → ${link.getAttribute("href")}`);
  const drawnFirstNote = note();
  const said = { before_the_read: told() };
  answerRead();
  await settle();
  assert.equal(note(), drawnFirstNote, "the note drawn is read again, not drawn again");
  said.once_read = told();
  const clicks = [];
  const click = (link, modifiers = {}) => {
    const event = { button: 0, defaultPrevented: false, ...modifiers };
    event.preventDefault = () => {
      event.defaultPrevented = true;
    };
    link.events.get("click")?.(event);
    const inPlace = [...opened.splice(0), ...shell.splice(0)];
    assert.ok(inPlace.length <= 1, "one click opens one thing");
    assert.equal(inPlace.length > 0, event.defaultPrevented, "opened in place");
    return event.defaultPrevented ? inPlace.join(", ") : "the browser follows it";
  };
  for (const link of note().querySelectorAll("a[href]")) {
    clicks.push(`${link.textContent}: ${click(link)}`);
  }
  for (const link of note().querySelectorAll("a[href]")) {
    if (link.getAttribute("href").startsWith("/")) {
      clicks.push(`Command-click ${link.textContent}: ${click(link, { metaKey: true })}`);
    }
  }
  said.clicks = clicks;
  handle.dispose?.();
  window.MetabrowserInertHtml = allowlist;
  return said;
}

run().catch((error) => {
  // Straight to standard error: the failure section quiets `console.error` while it runs.
  process.stderr.write(`${error?.stack ?? error}\n`);
  process.exitCode = 1;
});
