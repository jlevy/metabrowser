// Behavioral shim for plugin_sdk.js — tests three contracts that
// kpress_asset_loading.js (the happy-path shim) cannot:
//
//   1. _loadStylesheet awaits the actual onload event (not just appendChild)
//   2. fetchKpressRender deduplicates concurrent requests for the same key
//      via AbortController — the first call's signal becomes aborted
//   3. Non-ok fetch responses propagate as rejections (with .status / .payload)
//
// Usage:
//   node kpress_plugin_sdk_behavior.js <repo_root>
//
// Output: one JSON line summarizing each contract check.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function fail(msg) {
  process.stderr.write(`${msg}\n`);
  process.exit(1);
}

function _assert(condition, msg) {
  if (!condition) {
    fail(msg);
  }
}

const args = process.argv.slice(2);
if (args.length !== 1) {
  fail("usage: kpress_plugin_sdk_behavior.js <repo_root>");
}

const repoRoot = path.resolve(args[0]);

function assetManifest(assets = [], importMap = {}) {
  return {
    schema_version: "kpress-asset-manifest-v2",
    assets,
    import_map: importMap,
  };
}

// ── Sandbox setup ─────────────────────────────────────────────────────────

const appended = [];
// Track elements appended so we can fire onload later (async).
const pendingOnload = [];

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
    appended.push(element);
    pendingOnload.push(element);
    return element;
  },
};

// First fetch: blocks until released. Second: returns immediately.
let firstFetchSignal = null;
let _firstFetchReleased = false;
const firstFetchReady = { release: null };
function makeReleaseable() {
  return new Promise((resolve) => {
    firstFetchReady.release = resolve;
  });
}
const firstFetchGate = makeReleaseable();

// errorFetch returns 502, used for the third contract.
let useErrorFetch = false;

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
  AbortController,
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
          return "light";
        }
        return null;
      },
    },
  },
  fetch: async (_url, options) => {
    const signal = options?.signal;
    if (useErrorFetch) {
      return {
        ok: false,
        status: 502,
        json: async () => ({ error: "upstream failed", type: "kpress_render_error" }),
      };
    }
    // First (slow) call records its signal and waits to be released.
    if (firstFetchSignal === null) {
      firstFetchSignal = signal || null;
      await firstFetchGate;
      // If aborted during the wait, surface that as the second-call dedup
      // contract would in the real browser.
      if (signal?.aborted) {
        const err = new Error("AbortError");
        err.name = "AbortError";
        throw err;
      }
    }
    _firstFetchReleased = true;
    return {
      ok: true,
      status: 200,
      json: async () => ({
        type: "kpress-rendered-document",
        html: '<article class="kpress-doc">Doc</article>',
        profile: "document",
        printable: true,
        diagnostics: [],
        assets: assetManifest(),
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
const { fetchKpressRender, loadKpressAssets } = sandbox.metabrowser;

// ── Contract 1: _loadStylesheet waits for onload ──────────────────────────

async function check_loadStylesheet_waits_for_onload() {
  let resolved = false;
  appended.length = 0;
  pendingOnload.length = 0;
  const p = loadKpressAssets(
    assetManifest([
      {
        id: "css/late.css",
        path: "css/late.css",
        public_url: "/css/late.css",
        entry_point: true,
        loading: "stylesheet",
      },
    ]),
  ).then(() => {
    resolved = true;
  });

  // Yield twice; the css load promise must not be resolved yet because
  // the fakeParent did NOT fire onload synchronously this time.
  await new Promise((r) => setTimeout(r, 0));
  await new Promise((r) => setTimeout(r, 0));
  if (resolved) {
    return { ok: false, detail: "loadKpressAssets resolved before stylesheet onload fired" };
  }

  // Fire onload now — the promise should resolve on the next tick.
  for (const el of pendingOnload) {
    if (typeof el.onload === "function") {
      el.onload();
    }
  }
  await p;
  if (!resolved) {
    return { ok: false, detail: "loadKpressAssets never resolved after onload" };
  }
  return { ok: true };
}

// ── Contract 2: AbortController dedup ─────────────────────────────────────

async function check_fetchKpressRender_aborts_previous() {
  firstFetchSignal = null;
  _firstFetchReleased = false;
  // Replace the gate with a fresh one.
  const newGate = new Promise((resolve) => {
    firstFetchReady.release = resolve;
  });
  // Re-assign the variable the sandbox sees — but actually we use the closure
  // captured firstFetchGate above; the sandbox's fetch references it. Reset
  // by stubbing fetch to use the new gate.
  sandbox.fetch = async (_url, options) => {
    const signal = options?.signal;
    if (firstFetchSignal === null) {
      firstFetchSignal = signal || null;
      await newGate;
      if (signal?.aborted) {
        const err = new Error("AbortError");
        err.name = "AbortError";
        throw err;
      }
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({
        type: "kpress-rendered-document",
        html: '<article class="kpress-doc">Doc</article>',
        profile: "document",
        printable: true,
        diagnostics: [],
        assets: assetManifest(),
      }),
    };
  };

  // Fire two concurrent fetches for the same path.
  const firstPromise = fetchKpressRender({ path: "shared.md" }, "rendered", {}).catch((err) => ({
    error: err.name,
  }));
  // Yield so the first fetch is in flight and recorded its signal.
  await new Promise((r) => setTimeout(r, 0));
  const secondPromise = fetchKpressRender({ path: "shared.md" }, "rendered", {});

  // The second call should have aborted the first via the dedup key.
  // Release the (now-aborted) first fetch so its promise resolves to an
  // AbortError.
  firstFetchReady.release();

  const [firstResult, secondResult] = await Promise.all([firstPromise, secondPromise]);

  if (firstFetchSignal?.aborted !== true) {
    return {
      ok: false,
      detail: "first fetch's AbortSignal.aborted was not true after the second call",
    };
  }
  if (firstResult?.error !== "AbortError") {
    return {
      ok: false,
      detail: `first fetch did not reject with AbortError, got ${JSON.stringify(firstResult)}`,
    };
  }
  if (!secondResult?.html) {
    return { ok: false, detail: "second fetch did not return a payload" };
  }
  return { ok: true };
}

// ── Contract 3: error response propagates ─────────────────────────────────

async function check_fetchKpressRender_throws_on_error() {
  // Replace the dedup stub from contract 2 with an error-returning fetch.
  sandbox.fetch = async () => ({
    ok: false,
    status: 502,
    json: async () => ({ error: "upstream failed", type: "kpress_render_error" }),
  });
  try {
    await fetchKpressRender({ path: "broken.md" }, "rendered", { dedupKey: "broken-key" });
    return { ok: false, detail: "expected rejection on 502 response" };
  } catch (err) {
    if (err && err.status === 502 && err.payload && err.payload.type === "kpress_render_error") {
      return { ok: true };
    }
    return {
      ok: false,
      detail:
        "expected err.status===502 and err.payload.type === 'kpress_render_error', got " +
        JSON.stringify({
          status: err?.status,
          payload: err?.payload,
          message: err?.message,
        }),
    };
  } finally {
    useErrorFetch = false;
  }
}

// ── Driver ────────────────────────────────────────────────────────────────

(async () => {
  const stylesheet = await check_loadStylesheet_waits_for_onload();
  const dedup = await check_fetchKpressRender_aborts_previous();
  const errorProp = await check_fetchKpressRender_throws_on_error();

  process.stdout.write(`${JSON.stringify({ stylesheet, dedup, errorProp })}\n`);

  if (!stylesheet.ok || !dedup.ok || !errorProp.ok) {
    process.exit(1);
  }
})().catch((err) => fail(err?.stack ? err.stack : String(err)));
