// Behavioral test for the folder built-in plugin.
//
// Loads the real SDK, layout module, and folder index.js into a vm
// sandbox with a minimal DOM stub, then drives both registered views:
// README empty state, treemap toolbar + cells from a stubbed
// /api/rollup envelope, watchRollup refresh on inventory-change
// events, parent-folder navigation, toggle relayout without refetch,
// and dispose detaching the listeners.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];
function check(name, cond, detail) {
  if (!cond) {
    failures.push(`${name}: ${detail || "failed"}`);
  }
}

// ── Minimal DOM stub ────────────────────────────────────────────
// The treemap map builds its layers with createElement and appendChild, paints on a
// canvas, and puts a hover anchor in the viewport, so an element keeps its children; markup
// written to innerHTML replaces them, as a placeholder replaces the map's layers.
/** Every canvas context the map asked for, which records what it filled and in what. */
const canvasContexts = [];
function makeCanvasContext() {
  const ctx = {
    fillStyle: "",
    globalAlpha: 1,
    fills: [],
    setTransform() {},
    clearRect() {},
    drawImage() {},
    fillRect(x, y, w, h) {
      ctx.fills.push({ fillStyle: ctx.fillStyle, x, y, w, h });
    },
  };
  canvasContexts.push(ctx);
  return ctx;
}
function makeElement(tag = "div") {
  let markup = "";
  const el = {
    tagName: String(tag).toUpperCase(),
    get innerHTML() {
      return markup;
    },
    set innerHTML(value) {
      markup = String(value);
      for (const child of el.children) {
        child.parentNode = null;
      }
      el.children = [];
    },
    parentNode: null,
    className: "",
    hidden: false,
    listeners: {},
    attributes: {},
    dataset: {},
    style: {},
    appendChild(child) {
      child.remove?.();
      child.parentNode = el;
      el.children.push(child);
      return child;
    },
    insertBefore(child, reference) {
      child.remove?.();
      child.parentNode = el;
      const at = el.children.indexOf(reference);
      el.children.splice(at === -1 ? el.children.length : at, 0, child);
      return child;
    },
    remove() {
      if (el.parentNode) {
        el.parentNode.children = el.parentNode.children.filter((child) => child !== el);
        el.parentNode = null;
      }
    },
    getAttribute(k) {
      return k in el.attributes ? el.attributes[k] : null;
    },
    removeAttribute(k) {
      delete el.attributes[k];
    },
    addEventListener(type, fn) {
      el.listeners[type] = el.listeners[type] || [];
      el.listeners[type].push(fn);
    },
    removeEventListener(type, fn) {
      const listeners = el.listeners[type] || [];
      const index = listeners.indexOf(fn);
      if (index !== -1) {
        listeners.splice(index, 1);
      }
    },
    contains() {
      return true;
    },
    querySelector(selector) {
      if (selector === ".tm-viewport") {
        return el.viewport;
      }
      if (selector === ".tm-status") {
        return el.status;
      }
      if (selector === ".tm-totals") {
        return el.totals;
      }
      if (selector === ".tm-rollup-controls") {
        return el.rollupControls;
      }
      if (selector === ".tm-parent-nav") {
        return el.parentNav;
      }
      if (selector === ".tm-legend") {
        el.legend ??= makeElement();
        return el.legend;
      }
      return null;
    },
    children: [],
    replaceChildren(...children) {
      el.children = children;
    },
    querySelectorAll() {
      return [];
    },
    getBoundingClientRect: () => ({ width: 800, height: 600, top: 120, left: 0 }),
    setAttribute(k, v) {
      el.attributes[k] = v;
    },
    classList: { add() {}, remove() {}, contains: () => false },
  };
  if (el.tagName === "CANVAS") {
    // One context a canvas, as a browser keeps.
    el.getContext = () => {
      el.context ??= makeCanvasContext();
      return el.context;
    };
  }
  return el;
}

const windowListeners = {};
const sandbox = {
  console,
  Math,
  Date,
  Map,
  Set,
  Promise,
  URL,
  JSON,
  Number,
  Array,
  Object,
  performance,
  setTimeout: (fn, _ms) => {
    pendingTimers.push(fn);
    return pendingTimers.length;
  },
  clearTimeout: () => {},
  addEventListener(type, fn) {
    windowListeners[type] = windowListeners[type] || [];
    windowListeners[type].push(fn);
  },
  removeEventListener(type, fn) {
    const arr = windowListeners[type] || [];
    const idx = arr.indexOf(fn);
    if (idx !== -1) {
      arr.splice(idx, 1);
    }
  },
  dispatchEvent(evt) {
    for (const fn of windowListeners[evt.type] || []) {
      fn(evt);
    }
    return true;
  },
  CustomEvent: class CustomEvent {
    constructor(type, opts) {
      this.type = type;
      this.detail = opts ? opts.detail : undefined;
    }
  },
  innerHeight: 1000,
  localStorage: {
    _data: {},
    getItem(k) {
      return this._data[k] ?? null;
    },
    setItem(k, v) {
      this._data[k] = String(v);
    },
  },
  location: { origin: "http://127.0.0.1:8411" },
  document: {
    addEventListener() {},
    createElement: (tag) => makeElement(tag),
    querySelector: () => null,
    querySelectorAll: () => [],
  },
};
let pendingTimers = [];
sandbox.window = sandbox;
// One device pixel per CSS pixel, so the map paints the same on every host.
sandbox.devicePixelRatio = 1;
// The map reads each paint style from a probe element styled as a cell of that style.
// This cascade resolves an element's background to its inline style, so what a canvas
// fills names the palette style its probe was given.
const probedClasses = [];
// Each probe's classes and inline style, as the map styled it.
const probedStyles = [];
sandbox.getComputedStyle = (element) => {
  probedClasses.push(element.className);
  probedStyles.push({ className: element.className, style: element.getAttribute?.("style") ?? "" });
  return { backgroundColor: element.getAttribute?.("style") ?? "", opacity: "1" };
};
// The shell's tooltip, recording what each hide is given: the map's disposal puts away only
// its own tooltip, never another surface's (mb-alff).
const tooltipHides = [];
sandbox.MetabrowserTooltip = { show() {}, hide: (within) => tooltipHides.push(within) };
sandbox.globalThis = sandbox;
sandbox.MetabrowserFileTypeTaxonomy = {
  groups: [],
  families: [],
  matchExtension: () => null,
  canonicalExtension: (extension) => extension,
  groupForFile: () => "other",
  distributionKeyForExtension(extension) {
    if (extension === ".py") {
      return "family:python";
    }
    if (extension === ".md") {
      return "family:markdown";
    }
    return extension;
  },
};

const fetchCalls = [];
const envelope = {
  root: "/tmp/x",
  path: "",
  index_status: "done",
  indexed_files: 4,
  max_files: 500000,
  truncated: false,
  ext_tallies: [
    [".py", 2, 900, 2, 900],
    [".md", 1, 100, 0, 0],
    [".txt", 1, 50, 1, 50],
  ],
  file_type_breakdown: {
    groups: [{ id: "code", families: [{ id: "python" }] }],
    remaining_types: { extensions: [{ extension: ".txt" }] },
  },
  node: {
    name: "root",
    path: "",
    type: "dir",
    state: "complete",
    total_files: 4,
    total_size: 1050,
    unignored_files: 3,
    unignored_size: 950,
    mtime: 1700000000,
    gitignored: false,
    dominant_ext: ".py",
    children: [
      {
        name: "a.py",
        path: "a.py",
        type: "file",
        size: 600,
        mtime: 1700000000,
        ext: ".py",
        gitignored: false,
      },
      {
        name: "b.py",
        path: "b.py",
        type: "file",
        size: 300,
        mtime: 1700000000,
        ext: ".py",
        gitignored: false,
      },
      {
        name: "c.md",
        path: "c.md",
        type: "file",
        size: 100,
        mtime: 1700000000,
        ext: ".md",
        gitignored: true,
      },
      {
        name: "docs",
        path: "docs",
        type: "dir",
        state: "complete",
        total_files: 1,
        total_size: 50,
        unignored_files: 1,
        unignored_size: 50,
        mtime: 1700000000,
        dominant_ext: ".txt",
        gitignored: false,
        children: [],
      },
    ],
  },
};
/** What the next rollups answer instead of `envelope`, when a step sets it. */
let rollupOverride = null;
/** The tree without its gitignored nodes, as the route emits it for ignored=exclude. */
function withoutIgnored(node) {
  return {
    ...node,
    children: Array.isArray(node.children)
      ? node.children.filter((child) => !child.gitignored).map(withoutIgnored)
      : node.children,
  };
}
sandbox.fetch = async (url) => {
  fetchCalls.push(String(url));
  const exclude = new URL(String(url)).searchParams.get("ignored") === "exclude";
  const body = JSON.parse(JSON.stringify(envelope));
  if (exclude) {
    body.node = withoutIgnored(body.node);
  }
  return rollupOverride ?? { ok: true, json: async () => body };
};

vm.createContext(sandbox);
for (const relative of [
  "src/metabrowser/static/request-error.js",
  "src/metabrowser/static/formatters.js",
  "src/metabrowser/static/inventory-scope.js",
  "src/metabrowser/static/directory-totals-store.js",
  "src/metabrowser/static/resource-context.js",
  "src/metabrowser/static/view-state.js",
  "src/metabrowser/static/navigation.js",
  "src/metabrowser/static/plugin-sdk.js",
  "src/metabrowser/static/plugin-sdk-views.js",
  "src/metabrowser/static/filter-controls.js",
  "src/metabrowser/static/menus.js",
]) {
  const source = fs.readFileSync(path.join(repoRoot, relative), "utf8");
  vm.runInContext(source, sandbox, { filename: relative });
}
// In dependency order, since each runs in the one sandbox with its imports taken out:
// folder-totals.js and the treemap import the hover they share, the treemap the legend, and
// folder-totals.js the summary model's icon paths, which this harness leaves out since it
// stubs buildFolderTotalsComposition below;
// the map component the layout, the hit grid, and the paint list; the treemap its decoder.
const moduleSources = [
  "src/metabrowser/builtin_plugins/folder/distribution-hover.js",
  "src/metabrowser/builtin_plugins/folder/distribution-legend.js",
  "src/metabrowser/builtin_plugins/folder/folder-totals.js",
  "src/metabrowser/builtin_plugins/folder/treemap-layout.js",
  "src/metabrowser/builtin_plugins/folder/treemap-hit.js",
  "src/metabrowser/builtin_plugins/folder/treemap-paint.js",
  "src/metabrowser/builtin_plugins/folder/treemap-map.js",
  "src/metabrowser/builtin_plugins/folder/treemap-model.js",
  "src/metabrowser/builtin_plugins/folder/treemap-rollup-decode.js",
  "src/metabrowser/builtin_plugins/folder/rollup-controls.js",
];
for (const relative of moduleSources) {
  const source = fs
    .readFileSync(path.join(repoRoot, relative), "utf8")
    .replace(/^import\s[^;]*;$/gm, "")
    .replace(/^export\s*\{[^}]*\};$/gm, "")
    .replace(/^export\s+/gm, "");
  vm.runInContext(source, sandbox, { filename: relative });
}
const treemapSource = fs
  .readFileSync(path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/treemap.js"), "utf8")
  // Spans the whole statement, so a formatter-wrapped multi-line import
  // is stripped as completely as a single-line one.
  .replace(/^import\s[^;]*;$/gm, "")
  .replace("export function registerTreemap", "function registerTreemap");
const treemapStyles = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/styles.css"),
  "utf8",
);
vm.runInContext(treemapSource, sandbox, { filename: "treemap.js" });
vm.runInContext(
  `function normalizeFolderTotals(value) { return value || {state: "pending"}; }
   function normalizeRollupEnvelope(raw) {
     if (!raw || typeof raw !== "object") { throw new TypeError("bad envelope"); }
     return { registry: {revision: 1}, totals: {}, breakdown: raw.file_type_breakdown };
   }
   function buildFileTypeLegendModel() { return { legend: [], caption: "" }; }
   function buildFolderTotalsComposition(envelope, _fileTypes, metric) {
     return envelope
       ? {metric, all: {segments: []}, files: {segments: []}, ignored: {segments: []}}
       : null;
   }
   function mountFolderTotalsView(container, value, _mb, metric) {
     container.value = value;
     container.metric = metric;
     container.composition = undefined;
     container.compositionPalette = undefined;
     return {
       dispose() { container.disposed = true; },
       resumeLoading() { container.stoppedLoading = false; },
       stopLoading() { container.stoppedLoading = true; },
       update(next) { container.value = next; },
       updateMetric(next) { container.metric = next; },
       updateComposition(next, palette) {
         container.composition = next;
         container.compositionPalette = palette;
       }
     };
   }`,
  sandbox,
);
const fileIconCalls = [];
sandbox.MetabrowserFileTypes = {
  iconFor(name) {
    fileIconCalls.push(name);
    return {
      svg: `<svg data-file-icon="${name}"></svg>`,
      cls: name.endsWith(".md") ? "ft-md" : "ft-code",
    };
  },
};
vm.runInContext(
  `registerTreemap(metabrowser, {
    classFor(key) {
      return key ? "mb-distribution-mark" : "mb-distribution-other";
    },
    styleFor(key) {
      if (key === "family:python") return "--mb-distribution-color-light:python;";
      if (key === "family:markdown") return "--mb-distribution-color-light:markdown;";
      return key ? "--mb-distribution-color-light:other-type;" : "";
    },
    paint(element, key) {
      element.classList.add(key ? "mb-distribution-mark" : "mb-distribution-other");
    },
  }, createFolderRollupControls(metabrowser));`,
  sandbox,
);

const mb = sandbox.metabrowser;
check("treemap view registered", !!mb.getRegisteredView("folder", "treemap"));
check(
  "public directory totals store is read-only",
  typeof mb.directoryTotals.get === "function" &&
    typeof mb.directoryTotals.subscribe === "function" &&
    mb.directoryTotals.applySnapshot === undefined &&
    mb.directoryTotals.applyChange === undefined,
);
const navigationCalls = [];
sandbox.MetabrowserNavigationRoute.attachController({
  current() {
    return null;
  },
  open(target, options) {
    navigationCalls.push({ target, options });
    return Promise.resolve();
  },
});

// ── Treemap view: toolbar, cells, refresh, toggle, dispose ──────
(async () => {
  let invalidViewRejected = false;
  try {
    await mb.navigation.open({ path: "docs" }, { viewId: "" });
  } catch (error) {
    invalidViewRejected = error.message.includes("options.viewId");
  }
  check("navigation rejects an empty preferred view", invalidViewRejected);

  const container = makeElement();
  container.viewport = makeElement();
  container.status = makeElement();
  container.totals = makeElement();
  container.rollupControls = makeElement();
  const metricChips = ["files", "size"].map((value) => {
    const attributes = {
      "aria-checked": value === "files" ? "true" : "false",
      "data-chip-value": value,
      tabindex: value === "files" ? "0" : "-1",
    };
    return {
      getAttribute(name) {
        return attributes[name] ?? null;
      },
      setAttribute(name, next) {
        attributes[name] = String(next);
      },
    };
  });
  container.rollupControls.querySelectorAll = (selector) =>
    selector === '[data-chip-group="folder-rollup-metric"] [data-chip-value]' ? metricChips : [];
  container.viewport.textContent = "";
  Object.defineProperty(container.viewport, "textContent", {
    set() {},
    get() {
      return "";
    },
  });
  Object.defineProperty(container.status, "textContent", {
    set(v) {
      container.status._text = v;
    },
    get() {
      return container.status._text || "";
    },
  });

  const view = mb.getRegisteredView("folder", "treemap");
  sandbox.MetabrowserViewState.setActive(container, true);
  sandbox.metabrowserDirectoryTotalsStore.applySnapshot([
    {
      path: "",
      type: "dir",
      total_files: null,
      total_size: null,
      unignored_files: null,
      unignored_size: null,
    },
  ]);
  const mounted = view.render(container, {
    path: "",
    kind: "folder",
    raw: {
      readme_path: "README.md",
      dir: {
        total_files: 4,
        total_size: 1050,
        unignored_files: 3,
        unignored_size: 950,
      },
    },
  });
  check(
    "pending cache entries never replace complete first-frame totals",
    container.totals.value.total_files === 4 &&
      container.totals.value.total_size === 1050 &&
      container.totals.metric === "files",
    JSON.stringify({ value: container.totals.value, metric: container.totals.metric }),
  );
  check(
    "Files heading precedes the treemap",
    container.innerHTML.includes('<h2 class="section-heading tm-totals-heading">Files</h2>'),
    container.innerHTML,
  );
  check("shared controls rendered", container.innerHTML.includes("folder-rollup-controls"));
  check(
    "Treemap root omits parent navigation",
    !container.innerHTML.includes("tm-parent-nav"),
    container.innerHTML,
  );
  check(
    "metric chooser present",
    container.rollupControls.innerHTML.includes('data-chip-key="folder-rollup-metric"'),
  );
  check(
    "metric chooser is Files then Bytes with Files selected",
    container.rollupControls.innerHTML.indexOf('data-chip-value="files"') <
      container.rollupControls.innerHTML.indexOf('data-chip-value="size"') &&
      container.rollupControls.innerHTML.includes(
        'data-chip-value="files" role="radio" aria-checked="true" tabindex="0"',
      ),
    container.rollupControls.innerHTML,
  );
  check(
    "obsolete grouping and color choices absent",
    !container.innerHTML.includes('data-chip-key="grouping"') &&
      !container.innerHTML.includes('data-chip-key="color"') &&
      !container.innerHTML.includes(">Folders<") &&
      !container.innerHTML.includes(">Types<") &&
      !container.innerHTML.includes(">Age<"),
    container.innerHTML,
  );
  check(
    "the measure and the gitignore switch share one control row, as in Overview",
    container.rollupControls.innerHTML.includes('data-chip-key="folder-rollup-metric"') &&
      container.rollupControls.innerHTML.includes('data-chip-check="folder-rollup-ignored"'),
    container.rollupControls.innerHTML,
  );
  check(
    "ignored scope defaults to a checked checkbox",
    container.rollupControls.innerHTML.includes('type="checkbox"') &&
      container.rollupControls.innerHTML.includes('data-chip-check="folder-rollup-ignored"') &&
      container.rollupControls.innerHTML.includes(
        'data-chip-check="folder-rollup-ignored" checked',
      ) &&
      container.rollupControls.innerHTML.includes("Show ignored"),
    container.rollupControls.innerHTML,
  );

  // Initial watchRollup fetch resolves through several microtasks; a
  // host setImmediate drains the whole promise-job queue.
  await new Promise((resolve) => setImmediate(resolve));
  check("initial fetch", fetchCalls.length === 1, `${fetchCalls.length} fetches`);
  // The tally above the map is the same component the Overview tab shows,
  // so it has to be fed the same file-type segments and palette; without
  // a composition it degrades to one flat neutral bar.
  check(
    "treemap tally carries the Overview's file-type composition",
    container.totals.composition?.metric === "files" && !!container.totals.compositionPalette,
    JSON.stringify({
      composition: container.totals.composition,
      palette: !!container.totals.compositionPalette,
    }),
  );
  // The map paints its cells on a canvas and keeps labels, a focus proxy, and a hover
  // anchor in the DOM; what it drew is read through its inspection (treemap-map.js).
  const drawnMap = (pane = container) => sandbox.inspectTreemap(pane.viewport);
  const layerOf = (pane, className) =>
    pane.viewport.children.find((child) => child.className === className) ?? null;
  /** The index of the drawn folder or file cell at `cellPath`, or -1. */
  const cellIndexOf = (pane, cellPath) =>
    (drawnMap(pane)?.cells ?? []).findIndex(
      (cell) => cell.path === cellPath && cell.kind !== "rest",
    );
  /** The label element over the drawn cell at `cellPath`, or null. */
  const labelFor = (pane, cellPath) => {
    const index = cellIndexOf(pane, cellPath);
    return (
      layerOf(pane, "tm-labels")?.children.find(
        (element) => Number(element.dataset.tmCell) === index,
      ) ?? null
    );
  };
  const labelsMarkup = (pane) =>
    (layerOf(pane, "tm-labels")?.children ?? [])
      .map(
        (element) => `${element.className} ${element.getAttribute("style")} ${element.innerHTML}`,
      )
      .join("\n");
  /** The client coordinates of a point in cell `index`, its center unless `at` names one. */
  const clientAt = (pane, index, at) => {
    const cell = drawnMap(pane).cells[index];
    const point = at ?? { x: cell.x + cell.w / 2, y: cell.y + cell.h / 2 };
    const rect = pane.viewport.getBoundingClientRect();
    return { clientX: rect.left + point.x, clientY: rect.top + point.y };
  };
  /** What the browser sends the viewport, which takes every pointer and key event itself. */
  const dispatch = (pane, type, init = {}) => {
    const event = {
      type,
      target: pane.viewport,
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
      ...init,
    };
    for (const fn of [...(pane.viewport.listeners[type] || [])]) {
      fn(event);
    }
    return event;
  };
  const geometry = (pane) =>
    JSON.stringify(
      (drawnMap(pane)?.cells ?? []).map((cell) => [cell.path, cell.x, cell.y, cell.w, cell.h]),
    );

  check(
    "cells rendered",
    drawnMap()?.cells.some((cell) => cell.path === "a.py") === true &&
      drawnMap().paint.length > 0 &&
      ["tm-paint", "tm-marks", "tm-labels", "tm-focus"].every((name) => layerOf(container, name)),
    JSON.stringify(container.viewport.children.map((child) => child.className)),
  );
  {
    // The map lays out to the viewport's padding box (clientWidth and
    // clientHeight, inside its border), not to its bounding box, which is
    // larger by the border: laying out to that pushed the right- and
    // bottom-edge cells under the border. What is painted is the paint list,
    // in device pixels, one a CSS pixel here.
    container.viewport.clientWidth = 798;
    container.viewport.clientHeight = 598;
    sandbox.dispatchEvent(new sandbox.CustomEvent("resize"));
    const rects = drawnMap().paint;
    const reach = rects.reduce(
      (most, rect) => [Math.max(most[0], rect.x + rect.w), Math.max(most[1], rect.y + rect.h)],
      [0, 0],
    );
    check(
      "cells lay out inside the viewport's client box, not its bounding box",
      rects.length > 0 && reach[0] <= 798 && reach[1] <= 598 && reach[0] > 790,
      JSON.stringify({ rects: rects.length, reach }),
    );
    delete container.viewport.clientWidth;
    delete container.viewport.clientHeight;
    sandbox.dispatchEvent(new sandbox.CustomEvent("resize"));
  }
  {
    // A folder's accessible name is the focus proxy's while it is on the folder.
    const docsIndex = cellIndexOf(container, "docs");
    for (let step = 0; step < drawnMap().focusOrder.length; step += 1) {
      if (drawnMap().focused === docsIndex) {
        break;
      }
      dispatch(container, "keydown", { key: "ArrowRight" });
    }
    const proxy = layerOf(container, "tm-focus");
    check(
      "folder labels carry a trailing slash without changing the accessible name",
      (labelFor(container, "docs")?.innerHTML ?? "").includes(
        '<span class="tm-cell-label">docs/</span>',
      ) &&
        drawnMap().focused === docsIndex &&
        String(proxy?.getAttribute("aria-label")).startsWith("docs (folder,"),
      `${labelsMarkup(container)}\n${proxy?.getAttribute("aria-label")}`,
    );
  }
  check(
    "file cells use the shared file identity icon",
    (labelFor(container, "a.py")?.innerHTML ?? "").includes(
      "file-identity-icon tm-cell-file-icon ft-code",
    ) &&
      labelFor(container, "a.py").innerHTML.includes('data-file-icon="a.py"') &&
      fileIconCalls.includes("a.py"),
    labelsMarkup(container),
  );
  check(
    "Treemap hover is one whole-cell treatment",
    !treemapStyles.includes('.tm-cell-title[role="button"]:hover') &&
      !treemapStyles.includes("border-color: var(--viz-border-strong)") &&
      treemapStyles.includes("filter: var(--viz-data-mark-hover-filter)"),
    treemapStyles,
  );
  {
    // The whole painted rectangle of a folder or file cell is its pointer target, from
    // corner to corner, and the viewport shows the pointer cursor over it; the edge past
    // it is its parent's. A remainder cell, which opens nothing, shows no cursor. The
    // paint is in device pixels, one a CSS pixel here.
    const pointerOver = [];
    for (const cellPath of ["docs", "a.py"]) {
      const index = cellIndexOf(container, cellPath);
      const fill = drawnMap().paint.find((rect) => rect.cell === index && rect.tone === "fill");
      for (const at of [
        { x: fill.x + 0.5, y: fill.y + 0.5 },
        { x: fill.x + fill.w / 2, y: fill.y + fill.h / 2 },
        { x: fill.x + fill.w - 0.5, y: fill.y + fill.h - 0.5 },
        { x: fill.x + fill.w + 0.5, y: fill.y + fill.h / 2 },
      ]) {
        dispatch(container, "mousemove", clientAt(container, index, at));
        pointerOver.push(
          `${cellPath} ${drawnMap().hovered === index ? "hovered" : "missed"} ${container.viewport.style.cursor || "no cursor"}`,
        );
      }
    }
    dispatch(container, "mouseleave");
    pointerOver.push(`left ${container.viewport.style.cursor || "no cursor"}`);

    rollupOverride = {
      ok: true,
      json: async () => {
        const body = JSON.parse(JSON.stringify(envelope));
        body.node.rest = { files: 2, size: 200, unignored_files: 2, unignored_size: 200 };
        return body;
      },
    };
    const restPane = makeElement();
    restPane.viewport = makeElement();
    restPane.status = makeElement();
    restPane.totals = makeElement();
    restPane.rollupControls = makeElement();
    sandbox.MetabrowserViewState.setActive(restPane, true);
    const restShown = view.render(restPane, { path: "", kind: "folder", raw: {} });
    await new Promise((resolve) => setImmediate(resolve));
    rollupOverride = null;
    const restIndex = (drawnMap(restPane)?.cells ?? []).findIndex((cell) => cell.kind === "rest");
    const navigationsBeforeRest = navigationCalls.length;
    if (restIndex >= 0) {
      dispatch(restPane, "mousemove", clientAt(restPane, restIndex));
      pointerOver.push(
        `the remainder ${drawnMap(restPane).hovered === restIndex ? "hovered" : "missed"} ${restPane.viewport.style.cursor || "no cursor"}`,
      );
      dispatch(restPane, "click", clientAt(restPane, restIndex));
    }
    restShown.dispose();

    // An extension keeps any character but a slash, a `|` among them: the cell still
    // paints in its own family, dimmed as ignored, and not as a family its key's first
    // part names.
    rollupOverride = {
      ok: true,
      json: async () => {
        const body = JSON.parse(JSON.stringify(envelope));
        body.node.children.push({
          name: "x.b|c",
          path: "x.b|c",
          type: "file",
          size: 400,
          mtime: 1700000000,
          ext: ".b|c",
          gitignored: true,
        });
        return body;
      },
    };
    const pipePane = makeElement();
    pipePane.viewport = makeElement();
    pipePane.status = makeElement();
    pipePane.totals = makeElement();
    pipePane.rollupControls = makeElement();
    sandbox.MetabrowserViewState.setActive(pipePane, true);
    const probesBefore = probedStyles.length;
    const pipeShown = view.render(pipePane, { path: "", kind: "folder", raw: {} });
    await new Promise((resolve) => setImmediate(resolve));
    rollupOverride = null;
    // The palette files a family it does not know as other-type, so x.b|c is the one
    // ignored cell of that style; misread, its key's later parts said not ignored and
    // still scanning.
    const pipeProbes = probedStyles
      .slice(probesBefore)
      .filter((probe) => probe.className.includes("tm-type-fill"));
    check(
      "a cell whose extension holds a | paints in its own family, dimmed as ignored",
      cellIndexOf(pipePane, "x.b|c") >= 0 &&
        pipeProbes.some(
          (probe) => probe.style.includes("other-type") && probe.className.includes("tm-ignored"),
        ) &&
        pipeProbes.every((probe) => !probe.className.includes("tm-pending-still")),
      JSON.stringify(pipeProbes),
    );
    pipeShown.dispose();
    check(
      "actionable cells expose a whole-rectangle pointer target",
      JSON.stringify(pointerOver) ===
        JSON.stringify([
          "docs hovered pointer",
          "docs hovered pointer",
          "docs hovered pointer",
          "docs missed no cursor",
          "a.py hovered pointer",
          "a.py hovered pointer",
          "a.py hovered pointer",
          "a.py missed no cursor",
          "left no cursor",
          "the remainder hovered no cursor",
        ]) && navigationCalls.length === navigationsBeforeRest,
      JSON.stringify({ pointerOver, opened: navigationCalls.slice(navigationsBeforeRest) }),
    );
  }
  {
    // Each cell is painted in the style its probe resolves to, a probe styled with the
    // shared palette's class and style for the cell's family.
    const paintContext = layerOf(container, "tm-paint")?.context;
    const filledAs = (cellPath) => {
      const index = cellIndexOf(container, cellPath);
      const rect = drawnMap().paint.find((each) => each.cell === index && each.tone === "fill");
      const fill = (paintContext?.fills ?? []).findLast(
        (each) =>
          rect && each.x === rect.x && each.y === rect.y && each.w === rect.w && each.h === rect.h,
      );
      return fill?.fillStyle ?? null;
    };
    const fills = { "a.py": filledAs("a.py"), "c.md": filledAs("c.md") };
    check(
      "type fill always uses the shared palette",
      fills["a.py"] === "--mb-distribution-color-light:python;" &&
        fills["c.md"] === "--mb-distribution-color-light:markdown;" &&
        probedClasses.some(
          (name) => name.includes("tm-type-fill") && name.includes("mb-distribution-mark"),
        ),
      JSON.stringify({ fills, probedClasses: [...new Set(probedClasses)] }),
    );
  }
  check(
    "cell values use the common byte formatter",
    (labelFor(container, "a.py")?.innerHTML ?? "").includes("600 B"),
    labelsMarkup(container),
  );
  check(
    "cell typography is data-driven",
    String(labelFor(container, "a.py")?.getAttribute("style")).includes("--tm-label-size:") &&
      labelFor(container, "a.py").getAttribute("style").includes("--tm-value-size:"),
    labelsMarkup(container),
  );
  check(
    "obsolete age coloring is absent",
    !labelsMarkup(container).includes("tm-cell-age") &&
      !labelsMarkup(container).includes("tm-age-"),
    labelsMarkup(container),
  );
  check(
    "steady-state footer is empty",
    container.status.textContent === "",
    container.status.textContent,
  );

  const refreshFromInventoryChange = async () => {
    sandbox.dispatchEvent(
      new sandbox.CustomEvent("metabrowser:inventory-change", {
        detail: { kind: "change", paths: ["a.py"] },
      }),
    );
    const refreshTimers = pendingTimers.slice();
    pendingTimers = [];
    for (const fn of refreshTimers) {
      fn();
    }
    await new Promise((resolve) => setImmediate(resolve));
  };

  const cellsBeforeScan = drawnMap().cells;
  const labelsBeforeScan = layerOf(container, "tm-labels");
  envelope.index_status = "scanning";
  await refreshFromInventoryChange();
  check(
    "an in-progress refresh keeps the completed map and its label layer",
    !container.viewport.innerHTML.includes("tm-loading") &&
      drawnMap().cells === cellsBeforeScan &&
      layerOf(container, "tm-labels") === labelsBeforeScan,
    container.viewport.innerHTML,
  );
  envelope.index_status = "done";
  await refreshFromInventoryChange();
  check(
    "a completed refresh reuses the label layer when replacing the layout",
    !container.viewport.innerHTML.includes("tm-loading") &&
      drawnMap().cells !== cellsBeforeScan &&
      drawnMap().cells.length > 0 &&
      layerOf(container, "tm-labels") === labelsBeforeScan,
    container.viewport.innerHTML,
  );

  const folderIndex = cellIndexOf(container, "docs");
  const fileIndex = cellIndexOf(container, "a.py");
  check(
    "folder cell is actionable",
    folderIndex >= 0 &&
      drawnMap().cells[folderIndex].kind === "dir" &&
      drawnMap().focusOrder.includes(folderIndex),
    geometry(container),
  );
  check(
    "file cell is actionable",
    fileIndex >= 0 &&
      drawnMap().cells[fileIndex].kind === "file" &&
      drawnMap().focusOrder.includes(fileIndex),
    geometry(container),
  );
  const cellClick = container.viewport.listeners.click?.[0];
  check("cell click handler bound", typeof cellClick === "function");
  if (cellClick && folderIndex >= 0 && fileIndex >= 0) {
    // A click is hit-tested against the layout at its coordinates: anywhere in a cell,
    // over its label or not, takes the same route.
    dispatch(container, "click", clientAt(container, folderIndex));
    check(
      "folder background keeps Treemap active",
      navigationCalls.length === 1 &&
        navigationCalls[0].target.path === "docs" &&
        navigationCalls[0].options.viewId === "treemap",
      JSON.stringify(navigationCalls),
    );

    const folder = drawnMap().cells[folderIndex];
    dispatch(
      container,
      "click",
      clientAt(container, folderIndex, { x: folder.x + 4, y: folder.y + 4 }),
    );
    check(
      "folder label uses the same whole-cell route",
      navigationCalls.length === 2 && navigationCalls[1].target.path === "docs",
      JSON.stringify(navigationCalls),
    );

    dispatch(container, "click", clientAt(container, fileIndex));
    check(
      "a file cell opens the file outside the Treemap",
      navigationCalls.length === 3 &&
        navigationCalls[2].target.path === "a.py" &&
        navigationCalls[2].options?.viewId === undefined,
      JSON.stringify(navigationCalls),
    );
  }

  // A key held with Command, Control, or Option is the browser's: Command-R reloads,
  // Command-Left goes back in Chrome and Alt-Left elsewhere, Command-Up scrolls to the top.
  // The map's keys act only unmodified.
  const cellKeydown = container.viewport.listeners.keydown?.[0];
  check("cell keydown handler bound", typeof cellKeydown === "function");
  if (cellKeydown) {
    const navigationsBefore = navigationCalls.length;
    const swallowed = [];
    for (const key of [
      "r",
      "Enter",
      " ",
      "ArrowRight",
      "ArrowDown",
      "ArrowLeft",
      "ArrowUp",
      "Backspace",
    ]) {
      for (const modifier of ["metaKey", "ctrlKey", "altKey"]) {
        const event = {
          key,
          [modifier]: true,
          defaultPrevented: false,
          preventDefault() {
            this.defaultPrevented = true;
          },
        };
        cellKeydown(event);
        if (event.defaultPrevented) {
          swallowed.push(`${modifier} ${key}`);
        }
      }
    }
    check(
      "the map takes no key held with a modifier",
      swallowed.length === 0,
      swallowed.join(", "),
    );
    check(
      "a modified Enter or Backspace navigates nowhere",
      navigationCalls.length === navigationsBefore,
      JSON.stringify(navigationCalls.slice(navigationsBefore)),
    );
    // Unmodified, the keys work the focus proxy, the map's one control: an arrow moves it
    // to the next folder or file cell in layout order, and Enter opens the cell it is on.
    const order = drawnMap().focusOrder;
    const focusedBefore = drawnMap().focused;
    const plain = {
      key: "ArrowRight",
      defaultPrevented: false,
      preventDefault() {
        this.defaultPrevented = true;
      },
    };
    cellKeydown(plain);
    const proxy = layerOf(container, "tm-focus");
    const focusedCell = drawnMap().cells[drawnMap().focused];
    check(
      "a plain arrow still moves within the map",
      plain.defaultPrevented &&
        drawnMap().focused === order[order.indexOf(focusedBefore) + 1] &&
        proxy?.getAttribute("role") === "button" &&
        proxy.getAttribute("tabindex") === "0" &&
        !proxy.hidden &&
        String(proxy.getAttribute("aria-label")).startsWith(`${focusedCell?.name} (`),
      JSON.stringify({
        order,
        focusedBefore,
        focused: drawnMap().focused,
        label: proxy?.getAttribute("aria-label"),
      }),
    );
    const enter = dispatch(container, "keydown", { key: "Enter" });
    const opened = navigationCalls.at(-1);
    check(
      "Enter opens the cell the focus proxy is on",
      enter.defaultPrevented &&
        navigationCalls.length === navigationsBefore + 1 &&
        opened.target.path === focusedCell?.path &&
        (focusedCell?.kind === "dir"
          ? opened.options?.viewId === "treemap"
          : !opened.options?.viewId),
      JSON.stringify({ focused: focusedCell?.path, opened }),
    );

    // A relayout keeps the focus proxy on the cell it was on, so a key pressed after a
    // refresh acts on the cell the user chose, not on the first one.
    const keptPath = drawnMap().cells[drawnMap().focused]?.path;
    sandbox.dispatchEvent(new sandbox.CustomEvent("resize"));
    check(
      "a relayout keeps the focus proxy on its cell",
      drawnMap().focused !== drawnMap().focusOrder[0] &&
        drawnMap().cells[drawnMap().focused]?.path === keptPath,
      JSON.stringify({ keptPath, now: drawnMap().cells[drawnMap().focused]?.path }),
    );

    // A still pointer is looked up where the viewport is now: the viewport moving under
    // it, as when the legend's row wraps above the map, puts it over another cell.
    const pointed = cellIndexOf(container, "a.py");
    const client = clientAt(container, pointed);
    dispatch(container, "mousemove", client);
    const box = container.viewport.getBoundingClientRect;
    const shift = drawnMap().cells[pointed].h + 1;
    container.viewport.getBoundingClientRect = () => ({ ...box(), top: box().top + shift });
    sandbox.dispatchEvent(new sandbox.CustomEvent("resize"));
    const afterMove = drawnMap().hovered;
    dispatch(container, "mousemove", client);
    check(
      "a relayout looks a still pointer up where the viewport is now",
      afterMove === drawnMap().hovered && afterMove !== pointed,
      JSON.stringify({ pointed, afterMove, fresh: drawnMap().hovered }),
    );
    dispatch(container, "mouseleave");
    container.viewport.getBoundingClientRect = box;
    sandbox.dispatchEvent(new sandbox.CustomEvent("resize"));
  }

  // Viewport height is measured, not the CSS calc: innerHeight 1000
  // minus rect.top 120 minus the 64px bottom reserve.
  check(
    "viewport height measured on mount",
    container.viewport.style.height === "816px",
    container.viewport.style.height || "unset",
  );
  // Window resize re-measures; a too-short window clamps to the floor.
  sandbox.innerHeight = 300;
  sandbox.dispatchEvent(new sandbox.CustomEvent("resize"));
  check(
    "viewport height clamped at the minimum",
    container.viewport.style.height === "280px",
    container.viewport.style.height || "unset",
  );
  sandbox.innerHeight = 1000;

  // Inventory change → debounce timer → refetch.
  const refreshStart = fetchCalls.length;
  sandbox.dispatchEvent(
    new sandbox.CustomEvent("metabrowser:inventory-change", {
      detail: { kind: "change", paths: ["a.py"] },
    }),
  );
  check("debounce timer armed", pendingTimers.length > 0, "no timer");
  const timers = pendingTimers.slice();
  pendingTimers = [];
  for (const fn of timers) {
    fn();
  }
  await new Promise((resolve) => setImmediate(resolve));
  check(
    "refresh refetched",
    fetchCalls.length === refreshStart + 1,
    `${fetchCalls.length} fetches`,
  );

  // A metric change relayouts without refetching; Show ignored asks again.
  const before = fetchCalls.length;
  const filesMetricGeometry = geometry(container);
  const toolbarClick = container.rollupControls.listeners.click?.[0];
  check("toolbar click handler bound", typeof toolbarClick === "function");
  const clickMetric = (value) => {
    const group = {
      getAttribute(name) {
        return name === "data-select" ? "one" : null;
      },
    };
    const button = {
      getAttribute(name) {
        if (name === "data-chip-key") {
          return "folder-rollup-metric";
        }
        if (name === "data-chip-value") {
          return value;
        }
        if (name === "aria-checked") {
          return "false";
        }
        return null;
      },
      closest(selector) {
        if (selector === "[data-chip-key]") {
          return button;
        }
        if (selector === ".chip-group") {
          return group;
        }
        return null;
      },
    };
    toolbarClick({ target: button });
  };
  if (toolbarClick) {
    clickMetric("size");
    check("metric toggle no refetch", fetchCalls.length === before, `${fetchCalls.length}`);
    check(
      "metric toggle updates the visible totals measure",
      container.totals.metric === "size",
      container.totals.metric,
    );
    check(
      "metric toggle recomposes the tally segments",
      container.totals.composition?.metric === "size",
      JSON.stringify(container.totals.composition),
    );
    check(
      "metric toggle changes cell geometry",
      geometry(container) !== filesMetricGeometry,
      "Bytes and Files produced identical cells",
    );
    check(
      "metric chooser reflects the active metric",
      container.rollupControls.innerHTML.includes(
        'data-chip-value="size" role="radio" aria-checked="true" tabindex="0"',
      ),
      container.rollupControls.innerHTML,
    );
    clickMetric("files");
    check(
      "Files metric keeps useful formatted bytes on file leaves",
      container.rollupControls.innerHTML.includes(
        'data-chip-value="files" role="radio" aria-checked="true" tabindex="0"',
      ) &&
        (labelFor(container, "a.py")?.innerHTML ?? "").includes("600 B") &&
        container.status.textContent === "",
      labelsMarkup(container),
    );
  }

  const toolbarChange = container.rollupControls.listeners.change?.[0];
  check("ignored checkbox handler bound", typeof toolbarChange === "function");
  if (toolbarChange) {
    // The folder's sums, which a tree without its ignored nodes leaves as they were.
    const sums = (value) =>
      JSON.stringify(
        ["total_files", "total_size", "unignored_files", "unignored_size"].map(
          (key) => value?.[key],
        ),
      );
    const totalsBeforeIgnored = sums(container.totals.value);
    const totalsMetricBeforeIgnored = container.totals.metric;
    toolbarChange({
      target: {
        checked: false,
        getAttribute(name) {
          return name === "data-chip-check" ? "folder-rollup-ignored" : null;
        },
      },
    });
    check(
      "unchecked ignored scope hides ignored cells without a footer summary",
      cellIndexOf(container, "c.md") === -1 &&
        !labelsMarkup(container).includes("c.md") &&
        container.status.textContent === "",
      geometry(container),
    );
    const excludeUrl = new URL(fetchCalls.at(-1));
    check(
      "Show ignored off asks again for the tree without its ignored nodes",
      fetchCalls.length === before + 1 &&
        excludeUrl.searchParams.get("ignored") === "exclude" &&
        excludeUrl.searchParams.get("encoding") === "compact" &&
        excludeUrl.searchParams.get("nodes") === "max",
      `${fetchCalls.length - before} ${excludeUrl.search}`,
    );
    await new Promise((resolve) => setImmediate(resolve));
    check(
      "the tree without ignored nodes draws no ignored cell",
      cellIndexOf(container, "c.md") === -1 && drawnMap().cells.length > 0,
      geometry(container),
    );
    check(
      "ignored scope leaves explicit Files and Ignored context unchanged",
      sums(container.totals.value) === totalsBeforeIgnored &&
        container.totals.metric === totalsMetricBeforeIgnored,
      JSON.stringify({ value: container.totals.value, metric: container.totals.metric }),
    );
    toolbarChange({
      target: {
        checked: true,
        getAttribute(name) {
          return name === "data-chip-check" ? "folder-rollup-ignored" : null;
        },
      },
    });
    // Until the tree with ignored nodes arrives, the map keeps the one it has, laid out
    // as Show ignored off: no folder is sized by totals whose nodes are missing.
    check(
      "rechecking Show ignored keeps the map until its tree arrives",
      cellIndexOf(container, "c.md") === -1 &&
        new URL(fetchCalls.at(-1)).searchParams.get("ignored") === "include",
      `${geometry(container)} ${fetchCalls.at(-1)}`,
    );
    await new Promise((resolve) => setImmediate(resolve));
    check(
      "rechecking ignored scope restores ignored cells",
      cellIndexOf(container, "c.md") >= 0 &&
        labelsMarkup(container).includes("c.md") &&
        container.status.textContent === "",
      geometry(container),
    );

    // Out of sight, as when File Overview's own Show ignored turns it off, the view asks
    // nothing; it asks once it shows.
    const setIgnored = (checked) =>
      toolbarChange({
        target: {
          checked,
          getAttribute(name) {
            return name === "data-chip-check" ? "folder-rollup-ignored" : null;
          },
        },
      });
    sandbox.MetabrowserViewState.setActive(container, false);
    const hiddenStart = fetchCalls.length;
    setIgnored(false);
    await new Promise((resolve) => setImmediate(resolve));
    check(
      "a hidden view asks nothing when Show ignored changes",
      fetchCalls.length === hiddenStart,
      `${fetchCalls.length - hiddenStart}`,
    );
    sandbox.MetabrowserViewState.setActive(container, true);
    await new Promise((resolve) => setImmediate(resolve));
    check(
      "the view asks for the tree Show ignored names once it shows",
      fetchCalls.length === hiddenStart + 1 &&
        new URL(fetchCalls.at(-1)).searchParams.get("ignored") === "exclude" &&
        cellIndexOf(container, "c.md") === -1,
      `${fetchCalls.length - hiddenStart} ${fetchCalls.at(-1)}`,
    );

    // Show ignored on, and the tree with ignored files fails to arrive: the map keeps the
    // others and says so, until a tree with them does arrive.
    rollupOverride = { ok: false, status: 500 };
    setIgnored(true);
    await new Promise((resolve) => setImmediate(resolve));
    check(
      "a failed tree with ignored files says the map shows the others",
      cellIndexOf(container, "c.md") === -1 &&
        container.status.textContent ===
          "Could not load the ignored files; the treemap shows the others.",
      container.status.textContent,
    );
    rollupOverride = null;
    setIgnored(false);
    setIgnored(true);
    await new Promise((resolve) => setImmediate(resolve));
    check(
      "the tree with ignored files puts the statement away",
      cellIndexOf(container, "c.md") >= 0 && container.status.textContent === "",
      container.status.textContent,
    );
  }

  // Dispose detaches the inventory-change and window-resize listeners.
  const listenerCount = (windowListeners["metabrowser:inventory-change"] || []).length;
  const resizeCount = (windowListeners.resize || []).length;
  // On a cell when the map goes, so its anchor is in the viewport to take back.
  const disposeLeaf = drawnMap().cells.findIndex((cell) => cell.kind === "file");
  dispatch(container, "mousemove", clientAt(container, disposeLeaf));
  const hidesBeforeDispose = tooltipHides.length;
  const anchoredBeforeDispose = container.viewport.children.some((child) =>
    String(child.className).includes("tm-hover-anchor"),
  );
  mounted.dispose();
  check(
    "dispose takes back every element the map put in the viewport",
    anchoredBeforeDispose && container.viewport.children.length === 0,
    JSON.stringify(container.viewport.children.map((child) => child.className)),
  );
  const afterDispose = (windowListeners["metabrowser:inventory-change"] || []).length;
  check("dispose detaches listener", afterDispose === listenerCount - 1, `${afterDispose}`);
  const resizeAfter = (windowListeners.resize || []).length;
  check("dispose detaches resize listener", resizeAfter === resizeCount - 1, `${resizeAfter}`);
  check(
    "dispose hides only the map's own tooltip",
    tooltipHides.length === hidesBeforeDispose + 1 && tooltipHides.at(-1) === container,
    `${tooltipHides.length - hidesBeforeDispose}`,
  );
  check(
    "dispose releases the map's pointer and key listeners",
    Object.values(container.viewport.listeners).every((listeners) => listeners.length === 0) &&
      drawnMap() === null,
    JSON.stringify(Object.keys(container.viewport.listeners)),
  );

  // A nested Treemap identifies its enclosing folder and navigates to
  // that path without dropping back to the folder's default Overview.
  const nestedContainer = makeElement();
  nestedContainer.viewport = makeElement();
  nestedContainer.status = makeElement();
  nestedContainer.totals = makeElement();
  nestedContainer.rollupControls = makeElement();
  nestedContainer.parentNav = makeElement();
  sandbox.MetabrowserViewState.setActive(nestedContainer, true);
  const nestedMounted = view.render(nestedContainer, {
    path: "src/metabrowser",
    kind: "folder",
    raw: {
      name: "metabrowser",
      readme_path: "",
      dir: {
        total_files: 4,
        total_size: 1050,
        unignored_files: 3,
        unignored_size: 950,
      },
    },
  });
  check(
    "nested Treemap names the enclosing folder above the map",
    nestedContainer.innerHTML.includes('class="btn parent-nav-btn tm-parent-nav"') &&
      nestedContainer.innerHTML.includes(
        '<span class="parent-nav-arrow" aria-hidden="true">↑</span>',
      ) &&
      nestedContainer.innerHTML.includes('aria-label="Zoom out to src/"') &&
      nestedContainer.innerHTML.includes(">src/</span>"),
    nestedContainer.innerHTML,
  );
  const parentClick = nestedContainer.parentNav.listeners.click?.[0];
  check("parent navigation click handler bound", typeof parentClick === "function");
  if (parentClick) {
    parentClick();
    const call = navigationCalls.at(-1);
    check(
      "parent navigation preserves Treemap",
      call?.target.path === "src" && call?.options?.viewId === "treemap",
      JSON.stringify(call),
    );
  }
  // Backspace on the map asks for the same enclosing folder.
  const navigationsBeforeBackspace = navigationCalls.length;
  const backspace = dispatch(nestedContainer, "keydown", { key: "Backspace" });
  check(
    "Backspace on the map opens the enclosing folder's Treemap",
    backspace.defaultPrevented &&
      navigationCalls.length === navigationsBeforeBackspace + 1 &&
      navigationCalls.at(-1).target.path === "src" &&
      navigationCalls.at(-1).options?.viewId === "treemap",
    JSON.stringify(navigationCalls.slice(navigationsBeforeBackspace)),
  );
  const parentClickListeners = nestedContainer.parentNav.listeners.click?.length || 0;
  const hidesBeforeNestedDispose = tooltipHides.length;
  nestedMounted.dispose();
  check(
    "parent navigation listener is disposed",
    (nestedContainer.parentNav.listeners.click?.length || 0) === parentClickListeners - 1,
    `${nestedContainer.parentNav.listeners.click?.length || 0}`,
  );
  check(
    "a nested map's dispose hides only its own tooltip",
    tooltipHides.length === hidesBeforeNestedDispose + 1 && tooltipHides.at(-1) === nestedContainer,
    `${tooltipHides.length - hidesBeforeNestedDispose}`,
  );

  // ── watchRollup active-gate: hidden views spend no fetches ──────
  {
    const start = fetchCalls.length;
    let visible = true;
    const watch = mb.watchRollup("", { active: () => visible }, () => {});
    await new Promise((resolve) => setImmediate(resolve));
    check("gate: initial fetch", fetchCalls.length === start + 1, `${fetchCalls.length}`);
    visible = false;
    sandbox.dispatchEvent(
      new sandbox.CustomEvent("metabrowser:inventory-change", {
        detail: { kind: "change", paths: [""] },
      }),
    );
    const gateTimers = pendingTimers.slice();
    pendingTimers = [];
    for (const fn of gateTimers) {
      fn();
    }
    await new Promise((resolve) => setImmediate(resolve));
    check(
      "gate: hidden view skips the fetch",
      fetchCalls.length === start + 1,
      `${fetchCalls.length}`,
    );
    check("gate: watch reports stale", watch.stale() === true, String(watch.stale()));
    visible = true;
    await watch.refresh();
    check(
      "gate: refresh catches up and clears stale",
      fetchCalls.length === start + 2 && watch.stale() === false,
      `${fetchCalls.length}/${watch.stale()}`,
    );
    watch.dispose();
  }

  // ── A rollup with nothing to draw never leaves the loading skeleton ──
  {
    const answers = {
      "a refused request": { ok: false, status: 404 },
      "an index finished without the folder": {
        ok: true,
        json: async () => ({ index_status: "done", node: null }),
      },
      "a failed index": { ok: true, json: async () => ({ index_status: "failed", node: null }) },
    };
    for (const [name, answer] of Object.entries(answers)) {
      rollupOverride = answer;
      const pane = makeElement();
      pane.viewport = makeElement();
      pane.status = makeElement();
      pane.totals = makeElement();
      pane.rollupControls = makeElement();
      sandbox.MetabrowserViewState.setActive(pane, true);
      const shown = mb
        .getRegisteredView("folder", "treemap")
        .render(pane, { path: "gone", kind: "folder", raw: {} });
      await new Promise((resolve) => setImmediate(resolve));
      check(
        `treemap: ${name} says the map is unavailable`,
        pane.viewport.innerHTML.includes("Treemap unavailable.") &&
          !pane.viewport.innerHTML.includes("tm-loading"),
        pane.viewport.innerHTML,
      );
      check(`treemap: ${name} stops the totals loading`, pane.totals.stoppedLoading === true);
      shown.dispose();
    }
    // A capped index: the folders it reached draw under the notice, and one it stopped
    // before finishing has nothing more coming.
    for (const [name, node, drawn] of [
      ["a reached folder", envelope.node, true],
      ["a folder past the cap", { path: "gone", state: "pending", total_files: 0 }, false],
    ]) {
      rollupOverride = {
        ok: true,
        json: async () => ({
          ...JSON.parse(JSON.stringify(envelope)),
          index_status: "truncated",
          truncated: true,
          node,
        }),
      };
      const pane = makeElement();
      pane.viewport = makeElement();
      pane.status = makeElement();
      pane.totals = makeElement();
      pane.rollupControls = makeElement();
      sandbox.MetabrowserViewState.setActive(pane, true);
      const shown = mb
        .getRegisteredView("folder", "treemap")
        .render(pane, { path: "", kind: "folder", raw: {} });
      await new Promise((resolve) => setImmediate(resolve));
      check(
        `treemap: ${name} on a capped index carries the notice`,
        pane.status.textContent.startsWith("Only the first 500,000 files were scanned"),
        pane.status.textContent,
      );
      check(
        `treemap: ${name} on a capped index leaves no skeleton`,
        !pane.viewport.innerHTML.includes("tm-loading") &&
          pane.viewport.innerHTML.includes("Treemap unavailable.") === !drawn,
        pane.viewport.innerHTML,
      );
      shown.dispose();
    }
    // A scan still running has more to say, so its skeleton stays.
    rollupOverride = {
      ok: true,
      json: async () => ({ index_status: "scanning", node: null }),
    };
    const pane = makeElement();
    pane.viewport = makeElement();
    pane.status = makeElement();
    pane.totals = makeElement();
    pane.rollupControls = makeElement();
    sandbox.MetabrowserViewState.setActive(pane, true);
    const shown = mb
      .getRegisteredView("folder", "treemap")
      .render(pane, { path: "gone", kind: "folder", raw: {} });
    await new Promise((resolve) => setImmediate(resolve));
    check(
      "treemap: a running scan keeps its skeleton",
      pane.viewport.innerHTML.includes("tm-loading") && pane.totals.stoppedLoading !== true,
      pane.viewport.innerHTML,
    );
    shown.dispose();

    // What the map shows follows the last answer, in either direction, and the totals follow
    // the map: a failure with no map to keep ends the skeleton however the scan began, and a
    // later answer that the scan is running brings both back.
    const answer = (body) => ({ ok: true, json: async () => JSON.parse(JSON.stringify(body)) });
    const failing = { ok: false, status: 500 };
    const scanning = answer({ index_status: "scanning", node: null });
    const finishedWithout = answer({ index_status: "done", node: null });
    const complete = answer({ ...envelope, index_status: "done" });
    for (const [name, steps] of [
      [
        "a refused request, a rescan, then the folder",
        [
          [{ ok: false, status: 404 }, "unavailable", true],
          [scanning, "skeleton", false],
          [complete, "drawn", false],
        ],
      ],
      [
        "a scan, failures, a rescan, then an index without the folder",
        [
          [scanning, "skeleton", false],
          [failing, "unavailable", true],
          [failing, "unavailable", true],
          [scanning, "skeleton", false],
          [finishedWithout, "unavailable", true],
        ],
      ],
      [
        "an index without the folder, then a rescan",
        [
          [finishedWithout, "unavailable", true],
          [scanning, "skeleton", false],
        ],
      ],
      [
        "a scan with the folder pending, then a failure",
        [
          [answer({ index_status: "scanning", node: { state: "pending" } }), "skeleton", false],
          [failing, "unavailable", true],
        ],
      ],
      [
        "a scan with the folder finished, then a failure",
        [
          [answer({ ...envelope, index_status: "scanning" }), "skeleton", false],
          [failing, "unavailable", true],
        ],
      ],
      [
        "a drawn map, then a failure",
        [
          [complete, "drawn", false],
          [failing, "drawn", false],
        ],
      ],
    ]) {
      const steppedPane = makeElement();
      steppedPane.viewport = makeElement();
      steppedPane.status = makeElement();
      steppedPane.totals = makeElement();
      steppedPane.rollupControls = makeElement();
      sandbox.MetabrowserViewState.setActive(steppedPane, true);
      let stepped = null;
      for (const [index, [next, viewport, stopped]] of steps.entries()) {
        rollupOverride = next;
        if (stepped) {
          await refreshFromInventoryChange();
        } else {
          stepped = mb
            .getRegisteredView("folder", "treemap")
            .render(steppedPane, { path: "", kind: "folder", raw: {} });
        }
        await new Promise((resolve) => setImmediate(resolve));
        const markup = steppedPane.viewport.innerHTML;
        check(
          `treemap: ${name}, step ${index + 1} shows ${viewport}`,
          viewport === "skeleton"
            ? markup.includes("tm-loading")
            : viewport === "unavailable"
              ? markup.includes("Treemap unavailable.")
              : (drawnMap(steppedPane)?.cells.length ?? 0) > 0 && !markup.includes("tm-loading"),
          markup,
        );
        check(
          `treemap: ${name}, step ${index + 1} ${stopped ? "stops" : "leaves"} the totals loading`,
          (steppedPane.totals.stoppedLoading === true) === stopped,
          String(steppedPane.totals.stoppedLoading),
        );
      }
      stepped.dispose();
    }
    rollupOverride = null;
  }

  await mb.fetchRollup("override", { remaining_top: 9 });
  const overrideUrl = new URL(fetchCalls.at(-1));
  check(
    "remaining_top overrides the default and emits no alias",
    overrideUrl.searchParams.get("type_top") === null &&
      overrideUrl.searchParams.get("remaining_top") === "9",
    overrideUrl.search,
  );

  // "max" asks for the route's deepest and widest tree; the route resolves it
  // (tests/test_rollup_route.py), so neither the SDK nor a plugin knows the bounds.
  await mb.fetchRollup("deep", { depth: "max", top: "max" });
  const maxUrl = new URL(fetchCalls.at(-1));
  check(
    '"max" depth and top reach the route as asked',
    maxUrl.searchParams.get("depth") === "max" && maxUrl.searchParams.get("top") === "max",
    maxUrl.search,
  );
  // The node budget, ignored scope, and encoding reach the route as asked, and the SDK
  // returns a compact body undecoded. The route clamps a node budget as it does depth and
  // top, and refuses an unknown scope or encoding (tests/test_rollup_route.py).
  await mb.fetchRollup("dense", { nodes: "max", ignored: "exclude", encoding: "compact" });
  const denseUrl = new URL(fetchCalls.at(-1));
  check(
    "nodes, ignored, and encoding reach the route as asked",
    denseUrl.searchParams.get("nodes") === "max" &&
      denseUrl.searchParams.get("ignored") === "exclude" &&
      denseUrl.searchParams.get("encoding") === "compact",
    denseUrl.search,
  );
  await mb.fetchRollup("plain");
  const plainUrl = new URL(fetchCalls.at(-1));
  check(
    "an unasked node budget, scope, and encoding stay off the query",
    !["nodes", "ignored", "encoding"].some((key) => plainUrl.searchParams.has(key)),
    plainUrl.search,
  );

  if (failures.length > 0) {
    console.error(`folder plugin FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("folder plugin OK");
})();
