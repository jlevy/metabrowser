// Guided Review on the production pull page: its guide is imported and mounted only when its tab
// first paints, a tab left while the import is on its way mounts nothing, a new record revision
// asks again for the step on screen and drops the read still on its way, leaving the tab or
// ending the page disposes the view and aborts its read, and a step is inserted as text, each
// row's code marked for the shell's highlighter to skip. The navigation state machine itself is
// pinned in github-guided-review-session.js; this is the page's ownership of it. Layout is not
// measured: the shell's highlighting and the rows' paint are Chrome's
// (tests/test_github_guided_review_chrome.py).
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");
const { agesFrom, refHelpers } = require("./sdk-ref-fixture.js");
const { linkCardRegistration } = require("./sdk-sandbox.js");

const pagePath = path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js");
const GUIDE_ROUTE = "/api/plugin/github/guided-review";
const FENCE = "Counts to two.\n\n```guided-review\nsoftschema: {}\n```\n";

/** The record's revision for a generation: a revision is 64 hexadecimal characters. */
const revisionOf = (generation) => String(generation).padStart(64, "0");

function envelope(generation) {
  const body = structuredClone(recorded.current.body);
  body.record_revision = revisionOf(generation);
  body.record.pull.body = FENCE;
  body.record.issue_comments = [];
  body.record.reviews = [];
  body.record.review_comments = [];
  body.record.comparison = null;
  body.record.unavailable.comparison = "no_store";
  return body;
}

/** A core preview of page 7: its description, and no record yet. */
function previewEnvelope() {
  const full = envelope(1);
  return {
    ...full,
    state: "pending",
    reason: "not_cached",
    record: null,
    record_revision: null,
    fetched_at: null,
    refreshing: true,
    core_preview: {
      source: full.source,
      number: 7,
      reader: full.record.reader,
      observed_at: full.record.fetched_at,
      revision: "a".repeat(64),
      pull: full.record.pull,
      comparison_state: "no_store",
    },
  };
}

/** One step as the route answers it: one hunk of a context, a deleted and an added line, and
 * a path the comparison does not have. Its text is markup, which a page that inserted it as
 * HTML would draw as elements. */
function step(generation, number, count = 2) {
  const hunks = [
    {
      old_start: 1,
      old_count: 2,
      new_start: 1,
      new_count: 2,
      heading: null,
      lines: [
        { op: "context", text: "one" },
        { op: "del", text: "<i>two</i>" },
        { op: "add", text: "three" },
      ],
    },
  ];
  return {
    state: "ready",
    record_revision: revisionOf(generation),
    comparison: { merge_base: "a".repeat(40), head: "b".repeat(40) },
    step_count: count,
    titles: Array.from({ length: count }, (_, index) => `Step ${index + 1}`),
    // A guide without groups: its outline is its steps, and no step has a group.
    outline: Array.from({ length: count }, (_, index) => ({
      kind: "step",
      step: index + 1,
      title: `Step ${index + 1}`,
    })),
    step: number,
    group: null,
    title: `Step ${number}`,
    note: "Check <b>this</b> first.\nThen that.",
    // A note whose render was refused, which the page shows as typed.
    note_html: null,
    group_note_html: null,
    references: [
      cited({
        path: "src/app.txt",
        side: "new",
        start_line: 1,
        end_line: 2,
        state: "ready",
        href: "/pull/7/files/src/app.txt",
        hunks,
      }),
      cited({ path: "gone.txt", state: "path_not_changed", href: null }),
    ],
  };
}

/** A reference as the route answers it, every field present: a file of the pull request
 * named alone, unless *fields* say otherwise. */
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

/** Step 1 of a guide whose two steps are in one group with a note, which step 1 opens: its
 * title is markup, and *more* adds to or replaces the route's fields. */
function grouped(more = {}) {
  const title = "Step <b>1</b>";
  return {
    ...step(1, 1),
    title,
    outline: [
      {
        kind: "group",
        title: "Decisions",
        note: "Read *these*.",
        children: [
          { kind: "step", step: 1, title },
          { kind: "step", step: 2, title: "Step 2" },
        ],
      },
    ],
    group: 0,
    ...more,
  };
}

/** The page's host. Without *allowlist*, the inert allowlist does not load, as when its
 * script fails: `window.MetabrowserInertHtml` is never set. */
/** The document's keep of step answers (guide-reads.js), which each host empties: each is a
 * fresh load of the page. */
let guideReads = null;
/** The diff plugin's own `fileDisclosure` (diff-view.js), which its `guidePatchDrawer` hands
 * the guide for the cards it draws: the stand-in below hands the same one, so the bar a
 * step's file folds by here is the production one. */
let fileDisclosure = null;

function host({ allowlist = true } = {}) {
  guideReads?.clear();
  const timers = new Map();
  /** Each read of the guide: its step, its signal, and the answer or failure that ends it. */
  const reads = [];
  /** The routes the page asked the page to open. */
  const opened = [];
  /** Each patch the page handed the diff plugin to draw, and whether it was disposed. */
  const patches = [];
  /** Each text's HTML the page handed the allowlist, with the page it resolves against. */
  const sanitized = [];
  /** The diff plugin's export, as `plugins.load("diff")` answers it: it draws each line as
   * the diff draws a row, its text a span. The diff plugin's own drawing (hunk bars, folds,
   * syntax) is its own, pinned by its tests and painted in the Chrome check. */
  const diff = {
    guidePatchDrawer() {
      return Object.assign((body, change, patch) => this.mountFilePatch(body, change, patch), {
        disclose: (section, folded, changed) => fileDisclosure(section, folded, changed),
      });
    },
    mountFilePatch(body, change, patch) {
      const drawn = { path: change.new.path, patch, disposed: false };
      patches.push(drawn);
      for (const hunk of patch.hunks) {
        for (const line of hunk.lines) {
          const row = new Element("div");
          row.className = `diff-line diff-line-${line.op}`;
          const code = new Element("span");
          code.className = "diff-line-text hljs";
          code.textContent = line.text;
          row.append(code);
          body.append(row);
        }
      }
      return {
        dispose() {
          drawn.disposed = true;
        },
      };
    },
  };
  let current = null;
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
    // The allowlist's stand-in: each text it is handed comes back as one element holding the
    // HTML as text, so a test reads where the page put it. The rebuild itself is the
    // allowlist's, pinned by tests/dom/inert-html-session.js.
    MetabrowserInertHtml: !allowlist
      ? undefined
      : {
          sanitizeHtml(html, base) {
            sanitized.push({ html, base });
            const node = document.createElement("span");
            node.className = "inert-rebuilt";
            node.textContent = html;
            return [node];
          },
          kpressProse(nodes) {
            const prose = document.createElement("div");
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
  const response = (body, status = 200) => ({
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => null },
    json: async () => body,
    // The guide reads its answer as text, whose length it keeps (guide-reads.js).
    text: async () => JSON.stringify(body),
  });
  globalThis.fetch = async (route, init = {}) => {
    if (route.startsWith(`${GUIDE_ROUTE}?`)) {
      const asked = new URL(route, "http://localhost").searchParams;
      assert.equal(asked.get("number"), "7");
      return new Promise((resolve, reject) => {
        const read = { step: Number(asked.get("step")), signal: init.signal, settled: false };
        read.answer = (body) => {
          read.settled = true;
          resolve(response(body));
        };
        init.signal?.addEventListener("abort", () => reject(new Error("aborted")), { once: true });
        reads.push(read);
      });
    }
    if (route.startsWith("/api/plugin/github/pull-markdown?")) {
      return response({
        record_revision: current.record_revision,
        fetched_at: current.fetched_at,
        html: "rendered",
        assets: {},
      });
    }
    if (route.startsWith("/api/plugin/github/pull?")) {
      return response(current);
    }
    return response({}, 404);
  };
  return {
    reads,
    opened,
    patches,
    sanitized,
    set current(value) {
      current = value;
    },
    /** Mount page 7 on *tab*, as the shell does at its address. */
    mount(page, tab, initial) {
      current = initial;
      window.location.pathname = tab === "" ? "/pull/7" : `/pull/7/${tab}`;
      const container = new Element("main");
      const handle = page.mountPullPage(
        container,
        {
          number: 7,
          tab,
          // The shell's route: it moves the address, and calls back into the page.
          open(route) {
            opened.push(route);
            return Promise.resolve();
          },
          reader: { initial: { etag: null, body: initial }, fetchAfterMs: 0 },
        },
        {
          perf,
          ensureAsset: async () => {},
          loadKpressAssets: async () => {},
          ...refHelpers(document),
          ...agesFrom(document, () => ({ label: "now", className: "age" })),
          // The SDK's own registration of a note's links for their cards.
          ...linkCardRegistration(),
          formatTimestamp: () => "now",
          navigation: { href: () => "/view/" },
          sourceKind: () => "git_revision",
          shortCommit: (commit) => commit.slice(0, 7),
          icons: { toggle: "" },
          ensureKindAssets: async () => {},
          whenIdle: require("./sdk-idle-fixture.js").whenIdle,
          plugins: {
            async load(name) {
              assert.equal(name, "diff", "the guide loads only the diff plugin");
              return diff;
            },
          },
        },
      );
      const view = () => container.querySelector(".github-pull-guided-review");
      return {
        handle,
        container,
        /** The route arrives at *next*, as the shell's does: the address, then the page. */
        arrive(next) {
          window.location.pathname = next === "" ? "/pull/7" : `/pull/7/${next}`;
          handle.setTab(next);
        },
        guided: view,
        /** Click the guide's button named *label*, as a reader does. */
        press(label) {
          [...container.descendants()]
            .find((node) => node.tag === "button" && node.getAttribute("aria-label") === label)
            .events.get("click")();
        },
        /** The step list's head: the overview or a step, and how many. */
        position: () => container.querySelector(".github-pull-guide-position")?.textContent ?? null,
        /** The step list as it reads: each group's heading in brackets, and each step, the one
         * shown marked. */
        outline: () =>
          container
            .querySelectorAll(".github-pull-guide-steps-heading, .github-pull-guide-steps-link")
            .map((node) =>
              node.classes.has("github-pull-guide-steps-heading")
                ? `[${node.textContent}]`
                : `${node.getAttribute("aria-current") === "step" ? "> " : ""}${node.children
                    .map((part) => part.textContent)
                    .filter(Boolean)
                    .join(" ")}`,
            )
            .join(" | "),
        /** The step list's rows outside any group, which start on a group heading's edge:
         * each by its number, the overview's by its title, since it has none, then how many
         * digits wide their numbers' column is (`--github-pull-guide-loose-digits`). */
        loose() {
          const list = container.querySelector(".github-pull-guide-steps");
          const rows = list.children
            .filter((item) => item.classes?.has("github-pull-guide-steps-item"))
            .map((item) => {
              const isElement = (node) => typeof node !== "string";
              const [first] = item.children.find(isElement).children.filter(isElement);
              return first.classes.has("github-pull-guide-steps-number")
                ? first.textContent
                : `${first.textContent}, no number`;
            });
          const digits = /--github-pull-guide-loose-digits: (\d+)/.exec(
            list.getAttribute("style") ?? "",
          );
          return `${rows.join(" | ")}; column ${digits?.[1] ?? "unset"}`;
        },
        /** The shown step's card head, and the group's note above the card, if any. */
        card() {
          const detail = container.querySelector(".github-pull-guide-step");
          const head = detail?.querySelector(".github-pull-guide-card-head");
          const note = detail?.querySelector(".github-pull-guide-group-note");
          const parts = head?.children.filter((part) => typeof part !== "string");
          return `${parts?.map((part) => part.textContent).join(" | ") ?? "no card"}${
            note ? `; under the group's note: ${note.textContent}` : ""
          }`;
        },
        /** The step list's buttons, in order. */
        links: () => container.querySelectorAll(".github-pull-guide-steps-link"),
        /** What the guide says in place of a step, or "nothing". */
        said() {
          const notice = view()?.children.find((node) => node.classes?.has("github-pull-quiet"));
          return notice && !notice.hidden ? notice.textContent : "nothing";
        },
        /** What an out-of-date guide says above its steps, a warning or a quiet line, or
         * "none". */
        stale() {
          const notice = container.querySelector(".github-pull-guide-stale");
          return notice ? said(notice) : "none";
        },
        /** Each excerpt's path and the note it carries, and each row as it reads, as a
         * reader reads them. */
        references: () =>
          container
            .querySelectorAll(".github-pull-guide-reference")
            .map((section) => {
              const row = section.querySelector(".github-pull-guide-row-link");
              if (row !== null) {
                // A pull request's place is a stack member's, whose tip names its stack.
                const tip = row
                  .querySelector(".github-pull-stack-member-position")
                  ?.getAttribute("data-tip-text");
                return `${row.tag === "a" ? `row to ${row.href}` : "row"}: ${row.textContent.replace(/\s+/g, " ").trim()}${tip ? ` (tip: ${tip})` : ""}`;
              }
              const pull = section.querySelector(".github-pull-guide-reference-pull");
              return `${pull === null ? "" : `${pull.textContent} `}${
                section.querySelector(".diff-file-path").textContent
              }: ${
                [...section.descendants()]
                  .filter((node) => node.tag === "p")
                  .map((note) => note.textContent)
                  .join(" ") || "no note"
              }`;
            })
            .join(" | "),
        /** The step on screen, as the reader sees it, or null while there is none. */
        shown() {
          const title = container
            .querySelector(".github-pull-guide-step")
            ?.querySelector(".github-pull-guide-title");
          return title?.textContent ?? null;
        },
      };
    },
    /** The reads still waiting for an answer. */
    pending: () => reads.filter((read) => !read.settled && !read.signal?.aborted),
    async poll() {
      const due = [...timers].filter(([, timer]) => timer.delay === 1000 || timer.delay === 30000);
      for (const [id, timer] of due) {
        timers.delete(id);
        timer.callback();
      }
      await settle();
    },
  };
}

/** What an out-of-date guide says, and whether it is a warning or a quiet line. */
const said = (notice) =>
  `${notice.dataset.severity ?? (notice.classes.has("github-pull-quiet") ? "quiet" : "plain")}: ${notice.textContent}`;

/** The route's details of a guide written for head b on merge base a, which a page never
 * shows: an agent brings the guide up to date with them. */
const DETAILS = [
  "bbbbbbb",
  "ccccccc",
  "aaaaaaa",
  "Count to",
  "src/app.txt",
  "commit",
  "rebase",
  "merge base",
];

/** Whether *notice* names none of the route's details, and holds no list. */
function plainly(notice) {
  for (const detail of DETAILS) {
    assert.ok(!notice.textContent.includes(detail), `the notice names ${detail}`);
  }
  assert.ok(
    [notice, ...notice.descendants()].every((node) => !["ul", "ol", "li"].includes(node.tag)),
    "the notice holds no list",
  );
}

const asked = (reads) => reads.map((read) => `step ${read.step}`).join(", ") || "nothing";

async function run() {
  const page = await import(pathToFileURL(pagePath).href);
  ({ guideReads } = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/guide-reads.js")).href
  ));
  ({ fileDisclosure } = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/diff/diff-view.js")).href
  ));
  const steps = [];
  /** The card of the shown step's file with a diff, or, without *excerpt*, of its file with
   * a sentence in a diff's place, as a reader finds it: its bar, the
   * trigger that leads it, what the bar folds, and how it stands, which its trigger, its
   * body, and its card must each say alike. */
  const fileCard = (container, excerpt = true) => {
    const section = container
      .querySelectorAll(".github-pull-guide-reference")
      .find((card) => (card.querySelector(".github-pull-guide-excerpt") !== null) === excerpt);
    const bar = section.querySelector(".diff-file-bar");
    const toggle = section.querySelector(".diff-file-toggle");
    const body = section.querySelector(".diff-file-body");
    return {
      section,
      bar,
      toggle,
      body,
      /** A press anywhere on the bar, or a key on its trigger, whose click reaches the bar. */
      press: (target = bar) => bar.events.get("click")({ target }),
      stands() {
        const open = toggle.getAttribute("aria-expanded") === "true";
        assert.equal(body.classes.has("diff-file-body-collapsed"), !open, "the body agrees");
        assert.equal(section.classes.has("diff-file-collapsed"), !open, "the card agrees");
        assert.equal(toggle.classes.has("expanded"), open, "the chevron agrees");
        assert.equal(toggle.classes.has("collapsed"), !open, "the chevron agrees");
        return open ? "open" : "folded";
      },
    };
  };

  // The front page of a pull request with a guide is Guided Review.
  {
    const front = host();
    const view = front.mount(page, "", envelope(1));
    await settle();
    steps.push(
      `the front page: guide ${view.guided() === null ? "not mounted" : "mounted"}; asked ${asked(front.reads)}`,
    );
    view.handle.dispose();
  }

  // A stale guide still shows its steps, read at the pull request's current head, under one
  // warning and its remedy at the top of the page. The steps that cite a changed file are
  // marked, and so is each such file. The commits, heads, merge bases, and paths behind it
  // are the route's, for an agent, and never the page's (mb-b9qd).
  {
    const late = host();
    const view = late.mount(page, "guided", envelope(1));
    await settle();
    late.pending()[0].answer({
      ...step(1, 1, 3),
      state: "stale",
      stale: {
        guide: { merge_base: "a".repeat(40), head: "b".repeat(40) },
        current: { merge_base: "d".repeat(40), head: "c".repeat(40) },
        github_newer: false,
        history: "rewritten",
        commit_count: 12,
        commits: [{ sha: "c".repeat(40), subject: "Count to <b>three</b>" }],
        changed_paths: ["gone.txt", "src/app.txt"],
        changed_steps: [1, 3],
      },
    });
    await settle();
    // The guide opens on its overview, under the step list, with the changed steps marked.
    steps.push(`a stale guide opens on: ${view.position()}; ${view.outline()}`);
    const top = view.guided().children[0];
    const notice = view.container.querySelector(".github-pull-guide-stale");
    assert.ok(top.children.includes(notice), "the notice is the page's first thing");
    plainly(notice);
    steps.push(`a stale guide's notice: ${view.stale()}`);
    const kept = late.reads.length;
    view.press("Next step");
    await settle();
    assert.equal(late.reads.length, kept, "step 1 is the overview's own answer");
    const card = view.container.querySelector(".github-pull-guide-card");
    steps.push(
      `and its step, in a card: ${card.querySelector(".github-pull-card-head").textContent}; ${view.shown()}; ${view.references()}`,
    );
    view.handle.dispose();
  }

  // Lazy mount: Conversation never reads the guide, and its tab mounts it at first paint.
  {
    const first = host();
    const view = first.mount(page, "conversation", envelope(1));
    await settle();
    steps.push(
      `Conversation: guide ${view.guided() === null ? "not mounted" : "mounted"}; asked ${asked(first.reads)}`,
    );
    // The description's guided-review block is a card there, which opens the guide.
    const card = view.container
      .querySelectorAll(".notice")
      .find((node) => node.textContent.includes("guided review"));
    steps.push(`its description's block: ${card?.textContent ?? "no card"}`);
    view.arrive("guided");
    await settle();
    assert.equal(first.pending().length, 1);
    steps.push(`its tab opens: guide mounted; asked ${asked(first.reads)}`);
    // The guide opens with the description, as Conversation renders it.
    const introduction = view.container.querySelector(".github-pull-guide-introduction");
    steps.push(`the guide's overview: ${introduction?.textContent ?? "none"}`);

    // A step is text, not markup, and each row is the diff plugin's: its text a span, which
    // the shell's highlighter, which takes `pre code`, cannot select.
    first.pending()[0].answer(step(1, 1));
    await settle();
    // The overview is step 0: the description shows, under the step list, and Next goes
    // to step 1 with the answer the overview already has.
    // The page's wrapper of the description card, third after the notice and the step list.
    const wrapper = view.guided().children[2];
    assert.ok([...wrapper.descendants()].includes(introduction));
    assert.equal(wrapper.hidden, false);
    steps.push(
      `the guide opens on: ${view.position()}; ${view.outline()}; step shown ${view.shown()}`,
    );
    // No row is in a group, so each starts on a group heading's edge: the overview's title,
    // with no number, and each step's number, in a column one digit wide (mb-420k).
    steps.push(`its rows outside a group: ${view.loose()}`);
    // A guide without groups draws its list as it did before groups: an item for the overview
    // and one for each step, each holding its button, and no group's heading, list, or item.
    const nodes = (parent) => parent.children.filter((node) => typeof node !== "string");
    assert.deepEqual(
      nodes(view.container.querySelector(".github-pull-guide-steps")).map((item) => [
        item.tag,
        [...item.classes],
        nodes(item),
      ]),
      view.links().map((link) => ["li", ["github-pull-guide-steps-item"], [link]]),
    );
    assert.equal(view.links().length, 3);
    assert.equal(
      view.container.querySelectorAll(
        ".github-pull-guide-steps-heading, .github-pull-guide-steps-members, .github-pull-guide-steps-group",
      ).length,
      0,
    );
    view.press("Next step");
    await settle();
    assert.equal(wrapper.hidden, true, "a step replaces the overview");
    assert.equal(first.reads.length, 1);
    const commentary = view.container.querySelector(".github-pull-guide-commentary");
    assert.equal(commentary.textContent, "Check <b>this</b> first.\nThen that.");
    assert.ok(
      commentary.children.every((child) => typeof child === "string"),
      "the commentary holds text and no element",
    );
    // The diff plugin draws the excerpt from the step's hunks, as it draws Changes.
    assert.deepEqual(
      first.patches.map(({ path, patch }) => [path, patch.hunks.length, patch.truncated]),
      [["src/app.txt", 1, false]],
    );
    const lines = view.container
      .querySelector(".github-pull-guide-excerpt")
      .querySelectorAll(".diff-line");
    steps.push(
      `step 1: ${view.shown()}; rows ${lines
        .map((line) => {
          const code = line.children.find((child) => child.classes?.has("diff-line-text"));
          assert.equal(code.tag, "span", "a row's text is a span, as the diff draws it");
          assert.ok(line.classes.has("diff-line"), "a row is the diff plugin's row");
          assert.ok(
            code.children.every((child) => typeof child === "string"),
            "a row's text holds text and no element",
          );
          const op = ["context", "del", "add"].find((name) =>
            line.classes.has(`diff-line-${name}`),
          );
          return `${op} ${code.textContent}`;
        })
        .join(", ")}`,
    );
    const quiet = view.container
      .querySelectorAll(".github-pull-quiet")
      .map((node) => node.textContent);
    steps.push(
      `a path outside the comparison says: ${quiet.filter((text) => text.startsWith("This path")).join("")}`,
    );

    // Open full diff goes to the file's route, the page's own openChangedFile.
    const link = view.container
      .querySelector(".github-pull-guide-reference-header")
      .children.find((child) => child.tag === "a");
    first.opened.length = 0;
    link.events.get("click")({
      button: 0,
      metaKey: false,
      ctrlKey: false,
      shiftKey: false,
      altKey: false,
      preventDefault() {},
    });
    await settle();
    steps.push(
      `Open full diff: ${first.opened.map((route) => `${route.tab} ${route.file}`).join("; ")}`,
    );

    // The excerpt's card folds as a file's does in Changes, by the diff plugin's own bar and
    // chevron: the trigger is a button that leads the bar and names the file, everything
    // under the bar folds, and folding disposes nothing the diff drew. The bar's motion and where it sits are
    // Chrome's (tests/dom/github-guided-review-fold-chrome.mjs).
    const fileOne = fileCard(view.container);
    assert.equal(
      fileOne.toggle.tag,
      "button",
      "the trigger is a button, which takes focus and keys",
    );
    assert.equal(fileOne.bar.children[0], fileOne.toggle, "the trigger leads the bar");
    assert.equal(fileOne.toggle.getAttribute("aria-controls"), fileOne.body.getAttribute("id"));
    assert.ok(fileOne.toggle.children[0].classes.has("diff-file-chevron"), "the chevron leads");
    assert.equal(
      fileOne.toggle.querySelector(".diff-file-path").textContent,
      "src/app.txt",
      "the trigger names the file",
    );
    assert.ok(link.classes.has("diff-file-view"), "Open full diff is the bar's view control");
    assert.ok(
      fileOne.body.querySelector(".github-pull-guide-excerpt") !== null,
      "the bar folds the excerpt",
    );
    const folds = [fileOne.stands()];
    fileOne.press();
    folds.push(`its bar pressed: ${fileOne.stands()}, ${lines.length} rows kept`);
    assert.equal(
      view.container.querySelector(".github-pull-guide-excerpt").querySelectorAll(".diff-line")
        .length,
      lines.length,
    );
    assert.equal(first.patches[0].disposed, false, "folding disposes nothing");
    fileOne.press(fileOne.toggle);
    folds.push(`its trigger pressed: ${fileOne.stands()}`);
    // A card that holds a sentence in a diff's place is built on the same bar, and folds.
    const sentence = fileCard(view.container, false);
    assert.equal(sentence.toggle.tag, "button");
    sentence.press();
    folds.push(`a card with no diff, its bar pressed: ${sentence.stands()}`);
    sentence.press();
    steps.push(`step 1's file: ${folds.join("; ")}`);
    // Left folded, to be found folded when the step is drawn again (below).
    fileOne.press();
    assert.equal(fileOne.stands(), "folded");

    // Next asks for step 2 alone, and the step shown stays, its diff with it, until step 2
    // is in hand to show in its place. Leaving the tab with that read on its way disposes
    // the view and its diff; the read goes on for the document's keep, and its late answer
    // paints nothing.
    view.press("Next step");
    await settle();
    const second = first.pending()[0];
    assert.equal(second.step, 2);
    assert.equal(first.patches[0].disposed, false, "the step shown stays while the next is read");
    steps.push(`Next with step 2 on its way: step shown ${view.shown()}`);
    view.arrive("conversation");
    await settle();
    assert.equal(first.patches[0].disposed, true, "leaving the tab disposes the step's diff");
    steps.push(
      `left for Conversation with step 2 on its way: read aborted ${second.signal.aborted}; guide ${view.guided() === null ? "gone" : "still there"}`,
    );
    second.answer?.(step(1, 2));
    await settle();
    assert.equal(view.guided(), null);

    // Back on the tab, a view of its own is mounted again, on its overview, which the keep
    // shows at once with the steps read before, reading none of them again.
    const before = first.reads.length;
    view.arrive("guided");
    await settle();
    steps.push(`its tab again: ${view.position()}; asked ${asked(first.reads.slice(before))}`);
    view.press("Next step");
    // A file the reader folded stays folded for the document, as the answers are kept
    // (guide-reads.js, mb-ez0x): the guide mounted again on its tab draws step 1's file
    // folded, and so does a step the reader leaves and comes back to; opened, it stays open.
    const kept = [`back on the tab ${fileCard(view.container).stands()}`];
    view.press("Next step");
    view.press("Previous step");
    kept.push(`after Next and Back ${fileCard(view.container).stands()}`);
    fileCard(view.container).press();
    view.press("Next step");
    steps.push(
      `and its kept steps at once: step shown ${view.shown()}; asked ${asked(first.reads.slice(before))}`,
    );
    view.press("Previous step");
    kept.push(`opened, then Next and Back ${fileCard(view.container).stands()}`);
    steps.push(`step 1's file, left folded: ${kept.join("; ")}`);
    view.handle.dispose();
    // The folds are a guide's at one head: the same guide read at a new head, whose files
    // may differ, starts with none, and so does another guide.
    const { foldKey } = await import(
      pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/guided-review.js")).href
    );
    const appKey = foldKey(1, 0, { pull: null, path: "src/app.txt" });
    // A fold is one card's: the same path at the same place in another pull request, as a
    // guide rewritten at the same head can cite, or at another place or step, is another's.
    const others = [
      foldKey(1, 0, { pull: 8, path: "src/app.txt" }),
      foldKey(1, 0, { pull: 9, path: "src/app.txt" }),
      foldKey(1, 1, { pull: null, path: "src/app.txt" }),
      foldKey(2, 0, { pull: null, path: "src/app.txt" }),
    ];
    assert.equal(new Set([appKey, ...others]).size, others.length + 1);
    const atHead = guideReads.folds("number=7", "b".repeat(40));
    atHead.set(appKey, true);
    // Opening the last folded file leaves the guide no entry, and folding one makes it.
    atHead.set(appKey, false);
    assert.equal(atHead.has(appKey), false);
    atHead.set(appKey, true);
    steps.push(
      `a fold kept for a guide at its head: the same head ${guideReads.folds("number=7", "b".repeat(40)).has(appKey)}, another guide ${guideReads.folds("number=8", "b".repeat(40)).has(appKey)}, a new head ${guideReads.folds("number=7", "c".repeat(40)).has(appKey)}, the first head again ${guideReads.folds("number=7", "b".repeat(40)).has(appKey)}`,
    );
  }

  // Replacement: a new record revision asks for the step on screen again, and drops the read
  // on its way, which goes on for the document's keep; the late answer to the dropped read
  // paints nothing.
  {
    const second = host();
    const view = second.mount(page, "guided", envelope(1));
    await settle();
    const old = second.pending()[0];
    steps.push(`opened on its tab: asked ${asked(second.reads)}`);
    second.current = envelope(2);
    await second.poll();
    steps.push(
      `a newer record arrives with the read on its way: old read aborted ${old.signal.aborted}; ` +
        `asked ${asked(second.reads)}`,
    );
    old.answer?.(step(1, 1));
    await settle();
    assert.equal(view.shown(), null, "the dropped read's answer paints nothing");
    second.pending()[0].answer(step(2, 1));
    await settle();
    steps.push(`the new read's answer: ${view.position()}`);
    // A poll that finds the same record asks for nothing.
    await second.poll();
    steps.push(`a poll of the same record: asked ${asked(second.reads)}`);
    view.handle.dispose();
  }

  // A tab left while the import is on its way mounts nothing, and neither does a page that
  // ends there: each is a view that nothing disposes if it were mounted late.
  {
    const third = host();
    const view = third.mount(page, "conversation", envelope(1));
    await settle();
    view.arrive("guided");
    view.arrive("conversation");
    await settle();
    steps.push(
      `Guided Review opened and left before its import settled: guide ${view.guided() === null ? "not mounted" : "mounted"}; asked ${asked(third.reads)}`,
    );
    view.arrive("guided");
    view.handle.dispose();
    await settle();
    steps.push(`the page ended before the import settled: asked ${asked(third.reads)}`);
  }

  // A guide this copy matches, stale only because GitHub reports a newer head: what the
  // newer commits changed is unknown, so the guide never says that its steps match (B1 of
  // review B on #677), and the page's header already says new commits were pushed, so the
  // guide says nothing at all.
  {
    const newer = host();
    const view = newer.mount(page, "guided", envelope(1));
    await settle();
    const pins = { merge_base: "a".repeat(40), head: "b".repeat(40) };
    newer.pending()[0].answer({
      ...step(1, 1, 3),
      state: "stale",
      stale: {
        guide: pins,
        current: pins,
        github_newer: true,
        history: "ahead",
        commit_count: 0,
        commits: [],
        changed_paths: null,
        changed_steps: null,
      },
    });
    await settle();
    steps.push(`a guide behind a newer head on GitHub: ${view.stale()}; ${view.outline()}`);
    view.handle.dispose();
  }

  // A guide whose head this copy lacks, as after a force push it never fetched: what changed
  // is unknown, so no step is marked, the warning says some may not match, and each reference
  // says what may be so, above its excerpt or in its place (A1 of review A on #795). A path
  // the pull request does not change says what any guide's would, since whether it ever did
  // is unknown (A7).
  {
    const lost = host();
    const view = lost.mount(page, "guided", envelope(1));
    await settle();
    const answered = step(1, 1, 3);
    lost.pending()[0].answer({
      ...answered,
      state: "stale",
      references: [
        ...answered.references,
        cited({
          path: "src/app.txt",
          side: "old",
          start_line: 2,
          end_line: 4,
          state: "range_unavailable",
          href: "/pull/7/files/src/app.txt",
        }),
      ],
      stale: {
        guide: { merge_base: "a".repeat(40), head: "b".repeat(40) },
        current: { merge_base: "a".repeat(40), head: "c".repeat(40) },
        github_newer: false,
        history: "unavailable",
        commit_count: null,
        commits: [],
        changed_paths: null,
        changed_steps: null,
      },
    });
    await settle();
    plainly(view.container.querySelector(".github-pull-guide-stale"));
    steps.push(`a guide whose head this copy lacks: ${view.stale()}; ${view.outline()}`);
    view.press("Next step");
    await settle();
    steps.push(`and its step: ${view.shown()}; ${view.references()}`);
    view.handle.dispose();
  }

  // A step that cites past its pull request: another pull request is a row as the stack menu
  // lists a member, which opens that pull request's page, and one this copy has not read is
  // named by its number; a file of another pull request is drawn under a bar that names it,
  // whose Open full diff opens that file in that pull request's Changes, and one this copy
  // cannot read says why; a commit is a row of its subject, when it was committed, and its
  // short ID, linking to the commit, and one the store lacks says so. A stale guide whose
  // changed files include a path another pull request's reference names marks none of them.
  {
    const wide = host();
    const view = wide.mount(page, "guided", envelope(1));
    await settle();
    const answered = step(1, 1, 3);
    const head = "c".repeat(40);
    const past = {
      ...answered,
      state: "stale",
      stale: {
        guide: { merge_base: "a".repeat(40), head: "b".repeat(40) },
        current: { merge_base: "a".repeat(40), head },
        github_newer: false,
        history: "ahead",
        commit_count: 1,
        commits: [],
        changed_paths: ["src/app.txt"],
        changed_steps: [3],
      },
      references: [
        cited({
          kind: "pull",
          pull: 8,
          href: "/pull/8",
          target: {
            title: "Say <b>more</b>",
            state: "merged",
            // In the guide's own stack, so its place is bare.
            stack: { number: 71, place: 1, count: 3, own: true },
            // Its author, drawn by the page's `identity` in a stack member's row
            // (stack-member-row.js).
            author: "maintainer",
            avatar: null,
          },
        }),
        // In another stack, which its place names (A2 of review A on #853).
        cited({
          kind: "pull",
          pull: 50,
          href: "/pull/50",
          target: {
            title: "Work item 50",
            state: "open",
            stack: { number: 300, place: 2, count: 2, own: false },
            author: "contributor",
            avatar: null,
          },
        }),
        cited({ kind: "pull", pull: 2000, state: "not_cached", href: "/pull/2000" }),
        cited({
          kind: "pull_file",
          pull: 9,
          path: "src/app.txt",
          href: "/pull/9/files/src/app.txt",
          hunks: answered.references[0].hunks,
          comparison: {
            merge_base: "a".repeat(40),
            head: "9".repeat(40),
            route: "/api/plugin/github/pull-comparison?number=9",
            image_route: "/api/plugin/github/pull-image?number=9",
            rendered_route: "/api/plugin/github/pull-rendered-diff?number=9",
          },
        }),
        cited({
          kind: "pull_file",
          pull: 12,
          path: "docs/plan.md",
          state: "not_cached",
          href: "/pull/12/files/docs/plan.md",
        }),
        cited({
          kind: "commit",
          commit: head,
          href: `/commit/${head}`,
          target: { subject: "Count <i>to</i> two", committed_at: "2026-08-29T14:40:00Z" },
        }),
        cited({ kind: "commit", commit: "e".repeat(40), state: "commit_unavailable" }),
        // A commit the served checkout lacks, which the route answers with no address.
        cited({
          kind: "commit",
          commit: "f".repeat(40),
          target: { subject: "Fetched with its pull request", committed_at: null },
        }),
        // One with its time, which still ends its row, after the note
        // (docs/design-system.md, "Ages End the Row").
        cited({
          kind: "commit",
          commit: "d".repeat(40),
          target: { subject: "Fetched and dated", committed_at: "2026-08-29T14:40:00Z" },
        }),
      ],
    };
    wide.pending()[0].answer(past);
    await settle();
    view.press("Next step");
    await settle();
    // It cites pull requests this copy has not read, so its answer is not kept: the step is
    // read again as the reader moves to it, and fills in once they are read (`retryable` in
    // guide-reads.js).
    const again = wide.pending();
    steps.push(
      `moving to it reads it again: ${again.length} read, ${view.shown() ?? "the overview"} shown meanwhile`,
    );
    again[0].answer(past);
    await settle();
    steps.push(`a step past its pull request: ${view.card()}; ${view.references()}`);
    const plain = {
      button: 0,
      metaKey: false,
      ctrlKey: false,
      shiftKey: false,
      altKey: false,
      preventDefault() {},
    };
    wide.opened.length = 0;
    view.container.querySelector(".github-pull-guide-pull").events.get("click")(plain);
    view.container
      .querySelectorAll(".github-pull-guide-reference-header")
      .map((bar) => bar.children.find((child) => child.tag === "a"))
      .find(Boolean)
      .events.get("click")(plain);
    await settle();
    steps.push(
      `its pull request row, then its other pull request's Open full diff, open: ${wide.opened
        .map(
          (route) =>
            `#${route.number} ${route.tab || "front page"}${route.file ? ` ${route.file}` : ""}`,
        )
        .join("; ")}`,
    );
    const commit = view.container
      .querySelectorAll(".github-pull-guide-commit")
      .find((node) => node.tag === "a");
    assert.equal(commit.events.get("click"), undefined, "a commit opens as a plain link");
    view.handle.dispose();
  }

  // A guide whose cited files are all as they were, after the base branch was merged in or
  // a rebase that kept them: a quiet line, with no warning and no remedy.
  {
    host();
    const { staleNotice } = await import(
      pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/guided-review.js")).href
    );
    const notice = staleNotice({
      guide: { merge_base: "a".repeat(40), head: "b".repeat(40) },
      current: { merge_base: "d".repeat(40), head: "c".repeat(40) },
      github_newer: false,
      history: "ahead",
      commit_count: 3,
      commits: [{ sha: "c".repeat(40), subject: "Merge main" }],
      changed_paths: [],
      changed_steps: [],
    });
    plainly(notice);
    steps.push(`a guide whose cited files did not change: ${said(notice)}`);
  }

  // A guide whose merge base alone moved, as when the base branch moved under the same head:
  // it is out of date all the same, so a cited file changed on the base side marks its step,
  // and when none did a quiet line says so (A5 of review A on #795).
  {
    const based = host();
    const view = based.mount(page, "guided", envelope(1));
    await settle();
    const pins = { merge_base: "a".repeat(40), head: "b".repeat(40) };
    const moved = { merge_base: "d".repeat(40), head: "b".repeat(40) };
    const stale = {
      guide: pins,
      current: moved,
      github_newer: false,
      history: "ahead",
      commit_count: 0,
      commits: [],
      changed_paths: ["src/app.txt"],
      changed_steps: [1],
    };
    based.pending()[0].answer({ ...step(1, 1, 3), state: "stale", stale });
    await settle();
    plainly(view.container.querySelector(".github-pull-guide-stale"));
    steps.push(`a guide whose merge base alone moved: ${view.stale()}; ${view.outline()}`);
    view.handle.dispose();
    const { staleNotice } = await import(
      pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/guided-review.js")).href
    );
    const quiet = staleNotice({ ...stale, changed_paths: [], changed_steps: [] });
    plainly(quiet);
    steps.push(`and when none of its files changed: ${said(quiet)}`);
  }

  // One step's read refused, or failed, keeps the guide: its steps, the place, and the way
  // on, with the reason in the step's place; the step is read again when chosen again (B7
  // of review B on #677). A step chosen from the list keeps its button, which a reader's
  // focus is on (B14).
  {
    const refused = host();
    const view = refused.mount(page, "guided", envelope(1));
    await settle();
    refused.pending()[0].answer(step(1, 1, 3));
    await settle();
    const buttons = view.links();
    buttons[2].events.get("click")();
    await settle();
    refused
      .pending()[0]
      .answer({ state: "comparison_unavailable", record_revision: revisionOf(1) });
    await settle();
    steps.push(`a refused step: ${view.position()}; ${view.outline()}; says ${view.said()}`);
    assert.ok(
      view.links().every((button, index) => button === buttons[index]),
      "the step list keeps its buttons across a step chosen from it",
    );
    buttons[2].events.get("click")();
    await settle();
    steps.push(`chosen again: asked ${asked(refused.reads)}`);
    refused.pending()[0].answer(step(1, 2, 3));
    await settle();
    steps.push(`and answered: ${view.position()}; ${view.shown()}; says ${view.said()}`);
    view.press("Previous step");
    await settle();
    steps.push(`back: ${view.position()}; asked ${asked(refused.reads)}`);
    view.handle.dispose();
  }

  // Rows outside any group start on a group heading's edge, numbered in a column as wide as
  // the widest of their numbers (mb-420k): two digits for a guide of twelve steps in no
  // group, and one for a guide whose one step outside a group is its first, though its
  // group's steps run to 11, since a group's steps keep a column of their own.
  for (const [name, count, outline] of [
    ["a guide of twelve steps", 12, null],
    [
      "a step, then a group of ten",
      11,
      [
        { kind: "step", step: 1, title: "Step 1" },
        {
          kind: "group",
          title: "The rest",
          note: null,
          children: Array.from({ length: 10 }, (_, index) => ({
            kind: "step",
            step: index + 2,
            title: `Step ${index + 2}`,
          })),
        },
      ],
    ],
  ]) {
    const long = host();
    const view = long.mount(page, "guided", envelope(1));
    await settle();
    const answer = step(1, 1, count);
    long.pending()[0].answer(outline === null ? answer : { ...answer, outline });
    await settle();
    steps.push(`${name}, its rows outside a group: ${view.loose()}`);
    view.handle.dispose();
  }

  // A guide in groups: each group is a heading in the step list, with no number and nothing
  // to press, above its steps, which keep their numbers through the groups; a step outside
  // a group sits between them. A step's card names its group before its place, and a
  // group's note shows above its first step alone. The list keeps its buttons as the reader
  // moves, and its changed marks are the steps' own.
  {
    const grouped = host();
    const view = grouped.mount(page, "guided", envelope(1));
    await settle();
    const outline = [
      {
        kind: "group",
        title: "Decisions",
        note: "Read these first.\nEach says why.",
        children: [
          { kind: "step", step: 1, title: "Step 1" },
          { kind: "step", step: 2, title: "Step 2" },
        ],
      },
      { kind: "step", step: 3, title: "Step 3" },
      {
        kind: "group",
        title: "Testing",
        note: null,
        children: [{ kind: "step", step: 4, title: "Step 4" }],
      },
    ];
    const groups = [0, 0, null, 2];
    /** Step *at* of the grouped guide, as the route answers it. */
    const answer = (at) => ({ ...step(1, at, 4), outline, group: groups[at - 1] });
    const stale = {
      guide: { merge_base: "a".repeat(40), head: "b".repeat(40) },
      current: { merge_base: "a".repeat(40), head: "c".repeat(40) },
      github_newer: false,
      history: "ahead",
      commit_count: 1,
      commits: [],
      changed_paths: ["src/app.txt"],
      changed_steps: [2, 4],
    };
    grouped.pending()[0].answer({ ...answer(1), state: "stale", stale });
    await settle();
    steps.push(`a guide in groups opens on: ${view.position()}; ${view.outline()}`);
    steps.push(`its rows outside a group: ${view.loose()}`);
    const headings = view.container.querySelectorAll(".github-pull-guide-steps-heading");
    assert.ok(
      headings.every((heading) => heading.tag !== "button" && heading.events.size === 0),
      "a group's heading is no control",
    );
    // Each group's list is named by the heading above it, as a menu's group heading names its
    // group, by an id of its own (A7 of review A on #807).
    const members = view.container.querySelectorAll(".github-pull-guide-steps-members");
    const namedBy = members.map((list) => {
      const peers = list.parentNode.children;
      const heading = peers[peers.indexOf(list) - 1];
      return heading?.classes.has("github-pull-guide-steps-heading") &&
        typeof heading.id === "string" &&
        heading.id !== "" &&
        list.getAttribute("aria-labelledby") === heading.id
        ? heading.id
        : null;
    });
    assert.ok(
      members.length === 2 &&
        namedBy.every((id) => id !== null) &&
        new Set(namedBy).size === members.length,
      "each group's list is named by its own heading",
    );
    const buttons = view.links();
    view.press("Next step");
    await settle();
    steps.push(`its first step: ${view.card()}`);
    view.press("Next step");
    await settle();
    grouped.pending()[0].answer({ ...answer(2), state: "stale", stale });
    await settle();
    steps.push(`its second: ${view.card()}`);
    for (const at of [3, 4]) {
      view.links()[at].events.get("click")();
      await settle();
      grouped.pending()[0].answer({ ...answer(at), state: "stale", stale });
      await settle();
      steps.push(`step ${at}: ${view.card()}; ${view.outline()}`);
    }
    assert.ok(
      view.links().every((button, index) => button === buttons[index]),
      "the grouped list keeps its buttons as the reader moves",
    );
    steps.push(`asked: ${asked(grouped.reads)}`);
    view.handle.dispose();
  }

  // A note is Markdown, which the route renders inert as it renders the description: the page
  // hands that HTML to the description's allowlist, against the pull request's page, and sets
  // what it builds in the step's prose after the title, which stays text. A group's note on its
  // first step is drawn the same way, in a KPress article above the card. A note whose render
  // was refused shows as typed, holding no element (step 1 above), with the line that says why
  // when the route says why (below).
  {
    const rendered = host();
    const view = rendered.mount(page, "guided", envelope(1));
    await settle();
    rendered.pending()[0].answer(
      grouped({
        note_html: "<p>Check <b>this</b> first.</p>",
        group_note_html: "<p>Read <em>these</em>.</p>",
      }),
    );
    await settle();
    // The overview's description is the allowlist's too; only the step's texts count here.
    rendered.sanitized.length = 0;
    view.press("Next step");
    await settle();
    const card = view.container.querySelector(".github-pull-guide-card");
    const prose = card.querySelector(".kpress-prose");
    const [heading, ...blocks] = prose.children;
    assert.equal(heading.tag, "h2");
    assert.ok(
      heading.children.every((child) => typeof child === "string"),
      "a title holds text and no element",
    );
    assert.equal(card.querySelector(".github-pull-guide-commentary"), null);
    const note = view.container.querySelector(".github-pull-guide-group-note");
    const article = note.querySelector(".kpress");
    assert.ok(
      note.tag === "div" &&
        note.classes.has("chrome-prose") &&
        article?.tag === "article" &&
        article.querySelector(".kpress-prose") !== null,
      "a group's rendered note is set in a KPress article",
    );
    steps.push(
      `a rendered note: title ${heading.textContent}; blocks ${blocks
        .map((block) => `${block.tag}.${[...block.classes].join(".")}: ${block.textContent}`)
        .join(
          ", ",
        )}; group's note ${note.querySelector(".inert-rebuilt")?.textContent}; allowlist asked ${rendered.sanitized
        .map(({ html, base }) => `${html} at ${base}`)
        .join(", ")}`,
    );
    view.handle.dispose();
  }

  // A note whose render was refused shows as typed, with the line a description's refusal
  // says under it, in a warning: for a note too slow to render, that it took too long; for a
  // group's note whose renderer was busy, that a reload may render it. Neither names the code.
  // An answer with a busy renderer's refusal is not kept, so the step the overview read is
  // read again when the reader moves to it.
  {
    const refused = host();
    const view = refused.mount(page, "guided", envelope(1));
    await settle();
    const answer = grouped({
      note_refusal: "render_deadline",
      group_note_refusal: "renderer_busy",
    });
    refused.pending()[0].answer(answer);
    await settle();
    view.press("Next step");
    await settle();
    refused.pending()[0].answer(answer);
    await settle();
    const card = view.container.querySelector(".github-pull-guide-card");
    const commentary = card.querySelector(".github-pull-guide-commentary");
    assert.ok(
      commentary.children.every((child) => typeof child === "string"),
      "a refused note holds text and no element",
    );
    const detail = view.container.querySelector(".github-pull-guide-step");
    const lines = detail.querySelectorAll(".github-pull-guide-note-refused");
    for (const line of lines) {
      assert.equal(line.getAttribute("role"), "status");
      assert.ok(!/render_|renderer_/.test(line.textContent), "the line names no code");
    }
    const typed = detail.querySelector(".github-pull-guide-group-note-typed");
    assert.equal(
      detail.children.indexOf(typed) + 1,
      detail.children.indexOf(lines[0]),
      "the group's line follows its note",
    );
    assert.ok(
      card.querySelector(".github-pull-text").children.includes(lines[1]),
      "the step's line is in the card's text, after the note",
    );
    steps.push(
      `refused notes: asked ${asked(refused.reads)}; group's note ${typed.textContent} | ${said(lines[0])}; step's note ${commentary.textContent} | ${said(lines[1])}; allowlist asked ${refused.sanitized.filter(({ html }) => html !== "rendered").length}`,
    );
    view.handle.dispose();
  }

  // Without the allowlist, which failed to load, a note the route rendered shows as typed, a
  // step's and its group's alike, as a description's text shows plain; nothing is said beside
  // it, since the render came, and the console says why.
  {
    const warned = [];
    const warn = console.warn;
    console.warn = (...args) => warned.push(String(args[0]));
    try {
      const bare = host({ allowlist: false });
      const view = bare.mount(page, "guided", envelope(1));
      await settle();
      bare.pending()[0].answer(
        grouped({
          note_html: "<p>Check <b>this</b> first.</p>",
          group_note_html: "<p>Read <em>these</em>.</p>",
        }),
      );
      await settle();
      view.press("Next step");
      await settle();
      const detail = view.container.querySelector(".github-pull-guide-step");
      const commentary = detail.querySelector(".github-pull-guide-commentary");
      const typed = detail.querySelector(".github-pull-guide-group-note-typed");
      assert.equal(detail.querySelector(".github-pull-guide-note-refused"), null);
      assert.equal(detail.querySelector(".inert-rebuilt"), null);
      steps.push(
        `no allowlist: step's note ${commentary?.textContent ?? "not typed"}; group's note ${typed?.textContent ?? "not typed"}; console ${warned.filter((line) => line.includes("guide's notes")).join(", ")}`,
      );
      view.handle.dispose();
    } finally {
      console.warn = warn;
    }
  }

  // A core preview resolves the front page from its description, as the record will: a
  // guided pull request opens on Guided Review, which waits for the record, and the record's
  // arrival reads the guide without changing tab (B3 of review B on #677).
  {
    const early = host();
    const view = early.mount(page, "", previewEnvelope());
    await settle();
    steps.push(
      `a preview's front page: guide ${view.guided() === null ? "not mounted" : "mounted"}; says ${view.said()}; asked ${asked(early.reads)}`,
    );
    assert.notEqual(view.guided(), null, "a preview's front page is its guide");
    early.current = envelope(1);
    await early.poll();
    steps.push(
      `its record arrives: guide ${view.guided() === null ? "not mounted" : "mounted"}; asked ${asked(early.reads)}`,
    );
    view.handle.dispose();
  }

  // On a guided front page, Guided Review's link and key go to the page on screen, never to
  // a second history entry of it at /pull/<n>/guided (B20 of review B on #677); from
  // Conversation they go to the front page.
  {
    const front = host();
    const view = front.mount(page, "", envelope(1));
    await settle();
    const tab = (label) =>
      view.container
        .querySelectorAll(".tab-btn")
        .find((link) => link.tag === "a" && link.textContent === label);
    view.handle.setTab("guided");
    await settle();
    assert.equal(front.opened.length, 0, "the page on screen is not opened again");
    assert.equal(tab("Guided Review").getAttribute("href"), "/pull/7");
    steps.push(
      `the guided front page: Guided Review links ${tab("Guided Review").getAttribute("href")}, Conversation ${tab("Conversation").getAttribute("href")}; its key opens ${front.opened.length === 0 ? "nothing" : front.opened.map((route) => route.tab).join(", ")}`,
    );
    view.handle.dispose();
    const away = host();
    const there = away.mount(page, "conversation", envelope(1));
    await settle();
    const card = there.container
      .querySelectorAll(".notice")
      .find((node) => node.textContent.includes("guided review"));
    const link = [card, ...card.descendants()].find((node) => node.tag === "a");
    assert.equal(link.getAttribute("href"), "/pull/7");
    steps.push(`from Conversation, the description's card links ${link.getAttribute("href")}`);
    there.handle.dispose();
  }

  // A description that carries a stack's guide: the server renders it without the block,
  // and Conversation's card says it has a stack guide, read on its stack's page, never that
  // it is the stack's, since a member above may carry the one the stack shows. It links
  // each stack the pull request is a member of once the stacks are known, and none while
  // it is in no stack this copy knows (A7 of review A on #838).
  {
    const optionalStacks = require("../fixtures/github-stacks-responses.json");
    const carrier = host();
    const routed = globalThis.fetch;
    globalThis.fetch = (route, init) =>
      route === "/api/plugin/github/stacks"
        ? Promise.resolve({
            ok: true,
            status: 200,
            headers: { get: () => optionalStacks.current.etag },
            json: async () => optionalStacks.current.body,
          })
        : routed(route, init);
    const described = envelope(1);
    described.record.pull.body = "Counts to two.\n\n```stack-review\nsoftschema: {}\n```\n";
    const view = carrier.mount(page, "conversation", described);
    await settle();
    const card = view.container
      .querySelectorAll(".notice")
      .find((node) => node.textContent.includes("stack guide"));
    const links = [...card.descendants()]
      .filter((node) => node.tag === "a")
      .map((node) => `${node.textContent} (${node.getAttribute("href")})`);
    assert.deepEqual(links, ["Open Stack #286 (/stack/286)"]);
    assert.ok(
      !view.container.textContent.includes("Open Guided Review"),
      "a stack's guide is not this pull request's",
    );
    steps.push(
      `a description with a stack's guide: "${card.textContent}" links ${links.join(", ")}`,
    );
    view.handle.dispose();
    const alone = host();
    // The stack column, emptied, checks where focus was, as the page does in a browser.
    globalThis.HTMLElement ??= Element;
    const unstacked = globalThis.fetch;
    globalThis.fetch = (route, init) =>
      route === "/api/plugin/github/stacks"
        ? Promise.resolve({
            ok: true,
            status: 200,
            headers: { get: () => optionalStacks.empty.etag },
            json: async () => optionalStacks.empty.body,
          })
        : unstacked(route, init);
    const lone = alone.mount(page, "conversation", described);
    await settle();
    const loneCard = lone.container
      .querySelectorAll(".notice")
      .find((node) => node.textContent.includes("stack guide"));
    assert.equal(
      [...loneCard.descendants()].filter((node) => node.tag === "a").length,
      0,
      "a pull request in no stack this copy knows links none",
    );
    steps.push(`one in no stack this copy knows: "${loneCard.textContent}"`);
    lone.handle.dispose();
  }

  // A stack's guide, as the stack's page mounts it: no introduction and no overview, so it
  // opens on its first step and goes no further back; it asks the route by `stack=`, and an
  // out-of-date guide and a file no longer changed say so of the stack. A step refused for
  // the stack's own reason says it in the step's place, under the steps it keeps; a refusal
  // of the whole guide names no place, since a stack's guide has no overview (A4 of review A
  // and B2 of review B on #838).
  {
    host();
    const routes = [];
    /** What the route answers step *at* with, when it is not the stale step of the guide. */
    let refuse = (_at) => null;
    globalThis.fetch = async (route) => {
      routes.push(route);
      const at = Number(new URL(route, "http://localhost").searchParams.get("step"));
      const changed = ["src/app.txt", "gone.txt"];
      const refused = refuse(at);
      const body = refused ?? {
        ...step(1, at),
        stack: 70,
        carrier: 10,
        state: "stale",
        stale: {
          guide: { merge_base: "a".repeat(40), head: "c".repeat(40) },
          current: { merge_base: "a".repeat(40), head: "b".repeat(40) },
          github_newer: false,
          history: "rewritten",
          commit_count: 1,
          commits: [],
          changed_paths: changed,
          changed_steps: [1],
        },
      };
      return {
        ok: true,
        status: 200,
        headers: { get: () => null },
        json: async () => body,
        text: async () => JSON.stringify(body),
      };
    };
    const { mountGuidedReview } = await import(
      pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/guided-review.js")).href
    );
    const container = new Element("section");
    const view = mountGuidedReview(
      container,
      null,
      { kind: "stack", number: 70 },
      {
        open() {},
        openPull() {},
        age: () => new Element("span"),
        shortCommit: (sha) => sha.slice(0, 7),
        identity: (login) => Object.assign(new Element("span"), { textContent: login }),
        loadStyles: async () => {},
        loadDrawPatch: async () => () => ({ dispose() {} }),
        loadDrawDocument: async () => null,
        loadDrawProse: async () => null,
        refusalNote: () => null,
        // Nothing is read ahead here, so each step is read when the reader moves to it.
        ahead: () => () => {},
      },
    );
    view.show(revisionOf(1), false);
    await settle();
    const position = container.querySelector(".github-pull-guide-position").textContent;
    const rows = container
      .querySelectorAll(".github-pull-guide-steps-item")
      .map((item) => item.textContent.trim());
    const previous = [...container.descendants()].find(
      (node) => node.tag === "button" && node.getAttribute("aria-label") === "Previous step",
    );
    const warned = container.querySelector(".github-pull-guide-stale").textContent;
    const gone = container
      .querySelectorAll(".github-pull-guide-reference")
      .map((section) =>
        [...section.descendants()]
          .filter((node) => node.tag === "p")
          .map((note) => note.textContent)
          .join(" "),
      )
      .filter(Boolean);
    assert.equal(position, "Step 1 of 2");
    assert.deepEqual(rows, ["1Step 1changed", "2Step 2"], "a stack's guide lists no overview");
    assert.equal(previous.disabled, true, "nothing comes before a stack guide's first step");
    view.move(-1);
    view.go(0);
    await settle();
    assert.deepEqual(
      routes.map((route) => route.split("?")[1]),
      ["stack=70&step=1"],
    );
    steps.push(
      `a stack's guide opens on ${position}, lists ${rows.length} steps and no overview, asks ${routes.map((route) => route.split("?")[1]).join(", ")}, and goes no further back; it says "${warned}" and of a file "${gone.join(" | ")}"`,
    );
    const said = () => container.querySelector(".github-pull-quiet")?.textContent ?? "";
    const listed = () => container.querySelectorAll(".github-pull-guide-steps-item").length;
    // Step 2 read while a member is fetched: the stack's words, in the step's place.
    refuse = () => ({ state: "not_cached", record_revision: null, stack: 70, carrier: null });
    view.move(1);
    await settle();
    const fetching = said();
    assert.equal(fetching, "This stack's pull requests are still being fetched.");
    assert.equal(listed(), 2, "a refused step keeps the guide's steps");
    assert.equal(container.querySelector(".github-pull-guide-position").textContent, "Step 2 of 2");
    // The stack moved past the comparison drawn, and its carrier with it: a step that names
    // the guide's new revision is refused in words that say how to read it.
    view.behind(revisionOf(1));
    refuse = () => ({ ...step(9, 2), stack: 70, carrier: 10 });
    view.move(-1);
    view.move(1);
    await settle();
    const movedPast = said();
    assert.equal(
      movedPast,
      "This stack has moved since its comparison was drawn. Show the new comparison to read its guide.",
    );
    assert.equal(listed(), 2);
    view.dispose();

    // A guide refused whole, as a block that cannot be read is, names no place.
    refuse = () => ({
      state: "invalid",
      record_revision: revisionOf(1),
      stack: 70,
      carrier: 10,
      message: "The stack-review block cannot be read.",
    });
    // On a fresh page, whose keep holds none of the steps read above.
    guideReads.clear();
    const whole = new Element("section");
    const refusedView = mountGuidedReview(
      whole,
      null,
      { kind: "stack", number: 70 },
      {
        open() {},
        openPull() {},
        age: () => new Element("span"),
        shortCommit: (sha) => sha.slice(0, 7),
        identity: (login) => Object.assign(new Element("span"), { textContent: login }),
        loadStyles: async () => {},
        loadDrawPatch: async () => () => ({ dispose() {} }),
        loadDrawDocument: async () => null,
        loadDrawProse: async () => null,
        refusalNote: () => null,
      },
    );
    refusedView.show(revisionOf(1), false);
    await settle();
    const place = whole.querySelector(".github-pull-guide-position").textContent;
    const refusal = whole.querySelector(".github-pull-quiet")?.textContent ?? "";
    assert.equal(place, "", "a stack's guide refused whole names no place");
    assert.equal(refusal, "The stack-review block cannot be read.");
    steps.push(
      `a stack step refused while a member is fetched says "${fetching}", one whose carrier moved past the comparison drawn says "${movedPast}", and a guide refused whole names no place and says "${refusal}"`,
    );
    refusedView.dispose();
  }

  return steps;
}

module.exports = { run };
if (require.main === module) {
  run()
    .then((steps) => process.stdout.write(`${JSON.stringify(steps, null, 2)}\n`))
    .catch((error) => {
      process.stderr.write(`${error.stack}\n`);
      process.exitCode = 1;
    });
}
