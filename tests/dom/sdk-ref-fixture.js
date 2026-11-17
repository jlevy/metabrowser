// Run shared production ref rendering against the caller's deterministic DOM, with the SDK's
// number format, title nodes, actor identity, and painters of count summaries and brief
// change lines, and the shell's changed-files tree a view that lists changed files draws
// with (the bundle `loadChangedFilesTree` loads in a page, already in hand here).
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
    actorIdentity: sandbox.metabrowser.actorIdentity,
    actorIdentityHtml: sandbox.metabrowser.actorIdentityHtml,
    formatInteger: sandbox.metabrowser.formatInteger,
    titleNodes: sandbox.metabrowser.titleNodes,
    countPartsNodes: sandbox.metabrowser.countPartsNodes,
    changeLine: sandbox.metabrowser.changeLine,
    changeLineNodes: sandbox.metabrowser.changeLineNodes,
    loadChangedFilesTree: () => Promise.resolve(tree),
  };
}
module.exports = { refHelpers };
