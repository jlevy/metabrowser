// Which tree rows app.js prefetches on hover: the production row markup, read by the
// production decision.
//
// Usage: node hover-prefetch-behavior.js '<json {tree?, live?, children?}>'
//
// - `tree`: file nodes as `/api/tree` sent them, drawn by renderTreeNodes;
// - `live`: entries as the event stream sent them, drawn by _buildRowHtml, which is
//   how a file that appears while the page is open gets its row;
// - `children`: a container's child rows as its plugin's hook sent them, drawn by
//   renderContainerChildren.
//
// Each renderer is lifted out of app.js whole and run, with the helpers that write a
// row's attributes (esc, dataTipNumberAttr, treeItemAttributes, getLogicalName). The
// attributes of each row it wrote are then read back as the row's dataset, the row is
// tested as the hover listener tests it (`.tree-item.tree-file`), and the production
// shouldPrefetchFile decides. So a change to what a renderer writes on a row reaches
// the decision here as it does in the page. What is stubbed draws and decides nothing:
// icons, ages, sizes, and the container chevron.
//
// Prints {cap, tree, live, children}: for each group, each row's path, the three
// attributes the decision reads, and whether a hover would prefetch it.

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

const sandbox = {
  // State the decision and the renderers read.
  fileCache: new Map(),
  activeFiles: new Set(),
  currentPath: "",
  // Drawing only: nothing here writes an attribute on the row's own element.
  ICONS: new Proxy({}, { get: () => "" }),
  getFileIcon: () => ({ cls: "", svg: "", style: "" }),
  formatAge: () => "",
  sizeHtml: () => "",
  treeDirChipHtml: () => "",
  treeChildGroupStartHtml: () => "",
  treeNodeDisplayName: (name) => String(name ?? ""),
  // No fixture is a container file; a container adds a chevron and three attributes
  // the decision does not read.
  containerForNode: () => null,
};
sandbox.window = { MetabrowserNavigationRoute: { displayPath: (name) => name } };
vm.createContext(sandbox);
vm.runInContext(
  [
    lift(/const FILE_PREFETCH_MAX_BYTES = [^;]+;/, "FILE_PREFETCH_MAX_BYTES"),
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
      "treeItemAttributes",
      "renderTreeNodes",
      "renderContainerChildren",
      "_buildRowHtml",
      "shouldPrefetchFile",
    ].map(liftFunction),
    "result = { renderTreeNodes, renderContainerChildren, _buildRowHtml, shouldPrefetchFile,",
    "  cap: FILE_PREFETCH_MAX_BYTES, pageSize: TREE_PAGE_SIZE };",
  ].join("\n"),
  sandbox,
  { filename: "hover-prefetch.js" },
);
const app = sandbox.result;

const unescapeAttribute = (text) =>
  text
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&");

// Every row element in the markup, as its class list and dataset. esc() leaves no
// quote or angle bracket inside an attribute value, so a tag ends at its first `>`.
function rows(html) {
  const found = [];
  for (const tag of html.matchAll(/<div class="(tree-item[^"]*)"([^>]*)>/g)) {
    const dataset = {};
    for (const attribute of tag[2].matchAll(/\sdata-([a-z0-9-]+)="([^"]*)"/g)) {
      const key = attribute[1].replace(/-([a-z0-9])/g, (_, letter) => letter.toUpperCase());
      dataset[key] = unescapeAttribute(attribute[2]);
    }
    found.push({ classes: tag[1].split(/\s+/), dataset });
  }
  return found;
}

function decide(html, expected) {
  const drawn = rows(html);
  if (drawn.length !== expected) {
    throw new Error(`expected ${expected} rows, the renderer wrote ${drawn.length}`);
  }
  return drawn.map(({ classes, dataset }) => {
    // The hover listener: target.closest(".tree-item.tree-file").
    const fileRow = classes.includes("tree-item") && classes.includes("tree-file");
    return {
      path: dataset.path,
      ext: dataset.ext ?? null,
      logicalExt: dataset.logicalExt ?? null,
      tipSize: dataset.tipSize ?? null,
      prefetch: fileRow && app.shouldPrefetchFile({ dataset }),
    };
  });
}

const input = JSON.parse(process.argv[2]);
const tree = input.tree ?? [];
const live = input.live ?? [];
const children = input.children ?? [];
if (tree.length > app.pageSize) {
  throw new Error(`more than one page of tree rows: ${tree.length}`);
}
const output = {
  cap: app.cap,
  tree: decide(app.renderTreeNodes(tree, false, { defaultExpandedPaths: new Set() }), tree.length),
  live: live.flatMap((entry) => decide(app._buildRowHtml(entry, {}), 1)),
  children: decide(app.renderContainerChildren(children, { level: 2 }), children.length),
};
process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);
