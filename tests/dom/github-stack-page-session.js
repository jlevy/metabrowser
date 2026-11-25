// Browserless session: a native stack's page, its front tab, its asks, and its body.
//
// The answers are the stack route's for the GitHub stand-in's stacks, recorded in
// tests/fixtures/github-stack-responses.json by tests/test_cli_github_stack_golden.py, which
// fails when the recording drifts: stack 70 pending before its members' records, then
// current; 71, whose top lacks 7, which has another comparison; and 72, not linear.
//
// It runs the production builtin_plugins/github/stack-page.js: the tab a route shows, the
// header's rows from its first paint to the answer (`stackHeader`), what the page passes the
// diff view for its Diff summary and its Docs and Changes, what a new answer does to the
// comparison drawn (`comparisonAction`), the line about members the top lacks, and the
// controller (`createStackController`) over a
// scripted poll, over a read that fails and then finds its answer current, over a cold
// stack of more members than the server fetches at once, one of whose fetches fails, over
// a read asked for while one is on its way, over a fetch that ends once the stack is no
// longer linear, and over an answer read as a fetch ended before its record. Then the
// body's state machine (`bodyPlan` and its events) and the notices above it
// (`statusNotices`) over a reader who opens a file while the stack moves. What is left to
// the glue (`mountStackPage`) is the drawing, which github-stack-guide-mount-session.js
// mounts.

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

const START = Date.parse("2026-09-17T12:00:00Z");

/** The scripted poll of the first session: pending, current, unchanged, then moved. */
async function scriptedPoll(page, pending, current, lacking) {
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
  let now = START;
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
          failed: model.failed,
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
  return { sent, rendered };
}

/** A read that fails while an answer is drawn, then one that finds that answer current. */
async function recovering(page, current) {
  const failing = [
    { status: 200, etag: '"current"', body: current },
    { status: 503, etag: null, body: { error: "the route's own words" } },
    { status: 304, etag: '"current"', body: null },
  ];
  const recovery = [];
  /** @type {Array<() => void>} */
  const later = [];
  const controller = page.createStackController(
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
      now: () => START,
      isVisible: () => true,
      render(model) {
        recovery.push({ state: model.envelope?.state ?? null, error: model.error });
      },
    },
    { number: 70 },
  );
  await controller.start();
  await settle();
  for (let poll = 0; poll < 2; poll += 1) {
    later.shift()?.();
    await settle();
  }
  controller.dispose();
  return recovery;
}

/**
 * A cold stack of ten members with no record, on a server that runs at most eight fetches
 * at once (`MAX_PULL_JOBS`) and refuses the rest with 429. Each fetch takes three seconds;
 * 109's ends without a record. The reader then retries it, and it arrives.
 */
async function coldStack(page, pending) {
  const numbers = Array.from({ length: 10 }, (_, at) => 100 + at);
  let now = START;
  /** Running fetches: number to when it ends. @type {Map<number, number>} */
  const running = new Map();
  const fetched = new Set();
  let failOnce = true;
  const asked = [];
  const rendered = [];
  /** @type {Array<{at: number, callback: () => void}>} */
  let timers = [];

  function settleJobs() {
    for (const [number, ends] of running) {
      if (now >= ends) {
        running.delete(number);
        if (number === 109 && failOnce) {
          failOnce = false;
        } else {
          fetched.add(number);
        }
      }
    }
  }

  function envelope() {
    settleJobs();
    const members = numbers.map((number, at) => {
      const has = fetched.has(number);
      return {
        number,
        place: at + 1,
        title: null,
        state: "open",
        base: has ? "b".repeat(40) : null,
        head: has ? "c".repeat(40) : null,
        in_top: null,
        pending: !has,
        fetching: !has && running.has(number),
      };
    });
    const waiting = members.filter((member) => member.pending).map((member) => member.number);
    return { ...pending, members, pending: waiting, state: waiting.length ? "pending" : "current" };
  }

  const controller = page.createStackController(
    {
      async request(method, _route, options) {
        if (method === "POST") {
          settleJobs();
          const { number } = options.body;
          let status = 202;
          if (!running.has(number)) {
            if (running.size >= 8) {
              status = 429;
            } else {
              running.set(number, now + 3000);
            }
          }
          asked.push(
            `${(now - START) / 1000}s #${number}${options.body.retry ? " retry" : ""} ${status}`,
          );
          return { status, etag: null, body: {} };
        }
        const body = envelope();
        return { status: 200, etag: `"${JSON.stringify(body.members)}"`, body };
      },
      schedule(callback, delayMs) {
        timers.push({ at: now + delayMs, callback });
        return timers.length;
      },
      cancel() {},
      now: () => now,
      isVisible: () => true,
      render(model) {
        rendered.push({
          at: `${(now - START) / 1000}s`,
          pending: model.envelope?.pending ?? null,
          failed: model.failed,
        });
      },
    },
    { number: 80 },
  );
  async function runUntil(end) {
    while (timers.length > 0) {
      timers.sort((a, b) => a.at - b.at);
      const next = timers[0];
      if (next.at > end) {
        return;
      }
      timers = timers.slice(1);
      now = next.at;
      next.callback();
      await settle();
    }
  }
  await controller.start();
  await settle();
  await runUntil(START + 20000);
  const delayAfterFailure = timers.length ? timers[0].at - now : null;
  // The reader's Retry.
  await controller.retry();
  await settle();
  await runUntil(START + 30000);
  controller.dispose();
  return { asked, rendered, delay_after_failure: delayAfterFailure };
}

/**
 * A member's fetch the server took while the stack was pending, which ends without moving
 * the member, by which time the stack is not linear (`absent`): the ask ends as on any
 * other answer, and the page goes back to reading at the absent stack's cadence.
 */
async function absentAsk(page, notLinear) {
  let now = START;
  /** When the one fetch ends, once the ask started it. @type {number | null} */
  let ends = null;
  const asked = [];
  const reads = [];
  /** @type {Array<{at: number, callback: () => void}>} */
  let timers = [];

  function envelope() {
    const ended = ends !== null && now >= ends;
    const members = notLinear.members.map((member) => ({
      ...member,
      pending: member.number === 8,
      fetching: member.number === 8 && ends !== null && !ended,
    }));
    return ended
      ? { ...notLinear, members, pending: [8] }
      : { ...notLinear, state: "pending", reason: null, members, pending: [8] };
  }

  const controller = page.createStackController(
    {
      async request(method, _route, options) {
        if (method === "POST") {
          ends ??= now + 3000;
          asked.push(`${(now - START) / 1000}s #${options.body.number} 202`);
          return { status: 202, etag: null, body: {} };
        }
        const body = envelope();
        reads.push(`${(now - START) / 1000}s ${body.state}`);
        return { status: 200, etag: `"${JSON.stringify(body)}"`, body };
      },
      schedule(callback, delayMs) {
        timers.push({ at: now + delayMs, callback });
        return timers.length;
      },
      cancel() {},
      now: () => now,
      isVisible: () => true,
      render() {},
    },
    { number: 72 },
  );
  await controller.start();
  await settle();
  for (let step = 0; step < 100 && timers.length > 0; step += 1) {
    timers.sort((a, b) => a.at - b.at);
    const next = timers[0];
    if (next.at > START + 60000) {
      break;
    }
    timers = timers.slice(1);
    now = next.at;
    next.callback();
    await settle();
  }
  controller.dispose();
  return { asked, reads };
}

/**
 * The reader's fetch of a member with no record ends, and one answer shows it ended before
 * the record it wrote is read; the next read has it. The page confirms an ended fetch with
 * one more read before it names the member as failed, so it names none.
 */
async function endedRace(page, pending) {
  let now = START;
  let gets = 0;
  const rendered = [];
  /** @type {Array<{at: number, callback: () => void}>} */
  let timers = [];

  function envelope() {
    // Read 0 is before the ask, read 1 after its fetch ended, and read 2 has the record.
    const has = gets >= 2;
    const member = {
      number: 101,
      place: 1,
      title: null,
      state: "open",
      base: has ? "b".repeat(40) : null,
      head: has ? "c".repeat(40) : null,
      in_top: null,
      pending: !has,
      fetching: false,
    };
    return {
      ...pending,
      members: [member],
      pending: has ? [] : [101],
      state: has ? "current" : "pending",
    };
  }

  const controller = page.createStackController(
    {
      async request(method) {
        if (method === "POST") {
          return { status: 202, etag: null, body: {} };
        }
        const body = envelope();
        gets += 1;
        return { status: 200, etag: `"${gets}"`, body };
      },
      schedule(callback, delayMs) {
        timers.push({ at: now + delayMs, callback });
        return timers.length;
      },
      cancel() {},
      now: () => now,
      isVisible: () => true,
      render(model) {
        rendered.push({
          at: `${(now - START) / 1000}s`,
          state: model.envelope?.state ?? null,
          failed: model.failed,
        });
      },
    },
    { number: 81 },
  );
  await controller.start();
  await settle();
  while (gets < 3 && timers.length > 0) {
    timers.sort((a, b) => a.at - b.at);
    const next = timers[0];
    timers = timers.slice(1);
    now = next.at;
    next.callback();
    await settle();
  }
  controller.dispose();
  return rendered;
}

/** A read asked for while one is on its way waits for it: one loop, one timer. */
async function oneLoop(page, current) {
  let gets = 0;
  const waiting = [];
  const timers = new Map();
  let next = 0;
  const controller = page.createStackController(
    {
      request(method) {
        if (method === "POST") {
          return Promise.resolve({ status: 202, etag: null, body: {} });
        }
        gets += 1;
        return new Promise((resolve) =>
          waiting.push(() => resolve({ status: 200, etag: '"c"', body: current })),
        );
      },
      schedule(callback) {
        next += 1;
        timers.set(next, callback);
        return next;
      },
      cancel(id) {
        timers.delete(id);
      },
      now: () => START,
      isVisible: () => true,
      render() {},
    },
    { number: 70 },
  );
  void controller.start();
  void controller.start(); // the page coming back into sight while the first read is out
  await settle();
  const during = { gets, timers: timers.size };
  for (const answer of waiting.splice(0)) {
    answer();
  }
  await settle();
  const afterFirst = { gets, timers: timers.size };
  for (const answer of waiting.splice(0)) {
    answer();
  }
  await settle();
  const afterSecond = { gets, timers: timers.size };
  controller.dispose();
  return { during, after_first: afterFirst, after_second: afterSecond };
}

/**
 * The body and its notices over a reader who follows a link to one file in Changes while
 * the stack moves under them: each step's answer, what the body does, and what the
 * notices above it say.
 */
function bodySession(page, pending, current, lacking, notLinear) {
  const steps = [];
  let body = page.NO_BODY;
  let tab = "changes";
  let failed = [];
  let envelope = null;
  const record = (step, action) => {
    steps.push({
      step,
      do: action.do === "mount" ? `mount ${action.tab}` : action.do,
      ...(action.file ? { file: action.file } : {}),
      ...(action.text ? { text: action.text } : {}),
      ...(action.retry ? { retry: true } : {}),
      drawn: body.drawn === current.comparison ? "current" : body.drawn ? "other" : null,
      notices: page
        .statusNotices(envelope, body.drawn?.key ?? null, null, failed)
        .map((notice) => `${notice.text}${notice.action ? ` [${notice.action}]` : ""}`),
    });
  };
  const plan = (step) => {
    const planned = page.bodyPlan(body, envelope, tab, failed);
    body = planned.body;
    record(step, planned.action);
    if (planned.action.do === "mount") {
      const mounted = page.bodyMounted(body, planned.action.key);
      body = mounted.body;
      if (mounted.scroll !== null) {
        record(`${step}, mounted`, { do: "scroll", file: mounted.scroll });
      }
    }
  };
  const answer = (step, next) => {
    envelope = next;
    body = page.bodyAnswered(body, envelope);
    plan(step);
  };

  // A link to /stack/70/changes/docs/draft.md, before the stack is read.
  body = page.bodyOpened(body, "docs/draft.md");
  plan("opened a file, nothing read");
  answer("pending", pending);
  answer("current", current);
  // The top member's record moved on (its checks), so the answer is new, and the same
  // comparison: the reader stays where they scrolled.
  answer("current again, top revision moved", {
    ...current,
    probe: { ...current.probe, held: "f".repeat(64) },
  });
  body = page.bodyOpened(body, "docs/draft.md");
  plan("the reader opens the file again");
  // A member is added on top: pending until its record arrives, the drawn one kept.
  const grown = {
    ...pending,
    members: [...current.members, { ...pending.members[1], number: 11, place: 3 }],
    pending: [11],
  };
  answer("a member added on top, pending", grown);
  failed = [11];
  answer("its fetch failed", grown);
  failed = [];
  answer("it arrived: another comparison", lacking);
  body = page.bodyTaken(body, envelope);
  plan("the reader takes it");
  answer("the stack can no longer be shown as one", notLinear);
  tab = "docs";
  body = page.bodyOpened(body, "");
  plan("the reader opens Docs");

  // With nothing drawn yet, the body says why.
  body = page.NO_BODY;
  tab = "changes";
  failed = [10];
  answer("nothing drawn, a member's fetch failed", pending);
  failed = [];
  answer("nothing drawn, not linear", notLinear);
  return steps;
}

/**
 * The front page of a stack with a guide while the stack moves: the guide shown after each
 * answer (`guideShown`), the tab, and what the body does. A member's push keeps Guided
 * Review and its guide while the member is fetched, and the guide mounts again only when
 * the reader takes the comparison offered; a description that no longer carries the guide
 * takes the tab away.
 */
function guidedSession(page, pending, current, lacking, notLinear) {
  const steps = [];
  let body = page.NO_BODY;
  let guide = null;
  let envelope = null;
  const step = (name, next, take = false) => {
    envelope = next;
    guide = page.guideShown(guide, envelope);
    const tab = page.shownTab("", envelope, guide);
    body = take ? page.bodyTaken(body, envelope) : page.bodyAnswered(body, envelope);
    const planned = page.bodyPlan(body, envelope, tab, []);
    body = planned.body;
    if (planned.action.do === "mount") {
      body = page.bodyMounted(body, planned.action.key).body;
    }
    steps.push({
      step: name,
      guide: guide === null ? null : `#${guide.number}`,
      tab,
      do: planned.action.do === "mount" ? `mount ${planned.action.tab}` : planned.action.do,
      drawn: body.drawn === current.comparison ? "current" : body.drawn ? "other" : null,
    });
  };
  step("before any answer", null);
  step("current", current);
  step("a member's push, fetched", pending);
  step("current again, another comparison", lacking);
  step("the reader takes it", lacking, true);
  step("the stack cannot be shown", notLinear);
  step("the guide's block removed", { ...lacking, guide: null });
  return steps;
}

async function main() {
  const page = await import(pathToFileURL(pagePath).href);
  const { pending, current, lacking } = recorded;
  const notLinear = recorded.not_linear;

  // The tab each route shows for a stack whose top carries its guide (70's), for one with
  // no guide, and before the stack is read.
  const unguided = { ...current, guide: null };
  const routes = ["", "guided", "files", "docs", "changes", "conversation"];
  const tabs = Object.fromEntries(
    [
      ["guided", current],
      ["unguided", unguided],
      ["unread", null],
    ].map(([name, envelope]) => [
      name,
      Object.fromEntries(
        routes.map((tab) => [
          tab || "(front)",
          page.shownTab(tab, envelope, page.guideShown(null, envelope)),
        ]),
      ),
    ]),
  );
  const guided = guidedSession(page, pending, current, lacking, notLinear);

  const comparison = [
    ["nothing drawn, pending", page.comparisonAction(null, pending)],
    ["nothing drawn, current", page.comparisonAction(null, current)],
    ["drawn, the same answer", page.comparisonAction(current.comparison.key, current)],
    ["drawn, another comparison", page.comparisonAction(current.comparison.key, lacking)],
    ["drawn, the stack now absent", page.comparisonAction(current.comparison.key, notLinear)],
  ];

  // The header from the page's first paint, when the Pulls tab knows the stack and its lists
  // titled and stated its members, through each answer, and for a stack the Pulls tab does
  // not know. Its rows stay those of the first paint; only the status line comes and goes.
  const known = {
    number: 70,
    base_ref: current.base_ref,
    open: true,
    pulls: current.members.map((member) => member.number),
    titles: current.members.map((member) => member.title),
  };
  const listed = (number) => (number === 8 ? { state: "merged", title: null } : null);
  const unlisted = () => null;
  const headerAt = (envelope, from, drawn, failedNow = []) => {
    const model = page.stackHeader(
      70,
      envelope,
      from,
      from === null ? unlisted : listed,
      page.statusNotices(
        envelope,
        drawn ? (envelope?.comparison?.key ?? null) : null,
        null,
        failedNow,
      ),
      drawn,
    );
    return {
      cold: model.cold,
      rows: model.rows.join(", "),
      members:
        model.members?.map(
          (member) =>
            `${member.state ?? "(unknown)"} ${member.title ?? "(untitled)"} ${member.place} · #${member.number}`,
        ) ?? null,
      merge: model.merge === null ? null : `${model.merge.head} → ${model.merge.base}`,
      status: model.status.map((notice) => notice.text),
      comparison: model.comparison,
    };
  };
  const header = {
    first_paint: headerAt(null, known, false),
    pending: headerAt(pending, known, false),
    current: headerAt(current, known, true),
    lacking: headerAt(lacking, known, true),
    unknown_first_paint: headerAt(null, null, false),
    unknown_not_linear: headerAt(notLinear, null, false),
  };

  // What the page passes the diff view: for the header's Diff summary, the comparison read
  // and where a file opens, so it starts collapsed with no layer marks; for Docs and Changes,
  // a pull request's drawings, with no summary of their own and the first screen's hold.
  const signal = new AbortController().signal;
  const opens = () => {};
  const shapeOf = (ctx) =>
    Object.fromEntries(
      Object.entries(ctx)
        .filter(([name]) => !["comparisonSignal", "raw"].includes(name))
        .map(([name, value]) => [name, typeof value === "function" ? "function" : value]),
    );
  const drawing = {
    summary: shapeOf(page.summaryDrawing({}, opens)),
    docs: shapeOf(page.diffDrawing("docs", current.comparison, { signal, onDocument: opens })),
    changes: shapeOf(
      page.diffDrawing("changes", current.comparison, {
        signal,
        raw: {},
        types: null,
        onTypes: opens,
      }),
    ),
  };

  const said = {
    lacking: page.lackingText(lacking),
    lacking_none: page.lackingText(current),
    two_lacking: page.lackingText({ ...lacking, lacking: [7, 9] }),
    not_linear: page.absentText(notLinear.reason),
    unknown: page.absentText("something_new"),
  };

  const delays = {
    pending_visible: page.pollDelay(pending, true, true),
    pending_none_asked: page.pollDelay(pending, true, false),
    current_visible: page.pollDelay(current, true),
    current_hidden: page.pollDelay(current, false),
  };

  const { sent, rendered } = await scriptedPoll(page, pending, current, lacking);
  const recovery = await recovering(page, current);
  const cold = await coldStack(page, pending);
  const one_loop = await oneLoop(page, current);
  const absent_ask = await absentAsk(page, notLinear);
  const ended_race = await endedRace(page, pending);
  const body = bodySession(page, pending, current, lacking, notLinear);

  // The header lists the members top first, as every stack menu does.
  const order = page.topFirst(lacking).map((member) => member.number);

  process.stdout.write(
    `${JSON.stringify(
      {
        tabs,
        guided,
        comparison,
        header,
        drawing,
        said,
        delays,
        sent,
        rendered,
        recovery,
        cold,
        one_loop,
        absent_ask,
        ended_race,
        body,
        order,
      },
      null,
      2,
    )}\n`,
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
