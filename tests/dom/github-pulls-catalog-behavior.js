const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const settle = async () => {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
};

// Controlled contract fixtures complement the production route recording: delayed requests
// deliberately ignore abort, so ownership guards must also reject their late responses.
function rig(panel, { cached = 6000, automatic = true, filter = "open" } = {}) {
  const state = {
    cached,
    automatic,
    now: Date.parse("2026-09-17T12:00:30Z"),
    online: true,
    visible: true,
    refreshing: true,
    complete: false,
    generation: "one",
    first: 8000,
    total: 8000,
    repositoryTotal: 9000,
    tailNear: false,
  };
  const requests = [];
  const prefetches = [];
  const waiting = [];
  const timers = new Map();
  const flashes = [];
  let model;
  function envelope(route) {
    const params = new URL(route, "http://localhost").searchParams;
    const after = Number(params.get("after"));
    const start = after ? state.first - after + 1 : 0;
    const limit = Number(params.get("limit") ?? 100);
    const count = Math.min(limit, Math.max(0, state.cached - start));
    return {
      state: "current",
      reason: null,
      source: "https://github.com/jlevy/metabrowser",
      list: params.get("state") ?? "open",
      fetched_at: "2026-09-17T12:00:00Z",
      count_at: "2026-09-17T12:00:00Z",
      reader: "gh:reader",
      fresh_for_s: 60,
      refreshing: state.refreshing,
      last_refresh: state.lastRefresh ?? null,
      fetched: state.cached,
      total: state.total,
      repository_total: state.repositoryTotal,
      catalog_fetched: state.cached + 100,
      generation: state.generation,
      complete: state.complete,
      truncated: false,
      limit,
      next_after: start + limit < state.cached ? state.first - start - limit + 1 : null,
      rows: Array.from({ length: count }, (_, index) => ({
        number: state.first - start - index,
        title: `PR ${state.first - start - index}`,
        state: "open",
        draft: false,
        merged_at: null,
        author: "reader",
        updated_at: "2026-09-17T12:00:00Z",
        base_ref: "main",
        head_ref: "branch",
        head_repository: "jlevy/metabrowser",
      })),
    };
  }
  function answer(request) {
    return {
      status: request.method === "POST" ? 202 : 200,
      etag: null,
      body:
        request.method === "POST"
          ? { pulls: envelope(`/api/plugin/github/pulls?state=${request.body.state}&limit=0`) }
          : envelope(request.route),
    };
  }
  const controller = panel.createPullsController(
    {
      request(method, route, options) {
        if (route === "/api/plugin/github/pulls-prefetch") {
          // Background prefetch is the prefetch behavior's subject, not this one's.
          prefetches.push(options.body);
          return Promise.resolve({ status: 202, etag: null, body: { prefetch: "started" } });
        }
        const request = { method, route, body: options.body, signal: options.signal };
        requests.push(request);
        if (method === "GET") {
          assert(
            route.startsWith("/api/plugin/github/pulls?"),
            "metadata loading must not read PR details",
          );
          assert(
            Number(new URL(route, "http://localhost").searchParams.get("limit")) <= 100,
            "large display revalidation must use bounded cache pages",
          );
        }
        if (state.automatic) {
          return Promise.resolve(answer(request));
        }
        return new Promise((resolve) => waiting.push({ ...request, resolve }));
      },
      schedule(callback, delay) {
        const id = Symbol();
        timers.set(id, { callback, delay });
        return id;
      },
      cancel: (id) => timers.delete(id),
      now: () => state.now,
      isVisible: () => state.visible,
      isOnline: () => state.online,
      formatTime: (at) => at,
      render: (next, _identity, arrivals) => {
        model = next;
        if (arrivals.length > 0) {
          flashes.push(arrivals);
        }
      },
      markCurrent() {},
      markAnchor() {},
      reveal() {},
      open() {},
      filterChanged() {},
      recheckTail() {
        queueMicrotask(() => {
          if (state.tailNear) {
            void controller.reachedEnd();
          }
        });
      },
    },
    { filter },
  );
  return {
    state,
    requests,
    waiting,
    timers,
    flashes,
    controller,
    envelope,
    model: () => model,
    async respond(index = 0, response = null) {
      const request = waiting.splice(index, 1)[0];
      assert(request, "a controlled request must be waiting");
      request.resolve(response ?? answer(request));
      await settle();
      return request;
    },
    dispose() {
      controller.dispose();
      assert.equal(timers.size, 0);
    },
  };
}

(async () => {
  const panel = await import(
    pathToFileURL(
      path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/github/pulls-panel.js"),
    ).href
  );
  assert.deepEqual(panel.LISTS, ["open", "closed", "all"]);
  const page = rig(panel);
  await page.controller.start({ shown: true });
  assert.equal(page.controller.snapshot().filter, "open");
  assert.equal(page.controller.snapshot().rows, 500);
  assert.equal(page.requests.length, 5);
  assert.equal(page.model().countNumber, "9,000");
  assert.equal(page.model().countSuffix, " PRs on ");
  assert.equal(page.model().repository, "jlevy/metabrowser");
  assert.equal(page.model().window, "Showing last 500");
  const version = page.model().rowsVersion;
  page.state.cached = 7000;
  page.requests.length = 0;
  page.controller.onVisibilityChange();
  await settle();
  assert.equal(page.controller.snapshot().rows, 500);
  assert.equal(page.model().rowsVersion, version);
  assert.equal(page.requests.length, 1, "older catalog growth preserves the displayed prefix");
  page.state.refreshing = false;
  page.state.lastRefresh = {
    outcome: "rate_limited",
    reset_at: null,
    message: null,
    at: "2026-09-17T12:00:00Z",
  };
  page.controller.onVisibilityChange();
  await settle();
  page.requests.length = 0;
  const expansion = page.controller.loadMore();
  assert.equal(page.model().connection.state, "paused");
  assert.match(page.model().connection.text, /rate limit/);
  await expansion;
  assert.equal(page.model().connection.state, "paused");
  assert.equal(page.controller.snapshot().rows, 1000);
  assert.equal(page.requests.length, 5);
  assert(
    page.requests.every((request) => request.method === "GET"),
    "cached expansion needs no provider work",
  );
  page.state.lastRefresh = null;
  page.state.refreshing = true;
  page.state.generation = "two";
  page.state.first += 1;
  page.requests.length = 0;
  page.controller.onVisibilityChange();
  await settle();
  assert.equal(page.controller.snapshot().rows, 1000);
  assert.equal(page.requests.length, 10, "a changed prefix revalidates in100-row pages");
  assert.equal(page.model().rows[0].number, 8001);
  page.state.repositoryTotal = null;
  page.state.total = null;
  page.controller.onVisibilityChange();
  await settle();
  assert.equal(page.model().countNumber, null, "unknown totals must not become zero");
  page.dispose();

  // Near the tail, add one cache page while holding selection and the existing prefix.
  const tail = rig(panel, { cached: 645 });
  tail.state.complete = true;
  tail.state.refreshing = false;
  tail.state.total = 645;
  await tail.controller.start({ shown: true });
  tail.controller.setCurrent(7750, { preserveScroll: true });
  tail.controller.setShown(false);
  tail.requests.length = 0;
  await tail.controller.reachedEnd();
  assert.equal(tail.requests.length, 0, "a hidden tail never reads ahead");
  tail.controller.setShown(true);
  await settle();
  tail.requests.length = 0;
  await Promise.all([tail.controller.reachedEnd(), tail.controller.reachedEnd()]);
  const scrollRows = tail.controller.snapshot().rows;
  assert.equal(scrollRows, 600);
  assert.equal(tail.controller.snapshot().current, 7750);
  assert.equal(tail.controller.snapshot().anchor, 7750);
  assert.equal(tail.requests.length, 1, "repeated approaches share the in-flight page");
  assert.match(tail.requests[0].route, /limit=100&after=7501$/u);
  await tail.controller.reachedEnd();
  const terminalRows = tail.controller.snapshot().rows;
  assert.equal(terminalRows, 645);
  assert.match(tail.requests[1].route, /limit=45&after=7401$/u);
  assert.equal(tail.model().loadMore, null);
  assert.equal(tail.model().window, null);
  await tail.controller.reachedEnd();
  await tail.controller.loadMore();
  assert.equal(tail.requests.length, 2, "the real filter tail is idle");
  assert(tail.requests.every((request) => request.method === "GET"));
  tail.dispose();

  // A partially cached page can finish later. Its remaining budget must determine
  // the request limit, so the next cursor cannot skip rows we did not hold.
  const growingTail = rig(panel, { cached: 500 });
  await growingTail.controller.start({ shown: true });
  growingTail.requests.length = 0;
  await growingTail.controller.reachedEnd();
  await growingTail.controller.reachedEnd();
  assert.deepEqual(
    growingTail.requests.map((request) => request.body),
    [{ state: "open", target: 600 }],
  );
  growingTail.state.cached = 550;
  growingTail.controller.onVisibilityChange();
  await settle();
  assert.equal(growingTail.controller.snapshot().rows, 550);
  growingTail.state.cached = 700;
  growingTail.controller.onVisibilityChange();
  await settle();
  assert.equal(growingTail.controller.snapshot().rows, 600);
  assert.match(growingTail.requests.at(-1).route, /limit=50&after=7451$/u);
  await growingTail.controller.reachedEnd();
  assert.equal(growingTail.controller.snapshot().rows, 700);
  assert.deepEqual(
    growingTail
      .model()
      .rows.slice(500)
      .map((row) => row.number),
    Array.from({ length: 200 }, (_, index) => 7500 - index),
  );
  growingTail.dispose();

  // The top poll can learn about older cache rows before the reader widens the budget.
  const cachedAhead = rig(panel, { cached: 500 });
  await cachedAhead.controller.start({ shown: true });
  assert.equal(cachedAhead.controller.snapshot().nextAfter, null);
  cachedAhead.state.cached = 700;
  cachedAhead.controller.onVisibilityChange();
  await settle();
  assert.equal(cachedAhead.controller.snapshot().nextAfter, null);
  cachedAhead.requests.length = 0;
  await cachedAhead.controller.reachedEnd();
  assert.equal(cachedAhead.controller.snapshot().rows, 600);
  assert.deepEqual(
    cachedAhead.requests.map(({ method, route }) => [method, route]),
    [["GET", "/api/plugin/github/pulls?state=open&limit=100&after=7501"]],
  );
  cachedAhead.dispose();

  // A refresh can report a new generation before its prefix is held. Read the new
  // top first, since the old tail would be a cursor into different content.
  const replacedTail = rig(panel, { cached: 500 });
  replacedTail.state.refreshing = false;
  await replacedTail.controller.start({ shown: true });
  await settle();
  replacedTail.state.cached = 700;
  replacedTail.state.generation = "two";
  replacedTail.state.first += 1;
  await replacedTail.controller.reload();
  replacedTail.requests.length = 0;
  await replacedTail.controller.reachedEnd();
  assert.equal(replacedTail.controller.snapshot().rows, 600);
  assert.equal(replacedTail.model().rows[0].number, 8001);
  assert.equal(replacedTail.requests[0].route, "/api/plugin/github/pulls?state=open&limit=100");
  assert.match(replacedTail.requests.at(-1).route, /after=7502$/u);
  replacedTail.dispose();

  // A refused tail read keeps automatic scrolling idle and restores the button.
  const refusedTail = rig(panel);
  await refusedTail.controller.start({ shown: true });
  refusedTail.state.automatic = false;
  const refused = refusedTail.controller.reachedEnd();
  await settle();
  assert.equal(refusedTail.model().loadMore, "loading");
  await refusedTail.respond(0, { status: 503, etag: null, body: null });
  await refused;
  assert.equal(refusedTail.controller.snapshot().rows, 500);
  assert.equal(refusedTail.model().loadMore, "ready");
  assert.match(refusedTail.model().connection.text, /HTTP 503/u);
  refusedTail.requests.length = 0;
  await refusedTail.controller.reachedEnd();
  assert.equal(refusedTail.requests.length, 0);
  refusedTail.state.automatic = true;
  await refusedTail.controller.loadMore();
  assert.equal(refusedTail.controller.snapshot().rows, 1100);
  assert.notEqual(refusedTail.model().connection.state, "unavailable");
  assert(refusedTail.requests.every((request) => request.method === "GET"));
  refusedTail.dispose();

  // One observer crossing during an outage remains relevant after the poll recovers.
  const recoveredTail = rig(panel, { cached: 645 });
  recoveredTail.state.complete = true;
  recoveredTail.state.refreshing = false;
  recoveredTail.state.total = 645;
  await recoveredTail.controller.start({ shown: true });
  recoveredTail.state.automatic = false;
  recoveredTail.controller.onVisibilityChange();
  await recoveredTail.respond(0, { status: 503, etag: null, body: null });
  recoveredTail.state.tailNear = true;
  await recoveredTail.controller.reachedEnd();
  assert.equal(recoveredTail.waiting.length, 0, "an errored catalog still blocks paging");
  recoveredTail.requests.length = 0;
  recoveredTail.controller.onVisibilityChange();
  await recoveredTail.respond(0, { status: 304, etag: null, body: null });
  assert.match(recoveredTail.waiting[0].route, /limit=100&after=7501$/u);
  await recoveredTail.controller.reachedEnd();
  assert.equal(recoveredTail.waiting.length, 1, "an outstanding tail read owns its window");
  // If the actual footer is still close after that page, there may be no observer edge.
  await recoveredTail.respond();
  assert.match(recoveredTail.waiting[0].route, /limit=45&after=7401$/u);
  await recoveredTail.respond();
  assert.equal(recoveredTail.controller.snapshot().rows, 645);
  assert.equal(recoveredTail.waiting.length, 0);
  assert(recoveredTail.requests.every((request) => request.method === "GET"));
  recoveredTail.dispose();

  const filterTail = rig(panel);
  await filterTail.controller.start({ shown: true });
  filterTail.state.automatic = false;
  const oldTail = filterTail.controller.reachedEnd();
  await settle();
  assert.equal(filterTail.waiting.length, 1);
  filterTail.controller.setFilter("closed");
  assert.equal(filterTail.waiting[0].signal.aborted, true);
  await filterTail.respond();
  await oldTail;
  assert.equal(filterTail.controller.snapshot().filter, "closed");
  assert.equal(filterTail.controller.snapshot().rows, 0);
  while (filterTail.waiting.length > 0) {
    await filterTail.respond();
  }
  assert.equal(filterTail.controller.snapshot().rows, 500);
  assert.equal(filterTail.controller.snapshot().displayLimit, 500);
  filterTail.dispose();

  const failedTail = rig(panel, { cached: 550 });
  failedTail.state.refreshing = false;
  failedTail.state.lastRefresh = {
    outcome: "gh_missing",
    reset_at: null,
    message: null,
    at: "2026-09-17T12:00:00Z",
  };
  await failedTail.controller.start({ shown: true });
  await settle();
  failedTail.requests.length = 0;
  await failedTail.controller.reachedEnd();
  assert.equal(failedTail.controller.snapshot().rows, 550);
  await failedTail.controller.reachedEnd();
  assert.equal(failedTail.requests.length, 1, "a failed provider leaves only cached continuation");
  assert.equal(failedTail.requests[0].method, "GET");
  failedTail.dispose();

  // A priority request raises the matching display target while the durable backfill runs.
  const partial = rig(panel, { cached: 100 });
  await partial.controller.start({ shown: true });
  await settle();
  assert.deepEqual(
    partial.requests.filter((request) => request.method === "POST").map((request) => request.body),
    [{ state: "open", target: 500 }],
  );
  await partial.controller.loadMore();
  assert.equal(partial.controller.snapshot().displayLimit, 1000);
  assert.deepEqual(partial.requests.at(-1).body, { state: "open", target: 1000 });
  partial.dispose();

  const priorityFilter = rig(panel, { cached: 100 });
  await priorityFilter.controller.start({ shown: true });
  await settle();
  priorityFilter.requests.length = 0;
  priorityFilter.controller.setFilter("closed");
  await settle();
  assert.deepEqual(
    priorityFilter.requests
      .filter((request) => request.method === "POST")
      .map((request) => request.body),
    [{ state: "closed", target: 500 }],
    "a reader's filter change can reprioritize an active catalog job",
  );
  priorityFilter.dispose();

  const resume = rig(panel, { cached: 500 });
  resume.state.refreshing = false;
  resume.state.total = 500;
  resume.state.repositoryTotal = 5000;
  await resume.controller.start({ shown: true });
  await settle();
  assert.equal(resume.controller.snapshot().rows, 500);
  assert.deepEqual(
    resume.requests.filter((request) => request.method === "POST").map((request) => request.body),
    [{ state: "open", target: 500, background: true }],
    "a fresh partial catalog resumes even when its matching window is full",
  );
  resume.controller.onVisibilityChange();
  await settle();
  assert.equal(
    resume.requests.filter((request) => request.method === "POST").length,
    1,
    "a paused worker's refusal does not cause a tight automatic retry loop",
  );
  resume.dispose();

  // Reopening transfers read ownership immediately, even if the cancelled read ignores abort.
  const race = rig(panel, { automatic: false });
  void race.controller.start({ shown: true });
  await settle();
  await race.respond(); // Old window follows the first100 rows.
  const oldWindow = race.waiting[0];
  race.controller.setShown(false);
  assert.equal(oldWindow.signal.aborted, true);
  race.controller.setShown(true);
  await settle();
  await race.respond(1); // New poll starts a new window despite the unresolved old one.
  assert.equal(race.waiting.length, 2);
  await race.respond(0); // Old finally must not release the new window owner.
  assert.equal(race.controller.snapshot().rows, 100);
  const count = race.requests.length;
  await race.controller.reachedEnd();
  assert.equal(race.requests.length, count, "old finally must not admit a duplicate new window");
  while (race.waiting.length > 0) {
    await race.respond();
  }
  assert.equal(race.controller.snapshot().rows, 500);

  // A changed prefix stays staged if one page belongs to another generation.
  const held = race.model().rowsVersion;
  race.state.generation = "two";
  race.state.first += 1;
  race.controller.onVisibilityChange();
  await settle();
  await race.respond();
  race.state.generation = "three";
  await race.respond();
  assert.equal(race.model().rowsVersion, held);
  assert.equal(race.model().rows[0].number, 8000);
  race.controller.onVisibilityChange();
  await settle();
  await race.respond();
  const oldStage = race.waiting[0];
  race.controller.setFilter("closed");
  await settle();
  assert.equal(oldStage.signal.aborted, true);
  await race.respond(0); // Late old-filter staged response cannot replace the new filter.
  while (race.waiting.length > 0) {
    await race.respond();
  }
  assert.equal(race.model().filter, "closed");
  assert.equal(race.model().rows[0].number, 8001);
  race.dispose();

  // Retry's acknowledgement can arrive while a changed prefix is being staged. The older
  // GET must neither publish its rows nor replace the newer envelope/timer afterwards.
  const refreshRace = rig(panel);
  refreshRace.state.refreshing = false;
  await refreshRace.controller.start({ shown: true });
  assert.match(refreshRace.model().connection.text, /Fetching pull requests|Catalog paused/u);
  const oldVersion = refreshRace.model().rowsVersion;
  refreshRace.state.automatic = false;
  refreshRace.state.generation = "two";
  refreshRace.state.first += 1;
  refreshRace.controller.onVisibilityChange();
  await settle();
  await refreshRace.respond();
  void refreshRace.controller.reload();
  await settle();
  refreshRace.state.refreshing = true;
  await refreshRace.respond(1);
  await refreshRace.respond(0);
  assert.equal(refreshRace.waiting.length, 0);
  assert.equal(refreshRace.model().rowsVersion, oldVersion);
  assert.equal(refreshRace.model().rows[0].number, 8000);
  // Rows are held, so the refresh runs under their plain age, breathing, with no spinner.
  assert.equal(refreshRace.model().connection.state, "connected");
  assert.equal(refreshRace.model().connection.refreshing, true);
  assert.match(refreshRace.model().connection.text, /^Updated /u);
  assert.equal(refreshRace.model().connection.reload, false);
  assert.equal(refreshRace.controller.snapshot().timer, "fast");
  refreshRace.controller.onVisibilityChange();
  await settle();
  while (refreshRace.waiting.length > 0) {
    await refreshRace.respond();
  }
  assert.equal(refreshRace.model().rows[0].number, 8001);
  refreshRace.dispose();

  const at = (time) => new Date(time).toISOString();
  const makeFailure = (outcome, time, reset = null) => ({
    outcome,
    reset_at: reset,
    message: null,
    at: at(time),
  });
  const providerAsks = (test) =>
    test.requests.filter((request) => request.method === "POST").map((request) => request.body);
  async function tick(test) {
    const [id, task] = [...test.timers][0];
    test.timers.delete(id);
    task.callback();
    await settle();
  }
  async function watchRig(outcome, age = 0, reset = null) {
    const test = rig(panel, { cached: 500 });
    test.state.complete = true;
    test.state.refreshing = false;
    test.state.total = 500;
    test.state.lastRefresh = makeFailure(outcome, test.state.now - age, reset);
    await test.controller.start({ shown: true });
    await settle();
    return test;
  }

  // A visible direct or restored filter may move a running Open warm-up to its
  // own missing rows. The next unchanged wake is a cache read only.
  const direct = rig(panel, { filter: "closed", cached: 150 });
  await direct.controller.start({ shown: true });
  await settle();
  direct.controller.setFilter("all", { fromAddress: true });
  await settle();
  direct.controller.onFocus();
  await settle();
  assert.deepEqual(providerAsks(direct), [
    { state: "closed", target: 500 },
    { state: "all", target: 500 },
  ]);
  direct.dispose();

  const restored = rig(panel, { cached: 150 });
  await restored.controller.start({ shown: false, refreshAhead: true });
  await settle();
  assert.deepEqual(providerAsks(restored), [{ state: "open", target: 500, background: true }]);
  restored.controller.setShown(true);
  await settle();
  restored.controller.onFocus();
  await settle();
  assert.deepEqual(providerAsks(restored), [
    { state: "open", target: 500, background: true },
    { state: "open", target: 500 },
  ]);
  restored.dispose();

  // Only coherent top GETs can announce newly created PRs in a continuously visible list.
  const arrivals = rig(panel, { cached: 3, automatic: false });
  const baseTime = arrivals.state.now;
  const envelope = arrivals.envelope("?state=open");
  const row = (number, when, title = `PR ${number}`) => ({
    ...envelope.rows[0],
    number,
    title,
    created_at: at(baseTime + when),
  });
  const old = row(8000, -60_000);
  const reopened = row(7999, -70_000);
  const newer = row(8001, 1_000);
  const top = (generation, rows, changes = {}) => ({
    ...envelope,
    generation,
    complete: true,
    refreshing: false,
    fetched: rows.length,
    total: rows.length,
    rows,
    ...changes,
  });
  const receive = (body, status = 200) => arrivals.respond(0, { status, etag: '"top"', body });
  const update = async (body) => {
    arrivals.controller.onFocus();
    await receive(body);
  };
  const starting = arrivals.controller.start({ shown: true });
  await receive(top("epoch:1", [old]));
  await starting;
  assert.deepEqual(arrivals.flashes, [], "initial population is neutral");
  void arrivals.controller.reload();
  await receive({ pulls: top("epoch:2", [newer, old], { refreshing: true }) }, 202);
  assert.deepEqual(arrivals.flashes, [], "a POST cannot create arrivals");
  arrivals.state.now += 2_000;
  await update(
    top("epoch:2", [newer, { ...old, title: "Retitled" }, reopened], { refreshing: true }),
  );
  assert.deepEqual(arrivals.flashes, [[8001]], "only the newly created top row arrives");
  await update(top("epoch:3", [old, reopened], { refreshing: true }));
  await update(top("epoch:4", [newer, old, reopened], { refreshing: true }));
  assert.deepEqual(arrivals.flashes, [[8001]], "a live arrival cannot flash again on reopening");

  const settled = top("epoch:4", [newer, old, reopened]);
  await update(settled);
  arrivals.controller.setShown(false);
  arrivals.state.now += 4_000;
  arrivals.controller.setShown(true);
  await receive(null, 304);
  const hidden = row(8002, 4_000);
  await update(top("epoch:5", [hidden, ...settled.rows]));
  assert.deepEqual(arrivals.flashes, [[8001]], "a revalidated reopen excludes hidden arrivals");
  const visible = row(8003, 7_000);
  arrivals.state.now += 2_000;
  await update(top("epoch:6", [visible, hidden, ...settled.rows]));
  assert.deepEqual(arrivals.flashes, [[8001], [8003]], "the 304 can seed later visible arrivals");

  arrivals.controller.onOffline();
  arrivals.controller.onOnline();
  await receive(top("epoch:7", [row(8004, 9_000), visible, hidden]));
  await update(top("replacement:1", [row(8005, 10_000), visible, hidden]));
  assert.deepEqual(arrivals.flashes, [[8001], [8003]], "reconnect and catalog reset are neutral");
  arrivals.dispose();

  const watch = await watchRig("network_error");
  assert.equal(watch.model().connection.state, "paused");
  assert.equal(watch.model().rows.length, 500);
  watch.requests.length = 0;
  watch.state.online = false;
  watch.controller.onOffline();
  await watch.controller.reload();
  assert.equal(watch.model().connection.text, "Offline. Showing cached pull requests.");
  assert.equal(watch.model().connection.reload, false);
  await tick(watch);
  assert.deepEqual(providerAsks(watch), []);
  watch.state.online = true;
  watch.controller.onOnline();
  watch.controller.onFocus();
  await settle();
  assert.deepEqual(providerAsks(watch), [
    { state: "open", target: 500, background: true, reconnect: true },
  ]);
  watch.requests.length = 0;
  watch.controller.pause();
  watch.controller.onFocus();
  await settle();
  assert.equal(watch.requests.length, 0, "a parked page does not watch");
  watch.controller.resume();
  await settle();
  assert.equal(watch.requests.length, 1, "pageshow resumes the cache read");
  assert.deepEqual(providerAsks(watch), []);
  watch.dispose();

  const transient = await watchRig("network_error");
  assert.deepEqual(providerAsks(transient), []);
  transient.state.now += 60_001;
  transient.state.automatic = false;
  const outage = transient.model().connection.text;
  const steadyRetry = () => {
    // 500 rows are held: the retry breathes the outage text instead of a spinner.
    assert.deepEqual(transient.model().connection, {
      state: "paused",
      text: outage,
      reload: false,
      refreshing: true,
    });
    assert.equal(transient.model().live, outage);
    assert.equal(transient.model().rows.length, 500);
  };
  await tick(transient);
  await transient.respond();
  assert.deepEqual(providerAsks(transient), [{ state: "open", target: 500, background: true }]);
  steadyRetry();
  transient.state.refreshing = true;
  await transient.respond();
  steadyRetry();
  assert.equal(panel.refreshFailure(transient.envelope("?state=open"), at), null);
  transient.state.refreshing = false;
  transient.state.lastRefresh = makeFailure("succeeded", transient.state.now);
  transient.state.automatic = true;
  await tick(transient);
  assert.equal(transient.model().connection.state, "connected");
  assert.equal(transient.model().connection.reload, true);
  assert.equal(transient.model().connection.retrying, undefined);
  assert.notEqual(transient.model().live, outage);
  transient.dispose();

  const localFailure = await watchRig("network_error");
  localFailure.state.now += 60_001;
  localFailure.state.automatic = false;
  localFailure.controller.onFocus();
  await localFailure.respond(0, { status: 503, etag: null, body: null });
  assert.deepEqual(providerAsks(localFailure), [], "a failed local read never asks from old state");
  assert.equal(localFailure.model().connection.state, "unavailable");
  assert.equal(localFailure.model().rows.length, 500);
  localFailure.dispose();

  const auth = await watchRig("not_logged_in");
  assert.match(auth.model().connection.text, /gh auth login/u);
  auth.state.now += 90_000;
  await tick(auth);
  assert.deepEqual(providerAsks(auth), [], "setup does not probe at the normal freshness window");
  auth.state.now += 30_001;
  await tick(auth);
  assert.deepEqual(providerAsks(auth), [{ state: "open", target: 500, background: true }]);
  auth.dispose();

  const focus = await watchRig("gh_missing", 61_000);
  assert.deepEqual(providerAsks(focus), []);
  focus.controller.onFocus();
  focus.controller.onFocus();
  await settle();
  assert.deepEqual(providerAsks(focus), [{ state: "open", target: 500, background: true }]);
  focus.dispose();

  const reload = await watchRig("not_found_or_private");
  reload.state.automatic = false;
  const reloading = reload.controller.reload();
  await reload.controller.reload();
  assert.equal(reload.model().connection.state, "paused");
  assert.equal(reload.model().connection.refreshing, true, "rows are held: no spinner");
  assert.equal(reload.model().connection.retrying, undefined);
  assert.equal(reload.model().connection.reload, false);
  assert.deepEqual(providerAsks(reload), [{ state: "open", target: 500, retry: true }]);
  await reload.respond();
  await reloading;
  reload.dispose();

  const rate = await watchRig(
    "rate_limited",
    61_000,
    at(Date.parse("2026-09-17T12:00:30Z") + 8_000),
  );
  assert.match(rate.model().connection.text, /Next attempt after/u);
  assert.equal(rate.model().connection.reload, false);
  await rate.controller.reload();
  assert.deepEqual(providerAsks(rate), []);
  assert.equal([...rate.timers.values()][0].delay, 8_000);
  rate.state.now += 8_001;
  await tick(rate);
  assert.deepEqual(providerAsks(rate), [{ state: "open", target: 500, background: true }]);
  rate.dispose();

  // The tail of a canceled filter must leave a reconnect hint for the new list's top read.
  const wakeRace = rig(panel, { automatic: false });
  const oldStart = wakeRace.controller.start({ shown: true });
  await wakeRace.respond();
  assert.match(wakeRace.waiting[0].route, /state=open.*after=/u);
  wakeRace.controller.setFilter("closed");
  wakeRace.controller.onOnline();
  assert.equal(wakeRace.waiting[0].signal.aborted, true);
  await wakeRace.respond();
  await oldStart;
  assert.equal(wakeRace.timers.size, 0, "the old tail schedules nothing on the new filter");
  wakeRace.state.cached = 0;
  wakeRace.state.total = 0;
  wakeRace.state.complete = true;
  wakeRace.state.refreshing = false;
  wakeRace.state.lastRefresh = makeFailure("network_error", wakeRace.state.now);
  await wakeRace.respond();
  assert.deepEqual(providerAsks(wakeRace), [
    { state: "closed", target: 500, background: true, reconnect: true },
  ]);
  await wakeRace.respond();
  wakeRace.dispose();

  // An unsuccessful cache window waits for the regular poll instead of a tight retry loop.
  const failed = rig(panel, { automatic: false });
  void failed.controller.start({ shown: true });
  await settle();
  await failed.respond();
  await failed.respond(0, { status: 503, etag: null, body: null });
  assert.equal(failed.waiting.length, 0);
  assert.equal(failed.requests.length, 2);
  failed.dispose();
  console.log(
    JSON.stringify(
      {
        defaultFilter: "open",
        initialRows: 500,
        explicitRows: 1000,
        scrollRows,
        terminalRows,
        repeatedScrollSharesRequest: true,
        keepsSelection: true,
        cachedGrowthKeepsEveryRow: true,
        failedProviderUsesCacheOnly: true,
        hiddenTailIsIdle: true,
        staleTailCannotChangeFilter: true,
        progressOnlyReads: 1,
        generationPages: 10,
        detailReads: 0,
        priorityTarget: 1000,
        lateWindowRejected: true,
        ownerTransferred: true,
        mixedGenerationRejected: true,
        lateFilterRejected: true,
        failedWindowDoesNotSpin: true,
        newerRefreshKeepsOwnership: true,
        freshPartialCatalogResumes: true,
        offlineKeepsCache: true,
        reconnectUsesBackgroundHint: true,
        interactiveFilterKeepsPriority: true,
        directAndHistoryFiltersKeepPriority: true,
        hiddenWarmupYieldsToVisibleDemand: true,
        acceptedTopArrivalsAreOneShot: true,
        transientRetriesAutomatically: true,
        retryKeepsPriorFailure: true,
        localReadFailureDoesNotPost: true,
        setupUsesQuietProbe: true,
        focusCoalesces: true,
        parkAndResume: true,
        rateResetWake: true,
        reloadCoalesces: true,
        abortedTailKeepsWake: true,
      },
      null,
      2,
    ),
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
