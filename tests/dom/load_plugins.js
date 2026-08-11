// JSDOM-shim plugin loader — runs the SDK + every plugin's index.js
// in a Node sandbox with minimal `window`/`document` mocks, then dumps
// the resulting view registry as JSON to stdout. Exercised by Python
// tests under tests/test_plugin_e2e_render.py.
//
// Usage:
//   node load_plugins.js <metabrowser_root> [extra_plugin_dir ...]
//
// Output: a single JSON line with shape:
//   {"plugins": ["markdown", "agent-log", ...],
//    "registrations": [{"kind": "markdown", "view": "rendered"}, ...],
//    "errors": [...]}
//
// We avoid jsdom on purpose — the SDK only needs `window`, plain
// console, and a tiny `document` stub; spinning up a real DOM would
// add ~150 MB of test deps for negligible gain.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function fail(msg) {
  process.stderr.write(`${msg}\n`);
  process.exit(1);
}

const args = process.argv.slice(2);
if (args.length < 1) {
  fail("usage: load_plugins.js <metabrowser_root> [extra_plugin_dir ...]");
}
const repoRoot = path.resolve(args[0]);
const extraDirs = args.slice(1).map((d) => path.resolve(d));

// ── Sandbox globals ───────────────────────────────────────────────

const errors = [];

const fakeDocument = {
  // Plugin index.js files only call this from inside their renderers,
  // not at registration time. Returning null is fine for the test.
  querySelector: () => null,
  querySelectorAll: () => [],
  addEventListener: () => {},
  createElement: () => ({ appendChild: () => {} }),
  documentElement: {},
};

const sandbox = {
  console: {
    log: (...a) => process.stderr.write(`[plugin:log] ${a.join(" ")}\n`),
    warn: (...a) => process.stderr.write(`[plugin:warn] ${a.join(" ")}\n`),
    error: (...a) => process.stderr.write(`[plugin:error] ${a.join(" ")}\n`),
  },
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  fetch: () => Promise.reject(new Error("fetch unavailable in shim")),
  Promise,
  Set,
  Map,
  // Mustache and Chart globals are referenced by some plugins. We don't
  // render in the shim; just stub them so module loading does not throw.
  Mustache: { render: (tpl) => tpl },
  Chart: () => {},
  // hljs is referenced from app.js's toggleEvent; not relevant here.
  hljs: { highlightElement: () => {} },
  HTMLCanvasElement: () => {},
};

// `window` is the global; many plugins call `(typeof window !== "undefined")`
// which evaluates against the sandbox global, so set both.
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.document = fakeDocument;

vm.createContext(sandbox);

function load(filepath, label) {
  try {
    const src = fs.readFileSync(filepath, "utf-8");
    vm.runInContext(src, sandbox, { filename: label });
  } catch (err) {
    errors.push({ file: label, error: String(err?.message ? err.message : err) });
  }
}

// ── 1. Plugin SDK ─────────────────────────────────────────────────

load(path.join(repoRoot, "src", "metabrowser", "static", "plugin_sdk.js"), "plugin_sdk.js");
load(
  path.join(repoRoot, "src", "metabrowser", "static", "filter_controls.js"),
  "filter_controls.js",
);
load(path.join(repoRoot, "src", "metabrowser", "static", "icons.js"), "icons.js");

if (!sandbox.metabrowser) {
  fail("plugin_sdk.js did not set window.metabrowser");
}

// ── 1b. Install a tracking Proxy on mb.builtins ───────────────────
//
// Enforces the "render-time-only namespace rule" from
// docs/plugins.md: a plugin's top-level IIFE MUST NOT
// dereference another plugin's mb.builtins.<other> namespace unless
// <other> has already loaded. Anything that violates the rule
// resolves to `undefined` during shim load, and we record the bad
// access so the Python test can fail.
//
// Reads inside renderView callbacks happen at render time (never
// triggered by this shim), so they pass through silently — exactly
// matching the rule.
const _builtinReads = []; // {plugin, key, hadValue}
let _currentLoadingPlugin = null;
const _builtinsTarget = {};
const _builtinsProxy = new Proxy(_builtinsTarget, {
  get(target, key) {
    if (_currentLoadingPlugin !== null && typeof key === "string" && key !== "constructor") {
      _builtinReads.push({
        plugin: _currentLoadingPlugin,
        key: key,
        hadValue: target[key] !== undefined,
      });
    }
    return target[key];
  },
  set(target, key, value) {
    target[key] = value;
    return true;
  },
  has(target, key) {
    return key in target;
  },
});
sandbox.metabrowser.builtins = _builtinsProxy;

// Wrap the existing load() so we know which plugin is executing.
const _rawLoad = load;
function loadPlugin(filepath, label, pluginName) {
  _currentLoadingPlugin = pluginName;
  try {
    _rawLoad(filepath, label);
  } finally {
    _currentLoadingPlugin = null;
  }
}

// Cheap manifest scan: pulls extra_scripts entries out of a manifest.toml
// without dragging in a full TOML parser. Same approach as
// enumerateFromManifests below — line-by-line regex match.
function _extraScriptsFromManifest(manifestPath) {
  if (!fs.existsSync(manifestPath)) {
    return [];
  }
  const text = fs.readFileSync(manifestPath, "utf-8");
  const out = [];
  let inPluginSection = false;
  let inExtraScriptsArray = false;
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (trimmed.startsWith("[plugin]")) {
      inPluginSection = true;
      continue;
    }
    if (trimmed.startsWith("[")) {
      inPluginSection = false;
      inExtraScriptsArray = false;
      continue;
    }
    if (!inPluginSection) {
      continue;
    }
    // Inline array form: extra_scripts = ["a.js", "b.js"]
    const inlineMatch = trimmed.match(/^extra_scripts\s*=\s*\[(.*)\]/);
    if (inlineMatch) {
      const inner = inlineMatch[1];
      const items = inner.match(/"([^"]+)"/g) || [];
      for (const it of items) {
        out.push(it.slice(1, -1));
      }
      continue;
    }
    // Multiline array start
    if (/^extra_scripts\s*=\s*\[/.test(trimmed)) {
      inExtraScriptsArray = true;
      continue;
    }
    if (inExtraScriptsArray) {
      if (trimmed.startsWith("]")) {
        inExtraScriptsArray = false;
        continue;
      }
      const m = trimmed.match(/"([^"]+)"/);
      if (m) {
        out.push(m[1]);
      }
    }
  }
  return out;
}

// ── 2. Built-in plugins (alphabetical, matching discovery order) ──

const builtinRoot = path.join(repoRoot, "src", "metabrowser", "builtin_plugins");
const builtinNames = fs
  .readdirSync(builtinRoot)
  .filter((name) => {
    const stat = fs.statSync(path.join(builtinRoot, name));
    return stat.isDirectory() && !name.startsWith("_") && !name.startsWith(".");
  })
  .sort();

const loadedPlugins = [];

for (const name of builtinNames) {
  const indexPath = path.join(builtinRoot, name, "index.js");
  const manifestPath = path.join(builtinRoot, name, "manifest.toml");
  if (!fs.existsSync(indexPath) || !fs.existsSync(manifestPath)) {
    continue;
  }
  // Load any extra_scripts the manifest declares (in order) BEFORE
  // index.js — the shell emits <script> tags in the same order, so
  // index.js can rely on the helpers they expose.
  for (const extra of _extraScriptsFromManifest(manifestPath)) {
    const extraPath = path.join(builtinRoot, name, extra);
    if (!fs.existsSync(extraPath)) {
      continue;
    }
    loadPlugin(extraPath, `builtin/${name}/${extra}`, name);
  }
  loadPlugin(indexPath, `builtin/${name}/index.js`, name);
  loadedPlugins.push(name);
}

// ── 3. Extra dirs (--plugins-dir / METABROWSER_PLUGINS_DIRS) ──────

for (const dir of extraDirs) {
  if (!fs.existsSync(dir) || !fs.statSync(dir).isDirectory()) {
    continue;
  }
  const subdirs = fs.readdirSync(dir).sort();
  for (const sub of subdirs) {
    const subPath = path.join(dir, sub);
    if (!fs.statSync(subPath).isDirectory()) {
      continue;
    }
    const indexPath = path.join(subPath, "index.js");
    const manifestPath = path.join(subPath, "manifest.toml");
    if (!fs.existsSync(indexPath) || !fs.existsSync(manifestPath)) {
      continue;
    }
    loadPlugin(indexPath, `extra/${sub}/index.js`, sub);
    loadedPlugins.push(sub);
  }
}

// ── 4. Inspect the view registry ──────────────────────────────────

const mb = sandbox.metabrowser;
const registrations = [];
// listViewsForKind iterates per-kind; we don't have the kind list,
// so dig into _viewRegistry indirectly via the SDK API. Unfortunately
// the registry is a private Map captured in the SDK closure; it's
// not exposed on `mb`. We probe by enumerating known kinds + view ids
// from the manifests on disk.
function enumerateFromManifests() {
  function readManifest(filepath) {
    const text = fs.readFileSync(filepath, "utf-8");
    const kinds = new Set();
    const views = [];
    let currentSection = null;
    let _pluginKind = null;
    for (const line of text.split("\n")) {
      const trimmed = line.trim();
      if (trimmed.startsWith("[[kind]]")) {
        currentSection = "kind";
        _pluginKind = null;
      } else if (trimmed.startsWith("[[view]]")) {
        currentSection = "view";
      } else if (trimmed.startsWith("[")) {
        currentSection = null;
      } else {
        const m = trimmed.match(/^id\s*=\s*"([^"]+)"/);
        const k = trimmed.match(/^kind\s*=\s*"([^"]+)"/);
        if (currentSection === "kind" && m) {
          kinds.add(m[1]);
        }
        if (currentSection === "view") {
          if (k) {
            views.push({ kind: k[1] });
          }
          if (m && views.length > 0) {
            views[views.length - 1].id = m[1];
          }
        }
      }
    }
    return { kinds: Array.from(kinds), views };
  }

  const manifestPaths = [];
  for (const name of builtinNames) {
    const p = path.join(builtinRoot, name, "manifest.toml");
    if (fs.existsSync(p)) {
      manifestPaths.push(p);
    }
  }
  const allViews = [];
  for (const m of manifestPaths) {
    const parsed = readManifest(m);
    allViews.push(...parsed.views.filter((v) => v.kind && v.id));
  }
  return allViews;
}

const declaredViews = enumerateFromManifests();
for (const v of declaredViews) {
  const reg = mb.getRegisteredView(v.kind, v.id);
  registrations.push({
    kind: v.kind,
    view: v.id,
    registered: !!reg,
  });
}

// Violations of the render-time-only namespace rule: a plugin's top-level
// IIFE read mb.builtins.<key> and got undefined. Anything that resolved
// to a real value (e.g. unknown_jsonl reading agentLog after agent_log
// loaded) is fine — load-order happens to satisfy the read. The foot-gun
// is the undefined case, so flag only that.
const namespaceViolations = _builtinReads
  .filter((r) => !r.hadValue)
  .map((r) => ({ plugin: r.plugin, key: r.key }));

process.stdout.write(
  `${JSON.stringify({
    plugins: loadedPlugins,
    registrations: registrations,
    errors: errors,
    namespace_violations: namespaceViolations,
  })}\n`,
);
