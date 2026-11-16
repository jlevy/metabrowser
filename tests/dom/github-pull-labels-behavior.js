// Browserless session: a pull request's page whose record names its labels alone, as one
// cached before label colors does, while the repository's label set is read (`mb-varu`).
//
// builtin_plugins/github/pull-page.js loads whole: createPullController asks for the set
// and polls, and describePull draws each chip from the record or from the envelope's
// `repository_labels`. The envelopes are the recorded pull request 7 of
// tests/fixtures/github-pull-page-responses.json with its one label named alone, beside
// one GitHub no longer has; the label routes' own answers are tests/golden/
// cli-github-labels.txt's. Timers, the clock, and paint are injected. Each step prints the
// requests the page made, the poll it left, and the chips it painted, if it painted. Run by
// tests/test_github_pull_labels_session.py and pinned in
// tests/golden/cli-ui-github-pull-page.tryscript.md.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const root = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/github-pull-page-responses.json"), "utf8"),
);
const LABELS_REFRESH = "/api/plugin/github/labels-refresh";

/** The recorded envelope with its labels named alone, and the set's state as given. */
function named(labelsPending, repositoryLabels) {
  const body = structuredClone(recorded.current.body);
  body.record.pull.labels = body.record.pull.labels
    .concat([{ name: "deleted-on-github", color: null, description: null }])
    .map(({ name }) => ({ name, color: null, description: null }));
  body.labels_pending = labelsPending;
  body.repository_labels = repositoryLabels;
  return body;
}

// The set's entry for the label it holds is that label as the record's own colors name it.
const own = recorded.current.body.record.pull.labels[0];
const answers = {
  bare: { status: 200, etag: '"bare"', body: named(false, []) },
  reading: { status: 200, etag: '"reading"', body: named(true, []) },
  colored: { status: 200, etag: '"colored"', body: named(false, [own]) },
};
const started = {
  status: 202,
  etag: null,
  body: { refresh: "started", labels: {}, status_route: "/api/plugin/github/labels" },
};
const notDue = {
  status: 200,
  etag: null,
  body: { refresh: "not_due", labels: {}, status_route: "/api/plugin/github/labels" },
};

/** One page: a scripted server, its timers, and what it painted. */
function createPage(runtime, { pull, refresh }) {
  const log = [];
  const timers = new Map();
  let nextTimer = 1;
  let paints = [];
  const server = { pull, refresh: [...refresh] };
  const deps = {
    async request(method, route, options) {
      if (method === "POST") {
        log.push(`POST ${route} ${JSON.stringify(options.body)}`);
        assert.equal(route, LABELS_REFRESH, "the page asks for nothing but the label set");
        const answer = server.refresh.shift();
        assert.ok(answer, `no scripted answer for POST ${route}`);
        return answer;
      }
      const answer = server.pull;
      if (options.etag) {
        log.push(`GET ${route} (If-None-Match)`);
        if (options.etag === answer.etag) {
          return { status: 304, etag: answer.etag, body: null };
        }
      } else {
        log.push(`GET ${route}`);
      }
      return structuredClone(answer);
    },
    schedule(callback, delayMs) {
      const id = nextTimer++;
      timers.set(id, { callback, delayMs });
      return id;
    },
    cancel(handle) {
      timers.delete(handle);
    },
    now: () => Date.parse("2026-09-17T12:00:30Z"),
    isVisible: () => true,
    render(model) {
      paints.push(model);
    },
    renderMarkdown() {},
    reload() {},
    navigate() {},
  };
  const controller = runtime.createPullController(deps, { number: 7, tab: "" });

  async function settle() {
    for (let turn = 0; turn < 20; turn += 1) {
      await new Promise((resolve) => setImmediate(resolve));
    }
  }

  return {
    controller,
    server,
    /** The model it painted last. */
    painted: () => paints.at(-1),
    async step(name, action) {
      log.length = 0;
      paints = [];
      await action();
      await settle();
      const timer = [...timers.values()].find((each) => each.delayMs !== runtime.REFRESH_ASK_MS);
      const delay = timer?.delayMs;
      const poll =
        delay === runtime.FAST_POLL_MS ? "fast" : delay === runtime.SLOW_POLL_MS ? "slow" : delay;
      const last = paints.at(-1);
      return {
        step: name,
        requests: [...log],
        poll: poll ?? null,
        // Each chip: its name, GitHub's color or "neutral", and its tooltip; "unchanged"
        // when the step painted nothing new.
        labels:
          last === undefined
            ? "unchanged"
            : last.pull.labels.map(
                (label) =>
                  `${label.name} ${label.color === null ? "neutral" : `#${label.color}`} ${label.tip === null ? "no tip" : "tip"}`,
              ),
      };
    },
    /** The poll that is due. */
    fire() {
      const [id, timer] = [...timers.entries()].find(
        ([, each]) => each.delayMs !== runtime.REFRESH_ASK_MS,
      );
      timers.delete(id);
      timer.callback();
    },
  };
}

/** What a chip drawn without its color and the same chip colored share: all but paint. */
function layout(model) {
  const copy = structuredClone(model);
  copy.pull.labels = copy.pull.labels.map(({ name }) => name);
  return copy;
}

async function run() {
  const runtime = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-page.js")).href
  );
  const steps = [];

  // The first read shows the labels named alone, with nothing cached: the page asks for the
  // set at once, and the job it started makes the next read a fast poll.
  const page = createPage(runtime, { pull: answers.bare, refresh: [started] });
  steps.push(await page.step("a first read of labels named alone", () => page.controller.start()));
  const bare = page.painted();
  page.server.pull = answers.reading;
  steps.push(await page.step("the set's job runs", () => page.fire()));
  page.server.pull = answers.colored;
  steps.push(await page.step("the set is cached", () => page.fire()));
  const colored = page.painted();
  // Only the chip's color and tooltip change: the same chips in the same order, and the
  // same header, rows, and everything else the page paints.
  assert.deepEqual(layout(colored), layout(bare), "a label's color arriving moves nothing");
  assert.notDeepEqual(colored.pull.labels, bare.pull.labels);
  steps.push(await page.step("nothing changes", () => page.fire()));
  page.controller.dispose();

  // The set already being read: the page asks for nothing and polls fast until it is done.
  const joined = createPage(runtime, { pull: answers.reading, refresh: [] });
  steps.push(await joined.step("a first read while the job runs", () => joined.controller.start()));
  joined.controller.dispose();

  // The server finds the set not due, as for a label deleted on GitHub that a set read
  // within its age does not hold: the page asks once and stays on its slow poll.
  const held = createPage(runtime, { pull: answers.colored, refresh: [notDue] });
  steps.push(await held.step("a label the set does not hold", () => held.controller.start()));
  steps.push(await held.step("the next poll", () => held.fire()));
  held.controller.dispose();

  // Every label has its own color: the page never asks.
  const plain = createPage(runtime, { pull: recorded.current, refresh: [] });
  steps.push(await plain.step("labels with their own colors", () => plain.controller.start()));
  plain.controller.dispose();

  process.stdout.write(`${JSON.stringify({ labelsPending: steps })}\n`);
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
