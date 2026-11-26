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
// (`POST /api/source/pin`, through the diff plugin's one switch), the tab, and the Markdown
// of each text, asked for one part at a time from
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
// class, id, data, style, or event attribute survives, but for the image fallback's own,
// nor any SVG, media, stylesheet, frame, form, or input but a disabled checkbox in the
// shape of a task list's box, wherever the text writes one; an image written in full over
// https is kept, with no referrer sent, unless the reader has turned that off, and any
// other is its alt text in a chip inside its link; a link is made absolute against the
// pull request's github.com page, kept only for http(s), and opened in a new tab with
// rel="noopener noreferrer"; and no KPress script is loaded for a text, but for one with a
// Mermaid block (a `pre` keeps `lang="mermaid"`), KPress's diagram modules, which draw
// each block as an image laid out in a frame whose policy loads nothing
// (`drawTextDiagrams`). KPress's stylesheets are, the route's one fixed list, and the page
// sets the rebuilt nodes in a KPress article of its own making, so a text reads as the
// same Markdown in a file does.

import {
  comparisonKey,
  createComparisonPrefetch,
  diffComparisonLoader,
} from "./comparison-prefetch.js";
import {
  rateLimitText,
  refreshFailureText,
  refreshRefusedText,
  setupHelp,
  unavailableText,
} from "./copy.js";
import { CHANGES_DRAWING, citedPullComparison, DOCS_DRAWING, DOCS_GROUP } from "./diff-drawing.js";
import {
  GUIDE_DOCUMENT_HOLD_MS,
  GUIDE_INTRODUCTION_HOLD_MS,
  guideAsks,
  guideReads,
} from "./guide-reads.js";
import {
  createStackIndex,
  memberRoute,
  namedStackPosition,
  stackEntries,
  stackLabel,
  stackMembership,
  stackMenuOrder,
  stackPosition,
  stackPositionHint,
  WHOLE_STACK,
  watchStacks,
} from "./pull-stacks.js";
import {
  displayState,
  listedAnywhere,
  listedState,
  noteRecord,
  PULL_STATES,
  pullStateIcon,
  withListedState,
} from "./pull-state.js";
import { briefLine, createSummaryBrief, PULL_FILES_SUMMARY_ROUTE } from "./pull-summary-brief.js";
import { stackMemberRow } from "./stack-member-row.js";

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
// A Mermaid block in a text's Markdown: the inert allowlist reduces KPress's figure to
// GitHub's own fallback markup and keeps that one language (src/metabrowser/inert_html.py).
const TEXT_DIAGRAM = 'pre[lang="mermaid"]';
// How long a conversation's first paint waits, out of sight, for the Markdown of the texts
// its first screen shows, so each is final when it first shows; kept renders wait for
// nothing. A core preview's first paint waits for its description the same way. Past this
// the page shows, each text still waiting a placeholder until its Markdown comes, and never
// its source (`showPending`). A page replacing another keeps that one on screen meanwhile.
// Measured 2026-11-12 in headless Chrome 152 against a local server on this repository, from
// the hold's `githubPull:firstPaintHold` span, each pull request clicked from the previous
// conversation scrolled by 1,500 px, two documents of five, load average 4 to 7: 23 to 155 ms
// (median 34, n 10), the 100 and 155 ms holds being a document's first pull request, which also
// loads `inert-html` and KPress's stylesheets; every one waited for one text, the description
// filling the first screen. None reached this bound. A first screen of several texts waits a
// round trip per `MARKDOWN_CONCURRENCY` texts: three texts at 40 ms an answer held 84 to 86 ms
// in a scratch page (review D), so a cold document's first page with several texts leaves less
// room than these figures. The exp-065 pilot also waited for a `cached_only` timeline read,
// which ran to the bound, so commits no longer hold the paint.
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
// The least a probe ask waits after the last one answered. Asks recur every
// `probe_every_s` from when each was sent, so an answer slower than that interval would
// otherwise be followed by the next ask at once, back to back for as long as answers are
// slow. It is a choice: a second is short beside the interval and long beside a request.
export const PROBE_ASK_GAP_MS = 1000;
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
// The key of what an entry's diff, on Changes or Docs, last showed (`rememberedChanges`),
// beside its place.
const CHANGES_KEY = "pullChanges";

// How long an idle browser may take before Files changed is fetched anyway. A page rendering
// its conversation is not idle, and the comparison should not wait for all of it.
export const PREFETCH_IDLE_TIMEOUT_MS = 300;
// Pull requests' sizes, by their size route, kept for the document: a route names two
// immutable commits, so its size never changes. Bounded as a Pulls window's rows are; each
// entry is two numbers.
const KEPT_PULL_SIZES_LIMIT = 256;
/** @type {Map<string, {pushed_bytes: number | null, diff_bytes: number | null}>} */
const KEPT_PULL_SIZES = new Map();

/**
 * @param {string} route
 * @param {{pushed_bytes: number | null, diff_bytes: number | null}} size
 */
function keepPullSize(route, size) {
  KEPT_PULL_SIZES.delete(route);
  KEPT_PULL_SIZES.set(route, size);
  while (KEPT_PULL_SIZES.size > KEPT_PULL_SIZES_LIMIT) {
    const oldest = KEPT_PULL_SIZES.keys().next();
    if (oldest.done) {
      break;
    }
    KEPT_PULL_SIZES.delete(oldest.value);
  }
}

/**
 * A comparison's file count, from the manifest of what was read of it, or null.
 *
 * @param {unknown} raw
 * @returns {number | null}
 */
export function manifestFiles(raw) {
  const files = /** @type {{manifest?: {totals?: {files?: unknown}}} | null} */ (raw)?.manifest
    ?.totals?.files;
  return typeof files === "number" && Number.isInteger(files) && files >= 0 ? files : null;
}

const PULL_ROUTE = "/api/plugin/github/pull";
const REFRESH_ROUTE = "/api/plugin/github/pull-refresh";
// The repository's list of pull requests, whose scan says which records GitHub changed.
const CATALOG_REFRESH_ROUTE = "/api/plugin/github/pulls-refresh";
const LABELS_REFRESH_ROUTE = "/api/plugin/github/labels-refresh";
// How the server says, on a 200 and a 304 alike, when the record was last checked and how.
const VERIFIED_HEADER = "x-metabrowser-verified";
const MARKDOWN_ROUTE = "/api/plugin/github/pull-markdown";
const TIMELINE_ROUTE = "/api/plugin/github/pull-timeline";
// Give a transient queue or provider failure one chance to clear while the reader stays.
export const TIMELINE_RETRY_MS = 1000;
// The longest wait the server may name for a timeline its budget refused (`retry_after_s`,
// HELD_RETRY_S in pull_timeline.py): the schema's own bound, an hour.
const TIMELINE_HELD_MAX_S = 3600;
// Guided Review leads, when the description carries a guide: it is the author's reading order.
export const TABS = Object.freeze(["guided", "", "conversation", "docs", "files", "checks"]);
/** How far a title may overhang its two-line box and still be whole: its descenders. */
const TITLE_OVERHANG_PX = 4;
/**
 * Each tab's label and key, in `TABS` order. Conversation, the default, keeps its C, and
 * Docs its D. Guided Review takes the R of gui-ded P-*r*, a review's letter, since Docs holds
 * D. The other two also start with C, so they take a free letter of their label:
 * chan-*g*es, and ch-*e*-cks, whose H is the Commits tab's (History) and whose K moves a
 * row up (docs/design-system.md, "Keyboard Shortcuts"). `C` is also the Charts tab's,
 * which is never shown beside a page.
 */
const PULL_TABS = Object.freeze([
  Object.freeze({ id: "guided", label: "Guided Review", key: "r" }),
  Object.freeze({ id: "", label: "Conversation", key: "c" }),
  Object.freeze({ id: "docs", label: "Docs", key: "d" }),
  Object.freeze({ id: "files", label: "Changes", key: "g" }),
  Object.freeze({ id: "checks", label: "Checks", key: "e" }),
]);
// A cheap tab visibility hint, which does not parse: the server's Markdown parser decides if a
// guide exists, and counts only a top-level fence, so a description that shows the format inside
// another fence gets a tab that says there is no guide (arch-github-pull-requests.md, "Guided Review").
const GUIDED_FENCE = /^ {0,3}(?:`{3,}|~{3,})[ \t]*guided-review[ \t]*$/m;
// The same hint for a native stack's guide, a `stack-review` block, which the stack's page
// reads (`stack_guided_review` in guided_review.py) and Conversation names in its place.
const STACK_GUIDE_FENCE = /^ {0,3}(?:`{3,}|~{3,})[ \t]*stack-review[ \t]*$/m;

/**
 * The tab a route shows, by its id in `PULL_TABS`. `/pull/<n>` is the pull request's front
 * page: Guided Review when the description has a guide, by the same hint the tab bar reads,
 * and Conversation otherwise. `/pull/<n>/conversation` names Conversation, whose id is "",
 * so a guided pull request's Conversation has an address that always shows it.
 *
 * @param {string} route The route's tab: "", "conversation", or another tab's id.
 * @param {string | null} description The description, or null before the record.
 * @returns {string}
 */
export function shownTabFor(route, description) {
  if (route === "conversation") {
    return "";
  }
  if (route === "") {
    return GUIDED_FENCE.test(description ?? "") ? "guided" : "";
  }
  return route;
}

/**
 * The tab a stack move keeps: the same tab on the next pull request, except that Guided Review
 * goes to its front page, which is its guide when it has one and Conversation otherwise.
 *
 * @param {string} tab The tab on screen.
 */
export function stackTab(tab) {
  return tab === "guided" ? "" : tab;
}

/**
 * The route that shows a tab: the front page's address for the tab the front page shows,
 * so its link and key go to the page already on screen rather than to a second entry of it,
 * and Conversation's is `/pull/<n>/conversation` when the front page is Guided Review
 * (`shownTabFor`).
 *
 * @param {string} id The tab's id in `PULL_TABS`.
 * @param {string | null} description
 * @returns {string}
 */
export function routeForTab(id, description) {
  const front = shownTabFor("", description);
  if (id === front) {
    return "";
  }
  return id === "" ? "conversation" : id;
}

/**
 * Whether *tab* shows the pull request's diff: Changes, every changed file, or Docs, its
 * documents alone (`DOCS_GROUP`). Both read the comparison themselves and own its fetch.
 *
 * @param {string | undefined} tab
 */
export function diffTab(tab) {
  return tab === "files" || tab === "docs";
}

/**
 * Whether a diff document lists no changed file, and its list was not cut short at its
 * bounds: a Docs tab with no document to show.
 *
 * @param {unknown} document_
 */
export function noFiles(document_) {
  const manifest = /** @type {{manifest?: {files?: unknown, truncated?: unknown}} | null} */ (
    document_
  )?.manifest;
  return (
    Array.isArray(manifest?.files) && manifest.files.length === 0 && manifest.truncated !== true
  );
}

/**
 * Whether a comparison's File type counts (the diff route's `view=types`) say it changes a
 * document: its `docs` preset row, the group the Docs tab shows. Null where the answer does
 * not say, and where it counts none of a list cut short at its bounds, which may have left
 * its documents out.
 *
 * @param {unknown} counts
 * @returns {boolean | null}
 */
export function changesDocuments(counts) {
  const answer = /** @type {{type_presets?: unknown, truncated?: unknown} | null} */ (counts);
  const rows = answer?.type_presets;
  if (!Array.isArray(rows)) {
    return null;
  }
  const row = rows.find((entry) => Array.isArray(entry) && entry[0] === "docs");
  if (!Array.isArray(row) || typeof row[1] !== "number") {
    return null;
  }
  if (row[1] > 0) {
    return true;
  }
  return answer?.truncated === true ? null : false;
}

/** @type {Readonly<Record<string, string>>} */
const ABSENCE = Object.freeze({
  not_github: "This server serves no GitHub repository.",
  not_cached: "This pull request has not been fetched yet.",
  schema_mismatch: "The saved copy of this pull request is from another version.",
  unreadable: "The saved copy of this pull request could not be read.",
});

/**
 * What the page says of a refresh's outcome that it words itself, beside copy.js's shared
 * words, and of any other, in one sentence each beside Retry. The job's own message stays
 * in the envelope's `last_refresh.message`, and the failure's Details shows what the event
 * log holds of it.
 * @type {Readonly<Record<string, string>>}
 */
const REFRESH_FAILURES = Object.freeze({
  not_found_or_private: "GitHub could not find this pull request, or this account cannot read it.",
  lender_missing: "The checkout cannot supply these changes.",
});
const REFRESH_FAILED = "Could not refresh this pull request.";

/**
 * A review's state, said by a chip after its heading where the verb does not say it
 * (mb-novh): every review's heading reads "author reviewed age", as a comment's reads
 * "author commented age", and Approved, Changes requested, and Dismissed are the review's
 * own states, as GitHub marks them. A plain review (COMMENTED) is all in its verb, and a
 * pending one in its "(pending)", so neither has a chip. A state GitHub adds later is
 * shown as itself.
 *
 * @type {Readonly<Record<string, string | null>>}
 */
const REVIEW_STATES = Object.freeze({
  APPROVED: "approved",
  CHANGES_REQUESTED: "changes requested",
  COMMENTED: null,
  DISMISSED: "dismissed",
  PENDING: null,
});

/** @type {Readonly<Record<string, string>>} */
const MERGEABLE = Object.freeze({
  mergeable: "No conflicts with the base branch.",
  conflicting: "Conflicts with the base branch.",
  unknown: "Merge status unknown.",
});

/** @type {Readonly<Record<string, string>>} */
const UNAVAILABLE = Object.freeze({
  check_runs: "check runs",
  status: "commit statuses",
  comparison: "changes",
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
 *   verified_by?: "catalog" | "fetch" | "probe" | null,
 *   head_moved?: boolean,
 *   checks_pending?: boolean,
 *   fresh_for_s: number,
 *   probe_every_s: number | null,
 *   record_revision: string | null,
 *   refreshing: boolean,
 *   preparing_comparison?: true,
 *   last_refresh: {outcome: string, message: string | null, reset_at: string | null, at: string} | null,
 *   comparison_route: string | null,
 *   image_route: string | null,
 *   rendered_route?: string | null,
 *   record: Record<string, any> | null,
 *   core_preview: {source: string, number: number, reader: string, observed_at: string,
 *     revision: string, pull: Record<string, any>, comparison_state: "pending" | "no_store" | "not_started"} | null,
 *   repository_labels?: RepositoryLabel[],
 *   labels_pending?: boolean,
 *   no_store?: true,
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
 *   review: {state: string, label: string | null} | null,
 * }} TimelineItem
 */

/**
 * @typedef {{kind: "commit", oid: string, subject: string, committed_at: string | null}} TimelineCommit
 * @typedef {{kind: "comment" | "review", id: string} | TimelineCommit} TimelineEvent
 * @typedef {{state: "complete" | "partial" | "unavailable", events: TimelineEvent[], retryable: boolean, heldMs: number | null}} TimelineProjection
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
 * serves this pull request's head, by its commit and under its ref. `at` is the full ID of the
 * commit that opens, which a tooltip names short (`mb.shortCommit`).
 *
 * @typedef {{kind: "link", at: string} | {kind: "switch", ref: string, head: string, at: string}} BrowseCode
 */

/**
 * @typedef {{
 *   number: number,
 *   tab: string,
 *   status: "loading" | "absent" | "pending" | "current" | "stale" | "unavailable",
 *   recordRevision: string | null,
 *   textRevision: string | null,
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
 *   failureAt?: string | null,
 *   failureHelp?: "install" | "update",
 *   failureHold?: true,
 *   refreshFailed: boolean,
 *   pull: null | {
 *     title: string, number: number, state: import("./pull-state.js").PullState, stateLabel: string, author: string,
 *     avatar: string | null, actorAvatar: string | null, baseRef: string, headRef: string,
 *     baseRepository: string | null, headRepository: string | null, headSha: string,
 *     actor: string | null, action: string,
 *     base: string, head: string, htmlUrl: string, created: string, updated: string,
 *     closed: string | null, closedLabel: string | null, labels: PullLabel[],
 *     merge: {state: string, label: string} | null, text: string, truncated: boolean,
 *     commits: number | null,
 *   },
 *   timeline: TimelineItem[],
 *   reviewComments: ReviewCommentItem[],
 *   checks: {counts: Record<string, number>, items: CheckItem[]} | null,
 *   checkNotes: string[],
 *   notes: string[],
 *   comparison: {left: string, right: string, route?: string, image_route?: string, rendered_route?: string, size_route?: string, branch: {ref: string | null} | null} | null,
 *   comparisonComing: boolean,
 *   head: string | null,
 *   baseRef: string | null,
 *   browse: BrowseCode | null,
 *   filesUnavailable: string,
 *   changesPending: boolean,
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

/**
 * A freshness note as wide as its age makes it: its age put at the widest `relativeAge`
 * says, "59 min ago", so the note's slot is that wide whatever the age reads (mb-ne91). An
 * age wider still, "at an unknown time", sizes its own note. Exported for
 * tests/dom/github-pull-page-mount-behavior.js, whose golden records what it gives.
 *
 * @param {string} note
 */
export function widestNote(note) {
  const widest = note.replace(/just now|\d+ (?:min|h|d) ago/, "59 min ago");
  return widest.length >= note.length ? widest : note;
}

/**
 * When a rate limit's hold lifts, as the note says it in the freshness note's place: a time
 * of day in the locale's short form when it lifts today, "2:05 PM", and otherwise a short
 * date and time, "11/19/26, 2:05 PM" (B3 of review B on #506). The whole timestamp the page
 * prints elsewhere, "11/18/2026, 2:05:00 PM", left the hold 120 px wider than the age it
 * replaces, so it left the author's row from 640 px down. *locale* and *timeZone* default to
 * the reader's; a session passes its own so what it prints does not depend on the machine.
 *
 * @param {number} liftMs
 * @param {number} nowMs
 * @param {string} [locale]
 * @param {string} [timeZone]
 */
export function holdLiftText(liftMs, nowMs, locale = undefined, timeZone = undefined) {
  const day = new Intl.DateTimeFormat(locale, {
    timeZone,
    year: "numeric",
    month: "numeric",
    day: "numeric",
  });
  const today = day.format(liftMs) === day.format(nowMs);
  return new Intl.DateTimeFormat(
    locale,
    today ? { timeZone, timeStyle: "short" } : { timeZone, dateStyle: "short", timeStyle: "short" },
  ).format(liftMs);
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

/**
 * A label as the header draws it. `color` is GitHub's six hex digits, or null for a label
 * drawn neutral; `style` is the custom properties github/styles.css paints a colored chip
 * from; `tip` is the label's description, its chip's tooltip, or null for none.
 * @typedef {{name: string, color: string | null, style: string | null, tip: string | null}} PullLabel
 */

/**
 * The custom properties github.com sets on a label for its stylesheet's formula: the
 * color's red, green, and blue, 0 to 255, and its hue in degrees and saturation and
 * lightness in percent, each rounded to a whole number as github.com rounds them: these are
 * the values github.com set on each of 112 colors of six public repositories' labels
 * (tests/fixtures/github-label-colors.json, read 2026-11-15). Null for anything but six hex
 * digits.
 *
 * @param {unknown} color
 * @returns {string | null}
 */
export function labelColorProperties(color) {
  if (typeof color !== "string" || !/^[0-9a-fA-F]{6}$/.test(color)) {
    return null;
  }
  const [r, g, b] = [0, 2, 4].map((at) => Number.parseInt(color.slice(at, at + 2), 16));
  const [red, green, blue] = [r, g, b].map((channel) => channel / 255);
  const max = Math.max(red, green, blue);
  const min = Math.min(red, green, blue);
  const chroma = max - min;
  const lightness = (max + min) / 2;
  let hue = 0;
  let saturation = 0;
  if (chroma > 0) {
    saturation = chroma / (1 - Math.abs(2 * lightness - 1));
    const sector =
      max === red
        ? ((green - blue) / chroma) % 6
        : max === green
          ? (blue - red) / chroma + 2
          : (red - green) / chroma + 4;
    hue = sector * 60;
    if (hue < 0) {
      hue += 360;
    }
  }
  const [h, s, l] = [hue, saturation * 100, lightness * 100].map(Math.round);
  return `--github-label-r:${r};--github-label-g:${g};--github-label-b:${b};--github-label-h:${h};--github-label-s:${s};--github-label-l:${l}`;
}

/**
 * A label's chip, our chip's size: a label with GitHub's color carries it, and the custom
 * properties github/styles.css paints it from, and one with a description has it as its
 * tooltip, which says what the name does not (docs/design-system.md, "Label Colors").
 *
 * @param {PullLabel} label
 */
export function labelChip(label) {
  /** @type {Record<string, string>} */
  const attributes = { class: "github-pull-label" };
  if (label.color !== null && label.style !== null) {
    attributes["data-color"] = label.color;
    attributes.style = label.style;
  }
  if (label.tip !== null) {
    attributes["data-tip-text"] = label.tip;
  }
  return h("span", attributes, [label.name]);
}

/**
 * A label of the repository's set, as the pull envelope's `repository_labels` names it.
 * @typedef {{name: string, color: string | null, description: string | null}} RepositoryLabel
 */

/**
 * The repository's labels the envelope carries, by name: those its record or core names
 * without a color, as one cached before label colors does (`mb-varu`).
 *
 * @param {unknown} entries
 * @returns {Map<string, RepositoryLabel>}
 */
function knownLabels(entries) {
  /** @type {Map<string, RepositoryLabel>} */
  const known = new Map();
  for (const entry of list(entries)) {
    if (entry !== null && typeof entry === "object" && typeof entry.name === "string") {
      known.set(entry.name, {
        name: entry.name,
        color: typeof entry.color === "string" ? entry.color : null,
        description: typeof entry.description === "string" ? entry.description : null,
      });
    }
  }
  return known;
}

/**
 * Whether the record or core the envelope shows names a label without a usable color that
 * `repository_labels` has no entry for, as a record cached before label colors does while
 * the repository's set lacks it (`mb-varu`).
 *
 * @param {PullEnvelope} envelope
 * @returns {boolean}
 */
function labelsMissing(envelope) {
  const pull = envelope.record !== null ? envelope.record.pull : envelope.core_preview?.pull;
  const known = knownLabels(envelope.repository_labels);
  return list(pull?.labels).some((value) => {
    const label =
      value !== null && typeof value === "object"
        ? /** @type {Record<string, unknown>} */ (value)
        : {};
    return labelColorProperties(label.color) === null && !known.has(text(label.name));
  });
}

/**
 * A label with its own color is drawn as it is; one named without a color takes the
 * repository's color and description for that name, so its chip is colored on first paint
 * whenever the repository's labels are cached.
 *
 * @param {unknown} value
 * @param {ReadonlyMap<string, RepositoryLabel>} [known]
 * @returns {PullLabel}
 */
export function describeLabel(value, known = new Map()) {
  const label =
    value !== null && typeof value === "object"
      ? /** @type {Record<string, unknown>} */ (value)
      : {};
  const name = text(label.name);
  const own = labelColorProperties(label.color);
  const repository = own === null ? known.get(name) : undefined;
  const color = own !== null ? label.color : repository?.color;
  const style = own ?? labelColorProperties(color);
  const description = text(label.description) || text(repository?.description);
  return {
    name,
    color: style === null ? null : text(color).toLowerCase(),
    style,
    tip: description.trim() ? description : null,
  };
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
      review: {
        state,
        label: Object.hasOwn(REVIEW_STATES, state) ? REVIEW_STATES[state] : state.toLowerCase(),
      },
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
  const retryable = state !== "complete" && answer.retryable === true;
  const wait = answer.retry_after_s;
  // The budget refused the read: the server says how long to wait before asking again.
  const heldMs =
    retryable &&
    state === "unavailable" &&
    typeof wait === "number" &&
    Number.isInteger(wait) &&
    wait >= 1 &&
    wait <= TIMELINE_HELD_MAX_S
      ? wait * 1000
      : null;
  return { state, events, retryable, heldMs };
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

/**
 * "a", "a and b", or "a, b, and c".
 *
 * @param {string[]} words
 */
function joinedWords(words) {
  return words.length < 3
    ? words.join(" and ")
    : `${words.slice(0, -1).join(", ")}, and ${words.at(-1)}`;
}

/**
 * The one note over the conversation, or over the checks, when part of it is missing or
 * cut short: at most one sentence, never one per part. A part that could not be read at
 * all outweighs a list or text that was cut, which still shows what it holds. Why a part
 * could not be read stays in the record's `unavailable`, and Files changed says why its
 * Changes are missing (`filesUnavailableText`).
 *
 * @param {Record<string, any>} record
 * @param {boolean} forChecks
 * @returns {string[]}
 */
function notes(record, forChecks) {
  const truncated = record.truncated ?? {};
  const checkPart = (/** @type {string} */ name) =>
    name === "check_runs" || name === "status" || name === "statuses";
  const missing = Object.entries(record.unavailable ?? {})
    .filter(
      ([part, why]) =>
        checkPart(part) === forChecks && !(part === "comparison" && why === "no_store"),
    )
    .map(([part]) => (Object.hasOwn(UNAVAILABLE, part) ? UNAVAILABLE[part] : "some details"));
  if (missing.length > 0) {
    const parts = joinedWords([...new Set(missing)]);
    return [`${parts.charAt(0).toUpperCase()}${parts.slice(1)} could not be loaded.`];
  }
  const cut = Object.keys(TRUNCATED).filter(
    (name) => checkPart(name) === forChecks && truncated[name] === true,
  );
  const textCut = !forChecks && truncated.text === true;
  if (cut.length > 0 && textCut) {
    return ["Only part of this conversation is shown."];
  }
  if (cut.length > 0) {
    return [`Only some ${joinedWords(cut.map((name) => TRUNCATED[name]))} are shown.`];
  }
  return textCut ? ["Some long text is shortened."] : [];
}

/**
 * What Files changed says in place of a diff, from the state the record names. Pure.
 *
 * One statement in a reader's terms, with the one remedy that can work. A merge base the
 * store's shallow history cannot settle is not a failure to read: the diff could be
 * computed and would be a guess, so the page shows none, and a refresh fetches the history
 * that settles it. The reason itself stays in the record's `unavailable.comparison`, which
 * docs/reviewing-pull-requests.md explains.
 *
 * @param {unknown} why The record's `unavailable.comparison`.
 * @returns {string}
 */
export function filesUnavailableText(why) {
  if (why === "base_uncertain") {
    return "Changes need more of this checkout’s history. Refresh to fetch it.";
  }
  if (why === "no_store") {
    return "Changes could not be fetched.";
  }
  if (why === "comparison_timeout") {
    return "Changes took too long to prepare. Refresh to try again.";
  }
  if (why === "comparison_too_large") {
    return "Changes are too large to show here. GitHub shows them.";
  }
  if (why === "commits_unavailable") {
    return "Changes need commits that are missing here. Refresh to fetch them.";
  }
  if (why === "no_merge_base") {
    return "Changes cannot be shown because this pull request’s branches share no history.";
  }
  return "Changes could not be shown.";
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
 * reader's Retry of Changes: GitHub's rate limit before it lifts, which the job's metadata
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
    diffTab(page.tab) &&
    page.ownsChanges !== false &&
    page.comparisonAttempted !== true &&
    envelope?.record?.unavailable?.comparison === "no_store" &&
    !comparisonHeld(envelope, page.nowMs)
  );
}

/**
 * The header sentence's action, a verb and the commits it moves: "wants to merge 1 commit",
 * "merged 6 commits", or the verb alone where the count is not known. A pull request's page
 * and a stack's say it alike (docs/design-system.md, "The Stack Page").
 *
 * @param {string} verb
 * @param {number | null} commits
 */
export function actionWords(verb, commits) {
  return commits === null ? verb : `${verb} ${commits} commit${commits === 1 ? "" : "s"}`;
}

/**
 * The header sentence's actors and action, a pull request's and a stack's alike: once merged,
 * its mergers, "merged 6 commits", and none where no merger is known, so the action is said
 * alone rather than crediting anyone; otherwise its authors, "wants to merge 1 commit", or
 * "want to merge" after two or more.
 *
 * @template T
 * @param {boolean} merged
 * @param {T[]} authors
 * @param {T[]} mergers
 * @param {number | null} commits
 * @returns {{actors: T[], action: string}}
 */
export function headerSentence(merged, authors, mergers, commits) {
  const actors = merged ? mergers : authors;
  const verb = merged ? "merged" : actors.length > 1 ? "want to merge" : "wants to merge";
  return { actors, action: actionWords(verb, commits) };
}

/**
 * The freshness note's words for a fetch *age* ago (`relativeAge`): "Fetched just now via
 * GitHub CLI", or, *offline* with nothing to refresh it, "Offline · fetched 3 h ago via GitHub
 * CLI". One time, never two (mb-ne91). A pull request's page says it of its record, and a
 * stack's of the oldest of its members' records.
 *
 * @param {string} age
 * @param {boolean} [offline]
 */
export function fetchedNote(age, offline = false) {
  return offline ? `Offline · fetched ${age} via GitHub CLI` : `Fetched ${age} via GitHub CLI`;
}

/** Header and description fields shared by a full record and a validated core preview.
 * @param {Record<string, any>} pull
 * @param {ReadonlyMap<string, RepositoryLabel>} [known] the repository's labels, by name,
 *   for a label the record names without a color
 * @returns {NonNullable<PullModel["pull"]>}
 */
function describeCore(pull, known = new Map()) {
  const crossRepository = pull.head?.repository !== pull.base?.repository;
  const state = displayState(pull);
  const merge = state === "open" || state === "draft" ? text(pull.mergeable) || "unknown" : null;
  const commits = typeof pull.commits === "number" ? pull.commits : null;
  // "<merger> merged 6 commits", and for an open, draft, or closed pull request
  // "<author> wants to merge 1 commit", with "<head> → <base>" on the branch line under it.
  // The verbs are github.com's; the branches read source → target, never github.com's
  // "into <base> from <head>" (docs/design-system.md, "Merge Direction"). An account GitHub
  // deleted is its "ghost"; a record that names no merger at all says only "merged 6
  // commits", rather than crediting anyone (`headerSentence`, which a stack's says too).
  const sentence = headerSentence(
    state === "merged",
    [who(pull.author)],
    typeof pull.merged_by === "string" && pull.merged_by ? [pull.merged_by] : [],
    commits,
  );
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
    baseRepository: text(pull.base?.repository) || null,
    headRepository: text(pull.head?.repository) || null,
    headSha: text(pull.head?.sha),
    actor: sentence.actors[0] ?? null,
    action: sentence.action,
    base: sideName(pull.base, crossRepository),
    head: sideName(pull.head, crossRepository),
    htmlUrl: text(pull.html_url),
    created: text(pull.created_at),
    updated: text(pull.updated_at),
    closed: state === "merged" ? pull.merged_at : state === "closed" ? pull.closed_at : null,
    closedLabel: state === "merged" ? "merged" : state === "closed" ? "closed" : null,
    labels: list(pull.labels).map((label) => describeLabel(label, known)),
    merge: merge === null ? null : { state: merge, label: MERGEABLE[merge] ?? MERGEABLE.unknown },
    // The header's size line opens with it (docs/design-system.md, "Change Size Line").
    commits,
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
 * *checkoutPin* marks a checkout's revision, which can open files at its own commit.
 *
 * The controller says what it will send. *fetchQueued* is a selected fetch not asked
 * for yet that the page will send once it is visible or the reader stops; *ownsChanges*
 * is whether the address names Changes, which an automatic comparison needs (see
 * `comparisonQueued`); *comparisonRefusal* is why the page's last comparison request
 * was refused, kept until it asks again. *refreshDue* is the page's own automatic refresh of
 * a stale record, scheduled or on its way; *online* is false when the browser reports no
 * network, and *formatHold* says when a rate limit lifts, `holdLiftText` in the reader's
 * locale where it is not given.
 *
 * Content already shown is never covered by progress: while a refresh runs or is about to,
 * `revalidating` says so, and the page breathes the age line instead of a spinner. The age is
 * the plain age. A stale record says why only when no refresh can run: offline, held by
 * GitHub's rate limit, or a failure the reader can retry.
 *
 * *listed* is what the repository's list said of this pull request, whose state is shown
 * when the list saw a later update than the record or preview did.
 *
 * `comparisonComing` is a comparison on its way that the page has none of yet, so the Diff
 * summary's row waits for it (mb-onr2), from the page's first paint (mb-30dz): before
 * anything is read, until a read fails; with no record or core, while the selected read
 * runs or will be sent, or the page waits for the reader to send it; a core preview while a
 * read that brings its record runs or will be sent, unless the server said it has no store
 * to compare in (`comparison_state: "no_store"`); and a record whose comparison is not in
 * the store and that the page asked the server to prepare, as Conversation's idle work does
 * (`preparing_comparison`) and Changes does while it fetches it. A pull request that is not
 * GitHub's, a server or core with no store (`no_store`), and a read that failed with nothing
 * running have none coming until Changes asks, so the placeholder never outlives its wait.
 *
 * `head` is the head commit the page knows, the one its Diff summary is drawn for: the
 * comparison's, else the record's or the core's, and null before either; `baseRef` is the
 * record's or the core's base branch.
 *
 * @param {{number: number, tab: string, nowMs: number, error?: string | null, errorFromComparison?: boolean, errorFromRefresh?: boolean, fetching?: boolean, fetchQueued?: boolean, refreshPending?: boolean, refreshDue?: boolean, online?: boolean, formatHold?: (liftMs: number, nowMs: number) => string, ownsChanges?: boolean, comparisonAttempted?: boolean, comparisonRefusal?: string | null, waitForReader?: boolean, checkoutHead?: string | null, checkoutPin?: boolean, listed?: {state: import("./pull-state.js").PullState, updatedAt: string} | null}} page
 * @returns {PullModel}
 */
export function describePull(envelope, page) {
  /** @type {PullModel} */
  const model = {
    number: page.number,
    tab: page.tab,
    status: "unavailable",
    recordRevision: null,
    textRevision: null,
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
    refreshFailed: false,
    pull: null,
    timeline: [],
    reviewComments: [],
    checks: null,
    checkNotes: [],
    notes: [],
    comparison: null,
    comparisonComing: false,
    head: null,
    baseRef: null,
    browse: null,
    filesUnavailable: filesUnavailableText(null),
    changesPending: false,
    checkoutAtHead: null,
    newCommits: null,
  };
  if (envelope === null) {
    // Nothing read yet: the page shows a skeleton, and an error once a read failed.
    model.status = page.error ? "unavailable" : "loading";
    // The first read brings the record, or the core whose read prepares its comparison, so
    // the Diff summary's row waits from the first paint rather than empty until the core.
    // Until it answers the page cannot know that the server has no store (`no_store`) or
    // serves no GitHub repository: on such a server the placeholder ends with that answer.
    model.comparisonComing = !page.error;
    return model;
  }
  model.status = envelope.state;
  model.refreshing =
    (envelope.refreshing && (diffTab(page.tab) || !envelope.preparing_comparison)) ||
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
    // Held, not failed: the time named is the one the page next asks at. It begins and
    // lifts by itself and asks nothing of the reader, so it keeps the row to one line.
    model.failureHold = true;
    model.failure = rateLimitText(
      Number.isFinite(heldUntil) ? (page.formatHold ?? holdLiftText)(heldUntil, page.nowMs) : null,
    );
  } else if (last !== null && last.outcome !== "succeeded" && !envelope.refreshing) {
    // The pull request shown stays, so the sentence says only what went wrong.
    model.failure = refreshFailureText(last.outcome, REFRESH_FAILURES, REFRESH_FAILED);
    // When it ended, which the failure's Details reads the event log around (mb-9zp5).
    model.failureAt = last.at ?? null;
    const help = setupHelp(last.outcome);
    if (help !== undefined) {
      model.failureHelp = help;
    }
  }
  // What Retry on the status row asks again for (mb-ablv): a refresh that failed, but not a
  // rate limit's hold, which lifts by itself, or a reader's refresh that was refused or
  // failed to reach the server.
  model.refreshFailed =
    (model.failure !== null && model.failureHold !== true) ||
    (Boolean(page.error) && page.errorFromRefresh === true);
  const record = envelope.record;
  if (record === null && envelope.core_preview !== null) {
    const preview = envelope.core_preview;
    model.pull = describeCore(
      withListedState(preview.pull, page.listed),
      knownLabels(envelope.repository_labels),
    );
    model.corePreview = true;
    model.textRevision = textRevision(envelope);
    model.head = text(preview.pull?.head?.sha) || null;
    model.baseRef = text(preview.pull?.base?.ref) || null;
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
    // or failed one leaves nothing running, which the navigation's Refresh then starts.
    model.changesPending =
      model.refreshing ||
      (diffTab(page.tab) && (page.fetching === true || page.fetchQueued === true));
    model.filesUnavailable = model.changesPending
      ? "Changes are still being prepared."
      : "Changes are unavailable because the full pull request could not be loaded.";
    // The record follows the core, and its comparison with it unless the server has no store;
    // a core read from the cache (`not_started`) has its record coming once a read runs.
    model.comparisonComing =
      preview.comparison_state !== "no_store" &&
      envelope.no_store !== true &&
      (envelope.refreshing || page.fetching === true || page.fetchQueued === true);
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
    // The selected read, running, still to be sent, or waiting for the reader, brings the
    // core and then the record; nothing running after a failure brings neither.
    model.comparisonComing =
      envelope.reason !== "not_github" &&
      envelope.no_store !== true &&
      (fetching || page.fetchQueued === true || page.waitForReader === true);
    model.canRefresh =
      !fetching &&
      envelope.state === "absent" &&
      envelope.reason !== "not_github" &&
      !envelope.refreshing;
    return model;
  }
  model.recordRevision = envelope.record_revision;
  model.textRevision = textRevision(envelope);
  model.contentReady = true;
  // A comparison's refusal is said where its Retry is, in the Changes body (below), not on
  // the header's status line, which then showed it on Changes alone and moved the tab bar
  // 27 px between tabs (B5 of review B on #506). Any other error is the header's, on every
  // tab, a refused Refresh's among them, whatever its words (C3 of review C).
  model.message = page.error && page.errorFromComparison !== true ? page.error : null;
  // A stale record the page is refreshing by itself offers nothing to press: Refresh is for a
  // failure, Changes, or a stale record whose automatic refresh did not run. A rate limit's
  // hold offers none either: the page names when it asks again and asks then, as the Pulls
  // tab's Refresh waits out the same hold, and a press would only meet the limit.
  model.canRefresh =
    !envelope.refreshing &&
    !model.revalidating &&
    !held &&
    (envelope.state !== "stale" || !offline) &&
    (envelope.state === "stale" ||
      model.failure !== null ||
      (diffTab(page.tab) &&
        typeof record.comparison?.base === "string" &&
        typeof record.comparison?.head === "string") ||
      (typeof record.unavailable?.comparison === "string" &&
        record.unavailable.comparison !== "no_store"));
  const age = relativeAge(record.fetched_at ?? null, page.nowMs);
  // The plain age while a refresh runs or is due: the page breathes it, and says nothing
  // about being out of date. Offline is the one stale state named here, since no refresh
  // can run; a hold or a failure is named by `failure`.
  // One time, never two (mb-ne91): the record's own fetch, the earliest that says how fresh
  // what is shown is. A later check of the repository's list that found nothing changed
  // (`verified_at`) makes the record no newer, so the line does not say it.
  model.freshness = fetchedNote(age, offline && envelope.state === "stale" && !model.revalidating);
  if (envelope.head_moved === true) {
    // The diff on screen stays until the reader takes the newer one, which a refresh offers.
    model.newCommits = model.revalidating
      ? "New commits were pushed; updating."
      : "New commits were pushed to this pull request.";
  }
  const pull = record.pull ?? {};
  model.pull = describeCore(
    withListedState(pull, page.listed),
    knownLabels(envelope.repository_labels),
  );
  model.timeline = timeline(record);
  model.reviewComments = reviewComments(record);
  model.checks = checks(record, model.pull.htmlUrl);
  model.checkNotes = notes(record, true);
  model.notes = notes(record, false);
  const head = text(pull.head?.sha);
  model.head = head || null;
  model.baseRef = text(pull.base?.ref) || null;
  const headRef = `refs/pull/${pull.number}/head`;
  // The PR's head ref belongs to a mirror. A checkout can link to a PR
  // head that it is already serving.
  const canOpenHead = page.checkoutPin !== true || envelope.pin === head;
  if (canOpenHead && envelope.pin !== null && head !== "") {
    model.browse = { kind: "link", at: envelope.pin };
    if (envelope.pin !== head) {
      // A branch, a tag, or another pull request. Nothing is wrong, so nothing is said:
      // reading a pull request does not need its code served. A pin on this pull request's
      // own head is here only until the server has followed the head a refresh just read
      // (`follows_moves` in mirror_refresh.py), and the page then reloads on it.
      model.browse = { kind: "switch", ref: headRef, head, at: head };
    }
  }
  if (envelope.pin === null && head !== "" && page.checkoutHead === head) {
    // A checkout has no pin, so no Browse code: its working tree is not the pull request's
    // code. When its HEAD is this pull request's head, that much is so, and the page says it.
    model.checkoutAtHead = "This checkout’s HEAD is this pull request’s head.";
  }
  model.filesUnavailable = filesUnavailableText(record.unavailable?.comparison ?? null);
  if (record.unavailable?.comparison === "no_store" && diffTab(page.tab)) {
    // Progress only for an attempt running or still to be sent, Retry only once one
    // failed or a recorded outcome holds it, and Fetch only when nothing will ask.
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
    } else if (typeof page.comparisonRefusal === "string") {
      // A later read clears the refusal's error; its reason stays until the page asks again.
      // Each refusal is one sentence (copy.js), so the two make the message's limit of two.
      model.filesUnavailable = `${model.filesUnavailable} ${page.comparisonRefusal}`;
    }
  }
  const comparison = pullComparison(envelope);
  if (comparison !== null) {
    // The Diff summary's head: the comparison's, which a record read at a newer head keeps.
    model.head = comparison.right;
    model.comparison = {
      ...comparison,
      // What View on branch opens: the pull request's head, under its ref, when the diff
      // shows that head. A diff of another commit has no branch it is on. A checkout can
      // open only the head it serves, and then under no ref of its own.
      branch:
        canOpenHead && head !== "" && comparison.right === head
          ? { ref: page.checkoutPin === true ? null : headRef }
          : null,
    };
  }
  model.comparisonComing =
    model.comparison === null &&
    record.unavailable?.comparison === "no_store" &&
    (envelope.preparing_comparison === true || (diffTab(page.tab) && model.changesPending));
  return model;
}

/**
 * The comparison an envelope's record names, with the routes that answer it, or null. The
 * page reads it for its Diff summary and Changes, and the Pulls tab to warm it ahead of a
 * click (comparison-prefetch.js, `createComparisonWarmer`). Pure.
 *
 * @param {unknown} envelope
 * @returns {{left: string, right: string, route?: string, image_route?: string, rendered_route?: string, size_route?: string} | null}
 */
export function pullComparison(envelope) {
  const shaped = /** @type {Record<string, any> | null} */ (
    envelope !== null && typeof envelope === "object" ? envelope : null
  );
  const comparison = shaped?.record?.comparison;
  if (!comparison || typeof comparison.base !== "string" || typeof comparison.head !== "string") {
    return null;
  }
  return {
    left: comparison.base,
    right: comparison.head,
    ...(typeof shaped?.comparison_route === "string" ? { route: shaped.comparison_route } : {}),
    // Where rendered Markdown in Changes loads the head's images from.
    ...(typeof shaped?.image_route === "string" ? { image_route: shaped.image_route } : {}),
    // Where Changes asks for one Markdown file's rendered redline.
    ...(typeof shaped?.rendered_route === "string"
      ? { rendered_route: shaped.rendered_route }
      : {}),
    // Where the header's size line asks what the comparison pushes (pull_size.py).
    ...(typeof shaped?.size_route === "string" ? { size_route: shaped.size_route } : {}),
  };
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

// ── Texts the server would not render ─────────────────────────

/**
 * What a text's notice says when the Markdown route will not render it, or null when
 * its answer says nothing a reader needs: a record the page no longer shows, say, whose
 * text stays plain until the newer record's is asked for. The server renders a text in
 * its Markdown child under a deadline (`pull_markdown.render_part`), and refuses one that
 * runs past it, whose renderer stops, whose renderer cannot start, or that arrives while
 * the renderer has as many other texts as it takes; KPress can also fail on a text. Each
 * shows the text as written, with this line saying so, and a reload only where the next
 * attempt can differ: a renderer that could not start or was busy. The code and the
 * deadline stay in the route's answer.
 *
 * @param {number} status
 * @param {Record<string, any> | null} body
 * @returns {string | null}
 */
export function refusedTextNote(status, body) {
  if (status === 200 || body === null || typeof body.code !== "string") {
    return null;
  }
  return textRefusalNote(body.code);
}

/**
 * What a text's notice says for the refusal *code* the Markdown route answers, or null for
 * a code with nothing a reader needs (`refusedTextNote`). Guided Review says the same under
 * a note whose render was refused (`note_refusal` in guided_review.py).
 *
 * @param {string} code
 * @returns {string | null}
 */
export function textRefusalNote(code) {
  switch (code) {
    case "render_deadline":
      return "This text took too long to render, so it is shown as written.";
    case "renderer_exited":
    case "render_failed":
      return "This text could not be rendered, so it is shown as written.";
    case "renderer_unavailable":
    case "renderer_busy":
      return "This text could not be rendered, so it is shown as written. Reload the page to try again.";
    default:
      return null;
  }
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

/**
 * What a page's texts are read from: the record, or with no record the core preview, whose
 * description is the one text it has. Null with neither.
 *
 * @param {PullEnvelope | null} envelope
 * @returns {Record<string, any> | null}
 */
export function textSource(envelope) {
  if (envelope === null) {
    return null;
  }
  if (envelope.record !== null) {
    return envelope.record;
  }
  return envelope.core_preview === null ? null : { pull: envelope.core_preview.pull };
}

/**
 * The revision a page's texts are asked under: the record's, or with no record the core
 * preview's, so a preview's description renders while its record is fetched (mb-d59o).
 *
 * @param {PullEnvelope | null} envelope
 * @returns {string | null}
 */
export function textRevision(envelope) {
  if (envelope === null) {
    return null;
  }
  if (envelope.record !== null) {
    return envelope.record_revision;
  }
  return envelope.core_preview?.revision ?? null;
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
 *   schedule(callback: () => void, delayMs: number, kind?: "ask"): unknown,
 *   cancel(handle: unknown): void,
 *   now(): number,
 *   isVisible(): boolean,
 *   isOnline?(): boolean,
 *   formatHold?(liftMs: number, nowMs: number): string,
 *   ownsChanges?(): boolean,
 *   ownsConversation?(): boolean,
 *   scheduleComparison?(callback: () => void): () => void,
 *   render(model: PullModel, identity: import("./pull-stacks.js").StackIdentity | null): void,
 *   renderMarkdown(part: string, rendered: Record<string, any>, text: string): void,
 *   textUnavailable?(part: string, text: string, note?: string | null): void,
 *   listed?(source: string | null, number: number): {state: import("./pull-state.js").PullState, updatedAt: string} | null,
 *   noteRecord?(source: string, pull: Record<string, any>): void,
 *   timelineStateChanged?(): void,
 *   switchPin(selection: {oid: string, under: string, view?: string}, wanted: () => boolean): Promise<{kind: "switched", href: string | null} | {kind: "busy"} | {kind: "abandoned"} | {kind: "refused", message: string}>,
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
 *   checkoutPin?: boolean,
 * }} options
 */
export function createPullController(deps, options) {
  const pullRoute = `${PULL_ROUTE}?number=${options.number}`;
  /** @type {PullEnvelope | null} */
  let envelope = null;
  /** @type {string | null} */
  let etag = null;
  // What the address asks for: a tab, or "" for the front page, which `shownTab` resolves.
  let routeTab = TABS.includes(options.tab) ? options.tab : "";
  /**
   * The tab on screen: the route's, with the front page resolved against the description the
   * page shows, the record's or before it the core preview's (`textSource`), as the page
   * resolves its address against the model's (`addressShows`), so the two never disagree.
   */
  const shownTab = () => shownTabFor(routeTab, partText(textSource(envelope), "body"));
  /** @type {unknown} */
  let timer = null;
  /** When `timer` fires, by `deps.now()`. */
  let timerDue = 0;
  let polling = false;
  // A render from a revision newer than the page's answered while a read was on its way
  // (`pollNow`): the page reads again as soon as that read answers.
  let readAgain = false;
  let hasPolled = false;
  let inFlightRefreshes = 0;
  let disposed = false;
  // When this page last sent an automatic ask of its own, by `deps.now()`. While it shows a
  // record it asks every `probe_every_s`, current or stale: the server probes the record, a
  // free conditional read, or reads it in full when that is due, and holds each number to
  // its own attempt windows, so a stale page whose refresh cannot run is not refreshed on
  // every ask. Without `probe_every_s` it asks only for a stale record, once a window.
  /** @type {number | null} */
  let autoAskedAt = null;
  /** When that ask was answered, or failed, by `deps.now()`. @type {number | null} */
  let autoAnsweredAt = null;
  // When the page last sent an automatic ask for a stale record. A stale record asks once
  // a window from this, not from the last probe ask: a probed record goes stale when its
  // full read comes due, a few seconds before the next probe ask would start that read,
  // and waiting a window from that probe ask showed it stale for most of a minute.
  /** @type {number | null} */
  let staleAskedAt = null;
  /** That ask: none, scheduled (waiting in `askTimer`), or sent and not yet answered. */
  /** @type {"none" | "scheduled" | "sent"} */
  let autoAsk = "none";
  // Whether that ask was for a stale record, which the age line shows as refreshing, or a
  // probe of a current one, which changes nothing the page shows unless it finds a change.
  let autoAskStale = false;
  // Once the repository's list of pull requests has vouched for this record, the page keeps
  // that list scanned while it is visible, so the record stays current without being read
  // again: when the check lapses it asks for the next scan, once a window, before it reads.
  // While probes vouch for the record the envelope's check is theirs and never lapses, so
  // a probing page asks for no scan (`catalogScanDue`).
  let catalogBacked = false;
  /** When the page last asked for the catalog's scan, by `deps.now()`. @type {number | null} */
  let catalogAskedAt = null;
  // The last answer said the catalog vouched while its next scan ran: the page reads again
  // in a fast poll, so a change that scan publishes is refreshed then, not a slow poll later.
  let catalogScanning = false;
  // A label the page shows without its color, which the envelope has no entry for, asks
  // for the repository's label set once a page (`mb-varu`); the server reads it only when
  // it is absent or due. Once the set's job started or was joined, the page reads again in
  // a fast poll, which says from then on whether the job still runs (`labels_pending`).
  let labelsAsked = false;
  let labelsComing = false;
  /** The ask that waits for `REFRESH_ASK_MS`. @type {unknown} */
  let askTimer = null;
  /** @type {string | null} */
  let error = null;
  // Whether `error` is a comparison's refusal, which Changes says beside its Retry, so the
  // header leaves it out. Told apart by the ask that met it, not by its words: a refused
  // Refresh says the same words, and the header must say those (C3 of review C on #506).
  let errorFromComparison = false;
  // Whether `error` is a reader's refresh that was refused or failed, which the status row
  // offers Retry for (mb-ablv): a failed read or a failed switch to the head says what failed
  // with nothing for Retry to ask again.
  let errorFromRefresh = false;
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
  /**
   * Markdown by part, for `markdownFor`, with the text it renders. `markdownFor` is the
   * revision the page's texts are asked under: the record's, or with no record the core
   * preview's, whose description the route renders from the core (`textRevision`).
   *
   * @type {Map<string, {rendered: Record<string, any>, text: string}>}
   */
  const markdown = new Map();
  /** @type {string | null} */
  let markdownFor = null;
  /** @type {string[]} */
  const queue = [];
  /**
   * The parts asked for, with the text and the revision each was asked for: an answer
   * rendered from another revision is not the render of that text. A part `joined` sent
   * nothing of its own: the same text was already on its way under an earlier revision, and
   * that render serves it, or the part is asked again if it fails.
   *
   * @type {Map<string, {text: string | null, revision: string | null, joined?: boolean}>}
   */
  const asked = new Map();
  /**
   * How many requests for each part's text are on their way: queued, sent and not answered,
   * or answered from a revision the page has not read yet (`ahead`). The glue shows such a
   * text as a placeholder, never as its source (`pending`), until every one has settled.
   *
   * @type {Map<string, Map<string, number>>}
   */
  const coming = new Map();
  /**
   * Renders answered from a revision newer than the page's, by part: a record that landed
   * between the page's read and the route's. Each serves its part once the page reads that
   * revision, and keeps the text it was asked for pending until then.
   *
   * @type {Map<string, {revision: string, rendered: Record<string, any>, text: string}>}
   */
  const ahead = new Map();
  let inFlight = 0;

  /**
   * @param {string} part
   * @param {string} text
   * @param {number} step 1 for a request on its way, -1 for one settled.
   */
  function counted(part, text, step) {
    const texts = coming.get(part) ?? new Map();
    const count = (texts.get(text) ?? 0) + step;
    if (count > 0) {
      texts.set(text, count);
      coming.set(part, texts);
    } else {
      texts.delete(text);
      if (texts.size === 0) {
        coming.delete(part);
      }
    }
  }

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
   * How long until the page's next automatic ask, or null when none is due without another
   * read: visible, online, nothing on its way or running, and not held. A stale record is
   * asked for, and so is a current one while the envelope names `probe_every_s`; a later ask
   * for a current record waits that long after the last, and one for a stale record a
   * freshness window. A failure the
   * reader must fix (no gh, an old gh, signed out) waits for the reader's Refresh after the
   * first ask.
   *
   * @returns {number | null}
   */
  function automaticAskWait() {
    const probeIntervalMs =
      typeof envelope?.probe_every_s === "number" ? envelope.probe_every_s * 1000 : null;
    if (
      disposed ||
      !deps.isVisible() ||
      !online() ||
      envelope === null ||
      !(envelope.state === "stale" || (envelope.state === "current" && probeIntervalMs !== null)) ||
      envelope.refreshing ||
      fetching ||
      autoAsk !== "none" ||
      askTimer !== null ||
      rateLimitHolds() ||
      (envelope.record?.unavailable?.comparison === "no_store" &&
        (diffTab(shownTab()) ||
          (shownTab() === "" &&
            deps.ownsConversation?.() === true &&
            hasFreshComparisonMetadata())))
    ) {
      return null;
    }
    if (autoAskedAt === null) {
      return 0;
    }
    const outcome = envelope.last_refresh?.outcome ?? "";
    if (["gh_missing", "gh_too_old", "not_logged_in"].includes(outcome)) {
      return null;
    }
    if (envelope.state === "current" && probeIntervalMs !== null) {
      return Math.max(
        0,
        autoAskedAt + probeIntervalMs - deps.now(),
        (autoAnsweredAt ?? autoAskedAt) + PROBE_ASK_GAP_MS - deps.now(),
      );
    }
    // A stale record asks again once a window has passed since the last ask for a stale
    // record (`staleAskedAt`), on the poll that finds it so: the server answers a probe ask
    // that finds a change, or a record past its full-read interval, with a refresh at once,
    // so a record still stale after such an ask is one whose refresh failed or was not due.
    return staleAskedAt === null || deps.now() - staleAskedAt >= envelope.fresh_for_s * 1000
      ? 0
      : null;
  }

  /**
   * Schedule the page's next automatic ask (`automaticAskWait`). The first ask of a page
   * waits for the reader to stay on it, as long as the Pulls tab's opening said (none for a
   * click) or `REFRESH_ASK_MS` for an address, which holding Back walks through; a later one,
   * on a page left open, asks when its interval has passed, and each answer schedules the
   * next. Any of them waits while a key that opened the page is held.
   */
  function askIfStale() {
    if (autoAsk === "scheduled" && !autoAskStale && envelope?.state === "stale") {
      // A probe ask was waiting for a current record that has since gone stale: the stale
      // record asks when its own wait says, which is at once on a page left open.
      cancelAsk();
    }
    const waitMs = automaticAskWait();
    if (waitMs === null) {
      return;
    }
    const delayMs =
      autoAskedAt !== null ? waitMs : Math.max(waitMs, reader?.fetchAfterMs ?? REFRESH_ASK_MS);
    autoAsk = "scheduled";
    const forStale = envelope?.state === "stale";
    autoAskStale = forStale;
    askAfter(async () => {
      autoAsk = "none";
      if (!forStale) {
        // A probe ask recurs, and what it waited for may have changed meanwhile: a refresh
        // started, the page fetched, or a limit took hold. Then it asks again when that is
        // due, not now. An ask for a stale record is sent as it was scheduled.
        const stillWaitMs = automaticAskWait();
        if (stillWaitMs === null || stillWaitMs > 0) {
          askIfStale();
          return;
        }
      }
      autoAsk = "sent";
      autoAskStale = envelope?.state === "stale";
      autoAskedAt = deps.now();
      if (autoAskStale) {
        staleAskedAt = autoAskedAt;
      }
      try {
        // The ask names the record the page shows, so an answer about that record comes
        // without it (`withHeldRecord`).
        const held = envelope?.record != null ? envelope.record_revision : null;
        await askForRefresh(
          { number: options.number, ...(held === null ? {} : { held }) },
          { automatic: true },
        );
      } finally {
        autoAsk = "none";
        autoAnsweredAt = deps.now();
      }
      if (!disposed) {
        render();
        askIfStale();
      }
    }, delayMs);
  }

  /**
   * Whether the page asks for the catalog's next scan before it reads: the catalog vouched
   * for this record before, its check is a window old, and none was asked within a window.
   * The server starts it only once a window, and a record it is scanning for stays current.
   * The check is the envelope's newest, the catalog's or a probe's: while probes vouch for
   * the record no scan is needed for it, and once they stop, the catalog's own older check
   * is the one the envelope carries, and the next poll asks for a scan.
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
    const found = /^(catalog|fetch|probe) (\S+)(?: scanning)?$/u.exec(value ?? "");
    if (envelope === null || envelope.record === null || found === null) {
      return;
    }
    const by = /** @type {"catalog" | "fetch" | "probe"} */ (found[1]);
    envelope = { ...envelope, verified_by: by, verified_at: found[2] };
    catalogBacked = catalogBacked || by === "catalog";
  }

  /** What `describePull` and `comparisonQueued` read of this page. */
  function pageState() {
    return {
      number: options.number,
      tab: shownTab(),
      nowMs: deps.now(),
      error,
      errorFromComparison,
      errorFromRefresh,
      fetching: fetching || refreshPending,
      fetchQueued: fetchQueued(),
      refreshPending,
      refreshDue: autoAsk !== "none" && autoAskStale,
      online: online(),
      ...(deps.formatHold === undefined ? {} : { formatHold: deps.formatHold }),
      ownsChanges: walkSettling || ownsChanges(),
      comparisonAttempted,
      comparisonRefusal,
      waitForReader: reader !== null && !readerAsked && envelope?.reason !== "not_github",
      checkoutHead: options.checkoutHead ?? null,
      checkoutPin: options.checkoutPin === true,
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
    // The record's state, noted back over a list's older word, so another member's stack
    // menu draws what this record holds rather than what the list said before it changed.
    const recorded = envelope?.record?.pull;
    if (recorded && typeof envelope?.source === "string") {
      deps.noteRecord?.(envelope.source, recorded);
    }
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

  /**
   * Whether an ask for a stale record is waiting, so a refresh may follow. A waiting probe
   * ask, for a current record, is not one: it waits on every visible current page, and
   * the probe it asks for is answered without a refresh unless GitHub changed.
   */
  function refreshAskWaiting() {
    return askTimer !== null && autoAskStale;
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
    askTimer = deps.schedule(
      () => {
        if (!disposed && reader?.walking?.() === true) {
          askAfter(ask, delayMs);
          return;
        }
        askTimer = null;
        ask();
      },
      delayMs,
      "ask",
    );
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
    const quiet = envelope?.preparing_comparison === true && !diffTab(shownTab());
    return (
      envelope === null ||
      (envelope.refreshing && !quiet) ||
      envelope.state === "pending" ||
      // The repository's labels are being read, so a chip still drawn without its color
      // takes it at once (`mb-varu`).
      envelope.labels_pending === true ||
      labelsComing ||
      catalogScanning
    );
  }

  /**
   * How long until a rate limit stops holding this page's automatic comparison or its stale
   * record's refresh, or null when none holds either. The page reads again then, so it asks
   * without waiting for a slow poll and does not keep a hold or a Retry painted past it.
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
    const revision = textRevision(next);
    if (revision !== markdownFor) {
      cancelIdleComparison();
      // Another record or preview: its texts may differ, so nothing rendered from the last
      // one is shown again. The page asks again for the parts a reader sees. A render still
      // on its way is answered all the same, and serves the part if its text is unchanged;
      // the same text asked again joins it (`requestMarkdown`).
      markdownFor = revision;
      markdown.clear();
      for (const part of queue) {
        const text = asked.get(part)?.text;
        if (typeof text === "string") {
          counted(part, text, -1);
        }
      }
      asked.clear();
      queue.length = 0;
      // A render answered from this revision before the page read it is this revision's
      // render of its part's text; one from any other revision serves nothing now.
      const source = textSource(next);
      for (const [part, early] of ahead) {
        const text = partText(source, part);
        if (early.revision === revision && text !== null) {
          markdown.set(part, { rendered: early.rendered, text });
          rememberRendered(next.source ?? null, options.number, part, text, early.rendered);
        }
        counted(part, early.text, -1);
      }
      ahead.clear();
    }
    return true;
  }

  /**
   * The envelope a refresh answered, with the record the page holds put back where the
   * answer left it out. An ask that names `held`, the revision of the record the page
   * shows, is answered `record_held` in place of that record when the server's is the
   * same one, which is nearly every answer of a page left open (`refresh_answer_pull` in
   * pull_route.py records what the whole envelope cost each `probe_every_s`).
   *
   * The revision leaves out the record's `fetched_at`, which a read that found the same
   * content moves, so the record takes the answer's: the envelope's `fetched_at` is its
   * record's, and the age line is counted from the record.
   *
   * Null when the page no longer holds that record as the server has it: another revision
   * since the ask, or a record whose comparison a server with no store drops (`no_store`),
   * which shares its revision with the one a store keeps. The page then reads the route.
   *
   * @param {unknown} pull
   * @returns {unknown} An envelope to check with `isEnvelope`, or null.
   */
  function withHeldRecord(pull) {
    if (pull === null || typeof pull !== "object" || !("record_held" in pull)) {
      return pull;
    }
    const { record_held: _held, ...rest } = /** @type {Record<string, unknown>} */ (pull);
    if (
      envelope === null ||
      envelope.record === null ||
      envelope.record_revision !== rest.record_revision ||
      "no_store" in envelope !== "no_store" in rest
    ) {
      return null;
    }
    return { ...rest, record: { ...envelope.record, fetched_at: rest.fetched_at } };
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
      errorFromComparison = false;
      errorFromRefresh = false;
    } finally {
      polling = false;
      hasPolled = true;
    }
    if (disposed) {
      return;
    }
    const again = readAgain;
    readAgain = false;
    // A waiting read spent part (or all) of the interval already.
    afterRead(
      again
        ? 0
        : waitStarted === null
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
    labelsComing = false;
    if (response.status === 200 && isEnvelope(response.body)) {
      if (accept(response.body, request)) {
        etag = response.etag;
        catalogScanning = / scanning$/u.test(response.verified ?? "");
      }
      error = null;
      errorFromComparison = false;
      errorFromRefresh = false;
    } else if (response.status === 304 || pinChanged(response)) {
      if (response.status === 304) {
        adoptVerified(response.verified);
        catalogScanning = / scanning$/u.test(response.verified ?? "");
      }
      error = null;
      errorFromComparison = false;
      errorFromRefresh = false;
    } else {
      error = unavailableText("The pull request");
      errorFromComparison = false;
      errorFromRefresh = false;
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
    askForLabels();
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
   * Ask once for the repository's label set when the page shows a label named alone that
   * the envelope has no entry for, at once on the first read that shows it, and not while
   * the set's job already runs. The server reads the set only when it is absent or due; a
   * job it started or joined makes the next read a fast poll.
   */
  function askForLabels() {
    if (
      labelsAsked ||
      disposed ||
      envelope === null ||
      envelope.labels_pending === true ||
      !deps.isVisible() ||
      !online() ||
      !labelsMissing(envelope)
    ) {
      return;
    }
    labelsAsked = true;
    void (async () => {
      let started = false;
      try {
        const response = await deps.request("POST", LABELS_REFRESH_ROUTE, { body: {} });
        started = response.status === 202;
      } catch {
        // The chips keep their neutral color; the page's next visit asks again.
      }
      if (started && !disposed) {
        labelsComing = true;
        scheduleNext();
      }
    })();
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
   * page's own request says nothing to the reader, whose page still shows what it did, and
   * which the navigation's Refresh still reaches.
   *
   * An automatic ask (*automatic*), a visible page's recurring probe or its ask for a stale
   * record, restarts the poll only when it started a refresh or the poll should be fast and
   * is not: the poll keeps its own interval, so a server that stops answering is reported
   * by it, and by the failed ask itself.
   *
   * @param {{number: number, retry?: boolean, wait_core?: boolean, comparison?: boolean, prepare_comparison?: string, recovery?: {base: string, head: string}, held?: string}} ask
   * @param {{automatic?: boolean}} [how]
   */
  async function askForRefresh(ask, { automatic = false } = {}) {
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
    let started = false;
    // The answer left out a record the page no longer holds: the route is read at once.
    let reread = false;
    try {
      const response = await deps.request("POST", REFRESH_ROUTE, { body: ask });
      const body = /** @type {{pull?: unknown, code?: unknown} | null} */ (response.body);
      const pull = body === null ? null : withHeldRecord(body.pull);
      if (
        (response.status === 202 || response.status === 200) &&
        body !== null &&
        pull === null &&
        body.pull != null
      ) {
        etag = null;
        reread = true;
        if (!idle) {
          error = null;
          errorFromComparison = false;
          errorFromRefresh = false;
        }
      } else if (
        (response.status === 202 || response.status === 200) &&
        body !== null &&
        isEnvelope(pull)
      ) {
        if (accept(pull, request)) {
          waitForFull =
            response.status === 202 &&
            ask.wait_core === true &&
            pull.record === null &&
            pull.refreshing;
        }
        if (response.status === 202) {
          // The answer changed; the next poll must not be answered by a 304.
          etag = null;
          started = true;
        }
        if (!idle) {
          error = null;
          errorFromComparison = false;
          errorFromRefresh = false;
        }
      } else if (ask.retry) {
        const code = body !== null && typeof body.code === "string" ? body.code : null;
        error = refreshRefusedText("The refresh", code);
        errorFromComparison = ask.comparison === true;
        errorFromRefresh = ask.comparison !== true;
        if (ask.comparison) {
          comparisonRefusal = error;
        }
      }
    } catch {
      if (automatic) {
        // As a failed poll is: the server did not answer this page's own ask.
        error = "The server did not answer.";
        errorFromComparison = false;
        errorFromRefresh = false;
      }
      if (ask.retry) {
        error = "The refresh request failed.";
        errorFromComparison = ask.comparison === true;
        errorFromRefresh = ask.comparison !== true;
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
      if (reread) {
        pollNow();
      } else if (
        !automatic ||
        started ||
        timer === null ||
        (pollsFast() && timerDue - deps.now() > FAST_POLL_MS)
      ) {
        scheduleNext(
          fastSince === null
            ? FAST_POLL_MS
            : FAST_POLL_MS - (Math.max(0, deps.now() - fastSince) % FAST_POLL_MS),
        );
      }
      deps.timelineStateChanged?.();
      fetchIdleChanges();
    }
  }

  /**
   * A reader's own press of the navigation's Refresh, or of Retry or Fetch on the status row
   * (mb-ablv). Files names the comparison still displayed, which can be older than the
   * latest metadata the page has polled.
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
      shownTab() !== "" ||
      !deps.isVisible() ||
      deps.ownsConversation?.() !== true ||
      !hasPolled ||
      polling ||
      fetching ||
      refreshAskWaiting() ||
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
   * A reader's Retry or Fetch of Changes, which the address need not name. What the
   * button was painted from can be older than the model: a hold lifts by the clock alone,
   * and a failed read stops the automatic attempt without repainting. So the click sends
   * whenever the record still lacks its store and nothing else is on its way.
   */
  async function requestComparison() {
    if (
      !disposed &&
      diffTab(shownTab()) &&
      deps.isVisible() &&
      inFlightRefreshes === 0 &&
      envelope?.refreshing === false &&
      envelope.record?.unavailable?.comparison === "no_store"
    ) {
      await fetchComparison();
    }
  }

  /**
   * Serve the pull request's head, by its commit and under its ref, and then go on. The
   * switch is the page's one switch, which the diff's View on branch shares
   * (`createPinSwitch` in the diff plugin): one at a time, and a refusal said in its words,
   * after which the page stays as it was.
   *
   * @param {{head: string, ref: string}} at
   * @param {string} view The `/view/` address the page goes to.
   * @param {(moved: string | null) => void} then Given where the server says *view* is on
   *   the head, when it says.
   */
  async function serveHead(at, view, then) {
    if (disposed) {
      return;
    }
    const outcome = await deps.switchPin({ oid: at.head, under: at.ref, view }, () => !disposed);
    if (disposed || outcome.kind === "busy" || outcome.kind === "abandoned") {
      return;
    }
    if (outcome.kind === "switched") {
      then(outcome.href);
      return;
    }
    error = outcome.message;
    errorFromComparison = false;
    errorFromRefresh = false;
    render();
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
      await serveHead(browse, href, (moved) => {
        // The server's address for the file on the head, or its root when the head has no
        // such file; the address asked for when it is the same file, which keeps its line.
        deps.navigate(moved !== null && moved !== href.split(/[?#]/, 1)[0] ? moved : href);
      });
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
    routeTab = next;
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
          if (text !== null) {
            counted(part, text, -1);
          }
          const rendered =
            !disposed &&
            response.status === 200 &&
            body !== null &&
            typeof body.html === "string" &&
            text !== null;
          const from = rendered ? (body.record_revision ?? body.core_revision ?? null) : null;
          const shows = partText(textSource(envelope), part);
          // A render is of its revision's text alone (`pull_markdown.render_part`). One of the
          // revision it was asked under renders the text asked for, and one of the revision
          // the page shows renders the text the page shows: either serves the part while the
          // page shows that text. The full record that follows a core preview usually has its
          // description unchanged, and may land between the page's read and the route's.
          const current =
            rendered &&
            ((from === revision && (revision === markdownFor || shows === text)) ||
              (from !== null && from === markdownFor && shows === text));
          if (current && text !== null) {
            markdown.set(part, { rendered: body, text });
            rememberRendered(source, options.number, part, text, body);
            deps.renderMarkdown(part, body, text);
            return;
          }
          if (rendered && from !== null && from !== revision && from !== markdownFor) {
            // Rendered from a revision the page has not read: the route read a record that
            // landed after the page's read. The text stays a placeholder, and the page reads
            // now; that revision's read lets this render serve its part (`accept`).
            const early = ahead.get(part);
            if (early !== undefined) {
              counted(part, early.text, -1);
            }
            ahead.set(part, { revision: from, rendered: body, text: /** @type {string} */ (text) });
            counted(part, /** @type {string} */ (text), 1);
            pollNow();
            return;
          }
          if (unanswered(part, text, revision)) {
            return;
          }
          // A render of a text the page no longer shows, or none at all: the
          // plain text stays, and a newer record is asked for again. A text the
          // server would not render says why.
          if (!disposed && text !== null) {
            deps.textUnavailable?.(part, text, refusedTextNote(response.status, body));
          }
        })
        .catch(() => {
          if (text !== null) {
            counted(part, text, -1);
          }
          if (unanswered(part, text, revision)) {
            return;
          }
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
   * Whether a part that joined this answer's request under a newer revision is asked again
   * now, as its own request: the request it joined did not render, and the part has nothing
   * else on its way. Once only, so a text the newer revision cannot render either says why.
   *
   * @param {string} part
   * @param {string | null} text
   * @param {string | null} revision The revision the answer was asked under.
   */
  function unanswered(part, text, revision) {
    const now = asked.get(part);
    if (
      disposed ||
      text === null ||
      now === undefined ||
      now.joined !== true ||
      now.text !== text ||
      now.revision === revision
    ) {
      return false;
    }
    asked.set(part, { text, revision: now.revision });
    counted(part, text, 1);
    queue.push(part);
    return true;
  }

  /** Read the pull route now, as a render from a newer revision shows one has landed. */
  function pollNow() {
    if (disposed) {
      return;
    }
    if (polling) {
      // A read on its way may have left before that revision landed: read again after it.
      readAgain = true;
      return;
    }
    clearTimer();
    timer = deps.schedule(() => {
      timer = null;
      void poll();
    }, 0);
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
    const text = shownText ?? partText(textSource(envelope), part);
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
    if (text !== null && (coming.get(part)?.get(text) ?? 0) > 0) {
      // The same text is on its way under an earlier revision, the core preview's whose
      // record has just landed: its render serves this part, so the text is rendered once.
      asked.set(part, { text, revision: markdownFor, joined: true });
      return;
    }
    asked.set(part, { text, revision: markdownFor });
    if (text !== null) {
      counted(part, text, 1);
    }
    queue.push(part);
    pump();
  }

  /**
   * Whether *text*'s Markdown is on its way for *part*: queued, asked and not answered, or
   * answered from a revision the page is reading now.
   *
   * @param {string} part
   * @param {string} text
   */
  function pending(part, text) {
    return !disposed && (coming.get(part)?.get(text) ?? 0) > 0;
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
      !refreshAskWaiting() &&
      inFlightRefreshes === 0 &&
      (envelope?.refreshing === false || envelope?.preparing_comparison === true),
    fetchIdleChanges,
    requestRefresh,
    requestComparison,
    browseCode,
    requestMarkdown,
    renderedFor,
    pending,
    setTab,
    walkCancelled,
    onVisibilityChange,
    onConnectivityChange,
    dispose,
    snapshot: () => ({
      state: envelope?.state ?? null,
      etag,
      tab: shownTab(),
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
 * In Changes a block is a file, and `file` names it, so a place holds its file when the
 * diff is another one: a pull request whose head moved shows other files above it.
 *
 * @typedef {{block: number, offset: number, top: number, file?: string}} PanePlace
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
 * A place in the header goes no further than the first block's top: the header can be
 * shorter than it was, as it is when the Diff summary in it was open, tens of thousands of
 * pixels of rows, and a page opened again draws it closed, so the same offset would land
 * that far into the page.
 *
 * *fileBlock* is where the place's file is now, when the page can say: the place is in
 * that block, whichever block it was. `-1` is a page that has no such file, a newer diff
 * the file is not in: the place is the top of the block at its index, since the offset was
 * a line of a file that is gone. Left out, the page cannot say, as before its diff has
 * mounted, and the place is at its index as it was.
 *
 * @param {PanePlace} place
 * @param {number[]} tops
 * @param {number} [fileBlock]
 * @returns {number | null}
 */
export function scrollTopOf(place, tops, fileBlock) {
  if (tops.length === 0) {
    return null;
  }
  if (place.block < 0) {
    return Math.min(place.top, tops[0]);
  }
  if (fileBlock !== undefined && fileBlock >= 0 && fileBlock < tops.length) {
    return tops[fileBlock] + place.offset;
  }
  const top = tops[Math.min(place.block, tops.length - 1)];
  return fileBlock === undefined ? top + place.offset : top;
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
    Number.isFinite(place.top) &&
    (place.file === undefined || typeof place.file === "string")
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
 *   schedule(callback: () => void, delayMs: number, kind?: "ask"): unknown,
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

  /**
   * Hold a place the page chose for the reader, as a landing's is held: where they were in a
   * diff that Changes is about to replace. Written at once, so a reload lands there too, and
   * put when the page next changes height, which is the new diff arriving: the page is asked
   * for nothing now, while it still shows the diff being replaced, and a scroll before then,
   * the emptied pane's clamp to its top, is the hold's and writes nothing.
   *
   * @param {PanePlace} place
   */
  function holdAt(place) {
    if (disposed) {
      return;
    }
    cancelWrite();
    cancelSettle();
    holding = place;
    deps.write(place);
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
    /** Hold a place the page chose for the reader (`holdAt`). */
    holdAt,
    /**
     * Hold the reader's place through a diff's replacement, as `holdAt`: where they are now,
     * or, when the page has nothing to measure (*measurable* false, as while the diff being
     * replaced is itself still being read), the place held, else the one the entry has, which
     * a landing there would hold. Measured then, the emptied page says only that the pane is
     * at its top. A second follow during the read finds the place still held, and a press of
     * a button over the read, the followed note's, finds it in the entry: the press ended
     * the hold first, as any input in the pane does (B1 of review B on #745).
     *
     * @param {boolean} measurable
     */
    holdThrough(measurable) {
      if (disposed) {
        return;
      }
      if (measurable) {
        holdAt(deps.measure());
        return;
      }
      const kept = holding ?? deps.read();
      holdAt(isPanePlace(kept) ? kept : deps.measure());
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
 * @typedef {{left: string, right: string, route?: string, image_route?: string, rendered_route?: string, size_route?: string}} ShownComparison
 */

/**
 * What Changes does with the record's comparison. Pure.
 *
 * Changes follows the pull request, as its served code follows the head (`follows_moves`
 * in mirror_refresh.py): a record read at a newer head, or against a base that moved,
 * replaces the diff shown, and a note names both heads with the way back
 * (`followedNote`). A reader who took the way back chose the earlier diff (*chosen*), so
 * it stays, and the record's is offered.
 *
 * @param {{left: string, right: string, route?: string} | null} mounted The comparison the diff shows.
 * @param {{left: string, right: string, route?: string} | null} comparison The record's.
 * @param {boolean} [chosen] Whether the reader went back to the diff shown.
 * @returns {"unavailable" | "mount" | "keep" | "follow" | "offer"}
 */
export function filesAction(mounted, comparison, chosen = false) {
  if (comparison === null) {
    return "unavailable";
  }
  if (mounted === null) {
    return "mount";
  }
  if (
    mounted.left === comparison.left &&
    mounted.right === comparison.right &&
    mounted.route === comparison.route
  ) {
    return "keep";
  }
  return chosen ? "offer" : "follow";
}

/**
 * The diff Changes replaced without the reader asking, which its note names, or null. Pure.
 *
 * *last* is the comparison Changes last showed, on this page or, for a page loaded again,
 * as its history entry remembers it (`rememberedChanges`); a served head that moved
 * reloads the page, so the entry is what carries the note across. A mount of other commits
 * than *last* replaced it. A mount of the same commits keeps the diff its note already
 * named (*from*), unless that is the one now shown.
 *
 * @param {ShownComparison | null} last
 * @param {ShownComparison | null} from
 * @param {{left: string, right: string}} next
 * @returns {ShownComparison | null}
 */
export function followedFrom(last, from, next) {
  const same = (/** @type {ShownComparison | null} */ other) =>
    other !== null && other.left === next.left && other.right === next.right;
  if (last !== null && !same(last)) {
    return last;
  }
  return from !== null && !same(from) ? from : null;
}

/**
 * What Changes says over a diff that replaced another, or null when it replaced none. Pure.
 *
 * `head` is a diff of another head, which the note calls newer commits; `base` is the same
 * head compared from another merge base. Both heads stay on the note, as its identity and in
 * history (`rememberedChanges`), and never in its sentence.
 *
 * @param {{left: string, right: string} | null} from
 * @param {{left: string, right: string}} to
 * @returns {{kind: "head", from: string, to: string} | {kind: "base"} | null}
 */
export function followedNote(from, to) {
  if (from === null || (from.left === to.left && from.right === to.right)) {
    return null;
  }
  return from.right === to.right
    ? { kind: "base" }
    : { kind: "head", from: from.right, to: to.right };
}

/**
 * What a history entry remembers of its diff, on Changes or Docs, read back from
 * `history.state`, or null for anything else: the comparison it showed, the one its note
 * named, and whether the one shown is the earlier diff the reader went back to. Pure.
 *
 * @param {unknown} value
 * @returns {{shown: ShownComparison, from: ShownComparison | null, chosen: boolean} | null}
 */
export function rememberedChanges(value) {
  const memory = /** @type {{shown?: unknown, from?: unknown, chosen?: unknown} | null} */ (value);
  if (typeof value !== "object" || memory === null) {
    return null;
  }
  const shown = shownComparison(memory.shown);
  return shown === null
    ? null
    : { shown, from: shownComparison(memory.from), chosen: memory.chosen === true };
}

/**
 * The earlier diff a reader went back to, which a page loaded again on the entry shows in
 * place of the record's, or null. Pure.
 *
 * The choice stays until the reader takes the newer changes, and on a repository URL every
 * later push reloads the page, so the entry holds it. A record that names the remembered
 * commits again has nothing earlier to show.
 *
 * @param {{shown: ShownComparison, chosen: boolean} | null} memory
 * @param {{left: string, right: string}} comparison The record's.
 * @returns {ShownComparison | null}
 */
export function chosenEarlier(memory, comparison) {
  if (memory === null || !memory.chosen) {
    return null;
  }
  const { shown } = memory;
  return shown.left === comparison.left && shown.right === comparison.right ? null : shown;
}

/**
 * A comparison as Changes mounts it, with nothing but its commits and routes. Pure.
 *
 * @param {unknown} value
 * @returns {ShownComparison | null}
 */
export function shownComparison(value) {
  const given = /** @type {Record<string, unknown> | null} */ (value);
  if (typeof value !== "object" || given === null) {
    return null;
  }
  const { left, right } = given;
  if (typeof left !== "string" || typeof right !== "string") {
    return null;
  }
  /** @type {ShownComparison} */
  const shown = { left, right };
  for (const route of /** @type {const} */ ([
    "route",
    "image_route",
    "rendered_route",
    "size_route",
  ])) {
    const address = given[route];
    if (typeof address === "string") {
      shown[route] = address;
    }
  }
  return shown;
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
 * @param {{key: string, textRevision: string | null}} previous
 * @param {{key: string, textRevision: string | null}} next
 * @returns {"repaint" | "reask" | "keep"}
 */
export function conversationAction(previous, next) {
  if (previous.key !== next.key) {
    return "repaint";
  }
  return previous.textRevision !== next.textRevision ? "reask" : "keep";
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
 * Give *parent* exactly *nodes*, in order, moving only what is out of place: a node that is
 * already where it belongs is not touched, so it keeps its hover, its focus, and a tooltip
 * anchored to it.
 *
 * @param {Element} parent
 * @param {Element[]} nodes
 */
function placeChildren(parent, nodes) {
  /** @type {Set<Node>} */
  const wanted = new Set(nodes);
  for (const node of [...parent.childNodes]) {
    if (!wanted.has(node)) {
      node.remove();
    }
  }
  let cursor = parent.firstChild;
  for (const node of nodes) {
    if (node === cursor) {
      cursor = cursor.nextSibling;
    } else {
      parent.insertBefore(node, cursor);
    }
  }
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

// How a pull request's page and a stack's tell an age, drawn and told again alike.
const AGE_STYLE = Object.freeze({ style: /** @type {const} */ ("relative") });

/**
 * An age on a pull request's page or a stack's, drawn by the SDK's one age builder,
 * `mb.ageLabel`, so it draws in its freshness ink (docs/design-system.md, "Age"), with the
 * exact time in its tooltip and its time in `data-age-at`, from which `retellAges` tells it
 * again as time passes where a page keeps the node. `also` is a time the row leaves out
 * because its age reads the same as this one; its exact time joins this tooltip, so leaving
 * the age out loses nothing.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {string} iso
 * @param {{label: string, iso: string} | null} [also]
 * @returns {HTMLElement}
 */
export function pullAge(mb, iso, also = null) {
  const at = Date.parse(iso);
  if (!Number.isFinite(at)) {
    return h("span", {}, [iso]);
  }
  /** @param {number} ms */
  const exact = (ms) => mb.formatTimestamp(ms / 1000);
  const alsoAt = also === null ? Number.NaN : Date.parse(also.iso);
  const tip =
    also !== null && Number.isFinite(alsoAt)
      ? `${exact(at)} · ${also.label} ${exact(alsoAt)}`
      : exact(at);
  const element = mb.ageLabel(at / 1000, { ...AGE_STYLE, className: "github-pull-age", tip });
  element.setAttribute("data-age-at", String(at));
  return element;
}

/**
 * Tell *element*, an age `pullAge` drew, its age at *at* (ms) as of now, through the SDK's
 * one age builder (`mb.retellAge`): its words and its freshness class, its own class kept,
 * changing only what changed.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {Element} element
 * @param {number} at
 */
function tellAge(mb, element, at) {
  mb.retellAge(element, at / 1000, AGE_STYLE);
}

/**
 * Tell the ages in a kept node again, as of now (`tellAge`): a section kept across paints
 * keeps its node, and its ages would otherwise read as of when it was built.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {Element} node
 */
export function retellAges(mb, node) {
  for (const element of node.querySelectorAll(".github-pull-age")) {
    const at = Number(element.getAttribute("data-age-at"));
    if (Number.isFinite(at)) {
      tellAge(mb, element, at);
    }
  }
}

/** An actor, as the shell draws every person (docs/design-system.md, "Actor Identity"): the
 * SDK's identity, the avatar's box and then the bold name, with GitHub's avatar in the box
 * where the record carries one that passes `avatarUrl`. The image is decorative beside the
 * same visible name, never a replacement for it.
 *
 * When the image loads is its placement's (docs/design-system.md, "A Repaint Keeps Its
 * Images"). Lazy, the default, leaves an avatar the reader has not scrolled to unasked, as
 * the conversation's are: its sections are kept across tabs and polls. A placement whose
 * avatar a repaint builds again passes `eager`, as the header does when its actor or avatar
 * changes: in WebKit, the macOS app's engine, a lazy image waits for layout and then asks
 * the network again, and when the header built its actor on every tab switch and poll the
 * unchanged avatar had no image for that round trip after each one.
 *
 * An author with no usable avatar keeps the box, holding the shell's person glyph, in the
 * header and on a Conversation card head: the name starts where it would beside an avatar,
 * as a commit's author's does on its page, and the timeline's line meets the head where an
 * avatar would be (docs/design-system.md, "Conversation Timeline"). A Pulls row passes
 * `placeholder: false`, and its name stays where it is.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {string} name
 * @param {unknown} url
 * @param {string} [className]
 * @param {{loading?: "lazy" | "eager", placeholder?: boolean}} [options]
 * @returns {HTMLElement}
 */
export function authorLabel(
  mb,
  name,
  url,
  className = "",
  { loading = "lazy", placeholder = true } = {},
) {
  return mb.actorIdentity(name, {
    avatar: avatarUrl(url),
    loading,
    placeholder,
    className: "github-pull-identity",
    nameClass: `github-pull-author${className ? ` ${className}` : ""}`,
  });
}

/**
 * A stack member's author, as the stack menu and a stack's page draw it at the end of its
 * member row (`stackMemberRow`): as a Pulls row draws one, no box where it has no avatar,
 * and its avatar asked for once the row is drawn (docs/design-system.md, "Actor Identity").
 *
 * @param {MetabrowserPublicSdk} mb
 * @returns {(login: string, avatar: string | null) => HTMLElement}
 */
export function stackMemberIdentity(mb) {
  return (login, avatar) =>
    authorLabel(mb, login, avatar, "github-pull-stack-member-author", { placeholder: false });
}

/**
 * Give *node* its own text as a tooltip whenever it is cut short, until *signal*, if any,
 * aborts.
 *
 * @template {HTMLElement} T
 * @param {T} node
 * @param {AbortSignal} [signal]
 * @returns {T}
 */
export function tipWhenCut(node, signal) {
  node.addEventListener(
    "pointerenter",
    () => {
      if (node.scrollWidth > node.clientWidth) {
        node.dataset.tipText = node.textContent ?? "";
      } else {
        delete node.dataset.tipText;
      }
    },
    { signal },
  );
  return node;
}

/**
 * A page's title heading, a pull request's or a stack's: *icon* in the state icon's slot,
 * the title's *words*, and the number. The number is outside the clamped text, so a title
 * cut short keeps it.
 *
 * @param {Node} icon
 * @param {Array<Node | string>} words
 * @param {number} number
 */
export function titleHeading(icon, words, number) {
  const titleText = h("span", { class: "github-pull-title-text" }, words);
  const heading = h(
    "h1",
    { class: "page-heading github-pull-title github-pull-title-with-state" },
    [icon, titleText, " ", h("span", { class: "github-pull-number" }, [`#${number}`])],
  );
  return { heading, titleText };
}

/**
 * The header of a pull request's page or a stack's, and the lines both have, empty
 * (docs/design-system.md, "Page Headers"), in the order both put them under the title:
 *
 * - `opened`, the row of ages, which a state's badge leads: a pull request's one badge, a
 *   stack's tally of its members' states (`stateBadge`), then the ages (`agesLine`), and at
 *   its end a stack chip's slot, whose strut (`rowStrut`) holds it at a chip's height.
 * - `meta`, the author's row: its lead (`meta.lead`) holds the sentence (`meta.details`), the
 *   actor and the action, then the freshness note (`meta.note`), a muted dot (`meta.sep`) and
 *   the note's words (`meta.line`) in a slot as wide as its widest age (`meta.sizer`), so the
 *   age ticking from "just now" to "12 min ago" changes its width not at all (mb-ne91). The
 *   sentence and the note share the lead, which the note leaves whole, dot and all, where it
 *   cannot be whole beside the sentence, so the sentence never gives up width to it; alone on
 *   the row it is cut short with its text as a tooltip. The row is its lead alone, a line
 *   tall. `showNote` writes the note.
 * - `branches`, the head and base branches, on a line of their own, a line tall while there
 *   are none to show.
 * - `labels`, the row of labels (`labels.list`, `labelChip`), there only while there are
 *   labels or they are not known yet.
 * - `status`, the status line (`statusLine`), there only while it has something to say.
 * - `size`, the change set's size line, and `summary`, its Diff summary, whose class carries
 *   the diff plugin's styles for a summary.
 *
 * Each page fills them and puts them in its header.
 */
export function pageHeaderParts() {
  const line = tipWhenCut(h("span", { class: "github-pull-freshness mb-refreshing-muted" }));
  const sizer = h("span", { class: "github-pull-freshness-sizer", "aria-hidden": "true" });
  const sep = h("span", { class: "github-pull-note-sep", "aria-hidden": "true" }, ["·"]);
  const note = h("span", { class: "github-pull-note" }, [
    sep,
    h("span", { class: "github-pull-freshness-slot" }, [line, sizer]),
  ]);
  const details = h("span", { class: "github-pull-meta-details" });
  const lead = h("span", { class: "github-pull-meta-lead" }, [details, note]);
  const list = h("div", { class: "github-pull-label-list" });
  return {
    header: h("div", { class: "github-pull-header page-header page-reading-column" }),
    opened: h("div", { class: "github-pull-opened page-header-line" }),
    meta: {
      row: h("div", { class: "github-pull-meta page-header-line" }, [lead]),
      lead,
      details,
      note,
      sep,
      line,
      sizer,
    },
    branches: h("div", { class: "github-pull-branches page-header-line" }),
    labels: { row: h("div", { class: "github-pull-labels" }, [list]), list },
    status: h("div", { class: "github-pull-status page-header-line" }),
    size: h("div", { class: "github-pull-size page-header-line page-header-size" }),
    summary: h("div", { class: "github-pull-summary metabrowser-diff-host page-header-line" }),
  };
}

/**
 * Write *text* in an author's row's freshness note (`pageHeaderParts`'s `meta`), or take the
 * note away with null; *sized* holds its slot as wide as its widest age (`widestNote`), for
 * a note that says an age. The dot is there only after a sentence (*after*). Writes only
 * what changed, so the age's breathing while a refresh runs is one animation.
 *
 * @param {ReturnType<typeof pageHeaderParts>["meta"]} meta
 * @param {string | null} text
 * @param {{sized: boolean, after: boolean}} how
 */
export function showNote(meta, text, { sized, after }) {
  meta.note.hidden = text === null;
  meta.sep.hidden = !after;
  if (meta.line.textContent !== (text ?? "")) {
    meta.line.textContent = text ?? "";
  }
  const width = text !== null && sized ? widestNote(text) : "";
  if (meta.sizer.textContent !== width) {
    meta.sizer.textContent = width;
  }
}

/**
 * A state's badge, as a pull request's header leads its row of ages with it: *label* in the
 * state's ink and edge (`data-state`, github/styles.css), its first letter a capital. A
 * pull request's says its state, "Merged", and a stack's tally one state's members, "2 Pulls
 * Merged". *kind* is another badge's, a review's or a check's.
 *
 * @param {string} state
 * @param {string} label
 * @param {string} [kind]
 */
export function stateBadge(state, label, kind = "state") {
  return h(
    "span",
    { class: `file-header-badge github-pull-badge github-pull-${kind}`, "data-state": state },
    [`${label.charAt(0).toUpperCase()}${label.slice(1)}`],
  );
}

/**
 * The row of ages' words (`pageHeaderParts`'s `opened`): the ages, muted, given way first,
 * cut short at their end, and the links after them whole (`.github-pull-ages-links`).
 *
 * @param {Array<Node | string>} ages
 * @param {Array<Node | string>} [links]
 */
export function agesLine(ages, links = []) {
  return h("div", { class: "github-pull-quiet" }, [
    h("span", { class: "github-pull-ages" }, ages),
    ...(links.length === 0 ? [] : [h("span", { class: "github-pull-ages-links" }, links)]),
  ]);
}

/**
 * A hidden chip of no width, which gives a row a chip's height whatever else it holds: the
 * row of ages ends in one where it has no stack chip, on a pull request's page and a stack's
 * alike, so the two rows are one height.
 */
export function rowStrut() {
  return h(
    "span",
    { class: "btn github-pull-stack-trigger github-pull-stack-strut", "aria-hidden": "true" },
    [h("span", { class: "github-pull-stack-icon" }), " "],
  );
}

/**
 * Write the size line's *counts* into *row* (`mb.changeSizeLine`), only when what it says
 * changes: its text and its bytes, since rounded sizes can share text across the file size
 * style's threshold. A pull request's page and a stack's write theirs alike.
 *
 * @param {MetabrowserPublicSdk} mb
 * @param {HTMLElement} row
 * @param {{commits?: number, files: number | null, pushedBytes: number | null,
 *   diffBytes: number | null}} counts
 */
export function paintSizeLine(mb, row, counts) {
  const line = mb.changeSizeLine(counts);
  const key = JSON.stringify([line.text, counts.pushedBytes, counts.diffBytes]);
  if (row.dataset.sizeKey !== key) {
    row.dataset.sizeKey = key;
    row.replaceChildren(...mb.changeSizeLineNodes(line));
  }
}

/**
 * The author's row's sentence (`pageHeaderParts`'s `meta.details`): each actor, the shell's
 * actor identity (`authorLabel`), then the action (`actionText`), "wants to merge 1 commit";
 * with no actor, the action alone. A stack's names each of its authors once, a comma after
 * each but the last. `identity` draws one actor and *action* is the action's node, so a page
 * may keep both across paints.
 *
 * @param {Array<{login: string, avatar: string | null}>} actors
 * @param {(actor: {login: string, avatar: string | null}) => HTMLElement} identity
 * @param {HTMLElement} action
 * @returns {HTMLElement[]}
 */
export function actorSentence(actors, identity, action) {
  return [
    ...actors.flatMap((actor, at) => [
      identity(actor),
      ...(at < actors.length - 1 ? [h("span", { class: "github-pull-actor-sep" }, [","])] : []),
    ]),
    action,
  ];
}

/**
 * The sentence's action, after its actor with a space.
 *
 * @param {string} action
 * @param {boolean} afterActor
 */
export function actionText(action, afterActor) {
  return h("span", { class: "github-pull-action" }, [`${afterActor ? " " : ""}${action}`]);
}

/**
 * The pending placeholders of a header's Diff summary and size line, while the comparison
 * they are drawn from is on its way (mb-onr2): the navigation tally's gray block and slow
 * pulse (`.tally-pending`), after the quiet period (`.mb-delayed-loading`), where the
 * summary's header and the size line will be. The reveal wrapper and the block are separate
 * nodes, as a pending section's are; a page keeps them across paints, so a wait's quiet
 * period and pulse run once.
 */
export function summaryPlaceholders() {
  return {
    summary: h(
      "span",
      {
        class: "mb-delayed-loading github-pull-summary-pending",
        role: "status",
        "aria-label": "Loading the summary of changes",
      },
      [h("span", { class: "tally-pending", "aria-hidden": "true" })],
    ),
    size: h("span", { class: "mb-delayed-loading github-pull-size-pending" }, [
      h("span", { class: "tally-pending", "aria-hidden": "true" }),
    ]),
  };
}

/**
 * The parts of a header's status line (docs/design-system.md, "The Pull Request Page"),
 * a pull request's and a stack's: a message muted, a failure in the warning's ink and cut
 * short with its text as a tooltip, and at the line's end what it asks of the reader, its
 * text actions and offers, so a message or failure changing its width moves nothing after
 * it. `failed` marks a line whose failure may wrap, since it carries its remedy.
 */
export const statusLine = Object.freeze({
  /** @param {string} text */
  message: (text) => h("span", { class: "github-pull-message" }, [text]),
  /**
   * @param {string} text
   * @param {AbortSignal} [signal]
   */
  failure: (text, signal) =>
    tipWhenCut(h("span", { class: "github-pull-failure" }, [text]), signal),
  /** The line's end, which holds its actions and offers. */
  end: () => h("span", { class: "github-pull-status-end" }),
  /**
   * A text action, such as Retry or Fetch: a text action, as the line's offers are links,
   * so the line is no taller than its text.
   *
   * @param {string} label
   */
  action: (label) =>
    h("button", { type: "button", class: "github-pull-text-action github-pull-remedy" }, [label]),
  /**
   * An offer: its sentence is cut short before its control is, so a narrow pane still
   * shows the control inside the header (styles.css, "The offers").
   *
   * @param {Array<Node | string>} sentence
   * @param {HTMLElement} control
   * @param {AbortSignal} [signal]
   */
  offer: (sentence, control, signal) =>
    h("span", { class: "github-pull-offer" }, [
      tipWhenCut(h("span", { class: "github-pull-offer-text" }, sentence), signal),
      " ",
      control,
    ]),
  /**
   * @param {HTMLElement} line
   * @param {boolean} failed
   */
  failed: (line, failed) => line.classList.toggle("github-pull-status-failed", failed),
});

/**
 * Docs or Changes held as a pull request's page holds them, in *body*: the diff's host,
 * and under it the shell's delayed loading block, so progress cannot move the diff's first
 * row. `hold` keeps the diff out of sight (`.github-pull-diff-holding`) from its first
 * draw; `firstScreen` waits until its first screen's Markdown waits no more, at most
 * `CHANGES_FIRST_SCREEN_MS`, and says which came first, "met" or "bound", or null for a
 * mount with no first screen to wait for, so the first screen the reader sees is the one
 * that stays; `release` takes the block away and shows the diff.
 *
 * @param {HTMLElement} body
 */
export function holdDiff(body) {
  const host = h("div", { class: "github-pull-diff metabrowser-diff-host" });
  const loading = h(
    "div",
    {
      class: "loading mb-delayed-loading github-pull-diff-loading",
      role: "status",
      "aria-label": "Loading changes",
    },
    [h("span", { class: "spinner", "aria-hidden": "true" })],
  );
  body.replaceChildren(host, loading);
  return {
    host,
    loading,
    hold() {
      host.classList.add("github-pull-diff-holding");
    },
    /**
     * @param {unknown} mounted
     * @returns {Promise<"met" | "bound" | null>}
     */
    async firstScreen(mounted) {
      const firstScreen = /** @type {{firstScreen?: () => Promise<void>} | null} */ (mounted)
        ?.firstScreen;
      if (typeof firstScreen !== "function") {
        return null;
      }
      /** @type {ReturnType<typeof window.setTimeout> | undefined} */
      let bound;
      const outcome = await Promise.race([
        firstScreen.call(mounted).then(() => /** @type {const} */ ("met")),
        new Promise((resolve) => {
          bound = window.setTimeout(() => resolve("bound"), CHANGES_FIRST_SCREEN_MS);
        }),
      ]);
      window.clearTimeout(bound);
      return /** @type {"met" | "bound"} */ (outcome);
    },
    release() {
      loading.remove();
      host.classList.remove("github-pull-diff-holding");
    },
  };
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
 * A stack member's state for the stack menu's line: the page's own for the pull request it
 * shows, as its header says it, and what the repository's list of pull requests last said of
 * any other (`listedState`), or null where the list has not said, as for a member it has not
 * reached.
 *
 * @param {string | null} source
 * @param {number} target
 * @param {number} number The page's pull request.
 * @param {import("./pull-state.js").PullState | null} current The page's state for it.
 * @returns {import("./pull-state.js").PullState | null}
 */
export function stackMemberState(source, target, number, current) {
  return target === number ? current : (listedState(source, target)?.state ?? null);
}

/**
 * A stack member's author for the stack menu's line (mb-x0z1): *own*, the page's author, for
 * the pull request the page shows, and for any other the author the stacks route read with
 * its title from the repository's cached list (pull_stacks_route.py), or null where the
 * list does not hold the member.
 *
 * @param {import("./pull-stacks.js").NativeStack} stack
 * @param {number} at The member's index in `stack.pulls`.
 * @param {{login: string, avatar: string | null} | null} own
 * @returns {{login: string, avatar: string | null} | null}
 */
export function stackMemberAuthor(stack, at, own) {
  if (own !== null) {
    return own;
  }
  const login = stack.authors[at];
  return login ? { login, avatar: stack.avatars[at] ?? null } : null;
}

/**
 * The native stack's compact trigger and lazy, keyboard-navigable member menu. Its words
 * are the shared stack design's (docs/design-system.md, "Stacks"): the trigger is the
 * position badge, the menu's heading is the stack's label, and its members come in
 * `stackMenuOrder`, the order the Pulls tab's stack groups list them in.
 *
 * Every member is one line in one layout (mb-as06): the pull request's state icon, its title,
 * the SDK's `titleNodes` (docs/design-system.md, "Titles"), cut short with the whole title in
 * its tip, and at the line's end its place in the stack in bold, "14/15", a muted dot, its
 * number, and another dot and its author, in a Pulls row's order (mb-pw8t, mb-x0z1). The state
 * is `deps.state`'s, read again each time the menu opens or the page repaints, and the author
 * the stack's (`stackMemberAuthor`), the page's own, `deps.author`'s, for its pull request; a
 * member whose state is not known yet keeps the icon's slot empty, so every member's place
 * starts at one edge, and one whose author is not known has no dot and no author. The current
 * member is marked by the Pulls list's current-row mark and
 * `aria-current`, not by a check before its icon.
 *
 * A pull request in more than one stack has a trigger for each, and each then names its
 * stack before its position, "300 2/2", as a Pulls row's place names every stack but its
 * own (`named`, and `update`'s): two bare positions told the stacks apart only by their
 * tips. However it opens, by a press, Enter, Space, `↓`, or `↑`, focus lands on the
 * current member, the row marked, as a filter's menu opens on its checked row
 * (docs/design-system.md, "Keys in a Menu"); Escape closes it and gives focus back to the
 * trigger.
 *
 * With `wholeStack`, the menu's first row, **Whole stack**, opens the stack's own page
 * (`/stack/<n>`, stack-page.js), before the members, in `stackEntries`' order, which an open
 * stack's rows in the Pulls tab take too, and in a member's row grid: the stack's Layers
 * glyph in the icon's slot, and its words where every member's title starts (mb-7cn4).
 * @param {import("./pull-stacks.js").NativeStack} initial
 * @param {number} number
 * @param {{link(number: number): HTMLElement, wholeStack?: (stack: number) => HTMLElement, icon: Element | null, currentTitle: string, titleNodes(title: string): Array<Node | string>, onOpen(): void, named?: boolean, state?(number: number): import("./pull-state.js").PullState | null, author?(): {login: string, avatar: string | null} | null, identity?(login: string, avatar: string | null): HTMLElement, menus?: MetabrowserMenus}} deps
 */
export function createStackMenu(initial, number, deps) {
  let stack = initial;
  let currentTitle = deps.currentTitle;
  let named = deps.named === true;
  const position = stack.pulls.indexOf(number);
  /** The trigger's position, named by its stack when the pull request is in another too.
   * @param {number} at */
  const shownPosition = (at) =>
    namedStackPosition(stackPosition(at, stack.pulls.length), named ? stack.number : null);
  const count = h("span", { class: "github-pull-stack-position" }, [shownPosition(position)]);
  const menuId = `github-pull-stack-menu-${++stackMenuSerial}`;
  const root = /** @type {HTMLDetailsElement} */ (
    h("details", { class: "github-pull-stack-disclosure" })
  );
  const trigger = h(
    "summary",
    {
      class: "btn github-pull-stack-trigger disclosure-toggle",
      "aria-label": `Navigate ${stackPositionHint(stack, position)}`,
      // The tip says in words the stack and the place the glyph and position show.
      "data-tip-text": stackPositionHint(stack, position),
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
  // The menu's rows are all one group, so its heading names the menu itself
  // (docs/design-system.md, "Groups in a Menu"): one name, read once.
  const labelId = `${menuId}-heading`;
  const menu = h("div", {
    class: "menu github-pull-stack-menu",
    id: menuId,
    role: "menu",
    "aria-labelledby": labelId,
  });
  root.append(trigger);
  const listening = new AbortController();
  const signal = listening.signal;
  // It closes as every menu does (docs/design-system.md, "Every Menu Closes Alike").
  const dismissal = deps.menus?.dismissible({
    name: "github-pull-stack-menu",
    trigger,
    inside: (node) => menu.contains(node),
    isOpen: () => root.open,
    close: () => close(),
  });
  /** @type {HTMLElement[]} */
  const links = [];
  /**
   * Each member's row (`stackMemberRow`), which changes only what a repaint changes.
   * @type {Map<number, import("./stack-member-row.js").StackMemberRow>}
   */
  const rows = new Map();
  // The members under the heading that names them and the menu: the host's group
  // look, with no group role, since a menu of one group is named by its heading. The
  // heading is the stack's label, which a Pulls stack group's row is headed by too
  // (docs/design-system.md, "Stacks").
  const label = h("div", { class: "group-heading github-pull-stack-label", id: labelId }, [
    stackLabel(stack.number),
  ]);
  const group = h("div", { class: "menu-group" });
  /** The Whole stack row, made once, for the stack the menu was made for. It is no member,
   * so it takes none of a member's classes, and the keys move over it as over a member.
   * @type {HTMLElement | null} */
  let whole = null;
  let populated = false;

  // The Whole stack row is in a member's row grid (github/styles.css,
  // `.github-pull-stack-whole`; mb-7cn4): the stack's Layers glyph in the state icon's slot,
  // as a Pulls stack's row has it, and its words where every member's title starts.
  function wholeRow() {
    if (whole === null && deps.wholeStack) {
      whole = deps.wholeStack(stack.number);
      whole.setAttribute("class", "menu-item github-pull-stack-whole");
      whole.setAttribute("role", "menuitem");
      whole.setAttribute("tabindex", "-1");
      whole.replaceChildren(
        h("span", { class: "github-pull-stack-icon", "aria-hidden": "true" }, [
          deps.icon === null ? null : document.importNode(deps.icon, true),
        ]),
        h("span", { class: "github-pull-stack-member-copy" }, [
          h("span", { class: "github-pull-stack-member-title" }, [WHOLE_STACK]),
        ]),
      );
    }
    return whole;
  }

  /**
   * Each drawn member's line, from the stack, `deps.state`, and its author
   * (`stackMemberAuthor`): its title, or the page's own for its pull request, its place,
   * its state, and its author where the menu has an identity to draw it with.
   */
  function updateMembers() {
    for (let at = 0; at < stack.pulls.length; at += 1) {
      const target = stack.pulls[at];
      const row = rows.get(target);
      if (!row) {
        continue;
      }
      row.show({
        number: target,
        place: stackPosition(at, stack.pulls.length),
        title: stack.titles?.[at] || (target === number ? currentTitle : null),
        state: deps.state?.(target) ?? null,
        author:
          deps.identity === undefined
            ? null
            : stackMemberAuthor(stack, at, target === number ? (deps.author?.() ?? null) : null),
      });
    }
  }

  /** @param {boolean} [reorder] */
  function populate(reorder = false) {
    if (populated && !reorder) {
      // Opened again: the members as they are now, a state the Pulls list has learned since.
      updateMembers();
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
    // The stack's rows in the one order the Pulls tab's open stack has them too
    // (`stackEntries`): the Whole stack row, where the menu has one, then the members.
    for (const target of stackEntries(stackMenuOrder(stack))) {
      if (target === null) {
        const entry = wholeRow();
        if (entry !== null) {
          links.push(entry);
        }
        continue;
      }
      let row = rows.get(target);
      if (!row) {
        const link = deps.link(target);
        link.setAttribute("class", "menu-item github-pull-stack-member");
        link.setAttribute("role", "menuitem");
        link.setAttribute("tabindex", "-1");
        if (target === number) {
          link.setAttribute("aria-current", "page");
        }
        // The member row the stack's page draws too (stack-member-row.js): the state icon, the
        // title, and at the line's end the place, the number, and the author, "14/15 · #N ·
        // jlevy" (mb-1kzu, mb-pw8t, mb-x0z1); the place, the dot, and the number never give
        // way, the author gives way only past its share of the line, and the title is cut
        // short before them.
        row = stackMemberRow(link, deps.titleNodes, deps.identity);
        rows.set(target, row);
      }
      links.push(row.link);
    }
    updateMembers();
    group.replaceChildren(label, ...links);
    if (!populated) {
      menu.append(group);
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
    dismissal?.closed();
    trigger.setAttribute("aria-expanded", "false");
    if (focus && trigger.isConnected) {
      trigger.focus({ preventScroll: true });
    }
  }

  /** Bring *link* into the menu's own view, scrolling the menu and never the page: the
   * menu opening is not a reason to move the page under it.
   * @param {HTMLElement} link */
  function reveal(link) {
    const top = link.offsetTop;
    const bottom = top + link.offsetHeight;
    if (top < menu.scrollTop) {
      menu.scrollTop = top;
    } else if (bottom > menu.scrollTop + menu.clientHeight) {
      menu.scrollTop = bottom - menu.clientHeight;
    }
  }

  /** Put focus on the current member, the row the menu opens on, or the first row. */
  function focusCurrent() {
    const target = links.find((link) => link.getAttribute("aria-current") === "page") ?? links[0];
    if (target) {
      target.focus({ preventScroll: true });
      reveal(target);
    }
  }

  root.addEventListener(
    "toggle",
    () => {
      trigger.setAttribute("aria-expanded", String(root.open));
      if (root.open && !signal.aborted) {
        dismissal?.opened();
        populate();
        deps.onOpen();
        // A press opens the menu here, with focus on the trigger; a key that opened it
        // has put focus in it already.
        if (!menu.contains(document.activeElement)) {
          focusCurrent();
        }
      }
    },
    { signal },
  );
  root.addEventListener(
    "keydown",
    (event) => {
      // A key held with Command, Control, or Option is the browser's: Command-R
      // reloads, Command-Left goes back, and Command-Down scrolls to the end.
      if (event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      const key = event.key;
      if (event.target === trigger && (key === "Enter" || key === " ")) {
        event.preventDefault();
        event.stopPropagation();
        if (root.open) {
          close();
        } else {
          root.open = true;
          trigger.setAttribute("aria-expanded", "true");
          dismissal?.opened();
          populate();
          deps.onOpen();
          focusCurrent();
        }
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
      const at = links.indexOf(/** @type {HTMLElement} */ (document.activeElement));
      // On the trigger, Home and End are left alone, as on a filter's trigger: the arrows
      // open the menu, on its current member, and Home and End move within it.
      if (at < 0 && (key === "Home" || key === "End")) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      if (at < 0) {
        root.open = true;
        trigger.setAttribute("aria-expanded", "true");
        dismissal?.opened();
        populate();
        deps.onOpen();
        focusCurrent();
        return;
      }
      const next =
        key === "Home"
          ? 0
          : key === "End"
            ? links.length - 1
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
  return Object.freeze({
    element: root,
    close,
    /** A title or membership update keeps the menu open and retains surviving link focus.
     * A repaint with neither still draws a member's state anew where it changed, as the
     * page's own does when another actor merges it.
     * @param {import("./pull-stacks.js").NativeStack} next
     * @param {string} title
     * @param {boolean} [nextNamed] Whether the pull request is in another stack too.
     */
    update(next, title, nextNamed = false) {
      if (next === stack && title === currentTitle && nextNamed === named) {
        updateMembers();
        return;
      }
      const reordered =
        stack.pulls.length !== next.pulls.length ||
        stack.pulls.some((target, index) => target !== next.pulls[index]);
      stack = next;
      currentTitle = title;
      named = nextNamed;
      const at = stack.pulls.indexOf(number);
      count.textContent = shownPosition(at);
      trigger.setAttribute("aria-label", `Navigate ${stackPositionHint(stack, at)}`);
      trigger.setAttribute("data-tip-text", stackPositionHint(stack, at));
      if (populated && reordered) {
        populate(true);
      } else {
        updateMembers();
      }
    },
    dispose() {
      listening.abort();
      close();
      dismissal?.dispose();
    },
  });
}

/**
 * Give the page's tab links their keys through the SDK's shortcut
 * surface. A key runs `setTab`, the page handle's own path, which moves the address as a
 * click on the link does. The links are kept across paints, so each key lasts until
 * `signal` aborts, as the page's disposal aborts it. Returns one handle per link, in
 * order, or none on a host without the surface.
 *
 * A stack's page gives its tabs the same keys, with its own word for whose tab it is.
 *
 * @param {MetabrowserPublicPluginShortcutsApi | undefined} shortcuts
 * @param {ReadonlyArray<{id: string, link: HTMLElement}>} tabLinks
 * @param {(tab: string) => void} setTab
 * @param {AbortSignal} signal
 * @param {string} [owner] Whose tabs they are, in Help's words.
 * @returns {MetabrowserPublicPluginShortcutHandle[]}
 */
export function attachTabKeys(shortcuts, tabLinks, setTab, signal, owner = "pull request") {
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
          description: `Show the ${owner}’s ${tab.label} tab.`,
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
 * Number the header's situational controls, its links and one-off actions, through the
 * SDK's shortcut surface: each takes 1 to 9 from its place on screen, as the shell's
 * numbered controls do, so nothing here picks a digit (docs/design-system.md, "Keyboard
 * Shortcuts"). *held* maps what a control does, such as `remedy`, to its handle and the
 * action it runs now. Each paint passes every control it shows, and each runs the action
 * that paint gave it: a control the header kept is the same element, which keeps its
 * number; one the header built again because what it shows changed moves its number to
 * the new element; one no longer shown lets its number go, and one shown for the first
 * time takes one. Each lasts until *signal* aborts, as the page's disposal aborts it.
 *
 * @param {MetabrowserPublicPluginShortcutsApi | undefined} shortcuts
 * @param {Map<string, {handle: MetabrowserPublicPluginShortcutHandle, run: () => unknown}>} held
 * @param {ReadonlyMap<string, {element: HTMLElement, run: () => unknown}>} controls
 * @param {AbortSignal} signal
 */
export function numberHeaderControls(shortcuts, held, controls, signal) {
  if (typeof shortcuts?.attach !== "function") {
    return;
  }
  for (const [name, entry] of held) {
    if (!controls.has(name)) {
      entry.handle.detach();
      held.delete(name);
    }
  }
  for (const [name, control] of controls) {
    const entry = held.get(name);
    if (entry) {
      entry.run = control.run;
      entry.handle.retarget(control.element);
      continue;
    }
    /** @type {{handle: MetabrowserPublicPluginShortcutHandle, run: () => unknown}} */
    const next = {
      handle: shortcuts.attach(control.element, {
        activate: () => next.run(),
        id: `github.pull.header.${name}`,
        numbered: true,
        signal,
      }),
      run: control.run,
    };
    held.set(name, next);
  }
}

/**
 * The dot between the Checks summary's counts, "3 success · 1 failure": muted and hidden
 * from a screen reader, which is told a comma in its place.
 */
const CHECKS_SEPARATOR = Object.freeze({ separator: "·", spoken: ", " });

/**
 * Mount the page into *container*. Browser only.
 *
 * @param {HTMLElement} container
 * @param {MetabrowserPublicRenderContext} ctx
 * @param {MetabrowserPublicSdk} mb
 */
export function mountPullPage(container, ctx, mb) {
  const number = typeof ctx.number === "number" ? ctx.number : 0;
  const checkoutPin = window.METABROWSER_SOURCE_CHECKOUT?.working_tree === false;
  const open = typeof ctx.open === "function" ? ctx.open : () => {};
  container.classList.add("github-pull");
  // The shared page header's lines start with state and ages beneath the title and end
  // with the Diff summary (docs/design-system.md, "Page Headers"); the lines a stack's page
  // has too are `pageHeaderParts`'s.
  const {
    header,
    opened: openedRow,
    meta,
    branches: branchesRow,
    labels: { row: labelsRow, list: labelList },
    status,
    size: sizeRow,
    summary: summaryRow,
  } = pageHeaderParts();
  const { row: stateRow, details: stateDetails } = meta;
  const body = h("div", { class: "github-pull-body" });
  // The header's box is decided at first paint: every row is there in every state, at one
  // line each, so nothing that arrives later, a stack, a label's color, a Refresh, the age
  // ticking, a rate limit's hold, moves the tab bar or the rows below it. Two rows depend on
  // what the page has to say. The labels row is held while the labels are unknown, and not
  // there for a pull request with none (mb-2u08). The status line is there only for a
  // failure, a message, or an offer, so those, and only those, move the tab bar as they come
  // and go (mb-ne91). docs/design-system.md, "The Pull Request Page".
  // A stack's chip arrives from its own /stacks answer, so it has a slot at the right end of
  // the row of ages, ending under the end of the title's number (mb-646g, mb-dwha), with
  // nothing after it: arriving, it lands in the row's empty end and moves nothing, and where
  // the row has no room left the ages give way, cut short at their end as in a narrow pane,
  // with Browse code after them, and the row never takes a second line. The page's Refresh
  // once held a slot after Browse code and kept the chip a Refresh's width short of the
  // number; the page has none now (mb-ablv). With no stack the slot holds a strut, which
  // gives the row a chip's height (`rowStrut`). At the end of the author's row (mb-cf0l)
  // it was a row below the state and ages it belongs with; at the end of the row that also
  // held the branches, a chip took its width from the sentence and the merge, which slid up
  // to 35 px.
  const stackStrut = rowStrut();
  const stackColumn = h("div", { class: "github-pull-stacks" }, [stackStrut]);
  const stateSlot = h("span", { class: "github-pull-state-slot" });
  // The author's sentence ends in a muted note of how fresh what is shown is, one time
  // (mb-ne91): "jlevy wants to merge 1 commit · Fetched just now via GitHub CLI". A rate
  // limit's hold is said in its place, since it begins and lifts by itself and asks nothing of
  // the reader. Before a record is shown the note is the page's word on it, "Fetching the pull
  // request…", so the sentence landing changes no line. The note and its age are kept across
  // paints, so the age's breathing while a refresh runs is one animation from start to end
  // rather than one restarted at each paint. The note's slot is as wide as its widest age
  // (`meta.sizer`, `showNote`), so the age ticking from "just now" to "12 min ago" changes
  // its width not at all; `pageHeaderParts` says how the sentence and the note share the
  // row. Refresh is not in the note, which can leave: it ends the row of ages, with the
  // stack's chip just before it.
  // The head and base branches (`branchesRow`) are on a line of their own under the author's
  // sentence: a line tall, the merge's arrow's, while no record is shown too.
  // The pull request's state leads the row of its ages (`openedRow`): its badge, then when
  // it was opened, updated, merged, or closed, and at its end the stack's chip.
  // The pull request's Diff summary, the header's last row, above the tabs and on every one
  // of them (mb-pb35): its header the change set's file and line totals, its tree the
  // changed files. Its row is held from first paint, so the summary arriving with the
  // comparison moves nothing (`summaryRow`).
  // While the page waits for the comparison its summary is drawn from, the row holds the
  // shell's pending placeholder (`summaryPlaceholders`).
  const { summary: summaryPending, size: sizePending } = summaryPlaceholders();
  // The change set's size line, the header's line above its Diff summary
  // (docs/design-system.md, "Change Size Line"): "2 commits · 36 files changed · 1.8 MB
  // compressed (6.2 MB raw diff)". It is there whenever the summary's row is, holding the
  // same pending placeholder while the summary waits, so neither row moves the tabs
  // (`sizeRow`).
  // A wait for the summary still running at the event log's late threshold says so in the
  // placeholder's place, with Details (mb-9zp5): a placeholder that only pulsed left the
  // reader no way to tell slow from stuck, nor anyone a record of it. A line tall, as the
  // placeholder is, so it moves nothing.
  const summaryLateText = h("span", { class: "github-pull-summary-late-text" });
  const summaryLate = h("span", { class: "github-pull-summary-late", role: "status" }, [
    summaryLateText,
  ]);
  let summaryLateShown = false;
  // The Details a failure or a late wait offers: the event log's records for it, read when
  // the reader asks (static/event-reports.js, showDetails), as the header's last row while
  // open. One panel, for the control that opened it last.
  const detailsId = `github-pull-details-${number}`;
  const detailsPanel = h("div", {
    class: "event-log-details github-pull-details",
    id: detailsId,
    role: "region",
    "aria-label": "Event log details",
  });
  /** @type {{button: HTMLElement, reading: AbortController} | null} */
  let detailsOpen = null;
  header.append(stateRow);
  // The status line: what the page has to say beyond the note, a failure and its remedy, a
  // message, and the offers, one of the header's metadata lines, a line tall as the author's
  // row is, there only while it has something to say. Its controls are text actions, a line
  // tall (mb-2u08). The row of ages is a stack chip's height (mb-646g). It is `status`.
  /** Commits of the conversation are being read from GitHub for the record shown. */
  let timelineBusy = false;
  let stackIndex = createStackIndex(null);
  /** @type {import("./pull-stacks.js").StackIdentity | null} */
  let stackIdentity = null;
  let stackKey = "";
  let preferredStack = 0;
  /** The state the page shows, which its stack menus give its own member: the header's.
   * @type {import("./pull-state.js").PullState | null} */
  let stackPullState = null;
  /** The author the page shows, which its stack menus give its own member (mb-x0z1).
   * @type {{login: string, avatar: string | null} | null} */
  let stackPullAuthor = null;
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
  /** The record or core preview the conversation last asked for Markdown from. @type {string | null} */
  let markdownRevision = null;
  /** @type {Map<string, HTMLElement>} */
  const texts = new Map();
  /** The text each text element shows, which its Markdown must be of. @type {WeakMap<Element, string>} */
  const textOf = new WeakMap();
  /**
   * Why a text shows plain, by part, while that text is the one shown: a text element
   * rebuilt on the same record is not asked for its Markdown again, so it says why from
   * here, and a render that arrives later takes the note away.
   *
   * @type {Map<string, {text: string, note: string}>}
   */
  const refusedNotes = new Map();
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
   *   final. A text whose Markdown cannot come is `failed` and waits no longer. The header
   *   paints the record at once, so the title shows without waiting; loading blocks that had
   *   shown stay over the body (`cover`) until it shows, so it never blinks empty.
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
   *   since: number,
   *   timer: ReturnType<typeof window.setTimeout>,
   * } | null}
   */
  let firstPaint = null;
  let firstPaintSpent = false;
  /** What the body last painted: another tab's content is never held on screen. */
  /** @type {"none" | "loading" | "conversation" | "checks" | "files" | "guided"} */
  let bodyShows = "none";
  /**
   * The Guided Review tab while it shows: the guide's view once its module loads, and the
   * description that introduces it.
   *
   * @typedef {{view: ReturnType<typeof import("./guided-review.js").mountGuidedReview> | null,
   *   introduction: {node: HTMLElement, key: string | null, block: HTMLElement | null}}} GuidedMount
   */
  /** @type {GuidedMount | null} */
  let guided = null;
  let active = false;
  /** @type {{revision: string, source: string, projection: TimelineProjection | null,
   *   settled: boolean, cacheMiss: boolean, retryPending: boolean, heldUntil: number | null,
   *   heldMs: number,
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
  /** The diff tab the mounted diff was drawn for (`diffTab`): Docs narrows it. */
  let diffShows = "";
  /** The comparison asked whether it changes a document (`askDocs`), and what it said. */
  let docsFor = "";
  /** @type {boolean | null} */
  let docsChanged = null;
  /** @type {AbortController | null} */
  let docsAsking = null;
  /**
   * The File type choice of Changes, null for every type: the page's, kept while the reader
   * is on another tab and given to each mount (the diff plugin's `ctx.types`).
   *
   * @type {Array<string> | null}
   */
  let diffTypes = null;
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
    // The shell's listener moved the address to the file; the button follows it.
    followCounterpart();
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
                showPending(/** @type {HTMLElement} */ (entry.target), part, value);
              }
            }
          },
          { root: pane, rootMargin: MARKDOWN_AHEAD },
        )
      : null;

  /**
   * An age, the one this page and a stack's page draw (`pullAge`).
   *
   * @param {string} iso
   * @param {{label: string, iso: string} | null} [also]
   */
  const age = (iso, also = null) => pullAge(mb, iso, also);

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
    // A message about the content, so sans under either reading font: the host's chrome
    // prose (docs/design-system.md, "Serif Is for Documents").
    const element = h("div", { class: "github-pull-text chrome-prose", "data-part": part });
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
    if (kept !== null && inert !== undefined) {
      element.append(kpressHost(inert, kept, element));
    } else {
      element.append(h("div", { class: "github-pull-plain" }, [value]));
      const refused = refusedNotes.get(part);
      if (refused?.text === value) {
        element.append(refusalNotice(refused.note));
      }
      showPending(element, part, value);
    }
    if (truncated) {
      element.append(notice("warning", ["This text was cut; the rest is on GitHub."]));
    }
    return element;
  }

  /**
   * Ask for the Markdown of the texts still plain: the description and the texts within
   * `MARKDOWN_AHEAD` of the view now, and the rest as they near it. The observer reports only
   * after the frame paints, so a text in view it asked for would show its source for a frame
   * first: a record's comments when it follows a core preview, whose first paint is spent.
   * Those are asked for here and marked pending before the frame. A hidden first paint asks
   * for its own first screen (`settleFirstPaint`), laid out where it will show.
   *
   * @param {HTMLElement[]} elements
   */
  function askForTexts(elements) {
    /** @type {[string, string, HTMLElement][]} */
    const plain = [];
    for (const element of elements) {
      const part = element.getAttribute("data-part");
      const value = textOf.get(element);
      if (part === null || value === undefined) {
        continue;
      }
      texts.set(part, element);
      if (element.querySelector(":scope > .github-pull-plain") !== null) {
        plain.push([part, value, element]);
      }
    }
    // Every box is read before any text is marked, so the layout is taken once.
    const now =
      observer === null || firstPaint?.mode === "hidden"
        ? null
        : plain.map(([part, , element]) => part !== "body" && nearViewNow(element));
    plain.forEach(([part, value, element], index) => {
      if (part === "body" || observer === null || now?.[index] === true) {
        controller.requestMarkdown(part, value);
        showPending(element, part, value);
      } else {
        observer.observe(element);
      }
    });
  }

  /**
   * Whether *element* is within `MARKDOWN_AHEAD` of the pane's view now, one view's height
   * above or below it, where the observer would find it after this frame. Not laid out, it
   * is not: the observer asks once it shows.
   *
   * @param {HTMLElement} element
   */
  function nearViewNow(element) {
    const box = boxOf(element);
    if (box === null || (box.width === 0 && box.height === 0)) {
      return false;
    }
    const top = (pane === null ? null : boxOf(pane))?.top ?? 0;
    const height = pane?.clientHeight || window.innerHeight || 0;
    return height > 0 && box.bottom > top - height && box.top < top + 2 * height;
  }

  /**
   * Renders answered and waiting to be inserted, for the allowlist and KPress's stylesheets,
   * by part, with the text each renders.
   *
   * @type {Map<string, string>}
   */
  const inserting = new Map();

  /**
   * Show a plain text as the placeholder while its Markdown is on its way: asked and not yet
   * answered, or answered and waiting to be inserted. Its source keeps its box out of sight
   * (`.github-pull-plain-pending`), so a text's first sight is its render; the source shows
   * only once its Markdown will not come, with the notice that says why. A text not asked for
   * yet, past `MARKDOWN_AHEAD` below the view, stays plain, so find-in-page reaches it.
   *
   * @param {HTMLElement} element
   * @param {string} part
   * @param {string} value
   */
  function showPending(element, part, value) {
    const plain = element.querySelector(":scope > .github-pull-plain");
    if (plain !== null && textOf.get(element) === value) {
      // A text already refused shows its source and says why while it is asked again, rather
      // than turn back into a placeholder under that line.
      plain.classList.toggle(
        "github-pull-plain-pending",
        refusedNotes.get(part)?.text !== value &&
          (controller.pending(part, value) || inserting.get(part) === value),
      );
    }
    textsChanged();
  }

  /** Tell each wait on texts (`textsSettled`) that one may have stopped waiting. */
  function textsChanged() {
    for (const check of [...pendingWatchers]) {
      check();
    }
  }

  /**
   * What waits for texts to stop waiting for their Markdown (`textsSettled`), told each time
   * one may have (`textsChanged`): as `showPending` marks a text, as a render replaces one
   * (`renderMarkdown`), or when the page is disposed.
   *
   * @type {Set<() => void>}
   */
  const pendingWatchers = new Set();

  /** @param {string} part */
  function showPendingPart(part) {
    const element = texts.get(part);
    const value = element === undefined ? undefined : textOf.get(element);
    if (element !== undefined && value !== undefined) {
      showPending(element, part, value);
    }
  }

  /** KPress's stylesheets, once. A text stays readable under the shell's if they fail. */
  /** @type {Promise<void> | null} */
  let documentStyles = null;

  /**
   * Load KPress's stylesheets for the page's texts, once, from the manifest a route answers
   * with: the Markdown route's for a description or comment, the guide's for Guided Review. Both
   * are `kpress_adapter.document_stylesheets`, so no text chooses what the page loads.
   *
   * @param {Parameters<MetabrowserPublicSdk["loadKpressAssets"]>[0]} assets
   * @returns {Promise<void>}
   */
  function textStyles(assets) {
    if (documentStyles === null) {
      // Only a load that succeeded lets later pages insert kept renders without asking again.
      documentStyles = mb.loadKpressAssets(assets).then(
        () => {
          kpressStylesSettled = true;
        },
        (error) => {
          console.warn("metabrowser github: the text styles did not load", error);
        },
      );
    }
    return documentStyles;
  }

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
   * never used, and no KPress script is loaded for it but the diagram modules a Mermaid block
   * asks for (`drawTextDiagrams`). static/inert-html.js parses it into an inert template and
   * inserts only nodes rebuilt from the same allowlist, links made absolute against the pull
   * request. The article and the classes on its tables and code blocks are the page's own.
   *
   * @param {MetabrowserInertHtmlRuntime} inert
   * @param {Record<string, any>} rendered
   * @param {Element} element The text element the host goes in.
   */
  function kpressHost(inert, rendered, element) {
    const article = h("article", { class: "kpress kpress-inert" }, [
      inertProse(inert, String(rendered.html)),
    ]);
    drawTextDiagrams(element, article);
    return h("div", { class: "metabrowser-kpress-host" }, [article]);
  }

  /**
   * A text's inert HTML in KPress's prose element, as `kpressHost` sets a description's and
   * Guided Review sets a note's (`DrawProse` in guided-review.js): rebuilt from the allowlist,
   * links absolute against the pull request.
   *
   * @param {MetabrowserInertHtmlRuntime} inert
   * @param {string} html
   */
  function inertProse(inert, html) {
    const prose = inert.kpressProse(
      inert.sanitizeHtml(html, shown?.pull?.htmlUrl ?? "https://github.com/"),
      document,
    );
    // Only this newly sanitized, lazily opened message is visited. Authored SVG and
    // state attributes have already been discarded; known state comes from our record.
    for (const anchor of prose.querySelectorAll("a[href]")) {
      decoratePullLink(/** @type {HTMLElement} */ (anchor), shown?.pull ?? null, mb);
    }
    return prose;
  }

  /**
   * The Mermaid diagrams each text with one draws, by its text element. A binding lasts as
   * long as its text's section: a section kept across polls and tabs keeps its drawings live,
   * one the conversation drops ends them (`paintConversation`), and so does the page's end.
   *
   * @type {Map<Element, {dispose(): void}>}
   */
  const textDiagrams = new Map();

  /**
   * Draw the Mermaid blocks of a text's Markdown, placed in *article*, as github.com draws
   * them in a description or comment. A text is untrusted, so each is an image, which runs
   * no script and loads nothing. A text with no block asks for nothing.
   *
   * On every page, a folder's served trusted among them, with no Content-Security-Policy.
   * Mermaid lays a diagram out in a document before it becomes an image, and there the
   * diagram's own CSS is live: its image shape, a `themeCSS` directive, and a state
   * diagram's `classDef` each load their URL. So each text's diagrams are laid out in the
   * Markdown plugin's diagram frame (`isolated: true`), whose own policy admits nothing but
   * its scripts, inline style, and `data:` images, under either profile
   * (markdown/diagram-frame.js has the measurement), as the text's other Markdown keeps
   * every other load away. A block whose image the frame refuses shows its error and
   * source.
   *
   * The Markdown plugin owns the host for KPress's diagrams (markdown/diagrams.js) and
   * exports it as `drawDiagrams`, which this plugin, declaring markdown in `requires`,
   * gets from `mb.plugins.load("markdown")` (docs/plugins.md, "Declared Dependencies"),
   * so it neither imports another plugin's files nor keeps a second copy of the adapter.
   * That plugin's static modules come with the first diagram, beside KPress's diagram
   * modules and Mermaid, which are far larger.
   *
   * @param {Element} element
   * @param {HTMLElement} article
   */
  function drawTextDiagrams(element, article) {
    disposeTextDiagrams(element);
    if (article.querySelector(TEXT_DIAGRAM) === null) {
      return;
    }
    let disposed = false;
    /** @type {{dispose(): void} | null} */
    let drawn = null;
    textDiagrams.set(element, {
      dispose() {
        disposed = true;
        drawn?.dispose();
        drawn = null;
      },
    });
    void mb.plugins
      .load("markdown")
      .then((markdown) => {
        if (!disposed && !listening.signal.aborted) {
          drawn = markdown.drawDiagrams(article, { isolated: true });
        }
      })
      .catch((error) => {
        // The text stays as it is, its block showing the diagram's source.
        console.warn("metabrowser github: a text's diagrams could not be drawn", error);
      });
  }

  /** @param {Element} element */
  function disposeTextDiagrams(element) {
    textDiagrams.get(element)?.dispose();
    textDiagrams.delete(element);
  }

  /**
   * Say under a text's plain text why its Markdown will not come, in one notice.
   *
   * @param {string} part
   * @param {string} text The text the server would not render.
   * @param {string} note
   */
  function refusedText(part, text, note) {
    refusedNotes.set(part, { text, note });
    const element = texts.get(part);
    const plain =
      element === undefined || textOf.get(element) !== text
        ? null
        : element.querySelector(":scope > .github-pull-plain");
    if (plain) {
      // One notice, saying the latest refusal's reason.
      element?.querySelector(":scope > .github-pull-text-refused")?.remove();
      plain.after(refusalNotice(note));
    }
  }

  /**
   * The line under a plain text that says why its Markdown will not come.
   *
   * @param {string} note
   */
  function refusalNotice(note) {
    const said = notice("warning", [note]);
    said.classList.add("github-pull-text-refused");
    said.setAttribute("role", "status");
    return said;
  }

  /**
   * @param {string} part
   * @param {Record<string, any>} rendered
   * @param {string} text The text it is the render of.
   */
  function renderMarkdown(part, rendered, text) {
    const element = texts.get(part);
    inserting.set(part, text);
    void Promise.all([inertReady, textStyles(rendered.assets)]).then(([inert]) => {
      // However this ends, a wait on the text hears of it: the render replaces the plain text
      // whose pending mark it was waiting on, and `showPending` sees no plain text after.
      try {
        if (inserting.get(part) === text) {
          inserting.delete(part);
        }
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
        if (plain && element !== undefined && inert !== null) {
          plain.replaceWith(kpressHost(inert, rendered, element));
          // The text is rendered now, so what said why it was plain goes with the plain text.
          element?.querySelector(":scope > .github-pull-text-refused")?.remove();
          if (refusedNotes.get(part)?.text === text) {
            refusedNotes.delete(part);
          }
        } else if (inert === null) {
          held?.failed.add(part);
        }
        // A text still plain shows its source now if no other render of it is on its way.
        showPendingPart(part);
        if (held?.mode === "hidden") {
          settleFirstPaint();
        }
      } finally {
        textsChanged();
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
    const at = mb.shortCommit(browse.at);
    const detail =
      browse.kind === "link"
        ? `Open ${what} at ${at}, the commit this page shows`
        : `Switch to ${at}, this pull request's head, and open ${what}`;
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
    if (wire === null || (checkoutPin && browse === null)) {
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
   * Whether the address is this page's and shows *tab*, by its id in `PULL_TABS`: the front
   * page, `/pull/<n>`, shows what `shownTabFor` resolves it to.
   *
   * @param {string} tab
   */
  function addressShows(tab) {
    const page = `/pull/${number}`;
    const here = window.location.pathname.replace(/\/$/, "");
    const route =
      here === page
        ? ""
        : (TABS.find((candidate) => candidate !== "" && onPageRoute(here, number, candidate)) ??
          null);
    return route !== null && shownTabFor(route, shown?.pull?.text ?? null) === tab;
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

  /**
   * A link to a native stack's own page, `/stack/<n>`, which the host opens in place.
   * @param {number} id
   */
  function stackPageLink(id) {
    const link = h("a", { href: `/stack/${id}` });
    link.addEventListener("click", (event) => {
      if (listening.signal.aborted || !isPlainClick(event)) {
        return;
      }
      event.preventDefault();
      void open({ number: id, tab: "", stack: true });
    });
    return link;
  }

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
   * @param {"layers"} name
   */
  const registryIcon = (name) =>
    new DOMParser().parseFromString(mb.icons[name] || "", "text/html").body.firstElementChild;
  const stackSvg = registryIcon("layers");

  /** One link per tab, kept across paints so a poll does not take focus from one. */
  const tabLinks = PULL_TABS.map(({ id, label }) => {
    // Conversation's route and Guided Review's are the front page's when it shows them, and
    // otherwise their own addresses (`routeForTab`); paintHeader keeps each link's route and
    // address current.
    /** @type {{number: number, tab: string}} */
    const route = { number, tab: id };
    const link = pageLink(route, "tab-btn", [label]);
    if (id === "guided") {
      link.classList.add("github-pull-guide-tab");
    } else {
      tabBar.append(link);
    }
    link.setAttribute("role", "tab");
    return { id, link, route };
  });
  /** The links' keys, from `attachTabKeys` once the page can end them. @type {MetabrowserPublicPluginShortcutHandle[]} */
  let tabKeys = [];
  /** The header's numbered links and actions, by what each does; see `numberHeaderControls`.
   * @type {Map<string, {handle: MetabrowserPublicPluginShortcutHandle, run: () => unknown}>} */
  const headerNumbers = new Map();

  /** Optional membership retains its labels-row disclosure while other header details repaint.
   * @param {PullModel} model
   */
  function paintStacks(model) {
    paintStackGuideLinks();
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
    // In more than one stack, each chip names its stack, as a Pulls row's place does.
    const named = memberships.length > 1;
    stackPullState = model.pull?.state ?? null;
    stackPullAuthor =
      model.pull === null ? null : { login: model.pull.author, avatar: model.pull.avatar };
    const nodes = memberships.map((stack) => {
      let menu = stackMenus.get(stack.number);
      if (menu) {
        menu.update(stack, model.pull?.title ?? "", named);
        return menu.element;
      }
      menu = createStackMenu(stack, number, {
        link: (target) => pageLink(memberRoute(target, stackTab(model.tab)), "", []),
        wholeStack: (id) => stackPageLink(id),
        icon: stackSvg === null ? null : document.importNode(stackSvg, true),
        currentTitle: model.pull?.title ?? "",
        named,
        titleNodes: mb.titleNodes,
        menus: mb.menus,
        state: (target) =>
          stackMemberState(stackIdentity?.source ?? null, target, number, stackPullState),
        author: () => stackPullAuthor,
        identity: stackMemberIdentity(mb),
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
    const slot = nodes.length === 0 ? [stackStrut] : nodes;
    if (
      slot.length !== stackColumn.children.length ||
      slot.some((node, at) => node !== stackColumn.children[at])
    ) {
      const focused = document.activeElement;
      const restore = focused instanceof HTMLElement && stackColumn.contains(focused);
      stackColumn.replaceChildren(...slot);
      if (restore && focused.isConnected) {
        focused.focus({ preventScroll: true });
      }
    }
  }

  /**
   * The menu most recently used chooses a stack when a PR has several memberships.
   */
  function currentStack() {
    if (
      !active ||
      listening.signal.aborted ||
      shown === null ||
      shown.pull === null ||
      document.visibilityState !== "visible" ||
      !addressShows(controller.snapshot().tab)
    ) {
      return null;
    }
    const memberships = stackMembership(stackIndex, stackIdentity, number);
    return memberships.find((stack) => stack.number === preferredStack) ?? memberships[0] ?? null;
  }

  /** The header's parts as last built, each with the inputs it was built from, as JSON.
   * @type {Map<string, {inputs: string, node: unknown}>} */
  const headerParts = new Map();

  /**
   * The header's part *name*: the node last built for it while *inputs*, everything it
   * shows, are unchanged, and else a new one. A tab switch or a poll then builds only what
   * changed, and the node under the reader's pointer or focus stays: replaced on each tab
   * switch, a branch chip's focused copy button lost its focus to the page, and the chip
   * under the pointer gave the shell's tooltip a new anchor (docs/design-system.md, "A
   * Repaint Keeps Its Images").
   *
   * @template T
   * @param {string} name
   * @param {unknown} inputs
   * @param {() => T} build
   * @returns {T}
   */
  function headerPart(name, inputs, build) {
    const key = JSON.stringify(inputs);
    const held = headerParts.get(name);
    if (held !== undefined && held.inputs === key) {
      return /** @type {T} */ (held.node);
    }
    const node = build();
    headerParts.set(name, { inputs: key, node });
    return node;
  }

  /**
   * A title (`titleHeading`): the state's icon, the title, and its number. A
   * conventional-commit prefix is regular and the rest bold (docs/design-system.md,
   * "Titles").
   *
   * @param {import("./pull-state.js").PullState} state
   * @param {string} title
   * @param {number} number
   */
  function pullTitle(state, title, number) {
    return titleHeading(pullStateIcon(state, { named: false }), mb.titleNodes(title), number);
  }

  // A sizer of every state's label, each a badge's box of no height, after the badge: the
  // slot is as wide as the widest, so a stale record that turns out merged does not widen
  // the badge under the reader (github/styles.css, `.github-pull-state-slot`).
  const badgeSizers = Object.values(PULL_STATES).map(({ label }) =>
    h(
      "span",
      {
        class: "file-header-badge github-pull-badge github-pull-badge-sizer",
        "aria-hidden": "true",
      },
      [label],
    ),
  );

  /** Keep stack disclosure and focus connected while ages and record details repaint.
   * @param {NonNullable<PullModel["pull"]>} pull
   */
  function paintStateRow(pull) {
    stateRow.hidden = false;
    placeChildren(stateSlot, [
      headerPart("badge", [pull.state, pull.stateLabel], () =>
        stateBadge(pull.state, pull.stateLabel),
      ),
      ...badgeSizers,
    ]);
    // A narrow row gives way in its sentence first: the action is cut short before the
    // author is (styles.css, "One line"). The branches have the line below to themselves.
    const actor = pull.actor;
    stateDetails.hidden = false;
    placeChildren(
      stateDetails,
      actorSentence(
        actor === null ? [] : [{ login: actor, avatar: pull.actorAvatar }],
        (one) =>
          headerPart("identity", [one.login, one.avatar], () =>
            authorLabel(mb, one.login, one.avatar, "", { loading: "eager" }),
          ),
        headerPart("action", [actor === null, pull.action], () =>
          actionText(pull.action, actor !== null),
        ),
      ),
    );
    placeChildren(branchesRow, [
      headerPart(
        "branches",
        [
          pull.headRef,
          pull.head,
          pull.headRepository,
          pull.headSha,
          pull.baseRef,
          pull.base,
          pull.baseRepository,
        ],
        () => {
          const sameRepository =
            pull.headRepository !== null && pull.headRepository === pull.baseRepository;
          const snapshot =
            !sameRepository && mb.sourceKind() === "git_revision" ? pull.headSha : "";
          const headRef = sameRepository
            ? `refs/remotes/origin/${pull.headRef}`
            : snapshot
              ? `refs/pull/${pull.number}/head`
              : undefined;
          const baseRef = `refs/remotes/origin/${pull.baseRef}`;
          return mb.mergeRefs(
            {
              name: pull.headRef,
              label: pull.head,
              repository: pull.headRepository,
              ref: headRef,
              snapshot: snapshot || undefined,
            },
            {
              name: pull.baseRef,
              label: pull.base,
              repository: pull.baseRepository,
              ref: baseRef,
            },
            { kind: "remote" },
          );
        },
      ),
    ]);
    return stateRow;
  }

  /**
   * Breathe the age while a refresh of what is shown runs or is due, or the conversation's
   * commits are read: the one sign of refreshing over content, with no spinner.
   *
   * @param {PullModel | null} model
   */
  function paintRefreshing(model) {
    // The note breathes only while it says the age, not a rate limit's hold in its place.
    const busy =
      model !== null &&
      model.pull !== null &&
      model.freshness !== null &&
      model.failureHold !== true &&
      (model.revalidating || (timelineBusy && model.tab === ""));
    meta.line.classList.toggle("mb-refreshing", busy);
    // Busy is said of the age being updated, never of the status line's buttons and links.
    if (busy) {
      meta.line.setAttribute("aria-busy", "true");
    } else {
      meta.line.removeAttribute("aria-busy");
    }
  }

  /**
   * Refresh what the page shows: on Changes, the comparison on screen with the record.
   * Settles when the refresh it asked for has been answered.
   *
   * @returns {Promise<void>}
   */
  async function refreshShown() {
    if (listening.signal.aborted || shown?.canRefresh !== true) {
      return;
    }
    const displayed = diffTab(shown.tab) ? diffFor : null;
    filesRefresh = displayed;
    await controller.requestRefresh(
      displayed === null ? undefined : { base: displayed.left, head: displayed.right },
    );
  }

  /**
   * Whether the cold page is held: null before the header's first paint, true from a first
   * paint with no record or core in hand until the header first paints one, false after.
   *
   * @type {boolean | null}
   */
  let coldHeld = null;

  /**
   * The cold header's title, decided at its first paint and kept: the Pulls tab's row for
   * this pull request where the list has one, so the cold title is the record's, its icon,
   * text, and number, and has the record's lines; null where the list has none, and the cold
   * title is "Pull request #7", held at the two lines a record's title takes at most.
   * Undefined before the first cold paint.
   *
   * @type {{state: import("./pull-state.js").PullState, title: string} | null | undefined}
   */
  let coldSeed;

  /**
   * Whether the cold header has been seen: the shell's quiet period, the hold's animation,
   * is over. Without the animation API, in a document no browser lays out, nothing has been
   * seen.
   */
  function coldHeaderShown() {
    return (
      typeof header.getAnimations === "function" &&
      !header
        .getAnimations()
        .some(
          (animation) =>
            typeof CSSAnimation === "function" &&
            animation instanceof CSSAnimation &&
            animation.animationName === "github-pull-cold-hold",
        )
    );
  }

  /**
   * A page mounted with no record in hand keeps its header and tab column out of sight for
   * the shell's quiet period (`.github-pull-cold`, `--loading-state-delay`), and shows them
   * at once with the first header that has a record or core. A read that lands within the
   * quiet period then never shows the cold header, whose labels row a pull request with no
   * labels drops as it lands; a slower one shows the cold header as it is, rows held, once
   * the quiet period is over. Opacity alone, so the rows keep their layout and the tab keys
   * stay live (docs/design-system.md, "Layout").
   *
   * A cold header that was seen with its title held at two lines, the Pulls tab having no row
   * to title it with, has the record's title keep those two lines for the page's life
   * (`.github-pull-title-held`), so the record lands moving nothing; a record that lands
   * unseen, or under its row's title, has its own lines.
   *
   * @param {PullModel} model
   */
  function holdColdPage(model) {
    const cold = model.pull === null;
    if (coldHeld === null) {
      coldHeld = cold;
      if (!cold) {
        return;
      }
    } else if (!coldHeld || cold) {
      return;
    } else {
      coldHeld = false;
      if (coldSeed === null && coldHeaderShown()) {
        header.classList.add("github-pull-title-held");
      }
    }
    for (const part of [header, tabColumn]) {
      part.classList.toggle("github-pull-cold", coldHeld);
    }
  }

  // The header's corner, which holds the View on GitHub button every page with a github.com
  // counterpart has (docs/design-system.md, "View on GitHub"): a view header's corner, right
  // after the title in the reading order, placed in the page's upper right
  // (github/styles.css). Each tab, and each changed file the Files tab is at, has its own
  // counterpart, so the button follows the page's address: the SDK asks once per address.
  const counterpartCorner = h("span", { class: "view-header-end", "data-counterpart": "" });
  /** Ask for the button of the address the page is at now. */
  function followCounterpart() {
    if (typeof mb.mountCounterpart === "function") {
      void mb.mountCounterpart(counterpartCorner, window.location.pathname);
    }
  }

  /** @param {PullModel} model */
  function paintHeader(model) {
    holdColdPage(model);
    /** @type {Element[]} */
    const children = [];
    const pull = model.pull;
    /** The situational controls this paint draws, by what each does, for their numbers.
     * @type {Map<string, {element: HTMLElement, run: () => unknown}>} */
    const numbered = new Map();
    // The page has no Refresh of its own (mb-ablv): the navigation's Refresh is the one
    // Refresh, and refreshes this page first (`refresh` on the page's handle, the page's
    // part of static/refresh-plan.js).
    // Its slot at the end of the row of ages held the stack chip a Refresh's width short of
    // the title's number (mb-dwha). What a sentence on the status row tells the reader to do
    // is on that row instead, after it (`remedy`, below), so a reader with the navigation
    // pane hidden still has it.
    if (pull !== null) {
      // The updated age is left out where it reads the same as the merged or closed age
      // beside it, or else the opened age; its exact time joins the tooltip of the age it
      // repeats. A merged pull request was usually last updated by its merge.
      const updated = age(pull.updated).textContent;
      const closedAt = pull.closed && pull.closedLabel ? pull.closed : null;
      const repeatsClosed = closedAt !== null && age(closedAt).textContent === updated;
      const repeatsOpened = !repeatsClosed && age(pull.created).textContent === updated;
      const also = { label: "updated", iso: pull.updated };
      const title = headerPart("title", [pull.state, pull.title, pull.number], () => {
        const { heading, titleText } = pullTitle(pull.state, pull.title, pull.number);
        // Two lines at most: a title cut short there carries the whole of it in its
        // tooltip. Cut short is a line or more hidden; a title of two lines that fit
        // overhangs its box by a pixel or two of descender (62 against 60 px, Chrome 152).
        heading.addEventListener("pointerenter", () => {
          if (titleText.scrollHeight - titleText.clientHeight > TITLE_OVERHANG_PX) {
            heading.dataset.tipText = `${pull.title} #${pull.number}`;
          } else {
            delete heading.dataset.tipText;
          }
        });
        return heading;
      });
      const root = mb.navigation.href({ path: "" });
      // The row's ages are told again below when it is kept; which of them it shows is
      // among its inputs.
      const opened = headerPart(
        "opened",
        [
          pull.created,
          pull.updated,
          closedAt,
          pull.closedLabel,
          repeatsOpened,
          repeatsClosed,
          model.browse,
          root,
        ],
        () => {
          const browse = model.browse === null ? null : browseControl(model.browse);
          // The ages give way first, cut short at their end, and the links after them stay
          // whole: cut at the row's end, the row lost Browse code before any age (B4 of
          // review B on #506).
          const row = agesLine(
            [
              "Opened ",
              age(pull.created, repeatsOpened ? also : null),
              ...(repeatsClosed || repeatsOpened ? [] : [" · updated ", age(pull.updated)]),
              ...(closedAt === null
                ? []
                : [` · ${pull.closedLabel} `, age(closedAt, repeatsClosed ? also : null)]),
            ],
            browse === null ? [] : [" · ", browse],
          );
          return { row, browse };
        },
      );
      retellAges(mb, opened.row);
      if (opened.browse !== null) {
        numbered.set("browse", {
          element: opened.browse,
          run:
            model.browse?.kind === "link"
              ? () => mb.navigation.open({ path: "" })
              : () => controller.browseCode(root),
        });
      }
      placeChildren(openedRow, [stateSlot, opened.row, stackColumn]);
      children.push(title, counterpartCorner, openedRow, paintStateRow(pull), branchesRow);
      // The labels follow the branches and take no row or gap if absent. They come
      // with its record or core, so the row is decided with the record's first paint; a
      // label's color and tooltip, which the repository's set may bring later, change no
      // chip's box.
      if (pull.labels.length > 0) {
        placeChildren(
          labelList,
          headerPart("labels", pull.labels, () => pull.labels.map(labelChip)),
        );
        children.push(labelsRow);
      }
    } else {
      if (coldSeed === undefined) {
        const listed = listedAnywhere(model.number);
        coldSeed = listed?.title ? { state: listed.state, title: listed.title } : null;
      }
      const seed = coldSeed;
      children.push(
        headerPart("loading title", [model.number, seed], () =>
          seed === null
            ? h("h1", { class: "page-heading github-pull-title" }, [
                `Pull request #${model.number}`,
              ])
            : pullTitle(seed.state, seed.title, model.number).heading,
        ),
        counterpartCorner,
      );
      // While the record is on its way the header keeps the rows it will have, empty, at
      // their heights, and its title the Pulls tab's row's or two lines held (`coldSeed`,
      // `holdColdPage`), so the record lands without moving the tab bar. The labels row is
      // among them while the labels are unknown, so a record with labels lands moving
      // nothing; one with none takes the row and its gap away in the paint that lands it,
      // the one paint that changes the header and the body together (mb-2u08).
      if (model.status !== "unavailable") {
        placeChildren(stateSlot, []);
        // No sentence yet, so the note, the page's word on the record, leads the row alone.
        placeChildren(stateDetails, []);
        stateDetails.hidden = true;
        placeChildren(branchesRow, []);
        placeChildren(openedRow, [
          stateSlot,
          headerPart("opened placeholder", null, () =>
            h("div", { class: "github-pull-quiet" }, ["\u00a0"]),
          ),
          stackColumn,
        ]);
        placeChildren(labelList, []);
        children.push(openedRow, stateRow, branchesRow, labelsRow);
      }
    }
    status.dataset.status = model.status;
    // A failure is the one text the row lets wrap: it carries its remedy.
    statusLine.failed(status, model.failure !== null && model.failureHold !== true);
    // The author's row ends in the note (mb-ne91): a record's one time, or a rate limit's hold
    // in its place, which begins and lifts by itself and asks nothing of the reader, so it
    // changes no row: on the status line it added one, moving the tab bar 27 px as it began
    // and lifted (A3 of review A on #506). Before a record is shown the note is the page's
    // word on it, which the status line then does not repeat, unless a failure goes with that
    // word, which then says it on the status line beside the failure (A10 of that review): on
    // the author's row it stood three empty rows above its failure. A header with no
    // author's row, a pull request that cannot be shown, says it on the status line, and so
    // does a page that offers Fetch, which follows that word there (`remedy`, below).
    const noteRow = children.includes(stateRow);
    const hold = model.failureHold === true ? model.failure : null;
    const offersFetch = pull === null && model.canRefresh;
    const noteText = !noteRow
      ? null
      : pull !== null
        ? (hold ?? model.freshness)
        : model.failure === null && !offersFetch
          ? model.message
          : null;
    const message = noteRow && pull === null && noteText !== null ? null : model.message;
    const failure = hold !== null && noteText === hold ? null : model.failure;
    // A hold is cut short with its text as a tooltip where it cannot be whole, rather than
    // leave the line as an age does, so the page always says why nothing refreshes (B3 of
    // review B on #506).
    const holdShown = hold !== null && noteText === hold;
    meta.line.classList.toggle("github-pull-freshness-held", holdShown);
    meta.lead.classList.toggle("github-pull-meta-lead-held", holdShown);
    // The dot joins the note to the author's sentence, so it is there only after one; the
    // note's slot is as wide as its widest age only while it says the age.
    showNote(meta, noteText, { sized: noteText === model.freshness, after: pull !== null });
    paintRefreshing(model);
    const failureHelp = model.failureHelp;
    // Offers end the status line, so a message or failure changing its width moves nothing
    // after it: the freshness text before them once moved an offer by 100 px.
    /** @type {Element[]} */
    const ending = [];
    // What the status row's sentence asks of the reader, first among its offers (mb-ablv):
    // Retry after a refresh that failed or was refused (`refreshFailed`), and Fetch, before a
    // record, after the word that the pull request has not been fetched. The Pulls tab's
    // Refresh does the same and refreshes the list too; this one is beside the sentence that
    // names its cause, so a reader with the navigation pane hidden, where the Pulls tab's keys
    // do nothing, still has it. A failed read or a failed switch to the head has nothing for
    // Retry to ask again.
    const asks =
      pull === null
        ? (failure !== null && model.failureHold !== true) || message !== null
        : model.refreshFailed;
    const remedyLabel = model.status === "absent" ? "Fetch" : "Retry";
    const remedy = headerPart("remedy", remedyLabel, () => {
      const button = statusLine.action(remedyLabel);
      // Held until a paint offers it, so a refresh already running as the page mounts shows
      // no waiting Retry that nothing had offered.
      button.hidden = true;
      button.addEventListener("click", refreshShown);
      return button;
    });
    // A Retry that shows waits while the refresh it asked for has not yet started: its
    // failure stays until one runs, and a press does nothing, as its click does
    // (`refreshShown`). Shown and muted, `aria-disabled`, it keeps its number, so the offer
    // after it keeps its own (B2 of review B on #506).
    const waiting = asks && !model.canRefresh && !remedy.hidden && model.revalidating;
    const remedyShown = asks && (model.canRefresh || waiting);
    if (remedy.hidden !== !remedyShown) {
      remedy.hidden = !remedyShown;
    }
    if (waiting) {
      remedy.setAttribute("aria-disabled", "true");
    } else {
      remedy.removeAttribute("aria-disabled");
    }
    if (remedyShown) {
      numbered.set("remedy", { element: remedy, run: refreshShown });
      ending.push(remedy);
    }
    const checkoutAtHead = model.checkoutAtHead;
    if (checkoutAtHead !== null) {
      const href = mb.navigation.href({ path: "" });
      const held = headerPart("checkout offer", [checkoutAtHead, href], () => {
        const link = h("a", { href }, ["Browse the checkout"]);
        return { offer: statusLine.offer([checkoutAtHead], link), link };
      });
      numbered.set("checkout", {
        element: held.link,
        run: () => mb.navigation.open({ path: "" }),
      });
      ending.push(held.offer);
    }
    const end = headerPart("status end", null, () => statusLine.end());
    const agesRow = children.includes(openedRow);
    placeChildren(end, ending);
    /** @type {Element[]} */
    const statusText = [
      ...(message === null
        ? []
        : [headerPart("message", message, () => statusLine.message(message))]),
      ...(failure === null
        ? []
        : [headerPart("failure", failure, () => statusLine.failure(failure))]),
      // What the event log holds of the failure: its cause, the address, and the timings
      // (mb-9zp5). Not for a rate limit's hold, which is not a failure.
      ...(failure === null || model.failureHold === true
        ? []
        : [headerPart("failure details", failure, () => detailsToggle("failure", failureQuery))]),
      ...(failureHelp === undefined
        ? []
        : [
            headerPart("failure help", failureHelp, () =>
              outside(mb, "https://cli.github.com/", "", [
                failureHelp === "install" ? "Install GitHub CLI" : "Update GitHub CLI",
              ]),
            ),
          ]),
    ];
    placeChildren(status, [...statusText, end]);
    // The line is there only while it has something to say, from what this paint put on it:
    // the note says the rest. With no row of ages it holds the page’s message, so it is
    // there.
    status.hidden = agesRow && statusText.length === 0 && ending.length === 0;
    children.push(status);
    if (pull !== null || model.status !== "unavailable") {
      children.push(sizeRow, summaryRow);
    }
    paintSummaryWait(model);
    if (detailsOpen !== null) {
      children.push(detailsPanel);
    }
    placeChildren(header, children);
    // A control that is gone, as a failure's when a refresh succeeds, closes its panel.
    if (detailsOpen !== null && !detailsOpen.button.isConnected) {
      closeDetails();
    }
    followCounterpart();
    if (model.pull === null && model.status === "unavailable") {
      tabColumn.remove();
    } else {
      for (const [at, { id, link, route }] of tabLinks.entries()) {
        if (id === "" || id === "guided") {
          route.tab = routeForTab(id, model.pull?.text ?? null);
          link.setAttribute("href", `/pull/${number}${route.tab ? `/${route.tab}` : ""}`);
        }
        if (id === "guided") {
          if (model.tab !== id && !GUIDED_FENCE.test(model.pull?.text ?? "")) {
            link.remove();
          } else if (link.parentNode === null) {
            tabBar.insertBefore(link, tabLinks[at + 1].link);
            tabKeys[at]?.retarget(link);
          }
        }
        link.classList.toggle("active", model.tab === id);
        link.setAttribute("aria-selected", String(model.tab === id));
      }
      showDocsTab(model);
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
    const said = [model.message, model.failure].filter(Boolean).join(" ");
    // Said again only when it changes: a live region announces each change of its text.
    if (live.textContent !== said) {
      live.textContent = said;
    }
    numberHeaderControls(mb.shortcuts, headerNumbers, numbered, listening.signal);
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
      retellAges(mb, shownRow);
      return shownRow;
    }
    const href = timelineCommitHref(source, number, event.oid);
    if (href === null) {
      return null;
    }
    // An event on the Conversation's timeline, said as a card head says a comment: the
    // subject where the author is, then when, in the head's type (docs/design-system.md,
    // "Conversation Timeline").
    return h("div", { class: "github-pull-commit github-pull-event" }, [
      h("span", { class: "github-pull-commit-subject" }, mb.titleNodes(event.subject || "Commit")),
      event.committed_at !== null && Number.isFinite(Date.parse(event.committed_at))
        ? h("span", {}, ["committed ", age(event.committed_at)])
        : null,
      mb.decorateExternalLink(
        outside(mb, href, "", [mb.shortCommit(event.oid)], "github-pull-commit-id git-commit-sha"),
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
        retellAges(mb, node);
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
        descriptionCard(pull, textBlock("body", pull.text, pull.truncated), [
          ...(GUIDED_FENCE.test(pull.text) ? [guideCard(pull.text)] : []),
          ...(STACK_GUIDE_FENCE.test(pull.text) ? [stackGuideCard()] : []),
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
          authorLabel(mb, item.author, item.avatar),
        ]);
        // Every event's heading reads alike: the author, a plain verb, and the age, and a
        // review's chip after them only for a state its verb does not say (mb-novh).
        head.append(
          item.review === null ? " commented " : " reviewed ",
          item.at === null ? "(pending)" : age(item.at),
        );
        if (item.review !== null && item.review.label !== null) {
          head.append(" ", stateBadge(item.review.state, item.review.label, "review"));
        }
        const built = h(
          "section",
          { class: `page-card github-pull-card github-pull-${item.kind} github-pull-event` },
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
    // A section the conversation no longer shows takes its texts' diagrams with it.
    const kept = new Set(order);
    for (const node of sections.values()) {
      if (!kept.has(node)) {
        for (const text of sectionTexts.get(node) ?? []) {
          disposeTextDiagrams(text);
        }
      }
    }
    sections = next;

    const before = discussion;
    const inserts = model.corePreview ? new Map() : (before?.inserts ?? new Map());
    const rows = new Set(inserts.values());
    for (const row of rows) {
      retellAges(mb, row);
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
    // Review comments are spaced as the Conversation's events are (mb-w7rt). Its heading's
    // tally sits beside the name after the separator, as every heading's does (the shell's
    // `.heading-tally`, docs/design-system.md, "Heading Tallies").
    const threads = h("section", { class: "github-pull-section github-pull-threads" }, [
      h("h2", { class: "section-heading" }, [
        "Review comments",
        h("span", { class: "heading-tally" }, [
          " ",
          h("span", { class: "heading-tally-dot", "aria-hidden": "true" }, ["·"]),
          " ",
          h("span", { class: "heading-tally-figure" }, [
            mb.formatInteger(model.reviewComments.length),
          ]),
        ]),
      ]),
    ]);
    for (const comment of model.reviewComments) {
      const head = h("div", { class: "github-pull-card-head" }, [
        fileLink(comment.path, comment.line, model.browse),
        comment.outdated ? " " : "",
        comment.outdated ? stateBadge("outdated", "outdated", "review") : null,
        " ",
        authorLabel(mb, comment.author, comment.avatar),
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
          // The fold's glyph is `.fold-expander`'s, drawn from `details[open]`.
          const disclosure = h("details", { class: "github-pull-hunk-earlier" }, [
            h("summary", { class: "fold-expander disclosure-toggle" }, [
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
      // "3 success · 1 failure": a count summary in its parts, painted by the shell's one
      // painter of them (`mb.countPartsNodes`): its numbers bold, and its dots muted and
      // hidden from a screen reader, which is told a comma in each one's place, as a paragraph
      // has no name to say the line in words (docs/design-system.md, "Count Summaries Bold
      // Their Numbers"). A no-break space holds each dot to the count before it, so a line
      // that wraps never starts with one.
      /** @type {MetabrowserCountPart[]} */
      const counted = Object.entries(summary.counts).flatMap(([tone, count], at) => [
        ...(at === 0 ? [] : ["\u00a0", CHECKS_SEPARATOR, " "]),
        { number: String(count) },
        ` ${tone}`,
      ]);
      checksSection.append(h("p", { class: "github-pull-quiet" }, mb.countPartsNodes(counted)));
      const rows = h("ul", { class: "github-pull-checks" });
      for (const item of summary.items) {
        rows.append(
          h("li", {}, [
            stateBadge(item.tone, item.label, "check"),
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
  /** The comparison Changes last showed on this page, mounted or not (`followedFrom`).
   * @type {ShownComparison | null}
   */
  let changesShown = null;
  /** The diff that the one shown replaced by itself, which its note names.
   * @type {ShownComparison | null}
   */
  let changesFrom = null;
  /** Whether the reader went back to the diff shown, which then stays (`filesAction`). */
  let changesChosen = false;
  /** Whether the keeper holds the place of a diff the one mounting replaces. */
  let keptThrough = false;

  function disposeDiff() {
    cancelCurrentFileBridge();
    unwatchCurrentFile?.();
    unwatchCurrentFile = null;
    diffHandle?.dispose?.();
    diffHandle = null;
    diffHost = null;
    diffFor = null;
    diffShows = "";
    reportCurrentFile(null);
  }

  const prefetch = createComparisonPrefetch({
    // The diff plugin spells the address, so the request `mountDiff` would make is this
    // one, byte for byte, and the browser's cache answers a Back from it.
    load: diffComparisonLoader(mb),
    warm() {
      void mb.ensureKindAssets("diff").catch(() => {});
      // The shared changed-files tree every diff draws its paths and summary with, so Changes
      // never waits for it after its comparison (docs/development.md, Asset Loading Tiers).
      void mb.loadChangedFilesTree().catch(() => {});
    },
    // What it read is the page's Diff summary too, on every tab (mb-pb35); a read on its way
    // holds the summary's placeholder, and one that failed leaves its row empty (mb-onr2). A
    // comparison the document keeps is handed over in the paint that shows its record, so the
    // summary is drawn in that paint once the diff's view is registered, as it is after any
    // first read (mb-neg9). Its first screen's Markdown is this page's own to ask for, once it
    // is idle.
    reading: (comparison) => summaryReading(comparison),
    loaded(comparison, payload) {
      if (mb.getRegisteredView("diff", "diff")) {
        showSummary(comparison, payload);
        askMarkdown(comparison, payload);
      } else {
        void mb.ensureKindAssets("diff").then(
          () => {
            showSummary(comparison, payload);
            askMarkdown(comparison, payload);
          },
          () => summaryUnavailable(comparison),
        );
      }
    },
    failed: (comparison) => summaryUnavailable(comparison),
    schedule: (callback) => mb.whenIdle(callback, { timeout: PREFETCH_IDLE_TIMEOUT_MS }),
    cancel: (cancel) => /** @type {() => void} */ (cancel)(),
    isVisible: () => document.visibilityState === "visible",
  });

  /**
   * A changed file at its address, `/pull/<n>/files/<path>`, the route a press on it in the
   * Pulls tab's tree takes, so the address names it and Back returns to where the reader was.
   * A path the route cannot spell, as one with a backslash, which Git allows in a name, has no
   * address: the diff goes to it in place instead.
   *
   * @param {string} path
   */
  function openChangedFile(path) {
    const opened = /** @type {{then?: unknown} | null | undefined} */ (
      open({ number, tab: "files", file: path, replace: false, jumped: false })
    );
    if (opened && typeof opened.then === "function") {
      void Promise.resolve(opened).then(undefined, () => goToFileInPlace(path));
    } else {
      goToFileInPlace(path);
    }
  }

  /**
   * Go to a changed file that has no address: the diff jumps to it in place, or, with no diff
   * mounted, as on Conversation and Checks, Changes opens at the page's own address and its
   * diff goes to the file once it mounts (`landFile`), so the press is not lost (A8 of review
   * A on #470).
   *
   * @param {string} path
   */
  function goToFileInPlace(path) {
    if (listening.signal.aborted || diffHandle !== null) {
      jumpTo(path);
      return;
    }
    wantedFile = path;
    void Promise.resolve(open({ number, tab: "files", replace: false, jumped: false })).catch(
      () => {},
    );
  }

  /**
   * The page's Diff summary: the comparison it is drawn for, or being drawn for, the claim of
   * its latest draw, and the mount in the row.
   */
  let summaryShown = {
    key: "",
    claim: 0,
    handle: /** @type {{dispose: () => void} | null} */ (null),
  };
  /**
   * The comparison whose last read drew no Diff summary, whose row is left empty until a
   * read of it starts again (mb-pb35, mb-onr2).
   */
  let summaryFailed = "";
  /** The size routes asked for and not yet answered. */
  const sizeAsked = new Set();
  /** The file count of the Diff summary drawn, by its comparison, for the size line. */
  let summaryFiles = { key: "", files: /** @type {number | null} */ (null) };
  /**
   * The cached changed-files list's brief line, drawn in the Diff summary's row while the
   * comparison is on its way or read (pull-summary-brief.js, mb-z8ea), and the line drawn,
   * by the list's generation and the tree's breakdown having loaded. An SDK without the
   * change line's painters has none.
   */
  const summaryBrief =
    typeof mb.changeLine === "function" &&
    typeof mb.changeLineNodes === "function" &&
    typeof mb.countPartsNodes === "function" &&
    typeof mb.formatInteger === "function"
      ? createSummaryBrief({
          async read(asked, signal) {
            const response = await fetch(`${PULL_FILES_SUMMARY_ROUTE}?numbers=${asked}`, {
              signal,
            });
            return { status: response.status, body: response.ok ? await response.json() : null };
          },
          // What the line is painted with, as the summary that replaces it is: the diff
          // plugin's styles and the changed-files tree, whose breakdown says its letters.
          async ready() {
            const [, tree] = await Promise.all([
              mb.ensureKindAssets("diff"),
              mb.loadChangedFilesTree(),
            ]);
            return tree.statusBreakdown;
          },
          changed: () => paintSummaryWait(shown),
        })
      : null;
  let briefShown = {
    key: "",
    node: /** @type {HTMLElement | null} */ (null),
    files: /** @type {number | null} */ (null),
  };
  // Asked as the page mounts: a page opened from a Pulls row has the row's line in the
  // document's memory, by the repository its envelope names; any other asks the route once.
  const readerSource = /** @type {{source?: unknown} | null | undefined} */ (
    ctx.reader?.initial?.body
  )?.source;
  summaryBrief?.want(number, typeof readerSource === "string" ? readerSource : null);

  /**
   * The brief line for what *model*'s Diff summary is drawn for, or null: on Changes the
   * mounted diff's comparison, else the record's, or the record's or core's head and base
   * branch before it has one (`briefMatches`). The node drawn is kept while its list is the
   * same, so a repaint moves nothing.
   *
   * @param {PullModel | null} model
   */
  function briefFor(model) {
    const compared =
      diffTab(model?.tab) && diffFor !== null ? diffFor : (model?.comparison ?? null);
    const summary =
      summaryBrief?.summary({
        head: compared?.right ?? model?.head ?? null,
        base: compared?.left ?? null,
        baseRef: model?.baseRef ?? null,
      }) ?? null;
    if (summary === null || summaryBrief === null) {
      return null;
    }
    const breakdown = summaryBrief.breakdown();
    const key = `${summary.generation}:${summary.head}:${breakdown === null ? 0 : 1}`;
    if (briefShown.key !== key || briefShown.node === null) {
      briefShown = { key, node: briefLine(mb, h, summary, breakdown), files: summary.files };
    }
    return briefShown.node;
  }
  /** The comparison whose first screen's Markdown this page asked for, and how to stop it. */
  let markdownAsked = { key: "", controller: /** @type {AbortController | null} */ (null) };

  /**
   * Ask, once the browser is idle, for the first screen's rendered Markdown of *comparison*,
   * whose answer is *raw*, so Changes finds it computed. It is asked apart from the
   * comparison, which the document keeps for later pages and whose request outlives this
   * one, under a controller of this page's: a page that goes, or a newer comparison, stops
   * the rest. A comparison with no rendered route asks for nothing.
   *
   * @param {{left: string, right: string, route?: string, rendered_route?: string}} comparison
   * @param {unknown} raw
   */
  function askMarkdown(comparison, raw) {
    const key = comparisonKey(comparison);
    if (
      listening.signal.aborted ||
      comparison.rendered_route === undefined ||
      markdownAsked.key === key
    ) {
      return;
    }
    markdownAsked.controller?.abort();
    const controller = new AbortController();
    markdownAsked = { key, controller };
    const cancel = mb.whenIdle(
      () => {
        const view =
          /** @type {{prefetchMarkdown?: (comparison: object, raw: unknown, signal: AbortSignal) => Promise<void>} | null} */ (
            mb.getRegisteredView("diff", "diff")
          );
        if (!controller.signal.aborted && typeof view?.prefetchMarkdown === "function") {
          const asked = {
            left: comparison.left,
            right: comparison.right,
            base_policy: "merge_base",
            ...(comparison.route === undefined ? {} : { route: comparison.route }),
            rendered_route: comparison.rendered_route,
          };
          void view.prefetchMarkdown(asked, raw, controller.signal).catch(() => {});
        }
      },
      { timeout: PREFETCH_IDLE_TIMEOUT_MS },
    );
    controller.signal.addEventListener("abort", () => cancel(), { once: true });
  }

  /**
   * A wait the event log hears of only when it is late (static/event-reports.js, `wait`).
   * The reporter is an on-demand bundle, which may arrive after the wait began, so it is
   * told when the wait began; a wait over before it arrives was not late.
   *
   * @param {string} name
   * @param {{onLate?: (ms: number) => void}} [options]
   */
  function reportedWait(name, options = {}) {
    const startedAt = performance.now();
    /** @type {MetabrowserEventWait | null} */
    let handle = null;
    let ended = false;
    loadEventReports().then(
      () => {
        if (!ended && !listening.signal.aborted) {
          handle =
            mb.eventReports?.wait(name, { ...options, startedAt, detail: { number } }) ?? null;
        }
      },
      () => {},
    );
    return {
      /** @param {MetabrowserEventOutcome} [outcome] */
      end(outcome = "ok") {
        if (!ended) {
          ended = true;
          handle?.end(outcome);
        }
      },
    };
  }

  /** The `event-reports` bundle, which the shell asks for after the first usable tree. */
  const loadEventReports = () =>
    typeof mb.ensureAsset === "function"
      ? Promise.resolve(mb.ensureAsset("event-reports"))
      : Promise.resolve();

  /** @type {{end: (outcome?: MetabrowserEventOutcome) => void} | null} */
  let summaryWait = null;
  /** @type {{end: (outcome?: MetabrowserEventOutcome) => void} | null} */
  let refreshWait = null;

  /**
   * The Diff summary's row holds its placeholder, or the line that says it is late: the
   * reader is waiting, and the event log hears of it if the wait runs late. It ends when
   * the row holds anything else: the summary (`ok`), nothing after a read that drew none
   * (`failed`), or the brief line or nothing because nothing is coming (`cancelled`).
   */
  function noteSummaryWait() {
    const held = summaryRow.firstChild;
    const waiting = held === summaryPending || held === summaryLate;
    if (waiting && summaryWait === null && !listening.signal.aborted) {
      summaryWait = reportedWait("githubPull:diffSummary", {
        onLate: (ms) => {
          summaryLateShown = true;
          summaryLateText.textContent = `The summary of changes has not arrived after ${Math.round(ms / 1000)} s.`;
          if (summaryLate.childNodes.length === 1) {
            summaryLate.append(
              " ",
              detailsToggle("summary details", () => ({ client: mb.eventReports?.page })),
            );
          }
          if (summaryRow.firstChild === summaryPending) {
            summaryRow.replaceChildren(summaryLate);
          }
        },
      });
    } else if (!waiting && summaryWait !== null) {
      summaryWait.end(
        summaryShown.handle !== null ? "ok" : summaryFailed !== "" ? "failed" : "cancelled",
      );
      summaryWait = null;
      summaryLateShown = false;
      if (detailsOpen !== null && !detailsOpen.button.isConnected) {
        closeDetails();
      }
    }
  }

  /**
   * A refresh of what is shown runs: the event log hears of it if it runs late, and how it
   * ended.
   *
   * @param {PullModel} model
   */
  function noteRefreshWait(model) {
    if (model.refreshing && refreshWait === null && !listening.signal.aborted) {
      refreshWait = reportedWait("githubPull:refresh");
    } else if (!model.refreshing && refreshWait !== null) {
      refreshWait.end(model.failure !== null && model.failureHold !== true ? "failed" : "ok");
      refreshWait = null;
    }
  }

  /** @param {number} ms */
  const utcSecond = (ms) => `${new Date(ms).toISOString().slice(0, 19)}Z`;

  /**
   * The records behind the failure shown: the failures in the window before the refresh
   * ended, to a minute after it, for the records written as it ended (its job's end, and the
   * probe that explains it), and this page's own.
   *
   * @returns {MetabrowserEventDetailsQuery}
   */
  function failureQuery() {
    const at = Date.parse(shown?.failureAt ?? "");
    const reports = mb.eventReports;
    const windowMs = (reports?.failureWindowS ?? 3600) * 1000;
    return {
      client: reports?.page,
      ...(Number.isFinite(at)
        ? { since: utcSecond(at - windowMs), until: utcSecond(at + 60_000) }
        : {}),
    };
  }

  /**
   * A text action that opens the Details panel on *query*'s records, and closes it.
   *
   * @param {string} name
   * @param {() => MetabrowserEventDetailsQuery} query
   */
  function detailsToggle(name, query) {
    const button = h(
      "button",
      {
        type: "button",
        class: "github-pull-text-action github-pull-details-toggle",
        "aria-expanded": "false",
        "aria-controls": detailsId,
        "data-details": name,
      },
      ["Details"],
    );
    button.addEventListener("click", () => {
      const opening = detailsOpen?.button !== button;
      closeDetails();
      if (opening) {
        openDetails(button, query);
      }
    });
    return button;
  }

  function closeDetails() {
    if (detailsOpen === null) {
      return;
    }
    detailsOpen.reading.abort();
    detailsOpen.button.setAttribute("aria-expanded", "false");
    detailsOpen = null;
    detailsPanel.remove();
  }

  /**
   * @param {HTMLElement} button
   * @param {() => MetabrowserEventDetailsQuery} query
   */
  function openDetails(button, query) {
    const reading = new AbortController();
    detailsOpen = { button, reading };
    button.setAttribute("aria-expanded", "true");
    detailsPanel.replaceChildren(
      h("p", { class: "event-log-details-note" }, ["Reading the event log…"]),
    );
    header.append(detailsPanel);
    loadEventReports()
      .then(() => {
        if (reading.signal.aborted) {
          return;
        }
        const reports = mb.eventReports;
        if (reports === undefined) {
          detailsPanel.replaceChildren(
            h("p", { class: "event-log-details-note" }, ["The event log is not available here."]),
          );
          return;
        }
        return reports.showDetails(detailsPanel, query(), { signal: reading.signal });
      })
      .catch(() => {
        if (!reading.signal.aborted) {
          detailsPanel.replaceChildren(
            h("p", { class: "event-log-details-note" }, ["The event log could not be read."]),
          );
        }
      });
  }

  /**
   * The Diff summary's row while no summary is drawn in it (mb-onr2). It waits on the read in
   * flight: on Changes the mounted diff's, which the summary is drawn from, and on every other
   * tab the record's comparison, which the prefetch reads; before the page has a comparison,
   * on one coming (`comparisonComing`). While it waits, the row holds the pending placeholder,
   * the same node from a core preview through its record to the read, so the wait has one
   * quiet period and one pulse; it is empty when nothing is coming or the read it waits on drew
   * no summary, so a placeholder never outlives its wait. A summary drawn stays while a newer
   * comparison is read, as content already shown does ("Refreshing Content"). The summary
   * replaces the placeholder in the row, which keeps its height.
   *
   * @param {PullModel | null} model
   */
  function paintSummaryWait(model) {
    if (summaryShown.handle !== null || listening.signal.aborted) {
      noteSummaryWait();
      return;
    }
    const awaited = model === null ? null : diffTab(model.tab) ? diffFor : model.comparison;
    const waits =
      awaited === null
        ? model?.comparisonComing === true
        : comparisonKey(awaited) !== summaryFailed;
    // The cached list's line for the head the page knows takes the placeholder's place, and
    // stays when the wait ends with no summary; another head's is never shown.
    const brief = briefFor(model);
    const holds = brief ?? (waits ? (summaryLateShown ? summaryLate : summaryPending) : null);
    if (holds !== null) {
      if (summaryRow.firstChild !== holds || summaryRow.childNodes.length !== 1) {
        summaryRow.replaceChildren(holds);
      }
    } else {
      summaryPending.remove();
      summaryLate.remove();
      briefShown.node?.remove();
    }
    paintSize(model);
    noteSummaryWait();
  }

  /**
   * The size line for *model*: the commits, the file count of the Diff summary drawn or of
   * the cached list's brief line, and, once `size_route` answers, what the comparison pushes
   * and its patch's size. While the summary's row waits with no count, this row holds the
   * placeholder too; with nothing coming it is empty. A size is drawn only for the comparison
   * whose files the line counts.
   *
   * @param {PullModel | null} model
   */
  function paintSize(model) {
    if (listening.signal.aborted) {
      return;
    }
    const comparison = model?.comparison ?? null;
    const key = comparison === null ? "" : comparisonKey(comparison);
    const drawn = summaryShown.handle !== null;
    const files = drawn
      ? summaryFiles.key === summaryShown.key
        ? summaryFiles.files
        : null
      : summaryRow.firstChild === briefShown.node && briefShown.node !== null
        ? briefShown.files
        : null;
    if (files === null) {
      delete sizeRow.dataset.sizeKey;
      const waits = summaryRow.firstChild === summaryPending;
      if (waits ? sizeRow.firstChild !== sizePending : sizeRow.firstChild !== null) {
        sizeRow.replaceChildren(...(waits ? [sizePending] : []));
      }
      return;
    }
    const route = comparison?.size_route;
    const size =
      route === undefined || (drawn && summaryShown.key !== key) ? null : pullSize(route, model);
    const commits = model?.pull?.commits ?? null;
    paintSizeLine(mb, sizeRow, {
      ...(commits === null ? {} : { commits }),
      files,
      pushedBytes: size?.pushed_bytes ?? null,
      diffBytes: size?.diff_bytes ?? null,
    });
  }

  /**
   * The size *route* answered, kept for the document, or null while it is on its way or
   * failed; a request is sent once, and an answer repaints the size line for the page shown.
   *
   * @param {string} route
   * @param {PullModel | null} model
   * @returns {{pushed_bytes: number | null, diff_bytes: number | null} | null}
   */
  function pullSize(route, model) {
    const kept = KEPT_PULL_SIZES.get(route);
    if (kept !== undefined) {
      return kept;
    }
    if (!sizeAsked.has(route)) {
      sizeAsked.add(route);
      void (async () => {
        try {
          const response = await fetch(route, { signal: listening.signal });
          const body = await response.json().catch(() => null);
          const size = response.ok ? body?.size : null;
          if (size?.state === "measured") {
            keepPullSize(route, { pushed_bytes: size.pushed_bytes, diff_bytes: size.diff_bytes });
            paintSize(shown ?? model);
          }
        } catch {
          // The line says its counts without a size; the next page asks again.
        } finally {
          sizeAsked.delete(route);
        }
      })();
    }
    return null;
  }

  /**
   * *comparison* was read, or could not be, and drew no Diff summary: its row is empty, the
   * placeholder gone with its wait (mb-onr2). A summary of an earlier comparison is not left
   * in the row either, where it would read as this one's (A1 of review A on #470), when
   * *comparison* is the one the page shows; the next read of it draws it. A draw of this
   * comparison already under way answers for itself, and a failure of another comparison, as
   * an older one Changes shows while it is repaired, empties nothing.
   *
   * @param {{left: string, right: string, route?: string}} comparison
   */
  function summaryUnavailable(comparison) {
    if (listening.signal.aborted) {
      return;
    }
    const key = comparisonKey(comparison);
    summaryFailed = key;
    const current = shown?.comparison ?? null;
    if (current !== null && comparisonKey(current) === key && summaryShown.key !== key) {
      clearSummary();
    }
    paintSummaryWait(shown);
  }

  /**
   * A read of *comparison* starts: the prefetch's, or a Changes diff's, a Retry's included.
   * One whose last read drew no summary is waited for again.
   *
   * @param {{left: string, right: string, route?: string}} comparison
   */
  function summaryReading(comparison) {
    if (listening.signal.aborted) {
      return;
    }
    if (summaryFailed === comparisonKey(comparison)) {
      summaryFailed = "";
    }
    paintSummaryWait(shown);
  }

  /** Empty the summary's row, which keeps its held height, so nothing moves. */
  function clearSummary() {
    summaryShown.handle?.dispose();
    summaryShown = { key: "", claim: summaryShown.claim + 1, handle: null };
    summaryRow.replaceChildren();
    paintSize(shown);
    noteSummaryWait();
  }

  /**
   * Draw the page's Diff summary for *comparison* from what was read of it, once per
   * comparison, whichever read comes first: the prefetch, on any tab but Changes, or the
   * Changes diff's own. It is drawn out of sight and put in the header's held row in one
   * step, so it moves nothing; a newer comparison's replaces it the same way. One that draws
   * nothing, or fails, empties the row rather than leave an earlier comparison's there.
   *
   * @param {{left: string, right: string, route?: string}} comparison
   * @param {unknown} raw
   */
  function showSummary(comparison, raw) {
    const key = comparisonKey(comparison);
    if (listening.signal.aborted || summaryShown.key === key) {
      return;
    }
    if (raw === undefined || raw === null) {
      summaryUnavailable(comparison);
      return;
    }
    const view =
      /** @type {{summary?: (slot: HTMLElement, ctx: {raw: unknown, openFile: (path: string) => void}) => Promise<{dispose: () => void} | null>} | null} */ (
        mb.getRegisteredView("diff", "diff")
      );
    if (typeof view?.summary !== "function") {
      summaryUnavailable(comparison);
      return;
    }
    const claim = summaryShown.claim + 1;
    summaryShown = { ...summaryShown, key, claim };
    const stage = h("div", {});
    void view.summary(stage, { raw, openFile: openChangedFile }).then(
      (handle) => {
        if (listening.signal.aborted || summaryShown.claim !== claim) {
          handle?.dispose();
          return;
        }
        if (handle === null) {
          clearSummary();
          summaryUnavailable(comparison);
          return;
        }
        summaryShown.handle?.dispose();
        summaryShown = { key, claim, handle };
        summaryFiles = { key, files: manifestFiles(raw) };
        // In place of the placeholder or an older summary, in one step.
        summaryRow.replaceChildren(...stage.childNodes);
        paintSize(shown);
        noteSummaryWait();
      },
      () => {
        if (!listening.signal.aborted && summaryShown.claim === claim) {
          clearSummary();
          summaryUnavailable(comparison);
        }
      },
    );
  }

  /**
   * The comparison is read on every tab but Changes, which reads it itself: the page's Diff
   * summary is drawn from it (mb-pb35). A page opened out of sight asks once it is shown.
   *
   * @param {PullModel} model
   */
  function wantComparison(model) {
    if (model.pull !== null && model.tab !== "files" && model.comparison !== null) {
      // Docs reads its narrowed diff itself, and the summary is the whole comparison's.
      prefetch.want(model.comparison);
    }
  }

  /**
   * Docs is offered only where the comparison changes a document: shown until its File
   * type counts say none changed, so the usual pull request's tab bar never moves, and
   * kept while the reader is on it, whose empty state says so.
   *
   * @param {PullModel} model
   */
  function showDocsTab(model) {
    const docs = tabLinks.find(({ id }) => id === "docs")?.link;
    if (docs) {
      docs.hidden = docsChanged === false && model.tab !== "docs";
    }
  }

  /**
   * Ask once per comparison whether it changes a document (`changesDocuments`), through the
   * diff view's `typeCounts`, at the comparison's own address with `view=types`.
   *
   * @param {PullModel} model
   */
  function askDocs(model) {
    const comparison = model.pull === null ? null : model.comparison;
    if (comparison === null) {
      return;
    }
    const key = JSON.stringify([comparison.left, comparison.right, comparison.route ?? ""]);
    if (key === docsFor) {
      return;
    }
    docsAsking?.abort();
    const asking = new AbortController();
    docsAsking = asking;
    docsFor = key;
    docsChanged = null;
    listening.signal.addEventListener("abort", () => asking.abort(), { once: true });
    void mb
      .ensureKindAssets("diff")
      .then(() => {
        const view = /** @type {MetabrowserPublicViewSpec | null} */ (
          mb.getRegisteredView("diff", "diff")
        );
        if (asking.signal.aborted || typeof view?.typeCounts !== "function") {
          return null;
        }
        return view.typeCounts(
          {
            left: comparison.left,
            right: comparison.right,
            base_policy: "merge_base",
            ...(comparison.route === undefined ? {} : { route: comparison.route }),
          },
          asking.signal,
        );
      })
      .then(
        (counts) => {
          if (asking.signal.aborted || docsFor !== key) {
            return;
          }
          docsChanged = changesDocuments(counts);
          if (shown !== null) {
            showDocsTab(shown);
          }
        },
        // A count that did not come leaves Docs shown, as before it was asked.
        () => {},
      );
  }

  /** What this history entry remembers of its diff, for a page first mounting one on it. */
  function entryMemory() {
    // The entry's memory is kept with its place: by a page in the pane that scrolls.
    return changesShown === null && pane !== null
      ? rememberedChanges(window.history.state?.[CHANGES_KEY])
      : null;
  }

  /**
   * Hold the reader's place through a diff's replacement, in its file where the next diff
   * has it. Held and written before the body is emptied: the pane then clamps to its top,
   * which arrives as a scroll, and with nothing held that top would be written as the
   * reader's place for as long as the next comparison takes to read, where the reload a
   * followed pin makes would land on it (A3 of review A on #745). While no diff is mounted,
   * as while the one being replaced is still read, the body has nothing to measure, and the
   * place is the one already kept (`holdThrough`).
   */
  function keepPlaceThrough() {
    if (place !== null) {
      place.keeper.holdThrough(diffHandle !== null);
      keptThrough = true;
    }
  }

  /**
   * Mount the record's comparison in Changes or Docs. One that replaces another diff, the
   * one shown or the one this history entry showed when the page was last loaded, is noted
   * (`followedNote`). *keep* holds the reader's place through the replacement.
   *
   * @param {NonNullable<PullModel["comparison"]>} comparison
   * @param {boolean} keep
   */
  function showChanges(comparison, keep) {
    const memory = entryMemory();
    changesFrom = followedFrom(
      changesShown ?? memory?.shown ?? null,
      changesFrom ?? memory?.from ?? null,
      comparison,
    );
    changesChosen = false;
    if (keep) {
      keepPlaceThrough();
    }
    diffMounted = mountDiff(comparison);
  }

  /** The way back a followed diff's note offers: the diff it replaced, which then stays. */
  function showEarlier() {
    const earlier = changesFrom;
    if (earlier === null || listening.signal.aborted) {
      return;
    }
    changesFrom = null;
    changesChosen = true;
    // An explicit choice of the earlier diff ends an older repair's hold on Changes.
    filesRefresh = null;
    keepPlaceThrough();
    diffMounted = mountDiff(earlier);
  }

  /**
   * On a page loaded again on its entry: the earlier diff the reader had gone back to,
   * mounted in place of the record's, so the choice outlives the reload each later push
   * makes on a repository URL (`chosenEarlier`). The landing holds the place.
   *
   * @param {NonNullable<PullModel["comparison"]>} comparison
   */
  function restoreChosen(comparison) {
    const earlier = chosenEarlier(entryMemory(), comparison);
    if (earlier !== null) {
      changesFrom = null;
      changesChosen = true;
      diffMounted = mountDiff(earlier);
    }
  }

  /** Whether the address is this page's entry on a tab that shows the diff (`diffTab`). */
  function onDiffRoute() {
    return TABS.some((tab) => diffTab(tab) && onPageRoute(window.location.pathname, number, tab));
  }

  /**
   * What this entry's diff shows, for a page loaded again on it (`rememberedChanges`).
   * Changes and Docs draw one comparison and both follow a moved head, so an entry on
   * either remembers it, the diff its note names, and the reader's choice (mb-mzcj).
   */
  function rememberChanges() {
    // History can move on before this page is told, as for a place (`keepPlace`).
    if (pane === null || !onDiffRoute()) {
      return;
    }
    const memory = { shown: changesShown, from: changesFrom, chosen: changesChosen };
    // An entry that already holds it is not written again: the host lands the page more
    // often than the memory changes, and Safari limits how often `replaceState` may run.
    if (JSON.stringify(window.history.state?.[CHANGES_KEY]) !== JSON.stringify(memory)) {
      window.history.replaceState({ ...window.history.state, [CHANGES_KEY]: memory }, "");
    }
  }

  /**
   * The host landed this page on an address of its own without mounting a diff, where the
   * memory is otherwise written. A key's walk of the Pulls tab's changed files replaces the
   * entry once it stops, and a click on a file or a tab pushes one, each with no state, so
   * the reload a followed pin makes there would lose the note and the reader's choice
   * (mb-eg5f). The diff mounted is what the entry remembers; with none mounted yet, the
   * mount writes it.
   */
  function rememberLanded() {
    if (diffFor !== null) {
      rememberChanges();
    }
  }

  /** @param {ShownComparison & {branch?: {ref: string | null} | null}} comparison */
  async function mountDiff(comparison, tab = shown?.tab ?? "files") {
    if (listening.signal.aborted) {
      return;
    }
    disposeDiff();
    // The diff's host, with progress kept below it so it cannot move the diff's first row
    // (`holdDiff`, which a stack's page holds its diff with too).
    const held = holdDiff(body);
    const { host, loading } = held;
    diffHost = host;
    diffFor = comparison;
    changesShown = shownComparison(comparison);
    rememberChanges();
    // Docs is the comparison's documents alone, drawn whole: the whole comparison, which
    // the page's Diff summary describes, is read apart from it, as on Conversation.
    const docs = tab === "docs";
    diffShows = docs ? "docs" : "files";
    if (docs) {
      prefetch.want(comparison);
    } else {
      // The page's Diff summary waits on this diff's read now, a Retry's too (mb-onr2).
      summaryReading(comparison);
    }
    const owns = () => !listening.signal.aborted && diffHost === host;
    // Whether the diff read its document, which the page's Diff summary is drawn from: a
    // diff that could not leaves the summary's row empty rather than pending (mb-onr2).
    let documented = false;
    // Whether Docs found no document, which then points the reader to Changes.
    let emptied = false;
    try {
      const raw = docs ? Promise.resolve(undefined) : prefetch.take(comparison);
      await mb.ensureKindAssets("diff");
      if (!owns()) {
        return;
      }
      const view = mb.getRegisteredView("diff", "diff");
      if (!view) {
        host.textContent = "Changes could not be shown. Reload the page to try again.";
        if (!docs) {
          summaryUnavailable(comparison);
        }
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
        held.hold();
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
                ...(comparison.image_route === undefined
                  ? {}
                  : { image_route: comparison.image_route }),
                ...(comparison.rendered_route === undefined
                  ? {}
                  : { rendered_route: comparison.rendered_route }),
                // A pull request's comparison: what its View on branch opens, if anything.
                branch: comparison.branch ?? null,
              },
              ...(prefetched === undefined ? {} : { raw: prefetched }),
              // The page draws the Diff summary at its top; the diff draws none (mb-pb35).
              summary: false,
              ...(docs
                ? {
                    // Docs: the documents alone, with no File type choice, drawn as Docs
                    // draws a document (`DOCS_DRAWING`).
                    group: DOCS_GROUP,
                    ...DOCS_DRAWING,
                    emptyText: "No documents changed in this pull request.",
                    onDocument: (/** @type {unknown} */ document_) => {
                      documented = true;
                      emptied = noFiles(document_);
                    },
                  }
                : {
                    // Changes: every file, drawn as Changes draws a file (`CHANGES_DRAWING`).
                    ...CHANGES_DRAWING,
                    // The File type choice is the page's: kept while the reader is on
                    // another tab, and gone with the page, as the diff's place is.
                    types: diffTypes,
                    onTypes: (/** @type {Array<string> | null} */ types) => {
                      diffTypes = types;
                    },
                    onDocument: (/** @type {unknown} */ document_) => {
                      documented = true;
                      showSummary(comparison, document_);
                    },
                  }),
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
      if (!documented && !docs) {
        summaryUnavailable(comparison);
      }
      if (emptied) {
        host
          .querySelector(".diff-type-empty")
          ?.append(" ", pageLink({ number, tab: "files" }, "", ["Show every change"]));
      }
      diffHandle = handle;
      watchCurrentFileAfterPaint(host, handle);
      // Landed before the wait, so the first screen the Markdown layer reports is the one the
      // reader lands on: a file the address names, not the top of the diff.
      if (landFile() === null) {
        // A held place, a landing's or one kept through a replaced diff, can find its file
        // now that the diff says where each one is.
        place?.keeper.contentChanged();
      } else if (keptThrough) {
        // The file the reader asked for is where they are now: a place kept through the
        // replaced diff gives way to it, as it did when it was held only from here.
        place?.keeper.readerMoved();
      }
      keptThrough = false;
      const since = Date.now();
      const outcome = holds ? await held.firstScreen(handle) : null;
      if (outcome !== null) {
        mb.perf.measure("githubPull:changesHold", () => {}, {
          number,
          heldMs: Date.now() - since,
          // A page that went during the wait settles its diff's first screen by disposing it.
          outcome: owns() ? outcome : "cancelled",
        });
      }
      if (!owns()) {
        // A page that went while its diff was held keeps it out of sight, as its conversation
        // does: the page replacing it shows it as it was until that one is ready.
        loading.remove();
        return;
      }
      held.release();
      // Failed diff loads resolve to a disposable notice without the public file API.
      // Do not report that surface, or a replaced mount, as useful Files readiness.
      if (owns() && typeof handle?.currentFile === "function") {
        mb.perf.measure("githubPull:filesReady", () => {}, { number });
      }
    } catch {
      if (!owns()) {
        return;
      }
      if (!documented && !docs) {
        summaryUnavailable(comparison);
      }
      held.release();
      const retry = h("button", { type: "button", class: "btn" }, ["Retry"]);
      retry.addEventListener("click", () => {
        if (owns()) {
          diffMounted = mountDiff(comparison, tab);
        }
      });
      host.replaceChildren(
        notice("error", [docs ? "Docs could not load. " : "Changes could not load. ", retry]),
      );
    } finally {
      loading.remove();
    }
  }

  /** The changed file an address or the Pulls tab asked to see, until the diff can show it. */
  /** @type {string | null} */
  let wantedFile = null;

  /**
   * Go to a file of the mounted diff. docs/project/architecture/arch-diff-pipeline.md,
   * "Hydration", says what it promises.
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
        // Returning from Conversation still has to render Files while repair runs, and
        // moving between Changes and Docs draws the other tab's diff of the same repair.
        if (diffFor === null || diffShows !== model.tab) {
          diffMounted = mountDiff(displayed, model.tab);
        }
        return;
      }
      filesRefresh = null;
      // A refresh that found another head is followed below, not repaired first.
      const follows = filesAction(displayed, model.comparison, changesChosen) === "follow";
      if (
        !follows &&
        (diffFor === null ||
          (model.failure === null && model.message === null && diffFor === displayed))
      ) {
        // Only an existing Files mount can supply the place this remount preserves.
        // A history arrival already owns its saved place; Conversation must not overwrite it.
        if (diffFor !== null) {
          place?.keeper.flush();
        }
        diffMounted = mountDiff(displayed).then(() => {
          if (!listening.signal.aborted && diffTab(shown?.tab) && diffFor === displayed) {
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
    if (diffFor === null && comparison !== null) {
      restoreChosen(comparison);
    }
    const action = filesAction(diffFor, comparison, changesChosen);
    if (comparison === null || action === "unavailable") {
      disposeDiff();
      // The header was painted while the diff was mounted: its summary waited on that read.
      paintSummaryWait(model);
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
          [retry ? "Retry" : "Fetch"],
        );
        ask.addEventListener("click", () => void controller.requestComparison());
        message.append(ask);
      }
      body.replaceChildren(message);
      return;
    }
    if (action === "mount" || action === "follow") {
      showChanges(comparison, action === "follow");
    } else if (diffFor !== null && diffShows !== model.tab) {
      // Changes and Docs are two drawings of one comparison: moving between them draws it
      // again, the record's as it is now, or an earlier one the reader chose (mb-825n).
      diffMounted = mountDiff(action === "offer" ? diffFor : comparison, model.tab);
    }
    if (action === "offer") {
      const offer = h("button", { type: "button", class: "btn github-pull-newer" }, [
        "Show the newer changes",
      ]);
      offer.addEventListener("click", () => {
        // A reader's explicit newer selection ends the older repair's UI ownership.
        filesRefresh = null;
        // What `whenFilesReady` waits for is the diff last asked for, this one included.
        showChanges(comparison, true);
        paintFollowed();
      });
      body.querySelector(".github-pull-newer-offer")?.remove();
      // The heads are on the record and the diff's own header, never in the sentence.
      const said = notice(null, [
        diffFor?.right === comparison.right
          ? "The comparison has changed. "
          : "This pull request has newer commits. ",
        offer,
      ]);
      said.classList.add("github-pull-newer-offer");
      body.prepend(said);
    }
    paintFollowed();
    // The repository's list says the head moved before the record was read again: the diff
    // shown stays until the refresh brings the newer one, which Changes then follows.
    body.querySelector(".github-pull-new-commits")?.remove();
    if (model.newCommits !== null && action !== "offer") {
      const said = notice(null, [model.newCommits]);
      said.classList.add("github-pull-new-commits");
      body.prepend(said);
    }
  }

  function disposeGuided() {
    guided?.view?.dispose();
    guided = null;
  }

  /**
   * The description's card: who opened the pull request and when, then its text.
   * Conversation and Guided Review draw it alike.
   *
   * @param {NonNullable<PullModel["pull"]>} pull
   * @param {HTMLElement} text The description's text block.
   * @param {HTMLElement[]} after
   */
  function descriptionCard(pull, text, after) {
    return h("section", { class: "page-card github-pull-card github-pull-event" }, [
      h("div", { class: "github-pull-card-head" }, [
        authorLabel(mb, pull.author, pull.avatar),
        " opened ",
        age(pull.created),
      ]),
      text,
      ...after,
    ]);
  }

  /**
   * Where Conversation's description had its guided-review block: the server renders the
   * description without it (`render_part`), and this says where the guide is read: the
   * front page, which shows it (`routeForTab`).
   *
   * @param {string} description
   */
  function guideCard(description) {
    return notice(null, [
      "This description has a guided review. ",
      pageLink({ number, tab: routeForTab("guided", description) }, "", ["Open Guided Review"]),
    ]);
  }

  /** Where Conversation's card about a stack's guide links the stacks that read it, and
   * the stacks it links, as JSON: filled when the card is drawn and again as the stacks
   * this pull request is a member of become known (`paintStacks`).
   * @type {{slot: HTMLElement, key: string} | null} */
  let stackGuideLinks = null;

  /**
   * Where Conversation's description had its stack-review block: the server renders the
   * description without it (`render_part`), and this says a stack guide is read on a
   * stack's page. It names a stack guide, not the stack's: a stack shows the block of its
   * top-most member that has one, which may be a member above this one.
   */
  function stackGuideCard() {
    const slot = h("span", { class: "github-pull-stack-guide-links" }, ["."]);
    stackGuideLinks = { slot, key: "" };
    paintStackGuideLinks();
    return notice(null, ["This description has a stack guide, read on its stack's page", slot]);
  }

  /** Link each stack this pull request is a member of from the stack guide's card, once
   * the stacks are known; with none, the card links nothing. */
  function paintStackGuideLinks() {
    const shownLinks = stackGuideLinks;
    if (shownLinks === null) {
      return;
    }
    const stacks = stackMembership(stackIndex, stackIdentity, number).map((stack) => stack.number);
    const key = JSON.stringify(stacks);
    if (key === shownLinks.key) {
      return;
    }
    shownLinks.key = key;
    shownLinks.slot.replaceChildren(
      ".",
      ...stacks.flatMap((id, at) => {
        const link = stackPageLink(id);
        link.append(`Open ${stackLabel(id)}`);
        return [at === 0 ? " " : " · ", link];
      }),
    );
  }

  /**
   * The guide's introduction: the description's card, as Conversation draws it, without
   * its guided-review block. It is drawn again only when its text or its render changes.
   *
   * @param {PullModel} model
   * @param {GuidedMount} mount
   */
  function paintGuideIntroduction(model, mount) {
    const pull = /** @type {NonNullable<PullModel["pull"]>} */ (model.pull);
    const key = JSON.stringify([
      pull.text,
      pull.truncated,
      pull.state,
      pull.author,
      pull.avatar,
      pull.created,
      model.textRevision,
    ]);
    const shown = mount.introduction;
    if (shown.key !== key || shown.block === null) {
      shown.key = key;
      shown.block = textBlock("body", pull.text, pull.truncated);
      shown.block.classList.add("github-pull-guide-introduction");
      shown.node.replaceChildren(descriptionCard(pull, shown.block, []));
    }
    // Each paint of the tab clears the page's texts: the description's is registered again
    // so its Markdown lands here.
    askForTexts([shown.block]);
    // A description drawn again, rendered from what the page kept, waits for nothing now.
    textsChanged();
  }

  /**
   * The record revision whose guide was read ahead, and whether the head had moved past it,
   * so it is read once for each (`readGuideAhead`).
   *
   * @type {string | null}
   */
  let guideAhead = null;
  /** @type {(() => void) | null} */
  let cancelGuideAhead = null;

  /**
   * Read the guide ahead of the reader: once a full record whose description carries a guide
   * is shown on another tab, its module and its first step, when the page is idle, so Guided
   * Review draws whole the moment it is opened (guide-reads.js has the cost). Guided Review's
   * own tab reads its first step as it starts to import the module (`paintGuided`).
   *
   * @param {PullModel} model
   */
  function readGuideAhead(model) {
    const revision = model.recordRevision;
    const moved = model.newCommits !== null;
    const ahead = JSON.stringify([revision, moved]);
    if (
      revision === null ||
      model.corePreview ||
      guideAhead === ahead ||
      model.tab === "guided" ||
      !GUIDED_FENCE.test(model.pull?.text ?? "")
    ) {
      return;
    }
    guideAhead = ahead;
    cancelGuideAhead?.();
    cancelGuideAhead = mb.whenIdle(
      () => {
        cancelGuideAhead = null;
        if (listening.signal.aborted) {
          return;
        }
        guideReads.prefetch(guideAsks({ kind: "pull", number }), 1, revision, moved);
        void import("./guided-review.js").catch(() => {});
      },
      { timeout: PREFETCH_IDLE_TIMEOUT_MS },
    );
  }

  /**
   * Resolve once *node*'s texts show as they will stay: none of them waits, out of sight,
   * for its Markdown (`showPending`), so each is rendered, or shows its source with the line
   * that says why.
   *
   * @param {HTMLElement} node
   * @returns {Promise<void>}
   */
  function textsSettled(node) {
    const waits = () => node.querySelector(".github-pull-plain-pending") !== null;
    if (!waits()) {
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      const check = () => {
        if (!waits() || listening.signal.aborted) {
          pendingWatchers.delete(check);
          resolve();
        }
      };
      pendingWatchers.add(check);
    });
  }

  /**
   * Resolve once the guide's introduction, *node*, shows as it will stay (`textsSettled`), or
   * once `GUIDE_INTRODUCTION_HOLD_MS` has passed, so a render that never ends never keeps the
   * guide out of sight: the overview then shows with the description's placeholder.
   *
   * @param {HTMLElement} node
   * @returns {Promise<void>}
   */
  function introductionSettled(node) {
    /** @type {number | undefined} */
    let timer;
    const bound = new Promise((resolve) => {
      timer = window.setTimeout(resolve, GUIDE_INTRODUCTION_HOLD_MS);
    });
    return Promise.race([textsSettled(node), bound]).then(() => {
      window.clearTimeout(timer);
    });
  }

  /** @param {PullModel} model */
  function paintGuided(model) {
    const moved = model.newCommits !== null;
    if (guided !== null) {
      paintGuideIntroduction(model, guided);
      guided.view?.show(model.recordRevision, moved);
      return;
    }
    // The guide's first step is asked for now, beside the module's import, rather than
    // after it; the guide reads the same request (guide-reads.js).
    if (model.recordRevision !== null) {
      guideReads.prefetch(guideAsks({ kind: "pull", number }), 1, model.recordRevision, moved);
    }
    // The description shows with the guide's first answer, as its overview.
    const introduction = h("div", { hidden: "" }, []);
    const host = h(
      "section",
      { class: "github-pull-guided-review", "aria-label": "Guided Review" },
      [
        introduction,
        h(
          "div",
          { class: "mb-delayed-loading", role: "status", "aria-label": "Loading the guide" },
          [h("div", { class: "recent-loading github-pull-loading", "aria-hidden": "true" })],
        ),
      ],
    );
    /** @type {GuidedMount} */
    const mount = { view: null, introduction: { node: introduction, key: null, block: null } };
    guided = mount;
    body.replaceChildren(host);
    paintGuideIntroduction(model, mount);
    void import("./guided-review.js").then(
      ({ mountGuidedReview }) => {
        if (guided !== mount || shown === null) {
          return;
        }
        /** @type {import("./guided-review.js").GuideSubject} */
        const subject = { kind: "pull", number };
        // The guide's text is KPress prose and its excerpts are the diff plugin's rows.
        mount.view = mountGuidedReview(host, introduction, subject, {
          open: openChangedFile,
          // Another pull request a step cites, or a file in its Changes, opened as a stack
          // member's link opens it.
          openPull: (target, path) =>
            void open(
              path === null
                ? { number: target, tab: "" }
                : { number: target, tab: "files", file: path, replace: false, jumped: false },
            ),
          age: (iso) => age(iso),
          shortCommit: (sha) => mb.shortCommit(sha),
          // A cited pull request's title and author, as a stack menu's member draws them, and
          // the Layers glyph that names a stack other than the guide's.
          titleNodes: mb.titleNodes,
          stackGlyph: () => (stackSvg === null ? null : document.importNode(stackSvg, true)),
          identity: (login, avatar) =>
            authorLabel(mb, login, avatar, "github-pull-stack-member-author", {
              placeholder: false,
            }),
          loadStyles: (assets) =>
            Promise.all([
              textStyles(
                /** @type {Parameters<MetabrowserPublicSdk["loadKpressAssets"]>[0]} */ (assets),
              ),
              mb.ensureKindAssets("diff"),
            ]),
          // The diff plugin draws the excerpts, as it draws Changes (`requires` in
          // manifest.toml).
          loadDrawPatch: async () => {
            const diff = await mb.plugins.load("diff");
            return diff.guidePatchDrawer();
          },
          // A file a step cites whole that the rendered route renders is the diff plugin's
          // own view of it, from this page's comparison while it is the one the step was read
          // at, or, a file of another pull request, from that one's comparison, whose routes
          // the step's answer names: a Markdown file drawn as Docs draws it (`DOCS_DRAWING`),
          // and a YAML or JSON file as Changes does (`CHANGES_DRAWING`).
          loadDrawDocument: async () => {
            const diff = await mb.plugins.load("diff");
            /**
             * @param {{merge_base: string | null, head: string, route?: string,
             *   image_route?: string, rendered_route?: string}} pins
             */
            const at = (pins) => {
              const cited = citedPullComparison(pins);
              if (cited !== null) {
                return cited;
              }
              const comparison = shown?.comparison ?? null;
              return comparison !== null &&
                comparison.left === pins.merge_base &&
                comparison.right === pins.head
                ? { ...comparison, base_policy: /** @type {const} */ ("merge_base") }
                : null;
            };
            return {
              draws: (pins) => at(pins) !== null,
              source(path, pins) {
                const comparison = at(pins);
                return comparison === null
                  ? null
                  : {
                      path,
                      load: (signal) => diff.loadFullSource(comparison, path, signal),
                    };
              },
              mount(body, path, format, pins) {
                const comparison = at(pins);
                if (comparison === null) {
                  return { settled: Promise.resolve(false), dispose() {} };
                }
                return diff.mountRenderedFile(body, comparison, path, {
                  ...(format === "markdown" ? DOCS_DRAWING : CHANGES_DRAWING),
                  // Its rendered layer waits for Rendered with Source hidden for as long as
                  // the rendered route can take, so the step never shows Source first in
                  // its place (`GUIDE_DOCUMENT_HOLD_MS`).
                  markdownHoldMs: GUIDE_DOCUMENT_HOLD_MS,
                });
              },
            };
          },
          // A note's Markdown, which the route renders inert as it renders a description, is
          // inserted through the description's allowlist.
          loadDrawProse: async () => {
            const inert = await inertReady;
            if (inert === null) {
              throw new Error("the inert HTML allowlist did not load");
            }
            return (html) => inertProse(inert, html);
          },
          // A refused note says why in a description's words.
          refusalNote: textRefusalNote,
          // The overview shows the description once its Markdown is drawn, or its source
          // with the line that says why, never its source and then its rendering, waiting
          // at most `GUIDE_INTRODUCTION_HOLD_MS`.
          introductionReady: () => introductionSettled(introduction),
          // A step's neighbors are read when the page is idle, after what it shows.
          ahead: (run) => mb.whenIdle(run, { timeout: PREFETCH_IDLE_TIMEOUT_MS }),
        });
        mount.view.show(shown.recordRevision, shown.newCommits !== null);
      },
      () => {
        if (guided === mount) {
          // The description is kept out of sight for the guide's first answer, which never
          // comes now, so it shows here, above the line that says why.
          introduction.hidden = false;
          host.replaceChildren(
            introduction,
            h("p", { class: "github-pull-quiet", role: "status" }, [
              "Could not load Guided Review.",
            ]),
          );
        }
      },
    );
  }

  /**
   * The note over a diff that replaced another by itself, and the way back.
   * Kept as painted while it says the same, so focus on its button survives a repaint.
   */
  function paintFollowed() {
    const note = diffFor === null || changesChosen ? null : followedNote(changesFrom, diffFor);
    const key = JSON.stringify(note);
    const painted = /** @type {HTMLElement | null} */ (body.querySelector(".github-pull-followed"));
    if (painted !== null && painted.dataset.note === key) {
      return;
    }
    painted?.remove();
    if (note === null) {
      return;
    }
    const back = h("button", { type: "button", class: "btn github-pull-earlier" }, [
      "Show the earlier changes",
    ]);
    back.addEventListener("click", () => {
      showEarlier();
      if (shown !== null) {
        paintFiles(shown);
      }
    });
    const said = notice(null, [
      note.kind === "head"
        ? "Changes now show this pull request’s newer commits. "
        : "The comparison has changed. ",
      back,
    ]);
    said.classList.add("github-pull-followed");
    said.dataset.note = key;
    body.prepend(said);
  }

  /** @param {PullModel} model */
  function paint(model) {
    container.dataset.corePreview = String(model.corePreview);
    shown = model;
    noteRefreshWait(model);
    if (model.tab !== "guided" || model.pull === null) {
      disposeGuided();
    }
    if (model.tab !== "files") {
      wantedFile = null;
    }
    if (firstPaint !== null && (model.tab !== "" || model.pull === null)) {
      // Another tab holds the body now: the conversation paints as it is when it returns.
      releaseFirstPaint("closed");
    }
    const conversation = model.pull !== null && model.tab === "";
    const key = conversation ? conversationKey(model) : null;
    const action =
      key === null
        ? null
        : conversationAction(
            { key: bodyKey, textRevision: markdownRevision },
            { key, textRevision: model.textRevision },
          );
    const hold = action === "repaint" ? holdFirstPaint(model) : null;
    // The header paints the record at once, held or not: only the body waits for its
    // Markdown, so the title shows as soon as the record is in hand (exp-099).
    paintHeader(model);
    askDocs(model);
    readGuideAhead(model);
    paintStacks(model);
    // Conversation, Guided Review, and Checks use the reading column. Changes and Docs use the
    // full pane.
    body.classList.toggle("page-reading-column", model.pull === null || !diffTab(model.tab));
    if (model.pull === null) {
      disposeDiff();
      paintSummaryWait(model);
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
    if (diffTab(model.tab)) {
      bodyKey = "";
      bodyShows = "files";
      discussion = null;
      texts.clear();
      paintFiles(model);
      return;
    }
    disposeDiff();
    wantComparison(model);
    if (model.tab === "guided") {
      bodyKey = "";
      bodyShows = "guided";
      discussion = null;
      texts.clear();
      observer?.disconnect();
      paintGuided(model);
      return;
    }
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
    markdownRevision = model.textRevision;
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
    // A core preview's is held too: its description renders from the core (mb-d59o).
    if (firstPaintSpent || model.textRevision === null || pull === null) {
      return null;
    }
    if (bodyShows === "files" || bodyShows === "checks" || bodyShows === "guided") {
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
          showPending(element, part, value);
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
              // When the wait the server named for a read its budget refused ends, in
              // `Date.now()` time; null for a transient failure's one retry. The wait
              // itself, which bounds what is left of it when the clock steps back.
              heldUntil: null,
              heldMs: 0,
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
      !addressShows("")
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
    // A wait the server's budget asked for is not the transient failure's one retry.
    const afterHold = retrying && held.heldUntil !== null;
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
    const owns = () => commitTimeline === held && held.read === read && addressShows("");
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
        // A read the server's budget held spent none: it is asked for until it is read.
        held.retryPending = false;
        held.settled = held.heldUntil === null;
        held.heldUntil = null;
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
      } else if (!cachedOnly && projection?.retryable && projection.heldMs !== null) {
        // The server's budget refused the read, at no cost to GitHub: ask again when it
        // says, for as long as it refuses and this record's page stays.
        held.settled = false;
        held.retryPending = true;
        held.heldMs = projection.heldMs;
        held.heldUntil = Date.now() + projection.heldMs;
        followTimeline();
      } else if (!cachedOnly && (!retrying || afterHold) && projection?.retryable) {
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
      // A paint during a refresh ask cancels the wait (`timelineAllowed`), and the next one
      // waits only what is left of it, so the server's minute is a period, not a minimum
      // that each refresh ask starts again (review B3 of #737), and never more than the
      // server asked when the clock steps back (review D4).
      const delay =
        held.heldUntil === null
          ? TIMELINE_RETRY_MS
          : Math.min(held.heldMs, Math.max(0, held.heldUntil - Date.now()));
      const timer = window.setTimeout(() => void load(), delay);
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
  tabKeys = attachTabKeys(
    mb.shortcuts,
    tabLinks,
    (tab) => {
      // A hidden tab's key does nothing, as its link offers nothing.
      if (!tabLinks.some(({ id, link }) => id === tab && link.hidden)) {
        page.setTab(routeForTab(tab, shown?.pull?.text ?? null));
      }
    },
    listening.signal,
  );
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
      // A hold's lift time as the reader's clock says it, short (`holdLiftText`).
      formatHold: (liftMs, nowMs) => holdLiftText(liftMs, nowMs),
      ownsChanges: () => onDiffRoute(),
      ownsConversation: () => active && mb.sourceKind() === "filesystem" && addressShows(""),
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
      // The diff plugin's one switch, which this page's Changes uses too, so a View on
      // branch and a Browse code never race, and both say a refusal in the same words. The
      // switch is in a module the diff plugin loads on demand, so the plugin's assets, or
      // that module, failing to load is said as a failed request, never left unhandled.
      async switchPin(selection, wanted) {
        const failed = /** @type {const} */ ({
          kind: "refused",
          message: "The switch request failed.",
        });
        try {
          await mb.ensureKindAssets("diff");
          const view = /** @type {{switchPin?: PullDependencies["switchPin"]} | null} */ (
            mb.getRegisteredView("diff", "diff")
          );
          return typeof view?.switchPin === "function"
            ? await view.switchPin(selection, wanted)
            : failed;
        } catch {
          return failed;
        }
      },
      navigate: (href) => window.location.assign(href),
      renderMarkdown,
      listed: listedState,
      noteRecord,
      textUnavailable(part, text, note) {
        if (note) {
          refusedText(part, text, note);
        }
        showPendingPart(part);
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
      checkoutPin,
    },
  );
  document.addEventListener(
    "visibilitychange",
    () => {
      controller.onVisibilityChange();
      followTimeline();
      // A page opened behind another tab is not prefetched until it is looked at: the
      // wish is not recorded while hidden, so it is asked again when shown, on every tab
      // that paints it (A2 of review A on #470).
      if (document.visibilityState === "visible" && shown !== null) {
        wantComparison(shown);
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
    place = keepPlace(pane, body, () => addressShows(shown?.tab ?? ""), {
      pathOf: (block) =>
        /** @type {{pathForSection?: (section: Element) => string | null} | null} */ (
          diffHandle
        )?.pathForSection?.(block) ?? null,
      sectionOf(path) {
        const section = /** @type {{sectionForPath?: (path: string) => Element | null} | null} */ (
          diffHandle
        )?.sectionForPath;
        return typeof section === "function" ? section(path) : undefined;
      },
    });
    place.keeper.land();
  }

  /** Stop ownership-bound work while preserving this page's inert handoff DOM. */
  function cancelPending() {
    releaseFirstPaint("closed", false);
    resolveReady();
    filesRefresh = null;
    wantedFile = null;
    listening.abort();
    disposeGuided();
    cancelGuideAhead?.();
    cancelGuideAhead = null;
    for (const check of [...pendingWatchers]) {
      check();
    }
    summaryBrief?.dispose();
    // A disposed binding leaves its figures as drawn, so the handoff keeps them on screen.
    for (const text of [...textDiagrams.keys()]) {
      disposeTextDiagrams(text);
    }
    cancelTimeline();
    body.querySelector(".github-pull-diff-loading")?.remove();
    observer?.disconnect();
    place?.dispose();
    controller.dispose();
    prefetch.dispose();
    markdownAsked.controller?.abort();
    summaryShown.handle?.dispose();
    summaryShown = { key: "", claim: summaryShown.claim + 1, handle: null };
    // A wait the reader left before it ended never completed for them (reported if late).
    summaryWait?.end("never_completed");
    summaryWait = null;
    refreshWait?.end("never_completed");
    refreshWait = null;
    closeDetails();
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
        void open(memberRoute(stack.pulls[at], stackTab(controller.snapshot().tab)));
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
        // A tab already on screen at another of the page's addresses, Guided Review on the
        // front page, stays where it is: its own address would be a second history entry
        // of the same view.
        if (!addressShows(shownTabFor(next, shown?.pull?.text ?? null))) {
          void open({ number, tab: next });
        }
        return;
      }
      const changed = controller.snapshot().tab !== shownTabFor(next, shown?.pull?.text ?? null);
      controller.setTab(next);
      if (changed) {
        place?.keeper.land();
      }
      rememberLanded();
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
      rememberLanded();
    },
    /** History is about to leave this entry: write its place now. */
    flush() {
      place?.keeper.flush();
    },
    /**
     * Go to a file of Files changed, for a list of the pull request's files beside the page.
     * docs/project/architecture/arch-diff-pipeline.md, "Hydration", says what it promises.
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
      // A walk's key moves no address: the walk lands the page once it stops (`setTab`).
      if (!settling) {
        rememberLanded();
      }
      // Still on Docs, its diff holds the documents alone: the file lands once Changes
      // has mounted the whole comparison.
      return (diffShows === "docs" ? null : landFile()) ?? { kind: "no_diff", path };
    },
    /**
     * Whether Files changed holds a path, typed as `scrollToFile` is: `no_diff` while no
     * diff is mounted, else what the diff says, `file` or `not_in_comparison`.
     *
     * @param {string} path
     * @returns {import("../diff/diff-view.js").FileLookup | {kind: "no_diff", path: string}}
     */
    fileForPath(path) {
      if (diffShows === "docs") {
        // Docs holds the documents alone, so its diff cannot say a path is not in the
        // comparison; showing one moves to Changes, which can.
        return { kind: "no_diff", path };
      }
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
    /**
     * Whether the page has something to refresh now: a stale record whose own refresh did
     * not run, a failure, the comparison Changes or Docs shows, or a pull request not fetched
     * yet. The navigation's Refresh reads it before it runs the page's part (mb-ablv).
     */
    canRefresh: () => !listening.signal.aborted && shown?.canRefresh === true,
    /**
     * What the page's own Refresh did, which the navigation's one Refresh runs as the page's
     * part (static/refresh-plan.js, through the Pulls tab's list): the record, with the
     * comparison on screen on Changes and Docs, or Fetch before a record. Nothing while the
     * page cannot refresh. Settles when the refresh it asked for has been answered.
     */
    refresh: refreshShown,
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
 * @param {() => boolean} owns Whether the address still shows this page's tab.
 * @param {{pathOf(block: Element): string | null, sectionOf(path: string): Element | null | undefined}} files
 *   Which changed file a block of Changes is, and the block of a file, as the mounted diff
 *   says, so a place there is its file's whichever diff shows it (`PanePlace`). *sectionOf*
 *   answers null for a file the diff lacks and undefined while no diff can say.
 */
function keepPlace(pane, body, owns, files) {
  const blocks = () => Array.from(body.querySelectorAll(PLACE_BLOCKS));
  /** @param {Element[]} [of] */
  const tops = (of = blocks()) => {
    const viewTop = pane.getBoundingClientRect().top;
    return of.map((block) => block.getBoundingClientRect().top - viewTop + pane.scrollTop);
  };
  /** @returns {PanePlace} */
  const measure = () => {
    const of = blocks();
    const at = placeAt(tops(of), pane.scrollTop);
    const file = at.block < 0 ? null : files.pathOf(of[at.block]);
    return file === null ? at : { ...at, file };
  };
  const keeper = createScrollKeeper({
    read: () => window.history.state?.[PLACE_KEY],
    write(place) {
      // History can move on before this page is told: the entry is written only while
      // it is still this page's.
      if (owns()) {
        window.history.replaceState({ ...window.history.state, [PLACE_KEY]: place }, "");
      }
    },
    measure,
    apply(place) {
      const of = blocks();
      const section = place.file === undefined ? undefined : files.sectionOf(place.file);
      const top = scrollTopOf(
        place,
        tops(of),
        section === undefined ? undefined : section === null ? -1 : of.indexOf(section),
      );
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
    measure,
    dispose() {
      listening.abort();
      heights.disconnect();
      keeper.dispose();
    },
  };
}
