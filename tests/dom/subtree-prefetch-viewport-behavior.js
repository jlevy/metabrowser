// Behavioral check for app.js's subtree-prefetch viewport bound.
//
// The sweep warms folders a reader can open next. "Next" is a claim about the
// screen, and getting it wrong is invisible from the code: taking stubs in DOM
// order sent 32 requests and 1.05 MB for folders nobody could see on a
// 300,000-file tree. The two ways a row is off screen are checked here,
// because only one of them is scrolling — a collapsed branch clips its
// children with `overflow: hidden` rather than removing them, so those rows
// keep full-height boxes and a rect test alone reads them as visible.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const appSource = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/app.js"), "utf-8");

const failures = [];

const match = appSource.match(/function isNearNavViewport\(row, view, lookahead\) \{[\s\S]*?\n\}/);
if (!match) {
  failures.push("isNearNavViewport not found in app.js");
} else {
  const sandbox = {};
  vm.createContext(sandbox);
  vm.runInContext(`${match[0]}; result = isNearNavViewport;`, sandbox, {
    filename: "isNearNavViewport.js",
  });
  const isNearNavViewport = sandbox.result;

  // The nav scroller: 720 px tall, starting 140 px down the page.
  const view = { top: 140, bottom: 860, height: 720 };
  const lookahead = view.height;

  /**
   * A tree row. `collapsedAncestor` stands in for the `.tree-children-collapsed`
   * closest() would find; the rect is what the row reports either way, which is
   * the whole point — a clipped row still measures 24 px tall.
   */
  const row = (top, options = {}) => ({
    closest: (selector) =>
      selector === ".tree-children-collapsed" && options.collapsedAncestor ? {} : null,
    getBoundingClientRect: () => ({
      top,
      bottom: top + (options.height === undefined ? 24 : options.height),
      height: options.height === undefined ? 24 : options.height,
    }),
  });

  const cases = [
    ["a row in the middle of the nav is a candidate", row(400), true],
    ["a row at the very top edge is a candidate", row(140), true],
    ["a row at the very bottom edge is a candidate", row(836), true],
    ["one screen above is still a candidate: a reader scrolls both ways", row(-500), true],
    ["one screen below is a candidate: that is the lookahead", row(1500), true],
    ["two screens below is not", row(2400), false],
    ["two screens above is not", row(-1400), false],
    [
      "a row inside a collapsed branch is not, even sitting in the viewport",
      row(400, { collapsedAncestor: true }),
      false,
    ],
    ["a row with no box at all is not", row(400, { height: 0 }), false],
    ["a missing row is not", null, false],
  ];

  for (const [label, subject, expected] of cases) {
    const actual = isNearNavViewport(subject, view, lookahead);
    if (actual !== expected) {
      failures.push(`${label}: expected ${expected}, got ${actual}`);
    }
  }
}

// Source-level guards. The helper is only worth having if the sweep calls it,
// and only safe if a shell that has not laid out yet falls back to the
// unbounded sweep rather than silently prefetching nothing forever.
const sweep = appSource.match(/function pendingSubtreePaths\(\) \{[\s\S]*?\n\}/);
if (!sweep) {
  failures.push("pendingSubtreePaths not found in app.js");
} else {
  if (!sweep[0].includes("isNearNavViewport")) {
    failures.push("pendingSubtreePaths no longer bounds its candidates to the viewport");
  }
  if (!/measured\.height > 0/.test(sweep[0])) {
    failures.push(
      "pendingSubtreePaths no longer falls back when the scroller has not been laid out",
    );
  }
}

// Opening a folder is the other thing that puts rows on screen. Without this
// the bound would warm nothing past the first screen.
if (
  !/if \(expanded\) \{[\s\S]{0,400}?scheduleSubtreePrefetch\(\{ afterExpand: true \}\);/.test(
    appSource,
  )
) {
  failures.push("setFolderExpanded no longer re-arms the sweep when a folder opens");
}
// And it must not wait for idle to do it. A browser is free to defer an idle
// callback indefinitely -- measured here at over 30 seconds in a hidden tab --
// so the sweep a reader just asked for runs on a timer instead.
const scheduler = appSource.match(/function scheduleSubtreePrefetch\(options\) \{[\s\S]*?\n\}/);
if (!scheduler) {
  failures.push("scheduleSubtreePrefetch(options) not found in app.js");
} else if (
  !/options\?\.afterExpand[\s\S]*?setTimeout\(run, SUBTREE_PREFETCH_AFTER_EXPAND_MS\)/.test(
    scheduler[0],
  )
) {
  failures.push("an expansion's sweep is back on the idle path");
}
if (!/addEventListener\(\n?\s*"scroll",/.test(appSource)) {
  failures.push("the nav scroller no longer re-arms the sweep");
}

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log("ok");
