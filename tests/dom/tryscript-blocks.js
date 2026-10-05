// What the installed tryscript makes of each file named on the command line: the
// command, expected exit status, and skip and only flags of every block it would run.
// tests/test_tryscript_blocks.py compares devtools/tryscript_blocks.py with this.

const fs = require("node:fs");
const { parseTestFile, TestParseError } = require("tryscript");

const parsed = {};
for (const file of process.argv.slice(2)) {
  try {
    parsed[file] = parseTestFile(fs.readFileSync(file, "utf8"), file).blocks.map((block) => ({
      command: block.command,
      status: block.expectedExitCode,
      skip: block.skip,
      only: block.only,
    }));
  } catch (error) {
    if (!(error instanceof TestParseError)) {
      throw error;
    }
    parsed[file] = { error: true };
  }
}
process.stdout.write(`${JSON.stringify(parsed)}\n`);
