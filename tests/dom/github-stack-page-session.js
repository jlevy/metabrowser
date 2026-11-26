// Browserless session: a native stack's page, its front tab, its asks, and its body.
//
// The answers are the stack route's for the GitHub stand-in's stacks, recorded in
// tests/fixtures/github-stack-responses.json by tests/test_cli_github_stack_golden.py, which
// fails when the recording drifts: stack 70 pending before its members' records, then
// current; 71, whose top lacks 7, which has another comparison; 72, not linear; 70 once 8
// left it, asked `since` its earlier comparison; and 74, whose one member, 7, is rewritten
// and then gains a commit, each asked `since` the comparison before.
//
// It runs the production builtin_plugins/github/stack-page.js: the tab a route shows, the
// header's rows from its first paint to the answer (`stackHeader`), what the page passes the
// diff view for its Diff summary and its Docs and Changes, what a new answer does to the
// comparison drawn (`answerAction`) and what its notice says (`changeText`), which keys are
// the reader's move on the page (`readerKey`), the line about members the top lacks, and the
// controller (`createStackController`) over a
// scripted poll, over a read that fails and then finds its answer current, over a cold
// stack of more members than the server fetches at once, one of whose fetches fails, over
// a read asked for while one is on its way, over a fetch that ends once the stack is no
// longer linear, and over an answer read as a fetch ended before its record. Then the
// body's state machine (`bodyPlan` and its events), the column it is set in
// (`bodyInColumn`), and the notices above it (`statusNotices`) over a reader who opens a
// file while the stack moves, over a reader who has not yet done anything on the page and
// then does, and over a reader on whose page a member's record catches up and another member
// then gains commits. What is left to
// the glue (`mountStackPage`) is the drawing, which github-stack-guide-mount-session.js
// mounts.

const assert = require("node:assert/strict");
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
    // Asked `since` 70's comparison, which the server keeps: nothing moved in a member both
    // hold, so the notice of it would name none.
    {
      status: 200,
      etag: '"moved"',
      body: { ...lacking, moved: { since: current.comparison.key, members: [] } },
    },
  ];
  const sent = [];
  const rendered = [];
  /** @type {Array<() => void>} */
  const timers = [];
  let now = START;
  let body = page.NO_BODY;
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
      // The comparison drawn, which each read after it is asked `since`.
      since: () => body.drawn?.key ?? null,
      render(model) {
        const action = page.answerAction(body, model.envelope, false, model.failed);
        body = page.bodyAnswered(body, model.envelope, false, model.failed);
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
      since: () => null,
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
      since: () => null,
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
      since: () => null,
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
      since: () => null,
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
      since: () => null,
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
 * notices above it say. The reader opened a file, so a comparison that looks different is
 * offered, never drawn under them.
 */
function bodySession(page, pending, current, notLinear, left) {
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
      // The body's column, a pull request's (`bodyInColumn`): the reading column but for a
      // drawn Docs or Changes.
      column: page.bodyInColumn(body, tab) ? "reading" : "full pane",
      notices: page
        .statusNotices(envelope, body, null, failed, true)
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
    body = page.bodyAnswered(body, envelope, true, failed);
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
  answer("8 leaves instead: another comparison, offered", left);
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
 * A reader on Changes of 70 while the stack moves. One that looks the same (71's answer,
 * standing in for 70 gaining 7, asked `since` 70's) is no change, before the reader does
 * anything on the page or after: the comparison drawn stays, and the next read is asked
 * `since` it. One that looks different (70 once 8 left it) is drawn without a word before the
 * reader's move; after it, it is held while a member it waits on is fetched, then offered
 * with what changed, and drawn when the reader takes it. When the server no longer keeps
 * the comparison drawn, its answer has no `moved`: one that looks the same is drawn in its
 * place without a word, and one that looks different is offered at once, though a member it
 * waits on is fetched. Each step records what the body does, the comparison it draws, the
 * notices above it, and the key the next read is asked `since`.
 */
function noticeSession(page, current, lacking, left) {
  const named = new Map([
    [current.comparison.key, "70"],
    [lacking.comparison.key, "71"],
    [left.comparison.key, "70 without 8"],
  ]);
  const since = (envelope, drawn) => ({
    ...envelope,
    moved: { since: drawn.comparison.key, members: [] },
  });
  const steps = [];
  let body = page.NO_BODY;
  let interacted = false;
  let envelope = null;
  const plan = (step) => {
    const planned = page.bodyPlan(body, envelope, "changes", []);
    body = planned.body;
    if (planned.action.do === "mount") {
      body = page.bodyMounted(body, planned.action.key).body;
    }
    steps.push({
      step,
      do: planned.action.do === "mount" ? `mount ${planned.action.tab}` : planned.action.do,
      drawn: body.drawn === null ? null : (named.get(body.drawn.key) ?? "another"),
      notices: page
        .statusNotices(envelope, body, null, [], interacted)
        .map((notice) => `${notice.text}${notice.action ? ` [${notice.action}]` : ""}`),
      since: body.drawn === null ? null : (named.get(body.drawn.key) ?? "another"),
    });
  };
  const answer = (step, next) => {
    envelope = next;
    body = page.bodyAnswered(body, envelope, interacted, []);
    plan(step);
  };
  answer("70, drawn", current);
  answer("looks the same, before the reader's move: 70's stays", since(lacking, current));
  answer("looks different, before the reader's move: drawn at once", since(left, current));

  body = page.NO_BODY;
  answer("70 again, drawn", current);
  interacted = true;
  answer("looks the same, after the reader scrolls: 70's stays", since(lacking, current));
  answer("70's again", current);
  answer("looks different while 10 is fetched: held", { ...since(left, current), pending: [10] });
  answer("looks different, 10 fetched: offered", since(left, current));
  body = page.bodyTaken(body, envelope);
  plan("the reader takes it");

  // The server no longer keeps the comparison drawn.
  body = page.NO_BODY;
  answer("70 once more, drawn", current);
  answer("looks the same, 70's gone: drawn in its place", { ...lacking, moved: null });
  body = page.NO_BODY;
  answer("70 drawn again", current);
  answer("looks different while 10 is fetched, 70's gone: offered", {
    ...left,
    pending: [10],
    moved: null,
  });
  body = page.bodyTaken(body, envelope);
  plan("the reader takes it, 70's gone");
  return steps;
}

/**
 * A reader on Changes of 70 whose page draws a comparison, then scrolls: 8's record catches
 * up to a head the comparison drawn already shows, so the answer looks the same and its
 * `moved` counts no commit for 8; then 10 gains two commits. The notice names 10 alone,
 * since 8's caught-up head was the answer the drawn comparison stayed through.
 */
function caughtUpSession(page, current) {
  const drawnKey = current.comparison.key;
  const caught = {
    ...current,
    comparison: { ...current.comparison, key: "c".repeat(32) },
    members: current.members.map((member) =>
      member.number === 8 ? { ...member, head: "8".repeat(40) } : member,
    ),
    moved: { since: drawnKey, members: [{ number: 8, commits: 0 }] },
  };
  const grew = {
    ...caught,
    comparison: { ...caught.comparison, key: "d".repeat(32), right: "a".repeat(40) },
    members: caught.members.map((member) =>
      member.number === 10 ? { ...member, head: "a".repeat(40) } : member,
    ),
    moved: {
      since: drawnKey,
      members: [
        { number: 8, commits: 0 },
        { number: 10, commits: 2 },
      ],
    },
  };
  const steps = [];
  let body = page.NO_BODY;
  let interacted = false;
  const answer = (step, envelope) => {
    const action = page.answerAction(body, envelope, interacted, []);
    body = page.bodyAnswered(body, envelope, interacted, []);
    steps.push({
      step,
      action,
      drawn: body.drawn?.key === drawnKey ? "70" : "another",
      notices: page
        .statusNotices(envelope, body, null, [], interacted)
        .map((notice) => `${notice.text}${notice.action ? ` [${notice.action}]` : ""}`),
    });
  };
  answer("70, drawn", current);
  answer("8's record catches up, looks the same: kept", caught);
  interacted = true;
  answer("the reader scrolls; 10 gains two commits: offered", grew);
  return steps;
}

/**
 * The front page of a stack with a guide while the stack moves, after the reader has moved
 * on the page: the guide shown after each answer (`guideShown`), the tab, and what the body
 * does. A member's push keeps Guided Review and its guide while the member is fetched, and
 * the guide mounts again only when the reader takes the comparison offered; a description
 * that no longer carries the guide takes the tab away.
 */
function guidedSession(page, pending, current, notLinear, left) {
  const steps = [];
  let body = page.NO_BODY;
  let guide = null;
  let envelope = null;
  const step = (name, next, take = false) => {
    envelope = next;
    guide = page.guideShown(guide, envelope);
    const tab = page.shownTab("", envelope, guide);
    body = take ? page.bodyTaken(body, envelope) : page.bodyAnswered(body, envelope, true, []);
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
      column: page.bodyInColumn(body, tab) ? "reading" : "full pane",
    });
  };
  step("before any answer", null);
  step("current", current);
  step("a member's push, fetched", pending);
  step("current again, another comparison", left);
  step("the reader takes it", left, true);
  step("the stack cannot be shown", notLinear);
  step("the guide's block removed", { ...left, guide: null });
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
  const guided = guidedSession(page, pending, current, notLinear, recorded.left);

  // What a new answer does to the comparison drawn, before the reader does anything on the
  // page and after: 71's answer looks as 70's does, and 70's once 8 left it does not.
  const { left, rewritten, grown } = recorded;
  const at = (envelope) => ({ ...page.NO_BODY, drawn: envelope.comparison, answer: envelope });
  const waiting = { ...left, pending: [10] };
  // An answer asked `since` the comparison drawn, which the server keeps, says how each
  // member moved from it; one without `moved` says the server no longer keeps it.
  const kept = (envelope) => ({
    ...envelope,
    moved: { since: current.comparison.key, members: [] },
  });
  const comparison = [
    ["nothing drawn, pending", page.answerAction(page.NO_BODY, pending, false, [])],
    ["nothing drawn, current", page.answerAction(page.NO_BODY, current, false, [])],
    ["drawn, the same answer", page.answerAction(at(current), current, true, [])],
    ["drawn, the stack now absent", page.answerAction(at(current), notLinear, true, [])],
    ["drawn, another that looks the same", page.answerAction(at(current), kept(lacking), true, [])],
    ["drawn, another that looks the same, gone", page.answerAction(at(current), lacking, true, [])],
    ["drawn, another, before the reader's move", page.answerAction(at(current), left, false, [])],
    ["drawn, another, after the reader's move", page.answerAction(at(current), left, true, [])],
    ["drawn, another, while 10 is fetched", page.answerAction(at(current), waiting, true, [])],
    ["drawn, another, once 10's fetch failed", page.answerAction(at(current), waiting, true, [10])],
    [
      "drawn, another, while 10 is fetched, gone",
      page.answerAction(at(current), { ...waiting, moved: null }, true, []),
    ],
  ];
  // Whether Guided Review reads an edit of its guide at the comparison drawn: the stack's
  // own, or one that looks the same, is current; another is not; none to say, null.
  const guide_current = [
    ["nothing drawn", page.drawnCurrent(page.NO_BODY, current)],
    ["the same answer", page.drawnCurrent(at(current), current)],
    ["another that looks the same", page.drawnCurrent(at(current), kept(lacking))],
    ["another", page.drawnCurrent(at(current), left)],
    ["the stack now absent", page.drawnCurrent(at(current), notLinear)],
  ];

  // What the notice of a new comparison says. 71's top member moves, two members join, and
  // 7 is closed, as one answer: the notice names three changes, or two and counts the rest.
  const moved = {
    ...lacking,
    members: [
      { ...lacking.members[0], place: 1 },
      { ...lacking.members[1], state: "closed" },
      { ...lacking.members[2], head: "f".repeat(40) },
      { ...lacking.members[2], number: 11, place: 4 },
      { ...lacking.members[2], number: 12, place: 5 },
    ],
    moved: { since: lacking.comparison.key, members: [{ number: 10, commits: 2 }] },
  };
  const changes = {
    left: page.changeText(current, left),
    joined: page.changeText(left, current),
    one_new_commit: page.changeText(rewritten, grown),
    rewritten: page.changeText(grown, rewritten),
    not_asked_since: page.changeText(rewritten, { ...grown, moved: null }),
    // 7's new head is one the comparison drawn shows: its record caught up.
    caught_up: page.changeText(rewritten, {
      ...grown,
      moved: { ...grown.moved, members: [{ number: 7, commits: 0 }] },
    }),
    three: page.changeText(lacking, { ...moved, members: moved.members.slice(0, 4) }),
    four: page.changeText(lacking, moved),
    reordered: page.changeText(lacking, {
      ...lacking,
      members: [...lacking.members].reverse(),
    }),
    nothing_named: page.changeText(current, {
      ...current,
      comparison: { ...current.comparison, key: "0".repeat(32) },
    }),
  };
  const notices = noticeSession(page, current, lacking, left);
  const caught_up = caughtUpSession(page, current);

  // Which keys the document hears are the reader's move on the page (`readerKey`): one with
  // focus in the page or on nothing in particular, but for a modifier pressed alone, which
  // may begin a chord that leaves the page. A node is a name here; the page contains those
  // whose name begins with "page".
  const pageNode = { contains: (node) => typeof node === "string" && node.startsWith("page") };
  const doc = { body: "body", documentElement: "root" };
  const reader_keys = [
    ["j in the page", { key: "j", target: "page file list" }],
    ["Enter on the page's link", { key: "Enter", target: "page link" }],
    ["j on the body", { key: "j", target: "body" }],
    ["Escape on the root", { key: "Escape", target: "root" }],
    ["a in the shell's search field", { key: "a", target: "search field" }],
    ["Meta alone in the page", { key: "Meta", target: "page file list" }],
    ["Shift alone on the body", { key: "Shift", target: "body" }],
    ["Control alone on the body", { key: "Control", target: "body" }],
    ["Alt alone on the body", { key: "Alt", target: "body" }],
  ].map(([name, event]) => [name, page.readerKey(event, pageNode, doc)]);

  // The header from the page's first paint, when the Pulls tab knows the stack and its lists
  // titled and stated its members, through each answer, and for a stack the Pulls tab does
  // not know. Its rows stay those of the first paint; only the status line comes and goes.
  // A member's author is the answer's once it names one, its record's, and before that the
  // stacks route's: that route read 8's author with its title and holds none for 10, so at
  // first paint 8's row ends in its author and 10's in its number, and the answer names 10's.
  // Its labels are the stacks route's too: it read 8's and none of 10's, so the labels row is
  // held until the answer says them all.
  const known = {
    number: 70,
    base_ref: current.base_ref,
    open: true,
    pulls: current.members.map((member) => member.number),
    titles: current.members.map((member) => member.title),
    authors: current.members.map((member) => (member.number === 8 ? "maintainer" : null)),
    avatars: current.members.map(() => null),
    labels: current.members.map((member) => (member.number === 8 ? ["bugfix"] : null)),
  };
  // The stacks route read both members' labels: the row is decided at first paint, by name
  // alone, and colored once the answer says them. A stack whose members carry none has no
  // labels row from first paint, and the answer that says none moves nothing.
  const knownLabelled = {
    ...known,
    labels: current.members.map((member) =>
      member.number === 8 ? ["bugfix", "shared design"] : ["earnings analysis", "bugfix"],
    ),
  };
  const knownBare = { ...known, labels: current.members.map(() => []) };
  const bare = { ...current, labels: [] };
  // The Pulls tab's lists read 8, merged.
  const listed = (number) => (number === 8 ? { state: "merged", title: null } : null);
  const unlisted = () => null;
  const headerAt = (envelope, from, drawn, failedNow = [], offline = false) => {
    const model = page.stackHeader(
      envelope,
      from,
      from === null ? unlisted : listed,
      page.statusNotices(
        envelope,
        drawn ? { ...page.NO_BODY, drawn: envelope.comparison, answer: envelope } : page.NO_BODY,
        null,
        failedNow,
        true,
      ),
      drawn,
      // Five minutes after the members' records were fetched.
      Date.parse("2026-09-17T12:05:00Z"),
      offline,
    );
    return {
      cold: model.cold,
      rows: model.rows.join(", "),
      tally: model.tally.map((badge) => `${badge.state}: ${badge.label}`),
      ages: model.ages,
      sentence:
        model.sentence === null
          ? null
          : `${model.sentence.actors.map((actor) => actor.login).join(", ")} ${model.sentence.action}`.trim(),
      note: model.note,
      labels:
        model.labels?.map(
          (label) => `${label.name}${label.color === null ? "" : ` #${label.color}`}`,
        ) ?? null,
      members:
        model.members?.map(
          (member) =>
            `${member.state ?? "(unknown)"} ${member.title ?? "(untitled)"} ${member.place} · #${member.number}${member.author === null ? "" : ` · ${member.author.login}`}`,
        ) ?? null,
      merge: model.merge === null ? null : `${model.merge.head} → ${model.merge.base}`,
      status: model.status.map((notice) => notice.text),
      comparison: model.comparison,
    };
  };
  // A stack whose members are all merged names who merged them, each once, as a merged pull
  // request's sentence names its merger; one with two authors names both, each once.
  const allMerged = {
    ...current,
    states: { open: 0, draft: 0, merged: 2, closed: 0 },
    mergers: [{ login: "octo", avatar: null }],
  };
  const twoAuthors = {
    ...current,
    authors: [...current.authors, { login: "forker", avatar: null }],
  };
  // Every member merged and no merger known, as list rows alone leave it: the action alone,
  // crediting no one, as a pull request's record that names no merger says it.
  const mergedByNoOne = { ...allMerged, mergers: [] };
  const sentences = {
    all_merged: page.stackSentence(allMerged),
    all_merged_no_merger: page.stackSentence(mergedByNoOne),
    two_authors: page.stackSentence(twoAuthors),
    no_commits_counted: page.stackSentence({ ...current, commits: null }),
    no_members: page.stackSentence({ ...current, members: [] }),
    no_authors: page.stackSentence({ ...current, authors: [] }),
  };
  // The tally counts the states in the order a stack's members run from its top: drafts,
  // open ones, merged ones, and closed ones.
  const tallyOrder = page
    .stateTally({ ...current, states: { open: 2, draft: 5, merged: 2, closed: 1 } })
    .map((badge) => badge.label);
  // The size line's counts for the comparison drawn: the answer's commits and sizes, each
  // left out while not known, and the files the Diff summary counts.
  const sizeInputs = {
    current: page.stackSizeInput(current, 1),
    sized: page.stackSizeInput({ ...current, size: { pushed_bytes: 380, diff_bytes: 741 } }, 1),
    pending: page.stackSizeInput(pending, null),
    none: page.stackSizeInput(null, null),
  };
  const header = {
    first_paint: headerAt(null, known, false),
    pending: headerAt(pending, known, false),
    current: headerAt(current, known, true),
    lacking: headerAt(lacking, known, true),
    unknown_first_paint: headerAt(null, null, false),
    unknown_not_linear: headerAt(notLinear, null, false),
    labelled_first_paint: headerAt(null, knownLabelled, false),
    bare_first_paint: headerAt(null, knownBare, false),
    bare_current: headerAt(bare, knownBare, true),
    held_labels_answered_bare: headerAt(bare, known, true),
    // Offline, a member's record behind and no refresh can run: the note says so, as a pull
    // request's does; with none behind it is the plain age.
    offline_behind: headerAt({ ...current, pending: [10] }, known, true, [], true),
    offline_current: headerAt(current, known, true, [], true),
  };

  // What the page passes the diff view for Docs and Changes: a pull request's drawings
  // (diff-drawing.js), each of their values the shared drawing's, with no summary of their
  // own and the first screen's Markdown held as a pull request's page holds it. What is the
  // stack's own, its comparison and Docs' word for none, is printed.
  const drawings = await import(
    pathToFileURL(path.join(path.dirname(pagePath), "diff-drawing.js")).href
  );
  const { CHANGES_FIRST_SCREEN_MS } = await import(
    pathToFileURL(path.join(path.dirname(pagePath), "pull-page.js")).href
  );
  const signal = new AbortController().signal;
  const opens = () => {};
  const raw = {};
  const drawn = (tab, using, shared) => {
    const ctx = page.diffDrawing(tab, current.comparison, using);
    for (const [name, value] of Object.entries(shared)) {
      assert.deepEqual(ctx[name], value, `${tab}: ${name} is the shared drawing's`);
    }
    assert.equal(ctx.summary, false, `${tab}: the diff draws no summary of its own`);
    assert.equal(ctx.markdownHoldMs, CHANGES_FIRST_SCREEN_MS, `${tab}: the first screen's hold`);
    assert.equal(ctx.comparisonSignal, signal, `${tab}: the page's signal`);
    return ctx;
  };
  const docs = drawn(
    "docs",
    { signal, onDocument: opens },
    { ...drawings.DOCS_DRAWING, group: drawings.DOCS_GROUP, onDocument: opens },
  );
  const changesTab = drawn(
    "changes",
    { signal, raw, types: null, onTypes: opens },
    { ...drawings.CHANGES_DRAWING, raw, types: null, onTypes: opens },
  );
  assert.deepEqual(changesTab.comparison, docs.comparison, "Docs and Changes draw one comparison");
  const drawing = { comparison: docs.comparison, docs_empty: docs.emptyText };

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
  const body = bodySession(page, pending, current, notLinear, left);

  // The header lists the members top first, as every stack menu does.
  const order = page.topFirst(lacking).map((member) => member.number);

  process.stdout.write(
    `${JSON.stringify(
      {
        tabs,
        guided,
        comparison,
        guide_current,
        changes,
        notices,
        caught_up,
        reader_keys,
        header,
        sentences,
        tally_order: tallyOrder,
        size_inputs: sizeInputs,
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
