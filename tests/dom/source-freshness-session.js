// Browserless session: a served mirror's freshness label, newer-revision offer, and pin
// switch, driven through the production browser code.
//
// The page talks to the server through three routes, and the commit view through a
// fourth. Every response here is one the in-process application gave while a mirror
// went stale, refreshed, gained a newer commit, switched its pin, lost its origin,
// invalidated an open history cursor, and was asked for commits it did not have,
// recorded in tests/fixtures/source-freshness-responses.json.
// tests/test_source_freshness_session.py replays that story against a real store and
// fails when the recording drifts, so this session never runs on an envelope a test
// wrote by hand. Only the entity tags are the session's own: the server's are hashes
// of wall-clock times the recording replaces.
//
// The production modules load whole, the way the shell links them:
// static/source-freshness.js owns polling, visibility, the label, the offer, the two
// POST actions, and what becomes of a commit the mirror lacks; static/source-pin-guard.js
// names the page's commit on its data
// requests and reports a pin_changed refusal; static/git-history-window.js owns
// what a failed history page means. Timers, the clock, visibility, and paint are
// injected; each step prints the requests the page made, the timer it left, how many
// times it painted, what it would paint, and whether it reloaded.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/source-freshness-responses.json"), "utf8"),
);

// A few minutes after the recording's stand-in fetch times, so ages read naturally.
const NOW_MS = Date.parse("2026-09-23T12:05:00Z");

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function loadProductionModules() {
  const context = {
    window: {},
    console,
    Date,
    Headers,
    JSON,
    Math,
    Number,
    Object,
    Promise,
    Request,
    URL,
  };
  context.window.window = context.window;
  vm.createContext(context);
  for (const name of ["source-freshness.js", "source-pin-guard.js", "git-history-window.js"]) {
    const file = path.join(staticDir, name);
    vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  }
  return context.window;
}

const runtime = loadProductionModules();
const freshness = runtime.MetabrowserSourceFreshness;
const pinGuard = runtime.MetabrowserSourcePinGuard;
const historyWindow = runtime.MetabrowserGitHistoryWindow;
assert(
  freshness && pinGuard && historyWindow,
  "the production modules did not install their runtimes",
);

/**
 * A scripted server and injected browser facilities for one page.
 *
 * The status route answers the status the step set, or a 304 when the page sends that
 * status's entity tag; each POST route answers from its own queue.
 */
function createPage() {
  const log = [];
  const timers = new Map();
  let nextTimer = 1;
  let visible = true;
  let reloads = 0;
  const navigated = [];
  let renders = 0;
  let model = null;
  const postAnswers = { "/api/source/refresh": [], "/api/source/pin": [] };
  let currentStatus = null;
  let currentTag = null;
  let tagCounter = 0;

  function setStatus(status) {
    currentStatus = status;
    tagCounter += 1;
    currentTag = `"s${tagCounter}"`;
  }

  const deps = {
    async request(method, route, options) {
      if (method === "GET") {
        const conditional = options.etag ? ` If-None-Match: ${options.etag}` : "";
        log.push(`GET ${route}${conditional}`);
        if (options.etag && options.etag === currentTag) {
          return { status: 304, etag: currentTag, body: null };
        }
        return { status: 200, etag: currentTag, body: currentStatus };
      }
      log.push(`POST ${route} ${JSON.stringify(options.body ?? {})}`);
      const answer = postAnswers[route].shift();
      assert(answer, `no scripted answer for POST ${route}`);
      return { status: answer.status, etag: null, body: answer.body };
    },
    schedule(callback, delayMs) {
      const handle = nextTimer;
      nextTimer += 1;
      timers.set(handle, { callback, delayMs });
      return handle;
    },
    cancel(handle) {
      timers.delete(handle);
    },
    now: () => NOW_MS,
    isVisible: () => visible,
    render(next) {
      model = next;
      renders += 1;
    },
    reload() {
      reloads += 1;
    },
    navigate(href) {
      navigated.push(href);
    },
  };

  // The commit view's side of opening a commit the mirror lacks, as static/git-panel.js
  // supplies it: asking the commit route again, painting, and whether the reader is
  // still on that commit. The route answers from its own queue.
  const commitAnswers = [];
  let commitModel = null;
  let commitShown = null;
  let commitPaints = 0;
  let onCommit = true;

  function commitView(oid) {
    return {
      async load() {
        log.push(`GET /api/git/commit/${oid}`);
        const answer = commitAnswers.shift();
        assert(answer, `no scripted answer for GET /api/git/commit/${oid}`);
        if (answer.status !== 200) {
          return false;
        }
        commitModel = null;
        commitShown = answer.commit;
        commitPaints += 1;
        return true;
      },
      paint(next) {
        commitModel = next;
        commitPaints += 1;
      },
      isCurrent: () => onCommit,
      now: () => NOW_MS,
    };
  }

  return {
    deps,
    setStatus,
    commitView,
    answerCommit(answer) {
      commitAnswers.push(answer);
    },
    leaveCommit() {
      onCommit = false;
    },
    answerPost(route, status, body) {
      postAnswers[route].push({ status, body });
    },
    setVisible(value) {
      visible = value;
    },
    async fireTimer() {
      const pending = [...timers.entries()];
      assert(pending.length === 1, `expected one pending timer, found ${pending.length}`);
      const [handle, timer] = pending[0];
      timers.delete(handle);
      timer.callback();
      await settle();
    },
    observe(step) {
      const pending = [...timers.values()];
      const timer =
        pending.length === 0
          ? null
          : pending[0].delayMs === freshness.FAST_POLL_MS
            ? "fast"
            : pending[0].delayMs === freshness.SLOW_POLL_MS
              ? "slow"
              : String(pending[0].delayMs);
      const painted = renders;
      renders = 0;
      const observed = {
        step,
        requests: log.splice(0),
        timer,
        reloads,
        repaints: painted,
        paint: paintOf(model),
      };
      // Only a page a selection arrived for navigates; the other steps omit the key.
      if (navigated.length > 0) {
        observed.navigated = navigated.splice(0);
      }
      // What the preview pane shows for a commit the mirror lacked, and how many times
      // the step painted it: the state it is in, or the commit once the fetch brought
      // it. Steps with no commit view omit the key.
      if (commitShown !== null) {
        observed.commit = { repaints: commitPaints, shows: commitShown };
      } else if (commitModel !== null) {
        observed.commit = {
          repaints: commitPaints,
          state: commitModel.state,
          title: commitModel.title,
          detail: commitModel.detail,
          offer: commitModel.retry ? "[Retry]" : null,
        };
      }
      commitPaints = 0;
      return observed;
    },
  };
}

// What the row would show, one line per part, so a transcript reads as the page does.
function paintOf(model) {
  if (model === null || !model.visible) {
    return null;
  }
  const offer = model.offer;
  return {
    label: model.label,
    tone: model.tone,
    detail: model.detail,
    offer:
      offer === null
        ? null
        : `${offer.text} [${offer.button}]${offer.kind === "switch" ? ` → ${offer.ref}` : ""}`,
    error: model.error,
  };
}

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

async function run() {
  const steps = [];
  const topic = recorded.refreshed.ref;

  // One page through a whole refresh and switch.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);

    page.setStatus(recorded.stale);
    page.answerPost("/api/source/refresh", 202, recorded.refresh_started);
    await controller.start();
    steps.push(page.observe("open a stale page"));

    page.setStatus(recorded.refresh_started.status);
    await page.fireTimer();
    steps.push(page.observe("poll while the refresh runs"));

    await page.fireTimer();
    steps.push(page.observe("an unchanged status is a 304"));

    page.setStatus(recorded.refreshed);
    await page.fireTimer();
    steps.push(page.observe("the refresh brought a newer commit"));

    page.setVisible(false);
    controller.onVisibilityChange();
    steps.push(page.observe("a hidden page stops polling"));

    page.setVisible(true);
    controller.onVisibilityChange();
    await settle();
    steps.push(page.observe("a page shown again polls at once"));

    page.answerPost("/api/source/pin", 200, recorded.switched);
    await controller.acceptOffer();
    steps.push(page.observe("accept the offer"));
    assert(
      JSON.stringify(steps.at(-1).requests) ===
        JSON.stringify([`POST /api/source/pin ${JSON.stringify({ ref: topic })}`]),
      "accepting must pin the ref the offer named",
    );
    controller.dispose();
  }

  // A page whose pin another tab switched.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.refreshed);
    await controller.start();
    page.observe("opened");
    page.setStatus(recorded.after_switch);
    await page.fireTimer();
    steps.push(page.observe("another tab switched the pin"));
    await controller.acceptOffer();
    steps.push(page.observe("reload after a switch elsewhere"));
    controller.dispose();
  }

  // A page whose pin was switched before its first poll, or that was left open while
  // the server restarted onto another pin: the server wrote the page's pin and ref into
  // it, so the first status it reads already differs.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps, {
      shown: { pin: recorded.refreshed.pin, ref: recorded.refreshed.ref },
    });
    page.setStatus(recorded.after_switch);
    await controller.start();
    steps.push(page.observe("switched before the first poll"));
    controller.dispose();
  }

  // A page opened on the default branch while the URL's selection waited for its fetch:
  // once the fetch brings it and the server serves it, the page goes to its address.
  {
    const page = createPage();
    const pending = recorded.selection_pending;
    const controller = freshness.createController(page.deps, {
      shown: { pin: pending.pin, ref: pending.ref },
    });
    page.setStatus(pending);
    page.answerPost("/api/source/refresh", 202, recorded.selection_refresh_started);
    await controller.start();
    steps.push(page.observe("a URL selection waits for its fetch"));
    page.setStatus(recorded.selection_found);
    await page.fireTimer();
    steps.push(page.observe("the fetch brought the selection; the page goes to it"));
    await page.fireTimer();
    steps.push(page.observe("a page goes to a selection once"));
    controller.dispose();
  }

  // A page whose address the fetch did not bring, and one whose fetch could not run:
  // the row says so, and the second offers to fetch again.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.selection_not_found);
    await controller.start();
    steps.push(page.observe("the address is not on the origin"));
    controller.dispose();
  }
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.selection_fetch_failed);
    await controller.start();
    steps.push(page.observe("the address could not be fetched"));
    page.answerPost("/api/source/refresh", 202, recorded.selection_retry_started);
    await controller.acceptOffer();
    steps.push(page.observe("retry the address"));
    controller.dispose();
  }

  // A commit the mirror lacks, opened by its address in a served page. The commit
  // route named the miss (recorded.commit_missing) and fetched nothing, so the view asks
  // for one fetch through the page's controller, waits for it on the page's own polls,
  // and asks the route again.
  const outcomes = [];
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.commit_page);
    await controller.start();
    page.observe("opened");
    assert(recorded.commit_missing.body.code === "commit_not_found", "the miss must be typed");
    page.answerPost("/api/source/refresh", 202, recorded.commit_fetch_started);
    page.answerCommit(recorded.commit_found);
    const opening = freshness.openMissingCommit(
      controller,
      page.commitView(recorded.commit_missing.oid),
    );
    await settle();
    steps.push(page.observe("a commit the mirror lacks waits for one fetch"));
    page.setStatus(recorded.commit_fetch_started.status);
    await page.fireTimer();
    steps.push(page.observe("the commit waits while the fetch runs"));
    page.setStatus(recorded.commit_fetched);
    await page.fireTimer();
    outcomes.push(await opening);
    steps.push(page.observe("the fetch brought the commit; it opens"));
    controller.dispose();
  }

  // One the origin does not have: the fetch runs to the end and the route still says no.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.commit_page);
    await controller.start();
    page.observe("opened");
    page.answerPost("/api/source/refresh", 202, recorded.commit_fetch_started);
    page.answerCommit(recorded.commit_absent_after);
    const opening = freshness.openMissingCommit(
      controller,
      page.commitView(recorded.commit_absent.oid),
    );
    await settle();
    page.observe("waiting");
    page.setStatus(recorded.commit_fetched);
    await page.fireTimer();
    outcomes.push(await opening);
    steps.push(page.observe("the fetch did not bring the commit"));
    controller.dispose();
  }

  // One whose fetch cannot run: the view says so and offers the fetch again, and a
  // retry asks once more.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.commit_fetched);
    await controller.start();
    page.observe("opened");
    const view = page.commitView(recorded.commit_absent.oid);
    page.answerPost("/api/source/refresh", 202, recorded.commit_unfetched_started);
    page.answerCommit(recorded.commit_absent_after);
    const opening = freshness.openMissingCommit(controller, view);
    await settle();
    page.observe("waiting");
    page.setStatus(recorded.commit_unfetched);
    await page.fireTimer();
    outcomes.push(await opening);
    steps.push(page.observe("the commit could not be fetched"));
    page.answerPost("/api/source/refresh", 202, recorded.commit_unfetched_started);
    const retrying = freshness.openMissingCommit(controller, view);
    await settle();
    steps.push(page.observe("retry the commit"));
    // The reader goes elsewhere while the retry's fetch runs: nothing is asked or painted.
    page.leaveCommit();
    page.setStatus(recorded.commit_unfetched);
    await page.fireTimer();
    outcomes.push(await retrying);
    steps.push(page.observe("the reader left before the fetch ended"));
    controller.dispose();
  }

  // A refresh already running is the fetch: the page that opened stale asked for it, so
  // the commit view asks for none beside it.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.stale);
    page.answerPost("/api/source/refresh", 202, recorded.refresh_started);
    await controller.start();
    page.observe("opened stale");
    page.answerCommit(recorded.commit_absent_after);
    const opening = freshness.openMissingCommit(
      controller,
      page.commitView(recorded.commit_absent.oid),
    );
    await settle();
    steps.push(page.observe("a refresh already running is the commit's fetch"));
    page.setStatus(recorded.refreshed);
    await page.fireTimer();
    outcomes.push(await opening);
    page.observe("ended");
    controller.dispose();
  }
  assert(
    JSON.stringify(outcomes) ===
      JSON.stringify(["found", "not_found", "fetch_failed", "superseded", "not_found"]),
    `a missing commit ended as ${JSON.stringify(outcomes)}`,
  );

  // A refresh that failed.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.failed);
    await controller.start();
    steps.push(page.observe("a refresh failed; the pin is still served"));
    controller.dispose();
  }

  // A switch the server refuses, as it does when a later refresh pruned the offered
  // branch before the reader accepted: the recorded refusal of a name the mirror lacks.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.refreshed);
    await controller.start();
    page.observe("offered");
    page.answerPost("/api/source/pin", recorded.pin_refused.status, recorded.pin_refused.body);
    await controller.acceptOffer();
    steps.push(page.observe("a refused switch says why and does not reload"));
    controller.dispose();
  }

  // A stale page whose refresh cannot run asks once per visible period, not once per
  // poll: its origin is gone, so every refresh fails and the mirror stays stale.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.unreachable);
    page.answerPost("/api/source/refresh", 202, recorded.unreachable_started);
    await controller.start();
    steps.push(page.observe("open a stale page whose origin is gone"));
    page.setStatus(recorded.unreachable_after);
    await page.fireTimer();
    await page.fireTimer();
    steps.push(page.observe("a stale page whose refresh fails asks once"));
    page.setVisible(false);
    controller.onVisibilityChange();
    page.setVisible(true);
    page.answerPost("/api/source/refresh", 202, recorded.unreachable_started);
    controller.onVisibilityChange();
    await settle();
    steps.push(page.observe("shown again, a stale page asks again"));
    controller.dispose();
  }

  // What a page's data requests say about the pin it shows, and a refusal for a pin the
  // server no longer serves, as the server answered it after the switch.
  const sent = [];
  const reported = [];
  const guardedFetch = pinGuard.guardFetch(
    async (input, init) => {
      const url = typeof input === "string" ? input : input.url;
      sent.push({ url, pin: new Headers(init?.headers).get(pinGuard.PIN_HEADER) });
      if (url.startsWith("/api/tree")) {
        return new Response(JSON.stringify(recorded.pin_changed.body), {
          status: recorded.pin_changed.status,
          headers: recorded.pin_changed.headers,
        });
      }
      return new Response("{}", { status: 200 });
    },
    recorded.refreshed.pin,
    () => "http://127.0.0.1:8471/view/",
    (served) => {
      reported.push(served);
    },
  );
  const answered = [];
  for (const url of [
    "/api/file?path=g1-UkVBRE1FLm1k",
    "/api/source/status",
    "http://elsewhere.example/api/file",
    "/api/tree?depth=1",
  ]) {
    answered.push((await guardedFetch(url)).status);
  }
  const guard = { page: recorded.refreshed.pin, sent, answered, reported };

  // What a failed history page means for the Git panel.
  const failures = [
    { name: "a refresh moved the refs", ...recorded.history_stale, initial: false },
    { name: "the session expired", status: 410, body: {}, initial: false },
    { name: "the cursor was rejected", status: 400, body: {}, initial: false },
    { name: "a conflict without a code", status: 409, body: {}, initial: false },
    { name: "the server failed", status: 500, body: {}, initial: false },
    { name: "the first page was stale", ...recorded.history_stale, initial: true },
  ];
  const history = failures.map((failure) => ({
    failure: failure.name,
    status: failure.status,
    code: failure.body.code ?? null,
    initial: failure.initial,
    means: historyWindow.classifyPageFailure({
      status: failure.status,
      code: failure.body.code ?? null,
      initial: failure.initial,
    }),
  }));

  return { steps, guard, history };
}

run()
  .then((transcript) => {
    process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
  })
  .catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
