const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const repo = path.resolve(__dirname, "../..");
const capturePath =
  process.argv[2] || path.join(repo, "explorations/performance-loop/capture-browser.js");
const perfPath = process.argv[3] || path.join(repo, "src/metabrowser/static/perf.js");
const source = fs.readFileSync(capturePath, "utf8");
const recorder = fs.readFileSync(perfPath, "utf8");
const capture = require(capturePath);
// Execute the exact scenario body, replacing only browser/corpus readiness dependencies.
// Point resolution, trusted dispatch, boundary capture, recorder and health gate stay real.
const scenarioBody = source.slice(
  source.indexOf("async function runDeferredHydrationScenario("),
  source.indexOf("\nfunction assertGitFilesCollapsedFolderHealth("),
);
const evaluateBody = source.slice(
  source.indexOf("async function evaluate("),
  source.indexOf("\nasync function installInputSentinel("),
);
const evaluate = new Function(`return (${evaluateBody});`)();
const A = "a".repeat(40);
const B = "b".repeat(40);

async function chronology(mode) {
  let epoch = 50;
  let selected = A;
  let rendered = A;
  const queued = [];
  const listeners = new Map();
  let started = false;
  let lagCompletion = null;
  class Element {
    constructor(revision) {
      this.dataset = { revision };
    }
    getBoundingClientRect() {
      return { width: 100, height: 22, left: 0, top: 0 };
    }
    closest(selector) {
      return selector === ".git-graph-row" ? this : null;
    }
  }
  const rows = [new Element(A), new Element(B)];
  const preview = {
    scrollHeight: 100,
    scrollTo() {
      if (started) {
        return;
      }
      started = true;
      for (const file of ["one.txt", "two.txt"]) {
        void sandbox
          .fetch(`/api/plugin/diff/comparison?revision=${A}&file=${file}`)
          .catch(() => {});
      }
    },
  };
  const document = {
    visibilityState: "visible",
    addEventListener() {},
    querySelector(selector) {
      if (selector === "#preview-pane") {
        return preview;
      }
      if (selector === ".git-graph-row.selected") {
        return new Element(selected);
      }
      if (selector === ".git-commit-view") {
        return new Element(rendered);
      }
      return null;
    },
    querySelectorAll(selector) {
      if (selector === ".git-graph-row") {
        return rows;
      }
      if (selector === ".git-commit-diff .diff-root") {
        return [1];
      }
      return [];
    },
  };
  class ClockDate extends Date {
    static now() {
      return epoch;
    }
  }
  const sandbox = {
    Date: ClockDate,
    URL,
    Request,
    Element,
    HTMLElement: Element,
    document,
    console: { log() {}, warn() {}, table() {} },
    performance: { now: () => epoch, timeOrigin: 0, timing: {}, getEntriesByType: () => [] },
    location: { pathname: `/commit/${A}` },
    metabrowser: {},
    fetch() {
      return new Promise((resolve, reject) => queued.push({ resolve, reject }));
    },
    addEventListener(name, listener) {
      if (!listeners.has(name)) {
        listeners.set(name, new Set());
      }
      listeners.get(name).add(listener);
    },
    removeEventListener(name, listener) {
      listeners.get(name)?.delete(listener);
    },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(recorder, sandbox, { filename: perfPath });
  const settle = async () => {
    await Promise.resolve();
    await Promise.resolve();
  };
  const session = {
    async send(method, params) {
      if (method === "Runtime.evaluate") {
        // Intentional point-resolution/transport lag: headers complete while A still owns
        // both selection and rendered DOM. All later operations share epoch60 to defend ties.
        if (
          params.expression.includes("getBoundingClientRect()") &&
          queued.length &&
          !lagCompletion
        ) {
          epoch = 60;
          queued[0].resolve({ status: 200, headers: { get: () => null } });
          await settle();
          lagCompletion = { selected, rendered, snapshot: sandbox.metabrowser.perf.snapshot() };
        }
        return { result: { value: vm.runInContext(params.expression, sandbox) } };
      }
      assert.equal(method, "Input.dispatchMouseEvent");
      if (params.type === "mouseReleased") {
        if (mode !== "missing") {
          const event = {
            isTrusted: mode !== "untrusted",
            target: mode === "wrong-target" ? rows[0] : rows[1],
          };
          for (const listener of [...(listeners.get("click") || [])]) {
            listener(event);
          }
        }
        selected = B;
        rendered = B;
        sandbox.location.pathname = `/commit/${B}`;
        if (mode === "postclick-success") {
          queued[1].resolve({ status: 200, headers: { get: () => null } });
        } else {
          queued[1].reject({ name: "AbortError" });
        }
        await settle();
      }
      return {};
    },
  };
  const scenario = new Function(
    "findDeferredRevision",
    "waitForClientQuiescence",
    "evaluate",
    "waitFor",
    "deferredDiffState",
    "gitRow",
    "dispatchTrustedClickForSelector",
    "dispatchTrustedGitSelection",
    "fetchesAfterGitSelection",
    "waitForGitRevision",
    `return (${scenarioBody});`,
  )(
    async () => ({ rowCount: 2, rowIndex: 0, revision: A, pendingFiles: 4 }),
    async () => {},
    evaluate,
    async (callback) => callback(),
    async () => ({ progressFiles: 1, fetchesInFlight: 2 }),
    async () => ({ revision: B }),
    capture.dispatchTrustedClickForSelector,
    capture.dispatchTrustedGitSelection,
    capture.fetchesAfterGitSelection,
    async () => {},
  );
  const result = await scenario(session, 100);
  assert.equal(lagCompletion.selected, A);
  assert.equal(lagCompletion.rendered, A);
  assert.equal(lagCompletion.snapshot.fetch_samples_seen, 1);
  assert.equal(lagCompletion.snapshot.raw_fetch.length, 1);
  assert.equal(lagCompletion.snapshot.raw_fetch[0].ts, 60);
  assert.equal(result.selected_revision, B);
  return result;
}

(async () => {
  const lag = await chronology("preinput-lag");
  // On stock db52 this fails with obsolete_successes=1: a real pre-input completion
  // is charged to post-selection work by the earlier Date.now boundary.
  capture.assertDeferredHydrationHealth(lag);
  assert.equal(lag.obsolete_successes, 0);
  assert.equal(lag.selection_boundary.epoch_ms, 60);
  assert.equal(lag.selection_boundary.completed_fetches, 1);
  const stale = await chronology("postclick-success");
  assert.equal(stale.selection_boundary.epoch_ms, 60);
  assert.equal(stale.obsolete_successes, 1);
  assert.throws(() => capture.assertDeferredHydrationHealth(stale), /obsolete_successes/);
  for (const mode of ["missing", "untrusted", "wrong-target"]) {
    await assert.rejects(chronology(mode), /trusted Git selection boundary/);
  }
  // Exercise actual 500-entry recorder retention: the target's completion window exceeds it.
  const manySandbox = {
    window: null,
    metabrowser: {},
    Date,
    URL,
    Request,
    console: { log() {}, warn() {}, table() {} },
    document: { visibilityState: "visible", addEventListener() {} },
    performance: { now: () => 0, timing: {}, getEntriesByType: () => [] },
    fetch: () => Promise.resolve({ status: 200, headers: { get: () => null } }),
  };
  manySandbox.window = manySandbox;
  vm.createContext(manySandbox);
  vm.runInContext(recorder, manySandbox);
  await Promise.all(
    Array.from({ length: 501 }, (_, index) => manySandbox.fetch(`/api/git/repo?sample=${index}`)),
  );
  const retained = manySandbox.metabrowser.perf.snapshot();
  assert.equal(retained.fetch_samples_seen, 501);
  assert.equal(retained.raw_fetch.length, 500);
  assert.deepEqual(
    Array.from(retained.raw_fetch, (sample) =>
      Number(new URL(sample.url, "http://localhost").searchParams.get("sample")),
    ),
    Array.from({ length: 500 }, (_, index) => index + 1),
  );
  assert.throws(
    () => capture.fetchesAfterGitSelection(retained, { completed_fetches: 0 }),
    /lost post-selection/,
  );
  manySandbox.metabrowser.perf.reset();
  const reset = manySandbox.metabrowser.perf.snapshot();
  assert.equal(reset.fetch_samples_seen, 0);
  assert.equal(reset.raw_fetch.length, 0);
  assert.throws(
    () =>
      capture.fetchesAfterGitSelection(reset, { completed_fetches: retained.fetch_samples_seen }),
    /recorder reset/,
  );
  console.log(
    "OK: actual recorder/scenario rejects the old driver-clock boundary; trusted-cut lag, same-ms stale success, missing/untrusted/wrong target, reset and real retention controls",
  );
})().catch((error) => {
  console.error(error.stack);
  process.exitCode = 1;
});
