// Browserless session for the Files tab's Group by, against the production filter state
// and tree filter model (static/filter-state.js, static/tree-filter-model.js).
//
// The browser owns which request a choice makes, how the answer becomes sections, how a
// folder inside a section opens, and what a later filter or grouping change reloads. The
// server owns which groups hold what, in what order, with what counts
// (metabrowser/tree_groups.py, pinned by tests/golden/cli-api-tree-groups.tryscript.md);
// the answer this session paints is read from that golden, its first answer, so the two
// cannot drift. It also drives the shell's Group by decisions, which tree-filter-model.js
// holds as pure functions: each section's share of the first paint's rows, the section a
// revealed row is looked for in first, the reopen plan after a refresh, and the prefetch.
//
// Prints one JSON transcript; tests/golden/cli-ui-files-group-by.tryscript.md pins it.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const sandbox = {
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
  files: section.files,
  topLevel: section.tree.map((node) => node.path),
}));
check(
  "sections keep the server's order, Documentation first",
  sections.map((section) => section.id).join() === "docs,code,data,other",
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
// Show ignored, on the row beside Group by, narrows every group too. Clear counts it, so
// it shows; the chevron's badge leaves it out, since the row shows its own state (mb-x1h6).
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
  "Clear counts Show ignored and the badge does not",
  transcript.steps.at(-1).activeFilters === 3 && transcript.steps.at(-1).drawerFilters === 2,
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

// The prefetch: opening the menu asks for what it offers, opening it again within the
// TTL asks for nothing new, a request no longer offered is aborted, a choice takes its
// answer once, a stale one is refetched, and a change to the files clears them.
{
  let clock = 0;
  const started = [];
  const aborted = [];
  const prefetch = model.createGroupsPrefetch({
    now: () => clock,
    ttlMs: 10_000,
    start(url) {
      started.push(url);
      return { answer: Promise.resolve(url), abort: () => aborted.push(url) };
    },
  });
  const steps = [];
  const step = (label, run) => {
    const before = started.length;
    const result = run();
    steps.push({
      step: label,
      started: started.slice(before),
      aborted: aborted.splice(0),
      kept: prefetch.size(),
      ...(result === undefined ? {} : { took: result !== null }),
    });
  };
  step("open the menu", () => prefetch.prefetch(["age", "type"]));
  clock = 2_000;
  step("open it again", () => prefetch.prefetch(["age", "type"]));
  step("open it while grouped by type", () => prefetch.prefetch(["age"]));
  step("choose By age", () => prefetch.take("age"));
  step("choose By age again", () => prefetch.take("age"));
  step("open the menu", () => prefetch.prefetch(["age", "type"]));
  clock = 20_000;
  step("open it after the TTL", () => prefetch.prefetch(["age", "type"]));
  step("a file changes", () => prefetch.clear());
  transcript.prefetch = steps;
  check(
    "a reopened menu within the TTL asks for nothing",
    steps[1].started.length === 0 && steps[1].aborted.length === 0,
    steps[1],
  );
  check("a dropped offer is aborted", steps[2].aborted.join() === "type", steps[2]);
  check("an answer is taken once", steps[3].took === true && steps[4].took === false, steps);
  check("a stale answer is asked again", steps[6].started.length === 2, steps[6]);
  check(
    "a change clears every answer",
    steps[7].kept === 0 && steps[7].aborted.length === 2,
    steps[7],
  );
}

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
