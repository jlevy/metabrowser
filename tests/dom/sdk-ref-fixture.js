// Run shared production ref rendering against the caller's deterministic DOM, with the SDK's
// number format, title nodes, short commit IDs, actor identity, its one age builder, and
// painters of count summaries, brief change lines, and size lines, and the shell's changed-files tree a view that lists
// changed files draws with (the bundle `loadChangedFilesTree` loads in a page, already in
// hand here).
const { createSdkSandbox } = require("./sdk-sandbox.js");
const { changedFilesTree } = require("./changed-files-tree-fixture.js");
// The SDK's one age builder (`ageLabel`, `ageLabelHtml`, `retellAge`), drawing into the
// caller's DOM. It tells every age as of `now`, epoch milliseconds or a function that gives
// them, or else as of this process's `Date.now()` when it is asked, so a session that holds
// its own clock still holds its ages still too.
function ageHelpers(document, now) {
  const outer = Date;
  const sandbox = createSdkSandbox({
    Date: class extends outer {
      static now() {
        return now === undefined ? outer.now() : typeof now === "function" ? now() : now;
      }
    },
  });
  sandbox.document = document;
  const { ageLabel, ageLabelHtml, retellAge } = sandbox.metabrowser;
  return { ageLabel, ageLabelHtml, retellAge };
}
// The SDK's age builder over an age primitive a session plays: what its `formatAge` answers,
// drawn the way the builder draws the primitive's answer, the label in its class after the
// call site's. A session that chooses its ages' labels, so that two read the same or one
// reads "now" whenever it runs, sees the ages a view draws and the ones it compares in
// words agree, as they do in a page. The builder itself is checked against the primitive in
// browser-primitives-behavior.js.
function agesFrom(document, formatAge) {
  const played = new WeakMap();
  const retellAge = (element, epochSeconds, options = {}) => {
    const { label, className } = formatAge(Number(epochSeconds) || 0, options);
    if (element.textContent !== label) {
      element.textContent = label;
    }
    const had = element.getAttribute("class") ?? "";
    const kept = had.split(/\s+/).filter((name) => name !== "" && name !== played.get(element));
    const wanted = (label === "" || !className ? kept : [...kept, className]).join(" ");
    if (had !== wanted) {
      element.setAttribute("class", wanted);
    }
    played.set(element, className);
    return label;
  };
  const ageLabel = (epochSeconds, options = {}) => {
    const element = document.createElement("span");
    if (options.className) {
      element.setAttribute("class", options.className);
    }
    if (options.tip) {
      element.setAttribute("data-tip-text", options.tip);
    }
    retellAge(element, epochSeconds, options);
    return element;
  };
  const ageLabelHtml = (epochSeconds, options = {}) => {
    const { label, className } = formatAge(Number(epochSeconds) || 0, options);
    if (label === "") {
      return "";
    }
    const classes = [options.className, className].filter(Boolean).join(" ");
    const tip = options.tip ? ` data-tip-text="${options.tip}"` : "";
    return `<span class="${classes}"${tip}>${label}</span>`;
  };
  return { formatAge, ageLabel, ageLabelHtml, retellAge };
}
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
    mountRefMenus: sandbox.metabrowser.mountRefMenus,
    actorIdentity: sandbox.metabrowser.actorIdentity,
    actorIdentityHtml: sandbox.metabrowser.actorIdentityHtml,
    formatInteger: sandbox.metabrowser.formatInteger,
    titleNodes: sandbox.metabrowser.titleNodes,
    shortCommit: sandbox.metabrowser.shortCommit,
    countPartsNodes: sandbox.metabrowser.countPartsNodes,
    changeLine: sandbox.metabrowser.changeLine,
    changeLineNodes: sandbox.metabrowser.changeLineNodes,
    changeSizeLine: sandbox.metabrowser.changeSizeLine,
    changeSizeLineNodes: sandbox.metabrowser.changeSizeLineNodes,
    changeSizeLineHtml: sandbox.metabrowser.changeSizeLineHtml,
    formatSize: sandbox.metabrowser.formatSize,
    ...ageHelpers(document),
    menus: sandbox.metabrowser.menus,
    loadChangedFilesTree: () => Promise.resolve(tree),
  };
}
module.exports = { ageHelpers, agesFrom, refHelpers };
