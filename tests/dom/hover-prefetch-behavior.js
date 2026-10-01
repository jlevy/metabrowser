// Which tree rows app.js prefetches on hover, decided by the production function.
//
// Usage: node hover-prefetch-behavior.js '<json [{path, ext?, logical_ext?, size?}]>'
//
// Each argument row is a file node as `/api/tree` sent it. renderTreeNodes writes
// `path`, `ext`, `logical_ext` and `size` onto the row as `data-path`, `data-ext`,
// `data-logical-ext` and `data-tip-size`, and those attributes are all that
// shouldPrefetchFile reads, so the row is given here as its dataset.
//
// shouldPrefetchFile, getExt and the size cap are lifted out of app.js and run, so
// this is the shipped decision and not a reading of its text. Prints a JSON object
// from each row's path to whether a hover would prefetch it.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const appSource = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/app.js"), "utf-8");

function lift(pattern, name) {
  const match = appSource.match(pattern);
  if (!match) {
    throw new Error(`${name} not found in app.js`);
  }
  return match[0];
}

const sandbox = { fileCache: new Map(), activeFiles: new Set() };
vm.createContext(sandbox);
vm.runInContext(
  [
    lift(/const FILE_PREFETCH_MAX_BYTES = [^;]+;/, "FILE_PREFETCH_MAX_BYTES"),
    lift(/function getExt\(name\) \{[\s\S]*?\n\}/, "getExt"),
    lift(/function shouldPrefetchFile\(item\) \{[\s\S]*?\n\}/, "shouldPrefetchFile"),
    "result = { shouldPrefetchFile, cap: FILE_PREFETCH_MAX_BYTES };",
  ].join("\n"),
  sandbox,
  { filename: "hover-prefetch.js" },
);

const rows = JSON.parse(process.argv[2]);
const decisions = {};
for (const row of rows) {
  const dataset = { path: row.path };
  if (row.ext) {
    dataset.ext = row.ext;
  }
  if (row.logical_ext) {
    dataset.logicalExt = row.logical_ext;
  }
  if (typeof row.size === "number") {
    dataset.tipSize = String(row.size);
  }
  decisions[row.path] = sandbox.result.shouldPrefetchFile({ dataset });
}
process.stdout.write(`${JSON.stringify({ cap: sandbox.result.cap, decisions }, null, 2)}\n`);
