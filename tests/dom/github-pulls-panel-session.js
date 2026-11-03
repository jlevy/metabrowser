// Browserless session: the Pulls tab's list, driven through the production browser code.
//
// The panel talks to the server through two GitHub plugin routes, and reads a row's record
// through a third. Every list answer here is one the in-process application gave while it
// served the stand-in in tests/github_pull_fixture.py, recorded in
// tests/fixtures/github-pulls-panel-responses.json; tests/test_github_pulls_panel_session.py
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
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/github-pulls-panel-responses.json"), "utf8"),
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
    count: model.count,
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
  const steps = [];

  // A page that is not a mirror's would read nothing here at all; this is a panel told only to
  // read, which asks for nothing more.
  let page = createPage();
  let controller = panel.createPullsController(page.deps, { filter: "all", current: null });
  void controller.start({ shown: false });
  await settle();
  steps.push(
    page.observe("the tab is not open: the list is read once, for later", controller, {
      paint: false,
    }),
  );
  await page.answer(recorded.absent);
  steps.push(page.observe("nothing is cached, and nothing asks to fetch it", controller));

  controller.setShown(true);
  await settle();
  steps.push(page.observe("the tab opens: its first read is a 304", controller, { paint: false }));
  await page.notModified();
  steps.push(page.observe("so the refresh is asked for", controller));
  await page.answer(recorded.refresh_started);
  steps.push(page.observe("the refresh started; the panel waits in the shape of rows", controller));

  await page.fire(panel.FAST_POLL_MS ?? 1000);
  await page.answer(recorded.pending);
  steps.push(page.observe("a fast poll while it runs", controller, { paint: false }));
  page.clock.now += panel.LONG_WAIT_MS;
  await page.fire(1000);
  await page.answer(recorded.pending);
  steps.push(page.observe("a long wait says why it may be waiting", controller));

  await page.fire(1000);
  await page.answer(recorded.current);
  steps.push(page.observe("the list arrives, newest first", controller));

  controller.setShown(false);
  steps.push(page.observe("hidden: no timer", controller, { paint: false }));
  controller.setShown(true);
  await settle();
  await page.notModified();
  steps.push(
    page.observe("shown again: one read, and a 304 paints nothing", controller, { paint: false }),
  );

  page.setVisible(false);
  controller.onVisibilityChange();
  steps.push(page.observe("the page is hidden: no timer", controller, { paint: false }));
  page.setVisible(true);
  controller.onVisibilityChange();
  await settle();
  await page.notModified();
  steps.push(
    page.observe("the page is shown again: it polls at once", controller, { paint: false }),
  );
  // Back brings the page from the back/forward cache after the pin moved: it polls before the
  // pin guard's own check, and the refusal is the guard's to answer, by a reload.
  page.setVisible(false);
  controller.onVisibilityChange();
  page.setVisible(true);
  controller.onVisibilityChange();
  await settle();
  await page.answer(recorded.pin_changed);
  steps.push(page.observe("a poll the pin guard refused: the list says nothing of it", controller));

  // The end of the rows held, and the next GitHub page. A reader's reaching it is the ask.
  const toEnd = controller.reachedEnd();
  await settle();
  steps.push(
    page.observe("the end of the list asks for the next page", controller, { paint: false }),
  );
  await page.answer(recorded.more_started);
  await toEnd;
  steps.push(page.observe("Load more says it is loading", controller));
  await page.fire(1000);
  await page.answer(recorded.more_refreshing);
  steps.push(page.observe("still reading it", controller, { paint: false }));
  await page.fire(1000);
  await page.answer(recorded.more_done);
  steps.push(
    page.observe("it is in, and the next window of rows is asked for", controller, {
      paint: false,
    }),
  );
  await page.answer(recorded.more_window);
  steps.push(page.observe("the rows after the first window are appended", controller));
  await controller.reachedEnd();
  await controller.loadMore();
  steps.push(page.observe("a complete list asks for nothing more", controller, { paint: false }));
  // A poll asks for the top window with its tag, however many rows are held: a list that did
  // not change is a 304, and not every held row again.
  await page.fire();
  await page.notModified();
  steps.push(
    page.observe("the next poll reads the top window, and it is unchanged", controller, {
      paint: false,
    }),
  );

  // The filters. Each is its own list, read when it is first chosen and kept.
  controller.setFilter("open");
  await settle();
  steps.push(page.observe("Open is chosen", controller, { paint: false }));
  await page.answer(recorded.open_current);
  steps.push(page.observe("its own rows: a draft and an open one", controller));
  controller.setFilter("all", { fromAddress: true });
  steps.push(page.observe("All again paints what it held at once", controller));
  await page.notModified();
  steps.push(page.observe("and its read is a 304", controller, { paint: false }));
  controller.setFilter("closed");
  await settle();
  // A newer answer wins: this request is let go when the filter changes again.
  controller.setFilter("all", { fromAddress: true });
  await settle();
  steps.push(
    page.observe("a filter left before it answered is let go", controller, { paint: false }),
  );
  await page.notModified();
  steps.push(page.observe("All's read is a 304", controller, { paint: false }));

  // Stale, and refreshing in the background with the rows in place.
  page.clock.now += 61_000;
  await page.fire();
  await page.answer(recorded.stale);
  steps.push(page.observe("a minute on, the list is stale, and asks", controller));
  await page.answer(recorded.refresh_again);
  await page.fire();
  await page.answer(recorded.stale_refreshing);
  steps.push(page.observe("it refreshes with its rows in place", controller));
  await page.fire();
  await page.answer(recorded.refreshed);
  // Another list file: the rows held past the top window are read again, once.
  await page.answer(recorded.refreshed_whole);
  steps.push(
    page.observe("refreshed: the whole range is read once, and no row repainted", controller),
  );
  controller.dispose();

  // Each way a refresh can end. A cached list shows under every one.
  const failures = {};
  for (const [name, answer] of Object.entries(recorded)) {
    if (name.startsWith("failed ")) {
      failures[name.slice("failed ".length)] = (({ notice, status, freshness }) => ({
        status,
        freshness,
        notice,
      }))(
        panel.describePulls(answer.body, {
          filter: "all",
          rows: answer.body.rows.map((row) => panel.describeRow(row, "octo/demo")),
          rowsVersion: 1,
          nowMs: Date.parse(answer.body.fetched_at) + 30_000,
          formatTime: (iso) => new Date(iso).toISOString(),
          more: false,
          waitedMs: 0,
          error: null,
        }),
      );
    }
  }

  // Retry: a reader's action, which the server may hold, and which says what happened.
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "all", current: null });
  void controller.start({ shown: true });
  await settle();
  await page.answer(recorded["failed network_error"]);
  steps.push(page.observe("offline: the rows show, with what to do", controller));
  await page.notModified().catch(() => {});
  const retried = controller.retry();
  await settle();
  steps.push(page.observe("Retry asks as a reader", controller, { paint: false }));
  await page.answer(recorded.refresh_again);
  await retried;
  steps.push(page.observe("the retry is under way", controller, { paint: false }));
  controller.dispose();

  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "all", current: null });
  void controller.start({ shown: true });
  await settle();
  await page.answer(recorded["failed rate_limited"]);
  steps.push(page.observe("rate limited: no Retry, and when it lifts", controller));
  controller.dispose();

  // A server with no repository: nothing is asked of it.
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "all", current: null });
  void controller.start({ shown: true });
  await settle();
  await page.answer(recorded.not_github);
  steps.push(page.observe("a server with no GitHub repository", controller));
  controller.dispose();

  // A mirror reads the list ahead of the tab, and starts its refresh, once and by itself.
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "all", current: null });
  void controller.start({ shown: false, refreshAhead: true });
  await settle();
  await page.answer(recorded.stale);
  steps.push(
    page.observe("a mirror's read ahead: a stale list asks", controller, { paint: false }),
  );
  await page.answer(recorded.refresh_again);
  steps.push(
    page.observe("and nothing polls a list that is not shown", controller, { paint: false }),
  );
  controller.dispose();

  // Keyboard, on a full window.
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "all", current: null });
  void controller.start({ shown: true });
  await settle();
  await page.answer(recorded.current);
  steps.push(
    page.observe("the first row takes Tab when none is current", controller, { paint: false }),
  );
  await page.answer(recorded.not_due).catch(() => {});
  controller.setShown(true);
  page.clock.now += 0;

  const movedAtTop = controller.move(-1);
  steps.push({
    ...page.observe("Up at the first row is clamped: no row opens", controller, { paint: false }),
    handled: movedAtTop,
  });
  controller.move(1);
  await settle();
  steps.push(
    page.observe("one press reads the row's record at once", controller, { paint: false }),
  );
  await page.record();
  steps.push(page.observe("and opens it, with what it read", controller, { paint: false }));

  // A key held down: only the two rows at each step.
  for (let step = 0; step < 40; step += 1) {
    controller.move(1, { repeat: true });
  }
  await settle();
  steps.push(
    page.observe("a key held for 40 rows", controller, { countMarks: true, paint: false }),
  );
  controller.released();
  await settle();
  const stopped = page.observe("the key is let go", controller, { paint: false });
  steps.push(stopped);
  await page.record();
  steps.push(page.observe("the row it stopped on opens", controller, { paint: false }));

  // A release the page never saw: the wait for a next key opens it.
  controller.move(1, { repeat: true });
  controller.move(1, { repeat: true });
  await page.fire(panel.WALK_SETTLE_MS);
  await settle();
  steps.push(
    page.observe("a key's release that was not seen: the wait opens it", controller, {
      paint: false,
    }),
  );
  // The newest opening wins, and the older read is let go.
  controller.move(1);
  await settle();
  controller.move(1);
  await settle();
  steps.push(page.observe("two presses: the older read is let go", controller, { paint: false }));
  await page.record();
  steps.push(page.observe("and only the newest opens", controller, { paint: false }));

  // Back lands while a press still waits for its row's record: the address wins, and the row
  // it left does not open over it.
  controller.move(1);
  await settle();
  controller.setCurrent(70);
  await page.record();
  steps.push(
    page.observe("Back while a row waits for its record: that row does not open", controller, {
      paint: false,
    }),
  );

  // The address moved: the row follows, and nothing is fetched or opened.
  controller.setCurrent(90);
  steps.push(page.observe("the address names another row", controller, { paint: false }));
  controller.setCurrent(null);
  steps.push(page.observe("the address names no row", controller, { paint: false }));
  controller.setCurrent(90);
  page.clock.now += 0;
  // A pointer rests on a row: its record is read once, and a click needs no second read.
  controller.peek(80);
  controller.peek(80);
  await settle();
  steps.push(page.observe("a pointer rests on a row: one read", controller, { paint: false }));
  await page.record();
  controller.activate(80);
  await settle();
  steps.push(
    page.observe("the click opens at once, with no second read", controller, {
      paint: false,
    }),
  );
  controller.dispose();

  // A page opened at a row the first window does not hold: further windows are read for it.
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "all", current: 5 });
  void controller.start({ shown: true });
  await settle();
  await page.answer(recorded.more_done);
  steps.push(
    page.observe("the current row is not in the first window", controller, {
      paint: false,
    }),
  );
  await page.answer(recorded.more_window);
  steps.push(
    page.observe("the next window holds it, and it is brought into view", controller, {
      paint: false,
    }),
  );
  // The end of the list: a held key stops there and does not ask again.
  const held = controller.snapshot().rows;
  assert(held === 102, "the two windows hold every row");
  controller.dispose();

  // In Closed, an address's row the first window does not hold is not chased: a filtered list
  // may not hold it at all, and the chase would read every window to the end for nothing.
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "closed", current: 50 });
  void controller.start({ shown: true });
  await settle();
  await page.answer(recorded.at_cap_window);
  steps.push(
    page.observe("in Closed, a row past the first window is not chased", controller, {
      paint: false,
    }),
  );
  controller.dispose();

  // A window and a poll that cross: the window lands first, and the poll, answered from another
  // list file, reads the whole range it now holds instead of dropping the rows just added.
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "all", current: null });
  void controller.start({ shown: true });
  await settle();
  await page.answer(recorded.more_done);
  page.observe("", controller, { paint: false });
  void controller.reachedEnd();
  await page.fire();
  steps.push(page.observe("a window and a poll are both asked for", controller, { paint: false }));
  await page.answer(recorded.more_window);
  await page.answer(recorded.refreshed);
  steps.push(
    page.observe("the window lands first, and the poll reads the whole range", controller, {
      paint: false,
    }),
  );
  await page.answer(recorded.refreshed_whole);
  const crossed = page.observe("so no row the window added is dropped", controller, {
    paint: false,
  });
  crossed.rowsHeld = controller.snapshot().rows;
  steps.push(crossed);
  controller.dispose();

  // The list at its cap, where a refresh found pull request 1001 opened, so every window moved
  // by a row. A window asked for the earlier rows, and the poll answered first: the window
  // follows rows the list no longer holds, so it is dropped and asked again from the new cursor.
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "closed", current: null });
  void controller.start({ shown: true });
  await settle();
  await page.answer(recorded.at_cap_window);
  page.observe("", controller, { paint: false });
  void controller.reachedEnd();
  await page.fire();
  steps.push(
    page.observe("a window and a poll of the list at its cap", controller, { paint: false }),
  );
  await page.answer(recorded.at_cap_moved, 1);
  steps.push(
    page.observe("the poll lands first: a pull request opened, and the rows moved", controller, {
      paint: false,
    }),
  );
  await page.answer(recorded.at_cap_window_2);
  steps.push(
    page.observe(
      "the window of the earlier rows is dropped, and asked after the new cursor",
      controller,
      {
        paint: false,
      },
    ),
  );
  await page.answer(recorded.at_cap_moved_after_902);
  const between = page.observe("so the row between the two cursors is held", controller, {
    paint: false,
  });
  Object.assign(between, { rowsHeld: controller.snapshot().rows, "holds 901": page.holds(901) });
  steps.push(between);
  controller.dispose();

  // A range read again while a window lands: the window makes the range short, so it is not
  // taken, and the next poll reads the list again.
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "closed", current: null });
  void controller.start({ shown: true });
  await settle();
  await page.answer(recorded.at_cap_window);
  void controller.reachedEnd();
  await settle();
  await page.answer(recorded.at_cap_window_2);
  page.observe("", controller, { paint: false });
  await page.fire();
  await page.answer(recorded.at_cap_moved);
  void controller.reachedEnd();
  await settle();
  steps.push(
    page.observe(
      "200 rows held: the range is read again, and a window asked while it is out",
      controller,
      {
        paint: false,
      },
    ),
  );
  await page.answer(recorded.at_cap_moved_after_801, 1);
  const appended = page.observe("the window lands first, and is appended", controller, {
    paint: false,
  });
  appended.rowsHeld = controller.snapshot().rows;
  steps.push(appended);
  await page.answer(recorded.at_cap_moved_whole);
  const short = page.observe("then the range, short of the window: it is not taken", controller, {
    paint: false,
  });
  short.rowsHeld = controller.snapshot().rows;
  steps.push(short);
  await page.fire();
  await page.poll(recorded.at_cap_moved);
  steps.push(page.observe("so the next poll reads the list again", controller, { paint: false }));
  controller.dispose();

  // A range read again that does not land: the reader chooses Open while it is out, and comes
  // back. The tag is taken only with the rows, so Closed's poll is not answered by a 304 over
  // the rows it held before.
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "closed", current: null });
  void controller.start({ shown: true });
  await settle();
  await page.answer(recorded.at_cap_window);
  void controller.reachedEnd();
  await settle();
  await page.answer(recorded.at_cap_window_2);
  await page.fire();
  await page.answer(recorded.at_cap_moved);
  page.observe("", controller, { paint: false });
  controller.setFilter("open");
  await settle();
  steps.push(
    page.observe("Open is chosen while Closed's range is read again", controller, { paint: false }),
  );
  await page.answer(recorded.open_current);
  controller.setFilter("closed", { fromAddress: true });
  await settle();
  steps.push(
    page.observe("Closed again: its poll names the tag of the rows it holds", controller, {
      paint: false,
    }),
  );
  await page.poll(recorded.at_cap_moved);
  steps.push(
    page.observe("so the list file it has not read is read again", controller, { paint: false }),
  );
  await page.answer(recorded.at_cap_moved_whole);
  const caughtUp = page.observe("and the pull request that opened is held", controller, {
    paint: false,
  });
  Object.assign(caughtUp, { rowsHeld: controller.snapshot().rows, "holds 1001": page.holds(1001) });
  steps.push(caughtUp);
  controller.dispose();

  // Disposal ends it: an answer after it paints nothing, and no timer is left.
  page = createPage();
  controller = panel.createPullsController(page.deps, { filter: "all", current: null });
  void controller.start({ shown: true });
  await settle();
  controller.dispose();
  await settle();
  const disposed = page.observe("dispose lets the read go", controller, { paint: false });
  disposed.timers = page.timerDelays();
  steps.push(disposed);

  // What the panel says at its cap, and of a list with cut rows.
  const atCap = recorded.at_cap.body;
  const held1000 = panel.describePulls(atCap, {
    filter: "closed",
    rows: Array.from({ length: atCap.fetched }, () => null),
    rowsVersion: 1,
    nowMs: Date.parse(atCap.fetched_at),
    formatTime: (iso) => iso,
    more: false,
    waitedMs: 0,
    error: null,
  });
  const cap = {
    count: held1000.count,
    listName: held1000.listName,
    loadMore: held1000.loadMore,
    github: held1000.github,
    notice: held1000.notice,
  };

  // What a row shows, whatever its author wrote. Text stays text; it is only ever a string.
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

  // GitHub spells an owner in its own case and a source is lowercased: the same repository.
  const spelled = panel.describeRow(
    { number: 8, state: "open", base_ref: "main", head_ref: "topic", head_repository: "OCTO/demo" },
    "octo/demo",
  ).refs;

  const formatTime = (iso) => new Date(iso).toISOString();
  const landing = {
    "a server with no repository": panel.describeLanding(recorded.not_github.body, formatTime),
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
    failures,
    cap,
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

class FakeNode {
  constructor(nodeName) {
    this.nodeName = nodeName;
    this.childNodes = [];
    this.parentNode = null;
  }
  append(...nodes) {
    for (const node of nodes) {
      this.adopt(typeof node === "string" ? new FakeText(node) : node);
    }
  }
  adopt(node) {
    if (node.nodeName === "#fragment") {
      for (const child of [...node.childNodes]) {
        this.adopt(child);
      }
      return;
    }
    node.parentNode?.drop(node);
    node.parentNode = this;
    this.childNodes.push(node);
  }
  drop(node) {
    this.childNodes.splice(this.childNodes.indexOf(node), 1);
    node.parentNode = null;
  }
  remove() {
    this.parentNode?.drop(this);
  }
  replaceChildren(...nodes) {
    for (const child of [...this.childNodes]) {
      this.drop(child);
    }
    this.append(...nodes);
  }
  contains(node) {
    for (let at = node; at; at = at.parentNode) {
      if (at === this) {
        return true;
      }
    }
    return false;
  }
  get textContent() {
    return this.childNodes.map((child) => child.textContent).join("");
  }
  set textContent(value) {
    this.replaceChildren(String(value));
  }
}

class FakeText extends FakeNode {
  constructor(data) {
    super("#text");
    this.data = data;
  }
  get textContent() {
    return this.data;
  }
  set textContent(value) {
    this.data = String(value);
  }
}

class FakeElement extends FakeNode {
  constructor(tag) {
    super(tag.toUpperCase());
    this.localName = tag;
    this.attributes = new Map();
    this.dataset = {};
    this.style = {};
    this.hidden = false;
    this.classes = new Set();
  }
  get classList() {
    const classes = this.classes;
    return {
      add(...names) {
        for (const name of names) {
          classes.add(name);
        }
      },
      remove(...names) {
        for (const name of names) {
          classes.delete(name);
        }
      },
      contains: (name) => classes.has(name),
      toggle(name, on) {
        const wanted = on ?? !classes.has(name);
        if (wanted) {
          classes.add(name);
        } else {
          classes.delete(name);
        }
        return wanted;
      },
    };
  }
  get className() {
    return [...this.classes].join(" ");
  }
  set className(value) {
    this.classes = new Set(String(value).split(/\s+/).filter(Boolean));
  }
  setAttribute(name, value) {
    if (name === "class") {
      this.className = value;
    } else if (name.startsWith("data-")) {
      this.dataset[name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] =
        String(value);
    } else {
      this.attributes.set(name, String(value));
    }
  }
  getAttribute(name) {
    return name === "class" ? this.className : (this.attributes.get(name) ?? null);
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  get firstElementChild() {
    return this.childNodes.find((child) => child instanceof FakeElement) ?? null;
  }
  addEventListener() {}
  querySelectorAll() {
    return [];
  }
  focus() {}
  scrollIntoView() {}
  set innerHTML(html) {
    this.childNodes = [];
    this.markup = html;
  }
}

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

async function paintStory(panel) {
  const { SLOW_POLL_MS } = await import(pathToFileURL(pagePath).href);
  const answers = [];
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
  let reachEnd = null;
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
    HTMLElement: FakeElement,
    Element: FakeElement,
    DOMParser: class {
      parseFromString() {
        return { body: { firstElementChild: new FakeElement("svg") } };
      }
    },
    IntersectionObserver: class {
      constructor(callback) {
        reachEnd = callback;
      }
      observe() {}
      disconnect() {}
    },
    fetch: (route, init) =>
      new Promise((resolve) => {
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
    const container = new FakeElement("div");
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
          scrollRoot: null,
          open: (route) => opened.push(route.number),
          file: null,
          fileHref: (number, path) => `/pull/${number}/files/${path}`,
          pageFor: () => null,
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
    const story = {
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
      reachEnd?.([{ isIntersecting: true }]);
      await settle();
      await answer(recorded.more_window);
    } finally {
      JSON.stringify = stringify;
    }
    story["a window of 2 appended to 100: rows built, aged, keyed"] = [built, aged, keyed];
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
    const chosen = wanted === "all" ? transcript : wanted === "2" ? rest : { steps };
    process.stdout.write(`${JSON.stringify(chosen, null, 2)}\n`);
  })
  .catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
