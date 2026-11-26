// Browserless session: a served checkout's branch and tag selector, driven through the
// production browser code.
//
// A folder that is a repository's root has the selector a served mirror has
// (tests/dom/source-ref-selector-session.js), on the same two routes. Every response here
// is one the in-process application gave for a real checkout, recorded in
// tests/fixtures/source-ref-selector-checkout-responses.json;
// tests/test_source_ref_selector_session.py replays them against a real checkout and
// fails when the recording drifts.
//
// The conversation: its working tree's tab and its three lists, the tab each page's list
// opens on, a branch shown as a revision, the checked-out branch shown as its commit, a
// press on the Working tree tab, which switches to the files on disk, and an arrow key
// onto it, which does not, a `HEAD` moved in a terminal and named in place, and the
// reload it offers when the server shows something else. Then what the page's own data
// requests do while it switches (`hold`).

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
  steps.push(page.observe("opening asks where the working tree is, and for no refs"));
  await page.answer(recording.working_tree);
  await opening;
  steps.push(page.observe("the list opens on the working tree's tab, its one entry current"));

  // An arrow key along the tabs shows each one's list (`setKind`).
  const branchesListed = selector.setKind("branch");
  await page.answer(recording.branches);
  await branchesListed;
  steps.push(page.observe("the checkout's branches, the checked-out one first and marked"));

  const remotes = selector.setKind("remote");
  await page.answer(recording.remotes);
  await remotes;
  steps.push(page.observe("a checkout has a list more, its remote-tracking branches"));

  const tags = selector.setKind("tag");
  await page.answer(recording.tags);
  await tags;
  steps.push(page.observe("tags"));

  // A press on Working tree while the page already shows it has nothing to switch.
  const pressedShown = selector.pressKind("working_tree");
  await page.answer(recording.working_tree);
  await pressedShown;
  steps.push(page.observe("a press on Working tree while it is shown only shows its tab"));
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
  steps.push(page.observe("the button names the branch shown, and nothing else"));
  const reopened = selector.open();
  await page.answer(recording.branches_on_revision);
  await reopened;
  steps.push(page.observe("the list opens on Branches, where the branch shown is current"));

  // An arrow key onto Working tree shows where the files on disk are, and leaves the page
  // on the branch it shows.
  const arrowed = selector.setKind("working_tree");
  await page.answer(recording.working_tree_on_revision);
  await arrowed;
  steps.push(page.observe("an arrow key onto Working tree shows its entry and switches nothing"));
  const backToBranches = selector.setKind("branch");
  await page.answer(recording.branches_on_revision);
  await backToBranches;
  page.observe("back to branches");

  // The checked-out branch is a ref like any other: it shows its commit.
  const toCheckedOut = selector.choose("refs/heads/topic");
  await page.answer(recording.switch_checked_out);
  await toCheckedOut;
  steps.push(page.observe("the checked-out branch opens its commit, not the working tree"));
  selector.dispose();

  // The checked-out branch's own revision reads differently from its working tree: the
  // row names the branch alone. A press on the Working tree tab switches to the files on
  // disk, as choosing the tab's entry does (both call `chooseWorkingTree`).
  page = createPage(onRevisionReadme);
  selector = selectorRuntime.createSelector(
    page.deps,
    options(shownOf(recording.switch_checked_out)),
  );
  steps.push(page.observe("the checked-out branch's revision is not its working tree"));
  const onCheckedOut = selector.open();
  await page.answer(recording.branches_on_checked_out);
  await onCheckedOut;
  steps.push(page.observe("the checked-out branch is current in Branches once it is shown"));
  const toTree = selector.pressKind("working_tree");
  steps.push(page.observe("a press on Working tree asks for the files on disk, not for a ref"));
  await page.answer(recording.switch_working_tree);
  await toTree;
  steps.push(page.observe("the page goes to the same file in the folder"));
  selector.dispose();

  // The same chooser heads the Commits tab, which shows the history of the revision
  // chosen. A switch made there names no address, and the page reloads on Commits at
  // the tab's own landing, the newest commit of the history the server now serves.
  const onCommit = { view: `/commit/${recording.switch_checked_out.body.status.pin}`, tab: "git" };
  page = createPage(onCommit);
  selector = selectorRuntime.createSelector(page.deps, options(null));
  const fromCommits = selector.choose("refs/heads/feature");
  steps.push(page.observe("a switch on the Commits tab names no address"));
  await page.answer(recording.switch_from_commits);
  await fromCommits;
  steps.push(page.observe("the page reloads on the Commits tab's own landing"));
  selector.dispose();
  page = createPage({ view: "/view/", tab: "git" });
  selector = selectorRuntime.createSelector(
    page.deps,
    options(shownOf(recording.switch_from_commits)),
  );
  steps.push(page.observe("the reloaded Commits tab's row names the revision chosen there"));
  selector.dispose();

  // A switch to the working tree failed: the server is gone, since one that answers
  // serves its working tree. The list says so, and closing it clears it.
  page = createPage(onRevisionReadme);
  selector = selectorRuntime.createSelector(
    page.deps,
    options(shownOf(recording.switch_checked_out)),
  );
  const openedToFail = selector.open();
  await page.answer(recording.branches_on_checked_out);
  await openedToFail;
  const failedSwitch = selector.pressKind("working_tree");
  await page.fail();
  await failedSwitch;
  steps.push(page.observe("a switch that failed says so in the list, which stays open"));
  selector.close();
  steps.push(page.observe("closing the list clears it"));
  selector.dispose();

  // HEAD moved in a terminal, or an agent's, after the page was drawn on topic. The page's
  // watch on the checkout's HEAD says so (`headChanged`), and the row names the branch it
  // is on now, in place: nothing is navigated, and the list stays as it was, closed or open.
  page = createPage(onReadme);
  selector = selectorRuntime.createSelector(page.deps, options(null));
  const withTip = (step) => {
    const model = selectorRuntime.describe(selector.snapshot());
    return { ...page.observe(step), tip: model.viewTip, renders: page.renders() };
  };
  steps.push(withTip("a page drawn before a checkout in a terminal names the branch it was on"));
  const moved = selector.headChanged();
  steps.push(withTip("a HEAD that moved asks where it is, and for no refs, with the list closed"));
  await page.answer(recording.working_tree_moved);
  await moved;
  steps.push(withTip("the row names the branch HEAD is on now, in place"));
  // An open list asks for itself again, and its entry follows.
  const openedMoved = selector.open();
  await page.answer(recording.working_tree_moved);
  await openedMoved;
  steps.push(withTip("the open tab's entry names it too"));
  const same = selector.headChanged();
  await page.answer(recording.working_tree_moved);
  await same;
  steps.push(withTip("an answer that says the same draws nothing"));
  const detached = selector.headChanged();
  await page.answer(recording.working_tree_detached);
  await detached;
  steps.push(withTip("a HEAD detached since names its commit, in the row and the entry"));
  // The Branches list marks the branch checked out, so it follows as well.
  const listedDetached = selector.setKind("branch");
  await page.answer(recording.branches_moved);
  await listedDetached;
  steps.push(withTip("Branches as they were listed while HEAD was on feature"));
  const followed = selector.headChanged();
  await page.answer(recording.branches_detached);
  await followed;
  steps.push(withTip("the open Branches list follows: no branch is checked out"));
  // A change heard while a list the reader waits on is loading never replaces that ask,
  // which may have read HEAD before it moved: the list is asked for once more after it.
  const waited = selector.setKind("tag");
  const during = selector.headChanged();
  steps.push(withTip("a change heard during a load the reader waits on asks nothing yet"));
  await page.answer(recording.tags);
  await waited;
  await during;
  steps.push(withTip("and asks again once that load has answered"));
  await page.answer(recording.tags);
  selector.close();
  selector.dispose();
  // A refusal leaves what the row says.
  page = createPage(onReadme);
  selector = selectorRuntime.createSelector(page.deps, options(null));
  const refusedHead = selector.headChanged();
  await page.answer(recording.not_a_repository);
  await refusedHead;
  steps.push(withTip("a refused ask leaves the row as it was"));
  selector.dispose();

  // Back on the working tree.
  page = createPage(onReadme);
  selector = selectorRuntime.createSelector(page.deps, options(null));
  const openedAgain = selector.open();
  await page.answer(recording.working_tree);
  await openedAgain;
  page.observe("reopen");
  const sameTree = selector.chooseWorkingTree();
  await page.answer(recording.switch_working_tree_same);
  await sameTree;
  steps.push(page.observe("choosing the working tree's entry while it is shown only closes"));

  const reopenedForGone = selector.open();
  await page.answer(recording.working_tree);
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
  const beforeRefusal = selector.open();
  await page.answer(recording.working_tree);
  await beforeRefusal;
  const refusedGit = selector.setKind("branch");
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
  // read; then each kind of ref, which the row names alone, as a mirror's does. The row
  // is its label and the chooser's button in every one: `describe` has nothing else to
  // say of it.
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
    return `${model.button}${chip}${id} | ${model.viewTip}`;
  });

  // The tab a list opens on, by what the page shows: the one that holds it.
  const opens = Object.fromEntries(
    [
      ["a checkout's working tree", null, true],
      ["a checkout's branch", { pin, ref: "refs/heads/feature" }, true],
      ["a checkout's remote-tracking branch", { pin, ref: "refs/remotes/origin/feature" }, true],
      ["a checkout's tag", { pin, ref: "refs/tags/v1" }, true],
      ["a checkout's commit with no ref", { pin, ref: null }, true],
      ["a mirror's branch", { pin, ref: "refs/remotes/origin/feature" }, false],
      ["a mirror's tag", { pin, ref: "refs/tags/v1" }, false],
      ["a mirror's pull request", { pin, ref: "refs/pull/7/head" }, false],
    ].map(([what, shown, checkout]) => [what, selectorRuntime.openKind(shown, checkout)]),
  );

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
        working_tree: {
          current: true,
          head: null,
          head_name: null,
          head_commit: null,
          name,
          location,
        },
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
    opens,
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

runCheckout()
  .then((checkout) => {
    process.stdout.write(`${JSON.stringify({ checkout }, null, 2)}\n`);
  })
  .catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
