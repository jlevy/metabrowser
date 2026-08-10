// Shared filter state — the one vocabulary behind the navigation
// filter bar and any future filtering surface. See
// docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md.
//
// State shape (v1):
//   { recency: "all"|"live"|"1h"|"24h"|"7d"|"30d",
//     types: string[]|null,   // ft-* families; null means any
//     size: "all"|"s"|"m"|"l",
//     ignored: "shown"|"dimmed"|"hidden",
//     mode: "dim"|"hide" }
//
// Recency is one axis, not two: "live" (the active tracker's flag) is
// the narrowest point on it, so it is a value here rather than a
// separate boolean. Persistence rides mb.prefs (host-only cookies,
// shared across per-root ports); every change notifies subscribers and
// dispatches a `metabrowser:filter-change` CustomEvent. The predicate
// helpers live here so no two surfaces can disagree about what
// matches.

(() => {
  const PREF_KEY = "filters";

  const RECENCY_VALUES = ["all", "live", "1h", "24h", "7d", "30d"];
  /**
   * Seconds per windowed recency value; "all" and "live" are not
   * windows and are absent on purpose.
   * @type {Record<string, number>}
   */
  const RECENCY_SECONDS = { "1h": 3600, "24h": 86400, "7d": 604800, "30d": 2592000 };
  const SIZE_VALUES = ["all", "s", "m", "l"];
  /** Fixed byte thresholds — predictable labels that do not shift as you browse. */
  const SIZE_SMALL_MAX = 10 * 1024;
  const SIZE_MEDIUM_MAX = 1024 * 1024;
  const IGNORED_VALUES = ["shown", "dimmed", "hidden"];
  const MODE_VALUES = ["dim", "hide"];

  const DEFAULTS = Object.freeze({
    recency: "all",
    /** @type {string[] | null} */
    types: null,
    size: "all",
    ignored: "dimmed",
    // Hide, not dim: setting a filter should remove what does not
    // match, because that is what "filter" means to the person
    // clicking it (see Resolved Decision 5 in the plan).
    mode: "hide",
  });

  /** @typedef {{recency: string, types: string[] | null, size: string, ignored: string, mode: string}} FilterSnapshot */

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
   * Coerce arbitrary persisted or caller-supplied input into a valid
   * snapshot. Unknown values fall back to the default rather than
   * throwing: a stale cookie from a future version must not break the
   * filter bar.
   * @param {unknown} raw
   * @returns {FilterSnapshot}
   */
  function sanitize(raw) {
    /** @type {FilterSnapshot} */
    const out = {
      recency: DEFAULTS.recency,
      types: DEFAULTS.types,
      size: DEFAULTS.size,
      ignored: DEFAULTS.ignored,
      mode: DEFAULTS.mode,
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
      if (typeof r.ignored === "string" && IGNORED_VALUES.includes(r.ignored)) {
        out.ignored = r.ignored;
      }
      if (typeof r.mode === "string" && MODE_VALUES.includes(r.mode)) {
        out.mode = r.mode;
      }
    }
    return out;
  }

  function load() {
    const p = prefs();
    state = sanitize(p ? p.get(PREF_KEY, null) : null);
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
      ignored: s.ignored,
      mode: s.mode,
    };
  }

  /** @param {Record<string, unknown>} patch */
  function set(patch) {
    const next = sanitize(Object.assign(get(), patch));
    state = next;
    const p = prefs();
    if (p) {
      p.set(PREF_KEY, next);
    }
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
   * the drawer toggle so persisted filters are never invisible state.
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
    if (s.ignored !== DEFAULTS.ignored) {
      n += 1;
    }
    if (s.mode !== DEFAULTS.mode) {
      n += 1;
    }
    return n;
  }

  /** @param {string} recency @returns {number} 0 when not a time window */
  function recencySeconds(recency) {
    return RECENCY_SECONDS[recency] || 0;
  }

  /**
   * Does a path match the selected type families? A family matches its
   * subtypes (`ft-md` matches `ft-md-runbook`). Uses the shell's
   * classifier so the filter can never disagree with the colors; with
   * no classifier available nothing is ruled out.
   * @param {string} pathLike
   * @param {string[] | null} types
   */
  function typeMatches(pathLike, types) {
    if (!types || types.length === 0) {
      return true;
    }
    const ft = /** @type {Record<string, any>} */ (window).MetabrowserFileTypes;
    if (!ft || typeof ft.classFor !== "function") {
      return true;
    }
    const cls = String(ft.classFor(pathLike) || "");
    if (!cls) {
      // Unclassified is missing data, not a non-match — never rule a
      // row out on information we do not have.
      return true;
    }
    return types.some((family) => cls === family || cls.startsWith(`${family}-`));
  }

  /** @param {number | null | undefined} bytes @param {string} bucket */
  function sizeMatches(bytes, bucket) {
    if (bucket === "all") {
      return true;
    }
    if (typeof bytes !== "number" || !Number.isFinite(bytes) || bytes < 0) {
      return true; // pending size is unknown, not excluded
    }
    if (bucket === "s") {
      return bytes < SIZE_SMALL_MAX;
    }
    if (bucket === "m") {
      return bytes >= SIZE_SMALL_MAX && bytes < SIZE_MEDIUM_MAX;
    }
    return bytes >= SIZE_MEDIUM_MAX;
  }

  /**
   * The one row predicate every surface shares. `row` carries whatever
   * subset the caller knows: {mtime (seconds), size (bytes), path,
   * live, isDir}. Missing fields never rule a row out — pending data
   * must not flicker as filtered. Directories are judged only on
   * recency, because a folder's type and size are aggregates that mean
   * something different from a file's.
   * @param {{mtime?: number | null, size?: number | null, path?: string, live?: boolean, isDir?: boolean}} row
   * @param {FilterSnapshot} s
   * @param {number} nowSec
   */
  function rowMatches(row, s, nowSec) {
    if (s.recency === "live") {
      if (!row.isDir && row.live !== true) {
        return false;
      }
    } else if (s.recency !== "all") {
      const maxAge = recencySeconds(s.recency);
      if (typeof row.mtime === "number" && row.mtime > 0 && nowSec - row.mtime > maxAge) {
        return false;
      }
    }
    if (row.isDir) {
      return true;
    }
    if (s.types && typeof row.path === "string" && !typeMatches(row.path, s.types)) {
      return false;
    }
    if (!sizeMatches(row.size, s.size)) {
      return false;
    }
    return true;
  }

  /** @type {Record<string, any>} */ (window).MetabrowserFilterState = {
    DEFAULTS,
    RECENCY_VALUES: RECENCY_VALUES.slice(),
    SIZE_VALUES: SIZE_VALUES.slice(),
    SIZE_SMALL_MAX,
    SIZE_MEDIUM_MAX,
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
