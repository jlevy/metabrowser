// Browserless session: what a page calls its served root, and where a mirror says it is.
//
// A folder's page is headed by the folder's name, and its main heading starts with the
// folder's path. A served mirror's page showed the full commit ID in both places and
// said nowhere that its files came out of the cache (mb-fndz). It is now headed by the
// repository's name, as a checkout would be called, with a control that copies the
// full commit beside the short one, and its main heading ends with a note saying where
// the mirror is kept, whose tooltip says what that directory is.
//
// The input is what the in-process application served, recorded in
// tests/fixtures/mirror-heading-shell.json by tests/test_mirror_heading_session.py: for
// a folder, a mirror, and a mirror whose origin and application home have markup in
// their names, the tab title, the navigation heading and its data attributes, the
// commit the page was rendered for, whether the shell carried
// static/mirror-heading.js, and the fields of /api/source/status the heading is
// rendered from.
//
// Per subject, a fresh context is a page: mirror-heading.js runs first when the shell
// carried it, as its inline script does, then the production SDK and its modules load
// whole. The shell's own heading code is lifted verbatim from app.js, which cannot
// load without a document: the folder header and the file header's address, and the
// block that wires the navigation heading's tooltip. Nothing here composes a heading:
// every string below is what that code returned or showed.
//
// The steps, each observed and printed:
// - the page loads: DOMContentLoaded mounts the commit's copy control on a mirror;
// - the main heading is rendered for the root folder and for a nested file;
// - the pointer enters the navigation heading before and after the tree has loaded,
//   then the root's name and the note in the main heading;
// - the copy control is clicked, through the SDK's delegated listener.
// `document.title` is watched across all of them: no step may write it.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf8");
const served = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/mirror-heading-shell.json"), "utf8"),
);

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

// The heading code, lifted verbatim from app.js.
const LIFTED = [
  "esc",
  "queryHtml",
  "sizeClass",
  "isPendingNumber",
  "parseTipNumber",
  "formatCount",
  "formatTimestamp",
  "formatExactSize",
  "servedRoot",
  "mirrorHeading",
  "ownedControlAttr",
  "headerAddressHtml",
  "renderFolderHeader",
  "_tipSize",
  "_tipCount",
  "treeTooltipNameHtml",
  "folderTooltipHtml",
];
// The statement that wires the navigation heading's tooltip, from its comment to its end.
const TOOLTIP_BLOCK = /\n\/\/ Header hover tooltip[\s\S]*?\n\}\);\n/;

// What the lifted code calls that does not branch on the subject. The tooltip is the
// application's one tooltip, which mirror-heading.js reaches as plugins do.
const COLLABORATORS = `
var ICONS = { print: "" };
function showTooltip(html, anchor) {
  __shown.push({ html: html, anchor: anchor });
}
function hideTooltip() {
  __shown.push(null);
}
window.MetabrowserTooltip = { show: showTooltip, hide: hideTooltip };
`;

// One nested file, by the identity each subject's routes give it.
const NESTED = { filesystem: "docs/guide.md", git_revision: "g1-ZG9jcw/g1-Z3VpZGUubWQ" };
// The top-level tally the tree's first load writes onto the heading.
const TALLY = { tipFiles: "3", tipSize: "140", tipMtime: "" };

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function lift(name) {
  const match = appSource.match(new RegExp(`\\nfunction ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n\\}`));
  assert(match, `${name} not found in app.js`);
  return match[0];
}

function escaped(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** The text a reader sees: tags dropped, entities decoded. */
function text(html) {
  return html
    .replace(/<[^>]*>/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

class Element {}
class HTMLElement extends Element {}

/** An element with attributes, a dataset over its data-* attributes, and a class list. */
class FakeElement extends HTMLElement {
  constructor(tag, attributes = {}) {
    super();
    this.tagName = tag.toUpperCase();
    this.attributes = new Map(Object.entries(attributes));
    this.listeners = {};
    this.nextElementSibling = null;
    this.innerHTML = "";
    const attrs = this.attributes;
    const name = (key) => `data-${key.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}`;
    this.dataset = new Proxy(
      {},
      {
        get: (_target, key) => (typeof key === "string" ? attrs.get(name(key)) : undefined),
        set: (_target, key, value) => {
          attrs.set(name(key), String(value));
          return true;
        },
        has: (_target, key) => attrs.has(name(key)),
        ownKeys: () =>
          [...attrs.keys()]
            .filter((key) => key.startsWith("data-"))
            .map((key) => key.slice(5).replace(/-([a-z])/g, (_m, c) => c.toUpperCase())),
        getOwnPropertyDescriptor: (_target, key) =>
          attrs.has(name(key))
            ? { value: attrs.get(name(key)), enumerable: true, configurable: true, writable: true }
            : undefined,
      },
    );
    const classes = () => (attrs.get("class") || "").split(/\s+/).filter(Boolean);
    this.classList = {
      contains: (cls) => classes().includes(cls),
      add: (cls) => attrs.set("class", [...new Set([...classes(), cls])].join(" ")),
      remove: (cls) =>
        attrs.set(
          "class",
          classes()
            .filter((have) => have !== cls)
            .join(" "),
        ),
    };
  }
  set className(value) {
    this.attributes.set("class", value);
  }
  get className() {
    return this.attributes.get("class") || "";
  }
  set type(value) {
    this.attributes.set("type", value);
  }
  getAttribute(name) {
    return this.attributes.has(name) ? this.attributes.get(name) : null;
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  addEventListener(type, listener) {
    this.listeners[type] = [...(this.listeners[type] || []), listener];
  }
  after(node) {
    this.nextElementSibling = node;
  }
  matches(selector) {
    return selector.split(",").some((one) => {
      const single = one.trim();
      const attribute = /^\[([\w-]+)\]$/.exec(single);
      if (attribute) {
        return this.attributes.has(attribute[1]);
      }
      assert(single.startsWith("."), `unsupported selector ${single}`);
      return this.classList.contains(single.slice(1));
    });
  }
  closest(selector) {
    return this.matches(selector) ? this : null;
  }
}

/** The data attributes an element was served or given, by their dataset names. */
function datasetOf(element) {
  return Object.fromEntries(Object.keys(element.dataset).map((key) => [key, element.dataset[key]]));
}

function createPage(subject) {
  const { kind, title, dataset, pagePin, mirrorModule } = served[subject];
  const heading = new FakeElement("a", { class: "header-path" });
  for (const [key, value] of Object.entries(dataset)) {
    heading.dataset[key] = value;
  }
  const page = { heading, shown: [], copied: [], titleWrites: [], listeners: {}, wiring: null };
  let currentTitle = title;
  const document = {
    get title() {
      return currentTitle;
    },
    set title(value) {
      page.titleWrites.push(value);
      currentTitle = value;
    },
    addEventListener(type, listener) {
      const registered = { listener, by: page.wiring };
      page.listeners[type] = [...(page.listeners[type] || []), registered];
    },
    createElement: (tag) => new FakeElement(tag),
    querySelector: (selector) => (selector === ".header-path" ? heading : null),
    querySelectorAll: () => [],
    documentElement: {},
  };
  const sandbox = {
    __shown: page.shown,
    Array,
    Date,
    Element,
    HTMLElement,
    JSON,
    Map,
    Number,
    Object,
    Promise,
    Set,
    String,
    TextDecoder,
    URL,
    Uint8Array,
    atob,
    btoa,
    clearTimeout() {},
    console,
    decodeURIComponent,
    document,
    encodeURIComponent,
    location: { origin: "http://127.0.0.1:8411", pathname: "/view/" },
    navigator: {
      clipboard: {
        writeText(value) {
          page.copied.push(value);
          return Promise.resolve();
        },
      },
    },
    // The copy control's feedback resets on a timer the session never needs to run.
    setTimeout: () => 0,
    METABROWSER_SOURCE_KIND: kind,
    METABROWSER_PATH_ENCODING: "bytes",
  };
  if (pagePin) {
    sandbox.METABROWSER_SOURCE_PIN = pagePin;
  }
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  const load = (name) => {
    const absolute = path.join(staticDir, name);
    page.wiring = name;
    vm.runInContext(fs.readFileSync(absolute, "utf8"), sandbox, { filename: absolute });
  };
  // The shell's inline scripts run before any script it links.
  if (mirrorModule) {
    load("mirror-heading.js");
  }
  for (const name of PRODUCTION_MODULES) {
    if (name === "navigation.js" && kind === "git_revision") {
      load("git-path.js");
    }
    load(name);
  }
  page.wiring = "app.js";
  const tooltipBlock = appSource.match(TOOLTIP_BLOCK);
  assert(tooltipBlock, "the navigation heading's tooltip block was not found in app.js");
  vm.runInContext(`${COLLABORATORS}${LIFTED.map(lift).join("\n")}${tooltipBlock[0]}`, sandbox, {
    filename: "app.js (lifted)",
  });
  page.sandbox = sandbox;
  page.title = () => currentTitle;
  return page;
}

/** Fire the page's document listeners of *type* that *scripts* registered. */
function dispatch(page, type, event, scripts) {
  for (const { listener, by } of page.listeners[type] || []) {
    if (!scripts || scripts.includes(by)) {
      listener(event);
    }
  }
}

/** What the tooltip shows when the pointer enters *target*, or null. */
function hover(page, target) {
  page.shown.length = 0;
  if (target === page.heading) {
    for (const listener of page.heading.listeners.mouseenter || []) {
      listener({ target });
    }
  } else {
    dispatch(page, "mouseenter", { target }, ["mirror-heading.js"]);
  }
  const shown = page.shown.at(-1);
  if (!shown) {
    return null;
  }
  assert(shown.anchor === target, "a tooltip was anchored to another element");
  return shown.html;
}

async function observe(subject) {
  const { kind, heading: servedHeading, status } = served[subject];
  const page = createPage(subject);
  const { sandbox } = page;

  // The page loads.
  dispatch(page, "DOMContentLoaded", {}, ["mirror-heading.js", "app.js"]);

  // The main heading, as the shell renders a folder's and a file's. Each control
  // carries the page's owner mark, which is drawn anew on every load.
  const owner = sandbox.metabrowser.delegateOwnerAttribute();
  assert(/^ data-mb-owner="[0-9a-f]{32}"$/.test(owner), "the page has no owner mark");
  const root = sandbox.renderFolderHeader({ path: "" });
  const file = sandbox.headerAddressHtml(NESTED[kind], true);
  assert(file.split(owner).length === 4, "a crumb of the address is not an owned control");

  // The pointer enters the navigation heading, before and after the tree has loaded.
  const tipBefore = hover(page, page.heading);
  Object.assign(page.heading.dataset, { tipName: page.heading.dataset.servedRoot, ...TALLY });
  const tipAfter = hover(page, page.heading);
  // Then the root's name and the note, which the shell built above.
  const tipName = hover(page, new FakeElement("span", { class: "file-header-root" }));
  const tipNote = hover(page, new FakeElement("span", { class: "file-header-mirror-text" }));

  // The copy control beside the short commit, and a click on it.
  const control = page.heading.nextElementSibling;
  let commitCopy = null;
  if (control) {
    dispatch(page, "click", { target: control });
    await Promise.resolve();
    await Promise.resolve();
    commitCopy = {
      attributes: Object.fromEntries(
        [...control.attributes].filter(([name]) => name !== "data-mb-owner"),
      ),
      ownerStamped: sandbox.MetabrowserPluginHost.isOwnedDelegate(control),
      copied: [...page.copied],
    };
  }

  return {
    subject,
    kind,
    status,
    title: {
      served: served[subject].title,
      afterEveryStep: page.title(),
      writes: page.titleWrites,
    },
    navigationHeading: { html: servedHeading, text: text(servedHeading), commitCopy },
    mainHeading: {
      root: text(root),
      file: { html: file.replaceAll(owner, " data-mb-owner"), text: text(file) },
    },
    tooltips: {
      navigationHeading: { served: text(tipBefore), afterTreeLoad: text(tipAfter) },
      rootName: tipName === null ? null : text(tipName),
      note: tipNote === null ? null : text(tipNote),
    },
    // Kept out of the transcript: what the assertions below read.
    raw: { root, file, tipAfter, tipName, tipNote, heading: datasetOf(page.heading) },
  };
}

async function main() {
  const observed = [];
  for (const subject of Object.keys(served)) {
    observed.push(await observe(subject));
  }
  const [folder, mirror, hostile] = observed;

  // No step wrote the tab's title, which stays the one the server wrote.
  for (const page of observed) {
    assert(page.title.writes.length === 0, `${page.subject}: a step set the tab title`);
    assert(page.title.afterEveryStep === "Metabrowser", `${page.subject}: the tab is retitled`);
  }

  // A folder's page is what it was: its path, then the address, and nothing of a mirror.
  const folderRoot = served.folder.dataset.servedRoot;
  assert(
    folder.mainHeading.root === `\u2191 ${folderRoot} /`,
    `a folder's root reads ${folder.mainHeading.root}`,
  );
  assert(
    folder.mainHeading.file.text === `${folderRoot} / docs / guide.md`,
    `a folder's address reads ${folder.mainHeading.file.text}`,
  );
  assert(
    folder.tooltips.navigationHeading.served === `${folderRoot} Jump to root` &&
      folder.tooltips.navigationHeading.afterTreeLoad ===
        `${folderRoot} 3 files 140 bytes Jump to root`,
    "a folder's tooltip changed",
  );
  assert(
    !/mirror/i.test(folder.raw.root + folder.raw.file + folder.raw.tipAfter) &&
      folder.tooltips.rootName === null &&
      folder.tooltips.note === null &&
      folder.navigationHeading.commitCopy === null,
    "a folder's page shows something of a mirror",
  );

  for (const page of [mirror, hostile]) {
    const { name, origin, location, pin, ref_name: ref } = page.status;
    const where = `mirror in ${location}`;
    const sentence = `Mirror of ${origin} at ${pin}, stored in ${location}: a bare Git repository, with no checked-out files.`;
    const { root, file } = page.mainHeading;

    // The repository's name is the root, in both headings, with the commit beside it.
    assert(
      page.navigationHeading.text === `${name} ${ref} ${pin.slice(0, 12)}`,
      `${page.subject}: the navigation heading reads ${page.navigationHeading.text}`,
    );
    assert(root === `\u2191 ${name} / ${where}`, `${page.subject}: the root reads ${root}`);
    assert(
      file.text === `${name} / docs / guide.md ${where}`,
      `${page.subject}: a file's address reads ${file.text}`,
    );
    // The address is the name and the path under it: no commit, and no directory.
    const address = file.text.slice(0, file.text.indexOf(where));
    assert(!address.includes(pin.slice(0, 12)), `${page.subject}: the address names the commit`);
    assert(!address.includes(location), `${page.subject}: the address names the cache`);
    // The note follows the last crumb; it is not the address's prefix.
    for (const html of [page.raw.root, file.html]) {
      assert(
        html.indexOf("file-header-mirror") > html.lastIndexOf("folder-crumb"),
        `${page.subject}: the note is not after the address`,
      );
      assert(
        html.split("file-header-mirror-text").length === 2,
        `${page.subject}: a heading does not hold exactly one note`,
      );
    }
    // The name, the note, and the navigation heading each say what the directory is.
    assert(page.tooltips.rootName === sentence, `${page.subject}: the name's tooltip is wrong`);
    assert(page.tooltips.note === sentence, `${page.subject}: the note's tooltip is wrong`);
    const { served: before, afterTreeLoad: after } = page.tooltips.navigationHeading;
    assert(before === `${name} ${sentence} Jump to root`, `${page.subject}: tooltip: ${before}`);
    assert(
      after === `${name} 3 files 140 bytes ${sentence} Jump to root`,
      `${page.subject}: tooltip after the tree loads: ${after}`,
    );
    // The mirror's line of a tooltip is the one that wraps.
    for (const html of [page.raw.tipAfter, page.raw.tipName, page.raw.tipNote]) {
      assert(/class="(tip-detail )?tip-mirror"/.test(html), `${page.subject}: no tip-mirror line`);
    }
    // The full commit can be copied from beside the short one, by the SDK's delegate.
    const { commitCopy } = page.navigationHeading;
    assert(commitCopy !== null, `${page.subject}: no copy control beside the commit`);
    assert(
      commitCopy.ownerStamped && commitCopy.attributes["data-mb-copy-text"] === pin,
      `${page.subject}: the copy control does not carry the full commit`,
    );
    assert(
      JSON.stringify(commitCopy.copied) === JSON.stringify([pin]),
      `${page.subject}: a click copied ${JSON.stringify(commitCopy.copied)}`,
    );
    assert(
      commitCopy.attributes["data-tip-text"] === "Copied!",
      `${page.subject}: the copy control gave no feedback`,
    );
  }

  // Markup in a name, an address, or a path is text wherever it is written: each stands
  // escaped where the page writes it, and never raw.
  for (const key of ["name", "origin", "location"]) {
    const value = hostile.status[key];
    assert(escaped(value) !== value, `the hostile ${key} has no markup to escape: ${value}`);
    const written = {
      name: [
        hostile.raw.root,
        hostile.raw.file,
        hostile.raw.tipAfter,
        hostile.navigationHeading.html,
      ],
      origin: [hostile.raw.tipAfter, hostile.raw.tipName, hostile.raw.tipNote],
      location: [hostile.raw.root, hostile.raw.file, hostile.raw.tipAfter, hostile.raw.tipNote],
    }[key];
    for (const html of written) {
      assert(html.includes(escaped(value)), `the hostile ${key} is missing from ${html}`);
      assert(!html.includes(value), `the hostile ${key} was written as markup: ${html}`);
    }
  }
  assert(
    hostile.status.name === "a<b>&�x",
    `the hostile origin is named ${JSON.stringify(hostile.status.name)}`,
  );

  console.log(
    JSON.stringify(
      observed.map(({ raw: _raw, ...page }) => page),
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
