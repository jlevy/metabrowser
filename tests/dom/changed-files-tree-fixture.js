// The shell's changed-files tree (static/changed-files-tree.js) as its bundle installs it, for
// a session or check that mounts a tree of changed files: the Pulls tab's under a pull
// request's row, or a diff's Diff summary. Each call runs the file as it ships, verbatim and
// under its own name, so V8's coverage credits the production file (devtools/check_parity.py),
// in this realm, so the rows it builds are this realm's arrays and objects, which a strict deep
// comparison in the caller needs. The file installs the model on `window`, which here is an
// object of the call's own for the moment it runs, whatever `window` a caller has set up for
// its own checks. The shell's formatters (static/formatters.js), which every page loads before
// an on-demand bundle and whose words a change set's summary says, run first, on the same
// object, the same way.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = path.resolve(__dirname, "../../src/metabrowser/static/changed-files-tree.js");
const formatters = path.resolve(__dirname, "../../src/metabrowser/static/formatters.js");

/**
 * The shell's formatters alone, as a page installs them, for a check that paints a count
 * summary through their one painter, as the SDK's `countPartsNodes` does.
 *
 * @returns {MetabrowserFormatterRuntime}
 */
function shellFormatters() {
  const before = Object.getOwnPropertyDescriptor(globalThis, "window");
  const page = {};
  globalThis.window = page;
  try {
    vm.runInThisContext(fs.readFileSync(formatters, "utf8"), { filename: formatters });
  } finally {
    if (before === undefined) {
      delete globalThis.window;
    } else {
      Object.defineProperty(globalThis, "window", before);
    }
  }
  return page.MetabrowserFormatters;
}

/**
 * The SDK's painters as a page has them, for a view handed an SDK of the caller's own: the
 * shell's one painter of a count summary, `countPartsNodes`, and its brief change line,
 * `changeLine` in the shell's number format and `changeLineNodes`, each drawing into whatever
 * document the caller has set up when it is called, and the one length a commit's ID is
 * shown at, `shortCommit`.
 *
 * @returns {Pick<MetabrowserPublicSdk, "countPartsNodes" | "changeLine" | "changeLineNodes" | "changeSizeLine" | "changeSizeLineNodes" | "formatSize" | "shortCommit">}
 */
function shellPainters() {
  const formatters = shellFormatters();
  return {
    shortCommit: formatters.shortCommit,
    countPartsNodes: (parts) => formatters.countPartsNodes(globalThis.document, parts),
    changeLine: (change) => formatters.changeLine(change, formatters.formatInteger),
    changeLineNodes: (line, options) =>
      formatters.changeLineNodes(globalThis.document, line, options),
    // The size line is a view helper (plugin-sdk-views.js), taken from the SDK as a page
    // has it, drawing into the caller's document.
    ...sizeLinePainters(),
    formatSize: (bytes) => formatters.formatBytes(bytes),
  };
}

/**
 * The SDK's size-line helpers, from the real view helpers, drawing into whatever document
 * the caller has set up when each is called.
 * @returns {Pick<MetabrowserPublicSdk, "changeSizeLine" | "changeSizeLineNodes">}
 */
function sizeLinePainters() {
  const sandbox = require("./sdk-sandbox.js").createSdkSandbox();
  return {
    changeSizeLine: (change) => sandbox.metabrowser.changeSizeLine(change),
    changeSizeLineNodes: (line) => {
      sandbox.document = globalThis.document;
      return sandbox.metabrowser.changeSizeLineNodes(line);
    },
  };
}

/** @returns {MetabrowserChangedFilesTree} */
function changedFilesTree() {
  const before = Object.getOwnPropertyDescriptor(globalThis, "window");
  const page = {};
  globalThis.window = page;
  try {
    vm.runInThisContext(fs.readFileSync(formatters, "utf8"), { filename: formatters });
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

module.exports = { changedFilesTree, shellFormatters, shellPainters, source };
