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
// The same module is a served checkout's selector, on the same two routes:
// tests/dom/source-ref-selector-checkout-session.js is that conversation. The two are
// two sessions because one transcript of both is more than a golden can match.

const {
  assert,
  createPage,
  emptyState,
  recorded,
  selectorRuntime,
} = require("./source-ref-selector-harness.js");

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

  return { steps, labels, copies, keys, overscan, windows };
}

run()
  .then((transcript) => {
    process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
  })
  .catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
