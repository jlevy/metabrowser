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
  sandbox.METABROWSER_SETTINGS = {
    RECENT_WINDOW_SECONDS: {
      live: 90,
      "1h": 60 * 60,
      "24h": 24 * 60 * 60,
      "7d": 7 * 24 * 60 * 60,
      "30d": 30 * 24 * 60 * 60,
      all: null,
    },
  };
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
    showIgnored: true,
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
    prefs: { filters: { recency: "24h", types: [".md"], size: "1m", showIgnored: false } },
  });
  assertEqual("stored preferences are restored", state.get(), {
    recency: "24h",
    types: [".md"],
    size: "1m",
    showIgnored: false,
  });
  assertEqual("each non-default dimension counts once", state.activeCount(), 4);
}

// A cookie written by a future version must degrade, never throw.
{
  const { state } = makeSandbox({
    prefs: { filters: { recency: "since-tuesday", size: 42, showIgnored: "yes", types: "md" } },
  });
  assertEqual("unknown values fall back to defaults", state.get(), {
    recency: "all",
    types: null,
    size: "all",
    showIgnored: true,
  });
}

{
  const { state } = makeSandbox({ prefs: { filters: { types: [] } } });
  assertEqual("an empty type list normalizes to no constraint", state.get().types, null);
  assertEqual("...and does not count as active", state.activeCount(), 0);
}

{
  const { state } = makeSandbox({
    prefs: { filters: { recency: "7d", types: [".md"], showIgnored: false } },
  });
  state.clear();
  assertEqual("clear resets every dimension", state.activeCount(), 0);
  assertEqual("clear restores gitignored visibility", state.get().showIgnored, true);
}

// get() must not hand out a reference into internal state.
{
  const { state } = makeSandbox({ prefs: { filters: { types: [".md"] } } });
  const snapshot = state.get();
  snapshot.types.push(".py");
  assertEqual("snapshots are copies", state.get().types, [".md"]);
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
  assertTrue(
    "an ordinary file touched inside the Live window matches",
    state.rowMatches({ mtime: NOW - 89, path: "notes.md" }, s, NOW),
  );
  assertEqual(
    "a file outside the Live window does not",
    state.rowMatches({ mtime: NOW - 91, path: "session.jsonl" }, s, NOW),
    false,
  );
  assertTrue(
    "missing mtime stays unknown rather than excluding a pending row",
    state.rowMatches({ path: "pending.txt" }, s, NOW),
  );
}

// Size is a floor, not a band: each step matches everything above it.
{
  const { state } = makeSandbox();
  const s = state.get();
  const MB = 1024 * 1024;
  assertTrue("any accepts everything", state.sizeMatches(10, "all"));
  assertTrue(">100K matches a 200K file", state.sizeMatches(200 * 1024, "100k"));
  assertEqual(">100K rejects a 2K file", state.sizeMatches(2048, "100k"), false);
  assertTrue(">1M matches a 5M file", state.sizeMatches(5 * MB, "1m"));
  assertEqual(">10M rejects a 5M file", state.sizeMatches(5 * MB, "10m"), false);
  assertTrue(">1G matches a 2G file", state.sizeMatches(2 * 1024 * MB, "1g"));
  // A floor is cumulative, so a big file matches every step below it.
  assertTrue("a 2G file also matches >100K", state.sizeMatches(2 * 1024 * MB, "100k"));
  assertTrue("a pending size is not excluded", state.sizeMatches(null, "1g"));
  assertTrue("directories skip the size dimension", state.rowMatches({ isDir: true }, s, NOW));
}

// Types are literal extensions now, so the menu offers exactly what
// the tree contains and no classifier can disagree with it.
{
  const { state } = makeSandbox();
  assertTrue("a selected extension matches", state.typeMatches("a/b/c.md", [".md"]));
  assertEqual("an unselected extension does not", state.typeMatches("a.py", [".md"]), false);
  assertTrue("no selection means no constraint", state.typeMatches("a.py", null));
  assertTrue("matching is case-insensitive", state.typeMatches("A.MD", [".md"]));
  assertTrue("several extensions are ORed", state.typeMatches("a.py", [".md", ".py"]));
  // Unlike a pending size, "this file has no extension" is complete
  // information, so it is a real non-match.
  assertEqual("an extensionless file cannot match", state.typeMatches("Makefile", [".md"]), false);
  // A dotfile is a name, not an extension.
  assertEqual("a dotfile has no extension", state.typeMatches(".gitignore", [".gitignore"]), false);
  // Compound extensions match on the last segment, the same way the
  // tree's own extension column reads them.
  assertTrue("a compound name matches its tail", state.typeMatches("a.min.js", [".js"]));
  // The menu tallies on the index's compound tail, so a compound pick
  // must match on it too. Matching by last-suffix only made ".min.js"
  // reduce to ".js" and pick up nothing it was counted for.
  assertTrue(
    "a compound pick matches via the logical extension",
    state.typeMatches("a.min.js", [".min.js"], ".min.js"),
  );
  assertEqual(
    "and does not match a plain sibling",
    state.typeMatches("a.js", [".min.js"], ".js"),
    false,
  );

  // One convention: a leading dot is an extension, anything else is a
  // whole filename. That is what lets a preset name README and LICENSE,
  // which carry no extension and would otherwise be unfilterable.
  assertTrue(
    "a bare token matches the whole filename",
    state.typeMatches("a/LICENSE", ["license"]),
  );
  assertTrue(
    "filename matching is case-insensitive",
    state.typeMatches("a/Makefile", ["MAKEFILE"]),
  );
  assertEqual(
    "a bare token does not match a prefix of a longer name",
    state.typeMatches("a/LICENSE.txt", ["license"]),
    false,
  );
  assertEqual(
    "nor does it match an unrelated file",
    state.typeMatches("a/main.py", ["license"]),
    false,
  );
  // Mixed tokens are ORed like any other selection.
  assertTrue("extensions and names combine", state.typeMatches("a/LICENSE", [".md", "license"]));
  assertTrue("and the extension half still works", state.typeMatches("a/x.md", [".md", "license"]));
}

if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}

process.stdout.write("OK filter state\n");
