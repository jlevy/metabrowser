// The shell's changed-files tree (static/changed-files-tree.js) as its bundle installs it, for
// a session or check that mounts a tree of changed files: the Pulls tab's under a pull
// request's row, or a diff's Diff summary. Each call runs the file as it ships, verbatim and
// under its own name, so V8's coverage credits the production file (devtools/check_parity.py),
// in this realm, so the rows it builds are this realm's arrays and objects, which a strict deep
// comparison in the caller needs. The file installs the model on `window`, which here is an
// object of the call's own for the moment it runs, whatever `window` a caller has set up for
// its own checks.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = path.resolve(__dirname, "../../src/metabrowser/static/changed-files-tree.js");

/** @returns {MetabrowserChangedFilesTree} */
function changedFilesTree() {
  const before = Object.getOwnPropertyDescriptor(globalThis, "window");
  const page = {};
  globalThis.window = page;
  try {
    vm.runInThisContext(fs.readFileSync(source, "utf8"), { filename: source });
  } finally {
    if (before === undefined) {
      delete globalThis.window;
    } else {
      Object.defineProperty(globalThis, "window", before);
    }
  }
  return page.MetabrowserChangedFilesTree;
}

module.exports = { changedFilesTree, source };
