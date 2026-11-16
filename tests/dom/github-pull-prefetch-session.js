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
  const nothing = await beforeIdle.prefetch.take(first);
  beforeIdle.idle();
  say("a click before the browser was idle: the diff asks for itself, and only once", beforeIdle, {
    handed: nothing ?? null,
  });

  const direct = page();
  const direct_ = await direct.prefetch.take(first);
  direct.prefetch.want(first);
  direct.idle();
  say("a page opened on Files changed sends nothing here", direct, { handed: direct_ ?? null });

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
        reads.push({ number, signal, answer: () => resolve(records[number] ?? null) });
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
  clock += prefetchModule.WARM_RECHECK_MS;
  warmer.want([8]);
  await warmIdle();
  reads.at(-1).answer();
  await tick();
  warmLine("past the record's freshness window it is read again, and the keep answers: no request");
  assert(loads.length === 2, "a kept comparison was asked for again");
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
    read: (number) => Promise.resolve({ left: "base", right: `head${number}` }),
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
  const cappedIdle = [];
  let cappedClock = 0;
  const cappedWarmer = createComparisonWarmer({
    keep: keepNow(),
    read: (number) => Promise.resolve({ left: "base", right: `head${number}` }),
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

  console.log(JSON.stringify({ steps }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
