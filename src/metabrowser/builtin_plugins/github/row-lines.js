// A pull request's brief change line, at the end of its row's run in the Pulls column
// (mb-d0a3, mb-pw8t), after its number and a dot: its line totals alone, "+1,234 −567", with
// no file total and no file statuses (mb-lqkb), the chevron for its changed files after it.
//
// What it says is what the row's own list of changed files sums to, the list its chevron
// discloses, so the line and the tree under it agree: the server sums the cached list
// (`GET pull-files-summary`, pull_files_summary.py), how many files have each status and its
// line totals. The line is the shell's one component for a change set said in brief
// (docs/design-system.md, "Brief Change Line"), built and painted through the SDK,
// `metabrowser.changeLine` and `metabrowser.changeLineNodes`; nothing here paints its parts.
//
// When it is read, and what it costs:
//
// - Only for the rows the list draws, its rows in view and the window's overscan, in one
//   request for all of them, when the browser is idle and once no comparison is being read, so
//   a page's own read goes first (`keep.quiet`). The rows it names are the window's once its
//   rows are measured (`settle`), not the window first placed at estimated heights, which the
//   measures move by a row or more. A read is the cache alone: no GitHub call, no
//   Git, and no fetch. The lists themselves are the ones the Pulls tab already has read, the
//   changed files its prefetch names for the rows in view and a reader's own expansions, so a
//   row's line asks GitHub for nothing.
// - A row's answer holds until something says its list changed: the row's head commit, from
//   the list of pull requests, moves; the prefetch lane reports it listed the row's files
//   (`listed`); or the row's own tree reads a list of another refresh (`heard`). No timer reads
//   a line again, so a list that does not change costs nothing more. A read that failed is
//   asked again after a minute.
// - Which answer is each row's is kept for the document, so a row drawn again, scrolled back
//   into view or in a Pulls tab mounted again, has its line in the paint that draws it.
//
// A row waits for its line in the shell's pending placeholder, after the quiet period, so
// nothing moves when the line arrives; the line's box keeps the placeholder's room at the run's
// end, which is always there, as the chevron is. A row whose list is not cached and is not being listed shows no
// line and no placeholder.

import { changeLineInput, createBoundedIndex } from "./change-lines.js";
import { documentComparisons } from "./comparison-prefetch.js";

export const PULL_FILES_SUMMARY_ROUTE = "/api/plugin/github/pull-files-summary";
// The rows one read names, the server's MAX_SUMMARY_NUMBERS: more than a Pulls window mounts.
export const MAX_SUMMARY_NUMBERS = 100;
// A read that failed, a refusal of the request or a broken connection rather than an answer,
// is asked again after a minute, the pull routes' own freshness window (`FRESHNESS_WINDOW_S`),
// so a failure that lasts costs one read a minute at most. So is a row whose list was being
// listed when it was asked and whose listing no report has ended.
export const ROW_LINE_RETRY_MS = 60_000;
// The rows whose answer the document remembers, oldest out first: ten windows of rows.
// Measured 2026-11-16 in Node 24 with `--expose-gc`, 1,024 of them, each a listed
// answer of four statuses with its head and generation, held 1.16 MB of heap, 1.1 KB each.
const REMEMBERED_ROWS = 1024;
// The recent outcomes a snapshot reports.
const RECENT = 8;

/**
 * One pull request's changed files, summed, as `GET pull-files-summary` answers it
 * (pull_files_summary.py, `FilesSummaryWire`).
 *
 * @typedef {{
 *   number: number,
 *   state: "listed" | "absent",
 *   reason: string | null,
 *   listing: boolean,
 *   listed_from: string | null,
 *   generation: string | null,
 *   head: string | null,
 *   files: number | null,
 *   additions: number | null,
 *   deletions: number | null,
 *   exact: boolean,
 *   statuses: {status: string, count: number}[],
 * }} FilesSummary
 *
 * A row as the lane reads it: its number and its head commit as the list of pull requests
 * last said it.
 * @typedef {{number: number, head: string | null}} LineRow
 *
 * What a row's lines show now: its line, its pending placeholder, or nothing.
 * @typedef {{phase: "shown", summary: FilesSummary} | {phase: "waiting"} | {phase: "none"}} RowLineState
 *
 * What the document remembers of a row: the head it was read for, its last listed answer,
 * the refresh its last answer was of (`generation`, a list summed or one too large to sum),
 * whether that holds, and whether a list was being listed.
 * @typedef {{
 *   head: string | null,
 *   generation: string | null,
 *   summary: FilesSummary | null,
 *   due: boolean,
 *   listing: boolean,
 *   failedAt: number | null,
 *   at: number,
 * }} RowLineOutcome
 */

/** @param {unknown} value @returns {value is FilesSummary} */
export function isFilesSummary(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const body = /** @type {Record<string, unknown>} */ (value);
  const count = (/** @type {unknown} */ part) =>
    part === null || (typeof part === "number" && Number.isInteger(part) && part >= 0);
  return (
    (body.state === "listed" || body.state === "absent") &&
    typeof body.number === "number" &&
    typeof body.listing === "boolean" &&
    typeof body.exact === "boolean" &&
    Array.isArray(body.statuses) &&
    body.statuses.every(
      (entry) =>
        entry !== null &&
        typeof entry === "object" &&
        typeof entry.status === "string" &&
        Number.isInteger(entry.count) &&
        entry.count >= 0,
    ) &&
    count(body.additions) &&
    count(body.deletions) &&
    (body.head === null || typeof body.head === "string") &&
    (body.generation === null || typeof body.generation === "string")
  );
}

/**
 * The change line's input from a row's summary, built as a stack's is
 * (change-lines.js), so a stack of one pull request draws the line its row draws.
 *
 * @param {FilesSummary} change
 * @param {((statuses: Iterable<string>) => MetabrowserChangeLineInput["statuses"]) | null} breakdown
 * @returns {MetabrowserChangeLineInput}
 */
export function rowLineInput(change, breakdown) {
  return changeLineInput(change, breakdown);
}

/**
 * The change line's accessible name, which describes its row: what it is, and the line in
 * words once it is shown, as a stack's Whole stack row says its line after its words
 * (`wholeStackHint`).
 *
 * @param {string | null} words The line's `label`, or null while there is none.
 */
export function rowLineHint(words) {
  return words === null ? "Changed files" : `Changed files: ${words}`;
}

/** A row as the document remembers its line: its repository and its number.
 * @param {string | null} source @param {number} number
 */
export const rowLineKey = (source, number) => `${source ?? ""}#${number}`;

/**
 * The document's memory of each row's line, by `rowLineKey`, oldest out first.
 *
 * @returns {import("./change-lines.js").BoundedIndex<RowLineOutcome>}
 */
export function createRowLineIndex() {
  return createBoundedIndex(REMEMBERED_ROWS);
}

/** The document's index, which every Pulls tab mounted in it shares. */
export const documentRowLines = createRowLineIndex();

/**
 * The Pulls tab's lane for its rows' change lines.
 *
 * @param {{
 *   keep?: {quiet(): Promise<void>},
 *   index?: ReturnType<typeof createRowLineIndex>,
 *   read(numbers: number[], signal: AbortSignal): Promise<{status: number, body: unknown}>,
 *   schedule(callback: () => void): unknown,
 *   cancel(handle: unknown): void,
 *   settle(): void,
 *   isVisible(): boolean,
 *   now(): number,
 *   changed(numbers: number[] | null): void,
 * }} deps `changed` repaints the rows named, or every row for null. `settle` brings the
 *   rows drawn up to date, asking `want` again if they changed, before a read names them.
 */
export function createRowLines(deps) {
  const keep = deps.keep ?? documentComparisons;
  const index = deps.index ?? documentRowLines;
  /** @type {string | null} */
  let source = null;
  /** The rows the list draws, in its order, as last asked. @type {LineRow[]} */
  let drawn = [];
  /** @type {unknown} */
  let handle = null;
  /** @type {{numbers: number[], controller: AbortController} | null} */
  let running = null;
  /**
   * Rows the prefetch lane was asked to list that have no line yet, and since when: each waits
   * for it, a minute at most (`ROW_LINE_RETRY_MS`), as a listing an answer reported does, so
   * a row whose lane the panel stopped following before it said it was done is read again.
   */
  /** @type {Map<number, number>} */
  const awaiting = new Map();
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

  /** Whether *row*'s last answer still holds: for its head, with no word since that its list
   * changed, and not a failure or a listing a minute old.
   * @param {LineRow} row
   */
  function settled(row) {
    const seen = index.get(rowLineKey(source, row.number));
    if (seen === undefined || seen.head !== row.head || seen.due) {
      return false;
    }
    if (seen.failedAt !== null || seen.listing) {
      return deps.now() - seen.at < ROW_LINE_RETRY_MS;
    }
    return true;
  }

  /** End the waits for the lane that have lasted a minute: those rows are read again. */
  function expireAwaiting() {
    const now = deps.now();
    for (const [number, since] of [...awaiting]) {
      if (now - since >= ROW_LINE_RETRY_MS) {
        awaiting.delete(number);
        unsettle([number]);
      }
    }
  }

  /** The rows drawn whose line is to be read, in the list's order, at most one read's worth. */
  function wanted() {
    if (disposed || refusedAll) {
      return [];
    }
    expireAwaiting();
    const queued = running === null ? [] : running.numbers;
    return drawn
      .filter((row) => !queued.includes(row.number) && !settled(row))
      .slice(0, MAX_SUMMARY_NUMBERS);
  }

  function next() {
    if (disposed || running !== null || handle !== null || !deps.isVisible()) {
      return;
    }
    if (wanted().length === 0) {
      return;
    }
    handle = deps.schedule(() => {
      // The rows drawn as their window stands once measured, so one read names every row
      // drawn: the browser can be idle between the frame that measured the rows of a window
      // placed at `ROW_ESTIMATE_PX` and the one that draws it again at their heights, and the
      // rows that frame adds would wait for a second read (mb-hb4a). While the handle is
      // held, the `want` this asks for schedules nothing more.
      deps.settle();
      handle = null;
      void run();
    });
  }

  async function run() {
    const rows = wanted();
    if (disposed || !deps.isVisible() || rows.length === 0) {
      return;
    }
    const numbers = rows.map((row) => row.number);
    const heads = new Map(rows.map((row) => [row.number, row.head]));
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
      const at = deps.now();
      const body = /** @type {{source?: unknown, rows?: unknown}} */ (answer.body);
      if (answer.status === 200 && body?.source === null && Array.isArray(body.rows)) {
        // No GitHub repository: no row of this server has a line.
        refusedAll = true;
        note("not github");
        deps.changed(null);
        return;
      }
      /** @type {Map<number, FilesSummary>} */
      const found = new Map();
      if (answer.status === 200 && Array.isArray(body?.rows)) {
        for (const row of body.rows) {
          if (isFilesSummary(row) && heads.has(row.number)) {
            found.set(row.number, row);
          }
        }
      }
      for (const number of numbers) {
        const key = rowLineKey(asked, number);
        const had = index.get(key);
        const summary = found.get(number);
        if (summary === undefined) {
          // A failure keeps the line the row had, and is asked again after a minute.
          index.set(key, {
            head: heads.get(number) ?? null,
            generation: had?.generation ?? null,
            summary: had?.summary ?? null,
            due: false,
            listing: false,
            failedAt: at,
            at,
          });
          continue;
        }
        // A row waits for the lane's listing until its list is here or the lane says it is
        // done: an answer read before the lane took the ask says nothing of it.
        if (summary.state === "listed") {
          awaiting.delete(number);
        }
        // A list the request had no room to read is asked for in the next, and says nothing
        // of the list: the line the row had stays, as it does over a failure.
        const deferred = summary.reason === "deferred";
        index.set(key, {
          head: heads.get(number) ?? null,
          generation: deferred ? (had?.generation ?? null) : summary.generation,
          summary: summary.state === "listed" ? summary : deferred ? (had?.summary ?? null) : null,
          due: deferred,
          listing: summary.state !== "listed" && summary.listing,
          failedAt: null,
          at,
        });
      }
      note(
        found.size === numbers.length
          ? `read ${numbers.length}: ${[...found.values()].filter((row) => row.state === "listed").length} listed`
          : `failed ${answer.status}`,
      );
      deps.changed(numbers);
    } catch {
      if (controller.signal.aborted) {
        note("cancelled");
      } else {
        const at = deps.now();
        for (const number of numbers) {
          const key = rowLineKey(asked, number);
          const had = index.get(key);
          index.set(key, {
            head: heads.get(number) ?? null,
            generation: had?.generation ?? null,
            summary: had?.summary ?? null,
            due: false,
            listing: false,
            failedAt: at,
            at,
          });
        }
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

  /** Mark *numbers*' answers as no longer holding, so a row drawn reads its line again.
   * @param {Iterable<number>} numbers */
  function unsettle(numbers) {
    for (const number of numbers) {
      const key = rowLineKey(source, number);
      const seen = index.get(key);
      if (seen !== undefined && !seen.due) {
        index.set(key, { ...seen, due: true });
      }
    }
  }

  return Object.freeze({
    /**
     * What *row*'s lines show now: its kept line, shown while a newer answer is read,
     * until one replaces it; the placeholder while a read of it is coming or its list is being
     * listed; or nothing, when its list is not cached and nothing lists it.
     *
     * @param {LineRow} row
     * @returns {RowLineState}
     */
    line(row) {
      const seen = index.get(rowLineKey(source, row.number));
      if (seen?.summary != null) {
        return { phase: "shown", summary: seen.summary };
      }
      if (disposed || refusedAll) {
        return { phase: "none" };
      }
      const waitingForLane =
        awaiting.has(row.number) &&
        deps.now() - (awaiting.get(row.number) ?? 0) < ROW_LINE_RETRY_MS;
      if (waitingForLane || seen?.listing === true || !settled(row)) {
        return seen?.failedAt != null && settled(row) ? { phase: "none" } : { phase: "waiting" };
      }
      return { phase: "none" };
    },
    /**
     * The rows the list draws, in its order, of *rowsSource*'s list. An ask replaces the last;
     * the read on its way goes on. An empty ask, as a panel hidden asks, reads nothing more.
     *
     * @param {LineRow[]} rows
     * @param {string | null} rowsSource
     */
    want(rows, rowsSource) {
      if (disposed) {
        return;
      }
      if (rowsSource !== source) {
        source = rowsSource;
        awaiting.clear();
        refusedAll = false;
      }
      drawn = rows;
      if (wanted().length === 0 && handle !== null) {
        deps.cancel(handle);
        handle = null;
      }
      next();
    },
    /**
     * The prefetch lane was asked to list *numbers*' changed files, and took the ask: a row
     * among them with no line waits for its list in the placeholder until a report says the
     * lane listed it (`listed`).
     *
     * @param {number[]} numbers
     */
    listing(numbers) {
      if (disposed || refusedAll) {
        return;
      }
      /** @type {number[]} */
      const waiting = [];
      for (const number of numbers) {
        if (index.get(rowLineKey(source, number))?.summary == null && !awaiting.has(number)) {
          awaiting.set(number, deps.now());
          waiting.push(number);
        }
      }
      if (waiting.length > 0) {
        deps.changed(waiting);
      }
    },
    /**
     * The prefetch lane listed *numbers*' changed files, or went idle (*idle*): their lines are
     * read again when drawn. Idle, every row still waiting for the lane is read again, so none
     * waits for a listing that will not come. A row whose answer said another's refresh was
     * listing it is read again when its tree reads the list (`heard`), or a minute on.
     *
     * @param {number[]} numbers
     * @param {{idle?: boolean}} [how]
     */
    listed(numbers, how = {}) {
      if (disposed) {
        return;
      }
      const all = new Set(numbers);
      if (how.idle === true) {
        for (const number of awaiting.keys()) {
          all.add(number);
        }
      }
      if (all.size === 0) {
        return;
      }
      for (const number of all) {
        awaiting.delete(number);
      }
      unsettle(all);
      deps.changed([...all]);
      next();
    },
    /**
     * A row's own tree read its list, of the refresh *generation*: a row whose line is of
     * another reads it again.
     *
     * @param {number} number
     * @param {string | null} generation
     */
    heard(number, generation) {
      if (disposed || generation === null) {
        return;
      }
      const seen = index.get(rowLineKey(source, number));
      // An answer too large to sum names its list's refresh too, so a capped list's tree
      // reading its pages reads nothing more.
      if (seen !== undefined && seen.generation !== generation) {
        unsettle([number]);
        awaiting.delete(number);
        next();
      }
    },
    dispose() {
      disposed = true;
      drawn = [];
      awaiting.clear();
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
      awaiting: [...awaiting.keys()],
      refusedAll,
      recent: [...recent],
    }),
  });
}
