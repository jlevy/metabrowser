// A native stack's brief change line in the Pulls column (mb-9ekj): its line totals alone,
// "Whole stack · +1,234 −567", with no file statuses (mb-lqkb). It is drawn on the stack's
// Whole stack row (mb-tvhs; pulls-panel.js, `paintWholeRow`), where it and the chevron after
// it are the toggle of the stack's changed files (mb-odt4, stack-files.js), and was on the
// stack's own row, its heading, which now says the stack's size and age: "heading" below is
// whichever row draws the line, and the lane reads for every stack whose own row is drawn,
// open or closed, so a stack that opens has its line in the paint that draws its Whole
// stack row.
//
// What it says is the stack's combined change: a stack is the accumulation of its pull
// requests, merged or open, so its change is theirs, each member's own changed files, the
// list its expanded row shows, accumulated bottom first, every file once with a status
// composed from what the members did to it, and every member's lines summed, which the
// server does from the cache (`GET stack-change`, pull_stack_change.py). Summing each pull
// request's own file counts would count twice a file two layers change.
// The line is the shell's one component for a change set said in brief (docs/design-system.md,
// "Brief Change Line"), built and painted through the SDK, `metabrowser.changeLine` and
// `metabrowser.changeLineNodes`; nothing here paints its parts.
//
// When it is read, and what it costs:
//
// - Only for the stacks whose rows the list draws, its rows in view and the window's overscan,
//   one at a time, each when the browser is idle, and only once no comparison is being read,
//   so a page's own read goes first (`keep.quiet`), as the comparison warmer's are.
// - Once as the list draws it: its members and each member's head as the catalog's rows report
//   it, a member the list holds no row of taken as unchanged (`sameStack`), so switching
//   filters reads nothing again. It is read again, never on a timer (review of #484, A2):
//   - when the list's rows say a member moved or the members changed;
//   - when a member's list of changed files changes, as the prefetch lane reports a list it
//     refreshed or a row's own read of its list arrives (`listed`);
//   - while its last answer named members not yet settled, a list missing, filling, or one
//     the files route would refresh (`pending`): silently, a minute on and doubling while it
//     stays so, up to `STACK_LINE_PENDING_MAX_MS` (review B of #484, B1);
//   - and a minute after a read that failed.
//   An answer that names no unsettled member holds until one of those happens.
// - Within the lines' own hourly cap (`STACK_LINES_PER_HOUR`), apart from the comparison
//   warmer's (`WARM_PER_HOUR`), so the lines never take the warms' share. A read is the stack
//   snapshot and each member's list of changed files from the cache, and each member's newest
//   known head; no GitHub call, no fetch, and no Git.
// - An answer is a few hundred bytes of JSON. It is kept in the document's comparison keep
//   under its stack and its revision (`stackChangeKey`), and which answer is each stack's is
//   kept for the document too (`documentStackLines`), so a heading drawn again, scrolled
//   back into view or in a Pulls tab mounted again, has its line in the paint that draws it,
//   with no request. A line stays shown until a newer answer replaces it: while its stack is
//   read again, and when that read fails.
// - The members a stack's answer names as unsettled are the ones the Pulls tab's prefetch
//   asks to list, after the reader's own rows (`unsettled`, pulls-panel.js), so a collapsed
//   stack's line fills in too (review B of #484, B2).
//
// A heading waits for its line in the shell's pending placeholder only while the read of its
// stack is on its way, after the quiet period, and its accessible name says the change is
// pending meanwhile. A stack whose last answer as it is drawn had no line, was still
// settling, or failed, never waits again until its members or their heads change, so its
// heading does not pulse and go blank (review of #484, A4). Nor does a heading whose read is
// queued behind another, or whose read the cap holds.

import { changeLineInput, createBoundedIndex } from "./change-lines.js";
import { createWarmBudget, documentComparisons } from "./comparison-prefetch.js";
import { stackLabel } from "./pull-stacks.js";

export const STACK_CHANGE_ROUTE = "/api/plugin/github/stack-change";

// A read that failed, a refusal of the request, a broken connection, or a refusal that holds
// for the whole server, is asked again after a minute, the pull routes' own freshness window
// (`FRESHNESS_WINDOW_S`), so a failure that lasts costs one read a minute a stack at most.
export const STACK_LINE_RETRY_MS = 60_000;
// The longest a stack whose answer names unsettled members waits to be asked again: a minute
// first, then two, four, and so on to this. A list a head's move starts refreshing lands in
// seconds, one GitHub page or one store listing, so most stacks settle at the first retry;
// one whose member is listed later, by the prefetch or a row, is read at once when it is
// (`listed`), and the doubling keeps a stack whose member never is to six reads its first
// hour and two an hour after.
export const STACK_LINE_PENDING_MAX_MS = 30 * 60_000;
// The reads the lines start in an hour, each counted as it starts; the comparison warmer
// counts its own (`WARM_PER_HOUR`). A read runs no Git: it stats each member's list and,
// when one changed since the server last accumulated them, folds them in one at a time, 6
// to 16 ms for #446's 16 cached lists and at most about 400 ms within
// `MAX_STACK_LIST_BYTES`; it then reads whether the files route takes each list as
// current, 17 ms for #446's 19 cached lists (measured 2026-11-16 at a load average of 14 to
// 38, pull_stack_change.py). The list draws every one of this repository's 19 stacks, so a
// first visit reads 19, and an hour in which all 19 wait for members' lists reads each six
// times, 114. So the cap holds an hour of those retries alone, at about 5 s of local work
// and at most about 52 s were every read to parse at the bound, and the hour's reads of a
// Pulls tab left open with every stack settled are none.
// A read `listed` starts counts too: each list the prefetch refreshes makes every drawn
// stack that holds it due at once, so an hour that lists every member of all 19 stacks can
// spend the cap (review C of #484, C2). In review C's simulation, 19 stacks of 8 members,
// each member listed once at a random moment of the first hour, spent all 120; a stack's
// line came at most 11.6 minutes after its last list landed, and a stack first drawn at
// minute 40 waited 21 minutes for its first read. It recovers by itself as the hour's
// reads age out.
export const STACK_LINES_PER_HOUR = 120;
// The stacks whose last outcome the document remembers, oldest out first: more stacks than
// any repository's list draws at once. This repository has 19. Measured 2026-11-16 in Node
// 24, 256 of them, each a stack of 12 pull requests, held 216 KB of heap, 862 bytes each;
// the answers themselves are in the keep, which bounds them with every comparison.
const REMEMBERED_STACKS = 256;
// The recent outcomes a snapshot reports.
const RECENT = 8;
// Refusals that hold for every stack of the server, not one: no stack's change can be had.
const SERVER_REFUSALS = new Set(["not_github"]);

/**
 * What `GET stack-change` answers (pull_stack_change.py, `StackChangeEnvelope`).
 *
 * @typedef {{
 *   state: "absent" | "current",
 *   reason: string | null,
 *   number: number,
 *   pulls: number[],
 *   pending: number[],
 *   revision: string | null,
 *   files: number | null,
 *   additions: number | null,
 *   deletions: number | null,
 *   exact: boolean,
 *   statuses: {status: string, count: number}[],
 * }} StackChange
 *
 * A stack as the list draws it: its number, its members bottom first, and each member's
 * head as the catalog's row reports it, in the members' order, or null where the list holds
 * no row of it.
 * @typedef {{number: number, pulls: number[], heads: (string | null)[]}} StackMembers
 *
 * What a stack's heading shows now: its line, its pending placeholder, or nothing.
 * @typedef {{phase: "shown", change: StackChange} | {phase: "waiting"} | {phase: "none"}} StackLineState
 *
 * A stack's last outcome: its members and their heads as they were known when it was read,
 * the key of its change in the keep, or null, when it is asked again, or null, how many
 * times in a row its answer named members not yet settled, those members, and why it has no
 * change.
 * @typedef {{
 *   members: string,
 *   heads: (string | null)[],
 *   key: string | null,
 *   retryAt: number | null,
 *   tries: number,
 *   pending: number[],
 *   reason: string | null,
 * }} StackLineOutcome
 */

/** The keep's key for a stack's change: its stack and the answer's revision, which names its
 * content.
 * @param {number} number @param {string} revision
 */
export const stackChangeKey = (number, revision) => `stack-change:${number}:${revision}`;

/** A stack of a repository, whatever its members, as the document remembers its outcome.
 * @param {string | null} source @param {number} number
 */
const stackKey = (source, number) => `${source ?? ""}#${number}`;

/**
 * Whether *stack*, as the list draws it now, is the stack *seen* was read for: the same
 * members, and no member whose head both were known with has moved. A member the list holds
 * no row of, as a filter or a window that does not hold it leaves it, is taken as unchanged,
 * so switching filters reads nothing again (review B of #484, B3).
 *
 * @param {StackLineOutcome} seen @param {StackMembers} stack
 */
export function sameStack(seen, stack) {
  return (
    seen.members === stack.pulls.join(",") &&
    stack.heads.every(
      (head, at) => head === null || seen.heads[at] == null || seen.heads[at] === head,
    )
  );
}

/** @param {unknown} value @returns {value is StackChange} */
export function isStackChange(value) {
  if (value === null || typeof value !== "object") {
    return false;
  }
  const body = /** @type {Record<string, unknown>} */ (value);
  const count = (/** @type {unknown} */ part) =>
    part === null || (typeof part === "number" && Number.isInteger(part) && part >= 0);
  return (
    (body.state === "current" || body.state === "absent") &&
    typeof body.number === "number" &&
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
    Array.isArray(body.pulls) &&
    Array.isArray(body.pending) &&
    body.pending.every((member) => Number.isInteger(member)) &&
    (body.state === "absent" || typeof body.revision === "string")
  );
}

/**
 * The change line's input from a stack's change, its line totals alone with no file statuses
 * (mb-lqkb), built as a pull request row's is (change-lines.js), so a stack of one draws its
 * row's line.
 *
 * @param {StackChange} change
 * @returns {MetabrowserChangeLineInput}
 */
export function stackLineInput(change) {
  return changeLineInput(change, null);
}

/**
 * Each stack's last outcome, for the document: a stack of a repository (`stackKey`) to the
 * identity it was read under and the key of its change in the keep, or none.
 *
 * @returns {import("./change-lines.js").BoundedIndex<StackLineOutcome>}
 */
export function createStackLineIndex() {
  return createBoundedIndex(REMEMBERED_STACKS);
}

/** The document's index, which every Pulls tab mounted in it shares. */
export const documentStackLines = createStackLineIndex();

/**
 * The Pulls tab's lane for its stack headings' change lines.
 *
 * @param {{
 *   keep?: import("./comparison-prefetch.js").ComparisonKeep,
 *   index?: ReturnType<typeof createStackLineIndex>,
 *   budget?: import("./comparison-prefetch.js").WarmBudget,
 *   read(number: number, signal: AbortSignal): Promise<{status: number, body: unknown}>,
 *   schedule(callback: () => void): unknown,
 *   cancel(handle: unknown): void,
 *   isVisible(): boolean,
 *   now(): number,
 *   changed(number: number | null): void,
 * }} deps `changed` repaints a stack's heading, or every heading for null.
 */
export function createStackLines(deps) {
  const keep = deps.keep ?? documentComparisons;
  const index = deps.index ?? documentStackLines;
  const budget = deps.budget ?? createWarmBudget(deps.now, STACK_LINES_PER_HOUR);
  /** @typedef {{key: string, stack: StackMembers}} StackRead */
  /** @type {StackRead[]} */
  let queue = [];
  /** The stacks the list last drew, in its order, and its repository. */
  /** @type {{stacks: StackMembers[], source: string | null}} */
  let drawn = { stacks: [], source: null };
  /** @type {unknown} */
  let handle = null;
  /**
   * The read on its way: `sent` once its request is, and `waits` when its heading may hold
   * the placeholder meanwhile.
   * @type {(StackRead & {controller: AbortController, sent: boolean, waits: boolean}) | null}
   */
  let running = null;
  /** A refusal that holds for every stack of the server, and until when. */
  /** @type {{reason: string, until: number} | null} */
  let refusedAll = null;
  /** @type {string[]} */
  const recent = [];
  let disposed = false;

  /** @param {number} number @param {string} outcome */
  function note(number, outcome) {
    recent.push(`${stackLabel(number)}: ${outcome}`);
    if (recent.length > RECENT) {
      recent.shift();
    }
  }

  /** The kept change of a stack's last outcome, if the keep still has it.
   * @param {StackLineOutcome | undefined} seen
   * @returns {StackChange | undefined}
   */
  function kept(seen) {
    if (seen?.key == null) {
      return undefined;
    }
    const held = keep.held(seen.key);
    return isStackChange(held) ? held : undefined;
  }

  /**
   * Whether a stack is to be read: never read as it is drawn now, a retry's time come, or its
   * line let go by the keep. An answer that settled it holds otherwise. A head the list knows
   * now and did not when it was read is kept with the outcome, so a later move is seen.
   * @param {string} key @param {StackMembers} stack
   */
  function due(key, stack) {
    const seen = index.get(key);
    if (seen === undefined || !sameStack(seen, stack)) {
      return true;
    }
    for (const [at, head] of stack.heads.entries()) {
      seen.heads[at] ??= head;
    }
    if (seen.retryAt !== null) {
      return deps.now() >= seen.retryAt;
    }
    return seen.key !== null && !keep.has(seen.key);
  }

  /** Whether a read asked for now would be sent. */
  function canRead() {
    return !disposed && !budget.spent() && (refusedAll === null || deps.now() >= refusedAll.until);
  }

  function next() {
    if (disposed || running !== null || handle !== null || queue.length === 0) {
      return;
    }
    if (!deps.isVisible()) {
      return;
    }
    handle = deps.schedule(() => {
      handle = null;
      const item = queue.shift();
      if (item !== undefined) {
        void run(item);
      }
    });
  }

  /**
   * A stack's outcome as read for *item*, its heads as the list knew them, and a head it does
   * not know now as it was last known, so a filter that holds no row of a member forgets
   * nothing of it.
   * @param {StackRead} item
   * @param {Pick<StackLineOutcome, "key" | "retryAt" | "tries" | "pending" | "reason">} outcome
   */
  function settle(item, outcome) {
    const members = item.stack.pulls.join(",");
    const prior = index.get(item.key);
    const known = prior?.members === members ? prior.heads : [];
    index.set(item.key, {
      members,
      heads: item.stack.heads.map((head, at) => head ?? known[at] ?? null),
      ...outcome,
    });
  }

  /** A read that failed: asked again a minute on, the line it had kept meanwhile (A3).
   * @param {StackRead} item @param {StackLineOutcome | undefined} seen @param {string} outcome
   */
  function failed(item, seen, outcome) {
    settle(item, {
      key: seen?.key ?? null,
      retryAt: deps.now() + STACK_LINE_RETRY_MS,
      tries: 0,
      pending: seen?.pending ?? [],
      reason: null,
    });
    note(item.stack.number, outcome);
  }

  /**
   * When a stack whose answer named unsettled members is asked again: a minute on, doubling
   * each time it is still unsettled as it is drawn, up to `STACK_LINE_PENDING_MAX_MS`.
   * @param {StackRead} item @param {StackLineOutcome | undefined} seen @param {number} at
   */
  function pendingRetry(item, seen, at) {
    const tries =
      seen !== undefined && sameStack(seen, item.stack) && seen.pending.length > 0
        ? seen.tries + 1
        : 0;
    const wait = Math.min(STACK_LINE_RETRY_MS * 2 ** tries, STACK_LINE_PENDING_MAX_MS);
    return { tries, retryAt: at + wait };
  }

  /** @param {StackRead} item */
  async function run(item) {
    if (disposed || !deps.isVisible()) {
      return;
    }
    if (!due(item.key, item.stack) || !canRead()) {
      next();
      return;
    }
    if (!budget.take()) {
      note(item.stack.number, "hourly cap");
      queue = [];
      return;
    }
    const seen = index.get(item.key);
    const controller = new AbortController();
    // A heading waits for its stack's first read as it is drawn, and for a line the keep let
    // go, never again for an answer with no line, one still settling, or a read that failed
    // (A4).
    const waits =
      seen === undefined ||
      !sameStack(seen, item.stack) ||
      (seen.key !== null && seen.retryAt === null);
    const read = { ...item, controller, sent: false, waits };
    running = read;
    try {
      // Behind the reader: a comparison a page is reading goes first.
      await keep.quiet();
      if (controller.signal.aborted) {
        return;
      }
      read.sent = true;
      if (waits && kept(seen) === undefined) {
        // Its heading waits for the read on its way now.
        deps.changed(item.stack.number);
      }
      const answer = await deps.read(item.stack.number, controller.signal);
      if (controller.signal.aborted) {
        return;
      }
      const at = deps.now();
      const body = answer.body;
      if (answer.status === 304 && seen !== undefined) {
        // Unchanged: the stack's last answer holds, as it is drawn now (A10), and a stack it
        // named members not yet settled for is still asked again (review C of #484, C5).
        settle(item, {
          ...seen,
          ...(seen.pending.length > 0 ? pendingRetry(item, seen, at) : { retryAt: null }),
        });
        note(item.stack.number, "unchanged");
      } else if (
        answer.status !== 200 ||
        !isStackChange(body) ||
        body.number !== item.stack.number
      ) {
        failed(item, seen, `failed ${answer.status}`);
      } else {
        // Members not yet settled: asked again, silently, until none is (B1).
        const unsettled = body.pending.length > 0 ? pendingRetry(item, seen, at) : null;
        if (body.state === "current" && body.revision !== null) {
          const key = stackChangeKey(body.number, body.revision);
          keep.put(key, body);
          settle(item, {
            key,
            retryAt: unsettled?.retryAt ?? null,
            tries: unsettled?.tries ?? 0,
            pending: body.pending,
            reason: null,
          });
          note(
            item.stack.number,
            `${keep.has(key) ? "shown" : "not kept"}${unsettled ? ", pending" : ""}`,
          );
        } else {
          const server = body.reason !== null && SERVER_REFUSALS.has(body.reason);
          settle(item, {
            key: null,
            retryAt: server ? at + STACK_LINE_RETRY_MS : (unsettled?.retryAt ?? null),
            tries: unsettled?.tries ?? 0,
            pending: body.pending,
            reason: body.reason,
          });
          if (server) {
            refusedAll = {
              reason: /** @type {string} */ (body.reason),
              until: at + STACK_LINE_RETRY_MS,
            };
            queue = [];
          }
          note(item.stack.number, `${body.reason ?? "absent"}${unsettled ? ", pending" : ""}`);
        }
      }
      deps.changed(item.stack.number);
    } catch {
      if (controller.signal.aborted) {
        note(item.stack.number, "cancelled");
      } else {
        failed(item, seen, "failed");
        deps.changed(item.stack.number);
      }
    } finally {
      if (running === read) {
        running = null;
      }
      next();
    }
  }

  /**
   * The stacks the list draws, in its order, of which those due are queued.
   * @param {StackMembers[]} stacks
   * @param {string | null} source
   */
  function want(stacks, source) {
    if (disposed) {
      return;
    }
    drawn = { stacks, source };
    const seen = new Set();
    queue = [];
    // A refusal of the whole server, or the hour's cap spent: nothing would be sent.
    for (const stack of canRead() ? stacks : []) {
      const key = stackKey(source, stack.number);
      if (seen.has(key) || running?.key === key || !due(key, stack)) {
        continue;
      }
      seen.add(key);
      queue.push({ key, stack });
    }
    if (queue.length === 0 && handle !== null) {
      deps.cancel(handle);
      handle = null;
    }
    next();
  }

  return Object.freeze({
    /**
     * What *stack*'s heading shows now: its kept line, whatever it was read as, until a newer
     * answer replaces it; the placeholder while its stack's read is on its way, unless its
     * last outcome as it is drawn was an answer with no line, one still settling, or a
     * failure; or nothing.
     *
     * @param {StackMembers} stack
     * @param {string | null} source
     * @returns {StackLineState}
     */
    line(stack, source) {
      const key = stackKey(source, stack.number);
      const change = kept(index.get(key));
      if (change !== undefined) {
        return { phase: "shown", change };
      }
      if (running !== null && running.key === key && running.sent && running.waits) {
        return { phase: "waiting" };
      }
      return { phase: "none" };
    },
    /**
     * The stacks the list draws, in its order, of which those due are queued. An ask replaces
     * the queue; the read on its way goes on, since the server sums what it was asked for
     * whether or not the asker stays. An empty ask, as a panel hidden or offline asks, empties
     * it.
     */
    want,
    /**
     * Pull request *number*'s list of changed files changed, as the prefetch lane or a row's
     * own read saw it: each drawn stack that holds it is due now, silently (B1).
     *
     * @param {number} number
     */
    listed(number) {
      if (disposed) {
        return;
      }
      for (const stack of drawn.stacks) {
        const seen = index.get(stackKey(drawn.source, stack.number));
        if (seen !== undefined && stack.pulls.includes(number)) {
          seen.retryAt = deps.now();
        }
      }
      want(drawn.stacks, drawn.source);
    },
    /**
     * The members, in the drawn stacks' order, that the stacks' last answers named as not
     * settled, for the prefetch to list (B2).
     *
     * @param {(number: number) => boolean} [first] The stacks to take first: those in view.
     * @returns {number[]}
     */
    unsettled(first = () => false) {
      const order = [...drawn.stacks].sort(
        (left, right) => Number(first(right.number)) - Number(first(left.number)),
      );
      const members = order.flatMap((stack) => {
        const seen = index.get(stackKey(drawn.source, stack.number));
        return seen !== undefined && sameStack(seen, stack) ? seen.pending : [];
      });
      return [...new Set(members)];
    },
    dispose() {
      disposed = true;
      queue = [];
      if (handle !== null) {
        deps.cancel(handle);
        handle = null;
      }
      running?.controller.abort();
      running = null;
    },
    snapshot: () => ({
      queue: queue.map((item) => item.stack.number),
      running: running?.stack.number ?? null,
      sentThisHour: budget.count(),
      refusedAll: refusedAll?.reason ?? null,
      recent: [...recent],
    }),
  });
}
