// Behavior contract for static/pending-tally-diagnostics.js: one delayed
// report per unresolved episode, cancellation when values resolve, and a new
// report when pending values later reappear. Runs under Node with fake timers.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const sandbox = {};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/pending-tally-diagnostics.js"),
  "utf-8",
);
vm.runInContext(source, sandbox, { filename: "pending-tally-diagnostics.js" });

const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

function makeTimers() {
  let nextHandle = 1;
  const callbacks = new Map();
  const delays = new Map();
  return {
    cancel(handle) {
      callbacks.delete(handle);
      delays.delete(handle);
    },
    fireAll() {
      const queued = Array.from(callbacks.values());
      callbacks.clear();
      delays.clear();
      for (const callback of queued) {
        callback();
      }
    },
    pendingCount() {
      return callbacks.size;
    },
    schedule(callback, delayMs) {
      const handle = nextHandle++;
      callbacks.set(handle, callback);
      delays.set(handle, delayMs);
      return handle;
    },
    scheduledDelays() {
      return Array.from(delays.values());
    },
  };
}

async function tick() {
  await new Promise((resolve) => setImmediate(resolve));
}

async function main() {
  const timers = makeTimers();
  let pending = false;
  let now = 1_000;
  const reports = [];
  const errors = [];
  const watchdog = sandbox.MetabrowserPendingTallyDiagnostics.create({
    delayMs: 5_000,
    hasPending: () => pending,
    collect: (context) => ({ context, marker: "captured" }),
    report: (payload) => {
      reports.push(payload);
    },
    onError: (error) => errors.push(error),
    now: () => now,
    schedule: timers.schedule,
    cancel: timers.cancel,
  });

  watchdog.reconcile();
  check("resolved state schedules nothing", timers.pendingCount() === 0);

  pending = true;
  watchdog.reconcile();
  watchdog.reconcile();
  check("pending state schedules once", timers.pendingCount() === 1);
  check("uses configured five-second delay", timers.scheduledDelays()[0] === 5_000);

  now = 6_250;
  timers.fireAll();
  await tick();
  check("first episode reports once", reports.length === 1);
  check("report carries measured elapsed time", reports[0]?.context?.elapsedMs === 5_250);
  check("report carries episode id", reports[0]?.context?.episode === 1);

  watchdog.reconcile();
  timers.fireAll();
  await tick();
  check("same unresolved episode does not repeat", reports.length === 1);

  pending = false;
  watchdog.reconcile();
  pending = true;
  now = 8_000;
  watchdog.reconcile();
  now = 13_000;
  timers.fireAll();
  await tick();
  check("later pending episode reports again", reports.length === 2);
  check("later episode id increments", reports[1]?.context?.episode === 2);

  pending = false;
  watchdog.reconcile();
  pending = true;
  watchdog.reconcile();
  check("new episode has a timer", timers.pendingCount() === 1);
  watchdog.dispose();
  check("dispose cancels timer", timers.pendingCount() === 0);
  check("normal reporting raises no errors", errors.length === 0);

  if (failures.length > 0) {
    console.error(failures.join("\n"));
    process.exitCode = 1;
    return;
  }
  console.log("OK pending tally diagnostics");
}

main();
