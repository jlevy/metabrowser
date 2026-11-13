// A pull request's tree of changed files opens once, at its height, and a drawn tree never
// grows by itself later: the exact production controller waits briefly for the cached list it
// reads at once, an expanded tree with no rows draws its first rows whenever they come, and a
// change a GitHub job brings to rows already drawn, with no recent input, is offered for the
// reader to open. The answers are the recorded route's (tests/fixtures/
// github-pull-files-responses.json); time, timers, and the reader's last input are the
// session's.
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
 * Every model any story's tree rendered, for the relations `run` holds across them all.
 *
 * @type {object[]}
 */
const rendered = [];

/**
 * What a refresh POST answers, as `pull-files-refresh` does, its list with no rows (`limit=0`):
 * a job started on a list not yet there, or not due, because another request already listed
 * the whole list, as `tests/golden/cli-github-pull-files-refresh.txt` records it.
 */
const REFRESH_STARTED = { status: 202, body: { refresh: "started", files: recorded.pending } };
const REFRESH_NOT_DUE = {
  status: 200,
  body: { refresh: "not_due", files: { ...recorded.comparison, limit: 0 } },
};

/**
 * One tree; *answers* is what each read of the list answers, in order ("fail" for a read the
 * server does not answer, and `{afterMs, body}` for one it answers that long after it was
 * asked), and a refresh POST answers *refresh*, `REFRESH_STARTED` unless given. What the paint
 * shows is sampled where a frame could paint: after the click's task and after each later
 * task the session runs.
 */
function story(tree, answers, input, refresh = REFRESH_STARTED) {
  let now = 0;
  const timers = new Map();
  let next = 1;
  const painted = [];
  let shown = "closed";
  let lastModel = null;
  /** When rows were first drawn, by the session's clock. */
  let drawnAt = null;
  const reads = [];
  const spans = [];
  const schedule = (callback, delayMs) => {
    const handle = next;
    next += 1;
    timers.set(handle, { callback, at: now + delayMs });
    return handle;
  };
  const controller = tree.createFileTreeController(
    {
      request(method, route) {
        if (method === "POST") {
          return Promise.resolve({
            status: refresh.status,
            etag: null,
            body: { ...refresh.body, files: { ...refresh.body.files, rows: [] } },
          });
        }
        reads.push(route);
        const answer = answers.shift();
        if (answer === "fail") {
          return Promise.reject(new Error("the server did not answer"));
        }
        if (answer?.afterMs !== undefined) {
          return new Promise((resolve) =>
            schedule(() => resolve({ status: 200, etag: null, body: answer.body }), answer.afterMs),
          );
        }
        return answer === undefined
          ? new Promise(() => {})
          : Promise.resolve({ status: 200, etag: null, body: answer });
      },
      schedule,
      cancel: (handle) => timers.delete(handle),
      now: () => now,
      isVisible: () => true,
      formatTime: (iso) => iso,
      render(model) {
        lastModel = model;
        rendered.push(model);
        if (drawnAt === null && model.expanded && model.rows.length > 0) {
          drawnAt = now;
        }
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
                  : model.notice !== null
                    ? `notice: ${model.notice.text}`
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
    drawnAt: () => drawnAt,
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

  // A list a GitHub job fills two seconds after the click, with no input since, as when a
  // pull request's files were not cached: the tree keeps its loading line until the rows
  // come, and then draws them. It has drawn nothing, so nothing it drew can move.
  {
    const input = { at: 0 };
    const late = story(tree, [recorded.absent, recorded.pending, recorded.comparison], input);
    late.controller.expand();
    late.frame();
    await settle();
    late.frame();
    await late.advance(tree.FILES_POLL_MS);
    await late.advance(2 * tree.FILES_POLL_MS);
    facts.lateRows = late.painted;
    spans.lateRows = late.spans;
  }

  // The cached read itself answers after the opening's bound and past LATE_ROWS_MS, as on a
  // loaded server: the loading line gives way to the rows.
  {
    const input = { at: 0 };
    const slow = story(tree, [{ afterMs: 600, body: recorded.comparison }], input);
    slow.controller.expand();
    slow.frame();
    await settle();
    slow.frame();
    await slow.advance(tree.FILES_POLL_MS);
    facts.slowCachedRead = slow.painted;
    spans.slowCachedRead = slow.spans;
  }

  // A first read the server does not answer, and the next poll, a second later with no
  // input, that brings the rows: the failure's notice gives way to them.
  {
    const input = { at: 0 };
    const recovered = story(tree, ["fail", recorded.comparison], input);
    recovered.controller.expand();
    recovered.frame();
    await settle();
    recovered.frame();
    await recovered.advance(tree.FILES_POLL_MS);
    facts.afterFailedRead = recovered.painted;
  }

  // A tree opened on a list GitHub has not returned, closed, and opened again: its opening
  // hold ends at once on the read's pending answer, it shows its loading line, and rows that
  // come a second after the second click are drawn.
  {
    const input = { at: 0 };
    const reopened = story(tree, [recorded.absent, recorded.pending, recorded.comparison], input);
    reopened.controller.expand();
    reopened.frame();
    await settle();
    reopened.frame();
    input.at = 300;
    await reopened.advance(input.at);
    reopened.controller.collapse();
    reopened.frame();
    input.at = 5000;
    await reopened.advance(input.at);
    reopened.controller.expand();
    reopened.frame();
    await settle();
    reopened.frame();
    await reopened.advance(input.at + tree.FILES_POLL_MS);
    facts.reopened = reopened.painted;
    spans.reopened = reopened.spans;
  }

  // The same tree opened again after GitHub returned its list while it was closed: the read
  // on opening answers at once with the rows, so the tree opens on them in one step, with no
  // loading line before them.
  {
    const input = { at: 0 };
    const filled = story(tree, [recorded.absent, recorded.comparison], input);
    filled.controller.expand();
    filled.frame();
    await settle();
    filled.frame();
    input.at = 300;
    await filled.advance(input.at);
    filled.controller.collapse();
    filled.frame();
    input.at = 5000;
    await filled.advance(input.at);
    filled.controller.expand();
    filled.frame();
    await settle();
    filled.frame();
    facts.reopenedFilled = filled.painted;
  }

  // An expanded tree whose panel is hidden before GitHub returns its list, and shown again
  // ten seconds later: its first read on showing brings the rows, and they are drawn.
  {
    const input = { at: 0 };
    const restored = story(tree, [recorded.absent, recorded.comparison], input);
    restored.controller.expand();
    restored.frame();
    await settle();
    restored.frame();
    await restored.advance(300);
    restored.controller.setShown(false);
    await restored.advance(10_000);
    restored.controller.setShown(true);
    await settle();
    restored.frame();
    facts.shownAgain = restored.painted;
  }

  // A drawn list that a later read answers as absent just after a press or key, so the tree
  // empties; GitHub lists it again a second later with no input since. The tree has no rows
  // drawn, so the new list's are drawn.
  {
    const input = { at: 0 };
    const fresh = structuredClone(recorded.comparison);
    fresh.generation = `${"0".repeat(31)}6`;
    const emptied = story(
      tree,
      [structuredClone(recorded.comparison), recorded.absent, fresh],
      input,
    );
    emptied.controller.expand();
    emptied.frame();
    await settle();
    emptied.frame();
    const window = recorded.comparison.fresh_for_s * 1000;
    input.at = window - 100;
    await emptied.advance(window);
    await emptied.advance(window + tree.FILES_POLL_MS);
    facts.refreshEmptied = emptied.painted;
  }

  // A list another request finished listing between the tree's first read, which found none,
  // and its refresh, which answers not due with the whole list and, as that answer always
  // does, none of its rows (review A1). The tree reads them at once and shows that it is
  // reading in between; before, it showed nothing until its next read, a freshness window on.
  {
    const horizon = recorded.comparison.fresh_for_s * 1000 + tree.FILES_POLL_MS;
    const input = { at: 0 };
    const notDue = story(tree, [recorded.absent, recorded.comparison], input, REFRESH_NOT_DUE);
    notDue.controller.expand();
    notDue.frame();
    await settle();
    notDue.frame();
    const between = notDue.last();
    await notDue.advance(horizon);
    facts.refreshNotDue = {
      painted: notDue.painted,
      betweenReplies: { loading: between.loading, line: between.line, rows: between.rows.length },
      drawnAt: notDue.drawnAt(),
    };
    // The same on a landing, with no input yet, whose read of the rows answers late: they are
    // drawn into the empty tree all the same, with no offer.
    const late = story(
      tree,
      [recorded.absent, { afterMs: 700, body: recorded.comparison }],
      { at: null },
      REFRESH_NOT_DUE,
    );
    late.controller.expand();
    late.frame();
    await settle();
    late.frame();
    await late.advance(horizon);
    facts.refreshNotDueLate = { painted: late.painted, drawnAt: late.drawnAt() };
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

  // A list GitHub fills a page a second, with no input after the click: its first page is
  // drawn into the empty tree, and every later page waits on the line, so the drawn tree
  // never grows by itself; the reader's press draws them all.
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
    const drawnFirst = fill.controller.snapshot().rows;
    await fill.advance(6 * tree.FILES_POLL_MS);
    const drawnWhileIdle = fill.controller.snapshot().rows;
    input.at = 6 * tree.FILES_POLL_MS + 100;
    await fill.advance(input.at);
    fill.controller.reveal();
    fill.frame();
    facts.fill = {
      painted: fill.painted,
      drawnFirst,
      drawnWhileIdle,
      drawnAfterPress: fill.controller.snapshot().rows,
    };
    spans.fill = fill.spans;
  }

  // A landing whose address opened the tree, with no press or key yet: the tree's opening is
  // the reference, and rows that come later than that are drawn into it all the same.
  {
    const input = { at: null };
    const landing = story(tree, [recorded.absent, recorded.comparison], input);
    landing.controller.expand();
    landing.frame();
    await settle();
    landing.frame();
    await landing.advance(tree.FILES_POLL_MS);
    facts.landing = landing.painted;
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
    const window = recorded.comparison.fresh_for_s * 1000;
    await refreshed.advance(window);
    facts.refreshed = { painted: [...refreshed.painted], floats: refreshed.last().offerFloats };
    // The reader closes the tree with the change still offered: that ends the offer too
    // (review B1), and opening it again draws the change without a second span.
    input.at = window + 400;
    await refreshed.advance(input.at);
    refreshed.controller.collapse();
    refreshed.controller.expand();
    refreshed.frame();
    facts.refreshedReopened = refreshed.painted.at(-1);
    spans.offerClosed = refreshed.spans;
  }

  // The same offer standing, and a later refresh that brings back the rows drawn: the offer is
  // withdrawn, since pressing it would draw nothing new (review D4).
  {
    const input = { at: 0 };
    const changed = structuredClone(recorded.comparison);
    changed.generation = `${"0".repeat(31)}4`;
    changed.fetched += 1;
    changed.rows = [
      ...changed.rows,
      { ...changed.rows[0], path: "docs/added.md", display: "docs/added.md" },
    ];
    const back = structuredClone(recorded.comparison);
    back.generation = `${"0".repeat(31)}5`;
    const returned = story(tree, [structuredClone(recorded.comparison), changed, back], input);
    returned.controller.expand();
    returned.frame();
    await settle();
    returned.frame();
    await returned.advance(recorded.comparison.fresh_for_s * 1000);
    await returned.advance(2 * recorded.comparison.fresh_for_s * 1000);
    facts.offerWithdrawn = { painted: returned.painted, spans: returned.spans };
  }

  // A cached list that is stale, drawn at the click, whose refresh answers a second later with
  // the same files, as after a rebase that leaves the diff as it was: it would draw the same
  // rows, so it is drawn in place, and nothing is offered.
  {
    const input = { at: 0 };
    const cached = { ...structuredClone(recorded.comparison), state: "stale" };
    const generation = `${"0".repeat(31)}9`;
    const past = {
      ...structuredClone(recorded.comparison),
      generation,
      offset: cached.rows.length,
      rows: [],
    };
    const same = { ...structuredClone(recorded.comparison), generation };
    const unchanged = story(tree, [cached, past, same], input, {
      status: 202,
      body: { refresh: "started", files: { ...cached, refreshing: true } },
    });
    unchanged.controller.expand();
    unchanged.frame();
    await settle();
    unchanged.frame();
    await unchanged.advance(3 * tree.FILES_POLL_MS);
    facts.unchangedRefresh = {
      painted: unchanged.painted,
      reads: unchanged.reads.length,
      offer: unchanged.last().offer,
    };
  }

  // A first read the server does not answer: the opening ends, and says it failed.
  {
    const input = { at: 0 };
    const failing = story(tree, ["fail"], input);
    failing.controller.expand();
    await settle();
    spans.failedRead = failing.spans;
  }

  // An offer joins what the drawn tree says; it hides none of it: a list stopped at GitHub's
  // rate limit keeps its line and notice, and a poll that fails keeps its error and Retry.
  {
    const drawn = { number: 7, expanded: true, rows: [], rowsVersion: 1, asking: false };
    const stopped = tree.describeFileTree(recorded.stopped, {
      ...drawn,
      error: null,
      formatTime: (iso) => iso,
      withheld: 205,
      drawn: 200,
    });
    const failed = tree.describeFileTree(recorded.comparison, {
      ...drawn,
      error: "The server did not answer.",
      formatTime: (iso) => iso,
      withheld: 3,
      drawn: 2,
      floats: true,
    });
    facts.offerKeepsNotices = {
      stopped: { line: stopped.line, notice: stopped.notice?.text ?? null, offer: stopped.offer },
      failedPoll: {
        notice: failed.notice?.text ?? null,
        action: failed.notice?.action ?? null,
        offer: failed.offer,
      },
    };
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
  // Held across every model any story's tree rendered, its refresh answering started or not
  // due: an offer stands in only for a change to rows already drawn, so an expanded tree with
  // none drawn never carries one, and once open it shows its files, its progress, a notice,
  // or its line ("No changed files."), never nothing.
  const empty = rendered.filter((model) => model.expanded && model.rows.length === 0);
  facts.invariants = {
    "an expanded tree with no rows drawn never offers": empty.every(
      (model) => model.offer === null,
    ),
    "an open tree with no rows drawn shows progress, a notice, or its line": empty
      .filter((model) => !model.opening)
      .every((model) => model.loading || model.notice !== null || model.line !== null),
  };
  return facts;
}

run()
  .then((result) => process.stdout.write(`${JSON.stringify(result, null, 2)}\n`))
  .catch((error) => {
    process.stderr.write(`${error.stack}\n`);
    process.exitCode = 1;
  });
