// Run the production page controller through idle and foreground Changes handoff.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const fixture = require("../fixtures/github-checkout-comparison-responses.json");

async function main() {
  const { createPullController, FAST_POLL_MS, SLOW_POLL_MS } = await import(
    pathToFileURL(
      path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/github/pull-page.js"),
    ).href
  );
  // A server with a store answers a record written without one as stale, whatever its age:
  // the only place idle preparation runs. The same record on a checkout with no store is
  // current, and its page asks nothing.
  const record = { ...fixture.before.body, state: "stale" };
  const storeless = fixture.before.body;
  const idleAsk = { number: 10, prepare_comparison: record.record_revision };
  const foregroundAsk = { number: 10, comparison: true, retry: true };
  const pending = { ...record, refreshing: true, preparing_comparison: true };
  const tick = () => new Promise((resolve) => setImmediate(resolve));

  function page({ visible = true, latest = record } = {}) {
    const posts = [];
    const scheduled = new Set();
    const delays = [];
    const state = { visible, conversation: true, latest };
    let model;
    const controller = createPullController(
      {
        request(method, _route, options) {
          if (method === "GET") {
            return Promise.resolve({ status: 200, etag: null, body: state.latest });
          }
          return new Promise((resolve) => posts.push({ ask: options.body, resolve }));
        },
        schedule(_callback, delay) {
          delays.push(delay);
          return 0;
        },
        cancel() {},
        scheduleComparison(callback) {
          scheduled.add(callback);
          return () => scheduled.delete(callback);
        },
        now: () => Date.parse(record.fetched_at),
        isVisible: () => state.visible,
        ownsConversation: () => state.conversation,
        ownsChanges: () => !state.conversation,
        render(next) {
          model = next;
        },
        renderMarkdown() {},
        reload() {},
        navigate() {},
      },
      { number: 10, tab: "" },
    );
    return {
      posts,
      delays,
      state,
      controller,
      model: () => model,
      idle() {
        for (const callback of [...scheduled]) {
          scheduled.delete(callback);
          callback();
        }
      },
      changes() {
        state.conversation = false;
        controller.setTab("files");
      },
    };
  }

  const noStore = page({ latest: storeless });
  await noStore.controller.start();
  noStore.idle();
  assert.deepEqual(noStore.posts, [], "a checkout with no store is never asked for idle work");
  noStore.controller.dispose();

  const quick = page();
  await quick.controller.start();
  assert.deepEqual(quick.posts, []);
  quick.changes();
  quick.idle();
  assert.deepEqual(
    quick.posts.map(({ ask }) => ask),
    [foregroundAsk],
  );
  quick.controller.dispose();

  const stopped = page();
  await stopped.controller.start();
  stopped.controller.dispose();
  stopped.idle();
  assert.deepEqual(stopped.posts, []);

  const hidden = page({ visible: false });
  await hidden.controller.start();
  hidden.idle();
  assert.deepEqual(hidden.posts, []);
  hidden.state.visible = true;
  hidden.controller.onVisibilityChange();
  await tick();
  hidden.idle();
  assert.deepEqual(
    hidden.posts.map(({ ask }) => ask),
    [idleAsk],
  );
  hidden.posts[0].resolve({ status: 202, etag: null, body: { pull: pending } });
  await tick();
  assert.equal(hidden.model().refreshing, false, "idle Git work is quiet in Conversation");
  hidden.state.latest = pending;
  await hidden.controller.poll();
  const conversationPoll = hidden.delays.at(-1);
  assert.equal(conversationPoll, SLOW_POLL_MS, "Conversation polls slowly during idle work");
  hidden.changes();
  assert.deepEqual(
    hidden.posts.map(({ ask }) => ask),
    [idleAsk, foregroundAsk],
  );
  hidden.posts[1].resolve({ status: 202, etag: null, body: { pull: pending } });
  await tick();
  const changesPoll = hidden.delays.at(-1);
  assert.equal(changesPoll, FAST_POLL_MS, "Changes polls the promoted job at the fast rate");
  hidden.controller.dispose();

  const race = page();
  await race.controller.start();
  race.idle();
  race.changes();
  assert.deepEqual(
    race.posts.map(({ ask }) => ask),
    [idleAsk, foregroundAsk],
  );
  race.posts[1].resolve({ status: 202, etag: null, body: { pull: fixture.ready.body } });
  await tick();
  race.posts[0].resolve({ status: 202, etag: null, body: { pull: pending } });
  await tick();
  assert.ok(race.model().comparison, "the late idle acknowledgement cannot undo Changes");
  assert.equal(race.model().changesPending, false);
  race.controller.dispose();

  const refused = page();
  await refused.controller.start();
  refused.idle();
  refused.posts[0].resolve({ status: 429, etag: null, body: { error: "busy" } });
  await tick();
  await refused.controller.poll();
  refused.idle();
  assert.deepEqual(
    refused.posts.map(({ ask }) => ask),
    [idleAsk],
    "do not retry idle work",
  );
  assert.equal(refused.model().message, null);
  refused.changes();
  assert.deepEqual(
    refused.posts.map(({ ask }) => ask),
    [idleAsk, foregroundAsk],
  );
  refused.controller.dispose();

  const asks = (page) =>
    page.posts.map(({ ask }) => ("prepare_comparison" in ask ? "idle" : "foreground"));
  console.log(
    JSON.stringify({
      withoutStore: asks(noStore),
      changesBeforeIdle: asks(quick),
      pollWhilePreparing: { conversation: conversationPoll, changes: changesPoll },
      hiddenUntilVisible: asks(hidden),
      afterLateIdleReply: race.model().comparison ? "Changes ready" : "Changes unavailable",
      afterIdleRefusal: asks(refused),
      disposed: asks(stopped),
    }),
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
