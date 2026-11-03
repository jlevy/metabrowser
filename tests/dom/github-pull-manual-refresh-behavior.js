// Manual retry stays available for failed comparisons without making reads fetch.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const root = path.resolve(__dirname, "../..");
async function run() {
  const { describePull, createPullController } = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const recorded = JSON.parse(
    fs.readFileSync(path.join(root, "tests/fixtures/github-pull-page-responses.json"), "utf8"),
  );
  const current = recorded.current.body;
  const cases = [
    "comparison_timeout",
    "comparison_too_large",
    "commits_unavailable",
    "base_uncertain",
  ];
  for (const state of cases) {
    const envelope = structuredClone(current);
    envelope.record.comparison = null;
    envelope.record.unavailable = { comparison: state };
    envelope.state = "current";
    envelope.refreshing = false;
    const options = {
      number: envelope.number,
      tab: "files",
      nowMs: Date.parse("2026-09-17T12:00:30Z"),
    };
    assert.equal(describePull(envelope, options).canRefresh, true, state);
    assert.equal(describePull({ ...envelope, refreshing: true }, options).canRefresh, false, state);
    const calls = [];
    const controller = createPullController(
      {
        request: async (method, route, options) => {
          calls.push({ method, route, body: options.body });
          return method === "POST"
            ? { status: 202, etag: null, body: { pull: { ...envelope, refreshing: true } } }
            : { status: 200, etag: null, body: envelope };
        },
        schedule: () => 0,
        cancel() {},
        now: () => options.nowMs,
        isVisible: () => true,
        render() {},
        renderMarkdown() {},
        reload() {},
        navigate() {},
      },
      options,
    );
    await controller.start();
    assert.equal(calls.filter((call) => call.method === "POST").length, 0, state);
    await controller.requestRefresh();
    assert.deepEqual(
      calls.find((call) => call.method === "POST").body,
      { number: envelope.number, retry: true },
      state,
    );
    controller.dispose();
  }
  const noStore = structuredClone(current);
  noStore.record.unavailable = { comparison: "no_store" };
  const options = {
    number: current.number,
    tab: "files",
    nowMs: Date.parse("2026-09-17T12:00:30Z"),
  };
  assert.equal(describePull(noStore, options).canRefresh, false);
  assert.equal(
    describePull(
      {
        ...noStore,
        last_refresh: {
          outcome: "network_error",
          message: null,
          reset_at: null,
          at: "2026-09-17T12:00:00Z",
        },
      },
      options,
    ).canRefresh,
    true,
  );
  process.stdout.write(
    JSON.stringify({
      manualFailuresRetry: cases,
      automaticReadsFetch: false,
      noStoreKeepsOwnAction: true,
    }) + "\n",
  );
}
run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
