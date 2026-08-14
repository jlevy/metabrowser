const fs = require("node:fs");
const path = require("node:path");

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
    complete.files.filePercent !== "80%" ||
    complete.files.bytePercent !== "60%" ||
    complete.ignored.files !== 20 ||
    complete.ignored.bytes !== 200 ||
    complete.ignored.filePercent !== "20%" ||
    complete.ignored.bytePercent !== "40%" ||
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
    filesVisible.percent !== "80%" ||
    bytesVisible.value !== 300 ||
    bytesVisible.text !== "300 B" ||
    bytesVisible.percent !== "60%" ||
    bytesIgnored.value !== 200 ||
    bytesIgnored.text !== "200 B" ||
    bytesIgnored.percent !== "40%"
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
  if (
    allIgnored.state !== "complete" ||
    allIgnored.files.filePercent !== "0%" ||
    allIgnored.ignored.filePercent !== "100%" ||
    allIgnored.files.bytePercent !== "0%" ||
    allIgnored.ignored.bytePercent !== "100%"
  ) {
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
  if (
    empty.state !== "complete" ||
    empty.files.filePercent !== "0%" ||
    empty.ignored.filePercent !== "0%" ||
    empty.files.bytePercent !== "0%" ||
    empty.ignored.bytePercent !== "0%"
  ) {
    throw new Error(`empty totals are incorrect: ${JSON.stringify(empty)}`);
  }
  console.log(JSON.stringify({ ok: true }));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
