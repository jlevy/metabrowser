// The plugin SDK with its view helpers, in a fresh context and with no page.
//
//   const { createSdkSandbox } = require("./sdk-sandbox.js");
//   const sandbox = createSdkSandbox();
//   sandbox.MetabrowserSourceLineAnchors.parse("L10");
//
// For a test that calls one function of plugin-sdk-views.js -- the line-anchor
// grammar, a helper -- and compares its answer with another implementation's. The
// file holds the SDK's view helpers beside the line anchors and needs the SDK to be
// there when it runs, so it cannot be loaded into an empty context by itself. The
// document is the smallest one the SDK's startup touches; nothing renders here.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const staticDir = path.resolve(__dirname, "../../src/metabrowser/static");

function createSdkSandbox() {
  const sandbox = {
    AbortController,
    DOMException,
    Map,
    Promise,
    Set,
    TextEncoder,
    URL,
    addEventListener() {},
    clearInterval,
    clearTimeout,
    console,
    dispatchEvent: () => true,
    document: {
      addEventListener() {},
      body: { append() {} },
      cookie: "",
      createElement: () => ({ addEventListener() {}, getAttribute: () => null, setAttribute() {} }),
      documentElement: { getAttribute: () => null },
      head: { append() {} },
    },
    fetch: () => Promise.reject(new Error("no request is part of this sandbox")),
    location: { origin: "http://localhost" },
    METABROWSER_SETTINGS: {
      SYNTAX_HIGHLIGHT_MAX_BYTES: 512 * 1024,
      SYNTAX_LANGUAGE_BY_BASENAME: {},
      SYNTAX_LANGUAGE_BY_EXTENSION: {},
    },
    removeEventListener() {},
    setInterval,
    setTimeout,
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
    "plugin-sdk.js",
    "plugin-sdk-views.js",
  ]) {
    const filepath = path.join(staticDir, filename);
    vm.runInContext(fs.readFileSync(filepath, "utf8"), sandbox, { filename: filepath });
  }
  return sandbox;
}

module.exports = { createSdkSandbox };
