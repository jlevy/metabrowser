// The Pulls tab's list: every pull request of the repository, newest first, each with its
// state's icon, from the cache at once and refreshed in the background while it is shown.
//
// Every decision lives here without a DOM. `describePulls` turns one list's envelope and
// rows into what the panel shows; `createPullsController` owns the filters, the windows of
// rows, reading a next GitHub page, polling and refreshing only while the panel is shown,
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
// holds to one attempt a window. A row's record is read when the reader stops on it: that
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
  FAST_POLL_MS,
  h,
  isPlainClick,
  REFRESH_ASK_MS,
  relativeAge,
  SLOW_POLL_MS,
} from "./pull-page.js";
import { displayState, PULL_STATES, pullStateIcon } from "./pull-state.js";

const PULLS_ROUTE = "/api/plugin/github/pulls";
const REFRESH_ROUTE = "/api/plugin/github/pulls-refresh";
const PULL_ROUTE = "/api/plugin/github/pull";

export const LISTS = Object.freeze(["all", "open", "closed"]);
const LIST_LABELS = Object.freeze({ all: "All", open: "Open", closed: "Closed" });
const FILTER_GROUP = "github-pulls-filter";

// Rows asked for at a time, one GitHub page, as the route's own default. The tab appends plain
// rows, which costs what the new rows cost and not what the list holds.
//
// Measured 2026-11-03 in headless Chrome 152 on pallets/click at the cap, one page of 1,000 real
// rows, 20,700 nodes and 4.8 MB of heap, load average 4 to 6. Each number is load-independent or
// is the median of several runs:
//
// - The tab's activation to its next paint: 60 to 70 ms as plain rows, past `--loading-state-delay`,
//   and 14 to 23 ms with `content-visibility: auto` on each item (forced layout 66 ms and 2.9 ms).
//   At one window of 100 rows, 10 to 15 ms, and a first show after the read ahead is the same.
// - A window appended: 7 to 8 ms of main-thread tasks, the same at the 100th row as the 1,000th.
// - A step of a held key, at 30 steps a second, 200 steps: its handler took 0.3 to 0.6 ms, and
//   each event 24 ms at the slowest to its next paint, the same at 100 rows and 1,000. One row's
//   class, tab stop, focus, and bringing it into view took 0.4 ms in place.
//
// So plain rows carry the cap, MAX_LIST_ROWS in pull_list.py, with no windowing module: what is
// mounted costs what is on screen. The Git tab windows because its history has no such cap.
export const WINDOW_ROWS = 100;
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
// A list's job is one to three seconds a page when GitHub answers, so a wait past this is a
// wait for its turn: pull-request jobs queued before it hold the refresh slots. Measured
// 2026-11-03 on pallets/click: 1.7 s with nothing queued, and 35 s behind MAX_PULL_JOBS.
export const LONG_WAIT_MS = 10000;
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
  gh_missing: "Install GitHub CLI and sign in to read this repository's pull requests.",
  not_logged_in: "Run gh auth login to read this repository's pull requests.",
  network_error: "Offline, or GitHub could not be reached. The list is as it was last fetched.",
  not_found_or_private:
    "The repository was not found, or the signed-in account cannot read its pull requests.",
});

/** @type {Readonly<Record<string, string>>} */
const ABSENCE = Object.freeze({
  not_github: "This server serves no GitHub repository.",
  schema_mismatch: "The saved list is from another version, and is being replaced.",
  unreadable: "The saved list could not be read, and is being replaced.",
});
// A checkout's tab is drawn for an `origin` on github.com that the plugin's grammar may still
// refuse, which the route answers as `not_github`.
const CHECKOUT_NOT_LISTED =
  "This checkout's origin is not a GitHub repository Metabrowser can list.";

/**
 * @typedef {{outcome: string, message: string | null, reset_at: string | null, at: string}} LastRefresh
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
 *   at_cap: boolean,
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
 *   skeleton: boolean,
 *   listName: string,
 *   origin: string | null,
 *   count: string | null,
 *   freshness: string | null,
 *   empty: string | null,
 *   notice: {severity: "warning" | "error" | null, text: string, retry: boolean} | null,
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
function rowRefs(row, repository) {
  const head = text(row.head_ref);
  const from =
    typeof row.head_repository !== "string"
      ? `${head} (deleted fork)`
      : row.head_repository.toLowerCase() === repository?.toLowerCase()
        ? head
        : `${row.head_repository.split("/")[0]}:${head}`;
  return `${text(row.base_ref)} ← ${from}`;
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
  const refs = rowRefs(row, repository);
  return {
    number: row.number,
    href: `/pull/${row.number}`,
    state,
    stateLabel: PULL_STATES[state].label,
    title: text(row.title),
    author,
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
 * @returns {{text: string, retry: boolean} | null}
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
  const said = FAILURES[last.outcome] ?? last.message ?? last.outcome.replaceAll("_", " ");
  const sentence = `${said.charAt(0).toUpperCase()}${said.slice(1)}`;
  return { text: sentence.endsWith(".") ? sentence : `${sentence}.`, retry: true };
}

/**
 * What the panel shows for one list. Pure.
 *
 * *rows* are the rows held so far, already described; the envelope is the last answer, whose
 * own `rows` are only a window. *waitedMs* is how long a list with no rows has been waited on.
 *
 * @param {PullsEnvelope | null} envelope
 * @param {{
 *   filter: string,
 *   rows: PullRow[],
 *   rowsVersion: number,
 *   nowMs: number,
 *   formatTime: (iso: string) => string,
 *   more: boolean,
 *   waitedMs: number,
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
    setSize: Math.max(envelope?.fetched ?? 0, page.rows.length),
    skeleton: false,
    listName: "Pull requests",
    origin: null,
    count: null,
    freshness: null,
    empty: null,
    notice: null,
    loadMore: null,
    github: null,
    live: "",
  };
  if (envelope === null) {
    model.status = page.error === null ? "loading" : "unavailable";
    model.skeleton = page.error === null;
    model.notice =
      page.error === null ? null : { severity: "error", text: page.error, retry: false };
    model.live = page.error ?? "";
    return model;
  }
  model.status = envelope.state;
  const repository = repositoryName(envelope.source);
  const failure = refreshFailure(envelope, page.formatTime);
  const holding = envelope.fetched > 0 || page.rows.length > 0;
  if (envelope.state === "absent" && envelope.reason === "not_github") {
    model.empty = page.checkout === true ? CHECKOUT_NOT_LISTED : ABSENCE.not_github;
    model.live = model.empty;
    return model;
  }
  if (page.checkout === true && repository !== null) {
    // A checkout's heading is its folder, and on a fork its `origin` is the fork, whose list
    // is often empty: so the tab names the repository it lists, and how it chose it.
    model.origin = `Pull requests of ${repository}, this checkout's origin`;
  }
  if (!holding && (envelope.state === "absent" || envelope.state === "pending")) {
    // Nothing to show yet. The shape of rows, unless the wait is one a reader must act on.
    model.skeleton = failure === null;
    const reason = envelope.reason === null ? undefined : ABSENCE[envelope.reason];
    if (reason !== undefined && failure === null) {
      model.notice = { severity: null, text: reason, retry: false };
    }
    if (envelope.refreshing && page.waitedMs >= LONG_WAIT_MS) {
      model.notice = {
        severity: null,
        text: "Still waiting for the list… Pull requests being fetched go first.",
        retry: false,
      };
    }
    model.live = envelope.refreshing ? "Waiting for the list of pull requests…" : "";
  }
  const name = repository === null ? "Pull requests" : `Pull requests of ${repository}`;
  if (envelope.state === "current" || envelope.state === "stale") {
    const count = pullsCount(envelope.fetched);
    model.count = envelope.complete ? count : `${count} · GitHub has more`;
    model.listName = `${name}: ${model.count}`;
    const reader = text(envelope.reader).replace(/^gh:/, "");
    const age = relativeAge(envelope.fetched_at, page.nowMs);
    const stale = envelope.state === "stale" ? " · may be out of date" : "";
    model.freshness = envelope.refreshing
      ? `Refreshing… · fetched ${age} by ${reader}`
      : `Fetched ${age} by ${reader}${stale}`;
    if (envelope.fetched === 0 && envelope.complete) {
      model.empty =
        page.filter === "all" ? "No pull requests." : `No ${page.filter} pull requests.`;
    }
    // The list's name, whether or not a refresh is running: so a refresh that changes nothing
    // announces nothing, a minute after a minute, and a change in the count does.
    model.live = model.listName;
  } else {
    model.listName = name;
  }
  if (failure !== null) {
    model.notice = { severity: "warning", text: failure.text, retry: failure.retry };
    model.live = failure.text;
  } else if (envelope.truncated && model.notice === null) {
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
  } else if (
    holding &&
    (page.rows.length < envelope.fetched || (!envelope.complete && !envelope.at_cap))
  ) {
    model.loadMore = "ready";
  }
  if (envelope.at_cap && repository !== null) {
    model.github = `https://github.com/${repository}/pulls`;
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
    return checkout ? CHECKOUT_NOT_LISTED : ABSENCE.not_github;
  }
  const failure = envelope === null ? null : refreshFailure(envelope, formatTime);
  if (envelope !== null && envelope.fetched === 0 && failure !== null) {
    return failure.text;
  }
  if (envelope?.fetched === 0 && envelope.complete) {
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
 *   render(model: PullsModel): void,
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
 *   waitingSince: number | null,
 *   more: boolean,
 *   error: string | null,
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
    waitingSince: null,
    more: false,
    error: null,
  };
}

/**
 * Which list file an answer's rows come from. A refresh writes a new `fetched_at`, a next
 * GitHub page more rows, and another account its own name; a refresh that is starting, or a
 * list that went stale, changes none of them. So an answer that names the same file leaves the
 * rows held as they are, and only one that names another is read again whole.
 *
 * @param {PullsEnvelope} envelope
 */
function contentOf(envelope) {
  return JSON.stringify([
    envelope.source,
    envelope.fetched_at,
    envelope.reader,
    envelope.fetched,
    envelope.complete,
    envelope.truncated,
  ]);
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
    : "all";
  /** @type {number | null} */
  let current = options.current ?? null;
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

  /** @returns {HeldList} */
  function held() {
    return /** @type {HeldList} */ (lists.get(filter));
  }

  function live() {
    return shown && !disposed && deps.isVisible();
  }

  function model() {
    const list = held();
    const waiting = list.waitingSince === null ? 0 : deps.now() - list.waitingSince;
    return describePulls(list.envelope, {
      filter,
      rows: list.rows,
      rowsVersion: list.version,
      nowMs: deps.now(),
      formatTime: deps.formatTime,
      more: list.more,
      waitedMs: waiting,
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
    const key = JSON.stringify({ ...next, rows: null });
    if (key !== painted) {
      painted = key;
      deps.render(next);
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
   * Take one answer's envelope for its list.
   *
   * @param {HeldList} list
   * @param {PullsEnvelope} envelope
   */
  function holdEnvelope(list, envelope) {
    list.envelope = envelope;
    list.error = null;
    if (envelope.refreshing) {
      list.waitingSince ??= deps.now();
    } else {
      list.waitingSince = null;
    }
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
    if (filter !== "all" || current === null || list.keys.has(current) || list.nextAfter === null) {
      return;
    }
    if (current < list.nextAfter) {
      chasing = true;
      void loadWindow();
    }
  }

  /**
   * Hold the rows of a list file the panel has not read: the top window's, when that is all
   * it holds, and otherwise the whole range it holds, read again. A window appended while
   * that range is read makes it short, so it is not taken, and the next poll reads it again.
   * Whether the rows were held is the answer: the poll takes the top window's tag only with
   * them, so a read that did not land is not answered by a 304 next time.
   *
   * @param {HeldList} list
   * @param {PullsEnvelope} top
   * @param {string} content
   * @param {{request: number, signal: AbortSignal}} asked
   * @returns {Promise<boolean>}
   */
  async function holdContent(list, top, content, asked) {
    let answer = top;
    let named = content;
    if (list.rows.length > WINDOW_ROWS) {
      const name = filter;
      const version = list.version;
      const whole = await deps.request(
        "GET",
        `${PULLS_ROUTE}?state=${name}&limit=${list.rows.length}`,
        { signal: asked.signal },
      );
      if (disposed || name !== filter) {
        return false;
      }
      if (whole.status !== 200 || !isEnvelope(whole.body) || list.version !== version) {
        return false;
      }
      answer = whole.body;
      named = contentOf(answer);
      if (asked.request >= shownRequest) {
        holdEnvelope(list, answer);
      }
    }
    holdRows(list, answer.rows, answer.source);
    list.nextAfter = answer.next_after;
    list.content = named;
    return true;
  }

  /**
   * Read the list's top window: the route's tag says whether anything changed, so a poll of
   * an unchanged list is a 304 however many rows are held. An answer from another list file
   * replaces the rows; when more are held than the top window, they are read again whole,
   * once, so a list that changed is read in full only when it did.
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
    const controller = new AbortController();
    inflight = controller;
    try {
      const response = await deps.request(
        "GET",
        `${PULLS_ROUTE}?state=${name}&limit=${WINDOW_ROWS}`,
        { etag: list.etag, signal: controller.signal },
      );
      if (disposed || name !== filter) {
        return;
      }
      if (response.status === 200 && isEnvelope(response.body)) {
        if (request >= shownRequest) {
          shownRequest = request;
          holdEnvelope(list, response.body);
          const content = contentOf(response.body);
          if (
            content === list.content ||
            (await holdContent(list, response.body, content, {
              request,
              signal: controller.signal,
            }))
          ) {
            list.etag = response.etag;
          }
          if (list.more && !response.body.refreshing && list.nextAfter === null) {
            list.more = false;
          }
        }
      } else if (response.status === 304) {
        list.error = null;
      } else if (!pinChanged(response)) {
        list.error = `The list is unavailable (HTTP ${response.status}).`;
      }
    } catch {
      if (disposed || name !== filter || controller.signal.aborted) {
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
    if (disposed || name !== filter) {
      return;
    }
    settleAnchor();
    render();
    if (first && current !== null && list.keys.has(current)) {
      deps.reveal(current);
    }
    chaseCurrent();
    // A reader who asked for the next GitHub page gets its rows without asking twice.
    if (list.more && list.nextAfter !== null) {
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
      envelope.refreshing ||
      envelope.reason === "not_github"
    ) {
      return;
    }
    if (envelope.state !== "absent" && envelope.state !== "stale") {
      return;
    }
    const windowMs = envelope.fresh_for_s * 1000;
    if (list.askedAt !== null && deps.now() - list.askedAt < windowMs) {
      return;
    }
    list.askedAt = deps.now();
    void ask({ state: filter });
  }

  /**
   * Send a refresh and take the envelope it answers with. The answer has no rows.
   *
   * @param {{state: string, more?: boolean, retry?: boolean}} body
   */
  async function ask(body) {
    const name = body.state;
    const list = /** @type {HeldList} */ (lists.get(name));
    const request = ++sent;
    const reader = body.retry === true || body.more === true;
    try {
      const response = await deps.request("POST", REFRESH_ROUTE, { body });
      const answer = /** @type {{pulls?: unknown, error?: unknown} | null} */ (response.body);
      if (disposed) {
        return;
      }
      if (
        (response.status === 202 || response.status === 200) &&
        answer !== null &&
        isEnvelope(answer.pulls)
      ) {
        if (request >= shownRequest) {
          shownRequest = request;
          holdEnvelope(list, answer.pulls);
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
      if (reader && !disposed) {
        list.error = "The refresh request failed.";
        list.more = false;
      }
    }
    if (!disposed && name === filter) {
      render();
      scheduleNext();
    }
  }

  /** Read the next window of rows the list already holds. Local, and runs no gh. */
  let loadingWindow = false;
  async function loadWindow() {
    const list = held();
    const name = filter;
    if (disposed || loadingWindow || list.nextAfter === null) {
      return;
    }
    loadingWindow = true;
    const request = ++sent;
    // The rows it follows: a poll that replaces them while it is read makes it another list's.
    const version = list.version;
    const after = list.nextAfter;
    let superseded = false;
    try {
      const response = await deps.request(
        "GET",
        `${PULLS_ROUTE}?state=${name}&limit=${WINDOW_ROWS}&after=${after}`,
        {},
      );
      if (disposed) {
        return;
      }
      superseded = list.version !== version || list.nextAfter !== after;
      if (superseded) {
        // Its rows follow rows the list no longer holds, so they are dropped.
      } else if (response.status === 200 && isEnvelope(response.body)) {
        // The rows after the ones held, and only if nothing changed under them.
        const repository = repositoryName(response.body.source);
        const fresh = response.body.rows
          .map((row) => describeRow(row, repository))
          .filter((row) => !list.keys.has(row.number));
        for (const row of fresh) {
          list.keys.set(row.number, list.rows.length);
          list.rows.push(row);
        }
        if (fresh.length > 0) {
          list.version += 1;
        }
        // The poll's tag is the top window's, which a window leaves as it was.
        if (request >= shownRequest) {
          shownRequest = request;
          holdEnvelope(list, response.body);
        }
        list.nextAfter = response.body.next_after;
        if (list.nextAfter === null) {
          list.more = false;
        }
      } else if (!pinChanged(response)) {
        list.error = `The list is unavailable (HTTP ${response.status}).`;
      }
    } catch {
      if (!disposed) {
        list.error = "The server did not answer.";
      }
    } finally {
      loadingWindow = false;
    }
    if (superseded && !disposed && name === filter) {
      // The reader asked for the rows after the end, which the replaced list has too.
      await loadWindow();
      return;
    }
    if (!disposed && name === filter) {
      settleAnchor();
      render();
      if (chasing && current !== null && list.keys.has(current)) {
        chasing = false;
        deps.reveal(current);
      } else {
        chaseCurrent();
      }
    }
  }

  /**
   * The next rows: a window of what is held, or else, on a reader's action, one more GitHub
   * page. *retrying* is a press of the button: reaching the end of the list by itself never
   * asks again after a failure.
   *
   * @param {boolean} retrying
   */
  function next(retrying) {
    const list = held();
    const envelope = list.envelope;
    if (disposed || envelope === null) {
      return Promise.resolve();
    }
    if (list.nextAfter !== null) {
      return loadWindow();
    }
    // A list with nothing yet has no end to reach, and no next page to name.
    const holds = envelope.state === "current" || envelope.state === "stale";
    if (!holds || envelope.complete || envelope.at_cap || list.more) {
      return Promise.resolve();
    }
    const failed = envelope.last_refresh !== null && envelope.last_refresh.outcome !== "succeeded";
    if (failed && !retrying) {
      return Promise.resolve();
    }
    list.more = true;
    render();
    return ask({ state: filter, more: true });
  }

  /** @param {number} number */
  function setCurrentRow(number) {
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
        if (response.status !== 200) {
          return null;
        }
        const answer = { etag: response.etag, body: response.body };
        if (peeked.size >= MAX_PEEKED) {
          peeked.delete(/** @type {number} */ (peeked.keys().next().value));
        }
        peeked.set(number, answer);
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
    inflight?.abort();
    inflight = null;
    polling = false;
    // A row of the list being left that is still waiting to open does not open over it.
    opening += 1;
    clearWalk();
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
        return;
      }
      if (current !== null && held().keys.has(current)) {
        deps.reveal(current);
      }
      void poll();
    },
    setFilter,
    /**
     * The address says which pull request's page holds the pane. Not a selection: the row
     * only follows it, and no fetch starts.
     *
     * @param {number | null} number
     */
    setCurrent(number) {
      if (disposed || number === current) {
        return;
      }
      // The address moved by itself, by Back or by a link on the page: a row that is still
      // waiting for its record to open does not open over it.
      opening += 1;
      if (walkingTo !== null && walkingTo !== number) {
        clearWalk();
      }
      const previous = current;
      current = number;
      deps.markCurrent(previous, number);
      settleAnchor();
      if (number !== null && held().keys.has(number)) {
        deps.reveal(number);
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
      return ask({ state: filter, retry: true });
    },
    onVisibilityChange() {
      if (disposed) {
        return;
      }
      if (!deps.isVisible()) {
        clearTimer();
        return;
      }
      void poll();
    },
    dispose() {
      disposed = true;
      clearTimer();
      clearWalk();
      inflight?.abort();
      reading?.controller.abort();
      peeked.clear();
    },
    snapshot: () => ({
      filter,
      current,
      anchor,
      shown,
      rows: held().rows.length,
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
 * @param {"GET" | "POST"} method
 * @param {string} route
 * @param {{etag?: string | null, body?: unknown, signal?: AbortSignal}} options
 * @returns {Promise<PullsResponse>}
 */
async function request(method, route, options) {
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
      decoded = await response.json();
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
  const status = h("p", { class: "github-pulls-status" });
  const notice = h("div", { class: "github-pulls-notice-host" });
  // A tree: a row's changed files hang off it as a group. Its keys are this view's, bound by
  // the tab's host; the Files tree's keyboard handler is scoped to the Files tab and never
  // sees these rows.
  const list = h("ul", { class: "github-pulls-list", role: "tree" });
  const empty = h("p", { class: "github-pulls-empty" });
  const skeleton = h("div", {
    class: "recent-loading mb-delayed-loading",
    role: "status",
    "aria-label": "Loading pull requests",
  });
  const foot = h("div", { class: "github-pulls-foot" });
  const live = h("span", { class: "sr-only", "aria-live": "polite" });
  container.classList.add("github-pulls");
  container.replaceChildren(filters, status, notice, skeleton, list, empty, foot, live);

  /**
   * What is painted of each row held, by number: its elements, the key of what it shows, and
   * when it was updated, whose age moves on while the row stays.
   *
   * @typedef {{
   *   item: HTMLElement,
   *   row: HTMLAnchorElement,
   *   age: HTMLElement,
   *   key: string,
   *   at: number | null,
   *   label: string,
   * }} PaintedRow
   */
  /** @type {Map<number, PaintedRow>} */
  const painted = new Map();
  /** The rows last painted, in their order: an append leaves them as they were. @type {PullRow[]} */
  let paintedRows = [];
  let paintedVersion = -1;
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
  function followCurrentFile() {
    const page = currentRow === null ? null : tab.pageFor(currentRow);
    if (page === followedPage) {
      return;
    }
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
        if (file !== null && currentRow !== null) {
          currentFile = file.path;
          trees.get(currentRow)?.controller.followCurrent(file.path);
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
        number,
        autoExpandFiles: AUTO_EXPAND_FILES,
        current: number === currentRow ? currentFile : null,
        shown: panelShown,
        scrollRoot: tab.scrollRoot,
        chevron,
        href: (path) => tab.fileHref(number, path),
        request: (method, route, options) =>
          request(method, route, { ...options, signal: options.signal ?? signal }),
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
    const meta = h("span", { class: "github-pulls-meta" }, [row.meta]);
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
    return { item, row: anchor, age: updated, key, at, label: when.label };
  }

  /**
   * Paint the rows. An answer that appends keeps every row it held, the same objects in the
   * same order, so only the new ones are built: an append costs what the rows added cost, and
   * not what the list holds. Any other answer reuses the rows that say the same.
   *
   * @param {PullRow[]} rows
   * @returns {number} The first row whose place in the list may have moved.
   */
  function paintRows(rows) {
    const kept = paintedRows.length;
    const appends = rows.length >= kept && paintedRows.every((row, index) => rows[index] === row);
    if (appends) {
      const fragment = document.createDocumentFragment();
      for (const row of rows.slice(kept)) {
        const entry = buildRow(row, JSON.stringify(row));
        painted.set(row.number, entry);
        fragment.append(entry.item);
      }
      list.append(fragment);
    } else {
      const focused =
        document.activeElement instanceof HTMLElement &&
        list.contains(document.activeElement) &&
        document.activeElement.dataset.number
          ? Number(document.activeElement.dataset.number)
          : null;
      const order = rows.map((row) => {
        const key = JSON.stringify(row);
        let entry = painted.get(row.number);
        if (entry === undefined || entry.key !== key) {
          entry = buildRow(row, key);
          painted.set(row.number, entry);
        }
        return entry;
      });
      const held = new Set(rows.map((row) => row.number));
      for (const number of [...painted.keys()]) {
        if (!held.has(number)) {
          painted.delete(number);
        }
      }
      list.replaceChildren(...order.map((entry) => entry.item));
      if (focused !== null) {
        painted.get(focused)?.row.focus({ preventScroll: true });
      }
    }
    paintedRows = rows.slice();
    return appends ? kept : 0;
  }

  /** The list's size the rows' places were last told against. */
  let placedSize = -1;

  /**
   * Tell each row its place and the list's size, as every Files row is told. The browser would
   * count them from the rows it has drawn, and `content-visibility: auto` keeps a row not yet
   * drawn out of the accessibility tree: in Chrome 152, 43 of 100 rows at 800 px tall. Only the
   * rows from *from* on can have moved, unless the size did.
   *
   * Measured 2026-11-03 in headless Chrome 152 at the cap, 1,000 rows, eight back-to-back pairs
   * against the paint without it, at a load average of 13: a window appended took 1.7 ms of
   * paint against 1.6 ms, a repaint that moves every row's place 14.9 ms against 14.8 ms, and
   * the tab's activation to its next paint 28.4 ms against 27.7 ms, which this does not run in.
   *
   * @param {PullRow[]} rows
   * @param {number} size
   * @param {number} from
   */
  function placeRows(rows, size, from) {
    const resized = size !== placedSize;
    placedSize = size;
    const total = String(size);
    for (let index = resized ? 0 : from; index < rows.length; index += 1) {
      const row = painted.get(rows[index].number)?.row;
      const at = String(index + 1);
      if (row !== undefined && row.getAttribute("aria-posinset") !== at) {
        row.setAttribute("aria-posinset", at);
      }
      if (row !== undefined && row.getAttribute("aria-setsize") !== total) {
        row.setAttribute("aria-setsize", total);
      }
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
      painted.clear();
      paintedRows = [];
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
      placeRows(model.rows, model.setSize, paintRows(model.rows));
    } else if (model.setSize !== placedSize) {
      placeRows(model.rows, model.setSize, model.rows.length);
    }
    tellAges();
    list.setAttribute("aria-label", model.listName);
    list.hidden = model.rows.length === 0;
    skeleton.hidden = !model.skeleton;
    status.replaceChildren(
      ...[model.origin, model.count, model.freshness]
        .filter((line) => line !== null)
        .map((line) => h("span", {}, [/** @type {string} */ (line)])),
    );
    status.hidden = model.origin === null && model.count === null && model.freshness === null;
    empty.textContent = model.empty ?? "";
    empty.hidden = model.empty === null;
    if (model.notice === null) {
      notice.replaceChildren();
    } else {
      const box = h(
        "div",
        {
          class: "notice github-pulls-notice",
          ...(model.notice.severity === null ? {} : { "data-severity": model.notice.severity }),
        },
        [h("span", {}, [model.notice.text])],
      );
      if (model.notice.retry) {
        const retry = h("button", { type: "button", class: "btn" }, ["Retry"]);
        retry.addEventListener("click", () => void controller.retry());
        box.append(retry);
      }
      notice.replaceChildren(box);
    }
    const footChildren = [];
    if (model.loadMore !== null) {
      const more = /** @type {HTMLButtonElement} */ (
        h("button", { type: "button", class: "btn github-pulls-more" }, ["Load more"])
      );
      more.disabled = model.loadMore === "loading";
      more.setAttribute("aria-busy", String(more.disabled));
      more.addEventListener("click", () => void controller.loadMore());
      footChildren.push(more);
    }
    if (model.github !== null) {
      footChildren.push(
        h("a", { href: model.github, target: "_blank", rel: "noopener noreferrer" }, [
          "See the rest on GitHub",
        ]),
      );
    }
    foot.replaceChildren(...footChildren);
    if (live.textContent !== model.live) {
      live.textContent = model.live;
    }
  }

  const listening = new AbortController();
  const { signal } = listening;
  // A key moved the focus, and not a reader arriving at a row: a walk reads nothing per row.
  let movingFocus = false;

  const controller = createPullsController(
    {
      request: (method, route, options) =>
        request(method, route, { ...options, signal: options.signal ?? signal }),
      schedule: (callback, delayMs) => window.setTimeout(callback, delayMs),
      cancel: (handle) => window.clearTimeout(/** @type {number} */ (handle)),
      now: () => Date.now(),
      isVisible: () => document.visibilityState === "visible",
      formatTime: (iso) => mb.formatTimestamp(Date.parse(iso) / 1000),
      render: paint,
      markCurrent(previous, next) {
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
  document.addEventListener("visibilitychange", controller.onVisibilityChange, { signal });

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
    typeof ResizeObserver === "function" ? new ResizeObserver(() => repaintTrees()) : null;
  moved?.observe(list);
  function repaintTrees() {
    for (const tree of trees.values()) {
      tree.repaint();
    }
  }

  /** The tree a file row with focus is in. */
  const focused = () => (focusedTree === null ? undefined : trees.get(focusedTree)?.controller);

  void controller.start({ shown: nav.shown, refreshAhead: nav.refreshAhead });
  showPage(nav.current);
  const unwatchPage = tab.onPageChange(followCurrentFile);
  followCurrentFile();

  return Object.freeze({
    /** @param {boolean} visible */
    setShown(visible) {
      panelShown = visible;
      controller.setShown(visible);
      for (const tree of trees.values()) {
        tree.controller.setShown(visible);
      }
    },
    /**
     * The address names a pull request's page, and maybe one file of it.
     *
     * @param {number | null} number
     * @param {string | null} [file]
     */
    setCurrent(number, file = null) {
      if (currentRow !== null && currentRow !== number) {
        trees.get(currentRow)?.controller.cancelWalk();
      }
      if (focusedTree !== null && focusedTree !== number) {
        trees.get(focusedTree)?.controller.cancelWalk();
      }
      controller.setCurrent(number);
      currentFile = file;
      const row = number === null ? undefined : painted.get(number)?.row;
      if (row !== undefined) {
        markShown(row, true);
      }
      showPage(number);
      if (number !== null) {
        trees.get(number)?.controller.setCurrent(file);
      }
      followCurrentFile();
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
      listening.abort();
      atEnd?.disconnect();
      moved?.disconnect();
      unwatchPage();
      unwatchFile?.();
      window.clearTimeout(peekTimer);
      unbindFilters();
      controller.dispose();
      for (const tree of trees.values()) {
        tree.dispose();
      }
      trees.clear();
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
  const said = h("div", { class: "preview-empty" });
  container.replaceChildren(said);
  const landing = followLanding({
    request,
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
