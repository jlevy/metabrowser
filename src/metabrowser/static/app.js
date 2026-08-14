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
const TEXT_PREVIEW_CHUNK_BYTES = 128 * 1024;

// Optional perf instrumentation. perf.js installs window.metabrowserPerf
// with measure/measureAsync helpers and a fetch wrapper; if it isn't
// loaded these calls fall through to plain invocation.
var _perf = (typeof window !== "undefined" && window.metabrowserPerf) || {
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
    return;
  }
  _perf.measureAsync(
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

function formatSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Size-weight convention — every shell surface delegates to the shared
// formatter runtime so plugins and core use the same threshold.
function sizeClass(bytes) {
  return window.MetabrowserFormatters.sizeClass(Number(bytes) || 0);
}
function sizeHtml(bytes, extraClass) {
  // Walker emits ``null`` aggregates while a directory is still
  // finalizing in the InventoryIndex. Render as a skeleton cell
  // so the row paints with shape; the SSE
  // ``fs.change`` patch flow (applyCellPatch below) replaces it
  // in place once the walker finalizes the dir.
  if (bytes === null || bytes === undefined) {
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
function parseTipNumber(value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  var n = Number(value);
  return Number.isFinite(n) ? n : null;
}
function formatCount(n) {
  return `${(n || 0).toLocaleString()} ${n === 1 ? "file" : "files"}`;
}
function countClass(n) {
  return window.MetabrowserFormatters.countClass(Number(n) || 0);
}
function countHtml(n, extraClass) {
  if (isPendingNumber(n)) {
    var pendCls = `count tally-pending ${extraClass || ""}`.trim();
    return `<span class="${pendCls}"></span>`;
  }
  var cls = `count ${countClass(n)} ${extraClass || ""}`.trim();
  return `<span class="${cls}">${formatCount(n)}</span>`;
}

// Path-styling convention — split at the final slash and render the
// directory portion muted, the basename in the inherited (typically
// bold) style. Use anywhere a path is shown in a context where the
// last segment is the focus (app header, file header, drawer titles).
function pathHtml(path, extraClass) {
  var raw = String(path == null ? "" : path);
  var trimmed = raw.replace(/\/+$/, "");
  var cls = `path ${extraClass || ""}`.trim();
  var i = trimmed.lastIndexOf("/");
  if (i < 0) {
    return `<span class="${cls}"><span class="path-base">${esc(trimmed || raw)}</span></span>`;
  }
  var dir = trimmed.slice(0, i + 1);
  var base = trimmed.slice(i + 1);
  return `<span class="${cls}"><span class="path-dir">${esc(dir)}</span><span class="path-base">${esc(base)}</span></span>`;
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

function highlightCode() {
  // highlight.js is an optional CDN enhancement; if it failed to load (offline,
  // blocked, or a kpress-rendered doc that never pulled it in), no-op rather
  // than throwing `hljs is not defined` and aborting the whole render.
  if (typeof hljs === "undefined") {
    return;
  }
  // Skip raw blocks inside collapsed log events; renderLogTab can ship
  // 1000+ such elements and hljs.highlightElement runs in ~1 ms each,
  // so eager highlighting torpedoes the first paint of a big log file.
  // The toggleEvent handler highlights on first expand instead.
  var nodes = document.querySelectorAll("pre code:not(.hljs)");
  var meta = { blocks: nodes.length, skipped_collapsed_log_blocks: 0 };
  return _perf.measure(
    "highlightCode",
    () => {
      nodes.forEach((el) => {
        if (el.closest(".log-event-raw")) {
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

function formatAge(mtimeSec) {
  // Walker emits ``null`` newest-mtime while finalizing.
  // Render skeleton; applyCellPatch fills it from fs.change.
  if (mtimeSec === null) {
    return '<span class="tally-pending tally-pending-narrow"></span>';
  }
  if (!mtimeSec) {
    return "";
  }
  var diffMs = Date.now() - mtimeSec * 1000;
  var absMs = Math.abs(diffMs);
  /** @type {Array<[string, number]>} */
  var steps = [
    ["y", 365 * 24 * 60 * 60 * 1000],
    ["mo", 30 * 24 * 60 * 60 * 1000],
    ["w", 7 * 24 * 60 * 60 * 1000],
    ["d", 24 * 60 * 60 * 1000],
    ["h", 60 * 60 * 1000],
    ["m", 60 * 1000],
  ];
  var label = "<1m";
  for (var i = 0; i < steps.length; i++) {
    if (absMs >= steps[i][1]) {
      label = Math.round(absMs / steps[i][1]) + steps[i][0];
      break;
    }
  }
  // Color code by freshness
  var cls = "age-old";
  if (absMs < 60 * 1000) {
    cls = "age-sec";
  } else if (absMs < 60 * 60 * 1000) {
    cls = "age-min";
  } else if (absMs < 24 * 60 * 60 * 1000) {
    cls = "age-hr";
  } else if (absMs < 7 * 24 * 60 * 60 * 1000) {
    cls = "age-day";
  } else if (absMs < 30 * 24 * 60 * 60 * 1000) {
    cls = "age-wk";
  }
  return `<span class="${cls}">${label}</span>`;
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

// ── SVG Icons ───────────────────────────────────────────────────

// Lucide `copy` (v1.17.0, ISC), used by clipboard actions.
var ICON_COPY =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>';

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
  // Cookie is the store (shared across ports); fall back to a pre-existing
  // localStorage value so an upgrade carries the user's prior choice forward.
  var fromCookie = readPrefCookie(THEME_MODE_KEY);
  if (fromCookie) {
    return normalizeThemeMode(fromCookie);
  }
  try {
    return normalizeThemeMode(localStorage.getItem(THEME_MODE_KEY) || "system");
  } catch (_e) {
    return "system";
  }
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
        e.stopPropagation();
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
        e.stopPropagation();
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

    var isOpen = () => wrap.getAttribute("aria-expanded") === "true";
    var setOpen = (open) => {
      wrap.setAttribute("aria-expanded", open ? "true" : "false");
    };
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      setOpen(!isOpen());
    });
    // Dismiss on outside click or Escape.
    document.addEventListener("click", (e) => {
      if (isOpen() && e.target instanceof Node && !wrap.contains(e.target)) {
        setOpen(false);
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && isOpen()) {
        setOpen(false);
      }
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
// Rule: major type carries the icon SHAPE; subtype carries the COLOR.
//   - All markdown uses `doc` (document shape); regular vs template
//     is communicated by color (green vs yellow).
//   - All structured-config files (yaml/json/toml/cfg/ini) use `list`;
//     color distinguishes yaml-family vs plain config.
//   - All source code uses `alignLeft` (horizontal rules — reads as
//     lines of code); one shared color today but a new subtype can
//     split off its own color later.
//   - Tabular (csv), log-stream (jsonl), and pdf each get their own
//     iconic shape because they're visually distinct formats.
//
// To add a new file type: append an entry to FILE_TYPES (order = match
// priority, longest/compound suffix first). To add a subtype split:
// introduce a new `--ft-<name>` token in styles.css + a `ft-<name>`
// class, then point the entry's `cls` at it.
function endsWithSuffix(suffix) {
  return (name) => name.endsWith(suffix);
}
function hasExt(ext) {
  return (name) => getExt(name) === ext;
}
function hasAnyExt(exts) {
  return (name) => exts.indexOf(getExt(name)) >= 0;
}

var FILE_TYPES = [
  // Markdown subtypes — compound suffixes first so `.runbook.md`
  // matches before the generic `.md` fallback.
  { match: endsWithSuffix(".runbook.md"), icon: "doc", cls: "ft-md-runbook" },
  { match: endsWithSuffix(".template.md"), icon: "doc", cls: "ft-md-template" },
  { match: endsWithSuffix(".form.md"), icon: "doc", cls: "ft-md-template" },
  { match: hasExt(".md"), icon: "doc", cls: "ft-md" },
  { match: hasExt(".txt"), icon: "doc", cls: "ft-text" },
  // Structured-config family.
  { match: hasExt(".yaml"), icon: "list", cls: "ft-yaml" },
  { match: hasExt(".yml"), icon: "list", cls: "ft-yaml" },
  { match: hasExt(".json"), icon: "list", cls: "ft-yaml" },
  { match: hasExt(".toml"), icon: "list", cls: "ft-yaml" },
  { match: hasExt(".cfg"), icon: "list", cls: "ft-config" },
  { match: hasExt(".ini"), icon: "list", cls: "ft-config" },
  // Log stream.
  { match: hasExt(".jsonl"), icon: "activity", cls: "ft-jsonl" },
  // Source code — one shared shape/color across the family; append
  // an extension to the list to pick it up.
  {
    match: hasAnyExt([".py", ".sh", ".js", ".ts"]),
    icon: "alignLeft",
    cls: "ft-code",
  },
  // Tabular + document.
  { match: hasExt(".csv"), icon: "grid", cls: "ft-csv" },
  { match: hasExt(".pid"), icon: "fileText", cls: "ft-text" },
  { match: hasExt(".pdf"), icon: "fileText", cls: "ft-text" },
];

function getFileIcon(name) {
  for (var i = 0; i < FILE_TYPES.length; i++) {
    if (FILE_TYPES[i].match(name)) {
      return { svg: ICON_SVG[FILE_TYPES[i].icon], cls: FILE_TYPES[i].cls };
    }
  }
  return { svg: ICON_SVG.file, cls: "" };
}

// Classify a path by basename and return the file-type `ft-*` subtype
// class (no icon). Exposed on `window.MetabrowserFileTypes` so viz.js can
// color dep-node icons using the same design system as the file tree —
// "icon = major type, color = subtype" applies everywhere a filename
// shows up in the UI.
function getFileTypeClass(pathOrName) {
  if (!pathOrName) {
    return "";
  }
  var slash = pathOrName.lastIndexOf("/");
  var name = slash >= 0 ? pathOrName.slice(slash + 1) : pathOrName;
  for (var i = 0; i < FILE_TYPES.length; i++) {
    if (FILE_TYPES[i].match(name)) {
      return FILE_TYPES[i].cls;
    }
  }
  return "";
}

if (typeof window !== "undefined") {
  window.MetabrowserFileTypes = {
    classFor: getFileTypeClass,
    iconFor: getFileIcon,
  };
}

// The application shell owns the catalog and search composition. Search modules
// receive snapshots and navigation callbacks through their public constructors;
// they never reach into app.js state directly.
/**
 * @typedef {object} QuickFileOpenOutcome
 * @property {HTMLElement | null} [focusTarget]
 * @property {string} [message]
 * @property {"opened" | "not-found" | "error" | "cancelled"} status
 */
var knownFileCatalog = null;
var quickFileSearchController = null;
var quickFilePalette = null;
var quickFileCatalogFeed = null;
var QUICK_FILE_RESULT_LIMIT = 100;

// ── Tree ────────────────────────────────────────────────────────

async function loadTree() {
  return _perf.measureAsync("loadTree", async () => {
    const resp = await fetch("/api/tree");
    if (!resp.ok) {
      console.warn(`loadTree: HTTP ${resp.status}`);
      const treeEl = document.getElementById("tree-content");
      if (treeEl) {
        treeEl.innerHTML =
          '<div class="preview-empty" role="alert">Could not load files. Refresh the page to try again.</div>';
      }
      return;
    }
    const data = await _perf.measureAsync(
      "apiTree:json",
      () => resp.json(),
      responsePerfMeta(resp, ""),
    );
    knownFileCatalog?.observeInitialTree(data.tree);
    var pathEl = queryHtml(".header-path");
    if (pathEl) {
      pathEl.innerHTML = pathHtml(data.root);
    }
    // Aggregate root size + file count + newest-mtime from top-level
    // children. Same shape as a folder tooltip — the served root reads
    // as "just another folder", the top-most one.
    var totalSize = 0;
    var totalFiles = 0;
    var newestMtime = 0;
    var hasPendingAggregate = false;
    for (var i = 0; i < data.tree.length; i++) {
      var n = data.tree[i];
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
      } else if (n.type === "file") {
        totalSize += n.size || 0;
        totalFiles += 1;
      }
      if ((n.mtime || 0) > newestMtime) {
        newestMtime = n.mtime || 0;
      }
    }
    var summaryFiles = hasPendingAggregate ? null : totalFiles;
    var summarySize = hasPendingAggregate ? null : totalSize;
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
    // Carry aggregates on the path link so the header tooltip handler
    // can pull them on hover without rebuilding from DOM.
    if (pathEl) {
      pathEl.dataset.tipName = data.root;
      pathEl.dataset.tipFiles = nullableDataValue(summaryFiles);
      pathEl.dataset.tipSize = nullableDataValue(summarySize);
      pathEl.dataset.tipMtime = nullableDataValue(newestMtime);
    }
    // Summary row sits at the top of the scrollable tree listing, not
    // in the sticky header — visible on first paint, scrolls away with
    // the rest of the tree. Keeps the upper nav header clean.
    // The index-wide tracked/ignored split is partial while scanning just
    // like the visible-tree fallback. Gate the summary object itself; passing
    // it through would make treeSummaryHtml prefer concrete partial values
    // over the pending fallback we selected above.
    var stableSummary = data.tally_cache_status === "scanning" ? null : data.summary;
    var summaryHtml = treeSummaryHtml(stableSummary, summaryFiles, summarySize);
    // Cached so the recency source, which paints over the whole panel,
    // can keep the same tally row above its own filtered count.
    _lastTreeSummaryHtml = summaryHtml;
    // Walker truncation banner. The InventoryIndex
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
    _lastTreeRender = {
      tree: data.tree,
      chromeHtml: truncationHtml + summaryHtml,
      tallyCacheStatus: data.tally_cache_status,
    };
    // A recency request may have started while this tree request was in
    // flight. Keep the authoritative cache current without painting over the
    // newer source selection.
    if (!filesPanelUsesRecentSource()) {
      renderFilesFromTree();
    }
  });
}

// Nav header tally. Tracked and ignored are counted separately —
// "12,582 files, 189.8 MB" hides that almost all of it is node_modules
// — and the ignored half is dimmed to match how those rows read in the
// tree below. Falls back to the combined figure when the server has no
// split to give (a subtree request, or an index still warming up).
function treeSummaryHtml(summary, fallbackFiles, fallbackSize) {
  if (!summary || typeof summary.files !== "number") {
    return (
      '<div class="tree-summary">' +
      `<span class="tree-summary-count">${countHtml(fallbackFiles)}</span>` +
      `<span class="tree-summary-size">${sizeHtml(fallbackSize)}</span>` +
      "</div>"
    );
  }
  // Deliberately NOT .tree-summary-count / .tree-summary-size: those
  // are the live-update targets of updateRootAggregatePresentation,
  // which patches in the gitignore-blind root aggregate and would
  // overwrite the tracked half with the combined total. The split row
  // owns its own classes and its own refresh path.
  var tracked =
    `<span class="tree-summary-tracked">${esc(formatCount(summary.files))}</span>` +
    `<span class="tree-summary-bytes">(${esc(formatSize(summary.size))})</span>`;
  var ignored = "";
  if (summary.ignored_files > 0) {
    ignored =
      '<span class="tree-summary-ignored">' +
      '<span class="tree-summary-plus">+</span>' +
      `${esc(summary.ignored_files.toLocaleString())} ignored` +
      `<span class="tree-summary-bytes">(${esc(formatSize(summary.ignored_size))})</span>` +
      "</span>";
  }
  return `<div class="tree-summary tree-summary-split">${tracked}${ignored}</div>`;
}

// The walker's root upsert carries gitignore-blind totals, so it
// cannot refresh the split. Refetch the summary instead — depth=0 so
// the response is the tally and nothing else — debounced, because the
// root aggregate is patched repeatedly while the walk converges.
var _summaryRefreshHandle = null;
function scheduleRootSummaryRefresh() {
  if (_summaryRefreshHandle || !document.querySelector(".tree-summary-split")) {
    return;
  }
  _summaryRefreshHandle = setTimeout(() => {
    _summaryRefreshHandle = null;
    fetch("/api/tree?depth=0")
      .then((resp) => (resp.ok ? resp.json() : null))
      .then((data) => {
        if (!data?.summary || !_lastTreeRender) {
          return;
        }
        var row = document.querySelector(".tree-summary-split");
        if (!row) {
          return;
        }
        // Only rebuild the bar when no dropdown is open. Replacing
        // its DOM mid-poll would drop focus out of a menu the user
        // is arrowing through, and this runs repeatedly while the
        // index warms up.
        if (updateFilterTallies(data)) {
          if (filterOpenMenu === null) {
            renderNavFilterBar();
          } else {
            patchOpenRecencyTallyCounts();
          }
        }
        var html = treeSummaryHtml(data.summary, null, null);
        row.outerHTML = html;
        // Keep both caches in step: chromeHtml feeds a source swap back
        // to the tree, and _lastTreeSummaryHtml is what the recency
        // source prepends. Updating only the first left the tally
        // showing first-paint figures under a recency filter.
        _lastTreeSummaryHtml = html;
        _lastTreeRender.chromeHtml = _lastTreeRender.chromeHtml.replace(
          /<div class="tree-summary tree-summary-split">.*?<\/div>$/,
          html,
        );
      })
      .catch(() => {
        // A failed refresh leaves the previous figures in place, which
        // is better than blanking a number the user is reading.
      });
  }, RECENT_RECLUSTER_DEBOUNCE_MS * 5);
}

// Last /api/tree payload plus the chrome rendered above it. Cached so
// clearing a recency filter can restore the full tree from memory
// instead of refetching on every chip click.
var _lastTreeRender = null;
// The tally row alone, so the recency source can reuse it verbatim.
var _lastTreeSummaryHtml = "";

// Paint #tab-files from that cache. Returns false when nothing has
// been fetched yet, so the caller can fall back to loadTree().
function renderFilesFromTree() {
  if (!_lastTreeRender) {
    return false;
  }
  var snapshot = _lastTreeRender;
  _perf.measure(
    "renderTreeNodes:root",
    () => {
      pendingTreePages.clear();
      pendingTreePageId = 0;
      var filesPanel = document.getElementById("tab-files");
      if (filesPanel) {
        filesPanel.innerHTML = snapshot.chromeHtml + renderTreeNodes(snapshot.tree, true);
      }
    },
    { nodes: snapshot.tree ? snapshot.tree.length : 0 },
  );
  applyTreeFilters();
  reconcilePendingTallyDiagnostics();
  return true;
}

function treeTruncationNoteHtml(maxFiles) {
  var reason = maxFiles
    ? `Metabrowser stopped after ${formatCount(maxFiles)} files`
    : "Metabrowser reached its file limit";
  return (
    '<div class="tree-truncation-note" role="status">' +
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

// Header hover tooltip — same folder-tooltip HTML the tree uses, so
// hovering the served-root path shows the same name / files / size /
// mtime block a hovered folder row shows below. One helper, one design.
document.addEventListener("DOMContentLoaded", () => {
  const headerPath = queryHtml(".header-path");
  if (!headerPath) {
    return;
  }
  headerPath.addEventListener("mouseenter", (e) => {
    var d = headerPath.dataset;
    if (!d.tipName) {
      return;
    }
    showTooltip(
      folderTooltipHtml(
        d.tipName,
        parseTipNumber(d.tipFiles),
        parseTipNumber(d.tipSize),
        parseTipNumber(d.tipMtime),
      ),
      e,
    );
  });
  headerPath.addEventListener("mousemove", positionTooltip);
  headerPath.addEventListener("mouseleave", hideTooltip);
});

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
  if (treeDirMetric(options) === TREE_DIR_METRIC_COUNT) {
    return countHtml(totalFiles, "tree-item-size");
  }
  if (isPendingNumber(totalSize) && !isPendingNumber(totalFiles)) {
    return countHtml(totalFiles, "tree-item-size");
  }
  return sizeHtml(totalSize, "tree-item-size");
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
    var mutedCls = "";
    if (node.gitignored) {
      mutedCls += " tree-item-gitignored";
    }
    if (node.type === "dir" && node.empty) {
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
      parts.push(
        `<div class="tree-item tree-folder ${stateClass}${mutedCls}" data-action="select-dir" data-path="${esc(node.path)}" data-tip-type="dir" data-tip-name="${esc(node.name)}" data-tip-files="${nullableDataValue(node.total_files)}" data-tip-size="${nullableDataValue(node.total_size)}" data-tip-mtime="${nullableDataValue(node.mtime || 0)}">`,
        `<span class="tree-toggle">${ICONS.toggle}</span>`,
        '<span class="tree-item-name">',
        esc(node.name),
        "</span>",
        '<span class="tree-item-age-inline">',
        dirAge,
        "</span>",
        dirChip,
        "</div>",
        '<div class="tree-children" style="display:',
        expanded ? "block" : "none",
        '">',
      );
      if (Array.isArray(node.children)) {
        parts.push(renderTreeNodes(node.children, false, options));
      } else {
        // Lazy stub: server emits `children: null` past the depth
        // cap. Render a placeholder; click-to-expand fetches the
        // subtree via /api/tree?path=...
        parts.push(
          '<div class="tree-lazy-placeholder" role="status" aria-label="Loading">' +
            '<span class="spinner spinner-sm" aria-hidden="true"></span>' +
            "</div>",
        );
      }
      parts.push("</div>");
    } else if (node.type === "symlink") {
      var linkAge = formatAge(node.mtime);
      parts.push(
        `<div class="tree-item tree-symlink${mutedCls}" data-action="select" data-path="${esc(node.path)}" data-tip-type="symlink" data-tip-name="${esc(node.name)}" data-tip-mtime="${node.mtime || 0}">`,
        '<span class="tree-item-icon">',
        ICONS.fileSymlink,
        "</span>",
        '<span class="tree-item-name">',
        esc(node.name),
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
        ? `<span class="compression-badge" title="${esc(compressionName)} compressed">${compressionGlyph}</span>`
        : "";
      var logicalExtAttr = node.logical_ext ? ` data-logical-ext="${esc(node.logical_ext)}"` : "";
      // The index's bounded compound-tail extension, which the type filter
      // matches on. Separate from data-logical-ext, which means "inner
      // extension of a compressed artifact" and drives icon dispatch.
      var extAttr = node.ext ? ` data-ext="${esc(node.ext)}"` : "";
      var compressedAttr = compressed ? ' data-compressed="1"' : "";
      parts.push(
        `<div class="tree-item tree-file${mutedCls}" data-action="select" data-path="${esc(node.path)}"${logicalExtAttr}${extAttr}${compressedAttr} data-tip-type="file" data-tip-name="${esc(node.name)}" data-tip-size="${node.size || 0}" data-tip-mtime="${node.mtime || 0}">`,
        '<span class="',
        iconCls,
        '">',
        fi.svg,
        compressionBadge,
        "</span>",
        '<span class="tree-item-name">',
        esc(node.name),
        "</span>",
        '<span class="tree-item-age-inline"><span class="tree-item-age">',
        fileAge,
        '</span><span class="tree-item-activity"></span></span>',
        sizeHtml(node.size, "tree-item-size"),
        "</div>",
      );
    }
  }
  if (hidden > 0) {
    var pageId = String(++pendingTreePageId);
    pendingTreePages.set(pageId, {
      nodes: nodes.slice(visibleCount),
      options: options,
    });
    parts.push(
      '<div class="tree-page-more" data-action="page-more" data-page-id="',
      pageId,
      '">',
      "Show ",
      String(hidden),
      " more (",
      String(nodes.length),
      " total)",
      "</div>",
    );
  }
  return parts.join("");
}

// ── Lazy subtree loading ──────────────────────────────────────

const subtreeCache = new Map();
const subtreeRetryTimers = new WeakMap();

function treeLazyLoadingHtml(message) {
  return (
    '<div class="tree-lazy-placeholder" role="status" aria-live="polite">' +
    '<span class="spinner spinner-sm" aria-hidden="true"></span>' +
    "<span>" +
    esc(message || "Loading folder…") +
    "</span>" +
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

function errorMessage(e) {
  return e?.message ? e.message : String(e || "An unknown error occurred.");
}

function responseErrorDetail(body, status) {
  var text = String(body || "").trim();
  if (text) {
    try {
      var parsed = JSON.parse(text);
      var detail = parsed?.error || parsed?.detail;
      if (typeof detail === "string" && detail.trim()) {
        return detail.trim();
      }
    } catch (_error) {
      // A plain-text response is already suitable for the preview message.
    }
    if (text.length <= 400) {
      return text;
    }
  }
  return `The request failed (HTTP ${status}).`;
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
    childrenEl.style.display !== "none"
  );
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

async function loadSubtree(path, childrenEl, options) {
  options = options || treeRenderOptionsForElement(childrenEl);
  if (subtreeCache.has(path)) {
    clearSubtreeRetry(childrenEl);
    _perf.measure(
      "renderTreeNodes:subtreeCache",
      () => {
        childrenEl.innerHTML = renderTreeNodes(subtreeCache.get(path), false, options);
      },
      { path: path, nodes: subtreeCache.get(path).length },
    );
    return;
  }
  childrenEl.innerHTML = treeLazyLoadingHtml("Loading folder…");
  try {
    const resp = await fetch(
      `/api/tree?path=${encodeURIComponent(path)}&depth=${TREE_SUBTREE_FETCH_DEPTH}`,
      { cache: "no-store" },
    );
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
    var tree = data.tree;
    knownFileCatalog?.observeLazyTree(tree);
    if (tree.length === 0 && data.tally_cache_status === "scanning") {
      childrenEl.innerHTML = treeLazyLoadingHtml("Still scanning this folder…");
      startIndexProgressPolling();
      scheduleSubtreeRetry(path, childrenEl);
      return;
    }
    clearSubtreeRetry(childrenEl);
    subtreeCache.set(path, tree);
    _perf.measure(
      "renderTreeNodes:subtree",
      () => {
        childrenEl.innerHTML = tree.length
          ? renderTreeNodes(tree, false, options)
          : '<div class="tree-lazy-placeholder">This folder is empty.</div>';
      },
      { path: path, nodes: tree.length },
    );
    // Newly rendered children carry no filter classes yet, so without
    // this an expand under an active filter reveals the whole folder.
    applyTreeFilters();
    reconcilePendingTallyDiagnostics();
  } catch (e) {
    console.warn(`loadSubtree failed for ${path}`, e);
    clearSubtreeRetry(childrenEl);
    childrenEl.innerHTML = treeLazyFailureHtml(
      "Could not load this folder. Collapse and reopen it to try again.",
    );
  }
}

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

function initTooltip() {
  tooltipEl = document.createElement("div");
  tooltipEl.className = "custom-tooltip";
  document.body.appendChild(tooltipEl);
}

function showTooltip(html, e) {
  clearTimeout(tooltipTimer);
  // Small delay before appearing so tooltips don't flash when moving across items
  tooltipTimer = setTimeout(() => {
    tooltipEl.innerHTML = html;
    tooltipEl.style.display = "block";
    positionTooltip(e);
    // Trigger fade-in on next frame
    requestAnimationFrame(() => {
      tooltipEl.classList.add("visible");
    });
  }, 300);
}

function positionTooltip(e) {
  var x = e.clientX + 12;
  var y = e.clientY + 16;
  var rect = tooltipEl.getBoundingClientRect();
  if (x + rect.width > window.innerWidth - 8) {
    x = e.clientX - rect.width - 8;
  }
  if (y + rect.height > window.innerHeight - 8) {
    y = e.clientY - rect.height - 8;
  }
  tooltipEl.style.left = `${x}px`;
  tooltipEl.style.top = `${y}px`;
}

function hideTooltip() {
  clearTimeout(tooltipTimer);
  tooltipEl.classList.remove("visible");
  // Let the fade-out transition finish before hiding
  tooltipTimer = setTimeout(() => {
    tooltipEl.style.display = "none";
  }, 150);
}

if (typeof window !== "undefined") {
  window.MetabrowserTooltip = {
    show: (html, e) => {
      showTooltip(html, e);
    },
    move: positionTooltip,
    hide: hideTooltip,
  };
}

// Tooltip size/count rows reuse the shared .size / .count classes so
// they match the hue of the same data everywhere else (tree column,
// file header, app header). Tooltip still uses formatExactSize()
// (exact bytes) for the precise-value read hovering implies; the
// visual category (this number is a size) is carried by the class.
function _tipSize(bytes) {
  if (isPendingNumber(bytes)) {
    return '<span class="tip-loading">Loading size…</span>';
  }
  var cls = `size ${sizeClass(bytes)}`.trim();
  return `<span class="${cls}">${formatExactSize(bytes || 0)}</span>`;
}
function _tipCount(n) {
  if (isPendingNumber(n)) {
    return '<span class="tip-loading">Loading file count…</span>';
  }
  return `<span class="count">${formatCount(n)}</span>`;
}

function treeTooltipNameHtml(name, includeName) {
  return includeName === false ? "" : `<div class="tip-name">${esc(name)}</div>`;
}

function fileTooltipHtml(name, size, mtime, includeName) {
  return (
    treeTooltipNameHtml(name, includeName) +
    '<div class="tip-detail">' +
    _tipSize(size) +
    "</div>" +
    '<div class="tip-detail">' +
    formatTimestamp(mtime) +
    "</div>"
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
  return (
    treeTooltipNameHtml(name, includeName) +
    '<div class="tip-detail">' +
    _tipCount(totalFiles) +
    "</div>" +
    '<div class="tip-detail">' +
    _tipSize(totalSize) +
    "</div>" +
    '<div class="tip-detail">' +
    formatTimestamp(mtime) +
    "</div>"
  );
}

// ── Tree interactions ───────────────────────────────────────────

const treePane = /** @type {HTMLElement} */ (document.getElementById("tree-pane"));
if (!treePane) {
  throw new Error("Metabrowser shell is missing #tree-pane");
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
    // The tree row already shows the name, so the hover tooltip omits it and
    // shows size + date only (the name would be duplicative).
    var includeName = false;
    var html;
    if (d.tipType === "dir") {
      html = folderTooltipHtml(
        d.tipName,
        parseTipNumber(d.tipFiles),
        parseTipNumber(d.tipSize),
        parseTipNumber(d.tipMtime),
        includeName,
      );
    } else if (d.tipType === "symlink") {
      html = symlinkTooltipHtml(d.tipName, parseTipNumber(d.tipMtime), includeName);
    } else {
      html = fileTooltipHtml(
        d.tipName,
        parseTipNumber(d.tipSize),
        parseTipNumber(d.tipMtime),
        includeName,
      );
    }
    showTooltip(html, e);
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
var hoverPrefetchInFlight = 0;

function shouldPrefetchFile(item) {
  var path = item.dataset.path;
  if (!path || fileCache.has(path) || activeFiles.has(path)) {
    return false;
  }
  if (+(item.dataset.tipSize || 0) > FILE_PREFETCH_MAX_BYTES) {
    return false;
  }
  // For .gz files the server attaches `data-logical-ext`; key the
  // "skip prefetch for JSONL" rule off the inner extension so
  // `events.jsonl.gz` is treated identically to `events.jsonl`.
  var ext = (item.dataset.logicalExt || getExt(path)).toLowerCase();
  return ext !== ".jsonl";
}

function abortHoverPrefetch() {
  clearTimeout(hoverPrefetchTimer);
  hoverPrefetchTimer = null;
  hoverPrefetchPath = "";
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
  fetch(`/api/file?path=${encodeURIComponent(path)}`, options)
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
      if (hoverPrefetchPath === path) {
        hoverPrefetchController = null;
      }
    });
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
    window.MetabrowserTreeExpansion.setFolderExpanded(folder, ch, true);
    if (ch.querySelector(":scope > .tree-lazy-placeholder")) {
      await loadSubtree(folder.dataset.path, ch);
    }
    await expandAllDescendants(ch);
  }
}

function collapseAllDescendants(container) {
  container.querySelectorAll(".tree-children").forEach((ch) => {
    ch.style.display = "none";
    var folder = ch.previousElementSibling;
    if (folder?.classList.contains("tree-folder")) {
      window.MetabrowserTreeExpansion.setFolderExpanded(folder, ch, false);
    }
  });
}

function toggleTreeFolder(item, recursive) {
  var children = /** @type {HTMLElement | null} */ (item.nextElementSibling);
  if (!children?.classList.contains("tree-children")) {
    return;
  }
  var expanded = window.MetabrowserTreeExpansion.toggleFolderExpanded(item, children);
  if (!expanded) {
    if (recursive) {
      collapseAllDescendants(children);
    }
    return;
  }
  var needsLoad = !!children.querySelector(":scope > .tree-lazy-placeholder");
  if (needsLoad) {
    var load = loadSubtree(item.dataset.path, children);
    if (recursive) {
      load.then(() => expandAllDescendants(children));
    }
  } else if (recursive) {
    expandAllDescendants(children);
  }
}

treePane.addEventListener("click", (e) => {
  // Pagination "Show N more" sentinel is its own row (not .tree-item)
  // so it doesn't accidentally pick up tree-item click semantics like
  // hover-prefetch or selection.
  var target = eventTargetElement(e);
  if (!target) {
    return;
  }
  var pageRow = /** @type {HTMLElement | null} */ (target.closest(".tree-page-more"));
  if (pageRow) {
    var pageId = pageRow.dataset.pageId;
    var page = pendingTreePages.get(pageId);
    var nextBatch = page?.nodes;
    if (nextBatch) {
      pendingTreePages.delete(pageId);
      pageRow.outerHTML = renderTreeNodes(nextBatch, false, page.options);
      // Same reason as loadSubtree: a deferred page arrives unfiltered.
      applyTreeFilters();
      reconcilePendingTallyDiagnostics();
    }
    return;
  }
  const item = /** @type {HTMLElement | null} */ (target.closest(".tree-item"));
  if (!item) {
    return;
  }
  const action = item.dataset.action;
  if (action === "select") {
    setSelectedPath(item.dataset.path);
    navigateToPath(item.dataset.path || "");
  } else if (action === "select-dir") {
    setSelectedPath(item.dataset.path);
    navigateToPath(item.dataset.path ? `${item.dataset.path}/` : "/");
    toggleTreeFolder(item, e.shiftKey);
  }
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
    return;
  }
  queryHtmlAll(".tree-item").forEach((el) => {
    if (el.dataset.path === path) {
      el.classList.add("selected");
    }
  });
}

// ── Nav pane ────────────────────────────────────────────────────
//
// One Files panel, two data sources. The default source is the
// /api/tree walk. When the recency filter is set and the treatment is
// hide, the panel instead renders /api/recent's flat newest-first leaf
// list (filter + gitignore resolved server-side), clustered here via
// ``clusterRecentTreeJs`` — clustering is a rendering concern, owned
// by this layer. See ``metabrowser/recent.py`` for the layering
// rationale, and the nav filter bar section below for the switch.

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
  await loadTree();
  // The user can change or clear the filter while the tree request is in
  // flight. Re-read the current window after the await so recovery never
  // restores an obsolete recency source over the user's newer selection.
  var recency = filterState ? filterState.get().recency : null;
  if (recency && recency !== "all") {
    loadRecent(recency);
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

window.addEventListener("pagehide", () => pendingTallyWatchdog.dispose(), { once: true });

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
    el.hidden = true;
    indexProgressLastRendered = meta || null;
    return;
  }
  // `meta.indexed_files` can be missing (server hasn't reported yet),
  // a true zero (scan started but nothing finalized), or a positive
  // count. Only show "~N files scanned" once we have a positive count;
  // otherwise the spinner plus a generic "Scanning…" label is the
  // right UX — a literal "~0 files scanned" reads as "scan stuck".
  var rawFiles = meta.indexed_files;
  var files = typeof rawFiles === "number" && rawFiles > 0 ? rawFiles : null;
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

async function refreshTreeIfPendingTallies() {
  if (indexProgressCompletionRefreshInFlight) {
    return;
  }
  if (!document.querySelector("#tab-files .tally-pending")) {
    return;
  }
  indexProgressCompletionRefreshInFlight = true;
  try {
    await loadTree();
    // Match diagnostic recovery: the tree request updates the authoritative
    // cache but deliberately does not paint over an active recency source.
    // Re-read after the await so a filter change during the request wins.
    var recency = filterState ? filterState.get().recency : null;
    if (recency && recency !== "all") {
      loadRecent(recency);
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
    if (shouldRenderIndexProgress(meta, force)) {
      renderIndexProgress(meta);
    }
    if (!indexProgressIsActive(meta)) {
      if (meta?.truncated) {
        ensureTreeTruncationNote(meta.max_files);
      }
      renderIndexProgress(meta);
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
  if (indexProgressTimer) {
    return;
  }
  refreshIndexProgress(true);
  indexProgressTimer = setInterval(() => {
    refreshIndexProgress(false);
  }, INDEX_PROGRESS_POLL_MS);
}

function initNavTabs() {
  const navBar = queryHtml(".nav-tab-bar");
  if (!navBar) {
    return;
  }
  queryHtmlAll(".tab-btn", navBar).forEach((btn) => {
    btn.addEventListener("click", () => {
      var tabId = btn.dataset.tab;
      navBar.querySelectorAll(".tab-btn").forEach((b) => {
        b.classList.remove("active");
        b.setAttribute("aria-selected", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-selected", "true");
      queryHtmlAll("[data-tab-content]", treePane).forEach((panel) => {
        panel.style.display = panel.dataset.tabContent === tabId ? "" : "none";
      });
    });
  });
}

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
function initNavScrollShadow() {
  const shadowTarget = document.getElementById("nav-filter-bar") || queryHtml(".nav-tab-bar");
  const content = document.getElementById("tree-content");
  if (!shadowTarget || !content) {
    return;
  }
  const scrollNavBar = shadowTarget;
  const scrollContent = content;
  function update() {
    if (scrollContent.scrollTop > 0) {
      scrollNavBar.classList.add("scrolled");
    } else {
      scrollNavBar.classList.remove("scrolled");
    }
  }
  // Passive listener — we never preventDefault — so the browser
  // can keep scroll responsive while we just read scrollTop.
  scrollContent.addEventListener("scroll", update, { passive: true });
  update();
}

// Window key → seconds-back from "now", injected from the one
// authoritative mapping in metabrowser/settings.py.
const _RECENT_WINDOW_SECONDS = _METABROWSER_SETTINGS.RECENT_WINDOW_SECONDS || {};

// Recent is a hybrid
// of "snapshot from /api/recent" + "live FileStore overlay".
//
// The SSE stream is scoped to ``root-depth-2`` (the right scope
// for tree decoration). FileStore therefore does NOT contain
// files at depth 3+. A FileStore-only Recent panel was correct
// for 1h windows (recent edits cluster near the visible tree)
// but silently truncated 24h / 7d / 30d / all to whatever
// happened to fall within ``root-depth-2``.
//
// New flow:
// * On chip change, fetch ``/api/recent?window=...`` (server
//   reads ``InventoryIndex`` at ``all-known`` scope, so the
//   payload covers the whole window). Use the response's
//   ``entries_flat`` field as the base set.
// * Live overlay: ``fs.change`` upserts/removes mutate the base
//   set in place when they fall inside the active window. The
//   panel re-clusters + re-paints (debounced) so newly-written
//   files appear without a refetch.
// * The base set is keyed by path so a file edited twice doesn't
//   double-count.
//
// FileStore stays the single source of truth for the Files tab
// and tree decoration; Recent has its own base because it needs
// wider coverage than SSE's scope.
var recentBaseEntries = new Map(); // path -> recent-flat dict
var recentTotalMatching = 0;
var recentTruncated = false;
var recentInflight = null; // AbortController for the in-flight chip fetch
// Server-published set of dir paths the Recent panel paints gray.
// Pathspec is a backend concern; the SPA never re-derives this. A
// dir node produced by ``clusterRecentTreeJs`` is gray iff its
// compact path appears here. Refreshed on every /api/recent fetch;
// live fs.change ops can't grow it (a newly recent dir under a
// gitignored subtree goes un-marked until the next chip refetch).
var _GITIGNORED_DIR_PATHS = new Set();

function loadRecent(windowKey) {
  // A timer scheduled for the previous window must not repaint its
  // cached rows while this replacement request is still loading.
  clearRecentExpiryRecheck();
  // Lock the user's window intent synchronously so a second chip
  // click can dedup against it.
  currentRecentWindow = windowKey;
  recentEverLoaded = true;
  fetchRecent(windowKey);
}

function fetchRecent(windowKey) {
  if (recentInflight) {
    recentInflight.abort();
    recentInflight = null;
  }
  var results = recentResultsHost();
  // Always replace the panel, not just on a cold start. This source
  // paints over the full tree, so leaving the previous contents up
  // would show an unfiltered tree under a recency window that is
  // already selected — and a warm `recentBaseEntries` from an earlier
  // window is the wrong window's answer, not this one's.
  if (results) {
    results.innerHTML = '<div class="recent-empty">Loading recent files…</div>';
  }
  var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
  recentInflight = ctrl;
  var url =
    "/api/recent?window=" +
    encodeURIComponent(windowKey) +
    "&limit=" +
    encodeURIComponent(String(RECENT_LIMIT)) +
    // Asking for rows we are about to hide would spend the server's
    // cap on them; the filter drops gitignored entries anyway when
    // Show ignored is off.
    (filterState && filterState.get().showIgnored === false ? "&include_ignored=0" : "");
  var fetchOpts = ctrl ? { signal: ctrl.signal } : undefined;
  _perf
    .measureAsync(
      "apiRecent:fetch",
      () =>
        fetch(url, fetchOpts).then((resp) => {
          if (!resp.ok) {
            throw new Error(`recent fetch failed: ${resp.status}`);
          }
          return resp.json();
        }),
      { window: windowKey },
    )
    .then((data) => {
      var flat = data?.entries_flat || [];
      knownFileCatalog?.observeRecent(flat);
      if (windowKey !== currentRecentWindow) {
        return; // user clicked another chip
      }
      recentBaseEntries = new Map();
      for (var i = 0; i < flat.length; i++) {
        var f = flat[i];
        if (f?.path) {
          recentBaseEntries.set(f.path, f);
        }
      }
      recentTotalMatching = data?.total_matching || flat.length;
      recentTruncated = !!data?.truncated;
      var ignoredDirs = data?.gitignored_dirs || [];
      _GITIGNORED_DIR_PATHS = new Set(ignoredDirs);
      // renderRecentFromBase reapplies filters and restores the
      // selection; nothing more to do here.
      renderRecentFromBase();
    })
    .catch((err) => {
      if (err && err.name === "AbortError") {
        return;
      }
      if (windowKey !== currentRecentWindow) {
        return;
      }
      if (results) {
        results.innerHTML =
          '<div class="recent-empty" role="alert">Could not load recently modified files. Refresh the page to try again.</div>';
      }
    })
    .finally(() => {
      if (recentInflight === ctrl) {
        recentInflight = null;
      }
    });
}

// Render the Recent panel from ``recentBaseEntries`` (the chip-
// fetched base + any live ``fs.change`` overlay). Called by
// fetchRecent on chip change AND by ``_scheduleRecentRecompute``
// on every fs.change burst.
// Files the recency response still shows once the other dimensions
// apply. The recency window itself was resolved server-side, so only
// type, size, and gitignored visibility can rule an entry out here.
//
// Recomputed on every filter pass rather than cached from the last
// render: type and size changes run applyTreeFilters alone, so a
// cached count kept the previous value while the rows updated.
function countRecentMatches(entries, nowSec) {
  if (!filterState) {
    return entries.length;
  }
  var st = filterState.get();
  var n = 0;
  for (var i = 0; i < entries.length; i++) {
    var e = entries[i];
    if (!st.showIgnored && e.gitignored) {
      continue;
    }
    if (
      filterState.rowMatches(
        { mtime: e.mtime, size: e.size, path: e.path, ext: e.logical_ext || e.ext || "" },
        // The window already selected these rows; asking again here
        // would re-test an mtime the server has ruled on.
        Object.assign({}, st, { recency: "all" }),
        nowSec,
      )
    ) {
      n += 1;
    }
  }
  return n;
}

function renderRecentFromBase() {
  const results = recentResultsHost();
  if (!results) {
    return;
  }
  var entries = recentEntriesFromBase({
    window: currentRecentWindow,
    limit: RECENT_LIMIT,
  });
  _perf.measure(
    "renderRecent:root",
    () => {
      if (entries.length === 0) {
        results.innerHTML = renderRecentList({ tree: [] });
        return;
      }
      var nowSec = Date.now() / 1000;
      var tree = clusterRecentTreeJs(entries, nowSec, RECENT_CLUSTER_PCT);
      results.innerHTML = renderRecentList({ tree: tree });
    },
    { items: recentBaseEntries.size },
  );
  scheduleRecentExpiryRecheck(entries);
  // Recency is already resolved server-side; the remaining
  // dimensions still apply over these rows.
  applyTreeFilters();
  if (currentPath) {
    setSelectedPath(currentPath);
  }
  reconcilePendingTallyDiagnostics();
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

// Apply a live FileStore-equivalent op to the recent base. Used
// by the fs.change subscriber so an upsert in the active window
// shows up without a /api/recent refetch. Out-of-window upserts
// are dropped; in-window upserts overwrite by path. ``op`` is the
// fs.change op shape: ``{op, entry?, path?}`` matching events.py.
function recentBaseApplyOp(op) {
  if (!recentEverLoaded) {
    return false;
  }
  // No active window means the panel is not on this source, so there
  // is no overlay to keep current — and every op would otherwise be
  // retained, since none of them can be judged against a window that
  // does not exist.
  if (!currentRecentWindow) {
    return false;
  }
  if (!op) {
    return false;
  }
  if (op.op === "upsert") {
    var e = op.entry;
    if (e?.type !== "file") {
      return false;
    }
    var dict = recentEntryFromFsEntry(e);
    // Only retain entries that fall inside the active window;
    // anything older than the window's seconds-back is dropped.
    var seconds = _RECENT_WINDOW_SECONDS[currentRecentWindow];
    // `undefined`, not `null`, is what an unknown key gives — and the
    // window is cleared to "" when the panel leaves this source. The
    // old `!== null` guard let that through, so the cutoff became NaN,
    // every comparison against it was false, and the base map grew
    // without bound while the plain tree was on screen.
    if (typeof seconds === "number") {
      var cutoffSec = Date.now() / 1000 - seconds;
      if (dict.mtime < cutoffSec) {
        // Out-of-window upsert — make sure any stale base entry
        // for this path is removed (e.g. a file aged past 1h).
        if (recentBaseEntries.has(dict.path)) {
          recentBaseEntries.delete(dict.path);
          return true;
        }
        return false;
      }
    }
    recentBaseEntries.set(dict.path, dict);
    return true;
  }
  if (op.op === "remove") {
    if (recentBaseEntries.has(op.path)) {
      recentBaseEntries.delete(op.path);
      return true;
    }
    return false;
  }
  if (op.op === "move") {
    var prev = recentBaseEntries.get(op.from_path);
    if (!prev) {
      return false;
    }
    recentBaseEntries.delete(op.from_path);
    var moved = Object.assign({}, prev, {
      path: op.to_path,
      name: op.to_path.split("/").pop(),
    });
    recentBaseEntries.set(op.to_path, moved);
    return true;
  }
  return false;
}

// Convert an FsEntry (the FileStore wire shape) into the recent-
// flat dict shape (mtime in seconds, no mtime_ns / kind / labels).
// Mirror of metabrowser.recent._file_entry_to_recent_dict.
function recentEntryFromFsEntry(entry) {
  var out = {
    name: entry.name,
    path: entry.path,
    type: "file",
    size: entry.size || 0,
    mtime: (entry.mtime_ns || 0) / 1e9,
    // Mirror _file_entry_to_recent_dict: without the index's compound
    // tail, a file that reaches this panel only through the live
    // overlay would be matched on its last dotted suffix while the
    // rendered rows are matched on the tail, so a compound pick could
    // hide it.
    ext: entry.ext || "",
  };
  if (entry.gitignored) {
    out.gitignored = true;
  }
  return out;
}

// Produce a flat newest-first list of recent-flat dicts from the
// chip-fetched + live-overlaid ``recentBaseEntries`` map. Same
// shape the cluster helper expects. Window predicate re-applied
// here so a base entry that has aged out since the last fetch is
// dropped on the floor.
function recentEntriesFromBase(opts) {
  opts = opts || {};
  var windowKey = opts.window || currentRecentWindow;
  var limit = opts.limit || RECENT_LIMIT;
  var extFilter = opts.ext || null; // null or string[]
  var prefixFilter = opts.prefix || null; // null or string

  var seconds = _RECENT_WINDOW_SECONDS[windowKey];
  var nowSec = Date.now() / 1000;
  var minMtime = seconds === null ? 0 : nowSec - seconds;

  var matches = [];
  recentBaseEntries.forEach((entry) => {
    if (entry?.type !== "file") {
      return;
    }
    if ((entry.mtime || 0) < minMtime) {
      return;
    }
    if (extFilter || prefixFilter) {
      // Recent-flat dicts don't carry ``ext`` (server pre-filters
      // by extension); pull it from the path tail when callers
      // pass an ext filter.
      if (extFilter) {
        var name = entry.name || (entry.path || "").split("/").pop();
        var dot = name.lastIndexOf(".");
        var ext = dot >= 0 ? name.slice(dot) : "";
        if (extFilter.indexOf(ext) === -1) {
          return;
        }
      }
      if (prefixFilter && (entry.path || "").indexOf(prefixFilter) !== 0) {
        return;
      }
    }
    matches.push(entry);
  });
  matches.sort((a, b) => (b.mtime || 0) - (a.mtime || 0));
  if (matches.length > limit) {
    matches = matches.slice(0, limit);
  }
  return matches;
}

// Authoritative implementation of Recent clustering. Single-dir
// compaction + RECENT_CLUSTER_PCT cluster-collapse are presentation
// rules and live here; the Python side filters and resolves
// gitignore but does not cluster.
//
// Inputs the server is responsible for: ``files`` (filtered, sorted,
// per-leaf gitignored flag set) and ``_GITIGNORED_DIR_PATHS`` (the
// pathspec-derived set of dirs to gray). This function never decides
// gitignore status — it only maps a server-published path into a
// node flag.
function clusterRecentTreeJs(files, nowSec, pct) {
  pct = typeof pct === "number" ? pct : 0.05;
  // Build the directory tree.
  /** @type {{name: string, subdirs: Record<string, any>, leaves: Array<any>}} */
  var root = { name: "", subdirs: {}, leaves: [] };
  for (var fi = 0; fi < files.length; fi++) {
    var f = files[fi];
    var parts = f.path.split("/");
    var node = root;
    for (var pi = 0; pi < parts.length - 1; pi++) {
      var part = parts[pi];
      if (!node.subdirs[part]) {
        node.subdirs[part] = { name: part, subdirs: {}, leaves: [] };
      }
      node = node.subdirs[part];
    }
    node.leaves.push(f);
  }

  function emitDir(node, path) {
    var children = [];
    var subnames = Object.keys(node.subdirs).sort();
    for (var si = 0; si < subnames.length; si++) {
      var subname = subnames[si];
      var sub = node.subdirs[subname];
      var subPath = path ? `${path}/${subname}` : subname;
      children.push(emitDir(sub, subPath));
    }
    for (var li = 0; li < node.leaves.length; li++) {
      var leaf = node.leaves[li];
      var leafCopy = {};
      for (var k in leaf) {
        leafCopy[k] = leaf[k];
      }
      leafCopy.type = "file";
      children.push(leafCopy);
    }

    // Single-dir compaction.
    var compactName = node.name;
    var compactPath = path;
    while (children.length === 1 && children[0].type === "dir") {
      var sole = children[0];
      compactName = compactName ? `${compactName}/${sole.name}` : sole.name;
      compactPath = sole.path;
      children = sole.children;
    }
    children.sort((a, b) => (b.mtime || 0) - (a.mtime || 0));

    var totalFiles = 0,
      totalSize = 0,
      newestMtime = 0;
    for (var ci = 0; ci < children.length; ci++) {
      var c = children[ci];
      if (c.type === "dir") {
        totalFiles += c.total_files || 0;
        totalSize += c.total_size || 0;
      } else {
        totalFiles += 1;
        totalSize += c.size || 0;
      }
      if ((c.mtime || 0) > newestMtime) {
        newestMtime = c.mtime || 0;
      }
    }

    var ages = [];
    for (var ai = 0; ai < children.length; ai++) {
      var ac = children[ai];
      if ((ac.mtime || 0) > 0) {
        ages.push(nowSec - ac.mtime);
      }
    }
    var coherent = _agesWithinPctJs(ages, pct);

    var out = {
      type: "dir",
      name: compactName,
      path: compactPath,
      children: children,
      total_files: totalFiles,
      total_size: totalSize,
      mtime: newestMtime,
      clustered: coherent,
    };
    // Coherent (clustered) dirs collapse explicitly so the cluster
    // chip stands in for its children. For non-clustered dirs we
    // leave ``expanded`` unset so renderTreeNodes can apply the same
    // viewport-bounded expansion plan as the Files panel.
    if (coherent) {
      out.expanded = false;
    }
    if (_GITIGNORED_DIR_PATHS?.has(compactPath)) {
      out.gitignored = true;
    }
    return out;
  }

  var topNames = Object.keys(root.subdirs).sort();
  var out = [];
  for (var ti = 0; ti < topNames.length; ti++) {
    var n = topNames[ti];
    out.push(emitDir(root.subdirs[n], n));
  }
  for (var lj = 0; lj < root.leaves.length; lj++) {
    var lc = {};
    for (var lk in root.leaves[lj]) {
      lc[lk] = root.leaves[lj][lk];
    }
    lc.type = "file";
    out.push(lc);
  }
  out.sort((a, b) => (b.mtime || 0) - (a.mtime || 0));
  return out;
}

function _agesWithinPctJs(ages, pct) {
  if (ages.length <= 1) {
    return true;
  }
  var lo = ages[0],
    hi = ages[0];
  for (var i = 1; i < ages.length; i++) {
    if (ages[i] < lo) {
      lo = ages[i];
    }
    if (ages[i] > hi) {
      hi = ages[i];
    }
  }
  if (hi <= 0) {
    return true;
  }
  return (hi - lo) / hi <= pct;
}

// Both tree sources paint into the Files panel now that Recent is a
// filter rather than a tab.
function recentResultsHost() {
  return document.getElementById("tab-files");
}

function renderRecentList(data) {
  var tree = data.tree || [];
  if (tree.length === 0) {
    var emptyText =
      currentRecentWindow === "live"
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
  var body = renderTreeNodes(tree, true, { dirMetric: TREE_DIR_METRIC_COUNT });
  // Keep the tally row this source would otherwise paint over. The
  // filtered count that hangs off it is written by applyTreeFilters,
  // which runs next and is the only place that knows how many rows
  // survived every dimension rather than just the recency one.
  return (_lastTreeSummaryHtml || "") + body;
}

// ── Navigation filter bar ───────────────────────────────────────
//
// One always-visible row (recency) plus a drawer holding type, size,
// and gitignored visibility. Controls come from the shared chip family
// (static/filter_controls.js) and every click writes through to the
// shared state (static/filter_state.js), so the bar holds no state of
// its own.
//
// The drawer carries no section headings: an extension menu, a size
// ramp, and a checkbox labelled "Show ignored" say what they are.
//
// See docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md.

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
// keeps the freshest colour and spells out its exact server-owned
// cutoff in the accessible title.
var FILTER_RECENCY_OPTIONS = [
  {
    value: "live",
    label: "Live",
    title: `Files modified in the past ${_RECENT_WINDOW_SECONDS.live} seconds`,
    ageClass: "age-sec",
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

// Named shorthands at the top of the type menu. The server injects the
// vocabulary so the index can count the same tokens the browser uses.
var FILTER_TYPE_PRESETS = _METABROWSER_SETTINGS.FILTER_TYPE_PRESETS || [];

// The extension menu is built from what the folder actually contains,
// not a fixed vocabulary, so it never offers a type with nothing
// behind it and never omits one the tree is full of.
var FILTER_TYPE_MENU_MAX = 20;

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

function filterRecencyOptions() {
  const showIgnored = filterState ? filterState.get().showIgnored : true;
  const counts = new Map(
    _recencyTally.map((row) => [row[0], showIgnored ? row[1] + row[2] : row[1]]),
  );
  return FILTER_RECENCY_OPTIONS.map((option) => ({
    ...option,
    count: counts.get(option.value) || 0,
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
    if (typeof count === "number" && countEl) {
      countEl.textContent = count.toLocaleString();
    }
  }
}

function filterTypePresets() {
  const showIgnored = filterState ? filterState.get().showIgnored : true;
  const counts = new Map(
    _typePresetTally.map((row) => [row[0], showIgnored ? row[1] + row[2] : row[1]]),
  );
  return FILTER_TYPE_PRESETS.map((preset) => ({
    ...preset,
    count: counts.get(preset.id) || 0,
  }));
}

function filterTypeFamilies() {
  const showIgnored = filterState ? filterState.get().showIgnored : true;
  const counts = new Map(
    _typeFamilyTally.map((row) => [row[0], showIgnored ? row[1] + row[2] : row[1]]),
  );
  return (window.MetabrowserFileTypeTaxonomy?.families || [])
    .map((family) => ({
      id: `family:${family.id}`,
      label: family.label,
      values: family.extensions.slice(),
      count: counts.get(family.id) || 0,
    }))
    .filter((family) => family.count > 0);
}

function filterTypePresetSections() {
  return [
    { id: "categories", presets: filterTypePresets() },
    { id: "families", presets: filterTypeFamilies() },
  ];
}

function allFilterTypePresets() {
  return filterTypePresetSections().flatMap((section) => section.presets);
}

function filterTypeOptions() {
  const showIgnored = filterState ? filterState.get().showIgnored : true;
  const source = _canonicalExtensionTally.length > 0 ? _canonicalExtensionTally : _extensionTally;
  const ranked = source
    .map(
      (row) => /** @type {[string, number]} */ ([row[0], showIgnored ? row[1] + row[2] : row[1]]),
    )
    // An extension that exists only under gitignored paths has nothing
    // to offer once those rows are hidden.
    .filter((row) => row[1] > 0)
    // Re-rank on the count actually being shown. The server ranks by
    // the total, so hiding gitignored rows would otherwise leave the
    // menu ordered by numbers that are no longer on screen — .py with
    // 157 tracked files sorting below .d.ts with one.
    .sort((a, b) => (b[1] === a[1] ? (a[0] < b[0] ? -1 : 1) : b[1] - a[1]));
  // A hard cap, including anything currently selected. Appending
  // selected-but-unranked tokens instead let one preset add dozens of
  // rows — most of them extensions this folder does not contain, and
  // bare filename tokens like "makefile" listed as if they were
  // suffixes. A preset's members outside the top rows stay reachable
  // through the preset row itself and through Clear.
  const kept = ranked.slice(0, FILTER_TYPE_MENU_MAX);
  return kept.map(([ext, count]) => {
    // Same icon the tree row shows for that type, resolved through the
    // same matcher, so a menu row and the files it keeps are visibly
    // the same thing. `getFileIcon` wants a filename, not an
    // extension, so give it a synthetic one.
    const fi = getFileIcon(`x${ext}`);
    return {
      value: ext,
      label: ext,
      count: count,
      icon: fi.svg,
      iconClass: fi.cls,
    };
  });
}

// A recency window reads from /api/recent, which scans the whole index
// rather than the loaded subtrees — the one thing the Recent tab did
// that a DOM walk cannot. This includes Live: it is the shortest
// server-owned mtime window, not the specialized activity tracker.
function filesPanelUsesRecentSource() {
  if (!filterState) {
    return false;
  }
  var st = filterState.get();
  return st.recency !== "all";
}

function renderNavFilterBar() {
  var bar = document.getElementById("nav-filter-bar");
  if (!bar || !filterState || !filterControls) {
    return;
  }
  var st = filterState.get();
  var count = filterState.activeCount();
  var fc = filterControls;
  var main =
    '<div class="nav-filter-bar-main">' +
    // Age and type ride the always-visible row: they are the two
    // dimensions people reach for, and as dropdowns they cost a
    // fraction of the width the segmented ramps did.
    fc.menuGroupHtml({
      key: "recency",
      select: "one",
      label: "Modified within",
      options: filterRecencyOptions(),
      value: st.recency,
      anyLabel: "Any age",
      anyValue: "all",
      open: filterOpenMenu === "recency",
      menuId: "filter-recency-menu",
    }) +
    fc.menuGroupHtml({
      key: "types",
      label: "File extension",
      options: filterTypeOptions(),
      presetSections: filterTypePresetSections(),
      value: st.types,
      anyLabel: "Any type",
      open: filterOpenMenu === "types",
      menuId: "filter-type-menu",
    }) +
    '<span class="nav-filter-bar-end">' +
    // Clear sits with the dropdowns it undoes, not inside the drawer:
    // it can only appear when something is set, and having to open the
    // drawer to undo a filter set from the row above is a step too
    // many.
    // "Clear", not "Clear filters": it shares a 267px row with two
    // dropdowns whose labels grow with the value they hold, and the
    // shorter word buys the headroom for a long one.
    (count > 0 ? fc.clearHtml({ label: "Clear" }) : "") +
    fc.toggleHtml({
      key: "drawer",
      // The shared chevron glyph, rotated by CSS to point at the state
      // it will produce — the same icon the tree uses for expansion.
      icon: ICONS.toggle || "",
      className: "filter-drawer-toggle",
      pressed: filterDrawerOpen,
      badge: count,
      // A glyph-only control needs a name that says what happens, and
      // the badge is decorative once the count is spoken here.
      ariaLabel:
        (filterDrawerOpen ? "Hide more filters" : "Show more filters") +
        (count > 0 ? ` (${count} active)` : ""),
      title: filterDrawerOpen ? "Fewer filters" : "More filters",
      controls: "filter-drawer",
    }) +
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
    fc.menuGroupHtml({
      key: "size",
      select: "one",
      label: "Minimum file size",
      options: FILTER_SIZE_OPTIONS,
      value: st.size,
      anyLabel: "Any size",
      anyValue: "all",
      open: filterOpenMenu === "size",
      menuId: "filter-size-menu",
    }) +
    fc.checkHtml({
      key: "showIgnored",
      label: "Show ignored",
      checked: st.showIgnored,
      title: "Show gitignored entries, dimmed",
    }) +
    "</div></div>";
  bar.innerHTML = main + drawer;
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
    var count = filterState ? filterState.activeCount() : 0;
    toggle.setAttribute("aria-pressed", String(filterDrawerOpen));
    toggle.setAttribute(
      "aria-label",
      (filterDrawerOpen ? "Hide more filters" : "Show more filters") +
        (count > 0 ? ` (${count} active)` : ""),
    );
    toggle.setAttribute("title", filterDrawerOpen ? "Fewer filters" : "More filters");
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
        var hadMenu = filterOpenMenu === "size";
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
    onMenuToggle: (key, open) => {
      filterOpenMenu = open ? key : null;
      renderNavFilterBar();
      if (key === "recency" && open) {
        scheduleRootSummaryRefresh();
      }
    },
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
      // Additive, like the extensions beside it: turning Docs on adds
      // its values to whatever is already picked, and turning it off
      // removes only its own.
      var current = filterState.get().types || [];
      var next = wasOn
        ? current.filter((value) => preset.values.indexOf(value) < 0)
        : current.concat(preset.values.filter((value) => current.indexOf(value) < 0));
      filterState.set({ types: next.length > 0 ? next : null });
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
      if (key === "recency" || key === "size") {
        filterState.set({ [key]: value === null ? "all" : value });
        // Single-select closes on pick: the choice is made, and a menu
        // left hanging over the tree has nothing more to offer.
        filterOpenMenu = null;
        renderNavFilterBar();
      }
    },
    onClear: () => {
      filterOpenMenu = null;
      filterState.clear();
    },
  });
  // Seed the source tracking from the persisted state so the first
  // user change is compared against reality, not against null.
  _filterLastSource = filesPanelUsesRecentSource();
  _filterLastRecency = filterState.get().recency;
  _filterLastShowIgnored = filterState.get().showIgnored;
  filterState.subscribe(onFilterStateChange);
}

// One place decides what a filter change costs: a source swap plus a
// re-render when the tree's data source changes, and a class pass over
// the rendered rows otherwise.
var _filterLastSource = false;
var _filterLastRecency = "all";
var _filterLastShowIgnored = true;
function onFilterStateChange(state) {
  renderNavFilterBar();
  var usesRecent = filesPanelUsesRecentSource();
  var sourceChanged = _filterLastSource !== usesRecent;
  var windowChanged = usesRecent && _filterLastRecency !== state.recency;
  // Gitignored visibility is a server-side parameter on the recency
  // source, not just a class on the rows: it decides what the response
  // cap gets spent on, so changing it has to refetch.
  var ignoredChanged = usesRecent && _filterLastShowIgnored !== state.showIgnored;
  _filterLastSource = usesRecent;
  _filterLastRecency = state.recency;
  _filterLastShowIgnored = state.showIgnored;
  if (usesRecent && (sourceChanged || windowChanged || ignoredChanged)) {
    loadRecent(state.recency);
    return;
  }
  if (!usesRecent && sourceChanged) {
    // Abandon any recency fetch still in flight and drop the window it
    // was for. Otherwise a late response repaints the panel with the
    // old window's list under a trigger that now reads "Any age".
    if (recentInflight) {
      recentInflight.abort();
      recentInflight = null;
    }
    // Empty, not a window key: a late response compares against this
    // and must never find a match.
    currentRecentWindow = "";
    clearRecentExpiryRecheck();
    // Refetch the authoritative tree. The first-paint cache can still carry
    // pending aggregates even after live events patched the visible DOM; using
    // it here reintroduced skeleton cells after progress polling had stopped.
    loadTree();
    return;
  }
  applyTreeFilters();
}

// ── Applying filters to the tree ────────────────────────────────
//
// A decoration layer over rendered rows, never a render fork: with no
// filters set this removes its own classes and leaves the DOM exactly
// as the renderer produced it.
//
// The walk runs in reverse document order so a folder is judged after
// its descendants and can ask whether any of them survived. A folder
// with no loaded children is unknown rather than excluded — the one
// exception being recency, where the folder's own aggregate mtime
// (newest descendant) is a definitive answer for the whole subtree.

function _childContainerFor(row) {
  var next = row.nextElementSibling;
  return next?.classList.contains("tree-children") ? next : null;
}

function applyTreeFilters() {
  var panel = document.getElementById("tab-files");
  if (!panel || !filterState) {
    return;
  }
  var st = filterState.get();
  var rows = /** @type {HTMLElement[]} */ (
    Array.prototype.slice.call(panel.querySelectorAll(".tree-item"))
  );
  var constrained = filterHasConstraints(st);
  if (!constrained) {
    for (var c = 0; c < rows.length; c++) {
      rows[c].classList.remove("tree-item-filter-hidden");
    }
    // Clear both lines too: this early return is the path taken when
    // the last filter is removed, so leaving them would strand a
    // "Filtered to N files" over an unfiltered tree.
    _renderFilteredTally(panel, 0, st, null);
    _renderFilterNote(panel, 0, st);
    return;
  }
  var nowSec = Date.now() / 1000;
  var keep = new Map();
  var unloadedFolders = 0;
  for (var i = rows.length - 1; i >= 0; i--) {
    var row = rows[i];
    var isDir = row.classList.contains("tree-folder");
    var isSymlink = row.classList.contains("tree-symlink");
    var gitignored = row.classList.contains("tree-item-gitignored");
    var path = row.dataset.path || "";
    var ok;
    if (!st.showIgnored && gitignored) {
      ok = false;
    } else {
      ok = filterState.rowMatches(
        {
          mtime: parseTipNumber(row.dataset.tipMtime),
          size: isDir ? null : parseTipNumber(row.dataset.tipSize),
          path: path,
          // The renderer stamps the index's bounded compound-tail extension on
          // every file row; matching on it keeps a compound pick
          // (".min.js") agreeing with the tally that offered it.
          ext: row.dataset.ext || "",
          isDir: isDir,
          isSymlink: isSymlink,
        },
        st,
        nowSec,
      );
    }
    if (isDir && ok) {
      var container = _childContainerFor(row);
      var kids = container
        ? Array.prototype.slice.call(container.querySelectorAll(":scope > .tree-item"))
        : [];
      if (kids.length > 0) {
        ok = kids.some((kid) => keep.get(kid) === true);
      } else {
        // Nothing loaded under it: the filter cannot speak for this
        // subtree, so the folder stays and gets counted.
        unloadedFolders += 1;
      }
    }
    keep.set(row, ok);
  }
  // Forward pass so a pruned folder is seen before its descendants:
  // its verdict propagates down, and a subtree never keeps an orphaned
  // visible row under a parent that is gone.
  var suppressed = new Set();
  var shownFiles = 0;
  for (var j = 0; j < rows.length; j++) {
    var el = rows[j];
    var matched = !suppressed.has(el.parentElement) && keep.get(el) === true;
    el.classList.toggle("tree-item-filter-hidden", !matched);
    if (matched) {
      if (!el.classList.contains("tree-folder") && !el.classList.contains("tree-symlink")) {
        shownFiles += 1;
      }
    } else {
      var kidContainer = _childContainerFor(el);
      if (kidContainer) {
        suppressed.add(kidContainer);
      }
    }
  }
  // The recency source counts from its entries, not the rendered rows:
  // renderTreeNodes pages at TREE_PAGE_SIZE, so a DOM count reports how
  // much has been paged in rather than how many files passed.
  var recencyCount = filesPanelUsesRecentSource()
    ? countRecentMatches(
        recentEntriesFromBase({ window: currentRecentWindow, limit: RECENT_LIMIT }),
        nowSec,
      )
    : null;
  _renderFilteredTally(panel, shownFiles, st, recencyCount);
  _renderFilterNote(panel, unloadedFolders, st);
}

// How many files the filter is actually showing, as a second line
// under the tally. Rendered whenever anything is filtered, not only
// when a response was capped: "how many am I looking at" is the
// question a filter raises every time, and the totals above are what
// it reads against.
//
// Counted from the rows that survived, so it reflects every dimension
// rather than just the one the server resolved.
function _renderFilteredTally(panel, shownFiles, state, recencyCount) {
  var existing = panel.querySelector(".tree-summary-filtered");
  if (!filterHasConstraints(state)) {
    if (existing) {
      existing.remove();
    }
    return;
  }
  var count = recencyCount !== null ? recencyCount : shownFiles;
  var text = `Filtered to ${count.toLocaleString()} ${count === 1 ? "file" : "files"}`;
  // A capped response has more matches than it sent, and only it can
  // say so — the client never saw the rest.
  if (filesPanelUsesRecentSource() && recentTruncated && recentTotalMatching) {
    text += ` of ${recentTotalMatching.toLocaleString()} matching`;
  }
  text += ".";
  if (existing) {
    existing.textContent = text;
    return;
  }
  var summary = panel.querySelector(".tree-summary");
  var line = document.createElement("div");
  line.className = "tree-summary-filtered";
  line.setAttribute("role", "status");
  line.textContent = text;
  if (summary) {
    summary.insertAdjacentElement("afterend", line);
  } else {
    panel.insertAdjacentElement("afterbegin", line);
  }
}

// Filtering prunes what it has loaded, which is not the same as "this
// is everything that matches". Say so rather than letting a short tree
// imply completeness.
function _renderFilterNote(panel, unloadedFolders, state) {
  var existing = panel.querySelector(".filter-note");
  if (unloadedFolders <= 0 || !filterHasConstraints(state)) {
    if (existing) {
      existing.remove();
    }
    return;
  }
  var text =
    `${unloadedFolders.toLocaleString()} collapsed ` +
    `${unloadedFolders === 1 ? "folder may" : "folders may"} contain additional matches. ` +
    `Expand ${unloadedFolders === 1 ? "it" : "them"} to check.`;
  if (existing) {
    existing.textContent = text;
    return;
  }
  var note = document.createElement("div");
  note.className = "filter-note";
  note.setAttribute("role", "status");
  note.textContent = text;
  panel.appendChild(note);
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

const fileCache = new Map();
// HTTP ETags associated with cached file payloads. When a file drops
// out of the active set we move its path into ``fileNeedsRevalidate``
// rather than evicting the cache outright; the next ``selectFile``
// sends ``If-None-Match`` and accepts a 304 to re-confirm the payload
// without re-downloading. Server-side this is just the existing
// ``mtime_hash`` promoted to an HTTP-level ETag.
const fileETags = new Map();
const fileNeedsRevalidate = new Set();
const CACHE_MAX = 30; // file payloads are small
const ETAG_REVALIDATE_MAX = 512;

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

function showTextChunkLoadError() {
  var warning = document.querySelector(".metabrowser-source-truncation-warning");
  if (!warning) {
    return;
  }
  warning.setAttribute("role", "alert");
  warning.innerHTML =
    "<strong>Could not load more content.</strong> Select Load more to try again.";
}

// Called by the generated file-header action.
// biome-ignore lint/correctness/noUnusedVariables: referenced from generated HTML.
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
  var offset = cached.bytes_read || 0;
  try {
    var resp = await fetch(
      "/api/file?path=" +
        encodeURIComponent(path) +
        "&offset=" +
        encodeURIComponent(String(offset)) +
        "&limit=" +
        encodeURIComponent(String(TEXT_PREVIEW_CHUNK_BYTES)),
    );
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    var chunk = await _perf.measureAsync(
      "apiFile:textChunkJson",
      () => resp.json(),
      responsePerfMeta(resp, path, { offset: offset }),
    );
    if (currentPath !== path) {
      return;
    }
    if (chunk.mtime_hash && cached.mtime_hash && chunk.mtime_hash !== cached.mtime_hash) {
      fileNeedsRevalidate.add(path);
      boundMapSize(fileNeedsRevalidate, ETAG_REVALIDATE_MAX);
      await selectFile(path);
      return;
    }
    cached.content = (cached.content || "") + (chunk.content || "");
    cached.content_bytes = (cached.content_bytes || 0) + (chunk.content_bytes || 0);
    cached.bytes_read = chunk.bytes_read || cached.bytes_read;
    cached.content_truncated = !!chunk.content_truncated;
    cached.highlight_disabled = true;
    renderFile(cached);
  } catch (e) {
    console.warn("Failed to load text chunk", e);
    if (currentPath === path) {
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

/** @returns {Promise<QuickFileOpenOutcome>} */
async function selectFile(path, preferredViewId) {
  return _perf.measureAsync(
    "selectFile",
    async () => {
      // Always close any prior live stream — switching files (or reopening
      // the same file) starts fresh.
      closeLiveStream();
      currentPath = path;
      const preview = document.getElementById("preview-pane");
      if (!preview) {
        return {
          message: "Could not display the file. Refresh the page to try again.",
          status: "error",
        };
      }

      // Three-way cache state:
      //   - hot: in fileCache and not flagged → serve from cache.
      //   - revalidate: in fileCache but flagged (file recently changed in
      //     activity poll) → send If-None-Match, accept 304 to confirm.
      //   - cold: not in fileCache → unconditional fetch.
      const cached = fileCache.get(path);
      const needsRevalidate = fileNeedsRevalidate.has(path);
      if (cached && !needsRevalidate && !activeFiles.has(path)) {
        navigationController?.canonicalizePath(path, cached.kind === "folder");
        renderFile(cached, preferredViewId);
        maybeOpenLiveStream(path, cached);
        return openedFileOutcome(path, cached, preview);
      }

      if (loadingIndicatorTimer) {
        clearTimeout(loadingIndicatorTimer);
      }
      loadingIndicatorTimer = setTimeout(() => {
        loadingIndicatorTimer = null;
        if (currentPath !== path) {
          return;
        }
        disposeActivePluginViews();
        stopFolderHeaderSubscription();
        preview.innerHTML =
          '<div class="loading mb-delayed-loading"><div class="spinner"></div>Loading file…</div>';
      }, LOADING_INDICATOR_DELAY_MS);

      if (selectFileAbortController) {
        selectFileAbortController.abort();
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
        const resp = await fetch(`/api/file?path=${encodeURIComponent(path)}`, {
          headers: headers,
          signal: selectFileSignal,
        });
        if (resp.status === 304 && cached) {
          // Server confirmed the cached payload is still fresh — zero-byte
          // body, render from memory.
          fileNeedsRevalidate.delete(path);
          if (currentPath === path) {
            if (loadingIndicatorTimer) {
              clearTimeout(loadingIndicatorTimer);
              loadingIndicatorTimer = null;
            }
            navigationController?.canonicalizePath(path, cached.kind === "folder");
            renderFile(cached, preferredViewId);
            maybeOpenLiveStream(path, cached);
            return openedFileOutcome(path, cached, preview);
          }
          return { status: "cancelled" };
        }
        if (!resp.ok) {
          const text = await _perf.measureAsync(
            "apiFile:errorText",
            () => resp.text(),
            responsePerfMeta(resp, path),
          );
          throw Object.assign(new Error(responseErrorDetail(text, resp.status)), {
            notFound: resp.status === 404,
            summary: responseErrorSummary(text, "Could not open this file."),
          });
        }
        const data = await _perf.measureAsync(
          "apiFile:json",
          () => resp.json(),
          responsePerfMeta(resp, path),
        );
        if (data.kind !== "folder") {
          // Folder envelopes are no-store (aggregates move during a
          // scan): keep them out of the file cache and ETag books.
          cachePut(fileCache, path, data, CACHE_MAX, evictFileCacheMetadata);
          const etagHeader = resp.headers.get("etag");
          if (etagHeader) {
            fileETags.set(path, etagHeader);
            boundMapSize(fileETags, ETAG_REVALIDATE_MAX);
          }
        }
        fileNeedsRevalidate.delete(path);
        if (currentPath === path) {
          if (loadingIndicatorTimer) {
            clearTimeout(loadingIndicatorTimer);
            loadingIndicatorTimer = null;
          }
          navigationController?.canonicalizePath(path, data.kind === "folder");
          renderFile(data, preferredViewId);
          maybeOpenLiveStream(path, data);
          return openedFileOutcome(path, data, preview);
        }
        return { status: "cancelled" };
      } catch (err) {
        var caught = /** @type {{name?: string, notFound?: boolean, summary?: string}} */ (err);
        if (caught?.name === "AbortError") {
          return { status: "cancelled" };
        }
        var notFound = caught?.notFound === true;
        if (currentPath === path) {
          if (loadingIndicatorTimer) {
            clearTimeout(loadingIndicatorTimer);
            loadingIndicatorTimer = null;
          }
          disposeActivePluginViews();
          stopFolderHeaderSubscription();
          preview.innerHTML = previewErrorHtml(
            caught?.summary || "Could not open this file.",
            errorMessage(err),
          );
        } else {
          return { status: "cancelled" };
        }
        return notFound
          ? { message: `${path} is no longer available.`, status: "not-found" }
          : {
              message: `Could not open ${path}. Check that the file still exists and is readable.`,
              status: "error",
            };
      }
    },
    { path: path, preferred_view: preferredViewId || "" },
  );
}

/**
 * @param {string} path
 * @param {{kind?: string, logical_ext?: string}} data
 * @param {HTMLElement} preview
 * @returns {QuickFileOpenOutcome}
 */
function openedFileOutcome(path, data, preview) {
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
  navigateToPath(path === "" ? "/" : `${path}/`);
}

// Folder preview header: up control, clickable breadcrumb, aggregate
// summary. The shell owns this chrome so every folder view shares it.
function renderFolderHeader(data) {
  var path = typeof data.path === "string" ? data.path : "";
  var segments = path ? path.split("/") : [];
  var rootCrumb =
    '<button type="button" class="folder-crumb folder-crumb-root" data-nav-dir="" title="Served root">/</button>';
  var crumbs = [];
  var prefix = "";
  for (var i = 0; i < segments.length; i++) {
    prefix = prefix ? `${prefix}/${segments[i]}` : segments[i];
    var isLast = i === segments.length - 1;
    crumbs.push(
      isLast
        ? `<span class="folder-crumb folder-crumb-current">${esc(segments[i])}</span>`
        : `<button type="button" class="folder-crumb" data-nav-dir="${esc(prefix)}">${esc(segments[i])}</button>`,
    );
  }
  var parent = segments.length > 0 ? segments.slice(0, -1).join("/") : null;
  var upButton =
    parent === null
      ? '<button type="button" class="file-header-icon folder-up" title="Up" aria-label="Up to parent folder" disabled>↑</button>'
      : `<button type="button" class="file-header-icon folder-up" title="Up" aria-label="Up to parent folder" data-nav-dir="${esc(parent)}">↑</button>`;
  var summary = `<span class="folder-header-summary">${folderHeaderSummaryHtml(data.dir || {})}</span>`;
  return (
    '<div class="file-header folder-header">' +
    upButton +
    `<span class="file-header-path folder-breadcrumb">${rootCrumb}${crumbs.join('<span class="folder-crumb-sep">/</span>')}</span>` +
    summary +
    '<button class="icon-btn file-header-icon file-header-print" id="print-view-btn" type="button" onclick="printActiveView()" title="Print view" aria-label="Print view" hidden>' +
    (ICONS.print || "") +
    "</button>" +
    "</div>"
  );
}

// Aggregate strip of the folder header. Split out so the live
// refresher below can patch it in place when the inventory changes.
function folderHeaderSummaryHtml(dirInfo) {
  // A still-finalizing directory reports null aggregates; sizeHtml,
  // countHtml, and formatAge(null) all render the tally-pending
  // skeleton the tree rows use, so the header paints with shape
  // instead of blanks until the live refresher patches it.
  return (
    sizeHtml(dirInfo.total_size, "file-header-size") +
    countHtml(dirInfo.total_files, "folder-header-count") +
    `<span class="folder-header-age">${formatAge(dirInfo.mtime ?? null)}</span>`
  );
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
      summaryEl.innerHTML = folderHeaderSummaryHtml(data.dir || {});
    }
  });
}

// Build badges based on file kind (data-driven)
function renderBadges(data) {
  var badges = "";
  // Compression status — surfaced first so it's adjacent to the path.
  // Mirrors the .compression-badge overlay on the tree icon, with
  // text rather than a glyph since file-header badges are larger.
  if (data?.compressed) {
    var label = data.compression
      ? data.compression.charAt(0).toUpperCase() + data.compression.slice(1)
      : "Compressed";
    badges +=
      '<span class="file-header-badge badge-compressed" title="On-disk file is ' +
      esc(label.toLowerCase()) +
      '-compressed">' +
      esc(label) +
      "</span>";
  }
  var kind = data.kind;
  if (kind === "agent-log" && data.summary) {
    var summary = data.summary;
    if (summary.adapter === "claude") {
      badges += '<span class="file-header-badge badge-claude">Claude</span>';
    } else if (summary.adapter === "gemini") {
      badges += '<span class="file-header-badge badge-gemini">Gemini</span>';
    } else if (summary.adapter === "pi") {
      badges += '<span class="file-header-badge badge-pi">Pi</span>';
    }
  } else if (data.summary?.adapter && data.summary.adapter !== "unknown") {
    var adapterLabel = String(data.summary.adapter)
      .replace(/[-_]+/g, " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
    badges += `<span class="file-header-badge badge-adapter">${esc(adapterLabel)}</span>`;
  }
  // Status badge for JSONL kinds
  if (data.type === "jsonl" && data.summary) {
    var statusSummary = data.summary;
    if (statusSummary.is_done) {
      badges += statusSummary.is_error
        ? '<span class="file-header-badge badge-failed">Failed</span>'
        : '<span class="file-header-badge badge-completed">Done</span>';
    } else if (activeFiles.has(data.path)) {
      badges += '<span class="file-header-badge badge-live">Live</span>';
    } else {
      badges += '<span class="file-header-badge badge-running">Running</span>';
    }
  }
  // Frontmatter parse error — surfaced as a red warning badge with the
  // YAML parser's message in the tooltip. /api/file populates this on
  // .md files where the leading --- ... --- block is present but
  // unparsable; absent frontmatter does NOT trigger this. The warning
  // hides a producer bug (e.g. tab characters, unmatched quotes); the
  // file still renders because classification falls back to generic
  // markdown, but the operator now sees that the frontmatter was
  // ignored rather than silently using an unparsable value.
  if (data.frontmatter_error) {
    badges +=
      '<span class="file-header-badge badge-frontmatter-error" title="' +
      esc(data.frontmatter_error) +
      '">Frontmatter error</span>';
  }
  return badges;
}

function renderTextPreviewControls(data) {
  if (data?.type !== "text" || typeof data.bytes_read !== "number") {
    return "";
  }
  if (!data.content_truncated && data.bytes_read >= (data.size || 0)) {
    return "";
  }
  var loaded = Math.min(data.bytes_read || 0, data.size || 0);
  var html = `<span class="file-header-preview">${formatSize(loaded)} / ${formatSize(data.size || 0)}</span>`;
  if (data.content_truncated) {
    html +=
      '<button class="btn file-header-action" type="button" onclick="loadMoreCurrentText()" title="Load more of this file">Load more</button>';
  }
  return html;
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

function updatePrintButton(printable) {
  var btn = document.getElementById("print-view-btn");
  if (!btn) {
    return;
  }
  btn.hidden = !printable;
  btn.setAttribute("aria-hidden", printable ? "false" : "true");
}

function setActivePreviewView(tabId, preview) {
  preview = preview || document.getElementById("preview-pane");
  if (!preview) {
    return;
  }
  preview = /** @type {HTMLElement} */ (preview);
  /** @type {HTMLElement | null} */
  var active = null;
  var tabContents = queryHtmlAll("[data-tab-content]", preview);
  for (var i = 0; i < tabContents.length; i++) {
    var c = tabContents[i];
    var isActive = !!tabId && c.dataset.tabContent === tabId;
    if (window.MetabrowserViewState) {
      window.MetabrowserViewState.setActive(c, isActive);
    } else {
      c.dataset.activeView = isActive ? "true" : "false";
    }
    if (isActive) {
      active = c;
    }
  }
  if (!active) {
    delete preview.dataset.activeView;
    preview.dataset.printable = "false";
    preview.dataset.printProfile = "plain";
    delete preview.dataset.renderRuntime;
    delete preview.dataset.kpressEnabled;
    updatePrintButton(false);
    return;
  }
  var printable = boolData(active.dataset.printable);
  preview.dataset.activeView = tabId;
  preview.dataset.printable = printable ? "true" : "false";
  preview.dataset.printProfile = active.dataset.printProfile || "plain";
  if (active.dataset.renderRuntime) {
    preview.dataset.renderRuntime = active.dataset.renderRuntime;
  } else {
    delete preview.dataset.renderRuntime;
  }
  if (active.dataset.kpressEnabled) {
    preview.dataset.kpressEnabled = active.dataset.kpressEnabled;
  } else {
    delete preview.dataset.kpressEnabled;
  }
  updatePrintButton(printable);
}

function printActiveView() {
  window.print();
}

if (typeof window !== "undefined") {
  window.printActiveView = printActiveView;
}

document.addEventListener("metabrowser:view-print-state", () => {
  var preview = document.getElementById("preview-pane");
  if (preview?.dataset.activeView) {
    setActivePreviewView(preview.dataset.activeView, preview);
  }
});

var activePluginDisposers = [];

function disposeActivePluginViews() {
  stopFolderHeaderSubscription();
  var disposers = activePluginDisposers;
  activePluginDisposers = [];
  for (var i = 0; i < disposers.length; i++) {
    try {
      disposers[i]();
    } catch (err) {
      console.error("plugin dispose error:", err);
    }
  }
}

function mountPluginView(container, pluginView, ctx) {
  /** @type {{disposed: boolean, handle: {dispose: () => void} | null}} */
  var record = { disposed: false, handle: null };
  activePluginDisposers.push(() => {
    if (record.disposed) {
      return;
    }
    record.disposed = true;
    if (typeof record.handle?.dispose === "function") {
      record.handle.dispose();
    }
    if (typeof pluginView.dispose === "function") {
      pluginView.dispose(container);
    }
  });
  try {
    var maybePromise = pluginView.render(container, ctx);
    Promise.resolve(maybePromise).then(
      (handle) => {
        if (!handle || typeof handle.dispose !== "function") {
          return;
        }
        if (record.disposed) {
          handle.dispose();
        } else {
          record.handle = handle;
        }
      },
      (err) => {
        if (record.disposed) {
          return;
        }
        console.error("plugin render error:", err);
        container.innerHTML =
          '<div class="preview-empty" role="alert">Could not display this view. Refresh the page to try again.</div>';
      },
    );
  } catch (err) {
    console.error("plugin render error:", err);
    container.innerHTML =
      '<div class="preview-empty" role="alert">Could not display this view. Refresh the page to try again.</div>';
  }
}

function renderFile(data, preferredViewId) {
  return _perf.measure(
    `renderFile:${data.kind || data.type || "?"}`,
    () => {
      const preview = document.getElementById("preview-pane");
      if (!preview) {
        return;
      }

      // Drain any disposers from a previously mounted view; we're about to
      // replace preview.innerHTML below, which detaches their containers.
      disposeActivePluginViews();

      // Build header — folders get breadcrumb chrome (renderFolderHeader),
      // files the path/badges/size strip.
      let html = "";
      if (data.kind === "folder") {
        html = renderFolderHeader(data);
        window.metabrowser?.folderContext?.seed(data.path, data);
        startFolderHeaderSubscription(data.path);
      } else {
        stopFolderHeaderSubscription();
      }
      if (data.kind !== "folder") {
        var badges = renderBadges(data);
        html = '<div class="file-header">';
        html +=
          '<span class="file-header-path">' +
          esc(data.path) +
          `<button class="icon-btn icon-btn-reveal file-header-copy" type="button" data-copy-path="${esc(data.path)}" title="Copy path" aria-label="Copy path">` +
          ICON_COPY +
          "</button>" +
          "</span>";
        html += badges;
        html += sizeHtml(data.size, "file-header-size");
        html += renderTextPreviewControls(data);
        html +=
          '<button class="icon-btn file-header-icon file-header-print" id="print-view-btn" type="button" onclick="printActiveView()" title="Print view" aria-label="Print view" hidden>' +
          (ICONS.print || "") +
          "</button>";
        html += "</div>";
      }

      // Data-driven tab rendering from server views.
      //
      // Every (kind, viewId) goes through the plugin registry: built-in
      // plugins (markdown, agent-log, unknown-jsonl, text) own their own
      // kinds; entry-point plugins own theirs. The shell here
      // builds the empty containers; each plugin's render(container, ctx)
      // fires below once the DOM is in place. If no plugin claims a
      // (kind, viewId) we paint an unavailable-view message — never a
      // fallback that pulls renderers out of the shell. This is the
      // contract: every kind is a plugin.
      var views = data.views;
      var initialActiveView = null;
      if (views?.length) {
        // Plugin navigation can preserve a working mode across resources.
        // An unavailable preference falls through to the server default.
        initialActiveView =
          views.find((view) => view.id === preferredViewId) ||
          views.find((view) => view.default) ||
          views[0];
      }
      var pluginRenders = [];
      if (views && views.length > 0) {
        if (views.length > 1) {
          html += '<div class="tab-bar">';
          for (let i = 0; i < views.length; i++) {
            const view = views[i];
            var active = view.id === initialActiveView?.id ? " active" : "";
            html +=
              '<button class="tab-btn' +
              active +
              '" type="button" data-tab="' +
              esc(view.id) +
              '"' +
              viewMetaAttrs(view) +
              ">" +
              esc(view.label) +
              "</button>";
          }
          html += "</div>";
        }
        for (let i = 0; i < views.length; i++) {
          const view = views[i];
          var pluginView =
            window.metabrowser && data.kind
              ? window.metabrowser.getRegisteredView(data.kind, view.id)
              : null;
          // container_class can be set per-view in the plugin manifest as
          // [[view]].container_class; defaults to "content-body".
          var containerClass = view.container_class || "content-body";
          var hidden = view.id === initialActiveView?.id ? "" : ' style="display:none;"';
          var noPadding = view.id === "raw" || view.id === "source" ? "padding:0;" : "";
          if (noPadding && !hidden) {
            hidden = ` style="${noPadding}"`;
          } else if (noPadding && hidden) {
            hidden = ` style="display:none;${noPadding}"`;
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
              '><div class="preview-empty" role="alert">This view is unavailable. Refresh the page to try again.</div></div>';
          }
        }
      } else if (data.type === "image") {
        // No tab bar — the browser renders the image directly via /raw,
        // which already returns the right mimetype. The .content-body
        // wrapper gives the same outer padding a plain text view has.
        html +=
          '<div class="content-body"><img class="file-image" src="/raw?path=' +
          encodeURIComponent(data.path) +
          '" alt="' +
          esc(data.path) +
          '"></div>';
      } else if (data.type === "binary") {
        html += `<div class="content-body"><div class="preview-empty">No preview is available for this binary file (${formatSize(data.size || 0)}).</div></div>`;
      } else if (data.type === "jsonl_too_large") {
        html +=
          '<div class="content-body"><div class="preview-empty">' +
          "<strong>This JSONL file is too large to preview.</strong><br><br>" +
          "File size: " +
          formatSize(data.size || 0) +
          "<br>Preview limit: " +
          formatSize(data.max_size || 0) +
          "<br><br>Open it with a tool that can stream large files." +
          "</div></div>";
      } else if (data.type === "error") {
        html += `<div class="content-body">${previewErrorHtml("Could not preview this file.", data.error)}</div>`;
      }

      _perf.measure(
        "renderFile:mount",
        () => {
          preview.innerHTML = html;
        },
        filePerfMeta(data, { html_chars: html.length }),
      );
      if (initialActiveView) {
        setActivePreviewView(initialActiveView.id, preview);
      } else {
        setActivePreviewView(null, preview);
      }

      // Now that the DOM is in place, run any deferred plugin renderers.
      // Each plugin's render(container, ctx) mutates the container directly
      // — async work (fetches, charts) is fine; the spinner stays visible
      // until the plugin's render resolves.
      if (pluginRenders?.length) {
        var ctx = {
          path: data.path,
          kind: data.kind,
          ext: data.ext,
          size: data.size,
          frontmatter: data.frontmatter || {},
          body: typeof data.content === "string" ? data.content : data.body || "",
          raw: data,
          fetchPluginData: window.metabrowser ? window.metabrowser.fetchPluginData : null,
        };
        for (var pi = 0; pi < pluginRenders.length; pi++) {
          var pr = pluginRenders[pi];
          var container = preview.querySelector(`[data-plugin-view="${pr.tabId}"]`);
          if (!container) {
            continue;
          }
          var mount = ((target, pluginView) => () => {
            mountPluginView(target, pluginView, ctx);
          })(container, pr.view);
          if (initialActiveView && pr.tabId === initialActiveView.id) {
            mount();
          } else {
            container._metabrowserMount = mount;
          }
        }
      }

      _perf.measure("initTabs", initTabs, filePerfMeta(data));
      highlightCode();
      measureNextPaint("renderFile:nextPaint", filePerfMeta(data));
    },
    filePerfMeta(data),
  );
}

// The agent-log built-in plugin emits onclick="toggleEvent(this)"
// in each log event header. This handler sits on window so the
// inline onclick resolves at click time. Lazy-highlight on first
// expand keeps initial render cheap on logs with thousands of events.

// biome-ignore lint/correctness/noUnusedVariables: referenced from generated plugin HTML.
function toggleEvent(header) {
  var parent = header.parentElement;
  parent.classList.toggle("expanded");
  if (parent.classList.contains("expanded")) {
    // First-expand mount: agent-log emits log-event-raw containers
    // empty and registers mountLogEventRaw on window. When the
    // structured plugin is loaded, this renders a collapsible inline
    // tree; otherwise it falls back to a flat JSON block.
    var rawEl = parent.querySelector(".log-event-raw");
    if (
      rawEl &&
      window.metabrowserAgentLog &&
      typeof window.metabrowserAgentLog.mountLogEventRaw === "function"
    ) {
      window.metabrowserAgentLog.mountLogEventRaw(rawEl);
    }
    if (typeof hljs !== "undefined") {
      var code = parent.querySelector(".log-event-raw pre code:not(.hljs)");
      if (code) {
        hljs.highlightElement(code);
      }
    }
  }
}

// ── Charts loading + rendering ──────────────────────────────────

function copyPath(btn, path) {
  navigator.clipboard.writeText(path).then(() => {
    btn.classList.add("copied");
    btn.title = "Copied!";
    setTimeout(() => {
      btn.classList.remove("copied");
      btn.title = "Copy path";
    }, 1500);
  });
}

// Delegated handlers for header controls. Paths ride in data-*
// attributes (HTML-escaped at render, decoded by dataset) instead of
// inline onclick handlers, which HTML-decode their attribute before
// compiling JavaScript and therefore cannot safely carry filenames
// containing quotes.
document.addEventListener("click", (e) => {
  var origin = eventTargetElement(e);
  if (!origin) {
    return;
  }
  var navBtn = /** @type {HTMLElement | null} */ (origin.closest("[data-nav-dir]"));
  if (navBtn && !navBtn.hasAttribute("disabled")) {
    navigateToFolder(navBtn.dataset.navDir ?? "");
    return;
  }
  var copyBtn = /** @type {HTMLElement | null} */ (origin.closest("[data-copy-path]"));
  if (copyBtn && typeof copyBtn.dataset.copyPath === "string") {
    copyPath(copyBtn, copyBtn.dataset.copyPath);
  }
});

// biome-ignore lint/correctness/noUnusedVariables: referenced from generated HTML.
function copyContent(btn) {
  var container = btn.closest(".content-copy-wrap");
  var code = container?.querySelector("code");
  var text = code ? code.textContent : "";
  navigator.clipboard.writeText(text).then(() => {
    btn.classList.add("copied");
    btn.title = "Copied!";
    setTimeout(() => {
      btn.classList.remove("copied");
      btn.title = "Copy content";
    }, 1500);
  });
}

// ── Tab switching ───────────────────────────────────────────────

function initTabs() {
  queryHtmlAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      var tabId = btn.dataset.tab;
      var bar = /** @type {HTMLElement | null} */ (btn.closest(".tab-bar"));
      if (!bar) {
        return;
      }
      var container = bar.parentElement;
      if (!container) {
        return;
      }
      bar.querySelectorAll(".tab-btn").forEach((b) => {
        b.classList.remove("active");
      });
      btn.classList.add("active");
      queryHtmlAll("[data-tab-content]", container).forEach((c) => {
        c.style.display = c.dataset.tabContent === tabId ? "" : "none";
      });
      if (container && container.id === "preview-pane") {
        setActivePreviewView(tabId, container);
      }
      var activeContent = container.querySelector(`[data-tab-content="${tabId}"]`);
      if (activeContent && typeof activeContent._metabrowserMount === "function") {
        var mount = activeContent._metabrowserMount;
        activeContent._metabrowserMount = null;
        mount();
      }
    });
  });
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
    // EventSource auto-reconnects on transient errors. We only need
    // to clean up if the stream shows persistent failure (readyState
    // CLOSED), so transient errors remain under browser control.
  };
}

function appendLiveEvents(path, batch) {
  return _perf.measure(
    "appendLiveEvents",
    () => {
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
      // Append to the currently-rendered log tab if it's visible. Charts
      // re-fetch on poll because series rebinning depends on the complete
      // event timeline.
      var logPane = queryHtml('[data-tab-content="log"]');
      if (logPane && logPane.style.display !== "none") {
        var tail = "";
        var startIdx = cached.events.length - batch.events.length;
        // The agent-log built-in plugin owns renderLogEvent and exposes it
        // through the public namespace. If the plugin isn't loaded
        // (shouldn't happen for built-ins), the live tail is silently
        // skipped — the static log render still shows up on full reload.
        var renderEvt = window.metabrowser?.builtins?.agentLog?.renderLogEvent;
        if (renderEvt) {
          for (var j = 0; j < batch.events.length; j++) {
            tail += renderEvt(logPane, batch.events[j], startIdx + j);
          }
        }
        logPane.insertAdjacentHTML("beforeend", tail);
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
//
// Single source of truth for live tree decoration. Populated from
// /api/events:
//   1. fs.snapshot (id=0 sentinel) — initial snapshot at the
//      requested scope.
//   2. fs.change ops — walker / watcher updates; each upsert
//      replaces an FsEntry in the store and triggers
//      applyCellPatch() to update the rendered tree row.
var fileStore = new Map(); // path -> FsEntry
var fileStoreSubscribers = [];
var inventoryEventSource = null;

function fileStoreApplySnapshot(scope, entries) {
  // Atomic apply: rebuild the store from this snapshot before
  // notifying any subscriber, so derived views never see a
  // half-empty state.
  knownFileCatalog?.observeEventSnapshot(entries);
  fileStore = new Map();
  for (var i = 0; i < entries.length; i++) {
    fileStore.set(entries[i].path, entries[i]);
    applyCellPatch(entries[i]);
    _mirrorActiveFromFsEntry(entries[i]);
  }
  notifyFileStoreSubscribers({ kind: "snapshot", scope: scope });
}

function fileStoreApplyChange(ops) {
  knownFileCatalog?.applyEventChange(ops);
  for (var i = 0; i < ops.length; i++) {
    var op = ops[i];
    if (op.op === "upsert") {
      fileStore.set(op.entry.path, op.entry);
      // Patch any rendered cell for this path; insert a new row if
      // the parent is rendered + expanded. Idempotent.
      applyCellPatch(op.entry);
      _mirrorActiveFromFsEntry(op.entry);
    } else if (op.op === "remove") {
      fileStore.delete(op.path);
      activeFiles.delete(op.path);
      // Remove rendered rows in every tab panel; also drops the
      // dir's `.tree-children` container so descendant rows go
      // with it. Server's bulk-remove op already lists each
      // descendant path, but we drop them here too for defensive
      // idempotence against partial deliveries.
      _removeRenderedRows(op.path);
    }
    // Live overlay for the Recent panel. The panel
    // reads from a separate base map so it can show files outside
    // the SSE ``root-depth-2`` scope; when an op falls inside the
    // active window, mirror it into that base too.
    recentBaseApplyOp(op);
  }
  notifyFileStoreSubscribers({ kind: "change", ops: ops });
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
// path. See the realtime-debugging guide for the layer-by-layer contract.
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
    sizeHtml: sizeHtml(entry.size || 0, "tree-item-size"),
    ageHtml:
      '<span class="tree-item-age">' +
      formatAge(fileMtimeSec) +
      '</span><span class="tree-item-activity"></span>',
    tipSize: entry.size || 0,
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
  var name = entry.name || "";
  var muted = "";
  if (entry.gitignored) {
    muted += " tree-item-gitignored";
  }
  if (entry.type === "dir") {
    var dirChip = treeDirChipHtml(entry.total_files, entry.total_size, options);
    var dirAge = formatAge(entry.newest_mtime_ns ? entry.newest_mtime_ns / 1e9 : 0);
    return (
      '<div class="tree-item tree-folder collapsed' +
      muted +
      '" data-action="select-dir" data-path="' +
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
      '<span class="tree-item-name">' +
      esc(name) +
      "</span>" +
      '<span class="tree-item-age-inline">' +
      dirAge +
      "</span>" +
      dirChip +
      "</div>" +
      '<div class="tree-children" style="display:none">' +
      '<div class="tree-lazy-placeholder" role="status" aria-label="Loading">' +
      '<span class="spinner spinner-sm" aria-hidden="true"></span>' +
      "</div>" +
      "</div>"
    );
  }
  if (entry.type === "symlink") {
    var linkAge = formatAge(entry.mtime_ns ? entry.mtime_ns / 1e9 : 0);
    return (
      '<div class="tree-item tree-symlink' +
      muted +
      '" data-action="select" data-path="' +
      esc(entry.path) +
      '" data-tip-type="symlink" data-tip-name="' +
      esc(name) +
      '" data-tip-mtime="' +
      (entry.mtime_ns || 0) / 1e9 +
      '">' +
      '<span class="tree-item-icon">' +
      ICONS.fileSymlink +
      "</span>" +
      '<span class="tree-item-name">' +
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
  return (
    '<div class="tree-item tree-file' +
    muted +
    '" data-action="select" data-path="' +
    esc(entry.path) +
    '" data-tip-type="file" data-tip-name="' +
    esc(name) +
    '" data-tip-size="' +
    (entry.size || 0) +
    '" data-tip-mtime="' +
    (entry.mtime_ns || 0) / 1e9 +
    // Live-inserted rows need the filter's extension too, or a row
    // arriving over the event stream would be judged on its last
    // suffix while the rendered ones are judged on the index's.
    (entry.ext ? `" data-ext="${esc(entry.ext)}` : "") +
    '">' +
    '<span class="tree-item-icon file-identity-icon ' +
    fi.cls +
    '">' +
    fi.svg +
    "</span>" +
    '<span class="tree-item-name">' +
    esc(name) +
    "</span>" +
    '<span class="tree-item-age-inline">' +
    '<span class="tree-item-age">' +
    fileAge +
    "</span>" +
    '<span class="tree-item-activity"></span>' +
    "</span>" +
    sizeHtml(entry.size || 0, "tree-item-size") +
    "</div>"
  );
}

// Find the rendered child container under which an entry's
// siblings live — for root entries this is `#tab-files`; for
// entries under a folder it's the `.tree-children` sibling of the
// `.tree-folder`. Returns null when the parent isn't rendered or
// is collapsed (in which case we don't insert — the row will
// appear when the user expands).
function _findChildContainerFor(parentRel, panelEl) {
  if (!parentRel) {
    return panelEl; // root
  }
  var folder = panelEl.querySelector(
    `.tree-folder[data-path="${escapePathForSelector(parentRel)}"]`,
  );
  if (!folder) {
    return null;
  }
  if (!folder.classList.contains("expanded")) {
    return null;
  }
  var children = folder.nextElementSibling;
  if (!children?.classList.contains("tree-children")) {
    return null;
  }
  return children;
}

// Insert a new row into a child container at sorted position.
// Containers may include a `.tree-page-more` sentinel at the end
// (when the initial render hit TREE_PAGE_SIZE); inserts go before
// it so the sort order isn't broken by new arrivals at the cap.
// Idempotent: if a row with this data-path already exists in the
// container, do nothing (the patch path will handle updates).
//
// The newly-inserted .tree-item gets a `tree-item-flash-in` class
// to play the pale-yellow → transparent fade defined in styles.css.
// The class is auto-removed on `animationend` so subsequent layout
// (selection, hover) doesn't fight a dangling class.
function _insertRowSorted(container, entry, options) {
  var safe = escapePathForSelector(entry.path);
  var existing = container.querySelector(`:scope > .tree-item[data-path="${safe}"]`);
  if (existing) {
    return false;
  }
  container.querySelectorAll(":scope > .tree-lazy-placeholder").forEach((el) => {
    el.remove();
  });
  var tmp = document.createElement("div");
  tmp.innerHTML = _buildRowHtml(entry, options);
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
    // Insert before the page-more sentinel if present, else at the end.
    var more = container.querySelector(":scope > .tree-page-more");
    anchor = more || null;
  }
  for (var j = 0; j < nodes.length; j++) {
    var node = nodes[j];
    container.insertBefore(node, anchor);
    // Only flash the .tree-item itself; the sibling .tree-children
    // for folders is empty on insert (lazy placeholder) and would
    // visually double-flash if we styled it too.
    if (node.classList?.contains("tree-item")) {
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
  // When the split row is on screen these selectors find nothing by
  // design (see treeSummaryHtml): the blind aggregate cannot express
  // tracked-versus-ignored, so the split refreshes itself instead.
  var countEl = queryHtml(".tree-summary-count");
  var sizeEl = queryHtml(".tree-summary-size");
  if (countEl) {
    countEl.innerHTML = countHtml(totalFiles);
  }
  if (sizeEl) {
    sizeEl.innerHTML = sizeHtml(totalSize);
  }
  scheduleRootSummaryRefresh();
  var pathEl = queryHtml(".header-path");
  if (pathEl) {
    pathEl.dataset.tipFiles = nullableDataValue(totalFiles);
    pathEl.dataset.tipSize = nullableDataValue(totalSize);
    pathEl.dataset.tipMtime = nullableDataValue(newestMtime);
  }
}

function applyCellPatch(entry) {
  // The root (path "") is the implicit tree container, never a row. The
  // server includes it in the fs.snapshot for its aggregate totals, but
  // patching it here would fall through to the insert branch (its parent
  // resolves to the panel root) and graft a phantom row for the served
  // dir *inside itself* — flashed yellow like a new file on every
  // (re)connect. Keep it in the store; just don't render it.
  if (!entry.path) {
    updateRootAggregatePresentation(entry);
    reconcilePendingTallyDiagnostics();
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
          row.classList.toggle("tree-item-empty", entry.empty);
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
  var panel = document.getElementById("tab-files");
  if (!panel) {
    return;
  }
  var container = _findChildContainerFor(parentRel, panel);
  if (!container) {
    return;
  }
  _insertRowSorted(container, entry, treeRenderOptionsForElement(panel));
  // A freshly inserted row carries no filter classes yet; without this
  // a new file would show up regardless of the active filter.
  scheduleFilterReapply();
  reconcilePendingTallyDiagnostics();
}

// Remove all rendered rows (in any tab panel) for *path*. For
// folders, also removes the sibling .tree-children container so
// the rendered subtree is gone too. Called by fileStoreApplyChange
// on op=remove. Idempotent.
//
// The row gets a `tree-item-flash-out` class so it briefly flashes
// pale yellow + fades to opacity 0 + collapses height to 0, THEN
// the JS drops it from the DOM. ``forwards`` fill mode in the
// CSS keeps the row invisible during the small gap between
// `animationend` and the actual `.remove()` call. The folder's
// sibling `.tree-children` is removed immediately (no animation
// — its descendants would double-animate as their own removes
// arrive on the wire, and a collapsing tree-children container
// reads as confusing motion).
function _removeRenderedRows(path) {
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
            target.remove();
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
  var safe = escapePathForSelector(path);
  var rows = queryHtmlAll(`.tree-item[data-path="${safe}"]`);
  for (var i = 0; i < rows.length; i++) {
    var row = rows[i];
    if (row.classList.contains("tree-folder")) {
      var children = row.nextElementSibling;
      if (children?.classList.contains("tree-children")) {
        children.remove();
      }
    }
    row.remove();
  }
}

// Recency re-cluster scheduling: debounced so a burst of fs.change
// ops doesn't render-thrash. The recency source reads from
// ``recentBaseEntries`` (fetched from /api/recent plus a live overlay
// from fs.change), so updates inside the active window flow through
// without a refetch.
var _recentRecomputeHandle = null;
function _scheduleRecentRecompute() {
  if (!recentEverLoaded) {
    return; // never fetched; nothing to recompute
  }
  if (!filesPanelUsesRecentSource()) {
    return; // the panel is showing the full tree; that path has its own updates
  }
  if (_recentRecomputeHandle) {
    return; // already pending
  }
  _recentRecomputeHandle = setTimeout(() => {
    _recentRecomputeHandle = null;
    renderRecentFromBase();
  }, RECENT_RECLUSTER_DEBOUNCE_MS);
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

function _createInventoryEventSource() {
  try {
    inventoryEventSource = new EventSource("/api/events?scope=root-depth-2");
  } catch (_e) {
    inventoryEventSource = null;
    _scheduleInventoryReconnect();
    return;
  }
  inventoryEventSource.addEventListener("fs.snapshot", (e) => {
    try {
      var data = JSON.parse(e.data);
      fileStoreApplySnapshot(data.scope, data.entries || []);
      _scheduleRecentRecompute();
      // A fresh snapshot after the first one means the connection
      // was rebuilt and catalog deltas may have been dropped; the
      // feed refetches the bulk catalog to restore continuity.
      quickFileCatalogFeed?.onSentinelSnapshot();
    } catch (_e) {
      /* malformed frame; ignore */
    }
  });
  inventoryEventSource.addEventListener("fs.change", (e) => {
    try {
      var data = JSON.parse(e.data);
      fileStoreApplyChange(data.ops || []);
      _scheduleRecentRecompute();
    } catch (_e) {
      /* ignore */
    }
  });
  inventoryEventSource.addEventListener("catalog.change", (e) => {
    try {
      var data = JSON.parse(e.data);
      quickFileCatalogFeed?.onCatalogChange(data);
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
      }
    } catch (_e) {
      /* ignore */
    }
  });
  inventoryEventSource.addEventListener("fs.resync_required", (_e) => {
    // A resync marks a gap in the ordered delta stream. Clear derived state,
    // then replace this connection so the server sends an authoritative
    // snapshot before live updates resume.
    knownFileCatalog?.clear();
    fileStore = new Map();
    notifyFileStoreSubscribers({ kind: "resync" });
    startIndexProgressPolling();
    quickFileCatalogFeed?.onResync();
    _scheduleInventoryReconnect();
  });
  inventoryEventSource.onopen = () => {
    // Do not erase accumulated failure state as soon as a socket opens. A
    // connection that survives this interval is healthy enough to reset the
    // exponential backoff; repeated overflow/resync cycles keep backing off.
    _scheduleEsStableReset();
    // The first open starts the bulk catalog fetch after subscription;
    // later opens refetch to cover deltas lost while disconnected.
    quickFileCatalogFeed?.start();
  };
  inventoryEventSource.onerror = () => {
    _cancelEsStableReset();
    _esConsecutiveErrors += 1;
    if (_esConsecutiveErrors >= _ES_MAX_CONSECUTIVE_ERRORS) {
      // Circuit breaker: too many consecutive errors without a
      // successful open or message. Close and recreate with
      // exponential backoff. A fresh connection gets a snapshot
      // via the existing fs.snapshot/resync flow.
      _scheduleInventoryReconnect();
    }
  };
}

function startInventoryEventStream() {
  if (typeof EventSource === "undefined") {
    // Graceful degradation: no live deltas, but the one-shot bulk
    // fetch still gives the palette complete-as-of-fetch coverage.
    quickFileCatalogFeed?.start();
    return;
  }
  if (inventoryEventSource) {
    return;
  }
  _createInventoryEventSource();
}

// ── Canonical navigation ───────────────────────────────────────

var navigationController = null;

function showNavigationLanding() {
  closeLiveStream();
  currentPath = "";
  setSelectedPath(null);
  disposeActivePluginViews();
  stopFolderHeaderSubscription();
  const preview = document.getElementById("preview-pane");
  if (preview) {
    preview.innerHTML = '<div class="preview-empty">Select a file to preview.</div>';
  }
}

function deliverNavigationFragment(target) {
  window.dispatchEvent(
    new CustomEvent("metabrowser:navigation-fragment", {
      detail: { target: target },
    }),
  );
}

async function applyNavigationTarget(target, context) {
  if (!target) {
    showNavigationLanding();
    return { status: "cancelled" };
  }
  var path = target.path.replace(/\/$/, "");
  if (!context.pathChanged) {
    deliverNavigationFragment(target);
    return {
      focusTarget: document.getElementById("preview-pane") || undefined,
      status: "opened",
    };
  }
  await revealInTree(path);
  if (!context.isCurrent()) {
    return { status: "cancelled" };
  }
  var outcome = await selectFile(path, context.viewId);
  if (outcome.status === "opened" && context.isCurrent()) {
    deliverNavigationFragment(navigationController?.current() || target);
  }
  return outcome;
}

// Expand tree folders along ``path`` (loading lazy subtrees as needed)
// and mark the target row selected. Returns true if the row exists.
// Pair with selectFile() for the body; init() kicks off both legs in
// parallel so a deep-link doesn't pay tree-walk latency before its own
// request leaves the client.
async function revealInTree(path) {
  if (!path) {
    return false;
  }
  var segments = path.split("/");
  var current = "";
  for (var i = 0; i < segments.length - 1; i++) {
    current = current ? `${current}/${segments[i]}` : segments[i];
    var folder = queryHtml(`.tree-folder[data-path="${escapePathForSelector(current)}"]`);
    if (folder) {
      var children = /** @type {HTMLElement | null} */ (folder.nextElementSibling);
      if (children) {
        if (children.querySelector(".tree-lazy-placeholder")) {
          await loadSubtree(current, children);
        }
        window.MetabrowserTreeExpansion.setFolderExpanded(folder, children, true);
      }
    }
  }
  var target = document.querySelector(`.tree-item[data-path="${escapePathForSelector(path)}"]`);
  if (!target) {
    return false;
  }
  setSelectedPath(path);
  target.scrollIntoView({ block: "nearest" });
  return true;
}

/** @returns {Promise<QuickFileOpenOutcome>} */
async function navigateToPath(path, preferredViewId) {
  if (!navigationController) {
    return {
      message: "Navigation is unavailable. Refresh the page to try again.",
      status: "error",
    };
  }
  var folder = path === "/" || path.endsWith("/");
  var normalized = path === "/" ? "" : path.replace(/\/+$/, "");
  return navigationController.open(
    { path: folder && normalized ? `${normalized}/` : normalized },
    preferredViewId ? { viewId: preferredViewId } : undefined,
  );
}

// Compose the application-lifetime quick-file modules at the shell boundary.
function initQuickFileFinder() {
  if (quickFilePalette) {
    return;
  }
  if (
    !window.MetabrowserKnownFileCatalog ||
    !window.MetabrowserFileFuzzyMatch ||
    !window.MetabrowserSearch ||
    !window.MetabrowserSearchPalette
  ) {
    console.warn("Quick File dependencies are unavailable");
    return;
  }

  knownFileCatalog = window.MetabrowserKnownFileCatalog.create();
  if (window.MetabrowserCatalogFeed) {
    quickFileCatalogFeed = window.MetabrowserCatalogFeed.create({
      catalog: knownFileCatalog,
    });
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
  quickFilePalette = window.MetabrowserSearchPalette.create({
    controller: quickFileSearchController,
    getCatalogSnapshot: () => knownFileCatalog.snapshot(),
    getFileIcon: getFileIcon,
    maxRows: QUICK_FILE_RESULT_LIMIT,
    // Coverage grows while the palette is open — the bulk feed lands, then
    // live deltas — so an open search re-runs instead of keeping the result
    // set it happened to get first.
    subscribeCatalog: (listener) => knownFileCatalog.subscribe(listener),
    onNotFound: (path) => {
      knownFileCatalog.removePath(path);
    },
    openFile: (path) => {
      // Search hits can outlive deep inventory changes that are outside the
      // shallow event stream. Force the existing ETag path to confirm the file
      // still exists before treating palette navigation as successful.
      fileNeedsRevalidate.add(path);
      boundMapSize(fileNeedsRevalidate, ETAG_REVALIDATE_MAX);
      return navigateToPath(path);
    },
  });
}

if (window.MetabrowserNavigationRoute) {
  navigationController = window.MetabrowserNavigationRoute.createController({
    apply: applyNavigationTarget,
  });
  window.MetabrowserNavigationRoute.attachController(navigationController);
} else {
  console.error("Canonical navigation module is unavailable");
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
  window.MetabrowserDebug = {
    clearFileCache: clearBrowserFileCache,
    selectFile: selectFile,
  };

  function enhanceCurrentFileAfterOptionalAsset() {
    highlightCode();
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

document.addEventListener("DOMContentLoaded", async () => {
  initTooltip();
  initSettingsControl();
  initNavTabs();
  initFilterBar();
  initNavScrollShadow();
  initQuickFileFinder();
  // Start the URL-pinned file fetch in parallel with the tree walk. The
  // canonical controller reads only /view/ pathname routes; a legacy hash on
  // the landing URL is document state, never a file identity.
  var initialTarget = window.MetabrowserNavigationRoute?.parse(
    location.pathname,
    location.search,
    location.hash,
  );
  var initialPath = initialTarget?.path.replace(/\/$/, "") || "";
  navigationController?.start().catch((error) => {
    console.error("Could not initialize browser navigation", error);
  });
  startIndexProgressPolling();
  // The tree fetch always runs: it supplies the header path and root
  // aggregates before any later recency selection repaints the panel
  // from /api/recent.
  await loadTree();
  if (filesPanelUsesRecentSource()) {
    loadRecent(filterState.get().recency);
  }
  initPaneResize("tree-resize", ".tree-pane", 180, null);
  if (initialPath) {
    revealInTree(initialPath);
  }
  // /api/events is the single source for tree decoration and
  // active-file badges; ActiveFileTracker emits fs.change ops
  // with active/labels populated.
  startInventoryEventStream();
});
