// Browserless session: what a page calls its served root, and where a mirror says it is.
//
// The root summary uses the existing inventory. A mirror’s details retain the full
// source address and commit. Its main heading names the directory that holds its store.
//
// The input is what the in-process application served, recorded in
// tests/fixtures/mirror-heading-shell.json by tests/test_mirror_heading_session.py: for
// a folder, a mirror, and a mirror whose origin and application home have markup in
// their names, the tab title, the navigation heading and its data attributes, the
// commit the page was rendered for, whether the shell carried
// static/mirror-heading.js, and the fields of /api/source/status the heading is
// rendered from.
//
// Each subject uses the production view-header module and root details formatter.
// The session watches the tab title while rendering the scope, stats, and headings.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
// A commit as every line of the page names one, by the shell's own formatter.
const { shortCommit } = require("./changed-files-tree-fixture.js").shellFormatters();

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
  "view-header.js",
];

// The heading code's helpers, lifted verbatim from app.js.
const LIFTED = [
  "esc",
  "queryHtml",
  "sizeClass",
  "isPendingNumber",
  "parseTipNumber",
  "formatCountParts",
  "formatCount",
  "countClass",
  "countHtml",
  "formatTimestamp",
  "formatExactSize",
  "servedRoot",
  "mirrorHeading",
  "ownedControlAttr",
  "pathBaseName",
  "servedRootName",
  "getLogicalName",
  "formatSize",
  "sizeHtml",
  "formatAge",
  "_tipSize",
  "_tipCount",
  "treeTooltipNameHtml",
  "folderTooltipHtml",
  "rootDetailsStats",
];
// Constants the lifted code reads, lifted verbatim too.
const LIFTED_CONSTANTS = ["COMPRESSION_SUFFIX_BY_FORMAT"];
const COLLABORATORS = `
var activeFiles = new Map();
// The tree's icon resolver, which reads the file-type taxonomy: the name it was asked
// for is what the header owes it, the file's logical name.
function getFileIcon(name) {
  return { svg: "", cls: "icon-for-" + name.replace(/[^A-Za-z0-9.]/g, "_"), style: "" };
}
`;

// The view header's builders over the lifted helpers, as loadViewComposition makes them.
const VIEW_HEADER = `
var viewHeader = MetabrowserViewHeader.create({
  esc,
  servedRoot,
  servedRootName,
  ownedControlAttr,
  mirrorHeading,
  getFileIcon,
  getLogicalName,
  sizeHtml,
  countHtml,
  formatAge,
  activeFiles,
});
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

function liftConstant(name) {
  const match = appSource.match(new RegExp(`\\nconst ${name} = [\\s\\S]*?;\\n`));
  assert(match, `${name} not found in app.js`);
  return match[0].replace("const ", "var ");
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
  const lifted = [...LIFTED_CONSTANTS.map(liftConstant), ...LIFTED.map(lift)].join("\n");
  vm.runInContext(`${COLLABORATORS}${lifted}${VIEW_HEADER}`, sandbox, {
    filename: "app.js (lifted)",
  });
  page.sandbox = sandbox;
  page.title = () => currentTitle;
  return page;
}

async function observe(subject) {
  const { kind, heading: servedHeading, status } = served[subject];
  const page = createPage(subject);
  const { sandbox } = page;

  // The main heading, as the shell renders a folder's and a file's. Each control
  // carries the page's owner mark, which is drawn anew on every load.
  const owner = sandbox.metabrowser.delegateOwnerAttribute();
  assert(/^ data-mb-owner="[0-9a-f]{32}"$/.test(owner), "the page has no owner mark");
  const root = sandbox.viewHeader.renderFolderHeader({ path: "" });
  // A file's eyebrow, the Up control and its folder's address, and its title under it.
  const file = sandbox.viewHeader.viewHeaderEyebrowHtml(NESTED[kind]);
  const fileTitle = sandbox.viewHeader.viewHeaderName(NESTED[kind]);
  assert(file.split(owner).length === 4, "a control of the eyebrow is not an owned control");
  // A file's whole view header, as renderFileHeader writes it from the envelope: a served
  // file has an age from its `mtime`, a pin's file none, a compressed one its badge and
  // its logical name's icon, and one whose time is pending a skeleton. Three days old, so
  // the age reads "3d ago" whenever the session runs.
  const aged = Date.now() / 1000 - 3 * 24 * 60 * 60;
  const envelopes =
    kind === "git_revision"
      ? { "a pin's file": { path: NESTED[kind], size: 140 } }
      : {
          "a served file": { path: NESTED[kind], size: 140, mtime: aged },
          "a compressed file": {
            path: "logs/run.log.gz",
            size: 2048,
            mtime: aged,
            compressed: true,
            compression: "gzip",
          },
          "a pending time": { path: NESTED[kind], size: 140, mtime: null },
        };
  const fileHeaders = Object.fromEntries(
    Object.entries(envelopes).map(([name, envelope]) => {
      const html = sandbox.viewHeader
        .renderFileHeader(envelope)
        .replaceAll(owner, " data-mb-owner");
      // The metadata line follows the title in the heading row, before the row's end.
      const line =
        /<\/h1><div class="view-header-line page-header-line">(.*?)<\/div><\/div><span class="view-header-end">/.exec(
          html,
        );
      assert(line, `${name}: the header has no metadata line right after its title`);
      const items = [...line[1].matchAll(/class="(view-header-item|file-header-badge[^"]*)"/g)];
      return [
        name,
        {
          icon: /class="view-header-icon file-identity-icon ([^"]*)"/.exec(html)?.[1] ?? null,
          title: /<h1[^>]*>(.*?)<\/h1>/.exec(html)?.[1] ?? null,
          line: text(line[1]),
          lineParts: items.map((item) => item[1]),
          pending: line[1].includes("tally-pending"),
        },
      ];
    }),
  );

  const before = sandbox.rootDetailsStats(page.heading.dataset);
  Object.assign(page.heading.dataset, TALLY);
  const after = sandbox.rootDetailsStats(page.heading.dataset);

  return {
    subject,
    kind,
    status,
    title: {
      served: served[subject].title,
      afterEveryStep: page.title(),
      writes: page.titleWrites,
    },
    navigationHeading: { html: servedHeading, text: text(servedHeading) },
    mainHeading: {
      root: text(root),
      file: { html: file.replaceAll(owner, " data-mb-owner"), text: text(file), title: fileTitle },
      fileHeaders,
    },
    details: {
      location: page.heading.dataset.mirrorLocation ?? page.heading.dataset.servedRoot,
      source: page.heading.dataset.mirrorTip ?? null,
      before: text(before),
      after: text(after),
    },
    raw: { root, file },
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
    assert(page.title.afterEveryStep === page.title.served, `${page.subject}: the tab is retitled`);
  }

  // A folder's page is what it was: its path, then the address, and nothing of a mirror.
  // At the root the eyebrow is the directory that holds the root, and the root's name is
  // the title; under it the eyebrow is the root's address and the folders above the item,
  // each followed by a slash.
  const folderRoot = served.folder.dataset.servedRoot;
  const cut = folderRoot.lastIndexOf("/");
  assert(
    folder.mainHeading.root === `\u2191 ${folderRoot.slice(0, cut)} ${folderRoot.slice(cut + 1)}`,
    `a folder's root reads ${folder.mainHeading.root}`,
  );
  assert(
    folder.mainHeading.file.text === `\u2191 ${folderRoot} / docs /` &&
      folder.mainHeading.file.title === "guide.md",
    `a folder's eyebrow reads ${folder.mainHeading.file.text}`,
  );
  assert(
    folder.details.before === "" && folder.details.after === "3 files 140 bytes",
    "folder stats",
  );
  assert(folder.details.source === null, "a local folder has no mirror details");

  // A file's line: badges, then the size, then the age, last; no age without a time, and
  // a skeleton while the time is pending.
  const headers = folder.mainHeading.fileHeaders;
  assert(headers["a served file"].line === "140 B · 3d ago", "a served file's line");
  assert(
    headers["a compressed file"].lineParts[0].startsWith("file-header-badge") &&
      headers["a compressed file"].icon === "icon-for-run.log",
    "a compressed file's badge leads its line, and its icon is its logical name's",
  );
  assert(headers["a pending time"].pending, "a pending time draws no skeleton");
  for (const page of [mirror, hostile]) {
    assert(
      page.mainHeading.fileHeaders["a pin's file"].line === "140 B",
      "a pin's file has an age",
    );
  }
  for (const page of [mirror, hostile]) {
    const { name, location, pin, ref_name: ref } = page.status;
    // The note names the store's directory; the details and the status keep the bare
    // repository inside it, where `git -C` works.
    assert(location.endsWith("/repository.git"), `${page.subject}: the location is ${location}`);
    const directory = location.slice(0, -"/repository.git".length);
    const where = `mirror in ${directory}`;
    const sentence = "Bare Git mirror with no checked-out files.";
    const { root, file } = page.mainHeading;

    // The repository's name is the root, in both headings. The navigation heading is the
    // name alone: the ref selector names the ref.
    assert(
      page.navigationHeading.text === name && ref !== null,
      `${page.subject}: the navigation heading reads ${page.navigationHeading.text}`,
    );
    // A mirror's root has no directory above it: its eyebrow is the note alone.
    assert(root === `\u2191 ${where} ${name}`, `${page.subject}: the root reads ${root}`);
    assert(
      file.text === `\u2191 ${name} / docs / ${where}` && file.title === "guide.md",
      `${page.subject}: a file's eyebrow reads ${file.text}`,
    );
    // The address is the name and the path under it: no commit, and no directory.
    const address = file.text.slice(0, file.text.indexOf(where));
    assert(!address.includes(shortCommit(pin)), `${page.subject}: the address names the commit`);
    assert(!address.includes(directory), `${page.subject}: the address names the cache`);
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
    assert(page.details.location === location, "details show the local mirror path");
    assert(page.details.source === sentence, "the tip explains the mirror");
    assert(page.details.after === "3 files 140 bytes", "mirror stats follow the tree");
  }

  // Markup in a name, an address, or a path is text wherever it is written: each stands
  // escaped where the page writes it, and never raw.
  for (const key of ["name", "origin", "location"]) {
    const value = hostile.status[key];
    assert(escaped(value) !== value, `the hostile ${key} has no markup to escape: ${value}`);
    const written = {
      name: [hostile.raw.root, hostile.raw.file, hostile.navigationHeading.html],
      origin: [],
      location: [hostile.raw.root, hostile.raw.file],
    }[key];
    for (const html of written) {
      // The heading's note names the store's directory and the tooltips the bare
      // repository inside it, so each stands where it is written, escaped.
      const text =
        key === "location" && (html === hostile.raw.root || html === hostile.raw.file)
          ? value.slice(0, -"/repository.git".length)
          : value;
      assert(html.includes(escaped(text)), `the hostile ${key} is missing from ${html}`);
      assert(!html.includes(text), `the hostile ${key} was written as markup: ${html}`);
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
