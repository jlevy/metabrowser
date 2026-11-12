// perf.js in an engine without Long Tasks, as the app's WebKit is (WKWebView, macOS 26).
//
//   node tests/dom/perf-frame-gap-behavior.js
//
// WebKit has no `longtask`, `long-animation-frame`, or `layout-shift` observer. There the
// recorder measures requestAnimationFrame intervals past 50 ms under `raf_frame_gaps`, so
// a frame gap is never read as a Long Task, leaves the Long Task fields as they were with
// `longtask` named unsupported, and leaves CLS null. The frame loop runs only for a while
// after load, after reset(), and after trusted input, and not while the page is hidden.
// Prints one JSON object.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const source = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/perf.js"), "utf8");

let now = 1_000;
/** @type {Array<(at: number) => void>} */
let frames = [];
const documentListeners = new Map();

class WebKitPerformanceObserver {
  observe() {}
}
// What the WKWebView harness measured on macOS 26.5.2 (research 2026-11-11, 3.9).
WebKitPerformanceObserver.supportedEntryTypes = [
  "event",
  "first-input",
  "largest-contentful-paint",
  "mark",
  "measure",
  "navigation",
  "paint",
  "resource",
];

const sandbox = {
  Date,
  JSON,
  Math,
  Number,
  Object,
  Promise,
  URL,
  PerformanceObserver: WebKitPerformanceObserver,
  console: { log() {}, table() {}, warn() {} },
  document: {
    visibilityState: "visible",
    addEventListener(type, listener) {
      documentListeners.set(type, [...(documentListeners.get(type) ?? []), listener]);
    },
    createElement: () => ({ click() {}, remove() {} }),
    body: { appendChild() {} },
  },
  navigator: {},
  performance: {
    getEntriesByType: () => [],
    now: () => now,
    timeOrigin: 0,
    timing: {},
  },
  requestAnimationFrame(callback) {
    frames.push(callback);
    return frames.length;
  },
  setTimeout(callback) {
    callback();
    return 1;
  },
  metabrowser: {},
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(source, sandbox, { filename: "perf.js" });
const perf = sandbox.metabrowser.perf;

/** Draw one frame at *at*: every callback waiting for it runs with that timestamp. */
function frame(at) {
  now = at;
  const due = frames;
  frames = [];
  for (const callback of due) {
    callback(at);
  }
}

function emit(type, event) {
  for (const listener of documentListeners.get(type) ?? []) {
    listener(event);
  }
}

const gapFields = (r) => r.raf_frame_gaps;

const results = {};
results.frameRequestedAtLoad = frames.length;

// Two frames on time, then one 100 ms late, one on time, and one 300 ms late.
for (const at of [1_016, 1_032, 1_132, 1_148, 1_448]) {
  frame(at);
}
const loaded = perf.responsiveness();
results.afterLoad = gapFields(loaded);
results.longTasks = {
  long_tasks: loaded.long_tasks,
  long_task_max_ms: loaded.long_task_max_ms,
  unsupported: loaded.unsupported,
};
results.cls = perf.snapshot().vitals?.cls;

// A hidden page draws a frame a second; none of those is a gap, nor is the first
// frame after the page is shown again.
sandbox.document.visibilityState = "hidden";
emit("visibilitychange", {});
frame(2_448);
frame(3_448);
sandbox.document.visibilityState = "visible";
emit("visibilitychange", {});
frame(3_464);
frame(3_480);
results.afterHidden = gapFields(perf.responsiveness());

// The loop stops once its window has passed with no input.
frame(12_000);
frame(12_016);
results.framesRequestedAfterWindow = frames.length;

// Trusted input starts it again; untrusted input does not.
emit("click", { isTrusted: false });
results.framesAfterUntrustedClick = frames.length;
emit("keydown", { isTrusted: true });
results.framesAfterTrustedKey = frames.length;
frame(12_100);
frame(12_200);
results.afterInput = gapFields(perf.responsiveness());

// reset() starts a new measurement window, with the loop running.
perf.reset();
results.afterReset = gapFields(perf.responsiveness());
results.framesAfterReset = frames.length;

process.stdout.write(`${JSON.stringify(results)}\n`);
