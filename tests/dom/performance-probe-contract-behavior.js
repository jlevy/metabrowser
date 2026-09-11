// Behavioral contract for the performance probe's fail-closed label check.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const probePath = path.join(repoRoot, "explorations/performance-loop/probe.js");
const source = fs.readFileSync(probePath, "utf-8");
const start = source.indexOf("function missingRequiredPerformanceLabels");
const end = source.indexOf("\n\n(async () =>", start);
if (start < 0 || end < 0) {
  throw new Error("probe label contract helper is missing");
}

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(source.slice(start, end), sandbox, { filename: probePath });

const required = [
  "apiCatalog:parse",
  "knownFileCatalog:applyBulkSnapshot",
  "knownFileCatalog:applyCatalogChange",
];
const complete = required.map((label) => ({ label }));
const missingParse = [
  { label: "knownFileCatalog:applyBulkSnapshot" },
  { label: "knownFileCatalog:applyCatalogChange" },
  { label: "fileStoreApplySnapshot" },
];
const missingBulk = [
  { label: "apiCatalog:parse" },
  { label: "knownFileCatalog:applyCatalogChange" },
  { label: "fileStoreApplySnapshot" },
];

if (sandbox.missingRequiredPerformanceLabels(required, complete).length !== 0) {
  throw new Error("complete required attribution was rejected");
}
if (
  sandbox.missingRequiredPerformanceLabels(required, missingParse).join() !== "apiCatalog:parse"
) {
  throw new Error("missing parse attribution was hidden by another delivery label");
}
if (
  sandbox.missingRequiredPerformanceLabels(required, missingBulk).join() !==
  "knownFileCatalog:applyBulkSnapshot"
) {
  throw new Error("missing bulk attribution was hidden by another delivery label");
}
if (
  sandbox
    .missingRequiredPerformanceLabels(required, [
      { label: "apiCatalog:parse" },
      { label: "knownFileCatalog:applyBulkSnapshot" },
      { label: "fileStoreApplySnapshot" },
    ])
    .join() !== "knownFileCatalog:applyCatalogChange"
) {
  throw new Error("missing incremental catalog attribution was hidden by another delivery label");
}

console.log("performance probe contract behavior: OK");
