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
//   plugins.load(name)                   — a required plugin's index.js exports
//
//   View lifecycle ("Registration and Lifecycle" in docs/plugins.md):
//     render(container, ctx)             — own container; may return a Promise, or a
//                                          handle with ready and dispose()
//     dispose(container)                 — the pane was replaced, never on a tab switch:
//                                          release listeners, requests, and timers
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
//     onInventoryChange(listener)         — each filesystem change the shell observes:
//                                          listener(paths), the changed entries with
//                                          their ancestors, or null when anything may
//                                          have changed, as on every reconnect; returns
//                                          an unsubscribe function
//     sourceKind()                        — filesystem or git_revision served source
//     repository                          — verified GitHub identity for the served tree
//
//   Formatting:
//     formatSize(bytes)                  — "1.5 KB" / "2.3 MB" / etc.
//     formatAge(secondsSinceEpoch, opts?) — the age primitive: {label, className}
//     formatTimestamp(secondsSinceEpoch) — local-time short form
//     titleNodes(title)                  — a commit or PR title's nodes: a conventional-
//                                          commit prefix in span.title-prefix, then the rest
//     shortCommit(commit)                — a commit ID as every line names one, for an
//                                          element of class git-commit-sha
//     countPartsNodes(parts)             — a count summary's nodes: the shell's one
//                                          painter of them
//     changeLine(change)                 — a brief change line, "10 A, 5 D, 4 M · +1,234
//                                          −567", from statuses and line totals
//     changeLineNodes(line, options?)    — its nodes, the shell's one component for it
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
//     refChip/refChipHtml(name, opts?)    — structured refs with action menus
//     mergeRefs(source, target, opts?)    — a merge as source → target, left to right
//     mountRefMenus(primary, host)        — sibling controls; caller owns returned disposer
//     actorIdentity(name, opts?)          — a person: an avatar's box, then the bold name,
//                                          the person glyph in the box without an avatar
//     actorIdentityHtml(name, opts?)      — its markup, the box holding the glyph
//     mountCounterpart(corner, page)      — a page's View on GitHub button in a corner
//     prefetchCounterpart(page)           — ask for it before the header is drawn
//     counterpartButton(counterpart)      — the button, from the server's answer
//     filterControls                      — shared filter markup and interaction
//                                          helpers, installed before plugins load
//     filterControls.typeMenu             — File type menu rows from a tally
//                                          for the Files tab and diffs
//     class="disclosure-toggle"           — on any control that shows or hides
//                                          content: the host stylesheet keeps it from
//                                          selecting text, even on a double or triple
//                                          click
//
//   Keyboard ("Keyboard Shortcuts" in docs/plugins.md):
//     shortcuts.attach(element, spec)     — a letter key and badge for a view's control,
//                                          or with `numbered: true` a positional
//                                          number; returns {retarget, detach}
//
//   Diagnostics:
//     perf.measure(label, fn)            — contribute a synchronous named span
//     perf.measureAsync(label, fn)       — contribute an asynchronous named span
//     perf.report()/responsiveness()     — inspect the active browser profile
//     debug                              — console-only shell troubleshooting helpers
//
// The helpers that build a view's markup -- renderSourceView, wrapWithCopy,
// partialNoticeHtml, refChip/refChipHtml/mergeRefs/mountRefMenus,
// actorIdentity/actorIdentityHtml, counterpartButton/mountCounterpart,
// ageBucket/ageLabel/ageLabelHtml/retellAge,
// renderTextTruncationWarning, renderTextLoadMoreFooter, langForPath
// and langForExtension -- and the syntax service, highlightSyntax and
// isLargeTextPreview, are defined in plugin-sdk-views.js, which is not a startup
// script. It is on this object before any plugin's code runs: see loadPluginsForKind.
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
  /** Bounds a missing manifest-owned plugin asset load/error event. */
  const _pluginAssetLoadTimeoutMs = 10_000;
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
    truncated: false,
  });
  /** @type {{snapshot: () => unknown, subscribe: (listener: () => void) => () => void} | null} */
  let _attachedFileCatalog = null;
  // The server's plugin table (`_build_plugin_asset_config_block`), by name and by kind.
  /** @type {Map<string, MetabrowserPluginAssets>} */
  let _plugins = new Map();
  /** @type {Map<string, string[]>} */
  let _pluginKinds = new Map();
  /** @type {Map<string, Promise<object>>} */
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
  // Plugin keys until static/plugin-shortcuts.js loads and takes them: 252 bytes of
  // startup transfer, by devtools/check_startup_scripts.py.
  const _shortcutQueue = new Set();
  function queueShortcut(element, options) {
    const facade = global.MetabrowserPluginShortcuts;
    if (facade) {
      return facade.attachShortcut(element, options);
    }
    const queued = { element, options };
    _shortcutQueue.add(queued);
    options?.signal?.addEventListener?.("abort", () => _shortcutQueue.delete(queued));
    return {
      retarget(next) {
        queued.element = next;
        queued.handle?.retarget(next);
      },
      detach() {
        _shortcutQueue.delete(queued);
        queued.handle?.detach();
      },
    };
  }
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
      let settled = false;
      /** @type {ReturnType<typeof setTimeout> | null} */
      let readyPoll = null;
      /** @type {ReturnType<typeof setTimeout> | null} */
      let loadTimeout = null;

      const settle = () => {
        if (settled) {
          return;
        }
        settled = true;
        if (readyPoll !== null) {
          clearTimeout(readyPoll);
        }
        if (loadTimeout !== null) {
          clearTimeout(loadTimeout);
        }
        resolve(undefined);
      };
      /** @param {string} reason */
      const fail = (reason) => {
        if (settled) {
          return;
        }
        console.error(`metabrowser plugin asset failed to load: ${url} (${reason})`);
        settle();
      };
      const detectCachedStylesheet = () => {
        if (settled || tagName !== "link") {
          return;
        }
        if ("sheet" in element && element.sheet) {
          settle();
          return;
        }
        readyPoll = setTimeout(detectCachedStylesheet, _stylesheetReadyPollMs);
      };

      for (const [name, value] of Object.entries(attributes || {})) {
        element.setAttribute(name, value);
      }
      element.addEventListener("load", settle, { once: true });
      element.addEventListener("error", () => fail("error event"), { once: true });
      if (tagName === "link") {
        element.setAttribute("href", url);
      } else {
        element.setAttribute("src", url);
      }
      loadTimeout = setTimeout(() => fail("timed out"), _pluginAssetLoadTimeoutMs);
      global.document.head.append(element);
      detectCachedStylesheet();
    });
  }

  /** @param {{plugins: Record<string, MetabrowserPluginAssets>, kinds: Record<string, string[]>}} config */
  function configureAssets(config) {
    _plugins = new Map(Object.entries(config.plugins));
    _pluginKinds = new Map(Object.entries(config.kinds));
    for (const [kind, names] of _pluginKinds) {
      for (const name of names) {
        if (!_plugins.has(name)) {
          throw new TypeError(`configureAssets: ${kind} names no plugin ${name}`);
        }
      }
    }
  }

  /** @type {Map<string, Promise<unknown>>} */
  const _pluginStyleLoads = new Map();

  // Fetch what a plugin's code does not have to wait for: its stylesheets, and its
  // module through `modulepreload`, which does not evaluate it.
  function _startPluginAssets(descriptor) {
    const started = _pluginStyleLoads.get(descriptor.name);
    if (started) {
      return started;
    }
    const styles = Promise.all(
      descriptor.styles.map((url, index) =>
        _loadPluginElement("link", url, {
          "data-metabrowser-plugin-asset": `${descriptor.name}:style:${index}`,
          rel: "stylesheet",
        }),
      ),
    );
    _pluginStyleLoads.set(descriptor.name, styles);
    const preload = global.document.createElement("link");
    preload.setAttribute("rel", "modulepreload");
    preload.setAttribute("href", descriptor.module);
    global.document.head.append(preload);
    return styles;
  }

  function _loadPlugin(descriptor) {
    const existing = _pluginLoads.get(descriptor.name);
    if (existing) {
      return existing;
    }
    const loading = (async () => {
      await _startPluginAssets(descriptor);
      for (let index = 0; index < descriptor.scripts.length; index += 1) {
        await _loadPluginElement("script", descriptor.scripts[index], {
          "data-metabrowser-plugin-asset": `${descriptor.name}:script:${index}`,
        });
      }
      try {
        return await import(descriptor.module);
      } catch (error) {
        console.error(`metabrowser plugin failed to load: ${descriptor.name}`, error);
        throw error;
      }
    })();
    _pluginLoads.set(descriptor.name, loading);
    return loading;
  }

  // Both synchronous rendering helpers are ready before any plugin code runs.
  // Demand joins Mustache's idle prefetch; neither asset is an eager script.
  /** @returns {Promise<void>} */
  function _ensureViewHelpers() {
    const views =
      typeof global.metabrowser.renderSourceView === "function"
        ? Promise.resolve()
        : ensureAsset("sdk-views");
    return Promise.all([views, ensureAsset("mustache")]).then(() => {});
  }

  // The helpers gate each plugin's code, not its transfer. Rejects when they cannot
  // be loaded: no plugin's code has run then, and the next call tries again.
  async function loadPluginsForKind(kind) {
    const descriptors = (_pluginKinds.get(kind) || []).flatMap((name) => _plugins.get(name) || []);
    const helpers = _ensureViewHelpers();
    for (const descriptor of descriptors) {
      if (!_pluginLoads.has(descriptor.name)) {
        void _startPluginAssets(descriptor);
      }
    }
    await helpers;
    for (const descriptor of descriptors) {
      await _loadPlugin(descriptor).catch(() => {});
    }
  }

  // "Declared Dependencies" in docs/plugins.md.
  async function loadPluginExports(name) {
    const descriptor = _plugins.get(name);
    if (!descriptor) {
      throw new Error(`plugins.load: no plugin ${name}`);
    }
    await _ensureViewHelpers();
    return _loadPlugin(descriptor);
  }

  // Load more actions by name. A partial-content notice's button names one; the SDK's
  // delegated listener runs it only for the button the notice built, and a name nobody
  // registered does nothing. The shell registers its text loader through the private
  // host; a view that continues its own content passes `action: null` and wires its own.
  /** @type {Map<string, () => unknown>} */
  const _loadMoreActions = new Map();

  /** @param {string} name @param {() => unknown} action */
  function registerLoadMoreAction(name, action) {
    if (!/^[A-Za-z_$][\w$]*$/.test(name) || typeof action !== "function") {
      throw new TypeError("registerLoadMoreAction: a function and its identifier name");
    }
    _loadMoreActions.set(name, action);
  }

  // The document-wide delegates below (copy, Load more, and the shell's address
  // controls) act only on an element application or plugin code created.
  // No static marker can say so: a trusted folder's Markdown keeps class, id, and
  // data-* through KPress, so it could spell any attribute this code writes and turn
  // a click into a clipboard write or an application action. This value is drawn when
  // the page loads, after every document was written, so authored markup cannot
  // carry it. Web Crypto is always present in a browser; a browserless test realm
  // may lack it, and there any value serves.
  const _delegateOwner = (() => {
    const bytes = new Uint8Array(16);
    if (typeof global.crypto?.getRandomValues === "function") {
      global.crypto.getRandomValues(bytes);
    } else {
      bytes.forEach((_byte, index) => {
        bytes[index] = Math.floor(Math.random() * 256);
      });
    }
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  })();

  /** Markup for a delegated control: ` data-mb-owner="…"`, set only by page code. */
  function delegateOwnerAttribute() {
    return ` data-mb-owner="${_delegateOwner}"`;
  }

  // The elements `ownDelegate` marked, by identity. The owner value is a string a
  // trusted document's stylesheet can read and a document fetched later can then carry
  // (docs/project/architecture/arch-server-and-content.md), so where a check need not
  // admit markup page code wrote as text, as the tooltip inside a rendered document
  // does not, it asks for the element itself (`ownsElement`).
  /** @type {WeakSet<Element>} */
  const _ownedElements = new WeakSet();

  /**
   * Mark an element page code created as a delegated control.
   * @template {Element} T
   * @param {T} element
   * @returns {T}
   */
  function ownDelegate(element) {
    element.setAttribute("data-mb-owner", _delegateOwner);
    _ownedElements.add(element);
    return element;
  }

  /**
   * Whether *element* is one `ownDelegate` marked: the element, not a copy of its mark.
   * @param {Element | null | undefined} element
   */
  function ownsElement(element) {
    return !!element && _ownedElements.has(element);
  }

  /** @param {Element | null | undefined} element */
  function isOwnedDelegate(element) {
    return (
      !!element &&
      typeof element.getAttribute === "function" &&
      element.getAttribute("data-mb-owner") === _delegateOwner
    );
  }

  global.MetabrowserPluginHost = Object.freeze({
    attachFileCatalog,
    configureAssets,
    isOwnedDelegate,
    loadPluginsForKind,
    ownsElement,
    registerLoadMoreAction,
    shortcutQueue: _shortcutQueue,
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

  function sourceKind() {
    return global.METABROWSER_SOURCE_KIND === "git_revision" ? "git_revision" : "filesystem";
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
        // An array repeats its parameter, one value each (`cols=a&cols=b`), so a value
        // may hold any character, a comma among them.
        for (const item of Array.isArray(v) ? v : [v]) {
          if (item !== undefined && item !== null) {
            url.searchParams.append(k, String(item));
          }
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
    const responseBytes = Number(resp.headers?.get?.("content-length"));
    const decode = () => resp.json();
    const recorder = global.metabrowser?.perf;
    const data =
      typeof recorder?.measureAsync === "function"
        ? await recorder.measureAsync("pluginData:decode", decode, {
            plugin,
            response_bytes: Number.isFinite(responseBytes) ? responseBytes : null,
            route,
          })
        : await decode();
    if (data && data.type === "plugin_error") {
      /** @type {Error & {status?: number, payload?: unknown}} */
      const err = new Error(data.error || PLUGIN_DATA_FAILED);
      err.status = resp.status;
      err.payload = data;
      throw err;
    }
    return data;
  }

  const PLUGIN_DATA_FAILED = "Could not load this view's data.";
  const KPRESS_RENDER_FAILED = "This document could not be rendered.";

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
      schema: "file-type-registry-v5",
      schemaVersion: 5,
      revision: 0,
      fingerprint: "unavailable",
      maxExtensionComponents: 2,
      registryIdentity: Object.freeze({
        schemaVersion: 5,
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
    // ``path`` may be "" for the served root; opts may set the keys below,
    // over the settings' defaults, and ``signal``.
    if (typeof path !== "string") {
      throw new Error("fetchRollup: path must be a string");
    }
    const defaults = _rollupSettings();
    const options = opts && typeof opts === "object" ? opts : {};
    const url = new URL("/api/rollup", global.location.origin);
    url.searchParams.set("path", path);
    const keys = "depth top nodes ext_top filename_top remaining_top ext_rank ignored encoding";
    for (const key of keys.split(" ")) {
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

  /**
   * Call *listener* with each filesystem change the shell observes.
   *
   * The paths are inventory paths: each changed entry with every ancestor whose totals it
   * moved, down to the depth the shell watches, so a deeper change arrives as its deepest
   * watched ancestor. Null means anything may have changed: the stream reconnected,
   * whether or not its snapshot changed, or resynchronized, or the first crawl finished.
   * Returns an unsubscribe function.
   *
   * A host with no event target, such as a page that is not the shell, has no inventory
   * stream: the listener is never called, as the folder context's refresh is never
   * scheduled there.
   *
   * @param {(paths: ReadonlyArray<string> | null) => void} listener
   * @returns {() => void}
   */
  function onInventoryChange(listener) {
    if (typeof listener !== "function") {
      throw new TypeError("onInventoryChange: listener must be a function");
    }
    /** @param {Event} event */
    const handleChange = (event) => {
      const paths = /** @type {CustomEvent<{paths?: unknown}>} */ (event).detail?.paths;
      listener(
        Array.isArray(paths)
          ? Object.freeze(paths.filter((path) => typeof path === "string"))
          : null,
      );
    };
    if (typeof global.addEventListener !== "function") {
      return () => {};
    }
    global.addEventListener("metabrowser:inventory-change", handleChange);
    let subscribed = true;
    return () => {
      if (subscribed) {
        subscribed = false;
        global.removeEventListener("metabrowser:inventory-change", handleChange);
      }
    };
  }

  // Hear when *path* changes, through the page's one event stream (static/file-watches.js,
  // fetched on first use); returns a disposer. A pin's page has no stream: never called.
  function watchFile(path, options) {
    let dispose = null;
    let disposed = false;
    if (global.METABROWSER_SOURCE_KIND !== "git_revision") {
      ensureAsset("file-watches").then(
        () => {
          if (!disposed) {
            dispose = global.MetabrowserFileWatches.shared().watch(
              path,
              options,
              options.generation,
            );
          }
        },
        (error) => console.warn("metabrowser.watchFile:", error),
      );
    }
    return () => {
      disposed = true;
      dispose?.();
      dispose = null;
    };
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
    /**
     * Put the tooltip away. With `within`, a tooltip anchored at or inside it, or one
     * whose anchor has left the document, and never one shown with no anchor. With none,
     * any tooltip but one anchored in the nav's header. See docs/design-system.md, "A
     * Surface Puts Away Only Its Own Tooltip".
     */
    hide(within) {
      if (global.MetabrowserTooltip) {
        global.MetabrowserTooltip.hide(within);
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

  function formatKpressError(payload) {
    const body = payload && typeof payload === "object" ? payload : {};
    return typeof body.error === "string" && body.error ? body.error : KPRESS_RENDER_FAILED;
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

  /**
   * Whether the page itself links `url` as a stylesheet: a `<link>` the page was served
   * with, not one this loader appended (those carry data-kpress-asset and are tracked in
   * the loaded and loading sets).
   * @param {string} url
   * @returns {boolean}
   */
  function _pageLinksStylesheet(url) {
    const doc = global.document;
    if (typeof doc.querySelectorAll !== "function") {
      return false;
    }
    const wanted = new URL(url, doc.baseURI).href;
    const links = /** @type {NodeListOf<HTMLLinkElement>} */ (
      doc.querySelectorAll('link[rel~="stylesheet"]:not([data-kpress-asset])')
    );
    return Array.from(links).some((link) => link.href === wanted);
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
    // A sheet the page already links is loaded, and a second link would move its rules
    // later in the cascade. The shell's <head> links KPress's style-tokens.css before
    // static/styles.css, so the shell's :root tokens outrank KPress's same-named ones
    // (--font-sans, --font-mono, --kpress-print-page-margin). Linked again after
    // styles.css, KPress's would win from the first rendered document on.
    if (!_loadedKpressAssets.has(url) && _pageLinksStylesheet(url)) {
      _loadedKpressAssets.add(url);
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
      // The Markdown plugin imports KPress's diagram module itself, with the figures and
      // the Mermaid it supplies (builtin_plugins/markdown/diagrams.js, through the
      // `kpress-diagrams` module bundle at this same URL). Loaded here, it would bind its
      // zero-configuration behavior, which draws nothing without `globalThis.mermaid`.
      if (asset?.id === "js/diagrams.js" || url.endsWith("/diagrams.js")) {
        continue;
      }
      await _loadScript(url, asset.loading);
    }
  }

  // "Idle Work" in docs/project/architecture/arch-browser-shell.md.
  const IDLE_INPUT_QUIET_MS = 250;
  let _lastInput = -Infinity;
  const _viewSettled = new Promise((resolve) =>
    global.addEventListener?.("metabrowser:first-view-settled", resolve),
  );
  if (!global.requestIdleCallback) {
    for (const type of ["pointerdown", "keydown", "wheel"]) {
      global.addEventListener?.(type, () => (_lastInput = performance.now()), {
        capture: true,
        passive: true,
      });
    }
  }
  function whenIdle(callback, options) {
    const timeout = options?.timeout;
    if (global.requestIdleCallback) {
      const id = global.requestIdleCallback(() => callback(), { timeout });
      return () => global.cancelIdleCallback(id);
    }
    const deadline = performance.now() + (timeout ?? Infinity);
    let waiting = true;
    let timer;
    const check = () => {
      const now = performance.now();
      const wait = Math.min(_lastInput + IDLE_INPUT_QUIET_MS - now, deadline - now);
      timer = wait > 0 ? setTimeout(check, wait) : void callback();
    };
    const start = () => {
      if (waiting) {
        waiting = false;
        clearTimeout(timer);
        timer = setTimeout(check);
      }
    };
    _viewSettled.then(start);
    if (timeout !== undefined) {
      timer = setTimeout(start, timeout);
    }
    return () => {
      waiting = false;
      clearTimeout(timer);
    };
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

  // The namespace of an on-demand module bundle (asset-loader.js), such as the
  // vendored Mermaid entry, imported the first time a consumer asks for it.
  /** @param {string} name @returns {Promise<unknown>} */
  function ensureModule(name) {
    const assets = global.MetabrowserAssets;
    if (!assets || typeof assets.ensureModule !== "function") {
      return Promise.reject(new Error("metabrowser.ensureModule: asset loader is not available"));
    }
    return assets.ensureModule(name);
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
  // dispose on unmount. Returns null if toc.js has not loaded yet. *config* is
  // KPress's own per-binding configuration, such as the toggle's `visible` policy
  // the Markdown plugin supplies (builtin_plugins/markdown/toc-toggle.js).
  function kpressInitToc(container, config) {
    if (typeof _kpressInitTocFn !== "function" || !container) {
      return null;
    }
    try {
      return _kpressInitTocFn(container, config);
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
      payload = { error: KPRESS_RENDER_FAILED };
    }
    if (!resp.ok) {
      /** @type {Error & {status?: number, payload?: unknown}} */
      const err = new Error(formatKpressError(payload));
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

  function formatSize(bytes) {
    return global.MetabrowserFormatters.formatBytes(Number(bytes) || 0);
  }

  function formatInteger(value) {
    return global.MetabrowserFormatters.formatInteger(Number(value) || 0);
  }

  function formatFileCount(value) {
    return global.MetabrowserFormatters.formatFileCount(Number(value) || 0);
  }

  // The one age primitive (docs/design-system.md, "Age"): the abbreviation and the
  // freshness class that owns its hue, weight, size, and numerals.
  /** @param {number} secondsSinceEpoch @param {MetabrowserAgeOptions} [options] */
  function formatAge(secondsSinceEpoch, options) {
    return global.MetabrowserFormatters.age(Number(secondsSinceEpoch) || 0, options);
  }

  // A commit's or pull request's title, for its element to hold: a conventional-commit
  // prefix at regular weight in `span.title-prefix`, then the rest at the title's own weight
  // (docs/design-system.md, "Titles"). The nodes belong to the page's document.
  /** @param {string} title @returns {Array<Node | string>} */
  function titleNodes(title) {
    return global.MetabrowserFormatters.titleNodes(global.document, title);
  }

  // A commit ID as every line names one: its first characters, the shell's one length
  // (docs/design-system.md, "Short Commit IDs"). Shown, it is in the commit-ID face,
  // `.git-commit-sha`, and its full ID is a copy or a link away.
  /** @param {string} commit @returns {string} */
  function shortCommit(commit) {
    return global.MetabrowserFormatters.shortCommit(commit);
  }

  // The shell's painters of a count summary and a brief change line, into the page's
  // document (docs/design-system.md, "Count Summaries Bold Their Numbers", "Brief Change
  // Line").
  /** @param {MetabrowserCountParts} parts @returns {Array<Node | string>} */
  function countPartsNodes(parts) {
    return global.MetabrowserFormatters.countPartsNodes(global.document, parts);
  }

  /** @param {MetabrowserChangeLineInput} change */
  function changeLine(change) {
    const formatters = global.MetabrowserFormatters;
    return formatters.changeLine(change, formatters.formatInteger);
  }

  /**
   * @param {MetabrowserChangeLine} line
   * @param {MetabrowserChangeLineOptions} [options]
   * @returns {Array<Node | string>}
   */
  function changeLineNodes(line, options) {
    return global.MetabrowserFormatters.changeLineNodes(global.document, line, options);
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
    if (bytes === undefined) {
      return "";
    }
    if (bytes === null) {
      // The provider emits null aggregates while a directory is still
      // finalizing; render as a skeleton cell so the row paints
      // with shape; the SSE fs.change patch flow replaces it in place.
      const pendCls = `size tally-pending ${extraClass || ""}`.trim();
      return `<span class="${pendCls}"></span>`;
    }
    const cls = `size ${sizeClass(bytes)} ${extraClass || ""}`.trim();
    return `<span class="${cls}">${formatSize(bytes)}</span>`;
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

  /** @param {HTMLElement} btn */
  function _handleCopyClick(btn) {
    var mode = btn.dataset.mbCopy || "";
    var text = "";
    if (mode === "text") {
      text = btn.dataset.mbCopyText || "";
    } else if (mode === "wrap") {
      const wrap = btn.closest(".content-copy-wrap");
      if (!wrap) {
        return;
      }
      const code = wrap.querySelector("[data-mb-copy-payload]") || wrap.querySelector("code");
      text = code ? code.textContent || "" : "";
      if (!text) {
        // No <code> child: copy the wrap's text minus the button's label.
        const nodes = wrap.childNodes || [];
        for (let ci = 0; ci < nodes.length; ci++) {
          if (nodes[ci] !== btn) {
            text += nodes[ci].textContent || "";
          }
        }
      }
    } else {
      return;
    }
    var clipboard = global.navigator?.clipboard;
    if (!clipboard || typeof clipboard.writeText !== "function") {
      return;
    }
    showCopyResult(btn, clipboard.writeText(text));
  }

  /** @param {HTMLElement} btn @param {Promise<void>} writing */
  function showCopyResult(btn, writing) {
    const restingTip = btn.dataset.mbCopyLabel || "Copy content";
    /** @param {string} tip @param {boolean} copied */
    function feedback(tip, copied) {
      if (copied) {
        btn.classList.add("copied");
      }
      btn.dataset.tipText = tip;
      setTimeout(() => {
        btn.classList.remove("copied");
        btn.dataset.tipText = restingTip;
      }, 1500);
    }
    writing.then(
      () => feedback("Copied", true),
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
        // Only a control page code created (see `_delegateOwner`): the same markup
        // written by a document is ignored.
        var btn = target.closest("[data-mb-copy]");
        if (btn) {
          if (isOwnedDelegate(btn)) {
            _handleCopyClick(/** @type {HTMLElement} */ (btn));
          }
          return;
        }
        // Load more: only a notice's own button, and only an action registered by
        // name (see registerLoadMoreAction); anything else in the page is ignored.
        var more = target.closest("button.metabrowser-load-more[data-mb-load-more]");
        var call =
          isOwnedDelegate(more) &&
          /^([A-Za-z_$][\w$]*)\(\)$/.exec(more?.getAttribute("data-mb-load-more") || "");
        var registered = call ? _loadMoreActions.get(call[1]) : undefined;
        if (registered) {
          registered();
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
    plugins: Object.freeze({ load: loadPluginExports }),
    async loadStructuredTree() {
      await Promise.all([
        ensureAsset("structured-tree"),
        _loadStylesheet("/static/structured-tree.css"),
      ]);
      const preview = global.__structuredPreview;
      const tree = global.__structuredTree;
      if (!preview || !tree) {
        throw new Error("Structured Tree unavailable");
      }
      return { ...preview, ...tree };
    },
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
    onInventoryChange: onInventoryChange,
    watchFile: watchFile,
    errors: global.MetabrowserRequestErrors,
    folderContext: folderContext,
    directoryTotals: directoryTotals,
    viewState: viewState,
    setViewPrintState: global.MetabrowserViewState.setPrintState,
    tooltip: tooltip,
    fileTypeClass: fileTypeClass,
    fileTypeIcon: fileTypeIcon,
    fileCatalog: fileCatalog,
    shortcuts: Object.freeze({ attach: queueShortcut }),
    navigation: global.MetabrowserNavigationRoute.navigation,
    sourceKind: sourceKind,
    repository: repository,
    fetchKpressRender: fetchKpressRender,
    loadKpressAssets: loadKpressAssets,
    ensureAsset: ensureAsset,
    ensureModule: ensureModule,
    ensureKindAssets: ensureKindAssets,
    whenIdle: whenIdle,
    kpressInitToc: kpressInitToc,
    formatKpressError: formatKpressError,
    // static/charts.js, in the `chart` bundle the wrapper needs, replaces this.
    chart() {
      throw new Error('metabrowser.chart: await metabrowser.ensureAsset("chart") first');
    },
    formatSize: formatSize,
    formatInteger: formatInteger,
    formatFileCount: formatFileCount,
    formatAge: formatAge,
    formatTimestamp: formatTimestamp,
    titleNodes: titleNodes,
    shortCommit: shortCommit,
    countPartsNodes: countPartsNodes,
    changeLine: changeLine,
    changeLineNodes: changeLineNodes,
    countClass: countClass,
    sizeClass: sizeClass,
    sizeHtml: sizeHtml,
    delegateOwnerAttribute: delegateOwnerAttribute,
    ownDelegate: ownDelegate,
    showCopyResult,
    icons: icons,
    perf: perf,
    prefs: prefs,
    filters: filters,
    fileTypes: fileTypes,
  };
})(typeof window !== "undefined" ? window : globalThis);
