// Manual retry stays available for failed comparisons without making reads fetch.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const root = path.resolve(__dirname, "../..");
async function run() {
  const { comparisonHeld, describePull, createPullController } = await import(
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
  noStore.record.comparison = null;
  noStore.comparison_route = null;
  const options = {
    number: current.number,
    tab: "files",
    nowMs: Date.parse("2026-09-17T12:00:30Z"),
  };
  assert.equal(describePull(noStore, options).canRefresh, false);
  assert.equal(describePull(noStore, options).canRetryComparison, false);
  const readFailed = describePull(noStore, { ...options, error: "The server did not answer." });
  assert.equal(readFailed.changesPending, false, "a failed read is no attempt in progress");
  assert.equal(readFailed.canRetryComparison, false, "nor a failed attempt to retry");
  assert.equal(readFailed.canFetchComparison, false, "the next good read asks by itself");
  assert.equal(readFailed.filesUnavailable, "Changes have not been fetched.");
  const failed = describePull(
    {
      ...noStore,
      last_refresh: {
        outcome: "network_error",
        message: null,
        reset_at: null,
        at: "2026-09-17T12:00:00Z",
      },
    },
    { ...options, comparisonAttempted: true },
  );
  assert.equal(failed.canRefresh, false, "only Retry changes can prepare the missing store");
  assert.equal(failed.canRetryComparison, true);
  // What holds the automatic comparison for Retry changes: an outcome a new visit would
  // only repeat, recorded since the record was written, or a rate limit before its reset.
  const nowMs = Date.parse("2026-09-17T12:00:30Z");
  const outcome = (name, at, resetAt = null) => ({
    ...noStore,
    last_refresh: { outcome: name, message: null, reset_at: resetAt, at },
  });
  const held = Object.fromEntries(
    [
      ["lender_missing after the record", outcome("lender_missing", "2026-09-17T12:00:20Z")],
      ["lender_missing before the record", outcome("lender_missing", "2026-09-17T11:00:00Z")],
      ["git_failed after the record", outcome("git_failed", "2026-09-17T12:00:20Z")],
      ["fetch_failed after the record", outcome("fetch_failed", "2026-09-17T12:00:20Z")],
      [
        "not_found_or_private after the record",
        outcome("not_found_or_private", "2026-09-17T12:00:20Z"),
      ],
      ["network_error after the record", outcome("network_error", "2026-09-17T12:00:20Z")],
      [
        "refreshing_elsewhere after the record",
        outcome("refreshing_elsewhere", "2026-09-17T12:00:20Z"),
      ],
      [
        "rate_limited before its reset",
        outcome("rate_limited", "2026-09-17T12:00:20Z", "2026-09-17T12:05:00Z"),
      ],
      [
        "rate_limited after its reset",
        outcome("rate_limited", "2026-09-17T12:00:20Z", "2026-09-17T12:00:29Z"),
      ],
      ["rate_limited without a reset", outcome("rate_limited", "2026-09-17T12:00:20Z")],
      ["succeeded", outcome("succeeded", "2026-09-17T12:00:20Z")],
    ].map(([name, envelope]) => [name, comparisonHeld(envelope, nowMs)]),
  );
  assert.deepEqual(held, {
    "lender_missing after the record": true,
    "lender_missing before the record": false,
    "git_failed after the record": true,
    "fetch_failed after the record": true,
    "not_found_or_private after the record": true,
    "network_error after the record": false,
    "refreshing_elsewhere after the record": false,
    "rate_limited before its reset": true,
    "rate_limited after its reset": false,
    "rate_limited without a reset": false,
    succeeded: false,
  });
  process.stdout.write(
    `${JSON.stringify({
      manualFailuresRetry: cases,
      automaticReadsFetch: false,
      noStoreSkipsPrematureRetry: true,
    })}\n`,
  );
}
run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
