// The session list's state machine: filters, sort, and paging, and the request each state
// makes of the `sessions` route.
//
// Everything the list lets a person change is here, apart from the DOM, so a browserless
// session runs the production module (tests/dom/agents-views-session.js) and the same
// requests are reached from a command line through `metab --api`
// (tests/golden/cli-api-agents-views.tryscript.md). The data semantics, the rows, their
// order, and the counts, belong to the route; this module only says what to ask for.

/** The most rows one page asks for; the route's own bound is `routes.PAGE_MAX`. */
export const PAGE_SIZE = 50;

/** The origins, in the route's order. `review` is what Codex's automatic reviews are. */
export const ORIGINS = Object.freeze(["human", "scheduled", "subagent", "review", "automation"]);

/** The statuses a session can have, in the route's order. */
export const STATUSES = Object.freeze(["running", "finished", "failed", "unknown"]);

/** Automatic reviews are most Codex threads, so the list starts without them. */
export const DEFAULT_HIDDEN_ORIGINS = Object.freeze(["review"]);

/** The sorts the route accepts, as the columns that offer them. */
export const SORTS = Object.freeze([
  "agent",
  "title",
  "origin",
  "project",
  "model",
  "activity",
  "start",
  "duration",
  "turns",
  "size",
  "status",
]);

/** What a sort ascends by when first chosen: the route's own default for the column. */
const ASCENDING_FIRST = new Set(["title", "agent", "origin", "project", "status", "model"]);

/** The date windows a person can choose, as seconds back from now; `null` is all time. */
export const WINDOWS = Object.freeze({
  all: null,
  day: 86_400,
  week: 7 * 86_400,
  month: 30 * 86_400,
});

/**
 * @typedef {object} ListState
 * @property {string | null} agent
 * @property {ReadonlyArray<string>} origins The origins shown; empty means every origin.
 * @property {ReadonlyArray<string>} statuses
 * @property {string | null} project
 * @property {string | null} model
 * @property {keyof typeof WINDOWS} window
 * @property {string} sort
 * @property {"asc" | "desc"} order
 * @property {number} offset
 */

/** @returns {ListState} */
export function initialState() {
  return {
    agent: null,
    origins: ORIGINS.filter((origin) => !DEFAULT_HIDDEN_ORIGINS.includes(origin)),
    statuses: [],
    project: null,
    model: null,
    window: "all",
    sort: "activity",
    order: "desc",
    offset: 0,
  };
}

/**
 * A filter changed: the page returns to the first, since the old offset names rows that
 * the new filter may not have.
 *
 * @param {ListState} state
 * @param {Partial<Pick<ListState, "agent" | "origins" | "statuses" | "project" | "model" | "window">>} change
 * @returns {ListState}
 */
export function withFilter(state, change) {
  return { ...state, ...change, offset: 0 };
}

/**
 * Toggle one origin in a set the person picks from, as a chip does. Choosing every origin
 * is the same as choosing none, so the state keeps the explicit list.
 *
 * @param {ListState} state
 * @param {string} origin
 * @returns {ListState}
 */
export function toggleOrigin(state, origin) {
  const on = state.origins.includes(origin);
  const origins = on
    ? state.origins.filter((item) => item !== origin)
    : ORIGINS.filter((item) => item === origin || state.origins.includes(item));
  return withFilter(state, { origins });
}

/**
 * Toggle one status, as a chip does; the page returns to the first.
 *
 * @param {ListState} state
 * @param {string} status
 * @returns {ListState}
 */
export function toggleStatus(state, status) {
  const on = state.statuses.includes(status);
  const statuses = on
    ? state.statuses.filter((item) => item !== status)
    : STATUSES.filter((item) => item === status || state.statuses.includes(item));
  return withFilter(state, { statuses });
}

/**
 * A column's header was chosen: a new column sorts as the route defaults it, and the same
 * column reverses. The page returns to the first.
 *
 * @param {ListState} state
 * @param {string} sort
 * @returns {ListState}
 */
export function withSort(state, sort) {
  if (!SORTS.includes(sort)) {
    return state;
  }
  if (state.sort === sort) {
    return { ...state, order: state.order === "asc" ? "desc" : "asc", offset: 0 };
  }
  return { ...state, sort, order: ASCENDING_FIRST.has(sort) ? "asc" : "desc", offset: 0 };
}

/**
 * The page a response names, kept inside what the response says exists.
 *
 * @param {ListState} state
 * @param {"first" | "previous" | "next"} direction
 * @param {{total: number}} [answer] The last response, for its row count.
 * @returns {ListState}
 */
export function withPage(state, direction, answer) {
  if (direction === "first") {
    return { ...state, offset: 0 };
  }
  if (direction === "previous") {
    return { ...state, offset: Math.max(0, state.offset - PAGE_SIZE) };
  }
  const total = answer?.total ?? 0;
  return state.offset + PAGE_SIZE < total ? { ...state, offset: state.offset + PAGE_SIZE } : state;
}

/**
 * The `sessions` request this state makes. `now` is the page's clock, in Unix seconds,
 * for the window; a state with no window ignores it.
 *
 * @param {ListState} state
 * @param {string} folder
 * @param {number} now
 * @returns {Record<string, string | number>}
 */
export function queryOf(state, folder, now) {
  /** @type {Record<string, string | number>} */
  const query = { folder, sort: state.sort, order: state.order, limit: PAGE_SIZE };
  if (state.offset > 0) {
    query.offset = state.offset;
  }
  if (state.agent) {
    query.agent = state.agent;
  }
  if (state.origins.length > 0 && state.origins.length < ORIGINS.length) {
    query.origin = state.origins.join(",");
  }
  if (state.statuses.length > 0) {
    query.status = state.statuses.join(",");
  }
  if (state.project) {
    query.project = state.project;
  }
  if (state.model) {
    query.model = state.model;
  }
  const back = WINDOWS[state.window];
  if (back !== null) {
    query.since = Math.floor(now - back);
  }
  return query;
}

/**
 * What the pager shows for a response: the rows' range, and whether either way exists.
 *
 * @param {ListState} state
 * @param {{total: number, sessions: ReadonlyArray<unknown>}} answer
 */
export function pageOf(state, answer) {
  const count = answer.sessions.length;
  return {
    first: count === 0 ? 0 : state.offset + 1,
    last: state.offset + count,
    total: answer.total,
    hasPrevious: state.offset > 0,
    hasNext: state.offset + PAGE_SIZE < answer.total,
  };
}

/**
 * The same query as a command line would make it, for the golden that pins the data.
 *
 * @param {Record<string, string | number>} query
 */
export function queryString(query) {
  return Object.entries(query)
    .map(([key, value]) => `${key}=${encodeURIComponent(String(value))}`)
    .join("&");
}
