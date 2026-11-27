// Browserless session: the shell's document-wide click and tooltip delegates act only
// on controls page code created.
//
// A trusted folder's Markdown keeps class, id, and data-* through KPress, so a
// document can spell the shell's control markup: an address crumb's
// `data-nav-dir` / `data-nav-file`, a `data-tip-text` label. The action delegates act
// only on an element carrying the SDK's per-page owner mark; the tooltip ignores a
// rendered document's markup, but for a control page code placed in it and marked, as
// the document's print button (builtin_plugins/markdown/print-indicator.js) is.
//
// The production SDK and the view header's builders (view-header.js) load whole. The
// shell's helpers and delegates are lifted verbatim from app.js, which cannot load
// without a document, as source-kind-session.js does, and the builders are made over
// them as loadViewComposition makes them; the navigation collaborators are stubs that
// record calls. Each click target is an element built from the attributes the builder
// wrote, so the owner mark under test is the one the production code emitted, not one
// this file assigned.
//
// Prints `{calls, failures}`; exits 1 on any failure.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf8");

const PRODUCTION_MODULES = [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "contribution-registry.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "plugin-sdk.js",
  "view-header.js",
];

// Helpers, gates, and delegates lifted verbatim from app.js.
const LIFTED = [
  "esc",
  "queryHtml",
  "servedRoot",
  "mirrorHeading",
  "eventTargetElement",
  "ownedControlAttr",
  "isOwnedControl",
  "isPageElement",
  "pathBaseName",
  "servedRootName",
  "tipTextAnchor",
  "onHeaderNavigationClick",
];

// The view header's builders over the lifted helpers. The headers built here show no
// icon, size, count, age, or badge, so those helpers say so if one is asked for.
const VIEW_HEADER = `
function notDrawnHere() {
  throw new Error("this session's headers draw no icon, size, count, age, or badge");
}
var viewHeader = MetabrowserViewHeader.create({
  esc,
  servedRoot,
  servedRootName,
  ownedControlAttr,
  mirrorHeading,
  getFileIcon: notDrawnHere,
  getLogicalName: notDrawnHere,
  sizeHtml: notDrawnHere,
  countHtml: notDrawnHere,
  formatAge: notDrawnHere,
  activeFiles: new Map(),
});
`;

const COLLABORATORS = `
function navigateToFolder(path) {
  __calls.push("folder:" + path);
}
function navigateToPath(path) {
  __calls.push("file:" + path);
  return Promise.resolve();
}
`;

const failures = [];

function check(name, condition) {
  if (!condition) {
    failures.push(name);
  }
}

function lift(name) {
  const match = appSource.match(new RegExp(`\\nfunction ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n\\}`));
  if (!match) {
    throw new Error(`${name} not found in app.js`);
  }
  return match[0];
}

class Element {}
class HTMLElement extends Element {}

/** A fake element whose attributes are exactly those given, under an optional parent. */
class FakeElement extends HTMLElement {
  constructor(attributes, parent = null) {
    super();
    this.attributes = new Map(Object.entries(attributes));
    this.parentElement = parent;
    this.dataset = {};
    for (const [name, value] of this.attributes) {
      if (name.startsWith("data-")) {
        const key = name.slice(5).replace(/-([a-z])/g, (_m, c) => c.toUpperCase());
        this.dataset[key] = value;
      }
    }
  }
  get classList() {
    const names = (this.getAttribute("class") || "").split(/\s+/);
    return { contains: (name) => names.includes(name) };
  }
  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }
  hasAttribute(name) {
    return this.attributes.has(name);
  }
  // For the SDK's `ownDelegate`, which marks an element page code built.
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  matches(selector) {
    const attribute = /^\[([\w-]+)\]$/.exec(selector);
    if (attribute) {
      return this.hasAttribute(attribute[1]);
    }
    if (selector.startsWith("#")) {
      return this.getAttribute("id") === selector.slice(1);
    }
    if (selector.startsWith(".")) {
      return (this.getAttribute("class") || "").split(/\s+/).includes(selector.slice(1));
    }
    throw new Error(`unsupported selector ${selector}`);
  }
  closest(selector) {
    for (let node = this; node; node = node.parentElement) {
      if (node.matches(selector)) {
        return node;
      }
    }
    return null;
  }
}

function unescapeHtml(value) {
  return value
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&amp;", "&");
}

/** Every `<button …>` the markup opens, as elements with exactly its attributes. */
function buttons(markup, parent = null) {
  return [...markup.matchAll(/<button\b([^>]*)>/g)].map((match) => {
    const attributes = {};
    for (const attr of match[1].matchAll(/([\w-]+)(?:="([^"]*)")?/g)) {
      attributes[attr[1]] = attr[2] === undefined ? "" : unescapeHtml(attr[2]);
    }
    return new FakeElement(attributes, parent);
  });
}

// The served root the page's navigation heading carries (`data-served-root` on
// `.header-path`), which the eyebrow writes as the root's crumb.
const SERVED_ROOT = "~/wrk/project";
const headerPath = { dataset: { servedRoot: SERVED_ROOT } };

const calls = [];
const sandbox = {
  console,
  setTimeout,
  clearTimeout,
  Promise,
  Map,
  Set,
  Element,
  HTMLElement,
  __calls: calls,
  document: {
    addEventListener: () => {},
    querySelector: (selector) => (selector === ".header-path" ? headerPath : null),
    querySelectorAll: () => [],
    createElement: () => ({}),
    documentElement: {},
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
for (const name of PRODUCTION_MODULES) {
  const file = path.join(staticDir, name);
  vm.runInContext(fs.readFileSync(file, "utf8"), sandbox, { filename: name });
}
vm.runInContext(COLLABORATORS + LIFTED.map(lift).join("\n") + VIEW_HEADER, sandbox, {
  filename: "app.js (lifted)",
});

function click(element) {
  sandbox.onHeaderNavigationClick({ target: element });
}

// The page's own controls, as the shell renders them: a file's eyebrow, its Up control and
// its folder's address, and a folder's whole view header.
const fileHeader = buttons(sandbox.viewHeader.viewHeaderEyebrowHtml("docs/a%25b.md"));
const folderHeader = buttons(sandbox.viewHeader.renderFolderHeader({ path: "docs/sub" }));
const owner = fileHeader[0].getAttribute("data-mb-owner");
check(
  "each control carries its tip text: Up its folder, the served root's crumb its address, and every other crumb its own name, not its path",
  JSON.stringify(fileHeader.map((element) => element.getAttribute("data-tip-text"))) ===
    JSON.stringify(["Open docs/", SERVED_ROOT, "docs"]),
);
check("the Up control carries a 32-hex owner mark", /^[0-9a-f]{32}$/.test(owner || ""));
// A document's `<label for=…>` clicks the element with that id, and the click would
// carry a real control's stamp, so no stamped control has an id to name.
check(
  "no shell control has an id a label could name",
  [...fileHeader, ...folderHeader].every((element) => !element.hasAttribute("id")),
);
check(
  "every shell control carries the same mark",
  [...fileHeader, ...folderHeader].every(
    (element) => element.getAttribute("data-mb-owner") === owner,
  ),
);
for (const element of [...fileHeader, ...folderHeader]) {
  click(element);
}
// A click on a control's child still reaches the control.
click(new FakeElement({ class: "parent-nav-arrow" }, folderHeader[0]));
const pageCalls = calls.splice(0);

// The same markup written by a document, which KPress keeps in a trusted folder,
// inside the rendered document's host: no mark, an empty one, or a guess.
const host = new FakeElement({ class: "content-body metabrowser-kpress-host md-body" });
const authoredMarkup = (mark) =>
  `<button type="button" class="folder-crumb" data-nav-dir="private"${mark}>x</button>` +
  `<button type="button" class="folder-crumb" data-nav-file="private/key.md"${mark}>x</button>` +
  `<button type="button" data-tip-text="Verified by Metabrowser"${mark}>x</button>`;
const authored = [
  ...buttons(authoredMarkup(""), host),
  ...buttons(authoredMarkup(' data-mb-owner=""'), host),
  ...buttons(authoredMarkup(` data-mb-owner="${"0".repeat(32)}"`), host),
];
for (const element of authored) {
  click(element);
}
const authoredCalls = calls.splice(0);

const tooltipFor = (element) => sandbox.tipTextAnchor({ target: element });
// Whether an anchor's tip then shows is the shell's rule (`tipAddsInformation`), which
// tests/dom/github-pulls-stacks-chrome.mjs reads in Chrome through this listener.
check(
  "the tooltip listener takes a shell crumb as its anchor",
  tooltipFor(fileHeader[2]) === fileHeader[2],
);
check(
  "a document's data-tip-text is not the application's tooltip",
  authored.every((element) => tooltipFor(element) === null),
);
// The print button page code puts in a document's card, marked as print-indicator.js
// marks it, keeps its tooltip there.
const printIndicator = sandbox.metabrowser.ownDelegate(
  new FakeElement(
    { class: "icon-btn metabrowser-print-indicator", "data-tip-text": "Print document" },
    host,
  ),
);
check(
  "a control page code placed in the document and marked keeps its tooltip",
  tooltipFor(printIndicator) === printIndicator,
);
// A document that has come to carry the page's owner value, as one fetched after its
// stylesheet read it could, spells the mark exactly. The tooltip asks for the element
// page code marked, not the value, so the copy still does not label itself.
const leaked = buttons(
  `<button type="button" data-tip-text="Verified by Metabrowser" data-mb-owner="${owner}">x</button>`,
  host,
)[0];
check(
  "a document carrying the page's own owner value still takes no tooltip",
  sandbox.MetabrowserPluginHost.isOwnedDelegate(leaked) && tooltipFor(leaked) === null,
);

check(
  "the page's controls navigate",
  JSON.stringify(pageCalls) ===
    JSON.stringify([
      "folder:docs",
      "folder:",
      "folder:docs",
      "folder:docs",
      "folder:",
      "folder:docs",
      "folder:docs",
    ]),
);
check("a document's copies of the controls do nothing", authoredCalls.length === 0);

process.stdout.write(`${JSON.stringify({ pageCalls, authoredCalls, failures }, null, 2)}\n`);
process.exit(failures.length ? 1 : 0);
