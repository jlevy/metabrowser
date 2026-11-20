// Browserless session: the pull requests a branch heads, in the ref selector, driven
// through the production browser code.
//
// A branch that is the head of a pull request lists it on its row; the server reads the
// pull requests from what its provider has cached and never fetches. Every response here
// is one the in-process application gave for a mirror whose repository's catalog was empty,
// then half full and still being filled, then whole, recorded in
// tests/fixtures/source-ref-selector-responses.json by
// tests/test_source_ref_selector_session.py. The selector's own conversation is
// tests/dom/source-ref-selector-session.js; the page and its printing are shared
// (tests/dom/source-ref-selector-harness.js).
//
// A list opened before the pull requests are cached asks again, quietly, while the server
// fills them; what an ask finds that moved is patched into the rows, and one that finds
// nothing moved draws nothing; the filter finds a branch by its pull request, and says so
// while the server has only some of them; a list that is laid out again keeps the reader's
// place.

const {
  createPage,
  emptyState,
  recorded,
  selectorRuntime,
} = require("./source-ref-selector-harness.js");

async function run() {
  const steps = [];
  const branches = recorded.branches.body;
  const topicPage = { pin: branches.pin, ref: branches.ref };
  const onNotes = { view: recorded.views.notes };
  let page;
  let selector;

  // A branch that is the head of a pull request lists it on its row: the server reads the
  // pull requests from what its provider has cached and never fetches, so a list opened
  // before they are cached shows none and asks again, quietly, while the server fills
  // them. The listings are the ones the application gave for a mirror whose repository's
  // catalog was empty, then half full and still being filled, then whole.
  page = createPage(onNotes);
  selector = selectorRuntime.createSelector(page.deps, { shown: topicPage });
  const waiting = selector.open();
  await page.answer(recorded.pending);
  await waiting;
  steps.push(
    page.observe("pull requests not cached yet: the rows show none, and the list will ask again"),
  );
  await page.fireTimer(selectorRuntime.PULLS_POLL_MS);
  steps.push(page.observe("asking again shows nothing while it waits"));
  await page.answer(recorded.filling);
  steps.push(
    page.observe(
      "a branch shows the pull requests the server has, and it asks again until it has all",
    ),
  );
  await page.fireTimer(selectorRuntime.PULLS_POLL_MS);
  await page.answer({ status: 500, body: null });
  steps.push(page.observe("an ask that is refused leaves the rows as they are and asks no more"));
  selector.close();
  const reopenedForPulls = selector.open();
  await page.answer(recorded.annotated);
  await reopenedForPulls;
  steps.push(
    page.observe("a full cache lists each branch's pull requests, open first, and asks no more"),
  );
  selector.setQuery("#1");
  await page.fireTimer();
  await page.answer(recorded.by_number);
  steps.push(page.observe("the filter finds a branch by its pull request's number"));
  selector.setQuery("start the");
  await page.fireTimer();
  await page.answer(recorded.by_title);
  steps.push(page.observe("and by the words of its title, whatever its name says"));
  const pullTags = selector.setKind("tag");
  await page.answer(recorded.tags_with_pulls);
  await pullTags;
  steps.push(page.observe("a list of tags has no pull requests, and the filter finds tags"));
  selector.dispose();

  // While the server fills its pull requests the list asks again, and what it draws is what
  // moved. An ask that finds the same listing draws nothing, so the rows keep their focus
  // and their tooltips and a press in progress; the pull requests a poll finds for rows the
  // list already has are patched into them (`sameRefLines`).
  page = createPage(onNotes);
  selector = selectorRuntime.createSelector(page.deps, { shown: topicPage });
  const filling = selector.open();
  await page.answer(recorded.filling);
  await filling;
  steps.push(page.observe("the server has half its pull requests, and is filling the rest"));
  const drawn = page.renders();
  await page.fireTimer(selectorRuntime.PULLS_POLL_MS);
  await page.answer(recorded.filling);
  const unchanged = page.observe("an ask that finds the listing unchanged draws nothing");
  unchanged.rendered = page.renders() - drawn;
  steps.push(unchanged);
  // A filter typed while the next ask is due goes first: the ask waits, and is made again.
  selector.setQuery("try");
  await page.fireTimer(selectorRuntime.PULLS_POLL_MS);
  steps.push(page.observe("an ask that comes due while a filter is typed waits for it"));
  await page.fireTimer();
  await page.answer(recorded.filling_by_title);
  steps.push(page.observe("the filter finds what is cached, and the list says it may find more"));
  selector.setQuery("zzz");
  await page.fireTimer();
  await page.answer(recorded.filling_nothing);
  steps.push(page.observe("a filter that finds nothing says so, and that it may find more later"));
  selector.dispose();

  // Closing the list stops the asking, so nothing is left running for a list nobody sees.
  page = createPage(onNotes);
  selector = selectorRuntime.createSelector(page.deps, { shown: topicPage });
  const closing = selector.open();
  await page.answer(recorded.pending);
  await closing;
  selector.close();
  steps.push(page.observe("closing stops asking for pull requests"));
  selector.dispose();

  // Where the list scrolls to when its rows are laid out again, as they are when pull
  // requests arrive for rows above the view: 100 rows, 28 px tall, in a view 112 px tall,
  // of which the first *grown* have a pull request and are 46 px tall.
  const refs = Array.from({ length: 100 }, (_, at) => `refs/remotes/origin/b-${at}`);
  const layout = (grown) =>
    selectorRuntime.rowOffsets(
      refs.map((_, at) => ({ pulls: at < grown ? [{}] : [] })),
      28,
      46,
    );
  const anchors = [
    ["at the top, nothing above to move", { grown: 0, now: 3, top: 0, focused: null }],
    [
      "the top row stays where it was while rows above it grow",
      { grown: 0, now: 5, top: 28 * 20 + 10, focused: null },
    ],
    [
      "rows that are the same stay where they are",
      { grown: 0, now: 0, top: 28 * 20, focused: null, after: layout(0) },
    ],
    [
      "the foot stays the foot, as End left it",
      { grown: 0, now: 5, top: 28 * 100 - 112, focused: null },
    ],
    [
      "a focused row in view stays in view",
      { grown: 0, now: 25, top: 28 * 20, focused: "refs/remotes/origin/b-22" },
    ],
    [
      "a focused row out of view is left where it is",
      { grown: 0, now: 25, top: 28 * 60, focused: "refs/remotes/origin/b-5" },
    ],
  ].map(([what, { grown, now, top, focused, after }]) => {
    const before = { refs, offsets: layout(grown) };
    const next = { refs, offsets: after ?? layout(now) };
    const scrolled = selectorRuntime.anchoredScroll(before, next, top, 112, focused);
    const row = (offsets, at) => offsets[at];
    const first = (offsets, y) =>
      offsets.findIndex((offset, at) => offset + (offsets[at + 1] - offset) > y);
    return `${what}: ${top} -> ${scrolled} px, the row at the top ${first(before.offsets, top)} -> ${first(next.offsets, scrolled)} (its top ${row(before.offsets, first(before.offsets, top))} -> ${row(next.offsets, first(next.offsets, scrolled))})`;
  });
  // A row gone from the list leaves the place where it was, and a list shorter than its
  // view is at its top.
  const gone = selectorRuntime.anchoredScroll(
    { refs, offsets: layout(0) },
    {
      refs: refs.slice(0, 3),
      offsets: selectorRuntime.rowOffsets(
        refs.slice(0, 3).map(() => ({ pulls: [] })),
        28,
        46,
      ),
    },
    28 * 50,
    112,
    null,
  );
  anchors.push(`a list that shrinks to three rows: ${28 * 50} -> ${gone} px`);

  // Which answers say the same, so that one asked for again draws nothing.
  const base = recorded.annotated.body;
  const moved = JSON.parse(JSON.stringify(base));
  moved.refs[1].pulls[0].title = "A new title";
  const refreshed = JSON.parse(JSON.stringify(base));
  refreshed.pull_requests.refreshing = true;
  const agreement = [
    ["the same answer", base, JSON.parse(JSON.stringify(base))],
    ["a pull request's title changed", base, moved],
    ["the server began filling its pull requests", base, refreshed],
    ["no answer and an answer", null, base],
    ["a row fewer", base, { ...base, refs: base.refs.slice(1) }],
  ].map(([what, a, b]) => `${what}: ${selectorRuntime.sameListing(a, b) ? "same" : "different"}`);

  // Which rows are the same refs drawn the same way, whatever pull requests they have: the
  // rows a drawn list keeps, and patches.
  const rowsOf = (listing) =>
    selectorRuntime.describe({ ...emptyState(), listing, open: true }).rows;
  const lines = rowsOf(recorded.filling.body);
  const grown = rowsOf(recorded.annotated.body);
  const renamed = rowsOf(recorded.annotated.body);
  renamed[1] = { ...renamed[1], commit: "0000000" };
  agreement.push(
    ...[
      ["the same refs with other pull requests", lines, grown],
      ["a ref's commit moved", grown, renamed],
      ["a row fewer", grown, grown.slice(1)],
    ].map(
      ([what, a, b]) => `${what}: ${selectorRuntime.sameRefLines(a, b) ? "same" : "different"}`,
    ),
  );

  return { steps, anchors, same: agreement };
}

run()
  .then((transcript) => {
    process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
  })
  .catch((error) => {
    process.stderr.write(`${error.stack || error}\n`);
    process.exitCode = 1;
  });
