// Real pull-page lifecycle: route changes and response order during explicit repair.
const assert = require("node:assert/strict");
const optionalStacks = require("../fixtures/github-stacks-responses.json");
const { pathToFileURL } = require("node:url");
const { Element, recorded, root, settle, perf } = require("./github-pull-page-mount-behavior.js");

async function story({ delaySecondMount = false, counts = undefined } = {}) {
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
  // Each mount's File type group (Docs asks for `type:docs`), and each jump, by that group.
  const groups = [];
  // Each mount's layout, which Docs fixes at Unified and Changes leaves to the reader.
  const layouts = [];
  const jumps = [];
  globalThis.fetch = async (route, options = {}) => {
    if (route === "/api/plugin/github/stacks") {
      return {
        status: optionalStacks.missing.status,
        headers: { get: () => optionalStacks.missing.etag },
        json: async () => optionalStacks.missing.body,
      };
    }
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
      whenIdle: require("./sdk-idle-fixture.js").whenIdle,
      ensureKindAssets: async () => {},
      getRegisteredView: () => ({
        // The comparison's File type counts, when the story gives them (`askDocs`).
        ...(counts === undefined ? {} : { typeCounts: async () => counts }),
        render: async (host, context) => {
          mounted.push(context.comparison);
          const group = context.group ?? null;
          groups.push(group);
          layouts.push(context.layout ?? null);
          if (delaySecondMount && mounted.length === 2) {
            await new Promise((resolve) => {
              releaseMount = resolve;
            });
          }
          host.textContent = "Displayed changes";
          // A Docs diff holds the documents alone, as the diff plugin narrowed by group does.
          const holds = (path) => group === null || path.endsWith(".md");
          return {
            fileForPath: (path) => ({ kind: holds(path) ? "file" : "not_in_comparison", path }),
            scrollToFile(path) {
              jumps.push([group, path]);
              return { kind: holds(path) ? "jumped" : "not_in_comparison", path };
            },
            dispose() {
              disposed += 1;
            },
          };
        },
      }),
      ...require("./sdk-ref-fixture.js").refHelpers(document),
      ...require("./sdk-ref-fixture.js").agesFrom(document, () => ({
        label: "now",
        className: "age",
      })),
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
    docsLink: () =>
      [...container.descendants()].find((item) => item.tag === "a" && item.textContent === "Docs"),
    mounted,
    groups,
    layouts,
    jumps,
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
    // The navigation's Refresh runs the page's `refresh` (static/refresh-plan.js): the page
    // has none of its own (mb-ablv).
    async refresh() {
      handle.refresh();
      await settle();
    },
    async land(tab) {
      window.location.pathname = `/pull/7${tab === "" ? "" : `/${tab}`}`;
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
    if (outcome === "pending") {
      assert.deepEqual(run.mounted[1], original, "route return retains the repaired selection");
    } else {
      // The refresh found another head while the reader was away: Changes follows it, and
      // says which diff it showed before, with the way back.
      assert.equal(run.mounted[1].right, "e".repeat(40), "route return follows the newer head");
      assert.match(
        run.container.textContent,
        /Changes now show this pull request’s newer commits\. Show the earlier changes/,
      );
    }
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

  // A head that advances under Changes is followed, and the way back is the reader's choice:
  // the earlier diff then stays through a repair and offers the newer one, which a route
  // return shows again.
  const run = await story();
  const earlier = run.mounted[0];
  run.advanceHead();
  await run.tick();
  await run.handle.whenFilesReady();
  assert.equal(run.mounted.length, 2, "one poll follows the head once");
  assert.equal(run.mounted[1].right, "e".repeat(40), "Changes follows a newer head");
  await run.tick();
  assert.equal(run.mounted.length, 2, "a later poll keeps the followed diff");
  run.button("Show the earlier changes").events.get("click")();
  await settle();
  await run.handle.whenFilesReady();
  assert.equal(run.mounted.at(-1).right, earlier.right, "the way back shows the earlier diff");
  assert.equal(run.mounted.at(-1).route, earlier.route);
  await run.tick();
  assert.equal(run.mounted.length, 3, "the reader's earlier diff is not followed away");
  assert.ok(!run.container.textContent.includes("Show the earlier changes"));
  await run.refresh();
  run.button("Show the newer changes").events.get("click")();
  await settle();
  await run.handle.whenFilesReady();
  assert.equal(run.mounted.at(-1).right, "e".repeat(40));
  run.button("Show the earlier changes");
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

// Changes and Docs are two drawings of one comparison: a Refresh under way still draws the
// tab the reader moved to, and a file shown from Docs lands on Changes, not in Docs' list.
async function docs() {
  const run = await story();
  await run.refresh();
  await run.acknowledge(true);
  await run.land("docs");
  await run.handle.whenFilesReady();
  assert.deepEqual(run.groups, [null, "type:docs"], "Docs is drawn while the refresh runs");
  await run.land("files");
  await run.handle.whenFilesReady();
  assert.deepEqual(run.groups, [null, "type:docs", null], "and Changes again, whole");
  // Docs asks the diff for Unified, with no layout control (mb-0ze2); Changes asks for no
  // layout, so the reader's stored choice and its control stand.
  assert.deepEqual(run.layouts, [null, "unified", null], "Docs alone fixes the layout");
  await run.land("docs");
  await run.handle.whenFilesReady();
  assert.equal(
    run.handle.fileForPath("src/app.py").kind,
    "no_diff",
    "Docs does not say a file outside its group is outside the comparison",
  );
  run.handle.showFile("src/app.py");
  await settle();
  await run.handle.whenFilesReady();
  assert.equal(run.groups.at(-1), null, "showing a file moves to Changes");
  assert.deepEqual(run.jumps, [[null, "src/app.py"]], "and lands on it there, not in Docs");
  run.handle.dispose();
}

// Docs is offered only where the comparison changes a document: hidden once its counts
// say none changed, shown again while the reader is on it, and shown where one changed.
async function docsOffered() {
  const none = await story({ counts: { type_presets: [["docs", 0, 0]], truncated: false } });
  await settle();
  assert.equal(none.docsLink().hidden, true, "no document changed: Docs is hidden");
  await none.land("docs");
  await none.handle.whenFilesReady();
  assert.equal(none.docsLink().hidden, false, "an address on Docs keeps it, empty state and all");
  await none.land("files");
  assert.equal(none.docsLink().hidden, true, "and leaving it hides it again");
  none.handle.dispose();
  const some = await story({ counts: { type_presets: [["docs", 2, 0]], truncated: false } });
  await settle();
  assert.equal(some.docsLink().hidden, false, "a changed document: Docs is offered");
  some.handle.dispose();
  const cut = await story({ counts: { type_presets: [["docs", 0, 0]], truncated: true } });
  await settle();
  assert.equal(cut.docsLink().hidden, false, "a list cut short may hold one: Docs stays");
  cut.handle.dispose();
}

const selected = process.argv.includes("--case") ? process.argv.at(-1) : "all";
(async () => {
  if (selected === "all" || selected === "history") {
    await history();
  }
  if (selected === "all" || selected === "poll-order") {
    await pollOrder();
  }
  if (selected === "all" || selected === "docs") {
    await docs();
  }
  if (selected === "all" || selected === "docs-offered") {
    await docsOffered();
  }
  process.stdout.write(`${JSON.stringify({ case: selected, passed: true })}\n`);
})().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exitCode = 1;
});
