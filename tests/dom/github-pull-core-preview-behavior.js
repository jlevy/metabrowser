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
  async function check({ heldMs, waitCore, cancel = false, hide = false }) {
    let now = 0,
      visible = true,
      current,
      release;
    const tasks = new Map(),
      gets = [];
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
    current = waitCore ? absent : { ...full, state: "stale" };
    const controller = page.createPullController(
      {
        request: async (method) => {
          if (method === "POST") {
            return new Promise((resolve) => {
              release = resolve;
            });
          }
          gets.push(now);
          return { status: 200, etag: null, body: current };
        },
        schedule(callback, delay) {
          const token = Symbol();
          tasks.set(token, { callback, at: now + delay });
          return token;
        },
        cancel: (token) => tasks.delete(token),
        now: () => now,
        isVisible: () => visible,
        render() {},
        reload() {},
        navigate() {},
      },
      { number: 7, tab: "" },
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
    await controller.start();
    const requested = controller.requestRefresh();
    await settle();
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
    current = waitCore ? preview : { ...full, refreshing: true };
    release({ status: 202, etag: null, body: { pull: current } });
    await requested;
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
    if (waitCore) {
      await advance(2000);
      current = full;
      await advance(3000);
      assert.deepEqual(
        gets,
        [0, 2000, 3000],
        "full publication is observed at the ordinary next one-second tick",
      );
    }
    controller.dispose();
    assert.equal(tasks.size, 0);
  }
  await check({ heldMs: 1700, waitCore: true });
  await check({ heldMs: 1400, waitCore: true });
  await check({ heldMs: 1700, waitCore: false });
  await check({ heldMs: 1700, waitCore: true, cancel: true });
  await check({ heldMs: 1700, waitCore: true, hide: true });
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
  current = preview;
  releasePost(preview);
  await settle();
  await handle.ready;
  assert.equal(container.dataset.corePreview, "true");
  assert.equal(container.querySelector(".github-pull-plain").textContent, full.record.pull.body);
  assert.match(container.textContent, /Comments and reviews are still loading/);
  assert.match(container.textContent, /Checks and statuses are still loading/);
  assert.doesNotMatch(container.textContent, /No checks or statuses reported/);
  assert.equal(markdownRequests, 0, "preview stays plain and never asks for full-record Markdown");
  const model = page.describePull(preview, { number: 7, tab: "", nowMs: Date.now() });
  assert.equal(model.browse, null);
  assert.equal(model.canFetchComparison, false);
  assert.equal(model.comparison, null);
  assert.equal(model.contentReady, true);
  assert.equal(model.corePreview, true);
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
  assert.doesNotMatch(container.textContent, /still loading/);
  assert.match(container.textContent, /No checks or statuses reported/);
  assert.equal(markdownRequests, 1, "full-record arrival enables the normal Markdown path");
  handle.dispose();
  const cancelled = page.mountPullPage(
    new Element("main"),
    { number: 7, tab: "", reader: { initial: null, fetchAfterMs: 0 } },
    mb,
  );
  cancelled.dispose();
  await cancelled.ready;

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

  // A direct URL remains explicit, and its Fetch joins the same bounded core wait.
  const waitCorePost = posts[0];
  current = absent;
  posts.length = 0;
  const direct = page.mountPullPage(new Element("main"), { number: 7, tab: "" }, mb);
  await settle();
  await direct.ready;
  assert.equal(posts.length, 0);
  direct.dispose();
  const directRequests = [];
  const directController = page.createPullController(
    {
      request: async (method, _route, options) => {
        if (method === "POST") {
          directRequests.push(options.body);
        }
        return {
          status: method === "POST" ? 202 : 200,
          etag: null,
          body: method === "POST" ? { pull: preview } : absent,
        };
      },
      schedule: () => 0,
      cancel() {},
      now: () => Date.now(),
      isVisible: () => true,
      render() {},
      reload() {},
      navigate() {},
      renderMarkdown() {},
    },
    { number: 7, tab: "" },
  );
  await directController.start();
  await directController.requestRefresh();
  assert.deepEqual(directRequests, [{ number: 7, retry: true, wait_core: true }]);
  directController.dispose();

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
    waitCorePost,
    previewMarkdownRequests: 0,
    fullMarkdownRequests: markdownRequests,
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
