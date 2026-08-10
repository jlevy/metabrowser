// Behavioural checks for static/filter_state.js: defaults,
// sanitization of anything a stale cookie could hand back, the
// predicate contract (missing data never excludes), change delivery,
// and unsubscribe.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");

const failures = [];

function assertEqual(label, actual, expected) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    failures.push(`${label}: expected ${JSON.stringify(expected)} got ${JSON.stringify(actual)}`);
  }
}

function assertTrue(label, actual) {
  assertEqual(label, actual, true);
}

// A sandbox with just enough window for the module: a prefs backing
// store standing in for mb.prefs, a file-type classifier, and a
// CustomEvent/dispatchEvent pair.
function makeSandbox(options) {
  const opts = options || {};
  const store = new Map(Object.entries(opts.prefs || {}));
  const events = [];
  const sandbox = {
    console: { warn() {} },
    JSON,
    Number,
    Object,
    Array,
    Math,
    Date,
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  sandbox.metabrowser = {
    prefs: {
      get(name, fallback) {
        return store.has(name) ? store.get(name) : fallback;
      },
      set(name, value) {
        store.set(name, value);
        return true;
      },
    },
  };
  if (opts.classifier) {
    sandbox.MetabrowserFileTypes = { classFor: opts.classifier };
  }
  sandbox.CustomEvent = class {
    constructor(type, init) {
      this.type = type;
      this.detail = init ? init.detail : undefined;
    }
  };
  sandbox.dispatchEvent = (event) => {
    events.push(event);
    return true;
  };
  vm.createContext(sandbox);
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/static/filter_state.js"),
    "utf-8",
  );
  vm.runInContext(source, sandbox, { filename: "filter_state.js" });
  return { state: sandbox.MetabrowserFilterState, store, events, sandbox };
}

// ── Defaults and persistence ───────────────────────────────────

{
  const { state } = makeSandbox();
  assertEqual("defaults with no stored preference", state.get(), {
    recency: "all",
    types: null,
    size: "all",
    ignored: "dimmed",
    mode: "hide",
  });
  assertEqual("a clean state counts as zero active filters", state.activeCount(), 0);
}

{
  const { state, store } = makeSandbox();
  state.set({ recency: "7d" });
  assertEqual("set writes through to prefs", store.get("filters").recency, "7d");
  assertEqual("one dimension away from default", state.activeCount(), 1);
}

{
  const { state } = makeSandbox({
    prefs: { filters: { recency: "24h", types: ["ft-md"], size: "l", mode: "dim" } },
  });
  assertEqual("stored preferences are restored", state.get(), {
    recency: "24h",
    types: ["ft-md"],
    size: "l",
    ignored: "dimmed",
    mode: "dim",
  });
  assertEqual("each non-default dimension counts once", state.activeCount(), 4);
}

// A cookie written by a future version must degrade, never throw.
{
  const { state } = makeSandbox({
    prefs: { filters: { recency: "since-tuesday", size: 42, mode: "explode", types: "md" } },
  });
  assertEqual("unknown values fall back to defaults", state.get(), {
    recency: "all",
    types: null,
    size: "all",
    ignored: "dimmed",
    mode: "hide",
  });
}

{
  const { state } = makeSandbox({ prefs: { filters: { types: [] } } });
  assertEqual("an empty type list normalizes to no constraint", state.get().types, null);
  assertEqual("...and does not count as active", state.activeCount(), 0);
}

{
  const { state } = makeSandbox({ prefs: { filters: { recency: "7d", types: ["ft-md"] } } });
  state.clear();
  assertEqual("clear resets every dimension", state.activeCount(), 0);
  assertEqual("clear restores the default treatment", state.get().mode, "hide");
}

// get() must not hand out a reference into internal state.
{
  const { state } = makeSandbox({ prefs: { filters: { types: ["ft-md"] } } });
  const snapshot = state.get();
  snapshot.types.push("ft-code");
  assertEqual("snapshots are copies", state.get().types, ["ft-md"]);
}

// ── Change delivery ────────────────────────────────────────────

{
  const { state, events } = makeSandbox();
  const seen = [];
  const unsubscribe = state.subscribe((s) => seen.push(s.recency));
  state.set({ recency: "1h" });
  assertEqual("subscribers see the new state", seen, ["1h"]);
  assertEqual("a change also dispatches an event", events.length, 1);
  assertEqual("event name", events[0].type, "metabrowser:filter-change");
  assertEqual("event carries the snapshot", events[0].detail.state.recency, "1h");
  unsubscribe();
  state.set({ recency: "7d" });
  assertEqual("unsubscribe detaches", seen, ["1h"]);
}

// One broken listener must not stop the others.
{
  const { state } = makeSandbox();
  const seen = [];
  state.subscribe(() => {
    throw new Error("listener blew up");
  });
  state.subscribe(() => seen.push("second"));
  state.set({ recency: "1h" });
  assertEqual("a failing listener does not block the rest", seen, ["second"]);
}

// ── Predicates ─────────────────────────────────────────────────

const NOW = 1_700_000_000;
const HOUR = 3600;

{
  const { state } = makeSandbox();
  const within = { mtime: NOW - HOUR / 2, size: 100, path: "a.md" };
  const older = { mtime: NOW - 5 * HOUR, size: 100, path: "a.md" };
  const s = Object.assign(state.get(), { recency: "1h" });
  assertTrue("a fresh file matches a 1h window", state.rowMatches(within, s, NOW));
  assertEqual("an old file does not", state.rowMatches(older, s, NOW), false);
  assertTrue(
    "a row with no mtime is unknown, not excluded",
    state.rowMatches({ path: "a.md" }, s, NOW),
  );
}

{
  const { state } = makeSandbox();
  const s = Object.assign(state.get(), { recency: "live" });
  assertTrue("a live file matches", state.rowMatches({ live: true, path: "a.md" }, s, NOW));
  assertEqual("a static file does not", state.rowMatches({ path: "a.md" }, s, NOW), false);
  assertTrue(
    "directories are not judged on activity",
    state.rowMatches({ isDir: true, path: "src" }, s, NOW),
  );
}

{
  const { state } = makeSandbox();
  const s = state.get();
  assertTrue("small bucket", state.sizeMatches(1024, "s"));
  assertEqual("small bucket rejects a medium file", state.sizeMatches(50 * 1024, "s"), false);
  assertTrue("medium bucket", state.sizeMatches(50 * 1024, "m"));
  assertTrue("large bucket", state.sizeMatches(5 * 1024 * 1024, "l"));
  assertEqual("large bucket rejects a small file", state.sizeMatches(10, "l"), false);
  assertTrue("any bucket accepts everything", state.sizeMatches(null, "all"));
  assertTrue("a pending size is not excluded", state.sizeMatches(null, "l"));
  assertTrue("directories skip the size dimension", state.rowMatches({ isDir: true }, s, NOW));
}

{
  const { state } = makeSandbox({
    classifier: (p) => {
      if (p.endsWith(".md")) {
        return "ft-md";
      }
      if (p.endsWith(".runbook.md")) {
        return "ft-md-runbook";
      }
      if (p.endsWith(".py")) {
        return "ft-code";
      }
      return "";
    },
  });
  assertTrue("a selected family matches", state.typeMatches("a.md", ["ft-md"]));
  assertEqual("an unselected family does not", state.typeMatches("a.py", ["ft-md"]), false);
  assertTrue("no selection means no constraint", state.typeMatches("a.py", null));
  assertTrue(
    "an unclassified path is missing data, not a non-match",
    state.typeMatches("mystery", ["ft-md"]),
  );
}

// A family matches its subtypes, so picking "md" cannot hide a runbook
// whose filename is colored from the same family.
{
  const { state } = makeSandbox({ classifier: () => "ft-md-runbook" });
  assertTrue("a family matches its subtypes", state.typeMatches("x.md", ["ft-md"]));
}

// With no classifier installed the filter must not rule anything out.
{
  const { state } = makeSandbox();
  assertTrue("no classifier means no exclusions", state.typeMatches("a.py", ["ft-md"]));
}

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("OK filter state\n");
