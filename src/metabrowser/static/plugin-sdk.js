// metabrowser plugin SDK — the window.metabrowser API surface.
//
// Loaded once, before any plugin index.js. Plugins call these methods to
// self-register their detectors and view renderers, and use the helpers
// for safe HTML rendering, data-hook fetches, and Chart.js wiring.
//
// Public surface (all under window.metabrowser, conventionally aliased
// as `mb` inside plugin index.js files):
//
//   Registration:
//     registerView(kindId, viewId, {render, dispose?})
//     getRegisteredView(kindId, viewId)
//     listViewsForKind(kindId)
//
//   View lifecycle contract:
//     render(container, ctx)
//       Called when the preview pane mounts this view. Plugin owns
//       container's innerHTML and may attach DOM listeners, fetch data,
//       paint charts. May return a Promise; the shell awaits it for
//       error surfacing.
//     dispose(container) [optional]
//       Called when the preview pane is *replaced* — specifically when
//       (1) a different file is opened, (2) the same file is reloaded
//       after a file-change event, or (3) an error/loading state
//       overwrites the pane. Use it to detach window-level listeners,
//       abort in-flight fetches, clear timers/SSE streams, and destroy
//       Chart.js instances or other resources that would otherwise
//       outlive their container.
//       dispose is *not* called on tab switches within the same file
//       — those toggle CSS display only; the container's DOM persists,
//       and so does any state the plugin captured in closures over it.
//
//   Rendering:
//     render(template, data)             — Mustache.render with auto-escape
//     escapeHtml(s)                      — escape for raw HTML insertion
//     wrapWithCopy(html)                 — wraps html in a copy-button frame
//                                          (delegated click handler, no inline onclick)
//     chart(container, type, data, opts) — Chart.js wrapper
//
//   Data fetches:
//     fetchPluginData(plugin, route, p, opts?)
//                                        — GET /api/plugin/<plugin>/<route>
//                                          opts.signal aborts the request; a
//                                          non-ok response rejects with an
//                                          Error carrying .status and .payload
//     fetchJsonl(path, opts)             — GET /api/file?path=... (JSONL envelope)
//     fetchCompleteText(ctx, opts)       — bounded complete source for a text context
//     fetchText(target, opts)            — bounded complete source for a navigation target
//     fetchKpressRender(ctx, view, opts) — GET or bounded POST /api/kpress/render
//     renderTextTruncationWarning(data) — partial-content banner, with a
//                                        Load more control in it
//     renderTextLoadMoreFooter(data)    — the same notice, for after the
//                                        content (see design-system.md)
//     partialNoticeHtml({loaded,total}, position, useSiteClass)
//                                        — the shared partial-content notice,
//                                          for views that track their own
//                                          progress rather than /api/file's
//
//   Navigation:
//     navigation.href(target)            — canonical /view/ href for a target
//     navigation.open(target, {viewId?}) — open a target, optionally preferring a view
//     navigation.current()               — current path/query/fragment target or null
//     fileCatalog.snapshot()              — immutable known-file inventory snapshot
//     fileCatalog.subscribe(listener)     — invalidate when inventory coverage changes
//     repository                          — verified GitHub identity for the served tree
//
//   Formatting:
//     formatSize(bytes)                  — "1.5 KB" / "2.3 MB" / etc.
//     formatTimestamp(secondsSinceEpoch) — local-time short form
//     countClass(count)                   — shared file-count emphasis class
//     sizeClass(bytes)                    — shared byte-count emphasis class
//     sizeHtml(bytes, extraClass?)       — formatSize wrapped in <span class=size>
//     isLargeTextPreview(data)           — true if /api/file payload exceeds the
//                                          syntax-highlight cutoff
//     highlightSyntax(source, language, options?)
//                                        — bounded DOM-free Highlight.js token data
//
//   Visual:
//     icons.<name>                       — raw SVG strings for built-in icons
//     icons.withClass(name, cls)         — returns SVG with extra class applied
//     filterControls                      — shared filter markup and interaction
//                                          helpers, installed before plugins load
//
//   Diagnostics:
//     perf.measure(label, fn)            — contribute a synchronous named span
//     perf.measureAsync(label, fn)       — contribute an asynchronous named span
//     perf.report()/responsiveness()     — inspect the active browser profile
//     debug                              — console-only shell troubleshooting helpers
//
// Plugins register from index.js with code like:
//   const mb = window.metabrowser;
//   mb.registerView("analysis-report", "visual", { render: (c, ctx) => ... });
//
// Templates are Mustache (`{{name}}` for variables and `{{#items}}…{{/items}}`
// for sections). Auto-escaping is on by default.

((global) => {
  if (
    typeof global.metabrowser?.registerView === "function" &&
    typeof global.metabrowser?.navigation?.open === "function"
  ) {
    // The actual SDK is already initialized; protect against double-load.
    // A host or browser extension may expose an unrelated truthy value under
    // this ordinary property name, so existence alone is not proof that our
    // contract is installed.
    return;
  }
  if (!global.MetabrowserNavigationRoute?.navigation) {
    throw new Error("plugin SDK requires the canonical navigation module");
  }

  // Internal registry: kindId -> Map<viewId, {render, dispose?}>.
  const _viewRegistry = new Map();
  /** @type {Set<string>} */
  const _loadedKpressAssets = new Set();
  /** @type {Map<string, Promise<void>>} */
  const _loadingKpressAssets = new Map();
  const _KPRESS_ASSET_MANIFEST_SCHEMA = "kpress-asset-manifest-v2";
  /** Bounds a missing stylesheet load/error event before a later render can retry. */
  const _stylesheetLoadTimeoutMs = 10_000;
  /** Detects cached stylesheets whose browsers expose `sheet` without a load event. */
  const _stylesheetReadyPollMs = 50;
  const _emptyFileCatalogSnapshot = Object.freeze({
    complete: false,
    files: Object.freeze([]),
    observedCount: 0,
    revision: 0,
    sourceSummary: Object.freeze({}),
  });
  /** @type {{snapshot: () => unknown, subscribe: (listener: () => void) => () => void} | null} */
  let _attachedFileCatalog = null;
  /** @type {Map<string, Array<{name: string, module: string, scripts: string[], styles: string[]}>>} */
  const _pluginAssetsByKind = new Map();
  /** @type {Map<string, Promise<void>>} */
  const _pluginLoads = new Map();

  const fileCatalog = Object.freeze({
    snapshot() {
      return _attachedFileCatalog?.snapshot() || _emptyFileCatalogSnapshot;
    },
    subscribe(listener) {
      if (typeof listener !== "function") {
        throw new TypeError("fileCatalog.subscribe: listener must be a function");
      }
      return _attachedFileCatalog?.subscribe(listener) || (() => {});
    },
  });
  const repository = normalizeRepositoryContext(global.METABROWSER_REPOSITORY_CONTEXT);

  /** @param {unknown} value */
  function normalizeRepositoryContext(value) {
    if (!value || typeof value !== "object") {
      return null;
    }
    const context = /** @type {Record<string, unknown>} */ (value);
    if (
      context.host !== "github.com" ||
      typeof context.owner !== "string" ||
      !context.owner ||
      typeof context.name !== "string" ||
      !context.name ||
      typeof context.revision !== "string" ||
      !/^[0-9a-f]{40}$/i.test(context.revision) ||
      (context.branch !== null && typeof context.branch !== "string") ||
      typeof context.served_prefix !== "string"
    ) {
      return null;
    }
    return Object.freeze({
      branch: context.branch,
      host: context.host,
      name: context.name,
      owner: context.owner,
      revision: context.revision.toLowerCase(),
      served_prefix: context.served_prefix,
    });
  }

  function attachFileCatalog(catalog) {
    if (
      !catalog ||
      typeof catalog.snapshot !== "function" ||
      typeof catalog.subscribe !== "function"
    ) {
      throw new TypeError("attachFileCatalog: catalog must expose snapshot and subscribe");
    }
    _attachedFileCatalog = catalog;
    return () => {
      if (_attachedFileCatalog === catalog) {
        _attachedFileCatalog = null;
      }
    };
  }

  function _loadPluginElement(tagName, url, attributes) {
    return new Promise((resolve) => {
      const element = global.document.createElement(tagName);
      for (const [name, value] of Object.entries(attributes || {})) {
        element.setAttribute(name, value);
      }
      element.addEventListener("load", () => resolve(undefined), { once: true });
      element.addEventListener(
        "error",
        () => {
          console.error(`metabrowser plugin asset failed to load: ${url}`);
          resolve(undefined);
        },
        { once: true },
      );
      if (tagName === "link") {
        element.setAttribute("href", url);
      } else {
        element.setAttribute("src", url);
      }
      global.document.head.append(element);
    });
  }

  function configureAssets(assetsByKind) {
    if (!assetsByKind || typeof assetsByKind !== "object") {
      throw new TypeError("configureAssets: expected a kind-to-assets object");
    }
    _pluginAssetsByKind.clear();
    for (const [kind, descriptors] of Object.entries(assetsByKind)) {
      if (!Array.isArray(descriptors)) {
        throw new TypeError(`configureAssets: ${kind} must contain an array`);
      }
      _pluginAssetsByKind.set(kind, descriptors);
    }
  }

  function _loadPlugin(descriptor) {
    const existing = _pluginLoads.get(descriptor.name);
    if (existing) {
      return existing;
    }
    const loading = (async () => {
      await Promise.all(
        descriptor.styles.map((url, index) =>
          _loadPluginElement("link", url, {
            "data-metabrowser-plugin-asset": `${descriptor.name}:style:${index}`,
            rel: "stylesheet",
          }),
        ),
      );
      for (let index = 0; index < descriptor.scripts.length; index += 1) {
        await _loadPluginElement("script", descriptor.scripts[index], {
          "data-metabrowser-plugin-asset": `${descriptor.name}:script:${index}`,
        });
      }
      try {
        await import(descriptor.module);
      } catch (error) {
        console.error(`metabrowser plugin failed to load: ${descriptor.name}`, error);
      }
    })();
    _pluginLoads.set(descriptor.name, loading);
    return loading;
  }

  async function loadPluginsForKind(kind) {
    const descriptors = _pluginAssetsByKind.get(kind) || [];
    for (const descriptor of descriptors) {
      await _loadPlugin(descriptor);
    }
  }

  global.MetabrowserPluginHost = Object.freeze({
    attachFileCatalog,
    configureAssets,
    loadPluginsForKind,
  });

  function registerView(kindId, viewId, spec) {
    if (typeof kindId !== "string" || !kindId) {
      throw new Error("registerView: kindId must be a non-empty string");
    }
    if (typeof viewId !== "string" || !viewId) {
      throw new Error("registerView: viewId must be a non-empty string");
    }
    if (!spec || typeof spec.render !== "function") {
      throw new Error("registerView: spec must be { render: function, dispose?: function }");
    }
    let bucket = _viewRegistry.get(kindId);
    if (!bucket) {
      bucket = new Map();
      _viewRegistry.set(kindId, bucket);
    }
    bucket.set(viewId, spec);
  }

  function getRegisteredView(kindId, viewId) {
    const bucket = _viewRegistry.get(kindId);
    return bucket ? bucket.get(viewId) || null : null;
  }

  function listViewsForKind(kindId) {
    const bucket = _viewRegistry.get(kindId);
    if (!bucket) {
      return [];
    }
    return Array.from(bucket.keys());
  }

  function render(template, data) {
    if (typeof global.Mustache === "undefined") {
      throw new Error("metabrowser.render: Mustache.js is not loaded — bundle is missing");
    }
    if (typeof template !== "string") {
      throw new Error("metabrowser.render: template must be a string");
    }
    return global.Mustache.render(template, data == null ? {} : data);
  }

  function escapeHtml(s) {
    if (s === null || s === undefined) {
      return "";
    }
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function fetchPluginData(plugin, route, params, options) {
    if (!plugin || !route) {
      throw new Error("fetchPluginData: plugin + route are required");
    }
    const url = new URL(
      `/api/plugin/${encodeURIComponent(plugin)}/${encodeURIComponent(route)}`,
      global.location.origin,
    );
    if (params && typeof params === "object") {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== null) {
          url.searchParams.set(k, String(v));
        }
      }
    }
    const resp = await fetch(url.toString(), { method: "GET", signal: options?.signal });
    if (!resp.ok) {
      // A hook that answers "why not" in its body is answering usefully; a
      // caller that only sees the status has to guess or hard-code the
      // reason. Same shape fetchKpressRender uses for the same reason.
      let payload = null;
      try {
        payload = await resp.json();
      } catch (_e) {
        payload = null;
      }
      /** @type {Error & {status?: number, payload?: unknown}} */
      const err = new Error(`fetchPluginData ${plugin}/${route}: ${resp.status}`);
      err.status = resp.status;
      err.payload = payload;
      throw err;
    }
    const data = await resp.json();
    if (data && data.type === "plugin_error") {
      /** @type {Error & {status?: number, payload?: unknown}} */
      const err = new Error(
        (data.error || "Plugin data hook failed") + (data.detail ? `: ${data.detail}` : ""),
      );
      err.status = resp.status;
      err.payload = data;
      throw err;
    }
    return data;
  }

  async function fetchJsonl(path, opts) {
    // Plugins fetch JSONL content through the same /api/file endpoint the
    // shell uses; it returns ``{type: "jsonl", events, summary, ...}`` for
    // .jsonl files, including built-in and plugin-registered adapters plus
    // the "unknown-jsonl" catch-all. Optional `opts` keys are forwarded
    // as query params so callers can pass through pagination / filters
    // when they're added server-side.
    const url = new URL("/api/file", global.location.origin);
    url.searchParams.set("path", path);
    if (opts && typeof opts === "object") {
      for (const [k, v] of Object.entries(opts)) {
        if (v !== undefined && v !== null) {
          url.searchParams.set(k, String(v));
        }
      }
    }
    const resp = await fetch(url.toString());
    if (!resp.ok) {
      throw new Error(`fetchJsonl ${path}: ${resp.status}`);
    }
    const data = await resp.json();
    if (data && data.type !== "jsonl") {
      throw new Error(`fetchJsonl ${path}: expected JSONL, got type=${data.type || "?"}`);
    }
    return data;
  }

  async function fetchCompleteText(ctx, opts) {
    const path = ctx?.path;
    const raw = ctx?.raw && typeof ctx.raw === "object" ? ctx.raw : {};
    if (typeof path !== "string" || !path) {
      throw new TypeError("fetchCompleteText: ctx.path must be a non-empty string");
    }
    if (typeof raw.content === "string" && raw.content_truncated !== true) {
      return raw.content;
    }
    const limit = raw.content_max_preview_limit;
    if (!Number.isSafeInteger(limit) || limit < 1) {
      throw new Error("fetchCompleteText: server did not advertise a valid source limit");
    }
    const data = await fetchTextEnvelope(path, limit, opts?.signal, "fetchCompleteText");
    if (data.content_truncated === true) {
      throw new Error(`fetchCompleteText ${path}: source exceeds the server read limit`);
    }
    return data.content;
  }

  async function fetchText(target, opts) {
    const normalized = global.MetabrowserNavigationRoute.normalizeTarget(target);
    const initial = await fetchTextEnvelope(normalized.path, null, opts?.signal, "fetchText");
    if (initial.content_truncated !== true) {
      return initial.content;
    }
    const limit = initial.content_max_preview_limit;
    if (!Number.isSafeInteger(limit) || limit < 1) {
      throw new Error("fetchText: server did not advertise a valid source limit");
    }
    const completed = await fetchTextEnvelope(normalized.path, limit, opts?.signal, "fetchText");
    if (completed.content_truncated === true) {
      throw Object.assign(
        new Error(`fetchText ${normalized.path}: source exceeds the server read limit`),
        { code: "source-too-large" },
      );
    }
    return completed.content;
  }

  async function fetchTextEnvelope(path, limit, signal, operation) {
    const url = new URL("/api/file", global.location.origin);
    url.searchParams.set("path", path);
    if (limit !== null) {
      url.searchParams.set("limit", String(limit));
    }
    const response = await fetch(url.toString(), { signal });
    if (!response.ok) {
      throw new Error(`${operation} ${path}: ${response.status}`);
    }
    const data = await response.json();
    if (data?.type !== "text" || typeof data.content !== "string") {
      throw new Error(`${operation} ${path}: expected a text envelope`);
    }
    return data;
  }

  // ── Preferences ─────────────────────────────────────────────────
  //
  // Versioned display-preference storage that survives across
  // Metabrowser instances. Every served root runs on its own port and
  // therefore its own browser origin, so localStorage silos per
  // folder; host-only cookies ignore the port (the mechanism the theme
  // already uses in app.js) and share small preferences across every
  // local instance. Values are JSON, size-bounded, and versioned;
  // consumers never learn which backend stores them. Not for sensitive
  // data or absolute paths.
  const PREF_COOKIE_PREFIX = "mbpref_";
  const PREF_VERSION_TAG = "v1:";
  const PREF_MAX_ENCODED_BYTES = 2048;
  const PREF_MAX_AGE_S = 365 * 24 * 60 * 60;
  const PREF_NAME_RE = /^[a-z][a-z0-9_.-]*$/i;

  function _prefCookieName(name) {
    return PREF_COOKIE_PREFIX + name.replace(/\./g, "_");
  }

  function prefsGet(name, fallback) {
    if (typeof name !== "string" || !PREF_NAME_RE.test(name)) {
      return fallback;
    }
    try {
      const doc = global.document;
      if (!doc || typeof doc.cookie !== "string") {
        return fallback;
      }
      const key = `${_prefCookieName(name)}=`;
      for (const part of doc.cookie.split("; ")) {
        if (part.startsWith(key)) {
          const raw = decodeURIComponent(part.slice(key.length));
          if (!raw.startsWith(PREF_VERSION_TAG)) {
            return fallback; // unknown future version: ignore, don't guess
          }
          return JSON.parse(raw.slice(PREF_VERSION_TAG.length));
        }
      }
    } catch (_err) {
      // Unreadable cookie or malformed JSON degrades to the fallback.
    }
    return fallback;
  }

  function prefsSet(name, value) {
    if (typeof name !== "string" || !PREF_NAME_RE.test(name)) {
      return false;
    }
    try {
      const doc = global.document;
      if (!doc || typeof doc.cookie !== "string") {
        return false;
      }
      const encoded = encodeURIComponent(PREF_VERSION_TAG + JSON.stringify(value));
      if (encoded.length > PREF_MAX_ENCODED_BYTES) {
        console.warn(`prefs.set(${name}): value exceeds ${PREF_MAX_ENCODED_BYTES} bytes; ignored`);
        return false;
      }
      doc.cookie = `${_prefCookieName(name)}=${encoded}; path=/; max-age=${PREF_MAX_AGE_S}; samesite=lax`;
      return true;
    } catch (_err) {
      return false;
    }
  }

  function prefsRemove(name) {
    if (typeof name !== "string" || !PREF_NAME_RE.test(name)) {
      return false;
    }
    try {
      const doc = global.document;
      if (!doc || typeof doc.cookie !== "string") {
        return false;
      }
      doc.cookie = `${_prefCookieName(name)}=; path=/; max-age=0; samesite=lax`;
      return true;
    } catch (_err) {
      return false;
    }
  }

  const prefs = { get: prefsGet, set: prefsSet, remove: prefsRemove };

  // Shared filter state (static/filter-state.js). Views bind to the
  // same vocabulary the nav filter bar edits; safe no-ops when the
  // module is absent (tests, partial harnesses).
  const filters = {
    get() {
      const fs = global.metabrowser?.filterState;
      return fs ? fs.get() : null;
    },
    set(patch) {
      const fs = global.metabrowser?.filterState;
      if (fs) {
        fs.set(patch);
      }
    },
    clear() {
      const fs = global.metabrowser?.filterState;
      if (fs) {
        fs.clear();
      }
    },
    subscribe(listener) {
      const fs = global.metabrowser?.filterState;
      return fs ? fs.subscribe(listener) : () => {};
    },
    activeCount() {
      const fs = global.metabrowser?.filterState;
      return fs ? fs.activeCount() : 0;
    },
  };

  // Semantic family membership is server-owned and validated before this
  // SDK loads. The frozen facade keeps plugins on the public boundary while
  // partial test harnesses retain conservative raw-extension behavior.
  const fileTypes =
    global.MetabrowserFileTypeTaxonomy ||
    Object.freeze({
      schema: "file-type-registry-v3",
      schemaVersion: 3,
      revision: 0,
      fingerprint: "unavailable",
      maxExtensionComponents: 2,
      registryIdentity: Object.freeze({
        schemaVersion: 3,
        revision: 0,
        fingerprint: "unavailable",
      }),
      groups: Object.freeze([]),
      families: Object.freeze([]),
      kinds: Object.freeze([]),
      classify(_name, extension) {
        return Object.freeze({
          logicalExtension: typeof extension === "string" ? extension.toLowerCase() || null : null,
          canonicalExtension: null,
          kindId: null,
          familyId: null,
          groupId: "other",
          contentFamily: "unknown",
          detectionSource: "unknown",
          confidence: "unknown",
          registryRevision: 0,
          registryFingerprint: "unavailable",
        });
      },
      matchExtension() {
        return null;
      },
      canonicalExtension(extension) {
        return typeof extension === "string" ? extension.toLowerCase() : "";
      },
      groupForFile() {
        return "other";
      },
      distributionKeyForExtension(extension) {
        return typeof extension === "string" ? extension.toLowerCase() : "";
      },
      hueForDistributionKey() {
        return null;
      },
    });

  // Age buckets shared with the shell's tree column. The thresholds
  // mirror app.js formatAge exactly (sec <1m, min <1h, hr <1d, day
  // <7d, wk <30d, old beyond); keep the two lists in sync so a
  // treemap fill and a tree row never disagree about freshness.
  /** @type {Array<[string, number]>} */
  const AGE_BUCKET_STEPS = [
    ["sec", 60 * 1000],
    ["min", 60 * 60 * 1000],
    ["hr", 24 * 60 * 60 * 1000],
    ["day", 7 * 24 * 60 * 60 * 1000],
    ["wk", 30 * 24 * 60 * 60 * 1000],
  ];

  function ageBucket(mtimeSeconds) {
    if (typeof mtimeSeconds !== "number" || !Number.isFinite(mtimeSeconds) || mtimeSeconds <= 0) {
      return null;
    }
    const absMs = Math.abs(Date.now() - mtimeSeconds * 1000);
    for (const [bucket, limitMs] of AGE_BUCKET_STEPS) {
      if (absMs < limitMs) {
        return bucket;
      }
    }
    return "old";
  }

  // Compact age text mirrors app.js formatAge ("3h", "2d", "<1m", …)
  // so a plugin label and a tree row read identically.
  /** @type {Array<[string, number]>} */
  const AGE_LABEL_STEPS = [
    ["y", 365 * 24 * 60 * 60 * 1000],
    ["mo", 30 * 24 * 60 * 60 * 1000],
    ["w", 7 * 24 * 60 * 60 * 1000],
    ["d", 24 * 60 * 60 * 1000],
    ["h", 60 * 60 * 1000],
    ["m", 60 * 1000],
  ];

  function ageLabelHtml(mtimeSeconds) {
    // The colored age chip the shell shows in tree rows and headers:
    // `<span class="age-<bucket>">3h</span>` on the shared freshness
    // tokens, or "" when there is no meaningful mtime.
    const bucket = ageBucket(mtimeSeconds);
    if (bucket === null) {
      return "";
    }
    const absMs = Math.abs(Date.now() - /** @type {number} */ (mtimeSeconds) * 1000);
    let text = "<1m";
    for (const [suffix, stepMs] of AGE_LABEL_STEPS) {
      if (absMs >= stepMs) {
        text = `${Math.round(absMs / stepMs)}${suffix}`;
        break;
      }
    }
    return `<span class="age-${bucket}">${escapeHtml(text)}</span>`;
  }

  const ROLLUP_FALLBACK_DEBOUNCE_MS = 1000;

  function _rollupSettings() {
    const settings = global.METABROWSER_SETTINGS || {};
    return {
      depth: settings.ROLLUP_DEFAULT_DEPTH,
      top: settings.ROLLUP_DEFAULT_TOP,
      ext_top: settings.ROLLUP_DEFAULT_EXT_TOP,
      filename_top: settings.ROLLUP_FILE_TYPE_FILENAME_LIMIT,
      remaining_top: settings.ROLLUP_FILE_TYPE_REMAINING_LIMIT,
      ext_rank: settings.ROLLUP_DEFAULT_EXT_RANK || "bytes",
      debounceMs: settings.ROLLUP_WATCH_DEBOUNCE_MS || ROLLUP_FALLBACK_DEBOUNCE_MS,
    };
  }

  async function fetchRollup(path, opts) {
    // Core rollup endpoint for directory subtrees (see /api/rollup).
    // ``path`` may be "" for the served root. Optional opts:
    // depth / top / ext_top / filename_top / remaining_top query overrides
    // plus ``signal``.
    if (typeof path !== "string") {
      throw new Error("fetchRollup: path must be a string");
    }
    const defaults = _rollupSettings();
    const options = opts && typeof opts === "object" ? opts : {};
    const url = new URL("/api/rollup", global.location.origin);
    url.searchParams.set("path", path);
    for (const key of ["depth", "top", "ext_top", "filename_top", "remaining_top", "ext_rank"]) {
      const value = options[key] !== undefined ? options[key] : defaults[key];
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
    const resp = await fetch(url.toString(), { signal: options.signal });
    if (!resp.ok) {
      throw new global.MetabrowserRequestErrors.RequestError("Could not load folder totals.", {
        operation: "fetchRollup",
        status: resp.status,
      });
    }
    return resp.json();
  }

  function watchRollup(path, opts, onUpdate) {
    // Fetch a rollup now and refresh it (trailing debounce) whenever the
    // shell's inventory store reports a change touching ``path``'s
    // subtree or ancestor chain. Returns {refresh, dispose, stale};
    // dispose detaches the listener and aborts any in-flight fetch.
    // Pair every watch with a view dispose — a leaked watch keeps
    // refetching. ``opts.active`` (optional callback) gates the
    // debounced refresh: while it returns false (e.g. the view's tab
    // is hidden) the fetch is skipped and the watch marks itself
    // stale instead; call ``refresh()`` when the view shows again and
    // ``stale()`` reports true.
    if (typeof onUpdate !== "function") {
      throw new Error("watchRollup: onUpdate callback is required");
    }
    const options = opts && typeof opts === "object" ? opts : {};
    return global.MetabrowserInventoryScope.createInventoryWatch(
      path,
      {
        active: options.active,
        debounceMs:
          typeof options.debounceMs === "number"
            ? options.debounceMs
            : _rollupSettings().debounceMs,
        fetch: (signal) => fetchRollup(path, Object.assign({}, options, { signal })),
        onError: options.onError || ((err) => console.warn("watchRollup refresh failed:", err)),
      },
      onUpdate,
    );
  }

  // Plugins can observe directory totals but cannot mutate the host-owned
  // inventory projection. The fallback keeps partial SDK harnesses usable
  // without weakening the production ownership boundary.
  const directoryTotalsHost = global.metabrowserDirectoryTotalsStore;
  const directoryTotals = Object.freeze({
    get(path) {
      return directoryTotalsHost?.get(path) ?? null;
    },
    subscribe(path, listener) {
      if (directoryTotalsHost) {
        return directoryTotalsHost.subscribe(path, listener);
      }
      listener(null);
      return () => {};
    },
  });

  // Shell-surface proxies — same pattern as `icons`: plugins reach the
  // shared tooltip and file-type classifier through the SDK so they
  // never touch app.js globals directly, and get safe no-ops when the
  // shell has not installed them (tests, partial harnesses).
  const tooltip = {
    /**
     * Show `html` for `anchor`, the element the tooltip describes. Position is
     * taken from the anchor, once — there is deliberately no move(): a tooltip
     * that follows the pointer jitters and stops naming what it annotates.
     * Re-announcing the same anchor keeps the tooltip where it is.
     */
    show(html, anchor) {
      if (global.MetabrowserTooltip) {
        global.MetabrowserTooltip.show(html, anchor);
      }
    },
    hide() {
      if (global.MetabrowserTooltip) {
        global.MetabrowserTooltip.hide();
      }
    },
  };

  function fileTypeClass(path) {
    if (global.MetabrowserFileTypes && typeof global.MetabrowserFileTypes.classFor === "function") {
      return global.MetabrowserFileTypes.classFor(path);
    }
    return "";
  }

  function fileTypeIcon(path) {
    if (global.MetabrowserFileTypes && typeof global.MetabrowserFileTypes.iconFor === "function") {
      const icon = global.MetabrowserFileTypes.iconFor(path);
      if (icon && typeof icon === "object") {
        return {
          svg: typeof icon.svg === "string" ? icon.svg : "",
          className: typeof icon.cls === "string" ? icon.cls : "",
        };
      }
    }
    return {
      svg:
        global.MetabrowserIcons && typeof global.MetabrowserIcons.file === "string"
          ? global.MetabrowserIcons.file
          : "",
      className: "",
    };
  }

  function formatKpressError(payload, status) {
    const body = payload && typeof payload === "object" ? payload : {};
    const base = body.error || "KPress render failed";
    const detail = body.detail || "";
    return `${base + (detail ? `: ${detail}` : "")} (HTTP ${status})`;
  }

  /**
   * How much of a partially-loaded payload is showing, or null when it is
   * complete. One reading of the payload, so the banner, the footer control,
   * and the header readout cannot disagree about whether more remains.
   *
   * @param {Record<string, any> | null | undefined} data
   * @returns {{loaded: string, total: string} | null}
   */
  function textPreviewProgress(data) {
    if (!data) {
      return null;
    }
    const totalBytes = data.size_uncompressed || data.logical_size || data.size || 0;
    const bytesRead = data.bytes_read || data.content_bytes || 0;
    const truncated =
      !!data.content_truncated ||
      (typeof data.bytes_read === "number" && totalBytes > 0 && bytesRead < totalBytes);
    if (!truncated) {
      return null;
    }
    return { loaded: formatSize(bytesRead), total: formatSize(totalBytes) };
  }

  /**
   * The Load more control itself. Emitted at both ends of partial content —
   * see docs/design-system.md, "Continuing partial content": a reader who has
   * scrolled to the end of what loaded is exactly the reader who wants more,
   * and sending them back to the top to ask for it is the whole problem.
   *
   * @param {"top" | "bottom"} position
   * @returns {string}
   */
  function loadMoreButtonHtml(position, action) {
    // `action: null` means the caller wires its own listener — a view that
    // tracks its own offsets cannot be continued by the shell's text loader.
    const onclick = action === null ? "" : ` onclick="${action || "loadMoreCurrentText()"}"`;
    return (
      `<button class="btn metabrowser-load-more" type="button" data-position="${position}"` +
      `${onclick} data-tip-text="Load more of this file">Load more</button>`
    );
  }

  /**
   * The shared partial-content notice.
   *
   * Every surface that says "this is only part of the file" is this box, in
   * core and in plugins alike — see docs/design-system.md, "Continuing partial
   * content". A use-site class rides along for querying and positioning, but
   * `partial-notice` is what carries the fill, border, and type, so the two
   * ends of a file and the two views cannot drift apart.
   *
   * `showControl: false` states the condition without offering to continue —
   * for content that is partial and will stay partial, such as a file larger
   * than a view is willing to load. That is still a partial-content notice; a
   * reader who cannot see the whole file needs telling either way.
   *
   * @param {{loaded: string, total: string}} progress
   * @param {"top" | "bottom"} position
   * @param {{useSiteClass?: string, action?: string | null, hidden?: boolean,
   *          label?: string, showControl?: boolean}} [options]
   * @returns {string}
   */
  function partialNoticeHtml(progress, position, options) {
    const useSiteClass = options?.useSiteClass ? ` ${options.useSiteClass}` : "";
    const hidden = options?.hidden ? " hidden" : "";
    const label = options?.label ?? "Partial file.";
    const control =
      options?.showControl === false ? "" : loadMoreButtonHtml(position, options?.action);
    return (
      `<div class="notice partial-notice${useSiteClass}" data-severity="warning"` +
      ` data-position="${position}" role="status"${hidden}>` +
      // The progress figures live in their own element so a view that updates
      // in place can rewrite them without taking the label with them.
      `<span><strong class="partial-notice-label">${escapeHtml(label)}</strong> ` +
      '<span class="partial-notice-readout">Showing ' +
      escapeHtml(progress.loaded) +
      " of " +
      escapeHtml(progress.total) +
      ".</span></span>" +
      // The notice carries its own button. It used to say "Select Load more to
      // continue" and point at a control in the pane header, which puts the
      // explanation and the remedy in different places.
      control +
      "</div>"
    );
  }

  function renderTextTruncationWarning(data) {
    const progress = textPreviewProgress(data);
    return progress
      ? partialNoticeHtml(progress, "top", {
          useSiteClass: "metabrowser-source-truncation-warning",
        })
      : "";
  }

  /**
   * Trailing companion to the banner, mounted after the content.
   *
   * @param {Record<string, any> | null | undefined} data
   * @returns {string}
   */
  function renderTextLoadMoreFooter(data) {
    const progress = textPreviewProgress(data);
    return progress
      ? partialNoticeHtml(progress, "bottom", { useSiteClass: "metabrowser-source-more-footer" })
      : "";
  }

  function _headOrBody() {
    return global.document && (global.document.head || global.document.body);
  }

  /**
   * Share an in-flight load and mark the asset complete only after it succeeds.
   * @param {string} key
   * @param {() => Promise<void>} load
   * @returns {Promise<void>}
   */
  function _loadKpressAssetOnce(key, load) {
    if (_loadedKpressAssets.has(key)) {
      return Promise.resolve();
    }
    const existing = _loadingKpressAssets.get(key);
    if (existing) {
      return existing;
    }
    const pending = load()
      .then(() => {
        _loadedKpressAssets.add(key);
      })
      .finally(() => {
        _loadingKpressAssets.delete(key);
      });
    _loadingKpressAssets.set(key, pending);
    return pending;
  }

  /** @param {string} url @returns {Promise<void>} */
  function _loadStylesheet(url) {
    if (!url || !global.document) {
      return Promise.resolve();
    }
    const parent = _headOrBody();
    if (!parent || typeof global.document.createElement !== "function") {
      return Promise.resolve();
    }
    return _loadKpressAssetOnce(
      url,
      () =>
        new Promise((resolve, reject) => {
          const link = global.document.createElement("link");
          let settled = false;
          /** @type {ReturnType<typeof setTimeout> | null} */
          let readyPoll = null;
          /** @type {ReturnType<typeof setTimeout> | null} */
          let loadTimeout = null;

          const clearLoadTimers = () => {
            if (readyPoll !== null) {
              clearTimeout(readyPoll);
            }
            if (loadTimeout !== null) {
              clearTimeout(loadTimeout);
            }
          };
          const succeed = () => {
            if (settled) {
              return;
            }
            settled = true;
            clearLoadTimers();
            resolve();
          };
          /** @param {Error} error */
          const fail = (error) => {
            if (settled) {
              return;
            }
            settled = true;
            clearLoadTimers();
            if (typeof link.remove === "function") {
              link.remove();
            }
            reject(error);
          };
          const detectCachedStylesheet = () => {
            if (settled) {
              return;
            }
            if (link.sheet) {
              succeed();
              return;
            }
            readyPoll = setTimeout(detectCachedStylesheet, _stylesheetReadyPollMs);
          };

          link.rel = "stylesheet";
          link.href = url;
          link.setAttribute("data-kpress-asset", "");
          link.onload = succeed;
          link.onerror = () => fail(new Error(`Failed to load KPress stylesheet: ${url}`));
          loadTimeout = setTimeout(
            () => fail(new Error(`Timed out loading KPress stylesheet: ${url}`)),
            _stylesheetLoadTimeoutMs,
          );
          parent.appendChild(link);
          detectCachedStylesheet();
        }),
    );
  }

  /** @param {string} url @param {"module" | "classic"} loading @returns {Promise<void>} */
  function _loadScript(url, loading) {
    if (!url || !global.document) {
      return Promise.resolve();
    }
    const parent = _headOrBody();
    if (!parent || typeof global.document.createElement !== "function") {
      return Promise.resolve();
    }
    return _loadKpressAssetOnce(
      url,
      () =>
        new Promise((resolve, reject) => {
          const script = global.document.createElement("script");
          script.type = loading === "classic" ? "text/javascript" : "module";
          script.src = url;
          script.async = false;
          script.setAttribute("data-kpress-asset", "");
          script.onload = () => resolve();
          script.onerror = () => {
            if (typeof script.remove === "function") {
              script.remove();
            }
            reject(new Error(`Failed to load KPress asset: ${url}`));
          };
          parent.appendChild(script);
        }),
    );
  }

  // toc.js is loaded via dynamic import (not a <script> tag) so we can capture
  // its initKpressToc export and drive it per rendered document. Its load-time
  // self-init runs once against the page; per-render wiring + teardown is owned
  // by kpressInitToc below.
  let _kpressInitTocFn = null;
  function _isTocScript(asset, url) {
    return asset?.id === "js/toc.js" || url.endsWith("/toc.js");
  }
  async function _loadKpressTocModule(url) {
    try {
      await _loadKpressAssetOnce(url, async () => {
        const mod = await import(url);
        if (mod && typeof mod.initKpressToc === "function") {
          _kpressInitTocFn = mod.initKpressToc;
        }
      });
    } catch (err) {
      // A failed TOC module must not break document rendering; the doc still
      // shows, just without sidebar/drawer behavior.
      if (global.console?.warn) {
        global.console.warn("metabrowser: failed to load kpress toc.js", err);
      }
    }
  }

  function _kpressAssetUrl(asset) {
    return asset?.public_url || asset?.output_path || asset?.path || "";
  }

  function _installKpressImportMap(importMap) {
    if (!importMap || typeof importMap !== "object" || !Object.keys(importMap).length) {
      return;
    }
    const parent = _headOrBody();
    if (!parent || !global.document || typeof global.document.createElement !== "function") {
      return;
    }
    const payload = JSON.stringify({ imports: importMap });
    const key = `importmap:${payload}`;
    if (_loadedKpressAssets.has(key)) {
      return;
    }
    const script = global.document.createElement("script");
    script.type = "importmap";
    script.textContent = payload;
    script.setAttribute("data-kpress-asset", "");
    parent.appendChild(script);
    _loadedKpressAssets.add(key);
  }

  function _validateKpressAssetManifest(manifest) {
    if (!manifest || manifest.schema_version !== _KPRESS_ASSET_MANIFEST_SCHEMA) {
      throw new Error(
        `Unsupported KPress asset manifest schema: ${manifest?.schema_version || "missing"}`,
      );
    }
    if (!Array.isArray(manifest.assets)) {
      throw new Error("Invalid KPress asset manifest: assets must be an array");
    }
    for (const asset of manifest.assets) {
      if (!asset?.entry_point || asset.loading === "resource") {
        continue;
      }
      if (!_kpressAssetUrl(asset)) {
        throw new Error(`KPress entry point ${asset.id || "<unknown>"} has no URL`);
      }
    }
  }

  async function loadKpressAssets(manifest) {
    _validateKpressAssetManifest(manifest);
    const entryPoints = manifest.assets.filter((asset) => asset?.entry_point === true);
    for (const asset of entryPoints) {
      if (asset.loading !== "stylesheet") {
        continue;
      }
      const url = _kpressAssetUrl(asset);
      if (!url) {
        throw new Error(`KPress entry point ${asset.id || "<unknown>"} has no URL`);
      }
      await _loadStylesheet(url);
    }
    _installKpressImportMap(manifest.import_map);
    for (const asset of entryPoints) {
      if (asset.loading !== "module" && asset.loading !== "classic") {
        continue;
      }
      const url = _kpressAssetUrl(asset);
      if (!url) {
        throw new Error(`KPress entry point ${asset.id || "<unknown>"} has no URL`);
      }
      if (_isTocScript(asset, url)) {
        await _loadKpressTocModule(url);
        continue;
      }
      await _loadScript(url, asset.loading);
    }
  }

  // On-demand vendored libraries. asset-loader.js owns the loading; the SDK
  // only publishes it, so a plugin never reaches into a private global.
  // A consumer awaits this before touching the library's global: Chart.js is
  // on this tier, so metabrowser.chart() throws until ensureAsset("chart")
  // has resolved.
  /** @param {string} name @returns {Promise<void>} */
  function ensureAsset(name) {
    const assets = global.MetabrowserAssets;
    if (!assets || typeof assets.ensureAsset !== "function") {
      return Promise.reject(new Error("metabrowser.ensureAsset: asset loader is not available"));
    }
    return assets.ensureAsset(name);
  }

  // Load the plugins that declare support for a file kind. This is public so
  // one plugin can embed another kind's renderer without reaching into the
  // private plugin host or forcing that renderer onto the eager shell path.
  /** @param {string} kind @returns {Promise<void>} */
  function ensureKindAssets(kind) {
    if (typeof kind !== "string" || !kind) {
      return Promise.reject(
        new TypeError("metabrowser.ensureKindAssets: kind must be a non-empty string"),
      );
    }
    return loadPluginsForKind(kind);
  }

  // Wire KPress's TOC for a freshly mounted document and return its disposer.
  // KPress's toc.js owns the behavior; the host's only jobs are to mark a scroll
  // element [data-kpress-viewport] (the preview pane) and call this on mount /
  // dispose on unmount. Returns null if toc.js has not loaded yet.
  function kpressInitToc(container) {
    if (typeof _kpressInitTocFn !== "function" || !container) {
      return null;
    }
    try {
      return _kpressInitTocFn(container);
    } catch (err) {
      if (global.console?.warn) {
        global.console.warn("metabrowser: kpress toc init failed", err);
      }
      return null;
    }
  }

  // Per-path in-flight controller so a fast file switch aborts the older
  // request rather than racing two responses into the same container.
  const _kpressInflight = new Map();

  async function fetchKpressRender(ctx, viewId, options) {
    const path = options?.path || ctx?.path;
    if (!path) {
      throw new Error("fetchKpressRender: ctx.path is required");
    }
    const url = new URL("/api/kpress/render", global.location.origin);
    url.searchParams.set("path", path);
    url.searchParams.set("view", viewId || "document");
    const profile = options && (options.profile || options.printProfile);
    if (profile) {
      url.searchParams.set("profile", profile);
    }
    // "off" for a document embedded in host navigation that is already the
    // reader's way around it; omitted means KPress' own thresholds decide.
    const includeToc = options?.includeToc;
    if (includeToc) {
      url.searchParams.set("toc", includeToc);
    }
    const dedupKey = options?.dedupKey || path;
    const previous = _kpressInflight.get(dedupKey);
    if (previous) {
      previous.abort();
    }
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    const externalSignal = options?.signal;
    const abortFromExternal = () => controller?.abort();
    if (externalSignal?.aborted) {
      controller?.abort();
    } else {
      externalSignal?.addEventListener("abort", abortFromExternal, { once: true });
    }
    if (controller) {
      _kpressInflight.set(dedupKey, controller);
    }

    const sourceText = options?.sourceText;
    if (sourceText !== undefined && typeof sourceText !== "string") {
      throw new Error("fetchKpressRender: options.sourceText must be a string");
    }
    let resp;
    try {
      const fetchOptions =
        sourceText === undefined
          ? { method: "GET", signal: controller ? controller.signal : undefined }
          : {
              body: JSON.stringify({
                path,
                profile,
                source_text: sourceText,
                view: viewId || "document",
              }),
              headers: { "content-type": "application/json" },
              method: "POST",
              signal: controller ? controller.signal : undefined,
            };
      resp = await fetch(url.toString(), fetchOptions);
    } finally {
      externalSignal?.removeEventListener("abort", abortFromExternal);
      if (controller && _kpressInflight.get(dedupKey) === controller) {
        _kpressInflight.delete(dedupKey);
      }
    }

    let payload = null;
    try {
      payload = await resp.json();
    } catch (_e) {
      payload = { error: "KPress render returned non-JSON response" };
    }
    if (!resp.ok) {
      /** @type {Error & {status?: number, payload?: unknown}} */
      const err = new Error(formatKpressError(payload, resp.status));
      err.status = resp.status;
      err.payload = payload;
      throw err;
    }
    const assets = payload.assets || {};
    _validateKpressAssetManifest(assets);
    try {
      await loadKpressAssets(assets);
    } catch (err) {
      if (global.console?.warn) {
        global.console.warn(
          "metabrowser: KPress document rendered with one or more unavailable assets",
          err,
        );
      }
    }
    return payload;
  }

  function _resolveChartThemeValue(value) {
    if (typeof value === "string") {
      const match = value.match(/^var\(\s*(--[\w-]+)\s*\)$/);
      if (!match || typeof global.getComputedStyle !== "function") {
        return value;
      }
      const resolved = global
        .getComputedStyle(global.document.documentElement)
        .getPropertyValue(match[1])
        .trim();
      return resolved || value;
    }
    if (Array.isArray(value)) {
      return value.map(_resolveChartThemeValue);
    }
    if (
      value === null ||
      typeof value !== "object" ||
      Object.prototype.toString.call(value) !== "[object Object]"
    ) {
      return value;
    }
    var resolvedObject = {};
    for (var key of Object.keys(value)) {
      resolvedObject[key] = _resolveChartThemeValue(value[key]);
    }
    return resolvedObject;
  }

  function _hasChartThemeValue(value) {
    if (typeof value === "string") {
      return /^var\(\s*--[\w-]+\s*\)$/.test(value);
    }
    if (Array.isArray(value)) {
      return value.some(_hasChartThemeValue);
    }
    if (
      value === null ||
      typeof value !== "object" ||
      Object.prototype.toString.call(value) !== "[object Object]"
    ) {
      return false;
    }
    return Object.values(value).some(_hasChartThemeValue);
  }

  function chart(container, type, data, options) {
    if (typeof global.Chart === "undefined") {
      throw new Error(
        'metabrowser.chart: Chart.js is on the on-demand tier; await metabrowser.ensureAsset("chart") first',
      );
    }
    // Container can be either a <canvas> or a <div> we'll create a canvas in.
    let canvas;
    if (container instanceof HTMLCanvasElement) {
      canvas = container;
    } else {
      canvas = global.document.createElement("canvas");
      container.appendChild(canvas);
    }
    var dataTemplate = data;
    var optionsTemplate = options || {};
    var followsTheme = _hasChartThemeValue(dataTemplate) || _hasChartThemeValue(optionsTemplate);
    var instance = new global.Chart(canvas, {
      type: type,
      data: followsTheme ? _resolveChartThemeValue(dataTemplate) : dataTemplate,
      options: followsTheme ? _resolveChartThemeValue(optionsTemplate) : optionsTemplate,
    });
    if (!followsTheme || !global.MetabrowserTheme) {
      return instance;
    }
    var destroyed = false;
    var unsubscribeTheme = global.MetabrowserTheme.subscribe(() => {
      if (destroyed) {
        return;
      }
      instance.data = _resolveChartThemeValue(dataTemplate);
      instance.options = _resolveChartThemeValue(optionsTemplate);
      instance.update("none");
    });
    var destroyChart = instance.destroy.bind(instance);
    instance.destroy = () => {
      if (destroyed) {
        return;
      }
      destroyed = true;
      unsubscribeTheme();
      destroyChart();
    };
    return instance;
  }

  function formatSize(bytes) {
    return global.MetabrowserFormatters.formatBytes(Number(bytes) || 0);
  }

  function formatInteger(value) {
    return global.MetabrowserFormatters.formatInteger(Number(value) || 0);
  }

  function formatFileCount(value) {
    return global.MetabrowserFormatters.formatFileCount(Number(value) || 0);
  }

  function formatTimestamp(secondsSinceEpoch) {
    // Local-time short form; matches the file header / activity feed.
    if (!secondsSinceEpoch) {
      return "";
    }
    const d = new Date(Number(secondsSinceEpoch) * 1000);
    if (Number.isNaN(d.getTime())) {
      return "";
    }
    return d.toLocaleString();
  }

  function sizeClass(bytes) {
    return global.MetabrowserFormatters.sizeClass(Number(bytes) || 0);
  }

  function countClass(value) {
    return global.MetabrowserFormatters.countClass(Number(value) || 0);
  }

  function sizeHtml(bytes, extraClass) {
    if (bytes === null || bytes === undefined) {
      // Walker emits null aggregates while a directory is still finalizing
      // in the InventoryIndex; render as a skeleton cell so the row paints
      // with shape; the SSE fs.change patch flow replaces it in place.
      const pendCls = `size tally-pending ${extraClass || ""}`.trim();
      return `<span class="${pendCls}"></span>`;
    }
    const cls = `size ${sizeClass(bytes)} ${extraClass || ""}`.trim();
    return `<span class="${cls}">${formatSize(bytes)}</span>`;
  }

  const HIGHLIGHT_TOKEN_CLASS_RE = /^[A-Za-z_][A-Za-z0-9_-]*$/;
  const HIGHLIGHT_ENTITIES = Object.freeze({
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#x27;": "'",
  });
  /** @type {TextEncoder | null} */
  let syntaxTextEncoder = null;
  let syntaxAssetsSettled = false;
  if (typeof global.addEventListener === "function") {
    global.addEventListener("metabrowser:optional-assets-loaded", () => {
      syntaxAssetsSettled = true;
    });
  }

  function syntaxHighlightMaxBytes() {
    const configured = Number(
      /** @type {{SYNTAX_HIGHLIGHT_MAX_BYTES?: unknown} | undefined} */ (
        global.METABROWSER_SETTINGS
      )?.SYNTAX_HIGHLIGHT_MAX_BYTES,
    );
    return Number.isFinite(configured) && configured >= 0 ? configured : 0;
  }

  /** @param {string} value */
  function utf8ByteLength(value) {
    syntaxTextEncoder ??= new global.TextEncoder();
    return syntaxTextEncoder.encode(value).byteLength;
  }

  /**
   * Record one safe plain-text fallback without making diagnostics part of
   * the syntax service's correctness path. Labels are fixed-cardinality and
   * metadata never includes source text.
   * @param {"over_limit" | "no_grammar" | "markup_rejected" | "lexer_threw"} reason
   * @param {string} language
   * @param {number} inputBytes
   */
  function recordSyntaxFallback(reason, language, inputBytes) {
    const recorder = global.metabrowser?.perf;
    if (typeof recorder?.measure !== "function") {
      return;
    }
    try {
      recorder.measure(`syntaxHighlight:fallback:${reason}`, () => undefined, {
        input_bytes: inputBytes,
        language: String(language).slice(0, 80),
      });
    } catch (_diagnosticError) {
      // Plain-text fallback must remain safe when an injected profiler fails.
    }
  }

  /** @param {string} language */
  function syntaxGrammarReady(language) {
    return (
      typeof global.hljs?.highlight === "function" &&
      typeof global.hljs?.getLanguage === "function" &&
      Boolean(global.hljs.getLanguage(language))
    );
  }

  function syntaxAbortError() {
    return new global.DOMException("Syntax highlighting was aborted.", "AbortError");
  }

  /**
   * Wait for a requested grammar or the terminal optional-asset event.
   * @param {string} language
   * @param {AbortSignal | undefined} signal
   * @returns {Promise<boolean>}
   */
  function waitForSyntaxAssets(language, signal) {
    if (signal?.aborted) {
      return Promise.reject(syntaxAbortError());
    }
    if (syntaxGrammarReady(language)) {
      return Promise.resolve(true);
    }
    if (syntaxAssetsSettled || typeof global.addEventListener !== "function") {
      return Promise.resolve(false);
    }
    return new Promise((resolve, reject) => {
      function cleanup() {
        global.removeEventListener("metabrowser:optional-asset-loaded", onAsset);
        global.removeEventListener("metabrowser:optional-assets-loaded", onTerminal);
        signal?.removeEventListener("abort", onAbort);
      }
      function onAsset() {
        if (syntaxGrammarReady(language)) {
          cleanup();
          resolve(true);
        }
      }
      function onTerminal() {
        cleanup();
        resolve(syntaxGrammarReady(language));
      }
      function onAbort() {
        cleanup();
        reject(syntaxAbortError());
      }
      global.addEventListener("metabrowser:optional-asset-loaded", onAsset);
      global.addEventListener("metabrowser:optional-assets-loaded", onTerminal);
      signal?.addEventListener("abort", onAbort, { once: true });
    });
  }

  function isLargeTextPreview(data) {
    if (!data) {
      return false;
    }
    return (
      !!data.highlight_disabled ||
      (typeof data.content === "string" && utf8ByteLength(data.content) > syntaxHighlightMaxBytes())
    );
  }

  /**
   * Convert Highlight.js's constrained markup to token data without an HTML parser.
   * @param {string} markup
   * @returns {MetabrowserSyntaxTokenLines | null}
   */
  function scanHighlightMarkup(markup) {
    /** @type {MetabrowserSyntaxTokenLines} */
    const lines = [[]];
    /** @type {string[][]} */
    const classStack = [];
    let offset = 0;

    /** @param {string} text */
    function appendText(text) {
      if (text.length === 0) {
        return;
      }
      const classes = classStack.flat();
      const line = lines[lines.length - 1];
      const previous = line[line.length - 1];
      if (
        previous &&
        previous.classes.length === classes.length &&
        previous.classes.every((name, index) => name === classes[index])
      ) {
        previous.text += text;
      } else {
        line.push({ classes, text });
      }
    }

    while (offset < markup.length) {
      if (markup.startsWith("</span>", offset)) {
        if (classStack.length === 0) {
          return null;
        }
        classStack.pop();
        offset += "</span>".length;
        continue;
      }
      if (markup.startsWith('<span class="', offset)) {
        const end = markup.indexOf('">', offset);
        if (end < 0) {
          return null;
        }
        const opening = markup.slice(offset, end + 2);
        const match = /^<span class="([^"]+)">$/.exec(opening);
        const classes = match?.[1].split(" ") ?? [];
        if (
          classes.length === 0 ||
          !classes.some((name) => name.startsWith("hljs-")) ||
          !classes.every((name) => HIGHLIGHT_TOKEN_CLASS_RE.test(name))
        ) {
          return null;
        }
        classStack.push(classes);
        offset = end + 2;
        continue;
      }
      const character = markup[offset];
      if (character === "<") {
        return null;
      }
      if (character === "&") {
        const end = markup.indexOf(";", offset);
        if (end < 0) {
          return null;
        }
        const entity = markup.slice(offset, end + 1);
        const decoded = HIGHLIGHT_ENTITIES[entity];
        if (decoded === undefined) {
          return null;
        }
        appendText(decoded);
        offset = end + 1;
        continue;
      }
      if (character === "\n") {
        lines.push([]);
        offset += 1;
        continue;
      }
      let end = offset + 1;
      while (end < markup.length && !"<&\n".includes(markup[end])) {
        end += 1;
      }
      appendText(markup.slice(offset, end));
      offset = end;
    }
    return classStack.length === 0 ? lines : null;
  }

  /**
   * Highlight source through the host grammar registry and return DOM-free token lines.
   * @param {string} source
   * @param {string} language
   * @param {{signal?: AbortSignal}} [options]
   * @returns {Promise<MetabrowserSyntaxTokenLines | null>}
   */
  async function highlightSyntax(source, language, options = {}) {
    if (options.signal?.aborted) {
      throw syntaxAbortError();
    }
    const inputBytes = utf8ByteLength(source);
    if (inputBytes > syntaxHighlightMaxBytes()) {
      recordSyntaxFallback("over_limit", language, inputBytes);
      return null;
    }
    if (!(await waitForSyntaxAssets(language, options.signal))) {
      recordSyntaxFallback("no_grammar", language, inputBytes);
      return null;
    }
    if (options.signal?.aborted) {
      throw syntaxAbortError();
    }
    try {
      const result = global.hljs.highlight(source, { language, ignoreIllegals: true });
      if (!result || typeof result.value !== "string") {
        recordSyntaxFallback("markup_rejected", language, inputBytes);
        return null;
      }
      const lines = scanHighlightMarkup(result.value);
      const sourceLines = source.split("\n");
      if (
        lines === null ||
        lines.length !== sourceLines.length ||
        lines.some((runs, index) => runs.map((run) => run.text).join("") !== sourceLines[index])
      ) {
        recordSyntaxFallback("markup_rejected", language, inputBytes);
        return null;
      }
      return lines;
    } catch (_error) {
      recordSyntaxFallback("lexer_threw", language, inputBytes);
      return null;
    }
  }

  // Copy-icon SVG. Defined here (not pulled from window.MetabrowserIcons)
  // so plugins don't depend on the icons.js bundle being loaded first.
  const ICON_COPY =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"' +
    ' stroke-linecap="round" stroke-linejoin="round">' +
    '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>' +
    '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>' +
    "</svg>";

  function wrapWithCopy(innerHtml) {
    // A delegated click listener (installed once at SDK init) handles
    // .content-copy-btn clicks — no inline handler needed. If the
    // shell's global copyContent exists it is called for full feedback;
    // otherwise the delegate falls back to clipboard.writeText.
    return (
      '<div class="content-copy-wrap">' +
      '<button class="icon-btn icon-btn-reveal icon-btn-overlay content-copy-btn"' +
      ' type="button" data-mb-copy="wrap" data-tip-text="Copy content" aria-label="Copy content">' +
      ICON_COPY +
      "</button>" +
      innerHtml +
      "</div>"
    );
  }

  // Icon registry — proxies window.MetabrowserIcons (loaded by icons.js)
  // so plugins can pull from mb.icons.<name> without depending on the
  // global's exact name. Falls back to an empty registry if icons.js
  // hasn't loaded (the shell ships with it; plugins should not assume
  // a particular icon is present).
  const icons = new Proxy(
    {},
    {
      get(_target, name) {
        const reg = (typeof global.MetabrowserIcons === "object" && global.MetabrowserIcons) || {};
        if (name === "withClass") {
          return reg.withClass || ((_n, _c) => "");
        }
        return reg[name] || "";
      },
    },
  );

  // perf.js replaces this temporary facade in the next eager script, before
  // application or plugin work starts.
  const perf = Object.freeze({
    measure(_label, fn) {
      return fn();
    },
    measureAsync(_label, fn) {
      return fn();
    },
  });

  function langForExtension(ext) {
    const languageByExtension = /** @type {Record<string, string>} */ (
      global.METABROWSER_SETTINGS?.SYNTAX_LANGUAGE_BY_EXTENSION || {}
    );
    return languageByExtension[ext || ""] || "";
  }

  function langForPath(pathOrName, ext = "") {
    const languageByBasename = /** @type {Record<string, string>} */ (
      global.METABROWSER_SETTINGS?.SYNTAX_LANGUAGE_BY_BASENAME || {}
    );
    const pathParts = String(pathOrName || "")
      .replaceAll("\\", "/")
      .split("/");
    let basename = (pathParts[pathParts.length - 1] || "").toLowerCase();
    for (const compressionSuffix of [".gz", ".zlib"]) {
      if (basename.endsWith(compressionSuffix)) {
        basename = basename.slice(0, -compressionSuffix.length);
        break;
      }
    }
    let logicalExtension = ext.toLowerCase();
    if (!logicalExtension) {
      const dot = basename.lastIndexOf(".");
      logicalExtension = dot > 0 ? basename.slice(dot) : "";
    }
    return languageByBasename[basename] || langForExtension(logicalExtension);
  }

  /**
   * Render the shared bounded Source surface used by generic text-like views.
   * @param {HTMLElement} container
   * @param {Record<string, unknown> & {content?: string, ext?: string}} data
   */
  function renderSourceView(container, data) {
    const truncationWarning = renderTextTruncationWarning(data);
    const loadMoreFooter = renderTextLoadMoreFooter(data);
    const content = typeof data.content === "string" ? data.content : "";
    let languageClass = "plaintext no-highlight";
    if (!isLargeTextPreview(data)) {
      const language = langForPath(
        typeof data.path === "string" ? data.path : "",
        typeof data.ext === "string" ? data.ext : "",
      );
      languageClass = language ? `language-${language}` : "plaintext";
    }
    const code =
      `<pre class="code-block"><code class="${languageClass}">` +
      `${escapeHtml(content)}</code></pre>`;
    container.classList.add("metabrowser-source-host");
    container.innerHTML = truncationWarning + wrapWithCopy(code) + loadMoreFooter;
  }

  // Delegated click handler for the copy buttons wrapWithCopy emits.
  // Fully SDK-owned: no reference to shell globals, so the documented
  // wrapWithCopy behavior cannot change when app.js internals do. Scoped
  // to buttons carrying data-mb-copy so plugin- or shell-built copy
  // buttons with their own listeners are never double-handled.
  /** @param {Element & {classList?: DOMTokenList, dataset?: DOMStringMap}} btn */
  function _handleCopyClick(btn) {
    var wrap = typeof btn.closest === "function" ? btn.closest(".content-copy-wrap") : null;
    if (!wrap) {
      return;
    }
    var code =
      typeof wrap.querySelector === "function"
        ? wrap.querySelector("[data-mb-copy-payload]") || wrap.querySelector("code")
        : null;
    var text = code ? code.textContent || "" : "";
    if (!text) {
      // No <code> child: copy the wrap's text minus the button's label.
      const nodes = wrap.childNodes || [];
      for (let ci = 0; ci < nodes.length; ci++) {
        if (nodes[ci] !== btn) {
          text += nodes[ci].textContent || "";
        }
      }
    }
    var clipboard = global.navigator?.clipboard;
    if (!clipboard || typeof clipboard.writeText !== "function") {
      return;
    }
    /** @param {string} tip @param {boolean} copied */
    function feedback(tip, copied) {
      if (copied && btn.classList) {
        btn.classList.add("copied");
      }
      if (btn.dataset) {
        btn.dataset.tipText = tip;
      }
      setTimeout(() => {
        if (btn.classList) {
          btn.classList.remove("copied");
        }
        if (btn.dataset) {
          btn.dataset.tipText = "Copy content";
        }
      }, 1500);
    }
    clipboard.writeText(text).then(
      () => feedback("Copied!", true),
      () => feedback("Copy failed", false),
    );
  }

  var _copyDelegationInstalled = false;
  if (global.document && typeof global.document.addEventListener === "function") {
    if (!_copyDelegationInstalled) {
      _copyDelegationInstalled = true;
      global.document.addEventListener("click", (e) => {
        var target = /** @type {Element | null} */ (e.target);
        if (!target || typeof target.closest !== "function") {
          return;
        }
        var btn = target.closest(".content-copy-btn[data-mb-copy]");
        if (btn) {
          _handleCopyClick(btn);
        }
      });
    }
  }

  async function fetchFolderEnvelope(path, signal) {
    const url = new URL("/api/file", global.location.origin);
    url.searchParams.set("path", path);
    const response = await fetch(url.toString(), { signal });
    if (!response.ok) {
      throw new global.MetabrowserRequestErrors.RequestError("Could not refresh this folder.", {
        operation: "fetchFolderEnvelope",
        status: response.status,
      });
    }
    return response.json();
  }

  const folderContext = global.MetabrowserResourceContext.createResourceContextStore({
    debounceMs: _rollupSettings().debounceMs,
    fetchEnvelope: fetchFolderEnvelope,
    pathsIntersect: global.MetabrowserInventoryScope.pathsIntersectScope,
  });

  const viewState = Object.freeze({
    isActive: global.MetabrowserViewState.isActive,
    subscribeActive: global.MetabrowserViewState.subscribeActive,
  });

  global.metabrowser = {
    builtins: {},
    registerView: registerView,
    getRegisteredView: getRegisteredView,
    listViewsForKind: listViewsForKind,
    render: render,
    escapeHtml: escapeHtml,
    fetchPluginData: fetchPluginData,
    fetchJsonl: fetchJsonl,
    fetchCompleteText: fetchCompleteText,
    fetchText: fetchText,
    fetchRollup: fetchRollup,
    watchRollup: watchRollup,
    errors: global.MetabrowserRequestErrors,
    folderContext: folderContext,
    directoryTotals: directoryTotals,
    viewState: viewState,
    setViewPrintState: global.MetabrowserViewState.setPrintState,
    ageBucket: ageBucket,
    ageLabelHtml: ageLabelHtml,
    tooltip: tooltip,
    fileTypeClass: fileTypeClass,
    fileTypeIcon: fileTypeIcon,
    fileCatalog: fileCatalog,
    navigation: global.MetabrowserNavigationRoute.navigation,
    repository: repository,
    fetchKpressRender: fetchKpressRender,
    renderTextTruncationWarning: renderTextTruncationWarning,
    renderTextLoadMoreFooter: renderTextLoadMoreFooter,
    renderSourceView: renderSourceView,
    partialNoticeHtml: partialNoticeHtml,
    loadKpressAssets: loadKpressAssets,
    ensureAsset: ensureAsset,
    ensureKindAssets: ensureKindAssets,
    kpressInitToc: kpressInitToc,
    formatKpressError: formatKpressError,
    chart: chart,
    formatSize: formatSize,
    formatInteger: formatInteger,
    formatFileCount: formatFileCount,
    formatTimestamp: formatTimestamp,
    countClass: countClass,
    sizeClass: sizeClass,
    sizeHtml: sizeHtml,
    isLargeTextPreview: isLargeTextPreview,
    highlightSyntax: highlightSyntax,
    wrapWithCopy: wrapWithCopy,
    icons: icons,
    perf: perf,
    prefs: prefs,
    filters: filters,
    fileTypes: fileTypes,
    langForExtension: langForExtension,
    langForPath: langForPath,
  };
})(typeof window !== "undefined" ? window : globalThis);
