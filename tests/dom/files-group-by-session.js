// Browserless session for the Files tab's Group by, against the production filter state
// and tree filter model (static/filter-state.js, static/tree-filter-model.js).
//
// The browser owns which request a choice makes, how the answer becomes sections, how a
// folder inside a section opens, and what a later filter or grouping change reloads. The
// server owns which groups hold what, in what order, with what counts
// (metabrowser/tree_groups.py, pinned by tests/golden/cli-api-tree-groups.tryscript.md);
// the answer this session paints is that golden's first answer, kept in
// tests/fixtures/tree-groups-answer.json, which tests/test_tree_groups_session.py holds
// equal to the golden.
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
const answer = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/tree-groups-answer.json"), "utf-8"),
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
    activeFilters: filter.activeCount(),
  });
  return transition.action;
}

// The default tree is ungrouped.
check("a page starts ungrouped", model.groupBy(filter.get()) === "none", filter.get());
check("ungrouped is the tree source", cursor.source === "tree", cursor);

// File type: one request for every group's counts and first two levels.
check(
  "choosing File type loads the groups",
  choose("File type", { group: "type" }) === "load-groups",
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
// Clear undoes the filters and keeps the grouping.
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
});
check("Clear reloads the groups without the filters", cleared.action === "load-groups", cleared);
check("Clear keeps Group by", filter.get().group === "type", filter.get());

// Age: the same request with the other grouping.
check("choosing Age loads the groups", choose("Age", { group: "age" }) === "load-groups");
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
