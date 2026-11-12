// A pending file belongs to its Files visit, and survives replacement within that visit.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");
function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
function setup() {
  const timers = new Map();
  globalThis.document = {
    visibilityState: "visible",
    addEventListener() {},
    createElement: (tag) => new Element(tag),
    importNode: () => new Element("svg"),
  };
  globalThis.window = {
    location: { pathname: "/pull/7/files" },
    setTimeout(callback, delay) {
      const id = Symbol();
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
  };
  globalThis.DOMParser = class {
    parseFromString() {
      return { body: { firstElementChild: null } };
    }
  };
  return timers;
}
const response = (body) => ({ status: 200, headers: { get: () => null }, json: async () => body });
async function run() {
  const { FAST_POLL_MS, mountPullPage } = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const mount = (
    initial,
    assets,
    jumps,
    container,
    renderReady = Promise.resolve(),
    tab = "files",
  ) =>
    mountPullPage(
      container,
      { number: 7, tab, reader: { initial, fetchAfterMs: 0 } },
      {
        perf,
        ensureAsset: async () => {},
        ensureKindAssets: () => assets,
        getRegisteredView: () => ({
          async render() {
            await renderReady;
            return {
              scrollToFile(file) {
                jumps.push(file);
                return { kind: "jumped", path: file };
              },
              dispose() {},
            };
          },
        }),
        ...require("./sdk-ref-fixture.js").refHelpers(document),
        formatAge: () => ({ label: "now", className: "age" }),
        formatTimestamp: () => "now",
        navigation: { href: () => "/view/" },
        sourceKind: () => "git_revision",
        icons: { toggle: "" },
      },
    );
  setup();
  globalThis.fetch = async () => ({ status: 304, headers: { get: () => null } });
  const assets = deferred();
  const abandoned = [];
  const loading = new Element("main");
  const rendering = deferred();
  const page = mount(recorded.current, assets.promise, abandoned, loading, rendering.promise);
  await settle();
  const pending = () => loading.querySelector(".mb-delayed-loading");
  assert.equal(pending()?.getAttribute("aria-label"), "Loading changes");
  assert.ok(pending().querySelector(".spinner"));
  assert.equal(page.showFile("src/app.txt").kind, "no_diff");
  window.location.pathname = "/pull/7";
  page.setTab("");
  assert.equal(pending(), null, "leaving Changes retires its pending spinner");
  assets.resolve();
  await settle();
  window.location.pathname = "/pull/7/files";
  page.setTab("files");
  await settle();
  assert.ok(pending(), "the spinner covers the renderer’s initial request as well as assets");
  rendering.resolve();
  await page.whenFilesReady();
  assert.equal(pending(), null, "the diff owns progress after its initial render");
  assert.deepEqual(abandoned, [], "a fileless visit must not consume the abandoned file");
  page.dispose();

  const timers = setup();
  const acquisition = deferred();
  const unavailable = structuredClone(recorded.current);
  unavailable.body.record.comparison = null;
  unavailable.body.comparison_route = null;
  unavailable.body.record.unavailable.comparison = "no_store";
  unavailable.body.refreshing = true;
  let current = { ...unavailable.body, refreshing: false };
  let asked;
  globalThis.fetch = (route, options) => {
    if (options.method === "POST") {
      assert.equal(route, "/api/plugin/github/pull-refresh");
      asked = JSON.parse(options.body);
      return acquisition.promise;
    }
    return Promise.resolve(response(current));
  };
  const retained = [];
  const changes = new Element("main");
  window.location.pathname = "/pull/7/files/docs/new.md";
  const waiting = mount(unavailable, Promise.resolve(), retained, changes);
  const changesBody = () => changes.querySelector(".github-pull-body");
  waiting.land({ tab: "files", file: "docs/new.md" });
  assert.ok(
    changesBody().querySelector(".spinner"),
    "Changes shows progress while metadata settles",
  );
  assert.equal(asked, undefined, "comparison waits for the existing metadata request");
  await settle();
  assert.deepEqual(asked, { number: 7, retry: true, comparison: true });
  const assertAcquiring = () => {
    // The sentence is the delayed spinner's name for a screen reader, not painted text.
    assert.match(
      changesBody().querySelector(".github-pull-changes-pending")?.getAttribute("aria-label") ?? "",
      /Fetching changes/,
    );
    assert.ok(changesBody().querySelector(".spinner"));
    assert.equal(changesBody().querySelector(".github-pull-retry-changes"), null);
  };
  assertAcquiring();
  current = unavailable.body;
  acquisition.resolve({ ...response({ pull: current }), status: 202 });
  await settle();
  assertAcquiring();
  async function poll() {
    const [id, timer] = [...timers].find(([, timer]) => timer.delay === FAST_POLL_MS);
    timers.delete(id);
    timer.callback();
    await settle();
  }
  await poll();
  assertAcquiring();
  current = recorded.current.body;
  await poll();
  await waiting.whenFilesReady();
  assert.equal(changesBody().querySelector(".spinner"), null);
  assert.deepEqual(retained, ["docs/new.md"], "acquiring changes retains the pending file");
  waiting.dispose();

  setup();
  const newer = deferred();
  globalThis.fetch = () => newer.promise;
  const oldAssets = deferred();
  const replacements = [];
  const container = new Element("main");
  const sameVisit = mountPullPage(
    container,
    { number: 7, tab: "files", reader: { initial: recorded.current, fetchAfterMs: 0 } },
    {
      perf,
      ensureAsset: async () => {},
      ensureKindAssets: () => oldAssets.promise,
      getRegisteredView: () => ({
        render: async () => ({
          scrollToFile(file) {
            replacements.push(file);
            return { kind: "jumped", path: file };
          },
          dispose() {},
        }),
      }),
      ...require("./sdk-ref-fixture.js").refHelpers(document),
      formatAge: () => ({ label: "now", className: "age" }),
      formatTimestamp: () => "now",
      navigation: { href: () => "/view/" },
      sourceKind: () => "git_revision",
      icons: { toggle: "" },
    },
  );
  await settle();
  sameVisit.showFile("docs/new.md");
  const updated = structuredClone(recorded.current.body);
  updated.record.comparison.head = "c".repeat(40);
  updated.record.pull.head.sha = "c".repeat(40);
  updated.fetched_at = "2026-09-17T12:00:01Z";
  newer.resolve(response(updated));
  await settle();
  const offer = [...container.descendants()].find(
    (element) => element.textContent === "Show the newer changes",
  );
  assert.ok(offer);
  offer.events.get("click")();
  oldAssets.resolve();
  await settle();
  await sameVisit.whenFilesReady();
  assert.deepEqual(
    replacements,
    ["docs/new.md"],
    "same-Files replacement retains the newest pending selection",
  );
  sameVisit.dispose();

  // A walk of the Pulls tab's files jumps the page key by key while the address still names
  // Conversation. Once it settles, the route moves the address and confirms the tab with
  // setTab, which must not jump the diff a second time.
  setup();
  window.location.pathname = "/pull/7";
  globalThis.fetch = async () => response(recorded.current.body);
  const walked = [];
  const walk = mount(
    recorded.current,
    Promise.resolve(),
    walked,
    new Element("main"),
    undefined,
    "",
  );
  await settle();
  walk.showFile("src/app.txt");
  await walk.whenFilesReady();
  await settle();
  assert.deepEqual(walked, ["src/app.txt"], "the walk's key jumped the diff once");
  window.location.pathname = "/pull/7/files/src/app.txt";
  walk.setTab("files");
  await settle();
  assert.deepEqual(walked, ["src/app.txt"], "confirming a settled walk's tab does not jump again");
  walk.dispose();

  // The same walk over a pull request without a store: Changes shows progress while the
  // walk will settle, not an action the settled address makes needless, and the request
  // waits for the address. A walk cancelled before it settles leaves the page to the reader.
  const checkout = JSON.parse(
    fs.readFileSync(
      path.join(root, "tests/fixtures/github-checkout-comparison-responses.json"),
      "utf8",
    ),
  );
  const unstored = () => {
    setup();
    window.location.pathname = "/pull/10";
    const posts = [];
    globalThis.fetch = async (route, options = {}) => {
      // A commit timeline read is not the refresh this counts.
      if (options.method === "POST" && !route.includes("pull-timeline")) {
        posts.push(JSON.parse(options.body));
      }
      const answer = options.method === "POST" ? checkout.started : checkout.before;
      return { status: answer.status, headers: { get: () => null }, json: async () => answer.body };
    };
    const container = new Element("main");
    const handle = mountPullPage(
      container,
      { number: 10, tab: "", reader: { initial: checkout.before, fetchAfterMs: 0 } },
      {
        perf,
        ensureAsset: async () => {},
        ensureKindAssets: async () => {},
        getRegisteredView: () => {
          throw new Error("no comparison exists before acquisition");
        },
        ...require("./sdk-ref-fixture.js").refHelpers(document),
        formatAge: () => ({ label: "now", className: "age" }),
        formatTimestamp: () => "now",
        navigation: { href: () => "/view/" },
        sourceKind: () => "filesystem",
        icons: { toggle: "" },
      },
    );
    const body = () => container.querySelector(".github-pull-body");
    const paint = () => ({
      text: body().textContent,
      pending: body().querySelector(".github-pull-changes-pending")?.getAttribute("aria-label"),
      spinner: body().querySelector(".spinner") !== null,
      fetch: body().querySelector(".github-pull-fetch-changes") !== null,
      posts: posts.length,
    });
    return { handle, paint };
  };
  for (const end of ["settled", "cancelled", "unclaimed"]) {
    const { handle, paint } = unstored();
    await handle.ready;
    await settle();
    handle.showFile("src/app.txt", { settling: true });
    // A walk's later keys repeat the claim, which changes nothing.
    handle.showFile("src/app.txt", { settling: true });
    await settle();
    const during = paint();
    assert.match(during.pending ?? "", /Fetching changes/, "the walk will settle on Changes");
    assert.equal(during.spinner, true);
    assert.equal(during.fetch, false, "no Fetch changes the settled address makes needless");
    assert.equal(during.posts, 0, "the request waits for the address");
    if (end !== "settled") {
      if (end === "cancelled") {
        handle.walkCancelled();
      } else {
        // A key onto a file no address can name claims no settling, which ends the claim.
        handle.showFile("src/app.txt");
      }
      await settle();
      const left = paint();
      assert.match(left.text, /Changes have not been fetched/);
      assert.equal(left.spinner, false, "a cancelled walk leaves nothing on its way");
      assert.equal(left.fetch, true, "and the reader can still fetch");
      assert.equal(left.posts, 0);
    } else {
      window.location.pathname = "/pull/10/files/src/app.txt";
      handle.setTab("files");
      await settle();
      assert.equal(paint().posts, 1, "the settled walk's address asks once");
      assert.equal(paint().spinner, true);
    }
    handle.dispose();
  }
  return {
    abandonedJump: false,
    unavailableRetainsSelection: true,
    replacementRetainsSelection: true,
    settledWalkJumpsOnce: true,
    unsettledWalkShowsProgress: true,
  };
}
run()
  .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });
