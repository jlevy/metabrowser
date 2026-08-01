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

// Size-weight convention — single source of truth. Anything displaying a
// byte count anywhere in the SPA (file tree, file header, app header,
// drawer, tooltip) reaches for these helpers so "big = bold, small =
// normal" is identical everywhere. Threshold is 1 MiB; to change it,
// change here and nowhere else.
var SIZE_LARGE_THRESHOLD = 1024 * 1024;
function sizeClass(bytes) {
  return (bytes || 0) > SIZE_LARGE_THRESHOLD ? "size-large" : "";
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
// above COUNT_LARGE_THRESHOLD bold up the same way sizes above
// SIZE_LARGE_THRESHOLD do — the two helpers share the same visual
// scale because they describe the same data category.
var COUNT_LARGE_THRESHOLD = 1000;
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
  return (n || 0) >= COUNT_LARGE_THRESHOLD ? "count-large" : "";
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
  document.documentElement.setAttribute("data-theme-mode", normalized);
  document.documentElement.setAttribute("data-theme", resolved);
  // Metabrowser is the single theme owner for embedded KPress fragments.
  // KPress reads this resolved value from the root; fragments remain
  // theme-agnostic and its automatic manifest omits the standalone resolver.
  document.documentElement.setAttribute("data-kpress-resolved-theme", resolved);
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

// ── Tree ────────────────────────────────────────────────────────

async function loadTree() {
  return _perf.measureAsync("loadTree", async () => {
    const resp = await fetch("/api/tree");
    if (!resp.ok) {
      console.warn(`loadTree: HTTP ${resp.status}`);
      const treeEl = document.getElementById("tree-content");
      if (treeEl) {
        treeEl.innerHTML = `<div class="preview-empty">Failed to load tree (HTTP ${resp.status})</div>`;
      }
      return;
    }
    const data = await _perf.measureAsync(
      "apiTree:json",
      () => resp.json(),
      responsePerfMeta(resp, ""),
    );
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
      } else {
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
    var summaryHtml =
      '<div class="tree-summary">' +
      '<span class="tree-summary-count">' +
      countHtml(summaryFiles) +
      "</span>" +
      '<span class="tree-summary-size">' +
      sizeHtml(summarySize) +
      "</span>" +
      "</div>";
    // Walker truncation banner. The InventoryIndex
    // walker stops at INVENTORY_MAX_FILES; finalized dirs still
    // emit accumulated totals so the UI is usable, but the user
    // had no signal that the tree was incomplete.
    var truncationHtml = "";
    if (data.tally_cache_status === "truncated") {
      truncationHtml = treeTruncationNoteHtml(data.tally_cache_max_files);
    }
    _perf.measure(
      "renderTreeNodes:root",
      () => {
        pendingTreePages.clear();
        pendingTreePageId = 0;
        // Files and Recent are sibling panels inside #tree-content.
        var filesPanel = document.getElementById("tab-files");
        if (filesPanel) {
          filesPanel.innerHTML = truncationHtml + summaryHtml + renderTreeNodes(data.tree, true);
        }
      },
      { nodes: data.tree ? data.tree.length : 0 },
    );
  });
}

function treeTruncationNoteHtml(maxFiles) {
  var capText = maxFiles ? formatCount(maxFiles) : "the file cap";
  return (
    '<div class="tree-truncation-note" role="status">' +
    "Tree partial: capped at " +
    capText +
    ". " +
    "Deep subtrees may be incomplete." +
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

function treeRenderOptionsForElement(el) {
  return el?.closest?.("#tab-recent")
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
        `<div class="tree-item tree-folder ${stateClass}${mutedCls}" data-action="toggle" data-path="${esc(node.path)}" data-tip-type="dir" data-tip-name="${esc(node.name)}" data-tip-files="${nullableDataValue(node.total_files)}" data-tip-size="${nullableDataValue(node.total_size)}" data-tip-mtime="${nullableDataValue(node.mtime || 0)}">`,
        ICONS.toggle,
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
    } else {
      // Icon dispatch keys off the *logical* name so subtype matchers
      // (`.process.md`, `.runbook.md`, etc.) work on `foo.process.md.gz`.
      var fi = getFileIcon(getLogicalName(node));
      var fileAge = formatAge(node.mtime);
      var compressed = !!node.compressed;
      var iconCls = `tree-item-icon ${fi.cls}${compressed ? " is-compressed" : ""}`;
      var compressionName = node.compression || "compressed";
      var compressionGlyph = compressionName === "gzip" ? "G" : "Z";
      var compressionBadge = compressed
        ? `<span class="compression-badge" title="${esc(compressionName)} compressed">${compressionGlyph}</span>`
        : "";
      var logicalExtAttr = node.logical_ext ? ` data-logical-ext="${esc(node.logical_ext)}"` : "";
      var compressedAttr = compressed ? ' data-compressed="1"' : "";
      parts.push(
        `<div class="tree-item tree-file${mutedCls}" data-action="select" data-path="${esc(node.path)}"${logicalExtAttr}${compressedAttr} data-tip-type="file" data-tip-name="${esc(node.name)}" data-tip-size="${node.size || 0}" data-tip-mtime="${node.mtime || 0}">`,
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
    esc(message || "Loading folder...") +
    "</span>" +
    "</div>"
  );
}

function treeLazyFailureHtml(message) {
  return (
    '<div class="tree-lazy-placeholder tree-lazy-error" role="status">' +
    esc(message || "Unable to load folder.") +
    "</div>"
  );
}

function errorMessage(e) {
  return e?.message ? e.message : String(e || "unknown error");
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
  childrenEl.innerHTML = treeLazyLoadingHtml("Loading folder...");
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
    if (tree.length === 0 && data.tally_cache_status === "scanning") {
      childrenEl.innerHTML = treeLazyLoadingHtml("Folder still loading...");
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
          : '<div class="tree-lazy-placeholder">Empty folder</div>';
      },
      { path: path, nodes: tree.length },
    );
  } catch (e) {
    console.warn(`loadSubtree failed for ${path}`, e);
    clearSubtreeRetry(childrenEl);
    childrenEl.innerHTML = treeLazyFailureHtml(`Unable to load folder (${errorMessage(e)}).`);
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
    return '<span class="tip-loading">Loading size...</span>';
  }
  var cls = `size ${sizeClass(bytes)}`.trim();
  return `<span class="${cls}">${formatExactSize(bytes || 0)}</span>`;
}
function _tipCount(n) {
  if (isPendingNumber(n)) {
    return '<span class="tip-loading">Loading file count...</span>';
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
    ch.style.display = "block";
    folder.classList.remove("collapsed");
    folder.classList.add("expanded");
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
      folder.classList.remove("expanded");
      folder.classList.add("collapsed");
    }
  });
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
    }
    return;
  }
  const item = /** @type {HTMLElement | null} */ (target.closest(".tree-item"));
  if (!item) {
    return;
  }
  const action = item.dataset.action;
  if (action === "toggle") {
    var children = /** @type {HTMLElement | null} */ (item.nextElementSibling);
    if (!children) {
      return;
    }
    if (e.shiftKey) {
      // Shift+click: recursive expand/collapse.
      var wasExpanded = children.style.display !== "none";
      if (wasExpanded) {
        collapseAllDescendants(children);
        children.style.display = "none";
        item.classList.remove("expanded");
        item.classList.add("collapsed");
      } else {
        children.style.display = "block";
        item.classList.remove("collapsed");
        item.classList.add("expanded");
        if (children.querySelector(":scope > .tree-lazy-placeholder")) {
          loadSubtree(item.dataset.path, children).then(() => {
            expandAllDescendants(children);
          });
        } else {
          expandAllDescendants(children);
        }
      }
    } else {
      // Normal click: toggle single level.
      var isExpanded = children.style.display !== "none";
      children.style.display = isExpanded ? "none" : "block";
      item.classList.toggle("expanded", !isExpanded);
      item.classList.toggle("collapsed", isExpanded);
      if (!isExpanded && children.querySelector(".tree-lazy-placeholder")) {
        loadSubtree(item.dataset.path, children);
      }
    }
  } else if (action === "select") {
    setSelectedPath(item.dataset.path);
    selectFile(item.dataset.path);
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

// ── Nav tabs (Files / Recent) ──────────────────────────────────
//
// Files panel reuses the existing tree machinery. Recent fetches a
// flat newest-first leaf list from /api/recent (filter + gitignore
// resolved server-side) and clusters it here via
// ``clusterRecentTreeJs`` — clustering is a rendering concern, owned
// by this layer. See ``metabrowser/recent.py`` for the layering
// rationale. Both panels share the same .tab-bar styling as the
// file-preview tabs (see :root --tab-active-* vars in styles.css).

// Client constants come from window.METABROWSER_SETTINGS (injected
// by the Starlette index handler). The server-side
// metabrowser.settings module is the single source of
// truth for every tunable in the browser plane; this avoids
// duplicating constants between Python and JS.
var _METABROWSER_SETTINGS = (typeof window !== "undefined" && window.METABROWSER_SETTINGS) || {};
const RECENT_LIMIT = _METABROWSER_SETTINGS.RECENT_LIMIT || 2000;
const RECENT_WINDOWS = _METABROWSER_SETTINGS.RECENT_WINDOWS || ["1h", "24h", "7d", "30d", "all"];
const RECENT_RECLUSTER_DEBOUNCE_MS = _METABROWSER_SETTINGS.RECENT_RECLUSTER_DEBOUNCE_MS || 100;
const RECENT_CLUSTER_PCT = _METABROWSER_SETTINGS.RECENT_CLUSTER_PCT || 0.05;
const INDEX_PROGRESS_POLL_MS = _METABROWSER_SETTINGS.INDEX_PROGRESS_POLL_MS || 1000;
const INDEX_PROGRESS_UPDATE_FILES = _METABROWSER_SETTINGS.INDEX_PROGRESS_UPDATE_FILES || 1024;
var currentRecentWindow = _METABROWSER_SETTINGS.RECENT_DEFAULT_WINDOW || "24h";
var recentEverLoaded = false;

// Lightweight pull-based scan progress for the nav footer. This
// intentionally reads /api/index/progress instead of the full meta
// envelope so it never scans known entries while the index is active.
var indexProgressTimer = null;
var indexProgressInFlight = false;
var indexProgressLastRendered = null;
var indexProgressCompletionRefreshInFlight = false;

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
  if (!document.querySelector(".tally-pending")) {
    return;
  }
  indexProgressCompletionRefreshInFlight = true;
  try {
    await loadTree();
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
      if (tabId === "recent" && !recentEverLoaded) {
        loadRecent(currentRecentWindow);
      }
    });
  });
}

// Toggle the nav tab bar's drop shadow based on whether the
// tree-content scroll position is at the top. At scrollTop=0 the
// shadow would fall onto whitespace and read as floating chrome;
// once content has scrolled under the tabs the shadow becomes
// useful as a "there's more above" cue. The hairline border-bottom
// from .tab-bar stays in both states.
function initNavScrollShadow() {
  const navBar = queryHtml(".nav-tab-bar");
  const content = document.getElementById("tree-content");
  if (!navBar || !content) {
    return;
  }
  const scrollNavBar = navBar;
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

// Window key → seconds-back from "now". Mirror of
// RECENT_WINDOW_SECONDS in metabrowser/settings.py; if you
// change one, change the other (or move both behind the
// METABROWSER_SETTINGS injection).
var _RECENT_WINDOW_SECONDS = {
  "1h": 60 * 60,
  "24h": 24 * 60 * 60,
  "7d": 7 * 24 * 60 * 60,
  "30d": 30 * 24 * 60 * 60,
  all: null,
};

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
  // Lock the user's window intent synchronously so the chip-
  // click handler's dedup is honoured.
  currentRecentWindow = windowKey;
  ensureRecentScaffold();
  setActiveRecentChip(windowKey);
  recentEverLoaded = true;
  fetchRecent(windowKey);
}

function fetchRecent(windowKey) {
  if (recentInflight) {
    recentInflight.abort();
    recentInflight = null;
  }
  var results = document.getElementById("recent-results");
  if (results && recentBaseEntries.size === 0) {
    results.innerHTML = '<div class="recent-empty">Loading recent files…</div>';
  }
  var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
  recentInflight = ctrl;
  var url =
    "/api/recent?window=" +
    encodeURIComponent(windowKey) +
    "&limit=" +
    encodeURIComponent(String(RECENT_LIMIT));
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
      if (windowKey !== currentRecentWindow) {
        return; // user clicked another chip
      }
      recentBaseEntries = new Map();
      var flat = data?.entries_flat || [];
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
      renderRecentFromBase();
      if (currentPath) {
        setSelectedPath(currentPath);
      }
    })
    .catch((err) => {
      if (err && err.name === "AbortError") {
        return;
      }
      if (windowKey !== currentRecentWindow) {
        return;
      }
      if (results) {
        results.innerHTML = '<div class="recent-empty">Failed to load recent files.</div>';
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
function renderRecentFromBase() {
  const results = document.getElementById("recent-results");
  if (!results) {
    return;
  }
  _perf.measure(
    "renderRecent:root",
    () => {
      var entries = recentEntriesFromBase({
        window: currentRecentWindow,
        limit: RECENT_LIMIT,
      });
      if (entries.length === 0) {
        results.innerHTML = renderRecentList({ tree: [] });
        return;
      }
      var nowSec = Date.now() / 1000;
      var tree = clusterRecentTreeJs(entries, nowSec, RECENT_CLUSTER_PCT);
      results.innerHTML = renderRecentList({
        tree: tree,
        total_matching: recentTotalMatching,
        truncated: recentTruncated,
      });
    },
    { items: recentBaseEntries.size },
  );
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
    if (seconds !== null) {
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

function ensureRecentScaffold() {
  var panel = document.getElementById("tab-recent");
  if (document.getElementById("recent-controls")) {
    return;
  }
  if (!panel) {
    return;
  }
  panel.innerHTML = `${renderRecentControls(currentRecentWindow)}<div id="recent-results"></div>`;
}

function renderRecentControls(windowKey) {
  var parts = ['<div class="recent-controls" id="recent-controls">'];
  for (var i = 0; i < RECENT_WINDOWS.length; i++) {
    var w = RECENT_WINDOWS[i];
    var active = w === windowKey ? " active" : "";
    parts.push(
      '<button class="recent-chip' +
        active +
        '" data-action="recent-window" data-window="' +
        esc(w) +
        '">' +
        esc(w) +
        "</button>",
    );
  }
  parts.push("</div>");
  return parts.join("");
}

function setActiveRecentChip(windowKey) {
  queryHtmlAll("#recent-controls .recent-chip").forEach((chip) => {
    chip.classList.toggle("active", chip.dataset.window === windowKey);
  });
}

function renderRecentList(data) {
  var tree = data.tree || [];
  if (tree.length === 0) {
    return '<div class="recent-empty">No files modified in this window.</div>';
  }
  // Reuse the Files-tab renderer with one mode flip: dir rows
  // show file count instead of total bytes (see comments on
  // renderTreeNodes: aggregating bytes across "files modified
  // in last 24h" mixes incomparable things). isRoot=true so the
  // viewport-bounded expansion planner can select compact folders;
  // the Recent tree builder leaves ``expanded`` unset on those
  // nodes so explicit cluster-collapse state still wins.
  var body = renderTreeNodes(tree, true, { dirMetric: TREE_DIR_METRIC_COUNT });
  // Truncation banner: when total_matching exceeds the cap (server
  // tops out at ``RECENT_MAX_LIMIT = 2 000``), tell the user the
  // window has more files than the response includes.
  if (data.truncated && data.total_matching) {
    body =
      '<div class="recent-truncated-note">Showing ' +
      RECENT_LIMIT +
      " of " +
      data.total_matching +
      " files. Narrow the window to see fewer.</div>" +
      body;
  }
  return body;
}

// Window-chip clicks delegated off #tree-pane (the same listener
// that handles tree-item / page-more clicks); this binds the
// chip-specific behavior. Picking the same chip again is a
// no-op so a stray click doesn't trigger an extra fetch.
treePane.addEventListener("click", (e) => {
  var target = eventTargetElement(e);
  var chip = /** @type {HTMLElement | null} */ (target?.closest("[data-action='recent-window']"));
  if (!chip) {
    return;
  }
  var w = chip.dataset.window;
  if (w === currentRecentWindow) {
    return;
  }
  loadRecent(w);
});

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
      return;
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

async function selectFile(path, skipHash) {
  return _perf.measureAsync(
    "selectFile",
    async () => {
      // Always close any prior live stream — switching files (or reopening
      // the same file) starts fresh.
      closeLiveStream();
      currentPath = path;
      // Update URL hash for deep-linking (replaceState — lateral navigation, not history).
      if (!skipHash) {
        history.replaceState(null, "", `#${encodeURIComponent(path)}`);
      }
      const preview = document.getElementById("preview-pane");
      if (!preview) {
        return;
      }

      // Three-way cache state:
      //   - hot: in fileCache and not flagged → serve from cache.
      //   - revalidate: in fileCache but flagged (file recently changed in
      //     activity poll) → send If-None-Match, accept 304 to confirm.
      //   - cold: not in fileCache → unconditional fetch.
      const cached = fileCache.get(path);
      const needsRevalidate = fileNeedsRevalidate.has(path);
      if (cached && !needsRevalidate && !activeFiles.has(path)) {
        renderFile(cached);
        maybeOpenLiveStream(path, cached);
        return;
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
        preview.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';
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
            renderFile(cached);
            maybeOpenLiveStream(path, cached);
          }
          return;
        }
        if (!resp.ok) {
          const text = await _perf.measureAsync(
            "apiFile:errorText",
            () => resp.text(),
            responsePerfMeta(resp, path),
          );
          throw new Error(text || `HTTP ${resp.status}`);
        }
        const data = await _perf.measureAsync(
          "apiFile:json",
          () => resp.json(),
          responsePerfMeta(resp, path),
        );
        cachePut(fileCache, path, data, CACHE_MAX, evictFileCacheMetadata);
        const etagHeader = resp.headers.get("etag");
        if (etagHeader) {
          fileETags.set(path, etagHeader);
          boundMapSize(fileETags, ETAG_REVALIDATE_MAX);
        }
        fileNeedsRevalidate.delete(path);
        if (currentPath === path) {
          if (loadingIndicatorTimer) {
            clearTimeout(loadingIndicatorTimer);
            loadingIndicatorTimer = null;
          }
          renderFile(data);
          maybeOpenLiveStream(path, data);
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        if (currentPath === path) {
          if (loadingIndicatorTimer) {
            clearTimeout(loadingIndicatorTimer);
            loadingIndicatorTimer = null;
          }
          disposeActivePluginViews();
          preview.innerHTML = `<div class="preview-empty">Error: ${esc(errorMessage(err))}</div>`;
        }
      }
    },
    { path: path, skip_hash: !!skipHash },
  );
}

// ── File rendering ──────────────────────────────────────────────

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
      '<button class="file-header-action" onclick="loadMoreCurrentText()" title="Load another text chunk">Load more</button>';
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
    c.dataset.activeView = isActive ? "true" : "false";
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

var activePluginDisposers = [];

function disposeActivePluginViews() {
  if (!activePluginDisposers.length) {
    return;
  }
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
  if (typeof pluginView.dispose === "function") {
    activePluginDisposers.push(pluginView.dispose);
  }
  try {
    var maybePromise = pluginView.render(container, ctx);
    if (maybePromise && typeof maybePromise.catch === "function") {
      maybePromise.catch((err) => {
        container.innerHTML =
          '<div class="preview-empty">Plugin render error: ' +
          esc(String(err?.message || err)) +
          "</div>";
      });
    }
  } catch (err) {
    container.innerHTML = `<div class="preview-empty">Plugin render error: ${esc(errorMessage(err))}</div>`;
  }
}

function renderFile(data) {
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

      // Build header
      var badges = renderBadges(data);
      let html = '<div class="file-header">';
      html +=
        '<span class="file-header-path">' +
        esc(data.path) +
        '<button class="file-header-copy" onclick="copyPath(this, \'' +
        esc(data.path).replace(/'/g, "\\'") +
        '\')" title="Copy path">' +
        ICON_COPY +
        "</button>" +
        "</span>";
      html += badges;
      html += sizeHtml(data.size, "file-header-size");
      html += renderTextPreviewControls(data);
      html +=
        '<button class="file-header-icon file-header-print" id="print-view-btn" type="button" onclick="printActiveView()" title="Print view" aria-label="Print view" hidden>' +
        (ICONS.print || "") +
        "</button>";
      html += "</div>";

      // Data-driven tab rendering from server views.
      //
      // Every (kind, viewId) goes through the plugin registry: built-in
      // plugins (markdown, agent-log, unknown-jsonl, text) own their own
      // kinds; entry-point plugins own theirs. The shell here
      // builds the empty containers; each plugin's render(container, ctx)
      // fires below once the DOM is in place. If no plugin claims a
      // (kind, viewId) we paint an "Unknown view" empty state — never a
      // fallback that pulls renderers out of the shell. This is the
      // contract: every kind is a plugin.
      var views = data.views;
      var pluginRenders = [];
      if (views && views.length > 0) {
        if (views.length > 1) {
          html += '<div class="tab-bar">';
          for (let i = 0; i < views.length; i++) {
            const view = views[i];
            var active = view.default ? " active" : "";
            html +=
              '<button class="tab-btn' +
              active +
              '" data-tab="' +
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
          var hidden = view.default ? "" : ' style="display:none;"';
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
              '><div class="preview-empty">Unknown view: ' +
              esc(view.id) +
              "</div></div>";
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
        html += `<div class="content-body"><div class="preview-empty">Binary file (${formatSize(data.size || 0)})</div></div>`;
      } else if (data.type === "jsonl_too_large") {
        html +=
          '<div class="content-body"><div class="preview-empty">' +
          "<strong>Log file too large for browser parsing</strong><br><br>" +
          "Size: " +
          formatSize(data.size || 0) +
          " (limit: " +
          formatSize(data.max_size || 0) +
          ")<br><br>" +
          "View with:<br><code>tail -f " +
          esc(data.path) +
          "</code>" +
          "</div></div>";
      } else if (data.type === "error") {
        html += `<div class="content-body"><div class="preview-empty">Error: ${esc(data.error)}</div></div>`;
      }

      _perf.measure(
        "renderFile:mount",
        () => {
          preview.innerHTML = html;
        },
        filePerfMeta(data, { html_chars: html.length }),
      );
      var defaultActiveView = null;
      if (views?.length) {
        defaultActiveView = views.find((v) => v.default) || views[0];
        setActivePreviewView(defaultActiveView.id, preview);
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
          if (defaultActiveView && pr.tabId === defaultActiveView.id) {
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

// biome-ignore lint/correctness/noUnusedVariables: referenced from generated HTML.
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
            tail += renderEvt(batch.events[j], startIdx + j);
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
  fileStore = new Map();
  for (var i = 0; i < entries.length; i++) {
    fileStore.set(entries[i].path, entries[i]);
    applyCellPatch(entries[i]);
    _mirrorActiveFromFsEntry(entries[i]);
  }
  notifyFileStoreSubscribers({ kind: "snapshot", scope: scope });
}

function fileStoreApplyChange(ops) {
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
}

// Pure function: derive the patched cell HTML for a single
// FsEntry. Returns separate dir/file shapes; applyCellPatch picks
// the matching DOM target (.tree-folder vs .tree-file).
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
      '" data-action="toggle" data-path="' +
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
      ICONS.toggle +
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
    '">' +
    '<span class="tree-item-icon ' +
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
// siblings live — for root entries this is `#tab-files` (or
// `#tab-recent` on the Recent panel); for entries under a folder
// it's the `.tree-children` immediate sibling of the
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
    } else if (ch.classList.contains("tree-file")) {
      var name2 = ch.querySelector(".tree-item-name");
      var k2 = _treeSortKey({
        type: "file",
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

// Apply the patch+insert path for one fs.change op. For type=file,
// patches existing .tree-file rows (size/age/active). For type=dir,
// patches existing .tree-folder rows (metric chip + age + tip-*). If
// no row exists for the entry's path AND the entry's parent is
// rendered + expanded in either tab panel, insert a new row in
// sorted position so the user sees new files/dirs without a reload.
function updateRootAggregatePresentation(entry) {
  if (entry.path || entry.type !== "dir") {
    return;
  }
  var totalFiles = entry.total_files == null ? null : entry.total_files;
  var totalSize = entry.total_size == null ? null : entry.total_size;
  var newestMtime = entry.newest_mtime_ns ? entry.newest_mtime_ns / 1e9 : 0;
  var countEl = queryHtml(".tree-summary-count");
  var sizeEl = queryHtml(".tree-summary-size");
  if (countEl) {
    countEl.innerHTML = countHtml(totalFiles);
  }
  if (sizeEl) {
    sizeEl.innerHTML = sizeHtml(totalSize);
  }
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
    return;
  }
  var safePath = escapePathForSelector(entry.path);
  var selector =
    entry.type === "dir"
      ? `.tree-folder[data-path="${safePath}"]`
      : `.tree-file[data-path="${safePath}"]`;
  var rows = queryHtmlAll(selector);
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
        // Sync the gray "empty" class. Server emits null for
        // walker-pending dirs (don't change the class) and 0
        // for finalized-empty (gray). Without this toggle, a
        // dir initially painted gray during inventory startup
        // never cleared once its real count arrived via
        // fs.change.
        var totalFiles = entry.total_files;
        if (totalFiles != null) {
          row.classList.toggle("tree-item-empty", totalFiles === 0);
        }
      }
      // Sync gitignored across dir + file rows so a flag flip
      // (rare, but possible if .gitignore is edited) updates
      // the muted class without a full rerender.
      row.classList.toggle("tree-item-gitignored", !!entry.gitignored);
    }
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
  var panels = [document.getElementById("tab-files"), document.getElementById("tab-recent")];
  for (var p = 0; p < panels.length; p++) {
    var panel = panels[p];
    if (!panel) {
      continue;
    }
    var container = _findChildContainerFor(parentRel, panel);
    if (!container) {
      continue;
    }
    _insertRowSorted(container, entry, treeRenderOptionsForElement(panel));
  }
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

// Recent re-cluster scheduling:
// debounced so a burst of fs.change ops doesn't render-thrash.
// The Recent panel reads from ``recentBaseEntries`` (chip-fetched
// from /api/recent + live overlay from fs.change), so live
// updates inside the active window flow through without a refetch.
var _recentRecomputeHandle = null;
function _scheduleRecentRecompute() {
  if (!recentEverLoaded) {
    return; // panel never mounted; nothing to do
  }
  var panel = document.getElementById("tab-recent");
  if (!panel || panel.style.display === "none") {
    return; // hidden tab; defer
  }
  if (_recentRecomputeHandle) {
    return; // already pending
  }
  _recentRecomputeHandle = setTimeout(() => {
    _recentRecomputeHandle = null;
    renderRecentFromBase();
    if (currentPath) {
      setSelectedPath(currentPath);
    }
  }, RECENT_RECLUSTER_DEBOUNCE_MS);
}

var _esConsecutiveErrors = 0;
var _esBackoffMs = 2000;
var _esReconnectTimer = null;
var _ES_MAX_CONSECUTIVE_ERRORS = 5;
var _ES_BACKOFF_CAP_MS = 60000;

function _resetEsCircuitBreaker() {
  _esConsecutiveErrors = 0;
  _esBackoffMs = 2000;
}

function _createInventoryEventSource() {
  try {
    inventoryEventSource = new EventSource("/api/events?scope=root-depth-2");
  } catch (_e) {
    inventoryEventSource = null;
    return;
  }
  inventoryEventSource.addEventListener("fs.snapshot", (e) => {
    _resetEsCircuitBreaker();
    try {
      var data = JSON.parse(e.data);
      fileStoreApplySnapshot(data.scope, data.entries || []);
      _scheduleRecentRecompute();
    } catch (_e) {
      /* malformed frame; ignore */
    }
  });
  inventoryEventSource.addEventListener("fs.change", (e) => {
    _resetEsCircuitBreaker();
    try {
      var data = JSON.parse(e.data);
      fileStoreApplyChange(data.ops || []);
      _scheduleRecentRecompute();
    } catch (_e) {
      /* ignore */
    }
  });
  inventoryEventSource.addEventListener("fs.resync_required", (_e) => {
    _resetEsCircuitBreaker();
    // Server restart or root swap — drop everything; reconnect
    // will deliver a fresh snapshot.
    fileStore = new Map();
    notifyFileStoreSubscribers({ kind: "resync" });
    startIndexProgressPolling();
  });
  inventoryEventSource.onopen = () => {
    _resetEsCircuitBreaker();
  };
  inventoryEventSource.onerror = () => {
    _esConsecutiveErrors += 1;
    if (_esConsecutiveErrors >= _ES_MAX_CONSECUTIVE_ERRORS) {
      // Circuit breaker: too many consecutive errors without a
      // successful open or message. Close and recreate with
      // exponential backoff. A fresh connection gets a snapshot
      // via the existing fs.snapshot/resync flow.
      if (inventoryEventSource) {
        inventoryEventSource.close();
        inventoryEventSource = null;
      }
      var delay = _esBackoffMs;
      _esBackoffMs = Math.min(_esBackoffMs * 2, _ES_BACKOFF_CAP_MS);
      _esReconnectTimer = setTimeout(() => {
        _esReconnectTimer = null;
        _esConsecutiveErrors = 0;
        _createInventoryEventSource();
      }, delay);
    }
  };
}

function startInventoryEventStream() {
  if (typeof EventSource === "undefined") {
    return; // graceful degradation
  }
  if (inventoryEventSource) {
    return;
  }
  _createInventoryEventSource();
}

// ── Hash routing ──────────────────────────────────────────────

function parseHashRoute() {
  var hash = location.hash;
  if (!hash || hash === "#") {
    return "";
  }
  var frag = decodeURIComponent(hash.slice(1)).replace(/\/+$/, "");
  if (!frag) {
    return "";
  }
  // The URL hash doubles as a file deep-link (#<path>) and as in-document
  // anchors inside an embedded KPress document (#section, #fn-note). Only treat
  // a fragment as a file path when it looks like one — a directory separator or
  // a file extension. Otherwise it is an in-doc anchor the browser scrolls
  // natively, and opening a file named by the fragment would 404.
  if (frag.indexOf("/") === -1 && !/\.[A-Za-z0-9]{1,8}$/.test(frag)) {
    return "";
  }
  return frag;
}

function serverInitialPath() {
  if (typeof window === "undefined") {
    return "";
  }
  var path = window.METABROWSER_INITIAL_PATH || "";
  return typeof path === "string" ? path.replace(/\/+$/, "") : "";
}

// Top-level README (case-insensitive). Returns its path or "" if absent.
// Auto-navigates on first load when no hash is set, so a worktree with
// a root readme never opens to the empty "select a file" pane. Scoped
// to direct children of the tree root: never auto-navs to a README in
// some nested subdirectory.
function findRootReadme() {
  // Files are direct children of the Files panel; Recent is its sibling.
  var rootFiles = queryHtmlAll("#tab-files > .tree-item.tree-file");
  for (var i = 0; i < rootFiles.length; i++) {
    var path = rootFiles[i].dataset.path;
    if (!path) {
      continue;
    }
    var base = path.split("/").pop();
    if (base && /^readme\.md$/i.test(base)) {
      return path;
    }
  }
  return "";
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
    var folder = queryHtml(`.tree-folder[data-path="${current}"]`);
    if (folder) {
      var children = /** @type {HTMLElement | null} */ (folder.nextElementSibling);
      if (children) {
        if (children.querySelector(".tree-lazy-placeholder")) {
          await loadSubtree(current, children);
        }
        if (children.style.display === "none") {
          children.style.display = "block";
          folder.classList.remove("collapsed");
          folder.classList.add("expanded");
        }
      }
    }
  }
  var target = document.querySelector(`.tree-file[data-path="${path}"]`);
  if (!target) {
    return false;
  }
  setSelectedPath(path);
  target.scrollIntoView({ block: "nearest" });
  return true;
}

async function navigateToPath(path) {
  if (!path) {
    return;
  }
  if (await revealInTree(path)) {
    selectFile(path, true);
  }
}

window.addEventListener("hashchange", () => {
  var path = parseHashRoute();
  if (path && path !== currentPath) {
    navigateToPath(path);
  }
});

window.addEventListener("metabrowser:open-path", (event) => {
  if (!(event instanceof CustomEvent)) {
    return;
  }
  var path = event.detail?.path;
  if (typeof path === "string" && path) {
    selectFile(path);
  }
});

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
  initNavScrollShadow();
  // Fire the URL-pinned file fetch in parallel with the tree walk: the
  // two requests don't depend on each other, so a deep-link's preview
  // can render as soon as /api/file lands instead of waiting for the
  // full tree to come back. revealInTree below still waits on the
  // tree because it queries DOM the renderer just produced.
  var hashPath = parseHashRoute();
  var initialPath = hashPath || serverInitialPath();
  if (initialPath) {
    selectFile(initialPath, true);
  }
  startIndexProgressPolling();
  await loadTree();
  initPaneResize("tree-resize", ".tree-pane", 180, null);
  if (initialPath) {
    revealInTree(initialPath);
  } else {
    var readme = findRootReadme();
    if (readme) {
      navigateToPath(readme);
    }
  }
  // /api/events is the single source for tree decoration and
  // active-file badges; ActiveFileTracker emits fs.change ops
  // with active/labels populated.
  startInventoryEventStream();
});
