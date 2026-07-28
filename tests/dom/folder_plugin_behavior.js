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
  const classes = new Set();
  const el = {
    innerHTML: "",
    listeners: {},
    attributes: {},
    style: {
      setProperty(k, v) {
        this[k] = v;
      },
      removeProperty(k) {
        delete this[k];
      },
    },
    addEventListener(type, fn) {
      el.listeners[type] = el.listeners[type] || [];
      el.listeners[type].push(fn);
    },
    querySelector(selector) {
      if (selector === ".tm-viewport") {
        return el.viewport;
      }
      if (selector === ".tm-scene") {
        return el.scene;
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
    classList: {
      add(...names) {
        names.forEach((name) => {
          classes.add(name);
        });
      },
      remove(...names) {
        names.forEach((name) => {
          classes.delete(name);
        });
      },
      contains(name) {
        return classes.has(name);
      },
    },
  };
  return el;
}

const windowListeners = {};
let reducedMotion = false;
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
  METABROWSER_SETTINGS: {
    ROLLUP_DEFAULT_DEPTH: 6,
    ROLLUP_DEFAULT_TOP: 40,
    ROLLUP_DEFAULT_EXT_TOP: 12,
    ROLLUP_WATCH_DEBOUNCE_MS: 1000,
  },
  matchMedia() {
    return { matches: reducedMotion };
  },
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
  MetabrowserFileTypes: {
    classFor(p) {
      if (/\.md$/.test(p)) {
        return "ft-md";
      }
      if (/\.py$/.test(p)) {
        return "ft-code";
      }
      return "ft-text";
    },
    iconFor() {
      return "";
    },
  },
  document: {
    // Minimal cookie jar so mb.prefs round-trips in the vm (real
    // browsers merge by name; attributes after the first ; drop).
    _cookies: {},
    get cookie() {
      return Object.entries(this._cookies)
        .map(([k, v]) => `${k}=${v}`)
        .join("; ");
    },
    set cookie(str) {
      const pair = String(str).split(";")[0];
      const eq = pair.indexOf("=");
      if (eq > 0) {
        this._cookies[pair.slice(0, eq).trim()] = pair.slice(eq + 1);
      }
    },
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
        name: "src",
        path: "src",
        type: "dir",
        state: "complete",
        total_files: 1,
        total_size: 600,
        unignored_files: 1,
        unignored_size: 600,
        mtime: 1700000000,
        gitignored: false,
        dominant_ext: ".py",
        children: [
          {
            name: "lib",
            path: "src/lib",
            type: "dir",
            state: "complete",
            total_files: 1,
            total_size: 600,
            unignored_files: 1,
            unignored_size: 600,
            mtime: 1700000000,
            gitignored: false,
            dominant_ext: ".py",
            children: [
              {
                name: "a.py",
                path: "src/lib/a.py",
                type: "file",
                size: 600,
                mtime: 1700000000,
                ext: ".py",
                gitignored: false,
              },
            ],
          },
        ],
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
  const response = JSON.parse(JSON.stringify(envelope));
  const requested = new URL(String(url)).searchParams.get("path") || "";
  if (requested === "src") {
    response.path = "src";
    response.node = response.node.children.find((child) => child.path === "src");
  }
  return { ok: true, json: async () => response };
};

vm.createContext(sandbox);
for (const relative of [
  "src/metabrowser/static/plugin_sdk.js",
  "src/metabrowser/static/filter_state.js",
  "src/metabrowser/builtin_plugins/folder/treemap_layout.js",
  "src/metabrowser/builtin_plugins/markdown/index.js",
  "src/metabrowser/builtin_plugins/folder/index.js",
]) {
  const source = fs.readFileSync(path.join(repoRoot, relative), "utf8");
  vm.runInContext(source, sandbox, { filename: relative });
}

const mb = sandbox.metabrowser;
const openedPaths = [];
sandbox.addEventListener("metabrowser:open-path", (event) => {
  openedPaths.push(event.detail.path);
});
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
  container.viewport.scene = makeElement();
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
    "root omits zoom-out control",
    !container.innerHTML.includes("data-tm-zoom-out"),
    container.innerHTML,
  );
  check(
    "toggle groups present",
    ["metric", "grouping", "color", "depth"].every((k) =>
      container.innerHTML.includes(`data-tm-key="${k}"`),
    ),
    "missing toggle group",
  );
  check(
    "gitignored control is one checkbox",
    container.innerHTML.includes('type="checkbox"') &&
      container.innerHTML.includes("data-tm-include-ignored") &&
      container.innerHTML.includes("Show gitignored") &&
      !container.innerHTML.includes('data-tm-key="ignored"'),
    container.innerHTML,
  );

  // Initial watchRollup fetch resolves through several microtasks; a
  // host setImmediate drains the whole promise-job queue.
  await new Promise((resolve) => setImmediate(resolve));
  check("initial fetch", fetchCalls.length === 1, `${fetchCalls.length} fetches`);
  check(
    "rollup requests the full bounded scene depth",
    new URL(fetchCalls[0]).searchParams.get("depth") === "6",
    fetchCalls[0],
  );
  check(
    "cells rendered",
    container.viewport.scene.innerHTML.includes("tm-cell") &&
      container.viewport.scene.innerHTML.includes("a.py"),
    container.viewport.scene.innerHTML.slice(0, 200),
  );
  check(
    "recursive scene exposes multiple visible levels",
    container.viewport.scene.innerHTML.includes("tm-nested") &&
      container.viewport.scene.innerHTML.includes('data-tm-depth="1"') &&
      container.viewport.scene.innerHTML.includes('data-tm-depth="2"'),
    container.viewport.scene.innerHTML.slice(0, 800),
  );
  check(
    "folder announces zoom action",
    container.viewport.scene.innerHTML.includes("zoom in"),
    container.viewport.scene.innerHTML.slice(0, 500),
  );
  check(
    "type fill is the default",
    container.viewport.scene.innerHTML.includes("tm-type-fill"),
    "no ft class on initial render",
  );
  check(
    "age chip beside the name",
    container.viewport.scene.innerHTML.includes("tm-cell-age") &&
      container.viewport.scene.innerHTML.includes('class="age-old"'),
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
  const clickToggle = (key, value) => {
    const btn = {
      dataset: { tmKey: key, tmValue: value },
      parentElement: { querySelectorAll: () => [] },
      closest(selector) {
        return selector === "[data-tm-key]" ? btn : null;
      },
    };
    toolbarClick({ target: btn });
  };
  if (toolbarClick) {
    clickToggle("depth", "2");
    check(
      "intermediate depth relayouts without deeper descendants",
      !container.viewport.scene.innerHTML.includes('data-tm-depth="2"'),
      container.viewport.scene.innerHTML.slice(0, 800),
    );
    clickToggle("depth", "all");
    check(
      "all depth restores recursively visible descendants",
      container.viewport.scene.innerHTML.includes('data-tm-depth="2"'),
      container.viewport.scene.innerHTML.slice(0, 800),
    );
    clickToggle("color", "age");
    check("toggle no refetch", fetchCalls.length === before, `${fetchCalls.length}`);
    check(
      "age fill applied after toggle",
      container.viewport.scene.innerHTML.includes("tm-age-"),
      "no age fill class after color toggle",
    );
    const clickIncludeIgnored = (checked) => {
      const input = {
        checked,
        closest(selector) {
          return selector === "[data-tm-include-ignored]" ? input : null;
        },
      };
      toolbarClick({ target: input });
    };
    // Unchecking the single control switches to the unignored
    // aggregates; checking it shows ignored entries at full strength.
    clickIncludeIgnored(false);
    check(
      "hidden mode status disclosure",
      container.status.textContent.includes("gitignored hidden"),
      container.status.textContent,
    );
    clickIncludeIgnored(true);
    check(
      "include checkbox selects shown state",
      mb.filters.get().ignored === "shown",
      mb.filters.get().ignored,
    );
  }

  // Folder activation magnifies that cell's recursive inner scene
  // before normal route navigation.
  const viewportClick = container.viewport.listeners.click?.[0];
  check("cell click handler bound", typeof viewportClick === "function");
  if (viewportClick) {
    const srcCell = {
      dataset: { tmIndex: "0" },
      closest(selector) {
        return selector === "[data-tm-index]" ? srcCell : null;
      },
    };
    const beforeOpen = openedPaths.length;
    viewportClick({ target: srcCell });
    check(
      "zoom-in waits for exit transition",
      openedPaths.length === beforeOpen && pendingTimers.length === 1,
      `${openedPaths.length - beforeOpen} opens / ${pendingTimers.length} timers`,
    );
    check(
      "zoom-in transforms the persistent scene toward the folder",
      container.viewport.scene.classList.contains("tm-scene-exit-in") &&
        String(container.viewport.scene.style["--tm-scene-end-transform"]).startsWith("matrix("),
      "missing recursive scene transform",
    );
    const finishExit = pendingTimers.shift();
    if (finishExit) {
      finishExit();
    }
    check(
      "zoom-in opens folder through normal navigation",
      openedPaths.at(-1) === "src",
      openedPaths.join(","),
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

  // The destination renders a visible structural way back out and
  // consumes the matching entrance transition.
  {
    const cZoom = makeElement();
    cZoom.viewport = makeElement();
    cZoom.viewport.scene = makeElement();
    cZoom.status = makeElement();
    const zoomView = mb.getRegisteredView("folder", "treemap");
    zoomView.render(cZoom, { path: "src", kind: "folder", raw: { readme_path: "" } });
    check(
      "nested root exposes zoom-out control",
      cZoom.innerHTML.includes("data-tm-zoom-out") && cZoom.innerHTML.includes("Zoom out"),
      cZoom.innerHTML,
    );
    await new Promise((resolve) => setImmediate(resolve));
    const click = cZoom.listeners.click?.[0];
    const zoomOutButton = {
      dataset: { tmZoomOut: "" },
      closest(selector) {
        return selector === "[data-tm-zoom-out]" ? zoomOutButton : null;
      },
    };
    const beforeOpen = openedPaths.length;
    if (click) {
      click({ target: zoomOutButton });
    }
    check(
      "zoom-out navigates immediately so the parent scene can expand",
      openedPaths.length === beforeOpen + 1 && openedPaths.at(-1) === "/",
      `${openedPaths.length - beforeOpen} opens / ${pendingTimers.length} timers`,
    );
    zoomView.dispose();

    const cParent = makeElement();
    cParent.viewport = makeElement();
    cParent.viewport.scene = makeElement();
    cParent.status = makeElement();
    zoomView.render(cParent, { path: "", kind: "folder", raw: { readme_path: "" } });
    await new Promise((resolve) => setImmediate(resolve));
    check(
      "parent scene expands out from the previous root cell",
      cParent.viewport.scene.classList.contains("tm-scene-enter-out") &&
        String(cParent.viewport.scene.style["--tm-scene-start-transform"]).startsWith("matrix("),
      "missing inverse recursive scene transform",
    );
    const finishEnter = pendingTimers.shift();
    if (finishEnter) {
      finishEnter();
    }
    zoomView.dispose();
  }

  // Reduced-motion mode preserves navigation but skips the delay.
  {
    reducedMotion = true;
    const cReduced = makeElement();
    cReduced.viewport = makeElement();
    cReduced.viewport.scene = makeElement();
    cReduced.status = makeElement();
    const reducedView = mb.getRegisteredView("folder", "treemap");
    reducedView.render(cReduced, { path: "src", kind: "folder", raw: { readme_path: "" } });
    const click = cReduced.listeners.click?.[0];
    const zoomOutButton = {
      dataset: { tmZoomOut: "" },
      closest(selector) {
        return selector === "[data-tm-zoom-out]" ? zoomOutButton : null;
      },
    };
    const beforeTimers = pendingTimers.length;
    const beforeOpen = openedPaths.length;
    if (click) {
      click({ target: zoomOutButton });
    }
    check(
      "reduced motion navigates immediately",
      openedPaths.length === beforeOpen + 1 &&
        openedPaths.at(-1) === "/" &&
        pendingTimers.length === beforeTimers,
      `${openedPaths.length - beforeOpen} opens / ${pendingTimers.length - beforeTimers} timers`,
    );
    reducedView.dispose();
    reducedMotion = false;
  }

  // ── Shared filters drive the treemap (mb.filters) ──────────────
  {
    const c2 = makeElement();
    c2.viewport = makeElement();
    c2.viewport.scene = makeElement();
    c2.status = makeElement();
    Object.defineProperty(c2.status, "textContent", {
      set(v) {
        c2.status._text = v;
      },
      get() {
        return c2.status._text || "";
      },
    });
    Object.defineProperty(c2.viewport, "textContent", {
      set() {},
      get() {
        return "";
      },
    });
    const view2 = mb.getRegisteredView("folder", "treemap");
    view2.render(c2, { path: "", kind: "folder", raw: { readme_path: "" } });
    await new Promise((resolve) => setImmediate(resolve));
    mb.filters.set({ types: ["ft-md"] });
    const dimCount = (c2.viewport.scene.innerHTML.match(/tm-filter-dim/g) || []).length;
    check("shared type filter dims non-matching cells", dimCount === 2, `${dimCount}`);
    check(
      "caption reports active filters",
      c2.status.textContent.includes("filters: types md"),
      c2.status.textContent,
    );
    mb.filters.clear();
    const cleared = (c2.viewport.scene.innerHTML.match(/tm-filter-dim/g) || []).length;
    check("clear undims", cleared === 0, `${cleared}`);
    view2.dispose();
  }

  // ── Legacy ignored migration is one-shot ───────────────────────
  {
    mb.prefs.set("folder.treemap", { metric: "files", ignored: "hidden" });
    const c3 = makeElement();
    c3.viewport = makeElement();
    c3.viewport.scene = makeElement();
    c3.status = makeElement();
    const view3 = mb.getRegisteredView("folder", "treemap");
    view3.render(c3, { path: "", kind: "folder", raw: { readme_path: "" } });
    check(
      "legacy ignored migrates to shared state",
      mb.filters.get().ignored === "hidden",
      mb.filters.get().ignored,
    );
    const stored = mb.prefs.get("folder.treemap", null);
    check(
      "legacy field stripped from stored pref",
      stored && stored.ignored === undefined && stored.metric === "files",
      JSON.stringify(stored),
    );
    view3.dispose();
    // A later shared choice must survive a remount (no re-migration).
    mb.filters.set({ ignored: "dimmed" });
    const c4 = makeElement();
    c4.viewport = makeElement();
    c4.viewport.scene = makeElement();
    c4.status = makeElement();
    const view4 = mb.getRegisteredView("folder", "treemap");
    view4.render(c4, { path: "", kind: "folder", raw: { readme_path: "" } });
    check(
      "remount keeps the later shared choice",
      mb.filters.get().ignored === "dimmed",
      mb.filters.get().ignored,
    );
    view4.dispose();
    mb.filters.clear();
  }

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

  if (failures.length > 0) {
    console.error(`folder plugin FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("folder plugin OK");
})();
