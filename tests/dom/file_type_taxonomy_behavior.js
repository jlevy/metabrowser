const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(__dirname, "../..");
const fallbackRegistry = {
  schema: "file-type-registry-v1",
  schema_version: 1,
  revision: 1,
  fingerprint: "fixture-registry",
  max_extension_components: 2,
  groups: [
    { id: "docs", label: "Docs", order: 10 },
    { id: "code", label: "Code", order: 20 },
    { id: "data", label: "Data", order: 30 },
    { id: "other", label: "Other", order: 40 },
  ],
  families: [
    {
      id: "javascript",
      label: "JavaScript",
      group_id: "code",
      order: 10,
      extensions: [".js", ".mjs", ".cjs", ".jsx"],
    },
    { id: "typescript", label: "TypeScript", group_id: "code", order: 20, extensions: [".ts"] },
    { id: "yaml", label: "YAML", group_id: "data", order: 10, extensions: [".yaml", ".yml"] },
  ],
  kinds: [
    {
      id: "javascript",
      family_id: "javascript",
      group_id: "code",
      content_family: "code",
      extensions: [".js", ".mjs", ".cjs", ".jsx"],
      filenames: [],
      shebangs: [],
      priority: 100,
    },
    {
      id: "typescript",
      family_id: "typescript",
      group_id: "code",
      content_family: "code",
      extensions: [".ts"],
      filenames: [],
      shebangs: [],
      priority: 100,
    },
    {
      id: "yaml",
      family_id: "yaml",
      group_id: "data",
      content_family: "data",
      extensions: [".yaml", ".yml"],
      filenames: [],
      shebangs: [],
      priority: 100,
    },
    {
      id: "docs-file",
      family_id: null,
      group_id: "docs",
      content_family: "prose",
      extensions: [],
      filenames: ["readme"],
      shebangs: [],
      priority: 100,
    },
    {
      id: "code-extra",
      family_id: null,
      group_id: "code",
      content_family: "code",
      extensions: [".m"],
      filenames: ["makefile"],
      shebangs: [],
      priority: 100,
    },
    {
      id: "data-extra",
      family_id: null,
      group_id: "data",
      content_family: "data",
      extensions: [".db"],
      filenames: [],
      shebangs: [],
      priority: 100,
    },
  ],
};
const registry = process.argv[2]
  ? JSON.parse(fs.readFileSync(path.resolve(process.argv[2]), "utf8"))
  : fallbackRegistry;
const sandbox = {
  console,
  globalThis: null,
  METABROWSER_SETTINGS: { FILE_TYPE_REGISTRY: registry },
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
if (
  runtime.groups.map((group) => group.id).join(",") !==
  registry.groups.map((group) => group.id).join(",")
) {
  throw new Error("registry group order was not preserved");
}
if (runtime.revision !== registry.revision || runtime.fingerprint !== registry.fingerprint) {
  throw new Error("registry identity was not preserved");
}
if (process.argv[3]) {
  const corpus = JSON.parse(fs.readFileSync(path.resolve(process.argv[3]), "utf8"));
  for (const item of corpus.metadata_cases) {
    const actual = runtime.classify(item.name, item.logical_extension || "");
    const expected = item.expected;
    const pairs = {
      logicalExtension: expected.logical_extension,
      canonicalExtension: expected.canonical_extension,
      kindId: expected.kind_id,
      familyId: expected.family_id,
      groupId: expected.group_id,
      contentFamily: expected.content_family,
      detectionSource: expected.detection_source,
      confidence: expected.confidence,
    };
    for (const [key, expectedValue] of Object.entries(pairs)) {
      if (actual[key] !== expectedValue) {
        throw new Error(
          `conformance mismatch for ${item.name} ${key}: ${actual[key]} !== ${expectedValue}`,
        );
      }
    }
  }
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

const signedOrderRegistry = JSON.parse(JSON.stringify(registry));
signedOrderRegistry.groups[0].order = -10;
signedOrderRegistry.kinds[0].priority = -1;
const signedOrderSandbox = {
  console,
  globalThis: null,
  METABROWSER_SETTINGS: { FILE_TYPE_REGISTRY: signedOrderRegistry },
};
signedOrderSandbox.globalThis = signedOrderSandbox;
signedOrderSandbox.window = signedOrderSandbox;
vm.createContext(signedOrderSandbox);
vm.runInContext(source, signedOrderSandbox, { filename: "file_type_taxonomy.js" });
if (!signedOrderSandbox.MetabrowserFileTypeTaxonomy) {
  throw new Error("signed registry order and priority values were rejected");
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
