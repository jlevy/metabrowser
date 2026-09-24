// Browserless session: the shell's document-wide click and tooltip delegates act only
// on controls page code created.
//
// A trusted folder's Markdown keeps class, id, and data-* through KPress, so a
// document can spell the shell's control markup: an address crumb's
// `data-nav-dir` / `data-nav-file`, the header's `#print-view-btn`, a
// `data-tip-text` label. The action delegates act only on an element carrying the
// SDK's per-page owner mark; the tooltip ignores a rendered document's markup.
//
// The production SDK loads whole. The shell's markup builders and delegates are
// lifted verbatim from app.js, which cannot load without a document, as
// source-kind-session.js does; their navigation and print collaborators are
// stubs that record calls. Each click target is an element built from the
// attributes the lifted builder wrote, so the owner mark under test is the one the
// production code emitted, not one this file assigned.
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
];

// Builders, gates, and delegates lifted verbatim from app.js.
const LIFTED = [
  "esc",
  "queryHtml",
  "servedRoot",
  "eventTargetElement",
  "ownedControlAttr",
  "isOwnedControl",
  "headerAddressHtml",
  "renderFolderHeader",
  "tipTextAnchor",
  "onPrintViewClick",
  "onHeaderNavigationClick",
];

const COLLABORATORS = `
var ICONS = { print: "" };
function navigateToFolder(path) {
  __calls.push("folder:" + path);
}
function navigateToPath(path) {
  __calls.push("file:" + path);
  return Promise.resolve();
}
function printActiveView() {
  __calls.push("print");
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
  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }
  hasAttribute(name) {
    return this.attributes.has(name);
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
    querySelector: () => null,
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
vm.runInContext(COLLABORATORS + LIFTED.map(lift).join("\n"), sandbox, {
  filename: "app.js (lifted)",
});

function click(element) {
  sandbox.onPrintViewClick({ target: element });
  sandbox.onHeaderNavigationClick({ target: element });
}

// The page's own controls, as the shell renders them.
const fileHeader = buttons(sandbox.headerAddressHtml("docs/a%25b.md", true));
const folderHeader = buttons(sandbox.renderFolderHeader({ path: "docs/sub" }));
const owner = fileHeader[0].getAttribute("data-mb-owner");
check(
  "the crumbs are well-formed controls with their own tooltips",
  JSON.stringify(fileHeader.map((element) => element.getAttribute("data-tip-text"))) ===
    JSON.stringify(["Served root", "docs", "docs/a%b.md"]),
);
check("the root crumb carries a 32-hex owner mark", /^[0-9a-f]{32}$/.test(owner || ""));
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
  `<button class="icon-btn" id="print-view-btn" type="button"${mark}>x</button>` +
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
check("a shell crumb shows its tooltip", tooltipFor(fileHeader[1]) === fileHeader[1]);
check(
  "a document's data-tip-text is not the application's tooltip",
  authored.every((element) => tooltipFor(element) === null),
);

check(
  "the page's controls navigate, open the file, and print",
  JSON.stringify(pageCalls) ===
    JSON.stringify([
      "folder:",
      "folder:docs",
      "file:docs/a%25b.md",
      "folder:docs",
      "folder:",
      "folder:docs",
      "folder:docs/sub",
      "print",
      "folder:docs",
    ]),
);
check("a document's copies of the controls do nothing", authoredCalls.length === 0);

process.stdout.write(`${JSON.stringify({ pageCalls, authoredCalls, failures }, null, 2)}\n`);
process.exit(failures.length ? 1 : 0);
