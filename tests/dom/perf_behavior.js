const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const source = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/perf.js"), "utf-8");
const observers = [];
const visibilityListeners = [];
const interactionListeners = [];
let resourceTimingOverflowListener = null;
let resourceTimingCapacity = null;
let now = 1_000;

class FakePerformanceObserver {
  constructor(callback) {
    this.callback = callback;
    this.type = null;
  }

  observe(options) {
    this.type = options.type;
    observers.push(this);
  }
}
FakePerformanceObserver.supportedEntryTypes = [
  "event",
  "largest-contentful-paint",
  "layout-shift",
  "long-animation-frame",
  "longtask",
  "paint",
];

const sandbox = {
  Blob,
  Date,
  JSON,
  Math,
  Number,
  Object,
  PerformanceObserver: FakePerformanceObserver,
  Promise,
  URL,
  console: { log() {}, table() {}, warn() {} },
  document: {
    addEventListener(name, listener) {
      if (name === "visibilitychange") {
        visibilityListeners.push(listener);
      } else if (name === "click" || name === "keydown") {
        interactionListeners.push(listener);
      }
    },
    createElement() {
      return { click() {}, remove() {} };
    },
    body: { appendChild() {} },
    visibilityState: "visible",
  },
  fetch(input) {
    if (input === "/network") {
      return Promise.reject({ name: "TypeError" });
    }
    if (input === "/abort") {
      return Promise.reject({ name: "AbortError" });
    }
    const status = input === "/missing" ? 404 : input === "/server-error" ? 503 : 200;
    return Promise.resolve({ headers: { get: () => null }, status });
  },
  navigator: {},
  performance: {
    addEventListener(name, listener) {
      if (name === "resourcetimingbufferfull") {
        resourceTimingOverflowListener = listener;
      }
    },
    clearResourceTimings() {},
    getEntriesByType() {
      return [];
    },
    now() {
      return now;
    },
    timeOrigin: 0,
    timing: {},
    setResourceTimingBufferSize(capacity) {
      resourceTimingCapacity = capacity;
    },
  },
  setTimeout(callback) {
    callback();
    return 1;
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(source, sandbox, { filename: "perf.js" });

const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

function observer(type) {
  const found = observers.find((candidate) => candidate.type === type);
  if (!found) {
    throw new Error(`missing ${type} observer`);
  }
  return found;
}

function deliver(type, entries) {
  observer(type).callback({ getEntries: () => entries });
}

async function main() {
  check(
    "generic and application profiler globals share one recorder",
    sandbox.webPerformanceProfiler === sandbox.metabrowserPerf,
  );
  await Promise.allSettled([
    sandbox.fetch("/ok"),
    sandbox.fetch("/missing"),
    sandbox.fetch("/server-error"),
    sandbox.fetch("/network"),
    sandbox.fetch("/abort"),
  ]);
  const fetchProfile = sandbox.metabrowserPerf.snapshot();
  check("fetch count survives bounded detail", fetchProfile.fetch_samples_seen === 5);
  check("non-abort fetch rejection is exact", fetchProfile.fetch_network_errors === 1);
  check("fetch abort is classified separately", fetchProfile.fetch_aborts === 1);
  check("HTTP 4xx count is exact", fetchProfile.fetch_http_4xx === 1);
  check("HTTP 5xx count is exact", fetchProfile.fetch_http_5xx === 1);
  interactionListeners[0]({ isTrusted: true });
  interactionListeners[0]({ isTrusted: false });

  // Whole-window long-task aggregates stay exact without retaining every task.
  deliver("longtask", [
    { duration: 250, startTime: 500 },
    { duration: 700, startTime: 7_000 },
  ]);
  let responsiveness = sandbox.metabrowserPerf.responsiveness();
  check("long-task count is exact", responsiveness.long_tasks === 2);
  check("long-task total is exact", responsiveness.long_task_ms_total === 950);
  check("long-task max is exact", responsiveness.long_task_max_ms === 700);
  check("total blocking time is exact", responsiveness.total_blocking_time_ms === 850);
  check(
    "initial window includes buffered entries from before perf.js loaded",
    responsiveness.long_task_max_ms_first_5s === 250,
  );

  deliver("long-animation-frame", [
    {
      blockingDuration: 590,
      duration: 650,
      renderStart: 620,
      scripts: [{ duration: 610, forcedStyleAndLayoutDuration: 13 }],
      startTime: 600,
      styleAndLayoutStart: 630,
    },
  ]);
  responsiveness = sandbox.metabrowserPerf.responsiveness();
  check("animation-frame count is exact", responsiveness.animation_frames === 1);
  check("animation-frame maximum is exact", responsiveness.animation_frame_max_ms === 650);
  check("animation-frame budget count is exact", responsiveness.animation_frames_over_200ms === 1);
  check(
    "animation-frame blocking maximum is exact",
    responsiveness.animation_frame_blocking_ms_max === 590,
  );
  check("forced layout attribution is retained", responsiveness.forced_style_layout_ms_max === 13);

  deliver("paint", [{ name: "first-contentful-paint", startTime: 120 }]);
  deliver("largest-contentful-paint", [
    { element: { className: "first hero", tagName: "DIV" }, startTime: 300 },
    { element: { className: "final hero", tagName: "MAIN" }, startTime: 450 },
  ]);
  deliver("layout-shift", [
    { hadRecentInput: false, startTime: 100, value: 0.04 },
    { hadRecentInput: false, startTime: 500, value: 0.03 },
    { hadRecentInput: false, startTime: 1_700, value: 0.08 },
    { hadRecentInput: true, startTime: 1_800, value: 0.5 },
  ]);
  const vitals = sandbox.metabrowserPerf.snapshot().vitals;
  check("FCP is retained from navigation", vitals.fcp_ms === 120);
  check(
    "latest LCP is retained from navigation",
    vitals.lcp_ms === 450 && vitals.lcp_entries === 2,
  );
  check("LCP element attribution is retained", vitals.lcp_element === "MAIN.final");
  check("CLS uses the largest session window", vitals.cls === 0.08 && vitals.cls_shifts === 3);

  sandbox.metabrowserPerf.measureAsync("async-span", () => 42);
  const profile = sandbox.metabrowserPerf.snapshot();
  check("profile uses the reusable schema", profile.schema === "web-performance-profile/v1");
  check("async spans contribute whole-window attribution", profile.measure_samples_seen === 1);
  check(
    "first-span milestone survives outside the detail ring",
    profile.label_totals[0]?.label === "async-span" &&
      Number.isFinite(profile.label_totals[0]?.first_end_ms),
    JSON.stringify(profile.label_totals),
  );
  for (let index = 0; index < 205; index += 1) {
    sandbox.metabrowserPerf.measure(`dynamic-${index}`, () => index);
  }
  const overflowProfile = sandbox.metabrowserPerf.snapshot();
  check("span labels stay bounded", overflowProfile.labels_retained <= 200);
  check("span-label overflow is explicit", overflowProfile.labels_overflowed > 0);
  check("Resource Timing capacity is explicit", resourceTimingCapacity === 500);
  resourceTimingOverflowListener?.();
  check(
    "Resource Timing overflow is explicit",
    sandbox.metabrowserPerf.snapshot().resource_timing_buffer_full === 1,
  );

  // Event Timing can run for the life of the tab. Group the several DOM events
  // belonging to one logical gesture by interactionId, then retain a fixed-size
  // recent interaction sample while preserving the whole-window count and max.
  deliver("event", [
    // Same interaction as the first generated click. Its slower duration must
    // replace that interaction's row rather than incrementing the count.
    { duration: 20, interactionId: 1, name: "pointerdown", startTime: 7_099 },
    // An observable event outside an INP-style interaction is not a gesture.
    { duration: 900, interactionId: 0, name: "mousemove", startTime: 7_099 },
    ...Array.from({ length: 700 }, (_value, index) => ({
      duration: index + 1,
      interactionId: index + 1,
      name: "click",
      startTime: 7_100 + index,
    })),
  ]);
  responsiveness = sandbox.metabrowserPerf.responsiveness();
  check("logical interaction count is exact", responsiveness.interactions === 700);
  check("interaction sample is bounded", responsiveness.interaction_samples_retained === 500);
  check(
    "bounded percentile scope is explicit",
    responsiveness.interaction_percentile_scope === "most-recent-500",
  );
  check("interaction maximum is exact", responsiveness.interaction_max_ms === 700);
  check("trusted input coverage is counted", responsiveness.interaction_inputs === 1);

  // A reset starts a coherent new window. Old buffered observer entries are
  // ignored, the denominator restarts, and a previously hidden session can
  // become valid again once the current document is visible.
  sandbox.document.visibilityState = "hidden";
  visibilityListeners.forEach((listener) => {
    listener();
  });
  check(
    "hidden page invalidates the active window",
    !sandbox.metabrowserPerf.responsiveness().measurement_valid,
  );
  sandbox.document.visibilityState = "visible";
  now = 10_000;
  sandbox.metabrowserPerf.reset();
  now = 10_400;
  deliver("longtask", [
    { duration: 900, startTime: 9_900 },
    { duration: 300, startTime: 10_100 },
  ]);
  responsiveness = sandbox.metabrowserPerf.responsiveness();
  check(
    "reset restarts the denominator",
    responsiveness.window_ms === 400,
    String(responsiveness.window_ms),
  );
  check("reset drops pre-window buffered tasks", responsiveness.long_tasks === 1);
  check("reset clears the hidden marker when currently visible", responsiveness.measurement_valid);
  check("reset clears interaction aggregates", responsiveness.interactions === 0);
  check("reset clears interaction coverage", responsiveness.interaction_inputs === 0);
  check("reset clears animation-frame aggregates", responsiveness.animation_frames === 0);
  const resetProfile = sandbox.metabrowserPerf.snapshot();
  check("reset clears navigation vitals", resetProfile.vitals.lcp_ms === null);
  check("reset clears Resource Timing overflow", resetProfile.resource_timing_buffer_full === 0);
  check(
    "reset clears exact fetch failure counters",
    resetProfile.fetch_network_errors === 0 &&
      resetProfile.fetch_aborts === 0 &&
      resetProfile.fetch_http_4xx === 0 &&
      resetProfile.fetch_http_5xx === 0,
  );

  // Engines can accept observe({type}) without throwing for an unsupported
  // entry type. The recorder must consult supportedEntryTypes so an absent signal
  // stays explicit instead of becoming a false zero.
  class PartialPerformanceObserver {
    constructor(_callback) {}
    observe(_options) {}
  }
  PartialPerformanceObserver.supportedEntryTypes = ["event"];
  const partialSandbox = {
    Blob,
    Date,
    JSON,
    Math,
    Number,
    Object,
    PerformanceObserver: PartialPerformanceObserver,
    Promise,
    URL,
    console: { log() {}, table() {}, warn() {} },
    document: {
      addEventListener() {},
      createElement() {
        return { click() {}, remove() {} };
      },
      body: { appendChild() {} },
      visibilityState: "visible",
    },
    navigator: {},
    performance: {
      getEntriesByType() {
        return [];
      },
      now() {
        return 1_000;
      },
      timeOrigin: 0,
      timing: {},
    },
    setTimeout(callback) {
      callback();
      return 1;
    },
  };
  partialSandbox.window = partialSandbox;
  partialSandbox.globalThis = partialSandbox;
  vm.createContext(partialSandbox);
  vm.runInContext(source, partialSandbox, { filename: "perf-partial.js" });
  const partialResponsiveness = partialSandbox.metabrowserPerf.responsiveness();
  check(
    "unsupported required observer is explicit",
    partialResponsiveness.unsupported?.includes("longtask"),
  );
  check(
    "unsupported optional attribution is explicit",
    partialResponsiveness.attribution_unsupported?.includes("long-animation-frame") &&
      partialResponsiveness.animation_frame_max_ms === null,
  );

  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.exit(1);
  }

  process.stdout.write("OK perf instrumentation\n");
}

main().catch((error) => {
  process.stderr.write(`${String(error?.stack ?? error)}\n`);
  process.exit(1);
});
