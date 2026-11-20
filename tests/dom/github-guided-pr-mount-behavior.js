// Guided PR on the production pull page: its guide is imported and mounted only when its tab
// first paints, a tab left while the import is on its way mounts nothing, a new record revision
// asks again for the step on screen and drops the read still on its way, leaving the tab or
// ending the page disposes the view and aborts its read, and a step is inserted as text, each
// row's code marked for the shell's highlighter to skip. The navigation state machine itself is
// pinned in github-guided-pr-session.js; this is the page's ownership of it. Layout is not
// measured: the shell's highlighting and the rows' paint are Chrome's
// (tests/test_github_guided_pr_chrome.py).
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");
const { refHelpers } = require("./sdk-ref-fixture.js");

const pagePath = path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js");
const GUIDE_ROUTE = "/api/plugin/github/guided-pr";
const FENCE = "Counts to two.\n\n```guided-pr\nsoftschema: {}\n```\n";

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

/** One step as the route answers it: a context, a deleted and an added row, and a path the
 * comparison does not have. Its text is markup, which a page that inserted it as HTML would
 * draw as elements. */
function step(generation, number, count = 2) {
  const rows = [
    { old: 1, new: 1, op: "context", text: "one" },
    { old: 2, new: null, op: "del", text: "<i>two</i>" },
    { old: null, new: 2, op: "add", text: "three" },
  ];
  return {
    state: "ready",
    record_revision: revisionOf(generation),
    feature: "Teach the app to <b>count</b>.",
    architecture: "Two files.\nThe count and its words.",
    comparison: { merge_base: "a".repeat(40), head: "b".repeat(40) },
    step_count: count,
    step: number,
    title: `Step ${number}`,
    commentary: "Check <b>this</b> first.\nThen that.",
    references: [
      {
        path: "src/app.txt",
        side: "new",
        start_line: 1,
        end_line: 2,
        state: "ready",
        href: "/pull/7/files/src/app.txt",
        rows,
      },
      {
        path: "gone.txt",
        side: null,
        start_line: null,
        end_line: null,
        state: "path_not_changed",
        href: null,
        rows: [],
      },
    ],
  };
}

function host() {
  const timers = new Map();
  /** Each read of the guide: its step, its signal, and the answer or failure that ends it. */
  const reads = [];
  /** The routes the page asked the page to open. */
  const opened = [];
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
    MetabrowserInertHtml: {
      sanitizeHtml: (html) => html,
      kpressProse(html) {
        const node = document.createElement("p");
        node.textContent = html;
        return node;
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
          formatAge: () => ({ label: "now", className: "age" }),
          formatTimestamp: () => "now",
          navigation: { href: () => "/view/" },
          sourceKind: () => "git_revision",
          icons: { toggle: "" },
        },
      );
      return {
        handle,
        container,
        /** The route arrives at *next*, as the shell's does: the address, then the page. */
        arrive(next) {
          window.location.pathname = next === "" ? "/pull/7" : `/pull/7/${next}`;
          handle.setTab(next);
        },
        guided: () => container.querySelector(".github-pull-guided-pr"),
        /** The step on screen, as the reader sees it, or null while there is none. */
        shown() {
          const title = container
            .querySelector(".github-pull-guide-step")
            ?.querySelector(".section-heading");
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

const asked = (reads) => reads.map((read) => `step ${read.step}`).join(", ") || "nothing";

async function run() {
  const page = await import(pathToFileURL(pagePath).href);
  const steps = [];

  // Lazy mount: Conversation never reads the guide, and its tab mounts it at first paint.
  {
    const first = host();
    const view = first.mount(page, "", envelope(1));
    await settle();
    steps.push(
      `Conversation: guide ${view.guided() === null ? "not mounted" : "mounted"}; asked ${asked(first.reads)}`,
    );
    view.arrive("guided");
    await settle();
    assert.equal(first.pending().length, 1);
    steps.push(`its tab opens: guide mounted; asked ${asked(first.reads)}`);

    // A step is text, not markup, and each row's code is marked for the highlighter to skip.
    first.pending()[0].answer(step(1, 1));
    await settle();
    const commentary = view.container.querySelector(".github-pull-guide-commentary");
    assert.equal(commentary.textContent, "Check <b>this</b> first.\nThen that.");
    assert.ok(
      commentary.children.every((child) => typeof child === "string"),
      "the commentary holds text and no element",
    );
    const lines = view.container.querySelectorAll(".github-pull-guide-line");
    steps.push(
      `step 1: ${view.shown()}; rows ${lines
        .map((line) => {
          const code = line.children.find((child) => child.tag === "code");
          assert.ok(code.classes.has("no-highlight"), "a row's code is skipped by the highlighter");
          assert.ok(
            code.children.every((child) => typeof child === "string"),
            "a row's code holds text and no element",
          );
          return `${line.dataset.op} ${code.textContent}`;
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

    // Next asks for step 2 alone; leaving the tab with that read on its way disposes the
    // view and aborts the read, and its late answer paints nothing.
    [...view.container.descendants()]
      .find((node) => node.tag === "button" && node.textContent === "Next")
      .events.get("click")();
    await settle();
    const second = first.pending()[0];
    assert.equal(second.step, 2);
    view.arrive("");
    await settle();
    steps.push(
      `left for Conversation with step 2 on its way: read aborted ${second.signal.aborted}; guide ${view.guided() === null ? "gone" : "still there"}`,
    );
    second.answer?.(step(1, 2));
    await settle();
    assert.equal(view.guided(), null);

    // Back on the tab, a view of its own is mounted again, from step 1.
    view.arrive("guided");
    await settle();
    steps.push(`its tab again: asked ${asked(first.reads.slice(2))}`);

    // The page ends with a read on its way: the read is aborted.
    const waiting = first.pending()[0];
    view.handle.dispose();
    steps.push(`the page ends: read aborted ${waiting.signal.aborted}`);
  }

  // Replacement: a new record revision asks for the step on screen again, and drops the read
  // on its way; the late answer to the dropped read paints nothing.
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
    steps.push(`the new read's answer: ${view.shown()}`);
    // A poll that finds the same record asks for nothing.
    await second.poll();
    steps.push(`a poll of the same record: asked ${asked(second.reads)}`);
    view.handle.dispose();
  }

  // A tab left while the import is on its way mounts nothing, and neither does a page that
  // ends there: each is a view that nothing disposes if it were mounted late.
  {
    const third = host();
    const view = third.mount(page, "", envelope(1));
    await settle();
    view.arrive("guided");
    view.arrive("");
    await settle();
    steps.push(
      `Guided PR opened and left before its import settled: guide ${view.guided() === null ? "not mounted" : "mounted"}; asked ${asked(third.reads)}`,
    );
    view.arrive("guided");
    view.handle.dispose();
    await settle();
    steps.push(`the page ended before the import settled: asked ${asked(third.reads)}`);
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
