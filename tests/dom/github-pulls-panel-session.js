// Browserless session: the Pulls tab's list, driven through the production browser code.
//
// The panel talks to the server through two GitHub plugin routes, and reads a row's record
// through a third. Every list answer here is one the in-process application gave while it
// served the stand-in in tests/github_pull_fixture.py, recorded in
// the lifecycle, cached-window and changed-prefix fixtures; tests/test_github_pulls_panel_session.py
// replays that story and fails when the recording drifts, so this session never runs on an
// envelope a test wrote by hand. A row's record is the pull-request page's business and its
// recording's: an answer here stands for one, and only the fact that it was asked for counts.
//
// builtin_plugins/github/pulls-panel.js loads whole, as the shell loads the plugin. Timers,
// the clock, visibility, and paint are injected, and each request waits for the step to answer
// it, so a step can answer late or out of order. Each step prints the requests the panel made,
// the timer it left, how many times it painted, what it would paint, the row marks it made, and
// what it opened.

const fs = require("node:fs");
const optionalStacks = require("../fixtures/github-stacks-responses.json");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const recorded = Object.assign(
  {},
  ...[
    "github-pulls-panel-responses.json",
    "github-pulls-catalog-window-responses.json",
    "github-pulls-catalog-prefix-responses.json",
  ].map((name) => JSON.parse(fs.readFileSync(path.join(repoRoot, "tests/fixtures", name), "utf8"))),
);
// The recording holds each distinct window once: an answer whose rows an earlier answer carried
// names that answer, and reads here as those rows.
const heldRows = (rows) =>
  Array.isArray(rows)
    ? rows.map((row) => JSON.parse(row))
    : [rows.same_as].flat().flatMap((holder) => heldRows(recorded[holder].body.rows));
const answers = Object.values(recorded).filter((answer) => answer.body?.rows !== undefined);
const whole = answers.map((answer) => heldRows(answer.body.rows));
for (const [index, answer] of answers.entries()) {
  answer.body.rows = whole[index];
}
const panelPath = path.join(repoRoot, "src/metabrowser/builtin_plugins/github/pulls-panel.js");
// A list of changed files as the route answered it, for the row whose page is shown.
const filesRecorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/github-pull-files-responses.json"), "utf8"),
);
for (const envelope of Object.values(filesRecorded)) {
  envelope.rows = envelope.rows.map((row) => JSON.parse(row));
}
const pagePath = path.join(repoRoot, "src/metabrowser/builtin_plugins/github/pull-page.js");
// What the server answers of a record, for a page a reader's selection opens.
const pageRecorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/github-pull-page-responses.json"), "utf8"),
);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/** What a reader would see, a line per item; rows by their ends, as a full page is long. */
function summarize(model) {
  const rows = model.rows;
  const shown = rows.length > 4 ? [...rows.slice(0, 2), null, ...rows.slice(-2)] : rows;
  return present({
    filter: model.filter,
    status: model.status,
    skeleton: model.skeleton || null,
    listName: model.listName,
    origin: model.origin,
    count: model.count,
    window: model.window,
    progress: model.progress,
    freshness: model.freshness,
    empty: model.empty,
    notice: model.notice,
    loadMore: model.loadMore,
    github: model.github,
    live: model.live || null,
    rowsHeld: rows.length || null,
    rows:
      shown.length > 0
        ? shown.map((row) =>
            row === null ? "…" : `[${row.stateLabel}] ${row.title} | ${row.meta} | ${row.href}`,
          )
        : null,
  });
}

/** An object without what is empty: a transcript's length is bounded, and silence says as much. */
function present(fields) {
  return Object.fromEntries(
    Object.entries(fields).filter(
      ([, value]) => value !== null && !(Array.isArray(value) && value.length === 0),
    ),
  );
}

function createPage() {
  const log = [];
  const waiting = [];
  const timers = new Map();
  let nextTimer = 1;
  const clock = { now: Date.parse("2026-09-17T12:00:30Z") };
  let visible = true;
  let model = null;
  let paints = 0;
  const marks = [];
  const reveals = [];
  const opened = [];
  const filters = [];

  const deps = {
    request(method, route, options) {
      const body = options.body === undefined ? "" : ` ${JSON.stringify(options.body)}`;
      const etag = options.etag ? ` if-none-match ${options.etag}` : "";
      const line = `${method} ${route}${body}${etag}`;
      log.push(line);
      return new Promise((resolve, reject) => {
        const request = { route, method, etag: options.etag, resolve, reject };
        waiting.push(request);
        // As fetch does: an aborted request settles at once with an AbortError.
        options.signal?.addEventListener("abort", () => {
          const at = waiting.indexOf(request);
          if (at >= 0) {
            waiting.splice(at, 1);
            log.push(`aborted ${method} ${route}`);
            reject(Object.assign(new Error("aborted"), { name: "AbortError" }));
          }
        });
      });
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
    now: () => clock.now,
    isVisible: () => visible,
    formatTime: (iso) => new Date(iso).toISOString(),
    render(next) {
      model = next;
      paints += 1;
    },
    markCurrent(previous, next) {
      marks.push(`current ${previous} -> ${next}`);
    },
    markAnchor(previous, next, focus) {
      marks.push(`anchor ${previous} -> ${next}${focus ? " focus" : ""}`);
    },
    reveal(number) {
      reveals.push(number);
    },
    open(route) {
      opened.push({
        number: route.number,
        tab: route.tab,
        // A key's skim replaces the history entry, and a click or Enter pushes one.
        history: route.replace ? "replace" : "push",
        fetchAfterMs: route.reader.fetchAfterMs,
        initial: route.reader.initial === null ? null : "the record read for it",
      });
    },
    filterChanged(state) {
      filters.push(state);
    },
  };

  return {
    deps,
    clock,
    setVisible(value) {
      visible = value;
    },
    /** Answer the oldest waiting request (or the one at *index*) with a recorded answer. */
    async answer(recording, index = 0) {
      assert(waiting.length > index, "no request is waiting for an answer");
      const [request] = waiting.splice(index, 1);
      request.resolve({ status: recording.status, etag: recording.etag, body: recording.body });
      await settle();
    },
    /** Reject the oldest read as fetch does when the connection fails. */
    async reject() {
      assert(waiting.length > 0, "no request is waiting for rejection");
      waiting.shift().reject(new Error("connection failed"));
      await settle();
    },
    /**
     * Answer the oldest waiting poll as the route does when the list file is *recording*'s: a
     * 304 to the tag that file has, and that answer to any other tag.
     */
    async poll(recording) {
      assert(waiting.length > 0, "no request is waiting for an answer");
      const [request] = waiting.splice(0, 1);
      request.resolve(
        request.etag === recording.etag
          ? { status: 304, etag: request.etag, body: null }
          : { status: recording.status, etag: recording.etag, body: recording.body },
      );
      await settle();
    },
    /** Whether the list the panel would paint holds pull request *number*. */
    holds: (number) => model?.rows.some((row) => row.number === number) ?? false,
    /** The requests made since the last look. */
    requests: () => log.splice(0),
    /** Answer as the route does to a tag it still holds. */
    async notModified(index = 0) {
      assert(waiting.length > index, "no request is waiting for an answer");
      const [request] = waiting.splice(index, 1);
      assert(request.etag, "a 304 answers a request that named a tag");
      request.resolve({ status: 304, etag: request.etag, body: null });
      await settle();
    },
    /** Answer a read of a row's record: what is in it is the page's, and not asserted here. */
    async record(index = 0) {
      assert(waiting.length > index, "no request is waiting for an answer");
      const [request] = waiting.splice(index, 1);
      assert(request.route.startsWith("/api/plugin/github/pull?"), "not a read of a record");
      request.resolve({ status: 200, etag: '"record"', body: { state: "current" } });
      await settle();
    },
    waitingCount: () => waiting.length,
    rowsVersion: () => model?.rowsVersion,
    /** Run the timer with this delay, or the only one. */
    async fire(delayMs) {
      const match = [...timers.entries()].filter(
        ([, timer]) => delayMs === undefined || timer.delayMs === delayMs,
      );
      assert(match.length === 1, `expected one timer, found ${match.length}`);
      const [handle, timer] = match[0];
      timers.delete(handle);
      timer.callback();
      await settle();
    },
    timerDelays: () => [...timers.values()].map((timer) => timer.delayMs),
    /** What one step did, and everything it left behind. */
    observe(step, controller, options = {}) {
      const snapshot = controller.snapshot();
      const observed = {
        step,
        requests: log.splice(0),
        ...present({
          timer: snapshot.timer,
          marks: options.countMarks ? marks.length : [...marks],
          reveals: reveals.splice(0),
          opened: opened.splice(0),
          filterChanged: filters.splice(0),
        }),
        painted: paints,
      };
      if (options.paint !== false) {
        observed.paint = summarize(model);
      }
      paints = 0;
      marks.length = 0;
      return observed;
    },
  };
}

async function run() {
  const panel = await import(pathToFileURL(panelPath).href);
  if (process.argv.includes("selection")) {
    return { selection: await paintStory(panel, true) };
  }
  const steps = [];
  let page = createPage();
  let controller = panel.createPullsController(page.deps, { filter: "all", current: null });
  void controller.start({ shown: false });
  await settle();
  await page.answer(recorded.absent);
  steps.push(page.observe("hidden: one cache read and no provider work", controller));
  controller.setShown(true);
  await settle();
  await page.notModified();
  steps.push(page.observe("opening starts the all-history catalog job", controller));
  await page.answer(recorded.refresh_started);
  await page.fire(1000);
  await page.answer(recorded.pending);
  steps.push(page.observe("the catalog runs independently of the panel", controller));
  await page.fire(1000);
  await page.answer(recorded.current);
  steps.push(page.observe("the top cache page arrives", controller));
  await page.answer(recorded.more_window);
  steps.push(page.observe("cached windows fill only the display budget", controller));
  assert(controller.snapshot().rows === 102, "the real catalog holds 102 rows");
  controller.setShown(false);
  steps.push(page.observe("hidden: no presentation timer", controller, { paint: false }));
  controller.setShown(true);
  await settle();
  await page.notModified();
  steps.push(page.observe("reopening reads one tagged cache window", controller, { paint: false }));
  controller.setFilter("open");
  await settle();
  await page.answer(recorded.open_current);
  steps.push(page.observe("Open has its exact matching count", controller));
  controller.setFilter("closed");
  await settle();
  controller.setFilter("all", { fromAddress: true });
  await settle();
  await page.notModified();
  steps.push(page.observe("leaving a filter aborts its read", controller, { paint: false }));
  controller.dispose();

  // A large real catalog is read in bounded cache pages. Older backfill progress does not
  // replace the prefix or silently enlarge the display budget.
  page = createPage();
  page.clock.now = Date.parse(recorded.large_0.body.fetched_at) + 30_000;
  controller = panel.createPullsController(page.deps, { filter: "closed", current: null });
  void controller.start({ shown: true });
  await settle();
  for (let index = 0; index < 5; index += 1) {
    await page.answer(recorded[`large_${index}`]);
  }
  assert(controller.snapshot().rows === 500, "initial display must stop at 500");
  steps.push(page.observe("500 shown while the catalog continues in the background", controller));
  await page.answer(recorded.large_resume_started);
  const beforeProgress = page.rowsVersion();
  controller.onVisibilityChange();
  await settle();
  await page.answer(recorded.large_progress);
  assert(controller.snapshot().rows === 500, "catalog growth must not grow display");
  assert(page.rowsVersion() === beforeProgress, "older appends preserve prefix identity");
  steps.push(page.observe("6,000 cached: the same 500 rows stay in place", controller));
  void controller.loadMore();
  await settle();
  for (let index = 5; index < 10; index += 1) {
    await page.answer(recorded[`large_${index}`]);
  }
  assert(controller.snapshot().rows === 1000, "Fetch more grows display by 500");
  steps.push(
    page.observe("Fetch more displays another 500 cached rows without provider work", controller),
  );
  controller.onVisibilityChange();
  await settle();
  await page.answer(recorded.moved_0);
  assert(controller.snapshot().rows === 1000, "a changed prefix is staged before replacement");
  for (let index = 1; index < 10; index += 1) {
    await page.answer(recorded[`moved_${index}`]);
  }
  assert(page.holds(6001), "coherent staged prefix must include the new PR");
  steps.push(
    page.observe("a new PR revalidates the display through ten bounded cache pages", controller),
  );
  controller.dispose();

  // Holding a key marks only the two changed rows, with one cache-only detail read at rest.
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "all", current: null });
  void controller.start({ shown: true });
  await settle();
  await page.answer(recorded.current);
  await page.answer(recorded.more_window);
  page.observe("ready", controller, { paint: false });
  controller.move(-1);
  steps.push(page.observe("Up at the first row is clamped", controller, { paint: false }));
  controller.move(1);
  await settle();
  await page.record();
  steps.push(page.observe("one press opens with its cached record", controller, { paint: false }));
  for (let step = 0; step < 40; step += 1) {
    controller.move(1, { repeat: true });
  }
  await settle();
  steps.push(
    page.observe("a key held for 40 rows", controller, { countMarks: true, paint: false }),
  );
  controller.released();
  await settle();
  steps.push(page.observe("the key is let go", controller, { paint: false }));
  await page.record();
  steps.push(page.observe("the row it stopped on opens", controller, { paint: false }));
  controller.move(1);
  await settle();
  controller.setCurrent(70);
  await page.record();
  steps.push(page.observe("Back wins over a pending row opening", controller, { paint: false }));
  controller.peek(80);
  controller.peek(80);
  await settle();
  await page.record();
  controller.activate(80);
  await settle();
  steps.push(
    page.observe("a repeated hover and click reuse one cached record", controller, {
      paint: false,
    }),
  );
  controller.dispose();

  const failures = {};
  for (const [name, answer] of Object.entries(recorded)) {
    if (!name.startsWith("failed ")) {
      continue;
    }
    const model = panel.describePulls(answer.body, {
      filter: "all",
      rows: answer.body.rows.map((row) => panel.describeRow(row, "octo/demo")),
      rowsVersion: 1,
      nowMs: Date.parse(answer.body.fetched_at) + 30_000,
      formatTime: (iso) => new Date(iso).toISOString(),
      more: false,
      waitedMs: 0,
      error: null,
    });
    failures[name.slice("failed ".length)] = {
      status: model.status,
      freshness: model.freshness,
      notice: model.notice,
    };
  }
  for (const [name, context] of [
    ["a server with no GitHub repository", {}],
    ["a checkout whose origin cannot be listed", { checkout: true }],
  ]) {
    page = createPage();
    controller = panel.createPullsController(page.deps, {
      filter: "open",
      current: null,
      ...context,
    });
    void controller.start({ shown: true });
    await settle();
    await page.answer(recorded.not_github);
    steps.push(page.observe(name, controller));
    controller.dispose();
  }
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "all", current: null });
  void controller.start({ shown: true });
  await settle();
  controller.dispose();
  await settle();
  steps.push({
    ...page.observe("dispose aborts presentation reads", controller, { paint: false }),
    timers: page.timerDelays(),
  });

  const hostile = panel.describeRow(
    {
      number: 7,
      title: '<img src=x onerror="alert(1)"> & "quotes"',
      state: "closed",
      draft: false,
      merged: true,
      author: null,
      updated_at: "2026-09-17T12:00:00Z",
      base_ref: "main",
      head_ref: "<b>topic</b>",
      head_repository: null,
    },
    "octo/demo",
  );
  const spelled = panel.describeRow(
    { number: 8, state: "open", base_ref: "main", head_ref: "topic", head_repository: "OCTO/demo" },
    "octo/demo",
  ).refs;
  const formatTime = (iso) => new Date(iso).toISOString();
  const landing = {
    "a server with no repository": panel.describeLanding(recorded.not_github.body, formatTime),
    "a checkout whose origin cannot be listed": panel.describeLanding(
      recorded.not_github.body,
      formatTime,
      true,
    ),
    "a mirror": panel.describeLanding(recorded.current.body, formatTime),
    "a list with no rows, and no gh": panel.describeLanding(
      recorded.open_gh_missing.body,
      formatTime,
    ),
  };

  // The list's address on a first visit lands before the tab's refresh has run, so it reads
  // the list again while there is nothing to say yet, and stops once there is.
  page = createPage();
  const said = [];
  const following = panel.followLanding({
    request: page.deps.request,
    schedule: page.deps.schedule,
    cancel: page.deps.cancel,
    isVisible: page.deps.isVisible,
    formatTime,
    say: (line) => said.push(line),
  });
  await settle();
  const firstVisit = [];
  const look = (step) =>
    firstVisit.push({
      step,
      requests: page.requests(),
      said: said.splice(0),
      timers: page.timerDelays(),
    });
  look("it mounts and reads the list");
  await page.answer(recorded.landing_absent);
  look("nothing cached, and the refresh not yet asked: it reads again soon");
  await page.fire();
  await page.answer(recorded.landing_pending);
  look("the refresh is running: again at the fast poll");
  await page.fire();
  await page.answer(recorded.landing_gh_missing);
  look("the refresh failed: it says why, and reads no more");
  following.dispose();

  // The polling landing carries the checkout's context through its eventual refusal.
  page = createPage();
  const checkoutSaid = [];
  const checkoutLanding = panel.followLanding({
    request: page.deps.request,
    schedule: page.deps.schedule,
    cancel: page.deps.cancel,
    isVisible: page.deps.isVisible,
    formatTime,
    checkout: true,
    say: (line) => checkoutSaid.push(line),
  });
  await settle();
  await page.answer(recorded.not_github);
  landing["a polling checkout landing preserves its origin refusal"] = {
    said: checkoutSaid,
    requests: page.requests(),
    timers: page.timerDelays(),
  };
  checkoutLanding.dispose();

  const landingRecovery = [];
  for (const failure of ["connection", "non-envelope", "pin changed", "empty refreshing"]) {
    page = createPage();
    const recoverySaid = [];
    const recovery = panel.followLanding({
      request: page.deps.request,
      schedule: page.deps.schedule,
      cancel: page.deps.cancel,
      isVisible: page.deps.isVisible,
      formatTime,
      say: (line) => recoverySaid.push(line),
    });
    await settle();
    if (failure === "connection") {
      await page.reject();
    } else if (failure === "non-envelope") {
      await page.answer({ status: 503, etag: null, body: { error: "unavailable" } });
    } else {
      await page.answer(
        failure === "pin changed" ? recorded.pin_changed : recorded.landing_empty_refreshing,
      );
    }
    const before = { said: recoverySaid.splice(0), timers: page.timerDelays() };
    if (failure !== "pin changed") {
      await page.fire();
      await page.answer(
        failure === "empty refreshing" ? recorded.landing_found_rows : recorded.landing_gh_missing,
      );
    }
    landingRecovery.push({
      step: failure,
      before,
      after: { said: recoverySaid.splice(0), timers: page.timerDelays() },
      requests: page.requests(),
    });
    recovery.dispose();
  }

  return {
    steps,
    provider_calls: recorded.provider_calls,
    failures,
    hostile,
    spelled,
    landing,
    "the list's address, on a first visit": firstVisit,
    "the list's address recovers": landingRecovery,
    reader: await readerStory(),
    paint: await paintStory(panel),
  };
}

/**
 * The page a reader's selection opens: it is the selection that adds a record, as a press of
 * Fetch is, so only such a page asks, and past the bound on jobs it says why.
 */
async function readerStory() {
  const page = await import(pathToFileURL(pagePath).href);
  const story = [];
  /** One page, with the answers it gets by the order it asks. */
  async function opened(name, reader, answers, letGo = null) {
    const asked = [];
    let shown = null;
    const timers = new Map();
    let next = 1;
    const controller = page.createPullController(
      {
        request(method, route, options) {
          asked.push(`${method} ${route}${options.body ? ` ${JSON.stringify(options.body)}` : ""}`);
          const answer = method === "POST" ? answers.refresh : answers.pull;
          return Promise.resolve({ status: answer.status, etag: answer.etag, body: answer.body });
        },
        schedule(callback, delayMs) {
          const handle = next;
          next += 1;
          timers.set(handle, { callback, delayMs });
          return handle;
        },
        cancel: (handle) => timers.delete(handle),
        now: () => Date.parse("2026-09-17T12:00:30Z"),
        isVisible: () => true,
        render: (model) => {
          shown = model;
        },
        renderMarkdown() {},
        reload() {},
        navigate() {},
      },
      { number: 7, tab: "", reader },
    );
    await controller.start();
    await settle();
    const before = { message: shown.message, canRefresh: shown.canRefresh };
    const waits = [...timers.values()].map((timer) => timer.delayMs);
    for (const [handle, timer] of [...timers.entries()]) {
      if (timer.delayMs !== page.SLOW_POLL_MS && timer.delayMs !== page.FAST_POLL_MS) {
        timers.delete(handle);
        timer.callback();
      }
    }
    await settle();
    const entry = {
      name,
      asked: asked.splice(0),
      waits,
      before,
      after: { message: shown.message, canRefresh: shown.canRefresh },
    };
    if (letGo !== null) {
      // The key is let go where it opened this page: its wait runs out once more, and it asks.
      letGo();
      for (const [handle, timer] of [...timers.entries()]) {
        if (timer.delayMs !== page.SLOW_POLL_MS && timer.delayMs !== page.FAST_POLL_MS) {
          timers.delete(handle);
          timer.callback();
        }
      }
      await settle();
      entry["once let go"] = { asked: asked.splice(0), message: shown.message };
    }
    story.push(entry);
    controller.dispose();
  }
  const { absent, refresh_started: started, too_many: tooMany, current } = pageRecorded;
  await opened("an address alone fetches nothing", null, { pull: absent });
  await opened(
    "a click on a row with no record fetches it at once",
    { fetchAfterMs: 0, initial: null },
    { pull: absent, refresh: started },
  );
  await opened(
    "a key stopping on one waits, so tapping past it spends nothing",
    { fetchAfterMs: page.REFRESH_ASK_MS, initial: null },
    { pull: absent, refresh: started },
  );
  let holding = true;
  await opened(
    "a key still held waits out the page it opened, however long: it fetches nothing",
    { fetchAfterMs: page.REFRESH_ASK_MS, initial: null, walking: () => holding },
    { pull: absent, refresh: started },
    () => {
      holding = false;
    },
  );
  await opened(
    "past the bound on jobs it says why, and offers Fetch",
    { fetchAfterMs: 0, initial: null },
    { pull: absent, refresh: tooMany },
  );
  await opened(
    "a row with a record fetches nothing",
    { fetchAfterMs: 0, initial: { etag: current.etag, body: current.body } },
    { pull: { status: 304, etag: current.etag, body: null } },
  );
  return story;
}

// ── The paint ──────────────────────────────────────────────────
//
// mountPullsPanel builds the list's elements. Here it builds them in a stand-in for the DOM,
// just enough of one to hold elements, attributes, and text, so what the rows are made of is
// read back from the production code: the tree's roles, a title that is markup painted as
// text, an append that builds only the rows it adds, and ages told again as time passes. What
// only a browser has -- layout, focus rings, scrolling -- stays the paint exemption's.

const { FakeNode, FakeElement } = require("./pulls-test-dom.js");

/** One element as a line: its tag, classes, and attributes. */
function described(element) {
  const attributes = [...element.attributes].map(([name, value]) => `${name}="${value}"`);
  return [
    element.localName,
    element.className && `.${[...element.classes].join(".")}`,
    ...attributes,
  ]
    .filter(Boolean)
    .join(" ");
}

async function paintStory(panel, selection = false) {
  const { SLOW_POLL_MS } = await import(pathToFileURL(pagePath).href);
  const answers = [];
  const pageChanges = new Set();
  let pageHost = null;
  const timers = new Map();
  let nextTimer = 1;
  let now = Date.parse(recorded.more_done.body.fetched_at) + 30_000;
  let built = 0;
  // The work an append could spend on rows already painted: ages told, and rows keyed.
  let aged = 0;
  let keyed = 0;
  const document = {
    activeElement: null,
    visibilityState: "visible",
    addEventListener() {},
    createElement(tag) {
      if (tag === "li") {
        built += 1;
      }
      return new FakeElement(tag);
    },
    createDocumentFragment: () => new FakeNode("#fragment"),
    importNode: (node) => new FakeElement(node.localName),
  };
  /** @type {((entries: {isIntersecting: boolean}[]) => void) | null} */
  const saved = {};
  const globals = {
    document,
    window: {
      setTimeout(callback, delayMs) {
        timers.set(nextTimer, { callback, delayMs });
        nextTimer += 1;
        return nextTimer - 1;
      },
      clearTimeout: (handle) => timers.delete(handle),
    },
    getComputedStyle: () => ({ getPropertyValue: () => "24" }),
    HTMLElement: FakeElement,
    Element: FakeElement,
    MouseEvent: class {},
    DOMParser: class {
      parseFromString() {
        return { body: { firstElementChild: new FakeElement("svg") } };
      }
    },
    IntersectionObserver: class {
      observe() {}
      disconnect() {}
    },
    fetch: (route, init) =>
      route === "/api/plugin/github/stacks"
        ? Promise.resolve({
            status: optionalStacks.missing.status,
            headers: { get: () => optionalStacks.missing.etag },
            json: async () => optionalStacks.missing.body,
          })
        : new Promise((resolve) => {
            answers.push({ route, init, resolve });
          }),
  };
  for (const [name, value] of Object.entries(globals)) {
    saved[name] = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });
  }
  const realNow = Date.now;
  Date.now = () => now;
  async function answer(recording) {
    const { resolve } = answers.shift();
    resolve({
      status: recording.status,
      headers: { get: () => recording.etag },
      json: async () => recording.body,
    });
    await settle();
  }
  try {
    const mb = {
      ...require("./sdk-ref-fixture.js").refHelpers(document),
      perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
      filterControls: { groupHtml: () => "<div></div>", bind: () => () => {} },
      formatAge(seconds) {
        aged += 1;
        const minutes = Math.round((now / 1000 - seconds) / 60);
        return minutes < 60
          ? { label: `${minutes}m`, className: "age-min" }
          : { label: `${Math.round(minutes / 60)}h`, className: "age-hour" };
      },
      formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
    };
    // What the server answered, but with the first row's title written as markup: what is under
    // test is how a title is painted, and every title GitHub sends is a user's text.
    const first = structuredClone(recorded.more_done);
    first.body.rows[0].title = '<img src=x onerror="alert(1)"> & <b>bold</b>';
    first.body.rows[0].base_ref = "release/←base";
    first.body.rows[0].head_ref = "feature/←<literal>";
    first.body.rows[0].head_repository = "fork/demo";
    const container = new FakeElement("div");
    if (selection) {
      document.body = container;
      container.bounds = () => ({
        top: 0,
        bottom: 700,
        height: 700,
        left: 0,
        right: 800,
        width: 800,
      });
    }
    const opened = [];
    const current = first.body.rows[1].number;
    const mounted = panel.mountPullsPanel(
      container,
      {
        kind: "pull-request-list",
        pullsNav: {
          filter: "all",
          current,
          shown: true,
          refreshAhead: false,
          scrollRoot: selection ? container : null,
          open: (route) => opened.push(route.number),
          file: null,
          fileHref: (number, path) => `/pull/${number}/files/${path}`,
          pageFor: (number) => pageHost?.pageFor(number) ?? null,
          onPageChange: (listener) => {
            pageChanges.add(listener);
            return () => pageChanges.delete(listener);
          },
          filterChanged() {},
        },
      },
      mb,
    );
    await settle();
    await answer(first);
    // The row of the page shown opens its changed files, read from the cache: the tree's
    // session holds what they are, and this one where they hang.
    const filesRead = answers[0].route;
    await answer({ status: 200, etag: null, body: filesRecorded.comparison });
    const list = container.childNodes.find((node) => node.localName === "ul");
    const [hostile, shown] = list.childNodes;
    const row = (item) => item.firstElementChild;
    if (selection) {
      if (answers[0]?.route.includes("/pulls?")) {
        await answer(recorded.more_window);
      }
      const vm = require("node:vm");
      const runtime = {
        Object,
        Array,
        String,
        Error,
        TypeError,
        URIError,
        atob,
        btoa,
        TextDecoder,
        TextEncoder,
        Uint8Array,
        URLSearchParams,
      };
      runtime.window = runtime;
      for (const name of ["navigation.js", "pull-route.js"]) {
        vm.runInNewContext(
          fs.readFileSync(path.join(repoRoot, "src/metabrowser/static", name), "utf8"),
          runtime,
        );
      }
      const routes = runtime.MetabrowserPullRoute;
      const handles = new Map();
      const other = Number(row(hostile).dataset.number);
      let pathname = `/pull/${current}/files/src/app.txt`;
      let claim = 0;
      let releaseNext;
      let delayNext = false;
      function makePage(route) {
        let path = route.file ?? "src/app.txt";
        const listeners = [];
        const handle = {
          callbacks: listeners,
          onCurrentFile(listener) {
            listeners.push(listener);
            listener(path === null ? null : { path });
            return () => {};
          },
          emit(next) {
            path = next;
            for (const listener of listeners) {
              listener(path === null ? null : { path });
            }
          },
          fileForPath: (path) => ({ kind: "file", path }),
          scrollToFile: (path) => ({ kind: "file", path }),
          // A jump may report later; its explicit address must win while unavailable.
          showFile() {},
          setTab() {},
          land() {},
          flush() {},
          dispose() {},
        };
        handles.set(route.number, handle);
        return handle;
      }
      function address(href) {
        pathname = href;
        const route = routes.parsePull(href);
        mounted.setCurrent(route?.number ?? null, route?.file || null);
      }
      pageHost = routes.createPullPageHost({
        claim: () => ++claim,
        isCurrent: (ticket) => ticket === claim,
        pathname: () => pathname,
        pushHref: address,
        replaceHref: address,
        mount(_claim, route) {
          return delayNext && route.number === other
            ? new Promise((resolve) => {
                releaseNext = () => resolve(makePage(route));
              })
            : Promise.resolve(makePage(route));
        },
        mountList: async () => null,
      });
      const off = routes.onPageChange(() => {
        for (const listener of pageChanges) {
          listener();
        }
      });
      await pageHost.open({ number: current, tab: "files", file: "src/app.txt" });
      await settle();
      const walk = (node) => [node, ...node.childNodes.flatMap(walk)];
      const files = (number) =>
        walk(container).filter(
          (node) =>
            node.classList?.contains("github-pull-file-row") &&
            node.closest(".github-pull-files")?.getAttribute("id") ===
              `github-pull-files-${number}`,
        );
      const selected = (number) =>
        files(number)
          .filter((node) => node.getAttribute("aria-selected") === "true")
          .map((node) => node.getAttribute("href"));
      assert(selected(current).length === 1, "initial page observation selects its actual file");
      list.listeners.get("focusin")({ target: row(shown) });
      mounted.expand();
      const oldAnchor = walk(container).find(
        (node) =>
          node.getAttribute?.("tabindex") === "0" &&
          node.closest?.(".github-pull-files")?.getAttribute("id") ===
            `github-pull-files-${current}`,
      );
      assert(oldAnchor !== undefined, "positive control: reader has a roving anchor");
      const observations = { initial: selected(current) };
      mounted.setCurrent(current, null);
      observations.repeat = selected(current);
      handles.get(current).emit("src/app.txt");
      assert(
        selected(current).length === 1,
        "positive control: restore old active file before leaving",
      );
      delayNext = true;
      const opening = pageHost.open({
        number: other,
        tab: "files",
        reader: { fetchAfterMs: 0, initial: null },
      });
      await settle();
      observations.leaving = selected(current);
      assert(
        row(shown).getAttribute("aria-expanded") === "true",
        "reader-expanded old tree remains open",
      );
      assert(oldAnchor.getAttribute("tabindex") === "0", "leaving keeps the old roving anchor");
      handles.get(current).emit("docs/new.md");
      observations.ignoredOld = selected(current);
      releaseNext();
      await opening;
      await settle();
      const fileRequest = answers.findIndex((request) =>
        request.route.includes(`/pull-files?number=${other}`),
      );
      if (fileRequest !== -1) {
        const [request] = answers.splice(fileRequest, 1);
        request.resolve({
          status: 200,
          headers: { get: () => null },
          json: async () => ({ ...filesRecorded.comparison, number: other }),
        });
        await settle();
      }
      observations.arriving = selected(other);
      mounted.setCurrent(other, null);
      const rebound = handles.get(other);
      const staleSameHandle = rebound.callbacks.at(-1);
      // Rebinding the same handle creates a new subscription owner, not just the same PR.
      mounted.setCurrent(other, null);
      observations.sameHandle = selected(other);
      await pageHost.open({ number: other, tab: "files", file: "docs/new.md" });
      staleSameHandle({ path: "src/app.txt" });
      observations.explicit = selected(other);
      rebound.emit(null);
      observations.unavailable = selected(other);
      rebound.emit("docs/new.md");
      observations.reported = selected(other);
      delayNext = false;
      pathname = `/pull/${current}/files/src/app.txt`;
      const back = pageHost.onHistory(pathname, false);
      address(pathname);
      await settle();
      observations.history = selected(current);
      handles.get(other).emit("src/app.txt");
      observations.lateAfterHistory = selected(other);
      mounted.dispose();
      handles.get(current).emit("docs/new.md");
      pageHost.dispose();
      off();
      assert(observations.repeat.length === 1, "same-page route retains current diff selection");
      assert(
        observations.leaving.length === 0 && observations.ignoredOld.length === 0,
        "inactive page selection clears and ignores a stale callback",
      );
      assert(
        observations.arriving.length === 1 && observations.sameHandle.length === 1,
        "new and repeated active page observations select their file",
      );
      assert(
        observations.explicit[0]?.endsWith("/docs/new.md") &&
          observations.unavailable[0]?.endsWith("/docs/new.md"),
        "explicit file survives an unavailable jump report",
      );
      assert(
        observations.history.length === 1 && observations.lateAfterHistory.length === 0,
        "Back restores old page selection without a late new-page callback",
      );
      return {
        observations,
        back: back.action,
        readerExpansionRetained: true,
        rovingAnchorRetained: true,
        disposed: container.childNodes.length,
      };
    }

    const metadata = row(hostile).childNodes.find((node) =>
      node.classList?.contains("github-pulls-meta"),
    );
    const numberLabel = metadata.childNodes.find((node) =>
      node.classList?.contains("github-pulls-number"),
    );
    const identity = metadata.childNodes.find((node) =>
      node.classList?.contains("github-pull-identity"),
    );
    const authorLabel = identity.childNodes.find((node) =>
      node.classList?.contains("github-pulls-author"),
    );
    const branches = metadata.childNodes.find((node) =>
      node.classList?.contains("github-pulls-refs"),
    );
    assert(
      numberLabel.textContent === `#${first.body.rows[0].number}`,
      "number has its normal-size span",
    );
    assert(authorLabel.localName === "strong", "username is semantically bold");
    assert(authorLabel.textContent === first.body.rows[0].author, "username stays literal text");
    assert(branches.textContent.includes(" ← "), "branches keep their own smaller semantic span");
    const chips = branches.childNodes.filter((node) => node.classList?.contains("git-ref"));
    assert(chips.length === 2, "exactly two structured chips, including literal arrow refs");
    assert(chips[0].dataset.refCopy === "release/←base", "raw base ref remains intact");
    assert(
      chips[1].dataset.refCopy === "feature/←<literal>",
      "copy omits fork display qualification",
    );
    assert(
      chips[1].textContent === "fork:feature/←<literal>",
      "head label is literal and owner-qualified",
    );

    const status = container.childNodes.find((node) =>
      node.classList?.contains("github-pulls-status"),
    );
    const total = status.firstElementChild;
    assert(
      total.childNodes[0].localName === "strong" && total.childNodes[0].textContent === "102",
      "only the exact repository number is strong",
    );
    assert(
      total.childNodes[1].nodeName === "#text" &&
        total.childNodes[1].textContent === " PRs on octo/demo",
      "repository and label must remain plain text",
    );
    const story = {
      "only the exact number is bold": total.childNodes.map((node) => ({
        node: node.nodeName,
        text: node.textContent,
      })),
      "the list": described(list),
      "a row": [described(hostile), described(row(hostile))],
      "the row whose page is shown": described(row(shown)),
      "its parts": row(shown).childNodes.map(described),
      "its changed files, read from the cache": filesRead,
      "they hang under it as a group it owns": shown.childNodes.map(described),
      "a title written as markup is one text node": row(hostile).childNodes[2].childNodes.map(
        (node) => ({ node: node.nodeName, data: node.data }),
      ),
      "rows built for the first window": built,
    };
    // The end of the list comes into view: the next window is appended, and only its rows are
    // built, aged, and keyed, and none of the hundred already painted.
    built = 0;
    aged = 0;
    const stringify = JSON.stringify;
    JSON.stringify = (value, ...rest) => {
      if (value !== null && typeof value === "object" && "href" in value && "number" in value) {
        keyed += 1;
      }
      return stringify(value, ...rest);
    };
    try {
      // Initial cache filling already requested this second window.
      await settle();
      await answer(recorded.more_window);
    } finally {
      JSON.stringify = stringify;
    }
    story["a cached window of 2 auto-fills the budget: rows built, aged, keyed"] = [
      built,
      aged,
      keyed,
    ];
    story["rows held"] = list.childNodes.length;
    // Two hours on, the list unchanged: a poll's answer moves the freshness, and with it each
    // row's age, in place.
    const age = () => row(shown).childNodes[3].textContent;
    story["an age, before"] = age();
    built = 0;
    now += 2 * 60 * 60 * 1000;
    const poll = [...timers.entries()].find(([, timer]) => timer.delayMs === SLOW_POLL_MS);
    timers.delete(poll[0]);
    poll[1].callback();
    await settle();
    answers.shift().resolve({ status: 304, headers: { get: () => null }, json: async () => null });
    await settle();
    story["an age, two hours on"] = age();
    story["rows built to tell it"] = built;
    // Reader-opened trees can all be expanded together. Closing them must apply the bound
    // immediately, without waiting for another tree to be created.
    const many = list.childNodes
      .filter((item) => Number(row(item).dataset.number) !== current)
      .slice(0, 12);
    const click = (item) => list.listeners.get("click")({ target: row(item), preventDefault() {} });
    const retained = () =>
      list.childNodes.filter((item) =>
        item.childNodes.some(
          (child) => child instanceof FakeElement && child.classList.contains("github-pull-files"),
        ),
      ).length;
    for (const item of many) {
      click(item);
    }
    for (const item of many.slice(0, -1)) {
      click(item);
    }
    const whileExpanded = retained();
    assert(
      whileExpanded === panel.MAX_HELD_TREES + 2,
      "expanded and current trees must survive trimming",
    );
    click(many.at(-1));
    const afterClosingAll = retained();
    assert(afterClosingAll === panel.MAX_HELD_TREES + 1, "closed trees must be bounded on close");
    assert(
      row(many[0]).getAttribute("aria-owns") === null,
      "the longest-closed tree must go first",
    );
    assert(row(shown).getAttribute("aria-owns") !== null, "the shown page's tree must remain");
    assert(
      row(many.at(-1)).getAttribute("aria-owns") !== null,
      "the most recently closed tree must remain",
    );
    story["closing twelve expanded trees enforces retention immediately"] = {
      whileExpanded,
      afterClosingAll,
    };
    mounted.dispose();
    story["disposed: what is left in the tab"] = container.childNodes.length;
    return story;
  } finally {
    Date.now = realNow;
    for (const [name, descriptor] of Object.entries(saved)) {
      if (descriptor === undefined) {
        delete globalThis[name];
      } else {
        Object.defineProperty(globalThis, name, descriptor);
      }
    }
  }
}

// A step that awaits an answer nobody gives ends the process quietly, with nothing printed.
let finished = false;
process.on("beforeExit", () => {
  if (!finished) {
    process.stderr.write("the session stopped on a request no step answered\n");
    process.exitCode = 1;
  }
});

// Printed in two parts: this script prints the steps, and github-pulls-panel-second-session.js,
// which runs this same session, the rest. tryscript matches a command's expected output as one
// regular expression, and the whole transcript in one block is larger than V8 compiles.
// `--part 2` selects the second here, and `--part all` prints everything, for a reader.
run()
  .then((transcript) => {
    finished = true;
    const { steps, ...rest } = transcript;
    const part = process.argv.indexOf("--part");
    const wanted = part === -1 ? "1" : process.argv[part + 1];
    const chosen =
      wanted === "all" || wanted === "selection" ? transcript : wanted === "2" ? rest : { steps };
    process.stdout.write(`${JSON.stringify(chosen, null, 2)}\n`);
  })
  .catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
