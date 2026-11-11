// Exact production page/controller and route mount, with deferred provider/UI dependencies.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");

// Fake time drives the exact production controller; the POST acknowledgement is held
// across a normal poll tick, while final record publication happens before the next one.
async function heldPostCadence(page, full) {
  async function check({
    heldMs,
    waitCore,
    cancel = false,
    hide = false,
    settlement = null,
    peek = false,
    noCore = false,
  }) {
    let now = 0,
      visible = true,
      current,
      release,
      releaseGet,
      shown;
    const tasks = new Map(),
      gets = [],
      routes = [],
      etags = [];
    const absent = {
      ...full,
      state: "absent",
      reason: "not_cached",
      record: null,
      record_revision: null,
      fetched_at: null,
      core_preview: null,
      refreshing: false,
    };
    const preview = {
      ...absent,
      state: "pending",
      refreshing: true,
      core_preview: {
        source: full.source,
        number: 7,
        reader: full.record.reader,
        observed_at: full.record.fetched_at,
        revision: "a".repeat(64),
        pull: full.record.pull,
        comparison_state: "no_store",
      },
    };
    current = peek ? preview : waitCore ? absent : { ...full, state: "stale" };
    const controller = page.createPullController(
      {
        request: async (method, route, { etag }) => {
          if (method === "POST") {
            return new Promise((resolve) => {
              release = resolve;
            });
          }
          gets.push(now);
          routes.push(route);
          etags.push(etag);
          if (settlement !== null && now === (typeof settlement === "number" ? 3000 : 2000)) {
            return new Promise((resolve) => {
              releaseGet = resolve;
            });
          }
          return { status: 200, etag: current === preview ? '"preview"' : null, body: current };
        },
        schedule(callback, delay) {
          const token = Symbol();
          tasks.set(token, { callback, at: now + delay });
          return token;
        },
        cancel: (token) => tasks.delete(token),
        now: () => now,
        isVisible: () => visible,
        render(model) {
          shown = model;
        },
        reload() {},
        navigate() {},
      },
      {
        number: 7,
        tab: "",
        reader: peek ? { initial: { etag: '"peek"', body: preview }, fetchAfterMs: 0 } : null,
      },
    );
    async function advance(target) {
      for (;;) {
        const next = [...tasks]
          .filter(([, task]) => task.at <= target)
          .sort((a, b) => a[1].at - b[1].at)[0];
        if (!next) {
          break;
        }
        now = next[1].at;
        tasks.delete(next[0]);
        next[1].callback();
        await settle();
      }
      now = target;
    }
    const plain = "/api/plugin/github/pull?number=7";
    const waiting = `${plain}&wait_full_after=${preview.core_preview.revision}`;
    await controller.start();
    assert.deepEqual(routes, [plain], "the first GET is always plain");
    if (peek) {
      await advance(1000);
      assert.deepEqual(routes, [plain, plain], "a peeked preview cannot opt this page in");
      controller.dispose();
      return;
    }
    const requested = controller.requestRefresh();
    await settle();
    if (!waitCore) {
      // A stale cached record is already refreshing itself, so it offers no Refresh and
      // the reader's press sends nothing; the automatic ask, held below, is the POST. The
      // record keeps its plain age meanwhile.
      assert.match(shown.freshness, /^Fetched .+ via GitHub CLI$/);
      assert.equal(shown.revalidating, true);
      assert.equal(shown.canRefresh, false);
    }
    await advance(heldMs);
    assert.deepEqual(
      gets,
      [0],
      "unacknowledged selected POST admits no GET that could outrank its answer",
    );
    if (cancel) {
      controller.dispose();
    }
    if (hide) {
      visible = false;
      controller.onVisibilityChange();
    }
    current = waitCore
      ? noCore
        ? { ...preview, core_preview: null }
        : preview
      : { ...full, refreshing: true };
    release({ status: 202, etag: null, body: { pull: current } });
    await requested;
    await settle();
    if (cancel || hide) {
      assert.equal(tasks.size, 0, "hidden/disposed POST completion cannot schedule polling");
      return;
    }
    const due = Math.min(...[...tasks.values()].map((task) => task.at));
    assert.equal(
      due,
      waitCore ? 2000 : heldMs + 1000,
      "held core acknowledgement must retain the POST-start poll phase; cached-full refresh stays unchanged",
    );
    if (settlement === "wake" || settlement === "dispose") {
      await advance(2000);
      assert.deepEqual(
        routes,
        [plain, waiting],
        "the selected GET opts in with the shown revision",
      );
      assert.equal(etags[1], null, "the first opted GET can wait without an ETag");
      await controller.poll();
      assert.equal(gets.length, 2, "a held GET is the only poll in flight");
      await advance(2250);
      assert.equal(shown.corePreview, true);
      if (settlement === "dispose") {
        controller.dispose();
      }
      releaseGet({ status: 200, etag: '"full"', body: full });
      await settle();
      assert.equal(shown.corePreview, settlement === "dispose");
      if (settlement === "dispose") {
        assert.equal(tasks.size, 0, "a disposed page does not rearm on a late wake");
      } else {
        assert.equal(shown.pull.number, 7);
        assert.equal(controller.snapshot().etag, '"full"');
        assert.equal(controller.snapshot().timer, "slow");
      }
    } else if (typeof settlement === "number") {
      await advance(3000);
      assert.deepEqual(routes, [plain, waiting, waiting]);
      assert.equal(etags[2], '"preview"');
      await advance(settlement);
      releaseGet({ status: 304, etag: '"preview"', body: null });
      await settle();
      assert.equal(shown.corePreview, true);
      assert.deepEqual(
        [...tasks.values()].map((task) => task.at),
        [Math.max(4000, settlement)],
        "304 re-arms from the start of the held GET, including overrun",
      );
    } else if (waitCore) {
      current = preview;
      await advance(2000);
      assert.equal(routes[1], noCore ? plain : waiting);
      current = full;
      await advance(3000);
      assert.deepEqual(gets, [0, 2000, 3000]);
      assert.equal(routes[2], waiting, "a later verified core can enable the owned wait");
      await controller.poll();
      assert.equal(routes.at(-1), plain, "the full record ends the owned wait");
    } else {
      await advance(due);
      assert.deepEqual(routes, [plain, plain], "a refreshing cached record never waits");
    }
    controller.dispose();
    assert.equal(tasks.size, 0);
  }
  await check({ heldMs: 1700, waitCore: true });
  await check({ heldMs: 1400, waitCore: true });
  await check({ heldMs: 1700, waitCore: false });
  await check({ heldMs: 1700, waitCore: true, cancel: true });
  await check({ heldMs: 1700, waitCore: true, hide: true });
  await check({ heldMs: 1700, waitCore: true, settlement: "wake" });
  await check({ heldMs: 1700, waitCore: true, settlement: "dispose" });
  await check({ heldMs: 1700, waitCore: true, settlement: 3900 });
  await check({ heldMs: 1700, waitCore: true, settlement: 4100 });
  await check({ heldMs: 1700, waitCore: true, noCore: true });
  await check({ peek: true });
}

async function retentionCapability(routes) {
  for (const retainable of [true, false]) {
    let claim = 0,
      visible = null,
      stopped = 0,
      disposed = 0;
    const mount = routes.createViewMount({
      sdk: {
        ensureKindAssets: async () => {},
        getRegisteredView: () => ({
          render(node) {
            node.textContent = "custom useful content";
            return {
              ...(retainable
                ? {
                    cancelPending() {
                      stopped++;
                    },
                  }
                : {}),
              dispose() {
                disposed++;
                node.textContent = "";
              },
            };
          },
        }),
      },
      isCurrent: (token) => token === claim,
      beginNavigation: () => false,
      endNavigation() {},
      stageNode() {
        throw Error("unexpected initial stage");
      },
      renderNode: (node) => {
        visible = node;
      },
      renderHtml() {},
      showLoadFailure() {
        throw Error("unexpected failure");
      },
    });
    const host = routes.createPullPageHost({
      claim: () => ++claim,
      isCurrent: (token) => token === claim,
      mount: (token, route) => mount(token, "pull-request", route),
      mountList: async () => null,
      pathname: () => "/pull/7",
      pushHref() {},
      replaceHref() {},
    });
    await host.show({ number: 7, tab: "" });
    assert.equal(visible.textContent, "custom useful content");
    const retired = host.release();
    if (retainable) {
      assert.equal(stopped, 1);
      assert.equal(disposed, 0);
      assert.equal(visible.textContent, "custom useful content");
      assert.equal(typeof retired, "function");
      retired();
      assert.equal(disposed, 1);
      assert.equal(visible.textContent, "");
    } else {
      assert.equal(disposed, 1);
      assert.equal(visible.textContent, "");
      assert.equal(retired, null, "destructive-only custom view must not advertise retainable DOM");
    }
    host.dispose();
    assert.equal(disposed, 1, "release and later host disposal do not double-dispose custom view");
  }
}

async function run() {
  const timers = new Map();
  global.document = {
    visibilityState: "visible",
    addEventListener() {},
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  global.window = {
    location: { pathname: "/pull/7" },
    setTimeout(callback, delay) {
      const key = Symbol();
      timers.set(key, { callback, delay });
      return key;
    },
    clearTimeout(key) {
      timers.delete(key);
    },
  };
  global.DOMParser = class {
    parseFromString() {
      return { body: { firstElementChild: null } };
    }
  };
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const full = structuredClone(recorded.current.body);
  full.core_preview = null;
  full.pin = null;
  full.record.issue_comments = [];
  full.record.reviews = [];
  full.record.review_comments = [];
  full.record.check_runs = [];
  full.record.status = null;
  full.record.comparison = null;
  full.record.unavailable = { comparison: "no_store" };
  full.record_revision = "f".repeat(64);
  full.record.pull.body = "<img src=x onerror=alert(1)> preview description";
  await heldPostCadence(page, full);
  const preview = {
    ...full,
    state: "pending",
    record: null,
    fetched_at: null,
    record_revision: null,
    refreshing: true,
    comparison_route: null,
    core_preview: {
      source: full.source,
      number: 7,
      reader: full.record.reader,
      observed_at: full.record.fetched_at,
      revision: "a".repeat(64),
      pull: full.record.pull,
      comparison_state: "no_store",
    },
  };
  const absent = {
    ...preview,
    state: "absent",
    reason: "not_cached",
    refreshing: false,
    core_preview: null,
  };
  let current = absent,
    releasePost,
    settlementSignal,
    markdownRequests = 0;
  const posts = [];
  global.fetch = async (route, options) => {
    if (options.method === "POST") {
      posts.push(JSON.parse(options.body));
      return new Promise((resolve) => {
        releasePost = (body) =>
          resolve({
            status: 202,
            headers: { get: () => null },
            json: async () => ({ pull: body }),
          });
      });
    }
    if (route.includes("pull-markdown")) {
      markdownRequests++;
      return { status: 404, headers: { get: () => null }, json: async () => ({}) };
    }
    if (route.includes("wait_full_after=")) {
      settlementSignal = options.signal;
    }
    return { status: 200, headers: { get: () => null }, json: async () => current };
  };
  const mb = {
    perf,
    ensureAsset: async () => {},
    ensureKindAssets: async () => {},
    ...require("./sdk-ref-fixture.js").refHelpers(document),
    formatAge: () => ({ label: "now", className: "age" }),
    formatTimestamp: () => "now",
    navigation: { href: () => "/view/" },
    sourceKind: () => "filesystem",
    icons: { toggle: "" },
  };
  const container = new Element("main");
  const handle = page.mountPullPage(
    container,
    { number: 7, tab: "", reader: { initial: null, fetchAfterMs: 0 } },
    mb,
  );
  let ready = false;
  handle.ready.then(() => {
    ready = true;
  });
  await settle();
  assert.equal(
    ready,
    false,
    "initial absence does not replace useful content before selected fetch",
  );
  const ask = [...timers].find(([, task]) => task.delay === 0);
  assert.ok(ask);
  timers.delete(ask[0]);
  ask[1].callback();
  await settle();
  assert.deepEqual(posts, [{ number: 7, retry: true, wait_core: true }]);
  assert.equal(ready, false, "a pending POST does not make a skeleton useful");
  assert.ok(
    container.querySelector(".github-pull-loading"),
    "the selected missing record shows loading blocks while its POST is held",
  );
  assert.equal(container.querySelector(".spinner"), null, "cold progress uses only blocks");
  current = preview;
  releasePost(preview);
  await settle();
  await handle.ready;
  assert.equal(container.dataset.corePreview, "true");
  assert.equal(container.querySelector(".github-pull-plain").textContent, full.record.pull.body);
  const body = container.querySelector(".github-pull-body");
  assert.doesNotMatch(body.textContent, /Checks and statuses|No checks or statuses reported/);
  assert.doesNotMatch(container.textContent, /still loading|Loading details/);
  assert.equal(container.querySelector(".spinner"), null, "a description preview never spins");
  // Discussion is a section the preview does not have yet: delayed blocks, named for a reader.
  const discussionPending = body.querySelector(".github-pull-section-loading");
  assert.ok(discussionPending, "Discussion shows the shared skeleton blocks");
  assert.equal(discussionPending.getAttribute("aria-hidden"), "true");
  const pendingReveal = body.querySelectorAll(".mb-delayed-loading");
  assert.equal(pendingReveal.length, 1, "revealed after the quiet period");
  assert.equal(pendingReveal[0].getAttribute("role"), "status");
  assert.equal(pendingReveal[0].getAttribute("aria-label"), "Loading comments and reviews");
  // The header keeps the description's plain age, breathing while its details are fetched.
  const statusLine = container.querySelector(".github-pull-status");
  const age = statusLine.querySelector(".github-pull-freshness");
  assert.match(age.textContent, /^Description fetched .+ via GitHub CLI$/);
  assert.ok(age.classes.has("mb-refreshing") && age.classes.has("mb-refreshing-muted"));
  assert.equal(statusLine.getAttribute("aria-busy"), "true");
  function land(tab) {
    window.location.pathname = tab ? `/pull/7/${tab}` : "/pull/7";
    handle.land({ tab });
  }
  land("checks");
  const checksRoute = window.location.pathname;
  assert.equal(
    container
      .querySelectorAll(".tab-btn")
      .find((tab) => tab.getAttribute("aria-selected") === "true")?.textContent,
    "Checks",
  );
  assert.doesNotMatch(body.textContent, /Comments and reviews|No checks or statuses reported/);
  assert.equal(body.querySelector(".spinner"), null, "Checks does not spin either");
  assert.equal(
    body.querySelector(".mb-delayed-loading")?.getAttribute("aria-label"),
    "Loading checks and statuses",
    "Checks shows the same delayed blocks",
  );
  assert.ok(body.querySelector(".github-pull-section-loading"));
  assert.ok(body.classes.has("page-reading-column"), "Checks uses the reading column");
  land("");
  assert.equal(markdownRequests, 0, "preview stays plain and never asks for full-record Markdown");
  const model = page.describePull(preview, { number: 7, tab: "", nowMs: Date.now() });
  assert.equal(model.browse, null);
  assert.equal(model.canRetryComparison, false);
  assert.equal(model.comparison, null);
  assert.equal(model.contentReady, true);
  assert.equal(model.corePreview, true);
  const preparedCore = { ...preview.core_preview, comparison_state: "not_started" };
  const filesPage = { number: 7, tab: "files", nowMs: Date.now() };
  const idleCore = {
    ...preview,
    state: "absent",
    refreshing: false,
    core_preview: preparedCore,
    last_refresh: null,
  };
  const failedCore = {
    ...idleCore,
    last_refresh: { outcome: "network_error", message: "offline" },
  };
  assert.equal(
    page.describePull(idleCore, { ...filesPage, fetchQueued: true }).changesPending,
    true,
    "a selected fetch the page will still send is preparing the record",
  );
  assert.equal(
    page.describePull(idleCore, { ...filesPage, fetching: true }).changesPending,
    true,
    "and so is one on its way",
  );
  assert.equal(
    page.describePull(idleCore, filesPage).changesPending,
    false,
    "once the selected fetch was refused, nothing is preparing it",
  );
  assert.equal(
    page.describePull(failedCore, filesPage).filesUnavailable,
    "Changes are unavailable because the full pull request could not be loaded.",
  );
  assert.equal(
    page.describePull({ ...preview, core_preview: preparedCore }, filesPage).filesUnavailable,
    "Changes are still being prepared.",
    "an adopted description does not make the active comparison look unrequested",
  );
  const fullWins = page.describePull(
    { ...full, core_preview: preview.core_preview },
    { number: 7, tab: "", nowMs: Date.now() },
  );
  assert.equal(
    fullWins.corePreview,
    false,
    "an existing full record takes priority over any preview",
  );
  assert.notEqual(page.conversationKey(model), page.conversationKey(fullWins));
  const poll = [...timers].find(([, task]) => task.delay > 0 && task.delay <= 1000);
  assert.ok(poll);
  current = full;
  timers.delete(poll[0]);
  poll[1].callback();
  await settle();
  assert.equal(container.dataset.corePreview, "false");
  assert.equal(container.querySelector(".github-pull-section-loading"), null);
  assert.equal(container.querySelector(".spinner"), null, "full arrival clears progress");
  assert.equal(
    container.querySelector(".github-pull-status").getAttribute("aria-busy"),
    "false",
    "and the age stops breathing",
  );
  assert.doesNotMatch(body.textContent, /No checks or statuses reported/);
  const fullMarkdownRequests = markdownRequests;
  assert.equal(fullMarkdownRequests, 1, "full-record arrival enables the normal Markdown path");
  land("checks");
  assert.match(body.textContent, /No checks or statuses reported/);
  assert.equal(body.querySelector(".spinner"), null, "an empty complete Checks pane is settled");
  assert.equal(markdownRequests, fullMarkdownRequests, "Checks asks for no Markdown");
  land("");
  assert.equal(settlementSignal?.aborted, false);
  handle.dispose();
  assert.equal(settlementSignal.aborted, true, "the mounted wait shares the page disposal signal");
  current = absent;
  window.location.pathname = checksRoute;
  const coldChecks = new Element("main");
  const cancelled = page.mountPullPage(
    coldChecks,
    { number: 7, tab: "checks", reader: { initial: null, fetchAfterMs: 0 } },
    mb,
  );
  await settle();
  assert.ok(coldChecks.querySelector(".github-pull-loading"), "a cold Checks link shows blocks");
  assert.equal(coldChecks.querySelector(".spinner"), null);
  cancelled.dispose();
  await cancelled.ready;

  current = structuredClone(recorded.current.body);
  current.record.truncated = {
    ...current.record.truncated,
    check_runs: true,
    issue_comments: true,
  };
  current.record.status = null;
  current.record.unavailable = { status: "fetch_failed" };
  window.location.pathname = checksRoute;
  const directChecks = new Element("main");
  const checksView = page.mountPullPage(directChecks, { number: 7, tab: "checks" }, mb);
  await checksView.ready;
  const checksBody = directChecks.querySelector(".github-pull-body");
  const selectedChecks = directChecks
    .querySelectorAll(".tab-btn")
    .find((tab) => tab.getAttribute("aria-selected") === "true");
  assert.equal(selectedChecks?.textContent, "Checks");
  assert.equal(selectedChecks?.getAttribute("href"), checksRoute);
  assert.match(checksBody.textContent, /1 success · 1 pending/);
  assert.match(checksBody.textContent, /tests \(3\.13\)/);
  assert.match(checksBody.textContent, /Only some check runs are shown/);
  assert.match(checksBody.textContent, /Commit statuses could not be read/);
  assert.match(checksBody.textContent, /No conflicts with the base branch/);
  assert.doesNotMatch(checksBody.textContent, /Only some comments are shown|It no longer does/);
  const checkLinks = checksBody.querySelectorAll("a[href]");
  assert.equal(checkLinks.length, 2);
  for (const link of checkLinks) {
    assert.equal(link.getAttribute("target"), "_blank");
    assert.equal(link.getAttribute("rel"), "noopener noreferrer");
  }
  assert.equal(
    page.conversationKey(page.describePull(current, { number: 7, tab: "", nowMs: Date.now() })),
    page.conversationKey(
      page.describePull(
        {
          ...current,
          record: { ...current.record, check_runs: [], status: null, unavailable: {} },
        },
        { number: 7, tab: "", nowMs: Date.now() },
      ),
    ),
    "only check data changed, so Conversation can keep its rendered discussion",
  );
  const checkResults = { route: checksRoute, links: checkLinks.length, empty: true, pending: true };
  checksView.dispose();
  window.location.pathname = "/pull/7";
  for (const refreshing of [true, false]) {
    current = refreshing ? { ...preview, core_preview: preparedCore } : failedCore;
    const changes = new Element("main");
    // A reader's selection would ask for the failed record again, so the failure is seen
    // on a direct link, whose cold miss was already tried.
    const view = page.mountPullPage(
      changes,
      refreshing
        ? {
            number: 7,
            tab: "files",
            reader: { initial: { body: current, etag: null }, fetchAfterMs: 0 },
          }
        : { number: 7, tab: "files" },
      mb,
    );
    await view.ready;
    const body = changes.querySelector(".github-pull-body");
    // Changes has nothing cached and no known shape: the delayed spinner, its sentence only
    // for a screen reader.
    assert.equal(body.querySelector(".spinner") !== null, refreshing);
    if (refreshing) {
      const pending = body.querySelector(".github-pull-changes-pending");
      assert.ok(pending.classes.has("mb-delayed-loading"));
      assert.equal(pending.getAttribute("aria-label"), "Changes are still being prepared.");
      assert.doesNotMatch(body.textContent, /still being prepared/);
    } else {
      assert.match(
        body.textContent,
        /Changes are unavailable because the full pull request could not be loaded/,
      );
    }
    view.dispose();
  }

  // The real core mount retains A, cancels pending B, then commits C without resurrecting B.
  const context = { window: {}, document, console, Promise };
  vm.runInNewContext(
    fs.readFileSync(path.join(root, "src/metabrowser/static/pull-route.js"), "utf8"),
    context,
  );
  const routes = context.window.MetabrowserPullRoute;
  await retentionCapability(routes);
  let claim = 1,
    visible = "A",
    heldDispose = 0,
    bDispose = 0,
    bCancel = 0,
    activations = 0;
  const stages = new Set(),
    instances = [];
  const mount = routes.createViewMount({
    sdk: {
      ensureKindAssets: async () => {},
      getRegisteredView: () => ({
        render(host) {
          let ready;
          const promise = new Promise((resolve) => {
            ready = resolve;
          });
          const i = {
            host,
            ready: promise,
            resolve: () => {
              host.textContent = "useful";
              ready();
            },
            activate() {
              activations++;
            },
            cancelPending() {
              bCancel++;
            },
            dispose() {
              bDispose++;
              ready();
            },
          };
          instances.push(i);
          return i;
        },
      }),
    },
    isCurrent: (token) => token === claim,
    beginNavigation: () => true,
    endNavigation() {},
    stageNode(host) {
      stages.add(host);
      return () => stages.delete(host);
    },
    renderHtml() {},
    renderNode(host) {
      visible = host;
      heldDispose++;
    },
    showLoadFailure() {
      throw Error("unexpected failure");
    },
  });
  const b = await mount(1, "pull-request", { number: 7 });
  assert.equal(visible, "A");
  claim = 2;
  b.dispose();
  await b.ready;
  assert.equal(visible, "A");
  assert.equal(stages.size, 0);
  assert.equal(bDispose, 1);
  const c = await mount(2, "pull-request", { number: 8 });
  instances[0].resolve();
  await settle();
  assert.equal(visible, "A", "a canceled old ready callback cannot commit");
  instances[1].resolve();
  await c.ready;
  assert.equal(visible, instances[1].host);
  assert.equal(heldDispose, 1);
  assert.equal(stages.size, 0);
  c.cancelPending();
  assert.equal(visible.inert, true);
  assert.equal(bCancel, 1);
  c.dispose();
  assert.equal(activations, 1, "only committed C activates; canceled B stays dormant");
  const integratedHost = routes.createPullPageHost({
    claim: () => ++claim,
    isCurrent: (token) => token === claim,
    mount: (token, route) => mount(token, "pull-request", route),
    mountList: async () => null,
    pathname: () => "/pull/9",
    pushHref() {},
    replaceHref() {},
  });
  const integratedOpen = integratedHost.show({ number: 9, tab: "" });
  await settle();
  instances[2].resolve();
  await integratedOpen;
  assert.equal(
    activations,
    2,
    "route host must not activate a custom committed plugin a second time",
  );
  integratedHost.dispose();

  let hostClaim = 0,
    mounts = 0,
    releaseReady,
    rejectReady;
  const lands = [];
  const pageHost = routes.createPullPageHost({
    claim: () => ++hostClaim,
    isCurrent: (n) => n === hostClaim,
    mount: async () => {
      mounts++;
      return {
        ready: new Promise((resolve, reject) => {
          releaseReady = resolve;
          rejectReady = reject;
        }),
        land: (route) => lands.push(route),
        dispose() {},
      };
    },
    mountList: async () => null,
    pathname: () => "/pull/7",
    pushHref() {},
    replaceHref() {},
  });
  const opening = pageHost.show({ number: 7, tab: "" });
  await settle();
  const joined = pageHost.show({ number: 7, tab: "files", file: "latest.py" });
  assert.equal(mounts, 1);
  assert.equal(hostClaim, 1);
  assert.equal(pageHost.shown(), null);
  releaseReady();
  await opening;
  await joined;
  assert.deepEqual(lands, [{ number: 7, tab: "files", file: "latest.py" }]);
  pageHost.dispose();
  const rejected = pageHost.show({ number: 8, tab: "" });
  await settle();
  rejectReady(Error("readiness"));
  assert.equal((await rejected).status, "cancelled");
  assert.equal(pageHost.shown(), null);
  const retry = pageHost.show({ number: 8, tab: "" });
  await settle();
  assert.equal(mounts, 3);
  releaseReady();
  await retry;
  pageHost.dispose();

  // A direct cold URL also joins the bounded core wait, without a Fetch press.
  const waitCorePost = posts[0];
  current = { ...absent, last_refresh: null };
  posts.length = 0;
  const directRoot = new Element("main");
  const direct = page.mountPullPage(directRoot, { number: 7, tab: "" }, mb);
  let directReady = false;
  direct.ready.then(() => {
    directReady = true;
  });
  await settle();
  assert.equal(posts.length, 0, "the initial GET reads only the cache");
  assert.equal(directReady, false, "a cold GET does not replace the loading blocks");
  assert.ok(directRoot.querySelector(".github-pull-loading"));
  const directAsk = [...timers].find(([, task]) => task.delay === 0);
  assert.ok(directAsk);
  timers.delete(directAsk[0]);
  directAsk[1].callback();
  await settle();
  assert.deepEqual(posts, [waitCorePost]);
  assert.equal(directReady, false, "a held automatic POST keeps the loading blocks");
  current = preview;
  releasePost(preview);
  await direct.ready;
  assert.equal(directRoot.dataset.corePreview, "true");
  direct.dispose();

  // A later direct URL with a fresh record uses the cache without starting a POST.
  posts.length = 0;
  current = full;
  const warm = page.mountPullPage(new Element("main"), { number: 7, tab: "" }, mb);
  await warm.ready;
  assert.equal(posts.length, 0);
  assert.ok(![...timers.values()].some((task) => task.delay === 0), "warm open schedules no fetch");
  warm.dispose();

  const scrollPane = new Element("aside");
  scrollPane.scrollTop = 600;
  scrollPane.getBoundingClientRect = () => ({ top: 0 });
  window.history = { state: null, replaceState() {} };
  window.addEventListener = () => {};
  global.ResizeObserver = class {
    observe() {}
    disconnect() {}
  };
  const filesEnvelope = structuredClone(recorded.current.body);
  filesEnvelope.core_preview = null;
  current = filesEnvelope;
  window.location = { pathname: "/pull/7/files", hash: "" };
  const filesRoot = new Element("main");
  filesRoot.closest = () => scrollPane;
  let filesStopped = 0,
    filesDisposed = 0;
  const filesHandle = page.mountPullPage(
    filesRoot,
    {
      number: 7,
      tab: "files",
      reader: { initial: { body: filesEnvelope, etag: null }, fetchAfterMs: 0 },
    },
    {
      ...mb,
      getRegisteredView: () => ({
        render(host) {
          host.textContent = "retained comparison";
          return {
            cancelPending() {
              filesStopped++;
            },
            dispose() {
              filesDisposed++;
              host.textContent = "";
            },
          };
        },
      }),
    },
  );
  await settle();
  await filesHandle.ready;
  await filesHandle.whenFilesReady();
  assert.equal(scrollPane.scrollTop, 600, "staged page does not move the old owner's scroll");
  filesHandle.activate();
  assert.equal(scrollPane.scrollTop, 0, "committed page activates its own place");
  filesHandle.cancelPending();
  assert.equal(filesStopped, 1);
  assert.equal(filesDisposed, 0);
  assert.match(filesRoot.textContent, /retained comparison/);
  filesHandle.dispose();
  assert.equal(filesDisposed, 1);

  // The actual shell owns one retired visible page through any number of pending claims.
  const appSource = fs.readFileSync(path.join(root, "src/metabrowser/static/app.js"), "utf8");
  const functions = [
    "claimPreview",
    "finishRetainedPullPage",
    "renderPreviewHtml",
    "renderPreviewNode",
  ].map(
    (name) =>
      appSource.match(
        new RegExp(`^(?:async )?function ${name}\\([^)]*\\) \\{[\\s\\S]*?^\\}`, "m"),
      )?.[0],
  );
  assert.ok(functions.every(Boolean));
  const oldDOM = new Element("section");
  oldDOM.textContent = "old Files comparison";
  const pane = new Element("main");
  pane.append(oldDOM);
  let generation = 0,
    retired = 0,
    pendingDisposed = 0,
    oldCancelled = 0,
    active = null;
  const shell = {
    window: {},
    document: { getElementById: () => pane },
    pullPageHost: {
      release() {
        const handle = active;
        active = null;
        return handle?.release() ?? null;
      },
    },
    retainedPullPageDispose: null,
    cancelPendingFilePreviewStage() {},
    clearPreviewNavigationState() {},
    previewPane: {
      claim() {
        return ++generation;
      },
    },
    isPreviewClaimCurrent: (token) => token === generation,
    disposeActivePluginViews() {},
    animatePreviewContentArrival() {},
  };
  vm.runInNewContext(functions.join("\n"), shell);
  active = {
    release() {
      oldCancelled++;
      oldDOM.inert = true;
      return () => {
        retired++;
        oldDOM.remove();
      };
    },
  };
  shell.claimPreview("pull");
  assert.equal(oldCancelled, 1);
  assert.equal(retired, 0);
  assert.match(pane.textContent, /old Files/);
  active = {
    release() {
      pendingDisposed++;
      return null;
    },
  };
  shell.claimPreview("file");
  assert.equal(pendingDisposed, 1);
  assert.equal(retired, 0);
  assert.match(pane.textContent, /old Files/);
  const nextDOM = new Element("article");
  nextDOM.textContent = "new file";
  shell.renderPreviewNode(nextDOM, generation);
  assert.equal(retired, 1);
  assert.equal(shell.retainedPullPageDispose, null);
  assert.equal(pane.textContent, "new file");
  shell.renderPreviewNode(oldDOM, generation - 1);
  assert.equal(pane.textContent, "new file");

  return {
    description: "plain preview before full conversation",
    pendingParts: ["discussion", "checks"],
    checkResults,
    waitCorePost,
    previewMarkdownRequests: 0,
    fullMarkdownRequests,
    fullRecordWins: true,
    crossOwnerRetirement: true,
    stagedReplacement: "A retained through B cancellation until C commits",
  };
}
if (require.main === module) {
  run()
    .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
    .catch((error) => {
      process.stderr.write(`${error.stack}\n`);
      process.exitCode = 1;
    });
}
module.exports = { run };
