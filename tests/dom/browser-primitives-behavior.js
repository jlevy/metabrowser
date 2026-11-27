const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { createSdkSandbox } = require("./sdk-sandbox.js");

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
  check(
    "bytes reach GB at the first count past megabytes",
    sandbox.MetabrowserFormatters.formatBytes(1024 ** 3 - 1) === "1024.0 MB" &&
      sandbox.MetabrowserFormatters.formatBytes(1024 ** 3) === "1.0 GB",
  );
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
  const now = 1900000000000;
  sandbox.Date = class extends Date {
    static now() {
      return now;
    }
  };
  const age = sandbox.MetabrowserFormatters.age;
  for (const [seconds, expected] of [
    [now / 1000 - 7200, "2h ago"],
    [now / 1000 + 7200, "in 2h"],
    [now / 1000 - 5, "just now"],
    [now / 1000 + 5, "just now"],
    [0, ""],
    [NaN, ""],
    [now / 1000 - 60, "1m ago"],
    [now / 1000 - 365 * 86400, "1y ago"],
  ]) {
    check(`relative age ${seconds}`, age(seconds, { style: "relative" }).label === expected);
  }
  check("compact age remains abbreviated", age(now / 1000 - 7200).label === "2h");
  check(
    "styles share freshness",
    age(now / 1000 - 7200).className === age(now / 1000 - 7200, { style: "relative" }).className,
  );
  // The one age builder: whatever a call site asks, the drawn age carries the primitive's
  // own class beside the call site's, and telling it again swaps that class alone. Telling
  // an age again is the SDK views' (plugin-sdk-views.js), run here on the same clock.
  const { ageLabel, ageLabelHtml } = sandbox.MetabrowserFormatters;
  const sdk = createSdkSandbox();
  sdk.Date = sandbox.Date;
  const { retellAge } = sdk.metabrowser;
  const element = () => {
    const attributes = new Map();
    return {
      textContent: "",
      getAttribute: (name) => attributes.get(name) ?? null,
      setAttribute: (name, value) => attributes.set(name, String(value)),
    };
  };
  const doc = { createElement: element };
  const hourAgo = now / 1000 - 7200;
  const drawn = ageLabel(doc, hourAgo, { className: "row-age", tip: "exact" });
  check(
    "a drawn age carries the primitive's class after the call site's",
    drawn.getAttribute("class") === `row-age ${age(hourAgo).className}` &&
      drawn.textContent === age(hourAgo).label &&
      drawn.getAttribute("data-tip-text") === "exact",
    drawn.getAttribute("class"),
  );
  const told = retellAge(drawn, now / 1000 - 30 * 86400);
  check(
    "telling an age again swaps its class and keeps the call site's",
    told === age(now / 1000 - 30 * 86400).label &&
      drawn.getAttribute("class") === `row-age ${age(now / 1000 - 30 * 86400).className}`,
    drawn.getAttribute("class"),
  );
  retellAge(drawn, null);
  check(
    "an age with no time is empty and has no freshness class",
    drawn.textContent === "" && drawn.getAttribute("class") === "row-age",
    drawn.getAttribute("class"),
  );
  check(
    "the markup and the element agree",
    ageLabelHtml(hourAgo, { className: "row-age", tip: '<"x">' }) ===
      `<span class="row-age ${age(hourAgo).className}" data-tip-text="&lt;&quot;x&quot;&gt;">${age(hourAgo).label}</span>` &&
      ageLabelHtml(0, { className: "row-age" }) === "",
  );
  check(
    "an age is told as of the time it is given",
    age(hourAgo + 7200 - 600, { now: (now + 0) / 1000 }).label === "10m" &&
      age(1000, { now: 1000 + 3 * 86400, style: "relative" }).label === "3d ago",
  );
  sandbox.Date = Date;
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

  // An explicit reread during a background fetch waits for the next cycle it requested.
  const requestedReads = [];
  const updates = [];
  const errors = [];
  const requestedWatch = sandbox.MetabrowserInventoryScope.createInventoryWatch(
    "src",
    {
      fetch: (signal) =>
        new Promise((resolve, reject) => requestedReads.push({ resolve, reject, signal })),
      onError: (error) => errors.push(error.message),
    },
    (value) => updates.push(value.revision),
  );
  let explicitSettled = false;
  const requested = requestedWatch.refresh();
  const sameRequest = requestedWatch.refresh() === requested;
  void requested.then(() => {
    explicitSettled = true;
  });
  dispatch("metabrowser:inventory-change", { paths: ["src/a.py"] });
  const automatic = timers;
  timers = [];
  for (const callback of automatic) {
    callback();
  }
  requestedReads[0].resolve({ revision: 1 });
  await new Promise((resolve) => setImmediate(resolve));
  check(
    "explicit rereads share the queued cycle and wait for its result",
    sameRequest && !explicitSettled && requestedReads.length === 2,
  );
  requestedReads[1]?.resolve({ revision: 2 });
  await new Promise((resolve) => setImmediate(resolve));
  check(
    "the queued result settles the request and covers prior automatic changes",
    explicitSettled && updates.join(",") === "1,2" && requestedReads.length === 2,
  );

  let failureSettled = false;
  void requestedWatch.refresh().then(() => {
    failureSettled = true;
  });
  requestedReads[2]?.reject(new Error("inventory read failed"));
  await new Promise((resolve) => setImmediate(resolve));
  check(
    "a failed explicit cycle reports its error and settles",
    failureSettled && errors.join(",") === "inventory read failed",
  );

  let disposalSettled = 0;
  void requestedWatch.refresh().then(() => {
    disposalSettled += 1;
  });
  void requestedWatch.refresh().then(() => {
    disposalSettled += 1;
  });
  requestedWatch.dispose();
  await new Promise((resolve) => setImmediate(resolve));
  check(
    "disposal settles running and queued explicit reads without waiting for fetch",
    disposalSettled === 2 && requestedReads[3]?.signal.aborted === true,
  );
  requestedReads[3]?.resolve({ revision: 3 });
  await new Promise((resolve) => setImmediate(resolve));
  check(
    "a disposed watcher neither publishes its late result nor starts the queued read",
    updates.join(",") === "1,2" && requestedReads.length === 4,
  );

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
