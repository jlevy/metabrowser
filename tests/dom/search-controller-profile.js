const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { performance } = require("node:perf_hooks");

const repoRoot = path.resolve(__dirname, "../..");
let fetchCalls = 0;
const sandbox = {
  AbortController,
  clearTimeout,
  fetch() {
    fetchCalls += 1;
    throw new Error("Local known-file search must not fetch");
  },
  setTimeout,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

for (const filename of ["known-file-catalog.js", "file-fuzzy-match.js", "search-controller.js"]) {
  vm.runInContext(
    fs.readFileSync(path.join(repoRoot, "src/metabrowser/static", filename), "utf-8"),
    sandbox,
    { filename },
  );
}

function syntheticEntries(count, prefix) {
  return Array.from({ length: count }, (_, index) => {
    const ordinal = String(index).padStart(5, "0");
    const shard = String(index % 257).padStart(3, "0");
    return {
      logical_ext: ".json",
      path: `${prefix}/shard-${shard}/nested/result-file-${ordinal}.json`,
      type: "file",
    };
  });
}

function createCatalog(count, prefix) {
  const catalog = sandbox.MetabrowserKnownFileCatalog.create();
  catalog.observeEventSnapshot(syntheticEntries(count, prefix));
  return catalog;
}

function timerPromise(startedAt) {
  let firedAt = null;
  const promise = new Promise((resolve) => {
    setTimeout(() => {
      firedAt = performance.now();
      resolve();
    }, 0);
  });
  return {
    delayMs: () => (firedAt === null ? null : Number((firedAt - startedAt).toFixed(2))),
    firedAt: () => firedAt,
    promise,
  };
}

async function profileCatalog(label, candidateCount) {
  const catalog = createCatalog(candidateCount, label);
  let yieldCount = 0;
  const provider = sandbox.MetabrowserSearch.createLocalFileProvider({
    catalog,
    chunkSize: 250,
    matcher: sandbox.MetabrowserFileFuzzyMatch,
    maxResults: 100,
    syncThreshold: 500,
    yieldControl: async () => {
      yieldCount += 1;
      await new Promise((resolve) => setTimeout(resolve, 0));
    },
  });
  const controller = sandbox.MetabrowserSearch.createController({ maxResults: 100 });
  controller.registerProvider(provider);

  const startedAt = performance.now();
  const inputTimer = timerPromise(startedAt);
  const state = await controller.search({ match: "fuzzy", query: "rfl", target: "file" });
  const completedAt = performance.now();
  await inputTimer.promise;
  const result = {
    candidateCount,
    firstResultMs: Number((completedAt - startedAt).toFixed(2)),
    inputDelayMs: inputTimer.delayMs(),
    resultCount: state.results.length,
    timerBeforeCompletion: inputTimer.firedAt() !== null && inputTimer.firedAt() <= completedAt,
    truncated: state.truncated,
    yieldCount,
  };
  controller.dispose();
  return result;
}

async function profileCancellation() {
  const catalog = createCatalog(5_000, "cancellation");
  const provider = sandbox.MetabrowserSearch.createLocalFileProvider({
    catalog,
    chunkSize: 250,
    matcher: sandbox.MetabrowserFileFuzzyMatch,
    maxResults: 100,
    syncThreshold: 500,
    yieldControl: () => new Promise((resolve) => setTimeout(resolve, 0)),
  });
  const controller = sandbox.MetabrowserSearch.createController({ maxResults: 100 });
  controller.registerProvider(provider);
  const publishedCompletions = [];
  controller.subscribe((state) => {
    if (state.phase === "complete" && state.request) {
      publishedCompletions.push(state.request.query);
    }
  });

  const startedAt = performance.now();
  const obsoleteSearch = controller.search({ match: "fuzzy", query: "rfl", target: "file" });
  const currentSearch = controller.search({
    match: "fuzzy",
    query: "result-file-04999.json",
    target: "file",
  });
  const [obsoleteState, currentState] = await Promise.all([obsoleteSearch, currentSearch]);
  const result = {
    elapsedMs: Number((performance.now() - startedAt).toFixed(2)),
    finalFirstPath: currentState.results[0]?.path || null,
    finalResultCount: currentState.results.length,
    obsoleteResultWasDiscarded: obsoleteState === null,
    publishedObsoleteCompletion: publishedCompletions.includes("rfl"),
  };
  controller.dispose();
  return result;
}

async function main() {
  const report = {
    cancellation: await profileCancellation(),
    expanded: await profileCatalog("expanded", 50_000),
    node: process.version,
    recent: await profileCatalog("recent", 2_000),
    shallow: await profileCatalog("shallow", 50),
  };
  const failures = [];
  if (fetchCalls !== 0) {
    failures.push(`unexpected fetch calls: ${fetchCalls}`);
  }
  if (report.shallow.resultCount !== 50) {
    failures.push("shallow result count is not 50");
  }
  if (report.recent.resultCount !== 100) {
    failures.push("Recent result count is not bounded at 100");
  }
  if (report.expanded.resultCount !== 100) {
    failures.push("expanded result count is not bounded at 100");
  }
  if (!report.recent.timerBeforeCompletion || !report.expanded.timerBeforeCompletion) {
    failures.push("large scans did not yield to an already queued input timer");
  }
  if (!report.cancellation.obsoleteResultWasDiscarded) {
    failures.push("obsolete search returned publishable state");
  }
  if (report.cancellation.publishedObsoleteCompletion) {
    failures.push("obsolete search published a completion");
  }
  if (report.shallow.firstResultMs > 1_000) {
    failures.push("shallow profile exceeded 1 second");
  }
  if (report.recent.firstResultMs > 5_000) {
    failures.push("Recent profile exceeded 5 seconds");
  }
  if (report.expanded.firstResultMs > 20_000) {
    failures.push("expanded profile exceeded 20 seconds");
  }

  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n${JSON.stringify(report)}\n`);
    process.exit(1);
  }
  process.stdout.write(`PROFILE ${JSON.stringify(report)}\n`);
}

main().catch((error) => {
  process.stderr.write(`${error?.stack || error}\n`);
  process.exit(1);
});
