// Exact browserless session for production file-navigation ownership primitives.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const navigationPath = path.join(repoRoot, "src/metabrowser/static/navigation.js");
const sandbox = { Array, Error, Map, Number, Object, Promise, String, TypeError, URIError };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(navigationPath, "utf8"), sandbox, {
  filename: navigationPath,
});

const navigation = sandbox.MetabrowserNavigationRoute;

function createCacheState(pathName, revision = "old") {
  return {
    cache: new Map([[pathName, { kind: "text", path: pathName, revision }]]),
    validators: new Map([[pathName, `"${revision}"`]]),
  };
}

function commitResponse(state, pathName, data, etag, isCurrent) {
  return navigation.commitFreshFileResponse({
    cacheFile: (fresh) => state.cache.set(pathName, fresh),
    cacheValidator: (freshEtag) => state.validators.set(pathName, freshEtag),
    data,
    etag,
    evictFile: () => state.cache.delete(pathName),
    evictValidator: () => state.validators.delete(pathName),
    isCurrent,
  });
}

async function main() {
  const dependency = await navigation.settleNavigationDependency(
    Promise.reject(new Error("compositor unavailable")),
  );

  const samePath = createCacheState("same.md");
  const samePathTracker = navigation.createFileRevalidationTracker(4);
  samePathTracker.add("same.md");
  const olderMarker = samePathTracker.capture("same.md");
  // A replacement begins before the older request settles. The marker remains
  // visible, so the replacement must revalidate instead of taking hot cache.
  const replacementSawDirty = samePathTracker.has("same.md");
  const newerMarker = samePathTracker.capture("same.md");
  const newerCommit = commitResponse(
    samePath,
    "same.md",
    { kind: "text", path: "same.md", revision: "B" },
    '"B"',
    () => true,
  );
  const newerSettled = samePathTracker.settle("same.md", newerMarker);
  const olderAbort = navigation.settleFileSelectionFailure({
    cached: true,
    error: Object.assign(new Error("superseded"), { name: "AbortError" }),
    isCurrent: () => false,
    markForRevalidation: () => samePathTracker.add("same.md"),
    path: "same.md",
    showError: () => {
      throw new Error("a superseded selection must not paint an error");
    },
  });
  const lateOlderCommit = commitResponse(
    samePath,
    "same.md",
    { kind: "text", path: "same.md", revision: "A" },
    '"A"',
    () => false,
  );

  const shapeChange = createCacheState("shape-change");
  const shapeTracker = navigation.createFileRevalidationTracker(4);
  shapeTracker.add("shape-change");
  const requestMarker = shapeTracker.capture("shape-change");
  // A filesystem event during the request owns a newer marker.
  shapeTracker.add("shape-change");
  const folderCommit = commitResponse(
    shapeChange,
    "shape-change",
    { kind: "folder", path: "shape-change" },
    '"folder"',
    () => true,
  );
  const olderMarkerSettled = shapeTracker.settle("shape-change", requestMarker);

  const noValidator = createCacheState("no-validator.md");
  const noValidatorTracker = navigation.createFileRevalidationTracker(4);
  noValidatorTracker.add("no-validator.md");
  const noValidatorMarker = noValidatorTracker.capture("no-validator.md");
  const noValidatorCommit = commitResponse(
    noValidator,
    "no-validator.md",
    { kind: "text", path: "no-validator.md", revision: "fresh" },
    null,
    () => true,
  );
  const noValidatorSettled = noValidatorTracker.settle("no-validator.md", noValidatorMarker);

  const boundedTracker = navigation.createFileRevalidationTracker(2);
  boundedTracker.add("one.md");
  boundedTracker.add("two.md");
  boundedTracker.add("three.md");

  // FileStore after a snapshot and its scoped deltas: two logs and a folder
  // the reader expanded, whose children were loaded through /api/tree and so
  // live only in the rendered tree. A resync keeps this store as the baseline;
  // the reconnect snapshot then omits gone.jsonl and adds new.jsonl.
  const renderedRows = new Map([
    ["gone.jsonl", { children: [], expanded: false }],
    ["kept.jsonl", { children: [], expanded: false }],
    ["src", { children: ["src/lazy/deep.md"], expanded: true }],
  ]);
  const activeSnapshotPaths = new Set(["gone.jsonl", "kept.jsonl"]);
  let installedSnapshot = new Map([
    ["gone.jsonl", { active: true, path: "gone.jsonl" }],
    ["kept.jsonl", { active: true, path: "kept.jsonl" }],
    ["src", { active: false, path: "src", type: "dir" }],
  ]);
  const snapshotActions = [];
  navigation.replaceFileSnapshot(
    installedSnapshot,
    [
      { active: false, path: "kept.jsonl" },
      { active: true, path: "new.jsonl" },
      { active: false, path: "src", type: "dir" },
    ],
    {
      install(next) {
        installedSnapshot = next;
        snapshotActions.push(["install", Array.from(next.keys())]);
      },
      retire(pathName) {
        activeSnapshotPaths.delete(pathName);
        renderedRows.delete(pathName);
        snapshotActions.push(["retire", pathName, installedSnapshot.has(pathName)]);
      },
      upsert(entry) {
        if (entry.active) {
          activeSnapshotPaths.add(entry.path);
        } else {
          activeSnapshotPaths.delete(entry.path);
        }
        if (!renderedRows.has(entry.path)) {
          renderedRows.set(entry.path, { children: [], expanded: false });
        }
        snapshotActions.push(["upsert", entry.path, installedSnapshot.has(entry.path)]);
      },
    },
  );

  process.stdout.write(
    `${JSON.stringify(
      {
        dependencyFailure: {
          error: dependency.error.message,
          status: dependency.status,
        },
        samePathRevalidation: {
          cachedRevision: samePath.cache.get("same.md").revision,
          dirty: samePathTracker.has("same.md"),
          etag: samePath.validators.get("same.md"),
          lateOlderCommit,
          markerSharedByPendingRequests: olderMarker === newerMarker,
          newerCommit,
          newerSettled,
          olderAbort,
          replacementSawDirty,
        },
        fileToFolderEventRace: {
          cacheRetained: shapeChange.cache.has("shape-change"),
          dirty: shapeTracker.has("shape-change"),
          etagRetained: shapeChange.validators.has("shape-change"),
          folderCommit,
          olderMarkerSettled,
        },
        missingValidatorResponse: {
          cachedRevision: noValidator.cache.get("no-validator.md").revision,
          dirty: noValidatorTracker.has("no-validator.md"),
          noValidatorCommit,
          noValidatorSettled,
          validatorRetained: noValidator.validators.has("no-validator.md"),
        },
        boundedInvalidations: {
          oldestRetained: boundedTracker.has("one.md"),
          retained: Array.from(boundedTracker.keys()),
          size: boundedTracker.size,
        },
        authoritativeSnapshot: {
          actions: snapshotActions,
          active: Array.from(activeSnapshotPaths),
          paths: Array.from(installedSnapshot.keys()),
          renderedRows: Object.fromEntries(renderedRows),
        },
      },
      null,
      2,
    )}\n`,
  );
}

main().catch((error) => {
  process.stderr.write(String(error?.stack || error));
  process.exitCode = 1;
});
