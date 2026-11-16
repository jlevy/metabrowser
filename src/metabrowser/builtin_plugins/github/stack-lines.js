// A native stack's brief change line, on its heading in the Pulls column (mb-9ekj):
// "Stack #286 · 10 A, 5 D, 4 M · +1,234 −567".
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
// - Once for each stack's identity (`stackLineIdentity`): its members and each member's head
//   as the catalog's rows report it. Any member's change moves the accumulation, and a
//   member's change moves its head, so a stack is read again when the list's rows say a
//   member moved or the members changed, and never on a timer (review of #484, A2). A read
//   that failed is asked again a minute on; a stack with a member whose list is not cached
//   is not, until its identity changes.
// - Within the lines' own hourly cap (`STACK_LINES_PER_HOUR`), apart from the comparison
//   warmer's (`WARM_PER_HOUR`), so the lines never take the warms' share. A read is the stack
//   snapshot and each member's list of changed files from the cache; no GitHub call, no
//   fetch, and no Git.
// - An answer is a few hundred bytes of JSON. It is kept in the document's comparison keep
//   under its stack and its revision (`stackChangeKey`), and which answer is each stack's is
//   kept for the document too (`documentStackLines`), so a heading drawn again, scrolled
//   back into view or in a Pulls tab mounted again, has its line in the paint that draws it,
//   with no request. A line stays shown until a newer answer replaces it: while its stack is read
//   again, and when that read fails.
//
// A heading waits for its line in the shell's pending placeholder only while the read of its
// stack is on its way, after the quiet period, and its accessible name says the change is
// pending meanwhile. A stack whose last answer for its identity was not a line, whose change
// cannot be had, never waits again until its identity changes, so its heading does not
// pulse and go blank (review of #484, A4). Nor does a heading whose read is queued behind
// another, or whose read the cap holds.

import { createWarmBudget, documentComparisons } from "./comparison-prefetch.js";
import { stackLabel } from "./pull-stacks.js";

export const STACK_CHANGE_ROUTE = "/api/plugin/github/stack-change";

// A read that failed, a refusal of the request, a broken connection, or a refusal that holds
// for the whole server, is asked again after a minute, the pull routes' own freshness window
// (`FRESHNESS_WINDOW_S`), so a failure that lasts costs one read a minute a stack at most.
export const STACK_LINE_RETRY_MS = 60_000;
// The reads the lines start in an hour, each counted as it starts; the comparison warmer
// counts its own (`WARM_PER_HOUR`). A read runs no Git: it stats each member's list and,
// when one changed since the server last accumulated them, parses them all, 6 to 16 ms for
// #446's 16 cached lists and at most about 210 ms within `MAX_STACK_LIST_BYTES`, a repeat
// 0.2 ms (measured 2026-11-16 at a load average of 26 to 38, pull_stack_change.py). The
// list draws every one of this repository's 19 stacks, so a first visit reads 19, and the
// rest of an hour's reads are stacks whose member moved, and failed reads asked again. So
// the cap is at most about 13 s of local parsing an hour, and the hour's reads of a Pulls
// tab left open with nothing changing are none.
export const STACK_LINES_PER_HOUR = 60;
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
 * A stack's last outcome: the identity it was read under, the key of its change in the keep,
 * or null, when it is asked again after a failure, or null, and why it has no change.
 * @typedef {{identity: string, key: string | null, retryAt: number | null, reason: string | null}} StackLineOutcome
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

/** What a stack's answer depends on that the list knows: its repository, its number, its
 * members, and each member's head, so a stack whose members change or any of whose members
 * moves is asked for again.
 * @param {string | null} source @param {StackMembers} stack
 */
export const stackLineIdentity = (source, stack) =>
  `${stackKey(source, stack.number)}:${stack.pulls
    .map((number, at) => `${number}@${stack.heads[at] ?? "-"}`)
    .join(",")}`;

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
    (body.state === "absent" || typeof body.revision === "string")
  );
}

/**
 * The change line's input from a stack's change: its statuses in the header's order, each
 * with its letter and word, from the changed-files tree's own breakdown, which the Diff
 * summary's header reads, and its line totals. With no tree, a line of its totals alone, as
 * the Diff summary's fallback line is.
 *
 * @param {StackChange} change
 * @param {((statuses: Iterable<string>) => MetabrowserChangeLineInput["statuses"]) | null} breakdown
 * @returns {MetabrowserChangeLineInput}
 */
export function stackLineInput(change, breakdown) {
  const statuses =
    breakdown === null
      ? []
      : breakdown(
          change.statuses.flatMap((entry) =>
            Array.from({ length: entry.count }, () => entry.status),
          ),
        );
  return { statuses, additions: change.additions, deletions: change.deletions };
}

/**
 * Each stack's last outcome, for the document: a stack of a repository (`stackKey`) to the
 * identity it was read under and the key of its change in the keep, or none.
 */
export function createStackLineIndex() {
  /** @type {Map<string, StackLineOutcome>} */
  const outcomes = new Map();
  return Object.freeze({
    /** @param {string} stack */
    get: (stack) => outcomes.get(stack),
    /** @param {string} stack @param {StackLineOutcome} outcome */
    set(stack, outcome) {
      outcomes.delete(stack);
      outcomes.set(stack, outcome);
      if (outcomes.size > REMEMBERED_STACKS) {
        outcomes.delete(/** @type {string} */ (outcomes.keys().next().value));
      }
    },
    clear: () => outcomes.clear(),
  });
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
  /** @typedef {{stack: string, identity: string, number: number}} StackRead */
  /** @type {StackRead[]} */
  let queue = [];
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

  /** Whether a stack is to be read: never read under this identity, a failed read's minute
   * passed, or its line let go by the keep. An answer for its identity holds otherwise.
   * @param {string} stack @param {string} identity
   */
  function due(stack, identity) {
    const seen = index.get(stack);
    if (seen === undefined || seen.identity !== identity) {
      return true;
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

  /** A read that failed: asked again a minute on, the line it had kept meanwhile (A3).
   * @param {StackRead} item @param {StackLineOutcome | undefined} seen @param {string} outcome
   */
  function failed(item, seen, outcome) {
    index.set(item.stack, {
      identity: item.identity,
      key: seen?.key ?? null,
      retryAt: deps.now() + STACK_LINE_RETRY_MS,
      reason: null,
    });
    note(item.number, outcome);
  }

  /** @param {StackRead} item */
  async function run(item) {
    if (disposed || !deps.isVisible()) {
      return;
    }
    if (!due(item.stack, item.identity) || !canRead()) {
      next();
      return;
    }
    if (!budget.take()) {
      note(item.number, "hourly cap");
      queue = [];
      return;
    }
    const seen = index.get(item.stack);
    const controller = new AbortController();
    // A heading waits for a stack's first read under its identity, and for a line the keep
    // let go, never again for an answer with no line or a read that failed (A4).
    const waits = seen?.identity !== item.identity || (seen.key !== null && seen.retryAt === null);
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
        deps.changed(item.number);
      }
      const answer = await deps.read(item.number, controller.signal);
      if (controller.signal.aborted) {
        return;
      }
      const at = deps.now();
      const body = answer.body;
      if (answer.status === 304 && seen !== undefined) {
        // Unchanged: the stack's last answer holds for its identity now (A10).
        index.set(item.stack, { ...seen, identity: item.identity, retryAt: null });
        note(item.number, "unchanged");
      } else if (answer.status !== 200 || !isStackChange(body) || body.number !== item.number) {
        failed(item, seen, `failed ${answer.status}`);
      } else if (body.state === "current" && body.revision !== null) {
        const key = stackChangeKey(body.number, body.revision);
        keep.put(key, body);
        index.set(item.stack, { identity: item.identity, key, retryAt: null, reason: null });
        note(item.number, keep.has(key) ? "shown" : "not kept");
      } else {
        const server = body.reason !== null && SERVER_REFUSALS.has(body.reason);
        index.set(item.stack, {
          identity: item.identity,
          key: null,
          retryAt: server ? at + STACK_LINE_RETRY_MS : null,
          reason: body.reason,
        });
        if (server) {
          refusedAll = {
            reason: /** @type {string} */ (body.reason),
            until: at + STACK_LINE_RETRY_MS,
          };
          queue = [];
        }
        note(item.number, body.reason ?? "absent");
      }
      deps.changed(item.number);
    } catch {
      if (controller.signal.aborted) {
        note(item.number, "cancelled");
      } else {
        failed(item, seen, "failed");
        deps.changed(item.number);
      }
    } finally {
      if (running === read) {
        running = null;
      }
      next();
    }
  }

  return Object.freeze({
    /**
     * What *stack*'s heading shows now: its kept line, whatever identity it was read under,
     * until a newer answer replaces it; the placeholder while its stack's read is on its way,
     * unless its last outcome under this identity was an answer with no line or a failure;
     * or nothing.
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
      if (running !== null && running.stack === key && running.sent && running.waits) {
        return { phase: "waiting" };
      }
      return { phase: "none" };
    },
    /**
     * The stacks the list draws, in its order, of which those due are queued. An ask replaces
     * the queue; the read on its way goes on, since the server sums what it was asked for
     * whether or not the asker stays. An empty ask, as a panel hidden or offline asks, empties
     * it.
     *
     * @param {StackMembers[]} stacks
     * @param {string | null} source
     */
    want(stacks, source) {
      if (disposed) {
        return;
      }
      const seen = new Set();
      queue = [];
      // A refusal of the whole server, or the hour's cap spent: nothing would be sent.
      for (const stack of canRead() ? stacks : []) {
        const key = stackKey(source, stack.number);
        const identity = stackLineIdentity(source, stack);
        if (seen.has(key) || running?.identity === identity || !due(key, identity)) {
          continue;
        }
        seen.add(key);
        queue.push({ stack: key, identity, number: stack.number });
      }
      if (queue.length === 0 && handle !== null) {
        deps.cancel(handle);
        handle = null;
      }
      next();
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
      queue: queue.map((item) => item.number),
      running: running?.number ?? null,
      sentThisHour: budget.count(),
      refusedAll: refusedAll?.reason ?? null,
      recent: [...recent],
    }),
  });
}
