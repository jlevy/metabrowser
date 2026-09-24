// The served pull request's page: header, conversation, reviews, review comments,
// checks, and Files changed, from the cached record alone.
//
// Every decision lives here without a DOM. `describePull` turns one answer of
// `GET /api/plugin/github/pull` into what the page shows; `createPullController` owns
// polling that route while the page is visible (quickly while a refresh runs or the
// record is pending, slowly otherwise, with If-None-Match so an unchanged answer is a
// 304), the refresh a stale page offers (`POST /api/plugin/github/pull-refresh`), the
// switch to the pull request's head when the pin is elsewhere (`POST /api/source/pin`),
// the tab, and the Markdown of each text, asked for one part at a time from
// `GET /api/plugin/github/pull-markdown` and kept only for the record it was rendered
// from. `mountPullPage` is the browser glue: real fetch, timers, and paint.
// tests/dom/github-pull-page-session.js runs the same functions from the command line.
//
// All text is the pull request's own and untrusted. Paint writes it with textContent;
// only KPress's sanitized Markdown HTML is parsed, and it is made inert twice, by the
// hook on the server (pull_html.py) and by `neutralizeFragment` in an inert template
// before insertion: nothing in it loads, embeds, restyles, or names an element -- no
// stylesheet, style, image, media, frame, form, SVG use, `id`, or `name` -- an image
// becomes a link to it, and a link is made absolute against the pull request's
// github.com page, kept only for http(s), and opened in a new tab with
// rel="noopener noreferrer".

// The same intervals as the freshness row (static/source-freshness.js), measured there:
// one second while a refresh runs makes its end visible promptly, and thirty seconds
// otherwise bounds how late a page learns of a refresh another tab started.
export const FAST_POLL_MS = 1000;
export const SLOW_POLL_MS = 30000;
// Markdown renders asked for at once. A render is one bounded body through KPress:
// 4 to 7 ms warm for a short comment (KPress 0.3.5, measured 2026-09-24 in-process on a
// loaded development machine), and a text scrolls into view before it is asked for, so
// two keep a long conversation filling in without queueing ahead of the page's polls.
export const MARKDOWN_CONCURRENCY = 2;

const PULL_ROUTE = "/api/plugin/github/pull";
const REFRESH_ROUTE = "/api/plugin/github/pull-refresh";
const MARKDOWN_ROUTE = "/api/plugin/github/pull-markdown";
const PIN_ROUTE = "/api/source/pin";
export const TABS = Object.freeze(["", "files"]);

/** @type {Readonly<Record<string, string>>} */
const ABSENCE = Object.freeze({
  no_pull_request: "This server serves no pull request.",
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
 *   number: number | null,
 *   pin: string | null,
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
 *   hunk: string,
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
 *   status: "loading" | "absent" | "pending" | "current" | "stale" | "other_number" | "unavailable",
 *   recordAt: string | null,
 *   message: string | null,
 *   refreshing: boolean,
 *   canRefresh: boolean,
 *   freshness: string | null,
 *   failure: string | null,
 *   pull: null | {
 *     title: string, number: number, state: string, stateLabel: string, author: string,
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

/**
 * The tone a check's result paints with: success, failure, pending, or neutral.
 *
 * @param {string | null} result
 */
function checkTone(result) {
  if (result === "success") {
    return "success";
  }
  if (
    result === "failure" ||
    result === "error" ||
    result === "timed_out" ||
    result === "action_required" ||
    result === "startup_failure"
  ) {
    return "failure";
  }
  if (result === null || result === "pending" || result === "queued" || result === "in_progress") {
    return "pending";
  }
  return "neutral";
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

/** @param {{ref?: unknown, repository?: unknown} | undefined} side @param {string} repository */
function sideName(side, repository) {
  const ref = text(side?.ref);
  const owner = typeof side?.repository === "string" ? side.repository : null;
  if (owner === null) {
    return `${ref} (deleted fork)`;
  }
  return owner === repository ? ref : `${owner.split("/")[0]}:${ref}`;
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
      hunk: text(comment.diff_hunk),
      hunkTruncated: comment.diff_hunk_truncated === true,
    }));
}

/** @param {Record<string, any>} record */
function checks(record) {
  /** @type {CheckItem[]} */
  const items = [];
  for (const run of list(record.check_runs)) {
    const result = run.status === "completed" ? (run.conclusion ?? "neutral") : text(run.status);
    items.push({
      name: text(run.name),
      detail: typeof run.app === "string" ? run.app : null,
      tone: checkTone(result),
      label: result.replaceAll("_", " "),
      url: typeof run.details_url === "string" ? run.details_url : null,
    });
  }
  for (const status of list(record.status?.statuses)) {
    const state = text(status.state);
    items.push({
      name: text(status.context),
      detail: typeof status.description === "string" ? status.description : null,
      tone: checkTone(state),
      label: state,
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
  if (envelope.number !== null && envelope.number !== page.number) {
    model.status = "other_number";
    model.message = `This server serves pull request #${envelope.number}.`;
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
        : (ABSENCE[envelope.reason ?? ""] ?? "No data for this pull request is cached.");
    model.canRefresh =
      envelope.state === "absent" && envelope.reason !== "no_pull_request" && !envelope.refreshing;
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
  const repository = text(pull.base?.repository);
  const state = displayState(pull);
  const merge = state === "open" || state === "draft" ? text(pull.mergeable) || "unknown" : null;
  model.pull = {
    title: text(pull.title),
    number: pull.number,
    state,
    stateLabel: state[0].toUpperCase() + state.slice(1),
    author: who(pull.author),
    base: sideName(pull.base, repository),
    head: sideName(pull.head, repository),
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
  /** @type {PullEnvelope | null} */
  let envelope = null;
  /** @type {string | null} */
  let etag = null;
  let tab = TABS.includes(options.tab) ? options.tab : "";
  /** @type {unknown} */
  let timer = null;
  let polling = false;
  let disposed = false;
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
      const response = await deps.request("GET", PULL_ROUTE, { etag });
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
    if (!disposed) {
      render();
      scheduleNext();
    }
  }

  async function requestRefresh() {
    if (disposed || !model().canRefresh) {
      return;
    }
    const request = ++sent;
    try {
      const response = await deps.request("POST", REFRESH_ROUTE, { body: {} });
      const body = /** @type {{pull?: unknown, error?: unknown} | null} */ (response.body);
      if (response.status === 202 && body !== null && isEnvelope(body.pull)) {
        accept(body.pull, request);
        // The answer changed; the next poll must not be answered by a 304.
        etag = null;
        error = null;
      } else {
        const said = body !== null && typeof body.error === "string" ? body.error : null;
        error = `The refresh was refused (${said ?? `HTTP ${response.status}`}).`;
      }
    } catch {
      error = "The refresh request failed.";
    }
    if (!disposed) {
      render();
      scheduleNext();
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
        .request("GET", `${MARKDOWN_ROUTE}?part=${encodeURIComponent(part)}`, {})
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
   * Ask for one part's Markdown once per record. The glue asks when the part is on
   * screen, so a long conversation renders what a reader reaches.
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

// ── Browser glue ────────────────────────────────────────────────

/**
 * The GitPath wire of a slash-separated repository path, as `/view/` addresses a file
 * on a pinned revision: `g1-` and the unpadded base64url of each segment's UTF-8.
 *
 * @param {string} path
 */
export function gitPathWire(path) {
  return path
    .split("/")
    .filter((segment) => segment !== "")
    .map((segment) => {
      let binary = "";
      for (const byte of new TextEncoder().encode(segment)) {
        binary += String.fromCharCode(byte);
      }
      return `g1-${btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "")}`;
    })
    .join("/");
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

// Elements removed with their content and attributes removed from every element before a
// text's Markdown is inserted; kept in step with builtin_plugins/github/pull_html.py,
// which applies them first on the server. They load, embed, restyle, or submit, or they
// name an element for a script to find.
export const DROPPED_ELEMENTS = Object.freeze([
  "audio",
  "base",
  "embed",
  "form",
  "iframe",
  "image",
  "link",
  "meta",
  "noscript",
  "object",
  "script",
  "source",
  "style",
  "symbol",
  "template",
  "title",
  "track",
  "use",
  "video",
]);
export const DROPPED_ATTRIBUTES = Object.freeze([
  "action",
  "background",
  "data",
  "formaction",
  "href",
  "id",
  "lowsrc",
  "name",
  "poster",
  "rel",
  "src",
  "srcset",
  "style",
  "target",
  "xlink:href",
]);

/**
 * What an image in a text becomes: a link to it, never the image. Pure.
 *
 * @param {string | null} src
 * @param {string | null} alt
 * @param {string} base
 */
export function imageLink(src, alt, base) {
  return { href: safeLink(src, base), text: (alt ?? "").trim() || "image" };
}

/**
 * Make parsed Markdown inert before it is inserted: drop what loads or names itself,
 * turn images into links, and keep a link only for http(s), opening in a new tab with
 * no opener or referrer. *root* is a template's content, where nothing has loaded.
 *
 * @param {ParentNode} root
 * @param {Pick<Document, "createElement">} doc
 * @param {string} base The pull request's github.com page, for relative links.
 */
export function neutralizeFragment(root, doc, base) {
  for (const element of Array.from(root.querySelectorAll("*"))) {
    const tag = element.tagName.toLowerCase();
    const sprite = tag === "svg" && /display:\s*none/.test(element.getAttribute("style") ?? "");
    if (DROPPED_ELEMENTS.includes(tag) || sprite) {
      element.remove();
      continue;
    }
    if (tag === "img") {
      const image = imageLink(element.getAttribute("src"), element.getAttribute("alt"), base);
      const replacement = doc.createElement(image.href === null ? "span" : "a");
      replacement.setAttribute("class", "github-pull-image");
      if (image.href !== null) {
        replacement.setAttribute("href", image.href);
        replacement.setAttribute("target", "_blank");
        replacement.setAttribute("rel", "noopener noreferrer");
      }
      replacement.textContent = image.text;
      element.replaceWith(replacement);
      continue;
    }
    const href = tag === "a" ? safeLink(element.getAttribute("href"), base) : null;
    for (const name of element.getAttributeNames()) {
      if (DROPPED_ATTRIBUTES.includes(name) || name.startsWith("on")) {
        element.removeAttribute(name);
      }
    }
    if (href !== null) {
      element.setAttribute("href", href);
      element.setAttribute("target", "_blank");
      element.setAttribute("rel", "noopener noreferrer");
    }
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
  const openTab = typeof ctx.openTab === "function" ? ctx.openTab : () => {};
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
  /** @type {{left: string, right: string} | null} */
  let diffFor = null;
  /** @type {{dispose?: () => void} | null} */
  let diffHandle = null;
  /** @type {HTMLElement | null} */
  let diffHost = null;
  const observer =
    typeof IntersectionObserver === "function"
      ? new IntersectionObserver((entries) => {
          for (const entry of entries) {
            const part = entry.isIntersecting ? entry.target.getAttribute("data-part") : null;
            if (part !== null) {
              observer?.unobserve(entry.target);
              controller.requestMarkdown(part);
            }
          }
        })
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
    const element = texts.get(part);
    const plain = element?.querySelector(":scope > .github-pull-plain");
    if (!element || !plain) {
      return;
    }
    const assets = rendered.assets;
    if (assets && typeof assets === "object") {
      void mb.loadKpressAssets(assets).catch(() => {});
    }
    const holder = h("div", { class: "github-pull-markdown metabrowser-kpress-host" });
    // KPress's Markdown HTML, sanitized on the server and hardened there by the hook;
    // GitHub's own body_html is never used. A template's content is inert -- nothing in
    // it loads or runs -- so the same rules apply again before any of it is inserted.
    const template = document.createElement("template");
    template.innerHTML = String(rendered.html);
    neutralizeFragment(template.content, document, shown?.pull?.htmlUrl ?? "");
    holder.replaceChildren(template.content);
    plain.replaceWith(holder);
  }

  /** @param {string} path @param {number | null} line */
  function fileLink(path, line) {
    if (mb.sourceKind() !== "git_revision" || path === "") {
      return h("code", {}, [path]);
    }
    const target = { path: gitPathWire(path), ...(line === null ? {} : { fragment: `L${line}` }) };
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
            h("strong", {}, [pull.author]),
            ` wants to merge into `,
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
        const selected = model.tab === id;
        const button = h(
          "a",
          {
            href: `/pull/${model.number}${id ? `/${id}` : ""}`,
            role: "tab",
            class: "github-pull-tab",
            "aria-selected": String(selected),
          },
          [label],
        );
        button.addEventListener("click", (event) => {
          if (!isPlainClick(event)) {
            return;
          }
          event.preventDefault();
          openTab(id);
        });
        tabs.append(button);
      }
      children.push(tabs);
    }
    header.replaceChildren(...children.filter((child) => child !== null));
    live.textContent = [model.message, model.failure].filter(Boolean).join(" ");
  }

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
        if (!comment.reply && comment.hunk !== "") {
          card.append(h("pre", { class: "github-pull-hunk" }, [comment.hunk]));
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
  return Object.freeze({
    setTab: controller.setTab,
    dispose() {
      listening.abort();
      observer?.disconnect();
      controller.dispose();
      disposeDiff();
    },
  });
}
