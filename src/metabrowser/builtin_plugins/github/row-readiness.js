// Each open pull request's readiness where a row names it (mb-3n21): the verdict's glyph in its
// tone (pull-readiness.js, `readinessIcon`) in the Pulls column's readiness column, between
// the row's change line and its age, and on a stack's member rows, in the stack menu and on
// the stack's own page (stack-member-row.js). The server judges it: `GET pull-statuses`
// (pull_statuses_route.py) answers each pull request's kept status and the verdict on it, for
// the head and the lifecycle the catalog's row names, and a row draws the verdict, the tone,
// and the label that answer gives, nothing of its own.
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
//   surface last asked them, moves (`want`); the list's ask answers that the scan of every open
//   pull request's status started (`scanned`); the ask or a read says a scan ended later than
//   any the document had heard of, by its stamp's time (`scanEnded`), however it started,
//   the list's ask, another tab's, or a look at the mirror after an ask had answered; a pull
//   request page reads a newer status of its own pull request (`heard`); or, on a surface no
//   ask reaches, the stack menu as it opens and the stack's page as it polls, its answer is a
//   minute old (`refresh`). A read that failed is asked again after a minute. No timer reads
//   a row again.
// - Which answer is each row's is kept for the document (`documentReadiness`), with nothing of
//   the surface that asked: the answer's head and lifecycle are the server's, the catalog's,
//   so every surface that draws a row, whatever head it knows it by, holds the one answer, and
//   one read settles the row for all of them. A row being read by one surface is read by no
//   other meanwhile, and each surface drawing it repaints when its answer lands or is due
//   again (`listen`). So a row drawn again, scrolled back into view or in a Pulls tab mounted
//   again, has its glyph in the paint that draws it, a stack's member rows draw what the
//   Pulls tab read, and a row is read at most once for each thing that says it changed.
//
// A row with no readiness draws no glyph: a closed or merged pull request, whose state is its
// answer and which is never asked for, and one the server has no status of for the head the
// list names (`absent`, whatever its reason). A verdict is drawn only for the head and the
// state it judged (`readinessForState`), so a row whose head moved, or whose draft was marked
// ready, draws none until the server judges the new one.
//
// It loads with the plugin's module graph, as row-lines.js does: the Pulls tab, the pull
// request page, and the stack's page that draw it import it statically, and it is a few
// kilobytes of code that holds no glyph of its own.

import { createBoundedIndex } from "./change-lines.js";
import { documentComparisons } from "./comparison-prefetch.js";
import { readinessForState, TONES, VERDICT_GLYPHS } from "./pull-readiness.js";

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
// a label, a head, a lifecycle, and a time, smaller than a change line's. A lane remembers as
// many of the heads and states it asked rows with, which say when one moves.
const REMEMBERED_ROWS = 1024;
// The repositories whose scans the document counts: a server lists one, and a checkout whose
// origin changes another.
const COUNTED_SOURCES = 8;
// The recent outcomes a snapshot reports.
const RECENT = 8;
// The states the server judges; a closed or merged pull request has no readiness.
const JUDGED = new Set(["open", "draft"]);
const STATES = new Set(["open", "draft", "merged", "closed"]);

/**
 * @typedef {import("./pull-readiness.js").ShownReadiness} ShownReadiness
 * @typedef {import("./pull-state.js").PullState} PullState
 *
 * A row as a surface draws it: its number, the head the list of pull requests names for it,
 * which is the head the server judges, and the state the surface shows; either null where the
 * surface does not know it, as a stack menu does not know a member's head.
 * @typedef {{number: number, head: string | null, state: PullState | null}} ReadinessRow
 *
 * What the document remembers of a row: the head and the lifecycle its answer judged, the
 * catalog's; its readiness; the latest time its status was observed that the document has
 * heard of, the answer's or a page's own read's since (`heard`); the scans it was read after
 * (`epoch`); whether it is to be read again; and when it was read or failed.
 * @typedef {{
 *   head: string | null,
 *   lifecycle: PullState | null,
 *   readiness: ShownReadiness | null,
 *   observedAt: string | null,
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
    !TONES.includes(/** @type {import("./pull-readiness.js").ReadinessTone} */ (tone)) ||
    typeof label !== "string" ||
    label === ""
  ) {
    return null;
  }
  return /** @type {ShownReadiness} */ ({ verdict, tone, label });
}

/**
 * Whether *value* is a row of the server's answer: its number, its state, and the head and
 * the lifecycle the catalog's row names, which the verdict judged.
 *
 * @param {unknown} value
 * @returns {value is {number: number, state: "status" | "absent", head: string | null, lifecycle: PullState | null}}
 */
export function isStatusRow(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const row = /** @type {Record<string, unknown>} */ (value);
  return (
    Number.isInteger(row.number) &&
    (row.state === "status" || row.state === "absent") &&
    (row.head === null || typeof row.head === "string") &&
    (row.lifecycle === null || (typeof row.lifecycle === "string" && STATES.has(row.lifecycle)))
  );
}

/** When the status an answer's row gives was observed, or null with none. @param {unknown} row */
function observedOf(row) {
  const status = /** @type {{status?: {observed_at?: unknown} | null}} */ (row).status;
  const at = status?.observed_at;
  return typeof at === "string" ? at : null;
}

/** The later of two observation times, either null for none; an ISO time sorts as text.
 * @param {string | null} left @param {string | null} right */
const later = (left, right) => (left === null || (right !== null && right > left) ? right : left);

/** A row as the document remembers its readiness: its repository and its number.
 * @param {string | null} source @param {number} number
 */
export const readinessKey = (source, number) => `${source ?? ""}#${number}`;

/**
 * The document's memory of each row's readiness, by `readinessKey`, oldest out first; for each
 * repository, how many scans have ended or begun since the document first read one of its rows
 * (`epoch`), an answer read before the latest holding no longer, and the latest end of a scan
 * it has heard of (`scanEnded`); which rows a lane is reading now (`claim`), which no other
 * reads meanwhile; and the lanes to tell when a row's answer lands, is due again, or is
 * released unread (`listen`).
 */
export function createReadinessIndex() {
  /** @type {import("./change-lines.js").BoundedIndex<ReadinessOutcome>} */
  const entries = createBoundedIndex(REMEMBERED_ROWS);
  /** @type {Map<string, number>} */
  const epochs = new Map();
  /** The stamp's `at` of the latest scan's end heard of, by repository; null before any.
   * @type {Map<string, string | null>} */
  const ends = new Map();
  /** The rows a lane is reading now, by `readinessKey`. @type {Set<string>} */
  const reading = new Set();
  /** @type {Set<(source: string | null, numbers: number[]) => void>} */
  const listeners = new Set();
  let advanced = 0;

  /** @template T @param {Map<string, T>} map @param {string} key @param {T} value */
  function remember(map, key, value) {
    map.delete(key);
    map.set(key, value);
    if (map.size > COUNTED_SOURCES) {
      map.delete(/** @type {string} */ (map.keys().next().value));
    }
  }

  /** Every answer of *source*'s rows is to be read again. @param {string | null} source */
  function advance(source) {
    // One count for every repository, so an epoch is never given twice, even to a
    // repository forgotten and read again.
    advanced += 1;
    remember(epochs, source ?? "", advanced);
  }

  /** Tell every lane that *numbers* of *source* changed in the index.
   * @param {string | null} source @param {number[]} numbers */
  function tell(source, numbers) {
    if (numbers.length > 0) {
      for (const listener of [...listeners]) {
        listener(source, numbers);
      }
    }
  }

  /**
   * *numbers* of *source* are to be read again, by whichever lane draws them first: something
   * says their status changed. A row no lane has read yet is read when one draws it, and one
   * already due is told of no more.
   *
   * @param {string | null} source
   * @param {number[]} numbers
   */
  function due(source, numbers) {
    /** @type {number[]} */
    const marked = [];
    for (const number of numbers) {
      const key = readinessKey(source, number);
      const seen = entries.get(key);
      if (seen !== undefined && !seen.due) {
        entries.set(key, { ...seen, due: true });
        marked.push(number);
      }
    }
    tell(source, marked);
  }

  return Object.freeze({
    get: entries.get,
    /** @param {string | null} source */
    epoch: (source) => epochs.get(source ?? "") ?? 0,
    advance,
    due,
    /**
     * That *source*'s latest scan ended at *at*, its stamp's time, or that none has (null), as
     * the list's ask or a read says it: an end later than the latest heard of says the scan's
     * statuses are newer than every answer read before, which hold no longer (`advance`),
     * however the scan started. The first word of a repository's scans is where the document
     * starts counting them. Returns whether it advanced.
     *
     * @param {string | null} source
     * @param {string | null} at
     */
    scanEnded(source, at) {
      const key = source ?? "";
      if (!ends.has(key)) {
        remember(ends, key, at);
        return false;
      }
      const known = ends.get(key) ?? null;
      if (at === null || (known !== null && at <= known)) {
        return false;
      }
      remember(ends, key, at);
      advance(source);
      return true;
    },
    /**
     * That a pull request page read *number*'s status itself, observed at *observedAt*
     * (`observed_at` of the envelope's `status`): one newer than any the document has heard of
     * is to be read again (`due`), so every row that draws it says what the page says.
     *
     * @param {string | null} source
     * @param {number} number
     * @param {string | null} observedAt
     */
    heard(source, number, observedAt) {
      const key = readinessKey(source, number);
      const seen = entries.get(key);
      if (
        seen === undefined ||
        observedAt === null ||
        (seen.observedAt !== null && observedAt <= seen.observedAt)
      ) {
        return;
      }
      entries.set(key, { ...seen, observedAt });
      due(source, [number]);
    },
    /**
     * Keep the outcomes a lane read of *source*'s rows, and tell every lane they landed.
     *
     * @param {string | null} source
     * @param {Map<number, ReadinessOutcome>} outcomes
     */
    keep(source, outcomes) {
      for (const [number, outcome] of outcomes) {
        entries.set(readinessKey(source, number), outcome);
      }
      tell(source, [...outcomes.keys()]);
    },
    /**
     * Which of *numbers* of *source* a lane may read now: those no lane is reading, each then
     * held as being read until `release`.
     *
     * @param {string | null} source
     * @param {number[]} numbers
     */
    claim(source, numbers) {
      const claimed = numbers.filter((number) => !reading.has(readinessKey(source, number)));
      for (const number of claimed) {
        reading.add(readinessKey(source, number));
      }
      return claimed;
    },
    /** @param {string | null} source @param {number} number */
    isReading: (source, number) => reading.has(readinessKey(source, number)),
    /**
     * *numbers* of *source* are read no more by the lane that claimed them; *unread*, as of a
     * read cancelled, tells every lane, so one that draws them reads them itself.
     *
     * @param {string | null} source
     * @param {number[]} numbers
     * @param {boolean} unread
     */
    release(source, numbers, unread) {
      for (const number of numbers) {
        reading.delete(readinessKey(source, number));
      }
      if (unread) {
        tell(source, numbers);
      }
    },
    /**
     * Call *listener* with a repository and its numbers whose answer landed, is due again, or
     * was released unread. Returns the call that stops it, a lane's disposal path.
     *
     * @param {(source: string | null, numbers: number[]) => void} listener
     */
    listen(listener) {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    clear() {
      entries.clear();
      epochs.clear();
      ends.clear();
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
  /** The repository of the rows last asked for. @type {string | null} */
  let source = null;
  /** The rows the surface draws, in its order, as last asked. @type {ReadinessRow[]} */
  let drawn = [];
  /**
   * The head and the state this lane last asked each row with, so a move between two asks
   * says the row changed. Its own, not the document's: two surfaces that know a row by two
   * heads each ask with their own, and neither is a move.
   * @type {import("./change-lines.js").BoundedIndex<{head: string | null, state: PullState | null}>}
   */
  let asked = createBoundedIndex(REMEMBERED_ROWS);
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
   * Whether *row*'s answer still holds: read after the latest scan, with no word since that
   * it changed, and not a failure a minute old. Nothing of the surface's own is asked of it,
   * so every surface that draws the row finds the same.
   *
   * @param {ReadinessRow} row
   */
  function settled(row) {
    const seen = index.get(readinessKey(source, row.number));
    if (seen === undefined || seen.due || seen.epoch !== index.epoch(source)) {
      return false;
    }
    return seen.failedAt === null || deps.now() - seen.at < ROW_READINESS_RETRY_MS;
  }

  /** Whether the answer the document holds judged *row*'s head and state, where the surface
   * knows them. @param {ReadinessRow} row */
  function describes(row) {
    const seen = index.get(readinessKey(source, row.number));
    return (
      seen !== undefined &&
      (row.head === null || seen.head === row.head) &&
      (row.state === null || seen.lifecycle === row.state)
    );
  }

  /** The rows drawn whose readiness is to be read, in the surface's order, at most one
   * read's worth: none another lane is reading. */
  function wanted() {
    if (disposed || refusedAll) {
      return [];
    }
    const queued = running === null ? [] : running.numbers;
    return drawn
      .filter(
        (row) =>
          judged(row) &&
          !queued.includes(row.number) &&
          !index.isReading(source, row.number) &&
          !settled(row),
      )
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

  // Another lane's answer landed, or a row was marked due or left unread: the rows this lane
  // draws among them are drawn again and, where due, read.
  const unlisten = index.listen((changedSource, numbers) => {
    if (disposed || changedSource !== source) {
      return;
    }
    const mine = drawn.filter((row) => numbers.includes(row.number)).map((row) => row.number);
    if (mine.length > 0) {
      deps.changed(mine);
      next();
    }
  });

  /**
   * Each of *rows*' outcome: its answer's head, lifecycle, and readiness, or, where the read
   * failed, what it had, asked again after a minute.
   *
   * @param {string | null} from
   * @param {ReadinessRow[]} rows
   * @param {Map<number, unknown> | null} found The answer's rows by number, null for a failure.
   */
  function outcomes(from, rows, found) {
    const at = deps.now();
    const epoch = index.epoch(from);
    /** @type {Map<number, ReadinessOutcome>} */
    const kept = new Map();
    for (const row of rows) {
      const had = index.get(readinessKey(from, row.number));
      const answer = found?.get(row.number);
      if (answer === undefined || !isStatusRow(answer)) {
        kept.set(row.number, {
          head: had?.head ?? null,
          lifecycle: had?.lifecycle ?? null,
          readiness: had?.readiness ?? null,
          observedAt: had?.observedAt ?? null,
          epoch,
          due: false,
          failedAt: at,
          at,
        });
        continue;
      }
      kept.set(row.number, {
        head: answer.head,
        lifecycle: answer.lifecycle,
        readiness: shownReadiness(answer),
        observedAt: later(had?.observedAt ?? null, observedOf(answer)),
        epoch,
        due: false,
        failedAt: null,
        at,
      });
    }
    return kept;
  }

  async function run() {
    const rows = wanted();
    if (disposed || !deps.isVisible() || rows.length === 0) {
      return;
    }
    const from = source;
    const claimed = new Set(
      index.claim(
        from,
        rows.map((row) => row.number),
      ),
    );
    const reads = rows.filter((row) => claimed.has(row.number));
    const numbers = reads.map((row) => row.number);
    if (numbers.length === 0) {
      // Another lane is reading every one; its answer is drawn here as it lands (`listen`).
      return;
    }
    const controller = new AbortController();
    running = { numbers, controller };
    let landed = false;
    try {
      // Behind the reader: a comparison a page is reading goes first.
      await keep.quiet();
      if (controller.signal.aborted) {
        return;
      }
      const answer = await deps.read(numbers, controller.signal);
      if (controller.signal.aborted || from !== source) {
        return;
      }
      const body =
        /** @type {{source?: unknown, scanning?: unknown, scan?: unknown, rows?: unknown}} */ (
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
      if (found.size > 0) {
        // A read that says a scan ended later than the document had heard of holds for its
        // own rows and says every other row's answer is older than the scan's end.
        const scan = /** @type {{at?: unknown} | null | undefined} */ (body?.scan);
        if (scan !== undefined) {
          index.scanEnded(from, typeof scan?.at === "string" ? scan.at : null);
        }
        if (typeof body?.scanning === "boolean") {
          scanning = body.scanning;
        }
      }
      const judgedRows = [...found.values()].filter((row) => shownReadiness(row) !== null);
      note(
        found.size === numbers.length
          ? `read ${numbers.length}: ${judgedRows.length} judged${scanning ? ", scanning" : ""}`
          : `failed ${answer.status}`,
      );
      landed = true;
      index.release(from, numbers, false);
      index.keep(from, outcomes(from, reads, found.size === 0 ? null : found));
    } catch {
      if (controller.signal.aborted) {
        note("cancelled");
      } else {
        note("failed");
        landed = true;
        index.release(from, numbers, false);
        index.keep(from, outcomes(from, reads, null));
      }
    } finally {
      if (!landed) {
        // Cancelled, or for another repository now: another lane that draws them reads them.
        index.release(from, numbers, true);
      }
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
      asked = createBoundedIndex(REMEMBERED_ROWS);
    }
    drawn = rows;
    // A row whose head or state moved since this lane last asked it is read again, unless the
    // answer the document holds judged the new ones already: the server may have judged them.
    /** @type {number[]} */
    const moved = [];
    for (const row of rows) {
      const key = String(row.number);
      const before = asked.get(key);
      if (before?.head !== row.head || before?.state !== row.state) {
        asked.set(key, { head: row.head, state: row.state });
        if (before !== undefined && !describes(row)) {
          moved.push(row.number);
        }
      }
    }
    if (moved.length > 0) {
      index.due(source, moved);
    }
    if (wanted().length === 0 && handle !== null) {
      deps.cancel(handle);
      handle = null;
    }
    next();
  }

  return Object.freeze({
    /**
     * What *row* of *rowsSource*'s list draws now: the verdict its last answer gave, kept
     * while a newer answer is read, where that answer judged the row's head and its state,
     * as the surface knows them; or null for a closed or merged pull request, for one with no
     * answer yet or an answer with no readiness, and for one whose head or state the answer
     * did not judge. It names its repository itself, so a surface's first paint, before it
     * has asked for any row (`want`), draws what the document already holds.
     *
     * @param {ReadinessRow} row
     * @param {string | null} rowsSource
     * @returns {ShownReadiness | null}
     */
    readiness(row, rowsSource) {
      if (disposed || (refusedAll && rowsSource === source) || !judged(row)) {
        return null;
      }
      const seen = index.get(readinessKey(rowsSource, row.number));
      if (
        seen === undefined ||
        seen.lifecycle === null ||
        (row.head !== null && seen.head !== row.head)
      ) {
        return null;
      }
      // A surface that shows no state draws the verdict on the state the server judged.
      return readinessForState(seen.readiness, seen.lifecycle, row.state ?? seen.lifecycle);
    },
    /**
     * The rows the surface draws, in its order, of *rowsSource*'s list. An ask replaces the
     * last; the read on its way goes on. An empty ask, as a hidden panel's, reads nothing more.
     */
    want,
    /**
     * *numbers* of *rowsSource*'s list are to be read again: the surface knows they changed,
     * as the stack's page does when a member's record moves to a new head.
     *
     * @param {number[]} numbers
     * @param {string | null} rowsSource
     */
    reread(numbers, rowsSource) {
      if (!disposed) {
        index.due(rowsSource, numbers);
      }
    },
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
      const old = rows
        .map((row) => row.number)
        .filter((number) => {
          const seen = index.get(readinessKey(rowsSource, number));
          return seen !== undefined && !seen.due && deps.now() - seen.at >= ROW_READINESS_RETRY_MS;
        });
      index.due(rowsSource, old);
      want(rows, rowsSource);
    },
    /**
     * What the list's ask said of the scan of every open pull request's status
     * (`status_scan` in `POST pulls-refresh`'s answer): `started`, or `joined` where this lane
     * had not heard it run, says the statuses kept are changing; and *endedAt*, its
     * `status_scan_at`, when the latest scan ended, says, where it is later than any the
     * document had heard of, that one ended since, whoever started it (`scanEnded`). Each reads
     * every row's answer again as it is drawn.
     *
     * @param {unknown} scan
     * @param {unknown} [endedAt]
     */
    scanned(scan, endedAt) {
      if (disposed) {
        return;
      }
      const began = scan === "started" || (scan === "joined" && !scanning);
      if (scan === "started" || scan === "joined") {
        scanning = true;
      } else if (scan === "not_due") {
        scanning = false;
      }
      const ended =
        (endedAt === null || typeof endedAt === "string") && index.scanEnded(source, endedAt);
      if (began && !ended) {
        index.advance(source);
      }
      if (began || ended) {
        note(ended ? "scan ended" : "scan started");
        next();
      }
    },
    dispose() {
      disposed = true;
      drawn = [];
      unlisten();
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
