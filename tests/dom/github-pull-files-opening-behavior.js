// A pull request's tree of changed files opens once, at its height, and never grows by
// itself later: the exact production controller waits briefly for the cached list it reads
// at once, and rows a GitHub job brings with no recent input are offered on its line for the
// reader to open. The answers are the recorded route's (tests/fixtures/
// github-pull-files-responses.json); time, timers, and the reader's last input are the
// session's.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const root = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(root, "tests/fixtures/github-pull-files-responses.json"), "utf8"),
);
for (const envelope of Object.values(recorded)) {
  envelope.rows = envelope.rows.map((row) => JSON.parse(row));
}

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/**
 * One tree; *answers* is what each read of the list answers, in order, and a refresh POST
 * answers that it started. What the paint shows is sampled where a frame could paint: after
 * the click's task and after each later task the session runs.
 */
function story(tree, answers, input) {
  let now = 0;
  const timers = new Map();
  let next = 1;
  const painted = [];
  let shown = "closed";
  const reads = [];
  const controller = tree.createFileTreeController(
    {
      request(method, route) {
        if (method === "POST") {
          return Promise.resolve({
            status: 202,
            etag: null,
            body: { files: { ...recorded.pending, rows: [] } },
          });
        }
        reads.push(route);
        const answer = answers.shift();
        return answer === undefined
          ? new Promise(() => {})
          : Promise.resolve({ status: 200, etag: null, body: answer });
      },
      schedule(callback, delayMs) {
        const handle = next;
        next += 1;
        timers.set(handle, { callback, at: now + delayMs });
        return handle;
      },
      cancel: (handle) => timers.delete(handle),
      now: () => now,
      isVisible: () => true,
      formatTime: (iso) => iso,
      render(model) {
        // What the paint shows: closed while opening, else the line and the rows.
        shown =
          !model.expanded || model.opening
            ? "closed"
            : model.offer !== null
              ? `offer: ${model.offer}`
              : model.rows.length > 0
                ? `${model.rows.length} rows`
                : model.loading
                  ? "loading line"
                  : "empty";
      },
      markAnchor() {},
      markCurrent() {},
      markMuted() {},
      page: () => null,
      open() {},
      leave() {},
      lastInput: () => input.at,
    },
    { number: 7, autoExpandFiles: 3000 },
  );
  const frame = () => {
    if (painted.at(-1) !== shown) {
      painted.push(shown);
    }
  };
  return {
    controller,
    painted,
    reads,
    frame,
    async advance(target) {
      for (;;) {
        const due = [...timers.entries()]
          .filter(([, timer]) => timer.at <= target)
          .sort((a, b) => a[1].at - b[1].at)[0];
        if (due === undefined) {
          break;
        }
        timers.delete(due[0]);
        now = due[1].at;
        due[1].callback();
        await settle();
        frame();
      }
      now = target;
    },
  };
}

async function run() {
  const tree = await import(
    pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github/pull-files-tree.js")).href
  );
  const facts = {};

  // A list the cache holds: one step from closed to its rows, at the click.
  {
    const input = { at: 0 };
    const cached = story(tree, [recorded.comparison], input);
    cached.controller.expand();
    cached.frame();
    await settle();
    cached.frame();
    facts.cached = cached.painted;
  }

  // A list a GitHub job fills two seconds after the click, with no input since: the tree
  // keeps its loading line, which then offers the rows, and draws them when asked.
  {
    const input = { at: 0 };
    const late = story(tree, [recorded.absent, recorded.pending, recorded.comparison], input);
    late.controller.expand();
    late.frame();
    await settle();
    late.frame();
    await late.advance(tree.FILES_POLL_MS);
    await late.advance(2 * tree.FILES_POLL_MS);
    assert.equal(late.controller.snapshot().rows, 0, "late rows are not drawn by themselves");
    input.at = 2 * tree.FILES_POLL_MS + 100;
    late.controller.reveal();
    late.frame();
    facts.lateRows = late.painted;
  }

  // The same job answering within the input's window draws its rows as the click's.
  {
    const input = { at: 0 };
    const prompt = story(tree, [recorded.absent, recorded.comparison], input);
    prompt.controller.expand();
    prompt.frame();
    await settle();
    prompt.frame();
    input.at = tree.FILES_POLL_MS - 100;
    await prompt.advance(tree.FILES_POLL_MS);
    facts.promptRows = prompt.painted;
  }

  // A server that does not answer within the bound: the tree opens on its loading line.
  {
    const input = { at: 0 };
    const slow = story(tree, [], input);
    slow.controller.expand();
    slow.frame();
    await settle();
    slow.frame();
    await slow.advance(tree.FILES_OPEN_HOLD_MS);
    facts.slowRead = slow.painted;
  }
  return facts;
}

run()
  .then((result) => process.stdout.write(`${JSON.stringify(result)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });
