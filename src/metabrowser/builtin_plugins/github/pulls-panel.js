// The Pulls tab's list: every pull request of the repository, newest first, each with its
// state's icon, from the cache at once while the backend fills its lightweight catalog.
//
// Every decision lives here without a DOM. `describePulls` turns one list's envelope and
// rows into what the panel shows; `createPullsController` owns the filters, the windows of
// rows, bounded cached windows, polling only while shown and prioritizing metadata fetches,
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
// `GET` never does. A list's refresh is asked for while the panel is shown, which the server
// holds to one attempt a window; an accepted catalog job continues while hidden. A row's
// record is read when the reader stops on it: that
// read is local and runs no gh, and only a page opened by a reader's selection asks to fetch
// a record the cache lacks. A key held down selects rows and opens only the one it stops on,
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
const VISIBLE_CORE_LIMIT = 8;
const CORE_CONTROL_TIMEOUT_MS = 2000;
export const CORE_BUSY_RETRY_MS = 1000;

export const LISTS = Object.freeze(["open", "closed", "all"]);
const LIST_LABELS = Object.freeze({ all: "All", open: "Open", closed: "Closed" });
const FILTER_GROUP = "github-pulls-filter";

// Catalog cache reads remain one provider page. The backend may cache every PR;
// the controller initially materializes500 and only explicit Fetch more grows it.
// The paint independently mounts a variable-height viewport and protected anchors.
export const WINDOW_ROWS = 100;
export const DISPLAY_ROWS = 500;
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
  gh_missing:
    "Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, then run gh auth login --hostname github.com.",
  gh_too_old:
    "This GitHub CLI cannot report the active account. Update gh from https://cli.github.com/, then run gh auth status --hostname github.com.",
  not_logged_in:
    "GitHub CLI is not signed in to github.com. Run gh auth login --hostname github.com, then retry.",
  network_error: "Offline, or GitHub could not be reached. The list is as it was last fetched.",
  not_found_or_private:
    "The repository was not found, or the signed-in account cannot read its pull requests.",
});

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
 *   fetching: string | null,
 *   progress: string | null,
 *   freshness: string | null,
 *   empty: string | null,
 *   notice: {severity: "warning" | "error", text: string, retry: boolean, help?: "install" | "update"} | null,
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
 * What a list's last refresh says to a reader, or null when it says nothing to them: one
 * that succeeded, or one still running.
 *
 * @param {PullsEnvelope} envelope
 * @param {(iso: string) => string} formatTime
 * @returns {{text: string, retry: boolean, help?: "install" | "update"} | null}
 */
export function refreshFailure(envelope, formatTime) {
  const last = envelope.last_refresh;
  if (last === null || last.outcome === "succeeded" || envelope.refreshing) {
    return null;
  }
  if (last.outcome === "rate_limited") {
    // A reader's Retry is held too: each request GitHub refuses moves the time on.
    return {
      text:
        last.reset_at === null
          ? "GitHub's rate limit was reached. No automatic attempt runs until it lifts."
          : `GitHub's rate limit lifts at ${formatTime(last.reset_at)}. No automatic attempt runs before then.`,
      retry: false,
    };
  }
  // What the job recorded is a clause; here it stands as a status sentence of its own.
  const setup = ["gh_missing", "gh_too_old", "not_logged_in"].includes(last.outcome);
  const said = setup
    ? (last.message ?? FAILURES[last.outcome])
    : (FAILURES[last.outcome] ?? last.message ?? last.outcome.replaceAll("_", " "));
  const sentence = `${said.charAt(0).toUpperCase()}${said.slice(1)}`;
  const help =
    last.outcome === "gh_missing"
      ? "install"
      : last.outcome === "gh_too_old"
        ? "update"
        : undefined;
  const message = sentence.endsWith(".") ? sentence : `${sentence}.`;
  return {
    text:
      message + (setup ? " You can still browse local files and any cached pull requests." : ""),
    retry: true,
    ...(help === undefined ? {} : { help }),
  };
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
    fetching: null,
    progress: null,
    freshness: null,
    empty: null,
    notice: null,
    loadMore: null,
    github: null,
    live: "",
  };
  if (envelope === null) {
    model.status = page.error === null ? "loading" : "unavailable";
    model.fetching = page.error === null ? FETCHING : null;
    model.notice =
      page.error === null ? null : { severity: "error", text: page.error, retry: false };
    model.live = page.error ?? FETCHING;
    return model;
  }
  model.status = envelope.state;
  const repository = repositoryName(envelope.source);
  const failure = refreshFailure(envelope, page.formatTime);
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
  const catalogPending =
    envelope.refreshing || envelope.state === "pending" || envelope.state === "absent";
  // Fetch more can still page through the cache after a provider failure.
  if (page.error === null && (page.more || (catalogPending && failure === null))) {
    model.fetching = FETCHING;
  }
  if (model.fetching === null && !envelope.complete && envelope.catalog_fetched > 0) {
    model.progress =
      envelope.catalog_fetched === envelope.repository_total
        ? "Catalog paused"
        : `Catalog paused · ${new Intl.NumberFormat("en-US").format(envelope.catalog_fetched)} cached`;
  }
  const name = repository === null ? "Pull requests" : `Pull requests of ${repository}`;
  if (envelope.state === "current" || envelope.state === "stale") {
    model.listName = `${name}: ${pullsCount(envelope.total ?? envelope.fetched)}`;
    if (model.fetching === null) {
      const reader = text(envelope.reader).replace(/^gh:/, "");
      const age = relativeAge(envelope.count_at ?? envelope.fetched_at, page.nowMs);
      const stale = envelope.state === "stale" ? " · may be out of date" : "";
      model.freshness = `PRs fetched ${age}${reader === "" ? "" : ` by ${reader}`}${stale}`;
    }
    if (envelope.total === 0 || (envelope.fetched === 0 && envelope.complete)) {
      model.empty =
        page.filter === "all" ? "No pull requests." : `No ${page.filter} pull requests.`;
    }
    model.live = model.listName;
  } else {
    model.listName = name;
  }
  if (model.fetching !== null) {
    // Polls update the display without announcing each step of the same fetch.
    model.live = model.fetching;
  }
  if (failure !== null) {
    model.notice = { severity: "warning", ...failure };
    model.live = model.fetching ?? failure.text;
  } else if (envelope.truncated) {
    model.notice = {
      severity: "warning",
      text: "Some rows were cut to fit, or could not be read.",
      retry: false,
    };
  }
  if (page.error !== null) {
    model.notice = { severity: "error", text: page.error, retry: false };
    model.live = page.error;
  }
  if (page.more) {
    model.loadMore = "loading";
  } else if (holding && envelope.total !== null && page.rows.length < envelope.total) {
    model.loadMore = "ready";
  }
  return model;
}

/**
 * What the pane says at the list's own address, `/pulls`: nothing is selected, as on GitHub,
 * or there is nothing to list. A list with no rows has nothing to select, so the pane says
 * what the tab's notice says: why, when a refresh failed. Pure.
 *
 * @param {PullsEnvelope | null} envelope
 * @param {(iso: string) => string} formatTime
 * @param {boolean} [checkout] A checkout served as a folder.
 * @returns {string}
 */
export function describeLanding(envelope, formatTime, checkout = false) {
  if (envelope?.reason === "not_github") {
    return checkout ? CHECKOUT_NOT_LISTED : NO_GITHUB;
  }
  const failure = envelope === null ? null : refreshFailure(envelope, formatTime);
  if (envelope !== null && envelope.fetched === 0 && failure !== null) {
    return failure.text;
  }
  if (envelope?.repository_total === 0 && envelope.complete) {
    return "No pull requests.";
  }
  return "Select a pull request.";
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
 * @typedef {{key: string, epoch: number, body: CoreWindowRequest, canRetry: boolean}} CoreDemand
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
 *   formatTime(iso: string): string,
 *   render(model: PullsModel, identity: import("./pull-stacks.js").StackIdentity | null): void,
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
 * }} PullsDependencies
 */

/**
 * A list as far as it has been read. *etag* is the route's tag for the list's top window,
 * which every poll asks for, and *content* says which list file the rows held were read from.
 *
 * @typedef {{
 *   envelope: PullsEnvelope | null,
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
  // The panel's first read may start the refresh though it is not shown: see `start`.
  let readAhead = false;
  /** @type {unknown} */
  let timer = null;
  /** @type {AbortController | null} */
  let inflight = null;
  // A request's answer counts only for the newest request of its list: a slow poll sent before
  // a refresh started must not replace the refresh's answer when it lands after it.
  let sent = 0;
  let shownRequest = 0;
  let requestEpoch = 0;
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
  // Counts describe the repository, so switching filters keeps the last accepted tallies.
  /** @type {PullFilterTotals | null} */
  let filterTotals = null;

  /** @returns {HeldList} */
  function held() {
    return /** @type {HeldList} */ (lists.get(filter));
  }

  function live() {
    return shown && !disposed && deps.isVisible();
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
        const receipt = /** @type {{preparation?: string} | null | undefined} */ (response?.body);
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
          live() &&
          walkingTo === null
        ) {
          // Keep both the requested token and its predecessor while the server is busy.
          demand.canRetry = false;
          coreRetryTimer = deps.schedule(() => {
            coreRetryTimer = null;
            if (coreWanted === demand && live() && walkingTo === null) {
              coreSent = null;
              void sendCoreWindow();
            }
          }, CORE_BUSY_RETRY_MS);
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

  /** @param {number[]} numbers */
  function prepareVisible(numbers) {
    if (!live() || walkingTo !== null) {
      return;
    }
    const list = held();
    const generation = list.envelope?.generation;
    if (typeof generation !== "string" || list.content === null) {
      return;
    }
    const rows = numbers.slice(0, VISIBLE_CORE_LIMIT).flatMap((number) => {
      const index = list.keys.get(number);
      return index === undefined ? [] : [list.rows[index]];
    });
    if (rows.length === 0) {
      clearCoreWindow();
      return;
    }
    const key = JSON.stringify([list.content, rows.map((row) => [row.number, row.updatedAt])]);
    if (coreWanted?.key === key) {
      return;
    }
    cancelCoreRetry();
    // getRandomValues also works when serving trusted-network plain HTTP.
    const id = Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
      byte.toString(16).padStart(2, "0"),
    ).join("");
    coreWanted = {
      key,
      epoch: coreEpoch,
      canRetry: true,
      body: {
        state: filter,
        window: { id, generation },
        numbers: rows.map((row) => row.number),
      },
    };
    void sendCoreWindow();
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
    });
  }

  // Compared without its rows, which their version stands for: an unchanged list costs a
  // string of its envelope, and not of its thousand rows.
  function render() {
    if (disposed) {
      return;
    }
    const next = model();
    const envelope = held().envelope;
    const identity =
      envelope === null ? null : { source: envelope.source, reader: envelope.reader };
    const key = JSON.stringify([{ ...next, rows: null }, identity, held().content]);
    if (key !== painted) {
      painted = key;
      deps.render(next, identity);
    }
  }

  function clearTimer() {
    if (timer !== null) {
      deps.cancel(timer);
      timer = null;
    }
  }

  function scheduleNext() {
    clearTimer();
    if (!live()) {
      return;
    }
    const envelope = held().envelope;
    const fast = envelope === null || envelope.refreshing || envelope.state === "pending";
    timer = deps.schedule(
      () => {
        timer = null;
        void poll();
      },
      fast ? FAST_POLL_MS : SLOW_POLL_MS,
    );
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
    list.error = null;
    shownRequest = request;
    filterTotals = envelope.filter_totals ?? null;
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
      const response = await deps.request(
        "GET",
        `${PULLS_ROUTE}?state=${name}&limit=${WINDOW_ROWS}&after=${after}`,
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
   * Read the list's top window: the route's tag says whether anything changed, so a poll of
   * an unchanged list is a 304 however many rows are held. Catalog counts and older-page
   * progress keep the held prefix. A new generation stages that prefix in bounded pages.
   *
   * @param {boolean} [first] The panel's first read of this list, which a panel not shown
   *   still takes, so it opens with its rows.
   */
  async function poll(first = false) {
    if (disposed || polling || (!first && !live())) {
      return;
    }
    const name = filter;
    const list = held();
    polling = true;
    const request = ++sent;
    const epoch = requestEpoch;
    const controller = new AbortController();
    inflight = controller;
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
          const coherent =
            content === list.content ||
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
            list.etag = response.etag;
            if (
              list.nextAfter === null &&
              list.rows.length < Math.min(list.displayLimit, response.body.fetched)
            ) {
              list.nextAfter = list.rows.at(-1)?.number ?? null;
            }
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
      } else if (!pinChanged(response)) {
        list.error = `The list is unavailable (HTTP ${response.status}).`;
      }
    } catch {
      if (disposed || request < shownRequest || name !== filter || controller.signal.aborted) {
        return;
      }
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
    render();
    if (first && revealCurrent && current !== null && list.keys.has(current)) {
      deps.reveal(current);
    }
    chaseCurrent();
    // Fill the reader's display budget from cached metadata, independently of provider paging.
    if (list.nextAfter !== null && list.rows.length < list.displayLimit) {
      await loadWindow();
    }
    scheduleNext();
    askIfDue();
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
      !deps.isVisible() ||
      envelope === null ||
      envelope.reason === "not_github"
    ) {
      return;
    }
    const target = Math.min(list.displayLimit, envelope.total ?? list.displayLimit);
    const needsRows = envelope.fetched < target && list.priorityTarget < target;
    const needsCatalog = !envelope.complete && !envelope.refreshing;
    if (
      !needsRows &&
      !needsCatalog &&
      (envelope.refreshing || (envelope.state !== "absent" && envelope.state !== "stale"))
    ) {
      return;
    }
    const windowMs = envelope.fresh_for_s * 1000;
    if (!needsRows && list.askedAt !== null && deps.now() - list.askedAt < windowMs) {
      return;
    }
    list.askedAt = deps.now();
    list.priorityTarget = target;
    void ask({ state: filter, target: list.displayLimit });
  }

  /**
   * Send a refresh and take the envelope it answers with. The answer has no rows.
   *
   * @param {{state: string, target: number, retry?: boolean}} body
   */
  async function ask(body) {
    const name = body.state;
    const list = /** @type {HeldList} */ (lists.get(name));
    const request = ++sent;
    const reader = body.retry === true || list.more;
    const epoch = requestEpoch;
    const controller = new AbortController();
    refreshReads.add(controller);
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
    let advanced = false;
    try {
      const response = await deps.request(
        "GET",
        `${PULLS_ROUTE}?state=${name}&limit=${WINDOW_ROWS}&after=${after}`,
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
      }
    } catch {
      if (!disposed && epoch === requestEpoch && !controller.signal.aborted) {
        list.error = "The server did not answer.";
      }
    } finally {
      if (windowRead === controller) {
        windowRead = null;
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
        list.nextAfter === null &&
        list.envelope !== null &&
        list.rows.length < Math.min(list.displayLimit, list.envelope.total ?? list.displayLimit) &&
        list.priorityTarget < list.displayLimit
      ) {
        list.priorityTarget = list.displayLimit;
        await ask({ state: name, target: list.displayLimit });
      }
    }
  }

  /**
   * Read cached rows within the display budget. A button grows it by500 and can
   * prioritize metadata that the background catalog walk has not reached yet.
   * @param {boolean} retrying
   */
  function next(retrying) {
    const list = held();
    const envelope = list.envelope;
    if (disposed || envelope === null) {
      return Promise.resolve();
    }
    if (retrying) {
      if (envelope.total !== null && list.rows.length >= envelope.total) {
        return Promise.resolve();
      }
      list.displayLimit += DISPLAY_ROWS;
      list.more = true;
      render();
    }
    if (list.nextAfter !== null && list.rows.length < list.displayLimit) {
      return loadWindow();
    }
    if (
      retrying &&
      (envelope.total === null || envelope.fetched < Math.min(list.displayLimit, envelope.total))
    ) {
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
    clearCoreWindow();
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
     * The panel's first read, shown or not: a mirror reads it ahead of the tab, once the first
     * tree has settled, and starts its refresh then too (*refreshAhead*).
     *
     * @param {{shown?: boolean, refreshAhead?: boolean}} [how]
     */
    start(how = {}) {
      shown = how.shown === true;
      readAhead = how.refreshAhead === true;
      render();
      return poll(true);
    },
    /** @param {boolean} visible */
    setShown(visible) {
      if (disposed || visible === shown) {
        return;
      }
      shown = visible;
      if (!visible) {
        clearTimer();
        cancelReads();
        return;
      }
      if (revealCurrent && current !== null && held().keys.has(current)) {
        deps.reveal(current);
      }
      void poll();
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
        void next(false);
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
    /** A press of Load more. */
    loadMore: () => next(true),
    /** The end of the list came into view. */
    reachedEnd: () => next(false),
    /** A press of Retry. */
    retry() {
      if (disposed) {
        return Promise.resolve();
      }
      held().error = null;
      return ask({ state: filter, target: held().displayLimit, retry: true });
    },
    onVisibilityChange() {
      if (disposed) {
        return;
      }
      if (!deps.isVisible()) {
        clearTimer();
        cancelReads();
        return;
      }
      void poll();
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
      timer:
        timer === null
          ? null
          : held().envelope === null ||
              held().envelope?.refreshing ||
              held().envelope?.state === "pending"
            ? "fast"
            : "slow",
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
  const notice = h("div", { class: "github-pulls-notice-host" });
  // A tree: a row's changed files hang off it as a group. Its keys are this view's, bound by
  // the tab's host; the Files tree's keyboard handler is scoped to the Files tab and never
  // sees these rows.
  const list = h("ul", { class: "github-pulls-list", role: "tree" });
  const empty = h("p", { class: "github-pulls-empty" });
  const fetchLabel = h("span");
  // The live region announces the same activity once, including across polling updates.
  const activity = h(
    "p",
    { class: "github-pulls-activity mb-delayed-loading", "aria-hidden": "true", hidden: "" },
    [h("span", { class: "spinner spinner-sm" }), fetchLabel],
  );
  const foot = h("div", { class: "github-pulls-foot" });
  const moreButton = /** @type {HTMLButtonElement} */ (
    h("button", { type: "button", class: "btn github-pulls-more" }, ["Fetch more"])
  );
  moreButton.addEventListener("click", () => void controller.loadMore());
  const live = h("span", { class: "sr-only", "aria-live": "polite" });
  container.classList.add("github-pulls");
  container.replaceChildren(filters, status, activity, notice, list, empty, foot, live);

  /**
   * What is painted of each row held, by number: its elements, the key of what it shows, and
   * when it was updated, whose age moves on while the row stays.
   *
   * @typedef {{
   *   item: HTMLElement,
   *   row: HTMLAnchorElement,
   *   age: HTMLElement,
   *   stack: HTMLElement,
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
          showPage(number);
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
   * @param {boolean} reader A reader's own click or key, which may ask GitHub for the list.
   */
  function setExpanded(number, open, reader) {
    if (open) {
      treeFor(number).controller.expand({ reader });
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
   * The page of *number* holds the pane, or none does: its row opens, and the one before it
   * closes again if only its page had opened it.
   *
   * @param {number | null} number
   */
  function showPage(number) {
    const changes = expansion.shown(number);
    for (const closed of changes.collapse) {
      setExpanded(closed, false, false);
    }
    for (const opened of changes.expand) {
      setExpanded(opened, true, false);
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

  /**
   * One row's elements. Its text is GitHub's users', so it is only ever text.
   *
   * @param {PullRow} row
   * @param {string} key
   * @returns {PaintedRow}
   */
  function buildRow(row, key) {
    const parsed = row.updatedAt === null ? Number.NaN : Date.parse(row.updatedAt) / 1000;
    const at = Number.isFinite(parsed) ? parsed : null;
    const when = at === null ? { label: "", className: "" } : mb.formatAge(at);
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
    const meta = h("span", { class: "github-pulls-meta" }, [
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
        [toggle, pullStateIcon(row.state), title, updated, meta],
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
            if (numbers.length === VISIBLE_CORE_LIMIT) {
              break;
            }
          }
        }
        controller.prepareVisible(numbers);
      }, PEEK_MS);
    });
  }

  function paintViewport() {
    if (windowDisposed) {
      return;
    }
    mb.perf.measure("githubPulls:window", paintWindow, { rows: paintedRows.length });
    queueCoreSample();
  }

  function paintWindow() {
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
      if (entry === undefined || entry.key !== key) {
        if (entry !== undefined) {
          rowSizes?.unobserve(entry.item);
          entry.releaseCopies();
          entry.item.remove();
        }
        entry = buildRow(row, key);
        entry.item.dataset.number = String(row.number);
        painted.set(row.number, entry);
        rowSizes?.observe(entry.item);
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

  /** @param {PullsModel} model */
  function paint(model) {
    // A filter's rows are their own list: nothing is kept across a change of filter.
    if (list.dataset.filter !== model.filter) {
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
    if (model.rowsVersion !== paintedVersion) {
      paintedVersion = model.rowsVersion;
      paintRows(model.rows);
      placeRows(model.setSize);
    } else if (model.setSize !== placedSize) {
      placeRows(model.setSize);
    }
    for (const { chip, value, tally } of tallies) {
      const count = model.filterTotals?.[value] ?? null;
      const pending = count === null && model.fetching !== null;
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
    for (const line of [model.progress, model.freshness]) {
      if (line !== null) {
        lines.push(h("span", { class: "github-pulls-progress" }, [line]));
      }
    }
    status.replaceChildren(...lines);
    status.hidden = lines.length === 0;
    if (fetchLabel.textContent !== (model.fetching ?? "")) {
      fetchLabel.textContent = model.fetching ?? "";
    }
    activity.hidden = model.fetching === null;
    empty.textContent = model.empty ?? "";
    empty.hidden = model.empty === null;
    if (model.notice === null) {
      notice.replaceChildren();
    } else {
      const box = h(
        "div",
        {
          class: "notice github-pulls-notice",
          "data-severity": model.notice.severity,
        },
        [h("span", {}, [model.notice.text])],
      );
      if (model.notice.help !== undefined) {
        box.append(
          mb.decorateExternalLink(
            h(
              "a",
              { href: "https://cli.github.com/", target: "_blank", rel: "noopener noreferrer" },
              [model.notice.help === "install" ? "Install GitHub CLI" : "Update GitHub CLI"],
            ),
          ),
        );
      }
      if (model.notice.retry) {
        const retry = h("button", { type: "button", class: "btn" }, ["Retry"]);
        retry.addEventListener("click", () => void controller.retry());
        box.append(retry);
      }
      notice.replaceChildren(box);
    }
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
    paintViewport();
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
      now: () => Date.now(),
      isVisible: () => document.visibilityState === "visible",
      formatTime: (iso) => mb.formatTimestamp(Date.parse(iso) / 1000),
      render(model, identity) {
        stackIdentity = identity;
        mb.perf.measure("githubPulls:render", () => paint(model), { rows: model.rows.length });
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
      open: (route) => {
        showPage(route.number);
        return nav.open(route);
      },
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
        setExpanded(number, expansion.toggle(number), true);
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
  document.addEventListener(
    "visibilitychange",
    () => {
      controller.onVisibilityChange();
      if (document.visibilityState === "visible") {
        queueWindow();
      } else {
        cancelCoreSample();
      }
    },
    { signal },
  );

  // Rows ahead of the view arrive before they are reached, so a scroll does not stop at the end
  // of a window, and reaching the end is a reader's action, as Load more is.
  const atEnd =
    typeof IntersectionObserver === "function"
      ? new IntersectionObserver(
          (entries) => {
            if (entries.some((entry) => entry.isIntersecting)) {
              void controller.reachedEnd();
            }
          },
          { root: nav.scrollRoot, rootMargin: "100% 0px" },
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
  showPage(nav.current);
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
      showPage(number);
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
        setExpanded(number, true, true);
      } else if (!treeFor(number).controller.enter()) {
        setExpanded(number, true, true);
      }
      return true;
    },
    /** Left on a pull request's row: its files close. */
    collapse() {
      const number = controller.snapshot().anchor;
      if (number !== null && expansion.collapse(number)) {
        setExpanded(number, false, true);
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

/**
 * Whether the list a landing reads has nothing to say yet: no rows, no end, and no failure,
 * with its refresh not run or still running.
 *
 * @param {PullsEnvelope | null} envelope
 */
function landingWaits(envelope) {
  if (envelope === null) {
    return true;
  }
  return (
    envelope.reason !== "not_github" &&
    envelope.fetched === 0 &&
    (envelope.refreshing ||
      (!envelope.complete &&
        (envelope.state === "absent" || envelope.state === "pending") &&
        envelope.last_refresh === null))
  );
}

/**
 * What the pane says at the list's own address, `/pulls`, as the list comes in. A first visit
 * lands before the tab's refresh has run, so a list with nothing to say yet is read again while
 * the page is shown, until it has rows, an end, or a failure to tell. The first read again is
 * at the fast poll, as the tab's ask follows the landing by a moment; then the fast poll while
 * a refresh runs, and the slow one while none does.
 *
 * @param {{
 *   request: PullsDependencies["request"],
 *   schedule(callback: () => void, delayMs: number): unknown,
 *   cancel(handle: unknown): void,
 *   isVisible(): boolean,
 *   formatTime(iso: string): string,
 *   checkout?: boolean,
 *   say(text: string): void,
 * }} deps
 */
export function followLanding(deps) {
  const listening = new AbortController();
  /** @type {unknown} */
  let timer = null;
  let reads = 0;
  let reading = false;
  let settled = false;

  async function read() {
    if (settled || reading || listening.signal.aborted) {
      return;
    }
    reading = true;
    reads += 1;
    /** @type {PullsEnvelope | null} */
    let envelope = null;
    try {
      const response = await deps.request("GET", `${PULLS_ROUTE}?limit=0`, {
        signal: listening.signal,
      });
      // The pin guard owns this refusal and will reload the page. Say nothing over it.
      if (pinChanged(response)) {
        settled = true;
        return;
      }
      envelope = response.status === 200 && isEnvelope(response.body) ? response.body : null;
    } catch {
      envelope = null;
    } finally {
      reading = false;
    }
    if (listening.signal.aborted) {
      return;
    }
    deps.say(
      envelope === null
        ? "Could not read pull requests. Trying again."
        : describeLanding(envelope, deps.formatTime, deps.checkout),
    );
    settled = !landingWaits(envelope);
    if (!settled && deps.isVisible()) {
      const running = envelope?.refreshing === true || envelope?.state === "pending";
      timer = deps.schedule(
        () => {
          timer = null;
          void read();
        },
        envelope !== null && (reads === 1 || running) ? FAST_POLL_MS : SLOW_POLL_MS,
      );
    }
  }

  void read();
  return Object.freeze({
    onVisibilityChange() {
      if (!deps.isVisible()) {
        deps.cancel(timer);
        timer = null;
      } else if (timer === null) {
        void read();
      }
    },
    dispose() {
      listening.abort();
      deps.cancel(timer);
      timer = null;
    },
  });
}

/**
 * Mount what the pane says at the list's own address. Browser only.
 *
 * @param {HTMLElement} container
 * @param {MetabrowserPublicRenderContext} _ctx
 * @param {MetabrowserPublicSdk} mb
 */
export function mountPullsLanding(container, _ctx, mb) {
  // The wrapper contains a neutral instruction, not content to retain on selection.
  container.setAttribute("data-preview-empty", "");
  const said = h("div", { class: "preview-empty" });
  container.replaceChildren(said);
  const landing = followLanding({
    request: (method, route, options) => request(mb.perf, method, route, options),
    schedule: (callback, delayMs) => window.setTimeout(callback, delayMs),
    cancel: (handle) => window.clearTimeout(/** @type {number | undefined} */ (handle)),
    isVisible: () => document.visibilityState === "visible",
    formatTime: (iso) => mb.formatTimestamp(Date.parse(iso) / 1000),
    checkout: mb.sourceKind() === "filesystem",
    say(text) {
      if (said.textContent !== text) {
        said.textContent = text;
      }
    },
  });
  const listening = new AbortController();
  document.addEventListener("visibilitychange", landing.onVisibilityChange, {
    signal: listening.signal,
  });
  return Object.freeze({
    dispose() {
      listening.abort();
      landing.dispose();
    },
  });
}
