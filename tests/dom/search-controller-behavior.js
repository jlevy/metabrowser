const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

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

const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

function equal(label, actual, expected) {
  check(label, JSON.stringify(actual) === JSON.stringify(expected), JSON.stringify(actual));
}

function fileResult(pathname, score) {
  const separator = pathname.lastIndexOf("/");
  return {
    description: separator >= 0 ? pathname.slice(0, separator) : "",
    id: `file:${pathname}`,
    kind: "file",
    label: pathname.slice(separator + 1),
    matchRanges: [],
    path: pathname,
    score,
  };
}

async function main() {
  const catalog = sandbox.MetabrowserKnownFileCatalog.create();
  catalog.observeRecent([
    { path: "src/application.js", type: "file" },
    { path: "src/app.js", type: "file", logical_ext: ".js" },
    { path: "examples/happy.js", type: "file" },
    { path: "app/config.js", type: "file" },
    { path: "docs/guide.md", type: "file" },
  ]);

  let yields = 0;
  const localProvider = sandbox.MetabrowserSearch.createLocalFileProvider({
    catalog,
    chunkSize: 2,
    matcher: sandbox.MetabrowserFileFuzzyMatch,
    maxResults: 2,
    syncThreshold: 2,
    yieldControl: async () => {
      yields += 1;
    },
  });
  const localBatch = await localProvider.search(
    { match: "fuzzy", query: "app", target: "file" },
    { requestId: 1 },
    new AbortController().signal,
  );
  equal(
    "local provider preserves fuzzy order and bounds results",
    localBatch.results.map((result) => result.path),
    ["src/app.js", "src/application.js"],
  );
  check("local coverage remains incomplete", localBatch.complete === false);
  check("result truncation is independent", localBatch.truncated === true);
  check("provider reports observed candidate count", localBatch.candidateCount === 5);
  equal(
    "incomplete results report matches and scope concisely",
    localBatch.statusMessage,
    "4 matches in 5 indexed files. Scanning continues.",
  );
  check("large local scans yield between chunks", yields === 2, String(yields));
  check("provider is DOM independent", !("document" in sandbox));
  check("local provider performs no search request", fetchCalls === 0, String(fetchCalls));
  const emptyIncompleteBatch = await localProvider.search(
    { match: "fuzzy", query: "not-present", target: "file" },
    { requestId: 2 },
    new AbortController().signal,
  );
  equal(
    "incomplete empty results report scope without repeated instructions",
    emptyIncompleteBatch.statusMessage,
    "No matches in 5 indexed files. Scanning continues.",
  );
  const alreadyAborted = new AbortController();
  alreadyAborted.abort();
  let abortName = "";
  try {
    await localProvider.search(
      { match: "fuzzy", query: "app", target: "file" },
      { requestId: 2 },
      alreadyAborted.signal,
    );
  } catch (error) {
    abortName = error?.name || "";
  }
  check("local provider honors AbortSignal", abortName === "AbortError", abortName);

  const localController = sandbox.MetabrowserSearch.createController({ maxResults: 2 });
  const unregisterLocal = localController.registerProvider(localProvider);
  const localState = await localController.search({
    match: "fuzzy",
    query: "app",
    target: "file",
  });
  equal(
    "controller composes local file results",
    localState.results.map((result) => result.path),
    ["src/app.js", "src/application.js"],
  );
  check("controller preserves incomplete metadata", localState.complete === false);
  check("controller preserves truncation metadata", localState.truncated === true);
  check("controller state is immutable", Object.isFrozen(localState));
  unregisterLocal();
  localController.dispose();

  catalog.markComplete();
  const completeBatch = await localProvider.search(
    { match: "fuzzy", query: "guide", target: "file" },
    { requestId: 3 },
    new AbortController().signal,
  );
  equal("one complete result uses a singular match", completeBatch.statusMessage, "1 match.");

  let resolveFirst;
  let firstSignal;
  const delayedProvider = {
    id: "delayed",
    priority: 10,
    search(request, _context, signal) {
      if (request.query === "first") {
        firstSignal = signal;
        return new Promise((resolve) => {
          resolveFirst = resolve;
        });
      }
      return Promise.resolve({
        complete: true,
        providerId: "delayed",
        results: [fileResult("second.md", 1)],
        truncated: false,
      });
    },
    supports: () => true,
  };
  const cancellationController = sandbox.MetabrowserSearch.createController();
  cancellationController.registerProvider(delayedProvider);
  const publishedQueries = [];
  cancellationController.subscribe((state) => {
    if (state.request) {
      publishedQueries.push(state.request.query);
    }
  });
  const obsoleteSearch = cancellationController.search({
    match: "fuzzy",
    query: "first",
    target: "file",
  });
  await Promise.resolve();
  const currentSearch = cancellationController.search({
    match: "fuzzy",
    query: "second",
    target: "file",
  });
  const currentState = await currentSearch;
  check("new request aborts the previous signal", firstSignal?.aborted === true);
  equal(
    "current request publishes its result",
    currentState.results.map((result) => result.path),
    ["second.md"],
  );
  resolveFirst({
    complete: true,
    providerId: "delayed",
    results: [fileResult("first.md", 99)],
    truncated: false,
  });
  check("obsolete search resolves without state", (await obsoleteSearch) === null);
  check(
    "late result cannot replace current state",
    cancellationController.state() === currentState,
  );
  check(
    "obsolete completion is never published after the current result",
    publishedQueries[publishedQueries.length - 1] === "second",
    JSON.stringify(publishedQueries),
  );
  cancellationController.dispose();

  const compositionController = sandbox.MetabrowserSearch.createController({ maxResults: 3 });
  compositionController.registerProvider({
    id: "lower-priority",
    priority: 20,
    search: async () => ({
      complete: false,
      providerId: "lower-priority",
      results: [fileResult("same.md", 5), fileResult("z-last.md", 1)],
      truncated: true,
    }),
    supports: () => true,
  });
  compositionController.registerProvider({
    id: "higher-priority",
    priority: 10,
    search: async () => ({
      complete: true,
      providerId: "higher-priority",
      results: [fileResult("same.md", 8), fileResult("a-first.md", 1)],
      truncated: false,
    }),
    supports: () => true,
  });
  const composed = await compositionController.search({
    match: "fuzzy",
    query: "same",
    target: "file",
  });
  equal(
    "composition deduplicates by path and sorts stable ties by path",
    composed.results.map((result) => [result.path, result.providerId]),
    [
      ["same.md", "higher-priority"],
      ["a-first.md", "higher-priority"],
      ["z-last.md", "lower-priority"],
    ],
  );
  check("one incomplete provider keeps composition incomplete", composed.complete === false);
  check("one truncated provider keeps composition truncated", composed.truncated === true);
  compositionController.dispose();

  let fallbackCalls = 0;
  const fallbackController = sandbox.MetabrowserSearch.createController();
  let invalidActivationRejected = false;
  try {
    fallbackController.registerProvider({
      activation: "typo",
      id: "invalid-activation",
      search: async () => ({ complete: true, results: [], truncated: false }),
    });
  } catch (error) {
    invalidActivationRejected = error?.name === "TypeError";
  }
  check("unknown provider activation is rejected", invalidActivationRejected);
  fallbackController.registerProvider({
    id: "observed-files",
    priority: 10,
    search: async (request) => ({
      complete: false,
      providerId: "observed-files",
      results: request.query === "hit" ? [fileResult("local-hit.md", 2)] : [],
      truncated: false,
    }),
    supports: () => true,
  });
  fallbackController.registerProvider({
    activation: "fallback",
    id: "indexed-files",
    priority: 20,
    search: async () => {
      fallbackCalls += 1;
      return {
        complete: true,
        providerId: "indexed-files",
        results: [fileResult("server-hit.md", 1)],
        truncated: false,
      };
    },
    supports: () => true,
  });
  const localHit = await fallbackController.search({
    match: "fuzzy",
    query: "hit",
    target: "file",
  });
  equal(
    "a local hit does not start the deferred provider",
    localHit.results.map((result) => result.path),
    ["local-hit.md"],
  );
  check("deferred provider remains idle after a local hit", fallbackCalls === 0);
  const fallbackHit = await fallbackController.search({
    match: "fuzzy",
    query: "miss",
    target: "file",
  });
  equal(
    "an empty incomplete local batch starts the fallback provider",
    fallbackHit.results.map((result) => result.path),
    ["server-hit.md"],
  );
  check("fallback provider ran once", fallbackCalls === 1, String(fallbackCalls));
  await fallbackController.search(
    { match: "fuzzy", query: "hit", target: "file" },
    { includeFallback: true },
  );
  check("an explicit complete search includes fallback providers", fallbackCalls === 2);
  fallbackController.dispose();

  if (failures.length > 0) {
    process.stderr.write(`${failures.join("\n")}\n`);
    process.exit(1);
  }
  process.stdout.write("OK headless search controller\n");
}

main().catch((error) => {
  process.stderr.write(`${error?.stack || error}\n`);
  process.exit(1);
});
