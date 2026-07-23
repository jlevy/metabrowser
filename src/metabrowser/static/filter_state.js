// Shared filter state — the one vocabulary behind the nav filter bar
// and folder views (see docs/project/specs/active/
// plan-2026-07-20-unified-filtering.md, Resolved Decisions).
//
// State shape (v1, no mode field — age/type apply as dim everywhere):
//   { current: boolean, ageWindow: "1h"|"24h"|"7d"|"30d"|null,
//     types: string[]|null, ignored: "shown"|"dimmed"|"hidden" }
//
// Persistence rides mb.prefs (host-only cookies, shared across
// per-root ports); every change dispatches a
// `metabrowser:filter-change` CustomEvent and notifies subscribers.
// The predicate helpers live here so the tree and the treemap can
// never disagree about what matches.

(() => {
  const PREF_KEY = "filters";
  const AGE_WINDOWS = ["1h", "24h", "7d", "30d"];
  /** @type {Record<string, number>} */
  const WINDOW_SECONDS = { "1h": 3600, "24h": 86400, "7d": 604800, "30d": 2592000 };
  const IGNORED_VALUES = ["shown", "dimmed", "hidden"];
  const RECENT_DEFAULT_WINDOW = "24h";
  const DEFAULTS = Object.freeze({
    current: false,
    ageWindow: /** @type {string | null} */ (null),
    types: /** @type {string[] | null} */ (null),
    ignored: "dimmed",
  });

  /** @type {ReturnType<typeof sanitize> | null} */
  let state = null;
  /** @type {Array<(s: Record<string, unknown>) => void>} */
  let listeners = [];

  function prefs() {
    const mb = /** @type {Record<string, any> | undefined} */ (
      /** @type {Record<string, any>} */ (window).metabrowser
    );
    return mb && mb.prefs ? mb.prefs : null;
  }

  /** @param {unknown} raw */
  function sanitize(raw) {
    /** @type {{current: boolean, ageWindow: string | null, types: string[] | null, ignored: string}} */
    const out = {
      current: DEFAULTS.current,
      ageWindow: DEFAULTS.ageWindow,
      types: DEFAULTS.types,
      ignored: DEFAULTS.ignored,
    };
    if (raw && typeof raw === "object") {
      const r = /** @type {Record<string, unknown>} */ (raw);
      if (typeof r.current === "boolean") {
        out.current = r.current;
      }
      if (typeof r.ageWindow === "string" && AGE_WINDOWS.includes(r.ageWindow)) {
        out.ageWindow = r.ageWindow;
      }
      if (Array.isArray(r.types)) {
        const cleaned = r.types.filter((t) => typeof t === "string" && t.length > 0);
        out.types = cleaned.length > 0 ? cleaned : null;
      }
      if (typeof r.ignored === "string" && IGNORED_VALUES.includes(r.ignored)) {
        out.ignored = r.ignored;
      }
    }
    return out;
  }

  function load() {
    const p = prefs();
    state = sanitize(p ? p.get(PREF_KEY, null) : null);
  }

  function get() {
    if (!state) {
      load();
    }
    const s = /** @type {NonNullable<typeof state>} */ (state);
    return {
      current: s.current,
      ageWindow: s.ageWindow,
      types: s.types ? s.types.slice() : null,
      ignored: s.ignored,
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
      // CustomEvent unavailable in a partial harness; listeners above
      // were still notified.
    }
  }

  function clear() {
    set(Object.assign({}, DEFAULTS));
  }

  /** @param {(s: Record<string, unknown>) => void} listener */
  function subscribe(listener) {
    listeners.push(listener);
    return () => {
      listeners = listeners.filter((l) => l !== listener);
    };
  }

  /** Number of non-default dimensions — drives the nav badge. */
  function activeCount() {
    const s = get();
    let n = 0;
    if (s.current) {
      n += 1;
    }
    if (s.ageWindow) {
      n += 1;
    }
    if (s.types) {
      n += 1;
    }
    if (s.ignored !== DEFAULTS.ignored) {
      n += 1;
    }
    return n;
  }

  /** @param {string} win @returns {number} 0 for unknown windows */
  function windowSeconds(win) {
    return WINDOW_SECONDS[win] || 0;
  }

  /**
   * Does a path match the selected type families? A family matches its
   * subtypes (`ft-md` matches `ft-md-runbook`). Uses the shell's
   * classifier through the SDK so the filter can never disagree with
   * the colors; with no classifier available nothing is ruled out.
   * @param {string} pathLike
   * @param {string[] | null} types
   */
  function typeMatches(pathLike, types) {
    if (!types || types.length === 0) {
      return true;
    }
    const mb = /** @type {Record<string, any>} */ (window).metabrowser;
    if (!mb || typeof mb.fileTypeClass !== "function") {
      return true;
    }
    const cls = String(mb.fileTypeClass(pathLike) || "");
    if (!cls) {
      // Unclassified is missing data, not a non-match — never rule
      // a row out on information we do not have.
      return true;
    }
    return types.some((family) => cls === family || cls.startsWith(`${family}-`));
  }

  /**
   * The one row predicate both surfaces share. `row` carries whatever
   * subset the surface knows: {mtime (seconds), path, active,
   * isDir}. Missing fields never rule a row out (pending data must
   * not flicker as filtered). The gitignored dimension is handled by
   * the surfaces themselves (three-state, not boolean).
   * @param {{mtime?: number | null, path?: string, active?: boolean, isDir?: boolean}} row
   * @param {ReturnType<typeof get>} s
   * @param {number} nowSec
   */
  function rowMatches(row, s, nowSec) {
    if (s.current && !row.isDir && row.active !== true) {
      return false;
    }
    if (s.ageWindow) {
      const maxAge = windowSeconds(s.ageWindow);
      if (typeof row.mtime === "number" && row.mtime > 0 && nowSec - row.mtime > maxAge) {
        return false;
      }
    }
    if (s.types && !row.isDir && typeof row.path === "string") {
      if (!typeMatches(row.path, s.types)) {
        return false;
      }
    }
    return true;
  }

  /** @type {Record<string, any>} */ (window).MetabrowserFilterState = {
    AGE_WINDOWS: AGE_WINDOWS.slice(),
    RECENT_DEFAULT_WINDOW,
    get,
    set,
    clear,
    subscribe,
    activeCount,
    windowSeconds,
    typeMatches,
    rowMatches,
  };
})();
