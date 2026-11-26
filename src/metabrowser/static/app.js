// Metabrowser — client-side application

let currentPath = null;
const activeFiles = new Map(); // path -> {pid_alive: bool|null}
// Active SSE subscription for the currently-viewed live JSONL.
// Closed and replaced on every selectFile.
let currentLiveStream = null;

const TREE_SUBTREE_FETCH_DEPTH = 2;
// Per-directory render cap. A directory with thousands
// of flat result files could otherwise render thousands of DOM rows on first
// paint and freeze the tree pane. We render the first N entries plus
// a synthetic "Show N more (M total)" row that swaps in the next batch
// on click. The full child list is still in memory; we only stage how
// much hits the DOM.
const TREE_PAGE_SIZE = 200;
const TREE_AUTO_EXPAND_FALLBACK_ROWS =
  window.METABROWSER_SETTINGS?.TREE_AUTO_EXPAND_FALLBACK_ROWS || 24;
const TREE_AUTO_EXPAND_ROW_HEIGHT_PROPERTY = "--tree-auto-expand-row-height";
const FILE_PREFETCH_HOVER_DELAY_MS = 250;
const FILE_PREFETCH_MAX_BYTES = 512 * 1024;
const FILE_PREFETCH_MAX_CONCURRENT = 1;
// Chunking comes from settings.py so the two planes cannot drift; see
// docs/large-content-rendering.md for the measurements behind the sizes.
const TEXT_PREVIEW_CHUNK_BYTES =
  window.METABROWSER_SETTINGS?.TEXT_PREVIEW_CHUNK_BYTES || 2 * 1024 * 1024;
const TEXT_PREVIEW_MAX_CHUNK_BYTES =
  window.METABROWSER_SETTINGS?.TEXT_PREVIEW_MAX_CHUNK_BYTES || 8 * 1024 * 1024;

// perf.js installs window.metabrowser.perf with measure/measureAsync helpers
// and a fetch wrapper before production application work starts. The fallback
// keeps isolated app.js harnesses usable without recreating the recorder.
var _perf = (typeof window !== "undefined" && window.metabrowser?.perf) || {
  measure: (_label, fn) => fn(),
  measureAsync: (_label, fn) => fn(),
};

function filePerfMeta(data, extra) {
  var meta = {
    path: data?.path || "",
    type: data?.type || "",
    kind: data?.kind || "",
    ext: data?.ext || "",
    size_bytes: data?.size || 0,
    view_count: data?.views ? data.views.length : 0,
  };
  if (data && typeof data.content === "string") {
    meta.content_chars = data.content.length;
  }
  if (data && typeof data.raw_text === "string") {
    meta.raw_text_chars = data.raw_text.length;
  }
  if (data && Array.isArray(data.events)) {
    meta.events = data.events.length;
  }
  if (data && typeof data.bytes_read === "number") {
    meta.bytes_read = data.bytes_read;
  }
  if (data?.content_truncated) {
    meta.content_truncated = true;
  }
  if (data?.highlight_disabled) {
    meta.highlight_disabled = true;
  }
  if (extra) {
    Object.keys(extra).forEach((k) => {
      meta[k] = extra[k];
    });
  }
  return meta;
}

function responsePerfMeta(resp, path, extra) {
  /** @type {Record<string, unknown>} */
  var meta = {
    path: path || "",
    status: resp?.status || 0,
    content_length: null,
    content_encoding: null,
  };
  try {
    var cl = resp?.headers?.get?.("content-length");
    if (cl) {
      meta.content_length = parseInt(cl, 10);
    }
    meta.content_encoding = resp?.headers?.get ? resp.headers.get("content-encoding") : null;
  } catch (_e) {
    /* ignore */
  }
  if (extra) {
    Object.keys(extra).forEach((k) => {
      meta[k] = extra[k];
    });
  }
  return meta;
}

function measureNextPaint(label, meta) {
  if (typeof requestAnimationFrame === "undefined") {
    return Promise.resolve();
  }
  return _perf.measureAsync(
    label,
    () =>
      new Promise((resolve) => {
        requestAnimationFrame(() => {
          requestAnimationFrame(resolve);
        });
      }),
    meta,
  );
}

// ── Utilities ───────────────────────────────────────────────────

function esc(s) {
  if (s == null) {
    return "";
  }
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Escape a filesystem path for embedding inside a double-quoted CSS
// attribute selector: [data-path="…"]. Backslashes must be doubled
// before quotes are escaped — POSIX filenames can contain both, and a
// missed backslash silently breaks live insert/update/remove matching.
// Used by every dynamic data-path selector in this file.
function escapePathForSelector(path) {
  return String(path).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

/**
 * @param {string} selector
 * @param {ParentNode} [root]
 * @returns {HTMLElement | null}
 */
function queryHtml(selector, root) {
  return /** @type {HTMLElement | null} */ ((root || document).querySelector(selector));
}

/**
 * @param {string} selector
 * @param {ParentNode} [root]
 * @returns {NodeListOf<HTMLElement>}
 */
function queryHtmlAll(selector, root) {
  return /** @type {NodeListOf<HTMLElement>} */ ((root || document).querySelectorAll(selector));
}

/** @param {Event} event @returns {Element | null} */
function eventTargetElement(event) {
  return event.target instanceof Element ? event.target : null;
}

// Size and size-weight conventions — every shell surface delegates to the
// shared formatter runtime, as `mb.formatSize` and `mb.sizeClass` do, so
// plugins and core use the same units and the same threshold.
function formatSize(bytes) {
  return window.MetabrowserFormatters.formatBytes(Number(bytes) || 0);
}
function sizeClass(bytes) {
  return window.MetabrowserFormatters.sizeClass(Number(bytes) || 0);
}
function sizeHtml(bytes, extraClass) {
  // ``null`` means the filesystem walker is still finalizing this cell.
  // An omitted value is not pending: Git listings have no size fact.
  if (bytes === undefined) {
    return "";
  }
  if (bytes === null) {
    var pendCls = `size tally-pending ${extraClass || ""}`.trim();
    return `<span class="${pendCls}"></span>`;
  }
  var cls = `size ${sizeClass(bytes)} ${extraClass || ""}`.trim();
  return `<span class="${cls}">${formatSize(bytes)}</span>`;
}

// File-count convention — same idea as sizeHtml. One helper, one class,
// consistent rendering of "N files" / "1 file" anywhere a count shows up
// (app header, tooltip, drawer). Keep formatting decisions (thousands
// separator, singular/plural) here so every call site agrees. Counts
// above the shared count boundary bold up the same way large sizes do.
function isPendingNumber(n) {
  return n === null || n === undefined || Number.isNaN(n);
}
function nullableDataValue(n) {
  return isPendingNumber(n) ? "" : String(n);
}
function dataTipNumberAttr(key, n) {
  if (n === undefined) {
    return "";
  }
  return ` data-tip-${key}="${esc(nullableDataValue(n))}"`;
}
function parseTipNumber(value) {
  if (value === undefined) {
    return undefined;
  }
  if (value === null || value === "") {
    return null;
  }
  var n = Number(value);
  return Number.isFinite(n) ? n : null;
}
// A count of files, "12,797 files", in a count summary's parts, which paint the number bold
// and the word in the line's weight (docs/design-system.md, "Count Summaries Bold Their
// Numbers"). `formatCount` is the parts joined.
function formatCountParts(n) {
  return [{ number: (n || 0).toLocaleString() }, n === 1 ? " file" : " files"];
}
function formatCount(n) {
  return formatCountParts(n)
    .map((part) => (typeof part === "string" ? part : part.number))
    .join("");
}
function countClass(n) {
  return window.MetabrowserFormatters.countClass(Number(n) || 0);
}
function countHtml(n, extraClass) {
  if (n === undefined) {
    return "";
  }
  if (isPendingNumber(n)) {
    var pendCls = `count tally-pending ${extraClass || ""}`.trim();
    return `<span class="${pendCls}"></span>`;
  }
  var cls = `count ${countClass(n)} ${extraClass || ""}`.trim();
  return `<span class="${cls}">${formatCount(n)}</span>`;
}

/**
 * Just the last component of `path`, wrapped in `.path`/`.path-base` so it
 * inherits whatever emphasis its container declares. This is what the
 * navigation heading shows: the directories above the served root never
 * change, and the column they would spend width on is the narrowest in the
 * app. Where the main view names an item, its view header renders the
 * folders above it as an address of controls — see view-header.js.
 */
function pathBaseHtml(path) {
  return `<span class="path"><span class="path-base">${esc(pathBaseName(path))}</span></span>`;
}

/** The name `pathBaseHtml` shows: the last component of `path`, or all of it at a root. */
function pathBaseName(path) {
  var trimmed = String(path == null ? "" : path).replace(/\/+$/, "");
  return trimmed.slice(trimmed.lastIndexOf("/") + 1) || trimmed;
}

/**
 * Update the folder name from the tree payload. A pinned revision keeps the
 * server-rendered heading because its GitPath root is empty.
 */
function renderServedRootHeading(pathEl, root) {
  if (!pathEl || isGitRevisionSource()) {
    return;
  }
  // Keep the name's nodes under the pointer on Home redraws. Compare text
  // because the browser and esc() serialize quoted names differently.
  if (pathEl.textContent !== pathBaseName(root)) {
    pathEl.innerHTML = pathBaseHtml(root);
  }
}

/**
 * The served root's file count, size, and newest mtime, from its top-level rows.
 * Same shape as a folder tooltip: the served root reads as "just another
 * folder", the top-most one. Count and size are null while a directory's
 * aggregate is still pending.
 *
 * A symlink counts the way the server's own tallies count it, so the heading
 * agrees with /api/rollup. On a pinned revision a link is a blob, one file of
 * its stored size; under a served folder it is not followed and counts for
 * nothing.
 */
function rootTallyFromTopLevel(tree) {
  var linksAreFiles = isGitRevisionSource();
  var totalSize = 0;
  var totalFiles = 0;
  var newestMtime = 0;
  var hasPendingAggregate = false;
  for (var i = 0; i < tree.length; i++) {
    var n = tree[i];
    if (n.type === "dir") {
      if (
        n.total_size === null ||
        n.total_size === undefined ||
        n.total_files === null ||
        n.total_files === undefined
      ) {
        hasPendingAggregate = true;
      } else {
        totalSize += n.total_size;
        totalFiles += n.total_files;
      }
    } else if (n.type === "file" || (linksAreFiles && n.type === "symlink")) {
      totalSize += n.size || 0;
      totalFiles += 1;
    }
    if ((n.mtime || 0) > newestMtime) {
      newestMtime = n.mtime || 0;
    }
  }
  return {
    files: hasPendingAggregate ? null : totalFiles,
    size: hasPendingAggregate ? null : totalSize,
    newestMtime: newestMtime,
  };
}

// The served root, absolute, from the one element that carries it.
function servedRoot() {
  return queryHtml(".header-path")?.dataset.servedRoot || "";
}

// What a served mirror's page adds to its headings; see static/mirror-heading.js.
function mirrorHeading(part) {
  return window.MetabrowserMirrorHeading?.[part]() ?? "";
}

// The shell's delegated controls (the address crumbs, the parent button, and copy path)
// carry the SDK's per-page owner mark, and their document listeners act only on a marked
// element: a trusted folder's Markdown keeps class, id, and data-*, so it can spell the
// same markup. See `_delegateOwner` in plugin-sdk.js.
function ownedControlAttr() {
  return window.metabrowser?.delegateOwnerAttribute?.() ?? "";
}

/** @param {Element | null} element */
function isOwnedControl(element) {
  return window.MetabrowserPluginHost?.isOwnedDelegate?.(element) === true;
}

// Whether page code marked this very element with `mb.ownDelegate`: its identity, which a
// document that carries a copy of the owner value cannot have. See `ownsElement` in
// plugin-sdk.js.
/** @param {Element | null} element */
function isPageElement(element) {
  return window.MetabrowserPluginHost?.ownsElement?.(element) === true;
}

function getExt(name) {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i) : "";
}

const COMPRESSION_SUFFIX_BY_FORMAT = Object.freeze({
  gzip: ".gz",
  zlib: ".zlib",
});

// Strip a recognized compression suffix before extension-based dispatch.
function getLogicalName(entry) {
  const suffix = COMPRESSION_SUFFIX_BY_FORMAT[entry?.compression];
  if (entry?.compressed && suffix && entry.name?.toLowerCase().endsWith(suffix)) {
    return entry.name.slice(0, -suffix.length);
  }
  return entry?.name ? entry.name : "";
}

// ── Syntax highlighting (client-side via highlight.js) ──────────

/** @type {WeakSet<Document | Element>} */
var scheduledHighlightRoots = new WeakSet();

/** @param {Document | Element} root */
function highlightCode(root = document) {
  // Highlight.js is a prefetched vendored enhancement. If the optional asset
  // failed to load, no-op rather than aborting the readable plain-text render.
  if (typeof hljs === "undefined") {
    return;
  }
  // Skip raw blocks inside collapsed log events; renderLogTab can ship
  // 1000+ such elements and hljs.highlightElement runs in ~1 ms each,
  // so eager highlighting torpedoes the first paint of a big log file.
  // The toggleEvent handler highlights on first expand instead.
  var nodes = root.querySelectorAll("pre code:not(.hljs)");
  var meta = { blocks: nodes.length, skipped_collapsed_log_blocks: 0 };
  return _perf.measure(
    "highlightCode",
    () => {
      nodes.forEach((el) => {
        var rawLogHost = el.closest(".log-event-raw");
        if (rawLogHost && !rawLogHost.closest(".log-event.expanded")) {
          meta.skipped_collapsed_log_blocks += 1;
          return;
        }
        // KPress highlights its own code server-side; re-running hljs over those
        // blocks double-highlights and trips hljs's "unescaped HTML" warning on
        // the markup KPress already emitted. Leave the kpress host alone.
        if (el.closest(".metabrowser-kpress-host")) {
          meta.skipped_kpress_blocks = (meta.skipped_kpress_blocks || 0) + 1;
          return;
        }
        if (el.classList.contains("no-highlight")) {
          meta.skipped_no_highlight = (meta.skipped_no_highlight || 0) + 1;
          return;
        }
        hljs.highlightElement(el);
      });
    },
    meta,
  );
}

/**
 * Schedule optional syntax work after the next browser paint.
 * @param {Document | Element} [root]
 */
function scheduleHighlightCode(root = document) {
  if (scheduledHighlightRoots.has(root)) {
    return;
  }
  scheduledHighlightRoots.add(root);
  var afterFrame = () => {
    setTimeout(() => {
      scheduledHighlightRoots.delete(root);
      if (root !== document && !root.isConnected) {
        return;
      }
      highlightCode(root);
    }, 0);
  };
  if (typeof requestAnimationFrame === "function") {
    requestAnimationFrame(afterFrame);
  } else {
    afterFrame();
  }
}

function formatAge(mtimeSec, options) {
  // Walker emits ``null`` newest-mtime while finalizing.
  // Render skeleton; applyCellPatch fills it from fs.change.
  if (mtimeSec === null) {
    return '<span class="tally-pending tally-pending-narrow"></span>';
  }
  // The one age builder (formatters.js).
  return window.MetabrowserFormatters.ageLabelHtml(mtimeSec, options);
}

function formatTimestamp(mtimeSec) {
  if (!mtimeSec) {
    return "";
  }
  return new Date(mtimeSec * 1000).toISOString().replace(/\.\d{3}Z$/, "Z");
}

function formatExactSize(bytes) {
  return `${bytes.toLocaleString()} bytes`;
}

// ── Icon registry ──────────────────────────────────────────────
// All SVG markup lives in static/icons.js, loaded before this file
// and exposed as window.MetabrowserIcons. Local aliases below let
// existing callsites keep referencing ICON_SVG / ICONS.
var ICON_SVG = (typeof window !== "undefined" && window.MetabrowserIcons) || {};
var ICONS = ICON_SVG;

// ── Theme mode (KPress-compatible system/light/dark contract) ───

var THEME_MODE_KEY = "metabrowser.themeMode";
var THEME_MODES = ["system", "light", "dark"];

// Persist UI preferences in host-only cookies, not localStorage: localStorage
// is origin-scoped (host + port), but each metabrowser folder server lands on
// its own port, so a localStorage value is isolated per instance. Cookies
// ignore the port, so the choice is shared across every instance on the host.
function readPrefCookie(name) {
  try {
    var parts = document.cookie.split("; ");
    for (var i = 0; i < parts.length; i++) {
      if (parts[i].indexOf(`${name}=`) === 0) {
        return decodeURIComponent(parts[i].slice(name.length + 1));
      }
    }
  } catch (_e) {
    /* ignore */
  }
  return null;
}

function writePrefCookie(name, value) {
  try {
    // biome-ignore lint/suspicious/noDocumentCookie: compatibility fallback for browsers without Cookie Store.
    document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=31536000; samesite=lax`;
  } catch (_e) {
    /* cookies disabled */
  }
}

/** @returns {"dark" | "light" | "system"} */
function normalizeThemeMode(mode) {
  return THEME_MODES.indexOf(mode) >= 0 ? mode : "system";
}

function systemPrefersDark() {
  try {
    return !!window.matchMedia?.("(prefers-color-scheme: dark)").matches;
  } catch (_e) {
    return false;
  }
}

/** @returns {"dark" | "light"} */
function resolveTheme(mode) {
  var normalized = normalizeThemeMode(mode);
  if (normalized === "dark") {
    return "dark";
  }
  if (normalized === "light") {
    return "light";
  }
  return systemPrefersDark() ? "dark" : "light";
}

function getStoredThemeMode() {
  // The cookie is the only store; it has been since before the first
  // release, so there is no prior localStorage value to carry forward.
  return normalizeThemeMode(readPrefCookie(THEME_MODE_KEY) || "system");
}

function themeModeIcon(mode) {
  if (mode === "light") {
    return ICONS.sun || "";
  }
  if (mode === "dark") {
    return ICONS.moon || "";
  }
  return ICONS.monitor || "";
}

// Reading-font preference: "serif" keeps KPress's vendored PT Serif; "sans"
// uses the host system sans. Drives [data-prose-font] on <html>; styles.css
// turns that into --kpress-host-font-prose for the embedded document.
var PROSE_FONT_KEY = "metabrowser.proseFont";

function normalizeProseFont(font) {
  return font === "sans" ? "sans" : "serif";
}

function getStoredProseFont() {
  return normalizeProseFont(readPrefCookie(PROSE_FONT_KEY));
}

function proseFontIcon(font) {
  return font === "sans" ? ICONS.sans || "" : ICONS.serif || "";
}

// Reading width, in characters. Drives --doc-max-chars on <html>; styles.css
// multiplies it by the type base and the current face's advance-per-character
// to get KPress's --kpress-measure. Characters, not pixels, because that is
// the decision a reader has — see the token comment in styles.css.
var documentWidth = window.MetabrowserDocumentWidth;
var DOC_MAX_CHARS_DEFAULT = documentWidth.DEFAULT;

function getStoredDocMaxChars() {
  return documentWidth.readStored(readPrefCookie);
}

// Interface-font preference: the chosen font set's value (e.g. "clean",
// "system") is set as [data-app-font] on <html>; styles.css repoints
// --font-sans and bridges the host font hooks for the embedded document. The
// available sets are the <option>s of #app-font-select (rendered server-side
// from the _FONT_SETS registry), so adding a set needs no change here.
var INTERFACE_FONT_KEY = "metabrowser.interfaceFont";

function getStoredInterfaceFont() {
  return readPrefCookie(INTERFACE_FONT_KEY) || "";
}

// Mark the active segment of a chooser: the one whose data-<key> matches the
// current value gets aria-checked="true" (the .menu-seg CSS tints it).
function markChooserSegments(selector, dataKey, value) {
  var segs = queryHtmlAll(selector);
  for (var i = 0; i < segs.length; i++) {
    segs[i].setAttribute("aria-checked", segs[i].dataset[dataKey] === value ? "true" : "false");
  }
}

function applyThemeMode(mode, persist) {
  var normalized = normalizeThemeMode(mode);
  var resolved = resolveTheme(normalized);
  var previousResolved = document.documentElement.getAttribute("data-theme");
  document.documentElement.setAttribute("data-theme-mode", normalized);
  document.documentElement.setAttribute("data-theme", resolved);
  // Metabrowser is the single theme owner for embedded KPress fragments.
  // KPress reads this resolved value from the root; fragments remain
  // theme-agnostic and its automatic manifest omits the standalone resolver.
  document.documentElement.setAttribute("data-kpress-resolved-theme", resolved);
  if (previousResolved !== resolved) {
    window.MetabrowserTheme.notifyChanged({ mode: normalized, resolved: resolved });
  }
  if (persist) {
    writePrefCookie(THEME_MODE_KEY, normalized);
  }
  markChooserSegments("#settings-control [data-theme-choice]", "themeChoice", normalized);
}

function applyProseFont(font, persist) {
  var normalized = normalizeProseFont(font);
  document.documentElement.setAttribute("data-prose-font", normalized);
  if (persist) {
    writePrefCookie(PROSE_FONT_KEY, normalized);
  }
  markChooserSegments("#settings-control [data-font-choice]", "fontChoice", normalized);
}

function applyDocMaxChars(chars, persist) {
  var input = /** @type {HTMLInputElement | null} */ (
    document.getElementById("doc-max-chars-input")
  );
  return documentWidth.apply(chars, persist, {
    input,
    root: document.documentElement,
    writePreference: writePrefCookie,
  });
}

function applyInterfaceFont(font, persist) {
  document.documentElement.setAttribute("data-app-font", font);
  if (persist) {
    writePrefCookie(INTERFACE_FONT_KEY, font);
  }
  var sel = /** @type {HTMLSelectElement | null} */ (document.getElementById("app-font-select"));
  if (sel && sel.value !== font) {
    sel.value = font;
  }
}

function initSettingsControl() {
  applyThemeMode(getStoredThemeMode(), false);
  applyProseFont(getStoredProseFont(), false);
  applyDocMaxChars(getStoredDocMaxChars(), false);

  const wrap = document.getElementById("settings-control");
  const btn = document.getElementById("settings-btn");
  if (wrap && btn) {
    btn.innerHTML = ICONS.gear || "";

    // Fill each segment with its icon and wire instant-apply on click. The
    // menu stays open while picking — two choosers share one panel.
    var themeSegs = queryHtmlAll("[data-theme-choice]", wrap);
    for (var i = 0; i < themeSegs.length; i++) {
      themeSegs[i].innerHTML = themeModeIcon(themeSegs[i].dataset.themeChoice);
      themeSegs[i].addEventListener("click", (e) => {
        var segment = e.currentTarget;
        if (segment instanceof HTMLElement) {
          applyThemeMode(segment.dataset.themeChoice, true);
        }
      });
    }
    var fontSegs = queryHtmlAll("[data-font-choice]", wrap);
    for (var j = 0; j < fontSegs.length; j++) {
      fontSegs[j].innerHTML = proseFontIcon(fontSegs[j].dataset.fontChoice);
      fontSegs[j].addEventListener("click", (e) => {
        var segment = e.currentTarget;
        if (segment instanceof HTMLElement) {
          applyProseFont(segment.dataset.fontChoice, true);
        }
      });
    }
    // Font-set dropdown: options come from the markup (server _FONT_SETS). Keep
    // the stored value if it is still a known option, else fall back to the
    // first (default) option, then apply and wire instant change.
    var fontSelect = /** @type {HTMLSelectElement | null} */ (
      document.getElementById("app-font-select")
    );
    if (fontSelect) {
      var storedFont = getStoredInterfaceFont();
      if (storedFont) {
        fontSelect.value = storedFont;
      }
      if (!fontSelect.value) {
        fontSelect.selectedIndex = 0;
      }
      applyInterfaceFont(fontSelect.value, false);
      fontSelect.addEventListener("change", (event) => {
        var select = event.currentTarget;
        if (select instanceof HTMLSelectElement) {
          applyInterfaceFont(select.value, true);
        }
      });
    }

    // Reading width. `input` applies live so the column follows the number as
    // it is typed or stepped; `change` (commit, blur) is what normalizes and
    // writes back, so an out-of-range or half-typed value is not snapped under
    // the caret mid-edit.
    var charsInput = /** @type {HTMLInputElement | null} */ (
      document.getElementById("doc-max-chars-input")
    );
    if (charsInput) {
      charsInput.value = String(getStoredDocMaxChars());
      charsInput.addEventListener("input", (event) => {
        var field = event.currentTarget;
        if (field instanceof HTMLInputElement && field.value !== "") {
          applyDocMaxChars(field.value, true);
        }
      });
      charsInput.addEventListener("change", (event) => {
        var field = event.currentTarget;
        if (field instanceof HTMLInputElement) {
          applyDocMaxChars(field.value === "" ? DOC_MAX_CHARS_DEFAULT : field.value, true);
        }
      });
    }

    var isOpen = () => wrap.getAttribute("aria-expanded") === "true";
    var setOpen = (open) => {
      wrap.setAttribute("aria-expanded", open ? "true" : "false");
    };
    var dismissal = window.metabrowser.menus?.dismissible({
      name: "settings-menu",
      trigger: btn,
      inside: (node) => wrap.contains(node),
      isOpen,
      close: () => setOpen(false),
    });
    btn.addEventListener("click", () => {
      void window.MetabrowserAssets?.ensureAsset("settings-menu");
      setOpen(!isOpen());
      dismissal?.[isOpen() ? "opened" : "closed"]();
    });

    // Segments exist now — re-sync the active markers.
    markChooserSegments(
      "#settings-control [data-theme-choice]",
      "themeChoice",
      normalizeThemeMode(document.documentElement.getAttribute("data-theme-mode") || "system"),
    );
    markChooserSegments(
      "#settings-control [data-font-choice]",
      "fontChoice",
      normalizeProseFont(document.documentElement.getAttribute("data-prose-font")),
    );
  }

  if (window.matchMedia) {
    var media = window.matchMedia("(prefers-color-scheme: dark)");
    var onChange = () => {
      var mode = normalizeThemeMode(
        document.documentElement.getAttribute("data-theme-mode") || "system",
      );
      if (mode === "system") {
        applyThemeMode("system", false);
      }
    };
    if (media.addEventListener) {
      media.addEventListener("change", onChange);
    } else if (media.addListener) {
      media.addListener(onChange);
    }
  }

  // Enable the crossfade only after first paint (already in the correct theme
  // from the head boot script), so initial load never animates — only user
  // switches do. Double rAF guarantees we're past that first frame.
  if (typeof requestAnimationFrame === "function") {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.documentElement.classList.add("theme-anim");
      });
    });
  }
}

// ── File type design system ───────────────────────────────────
// The file tree's icon and colour, resolved through the rollup registry.
//
// Classification is NOT re-implemented here: `MetabrowserFileTypeTaxonomy` is the registry
// runtime (compound extensions, a family's shape through its group), and this file only
// turns its answer into markup. A second taxonomy here had drifted from the registry, so
// the bars disagreed with the rows beside them.
//
// Colours arrive finished in `DISTRIBUTION_COLORS`, resolved per theme by the server, since
// a browser clips an out-of-gamut `oklch()` and moves the hue. The distribution bars read
// the same list, so a family looks like itself wherever it appears.

/** Where a file row's colour for each theme is written. */
const FILE_COLOR_LIGHT_PROPERTY = "--mb-file-color-light";
const FILE_COLOR_DARK_PROPERTY = "--mb-file-color-dark";
/** The class that selects between the two theme colours above. */
const FILE_COLOR_CLASS = "file-identity-color";

/** @type {Map<string, {light: string, dark: string}> | null} */
let _familyColors = null;

function familyColors() {
  if (!_familyColors) {
    _familyColors = new Map();
    const declared =
      (typeof window !== "undefined" && window.METABROWSER_SETTINGS?.DISTRIBUTION_COLORS) || [];
    for (const entry of declared) {
      // Keys are `family:<id>`; the tree only ever asks about families.
      if (typeof entry?.key === "string" && entry.key.startsWith("family:")) {
        _familyColors.set(entry.key.slice("family:".length), {
          light: entry.light,
          dark: entry.dark,
        });
      }
    }
  }
  return _familyColors;
}

function fileTypeRuntime() {
  return (typeof window !== "undefined" && window.MetabrowserFileTypeTaxonomy) || null;
}

/**
 * The registry family a filename belongs to, or `null` when none claims it.
 * @param {string} pathOrName
 */
function fileTypeFamilyFor(pathOrName) {
  const runtime = fileTypeRuntime();
  if (!runtime || !pathOrName) {
    return null;
  }
  const slash = pathOrName.lastIndexOf("/");
  const name = slash >= 0 ? pathOrName.slice(slash + 1) : pathOrName;
  const dot = name.lastIndexOf(".");
  // `classify` takes the name and its extension and does the compound-suffix
  // work, so `.tar.gz` and `.d.ts` resolve the way the registry declares.
  return runtime.classify(name, dot > 0 ? name.slice(dot) : "").familyId || null;
}

/**
 * The icon and colour for a filename.
 *
 * Returns `style` beside `svg` and `cls` so a caller rendering markup carries
 * the colour without a second lookup. An unknown extension gets the generic
 * file shape and no colour, which is the honest answer: the registry does not
 * claim it.
 * @param {string} name
 */
function getFileIcon(name) {
  const runtime = fileTypeRuntime();
  const family = fileTypeFamilyFor(name);
  if (!runtime || !family) {
    return { svg: ICON_SVG.file, cls: "", style: "" };
  }
  const svg = ICON_SVG[runtime.iconForFamily(family) || "file"] || ICON_SVG.file;
  const color = familyColors().get(family);
  if (!color) {
    return { svg, cls: "", style: "" };
  }
  return {
    svg,
    cls: FILE_COLOR_CLASS,
    style: `${FILE_COLOR_LIGHT_PROPERTY}:${color.light};${FILE_COLOR_DARK_PROPERTY}:${color.dark}`,
  };
}

/**
 * The colour class for a path, for callers painting a name outside the tree.
 *
 * Exposed on `window.MetabrowserFileTypes` so anywhere a filename appears gets
 * the family's identity. The class alone cannot carry the colour — that is in
 * the custom properties — so callers needing the paint use `styleFor` beside it.
 * @param {string} pathOrName
 */
function getFileTypeClass(pathOrName) {
  return getFileIcon(pathOrName).cls;
}

/** @param {string} pathOrName */
function getFileTypeStyle(pathOrName) {
  return getFileIcon(pathOrName).style;
}

if (typeof window !== "undefined") {
  window.MetabrowserFileTypes = {
    classFor: getFileTypeClass,
    iconFor: getFileIcon,
    styleFor: getFileTypeStyle,
    familyFor: fileTypeFamilyFor,
  };
}

// The application shell owns the catalog and search composition. Search modules
// receive snapshots and navigation callbacks through their public constructors;
// they never reach into app.js state directly.
/**
 * A failed open always carries its message, so Quick File shows it as is.
 *
 * @typedef {{focusTarget?: HTMLElement | null, message?: string, status: "opened" | "not-found" | "cancelled"}
 *   | {focusTarget?: HTMLElement | null, message: string, status: "error" | "unreachable"}} QuickFileOpenOutcome
 */
var knownFileCatalog = null;
var quickFileSearchController = null;
var quickFilePalette = null;
var quickFileCatalogFeed = null;
var shortcutRegistry = null;
var keyboardHelp = null;
var treeKeyboard = null;
/** @type {MetabrowserPublicShellKeymapApi | null} */
var shellKeymap = null;
/** @type {MetabrowserPublicKeyRevealApi | null} */
var keyReveal = null;
var detachPluginShortcuts = null;
var applicationFocusRegion = null;
var applicationFocusListener = null;
// The most file rows one Quick Search query ranks and draws. The palette's row cap adds
// the pull-request group's own limit (`PULL_RESULT_LIMIT` in search-controller.js).
var QUICK_FILE_RESULT_LIMIT = 100;

// ── Tree ────────────────────────────────────────────────────────

// The filter, as /api/tree understands it.
//
// Which folders a filter leaves standing, and what those folders add up
// to, are both questions about a whole subtree — including the parts
// this client has never been sent. Only the server can answer them, so
// the filter travels with the request instead of being applied to the
// rows that come back. The inventory provider owns the projection;
// static/tree-filter-model.js turns a selection into request parameters.
var treeFilterModel = /** @type {any} */ (window).MetabrowserTreeFilterModel;

function currentFilterSnapshot() {
  return filterState ? filterState.get() : null;
}

function treeFilterSizeFloors() {
  return filterState ? filterState.SIZE_MIN_BYTES : {};
}

function treeFilterKey() {
  return treeFilterModel.requestKey(currentFilterSnapshot(), treeFilterSizeFloors());
}

/**
 * The /api/tree request for *path*. Inside a Group by section the request names that
 * section's group, so a folder opened there lists only the group's members.
 *
 * @param {string} path
 * @param {string[]} [extraParams]
 * @param {string} [group] the section's `<by>:<id>`, or empty outside a section
 */
function treeUrl(path, extraParams, group) {
  if (group) {
    return treeFilterModel.groupTreeUrl(
      path,
      group,
      currentFilterSnapshot(),
      treeFilterSizeFloors(),
      extraParams,
    );
  }
  return treeFilterModel.treeUrl(
    path,
    currentFilterSnapshot(),
    treeFilterSizeFloors(),
    extraParams,
  );
}

// ── Group by sections ──
//
// With Group by on, the Files panel holds one section per group the server lists
// (/api/tree?group_by=, metabrowser/tree_groups.py), each a heading and a tree of that
// group's members after the filter. A folder can stand in several sections, so a row
// looks up its section rather than the panel for anything keyed by its path: the request
// that opens it, the subtree cache, and the ids that tie a folder to its children.

function filesPanelUsesGroupedSource() {
  return treeFilterModel.groupBy(currentFilterSnapshot()) !== "none";
}

/**
 * The Group by section an element sits in, as `<by>:<id>`, or "" outside one.
 * @param {Element | null | undefined} element
 */
function treeSectionKey(element) {
  var section = /** @type {HTMLElement | null} */ (element?.closest?.(".tree-section") ?? null);
  return section?.dataset.treeGroup || "";
}

// The section the rows being built belong to, which scopes their DOM ids. Set only around
// a synchronous build (withTreeIdScope), so a folder's id and its children's group id
// agree, and the same folder in two sections never shares an id.
var _treeIdScope = "";

/**
 * @template T
 * @param {string} scope
 * @param {() => T} build
 * @returns {T}
 */
function withTreeIdScope(scope, build) {
  var previous = _treeIdScope;
  _treeIdScope = scope;
  try {
    return build();
  } finally {
    _treeIdScope = previous;
  }
}

// The rows the shell inlined, painted before the first fetch is even sent.
// Consumed once: after that the fetched payload is authoritative, and a second
// paint from a snapshot the server took at page-render time would be a
// regression, not a shortcut.
let _inlineTreeRows = window.METABROWSER_INITIAL_TREE?.tree ?? null;
// The Files totals line's source (`rootTotals`).
/** @type {ReturnType<Window["MetabrowserNavigationRoute"]["createRootTotals"]> | null} */
let _rootTotals = null;
// The exact rows that reached the DOM from the shell. The first /api/tree
// response reconciles against this snapshot instead of replacing the root,
// which preserves the first paint while still converging to the newer index.
let _inlineTreeBaseline = null;
let _rootTreeRequestsInFlight = 0;
// Whether this server paints the tree's first rows from the page itself, as it does for a
// folder (server.py, _INLINE_INITIAL_TREE_ROWS). A fresh load of `/view/` then paints the
// root's rows alone and keeps them so through the fetch, so it opens no folder; a pin's
// page has no inline rows, and its first paint opens the folders the planner chooses. Home
// draws the tree as that load does (resetFilesTab).
const _firstPaintInlinesTree = Array.isArray(window.METABROWSER_INITIAL_TREE?.tree);
// Set by Home across the filter reset it makes, so the tree load that reset begins draws
// the tree as a fresh load of `/view/` does; read and cleared by that load.
let _homeTreeDraw = false;

/**
 * Paint the inlined rows, if the shell carried any and nothing has painted yet.
 *
 * Only for the unfiltered default view. A filter is client state the server did
 * not have when it rendered the page, so these rows do not describe it.
 *
 * @returns {boolean} whether rows were painted
 */
function renderInitialTreeRows() {
  const rows = _inlineTreeRows;
  _inlineTreeRows = null;
  if (!Array.isArray(rows) || rows.length === 0 || _lastTreeRender) {
    return false;
  }
  // treeFilterKey() is the same key the request carries, and it is empty when
  // nothing is filtered — so this asks exactly the question the server was
  // answering when it rendered these rows.
  if (treeFilterKey() || filesPanelUsesRecentSource() || filesPanelUsesGroupedSource()) {
    return false;
  }
  // The tally row is rendered in its pending state rather than omitted. It
  // carries no numbers this payload can supply, but it holds a line of the
  // height the real one needs, so the rows below it are laid out close to
  // where they will stay. Omitting it cost 43 px of downward shift the moment
  // the fetch returned -- a jump this inline had itself introduced, since
  // before it there were no rows in place to push.
  paintTreeSummary(treeSummaryHtml(rootTotals().totals(), null, null));
  _lastTreeRender = { tree: rows, chromeHtml: "", tallyCacheStatus: "scanning" };
  // Measured here rather than around the call, so the span exists only when
  // this path actually paints. Every return above declined to — no inlined
  // rows, something already on screen, a filter the server did not know about
  // — and a span recorded for one of those reports work on a region nothing
  // touched, which is what the repaint and render-span counts read.
  const painted = _perf.measure("renderTreeNodes:inline", () => renderFilesFromTree());
  _inlineTreeBaseline = painted ? rows : null;
  // A landing whose folders the shell expanded: its row, selected and shown now.
  var landed = painted && window.METABROWSER_INITIAL_TREE?.path;
  if (landed) {
    setSelectedPath(landed);
    queryHtml(`.tree-item[data-path="${escapePathForSelector(landed)}"]`)?.scrollIntoView({
      block: "nearest",
    });
  }
  // Not authoritative — the fetch that follows reconciles newer values into it.
  _lastTreeRender = null;
  return painted;
}

/**
 * Load the authoritative root tree.
 *
 * A discovery-completion refresh already has a useful keyed tree mounted. It
 * reconciles that tree in place instead of rebuilding the whole Files region.
 * Home's load (`asHome`) draws the tree as a fresh load of `/view/` does.
 *
 * @param {{ reconcileMountedRoot?: boolean, asHome?: boolean }} [options]
 */
async function loadTree(options = {}) {
  if (filesPanelUsesGroupedSource()) {
    return loadGroupedTree({ preserve: options.reconcileMountedRoot === true });
  }
  const reconcileMountedRoot = options.reconcileMountedRoot === true;
  _rootTreeRequestsInFlight += 1;
  try {
    return await _perf.measureAsync("loadTree", async () => {
      renderInitialTreeRows();

      /** Replace whatever is on screen with a failure the reader can act on. */
      /** @param {unknown} cause */
      function failTree(cause) {
        console.warn("loadTree: could not load the tree", cause);
        const treeEl = document.getElementById("tree-content");
        if (treeEl) {
          treeEl.innerHTML =
            '<div class="preview-empty" role="alert">Could not load files. Reload the page to try again.</div>';
        }
      }

      let resp;
      let data;
      try {
        resp = await fetch(treeUrl(""));
        if (!resp.ok) {
          failTree({ status: resp.status });
          return;
        }
        data = await _perf.measureAsync(
          "apiTree:json",
          () => resp.json(),
          responsePerfMeta(resp, ""),
        );
      } catch (error) {
        // A throw lands here as a non-ok status does: the inline rows are already
        // painted, so a dropped connection or a malformed body would otherwise leave a tree
        // that appears complete with no chrome, no counts, and no error.
        failTree(error);
        return;
      }
      observeFileAges(data.ages);
      knownFileCatalog?.observeInitialTree(data.tree);
      var pathEl = queryHtml(".header-path");
      renderServedRootHeading(queryHtml("#header-home-name"), data.root);
      var rootTally = rootTallyFromTopLevel(data.tree);
      var newestMtime = rootTally.newestMtime;
      var summaryFiles = rootTally.files;
      var summarySize = rootTally.size;
      // Per-entry pending check above isn't enough: a partial scan can finalize
      // every visible top-level dir before the walker is done, leaving the
      // summary at a stale "known but incomplete" value. The envelope-level
      // tally_cache_status is the authoritative scan-state flag — defer the
      // header/summary numbers until the walker reports "done" or "truncated".
      if (data.tally_cache_status === "scanning") {
        summaryFiles = null;
        summarySize = null;
        // The progress request that began before this tree fetch can observe
        // completion and stop while this slower, conservatively labeled response
        // is still in flight. Restarting is idempotent and guarantees one final
        // tree refresh instead of leaving these new pending cells to the watchdog.
        startIndexProgressPolling();
      }
      // Keep the disclosure's aggregates in step with the root inventory.
      if (pathEl) {
        pathEl.dataset.tipFiles = nullableDataValue(summaryFiles);
        pathEl.dataset.tipSize = nullableDataValue(summarySize);
        pathEl.dataset.tipMtime = nullableDataValue(newestMtime);
        updateRootDetailsStats();
      }
      // The summary row stands in its band under the filter bar, out of the
      // tree's scroller, so it stays in view as the tree scrolls and its rule
      // runs the pane's width; every source the panel shows keeps it.
      // The root's totals, never partial (docs/design-system.md, "The Files totals").
      if (data.summary) {
        rootTotals().fromSummary(data.summary, data.tally_cache_status);
      }
      var stableSummary = rootTotals().totals();
      // Held, the figures stay pending: the combined figure counts the ignored files.
      var holding = !stableSummary && rootTotals().keepsIgnoredLine();
      var summaryHtml = treeSummaryHtml(
        stableSummary,
        holding ? null : summaryFiles,
        holding ? null : summarySize,
      );
      paintTreeSummary(summaryHtml);
      // Walker truncation banner. The provider
      // walker stops at INVENTORY_MAX_FILES; finalized dirs still
      // emit accumulated totals so the UI is usable, but the user
      // had no signal that the tree was incomplete.
      var truncationHtml = "";
      if (data.tally_cache_status === "truncated") {
        truncationHtml = treeTruncationNoteHtml(data.tally_cache_max_files);
      }
      if (updateFilterTallies(data)) {
        renderNavFilterBar();
      }
      // How many files the filter selected across the whole subtree. Only the
      // server can say: the payload is capped by depth and paged by the
      // renderer, so counting the rows in it would report how much has been
      // mounted rather than how much matched.
      _filteredTreeTotals = data.filtered || null;
      _lastTreeRender = {
        tree: data.tree,
        chromeHtml: truncationHtml,
        tallyCacheStatus: data.tally_cache_status,
      };
      // A recency request, or a grouping, may have started while this tree request was
      // in flight. Keep the authoritative cache current without painting over the
      // newer source selection.
      if (!filesPanelUsesRecentSource() && !filesPanelUsesGroupedSource()) {
        if (_inlineTreeBaseline || reconcileMountedRoot) {
          reconcileMountedTree(data.tree, truncationHtml);
        } else {
          renderFilesFromTree(options.asHome === true);
        }
        retryFailedExpandedSubtrees();
      }
      _inlineTreeBaseline = null;
      // Rows are on screen; now go get the numbers that ride beside them. The
      // server answers a row request from its tally memo or not at all, so that
      // the reader never waits on a pass over every entry in the index to see a
      // tree. This is the request that is allowed to pay for it, and it runs
      // after the render rather than in front of it.
      if (!data.summary) {
        scheduleRootSummaryRefresh();
      }
    });
  } finally {
    _rootTreeRequestsInFlight -= 1;
  }
}

// ── Group by: loading and painting the sections ─────────────────

function currentGroupedKey() {
  return treeFilterModel.groupedRequestKey(currentFilterSnapshot(), treeFilterSizeFloors());
}

/**
 * Load and paint the Group by sections. One request answers every group's count and its
 * first two levels (`/api/tree?group_by=`), the depth the ungrouped tree's first answer has.
 * The load's lifecycle, which loads wait and which cancel, is `groupedLoads`.
 *
 * @param {{ preserve?: boolean }} [options] `preserve` refreshes the sections on screen in
 *   place, after files changed, rather than painting a new grouping.
 * @returns {Promise<boolean>} whether an answer was painted
 */
function loadGroupedTree(options = {}) {
  return groupedLoads.load(currentGroupedKey(), {
    refresh: options.preserve === true,
    painted: queryHtml("#tab-files > .tree-section") !== null,
  });
}

// The Group by loads (tree-filter-model.js, createGroupedLoads): at most one on its way,
// which a newer grouping or filter cancels and a refresh of its first sections waits for.
// The shell supplies the request and the paint, the wait it shows, and the refresh.
var groupedLoads = treeFilterModel.createGroupedLoads({
  run: (load) => loadGroupedTreeInner(currentFilterSnapshot(), load),
  pending: (load) => setGroupingPending(load !== null, load?.first === true),
  refresh: () => requestGroupedRefresh(),
});

// Cancel the load on its way, when a newer grouping or filter supersedes it or the reader
// leaves grouping: its request is aborted, its answer is never painted, and the wait it
// showed ends at once. The server's pass, once begun, runs to its end regardless.
function cancelGroupedLoad() {
  groupedLoads.cancel();
}

/**
 * Wait until no grouping's first sections are on their way. A reveal under Group by
 * looks for its row in the sections, which a choice paints only when its groups come;
 * looked for before, it would find none and land nowhere.
 *
 * @returns {Promise<void>}
 */
function groupedSectionsSettled() {
  return groupedLoads.settled();
}

// While the groups are on their way the tree on screen stays, and the panel is busy. For a
// choice's first sections, the tree on screen is the arrangement the reader left, so past
// the quiet period it dims and the scan row says what is on its way (renderRegrouping);
// an answer inside --loading-state-delay shows none of it. The Group by trigger does not
// breathe: it reads the choice in the link's ink on the accent ground, and only primary
// ink breathes (docs/design-system.md, "Refreshing Content"), so the dim and the scan row
// say what is waiting.
/**
 * @param {boolean} pending
 * @param {boolean} [first] whether the load on its way paints new sections
 */
function setGroupingPending(pending, first = false) {
  var grouped = filesPanelUsesGroupedSource();
  document.getElementById("tab-files")?.setAttribute("aria-busy", String(pending));
  renderRegrouping(
    pending && grouped && first ? treeFilterModel.groupBy(currentFilterSnapshot()) : null,
  );
}

// The grouping whose first sections are on their way, or null.
/** @type {string | null} */
var _regroupingBy = null;
/** @type {ReturnType<typeof setTimeout> | null} */
var _regroupingWordsTimer = null;

// The quiet period, `--loading-state-delay` in styles.css, in milliseconds.
function loadingStateDelayMs() {
  var value = getComputedStyle(document.documentElement).getPropertyValue("--loading-state-delay");
  var ms = Number.parseFloat(value);
  return Number.isFinite(ms) ? ms : 50;
}

/**
 * Show, or end, the wait for a grouping's first sections (docs/design-system.md, "Grouping
 * the Files Tree", Waiting): the tree dims (`.tree-regrouping` in styles.css) and the scan
 * row says "Grouping by file type…" in its spinner and words, both after the quiet period.
 * A scan the row is already showing keeps its words through the quiet period, so an answer
 * inside it changes nothing the polite live region would announce, and comes back when the
 * wait ends.
 *
 * @param {string | null} by
 */
function renderRegrouping(by) {
  _regroupingBy = by;
  if (_regroupingWordsTimer !== null) {
    clearTimeout(_regroupingWordsTimer);
    _regroupingWordsTimer = null;
  }
  document.getElementById("tab-files")?.classList.toggle("tree-regrouping", by !== null);
  var row = document.getElementById("index-progress");
  if (!row) {
    return;
  }
  if (by === null) {
    row.classList.remove("mb-delayed-loading");
    renderIndexProgress(indexProgressLastRendered);
    return;
  }
  var text = row.querySelector(".index-progress-text");
  var words = treeFilterModel.regroupingStatusText(by);
  if (row.hidden === true) {
    // Hidden until the quiet period passes (.mb-delayed-loading).
    if (text) {
      text.textContent = words;
    }
    row.classList.add("mb-delayed-loading");
    row.hidden = false;
    return;
  }
  row.classList.remove("mb-delayed-loading");
  _regroupingWordsTimer = setTimeout(() => {
    _regroupingWordsTimer = null;
    if (text && _regroupingBy === by) {
      text.textContent = words;
    }
  }, loadingStateDelayMs());
}

/**
 * Fetch one load's groups and paint them, if it is still the load on its way and its
 * grouping and filters are still the panel's.
 *
 * @param {ReturnType<typeof currentFilterSnapshot>} state
 * @param {MetabrowserPublicGroupedLoad} load
 * @returns {Promise<boolean>}
 */
async function loadGroupedTreeInner(state, load) {
  var key = load.key;
  var preserve = !load.first;
  var owns = () => load.current() && filesPanelUsesGroupedSource() && key === currentGroupedKey();
  var data;
  var sections;
  try {
    data = await fetchGroups(treeFilterModel.groupsUrl(state, treeFilterSizeFloors(), 2), {
      preserve,
      signal: load.signal,
      load,
    });
    sections = treeFilterModel.groupSections(data);
    observeFileAges(data.ages);
  } catch (error) {
    // A refresh that fails keeps the sections on screen; its pacing retries it with a
    // backoff (requestGroupedRefresh). A first load has nothing to keep.
    if (owns() && !preserve) {
      failGroupedTree(error);
    }
    return false;
  }
  if (!owns()) {
    return false;
  }
  if (data.tally_cache_status === "scanning") {
    startIndexProgressPolling();
  }
  applyFilterTallies(data);
  if (preserve) {
    await fetchReopenedFolders(sections, owns);
    if (!owns()) {
      return false;
    }
  }
  // The groups partition what the filter keeps, so their counts add up to its total: the
  // line under the tally says how many files the sections hold.
  _filteredTreeTotals = {
    files: sections.reduce((sum, section) => sum + (section.files ?? 0), 0),
    size: sections.reduce((sum, section) => sum + (section.size ?? 0), 0),
  };
  var truncationHtml =
    data.tally_cache_status === "truncated"
      ? treeTruncationNoteHtml(data.tally_cache_max_files)
      : "";
  _perf.measure(
    preserve ? "renderTreeNodes:groupsRefresh" : "renderTreeNodes:groups",
    () =>
      preserve
        ? refreshGroupedSections(sections, truncationHtml)
        : renderGroupedSections(sections, truncationHtml),
    { nodes: sections.reduce((sum, section) => sum + section.tree.length, 0) },
  );
  return true;
}

// Grouping asks the server for every group at once, one pass over the index
// (`GroupedTreeQuery`): about 0.1 s on 100,000 files, where the ungrouped tree's rows take
// a few milliseconds (docs/design-system.md, "Grouping the Files Tree"). So the grouping a
// reader is about to choose is asked for ahead, when the pointer presses its row or the
// keyboard rests on it, and the choice takes the answer already on its way
// (tree-filter-model.js, groupPrefetchUrl and createGroupsPrefetch). An answer is kept
// until GROUPS_PREFETCH_TTL_MS passes; one a file change made stale still serves the
// choice, which then refreshes, and a refresh always asks again.
var GROUPS_PREFETCH_TTL_MS = 10000;

// How long keyboard focus rests on a Group by row before it asks for that grouping ahead.
// A row passed over on the way to another must ask for nothing: the server runs one
// grouped pass at a time, so a pass for a row passed over delays the chosen one by its
// whole length, and when passes overlapped one started 0, 100, or 250 ms ahead made the
// chosen grouping take 1.96, 1.79, or 1.43 times as long (review B of #466, on 260,000
// files). Pressing arrow keys walks rows about every 0.12-0.28 s (the keystroke-level
// model's K for skilled to average typists), and a held arrow key here repeats every 30 ms,
// so 300 ms passes over a walk; a choice comes after the reader has read the row, about
// 1.35 s (the model's M), so a row rested on still asks a second ahead of the choice, more
// than a pass takes on that folder (0.3-0.6 s).
var GROUPS_PREFETCH_DWELL_MS = 300;

/**
 * @param {string} url
 * @param {AbortSignal} [signal]
 */
function groupsRequest(url, signal) {
  return fetch(url, { cache: "no-store", signal }).then((resp) => {
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    return _perf.measureAsync("apiTreeGroups:json", () => resp.json());
  });
}

var groupsPrefetch = treeFilterModel.createGroupsPrefetch({
  now: () => performance.now(),
  ttlMs: GROUPS_PREFETCH_TTL_MS,
  dwellMs: GROUPS_PREFETCH_DWELL_MS,
  setTimer: (callback, ms) => setTimeout(callback, ms),
  clearTimer: (timer) => clearTimeout(/** @type {ReturnType<typeof setTimeout>} */ (timer)),
  start(url) {
    var controller = new AbortController();
    var answer = groupsRequest(url, controller.signal);
    // A prefetch nobody takes fails quietly; the choice that takes it reports its own.
    answer.catch(() => {});
    return { answer, abort: () => controller.abort() };
  },
});

/**
 * The answer a load paints: the one its press asked for ahead, if one is on its way, or a
 * request of its own. A cancel of the load reaches either.
 *
 * @param {string} url
 * @param {{ preserve?: boolean, signal?: AbortSignal, load?: MetabrowserPublicGroupedLoad }} options
 */
function fetchGroups(url, options) {
  var kept = options.preserve ? null : groupsPrefetch.take(url);
  if (!kept) {
    return groupsRequest(url, options.signal);
  }
  options.signal?.addEventListener("abort", kept.abort, { once: true });
  if (kept.stale) {
    // Asked for before a file changed: it paints, as it comes sooner than a new answer
    // would, and the sections then refresh once (createGroupedLoads).
    options.load?.refreshAfter();
  }
  return kept.answer;
}

/**
 * Ask ahead for the grouping whose Group by row the pointer pressed.
 *
 * @param {Event} event
 */
function prefetchPressedGrouping(event) {
  var row = /** @type {Element | null} */ (event.target)?.closest?.(
    '#filter-group-menu .chip-menu-item[data-chip-key="group"]',
  );
  var url = row ? groupingRowPrefetchUrl(row) : null;
  if (url) {
    groupsPrefetch.want(url);
  }
}

/**
 * Keyboard focus moved to a Group by row (filter-controls.js, onMenuFocus): ask for its
 * grouping once focus has rested there (GROUPS_PREFETCH_DWELL_MS), and still is there.
 * Focus alone is not intent: a rebuild of the bar puts focus back on the row that had it,
 * which is no reader's move, and reports nothing.
 *
 * @param {string} key
 * @param {string | null} value
 */
function restOnGroupingRow(key, value) {
  if (key !== "group") {
    return;
  }
  var url = treeFilterModel.groupPrefetchUrl(
    value ?? "none",
    currentFilterSnapshot(),
    treeFilterSizeFloors(),
  );
  groupsPrefetch.rest(url, () => focusedGroupingValue() === (value ?? "none"));
}

// The grouping of the Group by row focus is on, "none" for No grouping, or null.
function focusedGroupingValue() {
  var row = document.activeElement?.closest?.(
    '#filter-group-menu .chip-menu-item[data-chip-key="group"]',
  );
  if (!row) {
    return null;
  }
  return row.hasAttribute("data-chip-any") ? "none" : row.getAttribute("data-chip-value");
}

/**
 * The request a Group by row asks for ahead, if any (tree-filter-model.js, groupPrefetchUrl).
 *
 * @param {Element} row
 */
function groupingRowPrefetchUrl(row) {
  return treeFilterModel.groupPrefetchUrl(
    row.hasAttribute("data-chip-any") ? "none" : row.getAttribute("data-chip-value") || "",
    currentFilterSnapshot(),
    treeFilterSizeFloors(),
  );
}

/** @param {unknown} cause */
function failGroupedTree(cause) {
  console.warn("loadGroupedTree: could not load the groups", cause);
  var panel = document.getElementById("tab-files");
  if (panel) {
    panel.innerHTML =
      '<div class="preview-empty" role="alert">Could not load files. Reload the page to try again.</div>';
  }
}

/**
 * A section heading's inner markup: the group's name, then its file count beside it after
 * the separator, as every heading's tally sits (docs/design-system.md, "Heading Tallies").
 * The separator's dot is hidden from assistive technology, so the heading reads "Older
 * 10,004 files". A group the source could not count (a truncated Git index) has no tally.
 * A name too long for a narrow pane is cut short, and its tooltip then gives the whole
 * of it; while the name is whole the tooltip repeats it, so it does not show
 * (`tipAddsInformation`; docs/design-system.md, "Tooltips Add Information").
 * A type group's name follows its category's icon, and an age group has none
 * ("File-Type Category Icons"); a refresh rewrites a kept heading from here, so it keeps it.
 *
 * @param {MetabrowserPublicTreeSection} section
 */
function treeSectionHeadingHtml(section) {
  var label =
    (ICONS.withClass?.(section.icon, "category-icon") || "") +
    `<span class="tree-section-label" data-tip-text="${esc(section.label)}">${esc(section.label)}</span>`;
  if (section.files === null) {
    return label;
  }
  var unit = section.files === 1 ? "file" : "files";
  return (
    label +
    `<span class="heading-tally"> <span class="heading-tally-dot" aria-hidden="true">·</span> ` +
    `<span class="heading-tally-figure">${esc(section.files.toLocaleString())}</span> ${unit}</span>`
  );
}

/**
 * One section's tree, which its heading names.
 *
 * @param {MetabrowserPublicTreeSection} section
 * @param {Array<Record<string, any>>} nodes
 * @param {Set<string>} expandedPaths
 */
function treeSectionTreeHtml(section, nodes, expandedPaths) {
  // The heading's id is the panel's, outside the section's scope (treeSectionHtml).
  var labelledBy = treeDomId("tree-section", section.key);
  return withTreeIdScope(section.key, () =>
    renderTreeNodes(nodes, true, {
      ...treeRenderOptionsForElement(null),
      section: section.key,
      treeLabelledBy: labelledBy,
      defaultExpandedPaths: expandedPaths,
    }),
  );
}

/**
 * One section: the group's heading, in the menu group pattern (docs/design-system.md,
 * "Groups in a Menu"), and its tree.
 *
 * @param {MetabrowserPublicTreeSection} section
 * @param {Array<Record<string, any>>} nodes
 * @param {Set<string>} expandedPaths
 */
function treeSectionHtml(section, nodes, expandedPaths) {
  var headingId = treeDomId("tree-section", section.key);
  return (
    `<section class="tree-section" data-tree-group="${esc(section.key)}"` +
    ` aria-labelledby="${esc(headingId)}">` +
    `<div class="group-heading tree-section-heading" id="${esc(headingId)}">` +
    `${treeSectionHeadingHtml(section)}</div>` +
    `${treeSectionTreeHtml(section, nodes, expandedPaths)}</section>`
  );
}

function treeViewportRowBudget() {
  var treeContent = document.getElementById("tree-content");
  var rowHeight = parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue(
      TREE_AUTO_EXPAND_ROW_HEIGHT_PROPERTY,
    ),
  );
  return window.MetabrowserTreeExpansion.visibleRowBudget(
    treeContent?.clientHeight || 0,
    rowHeight,
    TREE_AUTO_EXPAND_FALLBACK_ROWS,
  );
}

/**
 * Paint a new grouping's sections into the Files panel under the tally row. Each section
 * opens folders from its share of the viewport's row budget
 * (tree-filter-model.js, sectionRowBudget).
 *
 * @param {MetabrowserPublicTreeSection[]} sections
 * @param {string} truncationHtml
 */
function renderGroupedSections(sections, truncationHtml) {
  var panel = document.getElementById("tab-files");
  if (!panel) {
    return;
  }
  treeKeyboard?.prepareForMutation();
  pendingTreePages.clear();
  pendingTreePageId = 0;
  var share = treeFilterModel.sectionRowBudget(treeViewportRowBudget(), sections.length);
  var body = sections
    .map((section) =>
      treeSectionHtml(
        section,
        section.tree,
        window.MetabrowserTreeExpansion.chooseDefaultExpandedPaths(
          /** @type {any} */ (section.tree),
          share,
          TREE_PAGE_SIZE,
        ),
      ),
    )
    .join("");
  panel.innerHTML =
    truncationHtml + (body || '<div class="recent-empty">No files match the filters.</div>');
  applyTreeFilters();
  reconcilePendingTallyDiagnostics();
  synchronizeTreeNow();
  scheduleSubtreePrefetch();
}

/**
 * Before a refresh paints, fetch the children of each folder the reader has open that
 * neither the answer nor the cache holds (a write in a folder drops its cached subtree),
 * a level at a time, so the refresh paints every one of them open in one frame and the
 * focused row inside them is still there to keep. A fetch that fails leaves its folder
 * closed; each is asked for once.
 *
 * @param {MetabrowserPublicTreeSection[]} sections
 * @param {() => boolean} owns
 */
async function fetchReopenedFolders(sections, owns) {
  /** @type {Set<string>} */
  var asked = new Set();
  for (;;) {
    var opened = openedSectionFolders();
    /** @type {Promise<unknown>[]} */
    var requests = [];
    for (const section of sections) {
      var plan = treeFilterModel.graftOpenedFolders(
        section.tree,
        opened.get(section.key) || [],
        (path) => subtreeCache.get(subtreeCacheKey(path, section.key)),
      );
      for (const path of plan.fetch) {
        var key = subtreeCacheKey(path, section.key);
        if (!asked.has(key)) {
          asked.add(key);
          requests.push(fetchSubtree(path, section.key).catch(() => null));
        }
      }
    }
    if (requests.length === 0 || !owns()) {
      return;
    }
    await Promise.all(requests);
  }
}

/**
 * Refresh the sections on screen in place, after files changed: each kept section's tree
 * is rebuilt with the folders the reader had open put back from the answer and from cached
 * subtrees (tree-filter-model.js, graftOpenedFolders; fetchReopenedFolders filled the
 * cache first), its count updated, new sections added in order and emptied ones removed,
 * and the scroll position and the focused row kept, all in one frame.
 *
 * @param {MetabrowserPublicTreeSection[]} sections
 * @param {string} truncationHtml
 */
function refreshGroupedSections(sections, truncationHtml) {
  var panel = document.getElementById("tab-files");
  if (!panel) {
    return;
  }
  var scroller = document.getElementById("tree-content");
  var scrollTop = scroller ? scroller.scrollTop : 0;
  var focused = /** @type {HTMLElement | null} */ (document.activeElement);
  var focusedId = focused?.closest?.("#tab-files .tree-section") ? focused.dataset.treeId : "";
  var opened = openedSectionFolders();
  treeKeyboard?.prepareForMutation();
  var mounted = new Map(
    Array.from(panel.querySelectorAll(":scope > .tree-section")).map((element) => [
      /** @type {HTMLElement} */ (element).dataset.treeGroup || "",
      /** @type {HTMLElement} */ (element),
    ]),
  );
  /** @type {HTMLElement | null} */
  var previous = null;
  for (const section of sections) {
    var graft = treeFilterModel.graftOpenedFolders(
      section.tree,
      opened.get(section.key) || [],
      (path) => subtreeCache.get(subtreeCacheKey(path, section.key)),
    );
    var element = mounted.get(section.key);
    mounted.delete(section.key);
    if (element) {
      var heading = element.querySelector(":scope > .tree-section-heading");
      if (heading) {
        heading.innerHTML = treeSectionHeadingHtml(section);
      }
      var tree = element.querySelector(':scope > [role="tree"]');
      var template = document.createElement("template");
      template.innerHTML = treeSectionTreeHtml(section, graft.tree, new Set(graft.expanded));
      if (tree) {
        tree.replaceWith(template.content);
      } else {
        element.append(template.content);
      }
    } else {
      var added = document.createElement("template");
      added.innerHTML = treeSectionHtml(section, graft.tree, new Set(graft.expanded));
      element = /** @type {HTMLElement} */ (added.content.firstElementChild);
      if (previous) {
        previous.after(element);
      } else {
        var lead = panel.querySelector(":scope > .tree-section");
        if (lead) {
          lead.before(element);
        } else {
          panel.append(element);
        }
      }
    }
    previous = element;
  }
  for (const gone of mounted.values()) {
    gone.remove();
  }
  panel.querySelector(":scope > .recent-empty")?.remove();
  if (sections.length === 0) {
    panel.insertAdjacentHTML(
      "beforeend",
      '<div class="recent-empty">No files match the filters.</div>',
    );
  }
  panel.querySelector(":scope > .tree-truncation-note")?.remove();
  if (truncationHtml) {
    panel.insertAdjacentHTML("afterbegin", truncationHtml);
  }
  if (scroller) {
    scroller.scrollTop = scrollTop;
  }
  if (focusedId) {
    queryHtml(`#tab-files [data-tree-id="${escapePathForSelector(focusedId)}"]`)?.focus({
      preventScroll: true,
    });
  }
  applyTreeFilters();
  reconcilePendingTallyDiagnostics();
  synchronizeTreeNow();
  scheduleSubtreePrefetch();
}

/** The folders open in each section now. */
function openedSectionFolders() {
  /** @type {Map<string, string[]>} */
  var opened = new Map();
  for (const section of queryHtmlAll("#tab-files > .tree-section")) {
    var key = /** @type {HTMLElement} */ (section).dataset.treeGroup || "";
    var paths = Array.from(section.querySelectorAll(".tree-folder.expanded"))
      .map((row) => /** @type {HTMLElement} */ (row).dataset.path || "")
      .filter(Boolean);
    opened.set(key, paths);
  }
  return opened;
}

// The Files totals, a navigation metadata line: the markup and its words are
// navigation.js's (`treeSummaryHtml`), written with the shell's own text helpers, so
// tests/dom/tree-summary-line-session.js runs exactly what paints.
// A function, not a constant: the shell can paint a tally before this line has run.
function treeSummaryFormat() {
  return { formatCountParts, formatSize };
}
function treeSummaryHtml(summary, fallbackFiles, fallbackSize) {
  return window.MetabrowserNavigationRoute.treeSummaryHtml(
    summary,
    fallbackFiles,
    fallbackSize,
    treeSummaryFormat(),
    rootTotals().keepsIgnoredLine(),
  );
}

// What the Files totals line is drawn from (navigation.js, `createRootTotals`).
function rootTotals() {
  _rootTotals ??= window.MetabrowserNavigationRoute.createRootTotals({
    gitRevision: isGitRevisionSource(),
    shell: window.METABROWSER_INITIAL_TREE?.summary ?? null,
  });
  return _rootTotals;
}

// Draw the totals line in place: the first line of the Files metadata band, outside the
// panel, so a source swap repaints the panel and leaves the band's lines as they are.
/** @param {string} html */
function paintTreeSummary(html) {
  var row = document.querySelector(".tree-summary");
  if (!row) {
    filesMetadataBand()?.insertAdjacentHTML("afterbegin", html);
  } else if (row.outerHTML !== html) {
    row.outerHTML = html;
  }
}

// The band the Files totals and the remarks on them stand in (server.py draws it).
function filesMetadataBand() {
  return document.getElementById("nav-metadata-files");
}

// The root's tallies, asked of the server again, for the filter menus' counts and the
// totals line while the root's entry has none; depth=0 so the response is the tally.
//
// One request at a time, however many callers ask (createRootSummaryRefresh in
// navigation.js). A live tree upserts its root on every write, and each answer is a
// pass over the whole index: on a 303,000-file tree with writes every 250 ms, one
// WebKit page held up to ten of these requests, five at the server at once, each
// answered in about 3.2 s, and the Commits tab waited behind them; with four pages its
// first request was still unanswered 90 s after Commits was opened
// (explorations/tree-summary-storm/README.md). The next request waits at least
// ROOT_SUMMARY_MIN_INTERVAL_MS, or twice the last one's duration, after it, so a page
// spends at most a third of a busy tree's time waiting on its tallies, and an isolated
// change still shows after the debounce alone.
var ROOT_SUMMARY_MIN_INTERVAL_MS = 2000;
var ROOT_SUMMARY_COST_FACTOR = 2;
// Each failure in a row doubles the spacing, until it reaches this. The cap bounds only
// that backoff: a slow answer still waits twice its own duration, however long.
var ROOT_SUMMARY_MAX_INTERVAL_MS = 30000;
/** @type {ReturnType<Window["MetabrowserNavigationRoute"]["createRootSummaryRefresh"]> | null} */
var _rootSummaryRefresh = null;

// Built on first use: the debounce is a setting declared further down this file.
function rootSummaryRefresh() {
  _rootSummaryRefresh ??= window.MetabrowserNavigationRoute.createRootSummaryRefresh({
    fetchSummary: fetchRootSummary,
    wanted: rootSummaryWanted,
    now: () => performance.now(),
    setTimer: (callback, ms) => setTimeout(callback, ms),
    debounceMs: RECENT_RECLUSTER_DEBOUNCE_MS * 5,
    minIntervalMs: ROOT_SUMMARY_MIN_INTERVAL_MS,
    costFactor: ROOT_SUMMARY_COST_FACTOR,
    maxIntervalMs: ROOT_SUMMARY_MAX_INTERVAL_MS,
  });
  return _rootSummaryRefresh;
}

function scheduleRootSummaryRefresh() {
  rootSummaryRefresh().request();
}

// Whether a fresh summary would be seen now. Either summary row, not just the split
// one. A first paint that landed before the index could answer renders the plain
// fallback row, and gating on the split row means the refresh that would replace it
// can never run — so the filter tallies keep whatever partial counts they were built
// with, for the life of the page, while the totals beside them stay live because
// updateRootAggregatePresentation patches those directly. Selecting the shared class
// lets the fallback be upgraded once the index has something to say.
//
// A hidden page, or a Files panel behind another tab, shows neither the row nor the
// filter bar: its refresh waits, and resumeRootSummaryRefresh sends it on return.
function rootSummaryWanted() {
  if (document.visibilityState === "hidden" || !document.querySelector(".tree-summary")) {
    return false;
  }
  var files = document.getElementById("tab-files");
  return files?.style.display !== "none";
}

function resumeRootSummaryRefresh() {
  _rootSummaryRefresh?.resume();
  _groupedRefresh?.resume();
}

// Files changing under Group by sections: refresh the sections, once the burst settles,
// keeping the folders the reader opened. A change can move a file into another group
// (a write moves it to Live) or add one a section must show, and only the server says
// where it goes. Each refresh asks for every group, so it is paced as the tally refresh
// is (createRootSummaryRefresh): at least ROOT_SUMMARY_MIN_INTERVAL_MS apart, or twice
// the last refresh's duration, and only while the Files panel is on screen.
/** @type {ReturnType<Window["MetabrowserNavigationRoute"]["createRootSummaryRefresh"]> | null} */
var _groupedRefresh = null;

function requestGroupedRefresh() {
  _groupedRefresh ??= window.MetabrowserNavigationRoute.createRootSummaryRefresh({
    fetchSummary: () =>
      filesPanelUsesGroupedSource() ? loadGroupedTree({ preserve: true }) : Promise.resolve(true),
    wanted: () =>
      filesPanelUsesGroupedSource() &&
      document.visibilityState !== "hidden" &&
      document.getElementById("tab-files")?.style.display !== "none",
    now: () => performance.now(),
    setTimer: (callback, ms) => setTimeout(callback, ms),
    debounceMs: RECENT_RECLUSTER_DEBOUNCE_MS * 5,
    minIntervalMs: ROOT_SUMMARY_MIN_INTERVAL_MS,
    costFactor: ROOT_SUMMARY_COST_FACTOR,
    maxIntervalMs: ROOT_SUMMARY_MAX_INTERVAL_MS,
  });
  _groupedRefresh.request();
}

/**
 * Fetch the root's tallies and paint them.
 *
 * @returns {Promise<boolean>} false when the server did not answer, so the refresh
 *   asks again after its backoff
 */
async function fetchRootSummary() {
  var data;
  try {
    var resp = await fetch("/api/tree?depth=0");
    if (!resp.ok) {
      return false;
    }
    data = await resp.json();
  } catch (_error) {
    // A failed refresh leaves the previous figures in place, which
    // is better than blanking a number the user is reading.
    return false;
  }
  if (!data?.summary || !_lastTreeRender) {
    return true;
  }
  rootTotals().fromSummary(data.summary, data.tally_cache_status);
  if (!document.querySelector(".tree-summary")) {
    return true;
  }
  applyFilterTallies(data);
  paintTreeSummary(treeSummaryHtml(rootTotals().totals(), null, null));
  return true;
}

// Last /api/tree payload plus the chrome rendered above it. Cached so
// clearing a recency filter can restore the full tree from memory
// instead of refetching on every chip click.
var _lastTreeRender = null;
// Match totals from the last filtered /api/tree response, or null when
// nothing is filtered. Shape: {files, size, entries}.
var _filteredTreeTotals = null;

/**
 * The folders the Files tree opens when it is drawn for Home (*asHome*), as a fresh load of
 * `/view/` opens them: none on a page that paints the root's rows itself
 * (*firstPaintInlinesTree*, a folder's), and on a pin's page, which has no such rows, the
 * planner's, as any other draw. `undefined` leaves the choice to the planner
 * (renderTreeNodes), whose budget is the viewport's.
 *
 * @param {boolean} asHome
 * @param {boolean} firstPaintInlinesTree
 * @returns {{defaultExpandedPaths: Set<string>} | undefined}
 */
function homeTreeExpansion(asHome, firstPaintInlinesTree) {
  return asHome && firstPaintInlinesTree ? { defaultExpandedPaths: new Set() } : undefined;
}

// Paint #tab-files from that cache. Returns false when nothing has
// been fetched yet, so the caller can fall back to loadTree(). Drawn for Home
// (`asHome`), the tree opens the folders a fresh load of `/view/` opens
// (homeTreeExpansion).
/** @param {boolean} [asHome] */
function renderFilesFromTree(asHome = false) {
  if (!_lastTreeRender) {
    return false;
  }
  var snapshot = _lastTreeRender;
  treeKeyboard?.prepareForMutation();
  _perf.measure(
    "renderTreeNodes:root",
    () => {
      pendingTreePages.clear();
      pendingTreePageId = 0;
      var filesPanel = document.getElementById("tab-files");
      if (filesPanel) {
        var expansion = homeTreeExpansion(asHome, _firstPaintInlinesTree);
        filesPanel.innerHTML =
          snapshot.chromeHtml + renderTreeNodes(snapshot.tree, true, expansion);
      }
    },
    { nodes: snapshot.tree ? snapshot.tree.length : 0 },
  );
  applyTreeFilters();
  reconcilePendingTallyDiagnostics();
  synchronizeTreeNow();
  scheduleSubtreePrefetch();
  return true;
}

// Convert an /api/tree node to the FsEntry-shaped fields consumed by the live
// patch path. The two wire surfaces intentionally differ on time units:
// trees carry seconds while inventory events carry nanoseconds.
function treeNodeAsEntry(node) {
  var slash = node.path.lastIndexOf("/");
  return {
    ...node,
    parent: slash >= 0 ? node.path.substring(0, slash) : "",
    mtime_ns: node.mtime ? node.mtime * 1e9 : 0,
    newest_mtime_ns: node.mtime ? node.mtime * 1e9 : 0,
  };
}

// Every "more" row of the container: a reveal can leave one above the page it drew as
// well as the one that ends the folder (mountTreePageAt).
function removeDeferredPageForContainer(container) {
  for (const sentinel of queryHtmlAll(":scope > .tree-page-more[data-page-id]", container)) {
    pendingTreePages.delete(sentinel.dataset.pageId);
    sentinel.remove();
  }
}

// Reconcile one mounted tree container without replacing it. Every container
// pages independently, while collapsed descendants stay in subtreeCache
// rather than becoming hidden DOM. The initial expansion planner bounds the
// only recursive path through this function to what the viewport can show.
function reconcileTreeContainer(container, nextNodes, work) {
  var nextVisible = nextNodes.slice(0, TREE_PAGE_SIZE);
  var visiblePaths = new Set(nextVisible.map((node) => node.path));
  var currentRows = Array.from(
    container.querySelectorAll(":scope > .tree-item:not(.tree-page-more)"),
  );
  for (var currentIndex = 0; currentIndex < currentRows.length; currentIndex++) {
    var currentPath = currentRows[currentIndex].dataset.path;
    if (currentPath && !visiblePaths.has(currentPath)) {
      _removeRenderedRowsImmediately(currentPath);
    }
  }

  // This container now has authoritative children. A failed lazy read is no
  // longer its answer, even when keyed reconciliation keeps the container.
  container.querySelector(":scope > .tree-lazy-error")?.remove();
  removeDeferredPageForContainer(container);
  for (var nextIndex = 0; nextIndex < nextVisible.length; nextIndex++) {
    var node = nextVisible[nextIndex];
    work.work_items += 1;
    applyCellPatch(treeNodeAsEntry(node), false);
    var reconciledRow = container.querySelector(
      `:scope > .tree-item[data-path="${escapePathForSelector(node.path)}"]`,
    );
    if (!reconciledRow) {
      continue;
    }
    reconciledRow.classList.remove("tree-item-flash-in");
    reconciledRow.dataset.treeLevel = String(treeLevelForContainer(container));
    reconciledRow.dataset.treePosition = String(nextIndex + 1);
    reconciledRow.dataset.treeSetSize = String(nextNodes.length);
    if (node.type !== "dir" || !Array.isArray(node.children)) {
      continue;
    }
    subtreeCache.set(subtreeCacheKey(node.path), node.children);
    var children = reconciledRow.nextElementSibling;
    if (
      reconciledRow.classList.contains("expanded") &&
      children?.classList.contains("tree-children")
    ) {
      reconcileTreeContainer(children, node.children, work);
    }
  }

  var tail = nextNodes.slice(TREE_PAGE_SIZE);
  if (tail.length > 0) {
    container.insertAdjacentHTML(
      "beforeend",
      deferredTreePageHtml(tail, {
        level: treeLevelForContainer(container),
        positionOffset: TREE_PAGE_SIZE,
        setSize: nextNodes.length,
      }),
    );
  }
}

// A mounted tree is already useful and visible. Reconcile a newer root answer
// into that keyed DOM instead of assigning panel.innerHTML again. This covers
// both the first fetch after the shell's inline paint and the terminal refresh
// that replaces a partial discovery snapshot. Mounted work is bounded by the
// root page and viewport expansion plan; unmounted descendants remain data
// until the reader asks for them.
function reconcileMountedTree(nextTree, chromeHtml) {
  const panel = document.getElementById("tab-files");
  const root = treeRootForPanel(panel);
  if (!panel || !root) {
    renderFilesFromTree();
    return;
  }

  var work = { work_items: 0 };
  _perf.measure(
    "reconcileTreeNodes:root",
    () => {
      treeKeyboard?.prepareForMutation();
      reconcileTreeContainer(root, nextTree, work);

      var chrome = document.createElement("div");
      chrome.innerHTML = chromeHtml;
      var truncation = panel.querySelector(":scope > .tree-truncation-note");
      var nextTruncation = chrome.querySelector(":scope > .tree-truncation-note");
      if (truncation && nextTruncation) {
        truncation.replaceWith(nextTruncation);
      } else if (truncation) {
        truncation.remove();
      } else if (nextTruncation) {
        panel.insertBefore(nextTruncation, panel.firstChild);
      }
    },
    work,
  );
  applyTreeFilters();
  reconcilePendingTallyDiagnostics();
  synchronizeTreeNow();
  scheduleSubtreePrefetch();
}

function treeTruncationNoteHtml(maxFiles) {
  var reason = maxFiles
    ? `Metabrowser stopped after ${formatCount(maxFiles)}`
    : "Metabrowser reached its file limit";
  return (
    '<div class="notice tree-truncation-note" data-severity="warning" role="status">' +
    "<strong>File list incomplete.</strong> " +
    reason +
    ", so some files and folders are not shown." +
    "</div>"
  );
}

function ensureTreeTruncationNote(maxFiles) {
  var filesPanel = document.getElementById("tab-files");
  if (!filesPanel || filesPanel.querySelector(".tree-truncation-note")) {
    return;
  }
  filesPanel.insertAdjacentHTML("afterbegin", treeTruncationNoteHtml(maxFiles));
}

// Populate the menu's file count and size from the live root inventory.
/** @param {DOMStringMap} dataset */
function rootDetailsStats(dataset) {
  return folderTooltipHtml(
    "",
    parseTipNumber(dataset.tipFiles),
    parseTipNumber(dataset.tipSize),
    undefined,
    false,
  );
}

function updateRootDetailsStats() {
  const heading = queryHtml(".header-path");
  const stats = queryHtml("#root-details .root-details-stats");
  if (heading && stats) {
    stats.innerHTML = rootDetailsStats(heading.dataset);
  }
}

function initRootDetails() {
  const details = document.getElementById("root-details");
  const panel = queryHtml("#root-details-panel");
  const trigger = details?.querySelector("button");
  const status = details?.querySelector(".root-details-status");
  if (!details || !panel || !trigger || !status) {
    return;
  }
  trigger.innerHTML = `<span aria-hidden="true">${ICONS.info ?? ""}</span>`;
  const location = details.querySelector(".root-details-location");
  const mirrorLocation = queryHtml(".header-path")?.dataset.mirrorLocation;
  if (location && mirrorLocation) {
    location.textContent = mirrorLocation;
  }
  const actions = details.querySelector(".root-details-actions");
  const revision = details.querySelector(".git-commit-revision[data-revision]");
  const tips = [document.getElementById("header-root-kind"), trigger].map((element) => ({
    element,
    text: element?.dataset.tipText,
  }));
  /** @param {boolean} open */
  const setOpen = async (open) => {
    if (open === !panel.hidden) {
      return;
    }
    panel.hidden = !open;
    trigger.ariaExpanded = String(open);
    for (const { element, text } of tips) {
      if (element && text) {
        if (open) {
          delete element.dataset.tipText;
          hideTooltipWithin(element);
        } else {
          element.dataset.tipText = text;
        }
      }
    }
    const url = details.dataset.repositoryUrl;
    if (!open) {
      status.textContent = "";
      return;
    }
    if (
      !(url && actions && !actions.childElementCount) &&
      !revision?.hasAttribute("data-revision")
    ) {
      return;
    }
    try {
      await window.MetabrowserAssets?.ensureAsset("sdk-views");
      if (panel.hidden) {
        return;
      }
      const commit = revision?.getAttribute("data-revision");
      if (revision && commit) {
        const copy = document.createElement("button");
        copy.className = "icon-btn icon-btn-reveal git-commit-revision-copy";
        copy.type = "button";
        copy.dataset.mbCopy = "text";
        copy.dataset.mbCopyText = commit;
        copy.dataset.mbCopyLabel = copy.dataset.tipText = "Copy revision";
        copy.setAttribute("aria-label", "Copy revision");
        copy.innerHTML = ICONS.copy ?? "";
        window.metabrowser.ownDelegate(copy);
        revision.append(copy);
        revision.removeAttribute("data-revision");
      }
      if (!url || !actions || actions.childElementCount) {
        return;
      }
      const items = window.metabrowser.externalLinkMenuItems(url, {
        onCopyResult: (result) => {
          status.textContent = result === "copied" ? "Link copied" : "Copy failed";
        },
      });
      for (const item of items) {
        item.removeAttribute("role");
        item.removeAttribute("tabindex");
        item.setAttribute("aria-describedby", "root-repository-url");
      }
      actions.append(...items);
      actions.removeAttribute("hidden");
    } catch (error) {
      console.warn("Could not load repository link actions", error);
      status.textContent = "Repository link actions are unavailable.";
    }
  };
  const dismissal = window.metabrowser.menus?.dismissible({
    name: "root-details-panel",
    trigger,
    inside: (node) => panel.contains(node),
    isOpen: () => !panel.hidden,
    close: () => void setOpen(false),
  });
  trigger.addEventListener("click", () => {
    void setOpen(Boolean(panel.hidden));
    dismissal?.[panel.hidden ? "closed" : "opened"]();
  });
}

// Lookup table from "page-more" sentinel id to the deferred slice.
// Keeps the closure per-renderer minimal — the click handler reads
// from this map and swaps the row in place.
var pendingTreePages = new Map();
var pendingTreePageId = 0;

var TREE_DIR_METRIC_SIZE = "size";
var TREE_DIR_METRIC_COUNT = "count";

function treeDirMetric(options) {
  return options && options.dirMetric === TREE_DIR_METRIC_COUNT
    ? TREE_DIR_METRIC_COUNT
    : TREE_DIR_METRIC_SIZE;
}

// Dir rows show total bytes when the panel is rendering the whole
// tree and descendant file count when it is rendering a recency
// result — aggregating bytes across "files modified in the last 24h"
// mixes incomparable things. Now that both sources render into
// #tab-files, the active source decides, not the element.
function treeRenderOptionsForElement(_el) {
  return filesPanelUsesRecentSource()
    ? { dirMetric: TREE_DIR_METRIC_COUNT }
    : { dirMetric: TREE_DIR_METRIC_SIZE };
}

function treeDirChipHtml(totalFiles, totalSize, options) {
  if (totalFiles === undefined && totalSize === undefined) {
    return "";
  }
  if (treeDirMetric(options) === TREE_DIR_METRIC_COUNT) {
    return countHtml(totalFiles, "tree-item-size");
  }
  if (isPendingNumber(totalSize) && !isPendingNumber(totalFiles)) {
    return countHtml(totalFiles, "tree-item-size");
  }
  return sizeHtml(totalSize, "tree-item-size");
}

function treeDomId(prefix, identity) {
  var scoped = _treeIdScope ? `${_treeIdScope}|${identity}` : String(identity);
  return `metabrowser-${prefix}-${encodeURIComponent(scoped)}`;
}

// A Group by section's tree is named by its heading; the one ungrouped tree is "Files".
function treeRootHtml(content, labelledBy) {
  var name = labelledBy ? `aria-labelledby="${esc(labelledBy)}"` : 'aria-label="Files"';
  return `<div class="tree-root" role="tree" ${name}${treeDepthStyle(1)}>${content}</div>`;
}

// Nesting depth as a custom property on the group, not as a margin on it.
// A row's box has to span the whole panel at every level — the selection
// and hover backgrounds are the reader's "you are here", and an inset box
// makes them read as a different, narrower control at each level. The group
// therefore keeps no box of its own and publishes the depth its children
// paint their own left inset from, which also indents the lazy-load and
// empty-folder notes without them needing a row of their own.
function treeDepthStyle(depth) {
  return ` style="--tree-depth:${Math.max(1, Number(depth) || 1)}"`;
}

// Every tree disclosure uses this exact child-group shape. The keyboard
// navigator derives aria-expanded and visibility from the collapsed class, so
// an inline display override is not an equivalent hiding mechanism.
function treeChildGroupStartHtml(groupId, depth, expanded) {
  return (
    `<div class="tree-children${expanded ? "" : " tree-children-collapsed"}"` +
    ` id="${esc(groupId)}" role="group"${treeDepthStyle(depth)}>`
  );
}

// Container kinds by extension, injected by the server from the loaded
// plugin manifests (docs/project/architecture/arch-plugin-system.md). A file
// whose extension is listed plays the folder-like role in addition to its own.
var CONTAINER_EXTS = window.METABROWSER_CONTAINER_EXTS || {};

function containerForNode(node) {
  var name = String(node?.name || "");
  var dot = name.lastIndexOf(".");
  if (dot <= 0) {
    return null;
  }
  return CONTAINER_EXTS[name.slice(dot).toLowerCase()] || null;
}

// Child entries of a container render as ordinary item-like rows: the
// same selection path, the same keyboard model, no new machinery.
function renderContainerChildren(rows, options) {
  var level = options.level;
  var parts = [];
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var labelId = treeDomId("tree-label", `container-child:${row.path}`);
    var attributes = treeItemAttributes({
      kind: "file",
      path: row.path,
      level: level,
      position: i + 1,
      setSize: rows.length,
      selected: currentPath === row.path,
      labelId: labelId,
    });
    parts.push(
      `<div class="tree-item tree-file tree-container-child${row.muted ? " tree-item-muted" : ""}"${attributes} data-action="select" data-path="${esc(row.path)}" data-tip-type="file" data-tip-name="${esc(row.name)}">`,
      row.badge
        ? `<span class="tree-container-badge" aria-hidden="true">${esc(row.badge)}</span>`
        : '<span class="tree-item-icon"></span>',
      `<span class="tree-item-name" id="${labelId}">`,
      esc(row.name),
      "</span>",
      "</div>",
    );
  }
  return parts.join("");
}

function treeItemAttributes(options) {
  var identity =
    options.kind === "page" ? `page:${options.pageId}` : `${options.kind}:${options.path || ""}`;
  // A folder can stand in several Group by sections: its identity, which the keyboard
  // navigator finds rows and repairs focus by, names the section, as its DOM ids do.
  if (_treeIdScope) {
    identity = `${_treeIdScope}|${identity}`;
  }
  var attributes =
    ' role="treeitem" tabindex="-1"' +
    ` data-tree-kind="${esc(options.kind)}"` +
    ` data-tree-id="${esc(identity)}"` +
    ` data-tree-level="${options.level}"` +
    ` data-tree-position="${options.position}"` +
    ` data-tree-set-size="${options.setSize}"` +
    ` aria-level="${options.level}"` +
    ` aria-posinset="${options.position}"` +
    ` aria-setsize="${options.setSize}"` +
    ` aria-labelledby="${esc(options.labelId)}"`;
  if (typeof options.expanded === "boolean") {
    attributes += ` aria-expanded="${options.expanded}"`;
  }
  if (typeof options.selected === "boolean") {
    attributes += ` aria-selected="${options.selected}"`;
  }
  if (options.ownedGroupId) {
    attributes += ` aria-owns="${esc(options.ownedGroupId)}"`;
  }
  if (options.pageId) {
    attributes += ` data-page-id="${esc(options.pageId)}"`;
  }
  return attributes;
}

function treeRootForPanel(panel) {
  return panel?.querySelector(":scope > .tree-root") || null;
}

function treeLevelForContainer(container) {
  if (container?.getAttribute("role") === "tree") {
    return 1;
  }
  var owner = container?.previousElementSibling;
  var ownerLevel = owner ? Number(owner.getAttribute("aria-level")) : 0;
  return Number.isFinite(ownerLevel) && ownerLevel > 0 ? ownerLevel + 1 : 1;
}

function deferredTreePageHtml(nodes, options) {
  if (!nodes.length) {
    return "";
  }
  var pageId = String(++pendingTreePageId);
  var pageLabelId = treeDomId("tree-label", `page:${pageId}`);
  pendingTreePages.set(pageId, {
    nodes: nodes,
    options: options,
  });
  var pageAttributes = treeItemAttributes({
    kind: "page",
    path: "",
    pageId: pageId,
    level: options.level,
    position: options.positionOffset + 1,
    setSize: options.setSize,
    labelId: pageLabelId,
  });
  return (
    `<div class="tree-item tree-page-more"${pageAttributes} data-action="page-more">` +
    `<span id="${pageLabelId}">` +
    "Show " +
    String(nodes.length) +
    " more (" +
    String(options.setSize) +
    " total)" +
    "</span>" +
    "</div>"
  );
}

// A tree node's rendered name. A Git pin sends the display basename already
// decoded, so decoding it again would read `g1-data` as a wire token and turn
// `50%25-off.md` into `50%-off.md`. Only a filesystem identity carries the
// escaping `displayPath` exists to undo.
function treeNodeDisplayName(name) {
  var text = name || "";
  return isGitRevisionSource() ? text : window.MetabrowserNavigationRoute.displayPath(text);
}

// `options` is a small bag of render-mode flags forwarded into
// recursive calls. Currently:
//   options.dirMetric — "size" (default, Files panel) renders
//     total bytes when available; "count" (Recent panel) renders
//     descendant file count. Recent uses count because aggregating
//     bytes across "files modified in last 24h" is misleading.
//   options.defaultExpandedPaths — folders selected by the viewport-bounded
//     first-paint planner. Recursive calls share the same set.
function renderTreeNodes(nodes, isRoot, options) {
  options = options || {};
  if (isRoot && !options.defaultExpandedPaths) {
    var treeContent = document.getElementById("tree-content");
    var rowHeight = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue(
        TREE_AUTO_EXPAND_ROW_HEIGHT_PROPERTY,
      ),
    );
    var rowBudget = window.MetabrowserTreeExpansion.visibleRowBudget(
      treeContent?.clientHeight || 0,
      rowHeight,
      TREE_AUTO_EXPAND_FALLBACK_ROWS,
    );
    options.defaultExpandedPaths = window.MetabrowserTreeExpansion.chooseDefaultExpandedPaths(
      nodes,
      rowBudget,
      TREE_PAGE_SIZE,
    );
  }
  var defaultExpandedPaths = options.defaultExpandedPaths || new Set();
  var level = options.level || 1;
  var positionOffset = options.positionOffset || 0;
  var setSize = options.setSize || nodes.length;
  // Array-of-strings + join() is O(n); naive `+=` against a growing
  // string was hot on big trees because every concat copied the whole
  // accumulator. With ~35 k files at depth=4 this drops a frame's
  // worth of CPU off the first paint.
  var parts = [];
  // Cap per-call: a single direct child of N entries renders at most
  // TREE_PAGE_SIZE rows, the rest pages in on demand.
  var visibleCount = Math.min(nodes.length, TREE_PAGE_SIZE);
  var hidden = nodes.length - visibleCount;
  for (var ni = 0; ni < visibleCount; ni++) {
    var node = nodes[ni];
    var position = positionOffset + ni + 1;
    var mutedCls = "";
    if (node.gitignored) {
      mutedCls += " tree-item-gitignored";
    }
    if (
      node.type === "dir" &&
      (node.empty || (Array.isArray(node.children) && node.children.length === 0))
    ) {
      mutedCls += " tree-item-empty";
    }
    if (node.type === "dir") {
      // Explicit state (used by Recent clustering) wins over the bounded
      // first-paint plan.
      var defaultExpanded = defaultExpandedPaths.has(node.path);
      var expanded = typeof node.expanded === "boolean" ? node.expanded : defaultExpanded;
      var stateClass = expanded ? "expanded" : "collapsed";
      var dirAge = formatAge(node.mtime);
      var dirChip = treeDirChipHtml(node.total_files, node.total_size, options);
      var hasPotentialChildren =
        !node.empty && (!Array.isArray(node.children) || node.children.length > 0);
      var folderLabelId = treeDomId("tree-label", `folder:${node.path}`);
      var groupId = hasPotentialChildren ? treeDomId("tree-group", node.path) : "";
      var folderAttributes = treeItemAttributes({
        kind: "folder",
        path: node.path,
        level: level,
        position: position,
        setSize: setSize,
        expanded: hasPotentialChildren ? expanded : undefined,
        ownedGroupId: groupId,
        labelId: folderLabelId,
      });
      parts.push(
        `<div class="tree-item tree-folder disclosure-toggle ${stateClass}${mutedCls}"${folderAttributes} data-action="select-dir" data-path="${esc(node.path)}" data-tip-type="dir" data-tip-name="${esc(treeNodeDisplayName(node.name))}"${dataTipNumberAttr("files", node.total_files)}${dataTipNumberAttr("size", node.total_size)}${dataTipNumberAttr("mtime", node.mtime)}>`,
        `<span class="tree-toggle">${ICONS.toggle}</span>`,
        `<span class="tree-item-name" id="${folderLabelId}">`,
        esc(treeNodeDisplayName(node.name)),
        "</span>",
        '<span class="tree-item-age-inline">',
        dirAge,
        "</span>",
        dirChip,
        "</div>",
      );
      if (hasPotentialChildren) {
        parts.push(treeChildGroupStartHtml(groupId, level + 1, expanded));
        if (Array.isArray(node.children) && expanded) {
          parts.push(
            renderTreeNodes(node.children, false, {
              ...options,
              level: level + 1,
              positionOffset: 0,
              setSize: node.children.length,
            }),
          );
        } else if (Array.isArray(node.children)) {
          // The response already contains this subtree, but a collapsed folder
          // does not need it in the DOM. Cache the data and leave the same lazy
          // stub the expansion path understands; opening the folder mounts one
          // bounded page from memory without another request.
          subtreeCache.set(subtreeCacheKey(node.path, options.section), node.children);
          parts.push(
            '<div class="tree-lazy-placeholder mb-delayed-loading" data-tree-lazy-stub' +
              ' role="status" aria-label="Loading">' +
              '<span class="spinner spinner-sm" aria-hidden="true"></span>' +
              "</div>",
          );
        } else {
          // Lazy stub: server emits `children: null` past the depth
          // cap. Render a placeholder; click-to-expand fetches the
          // subtree via /api/tree?path=...
          parts.push(
            '<div class="tree-lazy-placeholder mb-delayed-loading" data-tree-lazy-stub' +
              ' role="status" aria-label="Loading">' +
              '<span class="spinner spinner-sm" aria-hidden="true"></span>' +
              "</div>",
          );
        }
        parts.push("</div>");
      }
    } else if (node.type === "symlink") {
      var linkAge = formatAge(node.mtime);
      var linkLabelId = treeDomId("tree-label", `symlink:${node.path}`);
      var linkAttributes = treeItemAttributes({
        kind: "symlink",
        path: node.path,
        level: level,
        position: position,
        setSize: setSize,
        selected: currentPath === node.path,
        labelId: linkLabelId,
      });
      parts.push(
        `<div class="tree-item tree-symlink${mutedCls}"${linkAttributes} data-action="select" data-path="${esc(node.path)}" data-tip-type="symlink" data-tip-name="${esc(treeNodeDisplayName(node.name))}"${dataTipNumberAttr("mtime", node.mtime)}>`,
        '<span class="tree-item-icon">',
        ICONS.fileSymlink,
        "</span>",
        `<span class="tree-item-name" id="${linkLabelId}">`,
        esc(treeNodeDisplayName(node.name)),
        "</span>",
        '<span class="tree-item-age-inline"><span class="tree-item-age">',
        linkAge,
        '</span><span class="tree-item-activity"></span></span>',
        "</div>",
      );
    } else {
      // Icon dispatch keys off the *logical* name so subtype matchers
      // (`.process.md`, `.runbook.md`, etc.) work on `foo.process.md.gz`.
      var fi = getFileIcon(getLogicalName(node));
      var fileAge = formatAge(node.mtime);
      var compressed = !!node.compressed;
      var iconCls = `tree-item-icon file-identity-icon ${fi.cls}${compressed ? " is-compressed" : ""}`;
      var compressionName = node.compression || "compressed";
      var compressionGlyph = compressionName === "gzip" ? "G" : "Z";
      var compressionBadge = compressed
        ? `<span class="compression-badge" data-tip-text="${esc(compressionName)} compressed">${compressionGlyph}</span>`
        : "";
      var logicalExtAttr = node.logical_ext ? ` data-logical-ext="${esc(node.logical_ext)}"` : "";
      // The index's bounded compound-tail extension, which the type filter
      // matches on. Separate from data-logical-ext, which means "inner
      // extension of a compressed artifact" and drives icon dispatch.
      var extAttr = node.ext ? ` data-ext="${esc(node.ext)}"` : "";
      var compressedAttr = compressed ? ' data-compressed="1"' : "";
      var fileLabelId = treeDomId("tree-label", `file:${node.path}`);
      var fileAttributes = treeItemAttributes({
        kind: "file",
        path: node.path,
        level: level,
        position: position,
        setSize: setSize,
        selected: currentPath === node.path,
        labelId: fileLabelId,
      });
      // A file whose kind declares the container capability is
      // folder-like too (arch-plugin-system.md): it keeps its file
      // identity and views, and gains a chevron that discloses the
      // entries inside it, fetched on first expand.
      var container = containerForNode(node);
      var containerGroupId = container ? treeDomId("tree-group", `container:${node.path}`) : "";
      if (container) {
        fileAttributes = treeItemAttributes({
          kind: "file",
          path: node.path,
          level: level,
          position: position,
          setSize: setSize,
          selected: currentPath === node.path,
          labelId: fileLabelId,
          expanded: false,
          ownedGroupId: containerGroupId,
        });
      }
      parts.push(
        `<div class="tree-item tree-file${container ? " tree-container disclosure-toggle collapsed" : ""}${mutedCls}"${fileAttributes} data-action="select" data-path="${esc(node.path)}"${container ? ` data-container-kind="${esc(container.kind)}" data-container-plugin="${esc(container.plugin)}" data-container-children="${esc(container.children)}"` : ""}${logicalExtAttr}${extAttr}${compressedAttr} data-tip-type="file" data-tip-name="${esc(treeNodeDisplayName(node.name))}"${dataTipNumberAttr("size", node.size)}${dataTipNumberAttr("mtime", node.mtime)}>`,
        container ? `<span class="tree-toggle">${ICONS.toggle}</span>` : "",
        '<span class="',
        iconCls,
        fi.style ? `" style="${esc(fi.style)}` : "",
        '">',
        fi.svg,
        compressionBadge,
        "</span>",
        `<span class="tree-item-name" id="${fileLabelId}">`,
        esc(treeNodeDisplayName(node.name)),
        "</span>",
        '<span class="tree-item-age-inline"><span class="tree-item-age">',
        fileAge,
        '</span><span class="tree-item-activity"></span></span>',
        sizeHtml(node.size, "tree-item-size"),
        "</div>",
      );
      if (container) {
        parts.push(treeChildGroupStartHtml(containerGroupId, level + 1, false), "</div>");
      }
    }
  }
  if (hidden > 0) {
    parts.push(
      deferredTreePageHtml(nodes.slice(visibleCount), {
        ...options,
        level: level,
        positionOffset: positionOffset + visibleCount,
        setSize: setSize,
      }),
    );
  }
  var content = parts.join("");
  return isRoot ? treeRootHtml(content, options.treeLabelledBy) : content;
}

// ── Lazy subtree loading ──────────────────────────────────────

// Keyed by path *and* the filter it was fetched under: a subtree fetched
// while the filter was wider is not an answer for a narrower one.
const subtreeCache = new Map();
const subtreeRetryTimers = new WeakMap();

// Inside a Group by section the key also names the group and the grouped filter, recency
// included: the same folder holds different rows in each section.
function subtreeCacheKey(path, group) {
  var filter = group ? treeUrl("", [], group) : treeFilterKey();
  return filter ? `${path}\u0000${filter}` : path;
}

// A spinner alone says "loading"; the surrounding row already says what
// is loading, so the generic label is left to screen readers. Callers
// pass visible copy only for a state a spinner cannot express on its own
// (see the still-scanning case in loadSubtree).
function treeLazyLoadingHtml(message) {
  return (
    '<div class="tree-lazy-placeholder mb-delayed-loading" role="status" aria-live="polite">' +
    '<span class="spinner spinner-sm" aria-hidden="true"></span>' +
    (message ? `<span>${esc(message)}</span>` : '<span class="sr-only">Loading folder…</span>') +
    "</div>"
  );
}

function treeLazyFailureHtml(message) {
  return (
    '<div class="tree-lazy-placeholder tree-lazy-error" role="alert">' +
    esc(message || "Could not load this folder.") +
    "</div>"
  );
}

function responseErrorDetail(body) {
  var text = String(body || "").trim();
  if (text) {
    try {
      var said = JSON.parse(text)?.error;
      if (typeof said === "string" && said.trim()) {
        return said.trim();
      }
    } catch (_error) {
      // Not JSON.
    }
  }
  return "The server could not complete the request.";
}

function responseErrorSummary(body, fallback) {
  var text = String(body || "").trim();
  if (text) {
    try {
      var parsed = JSON.parse(text);
      if (typeof parsed?.summary === "string" && parsed.summary.trim()) {
        return parsed.summary.trim();
      }
    } catch (_error) {
      // Plain-text responses use the caller's stable summary.
    }
  }
  return fallback;
}

function previewErrorHtml(summary, detail) {
  return (
    '<div class="preview-empty preview-error" role="alert">' +
    '<strong class="preview-error-title">' +
    esc(summary) +
    "</strong>" +
    '<span class="preview-error-detail">' +
    esc(detail) +
    "</span></div>"
  );
}

function subtreeIsExpanded(childrenEl) {
  if (!childrenEl?.parentNode) {
    return false;
  }
  var folder = childrenEl.previousElementSibling;
  return (
    !!folder &&
    folder.classList.contains("tree-folder") &&
    folder.classList.contains("expanded") &&
    !childrenEl.classList.contains("tree-children-collapsed")
  );
}

// An authoritative recovery preserves mounted folders, including their failed
// bodies. Retry just those still expanded; successful, collapsed and loading
// bodies have nothing to repair. loadSubtree replaces the failure immediately
// and joins any existing fetch. An identical shallow sentinel still invalidates
// failed deep reads; filtered membership waits for one authoritative root read.
// @param {boolean} [revalidate] A deduplicated sentinel, not a newly applied tree.
function retryFailedExpandedSubtrees(revalidate = false) {
  window.MetabrowserNavigationRoute.recoverFailedExpandedFolders({
    panel: document.getElementById("tab-files"),
    revision: isGitRevisionSource(),
    recent: filesPanelUsesRecentSource(),
    load(path, children) {
      if (revalidate) {
        const key = subtreeCacheKey(path, treeSectionKey(children));
        subtreeCache.delete(key);
        subtreeRequests.delete(key);
        if (filterState && filterHasConstraints(filterState.get())) {
          if (_rootTreeRequestsInFlight === 0) {
            void loadTree({ reconcileMountedRoot: true });
          }
          return;
        }
      }
      return loadSubtree(path, children);
    },
  });
}

function scheduleSubtreeRetry(path, childrenEl) {
  if (subtreeRetryTimers.has(childrenEl)) {
    return;
  }
  var delayMs = INDEX_PROGRESS_POLL_MS || 1000;
  var timer = setTimeout(() => {
    subtreeRetryTimers.delete(childrenEl);
    if (subtreeIsExpanded(childrenEl)) {
      loadSubtree(path, childrenEl, treeRenderOptionsForElement(childrenEl));
    }
  }, delayMs);
  subtreeRetryTimers.set(childrenEl, timer);
}

function clearSubtreeRetry(childrenEl) {
  var timer = subtreeRetryTimers.get(childrenEl);
  if (!timer) {
    return;
  }
  clearTimeout(timer);
  subtreeRetryTimers.delete(childrenEl);
}

function markFolderKnownEmpty(childrenEl) {
  var folder = childrenEl.previousElementSibling;
  if (!folder?.classList.contains("tree-folder")) {
    return;
  }
  folder.classList.add("tree-item-empty", "collapsed");
  folder.classList.remove("expanded");
  folder.removeAttribute("aria-expanded");
  folder.removeAttribute("aria-owns");
  childrenEl.remove();
}

// One request per path, shared by the click that expands a folder and the
// idle sweep that warms it. A click landing on a prefetch already in flight
// joins it instead of racing a second identical fetch.
const subtreeRequests = new Map();

function invalidateSubtreeCaches(ops) {
  const affected = new Set();
  const removed = new Set();
  for (const op of ops) {
    let path = op.op === "upsert" ? op.entry.path : op.path;
    if (op.op === "remove") {
      removed.add(path);
    }
    while (true) {
      affected.add(path);
      if (!path) {
        break;
      }
      path = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";
    }
  }
  // Invalidate every filter variant, including requests that began before the
  // event. Work follows changed ancestors and cached folders, not inventory size.
  for (const key of new Set([...subtreeCache.keys(), ...subtreeRequests.keys()])) {
    const path = key.split("\u0000", 1)[0];
    let stale = affected.has(path);
    for (let ancestor = path; ancestor && !stale; ) {
      stale = removed.has(ancestor);
      ancestor = ancestor.includes("/") ? ancestor.slice(0, ancestor.lastIndexOf("/")) : "";
    }
    if (stale) {
      subtreeCache.delete(key);
      subtreeRequests.delete(key);
    }
  }
}

function fetchSubtree(path, group) {
  const key = subtreeCacheKey(path, group);
  const existing = subtreeRequests.get(key);
  if (existing) {
    return existing;
  }
  const request = (async () => {
    const resp = await fetch(treeUrl(path, [`depth=${TREE_SUBTREE_FETCH_DEPTH}`], group), {
      cache: "no-store",
    });
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    const data = await _perf.measureAsync(
      "apiTreeSubtree:json",
      () => resp.json(),
      responsePerfMeta(resp, path),
    );
    if (!Array.isArray(data.tree)) {
      throw new Error("Malformed tree response");
    }
    if (subtreeRequests.get(key) !== request) {
      // An event invalidated this in-flight read. Join or start the fresh read
      // before it can replace live rows or repopulate the prefetch cache.
      return fetchSubtree(path, group);
    }
    _perf.measure(
      "knownFileCatalog:observeLazyTree",
      () => knownFileCatalog?.observeLazyTree(data.tree),
      { path: path, nodes: data.tree.length },
    );
    // A folder whose scan has not reached it yet reports empty; caching that
    // would answer every later expansion with a folder that has contents.
    const scanning = data.tree.length === 0 && data.tally_cache_status === "scanning";
    if (!scanning) {
      subtreeCache.set(key, data.tree);
    }
    return { tree: data.tree, scanning: scanning };
  })();
  subtreeRequests.set(key, request);
  const forget = () => {
    if (subtreeRequests.get(key) === request) {
      subtreeRequests.delete(key);
    }
  };
  request.then(forget, forget);
  return request;
}

async function loadSubtree(path, childrenEl, options) {
  // A folder inside a Group by section lists that group's members only.
  var group = treeSectionKey(childrenEl);
  options = { ...(options || treeRenderOptionsForElement(childrenEl)), section: group };
  treeKeyboard?.prepareForMutation();
  var cacheKey = subtreeCacheKey(path, group);
  if (subtreeCache.has(cacheKey)) {
    clearSubtreeRetry(childrenEl);
    _perf.measure(
      "renderTreeNodes:subtreeCache",
      () => {
        var cachedTree = subtreeCache.get(cacheKey);
        childrenEl.innerHTML = withTreeIdScope(group, () =>
          renderTreeNodes(cachedTree, false, {
            ...options,
            level: treeLevelForContainer(childrenEl),
            positionOffset: 0,
            setSize: cachedTree.length,
          }),
        );
      },
      { path: path, nodes: subtreeCache.get(cacheKey).length },
    );
    if (subtreeCache.get(cacheKey).length === 0) {
      markFolderKnownEmpty(childrenEl);
    }
    applyTreeFilters();
    synchronizeTreeNow();
    scheduleSubtreePrefetch();
    return;
  }
  childrenEl.innerHTML = treeLazyLoadingHtml();
  synchronizeTreeNow();
  try {
    const result = await fetchSubtree(path, group);
    var tree = result.tree;
    if (result.scanning) {
      treeKeyboard?.prepareForMutation();
      childrenEl.innerHTML = treeLazyLoadingHtml("Still scanning this folder…");
      startIndexProgressPolling();
      scheduleSubtreeRetry(path, childrenEl);
      synchronizeTreeNow();
      return;
    }
    clearSubtreeRetry(childrenEl);
    treeKeyboard?.prepareForMutation();
    _perf.measure(
      "renderTreeNodes:subtree",
      () => {
        childrenEl.innerHTML = tree.length
          ? withTreeIdScope(group, () =>
              renderTreeNodes(tree, false, {
                ...options,
                level: treeLevelForContainer(childrenEl),
                positionOffset: 0,
                setSize: tree.length,
              }),
            )
          : '<div class="tree-lazy-placeholder">This folder is empty.</div>';
      },
      { path: path, nodes: tree.length },
    );
    if (tree.length === 0) {
      markFolderKnownEmpty(childrenEl);
    }
    // Newly rendered children carry no filter classes yet, so without
    // this an expand under an active filter reveals the whole folder.
    applyTreeFilters();
    reconcilePendingTallyDiagnostics();
    synchronizeTreeNow();
    scheduleSubtreePrefetch();
  } catch (e) {
    console.warn(`loadSubtree failed for ${path}`, e);
    clearSubtreeRetry(childrenEl);
    treeKeyboard?.prepareForMutation();
    childrenEl.innerHTML = treeLazyFailureHtml(
      "Could not load this folder. Collapse and reopen it to try again.",
    );
    synchronizeTreeNow();
  }
}

// ── Subtree prefetch ────────────────────────────────────────────
// Warm lazy-stub rows on screen plus one screen of lookahead, re-arming on
// scroll and expansion. Skip collapsed ancestors; idle batches yield to selected
// work. DOM-order warming sent 32 offscreen requests on a 100,000-file tree
// (explorations/performance-loop/experiments/exp-002).
const SUBTREE_PREFETCH_MAX_CONCURRENT = 3;
const SUBTREE_PREFETCH_MAX_PER_SWEEP = 32;
const SUBTREE_PREFETCH_IDLE_TIMEOUT_MS = 2000;
// A reader who just opened a folder has said where they are, so warming its
// children is not speculation about which folder — only about the next click.
// That earns a timer instead of an idle callback: long enough for the
// expansion's own render to finish, short enough to beat the click after it.
// An idle callback is the wrong instrument here twice over, because a browser
// is free to defer one indefinitely when it decides the page is not busy in a
// way it cares about.
const SUBTREE_PREFETCH_AFTER_EXPAND_MS = 50;
// Screens of lookahead past the visible nav area. One is a scroll gesture's
// worth: far enough that a reader scrolling steadily stays ahead of the
// fetches, near enough that it is still a folder they are heading toward.
const SUBTREE_PREFETCH_LOOKAHEAD_SCREENS = 1;
let subtreePrefetchScheduled = false;

function pendingSubtreePaths() {
  const paths = [];
  const stubs = treePane.querySelectorAll("[data-tree-lazy-stub]");
  // One layout read for the scroller, then one per stub owner, all inside the
  // idle callback that already owns this work. Without a scroller — a shell
  // that has not mounted the tree yet — every mounted stub is a candidate,
  // which is the old behavior and the safe direction to fail in.
  const scroller = document.getElementById("tree-content");
  const measured = scroller ? scroller.getBoundingClientRect() : null;
  // A zero-height scroller is a shell that has not laid out, not a viewport
  // with nothing in it. Bounding against it would reject every candidate and
  // silently disable the prefetch, so it falls back to the unbounded sweep.
  const view = measured && measured.height > 0 ? measured : null;
  const lookahead = view ? view.height * SUBTREE_PREFETCH_LOOKAHEAD_SCREENS : 0;
  for (let index = 0; index < stubs.length; index += 1) {
    if (paths.length >= SUBTREE_PREFETCH_MAX_PER_SWEEP) {
      break;
    }
    // Stub -> .tree-children -> the .tree-folder row that owns the path.
    const folder = /** @type {HTMLElement | null} */ (
      stubs[index].parentElement?.previousElementSibling ?? null
    );
    const path = folder?.dataset?.path;
    // A folder in a Group by section warms that group's subtree.
    const group = treeSectionKey(folder);
    const key = path ? subtreeCacheKey(path, group) : "";
    if (!path || subtreeCache.has(key) || subtreeRequests.has(key)) {
      continue;
    }
    if (view && !isNearNavViewport(folder, view, lookahead)) {
      continue;
    }
    paths.push({ path, group });
  }
  return paths;
}

/**
 * Is this row on screen in the nav, or within `lookahead` pixels of it?
 *
 * Two ways to be off screen, and only one of them is scrolling. A collapsed
 * branch clips its children with `overflow: hidden` rather than removing them,
 * so those rows keep full-height boxes stacked at the branch's own position —
 * a rect test alone reads them as visible and on screen. The branch is checked
 * first for that reason.
 *
 * @param {HTMLElement | null} row
 * @param {DOMRect} view
 * @param {number} lookahead
 * @returns {boolean}
 */
function isNearNavViewport(row, view, lookahead) {
  if (!row || row.closest(".tree-children-collapsed")) {
    return false;
  }
  const rect = row.getBoundingClientRect();
  if (rect.height === 0) {
    return false;
  }
  return rect.bottom >= view.top - lookahead && rect.top <= view.bottom + lookahead;
}

async function prefetchPendingSubtrees() {
  const paths = pendingSubtreePaths();
  let next = 0;
  const worker = async () => {
    while (next < paths.length) {
      const { path, group } = paths[next];
      next += 1;
      try {
        await fetchSubtree(path, group);
      } catch (_error) {
        // Best-effort: a failed warm-up costs nothing, and the expansion
        // that needs this folder reports its own failure.
      }
    }
  };
  const lanes = Math.min(SUBTREE_PREFETCH_MAX_CONCURRENT, paths.length);
  await Promise.all(Array.from({ length: lanes }, worker));
}

/**
 * Arm one sweep, if one is not already armed.
 *
 * @param {{ afterExpand?: boolean }} [options] `afterExpand` marks a sweep a
 *   reader asked for by opening a folder, which runs on a short timer rather
 *   than waiting for idle.
 */
function scheduleSubtreePrefetch(options) {
  if (subtreePrefetchScheduled) {
    return;
  }
  subtreePrefetchScheduled = true;
  const run = () => {
    subtreePrefetchScheduled = false;
    void prefetchPendingSubtrees();
  };
  if (options?.afterExpand) {
    setTimeout(run, SUBTREE_PREFETCH_AFTER_EXPAND_MS);
    return;
  }
  window.metabrowser.whenIdle(run, { timeout: SUBTREE_PREFETCH_IDLE_TIMEOUT_MS });
}

// Scrolling is what makes a folder next, so it is what re-arms the sweep. The
// scheduled flag and the idle callback already collapse a burst of scroll
// events into one pass, so this needs no debounce of its own.
document.getElementById("tree-content")?.addEventListener(
  "scroll",
  () => {
    // Wrapped rather than passed directly: a listener receives the event, and
    // an Event is not this function's options object.
    scheduleSubtreePrefetch();
  },
  { passive: true },
);

// ── Custom tooltip ──────────────────────────────────────────────
//
// Single floating element shared across the whole SPA — file tree,
// viz graph, drawer chips, anywhere we want a hover surface richer
// than the browser's native `title` attribute. Exposed on
// `window.MetabrowserTooltip` so viz.js can pass Identity HTML through
// the same pipeline (one delay, one fade, one stylesheet, one DOM
// node to inspect when styling or debugging).

var tooltipEl = null;
var tooltipTimer = null;
// The element the visible tooltip belongs to. It is what makes a tooltip hold
// still: position is read from this once, when the tooltip appears, and never
// again while it is up.
var tooltipAnchor = null;

var TOOLTIP_ANCHOR_GAP = 6;
var TOOLTIP_VIEWPORT_MARGIN = 8;
var TOOLTIP_APPEAR_DELAY = 300;
var TOOLTIP_FADE_OUT = 150;

function initTooltip() {
  tooltipEl = document.createElement("div");
  tooltipEl.className = "custom-tooltip";
  document.body.appendChild(tooltipEl);
}

/**
 * Show `html` anchored to `anchor`, the element the tooltip describes.
 *
 * Calling again with the same anchor is how a surface says "still here" — it
 * cancels a pending hide and leaves the tooltip exactly where it is. That is
 * what lets a delegated listener fire on every descendant the pointer crosses
 * without the tooltip flickering or drifting.
 */
function showTooltip(html, anchor) {
  var element = anchor && anchor.nodeType === 1 ? anchor : null;
  if (element && element === tooltipAnchor && tooltipEl.style.display === "block") {
    clearTimeout(tooltipTimer);
    tooltipEl.classList.add("visible");
    return;
  }
  tooltipAnchor = element;
  clearTimeout(tooltipTimer);
  // Small delay before appearing so tooltips don't flash when moving across items
  tooltipTimer = setTimeout(() => {
    // Replaced during the delay, as a tree row is when its folder re-renders. A
    // detached element's rect is all zeros, which would put the tooltip at the
    // top-left corner, and it will never fire the mouseleave that takes it away.
    if (element && !element.isConnected) {
      hideTooltip();
      return;
    }
    tooltipEl.innerHTML = html;
    tooltipEl.style.display = "block";
    positionTooltip(element);
    // Trigger fade-in on next frame
    requestAnimationFrame(() => {
      tooltipEl.classList.add("visible");
    });
  }, TOOLTIP_APPEAR_DELAY);
}

/**
 * Place the tooltip under its anchor, centered on it, flipping above when
 * there is no room below and clamping to the viewport either way.
 *
 * Anchored to the element rather than the pointer, and read once rather than
 * on every mousemove: a tooltip that tracks the cursor jitters, and one placed
 * where the pointer happened to enter tells the reader nothing about which
 * thing it describes.
 */
function positionTooltip(anchor) {
  if (!anchor?.getBoundingClientRect) {
    return;
  }
  var target = anchor.getBoundingClientRect();
  var rect = tooltipEl.getBoundingClientRect();
  var maxX = window.innerWidth - rect.width - TOOLTIP_VIEWPORT_MARGIN;
  var x = target.left + (target.width - rect.width) / 2;
  var y = target.bottom + TOOLTIP_ANCHOR_GAP;
  if (y + rect.height > window.innerHeight - TOOLTIP_VIEWPORT_MARGIN) {
    y = target.top - rect.height - TOOLTIP_ANCHOR_GAP;
  }
  tooltipEl.style.left = `${Math.max(TOOLTIP_VIEWPORT_MARGIN, Math.min(x, Math.max(TOOLTIP_VIEWPORT_MARGIN, maxX)))}px`;
  tooltipEl.style.top = `${Math.max(TOOLTIP_VIEWPORT_MARGIN, y)}px`;
}

function hideTooltip() {
  clearTimeout(tooltipTimer);
  tooltipEl.classList.remove("visible");
  // The anchor survives the fade on purpose: a surface that re-announces the
  // same element mid-fade gets its tooltip back rather than a fresh delay.
  tooltipTimer = setTimeout(() => {
    tooltipEl.style.display = "none";
    tooltipAnchor = null;
  }, TOOLTIP_FADE_OUT);
}

/**
 * Put the tooltip away only when its anchor is `within` or inside it, whether the tooltip
 * is up or still waiting out its delay. A surface that repaints or is disposed clears its
 * own tooltip this way and leaves another surface's: the page has one tooltip, so a
 * surface that hid every tooltip on each draw would take another's from under a pointer
 * that has not moved (mb-alff, docs/design-system.md, "A Surface Puts Away Only Its Own
 * Tooltip"). A tooltip whose anchor has left the document belongs to no surface on the
 * page, and would never hear the mouseleave that ends it, so any surface's call puts it
 * away, even one made after that surface removed its markup.
 *
 * @param {Element} within
 */
function hideTooltipWithin(within) {
  if (tooltipAnchor && (!tooltipAnchor.isConnected || within.contains(tooltipAnchor))) {
    hideTooltip();
  }
}

// The element focus was last given to, which tells focus put back from focus moved.
/** @type {Node | null} */
var tooltipFocusOwner = null;

/**
 * Focus moving puts a pointer's tooltip away (docs/design-system.md, "Tooltip Input
 * Modality"). A rebuild can replace a focused control and focus its
 *   replacement, as the Files filter bar's does when new tallies arrive. The element that
 *   had focus is out of the document by then, so a focus that follows one that left the
 *   document, with no key or press of the reader's since (endTooltipFocusRepair), is that
 *   repair (mb-alff). A tooltip whose own anchor the rebuild removed still goes: it would
 *   never hear the mouseleave that ends it.
 *
 * @param {FocusEvent} event
 */
function hideTooltipOnFocus(event) {
  var previous = tooltipFocusOwner;
  tooltipFocusOwner = /** @type {Node | null} */ (event.target);
  if (previous && previous.isConnected === false) {
    if (tooltipAnchor && !tooltipAnchor.isConnected) {
      hideTooltip();
    }
    return;
  }
  hideTooltip();
}

/**
 * The reader's own key or press ends a pending repair. A rebuild that removes the focused
 * element and focuses nothing, as pressing the Files filter bar's Clear does, leaves focus
 * on the page with no `focusin`, so the owner stays out of the document until the next
 * focus, and that focus, the reader's Tab or click, would pass for the repair and leave
 * the pointer's tooltip up beside the focus ring. A rebuild the reader's key causes still
 * counts as one, since its `keydown` comes before the removal. Letting the owner go also
 * lets the removed subtree it holds be collected.
 */
function endTooltipFocusRepair() {
  if (tooltipFocusOwner && !tooltipFocusOwner.isConnected) {
    tooltipFocusOwner = null;
  }
}

if (typeof window !== "undefined") {
  window.MetabrowserTooltip = {
    show: (html, anchor) => {
      showTooltip(html, anchor);
    },
    // With an element, only a tooltip anchored in it (hideTooltipWithin). With none, what a
    // pointer leaving a surface means: whatever tooltip there is, but the nav's header's.
    // The header is the shell's chrome, which no view draws, so its tooltips are never one
    // a view showed, and a view's bare hide leaves them: Home redraws the folder overview
    // and the Commits panel, whose hides took the folder's name's tooltip away under a click
    // (docs/design-system.md, "Home"). Anything but an element, such as the document or the
    // event when `hide` is itself a listener, is none.
    hide: (within) => {
      if (within instanceof Element) {
        hideTooltipWithin(within);
        return;
      }
      if (tooltipAnchor?.closest?.(".app-header")) {
        return;
      }
      hideTooltip();
    },
  };
}

/**
 * The plain-text half of the one tooltip: anything carrying `data-tip-text`
 * gets the app's tooltip, and nothing in the app uses the browser's own.
 *
 * A native `title` is a second tooltip system running beside this one. It
 * cannot be styled or placed, it appears on the platform's timer rather than
 * ours, and on a surface that already announces a tooltip it shows a second
 * one alongside — which is the bug that produced this rule. `data-tip-text`
 * exists so that having something to say is never a reason to reach for
 * `title`: the common case is a short string, and it should be one attribute.
 *
 * `aria-label` is untouched and still required where it was. It is the
 * accessible name, not a tooltip; a screen reader never reads this attribute,
 * so a glyph-only control needs both.
 *
 * Delegated from the document, so it covers markup that does not exist yet,
 * including a plugin's. Tooltips are pointer-only supplementary detail;
 * keyboard focus uses the element's accessible name and dismisses any tooltip
 * left under a stationary pointer.
 *
 * Unlike the action delegates it is not owner-marked (see `ownedControlAttr`):
 * it runs nothing, and plugins write plain `data-tip-text`. It does ignore a
 * rendered document's own markup, which a trusted folder's Markdown keeps, so a
 * document cannot label itself in the application's tooltip layer. A control page
 * code placed in the document and marked with `mb.ownDelegate`, as the document's print
 * button is (builtin_plugins/markdown/print-indicator.js), keeps its tooltip, and so does
 * an image's fallback chip (inert_html.py).
 */
function tipTextAnchor(event) {
  var anchor = eventTargetElement(event)?.closest("[data-tip-text]");
  return anchor instanceof HTMLElement &&
    (!anchor.closest(".metabrowser-kpress-host") ||
      isPageElement(anchor) ||
      anchor.classList.contains("mb-image-fallback"))
    ? anchor
    : null;
}

/**
 * A tip's text as compared with what its anchor shows: one space for every run of white
 * space, no case.
 *
 * @param {string | null | undefined} text
 */
function tipComparable(text) {
  return String(text || "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

/**
 * Whether *anchor* or a box in it is cut short, by an ellipsis or a line clamp. An inline
 * box has no client box to overflow, so only boxes that have one are read.
 *
 * @param {HTMLElement} anchor
 */
function tipAnchorIsCut(anchor) {
  // Ref names ellipsize horizontally. Font ink can extend below the compact line.
  const label = anchor.querySelector(":scope.git-ref > .git-ref-label");
  if (label) {
    return label.scrollWidth > label.clientWidth;
  }
  var boxes = [anchor, ...anchor.querySelectorAll("*")];
  return boxes.some(
    (box) =>
      box instanceof HTMLElement &&
      ((box.clientWidth > 0 && box.scrollWidth > box.clientWidth) ||
        (box.clientHeight > 0 && box.scrollHeight > box.clientHeight)),
  );
}

/**
 * Whether a tip says something its anchor does not already show (docs/design-system.md,
 * "Tooltips Add Information"). A tip that is the anchor's own text says nothing while
 * that text is whole, so it shows only while the text is cut short. So does a tip that is
 * the text of a box inside the anchor, as a changed file's row holds its name beside its
 * status letter and counts: it shows only while that box is cut short. Any other tip, such
 * as a glyph's name or an exact time, shows.
 *
 * @param {HTMLElement} anchor
 */
function tipAddsInformation(anchor) {
  var tip = tipComparable(anchor.dataset.tipText);
  if (tip === "") {
    return false;
  }
  var text = tipComparable(anchor.textContent);
  if (tip === text) {
    return tipAnchorIsCut(anchor);
  }
  // A box's text is part of its anchor's, so a tip the anchor's text does not hold is no
  // box's text, and nothing inside need be read.
  if (!text.includes(tip)) {
    return true;
  }
  var repeated = false;
  for (var box of anchor.querySelectorAll("*")) {
    if (box instanceof HTMLElement && tipComparable(box.textContent) === tip) {
      if (tipAnchorIsCut(box)) {
        return true;
      }
      repeated = true;
    }
  }
  return !repeated;
}

/** @param {Event} e */
function showTipText(e) {
  var anchor = tipTextAnchor(e);
  if (anchor && tipAddsInformation(anchor)) {
    showTooltip(esc(anchor.dataset.tipText || ""), anchor);
  }
}

/** @param {Event} e */
function hideTipText(e) {
  if (tipTextAnchor(e)) {
    hideTooltip();
  }
}

// mouseenter/mouseleave do not bubble, so these listen in the capture phase.
// Any focus transition ends pointer-owned tooltip presentation without
// creating a second visual layer around keyboard navigation. A rebuild can repair focus.
document.addEventListener("mouseenter", showTipText, true);
document.addEventListener("mouseleave", hideTipText, true);
document.addEventListener("focusin", hideTooltipOnFocus);
// The reader's key or press, in the capture phase so that it comes before any focus it
// gives, ends a focus repair (endTooltipFocusRepair).
document.addEventListener("keydown", endTooltipFocusRepair, true);
document.addEventListener("pointerdown", endTooltipFocusRepair, true);
// Tooltip size/count rows reuse the shared .size / .count classes so
// they match the hue of the same data everywhere else (tree column,
// file header, app header). Tooltip still uses formatExactSize()
// (exact bytes) for the precise-value read hovering implies; the
// visual category (this number is a size) is carried by the class.
function _tipSize(bytes) {
  if (bytes === undefined) {
    return "";
  }
  if (isPendingNumber(bytes)) {
    return '<span class="tally-pending" role="status" aria-label="Loading size"></span>';
  }
  var cls = `size ${sizeClass(bytes)}`.trim();
  return `<span class="${cls}">${formatExactSize(bytes || 0)}</span>`;
}
function _tipCount(n) {
  if (n === undefined) {
    return "";
  }
  if (isPendingNumber(n)) {
    return (
      '<span class="tally-pending tally-pending-narrow" role="status"' +
      ' aria-label="Loading file count"></span>'
    );
  }
  return `<span class="count">${formatCount(n)}</span>`;
}

function treeTooltipNameHtml(name, includeName) {
  return includeName === false ? "" : `<div class="tip-name">${esc(name)}</div>`;
}

function fileTooltipHtml(name, size, mtime, includeName) {
  var stamped = formatTimestamp(mtime);
  return (
    treeTooltipNameHtml(name, includeName) +
    (size === undefined ? "" : `<div class="tip-detail">${_tipSize(size)}</div>`) +
    (stamped ? `<div class="tip-detail">${stamped}</div>` : "")
  );
}

function symlinkTooltipHtml(name, mtime, includeName) {
  return (
    treeTooltipNameHtml(name, includeName) +
    '<div class="tip-detail">Symbolic link</div>' +
    '<div class="tip-detail">' +
    formatTimestamp(mtime) +
    "</div>"
  );
}

function folderTooltipHtml(name, totalFiles, totalSize, mtime, includeName) {
  var stamped = formatTimestamp(mtime);
  return (
    treeTooltipNameHtml(name, includeName) +
    (totalFiles === undefined ? "" : `<div class="tip-detail">${_tipCount(totalFiles)}</div>`) +
    (totalSize === undefined ? "" : `<div class="tip-detail">${_tipSize(totalSize)}</div>`) +
    (stamped ? `<div class="tip-detail">${stamped}</div>` : "")
  );
}

// ── Tree interactions ───────────────────────────────────────────

const treePane = /** @type {HTMLElement} */ (document.getElementById("tree-pane"));
if (!treePane) {
  throw new Error("Metabrowser shell is missing #tree-pane");
}

// Coalesce roving-focus/ARIA repair into one painted-tree walk per task.
// Snapshot/event bursts must not walk once per entry. Keep the earliest pending
// focus snapshot: it captures the anchor lineage before the first mutation.
var _treeSynchronizeHandle = null;
/** @type {ReturnType<NonNullable<typeof treeKeyboard>["prepareForMutation"]> | null} */
var _treeSynchronizeMutation = null;

/** @param {ReturnType<NonNullable<typeof treeKeyboard>["prepareForMutation"]> | null} [mutationSnapshot] */
function scheduleTreeSynchronize(mutationSnapshot) {
  if (!treeKeyboard) {
    return;
  }
  if (mutationSnapshot && !_treeSynchronizeMutation) {
    _treeSynchronizeMutation = mutationSnapshot;
  }
  if (_treeSynchronizeHandle !== null) {
    return;
  }
  _treeSynchronizeHandle = setTimeout(() => {
    _treeSynchronizeHandle = null;
    var snapshot = _treeSynchronizeMutation;
    _treeSynchronizeMutation = null;
    treeKeyboard?.synchronize(snapshot || undefined);
  }, 0);
}

// A user action repairs focus in its own turn, so it must not land behind a
// queued burst repair — and running both would walk the tree twice.
function synchronizeTreeNow() {
  if (_treeSynchronizeHandle !== null) {
    clearTimeout(_treeSynchronizeHandle);
    _treeSynchronizeHandle = null;
  }
  var snapshot = _treeSynchronizeMutation;
  _treeSynchronizeMutation = null;
  treeKeyboard?.synchronize(snapshot || undefined);
}

treePane.addEventListener(
  "mouseenter",
  (e) => {
    var target = eventTargetElement(e);
    var item = /** @type {HTMLElement | null} */ (target?.closest(".tree-item"));
    if (!item?.dataset.tipType) {
      return;
    }
    var d = item.dataset;
    // The tooltip gives what the row does not show (docs/design-system.md,
    // "Tooltips Add Information"): the exact date, a folder's other total, and
    // the exact size behind one its chip rounds. The row shows the name, and a
    // size or file count, whichever its chip holds, so the tooltip leaves out the
    // name and what the chip shows exactly: a count, and a size under 1,024
    // bytes, which formatBytes writes in whole bytes ("512 B").
    var includeName = false;
    var chip = item.querySelector(".tree-item-size");
    var shows = chip === null ? null : chip.classList.contains("count") ? "count" : "size";
    var size = parseTipNumber(d.tipSize);
    var chipRoundsSize = typeof size === "number" && size >= 1024;
    var tipSize = shows === "size" && !chipRoundsSize ? undefined : size;
    var html;
    if (d.tipType === "dir") {
      html = folderTooltipHtml(
        d.tipName,
        shows === "count" ? undefined : parseTipNumber(d.tipFiles),
        tipSize,
        parseTipNumber(d.tipMtime),
        includeName,
      );
    } else if (d.tipType === "symlink") {
      html = symlinkTooltipHtml(d.tipName, parseTipNumber(d.tipMtime), includeName);
    } else {
      html = fileTooltipHtml(d.tipName, tipSize, parseTipNumber(d.tipMtime), includeName);
    }
    if (html) {
      showTooltip(html, item);
    }
  },
  true,
);

treePane.addEventListener(
  "mouseleave",
  (e) => {
    var target = eventTargetElement(e);
    var item = target?.closest(".tree-item");
    if (item) {
      hideTooltip();
    }
  },
  true,
);

var hoverPrefetchTimer = null;
var hoverPrefetchPath = "";
var hoverPrefetchController = null;
var hoverPrefetchPromise = null;
var hoverPrefetchInFlight = 0;

async function settleHoverPrefetchForSelection(path) {
  clearTimeout(hoverPrefetchTimer);
  hoverPrefetchTimer = null;
  if (hoverPrefetchPath !== path) {
    abortHoverPrefetch();
    return;
  }
  if (hoverPrefetchPromise) {
    await hoverPrefetchPromise;
    return;
  }
  hoverPrefetchPath = "";
  hoverPrefetchController = null;
}

function shouldPrefetchFile(item) {
  var path = item.dataset.path;
  if (!path || fileCache.has(path) || activeFiles.has(path)) {
    return false;
  }
  if (+(item.dataset.tipSize || 0) > FILE_PREFETCH_MAX_BYTES) {
    return false;
  }
  // No name ending `.jsonl` is prefetched: /api/file parses such a file whole
  // into events instead of answering a bounded text window. `data-logical-ext`
  // is the inner extension of a .gz; `data-ext` is a compound tail
  // (`.codex.jsonl`), and all a pin's wire path has, so match its end.
  var ext = (item.dataset.logicalExt || item.dataset.ext || getExt(path)).toLowerCase();
  return !ext.endsWith(".jsonl");
}

function abortHoverPrefetch() {
  clearTimeout(hoverPrefetchTimer);
  hoverPrefetchTimer = null;
  hoverPrefetchPath = "";
  hoverPrefetchPromise = null;
  if (hoverPrefetchController) {
    hoverPrefetchController.abort();
    hoverPrefetchController = null;
  }
}

function startHoverPrefetch(path) {
  if (!path || fileCache.has(path) || activeFiles.has(path)) {
    return;
  }
  if (hoverPrefetchInFlight >= FILE_PREFETCH_MAX_CONCURRENT) {
    return;
  }

  hoverPrefetchInFlight += 1;
  hoverPrefetchController = typeof AbortController !== "undefined" ? new AbortController() : null;
  var options = hoverPrefetchController ? { signal: hoverPrefetchController.signal } : {};
  const request = fetch(`/api/file?path=${encodeURIComponent(path)}`, options)
    .then((resp) =>
      resp.ok
        ? _perf.measureAsync(
            "apiFile:prefetchJson",
            () => resp.json(),
            responsePerfMeta(resp, path),
          )
        : null,
    )
    .then((data) => {
      if (data && !fileCache.has(path)) {
        cachePut(fileCache, path, data, CACHE_MAX, evictFileCacheMetadata);
      }
    })
    .catch(() => {
      /* best-effort prefetch */
    })
    .finally(() => {
      hoverPrefetchInFlight -= 1;
      if (hoverPrefetchPath === path && hoverPrefetchPromise === request) {
        hoverPrefetchController = null;
        hoverPrefetchPath = "";
        hoverPrefetchPromise = null;
      }
    });
  hoverPrefetchPromise = request;
}

// Prefetch small, non-log file content only after hover intent is clear. Large
// files and JSONL logs can be expensive to parse, so they wait for an explicit click.
treePane.addEventListener(
  "mouseenter",
  (e) => {
    var target = eventTargetElement(e);
    var item = /** @type {HTMLElement | null} */ (target?.closest(".tree-item.tree-file"));
    if (!item) {
      return;
    }
    if (!shouldPrefetchFile(item)) {
      return;
    }
    var path = item.dataset.path;
    if (!path) {
      return;
    }
    abortHoverPrefetch();
    hoverPrefetchPath = path;
    hoverPrefetchTimer = setTimeout(() => {
      startHoverPrefetch(hoverPrefetchPath);
    }, FILE_PREFETCH_HOVER_DELAY_MS);
  },
  true,
);

treePane.addEventListener(
  "mouseleave",
  (e) => {
    var target = eventTargetElement(e);
    if (target?.closest(".tree-item.tree-file")) {
      abortHoverPrefetch();
    }
  },
  true,
);

async function expandAllDescendants(container) {
  var childItems = container.children;
  for (var i = 0; i < childItems.length; i++) {
    var folder = childItems[i];
    if (!folder.classList?.contains("tree-folder")) {
      continue;
    }
    var ch = folder.nextElementSibling;
    if (!ch?.classList.contains("tree-children")) {
      continue;
    }
    await setFolderExpanded(folder, true, { synchronize: false });
    await expandAllDescendants(ch);
  }
}

function collapseAllDescendants(container) {
  container.querySelectorAll(".tree-children").forEach((ch) => {
    var folder = ch.previousElementSibling;
    if (folder?.classList.contains("tree-folder")) {
      setFolderExpanded(folder, false, { synchronize: false });
    }
  });
}

function setFolderExpanded(row, expanded, options) {
  options = options || {};
  var children = /** @type {HTMLElement | null} */ (row.nextElementSibling);
  if (
    !row.classList.contains("tree-folder") ||
    row.classList.contains("tree-item-empty") ||
    !children?.classList.contains("tree-children")
  ) {
    return;
  }
  window.MetabrowserTreeExpansion.setFolderExpanded(row, children, expanded, !!options.instant);
  row.setAttribute("aria-expanded", String(expanded));
  if (options.synchronize !== false) {
    synchronizeTreeNow();
  }
  if (expanded) {
    // Opening a folder is what puts its children on screen, so it is the other
    // thing that makes a stub a candidate. Without this the viewport bound
    // would warm nothing after the first screen: the newly revealed rows are
    // visible, but nothing had re-armed the sweep to notice.
    scheduleSubtreePrefetch({ afterExpand: true });
  }
  if (expanded && children.querySelector(":scope > .tree-lazy-placeholder")) {
    return loadSubtree(row.dataset.path, children).then(() => {
      if (options.synchronize !== false) {
        synchronizeTreeNow();
      }
    });
  }
}

async function toggleTreeFolder(row, options) {
  options = options || {};
  var expanded = row.getAttribute("aria-expanded") === "true";
  var children = /** @type {HTMLElement | null} */ (row.nextElementSibling);
  if (!children?.classList.contains("tree-children")) {
    return row;
  }
  // Recursive walks defer every per-folder repair to the single synchronize
  // below. Expand and collapse pay the same price: one walk of the visible
  // tree for the whole operation, not one per descendant folder.
  if (options.recursive && expanded) {
    collapseAllDescendants(children);
    setFolderExpanded(row, false, { synchronize: false });
  } else if (options.recursive) {
    await setFolderExpanded(row, true, { synchronize: false });
    await expandAllDescendants(children);
  } else {
    await setFolderExpanded(row, !expanded);
  }
  synchronizeTreeNow();
  return row;
}

// Container expansion mirrors lazy folder expansion: fetch children on
// first open, then toggle visibility. Failures state themselves in the
// group rather than leaving an empty box.
// A container's children follow its file, as a database's tables do (file-watches.js,
// followContainer): a change reads them again, coalesced, or on the next expand.
var containerHtml = new WeakMap();
function watchContainer(row, children) {
  if (!isGitRevisionSource()) {
    void window.MetabrowserAssets?.ensureAsset("file-watches").then(() =>
      window.MetabrowserFileWatches?.followContainer(row, children, loadContainerChildren),
    );
  }
}

async function loadContainerChildren(row, children) {
  // A refresh keeps the children drawn until their replacement arrives.
  children.innerHTML ||=
    '<div class="tree-lazy-placeholder mb-delayed-loading" role="status" aria-label="Loading">' +
    '<span class="spinner spinner-sm" aria-hidden="true"></span></div>';
  var level = Number(row.dataset.treeLevel || "1") + 1;
  var childrenStartedAt = Date.now();
  var html;
  try {
    var payload = await window.metabrowser.fetchPluginData(
      row.dataset.containerPlugin,
      row.dataset.containerChildren,
      { path: row.dataset.path || "" },
    );
    var rows = Array.isArray(payload?.children) ? payload.children : [];
    html = rows.length
      ? renderContainerChildren(rows, { level: level })
      : '<div class="tree-empty-note">No entries in this file.</div>';
    children.dataset.loaded = "1";
    watchContainer(row, children);
  } catch (error) {
    console.error(
      "metabrowser tree: container children failed",
      {
        path: row.dataset.path,
        plugin: row.dataset.containerPlugin,
        hook: row.dataset.containerChildren,
        elapsedMs: Date.now() - childrenStartedAt,
      },
      error,
    );
    html = '<div class="tree-empty-note nav-error">Could not load these entries.</div>';
  }
  // Drawn again only when they differ, so a refresh keeps a child's focus and hover.
  if (containerHtml.get(children) !== html) {
    containerHtml.set(children, html);
    children.innerHTML = html;
    applyTreeFilters();
    synchronizeTreeNow();
  }
}

async function toggleTreeContainer(row) {
  var children = /** @type {HTMLElement | null} */ (row.nextElementSibling);
  if (!children?.classList.contains("tree-children")) {
    return row;
  }
  var expanded = row.getAttribute("aria-expanded") === "true";
  if (expanded) {
    row.setAttribute("aria-expanded", "false");
    row.classList.add("collapsed");
    row.classList.remove("expanded");
    children.classList.add("tree-children-collapsed");
    synchronizeTreeNow();
    return row;
  }
  row.setAttribute("aria-expanded", "true");
  row.classList.add("expanded");
  row.classList.remove("collapsed");
  children.classList.remove("tree-children-collapsed");
  if (!children.dataset.loaded) {
    await loadContainerChildren(row, children);
  }
  synchronizeTreeNow();
  return row;
}

// The keyboard's one disclosure entry point. Folders and container
// files both expand through it, each by its own path, so the navigation
// module never asks what kind of row it is holding.
function setRowExpanded(row, expanded) {
  if (!row.dataset.containerChildren) {
    return setFolderExpanded(row, expanded);
  }
  if (row.getAttribute("aria-expanded") === String(expanded)) {
    return undefined;
  }
  return toggleTreeContainer(row);
}

// A "more" row's page arrives where the row was and grows down from there, and the row
// that takes focus is the first it drew: a reader reading down reads on into it. A
// reveal can leave "more" rows with rows after them (mountTreePageAt). When the selected
// row, the reader's, is among those, the page grows up instead: the rows after it stay
// where they are on screen, so the reader's row is not pushed out of view, and the row
// that takes focus is the one nearest them.
function mountNextTreePage(row) {
  var pageId = row.dataset.pageId;
  var page = pendingTreePages.get(pageId);
  var nextBatch = page?.nodes;
  if (!nextBatch?.length) {
    return null;
  }
  treeKeyboard?.prepareForMutation();
  pendingTreePages.delete(pageId);
  var follower = /** @type {HTMLElement | null} */ (row.nextElementSibling);
  if (follower && !selectedTreeRowFollows(row)) {
    follower = null;
  }
  var scroller = document.getElementById("tree-content");
  var followerTop = follower && scroller ? follower.getBoundingClientRect().top : null;
  var temporary = document.createElement("div");
  temporary.innerHTML = withTreeIdScope(page.options.section || "", () =>
    renderTreeNodes(nextBatch, false, page.options),
  );
  var nodes = Array.prototype.slice.call(temporary.childNodes);
  var firstMounted = null;
  var lastMounted = null;
  for (var i = 0; i < nodes.length; i++) {
    var node = nodes[i];
    row.parentElement?.insertBefore(node, row);
    if (node.getAttribute?.("role") === "treeitem") {
      firstMounted ??= node;
      lastMounted = node;
    }
  }
  row.remove();
  // A deferred page arrives without current filter decoration.
  applyTreeFilters();
  reconcilePendingTallyDiagnostics();
  synchronizeTreeNow();
  if (follower && scroller && followerTop !== null) {
    scroller.scrollTop += follower.getBoundingClientRect().top - followerTop;
  }
  return follower ? lastMounted : firstMounted;
}

/**
 * Whether the selected row of *row*'s tree comes after it: the reader's row is below it.
 * Only its own tree's: the same file is selected in each tree that draws it.
 *
 * @param {HTMLElement} row
 * @returns {boolean}
 */
function selectedTreeRowFollows(row) {
  // Node.DOCUMENT_POSITION_FOLLOWING, spelled out so this needs no Node global.
  var FOLLOWING = 4;
  var tree = row.closest('[role="tree"]') ?? undefined;
  for (const selected of queryHtmlAll(".tree-item.selected", tree)) {
    if ((row.compareDocumentPosition(selected) & FOLLOWING) !== 0) {
      return true;
    }
  }
  return false;
}

// The pointer activation contract. A folder row is a single target: it selects
// the folder, opens its default Overview view, and toggles its immediate
// children, so the chevron stays a state indicator rather than a second action
// with its own navigation semantics.
//
// The keyboard splits what a click fuses, because arrows already carry the
// opening half: see openTreeRow and activateTreeRowFromKeyboard below.
async function activateTreeRow(row, options) {
  var action = row.dataset.action;
  if (action === "select-dir") {
    // Guarded like the select branch below: a pathless row would otherwise
    // clear the whole selection and request the served root.
    if (row.dataset.path) {
      setSelectedPath(row.dataset.path);
      // Trailing slash marks a folder in the canonical /view/ route.
      void navigateToPath(`${row.dataset.path}/`);
    }
    return toggleTreeFolder(row, options);
  }
  if (action === "page-more") {
    return mountNextTreePage(row);
  }
  if (action === "select" && row.dataset.path) {
    setSelectedPath(row.dataset.path);
    void navigateToPath(row.dataset.path);
    // A container file is one target like a folder row: opening it also
    // discloses what is inside it.
    if (row.dataset.containerChildren) {
      return toggleTreeContainer(row);
    }
  }
  return row;
}

// Arrow keys are the browse gesture: landing on a row opens it, so skimming
// costs one keypress per row instead of two. Reading is the common case and
// waiting for a confirm keystroke saved nothing once opening became fast.
//
// The route is replaced rather than pushed, so a skim does not bury the
// reader's entry point under one history entry per row they passed.
function openTreeRow(row) {
  var path = row.dataset.path;
  if (!path) {
    // Pagination rows carry no path; they are activated, never opened.
    return;
  }
  setSelectedPath(path);
  var folder = row.dataset.action === "select-dir";
  void navigateToPath(folder ? `${path}/` : path, undefined, { replace: true });
}

// Enter and Space are action keys in the tree, not view keys. Whatever the
// focus is on is already open, so activation is only for what arrows cannot
// express: changing a folder's disclosure state and mounting a deferred page.
async function activateTreeRowFromKeyboard(row, options) {
  var action = row.dataset.action;
  if (action === "select-dir") {
    return toggleTreeFolder(row, options);
  }
  if (action === "page-more") {
    return mountNextTreePage(row);
  }
  if (row.dataset.containerChildren) {
    return toggleTreeContainer(row);
  }
  return row;
}

treePane.addEventListener("click", (e) => {
  var target = eventTargetElement(e);
  if (!target) {
    return;
  }
  const item = /** @type {HTMLElement | null} */ (target.closest(".tree-item"));
  if (!item) {
    return;
  }
  treeKeyboard?.setAnchor(item);
  void activateTreeRow(item, { recursive: e.shiftKey }).then((focusTarget) => {
    if (focusTarget?.isConnected) {
      treeKeyboard?.setAnchor(focusTarget, item.dataset.action === "page-more");
    }
  });
});

// Mark every .tree-item whose data-path matches *path* as
// selected across panels. The same file can be rendered
// in both the Files tree and the Recent tree; the highlight
// should follow the user when they switch tabs. ``null`` /
// ``undefined`` clears all selection state.
function setSelectedPath(path) {
  queryHtmlAll(".tree-item.selected").forEach((el) => {
    if (el.dataset.path !== path) {
      el.classList.remove("selected");
    }
  });
  if (!path) {
    treeKeyboard?.setSelectedPath(null);
    renderSelectionOutsideFilterNote(null);
    return;
  }
  queryHtmlAll(".tree-item").forEach((el) => {
    if (el.dataset.path === path) {
      el.classList.add("selected");
    }
  });
  treeKeyboard?.setSelectedPath(path);
  // The path explicitly: this runs before navigateToPath has committed it, so
  // reading currentPath here would name the folder the reader just left.
  renderSelectionOutsideFilterNote(path);
}

// A filter can exclude the folder the reader is standing in — open one from a
// breadcrumb, a link, or a pasted URL and the tree legitimately has no row for
// it. Say so, naming it, rather than leaving the panel silently unselected.
//
// Deliberately not a pinned row. Keeping the selection in the tree means
// refetching as the reader navigates, and a refetch repaints the panel, which
// collapses every folder they had open — the same cost this change already
// refused to pay for filesystem bursts. A line costs nothing and answers the
// question the empty selection actually raises.
function renderSelectionOutsideFilterNote(selectedPath) {
  var panel = document.getElementById("tab-files");
  if (!panel) {
    return;
  }
  var path = selectedPath === undefined ? currentPath : selectedPath;
  var existing = document.querySelector(".tree-selection-note");
  var filtered = filterState ? filterHasConstraints(filterState.get()) : false;
  var absent = filtered && !!path && treeOmitsPath(panel, path);
  if (!absent) {
    existing?.remove();
    return;
  }
  var text = `${path} is outside this filter.`;
  if (existing) {
    existing.textContent = text;
    return;
  }
  var note = document.createElement("div");
  note.className = "tree-selection-note nav-metadata nav-metadata-note";
  note.setAttribute("role", "status");
  note.textContent = text;
  addFilesRemark(note);
}

/**
 * Add a remark to the Files metadata band, under the totals and the filter's remark.
 *
 * @param {HTMLElement} note
 */
function addFilesRemark(note) {
  var anchor =
    document.querySelector(".tree-summary-filtered") || document.querySelector(".tree-summary");
  if (anchor) {
    anchor.insertAdjacentElement("afterend", note);
  } else {
    filesMetadataBand()?.insertAdjacentElement("afterbegin", note);
  }
}

/**
 * Whether the tree in *panel* leaves *path* out, rather than holding it somewhere the
 * reader has not opened. A folder the filter keeps but the reader closed, or whose rows
 * are not read yet, may still hold it, and a page of a long folder not yet drawn may; then
 * the tree cannot say. A folder above it that has no row at all is one the filter left out.
 *
 * @param {HTMLElement} panel
 * @param {string} path
 */
function treeOmitsPath(panel, path) {
  if (panel.querySelector(`.tree-item[data-path="${escapePathForSelector(path)}"]`)) {
    return false;
  }
  var segments = path.split("/");
  var current = "";
  for (var i = 0; i < segments.length - 1; i++) {
    current = current ? `${current}/${segments[i]}` : segments[i];
    var folders = Array.from(
      queryHtmlAll(`.tree-folder[data-path="${escapePathForSelector(current)}"]`, panel),
    );
    if (folders.length === 0) {
      return !treePageHolds(current);
    }
    for (const folder of folders) {
      var children = folder.nextElementSibling;
      if (
        !children ||
        children.classList.contains("tree-children-collapsed") ||
        children.querySelector(":scope > .tree-lazy-placeholder")
      ) {
        return false;
      }
    }
  }
  return !treePageHolds(path);
}

/** Whether a page of a long folder, not yet drawn, holds *path*'s row. @param {string} path */
function treePageHolds(path) {
  for (const page of pendingTreePages.values()) {
    if (page.nodes.some((/** @type {{path: string}} */ node) => node.path === path)) {
      return true;
    }
  }
  return false;
}

// ── Nav pane ────────────────────────────────────────────────────
//
// One Files panel, two data sources. The default source is the
// /api/tree walk. When the recency filter is set and the treatment is
// hide, the panel instead renders /api/recent's flat newest-first leaf
// list (membership and gitignore resolved server-side), clustered by
// the browser-owned tree filter model before this layer renders it.
// See ``metabrowser/recent.py`` for the layering rationale, and the
// nav filter bar section below for the switch.

// Client constants come from window.METABROWSER_SETTINGS (injected
// by the Starlette index handler). The server-side
// metabrowser.settings module is the single source of
// truth for every tunable in the browser plane; this avoids
// duplicating constants between Python and JS.
var _METABROWSER_SETTINGS = (typeof window !== "undefined" && window.METABROWSER_SETTINGS) || {};
const RECENT_LIMIT = _METABROWSER_SETTINGS.RECENT_LIMIT || 2000;
const RECENT_RECLUSTER_DEBOUNCE_MS = _METABROWSER_SETTINGS.RECENT_RECLUSTER_DEBOUNCE_MS || 100;
const RECENT_CLUSTER_PCT = _METABROWSER_SETTINGS.RECENT_CLUSTER_PCT || 0.05;
const INDEX_PROGRESS_POLL_MS = _METABROWSER_SETTINGS.INDEX_PROGRESS_POLL_MS || 1000;
const INDEX_PROGRESS_UPDATE_FILES = _METABROWSER_SETTINGS.INDEX_PROGRESS_UPDATE_FILES || 1024;
const PENDING_TALLY_DIAGNOSTIC_DELAY_MS =
  _METABROWSER_SETTINGS.PENDING_TALLY_DIAGNOSTIC_DELAY_MS || 5000;
const PENDING_TALLY_DIAGNOSTIC_SAMPLE_LIMIT =
  _METABROWSER_SETTINGS.PENDING_TALLY_DIAGNOSTIC_SAMPLE_LIMIT || 20;
var currentRecentWindow = _METABROWSER_SETTINGS.RECENT_DEFAULT_WINDOW || "24h";
var recentEverLoaded = false;

// Lightweight pull-based scan progress for the nav footer. This
// intentionally reads /api/index/progress instead of the full meta
// envelope so it never scans known entries while the index is active.
var indexProgressTimer = null;
var indexProgressInFlight = false;
var indexProgressLastRendered = null;
var indexProgressCompletionRefreshInFlight = false;
var pendingTallyDiagnosticSequence = 0;

function compactTallyEntry(entry) {
  if (!entry) {
    return null;
  }
  return {
    type: entry.type || null,
    total_files: entry.total_files === undefined ? null : entry.total_files,
    total_size: entry.total_size === undefined ? null : entry.total_size,
    size: entry.size === undefined ? null : entry.size,
    mtime: entry.mtime === undefined ? null : entry.mtime,
    mtime_ns: entry.mtime_ns === undefined ? null : entry.mtime_ns,
    newest_mtime_ns: entry.newest_mtime_ns === undefined ? null : entry.newest_mtime_ns,
    empty: entry.empty === undefined ? null : entry.empty,
    gitignored: !!entry.gitignored,
  };
}

function cachedTallyEntries(paths) {
  var wanted = new Set(paths);
  var found = new Map();
  var stack = _lastTreeRender?.tree ? Array.from(_lastTreeRender.tree) : [];
  while (stack.length > 0 && wanted.size > 0) {
    var node = stack.pop();
    if (!node) {
      continue;
    }
    if (wanted.has(node.path)) {
      found.set(node.path, compactTallyEntry(node));
      wanted.delete(node.path);
    }
    if (Array.isArray(node.children)) {
      for (var i = 0; i < node.children.length; i++) {
        stack.push(node.children[i]);
      }
    }
  }
  return found;
}

function collectPendingTallyDiagnostic(context) {
  var cells = Array.from(queryHtmlAll("#tab-files .tally-pending"));
  var fieldCounts = { age: 0, count: 0, other: 0, size: 0 };
  var rowsByPath = new Map();
  var visibleCells = 0;
  var withoutPath = 0;
  for (var i = 0; i < cells.length; i++) {
    var cell = cells[i];
    if (cell.classList.contains("size")) {
      fieldCounts.size += 1;
    } else if (cell.classList.contains("count")) {
      fieldCounts.count += 1;
    } else if (cell.classList.contains("tally-pending-narrow")) {
      fieldCounts.age += 1;
    } else {
      fieldCounts.other += 1;
    }
    var row = /** @type {HTMLElement | null} */ (cell.closest(".tree-item"));
    var hidden = !!row?.classList.contains("tree-item-filter-hidden");
    if (!hidden) {
      visibleCells += 1;
    }
    if (!row?.dataset.path) {
      withoutPath += 1;
      continue;
    }
    var path = row.dataset.path;
    if (!rowsByPath.has(path)) {
      rowsByPath.set(path, {
        path,
        hidden,
        row_type: row.classList.contains("tree-folder")
          ? "dir"
          : row.classList.contains("tree-symlink")
            ? "symlink"
            : "file",
        dom: {
          tip_files: row.dataset.tipFiles ?? null,
          tip_mtime: row.dataset.tipMtime ?? null,
          tip_size: row.dataset.tipSize ?? null,
        },
      });
    }
  }

  var allPaths = Array.from(rowsByPath.keys());
  var sampledPaths = allPaths.slice(0, PENDING_TALLY_DIAGNOSTIC_SAMPLE_LIMIT);
  var cachedEntries = cachedTallyEntries(sampledPaths);
  var samples = sampledPaths.map((path) => {
    var sample = rowsByPath.get(path);
    sample.file_store = compactTallyEntry(fileStore?.get?.(path));
    sample.cached_tree = cachedEntries.get(path) || null;
    return sample;
  });
  var filter = filterState?.get ? filterState.get() : null;
  var readyState = inventoryEventSource?.readyState;
  return {
    diagnostic_id: `pending-tally-${Date.now()}-${++pendingTallyDiagnosticSequence}`,
    kind: "pending-folder-tallies",
    captured_at: new Date().toISOString(),
    elapsed_ms: context.elapsedMs,
    episode: context.episode,
    current_path: currentPath,
    source: filesPanelUsesRecentSource() ? "recent" : "tree",
    filter: filter,
    pending: {
      cells: cells.length,
      visible_cells: visibleCells,
      paths: allPaths.length,
      without_path: withoutPath,
      fields: fieldCounts,
      sample: samples,
      sample_truncated: allPaths.length > samples.length,
    },
    cached_tree: {
      root_nodes: _lastTreeRender?.tree?.length || 0,
      tally_cache_status: _lastTreeRender?.tallyCacheStatus || null,
    },
    progress: {
      in_flight: indexProgressInFlight,
      polling: indexProgressTimer !== null,
      completion_refresh_in_flight: indexProgressCompletionRefreshInFlight,
      last_rendered: indexProgressLastRendered,
    },
    event_stream: {
      ready_state: typeof readyState === "number" ? readyState : null,
      consecutive_errors: _esConsecutiveErrors,
      reconnect_scheduled: _esReconnectTimer !== null,
      reconnect_backoff_ms: _esBackoffMs,
      file_store_entries: fileStore?.size || 0,
    },
    document_visibility: document.visibilityState || null,
  };
}

async function refreshAfterPendingTallyDiagnostic(serverDiagnostic) {
  var status = serverDiagnostic?.inventory?.status;
  if (
    (status !== "done" && status !== "truncated") ||
    !document.querySelector("#tab-files .tally-pending")
  ) {
    return;
  }
  await loadTree({ reconcileMountedRoot: true });
  // The user can change or clear the filter while the tree request is in
  // flight. Re-read the current window after the await so recovery never
  // restores an obsolete recency source over the user's newer selection.
  var recency = filterState ? filterState.get().recency : null;
  if (recency && recency !== "all") {
    loadRecent(currentRecentFilterCursor());
  }
}

async function reportPendingTallyDiagnostic(payload) {
  var delaySeconds = PENDING_TALLY_DIAGNOSTIC_DELAY_MS / 1000;
  console.warn(`Folder totals are still loading after ${delaySeconds} seconds`, payload);
  try {
    var resp = await fetch("/api/diagnostics/pending-tallies", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      console.warn(`Could not record pending folder totals on the server: HTTP ${resp.status}`);
      return;
    }
    var serverDiagnostic = await resp.json();
    console.warn("Server state for pending folder totals", serverDiagnostic);
    await refreshAfterPendingTallyDiagnostic(serverDiagnostic);
  } catch (error) {
    console.warn("Could not record pending folder totals on the server", error);
  }
}

var pendingTallyWatchdog = window.MetabrowserPendingTallyDiagnostics.create({
  delayMs: PENDING_TALLY_DIAGNOSTIC_DELAY_MS,
  hasPending: () => !!document.querySelector("#tab-files .tally-pending"),
  collect: collectPendingTallyDiagnostic,
  report: reportPendingTallyDiagnostic,
  onError: (error) => console.warn("Could not collect pending folder total diagnostics", error),
});

function reconcilePendingTallyDiagnostics() {
  pendingTallyWatchdog?.reconcile();
}

window.addEventListener("pagehide", (event) => {
  if (!event.persisted) {
    pendingTallyWatchdog.dispose();
  }
});

function indexProgressIsActive(meta) {
  return !!meta && meta.status === "scanning";
}

function indexProgressBucket(files) {
  return Math.floor((files || 0) / INDEX_PROGRESS_UPDATE_FILES);
}

function renderIndexProgress(meta) {
  var el = document.getElementById("index-progress");
  if (!el) {
    return;
  }
  if (!indexProgressIsActive(meta)) {
    indexProgressLastRendered = meta || null;
    // While a grouping's sections are on their way the row says so (renderRegrouping),
    // and shows the scan again when they come.
    if (_regroupingBy === null) {
      el.hidden = true;
    }
    return;
  }
  // `meta.indexed_files` can be missing (server hasn't reported yet),
  // a true zero (scan started but nothing finalized), or a positive
  // count. Only show "~N files scanned" once we have a positive count;
  // otherwise the spinner plus a generic "Scanning…" label is the
  // right UX — a literal "~0 files scanned" reads as "scan stuck".
  var rawFiles = meta.indexed_files;
  var files = typeof rawFiles === "number" && rawFiles > 0 ? rawFiles : null;
  if (_regroupingBy !== null) {
    indexProgressLastRendered = { status: meta.status, indexed_files: files };
    return;
  }
  var text = el.querySelector(".index-progress-text");
  if (text) {
    text.textContent = files == null ? "Scanning…" : `~${files.toLocaleString()} files scanned`;
  }
  el.hidden = false;
  indexProgressLastRendered = {
    status: meta.status,
    indexed_files: files,
  };
}

function shouldRenderIndexProgress(meta, force) {
  if (force || !indexProgressLastRendered) {
    return true;
  }
  if (meta.status !== indexProgressLastRendered.status) {
    return true;
  }
  if (!indexProgressIsActive(meta)) {
    return true;
  }
  return (
    indexProgressBucket(meta.indexed_files) !==
    indexProgressBucket(indexProgressLastRendered.indexed_files)
  );
}

function stopIndexProgressPolling() {
  if (!indexProgressTimer) {
    return;
  }
  clearInterval(indexProgressTimer);
  indexProgressTimer = null;
}

// Finishing a crawl changes no entry, so it produces no file-store op and
// therefore no inventory-change event. Every rollup watch refreshes on that
// event alone, so without this announcement the last rollup a folder fetched
// keeps reporting index_status "scanning" for the rest of the session: the
// counts were right and the label above them was not, and nothing short of a
// reload cleared it. Announce the transition on the channel an entry change
// already uses, with null paths — "anything may have changed" — so each watch
// re-fetches once and reads the terminal status.
function announceScanCompletion() {
  window.dispatchEvent(
    new CustomEvent("metabrowser:inventory-change", {
      detail: { kind: "index-complete", paths: null },
    }),
  );
}

// A reconnect whose snapshot equals the last one skips parsing and repainting it, so
// no file-store notice goes out. It still cannot prove deep files unchanged (see the
// fs.snapshot listener): a file deeper than the stream watches may have changed while it
// was down. Announce it as a changed snapshot is announced, with null paths -- "anything
// may have changed" -- so SDK consumers (onInventoryChange) and rollup watches treat it
// as the reconnect it is.
function announceUnchangedSnapshot() {
  window.dispatchEvent(
    new CustomEvent("metabrowser:inventory-change", {
      detail: { kind: "snapshot", paths: null },
    }),
  );
}

async function refreshTreeIfPendingTallies() {
  if (indexProgressCompletionRefreshInFlight || _rootTreeRequestsInFlight > 0) {
    return;
  }
  if (!document.querySelector("#tab-files .tally-pending")) {
    return;
  }
  indexProgressCompletionRefreshInFlight = true;
  try {
    await loadTree({ reconcileMountedRoot: true });
    // Match diagnostic recovery: the tree request updates the authoritative
    // cache but deliberately does not paint over an active recency source.
    // Re-read after the await so a filter change during the request wins.
    var recency = filterState ? filterState.get().recency : null;
    if (recency && recency !== "all") {
      loadRecent(currentRecentFilterCursor());
    }
    if (currentPath) {
      setSelectedPath(currentPath);
    }
  } catch (e) {
    console.warn("tree refresh after scan completion failed", e);
    // Best-effort cleanup for stale startup placeholders. The next
    // manual reload or tree fetch will still render from the final
    // inventory state.
  } finally {
    indexProgressCompletionRefreshInFlight = false;
  }
}

async function refreshIndexProgress(force) {
  if (indexProgressInFlight) {
    return;
  }
  indexProgressInFlight = true;
  try {
    var resp = await fetch("/api/index/progress", {
      cache: "no-store",
    });
    if (resp.status === 304) {
      return;
    }
    if (!resp.ok) {
      console.warn(`index progress: HTTP ${resp.status}`);
      renderIndexProgress(null);
      stopIndexProgressPolling();
      return;
    }
    var meta = await resp.json();
    // Read before rendering: renderIndexProgress overwrites the record of
    // what the last poll saw, and the transition out of scanning is only
    // visible by comparing against it.
    var wasScanning = indexProgressLastRendered?.status === "scanning";
    if (shouldRenderIndexProgress(meta, force)) {
      renderIndexProgress(meta);
    }
    if (!indexProgressIsActive(meta)) {
      if (meta?.truncated) {
        ensureTreeTruncationNote(meta.max_files);
      }
      renderIndexProgress(meta);
      // Queue overflow deliberately replaces the SSE connection. Its terminal
      // capability event can therefore be the event that was dropped. The
      // lightweight progress poll is an independent completion source: let a
      // successfully completed (including capped) walk finish or repair the
      // Quick File catalog before the reconnect backoff expires. A failed or
      // idle provider is also inactive, but must not promote partial membership
      // to complete coverage. CatalogFeed coalesces this with the normal SSE
      // notification.
      if (meta?.complete === true) {
        quickFileCatalogFeed?.onIndexComplete(meta.truncated === true);
      }
      if (wasScanning) {
        announceScanCompletion();
      }
      await refreshTreeIfPendingTallies();
      stopIndexProgressPolling();
    }
  } catch (_e) {
    renderIndexProgress(null);
    stopIndexProgressPolling();
  } finally {
    indexProgressInFlight = false;
  }
}

function startIndexProgressPolling() {
  if (isGitRevisionSource() || indexProgressTimer) {
    return;
  }
  refreshIndexProgress(true);
  indexProgressTimer = setInterval(() => {
    refreshIndexProgress(false);
  }, INDEX_PROGRESS_POLL_MS);
}

// ── Nav panel registry ─────────────────────────────────────────
// Files is server-rendered for first paint. Conditional panels register after
// discovery (for example /api/git/repo), with their own first-show hooks. Late
// registration creates a tab/container, so retired panels must not register.
// This remains internal; no plugin registerNavPanel surface is exposed.

/** @type {ReturnType<NonNullable<Window["MetabrowserMainTabs"]>["create"]> | null} */
var mainTabs = null;
var mainTabIntent = 0;
var pullHistoryGeneration = 0;
// The pane's claims, phases, and placeholders live in the navigation module so
// a browserless session can drive exactly what this shell paints.
var previewPane = window.MetabrowserNavigationRoute.createPreviewPaneLifecycle();
/** @type {(() => void) | null} */
var pendingFilePreviewStageCleanup = null;

function cancelPendingFilePreviewStage() {
  const cleanup = pendingFilePreviewStageCleanup;
  pendingFilePreviewStageCleanup = null;
  cleanup?.();
}

// Completed replacements ease only compositor opacity. Retained content is
// never animated while work is pending.
var PREVIEW_ARRIVAL_DURATION_MS = 50;
var PREVIEW_ARRIVAL_START_OPACITY = 0.98;
/** @type {Animation | null} */
var previewArrivalAnimation = null;

/** @param {HTMLElement} content */
function animatePreviewContentArrival(content) {
  previewArrivalAnimation?.cancel();
  previewArrivalAnimation = null;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return;
  }
  const animation = content.animate([{ opacity: PREVIEW_ARRIVAL_START_OPACITY }, { opacity: 1 }], {
    duration: PREVIEW_ARRIVAL_DURATION_MS,
    easing: "ease-out",
  });
  previewArrivalAnimation = animation;
  animation.addEventListener(
    "finish",
    () => {
      if (previewArrivalAnimation === animation) {
        previewArrivalAnimation = null;
      }
    },
    { once: true },
  );
}

/** @param {HTMLElement} preview */
function clearPreviewNavigationState(preview) {
  preview.classList.remove("preview-navigation-pending");
  if (preview.hasAttribute("data-preview-pending-claim")) {
    preview.removeAttribute("aria-busy");
    preview.removeAttribute("data-preview-pending-claim");
  }
}

/**
 * Claim the shared preview pane for one preview producer.
 *
 * Async preview producers keep the returned generation and check it
 * before every write. A later file selection, commit, or landing increments
 * the generation, making all older writes harmless. Route-driven tab
 * marking does not claim the pane.
 *
 * @param {string} owner
 * @param {{folder: boolean, path: string, viewId?: string}} [selection]
 *   What a `file` claim loads, so its placeholder and reconnect retry can
 *   name it.
 * @returns {number}
 */
function claimPreview(owner, selection) {
  cancelPendingFilePreviewStage();
  // Whatever claims the pane next retires the pull-request page, and any owner but the
  // Git panel retires its commit diff. Their DOM can stay visible until the replacement
  // is ready (createPullPageHost).
  for (const retired of [
    owner !== "git" && window.MetabrowserGitPanel?.cancelPending(),
    pullPageHost?.release(),
  ]) {
    // A later pending claim must not replace the one old visible handoff surface.
    if (!retired) {
      continue;
    }
    if (retainedPullPageDispose) {
      retired();
    } else {
      retainedPullPageDispose = retired;
    }
  }
  const preview = document.getElementById("preview-pane");
  if (preview) {
    clearPreviewNavigationState(preview);
  }
  const claim = previewPane.claim(owner, selection);
  if (preview) {
    preview.dataset.previewOwner = owner;
  }
  return claim;
}

/** @param {number} claim */
function isPreviewClaimCurrent(claim) {
  return previewPane.isCurrent(claim);
}

/**
 * Markup for one pane placeholder directive from the navigation module.
 *
 * @param {ReturnType<typeof previewPane.placeholder>} directive
 * @returns {string | null} Null when the directive paints nothing.
 */
function previewPlaceholderHtml(directive) {
  if (directive.paint === "loading") {
    return (
      '<div class="loading mb-delayed-loading"><div class="spinner"></div>' +
      `<span class="sr-only">Loading ${esc(directive.subject)}…</span></div>`
    );
  }
  if (directive.paint === "idle") {
    return `<div class="preview-empty">${esc(directive.message)}</div>`;
  }
  return null;
}

/**
 * Mark retained preview content as pending for one navigation claim.
 *
 * Empty-state chrome is not a useful handoff surface. A delayed initial
 * spinner may call this again after it has installed its neutral status.
 *
 * @param {number} claim
 * @returns {boolean} Whether the pane contains a surface that can carry pending state.
 */
function beginPreviewNavigation(claim) {
  if (!isPreviewClaimCurrent(claim)) {
    return false;
  }
  const preview = document.getElementById("preview-pane");
  const child = preview?.firstElementChild;
  if (
    !preview ||
    !child ||
    child.classList.contains("preview-empty") ||
    child.hasAttribute("data-preview-empty")
  ) {
    return false;
  }
  preview.classList.add("preview-navigation-pending");
  preview.setAttribute("aria-busy", "true");
  preview.setAttribute("data-preview-pending-claim", String(claim));
  return true;
}

/** @param {number} claim */
function endPreviewNavigation(claim) {
  const preview = document.getElementById("preview-pane");
  if (!preview || preview.getAttribute("data-preview-pending-claim") !== String(claim)) {
    return;
  }
  clearPreviewNavigationState(preview);
}

function isGitHistoryLanding() {
  const { pathname, search, hash } = window.location;
  return pathname === "/view/" && !search && !hash && window.history.state?.gitLanding === true;
}

function cancelMainTabPreview() {
  pullHistoryGeneration += 1;
  selectFileAbortController?.abort();
  selectFileAbortController = null;
  closeLiveStream();
  claimPreview("none");
}

function attachMainTabs() {
  mainTabs ??=
    window.MetabrowserMainTabs?.create({
      cancelPreview: cancelMainTabPreview,
      filesShown: resumeRootSummaryRefresh,
      filesHidden: closeFilterMenu,
      flushPull: () => pullPageHost?.page()?.flush?.(),
      // Read when called: the tree controller is created after the main tabs.
      focusFilesRow: () => treeKeyboard?.focusCurrent() ?? false,
      isGitHistoryLanding,
      isPullAddress,
      openHome: openHomeRoot,
      resetFiles: resetFilesTab,
      restore: () => navigationController.restore(),
      revealFile: (how) => revealFileRow(addressedFilePath(), how),
      scrollShadow: () => navScrollShadowUpdate?.(),
    }) ?? null;
  return mainTabs;
}

// The folder's name at the top of the nav is Home (docs/design-system.md, "Home"), and `0`
// runs the same path (shell-keymap.js). The link keeps its `/view/` address for what a
// browser does with a link, so a modified or middle click, its context menu, and copying
// it behave as they do on any link. A plain primary activation, by pointer or by Enter,
// stays in the page, so the caches that make the app fast stay too: a reload of `/view/`
// would draw the same page from nothing. It used to load `/view/` again, and a browser
// reloading the neutral Commits entry, which has that address, kept its state and came
// back to Commits.
function initHomeHeading() {
  queryHtml(".header-path")?.addEventListener("click", onHomeHeadingClick);
}

/** @param {MouseEvent} event */
function onHomeHeadingClick(event) {
  if (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  ) {
    return;
  }
  event.preventDefault();
  goHome();
}

/**
 * Home: the served folder's home view, exactly as a fresh load of `/view/` shows it
 * (docs/design-system.md, "Home"). The tab controller's `home` makes every tab forget where
 * it was, has every panel put back what a fresh load draws in it, the Files tab by
 * `resetFilesTab`, and opens the root at its default view (`openHomeRoot`).
 *
 * Before the tab controller has loaded, the server's tab is in front: Files, unless the
 * page opened on a pull request's address, and no other panel has mounted. With Files in
 * front this does what the controller's `home` does, the Files tab reset, the tree at its
 * top, and the root drawn again, even on the root already shown. Only a pull request's
 * page waits for the controller, and a later choice of the reader's cancels it, as a tab
 * click does.
 */
function goHome() {
  if (mainTabs) {
    void mainTabs.home().catch((error) => {
      console.error("Could not go home", error);
    });
    return;
  }
  const front = /** @type {HTMLElement | null} */ (
    queryHtml(".nav-tab-bar")?.querySelector(".tab-btn.active") ?? null
  );
  if ((front?.dataset.tab ?? "files") === "files") {
    resetFilesTab();
    const scroller = document.getElementById("tree-content");
    if (scroller) {
      scroller.scrollTop = 0;
    }
    void openHomeRoot().catch(console.error);
    return;
  }
  const intent = ++mainTabIntent;
  void window.MetabrowserAssets?.ensureAsset("main-tabs")
    .then(() => {
      const tabs = attachMainTabs();
      if (intent === mainTabIntent) {
        return tabs?.home();
      }
    })
    .catch(console.error);
}

/**
 * The served root, drawn again at its default view, as a fresh load draws it. What the
 * pane shows is released first, as a tab switch releases it, so the root already shown is
 * drawn again from the file cache rather than kept at the view tab and the place the
 * reader left it at; the old view stays on screen until the root's replaces it.
 *
 * @returns {Promise<unknown>}
 */
function openHomeRoot() {
  cancelMainTabPreview();
  return navigateToPath("");
}

/**
 * The Files tab as a page that has just loaded draws it: every filter and Group by at its
 * default, the filter drawer closed with no menu open, and the tree drawn again from the
 * server's answer with the folders a first paint opens and no other. A change of filter
 * draws the tree that way already (onFilterStateChange), so a reset that changes one
 * leaves the drawing to it, and one that changes none asks for the tree itself. The
 * subtree cache stays, so a folder the reader opens again opens at once.
 */
function resetFilesTab() {
  var barChanged = filterOpenMenu !== null || filterDrawerOpen;
  filterOpenMenu = null;
  filterDrawerOpen = false;
  if (!filterState) {
    return;
  }
  var current = filterState.get();
  var defaults = filterState.DEFAULTS;
  var fresh = Object.keys(defaults).every(
    (key) => JSON.stringify(current[key]) === JSON.stringify(defaults[key]),
  );
  if (!fresh) {
    // Its listener draws the bar, closed, and the tree for the defaults.
    _homeTreeDraw = true;
    filterState.set({ ...defaults });
    _homeTreeDraw = false;
    return;
  }
  if (barChanged) {
    renderNavFilterBar();
  }
  void loadTree({ asHome: true });
}

function initNavTabs() {
  queryHtml(".nav-tab-bar")?.addEventListener("click", (event) => {
    const button = /** @type {HTMLElement | null} */ (
      event.target instanceof Element ? event.target.closest(".tab-btn") : null
    );
    const panel = button?.dataset.tab;
    if (!panel) {
      return;
    }
    if (mainTabs) {
      mainTabs.open(panel);
      return;
    }
    const intent = ++mainTabIntent;
    if (!button.classList.contains("active")) {
      void window.MetabrowserAssets?.ensureAsset("main-tabs")
        .then(() => {
          const tabs = attachMainTabs();
          if (intent === mainTabIntent) {
            tabs?.open(panel);
          }
        })
        .catch(console.error);
    }
  });
}

/**
 * What the shell keymap's commands reach their controls through: the activation paths
 * only app.js can run, each the one its control's click runs; see shell-keymap.js. The
 * keymap reads its targets itself, and the commit view's Copy revision and the branch
 * selector reach it through its own module and the selector's.
 * @returns {MetabrowserPublicShellKeymapShell}
 */
function shellKeymapShell() {
  return Object.freeze({
    goHome,
    navToggle: () => navCollapse?.button ?? null,
    openFolder: navigateToFolder,
    selectPreviewTab,
    toggleFilterMenu,
    toggleNav: () => navCollapse?.toggle(),
  });
}

/** Finalize the retired page only after a new owner's content has been installed. */
function finishRetainedPullPage() {
  const dispose = retainedPullPageDispose;
  retainedPullPageDispose = null;
  dispose?.();
  // Every install of new main-pane content ends here, so the keys that act on it follow:
  // the view tab letters of the bar now committed, or none, and the header's Up and Copy.
  shellKeymap?.syncPane();
}

/** Stage a route-backed plugin in the existing connected, inert preview staging layer.
 * @param {HTMLElement} node
 * @param {number} claim
 * @returns {(() => void) | null}
 */
function stagePreviewNode(node, claim) {
  if (!isPreviewClaimCurrent(claim)) {
    return null;
  }
  cancelPendingFilePreviewStage();
  const preview = document.getElementById("preview-pane");
  if (!preview) {
    return null;
  }
  const stage = createFilePreviewStage(preview);
  stage.append(node);
  const cleanup = () => {
    stage.remove();
    if (pendingFilePreviewStageCleanup === cleanup) {
      pendingFilePreviewStageCleanup = null;
    }
  };
  pendingFilePreviewStageCleanup = cleanup;
  return cleanup;
}

// Dispose plugin views before replacing shell-owned preview HTML.
function renderPreviewHtml(html, claim) {
  if (!isPreviewClaimCurrent(claim)) {
    return null;
  }
  const preview = document.getElementById("preview-pane");
  if (!preview) {
    return null;
  }
  disposeActivePluginViews();
  delete preview.dataset.renderedPath;
  preview.innerHTML = html;
  finishRetainedPullPage();
  return preview;
}

// Atomically install a prepared view without reparsing its HTML.
function renderPreviewNode(node, claim) {
  if (!isPreviewClaimCurrent(claim)) {
    return null;
  }
  const preview = document.getElementById("preview-pane");
  if (!preview) {
    return null;
  }
  disposeActivePluginViews();
  delete preview.dataset.renderedPath;
  preview.replaceChildren(node);
  finishRetainedPullPage();
  animatePreviewContentArrival(node);
  return preview;
}

// The seam between the shell and modules that are not file renderers.
//
// Deliberately narrow, and deliberately not `window.metabrowser`: that
// object is the documented plugin SDK with a compatibility contract,
// whereas this is an internal boundary that core modules loaded by the
// shell may use. Exposing it at all is what lets git-panel.js stay out
// of app.js instead of adding a thousand lines to it.
window.MetabrowserShell = Object.freeze({
  activateNavPanel: (/** @type {string} */ id) => mainTabs?.activate(id),
  rememberMainTabAddress: () => mainTabs?.remember(),
  beginPreviewNavigation,
  claimPreview,
  endPreviewNavigation,
  isGitHistoryLanding,
  isPreviewClaimCurrent,
  openPullRequest: async (route) => {
    const generation = pullHistoryGeneration;
    const host = await loadPullPageHost();
    return generation === pullHistoryGeneration && mainTabs?.active() === "pulls"
      ? host.open(route)
      : { status: "cancelled" };
  },
  registerNavPanel: (/** @type {MetabrowserNavPanel} */ panel) => mainTabs?.register(panel),
  removeNavPanel: (/** @type {string} */ id) => mainTabs?.remove(id),
  renderPreviewHtml,
  rereadFiles,
  renderPreviewNode,
  stagePreviewNode,
  shortcuts: () => shortcutRegistry,
  sourceFreshness,
});

// Toggle the nav chrome's drop shadow based on whether the
// tree-content scroll position is at the top. At scrollTop=0 the
// shadow would fall onto whitespace and read as floating chrome;
// once content has scrolled under the chrome the shadow becomes
// useful as a "there's more above" cue. The hairline border-bottom
// stays in both states.
//
// The shadow rides the filter bar, not the tab bar: the filter bar is
// the bottom-most chrome above the scroll owner, so a shadow on the
// tab bar would land on the filter bar instead of on the content.
/** @type {(() => void) | null} */
var navScrollShadowUpdate = null;

function initNavScrollShadow() {
  const filterBar = document.getElementById("nav-filter-bar");
  const tabBar = queryHtml(".nav-tab-bar");
  const content = document.getElementById("tree-content");
  if (!content || (!filterBar && !tabBar)) {
    return;
  }
  const scrollContent = content;
  const pane = content.parentElement ?? content;
  function update() {
    // Resolved per call rather than once at startup: each tab shows its own
    // toolbar in the slot, and a shadow on a hidden one is no cue at all.
    // Whichever chrome is bottom-most *and visible* carries it, and the
    // others are cleared so a tab switch cannot leave two shadows armed.
    // The chrome is the pane's own children, so a scroll visits those and not
    // the document (44 to 510 us a call on 1,871 to 23,232 elements). A metadata
    // band under the toolbar takes its shadow while it has lines (styles.css).
    const target = pane.querySelector(":scope > [data-nav-toolbar]:not([hidden])") ?? tabBar;
    for (const chrome of pane.querySelectorAll(":scope > :is([data-nav-toolbar], .nav-tab-bar)")) {
      chrome.classList.toggle("scrolled", chrome === target && scrollContent.scrollTop > 0);
    }
  }
  navScrollShadowUpdate = update;
  // Passive listener — we never preventDefault — so the browser
  // can keep scroll responsive while we just read scrollTop.
  scrollContent.addEventListener("scroll", update, { passive: true });
  update();
}

// Window key → seconds-back from "now", injected from the one
// authoritative mapping in metabrowser/settings.py.
const _RECENT_WINDOW_SECONDS = _METABROWSER_SETTINGS.RECENT_WINDOW_SECONDS || {};

// Recent is a snapshot from /api/recent plus a live FileStore overlay. The SSE stream is
// scoped to ``root-depth-2``, so FileStore holds no file at depth 3+ and a FileStore-only
// panel silently truncated 24h / 7d / 30d / all to that scope.
//
// * On chip change, fetch ``/api/recent?window=...``: the server queries every known entry,
//   so ``entries_flat`` covers the whole window and is the base set, keyed by path.
// * ``fs.change`` upserts/removes mutate the base set in place when they fall inside the
//   window, and the panel re-paints (debounced); a change seen while the snapshot request
//   is in flight invalidates that response and schedules one authoritative refetch.
//
// FileStore stays the source of truth for the Files tab and tree decoration.
var recentBaseEntries = new Map(); // path -> recent-flat dict
var recentTotalMatching = 0;
var recentTotalMatchingExact = true;
var recentTruncated = false;
var recentInflight = null; // AbortController for the in-flight chip fetch
// The retained base deliberately survives replacement requests so a bounded
// same-selection repair can preserve rows. Its owner does not: a normal
// replacement clears this identity, preventing later event/expiry callbacks
// from painting the previous selection under the new controls.
var recentCommittedView = null;
const RECENT_REPAIR_RETRY_BASE_MS = 500;
const RECENT_REPAIR_RETRY_MAX_MS = 8000;
const RECENT_REPAIR_MAX_RETRIES = 4;
var recentFilterRefetch = treeFilterModel.createRecentRefetchScheduler(
  RECENT_RECLUSTER_DEBOUNCE_MS,
  (request) => {
    if (
      filesPanelUsesRecentSource() &&
      currentRecentWindow === request.windowKey &&
      recentFilterKey() === request.requestKey
    ) {
      fetchRecent(currentRecentFilterCursor());
    }
  },
  window,
);
function recentRepairDescriptor() {
  var cursor = currentRecentFilterCursor();
  return {
    preserveRows: recentViewOwnsCurrentCursor(),
    windowKey: cursor.windowKey,
    requestKey: cursor.recentRequestKey,
  };
}

function recentViewOwnsCurrentCursor() {
  return treeFilterModel.recentViewOwnsCursor(recentCommittedView, currentRecentFilterCursor());
}

var recentContinuity = treeFilterModel.createRecentContinuity({
  delayMs: RECENT_RECLUSTER_DEBOUNCE_MS,
  retryBaseMs: RECENT_REPAIR_RETRY_BASE_MS,
  maxRetryDelayMs: RECENT_REPAIR_RETRY_MAX_MS,
  maxRetries: RECENT_REPAIR_MAX_RETRIES,
  clock: window,
  onRepair: (request) => {
    treeFilterModel.runRecentRepair(recentContinuity, request, {
      current:
        filesPanelUsesRecentSource() &&
        currentRecentWindow === request.windowKey &&
        recentFilterKey() === request.requestKey,
      filterRefetchPending: recentFilterRefetch.pending(),
      recentLoaded: recentEverLoaded,
      viewCommitted: recentViewOwnsCurrentCursor(),
      // A repair is an invisible data replacement. Keep the reader's current
      // rows mounted until the authoritative answer is ready.
      fetch: (_windowKey, preserveRows) => fetchRecent(currentRecentFilterCursor(), preserveRows),
    });
  },
  onStatus: setRecentContinuityStatus,
});

var recentRecompute = treeFilterModel.createRecentRecomputeScheduler(
  RECENT_RECLUSTER_DEBOUNCE_MS,
  () => renderRecentFromBase(),
  (request) =>
    recentViewOwnsCurrentCursor() &&
    filesPanelUsesRecentSource() &&
    currentRecentWindow === request.windowKey &&
    recentFilterKey() === request.requestKey,
  window,
);

function scheduleRecentAuthoritativeRefetch() {
  treeFilterModel.invalidateRecent(recentContinuity, {
    recentActive: recentEverLoaded && filesPanelUsesRecentSource(),
    filterRefetchPending: recentFilterRefetch.pending(),
    repair: recentRepairDescriptor(),
  });
}

/** @param {number} lowerBound */
function markRecentTotalAsRetainedLowerBound(lowerBound) {
  recentTotalMatching = lowerBound;
  recentTotalMatchingExact = false;
  if (!filterState) {
    return;
  }
  _renderFilteredTally(filterState.get(), recentTotalMatching);
}
// Server-published set of dir paths the Recent panel paints gray.
// Pathspec is a backend concern; the SPA never re-derives this. A
// dir node produced by the Recent tree model is gray iff its
// compact path appears here. Refreshed on every /api/recent fetch;
// live fs.change ops can't grow it (a newly recent dir under a
// gitignored subtree goes un-marked until the next chip refetch).
var _GITIGNORED_DIR_PATHS = new Set();

function loadRecent(cursor) {
  // A timer scheduled for the previous window must not repaint its
  // cached rows while this replacement request is still loading.
  clearRecentExpiryRecheck();
  recentFilterRefetch.cancel();
  recentContinuity.cancelRepairs();
  // Lock the user's window intent synchronously so a second chip
  // click can dedup against it.
  currentRecentWindow = cursor.windowKey;
  recentEverLoaded = true;
  fetchRecent(cursor);
}

function fetchRecent(cursor, preserveRows) {
  // A queued repaint owns the snapshot that existed before this request.
  // Cancel it now; the scheduler's identity guard also rejects a callback
  // already moved into the browser task queue.
  recentRecompute.cancel();
  if (recentInflight) {
    recentInflight.abort();
    recentInflight = null;
  }
  if (preserveRows !== true) {
    recentCommittedView = null;
  }
  var results = recentResultsHost();
  // Always replace the panel, not just on a cold start. This source
  // paints over the full tree, so leaving the previous contents up
  // would show an unfiltered tree under a recency window that is
  // already selected — and a warm `recentBaseEntries` from an earlier
  // window is the wrong window's answer, not this one's.
  if (results && preserveRows !== true) {
    results.innerHTML =
      '<div class="recent-loading mb-delayed-loading" role="status"' +
      ' aria-label="Loading recent files"></div>';
  }
  var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
  recentInflight = ctrl;
  var load = treeFilterModel.beginRecentRequest(recentContinuity, cursor, preserveRows === true);
  var url = load.url;
  // Object identity, rather than this URL alone, distinguishes two successive
  // requests for the same selection. Abort is only a transport optimization:
  // it does not stop a provider query that has already begun.
  var request = load.request;
  var repair = load.repair;
  var fetchOpts = ctrl ? { signal: ctrl.signal } : undefined;
  _perf
    .measureAsync(
      "apiRecent:fetch",
      () =>
        fetch(url, fetchOpts).then((resp) => {
          if (!resp.ok) {
            throw new window.MetabrowserRequestErrors.RequestError(
              "Could not refresh recently modified files.",
              { status: resp.status, operation: "recent" },
            );
          }
          return resp.json();
        }),
      { window: cursor.windowKey },
    )
    .then((data) => {
      treeFilterModel.settleRecentSuccess(recentContinuity, request, repair, {
        current: filesPanelUsesRecentSource() && recentFilterKey() === load.url,
        commit: () => commitRecentResponse(data, cursor),
        render: renderRecentFromBase,
      });
    })
    .catch((err) => {
      if (window.MetabrowserRequestErrors.isAbortError(err)) {
        recentContinuity.abandonRequest(request);
        return;
      }
      treeFilterModel.settleRecentFailure(recentContinuity, request, repair, err, {
        current: filesPanelUsesRecentSource() && recentFilterKey() === load.url,
        classify: window.MetabrowserRequestErrors.classifyRequestError,
        showInitialError: () => {
          if (results) {
            results.innerHTML =
              '<div class="recent-empty nav-error" role="alert">Could not load recently modified files. Reload the page to try again.</div>';
          }
        },
      });
    })
    .finally(() => {
      recentContinuity.abandonRequest(request);
      if (recentInflight === ctrl) {
        recentInflight = null;
      }
    });
}

/** Commit one accepted provider response without rendering it. */
function commitRecentResponse(data, cursor) {
  observeFileAges(data?.ages, data?.undated);
  var flat = data?.entries_flat || [];
  knownFileCatalog?.observeRecent(flat);
  recentBaseEntries = new Map();
  for (var i = 0; i < flat.length; i++) {
    var file = flat[i];
    if (file?.path) {
      recentBaseEntries.set(file.path, file);
    }
  }
  recentTotalMatching = data?.total_matching ?? flat.length;
  recentTotalMatchingExact = data?.total_matching_exact !== false;
  recentTruncated = !!data?.truncated;
  _GITIGNORED_DIR_PATHS = new Set(data?.gitignored_dirs || []);
  // The response is already filtered before its cap; the browser repeats the
  // leaf predicate only for filesystem events merged after this fetch.
  recentCommittedView = Object.freeze({
    windowKey: cursor.windowKey,
    requestKey: cursor.recentRequestKey,
  });
}

// Render the Recent panel from the server-filtered snapshot plus live
// filesystem updates. Membership is decided over complete leaves before
// clustering; mounted DOM rows never participate in that decision.
function renderRecentFromBase() {
  if (!recentViewOwnsCurrentCursor()) {
    return;
  }
  const results = recentResultsHost();
  if (!results || !filterState) {
    return;
  }
  treeKeyboard?.prepareForMutation();
  var nowSec = Date.now() / 1000;
  var state = filterState.get();
  var inputCount = recentBaseEntries.size;
  treeFilterModel.renderRecentView(
    Array.from(recentBaseEntries.values()),
    {
      filterState: filterState,
      ignoredDirectoryPaths: _GITIGNORED_DIR_PATHS,
      limit: RECENT_LIMIT,
      nowSec: nowSec,
      clusterPct: RECENT_CLUSTER_PCT,
      state: state,
    },
    (view) => paintRecentView(results, state, inputCount, view),
  );
}

/** Paint one already-decided Recent projection. */
function paintRecentView(results, state, inputCount, view) {
  var entries = view.entries;
  var lostKnownMember = view.matchingCount < inputCount;
  // A fetched page and its live overlay never retain more than the measured
  // route cap. The model chooses the same top-N order as the provider before
  // this replacement, so dropping the overflow does not change the view.
  recentBaseEntries = new Map(entries.map((entry) => [entry.path, entry]));
  _perf.measure(
    "renderRecent:root",
    () => {
      results.innerHTML = renderRecentList({ tree: view.tree });
    },
    { items: inputCount },
  );
  scheduleRecentExpiryRecheck(entries);
  _renderFilteredTally(state, entries.length);
  // Rendering replaces the whole panel, so restore any retry status that a
  // live repaint displaced while the authoritative repair is still pending.
  setRecentContinuityStatus(recentContinuity.status());
  renderSelectionOutsideFilterNote();
  if (currentPath) {
    setSelectedPath(currentPath);
  }
  reconcilePendingTallyDiagnostics();
  synchronizeTreeNow();
  // A capped snapshot cannot fill a hole from data it never received. This
  // catches time-window expiry between paints; explicit removals and rank
  // regressions take the same coalesced repair path below.
  if (recentTruncated && lostKnownMember && entries.length < RECENT_LIMIT) {
    markRecentTotalAsRetainedLowerBound(entries.length);
    scheduleRecentAuthoritativeRefetch();
  }
}

const RECENT_EXPIRY_MIN_DELAY_MS = 250;
const RECENT_EXPIRY_BOUNDARY_FUZZ_MS = 50;
// Browsers store timer delays in a signed 32-bit integer. A freshly
// touched file in the 30-day window crosses that limit, so wake once
// at the maximum and schedule the remaining interval on that repaint.
const RECENT_EXPIRY_MAX_DELAY_MS = 2_147_000_000;
var recentExpiryHandle = null;

function clearRecentExpiryRecheck() {
  if (recentExpiryHandle !== null) {
    clearTimeout(recentExpiryHandle);
    recentExpiryHandle = null;
  }
}

/** Repaint when the oldest visible file crosses the active window boundary. */
function scheduleRecentExpiryRecheck(entries) {
  clearRecentExpiryRecheck();
  var seconds = _RECENT_WINDOW_SECONDS[currentRecentWindow];
  if (typeof seconds !== "number" || entries.length === 0 || !filesPanelUsesRecentSource()) {
    return;
  }
  var oldestMtime = entries[0].mtime || 0;
  for (var i = 1; i < entries.length; i++) {
    oldestMtime = Math.min(oldestMtime, entries[i].mtime || 0);
  }
  var due = Math.min(
    RECENT_EXPIRY_MAX_DELAY_MS,
    Math.max(
      RECENT_EXPIRY_MIN_DELAY_MS,
      (oldestMtime + seconds) * 1000 - Date.now() + RECENT_EXPIRY_BOUNDARY_FUZZ_MS,
    ),
  );
  recentExpiryHandle = setTimeout(() => {
    recentExpiryHandle = null;
    if (filesPanelUsesRecentSource()) {
      renderRecentFromBase();
    }
  }, due);
}

// Both tree sources paint into the Files panel now that Recent is a
// filter rather than a tab.
function recentResultsHost() {
  return document.getElementById("tab-files");
}

/** @param {"fresh" | "retrying" | "stale"} status */
function setRecentContinuityStatus(status) {
  var existing = document.querySelector(".recent-stale-note");
  if (status === "fresh" || !filesPanelUsesRecentSource()) {
    existing?.remove();
    return;
  }
  var text =
    status === "retrying"
      ? "Recent files may be out of date; retrying…"
      : "Recent files may be out of date. Reload the page to try again.";
  if (existing) {
    existing.textContent = text;
    return;
  }
  var note = document.createElement("div");
  note.className = "recent-stale-note nav-metadata nav-metadata-note";
  note.setAttribute("role", "status");
  note.textContent = text;
  addFilesRemark(note);
}

function renderRecentList(data) {
  var tree = data.tree || [];
  if (tree.length === 0) {
    var emptyText =
      fileAgesState === "dating"
        ? "Reading file ages…"
        : fileAgesState === "failed"
          ? "No file ages to filter by."
          : currentRecentWindow === "live"
            ? `No files were modified in the past ${_RECENT_WINDOW_SECONDS.live} seconds.`
            : "No files were modified during the selected time range.";
    return `<div class="recent-empty">${emptyText}</div>`;
  }
  // Reuse the Files-tab renderer with one mode flip: dir rows
  // show file count instead of total bytes (see comments on
  // renderTreeNodes: aggregating bytes across "files modified
  // in last 24h" mixes incomparable things). isRoot=true so the
  // viewport-bounded expansion planner can select compact folders;
  // the Recent tree builder leaves ``expanded`` unset on those
  // nodes so explicit cluster-collapse state still wins.
  // The summary row stays in its band over the panel, and
  // renderRecentFromBase writes its filtered tally there from the
  // exact model entries after this markup is mounted.
  return renderTreeNodes(tree, true, { dirMetric: TREE_DIR_METRIC_COUNT });
}

// ── Navigation filter bar ───────────────────────────────────────
//
// One always-visible row (Group by) plus a drawer holding the three
// filters and Show ignored. Controls come from the shared chip family
// (static/filter-controls.js) and every click writes through to the
// shared state (static/filter-state.js), so the bar holds no state of
// its own.
//
// The drawer carries no section headings: its three menus' triggers
// and the checkbox's label say what they are.
//
// See docs/project/specs/done/plan-2026-08-09-nav-filter-controls.md.

var filterState = /** @type {any} */ (window).metabrowser?.filterState || null;
var filterControls = /** @type {any} */ (window.metabrowser?.filterControls) || null;

// Recency is one axis from "everything" to the shortest mtime window.
// Values match RECENT_WINDOW_SECONDS and the /api/recent contract; labels are
// shortened because the whole group has to fit a 300px pane.
// No "all" entry: the menu's any-row is that value, and listing it
// twice would offer the same choice under two names. Labels can be
// words rather than the abbreviations the segmented ramp needed,
// because a dropdown row is not fighting five siblings for width.
// Each row wears the freshness colour the tree gives files of that
// age, so the menu doubles as the legend for the ramp below it.
// Longer windows take the colour of the bucket they top out at. Live
// is an activity state that shares the freshest reddish-orange visual
// with under-one-minute files and spells out its exact server-owned
// cutoff in the accessible title.
var FILTER_RECENCY_OPTIONS = [
  {
    value: "live",
    label: "Live",
    tip: `Files modified in the past ${_RECENT_WINDOW_SECONDS.live} seconds`,
    ageClass: "age-live",
  },
  { value: "1h", label: "Past hour", ageClass: "age-min" },
  { value: "24h", label: "Past day", ageClass: "age-hr" },
  { value: "7d", label: "Past week", ageClass: "age-day" },
  { value: "30d", label: "Past month", ageClass: "age-wk" },
];

// Size is a cumulative floor rather than a band: "what is over 10M in
// here" is the question people ask, and a floor never makes you guess
// which band a file landed in.
var FILTER_SIZE_OPTIONS = [
  { value: "100k", label: ">100K" },
  { value: "1m", label: ">1M" },
  { value: "10m", label: ">10M" },
  { value: "100m", label: ">100M" },
  { value: "1g", label: ">1G" },
];

// Deliberately not persisted. The drawer holds the secondary controls,
// so a session that starts with it open costs vertical space the user
// did not ask for on this visit. Filter selections are transient too;
// the badge reports them whether or not the drawer is showing.
var filterDrawerOpen = false;
// At most one dropdown is open at a time — opening a second while the
// first is still down would leave two panels overlapping a 300px pane.
/** @type {string | null} */
var filterOpenMenu = null;
var filterBarUnbind = null;

/** Is any dimension constraining what the tree shows? */
function filterHasConstraints(state) {
  return (
    state.recency !== "all" || !!state.types || state.size !== "all" || state.showIgnored !== true
  );
}

// Filter tallies come from the server's full-index pass, not from the
// rendered tree or Quick File catalog. Both sources can be partial,
// and the catalog drops gitignored entries by design. Rows arrive as
// [key, tracked, ignored], so every count can follow the gitignored
// setting instead of being wrong half the time.
/** @type {Array<[string, number, number]>} */
var _extensionTally = [];
/** @type {Array<[string, number, number]>} */
var _canonicalExtensionTally = [];
/** @type {Array<[string, number, number]>} */
var _typeFamilyTally = [];
/** @type {Array<[string, number, number]>} */
var _typePresetTally = [];
/** @type {Array<[string, number, number]>} */
var _recencyTally = [];

function updateFilterTallies(data) {
  let changed = false;
  if (Array.isArray(data.extensions)) {
    _extensionTally = data.extensions;
    changed = true;
  }
  if (Array.isArray(data.canonical_extensions)) {
    _canonicalExtensionTally = data.canonical_extensions;
    changed = true;
  }
  if (Array.isArray(data.type_families)) {
    _typeFamilyTally = data.type_families;
    changed = true;
  }
  if (Array.isArray(data.type_presets)) {
    _typePresetTally = data.type_presets;
    changed = true;
  }
  if (Array.isArray(data.recency_tallies)) {
    _recencyTally = data.recency_tallies;
    changed = true;
  }
  return changed;
}

function applyFilterTallies(data) {
  if (updateFilterTallies(data)) {
    refreshFilterTallies();
  }
}

// A bar rebuilt under an open menu would drop focus out of it, so only its counts change.
function refreshFilterTallies() {
  if (filterOpenMenu === null) {
    renderNavFilterBar();
  } else {
    patchOpenRecencyTallyCounts();
  }
}

function filterRecencyOptions() {
  const showIgnored = filterState ? filterState.get().showIgnored : true;
  const counts = new Map(
    _recencyTally.map((row) => [row[0], showIgnored ? row[1] + row[2] : row[1]]),
  );
  // "…" until a revision's ages are read: "0" would say they are none.
  return FILTER_RECENCY_OPTIONS.map((option) => ({
    ...option,
    count: counts.get(option.value) || (fileAgesState === "dating" ? "…" : 0),
  }));
}

// Age counts decay without a filesystem event. A refresh that lands while the menu
// is open updates only its count cells, preserving focus and keyboard position.
function patchOpenRecencyTallyCounts() {
  if (filterOpenMenu !== "recency") {
    return;
  }
  const counts = new Map(filterRecencyOptions().map((option) => [option.value, option.count]));
  const rows = queryHtmlAll("#filter-recency-menu [data-chip-value]");
  for (var i = 0; i < rows.length; i++) {
    var value = rows[i].getAttribute("data-chip-value");
    var count = value === null ? undefined : counts.get(value);
    var countEl = rows[i].querySelector(".chip-menu-count");
    if (count !== undefined && countEl) {
      countEl.textContent = count.toLocaleString();
    }
  }
}

// The tally the server last sent, for `filterControls.typeMenu`.
function filterTypeTally() {
  return {
    extensions: _extensionTally,
    canonical_extensions: _canonicalExtensionTally,
    type_families: _typeFamilyTally,
    type_presets: _typePresetTally,
  };
}

function filterTypeMenuOptions() {
  return { showIgnored: filterState ? filterState.get().showIgnored : true, iconFor: getFileIcon };
}

// Where the drawer's filters take their keyboard numbers while the drawer is closed: its
// triggers are inert then and cannot be numbered, so each filter is numbered on a stand-in
// beside the chevron, which a number reaches whether or not the drawer is open
// (shell-keymap.js, syncFilters). Activating one opens the drawer with its menu
// (toggleFilterMenu). The stand-ins take no space and no focus; a badge on one shows
// beside the chevron.
function filterKeySlotsHtml() {
  /** @type {Record<string, string>} */
  var names = { recency: "Modified within", types: "File type" };
  return (noFileAges ? ["types"] : ["recency", "types"])
    .map(
      (key) =>
        `<span class="filter-key-slot" data-filter-key-slot="${key}" aria-hidden="true"` +
        ` aria-label="${names[key]}"></span>`,
    )
    .join("");
}

// Group by's choices, each with the letter that chooses it while the menu is open
// (docs/design-system.md, "Keys in a Menu"). With no file ages there is no By age.
function filterGroupOptions() {
  var options = [
    { value: "age", label: "By age", key: "a" },
    { value: "type", label: "By file type", key: "t" },
  ];
  return noFileAges ? options.filter((option) => option.value !== "age") : options;
}

function filterTypePresetSections() {
  return filterControls
    ? filterControls.typeMenu.presetSections(filterTypeTally(), filterTypeMenuOptions())
    : [];
}

function allFilterTypePresets() {
  return filterTypePresetSections().flatMap((section) => section.presets);
}

function filterTypeOptions() {
  return filterControls
    ? filterControls.typeMenu.options(filterTypeTally(), filterTypeMenuOptions())
    : [];
}

// A recency window, Live included, reads /api/recent, which scans the whole index and
// not the loaded subtrees.
function filesPanelUsesRecentSource() {
  if (noFileAges || !filterState) {
    return false;
  }
  var st = filterState.get();
  // Group by draws filtered trees, which take the recency window as one more filter.
  return st.recency !== "all" && treeFilterModel.groupBy(st) === "none";
}

function renderNavFilterBar() {
  var bar = document.getElementById("nav-filter-bar");
  if (!bar || !filterState || !filterControls) {
    return;
  }
  var st = filterState.get();
  // Clear resets every filter, Show ignored included. The chevron's badge counts what is
  // set behind it, Show ignored turned off among them, since the closed drawer hides it.
  var count = filterState.activeCount();
  var drawerCount = treeFilterModel.drawerFilterCount(st);
  var fc = filterControls;
  // The three filters, each a dropdown. With no file ages, recency is omitted, not a 409.
  var recencyMenu = noFileAges
    ? ""
    : fc.menuGroupHtml({
        key: "recency",
        select: "one",
        label: "Modified within",
        options: filterRecencyOptions(),
        value: st.recency,
        anyLabel: "Any age",
        anyValue: "all",
        open: filterOpenMenu === "recency",
        menuId: "filter-recency-menu",
      });
  var typeMenu = fc.menuGroupHtml({
    key: "types",
    label: "File type",
    options: filterTypeOptions(),
    presetSections: filterTypePresetSections(),
    value: st.types,
    anyLabel: "Any type",
    open: filterOpenMenu === "types",
    menuId: "filter-type-menu",
  });
  var sizeMenu = fc.menuGroupHtml({
    key: "size",
    select: "one",
    label: "Minimum file size",
    options: FILTER_SIZE_OPTIONS,
    value: st.size,
    anyLabel: "Any size",
    anyValue: "all",
    open: filterOpenMenu === "size",
    menuId: "filter-size-menu",
  });
  // Show ignored follows the three filters in the drawer: turned off, it removes rows as
  // they do, and its tick states its own direction. A Git revision has no gitignored
  // entries to show, so it has no Show ignored.
  var ignoredCheck = isGitRevisionSource()
    ? ""
    : fc.checkHtml({
        key: "showIgnored",
        label: "Show ignored",
        checked: st.showIgnored,
      });
  var main =
    // A toolbar row, which wraps between its controls in a narrow pane (styles.css,
    // `.nav-toolbar-row`).
    '<div class="nav-filter-bar-main nav-toolbar-row">' +
    // Group by leads the row: splitting the tree by age or by type is the simplest way to
    // see a folder, and it removes nothing, so it needs no drawer. The filters and Show
    // ignored, which remove rows, sit behind the chevron, whose name counts the ones set; it
    // has no visible count, so Clear and the chevron fit beside Group by
    // (docs/design-system.md, "Grouping the Files Tree").
    fc.menuGroupHtml({
      key: "group",
      select: "one",
      label: "Group by",
      options: filterGroupOptions(),
      value: treeFilterModel.groupBy(st),
      anyLabel: "No grouping",
      anyKey: "n",
      anyValue: "none",
      open: filterOpenMenu === "group",
      menuId: "filter-group-menu",
    }) +
    '<span class="nav-filter-bar-end">' +
    // Clear sits on the row with the chevron: it can only appear when a filter is set,
    // and having to open the drawer to undo one is a step too many. "Clear", not "Clear
    // filters", to leave the Group by trigger room for its longest value.
    (count > 0 ? fc.clearHtml({ label: "Clear" }) : "") +
    fc.toggleHtml({
      key: "drawer",
      // The shared chevron glyph, rotated by CSS to point at the state
      // it will produce — the same icon the tree uses for expansion.
      icon: ICONS.toggle || "",
      className: "filter-drawer-toggle disclosure-toggle",
      pressed: filterDrawerOpen,
      // A glyph-only control needs a name that says what happens, and
      // the badge is decorative once the count is spoken here.
      ariaLabel:
        (filterDrawerOpen ? "Hide filters" : "Show filters") +
        (drawerCount > 0 ? ` (${drawerCount} active)` : ""),
      tip: filterDrawerOpen ? "Hide filters" : "Filters",
      controls: "filter-drawer",
    }) +
    filterKeySlotsHtml() +
    "</span></div>";
  var drawer =
    // `inert` rather than `hidden`: it keeps the closed drawer out of
    // the tab order and the accessibility tree without the
    // `display: none` that would make the open transition impossible.
    // The single child is the grid track's content — see the
    // .filter-drawer rules.
    '<div class="filter-drawer" id="filter-drawer" data-open="' +
    (filterDrawerOpen ? "true" : "false") +
    '"' +
    (filterDrawerOpen ? "" : " inert") +
    ">" +
    '<div class="filter-drawer-row">' +
    recencyMenu +
    typeMenu +
    sizeMenu +
    ignoredCheck +
    "</div></div>";
  // The rebuild replaces the control that has focus: a menu row, its trigger, a checkbox.
  // Focus goes back to the same control, or to the trigger of a menu the rebuild closed,
  // so a key, a pick, or a tally refresh never drops it on the page (docs/design-system.md,
  // "Keys in a Menu").
  var restoreFocus = fc.keepFocus(bar);
  bar.innerHTML = main + drawer;
  // An open menu is sized to its rows and the window now that it has geometry, before
  // the frame paints it.
  fc.fitOpenMenus(bar);
  // The rebuild replaced the triggers that the file type and modified-within keys badge.
  shellKeymap?.syncFilters();
  restoreFocus();
}

// Flip the drawer's open state on the existing nodes. Re-rendering
// would replace the element, and a new element starts at its final
// grid track with nothing to animate from.
function applyDrawerOpenState() {
  var drawer = document.getElementById("filter-drawer");
  var toggle = queryHtml("[data-chip-key='drawer']");
  if (drawer) {
    drawer.dataset.open = filterDrawerOpen ? "true" : "false";
    drawer.toggleAttribute("inert", !filterDrawerOpen);
  }
  if (toggle) {
    var count = filterState ? treeFilterModel.drawerFilterCount(filterState.get()) : 0;
    toggle.setAttribute("aria-pressed", String(filterDrawerOpen));
    toggle.setAttribute(
      "aria-label",
      (filterDrawerOpen ? "Hide filters" : "Show filters") +
        (count > 0 ? ` (${count} active)` : ""),
    );
    toggle.dataset.tipText = filterDrawerOpen ? "Hide filters" : "Filters";
  }
  // The drawer's filters take their numbers on their triggers while it is open, and on
  // their stand-ins while it is closed.
  shellKeymap?.syncFilters();
}

// The Files toolbar is hidden with its panel. A filter menu left open there is not on
// screen to use, and with no box to measure it would be fitted to nothing and come back
// as an empty sliver, so it closes.
function closeFilterMenu() {
  if (filterOpenMenu === null) {
    return;
  }
  filterOpenMenu = null;
  renderNavFilterBar();
}

/**
 * Open or close one filter dropdown, as its trigger does. At most one is open. The
 * trigger's click and the file type and modified-within keys share this path.
 *
 * @param {string} key
 * @param {boolean} open
 */
function toggleFilterMenu(key, open) {
  if (key === "group" && !open) {
    // A row the keyboard is resting on asks for nothing once the menu closes.
    groupsPrefetch.cancelRest();
  }
  filterOpenMenu = open ? key : null;
  // The filters live in the drawer: a key that opens one opens the drawer with it.
  if (open && key !== "group") {
    filterDrawerOpen = true;
  }
  renderNavFilterBar();
  if (key === "recency" && open) {
    scheduleRootSummaryRefresh();
  }
}

function initFilterBar() {
  var bar = document.getElementById("nav-filter-bar");
  if (!bar || !filterState || !filterControls) {
    return;
  }
  // Always starts closed; see filterDrawerOpen.
  filterDrawerOpen = false;
  renderNavFilterBar();
  if (filterBarUnbind) {
    filterBarUnbind();
  }
  filterBarUnbind = filterControls.bind(bar, {
    onChange: (key, value, select) => {
      if (select === "many") {
        var current = filterState.get()[key] || null;
        filterState.set({ [key]: filterControls.nextSelection("many", current, value) });
      } else {
        filterState.set({ [key]: value });
      }
    },
    onToggle: (key, pressed) => {
      if (key === "drawer") {
        filterDrawerOpen = pressed;
        // Closing the drawer must close a menu inside it, or the popup
        // would hang over the tree with no owner in sight.
        // Every menu but Group by is in the drawer.
        var hadMenu = filterOpenMenu !== null && filterOpenMenu !== "group";
        if (!pressed && hadMenu) {
          filterOpenMenu = null;
        }
        // Mutate in place rather than re-render: a freshly built
        // element starts at its final grid track and would snap open.
        // Only a menu closing alongside needs the full rebuild.
        if (hadMenu && !pressed) {
          renderNavFilterBar();
        } else {
          applyDrawerOpenState();
        }
        return;
      }
      if (key === "showIgnored") {
        filterState.set({ showIgnored: pressed });
      }
    },
    onMenuToggle: toggleFilterMenu,
    onMenuPreset: (key, presetId, wasOn) => {
      if (key !== "types") {
        return;
      }
      // const, not var: the closures below need the narrowing that a
      // function-scoped binding cannot promise.
      const preset = allFilterTypePresets().find((p) => p.id === presetId);
      if (!preset) {
        return;
      }
      filterState.set({
        types: filterControls.typeMenu.togglePreset(filterState.get().types, preset.values, wasOn),
      });
    },
    onMenuPick: (key, value) => {
      // The any-row clears the dimension back to its default rather
      // than toggling a value.
      if (key === "types") {
        if (value === null) {
          filterState.set({ types: null });
        } else {
          var current = filterState.get().types;
          filterState.set({ types: filterControls.nextSelection("many", current, value) });
        }
        // Multi-select stays open — picking several extensions is the
        // whole point of it.
        return;
      }
      if (key === "group") {
        // Closed first, so the bar the change renders, before any of the work the choice
        // starts, is the closed trigger reading the choice: it shows in the frame the
        // choice is made, whatever the groups then take (mb-75l5).
        filterOpenMenu = null;
        filterState.set({ group: value === null ? "none" : value });
        return;
      }
      if (key === "recency" || key === "size") {
        filterState.set({ [key]: value === null ? "all" : value });
        // Single-select closes on pick: the choice is made, and a menu
        // left hanging over the tree has nothing more to offer.
        filterOpenMenu = null;
        renderNavFilterBar();
      }
    },
    onMenuFocus: restOnGroupingRow,
    onClear: () => {
      filterOpenMenu = null;
      filterState.clear();
    },
  });
  // The grouping a pointer presses is asked for ahead at once (prefetchPressedGrouping);
  // one the keyboard rests on, after a dwell (onMenuFocus above).
  const intentRoot = bar;
  var unbindControls = filterBarUnbind;
  intentRoot.addEventListener("pointerdown", prefetchPressedGrouping);
  filterBarUnbind = () => {
    unbindControls?.();
    groupsPrefetch.cancelRest();
    intentRoot.removeEventListener("pointerdown", prefetchPressedGrouping);
  };
  // Seed the source tracking from the persisted state so the first
  // user change is compared against reality, not against null.
  _filterCursor = currentRecentFilterCursor();
  filterState.subscribe(onFilterStateChange);
}

// One place decides what a filter change costs. Both sources resolve the
// filter on the server, so a change to any dimension either source reads
// is a refetch, not a repaint.
var _filterCursor = null;

function currentRecentFilterCursor(state = currentFilterSnapshot()) {
  return treeFilterModel.recentFilterCursor(state, RECENT_LIMIT, treeFilterSizeFloors());
}

function recentFilterKey() {
  return currentRecentFilterCursor().recentRequestKey;
}

function onFilterStateChange(state) {
  renderNavFilterBar();
  var transition = treeFilterModel.recentFilterTransition(
    _filterCursor,
    currentRecentFilterCursor(state),
  );
  _filterCursor = transition.current;
  if (transition.action === "load-recent") {
    // Grouping left for the Recent list: the groups on their way are not wanted.
    cancelGroupedLoad();
    loadRecent(transition.current);
    return;
  }
  if (transition.action === "refetch-recent") {
    // Filter menus can emit several type/size selections in one gesture. An
    // HTTP abort does not cancel the provider's O(N) scan, so invalidate the
    // old response now and launch only the final selection after the burst.
    recentRecompute.cancel();
    if (recentInflight) {
      recentInflight.abort();
      recentInflight = null;
    }
    recentContinuity.abandonRequest();
    recentContinuity.cancelRepairs();
    recentFilterRefetch.schedule({
      windowKey: transition.current.windowKey,
      requestKey: transition.current.recentRequestKey,
    });
    return;
  }
  if (transition.action === "load-groups") {
    // Group by draws filtered trees, recency included, so a Recent list in flight or on
    // screen has nothing more to say: drop it as a return to the tree does, then load
    // the sections.
    recentRecompute.cancel();
    if (recentInflight) {
      recentInflight.abort();
      recentInflight = null;
    }
    recentContinuity.abandonRequest();
    recentFilterRefetch.cancel();
    recentContinuity.cancelRepairs();
    currentRecentWindow = "";
    clearRecentExpiryRecheck();
    void loadGroupedTree();
    return;
  }
  if (transition.action === "load-tree") {
    // Abandon any recency fetch still in flight and drop the window it
    // was for. Otherwise a late response repaints the panel with the
    // old window's list under a trigger that now reads "Any age".
    // The same for groups on their way: No grouping ends their wait at once.
    cancelGroupedLoad();
    recentRecompute.cancel();
    if (recentInflight) {
      recentInflight.abort();
      recentInflight = null;
    }
    recentContinuity.abandonRequest();
    recentFilterRefetch.cancel();
    recentContinuity.cancelRepairs();
    // Empty, not a window key: a late response compares against this
    // and must never find a match.
    currentRecentWindow = "";
    clearRecentExpiryRecheck();
    // Refetch the authoritative tree. The first-paint cache can still carry
    // pending aggregates even after live events patched the visible DOM; using
    // it here reintroduced skeleton cells after progress polling had stopped.
    // Home's reset draws it as a fresh load does (resetFilesTab).
    var asHome = _homeTreeDraw;
    _homeTreeDraw = false;
    loadTree({ asHome });
    return;
  }
  applyTreeFilters();
}

// ── Applying filters to the tree ────────────────────────────────
//
// Both sources are filtered before rendering. /api/tree returns pruned folder
// aggregates; /api/recent returns matching leaves and the browser clusters
// those leaves before render. This pass only handles tree leaves inserted by
// the live event stream. It must never infer membership from mounted folders:
// collapsed and paged descendants are deliberately absent from the DOM.

function applyTreeFilters() {
  return _perf.measure("applyTreeFilters", applyTreeFiltersInner);
}

function applyTreeFiltersInner() {
  var panel = document.getElementById("tab-files");
  if (!panel || !filterState) {
    scheduleTreeSynchronize();
    return;
  }
  var st = filterState.get();
  if (filesPanelUsesRecentSource()) {
    renderSelectionOutsideFilterNote();
    scheduleTreeSynchronize();
    return;
  }
  _applyTreeSourceFilters(panel, st);
  scheduleTreeSynchronize();
}

// /api/tree already filters the whole index and supplies matching folder
// totals; mounted descendants cannot determine folder membership. Apply local
// filters only to new event-stream leaves. Live folders retain authoritative
// aggregates until the next response; refetching per event would collapse rows.
function _applyTreeSourceFilters(panel, state) {
  var rows = /** @type {HTMLElement[]} */ (
    Array.prototype.slice.call(
      panel.querySelectorAll(".tree-item.tree-file, .tree-item.tree-symlink"),
    )
  );
  var constrained = filterHasConstraints(state);
  var nowSec = Date.now() / 1000;
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    var hide =
      constrained &&
      (!state.showIgnored && row.classList.contains("tree-item-gitignored")
        ? true
        : !filterState.rowMatches(
            {
              mtime: parseTipNumber(row.dataset.tipMtime),
              size: parseTipNumber(row.dataset.tipSize),
              path: row.dataset.path || "",
              ext: row.dataset.ext || "",
              isSymlink: row.classList.contains("tree-symlink"),
            },
            state,
            nowSec,
          ));
    row.classList.toggle("tree-item-filter-hidden", hide);
  }
  _renderFilteredTally(state, _filteredTreeTotals ? _filteredTreeTotals.files : null);
  renderSelectionOutsideFilterNote();
  // A recency window's remark on its own freshness goes with it.
  setRecentContinuityStatus("fresh");
}

// How many files the filter is actually showing, as a second line
// under the tally. Rendered whenever anything is filtered, not only
// when a response was capped: "how many am I looking at" is the
// question a filter raises every time, and the totals above are what
// it reads against.
//
// `count` is a subtree total, never a count of rendered rows: the tree is
// capped by depth and the renderer pages long child lists, so a DOM count
// would report how much has been mounted. A null count means the filter has
// nothing to report and the line comes down.
function _renderFilteredTally(state, count) {
  var existing = document.querySelector(".tree-summary-filtered");
  if (!filterHasConstraints(state) || typeof count !== "number") {
    if (existing) {
      existing.remove();
    }
    return;
  }
  // Its numbers are bold, as the totals' are, so the two read against each other.
  var parts = treeFilterModel.filteredTallyParts(
    count,
    filesPanelUsesRecentSource()
      ? {
          totalMatching: recentTotalMatching,
          totalMatchingExact: recentTotalMatchingExact,
          truncated: recentTruncated,
        }
      : null,
  );
  // The remark is one item of the line, its words and numbers in one span: painted
  // straight into the flex line, each would be an item of its own, parted by the line's
  // gap and read as runs of their own.
  var remark = document.createElement("span");
  remark.append(...window.MetabrowserFormatters.countPartsNodes(document, parts));
  if (existing) {
    existing.replaceChildren(remark);
    window.MetabrowserRevisionAges?.annotate();
    return;
  }
  var summary = document.querySelector(".tree-summary");
  var line = document.createElement("div");
  line.className = "tree-summary-filtered nav-metadata nav-metadata-note";
  line.setAttribute("role", "status");
  line.append(remark);
  if (summary) {
    summary.insertAdjacentElement("afterend", line);
  } else {
    filesMetadataBand()?.insertAdjacentElement("afterbegin", line);
  }
  window.MetabrowserRevisionAges?.annotate();
}
// Rows arriving from the event stream have to be classified too, or a
// newly written file would appear regardless of the active filter.
var _filterReapplyHandle = null;
function scheduleFilterReapply() {
  if (_filterReapplyHandle || !filterState) {
    return;
  }
  // Nothing to reapply when nothing is filtered, and fs bursts would
  // otherwise walk the whole tree every 100ms in the default state.
  if (!filterHasConstraints(filterState.get())) {
    return;
  }
  _filterReapplyHandle = setTimeout(() => {
    _filterReapplyHandle = null;
    applyTreeFilters();
  }, RECENT_RECLUSTER_DEBOUNCE_MS);
}

// ── File selection + caching ────────────────────────────────────
//
// LRU caches keyed by path (stats keyed by run dir). Delete-then-set
// reorders the key to the Map tail so keys().next().value is always
// the oldest entry and gets evicted first. Skip cache for active
// files — content is still changing.

const CACHE_MAX = 30; // file payloads are small
const ETAG_REVALIDATE_MAX = 512;
const fileCache = new Map();
// HTTP ETags associated with cached file payloads. When filesystem facts change
// or a file drops out of the active set, mark it in ``fileNeedsRevalidate``
// rather than evicting the cache outright; the next ``selectFile``
// sends ``If-None-Match`` and accepts a 304 to re-confirm the payload
// without re-downloading. Server-side this is just the existing
// ``mtime_hash`` promoted to an HTTP-level ETag.
const fileETags = new Map();
const fileNeedsRevalidate =
  window.MetabrowserNavigationRoute.createFileRevalidationTracker(ETAG_REVALIDATE_MAX);

function boundMapSize(map, max) {
  while (map.size > max) {
    map.delete(map.keys().next().value);
  }
}

function evictFileCacheMetadata(path) {
  fileETags.delete(path);
  fileNeedsRevalidate.delete(path);
}

function cachePut(cache, key, value, maxSize, onEvict) {
  cache.delete(key);
  cache.set(key, value);
  while (cache.size > maxSize) {
    var evicted = cache.keys().next().value;
    cache.delete(evicted);
    if (onEvict) {
      onEvict(evicted);
    }
  }
}

var textChunkLoadInFlight = false;
/** @type {number | null} */
var filePreviewClaim = null;

/**
 * Bytes the next Load more will request. Each click doubles up to the cap, so
 * reaching a large file takes a handful of clicks rather than dozens while no
 * single click stalls the main thread.
 */
var textChunkNextBytes = TEXT_PREVIEW_CHUNK_BYTES;

function resetTextChunkGrowth() {
  textChunkNextBytes = TEXT_PREVIEW_CHUNK_BYTES;
}

/**
 * A path can leave and return while an earlier chunk request is pending. The
 * preview claim distinguishes that ABA sequence, and the cache identity keeps
 * a background replacement from accepting a chunk based on its predecessor.
 */
function textChunkRequestOwnsPreview(path, previewClaim, cached) {
  const sourceAppend = window.MetabrowserSourceAppend;
  if (sourceAppend) {
    return sourceAppend.requestOwnsPreview({
      cached,
      cachedForPath: fileCache.get(path),
      claim: previewClaim,
      currentPath,
      isClaimCurrent: isPreviewClaimCurrent,
      path,
    });
  }
  // The only pre-module path is a failed lazy asset load. Preserve the same
  // owned error behavior even though the production transaction could not
  // initialize.
  return (
    currentPath === path &&
    previewClaim !== null &&
    isPreviewClaimCurrent(previewClaim) &&
    fileCache.get(path) === cached
  );
}

function commitTextChunkCache(path, previewClaim, cached, nextCached, requested) {
  const nextBytes = window.MetabrowserSourceAppend.commitChunkCache({
    cached,
    cachedForPath: fileCache.get(path),
    claim: previewClaim,
    commit: (value) => cachePut(fileCache, path, value, CACHE_MAX, evictFileCacheMetadata),
    currentPath,
    isClaimCurrent: isPreviewClaimCurrent,
    nextCached,
    path,
    requested,
    requestCap: TEXT_PREVIEW_MAX_CHUNK_BYTES,
  });
  if (nextBytes === null) {
    return false;
  }
  textChunkNextBytes = nextBytes;
  return true;
}

function showTextChunkLoadError() {
  var warning = document.querySelector(".metabrowser-source-truncation-warning");
  if (!warning) {
    return;
  }
  warning.setAttribute("role", "alert");
  warning.innerHTML =
    "<strong>Could not load more content.</strong> Select Load more to try again.";
}

// The partial-content notice's Load more, registered by name with the SDK below.
async function loadMoreCurrentText() {
  if (textChunkLoadInFlight || !currentPath) {
    return;
  }
  var cached = fileCache.get(currentPath);
  if (!cached?.content_truncated) {
    return;
  }

  textChunkLoadInFlight = true;
  var path = currentPath;
  var previewClaim = filePreviewClaim;
  var offset = cached.bytes_read || 0;
  var requested = textChunkNextBytes;
  try {
    const assets = window.MetabrowserAssets;
    if (!assets) {
      throw new Error("Metabrowser asset loader is unavailable");
    }
    const [resp] = await Promise.all([
      fetch(
        "/api/file?path=" +
          encodeURIComponent(path) +
          "&offset=" +
          encodeURIComponent(String(offset)) +
          "&limit=" +
          encodeURIComponent(String(requested)),
      ),
      assets.ensureAsset("source-append"),
    ]);
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    var chunk = await _perf.measureAsync(
      "apiFile:textChunkJson",
      () => resp.json(),
      responsePerfMeta(resp, path, { offset: offset }),
    );
    const sourceAppend = window.MetabrowserSourceAppend;
    if (!sourceAppend) {
      throw new Error("Metabrowser source append runtime is unavailable");
    }
    if (!textChunkRequestOwnsPreview(path, previewClaim, cached)) {
      return;
    }
    if (chunk.mtime_hash && cached.mtime_hash && chunk.mtime_hash !== cached.mtime_hash) {
      fileNeedsRevalidate.add(path);
      boundMapSize(fileNeedsRevalidate, ETAG_REVALIDATE_MAX);
      await selectFile(path);
      return;
    }
    const nextCached = sourceAppend.nextCacheValue(cached, chunk);
    if (sourceAppend.appendSourceText(document, chunk.content || "", cached.content || "")) {
      // The append skipped the plugin's render, so the banner it emitted still
      // reports the byte counts from the previous chunk. Sync it rather than
      // leaving a "content truncated" notice over a fully loaded file.
      sourceAppend.syncTruncationWarning(
        document,
        window.metabrowser?.renderTextTruncationWarning?.(nextCached) || "",
      );
      sourceAppend.syncLoadMoreFooter(
        document,
        window.metabrowser?.renderTextLoadMoreFooter?.(nextCached) || "",
      );
      window.MetabrowserSourceLineAnchors?.refresh(document, nextCached);
      commitTextChunkCache(path, previewClaim, cached, nextCached, requested);
    } else {
      // The render replaces the whole file view; it keeps the tab the reader is on,
      // such as a Markdown file's Source tab that Load more is filling.
      var activeView = document.getElementById("preview-pane")?.dataset.activeView;
      await renderFile(nextCached, activeView || undefined, previewClaim, {
        isCurrent: () => textChunkRequestOwnsPreview(path, previewClaim, cached),
        onCommit: () => {
          commitTextChunkCache(path, previewClaim, cached, nextCached, requested);
          window.MetabrowserSourceLineAnchors?.refresh(document, nextCached);
        },
      });
    }
  } catch (e) {
    console.warn("Failed to load text chunk", e);
    if (textChunkRequestOwnsPreview(path, previewClaim, cached)) {
      showTextChunkLoadError();
    }
  } finally {
    textChunkLoadInFlight = false;
  }
}

// How long a fetch must take before the preview pane is replaced with
// the loading spinner. Below the threshold the previous file stays on
// screen until the new one is ready, eliminating the content→spinner
// →content flicker for fast local fetches.
var LOADING_INDICATOR_DELAY_MS = 120;
var loadingIndicatorTimer = null;
var selectFileAbortController = null;

/**
 * Settle an owned file-selection failure to one deterministic pane and result.
 * The same boundary covers hot cache, 304 revalidation, and fresh responses so
 * the on-demand compositor cannot turn one cache state into an unhandled
 * rejection while the others show a recoverable error.
 *
 * @param {unknown} err
 * @param {string} path
 * @param {object | undefined} cached
 * @param {HTMLElement} preview
 * @param {number} previewClaim
 * @returns {QuickFileOpenOutcome}
 */
function fileSelectionFailureOutcome(err, path, cached, preview, previewClaim) {
  return window.MetabrowserNavigationRoute.settleFileSelectionFailure({
    cached: !!cached,
    claim: previewClaim,
    error: err,
    isCurrent: () => currentPath === path && isPreviewClaimCurrent(previewClaim),
    markForRevalidation: () => {
      fileNeedsRevalidate.add(path);
      boundMapSize(fileNeedsRevalidate, ETAG_REVALIDATE_MAX);
    },
    pane: previewPane,
    path,
    // An unreachable server and a real file error share the error markup;
    // the module decides which message it carries.
    showError: (failure) => {
      if (loadingIndicatorTimer) {
        clearTimeout(loadingIndicatorTimer);
        loadingIndicatorTimer = null;
      }
      disposeActivePluginViews();
      stopFolderHeaderSubscription();
      delete preview.dataset.renderedPath;
      preview.innerHTML = previewErrorHtml(failure.summary, failure.detail);
      finishRetainedPullPage();
    },
  });
}

/**
 * Start the compositor without exposing a temporarily unobserved rejection.
 * The selected render unwraps the result later; an HTTP failure can return
 * first without leaving this independent request as an unhandled promise.
 */
function beginViewCompositionLoad() {
  return window.MetabrowserNavigationRoute.settleNavigationDependency(loadViewComposition());
}

/** @returns {Promise<QuickFileOpenOutcome>} */
async function selectFile(path, preferredViewId, refreshMounted = false) {
  // Folder routes carry a trailing slash and the served root is the empty
  // path, so the route says whether this selection is a folder before its
  // envelope arrives. The placeholder names what is loading.
  var routePath = navigationController.current()?.path;
  var previewClaim = claimPreview("file", {
    folder: path === "" || routePath === `${path}/`,
    path: path,
    viewId: preferredViewId,
  });
  filePreviewClaim = previewClaim;
  var selection = /** @type {Promise<QuickFileOpenOutcome>} */ (
    _perf.measureAsync(
      "selectFile",
      async () => {
        // Always close any prior live stream — switching files (or reopening
        // the same file) starts fresh.
        closeLiveStream();
        // Chunk growth is per file: a fresh selection starts small again so
        // opening a file never inherits the last file's appetite.
        resetTextChunkGrowth();
        awaitedPreviewView = null;
        currentPath = path;
        if (selectFileAbortController) {
          selectFileAbortController.abort();
          selectFileAbortController = null;
        }
        const preview = document.getElementById("preview-pane");
        if (!preview) {
          return {
            message: "Could not display the file. Reload the page to try again.",
            status: "error",
          };
        }
        var retainedPreview = beginPreviewNavigation(previewClaim);
        // The page's View on GitHub link is asked for while its file loads, so it can come
        // with the header (plugin-sdk-views.js, prefetchCounterpart). Only a page whose
        // repository is on github.com draws the button (view-header.js).
        if (window.METABROWSER_REPOSITORY_CONTEXT) {
          window.metabrowser?.prefetchCounterpart?.(location.pathname);
        }
        await settleHoverPrefetchForSelection(path);
        if (currentPath !== path || !isPreviewClaimCurrent(previewClaim)) {
          return { status: "cancelled" };
        }

        // Every file envelope uses the universal compositor. Begin that
        // independent request before /api/file so its transfer and evaluation
        // overlap the payload; renderFile awaits this exact promise and checks
        // the pane claim again before it prepares or mounts anything. Attach a
        // settled-result wrapper now because an HTTP failure may mean this
        // selection never reaches renderFile.
        const viewComposition = beginViewCompositionLoad();
        const renderOptions = { viewComposition, refreshMounted };

        // Three-way cache state:
        //   - hot: in fileCache and not flagged → serve from cache.
        //   - revalidate: in fileCache but flagged (file recently changed in
        //     activity poll) → send If-None-Match, accept 304 to confirm.
        //   - cold: not in fileCache → unconditional fetch.
        const cached = fileCache.get(path);
        const needsRevalidate = fileNeedsRevalidate.has(path);
        const revalidationMarker = needsRevalidate ? fileNeedsRevalidate.capture(path) : null;
        if (cached && !needsRevalidate && !activeFiles.has(path)) {
          try {
            navigationController.canonicalizePath(path, cached.kind === "folder");
            if (!(await renderFile(cached, preferredViewId, previewClaim, renderOptions))) {
              return { status: "cancelled" };
            }
            maybeOpenLiveStream(path, cached);
            return openedFileOutcome(path, cached, preview, previewClaim);
          } catch (err) {
            return fileSelectionFailureOutcome(err, path, cached, preview, previewClaim);
          }
        }

        if (loadingIndicatorTimer) {
          clearTimeout(loadingIndicatorTimer);
        }
        if (!retainedPreview) {
          loadingIndicatorTimer = setTimeout(() => {
            loadingIndicatorTimer = null;
            var loading =
              currentPath === path
                ? previewPlaceholderHtml(previewPane.placeholder(previewClaim))
                : null;
            if (loading === null) {
              return;
            }
            disposeActivePluginViews();
            stopFolderHeaderSubscription();
            delete preview.dataset.renderedPath;
            preview.innerHTML = loading;
            finishRetainedPullPage();
            beginPreviewNavigation(previewClaim);
          }, LOADING_INDICATOR_DELAY_MS);
        }

        selectFileAbortController =
          typeof AbortController !== "undefined" ? new AbortController() : null;
        var selectFileSignal = selectFileAbortController
          ? selectFileAbortController.signal
          : undefined;

        try {
          /** @type {Record<string, string>} */
          const headers = {};
          if (cached && fileETags.has(path)) {
            headers["if-none-match"] = fileETags.get(path);
          }
          // A rejected fetch received no response at all: the server stopped or
          // the connection was refused. Mark it here, where it cannot be
          // confused with an HTTP error or a renderer exception.
          const resp = await fetch(`/api/file?path=${encodeURIComponent(path)}`, {
            headers: headers,
            signal: selectFileSignal,
          }).catch((error) => {
            throw window.MetabrowserNavigationRoute.requestFailure(error);
          });
          if (resp.status === 304 && cached) {
            // Server confirmed the cached payload is still fresh — zero-byte
            // body, render from memory.
            if (currentPath === path && isPreviewClaimCurrent(previewClaim)) {
              fileNeedsRevalidate.settle(path, revalidationMarker);
              if (loadingIndicatorTimer) {
                clearTimeout(loadingIndicatorTimer);
                loadingIndicatorTimer = null;
              }
              navigationController.canonicalizePath(path, cached.kind === "folder");
              if (!(await renderFile(cached, preferredViewId, previewClaim, renderOptions))) {
                return { status: "cancelled" };
              }
              maybeOpenLiveStream(path, cached);
              return openedFileOutcome(path, cached, preview, previewClaim);
            }
            return { status: "cancelled" };
          }
          // `fetch` resolved at the headers, so a server that stops mid-body
          // rejects the read instead. Mark that at the read too.
          const bodyFailure = (error) => {
            throw window.MetabrowserNavigationRoute.responseBodyFailure(error);
          };
          if (!resp.ok) {
            const text = await _perf.measureAsync(
              "apiFile:errorText",
              () => resp.text().catch(bodyFailure),
              responsePerfMeta(resp, path),
            );
            if (resp.status !== 404) {
              console.error("file request failed", resp.status);
            }
            throw Object.assign(new Error(responseErrorDetail(text)), {
              notFound: resp.status === 404,
              summary: responseErrorSummary(text, "Could not open this file."),
            });
          }
          const data = await _perf.measureAsync(
            "apiFile:json",
            () => resp.json().catch(bodyFailure),
            responsePerfMeta(resp, path),
          );
          const responseCommit = window.MetabrowserNavigationRoute.commitFreshFileResponse({
            data,
            etag: resp.headers.get("etag"),
            isCurrent: () => currentPath === path && isPreviewClaimCurrent(previewClaim),
            cacheFile: (fresh) =>
              cachePut(fileCache, path, fresh, CACHE_MAX, evictFileCacheMetadata),
            cacheValidator: (etag) => {
              fileETags.set(path, etag);
              boundMapSize(fileETags, ETAG_REVALIDATE_MAX);
            },
            evictFile: () => fileCache.delete(path),
            evictValidator: () => fileETags.delete(path),
          });
          if (responseCommit === "cancelled") {
            return { status: "cancelled" };
          }
          fileNeedsRevalidate.settle(path, revalidationMarker);
          if (loadingIndicatorTimer) {
            clearTimeout(loadingIndicatorTimer);
            loadingIndicatorTimer = null;
          }
          navigationController.canonicalizePath(path, data.kind === "folder");
          if (!(await renderFile(data, preferredViewId, previewClaim, renderOptions))) {
            return { status: "cancelled" };
          }
          maybeOpenLiveStream(path, data);
          return openedFileOutcome(path, data, preview, previewClaim);
        } catch (err) {
          return fileSelectionFailureOutcome(err, path, cached, preview, previewClaim);
        }
      },
      { path: path, preferred_view: preferredViewId || "" },
    )
  );
  var readySelection = selection.finally(() => {
    if (loadingIndicatorTimer && isPreviewClaimCurrent(previewClaim)) {
      clearTimeout(loadingIndicatorTimer);
      loadingIndicatorTimer = null;
    }
    endPreviewNavigation(previewClaim);
  });
  return _perf.measureAsync("fileNavigation:selectToReady", () => readySelection, {
    path: path,
    preferred_view: preferredViewId || "",
  });
}

/**
 * @param {string} path
 * @param {{kind?: string, logical_ext?: string}} data
 * @param {HTMLElement} preview
 * @param {number} previewClaim
 * @returns {QuickFileOpenOutcome}
 */
function openedFileOutcome(path, data, preview, previewClaim) {
  // An empty folder is content too: its Overview states that it has no files.
  previewPane.settle(previewClaim, "content");
  if (path && data.kind !== "folder") {
    knownFileCatalog?.observeNavigation(path, data.logical_ext || null);
  }
  return { focusTarget: preview, status: "opened" };
}

// ── File rendering ──────────────────────────────────────────────

// Folder navigation targets never ride in inline handlers: an inline
// onclick HTML-decodes its attribute before compiling JavaScript, so a
// filename containing a quote re-opens the string no matter how it was
// HTML-escaped. Buttons carry the raw path in data-nav-dir and one
// delegated listener (installed in init) reads it back via dataset.
function navigateToFolder(path) {
  navigateToPath(path ? `${path}/` : "");
}

// ── Folder header live refresh ──────────────────────────────────
//
// The folder envelope is no-store, so its header aggregates would
// otherwise freeze at first render while the treemap keeps updating.
// While a folder is previewed, inventory-change events touching its
// subtree (deep changes surface via ancestor aggregate upserts)
// trigger a debounced envelope refetch that patches the summary strip
// in place — the server envelope stays the single authority.

/** @type {(() => void) | null} */
var activeFolderHeaderSubscription = null;

function stopFolderHeaderSubscription() {
  if (!activeFolderHeaderSubscription) {
    return;
  }
  activeFolderHeaderSubscription();
  activeFolderHeaderSubscription = null;
}

function startFolderHeaderSubscription(path) {
  stopFolderHeaderSubscription();
  var folderContext = window.metabrowser?.folderContext;
  if (!folderContext) {
    return;
  }
  activeFolderHeaderSubscription = folderContext.subscribe(path, (data) => {
    if (currentPath !== path || data?.kind !== "folder") {
      return;
    }
    var summaryEl = document.querySelector("#preview-pane .folder-header-summary");
    if (summaryEl) {
      var dir = data.dir && typeof data.dir === "object" ? data.dir : null;
      summaryEl.innerHTML = dir ? viewHeaderBuilders().folderHeaderSummaryHtml(dir) : "";
    }
  });
}

function boolData(value) {
  return value === true || value === "true" || value === "1";
}

function viewIsPrintable(view) {
  return boolData(view?.printable);
}

function viewPrintProfile(view) {
  return view?.print_profile || "plain";
}

function viewRenderRuntime(view) {
  return view?.render_runtime || "";
}

function viewMetaAttrs(view) {
  var printable = viewIsPrintable(view) ? "true" : "false";
  var profile = viewPrintProfile(view);
  var runtime = viewRenderRuntime(view);
  var attrs = ` data-printable="${printable}" data-print-profile="${esc(profile)}"`;
  if (runtime) {
    attrs += ` data-render-runtime="${esc(runtime)}"`;
  }
  if (runtime === "kpress") {
    attrs += ' data-kpress-enabled="true"';
  }
  return attrs;
}

// The partial-content notice's Load more runs the shell's text loader by name.
window.MetabrowserPluginHost?.registerLoadMoreAction?.("loadMoreCurrentText", loadMoreCurrentText);

document.addEventListener("metabrowser:view-print-state", () => {
  var preview = document.getElementById("preview-pane");
  if (preview?.dataset.activeView) {
    window.MetabrowserViewComposition.setActiveView(preview, preview.dataset.activeView);
  }
});

/** @type {ReturnType<Window["MetabrowserViewComposition"]["createLifecycle"]> | null} */
var pluginViewLifecycle = null;
/** @type {Readonly<MetabrowserViewHeaderBuilders> | null} */
var viewHeader = null;

/**
 * The view header's builders (view-header.js) over this file's helpers. Its bundle loads
 * with the compositor (loadViewComposition), so only a render, and the live refresh of
 * the folder line a render drew, asks for them.
 */
function viewHeaderBuilders() {
  if (!viewHeader) {
    const header = window.MetabrowserViewHeader;
    if (!header) {
      throw new Error("Metabrowser view header is unavailable");
    }
    viewHeader = header.create({
      esc,
      servedRoot,
      pathBaseName,
      ownedControlAttr,
      mirrorHeading,
      getFileIcon,
      getLogicalName,
      sizeHtml,
      countHtml,
      formatAge,
      activeFiles,
    });
  }
  return viewHeader;
}

async function loadViewComposition() {
  const assets = window.MetabrowserAssets;
  if (!assets) {
    throw new Error("Metabrowser asset loader is unavailable");
  }
  // The line gutter and the SDK's view helpers are one bundle, and the view header
  // another, fetched beside the compositor and not after it: every file view is mounted
  // through here, so its renderer finds them without the plugin loader having to fetch
  // them first.
  await _perf.measureAsync("fileNavigation:viewComposition", () =>
    Promise.all([
      assets.ensureAsset("view-composition"),
      assets.ensureAsset("sdk-views"),
      assets.ensureAsset("view-header"),
    ]),
  );
  const composition = window.MetabrowserViewComposition;
  if (!composition) {
    throw new Error("Metabrowser view compositor is unavailable");
  }
  if (!pluginViewLifecycle) {
    pluginViewLifecycle = composition.createLifecycle({
      onDisposeError(error) {
        console.error("plugin dispose error:", error);
      },
    });
  }
  return Object.freeze({ composition, lifecycle: pluginViewLifecycle });
}

function disposeActivePluginViews() {
  stopFolderHeaderSubscription();
  pluginViewLifecycle?.disposeActive();
}

/** @param {HTMLElement} preview */
function createFilePreviewStage(preview) {
  const stage = document.createElement("div");
  stage.className = "preview-file-stage";
  stage.setAttribute("aria-hidden", "true");
  stage.inert = true;
  preview.appendChild(stage);
  return stage;
}

/**
 * @param {Record<string, any>} data
 * @param {string | undefined} preferredViewId
 * @param {number | null | undefined} claim
 * @param {{
 *   isCurrent?: () => boolean,
 *   onCommit?: () => void,
 *   refreshMounted?: boolean,
 *   viewComposition?: ReturnType<typeof beginViewCompositionLoad>,
 * }} [options]
 * @returns {Promise<boolean>}
 */
async function renderFile(data, preferredViewId, claim, options = {}) {
  // Ownership, not staleness: the Git panel renders into this same pane, so a
  // file render that lost the pane must not paint over it. currentPath cannot
  // express that, because the owner changed rather than the path.
  const renderClaim = claim ?? filePreviewClaim;
  if (renderClaim === null) {
    return false;
  }
  const renderIsCurrent = () =>
    isPreviewClaimCurrent(renderClaim) && (!options.isCurrent || options.isCurrent());
  if (!renderIsCurrent()) {
    return false;
  }
  return _perf.measureAsync(
    `renderFile:${data.kind || data.type || "?"}`,
    async () => {
      const viewCompositionResult = options.viewComposition
        ? await options.viewComposition
        : {
            status: /** @type {"ready"} */ ("ready"),
            value: await loadViewComposition(),
          };
      if (viewCompositionResult.status === "error") {
        throw viewCompositionResult.error;
      }
      const viewComposition = viewCompositionResult.value;
      if (!renderIsCurrent()) {
        return false;
      }
      const compositionKind = data.kind || data.type || "unknown";
      const preview = document.getElementById("preview-pane");
      if (!preview) {
        return false;
      }
      const ctx = {
        path: data.path,
        kind: compositionKind,
        ext: data.ext,
        size: data.size,
        frontmatter: data.frontmatter || {},
        body: typeof data.content === "string" ? data.content : data.body || "",
        raw: data,
        fetchPluginData: window.metabrowser ? window.metabrowser.fetchPluginData : null,
      };
      if (
        options.refreshMounted &&
        compositionKind === "folder" &&
        preview.dataset.renderedPath === data.path
      ) {
        const active = preview.querySelector(':scope > [data-active-view="true"]');
        if (
          active instanceof HTMLElement &&
          (await viewComposition.composition.refresh(active, ctx))
        ) {
          if (!renderIsCurrent()) {
            return false;
          }
          for (const hidden of preview.querySelectorAll(":scope > [data-plugin-view]")) {
            if (hidden !== active && hidden instanceof HTMLElement) {
              await viewComposition.composition.refresh(hidden, ctx);
              if (!renderIsCurrent()) {
                return false;
              }
            }
          }
          window.metabrowser.folderContext.seed(
            data.path,
            /** @type {Parameters<Window["metabrowser"]["folderContext"]["seed"]>[1]} */ (data),
          );
          options.onCommit?.();
          return true;
        }
        if (!renderIsCurrent()) {
          return false;
        }
      }
      var composition = await viewComposition.composition.prepare({
        kind: compositionKind,
        views: Array.isArray(data.views) ? data.views : [],
        preferredViewId: takeAwaitedPreviewView(data.path || "") ?? preferredViewId,
        ensureKindAssets(kind) {
          return _perf.measureAsync(
            "fileNavigation:assets",
            () => window.metabrowser.ensureKindAssets(kind),
            { kind: kind },
          );
        },
        getRegisteredView(kind, viewId) {
          return window.metabrowser.getRegisteredView(kind, viewId);
        },
        isCurrent() {
          return renderIsCurrent();
        },
      });
      if (composition.status === "cancelled") {
        return false;
      }
      const stage = createFilePreviewStage(preview);
      const stagedPluginLifecycle = viewComposition.lifecycle.begin();
      const stagedPluginDisposers = stagedPluginLifecycle.disposers;
      let installed = false;
      let stageCleaned = false;
      const cleanupStage = () => {
        if (stageCleaned) {
          return;
        }
        stageCleaned = true;
        stagedPluginLifecycle.cancel();
        stage.remove();
      };
      cancelPendingFilePreviewStage();
      pendingFilePreviewStageCleanup = cleanupStage;
      try {
        // The view header: a folder's or a file's, one structure (view-header.js).
        let html = "";
        if (data.kind === "folder") {
          const folderData =
            /** @type {Parameters<Window["metabrowser"]["folderContext"]["seed"]>[1]} */ (data);
          html = viewHeaderBuilders().renderFolderHeader(folderData);
          window.metabrowser?.folderContext?.seed(data.path, folderData);
        } else {
          html = viewHeaderBuilders().renderFileHeader(
            /** @type {MetabrowserViewHeaderFile} */ (data),
          );
        }

        // Plugins own every (kind, viewId). The shell mounts empty hosts before
        // calling render(container, ctx); an unclaimed view gets an unavailable
        // message, never a shell-renderer fallback.
        var preparedViews = composition.views;
        var views = preparedViews.map((prepared) => prepared.view);
        // Plugin navigation can preserve a working mode across resources. An
        // unavailable preference falls through to the server default.
        var initialActiveView = composition.initialView;
        var pluginRenders = [];
        if (views && views.length > 0) {
          // One view gets the bar too, so content starts at one height in every file.
          // A tablist, as the navigation and pull request tab bars are. A view's
          // declared letter rides its button for the shell keymap, which reads it
          // only once the bar is committed to the pane, and only a bar of two or more
          // views carries one: a lone tab has no other view to switch to.
          var keyedBar = views.length > 1;
          html += '<div class="tab-bar" role="tablist">';
          for (let i = 0; i < views.length; i++) {
            const view = views[i];
            var isActive = view.id === initialActiveView?.id;
            var viewKey =
              typeof view.key === "string" && view.key ? ` data-view-key="${esc(view.key)}"` : "";
            html +=
              '<button class="tab-btn' +
              (isActive ? " active" : "") +
              '" type="button" role="tab" aria-selected="' +
              (isActive ? "true" : "false") +
              '" data-tab="' +
              esc(view.id) +
              '"' +
              (keyedBar ? viewKey : "") +
              viewMetaAttrs(view) +
              ">" +
              esc(view.label) +
              "</button>";
          }
          html += "</div>";
          for (let i = 0; i < views.length; i++) {
            const view = views[i];
            var pluginView = preparedViews[i].renderer;
            // container_class can be set per-view in the plugin manifest as
            // [[view]].container_class; defaults to "content-body".
            var containerClass = view.container_class || "content-body";
            var hidden = view.id === initialActiveView?.id ? "" : ' style="display:none;"';
            var blockPadding = view.id === "raw" || view.id === "source" ? "padding-block:0;" : "";
            if (blockPadding && !hidden) {
              hidden = ` style="${blockPadding}"`;
            } else if (blockPadding && hidden) {
              hidden = ` style="display:none;${blockPadding}"`;
            }

            if (pluginView) {
              // Empty container; plugin renders into it after innerHTML lands.
              html +=
                '<div class="' +
                containerClass +
                '" data-tab-content="' +
                view.id +
                '" data-plugin-view="' +
                esc(view.id) +
                '"' +
                viewMetaAttrs(view) +
                ' data-active-view="false"' +
                hidden +
                "></div>";
              pluginRenders.push({ tabId: view.id, view: pluginView });
            } else {
              // No plugin registered for this (kind, viewId). Defensive
              // empty-state — should not fire in practice because every
              // kind+view declared in any loaded plugin's manifest is
              // expected to have a matching registerView call.
              html +=
                '<div class="' +
                containerClass +
                '" data-tab-content="' +
                view.id +
                '"' +
                viewMetaAttrs(view) +
                ' data-active-view="false"' +
                hidden +
                '><div class="preview-empty" role="alert">This view is unavailable. Reload the page to try again.</div></div>';
            }
          }
        } else {
          html +=
            '<div class="tab-bar" aria-hidden="true"><span class="tab-btn tab-slot">&nbsp;</span></div>';
          if (data.type === "binary") {
            html += `<div class="content-body"><div class="preview-empty">No preview is available for this binary file (${formatSize(data.size || 0)}).</div></div>`;
          } else if (data.type === "error") {
            html += `<div class="content-body">${previewErrorHtml("Could not preview this file.", data.error)}</div>`;
          }
        }

        _perf.measure(
          "renderFile:mount",
          () => {
            stage.innerHTML = html;
            stage.dataset.renderedPath = data.path || "";
          },
          filePerfMeta(data, { html_chars: html.length }),
        );
        // The View on GitHub button in the header's corner, which view-header.js marks on
        // a page whose repository is on github.com; the server says whether this page has
        // a counterpart (plugin-sdk-views.js, mountCounterpart).
        const counterpartCorner = stage.querySelector(".view-header-end[data-counterpart]");
        if (counterpartCorner) {
          void window.metabrowser?.mountCounterpart?.(counterpartCorner, location.pathname);
        }
        viewComposition.composition.setActiveView(stage, initialActiveView?.id ?? null);

        // The stage is connected so renderers can measure layout, but remains
        // transparent and inert while the prior useful surface stays visible.
        // The active renderer and its optional readiness promise settle before
        // the shell transfers the stage's children into the preview.
        /** @type {(() => Promise<unknown>) | null} */
        let mountInitialView = null;
        if (pluginRenders?.length) {
          for (var pi = 0; pi < pluginRenders.length; pi++) {
            var pr = pluginRenders[pi];
            var container = stage.querySelector(`[data-plugin-view="${pr.tabId}"]`);
            if (!(container instanceof HTMLElement)) {
              continue;
            }
            const mount = (
              (target, pluginView) => () =>
                viewComposition.composition.mount(target, pluginView, ctx, stagedPluginDisposers, {
                  afterMount: scheduleHighlightCode,
                  onError(error) {
                    console.error("plugin render error:", error);
                  },
                })
            )(container, pr.view);
            if (initialActiveView && pr.tabId === initialActiveView.id) {
              mountInitialView = mount;
            } else {
              container._metabrowserMount = () => {
                void mount();
              };
            }
          }
        }

        // The staged bar takes a choice before the first view holds the paint: a tab
        // chosen in the hold is the one the commit brings to the front (mb-s588).
        _perf.measure(
          "initTabs",
          () => viewComposition.composition.bindTabs(stage),
          filePerfMeta(data),
        );
        if (mountInitialView && initialActiveView) {
          await _perf.measureAsync(
            "fileNavigation:activeView",
            mountInitialView,
            filePerfMeta(data, { view: initialActiveView.id }),
          );
        }
        const arrivalContent =
          stage.querySelector('[data-active-view="true"]') ?? stage.querySelector(".content-body");
        // Shown once the faces its text is set in land (view-composition.js#settleFaces).
        const facesSettled = viewComposition.composition.settleFaces(arrivalContent ?? stage);
        if (facesSettled) {
          await facesSettled;
        }
        if (!renderIsCurrent()) {
          return false;
        }
        const frontViewId = stage.dataset.activeView || null;
        const replacementNodes = Array.from(stage.childNodes);
        stopFolderHeaderSubscription();
        if (
          !stagedPluginLifecycle.commit(() => {
            preview.replaceChildren(...replacementNodes);
            // The view tab letters and the header's keys move with what the pane
            // commits, here and never while it is staged; a cancelled stage registered
            // nothing, so nothing of the keymap goes into stagedPluginDisposers, which
            // cancel() also runs.
            shellKeymap?.commitViewTabs(shellKeymap.committedBar());
            finishRetainedPullPage();
            options.onCommit?.();
          })
        ) {
          return false;
        }
        installed = true;
        if (pendingFilePreviewStageCleanup === cleanupStage) {
          pendingFilePreviewStageCleanup = null;
        }
        preview.dataset.renderedPath = data.path || "";
        viewComposition.composition.setActiveView(preview, frontViewId);
        if (data.kind === "folder") {
          startFolderHeaderSubscription(data.path);
        }
        scheduleHighlightCode(preview);
        const arrived =
          preview.querySelector(':scope > [data-active-view="true"]') ?? arrivalContent;
        if (arrived instanceof HTMLElement) {
          animatePreviewContentArrival(arrived);
        }
        await measureNextPaint("fileNavigation:paintReady", filePerfMeta(data));
        return true;
      } finally {
        if (!installed) {
          if (pendingFilePreviewStageCleanup === cleanupStage) {
            pendingFilePreviewStageCleanup = null;
          }
          cleanupStage();
        }
      }
    },
    filePerfMeta(data),
  );
}

// The agent-log built-in plugin calls toggleEvent from its delegated click
// listener on each log event header; it sits on window so the plugin reaches
// it. Lazy-highlight on first expand keeps initial render cheap on logs with
// thousands of events.

// biome-ignore lint/correctness/noUnusedVariables: called by the agent-log plugin through window.
function toggleEvent(header) {
  var parent = header.parentElement;
  parent.classList.toggle("expanded");
  if (parent.classList.contains("expanded")) {
    // First-expand mount: agent-log emits log-event-raw containers
    // empty and registers mountLogEventRaw on window. An object payload
    // is the structured plugin's collapsible tree, drawn once that plugin
    // loads (a flat JSON block if it cannot); a string is a flat block.
    var rawEl = parent.querySelector(".log-event-raw");
    if (
      rawEl &&
      window.metabrowserAgentLog &&
      typeof window.metabrowserAgentLog.mountLogEventRaw === "function"
    ) {
      window.metabrowserAgentLog.mountLogEventRaw(rawEl);
    }
    scheduleHighlightCode(parent);
  }
}

// ── Charts loading + rendering ──────────────────────────────────

// Delegated handlers for header navigation controls. Copyable values use
// the SDK-owned data-mb-copy contract, so path and revision identifiers
// share clipboard and feedback behavior without inline handlers.
/** @param {Event} e */
function onHeaderNavigationClick(e) {
  var origin = eventTargetElement(e);
  if (!origin) {
    return;
  }
  var navBtn = /** @type {HTMLElement | null} */ (origin.closest("[data-nav-dir]"));
  if (navBtn && isOwnedControl(navBtn) && !navBtn.hasAttribute("disabled")) {
    navigateToFolder(navBtn.dataset.navDir ?? "");
  }
}
document.addEventListener("click", onHeaderNavigationClick);

// ── Tab switching ───────────────────────────────────────────────

// A view asked for by name while its file was loading, before it had a tab bar. The
// render that stages the file opens in it, and the next selection forgets it.
/** @type {{path: string, viewId: string} | null} */
var awaitedPreviewView = null;

/** @param {string} path */
function takeAwaitedPreviewView(path) {
  var awaited = awaitedPreviewView;
  awaitedPreviewView = null;
  return awaited?.path === path ? awaited.viewId : undefined;
}

/**
 * Select a tab of the file the preview pane shows or is staging, as a click on it does,
 * unless it is already selected (view-composition.js#selectTab). A view the file lacks
 * has no tab to select.
 *
 * @param {string} path
 * @param {string | null} tabId
 */
function showPreviewTab(path, tabId) {
  var preview = document.getElementById("preview-pane");
  if (!tabId || !preview) {
    return;
  }
  var shown = preview.dataset.renderedPath === path ? preview : null;
  var staged = window.MetabrowserViewComposition?.stagedFile(preview, path) ?? null;
  if (!shown && !staged) {
    var held = previewPane.snapshot();
    if (held.phase === "loading" && held.path === path) {
      awaitedPreviewView = { path, viewId: tabId };
    }
    return;
  }
  // The pane's own bar first: selecting there selects in a stage of the same file.
  for (const host of [shown, staged]) {
    var button = host && queryHtml(`:scope > .tab-bar > .tab-btn[data-tab="${tabId}"]`, host);
    var bar = button?.parentElement;
    if (button && bar && !button.classList.contains("active")) {
      selectPreviewTab(bar, tabId);
    }
  }
}

/**
 * Select one tab of a view tab bar, as its click and its letter key do.
 *
 * @param {HTMLElement} bar
 * @param {string} tabId
 */
function selectPreviewTab(bar, tabId) {
  return window.MetabrowserViewComposition.selectTab(bar, tabId);
}

// ── Pane resizing ───────────────────────────────────────────────

function initPaneResize(handleId, paneSelector, minWidth, maxWidth) {
  var handle = document.getElementById(handleId);
  var pane = queryHtml(paneSelector);
  if (!handle || !pane) {
    return;
  }
  const resizePane = pane;
  var isResizing = false,
    startX = 0,
    startWidth = 0;

  handle.addEventListener("mousedown", (e) => {
    isResizing = true;
    startX = e.clientX;
    startWidth = resizePane.offsetWidth;
    document.body.classList.add("resizing");
    e.preventDefault();
  });
  document.addEventListener("mousemove", (e) => {
    if (!isResizing) {
      return;
    }
    var w = Math.max(minWidth, startWidth + e.clientX - startX);
    if (maxWidth) {
      w = Math.min(maxWidth, w);
    }
    resizePane.style.width = `${w}px`;
  });
  document.addEventListener("mouseup", () => {
    if (isResizing) {
      isResizing = false;
      document.body.classList.remove("resizing");
    }
  });
}

// ── Activity polling ────────────────────────────────────────────

// ── Live tail (SSE) ───────────────────────────────────────────
//
// When the user opens a JSONL whose pid is still alive, we subscribe
// to /api/stream and append new events to the rendered log as they
// arrive. Activity polling stays — it owns tree decoration. SSE is
// purely additive: if EventSource isn't supported, the existing
// "drop cache when pid dies, refetch on next click" path keeps
// working.

function closeLiveStream() {
  if (currentLiveStream) {
    try {
      currentLiveStream.close();
    } catch (_e) {
      /* ignore */
    }
    currentLiveStream = null;
  }
}

// Park the live tail (createPageConnections): reopened from the cursor it reached.
function parkLiveStream() {
  if (!currentLiveStream) {
    return null;
  }
  var path = currentPath;
  closeLiveStream();
  return () => {
    if (currentPath === path) {
      maybeOpenLiveStream(path, fileCache.get(path));
    }
  };
}

function maybeOpenLiveStream(path, data) {
  // Subscribe only if (a) the payload is a JSONL log, and (b) the
  // file's writer is still alive per the activity poll. Anything else
  // is wasted overhead — and the server would close immediately on a
  // dead writer anyway.
  if (data?.type !== "jsonl") {
    return;
  }
  if (currentLiveStream) {
    return;
  }
  var info = activeFiles.get(path);
  if (info === undefined || info.pid_alive === false) {
    return;
  }
  openLiveStream(path, data.bytes_read || 0);
}

function openLiveStream(path, startCursor) {
  closeLiveStream();
  if (typeof EventSource === "undefined") {
    return;
  }
  if (pageConnections?.suspended()) {
    pageConnections.defer(() => {
      if (currentPath === path) {
        maybeOpenLiveStream(path, fileCache.get(path));
      }
    });
    return;
  }
  var url = `/api/stream?path=${encodeURIComponent(path)}&cursor=${startCursor || 0}`;
  var es = new EventSource(url);
  currentLiveStream = es;

  es.addEventListener("append", (msg) => {
    if (currentPath !== path || currentLiveStream !== es) {
      return;
    }
    var batch;
    try {
      batch = JSON.parse(msg.data);
    } catch (_e) {
      return;
    }
    appendLiveEvents(path, batch);
  });

  es.addEventListener("closed", () => {
    if (currentPath !== path || currentLiveStream !== es) {
      return;
    }
    closeLiveStream();
    flagRunEndedBadge();
  });

  es.onerror = () => {
    // A deleted file returns HTTP 404 on restore, which permanently closes
    // EventSource. Transient failures remain under browser reconnect control.
    if (currentLiveStream === es && es.readyState === 2) {
      closeLiveStream();
      flagRunEndedBadge();
    }
  };
}

// Whether a live tail's rows went undrawn because the agent-log renderers did not load,
// which is said once on the console rather than for every batch.
var liveEventsUndrawnLogged = false;

function appendLiveEvents(path, batch) {
  return _perf.measureAsync(
    "appendLiveEvents",
    async () => {
      var cached = fileCache.get(path);
      if (!cached || !Array.isArray(batch.events)) {
        return;
      }
      // Extend the in-memory event list and the byte cursor in place so a
      // later "needs revalidation" cycle starts from the right point.
      for (var i = 0; i < batch.events.length; i++) {
        cached.events.push(batch.events[i]);
      }
      if (typeof batch.cursor === "number") {
        cached.bytes_read = batch.cursor;
      }
      // Append to the currently-rendered log tab if it's visible. Charts are
      // not extended: they show the events there were when the file loaded.
      const logPane = queryHtml('[data-tab-content="log"]');
      if (logPane && logPane.style.display !== "none") {
        var startIdx = cached.events.length - batch.events.length;
        // The agents plugin's agent-log renderers, which drew this pane, export
        // renderLogEvent. Returning the load makes the measure cover the rows' render, not
        // only the bookkeeping.
        return window.metabrowser.plugins
          .load("agents")
          .then((agents) => agents.loadLogRenderers())
          .then(
            (agentLog) => {
              var tail = "";
              for (var j = 0; j < batch.events.length; j++) {
                tail += agentLog.renderLogEvent(logPane, batch.events[j], startIdx + j);
              }
              logPane.insertAdjacentHTML("beforeend", tail);
            },
            (error) => {
              if (!liveEventsUndrawnLogged) {
                liveEventsUndrawnLogged = true;
                console.warn(
                  "metabrowser: live events were not drawn: agent-log did not load",
                  error,
                );
              }
            },
          );
      }
    },
    {
      path: path,
      events_appended: batch && Array.isArray(batch.events) ? batch.events.length : 0,
      cursor: batch && typeof batch.cursor === "number" ? batch.cursor : null,
    },
  );
}

function flagRunEndedBadge() {
  var badge = document.querySelector(".file-header-badge.badge-live");
  if (badge) {
    badge.className = "file-header-badge badge-completed";
    badge.textContent = "Run ended";
  }
}

// ── FileStore + /api/events EventSource ────────────────────────
// arch-live-delivery.md, "The Browser's Stores" and "Recovery".
var fileStore = new Map(); // path -> FsEntry
var fileStoreSubscribers = [];
var inventoryEventSource = null;
var lastInventorySnapshot = null;
var catalogFeedCanStart = false;
function isGitRevisionSource() {
  return window.METABROWSER_SOURCE_KIND === "git_revision";
}
// A revision whose Git cannot read file ages has no Modified within and no By age.
var noFileAges = window.METABROWSER_FILE_AGES === false;
var fileAgesState = "";
// Each response says how the read of ages stands; revision-ages.js loads when it is not `ready`.
function observeFileAges(ages, undated) {
  var before = fileAgesState;
  fileAgesState = ages?.state ?? "";
  if ((before === "dating") !== (fileAgesState === "dating")) {
    refreshFilterTallies();
  }
  if (window.MetabrowserRevisionAges) {
    window.MetabrowserRevisionAges.track(ages, undated);
  } else if (ages && ages.state !== "ready") {
    void window.MetabrowserAssets?.ensureAsset("revision-ages").then(() =>
      window.MetabrowserRevisionAges?.track(ages, undated),
    );
  }
}
// The ages landed, or the header's Refresh asked (static/refresh-plan.js): the tree and the
// file or folder the pane holds are read and drawn again, in the view the reader is on, a
// Markdown file's Source say, as Load more keeps it. Settles when both are drawn.
function rereadFiles() {
  subtreeCache.clear();
  fileCache.clear();
  var tree = loadTree({ reconcileMountedRoot: true });
  if (filesPanelUsesRecentSource()) {
    loadRecent(currentRecentFilterCursor());
  }
  var held = previewPane.snapshot();
  var shownView = document.getElementById("preview-pane")?.dataset.activeView || undefined;
  return Promise.all([
    tree,
    held.owner === "file" && held.path !== null && selectFile(held.path, shownView, true),
  ]);
}
window.addEventListener("metabrowser:file-ages-landed", rereadFiles);
// The startup crawl establishes the navigation baseline. Its snapshot and
// incremental walker upserts are not user-visible file changes, so newly
// mounted rows stay neutral until the first terminal inventory event. A
// completed on-connect snapshot arms the same policy after it has been applied.
var inventoryChangeHighlightingActive = false;

// Instrumented at the batch, not per entry: wrapping applyCellPatch itself
// would emit one span per file and charge the measurement more than the work.
// The entry count rides along as meta so the span can be read against the size
// of the batch that produced it -- which is the whole question in H58, since a
// pass whose cost tracks the data is the thing that has to stop.
function fileStoreApplySnapshot(scope, entries) {
  return _perf.measure(
    "fileStoreApplySnapshot",
    () => fileStoreApplySnapshotInner(scope, entries),
    { entries: entries.length, work_items: entries.length },
  );
}

function fileStoreApplySnapshotInner(scope, entries) {
  // SSE snapshots are unfiltered. Preserve the server-filtered folder rows
  // and aggregates until their authoritative filtered tree response arrives.
  var filtered = filterState && filterHasConstraints(filterState.get());
  // A baseline or reconnect snapshot is another observation made after an
  // in-flight Recent request began. Even an empty snapshot can represent
  // removals, so it invalidates that response like a nonempty fs.change batch.
  recentContinuity.dirtyActiveRequest();
  groupsPrefetch.markChanged();
  // Atomic apply: rebuild the store from this snapshot before
  // notifying any subscriber, so derived views never see a
  // half-empty state.
  subtreeCache.clear();
  subtreeRequests.clear();
  for (const path of fileCache.keys()) {
    fileNeedsRevalidate.add(path);
  }
  knownFileCatalog?.observeEventSnapshot(entries);
  window.MetabrowserNavigationRoute.replaceFileSnapshot(fileStore, entries, {
    install: (next) => {
      fileStore = next;
    },
    retire: (path) => {
      activeFiles.delete(path);
      _removeDeferredTreePageEntries(path);
      _removeRenderedRowsImmediately(path);
    },
    upsert: (entry) => {
      if (!filtered) {
        applyCellPatch(entry, false);
      }
      _mirrorActiveFromFsEntry(entry);
    },
  });
  window.metabrowserDirectoryTotalsStore?.applySnapshot(entries);
  if (filtered && !filesPanelUsesRecentSource()) {
    void loadTree({ reconcileMountedRoot: true });
  } else if (filesPanelUsesGroupedSource()) {
    requestGroupedRefresh();
  } else if (!filtered) {
    retryFailedExpandedSubtrees();
  }
  notifyFileStoreSubscribers({ kind: "snapshot", scope: scope });
}

function fileStoreApplyChange(ops) {
  return _perf.measure("fileStoreApplyChange", () => fileStoreApplyChangeInner(ops), {
    ops: ops.length,
    work_items: ops.length,
  });
}

function fileStoreApplyChangeInner(ops) {
  if (ops.length > 0) {
    recentContinuity.dirtyActiveRequest();
    // A grouping asked for ahead of a change answers for the files as they were: a choice
    // still takes it, and refreshes after (createGroupsPrefetch).
    groupsPrefetch.markChanged();
  }
  invalidateSubtreeCaches(ops);
  invalidateFilePreviews(ops);
  quickFileCatalogFeed?.onEventChange(ops);
  // Decide the whole Recent overlay transition before FileStore mutates. The
  // production model needs the pre-batch row type to distinguish a file that
  // became a directory from ordinary directory aggregate traffic.
  var recentEffect = null;
  if (
    recentEverLoaded &&
    currentRecentWindow &&
    filterState &&
    ops.length > 0 &&
    recentViewOwnsCurrentCursor()
  ) {
    recentEffect = treeFilterModel.applyRecentChangeBatch(recentBaseEntries, ops, {
      filterState: filterState,
      limit: RECENT_LIMIT,
      nowSec: Date.now() / 1000,
      previousEntries: fileStore,
      state: filterState.get(),
      truncated: recentTruncated,
    });
  }
  for (var i = 0; i < ops.length; i++) {
    var op = ops[i];
    if (op.op === "upsert") {
      fileStore.set(op.entry.path, op.entry);
      // Patch any rendered cell for this path; insert a new row if
      // the parent is rendered + expanded. Idempotent.
      applyCellPatch(op.entry, inventoryChangeHighlightingActive);
      _mirrorActiveFromFsEntry(op.entry);
    } else if (op.op === "remove") {
      fileStore.delete(op.path);
      activeFiles.delete(op.path);
      _removeDeferredTreePageEntries(op.path);
      // Remove rendered rows in every tab panel; also drops the
      // dir's `.tree-children` container so descendant rows go
      // with it. Server's bulk-remove op already lists each
      // descendant path, but we drop them here too for defensive
      // idempotence against partial deliveries.
      _removeRenderedRows(op.path);
    }
  }
  if (ops.length > 0 && filesPanelUsesGroupedSource()) {
    requestGroupedRefresh();
  }
  if (recentEffect) {
    recentTruncated = recentEffect.truncated;
  }
  if (recentEffect?.needsAuthoritativeRepair) {
    markRecentTotalAsRetainedLowerBound(recentEffect.retainedLowerBound ?? 0);
    scheduleRecentAuthoritativeRefetch();
  }
  window.metabrowserDirectoryTotalsStore?.applyChange(ops);
  notifyFileStoreSubscribers({ kind: "change", ops: ops });
}

function invalidateFilePreviews(ops) {
  const changed = new Set();
  for (const op of ops) {
    const path = op.op === "upsert" ? op.entry.path : op.path;
    const previous = fileStore.get(path);
    if (
      op.op === "remove" ||
      !previous ||
      previous.type !== op.entry.type ||
      previous.size !== op.entry.size ||
      previous.mtime_ns !== op.entry.mtime_ns ||
      op.entry.type === "dir"
    ) {
      changed.add(path);
    }
  }
  // The shallow event scope reports deep changes through ancestor aggregates.
  // Check only retained/in-flight previews; never scan the whole file catalog.
  for (const path of new Set([...fileCache.keys(), currentPath, hoverPrefetchPath])) {
    if (!path) {
      continue;
    }
    let ancestor = path;
    while (true) {
      if (changed.has(ancestor)) {
        fileNeedsRevalidate.add(path);
        break;
      }
      if (!ancestor) {
        break;
      }
      ancestor = ancestor.includes("/") ? ancestor.slice(0, ancestor.lastIndexOf("/")) : "";
    }
  }
}

// Mirror entry.active + labels.pid_alive into activeFiles, the
// single source of "is this file being written?" read by badge
// rendering, stale-cache eviction in selectFile, and live-stream
// gating in maybeOpenLiveStream. Active→inactive flips invalidate
// the per-file caches so the next view reflects the now-static
// file; inactive→active flips switch the header badge to "Live"
// and optionally open the live stream.
function _mirrorActiveFromFsEntry(entry) {
  if (entry.type !== "file") {
    return;
  }
  var pidLabel = null;
  if (entry.labels?.length) {
    for (var i = 0; i < entry.labels.length; i++) {
      var pair = entry.labels[i];
      if (pair[0] === "pid_alive") {
        pidLabel = pair[1] === "1";
        break;
      }
    }
  }
  var wasActive = activeFiles.has(entry.path);
  if (entry.active) {
    activeFiles.set(entry.path, { pid_alive: pidLabel });
    refreshActivityBadge(entry.path);
    // Inactive→active for the currently viewed file: switch the
    // header badge to "Live" and open the live stream if not
    // already running.
    if (!wasActive && currentPath === entry.path) {
      var badge = document.querySelector(".file-header-badge.badge-running");
      if (badge) {
        badge.className = "file-header-badge badge-live";
        badge.textContent = "Live";
      }
      var cachedData = fileCache.get(currentPath);
      if (cachedData && !currentLiveStream) {
        maybeOpenLiveStream(currentPath, cachedData);
      }
    }
  } else if (wasActive) {
    activeFiles.delete(entry.path);
    refreshActivityBadge(entry.path);
    // Active→inactive for the currently viewed file: flag the file cache so
    // the next view reflects the now-frozen content.
    if (currentPath === entry.path) {
      fileNeedsRevalidate.add(currentPath);
      boundMapSize(fileNeedsRevalidate, ETAG_REVALIDATE_MAX);
      if (!currentLiveStream) {
        selectFile(currentPath);
      }
    }
  }
}

// Re-render the activity affordances for a single path:
//   * ``.file-active`` / ``.pid-dead`` row classes (the
//     existing CSS uses these to highlight the row).
//   * ``.tree-item-activity`` inner dot span.
//
// Addressed by data-path so the same path on both Files and
// Recent rows updates simultaneously.
function refreshActivityBadge(path) {
  var safe = escapePathForSelector(path);
  var rows = queryHtmlAll(`.tree-file[data-path="${safe}"]`);
  if (!rows.length) {
    return;
  }
  var info = activeFiles.get(path);
  rows.forEach((row) => {
    if (info) {
      row.classList.add("file-active");
      if (info.pid_alive === false) {
        row.classList.add("pid-dead");
      } else {
        row.classList.remove("pid-dead");
      }
    } else {
      row.classList.remove("file-active", "pid-dead");
    }
    var span = row.querySelector(".tree-item-activity");
    if (!span) {
      return;
    }
    if (!info) {
      span.innerHTML = "";
      return;
    }
    var pidClass = "";
    if (info.pid_alive === true) {
      pidClass = " pid-alive";
    } else if (info.pid_alive === false) {
      pidClass = " pid-dead";
    }
    span.innerHTML = `<span class="activity-dot${pidClass}"></span>`;
  });
}

function notifyFileStoreSubscribers(evt) {
  for (var i = 0; i < fileStoreSubscribers.length; i++) {
    try {
      fileStoreSubscribers[i](evt);
    } catch (_e) {
      /* isolate listener failure */
    }
  }
  // Re-dispatch as a DOM event so SDK consumers (watchRollup) observe
  // inventory activity without reaching into shell internals. ``paths``
  // is null for snapshot/resync (treat as "anything may have changed").
  var changedPaths = null;
  if (evt && Array.isArray(evt.ops)) {
    changedPaths = [];
    for (var oi = 0; oi < evt.ops.length; oi++) {
      var op = evt.ops[oi];
      var opPath = op && (op.entry?.path ?? op.path);
      if (typeof opPath === "string") {
        changedPaths.push(opPath);
      }
    }
  }
  window.dispatchEvent(
    new CustomEvent("metabrowser:inventory-change", {
      detail: { kind: evt ? evt.kind : "", paths: changedPaths },
    }),
  );
}

// Pure function: derive the patched cell HTML for a single
// FsEntry. Returns separate directory, symlink, and file shapes;
// applyCellPatch picks the matching DOM target.
//
// Directory aggregates, file updates, inserts, and removals all use this
// path. See docs/project/architecture/arch-live-delivery.md#the-browsers-stores for the
// contract, and the realtime-debugging guide for following an update layer by layer.
function computeCellPatch(entry, options) {
  if (entry.type === "dir") {
    var dirMtimeSec = entry.newest_mtime_ns
      ? entry.newest_mtime_ns / 1e9
      : entry.total_files === null
        ? null
        : 0;
    var totalSize = entry.total_size === undefined ? null : entry.total_size;
    var totalFiles = entry.total_files == null ? null : entry.total_files;
    return {
      kind: "dir",
      sizeHtml: treeDirChipHtml(totalFiles, totalSize, options),
      ageHtml: formatAge(dirMtimeSec),
      tipFiles: nullableDataValue(totalFiles),
      tipSize: nullableDataValue(totalSize),
      tipMtime: nullableDataValue(dirMtimeSec),
    };
  }
  if (entry.type === "symlink") {
    var linkMtimeSec = entry.mtime_ns ? entry.mtime_ns / 1e9 : 0;
    return {
      kind: "symlink",
      sizeHtml: "",
      ageHtml:
        '<span class="tree-item-age">' +
        formatAge(linkMtimeSec) +
        '</span><span class="tree-item-activity"></span>',
      tipSize: null,
      tipMtime: linkMtimeSec,
      active: false,
    };
  }
  // File entry: size + age + active class.
  var fileMtimeSec = entry.mtime_ns ? entry.mtime_ns / 1e9 : 0;
  return {
    kind: "file",
    sizeHtml: sizeHtml(entry.size, "tree-item-size"),
    ageHtml:
      '<span class="tree-item-age">' +
      formatAge(fileMtimeSec) +
      '</span><span class="tree-item-activity"></span>',
    tipSize: nullableDataValue(entry.size),
    tipMtime: fileMtimeSec,
    active: !!entry.active,
  };
}

// Sort key matching the server's _dir_tree / walk_tree convention:
// dirs first, then by name. Used both for inserting new rows in
// sorted position AND for picking the right insert sibling.
function _treeSortKey(node) {
  // node is a { type, name } shape — the FsEntry has both fields.
  return [node.type === "dir" ? 0 : 1, (node.name || "").toLowerCase()];
}

function _treeKeyCmp(a, b) {
  if (a[0] !== b[0]) {
    return a[0] - b[0];
  }
  return a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0;
}

// Build the HTML for one entry — same shape as renderTreeNodes
// emits, narrowed to a single row. Used for live inserts. Mirrors
// the renderTreeNodes structure exactly so an insert is
// indistinguishable from a row that was server-rendered. Newly
// inserted dirs always get a collapsed, empty `.tree-children`
// sibling — the user can expand to lazy-load.
function _buildRowHtml(entry, options) {
  var name = window.MetabrowserNavigationRoute.displayPath(entry.name || "");
  var level = options?.level || 1;
  var position = options?.position || 1;
  var setSize = options?.setSize || 1;
  var muted = "";
  if (entry.gitignored) {
    muted += " tree-item-gitignored";
  }
  if (entry.type === "dir") {
    var dirChip = treeDirChipHtml(entry.total_files, entry.total_size, options);
    var dirAge = formatAge(entry.newest_mtime_ns ? entry.newest_mtime_ns / 1e9 : 0);
    var hasPotentialChildren = entry.empty !== true;
    var folderLabelId = treeDomId("tree-label", `folder:${entry.path}`);
    var groupId = hasPotentialChildren ? treeDomId("tree-group", entry.path) : "";
    var folderAttributes = treeItemAttributes({
      kind: "folder",
      path: entry.path,
      level: level,
      position: position,
      setSize: setSize,
      expanded: hasPotentialChildren ? false : undefined,
      ownedGroupId: groupId,
      labelId: folderLabelId,
    });
    return (
      '<div class="tree-item tree-folder disclosure-toggle collapsed' +
      muted +
      '"' +
      folderAttributes +
      ' data-action="select-dir" data-path="' +
      esc(entry.path) +
      '" data-tip-type="dir" data-tip-name="' +
      esc(name) +
      '" data-tip-files="' +
      nullableDataValue(entry.total_files) +
      '" data-tip-size="' +
      nullableDataValue(entry.total_size) +
      '" data-tip-mtime="' +
      nullableDataValue((entry.newest_mtime_ns || 0) / 1e9) +
      '">' +
      '<span class="tree-toggle">' +
      ICONS.toggle +
      "</span>" +
      '<span class="tree-item-name" id="' +
      folderLabelId +
      '">' +
      esc(name) +
      "</span>" +
      '<span class="tree-item-age-inline">' +
      dirAge +
      "</span>" +
      dirChip +
      "</div>" +
      (hasPotentialChildren
        ? treeChildGroupStartHtml(groupId, level + 1, false) +
          '<div class="tree-lazy-placeholder mb-delayed-loading" data-tree-lazy-stub' +
          ' role="status" aria-label="Loading">' +
          '<span class="spinner spinner-sm" aria-hidden="true"></span>' +
          "</div>" +
          "</div>"
        : "")
    );
  }
  if (entry.type === "symlink") {
    var linkAge = formatAge(entry.mtime_ns ? entry.mtime_ns / 1e9 : 0);
    var linkLabelId = treeDomId("tree-label", `symlink:${entry.path}`);
    var linkAttributes = treeItemAttributes({
      kind: "symlink",
      path: entry.path,
      level: level,
      position: position,
      setSize: setSize,
      selected: currentPath === entry.path,
      labelId: linkLabelId,
    });
    return (
      '<div class="tree-item tree-symlink' +
      muted +
      '"' +
      linkAttributes +
      ' data-action="select" data-path="' +
      esc(entry.path) +
      '" data-tip-type="symlink" data-tip-name="' +
      esc(name) +
      '" data-tip-mtime="' +
      (entry.mtime_ns || 0) / 1e9 +
      '">' +
      '<span class="tree-item-icon">' +
      ICONS.fileSymlink +
      "</span>" +
      '<span class="tree-item-name" id="' +
      linkLabelId +
      '">' +
      esc(name) +
      "</span>" +
      '<span class="tree-item-age-inline"><span class="tree-item-age">' +
      linkAge +
      '</span><span class="tree-item-activity"></span></span>' +
      "</div>"
    );
  }
  var fi = getFileIcon(getLogicalName(entry));
  var fileAge = formatAge(entry.mtime_ns ? entry.mtime_ns / 1e9 : 0);
  var fileLabelId = treeDomId("tree-label", `file:${entry.path}`);
  var fileAttributes = treeItemAttributes({
    kind: "file",
    path: entry.path,
    level: level,
    position: position,
    setSize: setSize,
    selected: currentPath === entry.path,
    labelId: fileLabelId,
  });
  return (
    '<div class="tree-item tree-file' +
    muted +
    '"' +
    fileAttributes +
    ' data-action="select" data-path="' +
    esc(entry.path) +
    '" data-tip-type="file" data-tip-name="' +
    esc(name) +
    '"' +
    dataTipNumberAttr("size", entry.size) +
    dataTipNumberAttr("mtime", entry.mtime_ns ? entry.mtime_ns / 1e9 : undefined) +
    // Live-inserted rows need the filter's extension too, or a row
    // arriving over the event stream would be judged on its last
    // suffix while the rendered ones are judged on the index's.
    (entry.ext ? ` data-ext="${esc(entry.ext)}"` : "") +
    ">" +
    '<span class="tree-item-icon file-identity-icon ' +
    fi.cls +
    (fi.style ? `" style="${esc(fi.style)}` : "") +
    '">' +
    fi.svg +
    "</span>" +
    '<span class="tree-item-name" id="' +
    fileLabelId +
    '">' +
    esc(name) +
    "</span>" +
    '<span class="tree-item-age-inline">' +
    '<span class="tree-item-age">' +
    fileAge +
    "</span>" +
    '<span class="tree-item-activity"></span>' +
    "</span>" +
    sizeHtml(entry.size, "tree-item-size") +
    "</div>"
  );
}

// Find the rendered child container under which an entry's
// siblings live — for root entries this is `#tab-files`; for
// entries under a folder it's the `.tree-children` sibling of the
// `.tree-folder`. Hidden children that already mounted stay current too.
// A collapsed lazy stub waits for expansion and a fresh subtree read.
function _findChildContainerFor(parentRel, panelEl) {
  if (!parentRel) {
    return treeRootForPanel(panelEl);
  }
  var folder = panelEl.querySelector(
    `.tree-folder[data-path="${escapePathForSelector(parentRel)}"]`,
  );
  if (!folder) {
    return null;
  }
  var children = folder.nextElementSibling;
  if (!children?.classList.contains("tree-children")) {
    return null;
  }
  if (
    !folder.classList.contains("expanded") &&
    children.querySelector(":scope > .tree-lazy-placeholder")
  ) {
    return null;
  }
  return children;
}

// The container's deferred page that holds *path*, or with no path its last one. A
// container has one "more" row at its end, and a reveal can leave another above the page
// it drew (mountTreePageAt).
function _deferredTreePageForContainer(container, path) {
  var sentinels = Array.from(
    queryHtmlAll(":scope > .tree-page-more[data-page-id]", container),
  ).reverse();
  for (const sentinel of sentinels) {
    var pageId = sentinel.dataset.pageId;
    var page = pendingTreePages.get(pageId);
    if (
      page &&
      (path === undefined ||
        page.nodes.some((/** @type {{path: string}} */ node) => node.path === path))
    ) {
      return { pageId: pageId, page: page, sentinel: sentinel };
    }
  }
  return null;
}

// Snapshot and change events include entries already held by a deferred page.
// Refresh that pending copy instead of mounting it ahead of its sentinel.
function _updateDeferredTreePageEntry(container, entry) {
  var deferred = _deferredTreePageForContainer(container, entry.path);
  if (!deferred) {
    return false;
  }
  var index = deferred.page.nodes.findIndex((node) => node.path === entry.path);
  if (index < 0) {
    return false;
  }
  var current = deferred.page.nodes[index];
  if (current.type !== entry.type) {
    deferred.page.nodes.splice(index, 1);
    _synchronizeDeferredTreePage(deferred.pageId, deferred.page);
    return false;
  }
  deferred.page.nodes[index] = { ...current, ...entry };
  return true;
}

function _synchronizeDeferredTreePage(pageId, page, mutationSnapshot) {
  var sentinel = /** @type {HTMLElement | null} */ (
    document.querySelector(`.tree-page-more[data-page-id="${escapePathForSelector(pageId)}"]`)
  );
  if (!sentinel) {
    pendingTreePages.delete(pageId);
    return;
  }
  var container = sentinel.parentElement;
  if (!container) {
    return;
  }
  // The container's rows in order, each "more" row counting the rows it holds back.
  var items = /** @type {HTMLElement[]} */ (
    Array.from(container.querySelectorAll(":scope > .tree-item"))
  );
  var held = (/** @type {HTMLElement} */ item) =>
    item.classList.contains("tree-page-more")
      ? (pendingTreePages.get(item.dataset.pageId || "")?.nodes.length ?? 0)
      : 1;
  var setSize = Math.max(
    items.reduce((total, item) => total + held(item), 0),
    Number(page.options.setSize) || 0,
  );
  page.options.setSize = setSize;
  var position = 0;
  for (const item of items) {
    item.dataset.treePosition = String(position + 1);
    item.dataset.treeSetSize = String(setSize);
    position += held(item);
    // Every "more" row of the container tells the folder's total and draws its rows with
    // it: a reveal can leave others than the one that ends the folder (mountTreePageAt).
    var heldPage = item.classList.contains("tree-page-more")
      ? pendingTreePages.get(item.dataset.pageId || "")
      : undefined;
    if (heldPage && heldPage !== page) {
      heldPage.options.setSize = setSize;
      _labelDeferredTreePage(item, heldPage);
    }
  }
  if (page.nodes.length === 0) {
    var sentinelMutation = mutationSnapshot || treeKeyboard?.prepareForMutation();
    sentinel.remove();
    pendingTreePages.delete(pageId);
    scheduleTreeSynchronize(sentinelMutation);
    return;
  }
  _labelDeferredTreePage(sentinel, page);
  scheduleTreeSynchronize(mutationSnapshot);
}

/**
 * @param {HTMLElement} sentinel A "more" row.
 * @param {{nodes: unknown[], options: Record<string, any>}} page What it holds back.
 */
function _labelDeferredTreePage(sentinel, page) {
  var label = document.getElementById(sentinel.getAttribute("aria-labelledby") || "");
  if (label) {
    label.textContent = `Show ${page.nodes.length} more (${page.options.setSize} total)`;
  }
}

function _removeDeferredTreePageEntries(path) {
  var prefix = `${path}/`;
  for (var [pageId, page] of pendingTreePages) {
    var originalLength = page.nodes.length;
    page.nodes = page.nodes.filter((node) => node.path !== path && !node.path.startsWith(prefix));
    var removed = originalLength - page.nodes.length;
    if (removed === 0) {
      continue;
    }
    var previousSetSize = Number(page.options.setSize) || originalLength;
    page.options.setSize = Math.max(page.nodes.length, previousSetSize - removed);
    _synchronizeDeferredTreePage(pageId, page);
  }
}

// Insert new arrivals in sorted order before any tree-page-more sentinel;
// entries already deferred remain deferred, and existing paths are patched
// separately. After startup settles, flash new rows and remove the flash class
// on animationend. Baseline rows stay neutral.
function _insertRowSorted(container, entry, options, highlightChange) {
  var safe = escapePathForSelector(entry.path);
  var existing = container.querySelector(`:scope > .tree-item[data-path="${safe}"]`);
  if (existing) {
    return false;
  }
  if (_updateDeferredTreePageEntry(container, entry)) {
    return false;
  }
  var deferredPage = _deferredTreePageForContainer(container);
  treeKeyboard?.prepareForMutation();
  container.querySelectorAll(":scope > .tree-lazy-placeholder").forEach((el) => {
    el.remove();
  });
  var tmp = document.createElement("div");
  var mountedRows = container.querySelectorAll(":scope > .tree-item").length + 1;
  tmp.innerHTML = _buildRowHtml(entry, {
    ...options,
    level: treeLevelForContainer(container),
    position: mountedRows,
    setSize: mountedRows,
  });
  var nodes = Array.prototype.slice.call(tmp.childNodes);
  // For dir inserts, _buildRowHtml emits two siblings (the .tree-folder
  // and its .tree-children). We insert both at the same anchor.
  var entryKey = _treeSortKey({ type: entry.type, name: entry.name });
  var anchor = null;
  var children = container.children;
  for (var i = 0; i < children.length; i++) {
    var ch = children[i];
    if (!ch.classList.contains("tree-item")) {
      continue;
    }
    if (ch.classList.contains("tree-folder")) {
      var name = ch.querySelector(".tree-item-name");
      var k = _treeSortKey({ type: "dir", name: name ? name.textContent : "" });
      if (_treeKeyCmp(entryKey, k) < 0) {
        anchor = ch;
        break;
      }
    } else if (ch.classList.contains("tree-file") || ch.classList.contains("tree-symlink")) {
      var name2 = ch.querySelector(".tree-item-name");
      var k2 = _treeSortKey({
        type: ch.classList.contains("tree-symlink") ? "symlink" : "file",
        name: name2 ? name2.textContent : "",
      });
      if (_treeKeyCmp(entryKey, k2) < 0) {
        anchor = ch;
        break;
      }
    }
  }
  if (anchor === null) {
    // Insert before the page-more sentinel that ends the folder if present, else at the
    // end. A reveal can leave others between the pages it drew, with rows after them.
    var lastItem = Array.from(queryHtmlAll(":scope > .tree-item", container)).pop();
    anchor = lastItem?.classList.contains("tree-page-more") ? lastItem : null;
  }
  for (var j = 0; j < nodes.length; j++) {
    var node = nodes[j];
    container.insertBefore(node, anchor);
    // Only flash the .tree-item itself; the sibling .tree-children
    // for folders is empty on insert (lazy placeholder) and would
    // visually double-flash if we styled it too.
    if (highlightChange && node.classList?.contains("tree-item")) {
      node.classList.add("tree-item-flash-in");
      node.addEventListener(
        "animationend",
        (ev) => {
          if (ev.animationName === "tree-row-flash-in") {
            ev.currentTarget.classList.remove("tree-item-flash-in");
          }
        },
        { once: true },
      );
    }
  }
  var mounted = /** @type {HTMLElement[]} */ (
    Array.from(container.querySelectorAll(":scope > .tree-item"))
  );
  if (deferredPage) {
    _synchronizeDeferredTreePage(deferredPage.pageId, deferredPage.page);
    return true;
  }
  var declaredSetSize = mounted.reduce(
    (largest, row) => Math.max(largest, Number(row.dataset.treeSetSize) || 0),
    mounted.length,
  );
  for (var metadataIndex = 0; metadataIndex < mounted.length; metadataIndex++) {
    mounted[metadataIndex].dataset.treeLevel = String(treeLevelForContainer(container));
    mounted[metadataIndex].dataset.treePosition = String(metadataIndex + 1);
    mounted[metadataIndex].dataset.treeSetSize = String(declaredSetSize);
  }
  scheduleTreeSynchronize();
  return true;
}

// Apply the patch+insert path for one fs.change op. File, directory,
// and symlink entries patch their matching row shape. If
// no row exists for the entry's path AND the entry's parent is
// rendered + expanded in either tab panel, insert a new row in
// sorted position so the user sees new entries without a reload.
function updateRootAggregatePresentation(entry) {
  if (entry.path || entry.type !== "dir") {
    return;
  }
  var totalFiles = entry.total_files == null ? null : entry.total_files;
  var totalSize = entry.total_size == null ? null : entry.total_size;
  var newestMtime = entry.newest_mtime_ns ? entry.newest_mtime_ns / 1e9 : 0;
  if (rootTotals().fromRootEntry(entry)) {
    if (_lastTreeRender) {
      paintTreeSummary(treeSummaryHtml(rootTotals().totals(), null, null));
    }
  } else if (!rootTotals().totals()) {
    // Until the root has totals, the fallback's two figures follow its aggregate.
    var countEl = queryHtml(".tree-summary-count");
    var sizeEl = queryHtml(".tree-summary-size");
    if (countEl) {
      countEl.innerHTML = window.MetabrowserNavigationRoute.treeSummaryCountHtml(
        totalFiles,
        treeSummaryFormat(),
      );
    }
    if (sizeEl) {
      sizeEl.innerHTML = window.MetabrowserNavigationRoute.treeSummarySizeHtml(
        totalSize,
        treeSummaryFormat(),
      );
    }
  }
  scheduleRootSummaryRefresh();
  var pathEl = queryHtml(".header-path");
  if (pathEl) {
    pathEl.dataset.tipFiles = nullableDataValue(totalFiles);
    pathEl.dataset.tipSize = nullableDataValue(totalSize);
    pathEl.dataset.tipMtime = nullableDataValue(newestMtime);
    updateRootDetailsStats();
  }
}

function applyCellPatch(entry, highlightChange) {
  // The root (path "") is the implicit tree container, never a row. The
  // server includes it in the fs.snapshot for its aggregate totals, but
  // patching it here would fall through to the insert branch (its parent
  // resolves to the panel root) and graft a phantom row for the served
  // dir *inside itself* — flashed yellow like a new file on every
  // (re)connect. Keep it in the store; just don't render it.
  if (!entry.path) {
    updateRootAggregatePresentation(entry);
    reconcilePendingTallyDiagnostics();
    scheduleTreeSynchronize();
    return;
  }
  var safePath = escapePathForSelector(entry.path);
  var selector =
    entry.type === "dir"
      ? `.tree-folder[data-path="${safePath}"]`
      : entry.type === "symlink"
        ? `.tree-symlink[data-path="${safePath}"]`
        : `.tree-file[data-path="${safePath}"]`;
  var rows = queryHtmlAll(selector);
  var pathRows = queryHtmlAll(`.tree-item[data-path="${safePath}"]`);
  var removingRow = Array.prototype.some.call(pathRows, (row) =>
    row.classList.contains("tree-item-flash-out"),
  );
  if (pathRows.length !== rows.length || removingRow) {
    // The watcher can observe a path changing shape (for example, a file
    // replaced by a symlink) without an intervening remove event. A stale row
    // with the old shape would make _insertRowSorted reject the replacement by
    // path. Remove it synchronously, including a former folder's child rows,
    // before taking the normal insert path. The same applies when a rapid
    // remove/recreate reaches us while an old same-shaped row is animating out.
    treeKeyboard?.prepareForMutation();
    _removeRenderedRowsImmediately(entry.path);
    rows = queryHtmlAll(selector);
  }
  if (rows.length > 0) {
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i];
      var patch = computeCellPatch(entry, treeRenderOptionsForElement(row));
      if (!patch) {
        continue;
      }
      var sizeSpan = row.querySelector(".tree-item-size");
      if (sizeSpan && sizeSpan.outerHTML !== patch.sizeHtml) {
        sizeSpan.outerHTML = patch.sizeHtml;
      }
      var ageSpan = row.querySelector(".tree-item-age-inline");
      if (ageSpan && ageSpan.innerHTML !== patch.ageHtml) {
        ageSpan.innerHTML = patch.ageHtml;
      }
      row.dataset.tipSize = nullableDataValue(patch.tipSize);
      row.dataset.tipMtime = nullableDataValue(patch.tipMtime);
      if (patch.kind === "dir") {
        row.dataset.tipFiles = patch.tipFiles;
        // A zero file total does not prove emptiness because symlinks
        // are visible leaves but intentionally excluded from aggregates.
        var totalFiles = entry.total_files;
        if (typeof entry.empty === "boolean") {
          treeKeyboard?.prepareForMutation();
          row.classList.toggle("tree-item-empty", entry.empty);
          var children = row.nextElementSibling;
          if (entry.empty && children?.classList.contains("tree-children")) {
            children.remove();
            row.classList.remove("expanded");
            row.classList.add("collapsed");
            row.removeAttribute("aria-expanded");
            row.removeAttribute("aria-owns");
          } else if (!entry.empty && !children?.classList.contains("tree-children")) {
            var groupId = treeDomId("tree-group", entry.path);
            row.insertAdjacentHTML(
              "afterend",
              treeChildGroupStartHtml(
                groupId,
                Number(row.getAttribute("aria-level") || 1) + 1,
                false,
              ) +
                '<div class="tree-lazy-placeholder mb-delayed-loading" data-tree-lazy-stub' +
                ' role="status" aria-label="Loading">' +
                '<span class="spinner spinner-sm" aria-hidden="true"></span></div></div>',
            );
            row.setAttribute("aria-expanded", "false");
            row.setAttribute("aria-owns", groupId);
          }
        } else if (totalFiles > 0) {
          // Positive totals remain an unambiguous fallback for events
          // from an older server that lacks explicit empty-state metadata.
          row.classList.toggle("tree-item-empty", false);
        }
      }
      // Sync gitignored across every row type so a flag flip
      // (rare, but possible if .gitignore is edited) updates
      // the muted class without a full rerender.
      row.classList.toggle("tree-item-gitignored", !!entry.gitignored);
      // mtime and active can both flip a row's filter verdict.
      scheduleFilterReapply();
    }
    reconcilePendingTallyDiagnostics();
    scheduleTreeSynchronize();
    return;
  }
  // No row exists — try to insert one in each panel where the
  // parent is currently rendered and expanded. Root parent is the
  // panel itself (always "expanded").
  var parentRel =
    entry.parent === undefined || entry.parent === null
      ? entry.path.indexOf("/") >= 0
        ? entry.path.substring(0, entry.path.lastIndexOf("/"))
        : ""
      : entry.parent;
  // A new entry's place in Group by sections is the server's to decide: which group it
  // joins, and which of the sections a folder stands in it belongs under. The batch that
  // carried it schedules a refresh of the sections (requestGroupedRefresh) instead.
  if (filesPanelUsesGroupedSource()) {
    return;
  }
  var panel = document.getElementById("tab-files");
  if (!panel) {
    return;
  }
  var container = _findChildContainerFor(parentRel, panel);
  if (!container) {
    return;
  }
  _insertRowSorted(container, entry, treeRenderOptionsForElement(panel), highlightChange);
  // A freshly inserted row carries no filter classes yet; without this
  // a new file would show up regardless of the active filter.
  scheduleFilterReapply();
  reconcilePendingTallyDiagnostics();
  scheduleTreeSynchronize();
}

// Remove matching rows from every tab, idempotently. Animate each row out,
// keeping it invisible with CSS forwards fill until removal. Remove a folder
// child container immediately so descendant events do not double-animate it.
function _removeRenderedRows(path) {
  var removalMutation = treeKeyboard?.prepareForMutation();
  var safe = escapePathForSelector(path);
  var rows = queryHtmlAll(`.tree-item[data-path="${safe}"]`);
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    // Idempotent: if the row is already in the flash-out
    // animation phase, don't re-trigger.
    if (row.classList.contains("tree-item-flash-out")) {
      continue;
    }
    if (row.classList.contains("tree-folder")) {
      var children = row.nextElementSibling;
      if (children?.classList.contains("tree-children")) {
        children.remove();
      }
    }
    row.classList.add("tree-item-flash-out");
    row.addEventListener(
      "animationend",
      (ev) => {
        if (!(ev instanceof AnimationEvent)) {
          return;
        }
        if (ev.animationName === "tree-row-flash-out") {
          var target = ev.currentTarget;
          if (target instanceof Element) {
            var parent = target.parentElement;
            var previousSetSize = Number(target.getAttribute("aria-setsize")) || 0;
            var deferredPage = parent ? _deferredTreePageForContainer(parent) : null;
            target.remove();
            if (deferredPage) {
              deferredPage.page.options.setSize = Math.max(
                deferredPage.page.nodes.length,
                previousSetSize - 1,
              );
              _synchronizeDeferredTreePage(deferredPage.pageId, deferredPage.page, removalMutation);
            } else if (parent) {
              var rows = /** @type {HTMLElement[]} */ (
                Array.from(parent.querySelectorAll(":scope > .tree-item"))
              );
              var nextSetSize = Math.max(rows.length, previousSetSize - 1);
              for (var j = 0; j < rows.length; j++) {
                rows[j].dataset.treePosition = String(j + 1);
                rows[j].dataset.treeSetSize = String(nextSetSize);
              }
              scheduleTreeSynchronize(removalMutation);
            }
          }
        }
      },
      { once: true },
    );
  }
}

// Type replacements cannot wait for the removal animation: the new row uses
// the same data-path and must be inserted in this event turn. This also removes
// a former folder's rendered descendants before its replacement is mounted.
function _removeRenderedRowsImmediately(path) {
  treeKeyboard?.prepareForMutation();
  var safe = escapePathForSelector(path);
  var rows = queryHtmlAll(`.tree-item[data-path="${safe}"]`);
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    if (row.classList.contains("tree-folder")) {
      var children = row.nextElementSibling;
      if (children?.classList.contains("tree-children")) {
        children.querySelectorAll(".tree-page-more[data-page-id]").forEach((sentinel) => {
          pendingTreePages.delete(/** @type {HTMLElement} */ (sentinel).dataset.pageId);
        });
        children.remove();
      }
    }
    row.remove();
  }
}

// Recency re-cluster scheduling: debounced so a burst of fs.change
// ops doesn't render-thrash. The recency source reads from
// ``recentBaseEntries`` (fetched from /api/recent plus a live overlay
// from fs.change), so updates inside the active window normally flow
// through without a refetch. In-flight snapshots are invalidated as
// described above.
function _scheduleRecentRecompute() {
  if (!recentEverLoaded) {
    return; // never fetched; nothing to recompute
  }
  if (!filesPanelUsesRecentSource()) {
    return; // the panel is showing the full tree; that path has its own updates
  }
  var cursor = currentRecentFilterCursor();
  recentRecompute.schedule({
    windowKey: cursor.windowKey,
    requestKey: cursor.recentRequestKey,
  });
}

var _esConsecutiveErrors = 0;
var _esBackoffMs = 2000;
var _esReconnectTimer = null;
var _esStableResetTimer = null;
var _ES_MAX_CONSECUTIVE_ERRORS = 5;
var _ES_BACKOFF_CAP_MS = 60000;
var _ES_STABLE_CONNECTION_MS = 10000;

function _resetEsCircuitBreaker() {
  _esConsecutiveErrors = 0;
  _esBackoffMs = 2000;
}

function _cancelEsStableReset() {
  if (_esStableResetTimer !== null) {
    clearTimeout(_esStableResetTimer);
    _esStableResetTimer = null;
  }
}

function _scheduleEsStableReset() {
  _cancelEsStableReset();
  _esStableResetTimer = setTimeout(() => {
    _esStableResetTimer = null;
    if (inventoryEventSource) {
      _resetEsCircuitBreaker();
    }
  }, _ES_STABLE_CONNECTION_MS);
}

function _scheduleInventoryReconnect() {
  _cancelEsStableReset();
  if (inventoryEventSource) {
    inventoryEventSource.close();
    inventoryEventSource = null;
  }
  catalogFeedCanStart = false;
  if (_esReconnectTimer !== null) {
    return;
  }
  var delay = _esBackoffMs;
  _esBackoffMs = Math.min(_esBackoffMs * 2, _ES_BACKOFF_CAP_MS);
  _esReconnectTimer = setTimeout(() => {
    _esReconnectTimer = null;
    // Each EventSource gets its own transport-error allowance. Keep the
    // escalating reconnect delay until the stable timer fires, but do not let
    // the previous source's threshold make one transient error close this one.
    _esConsecutiveErrors = 0;
    _createInventoryEventSource();
  }, delay);
}

// Park the stream or its pending reconnect (createPageConnections); a pin has
// neither. A new stream begins with a snapshot and a catalog refetch, as a reconnect
// does, which covers what the cached page missed.
function parkInventoryEventStream() {
  if (!inventoryEventSource && _esReconnectTimer === null) {
    return null;
  }
  _cancelEsStableReset();
  clearTimeout(_esReconnectTimer);
  _esReconnectTimer = null;
  inventoryEventSource?.close();
  inventoryEventSource = null;
  catalogFeedCanStart = false;
  _esConsecutiveErrors = 0;
  return _createInventoryEventSource;
}

function _createInventoryEventSource() {
  if (pageConnections?.suspended()) {
    pageConnections.defer(_createInventoryEventSource);
    return;
  }
  if (inventoryEventSource) {
    return;
  }
  catalogFeedCanStart = false;
  try {
    inventoryEventSource = new EventSource("/api/events?scope=root-depth-2");
  } catch (_e) {
    inventoryEventSource = null;
    _scheduleInventoryReconnect();
    return;
  }
  inventoryEventSource.addEventListener("fs.snapshot", (e) => {
    try {
      // The connection leads the frame; file watches register on it (file-watches.js).
      var named = /^\{"connection":(?:"([^"]*)"|null),/.exec(e.data);
      var body = named ? e.data.slice(named[0].length) : e.data;
      window.metabrowserEventConnection = named?.[1] ?? null;
      window.MetabrowserFileWatches?.connected(window.metabrowserEventConnection);
      // Equality of this scoped snapshot avoids parsing and repainting it.
      // It cannot prove deep files unchanged: retain the normal revalidation
      // and Recent repair boundary even when the shallow tree is identical.
      if (lastInventorySnapshot !== body) {
        var data = JSON.parse(e.data);
        fileStoreApplySnapshot(data.scope, data.entries || []);
        lastInventorySnapshot = body;
        if (data.complete === true) {
          inventoryChangeHighlightingActive = true;
        }
      } else {
        recentContinuity.dirtyActiveRequest();
        for (const path of fileCache.keys()) {
          fileNeedsRevalidate.add(path);
        }
        retryFailedExpandedSubtrees(true);
        announceUnchangedSnapshot();
      }
      _scheduleRecentRecompute();
      // Every depth-limited sentinel establishes a transport boundary. The
      // first must cover a Recent request/page that started before the SSE
      // baseline; later ones cover deltas dropped across reconnect. If Recent
      // starts after the first sentinel, this call had no active view and
      // retained no deferred repair.
      quickFileCatalogFeed?.onSentinelSnapshot();
      treeFilterModel.observeRecentSentinel(recentContinuity, {
        recentActive: recentEverLoaded && filesPanelUsesRecentSource(),
        filterRefetchPending: recentFilterRefetch.pending(),
        repair: recentRepairDescriptor(),
      });
    } catch (_e) {
      /* malformed frame; ignore */
    }
  });
  inventoryEventSource.addEventListener("fs.change", (e) => {
    lastInventorySnapshot = null;
    try {
      var data = JSON.parse(e.data);
      fileStoreApplyChange(data.ops || []);
      _scheduleRecentRecompute();
    } catch (_e) {
      /* ignore */
    }
  });
  inventoryEventSource.addEventListener("file.changed", (e) => {
    try {
      window.MetabrowserFileWatches?.changed(JSON.parse(e.data));
    } catch (_e) {
      /* ignore */
    }
  });
  inventoryEventSource.addEventListener("catalog.change", (e) => {
    try {
      var data = JSON.parse(e.data);
      quickFileCatalogFeed?.onCatalogChange(data);
      var recentOwnsCurrentView = recentViewOwnsCurrentCursor();
      var recentCatalogEffect =
        filterState && recentOwnsCurrentView
          ? treeFilterModel.applyRecentCatalogChange(recentBaseEntries, data, {
              filterState: filterState,
              nowSec: Date.now() / 1000,
              state: filterState.get(),
              visibleDepth: 2,
            })
          : null;
      if (!recentOwnsCurrentView && recentEverLoaded && filesPanelUsesRecentSource()) {
        // The unscoped catalog is the only notice for deep changes. A normal
        // replacement owns no retained base, so do not mutate or paint the old
        // one; dirty its in-flight response (or schedule recovery after a
        // failure) instead.
        scheduleRecentAuthoritativeRefetch();
      } else if (recentCatalogEffect?.needsAuthoritativeRepair) {
        // catalog.change rides every stream scope, so it is the authoritative
        // signal for file changes too deep for root-depth-2 fs.change.
        if (recentEverLoaded && filesPanelUsesRecentSource()) {
          markRecentTotalAsRetainedLowerBound(recentCatalogEffect.retainedLowerBound ?? 0);
          if (recentCatalogEffect.changed) {
            _scheduleRecentRecompute();
          }
        }
        scheduleRecentAuthoritativeRefetch();
      }
    } catch (_e) {
      /* ignore */
    }
  });
  inventoryEventSource.addEventListener("capability.update", (e) => {
    try {
      var data = JSON.parse(e.data);
      // Every terminal walk can repair membership lost across a reconnect.
      // A capped walk remains incomplete for the root even after that repair.
      if (data.index && data.index.complete === true) {
        quickFileCatalogFeed?.onIndexComplete(data.index.truncated === true);
        inventoryChangeHighlightingActive = true;
      }
    } catch (_e) {
      /* ignore */
    }
  });
  inventoryEventSource.addEventListener("fs.resync_required", (_e) => {
    lastInventorySnapshot = null;
    // A gap: clear derived state, keep FileStore and its rows as the baseline, and
    // reconnect for a snapshot (arch-live-delivery.md, "Recovery", says why).
    recentRecompute.cancel();
    scheduleRecentAuthoritativeRefetch();
    knownFileCatalog?.clear();
    notifyFileStoreSubscribers({ kind: "resync" });
    startIndexProgressPolling();
    quickFileCatalogFeed?.onResync();
    _scheduleInventoryReconnect();
  });
  inventoryEventSource.onopen = () => {
    catalogFeedCanStart = true;
    // The backoff resets only once the connection has lasted ("Recovery").
    _scheduleEsStableReset();
    // The first open starts the bulk catalog fetch after subscription;
    // later opens refetch to cover deltas lost while disconnected.
    quickFileCatalogFeed?.start();
    retryUnreachablePreview();
    quickFilePalette?.reconnected();
  };
  inventoryEventSource.onerror = () => {
    _cancelEsStableReset();
    _esConsecutiveErrors += 1;
    if (_esConsecutiveErrors >= _ES_MAX_CONSECUTIVE_ERRORS) {
      _scheduleInventoryReconnect();
    }
  };
}

function startInventoryEventStream() {
  if (isGitRevisionSource() || typeof EventSource === "undefined") {
    // A Git pin is already complete and has no watcher. Missing EventSource
    // is the same one-shot catalog path without live deltas.
    catalogFeedCanStart = true;
    quickFileCatalogFeed?.start();
    return;
  }
  if (inventoryEventSource) {
    return;
  }
  _createInventoryEventSource();
}

// ── Canonical navigation ───────────────────────────────────────

// navigation.js is linked by the same shell response, immediately ahead of this
// script, so the module and this controller always exist together.
var navigationController = window.MetabrowserNavigationRoute.createController({
  apply(target, context) {
    // A file or a folder reads the catalog.
    if (target && !isGitHistoryLanding()) {
      quickFileCatalogFeed?.release();
    }
    return applyNavigationTarget(target, context);
  },
});
window.MetabrowserNavigationRoute.attachController(navigationController);

/** @param {string} [prompt] */
function showNavigationLanding(prompt) {
  closeLiveStream();
  currentPath = "";
  setSelectedPath(null);
  // Nothing is selected, so no earlier load may still land in the pane.
  var claim = claimPreview("none");
  disposeActivePluginViews();
  stopFolderHeaderSubscription();
  const preview = document.getElementById("preview-pane");
  if (preview) {
    delete preview.dataset.renderedPath;
    preview.innerHTML = prompt
      ? `<div class="preview-empty">${esc(prompt)}</div>`
      : (previewPlaceholderHtml(previewPane.placeholder(claim)) ?? "");
    finishRetainedPullPage();
  }
}

// The shell ships a loading preview because every route it serves selects
// something. When startup ends with no producer having claimed the pane — a
// /commit/ route whose Git panel could not restore it, or navigation that
// failed to start — nothing is selected or loading, so show the prompt.
function settleUnclaimedPreview() {
  var html = previewPlaceholderHtml(previewPane.settleUnclaimed());
  var preview = document.getElementById("preview-pane");
  if (html !== null && preview) {
    preview.innerHTML = html;
    finishRetainedPullPage();
  }
}

// Only a /commit/ route and the neutral Commits entry wait on the Git panel to
// select something; any other /view/ route is claimed by its own file
// selection. Startup calls this once the shell tools, and with them the Git
// panel, have settled.
function settleCommitRoutePreview() {
  if (window.MetabrowserNavigationRoute.parseCommit(location.pathname) || isGitHistoryLanding()) {
    settleUnclaimedPreview();
  }
}

// The inventory stream reopening means the server answers again. A selection
// that failed because it could not reach the server is retried without the
// reader having to open it again.
function retryUnreachablePreview() {
  var retry = previewPane.reconnected();
  if (retry) {
    void selectFile(retry.path, retry.viewId);
  }
}

function deliverNavigationFragment(target) {
  window.dispatchEvent(
    new CustomEvent("metabrowser:navigation-fragment", {
      detail: { target: target },
    }),
  );
}

// ── Pull-request page ──────────────────────────────────────────
//
// pull-route.js holds the pull requests' address space and says how the shell and the view
// meet; the shell supplies the pane and the history. The host is null until a route opened.
var PULL_ROUTE_PREFIX = "/pull/";
var PULLS_ROUTE = "/pulls";

/** @param {string} pathname */
function isPullAddress(pathname) {
  return /^\/(pull|stack)\//.test(pathname) || pathname === PULLS_ROUTE;
}
/** @type {ReturnType<NonNullable<Window["MetabrowserPullRoute"]>["createPullPageHost"]> | null} */
var pullPageHost = null;
/** @type {(() => void) | null} One retired page or commit diff, shown until its replacement. */
var retainedPullPageDispose = null;

/** The pull-request page's host, created once its module has arrived. */
async function loadPullPageHost() {
  if (pullPageHost) {
    return pullPageHost;
  }
  if (!window.MetabrowserPullRoute) {
    const assets = window.MetabrowserAssets;
    if (!assets) {
      throw new Error("Metabrowser asset loader is unavailable");
    }
    await assets.ensureAsset("pull-route");
  }
  const routes = window.MetabrowserPullRoute;
  if (!routes) {
    throw new Error("Metabrowser pull-request routes are unavailable");
  }
  pullPageHost ??= routes.createPullPageHost(pullPageHostDeps(routes));
  return pullPageHost;
}

/** @param {number} number @returns {Promise<QuickFileOpenOutcome>} */
async function openQuickSearchPull(number) {
  const intent = ++mainTabIntent;
  const claim = previewPane.snapshot().claim;
  const host = await loadPullPageHost();
  if (intent !== mainTabIntent || !isPreviewClaimCurrent(claim)) {
    return { status: "cancelled" };
  }
  mainTabs?.remember();
  const routes = window.MetabrowserPullRoute;
  const naming = () => routes?.parsePull(window.location.pathname)?.number ?? null;
  // The pull request shown, on its page or on any of its tabs or changed files.
  const shown = naming() === number;
  const outcome = await host.open({ number, tab: "" });
  // Quick Search for the pull request shown opens it again, and its row is revealed again,
  // opening a stack the reader closed since. Its address names no other pull request, so
  // the host's write reveals nothing (revealPullAddress).
  if (outcome.status === "opened" && shown && naming() === number) {
    void mainTabs?.reveal("open", { again: true });
  }
  return outcome.status === "opened"
    ? { ...outcome, focusTarget: document.getElementById("preview-pane") }
    : outcome;
}

/**
 * The pane when the pull-request page's code could not be loaded.
 *
 * @param {number} [claim] The page's claim when it already holds the pane.
 * @param {string} [what] What could not load: the page, or the list at /pulls.
 */
function showPullPageLoadFailure(claim, what = "the pull-request page") {
  var held = claim;
  if (held === undefined) {
    closeLiveStream();
    currentPath = "";
    setSelectedPath(null);
    held = claimPreview("pull-request");
    stopFolderHeaderSubscription();
  }
  renderPreviewHtml(
    previewErrorHtml(`Could not load ${what}.`, "Reload the page to try again."),
    held,
  );
}

function pullPageHostDeps(routes) {
  var mountView = routes.createViewMount({
    sdk: window.metabrowser,
    isCurrent: isPreviewClaimCurrent,
    renderHtml: renderPreviewHtml,
    renderNode: (node, claim) => renderPreviewNode(node, claim),
    beginNavigation: beginPreviewNavigation,
    endNavigation: endPreviewNavigation,
    stageNode: stagePreviewNode,
    showLoadFailure: showPullPageLoadFailure,
  });
  return {
    claim: () => {
      closeLiveStream();
      currentPath = "";
      setSelectedPath(null);
      var claim = claimPreview("pull-request");
      stopFolderHeaderSubscription();
      return claim;
    },
    isCurrent: isPreviewClaimCurrent,
    mount: (claim, route, open) =>
      mountView(claim, route.stack ? "pull-stack" : "pull-request", {
        number: route.number,
        tab: route.tab,
        reader: route.reader,
        open: open,
      }),
    mountList: (claim) => mountView(claim, "pull-request-list", {}),
    pathname: () => window.location.pathname,
    // A pull request's page, one of its tabs, or one of its changed files, opened by a link,
    // a key, or a row.
    pushHref: (href) => {
      var before = window.location.pathname;
      mainTabIntent += 1;
      window.history.pushState(null, "", href);
      mainTabs?.remember();
      revealPullAddress(before, "open");
    },
    // A key's skim through the Pulls tab's rows, or through a pull request's changed files,
    // replaces, as openTreeRow does.
    replaceHref: (href) => {
      var before = window.location.pathname;
      mainTabIntent += 1;
      window.history.replaceState(null, "", href);
      mainTabs?.remember();
      revealPullAddress(before, "nav");
    },
  };
}

/**
 * Show the pull request's address the page host just wrote, by the reveal rule
 * (docs/design-system.md, "Navigation Reveals the Item"). An address that names another
 * pull request than *before* did reveals that pull request's row, by *route*. One that
 * names the same pull request, another tab of its page or one of its changed files, is a
 * step within the item shown: the Pulls tab comes to the front if another is, and the
 * list is told the address, which marks a changed file as current. A changed file of the
 * pull request shown never reveals its row.
 *
 * @param {string} before The address's path before the host wrote this one.
 * @param {"open" | "nav"} route
 */
function revealPullAddress(before, route) {
  var routes = window.MetabrowserPullRoute;
  var number = routes?.parsePull(window.location.pathname)?.number ?? null;
  if (mainTabs && number !== null && number !== (routes?.parsePull(before)?.number ?? null)) {
    void mainTabs.reveal(route);
    return;
  }
  void mainTabs?.reveal("step");
  window.MetabrowserPullsNav?.routeChanged();
}

// Back and forward between a page's tabs change no navigation target, so the host decides
// (pullHistoryAction). Added as app.js loads, before the controller adds its own, so it reads
// the target the controller held. With no host yet it is applied once one has loaded.
function applyPullHistoryLanding() {
  mainTabIntent += 1;
  if (mainTabs) {
    mainTabs.onHistory();
  } else if (window.location.pathname === "/view/") {
    void navigationController.restore().catch(console.error);
  }
  const generation = ++pullHistoryGeneration;
  var pathname = window.location.pathname;
  var heldTarget = navigationController.current() !== null;
  if (pullPageHost) {
    pullPageHost.onHistory(pathname, heldTarget);
    return;
  }
  if (!isPullAddress(pathname)) {
    return;
  }
  loadPullPageHost().then(
    (host) => {
      if (generation === pullHistoryGeneration && window.location.pathname === pathname) {
        host.onHistory(pathname, heldTarget);
      }
    },
    (error) => {
      console.error("metabrowser: the pull-request page could not load", error);
      if (generation === pullHistoryGeneration && window.location.pathname === pathname) {
        showPullPageLoadFailure();
      }
    },
  );
}
window.addEventListener("popstate", applyPullHistoryLanding);

/**
 * The view *target*'s address asks a file to open in, once the line-anchor module that
 * reads it has arrived with the view compositor (*loading*). A load that failed names
 * no view, and the file's own load of the same bundle reports the failure.
 *
 * @param {{path: string, query?: string, fragment?: string}} target
 * @param {ReturnType<typeof beginViewCompositionLoad>} loading
 * @returns {Promise<"source" | null>}
 */
async function addressedView(target, loading) {
  return (await loading).status === "ready"
    ? (window.MetabrowserSourceLineAnchors?.preferredView(target) ?? null)
    : null;
}

async function applyNavigationTarget(target, context) {
  if (context.source === "user") {
    mainTabIntent += 1;
  }
  // How the reader came: an open, a tab's landing, Back, or the page's own address.
  const route = mainTabs?.landingRoute(context.source) ?? null;
  if (isGitHistoryLanding()) {
    if (context.source !== "user") {
      // The neutral Commits entry is the Git panel's, as a /commit/ address is: the
      // panel selects the newest commit there, and the pane keeps what it shows until
      // that commit is ready (git-panel.js, landOnNewestCommit). A prompt painted here
      // would flash for as long as the first page of history takes.
      return { status: "cancelled" };
    }
    // An explicit Files root open can have the same address as the Git history entry.
    window.history.pushState(null, "", "/view/");
  }
  mainTabs?.remember();
  if (!target) {
    // A null target usually means "no selection". A /commit/ URL is a
    // selection in another address space (Browser URL Grammar), owned
    // by the Git panel — so the file pane must not claim the preview
    // with its empty landing state.
    if (window.MetabrowserNavigationRoute.parseCommit(window.location.pathname)) {
      return { status: "cancelled" };
    }
    if (isPullAddress(window.location.pathname)) {
      var pullHost = null;
      try {
        pullHost = await loadPullPageHost();
      } catch (error) {
        console.error("metabrowser: the pull-request page could not load", error);
        if (context.isCurrent()) {
          showPullPageLoadFailure();
        }
        return { status: "cancelled" };
      }
      if (!context.isCurrent()) {
        return { status: "cancelled" };
      }
      var pullRoute =
        window.MetabrowserPullRoute?.parsePull(window.location.pathname) ??
        window.MetabrowserPullRoute?.parseStack(window.location.pathname);
      if (pullRoute) {
        return pullHost.show(pullRoute);
      }
      if (window.location.pathname === PULLS_ROUTE) {
        return pullHost.showList();
      }
    }
    showNavigationLanding();
    return { status: "cancelled" };
  }
  var path = target.path.replace(/\/$/, "");
  // The file's tab comes to the front before the pane is read: a switch from another tab
  // takes the pane from what that tab showed there.
  void revealAddressedItem("step", { isCurrent: context.isCurrent });
  window.MetabrowserPullsNav?.routeChanged();
  // An address that anchors lines or carries `plain=1` opens the file's Source view.
  // Only an address with a fragment or a query can ask for one, and reading it takes
  // the line-anchor module, which arrives with the view compositor. That load starts
  // here and is awaited where the view is chosen, so it overlaps revealing the row,
  // and an address with neither goes on without it.
  var anchorModule = target.fragment || target.query ? beginViewCompositionLoad() : null;
  // Only a pane that already shows or is loading this path can take the
  // fragment alone. After a failure, or once the Git panel owns the pane,
  // opening the same path again is a retry and has to load it.
  if (!context.pathChanged && previewPane.holds(path)) {
    // A fragment or a line anchor is a step within the file shown, which reveals nothing.
    // Opening the file shown again, as Quick Search does, reveals its row again.
    if (context.source === "user" && !target.fragment && !target.query) {
      await revealAddressedItem(route, { isCurrent: context.isCurrent, again: true });
    }
    // A line anchor opens its Source tab; a caller's `viewId` wins, as below.
    var shownView = anchorModule ? await addressedView(target, anchorModule) : null;
    if (!context.isCurrent()) {
      return { status: "cancelled" };
    }
    showPreviewTab(path, context.viewId || shownView);
    deliverNavigationFragment(target);
    return {
      focusTarget: document.getElementById("preview-pane") || undefined,
      status: "opened",
    };
  }
  await revealAddressedItem(route, { isCurrent: context.isCurrent });
  // A held arrow key opens only the row its walk stops on.
  var walk = treeKeyboard?.walking(path);
  if (walk) {
    await walk;
  }
  var preferredView = anchorModule ? await addressedView(target, anchorModule) : null;
  if (!context.isCurrent()) {
    return { status: "cancelled" };
  }
  var outcome = await selectFile(path, context.viewId || preferredView || undefined);
  if (outcome.status === "opened" && context.isCurrent()) {
    deliverNavigationFragment(navigationController.current() || target);
  }
  return outcome;
}

/**
 * Show the item the address names in the navigation pane (docs/design-system.md,
 * "Navigation Reveals the Item"): main-tabs.js's `reveal` brings its tab to the front and
 * has that tab's panel reveal it, by the one rule for every route. Before the tab
 * controller has loaded, Files is the tab in front and reveals the file itself.
 *
 * The address is the one source of what is revealed, before the tab controller has
 * loaded and after: the navigation controller writes a target's address before it
 * applies the target, so the file a landing applies is the one the address names
 * (addressedFilePath).
 *
 * @param {MetabrowserRevealRoute | null} route Null before the tab controller has loaded.
 * @param {{isCurrent: () => boolean, again?: boolean}} how *again*: an open of the file
 *   shown (main-tabs.js, `reveal`).
 * @returns {Promise<void>}
 */
async function revealAddressedItem(route, how) {
  if (mainTabs && route !== null) {
    await mainTabs.reveal(route, how);
  } else if (route !== "step") {
    await revealFileRow(addressedFilePath(), {
      scroll: "nearest",
      isCurrent: how.isCurrent,
      again: how.again === true,
    });
  }
}

/** The file or folder the address names, without a folder's trailing slash; "" for none. */
function addressedFilePath() {
  var target = window.MetabrowserNavigationRoute.parse(
    window.location.pathname,
    window.location.search,
    window.location.hash,
  );
  return target ? target.path.replace(/\/$/, "") : "";
}

/**
 * The Files panel's reveal: open the folders above *path*, and the page of a long folder
 * that holds it, select its row, and scroll it into view unless *how* keeps the tree's
 * place. A path the tree cannot show still takes the selection from the row that had it,
 * so no other row stays selected under it, and when a filter hides it the tree says so
 * (renderSelectionOutsideFilterNote).
 *
 * @param {string} path
 * @param {MetabrowserRevealHow} how
 * @returns {Promise<boolean>} Whether its row is shown.
 */
async function revealFileRow(path, how) {
  var shown = await revealInTree(path, {
    isCurrent: how.isCurrent,
    scroll: how.scroll === "nearest",
  });
  if (!shown && how.isCurrent()) {
    setSelectedPath(path || null);
  }
  return shown;
}

// Expand tree folders along ``path`` (loading lazy subtrees as needed)
// and mark the target row selected. Returns true if the row exists.
// Pair with selectFile() for the body; init() kicks off both legs in
// parallel so a deep-link doesn't pay tree-walk latency before its own
// request leaves the client.
/** @param {string} path @param {{isCurrent?: () => boolean, scroll?: boolean, instant?: boolean}} [options] */
async function revealInTree(path, options = {}) {
  if (!path) {
    return false;
  }
  if (!filesPanelUsesGroupedSource()) {
    return revealWithin(document, path, options);
  }
  // The sections a choice is still loading are not on screen yet: the reveal lands once
  // they paint.
  await groupedSectionsSettled();
  if (options.isCurrent && !options.isCurrent()) {
    return false;
  }
  if (!filesPanelUsesGroupedSource()) {
    // The reader left grouping while the sections were on their way.
    return revealWithin(document, path, options);
  }
  // Under Group by the row is in one section, and its folders may stand in several: open
  // them only in the section the file belongs to, or, when that cannot be told here, in
  // each section in order until one holds the row.
  for (const section of sectionsForPath(path)) {
    if (await revealWithin(section, path, options)) {
      return true;
    }
  }
  return false;
}

/**
 * The sections that can hold *path*'s row, most likely first: its type group's, or for
 * Age the band its known mtime falls in, else every section.
 *
 * @param {string} path
 * @returns {HTMLElement[]}
 */
function sectionsForPath(path) {
  var sections = /** @type {HTMLElement[]} */ (
    Array.from(queryHtmlAll("#tab-files > .tree-section"))
  );
  var byKey = new Map(sections.map((section) => [section.dataset.treeGroup || "", section]));
  var order = treeFilterModel.revealSectionOrder(
    Array.from(byKey.keys()),
    treeFilterModel.likelySectionKey(
      treeFilterModel.groupBy(currentFilterSnapshot()),
      revealEntryFor(path),
      Date.now() / 1000,
      _RECENT_WINDOW_SECONDS,
      (name, ext) => window.MetabrowserFileTypeTaxonomy?.groupForFile(name, ext) ?? null,
    ),
  );
  return order.map((key) => /** @type {HTMLElement} */ (byKey.get(key)));
}

/**
 * What the shell knows of *path* to guess its section by: the file store's entry, else a
 * row already drawn for it, else nothing, which makes no guess.
 *
 * @param {string} path
 */
function revealEntryFor(path) {
  var name = path.slice(path.lastIndexOf("/") + 1);
  var entry = fileStore.get(path);
  if (entry) {
    return {
      type: entry.type,
      name,
      ext: entry.ext ?? getExt(name),
      mtime: typeof entry.mtime_ns === "number" ? entry.mtime_ns / 1e9 : undefined,
    };
  }
  var row = /** @type {HTMLElement | null} */ (
    queryHtml(`#tab-files .tree-item[data-path="${escapePathForSelector(path)}"]`)
  );
  if (!row) {
    return null;
  }
  return {
    type: row.classList.contains("tree-folder")
      ? "dir"
      : row.classList.contains("tree-symlink")
        ? "symlink"
        : "file",
    name,
    ext: row.dataset.ext || getExt(name),
    mtime: parseTipNumber(row.dataset.tipMtime) ?? undefined,
  };
}

/**
 * Open the folders above *path* inside *scope*, select its row, and scroll to it.
 *
 * @param {Document | HTMLElement} scope
 * @param {string} path
 * @param {{ isCurrent?: () => boolean, scroll?: boolean, instant?: boolean }} [options]
 */
async function revealWithin(
  scope,
  path,
  { isCurrent = () => true, scroll = true, instant = true } = {},
) {
  var segments = path.split("/");
  var current = "";
  for (var i = 0; i < segments.length - 1; i++) {
    if (!isCurrent()) {
      return false;
    }
    current = current ? `${current}/${segments[i]}` : segments[i];
    var folder = queryHtml(
      `.tree-folder[data-path="${escapePathForSelector(current)}"]`,
      /** @type {HTMLElement} */ (scope),
    );
    if (!folder && mountTreePageHolding(scope, current)) {
      folder = queryHtml(
        `.tree-folder[data-path="${escapePathForSelector(current)}"]`,
        /** @type {HTMLElement} */ (scope),
      );
    }
    if (folder) {
      var children = /** @type {HTMLElement | null} */ (folder.nextElementSibling);
      if (children) {
        // Scoped to direct children on purpose. A descendant folder carries
        // its own stub, so an unscoped match reads "this folder is unloaded"
        // for a folder whose rows are already on screen, and reloading it
        // swaps those rows for a spinner before restoring them.
        if (children.querySelector(":scope > .tree-lazy-placeholder")) {
          await loadSubtree(current, children);
          if (!isCurrent()) {
            return false;
          }
        }
        if (children.classList.contains("tree-children-collapsed")) {
          // The reader asked for the row, not the disclosure: no travel. A landing's
          // reveal has no input to answer, and its folders travelling moved the tree less
          // than their opening at once (layout shift 0.11-0.39 against 0.36-0.83, two to
          // eight folders of 152 rows, Chrome 152).
          await setFolderExpanded(folder, true, { instant });
        }
      }
    }
  }
  if (!isCurrent()) {
    return false;
  }
  var selector = `.tree-item[data-path="${escapePathForSelector(path)}"]`;
  var target = scope.querySelector(selector);
  if (!target && mountTreePageHolding(scope, path)) {
    target = scope.querySelector(selector);
  }
  if (!target) {
    return false;
  }
  setSelectedPath(path);
  var travel = scroll ? folderTravelAbove(target) : null;
  if (travel !== null) {
    // Once the folders above have opened, if the reveal stands and its folder is open.
    const revealed = target;
    void travel.then(() => {
      var row = revealed.isConnected ? revealed : scope.querySelector(selector);
      if (row && isCurrent() && !row.closest(".tree-children-collapsed")) {
        row.scrollIntoView({ block: "nearest" });
      }
    });
  } else if (scroll) {
    target.scrollIntoView({ block: "nearest" });
  }
  synchronizeTreeNow();
  return true;
}

/**
 * The end of every finite opening of a folder above *row*, or null (mb-551m).
 * @param {Element} row
 * @returns {Promise<unknown> | null}
 */
function folderTravelAbove(row) {
  /** @type {Animation[]} */
  var travel = [];
  for (
    var body = row.parentElement?.closest(".tree-children");
    body;
    body = body.parentElement?.closest(".tree-children")
  ) {
    travel.push(
      ...body.getAnimations().filter((a) => a.effect?.getComputedTiming().endTime !== Infinity),
    );
  }
  return travel.length > 0
    ? Promise.allSettled(travel.map((animation) => animation.finished))
    : null;
}

/**
 * Draw the page of a long folder that holds *path*'s row. A folder draws its first
 * TREE_PAGE_SIZE rows and holds the rest behind a "more" row, which draws them a page at
 * a time. A reveal draws only the page that holds the row: the rows before that page
 * stay behind the "more" row, and the rows after it go behind one of their own
 * (docs/design-system.md, "Navigation Reveals the Item").
 *
 * @param {Document | HTMLElement} scope
 * @param {string} path
 * @returns {boolean} Whether a page holding it was mounted.
 */
function mountTreePageHolding(scope, path) {
  for (const sentinel of queryHtmlAll(
    ".tree-page-more[data-page-id]",
    /** @type {HTMLElement} */ (scope),
  )) {
    var page = pendingTreePages.get(sentinel.dataset.pageId);
    var index = page
      ? page.nodes.findIndex((/** @type {{path: string}} */ node) => node.path === path)
      : -1;
    if (index >= TREE_PAGE_SIZE) {
      return mountTreePageAt(sentinel, page, index - (index % TREE_PAGE_SIZE)) !== null;
    }
    if (index >= 0) {
      return mountNextTreePage(sentinel) !== null;
    }
  }
  return false;
}

/**
 * Draw the page that starts *start* rows into what *sentinel* holds back, after the
 * sentinel, which keeps the rows before that page, and the rows after it behind a "more"
 * row of its own. Each of the two draws its page in place, as any "more" row does
 * (mountNextTreePage), so pressing them draws the folder in order.
 *
 * The cost is one page's, however long the folder. Measured 2026-11-15 in headless
 * Chrome 152 against a live server, with the folder's first page drawn, on a machine at
 * load average 14: `revealFileRow` for the last of 10,000 files took 18 ms (median of
 * five, at most 20 ms) and 28 ms to the second frame after, with the row selected and in
 * view, against 17 ms for a row in the second page. Drawing every page up to the row
 * instead, as pressing "more" until it appears would, took 204 ms for 2,000 files, 783 ms
 * for 5,000, and 2.75 s for 10,000, most of it the layout of every row drawn.
 *
 * @param {HTMLElement} sentinel
 * @param {{nodes: {path: string}[], options: Record<string, any>}} page
 * @param {number} start A multiple of TREE_PAGE_SIZE within `page.nodes`.
 * @returns {HTMLElement | null} The first row drawn.
 */
function mountTreePageAt(sentinel, page, start) {
  var nodes = page.nodes;
  var offset = Number(page.options.positionOffset) || 0;
  treeKeyboard?.prepareForMutation();
  page.nodes = nodes.slice(0, start);
  var temporary = document.createElement("div");
  temporary.innerHTML = withTreeIdScope(
    page.options.section || "",
    () =>
      renderTreeNodes(nodes.slice(start, start + TREE_PAGE_SIZE), false, {
        ...page.options,
        positionOffset: offset + start,
      }) +
      deferredTreePageHtml(nodes.slice(start + TREE_PAGE_SIZE), {
        ...page.options,
        positionOffset: offset + start + TREE_PAGE_SIZE,
      }),
  );
  _labelDeferredTreePage(sentinel, page);
  var after = sentinel.nextElementSibling;
  var firstMounted = null;
  for (const node of Array.prototype.slice.call(temporary.childNodes)) {
    sentinel.parentElement?.insertBefore(node, after);
    if (!firstMounted && node.getAttribute?.("role") === "treeitem") {
      firstMounted = node;
    }
  }
  // A drawn page arrives without current filter decoration, as mountNextTreePage's does.
  applyTreeFilters();
  reconcilePendingTallyDiagnostics();
  synchronizeTreeNow();
  return firstMounted;
}

/**
 * @param {string} path
 * @param {string=} preferredViewId
 * @param {{replace?: boolean}=} routeOptions
 * @returns {Promise<QuickFileOpenOutcome>}
 */
async function navigateToPath(path, preferredViewId, routeOptions) {
  // The served root is the empty path, and only a nested folder carries a
  // trailing slash, so both spellings arrive here already canonical.
  var normalized = path.replace(/\/+$/, "");
  var folder = path.endsWith("/");
  /** @type {{replace?: boolean, viewId?: string}} */
  var openOptions = {};
  if (preferredViewId) {
    openOptions.viewId = preferredViewId;
  }
  // Skimming with arrows replaces the route instead of pushing it, so Back
  // returns to wherever the reader entered the tree rather than replaying
  // every row they passed through.
  if (routeOptions?.replace) {
    openOptions.replace = true;
  }
  // The route module is dialect-agnostic and types `open` as returning the
  // apply callback's `unknown`. This shell installed that callback, so it is
  // the one place that knows the result is an open outcome.
  return /** @type {Promise<QuickFileOpenOutcome>} */ (
    navigationController.open(
      { path: folder && normalized ? `${normalized}/` : normalized },
      openOptions,
    )
  );
}

// Compose application keyboard infrastructure at the shell boundary.
function resolveApplicationFocusFallback(previous) {
  // A file tree row: a Pulls row is a tree's item too, with no tree id.
  if (treeKeyboard && previous?.closest?.('[role="treeitem"][data-tree-id]')) {
    var focusedTreeRow = treeKeyboard.focusedRow();
    if (focusedTreeRow?.isConnected) {
      return focusedTreeRow;
    }
  }
  if (applicationFocusRegion === "preview") {
    return document.getElementById("preview-pane");
  }
  return null;
}

function initKeyboardInfrastructure() {
  if (shortcutRegistry || keyboardHelp || treeKeyboard) {
    return;
  }
  if (
    !window.MetabrowserKeyboardShortcuts ||
    !window.MetabrowserTreeKeyboardNavigation ||
    !window.MetabrowserOverlay ||
    !window.MetabrowserKeyboardHelp
  ) {
    console.warn("Keyboard Help dependencies are unavailable");
    return;
  }
  var hintHost = document.getElementById("nav-shortcut-hints");
  if (!hintHost) {
    console.warn("Keyboard Help hint host is unavailable");
    return;
  }
  shortcutRegistry = window.MetabrowserKeyboardShortcuts.create({ document: document });
  mainTabs?.bindShortcuts(shortcutRegistry);
  window.MetabrowserPullsNav?.bindShortcuts(shortcutRegistry);
  keyboardHelp = window.MetabrowserKeyboardHelp.create({
    document: document,
    hintHost: hintHost,
    overlay: window.MetabrowserOverlay,
    resolveFocusFallback: resolveApplicationFocusFallback,
    shortcuts: shortcutRegistry,
  });
  treeKeyboard = window.MetabrowserTreeKeyboardNavigation.create({
    activate: activateTreeRowFromKeyboard,
    // The Files tab's: the Pulls tab's list is a tree too, with keys of its own.
    container: /** @type {HTMLElement} */ (document.getElementById("tab-files")),
    document: document,
    navigate: openTreeRow,
    setFolderExpanded: setRowExpanded,
    shortcuts: shortcutRegistry,
  });
  // Both read what rendered before the registry existed: the keymap the committed view
  // tabs, header, filters, and selector; the reveal nothing, until Shift is held.
  if (window.MetabrowserShellKeymap) {
    shellKeymap = window.MetabrowserShellKeymap.createShellKeymap({
      shell: shellKeymapShell(),
      shortcuts: shortcutRegistry,
    });
  }
  if (window.MetabrowserKeyReveal) {
    keyReveal = window.MetabrowserKeyReveal.createKeyReveal({
      document: document,
      shortcuts: shortcutRegistry,
    });
  }
  detachPluginShortcuts =
    window.MetabrowserPluginShortcuts?.attachShortcutRegistry(shortcutRegistry);
  applicationFocusListener = (event) => {
    var target = event.target;
    var treePaneElement = document.getElementById("tree-pane");
    var previewElement = document.getElementById("preview-pane");
    if (treePaneElement?.contains(target)) {
      applicationFocusRegion = "tree";
    } else if (previewElement?.contains(target)) {
      applicationFocusRegion = "preview";
    }
  };
  document.addEventListener("focusin", applicationFocusListener);
}

function disposeKeyboardInfrastructure() {
  if (applicationFocusListener) {
    document.removeEventListener("focusin", applicationFocusListener);
    applicationFocusListener = null;
  }
  quickFilePalette?.dispose();
  quickFilePalette = null;
  quickFileCatalogFeed?.dispose();
  quickFileCatalogFeed = null;
  quickFileSearchController?.dispose();
  quickFileSearchController = null;
  knownFileCatalog = null;
  keyReveal?.dispose();
  keyReveal = null;
  shellKeymap?.dispose();
  shellKeymap = null;
  detachPluginShortcuts?.();
  detachPluginShortcuts = null;
  treeKeyboard?.dispose();
  treeKeyboard = null;
  keyboardHelp?.dispose();
  keyboardHelp = null;
  mainTabs?.bindShortcuts(null);
  shortcutRegistry?.dispose();
  shortcutRegistry = null;
}

// `pagehide` also fires when the document enters the back/forward cache, and a
// bfcache restore never re-runs DOMContentLoaded. Tearing the registry down
// there would return the user to a page whose shortcuts, Help, Quick File, and
// tree keys are all silently dead, so a persisted hide parks only the page's
// connections, and the matching `pageshow` rebuilds whatever an earlier real
// teardown removed and reopens them. The listeners stay registered: a persisted
// hide can be followed by a genuine one.
var pageConnections = window.MetabrowserNavigationRoute.createPageConnections({
  connections: [parkInventoryEventStream, parkLiveStream],
  rebuild: () => {
    initKeyboardInfrastructure();
    initQuickFileFinder();
  },
  teardown: disposeKeyboardInfrastructure,
});
window.addEventListener("pagehide", (event) => pageConnections.hidden(event.persisted));
window.addEventListener("pageshow", (event) => pageConnections.shown(event.persisted));

// Compose the application-lifetime quick-file modules at the shell boundary.
function initQuickFileFinder() {
  if (quickFilePalette) {
    return;
  }
  if (
    !window.MetabrowserKnownFileCatalog ||
    !window.MetabrowserFileFuzzyMatch ||
    !window.MetabrowserSearch ||
    !window.MetabrowserSearchPalette ||
    !shortcutRegistry ||
    !window.MetabrowserOverlay
  ) {
    console.warn("Quick Search dependencies are unavailable");
    return;
  }

  knownFileCatalog = window.MetabrowserKnownFileCatalog.create();
  window.MetabrowserPluginHost?.attachFileCatalog(knownFileCatalog);
  if (window.MetabrowserCatalogFeed) {
    quickFileCatalogFeed = window.MetabrowserCatalogFeed.create({
      catalog: knownFileCatalog,
    });
    // A pull request's page reads no catalog until its palette or a file does, and each of
    // those releases it (`catalog-feed.js#hold`).
    if (window.location.pathname.startsWith(PULL_ROUTE_PREFIX)) {
      quickFileCatalogFeed.hold();
    }
    // The stream can open while its on-demand catalog modules are loading.
    // Start here if that open already happened, or if this browser has no live
    // transport; otherwise onopen starts it. JavaScript dispatches neither
    // callback in the middle of this task, so the first fetch runs once.
    if (catalogFeedCanStart) {
      quickFileCatalogFeed.start();
    }
  }
  quickFileSearchController = window.MetabrowserSearch.createController({
    maxResults: QUICK_FILE_RESULT_LIMIT,
  });
  var localProvider = window.MetabrowserSearch.createLocalFileProvider({
    catalog: knownFileCatalog,
    matcher: window.MetabrowserFileFuzzyMatch,
    maxResults: QUICK_FILE_RESULT_LIMIT,
  });
  quickFileSearchController.registerProvider(localProvider);
  const hasPulls = window.metabrowser.repository !== null;
  if (hasPulls) {
    quickFileSearchController.registerProvider(window.MetabrowserSearch.createPullProvider());
  }
  quickFilePalette = window.MetabrowserSearchPalette.create({
    controller: quickFileSearchController,
    // The same distinction the preview pane makes: an unreachable server is a
    // connection problem, not a reason the file could not be opened.
    describeOpenFailure: window.MetabrowserNavigationRoute.openFailureOutcome,
    getCatalogSnapshot: () => knownFileCatalog.snapshot(),
    getFileIcon: getFileIcon,
    maxRows: QUICK_FILE_RESULT_LIMIT + window.MetabrowserSearch.PULL_RESULT_LIMIT,
    onOpen: () => quickFileCatalogFeed?.release(),
    overlay: window.MetabrowserOverlay,
    // Coverage grows while the palette is open — the bulk feed lands, then
    // live deltas — so an open search re-runs instead of keeping the result
    // set it happened to get first.
    subscribeCatalog: (listener) => knownFileCatalog.subscribe(listener),
    onNotFound: (path) => {
      quickFileCatalogFeed?.onEventChange([{ op: "remove", path }]);
    },
    openPull: hasPulls ? openQuickSearchPull : undefined,
    openFile: (path) => {
      // Search hits can outlive deep inventory changes that are outside the
      // shallow event stream. Force the existing ETag path to confirm the file
      // still exists before treating palette navigation as successful.
      fileNeedsRevalidate.add(path);
      boundMapSize(fileNeedsRevalidate, ETAG_REVALIDATE_MAX);
      return navigateToPath(path);
    },
    resolveFocusFallback: resolveApplicationFocusFallback,
    shortcuts: shortcutRegistry,
  });
}

function clearBrowserFileCache(path) {
  if (path) {
    fileCache.delete(path);
    fileETags.delete(path);
    fileNeedsRevalidate.delete(path);
    return;
  }
  fileCache.clear();
  fileETags.clear();
  fileNeedsRevalidate.clear();
}

if (typeof window !== "undefined") {
  window.metabrowser.debug = Object.freeze({
    clearFileCache: clearBrowserFileCache,
    pullPage: () => pullPageHost?.page() ?? null,
    selectFile: selectFile,
  });

  function enhanceCurrentFileAfterOptionalAsset() {
    scheduleHighlightCode(document);
  }

  window.addEventListener(
    "metabrowser:optional-asset-loaded",
    enhanceCurrentFileAfterOptionalAsset,
  );
  window.addEventListener(
    "metabrowser:optional-assets-loaded",
    enhanceCurrentFileAfterOptionalAsset,
  );
}

// ── Init ────────────────────────────────────────────────────────

async function initDeferredShellTools() {
  const assets = window.MetabrowserAssets;
  if (!assets) {
    throw new Error("Metabrowser asset loader is unavailable");
  }
  await _perf.measureAsync("loadShellTools", () => assets.ensureAsset("shell-tools"));
  attachMainTabs();
  // Before the keymap, whose backslash key targets the chevron.
  startNavCollapse();
  initKeyboardInfrastructure();
  initQuickFileFinder();
  window.MetabrowserPullsNav?.init().catch((error) => {
    console.error("metabrowser pulls tab: init failed", error);
  });
  await window.MetabrowserGitPanel?.init();
  await mainTabs?.finishGitDiscovery();
  document.documentElement.dataset.shellToolsReady = "true";
}

/**
 * A served mirror's freshness row: when it was fetched and an offer when a refresh
 * moved the pinned ref. Only a pin has one, and it is fetched on demand after the
 * first tree request, so neither a folder nor the first rows ever wait for it.
 * static/source-freshness.js owns every decision; this only mounts it.
 */
async function startSourceFreshness() {
  var element = document.getElementById("source-freshness");
  var assets = window.MetabrowserAssets;
  if (!isGitRevisionSource() || !element || !assets) {
    return null;
  }
  await assets.ensureAsset("source-freshness");
  return window.MetabrowserSourceFreshness?.mount(element) ?? null;
}

/** @type {Promise<MetabrowserSourceFreshnessController | null> | null} */
var sourceFreshnessStarted = null;

/**
 * The page's one freshness controller, mounted on first use: null when a folder is
 * served. The commit view asks it to fetch for a commit the mirror lacks, so both read
 * one status and a page never polls twice.
 */
function sourceFreshness() {
  sourceFreshnessStarted ??= startSourceFreshness().catch((error) => {
    // A failed asset load is not the answer for the rest of the page's life.
    sourceFreshnessStarted = null;
    throw error;
  });
  return sourceFreshnessStarted;
}

/**
 * The branch and tag selector. The server renders its element only where one mounts;
 * the module is fetched on demand after the first tree request, and
 * static/source-ref-selector.js owns every decision; this only mounts it.
 */
async function startSourceRefSelector() {
  var element = document.getElementById("source-ref-selector");
  var assets = window.MetabrowserAssets;
  if (!element || !assets) {
    return;
  }
  await Promise.all([assets.ensureAsset("source-ref-selector"), assets.ensureAsset("sdk-views")]);
  // The selector's module keeps what it mounted, which the branch or tag key runs the
  // button's path through, and the keymap reads it from there.
  window.MetabrowserSourceRefSelector?.mount(element);
  shellKeymap?.syncSource();
}

// app.js is the last core script in the body, so the tree container and every
// cache used by its renderer are initialized here. Paint the server-carried
// rows now instead of waiting for DOMContentLoaded. The authoritative request
// below keeps the same baseline and reconciles into it.
//
// A pin's page names and addresses every file through the GitPath codec, a startup
// script of its shell. Without it a row would show its wire for a name and a link
// would address another file, so the page stops here and says so.
if (isGitRevisionSource() && !window.MetabrowserGitPath) {
  for (const id of ["tree-content", "preview-pane"]) {
    const pane = document.getElementById(id);
    if (pane) {
      pane.innerHTML =
        '<div class="preview-empty" role="alert">This page did not load completely. Reload the page to try again.</div>';
    }
  }
  throw new Error("metabrowser: git-path.js did not load on a pinned revision's page");
}
renderNavFilterBar();
renderInitialTreeRows();
/** @type {MetabrowserPublicNavCollapseController | null} */
var navCollapse = null;
drawNavCollapseButton();

/**
 * The chevron that hides and shows the navigation pane, drawn before the first paint.
 * Its module, static/nav-collapse.js, arrives in the `shell-tools` bundle, which owns
 * every decision; a click before then loads the bundle and then hides the pane.
 */
function drawNavCollapseButton() {
  var button = document.getElementById("nav-collapse-toggle");
  if (!button) {
    return;
  }
  // The chevron of the "icon-btn nav-collapse-toggle disclosure-toggle" server.py writes.
  button.innerHTML = `${ICONS.toggle}`;
  button.addEventListener("click", onEarlyNavCollapseClick);
  alignNavCollapseButton(button);
}

/**
 * Keep the chevron on the shortcut strip's row (mb-yw18), from the first paint on. The
 * strip moves when a row under it shows, the scan's progress or a mirror's freshness,
 * so a ResizeObserver on the pane and the rows from the strip down measures the row below
 * the strip's rule, from the pane's top, where the frame and the divider start too, and
 * gives `--nav-shortcut-row-top` and `--nav-shortcut-row-height` to the chevron, which it
 * places, and to the divider, whose resize reach stops above it (`.nav-collapse-toggle`
 * and `.resize-handle::after` in styles.css). Only those two take them: a property set on
 * a shared ancestor restyled the whole open document on every change, 100 ms for a
 * 28,000-node file in headless Chrome 152 (review A on #609). Boxes, not offsets, so the
 * row is not rounded to a whole pixel under the app's fractional page zoom.
 *
 * @param {HTMLElement} button
 */
function alignNavCollapseButton(button) {
  var pane = document.getElementById("tree-pane");
  var strip = document.getElementById("nav-shortcut-hints");
  var handle = document.getElementById("tree-resize");
  if (!pane || !strip || typeof ResizeObserver !== "function") {
    return;
  }
  var targets = handle ? [button, handle] : [button];
  var row = strip;
  var start = pane;
  var observer = new ResizeObserver(() => {
    var rect = row.getBoundingClientRect();
    var top = `${rect.top + row.clientTop - start.getBoundingClientRect().top}px`;
    var height = `${rect.height - row.clientTop}px`;
    for (var target of targets) {
      target.style.setProperty("--nav-shortcut-row-top", top);
      target.style.setProperty("--nav-shortcut-row-height", height);
    }
  });
  observer.observe(pane);
  for (var node = /** @type {Element | null} */ (strip); node; node = node.nextElementSibling) {
    observer.observe(node);
  }
}

/** @param {MouseEvent} event */
function onEarlyNavCollapseClick(event) {
  event.preventDefault();
  window.MetabrowserAssets?.ensureAsset("shell-tools").then(
    () => startNavCollapse()?.toggle(),
    (error) => console.error("metabrowser: could not load the navigation toggle", error),
  );
}

/** Run the chevron with its module, once the `shell-tools` bundle has loaded it. */
function startNavCollapse() {
  if (navCollapse) {
    return navCollapse;
  }
  var button = /** @type {HTMLButtonElement | null} */ (
    document.getElementById("nav-collapse-toggle")
  );
  var pane = document.getElementById("tree-pane");
  var frame = queryHtml(".preview-frame");
  var container = queryHtml(".container");
  if (!window.MetabrowserNavCollapse || !button || !pane || !frame || !container) {
    return null;
  }
  button.removeEventListener("click", onEarlyNavCollapseClick);
  navCollapse = window.MetabrowserNavCollapse.create({
    button: button,
    container: container,
    focusFallback: () => document.getElementById("preview-pane"),
    frame: frame,
    // Close the hidden pane’s menus.
    onHide: () => {
      closeFilterMenu();
      queryHtml(".root-details-trigger[aria-expanded=true]")?.click();
      window.MetabrowserSourceRefSelector?.mounted()?.close();
    },
    pane: pane,
  });
  return navCollapse;
}

document.addEventListener("DOMContentLoaded", async () => {
  initTooltip();
  initSettingsControl();
  initNavTabs();
  initHomeHeading();
  initRootDetails();
  initFilterBar();
  initNavScrollShadow();
  // Only a /view/ pathname selects a file; a hash is document state, never identity.
  var initialTarget = window.MetabrowserNavigationRoute.parse(
    location.pathname,
    location.search,
    location.hash,
  );
  // A root summary that waited while the page was hidden is sent when it shows.
  document.addEventListener("visibilitychange", resumeRootSummaryRefresh);
  var initialPath = initialTarget?.path.replace(/\/$/, "") || "";
  startIndexProgressPolling();
  // The tree fetch always runs: it supplies the header path and root
  // aggregates before any later recency selection repaints the panel
  // from /api/recent.
  await loadTree();
  // The selected preview and its on-demand plugin assets share the local
  // HTTP/1.1 connection pool with the tree. Start them after the first tree
  // request so a folder renderer cannot delay the navigation's usable rows.
  const started = navigationController.start().catch((error) => {
    console.error("Could not initialize browser navigation", error);
    settleUnclaimedPreview();
  });
  // For metabrowser.whenIdle.
  started.finally(() => window.dispatchEvent(new Event("metabrowser:first-view-settled")));
  // These application-lifetime controls are not prerequisites for a usable
  // tree. Start their ordered on-demand bundle only after the first tree
  // request settles, so eleven unrelated scripts cannot delay the inline row,
  // DOMContentLoaded, that request, inventory, or navigation. The catalog feed
  // repairs the ordering when its stream opened before the bundle arrived.
  initDeferredShellTools()
    .catch((error) => {
      console.error("metabrowser shell tools: init failed", { url: location.pathname }, error);
    })
    .finally(settleCommitRoutePreview);
  sourceFreshness().catch((error) => {
    console.error("metabrowser source freshness: init failed", error);
  });
  startSourceRefSelector().catch((error) => {
    console.error("metabrowser ref selector: init failed", error);
  });
  if (filesPanelUsesRecentSource()) {
    loadRecent(currentRecentFilterCursor());
  }
  initPaneResize("tree-resize", ".tree-pane", 180, null);
  if (initialPath) {
    const target = navigationController.current();
    revealInTree(initialPath, {
      instant: false,
      isCurrent: () =>
        navigationController.current() === target && (mainTabs?.active() ?? "files") === "files",
    });
  }
  // /api/events is the single source for tree decoration and
  // active-file badges; ActiveFileTracker emits fs.change ops
  // with active/labels populated.
  startInventoryEventStream();
});
