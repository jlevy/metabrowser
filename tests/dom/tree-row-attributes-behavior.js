// The attributes app.js writes on tree rows, read as the HTML parser reads them.
//
// Usage: node tree-row-attributes-behavior.js '<json {tree?, live?, children?, containers?}>'
//
// - `tree`: nodes as `/api/tree` sent them, drawn by renderTreeNodes;
// - `live`: entries as the event stream sent them, drawn by _buildRowHtml, which is
//   how a row that appears while the page is open is drawn;
// - `children`: a container's child rows as its plugin's hook sent them, drawn by
//   renderContainerChildren;
// - `containers`: the container kinds by extension, as the server writes them into the
//   page (`METABROWSER_CONTAINER_EXTS`), which is what gives a patch file its chevron.
//
// Each renderer is lifted out of app.js whole and run, with the helpers that write a
// row's attributes (esc, dataTipNumberAttr, treeItemAttributes, treeChildGroupStartHtml).
// What is stubbed writes no attribute on a row or a group: icons, ages, sizes and the
// folder's tally chip.
//
// A row template is a string, and a helper such as dataTipNumberAttr returns a whole
// attribute with its own quotes. A template that closes a quote after such a helper
// writes `…"">`, which a regular expression looking for `name="value"` pairs reads as
// well formed and the HTML parser reads as one more attribute, named `"`. So each
// start tag is tokenized here as the parser tokenizes it, and the names it finds are
// what the page's `element.getAttributeNames()` returns.
//
// Prints {tree, live, children, malformed}: for each group, every element the renderer
// wrote with its tag, classes and attribute names; and every element with a name no
// template means to write, or a name written twice.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const appSource = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/app.js"), "utf-8");

function lift(pattern, name) {
  const match = appSource.match(pattern);
  if (!match) {
    throw new Error(`${name} not found in app.js`);
  }
  return match[0];
}

function liftFunction(name) {
  return lift(new RegExp(`function ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n\\}`), name);
}

const input = JSON.parse(process.argv[2]);

const sandbox = {
  CONTAINER_EXTS: input.containers ?? {},
  // State the renderers read.
  currentPath: "",
  subtreeCache: new Map(),
  subtreeCacheKey: (nodePath) => nodePath,
  // Drawing only: nothing here writes an attribute on a row or on a group.
  ICONS: new Proxy({}, { get: () => "" }),
  getFileIcon: () => ({ cls: "", svg: "", style: "" }),
  formatAge: () => "",
  sizeHtml: () => "",
  treeDirChipHtml: () => "",
  treeNodeDisplayName: (name) => String(name ?? ""),
};
sandbox.window = { MetabrowserNavigationRoute: { displayPath: (name) => name } };
vm.createContext(sandbox);
vm.runInContext(
  [
    lift(/const TREE_PAGE_SIZE = [^;]+;/, "TREE_PAGE_SIZE"),
    lift(/const COMPRESSION_SUFFIX_BY_FORMAT = Object\.freeze\(\{[\s\S]*?\}\);/, "suffixes"),
    ...[
      "esc",
      "isPendingNumber",
      "nullableDataValue",
      "dataTipNumberAttr",
      "getExt",
      "getLogicalName",
      "treeDomId",
      "treeDepthStyle",
      "treeChildGroupStartHtml",
      "containerForNode",
      "treeItemAttributes",
      "renderTreeNodes",
      "renderContainerChildren",
      "_buildRowHtml",
    ].map(liftFunction),
    "result = { renderTreeNodes, renderContainerChildren, _buildRowHtml, pageSize: TREE_PAGE_SIZE };",
  ].join("\n"),
  sandbox,
  { filename: "tree-row-attributes.js" },
);
const app = sandbox.result;

const SPACE = new Set([" ", "\t", "\n", "\f", "\r"]);

// The attributes of the start tag that opens at `html[at] === "<"`, by the HTML
// standard's tokenizer states for a start tag (13.2.5.32 to 13.2.5.39). A character a
// state calls a parse error is kept as that state keeps it, which is the point: a
// stray quote after a quoted value starts an attribute whose name is that quote.
// Character references are left as written; no name holds one.
function startTag(html, at) {
  let i = at + 1;
  let tag = "";
  while (i < html.length && !SPACE.has(html[i]) && html[i] !== "/" && html[i] !== ">") {
    tag += html[i++].toLowerCase();
  }
  const attributes = [];
  while (i < html.length) {
    // Before attribute name.
    while (SPACE.has(html[i]) || html[i] === "/") {
      i++;
    }
    if (i >= html.length || html[i] === ">") {
      break;
    }
    // Attribute name: a leading "=" is part of the name, and so is a quote anywhere.
    let name = html[i++].toLowerCase();
    while (i < html.length && !SPACE.has(html[i]) && !"/>=".includes(html[i])) {
      name += html[i++].toLowerCase();
    }
    // After attribute name.
    while (SPACE.has(html[i])) {
      i++;
    }
    let value = "";
    if (html[i] === "=") {
      i++;
      while (SPACE.has(html[i])) {
        i++;
      }
      if (html[i] === '"' || html[i] === "'") {
        const quote = html[i++];
        while (i < html.length && html[i] !== quote) {
          value += html[i++];
        }
        i++;
      } else {
        while (i < html.length && !SPACE.has(html[i]) && html[i] !== ">") {
          value += html[i++];
        }
      }
    }
    attributes.push([name, value]);
  }
  return { tag, attributes, end: i + 1 };
}

// Every element in the markup. esc() leaves no angle bracket in text or in a value, so
// a `<` followed by a letter opens a start tag.
function elements(html) {
  const found = [];
  let at = html.indexOf("<");
  while (at !== -1) {
    if (/[a-zA-Z]/.test(html[at + 1] ?? "")) {
      const parsed = startTag(html, at);
      const names = parsed.attributes.map(([name]) => name);
      const classes = (parsed.attributes.find(([name]) => name === "class")?.[1] ?? "")
        .split(/\s+/)
        .filter(Boolean);
      found.push({ tag: parsed.tag, classes, names });
      at = html.indexOf("<", parsed.end);
    } else {
      at = html.indexOf("<", at + 1);
    }
  }
  return found;
}

const WELL_FORMED = /^[a-z][a-z0-9-]*$/;

function malformed(group, drawn) {
  return drawn
    .filter(
      ({ names }) =>
        names.some((name) => !WELL_FORMED.test(name)) || new Set(names).size !== names.length,
    )
    .map((element) => ({ group, ...element }));
}

const tree = input.tree ?? [];
const live = input.live ?? [];
const children = input.children ?? [];
if (tree.length > app.pageSize) {
  throw new Error(`more than one page of tree rows: ${tree.length}`);
}
// Every folder is drawn expanded, so the rows inside it are drawn too.
const expandEvery = { has: () => true };
const output = {
  tree: elements(app.renderTreeNodes(tree, false, { defaultExpandedPaths: expandEvery })),
  live: live.flatMap((entry) => elements(app._buildRowHtml(entry, {}))),
  children: elements(app.renderContainerChildren(children, { level: 2 })),
};
output.malformed = [
  ...malformed("tree", output.tree),
  ...malformed("live", output.live),
  ...malformed("children", output.children),
];
process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);
