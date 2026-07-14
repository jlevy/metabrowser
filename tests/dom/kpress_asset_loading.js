// KPress asset-loading shim — executes plugin_sdk.js in the same small
// Node vm sandbox style as load_plugins.js/render_view.js, then exercises
// mb.fetchKpressRender against a fake /api/kpress/render response.
//
// Usage:
//   node kpress_asset_loading.js <repo_root>
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
  fail("usage: kpress_asset_loading.js <repo_root>");
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
          css: ["/kpress-static/css/document.css"],
          // theme.js is skipped (metabrowser owns the theme). toc.js is loaded
          // via dynamic import (so the host can call its initKpressToc per
          // render) — it is never appended as a <script> tag. code-copy.js is a
          // plain enhancement appended as an ordered module script.
          js: [
            "/kpress-static/js/theme.js",
            "/kpress-static/js/code-copy.js",
            "/kpress-static/js/toc.js",
          ],
        },
      }),
    };
  },
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

vm.createContext(sandbox);

const sdkPath = path.join(repoRoot, "src", "metabrowser", "static", "plugin_sdk.js");
vm.runInContext(fs.readFileSync(sdkPath, "utf-8"), sandbox, {
  filename: "plugin_sdk.js",
});

if (!sandbox.metabrowser || typeof sandbox.metabrowser.fetchKpressRender !== "function") {
  fail("plugin_sdk.js did not expose metabrowser.fetchKpressRender");
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
    assert(requested.searchParams.get("theme_mode") === "system", "bad theme_mode param");
    assert(requested.searchParams.get("resolved_theme") === "dark", "bad resolved_theme param");

    const links = appended.filter((el) => el.tagName === "LINK");
    const scripts = appended.filter((el) => el.tagName === "SCRIPT");
    assert(links.length === 1, `expected one stylesheet, got ${links.length}`);
    assert(links[0].rel === "stylesheet", "stylesheet rel was not set");
    assert(links[0].href === "/kpress-static/css/document.css", "stylesheet href was not set");
    assert(
      Object.hasOwn(links[0].attrs, "data-kpress-asset"),
      "stylesheet missing data-kpress-asset marker",
    );

    // Only code-copy.js is appended as a <script> tag: theme.js is skipped
    // (metabrowser owns the theme) and toc.js is loaded via dynamic import (so
    // the host can drive its initKpressToc per render), so neither appears as a
    // script tag.
    const scriptSrcs = scripts.map((el) => el.src);
    assert(
      scripts.length === 1,
      `expected one script tag (code-copy.js), got ${scripts.length}: ${scriptSrcs.join(", ")}`,
    );
    assert(
      scriptSrcs[0] === "/kpress-static/js/code-copy.js",
      `expected code-copy.js to load, got ${scriptSrcs[0]}`,
    );
    assert(
      !scriptSrcs.some((src) => src.endsWith("/theme.js") || src.endsWith("/toc.js")),
      `theme.js/toc.js must not be appended as script tags: ${scriptSrcs.join(", ")}`,
    );
    for (const script of scripts) {
      assert(script.type === "module", `${script.src} was not loaded as an ES module`);
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
