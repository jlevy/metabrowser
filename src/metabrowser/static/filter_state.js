// Shared filter state — the one vocabulary behind the navigation
// filter bar and any future filtering surface. See
// docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md.
//
// State shape (v1):
//   { recency: "all"|"live"|"1h"|"24h"|"7d"|"30d",
//     types: string[]|null,   // ft-* families; null means any
//     size: "all"|"s"|"m"|"l",
//     showIgnored: boolean }  // gitignored entries visible (dimmed)
//
// Recency is one axis, not two: "live" is the shortest server-owned
// mtime window, so it is a value here rather than a separate boolean.
//
// There is no dim/hide switch. A filter removes what does not match —
// that is what filtering is — so the only display choice left is
// whether gitignored entries are in the tree at all, and when they are
// they keep the dimmed treatment the tree has always given them.
//
// Filter selections are transient view state: every page starts from
// the defaults, and changes live only in this module. Every change
// notifies subscribers and dispatches a `metabrowser:filter-change`
// CustomEvent. The predicate helpers live here so no two surfaces can
// disagree about what matches.

(() => {
  // Development builds after v0.2.0 stored filters in the host-wide
  // preference cookie. Expire that value once so an upgrade does not
  // leave dead browser state behind.
  const LEGACY_PREF_KEY = "filters";

  /**
   * Seconds per recency value, injected from metabrowser/settings.py.
   * `all` maps to null and recencySeconds normalizes it to zero.
   * @type {Record<string, number | null>}
   */
  const RECENCY_SECONDS = /** @type {Record<string, number | null>} */ (
    /** @type {any} */ (window).METABROWSER_SETTINGS?.RECENT_WINDOW_SECONDS || {}
  );
  const RECENCY_VALUES = Object.keys(RECENCY_SECONDS);
  /**
   * Size is a cumulative floor, not a band: "bigger than this". Bands
   * force you to guess which one a file lands in, while "what is over
   * 10M in here" is the question people actually ask. Fixed
   * thresholds, so the labels never shift as you browse.
   * @type {Record<string, number>}
   */
  const SIZE_MIN_BYTES = {
    "100k": 100 * 1024,
    "1m": 1024 * 1024,
    "10m": 10 * 1024 * 1024,
    "100m": 100 * 1024 * 1024,
    "1g": 1024 * 1024 * 1024,
  };
  const SIZE_VALUES = ["all", "100k", "1m", "10m", "100m", "1g"];
  const DEFAULTS = Object.freeze({
    recency: "all",
    /** @type {string[] | null} */
    types: null,
    size: "all",
    // Gitignored entries are present but dimmed, which is what the
    // tree has always done; unchecking removes them entirely.
    showIgnored: true,
  });

  /** @typedef {{recency: string, types: string[] | null, size: string, showIgnored: boolean}} FilterSnapshot */

  /** @type {FilterSnapshot | null} */
  let state = null;
  /** @type {Array<(s: FilterSnapshot) => void>} */
  let listeners = [];

  function prefs() {
    const mb = /** @type {Record<string, any> | undefined} */ (
      /** @type {Record<string, any>} */ (window).metabrowser
    );
    return mb?.prefs ? mb.prefs : null;
  }

  /**
   * Coerce arbitrary caller-supplied input into a valid snapshot.
   * Unknown values fall back to the default rather than throwing.
   * @param {unknown} raw
   * @returns {FilterSnapshot}
   */
  function sanitize(raw) {
    /** @type {FilterSnapshot} */
    const out = {
      recency: DEFAULTS.recency,
      types: DEFAULTS.types,
      size: DEFAULTS.size,
      showIgnored: DEFAULTS.showIgnored,
    };
    if (raw && typeof raw === "object") {
      const r = /** @type {Record<string, unknown>} */ (raw);
      if (typeof r.recency === "string" && RECENCY_VALUES.includes(r.recency)) {
        out.recency = r.recency;
      }
      if (Array.isArray(r.types)) {
        const cleaned = r.types.filter((t) => typeof t === "string" && t.length > 0);
        // An empty selection is "no constraint", the same as null, so
        // it normalizes to null and activeCount stays honest.
        out.types = cleaned.length > 0 ? cleaned : null;
      }
      if (typeof r.size === "string" && SIZE_VALUES.includes(r.size)) {
        out.size = r.size;
      }
      if (typeof r.showIgnored === "boolean") {
        out.showIgnored = r.showIgnored;
      }
    }
    return out;
  }

  function load() {
    const p = prefs();
    if (p && typeof p.remove === "function") {
      p.remove(LEGACY_PREF_KEY);
    }
    state = sanitize(null);
  }

  /** @returns {FilterSnapshot} */
  function get() {
    if (!state) {
      load();
    }
    const s = /** @type {FilterSnapshot} */ (state);
    return {
      recency: s.recency,
      types: s.types ? s.types.slice() : null,
      size: s.size,
      showIgnored: s.showIgnored,
    };
  }

  /** @param {Record<string, unknown>} patch */
  function set(patch) {
    const next = sanitize(Object.assign(get(), patch));
    state = next;
    const snapshot = get();
    for (const listener of listeners.slice()) {
      try {
        listener(snapshot);
      } catch (err) {
        console.warn("filter listener failed:", err);
      }
    }
    try {
      window.dispatchEvent(
        new CustomEvent("metabrowser:filter-change", { detail: { state: snapshot } }),
      );
    } catch (_err) {
      // CustomEvent unavailable in a partial harness; the subscribers
      // above were still notified, which is the contract that matters.
    }
  }

  /** Reset every dimension, including the ones behind the drawer. */
  function clear() {
    set(Object.assign({}, DEFAULTS));
  }

  /** @param {(s: FilterSnapshot) => void} listener @returns {() => void} */
  function subscribe(listener) {
    listeners.push(listener);
    return () => {
      listeners = listeners.filter((l) => l !== listener);
    };
  }

  /**
   * Number of dimensions away from their default — drives the badge on
   * the drawer toggle so filters remain visible when it is collapsed.
   */
  function activeCount() {
    const s = get();
    let n = 0;
    if (s.recency !== DEFAULTS.recency) {
      n += 1;
    }
    if (s.types) {
      n += 1;
    }
    if (s.size !== DEFAULTS.size) {
      n += 1;
    }
    if (s.showIgnored !== DEFAULTS.showIgnored) {
      n += 1;
    }
    return n;
  }

  /** @param {string} recency @returns {number} 0 when not a bounded window */
  function recencySeconds(recency) {
    return RECENCY_SECONDS[recency] || 0;
  }

  /**
   * The extension a filter matches on, lowercased and including the
   * dot (".md"). Mirrors app.js getExt; a file with no dot has no
   * extension and reports "".
   * @param {string} pathLike
   */
  function extensionOf(pathLike) {
    if (typeof pathLike !== "string" || pathLike.length === 0) {
      return "";
    }
    const name = pathLike.slice(pathLike.lastIndexOf("/") + 1);
    const dot = name.lastIndexOf(".");
    // A leading dot is a dotfile (".gitignore"), not an extension.
    if (dot <= 0) {
      return "";
    }
    return name.slice(dot).toLowerCase();
  }

  /**
   * Does a row carry one of the selected extensions? Extensions are
   * the literal ".md" / ".py" the tree shows, not an abstract family,
   * so what the menu offers is exactly what the folder contains.
   *
   * `logicalExt` is the compound tail the index derives (".min.js",
   * ".runbook.md") and is what the menu's tally counts, so it must win
   * when present: reducing to the last dotted suffix would turn every
   * compound row into a plain ".js" and a compound pick would match
   * nothing it was counted for.
   *
   * @param {string} pathLike
   * @param {string[] | null} types
   * @param {string} [logicalExt]
   */
  function typeMatches(pathLike, types, logicalExt) {
    if (!types || types.length === 0) {
      return true;
    }
    const ext = (logicalExt || extensionOf(pathLike)).toLowerCase();
    const name = String(pathLike || "")
      .slice(String(pathLike || "").lastIndexOf("/") + 1)
      .toLowerCase();
    for (const raw of types) {
      const token = String(raw).toLowerCase();
      // One convention, no ambiguity: a leading dot means extension,
      // anything else is a whole filename. That is what lets a preset
      // name README and LICENSE alongside .md and .txt — files that
      // carry no extension at all and would otherwise be unreachable.
      if (token.charAt(0) === ".") {
        const semantic = window.MetabrowserFileTypeTaxonomy?.matchExtension(token);
        if (ext && (ext === token || (semantic && ext.endsWith(token)))) {
          return true;
        }
      } else if (name === token) {
        return true;
      }
    }
    // No token matched. For an extensionless file this is still a real
    // non-match rather than missing data: the name was known, it just
    // was not asked for.
    return false;
  }

  /** @param {number | null | undefined} bytes @param {string} bucket */
  function sizeMatches(bytes, bucket) {
    const floor = SIZE_MIN_BYTES[bucket];
    if (!floor) {
      return true; // "all", or a value from a newer version
    }
    if (typeof bytes !== "number" || !Number.isFinite(bytes) || bytes < 0) {
      return true; // pending size is unknown, not excluded
    }
    return bytes >= floor;
  }

  /**
   * The one row predicate every surface shares. `row` carries whatever
   * subset the caller knows: {mtime (seconds), size (bytes), path,
   * isDir, isSymlink}. Missing fields never rule a row out — pending data
   * must not flicker as filtered. Directories are judged only on
   * recency, because a folder's type and size are aggregates that mean
   * something different from a file's. Symlinks stay visible only when
   * no file-specific filter is active; they are filesystem references,
   * not members of a file age, type, or size bucket.
   * @param {{mtime?: number | null, size?: number | null, path?: string, isDir?: boolean, isSymlink?: boolean, ext?: string}} row
   * @param {FilterSnapshot} s
   * @param {number} nowSec
   */
  function rowMatches(row, s, nowSec) {
    // Note: gitignored is handled by the caller, which knows the row's
    // class; showIgnored is a visibility choice, not a predicate.
    if (row.isSymlink) {
      return s.recency === "all" && !s.types && s.size === "all";
    }
    if (s.recency !== "all") {
      const maxAge = recencySeconds(s.recency);
      if (typeof row.mtime === "number" && row.mtime > 0 && nowSec - row.mtime > maxAge) {
        return false;
      }
    }
    if (row.isDir) {
      return true;
    }
    if (s.types && typeof row.path === "string" && !typeMatches(row.path, s.types, row.ext)) {
      return false;
    }
    if (!sizeMatches(row.size, s.size)) {
      return false;
    }
    return true;
  }

  const mb = /** @type {Record<string, any>} */ (window).metabrowser;
  if (!mb) {
    console.error("metabrowser filter state: window.metabrowser missing — SDK not loaded");
    return;
  }
  mb.filterState = {
    DEFAULTS,
    RECENCY_VALUES: RECENCY_VALUES.slice(),
    SIZE_VALUES: SIZE_VALUES.slice(),
    SIZE_MIN_BYTES,
    get,
    set,
    clear,
    subscribe,
    activeCount,
    recencySeconds,
    typeMatches,
    sizeMatches,
    rowMatches,
  };
})();
