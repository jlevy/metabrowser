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
//     dispose() [optional]
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
//     fetchPluginData(plugin, route, p)  — GET /api/plugin/<plugin>/<route>
//     fetchJsonl(path, opts)             — GET /api/file?path=... (JSONL envelope)
//     fetchKpressRender(ctx, view, opts) — GET /api/kpress/render?path=...
//     renderTextTruncationWarning(data) — print-visible source truncation warning
//
//   Navigation:
//     openPath(path)                     — open a path in the preview pane
//
//   Formatting:
//     formatSize(bytes)                  — "1.5 KB" / "2.3 MB" / etc.
//     formatTimestamp(secondsSinceEpoch) — local-time short form
//     sizeHtml(bytes, extraClass?)       — formatSize wrapped in <span class=size>
//     isLargeTextPreview(data)           — true if /api/file payload exceeds the
//                                          syntax-highlight cutoff
//
//   Visual:
//     icons.<name>                       — raw SVG strings for built-in icons
//     icons.withClass(name, cls)         — returns SVG with extra class applied
//
//   Diagnostics:
//     perf.measure(label, fn)            — wrap a render closure with timing logs
//     perf.measureAsync(label, fn)       — async timing wrapper
//
// Plugins register from index.js with code like:
//   const mb = window.metabrowser;
//   mb.registerView("analysis-report", "visual", { render: (c, ctx) => ... });
//
// Templates are Mustache (`{{name}}` for variables and `{{#items}}…{{/items}}`
// for sections). Auto-escaping is on by default.

((global) => {
  if (global.metabrowser) {
    // Already initialized; protect against double-load.
    return;
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

  async function fetchPluginData(plugin, route, params) {
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
    const resp = await fetch(url.toString(), { method: "GET" });
    if (!resp.ok) {
      throw new Error(`fetchPluginData ${plugin}/${route}: ${resp.status}`);
    }
    const data = await resp.json();
    if (data && data.type === "plugin_error") {
      throw new Error(
        (data.error || "Plugin data hook failed") + (data.detail ? `: ${data.detail}` : ""),
      );
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

  function openPath(path) {
    if (typeof path !== "string" || !path) {
      throw new Error("openPath: path must be a non-empty string");
    }
    global.dispatchEvent(
      new global.CustomEvent("metabrowser:open-path", { detail: { path: path } }),
    );
  }

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
      debounceMs: settings.ROLLUP_WATCH_DEBOUNCE_MS || ROLLUP_FALLBACK_DEBOUNCE_MS,
    };
  }

  async function fetchRollup(path, opts) {
    // Core rollup endpoint for directory subtrees (see /api/rollup).
    // ``path`` may be "" for the served root. Optional opts:
    // depth / top / ext_top query overrides plus ``signal`` for aborts.
    if (typeof path !== "string") {
      throw new Error("fetchRollup: path must be a string");
    }
    const defaults = _rollupSettings();
    const options = opts && typeof opts === "object" ? opts : {};
    const url = new URL("/api/rollup", global.location.origin);
    url.searchParams.set("path", path);
    for (const key of ["depth", "top", "ext_top"]) {
      const value = options[key] !== undefined ? options[key] : defaults[key];
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
    const resp = await fetch(url.toString(), { signal: options.signal });
    if (!resp.ok) {
      throw new Error(`fetchRollup ${path || "<root>"}: ${resp.status}`);
    }
    return resp.json();
  }

  function _pathsIntersectScope(changedPaths, scopePath) {
    // A change matters when it is the scope itself, inside it, or an
    // ancestor of it — ancestor aggregate upserts are how deep changes
    // surface at the shell's depth-2 event scope.
    if (!Array.isArray(changedPaths)) {
      return true; // snapshot / resync: treat as "anything changed"
    }
    for (const changed of changedPaths) {
      if (typeof changed !== "string") {
        continue;
      }
      if (
        changed === scopePath ||
        scopePath === "" ||
        changed === "" ||
        changed.startsWith(`${scopePath}/`) ||
        scopePath.startsWith(`${changed}/`)
      ) {
        return true;
      }
    }
    return false;
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
    const debounceMs =
      typeof options.debounceMs === "number" ? options.debounceMs : _rollupSettings().debounceMs;
    let disposed = false;
    let timer = null;
    let controller = null;
    let stale = false;

    async function refresh() {
      if (disposed) {
        return;
      }
      stale = false;
      if (controller) {
        controller.abort();
      }
      controller = typeof AbortController !== "undefined" ? new AbortController() : null;
      try {
        const envelope = await fetchRollup(
          path,
          Object.assign({}, options, { signal: controller ? controller.signal : undefined }),
        );
        if (!disposed) {
          onUpdate(envelope);
        }
      } catch (err) {
        const isAbort = err instanceof Error && err.name === "AbortError";
        if (!disposed && !isAbort) {
          console.warn("watchRollup refresh failed:", err);
        }
      }
    }

    function onInventoryChange(event) {
      if (disposed) {
        return;
      }
      const detail = event && event.detail ? event.detail : {};
      if (!_pathsIntersectScope(detail.paths, path)) {
        return;
      }
      if (timer) {
        clearTimeout(timer);
      }
      timer = setTimeout(() => {
        timer = null;
        if (typeof options.active === "function" && !options.active()) {
          // Hidden view: remember that data went stale, spend nothing.
          stale = true;
          return;
        }
        refresh();
      }, debounceMs);
    }

    global.addEventListener("metabrowser:inventory-change", onInventoryChange);
    refresh();
    return {
      refresh: refresh,
      stale() {
        return stale;
      },
      dispose() {
        disposed = true;
        global.removeEventListener("metabrowser:inventory-change", onInventoryChange);
        if (timer) {
          clearTimeout(timer);
          timer = null;
        }
        if (controller) {
          controller.abort();
          controller = null;
        }
      },
    };
  }

  // Shell-surface proxies — same pattern as `icons`: plugins reach the
  // shared tooltip and file-type classifier through the SDK so they
  // never touch app.js globals directly, and get safe no-ops when the
  // shell has not installed them (tests, partial harnesses).
  const tooltip = {
    show(html, event) {
      if (global.MetabrowserTooltip) {
        global.MetabrowserTooltip.show(html, event);
      }
    },
    move(event) {
      if (global.MetabrowserTooltip) {
        global.MetabrowserTooltip.move(event);
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

  // ── Preferences ─────────────────────────────────────────────────
  //
  // Versioned display-preference storage that survives across
  // Metabrowser instances. Every served root runs on its own port and
  // therefore its own browser origin, so localStorage silos per
  // folder; host-only cookies ignore the port (the mechanism the
  // theme already uses) and share small preferences across every
  // local instance. Values are JSON, size-bounded, and versioned;
  // consumers never learn which backend stores them. Not for
  // sensitive data or absolute paths.
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

  const prefs = { get: prefsGet, set: prefsSet };

  function formatKpressError(payload, status) {
    const body = payload && typeof payload === "object" ? payload : {};
    const base = body.error || "KPress render failed";
    const detail = body.detail || "";
    return `${base + (detail ? `: ${detail}` : "")} (HTTP ${status})`;
  }

  function renderTextTruncationWarning(data) {
    if (!data) {
      return "";
    }
    const totalBytes = data.size_uncompressed || data.logical_size || data.size || 0;
    const bytesRead = data.bytes_read || data.content_bytes || 0;
    const truncated =
      !!data.content_truncated ||
      (typeof data.bytes_read === "number" && totalBytes > 0 && bytesRead < totalBytes);
    if (!truncated) {
      return "";
    }
    const loadedLabel = formatSize(bytesRead);
    const totalLabel = formatSize(totalBytes);
    return (
      '<div class="metabrowser-source-truncation-warning" role="status">' +
      "<strong>Source preview truncated.</strong> " +
      "Printed output includes only " +
      escapeHtml(loadedLabel) +
      " of " +
      escapeHtml(totalLabel) +
      ". " +
      "Load the remaining text before printing a complete source PDF." +
      "</div>"
    );
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

  // KPress ships standalone-page runtime scripts. theme.js is still skipped in
  // the embedded host — it writes data-kpress-resolved-theme onto <html> from
  // the viewer's system preference, fighting metabrowser's own theme toggle
  // (applyThemeMode owns those attributes). toc.js is NOT skipped: metabrowser
  // marks its preview pane as the kpress document viewport, so toc.js drives the
  // sidebar/drawer, scroll-spy, and toggle against the pane (see kpressInitToc).
  const _SKIP_EMBEDDED_KPRESS_JS = ["theme.js"];

  function _isSkippedKpressScript(asset, url) {
    return _SKIP_EMBEDDED_KPRESS_JS.some(
      (name) => asset?.id === `js/${name}` || url.endsWith(`/${name}`),
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
      if (_isSkippedKpressScript(asset, url)) {
        continue;
      }
      if (_isTocScript(asset, url)) {
        await _loadKpressTocModule(url);
        continue;
      }
      await _loadScript(url, asset.loading);
    }
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
    const root = global.document?.documentElement;
    const themeMode = options?.themeMode || root?.getAttribute?.("data-theme-mode") || "system";
    const resolvedTheme = options?.resolvedTheme || root?.getAttribute?.("data-theme") || "light";
    url.searchParams.set("theme_mode", themeMode);
    url.searchParams.set("resolved_theme", resolvedTheme);

    const dedupKey = options?.dedupKey || path;
    const previous = _kpressInflight.get(dedupKey);
    if (previous) {
      previous.abort();
    }
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    if (controller) {
      _kpressInflight.set(dedupKey, controller);
    }

    let resp;
    try {
      resp = await fetch(url.toString(), {
        method: "GET",
        signal: controller ? controller.signal : undefined,
      });
    } finally {
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

  function chart(container, type, data, options) {
    if (typeof global.Chart === "undefined") {
      throw new Error("metabrowser.chart: Chart.js is not loaded");
    }
    // Container can be either a <canvas> or a <div> we'll create a canvas in.
    let canvas;
    if (container instanceof HTMLCanvasElement) {
      canvas = container;
    } else {
      canvas = global.document.createElement("canvas");
      container.appendChild(canvas);
    }
    return new global.Chart(canvas, { type: type, data: data, options: options || {} });
  }

  function formatSize(bytes) {
    // Match the convention used everywhere else in the shell so plugin
    // displays line up visually.
    const n = Number(bytes) || 0;
    if (n < 1024) {
      return `${n} B`;
    }
    if (n < 1024 * 1024) {
      return `${(n / 1024).toFixed(1)} KB`;
    }
    return `${(n / (1024 * 1024)).toFixed(1)} MB`;
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

  // Single source of truth for the "large file = bold size, small file
  // = normal" rule used everywhere a size badge is rendered. Threshold
  // matches the shell's SIZE_LARGE_THRESHOLD (1 MiB).
  const SIZE_LARGE_THRESHOLD = 1024 * 1024;

  function sizeClass(bytes) {
    return (bytes || 0) > SIZE_LARGE_THRESHOLD ? "size-large" : "";
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

  // Threshold for syntax-highlight bypass. Mirrors app.js's
  // SYNTAX_HIGHLIGHT_MAX_BYTES so plugins make the same call about
  // whether a file is too big to highlight client-side. Files larger
  // than this fall back to escaped <pre> rendering.
  const SYNTAX_HIGHLIGHT_MAX_BYTES = 512 * 1024;

  function isLargeTextPreview(data) {
    if (!data) {
      return false;
    }
    return (
      !!data.content_truncated ||
      !!data.highlight_disabled ||
      (data.size || 0) > SYNTAX_HIGHLIGHT_MAX_BYTES ||
      (typeof data.content === "string" && data.content.length > SYNTAX_HIGHLIGHT_MAX_BYTES)
    );
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
      '<button class="content-copy-btn" data-mb-copy="wrap" title="Copy content">' +
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

  // Performance probe — wraps a render closure so the perf overlay
  // (when enabled via the perf.js gate) can show plugin render time.
  // No-op when perf.js isn't loaded; never throws.
  const perf = {
    measure(label, fn) {
      const probe =
        global._mbPerf && typeof global._mbPerf.measure === "function" ? global._mbPerf : null;
      if (probe) {
        return probe.measure(label, fn);
      }
      return fn();
    },
    measureAsync(label, fn) {
      const probe =
        global._mbPerf && typeof global._mbPerf.measureAsync === "function" ? global._mbPerf : null;
      if (probe) {
        return probe.measureAsync(label, fn);
      }
      return fn();
    },
  };

  // File-extension → highlight.js language id. Single source of truth so
  // every plugin uses the same `language-X` class for `.py`, `.ts`, etc.
  const LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".json": "json",
    ".jsonl": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".md": "markdown",
    ".css": "css",
    ".html": "xml",
  };

  function langForExtension(ext) {
    return LANG_MAP[ext || ""] || "";
  }

  // Delegated click handler for the copy buttons wrapWithCopy emits.
  // Fully SDK-owned: no reference to shell globals, so the documented
  // wrapWithCopy behavior cannot change when app.js internals do. Scoped
  // to buttons carrying data-mb-copy so plugin- or shell-built copy
  // buttons with their own listeners are never double-handled.
  /** @param {Element & {classList?: DOMTokenList, title?: string}} btn */
  function _handleCopyClick(btn) {
    var wrap = typeof btn.closest === "function" ? btn.closest(".content-copy-wrap") : null;
    if (!wrap) {
      return;
    }
    var code = typeof wrap.querySelector === "function" ? wrap.querySelector("code") : null;
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
    /** @param {string} title @param {boolean} copied */
    function feedback(title, copied) {
      if (copied && btn.classList) {
        btn.classList.add("copied");
      }
      btn.title = title;
      setTimeout(() => {
        if (btn.classList) {
          btn.classList.remove("copied");
        }
        btn.title = "Copy content";
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

  global.metabrowser = {
    builtins: {},
    registerView: registerView,
    getRegisteredView: getRegisteredView,
    listViewsForKind: listViewsForKind,
    render: render,
    escapeHtml: escapeHtml,
    fetchPluginData: fetchPluginData,
    fetchJsonl: fetchJsonl,
    fetchRollup: fetchRollup,
    watchRollup: watchRollup,
    ageBucket: ageBucket,
    ageLabelHtml: ageLabelHtml,
    tooltip: tooltip,
    fileTypeClass: fileTypeClass,
    prefs: prefs,
    openPath: openPath,
    fetchKpressRender: fetchKpressRender,
    renderTextTruncationWarning: renderTextTruncationWarning,
    loadKpressAssets: loadKpressAssets,
    kpressInitToc: kpressInitToc,
    formatKpressError: formatKpressError,
    chart: chart,
    formatSize: formatSize,
    formatTimestamp: formatTimestamp,
    sizeHtml: sizeHtml,
    isLargeTextPreview: isLargeTextPreview,
    wrapWithCopy: wrapWithCopy,
    icons: icons,
    perf: perf,
    langForExtension: langForExtension,
  };
})(typeof window !== "undefined" ? window : globalThis);
