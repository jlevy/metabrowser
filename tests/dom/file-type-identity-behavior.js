// One family, one icon, one colour — wherever a filename appears.
//
// This is the assertion neither taxonomy could fail on its own. The tree's
// hand-maintained table and the rollup registry were each internally
// consistent and disagreed with each other, so a test that asked either one
// what it thought passed while `.js` and `.jsx` rendered differently and
// `.json`, `.toml` and `.yaml` rendered the same. What has to be pinned is the
// RELATION between them, which is what this file does.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const registry = JSON.parse(
  fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/data/file-rollup-format/recommended-file-types.json"),
    "utf8",
  ),
);

// The colours the server resolves per theme. Only the keys and the pairing
// matter here; the palette's own separation is checked by
// devtools/check_file_type_colors.py.
const distributionColors = registry.families.map((family) => ({
  key: `family:${family.id}`,
  light: `oklch(59% 0.15 ${family.hue})`,
  dark: `oklch(72% 0.13 ${family.hue})`,
}));

const sandbox = {
  console,
  globalThis: null,
  METABROWSER_SETTINGS: {
    FILE_TYPE_REGISTRY: registry,
    DISTRIBUTION_COLORS: distributionColors,
  },
  MetabrowserIcons: new Proxy({}, { get: (_target, name) => `<svg data-icon="${String(name)}">` }),
};
sandbox.globalThis = sandbox;
sandbox.window = sandbox;
vm.createContext(sandbox);

for (const filename of ["file-type-taxonomy.js"]) {
  vm.runInContext(
    fs.readFileSync(path.join(repoRoot, "src/metabrowser/static", filename), "utf8"),
    sandbox,
    { filename },
  );
}

// app.js is the shell and will not evaluate headlessly, so lift the block under
// test. Bounded by its own markers, so a rename fails loudly here rather than
// silently testing nothing.
const appSource = fs.readFileSync(path.join(repoRoot, "src/metabrowser/static/app.js"), "utf8");
const start = appSource.indexOf(
  "// The file tree's icon and colour, resolved through the rollup registry.",
);
const end = appSource.indexOf("// The application shell owns the catalog and search composition.");
if (start < 0 || end < 0 || end <= start) {
  throw new Error("file-type identity block not found in app.js");
}
vm.runInContext(`var ICON_SVG = MetabrowserIcons;\n${appSource.slice(start, end)}`, sandbox, {
  filename: "app.js#file-type-identity",
});

const fileTypes = sandbox.MetabrowserFileTypes;
if (!fileTypes) {
  throw new Error("MetabrowserFileTypes was not installed");
}

const failures = [];
const iconOf = (name) => fileTypes.iconFor(name).svg;
const styleOf = (name) => fileTypes.iconFor(name).style;

// One family is one identity. `.mjs`, `.cjs` and `.jsx` were absent from the
// old table entirely and fell through to the generic file icon with no colour.
const javascript = [".js", ".mjs", ".cjs", ".jsx"].map((ext) => `module${ext}`);
const jsIcons = new Set(javascript.map(iconOf));
const jsStyles = new Set(javascript.map(styleOf));
if (jsIcons.size !== 1 || jsStyles.size !== 1) {
  failures.push(
    `JavaScript extensions must share one icon and one colour; got ${jsIcons.size} icons, ${jsStyles.size} colours`,
  );
}
if ([...jsStyles][0] === "") {
  failures.push("JavaScript resolved to no colour at all");
}

// Different families are different colours. All three were `ft-yaml` before.
const dataStyles = [".json", ".toml", ".yaml"].map((ext) => styleOf(`config${ext}`));
if (new Set(dataStyles).size !== 3) {
  failures.push(`json/toml/yaml must be three colours; got ${new Set(dataStyles).size}`);
}

// Both were `ft-code` before, so the tree said Python and TypeScript were the
// same thing while the bars beside it said otherwise.
if (styleOf("a.py") === styleOf("a.ts")) {
  failures.push("python and typescript must not share a colour");
}

// The invariant the epic exists to restore: a row's colour is the colour the
// distribution bars give that family, from the same list.
const pythonFamily = fileTypes.familyFor("a.py");
const pythonDeclared = distributionColors.find((entry) => entry.key === `family:${pythonFamily}`);
if (!pythonDeclared || !styleOf("a.py").includes(pythonDeclared.light)) {
  failures.push("a row's colour must be the family's declared distribution colour");
}

// Compound extensions resolve to the family, not to their tail.
if (iconOf("bundle.min.js") !== iconOf("module.js")) {
  failures.push("compound extensions must resolve to the same family");
}

// An extension the registry does not claim gets the generic shape and no
// colour, rather than an invented one.
const unknown = fileTypes.iconFor("mystery.zzzz");
if (unknown.svg !== sandbox.MetabrowserIcons.file || unknown.style !== "" || unknown.cls !== "") {
  failures.push("an unclaimed extension must render the generic icon with no colour");
}

// Icon is the major type: a family without its own icon takes its group's.
const groupIcon = new Map(registry.groups.map((group) => [group.id, group.icon]));
const plainCode = registry.families.find(
  (family) => family.group_id === "code" && !family.icon && family.extensions.length,
);
if (plainCode) {
  const expected = sandbox.MetabrowserIcons[groupIcon.get("code")];
  if (iconOf(`file${plainCode.extensions[0]}`) !== expected) {
    failures.push(`${plainCode.id} must inherit the code group's icon`);
  }
}

if (failures.length) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exitCode = 1;
} else {
  console.log("OK file type identity");
}
