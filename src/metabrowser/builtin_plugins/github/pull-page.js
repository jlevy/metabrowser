// A pull request's page: header, conversation, reviews, review comments, checks, and
// Files changed, from the cached record alone. The number is the page's one input, and
// every route it asks names it, so a page for any number opens the same way.
//
// Every decision lives here without a DOM. `describePull` turns one answer of
// `GET /api/plugin/github/pull` into what the page shows; `createPullController` owns
// polling that route while the page is visible (quickly while a refresh runs or the
// record is pending, slowly otherwise, with If-None-Match so an unchanged answer is a
// 304), the refresh a stale page asks for and offers and an absent page offers
// (`POST /api/plugin/github/pull-refresh`), the switch to the pull request's head
// (`POST /api/source/pin`), the tab, and the Markdown of each text, asked for one part at
// a time from
// `GET /api/plugin/github/pull-markdown` and kept only for the record it was rendered
// from. `mountPullPage` is the browser glue: real fetch, timers, and paint.
// tests/dom/github-pull-page-session.js runs the same functions from the command line.
//
// What starts a fetch: a page opened at an address shows what is cached, whether the address
// was typed, followed from rendered content, or reached by Back, so only a reader's press of
// Fetch adds a pull request to the cache. A page with a record refreshes it by itself while
// it is visible and stale, as a stale mirror does, once per visible period and only once a
// reader has stayed on it, and the server holds each number to one attempt per window.
//
// All text is the pull request's own and untrusted. Paint writes it with textContent;
// only KPress's Markdown HTML is parsed, and only after it is reduced to an allowlist of
// plain markup twice: by the hook on the server (src/metabrowser/inert_html.py), and by
// static/inert-html.js, which rebuilds the inserted nodes from an inert template. No
// class, id, data, style, or event attribute survives, nor any SVG, media, stylesheet,
// frame, or form; an image becomes a link to it; a link is made absolute against the
// pull request's github.com page, kept only for http(s), and opened in a new tab with
// rel="noopener noreferrer"; and no KPress script is loaded for a text. KPress's
// stylesheets are, the route's one fixed list, and the page sets the rebuilt nodes in a
// KPress article of its own making, so a text reads as the same Markdown in a file does.

import { createComparisonPrefetch } from "./comparison-prefetch.js";
import { displayState, pullStateIcon } from "./pull-state.js";

// The same intervals as the freshness row (static/source-freshness.js), measured there:
// one second while a refresh runs makes its end visible promptly, and thirty seconds
// otherwise bounds how late a page learns of a refresh another tab started.
export const FAST_POLL_MS = 1000;
export const SLOW_POLL_MS = 30000;
// Markdown renders asked for at once. A render is one bounded body through KPress:
// 4 to 7 ms warm for a short comment (KPress 0.3.5, measured 2026-09-24 in-process on a
// loaded development machine), and a text nears the view before it is asked for, so two
// keep a long conversation filling in without queueing ahead of the page's polls.
export const MARKDOWN_CONCURRENCY = 2;
// How far from the view a text's Markdown is asked for: one pane's height above and below
// it, as an IntersectionObserver margin. A text asked for only once it is on screen shows
// its raw Markdown until the answer comes, which a fast scroll can catch. A render request
// took about 10 to 15 ms in a browser (2026-11-01), so one screen ahead is plenty, and it
// stays lazy: what is further off is not asked for until the reader comes nearer.
export const MARKDOWN_AHEAD = "100% 0px";
// How much of a review comment's diff hunk it shows; the rest is behind a disclosure.
// GitHub's `diff_hunk` runs from the hunk's `@@` line to the commented line, which is
// last, however long the hunk: on pallets/click#3030 (read 2026-11-01), 37 hunks of up to
// 253 lines took 35,104 px of a 62,117 px page. The tail is what is shown because that
// is where the comment anchors, and github.com shows the same end of it. Eight lines is
// a display choice, enough to read what a comment is about, and not a bound on any cost.
export const HUNK_TAIL_LINES = 8;
// The most of a hunk a comment shows, however long its range; the rest is behind the same
// disclosure. Unlike the tail this bounds a cost, as a commenter picks the range and a line
// shown is two nodes in a grid. Measured 2026-11-02 in headless Chrome 152 on a loaded
// development machine, a fresh process a run, from mount through layout: 250 comments of
// 16 KiB of blank lines, each with a range over all of them, took 26 to 28 s unbounded and
// 0.6 s here. The worst a record can do at this bound, 1,000 comments past it, took 1.6 to
// 1.8 s, and 1.0 s at 50, 2.7 s at 200, and 5.0 to 5.4 s at 400, so the cost is linear in it.
// It cuts little: of 1,858 multi-line comments read that day across 14 repositories, the
// 99th percentile was 34 lines, and 2 passed 100, both of 129.
export const HUNK_RANGE_LINES = 100;
// How long the pane stays still before its place is written to the history entry. A click
// writes at once, so this only keeps a moving pane from calling `history.replaceState`,
// which Safari limits to 100 calls in 30 s, and past that throws. Writes this long after the
// last move are at least this far apart, so 350 ms allows 85 in 30 s, however the reader
// paces their moves; 100 ms allowed 297 to a reader moving the pane in short tugs.
export const PLACE_WRITE_MS = 350;
// How long a landing holds its place after the page last changed height, for a page still
// rendering what it fetches. Measured 2026-11-02 in Chrome 152, Back onto a page loaded
// again, the widest gap between two changes in height: 231 ms for 34 files, 501 ms for a
// PR of 137 files whose diffs load as they come near, and 17 ms for a conversation of 120
// texts. A page that changes later than this keeps its place by the browser's own scroll
// anchoring, except in a browser without it.
export const LANDING_SETTLE_MS = 2000;
// How long a stale page is shown before it asks for its refresh. A reader who walks past
// pages, holding Back or a key, spends no refresh on one they did not stop at: in Chrome
// (2026-11-02) ten pages opened 30 ms apart started eight refreshes when each asked at once,
// and each is eight gh processes and a fetch that take about 5 s. It is a choice, longer than
// a press of Back takes and short beside the refresh it delays.
export const REFRESH_ASK_MS = 500;
// The blocks a place is counted in: the conversation's cards and sections, and Files
// changed's files, which keep their order for as long as the page shows one comparison.
// A place is an index, so a refresh that adds a card above it while a landing holds puts the
// pane one block off. Accepted: it takes a refresh completing inside the settle window.
const PLACE_BLOCKS = ".github-pull-card, .github-pull-section, .diff-file";
// The keys a browser moves a pane with. Tab is one, since moving focus scrolls to what takes it.
const PANE_KEYS = new Set([
  "ArrowUp",
  "ArrowDown",
  "PageUp",
  "PageDown",
  "Home",
  "End",
  " ",
  "Tab",
]);
// The key of a place in `history.state`, which no other code of the shell writes into.
const PLACE_KEY = "pullPlace";

// How long an idle browser may take before Files changed is fetched anyway. A page rendering
// its conversation is not idle, and the comparison should not wait for all of it.
const PREFETCH_IDLE_TIMEOUT_MS = 300;

const PULL_ROUTE = "/api/plugin/github/pull";
const REFRESH_ROUTE = "/api/plugin/github/pull-refresh";
const MARKDOWN_ROUTE = "/api/plugin/github/pull-markdown";
const PIN_ROUTE = "/api/source/pin";
export const TABS = Object.freeze(["", "files"]);

/** @type {Readonly<Record<string, string>>} */
const ABSENCE = Object.freeze({
  not_github: "This server serves no GitHub repository.",
  not_cached: "This pull request has not been fetched yet.",
  schema_mismatch: "The saved copy of this pull request is from another version.",
  unreadable: "The saved copy of this pull request could not be read.",
});

/** @type {Readonly<Record<string, string>>} */
const REVIEW_STATES = Object.freeze({
  APPROVED: "approved",
  CHANGES_REQUESTED: "requested changes",
  COMMENTED: "reviewed",
  DISMISSED: "review dismissed",
  PENDING: "review pending",
});

/** @type {Readonly<Record<string, string>>} */
const MERGEABLE = Object.freeze({
  mergeable: "No conflicts with the base branch.",
  conflicting: "Conflicts with the base branch.",
  unknown: "Merge status unknown.",
});

/** @type {Readonly<Record<string, string>>} */
const UNAVAILABLE = Object.freeze({
  check_runs: "Check runs",
  status: "Commit statuses",
  comparison: "Files changed",
});

/** @type {Readonly<Record<string, string>>} */
const TRUNCATED = Object.freeze({
  issue_comments: "comments",
  reviews: "reviews",
  review_comments: "review comments",
  check_runs: "check runs",
  statuses: "statuses",
});

/**
 * @typedef {{
 *   state: "absent" | "pending" | "current" | "stale",
 *   reason: string | null,
 *   number: number,
 *   pin: string | null,
 *   pin_ref: string | null,
 *   fetched_at: string | null,
 *   refreshing: boolean,
 *   last_refresh: {outcome: string, message: string | null, reset_at: string | null, at: string} | null,
 *   comparison_route: string | null,
 *   record: Record<string, any> | null,
 * }} PullEnvelope
 */

/**
 * @typedef {{
 *   kind: "comment" | "review",
 *   id: number,
 *   part: string,
 *   author: string,
 *   at: string | null,
 *   text: string,
 *   truncated: boolean,
 *   review: {state: string, label: string} | null,
 * }} TimelineItem
 */

/**
 * @typedef {{kind: "hunk" | "add" | "del" | "context" | "note", text: string}} HunkLine
 * @typedef {{earlier: string, earlierLines: number, shown: HunkLine[]}} HunkView
 */

/**
 * @typedef {{
 *   id: number,
 *   part: string,
 *   path: string,
 *   line: number | null,
 *   outdated: boolean,
 *   reply: boolean,
 *   author: string,
 *   at: string,
 *   text: string,
 *   truncated: boolean,
 *   hunk: HunkView | null,
 *   hunkTruncated: boolean,
 * }} ReviewCommentItem
 */

/**
 * @typedef {{name: string, detail: string | null, tone: string, label: string, url: string | null}} CheckItem
 */

/**
 * What Browse code is. One server has one pin, and other tabs share it, so opening a pull
 * request moves nothing: a `link` goes to the root of what is served, and a `switch` first
 * serves this pull request's head. `at` is the commit that opens, as a reader sees it.
 *
 * @typedef {{kind: "link", at: string} | {kind: "switch", ref: string, at: string}} BrowseCode
 */

/**
 * @typedef {{
 *   number: number,
 *   tab: string,
 *   status: "loading" | "absent" | "pending" | "current" | "stale" | "unavailable",
 *   recordAt: string | null,
 *   message: string | null,
 *   refreshing: boolean,
 *   canRefresh: boolean,
 *   freshness: string | null,
 *   failure: string | null,
 *   pull: null | {
 *     title: string, number: number, state: string, stateLabel: string, author: string,
 *     actor: string | null, action: string,
 *     base: string, head: string, htmlUrl: string, created: string, updated: string,
 *     closed: string | null, closedLabel: string | null, labels: string[],
 *     merge: {state: string, label: string} | null, text: string, truncated: boolean,
 *   },
 *   timeline: TimelineItem[],
 *   reviewComments: ReviewCommentItem[],
 *   checks: {counts: Record<string, number>, items: CheckItem[]} | null,
 *   notes: string[],
 *   comparison: {left: string, right: string, route?: string, headMoved: boolean} | null,
 *   browse: BrowseCode | null,
 *   filesUnavailable: string,
 *   headOffer: {ref: string, head: string, pin: string, text: string} | null,
 * }} PullModel
 */

/**
 * How long ago an ISO timestamp was, the way the freshness row says it.
 *
 * @param {string | null} iso
 * @param {number} nowMs
 */
export function relativeAge(iso, nowMs) {
  const at = iso === null ? Number.NaN : Date.parse(iso);
  if (!Number.isFinite(at)) {
    return "at an unknown time";
  }
  const seconds = Math.max(0, Math.floor((nowMs - at) / 1000));
  if (seconds < 60) {
    return "just now";
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes} min ago`;
  }
  const hours = Math.floor(minutes / 60);
  return hours < 48 ? `${hours} h ago` : `${Math.floor(hours / 24)} d ago`;
}

/** @param {unknown} value */
function text(value) {
  return typeof value === "string" ? value : "";
}

/** @param {unknown} value */
function list(value) {
  return Array.isArray(value) ? value : [];
}

/** @param {unknown} login */
function who(login) {
  return typeof login === "string" && login ? login : "ghost";
}

// The tone a completed check run's conclusion is painted with and counted under. As
// github.com's Checks page does (read 2026-09-24 on pytorch/pytorch#198558: "This job
// was cancelled", "was skipped", "failed", "This check was neutral"), a cancelled,
// skipped, or stale run is its own count, apart from neutral.
/** @type {Readonly<Record<string, string>>} */
const CONCLUSION_TONES = Object.freeze({
  success: "success",
  failure: "failure",
  timed_out: "failure",
  action_required: "failure",
  startup_failure: "failure",
  cancelled: "cancelled",
  skipped: "skipped",
  stale: "stale",
  neutral: "neutral",
});

// The tone of a commit status's state.
/** @type {Readonly<Record<string, string>>} */
const STATUS_TONES = Object.freeze({
  success: "success",
  failure: "failure",
  error: "failure",
  pending: "pending",
});

/**
 * How one check run is labeled and counted. A run that has not completed (queued,
 * in_progress, waiting, requested, pending, or no status at all) is pending; a completed
 * run is its conclusion's tone, and `unknown` when GitHub gave none or one it does not
 * document.
 *
 * @param {Record<string, any>} run
 * @returns {{tone: string, label: string}}
 */
export function checkRunResult(run) {
  const status = text(run.status);
  if (status !== "completed") {
    return { tone: "pending", label: (status || "pending").replaceAll("_", " ") };
  }
  const conclusion = text(run.conclusion);
  if (!Object.hasOwn(CONCLUSION_TONES, conclusion)) {
    return { tone: "unknown", label: conclusion.replaceAll("_", " ") || "no conclusion" };
  }
  return { tone: CONCLUSION_TONES[conclusion], label: conclusion.replaceAll("_", " ") };
}

/**
 * How one commit status is labeled and counted: its state's tone, and `unknown` for a
 * state GitHub does not document.
 *
 * @param {Record<string, any>} status
 * @returns {{tone: string, label: string}}
 */
export function commitStatusResult(status) {
  const state = text(status.state);
  if (!Object.hasOwn(STATUS_TONES, state)) {
    return { tone: "unknown", label: state || "unknown" };
  }
  return { tone: STATUS_TONES[state], label: state };
}

/**
 * A side of the pull request as github.com's header names it: the bare branch when head
 * and base are one repository, and `owner:branch` on both sides when they are not, as
 * in "into cli:trunk from 00200200:fix/…". A head whose fork was deleted names no
 * repository, so it differs from the base and the base is qualified too.
 *
 * @param {{ref?: unknown, repository?: unknown} | undefined} side
 * @param {boolean} crossRepository
 */
function sideName(side, crossRepository) {
  const ref = text(side?.ref);
  const repository = typeof side?.repository === "string" ? side.repository : null;
  if (repository === null) {
    return `${ref} (deleted fork)`;
  }
  return crossRepository ? `${repository.split("/")[0]}:${ref}` : ref;
}

/**
 * The conversation: comments and submitted reviews, oldest first. A review with no
 * body and only review comments still appears, as GitHub shows it.
 *
 * @param {Record<string, any>} record
 * @returns {TimelineItem[]}
 */
function timeline(record) {
  /** @type {TimelineItem[]} */
  const items = [];
  for (const comment of list(record.issue_comments)) {
    items.push({
      kind: "comment",
      id: comment.id,
      part: `issue_comment/${comment.id}`,
      author: who(comment.author),
      at: text(comment.created_at) || null,
      text: text(comment.body),
      truncated: comment.body_truncated === true,
      review: null,
    });
  }
  for (const review of list(record.reviews)) {
    const state = text(review.state);
    items.push({
      kind: "review",
      id: review.id,
      part: `review/${review.id}`,
      author: who(review.author),
      at: typeof review.submitted_at === "string" ? review.submitted_at : null,
      text: text(review.body),
      truncated: review.body_truncated === true,
      review: { state, label: REVIEW_STATES[state] ?? state.toLowerCase() },
    });
  }
  // A pending review has no time and sorts last; ties keep comments before reviews,
  // then ID order, so the order never depends on the engine's sort.
  return items.sort(
    (left, right) =>
      (left.at ?? "￿").localeCompare(right.at ?? "￿") ||
      (left.kind === right.kind ? left.id - right.id : left.kind === "comment" ? -1 : 1),
  );
}

/**
 * What one line of a diff hunk is, by its first character. `\ No newline at end of file`
 * is a note about the line before it.
 *
 * @param {string} line
 * @returns {HunkLine["kind"]}
 */
function hunkLineKind(line) {
  if (line.startsWith("@@")) {
    return "hunk";
  }
  if (line.startsWith("+")) {
    return "add";
  }
  if (line.startsWith("-")) {
    return "del";
  }
  return line.startsWith("\\") ? "note" : "context";
}

/**
 * @param {string} line
 * @returns {HunkLine}
 */
function hunkLine(line) {
  return { kind: hunkLineKind(line), text: line };
}

/**
 * How many lines of its side a review comment covers: one, or a multi-line comment's
 * range. `original_*` number the commit the hunk is from, and `line` and `start_line` the
 * head, or are gone when the comment is outdated. A later commit can change the distance
 * between them, so the larger is taken: a line too many costs nothing, and a range cut
 * short is what this exists to prevent.
 *
 * @param {Record<string, any>} comment
 */
function commentedSpan(comment) {
  /** @param {unknown} start @param {unknown} end */
  const span = (start, end) =>
    typeof start === "number" && typeof end === "number" && end >= start ? end - start + 1 : 1;
  return Math.max(
    span(comment.start_line, comment.line),
    span(comment.original_start_line, comment.original_line),
  );
}

/**
 * What a review comment shows of its hunk: `shown` is the tail, from the start of the
 * commented range if that is further back than `HUNK_TAIL_LINES` and no further than
 * `HUNK_RANGE_LINES`, and `earlier` is the text of the rest, `earlierLines` of them, for
 * the disclosure. One string and not a line each, as this runs on every poll and the page
 * compares what it answers as JSON: a line's kind is worked out when it is painted.
 * Counted back from the end, where the commented line is, along the comment's side of the
 * diff, because a hunk cut to fit the record has lost its `@@` line and the numbers it
 * starts from. A range reaching above what the record kept shows all of it. A comment is
 * on one side here: the record does not keep `start_side`, so a range starting on the
 * other side is counted on this one, and any of it that falls outside the tail is in the
 * disclosure.
 *
 * @param {string} hunk
 * @param {Record<string, any>} comment
 * @returns {HunkView}
 */
export function hunkView(hunk, comment) {
  const lines = hunk.replace(/\n$/, "").split("\n");
  const side = comment.side === "LEFT" ? "del" : "add";
  const furthest = Math.max(0, lines.length - HUNK_RANGE_LINES);
  let remaining = commentedSpan(comment);
  let rangeStart = lines.length;
  for (let index = lines.length - 1; index >= furthest && remaining > 0; index -= 1) {
    const kind = hunkLineKind(lines[index]);
    if (kind === "context" || kind === side) {
      remaining -= 1;
      rangeStart = index;
    }
  }
  const first = Math.min(rangeStart, lines.length - HUNK_TAIL_LINES);
  // A disclosure is a row of its own, so it never hides less than a row's worth: one
  // line, in practice the `@@` line of a hunk just past the tail.
  const cut = first <= 1 ? 0 : first;
  return {
    earlier: lines.slice(0, cut).join("\n"),
    earlierLines: cut,
    shown: lines.slice(cut).map(hunkLine),
  };
}

/**
 * A disclosure's lines are one text node until it is first opened, when they become a line
 * each and take their tints, because a record can hold 2,048,000 lines no one opens: 250
 * comments of 16 KiB of blank lines made 4.1M nodes and took 3.4 s, and take 28,000 and 0.4 s
 * this way (`HUNK_RANGE_LINES` says how that was measured). One node and not none, so its
 * text stays in the page for search, and so nothing moves in the frame the browser paints
 * before it fires `toggle`: the node is as tall as the lines will be. Once, as the lines
 * stay; a repaint replaces the disclosure, with its listener, and starts it closed.
 *
 * @param {EventTarget} details
 * @param {ChildNode} plain What it holds until then.
 * @param {string} earlier
 * @param {(lines: HunkLine[]) => Node} paintLines
 */
export function tintOnFirstOpen(details, plain, earlier, paintLines) {
  details.addEventListener(
    "toggle",
    () => plain.replaceWith(paintLines(earlier.split("\n").map(hunkLine))),
    { once: true },
  );
}

/**
 * Review comments by file, each thread's first comment before its replies.
 *
 * @param {Record<string, any>} record
 * @returns {ReviewCommentItem[]}
 */
function reviewComments(record) {
  /** @type {Map<number, Record<string, any>>} */
  const byId = new Map(list(record.review_comments).map((comment) => [comment.id, comment]));
  /** @param {Record<string, any>} comment */
  const root = (comment) => {
    let current = comment;
    const seen = new Set();
    while (typeof current.in_reply_to === "number" && byId.has(current.in_reply_to)) {
      if (seen.has(current.id)) {
        break;
      }
      seen.add(current.id);
      current = /** @type {Record<string, any>} */ (byId.get(current.in_reply_to));
    }
    return current;
  };
  return [...byId.values()]
    .map((comment) => ({ comment, thread: root(comment) }))
    .sort(
      (left, right) =>
        text(left.thread.path).localeCompare(text(right.thread.path)) ||
        left.thread.id - right.thread.id ||
        text(left.comment.created_at).localeCompare(text(right.comment.created_at)) ||
        left.comment.id - right.comment.id,
    )
    .map(({ comment }) => ({
      id: comment.id,
      part: `review_comment/${comment.id}`,
      path: text(comment.path),
      line: typeof comment.line === "number" ? comment.line : null,
      outdated: typeof comment.line !== "number",
      reply: typeof comment.in_reply_to === "number",
      author: who(comment.author),
      at: text(comment.created_at),
      text: text(comment.body),
      truncated: comment.body_truncated === true,
      hunk: text(comment.diff_hunk) === "" ? null : hunkView(text(comment.diff_hunk), comment),
      hunkTruncated: comment.diff_hunk_truncated === true,
    }));
}

/** @param {Record<string, any>} record */
function checks(record) {
  /** @type {CheckItem[]} */
  const items = [];
  for (const run of list(record.check_runs)) {
    items.push({
      name: text(run.name),
      detail: typeof run.app === "string" ? run.app : null,
      ...checkRunResult(run),
      url: typeof run.details_url === "string" ? run.details_url : null,
    });
  }
  for (const status of list(record.status?.statuses)) {
    items.push({
      name: text(status.context),
      detail: typeof status.description === "string" ? status.description : null,
      ...commitStatusResult(status),
      url: typeof status.target_url === "string" ? status.target_url : null,
    });
  }
  if (items.length === 0) {
    return null;
  }
  /** @type {Record<string, number>} */
  const counts = {};
  for (const item of items) {
    counts[item.tone] = (counts[item.tone] ?? 0) + 1;
  }
  return { counts, items };
}

/** @param {Record<string, any>} record */
function notes(record) {
  /** @type {string[]} */
  const said = [];
  const truncated = record.truncated ?? {};
  const cut = Object.keys(TRUNCATED).filter((name) => truncated[name] === true);
  if (cut.length > 0) {
    said.push(
      `Only some ${cut.map((name) => TRUNCATED[name]).join(", ")} are shown: the list was longer than what is kept.`,
    );
  }
  if (truncated.text === true) {
    said.push("Some text was cut to keep this pull request's data within its size limit.");
  }
  for (const [part, why] of Object.entries(record.unavailable ?? {})) {
    said.push(
      `${UNAVAILABLE[part] ?? part} could not be read (${String(why).replaceAll("_", " ")}).`,
    );
  }
  return said;
}

/**
 * What Files changed says in place of a diff, from the state the record names. Pure.
 *
 * A merge base the store's shallow history cannot settle is not a failure to read: the
 * diff could be computed and would be a guess, so the page says that it does not guess
 * and what would settle it.
 *
 * @param {unknown} why The record's `unavailable.comparison`.
 * @returns {string}
 */
export function filesUnavailableText(why) {
  if (why === "base_uncertain") {
    return "Files changed is not shown: this checkout's history is too shallow to know what this pull request changed. Metabrowser does not guess. A refresh with the network available fetches more history.";
  }
  if (why === "comparison_timeout") {
    return "Files changed is unavailable: checking this pull request's history took too long. Refresh to try again.";
  }
  if (why === "comparison_too_large") {
    return "Files changed is unavailable: checking this pull request's history exceeded the comparison limit.";
  }
  if (why === "commits_unavailable") {
    return "Files changed is unavailable: a commit of this pull request's history is not readable here. On a mirror borrowing from a checkout, the checkout no longer holds it.";
  }
  return "Files changed is unavailable: the pull request's base could not be compared with its head.";
}

/**
 * What the page shows for one answer of the pull route. Pure.
 *
 * @param {PullEnvelope | null} envelope
 * @param {{number: number, tab: string, nowMs: number, error?: string | null, fetching?: boolean}} page
 * @returns {PullModel}
 */
export function describePull(envelope, page) {
  /** @type {PullModel} */
  const model = {
    number: page.number,
    tab: page.tab,
    status: "unavailable",
    recordAt: null,
    message: page.error ?? null,
    refreshing: false,
    canRefresh: false,
    freshness: null,
    failure: null,
    pull: null,
    timeline: [],
    reviewComments: [],
    checks: null,
    notes: [],
    comparison: null,
    browse: null,
    filesUnavailable: filesUnavailableText(null),
    headOffer: null,
  };
  if (envelope === null) {
    // Nothing read yet: the page shows a spinner, and an error once a read failed.
    model.status = page.error ? "unavailable" : "loading";
    return model;
  }
  model.status = envelope.state;
  model.refreshing = envelope.refreshing;
  const last = envelope.last_refresh;
  if (last !== null && last.outcome !== "succeeded" && !envelope.refreshing) {
    model.failure = `The last refresh failed: ${last.message ?? last.outcome.replaceAll("_", " ")}`;
  }
  const record = envelope.record;
  if (envelope.state === "absent" || envelope.state === "pending" || record === null) {
    const fetching = envelope.state === "pending" || page.fetching === true;
    model.message = fetching
      ? "Fetching the pull request…"
      : (page.error ?? ABSENCE[envelope.reason ?? ""] ?? ABSENCE.not_cached);
    model.canRefresh =
      !fetching &&
      envelope.state === "absent" &&
      envelope.reason !== "not_github" &&
      !envelope.refreshing;
    return model;
  }
  model.recordAt = typeof record.fetched_at === "string" ? record.fetched_at : null;
  model.message = page.error ?? null;
  model.canRefresh =
    !envelope.refreshing &&
    (envelope.state === "stale" ||
      model.failure !== null ||
      (typeof record.unavailable?.comparison === "string" &&
        record.unavailable.comparison !== "no_store"));
  const age = relativeAge(record.fetched_at ?? null, page.nowMs);
  // The account the record was read as, without the tool that read it.
  const reader = text(record.reader).replace(/^gh:/, "");
  model.freshness = envelope.refreshing
    ? `Refreshing… · fetched ${age} by ${reader}`
    : `Fetched ${age} by ${reader}${envelope.state === "stale" ? " · may be out of date" : ""}`;
  const pull = record.pull ?? {};
  const crossRepository = pull.head?.repository !== pull.base?.repository;
  const state = displayState(pull);
  const merge = state === "open" || state === "draft" ? text(pull.mergeable) || "unknown" : null;
  const commits = typeof pull.commits === "number" ? pull.commits : null;
  const count = commits === null ? "" : ` ${commits} commit${commits === 1 ? "" : "s"}`;
  model.pull = {
    title: text(pull.title),
    number: pull.number,
    state,
    stateLabel: state[0].toUpperCase() + state.slice(1),
    author: who(pull.author),
    // github.com's words: "<merger> merged 6 commits into <base> from <head>", and for
    // an open, draft, or closed pull request "<author> wants to merge 1 commit into".
    // An account GitHub deleted is its "ghost"; a record that names no merger at all
    // says only "merged 6 commits into", rather than crediting anyone.
    actor:
      state !== "merged"
        ? who(pull.author)
        : typeof pull.merged_by === "string" && pull.merged_by
          ? pull.merged_by
          : null,
    action: `${state === "merged" ? "merged" : "wants to merge"}${count} into`,
    base: sideName(pull.base, crossRepository),
    head: sideName(pull.head, crossRepository),
    htmlUrl: text(pull.html_url),
    created: text(pull.created_at),
    updated: text(pull.updated_at),
    closed: state === "merged" ? pull.merged_at : state === "closed" ? pull.closed_at : null,
    closedLabel: state === "merged" ? "merged" : state === "closed" ? "closed" : null,
    labels: list(pull.labels).map(text),
    merge: merge === null ? null : { state: merge, label: MERGEABLE[merge] ?? MERGEABLE.unknown },
    text: text(pull.body),
    truncated: pull.body_truncated === true,
  };
  model.timeline = timeline(record);
  model.reviewComments = reviewComments(record);
  model.checks = checks(record);
  model.notes = notes(record);
  const head = text(pull.head?.sha);
  const headRef = `refs/pull/${pull.number}/head`;
  if (envelope.pin !== null && head !== "") {
    model.browse = { kind: "link", at: envelope.pin.slice(0, 12) };
    if (envelope.pin !== head && envelope.pin_ref === headRef) {
      // Served from this pull request's head, and a refresh found a newer one: the ref
      // moved, which the refresh fetched, so the page offers it rather than switching
      // under the reader.
      model.headOffer = {
        ref: headRef,
        head,
        pin: envelope.pin,
        text: `This page's code is ${envelope.pin.slice(0, 12)}, not the pull request's head ${head.slice(0, 12)}.`,
      };
    } else if (envelope.pin !== head) {
      // Anything else, such as a branch, a tag, or another pull request. Nothing is wrong,
      // so nothing is said: reading a pull request does not need its code served.
      model.browse = { kind: "switch", ref: headRef, at: head.slice(0, 12) };
    }
  }
  model.filesUnavailable = filesUnavailableText(record.unavailable?.comparison ?? null);
  const comparison = record.comparison;
  if (comparison && typeof comparison.base === "string" && typeof comparison.head === "string") {
    model.comparison = {
      left: comparison.base,
      right: comparison.head,
      ...(typeof envelope.comparison_route === "string"
        ? { route: envelope.comparison_route }
        : {}),
      // The page's code is the served pin; a record read at a newer head says so
      // rather than moving what the reader sees.
      headMoved: model.headOffer !== null,
    };
  }
  return model;
}

/**
 * Whether *response* is the pin guard's refusal of a page whose pin moved. The guard
 * answers it by reloading the page onto the commit now served, so the page says nothing
 * of its own meanwhile: a page Back restores polls before the guard's check, and its
 * "unavailable" would be on screen only until the reload.
 *
 * @param {{status: number, body: unknown}} response
 */
function pinChanged(response) {
  const body = /** @type {Record<string, unknown> | null} */ (
    response.body !== null && typeof response.body === "object" ? response.body : null
  );
  return response.status === 409 && body?.code === "pin_changed";
}

/**
 * @param {unknown} value
 * @returns {value is PullEnvelope}
 */
function isEnvelope(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const envelope = /** @type {Record<string, unknown>} */ (value);
  return (
    typeof envelope.state === "string" &&
    typeof envelope.refreshing === "boolean" &&
    Number.isInteger(envelope.number) &&
    Number(envelope.number) > 0 &&
    (envelope.record === null || typeof envelope.record === "object")
  );
}

/**
 * @typedef {{status: number, etag: string | null, body: unknown}} PullResponse
 * @typedef {{
 *   request(method: "GET" | "POST", route: string, options: {etag?: string | null, body?: unknown}): Promise<PullResponse>,
 *   schedule(callback: () => void, delayMs: number): unknown,
 *   cancel(handle: unknown): void,
 *   now(): number,
 *   isVisible(): boolean,
 *   render(model: PullModel): void,
 *   renderMarkdown(part: string, rendered: Record<string, any>): void,
 *   reload(): void,
 *   navigate(href: string): void,
 * }} PullDependencies
 */

/**
 * The polling, refresh, tab, and Markdown state machine for one page.
 *
 * @param {PullDependencies} deps
 * @param {{
 *   number: number,
 *   tab: string,
 *   reader?: {
 *     fetchAfterMs: number,
 *     initial: {etag: string | null, body: unknown} | null,
 *     walking?: () => boolean,
 *   } | null,
 * }} options
 */
export function createPullController(deps, options) {
  const pullRoute = `${PULL_ROUTE}?number=${options.number}`;
  /** @type {PullEnvelope | null} */
  let envelope = null;
  /** @type {string | null} */
  let etag = null;
  let tab = TABS.includes(options.tab) ? options.tab : "";
  /** @type {unknown} */
  let timer = null;
  let polling = false;
  let disposed = false;
  // One refresh asked for by itself per visible period: a stale page whose refresh cannot
  // run must not ask again on every poll.
  let refreshAskedWhileVisible = false;
  /** The ask that waits for `REFRESH_ASK_MS`. @type {unknown} */
  let askTimer = null;
  /** @type {string | null} */
  let error = null;
  /** @type {string | null} */
  let painted = null;
  /** The reader's selection in the Pulls tab that opened this page, if one did. */
  const reader = options.reader ?? null;
  let readerAsked = false;
  /** Asked for by a reader's selection, and the ask is on its way. */
  let fetching = false;
  /** Markdown by part, for the record fetched at `markdownFor`. @type {Map<string, Record<string, any>>} */
  const markdown = new Map();
  /** @type {string | null} */
  let markdownFor = null;
  /** @type {string[]} */
  const queue = [];
  const asked = new Set();
  let inFlight = 0;

  function model() {
    return describePull(envelope, {
      number: options.number,
      tab,
      nowMs: deps.now(),
      error,
      fetching,
    });
  }

  function render() {
    const next = model();
    const key = JSON.stringify(next);
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

  function cancelAsk() {
    if (askTimer !== null) {
      deps.cancel(askTimer);
      askTimer = null;
    }
  }

  /**
   * Ask after *delayMs*, and not while a key that opened this page is still held: the walk
   * has left it, and where it stops opens a page of its own, or this one again.
   *
   * @param {() => void} ask
   * @param {number} delayMs
   */
  function askAfter(ask, delayMs) {
    askTimer = deps.schedule(() => {
      if (!disposed && reader?.walking?.() === true) {
        askAfter(ask, delayMs);
        return;
      }
      askTimer = null;
      ask();
    }, delayMs);
  }

  function scheduleNext() {
    clearTimer();
    if (disposed || !deps.isVisible()) {
      return;
    }
    const fast = envelope === null || envelope.refreshing || envelope.state === "pending";
    timer = deps.schedule(
      () => {
        timer = null;
        void poll();
      },
      fast ? FAST_POLL_MS : SLOW_POLL_MS,
    );
  }

  // Every request that answers an envelope is numbered when it is sent. A slow poll sent
  // before a refresh started must not replace the refresh's answer when it lands after
  // it, so an answer older than the one the page shows is dropped.
  let sent = 0;
  let shownRequest = 0;

  /**
   * @param {PullEnvelope} next
   * @param {number} request The number of the request that answered it.
   * @returns {boolean} Whether the page now shows it.
   */
  function accept(next, request) {
    if (request < shownRequest) {
      return false;
    }
    shownRequest = request;
    envelope = next;
    const fetchedAt = next.record === null ? null : next.fetched_at;
    if (fetchedAt !== markdownFor) {
      // Another record: its texts may differ, so nothing rendered from the last one
      // is shown again. The page asks again for the parts a reader sees.
      markdownFor = fetchedAt;
      markdown.clear();
      asked.clear();
      queue.length = 0;
    }
    return true;
  }

  /**
   * Read the pull route. A hidden page does not poll; *first* is the page's own first
   * read, which a page opened in the background needs as much as a visible one.
   *
   * @param {boolean} [first]
   */
  async function poll(first = false) {
    if (disposed || polling || (!first && !deps.isVisible())) {
      return;
    }
    polling = true;
    const request = ++sent;
    try {
      const response = await deps.request("GET", pullRoute, { etag });
      if (disposed) {
        return;
      }
      if (response.status === 200 && isEnvelope(response.body)) {
        if (accept(response.body, request)) {
          etag = response.etag;
        }
        error = null;
      } else if (response.status === 304 || pinChanged(response)) {
        error = null;
      } else {
        error = `The pull request is unavailable (HTTP ${response.status}).`;
      }
    } catch {
      error = "The server did not answer.";
    } finally {
      polling = false;
    }
    if (disposed) {
      return;
    }
    render();
    scheduleNext();
    fetchForReader();
    if (
      deps.isVisible() &&
      envelope?.state === "stale" &&
      !envelope.refreshing &&
      !refreshAskedWhileVisible
    ) {
      refreshAskedWhileVisible = true;
      askAfter(() => void askForRefresh({ number: options.number }), REFRESH_ASK_MS);
    }
  }

  /**
   * A reader chose this page's row in the Pulls tab, and the cache has no record of it: that
   * is the action that adds one, as a press of Fetch is. A row a key stopped on waits a
   * moment, so that a reader tapping past it spends nothing.
   */
  function fetchForReader() {
    if (readerAsked || reader === null || envelope === null) {
      return;
    }
    readerAsked = true;
    if (envelope.state !== "absent" || envelope.reason === "not_github" || envelope.refreshing) {
      return;
    }
    fetching = true;
    render();
    askAfter(() => {
      fetching = false;
      void askForRefresh({ number: options.number, retry: true });
    }, reader.fetchAfterMs);
  }

  /**
   * Ask the server for a refresh and take the envelope it answers with. A refusal of the
   * page's own request says nothing to the reader, whose page still shows what it did and
   * still offers Refresh.
   *
   * @param {{number: number, retry?: boolean}} ask
   */
  async function askForRefresh(ask) {
    cancelAsk();
    const request = ++sent;
    try {
      const response = await deps.request("POST", REFRESH_ROUTE, { body: ask });
      const body = /** @type {{pull?: unknown, error?: unknown} | null} */ (response.body);
      if (
        (response.status === 202 || response.status === 200) &&
        body !== null &&
        isEnvelope(body.pull)
      ) {
        accept(body.pull, request);
        if (response.status === 202) {
          // The answer changed; the next poll must not be answered by a 304.
          etag = null;
        }
        error = null;
      } else if (ask.retry) {
        const said = body !== null && typeof body.error === "string" ? body.error : null;
        error = `The refresh was refused (${said ?? `HTTP ${response.status}`}).`;
      }
    } catch {
      if (ask.retry) {
        error = "The refresh request failed.";
      }
    }
    if (!disposed) {
      render();
      scheduleNext();
    }
  }

  /** A reader's own press of Fetch or Refresh, which the server always takes as due. */
  async function requestRefresh() {
    if (!disposed && model().canRefresh) {
      await askForRefresh({ number: options.number, retry: true });
    }
  }

  let switching = false;

  /**
   * Serve the pull request's head, and then go on. `POST /api/source/pin` is the freshness
   * row's own switch; a refusal says why and the page stays as it was.
   *
   * @param {string} ref
   * @param {() => void} then
   */
  async function serveHead(ref, then) {
    if (disposed || switching) {
      return;
    }
    switching = true;
    try {
      const response = await deps.request("POST", PIN_ROUTE, { body: { ref } });
      if (disposed) {
        return;
      }
      if (response.status === 200) {
        then();
        return;
      }
      const body = /** @type {{code?: unknown} | null} */ (response.body);
      const code = body !== null && typeof body.code === "string" ? body.code : "";
      error = `Could not switch to the head (${code || `HTTP ${response.status}`}).`;
    } catch {
      error = "The switch request failed.";
    } finally {
      switching = false;
    }
    if (!disposed) {
      render();
    }
  }

  /** The newer head the page offers: served, then reloaded so every view shows it. */
  async function switchToHead() {
    const offer = model().headOffer;
    if (offer !== null) {
      await serveHead(offer.ref, deps.reload);
    }
  }

  /**
   * Open code of this pull request at *href*, when the pin is elsewhere: its head is served
   * first, and the address loads as a new document. Back then lands on this page, rendered
   * for the earlier pin, which the shell's history guard reloads.
   *
   * @param {string} href
   */
  async function browseCode(href) {
    const browse = model().browse;
    if (browse?.kind === "switch") {
      await serveHead(browse.ref, () => deps.navigate(href));
    }
  }

  /** @param {string} next */
  function setTab(next) {
    if (disposed || !TABS.includes(next)) {
      return;
    }
    tab = next;
    render();
  }

  function pump() {
    while (!disposed && inFlight < MARKDOWN_CONCURRENCY && queue.length > 0) {
      const part = /** @type {string} */ (queue.shift());
      inFlight += 1;
      void deps
        .request(
          "GET",
          `${MARKDOWN_ROUTE}?number=${options.number}&part=${encodeURIComponent(part)}`,
          {},
        )
        .then((response) => {
          const body = /** @type {Record<string, any> | null} */ (response.body);
          if (
            disposed ||
            response.status !== 200 ||
            body === null ||
            typeof body.html !== "string" ||
            body.fetched_at !== markdownFor
          ) {
            // A render of a record the page no longer shows, or none at all: the
            // plain text stays, and a newer record is asked for again.
            return;
          }
          markdown.set(part, body);
          deps.renderMarkdown(part, body);
        })
        .catch(() => {})
        .finally(() => {
          inFlight -= 1;
          pump();
        });
    }
  }

  /**
   * Ask for one part's Markdown once per record. The glue asks when the part is within
   * `MARKDOWN_AHEAD` of the view, so a long conversation renders what a reader reaches.
   *
   * @param {string} part
   */
  function requestMarkdown(part) {
    if (disposed || markdownFor === null) {
      return;
    }
    const done = markdown.get(part);
    if (done !== undefined) {
      deps.renderMarkdown(part, done);
      return;
    }
    if (asked.has(part)) {
      return;
    }
    asked.add(part);
    queue.push(part);
    pump();
  }

  function onVisibilityChange() {
    if (disposed) {
      return;
    }
    if (!deps.isVisible()) {
      clearTimer();
      cancelAsk();
      refreshAskedWhileVisible = false;
      if (fetching) {
        fetching = false;
        readerAsked = false;
      }
      return;
    }
    void poll();
  }

  function dispose() {
    disposed = true;
    clearTimer();
    cancelAsk();
    queue.length = 0;
  }

  return Object.freeze({
    start: () => {
      // What the Pulls tab read when the row was chosen: the page paints with no empty frame,
      // and its first read then asks whether that is still so.
      const initial = reader?.initial?.body;
      if (isEnvelope(initial) && accept(initial, 0)) {
        etag = reader?.initial?.etag ?? null;
      }
      render();
      return poll(true);
    },
    poll: () => poll(),
    requestRefresh,
    switchToHead,
    browseCode,
    requestMarkdown,
    setTab,
    onVisibilityChange,
    dispose,
    snapshot: () => ({
      state: envelope?.state ?? null,
      etag,
      tab,
      timer:
        timer === null
          ? null
          : envelope === null || envelope.refreshing || envelope.state === "pending"
            ? "fast"
            : "slow",
      markdown: [...markdown.keys()],
      queued: [...queue],
      inFlight,
      error,
    }),
  });
}

// ── A reader's place in the pane ────────────────────────────────

/**
 * Where a reader was in a page: the block at the pane's top and how far into it.
 *
 * A block rather than a scroll offset, because the pixels above a place depend on what has
 * rendered: a text is plain until it comes near the view, a file's diff is empty until it
 * does, and a page opened again renders only what is near where it lands. `block` is -1
 * above the first block, in the header, where `top`, the scroll offset, says where.
 *
 * @typedef {{block: number, offset: number, top: number}} PanePlace
 */

/**
 * The place a pane shows. Pure.
 *
 * @param {number[]} tops Each block's top in the pane's scroll coordinates, in page order.
 * @param {number} scrollTop
 * @returns {PanePlace}
 */
export function placeAt(tops, scrollTop) {
  let block = -1;
  for (let index = 0; index < tops.length && tops[index] <= scrollTop; index += 1) {
    block = index;
  }
  const offset = block < 0 ? 0 : scrollTop - tops[block];
  return { block, offset: Math.round(offset), top: Math.round(scrollTop) };
}

/**
 * The scroll offset that shows *place*, or null while the page has no blocks to place it
 * in. A page that now has fewer blocks than it did shows its last.
 *
 * @param {PanePlace} place
 * @param {number[]} tops
 * @returns {number | null}
 */
export function scrollTopOf(place, tops) {
  if (tops.length === 0) {
    return null;
  }
  return place.block < 0 ? place.top : tops[Math.min(place.block, tops.length - 1)] + place.offset;
}

/**
 * @param {unknown} value
 * @returns {value is PanePlace}
 */
function isPanePlace(value) {
  const place = /** @type {Record<string, unknown> | null} */ (value);
  return (
    typeof value === "object" &&
    place !== null &&
    Number.isInteger(place.block) &&
    Number.isFinite(place.offset) &&
    Number.isFinite(place.top)
  );
}

/**
 * Whether a key press can move the pane, and so ends a landing's hold. A bare modifier cannot,
 * and in a field typing a letter or moving the caret does not, so a reader who starts typing
 * in a filter during the settle window keeps their place. Pure.
 *
 * @param {string} key
 * @param {{closest?: (selector: string) => unknown} | null} target
 */
export function keyMovesPane(key, target) {
  if (!PANE_KEYS.has(key)) {
    return false;
  }
  return key === "Tab" || !target?.closest?.("input, textarea, select, [contenteditable]");
}

/**
 * @typedef {{
 *   read(): unknown,
 *   write(place: PanePlace): void,
 *   measure(): PanePlace,
 *   apply(place: PanePlace): boolean,
 *   anchored(): boolean,
 *   toTop(): void,
 *   schedule(callback: () => void, delayMs: number): unknown,
 *   cancel(handle: unknown): void,
 * }} ScrollKeeperDependencies
 */

/**
 * Keeps a reader's place in a history entry and puts them back when history lands there.
 *
 * Only an entry the reader has been on holds a place, because a new entry's state is null:
 * so a fresh navigation starts at the top, a reload or a Back that loads the page again
 * lands where it was, and no navigation type needs reading. A kept page restored from the
 * back/forward cache never lands, since the browser kept its scroll.
 *
 * A landing holds its place while the page renders: each change in height puts the pane
 * back, until the reader moves it or the page has been still for `LANDING_SETTLE_MS`. An
 * address with a fragment names its own place, so a landing on one leaves the pane alone.
 *
 * *apply* answers whether the page has anything to place the pane in yet.
 *
 * @param {ScrollKeeperDependencies} deps
 */
export function createScrollKeeper(deps) {
  /** The place a landing is holding. @type {PanePlace | null} */
  let holding = null;
  /** @type {unknown} */
  let writeTimer = null;
  /** @type {unknown} */
  let settleTimer = null;
  let disposed = false;

  function cancelWrite() {
    if (writeTimer !== null) {
      deps.cancel(writeTimer);
      writeTimer = null;
    }
  }

  function cancelSettle() {
    if (settleTimer !== null) {
      deps.cancel(settleTimer);
      settleTimer = null;
    }
  }

  function hold() {
    if (holding === null || !deps.apply(holding)) {
      return;
    }
    cancelSettle();
    settleTimer = deps.schedule(() => {
      settleTimer = null;
      holding = null;
    }, LANDING_SETTLE_MS);
  }

  return Object.freeze({
    /** History arrived at an entry, or the page opened on one. */
    land() {
      if (disposed) {
        return;
      }
      // A write still waiting belongs to the entry history just left.
      cancelWrite();
      cancelSettle();
      holding = null;
      if (deps.anchored()) {
        return;
      }
      const saved = deps.read();
      if (isPanePlace(saved)) {
        holding = saved;
        hold();
      } else {
        deps.toTop();
      }
    },
    /** The page changed height. */
    contentChanged() {
      if (!disposed) {
        hold();
      }
    },
    /** The reader moved the pane, or may have: from here the place is theirs. */
    readerMoved() {
      holding = null;
      cancelSettle();
    },
    /** The pane scrolled. A place being held is not the reader's doing, so it is not written. */
    scrolled() {
      if (disposed || holding !== null) {
        return;
      }
      cancelWrite();
      writeTimer = deps.schedule(() => {
        writeTimer = null;
        deps.write(deps.measure());
      }, PLACE_WRITE_MS);
    },
    /** Write a waiting place now, before a click can move history on from this entry. */
    flush() {
      if (writeTimer !== null) {
        cancelWrite();
        deps.write(deps.measure());
      }
    },
    dispose() {
      disposed = true;
      holding = null;
      cancelWrite();
      cancelSettle();
    },
    snapshot: () => ({
      holding,
      writing: writeTimer !== null,
      settling: settleTimer !== null,
    }),
  });
}

// ── Browser glue ────────────────────────────────────────────────

/**
 * The GitPath wire of a slash-separated repository path, as `/view/` addresses a file
 * on a pinned revision, by the route codec's encoder. A path that is not one a tree
 * entry has (an empty segment) has no wire and addresses the root. Null when the page
 * has no codec, as a folder's does not: nothing is addressed then, not the root.
 *
 * @param {string} path
 * @returns {string | null}
 */
export function gitPathWire(path) {
  const codec = window.MetabrowserGitPath;
  return codec ? (codec.wire(path) ?? "") : null;
}

/**
 * The pull request's link, made safe to follow: absolute against its github.com page,
 * http(s) only. `null` for anything else, which paints as text.
 *
 * @param {string | null} href
 * @param {string} base
 */
export function safeLink(href, base) {
  if (href === null || href === "") {
    return null;
  }
  try {
    const url = new URL(href, base || undefined);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

/**
 * Whether *pathname* is this page's entry on *tab*: `/pull/<n>` or `/pull/<n>/files`, and
 * for Files changed one changed file's address, `/pull/<n>/files/<path>`, too, since that
 * is the same tab at a file. Pure.
 *
 * @param {string} pathname
 * @param {number} number
 * @param {string} tab
 */
export function onPageRoute(pathname, number, tab) {
  const route = `/pull/${number}${tab ? `/${tab}` : ""}`;
  const here = pathname.replace(/\/$/, "");
  return here === route || (tab === "files" && here.startsWith(`${route}/`));
}

/**
 * What Files changed does with the record's comparison. Pure.
 *
 * The diff keeps the comparison it was opened on: a record read at a newer head offers
 * it rather than changing the diff under the reader.
 *
 * @param {{left: string, right: string, route?: string} | null} mounted The comparison the diff shows.
 * @param {{left: string, right: string, route?: string} | null} comparison The record's.
 * @returns {"unavailable" | "mount" | "keep" | "offer"}
 */
export function filesAction(mounted, comparison) {
  if (comparison === null) {
    return "unavailable";
  }
  if (mounted === null) {
    return "mount";
  }
  return mounted.left === comparison.left &&
    mounted.right === comparison.right &&
    mounted.route === comparison.route
    ? "keep"
    : "offer";
}

/**
 * What the conversation shows, as one comparable string. Pure.
 *
 * @param {PullModel} model
 */
export function conversationKey(model) {
  return JSON.stringify([
    model.pull,
    model.timeline,
    model.reviewComments,
    model.checks,
    model.notes,
    // A review comment's file is a link or a button by this.
    model.browse?.kind ?? null,
  ]);
}

/**
 * What the conversation does when the page paints. Pure.
 *
 * It rebuilds only when what it shows changed, so the header's age ticking over does not
 * rebuild the comments under the reader. A refresh that changed no text keeps what is
 * rendered and asks again for the texts still plain, whose renders of the older record
 * were dropped.
 *
 * @param {{key: string, recordAt: string | null}} previous
 * @param {{key: string, recordAt: string | null}} next
 * @returns {"repaint" | "reask" | "keep"}
 */
export function conversationAction(previous, next) {
  if (previous.key !== next.key) {
    return "repaint";
  }
  return previous.recordAt !== next.recordAt ? "reask" : "keep";
}

/**
 * Whether a click on a link is the page's to handle: a modified or middle click opens
 * the link's own address the browser's way.
 *
 * @param {Event} event
 */
export function isPlainClick(event) {
  return !(
    event instanceof MouseEvent &&
    (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
  );
}

/**
 * @param {string} tag
 * @param {Record<string, string>} [attributes]
 * @param {Array<Node | string | null>} [children]
 */
export function h(tag, attributes = {}, children = []) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) {
    element.setAttribute(name, value);
  }
  for (const child of children) {
    if (child !== null) {
      element.append(child);
    }
  }
  return element;
}

/**
 * An outside link: new tab, no opener, no referrer. Text when the URL is not http(s).
 *
 * @param {string | null} href
 * @param {string} base
 * @param {Array<Node | string | null>} children
 * @param {string} [className]
 */
function outside(href, base, children, className = "") {
  const safe = safeLink(href, base);
  if (safe === null) {
    return h("span", className ? { class: className } : {}, children);
  }
  return h(
    "a",
    {
      href: safe,
      target: "_blank",
      rel: "noopener noreferrer",
      ...(className ? { class: className } : {}),
    },
    children,
  );
}

/**
 * Mount the page into *container*. Browser only.
 *
 * @param {HTMLElement} container
 * @param {MetabrowserPublicRenderContext} ctx
 * @param {MetabrowserPublicSdk} mb
 */
export function mountPullPage(container, ctx, mb) {
  const number = typeof ctx.number === "number" ? ctx.number : 0;
  const open = typeof ctx.open === "function" ? ctx.open : () => {};
  container.classList.add("github-pull");
  const header = h("div", { class: "github-pull-header github-pull-column" });
  const body = h("div", { class: "github-pull-body" });
  const live = h("span", { class: "sr-only", "aria-live": "polite" });
  // Between the header and the body, as wide as the pane, as a file's views are.
  const tabBar = h("div", { class: "tab-bar", role: "tablist", "aria-label": "Pull request" });
  container.replaceChildren(header, body, live);

  /** @type {PullModel | null} */
  let shown = null;
  let bodyKey = "";
  /** The record the conversation last asked for Markdown from. @type {string | null} */
  let markdownRecord = null;
  /** @type {Map<string, HTMLElement>} */
  const texts = new Map();
  // The allowlist a text's Markdown passes through before it is inserted; a text stays
  // plain if it cannot load.
  /** @type {Promise<MetabrowserInertHtmlRuntime | null>} */
  const inertReady = mb
    .ensureAsset("inert-html")
    .then(() => window.MetabrowserInertHtml ?? null)
    .catch(() => null);
  /** @type {{left: string, right: string, route?: string} | null} */
  let diffFor = null;
  /** @type {{dispose?: () => void} | null} */
  let diffHandle = null;
  /** @type {HTMLElement | null} */
  let diffHost = null;
  /** @type {Set<(file: Extract<import("../diff/diff-view.js").FileLookup, {kind: "file"}> | null) => void>} */
  const currentFileListeners = new Set();
  /** @type {(() => void) | null} */
  let unwatchCurrentFile = null;
  /** @type {number | null} */
  let currentFileFrame = null;
  /** @type {ReturnType<typeof window.setTimeout> | null} */
  let currentFileTimer = null;
  let currentFileGeneration = 0;

  function cancelCurrentFileBridge() {
    currentFileGeneration += 1;
    if (currentFileFrame !== null) {
      window.cancelAnimationFrame(currentFileFrame);
      currentFileFrame = null;
    }
    if (currentFileTimer !== null) {
      window.clearTimeout(currentFileTimer);
      currentFileTimer = null;
    }
  }

  /**
   * The diff subscription immediately measures its current file. Let the mounted bars
   * paint first, so that read does not force their layout into the mounting task. The
   * page's explicit currentFile/onCurrentFile calls retain their immediate snapshot.
   *
   * @param {HTMLElement} host
   * @param {{dispose?: () => void} | null} handle
   */
  function watchCurrentFileAfterPaint(host, handle) {
    cancelCurrentFileBridge();
    const generation = currentFileGeneration;
    const owns = () =>
      generation === currentFileGeneration &&
      !listening.signal.aborted &&
      diffHost === host &&
      diffHandle === handle;
    const subscribe = () => {
      if (!owns()) {
        return;
      }
      const reporting =
        /** @type {{onCurrentFile?: (listener: (file: Extract<import("../diff/diff-view.js").FileLookup, {kind: "file"}> | null) => void) => () => void} | null} */ (
          handle
        );
      const unwatch =
        reporting?.onCurrentFile?.((file) => {
          if (owns()) {
            reportCurrentFile(file);
          }
        }) ?? null;
      if (owns()) {
        unwatchCurrentFile = unwatch;
      } else {
        unwatch?.();
      }
    };
    if (typeof window.requestAnimationFrame === "function") {
      currentFileFrame = window.requestAnimationFrame(() => {
        if (!owns()) {
          return;
        }
        currentFileFrame = window.requestAnimationFrame(() => {
          if (owns()) {
            currentFileFrame = null;
            subscribe();
          }
        });
      });
    } else {
      // No animation frames in a nonvisual host. Readiness never waits for this task.
      currentFileTimer = window.setTimeout(() => {
        if (owns()) {
          currentFileTimer = null;
          subscribe();
        }
      }, 0);
    }
  }
  /** @type {string | null} */
  let reportedFileId = null;
  /** @param {Extract<import("../diff/diff-view.js").FileLookup, {kind: "file"}> | null} file */
  function reportCurrentFile(file) {
    const id = file?.fileId ?? null;
    if (id === reportedFileId) {
      return;
    }
    reportedFileId = id;
    for (const listener of currentFileListeners) {
      listener(file);
    }
  }
  /** The mounted diff's answer, without asking it to render anything. */
  function currentDiffFile() {
    const current =
      /** @type {{currentFile?: () => Extract<import("../diff/diff-view.js").FileLookup, {kind: "file"}> | null} | null} */ (
        diffHandle
      );
    return current?.currentFile?.() ?? null;
  }
  const pane = /** @type {HTMLElement | null} */ (container.closest("[data-kpress-viewport]"));
  // Rooted in the pane that scrolls, which the shell marks. With no root the root is the
  // window, and a margin on it does nothing here: a text past the pane's edge is clipped
  // by the pane on its way to the window, before the window's margin is applied.
  const observer =
    typeof IntersectionObserver === "function"
      ? new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              const part = entry.isIntersecting ? entry.target.getAttribute("data-part") : null;
              if (part !== null) {
                observer?.unobserve(entry.target);
                controller.requestMarkdown(part);
              }
            }
          },
          { root: pane, rootMargin: MARKDOWN_AHEAD },
        )
      : null;

  /**
   * An age, from the one primitive, with the exact time in its tooltip.
   *
   * @param {string} iso
   */
  const age = (iso) => {
    const at = Date.parse(iso);
    if (!Number.isFinite(at)) {
      return h("span", {}, [iso]);
    }
    const { label, className } = mb.formatAge(at / 1000);
    return h("span", { class: className, "data-tip-text": mb.formatTimestamp(at / 1000) }, [label]);
  };

  /**
   * A text of the pull request: plain until its Markdown arrives.
   *
   * @param {string} part
   * @param {string} value
   * @param {boolean} truncated
   */
  function textBlock(part, value, truncated) {
    const element = h("div", { class: "github-pull-text", "data-part": part });
    if (value.trim() === "") {
      element.append(
        h("p", { class: "github-pull-empty" }, [
          part === "body" ? "No description provided." : "No text.",
        ]),
      );
      return element;
    }
    element.append(h("div", { class: "github-pull-plain" }, [value]));
    if (truncated) {
      element.append(notice("warning", ["This text was cut; the rest is on GitHub."]));
    }
    texts.set(part, element);
    if (part === "body" || observer === null) {
      controller.requestMarkdown(part);
    } else {
      observer.observe(element);
    }
    return element;
  }

  /** KPress's stylesheets, once. A text stays readable under the shell's if they fail. */
  /** @type {Promise<void> | null} */
  let documentStyles = null;

  /**
   * @param {string} part
   * @param {Record<string, any>} rendered
   */
  function renderMarkdown(part, rendered) {
    documentStyles ??= mb.loadKpressAssets(rendered.assets).catch((error) => {
      console.warn("metabrowser github: the text styles did not load", error);
    });
    void Promise.all([inertReady, documentStyles]).then(([inert]) => {
      const element = texts.get(part);
      const plain = element?.querySelector(":scope > .github-pull-plain");
      if (!element || !plain || inert === null) {
        return;
      }
      // KPress's Markdown HTML, reduced to the allowlist on the server; GitHub's own
      // body_html is never used, and no KPress script is loaded for it.
      // static/inert-html.js parses it into an inert template and inserts only nodes
      // rebuilt from the same allowlist, links made absolute against the pull request.
      // The article and the classes on its tables and code blocks are the page's own.
      const nodes = inert.sanitizeHtml(
        String(rendered.html),
        shown?.pull?.htmlUrl ?? "https://github.com/",
      );
      plain.replaceWith(
        h("div", { class: "metabrowser-kpress-host" }, [
          h("article", { class: "kpress kpress-inert" }, [inert.kpressProse(nodes, document)]),
        ]),
      );
    });
  }

  /**
   * A text action's tooltip and accessible name: which commit opens, and whether the pin
   * switches, since the link and the button look the same.
   *
   * @param {string} label The control's text.
   * @param {string} what What opens. A path reaches only these attributes, as text.
   * @param {BrowseCode | null} browse
   * @returns {Record<string, string>}
   */
  function opensAt(label, what, browse) {
    if (browse === null) {
      return {};
    }
    const detail =
      browse.kind === "link"
        ? `Open ${what} at ${browse.at}, the commit this page shows`
        : `Switch to ${browse.at}, this pull request's head, and open ${what}`;
    return { "data-tip-text": detail, "aria-label": `${label}: ${detail}` };
  }

  /**
   * A review comment's file, as this pull request has it and not as whatever the server
   * serves has it. So where Browse code moves the pin this does too, and is a button: a link
   * would open the file under the current pin on a modified click.
   *
   * @param {string} path
   * @param {number | null} line
   * @param {BrowseCode | null} browse
   */
  function fileLink(path, line, browse) {
    const wire = mb.sourceKind() === "git_revision" && path !== "" ? gitPathWire(path) : null;
    if (wire === null) {
      return h("span", { class: "github-pull-file" }, [path]);
    }
    const target = { path: wire, ...(line === null ? {} : { fragment: `L${line}` }) };
    const href = mb.navigation.href(target);
    const label = line === null ? path : `${path}:${line}`;
    const tip = opensAt(label, path, browse);
    if (browse?.kind === "switch") {
      const button = h(
        "button",
        { type: "button", class: "github-pull-file github-pull-text-action", ...tip },
        [label],
      );
      button.addEventListener("click", () => void controller.browseCode(href));
      return button;
    }
    const link = h("a", { href, class: "github-pull-file", ...tip }, [label]);
    link.addEventListener("click", (event) => {
      if (isPlainClick(event)) {
        event.preventDefault();
        void mb.navigation.open(target);
      }
    });
    return link;
  }

  /**
   * Browse code, as the model says it is: a text action, the same to the eye either way.
   *
   * @param {BrowseCode} browse
   */
  function browseControl(browse) {
    const root = mb.navigation.href({ path: "" });
    const tip = opensAt("Browse code", "the code", browse);
    if (browse.kind === "link") {
      return h("a", { href: root, ...tip }, ["Browse code"]);
    }
    const button = h("button", { type: "button", class: "github-pull-text-action", ...tip }, [
      "Browse code",
    ]);
    button.addEventListener("click", () => void controller.browseCode(root));
    return button;
  }

  /**
   * A link to a tab of this page or to another pull request's page. A plain click stays
   * in the app: the shell's `open` puts the route in the URL and shows it.
   *
   * @param {{number: number, tab: string}} route
   * @param {string} className
   * @param {Array<Node | string>} children
   */
  function pageLink(route, className, children) {
    const link = h(
      "a",
      { href: `/pull/${route.number}${route.tab ? `/${route.tab}` : ""}`, class: className },
      children,
    );
    link.addEventListener("click", (event) => {
      if (!isPlainClick(event)) {
        return;
      }
      event.preventDefault();
      void open(route);
    });
    return link;
  }

  /** @param {string} state @param {string} label @param {string} [kind] */
  const badge = (state, label, kind = "state") =>
    h(
      "span",
      { class: `file-header-badge github-pull-badge github-pull-${kind}`, "data-state": state },
      [`${label.charAt(0).toUpperCase()}${label.slice(1)}`],
    );

  /**
   * The pull request's state: the same icon as its row, beside the word it is named by.
   *
   * @param {string} state
   * @param {string} label
   */
  const stateBadge = (state, label) => {
    const shown = badge(state, label);
    shown.prepend(
      pullStateIcon(/** @type {import("./pull-state.js").PullState} */ (state), {
        named: false,
      }),
    );
    return shown;
  };

  /**
   * A box about the content, on the shell's primitive; its severity is its border.
   *
   * @param {"warning" | "error" | null} severity
   * @param {Array<Node | string>} children
   */
  const notice = (severity, children) =>
    h(
      "div",
      {
        class: "notice github-pull-notice",
        ...(severity === null ? {} : { "data-severity": severity }),
      },
      children,
    );

  /** A branch, as the ref chip names one. @param {string} name */
  const branch = (name) =>
    h("span", { class: "git-ref git-ref-remote", "data-tip-text": name }, [name]);

  /** The registry's disclosure chevron, parsed once: a constant, not the pull request's text. */
  const chevronSvg = new DOMParser().parseFromString(mb.icons.toggle || "", "text/html").body
    .firstElementChild;
  function chevron() {
    return chevronSvg === null
      ? null
      : h("span", { class: "github-pull-fold-chevron", "aria-hidden": "true" }, [
          document.importNode(chevronSvg, true),
        ]);
  }

  /** One link per tab, kept across paints so a poll does not take focus from one. */
  const tabLinks = [
    { id: "", label: "Conversation" },
    { id: "files", label: "Files changed" },
  ].map(({ id, label }) => {
    const link = pageLink({ number, tab: id }, "tab-btn", [label]);
    link.setAttribute("role", "tab");
    tabBar.append(link);
    return { id, link };
  });

  /** @param {PullModel} model */
  function paintHeader(model) {
    const children = [];
    const pull = model.pull;
    if (pull !== null) {
      children.push(
        h("h1", { class: "github-pull-title" }, [
          pull.title,
          " ",
          h("span", { class: "github-pull-number" }, [`#${pull.number}`]),
        ]),
        h("div", { class: "github-pull-meta" }, [
          stateBadge(pull.state, pull.stateLabel),
          h("span", {}, [
            pull.actor === null ? null : h("strong", {}, [pull.actor]),
            `${pull.actor === null ? "" : " "}${pull.action} `,
            branch(pull.base),
            " from ",
            branch(pull.head),
          ]),
        ]),
        h("div", { class: "github-pull-quiet" }, [
          "Opened ",
          age(pull.created),
          " · updated ",
          age(pull.updated),
          ...(pull.closed && pull.closedLabel ? [` · ${pull.closedLabel} `, age(pull.closed)] : []),
          " · ",
          outside(pull.htmlUrl, "", ["View on GitHub"]),
          model.browse === null ? null : " · ",
          model.browse === null ? null : browseControl(model.browse),
        ]),
      );
      if (pull.labels.length > 0) {
        children.push(
          h(
            "div",
            { class: "github-pull-labels" },
            pull.labels.map((label) => h("span", { class: "github-pull-label" }, [label])),
          ),
        );
      }
    } else {
      children.push(h("h1", { class: "github-pull-title" }, [`Pull request #${model.number}`]));
    }
    const status = h("div", { class: "github-pull-status", "data-status": model.status }, [
      model.freshness,
    ]);
    if (model.status === "loading" || model.status === "pending") {
      // A quiet spinner, named for a screen reader; the pending message says why.
      const name = document.createElement("span");
      name.className = "sr-only";
      name.textContent = "Loading the pull request";
      status.append(
        h("div", { class: "loading mb-delayed-loading" }, [h("div", { class: "spinner" }), name]),
      );
    }
    if (model.message !== null) {
      status.append(h("span", { class: "github-pull-message" }, [model.message]));
    }
    if (model.failure !== null) {
      status.append(h("span", { class: "github-pull-failure" }, [model.failure]));
    }
    if (model.canRefresh) {
      const refresh = h("button", { type: "button", class: "btn github-pull-refresh" }, [
        model.status === "absent" ? "Fetch" : "Refresh",
      ]);
      refresh.addEventListener("click", () => void controller.requestRefresh());
      status.append(refresh);
    }
    if (model.headOffer !== null) {
      const button = h("button", { type: "button", class: "btn github-pull-switch" }, [
        "Switch to the head",
      ]);
      button.addEventListener("click", () => void controller.switchToHead());
      status.append(h("span", { class: "github-pull-offer" }, [model.headOffer.text, " ", button]));
    }
    children.push(status);
    header.replaceChildren(...children.filter((child) => child !== null));
    if (model.pull === null) {
      tabBar.remove();
    } else {
      for (const { id, link } of tabLinks) {
        link.classList.toggle("active", model.tab === id);
        link.setAttribute("aria-selected", String(model.tab === id));
      }
      header.after(tabBar);
    }
    live.textContent = [model.message, model.failure].filter(Boolean).join(" ");
  }

  /**
   * Lines of a diff hunk, each its own text node, as all of a pull request's text is.
   *
   * @param {HunkLine[]} lines
   */
  const hunkLines = (lines) =>
    h(
      "pre",
      { class: "github-pull-hunk" },
      lines.map((line) =>
        h("span", { class: "github-pull-hunk-line", "data-kind": line.kind }, [line.text]),
      ),
    );

  /** @param {PullModel} model */
  function paintConversation(model) {
    const pull = /** @type {NonNullable<PullModel["pull"]>} */ (model.pull);
    texts.clear();
    observer?.disconnect();
    const sections = [
      h("section", { class: "github-pull-card" }, [
        h("div", { class: "github-pull-card-head" }, [
          h("strong", {}, [pull.author]),
          " opened ",
          age(pull.created),
        ]),
        textBlock("body", pull.text, pull.truncated),
      ]),
    ];
    for (const item of model.timeline) {
      const head = h("div", { class: "github-pull-card-head" }, [h("strong", {}, [item.author])]);
      if (item.review !== null) {
        head.append(" ", badge(item.review.state, item.review.label, "review"));
      } else {
        head.append(" commented");
      }
      head.append(" ", item.at === null ? "(pending)" : age(item.at));
      const card = h("section", { class: `github-pull-card github-pull-${item.kind}` }, [head]);
      if (item.text.trim() !== "" || item.kind === "comment") {
        card.append(textBlock(item.part, item.text, item.truncated));
      }
      sections.push(card);
    }
    if (model.reviewComments.length > 0) {
      const threads = h("section", { class: "github-pull-section" }, [
        h("h2", { class: "section-heading" }, [`Review comments (${model.reviewComments.length})`]),
      ]);
      for (const comment of model.reviewComments) {
        const head = h("div", { class: "github-pull-card-head" }, [
          fileLink(comment.path, comment.line, model.browse),
          comment.outdated ? " " : "",
          comment.outdated ? badge("outdated", "outdated", "review") : null,
          " ",
          h("strong", {}, [comment.author]),
          ` ${comment.reply ? "replied" : "commented"} `,
          age(comment.at),
        ]);
        const card = h(
          "div",
          { class: `github-pull-card${comment.reply ? " github-pull-reply" : ""}` },
          [head],
        );
        if (!comment.reply && comment.hunk !== null) {
          const { earlier, earlierLines, shown: tail } = comment.hunk;
          // One box scrolls all of a hunk sideways, however far it is opened.
          const box = h("div", { class: "github-pull-hunk-box" });
          if (earlierLines > 0) {
            // Native, so the browser opens and closes it and a repaint just closes it.
            const lines = `line${earlierLines === 1 ? "" : "s"}`;
            const plain = hunkLines([{ kind: "context", text: earlier }]);
            const disclosure = h("details", { class: "github-pull-hunk-earlier" }, [
              h("summary", { class: "fold-expander" }, [
                chevron(),
                h("span", { class: "github-pull-fold-closed" }, [
                  `${earlierLines} earlier ${lines}`,
                ]),
                h("span", { class: "github-pull-fold-open" }, [`Hide ${earlierLines} ${lines}`]),
              ]),
              plain,
            ]);
            tintOnFirstOpen(disclosure, plain, earlier, hunkLines);
            box.append(disclosure);
          }
          box.append(hunkLines(tail));
          card.append(box);
          if (comment.hunkTruncated) {
            card.append(notice("warning", ["The start of this hunk was cut."]));
          }
        }
        card.append(textBlock(comment.part, comment.text, comment.truncated));
        threads.append(card);
      }
      sections.push(threads);
    }
    const summary = model.checks;
    const checksSection = h("section", { class: "github-pull-section" }, [
      h("h2", { class: "section-heading" }, ["Checks"]),
    ]);
    if (summary === null) {
      checksSection.append(
        h("p", { class: "github-pull-quiet" }, ["No checks or statuses reported."]),
      );
    } else {
      checksSection.append(
        h("p", { class: "github-pull-quiet" }, [
          Object.entries(summary.counts)
            .map(([tone, count]) => `${count} ${tone}`)
            .join(" · "),
        ]),
      );
      const rows = h("ul", { class: "github-pull-checks" });
      for (const item of summary.items) {
        rows.append(
          h("li", {}, [
            badge(item.tone, item.label, "check"),
            " ",
            outside(item.url, pull.htmlUrl, [item.name]),
            item.detail ? h("span", { class: "github-pull-quiet" }, [` ${item.detail}`]) : null,
          ]),
        );
      }
      checksSection.append(rows);
    }
    if (pull.merge !== null) {
      checksSection.append(
        h("p", { class: "github-pull-merge", "data-state": pull.merge.state }, [pull.merge.label]),
      );
    }
    sections.push(checksSection);
    for (const note of model.notes) {
      sections.push(notice("warning", [note]));
    }
    body.replaceChildren(...sections);
  }

  /** Settles when the diff last asked for has mounted, or was replaced. */
  let diffMounted = Promise.resolve();

  function disposeDiff() {
    cancelCurrentFileBridge();
    unwatchCurrentFile?.();
    unwatchCurrentFile = null;
    diffHandle?.dispose?.();
    diffHandle = null;
    diffHost = null;
    diffFor = null;
    reportCurrentFile(null);
  }

  const prefetch = createComparisonPrefetch({
    // The diff plugin spells the address, so the request `mountDiff` would make is this
    // one, byte for byte, and the browser's cache answers a Back from it.
    async load(comparison, signal) {
      await mb.ensureKindAssets("diff");
      const view =
        /** @type {{prefetch?: (comparison: object, signal: AbortSignal) => Promise<unknown>} | null} */ (
          mb.getRegisteredView("diff", "diff")
        );
      if (typeof view?.prefetch !== "function") {
        throw new Error("the diff view has no prefetch");
      }
      return view.prefetch(
        {
          left: comparison.left,
          right: comparison.right,
          base_policy: "merge_base",
          ...(comparison.route === undefined ? {} : { route: comparison.route }),
        },
        signal,
      );
    },
    warm() {
      void mb.ensureKindAssets("diff").catch(() => {});
    },
    schedule: (callback) =>
      typeof window.requestIdleCallback === "function"
        ? { idle: window.requestIdleCallback(callback, { timeout: PREFETCH_IDLE_TIMEOUT_MS }) }
        : { timer: window.setTimeout(callback, PREFETCH_IDLE_TIMEOUT_MS) },
    cancel(handle) {
      const { idle, timer } = /** @type {{idle?: number, timer?: number}} */ (handle);
      if (idle !== undefined) {
        window.cancelIdleCallback(idle);
      }
      window.clearTimeout(timer);
    },
    isVisible: () => document.visibilityState === "visible",
  });

  /** @param {{left: string, right: string, route?: string}} comparison */
  async function mountDiff(comparison) {
    disposeDiff();
    const host = h("div", { class: "github-pull-diff metabrowser-diff-host" });
    diffHost = host;
    diffFor = comparison;
    body.replaceChildren(host);
    try {
      const raw = prefetch.take(comparison);
      await mb.ensureKindAssets("diff");
      const view = mb.getRegisteredView("diff", "diff");
      if (diffHost !== host) {
        return;
      }
      if (!view) {
        host.textContent = "The diff plugin is unavailable.";
        return;
      }
      const prefetched = await raw;
      if (diffHost !== host) {
        return;
      }
      const handle = /** @type {{dispose?: () => void} | null} */ (
        await view.render(host, {
          comparison: {
            left: comparison.left,
            right: comparison.right,
            base_policy: "merge_base",
            ...(comparison.route === undefined ? {} : { route: comparison.route }),
          },
          ...(prefetched === undefined ? {} : { raw: prefetched }),
        })
      );
      if (diffHost !== host) {
        handle?.dispose?.();
        return;
      }
      diffHandle = handle;
      watchCurrentFileAfterPaint(host, handle);
      landFile();
    } catch {
      if (diffHost !== host) {
        return;
      }
      const retry = h("button", { type: "button", class: "btn" }, ["Retry"]);
      retry.addEventListener("click", () => {
        if (diffHost === host) {
          diffMounted = mountDiff(comparison);
        }
      });
      host.replaceChildren(notice("error", ["Files changed could not load. ", retry]));
    }
  }

  /** The changed file an address or the Pulls tab asked to see, until the diff can show it. */
  /** @type {string | null} */
  let wantedFile = null;

  /**
   * Go to a file of the mounted diff. docs/large-content-rendering.md ("Going to a file")
   * says what it promises.
   *
   * @param {string} path
   * @returns {import("../diff/diff-view.js").FileJump | {kind: "no_diff", path: string}}
   */
  function jumpTo(path) {
    const jump =
      /** @type {{scrollToFile?: (path: string) => import("../diff/diff-view.js").FileJump} | null} */ (
        diffHandle
      )?.scrollToFile;
    // A diff that did not load answers with no handle to jump in.
    if (typeof jump !== "function") {
      return { kind: "no_diff", path };
    }
    // A jump is the reader's own move, and a list beside the pane is not an input to it.
    place?.keeper.readerMoved();
    return jump(path);
  }

  /** Show the file asked for, once there is a diff to show it in. */
  function landFile() {
    if (wantedFile === null || diffHandle === null) {
      return null;
    }
    const path = wantedFile;
    wantedFile = null;
    return jumpTo(path);
  }

  /** @param {PullModel} model */
  function paintFiles(model) {
    const comparison = model.comparison;
    const action = filesAction(diffFor, comparison);
    if (comparison === null || action === "unavailable") {
      disposeDiff();
      body.replaceChildren(notice("error", [model.filesUnavailable]));
      return;
    }
    if (action === "mount") {
      diffMounted = mountDiff(comparison);
    } else if (action === "offer") {
      const offer = h("button", { type: "button", class: "btn github-pull-newer" }, [
        "Show the newer changes",
      ]);
      offer.addEventListener("click", () => {
        // What `whenFilesReady` waits for is the diff last asked for, this one included.
        diffMounted = mountDiff(comparison);
      });
      body.querySelector(".github-pull-newer-offer")?.remove();
      const said = notice(null, [
        diffFor?.right === comparison.right
          ? "The comparison has changed. "
          : `The pull request now ends at ${comparison.right.slice(0, 12)}. `,
        offer,
      ]);
      said.classList.add("github-pull-newer-offer");
      body.prepend(said);
    }
  }

  /** @param {PullModel} model */
  function paint(model) {
    shown = model;
    paintHeader(model);
    // The conversation reads in the column; a diff takes the pane.
    body.classList.toggle("github-pull-column", model.tab !== "files");
    if (model.pull === null) {
      disposeDiff();
      texts.clear();
      body.replaceChildren();
      bodyKey = "";
      return;
    }
    if (model.tab === "files") {
      bodyKey = "";
      texts.clear();
      paintFiles(model);
      return;
    }
    disposeDiff();
    if (model.comparison !== null) {
      prefetch.want(model.comparison);
    }
    const key = conversationKey(model);
    const action = conversationAction(
      { key: bodyKey, recordAt: markdownRecord },
      { key, recordAt: model.recordAt },
    );
    bodyKey = key;
    if (action === "repaint") {
      paintConversation(model);
    } else if (action === "reask") {
      for (const [part, element] of texts) {
        if (element.querySelector(":scope > .github-pull-plain") === null) {
          continue;
        }
        if (part === "body" || observer === null) {
          controller.requestMarkdown(part);
        } else {
          observer.observe(element);
        }
      }
    }
    markdownRecord = model.recordAt;
  }

  // Disposing a page ends its work: a superseded page's requests are cancelled, whatever
  // answer they were waiting for, and its listeners go with them.
  const listening = new AbortController();
  const controller = createPullController(
    {
      async request(method, route, options) {
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
          signal: listening.signal,
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
      },
      schedule: (callback, delayMs) => window.setTimeout(callback, delayMs),
      cancel: (handle) => window.clearTimeout(/** @type {number} */ (handle)),
      now: () => Date.now(),
      isVisible: () => document.visibilityState === "visible",
      render: paint,
      reload: () => window.location.reload(),
      navigate: (href) => window.location.assign(href),
      renderMarkdown,
    },
    { number, tab: typeof ctx.tab === "string" ? ctx.tab : "", reader: ctx.reader ?? null },
  );
  document.addEventListener(
    "visibilitychange",
    () => {
      controller.onVisibilityChange();
      // A page opened behind another tab is not prefetched until it is looked at: the
      // wish is not recorded while hidden, so it is asked again when shown.
      if (document.visibilityState === "visible" && shown?.tab !== "files") {
        const comparison = shown?.comparison ?? null;
        if (comparison !== null) {
          prefetch.want(comparison);
        }
      }
    },
    { signal: listening.signal },
  );
  void controller.start();
  const place = pane === null ? null : keepPlace(pane, body, () => shown?.tab ?? "", number);
  place?.keeper.land();
  return Object.freeze({
    /**
     * Show a tab. A tab owns the address (Browser URL Grammar), so a call from beside the
     * page goes through the route, which moves the address and calls back here, and Back
     * then behaves as it does after a click; the route's own calls find the address in
     * place already.
     *
     * @param {string} next
     */
    setTab(next) {
      if (TABS.includes(next) && !onPageRoute(window.location.pathname, number, next)) {
        void open({ number, tab: next });
        return;
      }
      const changed = controller.snapshot().tab !== next;
      controller.setTab(next);
      if (changed) {
        place?.keeper.land();
      }
    },
    /**
     * History arrived at this route. Its saved position takes priority over a file start,
     * and stays held while a newly mounted diff changes height.
     * @param {{tab: string, file?: string}} route
     */
    land(route) {
      controller.setTab(route.tab);
      place?.keeper.land();
      wantedFile = place?.keeper.snapshot().holding ? null : (route.file ?? null);
      landFile();
    },
    /** History is about to leave this entry: write its place now. */
    flush() {
      place?.keeper.flush();
    },
    /**
     * Go to a file of Files changed, for a list of the pull request's files beside the page.
     * docs/large-content-rendering.md ("Going to a file") says what it promises.
     *
     * @param {string} path
     * @returns {import("../diff/diff-view.js").FileJump | {kind: "no_diff", path: string}}
     */
    scrollToFile: jumpTo,
    /**
     * Show one changed file, as its address `/pull/<n>/files/<path>` names it: Files changed,
     * with the diff at that file. Whoever calls moves the address, the page host before it or
     * a walk of the Pulls tab's files once it stops, so this moves none. Until the diff has
     * mounted the file waits, and the newest asked for is the one shown. A reader's new
     * selection ends any earlier history landing's hold.
     *
     * The answer is the jump's, or `no_diff` for a file that waits for the diff.
     *
     * @param {string} path
     * @returns {import("../diff/diff-view.js").FileJump | {kind: "no_diff", path: string}}
     */
    showFile(path) {
      place?.keeper.readerMoved();
      if (controller.snapshot().tab !== "files") {
        controller.setTab("files");
      }
      wantedFile = path;
      return landFile() ?? { kind: "no_diff", path };
    },
    /**
     * Whether Files changed holds a path, typed as `scrollToFile` is: `no_diff` while no
     * diff is mounted, else what the diff says, `file` or `not_in_comparison`.
     *
     * @param {string} path
     * @returns {import("../diff/diff-view.js").FileLookup | {kind: "no_diff", path: string}}
     */
    fileForPath(path) {
      const lookup =
        /** @type {{fileForPath?: (path: string) => import("../diff/diff-view.js").FileLookup} | null} */ (
          diffHandle
        )?.fileForPath;
      return typeof lookup === "function" ? lookup(path) : { kind: "no_diff", path };
    },
    /** Settles when a diff asked for by `setTab("files")` has mounted. */
    whenFilesReady: () => diffMounted,
    currentFile: currentDiffFile,
    /** Follow the mounted diff across replacement and tab changes. @param {(file: Extract<import("../diff/diff-view.js").FileLookup, {kind: "file"}> | null) => void} listener */
    onCurrentFile(listener) {
      if (listening.signal.aborted) {
        return () => {};
      }
      currentFileListeners.add(listener);
      listener(currentDiffFile());
      return () => currentFileListeners.delete(listener);
    },
    dispose() {
      listening.abort();
      observer?.disconnect();
      place?.dispose();
      controller.dispose();
      prefetch.dispose();
      disposeDiff();
      currentFileListeners.clear();
    },
  });
}

/**
 * Wire a scroll keeper to the pane, its page, and the history entry. Browser only.
 *
 * @param {HTMLElement} pane
 * @param {HTMLElement} body
 * @param {() => string} tab
 * @param {number} number
 */
function keepPlace(pane, body, tab, number) {
  const tops = () => {
    const viewTop = pane.getBoundingClientRect().top;
    return Array.from(
      body.querySelectorAll(PLACE_BLOCKS),
      (block) => block.getBoundingClientRect().top - viewTop + pane.scrollTop,
    );
  };
  const keeper = createScrollKeeper({
    read: () => window.history.state?.[PLACE_KEY],
    write(place) {
      // History can move on before this page is told: the entry is written only while
      // it is still this page's.
      if (onPageRoute(window.location.pathname, number, tab())) {
        window.history.replaceState({ ...window.history.state, [PLACE_KEY]: place }, "");
      }
    },
    measure: () => placeAt(tops(), pane.scrollTop),
    apply(place) {
      const top = scrollTopOf(place, tops());
      if (top === null) {
        return false;
      }
      pane.scrollTop = top;
      return true;
    },
    anchored: () => window.location.hash !== "",
    toTop() {
      pane.scrollTop = 0;
    },
    schedule: (callback, delayMs) => window.setTimeout(callback, delayMs),
    cancel: (handle) => window.clearTimeout(/** @type {number} */ (handle)),
  });
  const listening = new AbortController();
  const { signal } = listening;
  pane.addEventListener("scroll", keeper.scrolled, { passive: true, signal });
  // Any click: a nav row's is outside the pane, and leaves this entry all the same. A key on a
  // Pulls row reaches this through the page host's `open`, and no key may flush here: holding
  // one in the pane would write a place per repeat, past Safari's limit on `replaceState`.
  document.addEventListener("click", keeper.flush, { capture: true, signal });
  // Whatever a reader moves the pane with: a wheel, a finger, a scrollbar, a key. Only input
  // says so, since the browser's own scroll anchoring also moves a page that changes height.
  // So a scroll with no input the page can see, from assistive technology or the find bar, is
  // undone by the next change in height inside the settle window: telling it from anchoring
  // would end the hold on what the hold exists to override.
  for (const type of ["wheel", "touchstart", "pointerdown"]) {
    pane.addEventListener(type, keeper.readerMoved, { capture: true, passive: true, signal });
  }
  window.addEventListener(
    "keydown",
    (event) => {
      const target = /** @type {HTMLElement | null} */ (event.target);
      if (keyMovesPane(event.key, target)) {
        keeper.readerMoved();
      }
    },
    { capture: true, signal },
  );
  const heights = new ResizeObserver(() => keeper.contentChanged());
  heights.observe(body);
  return {
    keeper,
    dispose() {
      listening.abort();
      heights.disconnect();
      keeper.dispose();
    },
  };
}
