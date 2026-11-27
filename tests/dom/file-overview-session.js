// Browserless session: what File Overview shows for each answer the rollup can give.
//
// File Overview is a totals table above a type distribution, and the distribution's
// rollup drives both. Totals that were still pending when a rollup failed, or answered
// with none, used to stay a loading skeleton forever (mb-8wwl), and changing a control
// after a failure brought the distribution's skeleton back over the error. A folder the
// inventory leaves out, which its envelope names, says why it has no totals instead.
//
// The panel, its bodies, the rollup controls, the projection, the distribution model and
// view, and the inventory watch are the production modules, loaded whole. The document
// is a stand-in for the few calls they make, and `mb.watchRollup` is the SDK's, whose
// `fetch` here answers what each step says instead of asking a server: the rollups below
// have the shape `/api/rollup` answers, which cli-api.tryscript.md pins. The folder header's
// tally and the file list's note on a capped index are lifted verbatim from app.js, which
// cannot load without a document.
//
// Each step prints what is on screen: the totals, the distribution's text, starting with
// the legend, and whether it offers Retry. The distribution's table is behind Details,
// closed on mount, so it is in the text only where a step opens it. The caption naming
// the population the shares are of is for screen readers only, so it is not in the text;
// a step with one prints it apart as `caption`. A hover step prints the segments marked
// as hovered and the tooltip the shell would show, with the handle it is anchored on, the
// legend entry or the segment the pointer is on. Each step also prints the compact
// treemap's box under the breakdown, which follows the breakdown's answer: left out, its
// skeleton, unavailable, or drawn, and whether it has asked for its own deep tree. Exits 1
// on a failed invariant.

const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const vm = require("node:vm");
const { createSdkSandbox } = require("./sdk-sandbox.js");

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
    this.htmlWrites = 0;
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
  removeEventListener(type, listener) {
    if (this.listeners[type] === listener) {
      delete this.listeners[type];
    }
  }
  closest() {
    return null;
  }
  descendants() {
    return this.children.flatMap((child) => [child, ...child.descendants()]);
  }
  /** In the document: each parent up to its body still holds the element. */
  get isConnected() {
    let node = this;
    while (node.parentNode?.children.includes(node)) {
      node = node.parentNode;
    }
    return node === document.body;
  }
  contains(other) {
    return other === this || this.descendants().includes(other);
  }
  set innerHTML(value) {
    this.html = value;
    this.htmlWrites += 1;
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
  get ownerDocument() {
    return global.document;
  }
}

const windowListeners = new Map();
global.window = globalThis;
global.addEventListener = (type, listener) => windowListeners.set(type, listener);
global.removeEventListener = () => {};
global.document = { createElement: (tag) => new FakeElement(tag) };
global.metabrowser = createSdkSandbox().metabrowser;
document.body = new FakeElement("body");
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
  // The folder itself, without its tree, as a depth 0 request answers.
  node: {
    name: "docs",
    path: "docs",
    type: "dir",
    state: "complete",
    total_files: 3,
    total_size: 3000,
    unignored_files: 2,
    unignored_size: 2000,
    mtime: 1700000000.0,
    gitignored: false,
    dominant_ext: ".py",
    children: null,
  },
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
  // What the route's rule derives from that breakdown: Python is all of it.
  file_type_legend: {
    schema: "file-type-legend-v1",
    limit: 5,
    minimum_share_percent: 1,
    files: {
      all: { total: 3, named: [{ family: "python", value: 3 }], other: 0 },
      unignored: { total: 2, named: [{ family: "python", value: 2 }], other: 0 },
    },
    bytes: {
      all: { total: 3000, named: [{ family: "python", value: 3000 }], other: 0 },
      unignored: { total: 2000, named: [{ family: "python", value: 2000 }], other: 0 },
    },
  },
};

const FILE_TYPES = {
  schemaVersion: 1,
  revision: 1,
  fingerprint: "session",
  groups: [
    { id: "code", label: "Code" },
    { id: "docs", label: "Documentation" },
    { id: "data", label: "Data" },
    { id: "other", label: "Other" },
  ],
  // The order the app lists groups in, Documentation first (file_type_filters.py,
  // FILE_TYPE_GROUP_DISPLAY_ORDER): File Overview's rows and bars follow it. Each group's
  // icon is its category's, which leads its heading in Details (_REPRESENTATIVE_FAMILIES).
  displayGroups: [
    { id: "docs", label: "Documentation", icon: "doc" },
    { id: "code", label: "Code", icon: "alignLeft" },
    { id: "data", label: "Data", icon: "list" },
    { id: "other", label: "Other", icon: "file" },
  ],
  families: [
    { id: "typescript", label: "TypeScript", groupId: "code", extensions: [".ts"] },
    { id: "python", label: "Python", groupId: "code", extensions: [".py"] },
    { id: "javascript", label: "JavaScript", groupId: "code", extensions: [".js"] },
    { id: "rust", label: "Rust", groupId: "code", extensions: [".rs"] },
    { id: "markdown", label: "Markdown", groupId: "docs", extensions: [".md"] },
    { id: "json", label: "JSON", groupId: "data", extensions: [".json"] },
    { id: "yaml", label: "YAML", groupId: "data", extensions: [".yaml"] },
    { id: "log", label: "Log files", groupId: "other", extensions: [".log"] },
  ],
};

/**
 * A folder of many types, shaped like a large repository's: eight families in four
 * groups, files no family claims, and a JSON tree that is mostly ignored. By files Other
 * types is the largest bucket of all, and by bytes the order is another one. Its legend
 * is the route's: tests/test_file_type_legend.py checks the rule produced it.
 */
const MANY_TYPES_ROLLUP = JSON.parse(
  fs.readFileSync(path.join(__dirname, "fixtures/file-overview-many-types-rollup.json"), "utf8"),
);

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

  /** The family segments of the tally bars, in every row. */
  const segmentsOf = (container) =>
    container.descendants().filter((element) => element.dataset.segmentKey !== undefined);
  /** The tally row a segment is drawn in, by its heading: Files, Ignored, or Total. */
  const rowOf = (segment) =>
    segment.parentNode.parentNode.parentNode.parentNode.children[0].textContent;

  /** One mounted panel for a folder whose envelope carries `dir`, and its next rollup. */
  function page(dir, firstAnswer) {
    const answers = { next: firstAnswer };
    let requests = 0;
    let mapRequests = 0;
    // The page's one tooltip, as the shell keeps it: what it shows and the element it is
    // anchored on, until a hide puts it away. A hide within an element puts away only a
    // tooltip anchored there (docs/design-system.md, "A Surface Puts Away Only Its Own
    // Tooltip").
    const tooltip = { html: null, anchor: null };
    // Who hears the folder's sums from the directory index, which publishes them whenever
    // a file under the folder changes.
    const sumsListeners = new Set();
    const mb = {
      countClass: () => "",
      directoryTotals: {
        subscribe: (_path, listener) => {
          sumsListeners.add(listener);
          return () => sumsListeners.delete(listener);
        },
      },
      errors: window.MetabrowserRequestErrors,
      escapeHtml: String,
      fileTypeIcon: () => ({ className: "", svg: "" }),
      fileTypes: FILE_TYPES,
      // The shell's icon registry, each icon standing in as markup that names it.
      icons: {
        withClass: (name, cls) => (name ? `<svg class="${cls}" data-icon="${name}"></svg>` : ""),
      },
      filterControls: { bind: () => () => {}, checkHtml: () => "", groupHtml: () => "" },
      formatFileCount: (value) => `${value.toLocaleString("en-US")} files`,
      formatInteger: (value) => value.toLocaleString("en-US"),
      formatSize: (value) => `${value.toLocaleString("en-US")} B`,
      prefs: { get: () => null, set() {} },
      sizeClass: () => "",
      tooltip: {
        hide(within) {
          const anchor = tooltip.anchor;
          if (!within || within === anchor || within.descendants().includes(anchor)) {
            tooltip.html = null;
            tooltip.anchor = null;
          }
        },
        show(html, anchor) {
          tooltip.html = html;
          tooltip.anchor = anchor;
        },
      },
      viewState: { isActive: () => true, subscribeActive: () => () => {} },
      // Two requests, told apart by shape. The breakdown asks for no tree (depth 0) and
      // takes every answer a step gives. The section's compact treemap (treemap-compact.js)
      // asks for the deepest tree, and only once the breakdown says the index has settled;
      // its watch is counted and never answers, so the map shows its skeleton wherever it
      // keeps its box. What the map draws from a tree is treemap-compact-session.js's.
      watchRollup: (scope, options, onUpdate) => {
        if (options.depth !== 0) {
          assert(options.depth === "max", `the map asked for depth ${options.depth}`);
          mapRequests += 1;
          return { dispose() {}, refresh: async () => {}, stale: () => false };
        }
        return window.MetabrowserInventoryScope.createInventoryWatch(
          scope,
          {
            active: options.active,
            debounceMs: 0,
            fetch: async () => {
              requests += 1;
              const answer = answers.next;
              if (typeof answer === "function") {
                return answer();
              }
              if (answer instanceof Error) {
                throw answer;
              }
              return JSON.parse(JSON.stringify(answer));
            },
            onError: options.onError,
          },
          onUpdate,
        );
      },
    };
    const controls = createFolderRollupControls(mb);
    const container = new FakeElement("div");
    document.body.append(container);
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
    /** The compact treemap's box: left out, its skeleton, unavailable, or drawn. */
    const mapState = () => {
      const box = container.querySelector(".tm-compact");
      if (!box || box.hidden) {
        return "left out";
      }
      const html = box.querySelector(".tm-viewport")?.html ?? "";
      return html.includes("tm-loading")
        ? "skeleton"
        : html.includes("Treemap unavailable.")
          ? "unavailable"
          : "drawn";
    };
    return {
      answers,
      controls,
      panel,
      requests: () => requests,
      settle,
      /** Times the totals' markup was replaced, each of which restarts a skeleton's delay. */
      totalsWrites: () => totals().htmlWrites,
      read() {
        const shownTotals = totals();
        // A folder the inventory leaves out mounts neither body.
        if (!shownTotals && !summary()) {
          return { totals: "nothing", distribution: container.textContent, retry: false };
        }
        const caption = summary().querySelector(".file-type-summary-caption");
        const shown = {
          totals: shownTotals.html.includes("folder-totals-loading")
            ? "skeleton"
            : shownTotals.querySelector(".folder-totals-table")
              ? shownTotals.textContent
              : "nothing",
          distribution: summary().querySelector(".file-type-summary-skeleton")
            ? "skeleton"
            : summary().textContent,
          // What a screen reader names the legend and the table with.
          ...(caption
            ? {
                caption: caption.classList.contains("sr-only")
                  ? caption.textContent
                  : `visible: ${caption.textContent}`,
              }
            : {}),
          retry: summary().html.includes("data-file-types-retry"),
          map: mapState(),
          mapAsked: mapRequests > 0,
        };
        // The map's box is decided by the breakdown's answer: no box where the breakdown
        // offers Retry or the totals have nothing to say, and no deep request while the
        // breakdown still waits.
        if (shown.retry || (shown.totals === "nothing" && shown.distribution !== "skeleton")) {
          assert(shown.map === "left out", `the map kept its box: ${JSON.stringify(shown)}`);
        }
        assert(mapRequests <= 1, `the map asked for its tree ${mapRequests} times`);
        if (shown.distribution === "skeleton") {
          assert(shown.map === "skeleton", `the map did not wait: ${JSON.stringify(shown)}`);
          assert(
            !shown.mapAsked,
            `the map asked before the index settled: ${JSON.stringify(shown)}`,
          );
        }
        return shown;
      },
      retry() {
        summary().querySelector("[data-file-types-retry]").listeners.click();
      },
      /**
       * Each group heading in Details, as the icon that leads it, by name, and the
       * category it names: "doc Documentation".
       */
      detailsHeadings() {
        return container
          .descendants()
          .filter((element) => element.className === "file-type-summary-group-row")
          .map((row) => {
            const heading = row.children[0];
            const icon = /data-icon="([^"]*)"/.exec(heading.html)?.[1] ?? "no icon";
            return `${icon} ${heading.textContent}`;
          });
      },
      /** The Details toggle the compact summary offers. */
      details() {
        return summary().querySelector(".file-type-summary-details-toggle");
      },
      /** The summary's root, while it is mounted. */
      summaryRoot() {
        return container.querySelector(".file-type-summary");
      },
      /** The legend entry whose name is `label`. */
      legendEntry(label) {
        return container
          .descendants()
          .find(
            (element) =>
              element.classList.contains("file-type-summary-legend-item") &&
              element.querySelector(".file-type-summary-legend-label")?.textContent === label,
          );
      },
      /** The segment of family `key` in the tally row named `row`. */
      segment(row, key) {
        return segmentsOf(container).find(
          (segment) => segment.dataset.segmentKey === key && rowOf(segment) === row,
        );
      },
      /**
       * What the hover draws: every element marked as hovered, a segment by its tally row
       * and family, a Details row's bar by its row, and a legend entry by its family, in
       * page order; the tooltip's words; and what it is anchored on: the segment, or the
       * legend entry the pointer is on. A mark inside something hidden, as the Details
       * table is while closed, says so, since a reader would not see it.
       */
      hover() {
        const hidden = (element) => {
          for (let node = element; node; node = node.parentNode) {
            if (node.hidden) {
              return true;
            }
          }
          return false;
        };
        const name = (element) => {
          if (element.dataset.legendKey !== undefined) {
            return `legend ${element.dataset.legendKey}`;
          }
          if (element.dataset.segmentKey !== undefined) {
            return `${rowOf(element)} ${element.dataset.segmentKey}`;
          }
          const detailsRow = element.parentNode?.parentNode?.parentNode?.parentNode;
          return detailsRow?.dataset.typeKey !== undefined
            ? `Details ${detailsRow.dataset.typeKey}`
            : `not a mark: ${element.className}`;
        };
        const marked = container
          .descendants()
          .filter((element) => "hovered" in element.dataset)
          .map((element) => (hidden(element) ? `hidden ${name(element)}` : name(element)));
        return {
          marked,
          tooltip:
            tooltip.html === null
              ? null
              : tooltip.html
                  .replace(/<br>|<\/div>/g, " ")
                  .replace(/<[^>]*>/g, "")
                  .replace(/\s+/g, " ")
                  .trim(),
          anchoredOn:
            tooltip.anchor === null
              ? null
              : tooltip.anchor.dataset.legendKey !== undefined
                ? `legend ${tooltip.anchor.dataset.legendKey}`
                : tooltip.anchor.dataset.segmentKey === undefined
                  ? "not a segment"
                  : `${rowOf(tooltip.anchor)} ${tooltip.anchor.dataset.segmentKey}`,
        };
      },
      /** The folder's sums from the directory index, which redraw the bars alone. */
      sumsArrived(dir) {
        for (const listener of [...sumsListeners]) {
          listener(dir);
        }
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

  // A capped index with this folder in it: the counts show, and the distribution says
  // they are partial.
  {
    const view = page(PENDING_DIR, {
      ...COMPLETE_ROLLUP,
      index_status: "truncated",
      truncated: true,
      max_files: 3,
    });
    await view.settle();
    const shown = view.read();
    noSkeleton(shown, "a capped index");
    assert(
      shown.distribution.includes("Only the first 3 files were scanned"),
      `capped: ${shown.distribution}`,
    );
    transcript["a capped index says its summary is partial"] = shown;
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

  // A later answer that the scan is running brings both skeletons back, whatever ended them.
  // The distribution rebuilds its own from that answer, and the totals have to follow it.
  const SCANNING = { path: "docs", index_status: "scanning", node: null };
  const FINISHED_WITHOUT = { path: "docs", index_status: "done", truncated: false, node: null };
  for (const [step, answers, resume] of [
    ["a refresh failing during a scan, then Retry", [SCANNING, rollupError(500)], "retry"],
    ["a refresh failing during a scan, then a change", [SCANNING, rollupError(500)], "change"],
    ["an index that finished without the folder, then a rescan", [FINISHED_WITHOUT], "change"],
    ["a failed first request, then a change", [rollupError(500)], "change"],
    ["a failed first request, then Retry", [rollupError(500)], "retry"],
  ]) {
    const [firstAnswer, ...later] = answers;
    const view = page(PENDING_DIR, firstAnswer);
    await view.settle();
    for (const answer of later) {
      view.answers.next = answer;
      await view.inventoryChanged();
    }
    const stopped = view.read();
    noSkeleton(stopped, step);
    view.answers.next = SCANNING;
    if (resume === "retry") {
      view.retry();
      await view.settle();
    } else {
      await view.inventoryChanged();
    }
    const resumed = view.read();
    assert(resumed.totals === "skeleton", `${step}: totals ${resumed.totals}`);
    assert(resumed.distribution === "skeleton", `${step}: distribution ${resumed.distribution}`);
    transcript[`${step} brings both skeletons back`] = { stopped, resumed };
    view.panel.dispose();
  }

  // Every refresh of a scan answers the same, and only a change repaints the totals. Past a
  // failure and back it still ends the same way, when the index says nothing is coming.
  {
    const view = page(PENDING_DIR, SCANNING);
    await view.settle();
    const writes = view.totalsWrites();
    await view.inventoryChanged();
    assert(view.totalsWrites() === writes, "a scan's refresh repainted the totals' skeleton");
    view.answers.next = rollupError(500);
    await view.inventoryChanged();
    view.answers.next = SCANNING;
    await view.inventoryChanged();
    const resumed = view.read();
    assert(resumed.totals === "skeleton", `past a failure: totals ${resumed.totals}`);
    view.answers.next = FINISHED_WITHOUT;
    await view.inventoryChanged();
    const finished = view.read();
    noSkeleton(finished, "an index that finished after a resumed scan");
    assert(finished.totals === "nothing", `an index finished after: totals ${finished.totals}`);
    transcript["a resumed scan still finishes"] = { resumed, finished };
    view.panel.dispose();
  }

  // Totals already on screen are not a skeleton's to take back.
  {
    const view = page(COMPLETE_DIR, rollupError(500));
    await view.settle();
    view.answers.next = SCANNING;
    await view.inventoryChanged();
    const shown = view.read();
    assert(shown.totals.includes("Total"), `a rescan took the envelope's totals: ${shown.totals}`);
    transcript["a rescan leaves the totals the envelope carries"] = shown;
    view.panel.dispose();
  }

  // A folder the inventory leaves out: nothing can answer, so nothing is asked, nothing
  // waits, and File Overview says why. Its rollup would be refused.
  for (const reason of ["hidden", "symlink"]) {
    const view = page({ ...PENDING_DIR, not_indexed: reason }, rollupError(404));
    await view.settle();
    const shown = view.read();
    noSkeleton(shown, `a ${reason} folder`);
    assert(view.requests() === 0, `a ${reason} folder asked for a rollup`);
    assert(shown.distribution.includes("no file totals"), `a ${reason} folder: ${shown}`);
    assert(!shown.distribution.includes("Could not load"), `a ${reason} folder reads as a failure`);
    transcript[`a ${reason} folder says why it has no totals`] = shown;
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

  // The ordinary folder. The distribution's caption, for screen readers, says which
  // tally row its shares are of and how much that is, and follows Show ignored and the
  // measure; the tally rows themselves do not move.
  {
    const view = page(COMPLETE_DIR, COMPLETE_ROLLUP);
    await view.settle();
    const complete = view.read();
    assert(complete.distribution.includes("Python"), "the ordinary folder has no distribution");
    assert(
      complete.caption === "Share of Total (3 files)" && !complete.distribution.includes("Share"),
      `Show ignored on, by files: ${JSON.stringify(complete)}`,
    );
    view.controls.set({ includeIgnored: false });
    const filesOnly = view.read();
    assert(
      filesOnly.caption === "Share of Files (2 files)",
      `Show ignored off, by files: ${filesOnly.caption}`,
    );
    view.controls.set({ metric: "size" });
    const bytes = view.read();
    assert(
      bytes.caption === "Share of Files (2,000 B)",
      `Show ignored off, by bytes: ${bytes.caption}`,
    );
    view.controls.set({ includeIgnored: true });
    const allBytes = view.read();
    assert(
      allBytes.caption === "Share of Total (3,000 B)",
      `Show ignored on, by bytes: ${allBytes.caption}`,
    );
    assert(
      filesOnly.totals === complete.totals,
      "Show ignored moved the tally rows, which are fixed populations",
    );
    transcript["an ordinary folder"] = { complete, filesOnly, bytes, allBytes };
    view.panel.dispose();
  }

  // The compact summary and its Details. The legend is what File Overview shows of the
  // breakdown; everything else waits behind Details, which
  // starts closed, holds its state through every repaint of this mount, and goes with it.
  {
    const view = page(
      {
        total_files: 1000,
        total_size: 1000,
        unignored_files: 800,
        unignored_size: 920,
        state: "complete",
      },
      MANY_TYPES_ROLLUP,
    );
    await view.settle();
    const toggle = () => view.details();
    const state = (step) => {
      const { caption, distribution } = view.read();
      return { details: toggle().attributes["aria-expanded"], caption, distribution, step };
    };
    const closed = state("mounted");
    assert(closed.details === "false", "Details starts open");
    assert(
      closed.distribution ===
        "JSON 24% YAML 17% Markdown 15% TypeScript 6% Python 3.3% JavaScript 2.5% Log files 2.1% Other 30.1% Details" &&
        closed.caption === "Share of Total (1,000 files)",
      `the compact summary: ${closed.distribution}`,
    );
    toggle().listeners.click();
    const opened = { ...state("Details opened"), headings: view.detailsHeadings() };
    assert(opened.details === "true", "Details did not open");
    // Each group's heading leads with its category's icon (docs/design-system.md,
    // "File-Type Category Icons").
    assert(
      opened.headings.join(", ") === "doc Documentation, alignLeft Code, list Data, file Other",
      `Details' headings: ${opened.headings.join(", ")}`,
    );
    for (const shown of ["Code", "Documentation", "Data", "Other", "No extension", "Other types"]) {
      assert(opened.distribution.includes(shown), `open Details does not show ${shown}`);
    }
    assert(
      opened.distribution.includes("JavaScript 25 files 2.5%") &&
        opened.distribution.includes("1 more 8 files 0.8%"),
      `open Details lacks a type the legend leaves out: ${opened.distribution}`,
    );
    view.controls.set({ metric: "size" });
    const bySize = state("measure changed to bytes");
    view.controls.set({ includeIgnored: false });
    const unignored = state("Show ignored turned off");
    await view.inventoryChanged();
    const refreshed = state("rollup refreshed");
    for (const step of [bySize, unignored, refreshed]) {
      assert(step.details === "true", `${step.step} closed Details`);
    }
    assert(
      bySize.distribution.startsWith(
        "Markdown 30% TypeScript 20% Python 15% JavaScript 12% JSON 10% YAML 5% Log files 2.5% Other 5.5% Details",
      ) && bySize.caption === "Share of Total (1,000 B)",
      `by bytes: ${bySize.distribution}`,
    );
    assert(
      unignored.distribution.startsWith(
        "Markdown 32.6% TypeScript 21.7% Python 16.3% JavaScript 13% YAML 5.4% Log files 2.7% JSON 2.2% Other 6% Details",
      ) && unignored.caption === "Share of Files (920 B)",
      `Show ignored off: ${unignored.distribution}`,
    );
    const detailsBeforeScan = toggle();
    view.answers.next = { path: "docs", index_status: "scanning", node: null };
    await view.inventoryChanged();
    const rescanning = {
      keptDistribution: view.read().distribution === refreshed.distribution,
      keptOpenDetails:
        toggle() === detailsBeforeScan && toggle().attributes["aria-expanded"] === "true",
    };
    assert(rescanning.keptDistribution, "a rescan replaced the completed distribution");
    assert(rescanning.keptOpenDetails, "a rescan replaced the open Details toggle");
    view.answers.next = MANY_TYPES_ROLLUP;
    await view.inventoryChanged();
    const rescanned = state("a rescan answered");
    assert(rescanned.details === "true", "the completed rescan closed Details");
    toggle().listeners.click();
    const reclosed = state("Details closed");
    assert(reclosed.details === "false", "Details did not close");
    assert(
      reclosed.distribution.endsWith("Other 6% Details"),
      `a closed Details shows its table: ${reclosed.distribution}`,
    );
    toggle().listeners.click();
    view.panel.dispose();
    assert(view.summaryRoot() === null, "a disposed panel left its summary behind");
    const remounted = page(
      {
        total_files: 1000,
        total_size: 1000,
        unignored_files: 800,
        unignored_size: 920,
        state: "complete",
      },
      MANY_TYPES_ROLLUP,
    );
    await remounted.settle();
    const fresh = remounted.details().attributes["aria-expanded"];
    assert(fresh === "false", "Details stayed open into the next mount");
    transcript["the compact summary and its Details"] = {
      closed,
      opened,
      bySize,
      unignored,
      refreshed,
      rescanning,
      rescanned,
      reclosed,
      "disposed, then mounted again": { details: fresh },
    };
    remounted.panel.dispose();
  }

  // A legend entry is a handle on its family's marks in every bar on screen: its segment
  // in each tally row, Files, Ignored, and Total, and its own row's bar in Details while
  // that is open, not its extensions' rows. Pointing at a segment marks that segment
  // alone, the one value it is. Either way the family's entry is marked too, so the key
  // answers with what it keys, and there is one tooltip, anchored on the handle the
  // pointer is on: on a segment, the family and its counts; on the entry, which shows the
  // name, the counts alone of its family's segment in the row the legend's shares are of,
  // Total while Show ignored is on and Files while it is off. Other names no one segment
  // and draws nothing. Details opened or closed under a pointer still on an entry marks or
  // unmarks its row as it appears or goes. The folder's sums redrawing the bars under a
  // pointer still on an entry keep its hover, as the browser's entering a redrawn segment
  // keeps a segment's. A rollup that rebuilds or empties the legend, or the section's
  // disposal, puts the hover away (docs/design-system.md, "Aggregate Distributions").
  {
    const sums = {
      total_files: 1000,
      total_size: 1000,
      unignored_files: 800,
      unignored_size: 920,
      state: "complete",
    };
    const view = page(sums, MANY_TYPES_ROLLUP);
    await view.settle();
    const nothing = { marked: [], tooltip: null, anchoredOn: null };
    const same = (left, right) => JSON.stringify(left) === JSON.stringify(right);
    const atRest = view.hover();
    assert(same(atRest, nothing), `a hover before any pointer: ${JSON.stringify(atRest)}`);

    const json = () => view.legendEntry("JSON");
    json().listeners.mouseenter();
    const entry = view.hover();
    assert(
      same(entry.marked, [
        "Files family:json",
        "Ignored family:json",
        "Total family:json",
        "legend family:json",
      ]) &&
        entry.tooltip === "240 files · 100 B" &&
        entry.anchoredOn === "legend family:json",
      `the JSON entry under Show ignored: ${JSON.stringify(entry)}`,
    );
    json().listeners.mouseleave();
    const left = view.hover();
    assert(same(left, nothing), `leaving the entry: ${JSON.stringify(left)}`);

    const segment = view.segment("Total", "family:json");
    segment.listeners.mouseenter();
    const onSegment = view.hover();
    segment.listeners.mouseleave();
    // One value, and its family's entry; the category and the name join the counts on the
    // segment, which shows neither, and the tooltip sits by what the pointer is on.
    assert(
      same(onSegment.marked, ["Total family:json", "legend family:json"]) &&
        onSegment.tooltip === `Data JSON ${entry.tooltip}` &&
        onSegment.anchoredOn === "Total family:json",
      `the Total row's JSON segment: ${JSON.stringify(onSegment)}`,
    );
    assert(same(view.hover(), nothing), "leaving the segment left a hover");

    view.legendEntry("Other").listeners.mouseenter?.();
    const other = view.hover();
    assert(same(other, nothing), `Other drew a hover: ${JSON.stringify(other)}`);
    view.legendEntry("Other").listeners.mouseleave?.();

    // A key opens Details under a pointer that has not left the entry: the family's own
    // row is marked as it appears, and unmarked as Details closes. A segment marks no row.
    json().listeners.mouseenter();
    view.details().listeners.click();
    const detailsOpened = view.hover();
    assert(
      same(detailsOpened.marked, [...entry.marked, "Details family:json"]) &&
        detailsOpened.tooltip === entry.tooltip,
      `Details opened under the JSON entry: ${JSON.stringify(detailsOpened)}`,
    );
    json().listeners.mouseleave();
    segment.listeners.mouseenter();
    const segmentWithDetails = view.hover();
    segment.listeners.mouseleave();
    assert(
      same(segmentWithDetails.marked, onSegment.marked),
      `a segment marked a Details row: ${JSON.stringify(segmentWithDetails)}`,
    );
    json().listeners.mouseenter();
    view.details().listeners.click();
    const detailsClosed = view.hover();
    assert(
      same(detailsClosed, entry),
      `Details closed under the JSON entry: ${JSON.stringify(detailsClosed)}`,
    );
    json().listeners.mouseleave();

    // Show ignored rebuilds the legend after the bars have drawn again, so the legend
    // lets go of the hover the entry it removes held.
    json().listeners.mouseenter();
    view.controls.set({ includeIgnored: false });
    const toggled = view.hover();
    assert(
      same(toggled, nothing),
      `Show ignored turned off under the pointer kept a hover: ${JSON.stringify(toggled)}`,
    );
    const markdown = () => view.legendEntry("Markdown");
    markdown().listeners.mouseenter();
    const filesOnly = view.hover();
    assert(
      // No Markdown file is ignored, so the Ignored row has no Markdown segment to mark.
      same(filesOnly.marked, [
        "Files family:markdown",
        "Total family:markdown",
        "legend family:markdown",
      ]) && filesOnly.anchoredOn === "legend family:markdown",
      `the Markdown entry without ignored files: ${JSON.stringify(filesOnly)}`,
    );
    markdown().listeners.mouseleave();
    view.segment("Files", "family:markdown").listeners.mouseenter();
    assert(
      same(view.hover().marked, ["Files family:markdown", "legend family:markdown"]) &&
        view.hover().tooltip === `Documentation Markdown ${filesOnly.tooltip}`,
      "the Files row's segment drew another hover",
    );
    view.segment("Files", "family:markdown").listeners.mouseleave();

    // The folder's sums arrive whenever a file changes, and redraw the bars alone: the
    // entry under the pointer outlives the draw and hears nothing.
    markdown().listeners.mouseenter();
    const drawnBefore = view.segment("Files", "family:markdown");
    view.sumsArrived(sums);
    const redrawn = view.hover();
    assert(
      view.segment("Files", "family:markdown") !== drawnBefore,
      "the folder's sums did not redraw the bars",
    );
    assert(
      same(redrawn, filesOnly),
      `the bars redrawn under the entry dropped its hover: ${JSON.stringify(redrawn)}`,
    );

    // The incomplete rollup keeps the existing legend entry and its hover.
    const entryBeforeScan = markdown();
    view.answers.next = { path: "docs", index_status: "scanning", node: null };
    await view.inventoryChanged();
    const rescanning = view.hover();
    assert(
      markdown() === entryBeforeScan && same(rescanning, filesOnly),
      `a rescan displaced the legend hover: ${JSON.stringify(rescanning)}`,
    );
    view.answers.next = MANY_TYPES_ROLLUP;
    await view.inventoryChanged();
    const repainted = view.hover();
    assert(same(repainted, nothing), `a repaint kept the hover: ${JSON.stringify(repainted)}`);
    // The browser enters the rebuilt entry under a pointer that has not moved.
    markdown().listeners.mouseenter();
    const reentered = view.hover();
    assert(same(reentered, filesOnly), "entering the rebuilt entry drew nothing");

    view.panel.dispose();
    const disposed = view.hover();
    assert(same(disposed, nothing), `disposal kept the hover: ${JSON.stringify(disposed)}`);
    transcript["a legend entry hovers its family's marks"] = {
      "at rest": atRest,
      "pointer on the JSON entry, Show ignored on": entry,
      "left the entry": left,
      "pointer on the Total row's JSON segment": onSegment,
      "pointer on Other": other,
      "Details opened under the pointer on the JSON entry": detailsOpened,
      "pointer on the Total row's JSON segment, Details open": segmentWithDetails,
      "Details closed under the pointer on the JSON entry": detailsClosed,
      "Show ignored turned off under the pointer": toggled,
      "pointer on the Markdown entry, Show ignored off": filesOnly,
      "the folder's sums redrew the bars under the pointer": redrawn,
      "a rescan kept the legend under the pointer": rescanning,
      "the rollup refreshed under the pointer": repainted,
      "the browser entered the rebuilt entry": reentered,
      "the section disposed under the pointer": disposed,
    };
  }

  // The shell's folder header reads the same envelope: pending aggregates are a skeleton
  // until they arrive, and a folder the inventory leaves out has no tally to wait for. The
  // line is view-header.js's, over app.js's own cell helpers, lifted verbatim.
  {
    const appSource = fs.readFileSync(path.join(sourceRoot, "static/app.js"), "utf8");
    const lift = (name) => {
      const match = appSource.match(
        new RegExp(`\\nfunction ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n\\}`),
      );
      assert(match, `${name} not found in app.js`);
      return match[0];
    };
    const shellPage = {
      MetabrowserFormatters: { ageLabelHtml: () => '<span class="age">3h</span>' },
    };
    shellPage.window = shellPage;
    vm.createContext(shellPage);
    vm.runInContext(
      fs.readFileSync(path.join(sourceRoot, "static/view-header.js"), "utf8"),
      shellPage,
    );
    const summaryHtml = vm.runInContext(
      `function sizeClass() { return ""; }
       function countClass() { return ""; }
       function formatSize(value) { return value + " B"; }
       function formatCount(value) { return value + " files"; }
       function notDrawnHere() { throw new Error("the folder line draws only its cells"); }
       ${["isPendingNumber", "sizeHtml", "countHtml", "formatAge"].map(lift).join("\n")}
       MetabrowserViewHeader.create({
         esc: notDrawnHere,
         servedRoot: notDrawnHere,
         servedRootName: notDrawnHere,
         ownedControlAttr: notDrawnHere,
         mirrorHeading: notDrawnHere,
         getFileIcon: notDrawnHere,
         getLogicalName: notDrawnHere,
         sizeHtml,
         countHtml,
         formatAge,
         activeFiles: new Map(),
       }).folderHeaderSummaryHtml;`,
      shellPage,
    );
    const header = (dir) => {
      const html = summaryHtml(dir);
      return {
        skeleton: html.includes("tally-pending"),
        text: html
          .replace(/<[^>]*>/g, " ")
          .replace(/\s+/g, " ")
          .trim(),
      };
    };
    const shown = {
      "still scanning": header({ ...PENDING_DIR, mtime: null }),
      complete: header({ ...COMPLETE_DIR, mtime: 1700000000 }),
      hidden: header({ ...PENDING_DIR, mtime: null, not_indexed: "hidden" }),
      symlink: header({ ...PENDING_DIR, mtime: null, not_indexed: "symlink" }),
    };
    assert(shown["still scanning"].skeleton, "a scanning folder's header stopped loading");
    assert(!shown.hidden.skeleton && !shown.symlink.skeleton, "a tally waits for nothing");
    transcript["the folder header's tally"] = shown;

    // The file list says the same of a capped index. Its count helper writes the noun, and
    // the route may not name the limit.
    const noteHtml = vm.runInNewContext(
      `${["formatCountParts", "formatCount", "treeTruncationNoteHtml"].map(lift).join("\n")}
       treeTruncationNoteHtml;`,
    );
    const note = (maxFiles) => noteHtml(maxFiles).replace(/<[^>]*>/g, "");
    const notes = { "3 files": note(3), "1 file": note(1), "no limit named": note(undefined) };
    assert(
      notes["3 files"] ===
        "File list incomplete. Metabrowser stopped after 3 files, so some files and folders are not shown.",
      `the capped note: ${notes["3 files"]}`,
    );
    assert(notes["1 file"].includes("stopped after 1 file,"), `one file: ${notes["1 file"]}`);
    assert(notes["no limit named"].includes("its file limit"), notes["no limit named"]);
    transcript["the file list's note on a capped index"] = notes;
  }

  // The section holds the Overview's first paint for its first rollup, so it paints at
  // the height it keeps; a rollup slower than FIRST_ROLLUP_WAIT_MS paints the pending
  // state first, as before. Not part of the transcript: these are timings.
  {
    const { FIRST_ROLLUP_WAIT_MS } = await import(folder("file-overview-panel.js"));
    const settled = async (promise) => {
      let done = false;
      void promise.then(() => {
        done = true;
      });
      await new Promise((resolve) => setImmediate(resolve));
      return done;
    };
    let answer = () => {};
    const held = page(
      COMPLETE_DIR,
      () =>
        new Promise((resolve) => {
          answer = () => resolve(JSON.parse(JSON.stringify(COMPLETE_ROLLUP)));
        }),
    );
    assert(!(await settled(held.panel.ready)), "the section is ready before its rollup answered");
    answer();
    await held.settle();
    assert(await settled(held.panel.ready), "the section is not ready once its rollup answered");
    held.panel.dispose();
    const late = page(COMPLETE_DIR, () => new Promise(() => {}));
    assert(!(await settled(late.panel.ready)), "a late rollup did not hold the section");
    await new Promise((resolve) => setTimeout(resolve, FIRST_ROLLUP_WAIT_MS + 20));
    assert(await settled(late.panel.ready), "a late rollup held the section past its wait");
    assert(FIRST_ROLLUP_WAIT_MS <= 100, "the section waits longer than a short hold");
    late.panel.dispose();
  }

  console.warn = originalWarn;
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
})().catch((error) => {
  console.warn = originalWarn;
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
