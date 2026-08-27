// Structural checks for the bounded Git history page cache and virtual window.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const failures = [];

function assertEqual(label, actual, expected) {
  const a = JSON.stringify(actual);
  const b = JSON.stringify(expected);
  if (a !== b) {
    failures.push(`${label}: expected ${b} got ${a}`);
  }
}

function assertTrue(label, value) {
  if (!value) {
    failures.push(`${label}: expected true`);
  }
}

const sandbox = { window: {}, console, Number, Math, Map, Object, RangeError, Error };
sandbox.window = sandbox;
vm.createContext(sandbox);
const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/git-history-window.js"),
  "utf-8",
);
vm.runInContext(source, sandbox, { filename: "git-history-window.js" });
const historyWindow = sandbox.MetabrowserGitHistoryWindow;

function page(number, dispose) {
  return {
    page: number,
    startOrdinal: number * 250,
    commits: [],
    checkpoint: {
      version: 1,
      priorSwimlanes: [],
      colorIndex: -1,
      headRevision: null,
      scopeFingerprint: "scope",
    },
    pageCursor: `page-${number}`,
    nextCursor: `next-${number}`,
    previousCursor: number === 0 ? null : `page-${number - 1}`,
    dispose,
  };
}

// The decoded cache is exact LRU, never exceeds its configured budget, and
// disposes both evicted and explicitly cleared page ownership.
{
  const disposed = [];
  const cache = historyWindow.createPageCache({ maxPages: 8 });
  for (let i = 0; i < 8; i += 1) {
    cache.put(page(i, () => disposed.push(i)));
  }
  assertEqual("cache: fills to budget", cache.size, 8);
  assertTrue("cache: hit returns the page", cache.get(0)?.page === 0);
  cache.put(page(8, () => disposed.push(8)));
  assertEqual("cache: remains bounded", cache.size, 8);
  assertEqual("cache: hit promoted page zero", cache.keys(), [2, 3, 4, 5, 6, 7, 0, 8]);
  assertEqual("cache: least recently used page disposed", disposed, [1]);
  cache.put(page(0, () => disposed.push(100)));
  assertEqual("cache: replacing a page disposes old ownership", disposed, [1, 0]);
  cache.clear();
  assertEqual("cache: clear drops every decoded page", cache.size, 0);
  assertEqual("cache: clear invokes every remaining disposer", disposed.length, 10);
  cache.dispose();
  cache.dispose();
}

// Teardown gives up every owned page even when one page-specific disposer
// fails. The first error still reaches the caller after the cache is empty.
{
  const disposed = [];
  const cache = historyWindow.createPageCache({ maxPages: 3 });
  cache.put(
    page(0, () => {
      disposed.push(0);
      throw new Error("disposal failed");
    }),
  );
  cache.put(page(1, () => disposed.push(1)));
  let threw = false;
  try {
    cache.dispose();
  } catch {
    threw = true;
  }
  assertTrue("cache: disposal reports the first ownership error", threw);
  assertEqual("cache: disposal attempts every page owner", disposed, [0, 1]);
  assertEqual("cache: failed disposal still empties the cache", cache.size, 0);
  threw = false;
  try {
    cache.get(0);
  } catch {
    threw = true;
  }
  assertTrue("cache: failed disposal still seals the cache", threw);
}

// The measured 22 px model mounts only a bounded viewport plus at most the
// measured overscan on either side. Spacers account for every unmounted row.
{
  const virtual = historyWindow.createVirtualWindow({
    rowHeight: 22,
    maxRows: 256,
    overscanRows: 64,
    rebasePx: 8_000_000,
  });
  virtual.setRowCount(10_000);
  const top = virtual.read(0, 900);
  assertEqual("window: begins at first ordinal", top.start, 0);
  assertTrue("window: top mounts within hard bound", top.end - top.start <= 256);
  assertEqual("window: top spacer is empty", top.topSpacerPx, 0);
  assertEqual(
    "window: top spacers preserve logical height",
    top.topSpacerPx + (top.end - top.start) * 22 + top.bottomSpacerPx,
    top.segmentHeightPx,
  );

  const middle = virtual.read(5_000 * 22, 900);
  assertTrue("window: middle has leading overscan", middle.start < middle.visibleStart);
  assertTrue("window: middle has trailing overscan", middle.end > middle.visibleEnd);
  assertTrue("window: middle stays under row budget", middle.end - middle.start <= 256);
  assertTrue("window: leading overscan is bounded", middle.visibleStart - middle.start <= 64);
  assertTrue("window: trailing overscan is bounded", middle.end - middle.visibleEnd <= 64);
  assertEqual(
    "window: middle spacers preserve logical height",
    middle.topSpacerPx + (middle.end - middle.start) * 22 + middle.bottomSpacerPx,
    middle.segmentHeightPx,
  );
}

// A synthetic small segment forces both forward and backward rebasing. The
// logical row at the viewport top and its intra-row pixel offset do not move.
{
  const virtual = historyWindow.createVirtualWindow({
    rowHeight: 10,
    maxRows: 20,
    overscanRows: 5,
    rebasePx: 1_000,
  });
  virtual.setRowCount(1_000);
  assertEqual(
    "rebase: segment capacity derives from measured pixels",
    virtual.segmentCapacity,
    100,
  );
  const forward = virtual.read(807, 100);
  assertTrue("rebase: forward edge moves the segment", forward.rebased);
  assertEqual("rebase: logical top survives forward rebase", forward.visibleStart, 80);
  assertEqual("rebase: segment height never exceeds budget", forward.segmentHeightPx, 1_000);

  const backward = virtual.read(0, 100);
  assertTrue("rebase: backward edge moves the segment", backward.rebased);
  assertEqual("rebase: earlier logical rows become reachable", backward.visibleStart, 35);

  const targetScroll = virtual.scrollTopForOrdinal(900, 100, "center");
  const target = virtual.read(targetScroll, 100);
  assertTrue("rebase: direct target is mounted", target.start <= 900 && 900 < target.end);
  assertTrue(
    "rebase: direct target is visible",
    target.visibleStart <= 900 && 900 < target.visibleEnd,
  );
  virtual.dispose();
  let threw = false;
  try {
    virtual.read(0, 100);
  } catch {
    threw = true;
  }
  assertTrue("rebase: disposed model rejects retained work", threw);
}

if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log("OK git history window behavior");
