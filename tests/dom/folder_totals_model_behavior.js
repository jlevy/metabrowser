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
    complete.total.files !== 100 ||
    complete.ignored.files !== 20 ||
    complete.ignored.bytes !== 200 ||
    complete.ignored.filePercent !== "20%" ||
    complete.ignored.bytePercent !== "40%"
  ) {
    throw new Error(`folder totals are incorrect: ${JSON.stringify(complete)}`);
  }
  const pending = model.buildFolderTotalsModel(
    model.normalizeFolderTotals({ total_files: null, total_size: null, state: "pending" }),
    formatters,
  );
  if (pending.state !== "pending" || "total" in pending) {
    throw new Error("pending totals must not fabricate zero-valued rows");
  }
  console.log(JSON.stringify({ ok: true }));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
