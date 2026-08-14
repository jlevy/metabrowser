// Behavioral shim for plugin_sdk.js — tests six contracts that
// kpress_asset_loading.js (the happy-path shim) cannot:
//
//   1. _loadStylesheet awaits the actual onload event (not just appendChild)
//   2. fetchKpressRender deduplicates concurrent requests for the same key
//      via AbortController — the first call's signal becomes aborted
//   3. Non-ok fetch responses propagate as rejections (with .status / .payload)
//   4. Failed stylesheet, script, and TOC module loads can be retried
//   5. A cached stylesheet settles even when the browser omits load events
//   6. A failed auxiliary asset does not discard rendered HTML
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
let cacheNextStylesheet = false;

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
    if (cacheNextStylesheet && element.tagName === "LINK") {
      cacheNextStylesheet = false;
      element.sheet = {};
    } else {
      pendingOnload.push(element);
    }
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

let tocImportAttempts = 0;
const cachedStylesheetSettleDeadlineMs = 100;
async function importKpressModule() {
  tocImportAttempts += 1;
  if (tocImportAttempts === 1) {
    throw new Error("simulated TOC module failure");
  }
  return import(
    "data:text/javascript,export function initKpressToc() { return function dispose() {}; }"
  );
}

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

for (const filename of [
  "request_error.js",
  "formatters.js",
  "inventory_scope.js",
  "resource_context.js",
  "view_state.js",
  "navigation.js",
]) {
  const dependencyPath = path.join(repoRoot, "src", "metabrowser", "static", filename);
  vm.runInContext(fs.readFileSync(dependencyPath, "utf-8"), sandbox, { filename });
}
const sdkPath = path.join(repoRoot, "src", "metabrowser", "static", "plugin_sdk.js");
vm.runInContext(fs.readFileSync(sdkPath, "utf-8"), sandbox, {
  filename: "plugin_sdk.js",
  importModuleDynamically: importKpressModule,
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

// ── Contract 4: failed asset loads can retry ─────────────────────────────

async function check_failed_kpress_assets_retry() {
  const retryableAssets = [
    {
      id: "css/retry.css",
      path: "css/retry.css",
      public_url: "/css/retry.css",
      entry_point: true,
      loading: "stylesheet",
    },
    {
      id: "js/retry.js",
      path: "js/retry.js",
      public_url: "/js/retry.js",
      entry_point: true,
      loading: "module",
    },
  ];

  for (const asset of retryableAssets) {
    const firstAppend = appended.length;
    const firstLoad = loadKpressAssets(assetManifest([asset])).then(
      () => ({ rejected: false }),
      () => ({ rejected: true }),
    );
    await new Promise((resolve) => setTimeout(resolve, 0));
    const firstElement = appended.at(-1);
    if (appended.length !== firstAppend + 1 || typeof firstElement?.onerror !== "function") {
      return { ok: false, detail: `${asset.id} did not append a loadable element` };
    }
    firstElement.onerror();
    if (!(await firstLoad).rejected) {
      return { ok: false, detail: `${asset.id} failure did not reject` };
    }

    const secondAppend = appended.length;
    const secondLoad = loadKpressAssets(assetManifest([asset]));
    await new Promise((resolve) => setTimeout(resolve, 0));
    const secondElement = appended.at(-1);
    if (appended.length !== secondAppend + 1 || typeof secondElement?.onload !== "function") {
      return { ok: false, detail: `${asset.id} was not appended again for retry` };
    }
    secondElement.onload();
    await secondLoad;
  }

  tocImportAttempts = 0;
  const tocManifest = assetManifest([
    {
      id: "js/toc.js",
      path: "js/toc.js",
      public_url: "/js/toc.js",
      entry_point: true,
      loading: "module",
    },
  ]);
  await loadKpressAssets(tocManifest);
  await loadKpressAssets(tocManifest);
  if (tocImportAttempts !== 2) {
    return {
      ok: false,
      detail: `TOC module was imported ${tocImportAttempts} time(s), expected a retry`,
    };
  }
  return { ok: true };
}

// ── Contract 5: cached stylesheets settle without load events ────────────

async function check_cached_stylesheet_settles() {
  cacheNextStylesheet = true;
  const settled = await Promise.race([
    loadKpressAssets(
      assetManifest([
        {
          id: "css/cached.css",
          path: "css/cached.css",
          public_url: "/css/cached.css",
          entry_point: true,
          loading: "stylesheet",
        },
      ]),
    ).then(() => true),
    new Promise((resolve) => setTimeout(() => resolve(false), cachedStylesheetSettleDeadlineMs)),
  ]);
  if (!settled) {
    return { ok: false, detail: "cached stylesheet did not settle without load events" };
  }
  return { ok: true };
}

// ── Contract 6: rendered HTML survives auxiliary asset failure ──────────

async function check_render_survives_asset_failure() {
  sandbox.fetch = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      type: "kpress-rendered-document",
      html: '<article class="kpress-doc">Still visible</article>',
      assets: assetManifest([
        {
          id: "css/optional.css",
          path: "css/optional.css",
          public_url: "/css/optional.css",
          entry_point: true,
          loading: "stylesheet",
        },
      ]),
    }),
  });
  const pending = fetchKpressRender({ path: "asset-failure.md" }, "rendered", {
    dedupKey: "asset-failure",
  }).then(
    (payload) => ({ payload }),
    (error) => ({ error }),
  );
  await new Promise((resolve) => setTimeout(resolve, 0));
  const element = appended.at(-1);
  if (typeof element?.onerror !== "function") {
    return { ok: false, detail: "auxiliary stylesheet was not requested" };
  }
  element.onerror();
  const result = await pending;
  if (result.error || !result.payload?.html.includes("Still visible")) {
    return { ok: false, detail: "asset failure discarded the rendered document" };
  }
  return { ok: true };
}

// ── Contract 7: transformed source uses bounded POST transport ──────────

async function check_transformed_source_uses_post() {
  let request = null;
  sandbox.fetch = async (url, options) => {
    request = { options, url };
    return {
      ok: true,
      status: 200,
      json: async () => ({
        type: "kpress-rendered-document",
        html: '<article class="kpress-doc">Wiki</article>',
        assets: assetManifest(),
      }),
    };
  };
  await fetchKpressRender({ path: "wiki.md" }, "rendered", {
    dedupKey: "wiki-source",
    profile: "document",
    sourceText: '<span data-mb-wiki-target="Note">Note</span>',
  });
  const body = JSON.parse(request?.options?.body || "null");
  if (
    request?.options?.method !== "POST" ||
    request?.options?.headers?.["content-type"] !== "application/json" ||
    body?.path !== "wiki.md" ||
    body?.source_text !== '<span data-mb-wiki-target="Note">Note</span>'
  ) {
    return {
      ok: false,
      detail: `unexpected transformed-source request ${JSON.stringify(request)}`,
    };
  }
  return { ok: true };
}

// ── Driver ────────────────────────────────────────────────────────────────

(async () => {
  const stylesheet = await check_loadStylesheet_waits_for_onload();
  const dedup = await check_fetchKpressRender_aborts_previous();
  const errorProp = await check_fetchKpressRender_throws_on_error();
  const assetRetry = await check_failed_kpress_assets_retry();
  const cachedStylesheet = await check_cached_stylesheet_settles();
  const assetFailureFallback = await check_render_survives_asset_failure();
  const transformedSource = await check_transformed_source_uses_post();

  process.stdout.write(
    `${JSON.stringify({ stylesheet, dedup, errorProp, assetRetry, cachedStylesheet, assetFailureFallback, transformedSource })}\n`,
  );

  if (
    !stylesheet.ok ||
    !dedup.ok ||
    !errorProp.ok ||
    !assetRetry.ok ||
    !cachedStylesheet.ok ||
    !assetFailureFallback.ok ||
    !transformedSource.ok
  ) {
    process.exit(1);
  }
})().catch((err) => fail(err?.stack ? err.stack : String(err)));
