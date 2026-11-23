// Run the production compact treemap (treemap-compact.js, over treemap-map.js and
// treemap-layout.js) through its states: the skeleton while the rollup is on its way,
// the drawn tree once the index has finished, the section's legend hover marking a
// family's cells, activation, a control change, a failed refresh that keeps the map, and
// stepping out of the section when the first rollup fails or the folder is empty.
// Disposal releases every listener, the watch, and the observer, and puts away only the
// map's own tooltip.
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
  constructor(index, kind, pathName, classes) {
    this.dataset = { tmCell: String(index), tmKind: kind, tmPath: pathName };
    this.classes = classes;
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
      /<div class="([^"]*)"[^>]*data-tm-cell="(\d+)" data-tm-kind="(\w+)" data-tm-path="([^"]*)"/g;
    for (const match of html.matchAll(pattern)) {
      this.cells.push(new FakeCell(Number(match[2]), match[3], match[4], match[1].split(" ")));
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

function file(name, filePath, size, ext) {
  return { name, path: filePath, type: "file", size, ext, gitignored: false, mtime: 1 };
}

function dir(name, dirPath, children) {
  const files = children.reduce((sum, c) => sum + (c.type === "dir" ? c.total_files : 1), 0);
  const size = children.reduce((sum, c) => sum + (c.type === "dir" ? c.total_size : c.size), 0);
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
    unignored_files: files,
    unignored_size: size,
    gitignored: false,
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
]);

async function main() {
  // A failed rollup is logged; the session reports those lines as data instead.
  const warnings = [];
  console.warn = (message) => warnings.push(String(message));
  const { createDistributionHover } = await import(folder("distribution-hover.js"));
  const { mountCompactTreemap } = await import(folder("treemap-compact.js"));

  global.window = {
    METABROWSER_SETTINGS: { ROLLUP_MAX_DEPTH: 12, ROLLUP_MAX_TOP: 200 },
  };
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
  function mount() {
    const navigation = [];
    const tooltipHides = [];
    const watch = { options: null, apply: null, disposed: false };
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
        watch.options = options;
        watch.apply = apply;
        return {
          dispose() {
            watch.disposed = true;
          },
          refresh: async () => {},
          stale: () => false,
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
    const handle = mountCompactTreemap(container, { path: "src" }, mb, palette, controls, {
      hover,
    });
    const viewport = container.children[0];
    // The box the stylesheet gives the compact map, inside its border.
    viewport.clientWidth = 600;
    viewport.clientHeight = 218;
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
      resize() {
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
    cells: page.viewport.cells.map((cell) => `${cell.dataset.tmKind} ${cell.dataset.tmPath}`),
  });
  const steps = [];

  // ── a folder whose rollup arrives ─────────────────────────────
  const page = mount();
  steps.push({
    step: "mounted, before any answer",
    request: {
      depth: page.watch.options.depth,
      top: page.watch.options.top,
      ext_top: page.watch.options.ext_top,
      filename_top: page.watch.options.filename_top,
      remaining_top: page.watch.options.remaining_top,
    },
    ...summary(page),
  });

  page.watch.apply({ index_status: "scanning", node: { ...TREE, state: "pending" } });
  steps.push({ step: "the index is still scanning", ...summary(page) });

  page.resize();
  page.watch.apply({ index_status: "done", node: TREE });
  // Every cell fits inside the border: the map lays out to the client box, not to the
  // bounding box, which is larger by the border and pushed edge cells under it.
  const boxes = [
    ...page.viewport.innerHTML.matchAll(
      /left:([\d.]+)px;top:([\d.]+)px;width:([\d.]+)px;height:([\d.]+)px/g,
    ),
  ].map((m) => m.slice(1).map(Number));
  const insideBorder = boxes.every(
    ([left, top, width, height]) =>
      left + width <= page.viewport.clientWidth && top + height <= page.viewport.clientHeight,
  );
  steps.push({ step: "the index has finished", insideBorder, ...summary(page) });

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
  for (const target of ["src/lib/app.py", "src/docs"]) {
    const cell = page.viewport.cells.find((c) => c.dataset.tmPath === target);
    if (cell) {
      click({ target: cell });
    }
  }
  steps.push({ step: "activating a file cell and a folder cell", navigation: page.navigation });

  page.setControls({ metric: "files", includeIgnored: true });
  steps.push({ step: "the measure switches to Files", ...summary(page) });

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

  // ── a folder whose first rollup fails ─────────────────────────
  const failing = mount();
  failing.watch.options.onError(new Error("no rollup"));
  steps.push({ step: "the first rollup fails", ...summary(failing) });
  failing.handle.dispose();

  // ── an empty folder ───────────────────────────────────────────
  const empty = mount();
  empty.watch.apply({ index_status: "done", node: dir("src", "src", []) });
  steps.push({ step: "the folder is empty", ...summary(empty) });
  empty.handle.dispose();

  console.log(JSON.stringify({ steps, warnings }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
