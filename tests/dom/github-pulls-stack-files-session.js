// Browserless session: a native stack's combined changed files, under its Whole stack row
// in the Pulls tab (mb-odt4), through the production code.
//
// builtin_plugins/github/stack-files.js reads them as the stack's own page reads the files
// of its Diff summary: the stack (`GET stack`), then the stack's comparison, once for each
// comparison, and answers them as a list of changed files in the envelope a pull request's
// `pull-files` route answers, so the production tree controller of a pull request's files
// (pull-files-tree.js, which tests/dom/github-pull-files-tree-session.js runs on its own
// list) draws them. This session mounts that controller on a stack's list.
//
// The stack's answers are the `stack` route's own, recorded in
// tests/fixtures/github-stack-responses.json by tests/test_cli_github_stack_golden.py, which
// records the comparison its `current` answer names too, as `stack-comparison` gave it
// (tests/fixtures/github-stack-comparison-responses.json). The rows of that comparison are
// made here as the Pulls tab makes them, by the diff view's own `summaryRows`
// (builtin_plugins/diff/index.js), loaded whole, so they are the Diff summary's rows of it,
// counts and statuses included. No comparison is recorded for the answer the stack moves
// to, `grown`: each file that answer names stands in as a modified one with no counts, so
// that step holds which files are listed and when each read is made, not their counts.
// The panel's own path from the view to the tree (`comparisonRows` in pulls-panel.js) runs
// only in a browser: tests/test_github_stack_page_chrome.py holds there that a press lists
// the rows the stack page's Diff summary lists. Each step prints what was asked, which
// comparisons were read, and what the tree shows.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const GITHUB = path.join(repoRoot, "src/metabrowser/builtin_plugins/github");
const DIFF_VIEW = "src/metabrowser/builtin_plugins/diff/index.js";
// The shared tree, as the `changed-files-tree` bundle installs it.
const shared = require("./changed-files-tree-fixture.js").changedFilesTree();

// The comparison the recorded `current` answer names, as its route gave it.
const recordedComparisons = JSON.parse(
  fs.readFileSync(
    path.join(repoRoot, "tests/fixtures/github-stack-comparison-responses.json"),
    "utf8",
  ),
);

/** A row as drawn: a folder "v" open or ">" closed with its file count, a file its badge,
 * each with its counts as its row writes them (`changeStats`). */
function line(row) {
  const indent = "  ".repeat(row.depth);
  const stats = shared.changeStats(row, String);
  const counts = stats === null ? "" : ` ${stats.text}`;
  return row.kind === "folder"
    ? `${indent}${row.expanded ? "v" : ">"} ${row.name}/ (${row.files})${counts}`
    : `${indent}${row.badge} ${row.name}${counts}`;
}

/**
 * The diff plugin's view, as the page registers it: its module loaded whole over a stand-in
 * for the SDK that hands it the shared changed-files tree, which is all `summaryRows` asks
 * of it.
 */
async function loadDiffView() {
  let view = null;
  const sdk = new Proxy(
    {
      registerView: (_kind, _name, spec) => {
        view = spec;
      },
      loadChangedFilesTree: async () => shared,
    },
    { get: (target, name) => target[name] ?? (() => undefined) },
  );
  const saved = Object.getOwnPropertyDescriptor(globalThis, "window");
  Object.defineProperty(globalThis, "window", {
    value: { metabrowser: sdk },
    configurable: true,
    writable: true,
  });
  try {
    await import(pathToFileURL(path.join(repoRoot, DIFF_VIEW)).href);
  } finally {
    if (saved === undefined) {
      delete globalThis.window;
    } else {
      Object.defineProperty(globalThis, "window", saved);
    }
  }
  assert.equal(typeof view?.summaryRows, "function", "the diff view has summaryRows");
  return view;
}

async function main() {
  const tree = await import(pathToFileURL(path.join(GITHUB, "pull-files-tree.js")).href);
  const stackFiles = await import(pathToFileURL(path.join(GITHUB, "stack-files.js")).href);
  const view = await loadDiffView();
  const answers = JSON.parse(
    fs.readFileSync(path.join(repoRoot, "tests/fixtures/github-stack-responses.json"), "utf8"),
  );
  const settle = async () => {
    for (let at = 0; at < 10; at += 1) {
      await new Promise((resolve) => setImmediate(resolve));
    }
  };
  const POLL = tree.FILES_POLL_MS;
  /** One tree over scripted answers of the stack route, by the recording's names. */
  function mount() {
    const timers = new Map();
    const reads = [];
    const requests = [];
    const comparisons = [];
    let last = null;
    let model = null;
    let nextTimer = 0;
    const request = async (method, route, options) => {
      requests.push(`${method} ${route}${options.body ? ` ${JSON.stringify(options.body)}` : ""}`);
      if (method === "POST") {
        return { status: 202, etag: null, body: {} };
      }
      const name = reads.shift();
      if (name === undefined) {
        throw Error("no read scripted");
      }
      last = answers[name];
      return { status: 200, etag: null, body: last };
    };
    const list = stackFiles.createStackFileList(
      {
        request,
        rows: async (comparison) => {
          comparisons.push(`${comparison.left.slice(0, 7)}..${comparison.right.slice(0, 7)}`);
          if (last === answers.current) {
            // The comparison this answer names, read as the panel reads it.
            return view.summaryRows(recordedComparisons.current);
          }
          return last.files.map((file) => ({
            path: file.path,
            previous_path: null,
            status: "modified",
            additions: null,
            deletions: null,
            display: file.path,
            previous_display: null,
          }));
        },
        now: () => Date.parse("2026-09-17T12:00:30Z"),
      },
      70,
      "Changed files of Stack #70",
    );
    const controller = tree.createFileTreeController(
      {
        request,
        schedule: (callback, delay) => {
          const key = ++nextTimer;
          timers.set(key, { callback, delay });
          return key;
        },
        cancel: (key) => timers.delete(key),
        now: () => Date.parse("2026-09-17T12:00:30Z"),
        isVisible: () => true,
        formatTime: (iso) => iso,
        formatCount: (count) => count.toLocaleString("en-US"),
        render: (next) => {
          model = next;
        },
        markAnchor() {},
        markCurrent() {},
        markMuted() {},
        page: () => null,
        open() {},
        leave() {},
        tree: shared,
      },
      { number: -70.5, autoExpandFiles: 300, list },
    );
    const story = [];
    return {
      controller,
      reads,
      story,
      model: () => model,
      /** Run the tree's next poll, whatever it waits, and any read it asks for at once
       * after it, as a list that is not the one held is read again from its start. */
      async poll() {
        const due = (now) =>
          [...timers].find(([, timer]) => (now ? timer.delay === 0 : timer.delay >= POLL));
        for (let entry = due(false); entry !== undefined; entry = due(true)) {
          timers.delete(entry[0]);
          entry[1].callback();
          await settle();
        }
      },
      look(step) {
        story.push({
          step,
          requests: requests.splice(0),
          "comparisons read": comparisons.splice(0),
          label: model.label,
          loading: model.loading,
          notice: model.notice === null ? null : `${model.notice.text} [${model.notice.action}]`,
          line: model.line,
          rows: model.rows.map(line),
          "next poll in": [...timers.values()]
            .filter((timer) => timer.delay >= POLL)
            .map((timer) => timer.delay),
        });
      },
    };
  }

  // A stack whose members are not fetched yet, then fetched; read again, moved, and gone.
  const opened = mount();
  opened.reads.push("pending");
  opened.controller.expand();
  await settle();
  opened.look("opened on a stack whose members are not fetched: it asks for each, and waits");
  assert.equal(opened.model().loading, true);
  opened.reads.push("current");
  await opened.poll();
  opened.look("the members arrive: the stack's comparison is read once, and its files are drawn");
  assert.equal(opened.model().loading, false);
  assert.ok(opened.model().rows.some((row) => row.kind === "file"));
  opened.reads.push("current");
  await opened.poll();
  opened.look("a freshness window on, the same comparison: the stack is read, and nothing else");
  assert.deepEqual(opened.story.at(-1)["comparisons read"], [], "a comparison is read once");
  assert.deepEqual(opened.story.at(-1).rows, opened.story.at(-2).rows);
  opened.reads.push("grown", "grown");
  await opened.poll();
  opened.look("the stack moves: another comparison, read once, replaces the files");
  assert.equal(opened.story.at(-1)["comparisons read"].length, 1);
  opened.reads.push("not_linear");
  await opened.poll();
  opened.look("the stack can no longer be shown as one comparison: no list, and Retry");
  assert.equal(opened.model().notice?.action, "retry");
  opened.controller.dispose();

  // A member whose fetch ends without a record: two reads on, the tree says so, with Retry.
  const failed = mount();
  failed.reads.push("pending");
  failed.controller.expand();
  await settle();
  failed.look("opened on a pending stack: each member is asked for");
  failed.reads.push("pending");
  await failed.poll();
  failed.look("one read on, still pending with no fetch running: it waits once more");
  assert.equal(failed.model().loading, true);
  failed.reads.push("pending");
  await failed.poll();
  failed.look("two reads on: the fetch is taken as failed, and the tree offers Retry");
  assert.equal(failed.model().notice?.action, "retry");
  failed.reads.push("pending");
  await failed.controller.retry();
  await settle();
  failed.look("Retry asks for each member again, as a reader's retry");
  assert.ok(
    failed.story.at(-1).requests.filter((line) => line.includes('"retry":true')).length === 2,
    "Retry asks for both members",
  );
  failed.controller.dispose();
  process.stdout.write(
    `${JSON.stringify({ "a stack's files": opened.story, "a member that cannot be fetched": failed.story }, null, 2)}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});
