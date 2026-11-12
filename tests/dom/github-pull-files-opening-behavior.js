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
  let lastModel = null;
  const reads = [];
  const spans = [];
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
        lastModel = model;
        // What the paint shows: closed while opening, else the line and the rows.
        shown =
          !model.expanded || model.opening
            ? "closed"
            : model.offer !== null
              ? `${model.rows.length} rows, offer: ${model.offer}`
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
      held: (hold, heldMs, outcome) => spans.push(`${hold} ${outcome} ${heldMs} ms`),
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
    spans,
    frame,
    last: () => lastModel,
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
  // Each hold's span, by story: how long it held and why it ended.
  const spans = {};

  // A list the cache holds: one step from closed to its rows, at the click.
  {
    const input = { at: 0 };
    const cached = story(tree, [recorded.comparison], input);
    cached.controller.expand();
    cached.frame();
    await settle();
    cached.frame();
    facts.cached = cached.painted;
    spans.cached = cached.spans;
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
    await late.advance(input.at);
    late.controller.reveal();
    late.frame();
    facts.lateRows = late.painted;
    spans.lateRows = late.spans;
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

  // A list GitHub fills a page a second: the reader opens the first rows the line offers,
  // and then does nothing. Every later page waits on the line too, so the drawn tree never
  // grows by itself; the reader's press draws them all.
  {
    const input = { at: 0 };
    const pages = [
      recorded.absent,
      recorded["filling 0"],
      recorded["filling 1"],
      recorded["filling 2"],
      recorded.filled,
    ].map((envelope) => structuredClone(envelope));
    const fill = story(tree, pages, input);
    fill.controller.expand();
    fill.frame();
    await settle();
    fill.frame();
    await fill.advance(2 * tree.FILES_POLL_MS);
    input.at = 2 * tree.FILES_POLL_MS + 200;
    await fill.advance(input.at);
    fill.controller.reveal();
    fill.frame();
    await fill.advance(6 * tree.FILES_POLL_MS);
    const drawnWhileIdle = fill.controller.snapshot().rows;
    input.at = 6 * tree.FILES_POLL_MS + 100;
    fill.controller.reveal();
    fill.frame();
    facts.fill = {
      painted: fill.painted,
      drawnWhileIdle,
      drawnAfterPress: fill.controller.snapshot().rows,
    };
  }

  // A landing whose address opened the tree, with no press or key yet: the tree's opening is
  // the reference, so rows that come later than that are offered as well.
  {
    const input = { at: null };
    const landing = story(tree, [recorded.absent, recorded.comparison], input);
    landing.controller.expand();
    landing.frame();
    await settle();
    landing.frame();
    await landing.advance(tree.FILES_POLL_MS);
    facts.landing = landing.painted;
    // The reader closes the tree with its rows still offered: that ends the offer too.
    await landing.advance(tree.FILES_POLL_MS + 400);
    landing.controller.collapse();
    spans.landingClosed = landing.spans;
  }

  // A drawn list that is complete shows no line; a refresh that changes it later floats its
  // offer over the tree's top, so offering it moves nothing either.
  {
    const input = { at: 0 };
    const changed = structuredClone(recorded.comparison);
    changed.generation = "0".repeat(31) + "4";
    changed.fetched += 1;
    changed.rows = [
      ...changed.rows,
      { ...changed.rows[0], path: "docs/added.md", display: "docs/added.md" },
    ];
    const refreshed = story(tree, [structuredClone(recorded.comparison), changed], input);
    refreshed.controller.expand();
    refreshed.frame();
    await settle();
    refreshed.frame();
    await refreshed.advance(recorded.comparison.fresh_for_s * 1000);
    facts.refreshed = { painted: refreshed.painted, floats: refreshed.last().offerFloats };
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
    spans.slowRead = slow.spans;
  }
  facts.spans = spans;
  return facts;
}

run()
  .then((result) => process.stdout.write(`${JSON.stringify(result, null, 2)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });
