// Run shared production ref rendering against the caller's deterministic DOM, with the SDK's
// number format and title nodes, and the shell's changed-files tree a view that lists changed
// files draws with (the bundle `loadChangedFilesTree` loads in a page, already in hand here).
const { createSdkSandbox } = require("./sdk-sandbox.js");
const { changedFilesTree } = require("./changed-files-tree-fixture.js");
function refHelpers(document) {
  const sandbox = createSdkSandbox();
  sandbox.document = document;
  sandbox.MetabrowserIcons = { copy: '<svg data-icon="copy"></svg>' };
  const tree = changedFilesTree();
  return {
    decorateExternalLink: sandbox.metabrowser.decorateExternalLink,
    refChip: sandbox.metabrowser.refChip,
    refChipHtml: sandbox.metabrowser.refChipHtml,
    mergeRefs: sandbox.metabrowser.mergeRefs,
    mountRefCopies: sandbox.metabrowser.mountRefCopies,
    formatInteger: sandbox.metabrowser.formatInteger,
    titleNodes: sandbox.metabrowser.titleNodes,
    loadChangedFilesTree: () => Promise.resolve(tree),
  };
}
module.exports = { refHelpers };
