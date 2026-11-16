// A Group by refresh against the shell's own code (static/app.js, loadGroupedTreeInner and
// fetchReopenedFolders) and the production tree filter model, with recording collaborators.
//
// - A refresh whose groups request fails keeps the sections on screen; a first load that
//   fails says so.
// - A refresh fetches the children of each open folder the answer and the cache do not hold
//   before it paints, a level at a time, so it paints every one of them open at once; a
//   fetch that fails is asked for once, and the paint still runs.
// - A refresh another one overtakes while its folders are on their way paints nothing.
// - The wait for a choice's first sections (renderRegrouping): with the scan row hidden,
//   its words are set at once and shown past the quiet period by CSS; with the row already
//   showing a scan, the scan's words stay through the quiet period, so an answer inside it
//   changes none of them, and the wait's end clears the timer and paints the scan again.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "../..");
const app = fs.readFileSync(path.join(root, "src/metabrowser/static/app.js"), "utf8");
const lift = (name) => {
  const found = app.match(new RegExp(`^(?:async )?function ${name}\\([\\s\\S]*?^}`, "m"))?.[0];
  assert.ok(found, `app.js has no function ${name}`);
  return found;
};
const functions = ["loadGroupedTreeInner", "fetchReopenedFolders"].map(lift).join("\n");

const answer = (tree) => ({
  group_by: "type",
  groups: [{ id: "code", label: "Code", files: 3, size: 30, tree }],
});
const src = { type: "dir", path: "src", children: null };
const lib = { type: "dir", path: "src/lib", children: null };

/**
 * @param {{
 *   groups: () => Promise<unknown>,
 *   mounted?: boolean,
 *   opened?: string[],
 *   subtrees?: Record<string, Array<Record<string, unknown>> | Error>,
 * }} setup
 */
function session(setup) {
  const calls = [];
  const subtreeCache = new Map();
  const sandbox = {
    AbortController,
    Array,
    Map,
    Number,
    Object,
    Promise,
    Set,
    String,
    console: { warn() {} },
    // Whether the load is still the one on its way (createGroupedLoads, `current`).
    loadIsCurrent: true,
    _filteredTreeTotals: null,
    subtreeCache,
    queryHtml: (selector) =>
      selector === "#tab-files > .tree-section" && setup.mounted !== false ? {} : null,
    filesPanelUsesGroupedSource: () => true,
    currentGroupedKey: () => "type",
    treeFilterSizeFloors: () => [],
    fetchGroups: (_url, options) => {
      calls.push(["groups", options.preserve === true]);
      return setup.groups();
    },
    failGroupedTree: (reason) => calls.push(["failed", reason]),
    startIndexProgressPolling() {},
    treeTruncationNoteHtml: () => "",
    subtreeCacheKey: (folder, group) => `${group}\u0000${folder}`,
    // The folders open now; a fetched folder's children appear in the cache, as in the shell.
    openedSectionFolders: () => new Map([["type:code", setup.opened || []]]),
    fetchSubtree: (folder, group) => {
      calls.push(["subtree", folder]);
      const children = setup.subtrees?.[folder];
      return Promise.resolve().then(() => {
        if (children instanceof Error || children === undefined) {
          throw children || new Error("not found");
        }
        if (setup.overtakeOn === folder) {
          sandbox.loadIsCurrent = false;
        }
        subtreeCache.set(`${group}\u0000${folder}`, children);
        return { tree: children, scanning: false };
      });
    },
    _perf: { measure: (_label, run) => run() },
    renderGroupedSections: (sections) => calls.push(["painted", sections.length]),
    refreshGroupedSections: (sections) =>
      calls.push([
        "refreshed",
        sections.map((section) =>
          sandbox.treeFilterModel
            .graftOpenedFolders(section.tree, setup.opened || [], (folder) =>
              subtreeCache.get(`${section.key}\u0000${folder}`),
            )
            .expanded.join(),
        ),
      ]),
  };
  sandbox.window = sandbox;
  sandbox.metabrowser = { prefs: { remove() {} } };
  sandbox.dispatchEvent = () => {};
  sandbox.CustomEvent = function CustomEvent() {};
  sandbox.METABROWSER_SETTINGS = { RECENT_WINDOW_SECONDS: { all: null } };
  vm.createContext(sandbox);
  for (const relative of ["filter-state.js", "tree-filter-model.js"]) {
    const filename = path.join(root, "src/metabrowser/static", relative);
    vm.runInContext(fs.readFileSync(filename, "utf8"), sandbox, { filename });
  }
  sandbox.treeFilterModel = sandbox.MetabrowserTreeFilterModel;
  vm.runInContext(functions, sandbox, { filename: "app.js (lifted)" });
  return {
    calls,
    // A refresh paints new sections when none are on screen to keep (createGroupedLoads).
    run: (preserve) =>
      vm.runInContext(
        `loadGroupedTreeInner({ group: "type" }, {
          key: "type",
          first: ${!(preserve && setup.mounted !== false)},
          signal: new AbortController().signal,
          current: () => loadIsCurrent,
          refreshAfter() {},
        })`,
        sandbox,
      ),
  };
}

(async () => {
  // A refresh that fails keeps what is on screen.
  {
    const s = session({ groups: () => Promise.reject(new Error("HTTP 503")) });
    assert.equal(await s.run(true), false);
    assert.deepEqual(s.calls, [["groups", true]]);
  }
  // A first load that fails says so.
  {
    const s = session({ groups: () => Promise.reject(new Error("HTTP 503")), mounted: false });
    assert.equal(await s.run(false), false);
    assert.deepEqual(s.calls, [
      ["groups", false],
      ["failed", "Error: HTTP 503"],
    ]);
  }
  // Open folders the answer does not hold are fetched a level at a time, then painted open
  // together.
  {
    const s = session({
      groups: () => Promise.resolve(answer([src])),
      opened: ["src", "src/lib"],
      subtrees: { src: [lib], "src/lib": [{ type: "file", path: "src/lib/a.py" }] },
    });
    assert.equal(await s.run(true), true);
    assert.deepEqual(s.calls, [
      ["groups", true],
      ["subtree", "src"],
      ["subtree", "src/lib"],
      ["refreshed", ["src,src/lib"]],
    ]);
  }
  // A folder whose fetch fails is asked for once, and the refresh still paints.
  {
    const s = session({
      groups: () => Promise.resolve(answer([src])),
      opened: ["src", "src/lib"],
      subtrees: { src: [lib], "src/lib": new Error("HTTP 500") },
    });
    assert.equal(await s.run(true), true);
    assert.deepEqual(s.calls, [
      ["groups", true],
      ["subtree", "src"],
      ["subtree", "src/lib"],
      ["refreshed", ["src"]],
    ]);
  }
  // An open folder gone from the group is not asked for.
  {
    const s = session({
      groups: () => Promise.resolve(answer([{ type: "file", path: "README.md" }])),
      opened: ["src"],
    });
    assert.equal(await s.run(true), true);
    assert.deepEqual(s.calls, [
      ["groups", true],
      ["refreshed", [""]],
    ]);
  }
  // A refresh overtaken while its folders are on their way paints nothing.
  {
    const s = session({
      groups: () => Promise.resolve(answer([src])),
      opened: ["src"],
      subtrees: { src: [lib] },
      overtakeOn: "src",
    });
    assert.equal(await s.run(true), false);
    assert.deepEqual(s.calls, [
      ["groups", true],
      ["subtree", "src"],
    ]);
  }
  // A first load paints the answer as it is, with no folder fetches.
  {
    const s = session({
      groups: () => Promise.resolve(answer([src])),
      opened: ["src"],
      mounted: false,
    });
    assert.equal(await s.run(false), true);
    assert.deepEqual(s.calls, [
      ["groups", false],
      ["painted", 1],
    ]);
  }
  // The wait's words on the scan row (renderRegrouping).
  {
    const lifted = ["renderRegrouping", "loadingStateDelayMs"].map(lift).join("\n");
    const timers = new Map();
    let nextTimer = 1;
    const classes = new Set();
    const text = { textContent: "~1,200 files scanned" };
    const row = {
      hidden: false,
      classList: {
        add: (name) => classes.add(name),
        remove: (name) => classes.delete(name),
        toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)),
      },
      querySelector: () => text,
    };
    const painted = [];
    const sandbox = {
      _regroupingBy: null,
      _regroupingWordsTimer: null,
      indexProgressLastRendered: { status: "scanning" },
      treeFilterModel: {
        regroupingStatusText: (by) =>
          by === "age" ? "Grouping by age…" : "Grouping by file type…",
      },
      renderIndexProgress: (meta) => painted.push(meta.status),
      document: {
        documentElement: {},
        getElementById: (id) => (id === "index-progress" ? row : { classList: { toggle() {} } }),
      },
      getComputedStyle: () => ({ getPropertyValue: () => " 50ms" }),
      setTimeout: (callback, ms) => {
        timers.set(nextTimer, { callback, ms });
        nextTimer += 1;
        return nextTimer - 1;
      },
      clearTimeout: (id) => timers.delete(id),
      Number,
    };
    vm.createContext(sandbox);
    vm.runInContext(`${lifted}\nthis.renderRegrouping = renderRegrouping;`, sandbox);
    const fire = () => {
      const due = [...timers.values()];
      timers.clear();
      for (const timer of due) {
        timer.callback();
      }
      return due.map((timer) => timer.ms);
    };
    // A choice answered inside the quiet period, with a scan on the row: no word changes.
    sandbox.renderRegrouping("type");
    assert.equal(text.textContent, "~1,200 files scanned");
    assert.deepEqual([...classes], []);
    sandbox.renderRegrouping(null);
    assert.deepEqual(fire(), []);
    assert.equal(text.textContent, "~1,200 files scanned");
    assert.deepEqual(painted, ["scanning"]);
    // One that outlasts it: the words change once the quiet period passes.
    sandbox.renderRegrouping("age");
    assert.deepEqual(fire(), [50]);
    assert.equal(text.textContent, "Grouping by age…");
    // With the row hidden, the words are set at once, and CSS shows them past the delay.
    sandbox.renderRegrouping(null);
    row.hidden = true;
    sandbox.renderRegrouping("type");
    assert.equal(text.textContent, "Grouping by file type…");
    assert.deepEqual([row.hidden, [...classes], fire()], [false, ["mb-delayed-loading"], []]);
  }
  console.log("group by refresh OK");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
