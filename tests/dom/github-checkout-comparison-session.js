// The production pull controller consumes replies recorded by the CLI checkout golden.
// Opening Files is read-only; a reader's Fetch changes action attaches the comparison.
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

async function run() {
  const page = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  let answer = recorded.before;
  let model;
  const requests = [];
  const timers = new Map();
  const controller = page.createPullController(
    {
      async request(method, route, options) {
        requests.push({ method, route, ...(method === "POST" ? { body: options.body } : {}) });
        return method === "POST" ? recorded.started : answer;
      },
      schedule(callback, delay) {
        const id = Symbol();
        timers.set(id, { callback, delay });
        return id;
      },
      cancel(id) {
        timers.delete(id);
      },
      now: () => Date.parse("2026-09-17T12:00:30Z"),
      isVisible: () => true,
      render(next) {
        model = next;
      },
      renderMarkdown() {},
      reload() {
        throw new Error("a checkout comparison never reloads its source");
      },
      navigate() {
        throw new Error("a checkout comparison never switches its source");
      },
    },
    { number: 10, tab: "files" },
  );
  const story = [];
  function snapshot(step) {
    story.push({
      step,
      requests: requests.splice(0),
      canFetchChanges: model.canFetchComparison,
      refreshing: model.refreshing,
      comparison: model.comparison,
      browse: model.browse,
      headOffer: model.headOffer,
    });
  }
  await controller.start();
  assert.equal(
    requests.some((request) => request.method === "POST"),
    false,
  );
  assert.equal(model.canFetchComparison, true);
  snapshot("opening Files changed acquires nothing");
  await controller.requestComparison();
  assert.deepEqual(requests[0].body, { number: 10, retry: true, comparison: true });
  assert.equal(model.canFetchComparison, false);
  snapshot("Fetch changes starts the explicit comparison job");
  await controller.requestComparison();
  assert.equal(requests.length, 0);
  answer = recorded.ready;
  await controller.poll();
  assert.equal(model.canFetchComparison, false);
  assert.equal(model.browse, null);
  assert.equal(model.headOffer, null);
  assert.equal(model.comparison.route, recorded.ready.body.comparison_route);
  snapshot("the finished comparison stays beside the folder");
  controller.dispose();
  process.stdout.write(`${JSON.stringify(story, null, 2)}\n`);
}
run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
