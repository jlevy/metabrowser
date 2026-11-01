// Browserless session: what File Overview shows for each answer the rollup can give.
//
// File Overview is a totals table above a type distribution, and the distribution's
// rollup drives both. Totals that were still pending when a rollup failed, or answered
// with none, used to stay a loading skeleton forever (mb-8wwl), and changing a control
// after a failure brought the distribution's skeleton back over the error.
//
// The panel, its bodies, the rollup controls, the projection, the distribution model and
// view, and the inventory watch are the production modules, loaded whole. The document
// is a stand-in for the few calls they make, and `mb.watchRollup` is the SDK's, whose
// `fetch` here answers what each step says instead of asking a server: the rollups below
// have the shape `/api/rollup` answers, which cli-api.tryscript.md pins.
//
// Each step prints what is on screen: the totals, the distribution's text, and whether
// it offers Retry. Exits 1 on a failed invariant.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const sourceRoot = path.join(repoRoot, "src/metabrowser");

// The folder plugin's modules have no package.json saying they are modules, which the
// browser never asks about. Node's warning names the process and the checkout, so it is
// kept out of the transcript.
const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    return;
  }
  emitWarning.call(process, warning, ...rest);
};

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

class FakeElement {
  constructor(tag) {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.className = "";
    this.dataset = {};
    this.style = {};
    this.attributes = {};
    this.listeners = {};
    this.hidden = false;
    this.ownText = "";
    this.html = "";
    this.classList = {
      add: (...names) => {
        this.className = [...new Set([...this.className.split(" "), ...names])]
          .filter(Boolean)
          .join(" ");
      },
      remove: (...names) => {
        this.className = this.className
          .split(" ")
          .filter((name) => !names.includes(name))
          .join(" ");
      },
      toggle: (name, on) => (on ? this.classList.add(name) : this.classList.remove(name)),
      contains: (name) => this.className.split(" ").includes(name),
    };
  }
  append(...children) {
    for (const child of children) {
      child.remove();
      child.parentNode = this;
      this.children.push(child);
    }
  }
  replaceChildren(...children) {
    this.children = [];
    this.html = "";
    this.ownText = "";
    this.append(...children);
  }
  remove() {
    if (this.parentNode) {
      this.parentNode.children = this.parentNode.children.filter((child) => child !== this);
    }
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  removeAttribute(name) {
    delete this.attributes[name];
  }
  addEventListener(type, listener) {
    this.listeners[type] = listener;
  }
  closest() {
    return null;
  }
  descendants() {
    return this.children.flatMap((child) => [child, ...child.descendants()]);
  }
  set innerHTML(value) {
    this.html = value;
    this.children = [];
    this.ownText = "";
  }
  get innerHTML() {
    return this.html;
  }
  set textContent(value) {
    this.ownText = String(value);
    this.children = [];
    this.html = "";
  }
  /** What a sighted reader sees: nothing hidden and nothing for screen readers only. */
  get textContent() {
    const visible = this.children.filter(
      (child) => !child.hidden && !child.classList.contains("sr-only"),
    );
    return [
      this.ownText,
      this.html.replace(/<span class="sr-only">.*?<\/span>/g, "").replace(/<[^>]*>/g, ""),
      ...visible.map((child) => child.textContent),
    ]
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
  }
  querySelector(selector) {
    if (selector.startsWith(".")) {
      const name = selector.slice(1);
      return this.descendants().find((element) => element.classList.contains(name)) ?? null;
    }
    const attribute = /^\[([\w-]+)\]$/.exec(selector);
    if (attribute && this.html.includes(attribute[1])) {
      this.markupControl ??= new FakeElement("button");
      return this.markupControl;
    }
    return null;
  }
}

const windowListeners = new Map();
global.window = globalThis;
global.addEventListener = (type, listener) => windowListeners.set(type, listener);
global.removeEventListener = () => {};
global.document = { createElement: (tag) => new FakeElement(tag) };
global.METABROWSER_SETTINGS = {};
const originalWarn = console.warn;
console.warn = () => {};

const FAMILY_FILES = { all: { files: 3, bytes: 3000 }, unignored: { files: 2, bytes: 2000 } };
const ZERO = { all: { files: 0, bytes: 0 }, unignored: { files: 0, bytes: 0 } };

/** A rollup with the shape /api/rollup answers: one family, two files plus one ignored. */
const COMPLETE_ROLLUP = {
  path: "docs",
  index_status: "done",
  indexed_files: 3,
  max_files: 500000,
  truncated: false,
  file_type_breakdown: {
    schema: "file-type-breakdown-v1",
    registry: { schema_version: 1, revision: 1, fingerprint: "session" },
    metrics: FAMILY_FILES,
    groups: [
      {
        id: "code",
        families: [
          {
            id: "python",
            metrics: FAMILY_FILES,
            extensions: [{ extension: ".py", metrics: FAMILY_FILES }],
          },
        ],
      },
    ],
    no_extension: { metrics: ZERO, filenames: [], others: null },
    remaining_types: { metrics: ZERO, extensions: [], others: null },
  },
};

const FILE_TYPES = {
  schemaVersion: 1,
  revision: 1,
  fingerprint: "session",
  groups: [
    { id: "code", label: "Code" },
    { id: "other", label: "Other" },
  ],
  families: [{ id: "python", label: "Python", groupId: "code", extensions: [".py"] }],
};

const rollupError = (status) =>
  new window.MetabrowserRequestErrors.RequestError("Could not load folder totals.", {
    operation: "fetchRollup",
    status,
  });

(async () => {
  require(path.join(sourceRoot, "static/request-error.js"));
  require(path.join(sourceRoot, "static/inventory-scope.js"));
  const folder = (name) =>
    pathToFileURL(path.join(sourceRoot, "builtin_plugins/folder", name)).href;
  const { mountFileOverviewPanel } = await import(folder("file-overview-panel.js"));
  const { createFolderRollupControls } = await import(folder("rollup-controls.js"));
  const { createFolderRollupProjectionPool } = await import(folder("rollup-projection.js"));

  /** One mounted panel for a folder whose envelope carries `dir`, and its next rollup. */
  function page(dir, firstAnswer) {
    const answers = { next: firstAnswer };
    let requests = 0;
    const mb = {
      countClass: () => "",
      directoryTotals: { subscribe: () => () => {} },
      errors: window.MetabrowserRequestErrors,
      escapeHtml: String,
      fileTypeIcon: () => ({ className: "", svg: "" }),
      fileTypes: FILE_TYPES,
      filterControls: { bind: () => () => {}, checkHtml: () => "", groupHtml: () => "" },
      formatFileCount: (value) => `${value.toLocaleString("en-US")} files`,
      formatInteger: (value) => value.toLocaleString("en-US"),
      formatSize: (value) => `${value.toLocaleString("en-US")} B`,
      prefs: { get: () => null, set() {} },
      sizeClass: () => "",
      tooltip: { hide() {}, show() {} },
      viewState: { isActive: () => true, subscribeActive: () => () => {} },
      watchRollup: (scope, options, onUpdate) =>
        window.MetabrowserInventoryScope.createInventoryWatch(
          scope,
          {
            active: options.active,
            debounceMs: 0,
            fetch: async () => {
              requests += 1;
              const answer = answers.next;
              if (answer instanceof Error) {
                throw answer;
              }
              return JSON.parse(JSON.stringify(answer));
            },
            onError: options.onError,
          },
          onUpdate,
        ),
    };
    const controls = createFolderRollupControls(mb);
    const container = new FakeElement("div");
    const palette = { classFor: () => "", paint() {}, styleFor: () => "" };
    const panel = mountFileOverviewPanel(
      container,
      { path: "docs", raw: { dir } },
      mb,
      palette,
      createFolderRollupProjectionPool(),
      controls,
      {},
    );
    const settle = () => new Promise((resolve) => setImmediate(resolve));
    const totals = () => container.querySelector(".folder-totals");
    const summary = () => container.querySelector(".file-type-summary-body");
    return {
      answers,
      controls,
      panel,
      requests: () => requests,
      settle,
      read() {
        const shownTotals = totals();
        return {
          totals: shownTotals.html.includes("folder-totals-loading")
            ? "skeleton"
            : shownTotals.querySelector(".folder-totals-table")
              ? shownTotals.textContent
              : "nothing",
          distribution: summary().querySelector(".file-type-summary-skeleton")
            ? "skeleton"
            : summary().textContent,
          retry: summary().html.includes("data-file-types-retry"),
        };
      },
      retry() {
        summary().querySelector("[data-file-types-retry]").listeners.click();
      },
      /** The event the inventory stream sends, past the watch's debounce of zero. */
      async inventoryChanged() {
        windowListeners.get("metabrowser:inventory-change")(
          new CustomEvent("metabrowser:inventory-change", { detail: { paths: ["docs/a.py"] } }),
        );
        await new Promise((resolve) => setTimeout(resolve, 1));
        await settle();
      },
    };
  }

  const PENDING_DIR = {
    total_files: null,
    total_size: null,
    unignored_files: null,
    unignored_size: null,
    state: "pending",
  };
  const COMPLETE_DIR = {
    total_files: 3,
    total_size: 3000,
    unignored_files: 2,
    unignored_size: 2000,
    state: "complete",
  };
  const transcript = {};
  const noSkeleton = (shown, step) =>
    assert(
      shown.totals !== "skeleton" && shown.distribution !== "skeleton",
      `${step} left a skeleton: ${JSON.stringify(shown)}`,
    );

  // A refused rollup: a folder gone, or one the inventory holds no directory for.
  {
    const view = page(PENDING_DIR, rollupError(404));
    await view.settle();
    const refused = view.read();
    noSkeleton(refused, "a refused rollup");
    assert(!refused.retry, "a refused rollup offered Retry");
    view.controls.set({ metric: "size" });
    view.controls.set({ includeIgnored: false });
    const afterControls = view.read();
    noSkeleton(afterControls, "a control change after a refused rollup");
    assert(
      afterControls.distribution === refused.distribution,
      "a control change replaced the failure's message",
    );
    transcript["a refused rollup finishes both bodies"] = { refused, afterControls };
    view.panel.dispose();
  }

  // A failed request offers Retry, and a retry that succeeds shows everything.
  {
    const view = page(PENDING_DIR, rollupError(500));
    await view.settle();
    const failed = view.read();
    noSkeleton(failed, "a failed rollup");
    assert(failed.retry, "a failed rollup did not offer Retry");
    view.answers.next = COMPLETE_ROLLUP;
    view.retry();
    await view.settle();
    const retried = view.read();
    assert(retried.totals.includes("Files"), "a retry did not bring the totals");
    assert(retried.distribution.includes("Python"), "a retry did not bring the distribution");
    assert(view.requests() === 2, `a retry made ${view.requests()} requests`);
    transcript["a failed request retries into the complete page"] = { failed, retried };
    view.panel.dispose();
  }

  // The rollup answers, and the folder is not in it: an index that finished without it,
  // as one stopped at the file cap can, and an index that failed.
  for (const [step, status, truncated] of [
    ["an index that finished without the folder", "done", false],
    ["an index stopped at its cap", "truncated", true],
    ["a failed index", "failed", false],
  ]) {
    const view = page(PENDING_DIR, { path: "docs", index_status: status, truncated, node: null });
    await view.settle();
    const shown = view.read();
    noSkeleton(shown, step);
    assert(shown.totals === "nothing", `${step}: totals ${shown.totals}`);
    transcript[`${step} says so`] = shown;
    view.panel.dispose();
  }

  // A scan still running has more to say, so the skeletons are honest. If the next request
  // fails there is no totals to fall back on, and it says so.
  {
    const view = page(PENDING_DIR, { path: "docs", index_status: "scanning", node: null });
    await view.settle();
    const scanning = view.read();
    assert(scanning.totals === "skeleton", "a running scan's totals stopped loading");
    assert(scanning.distribution === "skeleton", "a running scan's distribution stopped loading");
    view.answers.next = rollupError(500);
    await view.inventoryChanged();
    const failedRefresh = view.read();
    noSkeleton(failedRefresh, "a failed refresh during a scan");
    assert(failedRefresh.retry, "a failed refresh during a scan did not offer Retry");
    transcript["a running scan keeps its skeletons until a refresh fails"] = {
      scanning,
      failedRefresh,
    };
    view.panel.dispose();
  }

  // Totals the folder's envelope already carries stay beside a failure.
  {
    const view = page(COMPLETE_DIR, rollupError(404));
    await view.settle();
    const shown = view.read();
    assert(shown.totals.includes("Total"), `a failure took the envelope's totals: ${shown.totals}`);
    transcript["totals the envelope carries stay beside a failure"] = shown;
    view.panel.dispose();
  }

  // The ordinary folder, and a refresh that fails once it has shown.
  {
    const view = page(COMPLETE_DIR, COMPLETE_ROLLUP);
    await view.settle();
    const complete = view.read();
    assert(complete.distribution.includes("Python"), "the ordinary folder has no distribution");
    transcript["an ordinary folder"] = complete;
    view.panel.dispose();
  }

  console.warn = originalWarn;
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
})().catch((error) => {
  console.warn = originalWarn;
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
