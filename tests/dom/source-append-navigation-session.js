// Exact browserless session for production incremental-source cache transactions.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const sourceAppendPath = path.join(repoRoot, "src/metabrowser/static/source-append.js");
const sandbox = { Map, Math, Number, Object, String };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(sourceAppendPath, "utf8"), sandbox, {
  filename: sourceAppendPath,
});

const sourceAppend = sandbox.MetabrowserSourceAppend;

function createState() {
  const cached = {
    bytes_read: 3,
    content: "old",
    content_bytes: 3,
    content_truncated: true,
    highlight_disabled: false,
    mtime_hash: "same",
  };
  return {
    activeClaim: 1,
    cache: new Map([["same.txt", cached]]),
    cached,
    currentPath: "same.txt",
  };
}

function transactionOptions(state, nextCached) {
  return {
    cached: state.cached,
    cachedForPath: state.cache.get("same.txt"),
    claim: 1,
    commit: (value) => state.cache.set("same.txt", value),
    currentPath: state.currentPath,
    isClaimCurrent: (claim) => claim === state.activeClaim,
    nextCached,
    path: "same.txt",
    requested: 128,
    requestCap: 1024,
  };
}

const chunk = {
  bytes_read: 6,
  content: "new",
  content_bytes: 3,
  content_truncated: false,
  highlight_disabled: false,
};

const retry = createState();
const stagedRetry = sourceAppend.nextCacheValue(retry.cached, chunk);
// A renderer failure simply discards the staged value. No live cursor moves.
const afterFailedRender = {
  cacheIsOriginal: retry.cache.get("same.txt") === retry.cached,
  content: retry.cache.get("same.txt").content,
  cursor: retry.cache.get("same.txt").bytes_read,
  nextBytes: 128,
  truncated: retry.cache.get("same.txt").content_truncated,
};
const nextBytes = sourceAppend.commitChunkCache(transactionOptions(retry, stagedRetry));

const aba = createState();
const stagedAba = sourceAppend.nextCacheValue(aba.cached, {
  ...chunk,
  content: "stale",
  content_bytes: 5,
});
aba.activeClaim = 2;
const abaNextBytes = sourceAppend.commitChunkCache(transactionOptions(aba, stagedAba));

const replacement = createState();
const stagedReplacement = sourceAppend.nextCacheValue(replacement.cached, chunk);
replacement.cache.set("same.txt", { ...replacement.cached, content: "replacement" });
const replacementNextBytes = sourceAppend.commitChunkCache(
  transactionOptions(replacement, stagedReplacement),
);

process.stdout.write(
  `${JSON.stringify(
    {
      afterFailedRender,
      afterRetryCommit: {
        cacheIsOriginal: retry.cache.get("same.txt") === retry.cached,
        content: retry.cache.get("same.txt").content,
        cursor: retry.cache.get("same.txt").bytes_read,
        nextBytes,
        truncated: retry.cache.get("same.txt").content_truncated,
      },
      samePathAba: {
        committed: abaNextBytes !== null,
        content: aba.cache.get("same.txt").content,
        nextBytes: abaNextBytes,
      },
      cacheReplacement: {
        committed: replacementNextBytes !== null,
        content: replacement.cache.get("same.txt").content,
        nextBytes: replacementNextBytes,
      },
    },
    null,
    2,
  )}\n`,
);
