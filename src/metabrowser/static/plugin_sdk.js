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
  const _loadedKpressAssets = new Set();

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
      "/api/plugin/" + encodeURIComponent(plugin) + "/" + encodeURIComponent(route),
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
      throw new Error("fetchPluginData " + plugin + "/" + route + ": " + resp.status);
    }
    const data = await resp.json();
    if (data && data.type === "plugin_error") {
      throw new Error(
        (data.error || "Plugin data hook failed") + (data.detail ? ": " + data.detail : ""),
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
      throw new Error("fetchJsonl " + path + ": " + resp.status);
    }
    const data = await resp.json();
    if (data && data.type !== "jsonl") {
      throw new Error("fetchJsonl " + path + ": expected JSONL, got type=" + (data.type || "?"));
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

  function formatKpressError(payload, status) {
    const body = payload && typeof payload === "object" ? payload : {};
    const base = body.error || "KPress render failed";
    const detail = body.detail || "";
    return base + (detail ? ": " + detail : "") + " (HTTP " + status + ")";
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

  function _loadStylesheet(url) {
    if (!url || _loadedKpressAssets.has(url) || !global.document) {
      return Promise.resolve();
    }
    const parent = _headOrBody();
    if (!parent || typeof global.document.createElement !== "function") {
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const link = global.document.createElement("link");
      link.rel = "stylesheet";
      link.href = url;
      link.setAttribute("data-kpress-asset", "");
      link.onload = () => resolve();
      // Some browsers don't fire onload for cached stylesheets — onerror is the
      // only signal we get for a hard failure, so reject on it.
      link.onerror = () => reject(new Error("Failed to load KPress stylesheet: " + url));
      parent.appendChild(link);
      _loadedKpressAssets.add(url);
    });
  }

  function _loadScript(url) {
    if (!url || _loadedKpressAssets.has(url) || !global.document) {
      return Promise.resolve();
    }
    const parent = _headOrBody();
    if (!parent || typeof global.document.createElement !== "function") {
      return Promise.resolve();
    }
    return new Promise((resolve, reject) => {
      const script = global.document.createElement("script");
      script.type = "module";
      script.src = url;
      script.async = false;
      script.setAttribute("data-kpress-asset", "");
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Failed to load KPress asset: " + url));
      parent.appendChild(script);
      _loadedKpressAssets.add(url);
    });
  }

  // KPress ships standalone-page runtime scripts. theme.js is still skipped in
  // the embedded host — it writes data-kpress-resolved-theme onto <html> from
  // the viewer's system preference, fighting metabrowser's own theme toggle
  // (applyThemeMode owns those attributes). toc.js is NOT skipped: metabrowser
  // marks its preview pane as the kpress document viewport, so toc.js drives the
  // sidebar/drawer, scroll-spy, and toggle against the pane (see kpressInitToc).
  const _SKIP_EMBEDDED_KPRESS_JS = ["theme.js"];

  function _isSkippedKpressScript(url) {
    return _SKIP_EMBEDDED_KPRESS_JS.some((name) => url.endsWith("/" + name));
  }

  // toc.js is loaded via dynamic import (not a <script> tag) so we can capture
  // its initKpressToc export and drive it per rendered document. Its load-time
  // self-init runs once against the page; per-render wiring + teardown is owned
  // by kpressInitToc below.
  let _kpressInitTocFn = null;
  function _isTocScript(url) {
    return url.endsWith("/toc.js");
  }
  async function _loadKpressTocModule(url) {
    if (_loadedKpressAssets.has(url)) {
      return;
    }
    _loadedKpressAssets.add(url);
    try {
      const mod = await import(url);
      if (mod && typeof mod.initKpressToc === "function") {
        _kpressInitTocFn = mod.initKpressToc;
      }
    } catch (err) {
      // A failed TOC module must not break document rendering; the doc still
      // shows, just without sidebar/drawer behavior.
      if (global.console?.warn) {
        global.console.warn("metabrowser: failed to load kpress toc.js", err);
      }
    }
  }

  async function loadKpressAssets(assets) {
    const css = assets?.css || [];
    const js = assets?.js || [];
    for (const url of css) {
      await _loadStylesheet(url);
    }
    for (const url of js) {
      if (_isSkippedKpressScript(url)) {
        continue;
      }
      if (_isTocScript(url)) {
        await _loadKpressTocModule(url);
        continue;
      }
      await _loadScript(url);
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
    await loadKpressAssets(payload.assets || {});
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
      return n + " B";
    }
    if (n < 1024 * 1024) {
      return (n / 1024).toFixed(1) + " KB";
    }
    return (n / (1024 * 1024)).toFixed(1) + " MB";
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
      const pendCls = ("size tally-pending " + (extraClass || "")).trim();
      return '<span class="' + pendCls + '"></span>';
    }
    const cls = ("size " + sizeClass(bytes) + " " + (extraClass || "")).trim();
    return '<span class="' + cls + '">' + formatSize(bytes) + "</span>";
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
    // copyContent is defined in app.js (the shell); plugins emit an
    // onclick="copyContent(this)" handler that resolves at click time
    // against the global, so the function reference doesn't need to
    // exist when this string is built.
    return (
      '<div class="content-copy-wrap">' +
      '<button class="content-copy-btn" onclick="copyContent(this)" title="Copy content">' +
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

  global.metabrowser = {
    registerView: registerView,
    getRegisteredView: getRegisteredView,
    listViewsForKind: listViewsForKind,
    render: render,
    escapeHtml: escapeHtml,
    fetchPluginData: fetchPluginData,
    fetchJsonl: fetchJsonl,
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
