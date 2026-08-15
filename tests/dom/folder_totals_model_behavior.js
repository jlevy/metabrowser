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
      allBytes: 800,
      unignoredFiles: 8,
      unignoredBytes: 500,
    },
    groups: [
      {
        id: "code",
        families: [
          {
            id: "javascript",
            allFiles: 7,
            allBytes: 400,
            unignoredFiles: 4,
            unignoredBytes: 300,
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
      { id: "markdown", label: "Markdown", groupId: "documentation" },
    ],
  };
  const composition = model.buildFolderTotalsComposition(rollup, fileTypes, "size");
  const filesSegments = composition.files.segments;
  const ignoredSegments = composition.ignored.segments;
  if (
    composition.metric !== "size" ||
    composition.files.value !== 500 ||
    composition.ignored.value !== 300 ||
    filesSegments.map((segment) => segment.label).join(",") !==
      "JavaScript,Markdown,Other types,No extension" ||
    Math.abs(filesSegments.reduce((sum, segment) => sum + segment.share, 0) - 100) >
      SHARE_TOLERANCE ||
    Math.abs(ignoredSegments.reduce((sum, segment) => sum + segment.share, 0) - 100) >
      SHARE_TOLERANCE ||
    filesSegments[0].paletteKey !== "family:javascript" ||
    ignoredSegments.some((segment) => segment.label === "No extension")
  ) {
    throw new Error(`folder total composition is incorrect: ${JSON.stringify(composition)}`);
  }

  const fileComposition = model.buildFolderTotalsComposition(rollup, fileTypes, "files");
  if (
    fileComposition.files.value !== 8 ||
    fileComposition.ignored.value !== 5 ||
    fileComposition.files.segments.reduce((sum, segment) => sum + segment.value, 0) !== 8 ||
    fileComposition.ignored.segments.reduce((sum, segment) => sum + segment.value, 0) !== 5
  ) {
    throw new Error(
      `file-count composition does not conserve totals: ${JSON.stringify(fileComposition)}`,
    );
  }
  console.log(JSON.stringify({ ok: true }));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
