// A pull request's page: header, conversation, reviews, review comments, checks, and
// Files changed, from the cached record alone. The number is the page's one input, and
// every route it asks names it, so a page for any number opens the same way.
//
// Every decision lives here without a DOM. `describePull` turns one answer of
// `GET /api/plugin/github/pull` into what the page shows; `createPullController` owns
// polling that route while the page is visible (quickly while a refresh runs or the
// record is pending, slowly otherwise, with If-None-Match so an unchanged answer is a
// 304), the refresh a stale page asks for and offers and an absent page offers
// (`POST /api/plugin/github/pull-refresh`), the
// switch to the pull request's head when the pin is elsewhere (`POST /api/source/pin`),
// the tab, and the Markdown of each text, asked for one part at a time from
// `GET /api/plugin/github/pull-markdown` and kept only for the record it was rendered
// from. `mountPullPage` is the browser glue: real fetch, timers, and paint.
// tests/dom/github-pull-page-session.js runs the same functions from the command line.
//
// What starts a fetch: a page opened at an address shows what is cached, whether the address
// was typed, followed from rendered content, or reached by Back, so only a reader's press of
// Fetch adds a pull request to the cache. A page with a record refreshes it by itself while
// it is visible and stale, as a stale mirror does, once per visible period, and the server
// holds each number to one attempt per window.
//
// All text is the pull request's own and untrusted. Paint writes it with textContent;
// only KPress's Markdown HTML is parsed, and only after it is reduced to an allowlist of
// plain markup twice: by the hook on the server (src/metabrowser/inert_html.py), and by
// static/inert-html.js, which rebuilds the inserted nodes from an inert template. No
// class, id, data, style, or event attribute survives, nor any SVG, media, stylesheet,
// frame, or form; an image becomes a link to it; a link is made absolute against the
// pull request's github.com page, kept only for http(s), and opened in a new tab with
// rel="noopener noreferrer"; and no KPress script or stylesheet is loaded for a text.

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
// How long the pane stays still before its place is written to the history entry. A click
// writes at once, so this only keeps a moving pane from calling `history.replaceState`,
// which Safari limits to 100 calls in 30 s.
export const PLACE_WRITE_MS = 100;
// How long a landing holds its place after the page last changed height, for a page still
// rendering what it fetches. Measured 2026-11-02 in Chrome 152, Back onto a page loaded
// again, the widest gap between two changes in height: 231 ms for 34 files, 501 ms for a
// PR of 137 files whose diffs load as they come near, and 17 ms for a conversation of 120
// texts. A page that changes later than this keeps its place by the browser's own scroll
// anchoring, except in a browser without it.
export const LANDING_SETTLE_MS = 2000;
// The blocks a place is counted in: the conversation's cards and sections, and Files
// changed's files, which keep their order for as long as the page shows one comparison.
const PLACE_BLOCKS = ".github-pull-card, .github-pull-section, .diff-file";
// The key of a place in `history.state`, which no other code of the shell writes into.
const PLACE_KEY = "pullPlace";

const PULL_ROUTE = "/api/plugin/github/pull";
const REFRESH_ROUTE = "/api/plugin/github/pull-refresh";
const MARKDOWN_ROUTE = "/api/plugin/github/pull-markdown";
const PIN_ROUTE = "/api/source/pin";
export const TABS = Object.freeze(["", "files"]);

/** @type {Readonly<Record<string, string>>} */
const ABSENCE = Object.freeze({
  not_github: "This server serves no GitHub repository.",
  not_cached: "No data for this pull request is cached yet.",
  schema_mismatch: "The cached data for this pull request is from another version.",
  unreadable: "The cached data for this pull request could not be read.",
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
  mergeable: "No conflicts with the base branch",
  conflicting: "Conflicts with the base branch",
  unknown: "Merge status unknown",
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
 * @typedef {{earlier: HunkLine[], shown: HunkLine[]}} HunkView
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
 *   comparison: {left: string, right: string, headMoved: boolean} | null,
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

/** @param {Record<string, any>} pull */
function displayState(pull) {
  if (pull.merged === true) {
    return "merged";
  }
  if (pull.state === "open") {
    return pull.draft === true ? "draft" : "open";
  }
  return "closed";
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
 * commented range if that is further back than `HUNK_TAIL_LINES`, and `earlier` is the
 * rest, in order, for the disclosure. Counted back from the end, where the commented
 * line is, along the comment's side of the diff, because a hunk cut to fit the record has
 * lost its `@@` line and the numbers it starts from. A range reaching above what the
 * record kept shows all of it. A comment is on one side here: the record does not keep
 * `start_side`, so a range starting on the other side is counted on this one, and any of
 * it that falls outside the tail is in the disclosure.
 *
 * @param {string} hunk
 * @param {Record<string, any>} comment
 * @returns {HunkView}
 */
export function hunkView(hunk, comment) {
  /** @type {HunkLine[]} */
  const lines = hunk
    .replace(/\n$/, "")
    .split("\n")
    .map((line) => ({ kind: hunkLineKind(line), text: line }));
  const side = comment.side === "LEFT" ? "del" : "add";
  let remaining = commentedSpan(comment);
  let rangeStart = lines.length;
  for (let index = lines.length - 1; index >= 0 && remaining > 0; index -= 1) {
    if (lines[index].kind === "context" || lines[index].kind === side) {
      remaining -= 1;
      rangeStart = index;
    }
  }
  const first = Math.min(rangeStart, lines.length - HUNK_TAIL_LINES);
  // A disclosure is a row of its own, so it never hides less than a row's worth: one
  // line, in practice the `@@` line of a hunk just past the tail.
  const cut = first <= 1 ? 0 : first;
  return { earlier: lines.slice(0, cut), shown: lines.slice(cut) };
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
 * What the page shows for one answer of the pull route. Pure.
 *
 * @param {PullEnvelope | null} envelope
 * @param {{number: number, tab: string, nowMs: number, error?: string | null}} page
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
    model.message =
      envelope.state === "pending"
        ? "Fetching the pull request…"
        : (page.error ??
          ABSENCE[envelope.reason ?? ""] ??
          "No data for this pull request is cached.");
    model.canRefresh =
      envelope.state === "absent" && envelope.reason !== "not_github" && !envelope.refreshing;
    return model;
  }
  model.recordAt = typeof record.fetched_at === "string" ? record.fetched_at : null;
  model.message = page.error ?? null;
  model.canRefresh = envelope.state === "stale" && !envelope.refreshing;
  const age = relativeAge(record.fetched_at ?? null, page.nowMs);
  model.freshness = envelope.refreshing
    ? `Refreshing… · fetched ${age} by ${text(record.reader)}`
    : `Fetched ${age} by ${text(record.reader)}${envelope.state === "stale" ? " · may be out of date" : ""}`;
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
  if (envelope.pin !== null && head !== "" && envelope.pin !== head) {
    // The served code is not the head this record names: the pull request could not be
    // opened when serving began and the pin fell back to the default branch or a commit,
    // or a refresh found a newer head. The head is GitHub's own ref, which the refresh
    // fetched, so the page offers to serve it rather than switching under the reader.
    model.headOffer = {
      ref: `refs/pull/${pull.number}/head`,
      head,
      pin: envelope.pin,
      text: `This page's code is ${envelope.pin.slice(0, 12)}, not the pull request's head ${head.slice(0, 12)}.`,
    };
  }
  const comparison = record.comparison;
  if (comparison && typeof comparison.base === "string" && typeof comparison.head === "string") {
    model.comparison = {
      left: comparison.base,
      right: comparison.head,
      // The page's code is the served pin; a record read at a newer head says so
      // rather than moving what the reader sees.
      headMoved: envelope.pin !== null && envelope.pin !== comparison.head,
    };
  }
  return model;
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
 * }} PullDependencies
 */

/**
 * The polling, refresh, tab, and Markdown state machine for one page.
 *
 * @param {PullDependencies} deps
 * @param {{number: number, tab: string}} options
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
  /** @type {string | null} */
  let error = null;
  /** @type {string | null} */
  let painted = null;
  /** Markdown by part, for the record fetched at `markdownFor`. @type {Map<string, Record<string, any>>} */
  const markdown = new Map();
  /** @type {string | null} */
  let markdownFor = null;
  /** @type {string[]} */
  const queue = [];
  const asked = new Set();
  let inFlight = 0;

  function model() {
    return describePull(envelope, { number: options.number, tab, nowMs: deps.now(), error });
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
      } else if (response.status === 304) {
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
    if (
      deps.isVisible() &&
      envelope?.state === "stale" &&
      !envelope.refreshing &&
      !refreshAskedWhileVisible
    ) {
      refreshAskedWhileVisible = true;
      await askForRefresh({ number: options.number });
    }
  }

  /**
   * Ask the server for a refresh and take the envelope it answers with. A refusal of the
   * page's own request says nothing to the reader, whose page still shows what it did and
   * still offers Refresh.
   *
   * @param {{number: number, retry?: boolean}} ask
   */
  async function askForRefresh(ask) {
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
        // The answer changed; the next poll must not be answered by a 304.
        etag = null;
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
   * Serve the pull request's head, which the page offers when the pin is elsewhere, and
   * reload so every view shows it. `POST /api/source/pin` is the freshness row's own
   * switch; a refusal says why and the page stays as it was.
   */
  async function switchToHead() {
    const offer = model().headOffer;
    if (disposed || switching || offer === null) {
      return;
    }
    switching = true;
    try {
      const response = await deps.request("POST", PIN_ROUTE, { body: { ref: offer.ref } });
      if (response.status === 200) {
        deps.reload();
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
      refreshAskedWhileVisible = false;
      return;
    }
    void poll();
  }

  function dispose() {
    disposed = true;
    clearTimer();
    queue.length = 0;
  }

  return Object.freeze({
    start: () => {
      render();
      return poll(true);
    },
    poll: () => poll(),
    requestRefresh,
    switchToHead,
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
 * What Files changed does with the record's comparison. Pure.
 *
 * The diff keeps the comparison it was opened on: a record read at a newer head offers
 * it rather than changing the diff under the reader.
 *
 * @param {{left: string, right: string} | null} mounted The comparison the diff shows.
 * @param {{left: string, right: string} | null} comparison The record's.
 * @returns {"unavailable" | "mount" | "keep" | "offer"}
 */
export function filesAction(mounted, comparison) {
  if (comparison === null) {
    return "unavailable";
  }
  if (mounted === null) {
    return "mount";
  }
  return mounted.left === comparison.left && mounted.right === comparison.right ? "keep" : "offer";
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
function isPlainClick(event) {
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
function h(tag, attributes = {}, children = []) {
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
  const header = h("div", { class: "github-pull-header" });
  const body = h("div", { class: "github-pull-body" });
  const live = h("span", { class: "sr-only", "aria-live": "polite" });
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
  /** @type {{left: string, right: string} | null} */
  let diffFor = null;
  /** @type {{dispose?: () => void} | null} */
  let diffHandle = null;
  /** @type {HTMLElement | null} */
  let diffHost = null;
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

  /** @param {string} iso */
  const when = (iso) => {
    const at = Date.parse(iso);
    return Number.isFinite(at) ? mb.formatTimestamp(at / 1000) : iso;
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
      element.append(
        h("p", { class: "github-pull-note" }, ["This text was cut; the rest is on GitHub."]),
      );
    }
    texts.set(part, element);
    if (part === "body" || observer === null) {
      controller.requestMarkdown(part);
    } else {
      observer.observe(element);
    }
    return element;
  }

  /**
   * @param {string} part
   * @param {Record<string, any>} rendered
   */
  function renderMarkdown(part, rendered) {
    void inertReady.then((inert) => {
      const element = texts.get(part);
      const plain = element?.querySelector(":scope > .github-pull-plain");
      if (!element || !plain || inert === null) {
        return;
      }
      const holder = h("div", { class: "github-pull-markdown" });
      // KPress's Markdown HTML, reduced to the allowlist on the server; GitHub's own
      // body_html is never used, and no KPress script or stylesheet is loaded for it.
      // static/inert-html.js parses it into an inert template and inserts only nodes
      // rebuilt from the same allowlist, links made absolute against the pull request.
      holder.replaceChildren(
        ...inert.sanitizeHtml(String(rendered.html), shown?.pull?.htmlUrl ?? "https://github.com/"),
      );
      plain.replaceWith(holder);
    });
  }

  /** @param {string} path @param {number | null} line */
  function fileLink(path, line) {
    const wire = mb.sourceKind() === "git_revision" && path !== "" ? gitPathWire(path) : null;
    if (wire === null) {
      return h("code", {}, [path]);
    }
    const target = { path: wire, ...(line === null ? {} : { fragment: `L${line}` }) };
    const link = h("a", { href: mb.navigation.href(target), class: "github-pull-file" }, [
      h("code", {}, [line === null ? path : `${path}:${line}`]),
    ]);
    link.addEventListener("click", (event) => {
      if (!isPlainClick(event)) {
        return;
      }
      event.preventDefault();
      void mb.navigation.open(target);
    });
    return link;
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
    h("span", { class: `github-pull-badge github-pull-${kind}`, "data-state": state }, [label]);

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
          badge(pull.state, pull.stateLabel),
          h("span", {}, [
            pull.actor === null ? null : h("strong", {}, [pull.actor]),
            `${pull.actor === null ? "" : " "}${pull.action} `,
            h("code", {}, [pull.base]),
            " from ",
            h("code", {}, [pull.head]),
          ]),
        ]),
        h("div", { class: "github-pull-meta github-pull-quiet" }, [
          `Opened ${when(pull.created)} · updated ${when(pull.updated)}`,
          pull.closed && pull.closedLabel ? ` · ${pull.closedLabel} ${when(pull.closed)}` : "",
          " · ",
          outside(pull.htmlUrl, "", ["View on GitHub"]),
          " · ",
          h("a", { href: mb.navigation.href({ path: "" }) }, ["Browse code"]),
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
    if (model.pull !== null) {
      const tabs = h("div", { class: "github-pull-tabs", role: "tablist" });
      for (const [id, label] of [
        ["", "Conversation"],
        ["files", "Files changed"],
      ]) {
        const button = pageLink({ number: model.number, tab: id }, "github-pull-tab", [label]);
        button.setAttribute("role", "tab");
        button.setAttribute("aria-selected", String(model.tab === id));
        tabs.append(button);
      }
      children.push(tabs);
    }
    header.replaceChildren(...children.filter((child) => child !== null));
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
          ` opened ${when(pull.created)}`,
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
      head.append(item.at === null ? " (pending)" : ` ${when(item.at)}`);
      const card = h("section", { class: `github-pull-card github-pull-${item.kind}` }, [head]);
      if (item.text.trim() !== "" || item.kind === "comment") {
        card.append(textBlock(item.part, item.text, item.truncated));
      }
      sections.push(card);
    }
    if (model.reviewComments.length > 0) {
      const threads = h("section", { class: "github-pull-section" }, [
        h("h2", {}, [`Review comments (${model.reviewComments.length})`]),
      ]);
      for (const comment of model.reviewComments) {
        const head = h("div", { class: "github-pull-card-head" }, [
          fileLink(comment.path, comment.line),
          comment.outdated ? " " : "",
          comment.outdated ? badge("outdated", "outdated", "review") : null,
          " ",
          h("strong", {}, [comment.author]),
          ` ${comment.reply ? "replied" : "commented"} ${when(comment.at)}`,
        ]);
        const card = h(
          "div",
          { class: `github-pull-card${comment.reply ? " github-pull-reply" : ""}` },
          [head],
        );
        if (!comment.reply && comment.hunk !== null) {
          const { earlier, shown: tail } = comment.hunk;
          if (earlier.length > 0) {
            // Native, so opening it asks nothing of the page and a repaint just closes it.
            card.append(
              h("details", { class: "github-pull-hunk-earlier" }, [
                h("summary", { class: "section-disclosure-trigger" }, [
                  `${earlier.length} earlier lines`,
                ]),
                hunkLines(earlier),
              ]),
            );
          }
          card.append(hunkLines(tail));
          if (comment.hunkTruncated) {
            card.append(h("p", { class: "github-pull-note" }, ["The start of this hunk was cut."]));
          }
        }
        card.append(textBlock(comment.part, comment.text, comment.truncated));
        threads.append(card);
      }
      sections.push(threads);
    }
    const summary = model.checks;
    const checksSection = h("section", { class: "github-pull-section" }, [h("h2", {}, ["Checks"])]);
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
      sections.push(h("p", { class: "github-pull-note" }, [note]));
    }
    body.replaceChildren(...sections);
  }

  function disposeDiff() {
    diffHandle?.dispose?.();
    diffHandle = null;
    diffHost = null;
    diffFor = null;
  }

  /** @param {{left: string, right: string}} comparison */
  async function mountDiff(comparison) {
    disposeDiff();
    const host = h("div", { class: "github-pull-diff metabrowser-diff-host" });
    diffHost = host;
    diffFor = comparison;
    body.replaceChildren(host);
    await mb.ensureKindAssets("diff");
    const view = mb.getRegisteredView("diff", "diff");
    if (diffHost !== host) {
      return;
    }
    if (!view) {
      host.textContent = "The diff plugin is unavailable.";
      return;
    }
    const handle = /** @type {{dispose?: () => void} | null} */ (
      await view.render(host, {
        comparison: { left: comparison.left, right: comparison.right, base_policy: "merge_base" },
      })
    );
    if (diffHost !== host) {
      handle?.dispose?.();
      return;
    }
    diffHandle = handle;
  }

  /** @param {PullModel} model */
  function paintFiles(model) {
    const comparison = model.comparison;
    const action = filesAction(diffFor, comparison);
    if (comparison === null || action === "unavailable") {
      disposeDiff();
      body.replaceChildren(
        h("p", { class: "github-pull-note" }, [
          "Files changed is unavailable: the pull request's base could not be compared with its head.",
        ]),
      );
      return;
    }
    if (action === "mount") {
      void mountDiff(comparison);
    } else if (action === "offer") {
      const offer = h("button", { type: "button", class: "btn github-pull-newer" }, [
        "Show the newer changes",
      ]);
      offer.addEventListener("click", () => void mountDiff(comparison));
      body.querySelector(".github-pull-newer-offer")?.remove();
      body.prepend(
        h("p", { class: "github-pull-note github-pull-newer-offer" }, [
          `The pull request now ends at ${comparison.right.slice(0, 12)}. `,
          offer,
        ]),
      );
    }
  }

  /** @param {PullModel} model */
  function paint(model) {
    shown = model;
    paintHeader(model);
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
      renderMarkdown,
    },
    { number, tab: typeof ctx.tab === "string" ? ctx.tab : "" },
  );
  const listening = new AbortController();
  document.addEventListener("visibilitychange", controller.onVisibilityChange, {
    signal: listening.signal,
  });
  void controller.start();
  const place = pane === null ? null : keepPlace(pane, body, () => shown?.tab ?? "", number);
  place?.keeper.land();
  return Object.freeze({
    /** @param {string} next */
    setTab(next) {
      const changed = controller.snapshot().tab !== next;
      controller.setTab(next);
      if (changed) {
        place?.keeper.land();
      }
    },
    dispose() {
      listening.abort();
      observer?.disconnect();
      place?.dispose();
      controller.dispose();
      disposeDiff();
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
      const route = `/pull/${number}${tab() ? `/${tab()}` : ""}`;
      if (window.location.pathname.replace(/\/$/, "") === route) {
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
  pane.addEventListener("click", keeper.flush, { capture: true, signal });
  // Whatever a reader moves the pane with: a wheel, a finger, a scrollbar, a key. Only input
  // says so, since the browser's own scroll anchoring also moves a page that changes height.
  for (const type of ["wheel", "touchstart", "pointerdown"]) {
    pane.addEventListener(type, keeper.readerMoved, { capture: true, passive: true, signal });
  }
  window.addEventListener("keydown", keeper.readerMoved, { capture: true, signal });
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
