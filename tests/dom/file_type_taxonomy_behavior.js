const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const fallbackTaxonomy = {
  categories: [
    { id: "docs", label: "Docs", extra_values: ["readme"] },
    { id: "code", label: "Code", extra_values: [".m", "makefile"] },
    { id: "data", label: "Data", extra_values: [".db"] },
  ],
  families: [
    {
      id: "javascript",
      label: "JavaScript",
      category: "code",
      extensions: [".js", ".mjs", ".cjs", ".jsx"],
    },
    { id: "typescript", label: "TypeScript", category: "code", extensions: [".ts"] },
    { id: "yaml", label: "YAML", category: "data", extensions: [".yaml", ".yml"] },
  ],
};
const taxonomy = process.argv[2]
  ? JSON.parse(fs.readFileSync(path.resolve(process.argv[2]), "utf8"))
  : fallbackTaxonomy;
const sandbox = {
  console,
  globalThis: null,
  METABROWSER_SETTINGS: { FILE_TYPE_TAXONOMY: taxonomy },
};
sandbox.globalThis = sandbox;
sandbox.window = sandbox;
vm.createContext(sandbox);
const source = fs.readFileSync(
  path.join(repoRoot, "src/metabrowser/static/file_type_taxonomy.js"),
  "utf8",
);
vm.runInContext(source, sandbox, { filename: "file_type_taxonomy.js" });

const runtime = sandbox.MetabrowserFileTypeTaxonomy;
if (!runtime) {
  throw new Error("taxonomy runtime was not installed");
}
const javascript = runtime.matchExtension("min.js");
if (javascript?.family.id !== "javascript" || javascript.canonicalExtension !== ".js") {
  throw new Error("compound JavaScript extension was not canonicalized");
}
if (runtime.canonicalExtension(".d.ts") !== ".ts") {
  throw new Error("longest suffix matching diverged for TypeScript");
}
if (runtime.categoryForFile("README", "") !== "docs") {
  throw new Error("whole-filename category matching failed");
}
if (runtime.categoryForFile("module.m", ".m") !== "code") {
  throw new Error("raw category-only extension matching failed");
}
if (runtime.distributionKeyForExtension(".min.js") !== "family:javascript") {
  throw new Error("family distribution key was not stable");
}
if (runtime.canonicalExtension(".unknown") !== ".unknown") {
  throw new Error("unknown extension did not remain raw");
}
if (!Object.isFrozen(runtime) || !Object.isFrozen(runtime.families[0])) {
  throw new Error("taxonomy runtime must be immutable");
}

sandbox.document = { addEventListener() {}, cookie: "" };
for (const filename of [
  "request_error.js",
  "formatters.js",
  "inventory_scope.js",
  "resource_context.js",
  "view_state.js",
  "plugin_sdk.js",
]) {
  const moduleSource = fs.readFileSync(
    path.join(repoRoot, "src/metabrowser/static", filename),
    "utf8",
  );
  vm.runInContext(moduleSource, sandbox, { filename });
}
if (sandbox.metabrowser.fileTypes !== runtime) {
  throw new Error("plugin SDK did not expose the immutable taxonomy runtime");
}

console.log("OK file type taxonomy");
