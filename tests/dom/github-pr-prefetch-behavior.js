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
    delayedRefresh = false,
    unownedUntil = 0,
    failedCatalogReads = 0,
    partialReceipts = 0,
    failedPrepareReads = 0,
    notGithub = false,
    unavailableUntil = 0,
    failedRefreshReads = 0,
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
    let releaseRefresh = null;
    const revoked = [];
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
          if (failedPrepareReads > 0) {
            failedPrepareReads -= 1;
            throw new Error("one transient preparation failure");
          }
          if (
            body.window.generation !== catalogGeneration ||
            body.numbers.some(
              (number) =>
                !inventory.some(
                  (row) =>
                    row.number === number && (body.state === "all" || row.state === body.state),
                ),
            )
          ) {
            return { status: 200, body: { preparation: "not_owner" } };
          }
          if (now < unownedUntil) {
            revoked.push(now);
            return { status: 200, body: { preparation: "not_owner" } };
          }
          if (partialReceipts > 0) {
            partialReceipts -= 1;
            return {
              status: 200,
              body: { preparation: "ready", ready_numbers: [], skipped_numbers: [] },
            };
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
          const retryNumbers = body.numbers.filter(
            (number) => number === rows[0].number && now < unavailableUntil,
          );
          const readyNumbers = body.numbers.filter((number) => !retryNumbers.includes(number));
          const receipt = () =>
            retryNumbers.length > 0
              ? {
                  preparation: "partial",
                  ready_numbers: readyNumbers,
                  skipped_numbers: [],
                  retry_numbers: retryNumbers,
                  retry_at: new Date(unavailableUntil).toISOString(),
                }
              : { preparation: "ready", ready_numbers: body.numbers, skipped_numbers: [] };
          const missing = readyNumbers.filter((number) => !cached.has(number));
          const key = missing.join(",");
          if (missing.length === 0) {
            return {
              status: 200,
              body: receipt(),
            };
          }
          if (!jobs.has(key)) {
            batches.push(missing);
            jobs.set(key, now + 1000);
          }
          if (now < jobs.get(key)) {
            return { status: 202, body: { preparation: "joined" } };
          }
          for (const number of readyNumbers) {
            cached.add(number);
          }
          return {
            status: 200,
            body: receipt(),
          };
        }
        if (route.endsWith("pulls-refresh")) {
          if (failedRefreshReads > 0) {
            failedRefreshReads -= 1;
            throw new Error("one transient refresh failure");
          }
          if (delayedRefresh) {
            await new Promise((resolve) => {
              releaseRefresh = resolve;
            });
          }
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
        if (notGithub) {
          return {
            status: 200,
            etag: null,
            body: { ...raw, state: "absent", reason: "not_github", rows: [], generation: null },
          };
        }
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
        if (q.get("state") === "all" && failedCatalogReads > 0) {
          failedCatalogReads -= 1;
          throw new Error("one transient local read failure");
        }
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
      revoked,
      releaseRefresh() {
        assert.equal(typeof releaseRefresh, "function");
        releaseRefresh();
      },
      deferVisible(until) {
        unavailableUntil = until;
        cached.delete(rows[0].number);
        jobs.clear();
        controller.prepareVisible([]);
        controller.prepareVisible(rows.map((row) => row.number));
      },
      revise(replacement, dirty = []) {
        inventory = replacement;
        catalogGeneration = `${catalogGeneration.split(":")[0]}:42`;
        for (const number of dirty) {
          cached.delete(number);
        }
      },
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
      changeEpoch(replacement = inventory) {
        inventory = replacement;
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

  const earlyEpoch = rig();
  await earlyEpoch.start();
  await earlyEpoch.next();
  assert.equal(earlyEpoch.batches.length, 1, "the first default-filter cohort is still priming");
  assert.equal(earlyEpoch.cached.size, 0);
  const replacementRows = rows.map((row, at) => ({ ...row, number: 60 - at }));
  earlyEpoch.changeEpoch(replacementRows);
  await settle();
  await earlyEpoch.until(() => earlyEpoch.cached.size === rows.length);
  assert.deepEqual(
    [...earlyEpoch.cached],
    replacementRows.map((row) => row.number),
  );
  assert.equal(earlyEpoch.batches.length, 4, "new identity replaces the unfinished prime cohort");
  earlyEpoch.controller.dispose();

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

  const coldRace = rig({ cold: true, delayedRefresh: true });
  await coldRace.start();
  await coldRace.next();
  await coldRace.next();
  assert(coldRace.timers.size > 0, "absent catalog stays unfinished while refresh is in flight");
  coldRace.releaseRefresh();
  await settle();
  await coldRace.until(() => coldRace.cached.size === rows.length);
  await coldRace.until(() => coldRace.timers.size === 0);
  coldRace.controller.dispose();

  const coldRefreshFailure = rig({ cold: true, failedRefreshReads: 1 });
  await coldRefreshFailure.start();
  await coldRefreshFailure.until(() => coldRefreshFailure.cached.size === rows.length);
  await coldRefreshFailure.until(() => coldRefreshFailure.timers.size === 0);
  assert.equal(
    coldRefreshFailure.requests.filter((request) => request.route.endsWith("pulls-refresh")).length,
    2,
    "a hidden retry recovers the failed initial refresh through normal freshness admission",
  );
  coldRefreshFailure.controller.dispose();

  const closedRows = rows.map((row) => ({ ...row, state: "closed" }));
  const revised = rig({ inventory: closedRows });
  await revised.start();
  await revised.until(() => revised.cached.size === 8);
  const added = { ...closedRows[0], number: 200, title: "New pull" };
  revised.revise([added, ...closedRows], [closedRows[0].number]);
  await revised.until(() => revised.cached.size === rows.length + 1);
  await revised.until(() => revised.timers.size === 0);
  assert(revised.cached.has(added.number), "same-epoch leading additions are revisited");
  assert(
    revised.cached.has(closedRows[0].number),
    "changed already-traversed rows are revalidated",
  );
  revised.controller.dispose();

  for (const shown of [false, true]) {
    const revoked = rig({ shown, unownedUntil: 65000 });
    await revoked.start();
    await revoked.until(() => revoked.cached.size === rows.length);
    assert(revoked.revoked.length < 10, "unchanged not_owner demand backs off across both lanes");
    assert(revoked.now() >= 65000);
    assert(revoked.revoked.at(-1) - revoked.revoked.at(-2) >= 16000);
    revoked.controller.dispose();
  }

  const partialCohort = rig({ unavailableUntil: 65000 });
  await partialCohort.start();
  await partialCohort.until(() => partialCohort.cached.size === rows.length - 1);
  assert(partialCohort.now() < 65000, "one unavailable member never blocks later cohorts");
  assert(!partialCohort.cached.has(rows[0].number));
  await partialCohort.until(() =>
    [...partialCohort.timers.values()].some((timer) => timer.at >= 65000),
  );
  await partialCohort.until(() => partialCohort.cached.size === rows.length);
  await partialCohort.until(() => partialCohort.timers.size === 0);
  assert(
    partialCohort.batches.at(-1).length === 1,
    "deferred retry asks only for the uncached member",
  );
  partialCohort.controller.dispose();

  const laterVisible = rig();
  await laterVisible.start();
  await laterVisible.until(() => laterVisible.cached.size === rows.length);
  await laterVisible.until(() => laterVisible.timers.size === 0);
  laterVisible.controller.setShown(true);
  await settle();
  laterVisible.deferVisible(65000);
  await settle();
  assert.equal(laterVisible.cached.size, rows.length - 1);
  await laterVisible.until(() => laterVisible.cached.size === rows.length);
  assert(
    laterVisible.now() >= 65000,
    "partial visible demand survives a previously completed pass",
  );
  laterVisible.controller.setShown(false);
  await laterVisible.until(() => laterVisible.timers.size === 0);
  laterVisible.controller.dispose();

  const transient = rig({ inventory: closedRows, failedCatalogReads: 1 });
  await transient.start();
  await transient.until(() => transient.cached.size === rows.length);
  await transient.until(() => transient.timers.size === 0);
  transient.controller.dispose();

  const transientPrepare = rig({ failedPrepareReads: 1 });
  await transientPrepare.start();
  await transientPrepare.until(() => transientPrepare.cached.size === rows.length);
  await transientPrepare.until(() => transientPrepare.timers.size === 0);
  transientPrepare.controller.dispose();

  const unavailable = rig({ notGithub: true });
  await unavailable.start();
  await unavailable.next();
  assert.equal(unavailable.timers.size, 0, "an unrefreshable source never starts a retry loop");
  assert.equal(unavailable.requests.length, 1);
  unavailable.controller.dispose();

  const partial = rig({ partialReceipts: 2 });
  await partial.start();
  await partial.until(() => partial.cached.size === rows.length);
  await partial.until(() => partial.timers.size === 0);
  partial.controller.dispose();

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
    recoveredRaceAndRevision: [coldRace.cached.size, revised.cached.size],
    recoveredTransientAndPartial: [transient.cached.size, partial.cached.size],
    cachedPastPartialCohort: partialCohort.cached.size,
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
