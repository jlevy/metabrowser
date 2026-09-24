// Browserless session: a served mirror's branch and tag selector, driven through the
// production browser code.
//
// The selector talks to the server through two routes. Every response here is one the
// in-process application gave for a real mirror's listings and switches, recorded in
// tests/fixtures/source-ref-selector-responses.json; tests/test_source_ref_selector_session.py
// replays them against a real store and fails when the recording drifts, so this session
// never runs on an envelope a test wrote by hand.
//
// static/source-ref-selector.js loads whole, the way the shell links it. Timers and paint
// are injected, and each request waits until the step answers it, so a step can answer
// two requests out of order. Each step prints the requests the selector made, whether a
// filter pause is pending, what it would paint, and where it navigated.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/source-ref-selector-responses.json"), "utf8"),
);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function loadProductionModule() {
  const context = { window: {}, console, JSON, Object, Promise, URLSearchParams };
  context.window.window = context.window;
  vm.createContext(context);
  const file = path.join(staticDir, "source-ref-selector.js");
  vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  return context.window.MetabrowserSourceRefSelector;
}

const selectorRuntime = loadProductionModule();
assert(selectorRuntime, "the production module did not install its runtime");

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

/**
 * Injected browser facilities for one page: requests wait for the step to answer them.
 *
 * @param {{view: string | null}} page The page's pathname.
 */
function createPage(page) {
  const log = [];
  const waiting = [];
  const timers = new Map();
  let nextTimer = 1;
  const navigated = [];
  let model = null;

  const deps = {
    request(method, route, body) {
      log.push(
        body === undefined ? `${method} ${route}` : `${method} ${route} ${JSON.stringify(body)}`,
      );
      return new Promise((resolve) => {
        waiting.push({ route, resolve });
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
    render(next) {
      model = next;
    },
    navigate(href) {
      navigated.push(href);
    },
    currentView: () => page.view,
  };

  return {
    deps,
    /** Answer the oldest waiting request (or the one at *index*) with a recorded answer. */
    async answer(recording, index = 0) {
      assert(waiting.length > index, "no request is waiting for an answer");
      const [request] = waiting.splice(index, 1);
      request.resolve({ status: recording.status, etag: null, body: recording.body });
      await settle();
    },
    async fireTimer() {
      const pending = [...timers.entries()];
      assert(pending.length === 1, `expected one pending timer, found ${pending.length}`);
      const [handle, timer] = pending[0];
      assert(timer.delayMs === selectorRuntime.FILTER_DELAY_MS, "the pause is the filter delay");
      timers.delete(handle);
      timer.callback();
      await settle();
    },
    observe(step) {
      const observed = {
        step,
        requests: log.splice(0),
        filterPending: timers.size > 0,
        paint: paintOf(model),
      };
      if (navigated.length > 0) {
        observed.navigated = navigated.splice(0);
      }
      return observed;
    },
  };
}

// What the selector would show, one line per row, so a transcript reads as the page does.
function paintOf(model) {
  if (model === null) {
    return null;
  }
  if (!model.open) {
    return { button: model.button, open: false };
  }
  return {
    button: model.button,
    open: true,
    kind: model.kind,
    query: model.query,
    loading: model.loading,
    switching: model.switching,
    rows: model.rows.map(
      (row) =>
        `${row.name} ${row.commit}${row.default ? " [default]" : ""}${row.current ? " [current]" : ""}`,
    ),
    note: model.note,
    error: model.error,
  };
}

function shownOf(switched) {
  return { pin: switched.body.status.pin, ref: switched.body.status.ref };
}

async function run() {
  const steps = [];
  const branches = recorded.branches.body;
  const topicPage = { pin: branches.pin, ref: branches.ref };
  const onNotes = { view: recorded.views.notes };

  // A page on topic, showing NOTES.md.
  let page = createPage(onNotes);
  let selector = selectorRuntime.createSelector(page.deps, { shown: topicPage });
  steps.push(page.observe("the button names the served branch"));

  const opening = selector.open();
  steps.push(page.observe("opening asks for the branches"));
  await page.answer(recorded.branches);
  await opening;
  steps.push(page.observe("opening lists the branches"));

  selector.setQuery("f");
  selector.setQuery("fe");
  selector.setQuery("feat");
  steps.push(page.observe("typing waits for a pause"));
  await page.fireTimer();
  await page.answer(recorded.filtered);
  steps.push(page.observe("the pause asks once"));

  // Two filters in flight: the answer to the older one arrives last and is dropped.
  selector.setQuery("zzz");
  await page.fireTimer();
  selector.setQuery("feat");
  await page.fireTimer();
  await page.answer(recorded.filtered, 1);
  await page.answer(recorded.nothing);
  steps.push(page.observe("an older answer does not replace a newer one"));

  selector.setQuery("zzz");
  await page.fireTimer();
  await page.answer(recorded.nothing);
  steps.push(page.observe("a filter that matches nothing says so"));

  selector.setQuery("");
  await page.fireTimer();
  await page.answer(recorded.branches);
  const tags = selector.setKind("tag");
  await page.answer(recorded.tags);
  await tags;
  steps.push(page.observe("tags list newest first"));

  const back = selector.setKind("branch");
  await page.answer(recorded.page);
  await back;
  steps.push(page.observe("a list longer than a page says it stops short"));

  const refused = selector.setKind("tag");
  await page.answer(recorded.refused);
  await refused;
  steps.push(page.observe("a refused listing says so"));
  const branchesAgain = selector.setKind("branch");
  await page.answer(recorded.branches);
  await branchesAgain;
  page.observe("back to branches");

  selector.close();
  steps.push(page.observe("closing"));

  // Closing drops an answer still on its way.
  const reopened = selector.open();
  selector.close();
  await page.answer(recorded.branches);
  await reopened;
  steps.push(page.observe("an answer after closing is dropped"));

  const reopenedAgain = selector.open();
  await page.answer(recorded.branches);
  await reopenedAgain;
  page.observe("reopen");

  const away = selector.choose("refs/remotes/origin/feature");
  steps.push(page.observe("a switch is under way"));
  await page.answer(recorded.switch_away);
  await away;
  steps.push(page.observe("a branch without the page's file opens at the root"));
  selector.dispose();

  // The page reloaded onto feature at the root; back to topic, now showing README.md.
  const onReadme = { view: recorded.views.readme };
  page = createPage(onReadme);
  selector = selectorRuntime.createSelector(page.deps, {
    shown: shownOf(recorded.switch_away),
  });
  steps.push(page.observe("the button names the branch after the switch"));
  const keep = selector.choose("refs/remotes/origin/topic");
  await page.answer(recorded.switch_keep);
  await keep;
  steps.push(page.observe("a branch with the page's file keeps it"));
  selector.dispose();

  page = createPage(onReadme);
  selector = selectorRuntime.createSelector(page.deps, { shown: shownOf(recorded.switch_keep) });
  const openedSame = selector.open();
  await page.answer(recorded.branches);
  await openedSame;
  page.observe("reopen");
  const same = selector.choose("refs/remotes/origin/topic");
  await page.answer(recorded.switch_same);
  await same;
  steps.push(page.observe("choosing what the page shows only closes"));
  const reopenedForGone = selector.open();
  await page.answer(recorded.branches);
  await reopenedForGone;
  page.observe("reopen");

  const missing = selector.choose("refs/remotes/origin/gone");
  await page.answer(recorded.switch_missing);
  await missing;
  steps.push(page.observe("a ref gone from the mirror says so"));
  selector.dispose();

  // A page on a commit's diff has no /view/ address to keep.
  page = createPage({ view: `/commit/${branches.pin}` });
  selector = selectorRuntime.createSelector(page.deps, { shown: topicPage });
  const offView = selector.choose("refs/remotes/origin/feature");
  await page.answer(recorded.switch_no_view);
  await offView;
  steps.push(page.observe("a page off /view/ names no address and opens at the root"));
  selector.dispose();

  const labels = [
    { pin: branches.pin, ref: "refs/tags/v1" },
    { pin: branches.pin, ref: "refs/pull/7/head" },
    { pin: branches.pin, ref: null },
  ].map((shown) => selectorRuntime.describe({ ...emptyState(), shown }).button);

  return { steps, labels };
}

function emptyState() {
  return {
    shown: null,
    open: false,
    kind: "branch",
    query: "",
    listing: null,
    loading: false,
    switching: false,
    error: null,
  };
}

run()
  .then((transcript) => {
    process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
  })
  .catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
