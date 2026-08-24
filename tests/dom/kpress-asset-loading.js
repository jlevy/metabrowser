// KPress asset-loading shim — executes plugin-sdk.js in the same small
// Node vm sandbox style as load-plugins.js/render-view.js, then exercises
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
  };
}

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
    if (typeof element.onload === "function") {
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

if (!sandbox.metabrowser || typeof sandbox.metabrowser.fetchKpressRender !== "function") {
  fail("plugin-sdk.js did not expose metabrowser.fetchKpressRender");
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

    const links = appended.filter((el) => el.tagName === "LINK");
    const scripts = appended.filter((el) => el.tagName === "SCRIPT");
    assert(links.length === 1, `expected one stylesheet, got ${links.length}`);
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

    process.stdout.write(
      `${JSON.stringify({
        requestedUrl: requestedUrls[0],
        appended,
        html: payload.html,
      })}\n`,
    );
  })
  .catch((err) => fail(err?.stack ? err.stack : String(err)));
