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
//
// The same module is a served checkout's selector, on the same two routes. `checkout` is
// that conversation, recorded from a folder that is a repository's root in
// tests/fixtures/source-ref-selector-checkout-responses.json: its working tree, its three
// lists, a branch shown as a revision, the checked-out branch shown as its commit, the
// way back to the working tree, and the reload it offers when the server shows something
// else.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const recorded = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/source-ref-selector-responses.json"), "utf8"),
);
const recordedCheckout = JSON.parse(
  fs.readFileSync(
    path.join(repoRoot, "tests/fixtures/source-ref-selector-checkout-responses.json"),
    "utf8",
  ),
);

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function loadProductionModule() {
  const context = {
    window: {},
    AbortController,
    console,
    JSON,
    Object,
    Promise,
    URLSearchParams,
  };
  context.window.window = context.window;
  vm.createContext(context);
  const file = path.join(staticDir, "source-ref-selector.js");
  vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  return context.window.MetabrowserSourceRefSelector;
}

const selectorRuntime = loadProductionModule();
assert(selectorRuntime, "the production module did not install its runtime");

// The pin guard, which a checkout's working-tree page takes with the selector's bundle.
// Its window here has no `fetch`, so it defines its functions and guards nothing.
function loadPinGuard() {
  const context = { window: {}, URL, Headers, Request, Promise, Object };
  context.window.window = context.window;
  vm.createContext(context);
  const file = path.join(staticDir, "source-pin-guard.js");
  vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  return context.window.MetabrowserSourcePinGuard;
}

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
    request(method, route, body, signal) {
      const line =
        body === undefined ? `${method} ${route}` : `${method} ${route} ${JSON.stringify(body)}`;
      log.push(line);
      return new Promise((resolve, reject) => {
        const request = { route, resolve };
        waiting.push(request);
        // As fetch does: an aborted request settles at once with an AbortError.
        signal?.addEventListener("abort", () => {
          const at = waiting.indexOf(request);
          if (at >= 0) {
            waiting.splice(at, 1);
            log.push(`aborted ${line}`);
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
// A checkout's selector adds what a mirror's has none of: the lists it offers, its
// working-tree row, the checked-out branch's badge, each row's chip, and its offer to
// reload. A mirror's paint is printed as it always was.
function paintOf(model) {
  if (model === null) {
    return null;
  }
  const checkout = model.workingTree !== null;
  const stale = model.stale === null ? {} : { stale: `${model.stale} [Reload]` };
  if (model.removed) {
    return { removed: true };
  }
  if (!model.open) {
    return { button: model.button, open: false, ...stale };
  }
  return {
    button: model.button,
    open: true,
    ...(checkout
      ? {
          workingTree: `Working tree: ${model.workingTree.detail}${model.workingTree.current ? " [current]" : ""}`,
          lists: model.kinds,
        }
      : {}),
    kind: model.kind,
    query: model.query,
    loading: model.loading,
    switching: model.switching,
    rows: model.rows.map(
      (row) =>
        `${row.name} ${row.commit}${row.default ? " [default]" : ""}${row.checkedOut ? " [checked out]" : ""}${row.current ? " [current]" : ""}${checkout ? ` (${row.chip} chip)` : ""}`,
    ),
    note: model.note,
    error: model.error,
    ...stale,
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

  // A filter asked while another is on its way aborts the older request.
  selector.setQuery("zzz");
  await page.fireTimer();
  selector.setQuery("feat");
  await page.fireTimer();
  await page.answer(recorded.filtered);
  steps.push(page.observe("a newer filter aborts the older request"));

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

  // Closing aborts a request still on its way.
  const reopened = selector.open();
  selector.close();
  await reopened;
  steps.push(page.observe("closing aborts the request on its way"));

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
  ].map((shown) => {
    // A pull request's number, which the button sets bold (docs/design-system.md, "Pull
    // Request Numbers"), shown in brackets after the words.
    const model = selectorRuntime.describe({ ...emptyState(), shown });
    return model.pullNumber === null ? model.button : `${model.button} [bold ${model.pullNumber}]`;
  });

  const copies = [
    "refs/remotes/origin/topic",
    "refs/tags/v1",
    `refs/remotes/origin/feature/${"long-".repeat(25)}←<literal>`,
  ].map((ref) => {
    const selected = selectorRuntime.describe({
      ...emptyState(),
      shown: { pin: branches.pin, ref },
    }).selectedRef;
    assert(
      selected.name === ref.replace(/^(?:refs\/remotes\/origin\/|refs\/tags\/)/, ""),
      "copy uses the full structured ref name",
    );
    return selected;
  });
  assert(
    selectorRuntime.describe({
      ...emptyState(),
      shown: { pin: branches.pin, ref: "refs/pull/7/head" },
    }).selectedRef === null,
    "a pull number is not a branch chip",
  );

  // Where a key moves focus in a list of three rows; -1 is the filter box.
  const keys = [];
  for (const [key, from] of [
    ["ArrowDown", -1],
    ["ArrowUp", -1],
    ["Home", -1],
    ["ArrowDown", 0],
    ["ArrowDown", 2],
    ["ArrowUp", 0],
    ["ArrowUp", 2],
    ["Home", 2],
    ["End", 0],
    ["Enter", 1],
  ]) {
    keys.push(`${key} from ${from}: ${selectorRuntime.moveRow(key, from, 3)}`);
  }
  keys.push(`ArrowDown from -1 in an empty list: ${selectorRuntime.moveRow("ArrowDown", -1, 0)}`);

  return { steps, labels, copies, keys, checkout: await runCheckout() };
}

// A served checkout: a folder that is a repository's root.
async function runCheckout() {
  const steps = [];
  const recording = recordedCheckout;
  const onReadme = { view: recording.views.readme };
  const options = (shown) => ({ shown, checkout: true });

  // The folder opens on its working tree, showing README.md.
  let page = createPage(onReadme);
  let selector = selectorRuntime.createSelector(page.deps, options(null));
  steps.push(page.observe("the button names the working tree"));

  const opening = selector.open();
  await page.answer(recording.branches);
  await opening;
  steps.push(page.observe("the working tree is listed above the branches, and is what is served"));

  const remotes = selector.setKind("remote");
  await page.answer(recording.remotes);
  await remotes;
  steps.push(page.observe("a checkout has a third list, its remote-tracking branches"));

  const tags = selector.setKind("tag");
  await page.answer(recording.tags);
  await tags;
  steps.push(page.observe("tags"));
  const branches = selector.setKind("branch");
  await page.answer(recording.branches);
  await branches;
  page.observe("back to branches");

  const toFeature = selector.choose("refs/heads/feature");
  steps.push(page.observe("a branch is asked for by its ref, with the folder's address"));
  await page.answer(recording.switch_branch);
  await toFeature;
  steps.push(page.observe("the page goes to the same file in the revision"));
  selector.dispose();

  // The page reloaded on feature, at the revision's address.
  const onRevisionReadme = { view: recording.views.readme_revision };
  page = createPage(onRevisionReadme);
  selector = selectorRuntime.createSelector(page.deps, options(shownOf(recording.switch_branch)));
  steps.push(page.observe("the button names the branch shown"));
  const reopened = selector.open();
  await page.answer(recording.branches_on_revision);
  await reopened;
  steps.push(page.observe("the branch shown is current, and the working tree no longer is"));

  // The checked-out branch is a ref like any other: it shows its commit.
  const toCheckedOut = selector.choose("refs/heads/topic");
  await page.answer(recording.switch_checked_out);
  await toCheckedOut;
  steps.push(page.observe("the checked-out branch opens its commit, not the working tree"));
  selector.dispose();

  page = createPage(onRevisionReadme);
  selector = selectorRuntime.createSelector(
    page.deps,
    options(shownOf(recording.switch_checked_out)),
  );
  const toTree = selector.chooseWorkingTree();
  steps.push(page.observe("the working tree is asked for by name, not by a ref"));
  await page.answer(recording.switch_working_tree);
  await toTree;
  steps.push(page.observe("the page goes to the same file in the folder"));
  selector.dispose();

  // Back on the working tree.
  page = createPage(onReadme);
  selector = selectorRuntime.createSelector(page.deps, options(null));
  const openedAgain = selector.open();
  await page.answer(recording.branches);
  await openedAgain;
  page.observe("reopen");
  const same = selector.chooseWorkingTree();
  await page.answer(recording.switch_working_tree_same);
  await same;
  steps.push(page.observe("choosing the working tree while it is shown only closes"));

  const reopenedForGone = selector.open();
  await page.answer(recording.branches);
  await reopenedForGone;
  page.observe("reopen");
  const missing = selector.choose("refs/heads/gone");
  await page.answer(recording.switch_missing);
  await missing;
  steps.push(page.observe("a ref gone from the checkout says so, and nothing is fetched"));
  selector.close();

  // Another tab switched the server: this page's next data request was refused.
  selector.servedChanged(recording.switch_branch.body.status.pin);
  steps.push(page.observe("a working-tree page left behind offers a reload"));
  selector.dispose();
  page = createPage(onRevisionReadme);
  selector = selectorRuntime.createSelector(page.deps, options(shownOf(recording.switch_branch)));
  selector.servedChanged("");
  steps.push(page.observe("a revision's page left behind offers one too"));
  selector.dispose();

  // A folder holding a `.git` that Git does not take for a repository's root: the server
  // drew the row from the entry, and the listing's refusal takes it away again.
  page = createPage(onReadme);
  selector = selectorRuntime.createSelector(page.deps, options(null));
  const hollow = selector.open();
  await page.answer(recording.not_a_repository);
  await hollow;
  steps.push(page.observe("a folder Git does not take for a repository loses its row"));
  selector.dispose();

  // A Git too old to be trusted never to fetch into a checkout: the server's own words.
  page = createPage(onReadme);
  selector = selectorRuntime.createSelector(page.deps, options(null));
  const refusedGit = selector.open();
  await page.answer(recording.unsupported_git);
  await refusedGit;
  steps.push(page.observe("an older Git is refused in the server's words"));
  selector.dispose();

  // A mirror has no working tree to choose, and its freshness row makes that offer.
  page = createPage(onRevisionReadme);
  selector = selectorRuntime.createSelector(page.deps, {
    shown: { pin: recorded.branches.body.pin, ref: recorded.branches.body.ref },
  });
  await selector.chooseWorkingTree();
  selector.servedChanged("");
  steps.push(page.observe("a mirror's selector asks for no working tree and offers no reload"));
  selector.dispose();

  const pin = recording.switch_branch.body.status.pin;
  const labels = [
    null,
    { pin, ref: "refs/heads/feature" },
    { pin, ref: "refs/remotes/origin/feature" },
    { pin, ref: "refs/tags/v1" },
    { pin, ref: null },
  ].map((shown) => {
    const model = selectorRuntime.describe({ ...emptyState(), shown, checkout: true });
    const chip = model.selectedRef === null ? "" : ` (${model.selectedRef.kind} chip)`;
    return `${model.button}${chip}`;
  });

  // What each kind of page names on its data requests, so a tab left behind is refused:
  // a commit, the working tree's word, or nothing, for a page with nothing to guard.
  const pinGuard = loadPinGuard();
  const named = (page, source) => {
    const shown = pinGuard.shownPin(page, source);
    if (shown === undefined) {
      return "nothing";
    }
    const token = shown ?? pinGuard.WORKING_TREE_PIN;
    const elsewhere = pinGuard.servesAnother(shown, { pin: shown === null ? pin : null });
    const here = pinGuard.servesAnother(shown, { pin: shown });
    return `${token}; refused when another is served: ${elsewhere}; while its own is: ${here}`;
  };
  const guard = {
    "a checkout's working tree": named(undefined, { working_tree: true }),
    "a checkout's revision": named({ pin, ref: "refs/heads/feature" }, { working_tree: false }),
    "a mirror's pin": named({ pin, ref: "refs/remotes/origin/feature" }, undefined),
    "a plain folder": named(undefined, undefined),
  };
  return { steps, labels, guard, hold: await runHold(recording, onReadme, options) };
}

// What the page's own data requests do while it switches (mb-bio7): from the moment the
// server is asked, it may serve the other subject while the page is still here, and would
// refuse them. So each waits: it goes at once when the page stays, and is held while the
// page goes, or until the guard's bound if the page is still there. The guard's own `fetch`
// wrapper and hold run here, over a network that logs what reaches it, with each hold's
// bound kept for a step to fire. A request whose signal is aborted is not sent, as `fetch`
// would not send it.
async function runHold(recording, onReadme, options) {
  const pinGuard = loadPinGuard();
  const timers = [];
  const hold = pinGuard.createSwitchHold((callback, ms) => timers.push({ callback, ms }));
  const network = [];
  const guarded = pinGuard.guardFetch(
    async (input, init) => {
      if (init?.signal?.aborted) {
        throw init.signal.reason;
      }
      network.push(`${input} ${new Headers(init?.headers).get(pinGuard.PIN_HEADER)}`);
      return { status: 200, headers: new Headers() };
    },
    pinGuard.WORKING_TREE_PIN,
    () => `http://127.0.0.1${onReadme.view}`,
    () => {},
    hold.waiting,
  );
  // The page refreshing its root's tallies, as app.js does after its first rows.
  const ask = (init) => guarded("/api/tree?depth=0", init);
  const observed = [];
  // *more* is read once the step has settled.
  const note = async (step, more = () => ({})) => {
    await settle();
    observed.push({
      step,
      sent: network.splice(0),
      bounds: timers.map((timer) => timer.ms),
      ...more(),
    });
  };
  // The oldest bound still to come, as its timer would fire it.
  const fireBound = () => timers.shift().callback();
  // The bounds of holds already ended, which find nothing left to release.
  const spendBounds = () => {
    for (const timer of timers.splice(0)) {
      timer.callback();
    }
  };
  const switching = () => {
    const page = createPage(onReadme);
    page.deps.hold = hold.hold;
    return { page, selector: selectorRuntime.createSelector(page.deps, options(null)) };
  };

  // A branch: the page goes, and the reader stops its navigation.
  let { page, selector } = switching();
  const toBranch = selector.choose("refs/heads/feature");
  void ask();
  await note("a request made while the switch is asked waits for the answer");
  await page.answer(recording.switch_branch);
  await toBranch;
  void ask();
  await note("a page that goes holds its requests until it is gone");
  fireBound();
  await note("a page still there at the bound sends them, to be refused");
  selector.dispose();

  // The working tree, which the page already shows: nothing changes.
  ({ page, selector } = switching());
  const same = selector.chooseWorkingTree();
  void ask();
  await page.answer(recording.switch_working_tree_same);
  await same;
  await note("choosing what the page shows sends them when it is answered");
  spendBounds();
  selector.dispose();

  ({ page, selector } = switching());
  const missing = selector.choose("refs/heads/gone");
  void ask();
  await page.answer(recording.switch_missing);
  await missing;
  await note("a switch refused sends them when it is answered");
  spendBounds();
  selector.dispose();

  // The page takes its selector away while the switch is asked: it stays where it is.
  ({ page, selector } = switching());
  const leftAlone = selector.choose("refs/heads/feature");
  void ask();
  selector.dispose();
  await page.answer(recording.switch_branch);
  await leftAlone;
  await note("a selector taken away during its switch sends them when it is answered");
  spendBounds();

  // A request given up while it is held, as a newer search or a timeout gives one up.
  ({ page, selector } = switching());
  const givenUp = selector.choose("refs/heads/gone");
  const controller = new AbortController();
  let settled = "pending";
  ask({ signal: controller.signal }).then(
    () => {
      settled = "answered";
    },
    (error) => {
      settled = error.name;
    },
  );
  controller.abort();
  await note("a request given up while it is held settles at once", () => ({ settled }));
  await page.answer(recording.switch_missing);
  await givenUp;
  await note("and is not sent when the hold ends");
  spendBounds();
  selector.dispose();

  // The back/forward cache shows the page again, and it switches once more before the
  // first switch's bound has fired.
  ({ page, selector } = switching());
  const first = selector.choose("refs/heads/feature");
  await page.answer(recording.switch_branch);
  await first;
  void ask();
  hold.release();
  await note("a page the back/forward cache shows again sends them at once");
  selector.dispose();
  ({ page, selector } = switching());
  const second = selector.choose("refs/heads/gone");
  void ask();
  fireBound();
  await note("the first switch's bound, firing during a second, sends nothing");
  await page.answer(recording.switch_missing);
  await second;
  await note("and the second sends them when it is answered");
  spendBounds();
  selector.dispose();
  return observed;
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
