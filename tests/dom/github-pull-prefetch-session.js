// Browserless session: Files changed fetched from Conversation, through the production module.
//
// builtin_plugins/github/comparison-prefetch.js loads whole. A scripted page asks it what the
// pull-request page asks: `want` on every paint of the Conversation tab, `take` when a diff
// mounts, `dispose` when the page goes. Each step prints what it has sent, what it holds, and
// what a mount would be handed. It asserts, and so prints nothing for, that a poll changes
// nothing and that a disposed prefetch does nothing.

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
  const { createComparisonPrefetch } = await import(
    pathToFileURL(
      path.join(repoRoot, "src/metabrowser/builtin_plugins/github/comparison-prefetch.js"),
    ).href
  );

  function page({ visible = true } = {}) {
    const requests = [];
    const scheduled = [];
    let warmed = 0;
    const state = { visible };
    const prefetch = createComparisonPrefetch({
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
  say("a later mount gets nothing here, and the browser's cache answers it", reader, {
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

  console.log(JSON.stringify({ steps }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
