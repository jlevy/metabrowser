const fs = require("node:fs");
const path = require("node:path");

const SHARE_TOLERANCE = 1e-9;

async function main() {
  const repoRoot = path.resolve(process.argv[2]);
  const source = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/builtin_plugins/folder/folder_totals.js"),
    "utf8",
  );
  const model = await import(
    `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
  );
  const formatters = {
    formatFileCount: (value) => `${value} files`,
    formatSize: (value) => `${value} B`,
  };
  const totals = model.normalizeFolderTotals({
    total_files: 100,
    total_size: 500,
    unignored_files: 80,
    unignored_size: 300,
    state: "complete",
  });
  const complete = model.buildFolderTotalsModel(totals, formatters);
  if (
    complete.state !== "complete" ||
    complete.files.files !== 80 ||
    complete.files.bytes !== 300 ||
    complete.ignored.files !== 20 ||
    complete.ignored.bytes !== 200 ||
    "filePercent" in complete.files ||
    "bytePercent" in complete.ignored ||
    complete.files.files + complete.ignored.files !== 100 ||
    complete.files.bytes + complete.ignored.bytes !== 500
  ) {
    throw new Error(`folder totals are incorrect: ${JSON.stringify(complete)}`);
  }
  const filesVisible = model.selectFolderTotalsMetric(complete.files, "files");
  const bytesVisible = model.selectFolderTotalsMetric(complete.files, "size");
  const bytesIgnored = model.selectFolderTotalsMetric(complete.ignored, "size");
  if (
    filesVisible.value !== 80 ||
    filesVisible.text !== "80 files" ||
    bytesVisible.value !== 300 ||
    bytesVisible.text !== "300 B" ||
    bytesIgnored.value !== 200 ||
    bytesIgnored.text !== "200 B" ||
    "percent" in filesVisible ||
    "share" in bytesIgnored
  ) {
    throw new Error(
      `folder totals did not follow the selected metric: ${JSON.stringify({ filesVisible, bytesVisible, bytesIgnored })}`,
    );
  }
  const pending = model.buildFolderTotalsModel(
    model.normalizeFolderTotals({ total_files: null, total_size: null, state: "pending" }),
    formatters,
  );
  if (pending.state !== "pending" || "files" in pending) {
    throw new Error("pending totals must not fabricate zero-valued rows");
  }
  // The directory totals store zero-fills the aggregates the walker has not
  // finalized and marks the entry pending. Re-deriving completeness from the
  // numbers alone would read those placeholders as a real "0 files" and show
  // it as settled, so an explicit pending state has to win over them.
  const zeroFilledPending = model.buildFolderTotalsModel(
    model.normalizeFolderTotals({
      path: "",
      revision: 1,
      state: "pending",
      totalFiles: 0,
      totalBytes: 0,
      unignoredFiles: 0,
      unignoredBytes: 0,
    }),
    formatters,
  );
  if (zeroFilledPending.state !== "pending") {
    throw new Error("a zero-filled pending entry must not read as complete");
  }
  const allIgnored = model.buildFolderTotalsModel(
    model.normalizeFolderTotals({
      total_files: 3,
      total_size: 9,
      unignored_files: 0,
      unignored_size: 0,
    }),
    formatters,
  );
  if (allIgnored.state !== "complete" || allIgnored.files.files !== 0) {
    throw new Error(`all-ignored totals are incorrect: ${JSON.stringify(allIgnored)}`);
  }
  const empty = model.buildFolderTotalsModel(
    model.normalizeFolderTotals({
      total_files: 0,
      total_size: 0,
      unignored_files: 0,
      unignored_size: 0,
    }),
    formatters,
  );
  if (empty.state !== "complete" || empty.files.files !== 0 || empty.ignored.bytes !== 0) {
    throw new Error(`empty totals are incorrect: ${JSON.stringify(empty)}`);
  }

  const rollup = {
    registry: { revision: 7, fingerprint: "registry-test" },
    totals: {
      allFiles: 13,
      allBytes: 900,
      unignoredFiles: 7,
      unignoredBytes: 350,
    },
    groups: [
      {
        id: "code",
        families: [
          {
            id: "javascript",
            allFiles: 5,
            allBytes: 400,
            unignoredFiles: 1,
            unignoredBytes: 50,
          },
          {
            id: "python",
            allFiles: 2,
            allBytes: 100,
            unignoredFiles: 2,
            unignoredBytes: 100,
          },
        ],
      },
      {
        id: "documentation",
        families: [
          {
            id: "markdown",
            allFiles: 3,
            allBytes: 150,
            unignoredFiles: 2,
            unignoredBytes: 50,
          },
        ],
      },
    ],
    specialTypes: {
      noExtension: {
        allFiles: 1,
        allBytes: 50,
        unignoredFiles: 1,
        unignoredBytes: 50,
      },
      remainingTypes: {
        allFiles: 2,
        allBytes: 200,
        unignoredFiles: 1,
        unignoredBytes: 100,
      },
    },
  };
  const fileTypes = {
    revision: 7,
    fingerprint: "registry-test",
    groups: [
      { id: "code", label: "Code" },
      { id: "documentation", label: "Documentation" },
      { id: "other", label: "Other" },
    ],
    families: [
      { id: "javascript", label: "JavaScript", groupId: "code" },
      { id: "python", label: "Python", groupId: "code" },
      { id: "markdown", label: "Markdown", groupId: "documentation" },
    ],
  };
  const composition = model.buildFolderTotalsComposition(rollup, fileTypes, "size", true);
  const filesSegments = composition.files.segments;
  const ignoredSegments = composition.ignored.segments;
  if (
    composition.metric !== "size" ||
    composition.files.value !== 350 ||
    composition.ignored.value !== 550 ||
    filesSegments.map((segment) => segment.label).join(",") !==
      "JavaScript,Python,Markdown,Other types,No extension" ||
    Math.abs(filesSegments.reduce((sum, segment) => sum + segment.share, 0) - 100) >
      SHARE_TOLERANCE ||
    Math.abs(ignoredSegments.reduce((sum, segment) => sum + segment.share, 0) - 100) >
      SHARE_TOLERANCE ||
    filesSegments[0].paletteKey !== "family:javascript" ||
    filesSegments[0].files !== 1 ||
    filesSegments[0].bytes !== 50 ||
    ignoredSegments.some((segment) => segment.label === "No extension")
  ) {
    throw new Error(`folder total composition is incorrect: ${JSON.stringify(composition)}`);
  }

  const unignoredOrder = model.buildFolderTotalsComposition(rollup, fileTypes, "size", false);
  if (
    unignoredOrder.files.segments
      .slice(0, 2)
      .map((segment) => segment.label)
      .join(",") !== "Python,JavaScript"
  ) {
    throw new Error(
      `composition order did not match the unignored breakdown: ${JSON.stringify(unignoredOrder)}`,
    );
  }

  const fileComposition = model.buildFolderTotalsComposition(rollup, fileTypes, "files", true);
  if (
    fileComposition.files.value !== 7 ||
    fileComposition.ignored.value !== 6 ||
    fileComposition.files.segments.reduce((sum, segment) => sum + segment.value, 0) !== 7 ||
    fileComposition.ignored.segments.reduce((sum, segment) => sum + segment.value, 0) !== 6
  ) {
    throw new Error(
      `file-count composition does not conserve totals: ${JSON.stringify(fileComposition)}`,
    );
  }
  // chooseFolderTotals: which of the two sources the panel renders.
  const walkerTotals = model.normalizeFolderTotals({
    totalFiles: 400019,
    totalBytes: 1747488822,
    unignoredFiles: 400019,
    unignoredBytes: 1747488822,
    state: "complete",
  });
  const rollupTotals = model.normalizeFolderTotals({
    totalFiles: 400000,
    totalBytes: 1747487872,
    unignoredFiles: 400000,
    unignoredBytes: 1747487872,
    state: "complete",
  });

  // Still scanning: both are lower bounds that only grow, so the larger one
  // wins and a pending source never replaces real numbers with a spinner.
  if (model.chooseFolderTotals(walkerTotals, rollupTotals, false) !== walkerTotals) {
    throw new Error("while scanning, the source that has seen more files should win");
  }
  if (model.chooseFolderTotals(rollupTotals, walkerTotals, false) !== walkerTotals) {
    throw new Error("while scanning, the larger source should win from either side");
  }

  // Settled: the rollup is authoritative. Without this a store that drifted
  // high during a churn burst stays on screen forever, because each source
  // holds its last value and the larger one wins every later comparison.
  if (model.chooseFolderTotals(walkerTotals, rollupTotals, true) !== rollupTotals) {
    throw new Error("a settled rollup must win even when the other source reports more");
  }

  // One source only: use it, settled or not.
  if (model.chooseFolderTotals(null, rollupTotals, false) !== rollupTotals) {
    throw new Error("a lone rollup should be used");
  }
  if (model.chooseFolderTotals(walkerTotals, null, true) !== walkerTotals) {
    throw new Error("a lone walker aggregate should be used");
  }
  if (model.chooseFolderTotals(null, null, true) !== null) {
    throw new Error("with no source at all the choice is nothing");
  }

  console.log(JSON.stringify({ ok: true }));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
