// The event log views' state and wording, with no DOM: what a filter asks of the server,
// how a timeline's pages nest and open, and how a time reads.
//
// The server (event_log_views.py) owns every figure: which spans nest under which, how long
// each took, how they are counted. This module keeps only what the page decides: which
// filters are chosen, which rows are open, and the pages read so far, so the whole
// interaction runs in a browserless session (tests/dom/event-log-view-session.js).

/**
 * @typedef {Object} EventRow One item of the log as the server answers it.
 * @property {"span" | "mark" | "report"} type
 * @property {string} key `<pid>:<span>` for a span, else `<pid>@<record>`.
 * @property {string} kind
 * @property {string} name
 * @property {number} start_ms Milliseconds after the log's first record.
 * @property {number | null} dur_ms How long it took, once it ended.
 * @property {number | null} elapsed_ms `dur_ms`, or an unfinished span's age at the log's end.
 * @property {string | null} outcome
 * @property {string} state `ended`, `unfinished`, `report`, or `mark`.
 * @property {string | null} client
 * @property {number} pid
 * @property {number | null} span
 * @property {string | null} parent The key of the span above, when the file holds it.
 * @property {Record<string, unknown>} attrs
 * @property {number} [children] Spans directly below that the filter shows.
 * @property {number} [below] Spans below, at any depth.
 * @property {boolean} [matched] Whether the row matches the filter or is shown for what is below.
 * @property {boolean} [orphan] It names a parent the file does not hold.
 * @property {number} [opens] The open records a span wrote while it ran late.
 * @property {string} [event] A report's record: `end`, `open`, or `mark`.
 * @property {Array<{key: string, kind: string, name: string}>} [path] The spans above it.
 */

/**
 * @typedef {Object} Filters What the three analysis views ask the server to count.
 * @property {string[]} kind
 * @property {string[]} outcome
 * @property {number | null} minMs
 */

/** @typedef {"kind" | "outcome"} ChoiceField */

/** @returns {Filters} */
export function emptyFilters() {
  return { kind: [], outcome: [], minMs: null };
}

/** @param {Filters} filters */
export function filtersActive(filters) {
  return filters.kind.length > 0 || filters.outcome.length > 0 || filters.minMs !== null;
}

/**
 * *filters* with *value* chosen or unchosen in *field*, as a chip's click means.
 *
 * @param {Filters} filters
 * @param {ChoiceField} field
 * @param {string} value
 * @returns {Filters}
 */
export function toggleChoice(filters, field, value) {
  const chosen = filters[field];
  const next = chosen.includes(value) ? chosen.filter((v) => v !== value) : [...chosen, value];
  return { ...filters, [field]: next };
}

/**
 * @param {Filters} filters
 * @param {number | null} minMs
 * @returns {Filters}
 */
export function chooseMinimum(filters, minMs) {
  return { ...filters, minMs };
}

/**
 * The query string's parameters for *filters*: the names the routes take, and only those
 * the person chose.
 *
 * @param {Filters} filters
 * @returns {Record<string, string>}
 */
export function filterParams(filters) {
  /** @type {Record<string, string>} */
  const params = {};
  if (filters.kind.length > 0) {
    params.kind = filters.kind.join(",");
  }
  if (filters.outcome.length > 0) {
    params.outcome = filters.outcome.join(",");
  }
  if (filters.minMs !== null) {
    params.min_ms = String(filters.minMs);
  }
  return params;
}

/**
 * How long, in the unit a person reads: sub-millisecond to the tenth, a millisecond count
 * to the whole millisecond below a second, seconds to the hundredth below ten, to the tenth
 * below a minute, then minutes and seconds.
 *
 * @param {number | null | undefined} ms
 */
export function formatDuration(ms) {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) {
    return "";
  }
  if (ms < 1) {
    return `${(Math.round(ms * 10) / 10).toFixed(1)} ms`;
  }
  if (ms < 10) {
    return `${ms.toFixed(1)} ms`;
  }
  if (ms < 1000) {
    return `${Math.round(ms)} ms`;
  }
  if (ms < 10_000) {
    return `${(ms / 1000).toFixed(2)} s`;
  }
  if (ms < 60_000) {
    return `${(ms / 1000).toFixed(1)} s`;
  }
  const seconds = Math.round(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes} min ${seconds % 60} s`;
  }
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}

/**
 * Where a row began, as an offset from the log's start.
 *
 * @param {number} ms
 */
export function formatOffset(ms) {
  return `+${formatDuration(Math.max(0, ms))}`;
}

/**
 * The labels of the distribution's buckets, from the edges the server cut it at.
 *
 * @param {ReadonlyArray<number>} edges
 */
export function bucketLabels(edges) {
  const labels = edges.map((edge, index) =>
    index === 0
      ? `< ${formatDuration(edge)}`
      : `${formatDuration(edges[index - 1])} – ${formatDuration(edge)}`,
  );
  const last = edges.at(-1);
  return [...labels, last === undefined ? "all" : `≥ ${formatDuration(last)}`];
}

/**
 * Where a row's bar sits on the log's time axis: its start and its length as fractions of
 * the log's extent, the length never under *floor* so that a quick span is still drawn.
 *
 * @param {{start_ms: number, elapsed_ms: number | null}} row
 * @param {number} extentMs
 * @param {number} floor
 */
export function axisBar(row, extentMs, floor) {
  const extent = extentMs > 0 ? extentMs : 1;
  // Four decimals of a fraction are a hundredth of a percent, finer than a pixel of any pane.
  const fine = (/** @type {number} */ fraction) => Math.round(fraction * 10_000) / 10_000;
  const left = Math.min(1, Math.max(0, row.start_ms / extent));
  const width = Math.min(1 - left, Math.max(floor, (row.elapsed_ms ?? 0) / extent));
  return { left: fine(left), width: fine(width) };
}

/**
 * A row's bar as a fraction of the longest in view.
 *
 * @param {number | null} elapsedMs
 * @param {number} longestMs
 */
export function lengthShare(elapsedMs, longestMs) {
  return longestMs > 0 && elapsedMs !== null ? Math.min(1, Math.max(0, elapsedMs / longestMs)) : 0;
}

// ── The timeline's pages ────────────────────────────────────────────────────────────

/**
 * @typedef {Object} Level The children of one span, or the roots, as read so far.
 * @property {EventRow[]} rows
 * @property {number} total How many the server holds at this level, under the filter.
 * @property {number | null} limit The page size the server answered with, which later pages keep.
 * @property {boolean} hasMore
 * @property {boolean} loading
 * @property {string | null} error
 */

/**
 * @typedef {Object} TimelineState
 * @property {Map<string, Level>} levels Keyed by the span above, `""` for the roots.
 * @property {Set<string>} open The keys of the rows that are open.
 */

/** @returns {TimelineState} */
export function createTimeline() {
  return { levels: new Map(), open: new Set() };
}

/** @param {string | null} parent */
export const levelKey = (parent) => parent ?? "";

/**
 * The parameters of the request that reads the next page of a level: the rows already
 * held are the offset, so a page read twice is not read twice.
 *
 * @param {TimelineState} state
 * @param {string | null} parent
 * @param {Filters} filters
 * @returns {Record<string, string>}
 */
export function pageParams(state, parent, filters) {
  const level = state.levels.get(levelKey(parent));
  const held = level?.rows.length ?? 0;
  return {
    ...filterParams(filters),
    ...(parent === null ? {} : { parent }),
    ...(held > 0 ? { offset: String(held) } : {}),
    // A later page is as long as the first the server sent, so the pages tile.
    ...(held > 0 && level?.limit != null ? { limit: String(level.limit) } : {}),
  };
}

/**
 * Whether the level still has pages to read and is not reading one.
 *
 * @param {TimelineState} state
 * @param {string | null} parent
 */
export function wantsPage(state, parent) {
  const level = state.levels.get(levelKey(parent));
  return level === undefined || (level.hasMore && !level.loading && level.error === null);
}

/**
 * @param {TimelineState} state
 * @param {string | null} parent
 */
export function beginPage(state, parent) {
  const key = levelKey(parent);
  const level = state.levels.get(key) ?? {
    rows: [],
    total: 0,
    limit: null,
    hasMore: false,
    loading: false,
    error: null,
  };
  level.loading = true;
  level.error = null;
  state.levels.set(key, level);
}

/**
 * Take a page the server answered: its rows follow those held.
 *
 * @param {TimelineState} state
 * @param {string | null} parent
 * @param {{rows: EventRow[], total: number, offset: number, limit: number, has_more: boolean}} answer
 */
export function takePage(state, parent, answer) {
  const key = levelKey(parent);
  const level = state.levels.get(key);
  if (level === undefined) {
    return;
  }
  // The server's offset is what this page follows; rows already held past it are the
  // answer to an earlier read of the same page.
  level.rows = [...level.rows.slice(0, answer.offset), ...answer.rows];
  level.total = answer.total;
  level.limit = level.limit ?? answer.limit;
  level.hasMore = answer.has_more;
  level.loading = false;
}

/**
 * @param {TimelineState} state
 * @param {string | null} parent
 * @param {string} message
 */
export function failPage(state, parent, message) {
  const level = state.levels.get(levelKey(parent));
  if (level !== undefined) {
    level.loading = false;
    level.error = message;
  }
}

/**
 * Open a row if it is closed, close it if open.
 *
 * @param {TimelineState} state
 * @param {string} key
 * @returns {boolean} Whether the row is now open.
 */
export function toggleRow(state, key) {
  if (state.open.delete(key)) {
    return false;
  }
  state.open.add(key);
  return true;
}

/**
 * @typedef {{kind: "row", depth: number, row: EventRow, open: boolean} | {kind: "more", depth: number, parent: string | null, remaining: number, loading: boolean} | {kind: "error", depth: number, parent: string | null, message: string}} TimelineLine
 */

/** The deepest nesting drawn: a file that nests spans deeper is cut here. */
export const MAX_DEPTH = 32;

/**
 * What the timeline shows now, top to bottom: the roots, and under each open row the
 * children read so far, each level ending in the offer of its next page.
 *
 * @param {TimelineState} state
 * @returns {TimelineLine[]}
 */
export function flatten(state) {
  /** @type {TimelineLine[]} */
  const lines = [];
  /**
   * @param {string | null} parent
   * @param {number} depth
   */
  const walk = (parent, depth) => {
    const level = state.levels.get(levelKey(parent));
    if (level === undefined || depth > MAX_DEPTH) {
      return;
    }
    for (const row of level.rows) {
      const open = state.open.has(row.key);
      lines.push({ kind: "row", depth, row, open });
      if (open) {
        walk(row.key, depth + 1);
      }
    }
    if (level.error !== null) {
      lines.push({ kind: "error", depth, parent, message: level.error });
    } else if (level.hasMore || level.loading) {
      lines.push({
        kind: "more",
        depth,
        parent,
        remaining: Math.max(0, level.total - level.rows.length),
        loading: level.loading,
      });
    }
  };
  walk(null, 0);
  return lines;
}

/**
 * The paint of an outcome: the word a row's mark is named by.
 *
 * @param {EventRow} row
 * @returns {"ok" | "failed" | "quiet" | "unfinished" | "none"}
 */
export function outcomeTone(row) {
  if (row.state === "unfinished") {
    return "unfinished";
  }
  switch (row.outcome) {
    case "ok":
      return "ok";
    case "failed":
    case "timeout":
    case "never_completed":
      return "failed";
    case "cancelled":
    case "abandoned":
      return "quiet";
    default:
      return "none";
  }
}

/**
 * The words that say how a row ended, in a row's own terms.
 *
 * @param {EventRow} row
 */
export function outcomeLabel(row) {
  if (row.state === "unfinished") {
    return "unfinished";
  }
  if (row.type === "report" && row.event === "open") {
    return "still waiting";
  }
  return row.outcome === null ? "" : row.outcome.replace(/_/g, " ");
}
