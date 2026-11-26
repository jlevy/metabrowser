// Each open pull request's readiness where a row names it (mb-3n21): the verdict's glyph in its
// tone (pull-readiness.js, `readinessIcon`) in the Pulls column's readiness column, between
// the row's change line and its age, and on a stack's member rows, in the stack menu and on
// the stack's own page (stack-member-row.js). The server judges it: `GET pull-statuses`
// (pull_statuses_route.py) answers each pull request's kept status and the verdict on it, and
// a row draws the verdict, the tone, and the label that answer gives, nothing of its own.
//
// It is read as a row's change line is (row-lines.js), by a lane of the same shape:
//
// - Only for the rows a surface draws, its rows in view and the window's overscan, in one
//   request for up to `MAX_STATUS_NUMBERS` of them, when the browser is idle and once no
//   comparison is being read, so a page's own read goes first (`keep.quiet`); in the Pulls
//   tab, the rows its window draws once measured (`settle`). A read is the cache alone: no
//   GitHub call, no Git, and no fetch. The statuses are the Pulls tab's scan's, which the
//   list's own ask starts (`POST pulls-refresh`, pull_status_scan.py), or a pull request page's
//   read.
// - A row's answer holds until something says it changed: the row's head or its state, as the
//   list of pull requests says them, moves (`want`); the list's ask answers that the scan of
//   every open pull request's status started, or that one it said was running has ended
//   (`scanned`), as does a read that says no scan runs any more; or, on a surface no ask
//   reaches, the stack menu as it opens and the stack's page as it polls, its answer is a
//   minute old (`refresh`). A read that failed is asked again after a minute. No timer reads
//   a row again.
// - Which answer is each row's is kept for the document (`documentReadiness`), so a row drawn
//   again, scrolled back into view or in a Pulls tab mounted again, has its glyph in the paint
//   that draws it, and a stack's member rows draw what the Pulls tab read.
//
// A row with no readiness draws no glyph: a closed or merged pull request, whose state is its
// answer and which is never asked for, and one the server has no status of for the head the
// list names (`absent`, whatever its reason). A verdict is never drawn for a head it does not
// describe, so a row whose head moved draws none until the server judges the new one.
//
// It loads with the plugin's module graph, as row-lines.js does: the Pulls tab, the pull
// request page, and the stack's page that draw it import it statically, and it is a few
// kilobytes of code that holds no glyph of its own.

import { createBoundedIndex } from "./change-lines.js";
import { documentComparisons } from "./comparison-prefetch.js";
import { VERDICT_GLYPHS } from "./pull-readiness.js";

export const PULL_STATUSES_ROUTE = "/api/plugin/github/pull-statuses";
// The rows one read names, the server's MAX_STATUS_NUMBERS (pull_catalog.py): more than a
// Pulls window mounts, as the change lines' read is (row-lines.js, `MAX_SUMMARY_NUMBERS`).
export const MAX_STATUS_NUMBERS = 100;
// A read that failed, a refusal or a broken connection rather than an answer, is asked again
// after a minute, the pull routes' own freshness window (`FRESHNESS_WINDOW_S`), as a change
// line's is (row-lines.js, `ROW_LINE_RETRY_MS`); and a surface that no ask of the list's
// reaches reads a row again at most that often (`refresh`). A read is one cache transaction
// of at most `MAX_STATUS_NUMBERS` rows by primary key (pull_statuses_route.py).
export const ROW_READINESS_RETRY_MS = 60_000;
// The rows whose answer the document remembers, oldest out first: ten windows of rows, as the
// change lines' index holds (row-lines.js, `REMEMBERED_ROWS`). An entry is a verdict, a tone,
// a label, and two heads, smaller than a change line's.
const REMEMBERED_ROWS = 1024;
// The recent outcomes a snapshot reports.
const RECENT = 8;
// The states the server judges; a closed or merged pull request has no readiness.
const JUDGED = new Set(["open", "draft"]);
const TONES = new Set(["success", "attention", "danger"]);

/**
 * @typedef {import("./pull-readiness.js").ShownReadiness} ShownReadiness
 * @typedef {import("./pull-state.js").PullState} PullState
 *
 * A row as a surface draws it: its number, and its head and its state as the list of pull
 * requests last said them, or null where the surface does not know them, as a stack menu
 * does not know a member's head.
 * @typedef {{number: number, head: string | null, state: PullState | null}} ReadinessRow
 *
 * What the document remembers of a row: the head and the state it was asked with, the head
 * the answer judged, its readiness, the scan it was read after (`epoch`), whether it is to
 * be read again, and when it was read or failed.
 * @typedef {{
 *   askedHead: string | null,
 *   askedState: PullState | null,
 *   head: string | null,
 *   readiness: ShownReadiness | null,
 *   epoch: number,
 *   due: boolean,
 *   failedAt: number | null,
 *   at: number,
 * }} ReadinessOutcome
 */

/**
 * What a row draws of one row of the server's answer: the verdict, its tone, and its label,
 * or null where the answer has no readiness or one this build does not draw. Pure.
 *
 * @param {unknown} value
 * @returns {ShownReadiness | null}
 */
export function shownReadiness(value) {
  if (value === null || typeof value !== "object") {
    return null;
  }
  const row = /** @type {Record<string, unknown>} */ (value);
  if (row.state !== "status" || row.readiness === null || typeof row.readiness !== "object") {
    return null;
  }
  const readiness = /** @type {Record<string, unknown>} */ (row.readiness);
  const { verdict, tone, label } = readiness;
  if (
    typeof verdict !== "string" ||
    !Object.hasOwn(VERDICT_GLYPHS, verdict) ||
    typeof tone !== "string" ||
    !TONES.has(tone) ||
    typeof label !== "string" ||
    label === ""
  ) {
    return null;
  }
  return /** @type {ShownReadiness} */ ({ verdict, tone, label });
}

/** @param {unknown} value @returns {value is {number: number, state: "status" | "absent", head: string | null}} */
export function isStatusRow(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const row = /** @type {Record<string, unknown>} */ (value);
  return (
    Number.isInteger(row.number) &&
    (row.state === "status" || row.state === "absent") &&
    (row.head === null || typeof row.head === "string")
  );
}

/** A row as the document remembers its readiness: its repository and its number.
 * @param {string | null} source @param {number} number
 */
export const readinessKey = (source, number) => `${source ?? ""}#${number}`;

/**
 * The document's memory of each row's readiness, by `readinessKey`, oldest out first, and,
 * for each repository, how many scans have ended or begun since the document first read one
 * of its rows (`epoch`): an answer read before the latest holds no longer.
 */
export function createReadinessIndex() {
  /** @type {import("./change-lines.js").BoundedIndex<ReadinessOutcome>} */
  const entries = createBoundedIndex(REMEMBERED_ROWS);
  /** @type {Map<string, number>} */
  const epochs = new Map();
  let advanced = 0;
  return Object.freeze({
    get: entries.get,
    set: entries.set,
    /** @param {string | null} source */
    epoch: (source) => epochs.get(source ?? "") ?? 0,
    /** Every answer of *source*'s rows is to be read again. @param {string | null} source */
    advance(source) {
      const key = source ?? "";
      // One count for every repository, so an epoch is never given twice, even to a
      // repository forgotten below and read again.
      advanced += 1;
      epochs.delete(key);
      epochs.set(key, advanced);
      // A server lists one repository, and a checkout whose origin changes another.
      if (epochs.size > 8) {
        epochs.delete(/** @type {string} */ (epochs.keys().next().value));
      }
    },
    clear() {
      entries.clear();
      epochs.clear();
    },
  });
}

/** The document's index, which every surface mounted in it shares. */
export const documentReadiness = createReadinessIndex();

/**
 * A lane for one surface's rows' readiness.
 *
 * @param {{
 *   keep?: {quiet(): Promise<void>},
 *   index?: ReturnType<typeof createReadinessIndex>,
 *   read(numbers: number[], signal: AbortSignal): Promise<{status: number, body: unknown}>,
 *   schedule(callback: () => void): unknown,
 *   cancel(handle: unknown): void,
 *   settle?: () => void,
 *   isVisible(): boolean,
 *   now(): number,
 *   changed(numbers: number[] | null): void,
 * }} deps `changed` repaints the rows named, or every row for null. `settle` brings the
 *   rows drawn up to date, asking `want` again if they changed, before a read names them.
 */
export function createRowReadiness(deps) {
  const keep = deps.keep ?? documentComparisons;
  const index = deps.index ?? documentReadiness;
  /** @type {string | null} */
  let source = null;
  /** The rows the surface draws, in its order, as last asked. @type {ReadinessRow[]} */
  let drawn = [];
  /** @type {unknown} */
  let handle = null;
  /** @type {{numbers: number[], controller: AbortController} | null} */
  let running = null;
  /** Whether the last word of the scan, an ask's or a read's, was that it runs. */
  let scanning = false;
  /** A refusal of the server's that holds for every row: it serves no GitHub repository. */
  let refusedAll = false;
  /** @type {string[]} */
  const recent = [];
  let disposed = false;

  /** @param {string} outcome */
  function note(outcome) {
    recent.push(outcome);
    if (recent.length > RECENT) {
      recent.shift();
    }
  }

  /** Whether *row* is one the server can judge: an open or draft pull request, or one whose
   * state the surface does not know. @param {ReadinessRow} row */
  const judged = (row) => row.state === null || JUDGED.has(row.state);

  /**
   * Whether *row*'s last answer still holds: read for its head and its state, where the
   * surface knows them, after the latest scan, with no word since that it changed, and not a
   * failure a minute old. A row that does not know its head or its state takes an answer read
   * for any, so two surfaces that draw one pull request do not read it in turn.
   *
   * @param {ReadinessRow} row
   */
  function settled(row) {
    const seen = index.get(readinessKey(source, row.number));
    if (
      seen === undefined ||
      seen.due ||
      seen.epoch !== index.epoch(source) ||
      (row.head !== null && seen.askedHead !== row.head) ||
      (row.state !== null && seen.askedState !== row.state)
    ) {
      return false;
    }
    return seen.failedAt === null || deps.now() - seen.at < ROW_READINESS_RETRY_MS;
  }

  /** The rows drawn whose readiness is to be read, in the surface's order, at most one
   * read's worth. */
  function wanted() {
    if (disposed || refusedAll) {
      return [];
    }
    const queued = running === null ? [] : running.numbers;
    return drawn
      .filter((row) => judged(row) && !queued.includes(row.number) && !settled(row))
      .slice(0, MAX_STATUS_NUMBERS);
  }

  function next() {
    if (disposed || running !== null || handle !== null || !deps.isVisible()) {
      return;
    }
    if (wanted().length === 0) {
      return;
    }
    handle = deps.schedule(() => {
      // The rows drawn as their window stands once measured, as the change lines' read names
      // them (row-lines.js): one read names every row drawn.
      deps.settle?.();
      handle = null;
      void run();
    });
  }

  /**
   * Keep each of *numbers*' outcome: its answer's readiness, or, where the read failed, the
   * readiness it had, asked again after a minute.
   *
   * @param {string | null} asked
   * @param {ReadinessRow[]} rows
   * @param {Map<number, unknown> | null} found The answer's rows by number, null for a failure.
   */
  function keepOutcomes(asked, rows, found) {
    const at = deps.now();
    const epoch = index.epoch(asked);
    for (const row of rows) {
      const key = readinessKey(asked, row.number);
      const had = index.get(key);
      const answer = found?.get(row.number);
      if (answer === undefined) {
        index.set(key, {
          askedHead: row.head,
          askedState: row.state,
          head: had?.head ?? null,
          readiness: had?.readiness ?? null,
          epoch,
          due: false,
          failedAt: at,
          at,
        });
        continue;
      }
      index.set(key, {
        askedHead: row.head,
        askedState: row.state,
        head: isStatusRow(answer) ? answer.head : null,
        readiness: shownReadiness(answer),
        epoch,
        due: false,
        failedAt: null,
        at,
      });
    }
  }

  async function run() {
    const rows = wanted();
    if (disposed || !deps.isVisible() || rows.length === 0) {
      return;
    }
    const numbers = rows.map((row) => row.number);
    const asked = source;
    const controller = new AbortController();
    running = { numbers, controller };
    try {
      // Behind the reader: a comparison a page is reading goes first.
      await keep.quiet();
      if (controller.signal.aborted) {
        return;
      }
      const answer = await deps.read(numbers, controller.signal);
      if (controller.signal.aborted || asked !== source) {
        return;
      }
      const body = /** @type {{source?: unknown, scanning?: unknown, rows?: unknown}} */ (
        answer.body
      );
      if (answer.status === 200 && body?.source === null && Array.isArray(body.rows)) {
        // No GitHub repository: no row of this server has a readiness.
        refusedAll = true;
        note("not github");
        deps.changed(null);
        return;
      }
      /** @type {Map<number, unknown>} */
      const found = new Map();
      if (answer.status === 200 && Array.isArray(body?.rows)) {
        for (const row of body.rows) {
          if (isStatusRow(row) && numbers.includes(row.number)) {
            found.set(row.number, row);
          }
        }
      }
      if (found.size > 0 && typeof body?.scanning === "boolean") {
        // A read that finds the scan over, one this lane last heard was running, holds for
        // its own rows and says every other row's answer is older than the scan's end.
        if (scanning && !body.scanning) {
          index.advance(asked);
        }
        scanning = body.scanning;
      }
      keepOutcomes(asked, rows, found.size === 0 ? null : found);
      const judgedRows = [...found.values()].filter((row) => shownReadiness(row) !== null);
      note(
        found.size === numbers.length
          ? `read ${numbers.length}: ${judgedRows.length} judged${scanning ? ", scanning" : ""}`
          : `failed ${answer.status}`,
      );
      deps.changed(numbers);
    } catch {
      if (controller.signal.aborted) {
        note("cancelled");
      } else {
        keepOutcomes(asked, rows, null);
        note("failed");
        deps.changed(numbers);
      }
    } finally {
      if (running?.controller === controller) {
        running = null;
      }
      next();
    }
  }

  /** @param {ReadinessRow[]} rows @param {string | null} rowsSource */
  function want(rows, rowsSource) {
    if (disposed) {
      return;
    }
    if (rowsSource !== source) {
      source = rowsSource;
      refusedAll = false;
      scanning = false;
    }
    drawn = rows;
    if (wanted().length === 0 && handle !== null) {
      deps.cancel(handle);
      handle = null;
    }
    next();
  }

  return Object.freeze({
    /**
     * What *row* draws now: the verdict its last answer gave, kept while a newer answer is
     * read, or null for a closed or merged pull request, for one with no answer yet or an
     * answer with no readiness, and for one whose head the answer did not judge.
     *
     * @param {ReadinessRow} row
     * @returns {ShownReadiness | null}
     */
    readiness(row) {
      if (disposed || refusedAll || !judged(row)) {
        return null;
      }
      const seen = index.get(readinessKey(source, row.number));
      if (seen === undefined || (row.head !== null && seen.head !== row.head)) {
        return null;
      }
      return seen.readiness;
    },
    /**
     * The rows the surface draws, in its order, of *rowsSource*'s list. An ask replaces the
     * last; the read on its way goes on. An empty ask, as a hidden panel's, reads nothing more.
     */
    want,
    /**
     * As `want`, for a surface no ask of the list's reaches: each of *rows* whose answer is a
     * minute old is read again (`ROW_READINESS_RETRY_MS`).
     *
     * @param {ReadinessRow[]} rows
     * @param {string | null} rowsSource
     */
    refresh(rows, rowsSource) {
      if (disposed) {
        return;
      }
      for (const row of rows) {
        const key = readinessKey(rowsSource, row.number);
        const seen = index.get(key);
        if (seen !== undefined && !seen.due && deps.now() - seen.at >= ROW_READINESS_RETRY_MS) {
          index.set(key, { ...seen, due: true });
        }
      }
      want(rows, rowsSource);
    },
    /**
     * What the list's ask said of the scan of every open pull request's status
     * (`status_scan` in `POST pulls-refresh`'s answer): `started`, or `joined` where this lane
     * had not heard it run, and `not_due` where it had, so the scan has ended since. Each
     * says the statuses kept changed, and every row's answer is read again as it is drawn.
     *
     * @param {unknown} scan
     */
    scanned(scan) {
      if (disposed) {
        return;
      }
      const began = scan === "started" || (scan === "joined" && !scanning);
      const ended = scan === "not_due" && scanning;
      if (scan === "started" || scan === "joined") {
        scanning = true;
      } else if (scan === "not_due") {
        scanning = false;
      }
      if (began || ended) {
        note(began ? "scan started" : "scan ended");
        index.advance(source);
        next();
      }
    },
    dispose() {
      disposed = true;
      drawn = [];
      if (handle !== null) {
        deps.cancel(handle);
        handle = null;
      }
      running?.controller.abort();
      running = null;
    },
    snapshot: () => ({
      wanted: wanted().map((row) => row.number),
      running: running?.numbers ?? null,
      scanning,
      refusedAll,
      recent: [...recent],
    }),
  });
}
