// JSDOM-shim view renderer — runs the SDK + every plugin's index.js,
// then invokes a registered renderer with a synthetic `/api/file`
// payload and prints the resulting innerHTML to stdout. Used by
// Python tests use this helper to verify
// per-view render behaviour without spinning up a real browser.
//
// Usage:
//   node render_view.js <metabrowser_root> <kind> <view_id> '<json_payload>'
//
// Output: the container's innerHTML on stdout.
//
// Sandbox note: same minimal mocks as load_plugins.js; just enough
// for module-load + a synchronous render call.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function fail(msg) {
  process.stderr.write(`${msg}\n`);
  process.exit(1);
}

const args = process.argv.slice(2);
if (args.length !== 4) {
  fail("usage: render_view.js <repo_root> <kind> <view_id> '<json_payload>'");
}
const [repoRoot, kind, viewId, payloadStr] = args;

let payload;
try {
  payload = JSON.parse(payloadStr);
} catch (err) {
  fail(`payload JSON parse error: ${err.message}`);
}

// ── Sandbox ────────────────────────────────────────────────────────

const fakeContainer = {
  _innerHTML: "",
  set innerHTML(v) {
    this._innerHTML = v;
  },
  get innerHTML() {
    return this._innerHTML;
  },
  appendChild() {},
  querySelector: () => null,
  querySelectorAll: () => [],
};

const sandbox = {
  console: {
    log: (...a) => process.stderr.write(`[plugin:log] ${a.join(" ")}\n`),
    warn: (...a) => process.stderr.write(`[plugin:warn] ${a.join(" ")}\n`),
    error: (...a) => process.stderr.write(`[plugin:error] ${a.join(" ")}\n`),
  },
  setTimeout,
  clearTimeout,
  Promise,
  Set,
  Map,
  fetch: () => Promise.reject(new Error("fetch unavailable in shim")),
  Mustache: { render: (tpl) => tpl },
  Chart: () => {},
  hljs: { highlightElement: () => {} },
  HTMLCanvasElement: () => {},
  document: {
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
    createElement: () => fakeContainer,
    documentElement: {},
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);

function load(filepath, label) {
  const src = fs.readFileSync(filepath, "utf-8");
  vm.runInContext(src, sandbox, { filename: label });
}

load(path.join(repoRoot, "src/metabrowser/static/navigation.js"), "navigation.js");
load(path.join(repoRoot, "src/metabrowser/static/plugin_sdk.js"), "plugin_sdk.js");
load(path.join(repoRoot, "src/metabrowser/static/filter_controls.js"), "filter_controls.js");
load(path.join(repoRoot, "src/metabrowser/static/icons.js"), "icons.js");

const builtinRoot = path.join(repoRoot, "src/metabrowser/builtin_plugins");
const builtinNames = fs
  .readdirSync(builtinRoot)
  .filter((n) => fs.statSync(path.join(builtinRoot, n)).isDirectory() && !n.startsWith("_"))
  .sort();
for (const name of builtinNames) {
  const indexPath = path.join(builtinRoot, name, "index.js");
  if (fs.existsSync(indexPath)) {
    load(indexPath, `builtin/${name}/index.js`);
  }
}

const view = sandbox.metabrowser.getRegisteredView(kind, viewId);
if (!view) {
  fail(`no view registered for (${kind}, ${viewId})`);
}

const ctx = {
  path: payload.path || "",
  kind: payload.kind || kind,
  ext: payload.ext || "",
  size: payload.size || 0,
  frontmatter: payload.frontmatter || {},
  body: payload.content || "",
  raw: payload,
};

const result = view.render(fakeContainer, ctx);
if (result && typeof result.then === "function") {
  result
    .then(() => process.stdout.write(fakeContainer.innerHTML))
    .catch((err) => fail(`render error: ${err.message}`));
} else {
  process.stdout.write(fakeContainer.innerHTML);
}
