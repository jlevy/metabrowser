// The shell's changed-files tree (static/changed-files-tree.js) as its bundle installs it, for
// a session or check that mounts a tree of changed files: the Pulls tab's under a pull
// request's row, or a diff's Diff summary. Each call runs the file as it ships, in this realm,
// so the rows it builds are this realm's arrays and objects, which a strict deep comparison
// in the caller needs. The file installs the model on the `window` it is given, which here is
// an object of the call's own, whatever `window` a caller has set up for its own checks.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = path.resolve(__dirname, "../../src/metabrowser/static/changed-files-tree.js");

/** @returns {MetabrowserChangedFilesTree} */
function changedFilesTree() {
  const install = vm.runInThisContext(
    `(function (window) {\n${fs.readFileSync(source, "utf8")}\n})`,
    { filename: source, lineOffset: -1 },
  );
  const page = {};
  install(page);
  return page.MetabrowserChangedFilesTree;
}

module.exports = { changedFilesTree, source };
