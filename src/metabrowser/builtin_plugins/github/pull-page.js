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
// it is visible and stale, as a stale mirror does, each time it goes stale and at most once a
// freshness window, the first time only once a reader has stayed on it; the server holds each
// number to one attempt per window, and a rate limit or a lost network holds the page too.
// Content the page already shows stays as it is while it refreshes, with no spinner: only
// the age line breathes (`.mb-refreshing`, "Refreshing Content" in docs/design-system.md).
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
import { createStackIndex, memberRoute, stackMembership, watchStacks } from "./pull-stacks.js";
import { displayState, listedState, pullStateIcon, withListedState } from "./pull-state.js";

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
// How long a conversation's first paint waits, out of sight, for the Markdown of the texts
// its first screen shows, so each is final when it first shows; kept renders wait for
// nothing. Past this the texts show plain and their Markdown replaces them when it comes. A
// page replacing another keeps that one on screen meanwhile. Measured 2026-11-12 in headless
// Chrome 152 against a local server on this repository, from the hold's
// `githubPull:firstPaintHold` span, each pull request clicked from the previous
// conversation scrolled by 1,500 px, two documents of five, load average 4 to 7: 23 to 155
// ms (median 34, n 10), the 100 and 155 ms holds being a document's first pull request,
// which also loads `inert-html` and KPress's stylesheets; every one waited for one text,
// the description filling the first screen. None reached this bound. A first screen of
// several texts waits a round trip per `MARKDOWN_CONCURRENCY` texts: three texts at 40 ms
// an answer held 84 to 86 ms in a scratch page (review D), so a cold document's first page
// with several texts leaves less room than these figures. The exp-065 pilot also waited for
// a `cached_only` timeline read, which ran to the bound, so commits no longer hold the paint.
export const DESCRIPTION_HOLD_MS = 200;
// How many plain texts past a held first screen are asked for with it, not waited on: a
// render shorter than its plain text brings the texts below it up into the screen, and one
// already asked for is on its way when it does.
export const FIRST_SCREEN_AHEAD = 3;
// Rendered texts kept across pages, the newest first: a revisit, Back, or Forward, and a
// refreshed record whose text did not change, show the Markdown at once instead of asking
// again. Descriptions and the other parts are kept apart, so reading one long conversation
// does not push every other pull request's description out. Each bound counts entries and
// UTF-16 code units of HTML and source text together (2 bytes each), and an entry keeps
// only its HTML: the stylesheet manifest (1,420 characters of JSON) is the same for every
// text and is kept once. Measured 2026-11-12 on this repository's 75 cached records, through
// the Markdown route: a description rendered to 485 to 18,588 characters (median 2,691, p90
// 8,515), any other part to 51 to 45,679 (median 2,000, p90 13,973), and a pull request had
// 1 to 56 parts (median 5, p90 21). So the descriptions' bound holds 64 near p90 with their
// texts, and the others' about 230 at the mean, some 25 conversations: at most 3 million
// code units, 6 MB, in all.
export const RENDERED_DESCRIPTIONS = 64;
export const RENDERED_DESCRIPTION_CHARS = 1_000_000;
export const RENDERED_PARTS = 256;
export const RENDERED_PART_CHARS = 2_000_000;
// How long Changes keeps a comparison with rendered Markdown out of sight while its first
// screen's Markdown files wait for Rendered, so they first show at the height they keep and
// the files below them never move by themselves. It is the screen it lands on: a file the
// address names is landed before the wait. Measured 2026-11-12 in headless Chrome 152 in the
// same runs as DESCRIPTION_HOLD_MS, from the `githubPull:changesHold` span: 29 to 170 ms
// (median 39, p90 90, n 24), none at this bound; the two above 100 ms were one pull
// request's, in two of the three documents.
export const CHANGES_FIRST_SCREEN_MS = 200;
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
// How long a stale page reached by an address or a key is shown before it first asks for its
// refresh; a click asks at once, and a page left open asks again at once. A reader who walks
// past pages, holding Back or a key, spends no refresh on one they did not stop at: in Chrome
// (2026-11-02) ten pages opened 30 ms apart started eight refreshes when each asked at once,
// and each is eight gh processes and a fetch that take about 5 s. It is a choice, longer than
// a press of Back takes and short beside the refresh it delays. The wait shows nothing: the
// page is already painted refreshing.
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
// The repository's list of pull requests, whose scan says which records GitHub changed.
const CATALOG_REFRESH_ROUTE = "/api/plugin/github/pulls-refresh";
// How the server says, on a 200 and a 304 alike, when the record was last checked and how.
const VERIFIED_HEADER = "x-metabrowser-verified";
const MARKDOWN_ROUTE = "/api/plugin/github/pull-markdown";
const TIMELINE_ROUTE = "/api/plugin/github/pull-timeline";
// Give a transient queue or provider failure one chance to clear while the reader stays.
export const TIMELINE_RETRY_MS = 1000;
const PIN_ROUTE = "/api/source/pin";
export const TABS = Object.freeze(["", "files", "checks"]);
/**
 * Each tab's label and key, in `TABS` order. Every label starts with C, so Conversation, the
 * default, keeps it, and the others take a distinctive letter of their label: chan-*g*es, and
 * the next letter of Checks (docs/project/specs/active/plan-2026-11-11-shift-key-reveal-and-keymap.md,
 * "Key Allocation Rules"). `C` is also the Charts tab's, which is never shown beside a page.
 */
const PULL_TABS = Object.freeze([
  Object.freeze({ id: "", label: "Conversation", key: "c" }),
  Object.freeze({ id: "files", label: "Changes", key: "g" }),
  Object.freeze({ id: "checks", label: "Checks", key: "h" }),
]);

/** @type {Readonly<Record<string, string>>} */
const ABSENCE = Object.freeze({
  not_github: "This server serves no GitHub repository.",
  not_cached: "This pull request has not been fetched yet.",
  schema_mismatch: "The saved copy of this pull request is from another version.",
  unreadable: "The saved copy of this pull request could not be read.",
});

/** @type {Readonly<Record<string, string>>} */
const SETUP_FAILURES = Object.freeze({
  gh_missing:
    "Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, then run gh auth login --hostname github.com.",
  gh_too_old:
    "This GitHub CLI cannot report the active account. Update gh from https://cli.github.com/, then run gh auth status --hostname github.com.",
  not_logged_in:
    "GitHub CLI is not signed in to github.com. Run gh auth login --hostname github.com, then retry.",
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
  comparison: "Changes",
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
 *   source: string | null,
 *   number: number,
 *   pin: string | null,
 *   pin_ref: string | null,
 *   fetched_at: string | null,
 *   verified_at?: string | null,
 *   verified_by?: "catalog" | "fetch" | null,
 *   head_moved?: boolean,
 *   checks_pending?: boolean,
 *   fresh_for_s: number,
 *   record_revision: string | null,
 *   refreshing: boolean,
 *   preparing_comparison?: true,
 *   last_refresh: {outcome: string, message: string | null, reset_at: string | null, at: string} | null,
 *   comparison_route: string | null,
 *   snapshot_route: string | null,
 *   rendered_route?: string | null,
 *   record: Record<string, any> | null,
 *   core_preview: {source: string, number: number, reader: string, observed_at: string,
 *     revision: string, pull: Record<string, any>, comparison_state: "pending" | "no_store" | "not_started"} | null,
 * }} PullEnvelope
 */

/**
 * @typedef {{
 *   kind: "comment" | "review",
 *   id: string,
 *   part: string,
 *   author: string,
 *   avatar: string | null,
 *   at: string | null,
 *   text: string,
 *   truncated: boolean,
 *   review: {state: string, label: string} | null,
 * }} TimelineItem
 */

/**
 * @typedef {{kind: "commit", oid: string, subject: string, committed_at: string | null}} TimelineCommit
 * @typedef {{kind: "comment" | "review", id: string} | TimelineCommit} TimelineEvent
 * @typedef {{state: "complete" | "partial" | "unavailable", events: TimelineEvent[], retryable: boolean}} TimelineProjection
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
 *   avatar: string | null,
 *   at: string,
 *   text: string,
 *   truncated: boolean,
 *   hunk: HunkView | null,
 *   hunkTruncated: boolean,
 * }} ReviewCommentItem
 */

/**
 * Where a check's details open, decided once for its link text, its look and its icon.
 * `actions` is a GitHub Actions run, `github` any other page the shell marks as GitHub's,
 * and `external` the check's own site. `name` is the link's accessible name: its text,
 * then the check's.
 *
 * @typedef {{kind: "actions" | "github" | "external", href: string, label: string, name: string}} CheckAction
 */

/**
 * @typedef {{name: string, detail: string | null, tone: string, label: string, action: CheckAction | null}} CheckItem
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
 *   recordRevision: string | null,
 *   corePreview: boolean,
 *   contentReady: boolean,
 *   message: string | null,
 *   refreshing: boolean,
 *   revalidating: boolean,
 *   canRefresh: boolean,
 *   canRetryComparison: boolean,
 *   canFetchComparison: boolean,
 *   freshness: string | null,
 *   failure: string | null,
 *   failureHelp?: "install" | "update",
 *   pull: null | {
 *     title: string, number: number, state: import("./pull-state.js").PullState, stateLabel: string, author: string,
 *     avatar: string | null, actorAvatar: string | null, baseRef: string, headRef: string,
 *     actor: string | null, action: string,
 *     base: string, head: string, htmlUrl: string, created: string, updated: string,
 *     closed: string | null, closedLabel: string | null, labels: string[],
 *     merge: {state: string, label: string} | null, text: string, truncated: boolean,
 *   },
 *   timeline: TimelineItem[],
 *   reviewComments: ReviewCommentItem[],
 *   checks: {counts: Record<string, number>, items: CheckItem[]} | null,
 *   checkNotes: string[],
 *   notes: string[],
 *   comparison: {left: string, right: string, route?: string, snapshot_route?: string, rendered_route?: string, headMoved: boolean} | null,
 *   browse: BrowseCode | null,
 *   filesUnavailable: string,
 *   changesPending: boolean,
 *   headOffer: {ref: string, head: string, pin: string, text: string} | null,
 *   checkoutAtHead: string | null,
 *   newCommits: string | null,
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
    const id = text(comment.timeline_id) || String(comment.id);
    items.push({
      kind: "comment",
      id,
      part: `issue_comment/${id}`,
      author: who(comment.author),
      avatar: avatarUrl(comment.author_avatar_url),
      at: text(comment.created_at) || null,
      text: text(comment.body),
      truncated: comment.body_truncated === true,
      review: null,
    });
  }
  for (const review of list(record.reviews)) {
    const state = text(review.state);
    const id = text(review.timeline_id) || String(review.id);
    items.push({
      kind: "review",
      id,
      part: `review/${id}`,
      author: who(review.author),
      avatar: avatarUrl(review.author_avatar_url),
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
      (left.kind === right.kind
        ? left.id.length - right.id.length || left.id.localeCompare(right.id)
        : left.kind === "comment"
          ? -1
          : 1),
  );
}

/** @param {unknown} value @param {string} revision @returns {TimelineProjection | null} */
function readTimelineProjection(value, revision) {
  if (value === null || typeof value !== "object") {
    return null;
  }
  const answer = /** @type {Record<string, unknown>} */ (value);
  const state = answer.state;
  if (
    answer.record_revision !== revision ||
    (state !== "complete" && state !== "partial" && state !== "unavailable") ||
    !Array.isArray(answer.events)
  ) {
    return null;
  }
  /** @type {TimelineEvent[]} */
  const events = [];
  for (const event of answer.events) {
    if (
      event?.kind === "commit" &&
      typeof event.oid === "string" &&
      /^[a-f0-9]{40}$/.test(event.oid)
    ) {
      events.push({
        kind: "commit",
        oid: event.oid,
        subject: text(event.subject),
        committed_at: typeof event.committed_at === "string" ? event.committed_at : null,
      });
    } else if (
      (event?.kind === "comment" || event?.kind === "review") &&
      typeof event.id === "string" &&
      /^[1-9][0-9]*$/.test(event.id)
    ) {
      events.push({ kind: event.kind, id: event.id });
    }
  }
  return { state, events, retryable: state !== "complete" && answer.retryable === true };
}

/** The exact PR's GitHub commit page, built from the held record's source. @param {string} source @param {number} number @param {string} oid */
function timelineCommitHref(source, number, oid) {
  return /^https:\/\/github\.com\/[a-z0-9-]+\/[a-z0-9_.-]+$/i.test(source)
    ? `${source}/pull/${number}/commits/${oid}`
    : null;
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
      avatar: avatarUrl(comment.author_avatar_url),
      at: text(comment.created_at),
      text: text(comment.body),
      truncated: comment.body_truncated === true,
      hunk: text(comment.diff_hunk) === "" ? null : hunkView(text(comment.diff_hunk), comment),
      hunkTruncated: comment.diff_hunk_truncated === true,
    }));
}

const CHECK_ACTION_LABELS = {
  actions: "View action on GitHub",
  github: "View on GitHub",
  external: "View details",
};
// GitHub serves a run's job page under the repository's /actions/ path on github.com.
const ACTIONS_PATH = /^\/[^/]+\/[^/]+\/actions\//;
// The hosts whose links the shell marks with GitHub's icon: `githubHosts` and
// `githubDestination` in static/plugin-sdk-views.js, which also leave out an address with
// a port or credentials. A check is GitHub's by the same rule, so its look and its mark
// agree; the Checks session asserts that they do for each kind of address.
const GITHUB_HOSTS = new Set([
  "github.com",
  "www.github.com",
  "cli.github.com",
  "docs.github.com",
  "gist.github.com",
  "api.github.com",
]);
const ACTIONS_APP = "GitHub Actions";

/**
 * A check's action, or `null` when its address is not one a page may follow (absent, or
 * not http(s)), so that no link text names an action that does not exist.
 *
 * @param {string} name
 * @param {unknown} url
 * @param {string} base
 * @returns {CheckAction | null}
 */
function checkAction(name, url, base) {
  const href = safeLink(typeof url === "string" ? url : null, base);
  if (href === null) {
    return null;
  }
  const { hostname, pathname, port, username, password } = new URL(href);
  /** @type {CheckAction["kind"]} */
  const kind =
    !GITHUB_HOSTS.has(hostname) || port || username || password
      ? "external"
      : (hostname === "github.com" || hostname === "www.github.com") && ACTIONS_PATH.test(pathname)
        ? "actions"
        : "github";
  const label = CHECK_ACTION_LABELS[kind];
  return { kind, href, label, name: `${label}: ${name}` };
}

/** @param {Record<string, any>} record @param {string} base The pull request's page. */
function checks(record, base) {
  /** @type {CheckItem[]} */
  const items = [];
  for (const run of list(record.check_runs)) {
    const name = text(run.name);
    const action = checkAction(name, run.details_url, base);
    const app = typeof run.app === "string" ? run.app : null;
    items.push({
      name,
      // An Actions link already says where the run is; any other app is named.
      detail: app === ACTIONS_APP && action?.kind === "actions" ? null : app,
      ...checkRunResult(run),
      action,
    });
  }
  for (const status of list(record.status?.statuses)) {
    const name = text(status.context);
    items.push({
      name,
      detail: typeof status.description === "string" ? status.description : null,
      ...commitStatusResult(status),
      action: checkAction(name, status.target_url, base),
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

/** @param {Record<string, any>} record @param {boolean} forChecks */
function notes(record, forChecks) {
  /** @type {string[]} */
  const said = [];
  const truncated = record.truncated ?? {};
  const checkPart = (/** @type {string} */ name) =>
    name === "check_runs" || name === "status" || name === "statuses";
  const cut = Object.keys(TRUNCATED).filter(
    (name) => checkPart(name) === forChecks && truncated[name] === true,
  );
  if (cut.length > 0) {
    said.push(
      `Only some ${cut.map((name) => TRUNCATED[name]).join(", ")} are shown: the list was longer than what is kept.`,
    );
  }
  if (!forChecks && truncated.text === true) {
    said.push("Some text was cut to keep this pull request's data within its size limit.");
  }
  for (const [part, why] of Object.entries(record.unavailable ?? {})) {
    if (checkPart(part) !== forChecks || (part === "comparison" && why === "no_store")) {
      continue;
    }
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
    return "Changes are not shown: this checkout's history is too shallow to know what this pull request changed. Metabrowser does not guess. A refresh with the network available fetches more history.";
  }
  if (why === "no_store") {
    return "Changes could not be fetched.";
  }
  if (why === "comparison_timeout") {
    return "Changes are unavailable: checking this pull request's history took too long. Refresh to try again.";
  }
  if (why === "comparison_too_large") {
    return "Changes are unavailable: checking this pull request's history exceeded the comparison limit.";
  }
  if (why === "commits_unavailable") {
    return "Changes are unavailable: a commit of this pull request's history is not readable here. On a mirror borrowing from a checkout, the checkout no longer holds it.";
  }
  return "Changes are unavailable: the pull request's base could not be compared with its head.";
}

/** What Changes says for a record without a store before anything has failed. */
const CHANGES_NOT_FETCHED = "Changes have not been fetched.";

/**
 * Failures that another automatic attempt would only repeat: the store's acquisition
 * (`checkout.py`'s `_acquire_comparison`), and an origin or pull request that cannot be
 * read, which the comparison job's own metadata read would meet again.
 */
const HELD_COMPARISON_FAILURES = new Set([
  "lender_missing",
  "git_failed",
  "fetch_failed",
  "not_found_or_private",
]);

/**
 * Whether the recorded outcome holds Changes' automatic comparison attempt for the
 * reader's Retry changes: GitHub's rate limit before it lifts, which the job's metadata
 * read would meet, or one of `HELD_COMPARISON_FAILURES` recorded since the record was
 * written, which a new visit would only repeat. A request with `retry` bypasses the
 * server's own guards, so the page holds itself. Pure.
 *
 * @param {PullEnvelope | null} envelope
 * @param {number} nowMs
 */
export function comparisonHeld(envelope, nowMs) {
  const last = envelope?.last_refresh ?? null;
  if (last === null) {
    return false;
  }
  if (last.outcome === "rate_limited") {
    return last.reset_at !== null && Date.parse(last.reset_at) > nowMs;
  }
  // An unreadable stamp cannot show the record is newer, so the outcome still holds.
  return (
    HELD_COMPARISON_FAILURES.has(last.outcome) &&
    !(Date.parse(last.at) < Date.parse(envelope?.record?.fetched_at ?? ""))
  );
}

/**
 * Whether Changes will ask for the record's missing comparison by itself: the page is on
 * Changes at its own address, has not asked yet, and no recorded outcome holds the ask.
 * The controller asks only on this, once the page is visible, its read succeeded, nothing
 * else is in flight, and the address names Changes; `describePull` shows progress only on
 * it, so the page never spins for an attempt that will not run. A Pulls-tab file walk
 * that will settle on Changes owns it for display, since its address follows. Pure.
 *
 * @param {PullEnvelope | null} envelope
 * @param {{tab: string, nowMs: number, ownsChanges?: boolean, comparisonAttempted?: boolean}} page
 */
export function comparisonQueued(envelope, page) {
  return (
    page.tab === "files" &&
    page.ownsChanges !== false &&
    page.comparisonAttempted !== true &&
    envelope?.record?.unavailable?.comparison === "no_store" &&
    !comparisonHeld(envelope, page.nowMs)
  );
}

/** Header and description fields shared by a full record and a validated core preview.
 * @param {Record<string, any>} pull
 * @returns {NonNullable<PullModel["pull"]>}
 */
function describeCore(pull) {
  const crossRepository = pull.head?.repository !== pull.base?.repository;
  const state = displayState(pull);
  const merge = state === "open" || state === "draft" ? text(pull.mergeable) || "unknown" : null;
  const commits = typeof pull.commits === "number" ? pull.commits : null;
  const count = commits === null ? "" : ` ${commits} commit${commits === 1 ? "" : "s"}`;
  return {
    title: text(pull.title),
    number: pull.number,
    state,
    stateLabel: state[0].toUpperCase() + state.slice(1),
    author: who(pull.author),
    avatar: avatarUrl(pull.author_avatar_url),
    actorAvatar: avatarUrl(state === "merged" ? pull.merged_by_avatar_url : pull.author_avatar_url),
    baseRef: text(pull.base?.ref),
    headRef: text(pull.head?.ref),
    // "<merger> merged 6 commits: <head> → <base>", and for an open, draft, or closed
    // pull request "<author> wants to merge 1 commit: <head> → <base>". The verbs are
    // github.com's; the branches read source → target, never github.com's "into <base>
    // from <head>" (docs/design-system.md, "Merge Direction"). An account GitHub deleted
    // is its "ghost"; a record that names no merger at all says only "merged 6 commits",
    // rather than crediting anyone.
    actor:
      state !== "merged"
        ? who(pull.author)
        : typeof pull.merged_by === "string" && pull.merged_by
          ? pull.merged_by
          : null,
    action: `${state === "merged" ? "merged" : "wants to merge"}${count}`,
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
}

/**
 * When GitHub's rate limit stops holding this pull request's automatic refresh, in ms, or NaN
 * when none holds it: not before `reset_at`, and not within a freshness window of the
 * attempt the limit refused, which the server's guard and the page's own once-a-window ask
 * both wait out. `last_refresh.at` is when that attempt ended, never before the server
 * counted it from, so the time this names is never earlier than the next check. Pure.
 *
 * @param {PullEnvelope | null} envelope
 */
export function rateLimitLifts(envelope) {
  const last = envelope?.last_refresh ?? null;
  if (last === null || last.outcome !== "rate_limited") {
    return Number.NaN;
  }
  const lifts = [
    last.reset_at === null ? Number.NaN : Date.parse(last.reset_at),
    Date.parse(last.at) + (envelope?.fresh_for_s ?? 0) * 1000,
  ].filter(Number.isFinite);
  return lifts.length === 0 ? Number.NaN : Math.max(...lifts);
}

/**
 * What the page shows for one answer of the pull route. Pure.
 *
 * @param {PullEnvelope | null} envelope
 * *checkoutHead* is the served checkout's `HEAD`, on a folder, which has no pin.
 *
 * The controller says what it will send. *fetchQueued* is a selected fetch not asked
 * for yet that the page will send once it is visible or the reader stops; *ownsChanges*
 * is whether the address names Changes, which an automatic comparison needs (see
 * `comparisonQueued`); *comparisonRefusal* is why the page's last comparison request
 * was refused, kept until it asks again. *refreshDue* is the page's own automatic refresh of
 * a stale record, scheduled or on its way; *online* is false when the browser reports no
 * network, and *formatTime* writes the time a rate limit lifts.
 *
 * Content already shown is never covered by progress: while a refresh runs or is about to,
 * `revalidating` says so, and the page breathes the age line instead of a spinner. The age is
 * the plain age. A stale record says why only when no refresh can run: offline, held by
 * GitHub's rate limit, or a failure the reader can retry.
 *
 * *listed* is what the repository's list said of this pull request, whose state is shown
 * when the list saw a later update than the record or preview did.
 *
 * @param {{number: number, tab: string, nowMs: number, error?: string | null, fetching?: boolean, fetchQueued?: boolean, refreshPending?: boolean, refreshDue?: boolean, online?: boolean, formatTime?: (iso: string) => string, ownsChanges?: boolean, comparisonAttempted?: boolean, comparisonRefusal?: string | null, waitForReader?: boolean, checkoutHead?: string | null, listed?: {state: import("./pull-state.js").PullState, updatedAt: string} | null}} page
 * @returns {PullModel}
 */
export function describePull(envelope, page) {
  /** @type {PullModel} */
  const model = {
    number: page.number,
    tab: page.tab,
    status: "unavailable",
    recordRevision: null,
    corePreview: false,
    contentReady: Boolean(page.error),
    message: page.error ?? null,
    refreshing: false,
    revalidating: false,
    canRefresh: false,
    canRetryComparison: false,
    canFetchComparison: false,
    freshness: null,
    failure: null,
    pull: null,
    timeline: [],
    reviewComments: [],
    checks: null,
    checkNotes: [],
    notes: [],
    comparison: null,
    browse: null,
    filesUnavailable: filesUnavailableText(null),
    changesPending: false,
    headOffer: null,
    checkoutAtHead: null,
    newCommits: null,
  };
  if (envelope === null) {
    // Nothing read yet: the page shows a skeleton, and an error once a read failed.
    model.status = page.error ? "unavailable" : "loading";
    return model;
  }
  model.status = envelope.state;
  model.refreshing =
    (envelope.refreshing && (page.tab === "files" || !envelope.preparing_comparison)) ||
    page.refreshPending === true;
  model.revalidating = model.refreshing || page.refreshDue === true;
  const offline = page.online === false;
  const last = envelope.last_refresh;
  // What the last attempt said stays until a refresh actually runs, so an automatic ask that
  // the server answers at once does not blink it.
  // A rate limit holds the automatic refresh, which asks again by itself when it lifts.
  const heldUntil = rateLimitLifts(envelope);
  const held = heldUntil > page.nowMs;
  if (last?.outcome === "rate_limited" && !envelope.refreshing) {
    // Held, not failed: the time named is the one the page next asks at.
    model.failure = Number.isFinite(heldUntil)
      ? `GitHub rate limit · next check at ${(page.formatTime ?? String)(new Date(heldUntil).toISOString().replace(".000Z", "Z"))}`
      : "GitHub rate limit · next check within a minute";
  } else if (last !== null && last.outcome !== "succeeded" && !envelope.refreshing) {
    model.failure = `The last refresh failed: ${last.message ?? SETUP_FAILURES[last.outcome] ?? last.outcome.replaceAll("_", " ")}`;
    if (["gh_missing", "gh_too_old", "not_logged_in"].includes(last.outcome)) {
      model.failure += `${model.failure.endsWith(".") ? "" : "."} You can still browse local files and any cached pull requests.`;
      if (last.outcome === "gh_missing") {
        model.failureHelp = "install";
      } else if (last.outcome === "gh_too_old") {
        model.failureHelp = "update";
      }
    }
  }
  const record = envelope.record;
  if (record === null && envelope.core_preview !== null) {
    const preview = envelope.core_preview;
    model.pull = describeCore(withListedState(preview.pull, page.listed));
    model.corePreview = true;
    model.contentReady = true;
    model.message = page.error ?? null;
    const age = relativeAge(preview.observed_at, page.nowMs);
    model.freshness = `${offline && !model.refreshing ? "Offline · description" : "Description"} fetched ${age} via GitHub CLI`;
    model.canRefresh =
      envelope.state === "absent" &&
      envelope.reason !== "not_github" &&
      !envelope.refreshing &&
      !page.fetching;
    // Only the selected fetch on its way, or still to be sent, prepares the record. A refused
    // or failed one leaves nothing running, which the header's Refresh then starts.
    model.changesPending =
      model.refreshing ||
      (page.tab === "files" && (page.fetching === true || page.fetchQueued === true));
    model.filesUnavailable = model.changesPending
      ? "Changes are still being prepared."
      : "Changes are unavailable because the full pull request could not be loaded.";
    return model;
  }
  if (record === null) {
    const fetching = envelope.state === "pending" || page.fetching === true;
    if (fetching) {
      model.status = "pending";
    }
    model.message = fetching
      ? "Fetching the pull request…"
      : (page.error ?? ABSENCE[envelope.reason ?? ""] ?? ABSENCE.not_cached);
    // Nothing is shown to refresh: the skeleton or the message is all there is.
    model.revalidating = false;
    model.contentReady = Boolean(page.error) || (!fetching && !page.waitForReader);
    model.canRefresh =
      !fetching &&
      envelope.state === "absent" &&
      envelope.reason !== "not_github" &&
      !envelope.refreshing;
    return model;
  }
  model.recordRevision = envelope.record_revision;
  model.contentReady = true;
  model.message = page.error ?? null;
  // A stale record the page is refreshing by itself offers nothing to press: Refresh is for a
  // failure, Changes, or a stale record whose automatic refresh did not run. A rate limit's
  // hold offers none either: the page names when it asks again and asks then, as the Pulls
  // tab's Reload waits out the same hold, and a press would only meet the limit.
  model.canRefresh =
    !envelope.refreshing &&
    !model.revalidating &&
    !held &&
    (envelope.state !== "stale" || !offline) &&
    (envelope.state === "stale" ||
      model.failure !== null ||
      (page.tab === "files" &&
        typeof record.comparison?.base === "string" &&
        typeof record.comparison?.head === "string") ||
      (typeof record.unavailable?.comparison === "string" &&
        record.unavailable.comparison !== "no_store"));
  const age = relativeAge(record.fetched_at ?? null, page.nowMs);
  // The plain age while a refresh runs or is due: the page breathes it, and says nothing
  // about being out of date. Offline is the one stale state named here, since no refresh
  // can run; a hold or a failure is named by `failure`.
  // "Checked" is the repository's list of pull requests saying, since the record was read,
  // that GitHub has not changed it; "Fetched" is the record itself. Each says its own age.
  const checked =
    envelope.verified_by === "catalog" &&
    typeof envelope.verified_at === "string" &&
    envelope.verified_at > (record.fetched_at ?? "")
      ? relativeAge(envelope.verified_at, page.nowMs)
      : null;
  const fetched = checked === null ? `Fetched ${age}` : `Checked ${checked} · fetched ${age}`;
  model.freshness =
    offline && envelope.state === "stale" && !model.revalidating
      ? `Offline · fetched ${age} via GitHub CLI`
      : `${fetched} via GitHub CLI`;
  if (envelope.head_moved === true) {
    // The diff on screen stays until the reader takes the newer one, which a refresh offers.
    model.newCommits = model.revalidating
      ? "New commits were pushed; updating."
      : "New commits were pushed to this pull request.";
  }
  const pull = record.pull ?? {};
  model.pull = describeCore(withListedState(pull, page.listed));
  model.timeline = timeline(record);
  model.reviewComments = reviewComments(record);
  model.checks = checks(record, model.pull.htmlUrl);
  model.checkNotes = notes(record, true);
  model.notes = notes(record, false);
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
  if (envelope.pin === null && head !== "" && page.checkoutHead === head) {
    // A checkout has no pin, so no Browse code: its working tree is not the pull request's
    // code. When its HEAD is this pull request's head, that much is so, and the page says it.
    model.checkoutAtHead = "This checkout's HEAD is this pull request's head.";
  }
  model.filesUnavailable = filesUnavailableText(record.unavailable?.comparison ?? null);
  if (record.unavailable?.comparison === "no_store" && page.tab === "files") {
    // Progress only for an attempt running or still to be sent, Retry changes only once one
    // failed or a recorded outcome holds it, and Fetch changes only when nothing will ask.
    // A failed read before any attempt waits for the next good one, which then asks.
    const queued = comparisonQueued(envelope, page);
    const failed = page.comparisonAttempted === true || comparisonHeld(envelope, page.nowMs);
    model.changesPending = model.refreshing || (queued && !page.error);
    model.canRetryComparison = !model.changesPending && failed;
    model.canFetchComparison = !model.changesPending && !failed && !queued;
    model.canRefresh = false;
    if (model.changesPending) {
      model.filesUnavailable = "Fetching changes…";
    } else if (!failed) {
      model.filesUnavailable = CHANGES_NOT_FETCHED;
    } else {
      // A later read clears the refusal's error; its reason stays until the page asks again.
      model.message = page.error ?? page.comparisonRefusal ?? null;
    }
  }
  const comparison = record.comparison;
  if (comparison && typeof comparison.base === "string" && typeof comparison.head === "string") {
    model.comparison = {
      left: comparison.base,
      right: comparison.head,
      ...(typeof envelope.comparison_route === "string"
        ? { route: envelope.comparison_route }
        : {}),
      // Where View file opens a file of either end without changing the served pin.
      ...(typeof envelope.snapshot_route === "string"
        ? { snapshot_route: envelope.snapshot_route }
        : {}),
      // Where Changes asks for one Markdown file's rendered redline.
      ...(typeof envelope.rendered_route === "string"
        ? { rendered_route: envelope.rendered_route }
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

/** @param {unknown} value @param {Record<string, unknown>} envelope */
function isCorePreview(value, envelope) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const preview = /** @type {Record<string, any>} */ (value);
  return (
    preview.source === envelope.source &&
    preview.number === envelope.number &&
    typeof preview.reader === "string" &&
    preview.reader.startsWith("gh:") &&
    typeof preview.observed_at === "string" &&
    typeof preview.revision === "string" &&
    /^[a-f0-9]{64}$/.test(preview.revision) &&
    preview.pull !== null &&
    typeof preview.pull === "object" &&
    preview.pull.number === envelope.number &&
    (preview.comparison_state === "pending" ||
      preview.comparison_state === "no_store" ||
      preview.comparison_state === "not_started")
  );
}

/**
 * @param {unknown} value
 * @returns {value is PullEnvelope}
 */
export function isEnvelope(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const envelope = /** @type {Record<string, unknown>} */ (value);
  return (
    typeof envelope.state === "string" &&
    typeof envelope.refreshing === "boolean" &&
    Number.isInteger(envelope.number) &&
    Number(envelope.number) > 0 &&
    (envelope.record === null || typeof envelope.record === "object") &&
    (envelope.core_preview === null || isCorePreview(envelope.core_preview, envelope)) &&
    (envelope.record === null
      ? envelope.record_revision === null
      : typeof envelope.record_revision === "string" &&
        /^[a-f0-9]{64}$/.test(envelope.record_revision))
  );
}

// ── Rendered texts, across pages ──────────────────────────────

/**
 * Rendered Markdown by what it renders. The server renders a text from the pull request's
 * number, the part, and the text alone (`pull_markdown.render_part`), so an entry serves any
 * record or core preview of that source with the same text, and never another text: the
 * entry holds the text it was rendered from, and a lookup compares it. Two pools, for
 * descriptions and for every other part, each with its own bounds.
 *
 * @typedef {{entries: Map<string, {text: string, html: string, size: number}>, chars: number,
 *   maxEntries: number, maxChars: number}} RenderedPool
 */
/** @type {RenderedPool} */
const renderedDescriptions = {
  entries: new Map(),
  chars: 0,
  maxEntries: RENDERED_DESCRIPTIONS,
  maxChars: RENDERED_DESCRIPTION_CHARS,
};
/** @type {RenderedPool} */
const renderedParts = {
  entries: new Map(),
  chars: 0,
  maxEntries: RENDERED_PARTS,
  maxChars: RENDERED_PART_CHARS,
};
/** The stylesheet manifest the last render named, the same for every text. @type {unknown} */
let renderedAssets = null;
/** @param {string} part */
const poolFor = (part) => (part === "body" ? renderedDescriptions : renderedParts);
// KPress's stylesheets for texts have loaded, or failed to, on some page of this document:
// they are the same for every text, so a later page inserts a kept render at once.
let kpressStylesSettled = false;

/**
 * @param {string} source
 * @param {number} number
 * @param {string} part
 * @param {string} text
 */
function renderedKey(source, number, part, text) {
  // FNV-1a, to spread texts over the map; equality is the stored text's.
  let hash = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    hash = Math.imul(hash ^ text.charCodeAt(index), 0x01000193);
  }
  return `${source}\n${number}\n${part}\n${text.length}:${(hash >>> 0).toString(16)}`;
}

/**
 * Keep a text's render for later pages, dropping the oldest past the bounds.
 *
 * @param {string | null} source
 * @param {number} number
 * @param {string} part
 * @param {string} text
 * @param {Record<string, any>} rendered
 */
export function rememberRendered(source, number, part, text, rendered) {
  if (source === null || typeof rendered.html !== "string") {
    return;
  }
  if (rendered.assets !== undefined) {
    renderedAssets = rendered.assets;
  }
  const pool = poolFor(part);
  const key = renderedKey(source, number, part, text);
  const previous = pool.entries.get(key);
  if (previous !== undefined) {
    pool.entries.delete(key);
    pool.chars -= previous.size;
  }
  const size = rendered.html.length + text.length;
  if (size > pool.maxChars) {
    return;
  }
  pool.entries.set(key, { text, html: rendered.html, size });
  pool.chars += size;
  for (const [oldest, entry] of pool.entries) {
    if (pool.entries.size <= pool.maxEntries && pool.chars <= pool.maxChars) {
      break;
    }
    pool.entries.delete(oldest);
    pool.chars -= entry.size;
  }
}

/**
 * The render kept for exactly this text, or null.
 *
 * @param {string | null} source
 * @param {number} number
 * @param {string} part
 * @param {string} text
 * @returns {Record<string, any> | null}
 */
export function renderedText(source, number, part, text) {
  if (source === null) {
    return null;
  }
  const pool = poolFor(part);
  const key = renderedKey(source, number, part, text);
  const entry = pool.entries.get(key);
  if (entry === undefined || entry.text !== text) {
    return null;
  }
  pool.entries.delete(key);
  pool.entries.set(key, entry);
  return { html: entry.html, assets: renderedAssets };
}

/**
 * The text a part names in *record*, as the server's `part_text` reads it, or null. A
 * comment's or review's part is named as `timeline` names it.
 *
 * @param {Record<string, any> | null} record
 * @param {string} part
 * @returns {string | null}
 */
export function partText(record, part) {
  if (record === null) {
    return null;
  }
  if (part === "body") {
    return text(record.pull?.body);
  }
  const [kind, ident] = part.split("/");
  const items =
    kind === "issue_comment"
      ? record.issue_comments
      : kind === "review"
        ? record.reviews
        : kind === "review_comment"
          ? record.review_comments
          : null;
  const item = list(items).find(
    (entry) =>
      (kind === "review_comment"
        ? String(entry.id)
        : text(entry.timeline_id) || String(entry.id)) === ident,
  );
  return item === undefined ? null : text(item.body);
}

/** How much the kept renders hold, for tests of the bounds. */
export function renderedTextsHeld() {
  return {
    descriptions: { texts: renderedDescriptions.entries.size, chars: renderedDescriptions.chars },
    parts: { texts: renderedParts.entries.size, chars: renderedParts.chars },
  };
}

/**
 * @typedef {{status: number, etag: string | null, body: unknown, verified?: string | null}} PullResponse
 * @typedef {{
 *   request(method: "GET" | "POST", route: string, options: {etag?: string | null, body?: unknown}): Promise<PullResponse>,
 *   schedule(callback: () => void, delayMs: number): unknown,
 *   cancel(handle: unknown): void,
 *   now(): number,
 *   isVisible(): boolean,
 *   isOnline?(): boolean,
 *   formatTime?(iso: string): string,
 *   ownsChanges?(): boolean,
 *   ownsConversation?(): boolean,
 *   scheduleComparison?(callback: () => void): () => void,
 *   render(model: PullModel, identity: import("./pull-stacks.js").StackIdentity | null): void,
 *   renderMarkdown(part: string, rendered: Record<string, any>, text: string): void,
 *   textUnavailable?(part: string, text: string): void,
 *   listed?(source: string | null, number: number): {state: import("./pull-state.js").PullState, updatedAt: string} | null,
 *   timelineStateChanged?(): void,
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
 *     initial: {etag: string | null, body: unknown, verified?: string | null, at?: number} | null,
 *     pending?: Promise<{etag: string | null, body: unknown, verified?: string | null, at?: number} | null> | null,
 *     abandon?: () => void,
 *     walking?: () => boolean,
 *   } | null,
 *   checkoutHead?: string | null,
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
  /** When `timer` fires, by `deps.now()`. */
  let timerDue = 0;
  let polling = false;
  let hasPolled = false;
  let inFlightRefreshes = 0;
  let disposed = false;
  // When this page last sent a refresh of its own for a stale record, by `deps.now()`. It asks
  // again once a freshness window has passed while the record is still or again stale, so a
  // page left open keeps refreshing, and a stale page whose refresh cannot run does not ask
  // on every poll; the server holds each number to one attempt a window as well.
  /** @type {number | null} */
  let autoAskedAt = null;
  /** That ask: none, scheduled (waiting in `askTimer`), or sent and not yet answered. */
  /** @type {"none" | "scheduled" | "sent"} */
  let autoAsk = "none";
  // Once the repository's list of pull requests has vouched for this record, the page keeps
  // that list scanned while it is visible, so the record stays current without being read
  // again: when the check lapses it asks for the next scan, once a window, before it reads.
  let catalogBacked = false;
  /** When the page last asked for the catalog's scan, by `deps.now()`. @type {number | null} */
  let catalogAskedAt = null;
  // The last answer said the catalog vouched while its next scan ran: the page reads again
  // in a fast poll, so a change that scan publishes is refreshed then, not a slow poll later.
  let catalogScanning = false;
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
  let refreshPending = false;
  // A refused automatic comparison stays a retry, even when later GETs clear the error.
  let comparisonAttempted = false;
  /** @type {string | null} */
  let idleAttemptedRevision = null;
  /** @type {(() => void) | null} */
  let cancelComparison = null;
  /** Why the last comparison request was refused, until the page asks again. @type {string | null} */
  let comparisonRefusal = null;
  // A Pulls-tab walk showed Changes and will move the address there once it stops.
  let walkSettling = false;
  // Only this page's acknowledged selected refresh can opt in to a settlement read.
  let waitForFull = false;
  /** Markdown by part, for the record content revision `markdownFor`, with the text it renders. @type {Map<string, {rendered: Record<string, any>, text: string}>} */
  const markdown = new Map();
  /** @type {string | null} */
  let markdownFor = null;
  /** @type {string[]} */
  const queue = [];
  /**
   * The parts asked for, with the text and the record revision each was asked for: an answer
   * rendered from another revision is not the render of that text.
   *
   * @type {Map<string, {text: string | null, revision: string | null}>}
   */
  const asked = new Map();
  let inFlight = 0;

  /** A direct link's cold miss, which the page asks to fill once it is visible. */
  function coldMiss() {
    return (
      reader === null &&
      error === null &&
      envelope?.state === "absent" &&
      envelope.reason === "not_cached" &&
      envelope.last_refresh === null &&
      !envelope.refreshing
    );
  }

  function directColdMiss() {
    return deps.isVisible() && coldMiss();
  }

  /** The selected fetch `fetchForReader` has still to ask for, once the page can. */
  function fetchQueued() {
    if (readerAsked || envelope === null) {
      return false;
    }
    return reader === null
      ? coldMiss()
      : envelope.state === "absent" && envelope.reason !== "not_github" && !envelope.refreshing;
  }

  /** Whether the address names Changes, which the automatic comparison waits for. */
  function ownsChanges() {
    return deps.ownsChanges?.() !== false;
  }

  /** Whether the browser reports a network; offline, nothing is asked by itself. */
  function online() {
    return deps.isOnline?.() !== false;
  }

  /** GitHub's rate limit holds automatic refreshes until `rateLimitLifts`. */
  function rateLimitHolds() {
    return rateLimitLifts(envelope) > deps.now();
  }

  /**
   * Whether the page asks for its stale record's refresh now: visible, online, nothing on its
   * way or running, not held, and not asked within a freshness window. A failure the reader
   * must fix (no gh, an old gh, signed out) waits for the reader's Refresh after the first ask.
   */
  function staleRefreshDue() {
    if (
      disposed ||
      !deps.isVisible() ||
      !online() ||
      envelope?.state !== "stale" ||
      envelope.refreshing ||
      fetching ||
      autoAsk !== "none" ||
      askTimer !== null ||
      rateLimitHolds() ||
      (envelope.record?.unavailable?.comparison === "no_store" &&
        (tab === "files" ||
          (tab === "" && deps.ownsConversation?.() === true && hasFreshComparisonMetadata())))
    ) {
      return false;
    }
    if (autoAskedAt === null) {
      return true;
    }
    const outcome = envelope.last_refresh?.outcome ?? "";
    return (
      !["gh_missing", "gh_too_old", "not_logged_in"].includes(outcome) &&
      deps.now() - autoAskedAt >= envelope.fresh_for_s * 1000
    );
  }

  /**
   * Ask for the stale record's refresh when it is due. The first ask of a page waits for the
   * reader to stay on it, as long as the Pulls tab's opening said (none for a click) or
   * `REFRESH_ASK_MS` for an address, which holding Back walks through; a later one, on a
   * page left open, asks at once. Any of them waits while a key that opened the page is held.
   */
  function askIfStale() {
    if (!staleRefreshDue()) {
      return;
    }
    const delayMs = autoAskedAt !== null ? 0 : (reader?.fetchAfterMs ?? REFRESH_ASK_MS);
    autoAsk = "scheduled";
    askAfter(async () => {
      autoAsk = "sent";
      autoAskedAt = deps.now();
      try {
        await askForRefresh({ number: options.number });
      } finally {
        autoAsk = "none";
      }
      if (!disposed) {
        render();
      }
    }, delayMs);
  }

  /**
   * Whether the page asks for the catalog's next scan before it reads: the catalog vouched
   * for this record before, its check is a window old, and none was asked within a window.
   * The server starts it only once a window, and a record it is scanning for stays current.
   */
  function catalogScanDue() {
    if (disposed || !catalogBacked || envelope === null || !deps.isVisible() || !online()) {
      return false;
    }
    const windowMs = envelope.fresh_for_s * 1000;
    const checked = Date.parse(envelope.verified_at ?? "");
    return (
      Number.isFinite(checked) &&
      deps.now() - checked >= windowMs &&
      (catalogAskedAt === null || deps.now() - catalogAskedAt >= windowMs)
    );
  }

  /**
   * Take the verdict a 304 carried in its header, `<verified_by> <verified_at>`: the
   * catalog's scans move it once a window and nothing else the page shows.
   *
   * @param {string | null | undefined} value
   */
  function adoptVerified(value) {
    const found = /^(catalog|fetch) (\S+)(?: scanning)?$/u.exec(value ?? "");
    if (envelope === null || envelope.record === null || found === null) {
      return;
    }
    const by = /** @type {"catalog" | "fetch"} */ (found[1]);
    envelope = { ...envelope, verified_by: by, verified_at: found[2] };
    catalogBacked = catalogBacked || by === "catalog";
  }

  /** What `describePull` and `comparisonQueued` read of this page. */
  function pageState() {
    return {
      number: options.number,
      tab,
      nowMs: deps.now(),
      error,
      fetching: fetching || refreshPending,
      fetchQueued: fetchQueued(),
      refreshPending,
      refreshDue: autoAsk !== "none",
      online: online(),
      ...(deps.formatTime === undefined ? {} : { formatTime: deps.formatTime }),
      ownsChanges: walkSettling || ownsChanges(),
      comparisonAttempted,
      comparisonRefusal,
      waitForReader: reader !== null && !readerAsked && envelope?.reason !== "not_github",
      checkoutHead: options.checkoutHead ?? null,
      listed: deps.listed?.(envelope?.source ?? null, options.number) ?? null,
    };
  }

  function model() {
    const next = describePull(envelope, pageState());
    if (inFlightRefreshes > 0) {
      // A click waits for no refresh, so no button is shown until this one answers.
      next.canRetryComparison = false;
      next.canFetchComparison = false;
    }
    if (refreshPending) {
      // The selected refresh has not acknowledged a core yet. Its POST being in flight
      // must not turn the still-absent envelope into a ready replacement surface.
      if (!next.pull) {
        next.contentReady = false;
      }
      next.canRefresh = false;
      next.canRetryComparison = false;
      next.canFetchComparison = false;
    }
    return next;
  }

  function render() {
    const next = model();
    const owner = envelope?.record ?? envelope?.core_preview;
    const identity = owner
      ? {
          source: typeof owner.source === "string" ? owner.source : null,
          reader: typeof owner.reader === "string" ? owner.reader : null,
        }
      : null;
    const key = JSON.stringify([next, identity]);
    if (key !== painted) {
      painted = key;
      deps.render(next, identity);
    }
  }

  function cancelIdleComparison() {
    cancelComparison?.();
    cancelComparison = null;
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
      if (autoAsk === "scheduled") {
        // Not sent, so not asked: the page asks again when it is due, or is shown again.
        autoAsk = "none";
      }
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

  function scheduleNext(fastDelay = FAST_POLL_MS) {
    clearTimer();
    if (disposed || !deps.isVisible()) {
      return;
    }
    const delay = pollsFast() ? fastDelay : SLOW_POLL_MS;
    const lifts = untilHoldLifts();
    const next = lifts === null ? delay : Math.min(delay, lifts);
    timerDue = deps.now() + next;
    timer = deps.schedule(() => {
      timer = null;
      void poll();
    }, next);
  }

  function pollsFast() {
    // Optional comparison work says nothing to Conversation, so it is polled slowly there.
    const quiet = envelope?.preparing_comparison === true && tab !== "files";
    return (
      envelope === null ||
      (envelope.refreshing && !quiet) ||
      envelope.state === "pending" ||
      catalogScanning
    );
  }

  /**
   * How long until a rate limit stops holding this page's automatic comparison or its stale
   * record's refresh, or null when none holds either. The page reads again then, so it asks
   * without waiting for a slow poll and does not keep a hold or a Retry changes painted past it.
   */
  function untilHoldLifts() {
    const last = envelope?.last_refresh;
    const resetMs = last?.outcome === "rate_limited" ? Date.parse(last.reset_at ?? "") : Number.NaN;
    const nowMs = deps.now();
    /** @type {number[]} */
    const waits = [];
    if (
      resetMs > nowMs &&
      comparisonQueued(envelope, { ...pageState(), ownsChanges: ownsChanges(), nowMs: resetMs })
    ) {
      waits.push(resetMs - nowMs);
    }
    // The stale record's refresh is asked for when its hold lifts, the time the page names.
    const recordLifts = rateLimitLifts(envelope);
    if (envelope?.state === "stale" && recordLifts > nowMs) {
      waits.push(recordLifts - nowMs);
    }
    return waits.length === 0 ? null : Math.min(...waits);
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
    if (next.number !== options.number || request < shownRequest) {
      return false;
    }
    shownRequest = request;
    envelope = next;
    catalogBacked = catalogBacked || next.verified_by === "catalog";
    if (next.record !== null || !next.refreshing) {
      waitForFull = false;
    }
    const revision = next.record === null ? null : next.record_revision;
    if (revision !== markdownFor) {
      cancelIdleComparison();
      // Another record: its texts may differ, so nothing rendered from the last one
      // is shown again. The page asks again for the parts a reader sees.
      markdownFor = revision;
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
    // Until the explicit POST is acknowledged, a newer GET could still see the pre-job
    // record. Keep it from outranking the job's acknowledgement in latest-wins metadata.
    if (disposed || polling || refreshPending || (!first && !deps.isVisible())) {
      return;
    }
    polling = true;
    if (!first && catalogScanDue()) {
      // Asked first, so the read below already sees the scan running and the record current.
      catalogAskedAt = deps.now();
      try {
        await deps.request("POST", CATALOG_REFRESH_ROUTE, { body: { background: true } });
      } catch {
        // The read below still answers; the next window asks again.
      }
      if (disposed) {
        polling = false;
        return;
      }
    }
    const request = ++sent;
    const coreRevision =
      !first && waitForFull && envelope?.refreshing && envelope.record === null
        ? envelope.core_preview?.revision
        : undefined;
    const route =
      coreRevision === undefined ? pullRoute : `${pullRoute}&wait_full_after=${coreRevision}`;
    const waitStarted = coreRevision === undefined ? null : deps.now();
    try {
      const response = await deps.request("GET", route, { etag });
      if (disposed) {
        return;
      }
      take(response, request);
    } catch {
      catalogScanning = false;
      error = "The server did not answer.";
    } finally {
      polling = false;
      hasPolled = true;
    }
    if (disposed) {
      return;
    }
    // A waiting read spent part (or all) of the interval already.
    afterRead(
      waitStarted === null
        ? FAST_POLL_MS
        : Math.max(0, FAST_POLL_MS - Math.max(0, deps.now() - waitStarted)),
    );
  }

  /**
   * One answer of the pull route, as a poll takes it.
   *
   * @param {PullResponse} response
   * @param {number} request
   */
  function take(response, request) {
    catalogScanning = false;
    if (response.status === 200 && isEnvelope(response.body)) {
      if (accept(response.body, request)) {
        etag = response.etag;
        catalogScanning = / scanning$/u.test(response.verified ?? "");
      }
      error = null;
    } else if (response.status === 304 || pinChanged(response)) {
      if (response.status === 304) {
        adoptVerified(response.verified);
        catalogScanning = / scanning$/u.test(response.verified ?? "");
      }
      error = null;
    } else {
      error = `The pull request is unavailable (HTTP ${response.status}).`;
    }
  }

  /** The page is waiting on the Pulls tab's read, which it would end if it went. */
  let joining = false;

  /**
   * The page's first read is the Pulls tab's, when the selection that opened it read the
   * record: one still on its way is joined, and one that answered within a fast poll is as
   * current as a read of the page's own would be, so a click reads the record once. Anything
   * else, a direct link or an answer read ahead long ago, is read again.
   *
   * @returns {Promise<void>}
   */
  async function firstRead() {
    const answered = reader?.initial ?? null;
    if (reader?.pending) {
      polling = true;
      joining = true;
      const request = ++sent;
      /** @type {{etag: string | null, body: unknown, verified?: string | null, at?: number} | null} */
      let joined = null;
      try {
        joined = await reader.pending;
      } catch {
        joined = null;
      } finally {
        polling = false;
        joining = false;
      }
      if (disposed) {
        return;
      }
      if (joined === null || !isEnvelope(joined.body) || joined.body.number !== options.number) {
        return poll(true);
      }
      take(
        { status: 200, etag: joined.etag, body: joined.body, verified: joined.verified },
        request,
      );
      // An answer that landed longer than a fast poll before the page started is not its first
      // read: it is read again, with its tag, as an older adopted answer is.
      const joinedAge = deps.now() - Number(joined.at ?? deps.now());
      if (!(joinedAge < FAST_POLL_MS)) {
        return poll(true);
      }
      hasPolled = true;
      afterRead(FAST_POLL_MS - Math.max(0, joinedAge));
      return;
    }
    const age = answered === null ? Number.NaN : deps.now() - Number(answered.at);
    if (envelope !== null && shownRequest === 0 && age >= 0 && age < FAST_POLL_MS) {
      hasPolled = true;
      afterRead(FAST_POLL_MS - age);
      return;
    }
    return poll(true);
  }

  /**
   * What follows any read the page counts as its own: its next poll in *fastMs* or the slow
   * interval, the asks that read may make due, and the paint.
   *
   * @param {number} fastMs
   */
  function afterRead(fastMs) {
    scheduleNext(fastMs);
    fetchForReader();
    fetchSelectedChanges();
    // Decided before the paint, so a record that just went stale is painted refreshing and
    // never offers a Refresh it is about to make.
    askIfStale();
    render();
    deps.timelineStateChanged?.();
    fetchIdleChanges();
  }

  /**
   * The selected PR can fill its cache once. A direct link waits for a visible cold miss,
   * and a row reached by keyboard waits for the reader to stop there.
   */
  function fetchForReader() {
    if (readerAsked || envelope === null || (reader === null && !directColdMiss())) {
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
      if (reader === null && !directColdMiss()) {
        readerAsked = false;
        render();
        return;
      }
      void askForRefresh({ number: options.number, retry: true, wait_core: true });
    }, reader?.fetchAfterMs ?? 0);
  }

  /**
   * Ask the server for a refresh and take the envelope it answers with. A refusal of the
   * page's own request says nothing to the reader, whose page still shows what it did and
   * still offers Refresh.
   *
   * @param {{number: number, retry?: boolean, wait_core?: boolean, comparison?: boolean, prepare_comparison?: string, recovery?: {base: string, head: string}}} ask
   */
  async function askForRefresh(ask) {
    const idle = ask.prepare_comparison !== undefined;
    if (!idle) {
      inFlightRefreshes += 1;
    }
    if (ask.retry) {
      refreshPending = true;
    }
    if (!idle) {
      // While it is on its way, Changes paints no button whose click would wait for it.
      render();
      cancelAsk();
    }
    const request = ++sent;
    // A bounded core wait must not shift the first ordinary poll by its response time.
    const fastSince = ask.wait_core === true ? deps.now() : null;
    try {
      const response = await deps.request("POST", REFRESH_ROUTE, { body: ask });
      const body = /** @type {{pull?: unknown, error?: unknown} | null} */ (response.body);
      if (
        (response.status === 202 || response.status === 200) &&
        body !== null &&
        isEnvelope(body.pull)
      ) {
        if (accept(body.pull, request)) {
          waitForFull =
            response.status === 202 &&
            ask.wait_core === true &&
            body.pull.record === null &&
            body.pull.refreshing;
        }
        if (response.status === 202) {
          // The answer changed; the next poll must not be answered by a 304.
          etag = null;
        }
        if (!idle) {
          error = null;
        }
      } else if (ask.retry) {
        const said = body !== null && typeof body.error === "string" ? body.error : null;
        error = `The refresh was refused (${said ?? `HTTP ${response.status}`}).`;
        if (ask.comparison) {
          comparisonRefusal = error;
        }
      }
    } catch {
      if (ask.retry) {
        error = "The refresh request failed.";
        if (ask.comparison) {
          comparisonRefusal = error;
        }
      }
    }
    if (!idle) {
      inFlightRefreshes -= 1;
    }
    if (ask.retry) {
      refreshPending = false;
    }
    if (!disposed) {
      fetchSelectedChanges();
      render();
      scheduleNext(
        fastSince === null
          ? FAST_POLL_MS
          : FAST_POLL_MS - (Math.max(0, deps.now() - fastSince) % FAST_POLL_MS),
      );
      deps.timelineStateChanged?.();
      fetchIdleChanges();
    }
  }

  /**
   * A reader's own press of Refresh. Files names the comparison still displayed,
   * which can be older than the latest metadata the page has polled.
   * @param {{base: string, head: string} | undefined} [recovery]
   */
  async function requestRefresh(recovery) {
    if (!disposed && model().canRefresh) {
      await askForRefresh({
        number: options.number,
        retry: true,
        ...(recovery === undefined
          ? envelope?.record === null
            ? { wait_core: true }
            : {}
          : { recovery }),
      });
    }
  }

  function fetchComparison() {
    comparisonAttempted = true;
    comparisonRefusal = null;
    return askForRefresh({ number: options.number, retry: true, comparison: true });
  }

  /**
   * Open Changes as soon as the selected pull's record can name the comparison. What it
   * waits for besides `comparisonQueued`, which also decides what the page shows, is only
   * timing: a visible page, a read that succeeded, and nothing else in flight.
   */
  function fetchSelectedChanges() {
    if (
      !disposed &&
      deps.isVisible() &&
      hasPolled &&
      !polling &&
      !fetching &&
      inFlightRefreshes === 0 &&
      comparisonDue()
    ) {
      void fetchComparison();
    }
  }

  /**
   * The automatic comparison, due once its read succeeded and the address names Changes.
   * A running idle preparation is promoted by the same request.
   */
  function comparisonDue() {
    return (
      error === null &&
      envelope !== null &&
      (envelope.preparing_comparison === true || !envelope.refreshing) &&
      comparisonQueued(envelope, { ...pageState(), ownsChanges: ownsChanges() })
    );
  }

  function hasFreshComparisonMetadata() {
    return (
      envelope?.fetched_at != null &&
      deps.now() - Date.parse(envelope.fetched_at) <= envelope.fresh_for_s * 1000
    );
  }

  /**
   * The record revision whose comparison this page may ask for as idle work, or null. Only
   * a server with an attached store prepares one, and there a fresh record written without
   * a store is `stale` (see `pull_state`), so a checkout with no store is never asked.
   * Measured 2026-11-11 with a logging Git and a local origin: asking a checkout with no
   * store acquired one, 21 Git calls fetching every branch the checkout lacked, after which
   * each Conversation refresh ran 18 to 22 Git calls with one or two origin fetches. With a
   * store attached, the job fetches only the pull request's head and base commit.
   */
  function idleCandidate() {
    if (
      disposed ||
      tab !== "" ||
      !deps.isVisible() ||
      deps.ownsConversation?.() !== true ||
      !hasPolled ||
      polling ||
      fetching ||
      askTimer !== null ||
      inFlightRefreshes > 0 ||
      error !== null ||
      envelope === null ||
      envelope.refreshing ||
      envelope.state !== "stale" ||
      envelope.record?.unavailable?.comparison !== "no_store" ||
      envelope.record_revision === idleAttemptedRevision ||
      !hasFreshComparisonMetadata()
    ) {
      return null;
    }
    return envelope.record_revision;
  }

  /** Only the activated Conversation page can name one idle candidate. */
  function fetchIdleChanges() {
    const revision = idleCandidate();
    if (revision === null || cancelComparison !== null || !deps.scheduleComparison) {
      return;
    }
    cancelComparison = deps.scheduleComparison(() => {
      cancelComparison = null;
      if (idleCandidate() === revision) {
        idleAttemptedRevision = revision;
        void askForRefresh({ number: options.number, prepare_comparison: revision });
      }
    });
  }

  /**
   * A reader's Retry changes or Fetch changes, which the address need not name. What the
   * button was painted from can be older than the model: a hold lifts by the clock alone,
   * and a failed read stops the automatic attempt without repainting. So the click sends
   * whenever the record still lacks its store and nothing else is on its way.
   */
  async function requestComparison() {
    if (
      !disposed &&
      tab === "files" &&
      deps.isVisible() &&
      inFlightRefreshes === 0 &&
      envelope?.refreshing === false &&
      envelope.record?.unavailable?.comparison === "no_store"
    ) {
      await fetchComparison();
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

  /**
   * *settling* says a Pulls-tab file walk showed this tab and will move the address there
   * once it stops; any other call, the route's own among them, ends that.
   *
   * @param {string} next
   * @param {{settling?: boolean}} [how]
   */
  function setTab(next, how = {}) {
    if (disposed || !TABS.includes(next)) {
      return;
    }
    tab = next;
    cancelIdleComparison();
    walkSettling = next === "files" && how.settling === true;
    // Whichever call leaves the address owning Changes under a hold, the route's confirmation
    // of a walk's tab among them, wakes the page at the lift if the poll set is later.
    const lifts = untilHoldLifts();
    if (timer !== null && lifts !== null && deps.now() + lifts < timerDue) {
      scheduleNext();
    }
    fetchSelectedChanges();
    render();
    fetchIdleChanges();
  }

  /** The walk that showed Changes stopped without moving the address there. */
  function walkCancelled() {
    if (!disposed && walkSettling) {
      walkSettling = false;
      render();
    }
  }

  function pump() {
    while (!disposed && inFlight < MARKDOWN_CONCURRENCY && queue.length > 0) {
      const part = /** @type {string} */ (queue.shift());
      const { text, revision } = asked.get(part) ?? { text: null, revision: null };
      const source = envelope?.source ?? null;
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
            body.record_revision !== revision ||
            revision !== markdownFor
          ) {
            // A render of a record the page no longer shows, or none at all: the
            // plain text stays, and a newer record is asked for again.
            if (!disposed && text !== null) {
              deps.textUnavailable?.(part, text);
            }
            return;
          }
          if (text === null) {
            return;
          }
          markdown.set(part, { rendered: body, text });
          rememberRendered(source, options.number, part, text, body);
          deps.renderMarkdown(part, body, text);
        })
        .catch(() => {
          if (!disposed && text !== null) {
            deps.textUnavailable?.(part, text);
          }
        })
        .finally(() => {
          inFlight -= 1;
          pump();
        });
    }
  }

  /**
   * Ask for one part's Markdown once per record. The glue asks when the part is within
   * `MARKDOWN_AHEAD` of the view, so a long conversation renders what a reader reaches.
   * A render an earlier page kept for the same text answers at once, a core preview's too.
   *
   * @param {string} part
   * @param {string} [shownText] The text the page shows for it; the record's when absent.
   */
  function requestMarkdown(part, shownText) {
    if (disposed) {
      return;
    }
    // A part the record does not name is still asked for, and its answer is kept by no text.
    const text = shownText ?? partText(envelope?.record ?? null, part);
    const done = markdown.get(part);
    if (done !== undefined && done.text === text) {
      deps.renderMarkdown(part, done.rendered, done.text);
      return;
    }
    const kept =
      text === null ? null : renderedText(envelope?.source ?? null, options.number, part, text);
    if (kept !== null && text !== null) {
      deps.renderMarkdown(part, kept, text);
      return;
    }
    if (markdownFor === null || asked.has(part)) {
      return;
    }
    asked.set(part, { text, revision: markdownFor });
    queue.push(part);
    pump();
  }

  /**
   * The render kept for *text*, by this page or an earlier one, or null.
   *
   * @param {string} part
   * @param {string} text
   */
  function renderedFor(part, text) {
    const done = markdown.get(part);
    return done !== undefined && done.text === text
      ? done.rendered
      : renderedText(envelope?.source ?? null, options.number, part, text);
  }

  function onVisibilityChange() {
    if (disposed) {
      return;
    }
    if (!deps.isVisible()) {
      clearTimer();
      cancelAsk();
      cancelIdleComparison();
      if (fetching) {
        fetching = false;
        readerAsked = false;
      }
      return;
    }
    void poll();
  }

  /** The browser's network came or went: online, read and ask if due; offline, say so. */
  function onConnectivityChange() {
    if (disposed) {
      return;
    }
    if (online()) {
      void poll();
    } else {
      render();
    }
  }

  function dispose() {
    disposed = true;
    // The Pulls tab's read this page joined is its own now: a page that goes ends it.
    if (joining) {
      reader?.abandon?.();
    }
    clearTimer();
    cancelAsk();
    cancelIdleComparison();
    queue.length = 0;
  }

  return Object.freeze({
    start: () => {
      // What the Pulls tab read when the row was chosen: the page paints with no empty frame,
      // and its first read then asks whether that is still so, unless that read was it.
      const initial = reader?.initial?.body;
      if (isEnvelope(initial) && accept(initial, 0)) {
        etag = reader?.initial?.etag ?? null;
        catalogScanning = / scanning$/u.test(reader?.initial?.verified ?? "");
        // A stale record the row read is painted refreshing from its first frame, never with
        // a Refresh it is about to make; the ask still waits as long as the opening said.
        askIfStale();
      }
      render();
      return firstRead();
    },
    poll: () => poll(),
    timelineAllowed: () =>
      hasPolled &&
      askTimer === null &&
      inFlightRefreshes === 0 &&
      (envelope?.refreshing === false || envelope?.preparing_comparison === true),
    fetchIdleChanges,
    requestRefresh,
    requestComparison,
    switchToHead,
    browseCode,
    requestMarkdown,
    renderedFor,
    setTab,
    walkCancelled,
    onVisibilityChange,
    onConnectivityChange,
    dispose,
    snapshot: () => ({
      state: envelope?.state ?? null,
      etag,
      tab,
      timer: timer === null ? null : pollsFast() ? "fast" : "slow",
      markdown: [...markdown.keys()],
      queued: [...queue],
      inFlight,
      error,
      settling: walkSettling,
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
 * Whether *pathname* is this page's entry on *tab*. A selected file beneath
 * `/pull/<n>/files/<path>` also belongs to Changes. Pure.
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
    model.pull === null ? null : { ...model.pull, merge: null },
    model.corePreview,
    ...(model.corePreview ? [model.refreshing] : []),
    model.timeline,
    model.reviewComments,
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
 * @param {{key: string, recordRevision: string | null}} previous
 * @param {{key: string, recordRevision: string | null}} next
 * @returns {"repaint" | "reask" | "keep"}
 */
export function conversationAction(previous, next) {
  if (previous.key !== next.key) {
    return "repaint";
  }
  return previous.recordRevision !== next.recordRevision ? "reask" : "keep";
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

/** The shell's keyframes for refreshing text (static/styles.css, `.mb-refreshing`). */
const REFRESHING = "mb-refreshing-text";

/**
 * Bring every refreshing breath under *root* to one beat. CSS starts an animation when its
 * element first matches, so a row drawn into a refreshing list, by a scroll of a windowed list
 * or a row whose text changed, would otherwise breathe out of step with the rest. The earliest
 * start among them is the beat; a browser without the Web Animations API keeps its own.
 *
 * @param {Element} root
 */
export function alignRefreshing(root) {
  if (typeof root.getAnimations !== "function") {
    return;
  }
  const breaths = root
    .getAnimations({ subtree: true })
    .filter((animation) => "animationName" in animation && animation.animationName === REFRESHING);
  /** @type {number | null} */
  let beat = null;
  for (const animation of breaths) {
    const start = animation.startTime;
    if (typeof start === "number" && (beat === null || start < beat)) {
      beat = start;
    }
  }
  if (beat !== null) {
    for (const animation of breaths) {
      if (animation.startTime !== beat) {
        animation.startTime = beat;
      }
    }
  }
}

/** Optional cached avatar URLs are revalidated before becoming browser requests.
 * @param {unknown} value
 * @returns {string | null}
 */
export function avatarUrl(value) {
  return typeof value === "string" &&
    /^https:\/\/avatars\.githubusercontent\.com\/(?:u|in)\/[0-9]{1,20}\?s=40$/.test(value)
    ? value
    : null;
}

/** A decorative image accompanies the same visible actor, never a replacement name.
 * @param {string} name
 * @param {unknown} url
 * @param {string} [className]
 */
export function authorLabel(name, url, className = "") {
  const label = h("span", { class: "github-pull-identity" });
  const safe = avatarUrl(url);
  if (safe !== null) {
    const image = h("img", {
      class: "github-pull-avatar",
      alt: "",
      width: "18",
      height: "18",
      loading: "lazy",
      decoding: "async",
      fetchpriority: "low",
      crossorigin: "anonymous",
      referrerpolicy: "no-referrer",
    });
    // A broken image keeps its fixed slot while the name remains immediately readable.
    image.addEventListener(
      "error",
      () => {
        image.style.visibility = "hidden";
      },
      { once: true },
    );
    image.setAttribute("src", safe);
    label.append(image);
  }
  label.append(
    h("strong", { class: `actor-name github-pull-author${className ? ` ${className}` : ""}` }, [
      name,
    ]),
  );
  return label;
}

/** Whether a destination is this exact known pull request, including its subpages.
 * @param {string} href
 * @param {string} pullUrl
 */
export function samePullDestination(href, pullUrl) {
  const path = /^\/([A-Za-z0-9-]+)\/([A-Za-z0-9_.-]+)\/pull\/([1-9]\d*)(?:\/|$)/;
  try {
    const target = new URL(href);
    const known = new URL(pullUrl);
    if (
      target.hostname !== "github.com" ||
      known.hostname !== "github.com" ||
      !/^https?:$/.test(target.protocol) ||
      target.username ||
      target.password ||
      target.port
    ) {
      return false;
    }
    const a = path.exec(target.pathname);
    const b = path.exec(known.pathname);
    return (
      a !== null &&
      b !== null &&
      a[1].toLowerCase() === b[1].toLowerCase() &&
      a[2].toLowerCase() === b[2].toLowerCase() &&
      a[3] === b[3]
    );
  } catch {
    return false;
  }
}

/** @param {HTMLElement} anchor @param {PullModel["pull"]} pull @param {MetabrowserPublicSdk} mb */
export function decoratePullLink(anchor, pull, mb) {
  const known =
    pull !== null && samePullDestination(anchor.getAttribute("href") ?? "", pull.htmlUrl);
  return mb.decorateExternalLink(
    anchor,
    known ? { icon: pullStateIcon(pull.state, { named: false }) } : {},
  );
}

/**
 * An outside link: new tab, no opener, no referrer. Text when the URL is not http(s).
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {string | null} href
 * @param {string} base
 * @param {Array<Node | string | null>} children
 * @param {string} [className]
 */
function outside(mb, href, base, children, className = "") {
  const safe = safeLink(href, base);
  if (safe === null) {
    return h("span", className ? { class: className } : {}, children);
  }
  return mb.decorateExternalLink(
    h(
      "a",
      {
        href: safe,
        target: "_blank",
        rel: "noopener noreferrer",
        ...(className ? { class: className } : {}),
      },
      children,
    ),
  );
}

let stackMenuSerial = 0;

/**
 * The native stack's compact trigger and lazy, keyboard-navigable member menu.
 * @param {import("./pull-stacks.js").NativeStack} initial
 * @param {number} number
 * @param {{link(number: number): HTMLElement, icon: Element | null, currentTitle: string, onOpen(): void}} deps
 */
export function createStackMenu(initial, number, deps) {
  let stack = initial;
  let currentTitle = deps.currentTitle;
  const position = stack.pulls.indexOf(number);
  const count = h("span", { class: "github-pull-stack-position" }, [
    `${position + 1}/${stack.pulls.length}`,
  ]);
  const menuId = `github-pull-stack-menu-${++stackMenuSerial}`;
  const root = /** @type {HTMLDetailsElement} */ (
    h("details", { class: "github-pull-stack-disclosure" })
  );
  const trigger = h(
    "summary",
    {
      class: "btn github-pull-stack-trigger disclosure-toggle",
      "aria-label": `Navigate Stack #${stack.number}, position ${position + 1} of ${stack.pulls.length}`,
      "aria-haspopup": "menu",
      "aria-controls": menuId,
      "aria-expanded": "false",
    },
    [
      deps.icon === null
        ? null
        : h("span", { class: "github-pull-stack-icon", "aria-hidden": "true" }, [deps.icon]),
      count,
    ],
  );
  const menu = h("div", {
    class: "menu github-pull-stack-menu",
    id: menuId,
    role: "menu",
    "aria-label": `Stack #${stack.number}`,
  });
  root.append(trigger);
  const listening = new AbortController();
  const signal = listening.signal;
  /** @type {HTMLElement[]} */
  const links = [];
  /** @type {Map<number, {link: HTMLElement, title: HTMLElement, position: HTMLElement, number: HTMLElement}>} */
  const rows = new Map();
  const label = h("div", { class: "menu-section-label" }, [`Stack #${stack.number}`]);
  let populated = false;

  function updateTitles() {
    for (let at = 0; at < stack.pulls.length; at += 1) {
      const target = stack.pulls[at];
      const row = rows.get(target);
      if (row) {
        row.title.textContent =
          stack.titles?.[at] || (target === number ? currentTitle : `Pull request #${target}`);
        row.position.textContent = `${at + 1}/${stack.pulls.length}`;
        row.number.textContent = `#${target}`;
      }
    }
  }

  /** @param {boolean} [reorder] */
  function populate(reorder = false) {
    if (populated && !reorder) {
      return;
    }
    const focused = document.activeElement;
    const restore = focused instanceof HTMLElement && menu.contains(focused);
    const scroll = menu.scrollTop;
    const retained = new Set(stack.pulls);
    for (const target of rows.keys()) {
      if (!retained.has(target)) {
        rows.delete(target);
      }
    }
    links.length = 0;
    for (let at = stack.pulls.length - 1; at >= 0; at -= 1) {
      const target = stack.pulls[at];
      let row = rows.get(target);
      if (!row) {
        const link = deps.link(target);
        link.setAttribute("class", "menu-item github-pull-stack-member");
        link.setAttribute("role", "menuitem");
        link.setAttribute("tabindex", "-1");
        if (target === number) {
          link.setAttribute("aria-current", "page");
        }
        const title = h("span", { class: "github-pull-stack-member-title" });
        const position = h("strong", { class: "github-pull-stack-member-position" });
        const identity = h("span", { class: "github-pull-stack-member-number" });
        link.append(
          h("span", { class: "github-pull-stack-current", "aria-hidden": "true" }, [
            target === number ? "✓" : "",
          ]),
          h("span", { class: "github-pull-stack-member-copy" }, [
            position,
            " ",
            h("span", { class: "github-pull-stack-dot", "aria-hidden": "true" }, ["·"]),
            " ",
            title,
            " ",
            h("span", { class: "github-pull-stack-dot", "aria-hidden": "true" }, ["·"]),
            " ",
            identity,
          ]),
        );
        row = { link, title, position, number: identity };
        rows.set(target, row);
      }
      links.push(row.link);
    }
    updateTitles();
    menu.replaceChildren(label, ...links);
    if (!populated) {
      root.append(menu);
      populated = true;
    }
    if (restore) {
      const target = links.includes(focused)
        ? focused
        : links.find((link) => link.getAttribute("aria-current") === "page");
      target?.focus({ preventScroll: true });
    }
    menu.scrollTop = scroll;
  }

  /** @param {boolean} [focus] */
  function close(focus = false) {
    root.open = false;
    trigger.setAttribute("aria-expanded", "false");
    if (focus && trigger.isConnected) {
      trigger.focus({ preventScroll: true });
    }
  }

  root.addEventListener(
    "toggle",
    () => {
      trigger.setAttribute("aria-expanded", String(root.open));
      if (root.open && !signal.aborted) {
        populate();
        deps.onOpen();
      }
    },
    { signal },
  );
  root.addEventListener(
    "keydown",
    (event) => {
      const key = event.key;
      if (event.target === trigger && (key === "Enter" || key === " ")) {
        event.preventDefault();
        event.stopPropagation();
        if (root.open) {
          close();
        } else {
          root.open = true;
          trigger.setAttribute("aria-expanded", "true");
          populate();
          deps.onOpen();
          links[0]?.focus({ preventScroll: true });
        }
        return;
      }
      if (key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        close(true);
        return;
      }
      if (key === "Tab" && root.open) {
        close(true);
        return;
      }
      if (key === " " && links.includes(/** @type {HTMLElement} */ (document.activeElement))) {
        event.preventDefault();
        event.stopPropagation();
        /** @type {HTMLElement} */ (document.activeElement).click();
        return;
      }
      if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(key)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      root.open = true;
      trigger.setAttribute("aria-expanded", "true");
      populate();
      deps.onOpen();
      const at = links.indexOf(/** @type {HTMLElement} */ (document.activeElement));
      const next =
        key === "Home"
          ? 0
          : key === "End"
            ? links.length - 1
            : at < 0
              ? key === "ArrowUp"
                ? links.length - 1
                : 0
              : (at + (key === "ArrowUp" ? -1 : 1) + links.length) % links.length;
      links[next]?.focus({ preventScroll: true });
      links[next]?.scrollIntoView({ block: "nearest" });
    },
    { signal },
  );
  // Run before the member link navigates and can replace this page. Only move
  // focus when it would otherwise remain inside the closed disclosure.
  menu.addEventListener("click", () => close(menu.contains(document.activeElement)), {
    capture: true,
    signal,
  });
  document.addEventListener(
    "pointerdown",
    (event) => {
      if (root.open && event.target instanceof Node && !root.contains(event.target)) {
        close();
      }
    },
    { signal },
  );
  document.addEventListener(
    "keydown",
    (event) => {
      if (root.open && event.key === "Escape") {
        event.preventDefault();
        close(true);
      }
    },
    { signal },
  );
  root.addEventListener(
    "focusout",
    (event) => {
      if (event.relatedTarget instanceof Node && !root.contains(event.relatedTarget)) {
        close();
      }
    },
    { signal },
  );
  return Object.freeze({
    element: root,
    close,
    /** A title or membership update keeps the menu open and retains surviving link focus.
     * @param {import("./pull-stacks.js").NativeStack} next
     * @param {string} title
     */
    update(next, title) {
      if (next === stack && title === currentTitle) {
        return;
      }
      const reordered =
        stack.pulls.length !== next.pulls.length ||
        stack.pulls.some((target, index) => target !== next.pulls[index]);
      stack = next;
      currentTitle = title;
      const at = stack.pulls.indexOf(number) + 1;
      count.textContent = `${at}/${stack.pulls.length}`;
      trigger.setAttribute(
        "aria-label",
        `Navigate Stack #${stack.number}, position ${at} of ${stack.pulls.length}`,
      );
      if (populated && reordered) {
        populate(true);
      } else {
        updateTitles();
      }
    },
    dispose() {
      listening.abort();
      close();
    },
  });
}

/**
 * Give the page's tab links their keys, `C`, `G`, and `H`, through the SDK's shortcut
 * surface. A key runs `setTab`, the page handle's own path, which moves the address as a
 * click on the link does. The links are kept across paints, so each key lasts until
 * `signal` aborts, as the page's disposal aborts it. Returns one handle per link, in
 * order, or none on a host without the surface.
 *
 * @param {MetabrowserPublicPluginShortcutsApi | undefined} shortcuts
 * @param {ReadonlyArray<{id: string, link: HTMLElement}>} tabLinks
 * @param {(tab: string) => void} setTab
 * @param {AbortSignal} signal
 * @returns {MetabrowserPublicPluginShortcutHandle[]}
 */
export function attachTabKeys(shortcuts, tabLinks, setTab, signal) {
  if (typeof shortcuts?.attach !== "function") {
    return [];
  }
  return tabLinks.flatMap(({ id, link }, index) => {
    const tab = PULL_TABS.find((candidate) => candidate.id === id);
    if (!tab) {
      return [];
    }
    return [
      shortcuts.attach(link, {
        activate: () => setTab(id),
        copy: {
          action: tab.label,
          description: `Show the pull request’s ${tab.label} tab.`,
          hint: tab.label,
        },
        group: "view-tabs",
        id: `github.pull.tab.${id || "conversation"}`,
        key: tab.key,
        order: 10 + index,
        signal,
      }),
    ];
  });
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
  const header = h("div", { class: "github-pull-header page-reading-column" });
  const body = h("div", { class: "github-pull-body" });
  const stackColumn = h("div", { class: "github-pull-stacks", hidden: "" });
  const stateBadge = h("span");
  const stateDetails = h("span", { class: "github-pull-state-details" });
  const stateRow = h("div", { class: "github-pull-meta" }, [stateBadge, stackColumn, stateDetails]);
  header.append(stateRow);
  // The status line and its age are kept across paints, so the age's breathing while a
  // refresh runs is one animation from start to end rather than one restarted at each paint.
  const freshnessLine = h("span", { class: "github-pull-freshness mb-refreshing-muted" });
  const status = h("div", { class: "github-pull-status" }, [freshnessLine]);
  /** Commits of the conversation are being read from GitHub for the record shown. */
  let timelineBusy = false;
  let stackIndex = createStackIndex(null);
  /** @type {import("./pull-stacks.js").StackIdentity | null} */
  let stackIdentity = null;
  let stackKey = "";
  let preferredStack = 0;
  /** @type {Map<number, ReturnType<typeof createStackMenu>>} */
  const stackMenus = new Map();
  const live = h("span", { class: "sr-only", "aria-live": "polite" });
  // Follow the reading column at every width; Files changed keeps the full pane.
  const tabBar = h("div", { class: "tab-bar", role: "tablist", "aria-label": "Pull request" });
  const tabColumn = h("div", { class: "page-reading-column" }, [tabBar]);
  container.replaceChildren(header, body, live);

  /** @type {PullModel | null} */
  let shown = null;
  let bodyKey = "";
  /** @type {() => void} */
  let resolveReady = () => {};
  const ready = new Promise((resolve) => {
    resolveReady = () => resolve(undefined);
  });
  /** The record the conversation last asked for Markdown from. @type {string | null} */
  let markdownRevision = null;
  /** @type {Map<string, HTMLElement>} */
  const texts = new Map();
  /** The text each text element shows, which its Markdown must be of. @type {WeakMap<Element, string>} */
  const textOf = new WeakMap();
  /** The conversation's sections as last painted, by what each shows. @type {Map<string, HTMLElement>} */
  let sections = new Map();
  /**
   * `fresh` while the task that painted the discussion runs: commits placed then are part
   * of its first paint, and any placed later only follow what is painted.
   *
   * @type {{description: HTMLElement, cards: Map<string, {node: HTMLElement, pending: boolean}>,
   *   inserts: Map<string, HTMLElement>, projection: TimelineProjection | null, fresh: boolean} | null}
   */
  let discussion = null;
  /**
   * The conversation's first paint of a full record, waiting at most `DESCRIPTION_HOLD_MS` for
   * the Markdown of the texts it shows. Spent once a page. Two ways, by what the body showed:
   *
   * - `hidden`, over nothing or the loading blocks: the conversation is painted and laid out
   *   out of sight, and waits for every text that is plain and on its first screen, measured
   *   from the page's own top (`parts`, all it waited for). Its kept renders are already
   *   final. A text whose Markdown cannot come is `failed` and waits no longer. Over the
   *   loading page the header waits with it (`header`), so the loading heading and any
   *   blocks that had shown (`cover`) stay as they are, and header and body change once.
   * - `delayed`, over a core preview: the preview stays as it is, and the full record paints
   *   once its description's Markdown can be inserted with it (`text`), or `plain` can.
   *
   * @type {{
   *   mode: "hidden" | "delayed",
   *   text: string,
   *   plain: boolean,
   *   parts: Set<string>,
   *   failed: Set<string>,
   *   cover: HTMLElement | null,
   *   header: boolean,
   *   since: number,
   *   timer: ReturnType<typeof window.setTimeout>,
   * } | null}
   */
  let firstPaint = null;
  let firstPaintSpent = false;
  /** What the body last painted: another tab's content is never held on screen. */
  /** @type {"none" | "loading" | "conversation" | "checks" | "files"} */
  let bodyShows = "none";
  let active = false;
  /** @type {{revision: string, source: string, projection: TimelineProjection | null,
   *   settled: boolean, cacheMiss: boolean, retryPending: boolean,
   *   read: {cachedOnly: boolean, abort: AbortController} | null} | null} */
  let commitTimeline = null;
  // The allowlist a text's Markdown passes through before it is inserted; a text stays
  // plain if it cannot load.
  /** @type {Promise<MetabrowserInertHtmlRuntime | null>} */
  const inertReady = mb
    .ensureAsset("inert-html")
    .then(() => window.MetabrowserInertHtml ?? null)
    .catch(() => null);
  /** @type {{left: string, right: string, route?: string} | null} */
  let diffFor = null;
  /** @type {{cancelPending?: () => void, dispose?: () => void} | null} */
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
              const value = textOf.get(entry.target);
              if (part !== null && value !== undefined) {
                observer?.unobserve(entry.target);
                controller.requestMarkdown(part, value);
              }
            }
          },
          { root: pane, rootMargin: MARKDOWN_AHEAD },
        )
      : null;

  /** An exact time, as an age's tooltip and a rate limit's lift give it. @param {number} ms */
  const exact = (ms) => mb.formatTimestamp(ms / 1000);
  /**
   * An age, from the one primitive, with the exact time in its tooltip. `also` is a time
   * the row leaves out because its age reads the same as this one; its exact time joins
   * this tooltip, so leaving the age out loses nothing.
   *
   * @param {string} iso
   * @param {{label: string, iso: string} | null} [also]
   */
  const age = (iso, also = null) => {
    const at = Date.parse(iso);
    if (!Number.isFinite(at)) {
      return h("span", {}, [iso]);
    }
    const { label, className } = mb.formatAge(at / 1000, { style: "relative" });
    const alsoAt = also === null ? Number.NaN : Date.parse(also.iso);
    const tip =
      also !== null && Number.isFinite(alsoAt)
        ? `${exact(at)} · ${also.label} ${exact(alsoAt)}`
        : exact(at);
    return h(
      "span",
      { class: `github-pull-age ${className}`, "data-tip-text": tip, "data-age-at": String(at) },
      [label],
    );
  };

  /**
   * Tell the ages in a kept node again, as of now: a section kept across paints keeps its
   * node, and its ages would otherwise read as of when it was built.
   *
   * @param {Element} node
   */
  const retellAges = (node) => {
    for (const element of node.querySelectorAll(".github-pull-age")) {
      const at = Number(element.getAttribute("data-age-at"));
      if (Number.isFinite(at)) {
        const { label, className } = mb.formatAge(at / 1000, { style: "relative" });
        if (element.textContent !== label) {
          element.textContent = label;
        }
        element.setAttribute("class", `github-pull-age ${className}`);
      }
    }
  };

  /**
   * A check's action. A GitHub destination is the quiet GitHub action, its mark leading;
   * the check's own site is an ordinary link, so it never reads as the description after
   * it. The accessible name adds the check's, so a list of links tells the rows apart.
   *
   * @param {CheckAction} action
   */
  const checkLink = (action) => {
    const github = action.kind !== "external";
    const link = outside(
      mb,
      action.href,
      "",
      [action.label],
      github ? "github-pull-external-action" : "",
    );
    link.setAttribute("aria-label", action.name);
    return github ? mb.decorateExternalLink(link, { icon: "github", position: "before" }) : link;
  };

  /** The text elements a section being built makes, which it keeps with it. @type {HTMLElement[] | null} */
  let collecting = null;
  /** @type {WeakMap<Element, HTMLElement[]>} */
  const sectionTexts = new WeakMap();

  /**
   * A text of the pull request: its Markdown when a render of this very text is kept and can
   * be inserted now, and otherwise plain until its Markdown arrives. The conversation asks
   * for what is still plain once its sections are placed.
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
    textOf.set(element, value);
    collecting?.push(element);
    const kept = controller.renderedFor(part, value);
    const inert = insertableNow(kept) ? window.MetabrowserInertHtml : undefined;
    element.append(
      kept !== null && inert !== undefined
        ? kpressHost(inert, kept)
        : h("div", { class: "github-pull-plain" }, [value]),
    );
    if (truncated) {
      element.append(notice("warning", ["This text was cut; the rest is on GitHub."]));
    }
    return element;
  }

  /**
   * Ask for the Markdown of the texts still plain: the description now, and the rest as they
   * near the view. A core preview's are answered only from renders kept for the same text.
   *
   * @param {HTMLElement[]} elements
   */
  function askForTexts(elements) {
    for (const element of elements) {
      const part = element.getAttribute("data-part");
      const value = textOf.get(element);
      if (part === null || value === undefined) {
        continue;
      }
      texts.set(part, element);
      if (element.querySelector(":scope > .github-pull-plain") === null) {
        continue;
      }
      if (part === "body" || observer === null) {
        controller.requestMarkdown(part, value);
      } else {
        observer.observe(element);
      }
    }
  }

  /** KPress's stylesheets, once. A text stays readable under the shell's if they fail. */
  /** @type {Promise<void> | null} */
  let documentStyles = null;

  /**
   * Whether *rendered* can be inserted in this task: the allowlist and the stylesheets an
   * earlier render loaded are in place, so it is final when it first shows.
   *
   * @param {Record<string, any> | null} rendered
   * @returns {boolean}
   */
  function insertableNow(rendered) {
    return rendered !== null && kpressStylesSettled && window.MetabrowserInertHtml !== undefined;
  }

  /**
   * KPress's Markdown HTML, reduced to the allowlist on the server; GitHub's own body_html is
   * never used, and no KPress script is loaded for it. static/inert-html.js parses it into an
   * inert template and inserts only nodes rebuilt from the same allowlist, links made absolute
   * against the pull request. The article and the classes on its tables and code blocks are
   * the page's own.
   *
   * @param {MetabrowserInertHtmlRuntime} inert
   * @param {Record<string, any>} rendered
   */
  function kpressHost(inert, rendered) {
    const nodes = inert.sanitizeHtml(
      String(rendered.html),
      shown?.pull?.htmlUrl ?? "https://github.com/",
    );
    const article = h("article", { class: "kpress kpress-inert" }, [
      inert.kpressProse(nodes, document),
    ]);
    // Only this newly sanitized, lazily opened message is visited. Authored SVG and
    // state attributes have already been discarded; known state comes from our record.
    for (const anchor of article.querySelectorAll("a[href]")) {
      decoratePullLink(/** @type {HTMLElement} */ (anchor), shown?.pull ?? null, mb);
    }
    return h("div", { class: "metabrowser-kpress-host" }, [article]);
  }

  /**
   * @param {string} part
   * @param {Record<string, any>} rendered
   * @param {string} text The text it is the render of.
   */
  function renderMarkdown(part, rendered, text) {
    const element = texts.get(part);
    if (documentStyles === null) {
      // Only a load that succeeded lets later pages insert kept renders without asking again.
      documentStyles = mb.loadKpressAssets(rendered.assets).then(
        () => {
          kpressStylesSettled = true;
        },
        (error) => {
          console.warn("metabrowser github: the text styles did not load", error);
        },
      );
    }
    void Promise.all([inertReady, documentStyles]).then(([inert]) => {
      if (listening.signal.aborted) {
        return;
      }
      const held = firstPaint;
      // The description a delayed first paint waits for may be insertable now, or never.
      if (held?.mode === "delayed" && part === "body" && held.text === text) {
        held.plain ||= inert === null;
        if (firstPaintReady()) {
          settleFirstPaint();
          return;
        }
      }
      const plain =
        element === undefined || texts.get(part) !== element || textOf.get(element) !== text
          ? null
          : element.querySelector(":scope > .github-pull-plain");
      if (plain && inert !== null) {
        plain.replaceWith(kpressHost(inert, rendered));
      } else if (inert === null) {
        held?.failed.add(part);
      }
      if (held?.mode === "hidden") {
        settleFirstPaint();
      }
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
   * @param {Parameters<NonNullable<MetabrowserPublicRenderContext["open"]>>[0]} route
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
      if (listening.signal.aborted || !isPlainClick(event)) {
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

  /**
   * A section a description preview does not have yet, while its refresh runs: the shell's
   * neutral pulsing blocks after the quiet period, never a spinner or a sentence. The reveal
   * wrapper and the skeleton are separate nodes, as on a cold page.
   *
   * @param {{"aria-label": string}} named What is loading, for a screen reader only.
   */
  const pendingSection = (named) =>
    h("div", { class: "mb-delayed-loading", role: "status", ...named }, [
      h("div", {
        class: "recent-loading github-pull-loading github-pull-section-loading",
        "aria-hidden": "true",
      }),
    ]);

  /** Only shell-owned icon constants enter this parser, never pull-request content.
   * @param {"toggle" | "layers"} name
   */
  const registryIcon = (name) =>
    new DOMParser().parseFromString(mb.icons[name] || "", "text/html").body.firstElementChild;
  const chevronSvg = registryIcon("toggle");
  const stackSvg = registryIcon("layers");
  function chevron() {
    return chevronSvg === null
      ? null
      : h("span", { class: "github-pull-fold-chevron", "aria-hidden": "true" }, [
          document.importNode(chevronSvg, true),
        ]);
  }

  /** One link per tab, kept across paints so a poll does not take focus from one. */
  const tabLinks = PULL_TABS.map(({ id, label }) => {
    const link = pageLink({ number, tab: id }, "tab-btn", [label]);
    link.setAttribute("role", "tab");
    tabBar.append(link);
    return { id, link };
  });
  /** The links' keys, from `attachTabKeys` once the page can end them. @type {MetabrowserPublicPluginShortcutHandle[]} */
  let tabKeys = [];

  /** Optional membership retains its status-row disclosure while other header details repaint.
   * @param {PullModel} model
   */
  function paintStacks(model) {
    const memberships =
      model.pull === null ? [] : stackMembership(stackIndex, stackIdentity, number);
    const key = JSON.stringify([stackIdentity, model.tab]);
    if (key !== stackKey) {
      for (const menu of stackMenus.values()) {
        menu.dispose();
      }
      stackMenus.clear();
      stackKey = key;
    }
    const retained = new Set(memberships.map((stack) => stack.number));
    for (const [id, menu] of stackMenus) {
      if (!retained.has(id)) {
        menu.dispose();
        stackMenus.delete(id);
      }
    }
    const nodes = memberships.map((stack) => {
      let menu = stackMenus.get(stack.number);
      if (menu) {
        menu.update(stack, model.pull?.title ?? "");
        return menu.element;
      }
      menu = createStackMenu(stack, number, {
        link: (target) => pageLink(memberRoute(target, model.tab), "", []),
        icon: stackSvg === null ? null : document.importNode(stackSvg, true),
        currentTitle: model.pull?.title ?? "",
        onOpen() {
          preferredStack = stack.number;
          for (const [other, view] of stackMenus) {
            if (other !== stack.number) {
              view.close();
            }
          }
        },
      });
      stackMenus.set(stack.number, menu);
      return menu.element;
    });
    stackColumn.hidden = nodes.length === 0;
    if (
      nodes.length !== stackColumn.children.length ||
      nodes.some((node, at) => node !== stackColumn.children[at])
    ) {
      const focused = document.activeElement;
      const restore = focused instanceof HTMLElement && stackColumn.contains(focused);
      stackColumn.replaceChildren(...nodes);
      if (restore && focused.isConnected) {
        focused.focus({ preventScroll: true });
      }
    }
  }

  /** The menu most recently used chooses a stack when a PR has several memberships. */
  function currentStack() {
    if (
      !active ||
      listening.signal.aborted ||
      shown === null ||
      shown.pull === null ||
      document.visibilityState !== "visible" ||
      !onPageRoute(window.location.pathname, number, controller.snapshot().tab)
    ) {
      return null;
    }
    const memberships = stackMembership(stackIndex, stackIdentity, number);
    return memberships.find((stack) => stack.number === preferredStack) ?? memberships[0] ?? null;
  }

  /** Keep stack disclosure and focus connected while ages and record details repaint.
   * @param {NonNullable<PullModel["pull"]>} pull
   */
  function paintStateRow(pull) {
    stateRow.hidden = false;
    stateBadge.replaceChildren(badge(pull.state, pull.stateLabel));
    stateDetails.replaceChildren(
      ...(pull.actor === null ? [] : [authorLabel(pull.actor, pull.actorAvatar)]),
      `${pull.actor === null ? "" : " "}${pull.action}: `,
      mb.mergeRefs(
        { name: pull.headRef, label: pull.head },
        { name: pull.baseRef, label: pull.base },
        { kind: "remote" },
      ),
    );
    return stateRow;
  }

  /**
   * Breathe the age while a refresh of what is shown runs or is due, or the conversation's
   * commits are read: the one sign of refreshing over content, with no spinner.
   *
   * @param {PullModel | null} model
   */
  function paintRefreshing(model) {
    const busy =
      model !== null &&
      model.pull !== null &&
      model.freshness !== null &&
      (model.revalidating || (timelineBusy && model.tab === ""));
    freshnessLine.classList.toggle("mb-refreshing", busy);
    // Busy is said of the age being updated, never of the status line's buttons and links.
    if (busy) {
      freshnessLine.setAttribute("aria-busy", "true");
    } else {
      freshnessLine.removeAttribute("aria-busy");
    }
  }

  /** @param {PullModel} model */
  function paintHeader(model) {
    const children = [];
    const pull = model.pull;
    if (pull !== null) {
      // The updated age is left out where it reads the same as the merged or closed age
      // beside it, or else the opened age; its exact time joins the tooltip of the age it
      // repeats. A merged pull request was usually last updated by its merge.
      const updated = age(pull.updated).textContent;
      const closedAt = pull.closed && pull.closedLabel ? pull.closed : null;
      const repeatsClosed = closedAt !== null && age(closedAt).textContent === updated;
      const repeatsOpened = !repeatsClosed && age(pull.created).textContent === updated;
      const also = { label: "updated", iso: pull.updated };
      children.push(
        h("h1", { class: "page-heading github-pull-title github-pull-title-with-state" }, [
          pullStateIcon(pull.state, { named: false }),
          h("span", {}, [
            pull.title,
            " ",
            h("span", { class: "github-pull-number" }, [`#${pull.number}`]),
          ]),
        ]),
        paintStateRow(pull),
        h("div", { class: "github-pull-quiet" }, [
          "Opened ",
          age(pull.created, repeatsOpened ? also : null),
          ...(repeatsClosed || repeatsOpened ? [] : [" · updated ", age(pull.updated)]),
          ...(closedAt === null
            ? []
            : [` · ${pull.closedLabel} `, age(closedAt, repeatsClosed ? also : null)]),
          " · ",
          mb.decorateExternalLink(
            outside(mb, pull.htmlUrl, "", ["View on GitHub"], "github-pull-external-action"),
            {
              icon: "github",
              position: "before",
            },
          ),
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
      children.push(
        h("h1", { class: "page-heading github-pull-title" }, [`Pull request #${model.number}`]),
      );
    }
    status.dataset.status = model.status;
    for (const node of [...status.childNodes]) {
      if (node !== freshnessLine) {
        node.remove();
      }
    }
    if (freshnessLine.parentNode !== status) {
      status.prepend(freshnessLine);
    }
    freshnessLine.hidden = model.freshness === null;
    if (freshnessLine.textContent !== (model.freshness ?? "")) {
      freshnessLine.textContent = model.freshness ?? "";
    }
    paintRefreshing(model);
    if (model.message !== null) {
      status.append(h("span", { class: "github-pull-message" }, [model.message]));
    }
    if (model.failure !== null) {
      status.append(h("span", { class: "github-pull-failure" }, [model.failure]));
    }
    if (model.failureHelp !== undefined) {
      status.append(
        outside(mb, "https://cli.github.com/", "", [
          model.failureHelp === "install" ? "Install GitHub CLI" : "Update GitHub CLI",
        ]),
      );
    }
    if (model.canRefresh) {
      const refresh = h("button", { type: "button", class: "btn github-pull-refresh" }, [
        model.status === "absent" ? "Fetch" : "Refresh",
      ]);
      refresh.addEventListener("click", () => {
        if (listening.signal.aborted || shown?.canRefresh !== true) {
          return;
        }
        const displayed = shown.tab === "files" ? diffFor : null;
        filesRefresh = displayed;
        void controller.requestRefresh(
          displayed === null ? undefined : { base: displayed.left, head: displayed.right },
        );
      });
      status.append(refresh);
    }
    if (model.headOffer !== null) {
      const button = h("button", { type: "button", class: "btn github-pull-switch" }, [
        "Switch to the head",
      ]);
      button.addEventListener("click", () => void controller.switchToHead());
      status.append(h("span", { class: "github-pull-offer" }, [model.headOffer.text, " ", button]));
    }
    if (model.checkoutAtHead !== null) {
      const root = h("a", { href: mb.navigation.href({ path: "" }) }, ["Browse the checkout"]);
      status.append(h("span", { class: "github-pull-offer" }, [model.checkoutAtHead, " ", root]));
    }
    children.push(status);
    const visible = children.filter((child) => child !== null);
    /** @type {Set<Node>} */
    const retained = new Set(visible);
    for (const node of [...header.childNodes]) {
      if (!retained.has(node)) {
        node.remove();
      }
    }
    let cursor = header.firstChild;
    for (const node of visible) {
      if (node === cursor) {
        cursor = cursor.nextSibling;
      } else {
        header.insertBefore(node, cursor);
      }
    }
    if (model.pull === null) {
      tabColumn.remove();
    } else {
      for (const { id, link } of tabLinks) {
        link.classList.toggle("active", model.tab === id);
        link.setAttribute("aria-selected", String(model.tab === id));
      }
      const returning = tabColumn.parentNode === null;
      header.after(tabColumn);
      if (returning) {
        // The same links come back, keys and all; retargeting them badges them at once
        // if the reader is holding Shift.
        tabKeys.forEach((handle, at) => {
          handle.retarget(tabLinks[at].link);
        });
      }
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

  /**
   * One commit's row, the one already shown for it when there is one.
   *
   * @param {TimelineCommit} event
   * @param {string} source
   * @param {Map<string, HTMLElement>} shownRows
   * @returns {HTMLElement | null}
   */
  function commitRow(event, source, shownRows) {
    const shownRow = shownRows.get(event.oid);
    if (shownRow !== undefined) {
      retellAges(shownRow);
      return shownRow;
    }
    const href = timelineCommitHref(source, number, event.oid);
    if (href === null) {
      return null;
    }
    return h("div", { class: "github-pull-commit" }, [
      h("span", { class: "github-pull-commit-subject" }, [event.subject || "Commit"]),
      event.committed_at !== null && Number.isFinite(Date.parse(event.committed_at))
        ? h("span", { class: "github-pull-quiet" }, ["committed ", age(event.committed_at)])
        : null,
      mb.decorateExternalLink(
        outside(
          mb,
          href,
          "",
          [event.oid.slice(0, 7)],
          "github-pull-commit-id git-commit-sha github-pull-external-action",
        ),
        { icon: "github", position: "before" },
      ),
    ]);
  }

  /** Remove the commit rows a superseded record's projection placed. */
  function retireRows() {
    if (discussion === null || discussion.inserts.size === 0) {
      return;
    }
    for (const node of discussion.inserts.values()) {
      node.remove();
    }
    discussion.inserts = new Map();
    discussion.projection = null;
  }

  /**
   * Install the provider order around the existing cards. Keep the focused card in
   * place and move its neighbors around it, so even a reordered review keeps focus.
   *
   * That is only while the discussion's own first paint is being made. A projection that
   * answers once it has painted moves nothing that is painted: the commit rows it adds go
   * after everything, in its order, and the cards keep theirs. A missing or unavailable
   * projection leaves what is shown, so a refreshed record keeps its rows until its own
   * projection replaces them.
   *
   * @param {TimelineProjection | null} projection
   * @param {string} source
   */
  function paintTimeline(projection, source) {
    if (
      discussion === null ||
      discussion.projection === projection ||
      projection === null ||
      projection.state === "unavailable"
    ) {
      return;
    }
    const { description, cards, inserts: previousInserts } = discussion;
    /** @type {Map<string, HTMLElement>} */
    const inserts = new Map();
    discussion.projection = projection;
    discussion.inserts = inserts;
    if (!discussion.fresh) {
      for (const event of projection.events) {
        if (event.kind !== "commit" || inserts.has(event.oid)) {
          continue;
        }
        const row = commitRow(event, source, previousInserts);
        if (row !== null) {
          if (!previousInserts.has(event.oid)) {
            body.append(row);
          }
          inserts.set(event.oid, row);
        }
      }
      if (projection.state === "partial") {
        const note =
          previousInserts.get("partial") ??
          h("p", { class: "github-pull-quiet" }, ["Some commits may be missing."]);
        if (!previousInserts.has("partial")) {
          body.append(note);
        }
        inserts.set("partial", note);
      }
      for (const [key, node] of previousInserts) {
        if (!inserts.has(key)) {
          node.remove();
        }
      }
      return;
    }
    const unmatched = new Map(cards);
    /** @type {HTMLElement[]} */
    const ordered = [];
    for (const event of projection.events) {
      if (event.kind !== "commit") {
        const key = `${event.kind}/${event.id}`;
        const card = unmatched.get(key);
        if (card !== undefined && !card.pending) {
          ordered.push(card.node);
          unmatched.delete(key);
        }
        continue;
      }
      if (inserts.has(event.oid)) {
        continue;
      }
      const row = commitRow(event, source, previousInserts);
      if (row === null) {
        continue;
      }
      ordered.push(row);
      inserts.set(event.oid, row);
    }
    for (const { node } of unmatched.values()) {
      ordered.push(node);
    }
    if (projection.state === "partial") {
      const note =
        previousInserts.get("partial") ??
        h("p", { class: "github-pull-quiet" }, ["Some commits may be missing."]);
      ordered.push(note);
      inserts.set("partial", note);
    }
    for (const [key, node] of previousInserts) {
      if (!inserts.has(key)) {
        node.remove();
      }
    }

    const focused = ordered.findIndex((node) => node.contains(document.activeElement));
    let next = ordered[focused];
    for (let index = focused - 1; index >= 0; index -= 1) {
      const node = ordered[index];
      if (next.previousElementSibling !== node) {
        body.insertBefore(node, next);
      }
      next = node;
    }
    let previous = ordered[focused] ?? description;
    for (let index = focused + 1; index < ordered.length; index += 1) {
      const node = ordered[index];
      if (previous.nextElementSibling !== node) {
        body.insertBefore(node, previous.nextElementSibling);
      }
      previous = node;
    }
  }

  /**
   * Paint the conversation in place. A section shown before with the same content keeps its
   * node, rendered Markdown and all, and where it is: nothing above the first section that
   * changed moves, and a full record replacing its core preview keeps the description it
   * already shows. Commit rows the timeline placed stay among the cards they follow.
   *
   * @param {PullModel} model
   */
  function paintConversation(model) {
    const pull = /** @type {NonNullable<PullModel["pull"]>} */ (model.pull);
    texts.clear();
    observer?.disconnect();
    /** @type {Map<string, HTMLElement>} */
    const next = new Map();
    /** @type {HTMLElement[]} */
    const order = [];
    /** @type {HTMLElement[]} */
    const textElements = [];
    /**
     * @param {unknown[]} what Everything the section shows.
     * @param {() => HTMLElement} build
     */
    const section = (what, build) => {
      const key = JSON.stringify(what);
      let node = sections.get(key);
      if (node === undefined || next.has(key)) {
        collecting = [];
        node = build();
        sectionTexts.set(node, collecting);
        collecting = null;
      } else {
        retellAges(node);
      }
      next.set(key, node);
      order.push(node);
      textElements.push(...(sectionTexts.get(node) ?? []));
      return node;
    };
    const description = section(
      // A rendered text's links to this pull request show its state, so the state is named.
      [
        "description",
        pull.state,
        pull.author,
        pull.avatar,
        pull.created,
        pull.text,
        pull.truncated,
      ],
      () =>
        h("section", { class: "page-card github-pull-card" }, [
          h("div", { class: "github-pull-card-head" }, [
            authorLabel(pull.author, pull.avatar),
            " opened ",
            age(pull.created),
          ]),
          textBlock("body", pull.text, pull.truncated),
        ]),
    );
    /** @type {Map<string, {node: HTMLElement, pending: boolean}>} */
    const cards = new Map();
    if (model.corePreview) {
      section(["discussion pending", model.refreshing], () =>
        h("section", { class: "github-pull-section" }, [
          h("h2", { class: "section-heading" }, ["Discussion"]),
          model.refreshing
            ? pendingSection({ "aria-label": "Loading comments and reviews" })
            : h("p", { class: "github-pull-quiet" }, [
                "Comments and reviews have not been fetched.",
              ]),
        ]),
      );
    }
    for (const item of model.corePreview ? [] : model.timeline) {
      const card = section(["card", pull.state, item], () => {
        const head = h("div", { class: "github-pull-card-head" }, [
          authorLabel(item.author, item.avatar),
        ]);
        if (item.review !== null) {
          head.append(" ", badge(item.review.state, item.review.label, "review"));
        } else {
          head.append(" commented");
        }
        head.append(" ", item.at === null ? "(pending)" : age(item.at));
        const built = h(
          "section",
          { class: `page-card github-pull-card github-pull-${item.kind}` },
          [head],
        );
        if (item.text.trim() !== "" || item.kind === "comment") {
          built.append(textBlock(item.part, item.text, item.truncated));
        }
        return built;
      });
      cards.set(`${item.kind}/${item.id}`, {
        node: card,
        pending: item.kind === "review" && (item.at === null || item.review?.state === "PENDING"),
      });
    }
    if (!model.corePreview && model.reviewComments.length > 0) {
      section(["threads", pull.state, model.reviewComments, model.browse], () =>
        reviewThreads(model),
      );
    }
    for (const [index, note] of (model.corePreview ? [] : model.notes).entries()) {
      section(["note", index, note], () => notice("warning", [note]));
    }
    sections = next;

    const before = discussion;
    const inserts = model.corePreview ? new Map() : (before?.inserts ?? new Map());
    const rows = new Set(inserts.values());
    for (const row of rows) {
      retellAges(row);
    }
    const placed = new Set(order);
    const cover = firstPaint?.cover ?? null;
    // The body holds only these sections and commit rows, all elements, and the loading
    // blocks a held first paint keeps over them.
    for (const child of [...body.childNodes]) {
      const node = /** @type {HTMLElement} */ (child);
      if (!placed.has(node) && !rows.has(node) && node !== cover) {
        node.remove();
      }
    }
    let cursor = body.firstChild;
    for (const node of order) {
      while (cursor !== null && cursor !== node && rows.has(/** @type {HTMLElement} */ (cursor))) {
        cursor = cursor.nextSibling;
      }
      if (cursor === node) {
        cursor = cursor.nextSibling;
      } else {
        body.insertBefore(node, cursor);
      }
    }
    const sameCards =
      before !== null &&
      before.cards.size === cards.size &&
      [...cards].every(([key, card]) => before.cards.get(key)?.node === card.node);
    discussion = model.corePreview
      ? null
      : {
          description,
          cards,
          inserts,
          projection: sameCards ? before.projection : null,
          fresh: true,
        };
    const painting = discussion;
    // Commits placed in this task are part of this paint; later ones follow what it painted.
    queueMicrotask(() => {
      if (painting !== null) {
        painting.fresh = false;
      }
    });
    askForTexts(textElements);
  }

  /** @param {PullModel} model */
  function reviewThreads(model) {
    const threads = h("section", { class: "github-pull-section" }, [
      h("h2", { class: "section-heading" }, [`Review comments (${model.reviewComments.length})`]),
    ]);
    for (const comment of model.reviewComments) {
      const head = h("div", { class: "github-pull-card-head" }, [
        fileLink(comment.path, comment.line, model.browse),
        comment.outdated ? " " : "",
        comment.outdated ? badge("outdated", "outdated", "review") : null,
        " ",
        authorLabel(comment.author, comment.avatar),
        ` ${comment.reply ? "replied" : "commented"} `,
        age(comment.at),
      ]);
      const card = h(
        "div",
        { class: `page-card github-pull-card${comment.reply ? " github-pull-reply" : ""}` },
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
            h("summary", { class: "fold-expander disclosure-toggle" }, [
              chevron(),
              h("span", { class: "github-pull-fold-closed" }, [`${earlierLines} earlier ${lines}`]),
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
    return threads;
  }

  /** @param {PullModel} model @param {NonNullable<PullModel["pull"]>} pull */
  function paintChecks(model, pull) {
    const summary = model.checks;
    const checksSection = h("section", { class: "github-pull-section" }, [
      h("h2", { class: "section-heading" }, ["Checks"]),
    ]);
    if (model.corePreview) {
      checksSection.append(
        model.refreshing
          ? pendingSection({ "aria-label": "Loading checks and statuses" })
          : h("p", { class: "github-pull-quiet" }, ["Checks and statuses have not been fetched."]),
      );
    } else if (summary !== null) {
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
            h("span", {}, [item.name]),
            item.action === null ? null : checkLink(item.action),
            item.detail ? h("span", { class: "github-pull-quiet" }, [item.detail]) : null,
          ]),
        );
      }
      checksSection.append(rows);
    } else if (model.checkNotes.length === 0) {
      checksSection.append(
        h("p", { class: "github-pull-quiet" }, ["No checks or statuses reported."]),
      );
    }
    if (!model.corePreview && pull.merge !== null) {
      checksSection.append(
        h("p", { class: "github-pull-merge", "data-state": pull.merge.state }, [pull.merge.label]),
      );
    }
    body.replaceChildren(
      checksSection,
      ...model.checkNotes.map((note) => notice("warning", [note])),
    );
  }

  /** Settles when the diff last asked for has mounted, or was replaced. */
  let diffMounted = Promise.resolve();
  /** An explicit Files refresh waiting for its job; metadata polls alone never remount.
   * @type {{left: string, right: string, route?: string} | null}
   */
  let filesRefresh = null;

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
      signal.throwIfAborted();
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
          ...(comparison.rendered_route === undefined
            ? {}
            : { rendered_route: comparison.rendered_route }),
        },
        signal,
      );
    },
    warm() {
      void mb.ensureKindAssets("diff").catch(() => {});
    },
    schedule: (callback) => mb.whenIdle(callback, { timeout: PREFETCH_IDLE_TIMEOUT_MS }),
    cancel: (cancel) => /** @type {() => void} */ (cancel)(),
    isVisible: () => document.visibilityState === "visible",
  });

  /** @param {{left: string, right: string, route?: string, snapshot_route?: string, rendered_route?: string}} comparison */
  async function mountDiff(comparison) {
    if (listening.signal.aborted) {
      return;
    }
    disposeDiff();
    const host = h("div", { class: "github-pull-diff metabrowser-diff-host" });
    diffHost = host;
    diffFor = comparison;
    const owns = () => !listening.signal.aborted && diffHost === host;
    const loading = h(
      "div",
      {
        class: "loading mb-delayed-loading github-pull-diff-loading",
        role: "status",
        "aria-label": "Loading changes",
      },
      [h("span", { class: "spinner", "aria-hidden": "true" })],
    );
    // Keep progress below the host so it cannot move the diff’s first row.
    body.replaceChildren(host, loading);
    try {
      const raw = prefetch.take(comparison);
      await mb.ensureKindAssets("diff");
      if (!owns()) {
        return;
      }
      const view = mb.getRegisteredView("diff", "diff");
      if (!view) {
        host.textContent = "The diff plugin is unavailable.";
        return;
      }
      const prefetched = await raw;
      if (!owns()) {
        return;
      }
      // A comparison with rendered Markdown is laid out out of sight from its first draw until
      // its first screen's Markdown waits no more, at most its bound; progress stays below.
      const holds = comparison.rendered_route !== undefined;
      if (holds) {
        host.classList.add("github-pull-diff-holding");
      }
      const handle = /** @type {{dispose?: () => void, currentFile?: () => unknown} | null} */ (
        await mb.perf.measureAsync(
          "githubPull:filesRender",
          async () =>
            view.render(host, {
              comparisonSignal: listening.signal,
              comparison: {
                left: comparison.left,
                right: comparison.right,
                base_policy: "merge_base",
                ...(comparison.route === undefined ? {} : { route: comparison.route }),
                ...(comparison.snapshot_route === undefined
                  ? {}
                  : { snapshot_route: comparison.snapshot_route }),
                ...(comparison.rendered_route === undefined
                  ? {}
                  : { rendered_route: comparison.rendered_route }),
              },
              ...(prefetched === undefined ? {} : { raw: prefetched }),
              ...(comparison.rendered_route === undefined
                ? {}
                : { markdownHoldMs: CHANGES_FIRST_SCREEN_MS }),
            }),
          { number },
        )
      );
      if (!owns()) {
        loading.remove();
        handle?.dispose?.();
        return;
      }
      diffHandle = handle;
      watchCurrentFileAfterPaint(host, handle);
      // Landed before the wait, so the first screen the Markdown layer reports is the one the
      // reader lands on: a file the address names, not the top of the diff.
      landFile();
      const firstScreen = /** @type {{firstScreen?: () => Promise<void>} | null} */ (handle)
        ?.firstScreen;
      if (holds && typeof firstScreen === "function") {
        const since = Date.now();
        /** @type {ReturnType<typeof window.setTimeout> | undefined} */
        let bound;
        const outcome = await Promise.race([
          firstScreen().then(() => "met"),
          new Promise((resolve) => {
            bound = window.setTimeout(() => resolve("bound"), CHANGES_FIRST_SCREEN_MS);
          }),
        ]);
        window.clearTimeout(bound);
        mb.perf.measure("githubPull:changesHold", () => {}, {
          number,
          heldMs: Date.now() - since,
          // A page that went during the wait settles its diff's first screen by disposing it.
          outcome: owns() ? outcome : "cancelled",
        });
      }
      loading.remove();
      if (!owns()) {
        // A page that went while its diff was held keeps it out of sight, as its conversation
        // does: the page replacing it shows it as it was until that one is ready.
        return;
      }
      host.classList.remove("github-pull-diff-holding");
      // Failed diff loads resolve to a disposable notice without the public file API.
      // Do not report that surface, or a replaced mount, as useful Files readiness.
      if (owns() && typeof handle?.currentFile === "function") {
        mb.perf.measure("githubPull:filesReady", () => {}, { number });
      }
    } catch {
      if (!owns()) {
        return;
      }
      host.classList.remove("github-pull-diff-holding");
      const retry = h("button", { type: "button", class: "btn" }, ["Retry"]);
      retry.addEventListener("click", () => {
        if (owns()) {
          diffMounted = mountDiff(comparison);
        }
      });
      host.replaceChildren(notice("error", ["Changes could not load. ", retry]));
    } finally {
      loading.remove();
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
    if (filesRefresh !== null) {
      const displayed = filesRefresh;
      if (model.refreshing) {
        // Returning from Conversation still has to render Files while repair runs.
        if (diffFor === null) {
          diffMounted = mountDiff(displayed);
        }
        return;
      }
      filesRefresh = null;
      if (
        diffFor === null ||
        (model.failure === null && model.message === null && diffFor === displayed)
      ) {
        // Only an existing Files mount can supply the place this remount preserves.
        // A history arrival already owns its saved place; Conversation must not overwrite it.
        if (diffFor !== null) {
          place?.keeper.flush();
        }
        diffMounted = mountDiff(displayed).then(() => {
          if (!listening.signal.aborted && shown?.tab === "files" && diffFor === displayed) {
            paintFiles(shown);
            place?.keeper.land();
          }
        });
        return;
      }
      // The reader may have explicitly selected another comparison during the job.
      // Let the current route render normally instead of restoring the older repair.
    }
    const comparison = model.comparison;
    const action = filesAction(diffFor, comparison);
    if (comparison === null || action === "unavailable") {
      disposeDiff();
      if (model.changesPending) {
        // Nothing of Changes is cached yet and its shape is unknown: the shared spinner after
        // the quiet period, and the sentence only for a screen reader.
        body.replaceChildren(
          h(
            "div",
            {
              class: "loading mb-delayed-loading github-pull-changes-pending",
              role: "status",
              "aria-label": model.filesUnavailable,
            },
            [h("span", { class: "spinner", "aria-hidden": "true" })],
          ),
        );
        return;
      }
      const message = notice(model.corePreview ? null : "error", [model.filesUnavailable]);
      if (model.canRetryComparison || model.canFetchComparison) {
        const retry = model.canRetryComparison;
        const ask = h(
          "button",
          {
            type: "button",
            class: `btn ${retry ? "github-pull-retry-changes" : "github-pull-fetch-changes"}`,
          },
          [retry ? "Retry changes" : "Fetch changes"],
        );
        ask.addEventListener("click", () => void controller.requestComparison());
        message.append(ask);
      }
      body.replaceChildren(message);
      return;
    }
    if (action === "mount") {
      diffMounted = mountDiff(comparison);
    } else if (action === "offer") {
      const offer = h("button", { type: "button", class: "btn github-pull-newer" }, [
        "Show the newer changes",
      ]);
      offer.addEventListener("click", () => {
        // A reader's explicit newer selection ends the older repair's UI ownership.
        filesRefresh = null;
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
    // The repository's list says the head moved before the record was read again: the diff
    // shown stays, and the offer above replaces this once the refresh brings the newer one.
    body.querySelector(".github-pull-new-commits")?.remove();
    if (model.newCommits !== null && action !== "offer") {
      const said = notice(null, [model.newCommits]);
      said.classList.add("github-pull-new-commits");
      body.prepend(said);
    }
  }

  /** @param {PullModel} model */
  function paint(model) {
    container.dataset.corePreview = String(model.corePreview);
    shown = model;
    if (model.tab !== "files") {
      wantedFile = null;
    }
    if (firstPaint !== null && (model.tab !== "" || model.pull === null)) {
      // Another tab holds the body now: the conversation paints as it is when it returns.
      releaseFirstPaint("closed");
    }
    // The conversation's first paint is decided before the header, since a hold over the
    // loading page keeps the loading heading too: header and body then change once.
    const conversation = model.pull !== null && model.tab !== "files" && model.tab !== "checks";
    const key = conversation ? conversationKey(model) : null;
    const action =
      key === null
        ? null
        : conversationAction(
            { key: bodyKey, recordRevision: markdownRevision },
            { key, recordRevision: model.recordRevision },
          );
    const hold = action === "repaint" ? holdFirstPaint(model) : null;
    if (!(firstPaint?.mode === "hidden" && firstPaint.header)) {
      paintHeader(model);
      paintStacks(model);
    }
    // Conversation and Checks use the reading column. Changes uses the full pane.
    body.classList.toggle("page-reading-column", model.pull === null || model.tab !== "files");
    if (model.pull === null) {
      disposeDiff();
      discussion = null;
      texts.clear();
      // A known text layout uses the shell's neutral pulse. The reveal wrapper has its
      // own node so its animation does not replace the skeleton's pulse/reduced motion.
      body.replaceChildren(
        ...(model.status === "loading" || model.status === "pending"
          ? [
              h(
                "div",
                {
                  class: "mb-delayed-loading",
                  role: "status",
                  "aria-label": "Loading the pull request",
                },
                [h("div", { class: "recent-loading github-pull-loading", "aria-hidden": "true" })],
              ),
            ]
          : []),
      );
      bodyKey = "";
      bodyShows = "loading";
      return;
    }
    if (model.tab === "files") {
      bodyKey = "";
      bodyShows = "files";
      discussion = null;
      texts.clear();
      paintFiles(model);
      return;
    }
    disposeDiff();
    if (model.tab === "checks") {
      const key = JSON.stringify([
        "checks",
        model.corePreview,
        model.corePreview && model.refreshing,
        model.checks,
        model.checkNotes,
        model.pull.merge,
        model.pull.htmlUrl,
      ]);
      if (key !== bodyKey) {
        bodyKey = key;
        bodyShows = "checks";
        discussion = null;
        texts.clear();
        observer?.disconnect();
        paintChecks(model, model.pull);
      }
      return;
    }
    if (model.comparison !== null) {
      prefetch.want(model.comparison);
    }
    if (hold === "delayed" || key === null) {
      return;
    }
    bodyKey = key;
    if (action === "repaint") {
      if (firstPaint?.mode === "hidden" && firstPaint.cover === null) {
        firstPaint.cover = shownLoading();
        firstPaint.cover?.classList.add("github-pull-loading-cover");
      }
      bodyShows = "conversation";
      paintConversation(model);
    } else if (action === "reask") {
      askForTexts([...texts.values()]);
    }
    if (firstPaint?.mode === "hidden") {
      body.classList.add("github-pull-body-holding");
    }
    markdownRevision = model.recordRevision;
  }

  /**
   * How the conversation's first paint of a full record waits, starting the wait when it is
   * the first (see `firstPaint`): `hidden` over nothing or the loading blocks, `delayed` over a
   * core preview, or null when it paints as it is. Its kept renders make a revisit final at
   * once. Meanwhile the page is not ready, so a page replacing another keeps that one on
   * screen. Commits wait for nothing: they are placed if held at this paint, and otherwise
   * follow what it painted.
   *
   * @param {PullModel} model
   * @returns {"hidden" | "delayed" | null}
   */
  function holdFirstPaint(model) {
    const pull = model.pull;
    if (firstPaintSpent || model.corePreview || model.recordRevision === null || pull === null) {
      return null;
    }
    if (bodyShows === "files" || bodyShows === "checks") {
      // A reader's own tab switch, from content that is not the conversation: paint now.
      firstPaintSpent = true;
      return null;
    }
    if (firstPaint !== null) {
      if (firstPaint.mode === "hidden") {
        // A newer record paints out of sight too, and its plain texts join the wait.
        return "hidden";
      }
      if (firstPaint.text !== pull.text) {
        firstPaint.plain = false;
        controller.requestMarkdown("body", pull.text);
      }
      firstPaint.text = pull.text;
      return "delayed";
    }
    const describedNow =
      pull.text.trim() === "" || insertableNow(controller.renderedFor("body", pull.text));
    const delayed = bodyShows === "conversation";
    if (delayed && describedNow) {
      firstPaintSpent = true;
      return null;
    }
    firstPaint = {
      mode: delayed ? "delayed" : "hidden",
      text: pull.text,
      plain: false,
      parts: new Set(),
      failed: new Set(),
      cover: null,
      header: !delayed && bodyShows === "loading",
      since: Date.now(),
      timer: window.setTimeout(() => releaseFirstPaint("bound"), DESCRIPTION_HOLD_MS),
    };
    if (delayed) {
      controller.requestMarkdown("body", pull.text);
    }
    return firstPaint.mode;
  }

  /** Whether the description a delayed first paint waits for has come: it then shows final. */
  function firstPaintReady() {
    const held = firstPaint;
    if (held === null || held.mode !== "delayed") {
      return true;
    }
    return (
      held.plain ||
      held.text.trim() === "" ||
      insertableNow(controller.renderedFor("body", held.text))
    );
  }

  /**
   * An element's box, or null where nothing is laid out.
   *
   * @param {Element} element
   * @returns {DOMRect | null}
   */
  function boxOf(element) {
    return typeof element.getBoundingClientRect === "function"
      ? element.getBoundingClientRect()
      : null;
  }

  /**
   * The texts a hidden first paint still waits for: each plain, not failed, and on the page's
   * first screen, from the conversation's own layout, out of sight as it is. The screen is one
   * pane's height from the page's own top, where the page shows once installed, and not the
   * pane's view now: a page that replaces another is laid out where that one is scrolled to.
   * It is taken again at every check, since a text that renders changes height and moves the
   * texts below it. With no layout to measure, every plain text is waited for. The next
   * `FIRST_SCREEN_AHEAD` plain texts past the screen are `ahead`: asked for, not waited
   * on, so one that comes up as those above render is already on its way. A failed text on
   * the screen is among the texts waited for, and ends the wait as unavailable.
   *
   * @param {NonNullable<typeof firstPaint>} held
   * @returns {{waiting: [string, HTMLElement][], ahead: [string, HTMLElement][]}}
   */
  function firstScreenPlain(held) {
    const top = boxOf(container)?.top ?? null;
    const height = pane?.clientHeight || window.innerHeight || Number.POSITIVE_INFINITY;
    /** @type {[string, HTMLElement][]} */
    const waiting = [];
    /** @type {[string, HTMLElement][]} */
    const ahead = [];
    for (const [part, element] of texts) {
      if (element.querySelector(":scope > .github-pull-plain") === null) {
        continue;
      }
      const box = boxOf(element);
      if (box !== null && box.width === 0 && box.height === 0) {
        // Not laid out, so not shown.
        continue;
      }
      if (top === null || box === null || box.top - top < height) {
        if (held.failed.has(part)) {
          held.parts.add(part);
        } else {
          waiting.push([part, element]);
        }
      } else if (!held.failed.has(part) && ahead.length < FIRST_SCREEN_AHEAD) {
        ahead.push([part, element]);
      }
    }
    return { waiting, ahead };
  }

  /**
   * The loading blocks, once they have shown: a held first paint keeps them over itself, since
   * taking them away first would blink the body empty. Blocks not shown yet go at once.
   *
   * @returns {HTMLElement | null}
   */
  function shownLoading() {
    const blocks = /** @type {HTMLElement | null} */ (
      body.querySelector(":scope > .mb-delayed-loading")
    );
    return blocks !== null &&
      typeof window.getComputedStyle === "function" &&
      window.getComputedStyle(blocks).visibility === "visible"
      ? blocks
      : null;
  }

  /**
   * Release a held first paint whose wait is over. A hidden one asks for the first screen's
   * plain texts it finds, at its start and each time a text lands, until none is left.
   */
  function settleFirstPaint() {
    const held = firstPaint;
    if (held === null) {
      return;
    }
    if (held.mode === "hidden") {
      const { waiting, ahead } = firstScreenPlain(held);
      for (const [part] of waiting) {
        held.parts.add(part);
      }
      // The screen's texts first, then those just past it, as the Markdown queue allows.
      for (const [part, element] of [...waiting, ...ahead]) {
        const value = textOf.get(element);
        if (value !== undefined) {
          controller.requestMarkdown(part, value);
        }
      }
      if (waiting.length > 0) {
        return;
      }
    } else if (!firstPaintReady()) {
      return;
    }
    // Unavailable only for a text it waited for: one past the screen may fail unseen.
    const failedWaited = [...held.failed].some((part) => held.parts.has(part));
    releaseFirstPaint(failedWaited || held.plain ? "unavailable" : "met");
  }

  /**
   * Show the held conversation now, as it is: its wait was met, its bound passed, or another
   * tab took the body. The span says how long it held and why it ended, so a round can count
   * holds that ran to their bound.
   *
   * @param {"met" | "bound" | "unavailable" | "closed"} outcome
   * @param {boolean} [reveal] False for the page's own cancellation: its body stays as the
   *   page that is replacing it found it, out of sight, until that one is ready.
   */
  function releaseFirstPaint(outcome, reveal = true) {
    const held = firstPaint;
    if (held === null) {
      return;
    }
    window.clearTimeout(held.timer);
    firstPaint = null;
    firstPaintSpent = true;
    if (reveal) {
      if (held.header && outcome !== "closed" && shown !== null) {
        // The header waited with the body: both change in this task, once.
        paintHeader(shown);
        paintStacks(shown);
      }
      body.classList.remove("github-pull-body-holding");
      held.cover?.remove();
    }
    mb.perf.measure("githubPull:firstPaintHold", () => {}, {
      number,
      heldMs: Date.now() - held.since,
      outcome,
      mode: held.mode,
      parts: held.parts.size,
    });
    if (outcome === "closed" || shown === null || listening.signal.aborted) {
      return;
    }
    const model = shown;
    if (held.mode === "delayed") {
      mb.perf.measure("githubPull:render", () => paint(model), { number });
    }
    painted(model);
  }

  function cancelTimeline() {
    if (commitTimeline?.read) {
      const { abort } = commitTimeline.read;
      commitTimeline.read = null;
      abort.abort();
    }
  }

  /** Timeline work follows an active Conversation with a full record. */
  function followTimeline() {
    const revision = shown?.recordRevision ?? null;
    const source = stackIdentity?.source ?? null;
    if (commitTimeline?.revision !== revision || commitTimeline.source !== source) {
      cancelTimeline();
      commitTimeline =
        revision !== null && source !== null
          ? {
              revision,
              source,
              projection: null,
              settled: false,
              cacheMiss: false,
              retryPending: false,
              read: null,
            }
          : null;
    }
    const held = commitTimeline;
    paintTimeline(held?.projection ?? null, source ?? "");
    if (
      !active ||
      listening.signal.aborted ||
      discussion === null ||
      held === null ||
      document.visibilityState !== "visible" ||
      !onPageRoute(window.location.pathname, number, "")
    ) {
      cancelTimeline();
      return;
    }
    const providerAllowed = controller.timelineAllowed();
    if (held.read && (held.read.cachedOnly || providerAllowed)) {
      return;
    }
    cancelTimeline();
    const retrying = held.retryPending;
    if (held.settled || (retrying && !providerAllowed)) {
      return;
    }
    // A held projection can paint during a stale metadata refresh. A cache miss waits
    // for settlement before it asks the provider.
    const cachedOnly = !providerAllowed;
    if (cachedOnly && (held.cacheMiss || (shown?.status !== "stale" && !shown?.refreshing))) {
      return;
    }
    const read = { cachedOnly, abort: new AbortController() };
    held.read = read;
    const owns = () =>
      commitTimeline === held &&
      held.read === read &&
      onPageRoute(window.location.pathname, number, "");
    const load = async () => {
      if (!owns()) {
        return;
      }
      if (!cachedOnly && !controller.timelineAllowed()) {
        followTimeline();
        return;
      }
      if (retrying) {
        // The retry budget is spent when the provider request starts, even if it is aborted.
        held.retryPending = false;
        held.settled = true;
      }
      // Commits join a conversation that is already shown, so the age line breathes for
      // them as for a refresh; nothing spins in the description card.
      const settleBusy = () => {
        if (timelineBusy) {
          timelineBusy = false;
          paintRefreshing(shown);
        }
      };
      if (!cachedOnly) {
        timelineBusy = true;
        paintRefreshing(shown);
        read.abort.signal.addEventListener("abort", settleBusy, { once: true });
      }
      /** @type {TimelineProjection | null} */
      let projection = null;
      try {
        const response = await fetch(TIMELINE_ROUTE, {
          method: "POST",
          headers: { "content-type": "application/json" },
          cache: "no-store",
          body: JSON.stringify({
            number,
            record_revision: held.revision,
            ...(cachedOnly ? { cached_only: true } : {}),
          }),
          signal: read.abort.signal,
        });
        if (response.status === 200 && owns()) {
          projection = readTimelineProjection(await response.json(), held.revision);
        }
      } catch {
        // The held discussion is already readable when the optional projection fails.
      } finally {
        if (!cachedOnly) {
          settleBusy();
        }
      }
      if (!owns()) {
        return;
      }
      held.read = null;
      if (
        projection !== null &&
        projection.state !== "unavailable" &&
        (held.projection === null ||
          projection.state === "complete" ||
          projection.events.length > held.projection.events.length)
      ) {
        const first = held.projection === null;
        const next = projection;
        held.projection = next;
        mb.perf.measure("githubPull:timelinePaint", () => paintTimeline(next, held.source), {
          number,
        });
        if (first) {
          mb.perf.measure("githubPull:timelineReady", () => {}, { number });
        }
      }
      if (cachedOnly && held.projection === null) {
        held.cacheMiss = true;
        followTimeline();
      } else if (!cachedOnly && !retrying && projection?.retryable) {
        held.retryPending = true;
        followTimeline();
      } else {
        held.settled = true;
        if (held.projection === null) {
          // This record has no projection, so the rows an earlier one placed are not its own.
          retireRows();
        }
      }
    };
    if (retrying) {
      const timer = window.setTimeout(() => void load(), TIMELINE_RETRY_MS);
      read.abort.signal.addEventListener("abort", () => window.clearTimeout(timer), { once: true });
    } else if (typeof window.requestAnimationFrame === "function") {
      let frame = window.requestAnimationFrame(() => {
        frame = window.requestAnimationFrame(() => void load());
      });
      read.abort.signal.addEventListener("abort", () => window.cancelAnimationFrame(frame), {
        once: true,
      });
    } else {
      const timer = window.setTimeout(() => void load(), 0);
      read.abort.signal.addEventListener("abort", () => window.clearTimeout(timer), { once: true });
    }
  }

  /**
   * What follows a paint: the commits it may read, and once no first paint is held, the
   * page's readiness and its milestones. A held first paint that can paint now does, and
   * comes back here once.
   *
   * @param {PullModel} model
   */
  function painted(model) {
    followTimeline();
    if (firstPaint !== null) {
      settleFirstPaint();
      return;
    }
    if (model.contentReady) {
      resolveReady();
    }
    if (!listening.signal.aborted && shown === model && model.pull !== null && model.tab === "") {
      // DOM readiness is not a painted milestone; the browser probe observes that boundary.
      mb.perf.measure("githubPull:descriptionReady", () => {}, {
        number,
        preview: model.corePreview,
      });
      if (!model.corePreview) {
        mb.perf.measure("githubPull:conversationReady", () => {}, { number });
      }
    }
  }

  // Disposing a page ends its work: a superseded page's requests are cancelled, whatever
  // answer they were waiting for, and its listeners go with them.
  const listening = new AbortController();
  // The tab keys end with it too: cancelPending() aborts the signal. A page the shell
  // stages for a retained navigation is inert, so its keys wait until it is shown.
  tabKeys = attachTabKeys(mb.shortcuts, tabLinks, (tab) => page.setTab(tab), listening.signal);
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
            decoded = await mb.perf.measureAsync("githubPull:decode", () => response.json(), {
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
          verified: response.headers.get(VERIFIED_HEADER),
        };
      },
      schedule: (callback, delayMs) => window.setTimeout(callback, delayMs),
      cancel: (handle) => window.clearTimeout(/** @type {number} */ (handle)),
      now: () => Date.now(),
      isVisible: () => document.visibilityState === "visible",
      isOnline: () => navigator.onLine !== false,
      formatTime: (iso) => exact(Date.parse(iso)),
      ownsChanges: () => onPageRoute(window.location.pathname, number, "files"),
      ownsConversation: () =>
        active &&
        mb.sourceKind() === "filesystem" &&
        onPageRoute(window.location.pathname, number, ""),
      scheduleComparison(callback) {
        /** @type {(() => void) | undefined} */
        let cancelIdle;
        // Wait until the reader stops on this page, as with a stale metadata refresh.
        const timer = window.setTimeout(() => {
          cancelIdle = mb.whenIdle(callback);
        }, REFRESH_ASK_MS);
        return () => {
          window.clearTimeout(timer);
          cancelIdle?.();
        };
      },
      render(model, identity) {
        stackIdentity = identity;
        mb.perf.measure("githubPull:render", () => paint(model), { number });
        painted(model);
      },
      reload: () => window.location.reload(),
      navigate: (href) => window.location.assign(href),
      renderMarkdown,
      listed: listedState,
      textUnavailable(part, text) {
        // A text a held first paint waits for will not come: it shows plain, and waits no longer.
        const held = firstPaint;
        if (held?.mode === "delayed" && part === "body" && held.text === text) {
          held.plain = true;
        } else if (held?.mode === "hidden") {
          // Only for the text the part shows now: a newer record's text is asked again.
          const element = texts.get(part);
          if (element !== undefined && textOf.get(element) === text) {
            held.failed.add(part);
          }
        }
        settleFirstPaint();
      },
      timelineStateChanged: followTimeline,
    },
    {
      number,
      tab: typeof ctx.tab === "string" ? ctx.tab : "",
      reader: ctx.reader ?? null,
      checkoutHead: mb.sourceKind() === "filesystem" ? (mb.repository?.revision ?? null) : null,
    },
  );
  document.addEventListener(
    "visibilitychange",
    () => {
      controller.onVisibilityChange();
      followTimeline();
      // A page opened behind another tab is not prefetched until it is looked at: the
      // wish is not recorded while hidden, so it is asked again when shown.
      if (document.visibilityState === "visible" && shown?.tab === "") {
        const comparison = shown?.comparison ?? null;
        if (comparison !== null) {
          prefetch.want(comparison);
        }
      }
    },
    { signal: listening.signal },
  );
  // The browserless sessions' window has no event target; a browser's always does.
  for (const type of ["online", "offline"]) {
    window.addEventListener?.(type, () => controller.onConnectivityChange(), {
      signal: listening.signal,
    });
  }
  const stacks = watchStacks((index) => {
    stackIndex = index;
    if (shown !== null && !listening.signal.aborted) {
      paintStacks(shown);
    }
  });
  void controller.start();
  /** @type {ReturnType<typeof keepPlace> | null} */
  let place = null;
  function activate() {
    if (listening.signal.aborted || active) {
      return;
    }
    active = true;
    followTimeline();
    controller.fetchIdleChanges();
    if (pane === null) {
      return;
    }
    place = keepPlace(pane, body, () => shown?.tab ?? "", number);
    place.keeper.land();
  }

  /** Stop ownership-bound work while preserving this page's inert handoff DOM. */
  function cancelPending() {
    releaseFirstPaint("closed", false);
    resolveReady();
    filesRefresh = null;
    wantedFile = null;
    listening.abort();
    cancelTimeline();
    body.querySelector(".github-pull-diff-loading")?.remove();
    observer?.disconnect();
    place?.dispose();
    controller.dispose();
    prefetch.dispose();
    stacks.dispose();
    for (const menu of stackMenus.values()) {
      menu.dispose();
    }
    stackMenus.clear();
    cancelCurrentFileBridge();
    unwatchCurrentFile?.();
    unwatchCurrentFile = null;
    diffHandle?.cancelPending?.();
    currentFileListeners.clear();
  }
  const page = Object.freeze({
    ready,
    activate,
    cancelPending,
    /** Whether the displayed PR has authoritative membership for stack navigation. */
    hasStack: () => currentStack() !== null,
    /** Move toward the base (-1) or top (+1), preserving the active PR tab.
     * Endpoints consume the command without navigating to an unrelated row.
     * @param {-1 | 1} delta
     */
    moveStack(delta) {
      const stack = currentStack();
      if (stack === null) {
        return false;
      }
      const at = stack.pulls.indexOf(number) + delta;
      if (at >= 0 && at < stack.pulls.length) {
        void open(memberRoute(stack.pulls[at], controller.snapshot().tab));
      }
      return true;
    },
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
     * *settling* is a walk's: Changes shows what the address it will settle on asks for,
     * until the route confirms the tab or `walkCancelled` says it will not.
     *
     * @param {string} path
     * @param {{settling?: boolean}} [how]
     * @returns {import("../diff/diff-view.js").FileJump | {kind: "no_diff", path: string}}
     */
    showFile(path, how = {}) {
      place?.keeper.readerMoved();
      const settling = how.settling === true;
      // A walk's every key repeats its claim, which would change nothing but cost a model.
      // Only Changes can be settling, so a repeated claim is already on it.
      if (!(settling && controller.snapshot().settling)) {
        controller.setTab("files", { settling });
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
    /** A walk that showed a file with *settling* stopped without moving the address there. */
    walkCancelled() {
      controller.walkCancelled();
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
      cancelPending();
      disposeDiff();
    },
  });
  return page;
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
