// Browserless session: what the Files totals line says, in each state it paints in.
//
// The line under the Files toolbar is a navigation metadata line (`.nav-metadata`,
// docs/design-system.md, "Navigation Metadata Line"). Its markup and words are
// navigation.js's `treeSummaryHtml`, written with the shell's own text helpers, and its
// two figures are patched live by `treeSummaryCountHtml` and `treeSummarySizeHtml` as the
// walker's root aggregate changes. This runs the real navigation.js with
// `formatCountParts` and `formatSize` extracted verbatim from app.js, the helpers app.js
// hands it, over the real formatters.js, whose `formatBytes` writes every size the shell
// shows (tests/dom/byte-sizes-session.js) and whose `countPartsHtml` paints every count
// summary's numbers bold, and records the line for each state: before any count, counted before the
// split arrives, a Git pin with no sizes, the split with and without ignored files, an
// empty folder, and each live figure. It records too a line drawn before the root's
// totals are known, which holds the line its ignored count may need with the pending
// placeholder, and what that line becomes as the root's own entry brings the totals
// (`rootTotalsFromEntry`): its ignored count, or nothing ignored. Where the line sits is
// layout, measured in Chrome by tests/test_nav_metadata_chrome.py and, from first paint
// to settled, by tests/test_files_totals_stable_chrome.py.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf8");

/** A top-level function of app.js, verbatim, up to its closing brace. */
function appFunction(name) {
  const start = appSource.indexOf(`\nfunction ${name}(`);
  const end = appSource.indexOf("\n}\n", start);
  if (start < 0 || end < start) {
    throw new Error(`app.js ${name} is not extractable`);
  }
  return appSource.slice(start + 1, end + 2);
}

const context = vm.createContext({ console, Number, Object, String, Math, Error, TypeError });
context.window = context;
for (const script of ["formatters.js", "navigation.js"]) {
  const file = path.join(staticDir, script);
  vm.runInContext(fs.readFileSync(file, "utf8"), context, { filename: file });
}
vm.runInContext(["formatSize", "formatCountParts"].map(appFunction).join("\n"), context, {
  filename: "app-text-helpers.js",
});
const route = context.MetabrowserNavigationRoute;
const format = vm.runInContext("({ formatCountParts, formatSize })", context);

/** A count summary's bold number (`.summary-number`), and the figure in it. */
const NUMBER = /<span class="summary-number">([^<]*)<\/span>/g;

/** Text with its tags taken out, each leaving the space an item boundary puts there. */
function untagged(html) {
  return html
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * How the line reads: its text, with the space each item boundary puts between items. A
 * bold number is inline in its item, so it reads as the figure it holds.
 */
function reads(html) {
  return untagged(html.replace(NUMBER, "$1"));
}

/** @param {string} html */
function line(html) {
  const classes = /^<div class="([^"]*)">/.exec(html)?.[1] ?? "";
  return {
    classes,
    reads: reads(html),
    pending: (html.match(/tally-pending/g) ?? []).length,
    // The line the ignored count takes, or holds while it is unknown.
    ignoredLine: html.includes('class="tree-summary-ignored"')
      ? "counted"
      : html.includes("tree-summary-ignored-pending")
        ? "held"
        : "none",
    // The figures it paints bold (docs/design-system.md, "Count Summaries Bold Their
    // Numbers"), and what it says in the line's weight, which holds no figure.
    numbers: [...html.matchAll(NUMBER)].map((found) => found[1]),
    regular: untagged(html.replace(NUMBER, " ")),
    html,
  };
}

const failures = [];
function check(label, ok) {
  if (!ok) {
    failures.push(label);
  }
}

const states = {
  "first paint, before any count": line(route.treeSummaryHtml(null, null, null, format)),
  "counted, before the split arrives": line(route.treeSummaryHtml(null, 12797, 413800000, format)),
  "a Git pin, which has no sizes": line(route.treeSummaryHtml(null, 4, undefined, format)),
  "the split, nothing ignored": line(
    route.treeSummaryHtml(
      { files: 4, size: 38, ignored_files: 0, ignored_size: 0 },
      null,
      null,
      format,
    ),
  ),
  "the split, with ignored files": line(
    route.treeSummaryHtml(
      { files: 12797, size: 413800000, ignored_files: 248189, ignored_size: 10100000000 },
      null,
      null,
      format,
    ),
  ),
  "an empty folder": line(
    route.treeSummaryHtml(
      { files: 0, size: 0, ignored_files: 0, ignored_size: 0 },
      null,
      null,
      format,
    ),
  ),
  "one file": line(
    route.treeSummaryHtml(
      { files: 1, size: 2048, ignored_files: 0, ignored_size: 0 },
      null,
      null,
      format,
    ),
  ),
};
// A folder whose shell was drawn before the walk finished the root: the line holds its
// ignored line, and the root's own entry, once the walk has finished it, fills it or
// takes it away.
const finishedRoot = {
  path: "",
  type: "dir",
  total_files: 261_000,
  total_size: 10_513_800_000,
  unignored_files: 12_797,
  unignored_size: 413_800_000,
};
const cleanRoot = {
  path: "",
  type: "dir",
  total_files: 51,
  total_size: 369,
  unignored_files: 51,
  unignored_size: 369,
};
const totals = {
  "a root the walk has finished": route.rootTotalsFromEntry(finishedRoot),
  "a root with nothing ignored": route.rootTotalsFromEntry(cleanRoot),
  "a root still being walked": route.rootTotalsFromEntry({
    path: "",
    type: "dir",
    total_files: null,
    total_size: null,
    unignored_files: null,
    unignored_size: null,
  }),
  "a Git revision's root, which keeps no ignored totals": route.rootTotalsFromEntry({
    path: "",
    type: "dir",
    total_files: 4,
    total_size: 38,
  }),
};
const sequence = {
  "unknown: the ignored line held": line(route.treeSummaryHtml(null, null, null, format, true)),
  "counted: the root's entry brings its ignored count": line(
    route.treeSummaryHtml(totals["a root the walk has finished"], null, null, format, true),
  ),
  "none: the root's entry says nothing is ignored": line(
    route.treeSummaryHtml(totals["a root with nothing ignored"], null, null, format, true),
  ),
};
const live = {
  "count still being counted": route.treeSummaryCountHtml(null, format),
  "count known": route.treeSummaryCountHtml(1, format),
  "count omitted": route.treeSummaryCountHtml(undefined, format),
  "size still being counted": route.treeSummarySizeHtml(Number.NaN, format),
  "size known": route.treeSummarySizeHtml(1536, format),
  "size omitted": route.treeSummarySizeHtml(undefined, format),
};

for (const [name, state] of Object.entries({ ...states, ...sequence })) {
  check(`${name}: a metadata line`, state.classes.split(" ").includes("nav-metadata"));
  check(
    `${name}: never the tree rows' chips`,
    !/class="(count|size) (count|size)-/.test(state.html),
  );
}
check("pending: two figures pending", states["first paint, before any count"].pending === 2);
check(
  "a line not asked to hold the ignored line holds none",
  Object.values(states).every((state) => state.ignoredLine !== "held"),
);
const held = sequence["unknown: the ignored line held"];
check(
  "unknown: both figures and the ignored line pending, the line held after the quiet period",
  held.pending === 3 &&
    held.ignoredLine === "held" &&
    /class="tree-summary-ignored-pending mb-delayed-loading" role="status" aria-label="Counting ignored files"><span class="tally-pending" aria-hidden="true"><\/span><\/span><\/div>$/.test(
      held.html,
    ),
);
check(
  "counted: the held line becomes the ignored count",
  sequence["counted: the root's entry brings its ignored count"].ignoredLine === "counted" &&
    sequence["counted: the root's entry brings its ignored count"].pending === 0,
);
check(
  "none: nothing ignored takes the held line away",
  sequence["none: the root's entry says nothing is ignored"].ignoredLine === "none",
);
check(
  "the root's totals are the split the server's pass counts",
  JSON.stringify(totals["a root the walk has finished"]) ===
    JSON.stringify({
      files: 12797,
      size: 413800000,
      ignored_files: 248203,
      ignored_size: 10100000000,
    }) &&
    totals["a root still being walked"] === null &&
    totals["a Git revision's root, which keeps no ignored totals"] === null,
);
check(
  "the fallback and the split say the figure in the same words",
  states["counted, before the split arrives"].reads.startsWith("12,797 files (394.6 MB)") &&
    states["the split, with ignored files"].reads.startsWith("12,797 files (394.6 MB)"),
);
check("a Git pin states no size", states["a Git pin, which has no sizes"].reads === "4 files");
// Every figure is a bold number, with its unit, and no word is.
for (const [name, state] of Object.entries(states)) {
  check(`${name}: every figure is a bold number`, !/\d/.test(state.regular));
}
check(
  "the split's figures are its bold numbers",
  JSON.stringify(states["the split, with ignored files"].numbers) ===
    JSON.stringify(["12,797", "394.6 MB", "248,189", "9.4 GB"]),
);
check(
  "a live figure is a bold number",
  live["count known"] === '<span class="summary-number">1</span> file' &&
    live["size known"] === '(<span class="summary-number">1.5 KB</span>)',
);

if (failures.length > 0) {
  process.stderr.write(`tree summary line: ${failures.join("; ")}\n`);
  process.exitCode = 1;
}
process.stdout.write(`${JSON.stringify({ states, totals, sequence, live }, null, 2)}\n`);
