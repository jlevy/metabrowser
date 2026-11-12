// KPress asset-loading shim — executes plugin-sdk.js in the same small
// Node vm sandbox style as load-plugins.js, then exercises
// mb.fetchKpressRender against a fake /api/kpress/render response.
//
// Usage:
//   node kpress-asset-loading.js <repo_root>
//
// Output: a single JSON line with the requested render URL and captured
// document.head appends.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function fail(msg) {
  process.stderr.write(`${msg}\n`);
  process.exit(1);
}

function assert(condition, msg) {
  if (!condition) {
    fail(msg);
  }
}

const args = process.argv.slice(2);
if (args.length !== 1) {
  fail("usage: kpress-asset-loading.js <repo_root>");
}

const repoRoot = path.resolve(args[0]);
const appended = [];
const removed = [];
const requestedUrls = [];

function makeElement(tagName) {
  const attrs = {};
  return {
    tagName: tagName.toUpperCase(),
    attrs,
    rel: "",
    href: "",
    src: "",
    type: "",
    async: true,
    textContent: "",
    onload: null,
    onerror: null,
    setAttribute(name, value) {
      attrs[name] = String(value);
    },
    getAttribute(name) {
      return Object.hasOwn(attrs, name) ? attrs[name] : null;
    },
    remove() {
      removed.push(`${this.rel || "script"}:${this.href || this.src}`);
    },
  };
}

// While holding, an appended stylesheet or script waits to load until released, to
// observe what is in flight at once.
let holding = false;
/** @type {Map<string, () => void>} */
const held = new Map();

const fakeParent = {
  appendChild(element) {
    appended.push({
      tagName: element.tagName,
      attrs: { ...element.attrs },
      rel: element.rel,
      href: element.href,
      src: element.src,
      type: element.type,
      async: element.async,
      textContent: element.textContent,
    });
    if (holding && typeof element.onload === "function") {
      held.set(element.href || element.src, () => element.onload());
    } else if (typeof element.onload === "function") {
      element.onload();
    }
    return element;
  },
};

const sandbox = {
  console: {
    log: (...a) => process.stderr.write(`[sdk:log] ${a.join(" ")}\n`),
    warn: (...a) => process.stderr.write(`[sdk:warn] ${a.join(" ")}\n`),
    error: (...a) => process.stderr.write(`[sdk:error] ${a.join(" ")}\n`),
  },
  setTimeout,
  clearTimeout,
  Promise,
  Set,
  Map,
  URL,
  location: { origin: "http://localhost" },
  document: {
    head: fakeParent,
    body: fakeParent,
    createElement: makeElement,
    documentElement: {
      getAttribute(name) {
        if (name === "data-theme-mode") {
          return "system";
        }
        if (name === "data-theme") {
          return "dark";
        }
        return null;
      },
    },
  },
  fetch: async (url) => {
    requestedUrls.push(url);
    return {
      ok: true,
      status: 200,
      json: async () => ({
        type: "kpress-rendered-document",
        html: '<article class="kpress-doc">Doc</article>',
        profile: "document",
        printable: true,
        diagnostics: [],
        assets: {
          schema_version: "kpress-asset-manifest-v2",
          assets: [
            {
              id: "css/document.css",
              path: "css/document.css",
              public_url: "/kpress-static/v0.3.0/css/document.css",
              entry_point: true,
              loading: "stylesheet",
            },
            {
              id: "js/runtime.js",
              path: "js/runtime.js",
              public_url: "/kpress-static/v0.3.0/js/runtime.js",
              entry_point: false,
              loading: "module",
            },
            {
              id: "js/theme.js",
              path: "js/theme.js",
              public_url: "/kpress-static/v0.3.0/js/theme.js",
              entry_point: true,
              loading: "module",
            },
            {
              id: "js/code-copy.js",
              path: "js/code-copy.js",
              public_url: "/kpress-static/v0.3.0/js/code-copy.js",
              entry_point: true,
              loading: "module",
            },
            {
              id: "js/toc.js",
              path: "js/toc.js",
              public_url: "/kpress-static/v0.3.0/js/toc.js",
              entry_point: true,
              loading: "module",
            },
            {
              id: "katex/katex.min.js",
              path: "katex/katex.min.js",
              public_url: "/kpress-static/v0.3.0/katex/katex.min.js",
              entry_point: true,
              loading: "classic",
            },
          ],
          // toc.js is loaded via dynamic import (so the host can call its
          // initKpressToc per render) and is never appended as a script tag.
          // Dependency-only runtime.js also receives no tag.
          import_map: {
            "/kpress-static/js/runtime.js": "/kpress-static/v0.3.0/js/runtime.js",
          },
        },
      }),
    };
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);

for (const filename of [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
]) {
  const dependencyPath = path.join(repoRoot, "src", "metabrowser", "static", filename);
  vm.runInContext(fs.readFileSync(dependencyPath, "utf-8"), sandbox, { filename });
}
const sdkPath = path.join(repoRoot, "src", "metabrowser", "static", "plugin-sdk.js");
vm.runInContext(fs.readFileSync(sdkPath, "utf-8"), sandbox, {
  filename: "plugin-sdk.js",
});
// The KPress loading is a view helper, in the SDK's on-demand half, which is on the page
// before any plugin's code runs.
const viewsPath = path.join(repoRoot, "src", "metabrowser", "static", "plugin-sdk-views.js");
vm.runInContext(fs.readFileSync(viewsPath, "utf-8"), sandbox, {
  filename: "plugin-sdk-views.js",
});

if (!sandbox.metabrowser || typeof sandbox.metabrowser.fetchKpressRender !== "function") {
  fail("the SDK did not expose metabrowser.fetchKpressRender");
}

sandbox.metabrowser
  .fetchKpressRender({ path: "docs/index.md" }, "rendered", { profile: "document" })
  .then((payload) => {
    assert(requestedUrls.length === 1, `expected one render request, got ${requestedUrls.length}`);

    const requested = new URL(requestedUrls[0]);
    assert(requested.pathname === "/api/kpress/render", "bad KPress render path");
    assert(requested.searchParams.get("path") === "docs/index.md", "bad path param");
    assert(requested.searchParams.get("view") === "rendered", "bad view param");
    assert(requested.searchParams.get("profile") === "document", "bad profile param");
    assert(!requested.searchParams.has("theme_mode"), "theme_mode must stay host-local");
    assert(!requested.searchParams.has("resolved_theme"), "resolved_theme must stay host-local");

    const links = appended.filter((el) => el.tagName === "LINK" && el.rel === "stylesheet");
    const scripts = appended.filter((el) => el.tagName === "SCRIPT");
    assert(links.length === 1, `expected one stylesheet, got ${links.length}`);
    // Every script entry point, toc.js included, is fetched beside the stylesheet.
    const preloads = appended
      .filter((el) => el.tagName === "LINK" && el.rel !== "stylesheet")
      .map((el) => `${el.rel}:${el.href}`);
    assert(
      JSON.stringify(preloads) ===
        JSON.stringify([
          "modulepreload:/kpress-static/v0.3.0/js/theme.js",
          "modulepreload:/kpress-static/v0.3.0/js/code-copy.js",
          "modulepreload:/kpress-static/v0.3.0/js/toc.js",
          "preload:/kpress-static/v0.3.0/katex/katex.min.js",
        ]),
      `unexpected preloads: ${preloads.join(", ")}`,
    );
    assert(links[0].rel === "stylesheet", "stylesheet rel was not set");
    assert(
      links[0].href === "/kpress-static/v0.3.0/css/document.css",
      "stylesheet href was not set",
    );
    assert(
      Object.hasOwn(links[0].attrs, "data-kpress-asset"),
      "stylesheet missing data-kpress-asset marker",
    );

    const importMaps = scripts.filter((el) => el.type === "importmap");
    assert(importMaps.length === 1, `expected one import map, got ${importMaps.length}`);
    const importMap = JSON.parse(importMaps[0].textContent);
    assert(
      importMap.imports["/kpress-static/js/runtime.js"] === "/kpress-static/v0.3.0/js/runtime.js",
      "KPress import map was not installed",
    );

    // Manifest entry points are authoritative. toc.js is loaded via dynamic
    // import so the host can drive initKpressToc per render; runtime.js is a
    // dependency-only entry resolved by module imports.
    const loadedScripts = scripts.filter((el) => el.type !== "importmap");
    const scriptSrcs = loadedScripts.map((el) => el.src);
    assert(
      loadedScripts.length === 3,
      `expected two modules + classic entry point, got ${loadedScripts.length}: ${scriptSrcs.join(", ")}`,
    );
    assert(
      scriptSrcs[0] === "/kpress-static/v0.3.0/js/theme.js",
      `expected declared theme.js to load, got ${scriptSrcs[0]}`,
    );
    assert(loadedScripts[0].type === "module", "theme.js was not loaded as a module");
    assert(
      scriptSrcs[1] === "/kpress-static/v0.3.0/js/code-copy.js",
      `expected code-copy.js to load, got ${scriptSrcs[1]}`,
    );
    assert(loadedScripts[1].type === "module", "code-copy.js was not loaded as a module");
    assert(
      scriptSrcs[2] === "/kpress-static/v0.3.0/katex/katex.min.js",
      `expected classic KaTeX script to load, got ${scriptSrcs[2]}`,
    );
    assert(
      loadedScripts[2].type === "text/javascript",
      "classic KPress entry point was loaded as a module",
    );
    assert(
      !scriptSrcs.some((src) => src.endsWith("/toc.js") || src.endsWith("/runtime.js")),
      `toc/dependency scripts must not be appended: ${scriptSrcs.join(", ")}`,
    );
    assert(
      appended.indexOf(importMaps[0]) < appended.indexOf(loadedScripts[0]),
      "import map must be installed before module entry points",
    );
    for (const script of loadedScripts) {
      assert(script.async === false, `${script.src} should preserve script execution order`);
      assert(
        Object.hasOwn(script.attrs, "data-kpress-asset"),
        `${script.src} missing data-kpress-asset marker`,
      );
    }

    const rendered = appended.slice();
    return heldLoad().then((held) => {
      process.stdout.write(
        `${JSON.stringify({
          requestedUrl: requestedUrls[0],
          appended: rendered,
          held,
          html: payload.html,
        })}\n`,
      );
    });
  })
  .catch((err) => fail(err?.stack ? err.stack : String(err)));

/** What is in flight at each step of a load whose stylesheets and scripts are held. */
async function heldLoad() {
  const tick = () => new Promise((resolve) => setImmediate(resolve));
  const since = appended.length;
  const removedSince = removed.length;
  const fresh = () =>
    appended
      .slice(since)
      .map((el) => `${el.tagName === "LINK" ? el.rel : "script"}:${el.href || el.src}`);
  holding = true;
  const done = sandbox.metabrowser.loadKpressAssets({
    schema_version: "kpress-asset-manifest-v2",
    import_map: {},
    assets: [
      { id: "css/a.css", public_url: "/k/a.css", entry_point: true, loading: "stylesheet" },
      { id: "js/m1.js", public_url: "/k/m1.js", entry_point: true, loading: "module" },
      { id: "css/b.css", public_url: "/k/b.css", entry_point: true, loading: "stylesheet" },
      { id: "katex/k.js", public_url: "/k/k.js", entry_point: true, loading: "classic" },
      { id: "js/m2.js", public_url: "/k/m2.js", entry_point: true, loading: "module" },
    ],
  });
  const steps = {};
  await tick();
  steps.atStart = fresh();
  held.get("/k/b.css")();
  await tick();
  steps.afterSecondStylesheet = fresh();
  held.get("/k/a.css")();
  await tick();
  steps.afterBothStylesheets = fresh();
  held.get("/k/m1.js")();
  await tick();
  steps.afterFirstScript = fresh();
  held.get("/k/k.js")();
  await tick();
  held.get("/k/m2.js")();
  await done;
  steps.atEnd = fresh();
  // The preloads leave the document once the call settles (review B of #372, B4).
  steps.removedAtEnd = removed.slice(removedSince);
  holding = false;
  return steps;
}
