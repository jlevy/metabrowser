// The production pull controller consumes replies recorded by the CLI checkout golden.
// Conversation reads metadata; opening Changes attaches a comparison automatically, once,
// and the page shows progress only while that attempt is on its way or will be sent.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const root = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(
    path.join(root, "tests/fixtures/github-checkout-comparison-responses.json"),
    "utf8",
  ),
);
const NOW = Date.parse("2026-09-17T12:00:30Z");
const comparisonPost = `POST /api/plugin/github/pull-refresh ${JSON.stringify({
  number: 10,
  retry: true,
  comparison: true,
})}`;

// A cold visit's answers are the recorded record with what a cold miss lacks removed: the
// server has only the description a catalog prepared.
const full = recorded.before.body;
const coldCore = {
  ...full,
  state: "absent",
  reason: "not_cached",
  fetched_at: null,
  record_revision: null,
  last_refresh: null,
  comparison_route: null,
  record: null,
  core_preview: {
    source: full.source,
    number: full.number,
    reader: full.record.reader,
    observed_at: full.record.fetched_at,
    revision: "a".repeat(64),
    pull: full.record.pull,
    comparison_state: "no_store",
  },
};
const answer = (body, status = 200) => ({ status, etag: null, body });
// The server's answer past its bound on jobs (sidekick.py's `_TOO_MANY`): nothing starts.
const tooMany = (pull) =>
  answer(
    {
      refresh: "too_many",
      pull,
      error: "too many pull requests are being fetched; try again when one has finished",
      code: "too_many",
    },
    429,
  );
// A recorded outcome after the record was written.
const failedAfter = (outcome, message, resetAt = null) => ({
  ...full,
  last_refresh: { outcome, message, reset_at: resetAt, at: "2026-09-17T12:00:20Z" },
});

function harness(page, { tab, get, post, owns = () => true }) {
  const state = { get, post, visible: true, now: NOW, model: null };
  const requests = [];
  const timers = new Map();
  const controller = page.createPullController(
    {
      async request(method, route, options) {
        requests.push(
          method === "POST" ? `POST ${route} ${JSON.stringify(options.body)}` : `GET ${route}`,
        );
        const next = method === "POST" ? state.post(options.body) : state.get();
        return typeof next === "function" ? next() : next;
      },
      schedule(callback, delay) {
        const id = Symbol();
        timers.set(id, { callback, delay });
        return id;
      },
      cancel(id) {
        timers.delete(id);
      },
      now: () => state.now,
      isVisible: () => state.visible,
      ownsChanges: () => owns(),
      render(next) {
        state.model = next;
      },
      renderMarkdown() {},
      reload() {
        throw new Error("a checkout comparison never reloads its source");
      },
      navigate() {
        throw new Error("a checkout comparison never switches its source");
      },
    },
    { number: 10, tab },
  );
  return {
    controller,
    state,
    requests,
    get model() {
      return state.model;
    },
    posts: () => requests.filter((request) => request.startsWith("POST ")),
    /** Run the asks scheduled with *delay*, as the page's timers would. */
    async fire(delay) {
      for (const [id, timer] of [...timers]) {
        if (timer.delay === delay) {
          timers.delete(id);
          timer.callback();
        }
      }
      await settle();
    },
  };
}

async function settle() {
  for (let turn = 0; turn < 4; turn += 1) {
    await new Promise(setImmediate);
  }
}

async function run() {
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const story = [];
  function snapshot(run, step) {
    const model = run.model;
    story.push({
      step,
      requests: run.requests.splice(0),
      changesPending: model.changesPending,
      canRetryChanges: model.canRetryComparison,
      canFetchChanges: model.canFetchComparison,
      canRefresh: model.canRefresh,
      // What Changes says in place of a diff, where it shows one.
      files: model.tab === "files" && model.comparison === null ? model.filesUnavailable : null,
      message: model.message,
      failure: model.failure,
      refreshing: model.refreshing,
      comparison: model.comparison,
    });
  }

  // Conversation first, then Changes: one automatic attempt, and the store route after it.
  {
    const run = harness(page, {
      tab: "",
      get: () => recorded.before,
      post: () => recorded.started,
    });
    await run.controller.start();
    assert.deepEqual(run.posts(), []);
    assert.equal(run.model.canRetryComparison, false);
    snapshot(run, "Conversation reads without acquiring a comparison");
    run.state.visible = false;
    run.controller.setTab("files");
    assert.equal(run.requests.length, 0, "a hidden Changes tab acquires nothing");
    assert.equal(run.model.changesPending, true, "it is queued for when the page is seen");
    run.state.visible = true;
    run.controller.onVisibilityChange();
    await settle();
    assert.deepEqual(run.posts(), [comparisonPost]);
    assert.equal(run.model.changesPending, true);
    assert.equal(run.model.canRetryComparison, false);
    snapshot(run, "visible Changes starts the comparison automatically");
    run.controller.setTab("");
    run.controller.setTab("files");
    await run.controller.requestComparison();
    assert.equal(run.requests.length, 0, "reentering Changes during a job cannot start another");
    run.state.get = () => recorded.ready;
    await run.controller.poll();
    assert.equal(run.model.canRetryComparison, false);
    assert.equal(run.model.browse, null, "an unpinned folder offers no Browse code");
    assert.equal(run.model.headOffer, null, "nor a switch to the head");
    assert.equal(run.model.comparison.route, recorded.ready.body.comparison_route);
    snapshot(run, "the finished comparison stays beside the folder");
    run.controller.dispose();
  }

  // A direct visit to Changes on a cold server: the selected fetch first, then exactly one
  // automatic comparison once the record names what is missing.
  {
    const run = harness(page, {
      tab: "files",
      get: () => answer(coldCore),
      post: (body) =>
        body.wait_core
          ? answer({ pull: { ...coldCore, refreshing: true } }, 202)
          : recorded.started,
    });
    await run.controller.start();
    await run.fire(0);
    assert.deepEqual(run.posts(), [
      `POST /api/plugin/github/pull-refresh ${JSON.stringify({ number: 10, retry: true, wait_core: true })}`,
    ]);
    assert.equal(run.model.changesPending, true);
    snapshot(run, "a cold direct Changes visit asks for the pull request first");
    run.state.get = () => recorded.before;
    await run.controller.poll();
    await settle();
    assert.deepEqual(run.posts(), [comparisonPost]);
    assert.equal(run.model.changesPending, true);
    snapshot(run, "the record without a store starts one comparison");
    run.state.get = () => recorded.ready;
    await run.controller.poll();
    await settle();
    assert.equal(run.posts().length, 0, "the comparison is asked for once");
    run.requests.length = 0;
    run.controller.dispose();
  }

  // The same visit when the server refuses the selected fetch: nothing is on its way, so
  // nothing spins, and the header's Refresh is the way on.
  {
    const run = harness(page, {
      tab: "files",
      get: () => answer(coldCore),
      post: () => tooMany(coldCore),
    });
    await run.controller.start();
    await run.fire(0);
    assert.equal(run.model.changesPending, false);
    assert.equal(run.model.canRefresh, true);
    snapshot(run, "a refused cold fetch stops showing progress");
    await run.controller.poll();
    await run.fire(0);
    assert.equal(run.model.changesPending, false, "a later read does not restart progress");
    assert.equal(run.posts().length, 0, "nor sends the selected fetch again");
    snapshot(run, "a later read neither spins nor asks again");
    run.controller.dispose();
  }

  // Changes painted while the address still names Conversation, as an unsettled walk of
  // the Pulls tab's files leaves it: nothing is sent by itself, and the reader can fetch.
  {
    const run = harness(page, {
      tab: "",
      owns: () => false,
      get: () => recorded.before,
      post: () => recorded.started,
    });
    await run.controller.start();
    run.controller.setTab("files");
    await run.controller.poll();
    assert.equal(run.posts().length, 0);
    assert.equal(run.model.changesPending, false);
    assert.equal(run.model.canFetchComparison, true);
    assert.equal(run.model.canRetryComparison, false, "nothing failed, so nothing is retried");
    snapshot(run, "Changes without its address waits for the reader");
    await run.controller.requestComparison();
    assert.equal(run.posts().length, 1);
    assert.equal(run.model.changesPending, true);
    snapshot(run, "Fetch changes asks for the comparison");
    run.controller.dispose();
  }

  // A read that fails before any attempt: the attempt waits for the next good read, and
  // until then Changes neither spins nor offers a retry.
  {
    const run = harness(page, {
      tab: "",
      get: () => recorded.before,
      post: () => recorded.started,
    });
    await run.controller.start();
    run.requests.length = 0;
    run.state.get = () => answer(null, 500);
    await run.controller.poll();
    run.controller.setTab("files");
    assert.equal(run.posts().length, 0);
    assert.equal(run.model.changesPending, false);
    assert.equal(run.model.canRetryComparison, false);
    snapshot(run, "a failed read before any attempt waits without a retry");
    run.state.get = () => recorded.before;
    await run.controller.poll();
    await settle();
    assert.equal(run.posts().length, 1);
    assert.equal(run.model.changesPending, true);
    snapshot(run, "the next good read starts the automatic attempt");
    run.controller.dispose();
  }

  // A refused automatic comparison keeps its reason until the reader retries.
  {
    const run = harness(page, {
      tab: "files",
      get: () => recorded.before,
      post: () => tooMany(full),
    });
    await run.controller.start();
    await settle();
    assert.equal(run.posts().length, 1);
    assert.equal(run.model.canRetryComparison, true);
    snapshot(run, "a refused automatic comparison offers Retry changes");
    await run.controller.poll();
    await settle();
    assert.equal(run.posts().length, 0, "polling does not retry a refused acquisition");
    assert.match(run.model.message, /too many pull requests/, "the reason outlasts the read");
    snapshot(run, "the refusal's reason stays after the next read");
    run.state.post = () => recorded.started;
    await run.controller.requestComparison();
    assert.equal(run.posts().length, 1);
    assert.equal(run.model.message, null);
    snapshot(run, "Retry changes asks again and clears the reason");
    run.controller.dispose();
  }

  // A recorded outcome that another attempt would only repeat holds it for the reader.
  {
    const lenderMissing = failedAfter(
      "lender_missing",
      "the checkout cannot supply this comparison",
    );
    const run = harness(page, {
      tab: "files",
      get: () => answer(lenderMissing),
      post: () => recorded.started,
    });
    await run.controller.start();
    await settle();
    assert.equal(run.posts().length, 0, "a new visit does not repeat a refused borrowing");
    assert.equal(run.model.changesPending, false);
    assert.equal(run.model.canRetryComparison, true);
    snapshot(run, "a recorded borrowing refusal holds the automatic attempt");
    await run.controller.requestComparison();
    assert.equal(run.posts().length, 1, "Retry changes is the reader's override");
    run.requests.length = 0;
    run.controller.dispose();
  }
  {
    const limited = failedAfter("rate_limited", null, "2026-09-17T12:05:00Z");
    const run = harness(page, {
      tab: "files",
      get: () => answer(limited),
      post: () => recorded.started,
    });
    await run.controller.start();
    await settle();
    assert.equal(run.posts().length, 0, "no attempt is due before GitHub's limit lifts");
    assert.equal(run.model.canRetryComparison, true);
    snapshot(run, "a rate limit holds the automatic attempt until it lifts");
    run.state.now = Date.parse("2026-09-17T12:05:01Z");
    await run.controller.poll();
    await settle();
    assert.equal(run.posts().length, 1);
    assert.equal(run.model.changesPending, true);
    snapshot(run, "the automatic attempt starts once the limit lifts");
    run.controller.dispose();
  }
  process.stdout.write(`${JSON.stringify(story, null, 2)}\n`);
}
run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
