// Guided Review's documents on the production pull page, guide, and diff plugin: a file a
// step names alone, of a format the diff view renders, is the diff plugin's own view of it
// (`loadRenderedFile` in builtin_plugins/diff/index.js), read from the comparison route's
// one-file answer and drawn with the options the Docs tab draws with; a range, and a whole
// file of another format, are hunks drawn by `mountFilePatch`, as before. Moving to another
// step disposes the views a step drew, a read still on its way is aborted, and its late
// answer draws nothing. The diff view itself (diff-view.js) is a recorder here: its drawing
// is its own sessions' and the Chrome check's (tests/test_github_guided_review_chrome.py).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { registerHooks } = require("node:module");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");
const { refHelpers } = require("./sdk-ref-fixture.js");

// The diff view is a recorder: what the plugin's render asks it to draw, and with which
// options. Everything above it, the plugin's routing, validation, and rendered layer, is the
// production plugin's.
registerHooks({
  load(url, context, nextLoad) {
    if (url.endsWith("/builtin_plugins/diff/diff-view.js")) {
      return {
        format: "module",
        shortCircuit: true,
        source: [
          "export const setChangeLoader = () => {};",
          "export const mountDiffSummary = () => ({ dispose() {} });",
          "export const mountDiffView = (...args) => globalThis.diffViewRecorder.mountDiffView(...args);",
          "export const mountFilePatch = (...args) => globalThis.diffViewRecorder.mountFilePatch(...args);",
        ].join("\n"),
      };
    }
    return nextLoad(url, context);
  },
});

const pagePath = path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js");
const diffPath = path.join(root, "src/metabrowser/builtin_plugins/diff/index.js");
const GUIDE_ROUTE = "/api/plugin/github/guided-review";
const FENCE = "Counts to two.\n\n```guided-review\nsoftschema: {}\n```\n";
const revisionOf = (generation) => String(generation).padStart(64, "0");
const comparisonOf = (body) => ({
  merge_base: body.record.comparison.base,
  head: body.record.comparison.head,
});

/** The pull request's envelope, with a guide, at the comparison its routes name. */
function envelope({ rendered = true } = {}) {
  const body = structuredClone(recorded.current.body);
  body.record_revision = revisionOf(1);
  body.record.pull.body = FENCE;
  body.record.issue_comments = [];
  body.record.reviews = [];
  body.record.review_comments = [];
  if (!rendered) {
    delete body.rendered_route;
  }
  return body;
}

/** One changed file as the comparison route answers it alone, valid for the plugin. */
function oneFile(filePath, id) {
  const whole = JSON.parse(
    fs.readFileSync(path.join(root, "tests/fixtures/diff-view-file-responses.json"), "utf8"),
  ).commit.body;
  const [first] = whole.manifest.files;
  const side = { ...first.new, path: filePath };
  const change = { ...first, id, old: { ...first.old, path: filePath }, new: side };
  return {
    ...whole,
    manifest: {
      ...whole.manifest,
      files: [change],
      totals: { files: 1, additions: change.additions, deletions: change.deletions, exact: true },
      truncated: false,
    },
    patches: { [id]: { ...whole.patches[first.id], file_id: id } },
  };
}

const HUNKS = [
  {
    old_start: 1,
    old_count: 1,
    new_start: 1,
    new_count: 2,
    heading: null,
    lines: [
      { op: "context", text: "# Guide" },
      { op: "add", text: "A new line." },
    ],
  },
];

/** A reference as the guided route answers it: a file named alone unless *range* says. */
function reference(filePath, { range = false, state = "ready" } = {}) {
  return {
    path: filePath,
    side: range ? "new" : null,
    start_line: range ? 1 : null,
    end_line: range ? 2 : null,
    state,
    href: state === "path_not_changed" ? null : `/pull/7/files/${filePath}`,
    hunks: state === "ready" ? HUNKS : [],
    truncated: false,
  };
}

function step(body, number, references, extra = {}) {
  return {
    state: "ready",
    record_revision: revisionOf(1),
    comparison: comparisonOf(body),
    step_count: 3,
    titles: ["Documents", "Another document", "Code"],
    step: number,
    title: `Step ${number}`,
    note: "Read it whole.",
    references,
    ...extra,
  };
}

/** The page and the production diff plugin, with every request the plugin makes recorded. */
async function harness() {
  /** What the diff view was asked to draw: each view and each patch, and whether disposed. */
  const views = [];
  const patches = [];
  globalThis.diffViewRecorder = {
    mountDiffView(container, document_, _api, options) {
      const [file] = document_.manifest.files;
      const drawn = {
        path: file.new.path,
        id: file.id,
        files: document_.manifest.files.length,
        options,
        disposed: false,
      };
      views.push(drawn);
      const rootNode = new Element("div");
      rootNode.className = "diff-root";
      rootNode.textContent = file.new.path;
      container.append(rootNode);
      return {
        dispose() {
          drawn.disposed = true;
          rootNode.remove();
        },
      };
    },
    mountFilePatch(body, change, patch) {
      const drawn = { path: change.new.path, hunks: patch.hunks.length, disposed: false };
      patches.push(drawn);
      const row = new Element("div");
      row.className = "diff-line";
      body.append(row);
      return {
        dispose() {
          drawn.disposed = true;
        },
      };
    },
  };
  /** Each request the plugin made of its routes, and a way to hold one-file answers. */
  const requests = [];
  const held = new Map();
  const hold = new Set();
  let diffView;
  const timers = new Map();
  globalThis.document = {
    visibilityState: "visible",
    addEventListener() {},
    removeEventListener() {},
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  globalThis.window = {
    location: { pathname: "/pull/7/guided" },
    METABROWSER_SETTINGS: { BUILD_TAG: "page-build", STORE_TAG: "page-store" },
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
    metabrowser: {
      registerView(_kind, _name, view) {
        diffView = view;
      },
      sourceKind: () => "git_revision",
      loadChangedFilesTree: async () =>
        require("./changed-files-tree-fixture.js").changedFilesTree(),
      async fetchPluginData(plugin, hook, params, options) {
        const request = { plugin, hook, params, signal: options?.signal };
        requests.push(request);
        if (params.view === "types") {
          return { rows: [], total: { files: 2 } };
        }
        if (params.file === undefined) {
          return oneFile("docs/guide.md", "f1");
        }
        if (hook === "pull-rendered-diff") {
          return { version: "markdown-diff-v1", status: "unsupported", blocks: [] };
        }
        const answer = oneFile(params.file, `id-${params.file}`);
        if (hold.has(params.file)) {
          return new Promise((resolve, reject) => {
            held.set(params.file, () => resolve(answer));
            options?.signal?.addEventListener("abort", () => reject(new Error("aborted")), {
              once: true,
            });
          });
        }
        return answer;
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
  const reads = [];
  let current = null;
  globalThis.fetch = async (route, init = {}) => {
    if (route.startsWith(`${GUIDE_ROUTE}?`)) {
      const asked = new URL(route, "http://localhost").searchParams;
      return new Promise((resolve, reject) => {
        const read = { step: Number(asked.get("step")), signal: init.signal };
        read.answer = (body) => resolve(response(body));
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
  const diff = await import(pathToFileURL(diffPath).href);
  const page = await import(pathToFileURL(pagePath).href);
  const { documentComparisons } = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/comparison-prefetch.js"))
      .href
  );
  return {
    views,
    patches,
    requests,
    reads,
    hold,
    /** Answer the one-file read held for *filePath*. */
    release(filePath) {
      held.get(filePath)();
    },
    /** Mount page 7 on *tab*, as the shell does at its address. */
    mount(tab, initial) {
      documentComparisons.clear();
      current = initial;
      window.location.pathname = `/pull/7/${tab}`;
      const container = new Element("main");
      const handle = page.mountPullPage(
        container,
        { number: 7, tab, reader: { initial: { etag: null, body: initial }, fetchAfterMs: 0 } },
        {
          perf,
          ensureAsset: async () => {},
          loadKpressAssets: async () => {},
          ...refHelpers(document),
          formatAge: () => ({ label: "now", className: "age" }),
          formatTimestamp: () => "now",
          navigation: { href: () => "/view/" },
          sourceKind: () => "git_revision",
          shortCommit: (commit) => commit.slice(0, 7),
          icons: { toggle: "" },
          whenIdle: () => () => {},
          ensureKindAssets: async () => {},
          getRegisteredView: () => diffView,
          plugins: {
            async load(name) {
              assert.equal(name, "diff", "the guide loads only the diff plugin");
              return diff;
            },
          },
        },
      );
      return {
        handle,
        container,
        /** Click the guide's button named *label*, as a reader does. */
        press(label) {
          [...container.descendants()]
            .find((node) => node.tag === "button" && node.getAttribute("aria-label") === label)
            .events.get("click")();
        },
        /** Each reference of the step on screen, as it is drawn. */
        drawn() {
          return container
            .querySelectorAll(".github-pull-guide-reference")
            .map((section) => {
              const note = section.children.find(
                (child) => typeof child !== "string" && child.tag === "p",
              );
              const said = note ? ` (${note.textContent})` : "";
              if (section.classes.has("github-pull-guide-document")) {
                const view = section.querySelector(".diff-root");
                return `${view?.textContent ?? "a document still loading"}: document${said}`;
              }
              const name = section.querySelector(".diff-file-path").textContent;
              return section.querySelector(".diff-line") !== null
                ? `${name}: patch${said}`
                : `${name}: says ${section.children.at(-1).textContent}`;
            })
            .join(" | ");
        },
      };
    },
  };
}

/** The one-file reads the plugin made, as their routes and paths. */
const fileReads = (requests) =>
  requests
    .filter((request) => request.params.file !== undefined && request.params.prefetch !== "1")
    .map((request) => `${request.hook} file=${request.params.file}`)
    .join(", ") || "none";

/** The options the diff view drew a mount with, by name, functions and objects by kind. */
function described(options) {
  return Object.keys(options)
    .sort()
    .map((key) => {
      const value = options[key];
      return typeof value === "function" || (typeof value === "object" && value !== null)
        ? `${key}: ${typeof value}`
        : `${key}: ${JSON.stringify(value)}`;
    })
    .join(", ");
}

async function run() {
  const steps = [];
  const world = await harness();
  const body = envelope();

  // Step 1: a Markdown and a YAML file named alone are documents, read from the comparison
  // route one file at a time; a range of the same Markdown file, a Python file named alone,
  // and a file past the step's budget draw as they did.
  {
    const view = world.mount("guided", body);
    await settle();
    world.reads
      .at(-1)
      .answer(
        step(body, 1, [
          reference("docs/guide.md"),
          reference("docs/guide.md", { range: true }),
          reference("src/app.py"),
          reference("config/settings.yaml"),
          reference("notes.md", { state: "patch_too_large" }),
        ]),
      );
    await settle();
    view.press("Next step");
    await settle();
    steps.push(`step 1 draws: ${view.drawn()}`);
    steps.push(`its one-file reads: ${fileReads(world.requests)}`);
    const comparisonRoute = new URL(body.comparison_route, "http://localhost").searchParams;
    for (const request of world.requests.filter((asked) => asked.params.file !== undefined)) {
      assert.equal(request.hook, "pull-comparison", "a document is read from the comparison");
      assert.equal(request.params.left, comparisonRoute.get("left"));
      assert.equal(request.params.right, comparisonRoute.get("right"));
      assert.equal(request.params.store, comparisonRoute.get("store"));
    }
    const [guide] = world.views;
    assert.equal(guide.files, 1, "a document's view holds its one file");
    steps.push(`a document's view is drawn with: ${described(guide.options)}`);
    // Its Rendered answer is asked by the manifest ID the one-file answer carries.
    world.requests.length = 0;
    await guide.options.renderMarkdown(guide.id, new AbortController().signal);
    steps.push(
      `its Rendered is asked of: ${world.requests.map((asked) => `${asked.hook} file=${asked.params.file}`).join(", ")}`,
    );

    // Step 2: moving on disposes every view step 1 drew. Its document's read is held, and
    // moving on again before it answers aborts it, and its late answer draws nothing.
    world.hold.add("docs/second.md");
    world.requests.length = 0;
    view.press("Next step");
    await settle();
    world.reads.at(-1).answer(step(body, 2, [reference("docs/second.md")]));
    await settle();
    steps.push(
      `step 2 disposes step 1's: ${world.views.filter((drawn) => drawn.disposed).length} of ${world.views.length} documents, ${world.patches.filter((drawn) => drawn.disposed).length} of ${world.patches.length} patches`,
    );
    steps.push(`step 2 draws, its read on its way: ${view.drawn()}`);
    const waiting = world.requests.find((asked) => asked.params.file === "docs/second.md");
    view.press("Next step");
    await settle();
    world.reads.at(-1).answer(step(body, 3, [reference("src/app.py")]));
    await settle();
    const mounted = world.views.length;
    world.release("docs/second.md");
    await settle();
    steps.push(
      `step 3 before it answered: read aborted ${waiting.signal.aborted}; views drawn after ${world.views.length - mounted}; ${view.drawn()}`,
    );
    view.handle.dispose();
  }

  // A step read at another comparison than the page's draws its document's patch, and so
  // does a step whose comparison names no rendered route.
  {
    const view = world.mount("guided", body);
    await settle();
    world.reads.at(-1).answer(
      step(body, 1, [reference("docs/guide.md")], {
        comparison: { merge_base: "c".repeat(40), head: "d".repeat(40) },
      }),
    );
    await settle();
    view.press("Next step");
    await settle();
    steps.push(`a step read at another comparison: ${view.drawn()}`);
    view.handle.dispose();
    const plain = envelope({ rendered: false });
    const without = world.mount("guided", plain);
    await settle();
    world.reads.at(-1).answer(step(plain, 1, [reference("docs/guide.md")]));
    await settle();
    without.press("Next step");
    await settle();
    steps.push(`a comparison with no rendered route: ${without.drawn()}`);
    without.handle.dispose();
  }

  // A stale guide's document that changed since says so above the document's own view.
  {
    const view = world.mount("guided", body);
    await settle();
    const pins = comparisonOf(body);
    world.reads.at(-1).answer(
      step(body, 1, [reference("docs/guide.md")], {
        state: "stale",
        stale: {
          guide: { merge_base: pins.merge_base, head: "e".repeat(40) },
          current: pins,
          github_newer: false,
          history: "ahead",
          commit_count: 1,
          commits: [],
          changed_paths: ["docs/guide.md"],
          changed_steps: [1],
        },
      }),
    );
    await settle();
    view.press("Next step");
    await settle();
    steps.push(`a changed document of a stale guide: ${view.drawn()}`);
    // Leaving the page disposes the document's view.
    const last = world.views.at(-1);
    view.handle.dispose();
    steps.push(`the page ends: its document disposed ${last.disposed}`);
  }

  // The Docs tab draws its documents with the same options, so a step's document opens as
  // Docs opens it: what Docs has that a step's document has not is Docs' own.
  {
    const docs = world.mount("docs", body);
    await settle();
    const tab = world.views.at(-1);
    const guided = world.views[0];
    assert.equal(tab.files > 0, true);
    const only = (from, to) =>
      Object.keys(from.options)
        .filter((key) => !(key in to.options))
        .sort()
        .join(", ") || "nothing";
    // Every choice is the same; what a mount is handed (its layer, its loaders) is its own.
    for (const key of Object.keys(guided.options)) {
      const value = guided.options[key];
      if (key in tab.options && typeof value !== "function" && typeof value !== "object") {
        assert.equal(value, tab.options[key], `${key} differs from Docs'`);
      }
    }
    assert.equal(guided.options.markdownViews, tab.options.markdownViews, "one rendered layer");
    steps.push(`Docs has, and a step's document has not: ${only(tab, guided)}`);
    steps.push(`a step's document has, and Docs has not: ${only(guided, tab)}`);
    docs.handle.dispose();
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
