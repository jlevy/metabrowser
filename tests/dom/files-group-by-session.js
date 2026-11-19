// Browserless session for the Files tab's Group by, against the production filter state
// and tree filter model (static/filter-state.js, static/tree-filter-model.js).
//
// The browser owns which request a choice makes, how the answer becomes sections, how a
// folder inside a section opens, and what a later filter or grouping change reloads. The
// server owns which groups hold what, in what order, with what counts
// (metabrowser/tree_groups.py, pinned by tests/golden/cli-api-tree-groups.tryscript.md);
// the answer this session paints is read from that golden, its first answer, so the two
// cannot drift. It also drives the shell's Group by decisions, which tree-filter-model.js
// holds: each section's share of the first paint's rows, the section a revealed row is
// looked for in first, the reopen plan after a refresh, the prefetch and its keyboard
// dwell, and the loads' lifecycle (createGroupedLoads), with the shell's fetch and paint
// stood in for by answers the session settles.
//
// Prints one JSON transcript; tests/golden/cli-ui-files-group-by.tryscript.md pins it.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const sandbox = {
  AbortController,
  Array,
  Map,
  Math,
  Number,
  Object,
  Set,
  String,
  encodeURIComponent,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.METABROWSER_SETTINGS = {
  RECENT_WINDOW_SECONDS: {
    live: 90,
    "1h": 3600,
    "24h": 86400,
    "7d": 604800,
    "30d": 2592000,
    all: null,
  },
};
sandbox.metabrowser = { prefs: { remove() {} } };
sandbox.dispatchEvent = () => {};
sandbox.CustomEvent = function CustomEvent() {};
vm.createContext(sandbox);
for (const relative of ["filter-state.js", "tree-filter-model.js"]) {
  const filename = path.join(repoRoot, "src/metabrowser/static", relative);
  vm.runInContext(fs.readFileSync(filename, "utf-8"), sandbox, { filename });
}
const filter = sandbox.metabrowser.filterState;
const model = sandbox.MetabrowserTreeFilterModel;
// The route's own answer, as the golden records it.
const golden = fs.readFileSync(
  path.join(repoRoot, "tests/golden/cli-api-tree-groups.tryscript.md"),
  "utf-8",
);
const command = "$ metab groupsroot --api '/api/tree?group_by=type&depth=1'";
const recorded = golden.slice(golden.indexOf(command));
const answer = JSON.parse(
  recorded.slice(recorded.indexOf("status: 200\n") + 12, recorded.indexOf("\n? 0")),
);
const LIMIT = 5000;
const floors = filter.SIZE_MIN_BYTES;
const failures = [];
const check = (label, ok, detail) => {
  if (!ok) {
    failures.push(`${label}: ${JSON.stringify(detail)}`);
  }
};

// Each step: what the reader chose, the action the shell takes, and the request it makes.
const transcript = { steps: [] };
let cursor = model.recentFilterCursor(filter.get(), LIMIT, floors);
/** @param {string} label @param {Record<string, unknown>} patch */
function choose(label, patch) {
  filter.set(patch);
  const state = filter.get();
  const next = model.recentFilterCursor(state, LIMIT, floors);
  const transition = model.recentFilterTransition(cursor, next);
  cursor = transition.current;
  const request =
    transition.action === "load-groups"
      ? model.groupsUrl(state, floors, 2)
      : transition.action === "load-tree"
        ? model.treeUrl("", state, floors)
        : transition.action === "load-recent"
          ? model.recentUrl(cursor.windowKey, LIMIT, state, floors)
          : null;
  transcript.steps.push({
    chose: label,
    source: cursor.source,
    action: transition.action,
    request,
    // Clear shows while any filter is set; the chevron's badge counts only the drawer's.
    activeFilters: filter.activeCount(),
    drawerFilters: model.drawerFilterCount(state),
  });
  return transition.action;
}

// The default tree is ungrouped.
check("a page starts ungrouped", model.groupBy(filter.get()) === "none", filter.get());
check("ungrouped is the tree source", cursor.source === "tree", cursor);

// By file type: one request for every group's counts and first two levels.
check(
  "choosing By file type loads the groups",
  choose("By file type", { group: "type" }) === "load-groups",
);
// The answer becomes sections in the server's order, each named for the group it holds.
const sections = model.groupSections(answer);
transcript.sections = sections.map((section) => ({
  key: section.key,
  label: section.label,
  icon: section.icon,
  files: section.files,
  topLevel: section.tree.map((node) => node.path),
}));
check(
  "sections keep the server's order, Documentation first",
  sections.map((section) => section.id).join() === "docs,code,data,other",
  transcript.sections,
);
// Each section carries its category's icon, which leads its heading (docs/design-system.md,
// "File-Type Category Icons").
check(
  "each section carries its category's icon",
  sections.map((section) => section.icon).join() === "doc,alignLeft,list,file",
  transcript.sections,
);
check(
  "the sections' counts are what the server counted",
  sections.reduce((sum, section) => sum + section.files, 0) === 9,
  transcript.sections,
);
// A folder inside a section opens with that section's group, so it lists only its members.
transcript.openFolder = {
  code: model.groupTreeUrl("src", "type:code", filter.get(), floors, ["depth=2"]),
  other: model.groupTreeUrl("logs", "type:other", filter.get(), floors, ["depth=2"]),
};

// A filter narrows every group: the groups are asked for again, under the filter.
check(
  "a type filter reloads the groups",
  choose("types .md and .py", { types: [".md", ".py"] }) === "load-groups",
);
// The recency window is one more filter on a grouped tree, not a Recent list.
check(
  "a recency window reloads the groups",
  choose("Modified within Past hour", { recency: "1h" }) === "load-groups",
);
check(
  "a grouped request carries the window",
  transcript.steps.at(-1).request.includes("recency=1h"),
  transcript.steps.at(-1),
);
// Show ignored, in the drawer beside the filters, narrows every group too. Clear counts
// it, so it shows, and the chevron's badge counts it, since the closed drawer hides it
// (mb-ey0d).
check(
  "Show ignored off reloads the groups",
  choose("Show ignored off", { showIgnored: false }) === "load-groups",
);
check(
  "a grouped request leaves out ignored entries",
  transcript.steps.at(-1).request.includes("include_ignored=0"),
  transcript.steps.at(-1),
);
check(
  "Clear and the badge both count Show ignored",
  transcript.steps.at(-1).activeFilters === 3 && transcript.steps.at(-1).drawerFilters === 3,
  transcript.steps.at(-1),
);
// Clear undoes the filters, Show ignored included, and keeps the grouping.
filter.clear();
const cleared = model.recentFilterTransition(
  cursor,
  model.recentFilterCursor(filter.get(), LIMIT, floors),
);
cursor = cleared.current;
transcript.steps.push({
  chose: "Clear",
  source: cursor.source,
  action: cleared.action,
  request: cleared.action === "load-groups" ? model.groupsUrl(filter.get(), floors, 2) : null,
  activeFilters: filter.activeCount(),
  drawerFilters: model.drawerFilterCount(filter.get()),
});
check("Clear reloads the groups without the filters", cleared.action === "load-groups", cleared);
check("Clear keeps Group by", filter.get().group === "type", filter.get());
check("Clear shows ignored entries again", filter.get().showIgnored === true, filter.get());

// By age: the same request with the other grouping.
check("choosing By age loads the groups", choose("By age", { group: "age" }) === "load-groups");
// Which band a file falls in, where the shell reveals a row without asking the server.
const windows = sandbox.METABROWSER_SETTINGS.RECENT_WINDOW_SECONDS;
transcript.ageBands = Object.fromEntries(
  [30, 90, 91, 3600, 3601, 86400 * 3, 86400 * 40].map((age) => [
    String(age),
    model.ageGroupFor(age, windows),
  ]),
);
check(
  "a band's far edge is inside it, and past the last window is Older",
  transcript.ageBands["90"] === "live" &&
    transcript.ageBands["91"] === "1h" &&
    transcript.ageBands["3600"] === "1h" &&
    transcript.ageBands[String(86400 * 40)] === "older",
  transcript.ageBands,
);

// No grouping with a window set is the Recent list again; with none, the tree.
filter.set({ recency: "24h" });
cursor = model.recentFilterCursor(filter.get(), LIMIT, floors);
check(
  "No grouping with a window is Recent",
  choose("No grouping", { group: "none" }) === "load-recent",
);
check("no window is the tree", choose("Any age", { recency: "all" }) === "load-tree");

// Each section opens folders from its share of the viewport's rows, at least one.
transcript.rowShares = {
  "30 rows, 4 sections": model.sectionRowBudget(30, 4),
  "5 rows, 10 sections": model.sectionRowBudget(5, 10),
  "0 sections": model.sectionRowBudget(30, 0),
};
check(
  "row shares",
  JSON.stringify(transcript.rowShares) ===
    '{"30 rows, 4 sections":7,"5 rows, 10 sections":1,"0 sections":30}',
  transcript.rowShares,
);

// Revealing a row: its likely section first, then every other one; a folder has no guess,
// since it stands in every section that holds its files.
const groupForFile = (name, ext) => (ext === ".md" || name === "README" ? "docs" : "code");
const nowSec = 2_000_000_000;
const typeKeys = ["type:docs", "type:code", "type:other"];
const ageKeys = ["age:live", "age:1h", "age:older"];
transcript.reveal = {
  "a Markdown file": model.revealSectionOrder(
    typeKeys,
    model.likelySectionKey(
      "type",
      { type: "file", name: "a.md", ext: ".md" },
      nowSec,
      windows,
      groupForFile,
    ),
  ),
  "a folder": model.revealSectionOrder(
    typeKeys,
    model.likelySectionKey("type", { type: "dir", name: "src" }, nowSec, windows, groupForFile),
  ),
  "a symlink": model.revealSectionOrder(
    typeKeys,
    model.likelySectionKey(
      "type",
      { type: "symlink", name: "link" },
      nowSec,
      windows,
      groupForFile,
    ),
  ),
  // Drawn in Live when the answer came, 91 s old now: Past hour first, Live still tried.
  "a file past Live's edge": model.revealSectionOrder(
    ageKeys,
    model.likelySectionKey(
      "age",
      { type: "file", name: "a.md", mtime: nowSec - 91 },
      nowSec,
      windows,
      groupForFile,
    ),
  ),
  "a file with no mtime": model.revealSectionOrder(
    ageKeys,
    model.likelySectionKey("age", { type: "file", name: "a.md" }, nowSec, windows, groupForFile),
  ),
};
check(
  "every reveal looks in every section",
  Object.values(transcript.reveal).every((order) => order.length === 3),
  transcript.reveal,
);
check(
  "a folder keeps display order",
  transcript.reveal["a folder"].join() === typeKeys.join(),
  transcript.reveal,
);
check(
  "a file past an edge is still looked for where it is drawn",
  transcript.reveal["a file past Live's edge"].join() === "age:1h,age:live,age:older",
  transcript.reveal,
);

// The reopen plan after a refresh: folders open before come back open in the same frame
// from the answer or the cache; an open folder the answer reaches with its children in
// neither is fetched before the paint, and one it no longer reaches is dropped.
const plan = model.graftOpenedFolders(
  [
    { type: "dir", path: "src", children: null },
    { type: "dir", path: "docs", children: [{ type: "file", path: "docs/a.md" }] },
    { type: "file", path: "README.md" },
  ],
  ["src", "docs", "src/app", "src/gone", "removed"],
  (folder) =>
    folder === "src"
      ? [
          { type: "dir", path: "src/app", children: null },
          { type: "dir", path: "src/lib", children: null },
        ]
      : null,
);
transcript.reopen = {
  paintedOpen: plan.expanded,
  fetchFirst: plan.fetch,
  srcChildren: plan.tree[0].children.map((node) => node.path),
};
check(
  "the reopen plan",
  JSON.stringify(transcript.reopen) ===
    '{"paintedOpen":["src","docs"],"fetchFirst":["src/app"],"srcChildren":["src/app","src/lib"]}',
  transcript.reopen,
);

// Waiting (mb-75l5). A refresh asked for while a grouping's first sections are on their way
// waits for them, rather than discarding them and starting over; anything else starts,
// cancelling the load it supersedes.
{
  const typeKey = model.groupedRequestKey({ ...filter.get(), group: "type" }, floors);
  const ageKey = model.groupedRequestKey({ ...filter.get(), group: "age" }, floors);
  const choice = { key: typeKey, first: true };
  const refresh = { key: typeKey, first: false };
  transcript.loads = {
    "a refresh, while the first sections are on their way": model.groupedLoadDecision(
      choice,
      refresh,
    ),
    "a refresh, while a refresh is on its way": model.groupedLoadDecision(refresh, refresh),
    "another grouping, while the first sections are on their way": model.groupedLoadDecision(
      choice,
      { key: ageKey, first: true },
    ),
    "a refresh of another grouping": model.groupedLoadDecision(choice, {
      key: ageKey,
      first: false,
    }),
    "a choice, with nothing on its way": model.groupedLoadDecision(null, choice),
    "a refresh, with nothing on its way": model.groupedLoadDecision(null, refresh),
  };
  check(
    "only a refresh of the sections on their way waits for them",
    Object.values(transcript.loads).join() === "after,start,start,start,start,start",
    transcript.loads,
  );
  // Past the quiet period, the scan row says what is on its way, in the row's own words.
  transcript.regroupingStatus = {
    age: model.regroupingStatusText("age"),
    type: model.regroupingStatusText("type"),
  };
  check(
    "the wait names the choice as its row does",
    transcript.regroupingStatus.age === "Grouping by age…" &&
      transcript.regroupingStatus.type === "Grouping by file type…",
    transcript.regroupingStatus,
  );
}

// The prefetch asks only for what the reader is about to choose: the grouping whose row the
// pointer presses or the keyboard rests on, never No grouping or the grouping shown, and
// nothing when the menu opens (mb-navs).
transcript.prefetchFor = Object.fromEntries(
  [
    ["No grouping, ungrouped", "none", { group: "none" }],
    ["By age, ungrouped", "age", { group: "none" }],
    ["By file type, grouped by type", "type", { group: "type" }],
    ["By age, grouped by type, under a filter", "age", { group: "type", types: [".md"] }],
  ].map(([label, value, patch]) => [
    label,
    model.groupPrefetchUrl(value, { ...filter.get(), ...patch }, floors),
  ]),
);
check(
  "No grouping and the grouping shown ask for nothing",
  transcript.prefetchFor["No grouping, ungrouped"] === null &&
    transcript.prefetchFor["By file type, grouped by type"] === null,
  transcript.prefetchFor,
);
check(
  "a prefetch is the request the choice makes",
  transcript.prefetchFor["By age, ungrouped"] ===
    model.groupsUrl({ ...filter.get(), group: "age" }, floors, 2),
  transcript.prefetchFor,
);

/** A promise and the hands that settle it. */
function deferred() {
  /** @type {(value?: unknown) => void} */
  let resolve = () => {};
  /** @type {(error: unknown) => void} */
  let reject = () => {};
  const promise = new Promise((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}
// Lets every settled promise's handlers run.
const settle = () => new Promise((resolve) => setImmediate(resolve));

/**
 * A prefetch with a clock, a dwell timer, and answers this session settles, and a step
 * that records what each move started, aborted, and kept. Requests are named for their
 * grouping and filters.
 */
function prefetchHarness() {
  const harness = { clock: 0, started: [], aborted: [], timers: new Map(), answers: new Map() };
  const name = (url) => {
    const by = url.match(/group_by=([a-z]+)/)[1];
    return url.includes("types=") ? `${by} under .md` : by;
  };
  let nextTimer = 1;
  harness.prefetch = model.createGroupsPrefetch({
    now: () => harness.clock,
    ttlMs: 10_000,
    dwellMs: 300,
    setTimer(callback, ms) {
      const id = nextTimer;
      nextTimer += 1;
      harness.timers.set(id, { callback, ms });
      return id;
    },
    clearTimer(id) {
      harness.timers.delete(id);
    },
    start(url) {
      const answer = deferred();
      harness.started.push(name(url));
      harness.answers.set(name(url), answer);
      return { answer: answer.promise, abort: () => harness.aborted.push(name(url)) };
    },
  });
  // The dwell passes: every timer waiting fires.
  harness.dwell = () => {
    const due = [...harness.timers.values()];
    harness.timers.clear();
    for (const timer of due) {
      timer.callback();
    }
    return due.map((timer) => timer.ms);
  };
  harness.steps = [];
  harness.step = async (label, run) => {
    const before = harness.started.length;
    const result = run();
    await settle();
    harness.steps.push({
      step: label,
      started: harness.started.slice(before),
      aborted: harness.aborted.splice(0),
      kept: harness.prefetch.size(),
      resting: harness.prefetch.resting(),
      ...(result === undefined || Array.isArray(result)
        ? {}
        : { took: result !== null, ...(result ? { stale: result.stale } : {}) }),
    });
  };
  return harness;
}

const url = (value, patch = {}) =>
  model.groupPrefetchUrl(value, { ...filter.get(), group: "none", ...patch }, floors);

async function sessions() {
  // A press asks at once. An answer asked for again within the TTL is not asked for twice,
  // a choice takes it once, and one past the TTL is dropped. A change to the files makes
  // every answer stale and drops none: a choice still takes a stale one, and is told so; a
  // press leaves a stale answer still on its way alone, since its pass is running, and
  // asks again for one that has come (mb-75l5). Asking under other filters drops the
  // answers kept for these.
  {
    const h = prefetchHarness();
    const { prefetch } = h;
    await h.step("press By age", () => prefetch.want(url("age")));
    h.clock = 2_000;
    await h.step("press it again", () => prefetch.want(url("age")));
    await h.step("press By file type", () => prefetch.want(url("type")));
    await h.step("choose By age", () => prefetch.take(url("age")));
    await h.step("choose By age again", () => prefetch.take(url("age")));
    h.clock = 20_000;
    await h.step("press By file type after the TTL", () => prefetch.want(url("type")));
    await h.step("a file changes", () => prefetch.markChanged());
    await h.step("press By file type while its stale answer is on its way", () =>
      prefetch.want(url("type")),
    );
    await h.step("choose By file type", () => prefetch.take(url("type")));
    await h.step("press By age, and its answer comes", () => {
      prefetch.want(url("age"));
      h.answers.get("age").resolve({});
    });
    await h.step("a file changes again", () => prefetch.markChanged());
    await h.step("press By age again", () => prefetch.want(url("age")));
    await h.step("choose By age", () => prefetch.take(url("age")));
    await h.step("press By file type", () => prefetch.want(url("type")));
    await h.step("press By age under a .md filter", () =>
      prefetch.want(url("age", { types: [".md"] })),
    );
    transcript.prefetch = h.steps;
    const steps = h.steps;
    check(
      "a press within the TTL asks for nothing new",
      steps[1].started.length === 0 && steps[1].aborted.length === 0,
      steps[1],
    );
    check(
      "another press asks for its grouping and keeps the first",
      steps[2].started.join() === "type" && steps[2].kept === 2,
      steps[2],
    );
    check("an answer is taken once", steps[3].took === true && steps[4].took === false, steps);
    check(
      "an answer past the TTL is dropped and asked for again",
      steps[5].started.join() === "type" && steps[5].aborted.join() === "type",
      steps[5],
    );
    check(
      "a change drops no answer",
      steps[6].kept === 1 && steps[6].aborted.length === 0,
      steps[6],
    );
    check(
      "a press leaves a stale answer still on its way alone",
      steps[7].started.length === 0 && steps[7].aborted.length === 0,
      steps[7],
    );
    check(
      "a choice takes an answer a change made stale, and is told so",
      steps[8].took === true && steps[8].stale === true,
      steps[8],
    );
    check(
      "a press asks again for a stale answer that has come",
      steps[11].started.join() === "age" && steps[11].aborted.length === 0,
      steps[11],
    );
    check(
      "an answer asked for after the change is fresh",
      steps[12].took === true && steps[12].stale === false,
      steps[12],
    );
    check(
      "asking under other filters drops the answers kept for these",
      steps[14].started.join() === "age under .md" &&
        steps[14].aborted.join() === "type" &&
        steps[14].kept === 1,
      steps[14],
    );
  }

  // The keyboard asks only for a row it rests on: focus that stays on a row for the dwell
  // asks for its grouping, and a row passed over on the way to another asks for nothing.
  // The next key, a choice, or the menu closing cancels the wait, and a row focus has left
  // asks for nothing when it ends (review A of #466, A1).
  {
    const h = prefetchHarness();
    const { prefetch } = h;
    await h.step("↓ to By age", () => prefetch.rest(url("age")));
    await h.step("↓ to By file type before the dwell passes", () => prefetch.rest(url("type")));
    await h.step("the dwell passes", () => h.dwell());
    await h.step("↑ to By age", () => prefetch.rest(url("age")));
    await h.step("Escape closes the menu", () => prefetch.cancelRest());
    await h.step("the dwell would have passed", () => h.dwell());
    await h.step("↓ to By age, then ↓ to No grouping", () => {
      prefetch.rest(url("age"));
      prefetch.rest(url("none"));
    });
    await h.step("the dwell passes on No grouping", () => h.dwell());
    await h.step("↓ to By age", () => prefetch.rest(url("age")));
    await h.step("Enter chooses it before the dwell passes", () => prefetch.take(url("age")));
    await h.step("the dwell would have passed", () => h.dwell());
    await h.step("↓ to By age, and focus leaves the menu", () =>
      prefetch.rest(url("age"), () => false),
    );
    await h.step("the dwell passes", () => h.dwell());
    await h.step("↓ to By age, and the pointer presses it", () => {
      prefetch.rest(url("age"));
      prefetch.want(url("age"));
    });
    transcript.keyboardPrefetch = h.steps;
    const steps = h.steps;
    const dwells = h.dwell();
    check("nothing is left waiting", dwells.length === 0, dwells);
    check(
      "a row passed over asks for nothing",
      steps[0].started.length === 0 &&
        steps[1].started.length === 0 &&
        steps[2].started.join() === "type",
      steps.slice(0, 3),
    );
    check(
      "the menu closing cancels the wait",
      steps[4].resting === false && steps[5].started.length === 0,
      steps.slice(3, 6),
    );
    check("No grouping asks for nothing", steps[7].started.length === 0, steps[7]);
    check(
      "a choice before the dwell cancels it, and takes no answer",
      steps[9].took === false && steps[9].resting === false && steps[10].started.length === 0,
      steps.slice(8, 11),
    );
    check("a row focus has left asks for nothing", steps[12].started.length === 0, steps[12]);
    check(
      "a press asks at once and cancels the rest",
      steps[13].started.join() === "age" && steps[13].resting === false,
      steps[13],
    );
  }

  // The Group by loads (createGroupedLoads), with the shell's fetch and paint stood in for
  // by answers this session settles: what each load asks for, which it aborts, what paints,
  // and when the wait it shows ends.
  {
    const log = [];
    const pending = [];
    let staleNext = false;
    let failNext = false;
    const loads = model.createGroupedLoads({
      async run(load) {
        const answer = deferred();
        const stale = staleNext;
        const fails = failNext;
        staleNext = false;
        failNext = false;
        pending.push(answer);
        log.push(`ask ${load.key}${load.first ? "" : " (refresh)"}`);
        load.signal.addEventListener("abort", () => log.push(`abort ${load.key}`));
        if (stale) {
          // Asked for ahead, before a file changed (fetchGroups in the shell).
          load.refreshAfter();
        }
        try {
          await answer.promise;
        } catch {
          log.push(`fail ${load.key}`);
          return false;
        }
        if (fails) {
          log.push(`fail ${load.key}`);
          return false;
        }
        if (!load.current()) {
          log.push(`drop ${load.key}`);
          return false;
        }
        log.push(`paint ${load.key}`);
        return true;
      },
      pending(load) {
        log.push(load ? `wait for ${load.key}${load.first ? "" : " (refresh)"}` : "wait ends");
      },
      refresh() {
        log.push("refresh");
        void loads.load("type", { refresh: true, painted: true });
      },
    });
    const answerNext = async () => {
      pending.shift().resolve({});
      await settle();
    };
    const cases = {};
    const run = async (label, work) => {
      log.length = 0;
      await work();
      await settle();
      cases[label] = log.slice();
      check(`${label}: nothing is left on its way`, loads.inFlight() === null, cases[label]);
    };
    await run("a refresh during a first load waits, then runs once", async () => {
      void loads.load("type");
      log.push(`a refresh: ${await loads.load("type", { refresh: true, painted: false })}`);
      log.push(`another: ${await loads.load("type", { refresh: true, painted: false })}`);
      await answerNext();
      await answerNext();
    });
    await run("a newer choice aborts the load, and its answer never paints", async () => {
      void loads.load("type");
      void loads.load("age");
      await answerNext();
      await answerNext();
    });
    await run("a stale prefetch paints, then refreshes once", async () => {
      staleNext = true;
      void loads.load("type");
      await answerNext();
      await answerNext();
    });
    await run("settled resolves on paint, on failure, and on cancel", async () => {
      const settled = (label) =>
        loads.settled().then(() => {
          log.push(`settled (${label})`);
        });
      void loads.load("type");
      const painted = settled("painted");
      await answerNext();
      await painted;
      failNext = true;
      void loads.load("type");
      const failed = settled("failed");
      await answerNext();
      await failed;
      void loads.load("type");
      const cancelled = settled("cancelled");
      loads.cancel();
      await cancelled;
      await answerNext();
      void loads.load("type", { refresh: true, painted: true });
      const refreshing = settled("a refresh paints no new sections");
      await refreshing;
      await answerNext();
    });
    transcript.groupedLoads = cases;
    const asked = (label) => cases[label].filter((line) => line.startsWith("ask ")).length;
    check(
      "a refresh during a first load runs once, after it paints",
      asked("a refresh during a first load waits, then runs once") === 2 &&
        cases["a refresh during a first load waits, then runs once"].indexOf("paint type") <
          cases["a refresh during a first load waits, then runs once"].indexOf(
            "ask type (refresh)",
          ),
      cases,
    );
    const superseded = cases["a newer choice aborts the load, and its answer never paints"];
    check(
      "a newer choice aborts the load, and its answer never paints",
      superseded.includes("abort type") &&
        superseded.includes("drop type") &&
        !superseded.includes("paint type") &&
        superseded.includes("paint age"),
      superseded,
    );
    const stale = cases["a stale prefetch paints, then refreshes once"];
    check(
      "a stale prefetch paints, then refreshes once",
      stale.filter((line) => line === "refresh").length === 1 &&
        stale.indexOf("paint type") < stale.indexOf("refresh"),
      stale,
    );
    const settledLines = cases["settled resolves on paint, on failure, and on cancel"].filter(
      (line) => line.startsWith("settled"),
    );
    check(
      "settled resolves on paint, on failure, on cancel, and at once for a refresh",
      settledLines.join() ===
        "settled (painted),settled (failed),settled (cancelled),settled (a refresh paints no new sections)",
      cases,
    );
  }
}

sessions().then(finish, (error) => {
  process.stderr.write(`${error.stack}\n`);
  process.exit(1);
});

function finish() {
  // A source that could not count a group keeps it, with no count.
  transcript.uncounted = model.groupSections({
    group_by: "type",
    groups: [{ id: "docs", label: "Documentation", files: null, size: null, tree: [] }],
  })[0];

  // A malformed answer is refused, not painted in part.
  const refused = [];
  for (const [label, payload] of [
    ["no grouping", { groups: [] }],
    ["no groups", { group_by: "type" }],
    ["a group with no id", { group_by: "age", groups: [{ label: "Live" }] }],
  ]) {
    try {
      model.groupSections(payload);
    } catch (error) {
      refused.push(`${label}: ${error.message}`);
    }
  }
  transcript.refused = refused;
  check("every malformed answer is refused", refused.length === 3, refused);

  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.exit(1);
  }
  process.stdout.write(`${JSON.stringify(transcript, null, 2)}\n`);
}
