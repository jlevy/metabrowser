// Browserless session: the ref selector on a checkout that keeps a store of its origin,
// driven through the production browser code.
//
// A folder that is a repository's root lists its origin's branches and tags from a store
// Metabrowser keeps beside the checkout (metabrowser/checkout_store.py). Every response
// here is one the in-process application gave for a real checkout whose origin moved on
// after the clone, recorded in tests/fixtures/source-ref-selector-origin-responses.json;
// tests/test_source_ref_selector_origin_session.py replays the conversation against a
// real checkout and fails when the recording drifts.
//
// static/source-ref-selector.js loads whole, the way the shell links it. Timers and paint
// are injected, and each request waits until the step answers it. Each step prints the
// requests the selector made, what it would paint, and where it navigated.

const fs = require("node:fs");
const path = require("node:path");

const {
  assert,
  createPage,
  recorded: recordedMirror,
  repoRoot,
  selectorRuntime,
  settle,
} = require("./source-ref-selector-harness.js");

const recording = JSON.parse(
  fs.readFileSync(
    path.join(repoRoot, "tests/fixtures/source-ref-selector-origin-responses.json"),
    "utf8",
  ),
);

// The checkout's HEAD is on trunk, which server.py writes on the row
// (`data-working-branch`) and each listing reads again.
const checkout = (shown) => ({ shown, checkout: true, workingBranch: "trunk" });

async function run() {
  const steps = [];
  const onFile = { view: recording.views.m };

  // The folder is on its working tree, whose tab its list opens on. That tab and the
  // checkout's own branches are read from the checkout.
  let page = createPage(onFile);
  let selector = selectorRuntime.createSelector(page.deps, checkout(null));
  let opening = selector.open();
  await page.answer(recording.working_tree);
  await opening;
  await settle();
  steps.push(page.observe("the working tree's tab reads no store, so it asks nothing"));
  const own = selector.setKind("branch");
  await page.answer(recording.branches);
  await own;
  await settle();
  steps.push(page.observe("the checkout's own branches read no store, so their list asks nothing"));

  const remotes = selector.setKind("remote");
  await page.answer(recording.remotes);
  await remotes;
  await settle();
  steps.push(
    page.observe("the origin's branches are the store's, and the list says when it was fetched"),
  );
  await page.answer(recording.ask_fresh);
  steps.push(page.observe("the store was just fetched, so nothing is due and nothing is asked"));
  const tags = selector.setKind("tag");
  await page.answer(recording.tags);
  await tags;
  steps.push(
    page.observe("the origin's tags are the store's, beside the tag only the checkout has"),
  );
  const back = selector.setKind("remote");
  await page.answer(recording.remotes);
  await back;
  page.observe("back to the remote-tracking list");
  selector.close();

  // Opened again an hour on: the store is older than the server's window, so the ask
  // starts a fetch, and the list follows it to its end.
  opening = selector.open();
  await page.answer(recording.working_tree);
  await opening;
  const again = selector.setKind("remote");
  await page.answer(recording.remotes);
  await again;
  await settle();
  page.observe("opened again");
  await page.answer(recording.ask_started);
  steps.push(page.observe("a fetch the ask started is followed: the list is asked for again"));
  await page.answer(recording.remotes_fetching);
  steps.push(page.observe("while the store is fetched, the open list asks again after a wait"));
  await page.fireTimer(selectorRuntime.PULLS_POLL_MS);
  await page.answer(recording.remotes_fetched);
  steps.push(page.observe("the fetch ended: the origin's branch moved, and nothing more is asked"));

  // The navigation's Refresh, on this working tree's page: the reader asked, so the
  // store is fetched whatever its age (`fetchOrigin`), the open list is asked for again
  // in place and follows the fetch to its end. Read again with nothing moved, the list
  // draws nothing.
  const drawn = page.renders();
  const rereading = selector.reread();
  await page.answer(recording.remotes_fetched);
  await rereading;
  steps.push({
    ...page.observe("Refresh reads the open list again, and one that says the same is not drawn"),
    drawnAgain: page.renders() - drawn,
  });
  const fetching = selector.fetchOrigin();
  steps.push(page.observe("Refresh asks for the origin's fetch, as the reader's own"));
  await page.answer(recording.refresh_started);
  steps.push(page.observe("the fetch started, so the open list is asked for again"));
  await page.answer(recording.remotes_fetching);
  await fetching;
  steps.push(page.observe("the list says the fetch runs, and waits to ask again"));
  await page.fireTimer(selectorRuntime.PULLS_POLL_MS);
  await page.answer(recording.remotes_fetched);
  steps.push(page.observe("the fetch ended, and the list is the origin's as just fetched"));
  // A closed list asks for the fetch and reads nothing: it lists when it next opens.
  selector.close();
  page.observe("closed");
  const behind = selector.fetchOrigin();
  await page.answer(recording.refresh_started);
  await behind;
  await selector.reread();
  steps.push(page.observe("with the list closed, Refresh fetches and lists nothing"));
  const reopening = selector.open();
  await page.answer(recording.working_tree);
  await reopening;
  const remotesAgain = selector.setKind("remote");
  await page.answer(recording.remotes_fetched);
  await remotesAgain;
  await settle();
  await page.answer(recording.ask_fresh);
  page.observe("opened on the remote-tracking list again");

  const choosing = selector.choose("refs/remotes/origin/trunk");
  steps.push(page.observe("an origin branch is asked for by its ref"));
  await page.answer(recording.switch_origin_branch);
  await choosing;
  steps.push(page.observe("the page goes to the same file in the origin's revision"));
  selector.dispose();

  // The page reloaded on the origin's branch, a revision read from the store.
  const status = recording.switch_origin_branch.body.status;
  page = createPage(onFile);
  selector = selectorRuntime.createSelector(
    page.deps,
    checkout({ pin: status.pin, ref: status.ref }),
  );
  steps.push(page.observe("the button names the origin's branch as the checkout names it"));
  selector.dispose();

  // A server still making the store, and one whose origin refused.
  for (const [answer, step] of [
    [
      recording.acquiring_remotes,
      "while the store is first fetched, the list is the checkout's own",
    ],
    [recording.not_fetched_remotes, "with no store, the list is the checkout's own, and says so"],
    [
      recording.refused_remotes,
      "an origin that needs credentials is not fetched, and the list says so",
    ],
  ]) {
    page = createPage(onFile);
    selector = selectorRuntime.createSelector(page.deps, checkout(null));
    opening = selector.open();
    await page.answer(recording.working_tree);
    await opening;
    await settle();
    page.observe("opened");
    const listed = selector.setKind("remote");
    await page.answer(answer);
    await listed;
    await settle();
    await page.answer(recording.ask_refused);
    steps.push(page.observe(step));
    selector.dispose();
  }

  // A mirror, and a checkout that keeps no store, send no ask and paint no line.
  page = createPage({ view: null });
  selector = selectorRuntime.createSelector(page.deps, { shown: null });
  opening = selector.open();
  await page.answer(recordedMirror.branches);
  await opening;
  await settle();
  const quiet = page.observe("a mirror");
  assert(quiet.requests.length === 1, "a mirror's list made a second request");
  selector.dispose();
  const model = selectorRuntime.describe({
    shown: null,
    open: true,
    kind: "remote",
    query: "",
    listing: { ...recording.remotes.body, origin: null },
    loading: false,
    switching: false,
    error: null,
    checkout: true,
  });

  // What a row says where the reader's own `origin/<branch>` is not where the origin's
  // is. The recording's commits share one pinned date, so the two rows it has say only
  // that they differ; the same listing with the checkout's commit dated a day earlier
  // and a day later says which was committed later.
  const listed = recording.remotes.body;
  const tips = (/** @type {(at: number) => number} */ shift) =>
    selectorRuntime
      .describe({
        shown: null,
        open: true,
        kind: "remote",
        query: "",
        listing: {
          ...listed,
          refs: listed.refs.map((row) =>
            row.checkout?.commit
              ? {
                  ...row,
                  checkout: { ...row.checkout, committed_at: shift(row.checkout.committed_at) },
                }
              : row,
          ),
        },
        loading: false,
        switching: false,
        error: null,
        checkout: true,
      })
      .rows.map((row) => (row.own === null ? null : `${row.own.text}: ${row.own.tip}`));
  const ownDifference = {
    asRecorded: tips((at) => at),
    yoursEarlier: tips((at) => at - 86400)[0],
    yoursLater: tips((at) => at + 86400)[0],
    // The checkout's own branches are not the origin's, and say nothing.
    ownBranches: selectorRuntime
      .describe({
        shown: null,
        open: true,
        kind: "branch",
        query: "",
        listing: recording.branches.body,
        loading: false,
        switching: false,
        error: null,
        checkout: true,
      })
      .rows.map((row) => row.own),
  };
  assert(
    ownDifference.asRecorded.every((tip) => tip !== null),
    "a differing row said nothing",
  );

  return {
    steps,
    quietWithoutAStore: { asked: quiet.requests.slice(1), origin: model.origin },
    ownDifference,
  };
}

run().then(
  (result) => {
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  },
  (error) => {
    process.stderr.write(`${error.stack ?? error}\n`);
    process.exitCode = 1;
  },
);
