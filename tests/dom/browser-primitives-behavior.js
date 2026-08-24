const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];
const listeners = new Map();
let timers = [];
let timerDelays = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

class CustomEvent {
  constructor(type, options = {}) {
    this.type = type;
    this.detail = options.detail;
  }
}

const sandbox = {
  console,
  Map,
  Set,
  WeakMap,
  Promise,
  Object,
  Array,
  Math,
  Number,
  Intl,
  Error,
  TypeError,
  AbortController,
  CustomEvent,
  setTimeout(callback, delay) {
    timers.push(callback);
    timerDelays.push(delay);
    return timers.length;
  },
  clearTimeout() {},
  addEventListener(type, callback) {
    const group = listeners.get(type) || [];
    group.push(callback);
    listeners.set(type, group);
  },
  removeEventListener(type, callback) {
    listeners.set(
      type,
      (listeners.get(type) || []).filter((item) => item !== callback),
    );
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

function dispatch(type, detail) {
  for (const listener of listeners.get(type) || []) {
    listener(new CustomEvent(type, { detail }));
  }
}

for (const name of [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "contribution-registry.js",
  "resource-context.js",
  "view-state.js",
]) {
  const source = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static", name), "utf8");
  vm.runInContext(source, sandbox, { filename: name });
}

(async () => {
  check("bytes reach GB", sandbox.MetabrowserFormatters.formatBytes(1024 ** 3) === "1.0 GB");
  check("file singular", sandbox.MetabrowserFormatters.formatFileCount(1).endsWith(" file"));
  check(
    "byte emphasis uses the shared navigation boundary",
    sandbox.MetabrowserFormatters.sizeClass(1024 ** 2) === "" &&
      sandbox.MetabrowserFormatters.sizeClass(1024 ** 2 + 1) === "size-large",
  );
  check(
    "file-count emphasis uses the shared navigation boundary",
    sandbox.MetabrowserFormatters.countClass(999) === "" &&
      sandbox.MetabrowserFormatters.countClass(1000) === "count-large",
  );
  const retryable = sandbox.MetabrowserRequestErrors.classifyRequestError(
    new sandbox.MetabrowserRequestErrors.RequestError("safe", { status: 503 }),
  );
  check("server error retries", retryable.retryable === true);
  check(
    "scope intersection",
    sandbox.MetabrowserInventoryScope.pathsIntersectScope(["src/a.py"], "src"),
  );

  const watchResolvers = [];
  let watchFetches = 0;
  const watch = sandbox.MetabrowserInventoryScope.createInventoryWatch(
    "src",
    {
      fetch: () => {
        watchFetches += 1;
        return new Promise((resolve) => watchResolvers.push(resolve));
      },
    },
    () => {},
  );
  dispatch("metabrowser:inventory-change", { paths: ["src/a.py"] });
  const pendingTimers = timers;
  timers = [];
  pendingTimers.forEach((callback) => {
    callback();
  });
  watchResolvers[0]({ revision: 1 });
  await new Promise((resolve) => setImmediate(resolve));
  check("change during fetch schedules follow-up", watchFetches === 2, String(watchFetches));
  watchResolvers[1]({ revision: 2 });
  await new Promise((resolve) => setImmediate(resolve));
  watch.dispose();

  // A crawl emits inventory changes continuously. A debounce that restarted
  // on every one would never fire until the stream paused, freezing a
  // folder's numbers for the whole scan; the wait is bounded by one window
  // so refreshes keep landing under a steady stream.
  timers = [];
  timerDelays = [];
  const steady = sandbox.MetabrowserInventoryScope.createInventoryWatch(
    "src",
    { debounceMs: 1000, fetch: () => new Promise(() => {}) },
    () => {},
  );
  dispatch("metabrowser:inventory-change", { paths: ["src/a.py"] });
  const firstDelay = timerDelays[timerDelays.length - 1];
  const startedAt = Date.now();
  while (Date.now() - startedAt < 4) {
    // Spin so measurable time passes inside the window before the next change.
  }
  dispatch("metabrowser:inventory-change", { paths: ["src/b.py"] });
  const secondDelay = timerDelays[timerDelays.length - 1];
  check(
    "a burst of changes coalesces into one window",
    firstDelay === 1000 && secondDelay <= 1000,
    `${firstDelay} then ${secondDelay}`,
  );
  check(
    "a later change cannot postpone the refresh past that window",
    secondDelay < firstDelay,
    `${firstDelay} then ${secondDelay}`,
  );
  steady.dispose();

  const registry = sandbox.MetabrowserContributionRegistry.createContributionRegistry({
    validate(id, spec) {
      if (!id || !spec.label) {
        throw new Error("invalid");
      }
    },
    compare: (left, right) => left.label.localeCompare(right.label),
  });
  const unregister = registry.register("z.last", { label: "Zulu" });
  registry.register("a.first", { label: "Alpha" });
  check("registry sorted", registry.list()[0].id === "a.first");
  check("descriptor frozen", Object.isFrozen(registry.list()[0]));
  let duplicate = false;
  try {
    registry.register("z.last", { label: "Again" });
  } catch (_error) {
    duplicate = true;
  }
  check("registry duplicate rejected", duplicate);
  unregister();
  check("registry unregister", registry.list().length === 1);

  let fetches = 0;
  const store = sandbox.MetabrowserResourceContext.createResourceContextStore({
    debounceMs: 1,
    pathsIntersect: sandbox.MetabrowserInventoryScope.pathsIntersectScope,
    async fetchEnvelope(resourcePath) {
      fetches += 1;
      return { path: resourcePath, revision: fetches };
    },
  });
  const received = [];
  store.seed("src", { path: "src", revision: 0 });
  const unsubscribeA = store.subscribe("src", (value) => received.push(value.revision));
  const unsubscribeB = store.subscribe("src", () => {});
  check("seed delivered immediately", received.join(",") === "0", received.join(","));
  dispatch("metabrowser:inventory-change", { paths: ["src/a.py"] });
  const pending = timers;
  timers = [];
  pending.forEach((callback) => {
    callback();
  });
  await new Promise((resolve) => setImmediate(resolve));
  check("context multiplexed refresh", fetches === 1, String(fetches));
  unsubscribeA();
  unsubscribeB();

  const events = [];
  const container = {
    dataset: {},
    dispatchEvent(event) {
      events.push(event);
      return true;
    },
  };
  const activeStates = [];
  const unsubscribeActive = sandbox.MetabrowserViewState.subscribeActive(container, (active) =>
    activeStates.push(active),
  );
  sandbox.MetabrowserViewState.setActive(container, true);
  sandbox.MetabrowserViewState.setActive(container, true);
  sandbox.MetabrowserViewState.setPrintState(container, {
    printable: true,
    profile: "document",
    runtime: "kpress",
  });
  check("active transition deduplicated", activeStates.join(",") === "false,true");
  check("active print event", events.length === 1 && events[0].detail.printable === true);
  unsubscribeActive();
  unsubscribeActive();
  store.dispose();

  if (failures.length) {
    console.error(`browser primitives FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("browser primitives OK");
})();
