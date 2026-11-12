// Behavioral shim for metabrowser.whenIdle in static/plugin-sdk.js.
//
//   node tests/dom/idle-work-behavior.js <repo_root>
//
// The app's WebKit (WKWebView, macOS 26) has no requestIdleCallback, and every idle
// call site used to fall back to a fixed timer, which starts prefetch on a clock
// instead of when the page is free. The helper waits there for the shell's first view
// to settle and for input to go quiet, bounded by the caller's timeout. Where the engine
// has requestIdleCallback the helper is that. The clock and timers are faked, so every
// moment a callback runs is exact. Prints one JSON object.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2] || path.join(__dirname, "../.."));
const staticDir = path.join(repoRoot, "src/metabrowser/static");

let clock = 0;
/** @type {Array<{id: number, at: number, fn: () => void}>} */
let timers = [];
let nextTimer = 1;
/** @type {Map<string, Array<(event: unknown) => void>>} */
const listeners = new Map();
/** @type {Map<string, unknown>} */
const listenerOptions = new Map();

function advance(ms) {
  const until = clock + ms;
  for (;;) {
    timers.sort((left, right) => left.at - right.at || left.id - right.id);
    const due = timers[0];
    if (!due || due.at > until) {
      break;
    }
    timers.shift();
    clock = Math.max(clock, due.at);
    due.fn();
  }
  clock = until;
}

function dispatch(type) {
  for (const listener of listeners.get(type) ?? []) {
    listener({ type, isTrusted: true });
  }
}

const element = () => ({
  setAttribute() {},
  getAttribute: () => null,
  addEventListener() {},
  append() {},
  appendChild() {},
  classList: { add() {}, remove() {}, contains: () => false },
  style: {},
});
const sandbox = {
  console,
  URL,
  URLSearchParams,
  AbortController,
  CustomEvent: class {
    constructor(type, init) {
      this.type = type;
      this.detail = init?.detail;
    }
  },
  Event: class {
    constructor(type) {
      this.type = type;
    }
  },
  location: { origin: "http://localhost", pathname: "/view/", search: "", hash: "" },
  history: { pushState() {}, replaceState() {} },
  performance: { now: () => clock },
  setTimeout(fn, ms = 0) {
    const id = nextTimer++;
    timers.push({ id, at: clock + Math.max(0, Number(ms) || 0), fn });
    return id;
  },
  clearTimeout(id) {
    timers = timers.filter((timer) => timer.id !== id);
  },
  addEventListener(type, listener, options) {
    listeners.set(type, [...(listeners.get(type) ?? []), listener]);
    listenerOptions.set(type, options ?? null);
  },
  removeEventListener() {},
  dispatchEvent(event) {
    dispatch(event.type);
    return true;
  },
  document: {
    head: element(),
    body: element(),
    documentElement: element(),
    createElement: element,
    addEventListener() {},
    getElementById: () => null,
    querySelector: () => null,
  },
  fetch: () => new Promise(() => {}),
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
for (const name of [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "plugin-sdk.js",
]) {
  vm.runInContext(fs.readFileSync(path.join(staticDir, name), "utf8"), sandbox, {
    filename: name,
  });
}
const mb = sandbox.metabrowser;

/** The listeners the SDK adds in an engine that has requestIdleCallback. */
function sdkListenerTypesWithIdleCallback() {
  const types = [];
  const other = {
    ...sandbox,
    // A fresh SDK: the one already loaded would make it return early, as on a double load.
    metabrowser: undefined,
    requestIdleCallback: () => 1,
    cancelIdleCallback() {},
    addEventListener: (type) => types.push(type),
  };
  other.window = other;
  other.globalThis = other;
  vm.createContext(other);
  for (const name of [
    "request-error.js",
    "formatters.js",
    "inventory-scope.js",
    "resource-context.js",
    "view-state.js",
    "navigation.js",
    "plugin-sdk.js",
  ]) {
    vm.runInContext(fs.readFileSync(path.join(staticDir, name), "utf8"), other, { filename: name });
  }
  return types.filter((type) => ["pointerdown", "keydown", "wheel"].includes(type));
}
const results = {};
/** @type {Array<string>} */
const ran = [];
const record = (name) => () => ran.push(`${name}@${clock}`);
// The first view's settling is a promise the helper chains on, so a step that asks for
// idle work, or settles the view, lets the microtasks run before the clock moves.
const flush = () => new Promise((resolve) => setImmediate(resolve));

(async () => {
  results.helper = typeof mb.whenIdle;
  // The input listeners only the fallback reads, passive so a wheel never waits on them.
  results.inputListeners = ["pointerdown", "keydown", "wheel"].map((type) =>
    listeners.has(type) ? listenerOptions.get(type) : null,
  );
  results.inputListenersWithIdleCallback = sdkListenerTypesWithIdleCallback();

  // 1. Before the first view settles, untimed work waits, and timed work waits for its
  //    timeout and no longer. Untimed work has no ceiling, by decision: see "Idle Work"
  //    in docs/development.md.
  mb.whenIdle(record("untimed"));
  mb.whenIdle(record("timed-2000"), { timeout: 2000 });
  await flush();
  advance(1999);
  results.beforeTimeout = ran.slice();
  advance(1);
  results.atTimeout = ran.slice();
  advance(5000);
  results.unsettledLongAfter = ran.slice();

  // 2. The settled first view releases what waited for it, in a task of its own.
  dispatch("metabrowser:first-view-settled");
  results.synchronouslyOnSettle = ran.slice();
  await flush();
  advance(0);
  results.afterSettle = ran.slice();

  // 3. Recent input defers idle work until input has been quiet for a while.
  ran.length = 0;
  advance(1000);
  dispatch("keydown");
  const keyAt = clock;
  mb.whenIdle(record("after-key"));
  await flush();
  advance(100);
  dispatch("pointerdown");
  const pointerAt = clock;
  advance(249);
  results.deferredWhileInputIsRecent = ran.slice();
  advance(1);
  results.afterQuiet = ran.slice();
  results.quietAfterLastInputMs = Number(ran[0]?.split("@")[1]) - pointerAt;
  results.keyThenPointerGapMs = pointerAt - keyAt;

  // 4. A timeout bounds the wait for quiet too.
  ran.length = 0;
  dispatch("wheel");
  mb.whenIdle(record("timed-100"), { timeout: 100 });
  await flush();
  for (let step = 0; step < 4; step += 1) {
    advance(40);
    dispatch("keydown");
  }
  results.timeoutDuringInput = ran.slice();

  // 5. Cancelled work never runs.
  ran.length = 0;
  advance(1000);
  const cancel = mb.whenIdle(record("cancelled"), { timeout: 50 });
  await flush();
  cancel();
  advance(5000);
  results.cancelled = ran.slice();
  results.timersLeft = timers.length;

  // 6. Where the engine has requestIdleCallback, the helper is that.
  const idleCalls = [];
  const cancelledIdle = [];
  sandbox.requestIdleCallback = (fn, options) => {
    idleCalls.push({ options: options ?? null });
    fn({ didTimeout: false, timeRemaining: () => 50 });
    return 7;
  };
  sandbox.cancelIdleCallback = (id) => cancelledIdle.push(id);
  /** @type {Array<number>} */
  const argumentCounts = [];
  mb.whenIdle((...args) => argumentCounts.push(args.length), { timeout: 300 });
  mb.whenIdle((...args) => argumentCounts.push(args.length))();
  results.nativeCalls = idleCalls;
  results.nativeArgumentCounts = argumentCounts;
  results.nativeCancelled = cancelledIdle;

  process.stdout.write(`${JSON.stringify(results)}\n`);
})();
