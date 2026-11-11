// Background freshness in the browser: what the Pulls panel asks to prefetch and when, and what
// the pull-request page asks of the catalog, says of a record the catalog checked, and shows
// when the head moved. Both controllers load whole from the production modules; the clock,
// visibility, the network, and timers are injected, and every request is answered at once.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const root = path.resolve(__dirname, "../..");
const PREFETCH = "/api/plugin/github/pulls-prefetch";
const CATALOG = "/api/plugin/github/pulls-refresh";
const settle = async () => {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
};

/** A Pulls list over pull requests 120 down to 101, as the route answers it. */
function listEnvelope(state, route) {
  const params = new URL(route, "http://localhost").searchParams;
  return {
    state: state.listState,
    reason: null,
    source: "https://github.com/octo/demo",
    list: params.get("state") ?? "open",
    fetched_at: state.fetchedAt,
    count_at: state.fetchedAt,
    reader: "gh:octo-reader",
    fresh_for_s: 60,
    refreshing: state.refreshing,
    last_refresh: state.lastRefresh,
    fetched: 20,
    total: 20,
    repository_total: 20,
    catalog_fetched: 20,
    generation: "epoch:1",
    complete: true,
    truncated: false,
    limit: 100,
    next_after: null,
    rows: Array.from({ length: 20 }, (_, index) => ({
      number: 120 - index,
      title: `PR ${120 - index}`,
      state: "open",
      draft: false,
      merged_at: null,
      author: "octo",
      updated_at: "2026-09-17T11:00:00Z",
      base_ref: "topic",
      head_ref: `work-${120 - index}`,
      head_repository: "octo/demo",
      head_oid: "0".repeat(40),
    })),
  };
}

function panelRig(panel, { current = null } = {}) {
  const state = {
    now: Date.parse("2026-09-17T12:00:30Z"),
    visible: true,
    online: true,
    listState: "current",
    refreshing: false,
    fetchedAt: "2026-09-17T12:00:00Z",
    lastRefresh: {
      outcome: "succeeded",
      message: null,
      reset_at: null,
      at: "2026-09-17T12:00:00Z",
    },
  };
  const prefetches = [];
  // While `state.holdPrefetch` is set, a prefetch POST waits here until `release()`.
  const held = [];
  const opened = [];
  const timers = new Map();
  let model = null;
  // What the lane reports when the panel follows it: the item running, and the queue.
  state.report = { running: null, queued: [] };
  const controller = panel.createPullsController(
    {
      async request(method, route, options) {
        if (route === PREFETCH && method === "GET") {
          return { status: 200, etag: null, body: state.report };
        }
        if (route === PREFETCH) {
          prefetches.push(options.body);
          const answer = { status: 202, etag: null, body: { prefetch: "started", queued: 1 } };
          if (state.holdPrefetch) {
            return new Promise((resolve) => held.push(() => resolve(answer)));
          }
          return answer;
        }
        if (method === "POST") {
          return { status: 200, etag: null, body: { pulls: listEnvelope(state, route) } };
        }
        if (route.startsWith("/api/plugin/github/pull?")) {
          return { status: 404, etag: null, body: null };
        }
        return { status: 200, etag: null, body: listEnvelope(state, route) };
      },
      schedule(callback, delayMs) {
        const id = Symbol();
        timers.set(id, { callback, delayMs });
        return id;
      },
      cancel: (id) => timers.delete(id),
      now: () => state.now,
      isVisible: () => state.visible,
      isOnline: () => state.online,
      formatTime: (at) => at,
      render(painted) {
        model = painted;
      },
      markCurrent() {},
      markAnchor() {},
      reveal() {},
      open(route) {
        opened.push(route.number);
      },
      filterChanged() {},
    },
    { filter: "open", current },
  );
  return {
    state,
    prefetches,
    opened,
    controller,
    model: () => model,
    async release() {
      for (const answer of held.splice(0)) {
        answer();
      }
      await settle();
    },
    async fire(delayMs) {
      const entries = [...timers.entries()].filter(([, timer]) => timer.delayMs === delayMs);
      for (const [id, timer] of entries) {
        timers.delete(id);
        timer.callback();
      }
      await settle();
    },
  };
}

/** A pull envelope the catalog vouched for, from the recorded page answers. */
function vouched(recorded, { checkedAt, fetchedAt }) {
  const envelope = structuredClone(recorded.current.body);
  envelope.state = "current";
  envelope.refreshing = false;
  envelope.fetched_at = fetchedAt;
  envelope.record.fetched_at = fetchedAt;
  envelope.verified_at = checkedAt;
  envelope.verified_by = "catalog";
  envelope.head_moved = false;
  envelope.checks_pending = false;
  envelope.last_refresh = { outcome: "succeeded", message: null, reset_at: null, at: fetchedAt };
  return envelope;
}

function pageRig(page, envelope) {
  const state = { now: Date.parse("2026-09-17T12:00:10Z"), visible: true, online: true };
  const calls = [];
  const timers = new Map();
  let model = null;
  /** What the next GET answers: 200 with an envelope, or a 304, and the header it carries. */
  let next = { status: 200, verified: null, body: envelope };
  const controller = page.createPullController(
    {
      async request(method, route, options) {
        calls.push({ method, route, body: options.body });
        if (method === "POST" && route === CATALOG) {
          return { status: 202, etag: null, body: { refresh: "started" } };
        }
        if (method === "POST") {
          return { status: 200, etag: null, body: { refresh: "not_due", pull: envelope } };
        }
        if (next.status === 304) {
          return { status: 304, etag: '"pull"', body: null, verified: next.verified };
        }
        return { status: 200, etag: '"pull"', body: next.body, verified: next.verified };
      },
      schedule(callback, delayMs) {
        const id = Symbol();
        timers.set(id, { callback, delayMs });
        return id;
      },
      cancel: (id) => timers.delete(id),
      now: () => state.now,
      isVisible: () => state.visible,
      isOnline: () => state.online,
      render(painted) {
        model = painted;
      },
      renderMarkdown() {},
      reload() {},
      navigate() {},
    },
    { number: envelope.number, tab: "" },
  );
  return {
    state,
    calls,
    controller,
    model: () => model,
    answer(status, verified = null, body = envelope) {
      next = { status, verified, body };
    },
    /** The delays of the timers set, in order. */
    delays() {
      return [...timers.values()].map((timer) => timer.delayMs).sort((a, b) => a - b);
    },
    async fire(delayMs) {
      const entries = [...timers.entries()].filter(([, timer]) => timer.delayMs === delayMs);
      for (const [id, timer] of entries) {
        timers.delete(id);
        timer.callback();
      }
      await settle();
    },
    take() {
      return calls.splice(0).map((call) => `${call.method} ${call.route}`);
    },
  };
}

(async () => {
  const panel = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pulls-panel.js")).href
  );
  const pageModule = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const recorded = JSON.parse(
    fs.readFileSync(path.join(root, "tests/fixtures/github-pull-page-responses.json"), "utf8"),
  );
  const facts = {};

  // ── The Pulls panel ─────────────────────────────────────────

  // A scan the server finished: one prefetch of the top rows and what it found changed.
  const shown = panelRig(panel, { current: 118 });
  await shown.controller.start({ shown: true });
  await settle();
  assert.equal(shown.prefetches.length, 1, "a finished scan asks for one prefetch");
  facts.afterScan = shown.prefetches[0];
  assert.equal(shown.prefetches[0].changed, true);
  assert(!shown.prefetches[0].records.includes(118), "the open row's record is the page's own");
  await shown.controller.onVisibilityChange();
  await settle();
  facts.sameScanAsksOnce = shown.prefetches.length === 1;
  assert(facts.sameScanAsksOnce, "the same scan is not prefetched again");
  shown.state.fetchedAt = "2026-09-17T12:01:05Z";
  shown.state.now = Date.parse("2026-09-17T12:01:06Z");
  await shown.controller.onVisibilityChange();
  await settle();
  facts.nextScanAsksAgain = shown.prefetches.length === 2;
  assert(facts.nextScanAsksAgain, "the next scan is prefetched");

  // The reader lands on a row: its neighbours, the top rows, and its own files.
  shown.controller.activate(110);
  await settle();
  facts.afterLanding = shown.prefetches.at(-1);
  assert.deepEqual(shown.opened, [110]);
  assert.equal(facts.afterLanding.changed, false);
  assert.deepEqual(facts.afterLanding.files, [110, 111, 109]);

  // The panel follows the lane it started: the row whose record it reads breathes, until
  // the lane has nothing left.
  const { FAST_POLL_MS } = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  shown.state.report = {
    running: { kind: "record", number: 111 },
    queued: [{ kind: "record", number: 109 }],
  };
  await shown.fire(FAST_POLL_MS);
  facts.breathingWhileRead = shown.model().refreshingRows ?? [];
  // Offline, nothing breathes that cannot finish, and the panel stops following the lane.
  shown.state.online = false;
  shown.controller.onOffline();
  await settle();
  facts.breathingOffline = shown.model().refreshingRows ?? [];
  shown.state.online = true;
  shown.state.report = { running: null, queued: [] };
  await shown.fire(FAST_POLL_MS);
  facts.breathingAfter = shown.model().refreshingRows ?? [];
  assert.deepEqual(facts.breathingWhileRead, [111]);
  assert.deepEqual(facts.breathingOffline, []);
  assert.deepEqual(facts.breathingAfter, []);
  shown.controller.dispose();

  // A walk faster than the prefetch POST answers: each landing made while one is on its way
  // waits as the one pending ask, sent when it answers, from the row landed on last.
  const walk = panelRig(panel);
  await walk.controller.start({ shown: true });
  await settle();
  walk.prefetches.splice(0);
  walk.state.holdPrefetch = true;
  for (const number of [115, 114, 113]) {
    walk.controller.activate(number);
    await settle();
  }
  facts.walkAsksInFlight = walk.prefetches.length;
  walk.state.holdPrefetch = false;
  await walk.release();
  facts.walkFiles = walk.prefetches.map((ask) => ask.files);
  assert.equal(facts.walkAsksInFlight, 1, "one ask is on its way at a time");
  assert.deepEqual(facts.walkFiles, [
    [115, 116, 114],
    [113, 114, 112],
  ]);
  walk.controller.dispose();

  // A scan still running, a list whose refresh failed, a hidden panel, and offline.
  const quiet = {};
  for (const [name, change] of Object.entries({
    refreshing: (state) => {
      state.refreshing = true;
    },
    failed: (state) => {
      state.lastRefresh = {
        outcome: "network_error",
        message: "GitHub could not be reached",
        reset_at: null,
        at: "2026-09-17T12:00:00Z",
      };
    },
    hidden: (state) => {
      state.visible = false;
    },
    offline: (state) => {
      state.online = false;
    },
  })) {
    const rig = panelRig(panel);
    change(rig.state);
    await rig.controller.start({ shown: true });
    await settle();
    rig.controller.activate(115);
    await settle();
    quiet[name] = rig.prefetches.length;
    rig.controller.dispose();
  }
  facts.quiet = quiet;
  // A scan still running asks nothing of its own, but a reader's landing still does.
  assert.deepEqual(quiet, { refreshing: 1, failed: 0, hidden: 0, offline: 0 });

  // ── The pull-request page ───────────────────────────────────

  const { describePull, SLOW_POLL_MS } = pageModule;
  const checkedAt = "2026-09-17T12:00:00Z";
  const fetchedAt = "2026-09-17T09:00:00Z";
  const envelope = vouched(recorded, { checkedAt, fetchedAt });
  const view = pageRig(pageModule, envelope);
  await view.controller.start();
  await settle();
  facts.firstRead = view.take();
  facts.checked = view.model().freshness;
  // A minute on, the record's check has lapsed: the page asks for the catalog's scan first,
  // then reads, and the read's 304 carries the next check in its header.
  view.state.now = Date.parse("2026-09-17T12:01:01Z");
  view.answer(304, "catalog 2026-09-17T12:01:01Z");
  await view.fire(SLOW_POLL_MS);
  facts.lapsedRead = view.take();
  facts.checkedAfter304 = view.model().freshness;
  // Within the window of that ask, nothing more is asked.
  view.state.now = Date.parse("2026-09-17T12:01:31Z");
  await view.fire(SLOW_POLL_MS);
  facts.withinWindow = view.take();
  view.controller.dispose();

  // The catalog's next scan running: its last check still vouches, the 304 says the scan
  // runs, and the page reads again in a fast poll, so a change that scan publishes is
  // refreshed then, not a slow poll later.
  const { FAST_POLL_MS: fastPoll } = pageModule;
  const scanning = pageRig(pageModule, envelope);
  await scanning.controller.start();
  await settle();
  scanning.take();
  scanning.state.now = Date.parse("2026-09-17T12:01:01Z");
  scanning.answer(304, `catalog ${checkedAt} scanning`);
  await scanning.fire(SLOW_POLL_MS);
  facts.scanningRead = scanning.take();
  facts.scanningNextPolls = scanning.delays();
  const changed = structuredClone(envelope);
  changed.state = "stale";
  changed.verified_by = "fetch";
  changed.verified_at = fetchedAt;
  scanning.answer(200, `fetch ${fetchedAt}`, changed);
  scanning.state.now = Date.parse("2026-09-17T12:01:02Z");
  await scanning.fire(fastPoll);
  await scanning.fire(pageModule.REFRESH_ASK_MS);
  facts.scanPublishedChange = scanning.take();
  facts.afterScanPolls = scanning.delays();
  assert(facts.scanningNextPolls.includes(fastPoll), "a running scan is polled fast");
  scanning.controller.dispose();

  // A record the catalog never vouched for, its checks still running: the page refreshes
  // it once a window instead, and never asks the catalog for it.
  const pending = structuredClone(envelope);
  pending.state = "stale";
  pending.verified_by = "fetch";
  pending.verified_at = fetchedAt;
  pending.checks_pending = true;
  const checks = pageRig(pageModule, pending);
  checks.state.now = Date.parse("2026-09-17T12:01:30Z");
  await checks.controller.start();
  await checks.fire(pageModule.REFRESH_ASK_MS);
  facts.pendingChecks = checks.take();
  facts.pendingFreshness = checks.model().freshness;
  checks.controller.dispose();

  // The head moved: the page says so over the diff it keeps, and the refresh offers the newer.
  const moved = { ...pending, checks_pending: false, head_moved: true };
  const page = { number: moved.number, tab: "files", nowMs: Date.parse("2026-09-17T12:01:30Z") };
  facts.headMoved = describePull(moved, { ...page, refreshDue: true }).newCommits;
  facts.headMovedOffline = describePull(moved, { ...page, online: false }).newCommits;
  facts.headStill = describePull({ ...moved, head_moved: false }, page).newCommits;

  console.log(JSON.stringify(facts, null, 2));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
