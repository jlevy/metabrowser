// Exact production controller, recorded catalog rows, virtual time, and held batch receipts.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const raw = require("../fixtures/github-pulls-panel-responses.json").open_current.body;
const rows = raw.rows.slice(0, 24).map(JSON.parse);
const settle = async () => {
  for (let n = 0; n < 12; n++) {
    await new Promise((resolve) => setImmediate(resolve));
  }
};
async function run() {
  const { createPullsController } = await import(
    pathToFileURL(
      path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/github/pulls-panel.js"),
    ).href
  );
  function rig({
    shown = false,
    busyUntil = 0,
    failure = null,
    cold = false,
    refreshing = false,
    inventory = rows,
    resetAt = null,
  } = {}) {
    let now = 0,
      online = true,
      visible = true,
      serial = 0;
    const timers = new Map(),
      requests = [],
      batches = [],
      attempts = [],
      cached = new Set(),
      jobs = new Map();
    let currentFailure = failure;
    let catalogGeneration = raw.generation;
    let catalogReadyAt = cold ? Infinity : 0;
    const controller = createPullsController({
      request: async (method, route, options) => {
        requests.push({ method, route, body: options.body });
        if (route.endsWith("pull-cores-prepare")) {
          const body = options.body;
          if (body.numbers.length === 0) {
            return { status: 200, body: { preparation: "released" } };
          }
          attempts.push({ at: now, numbers: body.numbers });
          if (now < busyUntil) {
            return { status: 200, body: { preparation: "busy" } };
          }
          if (resetAt !== null && now >= resetAt) {
            currentFailure = null;
          }
          if (currentFailure) {
            return {
              status: 200,
              body: {
                preparation: "failed",
                failure: {
                  outcome: currentFailure,
                  message: null,
                  reset_at: resetAt === null ? null : new Date(resetAt).toISOString(),
                },
              },
            };
          }
          const missing = body.numbers.filter((number) => !cached.has(number));
          const key = missing.join(",");
          if (missing.length === 0) {
            return {
              status: 200,
              body: { preparation: "ready", ready_numbers: body.numbers, skipped_numbers: [] },
            };
          }
          if (!jobs.has(key)) {
            batches.push(missing);
            jobs.set(key, now + 1000);
          }
          if (now < jobs.get(key)) {
            return { status: 202, body: { preparation: "joined" } };
          }
          for (const number of body.numbers) {
            cached.add(number);
          }
          return {
            status: 200,
            body: { preparation: "ready", ready_numbers: body.numbers, skipped_numbers: [] },
          };
        }
        if (route.endsWith("pulls-refresh")) {
          catalogReadyAt = now + 1000;
          return {
            status: 202,
            body: {
              pulls: {
                ...raw,
                state: "pending",
                refreshing: true,
                generation: null,
                rows: [],
                fetched: 0,
                next_after: null,
              },
            },
          };
        }
        assert.equal(method, "GET", "warming never asks for Git, comparisons, files, or details");
        if (now < catalogReadyAt) {
          return {
            status: 200,
            etag: null,
            body: {
              ...raw,
              state: catalogReadyAt === Infinity ? "absent" : "pending",
              reason: "not_cached",
              refreshing: catalogReadyAt !== Infinity,
              generation: null,
              rows: [],
              fetched: 0,
              total: null,
              next_after: null,
              complete: false,
              last_refresh: null,
            },
          };
        }
        const q = new URL(route, "http://example").searchParams;
        const after = Number(q.get("after")) || Infinity;
        const limit = Number(q.get("limit"));
        const available = inventory.filter(
          (row) => row.number < after && (q.get("state") === "all" || row.state === q.get("state")),
        );
        const window = available.slice(0, limit);
        return {
          status: 200,
          etag: null,
          body: {
            ...raw,
            state: "current",
            refreshing,
            complete: !refreshing,
            generation: catalogGeneration,
            list: q.get("state"),
            total: inventory.length,
            fetched: inventory.length,
            next_after: available.length > limit ? window.at(-1).number : null,
            rows: window,
          },
        };
      },
      schedule(fn, delay) {
        const id = ++serial;
        timers.set(id, { fn, at: now + delay, delay });
        return id;
      },
      cancel: (id) => timers.delete(id),
      now: () => now,
      isVisible: () => visible,
      isOnline: () => online,
      formatTime: (s) => s,
      render() {},
      markCurrent() {},
      markAnchor() {},
      reveal() {},
      open() {},
      filterChanged() {},
    });
    return {
      controller,
      requests,
      batches,
      attempts,
      cached,
      timers,
      async start() {
        await controller.start({ shown, refreshAhead: true });
        await settle();
      },
      async next() {
        const next = [...timers].sort((a, b) => a[1].at - b[1].at)[0];
        if (!next) {
          return false;
        }
        timers.delete(next[0]);
        now = next[1].at;
        next[1].fn();
        await settle();
        return true;
      },
      async until(done) {
        for (let n = 0; n < 120 && !done(); n++) {
          assert(await this.next(), "pending warming has a wakeup");
        }
        assert(done());
      },
      offline() {
        online = false;
        controller.onOffline();
      },
      reconnect() {
        online = true;
        currentFailure = null;
        controller.onOnline();
      },
      hide() {
        visible = false;
        controller.onVisibilityChange();
      },
      show() {
        visible = true;
        controller.onVisibilityChange();
      },
      changeEpoch() {
        catalogGeneration = "replacement-epoch:0";
        cached.clear();
        jobs.clear();
        controller.onFocus();
      },
      now: () => now,
    };
  }
  const startup = rig();
  await startup.start();
  assert.equal(startup.attempts.length, 0, "startup catalog paint precedes speculative work");
  await startup.until(() => startup.cached.size === rows.length);
  await startup.until(() => startup.timers.size === 0);
  assert.deepEqual(
    startup.batches.map((batch) => batch.length),
    [8, 8, 8],
  );
  assert.equal(
    startup.requests.some((r) => r.route.includes("/pull?")),
    false,
  );
  const settledRequests = startup.requests.length;
  assert.equal(startup.timers.size, 0, "one completed hidden pass is not a perpetual watch");
  startup.changeEpoch();
  await settle();
  await startup.until(() => startup.cached.size === rows.length);
  assert.equal(startup.batches.length, 6, "catalog epoch replacement restarts the completed pass");
  startup.controller.dispose();

  const recentClosed = rows.slice(0, 12).map((row, at) => ({
    ...row,
    number: 200 - at,
    state: "closed",
  }));
  const ordered = rig({ inventory: [...recentClosed, ...rows] });
  await ordered.start();
  await ordered.until(() => ordered.cached.size === recentClosed.length + rows.length);
  assert.deepEqual(
    ordered.batches.slice(0, 3).flat(),
    rows.map((row) => row.number),
    "the default Open page is primed before newer Closed rows in All",
  );
  assert.deepEqual(
    ordered.batches.slice(3).flat(),
    recentClosed.map((row) => row.number),
  );
  ordered.controller.dispose();

  const viewport = rig({ shown: true, busyUntil: 5000 });
  await viewport.start();
  viewport.controller.prepareVisible(rows.map((row) => row.number));
  await settle();
  await viewport.until(() => viewport.cached.size === rows.length);
  assert.deepEqual(
    viewport.batches.flat(),
    rows.map((row) => row.number),
    "all viewport rows cross the batch boundary",
  );
  assert.deepEqual(
    viewport.attempts.slice(0, 4).map((a) => a.at),
    [0, 1000, 3000, 7000],
  );
  const readyAt = viewport.now();
  viewport.controller.prepareVisible(rows.slice(12).map((row) => row.number));
  await settle();
  await viewport.next();
  assert.equal(
    viewport.batches.length,
    3,
    "scrolling to a later prepared cohort uses durable metadata",
  );
  viewport.controller.dispose();

  const watched = rig({ shown: true, refreshing: true });
  await watched.start();
  await watched.until(() => watched.cached.size === rows.length);
  assert(
    watched.now() < 10000,
    "a continuous fast catalog watch cannot debounce the queue forever",
  );
  watched.controller.dispose();

  const longBusy = rig({ shown: true, busyUntil: 65000 });
  await longBusy.start();
  longBusy.controller.prepareVisible(rows.map((row) => row.number));
  await settle();
  await longBusy.until(() => longBusy.cached.size === rows.length);
  const recoveredAt = longBusy.attempts.find((attempt) => attempt.at >= 65000).at;
  assert(recoveredAt > 60000, "current demand survives a whole freshness window of unrelated work");
  assert.deepEqual(
    longBusy.batches.flat(),
    rows.map((row) => row.number),
  );
  longBusy.controller.dispose();

  const cold = rig({ cold: true });
  await cold.start();
  await cold.until(() => cold.cached.size === rows.length);
  assert.equal(
    cold.requests.filter((request) => request.route.endsWith("pulls-refresh")).length,
    1,
  );
  cold.controller.dispose();

  const reconnect = rig();
  await reconnect.start();
  await reconnect.until(() => reconnect.cached.size === 8);
  const completed = reconnect.cached.size;
  reconnect.offline();
  const offlineRequests = reconnect.requests.length;
  assert.equal(reconnect.timers.size, 0);
  reconnect.reconnect();
  await reconnect.until(() => reconnect.cached.size === rows.length);
  assert.equal(reconnect.batches.length, 3, "reconnect retains the settled catalog cursor");
  assert(reconnect.requests.length > offlineRequests);
  reconnect.hide();
  assert.equal(reconnect.timers.size, 0);
  reconnect.controller.dispose();

  const rateHeld = rig({ failure: "rate_limited", resetAt: 10000 });
  await rateHeld.start();
  await rateHeld.until(() => rateHeld.attempts.length === 1);
  assert.deepEqual(
    [...rateHeld.timers.values()].map((timer) => timer.at),
    [10000],
    "an unfinished hidden pass wakes once at the known rate reset",
  );
  await rateHeld.until(() => rateHeld.cached.size === rows.length);
  assert(rateHeld.attempts[1].at >= 10000, "no provider admission occurs before reset");
  rateHeld.controller.dispose();

  const failed = rig({ failure: "not_logged_in" });
  await failed.start();
  await failed.until(() => failed.attempts.length === 1);
  assert.equal(failed.timers.size, 0, "a setup failure pauses the whole source pass");
  failed.reconnect();
  await failed.until(() => failed.cached.size === rows.length);
  failed.controller.dispose();

  return {
    catalogRows: rows.length,
    hiddenBatches: startup.batches.slice(0, 3).map((batch) => batch.length),
    busyAttemptsMs: viewport.attempts.slice(0, 4).map((a) => a.at),
    allVisibleReadyMs: readyAt,
    recoveredAfterLongBusyMs: recoveredAt,
    cachedAfterColdStart: cold.cached.size,
    cachedAfterReconnect: reconnect.cached.size,
    completedBeforeDisconnect: completed,
    backgroundRequestsAfterCompletion: settledRequests,
  };
}
run()
  .then((value) => process.stdout.write(`${JSON.stringify(value)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });
