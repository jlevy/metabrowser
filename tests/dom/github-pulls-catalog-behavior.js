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
function rig(panel, { cached = 6000, automatic = true } = {}) {
  const state = {
    cached,
    automatic,
    refreshing: true,
    generation: "one",
    first: 8000,
    total: 8000,
    repositoryTotal: 9000,
  };
  const requests = [];
  const waiting = [];
  const timers = new Map();
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
      last_refresh: null,
      fetched: state.cached,
      total: state.total,
      repository_total: state.repositoryTotal,
      catalog_fetched: state.cached + 100,
      generation: state.generation,
      complete: false,
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
  const controller = panel.createPullsController({
    request(method, route, options) {
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
    now: () => Date.parse("2026-09-17T12:00:30Z"),
    isVisible: () => true,
    formatTime: (at) => at,
    render: (next) => {
      model = next;
    },
    markCurrent() {},
    markAnchor() {},
    reveal() {},
    open() {},
    filterChanged() {},
  });
  return {
    state,
    requests,
    waiting,
    timers,
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
  assert.equal(page.model().countSuffix, " PRs on jlevy/metabrowser");
  assert.equal(page.model().window, "Showing last 500");
  const version = page.model().rowsVersion;
  page.state.cached = 7000;
  page.requests.length = 0;
  page.controller.onVisibilityChange();
  await settle();
  assert.equal(page.controller.snapshot().rows, 500);
  assert.equal(page.model().rowsVersion, version);
  assert.equal(page.requests.length, 1, "older catalog growth preserves the displayed prefix");
  page.requests.length = 0;
  await page.controller.loadMore();
  assert.equal(page.controller.snapshot().rows, 1000);
  assert.equal(page.requests.length, 5);
  assert(
    page.requests.every((request) => request.method === "GET"),
    "cached expansion needs no provider work",
  );
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

  const emptyFilter = {
    ...page.envelope("/api/plugin/github/pulls?limit=0"),
    fetched: 0,
    total: 0,
    repository_total: 17,
    complete: true,
  };
  assert.equal(
    panel.describeLanding(emptyFilter, (at) => at),
    "Select a pull request.",
  );
  assert.equal(
    panel.describeLanding({ ...emptyFilter, repository_total: 0 }, (at) => at),
    "No pull requests.",
  );
  assert.equal(
    panel.describeLanding({ ...emptyFilter, repository_total: null }, (at) => at),
    "Select a pull request.",
  );

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

  const resume = rig(panel, { cached: 500 });
  resume.state.refreshing = false;
  resume.state.total = 500;
  resume.state.repositoryTotal = 5000;
  await resume.controller.start({ shown: true });
  await settle();
  assert.equal(resume.controller.snapshot().rows, 500);
  assert.deepEqual(
    resume.requests.filter((request) => request.method === "POST").map((request) => request.body),
    [{ state: "open", target: 500 }],
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
  const oldVersion = refreshRace.model().rowsVersion;
  refreshRace.state.automatic = false;
  refreshRace.state.generation = "two";
  refreshRace.state.first += 1;
  refreshRace.controller.onVisibilityChange();
  await settle();
  await refreshRace.respond();
  void refreshRace.controller.retry();
  await settle();
  refreshRace.state.refreshing = true;
  await refreshRace.respond(1);
  await refreshRace.respond(0);
  assert.equal(refreshRace.waiting.length, 0);
  assert.equal(refreshRace.model().rowsVersion, oldVersion);
  assert.equal(refreshRace.model().rows[0].number, 8000);
  assert.match(refreshRace.model().progress, /Fetching catalog/);
  assert.equal(refreshRace.controller.snapshot().timer, "fast");
  refreshRace.controller.onVisibilityChange();
  await settle();
  while (refreshRace.waiting.length > 0) {
    await refreshRace.respond();
  }
  assert.equal(refreshRace.model().rows[0].number, 8001);
  refreshRace.dispose();

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
    JSON.stringify({
      defaultFilter: "open",
      initialRows: 500,
      explicitRows: 1000,
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
      emptyFilterDoesNotHideOtherPulls: true,
      freshPartialCatalogResumes: true,
    }),
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
