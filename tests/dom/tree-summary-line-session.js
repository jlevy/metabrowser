// Browserless session: what the Files totals line says, in each state it paints in.
//
// The line under the Files toolbar is a navigation metadata line (`.nav-metadata`,
// docs/design-system.md, "Navigation Metadata Line"). Its markup and words are
// navigation.js's `treeSummaryHtml`, written with the shell's own text helpers, and its
// two figures are patched live by `treeSummaryCountHtml` and `treeSummarySizeHtml` as the
// walker's root aggregate changes. This runs the real navigation.js with `esc`,
// `formatCount`, and `formatSize` extracted verbatim from app.js, the helpers app.js
// hands it, over the real formatters.js, whose `formatBytes` writes every size the
// shell shows (tests/dom/byte-sizes-session.js), and records the line for each state: before any count, counted before the
// split arrives, a Git pin with no sizes, the split with and without ignored files, an
// empty folder, and each live figure. Where the line sits is layout, measured in Chrome
// by tests/test_nav_metadata_chrome.py.

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
vm.runInContext(["esc", "formatSize", "formatCount"].map(appFunction).join("\n"), context, {
  filename: "app-text-helpers.js",
});
const route = context.MetabrowserNavigationRoute;
const format = vm.runInContext("({ esc, formatCount, formatSize })", context);

/** How the line reads: its text, with the space each item boundary puts between items. */
function reads(html) {
  return html
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** @param {string} html */
function line(html) {
  const classes = /^<div class="([^"]*)">/.exec(html)?.[1] ?? "";
  return {
    classes,
    reads: reads(html),
    pending: (html.match(/tally-pending/g) ?? []).length,
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
const live = {
  "count still being counted": route.treeSummaryCountHtml(null, format),
  "count known": route.treeSummaryCountHtml(1, format),
  "count omitted": route.treeSummaryCountHtml(undefined, format),
  "size still being counted": route.treeSummarySizeHtml(Number.NaN, format),
  "size known": route.treeSummarySizeHtml(1536, format),
  "size omitted": route.treeSummarySizeHtml(undefined, format),
};

for (const [name, state] of Object.entries(states)) {
  check(`${name}: a metadata line`, state.classes.split(" ").includes("nav-metadata"));
  check(
    `${name}: never the tree rows' chips`,
    !/class="(count|size) (count|size)-/.test(state.html),
  );
}
check("pending: two figures pending", states["first paint, before any count"].pending === 2);
check(
  "the fallback and the split say the figure in the same words",
  states["counted, before the split arrives"].reads.startsWith("12,797 files (394.6 MB)") &&
    states["the split, with ignored files"].reads.startsWith("12,797 files (394.6 MB)"),
);
check("a Git pin states no size", states["a Git pin, which has no sizes"].reads === "4 files");

if (failures.length > 0) {
  process.stderr.write(`tree summary line: ${failures.join("; ")}\n`);
  process.exitCode = 1;
}
process.stdout.write(`${JSON.stringify({ states, live }, null, 2)}\n`);
