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

const {
  assert,
  createPage,
  emptyState,
  recorded,
  repoRoot,
  selectorRuntime,
  settle,
  staticDir,
} = require("./source-ref-selector-harness.js");

const recordedCheckout = JSON.parse(
  fs.readFileSync(
    path.join(repoRoot, "tests/fixtures/source-ref-selector-checkout-responses.json"),
    "utf8",
  ),
);

// The pin guard, which a checkout's working-tree page takes with the selector's bundle.
// Its window here has no `fetch`, so it defines its functions and guards nothing.
function loadPinGuard() {
  const context = { window: {}, URL, Headers, Request, Response, Promise, Object };
  context.window.window = context.window;
  vm.createContext(context);
  const file = path.join(staticDir, "source-pin-guard.js");
  vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
  return context.window.MetabrowserSourcePinGuard;
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
  await page.answer(recorded.branches);
  await back;
  page.observe("back to branches");

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

  // Which rows a list draws: those in its view and the overscan on either side, however
  // many it holds, so a listing of every ref costs the page what its view holds, and the
  // row that takes Tab wherever it is, since focus may be on it and Tab from the filter
  // box goes to it. A view 320 px tall over rows 28 px tall, at the top, partway, and at
  // the end of 10,001 rows, with that row in the window or far from it; a short list;
  // and a list whose rows have not been measured.
  const overscan = selectorRuntime.ROWS_OVERSCAN;
  // Rows with a pull request are taller than the rest, so a row sits at its own offset:
  // *every* is how often a row has one (0 for none).
  const rowsOf = (count, every) =>
    Array.from({ length: count }, (_, at) => ({
      pulls: every > 0 && at % every === 0 ? [{ number: at + 1 }] : [],
    }));
  const windows = [
    [10001, 28, 28, 0, 0, 320, 0],
    [10001, 28, 28, 0, 0, 320, 9000],
    [10001, 28, 28, 0, 28 * 5000 + 10, 320, 0],
    [10001, 28, 28, 0, 28 * 5000 + 10, 320, 5003],
    [10001, 28, 28, 0, 28 * 10001 - 320, 320, 10000],
    [3, 28, 28, 0, 0, 320, 1],
    [10001, 0, 0, 0, 0, 0, 0],
    [0, 28, 28, 0, 0, 320, 0],
    // Every fourth row has a pull request and is 46 px tall: 10,001 rows are 340,034 px.
    [10001, 28, 46, 4, 0, 320, 0],
    [10001, 28, 46, 4, 46 * 2500 + 9 * 28 + 12, 320, 0],
    [10001, 28, 46, 4, 28 * 10001 + 18 * 2501 - 320, 320, 10000],
    // A list whose only row with a pull request is the first.
    [10001, 28, 46, 10001, 0, 320, 0],
  ].map(([count, plain, tall, every, scrollTop, viewHeight, roving]) => {
    const rows = rowsOf(count, every);
    const offsets = selectorRuntime.rowOffsets(rows, plain, tall);
    const { start, end, also } = selectorRuntime.rowWindow(offsets, scrollTop, viewHeight, roving);
    // The window is the rows that touch the view and the overscan on either side, found
    // here by looking at every row.
    if (offsets[count] > 0) {
      let first = count;
      let last = -1;
      for (let at = 0; at < count; at += 1) {
        if (offsets[at + 1] > scrollTop && at < first) {
          first = at;
        }
        if (offsets[at] < scrollTop + viewHeight) {
          last = at;
        }
      }
      assert(
        start === Math.max(0, first - overscan) && end === Math.min(count, last + 1 + overscan),
        "a window is its view and the overscan",
      );
    }
    assert(start >= 0 && end <= count && start <= end, "a window is inside the list");
    assert(
      count === 0 || (start <= roving && roving < end ? also === -1 : also === roving),
      "the row that takes Tab is drawn, in the window or as well as it",
    );
    const beside = also >= 0 ? ` and row ${also}` : "";
    const tallRows =
      every > 0 ? ` (every ${every === 10001 ? "10,001st" : `${every}th`} ${tall} px)` : "";
    return `${count} rows ${plain} px tall${tallRows}, scrolled ${scrollTop} px in ${viewHeight} px, Tab on row ${roving}: rows ${start} to ${end}${beside}`;
  });

  return { steps, labels, copies, keys, overscan, windows, checkout: await runCheckout() };
}

// A served checkout: a folder that is a repository's root.
async function runCheckout() {
  const steps = [];
  const recording = recordedCheckout;
  const onReadme = { view: recording.views.readme };
  // The page names the branch its working tree is on, as server.py writes it on the row
  // (`data-working-branch`): the fixture checkout's HEAD is on topic.
  const options = (shown) => ({ shown, checkout: true, workingBranch: "topic" });

  // The folder opens on its working tree, showing README.md: the row says so in words,
  // then names the branch the files on disk are on.
  let page = createPage(onReadme);
  let selector = selectorRuntime.createSelector(page.deps, options(null));
  steps.push(page.observe("the button names the working tree and the branch it is on"));

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
  steps.push(
    page.observe("the button names the branch shown, a revision, and offers the way back"),
  );
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

  // The checked-out branch's own revision reads differently from its working tree: the
  // row says "Revision", and its button goes back, as the list's Working tree row does
  // (both call `chooseWorkingTree`).
  page = createPage(onRevisionReadme);
  selector = selectorRuntime.createSelector(
    page.deps,
    options(shownOf(recording.switch_checked_out)),
  );
  steps.push(page.observe("the checked-out branch's revision is not its working tree"));
  const toTree = selector.chooseWorkingTree();
  steps.push(page.observe("the working tree is asked for by name, not by a ref"));
  await page.answer(recording.switch_working_tree);
  await toTree;
  steps.push(page.observe("the page goes to the same file in the folder"));
  selector.dispose();

  // The way back failed, with the list closed: the server is gone, since one that answers
  // serves its working tree. The row says so under its button, and opening the list, or
  // the next try, clears it.
  page = createPage(onRevisionReadme);
  selector = selectorRuntime.createSelector(
    page.deps,
    options(shownOf(recording.switch_checked_out)),
  );
  const failedBack = selector.chooseWorkingTree();
  await page.fail();
  await failedBack;
  steps.push(page.observe("a failed way back says so in the row, with the list closed"));
  const openedOnRefusal = selector.open();
  await page.answer(recording.branches_on_revision);
  await openedOnRefusal;
  selector.close();
  steps.push(page.observe("opening and closing the list clears it"));
  selector.dispose();

  // HEAD moved in a terminal after the page was drawn on feature. The row and its tooltip
  // name feature until a listing reads HEAD afresh, as the list's "checked out" badge does.
  page = createPage(onReadme);
  selector = selectorRuntime.createSelector(page.deps, {
    shown: null,
    checkout: true,
    workingBranch: "feature",
  });
  const withTip = (step) => ({
    ...page.observe(step),
    tip: selectorRuntime.describe(selector.snapshot()).viewTip,
  });
  steps.push(withTip("a page drawn before a switch in a terminal names the branch it was on"));
  const readsHead = selector.open();
  await page.answer(recording.branches);
  await readsHead;
  selector.close();
  steps.push(withTip("a listing names the branch HEAD is on now, in the row and its tooltip"));
  // The listing has no commit for a detached HEAD, so the row names no ref then.
  const readsDetached = selector.open();
  await page.answer(recording.branches_detached);
  await readsDetached;
  selector.close();
  steps.push(withTip("a HEAD detached since is the working tree's word alone"));
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
  steps.push(page.observe("an older Git is refused, and the page says so"));
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
  // The working tree on a branch, at a detached HEAD, and with a HEAD the server could not
  // read; then each kind of revision, which offers the way back.
  const labels = [
    [null, { workingBranch: "topic" }],
    [null, { workingCommit: pin }],
    [null, {}],
    [{ pin, ref: "refs/heads/feature" }, {}],
    [{ pin, ref: "refs/remotes/origin/feature" }, {}],
    [{ pin, ref: "refs/tags/v1" }, {}],
    [{ pin, ref: null }, {}],
  ].map(([shown, head]) => {
    const model = selectorRuntime.describe({ ...emptyState(), ...head, shown, checkout: true });
    const chip = model.selectedRef === null ? "" : ` (${model.selectedRef.kind} chip)`;
    const id = model.commitId === null ? "" : " (commit-ID face)";
    const back = model.back ? " [← Working tree]" : "";
    return `${model.button}${chip}${id}${back} | ${model.viewTip}`;
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

  // Where the Working tree row cuts a folder's path, keeping the folder's own name whole:
  // at the name the server sends, in whatever separator the platform joined the path with,
  // and nowhere at the home directory, whose path is `~` alone.
  const folders = Object.fromEntries(
    [
      ["under the home directory", "~/src/checkout", "checkout"],
      ["with the platform's other separator", "~\\src\\checkout", "checkout"],
      ["the home directory itself", "~", "reader"],
      ["outside the home directory", "/srv/checkout", "checkout"],
    ].map(([where, location, name]) => {
      const listing = {
        ...recording.branches.body,
        working_tree: { current: true, head: null, head_name: null, name, location },
      };
      const tree = selectorRuntime.describe({
        ...emptyState(),
        listing,
        checkout: true,
      }).workingTree;
      return [where, `${tree.directory}[${tree.base}]`];
    }),
  );
  return {
    steps,
    labels,
    guard,
    folders,
    hold: await runHold(recording, onReadme, options),
  };
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
  let resumePin = null;
  const guarded = pinGuard.guardFetch(
    async (input, init) => {
      if (init?.signal?.aborted) {
        throw init.signal.reason;
      }
      network.push(`${input} ${new Headers(init?.headers).get(pinGuard.PIN_HEADER)}`);
      if (input === "/api/source/pin") {
        await new Promise((resume) => {
          resumePin = resume;
        });
      }
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
  const post = () => guarded("/api/source/pin", { method: "POST" });
  const selecting = post();
  const competing = await guarded(
    new Request("http://127.0.0.1/api/source/pin", { method: "POST" }),
  );
  assert(competing.status === 409);
  const refusal = (await competing.json()).code;
  assert(refusal === "selection_busy");
  await note("a second source control cannot post while a ref switch is in flight", () => ({
    refusal,
  }));
  resumePin();
  await selecting;
  const retry = post();
  resumePin();
  assert((await retry).status === 200);
  await note("another source control can post after the first settles");
  return observed;
}

run()
  .then((transcript) => {
    process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
  })
  .catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
