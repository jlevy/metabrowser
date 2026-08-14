// Behavioral test for the folder built-in plugin.
//
// Loads the real SDK, layout module, and folder index.js into a vm
// sandbox with a minimal DOM stub, then drives both registered views:
// README empty state, treemap toolbar + cells from a stubbed
// /api/rollup envelope, watchRollup refresh on inventory-change
// events, toggle relayout without refetch, and dispose detaching the
// listener.

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
function makeElement() {
  const el = {
    innerHTML: "",
    listeners: {},
    attributes: {},
    dataset: {},
    style: {},
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
      if (selector === ".folder-rollup-controls") {
        return el.controls;
      }
      return null;
    },
    querySelectorAll() {
      return [];
    },
    getBoundingClientRect: () => ({ width: 800, height: 600, top: 120 }),
    setAttribute(k, v) {
      el.attributes[k] = v;
    },
    classList: { add() {}, remove() {}, contains: () => false },
  };
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
    createElement: () => ({ appendChild() {} }),
    querySelector: () => null,
    querySelectorAll: () => [],
  },
};
let pendingTimers = [];
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.MetabrowserFileTypeTaxonomy = {
  categories: [],
  families: [],
  matchExtension: () => null,
  canonicalExtension: (extension) => extension,
  categoryForFile: () => "other",
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
sandbox.fetch = async (url) => {
  fetchCalls.push(String(url));
  return { ok: true, json: async () => JSON.parse(JSON.stringify(envelope)) };
};

vm.createContext(sandbox);
for (const relative of [
  "src/metabrowser/static/request_error.js",
  "src/metabrowser/static/formatters.js",
  "src/metabrowser/static/inventory_scope.js",
  "src/metabrowser/static/directory_totals_store.js",
  "src/metabrowser/static/resource_context.js",
  "src/metabrowser/static/view_state.js",
  "src/metabrowser/static/plugin_sdk.js",
  "src/metabrowser/static/filter_controls.js",
]) {
  const source = fs.readFileSync(path.join(repoRoot, relative), "utf8");
  vm.runInContext(source, sandbox, { filename: relative });
}
const moduleSources = [
  "src/metabrowser/builtin_plugins/folder/treemap_layout.js",
  "src/metabrowser/builtin_plugins/folder/treemap_model.js",
  "src/metabrowser/builtin_plugins/folder/rollup_controls.js",
];
for (const relative of moduleSources) {
  const source = fs
    .readFileSync(path.join(repoRoot, relative), "utf8")
    .replace(/^export\s*\{[^}]*\};$/gm, "")
    .replace(/^export\s+/gm, "");
  vm.runInContext(source, sandbox, { filename: relative });
}
const treemapSource = fs
  .readFileSync(path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/treemap.js"), "utf8")
  .replace(/^import .*;$/gm, "")
  .replace("export function registerTreemap", "function registerTreemap");
const treemapStyles = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/styles.css"),
  "utf8",
);
vm.runInContext(treemapSource, sandbox, { filename: "treemap.js" });
vm.runInContext(
  `function normalizeFolderTotals(value) { return value || {state: "pending"}; }
   function mountFolderTotalsView(container, value) {
     container.value = value;
     return { update(next) { container.value = next; } };
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
    acquire() {
      return {
        sync() {}, release() {},
        classFor(key) {
          if (key === "family:python") return "mb-distribution-slot-7";
          if (key === "family:markdown") return "mb-distribution-slot-3";
          return key ? "mb-distribution-slot-1" : "mb-distribution-other";
        }
      };
    }
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
const openPathEvents = [];
sandbox.addEventListener("metabrowser:open-path", (event) => {
  openPathEvents.push(event.detail);
});
let invalidViewRejected = false;
try {
  mb.openPath("docs", { viewId: "" });
} catch (error) {
  invalidViewRejected = error.message.includes("options.viewId");
}
check("openPath rejects an empty preferred view", invalidViewRejected);

// ── Treemap view: toolbar, cells, refresh, toggle, dispose ──────
(async () => {
  const container = makeElement();
  container.viewport = makeElement();
  container.status = makeElement();
  container.totals = makeElement();
  container.controls = makeElement();
  const metricChips = ["size", "files"].map((value) => {
    const attributes = {
      "aria-checked": value === "size" ? "true" : "false",
      "data-chip-value": value,
      tabindex: value === "size" ? "0" : "-1",
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
  container.querySelectorAll = (selector) =>
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
    container.totals.value.total_files === 4 && container.totals.value.total_size === 1050,
    JSON.stringify(container.totals.value),
  );
  check("totals precede the treemap", container.innerHTML.includes("tm-totals-heading"));
  check("shared controls rendered", container.innerHTML.includes("folder-rollup-controls"));
  check(
    "metric chooser present",
    container.controls.innerHTML.includes('data-chip-key="folder-rollup-metric"'),
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
    "ignored scope defaults to an unchecked checkbox",
    container.controls.innerHTML.includes('type="checkbox"') &&
      container.controls.innerHTML.includes('data-chip-check="folder-rollup-ignored"') &&
      !container.controls.innerHTML.includes('data-chip-check="folder-rollup-ignored" checked') &&
      container.controls.innerHTML.includes("Show ignored"),
    container.controls.innerHTML,
  );

  // Initial watchRollup fetch resolves through several microtasks; a
  // host setImmediate drains the whole promise-job queue.
  await new Promise((resolve) => setImmediate(resolve));
  check("initial fetch", fetchCalls.length === 1, `${fetchCalls.length} fetches`);
  check(
    "cells rendered",
    container.viewport.innerHTML.includes("tm-cell") &&
      container.viewport.innerHTML.includes("a.py"),
    container.viewport.innerHTML.slice(0, 200),
  );
  check(
    "folder labels carry a trailing slash without changing the accessible name",
    container.viewport.innerHTML.includes('<span class="tm-cell-label">docs/</span>') &&
      container.viewport.innerHTML.includes('aria-label="docs (folder,'),
    container.viewport.innerHTML,
  );
  check(
    "file cells use the shared file identity icon",
    container.viewport.innerHTML.includes("file-identity-icon tm-cell-file-icon ft-code") &&
      container.viewport.innerHTML.includes('data-file-icon="a.py"') &&
      fileIconCalls.includes("a.py"),
    container.viewport.innerHTML,
  );
  check(
    "Treemap hover is one whole-cell treatment",
    !treemapStyles.includes('.tm-cell-title[role="button"]:hover') &&
      !treemapStyles.includes("border-color: var(--viz-border-strong)") &&
      treemapStyles.includes("filter: brightness(1.06)"),
    treemapStyles,
  );
  check(
    "type fill always uses the shared palette",
    container.viewport.innerHTML.includes("tm-type-fill") &&
      container.viewport.innerHTML.includes("mb-distribution-slot-7") &&
      !container.viewport.innerHTML.includes("mb-distribution-slot-3"),
    container.viewport.innerHTML,
  );
  check(
    "cell values use the common byte formatter",
    container.viewport.innerHTML.includes("600 B"),
    container.viewport.innerHTML,
  );
  check(
    "cell typography is data-driven",
    container.viewport.innerHTML.includes("--tm-label-size:") &&
      container.viewport.innerHTML.includes("--tm-value-size:"),
    container.viewport.innerHTML.slice(0, 300),
  );
  check(
    "obsolete age coloring is absent",
    !container.viewport.innerHTML.includes("tm-cell-age") &&
      !container.viewport.innerHTML.includes("tm-age-"),
    container.viewport.innerHTML,
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

  envelope.index_status = "scanning";
  await refreshFromInventoryChange();
  check(
    "in-progress snapshots render one quiet loading block without partial cells",
    container.viewport.innerHTML.includes("tm-loading mb-delayed-loading") &&
      !container.viewport.innerHTML.includes("data-tm-cell"),
    container.viewport.innerHTML,
  );
  envelope.index_status = "done";
  await refreshFromInventoryChange();
  check(
    "completed snapshots replace loading atomically",
    !container.viewport.innerHTML.includes("tm-loading") &&
      container.viewport.innerHTML.includes("data-tm-cell"),
    container.viewport.innerHTML,
  );

  const folderIndexMatch = container.viewport.innerHTML.match(
    /data-tm-index="(\d+)" aria-label="docs \(folder,/,
  );
  check("folder cell is actionable", !!folderIndexMatch, container.viewport.innerHTML);
  const cellClick = container.viewport.listeners.click?.[0];
  check("cell click handler bound", typeof cellClick === "function");
  if (cellClick && folderIndexMatch) {
    const folderTarget = {
      dataset: { tmIndex: folderIndexMatch[1] },
      closest(selector) {
        return selector === "[data-tm-index]" ? folderTarget : null;
      },
    };
    cellClick({ target: folderTarget });
    check(
      "folder cell keeps Treemap active",
      openPathEvents.length === 1 &&
        openPathEvents[0].path === "docs" &&
        openPathEvents[0].viewId === "treemap",
      JSON.stringify(openPathEvents),
    );
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

  // Metric and ignored-scope changes relayout without refetching.
  const before = fetchCalls.length;
  const sizeMetricHtml = container.viewport.innerHTML;
  const toolbarClick = container.controls.listeners.click?.[0];
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
    clickMetric("files");
    check("metric toggle no refetch", fetchCalls.length === before, `${fetchCalls.length}`);
    check(
      "metric toggle changes cell geometry",
      container.viewport.innerHTML !== sizeMetricHtml,
      "Bytes and Files produced identical markup",
    );
    check(
      "metric chooser reflects the active metric",
      container.controls.innerHTML.includes(
        'data-chip-value="files" role="radio" aria-checked="true" tabindex="0"',
      ),
      container.controls.innerHTML,
    );
    check(
      "Files metric keeps useful formatted bytes on file leaves",
      container.viewport.innerHTML.includes("600 B") && container.status.textContent === "",
      container.viewport.innerHTML,
    );
  }

  const toolbarChange = container.controls.listeners.change?.[0];
  check("ignored checkbox handler bound", typeof toolbarChange === "function");
  if (toolbarChange) {
    toolbarChange({
      target: {
        checked: true,
        getAttribute(name) {
          return name === "data-chip-check" ? "folder-rollup-ignored" : null;
        },
      },
    });
    check(
      "checked ignored scope includes ignored cells without a footer summary",
      container.viewport.innerHTML.includes("c.md") && container.status.textContent === "",
      container.viewport.innerHTML,
    );
    check("ignored scope change no refetch", fetchCalls.length === before, `${fetchCalls.length}`);
  }

  // Dispose detaches the inventory-change and window-resize listeners.
  const listenerCount = (windowListeners["metabrowser:inventory-change"] || []).length;
  const resizeCount = (windowListeners.resize || []).length;
  mounted.dispose();
  const afterDispose = (windowListeners["metabrowser:inventory-change"] || []).length;
  check("dispose detaches listener", afterDispose === listenerCount - 1, `${afterDispose}`);
  const resizeAfter = (windowListeners.resize || []).length;
  check("dispose detaches resize listener", resizeAfter === resizeCount - 1, `${resizeAfter}`);

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

  await mb.fetchRollup("legacy", { type_top: 7 });
  const legacyUrl = new URL(fetchCalls.at(-1));
  check(
    "legacy type_top input maps to the canonical parameter",
    legacyUrl.searchParams.get("type_top") === null &&
      legacyUrl.searchParams.get("remaining_top") === "7",
    legacyUrl.search,
  );

  await mb.fetchRollup("modern", { remaining_top: 9 });
  const modernUrl = new URL(fetchCalls.at(-1));
  check(
    "modern remaining_top emits no redundant alias",
    modernUrl.searchParams.get("type_top") === null &&
      modernUrl.searchParams.get("remaining_top") === "9",
    modernUrl.search,
  );

  if (failures.length > 0) {
    console.error(`folder plugin FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("folder plugin OK");
})();
