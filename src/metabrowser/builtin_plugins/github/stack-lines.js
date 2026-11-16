// A native stack's brief change line, on its heading in the Pulls column (mb-9ekj):
// "Stack #286 · 10 A, 5 D, 4 M · +1,234 −567".
//
// What it says is the stack's combined change, its bottom pull request's base against its top
// pull request's head, which the server sums in the repository store from the two cached
// records' comparisons (`GET stack-change`, pull_stack_change.py). Summing each pull request's
// own counts would count twice a file two layers change. The line is the shell's one
// component for a change set said in brief (docs/design-system.md, "Brief Change Line"), built
// and painted through the SDK, `metabrowser.changeLine` and `metabrowser.changeLineNodes`;
// nothing here paints its parts.
//
// When it is read, and what it costs:
//
// - Only for the stacks whose rows the list draws, its rows in view and the window's overscan,
//   one at a time, each when the browser is idle, and only once no comparison is being read,
//   so a page's own read goes first (`keep.quiet`), as the comparison warmer's are.
// - Each read counts against the Pulls tab's hourly cap, which the warmer's share
//   (`WARM_PER_HOUR`, `createWarmBudget`). A read is the stack snapshot and two records from
//   the cache and, the first time a stack's two ends are asked for, their comparison listed
//   in the store, a manifest with no patch; no GitHub call. Measured 2026-11-16 on this
//   repository's 19 stacks of 2 to 46 pull requests (pull_stack_change.py): a first answer
//   ran 3 Git processes and took 52 to 298 ms, and a repeat ran none and took under 1 ms.
// - An answer was 318 to 430 bytes of JSON. It is kept in the document's comparison keep
//   under its two commits (`stackChangeKey`), and which answer is each stack's is kept for
//   the document too (`documentStackLines`), so a heading drawn again, scrolled back into
//   view or in a Pulls tab mounted again, has its line in the paint that draws it, with no
//   request. It is asked again once its window passes, the answer's `fresh_for_s`, the stack
//   snapshot's own window, since its members and so its ends may have moved; the line it
//   had stays shown meanwhile.
//
// A heading waits for its line in the shell's pending placeholder, after the quiet period, so
// nothing moves when the line arrives. A stack whose change cannot be had, a server with no
// store or a stack whose ends are not cached, shows no line and no placeholder, and neither
// does a heading whose read the cap holds.

import { createWarmBudget, documentComparisons } from "./comparison-prefetch.js";
import { stackLabel } from "./pull-stacks.js";

export const STACK_CHANGE_ROUTE = "/api/plugin/github/stack-change";

// A read that failed, a refusal of the request or a broken connection rather than an
// answer, is asked again after a minute, the pull routes' own freshness window
// (`FRESHNESS_WINDOW_S`), so a failure that lasts costs one read a minute a stack at most.
export const STACK_LINE_RETRY_MS = 60_000;
// The answers whose stack the document remembers, oldest out first: more stacks than any
// repository's list draws at once. This repository has 19. Measured 2026-11-16 in Node 24,
// 256 of them, each a stack of 12 pull requests, held 216 KB of heap, 862 bytes each; the
// answers themselves are in the keep, which bounds them with every comparison.
const REMEMBERED_STACKS = 256;
// The recent outcomes a snapshot reports.
const RECENT = 8;
// Refusals that hold for every stack of the server, not one: no stack's change can be had.
const SERVER_REFUSALS = new Set(["not_github", "no_store"]);

/**
 * What `GET stack-change` answers (pull_stack_change.py, `StackChangeEnvelope`).
 *
 * @typedef {{
 *   state: "absent" | "current",
 *   reason: string | null,
 *   number: number,
 *   bottom: number | null,
 *   top: number | null,
 *   base: string | null,
 *   head: string | null,
 *   fresh_for_s: number,
 *   files: number | null,
 *   additions: number | null,
 *   deletions: number | null,
 *   exact: boolean,
 *   statuses: {status: string, count: number}[],
 * }} StackChange
 *
 * @typedef {{number: number, pulls: number[]}} StackMembers
 *
 * What a stack's heading shows now: its line, its pending placeholder, or nothing.
 * @typedef {{phase: "shown", change: StackChange} | {phase: "waiting"} | {phase: "none"}} StackLineState
 *
 * @typedef {{key: string | null, at: number, holdsMs: number, reason: string | null}} StackLineOutcome
 */

/** The keep's key for a stack's change: the two commits it runs between.
 * @param {string} base @param {string} head
 */
export const stackChangeKey = (base, head) => `stack-change:${base}...${head}`;

/** A stack as the document remembers its line: its repository, its number, and its members,
 * so a stack whose members change is a stack asked for again.
 * @param {string | null} source @param {StackMembers} stack
 */
export const stackLineIdentity = (source, stack) =>
  `${source ?? ""}#${stack.number}:${stack.pulls.join(",")}`;

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
    typeof body.fresh_for_s === "number" &&
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
    (body.state === "absent" || (typeof body.base === "string" && typeof body.head === "string"))
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
 * Which stack each kept change is, for the document: a stack's identity
 * (`stackLineIdentity`) to its last outcome, the key of its change in the keep, or none.
 */
export function createStackLineIndex() {
  /** @type {Map<string, StackLineOutcome>} */
  const outcomes = new Map();
  return Object.freeze({
    /** @param {string} identity */
    get: (identity) => outcomes.get(identity),
    /** @param {string} identity @param {StackLineOutcome} outcome */
    set(identity, outcome) {
      outcomes.delete(identity);
      outcomes.set(identity, outcome);
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
  const budget = deps.budget ?? createWarmBudget(deps.now);
  /** @type {{identity: string, number: number}[]} */
  let queue = [];
  /** @type {unknown} */
  let handle = null;
  /** @type {{identity: string, number: number, controller: AbortController} | null} */
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

  /** Whether *identity*'s last outcome still holds: within its window, and its change, if it
   * had one, still kept.
   * @param {string} identity
   */
  function settled(identity) {
    const seen = index.get(identity);
    return (
      seen !== undefined &&
      deps.now() - seen.at < seen.holdsMs &&
      (seen.key === null || keep.has(seen.key))
    );
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

  /** @param {{identity: string, number: number}} item */
  async function run(item) {
    if (disposed || !deps.isVisible()) {
      return;
    }
    if (settled(item.identity) || !canRead()) {
      next();
      return;
    }
    if (!budget.take()) {
      note(item.number, "hourly cap");
      queue = [];
      // The placeholders the queue held wait for nothing now.
      deps.changed(null);
      return;
    }
    const controller = new AbortController();
    running = { ...item, controller };
    try {
      // Behind the reader: a comparison a page is reading goes first.
      await keep.quiet();
      if (controller.signal.aborted) {
        return;
      }
      const answer = await deps.read(item.number, controller.signal);
      if (controller.signal.aborted) {
        return;
      }
      const at = deps.now();
      const body = answer.body;
      if (answer.status !== 200 || !isStackChange(body) || body.number !== item.number) {
        index.set(item.identity, { key: null, at, holdsMs: STACK_LINE_RETRY_MS, reason: null });
        note(item.number, `failed ${answer.status}`);
      } else {
        const holdsMs = body.fresh_for_s * 1000;
        if (body.state === "current" && body.base !== null && body.head !== null) {
          const key = stackChangeKey(body.base, body.head);
          keep.put(key, body);
          index.set(item.identity, { key, at, holdsMs, reason: null });
          note(item.number, keep.has(key) ? "shown" : "not kept");
        } else {
          index.set(item.identity, { key: null, at, holdsMs, reason: body.reason });
          if (body.reason !== null && SERVER_REFUSALS.has(body.reason)) {
            refusedAll = { reason: body.reason, until: at + holdsMs };
            queue = [];
            deps.changed(null);
          }
          note(item.number, body.reason ?? "absent");
        }
      }
      deps.changed(item.number);
    } catch {
      if (controller.signal.aborted) {
        note(item.number, "cancelled");
      } else {
        index.set(item.identity, {
          key: null,
          at: deps.now(),
          holdsMs: STACK_LINE_RETRY_MS,
          reason: null,
        });
        note(item.number, "failed");
        deps.changed(item.number);
      }
    } finally {
      if (running?.controller === controller) {
        running = null;
      }
      next();
    }
  }

  return Object.freeze({
    /**
     * What *stack*'s heading shows now: its kept line, shown whether or not its window has
     * passed, until a newer answer replaces it; the placeholder while a read of it is coming;
     * or nothing, when its change cannot be had or no read of it will be sent.
     *
     * @param {StackMembers} stack
     * @param {string | null} source
     * @returns {StackLineState}
     */
    line(stack, source) {
      const identity = stackLineIdentity(source, stack);
      const seen = index.get(identity);
      const change = kept(seen);
      if (change !== undefined) {
        return { phase: "shown", change };
      }
      if (settled(identity) || !canRead()) {
        return { phase: "none" };
      }
      return { phase: "waiting" };
    },
    /**
     * The stacks the list draws, in its order. An ask replaces the queue; the read on its way
     * goes on, since the server sums what it was asked for whether or not the asker stays.
     * An empty ask, as a panel hidden or offline asks, empties it.
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
      for (const stack of stacks) {
        const identity = stackLineIdentity(source, stack);
        if (seen.has(identity) || running?.identity === identity || settled(identity)) {
          continue;
        }
        seen.add(identity);
        queue.push({ identity, number: stack.number });
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
