// Browserless session: what a page calls its served root, and where a mirror says it is.
//
// A folder's page is headed by the folder's name, and its main heading starts with the
// folder's path. A served mirror's page showed the full commit ID in both places and
// said nowhere that its files came out of the cache (mb-fndz). It is now headed by the
// repository's name, as a checkout would be called, and its main heading ends with a
// note saying where the mirror is kept, whose tooltip says what that directory is.
//
// The input is what the in-process application served, recorded in
// tests/fixtures/mirror-heading-shell.json by tests/test_mirror_heading_session.py: for
// a folder, a mirror, and a mirror whose origin has markup and an invisible character in
// its name, the tab title, the navigation heading and its data attributes, and the
// fields of /api/source/status the heading is rendered from.
//
// Per subject, a fresh context loads navigation.js whole, with git-path.js ahead of it
// on a mirror as the shell does, and runs the shell's own heading code lifted out of
// app.js, which cannot load without a document: the main heading's address for the root
// and for a nested file, and the navigation heading's tooltip before and after the tree
// has loaded. The served root comes from servedRootAddress in navigation.js.
//
// What the transcript shows, per subject: each of those as HTML and as the text a
// reader sees. It fails unless a folder's page is unchanged, a mirror's address starts
// with the repository's name and never names a commit or a path, the note and the
// tooltips are the only places the location stands, the tooltip names the origin and
// the full commit, a hostile name is escaped wherever it is written, and no script sets
// the tab title, which stays the one the server wrote.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf8");
const served = JSON.parse(
  fs.readFileSync(path.join(repoRoot, "tests/fixtures/mirror-heading-shell.json"), "utf8"),
);

// The heading code, lifted verbatim from app.js.
const LIFTED = [
  "esc",
  "sizeClass",
  "isPendingNumber",
  "parseTipNumber",
  "formatCount",
  "formatTimestamp",
  "formatExactSize",
  "servedRootAddress",
  "ownedControlAttr",
  "headerAddressHtml",
  "servedRootTooltipHtml",
  "_tipSize",
  "_tipCount",
  "treeTooltipNameHtml",
  "folderTooltipHtml",
];

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

/** Every tooltip an element of *html* carries. */
function tips(html) {
  return [...html.matchAll(/data-tip-text="([^"]*)"/g)].map((match) => text(match[1]));
}

function createContext(kind, dataset) {
  const heading = { dataset };
  const sandbox = {
    Array,
    Date,
    JSON,
    Map,
    Number,
    Object,
    Set,
    String,
    TextDecoder,
    URL,
    Uint8Array,
    atob,
    btoa,
    console,
    decodeURIComponent,
    encodeURIComponent,
    document: {
      querySelector(selector) {
        return selector === ".header-path" ? heading : null;
      },
    },
    location: { origin: "http://127.0.0.1:8411", pathname: "/view/" },
    METABROWSER_SOURCE_KIND: kind,
    METABROWSER_PATH_ENCODING: "bytes",
    // The shared formatter runtime, which only chooses a size's weight class.
    MetabrowserFormatters: { sizeClass: () => "", countClass: () => "" },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  for (const name of kind === "git_revision"
    ? ["git-path.js", "navigation.js"]
    : ["navigation.js"]) {
    const absolute = path.join(staticDir, name);
    vm.runInContext(fs.readFileSync(absolute, "utf8"), sandbox, { filename: absolute });
  }
  // `queryHtml` is the shell's typed querySelector; nothing in it reads the subject.
  vm.runInContext(
    `function queryHtml(selector) { return document.querySelector(selector); }\n${LIFTED.map(lift).join("\n")}`,
    sandbox,
    { filename: "app-heading.js" },
  );
  return sandbox;
}

function observe(subject) {
  const { kind, title, heading, dataset, status } = served[subject];
  const sandbox = createContext(kind, { ...dataset });
  const note = sandbox.servedRootAddress().note;
  // A folder's header and a file's both end their address with the note.
  const root = sandbox.headerAddressHtml("", false) + note;
  const file = sandbox.headerAddressHtml(NESTED[kind], true) + note;
  const tipBefore = sandbox.servedRootTooltipHtml({ ...dataset });
  // The tree's first load names the tooltip by the served root, as the shell does.
  const tipAfter = sandbox.servedRootTooltipHtml({
    ...dataset,
    tipName: dataset.servedRoot,
    ...TALLY,
  });
  return {
    subject,
    kind,
    status,
    title,
    navigationHeading: { html: heading, text: text(heading) },
    mainHeading: {
      root: text(root),
      file: { html: file, text: text(file), tooltips: [...new Set(tips(file))] },
    },
    navigationTooltip: { served: text(tipBefore), afterTreeLoad: text(tipAfter) },
    // Kept out of the transcript: what the assertions below read.
    raw: { root, file, tipAfter },
  };
}

const observed = Object.keys(served).map(observe);
const [folder, mirror, hostile] = observed;

assert(
  !/document\.title/.test(appSource),
  "a script sets the tab title; the session pins only the one the server writes",
);
for (const page of observed) {
  assert(page.title === "Metabrowser", `${page.subject}: the tab is titled ${page.title}`);
}

// A folder's page is what it was: its path, then the address, and nothing about a mirror.
assert(
  folder.mainHeading.file.text === `${served.folder.dataset.servedRoot} / docs / guide.md`,
  `a folder's address reads ${folder.mainHeading.file.text}`,
);
assert(
  folder.mainHeading.root === `${served.folder.dataset.servedRoot} /`,
  "a folder's root changed",
);
assert(!folder.raw.file.includes("file-header-mirror"), "a folder showed a mirror note");
assert(
  folder.mainHeading.file.tooltips.every((tip) => !tip.startsWith("Mirror of")),
  "a folder's heading says it is a mirror",
);
assert(
  !folder.navigationTooltip.afterTreeLoad.includes("Mirror"),
  "a folder's tooltip says mirror",
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
  assert(root === `${name} / ${where}`, `${page.subject}: the root reads ${root}`);
  assert(
    file.text === `${name} / docs / guide.md ${where}`,
    `${page.subject}: a file's address reads ${file.text}`,
  );
  // The address is the name and the path under it: no commit, and no directory.
  const address = file.text.slice(0, file.text.indexOf(where));
  assert(!address.includes(pin.slice(0, 12)), `${page.subject}: the address names the commit`);
  assert(!address.includes(location), `${page.subject}: the address names the cache`);
  // The note follows the last crumb; it is not the address's prefix.
  assert(
    file.html.indexOf("file-header-mirror") > file.html.lastIndexOf("folder-crumb"),
    `${page.subject}: the note is not after the address`,
  );
  // Both the name and the note say what the directory is, and that says the full commit.
  assert(
    tips(file.html).filter((tip) => tip === sentence).length === 2,
    `${page.subject}: the heading's tooltips are ${JSON.stringify(file.tooltips)}`,
  );
  for (const tip of [page.navigationTooltip.served, page.navigationTooltip.afterTreeLoad]) {
    assert(tip.startsWith(name), `${page.subject}: the tooltip is not named ${name}`);
    assert(tip.includes(sentence), `${page.subject}: the tooltip does not say what the mirror is`);
    assert(tip.endsWith("Jump to root"), `${page.subject}: the tooltip lost its action`);
  }
}

// Markup in a name, an address, or a path is text wherever it is written: each stands
// escaped, once per place the page writes it, and never raw.
function escaped(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
for (const key of ["name", "origin", "location"]) {
  const value = hostile.status[key];
  assert(escaped(value) !== value, `the hostile ${key} has no markup to escape: ${value}`);
  for (const html of [hostile.raw.root, hostile.raw.file, hostile.raw.tipAfter]) {
    assert(html.includes(escaped(value)), `the hostile ${key} is missing from ${html}`);
    assert(!html.includes(value), `the hostile ${key} was written as markup: ${html}`);
  }
}
assert(
  hostile.navigationHeading.html.includes(escaped(hostile.status.name)),
  "the name is missing",
);
assert(!hostile.navigationHeading.html.includes(hostile.status.name), "the name is markup");
assert(
  hostile.status.name === "a<b>&\ufffdx",
  `the hostile origin is named ${JSON.stringify(hostile.status.name)}`,
);

console.log(
  JSON.stringify(
    observed.map(({ raw: _raw, ...page }) => page),
    null,
    2,
  ),
);
