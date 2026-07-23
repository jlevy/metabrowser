// Behavioral test for the shared FilterState module.
//
// Loads static/filter_state.js into a vm sandbox with a fake
// mb.prefs backend and a fake file-type classifier, then checks:
// defaults, patch sanitization, subscribe/unsubscribe, the
// filter-change CustomEvent, prefs persistence across a fresh module
// instance, activeCount, and the shared predicate semantics.

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

const prefStore = {};
function makeSandbox() {
  const listeners = {};
  const sandbox = {
    console,
    Date,
    Math,
    JSON,
    Number,
    Array,
    Object,
    String,
    addEventListener(type, fn) {
      listeners[type] = listeners[type] || [];
      listeners[type].push(fn);
    },
    removeEventListener() {},
    dispatchEvent(evt) {
      for (const fn of listeners[evt.type] || []) {
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
    metabrowser: {
      prefs: {
        get(name, fallback) {
          return name in prefStore ? JSON.parse(JSON.stringify(prefStore[name])) : fallback;
        },
        set(name, value) {
          prefStore[name] = JSON.parse(JSON.stringify(value));
          return true;
        },
      },
      // Fake classifier: extension-keyed, mirroring the family shapes.
      fileTypeClass(p) {
        if (/\.md$/.test(p)) {
          return "ft-md";
        }
        if (/\.runbook\.md$/.test(p)) {
          return "ft-md-runbook";
        }
        if (/\.py$/.test(p)) {
          return "ft-code";
        }
        if (/\.zzz$/.test(p)) {
          return "";
        }
        return "ft-text";
      },
    },
    _events: listeners,
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/static/filter_state.js"),
    "utf8",
  );
  vm.runInContext(source, sandbox, { filename: "filter_state.js" });
  return sandbox;
}

const sb = makeSandbox();
const api = sb.MetabrowserFilterState;
check("module exposed", !!api);

// Defaults.
const d = api.get();
check(
  "defaults",
  d.current === false && d.ageWindow === null && d.types === null && d.ignored === "dimmed",
  JSON.stringify(d),
);
check("activeCount 0 at defaults", api.activeCount() === 0, String(api.activeCount()));

// Sanitization: bad values drop to defaults, good ones stick.
api.set({ ageWindow: "99d", ignored: "nope", types: [1, "", "ft-md"], current: true });
const s1 = api.get();
check(
  "sanitize keeps valid parts",
  s1.current === true &&
    s1.ageWindow === null &&
    s1.ignored === "dimmed" &&
    JSON.stringify(s1.types) === '["ft-md"]',
  JSON.stringify(s1),
);

// Subscribe + CustomEvent.
let notified = null;
const unsubscribe = api.subscribe((s) => {
  notified = s;
});
let eventDetail = null;
sb.addEventListener("metabrowser:filter-change", (e) => {
  eventDetail = e.detail;
});
api.set({ ageWindow: "7d" });
check("subscriber notified", notified && notified.ageWindow === "7d", JSON.stringify(notified));
check(
  "filter-change event dispatched",
  eventDetail && eventDetail.state && eventDetail.state.ageWindow === "7d",
  JSON.stringify(eventDetail),
);
unsubscribe();
notified = null;
api.set({ ignored: "hidden" });
check("unsubscribe stops notifications", notified === null, JSON.stringify(notified));
check("activeCount counts dims", api.activeCount() === 4, String(api.activeCount()));

// Persistence: a fresh module instance sharing the pref store sees
// the same state (the cross-port cookie story in miniature).
const sb2 = makeSandbox();
const api2 = sb2.MetabrowserFilterState;
const persisted = api2.get();
check(
  "persists through prefs",
  persisted.ageWindow === "7d" &&
    persisted.ignored === "hidden" &&
    persisted.current === true &&
    JSON.stringify(persisted.types) === '["ft-md"]',
  JSON.stringify(persisted),
);

// clear() resets everything.
api.clear();
check("clear resets", api.activeCount() === 0, JSON.stringify(api.get()));

// Predicates. nowSec fixed; window seconds sanity first.
check("windowSeconds", api.windowSeconds("24h") === 86400, String(api.windowSeconds("24h")));
const now = 1_700_000_000;
const base = api.get();

// Age: old file fails, fresh file passes, missing mtime never fails.
const aged = Object.assign({}, base, { ageWindow: "1h" });
check("age dims old", api.rowMatches({ mtime: now - 7200 }, aged, now) === false);
check("age keeps fresh", api.rowMatches({ mtime: now - 60 }, aged, now) === true);
check("age keeps pending", api.rowMatches({ mtime: null }, aged, now) === true);

// Types: family + subtype match, files only.
const typed = Object.assign({}, base, { types: ["ft-md"] });
check("type keeps md", api.rowMatches({ path: "a.md" }, typed, now) === true);
check("type keeps md subtype", api.rowMatches({ path: "a.runbook.md" }, typed, now) === true);
check("type dims py", api.rowMatches({ path: "a.py" }, typed, now) === false);
check("type skips dirs", api.rowMatches({ path: "src", isDir: true }, typed, now) === true);
check("type keeps unclassified", api.rowMatches({ path: "a.zzz" }, typed, now) === true);

// Current: non-active files dim, dirs stay as context.
const current = Object.assign({}, base, { current: true });
check("current dims inactive file", api.rowMatches({ active: false }, current, now) === false);
check("current keeps active file", api.rowMatches({ active: true }, current, now) === true);
check("current keeps dirs", api.rowMatches({ isDir: true }, current, now) === true);

if (failures.length > 0) {
  console.error(`filter state FAILURES:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log("filter state OK");
