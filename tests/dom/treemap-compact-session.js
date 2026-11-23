// Run the production compact treemap (treemap-compact.js, over treemap-map.js and
// treemap-layout.js) through its states. Its box follows the section breakdown's answers:
// kept with a skeleton while the index scans, without asking for the deep tree; left out
// when the breakdown's request failed, the index stopped at its cap, or the folder holds no
// files in the population shown; and drawn once the index has settled and the map's own
// rollup answers, inside an outer box for the folder itself. It follows the section's legend
// hover, measure, Show ignored, and the tab's activation; a cell opens the Treemap view at its
// folder, and the outer box at the folder itself; a failed rollup keeps the
// box and recovers on Retry. Disposal releases every listener, the watch, and the observer,
// and puts away only the map's own tooltip.
//
// The DOM is a stand-in for the calls the map makes. A cell element is parsed back out
// of the HTML the map writes, so what the session reads is what the map drew.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes("is not specified and it doesn't parse as CommonJS")) {
    return;
  }
  emitWarning.call(process, warning, ...rest);
};

const folder = (name) =>
  pathToFileURL(path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/folder", name));

/** A drawn cell, parsed from the map's HTML. */
class FakeCell {
  constructor(index, kind, pathName, classes, box) {
    this.dataset = { tmCell: String(index), tmKind: kind, tmPath: pathName };
    this.classes = classes;
    this.box = box;
  }
  closest(selector) {
    return selector === "[data-tm-cell]" ? this : null;
  }
}

class FakeElement {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.listeners = new Map();
    this.attributes = {};
    this.hidden = false;
    this.className = "";
    this.classList = { add: (name) => (this.className = `${this.className} ${name}`.trim()) };
    this._html = "";
    this.cells = [];
    this.clientWidth = 0;
    this.clientHeight = 0;
  }
  set innerHTML(html) {
    this._html = html;
    this.cells = [];
    const pattern =
      /<div class="([^"]*)"[^>]*data-tm-cell="(\d+)" data-tm-kind="(\w+)" data-tm-path="([^"]*)" style="left:([\d.]+)px;top:([\d.]+)px;width:([\d.]+)px;height:([\d.]+)px/g;
    for (const match of html.matchAll(pattern)) {
      const box = match.slice(5, 9).map(Number);
      this.cells.push(new FakeCell(Number(match[2]), match[3], match[4], match[1].split(" "), box));
    }
  }
  get innerHTML() {
    return this._html;
  }
  append(...nodes) {
    this.children.push(...nodes);
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }
  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }
  removeEventListener(type, listener) {
    if (this.listeners.get(type) === listener) {
      this.listeners.delete(type);
    }
  }
  getBoundingClientRect() {
    return { width: this.clientWidth + 2, height: this.clientHeight + 2, top: 0, left: 0 };
  }
  querySelector() {
    return null;
  }
  querySelectorAll(selector) {
    assert.equal(selector, "[data-tm-cell]");
    return this.cells;
  }
  contains(node) {
    return this.cells.includes(node);
  }
  closest() {
    return null;
  }
}

const EXTENSION_FAMILIES = { ".py": "python", ".md": "markdown" };

function file(name, filePath, size, ext, gitignored = false) {
  return { name, path: filePath, type: "file", size, ext, gitignored, mtime: 1 };
}

function dir(name, dirPath, children, gitignored = false) {
  const sum = (pick) => children.reduce((total, c) => total + pick(c), 0);
  const files = sum((c) => (c.type === "dir" ? c.total_files : 1));
  const size = sum((c) => (c.type === "dir" ? c.total_size : c.size));
  const unignoredFiles = sum((c) => (c.type === "dir" ? c.unignored_files : c.gitignored ? 0 : 1));
  const unignoredSize = sum((c) =>
    c.type === "dir" ? c.unignored_size : c.gitignored ? 0 : c.size,
  );
  const counts = {};
  for (const c of children) {
    const ext = c.type === "dir" ? c.dominant_ext : c.ext;
    counts[ext] = (counts[ext] || 0) + (c.type === "dir" ? c.total_files : 1);
  }
  const dominant = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "";
  return {
    name,
    path: dirPath,
    type: "dir",
    state: "complete",
    total_files: files,
    total_size: size,
    unignored_files: unignoredFiles,
    unignored_size: unignoredSize,
    gitignored,
    dominant_ext: dominant,
    mtime: 1,
    children,
  };
}

const TREE = dir("src", "src", [
  dir("lib", "src/lib", [
    file("app.py", "src/lib/app.py", 6000, ".py"),
    file("util.py", "src/lib/util.py", 3000, ".py"),
    file("cli.py", "src/lib/cli.py", 2000, ".py"),
  ]),
  dir("docs", "src/docs", [
    file("guide.md", "src/docs/guide.md", 3000, ".md"),
    file("notes.md", "src/docs/notes.md", 1500, ".md"),
  ]),
  file("README.md", "src/README.md", 2500, ".md"),
  file("cache.md", "src/cache.md", 9000, ".md", true),
]);
const ONLY_IGNORED = dir("src", "src", [file("cache.md", "src/cache.md", 9000, ".md", true)]);
const EMPTY = dir("src", "src", []);

/** What the section's breakdown is told: its tally rollup has the folder's node, no tree. */
const breakdownAnswer = (indexStatus, tree, nodeState = "complete") => ({
  index_status: indexStatus,
  node: { ...tree, children: null, state: nodeState },
});

async function main() {
  // A failed rollup is logged; the session reports those lines as data instead.
  const warnings = [];
  console.warn = (message) => warnings.push(String(message));
  const { createDistributionHover } = await import(folder("distribution-hover.js"));
  const { mountCompactTreemap } = await import(folder("treemap-compact.js"));

  global.window = {};
  global.document = { createElement: (tag) => new FakeElement(tag) };
  const observers = [];
  global.ResizeObserver = class {
    constructor(callback) {
      this.callback = callback;
      this.observed = [];
      this.disconnected = false;
      observers.push(this);
    }
    observe(element) {
      this.observed.push(element);
    }
    disconnect() {
      this.disconnected = true;
    }
  };

  /** One mount: its rollup watch, navigation, tooltip, and controls. */
  function mount({ width = 600 } = {}) {
    const navigation = [];
    const tooltipHides = [];
    const watch = { options: null, apply: null, disposed: false, refreshes: 0, stale: false };
    let controlsState = { metric: "size", includeIgnored: true };
    const controlListeners = new Set();
    const activeListeners = new Set();
    const mb = {
      escapeHtml: (value) =>
        String(value).replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;"),
      fileTypeIcon: () => ({ svg: "", className: "" }),
      fileTypes: { distributionKeyForExtension: (ext) => EXTENSION_FAMILIES[ext] ?? "other" },
      formatFileCount: (count) => `${count} files`,
      formatSize: (bytes) => `${bytes} B`,
      formatTimestamp: () => "then",
      navigation: { open: (...args) => navigation.push(args) },
      sourceKind: () => "filesystem",
      tooltip: { show() {}, hide: (within) => tooltipHides.push(within) },
      viewState: {
        isActive: () => true,
        subscribeActive(_element, listener) {
          activeListeners.add(listener);
          return () => activeListeners.delete(listener);
        },
      },
      watchRollup(scope, options, apply) {
        assert.equal(scope, "src");
        assert.equal(watch.options, null, "the map asks for its tree once");
        watch.options = options;
        watch.apply = apply;
        return {
          dispose() {
            watch.disposed = true;
          },
          refresh: async () => {
            watch.refreshes += 1;
          },
          stale: () => watch.stale,
        };
      },
    };
    const controls = {
      get: () => controlsState,
      subscribe(listener) {
        controlListeners.add(listener);
        return () => controlListeners.delete(listener);
      },
    };
    const palette = { classFor: (key) => `c-${key}`, styleFor: () => "", paint() {} };
    const hover = createDistributionHover();
    const container = new FakeElement("div");
    // The box the stylesheet gives the compact map, inside its border; set before the
    // mount, as the stylesheet sizes it before the first paint.
    const created = document.createElement;
    document.createElement = (tag) => {
      const element = created(tag);
      element.clientWidth = width;
      element.clientHeight = 218;
      return element;
    };
    const handle = mountCompactTreemap(container, { path: "src" }, mb, palette, controls, {
      hover,
    });
    document.createElement = created;
    const viewport = container.children[0];
    return {
      handle,
      container,
      viewport,
      hover,
      watch,
      navigation,
      tooltipHides,
      controlListeners,
      activeListeners,
      setControls(next) {
        controlsState = next;
        for (const listener of [...controlListeners]) {
          listener(next);
        }
      },
      activate() {
        for (const listener of [...activeListeners]) {
          listener(true);
        }
      },
      resize(width) {
        viewport.clientWidth = width;
        for (const observer of observers) {
          if (observer.observed.includes(viewport)) {
            observer.callback();
          }
        }
      },
    };
  }

  const summary = (page) => ({
    hidden: page.container.hidden,
    skeleton: page.viewport.innerHTML.includes("tm-loading"),
    unavailable: page.viewport.innerHTML.includes("Treemap unavailable."),
    asked: page.watch.options !== null,
    cells: page.viewport.cells.map(
      (cell) =>
        `${cell.dataset.tmKind} ${cell.dataset.tmPath} ${cell.box[2].toFixed(0)}x${cell.box[3].toFixed(0)}`,
    ),
  });
  const steps = [];

  // ── a folder whose index settles ──────────────────────────────
  const page = mount();
  steps.push({ step: "mounted, before the breakdown answers", ...summary(page) });

  page.handle.follow(breakdownAnswer("scanning", TREE, "pending"));
  steps.push({ step: "the breakdown says the index is still scanning", ...summary(page) });

  page.handle.follow(breakdownAnswer("done", TREE));
  steps.push({
    step: "the breakdown says the index has finished",
    request: {
      depth: page.watch.options.depth,
      top: page.watch.options.top,
      ext_rank: page.watch.options.ext_rank,
    },
    ...summary(page),
  });

  page.watch.apply({ index_status: "done", node: TREE });
  // Every cell fits inside the border: the map lays out to the client box, not to the
  // bounding box, which is larger by the border and pushed edge cells under it.
  const insideBorder = page.viewport.cells.every(
    ({ box: [left, top, width, height] }) =>
      left + width <= page.viewport.clientWidth && top + height <= page.viewport.clientHeight,
  );
  steps.push({ step: "the map's tree arrives", insideBorder, ...summary(page) });

  const entry = { tag: "legend-entry" };
  page.hover.enter({ population: "all", key: "python", anchor: entry, marks: "family" });
  steps.push({
    step: "pointing at the Python legend entry",
    marked: page.viewport.cells
      .filter((cell) => cell.dataset.hovered === "family")
      .map((cell) => cell.dataset.tmPath),
  });
  page.hover.leave({ population: "all", key: "python", anchor: entry, marks: "family" });
  assert.equal(
    page.viewport.cells.filter((cell) => cell.dataset.hovered).length,
    0,
    "leaving the entry clears the marks",
  );

  const click = page.viewport.listeners.get("click");
  for (const target of ["src/lib/app.py", "src/docs", "src/README.md"]) {
    const cell = page.viewport.cells.find((c) => c.dataset.tmPath === target);
    if (cell) {
      click({ target: cell });
    }
  }
  steps.push({
    step: "activating two file cells and a folder cell opens the Treemap at their folders",
    navigation: page.navigation,
  });

  // The folder's own cell is the outer box around the rest, and opens the Treemap at it.
  const outer = page.viewport.cells[0];
  const [left, top, width, height] = outer.box;
  assert.equal(outer.dataset.tmPath, "src");
  assert.ok(
    left <= 1 && top <= 1 && width >= page.viewport.clientWidth - 2,
    "the box spans the map",
  );
  assert.ok(height >= page.viewport.clientHeight - 2, "the box spans the map's height");
  page.navigation.length = 0;
  click({ target: outer });
  steps.push({
    step: "activating the outer box opens the Treemap at the folder",
    outerBox: outer.classes.includes("tm-nested") ? "labelled, around the tree" : "solid",
    navigation: page.navigation,
  });

  page.setControls({ metric: "files", includeIgnored: true });
  steps.push({ step: "the measure switches to Files", ...summary(page) });

  page.setControls({ metric: "files", includeIgnored: false });
  steps.push({ step: "Show ignored is turned off", ...summary(page) });

  page.watch.stale = true;
  page.activate();
  steps.push({
    step: "the tab is shown again after a change while hidden",
    refreshes: page.watch.refreshes,
  });

  const drawn = page.viewport.innerHTML;
  page.watch.options.onError(new Error("refresh failed"));
  assert.equal(page.viewport.innerHTML, drawn, "a failed refresh keeps the map");
  steps.push({ step: "a refresh fails after a complete answer", ...summary(page) });

  const before = page.tooltipHides.length;
  page.handle.dispose();
  page.handle.dispose();
  steps.push({
    step: "disposed",
    viewportListeners: [...page.viewport.listeners.keys()],
    controlListeners: page.controlListeners.size,
    activeListeners: page.activeListeners.size,
    watchDisposed: page.watch.disposed,
    observerDisconnected: observers[0].disconnected,
    tooltipHides: page.tooltipHides.length - before,
    hidOwnTooltipOnly: page.tooltipHides.at(-1) === page.container,
  });

  // ── the breakdown's request fails, and Retry recovers ─────────
  const retried = mount();
  retried.handle.follow(null);
  steps.push({ step: "the breakdown's request fails", ...summary(retried) });
  retried.handle.refresh();
  retried.handle.follow(breakdownAnswer("done", TREE));
  retried.watch.apply({ index_status: "done", node: TREE });
  steps.push({
    step: "Retry: the breakdown answers, and the map follows",
    hidden: retried.container.hidden,
    drawn: retried.viewport.cells.length > 0,
  });
  retried.handle.dispose();

  // ── the map's own first rollup fails, and Retry recovers ──────
  const failing = mount();
  failing.handle.follow(breakdownAnswer("done", TREE));
  failing.watch.options.onError(new Error("no rollup"));
  steps.push({ step: "the map's first rollup fails", ...summary(failing) });
  failing.handle.refresh();
  failing.watch.apply({ index_status: "done", node: TREE });
  steps.push({
    step: "Retry: the map asks again, and its tree arrives",
    refreshes: failing.watch.refreshes,
    hidden: failing.container.hidden,
    drawn: failing.viewport.cells.length > 0,
  });
  failing.handle.dispose();

  // ── an index stopped at its cap before finishing this folder ──
  const capped = mount();
  capped.handle.follow(breakdownAnswer("truncated", TREE, "pending"));
  steps.push({ step: "the index stopped at its cap mid-folder", ...summary(capped) });
  capped.handle.dispose();

  // ── an empty folder, and one whose files are all ignored ──────
  const empty = mount();
  empty.handle.follow(breakdownAnswer("done", EMPTY));
  steps.push({ step: "the folder is empty", ...summary(empty) });
  empty.handle.dispose();

  const ignored = mount();
  ignored.setControls({ metric: "size", includeIgnored: false });
  ignored.handle.follow(breakdownAnswer("done", ONLY_IGNORED));
  steps.push({ step: "every file is ignored, and Show ignored is off", ...summary(ignored) });
  ignored.setControls({ metric: "size", includeIgnored: true });
  steps.push({ step: "Show ignored is turned on", ...summary(ignored) });
  ignored.handle.dispose();

  // ── a box too small to draw in yet ────────────────────────────
  const narrow = mount({ width: 6 });
  narrow.handle.follow(breakdownAnswer("done", TREE));
  narrow.watch.apply({ index_status: "done", node: TREE });
  steps.push({ step: "the box is too narrow to draw in", ...summary(narrow) });
  narrow.resize(600);
  steps.push({
    step: "the pane widens",
    hidden: narrow.container.hidden,
    drawn: narrow.viewport.cells.length > 0,
  });
  narrow.handle.dispose();

  console.log(JSON.stringify({ steps, warnings }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
