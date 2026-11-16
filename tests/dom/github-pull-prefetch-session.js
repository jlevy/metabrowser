// Browserless session: Files changed fetched from Conversation, through the production module.
//
// builtin_plugins/github/comparison-prefetch.js loads whole. A scripted page asks it what the
// pull-request page asks: `want` on every paint of the Conversation tab, `take` when a diff
// mounts, `dispose` when the page goes. Each step prints what it has sent, what it holds, what
// a mount would be handed, and which answers it has told the page of, for the page's Diff
// summary (`summarized`, mb-pb35), and which failed reads, so the summary's placeholder does
// not outlive its wait (`failedTold`, mb-onr2). It asserts, and so prints nothing for, that a
// poll changes nothing and that a disposed prefetch does nothing.
//
// Each scripted page has a keep of its own unless a step shares one, as the pages of one
// document share `documentComparisons`: then a second visit to a comparison is drawn from the
// keep with no request (mb-neg9). The Pulls tab's warmer runs against the same keep, its
// record reads and comparison requests printed as they are made.

const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const first = { left: "aaaa", right: "bbbb" };
const moved = { left: "aaaa", right: "cccc" };

async function main() {
  const prefetchModule = await import(
    pathToFileURL(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/github/comparison-prefetch.js"),
    ).href
  );
  const { createComparisonKeep, createComparisonPrefetch, createComparisonWarmer } = prefetchModule;

  /** A keep whose answers are measured at once, so a step needs no task to pass. */
  const keepNow = (options = {}) =>
    createComparisonKeep({ later: (callback) => callback(), ...options });

  function page({ visible = true, keep = keepNow() } = {}) {
    const requests = [];
    const scheduled = [];
    let warmed = 0;
    const summarized = [];
    const failedTold = [];
    const state = { visible };
    const prefetch = createComparisonPrefetch({
      keep,
      load(comparison, signal) {
        return new Promise((resolve, reject) => {
          const request = {
            comparison: comparison.right,
            signal,
            resolve,
            reject: () => reject(new Error("refused")),
          };
          requests.push(request);
          signal.addEventListener("abort", () => reject(new DOMException("gone", "AbortError")));
        });
      },
      warm() {
        warmed += 1;
      },
      loaded(comparison) {
        summarized.push(comparison.right);
      },
      failed(comparison) {
        failedTold.push(comparison.right);
      },
      schedule(callback) {
        const handle = { callback, cancelled: false };
        scheduled.push(handle);
        return handle;
      },
      cancel(handle) {
        handle.cancelled = true;
      },
      isVisible: () => state.visible,
    });
    return {
      prefetch,
      state,
      requests,
      failedTold,
      /** How many idle callbacks the page is waiting on. */
      waiting: () => scheduled.filter((handle) => !handle.cancelled).length,
      idle() {
        for (const handle of scheduled.splice(0)) {
          if (!handle.cancelled) {
            handle.callback();
          }
        }
      },
      line() {
        return {
          ...prefetch.snapshot(),
          requests: requests.map(
            (request) => `${request.comparison}${request.signal.aborted ? " (cancelled)" : ""}`,
          ),
          assetsWarmed: warmed,
          summarized: [...summarized],
          failedTold: [...failedTold],
        };
      },
    };
  }

  const steps = [];
  const say = (name, shown, extra = {}) => steps.push({ step: name, ...shown.line(), ...extra });
  const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

  const reader = page();
  reader.prefetch.want(first);
  say("the record names a comparison: nothing is sent until the browser is idle", reader);
  reader.idle();
  say("idle: one request, and the diff's assets", reader);
  for (let poll = 0; poll < 5; poll += 1) {
    reader.prefetch.want(first);
  }
  reader.idle();
  assert(reader.requests.length === 1, "a poll of the same record sent another request");
  reader.requests[0].resolve({ document: "first" });
  await tick();
  say("the answer arrives and is held", reader);
  const handed = await reader.prefetch.take(first);
  say("the reader clicks Files changed: it is handed over", reader, { handed });
  const again = await reader.prefetch.take(first);
  say("a later mount is handed it again, from the keep, with no request", reader, {
    handed: again ?? null,
  });
  reader.prefetch.want(first);
  reader.idle();
  say("back on Conversation: nothing more is sent for that comparison", reader);

  const quick = page();
  quick.prefetch.want(first);
  quick.idle();
  const waited = quick.prefetch.take(first);
  say("a click while the request is on its way waits for that request", quick);
  quick.requests[0].resolve({ document: "first" });
  say("it arrives", quick, { handed: await waited });

  const beforeIdle = page();
  beforeIdle.prefetch.want(first);
  const clicked = beforeIdle.prefetch.take(first);
  beforeIdle.idle();
  say(
    "a click before the browser was idle: the comparison is read now, through the keep, and only once",
    beforeIdle,
  );
  beforeIdle.requests[0].resolve({ document: "first" });
  say("it arrives and the diff is handed it", beforeIdle, { handed: await clicked });

  const direct = page();
  const directTaken = direct.prefetch.take(first);
  direct.prefetch.want(first);
  direct.idle();
  say(
    "a page opened on Changes reads its comparison through the keep, and a later Conversation sends nothing more",
    direct,
  );
  direct.requests[0].resolve({ document: "first" });
  say("it arrives and the diff is handed it", direct, { handed: await directTaken });

  const movedHead = page();
  movedHead.prefetch.want(first);
  movedHead.idle();
  movedHead.prefetch.want(moved);
  say("a refreshed record moved the head: the old request is cancelled", movedHead);
  movedHead.idle();
  say("the new comparison is fetched", movedHead);
  await tick();
  assert(movedHead.failedTold.length === 0, "a cancelled request told the page it failed");

  const waitingOnOld = page();
  waitingOnOld.prefetch.want(first);
  waitingOnOld.idle();
  const stillCounted = waitingOnOld.prefetch.take(first);
  waitingOnOld.prefetch.want(moved);
  say("a mount is waiting on the old request: it is not cancelled", waitingOnOld);
  waitingOnOld.requests[0].resolve({ document: "first" });
  assert((await stillCounted).document === "first", "the waiting mount lost its answer");

  const refused = page();
  refused.prefetch.want(first);
  refused.idle();
  refused.requests[0].reject();
  await tick();
  const fromRefusal = await refused.prefetch.take(first);
  say("a refused request is not retried and not an error: the diff asks and says why", refused, {
    handed: fromRefusal ?? null,
  });

  const takenRefused = page();
  takenRefused.prefetch.want(first);
  takenRefused.idle();
  const takenAnswer = takenRefused.prefetch.take(first);
  takenRefused.requests[0].reject();
  assert((await takenAnswer) === undefined, "a taken request that failed handed something");
  say(
    "a request a mount took fails: the diff asks and says why, and the page is told nothing",
    takenRefused,
  );

  const hidden = page({ visible: false });
  hidden.prefetch.want(first);
  hidden.idle();
  say("a tab in the background sends nothing", hidden);
  hidden.state.visible = true;
  hidden.prefetch.want(first);
  hidden.idle();
  say("the same page once it is shown", hidden);

  const leaving = page();
  leaving.prefetch.want(first);
  leaving.idle();
  leaving.prefetch.dispose();
  say("the page goes: its request is cancelled and nothing is held", leaving);
  await tick();
  assert(leaving.failedTold.length === 0, "a disposed prefetch told the page a read failed");
  leaving.prefetch.want(moved);
  leaving.idle();
  assert(leaving.requests.length === 1, "a disposed prefetch sent a request");
  assert(
    (await leaving.prefetch.take(first)) === undefined,
    "a disposed prefetch handed something",
  );

  const leavingScheduled = page();
  leavingScheduled.prefetch.want(first);
  leavingScheduled.prefetch.dispose();
  leavingScheduled.idle();
  assert(leavingScheduled.requests.length === 0, "a disposed prefetch started from its timer");

  const leavingWaited = page();
  leavingWaited.prefetch.want(first);
  leavingWaited.idle();
  const pending = leavingWaited.prefetch.take(first);
  leavingWaited.prefetch.dispose();
  assert((await pending) === undefined, "a mount waiting through a dispose was not released");
  assert(leavingWaited.requests[0].signal.aborted, "a dispose left a taken request running");

  const scoped = page();
  const oldRoute = { ...first, route: "/api/plugin/github/pull-comparison?store=old" };
  const newRoute = { ...first, route: "/api/plugin/github/pull-comparison?store=new" };
  scoped.prefetch.want(oldRoute);
  scoped.idle();
  scoped.prefetch.want(newRoute);
  scoped.idle();
  assert(scoped.requests[0].signal.aborted, "a changed comparison route reused the old answer");
  assert(scoped.requests.length === 2, "a changed store did not fetch its own comparison");
  say("the same endpoints at a changed route fetch again", scoped);
  scoped.prefetch.dispose();
  await tick();

  // ── One document's pages share what they read (mb-neg9) ─────────────────────────
  const shared = keepNow();
  const visitA = page({ keep: shared });
  visitA.prefetch.want(first);
  visitA.idle();
  visitA.requests[0].resolve({ document: "first" });
  await tick();
  visitA.prefetch.dispose();
  say("the reader opens a pull request and leaves it: its answer stays in the keep", visitA, {
    kept: shared.snapshot().kept,
  });
  const visitB = page({ keep: shared });
  visitB.prefetch.want(moved);
  visitB.idle();
  say("another pull request's page reads its own comparison", visitB);
  visitB.requests[0].resolve({ document: "moved" });
  await tick();
  visitB.prefetch.dispose();
  const revisit = page({ keep: shared });
  revisit.prefetch.want(first);
  say(
    "the first pull request again: its summary is drawn in the paint that shows the record, with no request and no wait",
    revisit,
    { waitingForIdle: revisit.waiting() },
  );
  assert(revisit.requests.length === 0, "a second visit to a comparison sent a request");
  const handedAgain = await revisit.prefetch.take(first);
  say("its Changes is handed the same answer", revisit, { handed: handedAgain ?? null });
  revisit.prefetch.dispose();

  // A pull request first opened on Changes (a file pressed in the Pulls tab's tree, `G`, or
  // a link): its read went through the keep, so its next visit is drawn from it too.
  const changesFirst = keepNow();
  const openedOnChanges = page({ keep: changesFirst });
  const changesTaken = openedOnChanges.prefetch.take(first);
  openedOnChanges.requests[0].resolve({ document: "first" });
  await changesTaken;
  await tick();
  openedOnChanges.prefetch.dispose();
  const afterChanges = page({ keep: changesFirst });
  afterChanges.prefetch.want(first);
  say(
    "a pull request first opened on Changes, opened again on Conversation: drawn from the keep, with no request and no wait",
    afterChanges,
    { waitingForIdle: afterChanges.waiting(), kept: changesFirst.snapshot().kept },
  );
  assert(afterChanges.requests.length === 0, "a visit after Changes read the comparison again");
  afterChanges.prefetch.dispose();

  const hiddenRevisit = page({ keep: shared, visible: false });
  hiddenRevisit.prefetch.want(moved);
  say("a page behind another tab draws a kept summary too: it costs nothing", hiddenRevisit);
  hiddenRevisit.prefetch.dispose();

  const headMoved = { left: "aaaa", right: "dddd" };
  const afterPush = page({ keep: shared });
  afterPush.prefetch.want(headMoved);
  afterPush.idle();
  say(
    "the head moved: the record names another comparison, which is read, and the old one is not drawn",
    afterPush,
  );
  afterPush.requests[0].resolve({ document: "pushed" });
  await tick();
  afterPush.prefetch.dispose();

  const overlap = keepNow();
  const leavingFirst = page({ keep: overlap });
  leavingFirst.prefetch.want(first);
  leavingFirst.idle();
  const joining = page({ keep: overlap });
  joining.prefetch.want(first);
  say(
    "a second page while the first's request is on its way joins it, and sends nothing",
    joining,
    { firstPageRequests: leavingFirst.requests.length },
  );
  leavingFirst.prefetch.dispose();
  assert(!leavingFirst.requests[0].signal.aborted, "a request another page waits on was cancelled");
  leavingFirst.requests[0].resolve({ document: "first" });
  await tick();
  say("the first page went; the request it shared answers the second", joining);
  joining.prefetch.dispose();

  // Between an answer and its measurement, a task later, the request stands for it: a visit
  // in that window joins it rather than sending its own.
  const measuredLater = createComparisonKeep();
  const answering = page({ keep: measuredLater });
  answering.prefetch.want(first);
  answering.idle();
  answering.requests[0].resolve({ document: "first" });
  await answering.prefetch.take(first);
  const inTheWindow = page({ keep: measuredLater });
  inTheWindow.prefetch.want(first);
  say(
    "an answer arrived and is not yet measured: a visit then joins its request, and sends none",
    inTheWindow,
    { keep: measuredLater.snapshot() },
  );
  assert(inTheWindow.requests.length === 0, "a visit before the measurement sent a request");
  await tick();
  say("a task later it is measured and kept; the visit that joined is drawn from it", inTheWindow, {
    keep: measuredLater.snapshot(),
  });
  answering.prefetch.dispose();
  inTheWindow.prefetch.dispose();

  // A page waiting for idle is taken while a warm of the same comparison is on its way: the
  // mount joins that request, and once the warmer and the page have both gone, no asker is
  // left, so the request is abandoned.
  const abandoned = keepNow();
  const waitingPage = page({ keep: abandoned });
  waitingPage.prefetch.want(first);
  const lonelyLoads = [];
  const lonelyIdle = [];
  const lonely = createComparisonWarmer({
    keep: abandoned,
    read: () => Promise.resolve({ comparison: first, freshForMs: 60_000 }),
    load(_comparison, signal) {
      return new Promise((_resolve, reject) => {
        lonelyLoads.push(signal);
        signal.addEventListener("abort", () => reject(new DOMException("gone", "AbortError")));
      });
    },
    schedule(callback) {
      lonelyIdle.push(callback);
      return callback;
    },
    cancel() {},
    isVisible: () => true,
    now: () => 0,
  });
  lonely.want([5]);
  lonelyIdle.shift()();
  await tick();
  const takenWhileWaiting = waitingPage.prefetch.take(first);
  lonely.dispose();
  waitingPage.prefetch.dispose();
  assert((await takenWhileWaiting) === undefined, "a mount let go of was handed something");
  steps.push({
    step: "a page waiting for idle is taken while a warm of its comparison is on its way; the warmer and the page go: the request is abandoned",
    warmRequests: lonelyLoads.length,
    sharedRequestAborted: lonelyLoads.every((signal) => signal.aborted),
    pending: abandoned.snapshot().pending,
  });
  assert(lonelyLoads[0]?.aborted === true, "a request no asker waits on was left running");

  const bounded = keepNow({ maxChars: 70, entryChars: 40 });
  for (const [index, right] of ["b1", "b2", "b3"].entries()) {
    const visit = page({ keep: bounded });
    visit.prefetch.want({ left: "aaaa", right });
    visit.idle();
    visit.requests[0].resolve({ document: `answer ${index} ${"x".repeat(8)}` });
    await tick();
    visit.prefetch.dispose();
  }
  const oversized = page({ keep: bounded });
  oversized.prefetch.want({ left: "aaaa", right: "big" });
  oversized.idle();
  oversized.requests[0].resolve({ document: "y".repeat(60) });
  await tick();
  oversized.prefetch.dispose();
  steps.push({
    step: "a keep of 70 characters of JSON, 40 for one answer: the oldest answer goes first, and a larger one is not kept",
    keep: bounded.snapshot(),
  });

  // ── The Pulls tab warms what the reader opens next ───────────────────────────────
  const warmKeep = keepNow();
  const records = {
    8: { left: "base8", right: "head8", route: "/api/plugin/github/pull-comparison?number=8" },
    10: { left: "base10", right: "head10", route: "/api/plugin/github/pull-comparison?number=10" },
    11: null,
  };
  const reads = [];
  const loads = [];
  const idleQueue = [];
  let clock = 0;
  const warmer = createComparisonWarmer({
    keep: warmKeep,
    read(number, signal) {
      return new Promise((resolve, reject) => {
        reads.push({
          number,
          signal,
          // The record's freshness window, `fresh_for_s`, as its envelope gives it.
          answer: () => resolve({ comparison: records[number] ?? null, freshForMs: 60_000 }),
        });
        signal.addEventListener("abort", () => reject(new DOMException("gone", "AbortError")));
      });
    },
    load(comparison, signal) {
      return new Promise((resolve, reject) => {
        loads.push({ comparison: comparison.right, signal, resolve });
        signal.addEventListener("abort", () => reject(new DOMException("gone", "AbortError")));
      });
    },
    schedule(callback) {
      const handle = { callback, cancelled: false };
      idleQueue.push(handle);
      return handle;
    },
    cancel(handle) {
      handle.cancelled = true;
    },
    isVisible: () => true,
    now: () => clock,
  });
  const warmIdle = async () => {
    for (const handle of idleQueue.splice(0)) {
      if (!handle.cancelled) {
        handle.callback();
      }
    }
    await tick();
  };
  const warmLine = (step) =>
    steps.push({
      step,
      ...warmer.snapshot(),
      recordReads: reads.map(
        (read) => `${read.number}${read.signal.aborted ? " (cancelled)" : ""}`,
      ),
      comparisonRequests: loads.map(
        (load) => `${load.comparison}${load.signal.aborted ? " (cancelled)" : ""}`,
      ),
      kept: warmKeep.snapshot().kept,
    });
  warmer.want([8, 10, 11, 12, 13, 14]);
  warmLine(
    "the Pulls tab names six pull requests: five are queued, and nothing is read until idle",
  );
  await warmIdle();
  warmLine("idle: the first one's record is read from the cache");
  reads[0].answer();
  await tick();
  warmLine("its record names a comparison the keep lacks: it is asked for");
  loads[0].resolve({ document: "eight" });
  await tick();
  await warmIdle();
  warmLine("it is kept, and at the next idle the second's record is read");
  const eightsPage = page({ keep: warmKeep });
  eightsPage.prefetch.want(records[8]);
  say("the reader opens the first: its page draws the summary with no request", eightsPage);
  assert(eightsPage.requests.length === 0, "a warmed comparison was asked for again");
  eightsPage.prefetch.dispose();
  warmer.want([11, 8]);
  warmLine(
    "the reader rests on another row: the queue is replaced, the one being read goes on, and the kept one is not looked up again",
  );
  reads.at(-1).answer();
  await tick();
  loads.at(-1).resolve({ document: "ten" });
  await tick();
  await warmIdle();
  reads.at(-1).answer();
  await tick();
  await warmIdle();
  warmLine("the one being read is kept, and a record with no comparison is passed over");
  warmer.want([11]);
  warmLine("asked again within the window, the record with no comparison is not read again");
  assert(reads.length === 3, "a record with no comparison was read again within its window");
  clock += 60_000;
  warmer.want([8]);
  await warmIdle();
  reads.at(-1).answer();
  await tick();
  warmLine("past the record's freshness window it is read again, and the keep answers: no request");
  assert(loads.length === 2, "a kept comparison was asked for again");
  warmer.want([12, 13]);
  warmer.want([]);
  warmLine("an empty ask, as a panel hidden, parked, or offline makes, empties the queue");
  assert(warmer.snapshot().queue.length === 0, "an empty ask left the queue");
  await warmIdle();
  assert(reads.length === 4, "a warm was read after an empty ask");
  warmer.want([12]);
  warmer.dispose();
  await warmIdle();
  assert(reads.length === 4, "a disposed warmer read a record");

  // Behind the reader: while a page's own read is on its way, a warm sends nothing.
  const behindKeep = keepNow();
  const reading = page({ keep: behindKeep });
  reading.prefetch.want(first);
  reading.idle();
  const behindLoads = [];
  const behindIdle = [];
  const behind = createComparisonWarmer({
    keep: behindKeep,
    read: (number) =>
      Promise.resolve({ comparison: { left: "base", right: `head${number}` }, freshForMs: 60_000 }),
    load(comparison) {
      behindLoads.push(comparison.right);
      return Promise.resolve({ document: comparison.right });
    },
    schedule(callback) {
      behindIdle.push(callback);
      return callback;
    },
    cancel() {},
    isVisible: () => true,
    now: () => 0,
  });
  behind.want([20]);
  behindIdle.shift()();
  await tick();
  steps.push({
    step: "a warm whose record is read while the open page's comparison is on its way waits for it",
    pageRequests: reading.requests.length,
    warmRequests: [...behindLoads],
  });
  assert(behindLoads.length === 0, "a warm was sent beside a page's own read");
  reading.requests[0].resolve({ document: "first" });
  await tick();
  await tick();
  steps.push({
    step: "the page's answer arrives: the warm is sent",
    warmRequests: [...behindLoads],
  });
  assert(behindLoads.length === 1, "the warm was not sent once the page's read ended");
  behind.dispose();
  reading.prefetch.dispose();

  // The hourly cap: past WARM_PER_HOUR comparisons asked for, the lane asks for none, and
  // an hour later it asks again.
  const capped = [];
  const cappedReads = [];
  const cappedIdle = [];
  let cappedClock = 0;
  const cappedWarmer = createComparisonWarmer({
    keep: keepNow(),
    read(number) {
      cappedReads.push(number);
      return Promise.resolve({
        comparison: { left: "base", right: `head${number}` },
        freshForMs: 60_000,
      });
    },
    load(comparison) {
      capped.push(comparison.right);
      return Promise.resolve({ document: comparison.right });
    },
    schedule(callback) {
      cappedIdle.push(callback);
      return callback;
    },
    cancel() {},
    isVisible: () => true,
    now: () => cappedClock,
  });
  const drain = async () => {
    while (cappedIdle.length > 0) {
      cappedIdle.shift()();
      await tick();
    }
  };
  for (let number = 1; number <= prefetchModule.WARM_PER_HOUR + 1; number += 1) {
    cappedWarmer.want([number]);
    await drain();
  }
  assert(capped.length === prefetchModule.WARM_PER_HOUR, "the lane asked past its hourly cap");
  assert(
    cappedReads.length === prefetchModule.WARM_PER_HOUR,
    "the lane read a record past its hourly cap",
  );
  assert(
    cappedWarmer.snapshot().recent.at(-1) === `${prefetchModule.WARM_PER_HOUR + 1}: hourly cap`,
    "the lane did not say the cap held it",
  );
  cappedClock += 3_600_000;
  cappedWarmer.want([prefetchModule.WARM_PER_HOUR + 2]);
  await drain();
  assert(
    capped.length === prefetchModule.WARM_PER_HOUR + 1,
    "an hour later the lane asked nothing",
  );
  cappedWarmer.dispose();

  // An outcome that leaves nothing in the keep holds for the record's window too: ten asks a
  // second apart, each naming the same three pull requests, read each record once.
  async function repeatedAsks(kind) {
    const repeatKeep = keepNow({ maxChars: 70, entryChars: 40 });
    const repeatReads = [];
    const repeatLoads = [];
    const repeatIdle = [];
    let repeatClock = 0;
    const repeated = createComparisonWarmer({
      keep: repeatKeep,
      read(number) {
        repeatReads.push(number);
        return Promise.resolve({
          comparison: kind === "no comparison" ? null : { left: "base", right: `head${number}` },
          freshForMs: 60_000,
        });
      },
      load(comparison) {
        repeatLoads.push(comparison.right);
        return kind === "refused"
          ? Promise.reject(new Error("409"))
          : Promise.resolve({ document: kind === "too large to keep" ? "z".repeat(60) : "ok" });
      },
      schedule(callback) {
        repeatIdle.push(callback);
        return callback;
      },
      cancel() {},
      isVisible: () => true,
      now: () => repeatClock,
    });
    for (let ask = 0; ask < 10; ask += 1) {
      repeated.want([31, 32, 33]);
      while (repeatIdle.length > 0) {
        repeatIdle.shift()();
        await tick();
      }
      repeatClock += 1000;
    }
    const outcome = {
      recordReads: repeatReads.length,
      comparisonRequests: repeatLoads.length,
      kept: repeatKeep.snapshot().kept,
      recent: repeated.snapshot().recent,
    };
    repeated.dispose();
    assert(repeatReads.length === 3, `${kind}: a record was read again within its window`);
    return outcome;
  }
  steps.push({
    step: "ten asks a second apart, each naming the same three pull requests: each is read once, whatever its outcome",
    answersKept: await repeatedAsks("kept"),
    noComparison: await repeatedAsks("no comparison"),
    refused: await repeatedAsks("refused"),
    tooLargeToKeep: await repeatedAsks("too large to keep"),
  });

  console.log(JSON.stringify({ steps }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
