// The Pulls tab's list: every pull request of the repository, newest first, each with its
// state's icon, from the cache at once while the backend fills its lightweight catalog.
//
// Every decision lives here without a DOM. `describePulls` turns one list's envelope and
// rows into what the panel shows; `createPullsController` owns the filters, the windows of
// rows, bounded cached windows, foreground watch and progressive metadata preparation,
// which row is current and which takes Tab, and opening a row. `mountPullsPanel` is the
// browser glue: real fetch, timers, and paint. tests/dom/github-pulls-panel-session.js runs
// the same functions from the command line.
//
// The list is a tree: a row is one anchor in the role of a tree's item, in a list item with no
// role of its own, and its changed files hang off the item (pull-files-view.js): a chevron
// box before the state icon, a `.tree-children[role="group"]` after the anchor, which the
// anchor owns, and `aria-expanded` on it. A click opens the pull request and toggles its
// files, as a folder's does in the Files tab; Right and Left split the two. The walk goes by
// `rows`, not by the DOM, so it reads the same however a row is drawn.
//
// What starts a fetch (plan-2026-10-01-github-pulls-tab.md, "What starts a fetch"): a list's
// `GET` never does. Idle startup may warm the catalog and lightweight PR metadata in both
// repository modes; the visible panel also drives the foreground catalog watch. The server
// holds refreshes to its window. Background preparation follows the local catalog cursor
// and gives the entire visible viewport priority, without acquiring Git or diffs. A row's
// selected record read remains local, and only selection asks for its complete record.
// A key held down selects rows and opens only the one it stops on,
// so a walk costs no request per row.
//
// All text is GitHub's users', and untrusted. Paint writes it with textContent, and no value
// from GitHub reaches a class, a style, or markup. The only markup parsed is the shell's own
// chip group and icons.

import { createRowExpansion } from "./pull-files-tree.js";
import { mountFileTree } from "./pull-files-view.js";
import {
  authorLabel,
  avatarUrl,
  FAST_POLL_MS,
  h,
  isPlainClick,
  isEnvelope as isPullEnvelope,
  REFRESH_ASK_MS,
  relativeAge,
  SLOW_POLL_MS,
} from "./pull-page.js";
import { createStackIndex, stackCaption, watchStacks } from "./pull-stacks.js";
import { displayState, PULL_STATES, pullStateIcon } from "./pull-state.js";
import { createPullsWindow } from "./pulls-window.js";

const PULLS_ROUTE = "/api/plugin/github/pulls";
const REFRESH_ROUTE = "/api/plugin/github/pulls-refresh";
const PULL_ROUTE = "/api/plugin/github/pull";
const CORE_PREPARE_ROUTE = "/api/plugin/github/pull-cores-prepare";
// Existing measured GraphQL transport bound (exp-048); queues cover the whole viewport/catalog.
const CORE_BATCH_SIZE = 8;
const CORE_CONTROL_TIMEOUT_MS = 2000;
export const CORE_BUSY_RETRY_MS = 1000;

export const LISTS = Object.freeze(["open", "closed", "all"]);
const LIST_LABELS = Object.freeze({ all: "All", open: "Open", closed: "Closed" });
const FILTER_GROUP = "github-pulls-filter";

// The backend may cache every PR. Show the first 500 and extend by one cache page as
// the reader nears the tail. The viewport and its protected anchors mount separately.
export const WINDOW_ROWS = 100;
export const DISPLAY_ROWS = 500;
// Match Git history's near-tail distance.
const PAGE_AHEAD_PX = 240;
// Viewport neighbors; measured catalog-window evidence is recorded with the feature.
export const PULL_ROWS_OVERSCAN = 40;
// How long a walk waits for a next key before it opens the row it reached, once a key is
// repeating. A key's release opens it at once, so this is only for a release the page does
// not see, and it is past macOS's default repeat of 90 ms, so a held key never waits it out.
export const WALK_SETTLE_MS = 120;
// How long a row's opening waits for its record, so the page it replaces stays until the new
// one can paint with no empty frame. A read took 2 ms at the median and 23 ms at the worst of 15
// in Chrome, on a record of 5.6 KB of pallets/click at a load average of 6, so this is only for a
// server that is busy; past it the page opens and reads for itself, under its own quiet period.
export const OPEN_WAIT_MS = 100;
// How long a pointer rests on a row before its record is read ahead of a click, so that
// moving across the list reads nothing. A press follows a hover by about 200 ms or more, so
// the read is there first. It is a choice beside that, and not a bound on any cost.
export const PEEK_MS = 60;
// Records read ahead and not yet opened. A record is at most MAX_PULL_RECORD_BYTES, and a
// reader rests on a few rows at most before opening one.
export const MAX_PEEKED = 4;
const FETCHING = "Fetching pull requests…";
// Folders start open up to the measured file-list cap. Chrome 152, 2026-11-03: the
// first 1,183 files of django/django#15387 made 1,503 rows; 3,000 stress files made
// 4,539. With windowed paint, mounting cost 13.2 and 10.4 ms respectively, and a key's
// maximum cost was 4.1 and 1.4 ms. A larger page-count estimate starts compact.
export const AUTO_EXPAND_FILES = 3000;
// Trees of changed files kept while their rows are closed, so one opened again keeps the
// folders a reader opened. Each holds its list, at most 3,000 rows of text.
export const MAX_HELD_TREES = 8;

// What the panel says for each way a refresh can end, in what a reader can do about it. Each
// is the plan's table ("The lazy gh check"), and a cached list shows under any of them.
/** @type {Readonly<Record<string, string>>} */
const FAILURES = Object.freeze({
  gh_missing: "Install GitHub CLI, then run gh auth login --hostname github.com.",
  gh_too_old: "Update GitHub CLI, then run gh auth status --hostname github.com.",
  not_logged_in: "Run gh auth login --hostname github.com to connect.",
  network_error: "GitHub could not be reached.",
  github_unavailable: "GitHub is temporarily unavailable.",
  not_found_or_private: "GitHub could not find this repository or grant access to it.",
});
const WATCH_PAUSED = new Set(["gh_missing", "gh_too_old", "not_logged_in", "not_found_or_private"]);
const WATCH_SETUP_RETRY_MS = 120_000;

const NO_GITHUB = "This server serves no GitHub repository.";
// A checkout's tab is drawn for an `origin` on github.com that the plugin's grammar may still
// refuse, which the route answers as `not_github`.
const CHECKOUT_NOT_LISTED =
  "This checkout's origin is not a GitHub repository Metabrowser can list.";

/**
 * @typedef {{outcome: string, message: string | null, reset_at: string | null, at: string}} LastRefresh
 * @typedef {Record<keyof typeof LIST_LABELS, number>} PullFilterTotals
 * @typedef {{
 *   state: "absent" | "pending" | "current" | "stale",
 *   reason: string | null,
 *   source: string | null,
 *   list: string,
 *   fetched_at: string | null,
 *   reader: string | null,
 *   fresh_for_s: number,
 *   refreshing: boolean,
 *   last_refresh: LastRefresh | null,
 *   fetched: number,
 *   complete: boolean,
 *   truncated: boolean,
 *   total: number | null,
 *   repository_total: number | null,
 *   filter_totals: PullFilterTotals | null,
 *   catalog_fetched: number,
 *   generation: string | null,
 *   count_at: string | null,
 *   limit: number,
 *   next_after: number | null,
 *   rows: Record<string, any>[],
 * }} PullsEnvelope
 */

/**
 * What a row shows. Text only.
 *
 * @typedef {{
 *   number: number,
 *   href: string,
 *   state: import("./pull-state.js").PullState,
 *   stateLabel: string,
 *   title: string,
 *   author: string,
 *   avatar: string | null,
 *   baseRef: string,
 *   headRef: string,
 *   headLabel: string,
 *   updatedAt: string | null,
 *   refs: string,
 *   meta: string,
 * }} PullRow
 */

/**
 * @typedef {{
 *   filter: string,
 *   status: "loading" | "absent" | "pending" | "current" | "stale" | "unavailable",
 *   rows: PullRow[],
 *   rowsVersion: number,
 *   setSize: number,
 *   listName: string,
 *   repository: string | null,
 *   filterTotals: PullFilterTotals | null,
 *   countNumber: string | null,
 *   countSuffix: string | null,
 *   catalogReady: boolean,
 *   window: string | null,
 *   connection: {state: "working" | "connected" | "paused" | "unavailable", text: string,
 *     reload: boolean, retrying?: true, help?: "install" | "update"} | null,
 *   empty: string | null,
 *   loadMore: "ready" | "loading" | null,
 *   github: string | null,
 *   live: string,
 * }} PullsModel
 */

/** @param {unknown} value */
function text(value) {
  return typeof value === "string" ? value : "";
}

/**
 * The owner and name a list's source names: its canonical github.com address.
 *
 * @param {string | null} source
 * @returns {string | null}
 */
export function repositoryName(source) {
  const match = /^https:\/\/github\.com\/([^/]+\/[^/]+)$/.exec(source ?? "");
  return match === null ? null : match[1];
}

/**
 * One side of a row's branches, as the page's header names it: a bare branch when head and
 * base are one repository, and `owner:branch` when the head is another's.
 *
 * @param {Record<string, any>} row
 * @param {string | null} repository
 */
function rowHead(row, repository) {
  const head = text(row.head_ref);
  const from =
    typeof row.head_repository !== "string"
      ? `${head} (deleted fork)`
      : row.head_repository.toLowerCase() === repository?.toLowerCase()
        ? head
        : `${row.head_repository.split("/")[0]}:${head}`;
  return from;
}

/**
 * What one row of the route shows. Pure.
 *
 * @param {Record<string, any>} row
 * @param {string | null} repository
 * @returns {PullRow}
 */
export function describeRow(row, repository) {
  const state = displayState(row);
  const author = text(row.author) || "ghost";
  const headLabel = rowHead(row, repository);
  const baseRef = text(row.base_ref);
  const headRef = text(row.head_ref);
  const refs = `${baseRef} ← ${headLabel}`;
  return {
    number: row.number,
    href: `/pull/${row.number}`,
    state,
    stateLabel: PULL_STATES[state].label,
    title: text(row.title),
    author,
    avatar: avatarUrl(row.author_avatar_url),
    baseRef,
    headRef,
    headLabel,
    updatedAt: typeof row.updated_at === "string" ? row.updated_at : null,
    refs,
    meta: `#${row.number} · ${author} · ${refs}`,
  };
}

/**
 * How many pull requests that is, in the words a count is said with everywhere.
 *
 * @param {number} count
 */
function pullsCount(count) {
  return `${new Intl.NumberFormat("en-US").format(count)} pull request${count === 1 ? "" : "s"}`;
}

/**
 * What a list's last refresh failure says to a reader. Paging checks the settled
 * state, while the connection row can keep showing it during a recovery attempt.
 * @param {PullsEnvelope} envelope
 * @param {(iso: string) => string} formatTime
 * @param {{includeWhileRefreshing?: boolean}} [options]
 * @returns {{text: string, help?: "install" | "update"} | null}
 */
export function refreshFailure(envelope, formatTime, { includeWhileRefreshing = false } = {}) {
  const last = envelope.last_refresh;
  if (
    last === null ||
    last.outcome === "succeeded" ||
    (envelope.refreshing && !includeWhileRefreshing)
  ) {
    return null;
  }
  if (last.outcome === "rate_limited") {
    return {
      text:
        last.reset_at === null
          ? "GitHub rate limit reached."
          : `GitHub rate limit reached. Next attempt after ${formatTime(last.reset_at)}.`,
    };
  }
  const said = FAILURES[last.outcome] ?? last.message ?? last.outcome.replaceAll("_", " ");
  const sentence = `${said.charAt(0).toUpperCase()}${said.slice(1)}`;
  const help =
    last.outcome === "gh_missing"
      ? "install"
      : last.outcome === "gh_too_old"
        ? "update"
        : undefined;
  const text = sentence.endsWith(".") ? sentence : `${sentence}.`;
  return { text, ...(help === undefined ? {} : { help }) };
}

/** @param {PullsEnvelope | null} envelope @param {number} nowMs */
function rateHoldMs(envelope, nowMs) {
  const last = envelope?.last_refresh;
  if (last == null || (last.reset_at === null && last.outcome !== "rate_limited")) {
    return 0;
  }
  const deadline =
    last.reset_at === null
      ? Date.parse(last.at) + (envelope?.fresh_for_s ?? 0) * 1000
      : Date.parse(last.reset_at);
  return Number.isFinite(deadline) ? Math.max(0, deadline - nowMs) : 0;
}

/** @param {PullsEnvelope | null} envelope */
function watchPaused(envelope) {
  return WATCH_PAUSED.has(envelope?.last_refresh?.outcome ?? "");
}

/**
 * What the panel shows for one list. Pure.
 *
 * *rows* are the rows held so far, already described; the envelope is the last answer, whose
 * own `rows` are only a window.
 *
 * @param {PullsEnvelope | null} envelope
 * @param {{
 *   filter: string,
 *   rows: PullRow[],
 *   rowsVersion: number,
 *   filterTotals?: PullFilterTotals | null,
 *   nowMs: number,
 *   formatTime: (iso: string) => string,
 *   more: boolean,
 *   error: string | null,
 *   checkout?: boolean,
 *   online?: boolean,
 *   requesting?: boolean,
 * }} page
 * @returns {PullsModel}
 */
export function describePulls(envelope, page) {
  /** @type {PullsModel} */
  const model = {
    filter: page.filter,
    status: "loading",
    rows: page.rows,
    rowsVersion: page.rowsVersion,
    // How many rows the list has, which a window appended does not move: each row's place is
    // told against it, and not against the rows held or drawn so far.
    setSize: envelope?.total ?? Math.max(envelope?.fetched ?? 0, page.rows.length),
    listName: "Pull requests",
    repository: null,
    filterTotals:
      page.filterTotals === undefined ? (envelope?.filter_totals ?? null) : page.filterTotals,
    countNumber: null,
    countSuffix: null,
    catalogReady: envelope?.complete === true && !envelope.refreshing,
    window: null,
    connection: null,
    empty: null,
    loadMore: null,
    github: null,
    live: "",
  };
  const online = page.online !== false;
  if (envelope === null) {
    model.status = page.error === null ? "loading" : "unavailable";
    const working = online && (page.error === null || page.requesting === true);
    model.connection = {
      state: online ? (working ? "working" : "unavailable") : "paused",
      text: online ? (working ? FETCHING : (page.error ?? "")) : "Offline.",
      reload: online && !working,
    };
    model.live = model.connection.text;
    return model;
  }
  model.status = envelope.state;
  const repository = repositoryName(envelope.source);
  const failure = refreshFailure(envelope, page.formatTime, { includeWhileRefreshing: true });
  const holding = envelope.fetched > 0 || page.rows.length > 0;
  if (envelope.state === "absent" && envelope.reason === "not_github") {
    model.empty = page.checkout === true ? CHECKOUT_NOT_LISTED : NO_GITHUB;
    model.live = model.empty;
    return model;
  }
  model.repository = repository;
  const repositoryTotal = model.filterTotals?.all ?? envelope.repository_total;
  if (repositoryTotal !== null && repository !== null) {
    model.countNumber = new Intl.NumberFormat("en-US").format(repositoryTotal);
    model.countSuffix = repositoryTotal === 1 ? " PR on " : " PRs on ";
  }
  if (envelope.total !== null && page.rows.length > 0 && page.rows.length < envelope.total) {
    model.window = `Showing last ${new Intl.NumberFormat("en-US").format(page.rows.length)}`;
  }
  const name = repository === null ? "Pull requests" : `Pull requests of ${repository}`;
  const known = envelope.state === "current" || envelope.state === "stale";
  model.listName = known ? `${name}: ${pullsCount(envelope.total ?? envelope.fetched)}` : name;
  if (known && (envelope.total === 0 || (envelope.fetched === 0 && envelope.complete))) {
    model.empty = page.filter === "all" ? "No pull requests." : `No ${page.filter} pull requests.`;
  }
  const cached = holding ? " Showing cached pull requests." : "";
  const heldByRate = rateHoldMs(envelope, page.nowMs) > 0;
  const asking = page.requesting === true || envelope.refreshing;
  const working = asking || envelope.state === "pending" || envelope.state === "absent";
  if (!online) {
    model.connection = { state: "paused", text: `Offline.${cached}`, reload: false };
  } else if (page.error !== null) {
    model.connection = {
      state: "unavailable",
      text: page.error + cached,
      reload: !heldByRate && !asking,
    };
  } else if (failure !== null) {
    model.connection = {
      ...failure,
      state: "paused",
      text: failure.text + cached,
      reload: !heldByRate && !asking,
      ...(asking ? { retrying: true } : {}),
    };
  } else if (working || page.more) {
    model.connection = { state: "working", text: FETCHING, reload: false };
  } else if (!envelope.complete && envelope.catalog_fetched > 0) {
    const count = new Intl.NumberFormat("en-US").format(envelope.catalog_fetched);
    model.connection = { state: "paused", text: `Catalog paused · ${count} cached`, reload: true };
  } else {
    const age = relativeAge(envelope.count_at ?? envelope.fetched_at, page.nowMs);
    const note = envelope.truncated
      ? " · some pull requests could not be cached"
      : envelope.state === "stale"
        ? " · may be out of date"
        : "";
    model.connection = { state: "connected", text: `Updated ${age}${note}`, reload: true };
  }
  model.live = model.connection.state === "connected" ? model.listName : model.connection.text;
  const belowTotal = envelope.total === null || page.rows.length < envelope.total;
  const cachedMore = page.rows.length < envelope.fetched;
  const providerMayHaveMore =
    !envelope.complete &&
    envelope.total !== null &&
    online &&
    !heldByRate &&
    !watchPaused(envelope);
  if (page.more) {
    model.loadMore = "loading";
  } else if (holding && belowTotal && (cachedMore || providerMayHaveMore)) {
    model.loadMore = "ready";
  }
  return model;
}

/**
 * @param {unknown} value
 * @returns {value is PullsEnvelope}
 */
function isEnvelope(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const envelope = /** @type {Record<string, unknown>} */ (value);
  return (
    typeof envelope.state === "string" &&
    typeof envelope.refreshing === "boolean" &&
    typeof envelope.list === "string" &&
    Array.isArray(envelope.rows)
  );
}

/**
 * Whether *response* is the pin guard's refusal of a page whose pin moved. The guard answers it
 * by reloading the page onto the commit now served, so the list says nothing of its own for it,
 * whatever order the events arrive in: a page Back restores polls before the guard's check, and
 * "unavailable" would be on screen only until the reload. pull-page.js keeps the same rule.
 *
 * @param {PullsResponse} response
 */
function pinChanged(response) {
  const body = /** @type {Record<string, unknown> | null} */ (
    response.body !== null && typeof response.body === "object" ? response.body : null
  );
  return response.status === 409 && body?.code === "pin_changed";
}

/**
 * @typedef {{state: string, window: {id: string, generation: string}, numbers: number[]}} CoreWindowRequest
 * @typedef {{epoch: number, body: CoreWindowRequest, canRetry: boolean, retryDelay: number, lane: "visible" | "background", queueKey: string, done: boolean}} CoreDemand
 * @typedef {{status: number, etag: string | null, body: unknown}} PullsResponse
 * @typedef {{
 *   request(
 *     method: "GET" | "POST",
 *     route: string,
 *     options: {etag?: string | null, body?: unknown, signal?: AbortSignal},
 *   ): Promise<PullsResponse>,
 *   schedule(callback: () => void, delayMs: number): unknown,
 *   cancel(handle: unknown): void,
 *   now(): number,
 *   isVisible(): boolean,
 *   isOnline?(): boolean,
 *   formatTime(iso: string): string,
 *   render(model: PullsModel, identity: import("./pull-stacks.js").StackIdentity | null, arrivals: number[]): void,
 *   markCurrent(previous: number | null, next: number | null): void,
 *   markAnchor(previous: number | null, next: number | null, focus: boolean): void,
 *   reveal(number: number): void,
 *   open(route: {
 *     number: number,
 *     tab: string,
 *     replace: boolean,
 *     reader: {fetchAfterMs: number, initial: unknown, walking: () => boolean},
 *   }): unknown,
 *   filterChanged(state: string): void,
 *   recheckTail?(): void,
 * }} PullsDependencies
 */

/**
 * A list as far as it has been read. *etag* is the route's tag for the list's top window,
 * which every poll asks for, and *content* says which list file the rows held were read from.
 *
 * @typedef {{
 *   envelope: PullsEnvelope | null,
 *   lastTop: PullsEnvelope | null,
 *   rows: PullRow[],
 *   keys: Map<number, number>,
 *   version: number,
 *   etag: string | null,
 *   content: string | null,
 *   nextAfter: number | null,
 *   askedAt: number | null,
 *   more: boolean,
 *   error: string | null,
 *   displayLimit: number,
 *   priorityTarget: number,
 * }} HeldList
 */

/** @returns {HeldList} */
function emptyList() {
  return {
    envelope: null,
    lastTop: null,
    rows: [],
    keys: new Map(),
    version: 0,
    etag: null,
    content: null,
    nextAfter: null,
    askedAt: null,
    more: false,
    error: null,
    displayLimit: DISPLAY_ROWS,
    priorityTarget: 0,
  };
}

/**
 * Identity of the displayed prefix. Older catalog appends and count-only progress keep
 * it stable; changed existing rows, new leading rows and account resets change it.
 * @param {PullsEnvelope} envelope
 */
function contentOf(envelope) {
  return JSON.stringify([envelope.source, envelope.list, envelope.reader, envelope.generation]);
}

/**
 * The filters, windows, polling, and selection of one panel.
 *
 * @param {PullsDependencies} deps
 * @param {{filter?: string, current?: number | null, checkout?: boolean}} [options]
 */
export function createPullsController(deps, options = {}) {
  const checkout = options.checkout === true;
  /** @type {Map<string, HeldList>} */
  const lists = new Map(LISTS.map((name) => [name, emptyList()]));
  let filter = LISTS.includes(options.filter ?? "")
    ? /** @type {string} */ (options.filter)
    : "open";
  /** @type {number | null} */
  let current = options.current ?? null;
  let revealCurrent = true;
  /** The row that takes Tab: the current one, or else the first. @type {number | null} */
  let anchor = null;
  let shown = false;
  let disposed = false;
  let polling = false;
  // Idle startup can ask for metadata before this repository's Pulls tab is shown.
  let readAhead = false;
  let parked = false;
  let probeOnWake = false;
  let reconnectOnWake = false;
  let prioritizeFilter = false;
  /** @type {unknown} */
  let timer = null;
  /** @type {AbortController | null} */
  let inflight = null;
  // A request's answer counts only for the newest request of its list: a slow poll sent before
  // a refresh started must not replace the refresh's answer when it lands after it.
  let sent = 0;
  let shownRequest = 0;
  let requestEpoch = 0;
  /** @type {{identity: string, floor: number, seen: Map<number, number>} | null} */
  let arrivalBaseline = null;
  /** @type {AbortController | null} */
  let windowRead = null;
  /** @type {Set<AbortController>} */
  const refreshReads = new Set();
  /** @type {string | null} */
  let painted = null;

  /** The opening a key held down is waiting for, and the row it is for. */
  /** @type {unknown} */
  let walkTimer = null;
  /** @type {number | null} */
  let walkingTo = null;
  let opening = 0;
  /** @type {Map<number, {etag: string | null, body: unknown}>} */
  const peeked = new Map();
  /** @type {{number: number, controller: AbortController, done: Promise<{etag: string | null, body: unknown} | null>} | null} */
  let reading = null;
  /** @type {CoreDemand | null} */
  let coreWanted = null;
  /** @type {CoreDemand | null} */
  let coreSent = null;
  /** Last token that may still own the server window. @type {CoreDemand | null} */
  let coreHeld = null;
  let coreEpoch = 0;
  let sendingCore = false;
  /** @type {unknown} */
  let coreRetryTimer = null;
  /** The actual viewport may span several transport batches. @type {PullRow[]} */
  let visibleCores = [];
  let visibleCoreAt = 0;
  let visibleCoreKey = "";
  // Prime the already held default/filter page until a measured viewport replaces it.
  let primeHeldCores = false;
  let warming = false;
  let warmPaused = false;
  /** Last settled catalog row, retained across browser suspension. @type {number | null} */
  let warmAfter = null;
  /** @type {string | null} */
  let warmIdentity = null;
  /** @type {unknown} */
  let warmTimer = null;
  /** @type {AbortController | null} */
  let warmRead = null;
  // Counts describe the repository, so switching filters keeps the last accepted tallies.
  /** @type {PullFilterTotals | null} */
  let filterTotals = null;

  /** @returns {HeldList} */
  function held() {
    return /** @type {HeldList} */ (lists.get(filter));
  }

  const visible = () => !parked && deps.isVisible();
  const online = () => deps.isOnline?.() !== false;

  function live() {
    return shown && !disposed && visible();
  }

  function wake() {
    if (live() || ((warming || warmIdentity !== null) && visible() && !disposed)) {
      readAhead = readAhead || (!shown && warming);
      warmPaused = false;
      probeOnWake = true;
      render();
      void poll(!shown);
    }
  }

  /** @param {PullsEnvelope} envelope */
  function coreCatalogIdentity(envelope) {
    if (typeof envelope.generation !== "string") {
      return null;
    }
    // CatalogState.generation is the stable epoch followed by its paging revision.
    return JSON.stringify([envelope.source, envelope.reader, envelope.generation.split(":")[0]]);
  }

  function coreLive() {
    return !disposed && visible() && online() && (shown || warming);
  }

  function cancelWarmTimer() {
    if (warmTimer !== null) {
      deps.cancel(warmTimer);
      warmTimer = null;
    }
  }

  function queueCores() {
    if (
      !coreLive() ||
      warmPaused ||
      walkingTo !== null ||
      (!warming && visibleCoreAt >= visibleCores.length)
    ) {
      cancelWarmTimer();
      return;
    }
    // Coalesce rather than debounce: a fast catalog watch must not postpone warming forever.
    if (warmTimer !== null) {
      return;
    }
    warmTimer = deps.schedule(() => {
      warmTimer = null;
      void pumpCores();
    }, CORE_BUSY_RETRY_MS);
  }

  /** Read only the next batch of locally cataloged metadata; never extend the provider scan. */
  async function pumpCores() {
    if (!coreLive() || warmPaused || warmRead !== null || walkingTo !== null) {
      return;
    }
    if (coreWanted !== null && !coreWanted.done && coreWanted.canRetry) {
      return;
    }
    const list = held();
    if (
      (shown || primeHeldCores) &&
      visibleCoreAt < visibleCores.length &&
      typeof list.envelope?.generation === "string" &&
      list.content !== null
    ) {
      prepareBatch(
        visibleCores.slice(visibleCoreAt, visibleCoreAt + CORE_BATCH_SIZE),
        filter,
        list.envelope.generation,
        visibleCoreKey,
        "visible",
      );
      return;
    }
    if (!warming) {
      return;
    }
    if (primeHeldCores && visibleCores.length === 0 && list.envelope?.refreshing) {
      // A cold startup's first catalog page may arrive after the refresh POST.
      // Read that selected/default filter before walking the rest of All.
      await poll(true);
      queueCores();
      return;
    }
    const controller = new AbortController();
    warmRead = controller;
    try {
      const after = warmAfter === null ? "" : `&after=${warmAfter}`;
      const response = await deps.request(
        "GET",
        `${PULLS_ROUTE}?state=all&limit=${CORE_BATCH_SIZE}${after}`,
        { signal: controller.signal },
      );
      if (controller.signal.aborted || warmRead !== controller || !coreLive()) {
        return;
      }
      if (response.status !== 200 || !isEnvelope(response.body)) {
        warmPaused = true;
        return;
      }
      const envelope = response.body;
      const identity = coreCatalogIdentity(envelope);
      if (identity !== null && warmIdentity !== null && identity !== warmIdentity) {
        warmIdentity = identity;
        warmAfter = null;
        queueCores();
        return;
      }
      warmIdentity = identity;
      if (
        envelope.reason === "not_github" ||
        refreshFailure(envelope, deps.formatTime) !== null ||
        rateHoldMs(envelope, deps.now()) > 0
      ) {
        warmPaused = true;
        return;
      }
      if (envelope.rows.length === 0) {
        if (!envelope.refreshing && envelope.state !== "pending") {
          warming = false;
        } else {
          queueCores();
        }
        return;
      }
      if (typeof envelope.generation !== "string") {
        warmPaused = true;
        return;
      }
      // A visible demand may have arrived during this cache read.
      if (shown && visibleCoreAt < visibleCores.length) {
        queueCores();
        return;
      }
      const rows = envelope.rows.map((row) => describeRow(row, repositoryName(envelope.source)));
      prepareBatch(rows, "all", envelope.generation, contentOf(envelope), "background");
    } catch {
      if (!controller.signal.aborted) {
        warmPaused = true;
      }
    } finally {
      if (warmRead === controller) {
        warmRead = null;
      }
    }
  }

  /** @param {CoreWindowRequest} body */
  async function controlCoreWindow(body) {
    try {
      return await deps.request("POST", CORE_PREPARE_ROUTE, {
        body,
        // An exact-owner release must still be sendable after panel disposal.
        signal: AbortSignal.timeout(CORE_CONTROL_TIMEOUT_MS),
      });
    } catch {
      return null;
    }
  }

  /** @param {CoreDemand} demand */
  function releaseCoreWindow(demand) {
    return controlCoreWindow({ ...demand.body, numbers: [] });
  }

  function cancelCoreRetry() {
    if (coreWanted !== null) {
      coreWanted.canRetry = false;
    }
    if (coreRetryTimer !== null) {
      deps.cancel(coreRetryTimer);
      coreRetryTimer = null;
    }
  }

  async function sendCoreWindow() {
    if (sendingCore) {
      return;
    }
    sendingCore = true;
    try {
      while (coreWanted !== coreSent) {
        const previous = coreHeld;
        const demand = coreWanted;
        coreSent = demand;
        if (demand === null) {
          coreHeld = null;
          if (previous !== null) {
            await releaseCoreWindow(previous);
          }
          continue;
        }
        const response = await controlCoreWindow(demand.body);
        const receipt =
          /** @type {{preparation?: string, ready_numbers?: number[], skipped_numbers?: number[], failure?: unknown} | null | undefined} */ (
            response?.body
          );
        const admitted =
          (response?.status === 202 &&
            (receipt?.preparation === "started" || receipt?.preparation === "joined")) ||
          (response?.status === 200 && receipt?.preparation === "ready");
        const busy = response?.status === 200 && receipt?.preparation === "busy";
        const preserved =
          busy || (response?.status === 200 && receipt?.preparation === "not_owner");
        if (!preserved) {
          coreHeld = demand;
          if (!admitted && previous !== null) {
            // An uncertain replacement may have left its predecessor owned.
            await releaseCoreWindow(previous);
          }
        }
        if (demand.epoch !== coreEpoch) {
          if (coreHeld !== null) {
            await releaseCoreWindow(coreHeld);
            coreHeld = null;
          }
          coreSent = null;
        } else if (
          busy &&
          demand.canRetry &&
          demand === coreWanted &&
          coreLive() &&
          walkingTo === null
        ) {
          // Back off admission while preserving current work until its permit is available.
          const delay = demand.retryDelay;
          if (delay > 0) {
            demand.retryDelay = Math.min(demand.retryDelay * 2, SLOW_POLL_MS);
            coreRetryTimer = deps.schedule(() => {
              coreRetryTimer = null;
              if (coreWanted === demand && demand.canRetry && coreLive() && walkingTo === null) {
                coreSent = null;
                void sendCoreWindow();
              }
            }, delay);
          }
        } else if (demand === coreWanted && demand.canRetry && coreLive()) {
          if (receipt?.preparation === "started" || receipt?.preparation === "joined") {
            coreRetryTimer = deps.schedule(() => {
              coreRetryTimer = null;
              if (coreWanted === demand && demand.canRetry && coreLive()) {
                coreSent = null;
                void sendCoreWindow();
              }
            }, CORE_BUSY_RETRY_MS);
          } else if (receipt?.preparation === "ready") {
            const settled = new Set([
              ...(receipt.ready_numbers ?? []),
              ...(receipt.skipped_numbers ?? []),
            ]);
            if (!demand.body.numbers.every((number) => settled.has(number))) {
              demand.done = true;
              warmPaused = true;
              continue;
            }
            demand.done = true;
            if (demand.lane === "visible" && demand.queueKey === visibleCoreKey) {
              visibleCoreAt += demand.body.numbers.length;
            } else if (demand.lane === "background") {
              warmAfter = demand.body.numbers.at(-1) ?? warmAfter;
            }
            queueCores();
          } else if (receipt?.preparation === "not_owner" && demand.lane === "background") {
            // Catalog paging may advance its generation before admission. Re-read this
            // same cursor with the current generation; no settled row is skipped.
            demand.done = true;
            queueCores();
          } else {
            demand.done = true;
            warmPaused = true;
          }
        }
      }
    } finally {
      sendingCore = false;
    }
  }

  function clearCoreWindow() {
    cancelCoreRetry();
    coreEpoch += 1;
    coreWanted = null;
    void sendCoreWindow();
  }

  /**
   * @param {PullRow[]} rows
   * @param {string} state
   * @param {string} generation
   * @param {string} queueKey
   * @param {"visible" | "background"} lane
   */
  function prepareBatch(rows, state, generation, queueKey, lane) {
    cancelWarmTimer();
    cancelCoreRetry();
    const id = Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
    coreWanted = {
      queueKey,
      lane,
      done: false,
      epoch: coreEpoch,
      canRetry: true,
      retryDelay: CORE_BUSY_RETRY_MS,
      body: { state, window: { id, generation }, numbers: rows.map((row) => row.number) },
    };
    void sendCoreWindow();
  }

  /** Queue the whole measured viewport; eight is only the server's transport batch size.
   * @param {number[]} numbers
   */
  function prepareVisible(numbers) {
    if (!live() || !online() || walkingTo !== null) {
      return;
    }
    const list = held();
    if (typeof list.envelope?.generation !== "string" || list.content === null) {
      return;
    }
    const rows = numbers.flatMap((number) => {
      const index = list.keys.get(number);
      return index === undefined ? [] : [list.rows[index]];
    });
    const key = JSON.stringify([list.content, rows.map((row) => [row.number, row.updatedAt])]);
    if (key === visibleCoreKey) {
      primeHeldCores = false;
      if (coreWanted === null || coreWanted.done) {
        void pumpCores();
      }
      return;
    }
    primeHeldCores = false;
    visibleCoreKey = key;
    visibleCores = rows;
    visibleCoreAt = 0;
    warmPaused = false;
    if (rows.length === 0) {
      clearCoreWindow();
      queueCores();
      return;
    }
    prepareBatch(rows.slice(0, CORE_BATCH_SIZE), filter, list.envelope.generation, key, "visible");
  }

  function model() {
    const list = held();
    return describePulls(list.envelope, {
      filter,
      rows: list.rows,
      rowsVersion: list.version,
      filterTotals,
      nowMs: deps.now(),
      formatTime: deps.formatTime,
      more: list.more,
      error: list.error,
      checkout,
      online: online(),
      requesting: refreshReads.size > 0,
    });
  }

  // Compared without its rows, which their version stands for: an unchanged list costs a
  // string of its envelope, and not of its thousand rows.
  /** @param {number[]} [arrivals] One paint only, never stored in a held list. */
  function render(arrivals = []) {
    if (disposed) {
      return;
    }
    const next = model();
    const envelope = held().envelope;
    const identity =
      envelope === null ? null : { source: envelope.source, reader: envelope.reader };
    const key = JSON.stringify([{ ...next, rows: null }, identity, held().content]);
    if (key !== painted || arrivals.length > 0) {
      painted = key;
      deps.render(next, identity, arrivals);
    }
  }

  function clearTimer() {
    if (timer !== null) {
      deps.cancel(timer);
      timer = null;
    }
  }

  function pollDelay() {
    const list = held();
    const envelope = list.envelope;
    const fast =
      online() &&
      list.error === null &&
      (envelope === null || envelope.refreshing || envelope.state === "pending");
    const delay = fast ? FAST_POLL_MS : SLOW_POLL_MS;
    const rate = rateHoldMs(envelope, deps.now());
    return rate > 0 ? Math.min(delay, Math.max(FAST_POLL_MS, rate)) : delay;
  }

  function recheckTail() {
    const list = held();
    if (
      live() &&
      windowRead === null &&
      list.error === null &&
      !list.more &&
      list.rows.length >= list.displayLimit
    ) {
      deps.recheckTail?.();
    }
  }

  function scheduleNext() {
    clearTimer();
    if (!live()) {
      return;
    }
    timer = deps.schedule(() => {
      timer = null;
      void poll();
    }, pollDelay());
  }

  /**
   * Replace a list's rows with those an answer gives, keeping its version when they are the
   * same rows, so an answer that changed only its envelope repaints no row.
   *
   * @param {HeldList} list
   * @param {Record<string, any>[]} rows
   * @param {string | null} source
   */
  function holdRows(list, rows, source) {
    const repository = repositoryName(source);
    const next = rows.map((row) => describeRow(row, repository));
    const same =
      next.length === list.rows.length &&
      next.every((row, index) => JSON.stringify(row) === JSON.stringify(list.rows[index]));
    if (same) {
      return;
    }
    list.rows = next;
    list.keys = new Map(next.map((row, index) => [row.number, index]));
    list.version += 1;
  }

  /**
   * Take the envelope from a top-window read or a refresh.
   *
   * @param {HeldList} list
   * @param {PullsEnvelope} envelope
   * @param {number} request
   */
  function holdEnvelope(list, envelope, request) {
    list.envelope = envelope;
    const identity = coreCatalogIdentity(envelope);
    if (identity !== null && warmIdentity !== null && identity !== warmIdentity) {
      warmIdentity = identity;
      warmAfter = null;
      warming = true;
      warmPaused = false;
      visibleCoreKey = "";
      visibleCores = [];
      visibleCoreAt = 0;
      primeHeldCores = true;
      clearCoreWindow();
    }
    if (envelope.last_refresh !== null && envelope.last_refresh.outcome !== "succeeded") {
      arrivalBaseline = null;
    }
    list.error = null;
    shownRequest = request;
    filterTotals = envelope.filter_totals ?? null;
  }

  /**
   * Older rows can arrive after the last cache page had no following cursor. Continue from
   * the held tail only if it belongs to the generation whose count says more rows exist.
   * @param {HeldList} list
   * @param {PullsEnvelope} envelope
   */
  function recoverCachedCursor(list, envelope) {
    if (
      list.nextAfter !== null ||
      list.rows.length >= Math.min(list.displayLimit, envelope.fetched)
    ) {
      return true;
    }
    const last = list.rows.at(-1);
    if (last === undefined || list.content !== contentOf(envelope)) {
      return false;
    }
    list.nextAfter = last.number;
    return true;
  }

  /** The anchor follows the rows: the current one if it is held, and otherwise the first. */
  function settleAnchor() {
    const list = held();
    const next =
      current !== null && list.keys.has(current)
        ? current
        : anchor !== null && list.keys.has(anchor)
          ? anchor
          : (list.rows[0]?.number ?? null);
    if (next !== anchor) {
      const previous = anchor;
      anchor = next;
      deps.markAnchor(previous, next, false);
    }
  }

  /**
   * Read further windows for a current row the panel has not reached, as far as it can be.
   * Only All holds every pull request: in Open or Closed the address may name one the list
   * does not have, and chasing it would read every window to the end for nothing.
   */
  let chasing = false;
  function chaseCurrent() {
    const list = held();
    if (
      filter !== "all" ||
      current === null ||
      list.keys.has(current) ||
      list.nextAfter === null ||
      list.rows.length >= list.displayLimit
    ) {
      return;
    }
    if (current < list.nextAfter) {
      chasing = true;
      void loadWindow();
    }
  }

  /**
   * Stage a changed prefix in bounded cache pages before replacing the displayed rows.
   * Every page must name the same source, reader and generation. A concurrent append or
   * filter change discards the staged rows, and the old tag remains until a coherent read.
   *
   * @param {HeldList} list
   * @param {PullsEnvelope} top
   * @param {string} content
   * @param {{request: number, signal: AbortSignal}} asked
   * @returns {Promise<boolean>}
   */
  async function holdContent(list, top, content, asked) {
    const name = filter;
    const version = list.version;
    const desired = Math.min(
      list.displayLimit,
      Math.max(WINDOW_ROWS, list.rows.length),
      top.fetched,
    );
    const rows = top.rows.slice(0, desired);
    let after = top.next_after;
    while (rows.length < desired && after !== null) {
      const limit = Math.min(WINDOW_ROWS, desired - rows.length);
      const response = await deps.request(
        "GET",
        `${PULLS_ROUTE}?state=${name}&limit=${limit}&after=${after}`,
        { signal: asked.signal },
      );
      if (
        disposed ||
        asked.request < shownRequest ||
        name !== filter ||
        asked.signal.aborted ||
        list.version !== version ||
        response.status !== 200 ||
        !isEnvelope(response.body) ||
        contentOf(response.body) !== content
      ) {
        return false;
      }
      const seen = new Set(rows.map((row) => row.number));
      const next = response.body.rows.filter((row) => !seen.has(row.number));
      if (next.length === 0) {
        return false;
      }
      rows.push(...next.slice(0, desired - rows.length));
      after = response.body.next_after;
    }
    if (
      disposed ||
      asked.request < shownRequest ||
      name !== filter ||
      asked.signal.aborted ||
      list.version !== version
    ) {
      return false;
    }
    holdRows(list, rows, top.source);
    list.nextAfter = after;
    list.content = content;
    peeked.clear();
    clearCoreWindow();
    return true;
  }

  /**
   * Only an accepted top GET can identify arrivals. Its epoch stays stable across
   * ordinary generation changes, while a replaced catalog starts a neutral baseline.
   * @param {PullsEnvelope} top
   * @param {Map<number, number> | null} previous
   * @returns {number[]}
   */
  function arrivalsFromTop(top, previous) {
    const epoch =
      typeof top.generation === "string" ? /^(.*):\d+$/u.exec(top.generation)?.[1] : null;
    const fetchedAt = Date.parse(top.fetched_at ?? "");
    if (
      !live() ||
      !online() ||
      !top.complete ||
      top.list !== filter ||
      !top.source ||
      !top.reader ||
      !epoch ||
      !Number.isFinite(fetchedAt) ||
      (top.last_refresh !== null && top.last_refresh.outcome !== "succeeded")
    ) {
      arrivalBaseline = null;
      return [];
    }
    const identity = JSON.stringify([top.source, top.reader, epoch]);
    if (arrivalBaseline?.identity !== identity) {
      arrivalBaseline = top.refreshing
        ? null
        : { identity, floor: Math.max(fetchedAt, deps.now()), seen: new Map() };
      return [];
    }
    const { floor, seen } = arrivalBaseline;
    const arrivals = [];
    if (previous !== null) {
      for (const { number, created_at } of top.rows) {
        const created = typeof created_at === "string" ? Date.parse(created_at) : Number.NaN;
        if (!(created > floor) || previous.has(number) || seen.has(number)) {
          continue;
        }
        if (seen.size >= DISPLAY_ROWS) {
          // A burst that outruns the display budget starts another neutral baseline.
          arrivalBaseline = null;
          return [];
        }
        seen.set(number, created);
        arrivals.push(number);
      }
    }
    if (!top.refreshing && fetchedAt > floor) {
      arrivalBaseline.floor = fetchedAt;
      for (const [number, created] of seen) {
        if (created <= fetchedAt) {
          seen.delete(number);
        }
      }
    }
    return arrivals;
  }

  /**
   * Read the list's top window: the route's tag says whether anything changed, so a poll of
   * an unchanged list is a 304 however many rows are held. Catalog counts and older-page
   * progress keep the held prefix. A new generation stages that prefix in bounded pages.
   *
   * @param {boolean} [first] The panel's first read of this list, which a panel not shown
   *   still takes, so it opens with its rows.
   */
  async function poll(first = false) {
    if (disposed || polling || (!first && !live() && !(warming && visible() && online()))) {
      return;
    }
    const name = filter;
    const list = held();
    polling = true;
    const request = ++sent;
    const epoch = requestEpoch;
    const controller = new AbortController();
    inflight = controller;
    /** @type {number[]} */
    let arrivals = [];
    try {
      const response = await deps.request(
        "GET",
        `${PULLS_ROUTE}?state=${name}&limit=${WINDOW_ROWS}`,
        { etag: list.etag, signal: controller.signal },
      );
      if (
        disposed ||
        request < shownRequest ||
        name !== filter ||
        epoch !== requestEpoch ||
        controller.signal.aborted
      ) {
        return;
      }
      if (response.status === 200 && isEnvelope(response.body)) {
        if (request >= shownRequest) {
          const content = contentOf(response.body);
          const previous = content === list.content ? null : list.keys;
          const coherent =
            previous === null ||
            (await holdContent(list, response.body, content, {
              request,
              signal: controller.signal,
            }));
          if (
            coherent &&
            request >= shownRequest &&
            epoch === requestEpoch &&
            !controller.signal.aborted
          ) {
            holdEnvelope(list, response.body, request);
            list.lastTop = response.body;
            arrivals = arrivalsFromTop(response.body, previous);
            list.etag = response.etag;
            recoverCachedCursor(list, response.body);
            if (
              list.more &&
              (list.rows.length >= list.displayLimit ||
                (response.body.total !== null && list.rows.length >= response.body.total) ||
                !response.body.refreshing)
            ) {
              list.more = false;
            }
          }
        }
      } else if (response.status === 304) {
        list.error = null;
        if (list.lastTop !== null) {
          // The conditional response confirms the exact GET, even after a POST header.
          arrivalsFromTop(list.lastTop, null);
        }
      } else {
        arrivalBaseline = null;
        if (!pinChanged(response)) {
          list.error = `The list is unavailable (HTTP ${response.status}).`;
        }
      }
    } catch {
      if (disposed || request < shownRequest || name !== filter || controller.signal.aborted) {
        return;
      }
      arrivalBaseline = null;
      list.error = "The server did not answer.";
    } finally {
      // A change of filter already let this request go, and may have started another.
      if (inflight === controller) {
        inflight = null;
        polling = false;
      }
    }
    if (disposed || name !== filter || epoch !== requestEpoch) {
      return;
    }
    settleAnchor();
    render(arrivals);
    if (warming && primeHeldCores && visibleCores.length === 0 && list.rows.length > 0) {
      // Reuse the page already held for the default/current filter, without inventing
      // a row-count cutoff. The real viewport supersedes this startup hint.
      visibleCores = list.rows.slice();
      visibleCoreAt = 0;
      visibleCoreKey = JSON.stringify([
        list.content,
        visibleCores.map((row) => [row.number, row.updatedAt]),
      ]);
    }
    if (first && shown && revealCurrent && current !== null && list.keys.has(current)) {
      deps.reveal(current);
    }
    chaseCurrent();
    // Fill the reader's display budget from cached metadata, independently of provider paging.
    if (list.nextAfter !== null && list.rows.length < list.displayLimit) {
      await loadWindow();
    }
    if (disposed || name !== filter || epoch !== requestEpoch) {
      return;
    }
    scheduleNext();
    askIfDue();
    if (
      warmPaused &&
      list.envelope !== null &&
      refreshFailure(list.envelope, deps.formatTime) === null &&
      rateHoldMs(list.envelope, deps.now()) === 0
    ) {
      warmPaused = false;
    }
    queueCores();
    recheckTail();
  }

  /**
   * Ask for the list's refresh when it is stale and shown, or being read ahead of the tab. The
   * server holds it to one attempt a window.
   */
  function askIfDue() {
    const list = held();
    const envelope = list.envelope;
    const wanted = shown || readAhead;
    readAhead = false;
    if (
      !wanted ||
      disposed ||
      !visible() ||
      !online() ||
      envelope === null ||
      envelope.reason === "not_github" ||
      list.error !== null ||
      refreshReads.size > 0
    ) {
      return;
    }
    const priority = shown && prioritizeFilter;
    prioritizeFilter = false;
    if (rateHoldMs(envelope, deps.now()) > 0) {
      return;
    }
    const last = envelope.last_refresh;
    const probe = probeOnWake;
    const reconnect = reconnectOnWake && last?.outcome === "network_error";
    probeOnWake = false;
    reconnectOnWake = false;
    const now = deps.now();
    const windowMs = envelope.fresh_for_s * 1000;
    const failureDue =
      last !== null && last.outcome !== "succeeded" && now - Date.parse(last.at) > windowMs;
    if (
      watchPaused(envelope) &&
      last !== null &&
      now - Date.parse(last.at) <= (probe ? windowMs : Math.max(windowMs, WATCH_SETUP_RETRY_MS))
    ) {
      return;
    }
    const target = Math.min(list.displayLimit, envelope.total ?? list.displayLimit);
    const missingRows = envelope.fetched < target;
    const foreground = priority && missingRows && !reconnect;
    const needsRows = missingRows && (foreground || list.priorityTarget < target);
    const needsCatalog = !envelope.complete && !envelope.refreshing;
    if (
      !reconnect &&
      !needsRows &&
      !needsCatalog &&
      (envelope.refreshing ||
        (!failureDue && envelope.state !== "absent" && envelope.state !== "stale"))
    ) {
      return;
    }
    if (!reconnect && !needsRows && list.askedAt !== null && now - list.askedAt < windowMs) {
      return;
    }
    list.askedAt = now;
    list.priorityTarget = target;
    void ask({
      state: filter,
      target: list.displayLimit,
      ...(foreground ? {} : { background: true }),
      ...(reconnect ? { reconnect: true } : {}),
    });
  }

  /**
   * Send a refresh and take the envelope it answers with. The answer has no rows.
   *
   * @param {{state: string, target: number, retry?: boolean, background?: boolean, reconnect?: boolean}} body
   */
  async function ask(body) {
    const name = body.state;
    const list = /** @type {HeldList} */ (lists.get(name));
    const request = ++sent;
    const reader = body.retry === true || list.more;
    const epoch = requestEpoch;
    const controller = new AbortController();
    refreshReads.add(controller);
    render();
    try {
      const response = await deps.request("POST", REFRESH_ROUTE, {
        body,
        signal: controller.signal,
      });
      const answer = /** @type {{pulls?: unknown, error?: unknown} | null} */ (response.body);
      if (disposed || epoch !== requestEpoch || controller.signal.aborted) {
        return;
      }
      if (
        (response.status === 202 || response.status === 200) &&
        answer !== null &&
        isEnvelope(answer.pulls)
      ) {
        if (request >= shownRequest) {
          holdEnvelope(list, answer.pulls, request);
        }
        if (response.status === 202) {
          // The answer changed; the next poll must not be answered by a 304.
          list.etag = null;
        } else {
          list.more = false;
        }
      } else if (reader) {
        const said = answer !== null && typeof answer.error === "string" ? answer.error : null;
        if (!pinChanged(response)) {
          list.error = `The refresh was refused (${said ?? `HTTP ${response.status}`}).`;
        }
        list.more = false;
      }
    } catch {
      if (reader && !disposed && epoch === requestEpoch && !controller.signal.aborted) {
        list.error = "The refresh request failed.";
        list.more = false;
      }
    } finally {
      refreshReads.delete(controller);
    }
    if (!disposed && name === filter && epoch === requestEpoch) {
      render();
      scheduleNext();
    }
  }

  /** Read the next window of rows the list already holds. Local, and runs no gh. */
  async function loadWindow() {
    const list = held();
    const name = filter;
    if (
      disposed ||
      windowRead !== null ||
      list.nextAfter === null ||
      list.rows.length >= list.displayLimit
    ) {
      return;
    }
    const controller = new AbortController();
    windowRead = controller;
    const epoch = requestEpoch;
    const version = list.version;
    const after = list.nextAfter;
    const content = list.content;
    const limit = Math.min(WINDOW_ROWS, list.displayLimit - list.rows.length);
    let advanced = false;
    try {
      const response = await deps.request(
        "GET",
        `${PULLS_ROUTE}?state=${name}&limit=${limit}&after=${after}`,
        { signal: controller.signal },
      );
      if (
        disposed ||
        epoch !== requestEpoch ||
        name !== filter ||
        controller.signal.aborted ||
        windowRead !== controller
      ) {
        return;
      }
      if (list.version !== version || list.nextAfter !== after) {
        return;
      }
      if (response.status === 200 && isEnvelope(response.body)) {
        if (contentOf(response.body) !== content) {
          list.etag = null;
          return;
        }
        const repository = repositoryName(response.body.source);
        const fresh = response.body.rows
          .map((row) => describeRow(row, repository))
          .filter((row) => !list.keys.has(row.number))
          .slice(0, list.displayLimit - list.rows.length);
        for (const row of fresh) {
          list.keys.set(row.number, list.rows.length);
          list.rows.push(row);
        }
        if (fresh.length > 0) {
          list.version += 1;
        }
        // Cached pages only advance the rows and cursor. Keep the top window's metadata.
        list.error = null;
        list.nextAfter = response.body.next_after;
        advanced = fresh.length > 0 && list.nextAfter !== after;
        const total = list.envelope?.total ?? null;
        if (
          list.rows.length >= list.displayLimit ||
          (total !== null && list.rows.length >= total)
        ) {
          list.more = false;
        }
      } else if (!pinChanged(response)) {
        list.error = `The list is unavailable (HTTP ${response.status}).`;
        list.more = false;
      }
    } catch {
      if (!disposed && epoch === requestEpoch && !controller.signal.aborted) {
        list.error = "The server did not answer.";
        list.more = false;
      }
    } finally {
      if (windowRead === controller) {
        windowRead = null;
        recheckTail();
      }
    }
    if (!disposed && epoch === requestEpoch && name === filter) {
      settleAnchor();
      render();
      if (chasing && current !== null && list.keys.has(current)) {
        chasing = false;
        if (revealCurrent) {
          deps.reveal(current);
        }
      }
      if (advanced && list.nextAfter !== null && list.rows.length < list.displayLimit) {
        await loadWindow();
      } else if (
        advanced &&
        list.more &&
        live() &&
        list.nextAfter === null &&
        list.envelope !== null &&
        list.rows.length < Math.min(list.displayLimit, list.envelope.total ?? list.displayLimit) &&
        list.priorityTarget < list.displayLimit &&
        online() &&
        rateHoldMs(list.envelope, deps.now()) === 0 &&
        !watchPaused(list.envelope)
      ) {
        list.priorityTarget = list.displayLimit;
        await ask({ state: name, target: list.displayLimit });
      }
    }
  }

  /**
   * Grow the displayed prefix, reading the cache before asking the shared catalog job
   * to prioritize more rows. One scroll approach adds one page. The button can add five.
   * @param {"scroll" | "button"} trigger
   */
  function extendDisplay(trigger) {
    const list = held();
    const envelope = list.envelope;
    if (disposed || envelope === null || list.more || envelope.reason === "not_github") {
      return Promise.resolve();
    }
    const automatic = trigger === "scroll";
    if (
      automatic &&
      (!live() ||
        windowRead !== null ||
        list.error !== null ||
        list.rows.length < list.displayLimit)
    ) {
      return Promise.resolve();
    }
    // At a completed or failed refresh, automatic paging can still reveal cached rows.
    const cacheOnly =
      envelope.complete ||
      !online() ||
      watchPaused(envelope) ||
      rateHoldMs(envelope, deps.now()) > 0 ||
      (automatic && refreshFailure(envelope, deps.formatTime) !== null);
    const limit = Math.min(
      list.displayLimit + (automatic ? WINDOW_ROWS : DISPLAY_ROWS),
      envelope.total ?? Number.POSITIVE_INFINITY,
      cacheOnly ? envelope.fetched : Number.POSITIVE_INFINITY,
    );
    if (limit <= list.rows.length) {
      return Promise.resolve();
    }
    list.displayLimit = limit;
    list.more = true;
    render();
    if (!recoverCachedCursor(list, envelope)) {
      list.etag = null;
      return poll();
    }
    if (list.nextAfter !== null && list.rows.length < list.displayLimit) {
      return loadWindow();
    }
    if (!cacheOnly && envelope.fetched < list.displayLimit) {
      list.priorityTarget = list.displayLimit;
      return ask({ state: filter, target: list.displayLimit });
    }
    list.more = false;
    render();
    return Promise.resolve();
  }

  /** @param {number} number */
  function setCurrentRow(number) {
    cancelCoreRetry();
    const previous = current;
    if (previous !== number) {
      current = number;
      deps.markCurrent(previous, number);
    }
  }

  /**
   * Read a row's record, the newest asked for at a time. Local, and runs no gh.
   *
   * @param {number} number
   * @returns {Promise<{etag: string | null, body: unknown} | null>}
   */
  function readRecord(number) {
    const had = peeked.get(number);
    if (had !== undefined) {
      return Promise.resolve(had);
    }
    if (reading?.number === number) {
      return reading.done;
    }
    reading?.controller.abort();
    const controller = new AbortController();
    const done = deps
      .request("GET", `${PULL_ROUTE}?number=${number}`, { signal: controller.signal })
      .then((response) => {
        if (
          response.status !== 200 ||
          disposed ||
          controller.signal.aborted ||
          reading?.controller !== controller
        ) {
          return null;
        }
        const answer = { etag: response.etag, body: response.body };
        const envelope = response.body;
        if (
          isPullEnvelope(envelope) &&
          envelope.number === number &&
          envelope.source === held().envelope?.source &&
          envelope.record !== null
        ) {
          if (peeked.size >= MAX_PEEKED) {
            peeked.delete(/** @type {number} */ (peeked.keys().next().value));
          }
          peeked.set(number, answer);
        }
        return answer;
      })
      .catch(() => null)
      .finally(() => {
        if (reading?.controller === controller) {
          reading = null;
        }
      });
    reading = { number, controller, done };
    return done;
  }

  function clearWalk() {
    if (walkTimer !== null) {
      deps.cancel(walkTimer);
      walkTimer = null;
    }
    walkingTo = null;
  }

  /**
   * Open a row's page, once its record is read or the wait for it is over. Only the newest
   * opening counts. *fetchAfterMs* is how long the page waits before it fetches a record the
   * cache lacks: a press of a key can be the first of many, and a click means that row.
   * *replace* is a key's: a skim replaces the history entry, as the file tree's and Git's do,
   * so Back leaves the list in one step however many rows were passed; a click or Enter pushes.
   *
   * @param {number} number
   * @param {number} fetchAfterMs
   * @param {boolean} replace
   */
  async function openRow(number, fetchAfterMs, replace) {
    clearWalk();
    const ticket = ++opening;
    /** @type {{etag: string | null, body: unknown} | null} */
    let initial = null;
    /** @type {unknown} */
    let waiter = null;
    await Promise.race([
      readRecord(number).then((answer) => {
        initial = answer;
      }),
      new Promise((resolve) => {
        waiter = deps.schedule(() => resolve(undefined), OPEN_WAIT_MS);
      }),
    ]);
    deps.cancel(waiter);
    if (disposed || ticket !== opening) {
      return;
    }
    peeked.delete(number);
    // While a key is still held the page waits to fetch, whatever its wait was: a first press
    // held past it would otherwise fetch the row the walk left long ago.
    const walking = () => !disposed && walkingTo !== null;
    deps.open({ number, tab: "", replace, reader: { fetchAfterMs, initial, walking } });
  }

  function cancelReads() {
    arrivalBaseline = null;
    clearCoreWindow();
    visibleCores = [];
    visibleCoreAt = 0;
    visibleCoreKey = "";
    cancelWarmTimer();
    warmRead?.abort();
    warmRead = null;
    requestEpoch += 1;
    inflight?.abort();
    inflight = null;
    polling = false;
    windowRead?.abort();
    windowRead = null;
    reading?.controller.abort();
    reading = null;
    for (const controller of refreshReads) {
      controller.abort();
    }
    refreshReads.clear();
    opening += 1;
    clearWalk();
  }

  /**
   * The list rows changed under the panel: a new filter, or it became visible.
   *
   * @param {string} name
   * @param {{fromAddress?: boolean}} [how]
   */
  function setFilter(name, how = {}) {
    if (disposed || !LISTS.includes(name) || name === filter) {
      return;
    }
    cancelReads();
    filter = name;
    prioritizeFilter = shown;
    settleAnchor();
    painted = null;
    render();
    if (how.fromAddress !== true) {
      deps.filterChanged(name);
    }
    void poll(true);
  }

  return Object.freeze({
    /**
     * Read metadata after the first tree settles, in both repository modes. The one-pass
     * detail queue can continue in Files while the browser remains visible (*refreshAhead*).
     *
     * @param {{shown?: boolean, refreshAhead?: boolean}} [how]
     */
    start(how = {}) {
      shown = how.shown === true;
      prioritizeFilter = shown;
      readAhead = how.refreshAhead === true;
      warming = readAhead;
      primeHeldCores = warming;
      warmPaused = false;
      render();
      return poll(true);
    },
    /** @param {boolean} visible */
    setShown(visible) {
      if (disposed || visible === shown) {
        return;
      }
      shown = visible;
      prioritizeFilter = visible;
      if (!visible) {
        clearTimer();
        cancelReads();
        queueCores();
        return;
      }
      if (revealCurrent && current !== null && held().keys.has(current)) {
        deps.reveal(current);
      }
      wake();
    },
    setFilter,
    prepareVisible,
    /**
     * The address says which pull request's page holds the pane. Not a selection: the row
     * only follows it, and no fetch starts.
     *
     * @param {number | null} number
     * @param {{preserveScroll?: boolean}} [options]
     */
    setCurrent(number, options = {}) {
      if (disposed) {
        return;
      }
      if (options.preserveScroll) {
        revealCurrent = false;
      }
      if (number === current) {
        return;
      }
      revealCurrent = !options.preserveScroll;
      // The address moved by itself, by Back or by a link on the page: a row that is still
      // waiting for its record to open does not open over it.
      cancelCoreRetry();
      opening += 1;
      if (walkingTo !== null && walkingTo !== number) {
        clearWalk();
      }
      const previous = current;
      current = number;
      deps.markCurrent(previous, number);
      settleAnchor();
      if (number !== null && held().keys.has(number)) {
        if (revealCurrent) {
          deps.reveal(number);
        }
      } else {
        chaseCurrent();
      }
    },
    /**
     * Move the row selection by a key. Work is the two rows that change, and the pane opens
     * the row at once for a single press, or for a held key when it stops.
     *
     * @param {-1 | 1} delta
     * @param {{repeat?: boolean}} [how]
     * @returns {boolean} Whether the key was the list's, so nothing else scrolls for it.
     */
    move(delta, how = {}) {
      const list = held();
      if (disposed || list.rows.length === 0) {
        return false;
      }
      const at = anchor === null ? -1 : (list.keys.get(anchor) ?? -1);
      const target = at + delta;
      if (target < 0) {
        return true;
      }
      if (target >= list.rows.length) {
        void extendDisplay("scroll");
        return true;
      }
      const number = list.rows[target].number;
      const previous = anchor;
      anchor = number;
      deps.markAnchor(previous, number, true);
      setCurrentRow(number);
      // Keep rows arriving ahead of a walk, so a held key does not stall on the window's end.
      if (list.rows.length - target <= 2 && list.nextAfter !== null) {
        void loadWindow();
      }
      if (how.repeat === true) {
        clearWalk();
        walkingTo = number;
        walkTimer = deps.schedule(() => {
          walkTimer = null;
          void openRow(number, REFRESH_ASK_MS, true);
        }, WALK_SETTLE_MS);
      } else {
        void openRow(number, REFRESH_ASK_MS, true);
      }
      return true;
    },
    /** The key that was walking was let go: open what it stopped on. */
    released() {
      if (walkTimer !== null && walkingTo !== null) {
        const number = walkingTo;
        void openRow(number, REFRESH_ASK_MS, true);
      }
    },
    /**
     * A reader chose a row with a pointer or Enter.
     *
     * @param {number} number
     */
    activate(number) {
      if (disposed) {
        return;
      }
      setCurrentRow(number);
      if (anchor !== number) {
        const previous = anchor;
        anchor = number;
        deps.markAnchor(previous, number, false);
      }
      void openRow(number, 0, false);
    },
    /** Open the row that holds focus, for Enter and Space. */
    activateAnchor() {
      if (disposed || anchor === null) {
        return false;
      }
      setCurrentRow(anchor);
      void openRow(anchor, 0, false);
      return true;
    },
    /**
     * Focus reached a row by Tab or the pointer: it becomes the anchor, and nothing opens.
     *
     * @param {number} number
     */
    focused(number) {
      if (!disposed && anchor !== number && held().keys.has(number)) {
        const previous = anchor;
        anchor = number;
        deps.markAnchor(previous, number, false);
      }
    },
    /**
     * A row took the pointer or focus: read its record ahead of a click. A walk does not
     * come here, so it reads nothing per row.
     *
     * @param {number} number
     */
    peek(number) {
      if (!disposed && walkingTo === null) {
        void readRecord(number);
      }
    },
    /** A press of Fetch more. */
    loadMore: () => extendDisplay("button"),
    /** The reader neared the end of the displayed rows. */
    reachedEnd: () => extendDisplay("scroll"),
    /** A press of Reload asks the repository's existing catalog job. */
    reload() {
      if (!live() || model().connection?.reload !== true || refreshReads.size > 0) {
        return Promise.resolve();
      }
      held().error = null;
      return ask({ state: filter, target: held().displayLimit, retry: true });
    },
    onFocus: wake,
    onOnline() {
      warmPaused = false;
      queueCores();
      arrivalBaseline = null;
      reconnectOnWake = true;
      wake();
    },
    onOffline() {
      cancelWarmTimer();
      cancelCoreRetry();
      warmRead?.abort();
      warmRead = null;
      arrivalBaseline = null;
      reconnectOnWake = false;
      render();
      scheduleNext();
    },
    onVisibilityChange() {
      if (disposed) {
        return;
      }
      if (!visible()) {
        clearTimer();
        cancelReads();
        return;
      }
      warmPaused = false;
      queueCores();
      wake();
    },
    pause() {
      parked = true;
      clearTimer();
      cancelReads();
    },
    resume() {
      parked = false;
      wake();
    },
    dispose() {
      disposed = true;
      clearTimer();
      clearWalk();
      cancelReads();
      peeked.clear();
    },
    snapshot: () => ({
      filter,
      current,
      anchor,
      shown,
      rows: held().rows.length,
      displayLimit: held().displayLimit,
      nextAfter: held().nextAfter,
      etag: held().etag,
      peeked: [...peeked.keys()],
      walkingTo,
      timer: timer === null ? null : pollDelay() === FAST_POLL_MS ? "fast" : "slow",
    }),
  });
}

// ── Browser glue ────────────────────────────────────────────────

/**
 * The fetch every route here is read through.
 *
 * @param {MetabrowserPublicSdk["perf"]} perf
 * @param {"GET" | "POST"} method
 * @param {string} route
 * @param {{etag?: string | null, body?: unknown, signal?: AbortSignal}} options
 * @returns {Promise<PullsResponse>}
 */
async function request(perf, method, route, options) {
  /** @type {Record<string, string>} */
  const headers = {};
  if (method === "GET" && options.etag) {
    headers["if-none-match"] = options.etag;
  }
  if (method === "POST") {
    headers["content-type"] = "application/json";
  }
  const response = await fetch(route, {
    method,
    headers,
    cache: "no-store",
    body: method === "POST" ? JSON.stringify(options.body ?? {}) : undefined,
    signal: options.signal,
  });
  let decoded = null;
  if (response.status !== 304) {
    try {
      decoded = await perf.measureAsync("githubPulls:decode", () => response.json(), {
        route: route.split("?")[0],
      });
    } catch {
      decoded = null;
    }
  }
  return { status: response.status, etag: response.headers.get("etag"), body: decoded };
}

/**
 * Mount the list into the Pulls tab. Browser only.
 *
 * @param {HTMLElement} container
 * @param {MetabrowserPublicRenderContext} ctx
 * @param {MetabrowserPublicSdk} mb
 */
export function mountPullsPanel(container, ctx, mb) {
  const nav = ctx.pullsNav;
  if (nav === undefined) {
    throw new Error("metabrowser github plugin: the Pulls panel needs its host");
  }
  const controls = mb.filterControls;
  if (controls === undefined) {
    throw new Error("metabrowser github plugin: the shared filter controls are unavailable");
  }
  const filters = h("div", { class: "github-pulls-filters" });
  filters.innerHTML = controls.groupHtml({
    key: FILTER_GROUP,
    select: "one",
    layout: "joined",
    label: "Show",
    options: LISTS.map((value) => ({
      value,
      label: LIST_LABELS[/** @type {keyof typeof LIST_LABELS} */ (value)],
    })),
    value: nav.filter,
  });
  /** @type {{chip: HTMLButtonElement, value: keyof typeof LIST_LABELS, tally: HTMLElement}[]} */
  const tallies = [...filters.querySelectorAll("button")].flatMap((chip) => {
    const value = chip.dataset.chipValue;
    if (value !== "open" && value !== "closed" && value !== "all") {
      return [];
    }
    const tally = h("span", { class: "count", "aria-hidden": "true" });
    chip.append(" ", tally);
    return [{ chip, value, tally }];
  });
  const status = h("p", { class: "github-pulls-status" });
  // A tree: a row's changed files hang off it as a group. Its keys are this view's, bound by
  // the tab's host; the Files tree's keyboard handler is scoped to the Files tab and never
  // sees these rows.
  const list = h("ul", { class: "github-pulls-list", role: "tree" });
  const empty = h("p", { class: "github-pulls-empty" });
  const connectionMessage = h("span");
  const spinner = h("span", { class: "github-pulls-connection-spinner", hidden: "" }, [
    h("span", { class: "spinner spinner-sm", "aria-hidden": "true" }),
  ]);
  const connectionText = h("span", { class: "github-pulls-connection-text" }, [
    spinner,
    connectionMessage,
  ]);
  const connectionHelp = h("span", { hidden: "" });
  const reloadButton = h(
    "button",
    { type: "button", class: "btn github-pulls-reload", "aria-disabled": "true" },
    ["Reload"],
  );
  reloadButton.addEventListener("click", () => void controller.reload());
  const connection = h("div", { class: "github-pulls-connection", hidden: "" }, [
    connectionText,
    connectionHelp,
    reloadButton,
  ]);
  const foot = h("div", { class: "github-pulls-foot" });
  const moreButton = /** @type {HTMLButtonElement} */ (
    h("button", { type: "button", class: "btn github-pulls-more" }, ["Fetch more"])
  );
  moreButton.addEventListener("click", () => void controller.loadMore());
  const live = h("span", { class: "sr-only", "aria-live": "polite" });
  container.classList.add("github-pulls");
  container.replaceChildren(filters, status, connection, list, empty, foot, live);

  /**
   * What is painted of each row held, by number: its elements, the key of what it shows, and
   * when it was updated, whose age moves on while the row stays.
   *
   * @typedef {{
   *   item: HTMLElement,
   *   row: HTMLAnchorElement,
   *   age: HTMLElement,
   *   stack: HTMLElement,
   *   title: HTMLElement,
   *   icon: HTMLElement,
   *   meta: HTMLElement,
   *   info: PullRow,
   *   key: string,
   *   at: number | null,
   *   label: string,
   *   releaseCopies: () => void,
   * }} PaintedRow
   */
  /** @type {Map<number, PaintedRow>} */
  const painted = new Map();
  let stackIndex = createStackIndex(null);
  /** @type {import("./pull-stacks.js").StackIdentity | null} */
  let stackIdentity = null;
  /** The rows last painted, in their order: an append leaves them as they were. @type {PullRow[]} */
  let paintedRows = [];
  let paintedVersion = -1;
  const rowWindow = createPullsWindow({ estimate: 41.5, overscan: PULL_ROWS_OVERSCAN });
  /** @type {Map<number, number>} */
  let rowIndices = new Map();
  /** @type {Map<string, HTMLElement>} */
  const gaps = new Map();
  /** @type {{number: number, offset: number} | null} */
  let readingPlace = null;
  /** @type {number | null} */
  let windowFrame = null;
  /** @type {number | null} */
  let coreFrame = null;
  /** @type {number | null} */
  let coreTimer = null;
  let windowDisposed = false;

  /** The minute the rows' ages were last told in. */
  let agedIn = Math.floor(Date.now() / 60_000);
  /** @type {number | null} */
  let currentRow = nav.current;
  /** @type {number | null} */
  let anchorRow = null;

  /** The registry's disclosure chevron, parsed once: a constant, not the pull request's text. */
  const chevronSvg = new DOMParser().parseFromString(mb.icons?.toggle || "", "text/html").body
    .firstElementChild;
  const chevron = () => (chevronSvg === null ? null : document.importNode(chevronSvg, true));
  // Narrowed once, for the functions below that run later.
  const tab = nav;

  // Which rows show their changed files, and each one's tree, by number: open ones, and the
  // last MAX_HELD_TREES closed, so one opened again is as the reader left it.
  const expansion = createRowExpansion();
  /** @type {Map<number, ReturnType<typeof mountFileTree>>} */
  const trees = new Map();
  /** The tree a file row with focus is in, whose keys the host's file keys are. */
  /** @type {number | null} */
  let focusedTree = null;
  let panelShown = nav.shown;
  /** The file the address names, and of which pull request. */
  let currentFile = nav.file ?? null;
  /** @type {unknown} */
  let followedPage = null;
  /** @type {(() => void) | null} */
  let unwatchFile = null;
  let fileFollowEpoch = 0;
  /** A null-file route replays the same page's current observation after address sync.
   * @param {boolean} [replay]
   */
  function followCurrentFile(replay = false) {
    const number = currentRow;
    const page = number === null ? null : tab.pageFor(number);
    if (!replay && page === followedPage) {
      return;
    }
    const epoch = ++fileFollowEpoch;
    unwatchFile?.();
    unwatchFile = null;
    followedPage = page;
    const reporting =
      /** @type {{onCurrentFile?: (listener: (file: {path: string} | null) => void) => () => void} | null} */ (
        page
      );
    unwatchFile =
      reporting?.onCurrentFile?.((file) => {
        // A tab switch has no file at the top; its explicit address remains the selection.
        if (
          !windowDisposed &&
          epoch === fileFollowEpoch &&
          followedPage === page &&
          currentRow === number &&
          number !== null &&
          file !== null
        ) {
          currentFile = file.path;
          trees.get(number)?.controller.followCurrent(file.path);
        }
      }) ?? null;
  }

  /** Drop the longest-closed trees while keeping expanded trees and the shown page's tree. */
  function trimClosedTrees() {
    const closed = [...trees.keys()].filter((number) => !expansion.isExpanded(number));
    let excess = closed.length - MAX_HELD_TREES;
    for (const number of closed) {
      if (excess <= 0) {
        break;
      }
      if (number !== currentRow) {
        trees.get(number)?.dispose();
        trees.delete(number);
        excess -= 1;
      }
    }
  }

  /**
   * A pull request's tree, made the first time its row opens.
   *
   * @param {number} number
   */
  function treeFor(number) {
    let tree = trees.get(number);
    if (tree === undefined) {
      tree = mountFileTree({
        decorateExternalLink: mb.decorateExternalLink,
        number,
        autoExpandFiles: AUTO_EXPAND_FILES,
        current: number === currentRow ? currentFile : null,
        shown: panelShown,
        scrollRoot: tab.scrollRoot,
        chevron,
        href: (path) => tab.fileHref(number, path),
        request: (method, route, options) =>
          request(mb.perf, method, route, { ...options, signal: options.signal ?? signal }),
        formatTime: (iso) => mb.formatTimestamp(Date.parse(iso) / 1000),
        page: () =>
          /** @type {import("./pull-files-tree.js").FilePage | null} */ (tab.pageFor(number)),
        open: ({ file, replace, jumped }) => {
          void tab.open({ number, tab: "files", file, replace, jumped });
        },
        leave: () => {
          const row = painted.get(number)?.row;
          if (row !== undefined) {
            controller.focused(number);
            row.focus({ preventScroll: true });
          }
        },
        focusedIn: () => {
          if (focusedTree !== null && focusedTree !== number) {
            trees.get(focusedTree)?.controller.cancelWalk();
          }
          focusedTree = number;
        },
      });
      trees.set(number, tree);
      const entry = painted.get(number);
      if (entry !== undefined) {
        tree.attach(entry.item, entry.row);
      }
      trimClosedTrees();
    }
    return tree;
  }

  /**
   * Open or close a row's files.
   *
   * @param {number} number
   * @param {boolean} open
   */
  function setExpanded(number, open) {
    if (open) {
      treeFor(number).controller.expand();
    } else {
      const tree = trees.get(number);
      if (tree !== undefined) {
        tree.controller.collapse();
        // Map order records closing time, rather than the first time a tree was opened.
        trees.delete(number);
        trees.set(number, tree);
      }
      trimClosedTrees();
      if (focusedTree === number) {
        focusedTree = null;
      }
    }
  }

  /**
   * A file address temporarily opens its owner. A PR preview leaves disclosure to the reader.
   *
   * @param {number | null} number
   * @param {string | null} file
   */
  function showFileOwner(number, file) {
    const changes = expansion.shown(number, file);
    for (const closed of changes.collapse) {
      setExpanded(closed, false);
    }
    for (const opened of changes.expand) {
      setExpanded(opened, true);
    }
  }

  /**
   * The row whose page holds the pane: current, and the tree's one selected item.
   *
   * @param {HTMLAnchorElement} row
   * @param {boolean} on
   */
  function markShown(row, on) {
    row.classList.toggle("selected", on);
    if (on) {
      row.setAttribute("aria-current", "page");
      row.setAttribute("aria-selected", String(currentFile === null));
    } else {
      row.removeAttribute("aria-current");
      row.removeAttribute("aria-selected");
    }
  }

  /** @param {PullRow} row */
  function rowAge(row) {
    const parsed = row.updatedAt === null ? Number.NaN : Date.parse(row.updatedAt) / 1000;
    const at = Number.isFinite(parsed) ? parsed : null;
    const when = at === null ? { label: "", className: "" } : mb.formatAge(at);
    return { at, ...when };
  }

  /** @param {PullRow} row @param {HTMLElement} stack */
  function rowMeta(row, stack) {
    return h("span", { class: "github-pulls-meta" }, [
      h("span", { class: "github-pulls-number" }, [`#${row.number}`]),
      " · ",
      authorLabel(row.author, row.avatar, "github-pulls-author"),
      " · ",
      h("span", { class: "github-pulls-refs" }, [
        mb.refChip(row.baseRef, { kind: "remote", copy: "sibling" }),
        " ← ",
        mb.refChip(row.headRef, { label: row.headLabel, kind: "remote", copy: "sibling" }),
      ]),
      stack,
    ]);
  }

  /** Patch a mounted row without detaching its link, expanded files, or focus. */
  /** @param {PaintedRow} entry @param {PullRow} row @param {string} key */
  function patchRow(entry, row, key) {
    const before = entry.info;
    if (row.title !== before.title) {
      entry.title.textContent = row.title;
    }
    if (row.state !== before.state) {
      const icon = pullStateIcon(row.state);
      entry.row.insertBefore(icon, entry.icon);
      entry.icon.remove();
      entry.icon = icon;
    }
    if (row.updatedAt !== before.updatedAt) {
      const when = rowAge(row);
      entry.at = when.at;
      entry.label = when.label;
      entry.age.textContent = when.label;
      entry.age.className = `github-pulls-age ${when.className}`;
      if (when.at === null) {
        entry.age.removeAttribute("data-tip-text");
      } else {
        entry.age.dataset.tipText = mb.formatTimestamp(when.at);
      }
    }
    if (
      row.avatar !== before.avatar ||
      row.meta !== before.meta ||
      row.headRef !== before.headRef
    ) {
      entry.releaseCopies();
      const meta = rowMeta(row, entry.stack);
      entry.row.insertBefore(meta, entry.meta);
      entry.meta.remove();
      entry.meta = meta;
      entry.releaseCopies = mb.mountRefCopies(entry.row, entry.item);
    }
    entry.info = row;
    entry.key = key;
  }

  /**
   * One row's elements. Its text is GitHub's users', so it is only ever text.
   *
   * @param {PullRow} row
   * @param {string} key
   * @returns {PaintedRow}
   */
  function buildRow(row, key) {
    const when = rowAge(row);
    const { at } = when;
    const title = h("span", { class: "github-pulls-title" }, [row.title]);
    const updated = h(
      "span",
      {
        class: `github-pulls-age ${when.className}`,
        ...(at === null ? {} : { "data-tip-text": mb.formatTimestamp(at) }),
      },
      [when.label],
    );
    const stack = h("span", { class: "github-pulls-stack" }, [
      stackCaption(stackIndex, stackIdentity, row.number),
    ]);
    const meta = rowMeta(row, stack);
    const icon = pullStateIcon(row.state);
    // The registry's chevron in the 16px box a folder's takes, since the row is a container.
    const toggle = h("span", { class: "github-pulls-toggle", "aria-hidden": "true" }, [chevron()]);
    // A link, so a new tab and a copied address are the browser's, in the role of a tree's
    // item: its level is the list's one, and `placeRows` tells its place.
    const anchor = /** @type {HTMLAnchorElement} */ (
      h(
        "a",
        {
          class: "github-pulls-row collapsed",
          href: row.href,
          role: "treeitem",
          "aria-level": "1",
          "aria-expanded": "false",
          tabindex: "-1",
        },
        [toggle, icon, title, updated, meta],
      )
    );
    anchor.dataset.number = String(row.number);
    if (row.number === currentRow) {
      markShown(anchor, true);
    }
    if (row.number === anchorRow) {
      anchor.setAttribute("tabindex", "0");
    }
    const item = h("li", { class: "github-pulls-item", role: "none" }, [anchor]);
    // Its files, kept across a row built again for what it shows.
    trees.get(row.number)?.attach(item, anchor);
    return {
      item,
      row: anchor,
      age: updated,
      stack,
      title,
      icon,
      meta,
      info: row,
      key,
      at,
      label: when.label,
      releaseCopies: mb.mountRefCopies(anchor, item),
    };
  }

  /**
   * Retain the logical row order and measurements; only the viewport builds DOM rows.
   *
   * @param {PullRow[]} rows
   */
  function paintRows(rows) {
    paintedRows = rows.slice();
    rowIndices = new Map(rows.map((row, index) => [row.number, index]));
    rowWindow.setRows(rows.map((row) => row.number));
  }

  function visiblePlace() {
    const view = tab.scrollRoot?.getBoundingClientRect();
    if (view === undefined) {
      return null;
    }
    const visible = [...painted.entries()].sort(
      (left, right) => (rowIndices.get(left[0]) ?? 0) - (rowIndices.get(right[0]) ?? 0),
    );
    for (const [number, entry] of visible) {
      const box = entry.item.getBoundingClientRect();
      if (box.bottom > view.top && box.top < view.bottom) {
        return { number, offset: box.top - view.top };
      }
    }
    return null;
  }

  function queueWindow() {
    if (windowDisposed || windowFrame !== null) {
      return;
    }
    windowFrame = window.requestAnimationFrame(() => {
      windowFrame = null;
      paintViewport();
    });
  }

  const rowSizes =
    typeof ResizeObserver === "function"
      ? new ResizeObserver((entries) => {
          let changed = false;
          for (const entry of entries) {
            const number = Number(/** @type {HTMLElement} */ (entry.target).dataset.number);
            const box = entry.borderBoxSize[0];
            if (box !== undefined) {
              changed = rowWindow.measure(number, box.blockSize) || changed;
            }
          }
          if (changed) {
            queueWindow();
          }
        })
      : null;

  function cancelCoreSample() {
    if (coreFrame !== null) {
      window.cancelAnimationFrame(coreFrame);
      coreFrame = null;
    }
    if (coreTimer !== null) {
      window.clearTimeout(coreTimer);
      coreTimer = null;
    }
  }

  function queueCoreSample() {
    cancelCoreSample();
    if (
      windowDisposed ||
      !panelShown ||
      document.visibilityState !== "visible" ||
      tab.scrollRoot === null ||
      typeof window.requestAnimationFrame !== "function"
    ) {
      return;
    }
    coreFrame = window.requestAnimationFrame(() => {
      coreFrame = null;
      // A task after the frame leaves the summaries a paint opportunity. A short quiet
      // period coalesces a moving scroll window before reading its visible headers.
      coreTimer = window.setTimeout(() => {
        coreTimer = null;
        const view = tab.scrollRoot?.getBoundingClientRect();
        if (
          windowDisposed ||
          !panelShown ||
          document.visibilityState !== "visible" ||
          view === undefined ||
          view.bottom <= view.top
        ) {
          return;
        }
        const ordered = [...painted.entries()].sort(
          (left, right) => (rowIndices.get(left[0]) ?? 0) - (rowIndices.get(right[0]) ?? 0),
        );
        const numbers = [];
        for (const [number, entry] of ordered) {
          const row = entry.row.getBoundingClientRect();
          if (row.bottom > row.top && row.bottom > view.top && row.top < view.bottom) {
            numbers.push(number);
          }
        }
        controller.prepareVisible(numbers);
      }, PEEK_MS);
    });
  }

  function clearArrivalFlashes() {
    for (const { row } of painted.values()) {
      row.classList.remove("tree-item-flash-in");
    }
  }

  /** @param {number[]} [arrivals] */
  function paintViewport(arrivals = []) {
    if (windowDisposed) {
      return;
    }
    mb.perf.measure("githubPulls:window", () => paintWindow(arrivals), {
      rows: paintedRows.length,
    });
    queueCoreSample();
  }

  /** @param {number[]} arrivals */
  function paintWindow(arrivals) {
    const view = tab.scrollRoot?.getBoundingClientRect();
    const listTop = view === undefined ? 0 : list.getBoundingClientRect().top;
    const focusBefore =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const active =
      document.activeElement instanceof Element
        ? document.activeElement.closest("li.github-pulls-item")
        : null;
    const focused = active instanceof HTMLElement ? Number(active.dataset.number) : null;
    const protectedRows = [currentRow, anchorRow, focused];
    const pieces = rowWindow.range(
      view === undefined ? 0 : view.top - listTop,
      view === undefined ? DISPLAY_ROWS * 41.5 : view.bottom - listTop,
      protectedRows,
    );
    const wanted = new Set(pieces.filter((part) => part.kind === "row").map((part) => part.number));
    for (const [number, entry] of painted) {
      if (wanted.has(number)) {
        continue;
      }
      rowSizes?.unobserve(entry.item);
      trees.get(number)?.detach();
      entry.releaseCopies();
      entry.item.remove();
      painted.delete(number);
    }
    /** @type {Node[]} */
    const nodes = [];
    const usedGaps = new Set();
    for (const part of pieces) {
      if (part.kind === "gap") {
        const key = `${part.start}:${part.end}`;
        let gap = gaps.get(key);
        if (gap === undefined) {
          gap = h("li", {
            class: "github-pulls-spacer",
            role: "presentation",
            "aria-hidden": "true",
          });
          gaps.set(key, gap);
        }
        gap.style.height = `${part.height}px`;
        usedGaps.add(key);
        nodes.push(gap);
        continue;
      }
      const row = paintedRows[part.index];
      const key = JSON.stringify(row);
      let entry = painted.get(row.number);
      if (entry === undefined) {
        entry = buildRow(row, key);
        entry.item.dataset.number = String(row.number);
        painted.set(row.number, entry);
        rowSizes?.observe(entry.item);
      } else if (entry.key !== key) {
        patchRow(entry, row, key);
      }
      const caption = stackCaption(stackIndex, stackIdentity, row.number);
      if (entry.stack.textContent !== caption) {
        entry.stack.textContent = caption;
      }
      entry.row.setAttribute("aria-posinset", String(part.index + 1));
      entry.row.setAttribute("aria-setsize", String(placedSize));
      nodes.push(entry.item);
    }
    for (const [key, gap] of gaps) {
      if (!usedGaps.has(key)) {
        gap.remove();
        gaps.delete(key);
      }
    }
    // Insert only missing/moved nodes; a focused file inside a retained row stays connected.
    let cursor = list.firstChild;
    for (const node of nodes) {
      if (node === cursor) {
        cursor = cursor.nextSibling;
      } else {
        list.insertBefore(node, cursor);
      }
    }
    if (readingPlace !== null && tab.scrollRoot !== null) {
      const entry = painted.get(readingPlace.number);
      if (entry !== undefined && view !== undefined) {
        const delta = entry.item.getBoundingClientRect().top - view.top - readingPlace.offset;
        if (Math.abs(delta) >= 0.5) {
          tab.scrollRoot.scrollTop += delta;
        }
      }
    }
    if (focusBefore !== null && document.activeElement === document.body) {
      const arriving = focusBefore.isConnected
        ? focusBefore
        : focused === null
          ? null
          : painted.get(focused)?.row;
      arriving?.focus({ preventScroll: true });
    }
    // An arrival only belongs to this paint. Overscan, protected offscreen rows,
    // and later virtualized remounts never get an animation.
    if (
      arrivals.length > 0 &&
      view !== undefined &&
      panelShown &&
      document.visibilityState === "visible"
    ) {
      const top = Math.max(view.top, filters.getBoundingClientRect().bottom);
      for (const number of arrivals) {
        const row = painted.get(number)?.row;
        if (!row?.isConnected) {
          continue;
        }
        const box = row.getBoundingClientRect();
        if (box.bottom > box.top && box.bottom > top && box.top < view.bottom) {
          row.classList.add("tree-item-flash-in");
        }
      }
    }
    readingPlace = visiblePlace();
    for (const number of painted.keys()) {
      const tree = trees.get(number);
      tree?.controller.setShown(panelShown);
      tree?.repaint();
    }
  }

  /** The list's size the rows' places were last told against. */
  let placedSize = -1;

  /**
   * Tell mounted rows their absolute places and the selected filter's exact size. Spacer
   * rows do not enter the accessibility tree; catalog progress need not rebuild PR rows.
   *
   * @param {number} size
   */
  function placeRows(size) {
    placedSize = size;
    for (const [number, entry] of painted) {
      const index = rowIndices.get(number);
      if (index !== undefined) {
        entry.row.setAttribute("aria-posinset", String(index + 1));
      }
      entry.row.setAttribute("aria-setsize", String(size));
    }
  }

  /**
   * An age is told as of a moment, and a list that does not change keeps its rows: so, at most
   * once a minute, a paint tells each row's age again, and changes only the ones that moved.
   */
  function tellAges() {
    const minute = Math.floor(Date.now() / 60_000);
    if (minute === agedIn) {
      return;
    }
    agedIn = minute;
    for (const entry of painted.values()) {
      if (entry.at === null) {
        continue;
      }
      const { label, className } = mb.formatAge(entry.at);
      if (label !== entry.label) {
        entry.label = label;
        entry.age.textContent = label;
        entry.age.className = `github-pulls-age ${className}`;
      }
    }
  }

  /** @param {PullsModel} model @param {number[]} arrivals */
  function paint(model, arrivals) {
    // A filter's rows are their own list: nothing is kept across a change of filter.
    if (list.dataset.filter !== model.filter) {
      atEnd?.takeRecords();
      list.dataset.filter = model.filter;
      for (const [number, entry] of painted) {
        rowSizes?.unobserve(entry.item);
        entry.releaseCopies();
        trees.get(number)?.detach();
      }
      painted.clear();
      paintedRows = [];
      gaps.clear();
      readingPlace = null;
      list.replaceChildren();
      paintedVersion = -1;
      for (const chip of filters.querySelectorAll("button")) {
        const on = chip.dataset.chipValue === model.filter;
        chip.setAttribute("aria-checked", String(on));
        chip.tabIndex = on ? 0 : -1;
      }
    }
    if (arrivals.length > 0 && (tab.scrollRoot?.scrollTop ?? 0) <= 0) {
      readingPlace = null;
    }
    if (model.rowsVersion !== paintedVersion) {
      paintedVersion = model.rowsVersion;
      paintRows(model.rows);
      placeRows(model.setSize);
    } else if (model.setSize !== placedSize) {
      placeRows(model.setSize);
    }
    for (const { chip, value, tally } of tallies) {
      const count = model.filterTotals?.[value] ?? null;
      const pending = count === null && model.connection?.state === "working";
      tally.classList.toggle("tally-pending", pending);
      tally.classList.toggle("tally-pending-narrow", pending);
      const text = count === null ? (pending ? "" : "—") : count.toLocaleString("en-US");
      if (tally.textContent !== text) {
        tally.textContent = text;
      }
      const description =
        count === null ? (pending ? "count pending" : "count unavailable") : pullsCount(count);
      const label = `${LIST_LABELS[value]}, ${description}`;
      if (chip.getAttribute("aria-label") !== label) {
        chip.setAttribute("aria-label", label);
      }
    }
    tellAges();
    list.setAttribute("aria-label", model.listName);
    list.hidden = model.rows.length === 0;
    const lines = [];
    if (model.repository !== null) {
      const repository = h("strong", { class: "github-pulls-total" }, [model.repository]);
      lines.push(
        h(
          "span",
          { class: "github-pulls-total-line" },
          model.countNumber === null || model.countSuffix === null
            ? [repository]
            : [
                h("strong", { class: "github-pulls-total" }, [model.countNumber]),
                model.countSuffix,
                repository,
              ],
        ),
      );
    }
    if (model.window !== null) {
      lines.push(h("span", { class: "github-pulls-window" }, [model.window]));
    }
    status.replaceChildren(...lines);
    status.hidden = lines.length === 0;
    const connected = model.connection;
    const working = connected?.state === "working";
    const retrying = connected?.retrying === true;
    connection.hidden = connected === null;
    connectionText.classList.toggle("mb-delayed-loading", working);
    spinner.classList.toggle("mb-delayed-loading", retrying);
    spinner.hidden = !working && !retrying;
    const message = connected?.text ?? "";
    if (connectionMessage.textContent !== message) {
      connectionMessage.textContent = message;
    }
    reloadButton.setAttribute("aria-disabled", String(connected?.reload !== true));
    const help = connected?.help ?? "";
    if (connectionHelp.dataset.help !== help) {
      connectionHelp.dataset.help = help;
      connectionHelp.hidden = help === "";
      connectionHelp.replaceChildren(
        ...(help === ""
          ? []
          : [
              mb.decorateExternalLink(
                h(
                  "a",
                  { href: "https://cli.github.com/", target: "_blank", rel: "noopener noreferrer" },
                  [help === "install" ? "Install GitHub CLI" : "Update GitHub CLI"],
                ),
              ),
            ]),
      );
    }
    empty.textContent = model.empty ?? "";
    empty.hidden = model.empty === null;
    const footChildren = [];
    if (model.loadMore !== null) {
      moreButton.disabled = model.loadMore === "loading";
      moreButton.setAttribute("aria-busy", String(moreButton.disabled));
      footChildren.push(moreButton);
    }
    if (model.github !== null) {
      footChildren.push(
        mb.decorateExternalLink(
          h("a", { href: model.github, target: "_blank", rel: "noopener noreferrer" }, [
            "See the rest on GitHub",
          ]),
        ),
      );
    }
    const sameFoot =
      foot.childNodes.length === footChildren.length &&
      footChildren.every((node, index) => foot.childNodes[index] === node);
    if (!sameFoot) {
      foot.replaceChildren(...footChildren);
    }
    if (live.textContent !== model.live) {
      live.textContent = model.live;
    }
    paintViewport(arrivals);
  }

  const listening = new AbortController();
  const { signal } = listening;
  nav.scrollRoot?.addEventListener(
    "scroll",
    () => {
      readingPlace = visiblePlace();
      queueWindow();
    },
    { passive: true, signal },
  );

  // A key moved the focus, and not a reader arriving at a row: a walk reads nothing per row.
  let movingFocus = false;

  const controller = createPullsController(
    {
      request: (method, route, options) =>
        request(mb.perf, method, route, { ...options, signal: options.signal ?? signal }),
      schedule: (callback, delayMs) => window.setTimeout(callback, delayMs),
      cancel: (handle) => window.clearTimeout(/** @type {number} */ (handle)),
      recheckTail() {
        // Ask the observer for the current position after a blocker clears. Its next
        // delivery uses the laid-out footer, even if there was no new crossing.
        atEnd?.takeRecords();
        atEnd?.disconnect();
        atEnd?.observe(foot);
      },
      now: () => Date.now(),
      isVisible: () => document.visibilityState === "visible",
      isOnline: () => window.navigator?.onLine !== false,
      formatTime: (iso) => mb.formatTimestamp(Date.parse(iso) / 1000),
      render(model, identity, arrivals) {
        stackIdentity = identity;
        mb.perf.measure("githubPulls:render", () => paint(model, arrivals), {
          rows: model.rows.length,
        });
        if (windowDisposed) {
          return;
        }
        // Completion markers describe committed DOM, including hidden panels, not paint.
        // Their first_end_ms is a navigation-relative boundary, not the marker's duration.
        if (model.rows.length > 0) {
          mb.perf.measure("githubPulls:rowsReady", () => {}, { rows: model.rows.length });
        }
        if (model.countNumber !== null && model.catalogReady) {
          mb.perf.measure("githubPulls:catalogReady", () => {});
        }
      },
      markCurrent(previous, next) {
        // The roving anchor and reader expansion remain; only the old page's mark leaves.
        if (previous !== null && previous !== next) {
          trees.get(previous)?.controller.setCurrent(null);
        }
        currentRow = next;
        const leaving = previous === null ? undefined : painted.get(previous)?.row;
        if (leaving !== undefined) {
          markShown(leaving, false);
        }
        const arriving = next === null ? undefined : painted.get(next)?.row;
        if (arriving !== undefined) {
          markShown(arriving, true);
        }
      },
      markAnchor(previous, next, focus) {
        anchorRow = next;
        paintViewport();
        if (previous !== null) {
          painted.get(previous)?.row.setAttribute("tabindex", "-1");
        }
        if (next !== null) {
          const row = painted.get(next)?.row;
          row?.setAttribute("tabindex", "0");
          if (focus && row) {
            movingFocus = true;
            row.focus({ preventScroll: true });
            movingFocus = false;
            row.scrollIntoView({ block: "nearest" });
          }
        }
      },
      reveal(number) {
        paintViewport();
        painted.get(number)?.row.scrollIntoView({ block: "nearest" });
      },
      open: (route) => nav.open(route),
      filterChanged: (state) => nav.filterChanged(state),
    },
    { filter: nav.filter, current: nav.current, checkout: nav.checkout === true },
  );

  const unbindFilters = controls.bind(filters, {
    onChange(key, value, select) {
      if (key === FILTER_GROUP && select === "one") {
        controller.setFilter(String(value));
      }
    },
  });

  /** @param {EventTarget | null} target */
  const rowOf = (target) =>
    target instanceof Element
      ? /** @type {HTMLAnchorElement | null} */ (target.closest("a.github-pulls-row"))
      : null;

  list.addEventListener(
    "click",
    (event) => {
      const row = rowOf(event.target);
      // A new tab and a copied address are the browser's own.
      if (row !== null && isPlainClick(event)) {
        event.preventDefault();
        const number = Number(row.dataset.number);
        // One gesture, as a folder's in the Files tab: it opens the pull request and toggles
        // its files.
        setExpanded(number, expansion.toggle(number));
        controller.activate(number);
      }
    },
    { signal },
  );
  list.addEventListener(
    "focusin",
    (event) => {
      const row = rowOf(event.target);
      if (row !== null && !movingFocus) {
        const number = Number(row.dataset.number);
        controller.focused(number);
        controller.peek(number);
      }
    },
    { signal },
  );
  /** @type {number | undefined} */
  let peekTimer;
  list.addEventListener(
    "pointerover",
    (event) => {
      const row = rowOf(event.target);
      if (row === null) {
        return;
      }
      // Cut short by an ellipsis, a row's tooltip carries the whole of it.
      for (const part of row.querySelectorAll(".github-pulls-title, .github-pulls-meta")) {
        if (part instanceof HTMLElement) {
          if (part.scrollWidth > part.clientWidth) {
            part.dataset.tipText = part.textContent ?? "";
          } else {
            delete part.dataset.tipText;
          }
        }
      }
      window.clearTimeout(peekTimer);
      const number = Number(row.dataset.number);
      peekTimer = window.setTimeout(() => controller.peek(number), PEEK_MS);
    },
    { signal },
  );
  list.addEventListener("pointerout", () => window.clearTimeout(peekTimer), { signal });
  list.addEventListener(
    "animationend",
    (event) => {
      if (event.animationName === "tree-row-flash-in" && event.target instanceof HTMLElement) {
        event.target.classList.remove("tree-item-flash-in");
      }
    },
    { signal },
  );
  document.addEventListener(
    "visibilitychange",
    () => {
      controller.onVisibilityChange();
      if (document.visibilityState === "visible") {
        queueWindow();
      } else {
        cancelCoreSample();
        clearArrivalFlashes();
      }
    },
    { signal },
  );

  window.addEventListener("focus", controller.onFocus, { signal });
  window.addEventListener("online", controller.onOnline, { signal });
  window.addEventListener("offline", controller.onOffline, { signal });
  window.addEventListener(
    "pagehide",
    () => {
      controller.pause();
      clearArrivalFlashes();
    },
    { signal },
  );
  window.addEventListener("pageshow", controller.resume, { signal });

  // Observe the tail of the full displayed prefix, including virtual spacer rows.
  const atEnd =
    nav.scrollRoot !== null && typeof IntersectionObserver === "function"
      ? new IntersectionObserver(
          (entries) => {
            if (entries.some((entry) => entry.isIntersecting)) {
              void controller.reachedEnd();
            }
          },
          { root: nav.scrollRoot, rootMargin: `0px 0px ${PAGE_AHEAD_PX}px 0px` },
        )
      : null;
  atEnd?.observe(foot);
  document.addEventListener(
    "visibilitychange",
    () => {
      for (const tree of trees.values()) {
        tree.controller.onVisibilityChange();
      }
    },
    { signal },
  );
  // A tree that opens, closes, or fills moves every tree below it: each draws what is in view.
  const moved =
    typeof ResizeObserver === "function"
      ? new ResizeObserver(() => {
          repaintTrees();
          queueWindow();
        })
      : null;
  moved?.observe(list);
  if (tab.scrollRoot !== null) {
    moved?.observe(tab.scrollRoot);
  }
  function repaintTrees() {
    for (const number of painted.keys()) {
      trees.get(number)?.repaint();
    }
  }

  /** The tree a file row with focus is in. */
  const focused = () => (focusedTree === null ? undefined : trees.get(focusedTree)?.controller);

  const stacks = watchStacks((index) => {
    const hadMembership = stackIndex.byPull.size > 0;
    stackIndex = index;
    if (!windowDisposed && painted.size > 0 && (hadMembership || index.byPull.size > 0)) {
      queueWindow();
    }
  }, nav.shown);
  void controller.start({ shown: nav.shown, refreshAhead: nav.refreshAhead });
  showFileOwner(nav.current, nav.file ?? null);
  const unwatchPage = tab.onPageChange(followCurrentFile);
  followCurrentFile();

  return Object.freeze({
    /** @param {boolean} visible */
    setShown(visible) {
      panelShown = visible;
      stacks.setShown(visible);
      controller.setShown(visible);
      if (visible) {
        queueWindow();
      } else {
        cancelCoreSample();
        // Hiding the tab cancels its animations without an animationend event.
        clearArrivalFlashes();
      }
      for (const [number, tree] of trees) {
        tree.controller.setShown(visible && painted.has(number));
      }
    },
    /**
     * The address names a pull request's page, and maybe one file of it.
     *
     * @param {number | null} number
     * @param {string | null} [file]
     * @param {{preserveScroll?: boolean}} [options]
     */
    setCurrent(number, file = null, options) {
      if (currentRow !== null && currentRow !== number) {
        trees.get(currentRow)?.controller.cancelWalk();
      }
      if (focusedTree !== null && focusedTree !== number) {
        trees.get(focusedTree)?.controller.cancelWalk();
      }
      controller.setCurrent(number, options);
      currentFile = file;
      const row = number === null ? undefined : painted.get(number)?.row;
      if (row !== undefined) {
        markShown(row, true);
      }
      showFileOwner(number, file);
      if (number !== null) {
        trees.get(number)?.controller.setCurrent(file);
      }
      // An explicit file wins until its jump reports. A PR-only address can replay the
      // same page's observation instead of erasing it on a duplicate route notification.
      followCurrentFile(file === null);
    },
    setFilter: (/** @type {string} */ state) => controller.setFilter(state, { fromAddress: true }),
    move: controller.move,
    released() {
      controller.released();
      focused()?.released();
    },
    activateAnchor: controller.activateAnchor,
    /** Right on a pull request's row: its files open, or focus goes to the first. */
    expand() {
      const number = controller.snapshot().anchor;
      if (number === null) {
        return false;
      }
      if (expansion.expand(number)) {
        setExpanded(number, true);
      } else if (!treeFor(number).controller.enter()) {
        setExpanded(number, true);
      }
      return true;
    },
    /** Left on a pull request's row: its files close. */
    collapse() {
      const number = controller.snapshot().anchor;
      if (number !== null && expansion.collapse(number)) {
        setExpanded(number, false);
      }
      return number !== null;
    },
    /** @param {-1 | 1} delta @param {{repeat?: boolean}} [how] */
    moveFile: (delta, how) => focused()?.move(delta, how) ?? false,
    fileLeft: () => focused()?.left() ?? false,
    fileRight: () => focused()?.right() ?? false,
    activateFile: () => focused()?.activateAnchor() ?? false,
    dispose() {
      windowDisposed = true;
      cancelCoreSample();
      if (windowFrame !== null) {
        window.cancelAnimationFrame(windowFrame);
      }
      rowSizes?.disconnect();
      gaps.clear();
      listening.abort();
      atEnd?.disconnect();
      moved?.disconnect();
      unwatchPage();
      unwatchFile?.();
      window.clearTimeout(peekTimer);
      unbindFilters();
      stacks.dispose();
      controller.dispose();
      for (const tree of trees.values()) {
        tree.dispose();
      }
      trees.clear();
      for (const entry of painted.values()) {
        entry.releaseCopies();
      }
      painted.clear();
      container.classList.remove("github-pulls");
      container.replaceChildren();
    },
  });
}

/** @param {HTMLElement} container */
export function mountPullsLanding(container) {
  container.setAttribute("data-preview-empty", "");
  container.replaceChildren(h("div", { class: "preview-empty" }, ["Select a pull request."]));
}
