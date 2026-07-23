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
    style: {},
    addEventListener(type, fn) {
      el.listeners[type] = el.listeners[type] || [];
      el.listeners[type].push(fn);
    },
    querySelector(selector) {
      if (selector === ".tm-viewport") {
        return el.viewport;
      }
      if (selector === ".tm-status") {
        return el.status;
      }
      return null;
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

const fetchCalls = [];
const envelope = {
  root: "/tmp/x",
  path: "",
  index_status: "done",
  indexed_files: 3,
  max_files: 500000,
  truncated: false,
  ext_tallies: [
    [".py", 2, 900, 2, 900],
    [".md", 1, 100, 1, 100],
  ],
  node: {
    name: "root",
    path: "",
    type: "dir",
    state: "complete",
    total_files: 3,
    total_size: 1000,
    unignored_files: 3,
    unignored_size: 1000,
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
        gitignored: false,
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
  "src/metabrowser/static/plugin_sdk.js",
  "src/metabrowser/builtin_plugins/folder/treemap_layout.js",
  "src/metabrowser/builtin_plugins/markdown/index.js",
  "src/metabrowser/builtin_plugins/folder/index.js",
]) {
  const source = fs.readFileSync(path.join(repoRoot, relative), "utf8");
  vm.runInContext(source, sandbox, { filename: relative });
}

const mb = sandbox.metabrowser;
check("treemap view registered", !!mb.getRegisteredView("folder", "treemap"));
check("readme view registered", !!mb.getRegisteredView("folder", "readme"));

// ── README view: explicit empty state without a readme_path ─────
{
  const container = makeElement();
  mb.getRegisteredView("folder", "readme").render(container, {
    path: "sub",
    raw: { readme_path: "" },
  });
  check(
    "readme empty state",
    container.innerHTML.includes("No README in this folder"),
    container.innerHTML,
  );
}

// ── Treemap view: toolbar, cells, refresh, toggle, dispose ──────
(async () => {
  const container = makeElement();
  container.viewport = makeElement();
  container.status = makeElement();
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
  view.render(container, { path: "", kind: "folder", raw: { readme_path: "README.md" } });
  check("toolbar rendered", container.innerHTML.includes("tm-toolbar"), "no toolbar");
  check(
    "toggle groups present",
    ["metric", "grouping", "color", "ignored"].every((k) =>
      container.innerHTML.includes(`data-tm-key="${k}"`),
    ),
    "missing toggle group",
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
    "type fill is the default",
    container.viewport.innerHTML.includes("tm-type-fill"),
    "no ft class on initial render",
  );
  check(
    "age chip beside the name",
    container.viewport.innerHTML.includes("tm-cell-age") &&
      container.viewport.innerHTML.includes('class="age-old"'),
    "no colored age label in cells",
  );
  check(
    "status line totals",
    container.status.textContent.includes("3 files"),
    container.status.textContent,
  );

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
  check("refresh refetched", fetchCalls.length === 2, `${fetchCalls.length} fetches`);

  // Toggle click relayouts without refetching.
  const before = fetchCalls.length;
  const toolbarClick = container.listeners.click?.[0];
  check("toolbar click handler bound", typeof toolbarClick === "function");
  if (toolbarClick) {
    const btn = {
      dataset: { tmKey: "color", tmValue: "age" },
      parentElement: { querySelectorAll: () => [] },
      closest() {
        return btn;
      },
    };
    toolbarClick({ target: { closest: () => btn } });
    check("toggle no refetch", fetchCalls.length === before, `${fetchCalls.length}`);
    check(
      "age fill applied after toggle",
      container.viewport.innerHTML.includes("tm-age-"),
      "no age fill class after color toggle",
    );
  }

  // Dispose detaches the inventory-change and window-resize listeners.
  const listenerCount = (windowListeners["metabrowser:inventory-change"] || []).length;
  const resizeCount = (windowListeners.resize || []).length;
  view.dispose();
  const afterDispose = (windowListeners["metabrowser:inventory-change"] || []).length;
  check("dispose detaches listener", afterDispose === listenerCount - 1, `${afterDispose}`);
  const resizeAfter = (windowListeners.resize || []).length;
  check("dispose detaches resize listener", resizeAfter === resizeCount - 1, `${resizeAfter}`);

  if (failures.length > 0) {
    console.error(`folder plugin FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("folder plugin OK");
})();
