// Guided Review's documents on the production pull page, guide, and diff plugin: a file a
// step names alone that the guided route answers `rendered` (a file the rendered route
// renders, by its own rule) is the diff plugin's own view of it (`mountRenderedFile` in
// builtin_plugins/diff/index.js), read from the comparison route's one-file answer: a
// Markdown file drawn with the options the Docs tab draws with, and a YAML or JSON file with
// the options Changes draws with. A range, and a whole file the route answers with its
// hunks, are drawn by `mountFilePatch`, as before. Moving to another step disposes the
// views a step drew, a read still on its way is aborted, and its late answer draws nothing.
// A document the view could not draw keeps the guide's bar for it above the view's notice.
// The diff view itself (diff-view.js) is a recorder here: its drawing is its own sessions'
// and the Chrome check's (tests/test_github_guided_review_chrome.py).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { registerHooks } = require("node:module");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");
const { agesFrom, refHelpers } = require("./sdk-ref-fixture.js");

// The diff view is a recorder: what the plugin's render asks it to draw, and with which
// options. Everything above it, the plugin's routing, validation, and rendered layer, is the
// production plugin's.
// Which of the diff plugin's on-demand modules a session has loaded, by file name.
const loadedModules = new Set();
registerHooks({
  load(url, context, nextLoad) {
    if (url.includes("/builtin_plugins/diff/")) {
      loadedModules.add(url.slice(url.lastIndexOf("/") + 1));
    }
    if (url.endsWith("/builtin_plugins/diff/diff-view.js")) {
      return {
        format: "module",
        shortCircuit: true,
        source: [
          "export const setChangeLoader = () => {};",
          "export const setGapLoader = () => {};",
          "export const fileDisclosure = (...args) => globalThis.diffViewRecorder.fileDisclosure(...args);",
          "export const presentationControlHtml = () => '';",
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

/**
 * A reference as the guided route answers it: a file named alone unless *range* says, its
 * hunks unless the route answers the format it renders in (*rendered*), which has none.
 */
function reference(filePath, { range = false, state = "ready", rendered = null } = {}) {
  return {
    kind: "file",
    path: filePath,
    side: range ? "new" : null,
    start_line: range ? 1 : null,
    end_line: range ? 2 : null,
    pull: null,
    commit: null,
    state,
    rendered,
    href: state === "path_not_changed" ? null : `/pull/7/files/${filePath}`,
    hunks: state === "ready" && rendered === null ? HUNKS : [],
    truncated: false,
    comparison: null,
    target: null,
  };
}

/**
 * A Markdown file of pull request 10, which a step cites as `{pull: 10, path}`: the guided
 * route answers that pull request's comparison and the routes that answer it, which are not
 * the page's.
 */
function otherDocument(filePath) {
  const [left, right] = ["1".repeat(40), "2".repeat(40)];
  const pair = `number=10&left=${left}&right=${right}`;
  return {
    ...reference(filePath, { rendered: "markdown" }),
    kind: "pull_file",
    pull: 10,
    href: `/pull/10/files/${filePath}`,
    comparison: {
      merge_base: left,
      head: right,
      route: `/api/plugin/github/pull-comparison?${pair}&base_policy=merge_base&build=page-build&store=page-store`,
      image_route: `/api/plugin/github/pull-image?${pair}&store=page-store`,
      rendered_route: `/api/plugin/github/pull-rendered-diff?${pair}&store=page-store`,
    },
  };
}
const markdown = (filePath) => reference(filePath, { rendered: "markdown" });

function step(body, number, references, extra = {}) {
  return {
    state: "ready",
    record_revision: revisionOf(1),
    comparison: comparisonOf(body),
    step_count: 3,
    titles: ["Documents", "Another document", "Code"],
    outline: ["Documents", "Another document", "Code"].map((title, index) => ({
      kind: "step",
      step: index + 1,
      title,
    })),
    group: null,
    step: number,
    title: `Step ${number}`,
    note: "Read it whole.",
    references,
    ...extra,
  };
}

/** The page and the production diff plugin, with every request the plugin makes recorded. */
async function harness() {
  // The diff plugin's own bar and chevron, which a patch hands the card drawn around it;
  // the query passes the stand-in for diff-view.js above.
  const { fileDisclosure } = await import(
    `${pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/diff/diff-view.js")).href}?own`
  );
  /** What the diff view was asked to draw: each view and each patch, and whether disposed. */
  const views = [];
  const patches = [];
  /** Files whose view throws as it mounts, and files whose one-file read fails. */
  const failing = new Set();
  const refused = new Set();
  globalThis.diffViewRecorder = {
    mountDiffView(container, document_, _api, options) {
      const [file] = document_.manifest.files;
      if (failing.has(file.new.path)) {
        throw new Error(`the view of ${file.new.path} threw`);
      }
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
        currentFile: () => null,
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
    // The diff view's own builder of a card's bar, which the real index.js hands the guide.
    fileDisclosure,
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
      // The File type menu a page with Changes has, so a diff of more than one file would
      // load its filter.
      filterControls: { typeMenu: {}, bind: () => () => {} },
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
        if (refused.has(params.file)) {
          throw Object.assign(new Error("the comparison route failed"), { status: 503 });
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
    // The guide reads its answer as text, whose length it keeps (guide-reads.js).
    text: async () => JSON.stringify(body),
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
  const { guideReads } = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/guide-reads.js")).href
  );
  return {
    views,
    patches,
    requests,
    reads,
    hold,
    failing,
    refused,
    /** Answer the one-file read held for *filePath*. */
    release(filePath) {
      hold.delete(filePath);
      held.get(filePath)();
    },
    /** Mount page 7 on *tab*, as the shell does at its address. */
    mount(tab, initial) {
      documentComparisons.clear();
      guideReads.clear();
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
          ...agesFrom(document, () => ({ label: "now", className: "age" })),
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
        /** Whether a step waits out of sight to show whole in the place of the one shown. */
        incoming() {
          return container.querySelector(".github-pull-guide-incoming") !== null;
        },
        /** Whether the arrows' delayed mark is set to show, saying a step is on its way. */
        marked() {
          return container.querySelector(".github-pull-guide-waiting")?.hidden === false;
        },
        /** The arrows a reader can press, by label. */
        pressable() {
          const arrows = [...container.descendants()].filter(
            (node) =>
              node.tag === "button" &&
              ["Previous step", "Next step"].includes(node.getAttribute("aria-label")) &&
              node.disabled !== true,
          );
          return arrows.map((node) => node.getAttribute("aria-label")).join(" and ") || "none";
        },
        /** Each reference of the step on screen, as it is drawn: not a step that waits. */
        drawn() {
          const shown = container
            .querySelectorAll(".github-pull-guide-step")
            .find((detail) => !detail.classes.has("github-pull-guide-incoming"));
          return (shown?.querySelectorAll(".github-pull-guide-reference") ?? [])
            .map((section) => {
              const note = section.children.find(
                (child) => typeof child !== "string" && child.tag === "p",
              );
              const said = note ? ` (${note.textContent})` : "";
              if (section.classes.has("github-pull-guide-document")) {
                const view = section.querySelector(".diff-root");
                const failure = section.querySelector(".diff-notice");
                if (view !== null) {
                  return `${view.textContent}: document${said}`;
                }
                if (failure !== null) {
                  const bar = section.querySelector(".github-pull-guide-reference-header");
                  const name = bar?.querySelector(".diff-file-path")?.textContent ?? "no name";
                  const full = bar?.querySelector(".diff-file-view")?.href;
                  return `${name}: document says ${failure.textContent} (its bar opens ${full ?? "nothing"})${said}`;
                }
                return `a document still loading${said}`;
              }
              const pull = section.querySelector(".github-pull-guide-reference-pull");
              const name = `${pull === null ? "" : `${pull.textContent} `}${section.querySelector(".diff-file-path").textContent}`;
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

/**
 * What a tab's own view has that a step's document has not, and the other way round, after
 * checking that every choice both make is the same, but for how long Rendered waits: what a
 * mount is handed (its layer, its loaders) is its own, and a step's document waits for its
 * rendering for as long as the route can take, since the step shows only once its documents
 * are drawn as they stay (`GUIDE_DOCUMENT_HOLD_MS` in guide-reads.js), where a tab waits
 * for its first screen only as long as Changes does.
 */
function compared(tab, drawn) {
  const only = (from, to) =>
    Object.keys(from.options)
      .filter((key) => !(key in to.options))
      .sort()
      .join(", ") || "nothing";
  for (const key of Object.keys(drawn.options)) {
    const value = drawn.options[key];
    if (
      key in tab.options &&
      key !== "markdownHoldMs" &&
      typeof value !== "function" &&
      typeof value !== "object"
    ) {
      assert.equal(value, tab.options[key], `${key} differs from the tab's`);
    }
  }
  assert.equal(drawn.options.markdownViews, tab.options.markdownViews, "one rendered layer");
  return [only(tab, drawn), only(drawn, tab)];
}

/** Mount the guide, answer its overview with *answer*, and open its first step. */
async function opened(world, body, answer) {
  const view = world.mount("guided", body);
  await settle();
  world.reads.at(-1).answer(answer);
  await settle();
  view.press("Next step");
  await settle();
  return view;
}

async function run() {
  const steps = [];
  const world = await harness();
  const body = envelope();
  const pins = comparisonOf(body);

  // A step that cites no file the rendered route renders never loads the rendered layer.
  {
    const view = await opened(world, body, step(body, 1, [reference("src/app.py")]));
    steps.push(
      `a step of patches alone: ${view.drawn()}; the rendered layer loaded ${loadedModules.has("diff-markdown.js")}`,
    );
    view.handle.dispose();
  }

  // Step 1: a Markdown and a YAML file the route answers `rendered` are documents, read from
  // the comparison route one file at a time; a range of the same Markdown file, a Python file
  // named alone, and a file past the step's budget draw as they did.
  {
    const firstPatch = world.patches.length;
    const view = world.mount("guided", body);
    await settle();
    world.requests.length = 0;
    world.reads
      .at(-1)
      .answer(
        step(body, 1, [
          markdown("docs/guide.md"),
          reference("docs/guide.md", { range: true }),
          reference("src/app.py"),
          reference("config/settings.yaml", { rendered: "yaml" }),
          reference("notes.md", { state: "patch_too_large" }),
        ]),
      );
    await settle();
    view.press("Next step");
    await settle();
    steps.push(`step 1 draws: ${view.drawn()}`);
    steps.push(`its one-file reads: ${fileReads(world.requests)}`);
    // They load the rendered layer, and not the File type filter, which only a diff of more
    // than one file draws, so they ask for no type counts either.
    steps.push(
      `its documents load the rendered layer ${loadedModules.has("diff-markdown.js")}, the File type filter ${loadedModules.has("diff-type-filter.js")}`,
    );
    steps.push(
      `its documents' other reads: ${
        world.requests
          .filter((asked) => asked.params.file === undefined)
          .map((asked) => `${asked.hook} ${JSON.stringify(asked.params)}`)
          .join(", ") || "none"
      }`,
    );
    const comparisonRoute = new URL(body.comparison_route, "http://localhost").searchParams;
    for (const request of world.requests.filter((asked) => asked.params.file !== undefined)) {
      assert.equal(request.hook, "pull-comparison", "a document is read from the comparison");
      assert.equal(request.params.left, comparisonRoute.get("left"));
      assert.equal(request.params.right, comparisonRoute.get("right"));
      assert.equal(request.params.store, comparisonRoute.get("store"));
    }
    const guide = world.views.find((drawn) => drawn.path === "docs/guide.md");
    const settings = world.views.find((drawn) => drawn.path === "config/settings.yaml");
    assert.equal(guide.files, 1, "a document's view holds its one file");
    steps.push(`a Markdown document's view is drawn with: ${described(guide.options)}`);
    steps.push(`a YAML document's view is drawn with: ${described(settings.options)}`);
    // Its Rendered is asked by the manifest ID the one-file answer carries.
    world.requests.length = 0;
    await guide.options.renderMarkdown(guide.id, new AbortController().signal);
    steps.push(
      `its Rendered is asked of: ${world.requests.map((asked) => `${asked.hook} file=${asked.params.file}`).join(", ")}`,
    );

    // Step 2's document's read is held: step 2 is drawn out of sight, and step 1 stays on
    // screen, every view it drew with it, until step 2 can show whole. Moving on again before
    // the document answers withdraws step 2, which aborts its read, and step 3 shows in step
    // 1's place, which disposes step 1's views; the late answer draws nothing.
    world.hold.add("docs/second.md");
    world.requests.length = 0;
    const before = world.views.length;
    const drawnPatches = world.patches.slice(firstPatch);
    view.press("Next step");
    await settle();
    world.reads.at(-1).answer(step(body, 2, [markdown("docs/second.md")]));
    await settle();
    const disposedViews = () => world.views.slice(0, before).filter((drawn) => drawn.disposed);
    steps.push(
      `step 2 waits for its document: a step waits out of sight ${view.incoming()}, the arrows' mark shows ${view.marked()}; step 1's disposed: ${disposedViews().length} of ${before} documents, ${drawnPatches.filter((drawn) => drawn.disposed).length} of ${drawnPatches.length} patches`,
    );
    steps.push(`on screen meanwhile: ${view.drawn()}`);
    const waiting = world.requests.find((asked) => asked.params.file === "docs/second.md");
    view.press("Next step");
    await settle();
    world.reads.at(-1).answer(step(body, 3, [reference("src/app.py")]));
    await settle();
    const mounted = world.views.length;
    world.release("docs/second.md");
    await settle();
    steps.push(
      `step 3 before it answered: read aborted ${waiting.signal.aborted}; views drawn after ${world.views.length - mounted}; step 1's disposed: ${disposedViews().length} of ${before} documents, ${drawnPatches.filter((drawn) => drawn.disposed).length} of ${drawnPatches.length} patches; ${view.drawn()}`,
    );
    view.handle.dispose();
  }

  // A step whose document's read is held shows only once the document is drawn: the
  // overview stays until then, and the step never shows with a document still to come.
  // Meanwhile the arrows move on from the step the reader went to, as while a step is read,
  // so Previous goes back to the overview.
  {
    world.hold.add("docs/held.md");
    const view = await opened(world, body, step(body, 1, [markdown("docs/held.md")]));
    const held = `${view.drawn() || "nothing"}, a step waits out of sight ${view.incoming()}, the arrows' mark shows ${view.marked()}, the arrows to press ${view.pressable()}`;
    world.release("docs/held.md");
    await settle();
    steps.push(
      `a held document: while its read is held, the step shows ${held}; once drawn, ${view.drawn()}, a step waits ${view.incoming()}, the arrows' mark shows ${view.marked()}`,
    );
    view.handle.dispose();
  }

  // The page draws a document only at the comparison the step was read at: a step read at
  // another merge base, or at another head, says the file's diff is unavailable instead. A
  // comparison that names no rendered route still draws it, without the rendered layer.
  {
    for (const [label, comparison] of [
      ["another merge base", { merge_base: "c".repeat(40), head: pins.head }],
      ["another head", { merge_base: pins.merge_base, head: "d".repeat(40) }],
    ]) {
      const view = await opened(
        world,
        body,
        step(body, 1, [markdown("docs/guide.md")], { comparison }),
      );
      steps.push(`a step read at ${label}: ${view.drawn()}`);
      view.handle.dispose();
    }
    const plain = envelope({ rendered: false });
    const without = await opened(world, plain, step(plain, 1, [markdown("docs/guide.md")]));
    const drawn = world.views.at(-1);
    steps.push(
      `a comparison with no rendered route: ${without.drawn()}, its rendered layer ${"markdownViews" in drawn.options ? "drawn" : "absent"}`,
    );
    without.handle.dispose();
  }

  // A document of another pull request is drawn from that pull request's own comparison,
  // whose routes the step's answer names: its one-file read and its Rendered go to pull
  // request 10's routes. It draws in a step read at another comparison than the page's,
  // where a document of this pull request says its diff is unavailable.
  {
    world.requests.length = 0;
    const view = await opened(
      world,
      body,
      step(body, 1, [otherDocument("docs/draft.md"), markdown("docs/guide.md")], {
        comparison: { merge_base: "c".repeat(40), head: pins.head },
      }),
    );
    steps.push(`another pull request's document, at another comparison: ${view.drawn()}`);
    const reads = world.requests.filter((asked) => asked.params.file !== undefined);
    steps.push(
      `its one-file read: ${reads.map((asked) => `${asked.hook} number=${asked.params.number} left=${asked.params.left.slice(0, 4)} file=${asked.params.file}`).join(", ")}`,
    );
    const drawn = world.views.find((shown) => shown.path === "docs/draft.md" && !shown.disposed);
    world.requests.length = 0;
    await drawn.options.renderMarkdown(drawn.id, new AbortController().signal);
    steps.push(
      `its Rendered is asked of: ${world.requests.map((asked) => `${asked.hook} number=${asked.params.number}`).join(", ")}`,
    );
    view.handle.dispose();
  }

  // A document whose view could not draw it keeps the guide's bar for it, with its name and
  // its Open full diff, above the view's notice: a view that threw as it mounted, and a
  // one-file read that failed, which the view's render says in its place.
  {
    world.failing.add("docs/threw.md");
    world.refused.add("docs/refused.md");
    // The console's errors, which both failures log: kept, so they do not read as a fault.
    const logged = [];
    const consoleError = console.error;
    console.error = (...args) => logged.push(args);
    try {
      const view = await opened(
        world,
        body,
        step(body, 1, [markdown("docs/threw.md"), markdown("docs/refused.md")]),
      );
      steps.push(`documents that could not be drawn: ${view.drawn()}`);
      steps.push(`their failures are logged: ${logged.length}`);
      const notices = view.container.querySelectorAll(".diff-notice");
      view.handle.dispose();
      steps.push(
        `the page ends: ${notices.filter((notice) => notice.parentNode !== null).length} of ${notices.length} notices left`,
      );
    } finally {
      console.error = consoleError;
    }
  }

  // A stale guide's document that changed since says so above the document's own view.
  {
    const view = await opened(
      world,
      body,
      step(body, 1, [markdown("docs/guide.md")], {
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
    steps.push(`a changed document of a stale guide: ${view.drawn()}`);
    // Leaving the page disposes the document's view.
    const last = world.views.at(-1);
    view.handle.dispose();
    steps.push(`the page ends: its document disposed ${last.disposed}`);
  }

  // The Docs tab draws its documents with the options a step's Markdown document has, and
  // Changes its files with those a step's YAML document has: what the tab has that the step
  // has not is the tab's own.
  {
    const markdownDocument = world.views.find((drawn) => drawn.path === "docs/guide.md");
    const yamlDocument = world.views.find((drawn) => drawn.path === "config/settings.yaml");
    for (const [tab, name, drawn] of [
      ["docs", "Docs", markdownDocument],
      ["files", "Changes", yamlDocument],
    ]) {
      const shown = world.mount(tab, body);
      await settle();
      const own = world.views.at(-1);
      assert.equal(own.files > 0, true);
      assert.notEqual(own, drawn);
      const [tabOnly, drawnOnly] = compared(own, drawn);
      steps.push(`${name} has, and a step's ${drawn.path} has not: ${tabOnly}`);
      steps.push(`a step's ${drawn.path} has, and ${name} has not: ${drawnOnly}`);
      shown.handle.dispose();
    }
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
