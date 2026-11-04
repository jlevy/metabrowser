// Run shared production ref rendering against the caller's deterministic DOM.
const { createSdkSandbox } = require("./sdk-sandbox.js");
function refHelpers(document) {
  const sandbox = createSdkSandbox();
  sandbox.document = document;
  sandbox.MetabrowserIcons = { copy: '<svg data-icon="copy"></svg>' };
  return {
    refChip: sandbox.metabrowser.refChip,
    refChipHtml: sandbox.metabrowser.refChipHtml,
    mountRefCopies: sandbox.metabrowser.mountRefCopies,
  };
}
module.exports = { refHelpers };
