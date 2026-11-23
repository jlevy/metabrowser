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

const checkout = (shown) => ({ shown, checkout: true });

async function run() {
  const steps = [];
  const onFile = { view: recording.views.m };

  // The folder is on its working tree. Its own branches are read from the checkout.
  let page = createPage(onFile);
  let selector = selectorRuntime.createSelector(page.deps, checkout(null));
  let opening = selector.open();
  await page.answer(recording.branches);
  await opening;
  await settle();
  steps.push(page.observe("an open list of a checkout makes a visible page's own ask, once"));
  await page.answer(recording.ask_fresh);
  steps.push(page.observe("the store was just fetched, so nothing is due and nothing is asked"));

  const remotes = selector.setKind("remote");
  await page.answer(recording.remotes);
  await remotes;
  steps.push(
    page.observe("the origin's branches are the store's, and the list says when it was fetched"),
  );
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
  await page.answer(recording.remotes);
  await opening;
  await settle();
  page.observe("opened again");
  await page.answer(recording.ask_started);
  steps.push(page.observe("a fetch the ask started is followed: the list is asked for again"));
  await page.answer(recording.remotes_fetching);
  steps.push(page.observe("while the store is fetched, the open list asks again after a wait"));
  await page.fireTimer(selectorRuntime.PULLS_POLL_MS);
  await page.answer(recording.remotes_fetched);
  steps.push(page.observe("the fetch ended: the origin's branch moved, and nothing more is asked"));

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
      "an origin that needs credentials is not fetched, and the list says why",
    ],
  ]) {
    page = createPage(onFile);
    selector = selectorRuntime.createSelector(page.deps, checkout(null));
    opening = selector.open();
    await page.answer(recording.branches);
    await opening;
    await settle();
    await page.answer(recording.ask_refused);
    page.observe("opened");
    const listed = selector.setKind("remote");
    await page.answer(answer);
    await listed;
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

  return {
    steps,
    quietWithoutAStore: { asked: quiet.requests.slice(1), origin: model.origin },
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
