// Behavioral check for app.js treeNodeDisplayName, the shell's tree-row name.
//
// The two served subjects publish a node's name in two different spellings. A
// filesystem node carries an inventory identity, where a literal percent is
// escaped as %25, and the shell undoes that with displayPath. A Git pin sends
// the display basename the server already decoded from the tree, so decoding
// it again reads `g1-data` as a wire token and rewrites `50%25-off.md`.
//
// The helper and its source-kind predicate are lifted out of app.js and run
// against the real navigation module, so this exercises the production code
// rather than asserting on its text. A grep then checks that every tree-row
// name site still routes through the helper, because a half-reverted call site
// would pass the behavioral half on its own.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2] || path.join(__dirname, "../.."));
const staticDir = path.join(repoRoot, "src/metabrowser/static");
const appSource = fs.readFileSync(path.join(staticDir, "app.js"), "utf-8");

const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

function equal(name, actual, expected) {
  check(
    name,
    actual === expected,
    `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
  );
}

function lift(name) {
  const match = appSource.match(new RegExp(`function ${name}\\([^)]*\\) \\{[\\s\\S]*?\\n\\}`));
  if (!match) {
    failures.push(`${name} not found in app.js`);
    return "";
  }
  return match[0];
}

const sandbox = {
  console,
  Object,
  Array,
  String,
  Error,
  TypeError,
  URIError,
  atob,
  btoa,
  TextDecoder,
  Uint8Array,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

const navigationPath = path.join(staticDir, "navigation.js");
vm.runInContext(fs.readFileSync(navigationPath, "utf-8"), sandbox, { filename: navigationPath });

const helpers = `${lift("isGitRevisionSource")}\n${lift("treeNodeDisplayName")}`;
vm.runInContext(helpers, sandbox, { filename: "tree-node-name.js" });
const treeNodeDisplayName = sandbox.treeNodeDisplayName;

if (typeof treeNodeDisplayName !== "function") {
  failures.push("treeNodeDisplayName: tree rows have no source-kind-aware name helper");
} else {
  // A filesystem tree publishes inventory identities, so the escaping stands.
  sandbox.METABROWSER_SOURCE_KIND = "filesystem";
  equal("filesystem percent name unescapes", treeNodeDisplayName("50%25-off.md"), "50%-off.md");
  equal(
    "filesystem g1-looking name stays literal",
    treeNodeDisplayName("g1-UkVBRE1FLm1k"),
    "g1-UkVBRE1FLm1k",
  );
  equal("filesystem plain name is unchanged", treeNodeDisplayName("README.md"), "README.md");
  equal("a missing name renders empty", treeNodeDisplayName(undefined), "");

  // A Git pin publishes display basenames, so nothing is left to decode.
  sandbox.METABROWSER_SOURCE_KIND = "git_revision";
  equal("pinned percent name stays literal", treeNodeDisplayName("50%25-off.md"), "50%25-off.md");
  equal("pinned g1- directory stays literal", treeNodeDisplayName("g1-data"), "g1-data");
  equal("pinned g1- file stays literal", treeNodeDisplayName("g1-notes.md"), "g1-notes.md");
  equal("pinned plain name is unchanged", treeNodeDisplayName("README.md"), "README.md");
  equal("a missing pinned name renders empty", treeNodeDisplayName(undefined), "");
}

// What decoding a decoded name would have produced, so the cost of losing the
// guard is written down rather than inferred.
equal(
  "decoding a pinned display name again corrupts it",
  sandbox.MetabrowserNavigationRoute.displayPath("g1-data", "git_revision"),
  "u�Z",
);

const renderStart = appSource.indexOf("function renderTreeNodes(");
const renderEnd = appSource.indexOf("// ── Lazy subtree loading");
check("renderTreeNodes bounds located", renderStart >= 0 && renderEnd > renderStart);
const render = appSource.slice(renderStart, renderEnd);
const nameSites = render.match(/displayPath\(node\.name\)/g) || [];
check(
  "no tree-row name bypasses the helper",
  nameSites.length === 0,
  `${nameSites.length} site(s) still call displayPath(node.name)`,
);
check(
  "tree rows render through the helper",
  (render.match(/treeNodeDisplayName\(node\.name\)/g) || []).length >= 6,
  "expected every folder, symlink, and file row to use treeNodeDisplayName",
);

if (failures.length) {
  console.error(`tree node name FAILURES:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log("tree node name OK");
