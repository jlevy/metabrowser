// Real pull-page lifecycle: route changes and response order during explicit repair.
const assert = require("node:assert/strict");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");

async function story({ delaySecondMount = false } = {}) {
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
  const page = await import(
    pathToFileURL(`${root}/src/metabrowser/builtin_plugins/github/pull-page.js`).href
  );
  const initial = { ...recorded.current, body: structuredClone(recorded.current.body) };
  let current = structuredClone(initial.body);
  let reply,
    releaseMount,
    disposed = 0,
    reads = 0;
  const mounted = [];
  globalThis.fetch = async (route, options = {}) => {
    if (options.method === "POST") {
      return new Promise((resolve) => {
        reply = resolve;
      });
    }
    if (String(route).includes("pull-markdown")) {
      return { status: 404, headers: { get: () => null }, json: async () => ({}) };
    }
    reads += 1;
    const snapshot = structuredClone(current);
    return { status: 200, headers: { get: () => null }, json: async () => snapshot };
  };
  const container = new Element("main");
  const handle = page.mountPullPage(
    container,
    { number: 7, tab: "files", reader: { initial, fetchAfterMs: 0 } },
    {
      perf,
      ensureAsset: async () => {},
      ensureKindAssets: async () => {},
      getRegisteredView: () => ({
        render: async (host, context) => {
          mounted.push(context.comparison);
          if (delaySecondMount && mounted.length === 2) {
            await new Promise((resolve) => {
              releaseMount = resolve;
            });
          }
          host.textContent = "Displayed changes";
          return {
            dispose() {
              disposed += 1;
            },
          };
        },
      }),
      formatAge: () => ({ label: "now", className: "age" }),
      formatTimestamp: () => "now",
      navigation: { href: () => "/view/" },
      sourceKind: () => "git_revision",
      icons: { toggle: "" },
    },
  );
  await settle();
  await handle.whenFilesReady();
  assert.equal(mounted.length, 1);
  const button = (label) => {
    const element = [...container.descendants()].find(
      (item) => item.tag === "button" && item.textContent === label,
    );
    assert.ok(element, label);
    return element;
  };
  return {
    handle,
    container,
    mounted,
    button,
    reads: () => reads,
    disposed: () => disposed,
    release: () => releaseMount(),
    current: () => current,
    advanceHead() {
      current = structuredClone(current);
      current.record.comparison.head = "e".repeat(40);
      current.record.pull.head.sha = "e".repeat(40);
      const route = new URL(current.comparison_route, "http://example");
      route.searchParams.set("right", current.record.comparison.head);
      current.comparison_route = route.pathname + route.search;
    },
    async refresh() {
      button("Refresh").events.get("click")();
      await settle();
    },
    async land(tab) {
      window.location.pathname = `/pull/7${tab === "files" ? "/files" : ""}`;
      handle.land({ tab });
      await settle();
    },
    async acknowledge(refreshing, failed = false) {
      current = {
        ...current,
        refreshing,
        last_refresh: refreshing
          ? current.last_refresh
          : {
              outcome: failed ? "network_error" : "succeeded",
              message: failed ? "offline" : null,
              reset_at: null,
              at: current.fetched_at,
            },
      };
      const snapshot = structuredClone(current);
      reply({
        status: 202,
        headers: { get: () => null },
        json: async () => ({ pull: snapshot }),
      });
      await settle();
    },
    finish() {
      current = {
        ...current,
        refreshing: false,
        last_refresh: {
          outcome: "succeeded",
          message: null,
          reset_at: null,
          at: current.fetched_at,
        },
      };
    },
    async tick() {
      const entry = [...timers].find(
        ([, timer]) => timer.delay === page.FAST_POLL_MS || timer.delay === page.SLOW_POLL_MS,
      );
      assert.ok(entry, "a metadata poll is scheduled");
      timers.delete(entry[0]);
      entry[1].callback();
      await settle();
    },
  };
}

async function history() {
  for (const outcome of ["completed", "pending", "failed"]) {
    const run = await story({ delaySecondMount: outcome === "completed" });
    const original = run.mounted[0];
    await run.refresh();
    await run.land("");
    assert.equal(run.disposed(), 1);
    if (outcome !== "pending") {
      run.advanceHead();
      await run.acknowledge(false, outcome === "failed");
    }
    await run.land("files");
    assert.equal(run.mounted.length, 2, "the arriving Files route mounts immediately");
    if (outcome === "completed") {
      let ready = false;
      const waiting = run.handle.whenFilesReady().then(() => {
        ready = true;
      });
      await settle();
      assert.equal(ready, false, "readiness belongs to the new route's mount");
      run.release();
      await waiting;
    } else {
      await run.handle.whenFilesReady();
    }
    assert.ok(run.container.textContent.includes("Displayed changes"));
    assert.deepEqual(run.mounted[1], original, "route return retains the repaired selection");
    if (outcome === "pending") {
      await run.acknowledge(true);
      await run.tick();
      assert.equal(run.mounted.length, 2, "an active repair keeps the route's current mount");
      run.finish();
      await run.tick();
      await run.handle.whenFilesReady();
      assert.equal(run.mounted.length, 3, "successful completion remounts once");
    }
    run.handle.dispose();
  }

  const run = await story();
  run.advanceHead();
  await run.tick();
  await run.refresh();
  run.button("Show the newer changes").events.get("click")();
  await settle();
  await run.handle.whenFilesReady();
  assert.equal(run.mounted.at(-1).right, "e".repeat(40));
  await run.land("");
  await run.acknowledge(false);
  await run.land("files");
  await run.handle.whenFilesReady();
  assert.equal(run.mounted.at(-1).right, "e".repeat(40), "an explicit newer choice owns return");
  run.handle.dispose();
}

async function pollOrder() {
  const run = await story();
  await run.refresh();
  const reads = run.reads();
  await run.tick();
  assert.equal(run.reads(), reads, "polls cannot overtake an unacknowledged explicit POST");
  assert.equal(run.mounted.length, 1);
  await run.acknowledge(true);
  assert.equal(run.mounted.length, 1, "acknowledgement is not repair completion");
  await run.tick();
  assert.equal(run.mounted.length, 1);
  run.finish();
  await run.tick();
  await run.handle.whenFilesReady();
  assert.equal(run.mounted.length, 2, "actual completion performs the one repair remount");
  await run.tick();
  assert.equal(run.mounted.length, 2, "later polling cannot repeat the repair remount");
  run.handle.dispose();
}

const selected = process.argv.includes("--case") ? process.argv.at(-1) : "all";
(async () => {
  if (selected === "all" || selected === "history") {
    await history();
  }
  if (selected === "all" || selected === "poll-order") {
    await pollOrder();
  }
  process.stdout.write(`${JSON.stringify({ case: selected, passed: true })}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exitCode = 1;
});
