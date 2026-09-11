// Exact production session for the catalog's cross-runtime ordering boundary.
//
// The inventory provider orders valid paths by UTF-8 bytes, which agrees with
// Unicode code-point order. JavaScript's relational comparison orders UTF-16
// code units instead. A private-use BMP prefix therefore arrives before an
// astral prefix from the provider, while the browser must publish the astral
// prefix first. At scale, inserting every astral row at the front turns one
// scheduled slice into quadratic Array.splice work.

const fs = require("node:fs");
const path = require("node:path");
const { performance } = require("node:perf_hooks");
const vm = require("node:vm");

const FILES_PER_PREFIX = Number(process.env.METABROWSER_TEST_UNICODE_FILES_PER_PREFIX || "20000");
const repoRoot = path.resolve(__dirname, "../..");
const measurements = [];
const sandbox = { clearTimeout, setTimeout };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.metabrowser = {
  perf: {
    measure(label, fn, metadata = {}) {
      const started = performance.now();
      const result = fn();
      measurements.push({ duration_ms: performance.now() - started, label, ...metadata });
      return result;
    },
    measureAsync(_label, fn) {
      return fn();
    },
  },
};
vm.createContext(sandbox);

for (const filename of ["known-file-catalog.js", "catalog-feed.js"]) {
  const sourcePath = path.join(repoRoot, "src/metabrowser/static", filename);
  const source = fs.readFileSync(sourcePath, "utf-8");
  vm.runInContext(source, sandbox, { filename: sourcePath });
}

const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

function providerOrderedFiles() {
  const rows = [];
  for (const prefix of ["\ue000", "\u{1f600}"]) {
    for (let index = 0; index < FILES_PER_PREFIX; index++) {
      rows.push({
        e: ".txt",
        p: `unicode/${prefix}/file-${String(index).padStart(5, "0")}.txt`,
      });
    }
  }
  return rows;
}

async function main() {
  const files = providerOrderedFiles();
  const catalog = sandbox.MetabrowserKnownFileCatalog.create();
  const scheduledTurns = [];
  const feed = sandbox.MetabrowserCatalogFeed.create({
    catalog,
    fetchImpl: async () => ({
      headers: { get: () => null },
      text: async () => JSON.stringify({ complete: true, files }),
      ok: true,
      status: 200,
    }),
    yieldControl: () =>
      new Promise((resolve) => {
        scheduledTurns.push(resolve);
      }),
  });

  feed.start();
  await tick();
  await tick();
  check("Unicode bulk schedules continuation", scheduledTurns.length === 1);

  let turns = 0;
  while (turns < 1_000) {
    const continuation = scheduledTurns.shift();
    if (continuation) {
      continuation();
      turns += 1;
    }
    await tick();
    if (scheduledTurns.length === 0 && catalog.snapshot().complete) {
      break;
    }
  }

  const slices = measurements.filter(
    (measurement) => measurement.label === "knownFileCatalog:applyBulkSnapshot",
  );
  const sliceLimit = sandbox.MetabrowserCatalogFeed.BULK_APPLY_SLICE_ITEMS;
  const maxDuration = Math.max(...slices.map((measurement) => measurement.duration_ms));
  const maxWorkItems = Math.max(...slices.map((measurement) => measurement.work_items || 0));
  check("Unicode catalog finishes within scheduler guard", turns < 1_000, String(turns));
  check("Unicode ordering conversion spans multiple task slices", slices.length > 10);
  check(
    "every Unicode conversion slice respects the production work bound",
    maxWorkItems <= sliceLimit,
    String(maxWorkItems),
  );
  check(
    "every Unicode conversion slice stays below the 50 ms responsiveness gate",
    maxDuration < 50,
    String(maxDuration),
  );

  const snapshot = catalog.snapshot();
  const firstAstral = `unicode/\u{1f600}/file-00000.txt`;
  const lastAstral = `unicode/\u{1f600}/file-${String(FILES_PER_PREFIX - 1).padStart(5, "0")}.txt`;
  const firstBmp = "unicode/\ue000/file-00000.txt";
  const lastBmp = `unicode/\ue000/file-${String(FILES_PER_PREFIX - 1).padStart(5, "0")}.txt`;
  check("Unicode catalog publishes complete coverage", snapshot.complete === true);
  check("Unicode catalog publishes every provider row", snapshot.observedCount === files.length);
  check(
    "Unicode catalog converts provider order to canonical browser order",
    snapshot.files[0]?.path === firstAstral &&
      snapshot.files[FILES_PER_PREFIX - 1]?.path === lastAstral &&
      snapshot.files[FILES_PER_PREFIX]?.path === firstBmp &&
      snapshot.files.at(-1)?.path === lastBmp,
    `${snapshot.files[0]?.path}/${snapshot.files[FILES_PER_PREFIX]?.path}`,
  );
  feed.dispose();

  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.exit(1);
  }
  process.stdout.write(
    `${JSON.stringify(
      {
        browserOrder: ["astral", "bmp-private-use"],
        complete: snapshot.complete,
        files: snapshot.observedCount,
        providerOrder: ["bmp-private-use", "astral"],
        sliced: slices.length > 10,
        workItemLimit: sliceLimit,
      },
      null,
      2,
    )}\n`,
  );
}

main();
