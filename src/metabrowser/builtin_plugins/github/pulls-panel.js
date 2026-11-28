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
// role of its own, and the row's changed files hang off it as a folder's children do
// (pull-files-view.js): a `.tree-children[role="group"]` after it, which it owns, and
// `aria-expanded` on it. A pull request is one item, its anchor (mb-1z7j, mb-pw8t, mb-rb3n): a
// wrapping title followed by a dot and the author avatar, then its summary line with the
// diff toggle and age on the left and readiness and number on the right. The item has one
// hover, one selection, and one keyboard stop (`.github-pulls-entry`). Its toggle is the brief change
// line and the chevron after it, the summary the chevron expands (docs/design-system.md, "A
// Click on the Toggle's Line Toggles"): a click on them toggles the files and opens no page,
// and a click anywhere else on the item opens the pull request and expands nothing; a
// modified click toggles nothing, and off the toggle is the browser's, a new tab. No row
// expands on its own: not on an open, a selection, or a key's walk. Up and Down walk the pull
// requests as wholes, and bring the whole item into view; on one, Space toggles its files,
// Right opens them or goes to the first, Left closes them or goes to its stack's row, and
// Enter opens it. Every key acts on the row that has focus (`anchorFocusedRow`). The toggle
// is the pointer's alone: hidden from assistive technology, it leaves the tree its items and
// groups, and its words describe the row. The walk goes by `rows`, not by the DOM, so it reads the same however a row is drawn.
//
// The readiness glyph sits just before the number. A row without a verdict reserves
// the glyph's width. The accessible name says the verdict after the PR state.
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

import { createComparisonWarmer, diffComparisonLoader } from "./comparison-prefetch.js";
import {
  rateLimitText,
  refreshFailureText,
  refreshRefusedText,
  setupHelp,
  unavailableText,
} from "./copy.js";
import { createRowExpansion } from "./pull-files-tree.js";
import { mountFileTree } from "./pull-files-view.js";
import {
  alignRefreshing,
  authorLabel,
  avatarUrl,
  FAST_POLL_MS,
  h,
  isPlainClick,
  isEnvelope as isPullEnvelope,
  pullComparison,
  REFRESH_ASK_MS,
  SLOW_POLL_MS,
} from "./pull-page.js";
import {
  createStackIndex,
  groupByStack,
  namedStackPositionNodes,
  STACK_OVERVIEW,
  stackCaption,
  stackLabel,
  stackLeaders,
  stackMembership,
  stackPullsCount,
  stackRowKey,
  watchStacks,
  wholeStackHint,
  wholeStackOfKey,
  wholeStackRowKey,
} from "./pull-stacks.js";
import { displayState, noteListed, PULL_STATES } from "./pull-state.js";
import { createPullsWindow } from "./pulls-window.js";
import {
  createRowLines,
  PULL_FILES_SUMMARY_ROUTE,
  rowLineHint,
  rowLineInput,
} from "./row-lines.js";
import { createRowReadiness, PULL_STATUSES_ROUTE } from "./row-readiness.js";
import { createStackFileList } from "./stack-files.js";
import { createStackLines, STACK_CHANGE_ROUTE, stackLineInput } from "./stack-lines.js";
import { PULLS_RUN, stackMemberRow } from "./stack-member-row.js";

const PULLS_ROUTE = "/api/plugin/github/pulls";
const REFRESH_ROUTE = "/api/plugin/github/pulls-refresh";
const PULL_ROUTE = "/api/plugin/github/pull";
// The pull route's catalog verdict, which the page reads from its own first read.
const VERIFIED_HEADER = "x-metabrowser-verified";
const CORE_PREPARE_ROUTE = "/api/plugin/github/pull-cores-prepare";
const PREFETCH_ROUTE = "/api/plugin/github/pulls-prefetch";
// The list's first rows a prefetch names beside the anchored row's neighbours: the top open
// pull requests a reader most often opens next. With the two neighbours that is seven, under
// the server's eight record refreshes a scan, so one scan's changes do not crowd them out.
export const PREFETCH_TOP_ROWS = 5;
// The changed-files lists a prefetch names, the server's MAX_PREFETCH_NUMBERS: the rows the
// pointer or focus last rested on, the open row, its neighbours, then the rows in view.
export const PREFETCH_FILES = 16;
// Of those, the places kept for the members whose lists the drawn stacks' change lines wait
// for (stack-lines.js, `unsettled`), after the reader's own rows: a stack's line is its
// members' lists accumulated, and a collapsed stack's members are no rows in view. Each is
// listed once while its head stays put, from the local comparison with no GitHub call or
// from GitHub at a core point a page (pull_prefetch.py), under `FILES_PER_HOUR`,
// speculative work's share of the server's own ceiling, and the governor's floor; this
// repository's 19 stacks lacked 158 lists once. While a stack waits for lists, what gives
// way is the lowest rows in view past the twelfth: never a row rested on, the open row, or
// its neighbours, which come first. A
// row is about 41.5 px, so a pane taller than about 500 px has rows in view past those
// twelve, which are listed once the stacks' members are (review C of #484, C4).
export const PREFETCH_STACK_FILES = 4;
// The lane's files outcomes the panel remembers having passed on, to the stack lines and the
// rows' change lines, oldest out first: four times the outcomes its report holds
// (pull_prefetch.py, `MAX_RECENT`), so an outcome still in a report is never heard again.
const LISTED_SEEN = 64;
// Rows the pointer or focus rested on that a prefetch names first, newest first: the row a
// click is about to open, and the one the pointer left for it.
export const PREFETCH_RESTED = 2;
// How long the rows in view stay put before their changed files are asked for, so a reader
// scrolling past rows starts no list for them. A choice, not a bound on any cost: past the
// pauses inside one scroll, and under the seconds a reader spends reading rows before
// expanding one. A one-page list took about 1.1 s with its two account checks (github.com,
// 2026-11-13), and the lane reads one at a time, so the wait is the reader's, not the dwell.
export const FILES_DWELL_MS = 500;
// Existing measured GraphQL transport bound (exp-048); queues cover the whole viewport/catalog.
const CORE_BATCH_SIZE = 8;
// How long the panel waits for a batch's answer, a cache check unless it starts a read.
// Measured 2026-11-13 on 5,000 cataloged PRs: 14-34 ms idle; about 0.47 s, at most
// 0.73 s, beside eight 1000-row list reads. The slowest ever logged was 6.5 s, in a
// window serving a large repository, before those checks cost 2.5 times less. Each
// timeout is above all of these: an answer given up on is work thrown away and asked
// for again. A reader's next viewport aborts a visible batch sooner. A background batch
// is aborted by any visible one, so its timeout only ends a server that never answers.
const CORE_VISIBLE_TIMEOUT_MS = 10000;
const CORE_BACKGROUND_TIMEOUT_MS = 30000;
// A release clears ownership in memory, reading no disk.
const CORE_RELEASE_TIMEOUT_MS = 2000;
// A batch left unanswered this many times in a row, by a timeout or a failed request, is
// passed over; the walk returns to it at the end of its pass, as to a partial cohort,
// once 30 s have passed for every batch it passed over.
const CORE_MAX_MISSES = 2;
export const CORE_BUSY_RETRY_MS = 1000;

export const LISTS = Object.freeze(["open", "closed", "all"]);
const LIST_LABELS = Object.freeze({ all: "All", open: "Open", closed: "Closed" });
const FILTER_GROUP = "github-pulls-filter";

// The backend caches every PR, and the list has no end of its own: it reads the first 500
// from the cache, then one more cache page each time the reader nears its tail, as
// Commits does, until the filter's last row. The viewport and its protected anchors mount
// separately. A page's cost does not grow with depth: 2 ms of server time at the top,
// middle, and end of a 30,000-row catalog, and 6 to 7 ms a page from Chrome, at a load
// average of 14 to 18 (2026-11-13). So re-reading a changed prefix costs what the reader
// scrolled through, about 0.7 s for 10,000 rows, while the rows already shown stay.
export const WINDOW_ROWS = 100;
export const DISPLAY_ROWS = 500;
// Match Git history's near-tail distance.
const PAGE_AHEAD_PX = 240;
// Viewport neighbors; measured catalog-window evidence is recorded with the feature.
export const PULL_ROWS_OVERSCAN = 40;
// The height a row not yet measured is placed at: a typical pull request's closed row at the
// default pane, a run of three lines and its last line, the 2 px pad, three 19.5 px lines, and
// 20 px of last line, whether its lines wait or are shown (mb-pw8t, mb-rb3n). Measured in
// headless Chrome 152 with KPress's faces at the nav's 13 px type, on this repository's pull
// requests 440 to 488 in a closed row, each run the title, the number, and the author's avatar
// box and name, the age on the last line (tests/dom/github-pulls-row-lines-chrome.mjs,
// `REAL_TITLES`, 2026-11-25): at 299 px their runs take two lines for 7 of 45, three for 31,
// four for 6, and five for 1, a mean row of 80.9 px; at 380 px, one line for 1, two for 33,
// three for 10, and four for 1; at 420 px, one for 3, two for 36, and three for 6. With the age
// in the run after the author, at 299 px it was two lines for 4, three for 31, four for 9, and
// five for 1, a mean of 83.5 px. Each line of the run fewer or more makes a row a line shorter
// or taller, and the list places each row drawn by its measured height.
// When the run was the title alone, cut short at its second line, and the number and the
// lines were on the line under it, a row was at most 61 px (mb-85op, mb-lqkb).
export const ROW_ESTIMATE_PX = 80.5;
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
// How long a warm of a likely next pull request's comparison waits for the browser to be
// free, which bounds it only for a page that is never free. Idle callbacks run in the order
// they were asked for, and on an open the warm is asked for before the page has read its
// record, so this timeout does not put it behind the page: what does is that the warm waits
// for every comparison read on its way to end before it sends its own (`quiet` in
// comparison-prefetch.js).
const WARM_IDLE_TIMEOUT_MS = 1000;
const FETCHING = "Fetching pull requests…";
// Folders start open up to the measured file-list cap. Chrome 152, 2026-11-03: the
// first 1,183 files of django/django#15387 made 1,503 rows; 3,000 stress files made
// 4,539. With windowed paint, mounting cost 13.2 and 10.4 ms respectively, and a key's
// maximum cost was 4.1 and 1.4 ms. A larger page-count estimate starts compact.
export const AUTO_EXPAND_FILES = 3000;
// Trees of changed files kept while their rows are closed, so one opened again keeps the
// folders a reader opened. Each holds its list, at most 3,000 rows of text.
export const MAX_HELD_TREES = 8;

// What the panel says of a way a refresh can end that it words itself, and of any outcome
// neither it nor copy.js's shared words name, in one sentence each: a cached list shows
// under any of them, and the connection row says so after it.
/** @type {Readonly<Record<string, string>>} */
const FAILURES = Object.freeze({
  not_found_or_private: "GitHub could not find this repository or grant access to it.",
});
const REFRESH_FAILED = "Could not refresh the list.";
const WATCH_PAUSED = new Set(["gh_missing", "gh_too_old", "not_logged_in", "not_found_or_private"]);
const WATCH_SETUP_RETRY_MS = 120_000;

const NO_GITHUB = "This server serves no GitHub repository.";
// A checkout's tab is drawn for an `origin` on github.com that the plugin's grammar may still
// refuse, which the route answers as `not_github`.
const CHECKOUT_NOT_LISTED =
  "This checkout’s origin is not a GitHub repository Metabrowser can list.";

/**
 * @typedef {{outcome: string, message: string | null, reset_at: string | null, at: string}} LastRefresh
 * @typedef {Record<keyof typeof LIST_LABELS, number>} PullFilterTotals
 * @typedef {{
 *   state: "absent" | "pending" | "current" | "stale",
 *   reason: string | null,
 *   source: string | null,
 *   list: string,
 *   fetched_at: string | null,
 *   checked_at?: string | null,
 *   reader: string | null,
 *   fresh_for_s: number,
 *   probe_every_s?: number | null,
 *   refreshing: boolean,
 *   last_refresh: LastRefresh | null,
 *   refresh_timing?: MetabrowserRefreshTooltipTiming | null,
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
 *   position?: number | null,
 *   rows: Record<string, any>[],
 * }} PullsEnvelope
 */

/**
 * What a row shows. Text only. A row names no branches: the pull request's page does, and
 * the row's room goes to its title (docs/design-system.md, "The Pulls Tab").
 *
 * @typedef {{
 *   number: number,
 *   href: string,
 *   state: import("./pull-state.js").PullState,
 *   stateLabel: string,
 *   title: string,
 *   author: string,
 *   avatar: string | null,
 *   updatedAt: string | null,
 *   meta: string,
 *   head: string | null,
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
 *   filterTotals: PullFilterTotals | null,
 *   countSummary: {total: MetabrowserCountParts, scope: MetabrowserCountParts | null} | null,
 *   catalogReady: boolean,
 *   connection: {state: "working" | "connected" | "paused" | "unavailable", text: string,
 *     canRefresh: boolean, retrying?: true, refreshing?: true, help?: "install" | "update"} | null,
 *   refreshingRows?: number[],
 *   empty: string | null,
 *   progress: string | null,
 *   github: string | null,
 *   live: string,
 *   stacks: StackGrouping,
 * }} PullsModel
 */

/**
 * The Pulls tab's newest-first rows, with each stack's members grouped beneath its heading.
 * The tab groups once its stacks are known. `rows` is null while the list is flat,
 * before then or when no listed PR belongs to a stack.
 *
 * @typedef {{
 *   rows: import("./pull-stacks.js").GroupedRow[] | null,
 *   version: number,
 * }} StackGrouping
 */

/** @type {StackGrouping} */
const NO_GROUPING = Object.freeze({ rows: null, version: 0 });

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
 * What one row of the route shows. Pure.
 *
 * @param {Record<string, any>} row
 * @returns {PullRow}
 */
export function describeRow(row) {
  const state = displayState(row);
  const author = text(row.author) || "ghost";
  return {
    number: row.number,
    href: `/pull/${row.number}`,
    state,
    stateLabel: PULL_STATES[state].label,
    title: text(row.title),
    author,
    avatar: avatarUrl(row.author_avatar_url),
    updatedAt: typeof row.updated_at === "string" ? row.updated_at : null,
    meta: `${author} · #${row.number}`,
    // The head commit the catalog reported, which the row's change line (row-lines.js) and
    // its stack's (stack-lines.js) are read again for when it moves; it is not shown.
    head: typeof row.head_oid === "string" ? row.head_oid : null,
  };
}

/**
 * How many pull requests that is, in the words a count is said with everywhere.
 *
 * @param {number} count
 * @param {(count: number) => string} formatCount
 */
function pullsCount(count, formatCount) {
  return `${formatCount(count)} pull request${count === 1 ? "" : "s"}`;
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
      text: rateLimitText(last.reset_at === null ? null : formatTime(last.reset_at)),
    };
  }
  const text = refreshFailureText(last.outcome, FAILURES, REFRESH_FAILED);
  const help = setupHelp(last.outcome);
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
 * Rows already shown are never covered by progress. The navigation's Refresh gives the
 * latest completed refresh in its tooltip. The connection row explains first load,
 * incomplete results, and failures. *refreshingRows* are the rows
 * whose own data GitHub is being read for now, whose titles breathe too.
 *
 * The list never says how many rows it holds. Below the last row held, `progress` is the
 * crawl's own indicator, the nav's file scan in its words: while a further page is read
 * (*more*), or while GitHub's pages are still arriving and rows remain below.
 *
 * @param {PullsEnvelope | null} envelope
 * @param {{
 *   filter: string,
 *   rows: PullRow[],
 *   rowsVersion: number,
 *   filterTotals?: PullFilterTotals | null,
 *   nowMs: number,
 *   formatTime: (iso: string) => string,
 *   formatCount: (count: number) => string,
 *   more: boolean,
 *   error: string | null,
 *   checkout?: boolean,
 *   online?: boolean,
 *   requesting?: boolean,
 *   refreshingRows?: number[],
 *   stacks?: StackGrouping,
 * }} page
 * @returns {PullsModel}
 */
export function describePulls(envelope, page) {
  /** @type {PullsModel} */
  const model = {
    filter: page.filter,
    status: envelope?.state ?? "loading",
    rows: page.rows,
    rowsVersion: page.rowsVersion,
    // How many rows the list has, which a window appended does not move: each row's place is
    // told against it, and not against the rows held or drawn so far.
    setSize: envelope?.total ?? Math.max(envelope?.fetched ?? 0, page.rows.length),
    listName: "Pull requests",
    filterTotals:
      page.filterTotals === undefined ? (envelope?.filter_totals ?? null) : page.filterTotals,
    countSummary: null,
    catalogReady: envelope?.complete === true && !envelope.refreshing,
    connection: null,
    empty: null,
    progress: null,
    github: null,
    live: "",
    stacks: page.stacks ?? NO_GROUPING,
  };
  if (envelope?.state === "absent" && envelope.reason === "not_github") {
    model.empty = page.checkout === true ? CHECKOUT_NOT_LISTED : NO_GITHUB;
    model.live = model.empty;
    return model;
  }
  const repository = repositoryName(envelope?.source ?? null);
  const repositoryTotal = model.filterTotals?.all ?? envelope?.repository_total ?? null;
  if (repositoryTotal !== null && (envelope === null || repository !== null)) {
    const subset = page.filter === "closed" ? "closed" : "open";
    const subsetTotal =
      model.filterTotals?.[subset] ?? (envelope?.list === subset ? envelope.total : null);
    model.countSummary = {
      total: [
        { number: page.formatCount(repositoryTotal) },
        repositoryTotal === 1 ? " pull request" : " pull requests",
      ],
      scope:
        subsetTotal === null
          ? null
          : [
              { separator: " · ", spoken: "," },
              { number: page.formatCount(subsetTotal) },
              ` ${subset}`,
            ],
    };
  }
  const online = page.online !== false;
  if (envelope === null) {
    model.status = page.error === null ? "loading" : "unavailable";
    const working = online && (page.error === null || page.requesting === true);
    model.connection = {
      state: online ? (working ? "working" : "unavailable") : "paused",
      text: online ? (working ? FETCHING : (page.error ?? "")) : "Offline.",
      canRefresh: online && !working,
    };
    model.live = model.connection.text;
    return model;
  }
  const failure = refreshFailure(envelope, page.formatTime, { includeWhileRefreshing: true });
  const holding = envelope.fetched > 0 || page.rows.length > 0;
  const name = repository === null ? "Pull requests" : `Pull requests of ${repository}`;
  const known = envelope.state === "current" || envelope.state === "stale";
  model.listName = known
    ? `${name}: ${pullsCount(envelope.total ?? envelope.fetched, page.formatCount)}`
    : name;
  if (known && (envelope.total === 0 || (envelope.fetched === 0 && envelope.complete))) {
    model.empty = page.filter === "all" ? "No pull requests." : `No ${page.filter} pull requests.`;
  }
  const cached = holding ? " Showing the pull requests last loaded." : "";
  const heldByRate = rateHoldMs(envelope, page.nowMs) > 0;
  const asking = page.requesting === true || envelope.refreshing;
  const working = asking || envelope.state === "pending" || envelope.state === "absent";
  if (!online) {
    model.connection = { state: "paused", text: `Offline.${cached}`, canRefresh: false };
  } else if (page.error !== null) {
    model.connection = {
      state: "unavailable",
      text: page.error + cached,
      canRefresh: !heldByRate && !asking,
    };
  } else if (failure !== null) {
    model.connection = {
      ...failure,
      state: "paused",
      text: failure.text + cached,
      canRefresh: !heldByRate && !asking,
      ...(asking ? (holding ? { refreshing: true } : { retrying: true }) : {}),
    };
  } else if ((working || page.more) && !holding) {
    model.connection = { state: "working", text: FETCHING, canRefresh: false };
  } else {
    model.connection = {
      state: "connected",
      text: envelope.truncated ? "Some pull requests are not listed." : "",
      canRefresh: !working,
      ...(working ? { refreshing: true } : {}),
    };
  }
  if (page.refreshingRows !== undefined && page.refreshingRows.length > 0) {
    model.refreshingRows = page.refreshingRows;
  }
  model.live = model.connection.state === "connected" ? model.listName : model.connection.text;
  const belowTotal = envelope.total === null || page.rows.length < envelope.total;
  const providerMayHaveMore =
    !envelope.complete &&
    envelope.total !== null &&
    online &&
    !heldByRate &&
    !watchPaused(envelope);
  // GitHub's pages for this filter are arriving: the catalog job runs, this filter has rows
  // it has not cached, and nothing holds or failed it.
  const crawling =
    asking &&
    providerMayHaveMore &&
    envelope.fetched < (envelope.total ?? 0) &&
    failure === null &&
    page.error === null;
  if (holding && belowTotal && (page.more || crawling)) {
    // As the nav's scan says "~N files scanned": a count only once one is known.
    model.progress =
      crawling && envelope.fetched > 0
        ? `~${page.formatCount(envelope.fetched)} pull requests fetched`
        : FETCHING;
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
 * What the Pulls tab says of a pull request a navigation named that its list cannot show
 * (`noteOutside`). *catalogued*: whether the server's catalog holds it. One it holds is in
 * the list further down than the list draws, newest first, so the list says only what it
 * has loaded. One the whole catalog lacks is in no list. A pull request the filter leaves
 * out is never noted: a navigation moves the list to one that draws it (`placeSought`), and
 * a filter the reader chose says by its chip what the list holds.
 *
 * @param {number} number
 * @param {boolean} catalogued
 */
export function outsideText(number, catalogued) {
  return catalogued
    ? `#${number} is not among the pull requests loaded.`
    : `#${number} is not in this list.`;
}

/**
 * The catalog as a list's envelope describes it: its epoch, which a new reader or source
 * starts again, and how many pull requests it has read, which only grows within an epoch,
 * as it does when one is opened. Every list's envelope carries both.
 *
 * @param {PullsEnvelope | null} envelope
 * @returns {{epoch: string, fetched: number} | null}
 */
function catalogMark(envelope) {
  if (envelope === null) {
    return null;
  }
  return { epoch: envelope.generation?.split(":")[0] ?? "", fetched: envelope.catalog_fetched };
}

/**
 * The row that holds the current-row mark once it moves from *previous* to *next*, from
 * *marked*, the row that held it: a pull request's mark and a Stack Overview row's are given and
 * taken in turn (`followPull`, `followStack`), so a mark that leaves clears only the row that
 * held it.
 *
 * @param {number | null} marked
 * @param {number | null} previous
 * @param {number | null} next
 * @returns {number | null}
 */
export function markedRow(marked, previous, next) {
  return next !== null || marked === previous ? next : marked;
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
 * @typedef {{state: string, window: {id: string, generation: string}, numbers: number[], lane: "visible" | "background"}} CoreWindowRequest
 * @typedef {{epoch: number, pass: number, body: CoreWindowRequest, canRetry: boolean, retryDelay: number, lane: "visible" | "background", queueKey: string, done: boolean, admitted?: boolean}} CoreDemand
 * @typedef {{status: number, etag: string | null, body: unknown, verified?: string | null}} PullsResponse
 * A row's record as one read answered it, and when that answer landed, by `now()`.
 * @typedef {{etag: string | null, body: unknown, verified: string | null, at: number}} RecordAnswer
 * @typedef {{
 *   request(
 *     method: "GET" | "POST",
 *     route: string,
 *     options: {etag?: string | null, body?: unknown, signal?: AbortSignal},
 *   ): Promise<PullsResponse>,
 *   schedule(callback: () => void, delayMs: number, what?: "probe"): unknown,
 *   cancel(handle: unknown): void,
 *   now(): number,
 *   isVisible(): boolean,
 *   isOnline?(): boolean,
 *   formatTime(iso: string): string,
 *   formatCount(count: number): string,
 *   render(model: PullsModel, identity: import("./pull-stacks.js").StackIdentity | null, arrivals: number[]): void,
 *   markCurrent(previous: number | null, next: number | null): void,
 *   markAnchor(previous: number | null, next: number | null, focus: boolean): void,
 *   reveal(number: number): void,
 *   openStack?(number: number, replace: boolean): void,
 *   markOutside?(text: string | null): void,
 *   focusPlace?(): "list" | "body" | "elsewhere",
 *   open(route: {
 *     number: number,
 *     tab: string,
 *     replace: boolean,
 *     reader: {
 *       fetchAfterMs: number,
 *       initial: RecordAnswer | null,
 *       pending: Promise<RecordAnswer | null> | null,
 *       walking: () => boolean,
 *       abandon?: () => void,
 *     },
 *   }): unknown,
 *   filterChanged(state: string): void,
 *   recheckTail?(): void,
 *   retellAges?(): void,
 *   refreshDetailChanged?(): void,
 *   warmComparisons?(numbers: number[]): void,
 *   stackFiles?(): number[],
 *   filesListed?(number: number): void,
 *   listingFiles?(numbers: number[]): void,
 *   listedFiles?(numbers: number[], idle: boolean): void,
 *   statusScan?(scan: unknown, endedAt: unknown): void,
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
 * Its rows are grouped by stack (`groupByStack` in pull-stacks.js) once the stacks are known
 * for the list's own reader, and are in the list's order until then: a stack's row, "Stack #N",
 * then its Stack Overview row and its pull requests, one level in, in `stackEntries`' order,
 * then every pull request in no stack. The keys walk the rows as they are drawn. A stack's
 * row is a row of the tree as a folder is: J and K stop on it and open nothing, Enter and
 * Space open or close it, Right opens it or goes to its first row, its Stack Overview row, and
 * Left closes it, or from a row in it goes to it. An open stack's Stack Overview row opens the
 * stack's own page as a pull request's row opens its page, on J, K, and Enter, and its
 * children are the stack's changed files, as a pull request's row's are its own, which
 * Space, Right, and Left open and close in the panel (`mountPullsPanel`); here Left on it
 * goes to its stack's row. While the address is the stack's page the Stack Overview row takes
 * the current-row mark (`setCurrent`'s *stack*). An address that names a pull request in a
 * stack the reader closed opens the stack over it (`showCurrent`).
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
  /** The native stack whose own page the address names (`/stack/<n>`), whose Stack Overview
   * row takes the current-row mark; null at any other address.
   * @type {number | null} */
  let currentStack = null;
  /**
   * Whether *currentStack*'s Stack Overview row is still to be revealed: an address of the
   * stack's page can come before the list draws the row, before the stacks are known or a
   * read brings a member, and the row is revealed when it is drawn, as a pull request's row
   * is once the list holds it (*revealPending*).
   */
  let wholeRevealPending = false;
  let revealCurrent = true;
  /**
   * The pull request a navigation asked the list to reveal (docs/design-system.md,
   * "Navigation Reveals the Item"), until the address names another, a tab's landing keeps
   * the list's place, or the reader picks a filter. Only it is noted when the list cannot
   * show its row (`noteOutside`): one the reader's own filter leaves out needs no word.
   * @type {number | null}
   */
  let sought = current;
  /**
   * Whether *sought* is still to be placed (`placeSought`): until the list holds its row,
   * or the catalog has said where it is and the list has moved there or stays. Meanwhile
   * the list says nothing of it, except that the catalog lacks it: a pull request opened
   * since the catalog's last read is placed once the catalog reads it.
   */
  let placing = sought !== null;
  /**
   * Where the catalog has *sought* (`readSought`): its state, and whether All's drawn rows
   * reach it; "absent" while the whole catalog lacks it, with the catalog as the read that
   * lacked it saw it (`catalogMark`); null until a read says.
   * @type {{state: "open" | "closed", reach: boolean} | {state: "absent", mark: {epoch: string, fetched: number} | null} | null}
   */
  let soughtFound = null;
  /** The read of *sought*'s place in flight. @type {AbortController | null} */
  let soughtRead = null;
  /**
   * Whether *sought*'s row is still to be revealed (`revealRow`): the first read that brings
   * it reveals it, though the list has moved for it and its first read there failed.
   */
  let revealPending = sought !== null;
  /** Whether focus was in the list when it moved for *sought*, so its row takes focus. */
  let refocus = false;
  /**
   * What the list says of a current pull request it does not hold (`noteOutside`).
   * @type {string | null}
   */
  let outside = null;
  /** The row that takes Tab: the current one, or else the first. @type {number | null} */
  let anchor = null;
  // Whether the reader put the anchor where it is, by a key, a focus, or a press. A grouped
  // list's default anchor is its first row, a stack's row once the stacks arrive.
  let anchorChosen = false;
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
  // The next automatic ask of a list the envelope says to probe (`probe_every_s`): while
  // the tab is shown and visible it asks that often, current or stale, and the server
  // answers each ask with a free conditional read of GitHub, or with the scan when that
  // is due. Without it the tab asks only after a poll, for a stale list, once a window.
  /** @type {unknown} */
  let probeTimer = null;
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
  /** @type {Map<number, RecordAnswer>} */
  const peeked = new Map();
  /** @type {{number: number, controller: AbortController, done: Promise<RecordAnswer | null>} | null} */
  let reading = null;
  /** The read last handed to an opening page, which its page ends, or this panel's end. */
  /** @type {{number: number, controller: AbortController, done: Promise<RecordAnswer | null>} | null} */
  let handed = null;
  /** @type {CoreDemand | null} */
  let coreWanted = null;
  /** @type {CoreDemand | null} */
  let coreSent = null;
  /** Last token that may still own the server window. @type {CoreDemand | null} */
  let coreHeld = null;
  /** The rows last painted as being read from GitHub, joined. */
  let coreRefreshingKey = "";
  let coreEpoch = 0;
  // Traversal can restart while the same accepted producer remains owned.
  let corePass = 0;
  let sendingCore = false;
  /** The demand being sent, which a visible demand aborts. @type {{demand: CoreDemand, controller: AbortController} | null} */
  let coreRequest = null;
  /** The batch last left unanswered, and how many times in a row. @type {{key: string, count: number} | null} */
  let coreMisses = null;
  /** Batches this pass has passed over: one more miss passes over them again. @type {Set<string>} */
  const passedOverCores = new Set();
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
  /** The All prefix revision; tail-only appends leave it unchanged. @type {string | null} */
  let warmGeneration = null;
  /** Earliest retry among settled partial cohorts. @type {number | null} */
  let warmDeferredAt = null;
  // The latest deadline among batches passed over. The walk returns to the top for all of
  // them at once, so it waits for the last, and none is asked for before its own.
  /** @type {number | null} */
  let passedOverUntil = null;
  let warmRetryDelay = CORE_BUSY_RETRY_MS;
  /** @type {unknown} */
  let warmTimer = null;
  /** @type {AbortController | null} */
  let warmRead = null;
  // Counts describe the repository, so switching filters keeps the last accepted tallies.
  /** @type {PullFilterTotals | null} */
  let filterTotals = null;
  // Background prefetch (`PREFETCH_ROUTE`): the scan it last asked after, by the list's
  // `fetched_at`, and whether a request is on its way. An ask made meanwhile waits as the
  // one pending ask, sent when that request answers and built from the panel as it is then,
  // `changed` when any ask that waited had it; null when none waits. A pending ask that only
  // files asks made goes through their checks again when it is sent (`sendFiles`): the
  // answer on its way may have held them, or a walk or a read of the rows in view begun.
  /** @type {string | null} */
  let prefetchedScan = null;
  let prefetching = false;
  /** @type {{changed: boolean, files: boolean} | null} */
  let prefetchPending = null;
  // The lane's report is followed while it works: its next read, and the row it is reading.
  /** @type {unknown} */
  let prefetchTimer = null;
  /** @type {number[]} */
  let prefetchRows = [];
  /** The lane's files outcomes already passed on, to the stack lines and the rows' change
   * lines, by number and time. @type {Set<string>} */
  const listedSeen = new Set();
  // Rows likely to be expanded next, whose changed files a prefetch names beside the open
  // row's and its neighbours': the rows the pointer or focus last rested on, newest first, and
  // the rows in view, in the list's order. A files ask sends them once the rows in view stay
  // put, or at once for a row rested on, and sends nothing when it would repeat the last ask.
  /** @type {number[]} */
  let restedRows = [];
  /** @type {number[]} */
  let viewRows = [];
  /** @type {unknown} */
  let filesTimer = null;
  let lastAsk = "";
  // The `changed` of the last ask sent, which a files ask carries on, so it drops nothing a
  // scan's ask queued.
  let askChanged = false;
  // While the server says the budget admits no background work, a files ask waits a slow
  // poll; a scan's or a landing's ask still goes, and the server answers it from memory.
  /** @type {number | null} */
  let filesHeldUntil = null;

  /** @returns {HeldList} */
  function held() {
    return /** @type {HeldList} */ (lists.get(filter));
  }

  // Grouping by stack. The stacks are the shared optional snapshot's, which the panel hands
  // on as they arrive (`setStacks`); the stacks the reader closed are this panel's.
  // `grouping()` is the rows' order, recomputed only when one of its inputs moves.
  let stackIndex = createStackIndex(null);
  /** The stacks the reader closed, by number. @type {Set<number>} */
  const closedStacks = new Set();
  let groupingInputs = 0;
  /**
   * @type {{
   *   key: string, version: number,
   *   rows: import("./pull-stacks.js").GroupedRow[] | null, closed: import("./pull-stacks.js").StackGroupRow[],
   *   keys: number[], at: Map<number, number>, extra: Map<number, PullRow>,
   * } | null}
   */
  let grouped = null;

  /** The list's rows as they are drawn and walked: its own order, or grouped by stack. */
  function grouping() {
    const list = held();
    const envelope = list.envelope;
    const identity =
      envelope === null ? null : { source: envelope.source, reader: envelope.reader };
    const setSize = envelope?.total ?? Math.max(envelope?.fetched ?? 0, list.rows.length);
    const partial = list.nextAfter !== null;
    const key = JSON.stringify([filter, list.version, groupingInputs, identity, setSize, partial]);
    if (grouped?.key === key) {
      return grouped;
    }
    /** @type {Map<number, PullRow>} */
    const extra = new Map();
    const through = list.rows.at(-1)?.updatedAt;
    const listUpdatedAt = (/** @type {number} */ number) =>
      list.rows[list.keys.get(number) ?? -1]?.updatedAt ?? null;
    if (partial && through) {
      for (const row of stackLeaders(stackIndex, identity, filter, through, listUpdatedAt)) {
        if (!list.keys.has(row.number)) {
          extra.set(row.number, describeRow(row));
        }
      }
    }
    const numbers = [...list.rows.map((row) => row.number), ...extra.keys()];
    const answer = groupByStack(numbers, stackIndex, identity, {
      collapsed: closedStacks,
      setSize,
      updatedAt: (number) => listUpdatedAt(number) ?? extra.get(number)?.updatedAt ?? null,
    });
    // Stacks unknown, another reader's, or holding no listed pull request group nothing
    // (`groupByStack` places a row only by the list's own reader's membership).
    const rows = answer.stacks > 0 ? answer.rows : null;
    const keys = rows === null ? numbers : rows.map((row) => row.key);
    grouped = {
      key,
      version: (grouped?.version ?? 0) + 1,
      rows,
      closed: (rows ?? []).flatMap((row) => (row.kind === "stack" && !row.expanded ? [row] : [])),
      keys,
      at: new Map(keys.map((row, index) => [row, index])),
      extra,
    };
    return grouped;
  }

  /** @param {number} number */
  function rowFor(number) {
    const list = held();
    return list.rows[list.keys.get(number) ?? -1] ?? grouping().extra.get(number);
  }

  /** The row of a closed stack that holds pull request *number*, or whose Stack Overview row
   * *number* keys, if one does. @param {number} number */
  function closedStackOf(number) {
    const whole = wholeStackOfKey(number);
    return (
      grouping().closed.find((row) =>
        whole === null ? row.members.includes(number) : row.stack.number === whole,
      ) ?? null
    );
  }

  /** The row key the current-row mark is on: the current pull request's, or the Stack Overview
   * row of the stack whose page the address names. */
  function currentKey() {
    return current ?? (currentStack === null ? null : wholeStackRowKey(currentStack));
  }

  /** The stack a drawn pull request's row sits under, if any. @param {number} number */
  function stackOfRow(number) {
    const order = grouping();
    const at = order.at.get(number);
    const row = at === undefined ? undefined : order.rows?.[at];
    return row?.kind === "pull" ? row.stack : null;
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
    if (!coreLive() || walkingTo !== null || (!warming && visibleCoreAt >= visibleCores.length)) {
      cancelWarmTimer();
      return;
    }
    // A known reset owns the same one-shot queue timer while the source is held.
    if (warmPaused) {
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

  /** @param {{outcome?: string, reset_at?: string | null} | null | undefined} failure */
  function pauseCoreQueue(failure) {
    warmPaused = true;
    cancelWarmTimer();
    if (!coreLive() || WATCH_PAUSED.has(failure?.outcome ?? "")) {
      return;
    }
    const reset = typeof failure?.reset_at === "string" ? Date.parse(failure.reset_at) : NaN;
    // A reset still ahead is the one wake worth waiting for. One already past backs off
    // like any other hold: waiting for it meant a retry every second while the walk was
    // held for another reason, such as the catalog's backfill (review B1 of #761).
    const delay =
      Number.isFinite(reset) && reset > deps.now()
        ? Math.max(CORE_BUSY_RETRY_MS, reset - deps.now())
        : warmRetryDelay;
    warmRetryDelay = Math.min(warmRetryDelay * 2, SLOW_POLL_MS);
    warmTimer = deps.schedule(() => {
      warmTimer = null;
      warmPaused = false;
      // Refresh the held generation before retrying revoked or failed demand.
      // This reads local metadata; askIfDue retains provider freshness admission.
      readAhead = readAhead || (!shown && warming);
      void poll(true).finally(() => pumpCores());
    }, delay);
  }

  /** @param {boolean} [release] Whether the catalog identity revoked its producer. */
  function restartCorePass(release = true) {
    corePass += 1;
    passedOverCores.clear();
    warmAfter = null;
    warmGeneration = null;
    warmDeferredAt = null;
    passedOverUntil = null;
    warming = true;
    warmPaused = false;
    visibleCoreKey = "";
    visibleCores = [];
    visibleCoreAt = 0;
    primeHeldCores = true;
    if (release) {
      clearCoreWindow();
    }
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
    if (list.envelope?.reason === "not_github") {
      warming = false;
      return;
    }
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
    if (
      primeHeldCores &&
      visibleCores.length === 0 &&
      (list.envelope?.refreshing ||
        list.envelope?.state === "absent" ||
        list.envelope?.state === "pending")
    ) {
      // A cold startup's first catalog page may arrive after the refresh POST.
      // Read that selected/default filter before walking the rest of All.
      await poll(true);
      pauseCoreQueue(list.envelope?.last_refresh);
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
        pauseCoreQueue(null);
        return;
      }
      const envelope = response.body;
      const identity = coreCatalogIdentity(envelope);
      if (identity !== null && warmIdentity !== null && identity !== warmIdentity) {
        warmIdentity = identity;
        restartCorePass();
        queueCores();
        return;
      }
      warmIdentity = identity;
      if (
        warmGeneration !== null &&
        envelope.generation !== null &&
        envelope.generation !== warmGeneration
      ) {
        // A new or changed leading row can sit above the settled cursor.
        // Revisit that prefix; durable cache hits do not repeat provider work.
        warmAfter = null;
        warmGeneration = envelope.generation;
        queueCores();
        return;
      }
      warmGeneration = envelope.generation;
      if (
        envelope.reason === "not_github" ||
        refreshFailure(envelope, deps.formatTime) !== null ||
        rateHoldMs(envelope, deps.now()) > 0
      ) {
        pauseCoreQueue(envelope.last_refresh);
        return;
      }
      if (envelope.rows.length === 0) {
        if (envelope.complete && !envelope.refreshing && envelope.state !== "absent") {
          if (warmDeferredAt !== null || passedOverUntil !== null) {
            const retryAt = Math.max(warmDeferredAt ?? 0, passedOverUntil ?? 0);
            warmDeferredAt = null;
            passedOverUntil = null;
            warmAfter = null;
            // Later rows have had their turn. Revisit only after the partial cohort's
            // existing attempt lease and every passed-over batch's deadline; successful
            // siblings stay cached.
            pauseCoreQueue({ reset_at: new Date(retryAt).toISOString() });
          } else {
            warming = false;
            warmRetryDelay = CORE_BUSY_RETRY_MS;
          }
        } else {
          pauseCoreQueue(envelope.last_refresh);
        }
        return;
      }
      if (typeof envelope.generation !== "string") {
        pauseCoreQueue(null);
        return;
      }
      // A visible demand may have arrived during this cache read.
      if (shown && visibleCoreAt < visibleCores.length) {
        queueCores();
        return;
      }
      const rows = envelope.rows.map((row) => describeRow(row));
      prepareBatch(rows, "all", envelope.generation, contentOf(envelope), "background");
    } catch {
      if (!controller.signal.aborted) {
        pauseCoreQueue(null);
      }
    } finally {
      if (warmRead === controller) {
        warmRead = null;
      }
    }
  }

  /**
   * @param {CoreWindowRequest} body
   * @param {AbortSignal} signal
   */
  async function controlCoreWindow(body, signal) {
    try {
      return await deps.request("POST", CORE_PREPARE_ROUTE, { body, signal });
    } catch {
      return null;
    }
  }

  /**
   * One demand's request, ended by its lane's timeout or by `controller`.
   * @param {CoreDemand} demand
   * @param {AbortController} controller
   */
  async function requestCoreWindow(demand, controller) {
    const timeout = deps.schedule(
      () => controller.abort(),
      demand.lane === "visible" ? CORE_VISIBLE_TIMEOUT_MS : CORE_BACKGROUND_TIMEOUT_MS,
    );
    try {
      return await controlCoreWindow(demand.body, controller.signal);
    } finally {
      deps.cancel(timeout);
    }
  }

  /** @param {CoreDemand} demand */
  function releaseCoreWindow(demand) {
    // An exact-owner release must still be sendable after panel disposal.
    return controlCoreWindow(
      { ...demand.body, numbers: [] },
      AbortSignal.timeout(CORE_RELEASE_TIMEOUT_MS),
    );
  }

  /** @param {CoreDemand} demand */
  function coreBatchKey(demand) {
    return JSON.stringify([demand.lane, demand.body.state, demand.body.numbers]);
  }

  /**
   * Count a batch the server left unanswered; pass it over after `CORE_MAX_MISSES` in a row,
   * or after one when it was passed over before, so a revisit costs one attempt.
   * @param {CoreDemand} demand
   */
  function noteCoreMiss(demand) {
    const key = coreBatchKey(demand);
    const count = coreMisses?.key === key ? coreMisses.count + 1 : 1;
    coreMisses = { key, count };
    if (count < (passedOverCores.has(key) ? 1 : CORE_MAX_MISSES)) {
      return;
    }
    coreMisses = null;
    passedOverCores.add(key);
    if (demand.lane === "background") {
      warmAfter = demand.body.numbers.at(-1) ?? warmAfter;
    } else if (demand.queueKey === visibleCoreKey) {
      visibleCoreAt += demand.body.numbers.length;
    }
    // The walk revisits it after its pass, not before its slowest retry has passed.
    warming = true;
    passedOverUntil = Math.max(passedOverUntil ?? 0, deps.now() + SLOW_POLL_MS);
  }

  function cancelCoreRetry() {
    if (coreWanted !== null) {
      coreWanted.canRetry = false;
    }
    if (coreRetryTimer !== null) {
      deps.cancel(coreRetryTimer);
      coreRetryTimer = null;
    }
    // The panel no longer follows the batch, so its titles stop saying GitHub is read for them.
    noteCoreRefreshing();
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
        const controller = new AbortController();
        coreRequest = { demand, controller };
        const response = await requestCoreWindow(demand, controller);
        coreRequest = null;
        const receipt =
          /** @type {{preparation?: string, ready_numbers?: number[], skipped_numbers?: number[], retry_numbers?: number[], retry_at?: string, failure?: {outcome?: string, reset_at?: string | null} | null} | null | undefined} */ (
            response?.body
          );
        const admitted =
          response?.status === 202 &&
          (receipt?.preparation === "started" || receipt?.preparation === "joined");
        if (admitted) {
          // GitHub is being read for these rows now; their titles breathe until it settles.
          demand.admitted = true;
          noteCoreRefreshing();
        }
        const settled =
          response?.status === 200 &&
          (receipt?.preparation === "ready" || receipt?.preparation === "partial");
        const busy = response?.status === 200 && receipt?.preparation === "busy";
        const preserved =
          busy || (response?.status === 200 && receipt?.preparation === "not_owner");
        if (settled) {
          // Coverage does not claim this token: a cache-only answer may have
          // retained the previous server window. Release its exact owner before
          // advancing the queue, including when this same token just settled.
          coreHeld = null;
          if (previous !== null) {
            await releaseCoreWindow(previous);
          }
        } else if (!preserved) {
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
          demand.pass !== corePass &&
          !admitted &&
          demand === coreWanted &&
          demand.canRetry &&
          coreLive()
        ) {
          // Keep polling a retained producer until it settles, but its old receipt
          // cannot advance, defer or pause the traversal that replaced its pass.
          demand.done = true;
          queueCores();
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
          } else if (receipt?.preparation === "ready" || receipt?.preparation === "partial") {
            const accounted = [
              ...(receipt.ready_numbers ?? []),
              ...(receipt.skipped_numbers ?? []),
              ...(receipt.preparation === "partial" ? (receipt.retry_numbers ?? []) : []),
            ];
            const settled = new Set(accounted);
            const retryAt =
              receipt.preparation === "partial" ? Date.parse(receipt.retry_at ?? "") : null;
            if (
              accounted.length !== demand.body.numbers.length ||
              settled.size !== demand.body.numbers.length ||
              !demand.body.numbers.every((number) => settled.has(number)) ||
              (retryAt !== null &&
                (!Number.isFinite(retryAt) || (receipt.retry_numbers?.length ?? 0) === 0))
            ) {
              demand.done = true;
              pauseCoreQueue(null);
              continue;
            }
            demand.done = true;
            warmRetryDelay = CORE_BUSY_RETRY_MS;
            coreMisses = null;
            passedOverCores.delete(coreBatchKey(demand));
            if (retryAt !== null) {
              warming = true;
              warmDeferredAt =
                warmDeferredAt === null ? retryAt : Math.min(warmDeferredAt, retryAt);
            }
            if (demand.lane === "visible" && demand.queueKey === visibleCoreKey) {
              visibleCoreAt += demand.body.numbers.length;
            } else if (demand.lane === "background") {
              warmAfter = demand.body.numbers.at(-1) ?? warmAfter;
            }
            queueCores();
          } else if (receipt?.preparation === "not_owner") {
            // Re-read the catalog before retrying either lane. Repeated revocations
            // back off rather than reissuing a fresh token every second.
            demand.done = true;
            pauseCoreQueue(null);
          } else {
            demand.done = true;
            if (receipt?.preparation !== "failed" && receipt?.preparation !== "held") {
              // A source-wide failure holds every batch; no answer at all holds only this one.
              noteCoreMiss(demand);
            }
            pauseCoreQueue(receipt?.failure);
          }
        }
      }
    } finally {
      sendingCore = false;
      noteCoreRefreshing();
    }
  }

  /**
   * The rows GitHub is being read for: an admitted batch the panel still follows, live and
   * retrying until it settles. Offline, a selection, or an address that cancels the retry
   * ends it, as a settled or replaced batch does.
   */
  function coreRefreshing() {
    return coreWanted !== null &&
      coreWanted.admitted === true &&
      !coreWanted.done &&
      coreWanted.canRetry &&
      coreLive()
      ? coreWanted.body.numbers
      : [];
  }

  /** Paint again when the rows being read change, which nothing else would repaint for. */
  function noteCoreRefreshing() {
    const key = coreRefreshing().join(",");
    if (key !== coreRefreshingKey) {
      coreRefreshingKey = key;
      render();
    }
  }

  function clearCoreWindow() {
    cancelCoreRetry();
    coreEpoch += 1;
    coreWanted = null;
    // Nothing wants the batch on its way any more, so it does not hold up the release
    // behind it, and the server stops it. A release is never aborted here.
    coreRequest?.controller.abort();
    noteCoreRefreshing();
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
      pass: corePass,
      canRetry: true,
      retryDelay: CORE_BUSY_RETRY_MS,
      body: { state, window: { id, generation }, numbers: rows.map((row) => row.number), lane },
    };
    if (lane === "visible") {
      // The batch on its way is no longer wanted, so what the reader sees does not wait for
      // it. The server stops it at its next step; its ownership is settled as for any
      // request that went unanswered. Its lane tells the server to preempt a background
      // job that request started, unless that job reads rows this batch needs.
      coreRequest?.controller.abort();
    }
    noteCoreRefreshing();
    void sendCoreWindow();
  }

  /** Queue the whole measured viewport; eight is only the server's transport batch size.
   * @param {number[]} numbers
   */
  function prepareVisible(numbers) {
    if (!live() || !online() || walkingTo !== null) {
      return;
    }
    if (numbers.join(",") !== viewRows.join(",")) {
      // Their changed files are asked for once they stay put, after their own metadata.
      viewRows = numbers.slice();
      if (numbers.length > 0) {
        askFiles(FILES_DWELL_MS);
      }
    }
    const list = held();
    if (typeof list.envelope?.generation !== "string" || list.content === null) {
      return;
    }
    const rows = numbers.flatMap((number) => {
      const row = rowFor(number);
      return row === undefined ? [] : [row];
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
    const order = grouping();
    return describePulls(list.envelope, {
      stacks: { rows: order.rows, version: order.version },
      filter,
      rows: order.extra.size ? [...list.rows, ...order.extra.values()] : list.rows,
      rowsVersion: list.version,
      filterTotals,
      nowMs: deps.now(),
      formatTime: deps.formatTime,
      formatCount: deps.formatCount,
      more: list.more,
      error: list.error,
      checkout,
      online: online(),
      requesting: refreshReads.size > 0,
      refreshingRows: [...new Set([...coreRefreshing(), ...prefetchRefreshing()])],
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
    const key = JSON.stringify([
      { ...next, rows: null, stacks: { ...next.stacks, rows: null } },
      identity,
      held().content,
    ]);
    if (key !== painted || arrivals.length > 0) {
      painted = key;
      deps.render(next, identity, arrivals);
    } else {
      deps.retellAges?.();
    }
    noteOutside();
  }

  function clearTimer() {
    if (timer !== null) {
      deps.cancel(timer);
      timer = null;
    }
  }

  function clearProbeTimer() {
    if (probeTimer !== null) {
      deps.cancel(probeTimer);
      probeTimer = null;
    }
  }

  /**
   * Schedule the shown list's next probe ask, `probe_every_s` after its last ask, or at
   * once for a list not asked for within that, as when the tab is shown or wakes. After an
   * ask that was *tried* and not sent, for one on its way or a limit that holds, the next
   * waits a whole interval, so a list that cannot be asked for is not asked for in a loop.
   *
   * @param {boolean} [tried]
   */
  function scheduleProbe(tried = false) {
    clearProbeTimer();
    const list = held();
    const every = list.envelope?.probe_every_s;
    if (!live() || !online() || typeof every !== "number" || !(every > 0)) {
      return;
    }
    const everyMs = every * 1000;
    const dueInMs = list.askedAt === null ? 0 : list.askedAt + everyMs - deps.now();
    probeTimer = deps.schedule(
      () => {
        probeTimer = null;
        if (!askWhenDue(true)) {
          scheduleProbe(true);
        }
      },
      tried ? everyMs : Math.max(0, dueInMs),
      // Named, so a session that drives the panel's timers by hand can tell this one from
      // the poll's.
      "probe",
    );
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
    const next = rows.map((row) => describeRow(row));
    if (source !== null) {
      noteListed(source, filter, next);
    }
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
    const previous = list.envelope;
    list.envelope = envelope;
    if (JSON.stringify(previous?.refresh_timing) !== JSON.stringify(envelope.refresh_timing)) {
      deps.refreshDetailChanged?.();
    }
    const identity = coreCatalogIdentity(envelope);
    if (warmIdentity === null) {
      // Bind the startup hint before its first batch, not only when All is read.
      warmIdentity = identity;
    }
    if (
      identity !== null &&
      warmIdentity !== null &&
      (identity !== warmIdentity ||
        (typeof previous?.generation === "string" && envelope.generation !== previous.generation))
    ) {
      const replaced = identity !== warmIdentity;
      warmIdentity = identity;
      restartCorePass(replaced);
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

  /**
   * The anchor follows the rows: the current one if it is drawn, and otherwise the first. A
   * stack's row the reader moved to keeps it until the address moves (*follow*), since no
   * page stands for it; a pull request hidden in a closed stack is held by the stack's row;
   * and a grouped list's anchor no reader chose is its first row, a stack's.
   *
   * @param {boolean} [follow]
   */
  function settleAnchor(follow = false) {
    const order = grouping();
    const hiddenIn = (/** @type {number | null} */ number) => {
      const stack =
        number === null || (number < 0 && wholeStackOfKey(number) === null)
          ? null
          : closedStackOf(number);
      return stack === null ? null : stack.key;
    };
    const marked = currentKey();
    const next =
      !follow && anchor !== null && anchor < 0 && order.at.has(anchor)
        ? anchor
        : marked !== null && order.at.has(marked)
          ? marked
          : (hiddenIn(marked) ??
            (anchor !== null && order.at.has(anchor) && (anchorChosen || order.rows === null)
              ? anchor
              : null) ??
            hiddenIn(anchor) ??
            order.keys[0] ??
            null);
    if (next !== anchor) {
      const previous = anchor;
      anchor = next;
      deps.markAnchor(previous, next, false);
    }
  }

  /**
   * Open the stack over pull request *number*'s row where the list groups it under one the
   * reader closed. The one place a reveal unfolds, so a row reveals the same whether the
   * list held it when its address was named or it arrived later (`revealRow`).
   *
   * Only for the pull request a navigation named and has not revealed yet (*sought*,
   * *revealPending*): opening the item opens what the reader folded over it. A row shown
   * again for any other reason, the tab shown again, a filter picked, a tab's landing that
   * keeps the list's place, is the reader asking for the list, not the item, and what they
   * folded stays folded (docs/design-system.md, "Navigation Reveals the Item").
   *
   * Whether the stack opened, and so the rows were drawn again.
   *
   * @param {number | null} number
   */
  function unfoldOver(number) {
    const over =
      number === null || number !== sought || !revealPending ? null : closedStackOf(number);
    if (over === null) {
      return false;
    }
    closedStacks.delete(over.stack.number);
    groupingInputs += 1;
    render();
    return true;
  }

  /**
   * Show the current pull request's row: a closed stack that holds it opens, as a file the
   * address names opens its folders, and the row scrolls into view; one the filter leaves
   * out moves the list to one that draws it (`placeSought`), a row the list has not reached
   * yet is chased, and one it cannot show is noted (`noteOutside`).
   *
   * @param {number | null} number
   */
  function showCurrent(number) {
    unfoldOver(number);
    settleAnchor(true);
    if (placeSought(true)) {
      return;
    }
    if (number !== null && rowFor(number) !== undefined) {
      revealRow(number);
    } else {
      chaseCurrent();
    }
    noteOutside();
  }

  /**
   * Show the Stack Overview row of the stack whose page the address names, as a pull request's
   * row is shown (`showCurrent`): its stack opens if the reader closed it, and the row scrolls
   * into view. A stack none of whose pull requests this list holds has no row to show.
   *
   * @param {number} stack
   */
  function showWholeStack(stack) {
    if (closedStacks.delete(stack)) {
      groupingInputs += 1;
      render();
    }
    settleAnchor(true);
    wholeRevealPending = true;
    revealWholeStack();
  }

  /** Reveal the current stack's Stack Overview row if it is still to be revealed and is drawn
   * now (*wholeRevealPending*). */
  function revealWholeStack() {
    if (!wholeRevealPending || currentStack === null) {
      return;
    }
    const key = wholeStackRowKey(currentStack);
    if (!grouping().at.has(key)) {
      return;
    }
    wholeRevealPending = false;
    if (revealCurrent) {
      deps.reveal(key);
    }
  }

  /**
   * Open the page of *stack*, as a row's open opens a pull request's (`openRow`): its Stack
   * Overview row takes the current-row mark at once, and the address follows. *replace* is a
   * key's, which replaces the history entry, as a skim of pull requests does.
   *
   * @param {number} stack
   * @param {boolean} replace
   */
  function openStack(stack, replace) {
    cancelCoreRetry();
    opening += 1;
    const previous = currentKey();
    const next = wholeStackRowKey(stack);
    if (previous !== next) {
      current = null;
      currentStack = stack;
      deps.markCurrent(previous, next);
    }
    deps.openStack?.(stack, replace);
  }

  /**
   * A navigation named *number*, or, for null, none is to be placed: the address names no
   * pull request, a tab's landing keeps the list's place, or the reader picked a filter.
   *
   * @param {number | null} number
   */
  function seek(number) {
    sought = number;
    placing = number !== null;
    revealPending = number !== null;
    soughtFound = null;
    soughtRead?.abort();
    soughtRead = null;
    refocus = false;
  }

  /**
   * Reveal a row the list holds; the pull request a navigation named also takes focus when
   * focus was in the list as the list moved for it (`placeSought`), since the move drew the
   * list again and the row that had focus went with it. Only while focus is where that left
   * it, in the list or nowhere: focus the reader moved elsewhere while the list read is
   * theirs.
   *
   * @param {number} number
   */
  function revealRow(number) {
    // The row a navigation named may have arrived under a stack the reader closed after its
    // address was named: the list moved to a filter that holds it, or read the window it is
    // in (`placeSought`, `chaseCurrent`). A row revealed for any other reason unfolds nothing
    // (`unfoldOver`).
    if (unfoldOver(number)) {
      settleAnchor(true);
    }
    if (revealCurrent) {
      deps.reveal(number);
    }
    if (number !== sought) {
      return;
    }
    revealPending = false;
    if (refocus) {
      refocus = false;
      if (deps.focusPlace?.() !== "elsewhere") {
        anchorChosen = true;
        const previous = anchor;
        anchor = number;
        deps.markAnchor(previous, number, true);
      }
    }
  }

  /**
   * Put the pull request a navigation named where the list draws it. Open and Closed hold
   * only their state's pull requests, so for one the filter leaves out the list moves, as a
   * reveal opens a stack the reader closed: to All, which holds every pull request, when
   * All's drawn rows reach it, so that a stack walk across open and merged pull requests
   * stays on one list, and otherwise to the list of its own state, which reaches as far or
   * further, All included: All draws only its newest rows, so an older pull request is
   * further down All than it draws. Where it is comes from the catalog (`readSought`), not
   * from the windows the list has read, which cannot tell an older pull request from one the
   * filter leaves out, nor a catalog still being read from GitHub from one that has ended. A
   * list that holds it, or one that draws it, stays. A filter the reader picks afterwards is
   * theirs. Whether the list moved.
   *
   * @param {boolean} [mayRead] Whether this may ask the catalog: at a navigation and after a
   *   poll, so a place still unknown, as a catalog being read from GitHub leaves it, is asked
   *   for once a poll, and not at every window the list pages in; and one the catalog lacked
   *   is asked for again after a poll whose list says the catalog has read more since.
   */
  function placeSought(mayRead = false) {
    if (!placing || sought === null || sought !== current) {
      return false;
    }
    const list = held();
    if (rowFor(sought) !== undefined || list.envelope?.reason === "not_github") {
      placing = false;
      return false;
    }
    const now = catalogMark(list.envelope);
    if (soughtFound?.state === "absent" && now !== null && soughtFound.mark?.epoch !== now.epoch) {
      // A catalog started again, for a new reader or source, has not said yet what the old
      // one lacked: the list says nothing until it does.
      soughtFound = null;
      noteOutside();
    }
    if (soughtFound === null || soughtFound.state === "absent") {
      // A catalog that lacked it is asked again once it has read more pull requests, as it
      // does when one is opened, so an unchanged catalog is not asked at every poll.
      if (mayRead && (soughtFound === null || soughtFound.mark?.fetched !== now?.fetched)) {
        void readSought();
      }
      return false;
    }
    placing = false;
    const target = filter === soughtFound.state || !soughtFound.reach ? soughtFound.state : "all";
    if (target === filter) {
      return false;
    }
    refocus = deps.focusPlace?.() === "list";
    setFilter(target, { reveal: true });
    return true;
  }

  /**
   * Ask the cache for the pull request and how many rows precede it in All. The server
   * caps the indexed count at the requested depth. A missing row can be absent only
   * once the catalog is complete, or when the route refuses the number.
   */
  async function readSought() {
    if (sought === null || soughtRead !== null) {
      return;
    }
    const number = sought;
    const controller = new AbortController();
    soughtRead = controller;
    try {
      const limit = DISPLAY_ROWS;
      const at = await deps.request("GET", `${PULLS_ROUTE}?state=all&limit=${limit}&at=${number}`, {
        signal: controller.signal,
      });
      if (disposed || controller.signal.aborted || sought !== number) {
        return;
      }
      const from = at.status === 200 && isEnvelope(at.body) ? at.body : null;
      const refused = at.status >= 400 && at.status < 500 && !pinChanged(at);
      const row = from?.rows[0];
      if (row?.number === number) {
        soughtFound = {
          state: row.state === "open" ? "open" : "closed",
          reach:
            lists.get("all")?.keys.has(number) === true ||
            (typeof from?.position === "number" && from.position < limit),
        };
      } else if (refused || (from?.complete && from.reason === null)) {
        soughtFound = { state: "absent", mark: catalogMark(from ?? held().envelope) };
      } else {
        return;
      }
    } catch {
      return;
    } finally {
      if (soughtRead === controller) {
        soughtRead = null;
      }
    }
    if (placeSought()) {
      return;
    }
    chaseCurrent();
    noteOutside();
  }

  /**
   * Say so when a pull request a navigation named is in no row the list can draw, rather
   * than leave the reader looking for it: the catalog lacks it, or it is in this list
   * further down than the list draws. Only once its place is known and the list stays,
   * and not while the list is still filling its rows toward it; once said, a page the
   * reader asks for at the list's end keeps it until a page brings the row, rather than
   * take it back for the page's read and say it again. A pull request the reader's own
   * filter leaves out is not noted.
   */
  function noteOutside() {
    const list = held();
    let next = null;
    if (
      current !== null &&
      current === sought &&
      soughtFound !== null &&
      (!placing || soughtFound.state === "absent") &&
      list.envelope !== null &&
      list.error === null &&
      rowFor(current) === undefined
    ) {
      const further = outsideText(current, true);
      if (soughtFound.state === "absent") {
        next = outsideText(current, false);
      } else if (
        (filter === "all" || filter === soughtFound.state) &&
        list.nextAfter !== null &&
        (list.rows.length >= list.displayLimit || outside === further)
      ) {
        next = further;
      }
    }
    if (next !== outside) {
      outside = next;
      deps.markOutside?.(next);
    }
  }

  /**
   * Read further windows for a current row the panel has not reached, as far as it can be:
   * under All, which holds every pull request, or under the filter of the state the catalog
   * says a navigated pull request has (`readSought`). Otherwise the address may name one
   * the list does not have, and chasing it would read every window to the end for nothing.
   */
  let chasing = false;
  function chaseCurrent() {
    const list = held();
    if (
      current !== sought ||
      soughtFound === null ||
      soughtFound.state === "absent" ||
      !(filter === "all" || soughtFound.state === filter) ||
      current === null ||
      rowFor(current) !== undefined ||
      list.nextAfter === null ||
      list.rows.length >= list.displayLimit
    ) {
      return;
    }
    chasing = true;
    void loadWindow();
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
    const previousIdentity = list.envelope === null ? null : coreCatalogIdentity(list.envelope);
    holdRows(list, rows, top.source);
    list.nextAfter = after;
    list.content = content;
    peeked.clear();
    // An accepted producer rechecks individual members before publication. A prefix
    // revision alone must not cancel it and strand unchanged rows behind attempt leases.
    if (previousIdentity === null || previousIdentity !== coreCatalogIdentity(top)) {
      clearCoreWindow();
    }
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
          list.error = unavailableText("The list");
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
    // A list's first rows reveal the current row, and so does any read that brings the row
    // of a pull request a navigation named before it has been revealed.
    const awaited = first || (revealPending && sought === current);
    if (awaited && shown && current !== null && rowFor(current) !== undefined) {
      revealRow(current);
    }
    if (shown) {
      revealWholeStack();
    }
    if (placeSought(true)) {
      // The list it moved to reveals it, and this list's reads end with its filter.
      return;
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
    prefetchAfterScan();
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
   * server holds it to one attempt a window. A shown list the envelope says to probe is
   * also asked for every `probe_every_s` whatever its state, on a timer of its own
   * (`scheduleProbe`).
   */
  function askIfDue() {
    askWhenDue(false);
    scheduleProbe();
  }

  /**
   * @param {boolean} probing Whether the probe's timer asks, for a list current or stale.
   * @returns {boolean} Whether an ask was sent.
   */
  function askWhenDue(probing) {
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
      return false;
    }
    const priority = shown && prioritizeFilter;
    prioritizeFilter = false;
    if (rateHoldMs(envelope, deps.now()) > 0) {
      return false;
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
      return false;
    }
    const target = Math.min(list.displayLimit, envelope.total ?? list.displayLimit);
    const missingRows = envelope.fetched < target;
    const foreground = priority && missingRows && !reconnect;
    const needsRows = missingRows && (foreground || list.priorityTarget < target);
    const needsCatalog = !envelope.complete && !envelope.refreshing;
    // A list the server probes: a catalog whose last refresh did not fail, with no job
    // running. Its asks keep the probe's interval, not the window.
    const probeIntervalMs =
      probing &&
      shown &&
      typeof envelope.probe_every_s === "number" &&
      envelope.probe_every_s > 0 &&
      !envelope.refreshing &&
      (envelope.state === "current" || envelope.state === "stale") &&
      (last === null || last.outcome === "succeeded")
        ? envelope.probe_every_s * 1000
        : null;
    if (
      !reconnect &&
      !needsRows &&
      !needsCatalog &&
      probeIntervalMs === null &&
      (envelope.refreshing ||
        (!failureDue && envelope.state !== "absent" && envelope.state !== "stale"))
    ) {
      return false;
    }
    if (
      !reconnect &&
      !needsRows &&
      list.askedAt !== null &&
      now - list.askedAt < (probeIntervalMs ?? windowMs)
    ) {
      return false;
    }
    list.askedAt = now;
    list.priorityTarget = target;
    void ask({
      state: filter,
      target: list.displayLimit,
      ...(foreground ? {} : { background: true }),
      ...(reconnect ? { reconnect: true } : {}),
    });
    return true;
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
      const answer = /** @type {{pulls?: unknown, code?: unknown} | null} */ (response.body);
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
        // Whether the ask started the scan of every open pull request's status, or found one
        // running, and when the latest one ended, for the rows' readiness (row-readiness.js,
        // `scanned`).
        const scan = /** @type {{status_scan?: unknown, status_scan_at?: unknown}} */ (answer);
        deps.statusScan?.(scan.status_scan, scan.status_scan_at);
        if (response.status === 202) {
          // The answer changed; the next poll must not be answered by a 304.
          list.etag = null;
        } else {
          list.more = false;
        }
      } else if (reader) {
        const code = answer !== null && typeof answer.code === "string" ? answer.code : null;
        if (!pinChanged(response)) {
          list.error = refreshRefusedText("The refresh", code);
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
      scheduleProbe();
      if (warming) {
        queueCores();
      }
    }
  }

  /**
   * The anchored row's neighbours, the pull requests a key reaches next, a stack's row passed
   * over: the rows as they are drawn and walked, grouped by stack or not.
   *
   * @returns {number[]}
   */
  function neighbours() {
    const order = grouping();
    const at = anchor === null ? -1 : (order.at.get(anchor) ?? -1);
    /** @type {number[]} */
    const near = [];
    for (let index = at - 1; index >= 0; index -= 1) {
      if (order.keys[index] > 0) {
        near.push(order.keys[index]);
        break;
      }
    }
    const after = order.keys.slice(at + 1).find((key) => key > 0);
    if (after !== undefined) {
      near.push(after);
    }
    return near;
  }

  /**
   * Warm the comparisons of the pull requests the reader is likely to open next, in the
   * document's keep (comparison-prefetch.js, `createComparisonWarmer`), so a page opened on
   * one draws its Diff summary, and its Changes, with no wait: the open pull request first,
   * so a warm of it already on its way is its page's rather than a second request, then the
   * rows the pointer or focus last rested on, newest first, the open pull request's
   * neighbours in each of its stacks, which Control-N and Control-P reach, and the anchored
   * row's neighbours in the list. Only while shown, visible, and online (`stopWarming`);
   * each is local work, a record from the cache and a comparison from the repository store,
   * with no GitHub call, so the budget's floor and the lane's caps do not hold it, and the
   * warmer's own do. Its record reads are not views, so they add nothing to the records the
   * server's lane refreshes after a scan.
   */
  function warmAhead() {
    const list = held();
    if (
      deps.warmComparisons === undefined ||
      !live() ||
      !online() ||
      list.envelope === null ||
      list.envelope.reason === "not_github" ||
      list.rows.length === 0
    ) {
      return;
    }
    const identity = { source: list.envelope.source, reader: list.envelope.reader };
    const stacked =
      current === null
        ? []
        : stackMembership(stackIndex, identity, current).flatMap((stack) => {
            const at = stack.pulls.indexOf(current ?? 0);
            return [stack.pulls[at + 1], stack.pulls[at - 1]].filter(
              (number) => number !== undefined,
            );
          });
    const listed = (/** @type {number} */ number) => rowFor(number) !== undefined;
    deps.warmComparisons([
      ...new Set([
        ...(current === null ? [] : [current]),
        ...restedRows.filter(listed),
        ...stacked,
        ...neighbours(),
      ]),
    ]);
  }

  /**
   * A panel that is hidden, parked, or offline warms nothing more: its queue is emptied, and
   * only the warm being read goes on.
   */
  function stopWarming() {
    deps.warmComparisons?.([]);
  }

  /**
   * Ask the server to refresh, behind the reader, what they are likely to open next: the
   * anchored row's neighbours and the top of the list, and the changed files of the rows the
   * pointer or focus last rested on, the open row, its neighbours, and the rows in view.
   * *changed* adds what the server answered most recently that the scan just found changed.
   * Only while shown, visible, and online; the server reads each again, admits what is due
   * within its caps and the budget's floor, and waits behind any reader's work. A
   * *filesAsk* is `sendFiles`'s: it sends nothing when it would repeat the last ask sent,
   * and, waiting behind the one on its way, it is checked again when that one answers.
   *
   * @param {boolean} changed
   * @param {boolean} [filesAsk]
   * @returns {boolean} Whether a request was sent, or waits behind the one on its way.
   */
  function prefetch(changed, filesAsk = false) {
    const list = held();
    if (
      !live() ||
      !online() ||
      list.envelope === null ||
      list.envelope.reason === "not_github" ||
      // GitHub refused the list's own refresh, and would refuse the prefetch too.
      (list.envelope.last_refresh !== null && list.envelope.last_refresh.outcome !== "succeeded") ||
      list.rows.length === 0
    ) {
      return false;
    }
    if (prefetching) {
      prefetchPending = {
        changed: (prefetchPending?.changed ?? false) || changed,
        // A scan's or a landing's ask that waits goes as it is; only files asks are checked.
        files: (prefetchPending?.files ?? true) && filesAsk,
      };
      return true;
    }
    const order = grouping();
    const pulls = order.keys.filter((key) => key > 0);
    const near = neighbours();
    const top = pulls.slice(0, PREFETCH_TOP_ROWS);
    // The open row's record is the page's own refresh; its files are the tree under its row.
    const records = [...new Set([...near, ...top])].filter((number) => number !== current);
    const listed = (/** @type {number} */ number) => rowFor(number) !== undefined;
    const own = [
      ...new Set([
        ...restedRows.filter(listed),
        ...(current === null ? [] : [current]),
        ...near,
        ...viewRows.filter(listed),
      ]),
    ];
    // After the reader's own rows, the members the drawn stacks' lines wait for, which keep
    // a few places of their own (B2 of review B on #484).
    const members = (deps.stackFiles?.() ?? []).filter((number) => !own.includes(number));
    const reserved = Math.min(PREFETCH_STACK_FILES, members.length);
    const files = [...own.slice(0, PREFETCH_FILES - reserved), ...members].slice(0, PREFETCH_FILES);
    const key = JSON.stringify([records, files, changed]);
    if (filesAsk && key === lastAsk) {
      return false;
    }
    lastAsk = key;
    askChanged = changed;
    prefetching = true;
    void deps
      .request("POST", PREFETCH_ROUTE, { body: { records, files, changed } })
      .then((response) => {
        // A lane started or joined: follow it, so the row it reads breathes while it does,
        // and a row whose files it will list waits for them on its change line.
        if (response.status === 202) {
          filesHeldUntil = null;
          deps.listingFiles?.(files);
          watchPrefetch();
        } else if (
          /** @type {{prefetch?: unknown} | null} */ (response.body)?.prefetch === "deferred"
        ) {
          holdFiles();
        }
      })
      .catch(() => {
        // Not sent, as far as the panel knows: the next files ask may send it again.
        lastAsk = "";
      })
      .finally(() => {
        prefetching = false;
        const pending = prefetchPending;
        prefetchPending = null;
        if (pending !== null && !disposed) {
          if (pending.files) {
            // After this answer's own hold, if it set one, and as the reader is now.
            sendFiles();
          } else {
            prefetch(pending.changed);
          }
        }
      });
    return true;
  }

  /** Read the lane's report once a fast poll from now, while it has work. */
  function watchPrefetch() {
    if (prefetchTimer !== null || disposed) {
      return;
    }
    prefetchTimer = deps.schedule(() => {
      prefetchTimer = null;
      void readPrefetch();
    }, FAST_POLL_MS);
  }

  /**
   * The row whose record the lane is reading now breathes, as a core batch's rows do; the
   * report is read again while the lane runs or holds a queue, and only while shown.
   */
  async function readPrefetch() {
    if (!coreLive() || !shown) {
      setPrefetchRows([]);
      return;
    }
    /** @type {{running?: {kind?: string, number?: number} | null, queued?: unknown[], recent?: {kind?: string, number?: number, outcome?: string, at?: string}[], governor?: {admits?: unknown}, files?: {per_hour?: unknown, hour_used?: unknown}} | null} */
    let report = null;
    try {
      const response = await deps.request("GET", PREFETCH_ROUTE, {});
      report = response.status === 200 ? /** @type {any} */ (response.body) : null;
    } catch {
      report = null;
    }
    if (disposed) {
      return;
    }
    const running = report?.running ?? null;
    const files = report?.files;
    // A list the lane refreshed reaches the stack headings that wait for it (B1 of review B
    // on #484), as a running record's row breathes below; and every files outcome the lane
    // reports, a list or none, reaches the rows' change lines, which read their lines again.
    /** @type {number[]} */
    const listed = [];
    for (const done of Array.isArray(report?.recent) ? report.recent : []) {
      const seen = `${done?.number}@${done?.at}`;
      if (done?.kind === "files" && typeof done.number === "number" && !listedSeen.has(seen)) {
        listedSeen.add(seen);
        if (listedSeen.size > LISTED_SEEN) {
          listedSeen.delete(/** @type {string} */ (listedSeen.values().next().value));
        }
        listed.push(done.number);
        if (done.outcome === "refreshed") {
          deps.filesListed?.(done.number);
        }
      }
    }
    if (
      report?.governor?.admits === false ||
      (typeof files?.hour_used === "number" &&
        typeof files.per_hour === "number" &&
        files.hour_used >= files.per_hour)
    ) {
      // The lane stopped, or will, at the budget's floor, the server's own ceiling or
      // speculative work's share of it, or the hour's cap of lists.
      holdFiles();
    }
    setPrefetchRows(
      running?.kind === "record" && typeof running.number === "number" ? [running.number] : [],
    );
    const busy = running !== null || (Array.isArray(report?.queued) && report.queued.length > 0);
    // Idle, every row still waiting for the lane reads its line again.
    if (report !== null && (listed.length > 0 || !busy)) {
      deps.listedFiles?.(listed, !busy);
    }
    if (busy) {
      watchPrefetch();
    }
  }

  /** @param {number[]} rows */
  function setPrefetchRows(rows) {
    if (rows.join(",") !== prefetchRows.join(",")) {
      prefetchRows = rows;
      render();
    }
  }

  /**
   * The rows the lane is reading, under the rule a core batch's rows breathe by: only while
   * the panel is live and online, so an offline panel breathes nothing it cannot finish.
   */
  function prefetchRefreshing() {
    return coreLive() ? prefetchRows : [];
  }

  function stopPrefetchWatch() {
    if (prefetchTimer !== null) {
      deps.cancel(prefetchTimer);
      prefetchTimer = null;
    }
    prefetchRows = [];
    prefetchPending = null;
    if (filesTimer !== null) {
      deps.cancel(filesTimer);
      filesTimer = null;
    }
    // The rows in view are measured again when the panel next paints them.
    viewRows = [];
  }

  /** The server admits no background work, or no more lists this hour: files asks wait. */
  function holdFiles() {
    filesHeldUntil = deps.now() + SLOW_POLL_MS;
    // The ask it refused was not acted on, so the same ask may be sent once the hold ends.
    lastAsk = "";
  }

  /**
   * Whether GitHub is, or may be, being read for the rows in view: a batch of them whose
   * answer is still on its way, since the server may have started reading GitHub before it
   * answers; one it admitted, whose titles breathe; or, after one, the next batch the queue
   * holds. That is what the reader sees and waits for, and a files ask waits behind it. A
   * batch the cache answered holds nothing up once its answer is in.
   */
  function viewBeingRead() {
    if (
      coreWanted === null ||
      coreWanted.lane !== "visible" ||
      !coreWanted.canRetry ||
      !coreLive() ||
      warmPaused
    ) {
      return false;
    }
    if (coreRequest !== null && coreRequest.demand === coreWanted) {
      return true;
    }
    return (
      coreWanted.admitted === true && (!coreWanted.done || visibleCoreAt < visibleCores.length)
    );
  }

  /**
   * Ask, *delayMs* from now, for the changed files of the rows the reader is likely to
   * expand: at once for a row the pointer or focus rests on, and once the rows in view stay
   * put for the rows in view. A later ask replaces one still waiting.
   *
   * @param {number} delayMs
   */
  function askFiles(delayMs) {
    if (filesTimer !== null) {
      deps.cancel(filesTimer);
    }
    filesTimer = deps.schedule(() => {
      filesTimer = null;
      sendFiles();
    }, delayMs);
  }

  /**
   * Send a files ask, unless the reader is walking, GitHub is being read for the rows in
   * view, which it then waits behind, or the server said the budget admits none.
   */
  function sendFiles() {
    if (!live() || !online() || walkingTo !== null) {
      return;
    }
    if (filesHeldUntil !== null && deps.now() < filesHeldUntil) {
      return;
    }
    if (viewBeingRead()) {
      askFiles(CORE_BUSY_RETRY_MS);
      return;
    }
    prefetch(askChanged, true);
  }

  /** After a scan the server finished, once per scan: ask for what it found changed. */
  function prefetchAfterScan() {
    const envelope = held().envelope;
    if (
      envelope === null ||
      envelope.state !== "current" ||
      envelope.refreshing ||
      envelope.fetched_at === null ||
      envelope.fetched_at === prefetchedScan
    ) {
      return;
    }
    if (prefetch(true)) {
      prefetchedScan = envelope.fetched_at;
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
        const fresh = response.body.rows
          .map((row) => describeRow(row))
          .filter((row) => !list.keys.has(row.number))
          .slice(0, list.displayLimit - list.rows.length);
        for (const row of fresh) {
          list.keys.set(row.number, list.rows.length);
          list.rows.push(row);
        }
        if (fresh.length > 0) {
          if (response.body.source !== null) {
            noteListed(response.body.source, name, fresh, { append: true });
          }
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
        list.error = unavailableText("The list");
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
      // A chase, or a list filling its rows before a navigation's pull request is revealed.
      const waited = chasing || (revealPending && sought === current);
      if (waited && current !== null && rowFor(current) !== undefined) {
        chasing = false;
        revealRow(current);
      }
      revealWholeStack();
      if (placeSought()) {
        return;
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
   * Grow the displayed prefix by one page, reading the cache before asking the shared
   * catalog job to prioritize more rows. Each approach to the tail adds one, with no end
   * but the filter's own.
   */
  function extendDisplay() {
    const list = held();
    const envelope = list.envelope;
    if (
      disposed ||
      envelope === null ||
      list.more ||
      envelope.reason === "not_github" ||
      !live() ||
      windowRead !== null ||
      list.error !== null ||
      list.rows.length < list.displayLimit
    ) {
      return Promise.resolve();
    }
    // At a completed or failed refresh, paging can still reveal cached rows.
    const cacheOnly =
      envelope.complete ||
      !online() ||
      watchPaused(envelope) ||
      rateHoldMs(envelope, deps.now()) > 0 ||
      refreshFailure(envelope, deps.formatTime) !== null;
    const limit = Math.min(
      list.displayLimit + WINDOW_ROWS,
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

  /**
   * A pull request's row takes the current-row mark from whichever row held it, a stack's
   * Stack Overview row too, as `openStack` takes it the other way, so one row holds it: a walk
   * from a stack's Stack Overview row, which opens the stack's page, on to its pull requests
   * leaves no second mark, and no stale stack page for `settleAnchor`, before the address
   * follows.
   *
   * @param {number} number
   */
  function setCurrentRow(number) {
    cancelCoreRetry();
    const previous = currentKey();
    if (previous !== number) {
      current = number;
      currentStack = null;
      wholeRevealPending = false;
      deps.markCurrent(previous, number);
    }
  }

  /**
   * Read a row's record, the newest asked for at a time. Local, and runs no gh. A read the
   * opening page joined is the page's: it answers it even once a newer read replaced it here.
   *
   * @param {number} number
   * @returns {Promise<RecordAnswer | null>}
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
        if (response.status !== 200 || disposed || controller.signal.aborted) {
          return null;
        }
        /** @type {RecordAnswer} */
        const answer = {
          etag: response.etag,
          body: response.body,
          verified: response.verified ?? null,
          at: deps.now(),
        };
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
   * A row that was already the current one before this selection, *current*, opens at once
   * and reads nothing: its page holds the pane or is opening, and reads its own record. That
   * is a second click before the first one's open, or a click on a row a held key walked to.
   * Otherwise a read still on its way when the wait ends goes to the page as `pending`, which
   * the page joins instead of reading the record again, with `abandon` to end it if the page
   * goes first: the page host disposes a page that another replaces, so a read for a row the
   * reader left ends with its page.
   *
   * @param {number} number
   * @param {number} fetchAfterMs
   * @param {boolean} replace
   * @param {boolean} [wasCurrent]
   */
  async function openRow(number, fetchAfterMs, replace, wasCurrent = false) {
    clearWalk();
    const ticket = ++opening;
    /** @type {RecordAnswer | null} */
    let initial = null;
    /** @type {Promise<RecordAnswer | null> | null} */
    let pending = null;
    /** @type {AbortController | null} */
    let ends = null;
    if (wasCurrent) {
      if (reading?.number === number) {
        pending = reading.done;
        ends = reading.controller;
        handed = reading;
        reading = null;
      }
    } else {
      const read = readRecord(number);
      /** @type {unknown} */
      let waiter = null;
      let answered = false;
      await Promise.race([
        read.then((answer) => {
          initial = answer;
          answered = true;
        }),
        new Promise((resolve) => {
          waiter = deps.schedule(() => resolve(undefined), OPEN_WAIT_MS);
        }),
      ]);
      deps.cancel(waiter);
      if (disposed || ticket !== opening) {
        return;
      }
      if (!answered && reading?.number === number) {
        // Handed to the page: a peek of another row does not abort it, the page does.
        ends = reading.controller;
        handed = reading;
        reading = null;
        pending = read;
      }
    }
    peeked.delete(number);
    // While a key is still held the page waits to fetch, whatever its wait was: a first press
    // held past it would otherwise fetch the row the walk left long ago.
    const walking = () => !disposed && walkingTo !== null;
    const handedRead = handed;
    const abandon =
      ends === null
        ? undefined
        : () => {
            ends?.abort();
            if (handed === handedRead) {
              handed = null;
            }
          };
    deps.open({
      number,
      tab: "",
      replace,
      reader: { fetchAfterMs, initial, pending, walking, ...(abandon ? { abandon } : {}) },
    });
    // A row opens once the reader stops on it, a walk included, so its neighbours are next.
    prefetch(false);
    warmAhead();
  }

  function cancelReads() {
    arrivalBaseline = null;
    // The next poll asks again for a navigation's pull request still to be placed.
    soughtRead?.abort();
    soughtRead = null;
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
    handed?.controller.abort();
    handed = null;
    for (const controller of refreshReads) {
      controller.abort();
    }
    refreshReads.clear();
    opening += 1;
    clearWalk();
    stopPrefetchWatch();
  }

  /**
   * The list rows changed under the panel: a new filter, or it became visible. A filter the
   * reader or the list's address picks ends a navigation's reveal; *reveal* is the move a
   * reveal makes itself (`placeSought`).
   *
   * @param {string} name
   * @param {{fromAddress?: boolean, reveal?: boolean}} [how]
   */
  function setFilter(name, how = {}) {
    if (disposed || !LISTS.includes(name) || name === filter) {
      return;
    }
    if (how.reveal !== true) {
      seek(null);
    }
    cancelReads();
    filter = name;
    prioritizeFilter = shown;
    settleAnchor(true);
    painted = null;
    render();
    if (how.fromAddress !== true) {
      deps.filterChanged(name);
    }
    void poll(true);
  }

  /** The rows changed shape: draw them, then settle the anchor on what is drawn. */
  function regroup() {
    groupingInputs += 1;
    render();
    settleAnchor();
    revealWholeStack();
  }

  /**
   * Open or close a stack's row; *open* undefined turns it. Whether it changed.
   *
   * @param {number} number
   * @param {boolean} [open]
   */
  function setStackOpen(number, open) {
    const isOpen = !closedStacks.has(number);
    const wanted = open ?? !isOpen;
    if (disposed || wanted === isOpen) {
      return false;
    }
    if (wanted) {
      closedStacks.delete(number);
    } else {
      closedStacks.add(number);
    }
    regroup();
    return true;
  }

  /** Move the anchor to a row by a key: it takes focus, and nothing opens. @param {number} key */
  function anchorAt(key) {
    anchorChosen = true;
    if (anchor !== key) {
      const previous = anchor;
      anchor = key;
      deps.markAnchor(previous, key, true);
    }
  }

  /**
   * Move the row selection by a key. Work is the two rows that change, and the pane opens
   * the row at once for a single press, or for a held key when it stops. A stack's row is a
   * stop of its own, as a folder is in the Files tree: it takes focus and opens nothing.
   *
   * @param {-1 | 1} delta
   * @param {{repeat?: boolean}} [how]
   * @returns {boolean} Whether the key was the list's, so nothing else scrolls for it.
   */
  function move(delta, how = {}) {
    const list = held();
    const order = grouping();
    if (disposed || order.keys.length === 0) {
      return false;
    }
    const at = anchor === null ? -1 : (order.at.get(anchor) ?? -1);
    const target = at + delta;
    if (target < 0) {
      return true;
    }
    if (target >= order.keys.length) {
      void extendDisplay();
      return true;
    }
    const key = order.keys[target];
    anchorChosen = true;
    // Keep rows arriving ahead of a walk, so a held key does not stall on the window's end.
    if (order.keys.length - target <= 2 && list.nextAfter !== null) {
      void loadWindow();
    }
    const whole = wholeStackOfKey(key);
    if (whole !== null) {
      // A Stack Overview row opens its page as a pull request's row does: at once for a press,
      // and for a held key once it stops there.
      clearWalk();
      anchorAt(key);
      if (how.repeat === true) {
        walkTimer = deps.schedule(() => {
          walkTimer = null;
          openStack(whole, true);
        }, WALK_SETTLE_MS);
      } else {
        openStack(whole, true);
      }
      return true;
    }
    if (key < 0) {
      clearWalk();
      anchorAt(key);
      return true;
    }
    const number = key;
    const previous = anchor;
    anchor = number;
    deps.markAnchor(previous, number, true);
    const wasCurrent = current === number;
    setCurrentRow(number);
    if (how.repeat === true) {
      clearWalk();
      walkingTo = number;
      walkTimer = deps.schedule(() => {
        walkTimer = null;
        void openRow(number, REFRESH_ASK_MS, true);
      }, WALK_SETTLE_MS);
    } else {
      void openRow(number, REFRESH_ASK_MS, true, wasCurrent);
    }
    return true;
  }

  /**
   * The pull request the address names, for `setCurrent`.
   *
   * @param {number | null} number
   * @param {{preserveScroll?: boolean, again?: boolean}} options
   */
  function followPull(number, options) {
    if (options.preserveScroll) {
      revealCurrent = false;
      seek(null);
    }
    if (number === current) {
      if (options.again === true && number !== null) {
        revealCurrent = true;
        seek(number);
        showCurrent(number);
      }
      return;
    }
    revealCurrent = !options.preserveScroll;
    seek(options.preserveScroll ? null : number);
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
    showCurrent(number);
    // Back, a link, or a stack walk on the page: its neighbours are next all the same.
    warmAhead();
  }

  /**
   * The native stack whose page the address names, or null, for `setCurrent`: its Stack
   * Overview row takes the current-row mark and is shown as a pull request's row is, and shown
   * again only *again*, by an open of the page shown.
   *
   * @param {number | null} stack
   * @param {{preserveScroll?: boolean, again?: boolean}} options
   */
  function followStack(stack, options) {
    if (stack === currentStack) {
      if (stack !== null && options.again === true) {
        revealCurrent = true;
        showWholeStack(stack);
      }
      return;
    }
    const previous = currentStack === null ? null : wholeStackRowKey(currentStack);
    currentStack = stack;
    wholeRevealPending = false;
    deps.markCurrent(previous, stack === null ? null : wholeStackRowKey(stack));
    if (stack !== null) {
      revealCurrent = !options.preserveScroll;
      showWholeStack(stack);
    }
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
        clearProbeTimer();
        cancelReads();
        queueCores();
        stopWarming();
        return;
      }
      if (current !== null && rowFor(current) !== undefined) {
        revealRow(current);
      }
      wake();
    },
    setFilter,
    prepareVisible,
    /**
     * The address says which pull request's page holds the pane. Not a selection: the row
     * only follows it, and no fetch starts. The current number named again moves nothing,
     * as another tab of its page or one of its changed files does, unless *again* says the
     * reader opened the pull request shown again: then its stack opens and its row scrolls
     * into view (docs/design-system.md, "Navigation Reveals the Item"). *stack*, with no
     * pull request, is the native stack whose own page the address names, whose Stack Overview
     * row is marked and shown the same way.
     *
     * @param {number | null} number
     * @param {{preserveScroll?: boolean, again?: boolean, stack?: number | null}} [options]
     */
    setCurrent(number, options = {}) {
      if (disposed) {
        return;
      }
      followPull(number, options);
      // After the pull request's, so the mark the address leaves goes before the one it gives.
      followStack(number === null ? (options.stack ?? null) : null, options);
    },
    /**
     * Home (static/main-tabs.js, `goHome`): the rows as a fresh load of `/view/` draws them,
     * from the rows held and with no read. Every stack opens, and the Tab stop goes to the
     * first row as no reader chose it. The address Home opens names no pull request, which
     * `setCurrent` hears next and which keeps that row.
     */
    home() {
      if (disposed) {
        return;
      }
      closedStacks.clear();
      anchorChosen = false;
      groupingInputs += 1;
      render();
      const first = grouping().keys[0] ?? null;
      if (first !== anchor) {
        const previous = anchor;
        anchor = first;
        deps.markAnchor(previous, first, false);
      }
    },
    move,
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
      const wasCurrent = current === number;
      setCurrentRow(number);
      anchorChosen = true;
      if (anchor !== number) {
        const previous = anchor;
        anchor = number;
        deps.markAnchor(previous, number, false);
      }
      void openRow(number, 0, false, wasCurrent);
    },
    /**
     * A reader pressed a stack's Stack Overview row: it takes the anchor and opens the stack's
     * page.
     *
     * @param {number} stack
     */
    activateStack(stack) {
      if (disposed) {
        return;
      }
      anchorChosen = true;
      const key = wholeStackRowKey(stack);
      if (anchor !== key) {
        const previous = anchor;
        anchor = key;
        deps.markAnchor(previous, key, false);
      }
      openStack(stack, false);
    },
    /** Open the anchor row on Enter; on a stack's row, open or close the stack; on a Stack
     * Overview row, open the stack's page. */
    activateAnchor() {
      if (disposed || anchor === null) {
        return false;
      }
      const whole = wholeStackOfKey(anchor);
      if (whole !== null) {
        openStack(whole, false);
        return true;
      }
      if (anchor < 0) {
        setStackOpen(-anchor);
        return true;
      }
      const wasCurrent = current === anchor;
      setCurrentRow(anchor);
      void openRow(anchor, 0, false, wasCurrent);
      return true;
    },
    /**
     * Focus reached a row by Tab or the pointer: it becomes the anchor, and nothing opens.
     *
     * @param {number} number
     */
    focused(number) {
      if (!disposed && anchor !== number && grouping().at.has(number)) {
        anchorChosen = true;
        const previous = anchor;
        anchor = number;
        deps.markAnchor(previous, number, false);
      }
    },
    /**
     * A row or its change line took the pointer, or the row focus: read its record ahead of
     * a click on the row, and ask for its changed files, which a click on its change line
     * expands. A walk does not come here, so it reads
     * nothing per row, and neither does the row whose page holds the pane or is opening,
     * which reads its own: a pointer resting on the row it just clicked would otherwise read
     * the record the page has just read. That row's files are in every ask already.
     *
     * @param {number} number
     */
    peek(number) {
      if (!disposed && walkingTo === null && number !== current) {
        void readRecord(number);
        if (restedRows[0] !== number) {
          restedRows = [number, ...restedRows.filter((row) => row !== number)].slice(
            0,
            PREFETCH_RESTED,
          );
          askFiles(0);
          warmAhead();
        }
      }
    },
    /** The reader neared the end of the displayed rows. */
    reachedEnd: () => extendDisplay(),
    /**
     * The shared stack snapshot changed (pull-stacks.js, `watchStacks`).
     *
     * @param {import("./pull-stacks.js").StackIndex} index
     */
    setStacks(index) {
      if (!disposed && index !== stackIndex) {
        stackIndex = index;
        regroup();
        // The open pull request's stack neighbours may be known only now.
        warmAhead();
      }
    },
    setStackOpen,
    /** Right on a stack's row: open it, or go to its first row, its Stack Overview row, which opens
     * the stack's page as J does. A Stack Overview row's Right is its files' (`mountPullsPanel`). */
    enterStack() {
      if (disposed || anchor === null || anchor >= 0 || wholeStackOfKey(anchor) !== null) {
        return false;
      }
      if (!setStackOpen(-anchor, true)) {
        move(1);
      }
      return true;
    },
    /** Left on a stack's row closes it; on a pull request in a stack, or its Stack Overview row, it
     * goes to the stack. Nothing opens. */
    leaveToStack() {
      if (disposed || anchor === null) {
        return false;
      }
      const whole = wholeStackOfKey(anchor);
      if (whole !== null) {
        clearWalk();
        anchorAt(stackRowKey(whole));
        return true;
      }
      if (anchor < 0) {
        setStackOpen(-anchor, false);
        return true;
      }
      const stack = stackOfRow(anchor);
      if (stack === null) {
        return false;
      }
      clearWalk();
      anchorAt(stackRowKey(stack));
      return true;
    },
    /**
     * A press of Refresh asks the repository's existing catalog job, behind another tab too:
     * the navigation's Refresh refreshes the tabs not in front after those that are
     * (static/refresh-plan.js), and the list reads what the job brought when it shows.
     */
    refresh() {
      if (
        disposed ||
        !visible() ||
        model().connection?.canRefresh !== true ||
        refreshReads.size > 0
      ) {
        return Promise.resolve();
      }
      held().error = null;
      return ask({ state: filter, target: held().displayLimit, retry: true });
    },
    refreshDetail() {
      const envelope = held().envelope;
      const identity = envelope === null ? null : coreCatalogIdentity(envelope);
      if (identity === null) {
        return null;
      }
      // The endpoint reports the repository's last refresh. A retained filter may
      // still be showing its earlier envelope when the reader switches tabs.
      let latest = null;
      let latestMs = -Infinity;
      for (const list of lists.values()) {
        const candidate = list.envelope;
        if (
          candidate === null ||
          candidate.refresh_timing == null ||
          coreCatalogIdentity(candidate) !== identity ||
          typeof candidate.refresh_timing.duration_ms !== "number" ||
          !Number.isFinite(candidate.refresh_timing.duration_ms) ||
          candidate.refresh_timing.duration_ms < 0
        ) {
          continue;
        }
        const finishedMs = Date.parse(candidate.refresh_timing.finished_at);
        if (finishedMs > latestMs) {
          latest = candidate.refresh_timing;
          latestMs = finishedMs;
        }
      }
      return latest;
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
      stopWarming();
      cancelCoreRetry();
      stopPrefetchWatch();
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
        clearProbeTimer();
        cancelReads();
        stopWarming();
        return;
      }
      warmPaused = false;
      queueCores();
      wake();
    },
    pause() {
      parked = true;
      clearTimer();
      clearProbeTimer();
      cancelReads();
      stopWarming();
    },
    resume() {
      parked = false;
      wake();
    },
    dispose() {
      disposed = true;
      clearTimer();
      clearProbeTimer();
      clearWalk();
      cancelReads();
      seek(null);
      peeked.clear();
    },
    /**
     * The envelope of *number*'s record as a peek read it, waiting for one on its way, or
     * null, so a warm of its comparison does not read the record a second time.
     *
     * @param {number} number
     * @returns {Promise<unknown>}
     */
    knownRecord(number) {
      const had = peeked.get(number);
      if (had !== undefined) {
        return Promise.resolve(had.body);
      }
      if (reading?.number === number) {
        return reading.done.then((answer) => answer?.body ?? null);
      }
      return Promise.resolve(null);
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
      grouped: grouping().rows !== null,
      closedStacks: [...closedStacks].sort((left, right) => left - right),
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
  return {
    status: response.status,
    etag: response.headers.get("etag"),
    body: decoded,
    // A record read for a selection is the opening page's first read, catalog verdict and all.
    verified: response.headers.get(VERIFIED_HEADER),
  };
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
  const refreshParts = nav.refreshParts ?? null;
  const updateRefreshTooltip = () => refreshParts?.updateTooltip?.();
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
  // The count and the connection are the shell's navigation metadata line (`.nav-metadata`,
  // docs/design-system.md, "Navigation Metadata Line"): two lines of one band under the
  // toolbar, set as the Files and Commits tallies are. The connection is shown for
  // first load, incomplete results, and failures.
  const status = h("p", { class: "github-pulls-status nav-metadata" });
  // A tree: a row's changed files hang off it as a group. Its keys are this view's, bound by
  // the tab's host; the Files tree's keyboard handler is scoped to the Files tab and never
  // sees these rows.
  const list = h("ul", { class: "github-pulls-list", role: "tree" });
  const empty = h("p", { class: "github-pulls-empty" });
  const connectionMessage = h("span", { class: "mb-refreshing-muted" });
  const spinner = h("span", { class: "github-pulls-connection-spinner", hidden: "" }, [
    h("span", { class: "spinner spinner-sm", "aria-hidden": "true" }),
  ]);
  const connectionText = h("span", { class: "github-pulls-connection-text" }, [
    spinner,
    connectionMessage,
  ]);
  const connectionHelp = h("span", { hidden: "" });
  const connection = h("div", { class: "github-pulls-connection nav-metadata nav-metadata-note" }, [
    connectionText,
    connectionHelp,
  ]);
  // A pull request the address names that the list does not hold: a line of the band, as
  // the Files tree's outside-filter note is, there only while it has something to say
  // (docs/design-system.md, "Navigation Reveals the Item").
  const outsideNote = h("p", {
    class: "github-pulls-outside nav-metadata nav-metadata-note",
    role: "status",
  });
  const foot = h("div", { class: "github-pulls-foot" });
  // Below the last row held, while more are read or fetched: the nav's scan indicator, its
  // spinner and words (`.index-progress` in styles.css), after the shared quiet period.
  const progressText = h("span", { class: "index-progress-text" });
  const progress = h("span", { class: "github-pulls-progress mb-delayed-loading" }, [
    h("span", { class: "index-progress-spinner", "aria-hidden": "true" }),
    progressText,
  ]);
  const live = h("span", { class: "sr-only", "aria-live": "polite" });
  container.classList.add("github-pulls");
  // The filters are the tab's toolbar: in the navigation's toolbar slot when the host has one,
  // at the slot's height, so the list starts where the Files tree does. There they are a
  // toolbar row, which wraps between its controls in a narrow pane (`.nav-toolbar-row` in
  // the shell's styles.css). The count and connection lines go in the band under the slot
  // when the host has one (`.nav-metadata-band`), outside the scroller that holds the list,
  // so their rule runs the pane's width and they stay in view while the list scrolls, as
  // the Files totals do.
  const toolbar = nav.toolbar ?? null;
  const band = nav.metadata ?? null;
  const lines = band ? [] : [status, connection];
  band?.replaceChildren(status, connection);
  if (toolbar) {
    filters.classList.add("nav-toolbar-row");
    toolbar.replaceChildren(filters);
    container.replaceChildren(...lines, list, empty, foot, live);
  } else {
    container.replaceChildren(filters, ...lines, list, empty, foot, live);
  }

  /**
   * What is painted of each row held, by number: its elements, the key of what it shows, and
   * when it was updated, whose age moves on while the row stays.
   *
   * @typedef {{
   *   item: HTMLElement,
   *   zone: HTMLElement,
   *   row: HTMLAnchorElement,
   *   age: HTMLElement,
   *   said: HTMLElement,
   *   heading: HTMLElement,
   *   run: import("./stack-member-row.js").StackMemberRow,
   *   line: import("./stack-member-row.js").StackMemberLine,
   *   stack: HTMLElement,
   *   title: HTMLElement,
   *   change: HTMLElement,
   *   changeLine: HTMLElement,
   *   changeWords: HTMLElement,
   *   changePending: HTMLElement | null,
   *   changeKey: string,
   *   readinessKey: string,
   *   info: PullRow,
   *   key: string,
   *   at: number | null,
   *   label: string,
   * }} PaintedRow
   */
  /** @type {Map<number, PaintedRow>} */
  const painted = new Map();
  /** The rows whose titles breathe: GitHub is being read for them. @type {Set<number>} */
  let refreshingTitles = new Set();
  let stackIndex = createStackIndex(null);
  /** @type {import("./pull-stacks.js").StackIdentity | null} */
  let stackIdentity = null;
  /**
   * The rows last painted, in their order: an append leaves them as they were. A pull
   * request's row has its level and, under a stack's row, its stack and place in it.
   *
   * @typedef {{kind: "pull", key: number, row: PullRow, level: number, stack: number | null, posinset: number | null, setsize: number | null}
   *   | {kind: "stack", key: number, group: import("./pull-stacks.js").StackGroupRow}
   *   | {kind: "whole", key: number, whole: import("./pull-stacks.js").WholeStackRow, stack: import("./pull-stacks.js").NativeStack}} PaintedPlace
   */
  /** @type {PaintedPlace[]} */
  let paintedRows = [];
  /** @type {number | string} */
  let paintedVersion = -1;
  /**
   * A stack's row as painted, by its row key (`stackRowKey`): its elements, its stack, and
   * the key of what it shows. `age` is its age's element, `at` the time it tells, in epoch
   * seconds, and `aged` its label as last told, which the row's name says.
   *
   * @typedef {{
   *   item: HTMLElement, row: HTMLElement, label: HTMLElement, count: HTMLElement,
   *   age: HTMLElement, at: number | null, aged: string, hint: string,
   *   stack: import("./pull-stacks.js").NativeStack, key: string,
   * }} PaintedStack
   */
  /** @type {Map<number, PaintedStack>} */
  const paintedStacks = new Map();
  /**
   * A stack's Stack Overview row as painted, by its row key (`wholeStackRowKey`): its item and
   * its link, and the key of what it shows. `change` is the toggle of its stack's changed
   * files, its change line and the chevron after it, as a pull request's row's is; `line`
   * holds the stack's brief change line, or the pending placeholder while the stack's read
   * is on its way (`pending`), which is kept across paints so its quiet period and its pulse
   * run once.
   *
   * @typedef {{
   *   item: HTMLElement, row: HTMLElement, change: HTMLElement, line: HTMLElement,
   *   pending: HTMLElement | null, stack: import("./pull-stacks.js").NativeStack, key: string,
   * }} PaintedWhole
   */
  /** @type {Map<number, PaintedWhole>} */
  const paintedWholes = new Map();
  /** The stacks whose rows were in view at the last measure, whose members a prefetch names
   * first. */
  /** @type {Set<number>} */
  let stacksInView = new Set();
  /** A drawn row's treeitem by its key: a pull request's number, a stack's row key, or a
   * Stack Overview row's. */
  const rowElement = (/** @type {number} */ key) =>
    wholeStackOfKey(key) !== null
      ? paintedWholes.get(key)?.row
      : key < 0
        ? paintedStacks.get(key)?.row
        : painted.get(key)?.row;
  /**
   * What a row's item is on screen: a pull request's lines, its zone, which hovers and
   * takes the ring as one (mb-1z7j), or a stack's or a Stack Overview row's one row.
   */
  const itemElement = (/** @type {number} */ key) =>
    key < 0 ? rowElement(key) : painted.get(key)?.zone;
  /** A drawn row's list item by its key, whatever its kind. */
  const listItem = (/** @type {number} */ key) =>
    wholeStackOfKey(key) !== null
      ? paintedWholes.get(key)?.item
      : key < 0
        ? paintedStacks.get(key)?.item
        : painted.get(key)?.item;
  const rowWindow = createPullsWindow({
    estimate: ROW_ESTIMATE_PX,
    overscan: PULL_ROWS_OVERSCAN,
  });
  /** @type {Map<number, number>} */
  let rowIndices = new Map();
  /** Each listed pull request's head commit, as the catalog's row reports it. */
  /** @type {Map<number, string | null>} */
  let rowHeads = new Map();
  /** @type {Map<string, HTMLElement>} */
  const gaps = new Map();
  /**
   * The row the reader is reading, its key and its distance from the scroller's top, which
   * a paint keeps: the row a reveal scrolled to while it holds (`revealedPlace`), and
   * otherwise a pull request's row or a stack's, the first one in view.
   *
   * @type {{key: number, offset: number} | null}
   */
  let readingPlace = null;
  /**
   * Where a reveal put its row, and the scroll that put it there. Rows that arrive or regroup
   * after the reveal, as stacks read after the list's first window do, leave the row where
   * the reveal put it, until the list is scrolled other than by this view, as a reader
   * scrolls it: kept as the first row in view, the row was regrouped out of view.
   *
   * @type {{key: number, offset: number, scrollTop: number} | null}
   */
  let revealedPlace = null;
  /** Whether the rows last painted were grouped by stack. */
  let paintedGrouped = false;
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
  let currentStack = null;
  /** @type {number | null} */
  let anchorRow = null;

  /** The registry's disclosure chevron, parsed once: a constant, not the pull request's text. */
  const chevronSvg = new DOMParser().parseFromString(mb.icons?.toggle || "", "text/html").body
    .firstElementChild;
  const chevron = () => (chevronSvg === null ? null : document.importNode(chevronSvg, true));
  const stackSvg = new DOMParser().parseFromString(mb.icons?.layers || "", "text/html").body
    .firstElementChild;
  const layersGlyph = () => (stackSvg === null ? null : document.importNode(stackSvg, true));
  // Narrowed once, for the functions below that run later.
  const tab = nav;

  // Which rows show their changed files, and each one's tree, by the row's key: a pull
  // request's number, or a stack's Stack Overview row's key (`wholeStackRowKey`), whose files
  // are the stack's combined ones. Open ones, and the last MAX_HELD_TREES closed, so one
  // opened again is as the reader left it.
  const expansion = createRowExpansion();
  /**
   * The drawn row a tree hangs from, by its key: a pull request's or a Stack Overview row's
   * item, its treeitem, and its toggle, the change line and the chevron after it.
   *
   * @param {number} key
   * @returns {{item: HTMLElement, row: HTMLElement, change: HTMLElement} | undefined}
   */
  const treeOwner = (key) =>
    wholeStackOfKey(key) === null ? painted.get(key) : paintedWholes.get(key);
  /** The keys of the drawn rows a tree can hang from. */
  const treeOwners = () => [...painted.keys(), ...paintedWholes.keys()];
  // The changed-files tree every row's files are drawn with, which a diff's Diff summary
  // shares (static/changed-files-tree.js). It is asked for now, as the list mounts, so it is
  // in hand before a reader opens a row; a tree opened first waits for it in its read. A load
  // that failed is asked for again by the next read, so a tree's Retry can still draw.
  /** @type {Promise<MetabrowserChangedFilesTree> | null} */
  let changedFiles = null;
  const loadChangedFiles = () => {
    changedFiles ??= mb.loadChangedFilesTree().catch((error) => {
      changedFiles = null;
      console.error("metabrowser github: the changed-files tree did not load", error);
      throw error;
    });
    return changedFiles;
  };
  void loadChangedFiles().catch(() => {});
  /** Each row's list of changed files as its tree last read it whole, by its generation. */
  /** @type {Map<number, string>} */
  const listsRead = new Map();
  /**
   * A row's tree read its list of changed files: a list newly whole reaches the stack
   * headings that wait for it (B1 of review B on #484).
   *
   * @param {number} number
   * @param {string} route
   * @param {PullsResponse} answer
   */
  function noteFilesRead(number, route, answer) {
    const body = /** @type {{complete?: unknown, generation?: unknown} | null} */ (answer.body);
    if (
      !route.startsWith("/api/plugin/github/pull-files?") ||
      answer.status !== 200 ||
      body?.complete !== true ||
      typeof body.generation !== "string"
    ) {
      return;
    }
    // The row's own change line, summed from another refresh's list, reads again
    // (row-lines.js).
    rowLines?.heard(number, body.generation);
    if (listsRead.get(number) === body.generation) {
      return;
    }
    listsRead.delete(number);
    listsRead.set(number, body.generation);
    if (listsRead.size > LISTED_SEEN) {
      listsRead.delete(/** @type {number} */ (listsRead.keys().next().value));
    }
    stackLines?.listed(number);
  }
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
  /** @type {ReturnType<typeof refreshPage>} */
  let timedPage = null;
  /** @type {(() => void) | null} */
  let unwatchFile = null;
  /** @type {(() => void) | null} */
  let unwatchRefreshDetail = null;
  let fileFollowEpoch = 0;

  /** @returns {ReturnType<typeof import("./pull-page.js").mountPullPage> | null} */
  function currentPage() {
    return /** @type {ReturnType<typeof currentPage>} */ (
      currentRow === null ? null : tab.pageFor(currentRow)
    );
  }

  /** The preview that owns the page part of Refresh. */
  function refreshPage() {
    const stack =
      /** @type {ReturnType<typeof import("./stack-page.js").mountStackPage> | null} */ (
        currentStack === null ? null : (tab.stackFor?.(currentStack) ?? null)
      );
    return stack ?? currentPage();
  }

  /** A null-file route replays the same page's current observation after address sync.
   * @param {boolean} [replay]
   */
  function followCurrentFile(replay = false) {
    const number = currentRow;
    const page = currentPage();
    const timing = refreshPage();
    if (timing !== timedPage) {
      unwatchRefreshDetail?.();
      timedPage = timing;
      unwatchRefreshDetail = timing?.onRefreshDetail?.(updateRefreshTooltip) ?? null;
      updateRefreshTooltip();
    }
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
   * The files of a comparison as its Diff summary lists them, read through the diff view as
   * a stack's page reads its own (stack-page.js, `showSummary`): the comparison at the
   * address the page asks, so the browser's cache answers whichever asks second, and the
   * summary's own rows of it (`summaryRows`). The diff's assets are asked for here, when a
   * reader first opens a stack's files, and never as the list mounts. Null where the view
   * cannot give them.
   *
   * @param {ReturnType<typeof import("./stack-page.js").diffComparison>} comparison
   * @param {AbortSignal} asked
   */
  async function comparisonRows(comparison, asked) {
    await mb.ensureKindAssets("diff");
    asked.throwIfAborted();
    const view = mb.getRegisteredView("diff", "diff");
    if (typeof view?.prefetch !== "function" || typeof view.summaryRows !== "function") {
      return null;
    }
    const raw = await view.prefetch(comparison, asked);
    asked.throwIfAborted();
    return view.summaryRows(raw);
  }

  /**
   * A row's tree, made the first time its files open: a pull request's own changed files,
   * or, for a stack's Stack Overview row, the stack's combined ones, the files its page's Diff
   * summary lists (stack-files.js), in the one tree both are drawn with. A stack's file
   * opens the stack's Changes at it.
   *
   * @param {number} number The row's key.
   */
  function treeFor(number) {
    let tree = trees.get(number);
    if (tree === undefined) {
      const stack = wholeStackOfKey(number);
      /** @type {import("./pull-files-tree.js").FileTreeDependencies["request"]} */
      const ask = (method, route, options) =>
        request(mb.perf, method, route, { ...options, signal: options.signal ?? signal });
      tree = mountFileTree({
        decorateExternalLink: mb.decorateExternalLink,
        number,
        autoExpandFiles: AUTO_EXPAND_FILES,
        current: number === currentRow && stack === null ? currentFile : null,
        shown: panelShown,
        scrollRoot: tab.scrollRoot,
        chevron,
        changeLineNodes: mb.changeLineNodes,
        href: (path) =>
          stack === null ? tab.fileHref(number, path) : tab.stackFileHref(stack, path),
        request: async (method, route, options) => {
          const answer = await ask(method, route, options);
          noteFilesRead(number, route, answer);
          return answer;
        },
        ...(stack === null
          ? {}
          : {
              id: `github-stack-files-${stack}`,
              list: createStackFileList(
                { request: ask, rows: comparisonRows, now: () => Date.now() },
                stack,
                `Changed files of ${stackLabel(stack)}`,
              ),
            }),
        formatTime: (iso) => mb.formatTimestamp(Date.parse(iso) / 1000),
        // A stack's page is no pull request's: a walk of its files opens each at its address.
        page: () =>
          stack === null
            ? /** @type {import("./pull-files-tree.js").FilePage | null} */ (tab.pageFor(number))
            : null,
        open: ({ file, replace, jumped }) => {
          void tab.open(
            stack === null
              ? { number, tab: "files", file, replace, jumped }
              : { number: stack, tab: "changes", file, replace, stack: true },
          );
        },
        // Left from a file at the tree's top goes to the pull request the tree hangs from.
        leave: () => void focusItem(number),
        focusedIn: () => {
          if (focusedTree !== null && focusedTree !== number) {
            trees.get(focusedTree)?.controller.cancelWalk();
          }
          focusedTree = number;
        },
        lastInput: () => lastInputAt,
        held: (hold, heldMs, outcome) =>
          mb.perf.measure(`githubPulls:${hold}Hold`, () => {}, { number, heldMs, outcome }),
        tree: loadChangedFiles,
        formatCount: (count) => mb.formatInteger(count),
      });
      trees.set(number, tree);
      const entry = treeOwner(number);
      if (entry !== undefined) {
        tree.attach(entry.item, entry.row, entry.change);
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
   * The reader is about to open or close a row's files, by a press on its change line, or
   * Space, Right, or Left on the row: the row stays where it is, under the pointer or the
   * focus, and the files open or close below it. A reveal's place gives way to it, as a
   * reader's scroll ends one, so opening a row above the one a reveal placed does not move
   * the row the reader acted on. Called before the files change, while the row is where the
   * reader sees it.
   *
   * @param {number} number
   */
  function holdRowPlace(number) {
    const item = treeOwner(number)?.item;
    const view = tab.scrollRoot?.getBoundingClientRect();
    if (item !== undefined && view !== undefined) {
      revealedPlace = null;
      readingPlace = { key: number, offset: item.getBoundingClientRect().top - view.top };
    }
  }

  /** A press on a row's change line, or Space on the row: its files open or close in place.
   * @param {number} number */
  function toggleRowFiles(number) {
    holdRowPlace(number);
    setExpanded(number, expansion.toggle(number));
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
   * @param {HTMLElement} row
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

  /** When a row's pull request was updated, in epoch seconds, or null. @param {PullRow} row */
  function rowUpdatedAt(row) {
    const parsed = row.updatedAt === null ? Number.NaN : Date.parse(row.updatedAt) / 1000;
    return Number.isFinite(parsed) ? parsed : null;
  }

  /**
   * A stack member's place in its stack, after its title with a muted dot before it, "title ·
   * 14/15", where the row's run puts it (stack-member-row.js; docs/design-system.md,
   * "Stacks"), the stack menu's member line's dot (`.github-pull-stack-dot`). It has no stack
   * icon of its own: the stack's row it sits under has it. The place of its row's own stack
   * comes first, bare, and any other stack's is named by the Layers glyph before its number.
   * A pull request in no stack has neither place nor dot, so its title follows the icon. A
   * passive part of the row's one primary link, named by its accessible name; the Pulls
   * column shows no tooltips (docs/design-system.md, "Tooltips Add Information").
   *
   * @param {PaintedRow} entry
   * @param {number} number
   * @param {number | null} [under]
   */
  function paintPlace(entry, number, under = null) {
    const caption = stackCaption(stackIndex, stackIdentity, number, under);
    const text = caption?.text ?? null;
    const hint = caption?.hint ?? "";
    if (entry.line.place === text && (entry.line.placeHint ?? "") === hint) {
      return;
    }
    entry.line = {
      ...entry.line,
      place: text,
      placeHint: hint,
      placeNodes:
        caption === null
          ? []
          : caption.parts.flatMap((part, at) => [
              ...(at === 0 ? [] : [" · "]),
              ...namedStackPositionNodes(part.position, part.stack, layersGlyph),
            ]),
    };
    entry.run.show(entry.line);
  }

  /**
   * A row's fields as its run shows them (stack-member-row.js), with the place it showed
   * last: the place is the list's to decide (`paintPlace`).
   *
   * @param {PullRow} row
   * @param {import("./stack-member-row.js").StackMemberLine | null} shown
   * @returns {import("./stack-member-row.js").StackMemberLine}
   */
  function runLine(row, shown) {
    return {
      number: row.number,
      place: shown?.place ?? null,
      placeNodes: shown?.placeNodes,
      placeHint: shown?.placeHint,
      title: row.title,
      state: row.state,
      author: { login: row.author, avatar: row.avatar },
      // The readiness is the lane's to say (`paintReadiness`): what the row showed last.
      readiness: shown?.readiness ?? null,
    };
  }

  /** Use the shared identity and let the heading's styles show its avatar only.
   * @param {string} login
   * @param {string | null} avatar
   */
  function rowAuthor(login, avatar) {
    return authorLabel(mb, login, avatar, "github-pulls-author", { loading: "eager" });
  }

  /**
   * Say the author, PR number, and age once, after the title and stack position.
   *
   * @param {PullRow} row
   * @param {string} age
   */
  function rowSaid(row, age) {
    return age === "" ? row.meta : `${row.meta} · ${age}`;
  }

  /** Patch a mounted row without detaching its link, expanded files, or focus. */
  /** @param {PaintedRow} entry @param {PullRow} row @param {string} key */
  function patchRow(entry, row, key) {
    const before = entry.info;
    // The run changes only the fields that differ (stack-member-row.js).
    entry.line = runLine(row, entry.line);
    entry.run.show(entry.line);
    if (row.updatedAt !== before.updatedAt) {
      entry.at = rowUpdatedAt(row);
      entry.label = mb.retellAge(entry.age, entry.at);
    }
    entry.said.textContent = rowSaid(row, entry.label);
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
    const at = rowUpdatedAt(row);
    const changeId = `github-pull-change-${row.number}`;
    // The lines the pull request changes (`paintChange`), then the registry's chevron, after
    // the summary it expands, as every toggle of a diff summary has it (mb-f0pz): the row's
    // last line, and the item's inner target. A press on it opens or closes the changed files
    // and opens no page, where a press anywhere else on the item, the rest of its line too,
    // opens the pull request (mb-pw8t, mb-rb3n). It is for the pointer alone: Space, Right,
    // and Left on the row are its keys, and the row's `aria-expanded` its state, so it is
    // hidden from assistive technology, and the tree holds only its items and their groups
    // (mb-1z7j). Its words, the lines said in full, stay out of view in it, and describe the
    // row, which reads them though they are hidden. Its `.expanded` follows the files.
    const changeLine = h("span", { class: "github-pulls-change-line" });
    const changeWords = h("span", { class: "github-pulls-change-words", id: changeId, hidden: "" });
    const change = h(
      "span",
      { class: "github-pulls-change disclosure-toggle collapsed", "aria-hidden": "true" },
      [
        changeLine,
        h("span", { class: "github-pulls-toggle", "aria-hidden": "true" }, [chevron()]),
        changeWords,
      ],
    );
    change.dataset.number = String(row.number);
    // The age follows the toggle. The link's name says it (rowSaid).
    const updated = mb.ageLabel(at, { className: "github-pulls-age" });
    updated.setAttribute("aria-hidden", "true");
    const label = updated.textContent ?? "";
    // The avatar follows the title in the same wrapping flow.
    const heading = h("span", { class: "github-pulls-heading" });
    const run = stackMemberRow(heading, mb.titleNodes, rowAuthor, PULLS_RUN);
    const line = runLine(row, null);
    run.show(line);
    const separator = h("span", { class: "github-pull-stack-dot", "aria-hidden": "true" }, ["·"]);
    run.end.insertBefore(separator, run.end.firstChild);
    const tail = h("span", { class: "github-pulls-tail" }, [change, updated, run.end]);
    const said = h("span", { class: "sr-only" }, [rowSaid(row, label)]);
    // A link, so a new tab and a copied address are the browser's, in the role of a tree's
    // item: its level is the list's one, and `placeRows` tells its place. Its changed files
    // are its children, as a folder's are, closed until the reader opens them; the tree that
    // draws them owns them from it (pull-files-view.js, `attach`). Its name is the state, the
    // title, the place, the author, the number, and the age in words (`rowSaid`); its
    // lines' words describe it, so they are read with it, as its toggle is no stop and no node
    // of the tree.
    const anchor = /** @type {HTMLAnchorElement} */ (
      h(
        "a",
        {
          class: "github-pulls-row",
          href: row.href,
          role: "treeitem",
          "aria-level": "1",
          "aria-expanded": "false",
          "aria-describedby": changeId,
          tabindex: "-1",
        },
        [heading, tail, said],
      )
    );
    anchor.dataset.number = String(row.number);
    if (row.number === currentRow) {
      markShown(anchor, true);
    }
    if (row.number === anchorRow) {
      anchor.setAttribute("tabindex", "0");
    }
    // The item, one hover, one selection, and one focus ring (github/styles.css,
    // `.github-pulls-entry`); its files follow, outside it, as a folder's follow its row.
    const zone = h("div", { class: "github-pulls-entry" }, [anchor]);
    const item = h("li", { class: "github-pulls-item", role: "none" }, [zone]);
    // Its files, kept across a row built again for what it shows.
    trees.get(row.number)?.attach(item, anchor, change);
    return {
      item,
      zone,
      row: anchor,
      age: updated,
      said,
      heading,
      run,
      line,
      stack: run.place,
      title: run.title,
      change,
      changeLine,
      changeWords,
      changePending: null,
      changeKey: "",
      readinessKey: "",
      info: row,
      key,
      at,
      label,
    };
  }

  /**
   * Update the summary line’s readiness in place. An empty glyph slot keeps the number still.
   *
   * @param {PaintedRow} entry
   */
  function paintReadiness(entry) {
    const readiness =
      rowReadiness?.readiness(
        { number: entry.info.number, head: entry.info.head, state: entry.info.state },
        stackIdentity?.source ?? null,
      ) ?? null;
    const key =
      readiness === null ? "none" : `${readiness.verdict}:${readiness.tone}:${readiness.label}`;
    if (entry.readinessKey === key) {
      return;
    }
    entry.readinessKey = key;
    entry.line = { ...entry.line, readiness };
    entry.run.show(entry.line);
  }

  /**
   * The lines a row's pull request changes, as it is now (row-lines.js), on the row's last
   * line: "+1,234 −567", the shell's brief change line of its line totals alone, with no file
   * total and no file statuses (mb-lqkb), a total of zero left out, "+1,234" where it only
   * adds lines, and "0 lines" where it changes none (mb-efum); the shell's pending
   * placeholder while it is read or its list is listed; or nothing where it cannot be had.
   * The chevron comes after them, on a line one line tall whatever it holds, with the age at
   * its end (github/styles.css, `.github-pulls-tail`), so a row whose lines cannot be had has
   * the chevron alone there, and moves nothing when its list is listed and its lines are read
   * after all: a row goes from none to waiting to shown as the prefetch lane lists its files
   * (mb-rb3n). The lines are said in
   * words, as a stack's row says its line (`rowLineHint`), in the hidden text that describes
   * the row, so the row is read with them.
   *
   * @param {PaintedRow} entry
   */
  function paintChange(entry) {
    const line = rowLines?.line({ number: entry.info.number, head: entry.info.head }) ?? {
      phase: "none",
    };
    const shown =
      line.phase === "shown"
        ? `${line.summary.generation}:${line.summary.additions}:${line.summary.deletions}`
        : line.phase;
    if (entry.changeKey === shown) {
      return;
    }
    entry.changeKey = shown;
    let words = null;
    if (line.phase === "shown") {
      const said = mb.changeLine(rowLineInput(line.summary, null));
      entry.changeLine.replaceChildren(...mb.changeLineNodes(said));
      words = said.label;
    } else if (line.phase === "waiting") {
      // The shell's pending placeholder (`.tally-pending`), after the quiet period
      // (`.mb-delayed-loading`), where the line will be; the name says nothing of it.
      entry.changePending ??= h(
        "span",
        { class: "mb-delayed-loading github-pulls-change-pending", "aria-hidden": "true" },
        [h("span", { class: "tally-pending" })],
      );
      if (
        entry.changeLine.firstChild !== entry.changePending ||
        entry.changeLine.childNodes.length !== 1
      ) {
        entry.changeLine.replaceChildren(entry.changePending);
      }
    } else {
      entry.changeLine.replaceChildren();
    }
    entry.changeWords.textContent = rowLineHint(words);
  }

  /**
   * Retain the logical row order and measurements; only the viewport builds DOM rows. The
   * order is the list's, or, grouped by stack, the model's rows: each stack's row, its Stack
   * Overview row and its pull requests at the second level, then every pull request in no
   * stack.
   *
   * @param {PullsModel} model
   */
  function paintRows(model) {
    /** @type {PaintedPlace[]} */
    const places = [];
    if (model.stacks.rows === null) {
      for (const row of model.rows) {
        places.push({
          kind: "pull",
          key: row.number,
          row,
          level: 1,
          stack: null,
          posinset: null,
          setsize: null,
        });
      }
    } else {
      const byNumber = new Map(model.rows.map((row) => [row.number, row]));
      /** The stack whose row was placed last, which its Stack Overview row follows.
       * @type {import("./pull-stacks.js").NativeStack | null} */
      let stack = null;
      for (const entry of model.stacks.rows) {
        const row = entry.kind === "pull" ? byNumber.get(entry.number) : undefined;
        if (entry.kind === "stack") {
          stack = entry.stack;
          places.push({ kind: "stack", key: entry.key, group: entry });
        } else if (entry.kind === "whole") {
          if (stack?.number === entry.stack) {
            places.push({ kind: "whole", key: entry.key, whole: entry, stack });
          }
        } else if (row !== undefined) {
          places.push({
            kind: "pull",
            key: entry.key,
            row,
            level: entry.level,
            stack: entry.stack,
            posinset: entry.posinset,
            setsize: entry.setsize,
          });
        }
      }
    }
    paintedRows = places;
    rowIndices = new Map(paintedRows.map((entry, index) => [entry.key, index]));
    rowHeads = new Map(model.rows.map((row) => [row.number, row.head]));
    rowWindow.setRows(paintedRows.map((entry) => entry.key));
  }

  /**
   * What a stack's Stack Overview row shows of its change line now (stack-lines.js).
   *
   * @param {import("./pull-stacks.js").NativeStack} stack
   * @returns {import("./stack-lines.js").StackLineState}
   */
  function stackLineState(stack) {
    return (
      stackLines?.line(stackMembers(stack), stackIdentity?.source ?? null) ?? { phase: "none" }
    );
  }

  /**
   * A stack as its change line is read for it: its members, and each one's head as the
   * list's row of it reports it, or null where the list holds none (stack-lines.js).
   *
   * @param {import("./pull-stacks.js").NativeStack} stack
   * @returns {import("./stack-lines.js").StackMembers}
   */
  function stackMembers(stack) {
    const heads = stack.pulls.map((number) => rowHeads.get(number) ?? null);
    return { number: stack.number, pulls: stack.pulls, heads };
  }

  /** When a stack's heading says the stack last changed, in epoch seconds, or null
   * (pull-stacks.js, `stackUpdatedAt`). @param {import("./pull-stacks.js").StackGroupRow} group */
  function stackUpdatedSeconds(group) {
    const parsed = group.updatedAt === null ? Number.NaN : Date.parse(group.updatedAt) / 1000;
    return Number.isFinite(parsed) ? parsed : null;
  }

  /** A stack's row's accessible name: its hint, the count its heading shows among it, then
   * its age as drawn, as a pull request's row says its own (`rowSaid`).
   * @param {string} hint @param {string} age */
  function stackSaid(hint, age) {
    return age === "" ? hint : `${hint} · ${age}`;
  }

  /**
   * A stack's row: the chevron, then its heading, the stack's label in the label register
   * the stack menu's heading has (`.group-heading`, docs/design-system.md, "Stacks"), then,
   * after a muted dot, how many pull requests the stack has, a count summary with its number
   * bold (`metabrowser.countPartsNodes`; "Heading Tallies"), then the age of the stack's
   * most recent change: "Stack #286 · 4 pulls  2h". The count is the stack's size (`stackPullsCount`),
   * which the row's accessible name says first, and the age the newest of its listed pull
   * requests' (`stackUpdatedAt`); both are known when the row is first drawn, the stacks'
   * snapshot and the list's rows being what draws it, so the row has no pending state and
   * nothing in it arrives later. The lines the stack changes are its Stack Overview row's
   * (`paintWholeRow`), which carries the stack's Layers glyph too (mb-68uk), so this row
   * draws none. A row of the tree that opens and closes, as a folder is; it opens no page, so
   * it is not a link.
   *
   * @param {import("./pull-stacks.js").StackGroupRow} group
   * @returns {PaintedStack}
   */
  function paintStackRow(group) {
    let entry = paintedStacks.get(group.key);
    if (entry === undefined) {
      const label = h("span", { class: "group-heading github-pull-stack-label" });
      const count = h("span", { class: "github-pulls-stack-count" });
      const at = stackUpdatedSeconds(group);
      const age = mb.ageLabel(at, { className: "github-pulls-age" });
      age.setAttribute("aria-hidden", "true");
      const heading = h("span", { class: "github-pulls-stack-heading" }, [label, count, age]);
      const row = h(
        "div",
        {
          class: "github-pulls-row github-pulls-stack-row disclosure-toggle",
          role: "treeitem",
          "aria-level": "1",
          tabindex: "-1",
        },
        [h("span", { class: "github-pulls-toggle", "aria-hidden": "true" }, [chevron()]), heading],
      );
      row.dataset.stack = String(group.stack.number);
      const item = h("li", { class: "github-pulls-item github-pulls-stack-item", role: "none" }, [
        row,
      ]);
      item.dataset.number = String(group.key);
      entry = {
        item,
        row,
        label,
        count,
        age,
        at,
        aged: age.textContent ?? "",
        hint: group.hint,
        stack: group.stack,
        key: "",
      };
      paintedStacks.set(group.key, entry);
      rowSizes?.observe(item);
    }
    entry.stack = group.stack;
    const pulls = stackPullsCount(group.stack);
    const key = JSON.stringify([group.label, group.hint, group.expanded, pulls, group.updatedAt]);
    if (entry.key !== key) {
      entry.key = key;
      entry.label.textContent = group.label;
      // "· 4 pulls": the dot is a count summary's separator, which the name needs no word
      // for, and the number is bold in the text's ink, as every count summary's is.
      entry.count.replaceChildren(
        ...mb.countPartsNodes([
          { separator: "·" },
          " ",
          { number: mb.formatInteger(pulls) },
          pulls === 1 ? " pull" : " pulls",
        ]),
      );
      const at = stackUpdatedSeconds(group);
      if (at !== entry.at) {
        entry.at = at;
        entry.aged = mb.retellAge(entry.age, at);
      }
      entry.hint = group.hint;
      entry.row.setAttribute("aria-label", stackSaid(group.hint, entry.aged));
      entry.row.setAttribute("aria-expanded", String(group.expanded));
      entry.row.classList.toggle("expanded", group.expanded);
      entry.row.classList.toggle("collapsed", !group.expanded);
    }
    entry.row.setAttribute("aria-posinset", String(group.posinset));
    entry.row.setAttribute("aria-setsize", String(group.setsize));
    entry.row.setAttribute("tabindex", group.key === anchorRow ? "0" : "-1");
    return entry;
  }

  /**
   * Draw a stack's Stack Overview row, the first under its open stack, beside its pull
   * requests' rows: a link to the stack's own page (`/stack/<n>`, stack-page.js), one line
   * in a member's row grid. The stack's Layers glyph, in the text's ink, is in the state
   * icon's slot (mb-68uk), and "Stack Overview" where the members' titles start; then, after a
   * muted dot, the lines the stack changes, "Stack Overview · +1,234 −567", the shell's brief
   * change line of its line totals alone, with no file statuses, as a pull request's row
   * says its own (`metabrowser.changeLine`; mb-lqkb), whose words the row's accessible name
   * says; then the registry's chevron, after the summary it expands, as a pull request's
   * row's last line ends (`buildRow`; docs/design-system.md, "Stack Groups in the Pulls
   * Tab"). While its stack's read is on its way the row holds the shell's pending
   * placeholder where the line will be, and its name says the change is pending; a stack
   * whose change cannot be had shows the chevron alone, and does not wait again until its
   * members or their heads change.
   *
   * The line and the chevron are the toggle of the stack's changed files (mb-odt4), the
   * stack's combined ones, which its page's Diff summary lists (stack-files.js): a press on
   * it opens or closes them under the row, a level in, in the tree a pull request's files
   * are drawn with (`treeFor`), and opens no page, though it is in the link, as a pull
   * request's toggle is in its own (mb-pw8t). It is for the pointer: Space, Right, and Left
   * on the row are its keys, and the row's `aria-expanded` its state. A press anywhere else
   * on the row opens the stack's page. No pull request is ever under this row. It takes the
   * current-row mark while the address is the stack's page.
   *
   * @param {import("./pull-stacks.js").WholeStackRow} whole
   * @param {import("./pull-stacks.js").NativeStack} stack
   */
  function paintWholeRow(whole, stack) {
    let entry = paintedWholes.get(whole.key);
    if (entry === undefined) {
      const line = h("span", { class: "github-pulls-stack-change" });
      // The toggle a pull request's row has (`.github-pulls-change`), keyed by this row.
      const change = h(
        "span",
        {
          class: "github-pulls-change github-pulls-whole-change disclosure-toggle collapsed",
          "aria-hidden": "true",
        },
        [line, h("span", { class: "github-pulls-toggle", "aria-hidden": "true" }, [chevron()])],
      );
      change.dataset.number = String(whole.key);
      const row = h(
        "a",
        {
          class: "github-pulls-row github-pulls-whole-row",
          role: "treeitem",
          "aria-level": String(whole.level),
          "aria-expanded": "false",
          href: `/stack/${whole.stack}`,
          tabindex: "-1",
        },
        [
          h("span", { class: "github-pull-stack-icon", "aria-hidden": "true" }, [
            stackSvg === null ? null : document.importNode(stackSvg, true),
          ]),
          h("span", { class: "github-pulls-whole-line" }, [
            h("span", { class: "github-pulls-title github-pulls-whole-title" }, [STACK_OVERVIEW]),
            change,
          ]),
        ],
      );
      row.dataset.stack = String(whole.stack);
      const item = h("li", { class: "github-pulls-item github-pulls-whole-item", role: "none" }, [
        row,
      ]);
      item.dataset.number = String(whole.key);
      item.dataset.level = String(whole.level);
      // Its files, kept across a row built again when it scrolls back into the window.
      trees.get(whole.key)?.attach(item, row, change);
      entry = { item, row, change, line, pending: null, stack, key: "" };
      paintedWholes.set(whole.key, entry);
      rowSizes?.observe(item);
    }
    entry.stack = stack;
    const line = stackLineState(stack);
    const shownLine = line.phase === "shown" ? line.change.revision : line.phase;
    const key = JSON.stringify([
      whole.posinset,
      whole.setsize,
      whole.key === currentRow,
      shownLine,
    ]);
    if (entry.key !== key) {
      entry.key = key;
      let name = wholeStackHint(whole.stack);
      if (line.phase === "shown") {
        // Its line totals alone, with no file statuses, a total of zero left out, as a pull
        // request's row says its own (mb-lqkb, mb-efum).
        const said = mb.changeLine(stackLineInput(line.change));
        // "Stack Overview · +1,234 −567": the dot is a count summary's separator, which the
        // name, saying the line in words, needs no word for.
        // Totals a member's list could not count, a binary file it listed, are not exact:
        // the Diff summary's muted "(estimated)" follows them, and the name says so (B4 of
        // review B on #484).
        const estimated = line.change.exact === false;
        entry.line.replaceChildren(
          ...mb.countPartsNodes([{ separator: "·" }]),
          ...mb.changeLineNodes(said),
          ...(estimated
            ? [h("span", { class: "github-pulls-stack-change-note" }, ["(estimated)"])]
            : []),
        );
        name = wholeStackHint(whole.stack, estimated ? `${said.label}, estimated` : said.label);
      } else if (line.phase === "waiting") {
        // The shell's pending placeholder (`.tally-pending`), after the quiet period
        // (`.mb-delayed-loading`), where the line will be. It is hidden from the
        // accessibility tree, and the name says the change is pending, in the filter chips'
        // words (review of #484, A5): "Stack Overview, Stack #286: change pending".
        name = wholeStackHint(whole.stack, "change pending");
        entry.pending ??= h(
          "span",
          { class: "mb-delayed-loading github-pulls-stack-change-pending", "aria-hidden": "true" },
          [h("span", { class: "tally-pending" })],
        );
        if (entry.line.firstChild !== entry.pending || entry.line.childNodes.length !== 1) {
          entry.line.replaceChildren(entry.pending);
        }
      } else {
        entry.line.replaceChildren();
      }
      entry.row.setAttribute("aria-label", name);
      entry.row.setAttribute("aria-posinset", String(whole.posinset));
      entry.row.setAttribute("aria-setsize", String(whole.setsize));
      markShown(entry.row, whole.key === currentRow);
    }
    entry.row.setAttribute("tabindex", whole.key === anchorRow ? "0" : "-1");
    return entry;
  }

  function visiblePlace() {
    const view = tab.scrollRoot?.getBoundingClientRect();
    if (view === undefined) {
      return null;
    }
    // Every drawn row, a stack's included: opening a stack at the top of the view keeps its
    // header where it is, rather than the pull request after it.
    const visible = [
      ...[...painted.entries()].map(([key, entry]) => /** @type {const} */ ([key, entry.item])),
      ...[...paintedStacks.entries()].map(
        ([key, entry]) => /** @type {const} */ ([key, entry.item]),
      ),
      ...[...paintedWholes.entries()].map(
        ([key, entry]) => /** @type {const} */ ([key, entry.item]),
      ),
    ].sort((left, right) => (rowIndices.get(left[0]) ?? 0) - (rowIndices.get(right[0]) ?? 0));
    for (const [key, item] of visible) {
      const box = item.getBoundingClientRect();
      if (box.bottom > view.top && box.top < view.bottom) {
        return { key, offset: box.top - view.top };
      }
    }
    return null;
  }

  /**
   * The place a paint keeps: a reveal's, until the list is scrolled other than by this view,
   * and otherwise the first row in view. A hidden panel keeps the place it had: its rows
   * have none, and the scroller it shares is another tab's, whose scroll is not the
   * reader's here. The Pulls tab's button returns to the list as the reader left it
   * (main-tabs.js, `revealPlan`), so stacks read while the reader was away, or just after,
   * regroup it around the row a reveal put in view. With the place forgotten on the way,
   * the row was regrouped out of view: #7, revealed far down the flat list, came back
   * 5,446 px above the pane, its stack's row undrawn (headless Chrome 152, 2026-11-18).
   *
   * @returns {{key: number, offset: number} | null}
   */
  function keptPlace() {
    if (!panelShown) {
      return readingPlace;
    }
    if (
      revealedPlace !== null &&
      Math.abs((tab.scrollRoot?.scrollTop ?? 0) - revealedPlace.scrollTop) >= 1
    ) {
      revealedPlace = null;
    }
    return revealedPlace === null
      ? visiblePlace()
      : { key: revealedPlace.key, offset: revealedPlace.offset };
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

  /**
   * Draw the window now as its rows measure, if their measures move it: the rows drawn are
   * measured as `rowSizes` will measure them, and a window frame waiting for a measure taken
   * is drawn at once. A lane calls this before its read names the rows drawn, so a window
   * first placed at `ROW_ESTIMATE_PX` and not yet drawn again at its rows' heights names the
   * rows those heights draw: at 340 px the browser was idle between the frame that measured
   * 47 rows and the frame that drew 49, and the read named 47 (mb-hb4a). The rows in view
   * are all among those drawn, so one pass places the window; the measures force no layout
   * the next frame would not have done.
   */
  function settleWindow() {
    if (windowDisposed || !panelShown) {
      return;
    }
    let remeasured = false;
    if (rowSizes !== null) {
      for (const [key, entry] of [...painted, ...paintedStacks]) {
        remeasured =
          rowWindow.measure(key, entry.item.getBoundingClientRect().height) || remeasured;
      }
    }
    if (!remeasured && windowFrame === null) {
      return;
    }
    if (windowFrame !== null) {
      window.cancelAnimationFrame(windowFrame);
      windowFrame = null;
    }
    paintViewport();
  }

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
        stacksInView = new Set();
        for (const entry of paintedStacks.values()) {
          const row = entry.row.getBoundingClientRect();
          if (row.bottom > row.top && row.bottom > view.top && row.top < view.bottom) {
            stacksInView.add(entry.stack.number);
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

  /**
   * Breathe a row's title while GitHub is read for it. Paint only: the row stays a usable
   * link, so it is not marked busy.
   *
   * @param {{title: HTMLElement, info: PullRow}} entry
   * @returns {boolean} Whether it is breathing.
   */
  function markRefreshing(entry) {
    const on = refreshingTitles.has(entry.info.number);
    entry.title.classList.toggle("mb-refreshing", on);
    return on;
  }

  /** @param {number[]} arrivals */
  function paintWindow(arrivals) {
    let builtRefreshing = false;
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
      view === undefined ? DISPLAY_ROWS * ROW_ESTIMATE_PX : view.bottom - listTop,
      protectedRows,
    );
    const wanted = new Set(pieces.filter((part) => part.kind === "row").map((part) => part.number));
    for (const [number, entry] of painted) {
      if (wanted.has(number)) {
        continue;
      }
      rowSizes?.unobserve(entry.item);
      trees.get(number)?.detach();
      entry.item.remove();
      painted.delete(number);
    }
    for (const [key, entry] of paintedStacks) {
      if (!wanted.has(key)) {
        rowSizes?.unobserve(entry.item);
        entry.item.remove();
        paintedStacks.delete(key);
      }
    }
    for (const [key, entry] of paintedWholes) {
      if (!wanted.has(key)) {
        rowSizes?.unobserve(entry.item);
        trees.get(key)?.detach();
        entry.item.remove();
        paintedWholes.delete(key);
      }
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
      const placed = paintedRows[part.index];
      if (placed.kind === "stack") {
        nodes.push(paintStackRow(placed.group).item);
        continue;
      }
      if (placed.kind === "whole") {
        nodes.push(paintWholeRow(placed.whole, placed.stack).item);
        continue;
      }
      const row = placed.row;
      const key = JSON.stringify(row);
      let entry = painted.get(row.number);
      if (entry === undefined) {
        entry = buildRow(row, key);
        entry.item.dataset.number = String(row.number);
        painted.set(row.number, entry);
        rowSizes?.observe(entry.item);
        builtRefreshing ||= markRefreshing(entry);
      } else if (entry.key !== key) {
        patchRow(entry, row, key);
      }
      paintPlace(entry, row.number, placed.stack);
      // A pull request under a stack's row is a level in, and its changed files with it
      // (`--github-pulls-level` in github/styles.css; pull-files-view.js reads the level).
      entry.row.setAttribute("aria-level", String(placed.level));
      entry.item.dataset.level = String(placed.level);
      entry.row.setAttribute("aria-posinset", String(placed.posinset ?? part.index + 1));
      entry.row.setAttribute("aria-setsize", String(placed.setsize ?? placedSize));
      paintChange(entry);
      paintReadiness(entry);
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
    // The stacks drawn, in the list's order, whose change lines are read, for their Stack
    // Overview rows; a hidden panel reads none. A stack is drawn where its own row or its Stack
    // Overview row is: a closed stack's line is read too, so the row has it when the stack
    // opens, and so is one whose own row is scrolled out of the window above its Stack
    // Overview row.
    stackLines?.want(
      panelShown
        ? [
            ...new Map(
              [...paintedStacks.entries(), ...paintedWholes.entries()]
                .sort(
                  ([left], [right]) => (rowIndices.get(left) ?? 0) - (rowIndices.get(right) ?? 0),
                )
                .map(([, entry]) => [entry.stack.number, entry.stack]),
            ).values(),
          ].map(stackMembers)
        : [],
      stackIdentity?.source ?? null,
    );
    // The pull requests drawn, in the list's order, whose runs read their change lines and
    // their readiness.
    const drawnPulls = panelShown
      ? [...painted.entries()].sort(
          ([left], [right]) => (rowIndices.get(left) ?? 0) - (rowIndices.get(right) ?? 0),
        )
      : [];
    rowLines?.want(
      drawnPulls.map(([number, entry]) => ({ number, head: entry.info.head })),
      stackIdentity?.source ?? null,
    );
    rowReadiness?.want(
      drawnPulls.map(([number, entry]) => ({
        number,
        head: entry.info.head,
        state: entry.info.state,
      })),
      stackIdentity?.source ?? null,
    );
    if (builtRefreshing) {
      alignRefreshing(list);
    }
    if (readingPlace !== null && tab.scrollRoot !== null && panelShown) {
      const item = listItem(readingPlace.key);
      if (item !== undefined && view !== undefined) {
        const delta = item.getBoundingClientRect().top - view.top - readingPlace.offset;
        if (Math.abs(delta) >= 0.5) {
          tab.scrollRoot.scrollTop += delta;
        }
        if (revealedPlace?.key === readingPlace.key) {
          // Where the row is now: at the list's top or end, the scroll falls short of it.
          revealedPlace.offset = item.getBoundingClientRect().top - view.top;
        }
      }
      if (revealedPlace !== null) {
        revealedPlace.scrollTop = tab.scrollRoot.scrollTop;
      }
    }
    if (focusBefore !== null && document.activeElement === document.body) {
      const arriving = focusBefore.isConnected
        ? focusBefore
        : focused === null
          ? null
          : rowElement(focused);
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
        const entry = painted.get(number);
        const row = entry?.row;
        if (entry === undefined || !row?.isConnected) {
          continue;
        }
        const box = row.getBoundingClientRect();
        if (box.bottom > box.top && box.bottom > top && box.top < view.bottom) {
          // The row's lines arrive together: they are all its link's.
          row.classList.add("tree-item-flash-in");
        }
      }
    }
    readingPlace = keptPlace();
    for (const number of treeOwners()) {
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
      const placed = index === undefined ? undefined : paintedRows[index];
      const grouped = placed?.kind === "pull" && placed.posinset !== null ? placed : null;
      if (index !== undefined) {
        entry.row.setAttribute("aria-posinset", String(grouped?.posinset ?? index + 1));
      }
      entry.row.setAttribute("aria-setsize", String(grouped?.setsize ?? size));
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
      const label = mb.retellAge(entry.age, entry.at);
      if (label !== entry.label) {
        entry.label = label;
        entry.said.textContent = rowSaid(entry.info, label);
      }
    }
    for (const entry of paintedStacks.values()) {
      if (entry.at === null) {
        continue;
      }
      const label = mb.retellAge(entry.age, entry.at);
      if (label !== entry.aged) {
        entry.aged = label;
        entry.row.setAttribute("aria-label", stackSaid(entry.hint, label));
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
        trees.get(number)?.detach();
      }
      painted.clear();
      for (const entry of paintedStacks.values()) {
        rowSizes?.unobserve(entry.item);
      }
      paintedStacks.clear();
      paintedRows = [];
      gaps.clear();
      readingPlace = null;
      revealedPlace = null;
      list.replaceChildren();
      paintedVersion = -1;
      for (const { chip } of tallies) {
        const on = chip.dataset.chipValue === model.filter;
        chip.setAttribute("aria-checked", String(on));
        chip.tabIndex = on ? 0 : -1;
      }
    }
    // A row a reveal put in view holds its place over arrivals and a regroup, at the top too.
    const atTop = revealedPlace === null && (tab.scrollRoot?.scrollTop ?? 0) <= 0;
    if (arrivals.length > 0 && atTop) {
      readingPlace = null;
    }
    // Flat rows change with the list's rows; grouped rows with the grouping too.
    const version =
      model.stacks.rows === null
        ? model.rowsVersion
        : `${model.rowsVersion}:${model.stacks.version}`;
    if (version !== paintedVersion) {
      // A grouped order replacing the drawn one at the top of the list, as the stacks arriving
      // after the first paint or the option turned on, keeps the top, as arrivals at the top
      // do: kept in place, the first pull request read pushed the stacks' rows above the view.
      if ((model.stacks.rows !== null || paintedGrouped) && atTop) {
        readingPlace = null;
      }
      paintedGrouped = model.stacks.rows !== null;
      paintedVersion = version;
      paintRows(model);
      placeRows(model.setSize);
    } else if (model.setSize !== placedSize) {
      placeRows(model.setSize);
    }
    for (const { chip, value, tally } of tallies) {
      const count = model.filterTotals?.[value] ?? null;
      const pending =
        count === null &&
        (model.connection?.state === "working" || model.connection?.refreshing === true);
      tally.classList.toggle("tally-pending", pending);
      tally.classList.toggle("tally-pending-narrow", pending);
      const text = count === null ? (pending ? "" : "—") : mb.formatInteger(count);
      if (tally.textContent !== text) {
        tally.textContent = text;
      }
      const description =
        count === null
          ? pending
            ? "count pending"
            : "count unavailable"
          : pullsCount(count, mb.formatInteger);
      const label = `${LIST_LABELS[value]}, ${description}`;
      if (chip.getAttribute("aria-label") !== label) {
        chip.setAttribute("aria-label", label);
      }
    }
    tellAges();
    list.setAttribute("aria-label", model.listName);
    list.hidden = model.rows.length === 0;
    // Keep the count's space while it loads. Add a connection line only when it has
    // a status to show.
    const summary = model.countSummary;
    status.replaceChildren(
      summary === null
        ? "\u00a0"
        : h("span", { class: "github-pulls-total-line" }, [
            h("span", { class: "github-pulls-total-lead" }, mb.countPartsNodes(summary.total)),
            summary.scope === null
              ? null
              : h("span", { class: "github-pulls-total-scope" }, mb.countPartsNodes(summary.scope)),
          ]),
    );
    const connected = model.connection;
    const working = connected?.state === "working";
    const retrying = connected?.retrying === true;
    const refreshing = connected?.refreshing === true;
    connectionText.classList.toggle("mb-delayed-loading", working);
    spinner.classList.toggle("mb-delayed-loading", retrying);
    spinner.hidden = !working && !retrying;
    // An outage being retried keeps its text beside the cached rows.
    connectionMessage.classList.toggle("mb-refreshing", refreshing);
    // Busy is said of the status text, never of Refresh or the line's help link.
    if (working || retrying || refreshing) {
      connectionText.setAttribute("aria-busy", "true");
    } else {
      connectionText.removeAttribute("aria-busy");
    }
    const message = connected?.text ?? "";
    if (refreshing && message === "") {
      status.setAttribute("aria-busy", "true");
    } else {
      status.removeAttribute("aria-busy");
    }
    if (message === "") {
      connection.remove();
    } else if (connection.parentNode === null) {
      status.parentNode?.insertBefore(connection, status.nextSibling);
    }
    if (connectionMessage.textContent !== message) {
      connectionMessage.textContent = message;
    }
    const breathing = new Set(model.refreshingRows ?? []);
    if (
      breathing.size !== refreshingTitles.size ||
      [...breathing].some((number) => !refreshingTitles.has(number))
    ) {
      refreshingTitles = breathing;
      let any = false;
      for (const entry of painted.values()) {
        any = markRefreshing(entry) || any;
      }
      if (any) {
        alignRefreshing(list);
      }
    }
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
    if (model.progress !== null) {
      if (progressText.textContent !== model.progress) {
        progressText.textContent = model.progress;
      }
      footChildren.push(progress);
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
      readingPlace = keptPlace();
      queueWindow();
    },
    { passive: true, signal },
  );

  // A key moved the focus, and not a reader arriving at a row: a walk reads nothing per row.
  let movingFocus = false;
  /** @type {ReturnType<typeof createComparisonWarmer> | null} */
  let warmer = null;
  /** @type {ReturnType<typeof createStackLines> | null} */
  let stackLines = null;
  /** @type {ReturnType<typeof createRowLines> | null} */
  let rowLines = null;
  /** @type {ReturnType<typeof createRowReadiness> | null} */
  let rowReadiness = null;

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
      formatCount: (count) => mb.formatInteger(count),
      retellAges: tellAges,
      refreshDetailChanged: updateRefreshTooltip,
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
        if (model.countSummary !== null && model.catalogReady) {
          mb.perf.measure("githubPulls:catalogReady", () => {});
        }
      },
      markCurrent(previous, next) {
        // The roving anchor and reader expansion remain; only the old page's mark leaves.
        if (previous !== null && previous !== next) {
          trees.get(previous)?.controller.setCurrent(null);
        }
        currentRow = markedRow(currentRow, previous, next);
        const leaving = previous === null ? undefined : rowElement(previous);
        if (leaving !== undefined) {
          markShown(leaving, false);
        }
        const arriving = next === null ? undefined : rowElement(next);
        if (arriving !== undefined) {
          markShown(arriving, true);
        }
      },
      markAnchor(previous, next, focus) {
        anchorRow = next;
        paintViewport();
        if (previous !== null) {
          rowElement(previous)?.setAttribute("tabindex", "-1");
        }
        if (next !== null) {
          const row = rowElement(next);
          row?.setAttribute("tabindex", "0");
          if (focus && row) {
            movingFocus = true;
            row.focus({ preventScroll: true });
            movingFocus = false;
            // The whole item and the ring round it.
            itemElement(next)?.scrollIntoView({ block: "nearest" });
          }
        }
      },
      reveal(number) {
        paintViewport();
        const zone = itemElement(number);
        const item = listItem(number);
        // The whole item, as a walk brings it (`markAnchor`).
        zone?.scrollIntoView({ block: "nearest" });
        const view = tab.scrollRoot?.getBoundingClientRect();
        revealedPlace = null;
        // A hidden panel's rows have no place, and its tab's reveal comes when it is shown.
        if (item !== undefined && view !== undefined && tab.scrollRoot !== null && panelShown) {
          const offset = item.getBoundingClientRect().top - view.top;
          revealedPlace = { key: number, offset, scrollTop: tab.scrollRoot.scrollTop };
          readingPlace = { key: number, offset };
        }
      },
      markOutside(text) {
        if (text === null) {
          outsideNote.remove();
          return;
        }
        outsideNote.textContent = text;
        if (outsideNote.parentNode === null) {
          const line = connection.parentNode === null ? status : connection;
          line.parentNode?.insertBefore(outsideNote, line.nextSibling);
        }
      },
      // A row, walked to by J and K or focused for Control-N, Control-P, or a keyboard Back,
      // or nothing, as when the row that had focus was drawn away.
      focusPlace() {
        const active = document.activeElement;
        if (active === null || active === document.body) {
          return "body";
        }
        return list.contains(active) ? "list" : "elsewhere";
      },
      open: (route) => nav.open(route),
      openStack: (number, replace) => nav.open({ number, tab: "", stack: true, replace }),
      filterChanged: (state) => nav.filterChanged(state),
      warmComparisons: (numbers) => warmer?.want(numbers),
      // The members whose lists the drawn stacks' lines wait for, those in view first, and
      // each list the prefetch refreshed, for the stacks that hold it (stack-lines.js).
      stackFiles: () => stackLines?.unsettled((number) => stacksInView.has(number)) ?? [],
      filesListed: (number) => stackLines?.listed(number),
      // The lists the prefetch was asked for and has listed, for the rows' change lines
      // (row-lines.js).
      listingFiles: (numbers) => rowLines?.listing(numbers),
      listedFiles: (numbers, idle) => rowLines?.listed(numbers, { idle }),
      // What the list's ask said of the scan of every open pull request's status, for the
      // rows' readiness (row-readiness.js).
      statusScan: (scan, endedAt) => rowReadiness?.scanned(scan, endedAt),
    },
    { filter: nav.filter, current: nav.current, checkout: nav.checkout === true },
  );
  // The comparisons of the pull requests a reader opens next, kept for the document so their
  // pages draw the Diff summary at once (comparison-prefetch.js). A record is the peek's when
  // a peek read it, and otherwise one cache read, which never asks GitHub and, marked
  // `warm=1`, is not counted as a view: the server's prefetch lane refreshes the records a
  // reader viewed last, and a warm is not one. Warming is idle work, so an SDK without
  // `whenIdle`, as a session's that drives the panel alone is, has none, as one without
  // `shortcuts` has no numbered controls below.
  warmer =
    typeof mb.whenIdle !== "function"
      ? null
      : createComparisonWarmer({
          async read(number, readSignal) {
            let envelope = await controller.knownRecord(number);
            if (envelope === null) {
              const response = await request(
                mb.perf,
                "GET",
                `${PULL_ROUTE}?number=${number}&warm=1`,
                { signal: readSignal },
              );
              envelope = response.status === 200 ? response.body : null;
            }
            if (!isPullEnvelope(envelope) || envelope.number !== number) {
              throw new Error(`no record of pull request ${number}`);
            }
            return {
              comparison: pullComparison(envelope),
              // The record's own freshness window, past which its head may have moved.
              freshForMs: envelope.fresh_for_s * 1000,
            };
          },
          load: diffComparisonLoader(mb),
          schedule: (callback) => mb.whenIdle(callback, { timeout: WARM_IDLE_TIMEOUT_MS }),
          cancel: (cancel) => /** @type {() => void} */ (cancel)(),
          isVisible: () => document.visibilityState === "visible",
          now: () => Date.now(),
        });
  // Each stack's brief change line, on its Stack Overview row, the stack's combined change
  // (stack-lines.js):
  // read for the stacks the list draws, when the browser is idle, once for each stack's
  // members and their heads, within the lines' own hourly cap, and drawn through the SDK's one
  // component for it. An SDK without `whenIdle` or the component has no lines, and its
  // headings no placeholders.
  stackLines =
    typeof mb.whenIdle !== "function" ||
    typeof mb.changeLine !== "function" ||
    typeof mb.changeLineNodes !== "function" ||
    typeof mb.countPartsNodes !== "function"
      ? null
      : createStackLines({
          read: (number, readSignal) =>
            request(mb.perf, "GET", `${STACK_CHANGE_ROUTE}?number=${number}`, {
              signal: readSignal,
            }),
          schedule: (callback) => mb.whenIdle(callback, { timeout: WARM_IDLE_TIMEOUT_MS }),
          cancel: (cancel) => /** @type {() => void} */ (cancel)(),
          isVisible: () => document.visibilityState === "visible" && panelShown,
          now: () => Date.now(),
          changed: () => queueWindow(),
        });

  // Each row's brief change line, what its own list of changed files sums to (row-lines.js):
  // read for the rows the list draws, in one request, when the browser is idle, from the
  // cache alone, and drawn through the SDK's one component for it. An SDK without `whenIdle`
  // or the component has no lines, and its rows show none.
  rowLines =
    typeof mb.whenIdle !== "function" ||
    typeof mb.changeLine !== "function" ||
    typeof mb.changeLineNodes !== "function"
      ? null
      : createRowLines({
          read: (numbers, readSignal) =>
            request(mb.perf, "GET", `${PULL_FILES_SUMMARY_ROUTE}?numbers=${numbers.join(",")}`, {
              signal: readSignal,
            }),
          schedule: (callback) => mb.whenIdle(callback, { timeout: WARM_IDLE_TIMEOUT_MS }),
          cancel: (cancel) => /** @type {() => void} */ (cancel)(),
          settle: settleWindow,
          isVisible: () => document.visibilityState === "visible" && panelShown,
          now: () => Date.now(),
          changed: () => queueWindow(),
        });

  // Each open row's readiness, the server's verdict on its operational status
  // (row-readiness.js): read for the rows the list draws, in one request, when the browser is
  // idle, from the cache alone, and again when the list's ask says the scan of every open pull
  // request's status started or ended, or a row's head or state moves. It is drawn with the
  // vocabulary's glyph (pull-readiness.js). An SDK without `whenIdle` reads none, and its rows'
  // columns stay empty.
  rowReadiness =
    typeof mb.whenIdle !== "function"
      ? null
      : createRowReadiness({
          read: (numbers, readSignal) =>
            request(mb.perf, "GET", `${PULL_STATUSES_ROUTE}?numbers=${numbers.join(",")}`, {
              signal: readSignal,
            }),
          schedule: (callback) => mb.whenIdle(callback, { timeout: WARM_IDLE_TIMEOUT_MS }),
          cancel: (cancel) => /** @type {() => void} */ (cancel)(),
          settle: settleWindow,
          isVisible: () => document.visibilityState === "visible" && panelShown,
          now: () => Date.now(),
          changed: () => queueWindow(),
        });

  const unbindFilters = controls.bind(filters, {
    onChange(key, value, select) {
      if (key === FILTER_GROUP && select === "one") {
        controller.setFilter(String(value));
      }
    },
  });
  // The navigation's one Refresh (static/refresh-plan.js) refreshes the pull request page
  // beside the tab and this list, each as a part of its own, for as long as the list is
  // mounted: the page `currentRow` names through its own `refresh` while it has something to
  // refresh, and the list through the repository's catalog job. The plan runs the page
  // among what is on screen, and the list there too while the tab is in front; the button,
  // its waiting state, and its number are the shell's.
  const releaseRefreshParts = [
    refreshParts?.provide("page", () => {
      const page = refreshPage();
      return page?.canRefresh?.() === true ? page.refresh?.() : undefined;
    }),
    refreshParts?.provide("pulls", () => controller.refresh()),
    refreshParts?.provideTooltip?.("page", () => refreshPage()?.refreshDetail?.() ?? null),
    refreshParts?.provideTooltip?.("pulls", controller.refreshDetail),
  ];
  // The state chips are situational: through the SDK's shortcut surface each takes a number,
  // 1 to 9, from its place among the screen's numbered controls, so the panel picks no digit,
  // and a hidden panel's chips hold none (docs/design-system.md, "Keyboard Shortcuts"). A
  // number runs what a click runs, then focuses the chip, as the group's arrow keys do, since
  // the list it replaces may have held focus. The navigation's Refresh, at the top of the
  // navigation, comes first in reading order. Each lasts until disposal aborts `signal`.
  if (typeof mb.shortcuts?.attach === "function") {
    for (const { chip, value } of tallies) {
      mb.shortcuts.attach(chip, {
        activate() {
          controller.setFilter(value);
          chip.focus();
        },
        id: `github.pulls.filter.${value}`,
        numbered: true,
        signal,
      });
    }
  }

  /**
   * A pull request's row, not a stack's Stack Overview row, which is a row link too.
   * @param {EventTarget | null} target
   */
  const rowOf = (target) => {
    const row =
      target instanceof Element
        ? /** @type {HTMLAnchorElement | null} */ (target.closest("a.github-pulls-row"))
        : null;
    return row?.classList.contains("github-pulls-whole-row") ? null : row;
  };

  /** @param {EventTarget | null} target */
  const changeOf = (target) =>
    target instanceof Element
      ? /** @type {HTMLElement | null} */ (target.closest(".github-pulls-change"))
      : null;

  /**
   * Focus *number*'s row, a pull request's or a Stack Overview row by its key, the item's one
   * stop, reading nothing and opening nothing: after a press on its toggle, or Left from the
   * top of its files. The pointer is on the item, or the files were under it, so nothing
   * scrolls.
   *
   * @param {number} number
   */
  function focusItem(number) {
    const row = treeOwner(number)?.row;
    if (row === undefined) {
      return false;
    }
    controller.focused(number);
    movingFocus = true;
    row.focus({ preventScroll: true });
    movingFocus = false;
    return true;
  }

  /**
   * The keys act on the row that has focus, which a pull request's or a stack's row has as
   * the tree's one stop: each makes it the anchor first, as focus reaching it by Tab does.
   * A poll, a window's read, a regroup, or a reveal settles the anchor on the current pull
   * request (`settleAnchor`) and moves its Tab stop there, but leaves focus where the reader
   * put it, on a row a press on a change line focused, say; without this, Right, Left,
   * Enter, Up, and Down would act on that other row while Space, which reads the focused
   * row, acted on this one (mb-1z7j).
   */
  function anchorFocusedRow() {
    const active = document.activeElement;
    const wholeRow = wholeRowOf(active);
    if (wholeRow !== null) {
      const key = wholeStackRowKey(Number(wholeRow.dataset.stack));
      if (paintedWholes.get(key)?.row === wholeRow) {
        controller.focused(key);
      }
      return;
    }
    const stackRow = stackRowOf(active);
    if (stackRow !== null) {
      const key = stackRowKey(Number(stackRow.dataset.stack));
      if (paintedStacks.get(key)?.row === stackRow) {
        controller.focused(key);
      }
      return;
    }
    const row = rowOf(active);
    const number = row === null ? Number.NaN : Number(row.dataset.number);
    if (row !== null && painted.get(number)?.row === row) {
      controller.focused(number);
    }
  }

  /** @param {EventTarget | null} target */
  const stackRowOf = (target) =>
    target instanceof Element
      ? /** @type {HTMLElement | null} */ (target.closest(".github-pulls-stack-row"))
      : null;
  /** @param {EventTarget | null} target */
  const wholeRowOf = (target) =>
    target instanceof Element
      ? /** @type {HTMLElement | null} */ (target.closest(".github-pulls-whole-row"))
      : null;
  list.addEventListener(
    "click",
    (event) => {
      const wholeRow = wholeRowOf(event.target);
      if (wholeRow !== null) {
        const stack = Number(wholeRow.dataset.stack);
        // A press on its toggle, its change line and the chevron after it, opens or closes
        // the stack's changed files, as a press on a pull request's does its own (below), and
        // opens no page, though the toggle is in the row's link (mb-pw8t): the row takes the
        // focus, so Space and the arrows go on from it. A modified press, which on the rest
        // of the link opens a new tab, toggles nothing and opens nothing.
        if (changeOf(event.target) !== null) {
          event.preventDefault();
          if (isPlainClick(event)) {
            const key = wholeStackRowKey(stack);
            focusItem(key);
            toggleRowFiles(key);
          }
          return;
        }
        // A link to the stack's page: a plain press opens it in the pane, as a pull request's
        // row opens its page; a new tab and a copied address are the browser's own.
        if (isPlainClick(event)) {
          event.preventDefault();
          controller.activateStack(stack);
        }
        return;
      }
      const stackRow = stackRowOf(event.target);
      if (stackRow !== null && isPlainClick(event)) {
        // One gesture, as a folder's: the row takes the anchor and opens or closes.
        const number = Number(stackRow.dataset.stack);
        controller.focused(stackRowKey(number));
        controller.setStackOpen(number);
        return;
      }
      // A press on a row's toggle, its lines and the chevron after them, opens or closes its
      // changed files, as a press on a folder's chevron does, and opens no page, though the
      // toggle is in the item's link (mb-pw8t); the item takes the focus, so Space and the
      // arrows go on from it. A modified press, which on the rest of the link opens a new tab,
      // toggles nothing and opens nothing.
      const change = changeOf(event.target);
      if (change !== null) {
        event.preventDefault();
        if (isPlainClick(event)) {
          const number = Number(change.dataset.number);
          focusItem(number);
          toggleRowFiles(number);
        }
        return;
      }
      const row = rowOf(event.target);
      // A press anywhere else on the item, its title, its place, its number, its author, or the
      // rest of its last line, the age too, opens the pull request, and its changed files stay
      // as they were. A new tab and a copied address are the browser's own.
      if (row !== null && isPlainClick(event)) {
        event.preventDefault();
        controller.activate(Number(row.dataset.number));
      }
    },
    { signal },
  );
  // A middle press on a row's toggle opens no tab either: the toggle is the item's link's only
  // part that is not the link's, a pull request's row's and a Stack Overview row's alike.
  list.addEventListener(
    "auxclick",
    (event) => {
      if (changeOf(event.target) !== null) {
        event.preventDefault();
      }
    },
    { signal },
  );
  list.addEventListener(
    "focusin",
    (event) => {
      const wholeRow = wholeRowOf(event.target);
      if (wholeRow !== null && !movingFocus) {
        controller.focused(wholeStackRowKey(Number(wholeRow.dataset.stack)));
        return;
      }
      const stackRow = stackRowOf(event.target);
      if (stackRow !== null && !movingFocus) {
        controller.focused(stackRowKey(Number(stackRow.dataset.stack)));
        return;
      }
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
  // The reader's last press or key anywhere, which a tree's late rows wait for.
  /** @type {number | null} */
  let lastInputAt = null;
  for (const type of ["pointerdown", "keydown"]) {
    document.addEventListener(
      type,
      () => {
        lastInputAt = Date.now();
      },
      { capture: true, signal },
    );
  }
  list.addEventListener(
    "pointerover",
    (event) => {
      // The row, whose toggle's press opens the files a peek asks for.
      const row = rowOf(event.target);
      if (row === null) {
        return;
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
    for (const number of treeOwners()) {
      trees.get(number)?.repaint();
    }
  }

  /** The tree a file row with focus is in. */
  const focused = () => (focusedTree === null ? undefined : trees.get(focusedTree)?.controller);

  const stacks = watchStacks((index) => {
    const hadMembership = stackIndex.byPull.size > 0;
    stackIndex = index;
    controller.setStacks(index);
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
      if (visible && revealedPlace !== null && tab.scrollRoot !== null) {
        // The scroll the tab is shown at is the shell's, its saved scroll put back
        // (main-tabs.js, `activateNavPanel`), not the reader's: the row a reveal placed is
        // kept from it. Rows regrouped or placed at other heights since it was saved, as
        // stacks read while the reader was away regroup them, no longer stand where they
        // did at that scroll, and a list not yet painted at its height clamps it, so taken
        // for the reader's scroll it let the row go, out of view (headless Chrome 152,
        // 2026-11-25, rows placed at `ROW_ESTIMATE_PX` and drawn shorter).
        revealedPlace.scrollTop = tab.scrollRoot.scrollTop;
      }
      stacks.setShown(visible);
      controller.setShown(visible);
      if (visible) {
        queueWindow();
      } else {
        // The place a reveal put the list in stays (keptPlace).
        cancelCoreSample();
        // Hiding the tab cancels its animations without an animationend event.
        clearArrivalFlashes();
      }
      for (const [number, tree] of trees) {
        tree.controller.setShown(visible && treeOwner(number) !== undefined);
      }
    },
    /**
     * The address names a pull request's page, and maybe one file of it, or, with *stack*, a
     * native stack's page. *again* reveals the pull request already current (the
     * controller's `setCurrent`).
     *
     * @param {number | null} number
     * @param {string | null} [file]
     * @param {{preserveScroll?: boolean, again?: boolean, stack?: number | null}} [options]
     */
    setCurrent(number, file = null, options) {
      if (currentRow !== null && currentRow !== number) {
        trees.get(currentRow)?.controller.cancelWalk();
      }
      if (focusedTree !== null && focusedTree !== number) {
        trees.get(focusedTree)?.controller.cancelWalk();
      }
      currentStack = options?.stack ?? null;
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
    /**
     * Up and Down walk the pull requests as wholes, and expand nothing: a row's open files
     * are reached by Right, as its other keys are its row's (mb-1z7j).
     *
     * @param {-1 | 1} delta @param {{repeat?: boolean}} [how]
     */
    move(delta, how) {
      anchorFocusedRow();
      return controller.move(delta, how);
    },
    released() {
      controller.released();
      focused()?.released();
    },
    /** Enter: on a row it opens the pull request; on a stack's row, the stack opens or closes. */
    activateAnchor() {
      anchorFocusedRow();
      return controller.activateAnchor();
    },
    /** Space on a pull request's row toggles its files in place. @param {number} number */
    toggleFiles(number) {
      if (!painted.has(number)) {
        return false;
      }
      toggleRowFiles(number);
      return true;
    },
    /** Space on a stack's row opens or closes it. @param {number} number */
    toggleStack: (number) => controller.setStackOpen(number),
    /** Space on a stack's Stack Overview row toggles the stack's files in place, as it does a
     * pull request's on its row. @param {number} stack */
    toggleStackFiles(stack) {
      const key = wholeStackRowKey(stack);
      if (!paintedWholes.has(key)) {
        return false;
      }
      toggleRowFiles(key);
      return true;
    },
    /**
     * Right, as on a folder: on a pull request's row, or a stack's Stack Overview row, its
     * files open, or, open, focus goes to the first. On a stack's row: it opens, or focus
     * goes to its first row, Stack Overview.
     */
    expand() {
      anchorFocusedRow();
      const number = controller.snapshot().anchor;
      if (number === null) {
        return false;
      }
      if (number < 0 && wholeStackOfKey(number) === null) {
        return controller.enterStack();
      }
      const open = expansion.isExpanded(number);
      // The files are the reader's from here, whoever opened them: an address's own close
      // with it, and these stay.
      expansion.expand(number);
      if (!open || !treeFor(number).controller.enter()) {
        holdRowPlace(number);
        setExpanded(number, true);
      }
      return true;
    },
    /**
     * Left, as on a folder: on a pull request's row, or a stack's Stack Overview row, its open
     * files close, or, closed, focus goes to the stack's row it is under. On a stack's row:
     * it closes.
     */
    collapse() {
      anchorFocusedRow();
      const number = controller.snapshot().anchor;
      if (number === null) {
        return false;
      }
      if ((number > 0 || wholeStackOfKey(number) !== null) && expansion.isExpanded(number)) {
        holdRowPlace(number);
        expansion.collapse(number);
        setExpanded(number, false);
        return true;
      }
      controller.leaveToStack();
      return true;
    },
    /** @param {-1 | 1} delta @param {{repeat?: boolean}} [how] */
    moveFile: (delta, how) => focused()?.move(delta, how) ?? false,
    fileLeft: () => focused()?.left() ?? false,
    fileRight: () => focused()?.right() ?? false,
    activateFile: () => focused()?.activateAnchor() ?? false,
    /**
     * Home (static/main-tabs.js, `goHome`): the list as a fresh load of `/view/` draws it.
     * Every row's changed files close, whoever opened them, with no read, and the rows go
     * back to every stack open and the Tab stop on the first. The lists of changed files
     * already read stay held, as the rows do, so a row opened again opens at once, with
     * the folders in it as the reader left them.
     */
    home() {
      for (const key of Object.keys(expansion.snapshot())) {
        const number = Number(key);
        expansion.collapse(number);
        setExpanded(number, false);
      }
      controller.home();
    },
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
      unwatchRefreshDetail?.();
      for (const release of releaseRefreshParts) {
        release?.();
      }
      window.clearTimeout(peekTimer);
      unbindFilters();
      stacks.dispose();
      controller.dispose();
      warmer?.dispose();
      stackLines?.dispose();
      rowLines?.dispose();
      rowReadiness?.dispose();
      for (const tree of trees.values()) {
        tree.dispose();
      }
      trees.clear();
      painted.clear();
      paintedStacks.clear();
      container.classList.remove("github-pulls");
      container.replaceChildren();
      // What it put in the toolbar slot and the band under it, outside the container.
      filters.remove();
      status.remove();
      connection.remove();
      outsideNote.remove();
    },
  });
}

/** @param {HTMLElement} container */
export function mountPullsLanding(container) {
  container.setAttribute("data-preview-empty", "");
  container.replaceChildren(h("div", { class: "preview-empty" }, ["Select a pull request."]));
}
