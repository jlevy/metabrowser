// Browserless session: a served mirror's freshness label, following a branch to its new
// commit, and pin switches, driven through the production browser code.
//
// The page talks to the server through three routes, and the commit view through a
// fourth. A page on a branch also makes its own ask while visible, which has the server
// probe that branch at its origin; the scripted server answers it as the real one does
// when the branch has not moved, with the status as it is, unless a step queued the
// recorded answer of a probe that found a push. Every response here is one the in-process application gave while a mirror
// went stale, refreshed onto a newer commit it followed, switched its pin, lost its origin,
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
// names the page's commit on its data requests, reports a pin_changed refusal, and
// decides what a page brought back by Back or Forward does; static/git-history-window.js
// owns what a failed history page means. Timers, the clock, visibility, and paint are
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

// What a repository folder's server answered for the store it keeps of its checkout's
// origin, recorded by tests/test_source_ref_selector_origin_session.py: the statuses the
// freshness row of a folder's pages reads, printed under the `folder` argument.
const recordedFolder = JSON.parse(
  fs.readFileSync(
    path.join(repoRoot, "tests/fixtures/source-ref-selector-origin-responses.json"),
    "utf8",
  ),
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
  // formatters.js names the offered commit as every line does, as the shell's startup
  // scripts load it first.
  for (const name of [
    "formatters.js",
    "source-freshness.js",
    "source-pin-guard.js",
    "git-history-window.js",
  ]) {
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
  // Answers to the page's own ask, `{"for": "page"}`, ahead of the default one.
  const pageAskAnswers = [];
  // While set, the page's ask is not answered: a probe the server is still waiting for.
  let pageAskHeld = null;
  let currentStatus = null;
  let currentTag = null;
  let tagCounter = 0;
  let answering = true;
  // The page's own address, which a follow names so the server says where it lands.
  let address = "/view/";

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
        if (!answering) {
          throw new Error("connection refused");
        }
        if (options.etag && options.etag === currentTag) {
          return { status: 304, etag: currentTag, body: null };
        }
        return { status: 200, etag: currentTag, body: currentStatus };
      }
      log.push(`POST ${route} ${JSON.stringify(options.body ?? {})}`);
      if (route === "/api/source/refresh" && options.body?.for === "page") {
        if (!answering) {
          throw new Error("connection refused");
        }
        if (pageAskHeld !== null) {
          // The server holds the ask for as long as its probe takes.
          await pageAskHeld;
        }
        const scripted = pageAskAnswers.shift();
        return scripted
          ? { status: scripted.status, etag: null, body: scripted.body }
          : { status: 200, etag: null, body: { refresh: "probed", status: currentStatus } };
      }
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
    address: () => address,
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
      // What static/git-panel.js does with the route's answer: the commit when it is
      // there, `missing` only for the route's own `commit_not_found`, and `failed` for
      // any other answer, which says nothing about the commit.
      async load() {
        log.push(`GET /api/git/commit/${oid}`);
        const answer = commitAnswers.shift();
        assert(answer, `no scripted answer for GET /api/git/commit/${oid}`);
        if (answer.status === 200) {
          commitModel = null;
          commitShown = answer.commit;
          commitPaints += 1;
          return "found";
        }
        return answer.status === 404 && answer.body?.code === "commit_not_found"
          ? "missing"
          : "failed";
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
    stopAnswering() {
      answering = false;
    },
    setAddress(value) {
      address = value;
    },
    answerPost(route, status, body) {
      postAnswers[route].push({ status, body });
    },
    answerPageAsk(status, body) {
      pageAskAnswers.push({ status, body });
    },
    /** Leave the page's asks unanswered until the function this answers is called. */
    holdPageAsk() {
      let release = () => {};
      pageAskHeld = new Promise((resolve) => {
        release = () => {
          pageAskHeld = null;
          resolve(undefined);
        };
      });
      return release;
    },
    /**
     * Open the page and let its first ask be answered. The controller does not wait for
     * that ask, so a step that looks at once would see it still on its way.
     */
    async start(controller) {
      await controller.start();
      await settle();
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
              : pending[0].delayMs === (currentStatus?.probe_every_s ?? 0) * 1000
                ? "ask"
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
        : offer.kind === "switch"
          ? `${offer.text} [${offer.button}] → ${offer.ref}`
          : `${offer.text} [${offer.button}]`,
    error: model.error,
  };
}

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

// A repository folder that keeps a store of its checkout's origin: the row is on every
// page of the folder, its working tree's too, says what was fetched is that store, and
// its Refresh fetches the store. A page that shows nothing of the store has it fetched
// quietly when it has grown old, and says "Refreshing…" only for the reader's own press.
// The reload offer is the ref selector's there.
async function runFolder() {
  const steps = [];
  const options = { checkout: true };
  {
    const page = createPage();
    const controller = freshness.createController(page.deps, options);
    page.setStatus(recordedFolder.status_stale);
    page.answerPageAsk(recordedFolder.ask_started.status, recordedFolder.ask_started.body);
    await page.start(controller);
    steps.push(
      page.observe("the working tree's page, its origin's store grown old, asks quietly, once"),
    );

    page.setStatus(recordedFolder.status_refreshed);
    await page.fireTimer();
    steps.push(page.observe("the store was fetched; the row says when, and nothing reloads"));

    page.answerPost(
      "/api/source/refresh",
      recordedFolder.refresh_started.status,
      recordedFolder.refresh_started.body,
    );
    await controller.requestRefresh();
    steps.push(page.observe("the reader's own Refresh says so while it runs"));

    page.setStatus(recordedFolder.status_refresh_failed);
    await page.fireTimer();
    steps.push(page.observe("a fetch that failed says the checkout is unchanged"));
    controller.dispose();
  }
  {
    // A page on one of the origin's branches, read from the store.
    const status = recordedFolder.switch_origin_branch.body.status;
    const page = createPage();
    const controller = freshness.createController(page.deps, {
      ...options,
      shown: { pin: status.pin, ref: status.ref },
    });
    page.setStatus(status);
    await page.start(controller);
    steps.push(page.observe("an origin branch's page names the store, not a mirror"));
    assert(!JSON.stringify(steps.at(-1).paint).includes("mirror"), "a folder's row said mirror");
    // The server came to serve the working tree: the selector offers the reload, not the row.
    page.setStatus(recordedFolder.status_working_tree);
    await page.fireTimer();
    steps.push(page.observe("the server shows the working tree again: this row offers no reload"));
    controller.dispose();
  }
  {
    // An origin branch's page opened on a store grown old asks as the reader's Refresh
    // does: it shows the store, so the fetch can change what it shows, and the row says
    // "Refreshing…" while it runs.
    const status = recordedFolder.status_origin_branch_stale;
    const page = createPage();
    const controller = freshness.createController(page.deps, {
      ...options,
      shown: { pin: status.pin, ref: status.ref },
    });
    page.setStatus(status);
    page.answerPost(
      "/api/source/refresh",
      recordedFolder.origin_branch_refresh_started.status,
      recordedFolder.origin_branch_refresh_started.body,
    );
    await page.start(controller);
    steps.push(page.observe("an origin branch's page, its store grown old, asks loudly"));
    const opened = steps.at(-1);
    assert(
      JSON.stringify(opened.requests) ===
        JSON.stringify(["GET /api/source/status", "POST /api/source/refresh {}"]),
      `an origin branch's page did not ask loudly: ${JSON.stringify(opened.requests)}`,
    );
    assert(
      opened.paint.label === "Refreshing…",
      `an origin branch's page did not say Refreshing…: ${JSON.stringify(opened.paint)}`,
    );
    controller.dispose();
  }
  // The same statuses on a page that is not a folder's show no row for a working tree.
  const plain = freshness.describe(recordedFolder.status_working_tree, {
    shown: null,
    nowMs: NOW_MS,
  });
  assert(plain.visible === false, "a working tree's status drew a row on a page of no folder");
  return steps;
}

// The navigation's Refresh asks through `refreshNow` (static/refresh-plan.js), which settles
// once nothing is fetching, so a part the plan runs next reads what the fetch brought. It
// settles while the fetch runs only when it ends: at once for a refusal, when the fetch
// ends, at the first poll that fails, and when the row is disposed.
async function runRefreshNow() {
  const outcomes = {};
  /** A folder's page whose store was fetched a moment ago, its asks answered. */
  async function opened() {
    const page = createPage();
    const controller = freshness.createController(page.deps, { checkout: true });
    page.setStatus(recordedFolder.status_stale);
    page.answerPageAsk(recordedFolder.ask_started.status, recordedFolder.ask_started.body);
    await page.start(controller);
    page.setStatus(recordedFolder.status_refreshed);
    await page.fireTimer();
    page.observe("opened");
    return { page, controller };
  }
  /** A press, and whether it has settled, read as the plan would await it. */
  function press(controller) {
    const pressed = { settled: false };
    void controller.refreshNow().then(() => {
      pressed.settled = true;
    });
    return pressed;
  }
  const started = recordedFolder.refresh_started;
  {
    const { page, controller } = await opened();
    page.answerPost("/api/source/refresh", started.status, started.body);
    const pressed = press(controller);
    await settle();
    const whileFetching = pressed.settled;
    page.setStatus(recordedFolder.status_refreshed);
    await page.fireTimer();
    outcomes["a fetch that runs: settled while it runs, then once it has ended"] = [
      whileFetching,
      pressed.settled,
    ];
    controller.dispose();
  }
  {
    const { page, controller } = await opened();
    page.answerPost("/api/source/refresh", started.status, started.body);
    const pressed = press(controller);
    await settle();
    const whileFetching = pressed.settled;
    page.stopAnswering();
    await page.fireTimer();
    outcomes["a poll that fails while it runs: settled while it runs, then once it failed"] = [
      whileFetching,
      pressed.settled,
    ];
    controller.dispose();
  }
  {
    const { page, controller } = await opened();
    page.answerPost("/api/source/refresh", started.status, started.body);
    const pressed = press(controller);
    await settle();
    const whileFetching = pressed.settled;
    controller.dispose();
    await settle();
    outcomes["a row disposed while it runs: settled while it runs, then once disposed"] = [
      whileFetching,
      pressed.settled,
    ];
  }
  {
    const { page, controller } = await opened();
    page.answerPost("/api/source/refresh", 409, { code: "too_many" });
    const pressed = press(controller);
    await settle();
    outcomes["a refused refresh: settled at once"] = pressed.settled;
    controller.dispose();
  }
  const [ran, failed, disposed] = Object.values(outcomes);
  assert(
    [ran, failed, disposed].every(([during, after]) => during === false && after === true) &&
      outcomes["a refused refresh: settled at once"] === true,
    `refreshNow settled at the wrong time: ${JSON.stringify(outcomes)}`,
  );
  return outcomes;
}

// A repository folder's page on one of the checkout's own branches. It reads that branch,
// not one commit of it: the page asks as often as its status says, the server reads the
// checkout's refs for the ask and fetches nothing, and when the reader's commit moved the
// branch the page goes to the new commit at its own address. With a store of the origin
// the row is the store's as on every page of the folder; with none there is no row but
// while the page follows, or when its follow was refused.
async function runCheckoutBranch() {
  const steps = [];
  {
    const opened = recordedFolder.switch_local_branch.body;
    const page = createPage();
    page.setAddress(opened.view_href);
    const controller = freshness.createController(page.deps, {
      checkout: true,
      shown: { pin: opened.status.pin, ref: opened.status.ref },
    });
    page.setStatus(opened.status);
    await page.start(controller);
    steps.push(page.observe("a page on the checkout's own branch asks where the branch is"));
    await page.fireTimer();
    steps.push(page.observe("the branch is where it was: nothing repaints, and it asks again"));

    // The reader committed on the branch: the server read the refs and serves the commit.
    page.answerPageAsk(recordedFolder.ask_local_moved.status, recordedFolder.ask_local_moved.body);
    page.answerPost(
      "/api/source/pin",
      recordedFolder.follow_local_branch.status,
      recordedFolder.follow_local_branch.body,
    );
    await page.fireTimer();
    steps.push(page.observe("the reader committed on the branch; the page follows it"));
    controller.dispose();
  }
  {
    // A checkout that keeps no store: nothing is refreshable, and the branch still follows.
    const opened = recordedFolder.plain_switch.body;
    const page = createPage();
    page.setAddress(opened.view_href);
    const controller = freshness.createController(page.deps, {
      checkout: true,
      shown: { pin: opened.status.pin, ref: opened.status.ref },
    });
    page.setStatus(opened.status);
    await page.start(controller);
    steps.push(page.observe("with no store of an origin there is no row, and the page still asks"));
    assert(steps.at(-1).paint === null, "a folder with no store drew a row for an unmoved branch");

    page.answerPageAsk(recordedFolder.plain_ask_moved.status, recordedFolder.plain_ask_moved.body);
    page.answerPost(
      "/api/source/pin",
      recordedFolder.plain_follow_refused.status,
      recordedFolder.plain_follow_refused.body,
    );
    await page.fireTimer();
    steps.push(page.observe("a follow the server refused says the branch moved, and why"));

    // The reader presses the row: the follow is asked for again, and the page goes.
    page.answerPost(
      "/api/source/pin",
      recordedFolder.plain_follow.status,
      recordedFolder.plain_follow.body,
    );
    await controller.requestRefresh();
    await settle();
    steps.push(page.observe("pressed, the page asks again and follows"));
    controller.dispose();
  }
  {
    // A hidden page asks nothing, and a commit opened by its ID is never asked about.
    const opened = recordedFolder.plain_switch.body;
    const page = createPage();
    page.setVisible(false);
    const controller = freshness.createController(page.deps, {
      checkout: true,
      shown: { pin: opened.status.pin, ref: opened.status.ref },
    });
    page.setStatus(opened.status);
    await page.start(controller);
    steps.push(page.observe("a hidden page asks nothing"));
    controller.dispose();
    const commit = { ...opened.status, ref: null, follows: false, probe_every_s: null };
    const model = freshness.describe(
      { ...commit, pin: recordedFolder.plain_ask_moved.body.status.pin },
      { shown: { pin: opened.status.pin, ref: null }, nowMs: NOW_MS, checkout: true },
    );
    assert(model.visible === false && model.follow === null, "a commit opened by its ID moved");
  }
  {
    // The reader deleted the branch the page shows: the server keeps its last commit
    // served, the status reads the branch as naming none, and a quiet row says so.
    const opened = recordedFolder.plain_topic.body;
    const page = createPage();
    const controller = freshness.createController(page.deps, {
      checkout: true,
      shown: { pin: opened.status.pin, ref: opened.status.ref },
    });
    page.setStatus(opened.status);
    page.answerPageAsk(recordedFolder.plain_ask_gone.status, recordedFolder.plain_ask_gone.body);
    await page.start(controller);
    steps.push(page.observe("the reader deleted the branch: the row says its last commit stays"));
    controller.dispose();
    // With a store the row is the store's, and says it as well.
    const stored = { ...recordedFolder.switch_local_branch.body.status, latest: null };
    const model = freshness.describe(stored, {
      shown: { pin: stored.pin, ref: stored.ref },
      nowMs: NOW_MS,
      checkout: true,
    });
    steps.push({
      step: "with a store, the store's row says the branch is gone",
      paint: { label: model.label, tone: model.tone, detail: model.detail },
    });
    assert(model.follow === null, "a gone branch was followed");
  }
  return steps;
}

async function run() {
  const steps = [];
  // The steps of a page's own ask, printed under the `asks` argument: one transcript of
  // every step is more than the golden runner can match as one block.
  const asks = [];
  const topic = recorded.refreshed.ref;
  const folder = await runFolder();
  const checkoutBranch = await runCheckoutBranch();
  const refreshNow = await runRefreshNow();

  // One page through a whole refresh, which moves its branch: the server follows the
  // branch, and the page goes with it, with nothing to accept.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);

    page.setStatus(recorded.stale);
    page.answerPost("/api/source/refresh", 202, recorded.refresh_started);
    await page.start(controller);
    steps.push(page.observe("open a stale page"));

    page.setStatus(recorded.refresh_started.status);
    await page.fireTimer();
    steps.push(page.observe("poll while the refresh runs"));

    await page.fireTimer();
    steps.push(page.observe("an unchanged status is a 304"));

    page.setVisible(false);
    controller.onVisibilityChange();
    steps.push(page.observe("a hidden page stops polling"));

    page.setVisible(true);
    controller.onVisibilityChange();
    await settle();
    steps.push(page.observe("a page shown again polls at once"));

    page.setStatus(recorded.refreshed);
    page.answerPost("/api/source/pin", 200, recorded.followed);
    await page.fireTimer();
    steps.push(page.observe("the refresh moved the branch; the page follows it"));
    assert(
      steps.at(-1).requests.at(-1) ===
        `POST /api/source/pin ${JSON.stringify({ ref: topic, view: "/view/" })}` &&
        steps.at(-1).reloads === 1,
      "following must ask for the page's own ref at its own address, then reload in place",
    );
    controller.dispose();
  }

  // A page on a branch, visible for a while. It makes its own ask with its first status
  // and then every `probe_every_s`; each has the server ask the origin where the branch
  // is, and the answer is the status, so the ask is the page's poll too. A hidden page
  // asks nothing. When a probe finds a push, the server starts the fetch at once, the
  // page polls quickly until it ends, and then follows its branch.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    const answerAsk = (answer) => page.answerPageAsk(answer.status, answer.body);
    page.setStatus(recorded.probe_page);
    answerAsk(recorded.probe_unchanged);
    await page.start(controller);
    asks.push(page.observe("a page on a branch asks with its first status"));

    answerAsk(recorded.probe_unchanged);
    await page.fireTimer();
    asks.push(page.observe("an unchanged branch: the ask is the poll, and nothing repaints"));

    page.setVisible(false);
    controller.onVisibilityChange();
    asks.push(page.observe("a hidden page asks nothing"));

    page.setVisible(true);
    answerAsk(recorded.probe_unchanged);
    controller.onVisibilityChange();
    await settle();
    asks.push(page.observe("shown again, the page asks at once"));

    answerAsk(recorded.probe_moved);
    await page.fireTimer();
    asks.push(page.observe("the origin moved the branch: the fetch starts at once"));

    page.setStatus(recorded.probe_followed);
    page.answerPost("/api/source/pin", 200, recorded.followed);
    await page.fireTimer();
    asks.push(page.observe("the fetch brought the push; the page follows its branch"));
    controller.dispose();
  }

  // Once a window the page's ask fetches the whole mirror. Nobody pressed for that, so
  // the status calls it quiet: the row keeps its words, its button, and its silence, and
  // the page keeps its own interval, not the quick poll of a refresh it shows.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.probe_followed);
    await page.start(controller);
    page.observe("opened");
    page.answerPageAsk(recorded.window_fetch.status, recorded.window_fetch.body);
    await page.fireTimer();
    asks.push(page.observe("once a window the mirror is fetched, and the row says nothing"));
    page.setStatus(recorded.window_fetched);
    await page.fireTimer();
    asks.push(page.observe("the quiet fetch ended, and the row still says nothing new"));
    controller.dispose();
  }

  // A server that refuses the page's ask is polled as before, and one that stops
  // answering is reported as a failed poll is and found again by the slow poll.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.probe_page);
    page.answerPageAsk(recorded.pin_refused.status, recorded.pin_refused.body);
    await page.start(controller);
    asks.push(page.observe("a refused ask says nothing, and the page polls instead"));
    await page.fireTimer();
    asks.push(page.observe("the poll after a refused ask"));
    controller.dispose();
  }
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.probe_page);
    await page.start(controller);
    page.observe("opened");
    page.stopAnswering();
    await page.fireTimer();
    asks.push(page.observe("the server stopped answering the page's asks"));
    controller.dispose();
  }

  // A page on a commit opened by its ID, which no push moves: the status names no
  // interval, so the page sends no ask of its own and polls slowly.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.commit_pin);
    await page.start(controller);
    asks.push(page.observe("a page on a commit sends no ask of its own"));
    await page.fireTimer();
    asks.push(page.observe("a page on a commit polls slowly"));
    // The server's own fetch, which it runs while no page asks: quiet as well.
    page.setStatus(recorded.idle_fetch);
    await page.fireTimer();
    asks.push(page.observe("the server's own fetch says nothing on a page that is open"));
    controller.dispose();
  }

  // A commit the mirror lacks, opened by its address on a server pinned to a branch. The
  // commit view asks for the first status itself, and the page's first ask goes out with
  // it. The server may hold that ask for as long as a probe takes, and the view does not
  // wait for it: it says what it found while the ask is still unanswered.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.probe_page);
    const release = page.holdPageAsk();
    const opening = freshness.openMissingCommit(
      controller,
      page.commitView(recorded.commit_missing.oid),
    );
    const answered = await Promise.race([opening.then(() => true), settle().then(() => false)]);
    const step = page.observe("a missing commit does not wait for the page's first ask");
    step.answeredBeforeTheAsk = answered;
    asks.push(step);
    assert(answered, "the commit view waited for the page's first ask to be answered");
    release();
    await opening;
    await settle();
    asks.push(page.observe("the page's first ask is answered afterwards"));
    controller.dispose();
  }

  // A page on a file the new commit lacks goes where the server says, the root. A page
  // whose address the new commit has reloads in place, as above, keeping line and scroll.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps, {
      shown: { pin: recorded.stale.pin, ref: recorded.stale.ref },
    });
    page.setAddress(recorded.followed_elsewhere.view);
    page.setStatus(recorded.refreshed);
    page.answerPost("/api/source/pin", 200, recorded.followed_elsewhere.answer);
    await page.start(controller);
    await settle();
    steps.push(page.observe("a page on a file the new commit lacks goes to the root"));
    controller.dispose();
  }

  // A follow the server refuses: the row says why, offers a reload, and asks no more.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps, {
      shown: { pin: recorded.stale.pin, ref: recorded.stale.ref },
    });
    page.setStatus(recorded.refreshed);
    page.answerPost("/api/source/pin", recorded.pin_refused.status, recorded.pin_refused.body);
    await page.start(controller);
    await settle();
    steps.push(page.observe("a refused follow says why and offers a reload"));
    await page.fireTimer();
    steps.push(page.observe("a refused follow is not asked again on the next poll"));
    await controller.acceptOffer();
    steps.push(page.observe("the reload a refused follow offers"));
    controller.dispose();
  }

  // A page whose pin another tab switched.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.refreshed);
    await page.start(controller);
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
    await page.start(controller);
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
    await page.start(controller);
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
    await page.start(controller);
    steps.push(page.observe("the address is not on the origin"));
    controller.dispose();
  }
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.selection_fetch_failed);
    await page.start(controller);
    steps.push(page.observe("the address could not be fetched"));
    page.answerPost("/api/source/refresh", 202, recorded.selection_retry_started);
    await controller.acceptOffer();
    steps.push(page.observe("retry the address"));
    controller.dispose();
  }

  // A commit the mirror lacks, opened by its address in a served page. The commit
  // route named the miss (recorded.commit_missing) and fetched nothing. A link in
  // served content can send a reader to such an address, so the view asks for a fetch
  // by itself only when something is older than the freshness window.
  const outcomes = [];
  const refreshRoute = "/api/source/refresh";
  const answerRefresh = (page, answer) => page.answerPost(refreshRoute, answer.status, answer.body);
  assert(recorded.commit_missing.body.code === "commit_not_found", "the miss must be typed");
  {
    // Inside the window: nothing is asked for. The view says the commit is not in the
    // mirror as fetched, not that a fetch failed to bring it, and offers Retry.
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.commit_page);
    await page.start(controller);
    page.observe("opened");
    const view = page.commitView(recorded.commit_missing.oid);
    outcomes.push(await freshness.openMissingCommit(controller, view));
    steps.push(page.observe("inside the freshness window a missing commit starts no fetch"));

    // Retry is the reader's own click: it fetches, the view says so while it runs, and
    // the commit opens once the fetch has brought it.
    answerRefresh(page, recorded.commit_retry_started);
    page.answerCommit(recorded.commit_found);
    const retrying = freshness.openMissingCommit(controller, view, { retry: true });
    await settle();
    steps.push(page.observe("retry fetches for the commit"));
    page.setStatus(recorded.commit_retry_started.body.status);
    await page.fireTimer();
    steps.push(page.observe("the commit waits while the fetch runs"));
    page.setStatus(recorded.commit_fetched);
    await page.fireTimer();
    outcomes.push(await retrying);
    steps.push(page.observe("the fetch brought the commit; it opens"));
    controller.dispose();
  }

  // One the origin does not have: the retry's fetch runs to the end and the route
  // still says no, so the view may say that no branch or tag reaches it.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.commit_page);
    await page.start(controller);
    page.observe("opened");
    answerRefresh(page, recorded.commit_retry_started);
    page.answerCommit(recorded.commit_absent_after);
    const opening = freshness.openMissingCommit(
      controller,
      page.commitView(recorded.commit_absent.oid),
      { retry: true },
    );
    await settle();
    page.observe("waiting");
    page.setStatus(recorded.commit_fetched);
    await page.fireTimer();
    outcomes.push(await opening);
    steps.push(page.observe("the fetch ran and did not bring the commit"));
    controller.dispose();
  }

  // A request that fails when the commit is asked for again is not an answer about the
  // commit: the route refused this one because the pin changed while the fetch ran.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.commit_page);
    await page.start(controller);
    page.observe("opened");
    answerRefresh(page, recorded.commit_retry_started);
    page.answerCommit(recorded.commit_refused);
    const opening = freshness.openMissingCommit(
      controller,
      page.commitView(recorded.commit_refused.oid),
      { retry: true },
    );
    await settle();
    page.observe("waiting");
    page.setStatus(recorded.commit_fetched);
    await page.fireTimer();
    outcomes.push(await opening);
    steps.push(page.observe("asking again failed; the view does not say not found"));
    controller.dispose();
  }

  // Only the data served beside the mirror is stale. The page's own request starts that
  // refresh and no fetch of the mirror, and the server says so (`fresh`); the view waits
  // for it, since a pull request's head arrives that way, and then does not claim a
  // fetch of branches and tags that did not run.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.commit_beside_page);
    answerRefresh(page, recorded.commit_beside_refresh);
    await page.start(controller);
    page.observe("opened; the page refreshes the stale data beside the mirror");
    answerRefresh(page, recorded.commit_beside_only);
    page.answerCommit(recorded.commit_absent_after);
    const opening = freshness.openMissingCommit(
      controller,
      page.commitView(recorded.commit_absent.oid),
    );
    await settle();
    steps.push(page.observe("only the data beside the mirror is refreshed"));
    assert(recorded.commit_beside_only.body.refresh === "fresh", "no mirror fetch was started");
    page.setStatus(recorded.commit_page);
    await page.fireTimer();
    outcomes.push(await opening);
    steps.push(page.observe("no fetch of the mirror ran, and the view does not say one did"));
    controller.dispose();
  }

  // Outside the window: a page whose stale mirror could not be refreshed asks for the
  // commit's fetch by itself, and that fetch cannot run either. The reader then goes
  // elsewhere while a retry's fetch runs.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.unreachable);
    page.answerPost(refreshRoute, 202, recorded.unreachable_started);
    await page.start(controller);
    page.setStatus(recorded.unreachable_after);
    await page.fireTimer();
    page.observe("opened stale");
    const view = page.commitView(recorded.commit_absent.oid);
    answerRefresh(page, recorded.commit_stale_started);
    page.answerCommit(recorded.commit_absent_after);
    const opening = freshness.openMissingCommit(controller, view);
    await settle();
    steps.push(page.observe("outside the window the page asks for the fetch itself"));
    page.setStatus(recorded.commit_stale_unfetched);
    await page.fireTimer();
    outcomes.push(await opening);
    steps.push(page.observe("the commit could not be fetched"));

    answerRefresh(page, recorded.commit_stale_started);
    const retrying = freshness.openMissingCommit(controller, view, { retry: true });
    await settle();
    page.observe("retrying");
    page.leaveCommit();
    page.setStatus(recorded.commit_stale_unfetched);
    await page.fireTimer();
    outcomes.push(await retrying);
    steps.push(page.observe("the reader left before the fetch ended"));
    controller.dispose();
  }

  // A fetch of the mirror that is already running is joined by the server, and counts.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.commit_retry_started.body.status);
    await page.start(controller);
    page.observe("opened while a fetch runs");
    answerRefresh(page, recorded.commit_joined);
    page.answerCommit(recorded.commit_found);
    const opening = freshness.openMissingCommit(
      controller,
      page.commitView(recorded.commit_missing.oid),
    );
    await settle();
    steps.push(page.observe("a fetch of the mirror already running is joined"));
    page.setStatus(recorded.commit_fetched);
    await page.fireTimer();
    outcomes.push(await opening);
    page.observe("ended");
    controller.dispose();
  }

  // A full queue refused the attended pull request's refresh, the only one that brings a
  // newer head of it, while the mirror was fetched. The fetch ran and did not bring the
  // commit, and the view says the pull request's refresh did not run rather than that the
  // origin lacks the commit.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.queue_full_page);
    answerRefresh(page, recorded.queue_full_refresh);
    await page.start(controller);
    page.observe("opened");
    answerRefresh(page, recorded.commit_unqueued_started);
    page.answerCommit(recorded.commit_unqueued_after);
    const opening = freshness.openMissingCommit(
      controller,
      page.commitView(recorded.commit_unqueued_after.oid),
      { retry: true },
    );
    await settle();
    page.observe("waiting");
    page.setStatus(recorded.commit_unqueued_fetched);
    await page.fireTimer();
    outcomes.push(await opening);
    steps.push(page.observe("the queue had no room for the pull request's refresh"));
    controller.dispose();
  }

  // The server stops answering while the fetch runs: the view gives up at the first
  // poll that fails, and the page falls back to its slow poll.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.commit_page);
    await page.start(controller);
    page.observe("opened");
    answerRefresh(page, recorded.commit_retry_started);
    const opening = freshness.openMissingCommit(
      controller,
      page.commitView(recorded.commit_absent.oid),
      { retry: true },
    );
    await settle();
    page.observe("waiting");
    page.stopAnswering();
    await page.fireTimer();
    outcomes.push(await opening);
    steps.push(page.observe("the server stopped answering while the fetch ran"));
    controller.dispose();
  }
  assert(
    JSON.stringify(outcomes) ===
      JSON.stringify([
        "not_found",
        "found",
        "not_found",
        "failed",
        "not_found",
        "fetch_failed",
        "superseded",
        "found",
        "fetch_failed",
        "fetch_failed",
      ]),
    `a missing commit ended as ${JSON.stringify(outcomes)}`,
  );

  // The origin no longer shows the repository: the row says so in the command line's words.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.origin_not_shown);
    await page.start(controller);
    steps.push(page.observe("the origin no longer shows the repository"));
    controller.dispose();
  }

  // A refresh that failed.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.failed);
    await page.start(controller);
    steps.push(page.observe("a refresh failed; the pin is still served"));
    controller.dispose();
  }

  // A stale page whose refresh cannot run asks once per visible period, not once per
  // poll: its origin is gone, so every refresh fails and the mirror stays stale.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.unreachable);
    page.answerPost("/api/source/refresh", 202, recorded.unreachable_started);
    await page.start(controller);
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

  // A page of code on the attended pull request, whose record is stale while the queue of
  // pull requests a reader asked for is full: the server refuses the page's own refresh.
  // The reader did not ask, so the row says nothing of it, as the pull request's page does;
  // a press is the reader's own, and the row says why in the server's words.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.queue_full_page);
    answerRefresh(page, recorded.queue_full_refresh);
    await page.start(controller);
    steps.push(page.observe("a page's own refresh with no room in the queue says nothing"));
    answerRefresh(page, recorded.queue_full_refresh);
    await controller.requestRefresh();
    steps.push(page.observe("a press with no room in the queue says why"));
    controller.dispose();
  }

  // A page left open while the server restarted on a folder: a folder is not refreshable,
  // so not even a press asks for a refresh, and the queue's refusal cannot reach it.
  {
    const page = createPage();
    const controller = freshness.createController(page.deps);
    page.setStatus(recorded.folder);
    await page.start(controller);
    const asked = await controller.requestRefresh();
    const folder = page.observe("a folder asks for no refresh");
    assert(asked === null, "a folder's press must ask for nothing");
    assert(
      JSON.stringify(folder.requests) === JSON.stringify(["GET /api/source/status"]),
      `a folder must post nothing: ${JSON.stringify(folder.requests)}`,
    );
    assert(folder.paint === null, "a folder has no row to paint");
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
    // The event log is about the server, whichever revision it shows (A4, review A of #629).
    "/api/event-log/client",
    "/api/event-log?client=k3v9q2zx",
    "/api/event-logs",
    "/api/tree?depth=1",
  ]) {
    answered.push((await guardedFetch(url)).status);
  }
  const guard = { page: recorded.refreshed.pin, sent, answered, reported };

  // What a page does when Back or Forward brings it back. The page was rendered for the
  // refreshed pin; the server answers the status it gave then, after the switch, or after
  // a restart on a folder. Each landing prints how many times it asked the status route
  // and how many times it reloaded.
  async function land(name, play) {
    let asked = 0;
    let reloads = 0;
    const waiting = [];
    const guardian = pinGuard.createHistoryGuard(
      {
        status() {
          asked += 1;
          return new Promise((resolve, reject) => {
            waiting.push({ resolve, reject });
          });
        },
        reload() {
          reloads += 1;
        },
      },
      recorded.refreshed.pin,
    );
    await play({
      guardian,
      async answer(status) {
        assert(waiting.length === 1, `${name}: one status request is waiting`);
        waiting.shift().resolve(status);
        await settle();
      },
      async fail() {
        assert(waiting.length === 1, `${name}: one status request is waiting`);
        waiting.shift().reject(new TypeError("fetch failed"));
        await settle();
      },
    });
    assert(waiting.length === 0, `${name}: no status request is left waiting`);
    return { landing: name, asked, reloads };
  }
  const landing = [
    await land("restored from the back/forward cache, nothing switched", async (page) => {
      void page.guardian.loaded("navigate");
      void page.guardian.shown(false);
      void page.guardian.shown(true);
      await page.answer(recorded.refreshed);
    }),
    await land("restored from the back/forward cache after a switch", async (page) => {
      void page.guardian.loaded("navigate");
      void page.guardian.shown(true);
      await page.answer(recorded.after_switch);
      // Shown again before the reload takes the page: it does not ask or reload twice.
      void page.guardian.shown(true);
      page.guardian.refused();
    }),
    await land("loaded from the HTTP cache by Back after a switch", async (page) => {
      void page.guardian.loaded("back_forward");
      void page.guardian.shown(false);
      // The page's first data request is refused before the status answers.
      page.guardian.refused();
      await page.answer(recorded.after_switch);
    }),
    await land("loaded by Back, nothing switched, another tab switches later", async (page) => {
      void page.guardian.loaded("back_forward");
      await page.answer(recorded.refreshed);
      // A refusal now is not this landing's: the freshness row offers the reload.
      page.guardian.refused();
    }),
    await land("an ordinary load whose data request is refused", async (page) => {
      void page.guardian.loaded("navigate");
      void page.guardian.shown(false);
      page.guardian.refused();
    }),
    await land("a reload, which is where a landing's reload ends", async (page) => {
      void page.guardian.loaded("reload");
      void page.guardian.shown(false);
      page.guardian.refused();
    }),
    await land("restored after the server restarted on a folder", async (page) => {
      void page.guardian.shown(true);
      await page.answer(recorded.folder);
    }),
    await land("restored while the server does not answer", async (page) => {
      void page.guardian.shown(true);
      await page.fail();
      void page.guardian.shown(true);
      await page.answer(null);
    }),
  ];

  // The same module as the server writes it into a pin's page: it finds the page's
  // commit, wraps the page's fetch, and listens for `pageshow`. Each page prints the
  // requests that reached the server (`+pin` when the request named the page's commit),
  // the events it announced, and whether it reloaded.
  async function servedPage(name, navigationType, statusNow, play) {
    const requests = [];
    const events = [];
    const listeners = new Map();
    let reloads = 0;
    const window = {
      METABROWSER_SOURCE_PIN: { pin: recorded.refreshed.pin, ref: recorded.refreshed.ref },
      location: {
        href: `http://127.0.0.1:8471/commit/${recorded.refreshed.pin}`,
        reload() {
          reloads += 1;
        },
      },
      performance: { getEntriesByType: () => [{ type: navigationType }] },
      addEventListener(type, handler) {
        listeners.set(type, [...(listeners.get(type) ?? []), handler]);
      },
      dispatchEvent(event) {
        events.push(`${event.type} ${event.detail.pin}`);
        return true;
      },
      async fetch(input, init) {
        const url = typeof input === "string" ? input : input.url;
        const named = new Headers(init?.headers).get(pinGuard.PIN_HEADER);
        requests.push(`GET ${url}${named === null ? "" : " +pin"}`);
        if (url === "/api/source/status") {
          return new Response(JSON.stringify(statusNow), { status: 200 });
        }
        // A data request: refused when the server serves another commit than it names.
        return named === statusNow.pin
          ? new Response("{}", { status: 200 })
          : new Response(JSON.stringify(recorded.pin_changed.body), {
              status: recorded.pin_changed.status,
              headers: recorded.pin_changed.headers,
            });
      },
    };
    window.window = window;
    class CustomEvent {
      constructor(type, init) {
        this.type = type;
        this.detail = init.detail;
      }
    }
    const context = vm.createContext({ window, CustomEvent, Headers, Request, Response, URL });
    const file = path.join(staticDir, "source-pin-guard.js");
    vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
    await settle();
    await play({
      window,
      async pageshow(persisted) {
        for (const handler of listeners.get("pageshow") ?? []) {
          handler({ persisted });
        }
        await settle();
      },
    });
    await settle();
    return { page: name, requests, events, reloads };
  }
  const wired = [
    await servedPage("first load", "navigate", recorded.refreshed, async (page) => {
      await page.window.fetch("/api/tree?depth=1");
      await page.pageshow(false);
    }),
    await servedPage("restored, nothing switched", "navigate", recorded.refreshed, async (page) => {
      await page.pageshow(true);
    }),
    await servedPage("restored after a switch", "navigate", recorded.after_switch, async (page) => {
      await page.pageshow(true);
    }),
    await servedPage(
      "loaded from the HTTP cache by Back after a switch",
      "back_forward",
      recorded.after_switch,
      async (page) => {
        await page.window.fetch("/api/tree?depth=1");
        await page.pageshow(false);
      },
    ),
    await servedPage(
      "another tab switched while this one stayed open",
      "navigate",
      recorded.after_switch,
      async (page) => {
        await page.window.fetch("/api/tree?depth=1");
      },
    ),
  ];

  // What a failed history page means for the Git panel.
  const failures = [
    { name: "a refresh moved the refs", ...recorded.history_stale, initial: false },
    { name: "the session expired", status: 410, body: {}, initial: false },
    { name: "the cursor was rejected", status: 400, body: {}, initial: false },
    { name: "a conflict without a code", status: 409, body: {}, initial: false },
    { name: "another tab switched the revision", ...recorded.pin_changed, initial: false },
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

  // Focused invariants of `describe`, outside the recorded conversation: the recording's
  // mirror has no pull request heads to pin. A pin on a pull request's head follows it as
  // a branch's does (`follows_moves` in mirror_refresh.py), and the row names the pull
  // request, not its raw ref. A commit opened by its ID that is such a head stays put
  // (`follows` false), and the head's new tip is offered instead.
  {
    const onHead = {
      ...recorded.stale,
      ref: "refs/pull/7/head",
      ref_name: "refs/pull/7/head",
      follows: true,
      pin: recorded.refreshed.pin,
      latest: recorded.refreshed.pin,
    };
    const followed = freshness.describe(onHead, {
      shown: { pin: recorded.stale.pin, ref: onHead.ref },
      nowMs: NOW_MS,
    });
    assert(
      followed.follow?.ref === onHead.ref &&
        followed.follow.commit === onHead.pin &&
        followed.offer === null &&
        followed.label === "Updating to pull request #7…" &&
        followed.detail === "Pull request #7 has moved, and this page follows it.",
      `a pull request's head is followed, and named: ${JSON.stringify(followed)}`,
    );
    const byId = { ...onHead, follows: false, pin: recorded.stale.pin };
    const offered = freshness.describe(byId, {
      shown: { pin: byId.pin, ref: byId.ref },
      nowMs: NOW_MS,
    });
    assert(
      offered.follow === null &&
        offered.offer?.kind === "switch" &&
        offered.offer.ref === byId.ref &&
        offered.offer.text === "Pull request #7 has moved" &&
        offered.offer.button === "Switch",
      `a commit opened by its ID is offered its ref's new tip: ${JSON.stringify(offered)}`,
    );
    // The row's own words start a sentence capitalized, and a ref's name stays its own.
    const gone = { ...byId, latest: byId.pin, ref_on_origin: false };
    const goneRow = freshness.describe(gone, {
      shown: { pin: gone.pin, ref: gone.ref },
      nowMs: NOW_MS,
    });
    const branchGone = freshness.describe(
      { ...gone, ref: "refs/heads/topic", ref_name: "topic" },
      { shown: { pin: gone.pin, ref: "refs/heads/topic" }, nowMs: NOW_MS },
    );
    assert(
      goneRow.detail.startsWith("Pull request #7 is no longer on the origin;") &&
        branchGone.detail.startsWith("topic is no longer on the origin;"),
      `a sentence the label starts: ${JSON.stringify({ goneRow, branchGone })}`,
    );

    // Taking the offer asks for the ref by name, which the server follows from then on,
    // naming the page's address, and lands where the answer says the page is, as a follow
    // does (B2 of review B on #745): in place on a file the new tip has, the root on one it
    // lacks. A refusal says so and keeps the offer.
    const page = createPage();
    page.setStatus(byId);
    const controller = freshness.createController(page.deps, {
      shown: { pin: byId.pin, ref: byId.ref },
    });
    await page.start(controller);
    page.observe("opened on a commit a pull request's head has moved on from");
    page.answerPost("/api/source/pin", 409, { code: "ref_moved" });
    await controller.acceptOffer();
    const refused = page.observe("the switch is refused");
    page.answerPost("/api/source/pin", 200, { changed: true, status: onHead, view_href: "/view/" });
    await controller.acceptOffer();
    const taken = page.observe("the switch is taken");
    const lacked = recorded.followed_elsewhere;
    page.setAddress(lacked.view);
    page.answerPost("/api/source/pin", 200, { ...lacked.answer, status: onHead });
    await controller.acceptOffer();
    const elsewhere = page.observe("the switch from a file the new tip lacks");
    controller.dispose();
    const asked = (view) => `POST /api/source/pin ${JSON.stringify({ ref: byId.ref, view })}`;
    assert(
      refused.requests.includes(asked("/view/")) &&
        refused.reloads === 0 &&
        refused.paint.error === "Could not switch to that commit." &&
        refused.paint.offer === "Pull request #7 has moved [Switch] → refs/pull/7/head" &&
        taken.requests.includes(asked("/view/")) &&
        taken.reloads === 1 &&
        taken.navigated === undefined &&
        elsewhere.requests.includes(asked(lacked.view)) &&
        elsewhere.reloads === 1 &&
        JSON.stringify(elsewhere.navigated) === JSON.stringify([lacked.answer.view_href]),
      `the offer switches to the ref by name and lands as a follow does: ${JSON.stringify({ refused, taken, elsewhere })}`,
    );
  }

  return { steps, asks, folder, checkoutBranch, guard, landing, wired, history, refreshNow };
}

run()
  .then(({ asks, folder, checkoutBranch, ...transcript }) => {
    const printed =
      process.argv[2] === "asks"
        ? { part: "asks", steps: asks }
        : process.argv[2] === "folder"
          ? { part: "folder", steps: folder }
          : process.argv[2] === "checkout-branch"
            ? { part: "checkout-branch", steps: checkoutBranch }
            : transcript;
    process.stdout.write(`${JSON.stringify(printed, null, 2)}\n`);
  })
  .catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
