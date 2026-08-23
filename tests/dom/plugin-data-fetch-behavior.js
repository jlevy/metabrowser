// Contract checks for the SDK's fetchPluginData helper.
//
// A data hook that answers "why not" in its response body is answering
// usefully; a caller that only sees the status has to guess or hard-code the
// reason. These assert that a non-ok response reaches the caller with its
// status and parsed body attached, and that a caller can abort a request when
// its view is disposed.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

/** @type {Array<{url: string, init: object}>} */
const calls = [];
let nextResponse = null;

const sandbox = {
  console: {
    log: (...a) => process.stderr.write(`[sdk:log] ${a.join(" ")}\n`),
    warn: (...a) => process.stderr.write(`[sdk:warn] ${a.join(" ")}\n`),
    error: (...a) => process.stderr.write(`[sdk:error] ${a.join(" ")}\n`),
  },
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  Promise,
  Set,
  Map,
  URL,
  AbortController,
  Intl,
  Number,
  Math,
  JSON,
  Object,
  Array,
  String,
  Boolean,
  Error,
  location: { origin: "http://localhost" },
  document: {
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
    createElement: () => ({ appendChild: () => {}, setAttribute: () => {} }),
    documentElement: { getAttribute: () => null },
    head: { appendChild: () => {} },
    body: { appendChild: () => {} },
  },
  addEventListener: () => {},
  removeEventListener: () => {},
  dispatchEvent: () => {},
  fetch: (url, init) => {
    calls.push({ url: String(url), init: init || {} });
    return nextResponse();
  },
  Mustache: { render: (tpl) => tpl },
  Chart: () => {},
  hljs: { highlightElement: () => {} },
  HTMLCanvasElement: () => {},
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);

function load(filename) {
  const filepath = path.join(repoRoot, "src", "metabrowser", "static", filename);
  vm.runInContext(fs.readFileSync(filepath, "utf-8"), sandbox, { filename });
}

for (const filename of [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "contribution-registry.js",
  "resource-context.js",
  "view-state.js",
  // The SDK requires the canonical navigation module, exactly as the shell
  // links it immediately ahead of plugin-sdk.js in the same response.
  "navigation.js",
  "plugin-sdk.js",
]) {
  load(filename);
}

const mb = sandbox.metabrowser;

function jsonResponse(status, body) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  });
}

(async () => {
  check("SDK initialized", !!mb, "window.metabrowser missing");

  // ── Params and success ──────────────────────────────────────────
  nextResponse = () => jsonResponse(200, { type: "binary_chunk", bytes_read: 4 });
  const ok = await mb.fetchPluginData("binary", "chunk", { path: "a.bin", offset: 0 });
  check("successful payload is returned", ok.bytes_read === 4, JSON.stringify(ok));
  check(
    "params are encoded onto the query string",
    calls[0].url === "http://localhost/api/plugin/binary/chunk?path=a.bin&offset=0",
    calls[0].url,
  );

  // ── Structured non-ok errors ────────────────────────────────────
  nextResponse = () =>
    jsonResponse(413, {
      type: "binary_chunk_error",
      error: "Preview unavailable.",
      max_preview_bytes: 1024,
    });
  let captured = null;
  try {
    await mb.fetchPluginData("binary", "chunk", { path: "big.bin" });
  } catch (error) {
    captured = error;
  }
  check("a non-ok response rejects", captured instanceof Error, String(captured));
  check("the status reaches the caller", captured?.status === 413, String(captured?.status));
  check(
    "the parsed body reaches the caller",
    captured?.payload?.max_preview_bytes === 1024,
    JSON.stringify(captured?.payload),
  );

  // A hook that returns a non-ok status with an unparseable body must still
  // reject with its status rather than throwing a JSON error.
  nextResponse = () =>
    Promise.resolve({
      ok: false,
      status: 502,
      json: () => Promise.reject(new Error("not json")),
    });
  captured = null;
  try {
    await mb.fetchPluginData("binary", "chunk", {});
  } catch (error) {
    captured = error;
  }
  check("a non-JSON error body still rejects", captured?.status === 502, String(captured?.status));
  check("a non-JSON error body yields a null payload", captured?.payload === null);

  // ── Degraded plugin_error envelopes ─────────────────────────────
  nextResponse = () =>
    jsonResponse(200, { type: "plugin_error", error: "Plugin data hook failed", detail: "boom" });
  captured = null;
  try {
    await mb.fetchPluginData("binary", "chunk", {});
  } catch (error) {
    captured = error;
  }
  check(
    "a degraded plugin_error still rejects with its detail",
    captured?.message === "Plugin data hook failed: boom",
    String(captured?.message),
  );
  check("a degraded plugin_error carries its payload", captured?.payload?.detail === "boom");

  // ── Abort ───────────────────────────────────────────────────────
  const controller = new AbortController();
  nextResponse = () => jsonResponse(200, { ok: true });
  await mb.fetchPluginData("binary", "chunk", {}, { signal: controller.signal });
  const lastCall = calls[calls.length - 1];
  check(
    "the caller's signal is forwarded to fetch",
    lastCall.init.signal === controller.signal,
    String(lastCall.init.signal),
  );

  if (failures.length) {
    console.error(`plugin data fetch FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("plugin data fetch OK");
})();
