// The WKWebView probe's run-side decisions, browserless: which proxy requests belong to
// a step, the refusals and figures a scenario row derives from one step's probe output,
// a run's device pixel ratio, and the probe lock. Imports the exact modules a series
// runs; no server, WebKit, or clock is used.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const HERE = import.meta.dirname;
const LOOP = path.resolve(HERE, "../../explorations/performance-loop");
const { devicePixelRatioOf, scenarioRow, stepEntries } = await import(
  path.join(LOOP, "wkprobe-steps.mjs")
);
const lock = await import(path.join(LOOP, "wkprobe-lock.mjs"));

let checks = 0;
const check = (name, fn) => {
  try {
    fn();
  } catch (error) {
    throw new Error(`${name}: ${error.message}`, { cause: error });
  }
  checks += 1;
};

// ------------------------------------------------------------ step attribution

check("a step's requests are the entries between its own marks", () => {
  const log = [
    { mark: "load", at: "start", t: 10 },
    { url: "/view/README.md", t: 11 },
    { mark: "load", at: "end", t: 20 },
    { mark: "reload", at: "start", t: 30 },
    { url: "/static/app.js", t: 31 },
    { mark: "other", at: "start", t: 32 },
    { mark: "reload", at: "end", t: 40 },
  ];
  const load = stepEntries(log, "load", 0);
  assert.deepEqual(
    load.entries.map((e) => e.url),
    ["/view/README.md"],
  );
  assert.deepEqual([load.startAt, load.endAt, load.next], [10, 20, 3]);
  const reload = stepEntries(log, "reload", load.next);
  assert.deepEqual(
    reload.entries.map((e) => e.url),
    ["/static/app.js"],
  );
  assert.equal(reload.endAt, 40);
  // A start mark with no end, or none at all after the cursor, gives nothing.
  assert.equal(stepEntries(log, "other", 0), null);
  assert.equal(stepEntries(log, "load", 3), null);
});

// ------------------------------------------------------------ scenario rows

const ctx = { version: "metab 1.0", viewport: [1440, 900] };
const facts = (over = {}) => ({
  version: "metab 1.0",
  w: 1440,
  h: 900,
  dpr: 2,
  visibility: "visible",
  vis: [[0, "visible"]],
  errors: [],
  alerts: [],
  resources: [],
  ...over,
});
const screen = { locked: false, displayAsleep: false, onConsole: true };
const visibleStep = (over = {}) => ({
  step: "load",
  screenBefore: screen,
  screenAfter: screen,
  readyMs: 300,
  mountedMs: 360,
  commitMs: 40,
  raf: 60,
  ...over,
  facts: facts(over.facts),
});
// A page hidden from its first frame, shown at page time 2000.4, visible after.
const hiddenStep = (over = {}) => ({
  step: "hidden-load-show",
  screenBefore: screen,
  screenAfter: screen,
  hiddenMountedMs: 900,
  hiddenReady: true,
  hiddenReadyMs: 1200,
  visibilityHidden: "hidden",
  visibilityShown: "visible",
  showToVisibleMs: 12,
  showToPaintedReadyNativeMs: 41,
  showChain: { t0: 2000.4, firstFrame: 2016.2, readyFrame: 2016.2, painted: 2033, frames: 2 },
  commitMs: 40,
  raf: 60,
  rafHidden: 0,
  ...over,
  facts: facts({
    vis: [
      [0, "hidden"],
      [2010, "visible"],
    ],
    ...over.facts,
  }),
});
const guards = (row) => row.refusals.map(([g]) => g);

check("a visible scenario that converged at full frame rate has no refusal", () => {
  const row = scenarioRow("cold", visibleStep(), [], ctx);
  assert.deepEqual(row.refusals, []);
  assert.deepEqual([row.readyMs, row.mountedMs, row.dpr], [300, 360, 2]);
});
check("a visible scenario that saw hidden, never got ready, or ran slow is refused", () => {
  const hidden = scenarioRow(
    "relaunch",
    visibleStep({
      facts: {
        vis: [
          [0, "visible"],
          [50, "hidden"],
        ],
      },
    }),
    [],
    ctx,
  );
  assert.deepEqual(guards(hidden), ["visibility"]);
  assert.deepEqual(guards(scenarioRow("cold", visibleStep({ readyMs: null }), [], ctx)), [
    "converged",
  ]);
  assert.deepEqual(guards(scenarioRow("cold", visibleStep({ raf: 12 }), [], ctx)), ["raf"]);
  assert.deepEqual(guards(scenarioRow("cold", visibleStep(), null, ctx)), ["marks"]);
  assert.deepEqual(guards(scenarioRow("cold", null, [], ctx)), ["probe"]);
});
check("show to painted ready is the painted stamp minus the show's mark", () => {
  const row = scenarioRow("hidden-then-show", hiddenStep(), [], ctx);
  assert.deepEqual(row.refusals, []);
  // 2033 - 2000.4 = 32.6, and 2016.2 - 2000.4 = 15.8.
  assert.equal(row.showToPaintedReadyMs, 33);
  assert.equal(row.showToFirstFrameMs, 16);
  assert.equal(row.showToReadyFrameMs, 16);
  assert.equal(row.readyMs, undefined);
  assert.deepEqual([row.hiddenMounted, row.hiddenReady], [true, true]);
});
check("no painted frame after the show is converged, not a figure", () => {
  const chain = { t0: 2000.4, firstFrame: 2016.2, readyFrame: null, painted: null, frames: 40 };
  const row = scenarioRow("hidden-then-show", hiddenStep({ showChain: chain }), [], ctx);
  assert.deepEqual(guards(row), ["converged"]);
  assert.equal(row.showToPaintedReadyMs, null);
  const noChain = scenarioRow("hidden-then-show", hiddenStep({ showChain: null }), [], ctx);
  assert.ok(guards(noChain).includes("converged"));
});
check("visibility is split at the show: hidden before it, visible after it", () => {
  const early = scenarioRow(
    "hidden-then-show",
    hiddenStep({
      facts: {
        vis: [
          [0, "hidden"],
          [1500, "visible"],
          [1600, "hidden"],
          [2010, "visible"],
        ],
      },
    }),
    [],
    ctx,
  );
  assert.deepEqual(guards(early), ["visibility"]);
  const lapse = scenarioRow(
    "hidden-then-show",
    hiddenStep({
      facts: {
        vis: [
          [0, "hidden"],
          [2010, "visible"],
          [2400, "hidden"],
          [2500, "visible"],
        ],
      },
    }),
    [],
    ctx,
  );
  assert.deepEqual(guards(lapse), ["visibility"]);
  assert.deepEqual(
    guards(scenarioRow("hidden-then-show", hiddenStep({ visibilityShown: "hidden" }), [], ctx)),
    ["visibility"],
  );
});
check("the shown phase is held to the frame-rate guard too", () => {
  assert.deepEqual(guards(scenarioRow("hidden-then-show", hiddenStep({ raf: 8 }), [], ctx)), [
    "raf",
  ]);
});
check("never mounting while hidden is an outcome, not a refusal", () => {
  const row = scenarioRow(
    "hidden-then-show",
    hiddenStep({ hiddenMountedMs: null, hiddenReady: false, hiddenReadyMs: null }),
    [],
    ctx,
  );
  assert.deepEqual(row.refusals, []);
  assert.deepEqual([row.hiddenMounted, row.hiddenMountedMs, row.hiddenReady], [false, null, false]);
});
check("a run whose scenarios disagree on the device pixel ratio is refused", () => {
  assert.deepEqual(devicePixelRatioOf({ cold: { dpr: 2 }, reload: { dpr: 2 } }), {
    ratio: 2,
    refusal: null,
  });
  const mixed = devicePixelRatioOf({ cold: { dpr: 2 }, "hidden-then-show": { dpr: 1 } });
  assert.deepEqual(mixed.ratio, [2, 1]);
  assert.deepEqual(mixed.refusal, ["viewport", "device pixel ratios 2, 1"]);
});

// ------------------------------------------------------------ the probe lock

check("the probe lock refuses while held, reports a stale owner, and frees only its own", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "wkprobe-lock-"));
  try {
    const dir = path.join(root, "probe.lock");
    lock.takeLock(dir, "run --name t");
    assert.equal(lock.lockHeld(), true);
    assert.match(lock.lockOwner(dir), new RegExp(`^pid ${process.pid}: wkprobe.mjs run --name t`));
    assert.throws(() => lock.takeLock(dir, "clean"), /is held \(pid \d+: wkprobe\.mjs run/);
    lock.releaseLock();
    assert.equal(fs.existsSync(dir), false);
    assert.equal(lock.lockHeld(), false);

    // An owner that has exited: reported as stale, never broken.
    const gone = spawnSync(process.execPath, ["-e", ""]).pid;
    fs.mkdirSync(dir);
    fs.writeFileSync(path.join(dir, "owner"), `${gone}\n`);
    assert.equal(lock.ownerPid(lock.lockOwner(dir)), gone);
    assert.throws(() => lock.takeLock(dir, "run"), new RegExp(`pid ${gone}, is not running`));
    assert.equal(fs.existsSync(dir), true);

    // A lock another process took over while this one held it stays where it is.
    fs.rmSync(dir, { recursive: true });
    lock.takeLock(dir, "run");
    fs.writeFileSync(path.join(dir, "owner"), "pid 1: someone else\n");
    lock.releaseLock();
    assert.equal(fs.existsSync(dir), true);
    assert.equal(lock.ownerPid("pid=42 started"), 42);
    assert.equal(lock.ownerPid("nothing here"), null);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});
check("the default lock is beside the data it protects, not under the bundle's name", () => {
  assert.equal(path.dirname(lock.DEFAULT_LOCK), path.join(os.homedir(), "Library", "Caches"));
  assert.equal(path.basename(lock.DEFAULT_LOCK).startsWith("org.metabrowser.perf.wkprobe"), false);
});

console.log(`wkprobe run: ${checks} checks passed`);
