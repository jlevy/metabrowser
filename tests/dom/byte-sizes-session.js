// Browserless session: how a byte count reads, at every unit boundary.
//
// One formatter writes every size a reader sees: `formatBytes` in formatters.js. The
// shell's `formatSize` in app.js, which the Files tree rows, the Files totals line, and
// the binary preview use, and the plugin SDK's `mb.formatSize`, which plugins use, both
// hand their count to it. Before they did, the shell had a copy of its own that stopped
// at megabytes, so 10.1 billion bytes read "9632.1 MB" in the shell.
//
// This runs the real formatters.js and plugin SDK, with the shell's `formatSize`
// extracted verbatim from app.js, and records how each boundary count reads: the last
// count of one unit and the first of the next. It fails if the shell and the SDK ever
// write a count differently.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { createSdkSandbox } = require("./sdk-sandbox.js");

const appSource = fs.readFileSync(
  path.resolve(__dirname, "../../src/metabrowser/static/app.js"),
  "utf8",
);

/** A top-level function of app.js, verbatim, up to its closing brace. */
function appFunction(name) {
  const start = appSource.indexOf(`\nfunction ${name}(`);
  const end = appSource.indexOf("\n}\n", start);
  if (start < 0 || end < start) {
    throw new Error(`app.js ${name} is not extractable`);
  }
  return appSource.slice(start + 1, end + 2);
}

const sandbox = createSdkSandbox();
vm.runInContext(appFunction("formatSize"), sandbox, { filename: "app-format-size.js" });
const shell = vm.runInContext("formatSize", sandbox);
const sdk = sandbox.metabrowser.formatSize;

const KB = 1024;
const MB = 1024 ** 2;
const GB = 1024 ** 3;
const TB = 1024 ** 4;

/** @type {Array<[string, number]>} */
const COUNTS = [
  ["nothing", 0],
  ["one byte", 1],
  ["the last count in bytes", KB - 1],
  ["the first in kilobytes", KB],
  ["the last in kilobytes", MB - 1],
  ["the first in megabytes", MB],
  ["the last in megabytes", GB - 1],
  ["the first in gigabytes", GB],
  ["10.1 billion bytes", 10_100_000_000],
  ["the last in gigabytes", TB - 1],
  ["the first in terabytes", TB],
];

const reads = {};
for (const [label, bytes] of COUNTS) {
  const written = shell(bytes);
  assert.equal(sdk(bytes), written, `the shell and the SDK write ${bytes} bytes alike`);
  reads[label] = { bytes, reads: written };
}

// The boundary this session exists for: a gigabyte is the first count past megabytes.
assert.equal(shell(GB - 1), "1024.0 MB");
assert.equal(shell(GB), "1.0 GB");

console.log(JSON.stringify(reads, null, 2));
