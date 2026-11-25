// Browserless session: a native stack's page, its front tab, its asks, and a new comparison.
//
// The answers are the stack route's for the GitHub stand-in's stacks, recorded in
// tests/fixtures/github-stack-responses.json by tests/test_cli_github_stack_golden.py, which
// fails when the recording drifts: stack 70 pending before its members' records, then
// current; 71, whose top lacks 7, which has another comparison; and 72, not linear.
//
// It runs the production builtin_plugins/github/stack-page.js: the tab a route shows, what
// a new answer does to the comparison drawn (`comparisonAction`), each file's layer marks,
// the line about members the top lacks, and the controller (`createStackController`) over a
// scripted poll, printing each request it sends and each model it renders, and over a read
// that fails and then finds its answer current, and the order the header lists the members
// in (`topFirst`). What the page draws from them, its header, tabs, and the diff views, is
// the glue's (`mountStackPage`).

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/github-stack-responses.json"), "utf8"),
);
const pagePath = path.join(repoRoot, "src/metabrowser/builtin_plugins/github/stack-page.js");

// The page module imports pull-page.js, which reads the shell's route and Git path codecs at
// import, as in the shell.
const routeContext = { atob, btoa, TextDecoder, TextEncoder, Uint8Array };
routeContext.window = routeContext;
for (const name of ["navigation.js", "git-path.js"]) {
  const file = path.join(repoRoot, "src/metabrowser/static", name);
  vm.runInNewContext(fs.readFileSync(file, "utf8"), routeContext, { filename: file });
}
globalThis.window = {
  MetabrowserGitPath: routeContext.MetabrowserGitPath,
  MetabrowserNavigationRoute: routeContext.MetabrowserNavigationRoute,
};

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

async function main() {
  const page = await import(pathToFileURL(pagePath).href);
  const { pending, current, lacking } = recorded;
  const notLinear = recorded.not_linear;

  const tabs = Object.fromEntries(
    ["", "files", "docs", "changes", "guided"].map((tab) => [
      tab || "(front)",
      page.shownTab(tab, current),
    ]),
  );

  const comparison = [
    ["nothing drawn, pending", page.comparisonAction(null, pending)],
    ["nothing drawn, current", page.comparisonAction(null, current)],
    ["drawn, the same answer", page.comparisonAction(current.comparison.key, current)],
    ["drawn, another comparison", page.comparisonAction(current.comparison.key, lacking)],
    ["drawn, the stack now absent", page.comparisonAction(current.comparison.key, notLinear)],
  ];

  const href = (number, file) => `/pull/${number}/files/${file}`;
  const marks = Object.fromEntries(
    ["docs/draft.md", "README.md"].map((file) => [file, page.layerMarks(current, file, href)]),
  );

  const said = {
    lacking: page.lackingText(lacking),
    lacking_none: page.lackingText(current),
    two_lacking: page.lackingText({ ...lacking, lacking: [7, 9] }),
    not_linear: page.absentText(notLinear.reason),
    unknown: page.absentText("something_new"),
  };

  const delays = {
    pending_visible: page.pollDelay(pending, true),
    current_visible: page.pollDelay(current, true),
    current_hidden: page.pollDelay(current, false),
  };

  // The poll: pending, then current twice (the second a 304), then the stack moved.
  const script = [
    { status: 200, etag: '"pending"', body: pending },
    { status: 200, etag: '"current"', body: current },
    { status: 304, etag: '"current"', body: null },
    { status: 200, etag: '"moved"', body: lacking },
  ];
  const sent = [];
  const rendered = [];
  /** @type {Array<() => void>} */
  const timers = [];
  let now = Date.parse("2026-09-17T12:00:00Z");
  let shownKey = null;
  const controller = page.createStackController(
    {
      async request(method, route, options) {
        sent.push({
          method,
          route,
          ...(options.etag ? { etag: options.etag } : {}),
          ...(options.body === undefined ? {} : { body: options.body }),
        });
        if (method === "POST") {
          return { status: 202, etag: null, body: {} };
        }
        return script.shift() ?? { status: 304, etag: null, body: null };
      },
      schedule(callback, delayMs) {
        timers.push(() => {
          now += delayMs;
          callback();
        });
        return timers.length;
      },
      cancel() {},
      now: () => now,
      isVisible: () => true,
      render(model) {
        const action = page.comparisonAction(shownKey, model.envelope);
        if (action === "show") {
          shownKey = model.envelope.comparison.key;
        }
        rendered.push({
          state: model.envelope?.state ?? null,
          pending: model.envelope?.pending ?? null,
          lacking: model.envelope?.lacking ?? null,
          comparison: action,
          error: model.error,
        });
      },
    },
    { number: 70 },
  );
  await controller.start();
  await settle();
  for (let poll = 0; poll < 3; poll += 1) {
    timers.shift()?.();
    await settle();
  }
  controller.dispose();

  // A read that fails while an answer is drawn, then one that finds that answer current.
  const failing = [
    { status: 200, etag: '"current"', body: current },
    { status: 503, etag: null, body: { error: "the route's own words" } },
    { status: 304, etag: '"current"', body: null },
  ];
  const recovery = [];
  /** @type {Array<() => void>} */
  const later = [];
  const recovering = page.createStackController(
    {
      async request(method) {
        return method === "POST"
          ? { status: 202, etag: null, body: {} }
          : (failing.shift() ?? { status: 304, etag: null, body: null });
      },
      schedule(callback) {
        later.push(callback);
        return later.length;
      },
      cancel() {},
      now: () => now,
      isVisible: () => true,
      render(model) {
        recovery.push({ state: model.envelope?.state ?? null, error: model.error });
      },
    },
    { number: 70 },
  );
  await recovering.start();
  await settle();
  for (let poll = 0; poll < 2; poll += 1) {
    later.shift()?.();
    await settle();
  }
  recovering.dispose();

  // The header lists the members top first, as every stack menu does.
  const order = page.topFirst(lacking).map((member) => member.number);

  process.stdout.write(
    `${JSON.stringify({ tabs, comparison, marks, said, delays, sent, rendered, recovery, order }, null, 2)}\n`,
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
